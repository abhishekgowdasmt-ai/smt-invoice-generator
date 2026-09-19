"""Publish validated bookings to the existing RAC website API."""
import json
import urllib.error
import urllib.parse
import urllib.request

import config
from logutil import log, redact


def _headers():
    return {
        'Content-Type': 'application/json',
        'X-Ingest-Key': config.WEBSITE_API_KEY,
    }


def lookup_website_booking(booking_id):
    """Level 3: ask the RAC website if this booking ID already exists. Never logs tokens."""
    if not booking_id:
        return {'found': False}
    if not config.WEBSITE_API_KEY:
        return {'found': False, 'skipped': True}
    query = urllib.parse.urlencode({'source_booking_id': booking_id})
    url = f'{config.WEBSITE_API_URL}/bookings/ingest/lookup?{query}'
    req = urllib.request.Request(url, headers=_headers(), method='GET')
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {'found': False}
        log.error('API lookup failure %s', exc.code)
        return {'found': False, 'error': str(exc.code)}
    except OSError as exc:
        log.error('API lookup unavailable %s', redact(exc))
        return {'found': False, 'error': 'unavailable'}
    if not payload.get('success'):
        return {'found': False}
    return {
        'found': bool(payload.get('found')),
        'trip_date': payload.get('trip_date') or '',
        'booking_id': payload.get('booking_id') or booking_id,
        'source_booking_id': payload.get('source_booking_id') or booking_id,
    }


def publish_bookings(rows, source='website_upload'):
    if not rows:
        return {'created': [], 'updated': [], 'duplicates': [], 'conflicts': [], 'errors': []}
    if not config.WEBSITE_API_KEY:
        raise RuntimeError('WEBSITE_API_KEY / RAC_INGEST_KEY is not set')
    url = f'{config.WEBSITE_API_URL}/bookings/ingest'
    body = json.dumps({
        'bookings': rows,
        'source': source or 'website_upload',
    }).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=_headers(), method='POST')
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = redact(exc.read().decode('utf-8', errors='replace')[:400])
        log.error('API failure %s %s', exc.code, detail)
        raise RuntimeError(f'Website API {exc.code}: {detail}') from exc
    except OSError as exc:
        log.error('API unavailable %s', redact(exc))
        raise RuntimeError(f'Website API unavailable: {redact(exc)}') from exc
    if not payload.get('success'):
        raise RuntimeError(payload.get('message') or 'Website API rejected bookings')
    log.info(
        '[Publisher] Success created=%s duplicates=%s conflicts=%s errors=%s',
        payload.get('created_count') or len(payload.get('created') or []),
        len(payload.get('duplicates') or payload.get('updated') or []),
        len(payload.get('conflicts') or []),
        len(payload.get('errors') or []),
    )
    payload.setdefault('duplicates', payload.get('updated') or [])
    payload.setdefault('conflicts', [])
    return payload
