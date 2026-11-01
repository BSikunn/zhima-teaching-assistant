param([ValidateSet('start','stop')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"
Set-Location -LiteralPath $ProjectRoot
$TaskPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$TaskRecord = Join-Path $ProjectRoot 'logs\index-service.json'
if ($Action -eq 'stop') {
    if (-not (Test-Path -LiteralPath $TaskRecord)) { return }
    $TaskIdentity = Get-Content -LiteralPath $TaskRecord -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($TaskIdentity.project -ne $ProjectRoot) { throw 'Index process belongs to another project.' }
    $TaskProcess = Get-Process -Id $TaskIdentity.pid -ErrorAction SilentlyContinue
    if ($TaskProcess) {
        $TaskCommand = Get-CimInstance Win32_Process -Filter "ProcessId=$($TaskIdentity.pid)"
        if ($TaskProcess.StartTime.ToUniversalTime().Ticks -ne ([datetime]$TaskIdentity.started).ToUniversalTime().Ticks -or
            -not $TaskCommand.CommandLine.Contains($ProjectRoot) -or -not $TaskCommand.CommandLine.Contains('app.index_server:create_app')) {
            throw 'Index process identity changed; refusing to stop another process.'
        }
        $TaskChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($TaskIdentity.pid)"
        foreach ($TaskChild in $TaskChildren) {
            if ($TaskChild.CommandLine -and $TaskChild.CommandLine.Contains('app.index_server:create_app')) { Stop-Process -Id $TaskChild.ProcessId -ErrorAction SilentlyContinue }
        }
        Stop-Process -Id $TaskIdentity.pid -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $TaskRecord
    Write-Host 'Stopped project vector index.'
    return
}
$TaskSettingsText = & $TaskPython -c 'from app.config import Settings; import json; s=Settings(); print(json.dumps({"retrieval":s.retrieval_backend,"url":s.index_url}))'
if ($LASTEXITCODE -ne 0) { throw 'Cannot read project index settings.' }
$TaskSettings = $TaskSettingsText | ConvertFrom-Json
if ($TaskSettings.retrieval -ne 'vector') { return }
$TaskUrl = [Uri]$TaskSettings.url
if ($TaskUrl.Host -notin @('127.0.0.1','localhost')) {
    Write-Host 'Using configured external vector index.'
    return
}
$TaskPort = $TaskUrl.Port
$TaskHealth = $null
try { $TaskHealth = Invoke-RestMethod "$($TaskSettings.url)/health" -TimeoutSec 3 } catch {}
if ($TaskHealth -and $TaskHealth.status -eq 'ok') { Write-Host 'Vector index is ready.'; return }
if (Get-NetTCPConnection -LocalPort $TaskPort -State Listen -ErrorAction SilentlyContinue) { throw 'Index port is occupied or index failed its health probe.' }
$TaskProcess = Start-Process -FilePath $TaskPython -ArgumentList @('-m','uvicorn','app.index_server:create_app','--factory','--host','127.0.0.1','--port',"$TaskPort") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ProjectRoot 'logs\index.stdout.log') -RedirectStandardError (Join-Path $ProjectRoot 'logs\index.stderr.log') -PassThru
@{pid=$TaskProcess.Id;project=$ProjectRoot;started=$TaskProcess.StartTime.ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $TaskRecord -Encoding UTF8
for ($TaskAttempt=0; $TaskAttempt -lt 120; $TaskAttempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $TaskHealth = Invoke-RestMethod "$($TaskSettings.url)/health" -TimeoutSec 3
        if ($TaskHealth.status -eq 'ok') { Write-Host 'BGE / Chroma vector index is ready.'; return }
    } catch {}
    if ($TaskProcess.HasExited) { break }
}
throw 'Vector index failed to start; inspect logs/index.stderr.log.'
