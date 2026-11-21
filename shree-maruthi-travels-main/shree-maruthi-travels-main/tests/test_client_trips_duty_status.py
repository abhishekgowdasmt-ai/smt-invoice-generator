"""Regression: GET /api/client/trips via client_duty_status (migration 015).

Covers successful trip list after assignment and cross-company isolation.
Requires 015_client_duty_status_definer_selects.sql on disposable *_test.
Never targets smt_dev or production. Does not apply migrations.
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


def require_disposable_with_015():
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
                SELECT
                  has_column_privilege('smt_definer', 'drivers', 'display_name', 'SELECT'),
                  has_column_privilege('smt_definer', 'drivers', 'phone', 'SELECT'),
                  has_column_privilege('smt_definer', 'vehicles', 'registration_number', 'SELECT'),
                  has_column_privilege('smt_definer', 'vehicles', 'model', 'SELECT'),
                  has_column_privilege('smt_client', 'drivers', 'display_name', 'SELECT'),
                  has_table_privilege('smt_client', 'booking_assignments', 'SELECT')
                """
            )
            (
                definer_display,
                definer_phone,
                definer_reg,
                definer_model,
                client_drivers_display,
                client_assignments,
            ) = cur.fetchone()
            cur.execute(
                """
                SELECT 1 FROM pg_constraint
                WHERE conname = 'bookings_origin_check'
                  AND pg_get_constraintdef(oid) LIKE '%%client_request%%'
                """
            )
            has_origin = cur.fetchone() is not None
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    if not has_origin:
        raise unittest.SkipTest(
            "Apply dev-db/011_client_portal.sql to " + name + " before client trip tests"
        )
    if not (definer_display and definer_phone and definer_reg and definer_model):
        raise unittest.SkipTest(
            "Apply dev-db/015_client_duty_status_definer_selects.sql to "
            + name
            + " so client_duty_status can read driver/vehicle display columns"
        )
    if client_drivers_display or client_assignments:
        raise unittest.SkipTest(
            "smt_client must not have direct drivers.display_name or booking_assignments SELECT"
        )
    return name


class ClientTripsDutyStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_with_015()
        cls.owner = staff_client(OWNER)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        if not owner.get("ok"):
            raise unittest.SkipTest("missing owner identity")
        cls.password = "TripPass!" + cls.marker[:4]

        co_a = cls.owner.post("/api/companies", json={
            "name": "Trips Co A " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert co_a.status_code == 201, co_a.get_json()
        cls.company_a = co_a.get_json()["data"]["id"]
        co_b = cls.owner.post("/api/companies", json={
            "name": "Trips Co B " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert co_b.status_code == 201, co_b.get_json()
        cls.company_b = co_b.get_json()["data"]["id"]

        email_a = "trips.a.%s@example.com" % cls.marker
        email_b = "trips.b.%s@example.com" % cls.marker
        user_a = cls.owner.post("/api/clients", json={
            "full_name": "Trips Client A " + cls.marker,
            "email": email_a,
            "phone": "71" + str(int(cls.marker[:8], 16) % 10**8).zfill(8),
        })
        user_b = cls.owner.post("/api/clients", json={
            "full_name": "Trips Client B " + cls.marker,
            "email": email_b,
            "phone": "72" + str(int(cls.marker[:8], 16) % 10**8).zfill(8),
        })
        assert user_a.status_code == 201, user_a.get_json()
        assert user_b.status_code == 201, user_b.get_json()
        cls.user_a = user_a.get_json()["data"]["id"]
        cls.user_b = user_b.get_json()["data"]["id"]
        cls.email_a = email_a
        cls.email_b = email_b

        for company_id, user_id in (
            (cls.company_a, cls.user_a),
            (cls.company_b, cls.user_b),
        ):
            link = cls.owner.post(
                "/api/companies/%s/clients" % company_id,
                json={"user_id": user_id},
            )
            assert link.status_code in (200, 201), link.get_json()
            prov = cls.owner.post(
                "/api/clients/%s/login-account" % user_id,
                json={"password": cls.password},
            )
            assert prov.status_code in (200, 201), prov.get_json()

        phone = "73" + str(int(cls.marker[:8], 16) % 10**8).zfill(8)
        driver = cls.owner.post("/api/drivers", json={
            "display_name": "Trips Driver " + cls.marker,
            "phone": phone,
            "primary_branch_code": "BLR",
        })
        assert driver.status_code == 201, driver.get_json()
        cls.driver_id = driver.get_json()["data"]["id"]
        cls.driver_name = "Trips Driver " + cls.marker
        reviewed = cls.owner.post("/api/drivers/%s/reviews" % cls.driver_id, json={
            "decision": "verified",
            "reason": "Trips duty status verification",
        })
        assert reviewed.status_code == 200, reviewed.get_json()
        activated = cls.owner.post("/api/drivers/%s/active" % cls.driver_id, json={
            "active": True,
            "reason": "Trips duty status activation",
        })
        assert activated.status_code == 200, activated.get_json()
        linked = cls.owner.post(
            "/api/companies/%s/drivers" % cls.company_a,
            json={"driver_id": cls.driver_id},
        )
        assert linked.status_code in (200, 201), linked.get_json()

        reg = "TP" + cls.marker.upper()[:6]
        vehicle = cls.owner.post("/api/vehicles", json={
            "branch_code": "BLR",
            "registration_number": reg,
            "model": "Innova",
            "status": "active",
        })
        assert vehicle.status_code == 201, vehicle.get_json()
        cls.vehicle_id = vehicle.get_json()["data"]["id"]
        cls.vehicle_reg = reg
        linked_v = cls.owner.post(
            "/api/companies/%s/vehicles" % cls.company_a,
            json={"vehicle_id": cls.vehicle_id},
        )
        assert linked_v.status_code in (200, 201), linked_v.get_json()

    def _portal(self, email):
        client = app_module.app.test_client()
        login = client.post("/api/client/login", json={
            "email": email,
            "password": self.password,
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        return client

    def test_01_definer_grants_and_client_boundary(self):
        dsn = dev_postgres.local_development_dsn()
        import psycopg
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database()")
                self.assertEqual(cur.fetchone()[0], self.database_name)
                cur.execute(
                    """
                    SELECT
                      has_column_privilege('smt_definer', 'drivers', 'display_name', 'SELECT'),
                      has_column_privilege('smt_definer', 'drivers', 'phone', 'SELECT'),
                      has_column_privilege('smt_definer', 'vehicles', 'registration_number', 'SELECT'),
                      has_column_privilege('smt_definer', 'vehicles', 'model', 'SELECT'),
                      has_column_privilege('smt_client', 'drivers', 'display_name', 'SELECT'),
                      has_column_privilege('smt_client', 'vehicles', 'registration_number', 'SELECT'),
                      has_table_privilege('smt_client', 'client_duty_status', 'SELECT'),
                      has_table_privilege('smt_client', 'booking_assignments', 'SELECT')
                    """
                )
                row = cur.fetchone()
        self.assertEqual(
            row,
            (True, True, True, True, False, False, True, False),
            row,
        )

    def test_02_trips_list_and_cross_company_isolation(self):
        portal_a = self._portal(self.email_a)
        portal_b = self._portal(self.email_b)

        created = portal_a.post("/api/client/bookings", json={
            "branch_code": "BLR",
            "trip_date": "2031-05-15",
            "pickup_time": "08:45",
            "pickup_location": "Trips pickup " + self.marker,
            "passenger_name": "Trips passenger " + self.marker,
            "duty_type": "Local",
            "cab_type": "SUV",
            "route": "Office to hotel",
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        booking_id = created.get_json()["booking"]["id"]

        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={
                "driver_id": self.driver_id,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        self.assertEqual(assigned.status_code, 200, assigned.get_json())

        trips_a = portal_a.get("/api/client/trips")
        self.assertEqual(trips_a.status_code, 200, trips_a.get_json())
        body_a = trips_a.get_json()
        self.assertEqual(body_a.get("filter"), "all")
        rows_a = body_a["trips"]
        match = next((t for t in rows_a if t["booking_id"] == booking_id), None)
        self.assertIsNotNone(match, rows_a)
        self.assertEqual(match["duty_status"], "assigned")
        self.assertEqual(match["assignment_status"], "assigned")
        self.assertEqual(match["driver_name"], self.driver_name)
        self.assertTrue(match.get("driver_phone"))
        self.assertEqual(match["vehicle_registration"], self.vehicle_reg)
        self.assertEqual(match["vehicle_model"], "Innova")
        self.assertNotIn("rejection_reason", match)
        self.assertNotIn("assigned_by", match)

        trips_b = portal_b.get("/api/client/trips")
        self.assertEqual(trips_b.status_code, 200, trips_b.get_json())
        rows_b = trips_b.get_json()["trips"]
        self.assertFalse(
            any(t["booking_id"] == booking_id for t in rows_b),
            rows_b,
        )

        detail_b = portal_b.get("/api/client/bookings/%s" % booking_id)
        self.assertEqual(detail_b.status_code, 404)

        assigned_filter = portal_a.get("/api/client/trips?filter=assigned")
        self.assertEqual(assigned_filter.status_code, 200, assigned_filter.get_json())
        assigned_rows = assigned_filter.get_json()["trips"]
        self.assertTrue(any(t["booking_id"] == booking_id for t in assigned_rows))

    def test_03_rac_untouched(self):
        self.assertEqual(digest(BACKEND / "rac_data.json"), self.rac_hash)


if __name__ == "__main__":
    unittest.main()
