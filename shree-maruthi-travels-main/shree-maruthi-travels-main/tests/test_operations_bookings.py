"""Phase 1 PostgreSQL booking create and list tests.

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
    with open(path, "rb") as handle:
        hasher.update(handle.read())
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


class OperationBookingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = require_disposable_local_database()
        cls.owner = client_for(OWNER)
        cls.staff = client_for(STAFF)
        cls.anonymous = app_module.app.test_client()
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
            "name": "Operations " + cls.marker,
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
        cls.indexdef = found[0] if found else ""
        cls.global_source_index = (
            "source_booking_id" in cls.indexdef and "branch_id" not in cls.indexdef
        )

    def tearDown(self):
        def work(cur):
            cur.execute(
                "DELETE FROM user_branch_access WHERE user_id = %s::uuid AND branch_id = %s::uuid",
                (self.staff_id, self.branch["BLR"]),
            )
        dev_postgres.authorized_transaction(self.owner_id, work)

    def _payload(self, **extra):
        payload = {
            "branch_id": self.branch["BLR"],
            "trip_date": "2026-12-01",
            "employee_name": "Operations " + self.marker,
            "source_booking_id": "OPS-" + self.marker,
        }
        payload.update(extra)
        return payload

    def test_owner_creates_unassigned_booking_and_lists_it(self):
        self.assertEqual(self.company_status, 201)
        created = self.owner.post("/api/operations/bookings", json=self._payload(
            company_id=self.company_id,
            pickup_time="9:15",
            duty_type="Airport",
            amount=1500,
            toll=0,
            start_km=10,
        ))
        body = created.get_json()
        self.assertEqual(created.status_code, 201, body)
        booking = body["data"]
        self.assertEqual(booking["status"], "unassigned")
        self.assertEqual(booking["origin"], "rac")
        self.assertEqual(booking["source_booking_id"], "OPS-" + self.marker)
        self.assertEqual(booking["pickup_time"], "09:15:00")
        self.assertEqual(booking["amount"], 1500)
        self.assertEqual(booking["toll"], 0)
        self.assertEqual(booking["start_km"], 10)
        self.assertIsNone(booking["parking"])
        self.assertIsNone(booking["end_km"])
        listed = self.owner.get(
            "/api/operations/bookings?branch=BLR&trip_date=2026-12-01&status=unassigned&search="
            + self.marker
        )
        listed_body = listed.get_json()
        self.assertEqual(listed.status_code, 200, listed_body)
        self.assertIn(booking["id"], [row["id"] for row in listed_body["data"]])
        self.assertEqual(self.rac_hash, digest(BACKEND / "rac_data.json"))

    def test_duplicate_source_dates_are_rejected(self):
        source = "OPS-DUP-" + self.marker
        first = self.owner.post("/api/operations/bookings", json=self._payload(
            source_booking_id=source,
            trip_date="2026-12-02",
        ))
        self.assertEqual(first.status_code, 201, first.get_json())
        same_day = self.owner.post("/api/operations/bookings", json=self._payload(
            source_booking_id=source,
            trip_date="2026-12-02",
            employee_name="Other " + self.marker,
        ))
        self.assertEqual(same_day.status_code, 409, same_day.get_json())
        self.assertIn("this date", same_day.get_json()["message"])
        other_day = self.owner.post("/api/operations/bookings", json=self._payload(
            source_booking_id=source,
            trip_date="2026-12-03",
        ))
        self.assertEqual(other_day.status_code, 409, other_day.get_json())
        self.assertIn("another date", other_day.get_json()["message"])

    def test_validation_and_company_city(self):
        missing = self.owner.post("/api/operations/bookings", json={"branch_id": self.branch["BLR"]})
        self.assertEqual(missing.status_code, 400)
        forced = self.owner.post("/api/operations/bookings", json=self._payload(status="assigned"))
        self.assertEqual(forced.status_code, 400)
        self.assertIn("status", forced.get_json()["message"])
        unknown_branch = self.owner.post("/api/operations/bookings", json=self._payload(
            branch_id=str(uuid.uuid4()),
            source_booking_id="OPS-BRANCH-" + self.marker,
        ))
        self.assertEqual(unknown_branch.status_code, 400, unknown_branch.get_json())
        wrong_city = self.owner.post("/api/operations/bookings", json=self._payload(
            branch_id=self.branch["HYD"],
            company_id=self.company_id,
            source_booking_id="OPS-CITY-" + self.marker,
        ))
        self.assertEqual(wrong_city.status_code, 400, wrong_city.get_json())
        self.assertIn("company", wrong_city.get_json()["message"].lower())

    def test_staff_branch_access_and_anonymous_denial(self):
        anonymous = self.anonymous.get("/api/operations/bookings")
        self.assertEqual(anonymous.status_code, 401)

        def clear(cur):
            cur.execute(
                "DELETE FROM user_branch_access WHERE user_id = %s::uuid",
                (self.staff_id,),
            )
        self.assertIsNotNone(dev_postgres.authorized_transaction(self.owner_id, clear))
        denied = self.staff.post("/api/operations/bookings", json=self._payload(
            source_booking_id="OPS-STAFF-" + self.marker,
        ))
        self.assertEqual(denied.status_code, 403, denied.get_json())
        hidden = self.staff.get("/api/operations/bookings?search=" + self.marker)
        self.assertEqual(hidden.status_code, 200, hidden.get_json())
        self.assertEqual(hidden.get_json()["data"], [])

        def grant(cur):
            cur.execute(
                """
                INSERT INTO user_branch_access (user_id, branch_id)
                VALUES (%s::uuid, %s::uuid)
                ON CONFLICT DO NOTHING
                """,
                (self.staff_id, self.branch["BLR"]),
            )
        self.assertIsNotNone(dev_postgres.authorized_transaction(self.owner_id, grant))
        allowed = self.staff.post("/api/operations/bookings", json=self._payload(
            source_booking_id="OPS-STAFF-" + self.marker,
            trip_date="2026-12-04",
        ))
        self.assertEqual(allowed.status_code, 201, allowed.get_json())
        self.assertEqual(allowed.get_json()["data"]["status"], "unassigned")
        visible = self.staff.get("/api/operations/bookings?branch=BLR&search=OPS-STAFF-" + self.marker)
        self.assertEqual(visible.status_code, 200, visible.get_json())
        self.assertEqual(len(visible.get_json()["data"]), 1)
        other_city = self.staff.get("/api/operations/bookings?branch=HYD&search=" + self.marker)
        self.assertEqual(other_city.status_code, 200, other_city.get_json())
        self.assertEqual(other_city.get_json()["data"], [])

    def _require_global_source_index(self):
        if self.global_source_index:
            return
        self.skipTest(
            "bookings_clean_source_code still includes branch_id; "
            "cross-branch inserts are skipped so the forward migration can still be applied"
        )

    def test_blank_source_ids_are_allowed(self):
        payload = self._payload()
        payload.pop("source_booking_id")
        first = self.owner.post("/api/operations/bookings", json=payload)
        second = self.owner.post("/api/operations/bookings", json={
            **payload,
            "trip_date": "2026-12-11",
            "employee_name": "Blank " + self.marker,
        })
        self.assertEqual(first.status_code, 201, first.get_json())
        self.assertEqual(second.status_code, 201, second.get_json())
        self.assertIsNone(first.get_json()["data"]["source_booking_id"])
        self.assertIsNone(second.get_json()["data"]["source_booking_id"])

    def test_owner_rejects_source_id_on_another_branch(self):
        source = "OPS-CITYDUP-" + self.marker
        first = self.owner.post("/api/operations/bookings", json=self._payload(
            branch_id=self.branch["BLR"],
            source_booking_id=source,
            trip_date="2026-12-20",
            employee_name="Visible " + self.marker,
        ))
        self.assertEqual(first.status_code, 201, first.get_json())
        same_day = self.owner.post("/api/operations/bookings", json=self._payload(
            branch_id=self.branch["HYD"],
            source_booking_id=source,
            trip_date="2026-12-20",
        ))
        self.assertEqual(same_day.status_code, 409, same_day.get_json())
        other_day = self.owner.post("/api/operations/bookings", json=self._payload(
            branch_id=self.branch["HYD"],
            source_booking_id=source,
            trip_date="2026-12-21",
        ))
        self.assertEqual(other_day.status_code, 409, other_day.get_json())

    def test_nonclean_source_ids_stay_outside_the_clean_rule(self):
        source = "OPS-CONFLICT-" + self.marker

        def insert_nonclean(cur):
            for identity, trip_date, branch_id in (
                ("conflict", "2026-08-01", self.branch["BLR"]),
                ("conflict", "2026-08-02", self.branch["HYD"]),
                ("missing_code", "2026-08-03", self.branch["BLR"]),
            ):
                cur.execute(
                    """
                    INSERT INTO bookings (
                        branch_id, origin, source_booking_id, identity_status, trip_date, status
                    )
                    VALUES (%s::uuid, 'rac', %s, %s, %s, 'unassigned')
                    """,
                    (branch_id, source, identity, trip_date),
                )
        self.assertIsNotNone(dev_postgres.authorized_transaction(self.owner_id, insert_nonclean))
        clean = self.owner.post("/api/operations/bookings", json=self._payload(
            source_booking_id=source,
            trip_date="2026-08-04",
        ))
        self.assertEqual(clean.status_code, 201, clean.get_json())
        repeat = self.owner.post("/api/operations/bookings", json=self._payload(
            source_booking_id=source,
            trip_date="2026-08-05",
        ))
        self.assertEqual(repeat.status_code, 409, repeat.get_json())

    def test_staff_cannot_learn_another_branch_from_a_duplicate(self):
        self._require_global_source_index()
        source = "OPS-PRIVATE-" + self.marker
        hidden_name = "Hidden passenger " + self.marker
        hidden_date = "2026-07-02"
        created = self.owner.post("/api/operations/bookings", json=self._payload(
            branch_id=self.branch["HYD"],
            source_booking_id=source,
            trip_date=hidden_date,
            employee_name=hidden_name,
            remarks="private-route-" + self.marker,
        ))
        self.assertEqual(created.status_code, 201, created.get_json())

        def limit_staff(cur):
            cur.execute(
                "DELETE FROM user_branch_access WHERE user_id = %s::uuid",
                (self.staff_id,),
            )
            cur.execute(
                """
                INSERT INTO user_branch_access (user_id, branch_id)
                VALUES (%s::uuid, %s::uuid)
                """,
                (self.staff_id, self.branch["BLR"]),
            )
        self.assertIsNotNone(dev_postgres.authorized_transaction(self.owner_id, limit_staff))
        denied = self.staff.post("/api/operations/bookings", json=self._payload(
            branch_id=self.branch["BLR"],
            source_booking_id=source,
            trip_date="2026-07-09",
            employee_name="Local passenger " + self.marker,
        ))
        body = denied.get_json()
        self.assertEqual(denied.status_code, 409, body)
        self.assertEqual(body["message"], "That source booking ID is already used.")
        self.assertEqual(set(body), {"success", "message"})
        rendered = denied.get_data(as_text=True)
        self.assertNotIn(hidden_name, rendered)
        self.assertNotIn(hidden_date, rendered)
        self.assertNotIn(self.branch["HYD"], rendered)
        self.assertNotIn("private-route-" + self.marker, rendered)

    def test_concurrent_duplicate_inserts_leave_one_row(self):
        self._require_global_source_index()
        source = "OPS-RACE-" + self.marker
        payload = self._payload(source_booking_id=source, trip_date="2026-06-15")
        barrier = threading.Barrier(2)
        results = []

        def attempt():
            barrier.wait()
            results.append(dev_postgres.create_operation_booking(self.owner_id, payload))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 2)
        winners = [row for row in results if row and row.get("ok")]
        losers = [row for row in results if row and row.get("error") == "conflict"]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(len(losers), 1, results)

        def count(cur):
            cur.execute(
                """
                SELECT count(*)
                FROM bookings
                WHERE source_booking_id = %s AND identity_status = 'clean'
                """,
                (source,),
            )
            return cur.fetchone()[0]
        counted = dev_postgres.authorized_transaction(self.owner_id, count)
        self.assertEqual(counted["result"], 1)


if __name__ == "__main__":
    unittest.main()
