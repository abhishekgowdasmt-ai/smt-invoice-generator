@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo Could not change directory to "%~dp0"
  pause
  exit /b 1
)
set "PYTHONUNBUFFERED=1"
set "INGEST_DIR=%~dp0"
set "PY=%INGEST_DIR%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Installing Python packages. This can take a few minutes.
  py -3 -m venv "%INGEST_DIR%.venv"
  if errorlevel 1 (
    echo Failed to create virtualenv
    pause
    exit /b 1
  )
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r "%INGEST_DIR%requirements.txt"
)
echo Starting RAC Booking OCR from "%INGEST_DIR%"
echo Dashboard: http://127.0.0.1:8787
echo RAC page: /admin/dispatch/booking-ocr
echo Logs: "%INGEST_DIR%logs\ingest.log"
echo WhatsApp watcher is disabled. WorkDrive polling starts automatically when configured.
"%PY%" -c "import config; print('Tesseract:', config.TESSERACT_CMD or 'NOT FOUND - install Tesseract OCR'); print('WorkDrive enabled:', config.ZOHO_WORKDRIVE_ENABLED); print('WorkDrive folder configured:', bool(config.ZOHO_WORKDRIVE_FOLDER_ID)); print('WorkDrive OAuth configured:', bool(config.ZOHO_WORKDRIVE_CLIENT_ID and config.ZOHO_WORKDRIVE_CLIENT_SECRET and config.ZOHO_WORKDRIVE_REFRESH_TOKEN)); print('RAC API key configured:', bool(config.WEBSITE_API_KEY))"
"%PY%" "%INGEST_DIR%app.py"
endlocal
