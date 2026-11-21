"""PostgreSQL operational duty lifecycle for the supervisor portal.

Assignment, trip sessions and WhatsApp delivery for shared-origin bookings
(rac, retail, client_request). Does not touch rac_data.json or /api/v1 RAC routes.
"""
from __future__ import annotations

import os
import re
import uuid
from urllib.parse import quote

# Origins that supervisors may assign/reassign through the shared duty APIs.
_ASSIGNABLE_ORIGINS = frozenset(("rac", "retail", "client_request"))

import requests

import dev_postgres as pg

WA_BRIDGE_URL = os.environ.get("WA_BRIDGE_URL") or "http://127.0.0.1:3100"
_TRIGGER_NAMES = (
    "assignment_after",
    "session_after",
    "bookings_write_event_and_close",
)
_TRIGGER_REQUIRED = (
    "Assignment triggers need migration 007 (search_path)."
)
_OPEN_STATUSES = ("assigned", "accepted")


def _wa_digits(phone):
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def _wa_link(phone, body):
    digits = _wa_digits(phone)
    if not digits:
        return ""
    return "https://wa.me/%s?text=%s" % (digits, quote(body or ""))


def _display_date(value):
    text = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return text or "N/A"
    months = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    year, month, day = match.group(1), int(match.group(2)), int(match.group(3))
    if month < 1 or month > 12:
        return text
    return "%s %s %s" % (int(day), months[month - 1], year)


def _trip_facts(booking):
    return (
        "Booking ID: %s\n"
        "Date: %s\n"
        "Pickup: %s\n"
        "Pickup Time: %s\n"
        "Duty Type: %s\n"
        "Cab Type: %s"
        % (
            booking.get("source_booking_id") or "N/A",
            _display_date(booking.get("trip_date")),
            booking.get("planned_start") or "N/A",
            booking.get("pickup_time") or "N/A",
            booking.get("duty_type") or "N/A",
            booking.get("cab_type") or "N/A",
        )
    )


def _assign_body(booking, reassigned=False):
    headline = "This duty is now yours." if reassigned else "New ride assigned."
    return "%s\n\n%s\n\nPlease confirm this trip." % (headline, _trip_facts(booking))


def _release_body(booking, reason):
    if reason == "cancelled":
        headline = "This trip is cancelled. Do not proceed."
    elif reason == "reassigned":
        headline = (
            "This duty has been taken off you and given to another driver. "
            "Do not proceed."
        )
    else:
        headline = "This duty has been taken off you. Do not proceed."
    return "%s\n\n%s" % (headline, _trip_facts(booking))


def _bridge_send(phone, body):
    try:
        data = requests.post(
            "%s/send" % WA_BRIDGE_URL,
            json={"phone": phone, "message": body},
            timeout=25,
        ).json()
        return bool(data.get("success")), data
    except Exception as exc:
        return False, {"error": str(exc)}


