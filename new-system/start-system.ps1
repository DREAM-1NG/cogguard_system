param(
    [switch]$SyncHistoricalData,
    [switch]$SkipDocker,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$backendPython = Join-Path $backendDir '.venv\Scripts\python.exe'

$dockerExe = if (Get-Command docker.exe -ErrorAction SilentlyContinue) {
    (Get-Command docker.exe -ErrorAction SilentlyContinue).Source
} elseif (Test-Path 'C:\Program Files\Docker\Docker\resources\bin\docker.exe') {
    'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
} else {
    $null
}

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

if (-not $SkipFrontend -and -not $frontendNpm) {
    throw 'npm.cmd not found in PATH and D:\node\npm.cmd is unavailable.'
}

if (-not $SkipDocker -and -not $dockerExe) {
    throw 'docker.exe not found. Start Docker Desktop first, or rerun with -SkipDocker if services are already up.'
}

function Test-TcpPort {
    param(
        [string]$Hostname,
        [int]$Port
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($Hostname, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(1000, $false)
        if (-not $ok) {
            $client.Close()
            return $false
        }
        $client.EndConnect($iar)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Wait-TcpPort {
    param(
        [string]$Name,
        [int]$Port,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -Hostname '127.0.0.1' -Port $Port) {
            Write-Host "$Name is ready on 127.0.0.1:$Port"
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "$Name did not become ready on 127.0.0.1:$Port within $TimeoutSeconds seconds."
}

if (-not $SkipDocker) {
    Write-Host 'Starting MySQL / MongoDB / Redis with Docker Compose...'
    & $dockerExe compose -f (Join-Path $root 'docker-compose.yml') up -d
    Wait-TcpPort -Name 'MySQL' -Port 3306
    Wait-TcpPort -Name 'MongoDB' -Port 27017
    Wait-TcpPort -Name 'Redis' -Port 6379
}

Write-Host 'Applying database migrations...'
Push-Location $backendDir
try {
    & $backendPython -m alembic upgrade head

    if ($SyncHistoricalData) {
        Write-Host 'Importing existing MediaCrawler JSONL data into MongoDB...'
        & $backendPython (Join-Path $backendDir 'scripts\import_mediacrawler_jsonl.py')
    }
} finally {
    Pop-Location
}

$backendCommand = "cd /d `"$backendDir`" && `"$backendPython`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process cmd.exe -ArgumentList @(
    '/k',
    $backendCommand
)

if (-not $SkipFrontend) {
    $frontendCommand = "cd /d `"$frontendDir`" && `"$frontendNpm`" run dev -- --host 127.0.0.1 --port 5173"
    Start-Process cmd.exe -ArgumentList @(
        '/k',
        $frontendCommand
    )
}

Write-Host ''
Write-Host 'System startup commands have been launched in new terminal windows.'
Write-Host 'Backend health: http://127.0.0.1:8000/api/v1/health'
if (-not $SkipFrontend) {
    Write-Host 'Frontend preview: http://127.0.0.1:5173/preview'
    Write-Host 'Coordination page: http://127.0.0.1:5173/coordination?preview=1'
}
Write-Host 'Keep the opened terminal windows running while using the system.'
