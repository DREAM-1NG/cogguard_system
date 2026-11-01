$ErrorActionPreference = "Continue"

$Root = "G:\CISCN\CogGuard\subsystems\cogguard_dev"
$Benchmark = Join-Path $Root "benchmark"
$LogDir = Join-Path $Benchmark "logs"
$StatusPath = Join-Path $Benchmark "propagation_sota_full_20260810_status.json"
$Python = "python"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

$Steps = @(
    @{
        Name = "primary_sota_full";
        Log = Join-Path $LogDir "propagation_sota_primary_full_20260810.log";
        Args = @(
            "-u", "-m", "benchmark.same_protocol_full_run_baselines",
            "--datasets", "douban,twitter,memetracker",
            "--seeds", "42,43,44",
            "--models", "MINDS,FOREST,CasFT",
            "--forest_data_root", "G:\CISCN\dataset\forest-data",
            "--minds_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS",
            "--forest_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST",
            "--casft_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT",
            "--out", "benchmark\propagation_sota_primary_full_20260810.json",
            "--config_id", "propagation-sota-primary-full-20260810",
            "--device", "cuda",
            "--timeout", "14400",
            "--max_minds_cascades", "0",
            "--minds_epochs", "200",
            "--minds_batch_size", "16",
            "--minds_emb_dim", "64",
            "--minds_step_split", "8",
            "--forest_epochs", "200",
            "--forest_batch_size", "16",
            "--forest_d_model", "64",
            "--forest_max_train_batches", "0",
            "--forest_max_eval_batches", "0",
            "--forest_rl_epochs", "200",
            "--forest_rl_max_batches", "0",
            "--forest_rl_rollout_len", "5",
            "--casft_max_events", "0",
            "--casft_max_epoch", "200",
            "--casft_timesteps", "1000"
        )
    },
    @{
        Name = "sequence_joint_vs_minds_full";
        Log = Join-Path $LogDir "propagation_sota_sequence_vs_minds_full_20260810.log";
        Args = @(
            "-u", "-m", "benchmark.kt2_minds_comparison",
            "--datasets", "douban,twitter,memetracker",
            "--seeds", "42,43,44",
            "--forest_data_root", "G:\CISCN\dataset\forest-data",
            "--minds_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS",
            "--max_minds_cascades", "0",
            "--minds_epochs", "200",
            "--minds_batch_size", "16",
            "--minds_emb_dim", "64",
            "--minds_max_seq_length", "200",
            "--minds_reproduction_level", "frontier_reproduction_full_run",
            "--kt2_epochs", "200",
            "--kt2_batch_size", "64",
            "--kt2_hidden_dim", "64",
            "--kt2_max_train_cascades", "0",
            "--kt2_max_test_cascades", "0",
            "--kt2_max_sequence_len", "200",
            "--kt2_obs_ratios", "0.1,0.3,0.5",
            "--out", "benchmark\propagation_sota_sequence_vs_minds_full_20260810.json",
            "--config_id", "propagation-sota-sequence-vs-minds-full-20260810",
            "--device", "cuda",
            "--timeout", "14400",
            "--resume"
        )
    },
    @{
        Name = "frontier_temporal_full";
        Log = Join-Path $LogDir "propagation_sota_frontier_temporal_full_20260810.log";
        Args = @(
            "-u", "-m", "benchmark.run_benchmark",
            "--datasets", "douban", "twitter", "memetracker",
            "--models", "casft", "dyglib", "tgn",
            "--forest_dir", "G:\CISCN\dataset\forest-data",
            "--casft_dir", "G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT",
            "--dyglib_dir", "G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib",
            "--tgn_dir", "G:\CISCN\CogGuard\subsystems\kt2_repos\tgn",
            "--frontier_export_dir", "benchmark\propagation_sota_frontier_exports_20260810",
            "--frontier_max_cascades", "0",
            "--frontier_epochs", "200",
            "--frontier_num_runs", "5",
            "--frontier_batch_size", "64",
            "--frontier_timeout", "14400",
            "--frontier_gpu", "0",
            "--run_external_frontier",
            "--device", "cuda",
            "--output", "benchmark\propagation_sota_frontier_temporal_full_20260810.json"
        )
    }
)

$Results = @()
foreach ($Step in $Steps) {
    $Start = Get-Date
    $CommandLine = "$Python " + (($Step.Args | ForEach-Object { if ($_ -match "\s") { '"' + $_ + '"' } else { $_ } }) -join " ")
    "[$($Start.ToString("s"))] START $($Step.Name)" | Tee-Object -FilePath $Step.Log -Append
    $CommandLine | Tee-Object -FilePath $Step.Log -Append
    & $Python @($Step.Args) *>&1 | Tee-Object -FilePath $Step.Log -Append
    $ExitCode = $LASTEXITCODE
    $End = Get-Date
    $Results += [ordered]@{
        name = $Step.Name
        command = $CommandLine
        log = $Step.Log
        started_at = $Start.ToString("o")
        ended_at = $End.ToString("o")
        elapsed_seconds = [math]::Round(($End - $Start).TotalSeconds, 1)
        exit_code = $ExitCode
    }
    [ordered]@{
        status = "running_or_finished"
        updated_at = (Get-Date).ToString("o")
        results = $Results
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

[ordered]@{
    status = "finished"
    updated_at = (Get-Date).ToString("o")
    results = $Results
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
