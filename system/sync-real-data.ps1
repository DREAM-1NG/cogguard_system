param(
    [string[]]$Platform,
    [string[]]$Date,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'
$backendPython = Join-Path $backendDir '.venv\Scripts\python.exe'
$importScript = Join-Path $backendDir 'scripts\import_mediacrawler_jsonl.py'

if (-not (Test-Path $backendPython)) {
    throw "Backend Python not found: $backendPython"
}

if (-not (Test-Path $importScript)) {
    throw "Import script not found: $importScript"
}

$args = @($importScript)
foreach ($item in ($Platform | Where-Object { $_ })) {
    $args += @('--platform', $item)
}
foreach ($item in ($Date | Where-Object { $_ })) {
    $args += @('--date', $item)
}
if ($DryRun) {
    $args += '--dry-run'
}

Push-Location $backendDir
try {
    & $backendPython @args
} finally {
    Pop-Location
}
