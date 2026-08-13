# Propagation SOTA Stable Matrix Report 2026-08-10

- generated_at: `2026-08-10T18:47:08`
- evidence_level: `resource_bounded_stable_matrix`
- strict_full_validation_passed: `false`
- datasets: `douban, twitter, memetracker`
- seeds: `42, 43, 44` for Ours/MINDS/FOREST/CasFT; DyGFormer/TGN use upstream `num_runs=1` plus the shared candidate protocol.
- boundary: this report completes a local stable comparison matrix under explicit caps. It is not an uncapped strict full validation.

## Stable Run Configuration

| Component | Configuration | Interpretation |
| --- | --- | --- |
| Ours vs MINDS | 300 cascades, 5 epochs, 3 seeds, 3 datasets | Completed earlier and reused as trainable paired evidence. |
| FOREST | 1 epoch, 2 train batches, 2 eval batches, RL disabled | Runnable public-code adapter evidence; non-finite loss is flagged. |
| CasFT | 200 events, 1 epoch, timesteps=2, 3 seeds, 3 datasets | Upstream CasFT training executes under local resource cap. |
| DyGFormer/TGN | 50 cascades, 1 epoch, CPU, upstream smoke training | Upstream scripts complete; reported Top-K metrics remain shared candidate-protocol metrics. |

## Strict Full Attempt Failures Kept For Provenance

| Model | Dataset | Seed | Status | Note |
| --- | --- | --- | --- | --- |
| MINDS | douban | 42 | failed | MINDS adapter produced no parseable JSON. |
| FOREST | douban | 42 | failed | FOREST adapter produced no parseable JSON. |

## Macro / Scale Metrics

| Dataset | Method | Rows | Status | MSLE | MAE | RMSE | Direction Acc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| douban | CasFT | 3 | ok | 13.6440 | 3.0043 | - | - |
| memetracker | CasFT | 3 | ok | 9.6215 | 2.4730 | - | - |
| twitter | CasFT | 3 | ok | 10.7558 | 2.9240 | - | - |
| douban | MINDS | 3 | ok | 0.0632 | - | - | - |
| memetracker | MINDS | 3 | ok | 0.0668 | - | - | - |
| twitter | MINDS | 3 | ok | 0.2733 | - | - | - |
| douban | Ours | 3 | ok | 0.1063 | 5.8337 | 16.4371 | 1.0000 |
| memetracker | Ours | 3 | ok | 0.1271 | 2.4195 | 4.6033 | 1.0000 |
| twitter | Ours | 3 | ok | 0.1288 | 6.0093 | 14.8247 | 1.0000 |

## Micro / Next-Hop Metrics

| Dataset | Method | Rows | Status | Candidate Recall | Hits@10 | Hits@50 | Hits@100 | MAP@10 | MAP@50 | MAP@100 | MRR | NDCG@100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| douban | DyGFormer/DyGLib | 1 | ok | 0.8536 | 0.1143 | 0.2039 | 0.2532 | 0.0600 | 0.0727 | 0.0756 | 0.3310 | 0.1869 |
| memetracker | DyGFormer/DyGLib | 1 | ok | 1.0000 | 0.2066 | 0.3727 | 0.4530 | 0.1302 | 0.1575 | 0.1639 | 0.4581 | 0.3244 |
| twitter | DyGFormer/DyGLib | 1 | ok | 0.6888 | 0.1686 | 0.2462 | 0.2815 | 0.1181 | 0.1379 | 0.1438 | 0.3448 | 0.2441 |
| douban | FOREST | 3 | ok | - | 0.0000 | 0.0028 | 0.0028 | 0.0000 | 0.0001 | 0.0001 | - | - |
| memetracker | FOREST | 3 | ok | - | 0.0072 | 0.0169 | 0.0314 | 0.0010 | 0.0016 | 0.0019 | - | - |
| twitter | FOREST | 3 | ok | - | 0.0000 | 0.0050 | 0.0100 | 0.0000 | 0.0001 | 0.0002 | - | - |
| douban | MINDS | 3 | ok | - | 0.1535 | 0.2140 | 0.2723 | 0.0802 | 0.0827 | 0.0836 | - | - |
| memetracker | MINDS | 3 | ok | - | 0.1357 | 0.2566 | 0.3319 | 0.0863 | 0.0918 | 0.0928 | - | - |
| twitter | MINDS | 3 | ok | - | 0.0569 | 0.1047 | 0.1414 | 0.0482 | 0.0501 | 0.0506 | - | - |
| douban | Ours | 3 | ok | 0.9233 | 0.0089 | 0.0256 | 0.0522 | 0.0035 | 0.0041 | 0.0044 | 0.0055 | 0.0123 |
| memetracker | Ours | 3 | ok | 0.8367 | 0.0289 | 0.0489 | 0.1056 | 0.0088 | 0.0096 | 0.0103 | 0.0123 | 0.0266 |
| twitter | Ours | 3 | ok | 0.9233 | 0.0044 | 0.0111 | 0.0278 | 0.0008 | 0.0011 | 0.0013 | 0.0021 | 0.0057 |
| douban | TGN | 1 | ok | 0.8536 | 0.1143 | 0.2039 | 0.2532 | 0.0600 | 0.0727 | 0.0756 | 0.3310 | 0.1869 |
| memetracker | TGN | 1 | ok | 1.0000 | 0.2066 | 0.3727 | 0.4530 | 0.1302 | 0.1575 | 0.1639 | 0.4581 | 0.3244 |
| twitter | TGN | 1 | ok | 0.6888 | 0.1686 | 0.2462 | 0.2815 | 0.1181 | 0.1379 | 0.1438 | 0.3448 | 0.2441 |

