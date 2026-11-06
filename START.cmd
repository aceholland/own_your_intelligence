@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto check_local
python -c "import sys, uvicorn, own.api; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 goto launch_system
goto setup

:check_local
".venv\Scripts\python.exe" -c "import sys, uvicorn, own.api; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 goto launch_local

:setup
call "%~dp0SETUP.cmd" --no-pause
if errorlevel 1 goto failed

:launch_local
".venv\Scripts\python.exe" run.py --launch
if errorlevel 1 goto failed
exit /b 0

:launch_system
python run.py --launch
if errorlevel 1 goto failed
exit /b 0

:failed
pause
exit /b 1
