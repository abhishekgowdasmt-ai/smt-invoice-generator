"""Optional connection to the local development database.

Production leaves SMT_DEV_DATABASE_URL unset. The SQLite, JSON, and Zoho
stores stay in place, and this module does not replace them.
"""
import os
import re
import uuid
from datetime import date


def development_database_url():
    return (os.environ.get("SMT_DEV_DATABASE_URL") or "").strip().strip('"')


def local_development_dsn():
    """Return the development DSN only when it points at this machine."""
    dsn = development_database_url()
    if not dsn:
        return None
    if "127.0.0.1" not in dsn and "localhost" not in dsn:
        return None
    return dsn


def check_development_database():
    """Return connection facts when local development PostgreSQL is configured."""
    dsn = development_database_url()
    if not dsn:
        return None
    if local_development_dsn() is None:
        print("[WARN] SMT_DEV_DATABASE_URL is not local; development check skipped")
        return None
    try:
        import psycopg
    except ImportError:
        print("[WARN] Local PostgreSQL is configured but psycopg is not installed")
        return None
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT current_database(), current_user, current_setting('TIMEZONE')"
                )
                database, user, timezone = cur.fetchone()
                cur.execute(
                    "SELECT count(*) FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'r'"
                )
                tables = cur.fetchone()[0]
    except Exception as exc:
        print(f"[WARN] Local PostgreSQL check failed: {type(exc).__name__}")
        return None
    print(f"[OK] Local PostgreSQL {database} as {user} timezone {timezone} tables {tables}")
    return {
        "database": database,
        "user": user,
        "timezone": timezone,
        "tables": tables,
    }


def list_branches(include_inactive=False):
    """Read the branch directory. Returns None when local PostgreSQL is unavailable."""
    dsn = local_development_dsn()
    if not dsn:
        return None
    try:
        import psycopg
    except ImportError:
        return None
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user")
                connected_as = cur.fetchone()[0]
                if connected_as != "smt_app":
                    return None
                cur.execute(
                    """
                    SELECT id::text, code, name, city, timezone, active
                    FROM branches
                    WHERE active = true OR %s
                    ORDER BY code
                    """,
                    (bool(include_inactive),),
                )
                rows = cur.fetchall()
    except Exception as exc:
        print(f"[WARN] Local branch directory failed: {type(exc).__name__}")
        return None
    return [
        {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "city": row[3],
            "timezone": row[4],
            "is_active": bool(row[5]),
        }
        for row in rows
    ]


_APPROVED_ROLES = ("owner", "staff", "driver", "client")
_SET_LOCAL_ROLE = {
    "owner": "SET LOCAL ROLE smt_owner",
    "staff": "SET LOCAL ROLE smt_staff",
    "driver": "SET LOCAL ROLE smt_driver",
    "client": "SET LOCAL ROLE smt_client",
}
_DATABASE_ROLE = {
    "owner": "smt_owner",
    "staff": "smt_staff",
    "driver": "smt_driver",
    "client": "smt_client",
}


def _parse_uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _bootstrap_owner_id():
    return _parse_uuid(os.environ.get("SMT_DEV_BOOTSTRAP_OWNER_ID") or "")


def authorized_transaction(user_id, callback):
    """Run callback inside the user's transaction-local database role.

    user_id must already have been resolved by the server. The dispatch bearer
    is not an argument and cannot select the role. Returns None on failure.
    """
    parsed = _parse_uuid(user_id)
    dsn = local_development_dsn()
    if parsed is None or dsn is None:
        return None
    try:
        import psycopg
    except ImportError:
        return None
    conn = None
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute("SELECT current_user")
            if cur.fetchone()[0] != "smt_app":
                conn.rollback()
                return None
            cur.execute("SELECT app_begin(%s::uuid)", (parsed,))
            found = cur.fetchone()
            role = found[0] if found else None
            if role not in _SET_LOCAL_ROLE:
                conn.rollback()
                return None
            cur.execute(_SET_LOCAL_ROLE[role])
            cur.execute("SELECT set_config('app.user_id', %s, true)", (parsed,))
            result = callback(cur)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT current_user")
            after_commit_user = cur.fetchone()[0]
        return {
            "role": role,
            "database_role": _DATABASE_ROLE[role],
            "result": result,
            "after_commit_user": after_commit_user,
        }
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        print(f"[WARN] Local authorization failed: {type(exc).__name__}")
        return None
    finally:
        if conn is not None:
            conn.close()


def _rows_as_owner(sql, params):
    owner_id = _bootstrap_owner_id()
    if owner_id is None:
        return None
    box = {}

    def work(cur):
        cur.execute("SELECT current_user")
        box["database_role"] = cur.fetchone()[0]
        cur.execute(sql, params)
        box["rows"] = cur.fetchall()

    done = authorized_transaction(owner_id, work)
    if done is None or done.get("database_role") != "smt_owner":
        return None
    return box.get("rows")


def resolve_login_identity(email):
    """Resolve one verified email to the active users row. The browser does not supply the id."""
    email = (email or "").strip().lower()
    if not email or local_development_dsn() is None:
        return {"ok": False, "reason": "unavailable"}
    rows = _rows_as_owner(
        """
        SELECT id::text, role, status
        FROM users
        WHERE lower(email) = lower(%s)
        """,
        (email,),
    )
    if rows is None:
        return {"ok": False, "reason": "unavailable"}
    if len(rows) == 0:
        return {"ok": False, "reason": "not_found"}
    if len(rows) > 1:
        return {"ok": False, "reason": "ambiguous"}
    user_id, role, status = rows[0]
    if status != "active":
        return {"ok": False, "reason": "disabled", "id": user_id, "role": role, "status": status}
    if role not in _APPROVED_ROLES:
        return {"ok": False, "reason": "conflict", "id": user_id, "role": role, "status": status}
    return {"ok": True, "id": user_id, "role": role, "status": status}


def database_role_for_email(email, bearer_payload=None):
    """The bearer payload is ignored. The database role comes from the users row."""
    del bearer_payload
    found = resolve_login_identity(email)
    if not found.get("ok"):
        return None
    return _DATABASE_ROLE.get(found.get("role"))


_CITY_CODES = ("BLR", "HYD")


def _clean_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text or None


def _branch_maps():
    """City codes come from the smt_app branch directory, not from a role that cannot read branches."""
    rows = list_branches(include_inactive=True)
    if rows is None:
        return None
    by_code = {}
    by_id = {}
    for row in rows:
        by_id[row["id"]] = row
        if row["code"] in _CITY_CODES and row["is_active"]:
            by_code[row["code"]] = row
    return by_code, by_id


def _company_shape(rows, by_id):
    grouped = {}
    order = []
    for company_id, name, person, email, phone, address, branch_id in rows:
        company = grouped.get(company_id)
        if company is None:
            company = {
                "id": company_id,
                "name": name,
                "contact_person": person,
                "contact_email": email,
                "contact_phone": phone,
                "address": address,
                "branches": [],
            }
            grouped[company_id] = company
            order.append(company_id)
        branch = by_id.get(branch_id) if branch_id else None
        if branch and branch.get("code"):
            company["branches"].append({
                "code": branch["code"],
                "name": branch["name"],
                "city": branch["city"],
            })
    companies = []
    for company_id in order:
        company = grouped[company_id]
        company["branches"].sort(key=lambda item: item["code"])
        companies.append(company)
    return companies


def _select_companies(cur, company_id=None):
    params = ()
    where = ""
    if company_id is not None:
        where = "WHERE c.id = %s::uuid"
        params = (company_id,)
    cur.execute(
        f"""
        SELECT c.id::text, c.name, c.contact_person, c.contact_email,
               c.contact_phone, c.address, cb.branch_id::text
        FROM companies c
        LEFT JOIN company_branches cb ON cb.company_id = c.id
        {where}
        ORDER BY c.name, c.id, cb.branch_id
        """,
        params,
    )
    return cur.fetchall()


def _owner_work(user_id, work):
    done = authorized_transaction(user_id, work)
    if not done or done.get("role") != "owner":
        return None
    return done.get("result")


def list_companies(user_id):
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        return {"ok": True, "companies": _company_shape(_select_companies(cur), by_id)}

    return _owner_work(user_id, work)


def get_company(user_id, company_id):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        rows = _select_companies(cur, parsed)
        companies = _company_shape(rows, by_id)
        if not companies:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "company": companies[0]}

    return _owner_work(user_id, work)


def _city_ids(branch_codes):
    if not isinstance(branch_codes, list) or not branch_codes:
        return None, "Select Bengaluru or Hyderabad"
    maps = _branch_maps()
    if maps is None:
        return None, None
    by_code, _ = maps
    chosen = []
    seen = set()
    for code in branch_codes:
        if not isinstance(code, str):
            return None, "Select Bengaluru or Hyderabad"
        normalized = code.strip().upper()
        if normalized not in _CITY_CODES or normalized not in by_code:
            return None, "Select Bengaluru or Hyderabad"
        if normalized in seen:
            continue
        seen.add(normalized)
        chosen.append(by_code[normalized]["id"])
    if not chosen:
        return None, "Select Bengaluru or Hyderabad"
    return chosen, None