## Raw Method Rows

| Dataset | Method | Seed | Status | Reproduction Level | Source | Warning/Note |
| --- | --- | --- | --- | --- | --- | --- |
| douban | MINDS | 42 | ok | public_code_adapter | sequence_vs_minds |  |
| douban | Ours | 42 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| douban | MINDS | 43 | ok | public_code_adapter | sequence_vs_minds |  |
| douban | Ours | 43 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| douban | MINDS | 44 | ok | public_code_adapter | sequence_vs_minds |  |
| douban | Ours | 44 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| twitter | MINDS | 42 | ok | public_code_adapter | sequence_vs_minds |  |
| twitter | Ours | 42 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| twitter | MINDS | 43 | ok | public_code_adapter | sequence_vs_minds |  |
| twitter | Ours | 43 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| twitter | MINDS | 44 | ok | public_code_adapter | sequence_vs_minds |  |
| twitter | Ours | 44 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| memetracker | MINDS | 42 | ok | public_code_adapter | sequence_vs_minds |  |
| memetracker | Ours | 42 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| memetracker | MINDS | 43 | ok | public_code_adapter | sequence_vs_minds |  |
| memetracker | Ours | 43 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| memetracker | MINDS | 44 | ok | public_code_adapter | sequence_vs_minds |  |
| memetracker | Ours | 44 | ok | propagation_analysis_sequence_joint_model_small_run | sequence_vs_minds | PropagationAnalysisSequenceJointModel is the formal sequence-based PropagationAnalysis model. It is not an original MINDS, FOREST, or CasFT paper reproduction; it migrates their backbone/coupling/trend ideas. |
| douban | FOREST | 42 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| douban | CasFT | 42 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| douban | FOREST | 43 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| douban | CasFT | 43 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| douban | FOREST | 44 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| douban | CasFT | 44 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| twitter | FOREST | 42 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| twitter | CasFT | 42 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| twitter | FOREST | 43 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| twitter | CasFT | 43 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| twitter | FOREST | 44 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| twitter | CasFT | 44 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| memetracker | FOREST | 42 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| memetracker | CasFT | 42 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| memetracker | FOREST | 43 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| memetracker | CasFT | 43 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| memetracker | FOREST | 44 | ok | frontier_reproduction_full_run | primary_forest_casft | FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only. |
| memetracker | CasFT | 44 | ok | frontier_reproduction_full_run | primary_forest_casft | Upstream CasFT script completed on prepared official/preprocessed data. |
| douban | DyGFormer/DyGLib | 0 | ok | frontier_reproduction_small_run | frontier_temporal | DyGLib upstream training completed; event-level Top-K still uses KT2 candidate protocol metrics for comparability. |
| douban | TGN | 0 | ok | frontier_reproduction_small_run | frontier_temporal | TGN upstream self-supervised training completed; event-level Top-K uses KT2 protocol metrics for comparability. |
| twitter | DyGFormer/DyGLib | 0 | ok | frontier_reproduction_small_run | frontier_temporal | DyGLib upstream training completed; event-level Top-K still uses KT2 candidate protocol metrics for comparability. |
| twitter | TGN | 0 | ok | frontier_reproduction_small_run | frontier_temporal | TGN upstream self-supervised training completed; event-level Top-K uses KT2 protocol metrics for comparability. |
| memetracker | DyGFormer/DyGLib | 0 | ok | frontier_reproduction_small_run | frontier_temporal | DyGLib upstream training completed; event-level Top-K still uses KT2 candidate protocol metrics for comparability. |
| memetracker | TGN | 0 | ok | frontier_reproduction_small_run | frontier_temporal | TGN upstream self-supervised training completed; event-level Top-K uses KT2 protocol metrics for comparability. |

## Interpretation

- The matrix is now stable and multi-dataset, but resource-bounded. It should be used for engineering comparison and pipeline evidence, not final paper-level SOTA claims.
- The strongest paired trainable comparison remains Ours vs MINDS on the 300-cascade, 5-epoch, 3-seed protocol.
- FOREST needs a separate numerical-stability pass before it can be treated as a reliable competitive baseline under this Windows adapter.
- DyGFormer/TGN upstream training now launches successfully after the runtime shim path fix, but event-level Top-K values are still produced by the common candidate protocol for comparability.
