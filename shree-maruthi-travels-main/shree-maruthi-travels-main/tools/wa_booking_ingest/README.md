# Booking OCR ingest (website upload + Zoho WorkDrive)

WhatsApp Web/Playwright capture is **deprecated** and off by default. Booking images enter one shared pipeline from:

1. Website / dashboard upload
2. Zoho WorkDrive folder `RAC_Bookings_OCR`

```
Website upload ──┐
                 ├──► SQLite queue ► OCR ► parser ► validate ► dedupe ► RAC /bookings/ingest
WorkDrive ───────┘
   poll (webhook optional)
```

OCR, parser, validation, and publisher are the existing modules. This tool does not create a second website booking database.

## Start

On the OCR machine:

```
start.bat
```

This starts the dashboard, OCR worker, and WorkDrive poller. WhatsApp is not started.

Production AIC (same container as the RAC website, Tesseract in the root Dockerfile):

`start.sh` runs `python -m tools.wa_booking_ingest --http` on internal port 8787, then gunicorn on `$PORT` (8080).

Local dashboard: http://127.0.0.1:8787
RAC page: https://www.shreemaruthitravels.com/admin/dispatch/booking-ocr

## Method 1 — website upload

REQUIRED:

- `WEBSITE_API_URL` — RAC API, usually `https://www.shreemaruthitravels.com/api/v1`
- `WEBSITE_API_KEY` — same value as website `RAC_INGEST_KEY`
- On the RAC website (same AIC container): `OCR_INGEST_URL=http://127.0.0.1:8787`

The browser never calls 127.0.0.1. The RAC API proxies `/bookings/ocr-upload` to the local worker.

## Method 2 — Zoho WorkDrive

Polling is the baseline. The poller starts automatically with `start.bat` when WorkDrive is configured. A webhook is optional and not required.

REQUIRED:

- `ZOHO_WORKDRIVE_ENABLED=1`
- `ZOHO_WORKDRIVE_FOLDER_ID` — folder id of `RAC_Bookings_OCR` from the WorkDrive URL
- `ZOHO_WORKDRIVE_CLIENT_ID`
- `ZOHO_WORKDRIVE_CLIENT_SECRET`
- `ZOHO_WORKDRIVE_REFRESH_TOKEN`

Do **not** reuse `ZOHO_REFRESH_TOKEN` (Zoho Sheet). Required OAuth scope: `WorkDrive.files.READ`. Original WorkDrive files are never deleted.

## Duplicate protection

1. SHA-256 of the image bytes
2. `booking_id + trip_date`
3. RAC website lookup/ingest before insert

Same booking ID with a **different** date goes to Review (`Same BOOKING_ID already exists with a different date.`).

## Tests

```
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
