# KT2 Research Runtime Boundary

This directory contains KT2 research artifacts that are allowed to be read by the deployed CogGuard backend.

Current contents:

- `benchmark/kt2_sequence_vs_minds_sample_300c_5ep_3seed.json`: vetted cached benchmark evidence for the dashboard-facing `KT2SequenceJointModel` macro/micro result.

Current boundary:

- The backend may read cached artifacts from this directory.
- Live training runners, checkpoint adapters, public dataset loaders, and event-level checkpoint inference are not internalized yet.
- Until those runners are internalized here, live KT2 calls must return explicit `missing_data` or `model_unavailable` responses instead of importing external research workspaces.

Do not point system code at external `subsystems` paths. New KT2 runners or checkpoints must be added under this directory with provenance and tests.
