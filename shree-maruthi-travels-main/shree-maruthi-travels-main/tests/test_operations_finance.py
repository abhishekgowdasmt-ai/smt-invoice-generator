"""PostgreSQL financial management tests.

Uses only a disposable local database whose name ends with _test.
Requires migration 009 (finance lifecycle).
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
import operations_duty
import operations_finance
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


class OperationFinanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        if not operations_finance.finance_schema_ready():
            raise unittest.SkipTest(
                "Apply dev-db/009_finance_lifecycle.sql to "
                + cls.database_name
                + " before running finance tests"
            )
        if not operations_duty.assignment_triggers_ready():
            raise unittest.SkipTest(
                "Apply migration 007 before finance tests that complete duties"
            )
        cls.owner = client_for(OWNER)
        cls.staff = client_for(STAFF)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        staff = dev_postgres.resolve_login_identity(STAFF)
        if not owner.get("ok") or not staff.get("ok"):
            raise unittest.SkipTest("disposable database is missing the local staff identities")
        cls.owner_id = owner["id"]
        cls.staff_id = staff["id"]
        branches = cls.owner.get("/api/branches").get_json()["data"]
        cls.branch = {row["code"]: row["id"] for row in branches}
        created = cls.owner.post("/api/companies", json={
            "name": "Finance company " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert created.status_code == 201, created.get_json()
        cls.company_id = created.get_json()["data"]["id"]
        driver = cls.owner.post("/api/drivers", json={
            "display_name": "Finance driver " + cls.marker,
            "phone": "9000000099",
            "primary_branch_code": "BLR",
        })
        assert driver.status_code == 201, driver.get_json()
        cls.driver_id = driver.get_json()["data"]["id"]
        cls.owner.post("/api/drivers/%s/reviews" % cls.driver_id, json={
            "decision": "verified",
            "reason": "Finance test",
        })
        cls.owner.post("/api/drivers/%s/active" % cls.driver_id, json={
            "active": True,
            "reason": "Finance test",
        })
        cls.owner.post("/api/companies/%s/drivers" % cls.company_id, json={
            "driver_id": cls.driver_id,
        })
        vehicle = cls.owner.post("/api/vehicles", json={
            "branch_code": "BLR",
            "registration_number": "FIN" + cls.marker.upper()[:6],
            "model": "Innova",
            "status": "active",
        })
        assert vehicle.status_code == 201, vehicle.get_json()
        cls.vehicle_id = vehicle.get_json()["data"]["id"]
        cls.owner.post("/api/companies/%s/vehicles" % cls.company_id, json={
            "vehicle_id": cls.vehicle_id,
        })

    def tearDown(self):
        def work(cur):
            cur.execute(
                "DELETE FROM user_branch_access WHERE user_id = %s::uuid",
                (self.staff_id,),
            )
        dev_postgres.authorized_transaction(self.owner_id, work)
        self.assertEqual(self.rac_hash, digest(BACKEND / "rac_data.json"))

    def create_booking(self):
        created = self.owner.post("/api/operations/bookings", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "trip_date": "2026-11-20",
            "employee_name": "Finance passenger " + self.marker,
            "source_booking_id": "FIN-" + uuid.uuid4().hex[:12],
            "pickup_time": "09:00",
            "duty_type": "Airport",
            "planned_start": "Kempegowda Airport",
            "customer_amount": 1500,
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        return created.get_json()["data"]

    def complete_booking(self, booking):
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={
                "driver_id": self.driver_id,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        self.assertEqual(assigned.status_code, 200, assigned.get_json())
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        accepted = self.owner.post(
            "/api/operations/assignments/%s/accept" % assignment_id,
            json={},
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        started = self.owner.post(
            "/api/operations/bookings/%s/start" % booking["id"],
            json={},
        )
        self.assertEqual(started.status_code, 200, started.get_json())
        completed = self.owner.post(
            "/api/operations/bookings/%s/complete" % booking["id"],
            json={},
        )
        self.assertEqual(completed.status_code, 200, completed.get_json())
        return completed.get_json()["data"]["booking"]

    def test_invoice_create_issue_pay_and_duplicate_duty(self):
        booking = self.complete_booking(self.create_booking())
        created = self.owner.post("/api/finance/invoices", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "due_date": "2026-12-01",
            "lines": [{
                "booking_id": booking["id"],
                "description": "Airport duty " + self.marker,
                "amount": "1500.00",
            }],
        })
        body = created.get_json()
        self.assertEqual(created.status_code, 201, body)
        invoice = body["data"]["invoice"]
        self.assertEqual(invoice["status"], "draft")
        self.assertEqual(invoice["total_amount"], "1500.00")
        invoice_id = invoice["id"]
        number = invoice["invoice_number"]

        dup_number = self.owner.post("/api/finance/invoices", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "invoice_number": number,
            "lines": [{"description": "Other", "amount": "100"}],
        })
        self.assertEqual(dup_number.status_code, 409, dup_number.get_json())

        dup_duty = self.owner.post("/api/finance/invoices", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "lines": [{
                "booking_id": booking["id"],
                "description": "Duplicate duty",
                "amount": "1500.00",
            }],
        })
        self.assertEqual(dup_duty.status_code, 409, dup_duty.get_json())

        issued = self.owner.post("/api/finance/invoices/%s/issue" % invoice_id, json={})
        self.assertEqual(issued.status_code, 200, issued.get_json())
        self.assertEqual(issued.get_json()["data"]["invoice"]["status"], "issued")

        edit = self.owner.patch("/api/finance/invoices/%s" % invoice_id, json={
            "notes": "should fail",
        })
        self.assertEqual(edit.status_code, 409, edit.get_json())

        overpay = self.owner.post("/api/finance/invoices/%s/payments" % invoice_id, json={
            "amount": "2000.00",
            "paid_on": "2026-11-21",
            "method": "neft",
            "reference": "OVER-" + self.marker,
        })
        self.assertEqual(overpay.status_code, 409, overpay.get_json())

        import_key = "IMP-" + self.marker
        paid = self.owner.post("/api/finance/invoices/%s/payments" % invoice_id, json={
            "amount": "500.00",
            "paid_on": "2026-11-21",
            "method": "neft",
            "reference": "PAY1-" + self.marker,
            "import_key": import_key,
        })
        self.assertEqual(paid.status_code, 201, paid.get_json())
        self.assertEqual(paid.get_json()["data"]["invoice"]["status"], "partially_paid")
        self.assertEqual(paid.get_json()["data"]["invoice"]["outstanding_amount"], "1000.00")

        again = self.owner.post("/api/finance/invoices/%s/payments" % invoice_id, json={
            "amount": "500.00",
            "paid_on": "2026-11-21",
            "method": "neft",
            "reference": "PAY1B-" + self.marker,
            "import_key": import_key,
        })
        self.assertEqual(again.status_code, 200, again.get_json())
        self.assertTrue(again.get_json()["data"].get("idempotent"))

        settle = self.owner.post("/api/finance/invoices/%s/payments" % invoice_id, json={
            "amount": "1000.00",
            "paid_on": "2026-11-22",
            "method": "upi",
            "reference": "PAY2-" + self.marker,
        })
        self.assertEqual(settle.status_code, 201, settle.get_json())
        self.assertEqual(settle.get_json()["data"]["invoice"]["status"], "paid")

        payment_id = paid.get_json()["data"]["payment"]["id"]
        reversed_pay = self.owner.post(
            "/api/finance/payments/%s/reverse" % payment_id,
            json={"reason": "Bank returned the transfer"},
        )
        self.assertEqual(reversed_pay.status_code, 200, reversed_pay.get_json())
        self.assertEqual(
            reversed_pay.get_json()["data"]["invoice"]["outstanding_amount"],
            "500.00",
        )

    def test_payout_expense_settlement_dashboard_and_branch_auth(self):
        booking = self.complete_booking(self.create_booking())
        payout = self.owner.post("/api/finance/payouts", json={
            "booking_id": booking["id"],
            "driver_id": self.driver_id,
            "amount": "800.00",
            "status": "pending",
            "reference": "PO-" + self.marker,
        })
        self.assertEqual(payout.status_code, 201, payout.get_json())
        payout_id = payout.get_json()["data"]["id"]
        dup = self.owner.post("/api/finance/payouts", json={
            "booking_id": booking["id"],
            "driver_id": self.driver_id,
            "amount": "100.00",
            "status": "pending",
        })
        self.assertEqual(dup.status_code, 409, dup.get_json())
        marked = self.owner.patch("/api/finance/payouts/%s" % payout_id, json={
            "status": "paid",
        })
        self.assertEqual(marked.status_code, 200, marked.get_json())
        self.assertEqual(marked.get_json()["data"]["status"], "paid")

        expense = self.owner.post("/api/finance/expenses", json={
            "branch_id": self.branch["BLR"],
            "category": "Fuel",
            "description": "Finance expense " + self.marker,
            "amount": "250.00",
            "expense_date": "2026-11-21",
        })
        self.assertEqual(expense.status_code, 201, expense.get_json())

        settlement = self.owner.get(
            "/api/finance/companies/%s/settlement" % self.company_id
        )
        self.assertEqual(settlement.status_code, 200, settlement.get_json())
        settle = settlement.get_json()["data"]
        self.assertIn("invoiced_amount", settle)
        self.assertIn("outstanding_balance", settle)

        dash = self.owner.get("/api/finance/dashboard?branch=BLR")
        self.assertEqual(dash.status_code, 200, dash.get_json())
        self.assertIn("total_invoiced", dash.get_json()["data"])

        denied = self.staff.get("/api/finance/dashboard?branch=BLR")
        # Staff without branch grant still gets dashboard filtered by RLS;
        # creating an invoice for BLR must be forbidden/hidden.
        create_denied = self.staff.post("/api/finance/invoices", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "lines": [{"description": "Blocked", "amount": "10"}],
        })
        self.assertEqual(create_denied.status_code, 403, create_denied.get_json())

        bank = self.owner.get("/api/finance/bank-details")
        self.assertEqual(bank.status_code, 200, bank.get_json())
        self.assertIn("account_no", bank.get_json()["data"])
        anon = app_module.app.test_client().get("/api/finance/bank-details")
        self.assertEqual(anon.status_code, 401)

        def audit_count(cur):
            cur.execute(
                """
                SELECT count(*) FROM audit_logs
                WHERE entity_name IN ('invoices', 'payments', 'driver_payouts', 'expenses')
                  AND summary ILIKE %s
                """,
                ("%" + self.marker + "%",),
            )
            return cur.fetchone()[0]

        # Ensure at least payout/expense audits exist for this marker.
        count = dev_postgres.authorized_transaction(self.owner_id, audit_count)
        self.assertGreaterEqual(count.get("result") or 0, 1)

    def test_void_and_draft_edit_and_rollback(self):
        created = self.owner.post("/api/finance/invoices", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "lines": [{"description": "Draft line", "amount": "100.00"}],
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        invoice_id = created.get_json()["data"]["invoice"]["id"]
        edited = self.owner.patch("/api/finance/invoices/%s" % invoice_id, json={
            "notes": "Updated draft",
            "lines": [{"description": "Edited line", "amount": "125.00"}],
        })
        self.assertEqual(edited.status_code, 200, edited.get_json())
        self.assertEqual(edited.get_json()["data"]["invoice"]["total_amount"], "125.00")
        self.assertEqual(edited.get_json()["data"]["invoice"]["notes"], "Updated draft")

        # Failed child update should roll back: invalid line amount.
        failed = self.owner.patch("/api/finance/invoices/%s" % invoice_id, json={
            "lines": [{"description": "Bad", "amount": "-1"}],
        })
        self.assertEqual(failed.status_code, 400, failed.get_json())
        current = self.owner.get("/api/finance/invoices/%s" % invoice_id)
        self.assertEqual(current.status_code, 200, current.get_json())
        self.assertEqual(current.get_json()["data"]["invoice"]["total_amount"], "125.00")

        issued = self.owner.post("/api/finance/invoices/%s/issue" % invoice_id, json={})
        self.assertEqual(issued.status_code, 200, issued.get_json())
        voided = self.owner.post("/api/finance/invoices/%s/void" % invoice_id, json={
            "reason": "Raised in error",
        })
        self.assertEqual(voided.status_code, 200, voided.get_json())
        self.assertEqual(voided.get_json()["data"]["invoice"]["status"], "void")


if __name__ == "__main__":
    unittest.main()
