@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_DIR=%%~fI"

set "PYTHON_EXE="
if exist "C:\Users\ttamb\AppData\Local\Programs\Python\Python313\python.exe" set "PYTHON_EXE=C:\Users\ttamb\AppData\Local\Programs\Python\Python313\python.exe"
if not defined PYTHON_EXE if exist "C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PYTHON_EXE=C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not defined PYTHON_EXE (
  echo Could not find a Python runtime. Install Python 3.13 or use the bundled Codex runtime.
  exit /b 1
)

cd /d "%REPO_DIR%" || exit /b 1

set "JOB_AGENT_TRACKING_WEBHOOK_URL=https://script.google.com/macros/s/AKfycbzpjB_VmuIrJ5DWlB3Qru60pYsOG9Vceqq6u4zf5uBkIFRc4A5wKe7FoYykvoXrolWV/exec"
set "LIMIT=%~1"
if "%LIMIT%"=="" set "LIMIT=25"

if not exist "data\logs" mkdir "data\logs"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_STAMP=%%I"
set "LOG_PATH=data\logs\unattended_cycle_%RUN_STAMP%.log"

echo [%DATE% %TIME%] Starting unattended local daily cycle with submit limit %LIMIT% > "%LOG_PATH%"
"%PYTHON_EXE%" -m job_agent.local_daily_cycle --submit-limit %LIMIT% --headless >> "%LOG_PATH%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
echo [%DATE% %TIME%] Finished unattended local daily cycle with exit code %EXIT_CODE% >> "%LOG_PATH%"

exit /b %EXIT_CODE%
