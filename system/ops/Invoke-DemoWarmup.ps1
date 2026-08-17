[CmdletBinding()]
param(
    [string]$BackendOrigin = 'http://127.0.0.1:8000',
    [string]$Username = '',
    [string]$Password = '',
    [string]$EventId = '',
    [string]$CaseId = '',
    [int]$CoordinationDatasetId = 0,
    [int]$TimeoutSeconds = 180,
    [string]$ReportPath = '',
    [switch]$Strict
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$opsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$systemRoot = Split-Path -Parent $opsRoot
$environmentFile = Join-Path $systemRoot '.env'
$BackendOrigin = $BackendOrigin.TrimEnd('/')

if ($TimeoutSeconds -lt 1) {
    throw 'TimeoutSeconds must be at least 1.'
}

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$DefaultValue = ''
    )

    if (-not (Test-Path -LiteralPath $environmentFile)) {
        return $DefaultValue
    }

    foreach ($line in Get-Content -LiteralPath $environmentFile) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $DefaultValue
}

function Get-ConfiguredValue {
    param(
        [string]$ExplicitValue,
        [string]$EnvironmentName,
        [string]$DotEnvName = '',
        [string]$DefaultValue = ''
    )

    if ($ExplicitValue) {
        return $ExplicitValue
    }
    $environmentValue = [Environment]::GetEnvironmentVariable($EnvironmentName)
    if ($environmentValue) {
        return $environmentValue
    }
    if ($DotEnvName) {
        $dotEnvValue = Get-DotEnvValue -Name $DotEnvName
        if ($dotEnvValue) {
            return $dotEnvValue
        }
    }
    return $DefaultValue
}

$Username = Get-ConfiguredValue -ExplicitValue $Username -EnvironmentName 'COGGUARD_DEMO_USERNAME' -DotEnvName 'COGGUARD_DEMO_USERNAME' -DefaultValue 'admin'
$Password = Get-ConfiguredValue -ExplicitValue $Password -EnvironmentName 'COGGUARD_DEMO_PASSWORD' -DotEnvName 'COGGUARD_DEMO_PASSWORD'
if (-not $Password) {
    $Password = Get-DotEnvValue -Name 'DEFAULT_ADMIN_PASSWORD'
}
$EventId = Get-ConfiguredValue -ExplicitValue $EventId -EnvironmentName 'COGGUARD_DEMO_EVENT_ID' -DotEnvName 'COGGUARD_DEMO_EVENT_ID' -DefaultValue 'trump_visit_2026_05_21'

if (-not $Username -or -not $Password) {
    throw 'Demo credentials are missing. Set COGGUARD_DEMO_USERNAME and COGGUARD_DEMO_PASSWORD, or configure DEFAULT_ADMIN_PASSWORD in system/.env.'
}

if (-not $ReportPath) {
    $reportDirectory = Join-Path $systemRoot 'output\demo-warmup'
    New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
    $ReportPath = Join-Path $reportDirectory ("demo-warmup-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
} else {
    $reportDirectory = Split-Path -Parent $ReportPath
    if ($reportDirectory) {
        New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
    }
}

function Get-PropertyValue {
    param(
        [AllowNull()][object]$Object,
        [string]$Name,
        [AllowNull()][object]$DefaultValue = $null
    )

    if ($null -eq $Object) {
        return $DefaultValue
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $DefaultValue
    }
    return $property.Value
}

function Get-ResponseData {
    param([AllowNull()][object]$Response)

    $data = Get-PropertyValue -Object $Response -Name 'data'
    if ($null -ne $data) {
        return $data
    }
    return $Response
}

function Add-QueryString {
    param(
        [string]$Path,
        [hashtable]$Query
    )

    $parts = [System.Collections.Generic.List[string]]::new()
    foreach ($key in $Query.Keys) {
        $value = $Query[$key]
        if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
            continue
        }
        $encodedKey = [uri]::EscapeDataString([string]$key)
        $encodedValue = [uri]::EscapeDataString([string]$value)
        [void]$parts.Add("$encodedKey=$encodedValue")
    }
    if ($parts.Count -eq 0) {
        return $Path
    }
    return "${Path}?$($parts -join '&')"
}

$requestRows = [System.Collections.Generic.List[object]]::new()
$failureRows = [System.Collections.Generic.List[object]]::new()
$datasetId = 0

