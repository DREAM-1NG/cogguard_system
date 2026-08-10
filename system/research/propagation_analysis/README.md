# Propagation Analysis Research Boundary

This package contains the system-owned runtime and reproducibility artifacts for propagation prediction. Product code must not import models from `subsystems/` or external cloned repositories.

## Deployed Event Inference

- Event adapter: `benchmark/adapters/event_adapter.py`
- Sequence model: `benchmark/adapters/sequence_model.py`
- Checkpoint runtime: `benchmark/adapters/checkpoint_runtime.py`
- Output contract helpers: `benchmark/adapters/prediction_contract.py`
- Checkpoint: `benchmark/checkpoints/propagation_analysis_sequence_twitter_system.pt`
- SHA-256: `08790DF660B39C8F59D66F5878632D85AD64A8760BE391F53524A250E78FCC54`
- Model: `PropagationSequenceJointModel`
- Training source: local Twitter cascade data
- Runtime: CPU-safe PyTorch checkpoint loading and forward inference

The checkpoint stores its model configuration, 29 state-dict entries, relation-neighbor statistics, and the training user-bucket universe. Runtime code is split by responsibility: the event adapter constructs observed prefixes and legal candidate buckets; the sequence model defines `RelationGNN`, `DynamicCasHGNN`, `SharedLSTM`, a non-negative final-growth head, an Euler-style monotonic trend decoder, and a sampled-softmax-compatible next-user decoder; the checkpoint runtime loads the checkpoint and performs forward inference; the contract helpers produce unavailable/abstain responses without heuristic fallback values.

Current-event inference is governed by these rules:

1. `observed_until` is an inclusive, timezone-aware cutoff. Rows after it are excluded before model input construction.
2. `observation_ratio` must be one of the checkpoint-trained stages: `0.1`, `0.3`, or `0.5`.
3. Future trend checkpoints use model-native normalized steps. The public event API rejects wall-clock `prediction_horizon` values.
4. The model may score checkpoint training buckets, observed users, and historical relation-neighbor buckets. Public `candidate_count` counts only identity-mapped current-event users; bucket coverage is reported separately.
5. The current identity mapping supports reactivation ranking. Anonymous future buckets are not exposed as users and the system abstains from claiming identified new-user activation.
6. Missing checkpoints, missing dependencies, insufficient data, and inference errors return an unavailable/abstain response. No speed, acceleration, or activity-score fallback is used by the public current-event API.
7. No calibrated residual artifact is deployed yet, so prediction intervals remain unavailable and score concentration is not a confidence probability.

## Other Artifacts

- `benchmark/propagation_analysis_sequence_vs_minds_sample_300c_5ep_3seed.json`: sampled comparison evidence; it is not a full-validation result.
- `benchmark/loaders.py`: public cascade fixture normalizers.
- `runtime/protocol.py`: retained hindcast and benchmark protocol utilities; it is not loaded by the public current-event prediction service.
- `runtime/live_runtime.py`: retained research scaffold; it is not reachable from `POST /api/v1/propagation/model-event-predict`.

## Claim Boundary

Successful system inference proves deployment compatibility, not model superiority. The current sampled artifact records `full_validation_passed=false`. Formal research conclusions still require strict temporal splits, leakage audits, multiple seeds, candidate-recall reporting, calibrated intervals, and comparison with trainable baselines such as MINDS, FOREST, TGN, and DyGFormer.
