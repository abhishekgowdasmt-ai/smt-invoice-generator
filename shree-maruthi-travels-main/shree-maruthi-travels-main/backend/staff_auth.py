"""Staff Google Sign-In and role allowlists."""
import os
from urllib.parse import urlencode

import requests
from flask import request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

STAFF_COOKIE = 'smt_staff'
STAFF_TOKEN = os.environ.get('STAFF_TOKEN') or 'smt-session-token'
_SERIALIZER = URLSafeTimedSerializer(STAFF_TOKEN, salt='smt-staff-v2')

DEFAULT_STAFF = (
    'abhishekgowdasmt@gmail.com',
    'shreemaruthitravels5999@gmail.com',
    'veeruashwini01@gmail.com',
    'bhaskarbhaskarreddy9005@gmail.com',
)
DEFAULT_OD = (
    'abhishekgowdasmt@gmail.com',
    'shreemaruthitravels5999@gmail.com',
)


def _split_emails(raw, fallback):
    text = (raw or '').strip()
    if not text:
        return {item.lower() for item in fallback}
    return {part.strip().lower() for part in text.split(',') if part.strip()}


def staff_emails():
    extra = _split_emails(os.environ.get('STAFF_EXTRA_EMAILS'), ())
    return _split_emails(os.environ.get('STAFF_EMAILS'), DEFAULT_STAFF) | extra


def od_emails():
    return _split_emails(os.environ.get('OD_EMAILS'), DEFAULT_OD)


def google_configured():
    return bool((os.environ.get('GOOGLE_CLIENT_ID') or '').strip() and (os.environ.get('GOOGLE_CLIENT_SECRET') or '').strip())


def role_for(email):
    email = (email or '').strip().lower()
    if email in od_emails():
        return 'od'
    if email in staff_emails():
        return 'staff'
    return None


def issue_token(email):
    email = (email or '').strip().lower()
    role = role_for(email)
    if not role:
        return None
    return _SERIALIZER.dumps({'email': email, 'role': role})


def pin_staff_token():
    return _SERIALIZER.dumps({'email': 'pin@local', 'role': 'staff'})


def dump_state(payload):
    return _SERIALIZER.dumps(payload)


def load_state(value, max_age=600):
    return _SERIALIZER.loads(value or '', max_age=max_age)


def read_token(token):
    if not token:
        return None
    if token == STAFF_TOKEN:
        return {'email': 'pin@local', 'role': 'staff', 'legacy': True}
    try:
        data = _SERIALIZER.loads(token, max_age=60 * 60 * 12)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    email = str(data.get('email') or '').strip().lower()
    if email == 'pin@local':
        return {'email': email, 'role': 'staff', 'legacy': True}
    role = role_for(email)
    if not role:
        return None
    return {'email': email, 'role': role, 'legacy': False}


def token_from_request():
    cookie = request.cookies.get(STAFF_COOKIE)
    if cookie:
        return cookie
    header = request.headers.get('Authorization') or ''
    if header.startswith('Bearer '):
        return header.split(' ', 1)[1].strip()
    return None


def current_staff():
    return read_token(token_from_request())


def can_od(staff=None):
    staff = staff or current_staff()
    return bool(staff and staff.get('role') == 'od')


def google_authorize_url(redirect_uri, state):
    params = {
        'client_id': os.environ.get('GOOGLE_CLIENT_ID', '').strip(),
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'online',
        'prompt': 'select_account',
        'state': state,
    }
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(params)


def google_exchange(code, redirect_uri):
    resp = requests.post('https://oauth2.googleapis.com/token', data={
        'code': code,
        'client_id': os.environ.get('GOOGLE_CLIENT_ID', '').strip(),
        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET', '').strip(),
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }, timeout=20)
    data = resp.json()
    access = data.get('access_token')
    if not access:
        return None, data.get('error_description') or data.get('error') or 'Google token exchange failed'
    info = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {access}'},
        timeout=20,
    ).json()
    email = str(info.get('email') or '').strip().lower()
    if not email or not info.get('verified_email', True):
        return None, 'Google did not return a verified email'
    return email, None
