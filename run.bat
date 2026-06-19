@echo off
cd /d "%~dp0"

if exist "scripts\.venv\Scripts\python.exe" (
    "scripts\.venv\Scripts\python.exe" scripts\ui.py
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\ui.py
) else (
    python scripts\ui.py
)

if %errorlevel% neq 0 pause
