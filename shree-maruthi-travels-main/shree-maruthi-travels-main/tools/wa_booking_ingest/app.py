"""Booking OCR dashboard + workers. WhatsApp watcher stays off unless explicitly enabled."""
import hmac
import json
import threading
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import config
import db
from logutil import log
from pipeline import enqueue_local_image
from parser import salvage_payload
from publisher import publish_bookings
from service import start_background_loops
from validate import validate_booking
from workdrive import configured as workdrive_configured
from workdrive import status as workdrive_status
from workdrive_sync import extract_file_id_from_webhook, reconcile

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = config.MAX_IMAGE_BYTES * 40


def _local_request():
    addr = (request.remote_addr or '').strip()
    return addr in ('127.0.0.1', '::1', 'localhost')


def _ingest_key_ok():
    expected = (config.WEBSITE_API_KEY or '').strip()
    provided = (request.headers.get('X-Ingest-Key') or '').strip()
    return bool(expected) and bool(provided) and hmac.compare_digest(expected, provided)


def require_ingest_or_local(fn):
    from functools import wraps

    @wraps(fn)
    def wrapped(*args, **kwargs):
        if _ingest_key_ok() or _local_request():
            return fn(*args, **kwargs)
        if not config.WEBSITE_API_KEY and not config.INGEST_REQUIRE_KEY:
            return fn(*args, **kwargs)
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    return wrapped


@app.get('/')
def home():
    return render_template('index.html')


def _ocr_engine_name():
    try:
        from ocr_provider import get_provider
        return get_provider().name
    except Exception:
        return 'unknown'


def _counts():
    stats = db.get_stats()
    return {
        'whatsapp_watcher_enabled': config.WHATSAPP_WATCHER_ENABLED,
        'whatsapp': stats.get('whatsapp') or 'DISABLED',
        'uploaded': int(stats.get('ingest_total') or 0),
        'received': int(stats.get('images_received') or stats.get('ingest_total') or 0),
        'processed': int(stats.get('images_processed') or 0),
        'published': int(stats.get('ingest_PUBLISHED') or stats.get('bookings_created') or 0),
        'duplicates': int(stats.get('ingest_DUPLICATE_IMAGE') or 0) + int(stats.get('ingest_DUPLICATE_BOOKING') or 0),
        'duplicate_image': int(stats.get('ingest_DUPLICATE_IMAGE') or 0),
        'duplicate_booking': int(stats.get('ingest_DUPLICATE_BOOKING') or 0),
        'needs_review': int(stats.get('review_open') or stats.get('ingest_REVIEW_REQUIRED') or 0),
        'failed': int(stats.get('ingest_FAILED') or 0),
        'jobs_pending': int(stats.get('jobs_pending') or 0),
        'last_error': stats.get('last_error') or '',
        'source_website_upload': int(stats.get('source_website_upload') or 0),
        'source_zoho_workdrive': int(stats.get('source_zoho_workdrive') or 0),
        'today_received': int(stats.get('today_received') or 0),
        'today_published': int(stats.get('today_PUBLISHED') or 0),
        'today_duplicates': int(stats.get('today_DUPLICATE_IMAGE') or 0) + int(stats.get('today_DUPLICATE_BOOKING') or 0),
        'today_review': int(stats.get('today_REVIEW_REQUIRED') or 0),
        'today_failed': int(stats.get('today_FAILED') or 0),
        'workdrive': workdrive_status(),
        'ocr_engine': _ocr_engine_name(),
        'gemini_configured': bool(config.GEMINI_API_KEY),
    }


@app.get('/api/status')
@require_ingest_or_local
def api_status():
    return jsonify(_counts())


@app.get('/api/bookings')
@require_ingest_or_local
def api_bookings():
    return jsonify({'success': True, 'data': db.list_bookings(80)})


@app.get('/api/ingest')
@require_ingest_or_local
def api_ingest():
    return jsonify({'success': True, 'data': db.list_ingest_records(80)})


@app.get('/api/review')
@require_ingest_or_local
def api_review():
    rows = db.list_review(True)
    for row in rows:
        try:
            payload = json.loads(row.get('payload') or '{}')
        except json.JSONDecodeError:
            payload = {'raw': row.get('payload')}
        if isinstance(payload, dict):
            payload = salvage_payload(payload)
        row['payload'] = payload
    return jsonify({'success': True, 'data': rows})


@app.post('/api/review/<int:review_id>/approve')
@require_ingest_or_local
def api_approve(review_id):
    payload = salvage_payload(request.get_json(silent=True) or {})
    payload['confidence'] = 1
    ok, reasons, cleaned = validate_booking(payload, staff_override=True)
    if not ok:
        return jsonify({'success': False, 'message': '; '.join(reasons)}), 400
    publish_bookings([cleaned], source=payload.get('source') or db.SOURCE_WEBSITE)
    db.upsert_booking(cleaned)
    db.resolve_review(review_id, 'approved', cleaned)
    record_id = payload.get('ingest_record_id')
    if record_id:
        db.update_ingest_record(
            record_id,
            status=db.STATUS_PUBLISHED,
            booking_id=cleaned.get('booking_id') or '',
            booking_date=cleaned.get('trip_date') or '',
            processed_at=db.now(),
            error='',
        )
    return jsonify({'success': True})


