"""python -m tools.wa_booking_ingest

Ingest modules import as top-level names (`config`, `db`, ...), so this entry
adds the package directory to sys.path before starting the worker.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service import run  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(run())
