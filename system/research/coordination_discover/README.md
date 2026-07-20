# Coordination Discover Research Runtime

Coordination Discover is the platform-generic KT1 research pipeline. It learns dynamic coordination structure from observed account-object evidence without using platform-specific video, audio, image, OCR, ASR, or media embedding fields.

## Public API

- `build_evidence_graph(snapshot) -> EvidenceGraph`
- `run_dynamic_discover(request) -> DiscoverResult`
- `run_detect_validation(request, discovery) -> DetectValidationResult`
- `export_coordination_result(discovery, detect=None) -> dict`

## Method Boundary

The main model input is limited to account id, evidence object id, relation type, and time bucket. Degree, density, pagerank, object concentration, and related topology statistics are emitted as `Topology Audit Feature` rows for audit and ablation only.

Research artifacts require strict Leiden partitioning through `python-igraph` and `leidenalg`. The backend rejects KT1 artifacts whose manifest does not record `partition_backend=leiden`; non-Leiden partitioning can only be used in local exploratory code by explicitly disabling the strict model config and must not be promoted as a research artifact.

## Backend Integration

The backend is artifact-first. It validates `manifest.json` against the `EventSnapshot.data_fingerprint` and `modality_policy=platform_generic_only`; incompatible or missing artifacts fall back to `coordination-evidence-runtime-v2`.

Coordination Detect lives in `system/research/coordination_detect` and uses these representations only for public labeled validation.
