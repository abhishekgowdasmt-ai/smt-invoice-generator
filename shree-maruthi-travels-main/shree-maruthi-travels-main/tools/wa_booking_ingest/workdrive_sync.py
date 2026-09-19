"""WorkDrive webhook enqueue + polling reconciliation. Does not delete WorkDrive files."""
from __future__ import annotations

import time
from pathlib import Path

import config
import db
from logutil import log
from pipeline import enqueue_local_image
from workdrive import WorkDriveError, configured, download_file, file_metadata, list_folder_files


def _is_image(info):
    name = info.get('name') or ''
    ext = info.get('ext') or Path(name).suffix.lstrip('.')
    return config.is_allowed_image_name(name if Path(name).suffix else f'file.{ext}')


def _wait_until_stable(file_id, previous=None):
    first = previous or file_metadata(file_id)
    if not first or not first.get('id'):
        raise WorkDriveError('WorkDrive file metadata missing')
    if first.get('size', 0) <= 0:
        raise WorkDriveError('WorkDrive file is still uploading')
    wait = int(config.WORKDRIVE_STABLE_SECONDS or 0)
    if wait > 0:
        time.sleep(min(wait, 8))
        second = file_metadata(file_id)
    else:
        second = first
    if (second or {}).get('size') != first.get('size') or (second or {}).get('version') != first.get('version'):
        raise WorkDriveError('WorkDrive file size/version is still changing')
    return second


def enqueue_workdrive_file(file_id, info=None, force=False):
    if not file_id:
        return None
    existing = db.find_ingest_by_source_file(db.SOURCE_WORKDRIVE, file_id)
    info = info or {}
    if existing and not force:
        same_version = (existing.get('source_version') or '') == (info.get('version') or existing.get('source_version') or '')
        same_size = int(existing.get('source_size') or 0) == int(info.get('size') or existing.get('source_size') or 0)
        if same_version and same_size:
            log.info('[WorkDrive] skip already recorded file %s', file_id)
            return existing.get('id')
        if existing.get('status') in (db.STATUS_RECEIVED, db.STATUS_PROCESSING):
            return existing.get('id')
        if existing.get('image_sha256') and same_size:
            return existing.get('id')
        # Replaced file: new version with possibly new bytes.
        force = True
        log.info('[WorkDrive] file %s version changed; will re-check hash after download', file_id)

    meta = _wait_until_stable(file_id, info if info.get('id') else None)
    if not _is_image(meta):
        log.info('[WorkDrive] ignore non-image %s', meta.get('name'))
        return None
    dest = config.INCOMING_DIR / f'wd_{file_id}_{Path(meta.get("name") or "image.jpg").name}'
    download_file(file_id, dest)
    if dest.stat().st_size != int(meta.get('size') or dest.stat().st_size) and meta.get('size'):
        # size metadata can be formatted; still process if file is complete
        if dest.stat().st_size <= 32:
            dest.unlink(missing_ok=True)
            raise WorkDriveError('downloaded WorkDrive file is incomplete')

    if existing and force:
        from imageutil import sha256_file
        digest = sha256_file(dest)
        if digest and digest == (existing.get('image_sha256') or ''):
            db.update_ingest_record(
                existing['id'],
                source_version=meta.get('version') or '',
                source_size=int(meta.get('size') or 0),
                source_modified=meta.get('modified') or '',
                source_file_name=meta.get('name') or existing.get('source_file_name'),
            )
            dest.unlink(missing_ok=True)
            return existing.get('id')
        record_id = enqueue_local_image(
            dest,
            source=db.SOURCE_WORKDRIVE,
            source_file_id=f'{file_id}:v:{meta.get("version") or dest.stat().st_size}',
            source_file_name=meta.get('name') or dest.name,
            source_folder_id=config.ZOHO_WORKDRIVE_FOLDER_ID,
            extra={'workdrive_file_id': file_id, 'replaced': True},
        )
        db.update_ingest_record(
            record_id,
            source_version=meta.get('version') or '',
            source_size=int(meta.get('size') or 0),
            source_modified=meta.get('modified') or '',
        )
        return record_id

    record_id = enqueue_local_image(
        dest,
        source=db.SOURCE_WORKDRIVE,
        source_file_id=file_id,
        source_file_name=meta.get('name') or dest.name,
        source_folder_id=config.ZOHO_WORKDRIVE_FOLDER_ID,
        extra={'workdrive_file_id': file_id},
    )
    db.update_ingest_record(
        record_id,
        source_version=meta.get('version') or '',
        source_size=int(meta.get('size') or 0),
        source_modified=meta.get('modified') or '',
    )
    return record_id


def reconcile(list_fn=None, enqueue_fn=None):
    if not configured() and list_fn is None:
        log.info('[WorkDrive] polling idle until OAuth and folder ID are configured')
        return {'seen': 0, 'enqueued': 0}
    folder_id = config.ZOHO_WORKDRIVE_FOLDER_ID
    files = (list_fn or list_folder_files)(folder_id)
    enqueued = 0
    seen = 0
    for info in files:
        seen += 1
        if not _is_image(info):
            continue
        file_id = info.get('id')
        try:
            record_id = (enqueue_fn or enqueue_workdrive_file)(file_id, info=info)
            if record_id:
                record = db.get_ingest_record(record_id)
                if record and record.get('status') == db.STATUS_RECEIVED:
                    enqueued += 1
        except WorkDriveError as exc:
            log.warning('[WorkDrive] file %s not ready: %s', file_id, exc)
        except Exception as exc:
            log.error('[WorkDrive] file %s failed: %s', file_id, exc)
    log.info('[WorkDrive] reconcile seen=%s enqueued=%s', seen, enqueued)
    return {'seen': seen, 'enqueued': enqueued}


def extract_file_id_from_webhook(payload):
    if not isinstance(payload, dict):
        return ''
    data = payload.get('data') or payload
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return ''
    attrs = data.get('attributes') or {}
    return str(
        data.get('id')
        or data.get('resource_id')
        or attrs.get('resource_id')
        or payload.get('resource_id')
        or payload.get('file_id')
        or ''
    )
