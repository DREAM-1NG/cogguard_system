# KT2 Original-Fusion Gate

- status: `evidence_passed`
- objective: `Validate KT2 integrated MINDS/FOREST/CasFT-inspired joint-model evidence without overclaiming original-paper reproduction`

KT2 integrated joint-model evidence passes the current gate; this is not a claim that MINDS/FOREST/CasFT original-paper architectures are fully reproduced.

Completion rule: Gate pass requires upstream MINDS/FOREST/CasFT subpaths, CasFT main-output fusion, teacher-alignment evidence, same-protocol component ablation, multi-dataset/multi-seed/multi-observation coverage, required macro/micro metrics, leakage audit, a KT2 integrated full-run row, and same-protocol baseline comparison. It does not certify full original-paper reproduction.

## Checks

- `original_subpaths_and_teacher_alignment` / `passed`: All small-matrix KT2 rows ran MINDS/FOREST/CasFT original subpaths, recorded teacher alignment, and fused the CasFT continuous-time path into the main KT2 macro/trend outputs.
- `small_matrix_coverage` / `passed`: Requires >= 3 datasets, >= 3 seeds, >= 3 observation ratios; found 3 datasets, 3 seeds, 3 observation ratios.
- `metric_and_leakage_integrity` / `passed`: KT2 rows expose required macro/micro metrics and leak-check audit.
- `small_matrix_metric_stability` / `passed`: Small-matrix metrics are finite and below conservative explosion thresholds.
- `same_protocol_component_ablation` / `passed`: Same-protocol ablation covers MINDS baseline, FOREST, CasFT, full fusion and local bridge variants.
- `same_protocol_full_run_claimability` / `passed`: KT2 integrated full-run row and same-protocol baseline comparison support current integrated-model evidence.

## Required Next Actions

- All KT2 integrated-model evidence gates passed; keep reporting it as KT2 evidence, not full original-paper reproduction.
