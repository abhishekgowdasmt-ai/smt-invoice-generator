"""Rotating file + console logs. Never print OAuth tokens or API keys."""
import logging
import re
from logging.handlers import RotatingFileHandler

import config

_SECRET_PATTERN = re.compile(
    r'(refresh_token|access_token|client_secret|api[_-]?key|x-ingest-key)'
    r'(=|:|"\s*:\s*")[^&\s"]+',
    re.I,
)


def redact(text):
    if text is None:
        return ''
    cleaned = str(text)
    secrets = [
        config.WEBSITE_API_KEY,
        config.ZOHO_WORKDRIVE_CLIENT_SECRET,
        config.ZOHO_WORKDRIVE_REFRESH_TOKEN,
        config.ZOHO_WORKDRIVE_CLIENT_ID,
        config.AI_API_KEY,
    ]
    for secret in secrets:
        if secret and len(str(secret)) >= 8:
            cleaned = cleaned.replace(str(secret), '[redacted]')
    return _SECRET_PATTERN.sub(r'\1\2[redacted]', cleaned)


def setup_logging():
    config.ensure_dirs()
    logger = logging.getLogger('wa_ingest')
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, str(config.LOG_LEVEL).upper(), logging.INFO))
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    file_handler = RotatingFileHandler(config.LOG_DIR / 'ingest.log', maxBytes=2_000_000, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(fmt)
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(stream)
    return logger


log = setup_logging()
