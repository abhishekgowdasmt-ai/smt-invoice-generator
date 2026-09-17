"""Local dashboard + background WhatsApp ingest workers. Binds to localhost only."""
import asyncio
import json
import threading
import time

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import config
import db
from logutil import log
from publisher import publish_bookings
from validate import validate_booking
from worker import run_once

app = Flask(__name__, template_folder='templates', static_folder='static')


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/api/status')
def api_status():
    stats = db.get_stats()
    return jsonify({
        'whatsapp': stats.get('whatsapp') or 'DISCONNECTED',
        'target_group': stats.get('target_group') or 'NOT FOUND',
        'group_name': config.TARGET_WHATSAPP_GROUP,
        'last_image': stats.get('last_image') or '',
        'images_processed': int(stats.get('images_processed') or 0),
        'bookings_created': int(stats.get('bookings_created') or 0),
        'bookings_updated': int(stats.get('bookings_updated') or 0),
        'duplicates': int(stats.get('duplicates') or 0),
        'review_required': int(stats.get('review_open') or 0),
        'jobs_pending': int(stats.get('jobs_pending') or 0),
        'last_error': stats.get('last_error') or '',
    })


@app.get('/api/bookings')
def api_bookings():
    return jsonify({'success': True, 'data': db.list_bookings(80)})


@app.get('/api/review')
def api_review():
    rows = db.list_review(True)
    for row in rows:
        try:
            row['payload'] = json.loads(row.get('payload') or '{}')
        except json.JSONDecodeError:
            row['payload'] = {'raw': row.get('payload')}
    return jsonify({'success': True, 'data': rows})


@app.post('/api/review/<int:review_id>/approve')
def api_approve(review_id):
    payload = request.get_json(silent=True) or {}
    ok, reasons, cleaned = validate_booking(payload)
    if not ok:
        return jsonify({'success': False, 'message': '; '.join(reasons)}), 400
    publish_bookings([cleaned])
    db.upsert_booking(cleaned)
    db.resolve_review(review_id, 'approved', cleaned)
    return jsonify({'success': True})


@app.post('/api/review/<int:review_id>/reject')
def api_reject(review_id):
    db.resolve_review(review_id, 'rejected')
    return jsonify({'success': True})


@app.get('/images/<path:filename>')
def images(filename):
    for folder in (config.INCOMING_DIR, config.REVIEW_DIR, config.PROCESSED_DIR, config.FAILED_DIR):
        candidate = folder / filename
        if candidate.is_file():
            return send_from_directory(folder, filename)
    abort(404)


def worker_loop():
    while True:
        try:
            run_once()
        except Exception as exc:
            log.error('worker loop %s', exc)
        time.sleep(2)


def watcher_loop():
    from watcher import watch_forever
    while True:
        try:
            asyncio.run(watch_forever())
        except Exception as exc:
            log.error('watcher crashed %s', exc)
            db.set_stat('whatsapp', 'DISCONNECTED')
            db.set_stat('last_error', str(exc)[:300])
            time.sleep(8)


def main():
    config.ensure_dirs()
    db.connect().close()
    db.set_stat('whatsapp', db.get_stats().get('whatsapp') or 'DISCONNECTED')
    threading.Thread(target=worker_loop, daemon=True, name='ocr-worker').start()
    threading.Thread(target=watcher_loop, daemon=True, name='wa-watcher').start()
    log.info('dashboard http://%s:%s', config.DASHBOARD_HOST, config.DASHBOARD_PORT)
    app.run(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