function Invoke-WarmupRequest {
    param(
        [ValidateSet('GET', 'POST')][string]$Method,
        [string]$Path,
        [hashtable]$Query = @{},
        [AllowNull()][object]$Body = $null,
        [string]$Token = '',
        [switch]$Required
    )

    $requestPath = Add-QueryString -Path $Path -Query $Query
    $uri = "$BackendOrigin$requestPath"
    $headers = @{}
    if ($Token) {
        $headers.Authorization = "Bearer $Token"
    }
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        $invokeParameters = @{
            Method = $Method
            Uri = $uri
            Headers = $headers
            TimeoutSec = $TimeoutSeconds
        }
        if ($null -ne $Body) {
            $invokeParameters.ContentType = 'application/json'
            $invokeParameters.Body = $Body | ConvertTo-Json -Depth 10 -Compress
        }
        $response = Invoke-RestMethod @invokeParameters
        $stopwatch.Stop()

        $code = Get-PropertyValue -Object $response -Name 'code'
        if ($null -ne $code -and [int]$code -ne 0) {
            throw "API envelope returned code $code"
        }

        $row = [pscustomobject]@{
            method = $Method
            path = $Path
            status = 'ok'
            elapsed_ms = [math]::Round($stopwatch.Elapsed.TotalMilliseconds, 1)
        }
        [void]$requestRows.Add($row)
        Write-Host ("  {0,-4} {1,-52} {2,8} ms" -f $Method, $requestPath, $row.elapsed_ms)
        return $response
    } catch {
        $stopwatch.Stop()
        $message = $_.Exception.Message
        $row = [pscustomobject]@{
            method = $Method
            path = $Path
            status = 'failed'
            elapsed_ms = [math]::Round($stopwatch.Elapsed.TotalMilliseconds, 1)
            error = $message
        }
        [void]$requestRows.Add($row)
        [void]$failureRows.Add($row)
        if ($Required) {
            throw "Required demo warmup request failed: $Method $requestPath. $message"
        }
        Write-Warning ("Optional warmup request failed: {0} {1}. {2}" -f $Method, $requestPath, $message)
        return $null
    }
}

function Select-CoordinationDataset {
    param([object[]]$Items)

    if ($CoordinationDatasetId -gt 0) {
        return $Items | Where-Object { [int](Get-PropertyValue -Object $_ -Name 'dataset_id' -DefaultValue 0) -eq $CoordinationDatasetId } | Select-Object -First 1
    }

    # Keep the warmup target aligned with the analyst route's default dataset.
    # The UI prioritizes the real Weibo Trump event before generic archives.
    $preferred = $Items | Where-Object {
        $slug = [string](Get-PropertyValue -Object $_ -Name 'slug' -DefaultValue '')
        $displayName = [string](Get-PropertyValue -Object $_ -Name 'display_name' -DefaultValue '')
        $isPreferred = $slug.ToLowerInvariant().Contains('weibo-trump-visit-2026-05-21-2') -or
            $displayName.ToLowerInvariant().Contains('weibo trump visit 2026-05-21')
        $isCompleted = (Get-PropertyValue -Object $_ -Name 'latest_status') -eq 'completed'
        $isPreferred -and $isCompleted
    } | Select-Object -First 1
    if ($preferred) {
        return $preferred
    }

    $preferredArchive = $Items | Where-Object {
        $slug = [string](Get-PropertyValue -Object $_ -Name 'slug' -DefaultValue '')
        $displayName = [string](Get-PropertyValue -Object $_ -Name 'display_name' -DefaultValue '')
        $isPreferred = $slug.ToLowerInvariant().Contains('weibo-trump-visit-2026-05-21-2') -or
            $displayName.ToLowerInvariant().Contains('weibo trump visit 2026-05-21')
        $isArchived = (Get-PropertyValue -Object $_ -Name 'latest_status') -eq 'archived'
        $isPreferred -and $isArchived
    } | Select-Object -First 1
    if ($preferredArchive) {
        return $preferredArchive
    }

    $completed = $Items | Where-Object { (Get-PropertyValue -Object $_ -Name 'latest_status') -in @('completed', 'archived') } | Select-Object -First 1
    if ($completed) {
        return $completed
    }
    return $Items | Select-Object -First 1
}

function Select-ReviewCase {
    param([object[]]$Items)

    if ($CaseId) {
        return $Items | Where-Object { [string](Get-PropertyValue -Object $_ -Name 'case_id') -eq $CaseId } | Select-Object -First 1
    }
    $eventMatch = $Items | Where-Object { [string](Get-PropertyValue -Object $_ -Name 'event_id') -eq $EventId } | Select-Object -First 1
    if ($eventMatch) {
        return $eventMatch
    }
    return $Items | Select-Object -First 1
}

