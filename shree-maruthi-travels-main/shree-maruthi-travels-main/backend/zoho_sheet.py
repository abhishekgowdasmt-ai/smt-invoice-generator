"""
zoho_sheet.py — Zoho Sheet API for SMT inquiries + RAC dispatch.
OAuth2 refresh-token flow against the India datacenter (sheet.zoho.in).
"""
import json
import os
import time
from datetime import datetime

import requests

DEFAULT_SPREADSHEET_ID = 'wx4flb9932735a31d4f8ba038c6ec4a69c850'
ZOHO_ACCOUNTS_URL = 'https://accounts.zoho.in/oauth/v2/token'
ZOHO_SHEET_API_URL = 'https://sheet.zoho.in/api/v2'
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.zoho_refresh_token')
APP_WORKSHEETS = (
    'Sheet1',
    'Enquiries',
    'RAC_Drivers',
    'RAC_Bookings',
    'RAC_Assignments',
    'RAC_Uploads',
    'RAC_Messages',
)

_access_token_cache = {'token': None, 'expires_at': 0}


def _client_id():
    return (os.environ.get('ZOHO_CLIENT_ID') or '').strip()


def _client_secret():
    return (os.environ.get('ZOHO_CLIENT_SECRET') or '').strip()


def _spreadsheet_id():
    return (os.environ.get('ZOHO_SPREADSHEET_ID') or DEFAULT_SPREADSHEET_ID).strip()


def _refresh_token():
    token = (os.environ.get('ZOHO_REFRESH_TOKEN') or '').strip()
    if token:
        return token
    try:
        with open(TOKEN_FILE, encoding='utf-8') as handle:
            return handle.read().strip()
    except OSError:
        return ''


def _save_refresh_token(token):
    token = (token or '').strip()
    if not token:
        return
    os.environ['ZOHO_REFRESH_TOKEN'] = token
    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as handle:
            handle.write(token)
    except OSError as exc:
        print(f'[ZOHO] Could not write refresh token file: {exc}')


def zoho_configured():
    return all([_client_id(), _client_secret(), _refresh_token(), _spreadsheet_id()])


def connection_status():
    return {
        'connected': zoho_configured(),
        'has_client_id': bool(_client_id()),
        'has_client_secret': bool(_client_secret()),
        'has_refresh_token': bool(_refresh_token()),
        'spreadsheet_id': _spreadsheet_id(),
        'sheet_url': f'https://sheet.zoho.in/sheet/open/{_spreadsheet_id()}',
    }


def exchange_grant_code(code):
    """Turn a Zoho self-client grant code into a refresh token."""
    code = (code or '').strip()
    if not code:
        return {'success': False, 'message': 'Paste the grant code from the Zoho API console.'}
    if not _client_id() or not _client_secret():
        return {'success': False, 'message': 'ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET must be set first.'}
    payload = {
        'grant_type': 'authorization_code',
        'client_id': _client_id(),
        'client_secret': _client_secret(),
        'code': code,
    }
    redirect = (os.environ.get('ZOHO_REDIRECT_URI') or '').strip()
    if redirect:
        payload['redirect_uri'] = redirect
    try:
        resp = requests.post(ZOHO_ACCOUNTS_URL, data=payload, timeout=20)
        data = resp.json()
    except Exception as exc:
        return {'success': False, 'message': f'Token exchange failed: {exc}'}
    refresh = data.get('refresh_token')
    access = data.get('access_token')
    if not refresh:
        return {
            'success': False,
            'message': data.get('error_description') or data.get('error') or json.dumps(data),
        }
    _save_refresh_token(refresh)
    if access:
        _access_token_cache['token'] = access
        _access_token_cache['expires_at'] = time.time() + data.get('expires_in', 3600)
    return {
        'success': True,
        'message': 'Zoho connected. Copy the refresh token into Render so it survives restarts.',
        'refresh_token': refresh,
    }


