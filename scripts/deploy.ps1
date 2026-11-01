param(
    [ValidateSet('check','init','up','down','status','logs','migrate')]
    [string]$Action = 'check'
)
$ErrorActionPreference = 'Stop'
$TaskProject = Split-Path -Parent $PSScriptRoot
$TaskPrivateEnv = Join-Path $TaskProject '.env.compose'
$TaskComposeFile = Join-Path $TaskProject 'deploy\compose.yaml'

function Read-TaskDotEnv([string]$Path) {
    $TaskValues = @{}
    if (Test-Path -LiteralPath $Path) {
        foreach ($TaskLine in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
            if ($TaskLine -match '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
                $TaskValue = $Matches[2].Trim()
                if ($TaskValue.Length -ge 2 -and
                    (($TaskValue.StartsWith('"') -and $TaskValue.EndsWith('"')) -or
                     ($TaskValue.StartsWith("'") -and $TaskValue.EndsWith("'")))) {
                    $TaskValue = $TaskValue.Substring(1, $TaskValue.Length - 2)
                }
                $TaskValues[$Matches[1]] = $TaskValue
            }
        }
    }
    return $TaskValues
}
function New-TaskSecret {
    $TaskBytes = New-Object byte[] 32
    $TaskGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $TaskGenerator.GetBytes($TaskBytes) } finally { $TaskGenerator.Dispose() }
    return ([BitConverter]::ToString($TaskBytes)).Replace('-', '').ToLowerInvariant()
}
function Invoke-TaskCompose {
    & docker compose --env-file $TaskPrivateEnv -f $TaskComposeFile @args
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed; inspect the service logs without sharing private configuration.' }
}
function Sync-TaskJwt {
    $TaskSecretPath = Join-Path $TaskProject 'data\container\.jwt-secret'
    if (-not (Test-Path -LiteralPath $TaskSecretPath)) { throw 'Migrated JWT secret file is missing.' }
    $TaskJwt = [IO.File]::ReadAllText($TaskSecretPath).Trim()
    if ($TaskJwt -notmatch '^[A-Za-z0-9_-]{32,}$') { throw 'Migrated JWT secret has an invalid format.' }
    $TaskPrivateText = [IO.File]::ReadAllText($TaskPrivateEnv)
    $TaskPrivateText = [regex]::Replace($TaskPrivateText, '(?m)^JWT_SECRET=.*$', "JWT_SECRET='$TaskJwt'")
    [IO.File]::WriteAllText($TaskPrivateEnv, $TaskPrivateText, (New-Object Text.UTF8Encoding($false)))
}

