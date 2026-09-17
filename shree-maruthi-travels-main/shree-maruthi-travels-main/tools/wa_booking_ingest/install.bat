@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
echo.
echo If OCR is weak, install Tesseract:
echo   winget install --id UB-Mannheim.TesseractOCR
echo.
if not exist .env copy .env.example .env >nul
echo Edit .env and set TARGET_WHATSAPP_GROUP and WEBSITE_API_KEY
echo Then run start.bat
pause
