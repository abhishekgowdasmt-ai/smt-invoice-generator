import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import db
from publisher import publish_bookings


class DuplicateAndRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        config.DATA_DIR = self.tmp
        config.INCOMING_DIR = self.tmp / 'incoming'
        config.PROCESSED_DIR = self.tmp / 'processed'
        config.FAILED_DIR = self.tmp / 'failed'
        config.REVIEW_DIR = self.tmp / 'review'
        config.PROFILE_DIR = self.tmp / 'profile'
        config.LOG_DIR = self.tmp / 'logs'
        config.DB_PATH = self.tmp / 'ingest.sqlite3'
        config.ensure_dirs()
        db.connect().close()

    def test_message_dedup(self):
        self.assertFalse(db.message_seen('wa-1'))
        db.mark_message('wa-1', 'Bookings', 'a.jpg', 'queued')
        self.assertTrue(db.message_seen('wa-1'))
        db.mark_message('wa-1', 'Bookings', 'a.jpg', 'done')
        self.assertTrue(db.message_seen('wa-1'))

    def test_booking_upsert_not_duplicate_row(self):
        row = {
            'booking_id': 'B260917-AB12',
            'booking_type': 'DROP',
            'cab_type': 'SEDAN',
            'trip_date': '2026-09-17',
            'trip_time': '08:30',
            'planned_start_address': 'Whitefield',
            'confidence': 1,
            'source_message_id': 'm1',
            'source_image': 'a.jpg',
        }
        self.assertEqual(db.upsert_booking(row), 'created')
        row['planned_start_address'] = 'Whitefield Gate'
        self.assertEqual(db.upsert_booking(row), 'updated')
        rows = db.list_bookings()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['planned_start_address'], 'Whitefield Gate')

    def test_job_retry_on_failure(self):
        db.enqueue_job('ocr_image', {'image_path': 'missing.jpg'})
        job = db.next_jobs(1)[0]
        db.finish_job(job['id'], False, 'boom')
        again = db.next_jobs(5)
        self.assertEqual(again, [])
        with db.connect() as conn:
            stored = conn.execute('SELECT status, retry_count FROM jobs WHERE id=?', (job['id'],)).fetchone()
        self.assertEqual(stored['status'], 'retry')
        self.assertEqual(stored['retry_count'], 1)

    def test_publisher_api_failure(self):
        config.WEBSITE_API_KEY = 'test-key'
        config.WEBSITE_API_URL = 'https://example.test/api/v1'

        class FakeError(Exception):
            pass

        with patch('publisher.urllib.request.urlopen', side_effect=OSError('down')):
            with self.assertRaises(RuntimeError):
                publish_bookings([{'booking_id': 'B1'}])

    def test_publisher_success_payload(self):
        config.WEBSITE_API_KEY = 'test-key'
        config.WEBSITE_API_URL = 'https://example.test/api/v1'

        class Resp:
            def read(self):
                return json.dumps({'success': True, 'created': ['B1'], 'updated': [], 'created_count': 1, 'updated_count': 0, 'errors': []}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch('publisher.urllib.request.urlopen', return_value=Resp()):
            result = publish_bookings([{'booking_id': 'B1'}])
        self.assertEqual(result['created'], ['B1'])


if __name__ == '__main__':
    unittest.main()
