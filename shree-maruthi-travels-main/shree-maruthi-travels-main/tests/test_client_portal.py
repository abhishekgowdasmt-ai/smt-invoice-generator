"""Client portal API tests against a disposable *_test database.

Requires migration 011_client_portal.sql (and prior finance/duty migrations).
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
import client_auth
import dev_postgres
import staff_auth

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
            "Apply dev-db/011_client_portal.sql to " + name + " before client portal tests"
        )
    return name


class ClientPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        cls.owner = client_for(OWNER)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        if not owner.get("ok"):
            raise unittest.SkipTest("missing owner identity")
        cls.owner_id = owner["id"]
        cls.password = "ClientPass!" + cls.marker[:4]

        co_a = cls.owner.post("/api/companies", json={
            "name": "Client Portal A " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert co_a.status_code == 201, co_a.get_json()
        cls.company_a = co_a.get_json()["data"]["id"]
        co_b = cls.owner.post("/api/companies", json={
            "name": "Client Portal B " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert co_b.status_code == 201, co_b.get_json()
        cls.company_b = co_b.get_json()["data"]["id"]

        email_a = "client.a.%s@example.com" % cls.marker
        email_b = "client.b.%s@example.com" % cls.marker
        user_a = cls.owner.post("/api/clients", json={
            "full_name": "Client A " + cls.marker,
            "email": email_a,
            "phone": "9000000001",
        })
        user_b = cls.owner.post("/api/clients", json={
            "full_name": "Client B " + cls.marker,
            "email": email_b,
            "phone": "9000000002",
        })
        assert user_a.status_code == 201, user_a.get_json()
        assert user_b.status_code == 201, user_b.get_json()
        cls.user_a = user_a.get_json()["data"]["id"]
        cls.user_b = user_b.get_json()["data"]["id"]
        cls.email_a = email_a
        cls.email_b = email_b

        link_a = cls.owner.post(
            "/api/companies/%s/clients" % cls.company_a,
            json={"user_id": cls.user_a},
        )
        link_b = cls.owner.post(
            "/api/companies/%s/clients" % cls.company_b,
            json={"user_id": cls.user_b},
        )
        assert link_a.status_code in (200, 201), link_a.get_json()
        assert link_b.status_code in (200, 201), link_b.get_json()

        prov_a = cls.owner.post(
            "/api/clients/%s/login-account" % cls.user_a,
            json={"password": cls.password},
        )
        prov_b = cls.owner.post(
            "/api/clients/%s/login-account" % cls.user_b,
            json={"password": cls.password},
        )
        assert prov_a.status_code == 201, prov_a.get_json()
        assert prov_b.status_code == 201, prov_b.get_json()

    def _portal(self, email):
        client = app_module.app.test_client()
        login = client.post("/api/client/login", json={
            "email": email,
            "password": self.password,
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        return client

    def test_01_auth_and_session(self):
        anon = app_module.app.test_client().get("/api/client/dashboard")
        self.assertEqual(anon.status_code, 401)
        bad = app_module.app.test_client().post("/api/client/login", json={
            "email": self.email_a,
            "password": "wrong-password-xx",
        })
        self.assertEqual(bad.status_code, 401)
        client = self._portal(self.email_a)
        session = client.get("/api/client/session")
        self.assertEqual(session.status_code, 200, session.get_json())
        body = session.get_json()
        self.assertEqual(body["company"]["id"], self.company_a)
        self.assertEqual(body["user"]["email"], self.email_a)
        logout = client.post("/api/client/logout")
        self.assertEqual(logout.status_code, 200)
        after = client.get("/api/client/dashboard")
        self.assertEqual(after.status_code, 401)

    def test_02_booking_isolation_and_request(self):
        a = self._portal(self.email_a)
        b = self._portal(self.email_b)
        created = a.post("/api/client/bookings", json={
            "branch_code": "BLR",
            "trip_date": "2031-04-10",
            "pickup_time": "10:30",
            "pickup_location": "Client A pickup",
            "passenger_name": "Emp A",
            "duty_type": "Airport",
            "cab_type": "SUV",
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        booking_id = created.get_json()["booking"]["id"]
        self.assertEqual(created.get_json()["booking"]["status"], "unassigned")
        self.assertEqual(created.get_json()["booking"]["origin"], "client_request")

        other = b.get("/api/client/bookings/%s" % booking_id)
        self.assertEqual(other.status_code, 404)
        assign_attempt = b.post(
            "/api/operations/bookings/%s/assign" % booking_id,
            json={"driver_id": str(uuid.uuid4())},
        )
        self.assertIn(assign_attempt.status_code, (401, 403))

        forbidden_company = a.patch("/api/client/profile", json={
            "company_id": self.company_b,
        })
        self.assertEqual(forbidden_company.status_code, 403)

    def test_03_invoice_payment_isolation_and_supervisor_block(self):
        a = self._portal(self.email_a)
        b = self._portal(self.email_b)
        invoices_a = a.get("/api/client/invoices")
        invoices_b = b.get("/api/client/invoices")
        self.assertEqual(invoices_a.status_code, 200)
        self.assertEqual(invoices_b.status_code, 200)
        # Cross-company fake UUID should 404, not leak.
        fake = str(uuid.uuid4())
        self.assertEqual(a.get("/api/client/invoices/%s" % fake).status_code, 404)
        self.assertEqual(a.get("/api/client/payments").status_code, 200)
        # Supervisor finance create blocked for client cookie session.
        issue = a.post("/api/finance/invoices", json={"company_id": self.company_a})
        self.assertIn(issue.status_code, (401, 403, 404, 405))

    def test_04_rac_untouched(self):
        self.assertEqual(digest(BACKEND / "rac_data.json"), self.rac_hash)


if __name__ == "__main__":
    unittest.main()
