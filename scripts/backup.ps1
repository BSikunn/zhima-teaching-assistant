param([ValidateSet('Local','Compose')][string]$Mode = 'Local', [switch]$LeaveStopped)
$ErrorActionPreference = 'Stop'
$TaskProject = Split-Path -Parent $PSScriptRoot
$TaskStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
if ($Mode -eq 'Local') {
    . "$PSScriptRoot\env.ps1"
    $TaskPython = Join-Path $TaskProject '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $TaskPython)) { throw 'The project Python environment is missing.' }
    & $TaskPython -m app.migration --backup
    if ($LASTEXITCODE -ne 0) { throw 'Local backup failed.' }
    return
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is unavailable.' }
$TaskPrivateEnv = Join-Path $TaskProject '.env.compose'
if (-not (Test-Path -LiteralPath $TaskPrivateEnv)) { throw 'Private .env.compose is missing.' }
$TaskCompose = @('compose','--env-file',$TaskPrivateEnv,'-f',(Join-Path $TaskProject 'deploy\compose.yaml'))
function Invoke-TaskBackupCompose {
    & docker @TaskCompose @args
    if ($LASTEXITCODE -ne 0) { throw 'A Compose backup step failed; keep any partial backup for diagnosis.' }
}
$TaskRunning = @(& docker @TaskCompose ps --services --status running)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect running services.' }
if ($TaskRunning -notcontains 'mysql') { throw 'MySQL must already be running; backup never starts a new database.' }
$TaskBackup = Join-Path $TaskProject ".cache\backups\compose\$TaskStamp"
New-Item -ItemType Directory -Path $TaskBackup -Force | Out-Null
$TaskPause = @($TaskRunning | Where-Object { $_ -in @('nginx','app','worker','index','redis','minio') })
try {
    if ($TaskPause.Count) { Invoke-TaskBackupCompose stop -t 180 @TaskPause }
    # SQL is written inside a project bind mount, avoiding PowerShell 5.1 native redirection encoding changes.
    $TaskDump = 'umask 077; MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -u root --single-transaction --routines --triggers --events --no-tablespaces --set-gtid-purged=OFF zhima > "/backups/$1/database.sql"'
    Invoke-TaskBackupCompose exec -T mysql sh -c $TaskDump backup $TaskStamp
    foreach ($TaskName in @('container','chroma','redis','minio')) {
        $TaskSource = Join-Path $TaskProject "data\$TaskName"
        if (Test-Path -LiteralPath $TaskSource) {
            Copy-Item -LiteralPath $TaskSource -Destination (Join-Path $TaskBackup $TaskName) -Recurse -Force
        }
    }
    Copy-Item -LiteralPath $TaskPrivateEnv -Destination (Join-Path $TaskBackup '.env.compose')
    $TaskLocalEnv = Join-Path $TaskProject '.env'
    if (Test-Path -LiteralPath $TaskLocalEnv) { Copy-Item -LiteralPath $TaskLocalEnv -Destination (Join-Path $TaskBackup '.env') }
    Copy-Item -LiteralPath (Join-Path $TaskProject 'deploy\compose.yaml') -Destination (Join-Path $TaskBackup 'compose.yaml')
    $TaskManifest = @{ created_at = (Get-Date).ToUniversalTime().ToString('o'); kind = 'compose-consistent-stop'; running_services = $TaskRunning; sql = 'database.sql'; includes_private_credentials = $true }
    $TaskManifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $TaskBackup 'manifest.json') -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $TaskBackup 'COMPLETE') -Value 'Backup steps completed; restore verification remains required.' -Encoding ASCII
    Write-Host "Backup: $TaskBackup"
    Write-Host 'This directory contains private credentials. Do not share or commit it.'
} finally {
    if ($TaskPause.Count -and -not $LeaveStopped) { Invoke-TaskBackupCompose start @TaskPause }
}
