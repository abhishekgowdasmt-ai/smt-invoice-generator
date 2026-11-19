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


class VehicleDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if dev_postgres.local_development_dsn() is None:
            raise unittest.SkipTest("local database is not configured")
        cls.owner = client_for(OWNER)
        cls.marker = uuid.uuid4().hex[:8]
        cls.plate = ("KA-10C-" + cls.marker).upper()
        cls.files = {
            "rac": digest(BACKEND / "rac_data.json"),
            "history": digest(BACKEND / "data" / "rac_drivers.json"),
        }
        cls.sqlite = sqlite_counts()

    def test_owner_directory_and_boundaries(self):
        listed = self.owner.get("/api/vehicles")
        self.assertEqual(listed.status_code, 200, listed.get_data(as_text=True))
        before = len(listed.get_json()["data"])

        drivers = self.owner.get("/api/drivers")
        self.assertEqual(drivers.status_code, 200)
        driver = self.owner.post("/api/drivers", json={
            "display_name": "Phase 10C driver " + self.marker,
            "primary_branch_code": "BLR",
        })
        self.assertEqual(driver.status_code, 201, driver.get_data(as_text=True))
        driver_id = driver.get_json()["data"]["id"]

        rejected = self.owner.post("/api/vehicles", json={
            "registration_number": self.plate,
            "branch_code": "BLR",
            "identity_status": "conflict",
            "file_path": "C:/not-uploaded.pdf",
        })
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("cannot be set", rejected.get_json()["message"])

        created = self.owner.post("/api/vehicles", json={
            "registration_number": self.plate.lower(),
            "model": "Toyota Innova",
            "capacity": 7,
            "fuel_type": "Diesel",
            "is_ev": False,
            "branch_code": "blr",
            "usual_driver_id": driver_id,
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        vehicle = created.get_json()["data"]
        self.assertEqual(vehicle["registration_number"], self.plate)
        self.assertEqual(vehicle["model"], "Toyota Innova")
        self.assertEqual(vehicle["capacity"], 7)
        self.assertEqual(vehicle["status"], "active")
        self.assertEqual(vehicle["branch"]["code"], "BLR")
        self.assertEqual(vehicle["usual_driver"]["id"], driver_id)
        self.assertEqual(vehicle["documents"], [])
        self.assertNotIn("identity_status", vehicle)
        self.assertNotIn("file_path", vehicle)
        self.assertNotIn("legacy_id", vehicle)

        detail = self.owner.get("/api/vehicles/" + vehicle["id"])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["data"]["usual_driver"]["display_name"], "Phase 10C driver " + self.marker)

        duplicate = self.owner.post("/api/vehicles", json={
            "registration_number": self.plate,
            "branch_code": "HYD",
        })
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already", duplicate.get_json()["message"])

        spelling = self.owner.post("/api/vehicles", json={
            "registration_number": "KA10C" + self.marker,
            "branch_code": "HYD",
        })
        self.assertEqual(spelling.status_code, 201, spelling.get_data(as_text=True))
        self.assertNotEqual(spelling.get_json()["data"]["id"], vehicle["id"])

        invalid_branch = self.owner.post("/api/vehicles", json={
            "registration_number": "KA-10C-X" + self.marker,
            "branch_code": "DEL",
        })
        self.assertEqual(invalid_branch.status_code, 400)
        blank = self.owner.post("/api/vehicles", json={
            "registration_number": "   ",
            "branch_code": "BLR",
        })
        self.assertEqual(blank.status_code, 400)
        bad_status = self.owner.post("/api/vehicles", json={
            "registration_number": "KA-10C-Y" + self.marker,
            "branch_code": "BLR",
            "status": "maintenance",
        })
        self.assertEqual(bad_status.status_code, 400)
        missing_driver = self.owner.post("/api/vehicles", json={
            "registration_number": "KA-10C-Z" + self.marker,
            "branch_code": "BLR",
            "usual_driver_id": str(uuid.uuid4()),
        })
        self.assertEqual(missing_driver.status_code, 400)

        edited = self.owner.patch("/api/vehicles/" + vehicle["id"], json={
            "model": "Innova Crysta",
            "capacity": 6,
            "fuel_type": "Diesel",
            "is_ev": False,
            "branch_code": "HYD",
        })
        self.assertEqual(edited.status_code, 200, edited.get_data(as_text=True))
        edited_vehicle = edited.get_json()["data"]
        self.assertEqual(edited_vehicle["model"], "Innova Crysta")
        self.assertEqual(edited_vehicle["capacity"], 6)
        self.assertEqual(edited_vehicle["branch"]["code"], "HYD")
        self.assertEqual(edited_vehicle["usual_driver"]["id"], driver_id)

        cleared = self.owner.patch("/api/vehicles/" + vehicle["id"], json={"usual_driver_id": None})
        self.assertEqual(cleared.status_code, 200, cleared.get_data(as_text=True))
        self.assertIsNone(cleared.get_json()["data"]["usual_driver"])
        restored = self.owner.patch("/api/vehicles/" + vehicle["id"], json={"usual_driver_id": driver_id})
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.get_json()["data"]["usual_driver"]["id"], driver_id)

        inactive = self.owner.patch("/api/vehicles/" + vehicle["id"], json={"status": "inactive"})
        self.assertEqual(inactive.status_code, 200)
        self.assertEqual(inactive.get_json()["data"]["status"], "inactive")
        self.assertEqual(inactive.get_json()["data"]["branch"]["code"], "HYD")
        hidden = self.owner.get("/api/vehicles", query_string={"registration": self.plate, "status": "active"})
        self.assertNotIn(vehicle["id"], [row["id"] for row in hidden.get_json()["data"]])
        shown = self.owner.get("/api/vehicles", query_string={
            "registration": self.plate,
            "status": "inactive",
            "branch": "HYD",
        })
        self.assertIn(vehicle["id"], [row["id"] for row in shown.get_json()["data"]])
        active = self.owner.patch("/api/vehicles/" + vehicle["id"], json={"status": "active"})
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.get_json()["data"]["status"], "active")

        blocked_file = self.owner.post("/api/vehicles/" + vehicle["id"] + "/documents", json={
            "doc_type": "Insurance",
            "doc_number": "INS-" + self.marker,
            "file_path": "C:/not-uploaded.pdf",
        })
        self.assertEqual(blocked_file.status_code, 400)
        documented = self.owner.post("/api/vehicles/" + vehicle["id"] + "/documents", json={
            "doc_type": "Insurance",
            "doc_number": "INS-" + self.marker,
            "expiry_date": "2034-01-15",
        })
        self.assertEqual(documented.status_code, 201, documented.get_data(as_text=True))
        documents = documented.get_json()["data"]["documents"]
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["doc_type"], "Insurance")
        self.assertEqual(documents[0]["expiry_date"], "2034-01-15")
        self.assertNotIn("file_path", documents[0])
        changed_doc = self.owner.patch(
            "/api/vehicles/" + vehicle["id"] + "/documents/" + documents[0]["id"],
            json={"expiry_date": "2035-02-20"},
        )
        self.assertEqual(changed_doc.status_code, 200, changed_doc.get_data(as_text=True))
        self.assertEqual(changed_doc.get_json()["data"]["documents"][0]["expiry_date"], "2035-02-20")
        removed = self.owner.delete("/api/vehicles/" + vehicle["id"] + "/documents/" + documents[0]["id"])
        self.assertEqual(removed.status_code, 200, removed.get_data(as_text=True))
        self.assertEqual(removed.get_json()["data"]["documents"], [])

        staff = client_for(STAFF)
        self.assertEqual(staff.get("/api/vehicles").status_code, 403)
        self.assertEqual(staff.post("/api/vehicles", json={
            "registration_number": "KA-10C-S" + self.marker,
            "branch_code": "BLR",
        }).status_code, 403)
        self.assertEqual(len(self.owner.get("/api/vehicles").get_json()["data"]), before + 2)

        client_email = "phase10c-" + self.marker + "@example.com"
        client_created = self.owner.post("/api/clients", json={
            "full_name": "Phase 10C Client",
            "email": client_email,
        })
        self.assertEqual(client_created.status_code, 201, client_created.get_data(as_text=True))
        with patch.object(app_module, "accepted_staff", lambda: {"email": client_email, "role": "staff"}):
            client_denied = app_module.app.test_client().get("/api/vehicles")
        self.assertEqual(client_denied.status_code, 403)

        owner_id = dev_postgres.resolve_login_identity(OWNER)["id"]

        def driver_identity(email):
            return {"ok": True, "role": "driver", "id": owner_id, "status": "active"}

        with patch.object(app_module, "accepted_staff", lambda: {"email": "phase10c-driver@example.com", "role": "staff"}), \
             patch.object(dev_postgres, "resolve_login_identity", driver_identity):
            driver_denied = app_module.app.test_client().get("/api/vehicles")
        self.assertEqual(driver_denied.status_code, 403)

        anonymous = app_module.app.test_client()
        self.assertEqual(anonymous.get("/api/vehicles").status_code, 401)
        self.assertEqual(anonymous.post("/api/vehicles", json={
            "registration_number": "KA-10C-A" + self.marker,
            "branch_code": "BLR",
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
