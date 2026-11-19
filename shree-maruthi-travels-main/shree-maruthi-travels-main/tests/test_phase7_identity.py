"""Local identity and transaction-role checks. Skips unless the local DSN is configured."""
import os
import sys
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values

_vals = dotenv_values(APP_ROOT / '.env')
os.environ['SMT_DEV_DATABASE_URL'] = (_vals.get('SMT_DEV_DATABASE_URL') or '').strip()
os.environ['SMT_DEV_BOOTSTRAP_OWNER_ID'] = (_vals.get('SMT_DEV_BOOTSTRAP_OWNER_ID') or '').strip()

import dev_postgres

OWNERS = (
    'abhishekgowdasmt@gmail.com',
    'shreemaruthitravels5999@gmail.com',
)
STAFF = (
    'bhaskarbhaskarreddy9005@gmail.com',
)
REMOVED = 'veeruashwini01@gmail.com'


def _local_ready():
    return bool(dev_postgres.local_development_dsn() and dev_postgres._bootstrap_owner_id())


@unittest.skipUnless(_local_ready(), 'local development database is not configured')
class LocalIdentityTests(unittest.TestCase):
    def test_allowlist_roles_and_bearer_is_ignored(self):
        for email in OWNERS:
            found = dev_postgres.resolve_login_identity(email)
            self.assertTrue(found.get('ok'), found.get('reason'))
            self.assertEqual(found.get('role'), 'owner')
            forged = {'role': 'smt_migrate', 'user_id': '00000000-0000-0000-0000-000000000000'}
            self.assertEqual(dev_postgres.database_role_for_email(email, forged), 'smt_owner')
        for email in STAFF:
            found = dev_postgres.resolve_login_identity(email)
            self.assertTrue(found.get('ok'), found.get('reason'))
            self.assertEqual(found.get('role'), 'staff')
            forged = {'role': 'owner', 'database_role': 'smt_owner', 'user_id': found.get('id')}
            self.assertEqual(dev_postgres.database_role_for_email(email, forged), 'smt_staff')

    def test_unknown_email_and_injected_role_are_rejected(self):
        missing = dev_postgres.resolve_login_identity('nobody@example.com')
        self.assertEqual(missing.get('reason'), 'not_found')
        self.assertIsNone(dev_postgres.authorized_transaction('smt_owner; DROP TABLE users', lambda cur: 1))

    def test_roles_stay_inside_one_transaction(self):
        staff = dev_postgres.resolve_login_identity(STAFF[0])
        owner = dev_postgres.resolve_login_identity(OWNERS[0])

        def visible(cur):
            cur.execute('SELECT current_user, count(*) FROM users')
            return cur.fetchone()

        staff_tx = dev_postgres.authorized_transaction(staff['id'], visible)
        owner_tx = dev_postgres.authorized_transaction(owner['id'], visible)
        self.assertEqual(staff_tx['result'][0], 'smt_staff')
        self.assertEqual(staff_tx['result'][1], 1)
        self.assertEqual(staff_tx['after_commit_user'], 'smt_app')
        self.assertEqual(owner_tx['result'][0], 'smt_owner')
        self.assertEqual(owner_tx['result'][1], 4)
        self.assertEqual(owner_tx['after_commit_user'], 'smt_app')
        self.assertEqual(owner_tx['database_role'], 'smt_owner')

        import psycopg
        with psycopg.connect(dev_postgres.local_development_dsn(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_user')
                self.assertEqual(cur.fetchone()[0], 'smt_app')

    def test_removed_staff_identity_stays_disabled(self):
        removed = dev_postgres.resolve_login_identity(REMOVED)
        self.assertEqual(removed.get('reason'), 'disabled')
        self.assertEqual(removed.get('role'), 'staff')
        self.assertIsNone(dev_postgres.authorized_transaction(removed['id'], lambda cur: 1))
        self.assertIsNone(dev_postgres.database_role_for_email(REMOVED, {'role': 'staff'}))
        owner = dev_postgres.resolve_login_identity(OWNERS[0])

        def snapshot(cur):
            cur.execute(
                """
                SELECT id::text, role, status,
                       (SELECT count(*) FROM user_branch_access WHERE user_id = users.id)
                FROM users
                WHERE lower(email) = lower(%s)
                """,
                (REMOVED,),
            )
            return cur.fetchone()

        row = dev_postgres.authorized_transaction(owner['id'], snapshot)['result']
        self.assertEqual(row[0], removed['id'])
        self.assertEqual(row[1], 'staff')
        self.assertEqual(row[2], 'disabled')
        self.assertEqual(row[3], 0)


if __name__ == '__main__':
    unittest.main()
