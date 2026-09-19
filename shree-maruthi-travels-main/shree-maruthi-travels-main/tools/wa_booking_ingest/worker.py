"""OCR + validate + publish worker. Reads from the SQLite job queue."""
import json
from pathlib import Path

import config
import db
from logutil import log, redact
from pipeline import enqueue_local_image, process_ingest_record


def process_image_job(payload):
    record_id = payload.get('ingest_record_id')
    image_path = payload.get('image_path')
    if record_id:
        return process_ingest_record(record_id)
    if not image_path:
        raise RuntimeError('ocr_image job missing ingest_record_id and image_path')
    source = payload.get('source') or db.SOURCE_WEBSITE
    record_id = enqueue_local_image(
        image_path,
        source=source,
        source_file_id=payload.get('message_id') or payload.get('source_file_id') or '',
        source_file_name=Path(image_path).name,
    )
    return process_ingest_record(record_id)


def process_publish_job(payload):
    from publisher import publish_bookings
    rows = payload.get('bookings') or []
    publish_bookings(rows, source=payload.get('source') or db.SOURCE_WEBSITE)
    for row in rows:
        action = db.upsert_booking(row)
        db.bump('bookings_created' if action == 'created' else 'bookings_updated')


def run_once():
    db.recover_stale_processing()
    for job in db.next_jobs(3):
        payload = json.loads(job.get('payload') or '{}')
        try:
            if job.get('kind') == 'ocr_image':
                process_image_job(payload)
            elif job.get('kind') == 'publish':
                process_publish_job(payload)
            elif job.get('kind') == 'workdrive_reconcile':
                from workdrive_sync import reconcile
                reconcile()
            elif job.get('kind') == 'workdrive_file':
                from workdrive_sync import enqueue_workdrive_file
                file_id = payload.get('file_id')
                if not file_id:
                    raise RuntimeError('workdrive_file job missing file_id')
                enqueue_workdrive_file(file_id)
            else:
                raise RuntimeError(f"Unknown job {job.get('kind')}")
            db.finish_job(job['id'], True)
        except Exception as exc:
            log.error('job %s failed: %s', job['id'], redact(exc))
            db.finish_job(job['id'], False, redact(exc)[:500])
            db.set_stat('last_error', redact(exc)[:300])
            record_id = payload.get('ingest_record_id')
            if record_id:
                record = db.get_ingest_record(record_id)
                if record and record.get('status') == db.STATUS_PROCESSING:
                    db.update_ingest_record(
                        record_id,
                        status=db.STATUS_FAILED,
                        error=redact(exc)[:500],
                        processed_at=db.now(),
                    )
                    db.bump('failed')
