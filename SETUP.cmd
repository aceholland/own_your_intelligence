@echo off
setlocal
cd /d "%~dp0"
echo Setting up Own in this folder. This installs Python packages from PyPI.
python -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Double-click START.cmd to open Own.
pause
exit /b 0
:failed
echo Setup did not finish. Check that Python and an internet connection are available.
pause
exit /b 1
