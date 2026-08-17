[CmdletBinding()]
param(
    [switch]$SyncHistoricalData,
    [switch]$SkipDocker,
    [switch]$SkipFrontend,
    [switch]$DevelopmentFrontend,
    [switch]$SkipIndexPreparation,
    [switch]$DemoWarmup,
    [switch]$SkipDemoWarmup,
    [switch]$DemoWarmupStrict,
    [string]$DemoEventId = '',
    [string]$DemoCaseId = '',
    [int]$DemoCoordinationDatasetId = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$backendPython = Join-Path $backendDir '.venv\Scripts\python.exe'
$environmentFile = Join-Path $root '.env'
$composeFile = Join-Path $root 'docker-compose.yml'
$logsDir = Join-Path $root 'logs'

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

if ($SkipFrontend -and $DevelopmentFrontend) {
    throw 'DevelopmentFrontend cannot be combined with SkipFrontend.'
}

if ($SkipDemoWarmup -and $DemoWarmup) {
    throw 'SkipDemoWarmup cannot be combined with DemoWarmup.'
}

if (-not (Test-Path $backendPython)) {
    throw "Backend Python not found: $backendPython"
}

if (-not $SkipDocker -and -not $dockerExe) {
    throw 'docker.exe not found. Start Docker Desktop first, or rerun with -SkipDocker if services are already up.'
}

if (-not $SkipFrontend -and -not $DevelopmentFrontend -and -not $dockerExe) {
    throw 'docker.exe is required for the default static frontend delivery. Use -DevelopmentFrontend only while editing frontend source.'
}

if ($DevelopmentFrontend -and -not $frontendNpm) {
    throw 'npm.cmd not found in PATH and D:\node\npm.cmd is unavailable.'
}

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$DefaultValue = ''
    )

    if (-not (Test-Path $environmentFile)) {
        return $DefaultValue
    }

    foreach ($line in Get-Content -LiteralPath $environmentFile) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $DefaultValue
}

$configuredDemoUsername = [Environment]::GetEnvironmentVariable('COGGUARD_DEMO_USERNAME')
if (-not $configuredDemoUsername) {
    $configuredDemoUsername = Get-DotEnvValue -Name 'COGGUARD_DEMO_USERNAME'
}
$configuredDemoPassword = [Environment]::GetEnvironmentVariable('COGGUARD_DEMO_PASSWORD')
if (-not $configuredDemoPassword) {
    $configuredDemoPassword = Get-DotEnvValue -Name 'COGGUARD_DEMO_PASSWORD'
}
$runDemoWarmup = $DemoWarmup -or (
    -not $SkipDemoWarmup -and
    $configuredDemoUsername -and
    $configuredDemoPassword
)
if ($DemoWarmupStrict -and -not $runDemoWarmup) {
    throw 'DemoWarmupStrict requires demo credentials or the DemoWarmup switch.'
}

$frontendPort = 0
$frontendPortValue = Get-DotEnvValue -Name 'FRONTEND_PORT' -DefaultValue '5173'
if (-not [int]::TryParse($frontendPortValue, [ref]$frontendPort) -or $frontendPort -lt 1 -or $frontendPort -gt 65535) {
    throw "FRONTEND_PORT must be a valid TCP port; received '$frontendPortValue'."
}
$mongoPort = 0
$mongoPortValue = Get-DotEnvValue -Name 'MONGO_PORT' -DefaultValue '27017'
if (-not [int]::TryParse($mongoPortValue, [ref]$mongoPort) -or $mongoPort -lt 1 -or $mongoPort -gt 65535) {
    throw "MONGO_PORT must be a valid TCP port; received '$mongoPortValue'."
}

