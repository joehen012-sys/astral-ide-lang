@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe"
set "IDE=%SCRIPT_DIR%astral_ide.py"

if exist "%VENV_PY%" (
  "%VENV_PY%" "%IDE%"
  exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%IDE%"
  exit /b %errorlevel%
)

python "%IDE%"
exit /b %errorlevel%

