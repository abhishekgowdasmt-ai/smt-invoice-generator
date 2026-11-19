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
import staff_auth


class RedirectSafetyTests(unittest.TestCase):
    def test_safe_application_paths(self):
        for path in ('/admin', '/admin/dispatch/', '/admin/dispatch/dashboard', '/admin/dispatch/bookings?payment=Unpaid'):
            self.assertEqual(staff_auth.safe_local_path(path), path)

    def test_unsafe_redirects_use_the_local_fallback(self):
        unsafe = (
            '//evil.example',
            '///evil.example',
            '/\\evil.example',
            'http://evil.example',
            'https://evil.example/admin',
            'https://evil.example',
            '/%2f%2fevil.example',
            '/%5cevil.example',
            'javascript:alert(1)',
            'evil.example',
            '',
            None,
            ' /admin',
        )
        for value in unsafe:
            self.assertEqual(staff_auth.safe_local_path(value), '/admin', value)

    def test_callback_rejects_a_signed_protocol_relative_next(self):
        original_configured = staff_auth.google_configured
        original_exchange = staff_auth.google_exchange
        staff_auth.google_configured = lambda: True
        staff_auth.google_exchange = lambda code, redirect_uri: ('abhishekgowdasmt@gmail.com', None)
        try:
            state = staff_auth.dump_state({'next': '//evil.example'})
            response = app_module.app.test_client().get(
                '/admin/google/callback',
                query_string={'code': 'local-test-code', 'state': state},
            )
        finally:
            staff_auth.google_configured = original_configured
            staff_auth.google_exchange = original_exchange
        location = response.headers.get('Location', '')
        self.assertNotIn('evil.example', location)
        self.assertTrue(location.endswith('/admin'))
        self.assertNotIn('smt_staff=', location)
        self.assertIn('smt_staff=', response.headers.get('Set-Cookie', ''))

    def test_callback_keeps_a_safe_dispatch_path_and_the_token_out_of_the_url(self):
        original_configured = staff_auth.google_configured
        original_exchange = staff_auth.google_exchange
        staff_auth.google_configured = lambda: True
        staff_auth.google_exchange = lambda code, redirect_uri: ('bhaskarbhaskarreddy9005@gmail.com', None)
        try:
            state = staff_auth.dump_state({'next': '/admin/dispatch/dashboard'})
            response = app_module.app.test_client().get(
                '/admin/google/callback',
                query_string={'code': 'local-test-code', 'state': state},
            )
        finally:
            staff_auth.google_configured = original_configured
            staff_auth.google_exchange = original_exchange
        location = response.headers.get('Location', '')
        cookie = response.headers.get('Set-Cookie', '')
        self.assertTrue(location.endswith('/admin/dispatch/dashboard'))
        self.assertNotIn(cookie.split('=', 1)[1].split(';', 1)[0], location)
        self.assertNotIn('token=', location.lower())

    def test_unallowlisted_email_does_not_get_a_session(self):
        self.assertIsNone(staff_auth.issue_token('nobody@example.com'))
        self.assertIsNone(staff_auth.postgres_role_for('nobody@example.com'))
        self.assertIsNone(staff_auth.issue_token('veeruashwini01@gmail.com'))
        self.assertIsNone(staff_auth.postgres_role_for('veeruashwini01@gmail.com'))
        previous = staff_auth._SERIALIZER.dumps({
            'email': 'veeruashwini01@gmail.com',
            'role': 'staff',
        })
        self.assertIsNone(staff_auth.read_token(previous))

    def test_google_callback_rejects_the_removed_staff_identity(self):
        original_configured = staff_auth.google_configured
        original_exchange = staff_auth.google_exchange
        staff_auth.google_configured = lambda: True
        staff_auth.google_exchange = lambda code, redirect_uri: ('veeruashwini01@gmail.com', None)
        try:
            state = staff_auth.dump_state({'next': '/admin'})
            response = app_module.app.test_client().get(
                '/admin/google/callback',
                query_string={'code': 'local-test-code', 'state': state},
            )
        finally:
            staff_auth.google_configured = original_configured
            staff_auth.google_exchange = original_exchange
        location = response.headers.get('Location', '')
        self.assertIn('login_error=not_allowed', location)
        self.assertNotIn('smt_staff=', response.headers.get('Set-Cookie', ''))

    def test_allowlist_maps_without_an_admin_role(self):
        self.assertEqual(staff_auth.postgres_role_for('abhishekgowdasmt@gmail.com'), 'owner')
        self.assertEqual(staff_auth.postgres_role_for('shreemaruthitravels5999@gmail.com'), 'owner')
        self.assertEqual(staff_auth.postgres_role_for('bhaskarbhaskarreddy9005@gmail.com'), 'staff')
        self.assertIsNone(staff_auth.postgres_role_for('veeruashwini01@gmail.com'))
        self.assertNotIn('admin', ('owner', 'staff', 'driver', 'client'))


if __name__ == '__main__':
    unittest.main()
