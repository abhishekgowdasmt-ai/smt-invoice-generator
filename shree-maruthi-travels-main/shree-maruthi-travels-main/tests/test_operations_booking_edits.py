"""Phase 2 PostgreSQL booking edit and reschedule tests.

These tests commit rows on a disposable local database whose name ends with
_test. They refuse smt_dev. The RAC JSON store is only hashed.
"""
import hashlib
import os
import sys
import threading
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


class OperationBookingEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        cls.owner = client_for(OWNER)
        cls.staff = client_for(STAFF)
        cls.marker = uuid.uuid4().hex[:10]
        cls.rac_hash = digest(BACKEND / "rac_data.json")
        owner = dev_postgres.resolve_login_identity(OWNER)
        staff = dev_postgres.resolve_login_identity(STAFF)
        if not owner.get("ok") or not staff.get("ok"):
            raise unittest.SkipTest("disposable database is missing the local staff identities")
        cls.owner_id = owner["id"]
        cls.staff_id = staff["id"]
        branches = cls.owner.get("/api/branches").get_json()["data"]
        cls.branch = {row["code"]: row["id"] for row in branches}
        created = cls.owner.post("/api/companies", json={
            "name": "Edit operations " + cls.marker,
            "branch_codes": ["BLR"],
        })
        cls.company_id = (created.get_json().get("data") or {}).get("id")
        cls.company_status = created.status_code
        import psycopg
        with psycopg.connect(dev_postgres.local_development_dsn(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public' AND indexname = 'bookings_clean_source_code'
                    """
                )
                found = cur.fetchone()
        definition = (found[0] if found else "").lower()
        if "branch_id" in definition or "(source_booking_id)" not in definition:
            raise unittest.SkipTest(
                "bookings_clean_source_code is not a global source booking ID index"
            )

    def tearDown(self):
        def work(cur):
            cur.execute(
                "DELETE FROM user_branch_access WHERE user_id = %s::uuid AND branch_id IN (%s::uuid, %s::uuid)",
                (self.staff_id, self.branch["BLR"], self.branch["HYD"]),
            )
        dev_postgres.authorized_transaction(self.owner_id, work)

    def create(self, **extra):
        source = extra.pop("source_booking_id", "EDT-" + uuid.uuid4().hex[:12])
        payload = {
            "branch_id": self.branch["BLR"],
            "trip_date": "2026-12-01",
            "employee_name": "Edit " + self.marker,
            "remarks": "Keep remarks " + self.marker,
            "source_booking_id": source,
        }
        payload.update(extra)
        created = self.owner.post("/api/operations/bookings", json=payload)
        self.assertEqual(created.status_code, 201, created.get_json())
        return created.get_json()["data"]

    def patch(self, client, booking_id, payload):
        return client.patch("/api/operations/bookings/" + booking_id, json=payload)

    def grant_blr(self):
        def work(cur):
            cur.execute(
                """
                INSERT INTO user_branch_access (user_id, branch_id)
                VALUES (%s::uuid, %s::uuid)
                ON CONFLICT DO NOTHING
                """,
                (self.staff_id, self.branch["BLR"]),
            )
        self.assertIsNotNone(dev_postgres.authorized_transaction(self.owner_id, work))

    def reload(self, booking_id, source):
        listed = self.owner.get("/api/operations/bookings?search=" + source)
        self.assertEqual(listed.status_code, 200, listed.get_json())
        matches = [row for row in listed.get_json()["data"] if row["id"] == booking_id]
        self.assertEqual(len(matches), 1, listed.get_json())
        return matches[0]

    def advance(self, booking_id, target, branch_id=None):
        """Move a fixture booking forward on the disposable database.

        The booking status is set first, so the nested SECURITY DEFINER updates
        in assignment_after and session_after match no rows. Their
        search_path = pg_catalog cannot resolve null_if_blank, so a nested
        update that does match a row fails. No schema change is made.
        Returns None on success or the database message for a blocked step.
        """
        box = {
            "driver_id": getattr(self, "driver_id", None),
            "assignment_id": getattr(self, "assignment_id", None),
            "session_id": getattr(self, "session_id", None),
        }

        def work(cur):
            import psycopg
            cur.execute("SAVEPOINT fixture")
            try:
                if target == "assigned":
                    box["driver_id"] = str(uuid.uuid4())
                    box["assignment_id"] = str(uuid.uuid4())
                    cur.execute(
                        """
                        INSERT INTO drivers (id, primary_branch_id, display_name)
                        VALUES (%s::uuid, %s::uuid, %s)
                        """,
                        (box["driver_id"], branch_id, "Edit driver " + self.marker),
                    )
                    cur.execute(
                        "INSERT INTO driver_branches (driver_id, branch_id) VALUES (%s::uuid, %s::uuid)",
                        (box["driver_id"], branch_id),
                    )
                    cur.execute(
                        "UPDATE bookings SET status = 'assigned' WHERE id = %s::uuid AND status = 'unassigned'",
                        (booking_id,),
                    )
                    cur.execute(
                        """
                        INSERT INTO booking_assignments (id, booking_id, driver_id, assigned_by, status)
                        VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'assigned')
                        """,
                        (box["assignment_id"], booking_id, box["driver_id"], self.owner_id),
                    )
                elif target == "accepted":
                    cur.execute(
                        "UPDATE bookings SET status = 'accepted' WHERE id = %s::uuid AND status = 'assigned'",
                        (booking_id,),
                    )
                    cur.execute(
                        "UPDATE booking_assignments SET status = 'accepted' WHERE id = %s::uuid",
                        (box["assignment_id"],),
                    )
                elif target == "started":
                    box["session_id"] = str(uuid.uuid4())
                    cur.execute(
                        "UPDATE bookings SET status = 'started' WHERE id = %s::uuid AND status = 'accepted'",
                        (booking_id,),
                    )
                    cur.execute(
                        """
                        INSERT INTO trip_sessions (
                            id, assignment_id, driver_id, session_origin, status, started_at
                        )
                        VALUES (%s::uuid, %s::uuid, %s::uuid, 'duty', 'active', now())
                        """,
                        (box["session_id"], box["assignment_id"], box["driver_id"]),
                    )
                elif target == "completed":
                    cur.execute(
                        "UPDATE bookings SET status = 'completed' WHERE id = %s::uuid AND status = 'started'",
                        (booking_id,),
                    )
                elif target == "cancelled":
                    cur.execute(
                        "UPDATE bookings SET status = 'cancelled' WHERE id = %s::uuid AND status = 'unassigned'",
                        (booking_id,),
                    )
                cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
                cur.execute("SELECT status FROM bookings WHERE id = %s::uuid", (booking_id,))
                found = cur.fetchone()[0]
                cur.execute("RELEASE SAVEPOINT fixture")
                return {"ok": True, "status": found}
            except psycopg.Error as exc:
                cur.execute("ROLLBACK TO SAVEPOINT fixture")
                primary = getattr(getattr(exc, "diag", None), "message_primary", None)
                return {"ok": False, "message": primary or type(exc).__name__}

        done = dev_postgres.authorized_transaction(self.owner_id, work)
        self.assertIsNotNone(done, target)
        if not done["result"]["ok"]:
            return done["result"]["message"]
        self.assertEqual(done["result"]["status"], target, done["result"])
        self.driver_id = box["driver_id"]
        self.assignment_id = box["assignment_id"]
        self.session_id = box["session_id"]
        return None

    def test_owner_edits_unassigned_booking(self):
        self.assertEqual(self.company_status, 201)
        booking = self.create(amount=100, pickup_time="08:00")

        def events(cur):
            cur.execute(
                "SELECT count(*) FROM booking_events WHERE booking_id = %s::uuid",
                (booking["id"],),
            )
            return cur.fetchone()[0]

        before = dev_postgres.authorized_transaction(self.owner_id, events)
        edited = self.patch(self.owner, booking["id"], {
            "employee_name": "Renamed " + self.marker,
            "duty_type": "Airport",
            "pickup_time": "10:30",
        })
        body = edited.get_json()
        self.assertEqual(edited.status_code, 200, body)
        self.assertEqual(body["data"]["id"], booking["id"])
        self.assertEqual(body["data"]["status"], "unassigned")
        self.assertEqual(body["data"]["origin"], "rac")
        self.assertEqual(body["data"]["employee_name"], "Renamed " + self.marker)
        self.assertEqual(body["data"]["duty_type"], "Airport")
        self.assertEqual(body["data"]["pickup_time"], "10:30:00")
        self.assertEqual(body["data"]["remarks"], booking["remarks"])
        after = dev_postgres.authorized_transaction(self.owner_id, events)
        self.assertEqual(before["result"], after["result"])
        self.assertEqual(self.rac_hash, digest(BACKEND / "rac_data.json"))

    def test_staff_edits_authorized_branch(self):
        self.grant_blr()
        booking = self.create()
        edited = self.patch(self.staff, booking["id"], {"remarks": "Staff note " + self.marker})
        body = edited.get_json()
        self.assertEqual(edited.status_code, 200, body)
        self.assertEqual(body["data"]["remarks"], "Staff note " + self.marker)
        self.assertEqual(body["data"]["status"], "unassigned")

    def test_staff_cannot_edit_another_branch(self):
        self.grant_blr()
        secret = "Hidden edit " + self.marker
        booking = self.create(
            branch_id=self.branch["HYD"],
            employee_name=secret,
            source_booking_id="EDT-HID-" + self.marker,
            trip_date="2026-07-02",
        )
        denied = self.patch(self.staff, booking["id"], {"employee_name": "Local"})
        body = denied.get_json()
        self.assertEqual(denied.status_code, 404, body)
        self.assertEqual(body["message"], "Booking was not found.")
        rendered = denied.get_data(as_text=True)
        self.assertNotIn(secret, rendered)
        self.assertNotIn(self.branch["HYD"], rendered)
        self.assertNotIn("2026-07-02", rendered)

    def test_staff_with_both_branches_can_move_a_booking(self):
        self.grant_blr()

        def grant_hyd(cur):
            cur.execute(
                """
                INSERT INTO user_branch_access (user_id, branch_id)
                VALUES (%s::uuid, %s::uuid)
                ON CONFLICT DO NOTHING
                """,
                (self.staff_id, self.branch["HYD"]),
            )
        self.assertIsNotNone(dev_postgres.authorized_transaction(self.owner_id, grant_hyd))
        booking = self.create(source_booking_id="EDT-BOTH-" + self.marker)
        moved = self.patch(self.staff, booking["id"], {"branch_id": self.branch["HYD"]})
        self.assertEqual(moved.status_code, 200, moved.get_json())
        self.assertEqual(moved.get_json()["data"]["branch_id"], self.branch["HYD"])
        self.assertEqual(moved.get_json()["data"]["status"], "unassigned")
        self.assertEqual(moved.get_json()["data"]["origin"], "rac")

    def test_missing_global_source_index_is_reported(self):
        class FakeCursor:
            def __init__(self, definition):
                self.definition = definition

            def execute(self, *_args, **_kwargs):
                pass

            def fetchone(self):
                return None if self.definition is None else (self.definition,)

        old_style = (
            "CREATE UNIQUE INDEX bookings_clean_source_code ON public.bookings "
            "USING btree (branch_id, source_booking_id, trip_date) WHERE "
            "((source_booking_id IS NOT NULL) AND (identity_status = 'clean'::text))"
        )
        global_style = (
            "CREATE UNIQUE INDEX bookings_clean_source_code ON public.bookings "
            "USING btree (source_booking_id) WHERE "
            "((source_booking_id IS NOT NULL) AND (identity_status = 'clean'::text))"
        )
        self.assertFalse(dev_postgres._source_index_is_global(FakeCursor(None)))
        self.assertFalse(dev_postgres._source_index_is_global(FakeCursor(old_style)))
        self.assertTrue(dev_postgres._source_index_is_global(FakeCursor(global_style)))

    def test_staff_cannot_move_to_unauthorized_branch(self):
        self.grant_blr()
        booking = self.create(source_booking_id="EDT-MOVE-" + self.marker)
        denied = self.patch(self.staff, booking["id"], {"branch_id": self.branch["HYD"]})
        self.assertEqual(denied.status_code, 403, denied.get_json())
        self.assertEqual(denied.get_json()["message"], "You cannot use this branch.")
        kept = self.reload(booking["id"], "EDT-MOVE-" + self.marker)
        self.assertEqual(kept["branch_id"], self.branch["BLR"])

    def test_owner_moves_between_branches(self):
        plain = self.create(source_booking_id="EDT-CITY-" + self.marker)
        moved = self.patch(self.owner, plain["id"], {"branch_id": self.branch["HYD"]})
        self.assertEqual(moved.status_code, 200, moved.get_json())
        self.assertEqual(moved.get_json()["data"]["branch_id"], self.branch["HYD"])
        self.assertEqual(moved.get_json()["data"]["status"], "unassigned")
        linked = self.create(
            company_id=self.company_id,
            source_booking_id="EDT-LINK-" + self.marker,
        )
        rejected = self.patch(self.owner, linked["id"], {"branch_id": self.branch["HYD"]})
        self.assertEqual(rejected.status_code, 400, rejected.get_json())
        self.assertIn("company", rejected.get_json()["message"].lower())
        stayed = self.reload(linked["id"], "EDT-LINK-" + self.marker)
        self.assertEqual(stayed["branch_id"], self.branch["BLR"])

    def test_duplicate_source_id_is_rejected(self):
        first = self.create(source_booking_id="EDT-DUP-" + self.marker, trip_date="2026-12-08")
        second = self.create(source_booking_id="EDT-OTHER-" + self.marker, trip_date="2026-12-08")
        visible = self.patch(self.owner, second["id"], {"source_booking_id": first["source_booking_id"]})
        self.assertEqual(visible.status_code, 409, visible.get_json())
        self.assertIn("already used", visible.get_json()["message"])
        self.grant_blr()
        secret = "Cross branch " + self.marker
        hidden = self.create(
            branch_id=self.branch["HYD"],
            employee_name=secret,
            source_booking_id="EDT-X-" + self.marker,
            trip_date="2026-05-01",
        )
        local = self.create(source_booking_id="EDT-L-" + self.marker, trip_date="2026-05-09")
        hidden_conflict = self.patch(self.staff, local["id"], {
            "source_booking_id": hidden["source_booking_id"],
        })
        body = hidden_conflict.get_json()
        self.assertEqual(hidden_conflict.status_code, 409, body)
        self.assertEqual(body["message"], "That source booking ID is already used.")
        rendered = hidden_conflict.get_data(as_text=True)
        self.assertNotIn(secret, rendered)
        self.assertNotIn(self.branch["HYD"], rendered)
        self.assertNotIn("2026-05-01", rendered)

    def test_concurrent_source_updates_leave_one_row(self):
        left = self.create(source_booking_id="EDT-R1-" + self.marker)
        right = self.create(source_booking_id="EDT-R2-" + self.marker)
        shared = "EDT-RACE-" + self.marker
        barrier = threading.Barrier(2)
        results = []

        def attempt(booking_id):
            barrier.wait()
            results.append(dev_postgres.update_operation_booking(
                self.owner_id,
                booking_id,
                {"source_booking_id": shared},
            ))

        threads = [
            threading.Thread(target=attempt, args=(left["id"],)),
            threading.Thread(target=attempt, args=(right["id"],)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        winners = [row for row in results if row and row.get("ok")]
        losers = [row for row in results if row and row.get("error") == "conflict"]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(len(losers), 1, results)
        self.assertIn("already used", losers[0]["message"])

        def count(cur):
            cur.execute(
                """
                SELECT count(*)
                FROM bookings
                WHERE source_booking_id = %s AND identity_status = 'clean'
                """,
                (shared,),
            )
            return cur.fetchone()[0]

        counted = dev_postgres.authorized_transaction(self.owner_id, count)
        self.assertEqual(counted["result"], 1)

    def test_reschedule_date_and_times(self):
        booking = self.create(pickup_time="09:00", end_time="12:00")
        edited = self.patch(self.owner, booking["id"], {
            "trip_date": "2026-12-18",
            "pickup_time": "14:05",
            "end_time": "18:00",
        })
        body = edited.get_json()
        self.assertEqual(edited.status_code, 200, body)
        self.assertEqual(body["data"]["id"], booking["id"])
        self.assertEqual(body["data"]["status"], "unassigned")
        self.assertEqual(body["data"]["trip_date"], "2026-12-18")
        self.assertEqual(body["data"]["pickup_time"], "14:05:00")
        self.assertEqual(body["data"]["end_time"], "18:00:00")
        self.assertEqual(body["data"]["employee_name"], booking["employee_name"])

    def test_assigned_booking_cannot_be_edited(self):
        booking = self.create(source_booking_id="EDT-ASG-" + self.marker)
        self.assertIsNone(self.advance(booking["id"], "assigned", self.branch["BLR"]))
        denied = self.patch(self.owner, booking["id"], {"employee_name": "Too late"})
        self.assertEqual(denied.status_code, 409, denied.get_json())
        self.assertEqual(denied.get_json()["message"], "Only an unassigned booking can be edited.")
        kept = self.reload(booking["id"], booking["source_booking_id"])
        self.assertEqual(kept["status"], "assigned")
        self.assertEqual(kept["employee_name"], booking["employee_name"])

    def test_accepted_and_started_bookings_cannot_be_edited(self):
        booking = self.create(source_booking_id="EDT-LATE-" + self.marker)
        self.assertIsNone(self.advance(booking["id"], "assigned", self.branch["BLR"]))
        for target in ("accepted", "started"):
            self.assertIsNone(self.advance(booking["id"], target))
            denied = self.patch(self.owner, booking["id"], {"remarks": "No edit"})
            self.assertEqual(denied.status_code, 409, denied.get_json())
            self.assertEqual(denied.get_json()["message"], "Only an unassigned booking can be edited.")
            kept = self.reload(booking["id"], booking["source_booking_id"])
            self.assertEqual(kept["status"], target)
            self.assertEqual(kept["remarks"], booking["remarks"])

    def test_completed_booking_cannot_be_edited(self):
        booking = self.create(source_booking_id="EDT-DONE-" + self.marker)
        self.assertIsNone(self.advance(booking["id"], "assigned", self.branch["BLR"]))
        self.assertIsNone(self.advance(booking["id"], "accepted"))
        self.assertIsNone(self.advance(booking["id"], "started"))
        blocked = self.advance(booking["id"], "completed")
        if blocked is not None:
            self.skipTest(
                "The database cannot complete a booking in this schema: " + blocked
                + ". No schema change was made."
            )
        denied = self.patch(self.owner, booking["id"], {"remarks": "No edit"})
        self.assertEqual(denied.status_code, 409, denied.get_json())
        self.assertEqual(denied.get_json()["message"], "Only an unassigned booking can be edited.")

    def test_cancelled_booking_cannot_be_edited(self):
        cancelled = self.create(source_booking_id="EDT-CAN-" + self.marker)
        self.advance(cancelled["id"], "cancelled")
        denied = self.patch(self.owner, cancelled["id"], {"remarks": "No cancel edit"})
        self.assertEqual(denied.status_code, 409, denied.get_json())
        self.assertEqual(denied.get_json()["message"], "Only an unassigned booking can be edited.")

    def test_omitted_fields_stay_unchanged(self):
        booking = self.create(amount=80, toll=15, duty_type="Local", pickup_time="07:15")
        edited = self.patch(self.owner, booking["id"], {"employee_name": "Only name " + self.marker})
        body = edited.get_json()
        self.assertEqual(edited.status_code, 200, body)
        data = body["data"]
        self.assertEqual(data["employee_name"], "Only name " + self.marker)
        self.assertEqual(data["remarks"], booking["remarks"])
        self.assertEqual(data["duty_type"], "Local")
        self.assertEqual(data["pickup_time"], "07:15:00")
        self.assertEqual(data["amount"], 80)
        self.assertEqual(data["toll"], 15)
        self.assertEqual(data["trip_date"], booking["trip_date"])
        self.assertEqual(data["source_booking_id"], booking["source_booking_id"])

    def test_explicit_null_clears_optional_fields(self):
        booking = self.create(
            company_id=self.company_id,
            amount=40,
            toll=5,
            pickup_time="06:00",
            source_booking_id="EDT-NULL-" + self.marker,
        )
        edited = self.patch(self.owner, booking["id"], {
            "company_id": None,
            "remarks": None,
            "pickup_time": None,
            "amount": None,
        })
        body = edited.get_json()
        self.assertEqual(edited.status_code, 200, body)
        data = body["data"]
        self.assertIsNone(data["company_id"])
        self.assertIsNone(data["remarks"])
        self.assertIsNone(data["pickup_time"])
        self.assertIsNone(data["amount"])
        self.assertEqual(data["toll"], 5)
        self.assertEqual(data["source_booking_id"], booking["source_booking_id"])
        self.assertEqual(data["employee_name"], booking["employee_name"])
        self.assertEqual(data["branch_id"], booking["branch_id"])

    def test_source_id_null_and_blank_booking_rules(self):
        booking = self.create(source_booking_id="EDT-KEEP-" + self.marker)
        removal = self.patch(self.owner, booking["id"], {"source_booking_id": None})
        self.assertEqual(removal.status_code, 409, removal.get_json())
        self.assertEqual(
            removal.get_json()["message"],
            "A source booking ID cannot be removed once it is set.",
        )
        kept = self.reload(booking["id"], booking["source_booking_id"])
        self.assertEqual(kept["source_booking_id"], booking["source_booking_id"])
        blank = self.create(source_booking_id=None, employee_name="Blank " + self.marker)
        self.assertIsNone(blank["source_booking_id"])
        unchanged = self.patch(self.owner, blank["id"], {"source_booking_id": None, "remarks": "Blank ok"})
        self.assertEqual(unchanged.status_code, 200, unchanged.get_json())
        self.assertIsNone(unchanged.get_json()["data"]["source_booking_id"])
        added = self.patch(self.owner, blank["id"], {"source_booking_id": "EDT-NEW-" + self.marker})
        self.assertEqual(added.status_code, 409, added.get_json())
        self.assertEqual(
            added.get_json()["message"],
            "A source booking ID cannot be added to this booking.",
        )

    def test_empty_patch_and_non_rac_booking_are_refused(self):
        booking = self.create(source_booking_id="EDT-EMPTY-" + self.marker)
        empty = self.patch(self.owner, booking["id"], {})
        self.assertEqual(empty.status_code, 400, empty.get_json())
        self.assertEqual(empty.get_json()["message"], "No booking changes were supplied.")
        retail_id = str(uuid.uuid4())

        def insert_retail(cur):
            cur.execute(
                """
                INSERT INTO bookings (id, branch_id, origin, trip_date, status, employee_name)
                VALUES (%s::uuid, %s::uuid, 'retail', '2026-09-01', 'unassigned', 'Retail')
                """,
                (retail_id, self.branch["BLR"]),
            )
        self.assertIsNotNone(dev_postgres.authorized_transaction(self.owner_id, insert_retail))
        refused = self.patch(self.owner, retail_id, {"remarks": "Not a RAC booking"})
        self.assertEqual(refused.status_code, 409, refused.get_json())
        self.assertEqual(refused.get_json()["message"], "Only a RAC booking can be edited here.")

    def test_charges_and_readings_update_without_duplication(self):
        booking = self.create(amount=100, toll=20, start_km=10)
        edited = self.patch(self.owner, booking["id"], {"amount": 250, "end_km": 40})
        body = edited.get_json()
        self.assertEqual(edited.status_code, 200, body)
        data = body["data"]
        self.assertEqual(data["amount"], 250)
        self.assertEqual(data["toll"], 20)
        self.assertIsNone(data["parking"])
        self.assertEqual(data["start_km"], 10)
        self.assertEqual(data["end_km"], 40)

        def counts(cur):
            cur.execute("SELECT count(*) FROM booking_charges WHERE booking_id = %s::uuid", (booking["id"],))
            charges = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM duty_readings WHERE booking_id = %s::uuid", (booking["id"],))
            readings = cur.fetchone()[0]
            return charges, readings

        counted = dev_postgres.authorized_transaction(self.owner_id, counts)
        self.assertEqual(counted["result"], (1, 1))

    def test_invalid_values_are_rejected(self):
        booking = self.create()
        bad_date = self.patch(self.owner, booking["id"], {"trip_date": "tomorrow"})
        self.assertEqual(bad_date.status_code, 400, bad_date.get_json())
        self.assertIn("date", bad_date.get_json()["message"].lower())
        negative = self.patch(self.owner, booking["id"], {"amount": -5})
        self.assertEqual(negative.status_code, 400, negative.get_json())
        self.assertIn("zero", negative.get_json()["message"].lower())
        clock = self.patch(self.owner, booking["id"], {"pickup_time": "25:00"})
        self.assertEqual(clock.status_code, 400, clock.get_json())
        unknown = self.patch(self.owner, booking["id"], {"driver_notes": "nope"})
        self.assertEqual(unknown.status_code, 400, unknown.get_json())
        cleared_branch = self.patch(self.owner, booking["id"], {"branch_id": None})
        self.assertEqual(cleared_branch.status_code, 400, cleared_branch.get_json())
        self.assertIn("branch", cleared_branch.get_json()["message"].lower())
        kept = self.reload(booking["id"], booking["source_booking_id"])
        self.assertEqual(kept["employee_name"], booking["employee_name"])
        self.assertEqual(kept["trip_date"], booking["trip_date"])

    def test_failed_child_update_rolls_back(self):
        booking = self.create(employee_name="Keep name " + self.marker, start_km=12)
        failed = self.patch(self.owner, booking["id"], {
            "employee_name": "Changed " + self.marker,
            "start_km": 9999999999,
        })
        self.assertEqual(failed.status_code, 400, failed.get_json())
        self.assertEqual(failed.get_json()["message"], "Amounts and distances are too large.")
        kept = self.reload(booking["id"], booking["source_booking_id"])
        self.assertEqual(kept["employee_name"], "Keep name " + self.marker)
        self.assertEqual(kept["start_km"], 12)

    def test_protected_fields_are_rejected(self):
        booking = self.create()
        for payload in (
            {"status": "assigned"},
            {"origin": "retail"},
            {"id": str(uuid.uuid4())},
            {"assigned_by": self.owner_id},
            {"created_at": "2026-01-01T00:00:00+05:30"},
            {"user_id": self.owner_id},
        ):
            denied = self.patch(self.owner, booking["id"], payload)
            self.assertEqual(denied.status_code, 400, denied.get_json())
            self.assertIn("status", denied.get_json()["message"].lower())
        missing = self.patch(self.owner, "not-a-booking", {"remarks": "x"})
        self.assertEqual(missing.status_code, 404, missing.get_json())
        anonymous = app_module.app.test_client().patch(
            "/api/operations/bookings/" + booking["id"],
            json={"remarks": "x"},
        )
        self.assertEqual(anonymous.status_code, 401)


if __name__ == "__main__":
    unittest.main()
