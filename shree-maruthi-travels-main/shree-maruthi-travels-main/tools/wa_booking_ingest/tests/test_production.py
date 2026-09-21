import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import db
from logutil import redact
from pipeline import DATE_CONFLICT, enqueue_local_image, process_ingest_record
from workdrive import configured as workdrive_configured


class ProductionGuardTests(unittest.TestCase):
    def test_workdrive_poll_interval_default(self):
        self.assertGreaterEqual(config.WORKDRIVE_POLL_SECONDS, 20)
        self.assertIn('.jpg', config.IMAGE_EXTENSIONS)
        self.assertIn('.jpeg', config.IMAGE_EXTENSIONS)
        self.assertIn('.png', config.IMAGE_EXTENSIONS)
        self.assertIn('.webp', config.IMAGE_EXTENSIONS)

    def test_whatsapp_disabled_by_default(self):
        self.assertFalse(config.WHATSAPP_WATCHER_ENABLED)

    def test_image_types(self):
        self.assertEqual(config.IMAGE_EXTENSIONS, ('.jpg', '.jpeg', '.png', '.webp'))
        self.assertTrue(config.is_allowed_image_name('shot.JPG'))
        self.assertFalse(config.is_allowed_image_name('sheet.pdf'))

    def test_workdrive_folder_id_not_hardcoded(self):
        text = (ROOT / 'workdrive.py').read_text(encoding='utf-8')
        self.assertNotIn('x9f5cdd9f9c276e6f4a18bec018d82cf420a4', text)
        self.assertIn('ZOHO_WORKDRIVE_FOLDER_ID', text)

    def test_workdrive_requires_full_oauth(self):
        old = (
            config.ZOHO_WORKDRIVE_ENABLED,
            config.ZOHO_WORKDRIVE_CLIENT_ID,
            config.ZOHO_WORKDRIVE_CLIENT_SECRET,
            config.ZOHO_WORKDRIVE_REFRESH_TOKEN,
            config.ZOHO_WORKDRIVE_FOLDER_ID,
        )
        try:
            config.ZOHO_WORKDRIVE_ENABLED = True
            config.ZOHO_WORKDRIVE_CLIENT_ID = 'id'
            config.ZOHO_WORKDRIVE_CLIENT_SECRET = 'secret'
            config.ZOHO_WORKDRIVE_REFRESH_TOKEN = 'refresh'
            config.ZOHO_WORKDRIVE_FOLDER_ID = ''
            self.assertFalse(workdrive_configured())
            config.ZOHO_WORKDRIVE_FOLDER_ID = 'folder'
            self.assertTrue(workdrive_configured())
        finally:
            (
                config.ZOHO_WORKDRIVE_ENABLED,
                config.ZOHO_WORKDRIVE_CLIENT_ID,
                config.ZOHO_WORKDRIVE_CLIENT_SECRET,
                config.ZOHO_WORKDRIVE_REFRESH_TOKEN,
                config.ZOHO_WORKDRIVE_FOLDER_ID,
            ) = old

    def test_redact_hides_tokens(self):
        old_refresh = config.ZOHO_WORKDRIVE_REFRESH_TOKEN
        old_secret = config.ZOHO_WORKDRIVE_CLIENT_SECRET
        old_key = config.WEBSITE_API_KEY
        old_ocr = config.OCR_SPACE_API_KEY
        old_gemini = config.GEMINI_API_KEY
        try:
            config.ZOHO_WORKDRIVE_REFRESH_TOKEN = 'refresh-token-value-12345'
            config.ZOHO_WORKDRIVE_CLIENT_SECRET = 'client-secret-value-12345'
            config.WEBSITE_API_KEY = 'rac-ingest-key-12345'
            config.OCR_SPACE_API_KEY = 'ocrspace-key-value-12345'
            config.GEMINI_API_KEY = 'gemini-key-value-12345'
            message = redact(
                'token=refresh-token-value-12345 secret=client-secret-value-12345 '
                'key=rac-ingest-key-12345 ocr=ocrspace-key-value-12345 gem=gemini-key-value-12345'
            )
            self.assertNotIn('refresh-token-value-12345', message)
            self.assertNotIn('client-secret-value-12345', message)
            self.assertNotIn('rac-ingest-key-12345', message)
            self.assertNotIn('ocrspace-key-value-12345', message)
            self.assertNotIn('gemini-key-value-12345', message)
            self.assertIn('[redacted]', message)
        finally:
            config.ZOHO_WORKDRIVE_REFRESH_TOKEN = old_refresh
            config.ZOHO_WORKDRIVE_CLIENT_SECRET = old_secret
            config.WEBSITE_API_KEY = old_key
            config.OCR_SPACE_API_KEY = old_ocr
            config.GEMINI_API_KEY = old_gemini

    def test_start_bat_does_not_launch_whatsapp(self):
        text = (ROOT / 'start.bat').read_text(encoding='utf-8').lower()
        self.assertIn('app.py', text)
        self.assertNotIn('watcher.py', text)
        self.assertIn('whatsapp watcher is disabled', text)

    def test_review_edit_does_not_publish(self):
        import tempfile
        from PIL import Image
        tmp = Path(tempfile.mkdtemp())
        config.DATA_DIR = tmp
        config.INCOMING_DIR = tmp / 'incoming'
        config.PROCESSED_DIR = tmp / 'processed'
        config.FAILED_DIR = tmp / 'failed'
        config.REVIEW_DIR = tmp / 'review'
        config.LOG_DIR = tmp / 'logs'
        config.DB_PATH = tmp / 'ingest.sqlite3'
        config.ensure_dirs()
        db.connect().close()
        path = tmp / 'conflict.png'
        Image.new('RGB', (16, 16), (1, 2, 3)).save(path)

        published = []

        def extract(image_path, source_message_id=''):
            return 'text', [{
                'booking_id': 'B260919-EDIT',
                'booking_type': 'DROP',
                'cab_type': 'SEDAN',
                'trip_date': '2026-09-20',
                'trip_time': '08:30',
                'planned_start_address': 'Whitefield',
                'confidence': 1,
                'source_image': str(image_path),
                'source_message_id': source_message_id,
            }]

        def publish(rows, source='website_upload'):
            published.extend(rows)
            return {'created': [row['booking_id'] for row in rows], 'duplicates': [], 'conflicts': [], 'updated': [], 'errors': []}

        def lookup(booking_id):
            return {'found': True, 'trip_date': '2026-09-19', 'booking_id': booking_id}

        record_id = enqueue_local_image(path, source=db.SOURCE_WEBSITE, source_file_id='edit-1', source_file_name='conflict.png')
        status = process_ingest_record(record_id, extract_fn=extract, publish_fn=publish, lookup_fn=lookup)
        self.assertEqual(status, db.STATUS_REVIEW_REQUIRED)
        self.assertEqual(DATE_CONFLICT, db.get_ingest_record(record_id)['error'])
        self.assertEqual(published, [])
        reviews = db.list_review()
        self.assertEqual(len(reviews), 1)
        payload = {'booking_id': 'B260919-EDIT', 'trip_date': '2026-09-21', 'ingest_record_id': record_id}
        db.save_review_payload(reviews[0]['id'], payload)
        still_open = db.list_review()
        self.assertEqual(len(still_open), 1)
        self.assertEqual(published, [])


if __name__ == '__main__':
    unittest.main()