function Test-TcpPort {
    param(
        [string]$Hostname,
        [int]$Port
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $asyncResult = $client.BeginConnect($Hostname, $Port, $null, $null)
        $connected = $asyncResult.AsyncWaitHandle.WaitOne(1000, $false)
        if (-not $connected) {
            $client.Close()
            return $false
        }
        $client.EndConnect($asyncResult)
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

    throw "$Name did not become ready on 127.0.0.1:${Port} within $TimeoutSeconds seconds."
}

function Test-HttpEndpoint {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    } catch {
        return $false
    }
}

function Wait-HttpEndpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 120,
        [string]$FailureLogPath = ''
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpEndpoint -Url $Url) {
            Write-Host "$Name is ready at $Url"
            return
        }
        Start-Sleep -Seconds 2
    }

    if ($FailureLogPath -and (Test-Path $FailureLogPath)) {
        Write-Host "Last backend log lines from ${FailureLogPath}:"
        Get-Content -LiteralPath $FailureLogPath -Tail 60 | ForEach-Object { Write-Host $_ }
    }
    throw "$Name did not become ready at $Url within $TimeoutSeconds seconds."
}

function Get-LocalPortOwners {
    param([int]$Port)

    return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Stop-StaleLocalPortOwner {
    param(
        [int]$Port,
        [string]$Name,
        [string]$ExpectedPattern
    )

    foreach ($processId in Get-LocalPortOwners -Port $Port) {
        if (-not $processId) {
            continue
        }

        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }

        $commandLine = [string]$process.CommandLine
        if ($commandLine -notmatch $ExpectedPattern) {
            throw "$Name port $Port is already used by PID $processId and does not look like a CogGuard process: $commandLine"
        }

        Write-Host "Stopping stale $Name process on 127.0.0.1:${Port} (PID $processId)..."
        Stop-Process -Id $processId -Force
        Start-Sleep -Seconds 1
    }
}

function Stop-StaleDevelopmentFrontend {
    param([int]$Port)

    $portOwnerProcesses = @(
        foreach ($processId in Get-LocalPortOwners -Port $Port) {
            if ($processId) {
                Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
            }
        }
    )
    $hasDockerOwner = $portOwnerProcesses | Where-Object {
        $commandLine = [string]$_.CommandLine
        $executablePath = [string]$_.ExecutablePath
        $commandLine -match 'docker|com\.docker' -or $executablePath -match 'docker'
    }

    foreach ($process in $portOwnerProcesses) {
        $commandLine = [string]$process.CommandLine
        if ($commandLine -match 'vite(\.js)?|npm(\.cmd)?\s+run\s+dev') {
            Write-Host "Stopping stale Vite process on 127.0.0.1:${Port} (PID $($process.ProcessId))..."
            Stop-Process -Id $process.ProcessId -Force
            Start-Sleep -Seconds 1
            continue
        }
        if ($commandLine -match 'docker|com\.docker') {
            continue
        }
        if ($hasDockerOwner -and $process.Name -ieq 'wslrelay.exe') {
            continue
        }
        throw "Frontend port $Port is already used by PID $($process.ProcessId): $commandLine"
    }
}

function Get-DockerContainerState {
    param([string]$Name)

    $inspectOutput = & $dockerExe inspect $Name 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    $container = ($inspectOutput -join "`n" | ConvertFrom-Json)[0]
    return [PSCustomObject]@{
        Name = $Name
        Image = [string]$container.Config.Image
        Status = [string]$container.State.Status
    }
}

$reusedInfrastructure = $false

