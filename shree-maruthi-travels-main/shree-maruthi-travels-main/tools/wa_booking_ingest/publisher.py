"""Publish validated bookings to the existing RAC website API."""
import json
import urllib.error
import urllib.request

import config
from logutil import log


def publish_bookings(rows):
    if not rows:
        return {'created': [], 'updated': [], 'errors': []}
    if not config.WEBSITE_API_KEY:
        raise RuntimeError('WEBSITE_API_KEY / RAC_INGEST_KEY is not set')
    url = f'{config.WEBSITE_API_URL}/bookings/ingest'
    body = json.dumps({'bookings': rows, 'source': 'whatsapp-group'}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'X-Ingest-Key': config.WEBSITE_API_KEY,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:400]
        log.error('API failure %s %s', exc.code, detail)
        raise RuntimeError(f'Website API {exc.code}: {detail}') from exc
    except OSError as exc:
        log.error('API unavailable %s', exc)
        raise RuntimeError(f'Website API unavailable: {exc}') from exc
    if not payload.get('success'):
        raise RuntimeError(payload.get('message') or 'Website API rejected bookings')
    log.info(
        'API success created=%s updated=%s errors=%s',
        payload.get('created_count'),
        payload.get('updated_count'),
        len(payload.get('errors') or []),
    )
    return payload
