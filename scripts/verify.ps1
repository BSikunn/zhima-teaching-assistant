param([int]$Port = 8766, [switch]$SkipBrowser)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\env.ps1"
Set-Location -LiteralPath $ProjectRoot
$TaskPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $TaskPython -m pytest -q --basetemp=.cache/pytest-verify
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
& $TaskPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
Push-Location -LiteralPath (Join-Path $ProjectRoot 'frontend')
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend type check or build failed.' }
} finally { Pop-Location }
if (-not $SkipBrowser) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw 'Browser test port is occupied. Choose another -Port; existing services are never stopped by verification.' }
    $TaskServer = Start-Process -FilePath $TaskPython -ArgumentList @('scripts/browser-test-server.py',"$Port") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ProjectRoot 'logs\verify-browser.stdout.log') -RedirectStandardError (Join-Path $ProjectRoot 'logs\verify-browser.stderr.log') -PassThru
    try {
        $TaskReady = $false
        for ($TaskAttempt=0; $TaskAttempt -lt 40; $TaskAttempt++) {
            Start-Sleep -Milliseconds 500
            try { $TaskHealth = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2; if ($TaskHealth.mode -eq 'demo' -and $TaskHealth.project_root -eq $ProjectRoot) { $TaskReady=$true; break } } catch {}
            if ($TaskServer.HasExited) { break }
        }
        if (-not $TaskReady) { throw 'Disposable browser test server failed to start.' }
        $env:APP_URL = "http://127.0.0.1:$Port"
        foreach ($TaskBrowserScript in @('browser-smoke.mjs','browser-complete.mjs','browser-races.mjs','browser-layout.mjs','browser-hybrid.mjs','browser-sidebar.mjs')) {
            & node (Join-Path $PSScriptRoot $TaskBrowserScript)
            if ($LASTEXITCODE -ne 0) { throw "Browser verification failed: $TaskBrowserScript" }
        }
    } finally {
        $TaskChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($TaskServer.Id)"
        foreach ($TaskChild in $TaskChildren) {
            if ($TaskChild.CommandLine -and $TaskChild.CommandLine.Contains('browser-test-server.py')) { Stop-Process -Id $TaskChild.ProcessId -ErrorAction SilentlyContinue }
        }
        if (-not $TaskServer.HasExited) { $TaskServer.Kill() }
    }
}
Write-Host 'Verification complete. Browser records use isolated project-local demo data, with no paid AI calls.'
