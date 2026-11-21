"""Driver Android API tests against a disposable *_test database.

Requires migrations through 010_driver_app.sql.
Never targets smt_dev or production.
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
import driver_auth
import operations_duty
import operations_driver_app
import staff_auth
import dev_postgres

OWNER = "abhishekgowdasmt@gmail.com"
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
            cur.execute("SELECT to_regclass('public.driver_notifications') IS NOT NULL")
            has_notifications = cur.fetchone()[0]
            cur.execute(
                "SELECT has_column_privilege('smt_driver', 'bookings', 'status', 'UPDATE')"
            )
            driver_can_lock_booking = cur.fetchone()[0]
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    if not has_notifications:
        raise unittest.SkipTest(
            "Apply dev-db/010_driver_app.sql to " + name + " before driver app tests"
        )
    return name, bool(driver_can_lock_booking)


class DriverAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name, cls.driver_can_lock_booking = require_disposable_local_database()
        if not operations_duty.assignment_triggers_ready():
            raise unittest.SkipTest("Assignment triggers need migration 007")
        cls.owner = client_for(OWNER)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        if not owner.get("ok"):
            raise unittest.SkipTest("missing owner identity")
        cls.owner_id = owner["id"]
        branches = cls.owner.get("/api/branches").get_json()["data"]
        cls.branch = {row["code"]: row["id"] for row in branches}
        created = cls.owner.post("/api/companies", json={
            "name": "Driver app co " + cls.marker,
            "branch_codes": ["BLR"],
        })
        cls.company_id = (created.get_json().get("data") or {}).get("id")
        assert created.status_code == 201, created.get_json()
        phone_a = "81" + cls.marker[:8]
        phone_b = "82" + cls.marker[:8]
        cls.password = "DriverPass!" + cls.marker[:4]
        cls.driver_a_id = cls._make_driver("A", phone_a)
        cls.driver_b_id = cls._make_driver("B", phone_b)
        cls.phone_a = phone_a
        cls.phone_b = phone_b
        provision_a = cls.owner.post(
            "/api/drivers/%s/login-account" % cls.driver_a_id,
            json={"password": cls.password},
        )
        provision_b = cls.owner.post(
            "/api/drivers/%s/login-account" % cls.driver_b_id,
            json={"password": cls.password},
        )
        assert provision_a.status_code in (200, 201), provision_a.get_json()
        assert provision_b.status_code in (200, 201), provision_b.get_json()
        vehicle = cls.owner.post("/api/vehicles", json={
            "branch_code": "BLR",
            "registration_number": "DA" + cls.marker.upper()[:6],
            "model": "Innova",
            "status": "active",
        })
        assert vehicle.status_code == 201, vehicle.get_json()
        cls.vehicle_id = vehicle.get_json()["data"]["id"]
        linked_vehicle = cls.owner.post(
            "/api/companies/%s/vehicles" % cls.company_id,
            json={"vehicle_id": cls.vehicle_id},
        )
        assert linked_vehicle.status_code in (200, 201), linked_vehicle.get_json()
        booking = cls.owner.post("/api/operations/bookings", json={
            "branch_id": cls.branch["BLR"],
            "company_id": cls.company_id,
            "trip_date": "2030-03-15",
            "pickup_time": "09:00",
            "planned_start": "Test pickup",
            "duty_type": "Airport",
            "employee_name": "Passenger " + cls.marker,
            "source_booking_id": "DA-" + cls.marker,
        })
        assert booking.status_code == 201, booking.get_json()
        cls.booking_id = booking.get_json()["data"]["id"]
        assigned = cls.owner.post(
            "/api/operations/bookings/%s/assign" % cls.booking_id,
            json={
                "driver_id": cls.driver_a_id,
                "vehicle_id": cls.vehicle_id,
                "send_message": False,
            },
        )
        assert assigned.status_code == 200, assigned.get_json()
        payload = assigned.get_json()["data"]
        cls.assignment_id = payload["assignment"]["id"]
        assert cls.assignment_id, payload

    @classmethod
    def _make_driver(cls, label, phone):
        created = cls.owner.post("/api/drivers", json={
            "display_name": "App Driver %s %s" % (label, cls.marker),
            "phone": phone,
            "primary_branch_code": "BLR",
        })
        assert created.status_code == 201, created.get_json()
        driver_id = created.get_json()["data"]["id"]
        reviewed = cls.owner.post("/api/drivers/%s/reviews" % driver_id, json={
            "decision": "verified",
            "reason": "Driver app test verification",
        })
        assert reviewed.status_code == 200, reviewed.get_json()
        activated = cls.owner.post("/api/drivers/%s/active" % driver_id, json={
            "active": True,
            "reason": "Driver app test activation",
        })
        assert activated.status_code == 200, activated.get_json()
        linked = cls.owner.post("/api/companies/%s/drivers" % cls.company_id, json={
            "driver_id": driver_id,
        })
        assert linked.status_code in (200, 201), linked.get_json()
        return driver_id

    def _driver_client(self, phone):
        client = app_module.app.test_client()
        login = client.post("/api/driver/login", json={
            "phone": phone,
            "password": self.password,
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        token = login.get_json()["token"]
        client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
        return client

    def test_01_login_and_isolation(self):
        bad = app_module.app.test_client().post("/api/driver/login", json={
            "phone": self.phone_a,
            "password": "wrong-password-xx",
        })
        self.assertEqual(bad.status_code, 401)
        client_a = self._driver_client(self.phone_a)
        duties = client_a.get("/api/driver/duties?filter=pending")
        self.assertEqual(duties.status_code, 200, duties.get_json())
        rows = duties.get_json()["duties"]
        self.assertTrue(any(row["assignment_id"] == self.assignment_id for row in rows))
        client_b = self._driver_client(self.phone_b)
        other = client_b.get("/api/driver/duties/%s" % self.assignment_id)
        self.assertEqual(other.status_code, 404)
        accept_b = client_b.post("/api/driver/duties/%s/accept" % self.assignment_id)
        self.assertEqual(accept_b.status_code, 404)

    def test_02_accept_start_complete_and_readings(self):
        if not self.driver_can_lock_booking:
            raise unittest.SkipTest(
                "Apply dev-db/012_driver_booking_lock_grant.sql to "
                + self.database_name
                + " before driver accept/start tests"
            )
        client = self._driver_client(self.phone_a)
        accept = client.post("/api/driver/duties/%s/accept" % self.assignment_id)
        self.assertEqual(accept.status_code, 200, accept.get_json())
        self.assertEqual(accept.get_json()["duty"]["assignment_status"], "accepted")
        again = client.post("/api/driver/duties/%s/accept" % self.assignment_id)
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.get_json().get("already"))
        bad_km = client.post(
            "/api/driver/duties/%s/start" % self.assignment_id,
            json={"start_km": -1},
        )
        self.assertEqual(bad_km.status_code, 400)
        start = client.post(
            "/api/driver/duties/%s/start" % self.assignment_id,
            json={"start_km": 100.5},
        )
        self.assertEqual(start.status_code, 200, start.get_json())
        self.assertEqual(start.get_json()["duty"]["trip_session"]["status"], "active")
        low_end = client.post(
            "/api/driver/duties/%s/complete" % self.assignment_id,
            json={"end_km": 90},
        )
        self.assertEqual(low_end.status_code, 400)
        complete = client.post(
            "/api/driver/duties/%s/complete" % self.assignment_id,
            json={"end_km": 120},
        )
        self.assertEqual(complete.status_code, 200, complete.get_json())
        duty = complete.get_json()["duty"]
        self.assertEqual(duty["trip_session"]["status"], "closed")
        self.assertEqual(duty["readings"]["total_km"], 19.5)

    def test_03_payouts_read_only_and_notifications(self):
        client = self._driver_client(self.phone_a)
        payouts = client.get("/api/driver/payouts")
        self.assertEqual(payouts.status_code, 200, payouts.get_json())
        self.assertIn("payouts", payouts.get_json())
        notes = client.get("/api/driver/notifications")
        self.assertEqual(notes.status_code, 200, notes.get_json())
        self.assertTrue(isinstance(notes.get_json()["notifications"], list))
        dashboard = client.get("/api/driver/dashboard")
        self.assertEqual(dashboard.status_code, 200, dashboard.get_json())
        self.assertEqual(dashboard.get_json()["driver"]["id"], self.driver_a_id)

    def test_04_rac_json_untouched(self):
        self.assertEqual(digest(BACKEND / "rac_data.json"), self.rac_hash)


if __name__ == "__main__":
    unittest.main()
