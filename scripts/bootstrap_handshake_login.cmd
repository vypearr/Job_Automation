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

echo Opening the persistent Handshake browser profile for sign-in...
"%PYTHON_EXE%" -m job_agent.local_submit --login-only --limit 1 %*
exit /b %errorlevel%
