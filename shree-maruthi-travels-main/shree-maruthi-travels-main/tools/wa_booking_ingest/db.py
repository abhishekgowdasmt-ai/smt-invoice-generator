"""SQLite queue, bookings cache, processed messages, review queue."""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import config

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
        return data


def list_bookings(limit=100):
    with connect() as conn:
        rows = conn.execute('SELECT * FROM bookings ORDER BY updated_at DESC LIMIT ?', (limit,)).fetchall()
        return [row_to_dict(row) for row in rows]
