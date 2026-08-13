# IOHunter Official InfoOpsGFM Reproduction

Date: 2026-08-12

## Scope

This report reproduces the official `mminici/InfoOpsGFM` training entry points
against the local IOHunter processed bundles. The local checkout remains named
`G:\CISCN\dataset\iohunter\SocGFM` because it was obtained under the historical
repository name; it is pinned to the same verified source commit. The task is
account-level IO membership classification. It is not Coordination Discover
community recovery and it is not harmful-CIB Coordination Detect validation.

Official repository:

- Canonical upstream: `https://github.com/mminici/InfoOpsGFM`
- Local historical checkout origin: `https://github.com/mminici/SocGFM.git`
- Commit: `0c5ac6ec7502645217a5d7720a8fd85fb37e26e2`
- Official same-country configuration: SAGE, learning rate `0.01`, latent
  dimension `128`, maximum `1000` epochs, early stopping patience `30`, five
  dataset-provided splits, seed `12121995`.

The runner copies only official Python source and required full-data input
files into an isolated G-drive sandbox. It records command, source commit,
data SHA-256 manifest, G-drive-only temporary/cache paths, MLflow artifacts,
full log, and parsed global test aggregates. It does not write into the
upstream checkout.

Output root:

`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\`

## Results

### Cross-Attention Campaign Matrix

The values below are the official `run_MultiModalGNN_CrossAttention.py`
printed global `[TEST]` aggregate, reported as mean plus/minus standard
deviation over its five dataset-provided splits. They are not independent
multi-seed repetitions.

| Campaign | Backbone | Status | Macro-F1 | Accuracy | Precision | Runtime (s) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| UAE | SAGE | success | 0.9877 +/- 0.0034 | 0.9887 +/- 0.0031 | 0.9889 +/- 0.0055 | 1290.91 |
| Cuba | SAGE | blocked | - | - | - | 494.94 |
| Russia | SAGE | success | 0.9206 +/- 0.0189 | 0.9250 +/- 0.0178 | 0.8995 +/- 0.0270 | 49.93 |
| Venezuela | SAGE | success | 0.9890 +/- 0.0069 | 0.9958 +/- 0.0026 | 0.9814 +/- 0.0143 | 47.41 |
| Iran | SAGE | success | 0.9685 +/- 0.0024 | 0.9725 +/- 0.0020 | 0.9575 +/- 0.0037 | 223.20 |
| China | SAGE | success | 0.9301 +/- 0.0117 | 0.9913 +/- 0.0013 | 0.8963 +/- 0.0310 | 270.39 |

`Cuba` cannot complete on the local RTX 4060 Laptop GPU with 8GB VRAM. Its
full graph has 20,247 nodes and about 4.74M edges. The official SAGE run
failed when a propagation step requested 9.02GB; an official GCN retry
requested 9.03GB and also failed. The failures are retained as manifests and
logs. No graph sampling, model substitution, or altered training protocol was
used to manufacture a Cuba result.

### Same-Country Official Entry-Point Comparison

All four official SAGE entry points completed on the local Russia bundle under
the same five dataset-provided splits and hyperparameters. The summary
artifacts are:

`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-infoopsgfm-russia-method-matrix-20260812-230000\infoopsgfm_method_summary.md`

| Official entry point | Macro-F1 | Accuracy | Precision | Runtime (s) |
| --- | ---: | ---: | ---: | ---: |
| `run_GNN.py` | 0.8916 +/- 0.0312 | 0.9014 +/- 0.0276 | 0.9390 +/- 0.0449 | 62.79 |
| `run_GNNPlusLLM.py` | 0.9022 +/- 0.0167 | 0.9097 +/- 0.0146 | 0.9236 +/- 0.0134 | 122.22 |
| `run_MultiModalGNN.py` | 0.9085 +/- 0.0176 | 0.9153 +/- 0.0161 | 0.9297 +/- 0.0342 | 67.29 |
| `run_MultiModalGNN_CrossAttention.py` | 0.9206 +/- 0.0189 | 0.9250 +/- 0.0178 | 0.8995 +/- 0.0270 | 295.14 |

On this one campaign and protocol, Cross-Attention has the highest Macro-F1,
but it takes about 4.4 times the runtime of `MultiModalGNN`. This is an
ablation result, not a cross-campaign superiority claim.

## Official Matrix Execution

The repository now has a serial official-matrix runner for the four
same-country upstream entry points:

- `run_GNN.py`
- `run_GNNPlusLLM.py`
- `run_MultiModalGNN.py`
- `run_MultiModalGNN_CrossAttention.py`

It uses the source defaults documented by the upstream README: SAGE, learning
rate `0.01`, latent dimension `128`, maximum `1000` epochs, early stopping
patience `30`, and the five dataset-provided splits. It never changes the
upstream data loader, full-graph operators, split generation, optimizer, or
model code.

Use the resource-gated launcher from `system/backend/`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_iohunter_infoopsgfm_official_matrix.ps1
```

The launcher waits until the selected GPU and host memory are idle, then runs
the five executable local campaigns (`UAE`, `russia`, `venezuela`, `iran`,
`china`) across all four entry points serially. Every run uses a deterministic
`campaign--method--backbone` directory under the canonical G-drive output
root. Existing matching manifests are reused on restart; the matrix manifest
and summary report the expected, completed, successful, failed, and blocked
rows separately.

`cuba` remains in the plan but is blocked before execution on this workstation:
the official full-graph SAGE and GCN paths both requested about 9 GiB on the
recorded run, exceeding the available 8,188 MiB GPU. The runner writes a
blocked manifest rather than substituting sampling, mini-batching, or a
different model. On a machine with at least 12 GiB free GPU memory, rerunning
the same launcher with `-RetryNonSuccess` creates a new, linked attempt only
for the Cuba rows. By default, a recorded blocked or failed row is reused so
the same resource gate does not generate duplicate failure artifacts.

