param(
    [string]$Python = "python",
    [string]$Device = "cuda",
    [int]$Epochs = 200,
    [string]$Datasets = "douban,twitter,memetracker",
    [string]$Seeds = "42,43,44",
    [string]$Models = "Ours,MINDS,FOREST,CasFT",
    [int]$TrainLimit = 0,
    [int]$EvalLimit = 0,
    [int]$MaxTrainUsers = 0,
    [string]$Output = "benchmark\propagation_fair_full_matrix_20260812.json",
    [string]$Report = "benchmark\propagation_fair_full_matrix_20260812.md"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$LogDir = Join-Path $Root "benchmark\propagation_fair_full_matrix_20260812_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stdout = Join-Path $LogDir "fair_full_matrix.stdout.log"
$Stderr = Join-Path $LogDir "fair_full_matrix.stderr.log"
$StatusPath = Join-Path $LogDir "fair_full_matrix.status.json"

$Command = @(
    "-m", "benchmark.propagation_fair_full_matrix",
    "--datasets", $Datasets,
    "--seeds", $Seeds,
    "--models", $Models,
    "--epochs", "$Epochs",
    "--train_limit", "$TrainLimit",
    "--eval_limit", "$EvalLimit",
    "--max_train_users", "$MaxTrainUsers",
    "--device", $Device,
    "--output", $Output,
    "--report", $Report,
    "--resume"
)

@{
    schema = "cogguard.propagation.fair_full_matrix.run_status.v1"
    status = "running"
    started_at = (Get-Date).ToString("o")
    root = $Root
    command = @($Python) + $Command
    output = (Resolve-Path -LiteralPath (Split-Path -Parent $Output) -ErrorAction SilentlyContinue).Path
    output_file = $Output
    report_file = $Report
    stdout_log = $Stdout
    stderr_log = $Stderr
    protocol = "same native split, train-only vocabulary, shared prefix-window evaluator"
} | ConvertTo-Json -Depth 6 | Set-Content -Path $StatusPath -Encoding UTF8

try {
    & $Python @Command > $Stdout 2> $Stderr
    $ExitCode = $LASTEXITCODE
    $Status = if ($ExitCode -eq 0) { "completed" } else { "failed" }
}
catch {
    $ExitCode = 1
    $Status = "failed"
    $_ | Out-String | Add-Content -Path $Stderr -Encoding UTF8
}

$RowCount = 0
$FairOkCount = 0
if (Test-Path -LiteralPath $Output) {
    try {
        $Payload = Get-Content -Raw -LiteralPath $Output | ConvertFrom-Json
        $RowCount = [int]$Payload.protocol_audit.row_count
        $FairOkCount = [int]$Payload.protocol_audit.fair_ok_count
    }
    catch {
        Add-Content -Path $Stderr -Encoding UTF8 -Value "Failed to parse output JSON: $($_.Exception.Message)"
    }
}

@{
    schema = "cogguard.propagation.fair_full_matrix.run_status.v1"
    status = $Status
    exit_code = $ExitCode
    finished_at = (Get-Date).ToString("o")
    root = $Root
    command = @($Python) + $Command
    row_count = $RowCount
    fair_ok_count = $FairOkCount
    output_file = $Output
    report_file = $Report
    stdout_log = $Stdout
    stderr_log = $Stderr
} | ConvertTo-Json -Depth 6 | Set-Content -Path $StatusPath -Encoding UTF8

exit $ExitCode
