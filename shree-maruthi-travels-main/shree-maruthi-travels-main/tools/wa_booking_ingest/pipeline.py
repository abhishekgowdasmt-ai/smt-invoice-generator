"""Shared booking-image pipeline for website upload and Zoho WorkDrive.

Both sources enqueue ingest_records and this module does:
verify → hash → OCR → parse → validate → dedupe → publish.
"""
from pathlib import Path

import config
import db
from imageutil import sha256_file, verify_image
from logutil import log
from ocr_provider import extract_bookings
from publisher import lookup_website_booking, publish_bookings
from validate import validate_booking

DATE_CONFLICT = 'Same BOOKING_ID already exists with a different date.'


def _copy_name(image_path, folder):
    source = Path(image_path)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return str(source)
    target = folder / source.name
    if source.resolve() != target.resolve():
        target.write_bytes(source.read_bytes())
    return str(target)


def _payload(record):
    import json
    raw = record.get('payload') if record else ''
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or '{}')
    except Exception:
        return {}


def _mark(record_id, status, error='', booking_id='', booking_date='', extra=None):
    fields = {
        'status': status,
        'processed_at': db.now(),
        'error': (error or '')[:500],
    }
    if booking_id:
        fields['booking_id'] = booking_id
    if booking_date:
        fields['booking_date'] = booking_date
    if extra is not None:
        fields['payload'] = extra
    db.update_ingest_record(record_id, **fields)
    return status


def _review(record, cleaned, reason, image_path):
    payload = dict(cleaned or {})
    payload['ingest_record_id'] = record.get('id')
    payload['source'] = record.get('source')
    payload['source_file_name'] = record.get('source_file_name')
    stored = _copy_name(image_path, config.REVIEW_DIR)
    db.add_review(payload, reason, stored)
    db.bump('review_required')
    return _mark(
        record['id'],
        db.STATUS_REVIEW_REQUIRED,
        error=reason,
        booking_id=payload.get('booking_id') or record.get('booking_id') or '',
        booking_date=payload.get('trip_date') or record.get('booking_date') or '',
        extra=payload,
    )


