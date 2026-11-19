"""Revision 8 driver verification tests.

The workflow test commits driver, verification, and suspension rows. Those rows
stay: history is append-only, and a driver cannot be deleted after its
submission event. Run this file only against a disposable local database or a
restored test copy.

Set SMT_REVISION8_DISPOSABLE=yes and point SMT_DEV_DATABASE_URL at that copy.
The database name must end with _test. smt_dev, postgres, and any non-local
server are refused. The one-use guard test also needs SMT_REVISION8_ADMIN_URL,
a local superuser connection to the same database. Nothing here is for production.
"""
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "backend"
REPO_ROOT = APP_ROOT.parents[1]
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
ROLLBACK_FILE = REPO_ROOT / "dev-db" / "003_revision8_driver_verification_rollback.sql"
REFUSAL_CHECK = """
DO $refusal$
DECLARE
    event_rows bigint;
    document_rows bigint;
    active_rows bigint;
BEGIN
    SELECT count(*) INTO event_rows FROM public.driver_verification_events;
    SELECT count(*) INTO document_rows FROM public.driver_documents;
    SELECT count(*) INTO active_rows FROM public.driver_active_changes;
    IF event_rows > 0 OR document_rows > 0 OR active_rows > 0 THEN
        RAISE EXCEPTION
            'Refusing rollback: % verification events, % document rows, and % active-change rows exist. Leave the history in place and correct it forward.',
            event_rows, document_rows, active_rows;
    END IF;
END $refusal$;
"""


def client_for(email):
    client = app_module.app.test_client()
    token = staff_auth.issue_token(email)
    if token:
        client.set_cookie("smt_staff", token)
    return client


_LOCAL_SERVER_ADDRESSES = (None, "127.0.0.1", "127.0.0.1/32", "::1", "::1/128")


