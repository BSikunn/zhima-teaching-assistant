param([switch]$RequireDocker, [switch]$RequireModel)
$ErrorActionPreference = 'Stop'
$TaskProject = Split-Path -Parent $PSScriptRoot
Write-Host "Project: $TaskProject"
Write-Host 'This check does not install components, pull images, or modify Docker settings.'
$TaskPython = Join-Path $TaskProject '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $TaskPython) {
    & $TaskPython --version
    if ($LASTEXITCODE -ne 0) { throw 'Project Python is not usable.' }
} else { Write-Host 'Local Python environment: missing (Compose uses Python 3.11).' }
$TaskModel = Join-Path $TaskProject 'models\bge-small-zh-v1.5'
$TaskModelReady = (Test-Path -LiteralPath (Join-Path $TaskModel 'config.json')) -and
    ((Test-Path -LiteralPath (Join-Path $TaskModel 'model.safetensors')) -or
     (Test-Path -LiteralPath (Join-Path $TaskModel 'pytorch_model.bin')))
if ($TaskModelReady) { Write-Host 'BGE model: local files found; actual loading remains a runtime check.' }
else {
    Write-Host 'BGE model: missing/incomplete. Use project scripts/download-models.py before Compose up.'
    if ($RequireModel) { throw 'A complete local BGE model is required; automatic container downloads are disabled.' }
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'Docker: unavailable. Prepare the host separately; no installation has been attempted.'
    if ($RequireDocker) { throw 'Docker with Compose v2 is required.' }
    return
}
& docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 is unavailable.' }
$TaskInfoText = & docker info --format '{{json .}}' 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Docker daemon is not reachable.' }
$TaskInfo = $TaskInfoText | ConvertFrom-Json
if ($TaskInfo.OSType -ne 'linux') { throw 'This deployment requires Linux containers.' }
Write-Host "Docker-reported root: $($TaskInfo.DockerRootDir)"
Write-Host 'That Linux path alone does not verify the physical Windows disk/VHD location.'
if ($env:PROJECT_DOCKER_STORAGE_APPROVED -ne '1') {
    Write-Host 'Storage approval: absent. Verify Docker images, build cache and its VM/VHD are project-local first.'
    Write-Host 'After that manual verification, set PROJECT_DOCKER_STORAGE_APPROVED=1 in this shell.'
    if ($RequireDocker) { throw 'Project-local Docker storage has not been explicitly confirmed.' }
} else {
    Write-Host 'Storage approval: operator-confirmed. This script has not independently verified the host/VHD location.'
}
