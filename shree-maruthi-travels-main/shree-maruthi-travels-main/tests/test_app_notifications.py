"""Master Prompt 7: client/staff notification tests (requires migration 016)."""
import hashlib
import os
import sys
import unittest
import uuid
from datetime import date, timedelta
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
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    return name


class AppNotificationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        if not operations_notifications.notifications_schema_ready():
            raise unittest.SkipTest(
                "Apply dev-db/016_app_notifications.sql to "
                + cls.database_name
                + " before notification tests"
            )
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
            "name": "Notif company " + cls.marker,
            "branch_codes": ["BLR"],
        })
        assert company.status_code == 201, company.get_json()
        cls.company_id = company.get_json()["data"]["id"]
        email = "notif.client.%s@example.com" % cls.marker
        created = cls.owner.post("/api/clients", json={
            "email": email,
            "full_name": "Notif Client",
            "phone": "9000099%s" % cls.marker[:4],
        })
        assert created.status_code in (200, 201), created.get_json()
        client_user_id = created.get_json()["data"]["id"]
        linked = cls.owner.post(
            "/api/companies/%s/clients" % cls.company_id,
            json={"user_id": client_user_id},
        )
        assert linked.status_code in (200, 201), linked.get_json()
        provision = cls.owner.post(
            "/api/clients/%s/login-account" % client_user_id,
            json={"password": "NotifPass123!"},
        )
        assert provision.status_code in (200, 201), provision.get_json()
        cls.client_email = email
        cls.client_password = "NotifPass123!"

    def _client_http(self):
        client = app_module.app.test_client()
        login = client.post("/api/client/login", json={
            "email": self.client_email,
            "password": self.client_password,
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        return client

    def test_staff_notification_list_and_read(self):
        posted = operations_notifications.notify_staff(
            self.owner_id,
            kind="client_request",
            title="Test staff alert " + self.marker,
            body="Synthetic supervisor notification",
            event_key="staff-test:%s" % self.marker,
            branch_id=self.branch["BLR"],
            company_id=self.company_id,
        )
        self.assertTrue(posted and posted.get("ok"))
        listed = self.owner.get("/api/operations/notifications")
        self.assertEqual(listed.status_code, 200)
        data = listed.get_json()["data"]
        self.assertGreaterEqual(data["unread_count"], 1)
        match = next(
            (n for n in data["notifications"] if n["title"].endswith(self.marker)),
            None,
        )
        self.assertIsNotNone(match)
        marked = self.owner.post("/api/operations/notifications/%s/read" % match["id"])
        self.assertEqual(marked.status_code, 200)

    def test_client_notification_isolation_and_idempotency(self):
        event_key = "client-test:%s" % self.marker
        first = operations_notifications.notify_client(
            self.owner_id,
            company_id=self.company_id,
            kind="booking_received",
            title="Client alert " + self.marker,
            body="Your company alert",
            event_key=event_key,
        )
        second = operations_notifications.notify_client(
            self.owner_id,
            company_id=self.company_id,
            kind="booking_received",
            title="Client alert duplicate " + self.marker,
            body="Should not duplicate",
            event_key=event_key,
        )
        self.assertTrue(first and first.get("ok"))
        self.assertTrue(second and second.get("ok"))
        client = self._client_http()
        listed = client.get("/api/client/notifications")
        self.assertEqual(listed.status_code, 200, listed.get_json())
        payload = listed.get_json()
        titles = [n["title"] for n in payload.get("notifications") or []]
        self.assertEqual(sum(1 for t in titles if self.marker in t), 1)
        match = next(n for n in payload["notifications"] if self.marker in n["title"])
        marked = client.post("/api/client/notifications/%s/read" % match["id"], json={})
        self.assertEqual(marked.status_code, 200)

        other = app_module.app.test_client()
        # Unauthenticated client cannot list notifications.
        denied = other.get("/api/client/notifications")
        self.assertEqual(denied.status_code, 401)

    def test_emit_after_client_booking_best_effort(self):
        trip_date = (date.today() + timedelta(days=5)).isoformat()
        client = self._client_http()
        created = client.post("/api/client/bookings", json={
            "branch_code": "BLR",
            "trip_date": trip_date,
            "pickup_location": "Notif pickup",
            "passenger_name": "Notif passenger",
            "route": "Airport",
        })
        # Booking create must succeed even if notification insert fails later.
        self.assertIn(created.status_code, (200, 201), created.get_json())
        staff_list = self.owner.get("/api/operations/notifications")
        self.assertEqual(staff_list.status_code, 200)

    def test_client_cannot_see_driver_notifications_table(self):
        import psycopg
        dsn = dev_postgres.local_development_dsn()
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT has_table_privilege('smt_client', 'driver_notifications', 'SELECT')"
                )
                self.assertFalse(cur.fetchone()[0])

    def test_rac_json_untouched(self):
        self.assertEqual(self.rac_hash, digest(BACKEND / "rac_data.json"))


if __name__ == "__main__":
    unittest.main()
