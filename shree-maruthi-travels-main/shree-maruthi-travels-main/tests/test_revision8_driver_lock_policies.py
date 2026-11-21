"""Security checks for migration 013 lock-only driver UPDATE policies.

Requires 012 + 013 on disposable smt_revision8_test. Does not apply migrations.
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


def require_disposable_with_013():
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
                SELECT COUNT(*) FROM pg_policies
                WHERE schemaname = 'public'
                  AND policyname = 'bookings_driver_for_update_lock'
                """
            )
            has_013 = cur.fetchone()[0] == 1
            cur.execute(
                "SELECT has_column_privilege('smt_driver', 'bookings', 'status', 'UPDATE')"
            )
            has_012 = cur.fetchone()[0]
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    if not has_012:
        raise unittest.SkipTest("Apply dev-db/012_driver_booking_lock_grant.sql to " + name)
    if not has_013:
        raise unittest.SkipTest(
            "Apply dev-db/013_driver_booking_for_update_policy.sql to " + name
        )
    return name


class DriverLockPolicySecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_with_013()
        cls.owner = staff_client(OWNER)
        cls.marker = uuid.uuid4().hex[:10]
        owner = dev_postgres.resolve_login_identity(OWNER)
        if not owner.get("ok"):
            raise unittest.SkipTest("missing owner identity")
        cls.owner_id = owner["id"]
        branches = cls.owner.get("/api/branches").get_json()["data"]
        cls.branch = {row["code"]: row["id"] for row in branches}

        co_a = cls.owner.post("/api/companies", json={
            "name": "LockPol A " + cls.marker,
            "branch_codes": ["BLR"],
        })
        co_b = cls.owner.post("/api/companies", json={
            "name": "LockPol B " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert co_a.status_code == 201, co_a.get_json()
        assert co_b.status_code == 201, co_b.get_json()
        cls.company_a = co_a.get_json()["data"]["id"]
        cls.company_b = co_b.get_json()["data"]["id"]

        digits = str(int(cls.marker[:8], 16) % 10**8).zfill(8)
        cls.phone = "96" + digits
        cls.password = "DriverPass!" + cls.marker[:4]
        driver = cls.owner.post("/api/drivers", json={
            "display_name": "LockPol Driver " + cls.marker,
            "phone": cls.phone,
            "primary_branch_code": "BLR",
        })
        assert driver.status_code == 201, driver.get_json()
        cls.driver_id = driver.get_json()["data"]["id"]
        assert cls.owner.post(
            "/api/drivers/%s/reviews" % cls.driver_id,
            json={"decision": "verified", "reason": "lock policy test"},
        ).status_code == 200
        assert cls.owner.post(
            "/api/drivers/%s/active" % cls.driver_id,
            json={"active": True, "reason": "lock policy test"},
        ).status_code == 200
        assert cls.owner.post(
            "/api/companies/%s/drivers" % cls.company_a,
            json={"driver_id": cls.driver_id},
        ).status_code in (200, 201)
        assert cls.owner.post(
            "/api/drivers/%s/login-account" % cls.driver_id,
            json={"password": cls.password},
        ).status_code in (200, 201)

        vehicle = cls.owner.post("/api/vehicles", json={
            "branch_code": "BLR",
            "registration_number": "LP" + cls.marker.upper()[:6],
            "model": "Innova",
            "status": "active",
        })
        assert vehicle.status_code == 201, vehicle.get_json()
        cls.vehicle_id = vehicle.get_json()["data"]["id"]
        assert cls.owner.post(
            "/api/companies/%s/vehicles" % cls.company_a,
            json={"vehicle_id": cls.vehicle_id},
        ).status_code in (200, 201)
        assert cls.owner.post(
            "/api/companies/%s/vehicles" % cls.company_b,
            json={"vehicle_id": cls.vehicle_id},
        ).status_code in (200, 201)

        booking = cls.owner.post("/api/operations/bookings", json={
            "branch_id": cls.branch["BLR"],
            "company_id": cls.company_a,
            "trip_date": "2031-09-01",
            "planned_start": "Lock policy pickup",
            "employee_name": "Lock passenger",
            "source_booking_id": "LP-" + cls.marker,
        })
        assert booking.status_code == 201, booking.get_json()
        cls.booking_id = booking.get_json()["data"]["id"]
        assigned = cls.owner.post(
            "/api/operations/bookings/%s/assign" % cls.booking_id,
            json={
                "driver_id": cls.driver_id,
                "vehicle_id": cls.vehicle_id,
                "send_message": False,
            },
        )
        assert assigned.status_code == 200, assigned.get_json()
        cls.assignment_id = assigned.get_json()["data"]["assignment"]["id"]

        login = app_module.app.test_client().post("/api/driver/login", json={
            "phone": cls.phone,
            "password": cls.password,
        })
        assert login.status_code == 200, login.get_json()
        cls.driver_user_id = login.get_json()["user"]["id"]

    def test_01_policy_definitions_are_lock_only_and_open_scoped(self):
        import psycopg

        dsn = dev_postgres.local_development_dsn()
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tablename, policyname, cmd, with_check, qual
                    FROM pg_policies
                    WHERE schemaname = 'public'
                      AND policyname IN (
                        'bookings_driver_for_update_lock',
                        'vehicles_driver_for_update_lock',
                        'company_drivers_driver_read',
                        'company_vehicles_driver_read'
                      )
                    ORDER BY tablename, policyname
                    """
                )
                rows = {row[1]: row for row in cur.fetchall()}
        self.assertEqual(len(rows), 4)

        booking = rows["bookings_driver_for_update_lock"]
        self.assertEqual(booking[2], "UPDATE")
        self.assertEqual(booking[3], "false")
        self.assertIn("current_driver_id()", booking[4])
        self.assertIn("assigned", booking[4])
        self.assertIn("accepted", booking[4])

        vehicle = rows["vehicles_driver_for_update_lock"]
        self.assertEqual(vehicle[2], "UPDATE")
        self.assertEqual(vehicle[3], "false")
        self.assertIn("current_driver_id()", vehicle[4])
        self.assertIn("assigned", vehicle[4])
        self.assertIn("accepted", vehicle[4])

        company_drivers = rows["company_drivers_driver_read"]
        self.assertEqual(company_drivers[2], "SELECT")
        self.assertIn("current_driver_id()", company_drivers[4])

        company_vehicles = rows["company_vehicles_driver_read"]
        self.assertEqual(company_vehicles[2], "SELECT")
        self.assertIn("company_id", company_vehicles[4])
        self.assertIn("current_driver_id()", company_vehicles[4])
        self.assertIn("assigned", company_vehicles[4])

        import psycopg
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM pg_policies
                    WHERE schemaname = 'public'
                      AND tablename = 'bookings'
                      AND 'smt_driver' = ANY (roles)
                      AND cmd = 'UPDATE'
                      AND with_check IS DISTINCT FROM 'false'
                    """
                )
                self.assertEqual(cur.fetchone()[0], 0)

    def test_02_open_assignment_allows_lock_but_blocks_real_updates(self):
        def work(cur):
            out = {}
            cur.execute(
                """
                SELECT id::text FROM bookings
                WHERE id = %s::uuid
                FOR UPDATE
                """,
                (self.booking_id,),
            )
            out["booking_lock"] = cur.fetchone()
            cur.execute(
                """
                SELECT id::text FROM vehicles
                WHERE id = %s::uuid
                FOR UPDATE
                """,
                (self.vehicle_id,),
            )
            out["vehicle_lock"] = cur.fetchone()
            # WITH CHECK (false) aborts the statement; isolate with savepoints.
            cur.execute("SAVEPOINT try_booking_update")
            try:
                cur.execute(
                    "UPDATE bookings SET status = status WHERE id = %s::uuid RETURNING id::text",
                    (self.booking_id,),
                )
                out["booking_update"] = {"row": cur.fetchone()}
                cur.execute("RELEASE SAVEPOINT try_booking_update")
            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT try_booking_update")
                cur.execute("RELEASE SAVEPOINT try_booking_update")
                out["booking_update"] = {
                    "sqlstate": getattr(exc, "sqlstate", None),
                    "primary": getattr(getattr(exc, "diag", None), "message_primary", None),
                }
            cur.execute("SAVEPOINT try_vehicle_update")
            try:
                cur.execute(
                    "UPDATE vehicles SET status = status WHERE id = %s::uuid RETURNING id::text",
                    (self.vehicle_id,),
                )
                out["vehicle_update"] = {"row": cur.fetchone()}
                cur.execute("RELEASE SAVEPOINT try_vehicle_update")
            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT try_vehicle_update")
                cur.execute("RELEASE SAVEPOINT try_vehicle_update")
                out["vehicle_update"] = {
                    "sqlstate": getattr(exc, "sqlstate", None),
                    "primary": getattr(getattr(exc, "diag", None), "message_primary", None),
                }
            cur.execute(
                """
                SELECT company_id::text FROM company_vehicles
                WHERE vehicle_id = %s::uuid
                ORDER BY company_id::text
                """,
                (self.vehicle_id,),
            )
            out["company_vehicle_ids"] = [row[0] for row in cur.fetchall()]
            cur.execute(
                """
                SELECT company_id::text FROM company_drivers
                WHERE driver_id = current_driver_id()
                """
            )
            out["company_driver_ids"] = [row[0] for row in cur.fetchall()]
            return out

        done = dev_postgres.authorized_transaction(self.driver_user_id, work)
        self.assertIsNotNone(done)
        self.assertEqual(done.get("role"), "driver", done)
        result = done["result"]
        self.assertEqual(result["booking_lock"][0], self.booking_id)
        self.assertEqual(result["vehicle_lock"][0], self.vehicle_id)
        booking_update = result["booking_update"]
        vehicle_update = result["vehicle_update"]
        self.assertTrue(
            booking_update.get("row") is None
            or booking_update.get("sqlstate") in ("42501", "44000")
            or "policy" in ((booking_update.get("primary") or "")).lower(),
            booking_update,
        )
        self.assertTrue(
            vehicle_update.get("row") is None
            or vehicle_update.get("sqlstate") in ("42501", "44000")
            or "policy" in ((vehicle_update.get("primary") or "")).lower(),
            vehicle_update,
        )
        if booking_update.get("primary"):
            self.assertIn("policy", booking_update["primary"].lower())
        if vehicle_update.get("primary"):
            self.assertIn("policy", vehicle_update["primary"].lower())
        self.assertEqual(result["company_vehicle_ids"], [self.company_a])
        self.assertEqual(result["company_driver_ids"], [self.company_a])
        self.assertNotIn(self.company_b, result["company_vehicle_ids"])

    def test_03_historical_assignment_does_not_allow_locks(self):
        # Close the open assignment via supervisor reject path → historical.
        rejected = self.owner.post(
            "/api/operations/assignments/%s/reject" % self.assignment_id,
            json={"reason": "Lock policy historical coverage"},
        )
        self.assertEqual(rejected.status_code, 200, rejected.get_json())

        def work(cur):
            cur.execute(
                """
                SELECT id::text FROM bookings
                WHERE id = %s::uuid
                FOR UPDATE
                """,
                (self.booking_id,),
            )
            booking_lock = cur.fetchone()
            cur.execute(
                """
                SELECT id::text FROM vehicles
                WHERE id = %s::uuid
                FOR UPDATE
                """,
                (self.vehicle_id,),
            )
            vehicle_lock = cur.fetchone()
            cur.execute(
                """
                SELECT company_id::text FROM company_vehicles
                WHERE vehicle_id = %s::uuid
                """,
                (self.vehicle_id,),
            )
            company_vehicles = [row[0] for row in cur.fetchall()]
            return {
                "booking_lock": booking_lock,
                "vehicle_lock": vehicle_lock,
                "company_vehicles": company_vehicles,
            }

        done = dev_postgres.authorized_transaction(self.driver_user_id, work)
        self.assertEqual(done.get("role"), "driver", done)
        result = done["result"]
        self.assertIsNone(result["booking_lock"])
        self.assertIsNone(result["vehicle_lock"])
        self.assertEqual(result["company_vehicles"], [])


if __name__ == "__main__":
    unittest.main()
