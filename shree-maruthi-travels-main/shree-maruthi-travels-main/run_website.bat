@echo off
cd /d "%~dp0backend"
echo Starting Shree Maruthi Travels website...
echo Open: http://127.0.0.1:5000
echo Admin: http://127.0.0.1:5000/admin  (Google Sign-In)
python app.py
pause
