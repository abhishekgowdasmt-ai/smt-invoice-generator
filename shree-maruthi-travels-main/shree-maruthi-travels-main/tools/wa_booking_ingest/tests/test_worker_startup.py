import io
import logging
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import service
from logutil import redact


class WorkerStartupTests(unittest.TestCase):
    def test_module_command_exists(self):
        main = ROOT / '__main__.py'
        self.assertTrue(main.is_file())
        text = main.read_text(encoding='utf-8')
        self.assertIn('from service import run', text)
        worker_reqs = (ROOT / 'requirements-worker.txt').read_text(encoding='utf-8').lower()
        packages = [line.strip() for line in worker_reqs.splitlines() if line.strip() and not line.strip().startswith('#')]
        self.assertFalse(any(item.startswith('playwright') for item in packages))
        nested_app = ROOT.parents[1]
        start = (nested_app / 'start.sh').read_text(encoding='utf-8')
        self.assertIn('python -m tools.wa_booking_ingest --http', start)
        self.assertIn('OCR_HTTP_PORT', start)
        self.assertIn('8787', start)
        self.assertIn('gunicorn --bind 0.0.0.0:${PORT:-8080}', start)
        self.assertIn('trap cleanup EXIT INT TERM', start)
        self.assertNotIn('watch_forever', start)
        self.assertNotIn('playwright', start.lower())
        nested_docker = (nested_app / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('npm run build', nested_docker)
        self.assertIn('tesseract-ocr', nested_docker)
        self.assertIn('tesseract-ocr-eng', nested_docker)
        self.assertIn('requirements-worker.txt', nested_docker)
        self.assertIn('OCR_INGEST_URL=http://127.0.0.1:8787', nested_docker)
        self.assertIn('EXPOSE 8080', nested_docker)
        self.assertNotIn('EXPOSE 8787', nested_docker)
        repo_root = ROOT.parents[3]
        rac_root = (repo_root / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('npm run build', rac_root)
        self.assertIn('tesseract-ocr', rac_root)
        self.assertIn('tesseract-ocr-eng', rac_root)
        self.assertIn('./start.sh', rac_root)
        self.assertIn('OCR_HTTP_PORT=8787', rac_root)
        self.assertIn('OCR_INGEST_URL=http://127.0.0.1:8787', rac_root)
        self.assertIn('EXPOSE 8080', rac_root)
        self.assertNotIn('EXPOSE 8787', rac_root)
        self.assertNotIn('playwright', rac_root.lower())
        rac_api = (nested_app / 'backend' / 'rac_api.py').read_text(encoding='utf-8')
        self.assertIn("http://127.0.0.1:8787", rac_api)
        self.assertIn("requests.post(", rac_api)
        self.assertIn("/api/upload", rac_api)

    def test_missing_tesseract_fails_clearly(self):
        with mock.patch.object(config, 'tesseract_binary', return_value=''):
            with mock.patch.object(config, 'tesseract_version_line', return_value=''):
                with self.assertRaises(service.TesseractMissing):
                    service.require_tesseract()

    def test_startup_logs_do_not_include_secrets(self):
        buffer = io.StringIO()
        handler = logging.StreamHandler(buffer)
        service.log.addHandler(handler)
        old_refresh = config.ZOHO_WORKDRIVE_REFRESH_TOKEN
        old_secret = config.ZOHO_WORKDRIVE_CLIENT_SECRET
        old_key = config.WEBSITE_API_KEY
        try:
            config.ZOHO_WORKDRIVE_REFRESH_TOKEN = 'super-secret-refresh-token-xyz'
            config.ZOHO_WORKDRIVE_CLIENT_SECRET = 'super-secret-client-xyz'
            config.WEBSITE_API_KEY = 'super-secret-ingest-key-xyz'
            service.log_startup_health('/usr/bin/tesseract', 'tesseract 5.3.0')
            output = buffer.getvalue()
            self.assertIn('OCR worker started', output)
            self.assertIn('Tesseract detected: tesseract 5.3.0', output)
            self.assertIn('Poll interval:', output)
            self.assertNotIn('super-secret-refresh-token-xyz', output)
            self.assertNotIn('super-secret-client-xyz', output)
            self.assertNotIn('super-secret-ingest-key-xyz', output)
            self.assertNotIn('super-secret-refresh-token-xyz', redact(output))
        finally:
            service.log.removeHandler(handler)
            config.ZOHO_WORKDRIVE_REFRESH_TOKEN = old_refresh
            config.ZOHO_WORKDRIVE_CLIENT_SECRET = old_secret
            config.WEBSITE_API_KEY = old_key

    def test_worker_run_without_http_does_not_use_flask_dev(self):
        source = (ROOT / 'service.py').read_text(encoding='utf-8')
        self.assertNotIn('app.run(', source)
        self.assertIn('WorkDrive polling enabled', source)
        self.assertIn("if http:", source)

    def test_whatsapp_not_started_by_worker(self):
        source = (ROOT / 'service.py').read_text(encoding='utf-8')
        self.assertNotIn('watcher_loop', source)
        self.assertNotIn('watch_forever', source)

    def test_http_bind_uses_internal_8787_and_ignores_aic_port(self):
        with mock.patch.dict(os.environ, {'PORT': '8080', 'OCR_HTTP_PORT': '', 'DASHBOARD_PORT': '', 'DASHBOARD_HOST': ''}):
            self.assertEqual(service.listen_host(), '0.0.0.0')
            self.assertEqual(service.listen_port(), 8787)
        with mock.patch.dict(os.environ, {'PORT': '9090', 'OCR_HTTP_PORT': '8787', 'DASHBOARD_HOST': '0.0.0.0'}):
            self.assertEqual(service.listen_port(), 8787)
            self.assertEqual(service.listen_host(), '0.0.0.0')
        with mock.patch.dict(os.environ, {'OCR_HTTP_PORT': '8787', 'PORT': '8080'}):
            self.assertNotEqual(service.listen_port(), 8080)
        local = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('config.DASHBOARD_PORT', local)
        self.assertIn('app.run(', local)
        source = (ROOT / 'service.py').read_text(encoding='utf-8')
        self.assertNotIn("os.environ.get('PORT')", source)

    def test_workdrive_never_deletes_remote_files(self):
        workdrive = (ROOT / 'workdrive.py').read_text(encoding='utf-8')
        sync = (ROOT / 'workdrive_sync.py').read_text(encoding='utf-8')
        self.assertNotIn("method='DELETE'", workdrive)
        self.assertNotIn('method="DELETE"', workdrive)
        self.assertIn('Does not delete WorkDrive files', sync)
        self.assertIn('WORKDRIVE_STABLE_SECONDS', sync)
        self.assertIn('still uploading', sync)

    def test_sheet_refresh_token_is_not_used_for_workdrive(self):
        text = (ROOT / 'config.py').read_text(encoding='utf-8')
        self.assertIn("os.environ.get('ZOHO_WORKDRIVE_REFRESH_TOKEN')", text)
        self.assertIn('Never fall back to ZOHO_REFRESH_TOKEN', text)
        self.assertNotRegex(text, r"ZOHO_WORKDRIVE_REFRESH_TOKEN\s*=\s*.*ZOHO_REFRESH_TOKEN")


if __name__ == '__main__':
    unittest.main()
