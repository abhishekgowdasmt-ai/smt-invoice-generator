"""Master Prompt 8: cross-application workflow integration tests.

Covers client ↔ supervisor ↔ driver status sync, finance billable visibility,
notification isolation, and retry/invalid-transition handling on disposable
smt_revision8_test only.
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
import operations_notifications
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
            cur.execute("SELECT to_regclass('public.driver_notifications') IS NOT NULL")
            has_driver_notif = cur.fetchone()[0]
            cur.execute(
                """
                SELECT to_regclass('public.client_notifications') IS NOT NULL
                   AND to_regclass('public.staff_notifications') IS NOT NULL
                """
            )
            has_app_notif = cur.fetchone()[0]
            cur.execute(
                "SELECT has_column_privilege('smt_driver', 'bookings', 'status', 'UPDATE')"
            )
            driver_can_lock = cur.fetchone()[0]
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    if not has_driver_notif:
        raise unittest.SkipTest("Apply migration 010 to " + name)
    if not has_app_notif:
        raise unittest.SkipTest("Apply migrations 016 and 017 to " + name)
    return name, bool(driver_can_lock)


class CrossAppWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name, cls.driver_can_lock = require_disposable_local_database()
        if not operations_duty.assignment_triggers_ready():
            raise unittest.SkipTest("Assignment triggers need migration 007")
        if not operations_finance.finance_schema_ready():
            raise unittest.SkipTest("Finance schema needs migration 009")
        if not operations_notifications.notifications_schema_ready():
            raise unittest.SkipTest("Apply 016/017 notification migrations")
        cls.owner = staff_client(OWNER)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        if not owner.get("ok"):
            raise unittest.SkipTest("missing owner identity")
        cls.owner_id = owner["id"]
        branches = cls.owner.get("/api/branches").get_json()["data"]
        cls.branch = {row["code"]: row["id"] for row in branches}

        company = cls.owner.post("/api/companies", json={
            "name": "XApp Co " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert company.status_code == 201, company.get_json()
        cls.company_id = company.get_json()["data"]["id"]

        other = cls.owner.post("/api/companies", json={
            "name": "XApp Other " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert other.status_code == 201, other.get_json()
        cls.other_company_id = other.get_json()["data"]["id"]

        cls.client_password = "ClientPass!" + cls.marker[:4]
        cls.driver_password = "DriverPass!" + cls.marker[:4]
        cls.client_email = "xapp.client.%s@example.com" % cls.marker
        cls.other_email = "xapp.other.%s@example.com" % cls.marker

        client_user = cls.owner.post("/api/clients", json={
            "full_name": "XApp Client " + cls.marker,
            "email": cls.client_email,
            "phone": "71" + str(int(cls.marker[:8], 16) % 10**8).zfill(8),
        })
        assert client_user.status_code == 201, client_user.get_json()
        cls.client_user_id = client_user.get_json()["data"]["id"]
        assert cls.owner.post(
            "/api/companies/%s/clients" % cls.company_id,
            json={"user_id": cls.client_user_id},
        ).status_code in (200, 201)
        assert cls.owner.post(
            "/api/clients/%s/login-account" % cls.client_user_id,
            json={"password": cls.client_password},
        ).status_code in (200, 201)

        other_user = cls.owner.post("/api/clients", json={
            "full_name": "XApp Other Client " + cls.marker,
            "email": cls.other_email,
            "phone": "72" + str(int(cls.marker[:8], 16) % 10**8).zfill(8),
        })
        assert other_user.status_code == 201, other_user.get_json()
        cls.other_user_id = other_user.get_json()["data"]["id"]
        assert cls.owner.post(
            "/api/companies/%s/clients" % cls.other_company_id,
            json={"user_id": cls.other_user_id},
        ).status_code in (200, 201)
        assert cls.owner.post(
            "/api/clients/%s/login-account" % cls.other_user_id,
            json={"password": cls.client_password},
        ).status_code in (200, 201)

        phone_a = "81" + str(int(cls.marker[:8], 16) % 10**8).zfill(8)
        phone_b = "82" + str((int(cls.marker[:8], 16) + 1) % 10**8).zfill(8)
        cls.driver_a = cls._create_driver("XApp Driver A " + cls.marker, phone_a)
        cls.driver_b = cls._create_driver("XApp Driver B " + cls.marker, phone_b)
        cls.driver_a_phone = phone_a
        cls.driver_b_phone = phone_b

        vehicle = cls.owner.post("/api/vehicles", json={
            "branch_code": "BLR",
            "registration_number": "XA" + cls.marker.upper()[:6],
            "model": "Innova",
            "status": "active",
        })
        assert vehicle.status_code == 201, vehicle.get_json()
        cls.vehicle_id = vehicle.get_json()["data"]["id"]
        assert cls.owner.post(
            "/api/companies/%s/vehicles" % cls.company_id,
            json={"vehicle_id": cls.vehicle_id},
        ).status_code in (200, 201)

    @classmethod
    def _create_driver(cls, name, phone):
        created = cls.owner.post("/api/drivers", json={
            "display_name": name,
            "phone": phone,
            "primary_branch_code": "BLR",
        })
        assert created.status_code == 201, created.get_json()
        driver_id = created.get_json()["data"]["id"]
        assert cls.owner.post("/api/drivers/%s/reviews" % driver_id, json={
            "decision": "verified",
            "reason": "XApp verification",
        }).status_code == 200
        assert cls.owner.post("/api/drivers/%s/active" % driver_id, json={
            "active": True,
            "reason": "XApp activation",
        }).status_code == 200
        assert cls.owner.post(
            "/api/companies/%s/drivers" % cls.company_id,
            json={"driver_id": driver_id},
        ).status_code in (200, 201)
        assert cls.owner.post(
            "/api/drivers/%s/login-account" % driver_id,
            json={"password": cls.driver_password},
        ).status_code in (200, 201)
        return driver_id

    def _portal(self, email=None):
        client = app_module.app.test_client()
        login = client.post("/api/client/login", json={
            "email": email or self.client_email,
            "password": self.client_password,
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        return client

    def _driver(self, phone):
        client = app_module.app.test_client()
        login = client.post("/api/driver/login", json={
            "phone": phone,
            "password": self.driver_password,
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        token = login.get_json()["token"]
        client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
        return client

    def _require_lock(self):
        if not self.driver_can_lock:
            raise unittest.SkipTest(
                "Apply 012_driver_booking_lock_grant.sql to " + self.database_name
            )

    def _client_booking(self, portal, trip_date, suffix=""):
        created = portal.post("/api/client/bookings", json={
            "branch_code": "BLR",
            "trip_date": trip_date,
            "pickup_time": "11:00",
            "pickup_location": "XApp pickup " + self.marker + suffix,
            "passenger_name": "XApp passenger " + self.marker + suffix,
            "duty_type": "Local",
            "cab_type": "SUV",
            "route": "Office route",
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        return created.get_json()["booking"]

    def test_a_client_request_visible_to_supervisor(self):
        portal = self._portal()
        booking = self._client_booking(portal, "2032-01-11", "-a")
        listed = self.owner.get("/api/operations/bookings?origin=client_request")
        self.assertEqual(listed.status_code, 200)
        rows = listed.get_json()["data"]
        self.assertTrue(any(r["id"] == booking["id"] for r in rows))

    def test_b_assign_driver_duty_and_notification(self):
        self._require_lock()
        portal = self._portal()
        booking = self._client_booking(portal, "2032-01-12", "-b")
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={
                "driver_id": self.driver_a,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        self.assertEqual(assigned.status_code, 200, assigned.get_json())
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        driver = self._driver(self.driver_a_phone)
        duties = driver.get("/api/driver/duties?filter=all")
        self.assertEqual(duties.status_code, 200, duties.get_json())
        duty_rows = duties.get_json()["duties"]
        self.assertTrue(any(d["assignment_id"] == assignment_id for d in duty_rows), duty_rows)
        notes = driver.get("/api/driver/notifications")
        self.assertEqual(notes.status_code, 200)
        self.assertTrue(
            any(n.get("assignment_id") == assignment_id for n in notes.get_json()["notifications"])
        )

    def test_c_e_f_accept_start_complete_status_consistency(self):
        self._require_lock()
        portal = self._portal()
        booking = self._client_booking(portal, "2032-01-13", "-cef")
        booking_id = booking["id"]
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={
                "driver_id": self.driver_a,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        driver = self._driver(self.driver_a_phone)

        accept = driver.post("/api/driver/duties/%s/accept" % assignment_id)
        self.assertEqual(accept.status_code, 200, accept.get_json())
        ops = self.owner.get("/api/operations/bookings/%s/trip" % booking_id)
        self.assertEqual(ops.status_code, 200, ops.get_json())
        self.assertEqual(ops.get_json()["data"]["booking"]["status"], "accepted")
        detail = portal.get("/api/client/bookings/%s" % booking_id)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["booking"]["status"], "accepted")

        start = driver.post(
            "/api/driver/duties/%s/start" % assignment_id,
            json={"start_km": 100},
        )
        self.assertEqual(start.status_code, 200, start.get_json())
        ops = self.owner.get("/api/operations/bookings/%s/trip" % booking_id)
        self.assertEqual(ops.get_json()["data"]["booking"]["status"], "started")
        detail = portal.get("/api/client/bookings/%s" % booking_id)
        self.assertEqual(detail.get_json()["booking"]["status"], "started")

        complete = driver.post(
            "/api/driver/duties/%s/complete" % assignment_id,
            json={"end_km": 140},
        )
        self.assertEqual(complete.status_code, 200, complete.get_json())
        trips = portal.get("/api/client/trips?filter=completed")
        match = next(
            (t for t in trips.get_json()["trips"] if t["booking_id"] == booking_id),
            None,
        )
        self.assertIsNotNone(match)
        self.assertEqual(match["duty_status"], "completed")
        ops = self.owner.get("/api/operations/bookings/%s/trip" % booking_id)
        self.assertEqual(ops.get_json()["data"]["booking"]["status"], "completed")

        # Client trip notification after driver complete (owner-mediated emit)
        notes = portal.get("/api/client/notifications")
        self.assertEqual(notes.status_code, 200, notes.get_json())
        titles = [n["title"] for n in notes.get_json().get("notifications") or []]
        self.assertTrue(any("completed" in t.lower() for t in titles), titles)

    def test_d_reject_then_reassign(self):
        self._require_lock()
        portal = self._portal()
        booking = self._client_booking(portal, "2032-01-14", "-d")
        booking_id = booking["id"]
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={"driver_id": self.driver_a, "vehicle_id": self.vehicle_id, "send_message": False},
        )
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        driver_a = self._driver(self.driver_a_phone)
        rejected = driver_a.post(
            "/api/driver/duties/%s/reject" % assignment_id,
            json={"reason": "Unavailable for XApp test"},
        )
        self.assertEqual(rejected.status_code, 200, rejected.get_json())
        ops = self.owner.get("/api/operations/bookings/%s/trip" % booking_id)
        self.assertEqual(ops.get_json()["data"]["booking"]["status"], "unassigned")

        staff_notes = self.owner.get("/api/operations/notifications")
        self.assertEqual(staff_notes.status_code, 200)
        kinds = [n["kind"] for n in staff_notes.get_json()["data"]["notifications"]]
        self.assertIn("driver_reject", kinds)

        reassigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={"driver_id": self.driver_b, "vehicle_id": self.vehicle_id, "send_message": False},
        )
        self.assertEqual(reassigned.status_code, 200, reassigned.get_json())
        new_id = reassigned.get_json()["data"]["assignment"]["id"]
        driver_b = self._driver(self.driver_b_phone)
        duties = driver_b.get("/api/driver/duties?filter=all")
        self.assertTrue(any(d["assignment_id"] == new_id for d in duties.get_json()["duties"]))

    def test_g_completed_duty_billable(self):
        self._require_lock()
        portal = self._portal()
        booking = self._client_booking(portal, "2032-01-15", "-g")
        booking_id = booking["id"]
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={"driver_id": self.driver_a, "vehicle_id": self.vehicle_id, "send_message": False},
        )
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        driver = self._driver(self.driver_a_phone)
        self.assertEqual(driver.post("/api/driver/duties/%s/accept" % assignment_id).status_code, 200)
        self.assertEqual(
            driver.post("/api/driver/duties/%s/start" % assignment_id, json={"start_km": 10}).status_code,
            200,
        )
        self.assertEqual(
            driver.post("/api/driver/duties/%s/complete" % assignment_id, json={"end_km": 25}).status_code,
            200,
        )
        billable = self.owner.get(
            "/api/finance/companies/%s/billable-bookings" % self.company_id
        )
        self.assertEqual(billable.status_code, 200, billable.get_json())
        rows = billable.get_json()["data"]
        if isinstance(rows, dict):
            rows = rows.get("bookings") or rows.get("data") or []
        self.assertTrue(any(r.get("id") == booking_id for r in rows), rows)

        # Incomplete request must not appear as completed billable
        open_booking = self._client_booking(portal, "2032-01-16", "-g2")
        billable2 = self.owner.get(
            "/api/finance/companies/%s/billable-bookings" % self.company_id
        )
        rows2 = billable2.get_json()["data"]
        if isinstance(rows2, dict):
            rows2 = rows2.get("bookings") or []
        self.assertFalse(any(r.get("id") == open_booking["id"] for r in rows2))

    def test_h_notification_read_and_isolation(self):
        portal = self._portal()
        booking = self._client_booking(portal, "2032-01-17", "-h")
        # Client booking emit creates client + staff notifications
        notes = portal.get("/api/client/notifications")
        self.assertEqual(notes.status_code, 200, notes.get_json())
        payload = notes.get_json()
        unread_before = payload.get("unread_count") or 0
        self.assertGreaterEqual(unread_before, 1)
        match = next(
            (n for n in payload["notifications"] if n.get("booking_id") == booking["id"]),
            payload["notifications"][0],
        )
        marked = portal.post("/api/client/notifications/%s/read" % match["id"], json={})
        self.assertEqual(marked.status_code, 200, marked.get_json())

        other = self._portal(self.other_email)
        other_notes = other.get("/api/client/notifications")
        self.assertEqual(other_notes.status_code, 200)
        other_ids = {n["id"] for n in other_notes.get_json().get("notifications") or []}
        self.assertNotIn(match["id"], other_ids)

        driver = self._driver(self.driver_a_phone)
        self.assertEqual(driver.get("/api/client/notifications").status_code, 401)

    def test_i_cross_company_and_cross_driver_denial(self):
        self._require_lock()
        portal = self._portal()
        booking = self._client_booking(portal, "2032-01-18", "-i")
        other = self._portal(self.other_email)
        denied = other.get("/api/client/bookings/%s" % booking["id"])
        self.assertEqual(denied.status_code, 404)

        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking["id"],
            json={"driver_id": self.driver_a, "vehicle_id": self.vehicle_id, "send_message": False},
        )
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        driver_b = self._driver(self.driver_b_phone)
        steal = driver_b.post("/api/driver/duties/%s/accept" % assignment_id)
        self.assertIn(steal.status_code, (403, 404))

    def test_j_retry_idempotency_and_invalid_transition(self):
        self._require_lock()
        portal = self._portal()
        body = {
            "branch_code": "BLR",
            "trip_date": "2032-01-19",
            "pickup_time": "11:00",
            "pickup_location": "XApp retry " + self.marker,
            "passenger_name": "XApp retry passenger " + self.marker,
            "duty_type": "Local",
            "cab_type": "SUV",
        }
        first = portal.post("/api/client/bookings", json=body)
        second = portal.post("/api/client/bookings", json=body)
        self.assertEqual(first.status_code, 201, first.get_json())
        self.assertEqual(second.status_code, 201, second.get_json())
        self.assertEqual(first.get_json()["booking"]["id"], second.get_json()["booking"]["id"])
        self.assertTrue(second.get_json().get("already"))

        booking_id = first.get_json()["booking"]["id"]
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={"driver_id": self.driver_a, "vehicle_id": self.vehicle_id, "send_message": False},
        )
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        driver = self._driver(self.driver_a_phone)
        early_start = driver.post(
            "/api/driver/duties/%s/start" % assignment_id,
            json={"start_km": 1},
        )
        self.assertEqual(early_start.status_code, 409)

    def test_rac_json_untouched(self):
        self.assertEqual(self.rac_hash, digest(BACKEND / "rac_data.json"))


if __name__ == "__main__":
    unittest.main()
