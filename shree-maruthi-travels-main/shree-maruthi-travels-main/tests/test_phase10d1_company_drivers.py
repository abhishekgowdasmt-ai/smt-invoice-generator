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


def company_vehicle_count(owner_id):
    def work(cur):
        cur.execute("SELECT count(*) FROM company_vehicles")
        return cur.fetchone()[0]

    done = dev_postgres.authorized_transaction(owner_id, work)
    if not done:
        return None
    return done["result"]


class CompanyDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if dev_postgres.local_development_dsn() is None:
            raise unittest.SkipTest("local database is not configured")
        cls.owner = client_for(OWNER)
        cls.marker = uuid.uuid4().hex[:8]
        cls.files = {
            "rac": digest(BACKEND / "rac_data.json"),
            "history": digest(BACKEND / "data" / "rac_drivers.json"),
        }
        cls.sqlite = sqlite_counts()

    def test_owner_links_and_boundaries(self):
        owner_id = dev_postgres.resolve_login_identity(OWNER)["id"]
        self.assertEqual(company_vehicle_count(owner_id), 0)

        bengaluru = self.owner.post("/api/companies", json={
            "name": "Phase 10D1 Bengaluru " + self.marker,
            "branch_codes": ["BLR"],
        })
        self.assertEqual(bengaluru.status_code, 201, bengaluru.get_data(as_text=True))
        company_id = bengaluru.get_json()["data"]["id"]
        second = self.owner.post("/api/companies", json={
            "name": "Phase 10D1 Second " + self.marker,
            "branch_codes": ["BLR"],
        })
        self.assertEqual(second.status_code, 201, second.get_data(as_text=True))
        second_id = second.get_json()["data"]["id"]
        hyderabad = self.owner.post("/api/companies", json={
            "name": "Phase 10D1 Hyderabad " + self.marker,
            "branch_codes": ["HYD"],
        })
        self.assertEqual(hyderabad.status_code, 201, hyderabad.get_data(as_text=True))
        hyderabad_id = hyderabad.get_json()["data"]["id"]

        empty = self.owner.get("/api/companies/" + company_id + "/drivers")
        self.assertEqual(empty.status_code, 200, empty.get_data(as_text=True))
        self.assertEqual(empty.get_json()["data"], [])

        driver = self.owner.post("/api/drivers", json={
            "display_name": "Phase 10D1 driver " + self.marker,
            "phone": "0807777777",
            "license_number": "DL-10D1-" + self.marker,
            "primary_branch_code": "BLR",
        })
        self.assertEqual(driver.status_code, 201, driver.get_data(as_text=True))
        driver_id = driver.get_json()["data"]["id"]
        inactive = self.owner.post("/api/drivers", json={
            "display_name": "Phase 10D1 inactive " + self.marker,
            "primary_branch_code": "BLR",
        })
        self.assertEqual(inactive.status_code, 201, inactive.get_data(as_text=True))
        inactive_id = inactive.get_json()["data"]["id"]
        paused = self.owner.patch("/api/drivers/" + inactive_id, json={"active": False})
        self.assertEqual(paused.status_code, 200, paused.get_data(as_text=True))

        rejected_fields = self.owner.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": driver_id,
            "user_id": str(uuid.uuid4()),
        })
        self.assertEqual(rejected_fields.status_code, 400)

        linked = self.owner.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": driver_id,
        })
        self.assertEqual(linked.status_code, 201, linked.get_data(as_text=True))
        rows = linked.get_json()["data"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], driver_id)
        self.assertEqual(rows[0]["display_name"], "Phase 10D1 driver " + self.marker)
        self.assertEqual(rows[0]["phone"], "0807777777")
        self.assertEqual(rows[0]["license_number"], "DL-10D1-" + self.marker)
        self.assertTrue(rows[0]["active"])
        self.assertEqual(rows[0]["primary_branch"]["code"], "BLR")
        self.assertNotIn("user_id", rows[0])

        second_link = self.owner.post("/api/companies/" + second_id + "/drivers", json={
            "driver_id": driver_id,
        })
        self.assertEqual(second_link.status_code, 201, second_link.get_data(as_text=True))
        self.assertEqual(second_link.get_json()["data"][0]["id"], driver_id)

        duplicate = self.owner.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": driver_id,
        })
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already", duplicate.get_json()["message"])

        paused_link = self.owner.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": inactive_id,
        })
        self.assertEqual(paused_link.status_code, 400)
        self.assertIn("inactive", paused_link.get_json()["message"])

        other_city = self.owner.post("/api/companies/" + hyderabad_id + "/drivers", json={
            "driver_id": driver_id,
        })
        self.assertEqual(other_city.status_code, 400)
        self.assertIn("share a city", other_city.get_json()["message"])

        missing_driver = self.owner.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": str(uuid.uuid4()),
        })
        self.assertEqual(missing_driver.status_code, 404)
        missing_company = self.owner.post("/api/companies/" + str(uuid.uuid4()) + "/drivers", json={
            "driver_id": driver_id,
        })
        self.assertEqual(missing_company.status_code, 404)

        with app_module.app.app_context():
            blocked, status = app_module._company_response({
                "ok": False,
                "error": "in_use",
                "message": "This driver is still used by an assignment for the company.",
            })
        self.assertEqual(status, 409)
        self.assertIn("assignment", blocked.get_json()["message"])
        still_linked = self.owner.get("/api/companies/" + company_id + "/drivers")
        self.assertIn(driver_id, [row["id"] for row in still_linked.get_json()["data"]])

        removed = self.owner.delete("/api/companies/" + second_id + "/drivers/" + driver_id)
        self.assertEqual(removed.status_code, 200, removed.get_data(as_text=True))
        self.assertEqual(removed.get_json()["data"], [])
        kept_driver = self.owner.get("/api/drivers/" + driver_id)
        self.assertEqual(kept_driver.status_code, 200)
        self.assertEqual(kept_driver.get_json()["data"]["display_name"], "Phase 10D1 driver " + self.marker)
        kept_company = self.owner.get("/api/companies/" + second_id)
        self.assertEqual(kept_company.status_code, 200)
        self.assertEqual(kept_company.get_json()["data"]["name"], "Phase 10D1 Second " + self.marker)

        staff = client_for(STAFF)
        self.assertEqual(staff.get("/api/companies/" + company_id + "/drivers").status_code, 403)
        self.assertEqual(staff.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": driver_id,
        }).status_code, 403)

        client_email = "phase10d1-" + self.marker + "@example.com"
        client_created = self.owner.post("/api/clients", json={
            "full_name": "Phase 10D1 Client",
            "email": client_email,
        })
        self.assertEqual(client_created.status_code, 201, client_created.get_data(as_text=True))
        with patch.object(app_module, "accepted_staff", lambda: {"email": client_email, "role": "staff"}):
            client_denied = app_module.app.test_client().get("/api/companies/" + company_id + "/drivers")
        self.assertEqual(client_denied.status_code, 403)

        def driver_identity(email):
            return {"ok": True, "role": "driver", "id": owner_id, "status": "active"}

        with patch.object(app_module, "accepted_staff", lambda: {"email": "phase10d1-driver@example.com", "role": "staff"}), \
             patch.object(dev_postgres, "resolve_login_identity", driver_identity):
            driver_denied = app_module.app.test_client().delete(
                "/api/companies/" + company_id + "/drivers/" + driver_id
            )
        self.assertEqual(driver_denied.status_code, 403)

        anonymous = app_module.app.test_client()
        self.assertEqual(anonymous.get("/api/companies/" + company_id + "/drivers").status_code, 401)
        self.assertEqual(anonymous.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": driver_id,
        }).status_code, 401)

        self.assertEqual(self.owner.get("/api/companies").status_code, 200)
        self.assertEqual(self.owner.get("/api/drivers").status_code, 200)
        self.assertEqual(self.owner.get("/api/vehicles").status_code, 200)
        dashboard = self.owner.get("/api/v1/dashboard/summary")
        self.assertEqual(dashboard.status_code, 200)
        self.assertTrue(dashboard.get_json()["success"])
        self.assertEqual(company_vehicle_count(owner_id), 0)
        self.assertEqual(self.files["rac"], digest(BACKEND / "rac_data.json"))
        self.assertEqual(self.files["history"], digest(BACKEND / "data" / "rac_drivers.json"))
        self.assertEqual(self.sqlite, sqlite_counts())


if __name__ == "__main__":
    unittest.main()
