# LGB Official Data Request Package

- Status: `pending_authorized_data`
- Strict reproduction unblocked: `False`
- Dataset root: `G:\CISCN\dataset`
- Artifacts root: `G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict`

## Required Datasets

| Dataset | Official Repository | Target Directory | Required Files |
|---|---|---|---|
| TwiBot-22 | https://github.com/LuoUndergradXJTU/TwiBot-22 | `G:\CISCN\dataset\TwiBot-22` | label.csv, split.csv, edge.csv, user.json or user.jsonl or node.json or node.jsonl, tweet_*.json or tweet_*.jsonl |
| TwiBot-22 access note | Official repository states the full dataset is available through a Google Drive request with authorized/institutional contact. |  |  |
| TwiBot-20 | https://github.com/BunsenFeng/TwiBot-20 | `G:\CISCN\dataset\TwiBot-20` | train.json or train.jsonl, dev.json/dev.jsonl or valid.json/valid.jsonl, test.json or test.jsonl |
| TwiBot-20 access note | Official repository does not treat the sample file as the full strict-reproduction dataset; request/use authorized full train/dev/test files. |  |  |

## Sample Data Policy

TwiBot-20_sample.json may be used for converter smoke tests only; it must not pass strict LGB reproduction or be reported as paper-level evidence.

## Commands

### preflight

```powershell
python -m benchmark.adapters.lgb_bot_detection --inspect_data --dataset_root G:\CISCN\dataset
```

### strict_pipeline

```powershell
python -m benchmark.adapters.lgb_bot_detection --strict_pipeline --dataset_root G:\CISCN\dataset --artifacts_root G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict --device cuda --encoder_backend transformers_roberta_sft --model_name roberta-base --seeds 42,43,44,45,46
```

### strict_gate

```powershell
python -m benchmark.adapters.lgb_bot_detection --strict_gate --artifacts_root G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict --write_report_md G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict_gate.md
```

## Completion Rule

Strict reproduction can be claimed only after official data passes preflight and strict gate reports strict_reproduction_complete=true.
