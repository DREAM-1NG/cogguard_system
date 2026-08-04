[CmdletBinding()]
param(
    [string]$Database,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$opsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$systemRoot = Split-Path -Parent $opsRoot
$composeFile = Join-Path $systemRoot 'docker-compose.yml'
$environmentFile = Join-Path $systemRoot '.env'

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

$docker = Get-Command docker.exe -ErrorAction SilentlyContinue
if (-not $docker) {
    throw 'docker.exe is required to apply MongoDB performance indexes.'
}

if (-not $Database) {
    $Database = Get-DotEnvValue -Name 'MONGO_DATABASE' -DefaultValue 'cogguard'
}
$mongoUser = Get-DotEnvValue -Name 'MONGO_USER' -DefaultValue 'cogguard'
$mongoPassword = Get-DotEnvValue -Name 'MONGO_PASSWORD'
if (-not $mongoPassword) {
    throw 'MONGO_PASSWORD is required in system/.env.'
}

$arguments = @(
    'compose', '-f', $composeFile,
    'exec', '-T',
    '-e', "MONGO_DATABASE=$Database"
)
if ($DryRun) {
    $arguments += @('-e', 'MONGO_PERFORMANCE_INDEXES_DRY_RUN=1')
}
$arguments += @(
    'mongodb',
    'mongosh', '--quiet',
    '--username', $mongoUser,
    '--password', $mongoPassword,
    '--authenticationDatabase', 'admin',
    '--file', '/opt/cogguard-ops/apply_performance_indexes.js'
)

& $docker.Source @arguments
if ($LASTEXITCODE -ne 0) {
    throw "MongoDB performance-index operation failed with exit code $LASTEXITCODE."
}
