# KT2 全量实验验证审计

> 生成方式：由 `python -m benchmark.experiment_audit` 生成；不要手工把分项 small-run 结果改写为 full validation。
> 判定规则：分项 `passed` 只表示该模块当前审计项通过；KT2 是否全量完成以 `Full validation complete` 和 `benchmark.completion_gate` 为准。

- Schema: `cogguard.kt2.experiment_audit.v1`
- 总状态: `incomplete`
- Full validation complete: `False`
- Critical open sections: `role_evidence`

| 模块 | 状态 | 关键缺口 |
|---|---|---|
| 规模预测 | `passed` | - |
| 下一跳预测 | `passed` | - |
| 协同角色定位与证据追溯 | `partial` | manual_review_records |
| 前端展示与实验协议 | `passed` | - |

## 完成边界

- `frontier_reproduction_small_run` 只能说明上游 small-run 可复现，不能说明多数据多随机种子 full-run。
- 当前 KT2 full validation 只有在所有 critical section 均为 `passed` 且 completion gate 返回 `passed` 时才成立。
- 本报告应在新增模型证据、人工审核记录或前端协议证据后重新生成。

## 规模预测

- `passed` `scale_baselines`: RF/Temporal scale baselines have regression metrics.
- `passed` `observation_sensitivity`: Observation-window sensitivity exists.
- `passed` `casft_frontier_scale`: CasFT upstream small-run completed.

下一步：
- Repeat CasFT scale results across observation windows, datasets and at least three seeds before claiming full-run.
- Compare CasFT against RF/Temporal and CasDO/ConCat fallback rows before selecting the production scale model.
- Keep current evidence labelled frontier_reproduction_small_run, not frontier_reproduction_full_run.

## 下一跳预测

- `passed` `next_hop_baselines`: Next-hop baselines have ranking metrics.
- `passed` `dyglib_small_run`: DyGFormer/DyGLib small-run completed with no future-node injection audit.
- `passed` `tgn_small_run`: TGN small-run completed with no future-node injection audit.
- `passed` `repeated_small_run_evidence`: Small-run evidence records at least 3 repeated runs. This is not multi-seed full validation; seed-diverse larger runs remain required before final model selection.

下一步：
- Expand DyGLib/TGN from 20 cascades / 1 epoch / seed=0 to multi-seed and larger cascade caps.
- Parse upstream AP/AUC into the unified benchmark rows alongside KT2 candidate ranking metrics.
- Compare against ProspectiveRanker before selecting the final next-hop implementation.

## 协同角色定位与证据追溯

- `passed` `role_evidence_code`: Role evidence service and quality metrics are implemented and covered by tests.
- `passed` `real_kt1_coordination_input`: KT1 coordination file parsed with 2 coordinated users and 1 groups: G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\kt1_role_evidence_validation\kt1_coordination_scope.json
- `passed` `role_evidence_artifacts`: KT1-driven role evidence generated with 8 rows; coverage=1.0, path_complete_rate=1.0.
- `passed` `pheme_dataset_validation`: PHEME parsed 5 sample events with 99 nodes, 94 edges and 99 timestamps.
- `passed` `pheme_role_evidence_artifacts`: PHEME observed-user role evidence generated with 10 rows across 5 events; coverage=1.0, path_complete_rate=1.0.
- `passed` `manual_review_packet_ready`: Manual review packet is ready with 8 sampled rows; review_pass is intentionally not prefilled.
- `partial` `manual_review_records`: manual review has no recognized pass/fail values

下一步：
- Keep PHEME observed-user role evidence as real-timeline validation, not as KT1 prediction output.
- Use ROLE_EVIDENCE_REVIEW_GUIDE.md, ROLE_EVIDENCE_REVIEW_PACKET.md and ROLE_EVIDENCE_REVIEW.html to complete sampled manual pass/fail review rows.
- Initialize/fill analysis/role_evidence_manual_review.csv, then run python -m benchmark.role_evidence_review status and validate.
- Promote role evidence from partial to passed only after manual review records are available.

## 前端展示与实验协议

- `passed` `benchmark_schema`: Benchmark rows satisfy schema and anti-overclaim checks.
- `passed` `dashboard_experimental_label`: Dashboard prediction panels default to 实验预测 and expose dataset/window/model/reproduction metadata.
- `passed` `macro_micro_framework_protocol`: Macro/micro framework audit layer is implemented as a protocol summary, not as a new frontier reproduction claim.
- `passed` `kt2_joint_model_small_run`: KT2JointModel adapter is implemented and covered by tests; run `python -m benchmark.run_benchmark --models kt2_joint ... --output benchmark/results.json` to make it the current audit row. Absence from results.json is not treated as a legacy-frontier failure.

下一步：
- Keep predictions marked as experimental until final model selection is complete.
- Use KT2JointModel rows as KT2-owned local joint-model evidence; keep paper-model reproductions labelled separately.
- Expose result JSON/log links only for rows with verified reproduction levels.
