@echo off
setlocal
cd /d "%~dp0"
py -3.12 --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 was not found.
  echo Install Python 3.12 from https://www.python.org/downloads/
  echo Enable "Add python.exe to PATH" during installation.
  pause
  exit /b 1
)
if not exist .venv (
  py -3.12 -m venv .venv
  if errorlevel 1 goto error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Setup completed. Run start_windows.bat next time.
pause
exit /b 0
:error
echo.
echo Setup failed.
pause
exit /b 1