if (-not $SkipDocker) {
    Write-Host 'Starting MySQL / MongoDB / Redis with Docker Compose...'
    $requiredInfrastructure = @(
        [PSCustomObject]@{ Name = 'cogguard-mysql'; Image = 'mysql:8.0' },
        [PSCustomObject]@{ Name = 'cogguard-mongodb'; Image = 'mongo:7.0' },
        [PSCustomObject]@{ Name = 'cogguard-redis'; Image = 'redis:7-alpine' }
    )
    $existingInfrastructure = @(
        foreach ($required in $requiredInfrastructure) {
            $state = Get-DockerContainerState -Name $required.Name
            if ($null -ne $state) {
                $state
            }
        }
    )

    if ($existingInfrastructure.Count -eq $requiredInfrastructure.Count) {
        $reusedInfrastructure = $true
        foreach ($required in $requiredInfrastructure) {
            $state = $existingInfrastructure | Where-Object Name -eq $required.Name | Select-Object -First 1
            if ($state.Image -ne $required.Image) {
                throw "$($required.Name) uses image '$($state.Image)', expected '$($required.Image)'."
            }
            if ($state.Status -ne 'running') {
                & $dockerExe start $required.Name | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to start existing infrastructure container $($required.Name)."
                }
            }
        }
        Write-Host 'Reusing compatible CogGuard infrastructure containers and their existing data volumes.'
    } elseif ($existingInfrastructure.Count -eq 0) {
        & $dockerExe compose --project-directory $root -f $composeFile up -d mysql mongodb redis
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Compose infrastructure startup failed with exit code $LASTEXITCODE."
        }
    } else {
        $foundNames = ($existingInfrastructure | Select-Object -ExpandProperty Name) -join ', '
        throw "Partial CogGuard infrastructure already exists ($foundNames). Refusing to create a mixed container set."
    }
    Wait-TcpPort -Name 'MySQL' -Port 3306
    Wait-TcpPort -Name 'MongoDB' -Port $mongoPort
    Wait-TcpPort -Name 'Redis' -Port 6379

    if (-not $SkipIndexPreparation) {
        Write-Host 'Preparing idempotent MongoDB delivery indexes...'
        $indexScript = Join-Path $root 'ops\Apply-MongoPerformanceIndexes.ps1'
        if ($reusedInfrastructure) {
            & $indexScript -DockerExecutable $dockerExe -ContainerName 'cogguard-mongodb' -DryRun
            & $indexScript -DockerExecutable $dockerExe -ContainerName 'cogguard-mongodb'
        } else {
            & $indexScript -DockerExecutable $dockerExe -DryRun
            & $indexScript -DockerExecutable $dockerExe
        }
    }
} elseif (-not $SkipIndexPreparation) {
    Write-Host 'Skipping MongoDB index preparation because -SkipDocker was requested.'
}

Stop-StaleLocalPortOwner -Port 8000 -Name 'backend' -ExpectedPattern 'uvicorn\s+app\.main:app'

