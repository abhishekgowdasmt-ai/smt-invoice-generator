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
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(BACKEND))

import backend.app as app_module
import dev_postgres
import staff_auth

OWNER = "abhishekgowdasmt@gmail.com"
STAFF = "bhaskarbhaskarreddy9005@gmail.com"


def client_for(email):
    client = app_module.app.test_client()
    token = staff_auth.issue_token(email)
    if token:
        client.set_cookie("smt_staff", token)
    return client


class ClientManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if dev_postgres.local_development_dsn() is None:
            raise unittest.SkipTest("local database is not configured")
        cls.owner = client_for(OWNER)
        cls.marker = uuid.uuid4().hex[:8]
        cls.email = "phase9b-" + cls.marker + "@example.com"
        first = cls.owner.post("/api/companies", json={
            "name": "Phase 9B " + cls.marker + " A",
            "branch_codes": ["BLR"],
        })
        second = cls.owner.post("/api/companies", json={
            "name": "Phase 9B " + cls.marker + " B",
            "branch_codes": ["HYD"],
        })
        cls.company_a = first.get_json()["data"]["id"]
        cls.company_b = second.get_json()["data"]["id"]
        cls.company_status = (first.status_code, second.status_code)

    def test_client_lifecycle_and_access(self):
        self.assertEqual(self.company_status, (201, 201))
        created = self.owner.post("/api/clients", json={
            "full_name": "Phase 9B Client",
            "email": "Phase9B-" + self.marker + "@Example.com",
            "phone": "0801111111",
            "role": "client",
            "password": "should-not-be-stored",
            "google_sub": "should-not-be-stored",
        })
        self.assertEqual(created.status_code, 201)
        client = created.get_json()["data"]
        self.assertEqual(client["role"], "client")
        self.assertEqual(client["status"], "active")
        self.assertEqual(client["email"], self.email)
        self.assertNotIn("password", client)
        self.assertNotIn("password_hash", client)
        self.assertNotIn("google_sub", client)

        duplicate = self.owner.post("/api/clients", json={
            "full_name": "Again",
            "email": self.email,
        })
        self.assertEqual(duplicate.status_code, 409)
        rejected_role = self.owner.post("/api/clients", json={
            "full_name": "Not an owner",
            "email": "phase9b-role-" + self.marker + "@example.com",
            "role": "owner",
        })
        self.assertEqual(rejected_role.status_code, 400)
        invalid = self.owner.post("/api/clients", json={
            "full_name": "Bad email",
            "email": "not-an-email",
        })
        self.assertEqual(invalid.status_code, 400)

        linked = self.owner.post(
            "/api/companies/" + self.company_a + "/clients",
            json={"user_id": client["id"]},
        )
        self.assertEqual(linked.status_code, 200)
        again = self.owner.post(
            "/api/companies/" + self.company_a + "/clients",
            json={"email": self.email},
        )
        self.assertEqual(again.status_code, 409)
        listed = self.owner.get("/api/companies/" + self.company_a + "/clients")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["id"] for row in listed.get_json()["data"]], [client["id"]])

        other = self.owner.post(
            "/api/companies/" + self.company_b + "/clients",
            json={"email": self.email},
        )
        self.assertEqual(other.status_code, 200)
        removed = self.owner.delete(
            "/api/companies/" + self.company_b + "/clients/" + client["id"]
        )
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.get_json()["data"]["id"], client["id"])
        self.assertEqual(removed.get_json()["data"]["role"], "client")
        remaining = self.owner.get("/api/companies/" + self.company_b + "/clients")
        self.assertEqual(remaining.get_json()["data"], [])
        still_there = self.owner.post("/api/clients", json={
            "full_name": "Phase 9B Client",
            "email": self.email,
        })
        self.assertEqual(still_there.status_code, 409)

        seen = {}

        def read_companies(cur):
            cur.execute("SELECT id::text FROM companies")
            seen["ids"] = [row[0] for row in cur.fetchall()]

        read = dev_postgres.authorized_transaction(client["id"], read_companies)
        self.assertEqual(read["role"], "client")
        self.assertIn(self.company_a, seen["ids"])
        self.assertNotIn(self.company_b, seen["ids"])

        def try_create(cur):
            cur.execute(
                """
                INSERT INTO users (role, full_name, email, status)
                VALUES ('client', 'Blocked', %s, 'active')
                """,
                ("phase9b-blocked-" + self.marker + "@example.com",),
            )

        self.assertIsNone(dev_postgres.authorized_transaction(client["id"], try_create))
        self.assertEqual(
            dev_postgres.resolve_login_identity("phase9b-blocked-" + self.marker + "@example.com")["reason"],
            "not_found",
        )

        staff = client_for(STAFF)
        self.assertEqual(staff.post("/api/clients", json={
            "full_name": "Staff attempt",
            "email": "phase9b-staff-" + self.marker + "@example.com",
        }).status_code, 403)
        self.assertEqual(staff.post(
            "/api/companies/" + self.company_a + "/clients",
            json={"email": self.email},
        ).status_code, 403)
        anonymous = app_module.app.test_client()
        self.assertEqual(anonymous.post("/api/clients", json={
            "full_name": "Anon",
            "email": "phase9b-anon-" + self.marker + "@example.com",
        }).status_code, 401)
        self.assertEqual(anonymous.get("/api/companies/" + self.company_a + "/clients").status_code, 401)

        companies = self.owner.get("/api/companies")
        self.assertEqual(companies.status_code, 200)
        self.assertTrue(any(row["id"] == self.company_a for row in companies.get_json()["data"]))
        detail = self.owner.get("/api/companies/" + self.company_a)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["data"]["branches"][0]["code"], "BLR")
        dashboard = self.owner.get("/api/v1/dashboard/summary")
        self.assertEqual(dashboard.status_code, 200)
        self.assertTrue(dashboard.get_json()["success"])
        self.assertNotIn("psycopg", created.get_data(as_text=True).lower())


if __name__ == "__main__":
    unittest.main()
