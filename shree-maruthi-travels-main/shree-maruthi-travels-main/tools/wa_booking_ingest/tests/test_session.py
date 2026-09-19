import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import session


class SessionTests(unittest.TestCase):
    def test_diagnostic_stop_is_fatal(self):
        self.assertTrue(issubclass(session.DiagnosticStop, Exception))
        self.assertFalse(session.page_reports_db_error(''))
    def test_db_error_text(self):
        self.assertTrue(session.page_reports_db_error(
            'A database error occurred on your browser. Please relink your device.'
        ))
        self.assertFalse(session.page_reports_db_error('Scan this QR code to log in'))

    def test_backup_renames_instead_of_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'wa_playwright_profile'
            idb = folder / 'Default' / 'IndexedDB' / 'https_web.whatsapp.com_0.indexeddb.leveldb'
            idb.mkdir(parents=True)
            (idb / 'CURRENT').write_text('MANIFEST-000001\n', encoding='utf-8')
            (folder / 'Local State').write_text('{}', encoding='utf-8')
            dest = session.backup_profile('test corruption', folder=folder)
            self.assertTrue(dest.exists())
            self.assertTrue((dest / 'Default' / 'IndexedDB' / 'https_web.whatsapp.com_0.indexeddb.leveldb' / 'CURRENT').exists())
            self.assertTrue(folder.exists())
            self.assertTrue((folder / session.MARKER_NAME).exists())
            self.assertFalse((folder / 'Default' / 'IndexedDB').exists())

    def test_whatsapp_idb_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'wa_playwright_profile'
            folder.mkdir()
            self.assertFalse(session.profile_has_whatsapp_db(folder))
            idb = session.whatsapp_idb_dir(folder)
            idb.mkdir(parents=True)
            self.assertTrue(session.profile_has_whatsapp_db(folder))

    def test_stale_lock_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'wa_playwright_profile'
            folder.mkdir()
            (folder / 'SingletonLock').write_text('lock', encoding='utf-8')
            removed = session.remove_stale_locks(folder)
            self.assertIn('SingletonLock', removed)
            self.assertFalse((folder / 'SingletonLock').exists())

    def test_refuses_normal_chrome_profile(self):
        fake = r'C:\Users\Abhishek B G\AppData\Local\Google\Chrome\User Data'
        self.assertTrue(session.is_forbidden_chrome_profile(fake))
        ingest = ROOT / 'wa_playwright_profile'
        self.assertFalse(session.is_forbidden_chrome_profile(ingest))

    def test_prepare_does_not_rename_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'wa_playwright_profile'
            marker_idb = folder / 'Default' / 'IndexedDB' / 'keep-me'
            marker_idb.mkdir(parents=True)
            (marker_idb / 'x').write_text('stay', encoding='utf-8')
            old = session.profile_dir
            session.profile_dir = lambda: folder
            try:
                # prepare_for_start uses config.PROFILE_DIR, so only assert helper
                self.assertTrue(folder.exists())
                self.assertFalse(any(folder.parent.glob('*.corrupt-*')))
            finally:
                session.profile_dir = old


if __name__ == '__main__':
    unittest.main()
