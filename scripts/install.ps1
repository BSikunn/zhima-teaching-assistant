param([string]$Python = '')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"
Set-Location -LiteralPath $ProjectRoot
if (-not $Python) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = (& py -3.12 -c 'import sys; print(sys.executable)').Trim()
    }
    if (-not $Python -and (Test-Path -LiteralPath 'D:\Programs\Python\Python312\python.exe')) {
        $Python = 'D:\Programs\Python\Python312\python.exe'
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { throw 'Python 3.12 is required. Use -Python with the existing interpreter path.' }
& $Python -c 'import sys; assert sys.version_info[:2] in {(3, 11),(3, 12)}, "Python 3.11 or 3.12 required"'
if ($LASTEXITCODE -ne 0) { throw 'The selected interpreter must use Python 3.11 or 3.12.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create project virtual environment.' }
}
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $VenvPython -c 'import sys; assert sys.version_info[:2] in {(3, 11),(3, 12)}, "Existing .venv must use Python 3.11 or 3.12"'
if ($LASTEXITCODE -ne 0) { throw 'The existing virtual environment has the wrong Python version.' }
Write-Host 'Installing Python packages inside project .venv ...'
$TaskRequirements = 'requirements-prod.txt'
& $VenvPython -m pip install -r $TaskRequirements --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& $VenvPython scripts/download-models.py
if ($LASTEXITCODE -ne 0) { throw 'BGE model download failed.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Existing Node.js and npm are required.' }
Push-Location -LiteralPath (Join-Path $ProjectRoot 'frontend')
try {
    & npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host "Installed. All new packages and caches are under $ProjectRoot"
