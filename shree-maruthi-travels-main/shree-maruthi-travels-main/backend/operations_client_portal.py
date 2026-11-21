"""Client web portal APIs. Company isolation via smt_client RLS and server identity."""
from __future__ import annotations

import uuid
from datetime import date

import client_auth
import dev_postgres as pg


def _client_work(user_id, work):
    done = pg.authorized_transaction(user_id, work)
    if not done or done.get("role") != "client":
        return None
    return done.get("result")


def _owner_work(user_id, work):
    done = pg.authorized_transaction(user_id, work)
    if not done or done.get("role") != "owner":
        return None
    return done.get("result")


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


def authenticate_client(email, password):
    email = client_auth.normalize_email(email)
    if not email:
        return {"ok": False, "error": "invalid", "message": "Enter a valid email address."}
    if not isinstance(password, str) or len(password) < 8:
        return {"ok": False, "error": "invalid", "message": "Password must be at least 8 characters."}
    owner_id = pg._bootstrap_owner_id()
    if owner_id is None:
        return None

    box = {"row": None}

    def work(cur):
        cur.execute(
            """
            SELECT u.id::text, u.password_hash, u.status, u.full_name, u.email, u.phone,
                   l.company_id::text, c.name
            FROM users u
            JOIN user_company_links l ON l.user_id = u.id
            JOIN companies c ON c.id = l.company_id
            WHERE u.role = 'client' AND lower(u.email) = lower(%s)
            """,
            (email,),
        )
        rows = cur.fetchall()
        if len(rows) != 1:
            box["row"] = None
            return True
        box["row"] = rows[0]
        return True

    # work returns True on success; do not treat a None callback result as failure.
    if _owner_work(owner_id, work) is None:
        return None
    row = box["row"]
    if row is None:
        return {"ok": False, "error": "unauthorized", "message": "Invalid email or password."}
    user_id, password_hash, status, full_name, user_email, phone, company_id, company_name = row
    if status != "active":
        return {"ok": False, "error": "disabled", "message": "This account is disabled."}
    if not client_auth.verify_password(password_hash, password):
        return {"ok": False, "error": "unauthorized", "message": "Invalid email or password."}
    token = client_auth.issue_token(user_id, company_id)
    if not token:
        return None
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user_id,
            "full_name": full_name,
            "email": user_email,
            "phone": phone,
            "role": "client",
        },
        "company": {"id": company_id, "name": company_name},
    }


def provision_client_login(owner_user_id, client_user_id, password):
    client_user_id = pg._parse_uuid(client_user_id)
    if client_user_id is None:
        return {"ok": False, "error": "not_found", "message": "Client was not found."}
    if not isinstance(password, str) or len(password) < 8:
        return {"ok": False, "error": "invalid", "message": "Password must be at least 8 characters."}
    password_hash = client_auth.hash_password(password)

    def work(cur):
        cur.execute(
            """
            SELECT id::text, role, email, status
            FROM users WHERE id = %s::uuid
            """,
            (client_user_id,),
        )
        found = cur.fetchone()
        if found is None:
            return {"ok": False, "error": "not_found", "message": "Client was not found."}
        if found[1] != "client":
            return {"ok": False, "error": "invalid", "message": "Only a client account can receive a portal login."}
        if not found[2]:
            return {"ok": False, "error": "invalid", "message": "Client needs an email before a login can be created."}
        cur.execute(
            """
            SELECT company_id::text FROM user_company_links WHERE user_id = %s::uuid
            """,
            (client_user_id,),
        )
        links = cur.fetchall()
        if len(links) != 1:
            return {
                "ok": False,
                "error": "invalid",
                "message": "Client must be linked to exactly one company before login provisioning.",
            }
        cur.execute(
            """
            UPDATE users
            SET password_hash = %s, status = 'active'
            WHERE id = %s::uuid AND role = 'client'
            RETURNING id::text
            """,
            (password_hash, client_user_id),
        )
        updated = cur.fetchone()
        if updated is None:
            return {"ok": False, "error": "conflict", "message": "Client login could not be updated."}
        return {"ok": True, "user_id": updated[0], "company_id": links[0][0], "created": True}

    return _owner_work(owner_user_id, work)