Write-Host "Warming authenticated demo data for event '$EventId'..."
$healthResponse = Invoke-WarmupRequest -Method GET -Path '/api/v2/health' -Required
$loginResponse = Invoke-WarmupRequest -Method POST -Path '/api/v1/auth/login' -Body @{ username = $Username; password = $Password } -Required
$loginData = Get-ResponseData -Response $loginResponse
$accessToken = [string](Get-PropertyValue -Object $loginData -Name 'access_token')
if (-not $accessToken) {
    throw 'Login succeeded without an access token.'
}

[void](Invoke-WarmupRequest -Method GET -Path '/api/v1/auth/profile' -Token $accessToken -Required)
[void](Invoke-WarmupRequest -Method GET -Path '/api/v1/dashboard/overview' -Query @{ event_id = $EventId } -Token $accessToken -Required)

$datasetsResponse = Invoke-WarmupRequest -Method GET -Path '/api/v1/coordination/datasets' -Token $accessToken
if ($datasetsResponse) {
    $datasetItems = @(Get-ResponseData -Response $datasetsResponse)
    $dataset = Select-CoordinationDataset -Items $datasetItems
    $datasetId = [int](Get-PropertyValue -Object $dataset -Name 'dataset_id' -DefaultValue 0)
    if ($datasetId -gt 0) {
        [void](Invoke-WarmupRequest -Method GET -Path "/api/v1/coordination/datasets/$datasetId" -Token $accessToken)
        [void](Invoke-WarmupRequest -Method GET -Path "/api/v1/coordination/datasets/$datasetId/latest-result" -Token $accessToken)
        [void](Invoke-WarmupRequest -Method GET -Path "/api/v1/coordination/datasets/$datasetId/graph" -Query @{ node_limit = 200; min_node_score = 0 } -Token $accessToken)
    } else {
        Write-Warning 'No coordination dataset was available; the coordination page will load on demand.'
    }
}

[void](Invoke-WarmupRequest -Method GET -Path '/api/v1/accounts/profiles' -Token $accessToken)
[void](Invoke-WarmupRequest -Method GET -Path '/api/v1/propagation/observed-analysis' -Query @{ event_id = $EventId; node_limit = 160; first_layer_limit = 40; second_layer_limit = 80 } -Token $accessToken)
[void](Invoke-WarmupRequest -Method POST -Path '/api/v1/propagation/model-event-predict' -Query @{ event_id = $EventId; observation_ratio = 0.5; top_k = 10; force_refresh = $true } -Token $accessToken)

$caseSearchResponse = Invoke-WarmupRequest -Method GET -Path '/api/v2/review-cases' -Query @{ query = $EventId; limit = 20 } -Token $accessToken
$caseItem = $null
if ($caseSearchResponse) {
    $caseList = Get-ResponseData -Response $caseSearchResponse
    $caseItems = @(Get-PropertyValue -Object $caseList -Name 'items' -DefaultValue @())
    $caseItem = Select-ReviewCase -Items $caseItems
}
if (-not $caseItem -and -not $CaseId) {
    $latestCaseResponse = Invoke-WarmupRequest -Method GET -Path '/api/v2/review-cases/latest' -Token $accessToken
    if ($latestCaseResponse) {
        $caseItem = Get-ResponseData -Response $latestCaseResponse
    }
}
$selectedCaseId = if ($CaseId) { $CaseId } else { [string](Get-PropertyValue -Object $caseItem -Name 'case_id') }
if ($selectedCaseId) {
    $encodedCaseId = [uri]::EscapeDataString($selectedCaseId)
    [void](Invoke-WarmupRequest -Method GET -Path "/api/v2/review-cases/$encodedCaseId" -Token $accessToken)
    [void](Invoke-WarmupRequest -Method GET -Path "/api/v2/review-cases/$encodedCaseId/evidence" -Token $accessToken)
    [void](Invoke-WarmupRequest -Method GET -Path "/api/v2/review-cases/$encodedCaseId/activities" -Query @{ limit = 100 } -Token $accessToken)
} else {
    Write-Warning 'No review case was found; the review page will load on demand.'
}

$report = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    backend_origin = $BackendOrigin
    event_id = $EventId
    coordination_dataset_id = if ($datasetId) { $datasetId } else { $null }
    review_case_id = if ($selectedCaseId) { $selectedCaseId } else { $null }
    status = if ($failureRows.Count -eq 0) { 'ready' } else { 'partial' }
    request_count = $requestRows.Count
    failure_count = $failureRows.Count
    requests = @($requestRows)
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding utf8

Write-Host "Warmup report: $ReportPath"
if ($failureRows.Count -gt 0) {
    Write-Warning ("Demo warmup completed with {0} optional failure(s)." -f $failureRows.Count)
    if ($Strict) {
        throw 'Strict demo warmup failed; inspect the warmup report before recording.'
    }
}
Write-Host 'Demo data warmup completed.'
