"""Driver-facing PostgreSQL APIs for the Android application.

Server resolves the authenticated driver from the session token. Request bodies
never supply a trusted driver_id. Uses smt_driver RLS via authorized_transaction.
"""
from __future__ import annotations

import uuid
from datetime import date

import driver_auth
import dev_postgres as pg


def _driver_work(user_id, work):
    done = pg.authorized_transaction(user_id, work)
    if not done or done.get("role") != "driver":
        return None
    return done.get("result")


def _owner_work(user_id, work):
    done = pg.authorized_transaction(user_id, work)
    if not done or done.get("role") != "owner":
        return None
    return done.get("result")


def _duty_error(exc):
    message = getattr(getattr(exc, "diag", None), "message_primary", None) or str(exc)
    lowered = (message or "").lower()
    if "42501" in str(getattr(exc, "sqlstate", "") or "") or "permission" in lowered:
        return {"ok": False, "error": "forbidden", "message": "You cannot change that duty."}
    if "conflict" in lowered or "unique" in lowered or "one_open" in lowered:
        return {"ok": False, "error": "conflict", "message": "That duty changed. Refresh and try again."}
    return {"ok": False, "error": "invalid", "message": "The request could not be completed."}


def _iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_km(value, label):
    if value is None or value == "":
        return None, "%s is required." % label
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, "%s must be a number." % label
    if number < 0:
        return None, "%s cannot be negative." % label
    return number, None


def _today():
    return date.today().isoformat()


def authenticate_driver(phone, password):
    """Resolve phone+password to a driver session. Runs as owner for hash read."""
    phone = driver_auth.normalize_phone(phone)
    if not phone:
        return {"ok": False, "error": "invalid", "message": "Enter a valid 10-digit phone number."}
    if not isinstance(password, str) or len(password) < 8:
        return {"ok": False, "error": "invalid", "message": "Password must be at least 8 characters."}
    owner_id = pg._bootstrap_owner_id()
    if owner_id is None:
        return None

    box = {"row": None}

    def work(cur):
        cur.execute(
            """
            SELECT u.id::text, u.password_hash, u.status, u.full_name,
                   d.id::text, d.display_name, d.active, d.verification_status
            FROM users u
            JOIN drivers d ON d.user_id = u.id
            WHERE u.role = 'driver'
              AND regexp_replace(COALESCE(u.phone, ''), '\\D', '', 'g')
                  IN (%s, '91' || %s)
            """,
            (phone, phone),
        )
        rows = cur.fetchall()
        if len(rows) != 1:
            box["row"] = None
            return True
        box["row"] = rows[0]
        return True

    # work returns True on success; None callback result must not mean portal failure.
    done = _owner_work(owner_id, work)
    if done is None:
        return None
    row = box["row"]
    if row is None:
        return {"ok": False, "error": "unauthorized", "message": "Invalid phone or password."}
    user_id, password_hash, status, full_name, driver_id, display_name, active, verification = row
    if status != "active":
        return {"ok": False, "error": "disabled", "message": "This account is disabled."}
    if not active:
        return {"ok": False, "error": "disabled", "message": "This driver profile is inactive."}
    if not driver_auth.verify_password(password_hash, password):
        return {"ok": False, "error": "unauthorized", "message": "Invalid phone or password."}
    token = driver_auth.issue_token(user_id, driver_id)
    if not token:
        return None
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user_id,
            "full_name": full_name,
            "role": "driver",
        },
        "driver": {
            "id": driver_id,
            "display_name": display_name,
            "active": active,
            "verification_status": verification,
        },
    }


