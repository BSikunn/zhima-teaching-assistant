param([int]$Port = 8765, [switch]$KeepServices)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"
$TaskPidFile = Join-Path $ProjectRoot "logs\server-$Port.json"
if (-not (Test-Path -LiteralPath $TaskPidFile)) { if ($Port -eq 8765 -and -not $KeepServices) { & (Join-Path $ProjectRoot '.venv\Scripts\python.exe') (Join-Path $ProjectRoot 'scripts\local-services.py') stop; if ($LASTEXITCODE -ne 0) { throw 'Background task drain failed; services were preserved.' }; & "$PSScriptRoot\index-service.ps1" -Action stop }; Write-Host 'No managed server record for this port.'; return }
$TaskIdentity = Get-Content -LiteralPath $TaskPidFile -Raw -Encoding UTF8 | ConvertFrom-Json
if ($TaskIdentity.project -ne $ProjectRoot) { throw 'Process record belongs to another project.' }
$TaskProcess = Get-Process -Id $TaskIdentity.pid -ErrorAction SilentlyContinue
if ($TaskProcess) {
    $TaskCommand = Get-CimInstance Win32_Process -Filter "ProcessId=$($TaskIdentity.pid)"
    $TaskStartedTicks = $TaskProcess.StartTime.ToUniversalTime().Ticks
    $TaskRecordedTicks = ([datetime]$TaskIdentity.started).ToUniversalTime().Ticks
    if ($TaskStartedTicks -ne $TaskRecordedTicks -or -not $TaskCommand.CommandLine.Contains($ProjectRoot) -or -not $TaskCommand.CommandLine.Contains('app.main:create_app')) {
        throw 'Process identity changed; refusing to stop an unrelated process.'
    }
    $TaskChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($TaskIdentity.pid)"
    foreach ($TaskChild in $TaskChildren) {
        if ($TaskChild.CommandLine -and $TaskChild.CommandLine.Contains('app.main:create_app')) { Stop-Process -Id $TaskChild.ProcessId -ErrorAction SilentlyContinue }
    }
    Stop-Process -Id $TaskIdentity.pid -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $TaskPidFile
Write-Host "Stopped this project's server on port $Port."
if ($Port -eq 8765 -and -not $KeepServices) {
    & (Join-Path $ProjectRoot '.venv\Scripts\python.exe') (Join-Path $ProjectRoot 'scripts\local-services.py') stop
    if ($LASTEXITCODE -ne 0) { throw 'Background task drain failed; index and remaining services were preserved.' }
    & "$PSScriptRoot\index-service.ps1" -Action stop
}
