import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import db
from pipeline import DATE_CONFLICT, enqueue_local_image, process_ingest_record
from workdrive_sync import extract_file_id_from_webhook, reconcile


def _png(path, color):
    Image.new('RGB', (24, 24), color).save(path)
    return path


def _row(booking_id, trip_date='2026-09-19', **extra):
    data = {
        'booking_id': booking_id,
        'booking_type': 'DROP',
        'cab_type': 'SEDAN',
        'trip_date': trip_date,
        'trip_time': '08:30',
        'planned_start_address': 'Whitefield',
        'confidence': 1,
        'source_image': '',
        'source_message_id': '',
    }
    data.update(extra)
    return data


class PipelineTests(unittest.TestCase):
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
        config.WEBSITE_API_KEY = ''
        config.ensure_dirs()
        db.connect().close()
        self.published = []

    def extract(self, rows):
        def _extract(image_path, source_message_id=''):
            copied = []
            for row in rows:
                item = dict(row)
                item['source_image'] = str(image_path)
                copied.append(item)
            return 'ocr-text', copied
        return _extract

    def publish(self, rows, source='website_upload'):
        created = []
        duplicates = []
        conflicts = []
        for row in rows:
            key = (row['booking_id'], row['trip_date'])
            existing = next((item for item in self.published if item['booking_id'] == row['booking_id']), None)
            if existing and existing['trip_date'] != row['trip_date']:
                conflicts.append({'booking_id': row['booking_id'], 'existing_date': existing['trip_date'], 'new_date': row['trip_date']})
                continue
            if existing:
                duplicates.append(row['booking_id'])
                continue
            self.published.append({'booking_id': row['booking_id'], 'trip_date': row['trip_date'], 'source': source})
            created.append(row['booking_id'])
        return {'created': created, 'duplicates': duplicates, 'conflicts': conflicts, 'updated': [], 'errors': []}

    def lookup(self, booking_id):
        existing = next((item for item in self.published if item['booking_id'] == booking_id), None)
        if not existing:
            return {'found': False}
        return {'found': True, 'trip_date': existing['trip_date'], 'booking_id': booking_id}

    def run_image(self, path, source, source_file_id, rows):
        record_id = enqueue_local_image(path, source=source, source_file_id=source_file_id, source_file_name=Path(path).name)
        status = process_ingest_record(
            record_id,
            extract_fn=self.extract(rows),
            publish_fn=self.publish,
            lookup_fn=self.lookup,
        )
        return record_id, status, db.get_ingest_record(record_id)

    def test_01_same_image_uploaded_twice(self):
        path = _png(self.tmp / 'a.png', (10, 20, 30))
        copy = _png(self.tmp / 'a-copy.png', (10, 20, 30))
        rows = [_row('B260919-AA01')]
        _, status1, rec1 = self.run_image(path, db.SOURCE_WEBSITE, 'up-1', rows)
        _, status2, rec2 = self.run_image(copy, db.SOURCE_WEBSITE, 'up-2', rows)
        self.assertEqual(status1, db.STATUS_PUBLISHED)
        self.assertEqual(status2, db.STATUS_DUPLICATE_IMAGE)
        self.assertEqual(len(self.published), 1)
        self.assertEqual(rec1['image_sha256'], rec2['image_sha256'])

    def test_02_same_booking_id_and_date_different_images(self):
        first = _png(self.tmp / 'b1.png', (1, 2, 3))
        second = _png(self.tmp / 'b2.png', (4, 5, 6))
        rows = [_row('B260919-AA02')]
        self.run_image(first, db.SOURCE_WEBSITE, 'up-3', rows)
        _, status, rec = self.run_image(second, db.SOURCE_WEBSITE, 'up-4', rows)
        self.assertEqual(status, db.STATUS_DUPLICATE_BOOKING)
        self.assertEqual(len(self.published), 1)
        first_hash = hashlib.sha256(first.read_bytes()).hexdigest()
        self.assertNotEqual(rec['image_sha256'], first_hash)

    def test_03_same_booking_id_different_dates(self):
        first = _png(self.tmp / 'c1.png', (7, 8, 9))
        second = _png(self.tmp / 'c2.png', (9, 8, 7))
        self.run_image(first, db.SOURCE_WEBSITE, 'up-5', [_row('B260919-AA03', '2026-09-19')])
        _, status, rec = self.run_image(second, db.SOURCE_WEBSITE, 'up-6', [_row('B260919-AA03', '2026-09-20')])
        self.assertEqual(status, db.STATUS_REVIEW_REQUIRED)
        self.assertIn('different date', (rec.get('error') or ''))
        self.assertEqual(DATE_CONFLICT, rec.get('error'))
        self.assertEqual(len(self.published), 1)
        self.assertEqual(len(db.list_review()), 1)

    def test_04_two_different_bookings(self):
        first = _png(self.tmp / 'd1.png', (11, 12, 13))
        second = _png(self.tmp / 'd2.png', (13, 12, 11))
        self.run_image(first, db.SOURCE_WEBSITE, 'up-7', [_row('B260919-AA04')])
        self.run_image(second, db.SOURCE_WEBSITE, 'up-8', [_row('B260919-AA05')])
        self.assertEqual({item['booking_id'] for item in self.published}, {'B260919-AA04', 'B260919-AA05'})

    def test_05_ocr_missing_booking_id(self):
        path = _png(self.tmp / 'e.png', (20, 20, 20))
        _, status, rec = self.run_image(path, db.SOURCE_WEBSITE, 'up-9', [_row('', '2026-09-19')])
        self.assertEqual(status, db.STATUS_REVIEW_REQUIRED)
        self.assertIn('booking ID', rec.get('error') or '')
        self.assertEqual(self.published, [])

    def test_06_ocr_missing_date(self):
        path = _png(self.tmp / 'f.png', (21, 21, 21))
        row = _row('B260919-AA06')
        row['trip_date'] = ''
        _, status, rec = self.run_image(path, db.SOURCE_WEBSITE, 'up-10', [row])
        self.assertEqual(status, db.STATUS_REVIEW_REQUIRED)
        self.assertIn('date', rec.get('error') or '')
        self.assertEqual(self.published, [])

    def test_07_invalid_date(self):
        path = _png(self.tmp / 'g.png', (22, 22, 22))
        row = _row('B260919-AA07')
        row['trip_date'] = 'not-a-date'
        _, status, rec = self.run_image(path, db.SOURCE_WEBSITE, 'up-11', [row])
        self.assertEqual(status, db.STATUS_REVIEW_REQUIRED)
        self.assertTrue('date' in (rec.get('error') or '').lower())
        self.assertEqual(self.published, [])

    def test_08_workdrive_file_already_processed(self):
        path = _png(self.tmp / 'h.png', (30, 30, 30))
        first_id, _, _ = self.run_image(path, db.SOURCE_WORKDRIVE, 'wd-file-1', [_row('B260919-AA08')])
        second_id = enqueue_local_image(path, source=db.SOURCE_WORKDRIVE, source_file_id='wd-file-1', source_file_name='h.png')
        self.assertEqual(first_id, second_id)
        self.assertEqual(len(db.list_ingest_records()), 1)

    def test_09_workdrive_file_renamed(self):
        path = _png(self.tmp / 'i.png', (31, 31, 31))
        record_id, _, _ = self.run_image(path, db.SOURCE_WORKDRIVE, 'wd-file-2', [_row('B260919-AA09')])
        again = enqueue_local_image(path, source=db.SOURCE_WORKDRIVE, source_file_id='wd-file-2', source_file_name='renamed.png')
        self.assertEqual(record_id, again)
        self.assertEqual(db.get_ingest_record(record_id)['status'], db.STATUS_PUBLISHED)
        self.assertEqual(len(self.published), 1)

    def test_10_restart_during_processing(self):
        path = _png(self.tmp / 'j.png', (40, 40, 40))
        record_id = enqueue_local_image(path, source=db.SOURCE_WEBSITE, source_file_id='up-12', source_file_name='j.png')
        db.update_ingest_record(record_id, status=db.STATUS_PROCESSING)
        recovered = db.recover_stale_processing(minutes=0)
        self.assertIn(record_id, recovered)
        status = process_ingest_record(
            record_id,
            extract_fn=self.extract([_row('B260919-AA10')]),
            publish_fn=self.publish,
            lookup_fn=self.lookup,
        )
        self.assertEqual(status, db.STATUS_PUBLISHED)
        self.assertEqual(len(self.published), 1)
        status_again = process_ingest_record(
            record_id,
            extract_fn=self.extract([_row('B260919-AA10')]),
            publish_fn=self.publish,
            lookup_fn=self.lookup,
        )
        self.assertEqual(status_again, db.STATUS_PUBLISHED)
        self.assertEqual(len(self.published), 1)

    def test_11_webhook_then_polling(self):
        payload = {'data': {'id': 'wd-file-3', 'attributes': {'resource_id': 'wd-file-3'}}}
        file_id = extract_file_id_from_webhook(payload)
        self.assertEqual(file_id, 'wd-file-3')
        calls = []

        def enqueue(fid, info=None, force=False):
            existing = db.find_ingest_by_source_file(db.SOURCE_WORKDRIVE, fid)
            if existing:
                return existing['id']
            path = _png(self.tmp / f'{fid}.png', (50, 50, 50))
            rid = enqueue_local_image(path, source=db.SOURCE_WORKDRIVE, source_file_id=fid, source_file_name=f'{fid}.png')
            calls.append(rid)
            return rid

        first = enqueue(file_id)
        result = reconcile(
            list_fn=lambda folder_id=None: [{'id': 'wd-file-3', 'name': 'wd-file-3.png', 'ext': 'png', 'size': 100, 'version': '1'}],
            enqueue_fn=enqueue,
        )
        self.assertEqual(result['seen'], 1)
        self.assertEqual(len(set(calls + [first])), 1)

    def test_12_duplicate_webhook_events(self):
        path = _png(self.tmp / 'k.png', (51, 51, 51))
        first = enqueue_local_image(path, source=db.SOURCE_WORKDRIVE, source_file_id='wd-file-4', source_file_name='k.png')
        second = enqueue_local_image(path, source=db.SOURCE_WORKDRIVE, source_file_id='wd-file-4', source_file_name='k.png')
        self.assertEqual(first, second)
        self.assertEqual(len(db.list_ingest_records()), 1)

    def test_13_same_workdrive_file_webhook_and_polling(self):
        path = _png(self.tmp / 'l.png', (52, 52, 52))
        webhook_id = enqueue_local_image(path, source=db.SOURCE_WORKDRIVE, source_file_id='wd-file-5', source_file_name='l.png')
        poll_id = enqueue_local_image(path, source=db.SOURCE_WORKDRIVE, source_file_id='wd-file-5', source_file_name='l.png')
        self.assertEqual(webhook_id, poll_id)

    def test_14_website_then_same_image_on_workdrive(self):
        path = _png(self.tmp / 'm.png', (60, 60, 60))
        copy = _png(self.tmp / 'm-wd.png', (60, 60, 60))
        rows = [_row('B260919-AA14')]
        self.run_image(path, db.SOURCE_WEBSITE, 'up-14', rows)
        _, status, _ = self.run_image(copy, db.SOURCE_WORKDRIVE, 'wd-file-14', rows)
        self.assertEqual(status, db.STATUS_DUPLICATE_IMAGE)
        self.assertEqual(len(self.published), 1)

    def test_15_workdrive_then_same_image_on_website(self):
        path = _png(self.tmp / 'n.png', (61, 61, 61))
        copy = _png(self.tmp / 'n-web.png', (61, 61, 61))
        rows = [_row('B260919-AA15')]
        self.run_image(path, db.SOURCE_WORKDRIVE, 'wd-file-15', rows)
        _, status, _ = self.run_image(copy, db.SOURCE_WEBSITE, 'up-15', rows)
        self.assertEqual(status, db.STATUS_DUPLICATE_IMAGE)
        self.assertEqual(len(self.published), 1)


if __name__ == '__main__':
    unittest.main()