def provision_driver_login(owner_user_id, driver_id, password):
    """Owner-only: create or update the linked users row for a driver phone login."""
    driver_id = pg._parse_uuid(driver_id)
    if driver_id is None:
        return {"ok": False, "error": "not_found", "message": "Driver was not found."}
    if not isinstance(password, str) or len(password) < 8:
        return {"ok": False, "error": "invalid", "message": "Password must be at least 8 characters."}
    password_hash = driver_auth.hash_password(password)

    def work(cur):
        cur.execute(
            """
            SELECT id::text, user_id::text, display_name, phone, active
            FROM drivers WHERE id = %s::uuid
            """,
            (driver_id,),
        )
        found = cur.fetchone()
        if found is None:
            return {"ok": False, "error": "not_found", "message": "Driver was not found."}
        _, linked_user_id, display_name, phone, active = found
        phone_norm = driver_auth.normalize_phone(phone or "")
        if not phone_norm:
            return {
                "ok": False,
                "error": "invalid",
                "message": "Driver needs a valid 10-digit phone before a login can be created.",
            }
        if not active:
            return {
                "ok": False,
                "error": "invalid",
                "message": "Activate the driver before creating a login.",
            }
        if linked_user_id:
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    phone = %s,
                    status = 'active',
                    role = 'driver',
                    full_name = COALESCE(NULLIF(btrim(full_name), ''), %s)
                WHERE id = %s::uuid AND role = 'driver'
                RETURNING id::text
                """,
                (password_hash, phone_norm, display_name, linked_user_id),
            )
            updated = cur.fetchone()
            if updated is None:
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Linked user is not a driver account.",
                }
            return {"ok": True, "user_id": updated[0], "created": False}
        cur.execute(
            """
            INSERT INTO users (role, full_name, phone, password_hash, status)
            VALUES ('driver', %s, %s, %s, 'active')
            RETURNING id::text
            """,
            (display_name, phone_norm, password_hash),
        )
        user_id = cur.fetchone()[0]
        cur.execute(
            "UPDATE drivers SET user_id = %s::uuid WHERE id = %s::uuid AND user_id IS NULL",
            (user_id, driver_id),
        )
        if cur.rowcount != 1:
            return {
                "ok": False,
                "error": "conflict",
                "message": "Driver login could not be linked.",
            }
        return {"ok": True, "user_id": user_id, "created": True}

    return _owner_work(owner_user_id, work)


def session_profile(user_id):
    def work(cur):
        cur.execute("SELECT current_driver_id()::text")
        driver_id = cur.fetchone()[0]
        if not driver_id:
            return {"ok": False, "error": "forbidden", "message": "No driver profile is linked."}
        cur.execute(
            """
            SELECT d.id::text, d.display_name, d.phone, d.whatsapp_number, d.alternate_number,
                   d.home_area, d.license_number, d.license_expiry::text, d.active,
                   d.verification_status, u.full_name, u.status, u.phone
            FROM drivers d
            JOIN users u ON u.id = d.user_id
            WHERE d.id = %s::uuid
            """,
            (driver_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "Driver profile was not found."}
        cur.execute(
            """
            SELECT id::text, doc_type, doc_number, expiry_date::text, created_at
            FROM driver_documents
            WHERE driver_id = %s::uuid
            ORDER BY created_at, id
            """,
            (driver_id,),
        )
        documents = [
            {
                "id": r[0],
                "doc_type": r[1],
                "doc_number": r[2],
                "expiry_date": r[3],
                "created_at": _iso(r[4]),
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "driver": {
                "id": row[0],
                "display_name": row[1],
                "phone": row[2] or row[12],
                "whatsapp_number": row[3],
                "alternate_number": row[4],
                "home_area": row[5],
                "license_number": row[6],
                "license_expiry": row[7],
                "active": row[8],
                "verification_status": row[9],
                "full_name": row[10],
                "account_status": row[11],
                "photo_url": None,
                "documents": documents,
            },
        }

    return _driver_work(user_id, work)


def _duty_select_sql(extra_where=""):
    return """
        SELECT a.id::text, a.status, a.notes, a.rejection_reason, a.assigned_at, a.decided_at,
               b.id::text, b.source_booking_id, b.trip_date::text, b.pickup_time::text,
               b.planned_start, b.route_text, b.employee_name, b.source_mobile,
               b.duty_type, b.cab_type, b.status, b.remarks,
               c.name,
               v.id::text, v.registration_number, v.model, v.fuel_type, v.is_ev,
               ts.id::text, ts.status, ts.started_at, ts.ended_at,
               dr.start_km, dr.end_km, dr.total_km
        FROM booking_assignments a
        JOIN bookings b ON b.id = a.booking_id
        LEFT JOIN companies c ON c.id = b.company_id
        LEFT JOIN vehicles v ON v.id = a.vehicle_id
        LEFT JOIN LATERAL (
            SELECT s.id, s.status, s.started_at, s.ended_at
            FROM trip_sessions s
            WHERE s.assignment_id = a.id
            ORDER BY s.started_at DESC
            LIMIT 1
        ) ts ON true
        LEFT JOIN duty_readings dr ON dr.booking_id = b.id
        WHERE a.driver_id = current_driver_id()
        %s
        ORDER BY b.trip_date DESC NULLS LAST, a.assigned_at DESC
    """ % extra_where


def _shape_duty(row):
    return {
        "assignment_id": row[0],
        "assignment_status": row[1],
        "notes": row[2],
        "rejection_reason": row[3],
        "assigned_at": _iso(row[4]),
        "decided_at": _iso(row[5]),
        "booking_id": row[6],
        "booking_reference": row[7] or row[6],
        "trip_date": row[8],
        "pickup_time": row[9],
        "pickup_location": row[10],
        "route": row[11],
        "passenger_name": row[12],
        "passenger_phone": row[13],
        "duty_type": row[14],
        "cab_type": row[15],
        "booking_status": row[16],
        "remarks": row[17],
        "company_name": row[18],
        "vehicle": None
        if not row[19]
        else {
            "id": row[19],
            "registration_number": row[20],
            "model": row[21],
            "fuel_type": row[22],
            "is_ev": row[23],
        },
        "trip_session": None
        if not row[24]
        else {
            "id": row[24],
            "status": row[25],
            "started_at": _iso(row[26]),
            "ended_at": _iso(row[27]),
        },
        "readings": {
            "start_km": _num(row[28]),
            "end_km": _num(row[29]),
            "total_km": _num(row[30]),
        },
    }


def list_duties(user_id, filter_name=None):
    filter_name = (filter_name or "all").strip().lower()
    today = _today()
    clauses = {
        "today": "AND b.trip_date = %s::date AND a.status IN ('assigned','accepted','completed')",
        "upcoming": "AND b.trip_date > %s::date AND a.status IN ('assigned','accepted')",
        "pending": "AND a.status = 'assigned'",
        "active": "AND a.status = 'accepted' AND b.status IN ('accepted','started')",
        "completed": "AND (a.status = 'completed' OR b.status = 'completed')",
        "rejected": "AND a.status IN ('rejected','withdrawn','superseded')",
        "all": "",
    }
    if filter_name not in clauses:
        return {"ok": False, "error": "invalid", "message": "Unknown duty filter."}
    extra = clauses[filter_name]
    params = ()
    if "%s" in extra:
        params = (today,)

    def work(cur):
        cur.execute(_duty_select_sql(extra), params)
        duties = [_shape_duty(row) for row in cur.fetchall()]
        return {"ok": True, "duties": duties, "filter": filter_name, "live": True}

    return _driver_work(user_id, work)


def get_duty(user_id, assignment_id):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Duty was not found."}

    def work(cur):
        cur.execute(
            _duty_select_sql("AND a.id = %s::uuid"),
            (assignment_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "Duty was not found."}
        return {"ok": True, "duty": _shape_duty(row), "live": True}

    return _driver_work(user_id, work)


def dashboard(user_id):
    def work(cur):
        cur.execute("SELECT current_driver_id()::text")
        driver_id = cur.fetchone()[0]
        cur.execute(
            """
            SELECT d.display_name, d.active, d.verification_status, u.full_name
            FROM drivers d
            JOIN users u ON u.id = d.user_id
            WHERE d.id = %s::uuid
            """,
            (driver_id,),
        )
        driver_row = cur.fetchone()
        if driver_row is None:
            return {"ok": False, "error": "not_found", "message": "Driver profile was not found."}
        today = _today()

        def fetch(extra, params=()):
            cur.execute(_duty_select_sql(extra), params)
            return [_shape_duty(r) for r in cur.fetchall()]

        today_duties = fetch(
            "AND b.trip_date = %s::date AND a.status IN ('assigned','accepted','completed')",
            (today,),
        )
        pending = fetch("AND a.status = 'assigned'")
        upcoming = fetch(
            "AND b.trip_date > %s::date AND a.status IN ('assigned','accepted')",
            (today,),
        )
        active = fetch(
            "AND EXISTS ("
            " SELECT 1 FROM trip_sessions s"
            " WHERE s.assignment_id = a.id AND s.status = 'active'"
            "   AND s.driver_id = current_driver_id())"
        )
        cur.execute(
            """
            SELECT a.id::text, a.status, a.notes, a.rejection_reason, a.assigned_at, a.decided_at,
                   b.id::text, b.source_booking_id, b.trip_date::text, b.pickup_time::text,
                   b.planned_start, b.route_text, b.employee_name, b.source_mobile,
                   b.duty_type, b.cab_type, b.status, b.remarks,
                   c.name,
                   v.id::text, v.registration_number, v.model, v.fuel_type, v.is_ev,
                   ts.id::text, ts.status, ts.started_at, ts.ended_at,
                   dr.start_km, dr.end_km, dr.total_km
            FROM booking_assignments a
            JOIN bookings b ON b.id = a.booking_id
            LEFT JOIN companies c ON c.id = b.company_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id
            LEFT JOIN LATERAL (
                SELECT s.id, s.status, s.started_at, s.ended_at
                FROM trip_sessions s
                WHERE s.assignment_id = a.id
                ORDER BY s.started_at DESC
                LIMIT 1
            ) ts ON true
            LEFT JOIN duty_readings dr ON dr.booking_id = b.id
            WHERE a.driver_id = current_driver_id()
              AND (a.status = 'completed' OR b.status = 'completed')
            ORDER BY b.trip_date DESC NULLS LAST, a.assigned_at DESC
            LIMIT 10
            """
        )
        completed = [_shape_duty(r) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT id::text, kind, title, body, read_at, created_at, booking_id::text,
                   assignment_id::text
            FROM driver_notifications
            WHERE driver_id = current_driver_id()
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
        notifications = [
            {
                "id": r[0],
                "kind": r[1],
                "title": r[2],
                "body": r[3],
                "read_at": _iso(r[4]),
                "created_at": _iso(r[5]),
                "booking_id": r[6],
                "assignment_id": r[7],
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "live": True,
            "driver": {
                "id": driver_id,
                "display_name": driver_row[0],
                "full_name": driver_row[3],
                "active": driver_row[1],
                "verification_status": driver_row[2],
                "photo_url": None,
            },
            "today_duties": today_duties,
            "pending_responses": pending,
            "upcoming_duties": upcoming,
            "active_trip": active[0] if active else None,
            "completed_duties": completed,
            "notifications": notifications,
        }

    return _driver_work(user_id, work)


def accept_duty(user_id, assignment_id):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Duty was not found."}

    def work(cur):
        import psycopg

        cur.execute("SAVEPOINT driver_duty")
        try:
            cur.execute(
                """
                SELECT id::text, status, booking_id::text
                FROM booking_assignments
                WHERE id = %s::uuid AND driver_id = current_driver_id()
                FOR UPDATE
                """,
                (assignment_id,),
            )
            found = cur.fetchone()
            if found is None:
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {"ok": False, "error": "not_found", "message": "Duty was not found."}
            if found[1] == "accepted":
                cur.execute("RELEASE SAVEPOINT driver_duty")
                cur.execute(_duty_select_sql("AND a.id = %s::uuid"), (assignment_id,))
                row = cur.fetchone()
                return {
                    "ok": True,
                    "already": True,
                    "duty": _shape_duty(row) if row else None,
                    "message": "Duty was already accepted.",
                }
            if found[1] != "assigned":
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only a pending assignment can be accepted.",
                }
            cur.execute(
                """
                UPDATE booking_assignments
                SET status = 'accepted', decided_at = now()
                WHERE id = %s::uuid
                  AND driver_id = current_driver_id()
                  AND status = 'assigned'
                """,
                (assignment_id,),
            )
            if cur.rowcount != 1:
                cur.execute("ROLLBACK TO SAVEPOINT driver_duty")
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "That duty changed. Refresh and try again.",
                }
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT driver_duty")
            cur.execute("RELEASE SAVEPOINT driver_duty")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT driver_duty")
        cur.execute(_duty_select_sql("AND a.id = %s::uuid"), (assignment_id,))
        row = cur.fetchone()
        return {
            "ok": True,
            "duty": _shape_duty(row) if row else None,
            "message": "Duty accepted.",
        }

    return _driver_work(user_id, work)


def reject_duty(user_id, assignment_id, payload):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Duty was not found."}
    reason = pg._clean_text((payload or {}).get("reason"))
    if not reason:
        reason = "Rejected by driver"

    def work(cur):
        import psycopg

        cur.execute("SAVEPOINT driver_duty")
        try:
            cur.execute(
                """
                SELECT id::text, status
                FROM booking_assignments
                WHERE id = %s::uuid AND driver_id = current_driver_id()
                FOR UPDATE
                """,
                (assignment_id,),
            )
            found = cur.fetchone()
            if found is None:
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {"ok": False, "error": "not_found", "message": "Duty was not found."}
            if found[1] == "rejected":
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {"ok": True, "already": True, "message": "Duty was already rejected."}
            if found[1] != "assigned":
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only a pending assignment can be rejected.",
                }
            cur.execute(
                """
                UPDATE booking_assignments
                SET status = 'rejected',
                    rejection_reason = %s,
                    decided_at = now()
                WHERE id = %s::uuid
                  AND driver_id = current_driver_id()
                  AND status = 'assigned'
                """,
                (reason, assignment_id),
            )
            if cur.rowcount != 1:
                cur.execute("ROLLBACK TO SAVEPOINT driver_duty")
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "That duty changed. Refresh and try again.",
                }
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT driver_duty")
            cur.execute("RELEASE SAVEPOINT driver_duty")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT driver_duty")
        cur.execute(_duty_select_sql("AND a.id = %s::uuid"), (assignment_id,))
        row = cur.fetchone()
        return {
            "ok": True,
            "duty": _shape_duty(row) if row else None,
            "message": "Duty rejected.",
        }

    return _driver_work(user_id, work)


def start_trip(user_id, assignment_id, payload=None):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Duty was not found."}
    payload = payload if isinstance(payload, dict) else {}
    start_km, km_error = _parse_km(payload.get("start_km"), "Start kilometre")
    if km_error:
        return {"ok": False, "error": "invalid", "message": km_error}

    def work(cur):
        import psycopg

        cur.execute("SAVEPOINT driver_duty")
        try:
            cur.execute(
                """
                SELECT a.id::text, a.status, a.booking_id::text, b.status
                FROM booking_assignments a
                JOIN bookings b ON b.id = a.booking_id
                WHERE a.id = %s::uuid AND a.driver_id = current_driver_id()
                FOR UPDATE OF a
                """,
                (assignment_id,),
            )
            found = cur.fetchone()
            if found is None:
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {"ok": False, "error": "not_found", "message": "Duty was not found."}
            if found[1] != "accepted":
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Accept the duty before starting the trip.",
                }
            if found[3] not in ("accepted", "started"):
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "This booking cannot be started.",
                }
            cur.execute(
                """
                SELECT id::text FROM trip_sessions
                WHERE assignment_id = %s::uuid AND status = 'active'
                FOR UPDATE
                """,
                (assignment_id,),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "This trip is already started.",
                }
            session_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO trip_sessions (
                    id, assignment_id, driver_id, session_origin, status,
                    started_at, started_by
                )
                VALUES (
                    %s::uuid, %s::uuid, current_driver_id(), 'duty', 'active',
                    now(), %s::uuid
                )
                """,
                (session_id, assignment_id, user_id),
            )
            cur.execute(
                """
                INSERT INTO duty_readings (booking_id, start_km)
                VALUES (%s::uuid, %s)
                ON CONFLICT (booking_id) DO UPDATE
                SET start_km = EXCLUDED.start_km,
                    end_km = NULL,
                    total_km = NULL
                """,
                (found[2], start_km),
            )
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT driver_duty")
            cur.execute("RELEASE SAVEPOINT driver_duty")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT driver_duty")
        cur.execute(_duty_select_sql("AND a.id = %s::uuid"), (assignment_id,))
        row = cur.fetchone()
        return {
            "ok": True,
            "duty": _shape_duty(row) if row else None,
            "message": "Trip started.",
        }

    return _driver_work(user_id, work)