Write-Host 'Applying database migrations...'
Push-Location $backendDir
try {
    & $backendPython -m alembic upgrade heads

    if ($SyncHistoricalData) {
        Write-Host 'Importing existing social runtime JSONL data into MongoDB...'
        & $backendPython (Join-Path $backendDir 'scripts\import_mediacrawler_jsonl.py')
    }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$runStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backendOutputLog = Join-Path $logsDir "backend-$runStamp.out.log"
$backendErrorLog = Join-Path $logsDir "backend-$runStamp.err.log"
$accountTrainingOutputLog = Join-Path $logsDir "account-training-worker-$runStamp.out.log"
$accountTrainingErrorLog = Join-Path $logsDir "account-training-worker-$runStamp.err.log"
$accountTrainingBeatOutputLog = Join-Path $logsDir "account-training-beat-$runStamp.out.log"
$accountTrainingBeatErrorLog = Join-Path $logsDir "account-training-beat-$runStamp.err.log"
$accountTrainingBeatSchedule = Join-Path $logsDir 'account-training-beat.schedule'

function Stop-StaleAccountModelWorkers {
    $backendPythonPath = [System.IO.Path]::GetFullPath($backendPython)
    $workers = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $commandLine = [string]$_.CommandLine
            $executablePath = [string]$_.ExecutablePath
            [string]::Equals(
                $executablePath,
                $backendPythonPath,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -and
            $commandLine -match '(?i)(?:^|\s)-m\s+celery(?:\s|$)' -and
            $commandLine -match '(?i)(?:account_training|account_evaluation|account-training@|account-model@)'
        }
    foreach ($worker in $workers) {
        Write-Host "Stopping stale account-model worker (PID $($worker.ProcessId))..."
        Stop-Process -Id $worker.ProcessId -Force
    }
}

function Stop-StaleAccountTrainingSchedulers {
    $backendPythonPath = [System.IO.Path]::GetFullPath($backendPython)
    $schedulers = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $commandLine = [string]$_.CommandLine
            $executablePath = [string]$_.ExecutablePath
            [string]::Equals(
                $executablePath,
                $backendPythonPath,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -and
            $commandLine -match '(?i)(?:^|\s)-m\s+celery(?:\s|$)' -and
            $commandLine -match '(?i)(?:^|\s)beat(?:\s|$)' -and
            $commandLine -match '(?i)account-training-beat'
        }
    foreach ($scheduler in $schedulers) {
        Write-Host "Stopping stale account-training scheduler (PID $($scheduler.ProcessId))..."
        Stop-Process -Id $scheduler.ProcessId -Force
    }
}

Write-Host 'Starting backend without the development reloader...'
$backendStartParameters = @{
    FilePath = $backendPython
    WorkingDirectory = $backendDir
    ArgumentList = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000')
    WindowStyle = 'Hidden'
    RedirectStandardOutput = $backendOutputLog
    RedirectStandardError = $backendErrorLog
    PassThru = $true
}
$backendProcess = Start-Process @backendStartParameters
Wait-HttpEndpoint -Name 'Backend API' -Url 'http://127.0.0.1:8000/api/v2/health' -FailureLogPath $backendErrorLog
Write-Host "Backend PID: $($backendProcess.Id); logs: $logsDir"

Stop-StaleAccountModelWorkers
Write-Host 'Starting dedicated account-model Celery worker (training and evaluation, concurrency 1)...'
$accountTrainingStartParameters = @{
    FilePath = $backendPython
    WorkingDirectory = $backendDir
    ArgumentList = @('-m', 'celery', '-A', 'app.celery_app', 'worker', '--loglevel=info', '--queues', 'account_training,account_evaluation', '--concurrency', '1', '--pool', 'solo', '--hostname', 'account-training@%h')
    WindowStyle = 'Hidden'
    RedirectStandardOutput = $accountTrainingOutputLog
    RedirectStandardError = $accountTrainingErrorLog
    PassThru = $true
}
$accountTrainingProcess = Start-Process @accountTrainingStartParameters
Start-Sleep -Seconds 2
if ($accountTrainingProcess.HasExited) {
    if (Test-Path $accountTrainingErrorLog) {
        Get-Content -LiteralPath $accountTrainingErrorLog -Tail 60 | ForEach-Object { Write-Host $_ }
    }
    throw "Account-training worker exited during startup with exit code $($accountTrainingProcess.ExitCode)."
}
Write-Host "Account-training worker PID: $($accountTrainingProcess.Id); logs: $accountTrainingOutputLog, $accountTrainingErrorLog"

Stop-StaleAccountTrainingSchedulers
Write-Host 'Starting account-training Celery Beat scheduler...'
$accountTrainingBeatStartParameters = @{
    FilePath = $backendPython
    WorkingDirectory = $backendDir
    ArgumentList = @('-m', 'celery', '-A', 'app.celery_app', 'beat', '--loglevel=info', '--schedule', $accountTrainingBeatSchedule)
    WindowStyle = 'Hidden'
    RedirectStandardOutput = $accountTrainingBeatOutputLog
    RedirectStandardError = $accountTrainingBeatErrorLog
    PassThru = $true
}
$accountTrainingBeatProcess = Start-Process @accountTrainingBeatStartParameters
Start-Sleep -Seconds 2
if ($accountTrainingBeatProcess.HasExited) {
    if (Test-Path $accountTrainingBeatErrorLog) {
        Get-Content -LiteralPath $accountTrainingBeatErrorLog -Tail 60 | ForEach-Object { Write-Host $_ }
    }
    throw "Account-training Beat scheduler exited during startup with exit code $($accountTrainingBeatProcess.ExitCode)."
}
Write-Host "Account-training Beat PID: $($accountTrainingBeatProcess.Id); logs: $accountTrainingBeatOutputLog, $accountTrainingBeatErrorLog"

if ($runDemoWarmup) {
    $warmupScript = Join-Path $root 'ops\Invoke-DemoWarmup.ps1'
    $warmupParameters = @{
        BackendOrigin = 'http://127.0.0.1:8000'
    }
    if ($DemoEventId) {
        $warmupParameters.EventId = $DemoEventId
    }
    if ($DemoCaseId) {
        $warmupParameters.CaseId = $DemoCaseId
    }
    if ($DemoCoordinationDatasetId -gt 0) {
        $warmupParameters.CoordinationDatasetId = $DemoCoordinationDatasetId
    }
    if ($DemoWarmupStrict) {
        $warmupParameters.Strict = $true
    }
    Write-Host 'Preloading authenticated demo data before frontend delivery...'
    & $warmupScript @warmupParameters
}

if (-not $SkipFrontend) {
    if ($DevelopmentFrontend) {
        Stop-StaleLocalPortOwner -Port $frontendPort -Name 'frontend' -ExpectedPattern 'vite(\.js)?|npm(\.cmd)?\s+run\s+dev'
        $frontendOutputLog = Join-Path $logsDir "frontend-vite-$runStamp.out.log"
        $frontendErrorLog = Join-Path $logsDir "frontend-vite-$runStamp.err.log"
        Write-Host 'Starting Vite only because -DevelopmentFrontend was requested...'
        $frontendStartParameters = @{
            FilePath = $frontendNpm
            WorkingDirectory = $frontendDir
            ArgumentList = @('run', 'dev', '--', '--host', '127.0.0.1', '--port', $frontendPort)
            WindowStyle = 'Hidden'
            RedirectStandardOutput = $frontendOutputLog
            RedirectStandardError = $frontendErrorLog
        }
        Start-Process @frontendStartParameters | Out-Null
        Wait-HttpEndpoint -Name 'Development frontend' -Url "http://127.0.0.1:$frontendPort/" -FailureLogPath $frontendErrorLog
    } else {
        Stop-StaleDevelopmentFrontend -Port $frontendPort
        Write-Host 'Building the optimized frontend and starting static delivery...'
        & $dockerExe compose --project-directory $root -f $composeFile --profile production-ui up -d --build frontend_static
        if ($LASTEXITCODE -ne 0) {
            throw "Static frontend startup failed with exit code $LASTEXITCODE."
        }
        Wait-HttpEndpoint -Name 'Static frontend' -Url "http://127.0.0.1:$frontendPort/healthz" -TimeoutSeconds 180
    }
}

Write-Host ''
Write-Host 'CogGuard is ready.'
Write-Host 'Backend health: http://127.0.0.1:8000/api/v2/health'
if (-not $SkipFrontend) {
    Write-Host "Login: http://127.0.0.1:$frontendPort/login"
    Write-Host "Dashboard: http://127.0.0.1:$frontendPort/dashboard"
    Write-Host "Event review: http://127.0.0.1:$frontendPort/risk"
}
Write-Host 'Default mode uses the optimized static frontend. Use -DevelopmentFrontend only for frontend source work.'
if ($runDemoWarmup) {
    Write-Host 'Demo mode preloaded authenticated data before the frontend was exposed.'
}
if ($runDemoWarmup -and -not $DemoWarmup) {
    Write-Host 'Configured demo credentials enabled automatic authenticated warmup.'
}
if ($SkipDemoWarmup) {
    Write-Host 'Demo warmup was explicitly skipped.'
}
