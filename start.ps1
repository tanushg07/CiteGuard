$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv312\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create a Python environment and install requirements.txt first. See README.md.'
}
& $pythonPath -c 'import sys; print(sys.version)'
if ($LASTEXITCODE -ne 0) { throw 'Python environment is broken. Recreate it using the README instructions.' }
if (-not (Test-Path -LiteralPath 'citeguard-frontend\node_modules')) {
    & npm.cmd ci --prefix citeguard-frontend
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
}
& npm.cmd run build --prefix citeguard-frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
Write-Host 'Open http://127.0.0.1:8000 . Press Ctrl+C to stop.'
& $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
