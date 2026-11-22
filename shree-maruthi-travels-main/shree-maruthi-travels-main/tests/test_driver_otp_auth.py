"""Driver OTP login and password-reset tests against disposable *_test DB.

Requires migrations through 019_driver_otp_auth.sql.
Never targets smt_dev or production.
"""
import hashlib
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

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
os.environ["SMT_OTP_DEV_EXPOSE"] = "yes"
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(BACKEND))

import backend.app as app_module
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
            cur.execute("SELECT to_regclass('public.driver_auth_otps') IS NOT NULL")
            has_otp = cur.fetchone()[0]
    folded = (name or "").lower()
    if folded in ("smt_dev", "postgres", "template0", "template1") or "prod" in folded:
        raise unittest.SkipTest("refusing database " + name)
    if not folded.endswith("_test"):
        raise unittest.SkipTest("the disposable database name must end with _test")
    if address not in _LOCAL_SERVER_ADDRESSES:
        raise unittest.SkipTest("refusing a database server that is not on this machine")
    if not has_otp:
        raise unittest.SkipTest(
            "Apply dev-db/019_driver_otp_auth.sql to " + name + " before OTP tests"
        )
    return name


class DriverOtpAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        cls.owner = client_for(OWNER)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        if not owner.get("ok"):
            raise unittest.SkipTest("missing owner identity")
        digits = str(int(cls.marker[:8], 16) % 10**8).zfill(8)
        cls.phone = "83" + digits
        cls.password = "DriverPass!" + cls.marker[:4]
        created = cls.owner.post("/api/drivers", json={
            "display_name": "OTP Driver " + cls.marker,
            "phone": cls.phone,
            "primary_branch_code": "BLR",
        })
        assert created.status_code == 201, created.get_json()
        cls.driver_id = created.get_json()["data"]["id"]
        reviewed = cls.owner.post("/api/drivers/%s/reviews" % cls.driver_id, json={
            "decision": "verified",
            "reason": "OTP test verification",
        })
        assert reviewed.status_code == 200, reviewed.get_json()
        activated = cls.owner.post("/api/drivers/%s/active" % cls.driver_id, json={
            "active": True,
            "reason": "OTP test activation",
        })
        assert activated.status_code == 200, activated.get_json()
        provision = cls.owner.post(
            "/api/drivers/%s/login-account" % cls.driver_id,
            json={"password": cls.password},
        )
        assert provision.status_code in (200, 201), provision.get_json()

    def tearDown(self):
        self.assertEqual(digest(BACKEND / "rac_data.json"), self.rac_hash)

    def test_01_otp_login_flow(self):
        client = app_module.app.test_client()
        with mock.patch(
            "operations_driver_otp._send_whatsapp",
            return_value=(True, {"success": True}),
        ):
            requested = client.post("/api/driver/otp/request", json={
                "phone": self.phone,
                "purpose": "login",
            })
        self.assertEqual(requested.status_code, 200, requested.get_json())
        body = requested.get_json()
        self.assertTrue(body.get("success"))
        code = body.get("dev_code")
        self.assertTrue(isinstance(code, str) and len(code) == 6)

        bad = client.post("/api/driver/otp/login", json={
            "phone": self.phone,
            "code": "000000",
        })
        self.assertEqual(bad.status_code, 401)

        good = client.post("/api/driver/otp/login", json={
            "phone": self.phone,
            "code": code,
        })
        self.assertEqual(good.status_code, 200, good.get_json())
        self.assertTrue(good.get_json().get("token"))

        reuse = client.post("/api/driver/otp/login", json={
            "phone": self.phone,
            "code": code,
        })
        self.assertEqual(reuse.status_code, 401)

    def test_02_otp_password_reset_then_password_login(self):
        client = app_module.app.test_client()
        with mock.patch(
            "operations_driver_otp._send_whatsapp",
            return_value=(True, {"success": True}),
        ):
            requested = client.post("/api/driver/otp/request", json={
                "phone": self.phone,
                "purpose": "reset",
            })
        self.assertEqual(requested.status_code, 200, requested.get_json())
        code = requested.get_json().get("dev_code")
        self.assertTrue(isinstance(code, str) and len(code) == 6)
        new_password = "ResetPass!" + self.marker[:4]

        reset = client.post("/api/driver/otp/reset-password", json={
            "phone": self.phone,
            "code": code,
            "new_password": new_password,
        })
        self.assertEqual(reset.status_code, 200, reset.get_json())

        old_login = client.post("/api/driver/login", json={
            "phone": self.phone,
            "password": self.password,
        })
        self.assertEqual(old_login.status_code, 401)

        new_login = client.post("/api/driver/login", json={
            "phone": self.phone,
            "password": new_password,
        })
        self.assertEqual(new_login.status_code, 200, new_login.get_json())
        self.assertTrue(new_login.get_json().get("token"))
        self.password = new_password

    def test_03_unknown_phone_rejected(self):
        client = app_module.app.test_client()
        with mock.patch(
            "operations_driver_otp._send_whatsapp",
            return_value=(True, {"success": True}),
        ):
            requested = client.post("/api/driver/otp/request", json={
                "phone": "9000000099",
                "purpose": "login",
            })
        self.assertEqual(requested.status_code, 404)


if __name__ == "__main__":
    unittest.main()
