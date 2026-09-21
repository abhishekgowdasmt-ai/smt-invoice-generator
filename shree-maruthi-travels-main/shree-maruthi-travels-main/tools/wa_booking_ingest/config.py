"""Environment for the local booking OCR ingest service."""
import os
import shutil
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

ROOT = Path(__file__).resolve().parent
SITE_ROOT = ROOT.parent.parent
load_dotenv(ROOT / '.env')
load_dotenv(SITE_ROOT / '.env')

DATA_DIR = Path(os.environ.get('DATA_DIR') or ROOT / 'data')
INCOMING_DIR = DATA_DIR / 'incoming'
PROCESSED_DIR = DATA_DIR / 'processed'
FAILED_DIR = DATA_DIR / 'failed'
REVIEW_DIR = DATA_DIR / 'review'
PROFILE_DIR = Path(os.environ.get('WHATSAPP_PROFILE_DIR') or ROOT / 'wa_playwright_profile')
LOG_DIR = Path(os.environ.get('LOG_DIR') or ROOT / 'logs')
DB_PATH = Path(os.environ.get('DATABASE_URL') or DATA_DIR / 'ingest.sqlite3')
if str(DB_PATH).startswith('sqlite:///'):
    DB_PATH = Path(str(DB_PATH).replace('sqlite:///', '', 1))

