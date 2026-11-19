import os
import sys
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / 'backend'
os.environ['STAFF_TOKEN'] = 's' * 48
os.environ['RAC_JWT_SECRET'] = 'r' * 48
os.environ['SMT_DEV_DATABASE_URL'] = ''
os.environ['GOOGLE_CLIENT_ID'] = ''
os.environ['GOOGLE_CLIENT_SECRET'] = ''
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(BACKEND))

import backend.app as app_module
import rac_api
import staff_auth


def _cookie_header(response):
    return response.headers.get('Set-Cookie', '')


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        os.environ['SMT_DEV_DATABASE_URL'] = ''
        self.client = app_module.app.test_client()

    def test_logout_clears_the_cookie_over_http(self):
        token = staff_auth.issue_token('bhaskarbhaskarreddy9005@gmail.com')
        self.client.set_cookie('smt_staff', token)
        self.assertEqual(self.client.get('/api/admin/me').status_code, 200)
        response = self.client.post('/api/admin/logout')
        cleared = _cookie_header(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn('smt_staff=', cleared)
        self.assertIn('Max-Age=0', cleared)
        self.assertIn('SameSite=Lax', cleared)
        self.assertIn('HttpOnly', cleared)
        self.assertIn('Path=/', cleared)
        self.assertNotIn('Secure', cleared)
        self.assertEqual(self.client.get('/api/admin/me').status_code, 401)

    def test_logout_clears_a_secure_cookie_when_https_is_forwarded(self):
        response = self.client.post(
            '/api/admin/logout',
            headers={'X-Forwarded-Proto': 'https'},
            base_url='https://127.0.0.1',
        )
        cleared = _cookie_header(response)
        self.assertIn('Secure', cleared)
        self.assertIn('SameSite=Lax', cleared)
        self.assertIn('HttpOnly', cleared)
        self.assertIn('Path=/', cleared)
        self.assertIn('Max-Age=0', cleared)

    def test_dispatch_bearer_cannot_open_the_dashboard(self):
        bearer = rac_api.TOKEN.dumps({
            'user_id': 'rac-staff',
            'email': 'abhishekgowdasmt@gmail.com',
            'first_name': 'abhishekgowdasmt',
            'last_name': '',
            'role': 'admin',
            'active': True,
        })
        response = self.client.get(
            '/api/v1/dashboard/summary',
            headers={'Authorization': f'Bearer {bearer}'},
        )
        self.assertEqual(response.status_code, 401)

    def test_staff_cookie_still_opens_the_dashboard(self):
        self.client.set_cookie('smt_staff', staff_auth.issue_token('bhaskarbhaskarreddy9005@gmail.com'))
        response = self.client.get('/api/v1/dashboard/summary')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])

    def test_owner_cookie_still_opens_dispatch(self):
        self.client.set_cookie('smt_staff', staff_auth.issue_token('abhishekgowdasmt@gmail.com'))
        response = self.client.get('/admin/dispatch/dashboard')
        self.assertEqual(response.status_code, 200)

    def test_disabled_local_identity_is_rejected_on_the_next_request(self):
        token = staff_auth.issue_token('bhaskarbhaskarreddy9005@gmail.com')
        self.client.set_cookie('smt_staff', token)
        self.assertEqual(self.client.get('/api/admin/me').status_code, 200)
        os.environ['SMT_DEV_DATABASE_URL'] = 'postgresql://smt_app:local@127.0.0.1:5432/smt_dev'
        original = app_module.dev_postgres.resolve_login_identity
        app_module.dev_postgres.resolve_login_identity = lambda email: {
            'ok': False,
            'reason': 'disabled',
            'role': 'staff',
        }
        try:
            me = self.client.get('/api/admin/me')
            summary = self.client.get('/api/v1/dashboard/summary')
        finally:
            app_module.dev_postgres.resolve_login_identity = original
            os.environ['SMT_DEV_DATABASE_URL'] = ''
        self.assertEqual(me.status_code, 401)
        self.assertEqual(summary.status_code, 401)

    def test_production_without_the_local_database_keeps_the_allowlist_session(self):
        os.environ['SMT_DEV_DATABASE_URL'] = ''
        self.client.set_cookie('smt_staff', staff_auth.issue_token('shreemaruthitravels5999@gmail.com'))
        response = self.client.get('/api/admin/me')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['authenticated'])


if __name__ == '__main__':
    unittest.main()