def _company_fields(payload, require_name=True):
    if not isinstance(payload, dict):
        return None, "Company details are not valid"
    name = _clean_text(payload.get("name"))
    if name is False or (require_name and not name):
        return None, "Company name is required"
    person = _clean_text(payload.get("contact_person"))
    email = _clean_text(payload.get("contact_email"))
    phone = _clean_text(payload.get("contact_phone"))
    address = _clean_text(payload.get("address"))
    if False in (person, email, phone, address):
        return None, "Company details are not valid"
    return {
        "name": name,
        "contact_person": person,
        "contact_email": email,
        "contact_phone": phone,
        "address": address,
    }, None


def create_company(user_id, payload):
    fields, error = _company_fields(payload or {})
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    branch_ids, city_error = _city_ids((payload or {}).get("branch_codes"))
    if city_error:
        return {"ok": False, "error": "invalid", "message": city_error}
    if branch_ids is None:
        return None
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        cur.execute(
            """
            INSERT INTO companies (name, contact_person, contact_email, contact_phone, address)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            (
                fields["name"],
                fields["contact_person"],
                fields["contact_email"],
                fields["contact_phone"],
                fields["address"],
            ),
        )
        company_id = cur.fetchone()[0]
        for branch_id in branch_ids:
            cur.execute(
                """
                INSERT INTO company_branches (company_id, branch_id)
                VALUES (%s::uuid, %s::uuid)
                ON CONFLICT DO NOTHING
                """,
                (company_id, branch_id),
            )
        companies = _company_shape(_select_companies(cur, company_id), by_id)
        return {"ok": True, "company": companies[0]}

    return _owner_work(user_id, work)


def update_company(user_id, company_id, payload):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found"}
    fields, error = _company_fields(payload or {})
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        cur.execute(
            """
            UPDATE companies
            SET name = %s,
                contact_person = %s,
                contact_email = %s,
                contact_phone = %s,
                address = %s
            WHERE id = %s::uuid
            RETURNING id::text
            """,
            (
                fields["name"],
                fields["contact_person"],
                fields["contact_email"],
                fields["contact_phone"],
                fields["address"],
                parsed,
            ),
        )
        if cur.fetchone() is None:
            return {"ok": False, "error": "not_found"}
        companies = _company_shape(_select_companies(cur, parsed), by_id)
        return {"ok": True, "company": companies[0]}

    return _owner_work(user_id, work)


def _branch_is_referenced(cur, company_id, branch_id):
    cur.execute(
        """
        SELECT
            EXISTS (
                SELECT 1 FROM ets_contracts
                WHERE company_id = %s::uuid AND branch_id = %s::uuid
            )
            OR EXISTS (
                SELECT 1 FROM bookings
                WHERE company_id = %s::uuid AND branch_id = %s::uuid
            )
            OR EXISTS (
                SELECT 1 FROM invoices
                WHERE company_id = %s::uuid AND branch_id = %s::uuid
            )
            OR EXISTS (
                SELECT 1
                FROM company_vehicles cv
                JOIN vehicles v ON v.id = cv.vehicle_id
                WHERE cv.company_id = %s::uuid AND v.branch_id = %s::uuid
            )
            OR EXISTS (
                SELECT 1
                FROM company_drivers cd
                JOIN driver_branches db ON db.driver_id = cd.driver_id
                WHERE cd.company_id = %s::uuid AND db.branch_id = %s::uuid
            )
        """,
        (company_id, branch_id) * 5,
    )
    return bool(cur.fetchone()[0])


def _city_for_code(code):
    if not isinstance(code, str):
        return None, {"ok": False, "error": "invalid", "message": "Select Bengaluru or Hyderabad"}
    normalized = code.strip().upper()
    maps = _branch_maps()
    if maps is None:
        return None, None
    by_code, by_id = maps
    branch = by_code.get(normalized)
    if branch is None:
        return None, {"ok": False, "error": "invalid", "message": "Select Bengaluru or Hyderabad"}
    return (branch, by_id), None


def add_company_branch(user_id, company_id, code):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found"}
    found, error = _city_for_code(code)
    if error or found is None:
        return error
    branch, by_id = found

    def work(cur):
        cur.execute("SELECT 1 FROM companies WHERE id = %s::uuid", (parsed,))
        if cur.fetchone() is None:
            return {"ok": False, "error": "not_found"}
        cur.execute(
            """
            INSERT INTO company_branches (company_id, branch_id)
            VALUES (%s::uuid, %s::uuid)
            ON CONFLICT DO NOTHING
            RETURNING company_id
            """,
            (parsed, branch["id"]),
        )
        if cur.fetchone() is None:
            return {
                "ok": False,
                "error": "duplicate",
                "message": "This company is already linked to that city",
            }
        companies = _company_shape(_select_companies(cur, parsed), by_id)
        return {"ok": True, "company": companies[0]}

    return _owner_work(user_id, work)


def remove_company_branch(user_id, company_id, code):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found"}
    found, error = _city_for_code(code)
    if error or found is None:
        return error
    branch, by_id = found

    def work(cur):
        cur.execute("SELECT 1 FROM companies WHERE id = %s::uuid", (parsed,))
        if cur.fetchone() is None:
            return {"ok": False, "error": "not_found"}
        if _branch_is_referenced(cur, parsed, branch["id"]):
            return {
                "ok": False,
                "error": "in_use",
                "message": "This city is still used by a contract, booking, invoice, vehicle, or driver",
            }
        cur.execute(
            """
            DELETE FROM company_branches
            WHERE company_id = %s::uuid AND branch_id = %s::uuid
            RETURNING company_id
            """,
            (parsed, branch["id"]),
        )
        if cur.fetchone() is None:
            return {"ok": False, "error": "not_found", "message": "That city is not linked to this company"}
        companies = _company_shape(_select_companies(cur, parsed), by_id)
        return {"ok": True, "company": companies[0]}

    return _owner_work(user_id, work)


def _company_exists(cur, company_id):
    cur.execute("SELECT 1 FROM companies WHERE id = %s::uuid", (company_id,))
    return cur.fetchone() is not None


def _company_driver_shape(row, by_id):
    driver_id, name, phone, licence, active, primary_id = row
    primary = by_id.get(primary_id)
    return {
        "id": driver_id,
        "display_name": name,
        "phone": phone,
        "license_number": licence,
        "active": bool(active),
        "primary_branch": None if primary is None else {
            "code": primary["code"],
            "name": primary["name"],
            "city": primary["city"],
        },
    }


def _select_company_drivers(cur, company_id, by_id):
    cur.execute(
        """
        SELECT d.id::text, d.display_name, d.phone, d.license_number,
               d.active, d.primary_branch_id::text
        FROM company_drivers cd
        JOIN drivers d ON d.id = cd.driver_id
        WHERE cd.company_id = %s::uuid
        ORDER BY d.display_name, d.id
        """,
        (company_id,),
    )
    return [_company_driver_shape(row, by_id) for row in cur.fetchall()]


def _write_company_driver(cur, sql, params, removing):
    import psycopg

    cur.execute("SAVEPOINT company_driver_write")
    try:
        cur.execute(sql, params)
    except psycopg.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT company_driver_write")
        if isinstance(exc, psycopg.errors.UniqueViolation):
            return {
                "ok": False,
                "error": "duplicate",
                "message": "This driver is already linked to the company.",
            }
        if isinstance(exc, psycopg.errors.RaiseException):
            if removing:
                return {
                    "ok": False,
                    "error": "in_use",
                    "message": "This driver is still used by an assignment for the company.",
                }
            return {
                "ok": False,
                "error": "invalid",
                "message": "This driver and company do not share a city.",
            }
        raise
    affected = cur.rowcount
    cur.execute("RELEASE SAVEPOINT company_driver_write")
    return affected


def list_company_drivers(user_id, company_id):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        if not _company_exists(cur, parsed):
            return {"ok": False, "error": "not_found", "message": "Company not found"}
        return {"ok": True, "drivers": _select_company_drivers(cur, parsed, by_id)}

    return _owner_work(user_id, work)


def link_company_driver(user_id, company_id, payload):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    if not isinstance(payload, dict) or set(payload) - {"driver_id"}:
        return {"ok": False, "error": "invalid", "message": "Choose a driver from the directory."}
    driver_id = _parse_uuid(payload.get("driver_id"))
    if driver_id is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        if not _company_exists(cur, parsed):
            return {"ok": False, "error": "not_found", "message": "Company not found"}
        cur.execute("SELECT active FROM drivers WHERE id = %s::uuid", (driver_id,))
        driver = cur.fetchone()
        if driver is None:
            return {"ok": False, "error": "not_found", "message": "Driver not found"}
        if not driver[0]:
            return {
                "ok": False,
                "error": "invalid",
                "message": "An inactive driver cannot be linked to a company.",
            }
        cur.execute(
            """
            SELECT 1
            FROM driver_branches db
            JOIN company_branches cb
              ON cb.branch_id = db.branch_id AND cb.company_id = %s::uuid
            WHERE db.driver_id = %s::uuid
            """,
            (parsed, driver_id),
        )
        if cur.fetchone() is None:
            return {
                "ok": False,
                "error": "invalid",
                "message": "This driver and company do not share a city.",
            }
        outcome = _write_company_driver(
            cur,
            """
            INSERT INTO company_drivers (company_id, driver_id)
            VALUES (%s::uuid, %s::uuid)
            """,
            (parsed, driver_id),
            removing=False,
        )
        if isinstance(outcome, dict):
            return outcome
        return {"ok": True, "drivers": _select_company_drivers(cur, parsed, by_id)}

    return _owner_work(user_id, work)


def unlink_company_driver_row(cur, company_id, driver_id, by_id):
    """Delete one company_drivers row. The driver and company rows stay."""
    if not _company_exists(cur, company_id):
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    cur.execute("SELECT 1 FROM drivers WHERE id = %s::uuid", (driver_id,))
    if cur.fetchone() is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    outcome = _write_company_driver(
        cur,
        """
        DELETE FROM company_drivers
        WHERE company_id = %s::uuid AND driver_id = %s::uuid
        """,
        (company_id, driver_id),
        removing=True,
    )
    if isinstance(outcome, dict):
        return outcome
    if outcome != 1:
        return {
            "ok": False,
            "error": "not_found",
            "message": "This driver is not linked to the company.",
        }
    return {"ok": True, "drivers": _select_company_drivers(cur, company_id, by_id)}


def unlink_company_driver(user_id, company_id, driver_id):
    parsed_company = _parse_uuid(company_id)
    parsed_driver = _parse_uuid(driver_id)
    if parsed_company is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    if parsed_driver is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        return unlink_company_driver_row(cur, parsed_company, parsed_driver, by_id)

    return _owner_work(user_id, work)


def _company_vehicle_shape(row, by_id):
    vehicle_id, registration, model, capacity, fuel_type, is_ev, status, branch_id = row
    branch = by_id.get(branch_id)
    return {
        "id": vehicle_id,
        "registration_number": registration,
        "model": model,
        "capacity": capacity,
        "fuel_type": fuel_type,
        "is_ev": bool(is_ev),
        "status": status,
        "branch": None if branch is None else {
            "code": branch["code"],
            "name": branch["name"],
            "city": branch["city"],
        },
    }


def _select_company_vehicles(cur, company_id, by_id):
    cur.execute(
        """
        SELECT v.id::text, v.registration_number, v.model, v.capacity, v.fuel_type,
               v.is_ev, v.status, v.branch_id::text
        FROM company_vehicles cv
        JOIN vehicles v ON v.id = cv.vehicle_id
        WHERE cv.company_id = %s::uuid
        ORDER BY v.registration_number NULLS LAST, v.id
        """,
        (company_id,),
    )
    return [_company_vehicle_shape(row, by_id) for row in cur.fetchall()]


def _write_company_vehicle(cur, sql, params, removing):
    import psycopg

    cur.execute("SAVEPOINT company_vehicle_write")
    try:
        cur.execute(sql, params)
    except psycopg.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT company_vehicle_write")
        if isinstance(exc, psycopg.errors.UniqueViolation):
            return {
                "ok": False,
                "error": "duplicate",
                "message": "This vehicle is already linked to the company.",
            }
        if isinstance(exc, psycopg.errors.RaiseException):
            if removing:
                return {
                    "ok": False,
                    "error": "in_use",
                    "message": "This vehicle is still used by an assignment for the company.",
                }
            return {
                "ok": False,
                "error": "invalid",
                "message": "This vehicle is garaged in a city the company does not use.",
            }
        raise
    affected = cur.rowcount
    cur.execute("RELEASE SAVEPOINT company_vehicle_write")
    return affected


def list_company_vehicles(user_id, company_id):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        if not _company_exists(cur, parsed):
            return {"ok": False, "error": "not_found", "message": "Company not found"}
        return {"ok": True, "vehicles": _select_company_vehicles(cur, parsed, by_id)}

    return _owner_work(user_id, work)


def link_company_vehicle(user_id, company_id, payload):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    if not isinstance(payload, dict) or set(payload) - {"vehicle_id"}:
        return {"ok": False, "error": "invalid", "message": "Choose a vehicle from the directory."}
    vehicle_id = _parse_uuid(payload.get("vehicle_id"))
    if vehicle_id is None:
        return {"ok": False, "error": "not_found", "message": "Vehicle not found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        if not _company_exists(cur, parsed):
            return {"ok": False, "error": "not_found", "message": "Company not found"}
        cur.execute(
            "SELECT status, branch_id::text FROM vehicles WHERE id = %s::uuid",
            (vehicle_id,),
        )
        vehicle = cur.fetchone()
        if vehicle is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found"}
        status, branch_id = vehicle
        if status != "active":
            return {
                "ok": False,
                "error": "invalid",
                "message": "An inactive vehicle cannot be linked to a company.",
            }
        cur.execute(
            """
            SELECT 1 FROM company_branches
            WHERE company_id = %s::uuid AND branch_id = %s::uuid
            """,
            (parsed, branch_id),
        )
        if cur.fetchone() is None:
            return {
                "ok": False,
                "error": "invalid",
                "message": "This vehicle is garaged in a city the company does not use.",
            }
        outcome = _write_company_vehicle(
            cur,
            """
            INSERT INTO company_vehicles (company_id, vehicle_id)
            VALUES (%s::uuid, %s::uuid)
            """,
            (parsed, vehicle_id),
            removing=False,
        )
        if isinstance(outcome, dict):
            return outcome
        return {"ok": True, "vehicles": _select_company_vehicles(cur, parsed, by_id)}

    return _owner_work(user_id, work)


def unlink_company_vehicle_row(cur, company_id, vehicle_id, by_id):
    """Delete one company_vehicles row. The vehicle and company rows stay."""
    if not _company_exists(cur, company_id):
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    cur.execute("SELECT 1 FROM vehicles WHERE id = %s::uuid", (vehicle_id,))
    if cur.fetchone() is None:
        return {"ok": False, "error": "not_found", "message": "Vehicle not found"}
    outcome = _write_company_vehicle(
        cur,
        """
        DELETE FROM company_vehicles
        WHERE company_id = %s::uuid AND vehicle_id = %s::uuid
        """,
        (company_id, vehicle_id),
        removing=True,
    )
    if isinstance(outcome, dict):
        return outcome
    if outcome != 1:
        return {
            "ok": False,
            "error": "not_found",
            "message": "This vehicle is not linked to the company.",
        }
    return {"ok": True, "vehicles": _select_company_vehicles(cur, company_id, by_id)}


def unlink_company_vehicle(user_id, company_id, vehicle_id):
    parsed_company = _parse_uuid(company_id)
    parsed_vehicle = _parse_uuid(vehicle_id)
    if parsed_company is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    if parsed_vehicle is None:
        return {"ok": False, "error": "not_found", "message": "Vehicle not found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        return unlink_company_vehicle_row(cur, parsed_company, parsed_vehicle, by_id)

    return _owner_work(user_id, work)


_CLIENT_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _client_record(row):
    return {
        "id": row[0],
        "full_name": row[1],
        "email": row[2],
        "phone": row[3],
        "role": row[4],
        "status": row[5],
    }


def _client_email(value):
    text = _clean_text(value)
    if text is False or not text:
        return None
    email = text.lower()
    if len(email) > 254 or _CLIENT_EMAIL.match(email) is None:
        return None
    return email


def _client_fields(payload):
    if not isinstance(payload, dict):
        return None, "Client details are not valid"
    if "role" in payload and payload.get("role") != "client":
        return None, "A client is created with the client role"
    if "status" in payload and payload.get("status") not in (None, "active"):
        return None, "A new client starts active"
    name = _clean_text(payload.get("full_name"))
    if name is False or not name:
        return None, "Full name is required"
    email = _client_email(payload.get("email"))
    if email is None:
        return None, "Enter a valid email address"
    if "phone" in payload and payload.get("phone") not in (None, ""):
        phone = _clean_text(payload.get("phone"))
        if phone is False:
            return None, "Client details are not valid"
    else:
        phone = None
    return {"full_name": name, "email": email, "phone": phone}, None


def create_client(user_id, payload):
    fields, error = _client_fields(payload or {})
    if error:
        return {"ok": False, "error": "invalid", "message": error}

    def work(cur):
        cur.execute(
            "SELECT 1 FROM users WHERE lower(email) = lower(%s)",
            (fields["email"],),
        )
        if cur.fetchone() is not None:
            return {
                "ok": False,
                "error": "duplicate",
                "message": "An account with this email already exists",
            }
        cur.execute(
            """
            INSERT INTO users (role, full_name, email, phone, status)
            VALUES ('client', %s, %s, %s, 'active')
            RETURNING id::text, full_name, email, phone, role, status
            """,
            (fields["full_name"], fields["email"], fields["phone"]),
        )
        return {"ok": True, "client": _client_record(cur.fetchone())}

    return _owner_work(user_id, work)


def _company_exists(cur, company_id):
    cur.execute("SELECT 1 FROM companies WHERE id = %s::uuid", (company_id,))
    return cur.fetchone() is not None


def list_company_clients(user_id, company_id):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}

    def work(cur):
        if not _company_exists(cur, parsed):
            return {"ok": False, "error": "not_found", "message": "Company not found"}
        cur.execute(
            """
            SELECT u.id::text, u.full_name, u.email, u.phone, u.role, u.status
            FROM user_company_links l
            JOIN users u ON u.id = l.user_id
            WHERE l.company_id = %s::uuid
            ORDER BY u.full_name, u.email
            """,
            (parsed,),
        )
        return {"ok": True, "clients": [_client_record(row) for row in cur.fetchall()]}

    return _owner_work(user_id, work)


def _find_client(cur, payload):
    if not isinstance(payload, dict):
        return None, {"ok": False, "error": "invalid", "message": "Choose a client to link"}
    if payload.get("user_id"):
        parsed = _parse_uuid(payload.get("user_id"))
        if parsed is None:
            return None, {"ok": False, "error": "not_found", "message": "Client not found"}
        cur.execute(
            """
            SELECT id::text, full_name, email, phone, role, status
            FROM users
            WHERE id = %s::uuid
            """,
            (parsed,),
        )
    elif payload.get("email"):
        email = _client_email(payload.get("email"))
        if email is None:
            return None, {"ok": False, "error": "invalid", "message": "Enter a valid email address"}
        cur.execute(
            """
            SELECT id::text, full_name, email, phone, role, status
            FROM users
            WHERE lower(email) = lower(%s)
            """,
            (email,),
        )
    else:
        return None, {"ok": False, "error": "invalid", "message": "Choose a client to link"}
    row = cur.fetchone()
    if row is None:
        return None, {"ok": False, "error": "not_found", "message": "Client not found"}
    client = _client_record(row)
    if client["role"] != "client":
        return None, {"ok": False, "error": "invalid", "message": "Only a client can be linked to a company"}
    return client, None


def link_company_client(user_id, company_id, payload):
    parsed = _parse_uuid(company_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}

    def work(cur):
        if not _company_exists(cur, parsed):
            return {"ok": False, "error": "not_found", "message": "Company not found"}
        client, error = _find_client(cur, payload)
        if error:
            return error
        cur.execute(
            """
            INSERT INTO user_company_links (user_id, company_id)
            VALUES (%s::uuid, %s::uuid)
            ON CONFLICT DO NOTHING
            RETURNING user_id
            """,
            (client["id"], parsed),
        )
        if cur.fetchone() is None:
            return {
                "ok": False,
                "error": "duplicate",
                "message": "This client is already linked to the company",
            }
        return {"ok": True, "client": client}

    return _owner_work(user_id, work)


def unlink_company_client(user_id, company_id, client_id):
    parsed_company = _parse_uuid(company_id)
    parsed_client = _parse_uuid(client_id)
    if parsed_company is None:
        return {"ok": False, "error": "not_found", "message": "Company not found"}
    if parsed_client is None:
        return {"ok": False, "error": "not_found", "message": "Client not found"}

    def work(cur):
        if not _company_exists(cur, parsed_company):
            return {"ok": False, "error": "not_found", "message": "Company not found"}
        cur.execute(
            """
            DELETE FROM user_company_links
            WHERE user_id = %s::uuid AND company_id = %s::uuid
            RETURNING user_id
            """,
            (parsed_client, parsed_company),
        )
        if cur.fetchone() is None:
            return {"ok": False, "error": "not_found", "message": "That client is not linked to this company"}
        cur.execute(
            """
            SELECT id::text, full_name, email, phone, role, status
            FROM users
            WHERE id = %s::uuid
            """,
            (parsed_client,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "Client not found"}
        return {"ok": True, "client": _client_record(row)}

    return _owner_work(user_id, work)


_DRIVER_SENSITIVE = {
    "user_id",
    "role",
    "status",
    "password",
    "password_hash",
    "google_sub",
    "legacy_source",
    "legacy_driver_id",
    "legacy_sqlite_id",
    "branch_inferred",
    "id",
}
_DRIVER_CREATE_KEYS = {
    "display_name",
    "phone",
    "license_number",
    "license_expiry",
    "primary_branch_code",
    "active",
}
_DRIVER_PATCH_KEYS = {
    "display_name",
    "phone",
    "license_number",
    "license_expiry",
    "active",
}


def _like_contains(value):
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _clean_date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return text


def _date_text(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _driver_shape(row, by_id, events=None, changes=None, documents=None, warnings=None):
    driver_id, name, phone, licence, expiry, active, primary_id, memberships, verification_status = row
    primary = by_id.get(primary_id)
    branches = []
    for branch_id in memberships or []:
        branch = by_id.get(branch_id)
        if branch is None:
            continue
        branches.append({
            "code": branch["code"],
            "name": branch["name"],
            "city": branch["city"],
            "primary": branch_id == primary_id,
        })
    branches.sort(key=lambda item: (not item["primary"], item["code"]))
    shape = {
        "id": driver_id,
        "display_name": name,
        "phone": phone,
        "license_number": licence,
        "license_expiry": _date_text(expiry),
        "active": bool(active),
        "verification_status": verification_status,
        "primary_branch": None if primary is None else {
            "code": primary["code"],
            "name": primary["name"],
            "city": primary["city"],
        },
        "branches": branches,
    }
    if events is not None:
        shape["verification_events"] = events
    if changes is not None:
        shape["active_changes"] = changes
    if documents is not None:
        shape["documents"] = documents
    if warnings is not None:
        shape["duplicate_warnings"] = warnings
    return shape


def _driver_form(payload, creating):
    if not isinstance(payload, dict):
        return None, "Driver details are not valid"
    if _DRIVER_SENSITIVE.intersection(payload):
        return None, "That field cannot be set from the driver directory."
    if not creating and {"primary_branch_code", "primary_branch_id"}.intersection(payload):
        return None, "Primary branch cannot be changed from the driver profile."
    allowed = _DRIVER_CREATE_KEYS if creating else _DRIVER_PATCH_KEYS
    if set(payload) - allowed:
        return None, "Driver details are not valid"
    if not creating and not payload:
        return None, "No driver details to update"
    fields = {}
    if creating or "display_name" in payload:
        name = _clean_text(payload.get("display_name"))
        if name is False or not name:
            return None, "Driver name is required"
        fields["display_name"] = name
    for key in ("phone", "license_number"):
        if key not in payload:
            continue
        value = _clean_text(payload.get(key))
        if value is False:
            return None, "Driver details are not valid"
        fields[key] = value
    if "license_expiry" in payload:
        expiry = _clean_date(payload.get("license_expiry"))
        if expiry is False:
            return None, "Enter a licence expiry as YYYY-MM-DD"
        fields["license_expiry"] = expiry
    if "active" in payload:
        if not isinstance(payload.get("active"), bool):
            return None, "Active must be true or false"
        fields["active"] = payload["active"]
    elif creating:
        fields["active"] = False
    if creating:
        code = payload.get("primary_branch_code")
        if not isinstance(code, str) or not code.strip():
            return None, "Choose Bengaluru or Hyderabad"
        fields["primary_branch_code"] = code.strip().upper()
    return fields, None


def _select_drivers(cur, driver_id=None, branch_id=None, active=None, name=None, verification_status=None):
    where = []
    params = []
    if driver_id is not None:
        where.append("d.id = %s::uuid")
        params.append(driver_id)
    if branch_id is not None:
        where.append("d.primary_branch_id = %s::uuid")
        params.append(branch_id)
    if active is not None:
        where.append("d.active = %s")
        params.append(active)
    if verification_status is not None:
        where.append("d.verification_status = %s")
        params.append(verification_status)
    if name:
        where.append("d.display_name ILIKE %s ESCAPE '\\'")
        params.append(_like_contains(name))
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    cur.execute(
        f"""
        SELECT d.id::text, d.display_name, d.phone, d.license_number,
               d.license_expiry, d.active, d.primary_branch_id::text,
               array_agg(db.branch_id::text ORDER BY db.branch_id),
               d.verification_status
        FROM drivers d
        JOIN driver_branches db ON db.driver_id = d.id
        {clause}
        GROUP BY d.id
        ORDER BY d.display_name, d.id
        """,
        params,
    )
    return cur.fetchall()


def _insert_driver_with_primary_branch(cur, fields, branch_id):
    # RETURNING would also enforce the driver read policy, which requires the
    # branch membership that this function inserts immediately afterwards.
    driver_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO drivers (
            id, primary_branch_id, display_name, phone, license_number, license_expiry, active
        )
        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s)
        """,
        (
            driver_id,
            branch_id,
            fields["display_name"],
            fields.get("phone"),
            fields.get("license_number"),
            fields.get("license_expiry"),
            fields["active"],
        ),
    )
    cur.execute(
        """
        INSERT INTO driver_branches (driver_id, branch_id)
        VALUES (%s::uuid, %s::uuid)
        """,
        (driver_id, branch_id),
    )
    return driver_id


