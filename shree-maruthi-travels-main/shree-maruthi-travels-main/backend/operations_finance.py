"""PostgreSQL financial management for the supervisor portal.

Invoices, payments, driver payouts, expenses, company settlements and
dashboard aggregates. Uses existing financial tables and RLS. Does not
touch rac_data.json, SQLite, or RAC routes.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import dev_postgres as pg

_PAYMENT_METHODS = ("cash", "neft", "rtgs", "upi", "cheque", "card", "other")
_EXPENSE_STATUSES = ("recorded", "approved", "paid", "cancelled")
_PAYOUT_STATUSES = ("pending", "paid", "cancelled")
_MONEY = Decimal("0.01")

# Bank details for authenticated print only. Not served on public routes.
_BANK_DETAILS = {
    "bank": "BANK OF BARODA",
    "account_name": "SHREE MARUTHI TRAVELS",
    "account_no": "07640200003590",
    "ifsc": "BARB0JAYANA",
    "account_type": "Current",
    "branch": "JAYANAGAR BRANCH, BENGALURU 560011",
}


def finance_schema_ready(cur=None):
    def work(cursor):
        cursor.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = 'invoices'
                      AND a.attname = 'due_date' AND a.attnum > 0 AND NOT a.attisdropped
                ),
                EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = 'payments'
                      AND a.attname = 'reversed_at' AND a.attnum > 0 AND NOT a.attisdropped
                ),
                to_regclass('public.expenses') IS NOT NULL,
                EXISTS (
                    SELECT 1 FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = 'one_active_payout_per_booking'
                )
            """
        )
        due, rev, expenses, payout_uq = cursor.fetchone()
        return bool(due and rev and expenses and payout_uq)

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


def _schema_or_unavailable(cur):
    if finance_schema_ready(cur):
        return None
    return {
        "ok": False,
        "error": "unavailable",
        "message": "Financial tables need migration 009 on this database.",
    }


def _money(value, *, allow_zero=False):
    if value is None or value is False:
        return False
    if isinstance(value, bool):
        return False
    try:
        if isinstance(value, Decimal):
            amount = value
        elif isinstance(value, int):
            amount = Decimal(value)
        elif isinstance(value, float):
            amount = Decimal(str(value))
        elif isinstance(value, str):
            text = value.strip().replace(",", "")
            if not text:
                return False
            amount = Decimal(text)
        else:
            return False
    except (InvalidOperation, ValueError):
        return False
    amount = amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
    if allow_zero:
        if amount < 0 or amount > Decimal("9999999999.99"):
            return False
    elif amount <= 0 or amount > Decimal("9999999999.99"):
        return False
    return amount


def _date(value, *, required=False):
    if value in (None, ""):
        return None if not required else False
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    cleaned = pg._clean_date(value)
    if cleaned is False or cleaned is None:
        return False
    return cleaned


def _text(value, *, required=False, limit=500):
    if value is None:
        return None if not required else False
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return None if not required else False
    if len(text) > limit:
        return False
    return text


def _branch_directory():
    """Branch codes/ids via smt_app directory. Owner/staff roles cannot SELECT branches."""
    maps = pg._branch_maps()
    if maps is None:
        return None
    _by_code, by_id = maps
    return by_id


def _branch_code_for(branch_id, directory=None):
    directory = directory if directory is not None else _branch_directory()
    if directory is None:
        return None
    row = directory.get(str(branch_id))
    if row is None:
        return None
    return row.get("code")


def _finance_error(exc):
    diag = getattr(exc, "diag", None)
    constraint = getattr(diag, "constraint_name", None) or ""
    primary = getattr(diag, "message_primary", None) or ""
    sqlstate = getattr(exc, "sqlstate", None) or getattr(diag, "sqlstate", None) or ""
    if sqlstate == "42501":
        primary_l = primary.lower()
        # Match real branch-policy denials only. Table names such as branches
        # or driver_branches must not become authorization messages.
        if (
            "staff_can_branch" in primary_l
            or primary_l.startswith("you cannot use this branch")
            or "permission denied for function staff_can_branch" in primary_l
        ):
            return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
        print(
            "[WARN] Finance privilege error: %s"
            % ((primary or "permission denied")[:160],)
        )
        return {
            "ok": False,
            "error": "unavailable",
            "message": "The local finance register rejected this change.",
        }
    if constraint in ("invoices_number_uq",):
        return {
            "ok": False,
            "error": "conflict",
            "message": "That invoice number is already used.",
        }
    if constraint in ("one_invoice_line_per_booking",):
        return {
            "ok": False,
            "error": "conflict",
            "message": "That duty is already on an invoice.",
        }
    if constraint in ("payments_import_key_uq",):
        return {
            "ok": False,
            "error": "conflict",
            "message": "That payment import key was already recorded.",
        }
    if constraint in ("payments_reference_uq",):
        return {
            "ok": False,
            "error": "conflict",
            "message": "That payment reference is already used on this invoice.",
        }
    if constraint in ("one_active_payout_per_booking",):
        return {
            "ok": False,
            "error": "conflict",
            "message": "That duty already has an active driver payout.",
        }
    if "Payments would exceed" in primary:
        return {
            "ok": False,
            "error": "conflict",
            "message": "Payment would exceed the invoice balance.",
        }
    if "Invoice line company must match" in primary:
        return {
            "ok": False,
            "error": "invalid",
            "message": "Invoice company must match the booking company.",
        }
    return {"ok": False, "error": "invalid", "message": "Financial change could not be saved."}


def _audit(cur, user_id, branch_id, action, entity_name, entity_id, summary):
    cur.execute(
        """
        INSERT INTO audit_logs (actor_user_id, branch_id, action, entity_name, entity_id, summary)
        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
        """,
        (user_id, branch_id, action, entity_name, str(entity_id), summary),
    )


def _can_branch(cur, branch_id):
    cur.execute("SELECT staff_can_branch(%s::uuid)", (branch_id,))
    return bool(cur.fetchone()[0])