def assignment_triggers_ready(cur=None):
    """True when the three duty AFTER triggers can resolve public objects."""

    def work(cursor):
        cursor.execute(
            """
            SELECT p.proname, coalesce(array_to_string(p.proconfig, ','), '')
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
              AND p.proname = ANY(%s)
            """,
            (list(_TRIGGER_NAMES),),
        )
        found = {name: cfg.lower() for name, cfg in cursor.fetchall()}
        if len(found) != len(_TRIGGER_NAMES):
            return False
        for name in _TRIGGER_NAMES:
            cfg = found.get(name) or ""
            if "search_path" not in cfg or "public" not in cfg:
                return False
        return True

    if cur is not None:
        return work(cur)
    if pg.local_development_dsn() is None:
        return False

    def as_app(cursor):
        return work(cursor)

    try:
        import psycopg
        with psycopg.connect(pg.local_development_dsn(), connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                return as_app(cursor)
    except Exception:
        return False


_DEFINER_SELECT_REQUIRED = (
    "Local duty close needs migration 008 on this database "
    "(smt_definer SELECT on driver_branches, company_drivers, company_vehicles)."
)


def _definer_assignment_selects_ready(cur):
    """True when smt_definer can re-enter assignment_guard on booking close."""
    cur.execute(
        """
        SELECT has_table_privilege('smt_definer', 'driver_branches', 'SELECT')
           AND has_table_privilege('smt_definer', 'company_drivers', 'SELECT')
           AND has_table_privilege('smt_definer', 'company_vehicles', 'SELECT')
           AND has_column_privilege('smt_definer', 'vehicles', 'id', 'SELECT')
           AND has_column_privilege('smt_definer', 'vehicles', 'branch_id', 'SELECT')
           AND has_column_privilege('smt_definer', 'vehicles', 'status', 'SELECT')
           AND has_column_privilege('smt_definer', 'vehicles', 'status', 'UPDATE')
        """
    )
    return bool(cur.fetchone()[0])


def _triggers_or_unavailable(cur):
    if assignment_triggers_ready(cur):
        return None
    return {"ok": False, "error": "unavailable", "message": _TRIGGER_REQUIRED}


def _definer_close_or_unavailable(cur):
    blocked = _triggers_or_unavailable(cur)
    if blocked:
        return blocked
    if _definer_assignment_selects_ready(cur):
        return None
    return {"ok": False, "error": "unavailable", "message": _DEFINER_SELECT_REQUIRED}


def _duty_error(exc):
    mapped = pg._booking_database_error(exc)
    diag = getattr(exc, "diag", None)
    constraint = getattr(diag, "constraint_name", None) or ""
    primary = getattr(diag, "message_primary", None) or ""
    if constraint == "one_open_assignment_per_booking":
        return {
            "ok": False,
            "error": "conflict",
            "message": "This booking already has an open assignment.",
        }
    if constraint in ("one_active_session_per_assignment", "one_active_session_per_driver"):
        return {
            "ok": False,
            "error": "conflict",
            "message": "This trip is already started.",
        }
    if primary.startswith("Invalid assignment transition"):
        return {
            "ok": False,
            "error": "conflict",
            "message": "That assignment status change is not allowed.",
        }
    if primary.startswith("Invalid booking transition"):
        return {
            "ok": False,
            "error": "conflict",
            "message": "That booking status change is not allowed.",
        }
    if primary.startswith("A trip starts only after"):
        return {
            "ok": False,
            "error": "conflict",
            "message": "The driver must accept before the trip can start.",
        }
    if primary.startswith("This driver already has an active trip"):
        return {
            "ok": False,
            "error": "conflict",
            "message": "That driver already has an active trip.",
        }
    if primary.startswith("Driver is not enabled") or primary.startswith(
        "Driver is not authorised"
    ):
        return {
            "ok": False,
            "error": "invalid",
            "message": "That driver is not available for this booking.",
        }
    if primary.startswith("Vehicle is"):
        return {
            "ok": False,
            "error": "invalid",
            "message": "That vehicle is not available for this booking.",
        }
    if mapped.get("message") != "Booking could not be saved.":
        return mapped
    return {"ok": False, "error": "invalid", "message": "Duty change could not be saved."}


def _assignment_shape(row):
    (
        assignment_id, booking_id, driver_id, vehicle_id, assigned_by, status,
        notes, rejection_reason, whatsapp_status, assigned_at, decided_at,
        decided_by, driver_name, driver_phone, driver_whatsapp, vehicle_registration,
    ) = row
    return {
        "id": assignment_id,
        "booking_id": booking_id,
        "driver_id": driver_id,
        "vehicle_id": vehicle_id,
        "assigned_by": assigned_by,
        "status": status,
        "notes": notes,
        "rejection_reason": rejection_reason,
        "whatsapp_status": whatsapp_status,
        "assigned_at": pg._booking_value(assigned_at),
        "decided_at": pg._booking_value(decided_at),
        "decided_by": decided_by,
        "driver_name": driver_name,
        "driver_phone": driver_phone,
        "driver_whatsapp": driver_whatsapp,
        "vehicle_registration": vehicle_registration,
    }


_ASSIGNMENT_SELECT = """
    SELECT a.id::text, a.booking_id::text, a.driver_id::text, a.vehicle_id::text,
           a.assigned_by::text, a.status, a.notes, a.rejection_reason,
           a.whatsapp_status, a.assigned_at, a.decided_at, a.decided_by::text,
           d.display_name, d.phone, d.whatsapp_number, v.registration_number
    FROM booking_assignments a
    JOIN drivers d ON d.id = a.driver_id
    LEFT JOIN vehicles v ON v.id = a.vehicle_id
"""


def _select_assignment(cur, assignment_id):
    cur.execute(_ASSIGNMENT_SELECT + " WHERE a.id = %s::uuid", (assignment_id,))
    row = cur.fetchone()
    return _assignment_shape(row) if row else None


def _select_open_assignment(cur, booking_id):
    cur.execute(
        _ASSIGNMENT_SELECT
        + " WHERE a.booking_id = %s::uuid AND a.status = ANY(%s)"
        + " ORDER BY a.assigned_at DESC, a.id DESC LIMIT 1",
        (booking_id, list(_OPEN_STATUSES)),
    )
    row = cur.fetchone()
    return _assignment_shape(row) if row else None


def _load_booking_for_update(cur, booking_id):
    cur.execute(
        """
        SELECT id::text, status, origin, branch_id::text, company_id::text,
               source_booking_id, trip_date, pickup_time, duty_type, cab_type,
               planned_start
        FROM bookings
        WHERE id = %s::uuid
        FOR UPDATE
        """,
        (booking_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "status": row[1],
        "origin": row[2],
        "branch_id": row[3],
        "company_id": row[4],
        "source_booking_id": row[5],
        "trip_date": pg._booking_value(row[6]),
        "pickup_time": pg._booking_value(row[7]),
        "duty_type": row[8],
        "cab_type": row[9],
        "planned_start": row[10],
    }


def _driver_eligible(cur, driver_id, branch_id, company_id):
    cur.execute(
        """
        SELECT d.id::text, d.display_name, d.phone, d.whatsapp_number,
               d.active, d.verification_status
        FROM drivers d
        WHERE d.id = %s::uuid
        FOR UPDATE
        """,
        (driver_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None, "Driver was not found."
    driver = {
        "id": row[0],
        "display_name": row[1],
        "phone": row[2],
        "whatsapp_number": row[3],
        "active": bool(row[4]),
        "verification_status": row[5],
    }
    if driver["verification_status"] != "verified":
        return None, "Only a verified driver can be assigned."
    if not driver["active"]:
        return None, "Only an active driver can be assigned."
    cur.execute(
        """
        SELECT 1 FROM driver_branches
        WHERE driver_id = %s::uuid AND branch_id = %s::uuid
        """,
        (driver_id, branch_id),
    )
    if cur.fetchone() is None:
        return None, "That driver is not enabled for this branch."
    if company_id is not None:
        cur.execute(
            """
            SELECT 1 FROM company_drivers
            WHERE driver_id = %s::uuid AND company_id = %s::uuid
            """,
            (driver_id, company_id),
        )
        if cur.fetchone() is None:
            return None, "That driver is not authorised for this company."
    return driver, None


def _vehicle_eligible(cur, vehicle_id, branch_id, company_id):
    if vehicle_id is None:
        return None, None
    cur.execute(
        """
        SELECT id::text, branch_id::text, status, registration_number
        FROM vehicles
        WHERE id = %s::uuid
        FOR UPDATE
        """,
        (vehicle_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None, "Vehicle was not found."
    if row[2] != "active":
        return None, "Only an active vehicle can be assigned."
    if row[1] != branch_id:
        return None, "That vehicle is not available in this branch."
    if company_id is not None:
        cur.execute(
            """
            SELECT 1 FROM company_vehicles
            WHERE vehicle_id = %s::uuid AND company_id = %s::uuid
            """,
            (vehicle_id, company_id),
        )
        if cur.fetchone() is None:
            return None, "That vehicle is not authorised for this company."
    return {
        "id": row[0],
        "branch_id": row[1],
        "status": row[2],
        "registration_number": row[3],
    }, None


def _notify_assign(booking, driver, assignment_id, send_message, reassigned=False):
    phone = driver.get("whatsapp_number") or driver.get("phone")
    return {
        "kind": "reassign" if reassigned else "assign",
        "send_message": bool(send_message),
        "assignment_id": assignment_id,
        "booking_id": booking["id"],
        "branch_id": booking["branch_id"],
        "company_id": booking.get("company_id"),
        "phone": phone,
        "driver_name": driver.get("display_name") or "",
        "body": _assign_body(booking, reassigned=reassigned),
    }


def _notify_release(booking, driver, assignment_id, send_message, reason):
    phone = (driver or {}).get("whatsapp_number") or (driver or {}).get("phone")
    return {
        "kind": "release",
        "reason": reason,
        "send_message": bool(send_message),
        "assignment_id": assignment_id,
        "booking_id": booking["id"],
        "branch_id": booking["branch_id"],
        "company_id": booking.get("company_id"),
        "phone": phone,
        "driver_name": (driver or {}).get("display_name") or "",
        "body": _release_body(booking, reason),
    }


def _parse_send_message(payload):
    if not isinstance(payload, dict):
        return True
    if "send_message" not in payload:
        return True
    value = payload.get("send_message")
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("0", "false", "no"):
        return False
    return True


def assign_booking(user_id, booking_id, payload):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Assignment details are not valid."}
    driver_id = pg._parse_uuid(payload.get("driver_id"))
    if driver_id is None:
        return {"ok": False, "error": "invalid", "message": "Driver is not valid."}
    vehicle_raw = payload.get("vehicle_id")
    if vehicle_raw in (None, ""):
        vehicle_id = None
    else:
        vehicle_id = pg._parse_uuid(vehicle_raw)
        if vehicle_id is None:
            return {"ok": False, "error": "invalid", "message": "Vehicle is not valid."}
    notes = pg._clean_text(payload.get("notes")) if "notes" in payload else None
    if notes is False:
        return {"ok": False, "error": "invalid", "message": "Assignment details are not valid."}
    send_message = _parse_send_message(payload)

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            booking = _load_booking_for_update(cur, booking_id)
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            if booking["origin"] not in _ASSIGNABLE_ORIGINS:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "This booking origin cannot be assigned here.",
                }
            if booking["status"] != "unassigned":
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an unassigned booking can be assigned.",
                }
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            driver, error = _driver_eligible(
                cur, driver_id, booking["branch_id"], booking["company_id"]
            )
            if error:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "invalid", "message": error}
            vehicle, error = _vehicle_eligible(
                cur, vehicle_id, booking["branch_id"], booking["company_id"]
            )
            if error:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "invalid", "message": error}
            assignment_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO booking_assignments (
                    id, booking_id, driver_id, vehicle_id, assigned_by, status, notes
                )
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'assigned', %s)
                """,
                (
                    assignment_id,
                    booking_id,
                    driver_id,
                    vehicle_id,
                    user_id,
                    notes,
                ),
            )
            assignment = _select_assignment(cur, assignment_id)
            booking_out = pg._select_operation_booking(cur, booking_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        return {
            "ok": True,
            "booking": booking_out,
            "assignment": assignment,
            "notify": _notify_assign(
                booking_out or booking, driver, assignment_id, send_message
            ),
        }

    return pg._actor_work(user_id, work)


def reassign_booking(user_id, booking_id, payload):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Assignment details are not valid."}
    driver_id = pg._parse_uuid(payload.get("driver_id"))
    if driver_id is None:
        return {"ok": False, "error": "invalid", "message": "Driver is not valid."}
    vehicle_raw = payload.get("vehicle_id")
    if vehicle_raw in (None, ""):
        vehicle_id = None
    else:
        vehicle_id = pg._parse_uuid(vehicle_raw)
        if vehicle_id is None:
            return {"ok": False, "error": "invalid", "message": "Vehicle is not valid."}
    notes = pg._clean_text(payload.get("notes")) if "notes" in payload else None
    if notes is False:
        return {"ok": False, "error": "invalid", "message": "Assignment details are not valid."}
    send_message = _parse_send_message(payload)

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            booking = _load_booking_for_update(cur, booking_id)
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            if booking["origin"] not in _ASSIGNABLE_ORIGINS:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "This booking origin cannot be reassigned here.",
                }
            if booking["status"] not in ("assigned", "accepted"):
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an assigned or accepted booking can be reassigned.",
                }
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            previous = _select_open_assignment(cur, booking_id)
            if previous is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "This booking has no open assignment to replace.",
                }
            if previous["driver_id"] == driver_id:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "That driver is already assigned to this booking.",
                }
            driver, error = _driver_eligible(
                cur, driver_id, booking["branch_id"], booking["company_id"]
            )
            if error:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "invalid", "message": error}
            vehicle, error = _vehicle_eligible(
                cur, vehicle_id, booking["branch_id"], booking["company_id"]
            )
            if error:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "invalid", "message": error}
            cur.execute(
                """
                UPDATE booking_assignments
                SET status = 'superseded',
                    rejection_reason = 'Reassigned to another driver',
                    decided_at = now(),
                    decided_by = %s::uuid
                WHERE id = %s::uuid AND status = ANY(%s)
                """,
                (user_id, previous["id"], list(_OPEN_STATUSES)),
            )
            previous_after = _select_assignment(cur, previous["id"])
            assignment_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO booking_assignments (
                    id, booking_id, driver_id, vehicle_id, assigned_by, status, notes
                )
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'assigned', %s)
                """,
                (
                    assignment_id,
                    booking_id,
                    driver_id,
                    vehicle_id,
                    user_id,
                    notes,
                ),
            )
            assignment = _select_assignment(cur, assignment_id)
            booking_out = pg._select_operation_booking(cur, booking_id)
            previous_driver = {
                "display_name": previous.get("driver_name"),
                "phone": previous.get("driver_phone"),
                "whatsapp_number": previous.get("driver_whatsapp"),
            }
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        return {
            "ok": True,
            "booking": booking_out,
            "assignment": assignment,
            "previous_assignment": previous_after or previous,
            "notify_list": [
                _notify_release(
                    booking_out or booking,
                    previous_driver,
                    previous["id"],
                    send_message,
                    "reassigned",
                ),
                _notify_assign(
                    booking_out or booking,
                    driver,
                    assignment_id,
                    send_message,
                    reassigned=True,
                ),
            ],
        }

    return pg._actor_work(user_id, work)


