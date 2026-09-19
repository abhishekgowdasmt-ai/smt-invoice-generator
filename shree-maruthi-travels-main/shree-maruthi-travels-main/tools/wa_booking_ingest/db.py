"""SQLite queue, bookings cache, ingest records, review queue."""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import config

STATUS_RECEIVED = 'RECEIVED'
STATUS_PROCESSING = 'PROCESSING'
STATUS_PUBLISHED = 'PUBLISHED'
STATUS_DUPLICATE_IMAGE = 'DUPLICATE_IMAGE'
STATUS_DUPLICATE_BOOKING = 'DUPLICATE_BOOKING'
STATUS_REVIEW_REQUIRED = 'REVIEW_REQUIRED'
STATUS_FAILED = 'FAILED'

SOURCE_WEBSITE = 'website_upload'
SOURCE_WORKDRIVE = 'zoho_workdrive'

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY,
    booking_id TEXT UNIQUE NOT NULL,
    booking_type TEXT,
    cab_type TEXT,
    trip_date TEXT,
    trip_time TEXT,
    planned_start_address TEXT,
    status TEXT,
    confidence REAL,
    source_message_id TEXT,
    source_image_path TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS processed_messages (
    id INTEGER PRIMARY KEY,
    whatsapp_message_id TEXT UNIQUE NOT NULL,
    group_name TEXT,
    image_path TEXT,
    processed_at TEXT,
    processing_status TEXT,
    error_message TEXT
);
CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY,
    payload TEXT,
    reason TEXT,
    image_path TEXT,
    created_at TEXT,
    resolved_at TEXT,
    resolution TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    kind TEXT,
    payload TEXT,
    status TEXT,
    retry_count INTEGER DEFAULT 0,
    next_attempt_at TEXT,
    last_error TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS ingest_records (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_file_id TEXT,
    source_file_name TEXT,
    source_folder_id TEXT,
    source_version TEXT,
    source_size INTEGER,
    source_modified TEXT,
    image_sha256 TEXT,
    image_path TEXT,
    status TEXT NOT NULL,
    booking_id TEXT,
    booking_date TEXT,
    created_at TEXT,
    processed_at TEXT,
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    payload TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ingest_source_file
    ON ingest_records(source, source_file_id)
    WHERE source_file_id IS NOT NULL AND source_file_id != '';
CREATE INDEX IF NOT EXISTS idx_ingest_sha256 ON ingest_records(image_sha256);
CREATE INDEX IF NOT EXISTS idx_ingest_booking ON ingest_records(booking_id, booking_date);
CREATE INDEX IF NOT EXISTS idx_ingest_status ON ingest_records(status);
"""


def connect():
    config.ensure_dirs()
    path = Path(config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.executescript(SCHEMA)
    return conn


def now():
    return datetime.utcnow().isoformat(timespec='seconds') + 'Z'


def row_to_dict(row):
    return dict(row) if row else None


def mark_message(message_id, group_name, image_path, status, error=''):
    with connect() as conn:
        conn.execute(
            """INSERT INTO processed_messages
               (whatsapp_message_id, group_name, image_path, processed_at, processing_status, error_message)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(whatsapp_message_id) DO UPDATE SET
                 processing_status=excluded.processing_status,
                 error_message=excluded.error_message,
                 processed_at=excluded.processed_at,
                 image_path=excluded.image_path""",
            (message_id, group_name, image_path, now(), status, error[:500]),
        )


def message_seen(message_id):
    with connect() as conn:
        row = conn.execute(
            'SELECT 1 FROM processed_messages WHERE whatsapp_message_id=?',
            (message_id,),
        ).fetchone()
        return bool(row)


def enqueue_job(kind, payload, delay_seconds=0):
    when = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat(timespec='seconds') + 'Z'
    with connect() as conn:
        conn.execute(
            """INSERT INTO jobs (kind, payload, status, retry_count, next_attempt_at, last_error, created_at, updated_at)
               VALUES (?, ?, 'pending', 0, ?, '', ?, ?)""",
            (kind, json.dumps(payload), when, now(), now()),
        )


def next_jobs(limit=5):
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM jobs
               WHERE status IN ('pending', 'retry') AND next_attempt_at<=?
               ORDER BY id LIMIT ?""",
            (now(), limit),
        ).fetchall()
        return [row_to_dict(row) for row in rows]


def finish_job(job_id, ok, error=''):
    with connect() as conn:
        if ok:
            conn.execute(
                "UPDATE jobs SET status='done', last_error='', updated_at=? WHERE id=?",
                (now(), job_id),
            )
            return
        row = conn.execute('SELECT retry_count FROM jobs WHERE id=?', (job_id,)).fetchone()
        retries = int(row['retry_count'] if row else 0) + 1
        delay = min(30 * (2 ** min(retries, 6)), 1800)
        nxt = (datetime.utcnow() + timedelta(seconds=delay)).isoformat(timespec='seconds') + 'Z'
        status = 'failed' if retries >= 8 else 'retry'
        conn.execute(
            """UPDATE jobs SET status=?, retry_count=?, next_attempt_at=?, last_error=?, updated_at=?
               WHERE id=?""",
            (status, retries, nxt, error[:500], now(), job_id),
        )


