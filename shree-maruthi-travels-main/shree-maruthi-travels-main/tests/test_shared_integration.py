"""Cross-application integration tests (Master Prompt 5).

Covers client → supervisor → driver → client visibility on one PostgreSQL store.
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
import operations_duty
import operations_finance
import shared_api_contracts
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
            has_notifications = cur.fetchone()[0]
            cur.execute(
                """
                SELECT 1 FROM pg_constraint
                WHERE conname = 'bookings_origin_check'
                  AND pg_get_constraintdef(oid) LIKE '%%client_request%%'
                """
            )
            has_client_origin = cur.fetchone() is not None
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
        raise unittest.SkipTest("Apply dev-db/010_driver_app.sql to " + name)
    if not has_client_origin:
        raise unittest.SkipTest("Apply dev-db/011_client_portal.sql to " + name)
    return name, bool(driver_can_lock_booking)


class SharedIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name, cls.driver_can_lock_booking = require_disposable_local_database()
        if not operations_duty.assignment_triggers_ready():
            raise unittest.SkipTest("Assignment triggers need migration 007")
        if not operations_finance.finance_schema_ready():
            raise unittest.SkipTest("Finance schema needs migration 009")
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
            "name": "Shared Int Co " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert company.status_code == 201, company.get_json()
        cls.company_id = company.get_json()["data"]["id"]

        cls.client_password = "ClientPass!" + cls.marker[:4]
        cls.driver_password = "DriverPass!" + cls.marker[:4]
        cls.client_email = "shared.client.%s@example.com" % cls.marker
        client_user = cls.owner.post("/api/clients", json={
            "full_name": "Shared Client " + cls.marker,
            "email": cls.client_email,
            "phone": "70" + str(int(cls.marker[:8], 16) % 10**8).zfill(8),
        })
        assert client_user.status_code == 201, client_user.get_json()
        cls.client_user_id = client_user.get_json()["data"]["id"]
        link_client = cls.owner.post(
            "/api/companies/%s/clients" % cls.company_id,
            json={"user_id": cls.client_user_id},
        )
        assert link_client.status_code in (200, 201), link_client.get_json()
        provision_client = cls.owner.post(
            "/api/clients/%s/login-account" % cls.client_user_id,
            json={"password": cls.client_password},
        )
        assert provision_client.status_code in (200, 201), provision_client.get_json()

        phone = "91" + str(int(cls.marker[:8], 16) % 10**8).zfill(8)
        driver = cls.owner.post("/api/drivers", json={
            "display_name": "Shared Driver " + cls.marker,
            "phone": phone,
            "primary_branch_code": "BLR",
        })
        assert driver.status_code == 201, driver.get_json()
        cls.driver_id = driver.get_json()["data"]["id"]
        cls.driver_phone = phone
        reviewed = cls.owner.post("/api/drivers/%s/reviews" % cls.driver_id, json={
            "decision": "verified",
            "reason": "Shared integration verification",
        })
        assert reviewed.status_code == 200, reviewed.get_json()
        activated = cls.owner.post("/api/drivers/%s/active" % cls.driver_id, json={
            "active": True,
            "reason": "Shared integration activation",
        })
        assert activated.status_code == 200, activated.get_json()
        linked = cls.owner.post(
            "/api/companies/%s/drivers" % cls.company_id,
            json={"driver_id": cls.driver_id},
        )
        assert linked.status_code in (200, 201), linked.get_json()
        provision_driver = cls.owner.post(
            "/api/drivers/%s/login-account" % cls.driver_id,
            json={"password": cls.driver_password},
        )
        assert provision_driver.status_code in (200, 201), provision_driver.get_json()

        vehicle = cls.owner.post("/api/vehicles", json={
            "branch_code": "BLR",
            "registration_number": "SI" + cls.marker.upper()[:6],
            "model": "Innova",
            "status": "active",
        })
        assert vehicle.status_code == 201, vehicle.get_json()
        cls.vehicle_id = vehicle.get_json()["data"]["id"]
        linked_v = cls.owner.post(
            "/api/companies/%s/vehicles" % cls.company_id,
            json={"vehicle_id": cls.vehicle_id},
        )
        assert linked_v.status_code in (200, 201), linked_v.get_json()

    def _portal_client(self):
        client = app_module.app.test_client()
        login = client.post("/api/client/login", json={
            "email": self.client_email,
            "password": self.client_password,
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        return client

    def _driver_client(self):
        client = app_module.app.test_client()
        login = client.post("/api/driver/login", json={
            "phone": self.driver_phone,
            "password": self.driver_password,
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        token = login.get_json()["token"]
        client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
        return client

    def test_00_shared_error_contract(self):
        self.assertEqual(shared_api_contracts.http_status_for_error("conflict"), 409)
        self.assertEqual(shared_api_contracts.http_status_for_error("unauthorized"), 401)
        self.assertIn("client_request", shared_api_contracts.BOOKING_ORIGINS)
        self.assertIn("started", shared_api_contracts.BOOKING_STATUSES)

    def test_01_cross_role_access_denied(self):
        portal = self._portal_client()
        self.assertEqual(portal.get("/api/driver/duties").status_code, 401)
        self.assertEqual(portal.get("/api/operations/bookings").status_code, 401)
        self.assertEqual(portal.post("/api/finance/invoices", json={}).status_code, 401)
        self.assertEqual(
            portal.post(
                "/api/operations/bookings/%s/assign" % uuid.uuid4(),
                json={"driver_id": self.driver_id},
            ).status_code,
            401,
        )

        driver = self._driver_client()
        self.assertEqual(driver.get("/api/client/bookings").status_code, 401)
        self.assertEqual(driver.get("/api/finance/dashboard").status_code, 401)
        self.assertEqual(driver.post("/api/finance/invoices", json={}).status_code, 401)

    def _require_driver_lock_grant(self):
        if not self.driver_can_lock_booking:
            raise unittest.SkipTest(
                "Apply dev-db/012_driver_booking_lock_grant.sql to "
                + self.database_name
                + " so drivers can accept duties (FOR UPDATE lock)"
            )

    def test_02a_client_request_visible_to_supervisor(self):
        portal = self._portal_client()
        created = portal.post("/api/client/bookings", json={
            "branch_code": "BLR",
            "trip_date": "2031-04-09",
            "pickup_time": "09:15",
            "pickup_location": "Origin filter pickup " + self.marker,
            "passenger_name": "Origin passenger " + self.marker,
            "duty_type": "Local",
            "cab_type": "SUV",
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        booking_id = created.get_json()["booking"]["id"]
        self.assertEqual(created.get_json()["booking"]["origin"], "client_request")
        listed = self.owner.get("/api/operations/bookings?origin=client_request")
        self.assertEqual(listed.status_code, 200, listed.get_json())
        rows = listed.get_json()["data"]
        self.assertTrue(any(row["id"] == booking_id for row in rows), rows)
        found = next(row for row in rows if row["id"] == booking_id)
        self.assertEqual(found["origin"], "client_request")
        self.assertEqual(found["status"], "unassigned")
        bad = self.owner.get("/api/operations/bookings?origin=not_a_real_origin")
        self.assertEqual(bad.status_code, 400)

    def test_02_shared_booking_lifecycle_and_notifications(self):
        self._require_driver_lock_grant()
        portal = self._portal_client()
        created = portal.post("/api/client/bookings", json={
            "branch_code": "BLR",
            "trip_date": "2031-04-10",
            "pickup_time": "10:30",
            "pickup_location": "Shared pickup " + self.marker,
            "passenger_name": "Passenger " + self.marker,
            "duty_type": "Local",
            "cab_type": "SUV",
            "route": "Office to airport",
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        booking = created.get_json()["booking"]
        booking_id = booking["id"]
        self.assertEqual(booking["status"], "unassigned")
        self.assertEqual(booking["origin"], "client_request")

        listed = self.owner.get("/api/operations/bookings?origin=client_request")
        self.assertEqual(listed.status_code, 200, listed.get_json())
        rows = listed.get_json()["data"]
        self.assertTrue(any(row["id"] == booking_id for row in rows), rows)
        found = next(row for row in rows if row["id"] == booking_id)
        self.assertEqual(found["origin"], "client_request")
        self.assertEqual(found["status"], "unassigned")

        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={
                "driver_id": self.driver_id,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        self.assertEqual(assigned.status_code, 200, assigned.get_json())
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]

        driver = self._driver_client()
        notes = driver.get("/api/driver/notifications")
        self.assertEqual(notes.status_code, 200, notes.get_json())
        notifications = notes.get_json()["notifications"]
        self.assertTrue(
            any(n.get("assignment_id") == assignment_id for n in notifications),
            notifications,
        )

        other_driver_token_client = app_module.app.test_client()
        # Isolation: unauthenticated notification access denied
        anon = other_driver_token_client.get("/api/driver/notifications")
        self.assertEqual(anon.status_code, 401)

        accept = driver.post("/api/driver/duties/%s/accept" % assignment_id)
        self.assertEqual(accept.status_code, 200, accept.get_json())
        self.assertEqual(accept.get_json()["duty"]["assignment_status"], "accepted")

        start = driver.post(
            "/api/driver/duties/%s/start" % assignment_id,
            json={"start_km": 200},
        )
        self.assertEqual(start.status_code, 200, start.get_json())
        self.assertEqual(start.get_json()["duty"]["booking_status"], "started")

        # Concurrent second start from supervisor must conflict
        staff_start = self.owner.post("/api/operations/bookings/%s/start" % booking_id)
        self.assertEqual(staff_start.status_code, 409, staff_start.get_json())

        complete = driver.post(
            "/api/driver/duties/%s/complete" % assignment_id,
            json={"end_km": 230},
        )
        self.assertEqual(complete.status_code, 200, complete.get_json())
        self.assertEqual(complete.get_json()["duty"]["booking_status"], "completed")

        trips = portal.get("/api/client/trips")
        self.assertEqual(trips.status_code, 200, trips.get_json())
        trip_rows = trips.get_json()["trips"]
        match = next((t for t in trip_rows if t["booking_id"] == booking_id), None)
        self.assertIsNotNone(match, trip_rows)
        self.assertEqual(match["duty_status"], "completed")
        self.assertEqual(match["assignment_status"], "completed")
        self.assertTrue(match.get("driver_name"))
        self.assertNotIn("rejection_reason", match)

        booking_detail = portal.get("/api/client/bookings/%s" % booking_id)
        self.assertEqual(booking_detail.status_code, 200, booking_detail.get_json())
        self.assertEqual(booking_detail.get_json()["booking"]["status"], "completed")

        ops_trip = self.owner.get("/api/operations/bookings/%s/trip" % booking_id)
        self.assertEqual(ops_trip.status_code, 200, ops_trip.get_json())

        # Client cannot assign
        assign_attempt = portal.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={"driver_id": self.driver_id},
        )
        self.assertEqual(assign_attempt.status_code, 401)

    def test_03_finance_visibility_and_restrictions(self):
        # Staff lifecycle for invoicing does not need the driver lock grant.
        booking = self.owner.post("/api/operations/bookings", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "trip_date": "2031-04-11",
            "pickup_time": "11:00",
            "planned_start": "Finance pickup " + self.marker,
            "duty_type": "Airport",
            "employee_name": "Finance passenger " + self.marker,
            "source_booking_id": "SI-FIN-" + self.marker,
            "amount": 1800,
        })
        self.assertEqual(booking.status_code, 201, booking.get_json())
        booking_id = booking.get_json()["data"]["id"]
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={
                "driver_id": self.driver_id,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        self.assertEqual(assigned.status_code, 200, assigned.get_json())
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]
        self.assertEqual(
            self.owner.post(
                "/api/operations/assignments/%s/accept" % assignment_id, json={}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.owner.post("/api/operations/bookings/%s/start" % booking_id, json={}).status_code,
            200,
        )
        self.assertEqual(
            self.owner.post(
                "/api/operations/bookings/%s/complete" % booking_id, json={}
            ).status_code,
            200,
        )

        invoice = self.owner.post("/api/finance/invoices", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "due_date": "2031-05-01",
            "lines": [{
                "booking_id": booking_id,
                "description": "Shared integration duty " + self.marker,
                "amount": "1800.00",
            }],
        })
        self.assertEqual(invoice.status_code, 201, invoice.get_json())
        invoice_id = invoice.get_json()["data"]["invoice"]["id"]
        issued = self.owner.post("/api/finance/invoices/%s/issue" % invoice_id)
        self.assertEqual(issued.status_code, 200, issued.get_json())

        portal = self._portal_client()
        invoices = portal.get("/api/client/invoices")
        self.assertEqual(invoices.status_code, 200, invoices.get_json())
        ids = [row["id"] for row in invoices.get_json()["invoices"]]
        self.assertIn(invoice_id, ids)

        detail = portal.get("/api/client/invoices/%s" % invoice_id)
        self.assertEqual(detail.status_code, 200, detail.get_json())

        # Client cannot issue/void
        self.assertEqual(
            portal.post("/api/finance/invoices/%s/issue" % invoice_id).status_code, 401
        )
        self.assertEqual(
            portal.post("/api/finance/invoices/%s/void" % invoice_id).status_code, 401
        )

        driver = self._driver_client()
        self.assertEqual(driver.get("/api/client/invoices").status_code, 401)
        self.assertEqual(driver.get("/api/finance/invoices").status_code, 401)
        payouts = driver.get("/api/driver/payouts")
        self.assertEqual(payouts.status_code, 200, payouts.get_json())

    def test_04_invalid_transition_and_duplicate_start(self):
        self._require_driver_lock_grant()
        booking = self.owner.post("/api/operations/bookings", json={
            "branch_id": self.branch["BLR"],
            "company_id": self.company_id,
            "trip_date": "2031-04-12",
            "pickup_time": "08:00",
            "planned_start": "Conflict pickup " + self.marker,
            "duty_type": "Local",
            "employee_name": "Conflict passenger " + self.marker,
            "source_booking_id": "SI-CON-" + self.marker,
        })
        self.assertEqual(booking.status_code, 201, booking.get_json())
        booking_id = booking.get_json()["data"]["id"]
        assigned = self.owner.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={
                "driver_id": self.driver_id,
                "vehicle_id": self.vehicle_id,
                "send_message": False,
            },
        )
        self.assertEqual(assigned.status_code, 200, assigned.get_json())
        assignment_id = assigned.get_json()["data"]["assignment"]["id"]

        driver = self._driver_client()
        # Cannot start before accept
        early = driver.post(
            "/api/driver/duties/%s/start" % assignment_id,
            json={"start_km": 10},
        )
        self.assertEqual(early.status_code, 409, early.get_json())

        self.assertEqual(
            driver.post("/api/driver/duties/%s/accept" % assignment_id).status_code, 200
        )
        first = driver.post(
            "/api/driver/duties/%s/start" % assignment_id,
            json={"start_km": 10},
        )
        self.assertEqual(first.status_code, 200, first.get_json())
        second = driver.post(
            "/api/driver/duties/%s/start" % assignment_id,
            json={"start_km": 11},
        )
        self.assertEqual(second.status_code, 409, second.get_json())

    def test_05_rac_json_untouched(self):
        self.assertEqual(digest(BACKEND / "rac_data.json"), self.rac_hash)


if __name__ == "__main__":
    unittest.main()