def unassign_booking(user_id, booking_id, payload=None):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}
    payload = payload if isinstance(payload, dict) else {}
    reason = pg._clean_text(payload.get("reason")) if "reason" in payload else None
    if reason is False:
        return {"ok": False, "error": "invalid", "message": "Unassign details are not valid."}
    if reason is None:
        reason = "Unassigned by supervisor"
    send_message = _parse_send_message(payload)

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            booking = _load_booking_for_update(cur, booking_id)
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            if booking["status"] not in ("assigned", "accepted"):
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an assigned or accepted booking can be unassigned.",
                }
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            previous = _select_open_assignment(cur, booking_id)
            if previous is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "This booking has no open assignment.",
                }
            cur.execute(
                """
                UPDATE booking_assignments
                SET status = 'withdrawn',
                    rejection_reason = %s,
                    decided_at = now(),
                    decided_by = %s::uuid
                WHERE id = %s::uuid AND status = ANY(%s)
                """,
                (reason, user_id, previous["id"], list(_OPEN_STATUSES)),
            )
            assignment = _select_assignment(cur, previous["id"])
            booking_out = pg._select_operation_booking(cur, booking_id)
            previous_driver = {
                "display_name": previous.get("driver_name"),
                "phone": previous.get("driver_phone"),
                "whatsapp_number": previous.get("driver_whatsapp"),
            }
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        return {
            "ok": True,
            "booking": booking_out,
            "assignment": assignment,
            "notify": _notify_release(
                booking_out or booking,
                previous_driver,
                previous["id"],
                send_message,
                "removed",
            ),
        }

    return pg._actor_work(user_id, work)


