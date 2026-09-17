# WhatsApp group → RAC bookings (local Windows)

Someone posts a booking-table screenshot in your existing WhatsApp group. This PC captures it, reads the table, and upserts rows into the SMT RAC website. It never sends WhatsApp messages.

## How it fits the website

The live site already stores RAC bookings (Zoho / Flask `/api/v1`). This tool does **not** create a second booking database for the website.

- Website ingest: `POST /api/v1/bookings/ingest` (header `X-Ingest-Key`)
- Same `source_booking_id` updates the existing row instead of duplicating
- RAC → Bookings has two tabs: **Last 3 days** (paid/unpaid) and **All history**

The existing RAC WhatsApp linker is only for assignment messages. This watcher is a separate read-only Playwright session.

## One-time setup

1. Run `install.bat`
2. Install Tesseract OCR if prompted (`winget install --id UB-Mannheim.TesseractOCR`)
3. Copy `.env.example` to `.env` (install.bat does this)
4. Set:
   - `TARGET_WHATSAPP_GROUP` — exact group name
   - `WEBSITE_API_URL` — `https://www.shreemaruthitravels.com/api/v1`
   - `WEBSITE_API_KEY` — same value as `RAC_INGEST_KEY` on the server
5. On the website host, set `RAC_INGEST_KEY` to that same secret
6. Run `start.bat`
7. First launch: Chromium opens WhatsApp Web. Scan the QR once. The session is saved in `profile/`
8. Open http://127.0.0.1:8787 for status, captured bookings, and the review queue
9. Optional auto-start after login: right-click `install-startup.ps1` → Run with PowerShell

Leave the PC on. Do not close the Chromium window that shows WhatsApp Web.

## What happens on a new image

1. Watcher sees a new image in that group only
2. Image is saved under `data/incoming/`
3. OCR worker extracts table rows
4. Valid rows are posted to the website
5. Same booking ID updates the existing booking
6. Weak/broken rows go to the local review queue (fix → Approve / Reject)
7. Images already on screen when the app starts are skipped, so history is not re-imported

## Tests

```
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Notes

- Dashboard binds to `127.0.0.1` only
- `profile/` and `data/` stay off git
- OCR uses Tesseract locally. Set `OCR_PROVIDER=ai` later if you add a key; the rest of the app stays the same
- WhatsApp Web CSS can change. If the group is not found, keep the chat open and restart `start.bat`
