# Propagation Analysis Research Boundary

This directory contains KT2 / Propagation Analysis research artifacts that are allowed to be read by the deployed CogGuard backend.

Current contents:

- `benchmark/kt2_sequence_vs_minds_sample_300c_5ep_3seed.json`: vetted cached benchmark evidence for the dashboard-facing `KT2SequenceJointModel` macro/micro result.
- `benchmark/adapters/kt2_event_adapter.py`: internal event bundle / checkpoint seam used by the backend.
- `benchmark/loaders.py`: local public benchmark / fixture normalizer for Twitter/TGB/Douban/MemeTracker/CasFlow/CasFT-shaped cascade rows.
- `runtime/protocol.py`: app-facing hindcast protocol, split-conformal intervals, next-hop ranking, platform hindcasts, and baseline registry.
- `runtime/live_runtime.py`: current-event live fallback used when no approved checkpoint is active.

Current boundary:

- The backend may read cached artifacts, the internal event adapter, public fixture loader, hindcast protocol, and current-event live runtime from this directory.
- The current live runtime is a fallback. It is allowed for system demonstration and Trump-event smoke runs, but it is not sufficient as a research claim.
- TGN, DyGFormer, CasFlow, and CasFT are registered as baseline/checkpoint slots. Until approved checkpoints are vendored under this boundary, they must return explicit `missing_checkpoint` or `model_unavailable` states.
- Split-conformal 80/95 intervals are produced from event-prefix residuals when available and conservative fallback residuals otherwise; formal claims still require public benchmark coverage validation.

Do not point system code at external `subsystems` paths. New KT2 runners or checkpoints must be added under this directory with provenance and tests.
