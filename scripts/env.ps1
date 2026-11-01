$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PIP_CACHE_DIR = Join-Path $ProjectRoot '.cache\pip'
$env:npm_config_cache = Join-Path $ProjectRoot '.cache\npm'
$env:HF_HOME = Join-Path $ProjectRoot '.cache\huggingface'
$env:HF_HUB_CACHE = Join-Path $ProjectRoot '.cache\huggingface\hub'
$env:SENTENCE_TRANSFORMERS_HOME = Join-Path $ProjectRoot 'models'
$env:TORCH_HOME = Join-Path $ProjectRoot '.cache\torch'
$env:NLTK_DATA = Join-Path $ProjectRoot '.cache\nltk'
$env:TIKTOKEN_CACHE_DIR = Join-Path $ProjectRoot '.cache\tiktoken'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $ProjectRoot '.cache\ms-playwright'
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = '1'
$env:XDG_CACHE_HOME = Join-Path $ProjectRoot '.cache'
$env:TEMP = Join-Path $ProjectRoot '.cache\tmp'
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path $ProjectRoot 'backend'
foreach ($taskDirectory in @($env:PIP_CACHE_DIR, $env:npm_config_cache, $env:TEMP, (Join-Path $ProjectRoot 'logs'), (Join-Path $ProjectRoot 'artifacts'))) {
    New-Item -ItemType Directory -Path $taskDirectory -Force | Out-Null
}
