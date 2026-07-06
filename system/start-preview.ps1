$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$backendPython = Join-Path $backendDir '.venv\Scripts\python.exe'
$frontendNpm = if (Get-Command npm.cmd -ErrorAction SilentlyContinue) {
    (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
} elseif (Test-Path 'D:\node\npm.cmd') {
    'D:\node\npm.cmd'
} else {
    $null
}

if (-not (Test-Path $backendPython)) {
    throw "Backend Python not found: $backendPython"
}

if (-not $frontendNpm) {
    throw 'npm.cmd not found in PATH and D:\node\npm.cmd is unavailable.'
}

function Stop-StaleLocalPortOwner {
    param(
        [int]$Port,
        [string]$Name,
        [string]$ExpectedPattern
    )

    $owners = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($ownerPid in $owners) {
        if (-not $ownerPid) {
            continue
        }

        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerPid" -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }

        $commandLine = [string]$process.CommandLine
        if ($commandLine -notmatch $ExpectedPattern) {
            throw "$Name port $Port is already used by PID $ownerPid and does not look like a CogGuard process: $commandLine"
        }

        Write-Host "Stopping stale $Name process on 127.0.0.1:$Port (PID $ownerPid)..."
        Stop-Process -Id $ownerPid -Force
        Start-Sleep -Seconds 1
    }
}

Stop-StaleLocalPortOwner -Port 8000 -Name 'backend' -ExpectedPattern 'uvicorn\s+app\.main:app'
Stop-StaleLocalPortOwner -Port 5173 -Name 'frontend' -ExpectedPattern 'vite(\.js)?|npm.*run\s+dev'

$backendCommand = "cd /d `"$backendDir`" && `"$backendPython`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

$frontendCommand = "cd /d `"$frontendDir`" && `"$frontendNpm`" run dev -- --host 127.0.0.1 --port 5173"

Start-Process cmd.exe -ArgumentList @(
    '/k',
    $backendCommand
)

Start-Process cmd.exe -ArgumentList @(
    '/k',
    $frontendCommand
)

Write-Host 'Preview services are starting in two PowerShell windows...'
Write-Host 'Backend health: http://127.0.0.1:8000/api/v1/health'
Write-Host 'Frontend preview: http://127.0.0.1:5173/preview'
Write-Host 'Keep both windows open while previewing.'
