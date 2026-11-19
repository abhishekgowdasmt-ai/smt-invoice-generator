"""Revision 8 document, filter, history, and duplicate-warning tests.

These tests commit rows on a disposable local database whose name ends with
_test. They refuse smt_dev. SQLite and RAC files are only hashed.
"""
import hashlib
import os
import sqlite3
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
import staff_auth

OWNER = "abhishekgowdasmt@gmail.com"
STAFF = "bhaskarbhaskarreddy9005@gmail.com"
_LOCAL_SERVER_ADDRESSES = (None, "127.0.0.1", "127.0.0.1/32", "::1", "::1/128")


def client_for(email):
    client = app_module.app.test_client()
    token = staff_auth.issue_token(email)
    if token:
        client.set_cookie("smt_staff", token)
    return client


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
            name: cursor.execute("SELECT count(*) FROM " + name).fetchone()[0]
            for name in ("drivers", "cabs", "company_cabs", "cab_documents", "companies")
        }
    finally:
        connection.close()


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


class Revision8ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        cls.owner = client_for(OWNER)
        cls.staff = client_for(STAFF)
        cls.marker = uuid.uuid4().hex[:8]
        cls.owner_id = dev_postgres.resolve_login_identity(OWNER)["id"]
        cls.staff_id = dev_postgres.resolve_login_identity(STAFF)["id"]
        cls.files = {
            "rac": digest(BACKEND / "rac_data.json"),
            "history": digest(BACKEND / "data" / "rac_drivers.json"),
        }
        cls.sqlite = sqlite_counts()

    def _driver(self, label, phone=None, licence=None, branch="BLR"):
        payload = {
            "display_name": "Revision 8 " + label + " " + self.marker,
            "primary_branch_code": branch,
        }
        if phone is not None:
            payload["phone"] = phone
        if licence is not None:
            payload["license_number"] = licence
        created = self.owner.post("/api/drivers", json=payload)
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        return created.get_json()["data"]

    def test_document_crud_and_validation(self):
        driver = self._driver("documents", "9000011122", "DL-DOC-" + self.marker)
        self.assertEqual(driver["documents"], [])
        self.assertEqual(driver["verification_status"], "unverified")
        self.assertFalse(driver["active"])

        missing = self.owner.post("/api/drivers/" + driver["id"] + "/documents", json={
            "doc_number": "NO-TYPE",
        })
        self.assertEqual(missing.status_code, 400)
        self.assertIn("type", missing.get_json()["message"].lower())

        blank = self.owner.post("/api/drivers/" + driver["id"] + "/documents", json={
            "doc_type": "   ",
            "doc_number": "KA-1",
        })
        self.assertEqual(blank.status_code, 400)

        bad_date = self.owner.post("/api/drivers/" + driver["id"] + "/documents", json={
            "doc_type": "Licence",
            "doc_number": "KA-1",
            "expiry_date": "19-11-2026",
        })
        self.assertEqual(bad_date.status_code, 400)
        self.assertIn("YYYY-MM-DD", bad_date.get_json()["message"])

        stored_file = self.owner.post("/api/drivers/" + driver["id"] + "/documents", json={
            "doc_type": "Licence",
            "doc_number": "KA-1",
            "file_path": "C:/not-a-file.pdf",
        })
        self.assertEqual(stored_file.status_code, 400)

        created = self.owner.post("/api/drivers/" + driver["id"] + "/documents", json={
            "doc_type": "Licence",
            "doc_number": "KA-" + self.marker,
            "expiry_date": "2030-01-15",
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        saved = created.get_json()["data"]
        self.assertEqual(len(saved["documents"]), 1)
        document = saved["documents"][0]
        self.assertEqual(document["doc_type"], "Licence")
        self.assertEqual(document["doc_number"], "KA-" + self.marker)
        self.assertEqual(document["expiry_date"], "2030-01-15")
        self.assertNotIn("file_path", document)

        listed = self.owner.get("/api/drivers/" + driver["id"] + "/documents")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"][0]["id"], document["id"])

        edited = self.owner.patch(
            "/api/drivers/" + driver["id"] + "/documents/" + document["id"],
            json={"doc_number": "KA-" + self.marker + "-B", "expiry_date": ""},
        )
        self.assertEqual(edited.status_code, 200, edited.get_data(as_text=True))
        edited_document = edited.get_json()["data"]["documents"][0]
        self.assertEqual(edited_document["doc_number"], "KA-" + self.marker + "-B")
        self.assertIsNone(edited_document["expiry_date"])

        missing_document = self.owner.patch(
            "/api/drivers/" + driver["id"] + "/documents/" + str(uuid.uuid4()),
            json={"doc_type": "Badge"},
        )
        self.assertEqual(missing_document.status_code, 404)

        removed = self.owner.delete(
            "/api/drivers/" + driver["id"] + "/documents/" + document["id"]
        )
        self.assertEqual(removed.status_code, 200, removed.get_data(as_text=True))
        self.assertEqual(removed.get_json()["data"]["documents"], [])
        self.assertEqual(removed.get_json()["data"]["id"], driver["id"])

        unknown_driver = self.owner.post(
            "/api/drivers/" + str(uuid.uuid4()) + "/documents",
            json={"doc_type": "Licence", "doc_number": "NONE"},
        )
        self.assertEqual(unknown_driver.status_code, 404)

    def test_unauthorized_access_and_branch_restriction(self):
        driver = self._driver("branch", "9000011133", "DL-BR-" + self.marker)
        created = self.owner.post("/api/drivers/" + driver["id"] + "/documents", json={
            "doc_type": "Badge",
            "doc_number": "BR-" + self.marker,
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        document_id = created.get_json()["data"]["documents"][0]["id"]

        staff_write = self.staff.post("/api/drivers/" + driver["id"] + "/documents", json={
            "doc_type": "Badge",
            "doc_number": "STAFF",
        })
        self.assertEqual(staff_write.status_code, 403)
        staff_read = self.staff.get("/api/drivers/" + driver["id"] + "/documents")
        self.assertEqual(staff_read.status_code, 403)
        staff_warnings = self.staff.get("/api/driver-duplicate-warnings")
        self.assertEqual(staff_warnings.status_code, 403)
        anonymous = app_module.app.test_client()
        self.assertEqual(
            anonymous.get("/api/drivers/" + driver["id"] + "/documents").status_code,
            401,
        )

        import psycopg
        with psycopg.connect(dev_postgres.local_development_dsn(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database()")
                self.assertEqual(cur.fetchone()[0], self.database_name)
                cur.execute("SELECT set_config('app.user_id', %s, true)", (self.staff_id,))
                cur.execute("SET LOCAL ROLE smt_staff")
                cur.execute(
                    "SELECT count(*) FROM driver_documents WHERE id = %s::uuid",
                    (document_id,),
                )
                self.assertEqual(cur.fetchone()[0], 0)
                cur.execute("SELECT count(*) FROM drivers WHERE id = %s::uuid", (driver["id"],))
                self.assertEqual(cur.fetchone()[0], 0)
            conn.rollback()

        still_there = self.owner.get("/api/drivers/" + driver["id"] + "/documents")
        self.assertEqual(still_there.status_code, 200)
        self.assertEqual(still_there.get_json()["data"][0]["id"], document_id)

    def test_verification_filter_and_history(self):
        pending = self._driver("pending", "9000011144", "DL-PEN-" + self.marker)
        approved = self._driver("approved", "9000011155", "DL-APP-" + self.marker)
        rejected = self._driver("rejected", "9000011166", "DL-REJ-" + self.marker)
        review = self.owner.post("/api/drivers/" + approved["id"] + "/reviews", json={
            "decision": "verified",
            "reason": "Checked for the filter.",
        })
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))
        reject = self.owner.post("/api/drivers/" + rejected["id"] + "/reviews", json={
            "decision": "rejected",
            "reason": "Rejected for the filter.",
        })
        self.assertEqual(reject.status_code, 200, reject.get_data(as_text=True))

        invalid = self.owner.get("/api/drivers", query_string={
            "name": self.marker,
            "verification_status": "pending",
        })
        self.assertEqual(invalid.status_code, 400)

        unverified = self.owner.get("/api/drivers", query_string={
            "name": "pending " + self.marker,
            "verification_status": "unverified",
        })
        self.assertEqual(unverified.status_code, 200)
        unverified_ids = [row["id"] for row in unverified.get_json()["data"]]
        self.assertIn(pending["id"], unverified_ids)
        self.assertNotIn(approved["id"], unverified_ids)
        self.assertNotIn(rejected["id"], unverified_ids)

        verified_rows = self.owner.get("/api/drivers", query_string={
            "name": self.marker,
            "verification_status": "verified",
        })
        verified_ids = [row["id"] for row in verified_rows.get_json()["data"]]
        self.assertIn(approved["id"], verified_ids)
        self.assertNotIn(pending["id"], verified_ids)
        self.assertNotIn(rejected["id"], verified_ids)

        rejected_rows = self.owner.get("/api/drivers", query_string={
            "name": self.marker,
            "verification_status": "rejected",
        })
        rejected_ids = [row["id"] for row in rejected_rows.get_json()["data"]]
        self.assertEqual(rejected_ids.count(rejected["id"]), 1)
        self.assertNotIn(pending["id"], rejected_ids)

        detail = self.owner.get("/api/drivers/" + approved["id"])
        self.assertEqual(detail.status_code, 200)
        event = detail.get_json()["data"]["verification_events"][-1]
        self.assertEqual(event["event_name"], "verified")
        self.assertEqual(event["from_status"], "unverified")
        self.assertEqual(event["to_status"], "verified")
        self.assertEqual(event["reason"], "Checked for the filter.")
        self.assertEqual(event["actor_user_id"], self.owner_id)
        self.assertTrue(event["actor_name"])
        self.assertEqual(event["actor_email"], OWNER)
        self.assertTrue(event["created_at"])

        suspended = self.owner.post("/api/drivers/" + approved["id"] + "/active", json={
            "active": False,
            "reason": "Suspended for the history check.",
        })
        self.assertEqual(suspended.status_code, 200, suspended.get_data(as_text=True))
        change = suspended.get_json()["data"]["active_changes"][-1]
        self.assertTrue(change["active_before"])
        self.assertFalse(change["active_after"])
        self.assertEqual(change["reason"], "Suspended for the history check.")
        self.assertEqual(change["actor_user_id"], self.owner_id)
        self.assertEqual(change["actor_email"], OWNER)
        self.assertTrue(change["actor_name"])
        self.assertTrue(change["created_at"])
        self.assertEqual(suspended.get_json()["data"]["verification_status"], "verified")

    def test_duplicate_phone_and_licence_warnings(self):
        suffix = f"{int(self.marker, 16) % 1000000:06d}"
        phone = "9988" + suffix
        licence = "DL-DUP-" + self.marker
        first = self._driver("first duplicate", phone, licence)
        second = self._driver("second duplicate", phone, licence.lower())
        warnings = self.owner.get("/api/driver-duplicate-warnings")
        self.assertEqual(warnings.status_code, 200, warnings.get_data(as_text=True))
        pairs = [
            row for row in warnings.get_json()["data"]
            if {row["driver"]["id"], row["other_driver"]["id"]} == {first["id"], second["id"]}
        ]
        kinds = sorted(row["match_kind"] for row in pairs)
        self.assertEqual(kinds, ["licence", "phone"])
        names = {row["driver"]["display_name"] for row in pairs}
        names.update(row["other_driver"]["display_name"] for row in pairs)
        self.assertIn(first["display_name"], names)
        self.assertIn(second["display_name"], names)

        detail = self.owner.get("/api/drivers/" + first["id"])
        detail_warnings = detail.get_json()["data"]["duplicate_warnings"]
        other_ids = {row["other_driver"]["id"] for row in detail_warnings}
        self.assertEqual(other_ids, {second["id"]})
        self.assertIn("phone", [row["match_kind"] for row in detail_warnings])
        self.assertIn("licence", [row["match_kind"] for row in detail_warnings])
        self.assertTrue(any(row["other_driver"]["display_name"] == second["display_name"] for row in detail_warnings))
        self.assertTrue(any(row["other_driver"]["phone"] == phone for row in detail_warnings))

        changed = self.owner.patch("/api/drivers/" + second["id"], json={
            "phone": "9977" + suffix,
        })
        self.assertEqual(changed.status_code, 200, changed.get_data(as_text=True))
        remaining = [row["match_kind"] for row in changed.get_json()["data"]["duplicate_warnings"]]
        self.assertNotIn("phone", remaining)
        self.assertIn("licence", remaining)
        both = self.owner.get("/api/drivers", query_string={"name": "duplicate " + self.marker})
        self.assertEqual(len(both.get_json()["data"]), 2)

    def test_create_and_edit_keep_verification_locked(self):
        created = self._driver("edit", "9000011177", "DL-ED-" + self.marker)
        self.assertEqual(created["verification_status"], "unverified")
        self.assertFalse(created["active"])
        renamed = self.owner.patch("/api/drivers/" + created["id"], json={
            "display_name": created["display_name"] + " renamed",
        })
        self.assertEqual(renamed.status_code, 200, renamed.get_data(as_text=True))
        self.assertEqual(renamed.get_json()["data"]["verification_status"], "unverified")
        self.assertFalse(renamed.get_json()["data"]["active"])
        status_change = self.owner.patch("/api/drivers/" + created["id"], json={
            "verification_status": "verified",
        })
        self.assertEqual(status_change.status_code, 400)
        active_change = self.owner.patch("/api/drivers/" + created["id"], json={"active": True})
        self.assertEqual(active_change.status_code, 400)
        self.assertIn("Approve", active_change.get_json()["message"])

    def test_company_links_still_follow_active_state(self):
        company = self.owner.post("/api/companies", json={
            "name": "Revision 8 company " + self.marker,
            "branch_codes": ["BLR"],
        })
        self.assertEqual(company.status_code, 201, company.get_data(as_text=True))
        company_id = company.get_json()["data"]["id"]
        driver = self._driver("company", "9000011188", "DL-CO-" + self.marker)
        inactive = self.owner.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": driver["id"],
        })
        self.assertEqual(inactive.status_code, 400)
        self.assertIn("inactive", inactive.get_json()["message"].lower())

        approved = self.owner.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "verified",
            "reason": "Approved before the company link.",
        })
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        linked = self.owner.post("/api/companies/" + company_id + "/drivers", json={
            "driver_id": driver["id"],
        })
        self.assertEqual(linked.status_code, 201, linked.get_data(as_text=True))
        self.assertEqual(linked.get_json()["data"][0]["id"], driver["id"])
        self.assertTrue(linked.get_json()["data"][0]["active"])

        vehicle = self.owner.post("/api/vehicles", json={
            "registration_number": "KA-R8-" + self.marker,
            "model": "Ertiga",
            "branch_code": "BLR",
            "usual_driver_id": driver["id"],
        })
        self.assertEqual(vehicle.status_code, 201, vehicle.get_data(as_text=True))
        vehicle_id = vehicle.get_json()["data"]["id"]
        vehicle_link = self.owner.post("/api/companies/" + company_id + "/vehicles", json={
            "vehicle_id": vehicle_id,
        })
        self.assertEqual(vehicle_link.status_code, 201, vehicle_link.get_data(as_text=True))
        self.assertEqual(vehicle_link.get_json()["data"][0]["id"], vehicle_id)

        removed = self.owner.delete(
            "/api/companies/" + company_id + "/drivers/" + driver["id"]
        )
        self.assertEqual(removed.status_code, 200, removed.get_data(as_text=True))
        self.assertEqual(removed.get_json()["data"], [])

    def test_sqlite_and_rac_files_stay_unchanged(self):
        self.assertEqual(digest(BACKEND / "rac_data.json"), self.files["rac"])
        self.assertEqual(digest(BACKEND / "data" / "rac_drivers.json"), self.files["history"])
        self.assertEqual(sqlite_counts(), self.sqlite)


if __name__ == "__main__":
    unittest.main()
