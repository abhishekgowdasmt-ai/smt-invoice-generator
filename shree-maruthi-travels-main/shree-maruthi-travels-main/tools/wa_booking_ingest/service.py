"""Production OCR + WorkDrive worker. Does not start the Flask development server."""
from __future__ import annotations

import os
import sys
import threading
import time

import config
import db
from logutil import log, redact
from worker import run_once
from workdrive import configured as workdrive_configured
from workdrive_sync import reconcile

_loops_started = False


class TesseractMissing(SystemExit):
    """Raised/used when Tesseract is not installed in this environment."""


def require_tesseract():
    binary = config.tesseract_binary()
    version = config.tesseract_version_line(binary)
    if not binary or not version:
        log.error(
            'Tesseract is missing. The production Docker image must install tesseract-ocr. '
            'Set TESSERACT_CMD if the binary is not on PATH.'
        )
        raise TesseractMissing(1)
    if config.TESSERACT_CMD:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD
        except Exception:
            pass
    return binary, version


def log_startup_health(binary, version):
    log.info('OCR worker started')
    log.info('Tesseract detected: %s', version)
    from ocr_provider import get_provider
    log.info('OCR provider: %s', get_provider().name)
    log.info('OCR.space configured: %s', bool(config.OCR_SPACE_API_KEY))
    log.info('Gemini OCR configured: %s', bool(config.GEMINI_API_KEY))
    if config.ZOHO_WORKDRIVE_ENABLED:
        log.info('WorkDrive polling enabled')
    else:
        log.info('WorkDrive polling disabled')
    if config.ZOHO_WORKDRIVE_FOLDER_ID:
        log.info('WorkDrive folder configured')
    else:
        log.info('WorkDrive folder not configured')
    log.info('Poll interval: %s seconds', config.WORKDRIVE_POLL_SECONDS)
    log.info('WhatsApp watcher disabled')
    log.info('Tesseract binary present: %s', bool(binary))
    log.info('WorkDrive OAuth configured: %s', bool(
        config.ZOHO_WORKDRIVE_CLIENT_ID
        and config.ZOHO_WORKDRIVE_CLIENT_SECRET
        and config.ZOHO_WORKDRIVE_REFRESH_TOKEN
    ))
    log.info('RAC ingest URL configured: %s', bool(config.WEBSITE_API_URL))
    log.info('RAC ingest key configured: %s', bool(config.WEBSITE_API_KEY))


def worker_loop():
    while True:
        try:
            run_once()
        except Exception as exc:
            log.error('worker loop %s', redact(exc))
        time.sleep(2)


def workdrive_loop():
    log.info('[WorkDrive] poller started interval=%ss', config.WORKDRIVE_POLL_SECONDS)
    while True:
        try:
            if workdrive_configured():
                reconcile()
            elif config.ZOHO_WORKDRIVE_ENABLED:
                log.info('[WorkDrive] enabled but OAuth/folder is incomplete; retrying later')
        except Exception as exc:
            log.error('workdrive loop %s', redact(exc))
        time.sleep(config.WORKDRIVE_POLL_SECONDS)


def start_background_loops():
    global _loops_started
    if _loops_started:
        return
    _loops_started = True
    config.ensure_dirs()
    db.connect().close()
    db.recover_stale_processing(minutes=0)
    db.set_stat('whatsapp', 'DISABLED')
    threading.Thread(target=worker_loop, daemon=True, name='ocr-worker').start()
    threading.Thread(target=workdrive_loop, daemon=True, name='workdrive-poll').start()
    log.info('[WhatsApp] watcher disabled. Use website upload or Zoho WorkDrive.')


def listen_host():
    """OCR HTTP is container-internal. Default all interfaces; AIC only publishes gunicorn PORT."""
    return os.environ.get('DASHBOARD_HOST') or '0.0.0.0'


def listen_port():
    """Internal OCR port (8787). Never bind AIC/gunicorn PORT."""
    raw = os.environ.get('OCR_HTTP_PORT') or os.environ.get('DASHBOARD_PORT')
    if raw not in (None, ''):
        return int(raw)
    return 8787


def serve_http():
    from app import app
    port = listen_port()
    host = listen_host()
    log.info('OCR HTTP listening on %s:%s (production WSGI, not Flask debug)', host, port)
    try:
        from waitress import serve
        serve(app, host=host, port=port, ident='smt-ocr-worker')
        return
    except ImportError:
        pass
    import gunicorn.app.base

    class _App(gunicorn.app.base.BaseApplication):
        def __init__(self, wsgi, options):
            self.wsgi = wsgi
            self.options = options
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key, value)

        def load(self):
            return self.wsgi

    _App(app, {
        'bind': f'{host}:{port}',
        'workers': 1,
        'threads': 4,
        'timeout': 120,
    }).run()


def run(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    http = '--http' in argv
    binary, version = require_tesseract()
    log_startup_health(binary, version)
    start_background_loops()
    if http:
        serve_http()
        return
    log.info('OCR worker running without HTTP (WorkDrive poll + job queue)')
    while True:
        time.sleep(30)