def process_ingest_record(record_id, extract_fn=None, publish_fn=None, lookup_fn=None):
    record = db.get_ingest_record(record_id)
    if not record:
        raise RuntimeError(f'ingest record {record_id} not found')
    if record.get('status') in (
        db.STATUS_PUBLISHED,
        db.STATUS_DUPLICATE_IMAGE,
        db.STATUS_DUPLICATE_BOOKING,
        db.STATUS_REVIEW_REQUIRED,
    ) and record.get('processed_at'):
        return record.get('status')

    db.update_ingest_record(record_id, status=db.STATUS_PROCESSING, error='', processed_at=db.now())
    image_path = Path(record.get('image_path') or '')
    try:
        verify_image(image_path)
    except Exception as exc:
        db.bump('failed')
        return _mark(record_id, db.STATUS_FAILED, error=str(exc))

    digest = sha256_file(image_path)
    db.update_ingest_record(record_id, image_sha256=digest)
    prior = db.find_processed_by_sha256(digest, exclude_id=record_id)
    if prior:
        db.bump('duplicates')
        log.info('[Dedupe] duplicate image %s matches record %s', image_path.name, prior.get('id'))
        return _mark(
            record_id,
            db.STATUS_DUPLICATE_IMAGE,
            error=f'duplicate_image matches ingest_record {prior.get("id")}',
            booking_id=prior.get('booking_id') or '',
            booking_date=prior.get('booking_date') or '',
        )

    extract = extract_fn or extract_bookings
    log.info('[OCR] started %s source=%s', image_path.name, record.get('source'))
    text, rows = extract(image_path, source_message_id=f'ingest:{record_id}')
    log.info('[OCR] completed rows=%s chars=%s', len(rows), len(text or ''))
    if not rows:
        return _review(
            record,
            {'text': (text or '')[:4000], 'source_file_name': record.get('source_file_name')},
            'no booking rows extracted',
            str(image_path),
        )
    ready = []
    for row in rows:
        row = dict(row)
        row['upload_date'] = str(record.get('created_at') or '')
        ok, reasons, cleaned = validate_booking(row)
        cleaned['source_image'] = str(image_path)
        cleaned['source_message_id'] = f'ingest:{record_id}:{record.get("source")}'
        if not ok:
            reason = '; '.join(reasons)
            if any('booking_id is missing' in item for item in reasons):
                reason = 'OCR missing booking ID. ' + reason
            if any('trip_date is missing' in item for item in reasons):
                reason = 'OCR missing date. ' + reason
            if any('not a valid date' in item for item in reasons):
                reason = 'invalid date. ' + reason
            _review(record, cleaned, reason, str(image_path))
            continue
        local = db.get_booking(cleaned['booking_id'])
        if local and (local.get('trip_date') or '') != cleaned['trip_date']:
            _review(
                record,
                cleaned,
                DATE_CONFLICT,
                str(image_path),
            )
            continue
        if local and (local.get('trip_date') or '') == cleaned['trip_date']:
            db.bump('duplicates')
            log.info('[Dedupe] duplicate_booking %s %s', cleaned['booking_id'], cleaned['trip_date'])
            _mark(
                record_id,
                db.STATUS_DUPLICATE_BOOKING,
                error='duplicate_booking',
                booking_id=cleaned['booking_id'],
                booking_date=cleaned['trip_date'],
                extra=cleaned,
            )
            continue
        lookup = lookup_website_booking if lookup_fn is None else lookup_fn
        remote = lookup(cleaned['booking_id']) if lookup else None
        if remote and remote.get('error'):
            raise RuntimeError(f"RAC lookup failed: {remote.get('error')}")
        if remote and remote.get('found'):
            remote_date = remote.get('trip_date') or ''
            if remote_date and remote_date != cleaned['trip_date']:
                _review(record, cleaned, DATE_CONFLICT, str(image_path))
                continue
            db.bump('duplicates')
            _mark(
                record_id,
                db.STATUS_DUPLICATE_BOOKING,
                error='duplicate_booking website',
                booking_id=cleaned['booking_id'],
                booking_date=cleaned['trip_date'],
                extra=cleaned,
            )
            continue
        ready.append(cleaned)

    record = db.get_ingest_record(record_id)
    if record.get('status') in (db.STATUS_REVIEW_REQUIRED, db.STATUS_DUPLICATE_BOOKING, db.STATUS_DUPLICATE_IMAGE):
        if not ready:
            return record.get('status')

    if not ready:
        current = db.get_ingest_record(record_id)
        if current.get('status') == db.STATUS_PROCESSING:
            return _review(record, {'text': (text or '')[:4000]}, 'all rows need review', str(image_path))
        return current.get('status')

    publish = publish_fn or publish_bookings
    source = record.get('source') or db.SOURCE_WEBSITE
    result = publish(ready, source=source)
    for row in ready:
        action = db.upsert_booking(row)
        if action == 'created':
            db.bump('bookings_created')
            log.info('[Publisher] Booking inserted %s', row['booking_id'])
        else:
            db.bump('bookings_updated')
            log.info('[Publisher] Booking updated %s', row['booking_id'])
    conflicts = result.get('conflicts') or []
    if conflicts:
        first = conflicts[0] if isinstance(conflicts[0], dict) else {'booking_id': conflicts[0]}
        cleaned = next((row for row in ready if row.get('booking_id') == first.get('booking_id')), ready[0])
        return _review(record, cleaned, DATE_CONFLICT, str(image_path))
    duplicates = result.get('duplicates') or result.get('updated') or []
    created = result.get('created') or []
    stored = Path(_copy_name(image_path, config.PROCESSED_DIR))
    db.update_ingest_record(record_id, image_path=str(stored))
    db.bump('images_processed')
    first = ready[0]
    if created:
        return _mark(
            record_id,
            db.STATUS_PUBLISHED,
            booking_id=first.get('booking_id') or '',
            booking_date=first.get('trip_date') or '',
            extra=first,
        )
    if duplicates:
        db.bump('duplicates')
        return _mark(
            record_id,
            db.STATUS_DUPLICATE_BOOKING,
            error='duplicate_booking',
            booking_id=first.get('booking_id') or '',
            booking_date=first.get('trip_date') or '',
            extra=first,
        )
    return _mark(
        record_id,
        db.STATUS_PUBLISHED,
        booking_id=first.get('booking_id') or '',
        booking_date=first.get('trip_date') or '',
        extra=first,
    )


def enqueue_local_image(image_path, source, source_file_id='', source_file_name='', source_folder_id='', extra=None):
    existing = db.find_ingest_by_source_file(source, source_file_id) if source_file_id else None
    if existing:
        return existing['id']
    try:
        record_id = db.insert_ingest_record({
            'source': source,
            'source_file_id': source_file_id,
            'source_file_name': source_file_name or Path(image_path).name,
            'source_folder_id': source_folder_id,
            'image_path': str(image_path),
            'status': db.STATUS_RECEIVED,
            'payload': extra or {},
        })
    except Exception:
        raced = db.find_ingest_by_source_file(source, source_file_id) if source_file_id else None
        if raced:
            return raced['id']
        raise
    db.enqueue_job('ocr_image', {'ingest_record_id': record_id, 'image_path': str(image_path)})
    db.bump('images_received')
    return record_id
