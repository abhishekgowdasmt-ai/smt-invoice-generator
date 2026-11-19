import hashlib
import os
import sqlite3
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "backend"
for key in ("STAFF_TOKEN", "RAC_JWT_SECRET", "SMT_DEV_DATABASE_URL", "SMT_DEV_BOOTSTRAP_OWNER_ID"):
    os.environ.pop(key, None)
load_dotenv(APP_ROOT / ".env")
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(BACKEND))

import backend.app as app_module
import dev_postgres
import staff_auth

OWNER = "abhishekgowdasmt@gmail.com"
STAFF = "bhaskarbhaskarreddy9005@gmail.com"


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sqlite_counts():
    database = BACKEND / "database.db"
    connection = sqlite3.connect("file:" + str(database) + "?mode=ro", uri=True)
    try:
        cursor = connection.cursor()
        return {
            name: cursor.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            for name in ("drivers", "cabs", "company_cabs", "cab_documents", "companies")
        }
    finally:
        connection.close()


def client_for(email):
    client = app_module.app.test_client()
    token = staff_auth.issue_token(email)
    if token:
        client.set_cookie("smt_staff", token)
    return client


class DriverDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if dev_postgres.local_development_dsn() is None:
            raise unittest.SkipTest("local database is not configured")
        cls.owner = client_for(OWNER)
        cls.marker = uuid.uuid4().hex[:8]
        cls.name = "Phase 10B " + cls.marker
        cls.files = {
            "rac": digest(BACKEND / "rac_data.json"),
            "history": digest(BACKEND / "data" / "rac_drivers.json"),
        }
        cls.sqlite = sqlite_counts()

    def test_owner_directory_and_boundaries(self):
        listed = self.owner.get("/api/drivers")
        self.assertEqual(listed.status_code, 200)
        before = len(listed.get_json()["data"])

        created = self.owner.post("/api/drivers", json={
            "display_name": self.name,
            "phone": "0803333333",
            "license_number": "DL-10B-" + self.marker,
            "license_expiry": "2031-04-01",
            "primary_branch_code": "BLR",
            "user_id": str(uuid.uuid4()),
        })
        self.assertEqual(created.status_code, 400)
        self.assertIn("cannot be set", created.get_json()["message"])

        created = self.owner.post("/api/drivers", json={
            "display_name": self.name,
            "phone": "0803333333",
            "license_number": "DL-10B-" + self.marker,
            "license_expiry": "2031-04-01",
            "primary_branch_code": "blr",
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        driver = created.get_json()["data"]
        self.assertEqual(driver["display_name"], self.name)
        self.assertFalse(driver["active"])
        self.assertEqual(driver["verification_status"], "unverified")
        self.assertEqual(driver["primary_branch"]["code"], "BLR")
        self.assertEqual(driver["branches"][0]["code"], "BLR")
        self.assertTrue(driver["branches"][0]["primary"])
        self.assertNotIn("user_id", driver)
        self.assertNotIn("password_hash", driver)
        self.assertNotIn("google_sub", driver)

        detail = self.owner.get("/api/drivers/" + driver["id"])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["data"]["branches"][0]["primary"], True)

        duplicate = self.owner.post("/api/drivers", json={
            "display_name": self.name,
            "license_number": "DL-10B-" + self.marker,
            "primary_branch_code": "BLR",
        })
        self.assertEqual(duplicate.status_code, 201)
        self.assertNotEqual(duplicate.get_json()["data"]["id"], driver["id"])

        invalid_branch = self.owner.post("/api/drivers", json={
            "display_name": self.name + " nowhere",
            "primary_branch_code": "DEL",
        })
        self.assertEqual(invalid_branch.status_code, 400)
        blank = self.owner.post("/api/drivers", json={
            "display_name": "   ",
            "primary_branch_code": "BLR",
        })
        self.assertEqual(blank.status_code, 400)
        bad_date = self.owner.post("/api/drivers", json={
            "display_name": self.name + " date",
            "license_expiry": "31-04-2031",
            "primary_branch_code": "HYD",
        })
        self.assertEqual(bad_date.status_code, 400)

        owner_id = dev_postgres.resolve_login_identity(OWNER)["id"]
        branch_id = dev_postgres.list_branches()[0]["id"]
        probe = self.name + " rollback"

        def fail_membership(cur):
            driver_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO drivers (id, primary_branch_id, display_name, active)
                VALUES (%s::uuid, %s::uuid, %s, true)
                """,
                (driver_id, branch_id, probe),
            )
            cur.execute(
                """
                INSERT INTO driver_branches (driver_id, branch_id)
                VALUES (%s::uuid, %s::uuid)
                """,
                (driver_id, str(uuid.uuid4())),
            )

        self.assertIsNone(dev_postgres.authorized_transaction(owner_id, fail_membership))
        after_rollback = self.owner.get("/api/drivers", query_string={"name": probe})
        self.assertEqual(after_rollback.get_json()["data"], [])

        edited = self.owner.patch("/api/drivers/" + driver["id"], json={
            "phone": "0804444444",
            "license_number": "DL-10B-EDIT-" + self.marker,
            "license_expiry": "2032-05-02",
        })
        self.assertEqual(edited.status_code, 200)
        edited_driver = edited.get_json()["data"]
        self.assertEqual(edited_driver["phone"], "0804444444")
        self.assertEqual(edited_driver["license_number"], "DL-10B-EDIT-" + self.marker)
        self.assertEqual(edited_driver["license_expiry"], "2032-05-02")
        self.assertEqual(edited_driver["primary_branch"]["code"], "BLR")

        move = self.owner.patch("/api/drivers/" + driver["id"], json={"primary_branch_code": "HYD"})
        self.assertEqual(move.status_code, 400)
        self.assertIn("Primary branch", move.get_json()["message"])
        stayed = self.owner.get("/api/drivers/" + driver["id"])
        self.assertEqual(stayed.get_json()["data"]["primary_branch"]["code"], "BLR")

        inactive = self.owner.patch("/api/drivers/" + driver["id"], json={"active": True})
        self.assertEqual(inactive.status_code, 400)
        self.assertIn("unverified", inactive.get_json()["message"].lower())
        self.assertNotIn("not available", inactive.get_json()["message"].lower())
        hidden = self.owner.get("/api/drivers", query_string={"name": self.name, "active": "true"})
        self.assertNotIn(driver["id"], [row["id"] for row in hidden.get_json()["data"]])
        shown = self.owner.get("/api/drivers", query_string={"name": self.name, "active": "false", "branch": "BLR"})
        self.assertIn(driver["id"], [row["id"] for row in shown.get_json()["data"]])
        other_city = self.owner.get("/api/drivers", query_string={"name": self.name, "branch": "HYD"})
        self.assertNotIn(driver["id"], [row["id"] for row in other_city.get_json()["data"]])

        staff = client_for(STAFF)
        self.assertEqual(staff.get("/api/drivers").status_code, 403)
        self.assertEqual(staff.post("/api/drivers", json={
            "display_name": self.name + " staff",
            "primary_branch_code": "BLR",
        }).status_code, 403)
        self.assertEqual(len(self.owner.get("/api/drivers").get_json()["data"]), before + 2)

        client_email = "phase10b-" + self.marker + "@example.com"
        client_created = self.owner.post("/api/clients", json={
            "full_name": "Phase 10B Client",
            "email": client_email,
        })
        self.assertEqual(client_created.status_code, 201)
        with patch.object(app_module, "accepted_staff", lambda: {"email": client_email, "role": "staff"}):
            client_denied = app_module.app.test_client().get("/api/drivers")
        self.assertEqual(client_denied.status_code, 403)

        def driver_identity(email):
            return {"ok": True, "role": "driver", "id": owner_id, "status": "active"}

        with patch.object(app_module, "accepted_staff", lambda: {"email": "phase10b-driver@example.com", "role": "staff"}), \
             patch.object(dev_postgres, "resolve_login_identity", driver_identity):
            driver_denied = app_module.app.test_client().get("/api/drivers")
        self.assertEqual(driver_denied.status_code, 403)

        anonymous = app_module.app.test_client()
        self.assertEqual(anonymous.get("/api/drivers").status_code, 401)
        self.assertEqual(anonymous.post("/api/drivers", json={
            "display_name": self.name + " anon",
            "primary_branch_code": "BLR",
        }).status_code, 401)

        companies = self.owner.get("/api/companies")
        self.assertEqual(companies.status_code, 200)
        self.assertIsInstance(companies.get_json()["data"], list)
        dashboard = self.owner.get("/api/v1/dashboard/summary")
        self.assertEqual(dashboard.status_code, 200)
        self.assertTrue(dashboard.get_json()["success"])
        self.assertNotIn("psycopg", created.get_data(as_text=True).lower())
        self.assertEqual(self.files["rac"], digest(BACKEND / "rac_data.json"))
        self.assertEqual(self.files["history"], digest(BACKEND / "data" / "rac_drivers.json"))
        self.assertEqual(self.sqlite, sqlite_counts())


if __name__ == "__main__":
    unittest.main()
