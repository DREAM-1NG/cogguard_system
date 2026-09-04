# Coordination Discover Research Runtime

Coordination Discover is the platform-generic Coordination Discover research pipeline. It learns dynamic coordination structure from observed account-object evidence without using platform-specific video, audio, image, OCR, ASR, or media embedding fields.

## Current Status

This research runtime is deprecated for system activation and claim-making. IOHunter validation showed the TemporalMAGNN-style/Leiden version improves some modularity-style community separation while severely reducing reconstruction quality against the stable `magnn_legacy` baseline: complete 5-dataset/3-seed deltas were Recon AUC `-0.086226` and Recon AP `-0.064126`. Keep artifacts only for historical replay and negative-result analysis; backend artifact-first loading rejects this model version and falls back to `coordination-evidence-runtime-v2`. See `DEPRECATION_NOTICE.md`.

## Public API

- `build_evidence_graph(snapshot) -> EvidenceGraph`
- `run_dynamic_discover(request) -> DiscoverResult`
- `run_detect_validation(request, discovery) -> DetectValidationResult`
- `export_coordination_result(discovery, detect=None) -> dict`
- `build_process_causal_experiment_report(graph) -> dict`

## Optimization Priority

1. Evidence graph v2: keep account-object evidence, and also project it into a directed weighted account multigraph with behavior layers and higher-order co-evidence edges.
2. Dynamic community discovery: export centered overlapping window graphs, lineage, membership transitions, and stability rows instead of only a static aggregate.
3. Representation and Detect boundary: the TemporalMAGNN-style representation is non-claimable after the IOHunter reconstruction regression; use precomputed platform-generic text LM embeddings when they are present in the snapshot; never synthesize embeddings inside this runtime; report `missing_labels` instead of Detect metrics on unlabeled event data.
4. Process/causal branch: emit descriptive process-mining motifs as exploratory, non-claimable evidence; causal tests require a separate labeled or quasi-experimental protocol.

## Frontline Alignment Updates

- Near-duplicate evidence now uses `simhash64_lsh_token_shingle_jaccard`: SimHash bands and shared token shingles generate candidates, then Hamming distance plus shingle Jaccard or token containment confirms the match. This replaces the earlier prefix-hash behavior and is recorded under `coverage.near_duplicate_policy` as `candidate_evidence_only`.
- Evidence coverage now reports `account_edge_layer_counts` and `evidence_layer_matrix`, so CNT-style behavior layers and higher-order co-evidence can be audited without turning topology counts into model inputs.
- Dynamic community artifacts now include window-level evidence/relation counts and a membership `transition_matrix`, aligning the output with temporal multiplex community analysis while keeping the current event-level result descriptive.
- Detect validation now records the required public-labeled protocol and a `claim_readiness` block. Metrics computed without split/campaign/platform/seed metadata remain `exploratory_metrics_only` and must not be cited as supervised Detect performance.

See `DISCOVER_DETECT_FINAL_PLAN.md` for the accepted recommendation order, literature alignment, local three-platform validation, and remaining research gates.

## Method Boundary

The default model input is account id, evidence object id, relation type, and time bucket. If `lm_text_embedding`, `semantic_text_embedding`, or `text_embedding` already exists on snapshot rows, the scorer may add it as a text semantic feature. Degree, density, pagerank, object concentration, and related topology statistics are emitted as `Topology Audit Feature` rows for audit and ablation only.

Image, video, audio, OCR, ASR, frame, and media embedding fields remain excluded from the platform-generic Coordination Discover artifact. Text embeddings are accepted only as precomputed language-model features and are recorded under `representation_inputs.text_embeddings` with `policy=precomputed_only_no_synthetic_embeddings`.

Research artifacts require strict Leiden partitioning through `python-igraph` and `leidenalg`. The backend rejects Coordination Discover artifacts whose manifest does not record `partition_backend=leiden`; it also rejects this deprecated `coordination_discover-temporal-magnn-leiden-v0` model version. Non-Leiden partitioning can only be used in local exploratory code by explicitly disabling the strict model config and must not be promoted as a research artifact.

Large shared objects use bounded temporal pair projection: small groups remain exhaustive, while large groups connect temporal neighbors up to a recorded cap. This prevents public keywords and discussion targets from creating unbounded complete graphs.

Near-duplicate candidate buckets are also bounded. Very common phrases can generate large shared-shingle buckets, so the runtime samples candidates with a deterministic cap and records that cap in the policy. The near-duplicate edge is evidence for analyst review and graph construction, not a label or causal assertion.

## Backend Integration

The backend is artifact-first. It validates `manifest.json` against the `EventSnapshot.data_fingerprint` and `modality_policy=platform_generic_only`; incompatible or missing artifacts fall back to `coordination-evidence-runtime-v2`.

Coordination Detect lives in `system/research/coordination_detect` and uses these representations only for public labeled validation.