The current resource-gated matrix controller is:

`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-infoopsgfm-official-matrix-20260812-230724`

It remains a queue until `matrix_manifest.json` exists. A launcher log line
with `ready=false` is a resource wait, not an official training failure.
As of `2026-08-13 02:04:23 +08:00`, the queue had not started because the
resource gate still failed closed: host memory was `2291 MiB`, below the
`4096 MiB` minimum, and GPU used memory was `1675 MiB`, above the `1536 MiB`
idle threshold. This remains a resource wait, not an official training
failure; the launcher requires both host and GPU headroom before starting the
official full-graph jobs.

The clean-source baseline queue is:

`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-infoopsgfm-official-baselines-russia-20260813-001329`

It waits for the primary matrix `matrix_manifest.json` before running
`NodePruning` and `Node2Vec`, then applies the same resource gate. This keeps
the official main-method matrix from being delayed or contaminated by
secondary baselines.

Clean-source smoke checks for those secondary baselines show two upstream
script issues on the local Windows workstation:

| Baseline | Smoke manifest | Result |
| --- | --- | --- |
| `run_NodePruning.py` | `iohunter-infoopsgfm-node-pruning-russia-smoke-20260813-004429` | Printed one-split TEST metrics (`Macro-F1 0.8846`, `Accuracy 0.8958`) but exited with `official_post_metrics_cleanup_failed: shutil.rmtree received exp_dir=None`; the wrapper preserves the metrics and does not patch upstream source. |
| `run_Node2Vec.py` | `iohunter-infoopsgfm-node2vec-russia-smoke-20260813-005220` | Failed before TEST metrics with `official_windows_node2vec_worker_failed: PyG Node2Vec num_workers=4 cannot pickle PyCapsule`; this is the official script's Windows multiprocessing path, not a CogGuard model result. The wrapper now blocks this path by default on Windows before sandbox execution unless `COGGUARD_INFOOPSGFM_ALLOW_WINDOWS_NODE2VEC=1` is explicitly set. |

The verified default Node2Vec preflight manifest is
`iohunter-infoopsgfm-node2vec-russia-preflight-20260813-010421`; it records
`status=blocked`, `returncode=null`, and no sandbox directory.

The current point-in-time status report is:

`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-infoopsgfm-status-report-20260813-020505-auto\infoopsgfm_status_report.md`

It summarizes 20 unique tracked rows after normalizing legacy `SocGFM` v1
manifests and current `InfoOpsGFM` v2 manifests onto the same method/script
identity. The report contains 12 successful rows, 4 failed rows, 3 blocked
rows, and 1 pending resource-gated same-country all-campaign matrix row. The
pending row now records a structured `resource_gate` object with configured
thresholds, last observed host/GPU readings, and named blockers.

## Audit Notes

- The upstream checkout is dirty only in `run_Node2Vec.py` and
  `run_NodePruning.py`. Neither file is imported by the Cross-Attention entry
  point. The runner now records hashes and modified status for executed source
  files directly in new manifests.
- The official script overwrites root-level metric `.npy` files while writing
  relation-subset metrics after the global test. The CogGuard wrapper parses
  the official `[TEST]` console aggregate instead and records this limitation
  in every manifest.
- The official entry point exposes thresholded Accuracy, Precision, Macro-F1,
  and Micro-F1. It does not report global ROC-AUC, AUPRC, calibration, or
  cross-campaign holdout results, so this reproduction cannot be compared
  directly with the existing CogGuard external-account proxy matrix.
- The wrapper invokes four same-country official scripts: structural GNN,
  GNN plus SBERT node attributes, concatenated multimodal GNN, and
  Cross-Attention multimodal GNN. It does not modify their model, data-loading,
  split, early-stopping, or optimizer code. A wrapper-only MLflow workaround
  routes temporary/cache files to G: and preserves artifacts when Windows path
  length prevents a file-store copy.
- The official cross-country scripts remain blocked before execution. The
  standard cross-country entry point requires `processed/UAE_sample`, while
  the local bundle supplies `processed/UAE`; the runner deliberately refuses
  to synthesize an alias. The fine-tuning entry point correctly uses
  `processed/UAE`, but both entry points load Cuba, whose full graph exceeds
  the current 8GB GPU when using the official full-graph operators. The
  method-specific preflight records these independent blockers before any
  upstream code runs. The recorded manifests are:
  `iohunter-infoopsgfm-cross-country-official-preflight-20260812-230100` and
  `iohunter-infoopsgfm-cross-country-finetune-official-preflight-20260812-230100`.
- `run_Node2Vec.py` and `run_NodePruning.py` are baseline scripts present in
  the upstream source tree, but the upstream README does not list them as the
  primary InfoOpsGFM reproduction command. They are intentionally excluded
  from the clean official main-method matrix. Their independent runner now
  defaults to `InfoOpsGFM-clean` and fails closed before sandbox creation if
  any executed upstream source file is modified. Both entry points pass a
  clean-source parser/import smoke; their full Russia runs remain separately
  queued to avoid competing with the primary matrix for local resources.
- IOHunter labels identify externally attributed IO accounts. They do not
  provide observed event time, coordination-edge Gold, community Gold, or
  harmful/benign coordination-cluster Gold. The results cannot activate
  `coordination-evidence-runtime-v2` and cannot support a harmful-CIB claim.

## Next Step

Run the Cuba configuration on hardware with at least 12GB free GPU memory, or
adapt the official algorithm with a documented mini-batch implementation and
report it as a separate non-identical execution path. Do not merge the result
with the full-graph official reproduction table.