def _as_date(value):
    if value in (None, "", False):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def _invoice_status(row):
    voided_at = row.get("voided_at")
    issued_at = row.get("issued_at")
    due_date = _as_date(row.get("due_date"))
    total = Decimal(str(row.get("total_amount") or 0))
    paid = Decimal(str(row.get("paid_amount") or 0))
    outstanding = Decimal(str(row.get("outstanding_amount") or 0))
    if voided_at:
        return "void"
    if not issued_at:
        return "draft"
    if total > 0 and outstanding <= 0:
        return "paid"
    if paid > 0 and outstanding > 0:
        return "partially_paid"
    if due_date is not None and outstanding > 0 and due_date < date.today():
        return "overdue"
    return "issued"


def _select_invoice(cur, invoice_id, branch_directory=None):
    if branch_directory is None:
        branch_directory = _branch_directory()
    cur.execute(
        """
        SELECT i.id::text, i.branch_id::text, i.company_id::text, i.currency,
               i.invoice_number, i.period_start, i.period_end, i.issued_at,
               i.due_date, i.voided_at, i.void_reason, i.notes, i.created_at,
               c.name AS company_name,
               COALESCE(bal.total_amount, 0), COALESCE(bal.paid_amount, 0),
               COALESCE(bal.outstanding_amount, 0)
        FROM invoices i
        JOIN companies c ON c.id = i.company_id
        LEFT JOIN invoice_balances bal ON bal.invoice_id = i.id
        WHERE i.id = %s::uuid
        """,
        (invoice_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    shape = {
        "id": row[0],
        "branch_id": row[1],
        "company_id": row[2],
        "currency": row[3],
        "invoice_number": row[4],
        "period_start": pg._booking_value(row[5]),
        "period_end": pg._booking_value(row[6]),
        "issued_at": pg._booking_value(row[7]),
        "due_date": pg._booking_value(row[8]),
        "voided_at": pg._booking_value(row[9]),
        "void_reason": row[10],
        "notes": row[11],
        "created_at": pg._booking_value(row[12]),
        "company_name": row[13],
        "branch_code": _branch_code_for(row[1], branch_directory),
        "total_amount": str(row[14]),
        "paid_amount": str(row[15]),
        "outstanding_amount": str(row[16]),
    }
    shape["status"] = _invoice_status(shape)
    return shape


def _select_lines(cur, invoice_id):
    cur.execute(
        """
        SELECT l.id::text, l.invoice_id::text, l.booking_id::text, l.description, l.amount,
               b.source_booking_id, b.trip_date, b.status AS booking_status
        FROM invoice_lines l
        LEFT JOIN bookings b ON b.id = l.booking_id
        WHERE l.invoice_id = %s::uuid
        ORDER BY l.description, l.id
        """,
        (invoice_id,),
    )
    rows = []
    for row in cur.fetchall():
        rows.append(
            {
                "id": row[0],
                "invoice_id": row[1],
                "booking_id": row[2],
                "description": row[3],
                "amount": str(row[4]),
                "source_booking_id": row[5],
                "trip_date": pg._booking_value(row[6]),
                "booking_status": row[7],
            }
        )
    return rows


def _select_payments(cur, invoice_id):
    cur.execute(
        """
        SELECT id::text, invoice_id::text, currency, amount, paid_on, method,
               reference, import_key, reversed_at, reversal_reason
        FROM payments
        WHERE invoice_id = %s::uuid
        ORDER BY paid_on, id
        """,
        (invoice_id,),
    )
    rows = []
    for row in cur.fetchall():
        rows.append(
            {
                "id": row[0],
                "invoice_id": row[1],
                "currency": row[2],
                "amount": str(row[3]),
                "paid_on": pg._booking_value(row[4]),
                "method": row[5],
                "reference": row[6],
                "import_key": row[7],
                "reversed_at": pg._booking_value(row[8]),
                "reversal_reason": row[9],
                "active": row[8] is None,
            }
        )
    return rows


def _invoice_detail(cur, invoice_id, branch_directory=None):
    invoice = _select_invoice(cur, invoice_id, branch_directory=branch_directory)
    if invoice is None:
        return None
    return {
        "invoice": invoice,
        "lines": _select_lines(cur, invoice_id),
        "payments": _select_payments(cur, invoice_id),
    }


def _next_invoice_number(cur, branch_code):
    prefix = "SMT-%s-%s-" % ((branch_code or "XX").upper(), date.today().strftime("%Y%m"))
    cur.execute(
        """
        SELECT invoice_number FROM invoices
        WHERE invoice_number LIKE %s
        ORDER BY invoice_number DESC
        LIMIT 1
        FOR UPDATE
        """,
        (prefix + "%",),
    )
    row = cur.fetchone()
    seq = 1
    if row and row[0]:
        tail = row[0][len(prefix) :]
        if tail.isdigit():
            seq = int(tail) + 1
    return "%s%04d" % (prefix, seq)


def bank_details(user_id):
    def work(cur):
        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        return {"ok": True, "bank": dict(_BANK_DETAILS)}

    return pg._actor_work(user_id, work)


def list_invoices(user_id, branch_id=None, company_id=None, status=None, search=None):
    branch_directory = _branch_directory()

    def work(cur):
        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        clauses = ["TRUE"]
        params = []
        if branch_id:
            clauses.append("i.branch_id = %s::uuid")
            params.append(branch_id)
        if company_id:
            clauses.append("i.company_id = %s::uuid")
            params.append(company_id)
        if search:
            clauses.append(
                "(i.invoice_number ILIKE %s OR c.name ILIKE %s)"
            )
            like = "%" + search + "%"
            params.extend([like, like])
        cur.execute(
            """
            SELECT i.id::text
            FROM invoices i
            JOIN companies c ON c.id = i.company_id
            WHERE """
            + " AND ".join(clauses)
            + """
            ORDER BY COALESCE(i.issued_at, i.created_at) DESC, i.invoice_number DESC
            LIMIT 200
            """,
            params,
        )
        invoices = []
        for (invoice_id,) in cur.fetchall():
            item = _select_invoice(cur, invoice_id, branch_directory=branch_directory)
            if item is None:
                continue
            if status and item["status"] != status:
                continue
            invoices.append(item)
        return {"ok": True, "invoices": invoices}

    return pg._actor_work(user_id, work)


def get_invoice(user_id, invoice_id):
    invoice_id = pg._parse_uuid(invoice_id)
    if invoice_id is None:
        return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
    branch_directory = _branch_directory()

    def work(cur):
        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        detail = _invoice_detail(cur, invoice_id, branch_directory=branch_directory)
        if detail is None:
            return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
        return {"ok": True, **detail}

    return pg._actor_work(user_id, work)


def create_invoice(user_id, payload):
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Invoice details are not valid."}
    branch_id = pg._parse_uuid(payload.get("branch_id"))
    company_id = pg._parse_uuid(payload.get("company_id"))
    if branch_id is None:
        return {"ok": False, "error": "invalid", "message": "Branch is not valid."}
    if company_id is None:
        return {"ok": False, "error": "invalid", "message": "Company is not valid."}
    period_start = _date(payload.get("period_start"))
    period_end = _date(payload.get("period_end"))
    due_date = _date(payload.get("due_date"))
    if period_start is False or period_end is False or due_date is False:
        return {"ok": False, "error": "invalid", "message": "Invoice dates are not valid."}
    notes = _text(payload.get("notes"), limit=2000)
    if notes is False:
        return {"ok": False, "error": "invalid", "message": "Notes are not valid."}
    number = _text(payload.get("invoice_number"), limit=64)
    if number is False:
        return {"ok": False, "error": "invalid", "message": "Invoice number is not valid."}
    lines = payload.get("lines")
    if lines is None:
        lines = []
    if not isinstance(lines, list):
        return {"ok": False, "error": "invalid", "message": "Invoice lines are not valid."}
    issue_now = bool(payload.get("issue"))
    # Branch codes are read as smt_app. Owner/staff cannot SELECT branches.
    branch_directory = _branch_directory()
    if branch_directory is None:
        return {
            "ok": False,
            "error": "unavailable",
            "message": "Financial tables need migration 009 on this database."
            if not finance_schema_ready()
            else "Branch directory is not available.",
        }
    branch_code = _branch_code_for(branch_id, branch_directory)
    if not branch_code:
        return {"ok": False, "error": "invalid", "message": "Branch is not valid."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            if not _can_branch(cur, branch_id):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            cur.execute(
                """
                SELECT 1 FROM company_branches
                WHERE company_id = %s::uuid AND branch_id = %s::uuid
                """,
                (company_id, branch_id),
            )
            if cur.fetchone() is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {
                    "ok": False,
                    "error": "invalid",
                    "message": "That company is not available in this city.",
                }
            invoice_number = number or _next_invoice_number(cur, branch_code)
            invoice_id = str(uuid.uuid4())
            issued_at = datetime.utcnow() if issue_now else None
            cur.execute(
                """
                INSERT INTO invoices (
                    id, branch_id, company_id, currency, invoice_number,
                    period_start, period_end, issued_at, due_date, notes
                )
                VALUES (
                    %s::uuid, %s::uuid, %s::uuid, 'INR', %s,
                    %s, %s, %s, %s, %s
                )
                """,
                (
                    invoice_id,
                    branch_id,
                    company_id,
                    invoice_number,
                    period_start,
                    period_end,
                    issued_at,
                    due_date,
                    notes,
                ),
            )
            for raw in lines:
                ok, err = _insert_line(cur, invoice_id, company_id, raw)
                if not ok:
                    cur.execute("ROLLBACK TO SAVEPOINT finance_write")
                    return err
            _audit(
                cur,
                user_id,
                branch_id,
                "invoice.create",
                "invoices",
                invoice_id,
                "Created invoice %s" % invoice_number,
            )
            detail = _invoice_detail(cur, invoice_id, branch_directory=branch_directory)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {"ok": True, **detail}

    return pg._actor_work(user_id, work)


def _insert_line(cur, invoice_id, company_id, raw):
    if not isinstance(raw, dict):
        return False, {"ok": False, "error": "invalid", "message": "Invoice lines are not valid."}
    description = _text(raw.get("description"), required=True, limit=500)
    amount = _money(raw.get("amount"), allow_zero=True)
    if description is False or amount is False:
        return False, {"ok": False, "error": "invalid", "message": "Invoice line details are not valid."}
    booking_id = None
    if raw.get("booking_id") not in (None, ""):
        booking_id = pg._parse_uuid(raw.get("booking_id"))
        if booking_id is None:
            return False, {"ok": False, "error": "invalid", "message": "Booking is not valid."}
        cur.execute(
            """
            SELECT company_id::text, status, branch_id::text,
                   COALESCE(bc.customer_amount, 0)
            FROM bookings b
            LEFT JOIN booking_charges bc ON bc.booking_id = b.id
            WHERE b.id = %s::uuid
            """,
            (booking_id,),
        )
        booking = cur.fetchone()
        if booking is None:
            return False, {"ok": False, "error": "not_found", "message": "Booking was not found."}
        if booking[0] != company_id:
            return False, {
                "ok": False,
                "error": "invalid",
                "message": "Invoice company must match the booking company.",
            }
        if booking[1] != "completed":
            return False, {
                "ok": False,
                "error": "conflict",
                "message": "Only completed duties can be invoiced.",
            }
        if amount == 0 and booking[3] is not None:
            amount = Decimal(str(booking[3])).quantize(_MONEY)
        if amount <= 0:
            return False, {
                "ok": False,
                "error": "invalid",
                "message": "Invoice line amount must be greater than zero.",
            }
    elif amount <= 0:
        return False, {
            "ok": False,
            "error": "invalid",
            "message": "Invoice line amount must be greater than zero.",
        }
    line_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO invoice_lines (id, invoice_id, booking_id, description, amount)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s)
        """,
        (line_id, invoice_id, booking_id, description, amount),
    )
    return True, None


def update_draft_invoice(user_id, invoice_id, payload):
    invoice_id = pg._parse_uuid(invoice_id)
    if invoice_id is None:
        return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Invoice details are not valid."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            cur.execute(
                """
                SELECT id::text, branch_id::text, company_id::text, issued_at, voided_at
                FROM invoices WHERE id = %s::uuid FOR UPDATE
                """,
                (invoice_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
            if not _can_branch(cur, row[1]):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if row[4] is not None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "conflict", "message": "A void invoice cannot be edited."}
            if row[3] is not None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Issued invoices cannot be edited. Void and recreate if needed.",
                }
            fields = []
            values = []
            if "period_start" in payload:
                period_start = _date(payload.get("period_start"))
                if period_start is False:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Invoice dates are not valid."}
                fields.append("period_start = %s")
                values.append(period_start)
            if "period_end" in payload:
                period_end = _date(payload.get("period_end"))
                if period_end is False:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Invoice dates are not valid."}
                fields.append("period_end = %s")
                values.append(period_end)
            if "due_date" in payload:
                due_date = _date(payload.get("due_date"))
                if due_date is False:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Invoice dates are not valid."}
                fields.append("due_date = %s")
                values.append(due_date)
            if "notes" in payload:
                notes = _text(payload.get("notes"), limit=2000)
                if notes is False:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Notes are not valid."}
                fields.append("notes = %s")
                values.append(notes)
            if "lines" in payload:
                lines = payload.get("lines")
                if not isinstance(lines, list):
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Invoice lines are not valid."}
                cur.execute("DELETE FROM invoice_lines WHERE invoice_id = %s::uuid", (invoice_id,))
                for raw in lines:
                    ok, err = _insert_line(cur, invoice_id, row[2], raw)
                    if not ok:
                        cur.execute("ROLLBACK TO SAVEPOINT finance_write")
                        return err
            if fields:
                values.append(invoice_id)
                cur.execute(
                    "UPDATE invoices SET " + ", ".join(fields) + " WHERE id = %s::uuid",
                    values,
                )
            _audit(
                cur,
                user_id,
                row[1],
                "invoice.update_draft",
                "invoices",
                invoice_id,
                "Updated draft invoice",
            )
            detail = _invoice_detail(cur, invoice_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {"ok": True, **detail}

    return pg._actor_work(user_id, work)


def issue_invoice(user_id, invoice_id, payload=None):
    invoice_id = pg._parse_uuid(invoice_id)
    if invoice_id is None:
        return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
    payload = payload if isinstance(payload, dict) else {}
    due_date = _date(payload.get("due_date")) if "due_date" in payload else None
    if due_date is False:
        return {"ok": False, "error": "invalid", "message": "Due date is not valid."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            cur.execute(
                """
                SELECT id::text, branch_id::text, issued_at, voided_at
                FROM invoices WHERE id = %s::uuid FOR UPDATE
                """,
                (invoice_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
            if not _can_branch(cur, row[1]):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if row[3] is not None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "conflict", "message": "A void invoice cannot be issued."}
            if row[2] is not None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "conflict", "message": "Invoice is already issued."}
            cur.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM invoice_lines WHERE invoice_id = %s::uuid",
                (invoice_id,),
            )
            total = cur.fetchone()[0]
            if total is None or Decimal(str(total)) <= 0:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {
                    "ok": False,
                    "error": "invalid",
                    "message": "Add at least one invoice line before issuing.",
                }
            if "due_date" in payload:
                cur.execute(
                    """
                    UPDATE invoices
                    SET issued_at = now(), due_date = %s
                    WHERE id = %s::uuid
                    """,
                    (due_date, invoice_id),
                )
            else:
                cur.execute(
                    "UPDATE invoices SET issued_at = now() WHERE id = %s::uuid",
                    (invoice_id,),
                )
            _audit(
                cur,
                user_id,
                row[1],
                "invoice.issue",
                "invoices",
                invoice_id,
                "Issued invoice",
            )
            detail = _invoice_detail(cur, invoice_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {"ok": True, **detail}

    return pg._actor_work(user_id, work)


def void_invoice(user_id, invoice_id, payload):
    invoice_id = pg._parse_uuid(invoice_id)
    if invoice_id is None:
        return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
    reason = _text((payload or {}).get("reason"), required=True, limit=500)
    if reason is False or reason is None:
        return {"ok": False, "error": "invalid", "message": "A void reason is required."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            cur.execute(
                """
                SELECT id::text, branch_id::text, voided_at
                FROM invoices WHERE id = %s::uuid FOR UPDATE
                """,
                (invoice_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
            if not _can_branch(cur, row[1]):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if row[2] is not None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "conflict", "message": "Invoice is already void."}
            cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM payments
                WHERE invoice_id = %s::uuid AND reversed_at IS NULL
                """,
                (invoice_id,),
            )
            paid = Decimal(str(cur.fetchone()[0] or 0))
            if paid > 0:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Reverse active payments before voiding this invoice.",
                }
            cur.execute(
                """
                UPDATE invoices
                SET voided_at = now(), void_reason = %s, issued_at = COALESCE(issued_at, now())
                WHERE id = %s::uuid
                """,
                (reason, invoice_id),
            )
            _audit(
                cur,
                user_id,
                row[1],
                "invoice.void",
                "invoices",
                invoice_id,
                "Voided invoice: %s" % reason,
            )
            detail = _invoice_detail(cur, invoice_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {"ok": True, **detail}

    return pg._actor_work(user_id, work)


def record_payment(user_id, invoice_id, payload):
    invoice_id = pg._parse_uuid(invoice_id)
    if invoice_id is None:
        return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Payment details are not valid."}
    amount = _money(payload.get("amount"))
    paid_on = _date(payload.get("paid_on"), required=True)
    method = _text(payload.get("method"), limit=40)
    reference = _text(payload.get("reference"), limit=120)
    import_key = _text(payload.get("import_key"), limit=120)
    if amount is False or paid_on is False:
        return {"ok": False, "error": "invalid", "message": "Payment details are not valid."}
    if method is False or reference is False or import_key is False:
        return {"ok": False, "error": "invalid", "message": "Payment details are not valid."}
    if method and method.lower() not in _PAYMENT_METHODS:
        return {
            "ok": False,
            "error": "invalid",
            "message": "Payment method must be one of: %s." % ", ".join(_PAYMENT_METHODS),
        }

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        if import_key:
            cur.execute(
                """
                SELECT id::text, invoice_id::text FROM payments
                WHERE import_key = %s
                """,
                (import_key,),
            )
            existing = cur.fetchone()
            if existing is not None:
                if existing[1] != invoice_id:
                    return {
                        "ok": False,
                        "error": "conflict",
                        "message": "That payment import key was already recorded.",
                    }
                payments = _select_payments(cur, invoice_id)
                payment = next((p for p in payments if p["id"] == existing[0]), None)
                invoice = _select_invoice(cur, invoice_id)
                return {
                    "ok": True,
                    "idempotent": True,
                    "invoice": invoice,
                    "payment": payment,
                    "payments": payments,
                }
        cur.execute("SAVEPOINT finance_write")
        try:
            cur.execute(
                """
                SELECT id::text, branch_id::text, issued_at, voided_at
                FROM invoices WHERE id = %s::uuid FOR UPDATE
                """,
                (invoice_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "not_found", "message": "Invoice was not found."}
            if not _can_branch(cur, row[1]):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if row[3] is not None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "conflict", "message": "Cannot pay a void invoice."}
            if row[2] is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Issue the invoice before recording payments.",
                }
            payment_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO payments (
                    id, invoice_id, currency, amount, paid_on, method, reference, import_key
                )
                VALUES (%s::uuid, %s::uuid, 'INR', %s, %s, %s, %s, %s)
                """,
                (
                    payment_id,
                    invoice_id,
                    amount,
                    paid_on,
                    method.lower() if method else None,
                    reference,
                    import_key,
                ),
            )
            _audit(
                cur,
                user_id,
                row[1],
                "payment.record",
                "payments",
                payment_id,
                "Recorded payment %s" % amount,
            )
            invoice = _select_invoice(cur, invoice_id)
            payments = _select_payments(cur, invoice_id)
            payment = next(p for p in payments if p["id"] == payment_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {
            "ok": True,
            "invoice": invoice,
            "payment": payment,
            "payments": payments,
        }

    return pg._actor_work(user_id, work)


def reverse_payment(user_id, payment_id, payload):
    payment_id = pg._parse_uuid(payment_id)
    if payment_id is None:
        return {"ok": False, "error": "not_found", "message": "Payment was not found."}
    reason = _text((payload or {}).get("reason"), required=True, limit=500)
    if reason is False or reason is None:
        return {"ok": False, "error": "invalid", "message": "A reversal reason is required."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            cur.execute(
                """
                SELECT p.id::text, p.invoice_id::text, p.reversed_at, i.branch_id::text
                FROM payments p
                JOIN invoices i ON i.id = p.invoice_id
                WHERE p.id = %s::uuid
                FOR UPDATE OF p, i
                """,
                (payment_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "not_found", "message": "Payment was not found."}
            if not _can_branch(cur, row[3]):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if row[2] is not None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "conflict", "message": "Payment is already reversed."}
            cur.execute(
                """
                UPDATE payments
                SET reversed_at = now(), reversal_reason = %s
                WHERE id = %s::uuid
                """,
                (reason, payment_id),
            )
            _audit(
                cur,
                user_id,
                row[3],
                "payment.reverse",
                "payments",
                payment_id,
                "Reversed payment: %s" % reason,
            )
            invoice = _select_invoice(cur, row[1])
            payments = _select_payments(cur, row[1])
            payment = next(p for p in payments if p["id"] == row[0])
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {
            "ok": True,
            "invoice": invoice,
            "payment": payment,
            "payments": payments,
        }

    return pg._actor_work(user_id, work)


def create_payout(user_id, payload):
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Payout details are not valid."}
    booking_id = pg._parse_uuid(payload.get("booking_id"))
    driver_id = pg._parse_uuid(payload.get("driver_id"))
    amount = _money(payload.get("amount"), allow_zero=True)
    notes = _text(payload.get("notes"), limit=1000)
    reference = _text(payload.get("reference"), limit=120)
    status = (_text(payload.get("status"), limit=20) or "pending")
    if isinstance(status, str):
        status = status.lower()
    if booking_id is None:
        return {"ok": False, "error": "invalid", "message": "Booking is not valid."}
    if amount is False or notes is False or reference is False:
        return {"ok": False, "error": "invalid", "message": "Payout details are not valid."}
    if status not in _PAYOUT_STATUSES or status == "cancelled":
        return {"ok": False, "error": "invalid", "message": "Payout status is not valid."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            cur.execute(
                """
                SELECT b.id::text, b.branch_id::text, b.status,
                       a.driver_id::text
                FROM bookings b
                LEFT JOIN booking_assignments a
                  ON a.booking_id = b.id AND a.status = 'completed'
                WHERE b.id = %s::uuid
                FOR UPDATE OF b
                """,
                (booking_id,),
            )
            booking = cur.fetchone()
            if booking is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "not_found", "message": "Booking was not found."}
            if not _can_branch(cur, booking[1]):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if booking[2] != "completed":
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {
                    "ok": False,
                    "error": "conflict",
                    "message": "Only completed duties can receive a payout.",
                }
            resolved_driver = driver_id or booking[3]
            if resolved_driver is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {
                    "ok": False,
                    "error": "invalid",
                    "message": "Driver is required for this payout.",
                }
            payout_amount = amount
            if payout_amount is None or payout_amount <= 0:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {
                    "ok": False,
                    "error": "invalid",
                    "message": "Payout amount is required.",
                }
            payout_id = str(uuid.uuid4())
            paid_at = datetime.utcnow() if status == "paid" else None
            cur.execute(
                """
                INSERT INTO driver_payouts (
                    id, booking_id, driver_id, currency, status, amount, paid_at, notes, reference
                )
                VALUES (%s::uuid, %s::uuid, %s::uuid, 'INR', %s, %s, %s, %s, %s)
                """,
                (
                    payout_id,
                    booking_id,
                    resolved_driver,
                    status,
                    payout_amount,
                    paid_at,
                    notes,
                    reference,
                ),
            )
            _audit(
                cur,
                user_id,
                booking[1],
                "payout.create",
                "driver_payouts",
                payout_id,
                "Created driver payout %s" % payout_amount,
            )
            payout = _select_payout(cur, payout_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {"ok": True, "payout": payout}

    return pg._actor_work(user_id, work)


def _select_payout(cur, payout_id):
    cur.execute(
        """
        SELECT p.id::text, p.booking_id::text, p.driver_id::text, p.currency, p.status,
               p.amount, p.paid_at, p.notes, p.reference, p.created_at,
               d.display_name, b.source_booking_id, b.branch_id::text
        FROM driver_payouts p
        JOIN drivers d ON d.id = p.driver_id
        JOIN bookings b ON b.id = p.booking_id
        WHERE p.id = %s::uuid
        """,
        (payout_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "booking_id": row[1],
        "driver_id": row[2],
        "currency": row[3],
        "status": row[4],
        "amount": str(row[5]) if row[5] is not None else None,
        "paid_at": pg._booking_value(row[6]),
        "notes": row[7],
        "reference": row[8],
        "created_at": pg._booking_value(row[9]),
        "driver_name": row[10],
        "source_booking_id": row[11],
        "branch_id": row[12],
    }


def update_payout(user_id, payout_id, payload):
    payout_id = pg._parse_uuid(payout_id)
    if payout_id is None:
        return {"ok": False, "error": "not_found", "message": "Payout was not found."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Payout details are not valid."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            cur.execute(
                """
                SELECT p.id::text, b.branch_id::text, p.status
                FROM driver_payouts p
                JOIN bookings b ON b.id = p.booking_id
                WHERE p.id = %s::uuid
                FOR UPDATE OF p
                """,
                (payout_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "not_found", "message": "Payout was not found."}
            if not _can_branch(cur, row[1]):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if row[2] == "cancelled":
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "conflict", "message": "Cancelled payouts cannot be changed."}
            fields = []
            values = []
            if "status" in payload:
                status = _text(payload.get("status"), required=True, limit=20)
                if status is False or status.lower() not in _PAYOUT_STATUSES:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Payout status is not valid."}
                status = status.lower()
                fields.append("status = %s")
                values.append(status)
                if status == "paid":
                    fields.append("paid_at = COALESCE(paid_at, now())")
                elif status == "pending":
                    fields.append("paid_at = NULL")
            if "amount" in payload:
                amount = _money(payload.get("amount"))
                if amount is False:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Payout amount is not valid."}
                fields.append("amount = %s")
                values.append(amount)
            if "notes" in payload:
                notes = _text(payload.get("notes"), limit=1000)
                if notes is False:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Notes are not valid."}
                fields.append("notes = %s")
                values.append(notes)
            if "reference" in payload:
                reference = _text(payload.get("reference"), limit=120)
                if reference is False:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {"ok": False, "error": "invalid", "message": "Reference is not valid."}
                fields.append("reference = %s")
                values.append(reference)
            if not fields:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "invalid", "message": "No payout changes were provided."}
            values.append(payout_id)
            cur.execute(
                "UPDATE driver_payouts SET " + ", ".join(fields) + " WHERE id = %s::uuid",
                values,
            )
            _audit(
                cur,
                user_id,
                row[1],
                "payout.update",
                "driver_payouts",
                payout_id,
                "Updated driver payout",
            )
            payout = _select_payout(cur, payout_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {"ok": True, "payout": payout}

    return pg._actor_work(user_id, work)


def list_payouts(user_id, branch_id=None, status=None, driver_id=None):
    def work(cur):
        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        clauses = ["TRUE"]
        params = []
        if branch_id:
            clauses.append("b.branch_id = %s::uuid")
            params.append(branch_id)
        if status:
            clauses.append("p.status = %s")
            params.append(status)
        if driver_id:
            clauses.append("p.driver_id = %s::uuid")
            params.append(driver_id)
        cur.execute(
            """
            SELECT p.id::text
            FROM driver_payouts p
            JOIN bookings b ON b.id = p.booking_id
            WHERE """
            + " AND ".join(clauses)
            + """
            ORDER BY COALESCE(p.paid_at, p.created_at) DESC
            LIMIT 200
            """,
            params,
        )
        payouts = []
        for (payout_id,) in cur.fetchall():
            item = _select_payout(cur, payout_id)
            if item:
                payouts.append(item)
        return {"ok": True, "payouts": payouts}

    return pg._actor_work(user_id, work)


def create_expense(user_id, payload):
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Expense details are not valid."}
    branch_id = pg._parse_uuid(payload.get("branch_id"))
    company_id = None
    if payload.get("company_id") not in (None, ""):
        company_id = pg._parse_uuid(payload.get("company_id"))
        if company_id is None:
            return {"ok": False, "error": "invalid", "message": "Company is not valid."}
    category = _text(payload.get("category"), required=True, limit=80)
    description = _text(payload.get("description"), required=True, limit=500)
    amount = _money(payload.get("amount"))
    expense_date = _date(payload.get("expense_date"), required=True)
    document_ref = _text(payload.get("document_ref"), limit=200)
    status = (_text(payload.get("status"), limit=20) or "recorded")
    if isinstance(status, str):
        status = status.lower()
    if branch_id is None:
        return {"ok": False, "error": "invalid", "message": "Branch is not valid."}
    if False in (category, description, amount, expense_date, document_ref) or None in (
        category,
        description,
        amount,
        expense_date,
    ):
        return {"ok": False, "error": "invalid", "message": "Expense details are not valid."}
    if status not in _EXPENSE_STATUSES:
        return {"ok": False, "error": "invalid", "message": "Expense status is not valid."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            if not _can_branch(cur, branch_id):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if company_id:
                cur.execute(
                    """
                    SELECT 1 FROM company_branches
                    WHERE company_id = %s::uuid AND branch_id = %s::uuid
                    """,
                    (company_id, branch_id),
                )
                if cur.fetchone() is None:
                    cur.execute("RELEASE SAVEPOINT finance_write")
                    return {
                        "ok": False,
                        "error": "invalid",
                        "message": "That company is not available in this city.",
                    }
            expense_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO expenses (
                    id, branch_id, company_id, category, description, amount,
                    expense_date, document_ref, status
                )
                VALUES (
                    %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    expense_id,
                    branch_id,
                    company_id,
                    category,
                    description,
                    amount,
                    expense_date,
                    document_ref,
                    status,
                ),
            )
            _audit(
                cur,
                user_id,
                branch_id,
                "expense.create",
                "expenses",
                expense_id,
                "Recorded expense %s" % amount,
            )
            expense = _select_expense(cur, expense_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {"ok": True, "expense": expense}

    return pg._actor_work(user_id, work)


def _select_expense(cur, expense_id, branch_directory=None):
    if branch_directory is None:
        branch_directory = _branch_directory()
    cur.execute(
        """
        SELECT e.id::text, e.branch_id::text, e.company_id::text, e.category, e.description,
               e.currency, e.amount, e.expense_date, e.document_ref, e.status, e.created_at,
               c.name AS company_name
        FROM expenses e
        LEFT JOIN companies c ON c.id = e.company_id
        WHERE e.id = %s::uuid
        """,
        (expense_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "branch_id": row[1],
        "company_id": row[2],
        "category": row[3],
        "description": row[4],
        "currency": row[5],
        "amount": str(row[6]),
        "expense_date": pg._booking_value(row[7]),
        "document_ref": row[8],
        "status": row[9],
        "created_at": pg._booking_value(row[10]),
        "branch_code": _branch_code_for(row[1], branch_directory),
        "company_name": row[11],
    }


def list_expenses(user_id, branch_id=None, status=None):
    def work(cur):
        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        clauses = ["TRUE"]
        params = []
        if branch_id:
            clauses.append("e.branch_id = %s::uuid")
            params.append(branch_id)
        if status:
            clauses.append("e.status = %s")
            params.append(status)
        cur.execute(
            """
            SELECT e.id::text
            FROM expenses e
            WHERE """
            + " AND ".join(clauses)
            + """
            ORDER BY e.expense_date DESC, e.created_at DESC
            LIMIT 200
            """,
            params,
        )
        expenses = []
        for (expense_id,) in cur.fetchall():
            item = _select_expense(cur, expense_id)
            if item:
                expenses.append(item)
        return {"ok": True, "expenses": expenses}

    return pg._actor_work(user_id, work)


def update_expense(user_id, expense_id, payload):
    expense_id = pg._parse_uuid(expense_id)
    if expense_id is None:
        return {"ok": False, "error": "not_found", "message": "Expense was not found."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid", "message": "Expense details are not valid."}

    def work(cur):
        import psycopg

        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SAVEPOINT finance_write")
        try:
            cur.execute(
                """
                SELECT id::text, branch_id::text, status
                FROM expenses WHERE id = %s::uuid FOR UPDATE
                """,
                (expense_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "not_found", "message": "Expense was not found."}
            if not _can_branch(cur, row[1]):
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "forbidden", "message": "You cannot use this branch."}
            if row[2] == "cancelled":
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "conflict", "message": "Cancelled expenses cannot be changed."}
            if "status" not in payload:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "invalid", "message": "Expense status is required."}
            status = _text(payload.get("status"), required=True, limit=20)
            if status is False or status.lower() not in _EXPENSE_STATUSES:
                cur.execute("RELEASE SAVEPOINT finance_write")
                return {"ok": False, "error": "invalid", "message": "Expense status is not valid."}
            cur.execute(
                "UPDATE expenses SET status = %s WHERE id = %s::uuid",
                (status.lower(), expense_id),
            )
            _audit(
                cur,
                user_id,
                row[1],
                "expense.update",
                "expenses",
                expense_id,
                "Updated expense status to %s" % status.lower(),
            )
            expense = _select_expense(cur, expense_id)
        except psycopg.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT finance_write")
            return _finance_error(exc)
        cur.execute("RELEASE SAVEPOINT finance_write")
        return {"ok": True, "expense": expense}

    return pg._actor_work(user_id, work)


def company_settlement(user_id, company_id, branch_id=None):
    company_id = pg._parse_uuid(company_id)
    if company_id is None:
        return {"ok": False, "error": "not_found", "message": "Company was not found."}

    def work(cur):
        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        cur.execute("SELECT id::text, name FROM companies WHERE id = %s::uuid", (company_id,))
        company = cur.fetchone()
        if company is None:
            return {"ok": False, "error": "not_found", "message": "Company was not found."}
        params = [company_id]
        branch_clause = ""
        if branch_id:
            branch_clause = " AND b.branch_id = %s::uuid"
            params.append(branch_id)
        cur.execute(
            """
            SELECT COALESCE(SUM(COALESCE(bc.customer_amount, 0)), 0)
            FROM bookings b
            LEFT JOIN booking_charges bc ON bc.booking_id = b.id
            WHERE b.company_id = %s::uuid AND b.status = 'completed'
            """
            + branch_clause,
            params,
        )
        completed_value = cur.fetchone()[0]
        inv_params = [company_id]
        inv_branch = ""
        if branch_id:
            inv_branch = " AND i.branch_id = %s::uuid"
            inv_params.append(branch_id)
        cur.execute(
            """
            SELECT
                COALESCE(SUM(bal.total_amount), 0),
                COALESCE(SUM(bal.paid_amount), 0),
                COALESCE(SUM(bal.outstanding_amount), 0)
            FROM invoices i
            JOIN invoice_balances bal ON bal.invoice_id = i.id
            WHERE i.company_id = %s::uuid AND i.voided_at IS NULL
            """
            + inv_branch,
            inv_params,
        )
        invoiced, collected, outstanding = cur.fetchone()
        payout_params = [company_id]
        payout_branch = ""
        if branch_id:
            payout_branch = " AND b.branch_id = %s::uuid"
            payout_params.append(branch_id)
        cur.execute(
            """
            SELECT
                COALESCE(SUM(p.amount) FILTER (WHERE p.status = 'pending'), 0),
                COALESCE(SUM(p.amount) FILTER (WHERE p.status = 'paid'), 0)
            FROM driver_payouts p
            JOIN bookings b ON b.id = p.booking_id
            WHERE b.company_id = %s::uuid AND p.status IN ('pending', 'paid')
            """
            + payout_branch,
            payout_params,
        )
        pending_payouts, paid_payouts = cur.fetchone()
        return {
            "ok": True,
            "settlement": {
                "company_id": company[0],
                "company_name": company[1],
                "branch_id": branch_id,
                "completed_duty_value": str(completed_value),
                "invoiced_amount": str(invoiced),
                "payments_received": str(collected),
                "outstanding_balance": str(outstanding),
                "pending_driver_payouts": str(pending_payouts),
                "paid_driver_payouts": str(paid_payouts),
            },
        }

    return pg._actor_work(user_id, work)


def finance_dashboard(user_id, branch_id=None, date_from=None, date_to=None):
    date_from = _date(date_from) if date_from not in (None, "") else None
    date_to = _date(date_to) if date_to not in (None, "") else None
    if date_from is False or date_to is False:
        return {"ok": False, "error": "invalid", "message": "Date range is not valid."}

    def work(cur):
        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        params = []
        branch_sql = ""
        if branch_id:
            branch_sql = " AND i.branch_id = %s::uuid"
            params.append(branch_id)
        date_sql = ""
        if date_from:
            date_sql += " AND COALESCE(i.issued_at::date, i.created_at::date) >= %s"
            params.append(date_from)
        if date_to:
            date_sql += " AND COALESCE(i.issued_at::date, i.created_at::date) <= %s"
            params.append(date_to)
        cur.execute(
            """
            SELECT
                COALESCE(SUM(bal.total_amount) FILTER (WHERE i.voided_at IS NULL), 0),
                COALESCE(SUM(bal.paid_amount) FILTER (WHERE i.voided_at IS NULL), 0),
                COALESCE(SUM(bal.outstanding_amount) FILTER (WHERE i.voided_at IS NULL), 0),
                COUNT(*) FILTER (
                    WHERE i.voided_at IS NULL
                      AND i.issued_at IS NOT NULL
                      AND i.due_date IS NOT NULL
                      AND i.due_date < CURRENT_DATE
                      AND bal.outstanding_amount > 0
                )
            FROM invoices i
            JOIN invoice_balances bal ON bal.invoice_id = i.id
            WHERE TRUE
            """
            + branch_sql
            + date_sql,
            params,
        )
        invoiced, collected, outstanding, overdue_count = cur.fetchone()
        payout_params = []
        payout_branch = ""
        if branch_id:
            payout_branch = " AND b.branch_id = %s::uuid"
            payout_params.append(branch_id)
        cur.execute(
            """
            SELECT
                COALESCE(SUM(p.amount) FILTER (WHERE p.status = 'pending'), 0),
                COALESCE(SUM(p.amount) FILTER (WHERE p.status = 'paid'), 0)
            FROM driver_payouts p
            JOIN bookings b ON b.id = p.booking_id
            WHERE p.status IN ('pending', 'paid')
            """
            + payout_branch,
            payout_params,
        )
        pending_payouts, paid_payouts = cur.fetchone()
        expense_params = []
        expense_branch = ""
        if branch_id:
            expense_branch = " AND e.branch_id = %s::uuid"
            expense_params.append(branch_id)
        cur.execute(
            """
            SELECT COALESCE(SUM(e.amount), 0)
            FROM expenses e
            WHERE e.status <> 'cancelled'
            """
            + expense_branch,
            expense_params,
        )
        expenses_total = cur.fetchone()[0]
        # Aggregate by branch_id only. Branch codes come from the smt_app directory.
        cur.execute(
            """
            SELECT i.branch_id::text,
                   COALESCE(SUM(bal.total_amount) FILTER (WHERE i.voided_at IS NULL), 0),
                   COALESCE(SUM(bal.paid_amount) FILTER (WHERE i.voided_at IS NULL), 0),
                   COALESCE(SUM(bal.outstanding_amount) FILTER (WHERE i.voided_at IS NULL), 0)
            FROM invoices i
            LEFT JOIN invoice_balances bal ON bal.invoice_id = i.id
            GROUP BY i.branch_id
            """
        )
        totals_by_branch = {
            row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()
        }
        directory = _branch_directory() or {}
        by_branch = []
        for branch_id_key, meta in sorted(
            directory.items(), key=lambda item: item[1].get("code") or ""
        ):
            if not meta.get("is_active"):
                continue
            invoiced, collected, outstanding_amt = totals_by_branch.get(
                branch_id_key, (0, 0, 0)
            )
            by_branch.append(
                {
                    "branch_code": meta.get("code"),
                    "branch_id": branch_id_key,
                    "invoiced": str(invoiced),
                    "collected": str(collected),
                    "outstanding": str(outstanding_amt),
                }
            )
        cur.execute(
            """
            SELECT c.id::text, c.name,
                   COALESCE(SUM(bal.total_amount) FILTER (WHERE i.voided_at IS NULL), 0),
                   COALESCE(SUM(bal.paid_amount) FILTER (WHERE i.voided_at IS NULL), 0),
                   COALESCE(SUM(bal.outstanding_amount) FILTER (WHERE i.voided_at IS NULL), 0)
            FROM companies c
            LEFT JOIN invoices i ON i.company_id = c.id
            LEFT JOIN invoice_balances bal ON bal.invoice_id = i.id
            GROUP BY c.id, c.name
            HAVING COALESCE(SUM(bal.total_amount) FILTER (WHERE i.voided_at IS NULL), 0) > 0
                OR COALESCE(SUM(bal.paid_amount) FILTER (WHERE i.voided_at IS NULL), 0) > 0
            ORDER BY c.name
            LIMIT 100
            """
        )
        by_company = [
            {
                "company_id": row[0],
                "company_name": row[1],
                "invoiced": str(row[2]),
                "collected": str(row[3]),
                "outstanding": str(row[4]),
            }
            for row in cur.fetchall()
        ]
        return {
            "ok": True,
            "dashboard": {
                "total_invoiced": str(invoiced),
                "total_collected": str(collected),
                "outstanding_receivables": str(outstanding),
                "overdue_invoice_count": int(overdue_count or 0),
                "pending_driver_payouts": str(pending_payouts),
                "paid_driver_payouts": str(paid_payouts),
                "expenses": str(expenses_total),
                "by_branch": by_branch,
                "by_company": by_company,
            },
        }

    return pg._actor_work(user_id, work)


def list_billable_bookings(user_id, company_id, branch_id=None):
    company_id = pg._parse_uuid(company_id)
    if company_id is None:
        return {"ok": False, "error": "invalid", "message": "Company is not valid."}

    def work(cur):
        blocked = _schema_or_unavailable(cur)
        if blocked:
            return blocked
        params = [company_id]
        branch_sql = ""
        if branch_id:
            branch_sql = " AND b.branch_id = %s::uuid"
            params.append(branch_id)
        cur.execute(
            """
            SELECT b.id::text, b.source_booking_id, b.trip_date, b.employee_name,
                   b.branch_id::text, COALESCE(bc.customer_amount, 0)
            FROM bookings b
            LEFT JOIN booking_charges bc ON bc.booking_id = b.id
            WHERE b.company_id = %s::uuid
              AND b.status = 'completed'
              AND NOT EXISTS (
                    SELECT 1 FROM invoice_lines l WHERE l.booking_id = b.id
              )
            """
            + branch_sql
            + """
            ORDER BY b.trip_date DESC, b.source_booking_id
            LIMIT 200
            """,
            params,
        )
        bookings = []
        for row in cur.fetchall():
            bookings.append(
                {
                    "id": row[0],
                    "source_booking_id": row[1],
                    "trip_date": pg._booking_value(row[2]),
                    "employee_name": row[3],
                    "branch_id": row[4],
                    "customer_amount": str(row[5]),
                }
            )
        return {"ok": True, "bookings": bookings}

    return pg._actor_work(user_id, work)
