$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  $python = "C:/Users/joehe/AppData/Local/Microsoft/WindowsApps/python3.13.exe"
}

Write-Host "Using Python: $python"

# Ensure stale/locked binaries do not survive a rebuild.
Get-Process -Name "AstralIDE" -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -Path (Join-Path $root "dist\AstralIDE.exe") -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $root "build") -Recurse -Force -ErrorAction SilentlyContinue

& $python -m pip install --upgrade pip
& $python -m pip install pyinstaller pillow markdown tkinterweb

& $python tools/make_astral_icon.py

$icon = Join-Path $root "assets\icons\astral.ico"
$entry = Join-Path $root "astral_ide.py"
$version_file = Join-Path $root "version_info.txt"

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "AstralIDE" `
  --icon "$icon" `
  --version-file "$version_file" `
  --paths "$root" `
  "$entry"

Write-Host "Build finished. EXE is at: $root\dist\AstralIDE.exe"
