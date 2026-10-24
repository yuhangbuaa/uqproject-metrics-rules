@echo off
setlocal
cd /d "%~dp0"

pandoc --version >nul 2>nul
if errorlevel 1 (
    echo Pandoc was not found. Install Pandoc and add it to PATH.
    exit /b 1
)

py -3 --version >nul 2>nul
if not errorlevel 1 goto run_py

python --version >nul 2>nul
if not errorlevel 1 goto run_python

echo Python 3 was not found.
exit /b 1

:run_py
py -3 -X utf8 scripts\export_research_reports.py %*
exit /b %errorlevel%

:run_python
python -X utf8 scripts\export_research_reports.py %*
exit /b %errorlevel%
