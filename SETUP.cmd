@echo off
setlocal
cd /d "%~dp0"
set "setup_python=python"
%setup_python% -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 goto install
set "setup_python=py -3"
%setup_python% -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto no_python

:install
echo Setting up Acewyn AI in this folder. This installs Python packages from PyPI.
%setup_python% -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
if /i "%~1"=="--no-pause" exit /b 0
echo Setup complete. Double-click START.cmd to open Acewyn AI.
pause
exit /b 0
:no_python
echo Install Python 3.11 or later from python.org, then open START.cmd again.
if /i not "%~1"=="--no-pause" pause
exit /b 1
:failed
echo Setup did not finish. Review the error above, check your internet connection, and try START.cmd again.
if /i not "%~1"=="--no-pause" pause
exit /b 1