def _get_access_token():
    now = time.time()
    if _access_token_cache['token'] and _access_token_cache['expires_at'] > now + 60:
        return _access_token_cache['token']
    if not all([_client_id(), _client_secret(), _refresh_token()]):
        print('[ZOHO] Missing API credentials — skipping Zoho Sheet push')
        return None
    try:
        resp = requests.post(ZOHO_ACCOUNTS_URL, data={
            'refresh_token': _refresh_token(),
            'client_id': _client_id(),
            'client_secret': _client_secret(),
            'grant_type': 'refresh_token',
        }, timeout=10)
        data = resp.json()
        if 'access_token' in data:
            _access_token_cache['token'] = data['access_token']
            _access_token_cache['expires_at'] = now + data.get('expires_in', 3600)
            print('[ZOHO] Access token refreshed successfully')
            return data['access_token']
        print(f'[ZOHO] Token refresh failed: {data}')
        return None
    except Exception as exc:
        print(f'[ZOHO] Token refresh error: {exc}')
        return None


def inquiry_worksheet_name():
    configured = (os.environ.get('ZOHO_INQUIRY_SHEET') or '').strip()
    names = list_worksheets()
    wanted = [configured, 'Enquiries', 'enquiries', 'Inquiries', 'Sheet1']
    lower = {name.strip().lower(): name.strip() for name in names}
    for name in wanted:
        if name and name.lower() in lower:
            return lower[name.lower()]
    return configured or 'Enquiries'


def append_inquiry_to_sheet(inquiry_data):
    token = _get_access_token()
    if not token:
        print('[ZOHO] No token available — falling back to local logging')
        return False

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row_data = [
        timestamp,
        inquiry_data.get('name', ''),
        inquiry_data.get('phone', ''),
        inquiry_data.get('email', ''),
        inquiry_data.get('service_type', ''),
        inquiry_data.get('company', ''),
        str(inquiry_data.get('employee_count', 0)),
        inquiry_data.get('details', ''),
        'New',
    ]
    url = f'{ZOHO_SHEET_API_URL}/{_spreadsheet_id()}'
    payload = {
        'method': 'worksheet.records.add',
        'worksheet_name': inquiry_worksheet_name(),
        'header_row': 1,
        'json_data': json.dumps([{
            'Timestamp': row_data[0],
            'Name': row_data[1],
            'Phone': row_data[2],
            'Email': row_data[3],
            'Service Type': row_data[4],
            'Company': row_data[5],
            'Employee Count': row_data[6],
            'Details': row_data[7],
            'Status': row_data[8],
        }]),
    }
    try:
        resp = requests.post(url, headers={'Authorization': f'Zoho-oauthtoken {token}'}, data=payload, timeout=15)
        result = resp.json()
        if resp.status_code == 200 and result.get('status') == 'success':
            print(f'[ZOHO] [SUCCESS] Inquiry from {row_data[1]} added to Zoho Sheet')
            return True
        print(f'[ZOHO] [WARN] API response: {result}')
        return False
    except Exception as exc:
        print(f'[ZOHO] [ERROR] Error pushing to sheet: {exc}')
        return False


def _sheet_url():
    return f'{ZOHO_SHEET_API_URL}/{_spreadsheet_id()}'


def _sheet_headers(token):
    return {
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
    }


def _sheet_call(payload, http='post', timeout=45):
    token = _get_access_token()
    if not token:
        return None
    try:
        if http == 'get':
            resp = requests.get(_sheet_url(), headers=_sheet_headers(token), params=payload, timeout=timeout)
        else:
            resp = requests.post(_sheet_url(), headers=_sheet_headers(token), data=payload, timeout=timeout)
        return resp.json()
    except Exception as exc:
        print(f'[ZOHO] Sheet call failed: {exc}')
        return None


def list_worksheets():
    result = _sheet_call({'method': 'worksheet.list'})
    names = []
    if not result:
        return names
    for key in ('worksheet_names', 'worksheets', 'sheet_names'):
        value = result.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict):
                    names.append(item.get('worksheet_name') or item.get('sheet_name') or item.get('name') or '')
    return [name for name in names if name]


def resolve_worksheet(worksheet_name):
    wanted = (worksheet_name or '').strip().lower()
    if not wanted:
        return worksheet_name
    for name in list_worksheets():
        if name.strip().lower() == wanted:
            return name
    return worksheet_name