@app.post('/api/review/<int:review_id>/edit')
@require_ingest_or_local
def api_edit(review_id):
    payload = request.get_json(silent=True) or {}
    row = db.get_review(review_id) or {}
    if not row:
        return jsonify({'success': False, 'message': 'Review item not found'}), 404
    try:
        stored = json.loads(row.get('payload') or '{}')
    except json.JSONDecodeError:
        stored = {}
    stored.update(payload)
    db.save_review_payload(review_id, stored)
    record_id = stored.get('ingest_record_id')
    if record_id:
        db.update_ingest_record(
            record_id,
            booking_id=stored.get('booking_id') or '',
            booking_date=stored.get('trip_date') or '',
            payload=stored,
        )
    return jsonify({'success': True, 'data': stored})


@app.post('/api/review/<int:review_id>/reject')
@require_ingest_or_local
def api_reject(review_id):
    payload = request.get_json(silent=True) or {}
    db.resolve_review(review_id, 'rejected')
    record_id = payload.get('ingest_record_id')
    if not record_id:
        row = db.get_review(review_id) or {}
        try:
            stored = json.loads(row.get('payload') or '{}')
            record_id = stored.get('ingest_record_id')
        except json.JSONDecodeError:
            record_id = None
    if record_id:
        db.update_ingest_record(record_id, status=db.STATUS_FAILED, error='rejected', processed_at=db.now())
    return jsonify({'success': True})


@app.post('/api/upload')
@require_ingest_or_local
def api_upload():
    files = request.files.getlist('images') or request.files.getlist('files')
    if not files:
        uploaded = request.files.get('image') or request.files.get('file')
        files = [uploaded] if uploaded else []
    if not files:
        return jsonify({'success': False, 'message': 'No images uploaded'}), 400
    saved = []
    for handle in files:
        name = Path(handle.filename or '').name
        if not name or not config.is_allowed_image_name(name):
            saved.append({'filename': name or '(unnamed)', 'status': 'ignored', 'reason': 'not an allowed image type'})
            continue
        unique = f'{uuid.uuid4().hex[:10]}_{name}'
        dest = config.INCOMING_DIR / unique
        handle.save(dest)
        if dest.stat().st_size > config.MAX_IMAGE_BYTES:
            dest.unlink(missing_ok=True)
            saved.append({'filename': name, 'status': 'FAILED', 'reason': 'file too large'})
            continue
        record_id = enqueue_local_image(
            dest,
            source=db.SOURCE_WEBSITE,
            source_file_id=f'upload:{uuid.uuid4()}',
            source_file_name=name,
        )
        saved.append({'filename': name, 'status': db.STATUS_RECEIVED, 'id': record_id})
    return jsonify({'success': True, 'data': saved, 'counts': _counts()})


@app.post('/api/ingest/<int:record_id>/retry')
@require_ingest_or_local
def api_retry(record_id):
    record = db.get_ingest_record(record_id)
    if not record:
        return jsonify({'success': False, 'message': 'Record not found'}), 404
    if record.get('status') not in (db.STATUS_FAILED, db.STATUS_RECEIVED):
        return jsonify({'success': False, 'message': 'Only FAILED or RECEIVED records can be retried'}), 400
    db.update_ingest_record(record_id, status=db.STATUS_RECEIVED, error='', processed_at='')
    db.enqueue_job('ocr_image', {'ingest_record_id': record_id, 'image_path': record.get('image_path')})
    return jsonify({'success': True})


@app.post('/api/v1/integrations/zoho/workdrive/webhook')
@app.post('/api/integrations/zoho/workdrive/webhook')
def api_workdrive_webhook():
    payload = request.get_json(silent=True) or {}
    file_id = extract_file_id_from_webhook(payload)
    if not file_id:
        return jsonify({'success': True, 'enqueued': False, 'message': 'no file id'}), 200
    db.enqueue_job('workdrive_file', {'file_id': file_id})
    return jsonify({'success': True, 'enqueued': True, 'file_id': file_id})


@app.post('/api/workdrive/reconcile')
@require_ingest_or_local
def api_workdrive_reconcile():
    if not workdrive_configured():
        return jsonify({'success': False, 'message': 'WorkDrive OAuth or folder is not configured'}), 400
    result = reconcile()
    return jsonify({'success': True, **result})


@app.get('/api/workdrive/status')
def api_workdrive_status():
    return jsonify({'success': True, **workdrive_status()})


@app.get('/images/<path:filename>')
@require_ingest_or_local
def images(filename):
    for folder in (config.INCOMING_DIR, config.REVIEW_DIR, config.PROCESSED_DIR, config.FAILED_DIR):
        candidate = folder / filename
        if candidate.is_file():
            return send_from_directory(folder, filename)
    abort(404)


def watcher_loop():
    from session import DiagnosticStop
    from watcher import watch_forever
    import asyncio
    try:
        asyncio.run(watch_forever())
    except DiagnosticStop as exc:
        log.error('[WhatsApp] %s', exc)
        db.set_stat('whatsapp', 'DATABASE_ERROR')
        db.set_stat('last_error', 'DATABASE ERROR DETECTED; ingest stopped. See ingest.log')
        log.error('[WhatsApp] Watcher thread stopped. Dashboard remains up. No profile reset.')
    except Exception as exc:
        log.error('watcher crashed %s', exc)
        db.set_stat('whatsapp', 'DISCONNECTED')
        db.set_stat('last_error', str(exc)[:300])


def main():
    start_background_loops()
    if config.WHATSAPP_WATCHER_ENABLED:
        threading.Thread(target=watcher_loop, daemon=True, name='wa-watcher').start()
        log.info('[WhatsApp] watcher enabled (deprecated)')
    log.info('dashboard http://%s:%s', config.DASHBOARD_HOST, config.DASHBOARD_PORT)
    app.run(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