def complete_trip(user_id, assignment_id, payload=None):
    assignment_id = pg._parse_uuid(assignment_id)
    if assignment_id is None:
        return {"ok": False, "error": "not_found", "message": "Duty was not found."}
    payload = payload if isinstance(payload, dict) else {}
    end_km, km_error = _parse_km(payload.get("end_km"), "End kilometre")
    if km_error:
        return {"ok": False, "error": "invalid", "message": km_error}

    def work(cur):
        import psycopg

        cur.execute("SAVEPOINT driver_duty")
        try:
            cur.execute(
                """
                SELECT a.id::text, a.status, a.booking_id::text, b.status
                FROM booking_assignments a
                JOIN bookings b ON b.id = a.booking_id
                WHERE a.id = %s::uuid AND a.driver_id = current_driver_id()
                FOR UPDATE OF a
                """,
                (assignment_id,),
            )
            found = cur.fetchone()
            if found is None:
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {"ok": False, "error": "not_found", "message": "Duty was not found."}
            cur.execute(
                """
                SELECT id::text FROM trip_sessions
                WHERE assignment_id = %s::uuid
                  AND driver_id = current_driver_id()
                  AND status = 'active'
                FOR UPDATE
                """,
                (assignment_id,),
            )
            session = cur.fetchone()
            if session is None:
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Start the trip before completing it.",
                }
            cur.execute(
                "SELECT start_km FROM duty_readings WHERE booking_id = %s::uuid",
                (found[2],),
            )
            reading = cur.fetchone()
            start_km = _num(reading[0]) if reading else None
            if start_km is None:
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "invalid",
                    "message": "Start kilometre is missing for this trip.",
                }
            if end_km < start_km:
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "invalid",
                    "message": "End kilometre cannot be lower than start kilometre.",
                }
            total = end_km - start_km
            cur.execute(
                """
                UPDATE duty_readings
                SET end_km = %s, total_km = %s, driver_km = %s
                WHERE booking_id = %s::uuid
                """,
                (end_km, total, total, found[2]),
            )
            cur.execute(
                """
                UPDATE trip_sessions
                SET status = 'closed', ended_at = now()
                WHERE id = %s::uuid AND status = 'active'
                """,
                (session[0],),
            )
            if cur.rowcount != 1:
                cur.execute("ROLLBACK TO SAVEPOINT driver_duty")
                cur.execute("RELEASE SAVEPOINT driver_duty")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "That trip session changed. Refresh and try again.",
                }
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT driver_duty")
            cur.execute("RELEASE SAVEPOINT driver_duty")
            return _duty_error(exc)
        cur.execute("RELEASE SAVEPOINT driver_duty")
        cur.execute(_duty_select_sql("AND a.id = %s::uuid"), (assignment_id,))
        row = cur.fetchone()
        return {
            "ok": True,
            "duty": _shape_duty(row) if row else None,
            "message": "Trip completed.",
        }

    return _driver_work(user_id, work)