def list_drivers(user_id, branch_code=None, active=None, name=None, verification_status=None):
    if verification_status not in (None, "unverified", "verified", "rejected"):
        return {
            "ok": False,
            "error": "invalid",
            "message": "Verification status must be unverified, verified, or rejected",
        }
    maps = _branch_maps()
    if maps is None:
        return None
    by_code, by_id = maps
    branch_id = None
    if branch_code:
        if not isinstance(branch_code, str):
            return {"ok": False, "error": "invalid", "message": "Choose Bengaluru or Hyderabad"}
        branch = by_code.get(branch_code.strip().upper())
        if branch is None:
            return {"ok": False, "error": "invalid", "message": "Choose Bengaluru or Hyderabad"}
        branch_id = branch["id"]
    cleaned_name = None
    if name:
        cleaned_name = _clean_text(name) or None
        if cleaned_name is False:
            return {"ok": False, "error": "invalid", "message": "Driver details are not valid"}

    def work(cur):
        rows = _select_drivers(
            cur,
            branch_id=branch_id,
            active=active,
            name=cleaned_name,
            verification_status=verification_status,
        )
        warnings = _duplicate_warnings_by_driver(cur)
        return {
            "ok": True,
            "drivers": [
                _driver_shape(row, by_id, warnings=warnings.get(row[0], []))
                for row in rows
            ],
        }

    return _owner_work(user_id, work)