def require_disposable_local_database():
    flag = (os.environ.get("SMT_REVISION8_DISPOSABLE") or "").strip().lower()
    if flag not in ("1", "yes", "true"):
        raise unittest.SkipTest(
            "Set SMT_REVISION8_DISPOSABLE=yes only for a disposable local database or a restored test copy"
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


class DriverVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        cls.owner = client_for(OWNER)
        cls.marker = uuid.uuid4().hex[:8]
        cls.name = "Revision 8 " + cls.marker
        cls.owner_id = dev_postgres.resolve_login_identity(OWNER)["id"]

    def test_verification_suspension_and_denials(self):
        created = self.owner.post("/api/drivers", json={
            "display_name": self.name,
            "phone": "0805555555",
            "license_number": "DL-R8-" + self.marker,
            "primary_branch_code": "BLR",
            "active": True,
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        driver = created.get_json()["data"]
        self.assertFalse(driver["active"])
        self.assertEqual(driver["verification_status"], "unverified")
        submitted = driver["verification_events"]
        self.assertEqual(len(submitted), 1)
        self.assertEqual(submitted[0]["event_name"], "submitted")
        self.assertEqual(submitted[0]["reason"], "Driver record created.")
        self.assertEqual(submitted[0]["actor_user_id"], self.owner_id)
        self.assertEqual(driver["active_changes"], [])

        activated = self.owner.patch("/api/drivers/" + driver["id"], json={"active": True})
        self.assertEqual(activated.status_code, 400)
        self.assertIn("Approve", activated.get_json()["message"])
        self.assertNotIn("not available", activated.get_json()["message"].lower())

        missing_reason = self.owner.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "verified",
            "reason": "   ",
        })
        self.assertEqual(missing_reason.status_code, 400)

        approved = self.owner.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "verified",
            "reason": "Licence and phone checked.",
        })
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        approved_driver = approved.get_json()["data"]
        self.assertEqual(approved_driver["verification_status"], "verified")
        self.assertTrue(approved_driver["active"])
        self.assertEqual(approved_driver["active_changes"], [])
        self.assertEqual(
            [event["event_name"] for event in approved_driver["verification_events"]],
            ["submitted", "verified"],
        )

        again = self.owner.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "verified",
            "reason": "Second approval.",
        })
        self.assertEqual(again.status_code, 400)

        suspended = self.owner.post("/api/drivers/" + driver["id"] + "/active", json={
            "active": False,
            "reason": "Suspended after a duty complaint.",
        })
        self.assertEqual(suspended.status_code, 200, suspended.get_data(as_text=True))
        suspended_driver = suspended.get_json()["data"]
        self.assertEqual(suspended_driver["verification_status"], "verified")
        self.assertFalse(suspended_driver["active"])
        self.assertEqual(len(suspended_driver["active_changes"]), 1)
        change = suspended_driver["active_changes"][0]
        self.assertEqual(change["actor_user_id"], self.owner_id)
        self.assertTrue(change["active_before"])
        self.assertFalse(change["active_after"])
        self.assertEqual(change["verification_status"], "verified")

        unchanged = self.owner.post("/api/drivers/" + driver["id"] + "/active", json={
            "active": False,
            "reason": "Already suspended.",
        })
        self.assertEqual(unchanged.status_code, 200, unchanged.get_data(as_text=True))
        self.assertEqual(len(unchanged.get_json()["data"]["active_changes"]), 1)

        restored = self.owner.post("/api/drivers/" + driver["id"] + "/active", json={
            "active": True,
            "reason": "Complaint closed.",
        })
        self.assertEqual(restored.status_code, 200, restored.get_data(as_text=True))
        restored_driver = restored.get_json()["data"]
        self.assertTrue(restored_driver["active"])
        self.assertEqual(restored_driver["verification_status"], "verified")
        self.assertEqual(len(restored_driver["active_changes"]), 2)
        self.assertFalse(restored_driver["active_changes"][1]["active_before"])
        self.assertTrue(restored_driver["active_changes"][1]["active_after"])

        rejected = self.owner.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "rejected",
            "reason": "Licence number does not match.",
        })
        self.assertEqual(rejected.status_code, 200, rejected.get_data(as_text=True))
        rejected_driver = rejected.get_json()["data"]
        self.assertEqual(rejected_driver["verification_status"], "rejected")
        self.assertFalse(rejected_driver["active"])
        self.assertEqual(len(rejected_driver["active_changes"]), 2)
        self.assertIn("rejected", [event["event_name"] for event in rejected_driver["verification_events"]])

        skipped = self.owner.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "verified",
            "reason": "Approve without resubmission.",
        })
        self.assertEqual(skipped.status_code, 400)
        self.assertIn("Resubmit", skipped.get_json()["message"])
        still_rejected = self.owner.get("/api/drivers/" + driver["id"])
        self.assertEqual(still_rejected.get_json()["data"]["verification_status"], "rejected")

        resubmitted = self.owner.post("/api/drivers/" + driver["id"] + "/resubmissions", json={
            "reason": "Corrected licence received.",
        })
        self.assertEqual(resubmitted.status_code, 200, resubmitted.get_data(as_text=True))
        resubmitted_driver = resubmitted.get_json()["data"]
        self.assertEqual(resubmitted_driver["verification_status"], "unverified")
        self.assertFalse(resubmitted_driver["active"])
        names = [event["event_name"] for event in resubmitted_driver["verification_events"]]
        self.assertEqual(names.count("rejected"), 1)
        self.assertIn("resubmitted", names)

        approved_again = self.owner.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "verified",
            "reason": "Corrected licence checked.",
        })
        self.assertEqual(approved_again.status_code, 200, approved_again.get_data(as_text=True))
        final_driver = approved_again.get_json()["data"]
        self.assertEqual(final_driver["verification_status"], "verified")
        self.assertTrue(final_driver["active"])
        self.assertEqual(len(final_driver["active_changes"]), 2)

        staff_id = dev_postgres.resolve_login_identity(STAFF)["id"]
        branch_id = dev_postgres.list_branches()[0]["id"]
        probe = self.name + " staff insert"

        def staff_insert(cur):
            cur.execute(
                """
                INSERT INTO drivers (id, primary_branch_id, display_name, active)
                VALUES (%s::uuid, %s::uuid, %s, true)
                """,
                (str(uuid.uuid4()), branch_id, probe),
            )

        self.assertIsNone(dev_postgres.authorized_transaction(staff_id, staff_insert))
        missing = self.owner.get("/api/drivers", query_string={"name": probe})
        self.assertEqual(missing.get_json()["data"], [])

        staff = client_for(STAFF)
        self.assertEqual(staff.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "rejected",
            "reason": "Staff review.",
        }).status_code, 403)
        self.assertEqual(staff.post("/api/drivers/" + driver["id"] + "/active", json={
            "active": False,
            "reason": "Staff suspension.",
        }).status_code, 403)

        anonymous = app_module.app.test_client()
        self.assertEqual(anonymous.post("/api/drivers/" + driver["id"] + "/reviews", json={
            "decision": "rejected",
            "reason": "Anonymous review.",
        }).status_code, 401)

        client_email = "revision8-" + self.marker + "@example.com"
        client_created = self.owner.post("/api/clients", json={
            "full_name": "Revision 8 Client",
            "email": client_email,
        })
        self.assertEqual(client_created.status_code, 201)
        with patch.object(app_module, "accepted_staff", lambda: {"email": client_email, "role": "staff"}):
            client_denied = app_module.app.test_client().post(
                "/api/drivers/" + driver["id"] + "/reviews",
                json={"decision": "rejected", "reason": "Client review."},
            )
        self.assertEqual(client_denied.status_code, 403)

    def test_rollback_script_does_not_broaden_driver_update(self):
        text = ROLLBACK_FILE.read_text(encoding="utf-8")
        self.assertNotIn("GRANT UPDATE ON drivers TO", text)
        self.assertIn("active, notes", text)
        self.assertIn("Refusing rollback", text)

    def test_ordinary_roles_cannot_write_history(self):
        import psycopg
        history_tables = ("driver_verification_events", "driver_active_changes")
        roles = ("smt_owner", "smt_staff", "smt_driver", "smt_client")
        with psycopg.connect(dev_postgres.local_development_dsn(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database()")
                self.assertEqual(cur.fetchone()[0], self.database_name)
                for role in roles + ("smt_migrate",):
                    for table in history_tables:
                        for privilege in ("INSERT", "UPDATE", "DELETE"):
                            cur.execute(
                                "SELECT has_table_privilege(%s, %s, %s)",
                                (role, table, privilege),
                            )
                            self.assertFalse(cur.fetchone()[0], role + " " + privilege + " " + table)
                for role in roles:
                    cur.execute("SAVEPOINT role_denial")
                    cur.execute("SET LOCAL ROLE " + role)
                    for table in history_tables:
                        denied = (
                            (f"INSERT INTO {table} (driver_id) VALUES (%s::uuid)", (str(uuid.uuid4()),)),
                            (f"UPDATE {table} SET driver_id = driver_id", ()),
                            (f"DELETE FROM {table}", ()),
                        )
                        for statement, params in denied:
                            cur.execute("SAVEPOINT statement_denial")
                            with self.assertRaises(psycopg.Error) as caught:
                                cur.execute(statement, params)
                            self.assertEqual(caught.exception.sqlstate, "42501")
                            cur.execute("ROLLBACK TO SAVEPOINT statement_denial")
                    cur.execute("ROLLBACK TO SAVEPOINT role_denial")
            conn.rollback()

    def test_rollback_refuses_when_history_exists_and_keeps_it(self):
        import psycopg
        probe = self.name + " rollback refusal"
        branch_id = dev_postgres.list_branches()[0]["id"]
        with psycopg.connect(dev_postgres.local_development_dsn(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('app.user_id', %s, true)", (self.owner_id,))
                cur.execute("SET LOCAL ROLE smt_owner")
                driver_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO drivers (id, primary_branch_id, display_name)
                    VALUES (%s::uuid, %s::uuid, %s)
                    """,
                    (driver_id, branch_id, probe),
                )
                cur.execute(
                    "INSERT INTO driver_branches (driver_id, branch_id) VALUES (%s::uuid, %s::uuid)",
                    (driver_id, branch_id),
                )
                with self.assertRaises(psycopg.Error) as caught:
                    cur.execute(REFUSAL_CHECK)
                self.assertIn("Refusing rollback", str(caught.exception))
            conn.rollback()
        with psycopg.connect(dev_postgres.local_development_dsn(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user")
                self.assertEqual(cur.fetchone()[0], "smt_app")
                for name in (
                    "driver_verification_events",
                    "driver_documents",
                    "driver_active_changes",
                ):
                    cur.execute("SELECT to_regclass(%s)", ("public." + name,))
                    self.assertIsNotNone(cur.fetchone()[0])
        missing = self.owner.get("/api/drivers", query_string={"name": probe})
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.get_json()["data"], [])

    def test_one_history_row_cannot_authorize_a_second_change(self):
        import psycopg
        admin = (os.environ.get("SMT_REVISION8_ADMIN_URL") or "").strip().strip('"')
        if not admin or ("127.0.0.1" not in admin and "localhost" not in admin):
            raise unittest.SkipTest("SMT_REVISION8_ADMIN_URL must be a local superuser URL for this test copy")
        branch_id = dev_postgres.list_branches()[0]["id"]
        driver_id = str(uuid.uuid4())
        with psycopg.connect(admin, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT current_database(),
                           inet_server_addr()::text,
                           (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
                    """
                )
                name, address, superuser = cur.fetchone()
                if name != self.database_name or address not in _LOCAL_SERVER_ADDRESSES or not superuser:
                    raise unittest.SkipTest("admin URL is not a local superuser on the disposable database")
                cur.execute("SELECT set_config('app.user_id', %s, true)", (self.owner_id,))
                cur.execute("SET LOCAL ROLE smt_owner")
                cur.execute(
                    """
                    INSERT INTO drivers (id, primary_branch_id, display_name)
                    VALUES (%s::uuid, %s::uuid, %s)
                    """,
                    (driver_id, branch_id, self.name + " one use"),
                )
                cur.execute(
                    "INSERT INTO driver_branches (driver_id, branch_id) VALUES (%s::uuid, %s::uuid)",
                    (driver_id, branch_id),
                )
                cur.execute(
                    "SELECT review_driver(%s::uuid, 'verified', 'Checked for the one-use test.')",
                    (driver_id,),
                )
                cur.execute(
                    """
                    SELECT id::text FROM driver_verification_events
                    WHERE driver_id = %s::uuid AND event_name = 'verified'
                    """,
                    (driver_id,),
                )
                verified_event = cur.fetchone()[0]
                cur.execute(
                    "SELECT set_driver_active(%s::uuid, false, 'First suspension.')",
                    (driver_id,),
                )
                cur.execute(
                    "SELECT set_driver_active(%s::uuid, true, 'First restoration.')",
                    (driver_id,),
                )
                cur.execute(
                    """
                    SELECT id::text FROM driver_active_changes
                    WHERE driver_id = %s::uuid AND active_before = true AND active_after = false
                    """,
                    (driver_id,),
                )
                first_change = cur.fetchone()[0]
                cur.execute("SAVEPOINT reuse_active")
                cur.execute("SET LOCAL ROLE smt_definer")
                cur.execute(
                    "SELECT set_config('app.driver_active_change_id', %s, true)",
                    (first_change,),
                )
                with self.assertRaises(psycopg.Error) as active_denied:
                    cur.execute(
                        "UPDATE drivers SET active = false WHERE id = %s::uuid",
                        (driver_id,),
                    )
                self.assertIn("earlier active-change", str(active_denied.exception))
                cur.execute("ROLLBACK TO SAVEPOINT reuse_active")
                cur.execute(
                    "SELECT review_driver(%s::uuid, 'rejected', 'Reject after the one-use check.')",
                    (driver_id,),
                )
                cur.execute(
                    "SELECT resubmit_driver(%s::uuid, 'Resubmit after the one-use check.')",
                    (driver_id,),
                )
                cur.execute("SAVEPOINT reuse_event")
                cur.execute("SET LOCAL ROLE smt_definer")
                cur.execute(
                    "SELECT set_config('app.driver_verification_event_id', %s, true)",
                    (verified_event,),
                )
                with self.assertRaises(psycopg.Error) as event_denied:
                    cur.execute(
                        """
                        UPDATE drivers
                           SET verification_status = 'verified', active = true
                         WHERE id = %s::uuid
                        """,
                        (driver_id,),
                    )
                self.assertIn("new event", str(event_denied.exception))
                cur.execute("ROLLBACK TO SAVEPOINT reuse_event")
            conn.rollback()
        missing = self.owner.get("/api/drivers", query_string={"name": self.name + " one use"})
        self.assertEqual(missing.get_json()["data"], [])


if __name__ == "__main__":
    unittest.main()
