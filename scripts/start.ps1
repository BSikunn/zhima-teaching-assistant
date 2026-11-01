param([int]$Port = 8765, [switch]$NoBrowser, [switch]$SkipVectorSync)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"
Set-Location -LiteralPath $ProjectRoot
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Port must be between 1024 and 65535.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe') -or -not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
    & "$PSScriptRoot\install.ps1"
}
& (Join-Path $ProjectRoot '.venv\Scripts\python.exe') scripts/local-services.py start
if ($LASTEXITCODE -ne 0) { throw 'Project service startup failed. Inspect the Redis/MinIO/Celery project logs.' }
$Address = "http://127.0.0.1:$Port"
$TaskHealth = $null
try { $TaskHealth = Invoke-RestMethod "$Address/api/health" -TimeoutSec 2 } catch {}
if ($TaskHealth) {
    if ($TaskHealth.product -ne 'zhima-prototype' -or $TaskHealth.project_root -ne $ProjectRoot) { throw "Port $Port is used by another application." }
    & "$PSScriptRoot\index-service.ps1" -Action start
    if (-not $SkipVectorSync) {
        & (Join-Path $ProjectRoot '.venv\Scripts\python.exe') -m app.services.vectors sync
        if ($LASTEXITCODE -ne 0) { throw 'Course vector synchronization failed; inspect the index logs.' }
    }
    Write-Host "Already running: $Address"
    if (-not $NoBrowser) { Start-Process $Address }
    return
}
$TaskListener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($TaskListener) { throw "Port $Port is occupied. Choose another port with -Port." }
$TaskPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $TaskPython -c 'import sys; assert sys.version_info[:2] in {(3, 11),(3, 12)}, "Python 3.11 or 3.12 required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or 3.12 is required.' }
& "$PSScriptRoot\index-service.ps1" -Action start
$TaskProcess = Start-Process -FilePath $TaskPython -ArgumentList @('-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ProjectRoot "logs\server-$Port.stdout.log") -RedirectStandardError (Join-Path $ProjectRoot "logs\server-$Port.stderr.log") -PassThru
$TaskIdentity = @{ pid=$TaskProcess.Id; port=$Port; project=$ProjectRoot; started=$TaskProcess.StartTime.ToUniversalTime().ToString('o') }
$TaskIdentity | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ProjectRoot "logs\server-$Port.json") -Encoding UTF8
for ($TaskAttempt=0; $TaskAttempt -lt 30; $TaskAttempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $TaskHealth = Invoke-RestMethod "$Address/api/health" -TimeoutSec 2
    } catch {}
    if ($TaskHealth -and $TaskHealth.product -eq 'zhima-prototype' -and $TaskHealth.project_root -eq $ProjectRoot) {
        if (-not $SkipVectorSync) {
            & $TaskPython -m app.services.vectors sync
            if ($LASTEXITCODE -ne 0) { throw 'Course vector synchronization failed; inspect the index logs.' }
        }
        Write-Host "Running: $Address"
        Write-Host 'Accounts: student / student2 / student3 / teacher / admin; password: Demo12345!'
        if (-not $NoBrowser) { Start-Process $Address }
        return
    }
    if ($TaskProcess.HasExited) { break }
}
throw "Startup failed. Check project logs/server-$Port.stderr.log"
