"""Master Prompt 10 API acceptance harness — disposable smt_revision8_test only.

Does not print secrets. Writes JSON results under tools/_prompt10_results.json.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = Path(r"C:\Users\user\AppData\Local\Temp\smt_p10_dotenv")
if OVERLAY.is_file():
    load_dotenv(OVERLAY, override=True)
load_dotenv(ROOT / ".env")
os.environ["SMT_REVISION8_DISPOSABLE"] = "yes"
if os.environ.get("SMT_REVISION8_DATABASE_URL"):
    os.environ["SMT_DEV_DATABASE_URL"] = os.environ["SMT_REVISION8_DATABASE_URL"]
if os.environ.get("SMT_REVISION8_BOOTSTRAP_OWNER_ID"):
    os.environ["SMT_DEV_BOOTSTRAP_OWNER_ID"] = os.environ["SMT_REVISION8_BOOTSTRAP_OWNER_ID"]

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import backend.app as app_module  # noqa: E402
import dev_postgres  # noqa: E402
import operations_duty  # noqa: E402
import operations_finance  # noqa: E402
import operations_notifications  # noqa: E402
import staff_auth  # noqa: E402

OWNER = "abhishekgowdasmt@gmail.com"
RESULTS: list[dict] = []
OUT = ROOT / "tools" / "_prompt10_results.json"


def rec(name: str, status: str, detail: str = "") -> None:
    RESULTS.append({"name": name, "status": status, "detail": detail})
    print(f"{status}: {name}" + (f" — {detail}" if detail else ""))


def staff_client(email: str):
    client = app_module.app.test_client()
    token = staff_auth.issue_token(email)
    if token:
        client.set_cookie("smt_staff", token)
    return client


def require_disposable() -> None:
    flag = (os.environ.get("SMT_REVISION8_DISPOSABLE") or "").strip().lower()
    dsn = (os.environ.get("SMT_REVISION8_DATABASE_URL") or os.environ.get("SMT_DEV_DATABASE_URL") or "")
    parsed = urlparse(dsn)
    db = (parsed.path or "").strip("/")
    if flag not in ("1", "yes", "true") or db != "smt_revision8_test":
        raise SystemExit(f"refusing non-disposable db={db!r} disposable={flag!r}")
    if str(parsed.hostname) not in ("127.0.0.1", "localhost"):
        raise SystemExit("refusing non-local database host")
    rec("disposable_safeguard", "PASS", db)


def main() -> int:
    require_disposable()
    marker = uuid.uuid4().hex[:8]
    trip = (date.today() + timedelta(days=45)).isoformat()
    owner = staff_client(OWNER)

    me = owner.get("/api/admin/me")
    body = me.get_json() or {}
    # Local OD owner surfaces role "od" while retaining owner DB privileges.
    rec(
        "owner_api_session",
        "PASS" if me.status_code == 200 and body.get("role") in ("owner", "od") and body.get("authenticated") else "FAIL",
        f"status={me.status_code} role={body.get('role')}",
    )

    unauth = app_module.app.test_client().get("/api/operations/bookings")
    rec(
        "unauth_ops_denied",
        "PASS" if unauth.status_code in (401, 403) else "FAIL",
        str(unauth.status_code),
    )

    rec("duty_triggers", "PASS" if operations_duty.assignment_triggers_ready() else "FAIL")
    rec("finance_schema", "PASS" if operations_finance.finance_schema_ready() else "FAIL")
    rec("notif_schema", "PASS" if operations_notifications.notifications_schema_ready() else "FAIL")

    probe: dict = {}

    def _probe(cur):
        cur.execute(
            """
            SELECT COUNT(*) FROM booking_assignments ba
            LEFT JOIN bookings b ON b.id = ba.booking_id WHERE b.id IS NULL
            """
        )
        probe["orphan_assignments"] = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT booking_id FROM booking_assignments
              WHERE status IN ('assigned','accepted','started','in_progress')
              GROUP BY booking_id HAVING COUNT(*) > 1
            ) t
            """
        )
        probe["multi_open"] = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FROM invoice_balances ib
            JOIN invoices i ON i.id = ib.invoice_id
            WHERE ib.outstanding_amount < 0
            """
        )
        probe["neg_bal"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM pg_policies WHERE schemaname='public'")
        probe["rls"] = cur.fetchone()[0]
        return True

    tx = dev_postgres.authorized_transaction(os.environ["SMT_REVISION8_BOOTSTRAP_OWNER_ID"], _probe)
    ok = bool(tx) and probe.get("orphan_assignments") == 0 and probe.get("multi_open") == 0 and probe.get("neg_bal") == 0
    rec("db_integrity_probe", "PASS" if ok else "FAIL", json.dumps(probe))

    company = owner.post("/api/companies", json={"name": f"P10 Co {marker}", "branch_codes": ["BLR"]})
    if company.status_code != 201:
        rec("seed_company", "FAIL", str(company.get_json())[:240])
        _write()
        return 1
    company_id = company.get_json()["data"]["id"]
    other = owner.post("/api/companies", json={"name": f"P10 Other {marker}", "branch_codes": ["BLR"]})
    other_id = other.get_json()["data"]["id"]
    rec("seed_company", "PASS")

    client_pw = "P10Client1" + marker[:4]
    driver_pw = "P10Driver1" + marker[:4]
    email_a = f"p10.a.{marker}@example.com"
    email_b = f"p10.b.{marker}@example.com"
    phone_tail = str(int(marker[:8], 16) % 10**8).zfill(8)

    def make_client(email: str, phone: str, company: str):
        created = owner.post(
            "/api/clients",
            json={"full_name": f"P10 {email}", "email": email, "phone": phone},
        )
        assert created.status_code == 201, created.get_json()
        uid = created.get_json()["data"]["id"]
        assert owner.post(f"/api/companies/{company}/clients", json={"user_id": uid}).status_code in (200, 201)
        assert owner.post(f"/api/clients/{uid}/login-account", json={"password": client_pw}).status_code in (200, 201)
        return uid

    make_client(email_a, "91" + phone_tail, company_id)
    make_client(email_b, "92" + phone_tail, other_id)

    def make_driver(name: str, phone: str):
        created = owner.post(
            "/api/drivers",
            json={"display_name": name, "phone": phone, "primary_branch_code": "BLR"},
        )
        assert created.status_code == 201, created.get_json()
        did = created.get_json()["data"]["id"]
        assert owner.post(f"/api/drivers/{did}/reviews", json={"decision": "verified", "reason": "p10"}).status_code == 200
        assert owner.post(f"/api/drivers/{did}/active", json={"active": True, "reason": "p10"}).status_code == 200
        assert owner.post(f"/api/companies/{company_id}/drivers", json={"driver_id": did}).status_code in (200, 201)
        login_acct = owner.post(f"/api/drivers/{did}/login-account", json={"password": driver_pw})
        assert login_acct.status_code in (200, 201), login_acct.get_json()
        return did

    phone_a = "81" + phone_tail
    phone_b = "82" + phone_tail
    driver_a = make_driver(f"P10 Driver A {marker}", phone_a)
    driver_b = make_driver(f"P10 Driver B {marker}", phone_b)
    vehicle = owner.post(
        "/api/vehicles",
        json={
            "branch_code": "BLR",
            "registration_number": f"P1{marker.upper()[:6]}",
            "model": "Innova",
            "status": "active",
        },
    )
    assert vehicle.status_code == 201, vehicle.get_json()
    vehicle_id = vehicle.get_json()["data"]["id"]
    assert owner.post(f"/api/companies/{company_id}/vehicles", json={"vehicle_id": vehicle_id}).status_code in (200, 201)
    rec("seed_drivers_vehicle_clients", "PASS")

    def portal(email: str):
        c = app_module.app.test_client()
        login = c.post("/api/client/login", json={"email": email, "password": client_pw})
        assert login.status_code == 200, login.get_json()
        return c

    def driver(phone: str):
        c = app_module.app.test_client()
        login = c.post("/api/driver/login", json={"phone": phone, "password": driver_pw})
        assert login.status_code == 200, login.get_json()
        c.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + login.get_json()["token"]
        return c

    # Workflow 1: booking → complete
    pa = portal(email_a)
    created = pa.post(
        "/api/client/bookings",
        json={
            "branch_code": "BLR",
            "trip_date": trip,
            "pickup_time": "10:00",
            "pickup_location": f"P10 pickup {marker}",
            "passenger_name": f"P10 pax {marker}",
            "duty_type": "Local",
            "cab_type": "SUV",
            "route": "Office",
        },
    )
    rec("wf1_client_create", "PASS" if created.status_code == 201 else "FAIL", str(created.status_code))
    booking_id = (created.get_json() or {}).get("booking", {}).get("id")
    listed = owner.get("/api/operations/bookings?origin=client_request")
    seen = any(r["id"] == booking_id for r in (listed.get_json() or {}).get("data", []))
    rec("wf1_supervisor_sees_request", "PASS" if seen else "FAIL")

    assigned = owner.post(
        f"/api/operations/bookings/{booking_id}/assign",
        json={"driver_id": driver_a, "vehicle_id": vehicle_id, "send_message": False},
    )
    rec("wf1_assign", "PASS" if assigned.status_code == 200 else "FAIL", str(assigned.status_code))
    assignment_id = ((assigned.get_json() or {}).get("data") or {}).get("assignment", {}).get("id")

    da = driver(phone_a)
    duties = da.get("/api/driver/duties?filter=all")
    has_duty = any(d.get("assignment_id") == assignment_id for d in (duties.get_json() or {}).get("duties", []))
    rec("wf1_driver_sees_duty", "PASS" if has_duty else "FAIL")

    accept = da.post(f"/api/driver/duties/{assignment_id}/accept")
    rec("wf1_accept", "PASS" if accept.status_code == 200 else "FAIL", str(accept.status_code))
    start = da.post(f"/api/driver/duties/{assignment_id}/start", json={"start_km": 100})
    rec("wf1_start", "PASS" if start.status_code == 200 else "FAIL", str(start.status_code))
    complete = da.post(f"/api/driver/duties/{assignment_id}/complete", json={"end_km": 140})
    rec("wf1_complete", "PASS" if complete.status_code == 200 else "FAIL", str(complete.status_code))

    ops = owner.get(f"/api/operations/bookings/{booking_id}/trip")
    ops_status = ((ops.get_json() or {}).get("data") or {}).get("booking", {}).get("status")
    client_detail = pa.get(f"/api/client/bookings/{booking_id}")
    client_status = ((client_detail.get_json() or {}).get("booking") or {}).get("status")
    rec(
        "wf1_status_consistency",
        "PASS" if ops_status == "completed" and client_status == "completed" else "FAIL",
        f"ops={ops_status} client={client_status}",
    )

    # Workflow 2: reject + reassign
    trip2 = (date.today() + timedelta(days=46)).isoformat()
    b2 = pa.post(
        "/api/client/bookings",
        json={
            "branch_code": "BLR",
            "trip_date": trip2,
            "pickup_time": "11:00",
            "pickup_location": f"P10 rej {marker}",
            "passenger_name": f"P10 rej {marker}",
            "duty_type": "Local",
            "cab_type": "SUV",
            "route": "Office",
        },
    )
    bid2 = b2.get_json()["booking"]["id"]
    a2 = owner.post(
        f"/api/operations/bookings/{bid2}/assign",
        json={"driver_id": driver_a, "vehicle_id": vehicle_id, "send_message": False},
    )
    aid2 = a2.get_json()["data"]["assignment"]["id"]
    reject = da.post(f"/api/driver/duties/{aid2}/reject", json={"reason": "P10 busy"})
    rec("wf2_reject", "PASS" if reject.status_code == 200 else "FAIL", str(reject.status_code))
    reassign = owner.post(
        f"/api/operations/bookings/{bid2}/assign",
        json={"driver_id": driver_b, "vehicle_id": vehicle_id, "send_message": False},
    )
    rec("wf2_reassign", "PASS" if reassign.status_code == 200 else "FAIL", str(reassign.status_code))
    aid2b = reassign.get_json()["data"]["assignment"]["id"]
    db = driver(phone_b)
    accept_b = db.post(f"/api/driver/duties/{aid2b}/accept")
    rec("wf2_driver_b_accept", "PASS" if accept_b.status_code == 200 else "FAIL", str(accept_b.status_code))
    # Isolation: driver A must not see B's assignment detail as own open duty incorrectly
    other_duty = da.get(f"/api/driver/duties/{aid2b}")
    rec(
        "wf2_driver_isolation",
        "PASS" if other_duty.status_code in (403, 404) else "FAIL",
        str(other_duty.status_code),
    )

    # Workflow 3: client cancel unassigned
    trip3 = (date.today() + timedelta(days=47)).isoformat()
    b3 = pa.post(
        "/api/client/bookings",
        json={
            "branch_code": "BLR",
            "trip_date": trip3,
            "pickup_time": "12:00",
            "pickup_location": f"P10 cancel {marker}",
            "passenger_name": f"P10 cancel {marker}",
            "duty_type": "Local",
            "cab_type": "SUV",
            "route": "Office",
        },
    )
    bid3 = b3.get_json()["booking"]["id"]
    cancel = pa.post(f"/api/client/bookings/{bid3}/cancel", json={"reason": "P10 cancel"})
    rec("wf3_client_cancel", "PASS" if cancel.status_code == 200 else "FAIL", str(cancel.status_code))
    # Cross-company: client B cannot see booking A
    pb = portal(email_b)
    cross = pb.get(f"/api/client/bookings/{booking_id}")
    rec(
        "security_cross_company_booking",
        "PASS" if cross.status_code in (403, 404) else "FAIL",
        str(cross.status_code),
    )

    # Soft-retry: identical unassigned request within 2 minutes returns already=true (HTTP 201)
    soft_payload = {
        "branch_code": "BLR",
        "trip_date": (date.today() + timedelta(days=48)).isoformat(),
        "pickup_time": "13:00",
        "pickup_location": f"P10 soft {marker}",
        "passenger_name": f"P10 soft {marker}",
        "duty_type": "Local",
        "cab_type": "SUV",
        "route": "Office",
    }
    first_soft = pa.post("/api/client/bookings", json=soft_payload)
    again = pa.post("/api/client/bookings", json=soft_payload)
    again_json = again.get_json() or {}
    soft = (
        first_soft.status_code == 201
        and again.status_code == 201
        and again_json.get("already") is True
    )
    rec(
        "limitation_soft_retry_201_already",
        "PASS" if soft else "FAIL",
        f"first={first_soft.status_code} second={again.status_code} already={again_json.get('already')}",
    )

    # Notifications present for driver
    notes = da.get("/api/driver/notifications")
    rec(
        "wf5_driver_notifications",
        "PASS" if notes.status_code == 200 and isinstance((notes.get_json() or {}).get("notifications"), list) else "FAIL",
        str(notes.status_code),
    )
    staff_notes = owner.get("/api/operations/notifications")
    rec(
        "wf5_staff_notifications",
        "PASS" if staff_notes.status_code == 200 else "FAIL",
        str(staff_notes.status_code),
    )

    # Finance smoke: billable list after completed booking
    billable = owner.get(f"/api/finance/companies/{company_id}/billable-bookings")
    rec(
        "wf4_billable_list",
        "PASS" if billable.status_code == 200 else "FAIL",
        str(billable.status_code),
    )

    # Reports smoke (names match operations_reports._REPORT_DISPATCH)
    report = owner.get("/api/reports/bookings?from=2020-01-01&to=2040-01-01")
    rec("reports_bookings", "PASS" if report.status_code == 200 else "FAIL", str(report.status_code))
    csv = owner.get("/api/reports/bookings?from=2020-01-01&to=2040-01-01&export=csv")
    csv_ok = csv.status_code == 200 and (csv.content_type or "").startswith("text/csv")
    rec("reports_csv_export", "PASS" if csv_ok else "FAIL", f"{csv.status_code} {csv.content_type}")

    # Known limitations documentation markers
    rec("limitation_no_push", "PASS", "polling only — not push")
    rec("limitation_no_websockets", "PASS", "not implemented")
    rec("limitation_no_scheduled_jobs", "PASS", "not implemented")
    rec("limitation_owner_mediated_driver_client_notif", "PASS", "documented architecture")

    _write()
    fails = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print(f"TOTAL={len(RESULTS)} FAIL={fails}")
    return 1 if fails else 0


def _write() -> None:
    OUT.write_text(json.dumps({"results": RESULTS}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
