"""Official Zoho WorkDrive API client. Never logs OAuth tokens."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import config
from logutil import log, redact

_access_cache = {'token': '', 'expires_at': 0}


class WorkDriveError(RuntimeError):
    pass


def configured():
    return bool(
        config.ZOHO_WORKDRIVE_ENABLED
        and config.ZOHO_WORKDRIVE_CLIENT_ID
        and config.ZOHO_WORKDRIVE_CLIENT_SECRET
        and config.ZOHO_WORKDRIVE_REFRESH_TOKEN
        and config.ZOHO_WORKDRIVE_FOLDER_ID
    )


def status():
    return {
        'enabled': config.ZOHO_WORKDRIVE_ENABLED,
        'configured': configured(),
        'has_client_id': bool(config.ZOHO_WORKDRIVE_CLIENT_ID),
        'has_client_secret': bool(config.ZOHO_WORKDRIVE_CLIENT_SECRET),
        'has_refresh_token': bool(config.ZOHO_WORKDRIVE_REFRESH_TOKEN),
        'has_folder_id': bool(config.ZOHO_WORKDRIVE_FOLDER_ID),
        'folder_id': config.ZOHO_WORKDRIVE_FOLDER_ID,
        'poll_seconds': config.WORKDRIVE_POLL_SECONDS,
        'required_scope': 'WorkDrive.files.READ',
    }


def _form(url, data):
    encoded = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=encoded, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise WorkDriveError(f'token HTTP {exc.code}') from exc
    except OSError as exc:
        raise WorkDriveError('token request failed') from exc


def clear_access_token():
    _access_cache['token'] = ''
    _access_cache['expires_at'] = 0


def access_token():
    now = time.time()
    if _access_cache['token'] and _access_cache['expires_at'] > now + 60:
        return _access_cache['token']
    if not (config.ZOHO_WORKDRIVE_CLIENT_ID and config.ZOHO_WORKDRIVE_CLIENT_SECRET and config.ZOHO_WORKDRIVE_REFRESH_TOKEN):
        raise WorkDriveError('WorkDrive OAuth is not configured')
    payload = _form(f'{config.ZOHO_WORKDRIVE_ACCOUNTS_URL}/oauth/v2/token', {
        'grant_type': 'refresh_token',
        'client_id': config.ZOHO_WORKDRIVE_CLIENT_ID,
        'client_secret': config.ZOHO_WORKDRIVE_CLIENT_SECRET,
        'refresh_token': config.ZOHO_WORKDRIVE_REFRESH_TOKEN,
    })
    token = payload.get('access_token')
    if not token:
        log.error('[WorkDrive] token refresh failed (no access token)')
        raise WorkDriveError('WorkDrive token refresh failed')
    _access_cache['token'] = token
    _access_cache['expires_at'] = now + int(payload.get('expires_in') or 3600)
    return token


def _headers():
    return {
        'Authorization': f'Zoho-oauthtoken {access_token()}',
        'Accept': 'application/vnd.api+json',
    }


def _open(url, headers, retry=True, timeout=40):
    req = urllib.request.Request(url, headers=headers, method='GET')
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if retry and exc.code == 401:
            clear_access_token()
            headers = dict(headers)
            headers['Authorization'] = f'Zoho-oauthtoken {access_token()}'
            return _open(url, headers, retry=False, timeout=timeout)
        raise WorkDriveError(f'WorkDrive HTTP {exc.code}') from exc


def _get_json(url, params=None):
    if params:
        url = f'{url}?{urllib.parse.urlencode(params)}'
    try:
        with _open(url, _headers()) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except WorkDriveError:
        raise
    except OSError as exc:
        raise WorkDriveError(redact(f'WorkDrive request failed: {exc}')) from exc


def file_metadata(file_id):
    payload = _get_json(f'{config.ZOHO_WORKDRIVE_API_BASE}/files/{urllib.parse.quote(file_id)}')
    return _normalize_file(payload.get('data') or {})


def list_folder_files(folder_id=None, limit=200):
    folder_id = folder_id or config.ZOHO_WORKDRIVE_FOLDER_ID
    if not folder_id:
        raise WorkDriveError('ZOHO_WORKDRIVE_FOLDER_ID is not set')
    rows = []
    offset = 0
    page_size = min(int(limit or 50), 50)
    while True:
        payload = _get_json(
            f'{config.ZOHO_WORKDRIVE_API_BASE}/files/{urllib.parse.quote(folder_id)}/files',
            {'page[limit]': str(page_size), 'page[offset]': str(offset)},
        )
        batch = payload.get('data') or []
        for item in batch:
            parsed = _normalize_file(item)
            if parsed:
                rows.append(parsed)
        if not batch or len(batch) < page_size:
            break
        offset += len(batch)
        if offset >= 2000:
            break
    return rows


def _normalize_file(item):
    if not isinstance(item, dict):
        return None
    attrs = item.get('attributes') or {}
    kind = str(attrs.get('type') or item.get('type') or '').lower()
    if attrs.get('is_folder') or kind == 'folder':
        return None
    file_id = item.get('id') or attrs.get('resource_id') or ''
    name = attrs.get('name') or attrs.get('display_attr_name') or attrs.get('FileName') or ''
    storage = attrs.get('storage_info') or {}
    size = storage.get('size_in_bytes') or storage.get('size') or 0
    try:
        size = int(size or 0)
    except (TypeError, ValueError):
        size = 0
    return {
        'id': str(file_id),
        'name': str(name),
        'ext': str(attrs.get('extn') or Path(name).suffix.lstrip('.')).lower(),
        'size': size,
        'modified': str(attrs.get('modified_time') or ''),
        'version': str(attrs.get('version') or attrs.get('modified_time') or size or ''),
        'status': str(attrs.get('status') or ''),
        'permalink': str(attrs.get('permalink') or attrs.get('Permalink') or ''),
    }


def download_file(file_id, dest_path):
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f'{config.ZOHO_WORKDRIVE_DOWNLOAD_BASE}/{urllib.parse.quote(file_id)}'
    try:
        with _open(url, {'Authorization': f'Zoho-oauthtoken {access_token()}'}, timeout=90) as resp:
            dest.write_bytes(resp.read())
        return dest
    except WorkDriveError:
        alt = f'{config.ZOHO_WORKDRIVE_API_BASE}/download/{urllib.parse.quote(file_id)}'
        with _open(alt, _headers(), timeout=90) as resp:
            dest.write_bytes(resp.read())
        return dest