def cancel_booking(user_id, booking_id, payload=None):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}
    payload = payload if isinstance(payload, dict) else {}
    send_message = _parse_send_message(payload)

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            booking = _load_booking_for_update(cur, booking_id)
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            if booking["status"] in ("completed", "cancelled"):
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "That booking is already finished.",
                }
            if booking["status"] not in ("unassigned", "assigned", "accepted", "started"):
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "That booking cannot be cancelled.",
                }
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            # Started cancel still updates the open assignment as smt_definer.
            if booking["status"] == "started":
                missing = _definer_close_or_unavailable(cur)
                if missing:
                    cur.execute("RELEASE SAVEPOINT duty_write")
                    return missing
            previous = _select_open_assignment(cur, booking_id)
            # For assigned/accepted bookings, close the open assignment as the
            # caller first so the cancel path does not rely on smt_definer
            # re-entering assignment_guard. Started bookings keep the open
            # assignment until bookings_write_event_and_close runs.
            if previous is not None and booking["status"] in ("assigned", "accepted"):
                cur.execute(
                    """
                    UPDATE booking_assignments
                    SET status = 'superseded',
                        rejection_reason = 'Booking cancelled',
                        decided_at = now(),
                        decided_by = %s::uuid
                    WHERE id = %s::uuid AND status = ANY(%s)
                    """,
                    (user_id, previous["id"], list(_OPEN_STATUSES)),
                )
            cur.execute(
                """
                UPDATE bookings
                SET status = 'cancelled'
                WHERE id = %s::uuid AND status = ANY(%s)
                """,
                (booking_id, ["unassigned", "assigned", "accepted", "started"]),
            )
            booking_out = pg._select_operation_booking(cur, booking_id)
            notify = None
            if previous is not None:
                previous_driver = {
                    "display_name": previous.get("driver_name"),
                    "phone": previous.get("driver_phone"),
                    "whatsapp_number": previous.get("driver_whatsapp"),
                }
                notify = _notify_release(
                    booking_out or booking,
                    previous_driver,
                    previous["id"],
                    send_message,
                    "cancelled",
                )
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        result = {"ok": True, "booking": booking_out}
        if notify is not None:
            result["notify"] = notify
        return result

    return pg._actor_work(user_id, work)


