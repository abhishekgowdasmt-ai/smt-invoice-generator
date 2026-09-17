"""OCR + validate + publish worker. Reads from the SQLite job queue."""
import json
import shutil
from pathlib import Path

import config
import db
from logutil import log
from ocr_provider import extract_bookings
from publisher import publish_bookings
from validate import validate_booking


def _copy(image_path, folder):
    source = Path(image_path)
    if not source.exists():
        return str(source)
    target = Path(folder) / source.name
    shutil.copy2(source, target)
    return str(target)


def process_image_job(payload):
    image_path = Path(payload['image_path'])
    message_id = payload.get('message_id') or ''
    group_name = payload.get('group_name') or ''
    log.info('OCR started %s', image_path.name)
    text, rows = extract_bookings(image_path, source_message_id=message_id)
    log.info('OCR completed rows=%s chars=%s', len(rows), len(text or ''))
    if not rows:
        db.add_review({'text': (text or '')[:4000], 'message_id': message_id}, 'no booking rows extracted', str(image_path))
        db.bump('review_required')
        db.mark_message(message_id, group_name, _copy(image_path, config.REVIEW_DIR), 'review', 'no rows')
        return
    ready = []
    for row in rows:
        ok, reasons, cleaned = validate_booking(row)
        if not ok:
            db.add_review(cleaned, '; '.join(reasons), str(image_path))
            db.bump('review_required')
            log.info('validation failed %s %s', cleaned.get('booking_id'), reasons)
            continue
        ready.append(cleaned)
    if not ready:
        db.mark_message(message_id, group_name, _copy(image_path, config.REVIEW_DIR), 'review', 'all rows need review')
        return
    result = publish_bookings(ready)
    for row in ready:
        action = db.upsert_booking(row)
        if action == 'created':
            db.bump('bookings_created')
            log.info('booking inserted %s', row['booking_id'])
        else:
            db.bump('bookings_updated')
            log.info('booking updated %s', row['booking_id'])
    for booking_id in result.get('updated') or []:
        db.bump('duplicates')
        log.info('duplicate detected %s', booking_id)
    db.mark_message(message_id, group_name, _copy(image_path, config.PROCESSED_DIR), 'done', '')
    db.bump('images_processed')


def process_publish_job(payload):
    rows = payload.get('bookings') or []
    publish_bookings(rows)
    for row in rows:
        action = db.upsert_booking(row)
        db.bump('bookings_created' if action == 'created' else 'bookings_updated')


def run_once():
    for job in db.next_jobs(3):
        payload = json.loads(job.get('payload') or '{}')
        try:
            if job.get('kind') == 'ocr_image':
                process_image_job(payload)
            elif job.get('kind') == 'publish':
                process_publish_job(payload)
            else:
                raise RuntimeError(f"Unknown job {job.get('kind')}")
            db.finish_job(job['id'], True)
        except Exception as exc:
            log.error('job %s failed: %s', job['id'], exc)
            db.finish_job(job['id'], False, str(exc))
            db.set_stat('last_error', str(exc)[:300])