def session_profile(user_id):
    def work(cur):
        cur.execute(
            """
            SELECT u.id::text, u.full_name, u.email, u.phone, u.status,
                   c.id::text, c.name, c.contact_person, c.contact_email, c.contact_phone, c.address
            FROM users u
            JOIN user_company_links l ON l.user_id = u.id
            JOIN companies c ON c.id = l.company_id
            WHERE u.id = %s::uuid AND u.role = 'client'
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "forbidden", "message": "Client profile was not found."}
        cur.execute(
            """
            SELECT b.code, b.name
            FROM company_branches cb
            JOIN branches b ON b.id = cb.branch_id
            WHERE cb.company_id = %s::uuid
            ORDER BY b.code
            """,
            (row[5],),
        )
        branches = [{"code": r[0], "name": r[1]} for r in cur.fetchall()]
        return {
            "ok": True,
            "user": {
                "id": row[0],
                "full_name": row[1],
                "email": row[2],
                "phone": row[3],
                "status": row[4],
                "role": "client",
            },
            "company": {
                "id": row[5],
                "name": row[6],
                "contact_person": row[7],
                "contact_email": row[8],
                "contact_phone": row[9],
                "address": row[10],
                "branches": branches,
            },
        }

    return _client_work(user_id, work)


def update_profile(user_id, payload):
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Profile details are not valid."}
    full_name = pg._clean_text(payload.get("full_name")) if "full_name" in payload else None
    phone = pg._clean_text(payload.get("phone")) if "phone" in payload else None
    if full_name is False or phone is False:
        return {"ok": False, "error": "invalid", "message": "Profile details are not valid."}
    if full_name is not None and not full_name:
        return {"ok": False, "error": "invalid", "message": "Name cannot be blank."}
    # Reject privileged fields silently as invalid.
    for banned in ("email", "role", "status", "company_id", "password", "password_hash"):
        if banned in payload:
            return {
                "ok": False,
                "error": "forbidden",
                "message": "That account setting cannot be changed here.",
            }

    def work(cur):
        assignments = []
        params = []
        if full_name is not None:
            assignments.append("full_name = %s")
            params.append(full_name)
        if phone is not None:
            assignments.append("phone = %s")
            params.append(phone or None)
        if not assignments:
            return {"ok": True, "updated": False}
        params.append(user_id)
        cur.execute(
            "UPDATE users SET %s WHERE id = %%s::uuid AND role = 'client'"
            % ", ".join(assignments),
            params,
        )
        return {"ok": True, "updated": True}

    result = _client_work(user_id, work)
    if not result or not result.get("ok"):
        return result
    return session_profile(user_id)


def _booking_shape(row):
    return {
        "id": row[0],
        "branch_code": row[1],
        "company_id": row[2],
        "origin": row[3],
        "booking_reference": row[4] or row[0],
        "trip_date": row[5],
        "pickup_time": row[6],
        "end_time": row[7],
        "duty_type": row[8],
        "cab_type": row[9],
        "pickup_location": row[10],
        "route": row[11],
        "passenger_name": row[12],
        "passenger_phone": row[13],
        "status": row[14],
        "remarks": row[15],
        "created_at": _iso(row[16]),
    }


def _duty_shape(row):
    return {
        "booking_id": row[0],
        "trip_date": _iso(row[1]) if row[1] and not isinstance(row[1], str) else row[1],
        "pickup_time": str(row[2]) if row[2] is not None else None,
        "cab_type": row[3],
        "pickup_location": row[4],
        "route": row[5],
        "passenger_name": row[6],
        "duty_status": row[7],
        "assignment_status": row[8],
        "driver_name": row[9],
        "driver_phone": row[10],
        "vehicle_registration": row[11],
        "vehicle_model": row[12],
    }


_BOOKING_SELECT = """
    SELECT b.id::text, br.code, b.company_id::text, b.origin, b.source_booking_id,
           b.trip_date::text, b.pickup_time::text, b.end_time::text, b.duty_type, b.cab_type,
           b.planned_start, b.route_text, b.employee_name, b.source_mobile, b.status,
           b.remarks, b.created_at
    FROM bookings b
    JOIN branches br ON br.id = b.branch_id
    WHERE b.company_id IS NOT NULL AND client_can_company(b.company_id)
"""


def list_bookings(user_id, status=None, search=None):
    status = (status or "").strip().lower() or None
    search = (search or "").strip()
    if search and len(search) > 80:
        return {"ok": False, "error": "invalid", "message": "Search is too long."}

    def work(cur):
        clauses = []
        params = []
        if status:
            clauses.append("b.status = %s")
            params.append(status)
        if search:
            clauses.append(
                "(b.source_booking_id ILIKE %s OR b.employee_name ILIKE %s OR b.planned_start ILIKE %s)"
            )
            like = "%" + search + "%"
            params.extend([like, like, like])
        sql = _BOOKING_SELECT
        if clauses:
            sql += " AND " + " AND ".join(clauses)
        sql += " ORDER BY b.trip_date DESC NULLS LAST, b.created_at DESC LIMIT 200"
        cur.execute(sql, params)
        return {"ok": True, "bookings": [_booking_shape(r) for r in cur.fetchall()]}

    return _client_work(user_id, work)


def get_booking(user_id, booking_id):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}

    def work(cur):
        cur.execute(_BOOKING_SELECT + " AND b.id = %s::uuid", (booking_id,))
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "Booking was not found."}
        cur.execute(
            """
            SELECT booking_id::text, trip_date, pickup_time, cab_type, planned_start, route_text,
                   employee_name, duty_status, assignment_status, driver_name, driver_phone,
                   vehicle_registration, vehicle_model
            FROM client_duty_status
            WHERE booking_id = %s::uuid
            """,
            (booking_id,),
        )
        duty = cur.fetchone()
        result = {"ok": True, "booking": _booking_shape(row)}
        if duty:
            result["trip"] = _duty_shape(duty)
        return result

    return _client_work(user_id, work)


def create_booking_request(user_id, payload):
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Booking details are not valid."}
    branch_code = pg._clean_text(payload.get("branch_code"))
    if not branch_code:
        return {"ok": False, "error": "invalid", "message": "Choose Bengaluru or Hyderabad."}
    trip_date = pg._clean_date(payload.get("trip_date"))
    if not trip_date:
        return {"ok": False, "error": "invalid", "message": "Trip date is required."}
    pickup_raw = payload.get("pickup_time")
    if isinstance(pickup_raw, str) and pickup_raw.strip():
        import re
        match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", pickup_raw.strip())
        if not match:
            return {"ok": False, "error": "invalid", "message": "Pickup time is not valid."}
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            return {"ok": False, "error": "invalid", "message": "Pickup time is not valid."}
        pickup_time = "%02d:%02d:00" % (hour, minute)
    else:
        pickup_time = None

    planned_start = pg._clean_text(payload.get("pickup_location") or payload.get("planned_start"))
    if not planned_start:
        return {"ok": False, "error": "invalid", "message": "Pickup location is required."}
    employee_name = pg._clean_text(payload.get("passenger_name") or payload.get("employee_name"))
    route_text = pg._clean_text(payload.get("route") or payload.get("route_text"))
    duty_type = pg._clean_text(payload.get("duty_type"))
    cab_type = pg._clean_text(payload.get("cab_type"))
    source_mobile = pg._clean_text(payload.get("passenger_phone") or payload.get("source_mobile"))
    remarks = pg._clean_text(payload.get("remarks"))
    if any(v is False for v in (planned_start, employee_name, route_text, duty_type, cab_type, source_mobile, remarks)):
        return {"ok": False, "error": "invalid", "message": "Booking details are not valid."}

    def work(cur):
        import psycopg

        cur.execute(
            """
            SELECT c.id::text
            FROM user_company_links l
            JOIN companies c ON c.id = l.company_id
            WHERE l.user_id = %s::uuid
            """,
            (user_id,),
        )
        companies = cur.fetchall()
        if len(companies) != 1:
            return {"ok": False, "error": "forbidden", "message": "Company association is not available."}
        company_id = companies[0][0]
        cur.execute(
            """
            SELECT b.id::text
            FROM branches b
            JOIN company_branches cb ON cb.branch_id = b.id
            WHERE cb.company_id = %s::uuid AND upper(b.code) = upper(%s)
            """,
            (company_id, branch_code),
        )
        branch = cur.fetchone()
        if branch is None:
            return {
                "ok": False,
                "error": "invalid",
                "message": "That branch is not available for your company.",
            }
        source_id = "CLIENT-" + uuid.uuid4().hex[:12].upper()
        booking_id = str(uuid.uuid4())
        cur.execute("SAVEPOINT client_booking")
        try:
            cur.execute(
                """
                INSERT INTO bookings (
                    id, branch_id, company_id, origin, source_booking_id, trip_date,
                    pickup_time, duty_type, cab_type, planned_start, route_text,
                    employee_name, source_mobile, status, remarks
                )
                VALUES (
                    %s::uuid, %s::uuid, %s::uuid, 'client_request', %s, %s::date,
                    %s::time, %s, %s, %s, %s,
                    %s, %s, 'unassigned', %s
                )
                """,
                (
                    booking_id, branch[0], company_id, source_id, trip_date,
                    pickup_time, duty_type, cab_type, planned_start, route_text,
                    employee_name, source_mobile, remarks,
                ),
            )
        except psycopg.Error:
            cur.execute("ROLLBACK TO SAVEPOINT client_booking")
            cur.execute("RELEASE SAVEPOINT client_booking")
            return {
                "ok": False,
                "error": "invalid",
                "message": "Booking request could not be saved.",
            }
        cur.execute("RELEASE SAVEPOINT client_booking")
        cur.execute(_BOOKING_SELECT + " AND b.id = %s::uuid", (booking_id,))
        row = cur.fetchone()
        return {
            "ok": True,
            "booking": _booking_shape(row) if row else None,
            "message": "Booking request submitted. A supervisor will assign a driver.",
        }

    return _client_work(user_id, work)


def update_booking_request(user_id, booking_id, payload):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Booking details are not valid."}
    if payload.get("status") == "cancelled" or payload.get("action") == "cancel":
        return cancel_booking_request(user_id, booking_id)

    fields = {}
    mapping = {
        "trip_date": ("trip_date", lambda v: pg._clean_date(v)),
        "pickup_location": ("planned_start", lambda v: pg._clean_text(v)),
        "planned_start": ("planned_start", lambda v: pg._clean_text(v)),
        "route": ("route_text", lambda v: pg._clean_text(v)),
        "route_text": ("route_text", lambda v: pg._clean_text(v)),
        "passenger_name": ("employee_name", lambda v: pg._clean_text(v)),
        "employee_name": ("employee_name", lambda v: pg._clean_text(v)),
        "passenger_phone": ("source_mobile", lambda v: pg._clean_text(v)),
        "source_mobile": ("source_mobile", lambda v: pg._clean_text(v)),
        "duty_type": ("duty_type", lambda v: pg._clean_text(v)),
        "cab_type": ("cab_type", lambda v: pg._clean_text(v)),
        "remarks": ("remarks", lambda v: pg._clean_text(v)),
    }
    for key, (column, cleaner) in mapping.items():
        if key not in payload:
            continue
        value = cleaner(payload.get(key))
        if value is False:
            return {"ok": False, "error": "invalid", "message": "Booking details are not valid."}
        fields[column] = value
    if "pickup_time" in payload:
        raw = payload.get("pickup_time")
        if raw in (None, ""):
            fields["pickup_time"] = None
        elif isinstance(raw, str):
            import re
            match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", raw.strip())
            if not match:
                return {"ok": False, "error": "invalid", "message": "Pickup time is not valid."}
            fields["pickup_time"] = "%02d:%02d:00" % (int(match.group(1)), int(match.group(2)))
        else:
            return {"ok": False, "error": "invalid", "message": "Pickup time is not valid."}
    if not fields:
        return {"ok": False, "error": "invalid", "message": "No editable fields were provided."}

    def work(cur):
        import psycopg

        cur.execute("SAVEPOINT client_booking")
        try:
            cur.execute(
                """
                SELECT id::text, status, origin
                FROM bookings
                WHERE id = %s::uuid AND client_can_company(company_id)
                FOR UPDATE
                """,
                (booking_id,),
            )
            found = cur.fetchone()
            if found is None:
                cur.execute("RELEASE SAVEPOINT client_booking")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            if found[2] != "client_request" or found[1] != "unassigned":
                cur.execute("RELEASE SAVEPOINT client_booking")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an unassigned client request can be edited.",
                }
            assignments = []
            params = []
            for column, value in fields.items():
                assignments.append("%s = %%s" % column)
                params.append(value)
            params.append(booking_id)
            cur.execute(
                "UPDATE bookings SET %s WHERE id = %%s::uuid AND status = 'unassigned'"
                % ", ".join(assignments),
                params,
            )
            if cur.rowcount != 1:
                cur.execute("ROLLBACK TO SAVEPOINT client_booking")
                cur.execute("RELEASE SAVEPOINT client_booking")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "That booking changed. Refresh and try again.",
                }
        except psycopg.Error:
            cur.execute("ROLLBACK TO SAVEPOINT client_booking")
            cur.execute("RELEASE SAVEPOINT client_booking")
            return {"ok": False, "error": "invalid", "message": "Booking could not be updated."}
        cur.execute("RELEASE SAVEPOINT client_booking")
        cur.execute(_BOOKING_SELECT + " AND b.id = %s::uuid", (booking_id,))
        row = cur.fetchone()
        return {"ok": True, "booking": _booking_shape(row) if row else None}

    return _client_work(user_id, work)


def cancel_booking_request(user_id, booking_id):
    booking_id = pg._parse_uuid(booking_id)
    if booking_id is None:
        return {"ok": False, "error": "not_found", "message": "Booking was not found."}

    def work(cur):
        import psycopg

        cur.execute("SAVEPOINT client_booking")
        try:
            cur.execute(
                """
                SELECT id::text, status, origin
                FROM bookings
                WHERE id = %s::uuid AND client_can_company(company_id)
                FOR UPDATE
                """,
                (booking_id,),
            )
            found = cur.fetchone()
            if found is None:
                cur.execute("RELEASE SAVEPOINT client_booking")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            if found[2] != "client_request" or found[1] != "unassigned":
                cur.execute("RELEASE SAVEPOINT client_booking")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only an unassigned client request can be cancelled.",
                }
            cur.execute(
                """
                UPDATE bookings
                SET status = 'cancelled'
                WHERE id = %s::uuid AND status = 'unassigned' AND origin = 'client_request'
                """,
                (booking_id,),
            )
            if cur.rowcount != 1:
                cur.execute("ROLLBACK TO SAVEPOINT client_booking")
                cur.execute("RELEASE SAVEPOINT client_booking")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "That booking changed. Refresh and try again.",
                }
        except psycopg.Error:
            cur.execute("ROLLBACK TO SAVEPOINT client_booking")
            cur.execute("RELEASE SAVEPOINT client_booking")
            return {"ok": False, "error": "invalid", "message": "Booking could not be cancelled."}
        cur.execute("RELEASE SAVEPOINT client_booking")
        cur.execute(_BOOKING_SELECT + " AND b.id = %s::uuid", (booking_id,))
        row = cur.fetchone()
        return {"ok": True, "booking": _booking_shape(row) if row else None, "message": "Booking cancelled."}

    return _client_work(user_id, work)


def list_trips(user_id, filter_name=None):
    filter_name = (filter_name or "all").strip().lower()
    today = date.today().isoformat()

    def work(cur):
        clauses = {
            "upcoming": "AND trip_date >= %s::date AND duty_status NOT IN ('completed','cancelled')",
            "completed": "AND duty_status = 'completed'",
            "assigned": "AND assignment_status IS NOT NULL",
            "all": "",
        }
        if filter_name not in clauses:
            return {"ok": False, "error": "invalid", "message": "Unknown trip filter."}
        extra = clauses[filter_name]
        params = (today,) if "%s" in extra else ()
        cur.execute(
            """
            SELECT booking_id::text, trip_date, pickup_time, cab_type, planned_start, route_text,
                   employee_name, duty_status, assignment_status, driver_name, driver_phone,
                   vehicle_registration, vehicle_model
            FROM client_duty_status
            WHERE true
            %s
            ORDER BY trip_date DESC NULLS LAST
            LIMIT 200
            """ % extra,
            params,
        )
        return {"ok": True, "trips": [_duty_shape(r) for r in cur.fetchall()], "filter": filter_name}

    return _client_work(user_id, work)


def list_invoices(user_id):
    def work(cur):
        cur.execute(
            """
            SELECT i.id::text, i.invoice_number, i.issued_at, i.due_date, i.currency,
                   bal.total_amount, bal.paid_amount, bal.outstanding_amount,
                   br.code, i.period_start::text, i.period_end::text
            FROM invoices i
            JOIN branches br ON br.id = i.branch_id
            LEFT JOIN invoice_balances bal ON bal.invoice_id = i.id
            WHERE client_can_company(i.company_id)
              AND i.issued_at IS NOT NULL
              AND i.voided_at IS NULL
            ORDER BY i.issued_at DESC
            LIMIT 100
            """
        )
        invoices = []
        for r in cur.fetchall():
            invoices.append({
                "id": r[0],
                "invoice_number": r[1],
                "issued_at": _iso(r[2]),
                "due_date": _iso(r[3]) if r[3] else None,
                "currency": r[4],
                "total_amount": _num(r[5]),
                "paid_amount": _num(r[6]),
                "outstanding_amount": _num(r[7]),
                "branch_code": r[8],
                "period_start": r[9],
                "period_end": r[10],
                "status": "paid" if (_num(r[7]) or 0) <= 0 else "outstanding",
            })
        return {"ok": True, "invoices": invoices}

    return _client_work(user_id, work)


def get_invoice(user_id, invoice_id):
    invoice_id = pg._parse_uuid(invoice_id)
    if invoice_id is None:
        return {"ok": False, "error": "not_found", "message": "Invoice was not found."}

    def work(cur):
        cur.execute(
            """
            SELECT i.id::text, i.invoice_number, i.issued_at, i.due_date, i.currency,
                   bal.total_amount, bal.paid_amount, bal.outstanding_amount,
                   br.code, i.period_start::text, i.period_end::text, c.name
            FROM invoices i
            JOIN branches br ON br.id = i.branch_id
            JOIN companies c ON c.id = i.company_id
            LEFT JOIN invoice_balances bal ON bal.invoice_id = i.id
            WHERE i.id = %s::uuid
              AND client_can_company(i.company_id)
              AND i.issued_at IS NOT NULL
              AND i.voided_at IS NULL
            """,
            (invoice_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
        cur.execute(
            """
            SELECT id::text, description, amount, booking_id::text
            FROM invoice_lines
            WHERE invoice_id = %s::uuid
            ORDER BY id
            """,
            (invoice_id,),
        )
        lines = [
            {
                "id": r[0],
                "description": r[1],
                "amount": _num(r[2]),
                "booking_id": r[3],
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "invoice": {
                "id": row[0],
                "invoice_number": row[1],
                "issued_at": _iso(row[2]),
                "due_date": _iso(row[3]) if row[3] else None,
                "currency": row[4],
                "total_amount": _num(row[5]),
                "paid_amount": _num(row[6]),
                "outstanding_amount": _num(row[7]),
                "branch_code": row[8],
                "period_start": row[9],
                "period_end": row[10],
                "company_name": row[11],
                "status": "paid" if (_num(row[7]) or 0) <= 0 else "outstanding",
                "lines": lines,
            },
        }

    return _client_work(user_id, work)


def list_payments(user_id):
    def work(cur):
        cur.execute(
            """
            SELECT p.id::text, p.invoice_id::text, i.invoice_number, p.amount, p.paid_on,
                   p.method, p.reference, p.reversed_at, p.currency
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            WHERE client_can_company(i.company_id)
              AND i.issued_at IS NOT NULL
              AND i.voided_at IS NULL
            ORDER BY p.paid_on DESC, p.id DESC
            LIMIT 100
            """
        )
        payments = []
        for r in cur.fetchall():
            payments.append({
                "id": r[0],
                "invoice_id": r[1],
                "invoice_number": r[2],
                "amount": _num(r[3]),
                "paid_on": _iso(r[4]) if r[4] else None,
                "method": r[5],
                "reference": r[6],
                "reversed_at": _iso(r[7]),
                "currency": r[8],
                "status": "reversed" if r[7] else "recorded",
            })
        return {"ok": True, "payments": payments}

    return _client_work(user_id, work)


def dashboard(user_id):
    def work(cur):
        profile = None
        cur.execute(
            """
            SELECT u.full_name, u.email, c.id::text, c.name
            FROM users u
            JOIN user_company_links l ON l.user_id = u.id
            JOIN companies c ON c.id = l.company_id
            WHERE u.id = %s::uuid
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "forbidden", "message": "Client profile was not found."}
        today = date.today().isoformat()
        cur.execute(
            _BOOKING_SELECT
            + " AND b.trip_date >= %s::date AND b.status NOT IN ('completed','cancelled')"
            + " ORDER BY b.trip_date ASC LIMIT 10",
            (today,),
        )
        upcoming = [_booking_shape(r) for r in cur.fetchall()]
        cur.execute(
            _BOOKING_SELECT
            + " AND b.status = 'completed' ORDER BY b.trip_date DESC LIMIT 10"
        )
        completed = [_booking_shape(r) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT COALESCE(SUM(bal.outstanding_amount), 0)
            FROM invoices i
            JOIN invoice_balances bal ON bal.invoice_id = i.id
            WHERE client_can_company(i.company_id)
              AND i.issued_at IS NOT NULL
              AND i.voided_at IS NULL
            """
        )
        outstanding = _num(cur.fetchone()[0]) or 0
        cur.execute(
            """
            SELECT p.id::text, p.amount, p.paid_on, i.invoice_number, p.reversed_at
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            WHERE client_can_company(i.company_id)
              AND i.voided_at IS NULL
            ORDER BY p.paid_on DESC, p.id DESC
            LIMIT 5
            """
        )
        recent_payments = [
            {
                "id": r[0],
                "amount": _num(r[1]),
                "paid_on": _iso(r[2]) if r[2] else None,
                "invoice_number": r[3],
                "status": "reversed" if r[4] else "recorded",
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "user": {"full_name": row[0], "email": row[1]},
            "company": {"id": row[2], "name": row[3]},
            "upcoming_bookings": upcoming,
            "recent_completed": completed,
            "outstanding_balance": outstanding,
            "recent_payments": recent_payments,
        }

    return _client_work(user_id, work)


def support_info():
    """Verified contact details reused from the public contact page."""
    return {
        "ok": True,
        "support": {
            "company": "Shree Maruthi Travels",
            "phone": "+91 9611975999",
            "email": "shreemaruthitravels5999@gmail.com",
            "address": (
                "No. 374C, 1st Floor, 4th Cross, 9th Main, 1st Stage, Gubbalala, "
                "Near Pride Apartment, Jayanagar Housing Society Layout, Bangalore – 560061."
            ),
            "site_url": "https://www.shreemaruthitravels.com",
        },
    }
