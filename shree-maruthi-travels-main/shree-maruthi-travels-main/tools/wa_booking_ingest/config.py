"""Environment for the local WhatsApp booking ingest service."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')

DATA_DIR = Path(os.environ.get('DATA_DIR') or ROOT / 'data')
INCOMING_DIR = DATA_DIR / 'incoming'
PROCESSED_DIR = DATA_DIR / 'processed'
FAILED_DIR = DATA_DIR / 'failed'
REVIEW_DIR = DATA_DIR / 'review'
PROFILE_DIR = Path(os.environ.get('WHATSAPP_PROFILE_DIR') or ROOT / 'profile')
LOG_DIR = Path(os.environ.get('LOG_DIR') or ROOT / 'logs')
DB_PATH = Path(os.environ.get('DATABASE_URL') or DATA_DIR / 'ingest.sqlite3')
if str(DB_PATH).startswith('sqlite:///'):
    DB_PATH = Path(str(DB_PATH).replace('sqlite:///', '', 1))

TARGET_WHATSAPP_GROUP = os.environ.get('TARGET_WHATSAPP_GROUP') or ''
WEBSITE_API_URL = (os.environ.get('WEBSITE_API_URL') or 'https://www.shreemaruthitravels.com/api/v1').rstrip('/')
WEBSITE_API_KEY = os.environ.get('WEBSITE_API_KEY') or os.environ.get('RAC_INGEST_KEY') or ''
OCR_PROVIDER = (os.environ.get('OCR_PROVIDER') or 'local').strip().lower()
LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
HEADLESS = str(os.environ.get('WHATSAPP_HEADLESS') or '0').strip() in ('1', 'true', 'yes')
POLL_SECONDS = max(8, int(os.environ.get('POLL_SECONDS') or 12))
DASHBOARD_HOST = os.environ.get('DASHBOARD_HOST') or '127.0.0.1'
DASHBOARD_PORT = int(os.environ.get('DASHBOARD_PORT') or 8787)
SKIP_EXISTING_ON_START = str(os.environ.get('SKIP_EXISTING_ON_START') or '1').strip() not in ('0', 'false', 'no')
AI_API_KEY = os.environ.get('AI_API_KEY') or os.environ.get('OPENAI_API_KEY') or ''
AI_API_URL = os.environ.get('AI_API_URL') or ''
TESSERACT_CMD = os.environ.get('TESSERACT_CMD') or ''


def ensure_dirs():
    for path in (DATA_DIR, INCOMING_DIR, PROCESSED_DIR, FAILED_DIR, REVIEW_DIR, PROFILE_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