if ($Action -eq 'check') {
    & "$PSScriptRoot\check-environment.ps1"
    return
}
if ($Action -eq 'init') {
    if (Test-Path -LiteralPath $TaskPrivateEnv) {
        throw '.env.compose already exists. It has not been overwritten; update private settings deliberately.'
    }
    $TaskSource = Read-TaskDotEnv (Join-Path $TaskProject '.env')
    if (-not $TaskSource['DEEPSEEK_API_KEY']) { throw 'Put DEEPSEEK_API_KEY in the private project .env first.' }
    $TaskValues = [ordered]@{
        MYSQL_PASSWORD = New-TaskSecret
        MYSQL_ROOT_PASSWORD = New-TaskSecret
        MINIO_ACCESS_KEY = ('zhima' + (New-TaskSecret).Substring(0, 15))
        MINIO_SECRET_KEY = New-TaskSecret
        JWT_SECRET = New-TaskSecret
        INDEX_TOKEN = New-TaskSecret
        DEEPSEEK_API_KEY = $TaskSource['DEEPSEEK_API_KEY']
        DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
        DEEPSEEK_MODEL = 'deepseek-flash'
        HTTP_PORT = '8765'
        JUDGE0_URL = ''
        JUDGE0_KEY = ''
    }
    foreach ($TaskName in @('DEEPSEEK_BASE_URL','DEEPSEEK_MODEL','JUDGE0_URL','JUDGE0_KEY')) {
        if ($TaskSource[$TaskName]) { $TaskValues[$TaskName] = $TaskSource[$TaskName] }
    }
    $TaskLines = @('# Private generated configuration. Do not commit or share.')
    foreach ($TaskEntry in $TaskValues.GetEnumerator()) {
        if ([string]$TaskEntry.Value -match "['\r\n]") { throw 'A setting contains an unsupported quote or newline; no private file was written.' }
        $TaskLines += ($TaskEntry.Key + "='" + $TaskEntry.Value + "'")
    }
    [IO.File]::WriteAllLines($TaskPrivateEnv, $TaskLines, (New-Object Text.UTF8Encoding($false)))
    Write-Host 'Created private .env.compose with random database, object storage, index and JWT credentials.'
    Write-Host 'The DeepSeek key was read from .env and has not been printed.'
    return
}
if ($Action -eq 'up' -or $Action -eq 'migrate') {
    & "$PSScriptRoot\check-environment.ps1" -RequireDocker -RequireModel
} else {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is unavailable. No system changes were attempted.' }
}
if (-not (Test-Path -LiteralPath $TaskPrivateEnv)) { throw 'Run scripts/deploy.ps1 -Action init first.' }
# Never print `compose config`: it expands private credentials. --quiet only validates.
Invoke-TaskCompose config --quiet
switch ($Action) {
    'up' {
        foreach ($TaskRelative in @('data/mysql','data/redis','data/minio','data/chroma','data/container','logs/container','logs/index','logs/nginx','.cache/container/tmp','.cache/container-index/tmp','.cache/backups/compose')) {
            New-Item -ItemType Directory -Path (Join-Path $TaskProject $TaskRelative) -Force | Out-Null
        }
        # Import the preserved local database before the API can seed an empty MySQL installation.
        $TaskLocalDatabase = Join-Path $TaskProject 'data\zhima.db'
        $TaskImportMarker = Join-Path $TaskProject 'data\container\.source-imported'
        if ((Test-Path -LiteralPath $TaskLocalDatabase) -and -not (Test-Path -LiteralPath $TaskImportMarker)) {
            Invoke-TaskCompose up --build -d --wait --wait-timeout 600 mysql redis minio index
            Invoke-TaskCompose run --rm --no-deps --volume "${TaskProject}/data:/app/legacy:ro" app python -m app.migration --source /app/legacy/zhima.db
            Sync-TaskJwt
            [IO.File]::WriteAllText($TaskImportMarker, 'Imported preserved local SQLite into empty MySQL; see private migration report.')
        }
        Invoke-TaskCompose up --build -d --wait --wait-timeout 600
        Invoke-TaskCompose exec -T app python -m app.services.vectors sync
        $TaskSettings = Read-TaskDotEnv $TaskPrivateEnv
        Write-Host "Ready: http://127.0.0.1:$($TaskSettings['HTTP_PORT'])"
        Write-Host 'Container health is a startup check. Complete the teaching workflow acceptance checks separately.'
    }
    'down' { Invoke-TaskCompose down }
    'status' { Invoke-TaskCompose ps }
    'logs' { Invoke-TaskCompose logs --tail 100 }
    'migrate' {
        & "$PSScriptRoot\backup.ps1" -Mode Compose -LeaveStopped
        $TaskBackupRoot = Join-Path $TaskProject '.cache\backups\compose'
        $TaskLatest = Get-ChildItem -LiteralPath $TaskBackupRoot -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'COMPLETE') } | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
        if (-not $TaskLatest) { throw 'No complete Compose backup was found.' }
        try {
            Invoke-TaskCompose run --rm --no-deps app python -m app.migration --upgrade --backup-directory "/app/.cache/backups/compose/$($TaskLatest.Name)"
            Sync-TaskJwt
        }
        finally { Invoke-TaskCompose up -d --wait --wait-timeout 600 }
    }
}