TARGET_WHATSAPP_GROUP = (os.environ.get('TARGET_WHATSAPP_GROUP') or '').strip().strip('"').strip("'")
WEBSITE_API_URL = (os.environ.get('WEBSITE_API_URL') or 'https://www.shreemaruthitravels.com/api/v1').rstrip('/')
WEBSITE_API_KEY = os.environ.get('WEBSITE_API_KEY') or os.environ.get('RAC_INGEST_KEY') or ''
OCR_PROVIDER = (os.environ.get('OCR_PROVIDER') or 'auto').strip().lower()
OCR_SPACE_API_KEY = (os.environ.get('OCR_SPACE_API_KEY') or '').strip()
OCR_SPACE_URL = (os.environ.get('OCR_SPACE_URL') or 'https://api.ocr.space/parse/image').strip()
GEMINI_API_KEY = (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_AI_API_KEY') or '').strip()
GEMINI_MODEL = (os.environ.get('GEMINI_MODEL') or 'gemini-2.5-flash').strip()
LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
HEADLESS = str(os.environ.get('WHATSAPP_HEADLESS') or '0').strip() in ('1', 'true', 'yes')
POLL_SECONDS = max(8, int(os.environ.get('POLL_SECONDS') or 12))
DASHBOARD_HOST = os.environ.get('DASHBOARD_HOST') or '127.0.0.1'
DASHBOARD_PORT = int(os.environ.get('DASHBOARD_PORT') or 8787)
SKIP_EXISTING_ON_START = str(os.environ.get('SKIP_EXISTING_ON_START') or '1').strip() not in ('0', 'false', 'no')
AI_API_KEY = os.environ.get('AI_API_KEY') or os.environ.get('OPENAI_API_KEY') or ''
AI_API_URL = os.environ.get('AI_API_URL') or ''


def _find_tesseract():
    configured = (os.environ.get('TESSERACT_CMD') or '').strip()
    if configured:
        return configured
    which = shutil.which('tesseract')
    if which:
        return which
    home = Path.home()
    for candidate in (
        Path('/usr/bin/tesseract'),
        Path('/usr/local/bin/tesseract'),
        Path(os.environ.get('ProgramFiles') or r'C:\Program Files') / 'Tesseract-OCR' / 'tesseract.exe',
        Path(os.environ.get('ProgramFiles(x86)') or r'C:\Program Files (x86)') / 'Tesseract-OCR' / 'tesseract.exe',
        home / 'AppData' / 'Local' / 'Programs' / 'Tesseract-OCR' / 'tesseract.exe',
        home / 'AppData' / 'Local' / 'Tesseract-OCR' / 'tesseract.exe',
    ):
        if candidate.is_file():
            return str(candidate)
    return ''


TESSERACT_CMD = _find_tesseract()
WHATSAPP_WATCHER_ENABLED = str(os.environ.get('WHATSAPP_WATCHER_ENABLED') or '0').strip() in ('1', 'true', 'yes')

IMAGE_EXTENSIONS = tuple(
    ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
    for ext in (os.environ.get('IMAGE_EXTENSIONS') or '.jpg,.jpeg,.png,.webp').split(',')
    if ext.strip()
)
MAX_IMAGE_BYTES = max(100_000, int(os.environ.get('MAX_IMAGE_BYTES') or 15_000_000))

ZOHO_WORKDRIVE_ENABLED = str(os.environ.get('ZOHO_WORKDRIVE_ENABLED') or '0').strip() in ('1', 'true', 'yes')
ZOHO_WORKDRIVE_FOLDER_ID = (os.environ.get('ZOHO_WORKDRIVE_FOLDER_ID') or '').strip()
ZOHO_WORKDRIVE_CLIENT_ID = (os.environ.get('ZOHO_WORKDRIVE_CLIENT_ID') or os.environ.get('ZOHO_CLIENT_ID') or '').strip()
ZOHO_WORKDRIVE_CLIENT_SECRET = (
    os.environ.get('ZOHO_WORKDRIVE_CLIENT_SECRET') or os.environ.get('ZOHO_CLIENT_SECRET') or ''
).strip()
# Never fall back to ZOHO_REFRESH_TOKEN (Zoho Sheet). WorkDrive OCR may reuse the
# existing trip-sheet WORKDRIVE_REFRESH_TOKEN because that token already has files.READ.
ZOHO_WORKDRIVE_REFRESH_TOKEN = (
    os.environ.get('ZOHO_WORKDRIVE_REFRESH_TOKEN') or os.environ.get('WORKDRIVE_REFRESH_TOKEN') or ''
).strip()
ZOHO_WORKDRIVE_ACCOUNTS_URL = (os.environ.get('ZOHO_WORKDRIVE_ACCOUNTS_URL') or 'https://accounts.zoho.in').rstrip('/')
ZOHO_WORKDRIVE_API_BASE = (
    os.environ.get('ZOHO_WORKDRIVE_API_BASE') or 'https://www.zohoapis.in/workdrive/api/v1'
).rstrip('/')
ZOHO_WORKDRIVE_DOWNLOAD_BASE = (
    os.environ.get('ZOHO_WORKDRIVE_DOWNLOAD_BASE') or 'https://download.zoho.in/v1/workdrive/download'
).rstrip('/')
WORKDRIVE_POLL_SECONDS = max(20, int(os.environ.get('WORKDRIVE_POLL_SECONDS') or 60))
WORKDRIVE_STABLE_SECONDS = max(2, int(os.environ.get('WORKDRIVE_STABLE_SECONDS') or 8))
STALE_PROCESSING_MINUTES = max(5, int(os.environ.get('STALE_PROCESSING_MINUTES') or 15))
INGEST_REQUIRE_KEY = str(os.environ.get('INGEST_REQUIRE_KEY') or '0').strip() in ('1', 'true', 'yes')


def is_allowed_image_name(name):
    suffix = Path(name or '').suffix.lower()
    return suffix in IMAGE_EXTENSIONS


def ensure_dirs():
    paths = [DATA_DIR, INCOMING_DIR, PROCESSED_DIR, FAILED_DIR, REVIEW_DIR, LOG_DIR]
    if WHATSAPP_WATCHER_ENABLED:
        paths.append(PROFILE_DIR)
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def tesseract_binary():
    return TESSERACT_CMD or shutil.which('tesseract') or ''


def tesseract_version_line(binary=None):
    import subprocess
    cmd = binary or tesseract_binary()
    if not cmd:
        return ''
    try:
        output = subprocess.check_output([cmd, '--version'], stderr=subprocess.STDOUT, text=True, timeout=10)
    except Exception:
        return ''
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[0] if lines else ''