def accept_assignment(user_id, assignment_id):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Assignment was not found."}

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            assignment = _select_assignment(cur, assignment_id)
            if assignment is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Assignment was not found."}
            booking = _load_booking_for_update(cur, assignment["booking_id"])
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if assignment["status"] != "assigned":
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an assigned duty can be accepted.",
                }
            cur.execute(
                """
                UPDATE booking_assignments
                SET status = 'accepted',
                    decided_at = now(),
                    decided_by = %s::uuid
                WHERE id = %s::uuid AND status = 'assigned'
                """,
                (user_id, assignment_id),
            )
            assignment = _select_assignment(cur, assignment_id)
            booking_out = pg._select_operation_booking(cur, booking["id"])
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        return {"ok": True, "booking": booking_out, "assignment": assignment}

    return pg._actor_work(user_id, work)


def reject_assignment(user_id, assignment_id, payload):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Assignment was not found."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Rejection details are not valid."}
    reason = pg._clean_text(payload.get("reason"))
    if not reason:
        return {"ok": False, "error": "invalid", "message": "A rejection reason is required."}

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            assignment = _select_assignment(cur, assignment_id)
            if assignment is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Assignment was not found."}
            booking = _load_booking_for_update(cur, assignment["booking_id"])
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if assignment["status"] != "assigned":
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an assigned duty can be rejected.",
                }
            cur.execute(
                """
                UPDATE booking_assignments
                SET status = 'rejected',
                    rejection_reason = %s,
                    decided_at = now(),
                    decided_by = %s::uuid
                WHERE id = %s::uuid AND status = 'assigned'
                """,
                (reason, user_id, assignment_id),
            )
            assignment = _select_assignment(cur, assignment_id)
            booking_out = pg._select_operation_booking(cur, booking["id"])
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        return {"ok": True, "booking": booking_out, "assignment": assignment}

    return pg._actor_work(user_id, work)


