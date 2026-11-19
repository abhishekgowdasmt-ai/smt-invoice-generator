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
SECOND_OWNER = "shreemaruthitravels5999@gmail.com"
STAFF = "bhaskarbhaskarreddy9005@gmail.com"


def client_for(email):
    client = app_module.app.test_client()
    client.set_cookie("smt_staff", staff_auth.issue_token(email))
    return client


class CompanyDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if dev_postgres.local_development_dsn() is None:
            raise unittest.SkipTest("local database is not configured")
        cls.owner = client_for(OWNER)
        cls.marker = "Phase 9A " + uuid.uuid4().hex[:8]
        created = cls.owner.post("/api/companies", json={
            "name": cls.marker,
            "contact_person": "Desk",
            "contact_email": "desk@example.com",
            "contact_phone": "0800000000",
            "address": "Bengaluru",
            "branch_codes": ["BLR"],
        })
        cls.created = created.get_json()
        cls.company_id = (cls.created.get("data") or {}).get("id")
        cls.create_status = created.status_code

    def test_owner_lifecycle(self):
        self.assertEqual(self.create_status, 201, self.created)
        self.assertEqual(self.created["data"]["branches"][0]["code"], "BLR")
        listed = self.owner.get("/api/companies")
        self.assertEqual(listed.status_code, 200)
        self.assertIn(self.marker, [row["name"] for row in listed.get_json()["data"]])

        edited = self.owner.patch("/api/companies/" + self.company_id, json={
            "name": self.marker + " edited",
            "contact_person": "Front desk",
            "contact_email": "",
            "contact_phone": "0800000001",
            "address": "Hyderabad road",
        })
        self.assertEqual(edited.status_code, 200)
        company = edited.get_json()["data"]
        self.assertEqual(company["name"], self.marker + " edited")
        self.assertIsNone(company["contact_email"])
        self.assertEqual(company["branches"][0]["code"], "BLR")

        other = client_for(SECOND_OWNER).get("/api/companies/" + self.company_id)
        self.assertEqual(other.status_code, 200)
        self.assertEqual(other.get_json()["data"]["name"], self.marker + " edited")

        added = self.owner.post(f"/api/companies/{self.company_id}/branches/HYD")
        self.assertEqual(added.status_code, 200)
        self.assertEqual(
            [branch["code"] for branch in added.get_json()["data"]["branches"]],
            ["BLR", "HYD"],
        )
        duplicate = self.owner.post(f"/api/companies/{self.company_id}/branches/hyd")
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already linked", duplicate.get_json()["message"])
        still = self.owner.get("/api/companies/" + self.company_id)
        self.assertEqual(
            [branch["code"] for branch in still.get_json()["data"]["branches"]],
            ["BLR", "HYD"],
        )

        removed = self.owner.delete(f"/api/companies/{self.company_id}/branches/HYD")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(
            [branch["code"] for branch in removed.get_json()["data"]["branches"]],
            ["BLR"],
        )
        missing = self.owner.delete(f"/api/companies/{self.company_id}/branches/HYD")
        self.assertEqual(missing.status_code, 404)

    def test_a_referenced_city_stays_and_the_probe_rolls_back(self):
        branches = {row["code"]: row["id"] for row in dev_postgres.list_branches()}
        owner = dev_postgres.resolve_login_identity(OWNER)
        box = {}

        def work(cur):
            cur.execute(
                "INSERT INTO companies (name) VALUES (%s) RETURNING id::text",
                (self.marker + " rollback",),
            )
            company_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO company_branches (company_id, branch_id) VALUES (%s::uuid, %s::uuid)",
                (company_id, branches["BLR"]),
            )
            cur.execute(
                """
                INSERT INTO bookings (branch_id, company_id, origin, status)
                VALUES (%s::uuid, %s::uuid, 'rac', 'unassigned')
                """,
                (branches["BLR"], company_id),
            )
            box["referenced"] = dev_postgres._branch_is_referenced(cur, company_id, branches["BLR"])
            raise RuntimeError("rollback probe")

        done = dev_postgres.authorized_transaction(owner["id"], work)
        self.assertIsNone(done)
        self.assertTrue(box["referenced"])
        names = [row["name"] for row in self.owner.get("/api/companies").get_json()["data"]]
        self.assertNotIn(self.marker + " rollback", names)
        original = dev_postgres._branch_is_referenced
        dev_postgres._branch_is_referenced = lambda cur, company_id, branch_id: True
        try:
            blocked = self.owner.delete(f"/api/companies/{self.company_id}/branches/BLR")
        finally:
            dev_postgres._branch_is_referenced = original
        self.assertEqual(blocked.status_code, 409)
        self.assertIn("still used", blocked.get_json()["message"])
        kept = self.owner.get("/api/companies/" + self.company_id)
        self.assertEqual(kept.get_json()["data"]["branches"][0]["code"], "BLR")

    def test_staff_cannot_create_or_edit(self):
        staff = client_for(STAFF)
        before = len(self.owner.get("/api/companies").get_json()["data"])
        created = staff.post("/api/companies", json={"name": "Staff company", "branch_codes": ["BLR"]})
        edited = staff.patch("/api/companies/" + self.company_id, json={"name": "Taken over"})
        linked = staff.post(f"/api/companies/{self.company_id}/branches/HYD")
        self.assertEqual(created.status_code, 403)
        self.assertEqual(edited.status_code, 403)
        self.assertEqual(linked.status_code, 403)
        after = len(self.owner.get("/api/companies").get_json()["data"])
        self.assertEqual(before, after)
        current = self.owner.get("/api/companies/" + self.company_id).get_json()["data"]
        self.assertNotEqual(current["name"], "Taken over")

    def test_anonymous_and_invalid_requests_are_rejected(self):
        anonymous = app_module.app.test_client()
        self.assertEqual(anonymous.get("/api/companies").status_code, 401)
        self.assertEqual(anonymous.post("/api/companies", json={"name": "Nope", "branch_codes": ["BLR"]}).status_code, 401)
        missing = self.owner.post("/api/companies", json={"name": "   ", "branch_codes": ["BLR"]})
        self.assertEqual(missing.status_code, 400)
        unknown = self.owner.post("/api/companies", json={"name": "Elsewhere", "branch_codes": ["DEL"]})
        self.assertEqual(unknown.status_code, 400)
        self.assertNotIn("psycopg", missing.get_data(as_text=True).lower())

    def test_company_remains_after_a_new_connection(self):
        again = dev_postgres.get_company(
            dev_postgres.resolve_login_identity(OWNER)["id"],
            self.company_id,
        )
        self.assertTrue(again["ok"])
        self.assertTrue(again["company"]["name"].startswith("Phase 9A "))

    def test_rac_dashboard_still_opens_for_the_owner(self):
        response = self.owner.get("/api/v1/dashboard/summary")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
