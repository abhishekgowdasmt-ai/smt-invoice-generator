"""Rotating file + console logs."""
import logging
from logging.handlers import RotatingFileHandler

import config


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
