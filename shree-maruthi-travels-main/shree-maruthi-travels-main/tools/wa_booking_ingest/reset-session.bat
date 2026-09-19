@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run start.bat once so the virtualenv exists.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
echo This backs up ONLY the ingest WhatsApp Playwright profile.
echo It does not touch your normal Chrome or other WhatsApp data.
python -c "import session; session.reset_session('manual reset-session.bat')"
echo.
echo Next: run start.bat and scan the QR in the Chromium window.
pause