def ensure_worksheet(worksheet_name):
    actual = resolve_worksheet(worksheet_name)
    if (actual or '').strip().lower() == (worksheet_name or '').strip().lower() and actual in list_worksheets():
        return True
    existing = {name.strip().lower(): name for name in list_worksheets()}
    if (worksheet_name or '').strip().lower() in existing:
        return True
    result = _sheet_call({
        'method': 'worksheet.create',
        'new_sheet_name': worksheet_name,
    })
    if result and result.get('status') == 'success':
        print(f'[ZOHO] Created worksheet {worksheet_name}')
        return True
    message = str(result).lower() if result else ''
    if 'already' in message or 'exist' in message:
        return True
    if result:
        print(f'[ZOHO] worksheet.create {worksheet_name}: {result}')
    return False


def ensure_app_worksheets():
    if not zoho_configured():
        return False
    ok = True
    for name in APP_WORKSHEETS:
        if not ensure_worksheet(name):
            ok = False
    return ok


def ensure_header_row(worksheet_name, columns):
    columns = [str(col) for col in columns if col]
    if not columns:
        return False
    result = _sheet_call({
        'method': 'range.content.set',
        'worksheet_name': worksheet_name,
        'start_row': 1,
        'start_column': 1,
        'data': ','.join(columns),
    })
    if result and result.get('status') == 'success':
        return True
    result = _sheet_call({
        'method': 'cell.content.set',
        'worksheet_name': worksheet_name,
        'row': 1,
        'column': 1,
        'content': columns[0],
    })
    if not result or result.get('status') != 'success':
        print(f'[ZOHO] header {worksheet_name}: {result}')
        return False
    for index, name in enumerate(columns[1:], start=2):
        _sheet_call({
            'method': 'cell.content.set',
            'worksheet_name': worksheet_name,
            'row': 1,
            'column': index,
            'content': name,
        })
    return True


def fetch_records(worksheet_name):
    if not zoho_configured():
        return None
    ensure_worksheet(worksheet_name)
    actual = resolve_worksheet(worksheet_name)
    result = _sheet_call({
        'method': 'worksheet.records.fetch',
        'worksheet_name': actual,
        'header_row': 1,
    }, http='get', timeout=90)
    if result and result.get('error_code') == 2884:
        return []
    if not result or result.get('status') not in (None, 'success'):
        if result:
            print(f'[ZOHO] fetch {worksheet_name}: {result}')
        return None
    records = result.get('records') or result.get('data') or []
    return records if isinstance(records, list) else []


def add_records(worksheet_name, rows):
    if not rows or not zoho_configured():
        return False
    ensure_worksheet(worksheet_name)
    actual = resolve_worksheet(worksheet_name)
    result = _sheet_call({
        'method': 'worksheet.records.add',
        'worksheet_name': actual,
        'header_row': 1,
        'json_data': json.dumps(rows),
    }, timeout=60)
    if result and result.get('error_code') == 2884:
        ensure_header_row(actual, list(rows[0].keys()))
        result = _sheet_call({
            'method': 'worksheet.records.add',
            'worksheet_name': actual,
            'header_row': 1,
            'json_data': json.dumps(rows),
        }, timeout=60)
    ok = bool(result) and result.get('status') == 'success'
    if not ok:
        print(f'[ZOHO] add {worksheet_name}: {result}')
    return ok


def update_record(worksheet_name, id_field, id_value, data):
    if not zoho_configured():
        return False
    ensure_worksheet(worksheet_name)
    actual = resolve_worksheet(worksheet_name)
    result = _sheet_call({
        'method': 'worksheet.records.update',
        'worksheet_name': actual,
        'header_row': 1,
        'criteria': f'("{id_field}"="{id_value}")',
        'data': json.dumps(data),
    })
    ok = bool(result) and result.get('status') == 'success'
    if not ok:
        print(f'[ZOHO] update {worksheet_name}: {result}')
    return ok


def test_connection():
    token = _get_access_token()
    if not token:
        return {'status': 'error', 'message': 'Could not obtain access token'}
    try:
        resp = requests.get(_sheet_url(), headers={
            'Authorization': f'Zoho-oauthtoken {token}',
        }, params={
            'method': 'worksheet.records.fetch',
            'worksheet_name': 'Sheet1',
            'header_row': 1,
            'count': 1,
        }, timeout=10)
        return {'status': 'success', 'response': resp.json()}
    except Exception as exc:
        return {'status': 'error', 'message': str(exc)}
