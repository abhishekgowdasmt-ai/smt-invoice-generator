"""Master Prompt 6: supervisor website / operations dashboard API tests.

Uses disposable smt_revision8_test only. Never targets smt_dev or production.
"""
import hashlib
import os
import sys
import unittest
import uuid
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
import staff_auth

OWNER = "abhishekgowdasmt@gmail.com"
_LOCAL_SERVER_ADDRESSES = (None, "127.0.0.1", "127.0.0.1/32", "::1", "::1/128")


def staff_client(email):
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
            cur.execute(
                """
                SELECT 1 FROM pg_constraint
                WHERE conname = 'bookings_origin_check'
                  AND pg_get_constraintdef(oid) LIKE '%%client_request%%'
                """
            )
            has_client_origin = cur.fetchone() is not None
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    if not has_client_origin:
        raise unittest.SkipTest("Apply client portal / operations migrations to " + name)
    return name


class SupervisorWebsiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        cls.owner = staff_client(OWNER)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        if not owner.get("ok"):
            raise unittest.SkipTest("missing owner identity")
        branches = cls.owner.get("/api/branches").get_json()["data"]
        cls.branch = {row["code"]: row["id"] for row in branches}
        company = cls.owner.post("/api/companies", json={
            "name": "Supervisor Board Co " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert company.status_code == 201, company.get_json()
        cls.company_id = company.get_json()["data"]["id"]

    def test_00_database_is_revision8_test(self):
        self.assertEqual(self.database_name, "smt_revision8_test")

    def test_01_operations_dashboard_counts(self):
        created = self.owner.post("/api/operations/bookings", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "trip_date": "2031-06-01",
            "pickup_time": "09:00",
            "employee_name": "Board passenger " + self.marker,
            "planned_start": "Board pickup " + self.marker,
            "source_booking_id": "SUP-BOARD-" + self.marker,
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        booking_id = created.get_json()["data"]["id"]

        dash = self.owner.get("/api/operations/dashboard")
        self.assertEqual(dash.status_code, 200, dash.get_json())
        body = dash.get_json()
        self.assertTrue(body.get("success"))
        data = body["data"]
        for key in (
            "bookings_today",
            "upcoming_bookings",
            "unassigned_bookings",
            "assigned_duties",
            "accepted_duties",
            "trips_in_progress",
            "completed_today",
            "cancelled_today",
            "client_requests_open",
            "active_drivers",
            "pending_driver_verification",
            "active_vehicles",
        ):
            self.assertIn(key, data)
            self.assertIsInstance(data[key], int)
            self.assertGreaterEqual(data[key], 0)
        self.assertGreaterEqual(data["unassigned_bookings"], 1)
        self.assertGreaterEqual(data["upcoming_bookings"], 1)

        filtered = self.owner.get("/api/operations/dashboard?branch=BLR")
        self.assertEqual(filtered.status_code, 200, filtered.get_json())
        bad = self.owner.get("/api/operations/dashboard?branch=NOT_A_BRANCH")
        self.assertEqual(bad.status_code, 400)

        listed = self.owner.get("/api/operations/bookings?status=unassigned")
        self.assertEqual(listed.status_code, 200)
        rows = listed.get_json()["data"]
        self.assertTrue(any(row["id"] == booking_id for row in rows))

    def test_02_origin_filter_client_request(self):
        listed = self.owner.get("/api/operations/bookings?origin=client_request")
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertTrue(listed.get_json().get("success"))
        for row in listed.get_json()["data"]:
            self.assertEqual(row.get("origin"), "client_request")
        bad = self.owner.get("/api/operations/bookings?origin=not_real")
        self.assertEqual(bad.status_code, 400)

    def test_03_finance_dashboard_still_available(self):
        finance = self.owner.get("/api/finance/dashboard")
        self.assertEqual(finance.status_code, 200, finance.get_json())
        body = finance.get_json()
        self.assertTrue(body.get("success"))
        data = body["data"]
        self.assertIn("outstanding_receivables", data)
        self.assertIn("pending_driver_payouts", data)
        self.assertIn("by_branch", data)
        self.assertIn("by_company", data)

    def test_04_unauthenticated_dashboard_denied(self):
        anon = app_module.app.test_client()
        self.assertEqual(anon.get("/api/operations/dashboard").status_code, 401)
        self.assertEqual(anon.get("/api/finance/dashboard").status_code, 401)

    def test_05_rac_json_untouched(self):
        self.assertEqual(digest(BACKEND / "rac_data.json"), self.rac_hash)


if __name__ == "__main__":
    unittest.main()
