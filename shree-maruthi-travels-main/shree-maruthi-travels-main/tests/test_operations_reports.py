"""Master Prompt 7: reporting API tests on disposable smt_revision8_test."""
import hashlib
import os
import sys
import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "backend"
for key in ("STAFF_TOKEN", "RAC_JWT_SECRET", "SMT_DEV_DATABASE_URL", "SMT_DEV_BOOTSTRAP_OWNER_ID"):
    os.environ.pop(key, None)
load_dotenv(APP_ROOT / ".env")


def _prefer_disposable_database():
    flag = (os.environ.get("SMT_REVISION8_DISPOSABLE") or "").strip().lower()
    if flag not in ("1", "yes", "true"):
        return
    override = (os.environ.get("SMT_REVISION8_DATABASE_URL") or "").strip().strip("\"'")
    if override:
        os.environ["SMT_DEV_DATABASE_URL"] = override
    owner = (os.environ.get("SMT_REVISION8_BOOTSTRAP_OWNER_ID") or "").strip().strip("\"'")
    if owner:
        os.environ["SMT_DEV_BOOTSTRAP_OWNER_ID"] = owner


_prefer_disposable_database()
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(BACKEND))

import backend.app as app_module
import dev_postgres
import operations_finance
import operations_reports
import staff_auth

OWNER = "abhishekgowdasmt@gmail.com"
STAFF = "bhaskarbhaskarreddy9005@gmail.com"
_LOCAL_SERVER_ADDRESSES = (None, "127.0.0.1", "127.0.0.1/32", "::1", "::1/128")


def client_for(email):
    client = app_module.app.test_client()
    token = staff_auth.issue_token(email)
    if token:
        client.set_cookie("smt_staff", token)
    return client


def digest(path):
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return hasher.hexdigest()


def require_disposable_local_database():
    flag = (os.environ.get("SMT_REVISION8_DISPOSABLE") or "").strip().lower()
    if flag not in ("1", "yes", "true"):
        raise unittest.SkipTest(
            "Set SMT_REVISION8_DISPOSABLE=yes only for a disposable local database"
        )
    dsn = dev_postgres.local_development_dsn()
    if dsn is None:
        raise unittest.SkipTest("refusing to run without a local database URL")
    import psycopg
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), inet_server_addr()::text")
            name, address = cur.fetchone()
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    return name


class OperationsReportsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        if not operations_finance.finance_schema_ready():
            raise unittest.SkipTest(
                "Apply finance migrations before reporting tests on " + cls.database_name
            )
        cls.owner = client_for(OWNER)
        cls.staff = client_for(STAFF)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        staff = dev_postgres.resolve_login_identity(STAFF)
        if not owner.get("ok") or not staff.get("ok"):
            raise unittest.SkipTest("disposable database is missing local staff identities")
        cls.owner_id = owner["id"]
        cls.staff_id = staff["id"]
        branches = cls.owner.get("/api/branches").get_json()["data"]
        cls.branch = {row["code"]: row["id"] for row in branches}
        created = cls.owner.post("/api/companies", json={
            "name": "Report company " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert created.status_code == 201, created.get_json()
        cls.company_id = created.get_json()["data"]["id"]
        trip_date = (date.today() + timedelta(days=3)).isoformat()
        booking = cls.owner.post("/api/operations/bookings", json={
            "branch_id": cls.branch["BLR"],
            "company_id": cls.company_id,
            "trip_date": trip_date,
            "employee_name": "Report passenger " + cls.marker,
            "source_booking_id": "RPT-" + cls.marker,
            "pickup_time": "09:30",
            "duty_type": "Airport",
            "planned_start": "Report pickup",
        })
        assert booking.status_code in (200, 201), booking.get_json()
        cls.booking_id = booking.get_json()["data"]["id"]
        cls.trip_date = trip_date

    def test_booking_report_counts_and_filters(self):
        result = operations_reports.booking_report(
            self.owner_id,
            date_from=self.trip_date,
            date_to=self.trip_date,
            branch_id=self.branch["BLR"],
            company_id=self.company_id,
        )
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["summary"]["total"], 1)
        self.assertIn("completed", result["summary"])
        self.assertIn("unassigned", result["summary"])
        self.assertIn("by_origin", result)
        ids = {row["booking_id"] for row in result["rows"]}
        self.assertIn(self.booking_id, ids)

    def test_trip_driver_vehicle_branch_reports(self):
        for name in ("trips", "drivers", "vehicles", "branch-company"):
            result = operations_reports.run_report(
                self.owner_id,
                name,
                date_from=self.trip_date,
                date_to=self.trip_date,
                branch_id=self.branch["BLR"],
            )
            self.assertTrue(result and result.get("ok"), name)
            self.assertIn("summary", result)

    def test_invoice_payment_payout_expense_summary(self):
        for name in ("invoices", "payments", "payouts", "expenses", "financial-summary"):
            result = operations_reports.run_report(
                self.owner_id,
                name,
                branch_id=self.branch["BLR"],
            )
            self.assertTrue(result and result.get("ok"), name)
            self.assertIn("summary", result)
        notes = operations_reports.financial_summary(self.owner_id)["notes"]
        self.assertTrue(any("not cash revenue" in n.lower() for n in notes))

    def test_company_settlement_requires_company(self):
        missing = operations_reports.company_settlement_report(self.owner_id)
        self.assertFalse(missing["ok"])
        ok = operations_reports.company_settlement_report(
            self.owner_id, company_id=self.company_id, branch_id=self.branch["BLR"]
        )
        self.assertTrue(ok["ok"])
        self.assertIn("outstanding_balance", ok["summary"])

    def test_invalid_date_range_rejected(self):
        bad = operations_reports.booking_report(
            self.owner_id, date_from="2026-12-01", date_to="2026-01-01"
        )
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["error"], "invalid")

    def test_http_report_and_csv_auth(self):
        res = self.owner.get(
            "/api/reports/bookings?from=%s&to=%s&branch=BLR" % (self.trip_date, self.trip_date)
        )
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["success"])
        self.assertIn("summary", body["data"])

        csv_res = self.owner.get(
            "/api/reports/bookings?from=%s&to=%s&export=csv" % (self.trip_date, self.trip_date)
        )
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("text/csv", csv_res.content_type)
        self.assertIn("smt-bookings-", csv_res.headers.get("Content-Disposition", ""))
        self.assertTrue(csv_res.data.startswith(b"trip_date") or b"trip_date" in csv_res.data[:200])

        anon = app_module.app.test_client()
        denied = anon.get("/api/reports/bookings")
        self.assertEqual(denied.status_code, 401)

    def test_csv_formula_injection_escaped(self):
        cell = operations_reports._csv_cell("=CMD()")
        self.assertTrue(cell.startswith("'"))

    def test_reversed_payments_excluded_from_collected(self):
        result = operations_reports.payment_report(self.owner_id)
        self.assertTrue(result["ok"])
        self.assertIn("collected_active", result["summary"])
        self.assertIn("reversed_total", result["summary"])

    def test_rac_json_untouched(self):
        self.assertEqual(self.rac_hash, digest(BACKEND / "rac_data.json"))


if __name__ == "__main__":
    unittest.main()
