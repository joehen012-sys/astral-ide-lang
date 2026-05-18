@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"
set "RUNNER=%SCRIPT_DIR%run.py"

if exist "%VENV_PY%" (
  "%VENV_PY%" "%RUNNER%" %*
  exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%RUNNER%" %*
  exit /b %errorlevel%
)

python "%RUNNER%" %*
exit /b %errorlevel%
