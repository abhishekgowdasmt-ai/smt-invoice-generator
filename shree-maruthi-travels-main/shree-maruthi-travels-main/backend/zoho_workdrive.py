"""Zoho WorkDrive (India) — store generated and uploaded SMT files."""
import json
import os
import time
from urllib.parse import quote

import requests

ZOHO_ACCOUNTS_URL = 'https://accounts.zoho.in/oauth/v2/token'
WORKDRIVE_API = 'https://www.zohoapis.in/workdrive/api/v1'
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.workdrive_refresh_token')
SCOPES = 'WorkDrive.files.CREATE,WorkDrive.files.READ,WorkDrive.files.UPDATE'

_access_token_cache = {'token': None, 'expires_at': 0}


def _client_id():
    return (os.environ.get('ZOHO_CLIENT_ID') or '').strip()


def _client_secret():
    return (os.environ.get('ZOHO_CLIENT_SECRET') or '').strip()


def _refresh_token():
    token = (os.environ.get('WORKDRIVE_REFRESH_TOKEN') or '').strip()
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
    os.environ['WORKDRIVE_REFRESH_TOKEN'] = token
    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as handle:
            handle.write(token)
    except OSError as exc:
        print(f'[WORKDRIVE] Could not write refresh token file: {exc}')


def folder_id():
    return (os.environ.get('WORKDRIVE_FOLDER_ID') or '').strip()


def configured():
    return bool(_client_id() and _client_secret() and _refresh_token() and folder_id())


def connection_status():
    return {
        'connected': configured(),
        'has_client_id': bool(_client_id()),
        'has_refresh_token': bool(_refresh_token()),
        'has_folder_id': bool(folder_id()),
        'folder_id': folder_id(),
        'scopes': SCOPES,
        'folder_url': f'https://workdrive.zoho.in/folder/{folder_id()}' if folder_id() else '',
    }


def exchange_grant_code(code):
    code = (code or '').strip()
    if not code:
        return {'success': False, 'message': 'Paste the WorkDrive grant code from the Zoho API console.'}
    if not _client_id() or not _client_secret():
        return {'success': False, 'message': 'ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET must be set first.'}
    try:
        resp = requests.post(ZOHO_ACCOUNTS_URL, data={
            'grant_type': 'authorization_code',
            'client_id': _client_id(),
            'client_secret': _client_secret(),
            'code': code,
        }, timeout=20)
        data = resp.json()
    except Exception as exc:
        return {'success': False, 'message': f'Token exchange failed: {exc}'}
    refresh = data.get('refresh_token')
    if not refresh:
        return {
            'success': False,
            'message': data.get('error_description') or data.get('error') or json.dumps(data),
        }
    _save_refresh_token(refresh)
    return {
        'success': True,
        'message': 'WorkDrive connected. Add WORKDRIVE_REFRESH_TOKEN on Render so it survives restarts.',
        'refresh_token': refresh,
    }


def _access_token():
    now = time.time()
    if _access_token_cache['token'] and _access_token_cache['expires_at'] > now + 60:
        return _access_token_cache['token']
    if not all([_client_id(), _client_secret(), _refresh_token()]):
        return None
    try:
        resp = requests.post(ZOHO_ACCOUNTS_URL, data={
            'refresh_token': _refresh_token(),
            'client_id': _client_id(),
            'client_secret': _client_secret(),
            'grant_type': 'refresh_token',
        }, timeout=15)
        data = resp.json()
    except Exception as exc:
        print(f'[WORKDRIVE] Token refresh error: {exc}')
        return None
    token = data.get('access_token')
    if not token:
        print(f'[WORKDRIVE] Token refresh failed: {data}')
        return None
    _access_token_cache['token'] = token
    _access_token_cache['expires_at'] = now + data.get('expires_in', 3600)
    return token


def upload_bytes(filename, content, parent=None):
    if not configured():
        return {'ok': False, 'skipped': True, 'message': 'WorkDrive is not configured'}
    token = _access_token()
    if not token:
        return {'ok': False, 'message': 'Could not refresh WorkDrive token'}
    name = os.path.basename(filename or 'file.bin') or 'file.bin'
    files = {
        'content': (name, content),
    }
    data = {
        'filename': name,
        'parent_id': parent or folder_id(),
        'override-name-exist': 'false',
    }
    try:
        resp = requests.post(
            f'{WORKDRIVE_API}/upload',
            headers={
                'Authorization': f'Zoho-oauthtoken {token}',
                'Accept': 'application/vnd.api+json',
            },
            data=data,
            files=files,
            timeout=90,
        )
        payload = resp.json()
    except Exception as exc:
        return {'ok': False, 'message': str(exc)}
    rows = payload.get('data') or []
    row = rows[0] if isinstance(rows, list) and rows else (rows if isinstance(rows, dict) else {})
    attrs = row.get('attributes') or row
    resource_id = attrs.get('resource_id') or row.get('id') or ''
    permalink = attrs.get('Permalink') or attrs.get('permalink') or ''
    if resource_id and not permalink:
        permalink = f'https://workdrive.zoho.in/file/{resource_id}'
    if resp.status_code >= 400 or not resource_id:
        return {
            'ok': False,
            'message': payload.get('message') or json.dumps(payload)[:400],
        }
    return {
        'ok': True,
        'id': resource_id,
        'name': attrs.get('FileName') or name,
        'permalink': permalink,
        'size': len(content) if content is not None else 0,
    }


def list_files(limit=100):
    if not configured():
        return []
    token = _access_token()
    if not token:
        return []
    try:
        resp = requests.get(
            f'{WORKDRIVE_API}/files/{quote(folder_id())}/files',
            headers={
                'Authorization': f'Zoho-oauthtoken {token}',
                'Accept': 'application/vnd.api+json',
            },
            params={'page[limit]': min(int(limit), 200)},
            timeout=30,
        )
        payload = resp.json()
    except Exception as exc:
        print(f'[WORKDRIVE] list error: {exc}')
        return []
    items = payload.get('data') or []
    out = []
    for item in items:
        attrs = item.get('attributes') or {}
        file_id = item.get('id') or attrs.get('resource_id') or ''
        if attrs.get('is_folder'):
            continue
        out.append({
            'id': file_id,
            'name': attrs.get('name') or attrs.get('display_attr_name') or '',
            'created_at': attrs.get('created_time') or '',
            'size': (attrs.get('storage_info') or {}).get('size') or '',
            'permalink': f'https://workdrive.zoho.in/file/{file_id}' if file_id else '',
        })
    return out
