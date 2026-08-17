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

## Formal Validation Update

The latest reported formal run is recorded in [`benchmark/formal_36x_fair_protocol_20260815.md`](benchmark/formal_36x_fair_protocol_20260815.md). It covers 3 datasets x 3 seeds x 200 epochs, with 36/36 rows reported as `fair_protocol_passed=true`, and separates Macro scale/trend metrics from Micro next-hop ranking metrics.

The supported claim is deliberately specific: Ours improves Macro trend prediction over MINDS on all three datasets and outperforms FOREST on the reported Micro ranking metrics. It is not a universal SOTA claim. CasFT remains strongest on most Macro metrics, while MINDS is slightly better on many Douban/Twitter Micro metrics. Candidate Recall is a coverage audit, not ranking quality.

The older `benchmark/sequence_vs_minds_sample_300c_5ep_3seed.json` remains a historical preflight artifact. It must not be cited as the latest formal result or used to override the formal record above.

## Runtime Decision Boundaries

### Open-world candidates

Resolving participating users and their observed one- or two-hop neighbors can improve candidate recall, but it does not by itself resolve unknown identities. The implementation must keep candidate generation, platform identity resolution, and ranking as separate steps. Platform account IDs and explicit cross-platform evidence are required; names alone are not identity proof. Unknown or ambiguous candidates need an explicit bucket and separate evaluation. Until that contract exists, the public endpoint remains a closed-world reactivation ranking endpoint.

### Wall-clock horizons

The current checkpoint emits normalized trajectory steps. A request such as `prediction_horizon=24` cannot be interpreted as 24 hours and is rejected by the public API. Wall-clock support requires time-binned or duration-conditioned targets, horizon metadata, and time-based evaluation in a new checkpoint. Until then, expose normalized forecast checkpoints rather than a misleading hour value.

### `unavailable` versus `abstain`

- `unavailable`: required checkpoint, dependency, minimum data, legal candidate set, or inference execution is missing, so no model result exists.
- `abstain`: the service intentionally makes no claim, for example because identity mapping is ambiguous or the evidence is insufficient.

Both are structured outcomes. They are not zero-filled predictions and must retain reason codes, the observation cutoff, candidate counts, mapping status, and calibration status.

### Predictive uncertainty

Prediction intervals can be added to the current model family, but not as a UI-only field. The minimum path is a held-out temporal calibration split with post-hoc conformal residual intervals. A Bayesian last layer, heteroscedastic likelihood, ensemble, or MC-dropout posterior can follow when epistemic uncertainty is required. Macro intervals and Micro ranking calibration are separate tasks. The checkpoint contract must version `posterior_artifact`, `calibration_status`, interval coverage, and horizon metadata; without a calibration artifact, `intervals` remains `None`.

## Other Artifacts

- `benchmark/propagation_analysis_sequence_vs_minds_sample_300c_5ep_3seed.json`: historical sampled preflight evidence; it is not the latest formal result.
- `benchmark/loaders.py`: public cascade fixture normalizers.
- `runtime/protocol.py`: retained hindcast and benchmark protocol utilities; it is not loaded by the public current-event prediction service.
- `runtime/live_runtime.py`: retained research scaffold; it is not reachable from `POST /api/v1/propagation/model-event-predict`.

## Claim Boundary

Successful system inference proves deployment compatibility, not model superiority. The latest formal record supports a bounded claim about Macro trend improvement over MINDS and Micro performance relative to MINDS/FOREST; it does not support universal SOTA, new-user identity prediction, or calibrated uncertainty until the runtime contracts above are implemented and evaluated.