def get_driver(user_id, driver_id):
    parsed = _parse_uuid(driver_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        return _driver_result(cur, parsed, by_id)

    return _owner_work(user_id, work)


def create_driver(user_id, payload):
    fields, error = _driver_form(payload or {}, creating=True)
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    maps = _branch_maps()
    if maps is None:
        return None
    by_code, by_id = maps
    branch = by_code.get(fields["primary_branch_code"])
    if branch is None:
        return {"ok": False, "error": "invalid", "message": "Choose Bengaluru or Hyderabad"}

    def work(cur):
        driver_id = _insert_driver_with_primary_branch(cur, fields, branch["id"])
        return _driver_result(cur, driver_id, by_id)

    return _owner_work(user_id, work)


def _timestamp_text(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _history_actor(actor_id, name, email):
    return {
        "actor_user_id": actor_id,
        "actor_name": name,
        "actor_email": email,
    }


def _driver_history(cur, driver_id):
    cur.execute(
        """
        SELECT e.id::text, e.event_kind, e.event_name, e.reason, e.from_status, e.to_status,
               e.active_after, e.actor_user_id::text, u.full_name, u.email, e.created_at
        FROM driver_verification_events e
        LEFT JOIN users u ON u.id = e.actor_user_id
        WHERE e.driver_id = %s::uuid
        ORDER BY e.created_at, e.id
        """,
        (driver_id,),
    )
    events = []
    for event_id, kind, name, reason, from_status, to_status, active_after, actor_id, actor_name, actor_email, created_at in cur.fetchall():
        event = {
            "id": event_id,
            "event_kind": kind,
            "event_name": name,
            "reason": reason,
            "from_status": from_status,
            "to_status": to_status,
            "active_after": active_after,
            "created_at": _timestamp_text(created_at),
        }
        event.update(_history_actor(actor_id, actor_name, actor_email))
        events.append(event)
    cur.execute(
        """
        SELECT c.id::text, c.verification_status, c.active_before, c.active_after,
               c.reason, c.actor_user_id::text, u.full_name, u.email, c.created_at
        FROM driver_active_changes c
        LEFT JOIN users u ON u.id = c.actor_user_id
        WHERE c.driver_id = %s::uuid
        ORDER BY c.created_at, c.id
        """,
        (driver_id,),
    )
    changes = []
    for change_id, status, before, after, reason, actor_id, actor_name, actor_email, created_at in cur.fetchall():
        change = {
            "id": change_id,
            "verification_status": status,
            "active_before": before,
            "active_after": after,
            "reason": reason,
            "created_at": _timestamp_text(created_at),
        }
        change.update(_history_actor(actor_id, actor_name, actor_email))
        changes.append(change)
    return events, changes


def _driver_result(cur, driver_id, by_id):
    rows = _select_drivers(cur, driver_id=driver_id)
    if not rows:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    events, changes = _driver_history(cur, driver_id)
    documents = _select_driver_documents(cur, driver_id)
    warnings = _duplicate_warnings_by_driver(cur, driver_id).get(driver_id, [])
    return {
        "ok": True,
        "driver": _driver_shape(rows[0], by_id, events, changes, documents, warnings),
    }


def _activation_refusal(status):
    if status == "unverified":
        return "This driver is unverified. Approve the driver before activation."
    if status == "rejected":
        return "This driver was rejected. Resubmit the driver before a new approval."
    return "Suspend or restore a verified driver with a reason."


def _driver_database_error(exc):
    message = getattr(getattr(exc, "diag", None), "message_primary", None)
    if not message:
        message = "Driver request could not be completed"
    if message == "Driver not found":
        return {"ok": False, "error": "not_found", "message": message}
    return {"ok": False, "error": "invalid", "message": message}


def _call_driver_function(cur, sql, params):
    import psycopg

    cur.execute("SAVEPOINT driver_verification")
    try:
        cur.execute(sql, params)
    except psycopg.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT driver_verification")
        return _driver_database_error(exc)
    cur.execute("RELEASE SAVEPOINT driver_verification")
    return None


def _clean_reason(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def update_driver(user_id, driver_id, payload):
    parsed = _parse_uuid(driver_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    fields, error = _driver_form(payload or {}, creating=False)
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps
    if "active" in fields:
        def refuse(cur):
            cur.execute(
                "SELECT verification_status FROM drivers WHERE id = %s::uuid",
                (parsed,),
            )
            found = cur.fetchone()
            if found is None:
                return {"ok": False, "error": "not_found", "message": "Driver not found"}
            return {"ok": False, "error": "invalid", "message": _activation_refusal(found[0])}

        return _owner_work(user_id, refuse)
    assignments = []
    params = []
    for column in ("display_name", "phone", "license_number", "license_expiry"):
        if column in fields:
            assignments.append(f"{column} = %s")
            params.append(fields[column])
    if not assignments:
        return {"ok": False, "error": "invalid", "message": "No driver details to update"}

    def work(cur):
        cur.execute("SELECT 1 FROM drivers WHERE id = %s::uuid", (parsed,))
        if cur.fetchone() is None:
            return {"ok": False, "error": "not_found", "message": "Driver not found"}
        cur.execute(
            f"UPDATE drivers SET {', '.join(assignments)} WHERE id = %s::uuid",
            (*params, parsed),
        )
        return _driver_result(cur, parsed, by_id)

    return _owner_work(user_id, work)


def review_driver(user_id, driver_id, payload):
    parsed = _parse_uuid(driver_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Review details are not valid"}
    decision = payload.get("decision")
    if decision not in ("verified", "rejected"):
        return {"ok": False, "error": "invalid", "message": "Review decision must be verified or rejected"}
    reason = _clean_reason(payload.get("reason"))
    if reason is None:
        return {"ok": False, "error": "invalid", "message": "A review reason is required"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        failed = _call_driver_function(
            cur,
            "SELECT review_driver(%s::uuid, %s, %s)",
            (parsed, decision, reason),
        )
        if failed:
            return failed
        return _driver_result(cur, parsed, by_id)

    return _owner_work(user_id, work)


def resubmit_driver(user_id, driver_id, payload):
    parsed = _parse_uuid(driver_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Resubmission details are not valid"}
    reason = _clean_reason(payload.get("reason"))
    if reason is None:
        return {"ok": False, "error": "invalid", "message": "A resubmission reason is required"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        failed = _call_driver_function(
            cur,
            "SELECT resubmit_driver(%s::uuid, %s)",
            (parsed, reason),
        )
        if failed:
            return failed
        return _driver_result(cur, parsed, by_id)

    return _owner_work(user_id, work)


def set_driver_active(user_id, driver_id, payload):
    parsed = _parse_uuid(driver_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    if not isinstance(payload, dict) or not isinstance(payload.get("active"), bool):
        return {"ok": False, "error": "invalid", "message": "Active must be true or false"}
    reason = _clean_reason(payload.get("reason"))
    if reason is None:
        return {"ok": False, "error": "invalid", "message": "A reason is required to suspend or restore a driver"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        failed = _call_driver_function(
            cur,
            "SELECT set_driver_active(%s::uuid, %s, %s)",
            (parsed, payload["active"], reason),
        )
        if failed:
            return failed
        return _driver_result(cur, parsed, by_id)

    return _owner_work(user_id, work)


def _other_driver(driver_id, name, phone, licence, status, active):
    return {
        "id": driver_id,
        "display_name": name,
        "phone": phone,
        "license_number": licence,
        "verification_status": status,
        "active": bool(active),
    }


def _duplicate_warning_rows(cur, driver_id=None):
    params = ()
    where = ""
    if driver_id is not None:
        where = "WHERE w.driver_id = %s::uuid OR w.other_driver_id = %s::uuid"
        params = (driver_id, driver_id)
    cur.execute(
        f"""
        SELECT w.match_kind, w.match_value,
               a.id::text, a.display_name, a.phone, a.license_number,
               a.verification_status, a.active,
               b.id::text, b.display_name, b.phone, b.license_number,
               b.verification_status, b.active
        FROM driver_duplicate_warnings w
        JOIN drivers a ON a.id = w.driver_id
        JOIN drivers b ON b.id = w.other_driver_id
        {where}
        ORDER BY w.match_kind, a.display_name, b.display_name, a.id, b.id
        """,
        params,
    )
    return cur.fetchall()


def _duplicate_indexes(cur, driver_id=None):
    by_driver = {}
    pairs = []
    for (
        kind, value,
        left_id, left_name, left_phone, left_licence, left_status, left_active,
        right_id, right_name, right_phone, right_licence, right_status, right_active,
    ) in _duplicate_warning_rows(cur, driver_id):
        left = _other_driver(left_id, left_name, left_phone, left_licence, left_status, left_active)
        right = _other_driver(right_id, right_name, right_phone, right_licence, right_status, right_active)
        pairs.append({
            "match_kind": kind,
            "match_value": value,
            "driver": left,
            "other_driver": right,
        })
        by_driver.setdefault(left_id, []).append({
            "match_kind": kind,
            "match_value": value,
            "other_driver": right,
        })
        by_driver.setdefault(right_id, []).append({
            "match_kind": kind,
            "match_value": value,
            "other_driver": left,
        })
    return pairs, by_driver


def _duplicate_warnings_by_driver(cur, driver_id=None):
    _, by_driver = _duplicate_indexes(cur, driver_id)
    return by_driver


def list_duplicate_warnings(user_id):
    def work(cur):
        pairs, _ = _duplicate_indexes(cur)
        return {"ok": True, "warnings": pairs}

    return _owner_work(user_id, work)


_DRIVER_DOCUMENT_SENSITIVE = {
    "id",
    "driver_id",
    "created_at",
    "file_path",
    "storage_path",
    "legacy_sqlite_id",
}
_DRIVER_DOCUMENT_FIELDS = {"doc_type", "doc_number", "expiry_date"}


def _driver_document_form(payload):
    if not isinstance(payload, dict):
        return None, "Document details are not valid."
    if _DRIVER_DOCUMENT_SENSITIVE.intersection(payload):
        return None, "That field cannot be set on a driver document."
    if set(payload) - _DRIVER_DOCUMENT_FIELDS:
        return None, "Document details are not valid."
    if not payload:
        return None, "No document details to update."
    fields = {}
    if "doc_type" in payload:
        doc_type = _clean_text(payload.get("doc_type"))
        if doc_type is False:
            return None, "Document details are not valid."
        if not doc_type:
            return None, "Document type is required."
        fields["doc_type"] = doc_type
    if "doc_number" in payload:
        doc_number = _clean_text(payload.get("doc_number"))
        if doc_number is False:
            return None, "Document details are not valid."
        if not doc_number:
            return None, "Document number is required."
        fields["doc_number"] = doc_number
    if "expiry_date" in payload:
        expiry = _clean_date(payload.get("expiry_date"))
        if expiry is False:
            return None, "Enter an expiry as YYYY-MM-DD."
        fields["expiry_date"] = expiry
    if not fields:
        return None, "No document details to update."
    return fields, None


def _driver_document_shape(row):
    document_id, doc_type, doc_number, expiry = row
    return {
        "id": document_id,
        "doc_type": doc_type,
        "doc_number": doc_number,
        "expiry_date": _date_text(expiry),
    }


def _select_driver_documents(cur, driver_id):
    cur.execute(
        """
        SELECT id::text, doc_type, doc_number, expiry_date
        FROM driver_documents
        WHERE driver_id = %s::uuid
        ORDER BY doc_type, expiry_date NULLS LAST, id
        """,
        (driver_id,),
    )
    return [_driver_document_shape(row) for row in cur.fetchall()]


def _visible_driver(cur, driver_id):
    cur.execute(
        """
        SELECT 1
        FROM drivers d
        WHERE d.id = %s::uuid
          AND EXISTS (
              SELECT 1 FROM driver_branches db WHERE db.driver_id = d.id
          )
        """,
        (driver_id,),
    )
    return cur.fetchone() is not None


def _driver_document_write(cur, sql, params):
    import psycopg

    cur.execute("SAVEPOINT driver_document_write")
    try:
        cur.execute(sql, params)
    except psycopg.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT driver_document_write")
        if getattr(exc, "sqlstate", None) == "42501":
            return {"ok": False, "error": "not_found", "message": "Driver not found"}
        if isinstance(exc, psycopg.errors.CheckViolation):
            return {"ok": False, "error": "invalid", "message": "Document type and number are required."}
        if isinstance(exc, psycopg.errors.ForeignKeyViolation):
            return {"ok": False, "error": "not_found", "message": "Driver not found"}
        return {"ok": False, "error": "invalid", "message": "Document details are not valid."}
    affected = cur.rowcount
    cur.execute("RELEASE SAVEPOINT driver_document_write")
    return affected


def list_driver_documents(user_id, driver_id):
    parsed = _parse_uuid(driver_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}

    def work(cur):
        if not _visible_driver(cur, parsed):
            return {"ok": False, "error": "not_found", "message": "Driver not found"}
        return {"ok": True, "documents": _select_driver_documents(cur, parsed)}

    return _owner_work(user_id, work)


def add_driver_document(user_id, driver_id, payload):
    parsed = _parse_uuid(driver_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Driver not found"}
    fields, error = _driver_document_form(payload or {})
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    if "doc_type" not in fields:
        return {"ok": False, "error": "invalid", "message": "Document type is required."}
    if "doc_number" not in fields:
        return {"ok": False, "error": "invalid", "message": "Document number is required."}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps
    document_id = str(uuid.uuid4())

    def work(cur):
        if not _visible_driver(cur, parsed):
            return {"ok": False, "error": "not_found", "message": "Driver not found"}
        outcome = _driver_document_write(
            cur,
            """
            INSERT INTO driver_documents (id, driver_id, doc_type, doc_number, expiry_date)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s)
            """,
            (
                document_id,
                parsed,
                fields["doc_type"],
                fields["doc_number"],
                fields.get("expiry_date"),
            ),
        )
        if isinstance(outcome, dict):
            return outcome
        return _driver_result(cur, parsed, by_id)

    return _owner_work(user_id, work)


def update_driver_document(user_id, driver_id, document_id, payload):
    parsed_driver = _parse_uuid(driver_id)
    parsed_document = _parse_uuid(document_id)
    if parsed_driver is None or parsed_document is None:
        return {"ok": False, "error": "not_found", "message": "Document not found"}
    fields, error = _driver_document_form(payload or {})
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps
    assignments = []
    params = []
    for column in ("doc_type", "doc_number", "expiry_date"):
        if column in fields:
            assignments.append(f"{column} = %s")
            params.append(fields[column])

    def work(cur):
        if not _visible_driver(cur, parsed_driver):
            return {"ok": False, "error": "not_found", "message": "Driver not found"}
        outcome = _driver_document_write(
            cur,
            "UPDATE driver_documents SET "
            + ", ".join(assignments)
            + " WHERE id = %s::uuid AND driver_id = %s::uuid",
            (*params, parsed_document, parsed_driver),
        )
        if isinstance(outcome, dict):
            return outcome
        if outcome != 1:
            return {"ok": False, "error": "not_found", "message": "Document not found"}
        return _driver_result(cur, parsed_driver, by_id)

    return _owner_work(user_id, work)


def delete_driver_document(user_id, driver_id, document_id):
    parsed_driver = _parse_uuid(driver_id)
    parsed_document = _parse_uuid(document_id)
    if parsed_driver is None or parsed_document is None:
        return {"ok": False, "error": "not_found", "message": "Document not found"}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        if not _visible_driver(cur, parsed_driver):
            return {"ok": False, "error": "not_found", "message": "Driver not found"}
        outcome = _driver_document_write(
            cur,
            """
            DELETE FROM driver_documents
            WHERE id = %s::uuid AND driver_id = %s::uuid
            """,
            (parsed_document, parsed_driver),
        )
        if isinstance(outcome, dict):
            return outcome
        if outcome != 1:
            return {"ok": False, "error": "not_found", "message": "Document not found"}
        return _driver_result(cur, parsed_driver, by_id)

    return _owner_work(user_id, work)


_VEHICLE_STATUSES = ("active", "inactive")
_VEHICLE_SENSITIVE = {
    "id",
    "user_id",
    "role",
    "identity_status",
    "legacy_source",
    "legacy_id",
    "branch_inferred",
    "branch_id",
    "legacy_sqlite_id",
    "password",
    "password_hash",
    "google_sub",
    "file_path",
    "storage_path",
    "active",
}
_VEHICLE_FIELDS = {
    "registration_number",
    "model",
    "capacity",
    "fuel_type",
    "is_ev",
    "status",
    "branch_code",
    "usual_driver_id",
}
_DOCUMENT_SENSITIVE = {
    "id",
    "vehicle_id",
    "legacy_sqlite_id",
    "file_path",
    "storage_path",
}
_DOCUMENT_FIELDS = {"doc_type", "doc_number", "expiry_date"}


def _clean_registration(value):
    text = _clean_text(value)
    if text is False:
        return False
    if text is None:
        return None
    return text.upper()


def _clean_capacity(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    if value < 1 or value > 80:
        return False
    return value


def _clean_status(value):
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    if text not in _VEHICLE_STATUSES:
        return False
    return text


def _clean_driver_id(value):
    if value is None or value == "":
        return None
    return _parse_uuid(value)


def _vehicle_form(payload, creating):
    if not isinstance(payload, dict):
        return None, "Vehicle details are not valid."
    if _VEHICLE_SENSITIVE.intersection(payload):
        return None, "That field cannot be set from the vehicle directory."
    if set(payload) - _VEHICLE_FIELDS:
        return None, "Vehicle details are not valid."
    if not creating and not payload:
        return None, "No vehicle details to update."
    fields = {}
    if creating or "registration_number" in payload:
        registration = _clean_registration(payload.get("registration_number"))
        if registration is False:
            return None, "Vehicle details are not valid."
        if not registration:
            return None, "Registration number is required."
        fields["registration_number"] = registration
    for key in ("model", "fuel_type"):
        if key not in payload:
            continue
        value = _clean_text(payload.get(key))
        if value is False:
            return None, "Vehicle details are not valid."
        fields[key] = value
    if "capacity" in payload:
        capacity = _clean_capacity(payload.get("capacity"))
        if capacity is False:
            return None, "Capacity must be a whole number from 1 to 80."
        fields["capacity"] = capacity
    if "is_ev" in payload:
        if not isinstance(payload.get("is_ev"), bool):
            return None, "Electric must be true or false."
        fields["is_ev"] = payload["is_ev"]
    elif creating:
        fields["is_ev"] = False
    if "status" in payload:
        status = _clean_status(payload.get("status"))
        if status is False:
            return None, "Status must be active or inactive."
        fields["status"] = status
    elif creating:
        fields["status"] = "active"
    if creating or "branch_code" in payload:
        code = payload.get("branch_code")
        if not isinstance(code, str) or not code.strip():
            return None, "Choose Bengaluru or Hyderabad."
        fields["branch_code"] = code.strip().upper()
    if "usual_driver_id" in payload:
        driver_id = _clean_driver_id(payload.get("usual_driver_id"))
        if payload.get("usual_driver_id") not in (None, "") and driver_id is None:
            return None, "Choose a driver from the directory."
        fields["usual_driver_id"] = driver_id
    return fields, None


def _document_form(payload):
    if not isinstance(payload, dict):
        return None, "Document details are not valid."
    if _DOCUMENT_SENSITIVE.intersection(payload):
        return None, "That field cannot be set from the vehicle directory."
    if set(payload) - _DOCUMENT_FIELDS:
        return None, "Document details are not valid."
    if not payload:
        return None, "No document details to update."
    fields = {}
    if "doc_type" in payload:
        doc_type = _clean_text(payload.get("doc_type"))
        if doc_type is False:
            return None, "Document details are not valid."
        if not doc_type:
            return None, "Document type is required."
        fields["doc_type"] = doc_type
    if "doc_number" in payload:
        doc_number = _clean_text(payload.get("doc_number"))
        if doc_number is False:
            return None, "Document details are not valid."
        if not doc_number:
            return None, "Document number is required."
        fields["doc_number"] = doc_number
    if "expiry_date" in payload:
        expiry = _clean_date(payload.get("expiry_date"))
        if expiry is False:
            return None, "Enter an expiry as YYYY-MM-DD."
        fields["expiry_date"] = expiry
    if not fields:
        return None, "No document details to update."
    return fields, None


def _vehicle_shape(row, by_id, documents=None):
    (
        vehicle_id,
        registration,
        model,
        capacity,
        fuel_type,
        is_ev,
        status,
        branch_id,
        driver_id,
        driver_name,
        document_count,
    ) = row
    branch = by_id.get(branch_id)
    usual = None
    if driver_id:
        usual = {"id": driver_id, "display_name": driver_name}
    shaped = {
        "id": vehicle_id,
        "registration_number": registration,
        "model": model,
        "capacity": capacity,
        "fuel_type": fuel_type,
        "is_ev": bool(is_ev),
        "status": status,
        "branch": None if branch is None else {
            "code": branch["code"],
            "name": branch["name"],
            "city": branch["city"],
        },
        "usual_driver": usual,
        "document_count": int(document_count or 0),
    }
    if documents is not None:
        shaped["documents"] = documents
    return shaped


def _document_shape(row):
    document_id, doc_type, doc_number, expiry = row
    return {
        "id": document_id,
        "doc_type": doc_type,
        "doc_number": doc_number,
        "expiry_date": _date_text(expiry),
    }


def _select_documents(cur, vehicle_id):
    cur.execute(
        """
        SELECT id::text, doc_type, doc_number, expiry_date
        FROM vehicle_documents
        WHERE vehicle_id = %s::uuid
        ORDER BY doc_type, expiry_date NULLS LAST, id
        """,
        (vehicle_id,),
    )
    return [_document_shape(row) for row in cur.fetchall()]


def _select_vehicles(cur, vehicle_id=None, branch_id=None, status=None, registration=None):
    where = []
    params = []
    if vehicle_id is not None:
        where.append("v.id = %s::uuid")
        params.append(vehicle_id)
    if branch_id is not None:
        where.append("v.branch_id = %s::uuid")
        params.append(branch_id)
    if status is not None:
        where.append("v.status = %s")
        params.append(status)
    if registration:
        where.append("v.registration_number ILIKE %s ESCAPE '\\'")
        params.append(_like_contains(registration))
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    cur.execute(
        f"""
        SELECT v.id::text, v.registration_number, v.model, v.capacity, v.fuel_type,
               v.is_ev, v.status, v.branch_id::text, d.id::text, d.display_name,
               (SELECT count(*) FROM vehicle_documents vd WHERE vd.vehicle_id = v.id)
        FROM vehicles v
        LEFT JOIN drivers d ON d.id = v.usual_driver_id
        {clause}
        ORDER BY v.registration_number NULLS LAST, v.id
        """,
        params,
    )
    return cur.fetchall()


def _load_vehicle(cur, vehicle_id, by_id):
    rows = _select_vehicles(cur, vehicle_id=vehicle_id)
    if not rows:
        return None
    return _vehicle_shape(rows[0], by_id, _select_documents(cur, vehicle_id))


def _guarded_vehicle_write(cur, sql, params):
    """Keep a constraint failure inside this transaction and return a directory error."""
    import psycopg

    cur.execute("SAVEPOINT vehicle_write")
    try:
        cur.execute(sql, params)
    except psycopg.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT vehicle_write")
        if isinstance(exc, psycopg.errors.UniqueViolation):
            return {
                "ok": False,
                "error": "duplicate",
                "message": "This registration number is already in the directory.",
            }
        if isinstance(exc, psycopg.errors.ForeignKeyViolation):
            return {
                "ok": False,
                "error": "invalid",
                "message": "Choose a driver from the directory.",
            }
        if isinstance(exc, psycopg.errors.CheckViolation):
            return {"ok": False, "error": "invalid", "message": "Vehicle details are not valid."}
        if isinstance(exc, psycopg.errors.RaiseException):
            return {
                "ok": False,
                "error": "in_use",
                "message": "This vehicle stays in its current city because a company allocation or an assignment still uses it.",
            }
        raise
    cur.execute("RELEASE SAVEPOINT vehicle_write")
    return None


def _require_visible_driver(cur, driver_id):
    if driver_id is None:
        return None
    cur.execute("SELECT 1 FROM drivers WHERE id = %s::uuid", (driver_id,))
    if cur.fetchone() is None:
        return {"ok": False, "error": "invalid", "message": "Choose a driver from the directory."}
    return None


def list_vehicles(user_id, branch_code=None, status=None, registration=None):
    maps = _branch_maps()
    if maps is None:
        return None
    by_code, by_id = maps
    branch_id = None
    if branch_code:
        if not isinstance(branch_code, str):
            return {"ok": False, "error": "invalid", "message": "Choose Bengaluru or Hyderabad."}
        branch = by_code.get(branch_code.strip().upper())
        if branch is None:
            return {"ok": False, "error": "invalid", "message": "Choose Bengaluru or Hyderabad."}
        branch_id = branch["id"]
    if status is not None and status not in _VEHICLE_STATUSES:
        return {"ok": False, "error": "invalid", "message": "Status must be active or inactive."}
    cleaned = None
    if registration:
        cleaned = _clean_registration(registration)
        if cleaned is False:
            return {"ok": False, "error": "invalid", "message": "Vehicle details are not valid."}

    def work(cur):
        rows = _select_vehicles(cur, branch_id=branch_id, status=status, registration=cleaned)
        return {"ok": True, "vehicles": [_vehicle_shape(row, by_id) for row in rows]}

    return _owner_work(user_id, work)


def get_vehicle(user_id, vehicle_id):
    parsed = _parse_uuid(vehicle_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        vehicle = _load_vehicle(cur, parsed, by_id)
        if vehicle is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
        return {"ok": True, "vehicle": vehicle}

    return _owner_work(user_id, work)


def create_vehicle(user_id, payload):
    fields, error = _vehicle_form(payload or {}, creating=True)
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    maps = _branch_maps()
    if maps is None:
        return None
    by_code, by_id = maps
    branch = by_code.get(fields["branch_code"])
    if branch is None:
        return {"ok": False, "error": "invalid", "message": "Choose Bengaluru or Hyderabad."}
    columns = ["id", "branch_id", "registration_number", "status", "is_ev"]
    vehicle_id = str(uuid.uuid4())
    params = [
        vehicle_id,
        branch["id"],
        fields["registration_number"],
        fields["status"],
        fields["is_ev"],
    ]
    placeholders = ["%s::uuid", "%s::uuid", "%s", "%s", "%s"]
    for column in ("model", "capacity", "fuel_type"):
        if column in fields:
            columns.append(column)
            placeholders.append("%s")
            params.append(fields[column])
    if "usual_driver_id" in fields:
        columns.append("usual_driver_id")
        placeholders.append("%s::uuid")
        params.append(fields["usual_driver_id"])
    sql = (
        f"INSERT INTO vehicles ({', '.join(columns)}) "
        f"VALUES ({', '.join(placeholders)})"
    )

    def work(cur):
        denied = _require_visible_driver(cur, fields.get("usual_driver_id"))
        if denied:
            return denied
        failed = _guarded_vehicle_write(cur, sql, params)
        if failed:
            return failed
        vehicle = _load_vehicle(cur, vehicle_id, by_id)
        if vehicle is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
        return {"ok": True, "vehicle": vehicle}

    return _owner_work(user_id, work)


def update_vehicle(user_id, vehicle_id, payload):
    parsed = _parse_uuid(vehicle_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
    fields, error = _vehicle_form(payload or {}, creating=False)
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    maps = _branch_maps()
    if maps is None:
        return None
    by_code, by_id = maps
    assignments = []
    params = []
    for column in (
        "registration_number",
        "model",
        "capacity",
        "fuel_type",
        "is_ev",
        "status",
        "usual_driver_id",
    ):
        if column not in fields:
            continue
        cast = "::uuid" if column == "usual_driver_id" else ""
        assignments.append(f"{column} = %s{cast}")
        params.append(fields[column])
    if "branch_code" in fields:
        branch = by_code.get(fields["branch_code"])
        if branch is None:
            return {"ok": False, "error": "invalid", "message": "Choose Bengaluru or Hyderabad."}
        assignments.append("branch_id = %s::uuid")
        params.append(branch["id"])
    if not assignments:
        return {"ok": False, "error": "invalid", "message": "No vehicle details to update."}

    def work(cur):
        cur.execute("SELECT 1 FROM vehicles WHERE id = %s::uuid", (parsed,))
        if cur.fetchone() is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
        if "usual_driver_id" in fields:
            denied = _require_visible_driver(cur, fields.get("usual_driver_id"))
            if denied:
                return denied
        failed = _guarded_vehicle_write(
            cur,
            f"UPDATE vehicles SET {', '.join(assignments)} WHERE id = %s::uuid",
            (*params, parsed),
        )
        if failed:
            return failed
        vehicle = _load_vehicle(cur, parsed, by_id)
        if vehicle is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
        return {"ok": True, "vehicle": vehicle}

    return _owner_work(user_id, work)


def add_vehicle_document(user_id, vehicle_id, payload):
    parsed = _parse_uuid(vehicle_id)
    if parsed is None:
        return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
    fields, error = _document_form(payload or {})
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    if "doc_type" not in fields:
        return {"ok": False, "error": "invalid", "message": "Document type is required."}
    if "doc_number" not in fields:
        return {"ok": False, "error": "invalid", "message": "Document number is required."}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps
    document_id = str(uuid.uuid4())

    def work(cur):
        cur.execute("SELECT 1 FROM vehicles WHERE id = %s::uuid", (parsed,))
        if cur.fetchone() is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
        cur.execute(
            """
            INSERT INTO vehicle_documents (id, vehicle_id, doc_type, doc_number, expiry_date)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s)
            """,
            (
                document_id,
                parsed,
                fields["doc_type"],
                fields["doc_number"],
                fields.get("expiry_date"),
            ),
        )
        vehicle = _load_vehicle(cur, parsed, by_id)
        if vehicle is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
        return {"ok": True, "vehicle": vehicle}

    return _owner_work(user_id, work)


def update_vehicle_document(user_id, vehicle_id, document_id, payload):
    parsed_vehicle = _parse_uuid(vehicle_id)
    parsed_document = _parse_uuid(document_id)
    if parsed_vehicle is None or parsed_document is None:
        return {"ok": False, "error": "not_found", "message": "Document not found."}
    fields, error = _document_form(payload or {})
    if error:
        return {"ok": False, "error": "invalid", "message": error}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps
    assignments = []
    params = []
    for column in ("doc_type", "doc_number", "expiry_date"):
        if column in fields:
            assignments.append(f"{column} = %s")
            params.append(fields[column])

    def work(cur):
        cur.execute(
            "UPDATE vehicle_documents SET "
            + ", ".join(assignments)
            + " WHERE id = %s::uuid AND vehicle_id = %s::uuid",
            (*params, parsed_document, parsed_vehicle),
        )
        if cur.rowcount != 1:
            return {"ok": False, "error": "not_found", "message": "Document not found."}
        vehicle = _load_vehicle(cur, parsed_vehicle, by_id)
        if vehicle is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
        return {"ok": True, "vehicle": vehicle}

    return _owner_work(user_id, work)


def delete_vehicle_document(user_id, vehicle_id, document_id):
    parsed_vehicle = _parse_uuid(vehicle_id)
    parsed_document = _parse_uuid(document_id)
    if parsed_vehicle is None or parsed_document is None:
        return {"ok": False, "error": "not_found", "message": "Document not found."}
    maps = _branch_maps()
    if maps is None:
        return None
    _, by_id = maps

    def work(cur):
        cur.execute(
            """
            DELETE FROM vehicle_documents
            WHERE id = %s::uuid AND vehicle_id = %s::uuid
            """,
            (parsed_document, parsed_vehicle),
        )
        if cur.rowcount != 1:
            return {"ok": False, "error": "not_found", "message": "Document not found."}
        vehicle = _load_vehicle(cur, parsed_vehicle, by_id)
        if vehicle is None:
            return {"ok": False, "error": "not_found", "message": "Vehicle not found."}
        return {"ok": True, "vehicle": vehicle}

    return _owner_work(user_id, work)