def start_trip(user_id, booking_id):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            booking = _load_booking_for_update(cur, booking_id)
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if booking["status"] != "accepted":
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an accepted booking can be started.",
                }
            assignment = _select_open_assignment(cur, booking_id)
            if assignment is None or assignment["status"] != "accepted":
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "An accepted assignment is required to start the trip.",
                }
            cur.execute(
                """
                SELECT id::text FROM trip_sessions
                WHERE assignment_id = %s::uuid AND status = 'active'
                FOR UPDATE
                """,
                (assignment["id"],),
            )
            if cur.fetchone() is not None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "This trip is already started.",
                }
            session_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO trip_sessions (
                    id, assignment_id, driver_id, session_origin, status, started_at, started_by
                )
                VALUES (%s::uuid, %s::uuid, %s::uuid, 'duty', 'active', now(), %s::uuid)
                """,
                (session_id, assignment["id"], assignment["driver_id"], user_id),
            )
            booking_out = pg._select_operation_booking(cur, booking_id)
            cur.execute(
                """
                SELECT id::text, assignment_id::text, driver_id::text, status,
                       started_at, ended_at
                FROM trip_sessions WHERE id = %s::uuid
                """,
                (session_id,),
            )
            session_row = cur.fetchone()
            session = {
                "id": session_row[0],
                "assignment_id": session_row[1],
                "driver_id": session_row[2],
                "status": session_row[3],
                "started_at": pg._booking_value(session_row[4]),
                "ended_at": pg._booking_value(session_row[5]),
            }
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        return {
            "ok": True,
            "booking": booking_out,
            "assignment": assignment,
            "session": session,
        }

    return pg._actor_work(user_id, work)


def complete_trip(user_id, booking_id):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            booking = _load_booking_for_update(cur, booking_id)
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if booking["status"] != "started":
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only a started trip can be completed.",
                }
            assignment = _select_open_assignment(cur, booking_id)
            if assignment is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "An open assignment is required to complete the trip.",
                }
            cur.execute(
                """
                SELECT id::text
                FROM trip_sessions
                WHERE assignment_id = %s::uuid AND status = 'active'
                FOR UPDATE
                """,
                (assignment["id"],),
            )
            session = cur.fetchone()
            if session is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "An active trip session is required to complete the trip.",
                }
            # Closing the session updates the assignment as smt_definer; that
            # path needs the 008 SELECT grants before assignment_guard can run.
            if not _definer_assignment_selects_ready(cur):
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "unavailable",
                    "message": _DEFINER_SELECT_REQUIRED,
                }
            cur.execute(
                """
                UPDATE trip_sessions
                SET status = 'closed', ended_at = now()
                WHERE id = %s::uuid AND status = 'active'
                """,
                (session[0],),
            )
            booking_out = pg._select_operation_booking(cur, booking_id)
            assignment = _select_assignment(cur, assignment["id"])
            cur.execute(
                """
                SELECT id::text, assignment_id::text, driver_id::text, status,
                       started_at, ended_at
                FROM trip_sessions WHERE id = %s::uuid
                """,
                (session[0],),
            )
            session_row = cur.fetchone()
            session_out = {
                "id": session_row[0],
                "assignment_id": session_row[1],
                "driver_id": session_row[2],
                "status": session_row[3],
                "started_at": pg._booking_value(session_row[4]),
                "ended_at": pg._booking_value(session_row[5]),
            }
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        return {
            "ok": True,
            "booking": booking_out,
            "assignment": assignment,
            "session": session_out,
        }

    return pg._actor_work(user_id, work)


def set_assignment_vehicle(user_id, assignment_id, payload):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Assignment was not found."}
    if not isinstance(payload, dict) or "vehicle_id" not in payload:
        return {"ok": False, "error": "invalid", "message": "Vehicle details are not valid."}
    vehicle_raw = payload.get("vehicle_id")
    if vehicle_raw in (None, ""):
        vehicle_id = None
    else:
        vehicle_id = pg._parse_uuid(vehicle_raw)
        if vehicle_id is None:
            return {"ok": False, "error": "invalid", "message": "Vehicle is not valid."}

    def work(cur):
        import psycopg

        blocked = _triggers_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT duty_write")
        try:
            assignment = _select_assignment(cur, assignment_id)
            if assignment is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Assignment was not found."}
            if assignment["status"] not in _OPEN_STATUSES:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an open assignment can change vehicle.",
                }
            booking = _load_booking_for_update(cur, assignment["booking_id"])
            if booking is None:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            cur.execute("SELECT staff_can_branch(%s::uuid)", (booking["branch_id"],))
            if not cur.fetchone()[0]:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            vehicle, error = _vehicle_eligible(
                cur, vehicle_id, booking["branch_id"], booking["company_id"]
            )
            if error:
                cur.execute("RELEASE SAVEPOINT duty_write")
                return {"ok": False, "error": "invalid", "message": error}
            cur.execute(
                """
                UPDATE booking_assignments
                SET vehicle_id = %s::uuid
                WHERE id = %s::uuid AND status = ANY(%s)
                """,
                (vehicle_id, assignment_id, list(_OPEN_STATUSES)),
            )
            assignment = _select_assignment(cur, assignment_id)
            booking_out = pg._select_operation_booking(cur, booking["id"])
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT duty_write")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT duty_write")
        return {"ok": True, "booking": booking_out, "assignment": assignment}

    return pg._actor_work(user_id, work)


def get_booking_assignment(user_id, booking_id):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}

    def work(cur):
        booking = pg._select_operation_booking(cur, booking_id)
        if booking is None:
            return {"ok": False, "error": "not_found", "message": "Booking was not found."}
        assignment = _select_open_assignment(cur, booking_id)
        if assignment is None:
            return {"ok": False, "error": "not_found", "message": "No open assignment."}
        return {"ok": True, "booking": booking, "assignment": assignment}

    return pg._actor_work(user_id, work)


def list_booking_assignments(user_id, booking_id):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}

    def work(cur):
        booking = pg._select_operation_booking(cur, booking_id)
        if booking is None:
            return {"ok": False, "error": "not_found", "message": "Booking was not found."}
        cur.execute(
            _ASSIGNMENT_SELECT
            + " WHERE a.booking_id = %s::uuid ORDER BY a.assigned_at DESC, a.id DESC",
            (booking_id,),
        )
        return {
            "ok": True,
            "booking": booking,
            "assignments": [_assignment_shape(row) for row in cur.fetchall()],
        }

    return pg._actor_work(user_id, work)


def list_assignment_events(user_id, assignment_id):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Assignment was not found."}

    def work(cur):
        assignment = _select_assignment(cur, assignment_id)
        if assignment is None:
            return {"ok": False, "error": "not_found", "message": "Assignment was not found."}
        cur.execute(
            """
            SELECT id::text, old_status, new_status, actor_user_id::text, reason, created_at
            FROM assignment_events
            WHERE assignment_id = %s::uuid
            ORDER BY created_at, id
            """,
            (assignment_id,),
        )
        events = [
            {
                "id": row[0],
                "old_status": row[1],
                "new_status": row[2],
                "actor_user_id": row[3],
                "reason": row[4],
                "created_at": pg._booking_value(row[5]),
            }
            for row in cur.fetchall()
        ]
        return {"ok": True, "assignment": assignment, "events": events}

    return pg._actor_work(user_id, work)


def get_trip_status(user_id, booking_id):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}

    def work(cur):
        booking = pg._select_operation_booking(cur, booking_id)
        if booking is None:
            return {"ok": False, "error": "not_found", "message": "Booking was not found."}
        assignment = _select_open_assignment(cur, booking_id)
        session = None
        if assignment is not None:
            cur.execute(
                """
                SELECT id::text, assignment_id::text, driver_id::text, status,
                       started_at, ended_at
                FROM trip_sessions
                WHERE assignment_id = %s::uuid
                ORDER BY
                    CASE status WHEN 'active' THEN 0 ELSE 1 END,
                    started_at DESC
                LIMIT 1
                """,
                (assignment["id"],),
            )
            row = cur.fetchone()
            if row:
                session = {
                    "id": row[0],
                    "assignment_id": row[1],
                    "driver_id": row[2],
                    "status": row[3],
                    "started_at": pg._booking_value(row[4]),
                    "ended_at": pg._booking_value(row[5]),
                }
        cur.execute(
            """
            SELECT id::text, old_status, new_status, actor_user_id::text, created_at
            FROM booking_events
            WHERE booking_id = %s::uuid
            ORDER BY created_at, id
            """,
            (booking_id,),
        )
        events = [
            {
                "id": row[0],
                "old_status": row[1],
                "new_status": row[2],
                "actor_user_id": row[3],
                "created_at": pg._booking_value(row[4]),
            }
            for row in cur.fetchall()
        ]
        return {
            "ok": True,
            "booking": booking,
            "assignment": assignment,
            "session": session,
            "events": events,
        }

    return pg._actor_work(user_id, work)


def resend_assignment_message(user_id, assignment_id):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Assignment was not found."}

    def work(cur):
        assignment = _select_assignment(cur, assignment_id)
        if assignment is None:
            return {"ok": False, "error": "not_found", "message": "Assignment was not found."}
        if assignment["status"] not in _OPEN_STATUSES:
            return {
                "ok": False,
                "error": "conflict",
                "message": "Only an open assignment can be resent.",
            }
        booking = pg._select_operation_booking(cur, assignment["booking_id"])
        if booking is None:
            return {"ok": False, "error": "not_found", "message": "Booking was not found."}
        driver = {
            "display_name": assignment.get("driver_name"),
            "phone": assignment.get("driver_phone"),
            "whatsapp_number": assignment.get("driver_whatsapp"),
        }
        return {
            "ok": True,
            "booking": booking,
            "assignment": assignment,
            "notify": _notify_assign(booking, driver, assignment_id, True),
        }

    return pg._actor_work(user_id, work)


def deliver_operation_whatsapp(user_id, notify):
    """Send after the duty transaction has already committed."""
    if not notify or not notify.get("send_message"):
        return {
            "sent": False,
            "send_status": "skipped",
            "wa_link": _wa_link(notify.get("phone") if notify else None, (notify or {}).get("body")),
            "error": "",
        }
    phone = notify.get("phone")
    body = notify.get("body") or ""
    wa_link = _wa_link(phone, body)
    if not phone:
        send_status = "ready"
        sent = False
        error = "No WhatsApp number"
    else:
        sent, info = _bridge_send(phone, body)
        send_status = "sent" if sent else "ready"
        error = "" if sent else (info.get("error") or "WhatsApp bridge did not send")

    def work(cur):
        import psycopg

        cur.execute("SAVEPOINT duty_message")
        try:
            cur.execute(
                """
                INSERT INTO messages (
                    branch_id, company_id, booking_id, assignment_id,
                    channel, direction, phone, body, send_status
                )
                VALUES (
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                    'whatsapp', 'out', %s, %s, %s
                )
                RETURNING id::text
                """,
                (
                    notify.get("branch_id"),
                    notify.get("company_id"),
                    notify.get("booking_id"),
                    notify.get("assignment_id"),
                    phone,
                    body,
                    send_status,
                ),
            )
            message_id = cur.fetchone()[0]
            if notify.get("assignment_id"):
                cur.execute(
                    """
                    UPDATE booking_assignments
                    SET whatsapp_status = %s
                    WHERE id = %s::uuid
                    """,
                    (send_status, notify["assignment_id"]),
                )
        except psycopg.Error:
            cur.execute("ROLLBACK TO SAVEPOINT duty_message")
            return {
                "sent": sent,
                "send_status": send_status,
                "wa_link": wa_link,
                "error": error or "Message could not be recorded.",
                "recorded": False,
            }
        cur.execute("RELEASE SAVEPOINT duty_message")
        return {
            "sent": sent,
            "send_status": send_status,
            "wa_link": wa_link,
            "error": error,
            "message_id": message_id,
            "recorded": True,
            "driver_name": notify.get("driver_name") or "",
            "phone_number": phone or "",
        }

    recorded = pg._actor_work(user_id, work)
    if recorded is None:
        return {
            "sent": sent,
            "send_status": send_status,
            "wa_link": wa_link,
            "error": error or "Message could not be recorded.",
            "recorded": False,
        }
    return recorded
