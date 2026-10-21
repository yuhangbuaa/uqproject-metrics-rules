@echo off
setlocal
cd /d "%~dp0"

py -3 --version >nul 2>nul
if not errorlevel 1 goto run_py

python --version >nul 2>nul
if not errorlevel 1 goto run_python

echo Python 3 was not found.
echo Install Python 3, then run this file again.
pause
exit /b 1

:run_py
echo Project midterm catalog: http://127.0.0.1:4173/
echo Keep this window open. Press Ctrl+C to stop.
py -3 -m http.server 4173 --bind 127.0.0.1 --directory dist
exit /b %errorlevel%

:run_python
echo Project midterm catalog: http://127.0.0.1:4173/
echo Keep this window open. Press Ctrl+C to stop.
python -m http.server 4173 --bind 127.0.0.1 --directory dist
exit /b %errorlevel%
