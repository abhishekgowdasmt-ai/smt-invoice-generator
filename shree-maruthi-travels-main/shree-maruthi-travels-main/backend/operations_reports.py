"""Supervisor reporting aggregates and CSV exports (Master Prompt 7).

All calculations run under staff/owner RLS via pg._actor_work.
Uses existing tables and invoice_balances. Does not invent KPIs or rates.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal

import shared_api_contracts
import dev_postgres as pg

_REPORT_LIMIT = 500
_BOOKING_STATUSES = shared_api_contracts.BOOKING_STATUSES
_BOOKING_ORIGINS = shared_api_contracts.BOOKING_ORIGINS


def _parse_date(value, label="Date"):
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return False


def _parse_uuid(value):
    if value in (None, ""):
        return None
    return pg._parse_uuid(value)


def _money(value):
    if value is None:
        return "0.00"
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def _csv_cell(value):
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def _branch_label(branch_id, by_id):
    if not branch_id:
        return None
    row = (by_id or {}).get(str(branch_id)) or (by_id or {}).get(branch_id)
    if not row:
        return None
    return row.get("code")


def _filters(
    *,
    date_from=None,
    date_to=None,
    branch_id=None,
    company_id=None,
    driver_id=None,
    vehicle_id=None,
    status=None,
    origin=None,
    **_extra,
):
    d_from = _parse_date(date_from, "Start date")
    d_to = _parse_date(date_to, "End date")
    if d_from is False or d_to is False:
        return None, {"ok": False, "error": "invalid", "message": "Date range is not valid."}
    if d_from and d_to and d_from > d_to:
        return None, {"ok": False, "error": "invalid", "message": "Start date must be on or before end date."}
    bid = _parse_uuid(branch_id) if branch_id not in (None, "") else None
    if branch_id not in (None, "") and bid is None:
        return None, {"ok": False, "error": "invalid", "message": "Branch filter is not valid."}
    cid = _parse_uuid(company_id) if company_id not in (None, "") else None
    if company_id not in (None, "") and cid is None:
        return None, {"ok": False, "error": "invalid", "message": "Company filter is not valid."}
    did = _parse_uuid(driver_id) if driver_id not in (None, "") else None
    if driver_id not in (None, "") and did is None:
        return None, {"ok": False, "error": "invalid", "message": "Driver filter is not valid."}
    vid = _parse_uuid(vehicle_id) if vehicle_id not in (None, "") else None
    if vehicle_id not in (None, "") and vid is None:
        return None, {"ok": False, "error": "invalid", "message": "Vehicle filter is not valid."}
    if status not in (None, "") and status not in _BOOKING_STATUSES:
        return None, {"ok": False, "error": "invalid", "message": "Status filter is not valid."}
    if origin not in (None, "") and origin not in _BOOKING_ORIGINS:
        return None, {"ok": False, "error": "invalid", "message": "Origin filter is not valid."}
    return {
        "date_from": d_from,
        "date_to": d_to,
        "branch_id": bid,
        "company_id": cid,
        "driver_id": did,
        "vehicle_id": vid,
        "status": status or None,
        "origin": origin or None,
    }, None


def _booking_where(filters, alias="b"):
    clauses = []
    params = []
    if filters["date_from"]:
        clauses.append(f"{alias}.trip_date >= %s")
        params.append(filters["date_from"])
    if filters["date_to"]:
        clauses.append(f"{alias}.trip_date <= %s")
        params.append(filters["date_to"])
    if filters["branch_id"]:
        clauses.append(f"{alias}.branch_id = %s::uuid")
        params.append(filters["branch_id"])
    if filters["company_id"]:
        clauses.append(f"{alias}.company_id = %s::uuid")
        params.append(filters["company_id"])
    if filters["status"]:
        clauses.append(f"{alias}.status = %s")
        params.append(filters["status"])
    if filters["origin"]:
        clauses.append(f"{alias}.origin = %s")
        params.append(filters["origin"])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def csv_response_rows(filename, headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_cell(cell) for cell in row])
    return {
        "ok": True,
        "filename": filename,
        "content_type": "text/csv; charset=utf-8",
        "body": buffer.getvalue(),
    }


def booking_report(user_id, **kwargs):
    filters, err = _filters(**kwargs)
    if err:
        return err

    def work(cur):
        where, params = _booking_where(filters)
        cur.execute(
            f"""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE status = 'unassigned'),
                COUNT(*) FILTER (WHERE status = 'assigned'),
                COUNT(*) FILTER (WHERE status = 'accepted'),
                COUNT(*) FILTER (WHERE status = 'started'),
                COUNT(*) FILTER (WHERE status = 'completed'),
                COUNT(*) FILTER (WHERE status = 'cancelled'),
                COUNT(*) FILTER (WHERE origin = 'rac'),
                COUNT(*) FILTER (WHERE origin = 'retail'),
                COUNT(*) FILTER (WHERE origin = 'client_request'),
                COUNT(*) FILTER (WHERE origin = 'ets_occurrence')
            FROM bookings b
            {where}
            """,
            params,
        )
        totals = cur.fetchone()
        cur.execute(
            f"""
            SELECT trip_date::text, status, COUNT(*)
            FROM bookings b
            {where}
            GROUP BY trip_date, status
            ORDER BY trip_date NULLS LAST, status
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        by_date_status = [
            {"trip_date": r[0], "status": r[1], "count": int(r[2])}
            for r in cur.fetchall()
        ]
        cur.execute(
            f"""
            SELECT origin, COUNT(*)
            FROM bookings b
            {where}
            GROUP BY origin
            ORDER BY origin
            """,
            params,
        )
        by_origin = [{"origin": r[0], "count": int(r[1])} for r in cur.fetchall()]
        cur.execute(
            f"""
            SELECT b.trip_date::text, b.source_booking_id, b.employee_name, b.origin,
                   b.status, b.branch_id::text, c.name, b.id::text
            FROM bookings b
            LEFT JOIN companies c ON c.id = b.company_id
            {where}
            ORDER BY b.trip_date DESC NULLS LAST, b.created_at DESC
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        raw_rows = cur.fetchall()
        maps = pg._branch_maps()
        by_id = maps[1] if maps else {}
        rows = [
            {
                "trip_date": r[0],
                "source_booking_id": r[1],
                "employee_name": r[2],
                "origin": r[3],
                "status": r[4],
                "branch_code": _branch_label(r[5], by_id),
                "company_name": r[6],
                "booking_id": r[7],
            }
            for r in raw_rows
        ]
        return {
            "ok": True,
            "summary": {
                "total": int(totals[0] or 0),
                "unassigned": int(totals[1] or 0),
                "assigned": int(totals[2] or 0),
                "accepted": int(totals[3] or 0),
                "started": int(totals[4] or 0),
                "completed": int(totals[5] or 0),
                "cancelled": int(totals[6] or 0),
                "origin_rac": int(totals[7] or 0),
                "origin_retail": int(totals[8] or 0),
                "origin_client_request": int(totals[9] or 0),
                "origin_ets": int(totals[10] or 0),
            },
            "by_date_status": by_date_status,
            "by_origin": by_origin,
            "rows": rows,
        }

    return pg._actor_work(user_id, work)


def trip_report(user_id, **kwargs):
    filters, err = _filters(**kwargs)
    if err:
        return err

    def work(cur):
        where, params = _booking_where(filters)
        cur.execute(
            f"""
            SELECT
                COUNT(*) FILTER (WHERE b.status = 'completed'),
                COUNT(*) FILTER (WHERE b.status = 'started'),
                COUNT(*) FILTER (
                    WHERE b.trip_date > CURRENT_DATE
                      AND b.status NOT IN ('completed', 'cancelled')
                ),
                COUNT(*) FILTER (WHERE b.status = 'cancelled')
            FROM bookings b
            {where}
            """,
            params,
        )
        summary = cur.fetchone()
        cur.execute(
            f"""
            SELECT b.trip_date::text, b.source_booking_id, b.status,
                   ts.started_at, ts.ended_at,
                   CASE
                     WHEN ts.started_at IS NOT NULL AND ts.ended_at IS NOT NULL
                     THEN EXTRACT(EPOCH FROM (ts.ended_at - ts.started_at)) / 60.0
                     ELSE NULL
                   END AS duration_minutes,
                   dr.start_km, dr.end_km, dr.total_km,
                   d.display_name, v.registration_number, b.id::text
            FROM bookings b
            LEFT JOIN LATERAL (
                SELECT s.started_at, s.ended_at, s.assignment_id
                FROM trip_sessions s
                JOIN booking_assignments a ON a.id = s.assignment_id
                WHERE a.booking_id = b.id
                ORDER BY s.started_at DESC
                LIMIT 1
            ) ts ON true
            LEFT JOIN duty_readings dr ON dr.booking_id = b.id
            LEFT JOIN booking_assignments a
              ON a.booking_id = b.id AND a.status IN ('assigned','accepted','completed')
            LEFT JOIN drivers d ON d.id = a.driver_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id
            {where}
            ORDER BY b.trip_date DESC NULLS LAST
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        rows = []
        for r in cur.fetchall():
            rows.append(
                {
                    "trip_date": r[0],
                    "source_booking_id": r[1],
                    "status": r[2],
                    "started_at": r[3].isoformat() if r[3] else None,
                    "ended_at": r[4].isoformat() if r[4] else None,
                    "duration_minutes": float(r[5]) if r[5] is not None else None,
                    "start_km": float(r[6]) if r[6] is not None else None,
                    "end_km": float(r[7]) if r[7] is not None else None,
                    "total_km": float(r[8]) if r[8] is not None else None,
                    "driver_name": r[9],
                    "vehicle_registration": r[10],
                    "booking_id": r[11],
                }
            )
        return {
            "ok": True,
            "summary": {
                "completed": int(summary[0] or 0),
                "in_progress": int(summary[1] or 0),
                "upcoming": int(summary[2] or 0),
                "cancelled": int(summary[3] or 0),
            },
            "rows": rows,
        }

    return pg._actor_work(user_id, work)


def driver_performance_report(user_id, **kwargs):
    filters, err = _filters(**kwargs)
    if err:
        return err

    def work(cur):
        clauses = []
        params = []
        if filters["date_from"]:
            clauses.append("b.trip_date >= %s")
            params.append(filters["date_from"])
        if filters["date_to"]:
            clauses.append("b.trip_date <= %s")
            params.append(filters["date_to"])
        if filters["branch_id"]:
            clauses.append("b.branch_id = %s::uuid")
            params.append(filters["branch_id"])
        if filters["driver_id"]:
            clauses.append("a.driver_id = %s::uuid")
            params.append(filters["driver_id"])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cur.execute(
            f"""
            SELECT d.id::text, d.display_name, d.active, d.verification_status,
                   COUNT(*) FILTER (WHERE a.status IN ('assigned','accepted','rejected','withdrawn','superseded','completed')),
                   COUNT(*) FILTER (WHERE a.status = 'accepted'),
                   COUNT(*) FILTER (WHERE a.status = 'rejected'),
                   COUNT(*) FILTER (WHERE a.status = 'completed'),
                   COUNT(*) FILTER (WHERE a.status IN ('withdrawn','superseded'))
            FROM drivers d
            LEFT JOIN booking_assignments a ON a.driver_id = d.id
            LEFT JOIN bookings b ON b.id = a.booking_id
            {where}
            GROUP BY d.id, d.display_name, d.active, d.verification_status
            ORDER BY d.display_name
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        rows = [
            {
                "driver_id": r[0],
                "driver_name": r[1],
                "active": bool(r[2]),
                "verification_status": r[3],
                "assigned_duties": int(r[4] or 0),
                "accepted": int(r[5] or 0),
                "rejected": int(r[6] or 0),
                "completed": int(r[7] or 0),
                "withdrawn_or_superseded": int(r[8] or 0),
            }
            for r in cur.fetchall()
        ]
        return {"ok": True, "rows": rows, "summary": {"drivers": len(rows)}}

    return pg._actor_work(user_id, work)


def vehicle_utilization_report(user_id, **kwargs):
    filters, err = _filters(**kwargs)
    if err:
        return err

    def work(cur):
        clauses = []
        params = []
        if filters["date_from"]:
            clauses.append("b.trip_date >= %s")
            params.append(filters["date_from"])
        if filters["date_to"]:
            clauses.append("b.trip_date <= %s")
            params.append(filters["date_to"])
        if filters["branch_id"]:
            clauses.append("(v.branch_id = %s::uuid OR b.branch_id = %s::uuid)")
            params.extend([filters["branch_id"], filters["branch_id"]])
        if filters["vehicle_id"]:
            clauses.append("v.id = %s::uuid")
            params.append(filters["vehicle_id"])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cur.execute(
            f"""
            SELECT v.id::text, v.registration_number, v.model, v.status,
                   COUNT(a.id) FILTER (WHERE a.id IS NOT NULL),
                   COUNT(*) FILTER (WHERE a.status = 'completed')
            FROM vehicles v
            LEFT JOIN booking_assignments a ON a.vehicle_id = v.id
            LEFT JOIN bookings b ON b.id = a.booking_id
            {where}
            GROUP BY v.id, v.registration_number, v.model, v.status
            ORDER BY v.registration_number NULLS LAST
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        rows = [
            {
                "vehicle_id": r[0],
                "registration_number": r[1],
                "model": r[2],
                "status": r[3],
                "assigned_duties": int(r[4] or 0),
                "completed_trips": int(r[5] or 0),
            }
            for r in cur.fetchall()
        ]
        return {"ok": True, "rows": rows, "summary": {"vehicles": len(rows)}}

    return pg._actor_work(user_id, work)


def branch_company_report(user_id, **kwargs):
    filters, err = _filters(**kwargs)
    if err:
        return err

    def work(cur):
        where, params = _booking_where(filters)
        cur.execute(
            f"""
            SELECT b.branch_id::text,
                   COUNT(*) AS bookings,
                   COUNT(*) FILTER (WHERE b.status = 'completed') AS completed,
                   COUNT(*) FILTER (WHERE b.status = 'cancelled') AS cancelled
            FROM bookings b
            {where}
            GROUP BY b.branch_id
            ORDER BY b.branch_id
            """,
            params,
        )
        maps = pg._branch_maps()
        by_id = maps[1] if maps else {}
        by_branch = []
        for r in cur.fetchall():
            branch = by_id.get(r[0]) or {}
            by_branch.append(
                {
                    "branch_id": r[0],
                    "branch_code": branch.get("code"),
                    "branch_name": branch.get("name"),
                    "bookings": int(r[1]),
                    "completed": int(r[2]),
                    "cancelled": int(r[3]),
                }
            )
        by_branch.sort(key=lambda row: row.get("branch_code") or "")
        cur.execute(
            f"""
            SELECT c.id::text, c.name, COUNT(*) AS bookings,
                   COUNT(*) FILTER (WHERE b.status = 'completed') AS completed
            FROM bookings b
            JOIN companies c ON c.id = b.company_id
            {where}
            GROUP BY c.id, c.name
            ORDER BY c.name
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        by_company = [
            {
                "company_id": r[0],
                "company_name": r[1],
                "bookings": int(r[2]),
                "completed": int(r[3]),
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "by_branch": by_branch,
            "by_company": by_company,
            "summary": {
                "branches": len(by_branch),
                "companies": len(by_company),
            },
        }

    return pg._actor_work(user_id, work)


def invoice_report(user_id, **kwargs):
    filters, err = _filters(**{k: kwargs.get(k) for k in (
        "date_from", "date_to", "branch_id", "company_id"
    )})
    if err:
        return err
    invoice_status = (kwargs.get("invoice_status") or "").strip().lower() or None

    def work(cur):
        clauses = ["TRUE"]
        params = []
        if filters["branch_id"]:
            clauses.append("i.branch_id = %s::uuid")
            params.append(filters["branch_id"])
        if filters["company_id"]:
            clauses.append("i.company_id = %s::uuid")
            params.append(filters["company_id"])
        if filters["date_from"]:
            clauses.append("COALESCE(i.issued_at::date, i.created_at::date) >= %s")
            params.append(filters["date_from"])
        if filters["date_to"]:
            clauses.append("COALESCE(i.issued_at::date, i.created_at::date) <= %s")
            params.append(filters["date_to"])
        if invoice_status == "draft":
            clauses.append("i.issued_at IS NULL AND i.voided_at IS NULL")
        elif invoice_status == "issued":
            clauses.append("i.issued_at IS NOT NULL AND i.voided_at IS NULL")
        elif invoice_status == "void":
            clauses.append("i.voided_at IS NOT NULL")
        elif invoice_status == "overdue":
            clauses.append(
                "i.issued_at IS NOT NULL AND i.voided_at IS NULL "
                "AND i.due_date < CURRENT_DATE AND bal.outstanding_amount > 0"
            )
        elif invoice_status not in (None, ""):
            return {"ok": False, "error": "invalid", "message": "Invoice status filter is not valid."}
        where = "WHERE " + " AND ".join(clauses)
        cur.execute(
            f"""
            SELECT
                COALESCE(SUM(bal.total_amount) FILTER (
                    WHERE i.issued_at IS NOT NULL AND i.voided_at IS NULL), 0),
                COALESCE(SUM(bal.paid_amount) FILTER (
                    WHERE i.issued_at IS NOT NULL AND i.voided_at IS NULL), 0),
                COALESCE(SUM(bal.outstanding_amount) FILTER (
                    WHERE i.issued_at IS NOT NULL AND i.voided_at IS NULL), 0),
                COUNT(*) FILTER (
                    WHERE i.issued_at IS NOT NULL AND i.voided_at IS NULL
                      AND bal.outstanding_amount > 0
                      AND bal.paid_amount > 0),
                COUNT(*) FILTER (
                    WHERE i.issued_at IS NOT NULL AND i.voided_at IS NULL
                      AND i.due_date < CURRENT_DATE AND bal.outstanding_amount > 0),
                COUNT(*) FILTER (WHERE i.voided_at IS NOT NULL),
                COUNT(*) FILTER (WHERE i.issued_at IS NULL AND i.voided_at IS NULL)
            FROM invoices i
            LEFT JOIN invoice_balances bal ON bal.invoice_id = i.id
            {where}
            """,
            params,
        )
        s = cur.fetchone()
        cur.execute(
            f"""
            SELECT i.id::text, i.invoice_number, c.name, i.branch_id::text,
                   CASE
                     WHEN i.voided_at IS NOT NULL THEN 'void'
                     WHEN i.issued_at IS NULL THEN 'draft'
                     ELSE 'issued'
                   END AS status,
                   bal.total_amount, bal.paid_amount, bal.outstanding_amount,
                   i.issued_at::date::text, i.due_date::text
            FROM invoices i
            LEFT JOIN invoice_balances bal ON bal.invoice_id = i.id
            LEFT JOIN companies c ON c.id = i.company_id
            {where}
            ORDER BY COALESCE(i.issued_at, i.created_at) DESC
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        maps = pg._branch_maps()
        by_id = maps[1] if maps else {}
        rows = [
            {
                "invoice_id": r[0],
                "invoice_number": r[1],
                "company_name": r[2],
                "branch_code": _branch_label(r[3], by_id),
                "status": r[4],
                "total_amount": _money(r[5]),
                "paid_amount": _money(r[6]),
                "outstanding_amount": _money(r[7]),
                "issued_on": r[8],
                "due_date": r[9],
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "summary": {
                "issued_total": _money(s[0]),
                "collected": _money(s[1]),
                "outstanding": _money(s[2]),
                "partially_paid_count": int(s[3] or 0),
                "overdue_count": int(s[4] or 0),
                "void_count": int(s[5] or 0),
                "draft_count": int(s[6] or 0),
            },
            "rows": rows,
            "note": "Issued totals exclude draft and void invoices. Collections exclude reversed payments via invoice_balances.",
        }

    return pg._actor_work(user_id, work)


def payment_report(user_id, **kwargs):
    filters, err = _filters(**{k: kwargs.get(k) for k in (
        "date_from", "date_to", "branch_id", "company_id"
    )})
    if err:
        return err
    include_reversed = str(kwargs.get("include_reversed") or "").lower() in ("1", "true", "yes")

    def work(cur):
        clauses = ["TRUE"]
        params = []
        if filters["branch_id"]:
            clauses.append("i.branch_id = %s::uuid")
            params.append(filters["branch_id"])
        if filters["company_id"]:
            clauses.append("i.company_id = %s::uuid")
            params.append(filters["company_id"])
        if filters["date_from"]:
            clauses.append("p.paid_on >= %s")
            params.append(filters["date_from"])
        if filters["date_to"]:
            clauses.append("p.paid_on <= %s")
            params.append(filters["date_to"])
        if not include_reversed:
            clauses.append("p.reversed_at IS NULL")
        where = "WHERE " + " AND ".join(clauses)
        cur.execute(
            f"""
            SELECT
                COALESCE(SUM(p.amount) FILTER (WHERE p.reversed_at IS NULL), 0),
                COALESCE(SUM(p.amount) FILTER (WHERE p.reversed_at IS NOT NULL), 0),
                COUNT(*) FILTER (WHERE p.reversed_at IS NULL),
                COUNT(*) FILTER (WHERE p.reversed_at IS NOT NULL)
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            {where}
            """,
            params,
        )
        s = cur.fetchone()
        cur.execute(
            f"""
            SELECT p.id::text, p.paid_on::text, i.invoice_number, c.name,
                   p.amount, p.method, p.reference,
                   CASE WHEN p.reversed_at IS NULL THEN 'active' ELSE 'reversed' END,
                   p.reversed_at::date::text
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            LEFT JOIN companies c ON c.id = i.company_id
            {where}
            ORDER BY p.paid_on DESC, p.id DESC
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        rows = [
            {
                "payment_id": r[0],
                "paid_on": r[1],
                "invoice_number": r[2],
                "company_name": r[3],
                "amount": _money(r[4]),
                "method": r[5],
                "reference": r[6],
                "status": r[7],
                "reversed_on": r[8],
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "summary": {
                "collected_active": _money(s[0]),
                "reversed_total": _money(s[1]),
                "active_count": int(s[2] or 0),
                "reversed_count": int(s[3] or 0),
            },
            "rows": rows,
        }

    return pg._actor_work(user_id, work)


def payout_report(user_id, **kwargs):
    filters, err = _filters(**{k: kwargs.get(k) for k in (
        "date_from", "date_to", "branch_id", "driver_id"
    )})
    if err:
        return err
    status = (kwargs.get("payout_status") or "").strip().lower() or None
    if status and status not in ("pending", "paid", "cancelled"):
        return {"ok": False, "error": "invalid", "message": "Payout status filter is not valid."}

    def work(cur):
        clauses = ["TRUE"]
        params = []
        if filters["branch_id"]:
            clauses.append("b.branch_id = %s::uuid")
            params.append(filters["branch_id"])
        if filters["driver_id"]:
            clauses.append("p.driver_id = %s::uuid")
            params.append(filters["driver_id"])
        if filters["date_from"]:
            clauses.append("COALESCE(p.paid_at::date, p.created_at::date) >= %s")
            params.append(filters["date_from"])
        if filters["date_to"]:
            clauses.append("COALESCE(p.paid_at::date, p.created_at::date) <= %s")
            params.append(filters["date_to"])
        if status:
            clauses.append("p.status = %s")
            params.append(status)
        where = "WHERE " + " AND ".join(clauses)
        cur.execute(
            f"""
            SELECT
                COALESCE(SUM(p.amount) FILTER (WHERE p.status = 'pending'), 0),
                COALESCE(SUM(p.amount) FILTER (WHERE p.status = 'paid'), 0),
                COALESCE(SUM(p.amount) FILTER (WHERE p.status = 'cancelled'), 0),
                COUNT(*) FILTER (WHERE p.status = 'pending'),
                COUNT(*) FILTER (WHERE p.status = 'paid'),
                COUNT(*) FILTER (WHERE p.status = 'cancelled')
            FROM driver_payouts p
            JOIN bookings b ON b.id = p.booking_id
            {where}
            """,
            params,
        )
        s = cur.fetchone()
        cur.execute(
            f"""
            SELECT p.id::text, d.display_name, b.source_booking_id, b.trip_date::text,
                   p.amount, p.status, p.reference, p.paid_at::date::text
            FROM driver_payouts p
            JOIN bookings b ON b.id = p.booking_id
            LEFT JOIN drivers d ON d.id = p.driver_id
            {where}
            ORDER BY COALESCE(p.paid_at, p.created_at) DESC
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        rows = [
            {
                "payout_id": r[0],
                "driver_name": r[1],
                "source_booking_id": r[2],
                "trip_date": r[3],
                "amount": _money(r[4]),
                "status": r[5],
                "reference": r[6],
                "paid_on": r[7],
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "summary": {
                "pending_amount": _money(s[0]),
                "paid_amount": _money(s[1]),
                "cancelled_amount": _money(s[2]),
                "pending_count": int(s[3] or 0),
                "paid_count": int(s[4] or 0),
                "cancelled_count": int(s[5] or 0),
            },
            "rows": rows,
        }

    return pg._actor_work(user_id, work)


def expense_report(user_id, **kwargs):
    filters, err = _filters(**{k: kwargs.get(k) for k in (
        "date_from", "date_to", "branch_id", "company_id"
    )})
    if err:
        return err
    category = (kwargs.get("category") or "").strip() or None
    status = (kwargs.get("expense_status") or "").strip().lower() or None

    def work(cur):
        clauses = ["TRUE"]
        params = []
        if filters["branch_id"]:
            clauses.append("e.branch_id = %s::uuid")
            params.append(filters["branch_id"])
        if filters["company_id"]:
            clauses.append("e.company_id = %s::uuid")
            params.append(filters["company_id"])
        if filters["date_from"]:
            clauses.append("e.expense_date >= %s")
            params.append(filters["date_from"])
        if filters["date_to"]:
            clauses.append("e.expense_date <= %s")
            params.append(filters["date_to"])
        if category:
            clauses.append("e.category ILIKE %s")
            params.append(category)
        if status:
            clauses.append("e.status = %s")
            params.append(status)
        where = "WHERE " + " AND ".join(clauses)
        cur.execute(
            f"""
            SELECT
                COALESCE(SUM(e.amount) FILTER (WHERE e.status <> 'cancelled'), 0),
                COUNT(*) FILTER (WHERE e.status <> 'cancelled'),
                COUNT(*) FILTER (WHERE e.status = 'cancelled')
            FROM expenses e
            {where}
            """,
            params,
        )
        s = cur.fetchone()
        cur.execute(
            f"""
            SELECT e.id::text, e.expense_date::text, e.category, e.description,
                   e.amount, e.status, e.branch_id::text, c.name
            FROM expenses e
            LEFT JOIN companies c ON c.id = e.company_id
            {where}
            ORDER BY e.expense_date DESC, e.created_at DESC
            LIMIT {_REPORT_LIMIT}
            """,
            params,
        )
        maps = pg._branch_maps()
        by_id = maps[1] if maps else {}
        rows = [
            {
                "expense_id": r[0],
                "expense_date": r[1],
                "category": r[2],
                "description": r[3],
                "amount": _money(r[4]),
                "status": r[5],
                "branch_code": _branch_label(r[6], by_id),
                "company_name": r[7],
            }
            for r in cur.fetchall()
        ]
        return {
            "ok": True,
            "summary": {
                "active_total": _money(s[0]),
                "active_count": int(s[1] or 0),
                "cancelled_count": int(s[2] or 0),
            },
            "rows": rows,
        }

    return pg._actor_work(user_id, work)


def company_settlement_report(user_id, **kwargs):
    """Reuse finance settlement aggregates; requires company_id."""
    import operations_finance

    filters, err = _filters(**{k: kwargs.get(k) for k in (
        "date_from", "date_to", "branch_id", "company_id"
    )})
    if err:
        return err
    if not filters["company_id"]:
        return {
            "ok": False,
            "error": "invalid",
            "message": "Company settlement report requires company_id.",
        }
    result = operations_finance.company_settlement(
        user_id, filters["company_id"], branch_id=filters["branch_id"]
    )
    if not result or not result.get("ok"):
        return result
    settlement = result.get("settlement") or {}
    billable = operations_finance.list_billable_bookings(
        user_id, filters["company_id"], branch_id=filters["branch_id"]
    )
    rows = []
    if billable and billable.get("ok"):
        for row in billable.get("bookings") or []:
            rows.append({
                "source_booking_id": row.get("source_booking_id") or row.get("booking_id"),
                "trip_date": row.get("trip_date"),
                "amount": row.get("amount") or row.get("customer_amount"),
                "status": row.get("status") or "completed",
                "booking_id": row.get("id") or row.get("booking_id"),
            })
    return {
        "ok": True,
        "summary": {
            "company_name": settlement.get("company_name"),
            "completed_duty_value": settlement.get("completed_duty_value"),
            "invoiced_amount": settlement.get("invoiced_amount"),
            "payments_received": settlement.get("payments_received"),
            "outstanding_balance": settlement.get("outstanding_balance"),
            "pending_driver_payouts": settlement.get("pending_driver_payouts"),
            "paid_driver_payouts": settlement.get("paid_driver_payouts"),
            "billable_rows": len(rows),
        },
        "settlement": settlement,
        "rows": rows[:_REPORT_LIMIT],
        "notes": [
            "Settlement uses existing finance calculations (invoice_balances).",
            "Date-range filters do not alter settlement totals; use Finance for period detail.",
        ],
    }


def financial_summary(user_id, **kwargs):
    """Combines issued invoice balances, active payments context, payouts, expenses.

    Net position = collected - paid payouts - non-cancelled expenses.
    Issued invoice totals are receivables, not cash revenue.
    """
    inv = invoice_report(user_id, **kwargs)
    if not inv or not inv.get("ok"):
        return inv
    pay = payment_report(user_id, **kwargs)
    if not pay or not pay.get("ok"):
        return pay
    pout = payout_report(user_id, **kwargs)
    if not pout or not pout.get("ok"):
        return pout
    exp = expense_report(user_id, **kwargs)
    if not exp or not exp.get("ok"):
        return exp

    collected = Decimal(pay["summary"]["collected_active"])
    paid_payouts = Decimal(pout["summary"]["paid_amount"])
    expenses = Decimal(exp["summary"]["active_total"])
    return {
        "ok": True,
        "summary": {
            "issued_invoices": inv["summary"]["issued_total"],
            "collected_payments": pay["summary"]["collected_active"],
            "outstanding_receivables": inv["summary"]["outstanding"],
            "driver_payouts_paid": pout["summary"]["paid_amount"],
            "driver_payouts_pending": pout["summary"]["pending_amount"],
            "expenses": exp["summary"]["active_total"],
            "net_cash_position": _money(collected - paid_payouts - expenses),
        },
        "notes": [
            "Issued invoice totals are not cash revenue.",
            "Collected payments exclude reversed rows.",
            "Net cash position = active collections − paid payouts − non-cancelled expenses.",
        ],
    }


_REPORT_DISPATCH = {
    "bookings": booking_report,
    "trips": trip_report,
    "drivers": driver_performance_report,
    "vehicles": vehicle_utilization_report,
    "branch-company": branch_company_report,
    "invoices": invoice_report,
    "payments": payment_report,
    "payouts": payout_report,
    "expenses": expense_report,
    "company-settlement": company_settlement_report,
    "financial-summary": financial_summary,
}


def run_report(user_id, report_name, **kwargs):
    fn = _REPORT_DISPATCH.get(report_name)
    if fn is None:
        return {"ok": False, "error": "invalid", "message": "Unknown report."}
    return fn(user_id, **kwargs)


def export_report_csv(user_id, report_name, **kwargs):
    result = run_report(user_id, report_name, **kwargs)
    if result is None:
        return None
    if not result.get("ok"):
        return result
    stamp = date.today().isoformat()
    if report_name == "bookings":
        headers = ["trip_date", "source_booking_id", "employee_name", "origin", "status", "branch_code", "company_name", "booking_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-bookings-{stamp}.csv", headers, rows)
    if report_name == "trips":
        headers = ["trip_date", "source_booking_id", "status", "started_at", "ended_at", "duration_minutes", "start_km", "end_km", "total_km", "driver_name", "vehicle_registration", "booking_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-trips-{stamp}.csv", headers, rows)
    if report_name == "drivers":
        headers = ["driver_name", "active", "verification_status", "assigned_duties", "accepted", "rejected", "completed", "withdrawn_or_superseded", "driver_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-driver-performance-{stamp}.csv", headers, rows)
    if report_name == "vehicles":
        headers = ["registration_number", "model", "status", "assigned_duties", "completed_trips", "vehicle_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-vehicle-utilization-{stamp}.csv", headers, rows)
    if report_name == "branch-company":
        headers = ["section", "name", "bookings", "completed", "cancelled", "id"]
        rows = []
        for r in result.get("by_branch") or []:
            rows.append(["branch", r.get("branch_code"), r.get("bookings"), r.get("completed"), r.get("cancelled"), ""])
        for r in result.get("by_company") or []:
            rows.append(["company", r.get("company_name"), r.get("bookings"), r.get("completed"), "", r.get("company_id")])
        return csv_response_rows(f"smt-branch-company-{stamp}.csv", headers, rows)
    if report_name == "invoices":
        headers = ["invoice_number", "company_name", "branch_code", "status", "total_amount", "paid_amount", "outstanding_amount", "issued_on", "due_date", "invoice_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-invoices-{stamp}.csv", headers, rows)
    if report_name == "payments":
        headers = ["paid_on", "invoice_number", "company_name", "amount", "method", "reference", "status", "reversed_on", "payment_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-payments-{stamp}.csv", headers, rows)
    if report_name == "payouts":
        headers = ["driver_name", "source_booking_id", "trip_date", "amount", "status", "reference", "paid_on", "payout_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-payouts-{stamp}.csv", headers, rows)
    if report_name == "expenses":
        headers = ["expense_date", "category", "description", "amount", "status", "branch_code", "company_name", "expense_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-expenses-{stamp}.csv", headers, rows)
    if report_name == "company-settlement":
        headers = ["source_booking_id", "trip_date", "amount", "status", "booking_id"]
        rows = [[r.get(h) for h in headers] for r in result.get("rows") or []]
        return csv_response_rows(f"smt-company-settlement-{stamp}.csv", headers, rows)
    if report_name == "financial-summary":
        s = result.get("summary") or {}
        headers = ["metric", "value"]
        rows = [[k, v] for k, v in s.items()]
        return csv_response_rows(f"smt-financial-summary-{stamp}.csv", headers, rows)
    return {"ok": False, "error": "invalid", "message": "CSV export is not available for this report."}
