import os
import subprocess
import sys
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / 'backend'
INGEST_NAMES = ('RAC_INGEST_KEY', 'WEBSITE_API_KEY', 'OCR_INGEST_KEY')

os.environ['STAFF_TOKEN'] = 's' * 40
os.environ['RAC_JWT_SECRET'] = 'r' * 40
for _name in INGEST_NAMES:
    os.environ[_name] = ''

sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(BACKEND))

import backend.app as app_module
import rac_api
import rac_store
import staff_auth


def _import_result(module, extra_env, drop):
    env = os.environ.copy()
    for name in drop:
        env.pop(name, None)
    env.update(extra_env)
    script = (
        'import sys\n'
        f'sys.path.insert(0, {str(BACKEND)!r})\n'
        'try:\n'
        f'    import {module}\n'
        'except RuntimeError as exc:\n'
        '    sys.stdout.write(str(exc))\n'
        '    raise SystemExit(10)\n'
        'raise SystemExit(0)\n'
    )
    return subprocess.run(
        [sys.executable, '-c', script],
        env=env,
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


class SecretStartupTests(unittest.TestCase):
    def test_staff_token_required(self):
        result = _import_result('staff_auth', {'RAC_JWT_SECRET': 'r' * 40}, ('STAFF_TOKEN',))
        self.assertEqual(result.returncode, 10, result.stderr)
        self.assertIn('STAFF_TOKEN', result.stdout)
        self.assertIn('32', result.stdout)

    def test_staff_token_rejects_short_value(self):
        result = _import_result('staff_auth', {'STAFF_TOKEN': 'short', 'RAC_JWT_SECRET': 'r' * 40}, ())
        self.assertEqual(result.returncode, 10, result.stderr)
        self.assertIn('STAFF_TOKEN', result.stdout)

    def test_rac_jwt_secret_required_on_its_own(self):
        result = _import_result('rac_api', {'STAFF_TOKEN': 's' * 40}, ('RAC_JWT_SECRET',))
        self.assertEqual(result.returncode, 10, result.stderr)
        self.assertIn('RAC_JWT_SECRET', result.stdout)
        self.assertNotIn('STAFF_TOKEN must be set', result.stdout)


class Phase2SecurityTests(unittest.TestCase):
    def setUp(self):
        for name in INGEST_NAMES:
            os.environ[name] = ''
        self.client = app_module.app.test_client()
        self.booking_count = len(rac_store.all_rows('bookings'))

    def tearDown(self):
        for name in INGEST_NAMES:
            os.environ[name] = ''
        self.assertEqual(len(rac_store.all_rows('bookings')), self.booking_count)

    def _loopback(self, **kwargs):
        headers = {'Host': '127.0.0.1'}
        headers.update(kwargs.pop('headers', {}))
        kwargs['headers'] = headers
        kwargs['environ_overrides'] = {'REMOTE_ADDR': '127.0.0.1'}
        return kwargs

    def test_site_starts_without_ingest_key(self):
        home = self.client.get('/')
        self.assertLess(home.status_code, 500)
        me = self.client.get('/api/admin/me')
        self.assertEqual(me.status_code, 401)
        summary = self.client.get('/api/v1/dashboard/summary')
        self.assertEqual(summary.status_code, 401)

    def test_ingest_is_unavailable_without_a_key_even_on_loopback(self):
        posted = self.client.post('/api/v1/bookings/ingest', json={'bookings': []}, **self._loopback())
        looked = self.client.get(
            '/api/v1/bookings/ingest/lookup',
            query_string={'source_booking_id': 'phase2-security-probe'},
            **self._loopback(),
        )
        self.assertEqual(posted.status_code, 503)
        self.assertEqual(looked.status_code, 503)
        self.assertIn('not configured', posted.get_json()['message'])
        email = sorted(staff_auth.staff_emails())[0]
        self.client.set_cookie(staff_auth.STAFF_COOKIE, staff_auth.issue_token(email))
        with_cookie = self.client.post('/api/v1/bookings/ingest', json={'bookings': []})
        self.assertEqual(with_cookie.status_code, 503)

    def test_ingest_key_accepts_only_a_matching_header(self):
        os.environ['RAC_INGEST_KEY'] = 'k' * 40
        missing = self.client.post('/api/v1/bookings/ingest', json={'bookings': []}, **self._loopback())
        wrong = self.client.get(
            '/api/v1/bookings/ingest/lookup',
            query_string={'source_booking_id': 'phase2-security-probe'},
            **self._loopback(headers={'X-Ingest-Key': 'wrong-key'}),
        )
        accepted = self.client.get(
            '/api/v1/bookings/ingest/lookup',
            query_string={'source_booking_id': 'phase2-security-probe'},
            **self._loopback(headers={'X-Ingest-Key': 'k' * 40}),
        )
        empty = self.client.post(
            '/api/v1/bookings/ingest',
            json={'bookings': []},
            **self._loopback(headers={'X-Ingest-Key': 'k' * 40}),
        )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(accepted.status_code, 200)
        self.assertFalse(accepted.get_json()['found'])
        self.assertEqual(empty.status_code, 400)
        self.assertIn('No bookings', empty.get_json()['message'])

    def test_password_login_is_gone_and_staff_cookie_still_works(self):
        denied = self.client.post('/api/v1/auth/login', json={'email': 'person@example.com', 'password': 'not-a-password'})
        self.assertEqual(denied.status_code, 410)
        self.assertNotIn('token', denied.get_json())
        anonymous = self.client.get('/api/v1/auth/staff')
        self.assertEqual(anonymous.status_code, 401)

        email = sorted(staff_auth.staff_emails())[0]
        self.client.set_cookie(staff_auth.STAFF_COOKIE, staff_auth.issue_token(email))
        session = self.client.get('/api/v1/auth/staff')
        me = self.client.get('/api/admin/me')
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.get_json()['user']['email'], email)
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.get_json()['authenticated'])
        token = session.get_json()['token']
        with app_module.app.test_request_context(headers={'Authorization': 'Bearer ' + token}):
            loaded = rac_api._auth_user()
        self.assertEqual(loaded['email'], email)

    def test_local_login_stays_closed_when_google_is_configured(self):
        saved = {name: os.environ.get(name) for name in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET')}
        os.environ['GOOGLE_CLIENT_ID'] = 'test-client'
        os.environ['GOOGLE_CLIENT_SECRET'] = 'test-secret'
        try:
            response = self.client.post('/admin/local-login', data={'email': 'person@example.com'})
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        self.assertEqual(response.status_code, 403)

    def test_removed_password_surfaces_are_gone(self):
        app_jsx = (APP_ROOT / 'rac' / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
        server = (APP_ROOT / 'rac' / 'backend' / 'src' / 'server.js').read_text(encoding='utf-8')
        seed = (APP_ROOT / 'rac' / 'backend' / 'db' / 'seed.js').read_text(encoding='utf-8')
        start = (APP_ROOT / 'start.sh').read_text(encoding='utf-8')
        self.assertNotIn('/auth/login', app_jsx)
        self.assertNotIn('type="password"', app_jsx)
        self.assertIn('/auth/staff', app_jsx)
        self.assertNotIn('hashPassword', server)
        self.assertNotIn('hashPassword', seed)
        self.assertNotIn('admin@dispatch.local', server)
        self.assertNotIn('admin@dispatch.local', seed)
        self.assertIn('WEBSITE_API_URL="http://127.0.0.1:${PORT:-8080}/api/v1"', start)
        self.assertNotIn('OCR publishing is not configured', start)


if __name__ == '__main__':
    unittest.main()
