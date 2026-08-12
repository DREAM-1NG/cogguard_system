# Propagation Fair Comparison Implementation Log

## Date

2026-08-12

## What Changed

- Added a model-agnostic fair protocol layer for native split loading, train-only vocabulary, prefix windows, Macro metrics, Micro metrics, and audit gating.
- Added same-protocol learned adapters for `Ours`, `MINDS`, `FOREST`, and `CasFT`.
- Added a formal full-matrix orchestrator that produces separate Macro and Micro summaries.
- Added a PowerShell launch script for full-source 200 epoch runs.
- Added tests that block hash buckets, proxy ranking, future candidate injection, and non-train vocabulary use from formal summaries.
- Added project terminology documentation for propagation monitoring and fair comparison.

## Formal Table Boundaries

| Table | Methods |
| --- | --- |
| Macro size / trend | Ours, MINDS, CasFT |
| Micro next-hop | Ours, MINDS, FOREST |

`TGN` and `DyGFormer` are not in this formal Macro/Micro matrix because their native task is temporal link prediction. They should be evaluated in a separate table unless a cascade-prefix learned scorer is implemented.

## Validation Run

```powershell
python -m pytest tests/test_fair_propagation_protocol.py tests/test_smoke.py -q
```

Result:

```text
12 passed in 9.22s
```

## Smoke Status

The matrix smoke was run with Douban, one seed, four formal methods, one epoch, and small train/eval caps. It generated valid JSON and Markdown summaries with `fair_protocol_passed=true`, then temporary outputs were deleted so they are not mistaken for formal performance evidence.

## Full Run Command

```powershell
.\benchmark\run_propagation_fair_full_matrix_20260812.ps1 `
  -Device cuda `
  -Epochs 200 `
  -TrainLimit 0 `
  -EvalLimit 0 `
  -MaxTrainUsers 0
```

This is the formal full-source run entry point. It writes status, stdout, stderr, JSON, and Markdown report files.
