"""Playwright smoke test against a temporary profile only."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import session

INGEST_PROFILE = Path(config.PROFILE_DIR).resolve()
CHROME_PROFILE = Path.home() / 'AppData' / 'Local' / 'Google' / 'Chrome' / 'User Data'

INDEXEDDB_PROBE = """async () => {
  const out = { open: false, error: '' };
  try {
    await new Promise((resolve, reject) => {
      const req = indexedDB.open('wa_smoke_probe', 1);
      req.onerror = () => reject(req.error || new Error('open failed'));
      req.onsuccess = () => {
        try { req.result.close(); } catch (e) {}
        try { indexedDB.deleteDatabase('wa_smoke_probe'); } catch (e) {}
        resolve();
      };
    });
    out.open = true;
  } catch (err) {
    out.error = String(err && err.message ? err.message : err);
  }
  return out;
}"""


class PlaywrightSmokeTests(unittest.TestCase):
    @unittest.skipUnless(
        str(__import__('os').environ.get('WHATSAPP_WATCHER_ENABLED') or '0').strip() in ('1', 'true', 'yes'),
        'WhatsApp Playwright capture is deprecated and disabled',
    )
    def test_indexeddb_on_temporary_profile(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('playwright not installed')

        with tempfile.TemporaryDirectory(prefix='wa_ingest_smoke_') as tmp:
            profile = Path(tmp) / 'tmp_profile'
            profile.mkdir()
            self.assertNotEqual(profile.resolve(), INGEST_PROFILE)
            self.assertFalse(str(CHROME_PROFILE).lower() in str(profile.resolve()).lower())

            with sync_playwright() as pw:
                kwargs = {
                    'user_data_dir': str(profile),
                    'headless': True,
                    'args': list(session.INGEST_LAUNCH_ARGS),
                    'viewport': {'width': 800, 'height': 600},
                }
                chrome = session.chromium_executable_hint()
                if chrome:
                    kwargs['executable_path'] = chrome
                try:
                    context = pw.chromium.launch_persistent_context(**kwargs)
                except Exception as exc:
                    if 'Executable doesn\'t exist' in str(exc) or 'playwright install' in str(exc):
                        self.skipTest(f'chromium not available: {exc}')
                    raise
                page = context.pages[0] if context.pages else context.new_page()
                page.goto('https://example.com', wait_until='domcontentloaded')
                probe = page.evaluate(INDEXEDDB_PROBE)
                context.close()

            self.assertTrue(probe.get('open'), probe)
            self.assertTrue(profile.exists())


if __name__ == '__main__':
    unittest.main()
