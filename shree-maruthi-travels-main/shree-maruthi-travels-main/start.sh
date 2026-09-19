#!/bin/sh
# One AIC container: OCR worker on 8787 (internal) + RAC gunicorn on $PORT (public).
set -eu

OCR_HTTP_PORT="${OCR_HTTP_PORT:-8787}"
export OCR_HTTP_PORT
export DASHBOARD_HOST="${DASHBOARD_HOST:-0.0.0.0}"
export WHATSAPP_WATCHER_ENABLED="${WHATSAPP_WATCHER_ENABLED:-0}"
export TESSERACT_CMD="${TESSERACT_CMD:-/usr/bin/tesseract}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export OCR_INGEST_URL="${OCR_INGEST_URL:-http://127.0.0.1:8787}"

OCR_PID=""
GUNI_PID=""
WA_PID=""

cleanup() {
  for pid in ${GUNI_PID:-} ${OCR_PID:-} ${WA_PID:-}; do
    if [ -n "$pid" ]; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

node /app/backend/wa_bridge/server.js &
WA_PID=$!

python -m tools.wa_booking_ingest --http &
OCR_PID=$!

i=0
while [ "$i" -lt 40 ]; do
  if ! kill -0 "$OCR_PID" 2>/dev/null; then
    echo "OCR worker exited during startup. Check Tesseract and OCR logs. Refusing to start RAC without OCR." >&2
    exit 1
  fi
  if python -c "import socket; s=socket.create_connection(('127.0.0.1', int('${OCR_HTTP_PORT}')), 0.4); s.close()" 2>/dev/null; then
    echo "OCR worker listening on 127.0.0.1:${OCR_HTTP_PORT} (internal, not AIC PORT)"
    break
  fi
  i=$((i + 1))
  sleep 0.25
done

if ! kill -0 "$OCR_PID" 2>/dev/null; then
  echo "OCR worker died before becoming ready." >&2
  exit 1
fi
if ! python -c "import socket; s=socket.create_connection(('127.0.0.1', int('${OCR_HTTP_PORT}')), 0.4); s.close()" 2>/dev/null; then
  echo "OCR worker did not bind 127.0.0.1:${OCR_HTTP_PORT}" >&2
  exit 1
fi

gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120 backend.app:app &
GUNI_PID=$!
wait "$GUNI_PID"
