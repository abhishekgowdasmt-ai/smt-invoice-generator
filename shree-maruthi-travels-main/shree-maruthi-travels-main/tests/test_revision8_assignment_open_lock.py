"""Security and lifecycle checks for migration 014 assignment open locks.

Requires 012–014 on disposable smt_revision8_test. Does not apply migrations.
Never targets smt_dev or production.
"""
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


def require_disposable_with_014():
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
                SELECT qual, with_check
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = 'booking_assignments'
                  AND policyname = 'assignments_driver_update'
                """
            )
            row = cur.fetchone()
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    if row is None:
        raise unittest.SkipTest("assignments_driver_update policy missing on " + name)
    qual, with_check = row
    if "accepted" not in (qual or "") or "assigned" not in (qual or ""):
        raise unittest.SkipTest(
            "Apply dev-db/014_driver_assignment_open_lock.sql to " + name
        )
    if "rejected" not in (with_check or "") or "accepted" not in (with_check or ""):
        raise unittest.SkipTest(
            "assignments_driver_update WITH CHECK unexpected on " + name
        )
    return name


class AssignmentOpenLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_with_014()
        cls.owner = staff_client(OWNER)
        cls.marker = uuid.uuid4().hex[:10]
        owner = dev_postgres.resolve_login_identity(OWNER)
        if not owner.get("ok"):
            raise unittest.SkipTest("missing owner identity")
        cls.owner_id = owner["id"]
        branches = cls.owner.get("/api/branches").get_json()["data"]
        cls.branch = {row["code"]: row["id"] for row in branches}

        company = cls.owner.post("/api/companies", json={
            "name": "OpenLock Co " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert company.status_code == 201, company.get_json()
        cls.company_id = company.get_json()["data"]["id"]

        digits = str(int(cls.marker[:8], 16) % 10**8).zfill(8)
        cls.phone_a = "98" + digits
        cls.phone_b = "99" + digits
        cls.password = "DriverPass!" + cls.marker[:4]
        cls.driver_a = cls._make_driver("A", cls.phone_a)
        cls.driver_b = cls._make_driver("B", cls.phone_b)

        vehicle = cls.owner.post("/api/vehicles", json={
            "branch_code": "BLR",
            "registration_number": "OL" + cls.marker.upper()[:6],
            "model": "Innova",
            "status": "active",
        })
        assert vehicle.status_code == 201, vehicle.get_json()
        cls.vehicle_id = vehicle.get_json()["data"]["id"]
        assert cls.owner.post(
            "/api/companies/%s/vehicles" % cls.company_id,
            json={"vehicle_id": cls.vehicle_id},
        ).status_code in (200, 201)

        booking = cls.owner.post("/api/operations/bookings", json={
            "branch_id": cls.branch["BLR"],
            "company_id": cls.company_id,
            "trip_date": "2031-11-01",
            "planned_start": "Open lock pickup",
            "employee_name": "Open lock passenger",
            "source_booking_id": "OL-" + cls.marker,
        })
        assert booking.status_code == 201, booking.get_json()
        cls.booking_id = booking.get_json()["data"]["id"]
        assigned = cls.owner.post(
            "/api/operations/bookings/%s/assign" % cls.booking_id,
            json={
                "driver_id": cls.driver_a,
                "vehicle_id": cls.vehicle_id,
                "send_message": False,
            },
        )
        assert assigned.status_code == 200, assigned.get_json()
        cls.assignment_id = assigned.get_json()["data"]["assignment"]["id"]

        login = app_module.app.test_client().post("/api/driver/login", json={
            "phone": cls.phone_a,
            "password": cls.password,
        })
        assert login.status_code == 200, login.get_json()
        cls.user_a = login.get_json()["user"]["id"]
        cls.token_a = login.get_json()["token"]

        login_b = app_module.app.test_client().post("/api/driver/login", json={
            "phone": cls.phone_b,
            "password": cls.password,
        })
        assert login_b.status_code == 200, login_b.get_json()
        cls.user_b = login_b.get_json()["user"]["id"]

    @classmethod
    def _make_driver(cls, label, phone):
        created = cls.owner.post("/api/drivers", json={
            "display_name": "OpenLock %s %s" % (label, cls.marker),
            "phone": phone,
            "primary_branch_code": "BLR",
        })
        assert created.status_code == 201, created.get_json()
        driver_id = created.get_json()["data"]["id"]
        assert cls.owner.post(
            "/api/drivers/%s/reviews" % driver_id,
            json={"decision": "verified", "reason": "open lock test"},
        ).status_code == 200
        assert cls.owner.post(
            "/api/drivers/%s/active" % driver_id,
            json={"active": True, "reason": "open lock test"},
        ).status_code == 200
        assert cls.owner.post(
            "/api/companies/%s/drivers" % cls.company_id,
            json={"driver_id": driver_id},
        ).status_code in (200, 201)
        assert cls.owner.post(
            "/api/drivers/%s/login-account" % driver_id,
            json={"password": cls.password},
        ).status_code in (200, 201)
        return driver_id

    def _driver_http(self, token):
        client = app_module.app.test_client()
        client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
        return client

    def test_01_policy_definition(self):
        import psycopg

        dsn = dev_postgres.local_development_dsn()
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT qual, with_check FROM pg_policies
                    WHERE policyname = 'assignments_driver_update'
                    """
                )
                qual, with_check = cur.fetchone()
                cur.execute(
                    """
                    SELECT COUNT(*) FROM pg_policies
                    WHERE tablename = 'booking_assignments'
                      AND policyname = 'assignments_staff_update'
                    """
                )
                staff_ok = cur.fetchone()[0]
        self.assertIn("assigned", qual)
        self.assertIn("accepted", qual)
        self.assertIn("current_driver_id()", qual)
        self.assertNotIn("rejected", qual)
        self.assertNotIn("completed", qual)
        self.assertNotIn("superseded", qual)
        self.assertNotIn("withdrawn", qual)
        self.assertIn("accepted", with_check)
        self.assertIn("rejected", with_check)
        self.assertEqual(staff_ok, 1)

    def test_02_accept_allows_lock_start_complete_and_idempotent_accept(self):
        client = self._driver_http(self.token_a)
        accept = client.post("/api/driver/duties/%s/accept" % self.assignment_id)
        self.assertEqual(accept.status_code, 200, accept.get_json())
        again = client.post("/api/driver/duties/%s/accept" % self.assignment_id)
        self.assertEqual(again.status_code, 200, again.get_json())
        self.assertTrue(again.get_json().get("already"))

        def lock_after_accept(cur):
            cur.execute(
                """
                SELECT id::text, status FROM booking_assignments
                WHERE id = %s::uuid AND driver_id = current_driver_id()
                FOR UPDATE
                """,
                (self.assignment_id,),
            )
            return cur.fetchone()

        done = dev_postgres.authorized_transaction(self.user_a, lock_after_accept)
        self.assertEqual(done.get("role"), "driver", done)
        self.assertEqual(done["result"][0], self.assignment_id)
        self.assertEqual(done["result"][1], "accepted")

        start = client.post(
            "/api/driver/duties/%s/start" % self.assignment_id,
            json={"start_km": 50},
        )
        self.assertEqual(start.status_code, 200, start.get_json())
        complete = client.post(
            "/api/driver/duties/%s/complete" % self.assignment_id,
            json={"end_km": 80},
        )
        self.assertEqual(complete.status_code, 200, complete.get_json())

    def test_03_other_driver_cannot_lock_or_update(self):
        # Fresh assignment for isolation after test_02 completed the first duty.
        booking = self.owner.post("/api/operations/bookings", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "trip_date": "2031-11-02",
            "planned_start": "Isolation pickup",
            "employee_name": "Isolation passenger",
            "source_booking_id": "OL-ISO-" + self.marker,
        })
        self.assertEqual(booking.status_code, 201, booking.get_json())
        booking_id = booking.get_json()["data"]["id"]
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={
                "driver_id": self.driver_a,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        self.assertEqual(assigned.status_code, 200, assigned.get_json())
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]

        def other_driver(cur):
            cur.execute(
                """
                SELECT id::text FROM booking_assignments
                WHERE id = %s::uuid AND driver_id = current_driver_id()
                FOR UPDATE
                """,
                (assignment_id,),
            )
            locked = cur.fetchone()
            cur.execute("SAVEPOINT try_update")
            try:
                cur.execute(
                    """
                    UPDATE booking_assignments
                    SET status = 'accepted', decided_at = now()
                    WHERE id = %s::uuid
                    RETURNING id::text
                    """,
                    (assignment_id,),
                )
                updated = cur.fetchone()
                cur.execute("RELEASE SAVEPOINT try_update")
            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT try_update")
                cur.execute("RELEASE SAVEPOINT try_update")
                updated = {
                    "sqlstate": getattr(exc, "sqlstate", None),
                    "primary": getattr(getattr(exc, "diag", None), "message_primary", None),
                }
            return {"locked": locked, "updated": updated}

        done = dev_postgres.authorized_transaction(self.user_b, other_driver)
        self.assertEqual(done.get("role"), "driver", done)
        self.assertIsNone(done["result"]["locked"])
        updated = done["result"]["updated"]
        if isinstance(updated, tuple):
            self.fail("other driver updated foreign assignment: %r" % (updated,))
        # Zero-row update or RLS/policy error — never a successful row return.
        self.assertTrue(
            updated is None
            or (isinstance(updated, dict) and updated.get("row") is None)
            or (isinstance(updated, dict) and updated.get("sqlstate")),
            updated,
        )

        login_b = app_module.app.test_client().post("/api/driver/login", json={
            "phone": self.phone_b,
            "password": self.password,
        })
        client_b = self._driver_http(login_b.get_json()["token"])
        self.assertEqual(
            client_b.post("/api/driver/duties/%s/accept" % assignment_id).status_code,
            404,
        )

    def test_04_historical_statuses_cannot_be_locked(self):
        booking = self.owner.post("/api/operations/bookings", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "trip_date": "2031-11-03",
            "planned_start": "Historical pickup",
            "employee_name": "Historical passenger",
            "source_booking_id": "OL-HIST-" + self.marker,
        })
        self.assertEqual(booking.status_code, 201, booking.get_json())
        booking_id = booking.get_json()["data"]["id"]
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={
                "driver_id": self.driver_a,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        self.assertEqual(assigned.status_code, 200, assigned.get_json())
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        rejected = self.owner.post(
            "/api/operations/assignments/%s/reject" % assignment_id,
            json={"reason": "Open lock historical coverage"},
        )
        self.assertEqual(rejected.status_code, 200, rejected.get_json())

        def work(cur):
            cur.execute(
                """
                SELECT id::text, status FROM booking_assignments
                WHERE id = %s::uuid AND driver_id = current_driver_id()
                FOR UPDATE
                """,
                (assignment_id,),
            )
            locked = cur.fetchone()
            cur.execute(
                """
                SELECT id::text, status FROM booking_assignments
                WHERE id = %s::uuid AND driver_id = current_driver_id()
                """,
                (assignment_id,),
            )
            visible = cur.fetchone()
            return {"locked": locked, "visible": visible}

        done = dev_postgres.authorized_transaction(self.user_a, work)
        self.assertEqual(done.get("role"), "driver", done)
        self.assertIsNone(done["result"]["locked"])
        # SELECT policy still allows reading own historical rows.
        self.assertEqual(done["result"]["visible"][1], "rejected")


if __name__ == "__main__":
    unittest.main()
