@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py --launch
) else (
  python run.py --launch
)
if errorlevel 1 pause
