$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPy = Join-Path $scriptDir "..\..\..\.venv\Scripts\python.exe"
$runner = Join-Path $scriptDir "run.py"

if (Test-Path $venvPy) {
    & $venvPy $runner @args
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $runner @args
    exit $LASTEXITCODE
}

& python $runner @args
exit $LASTEXITCODE
