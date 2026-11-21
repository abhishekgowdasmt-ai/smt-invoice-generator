"""In-app notifications for clients and supervisors (Master Prompt 7).

Driver notifications remain on driver_notifications (migration 010/016).
Client and staff tables require migration 016. Inserts are idempotent via
event_key when the column/index is present. Failures to notify must not
roll back the originating business transaction when called after commit.
"""
from __future__ import annotations

import dev_postgres as pg


def notifications_schema_ready(cur=None):
    def work(cursor):
        cursor.execute(
            """
            SELECT to_regclass('public.client_notifications') IS NOT NULL,
                   to_regclass('public.staff_notifications') IS NOT NULL
            """
        )
        client_ok, staff_ok = cursor.fetchone()
        return bool(client_ok and staff_ok)

    if cur is not None:
        return work(cur)
    if pg.local_development_dsn() is None:
        return False
    try:
        import psycopg

        with psycopg.connect(pg.local_development_dsn(), connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                return work(cursor)
    except Exception:
        return False


def _iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _insert_ignore_duplicate(cur, sql, params):
    try:
        cur.execute("SAVEPOINT notif_write")
        cur.execute(sql, params)
        cur.execute("RELEASE SAVEPOINT notif_write")
        return True
    except Exception:
        try:
            cur.execute("ROLLBACK TO SAVEPOINT notif_write")
        except Exception:
            pass
        return False


def notify_client(
    user_id,
    *,
    company_id,
    kind,
    title,
    body,
    event_key=None,
    booking_id=None,
    invoice_id=None,
    target_user_id=None,
):
    """Best-effort client notification under the actor transaction."""

    def work(cur):
        if not notifications_schema_ready(cur):
            return {"ok": False, "error": "unavailable", "message": "Client notifications need migration 016."}
        company_id_p = pg._parse_uuid(company_id)
        if company_id_p is None:
            return {"ok": False, "error": "invalid", "message": "Company is not valid."}
        try:
            cur.execute("SAVEPOINT notif_write")
            cur.execute(
                """
                SELECT post_client_notification(
                    %s::uuid, %s, %s, %s, %s, %s::uuid, %s::uuid, %s::uuid
                )
                """,
                (
                    company_id_p,
                    kind,
                    title,
                    body,
                    event_key,
                    pg._parse_uuid(booking_id) if booking_id else None,
                    pg._parse_uuid(invoice_id) if invoice_id else None,
                    pg._parse_uuid(target_user_id) if target_user_id else None,
                ),
            )
            new_id = cur.fetchone()[0]
            cur.execute("RELEASE SAVEPOINT notif_write")
            return {"ok": True, "inserted": new_id is not None, "id": new_id}
        except Exception:
            try:
                cur.execute("ROLLBACK TO SAVEPOINT notif_write")
            except Exception:
                pass
            return {"ok": True, "inserted": False}

    done = pg.authorized_transaction(user_id, work)
    if not done:
        return None
    return done.get("result")


def notify_staff(
    user_id,
    *,
    kind,
    title,
    body,
    event_key=None,
    branch_id=None,
    company_id=None,
    booking_id=None,
    driver_id=None,
    invoice_id=None,
):
    def work(cur):
        if not notifications_schema_ready(cur):
            return {"ok": False, "error": "unavailable", "message": "Staff notifications need migration 016."}
        try:
            cur.execute("SAVEPOINT notif_write")
            cur.execute(
                """
                SELECT post_staff_notification(
                    %s, %s, %s, %s, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid
                )
                """,
                (
                    kind,
                    title,
                    body,
                    event_key,
                    pg._parse_uuid(branch_id) if branch_id else None,
                    pg._parse_uuid(company_id) if company_id else None,
                    pg._parse_uuid(booking_id) if booking_id else None,
                    pg._parse_uuid(driver_id) if driver_id else None,
                    pg._parse_uuid(invoice_id) if invoice_id else None,
                ),
            )
            new_id = cur.fetchone()[0]
            cur.execute("RELEASE SAVEPOINT notif_write")
            return {"ok": True, "inserted": new_id is not None, "id": new_id}
        except Exception:
            try:
                cur.execute("ROLLBACK TO SAVEPOINT notif_write")
            except Exception:
                pass
            return {"ok": True, "inserted": False}

    done = pg.authorized_transaction(user_id, work)
    if not done:
        return None
    return done.get("result")


def list_client_notifications(user_id):
    def work(cur):
        if not notifications_schema_ready(cur):
            return {"ok": False, "error": "unavailable", "message": "Client notifications need migration 016."}
        cur.execute(
            """
            SELECT id::text, kind, title, body, read_at, created_at,
                   booking_id::text, invoice_id::text, company_id::text
            FROM client_notifications
            WHERE client_can_company(company_id)
            ORDER BY created_at DESC
            LIMIT 100
            """
        )
        items = [
            {
                "id": r[0],
                "kind": r[1],
                "title": r[2],
                "body": r[3],
                "read_at": _iso(r[4]),
                "created_at": _iso(r[5]),
                "booking_id": r[6],
                "invoice_id": r[7],
                "company_id": r[8],
            }
            for r in cur.fetchall()
        ]
        unread = sum(1 for item in items if not item["read_at"])
        return {"ok": True, "notifications": items, "unread_count": unread}

    # Client actor path
    done = pg.authorized_transaction(user_id, work)
    if not done or done.get("role") != "client":
        return None
    return done.get("result")


def mark_client_notification_read(user_id, notification_id):
    try:
        nid = int(notification_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "not_found", "message": "Notification was not found."}

    def work(cur):
        if not notifications_schema_ready(cur):
            return {"ok": False, "error": "unavailable", "message": "Client notifications need migration 016."}
        cur.execute(
            """
            UPDATE client_notifications
            SET read_at = COALESCE(read_at, now())
            WHERE id = %s AND client_can_company(company_id)
            RETURNING id::text
            """,
            (nid,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "Notification was not found."}
        return {"ok": True, "id": row[0]}

    done = pg.authorized_transaction(user_id, work)
    if not done or done.get("role") != "client":
        return None
    return done.get("result")


def list_staff_notifications(user_id):
    def work(cur):
        if not notifications_schema_ready(cur):
            return {"ok": False, "error": "unavailable", "message": "Staff notifications need migration 016."}
        cur.execute(
            """
            SELECT id::text, kind, title, body, read_at, created_at,
                   branch_id::text, company_id::text, booking_id::text,
                   driver_id::text, invoice_id::text
            FROM staff_notifications
            ORDER BY created_at DESC
            LIMIT 100
            """
        )
        items = [
            {
                "id": r[0],
                "kind": r[1],
                "title": r[2],
                "body": r[3],
                "read_at": _iso(r[4]),
                "created_at": _iso(r[5]),
                "branch_id": r[6],
                "company_id": r[7],
                "booking_id": r[8],
                "driver_id": r[9],
                "invoice_id": r[10],
            }
            for r in cur.fetchall()
        ]
        unread = sum(1 for item in items if not item["read_at"])
        return {"ok": True, "notifications": items, "unread_count": unread}

    return pg._actor_work(user_id, work)


def mark_staff_notification_read(user_id, notification_id):
    try:
        nid = int(notification_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "not_found", "message": "Notification was not found."}

    def work(cur):
        if not notifications_schema_ready(cur):
            return {"ok": False, "error": "unavailable", "message": "Staff notifications need migration 016."}
        cur.execute(
            """
            UPDATE staff_notifications
            SET read_at = COALESCE(read_at, now())
            WHERE id = %s
            RETURNING id::text
            """,
            (nid,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "Notification was not found."}
        return {"ok": True, "id": row[0]}

    return pg._actor_work(user_id, work)


def emit_after_client_booking(actor_user_id, booking):
    """Notify staff of a new client request; acknowledge to the client company."""
    if not booking or booking.get("origin") != "client_request":
        return
    booking_id = booking.get("id")
    company_id = booking.get("company_id")
    branch_id = booking.get("branch_id")
    source = booking.get("source_booking_id") or booking_id or "request"
    try:
        if company_id:
            notify_client(
                actor_user_id,
                company_id=company_id,
                kind="booking_received",
                title="Booking request received",
                body="We received your booking request %s." % source,
                event_key="client-booking-received:%s" % booking_id,
                booking_id=booking_id,
            )
        notify_staff(
            actor_user_id,
            kind="client_request",
            title="New client booking request",
            body="Client request %s needs review." % source,
            event_key="staff-client-request:%s" % booking_id,
            branch_id=branch_id,
            company_id=company_id,
            booking_id=booking_id,
        )
    except Exception:
        return


def emit_assignment_client_update(actor_user_id, booking, assignment_status):
    if not booking or not booking.get("company_id"):
        return
    labels = {
        "assigned": ("Trip assigned", "A driver has been assigned to your booking."),
        "accepted": ("Driver accepted", "Your assigned driver accepted the trip."),
        "started": ("Trip started", "Your trip has started."),
        "completed": ("Trip completed", "Your trip is marked completed."),
        "cancelled": ("Booking cancelled", "Your booking was cancelled."),
    }
    pair = labels.get(assignment_status)
    if not pair:
        return
    title, body = pair
    try:
        notify_client(
            actor_user_id,
            company_id=booking["company_id"],
            kind="trip_%s" % assignment_status,
            title=title,
            body=body,
            event_key="client-trip-%s:%s" % (assignment_status, booking.get("id")),
            booking_id=booking.get("id"),
        )
    except Exception:
        return


def emit_driver_reject_staff(actor_user_id, booking, driver_id, reason=None):
    if not booking:
        return
    try:
        notify_staff(
            actor_user_id,
            kind="driver_reject",
            title="Driver rejected assignment",
            body=(reason or "A driver rejected an assignment.")[:240],
            event_key="staff-reject:%s:%s" % (booking.get("id"), driver_id or "x"),
            branch_id=booking.get("branch_id"),
            company_id=booking.get("company_id"),
            booking_id=booking.get("id"),
            driver_id=driver_id,
        )
    except Exception:
        return


def emit_invoice_issued_client(actor_user_id, invoice):
    if not invoice or not invoice.get("company_id"):
        return
    try:
        notify_client(
            actor_user_id,
            company_id=invoice["company_id"],
            kind="invoice_issued",
            title="Invoice issued",
            body="Invoice %s is ready." % (invoice.get("invoice_number") or invoice.get("id")),
            event_key="client-invoice:%s" % invoice.get("id"),
            invoice_id=invoice.get("id"),
        )
    except Exception:
        return


def emit_payment_client(actor_user_id, invoice, payment_id, reversed_flag=False):
    if not invoice or not invoice.get("company_id"):
        return
    kind = "payment_reversed" if reversed_flag else "payment_recorded"
    title = "Payment reversed" if reversed_flag else "Payment recorded"
    body = (
        "A payment on invoice %s was reversed."
        if reversed_flag
        else "A payment on invoice %s was recorded."
    ) % (invoice.get("invoice_number") or invoice.get("id"))
    try:
        notify_client(
            actor_user_id,
            company_id=invoice["company_id"],
            kind=kind,
            title=title,
            body=body,
            event_key="client-%s:%s" % (kind, payment_id),
            invoice_id=invoice.get("id"),
        )
    except Exception:
        return