def upsert_booking(row):
    stamp = now()
    with connect() as conn:
        existing = conn.execute('SELECT * FROM bookings WHERE booking_id=?', (row['booking_id'],)).fetchone()
        if existing:
            conn.execute(
                """UPDATE bookings SET booking_type=?, cab_type=?, trip_date=?, trip_time=?,
                   planned_start_address=?, status=?, confidence=?, source_message_id=?,
                   source_image_path=?, updated_at=? WHERE booking_id=?""",
                (
                    row.get('booking_type'), row.get('cab_type'), row.get('trip_date'),
                    row.get('trip_time'), row.get('planned_start_address'), row.get('status') or 'published',
                    row.get('confidence'), row.get('source_message_id'), row.get('source_image'),
                    stamp, row['booking_id'],
                ),
            )
            return 'updated'
        conn.execute(
            """INSERT INTO bookings (
                booking_id, booking_type, cab_type, trip_date, trip_time, planned_start_address,
                status, confidence, source_message_id, source_image_path, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row['booking_id'], row.get('booking_type'), row.get('cab_type'), row.get('trip_date'),
                row.get('trip_time'), row.get('planned_start_address'), row.get('status') or 'published',
                row.get('confidence'), row.get('source_message_id'), row.get('source_image'), stamp, stamp,
            ),
        )
        return 'created'


def get_booking(booking_id):
    with connect() as conn:
        return row_to_dict(conn.execute(
            'SELECT * FROM bookings WHERE booking_id=?',
            (booking_id,),
        ).fetchone())


def add_review(payload, reason, image_path):
    with connect() as conn:
        conn.execute(
            """INSERT INTO review_queue (payload, reason, image_path, created_at, resolved_at, resolution)
               VALUES (?, ?, ?, ?, '', '')""",
            (json.dumps(payload), reason, image_path, now()),
        )


def list_review(open_only=True):
    sql = 'SELECT * FROM review_queue'
    if open_only:
        sql += " WHERE resolved_at='' OR resolved_at IS NULL"
    sql += ' ORDER BY id DESC'
    with connect() as conn:
        return [row_to_dict(row) for row in conn.execute(sql).fetchall()]


def get_review(review_id):
    with connect() as conn:
        return row_to_dict(conn.execute('SELECT * FROM review_queue WHERE id=?', (review_id,)).fetchone())


def save_review_payload(review_id, payload):
    with connect() as conn:
        conn.execute(
            "UPDATE review_queue SET payload=?, resolved_at='', resolution='' WHERE id=?",
            (json.dumps(payload), review_id),
        )


def resolve_review(review_id, resolution, payload=None):
    with connect() as conn:
        if payload is not None:
            conn.execute(
                "UPDATE review_queue SET payload=?, resolution=?, resolved_at=? WHERE id=?",
                (json.dumps(payload), resolution, now(), review_id),
            )
        else:
            conn.execute(
                "UPDATE review_queue SET resolution=?, resolved_at=? WHERE id=?",
                (resolution, now(), review_id),
            )


def bump(key, amount=1):
    with connect() as conn:
        row = conn.execute('SELECT value FROM stats WHERE key=?', (key,)).fetchone()
        current = int(row['value']) if row else 0
        conn.execute(
            'INSERT INTO stats(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=?',
            (key, str(current + amount), str(current + amount)),
        )


def set_stat(key, value):
    with connect() as conn:
        conn.execute(
            'INSERT INTO stats(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            (key, str(value)),
        )


def get_stats():
    with connect() as conn:
        rows = conn.execute('SELECT key, value FROM stats').fetchall()
        data = {row['key']: row['value'] for row in rows}
        open_review = conn.execute(
            "SELECT COUNT(*) AS n FROM review_queue WHERE resolved_at='' OR resolved_at IS NULL"
        ).fetchone()['n']
        pending_jobs = conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE status IN ('pending','retry')"
        ).fetchone()['n']
        data['review_open'] = str(open_review)
        data['jobs_pending'] = str(pending_jobs)
        total = conn.execute('SELECT COUNT(*) AS n FROM ingest_records').fetchone()['n']
        data['ingest_total'] = str(total)
        data['ingest_total'] = str(conn.execute('SELECT COUNT(*) AS n FROM ingest_records').fetchone()['n'])
        counts = conn.execute(
            """SELECT status, COUNT(*) AS n FROM ingest_records GROUP BY status"""
        ).fetchall()
        for row in counts:
            data[f'ingest_{row["status"]}'] = str(row['n'])
        sources = conn.execute(
            """SELECT source, COUNT(*) AS n FROM ingest_records GROUP BY source"""
        ).fetchall()
        for row in sources:
            data[f'source_{row["source"]}'] = str(row['n'])
        today = datetime.utcnow().strftime('%Y-%m-%d')
        today_rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM ingest_records WHERE created_at LIKE ? GROUP BY status",
            (f'{today}%',),
        ).fetchall()
        data['today_received'] = '0'
        for row in today_rows:
            data['today_received'] = str(int(data.get('today_received') or 0) + row['n'])
            data[f'today_{row["status"]}'] = str(row['n'])
        return data


def list_bookings(limit=100):
    with connect() as conn:
        rows = conn.execute('SELECT * FROM bookings ORDER BY updated_at DESC LIMIT ?', (limit,)).fetchall()
        return [row_to_dict(row) for row in rows]


def insert_ingest_record(fields):
    stamp = now()
    cols = {
        'source': fields.get('source') or SOURCE_WEBSITE,
        'source_file_id': fields.get('source_file_id') or '',
        'source_file_name': fields.get('source_file_name') or '',
        'source_folder_id': fields.get('source_folder_id') or '',
        'source_version': fields.get('source_version') or '',
        'source_size': int(fields.get('source_size') or 0),
        'source_modified': fields.get('source_modified') or '',
        'image_sha256': fields.get('image_sha256') or '',
        'image_path': fields.get('image_path') or '',
        'status': fields.get('status') or STATUS_RECEIVED,
        'booking_id': fields.get('booking_id') or '',
        'booking_date': fields.get('booking_date') or '',
        'created_at': stamp,
        'processed_at': fields.get('processed_at') or '',
        'error': fields.get('error') or '',
        'retry_count': int(fields.get('retry_count') or 0),
        'payload': json.dumps(fields.get('payload') or {}),
    }
    with connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO ingest_records (
                    source, source_file_id, source_file_name, source_folder_id, source_version,
                    source_size, source_modified, image_sha256, image_path, status, booking_id,
                    booking_date, created_at, processed_at, error, retry_count, payload
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(cols.values()),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            row = conn.execute(
                'SELECT id FROM ingest_records WHERE source=? AND source_file_id=?',
                (cols['source'], cols['source_file_id']),
            ).fetchone()
            if not row:
                raise
            return row['id']


def get_ingest_record(record_id):
    with connect() as conn:
        return row_to_dict(conn.execute('SELECT * FROM ingest_records WHERE id=?', (record_id,)).fetchone())


def find_ingest_by_source_file(source, source_file_id):
    if not source_file_id:
        return None
    with connect() as conn:
        return row_to_dict(conn.execute(
            'SELECT * FROM ingest_records WHERE source=? AND source_file_id=?',
            (source, source_file_id),
        ).fetchone())


def find_processed_by_sha256(sha256, exclude_id=None):
    if not sha256:
        return None
    sql = """SELECT * FROM ingest_records
             WHERE image_sha256=? AND status!=?"""
    args = [sha256, STATUS_FAILED]
    if exclude_id:
        sql += ' AND id!=?'
        args.append(exclude_id)
    sql += ' ORDER BY id LIMIT 1'
    with connect() as conn:
        return row_to_dict(conn.execute(sql, args).fetchone())


def update_ingest_record(record_id, **fields):
    if not fields:
        return
    allowed = {
        'source_version', 'source_size', 'source_modified', 'image_sha256', 'image_path',
        'status', 'booking_id', 'booking_date', 'processed_at', 'error', 'retry_count', 'payload',
        'source_file_name',
    }
    sets = []
    values = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == 'payload' and not isinstance(value, str):
            value = json.dumps(value or {})
        sets.append(f'{key}=?')
        values.append(value)
    if not sets:
        return
    values.append(record_id)
    with connect() as conn:
        conn.execute(f"UPDATE ingest_records SET {', '.join(sets)} WHERE id=?", values)


def list_ingest_records(limit=80):
    with connect() as conn:
        rows = conn.execute(
            'SELECT * FROM ingest_records ORDER BY id DESC LIMIT ?',
            (limit,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]


def recover_stale_processing(minutes=None):
    minutes = 0 if minutes == 0 else (minutes if minutes is not None else config.STALE_PROCESSING_MINUTES)
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat(timespec='seconds') + 'Z'
    recovered = []
    with connect() as conn:
        if minutes == 0:
            rows = conn.execute(
                "SELECT * FROM ingest_records WHERE status=?",
                (STATUS_PROCESSING,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM ingest_records
                   WHERE status=? AND (
                     processed_at='' OR processed_at IS NULL OR processed_at<=?
                   )""",
                (STATUS_PROCESSING, cutoff),
            ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE ingest_records SET status=?, error=?, processed_at='', retry_count=retry_count+1 WHERE id=?",
                (STATUS_RECEIVED, 'recovered after restart', row['id']),
            )
            recovered.append(row['id'])
    for record_id in recovered:
        enqueue_job('ocr_image', {'ingest_record_id': record_id})
    return recovered