def list_notifications(user_id):
    def work(cur):
        cur.execute(
            """
            SELECT id::text, kind, title, body, read_at, created_at,
                   booking_id::text, assignment_id::text
            FROM driver_notifications
            WHERE driver_id = current_driver_id()
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
                "assignment_id": r[7],
            }
            for r in cur.fetchall()
        ]
        return {"ok": True, "notifications": items, "live": True}

    return _driver_work(user_id, work)


def mark_notification_read(user_id, notification_id):
    try:
        nid = int(notification_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "not_found", "message": "Notification was not found."}

    def work(cur):
        cur.execute(
            """
            UPDATE driver_notifications
            SET read_at = COALESCE(read_at, now())
            WHERE id = %s AND driver_id = current_driver_id()
            RETURNING id::text
            """,
            (nid,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "Notification was not found."}
        return {"ok": True, "id": row[0]}

    return _driver_work(user_id, work)


def list_payouts(user_id):
    def work(cur):
        cur.execute(
            """
            SELECT p.id::text, p.booking_id::text, b.source_booking_id, b.trip_date::text,
                   p.amount, p.status, p.paid_at, p.reference, p.currency, p.created_at
            FROM driver_payouts p
            JOIN bookings b ON b.id = p.booking_id
            WHERE p.driver_id = current_driver_id()
            ORDER BY COALESCE(p.paid_at, p.created_at) DESC NULLS LAST
            LIMIT 100
            """
        )
        payouts = [
            {
                "id": r[0],
                "booking_id": r[1],
                "booking_reference": r[2] or r[1],
                "duty_date": r[3],
                "amount": _num(r[4]),
                "status": r[5],
                "paid_at": _iso(r[6]),
                "reference": r[7],
                "currency": r[8],
                "created_at": _iso(r[9]),
            }
            for r in cur.fetchall()
        ]
        return {"ok": True, "payouts": payouts, "live": True}

    return _driver_work(user_id, work)
