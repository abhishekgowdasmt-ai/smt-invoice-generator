"""PostgreSQL duty assignment and trip lifecycle tests.

Uses only a disposable local database whose name ends with _test.
Requires migration 007 (assignment trigger search_path).
"""
import hashlib
import os
import sys
import threading
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


class OperationDutyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        if not operations_duty.assignment_triggers_ready():
            raise unittest.SkipTest(
                "Apply dev-db/007_assignment_search_path.sql to "
                + cls.database_name
                + " before running duty lifecycle tests"
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
            "name": "Duty company " + cls.marker,
            "branch_codes": ["BLR"],
        })
        cls.company_id = (created.get_json().get("data") or {}).get("id")
        assert created.status_code == 201, created.get_json()
        cls.driver_a = cls._make_driver("Alpha", "9000000001")
        cls.driver_b = cls._make_driver("Beta", "9000000002")
        vehicle = cls.owner.post("/api/vehicles", json={
            "branch_code": "BLR",
            "registration_number": "DUTY" + cls.marker.upper()[:6],
            "model": "Innova",
            "status": "active",
        })
        cls.vehicle_id = (vehicle.get_json().get("data") or {}).get("id")
        assert vehicle.status_code == 201, vehicle.get_json()
        linked_vehicle = cls.owner.post(
            "/api/companies/%s/vehicles" % cls.company_id,
            json={"vehicle_id": cls.vehicle_id},
        )
        assert linked_vehicle.status_code in (200, 201), linked_vehicle.get_json()

    @classmethod
    def _make_driver(cls, label, phone):
        created = cls.owner.post("/api/drivers", json={
            "display_name": "Duty %s %s" % (label, cls.marker),
            "phone": phone,
            "primary_branch_code": "BLR",
        })
        body = created.get_json()
        assert created.status_code == 201, body
        driver_id = body["data"]["id"]
        reviewed = cls.owner.post("/api/drivers/%s/reviews" % driver_id, json={
            "decision": "verified",
            "reason": "Duty test verification",
        })
        assert reviewed.status_code == 200, reviewed.get_json()
        activated = cls.owner.post("/api/drivers/%s/active" % driver_id, json={
            "active": True,
            "reason": "Duty test activation",
        })
        assert activated.status_code == 200, activated.get_json()
        linked = cls.owner.post("/api/companies/%s/drivers" % cls.company_id, json={
            "driver_id": driver_id,
        })
        assert linked.status_code in (200, 201), linked.get_json()
        return driver_id

    def tearDown(self):
        def work(cur):
            cur.execute(
                "DELETE FROM user_branch_access WHERE user_id = %s::uuid",
                (self.staff_id,),
            )
        dev_postgres.authorized_transaction(self.owner_id, work)

    def create_booking(self, **extra):
        payload = {
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "trip_date": "2026-11-20",
            "employee_name": "Duty passenger " + self.marker,
            "source_booking_id": "DUTY-" + uuid.uuid4().hex[:12],
            "pickup_time": "09:00",
            "duty_type": "Airport",
            "planned_start": "Kempegowda Airport",
        }
        payload.update(extra)
        created = self.owner.post("/api/operations/bookings", json=payload)
        self.assertEqual(created.status_code, 201, created.get_json())
        return created.get_json()["data"]

    def test_full_lifecycle_assign_accept_start_complete(self):
        booking = self.create_booking()
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={
                "driver_id": self.driver_a,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        body = assigned.get_json()
        self.assertEqual(assigned.status_code, 200, body)
        self.assertEqual(body["data"]["booking"]["status"], "assigned")
        self.assertEqual(body["data"]["assignment"]["status"], "assigned")
        self.assertEqual(body["data"]["assignment"]["driver_id"], self.driver_a)
        self.assertEqual(body["whatsapp"]["send_status"], "skipped")
        assignment_id = body["data"]["assignment"]["id"]

        accepted = self.owner.post(
            "/api/operations/assignments/%s/accept" % assignment_id,
            json={},
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        self.assertEqual(accepted.get_json()["data"]["booking"]["status"], "accepted")

        started = self.owner.post(
            "/api/operations/bookings/%s/start" % booking["id"],
            json={},
        )
        self.assertEqual(started.status_code, 200, started.get_json())
        self.assertEqual(started.get_json()["data"]["booking"]["status"], "started")
        self.assertEqual(started.get_json()["data"]["session"]["status"], "active")

        completed = self.owner.post(
            "/api/operations/bookings/%s/complete" % booking["id"],
            json={},
        )
        self.assertEqual(completed.status_code, 200, completed.get_json())
        self.assertEqual(completed.get_json()["data"]["booking"]["status"], "completed")
        self.assertEqual(completed.get_json()["data"]["session"]["status"], "closed")

        trip = self.owner.get("/api/operations/bookings/%s/trip" % booking["id"])
        self.assertEqual(trip.status_code, 200, trip.get_json())
        history = [row["new_status"] for row in trip.get_json()["data"]["events"]]
        self.assertIn("assigned", history)
        self.assertIn("completed", history)
        self.assertEqual(self.rac_hash, digest(BACKEND / "rac_data.json"))

    def test_reassign_and_unassign_preserve_history(self):
        booking = self.create_booking()
        first = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={"driver_id": self.driver_a, "send_message": False},
        )
        self.assertEqual(first.status_code, 200, first.get_json())
        reassigned = self.owner.post(
            "/api/operations/bookings/%s/reassign" % booking["id"],
            json={"driver_id": self.driver_b, "send_message": False},
        )
        body = reassigned.get_json()
        self.assertEqual(reassigned.status_code, 200, body)
        self.assertEqual(body["data"]["assignment"]["driver_id"], self.driver_b)
        self.assertEqual(body["data"]["previous_assignment"]["status"], "superseded")
        self.assertEqual(body["data"]["booking"]["status"], "assigned")

        history = self.owner.get("/api/operations/bookings/%s/assignments" % booking["id"])
        self.assertEqual(history.status_code, 200, history.get_json())
        rows = history.get_json()["data"]["assignments"]
        self.assertGreaterEqual(len(rows), 2)
        statuses = {row["status"] for row in rows}
        self.assertIn("assigned", statuses)
        self.assertIn("superseded", statuses)

        unassigned = self.owner.post(
            "/api/operations/bookings/%s/unassign" % booking["id"],
            json={"reason": "Driver unavailable", "send_message": False},
        )
        self.assertEqual(unassigned.status_code, 200, unassigned.get_json())
        self.assertEqual(unassigned.get_json()["data"]["booking"]["status"], "unassigned")
        self.assertEqual(unassigned.get_json()["data"]["assignment"]["status"], "withdrawn")

    def test_cancel_from_unassigned_and_assigned(self):
        plain = self.create_booking()
        cancelled = self.owner.post(
            "/api/operations/bookings/%s/cancel" % plain["id"],
            json={"send_message": False},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.get_json())
        self.assertEqual(cancelled.get_json()["data"]["status"], "cancelled")

        booked = self.create_booking()
        self.owner.post(
            "/api/operations/bookings/%s/assign" % booked["id"],
            json={"driver_id": self.driver_a, "send_message": False},
        )
        cancelled_assigned = self.owner.post(
            "/api/operations/bookings/%s/cancel" % booked["id"],
            json={"send_message": False},
        )
        self.assertEqual(cancelled_assigned.status_code, 200, cancelled_assigned.get_json())
        cancelled_data = cancelled_assigned.get_json()["data"]
        cancelled_booking = cancelled_data.get("booking") or cancelled_data
        self.assertEqual(cancelled_booking["status"], "cancelled")

    def test_unverified_and_inactive_drivers_are_rejected(self):
        booking = self.create_booking()
        created = self.owner.post("/api/drivers", json={
            "display_name": "Unverified " + self.marker,
            "phone": "9000000099",
            "primary_branch_code": "BLR",
        })
        unverified_id = created.get_json()["data"]["id"]
        denied = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={"driver_id": unverified_id, "send_message": False},
        )
        self.assertEqual(denied.status_code, 400, denied.get_json())
        self.assertIn("verified", denied.get_json()["message"].lower())

        inactive = self.create_booking(source_booking_id="DUTY-INACT-" + self.marker)
        suspended = self.owner.post("/api/drivers/%s/active" % self.driver_a, json={
            "active": False,
            "reason": "Temporary suspension for duty test",
        })
        self.assertEqual(suspended.status_code, 200, suspended.get_json())
        try:
            blocked = self.owner.post(
                "/api/operations/bookings/%s/assign" % inactive["id"],
                json={"driver_id": self.driver_a, "send_message": False},
            )
            self.assertEqual(blocked.status_code, 400, blocked.get_json())
            self.assertIn("active", blocked.get_json()["message"].lower())
        finally:
            restored = self.owner.post("/api/drivers/%s/active" % self.driver_a, json={
                "active": True,
                "reason": "Restore after duty test",
            })
            self.assertEqual(restored.status_code, 200, restored.get_json())

    def test_staff_branch_access_for_assignment(self):
        booking = self.create_booking()
        denied = self.staff.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={"driver_id": self.driver_a, "send_message": False},
        )
        body = denied.get_json()
        # RLS hides the booking, so staff without a grant see not-found, not 403.
        self.assertEqual(denied.status_code, 404, body)
        self.assertEqual(body["message"], "Booking was not found.")
        self.assertEqual(set(body), {"success", "message"})
        rendered = denied.get_data(as_text=True)
        self.assertNotIn(booking["id"], rendered)
        self.assertNotIn(self.branch["BLR"], rendered)
        source = booking.get("source_booking_id")
        if source:
            self.assertNotIn(source, rendered)

        def grant(cur):
            cur.execute(
                """
                INSERT INTO user_branch_access (user_id, branch_id)
                VALUES (%s::uuid, %s::uuid)
                ON CONFLICT DO NOTHING
                """,
                (self.staff_id, self.branch["BLR"]),
            )
        self.assertIsNotNone(dev_postgres.authorized_transaction(self.owner_id, grant))
        allowed = self.staff.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={"driver_id": self.driver_a, "send_message": False},
        )
        self.assertEqual(allowed.status_code, 200, allowed.get_json())

    def test_reject_returns_booking_to_unassigned(self):
        booking = self.create_booking()
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={"driver_id": self.driver_a, "send_message": False},
        )
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        rejected = self.owner.post(
            "/api/operations/assignments/%s/reject" % assignment_id,
            json={"reason": "Driver declined"},
        )
        self.assertEqual(rejected.status_code, 200, rejected.get_json())
        self.assertEqual(rejected.get_json()["data"]["booking"]["status"], "unassigned")
        self.assertEqual(rejected.get_json()["data"]["assignment"]["status"], "rejected")

    def test_cannot_complete_without_active_session(self):
        booking = self.create_booking()
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={"driver_id": self.driver_a, "send_message": False},
        )
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        self.owner.post("/api/operations/assignments/%s/accept" % assignment_id, json={})
        denied = self.owner.post(
            "/api/operations/bookings/%s/complete" % booking["id"],
            json={},
        )
        self.assertEqual(denied.status_code, 409, denied.get_json())

    def test_concurrent_assign_leaves_one_open(self):
        booking = self.create_booking()
        barrier = threading.Barrier(2)
        results = []

        def attempt(driver_id):
            barrier.wait()
            results.append(operations_duty.assign_booking(
                self.owner_id,
                booking["id"],
                {"driver_id": driver_id, "send_message": False},
            ))

        threads = [
            threading.Thread(target=attempt, args=(self.driver_a,)),
            threading.Thread(target=attempt, args=(self.driver_b,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        winners = [row for row in results if row and row.get("ok")]
        losers = [row for row in results if row and not row.get("ok")]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(len(losers), 1, results)

        def count(cur):
            cur.execute(
                """
                SELECT count(*)
                FROM booking_assignments
                WHERE booking_id = %s::uuid AND status = ANY(%s)
                """,
                (booking["id"], ["assigned", "accepted"]),
            )
            return cur.fetchone()[0]

        counted = dev_postgres.authorized_transaction(self.owner_id, count)
        self.assertEqual(counted["result"], 1)

    def test_vehicle_patch_and_resend_skip_whatsapp(self):
        booking = self.create_booking()
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={"driver_id": self.driver_a, "send_message": False},
        )
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        patched = self.owner.patch(
            "/api/operations/assignments/%s/vehicle" % assignment_id,
            json={"vehicle_id": self.vehicle_id},
        )
        self.assertEqual(patched.status_code, 200, patched.get_json())
        self.assertEqual(patched.get_json()["data"]["assignment"]["vehicle_id"], self.vehicle_id)
        resent = self.owner.post(
            "/api/operations/assignments/%s/resend-message" % assignment_id,
            json={},
        )
        self.assertEqual(resent.status_code, 200, resent.get_json())
        self.assertIn(resent.get_json()["whatsapp"]["send_status"], ("sent", "ready"))


if __name__ == "__main__":
    unittest.main()
