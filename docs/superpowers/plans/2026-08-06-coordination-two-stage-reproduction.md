# Coordination Two-Stage Research Reproduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research-only, auditable `Coordination Discovery -> harmful Coordination Detection` pipeline that faithfully implements TSGS/MHCR discovery, passes candidates through a versioned `DiscoveredClusterBatch`, and learns Detection parameters from labeled data.

**Architecture:** Stage 1 is label-free and owns event-to-graph sparsification, self-supervised hypergraph representation, clustering, and evidence-rich batch export. Stage 2 imports only the batch contract, combines cluster representations with detection-only content/telemetry features, learns and calibrates a classifier from train/validation data, and emits selective verdicts. Existing system Discovery remains frozen; new code is offline research-only until claim gates pass.

**Tech Stack:** Python 3.12, dataclasses, NumPy, SciPy, scikit-learn, PyTorch, python-igraph/leidenalg, pytest, JSON artifacts.

## Global Constraints

- `Discovery` means label-free discovery of coordinated account edges, clusters, evidence, and temporal structure; it must never consume harmful-CIB, bot, faction, or account-risk labels during fitting.
- Discovery may use content-derived coordination observations such as shared URL, hashtag, retweet/reply target, near-duplicate text, and optional semantic similarity; it must not use content harmfulness, stance, intent, or class labels.
- `Detection` means supervised classification of discovered clusters as benign/organic coordination versus harmful CIB; it consumes only a serialized `DiscoveredClusterBatch` plus explicitly detection-only features.
- Fixed weights `0.25/0.35/0.25/0.15`, Sigmoid scale `10`, and thresholds `0.65/0.85` are exported only as `heuristic_baseline_v1`; the primary Detection model learns coefficients from training data, calibration from validation data, and never fits on test data.
- `Cresci-2017` is a social-bot dataset and cannot support harmful-CIB Detection claims; it may be reported only as an auxiliary transfer or implementation benchmark.
- IOHunter official labels may be used only for external evaluation of Discovery and supervised Detection; they must never enter Stage 1 feature construction, training, clustering, or model selection.
- TSGS spectral approximation is claimed only relative to the explicit candidate graph unless candidate-recall evidence justifies a broader statement; asymptotic and speedup claims require measured scaling experiments.
- The targets `F1 > 0.98`, `ROC-AUC > 0.99`, `20x` construction speedup, `85%` memory savings, and `<3.5 ms` update latency remain unverified targets until generated artifacts support them.
- All data transforms, scalers, encoders, calibrators, and thresholds fit on train/validation partitions only; campaign/platform/time holdouts and seeds must be recorded in every result manifest.
- Existing `TemporalMAGNN + Leiden` remains deprecated/non-claimable; existing backend `coordination-evidence-runtime-v2` remains the production mainline throughout this plan.
- New source files remain focused modules; experiment orchestration must not be added to the existing monolithic `io_reproduction.py`.

---

### Task 1: Versioned Discovery-to-Detection Contract

**Files:**
- Create: `system/research/coordination_discover/stage1/__init__.py`
- Create: `system/research/coordination_discover/stage1/contracts.py`
- Create: `system/backend/tests/test_coordination_stage1_contracts.py`

**Interfaces:**
- Produces: `CoordinationMetricSet`, `DiscoveredCluster`, `DiscoveryProvenance`, `DiscoveredClusterBatch`.
- Produces: `DiscoveredClusterBatch.to_dict()`, `to_json(path)`, `from_dict(value)`, `from_json(path)`, and `validate()`.
- Contract version is exactly `cogguard.discovered-cluster-batch/v1`.

- [ ] Write failing tests for deterministic JSON round-trip, sorted unique member IDs, finite metric ranges, duplicate cluster rejection, contract-version rejection, and provenance/model-version preservation.
- [ ] Run `pytest tests/test_coordination_stage1_contracts.py -q` and verify the contract module is missing.
- [ ] Implement immutable/slotted dataclasses and strict validation. `overall_coordination_score` is a ranking score, not a probability or harmfulness score.
- [ ] Run the focused test and verify all cases pass.
- [ ] Commit only Task 1 files.

### Task 2: Faithful TSGS Candidate Graph and Spectral Audit

**Files:**
- Create: `system/research/coordination_discover/stage1/events.py`
- Create: `system/research/coordination_discover/stage1/tsgs.py`
- Create: `system/backend/tests/test_coordination_stage1_tsgs.py`

**Interfaces:**
- Consumes: normalized rows through `CoordinationEvent(account_id, relation, object_id, observed_at, weight, evidence_ref)`.
- Produces: `TSGSConfig`, `TSGSResult`, and `TemporalSketchGraphSparsifier.fit_transform(events) -> TSGSResult`.
- `TSGSResult` records candidate pair count, full pair count, bucket diagnostics, sampled weighted edges, timing, memory estimate, effective-resistance backend, guarantee scope, and empirical spectral audit.

- [ ] Write failing tests proving labels are rejected/ignored by the event adapter, LSH candidate generation avoids all-pairs calls on a fixture, deterministic seeds reproduce edges, sampled weights are finite, and a small connected fixture meets its empirical quadratic-form tolerance.
- [ ] Run the focused test and confirm failure before implementation.
- [ ] Implement sparse temporal activity vectors, random-hyperplane LSH bands with deterministic bucket caps, exact cosine scoring for candidate pairs, and effective-resistance sampling on the candidate graph. Use exact Laplacian pseudoinverse only below the configured exact-size limit; mark larger approximations explicitly.
- [ ] Add a dense reference builder used only by tests/benchmarks, never by the TSGS runtime path.
- [ ] Run the focused test and commit only Task 2 files.

### Task 3: MHCR Self-Supervised Representation and Discovery Engine

**Files:**
- Create: `system/research/coordination_discover/stage1/mhcr.py`
- Create: `system/research/coordination_discover/stage1/clustering.py`
- Create: `system/research/coordination_discover/stage1/engine.py`
- Create: `system/backend/tests/test_coordination_stage1_mhcr.py`
- Create: `system/backend/tests/test_coordination_stage1_engine.py`

**Interfaces:**
- Produces: `MHCRConfig`, `MHCRRepresentation`, `MHCREncoder.fit_transform(events, tsgs_result) -> MHCRRepresentation`.
- Produces: `DiscoveryConfig` and `CoordinationDiscoveryEngine.discover(events, provenance) -> DiscoveredClusterBatch`.

- [ ] Write failing tests that monkeypatch labels with opposite values and prove identical embeddings/clusters, verify relation-specific hyperedges, verify two stochastic views and InfoNCE training, and verify no classifier/logit/harmful verdict appears in Stage 1 output.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement normalized node-to-hyperedge/hyperedge-to-node propagation, relation-specific parameters, hyperedge-drop and temporal-jitter augmentations, InfoNCE-only fitting, and deterministic embedding export.
- [ ] Implement Leiden clustering over the fused TSGS/embedding affinity graph and evidence-backed cluster metrics; mark all aggregate scores as unsupervised rankings.
- [ ] Build `DiscoveredClusterBatch` with stable IDs, member evidence, artifact hashes, timing, and method versions.
- [ ] Run focused tests and commit only Task 3 files.

### Task 4: Learned Harmful-Coordination Detection

**Files:**
- Create: `system/research/coordination_detect/contracts.py`
- Create: `system/research/coordination_detect/features.py`
- Create: `system/research/coordination_detect/heuristic_baseline.py`
- Create: `system/research/coordination_detect/learned.py`
- Create: `system/research/coordination_detect/engine.py`
- Create: `system/backend/tests/test_coordination_stage2_detection.py`

**Interfaces:**
- Produces: `DetectionTrainingCase`, `DetectionFeatureSchema`, `DetectionModelArtifact`, `ClusterDetectionVerdict`, `ClusterDetectionBatch`.
- Produces: `LearnedCoordinationDetector.fit(train_cases, validation_cases) -> DetectionModelArtifact` and `predict(batch, detection_features) -> ClusterDetectionBatch`.
- Produces: `HeuristicBayesianBaseline.predict(...)`, always labeled `heuristic_baseline_v1` and never selected as the primary model by default.

- [ ] Write failing tests proving the learned coefficients differ when training labels are permuted, scaler/model fit excludes validation/test rows, calibration and decision/abstain thresholds use validation only, feature-schema mismatch fails closed, and the heuristic baseline is isolated.
- [ ] Run the focused test and confirm failure.
- [ ] Implement train-only standardization and regularized logistic/gradient-boosted cluster classification, validation-only probability calibration and selective threshold choice, explicit OOD/abstain output, artifact hashing, and serialization.
- [ ] Implement fixed-weight baseline separately with a mandatory warning and no production activation path.
- [ ] Run focused tests and commit only Task 4 files.

### Task 5: Dataset Adapters and Leakage-Safe Protocol

**Files:**
- Create: `system/research/coordination_experiments/__init__.py`
- Create: `system/research/coordination_experiments/protocol.py`
- Create: `system/research/coordination_experiments/iohunter.py`
- Create: `system/research/coordination_experiments/cresci.py`
- Create: `system/backend/tests/test_coordination_research_protocol.py`

**Interfaces:**
- Produces: `ExperimentSplit`, `DatasetCapability`, `ResearchDatasetManifest`, `build_campaign_holdout(...)`, `build_time_holdout(...)`.
- IOHunter produces unlabeled Stage 1 events plus a separately sealed evaluator label map; Cresci advertises `supports_harmful_cib_detection=False`.

- [ ] Write failing tests for label sealing, campaign-disjoint train/test IDs, chronological boundaries, train-only transform fit IDs, dataset capability checks, and deterministic seed manifests.
- [ ] Run the focused test and confirm failure.
- [ ] Implement adapters over local canonical data without `sys.path.insert`; labels must be returned only by evaluator objects unavailable to Stage 1.
- [ ] Record raw paths, checksums, label semantics, sample counts, campaign/platform/time axes, and blocked capabilities.
- [ ] Run focused tests and commit only Task 5 files.

### Task 6: Comparative Experiment Harness

**Files:**
- Create: `system/research/coordination_experiments/metrics.py`
- Create: `system/research/coordination_experiments/baselines.py`
- Create: `system/research/coordination_experiments/runner.py`
- Create: `system/backend/scripts/run_coordination_two_stage_reproduction.py`
- Create: `system/backend/tests/test_coordination_reproduction_runner.py`

**Interfaces:**
- Produces per-seed JSON/CSV artifacts and aggregate mean/std/bootstrap confidence intervals.
- Discovery baselines include dense cosine+Leiden, frozen system evidence prior, EdgeBank, TGN-style memory prior, and available legacy encoders.
- Detection baselines include coordination-only logistic regression, content/telemetry-only classifier, heuristic Bayesian baseline, and learned fused detector.

- [ ] Write failing fixture tests for multi-seed aggregation, metric direction, failed/blocked dataset reporting, ablation identity, runtime/memory reporting, and claim-gate computation.
- [ ] Run focused tests and confirm failure.
- [ ] Implement Discovery metrics (candidate recall, spectral distortion, edge AUPRC, B-cubed/NMI/ARI where externally labeled, stability) and Detection metrics (AUPRC, macro F1, ROC-AUC, ECE, coverage/risk, abstain).
- [ ] Implement ablations `no_tsgs`, `no_mhcr`, `no_relation_specific`, `no_temporal_augmentation`, `coordination_only`, and `detection_features_only`.
- [ ] Run focused tests and commit only Task 6 files.

### Task 7: Execute Local Reproduction Matrix and Audit Claims

**Files:**
- Generate: `system/output/coordination_two_stage_reproduction/<timestamp>/...`
- Create: `doc/research/coordination-two-stage-reproduction-results.md`

**Interfaces:**
- Consumes local IOHunter six-campaign processed data, Twitter state-backed operation data where feasible, and Cresci-2017 only for auxiliary transfer/scaling.
- Produces signed/checksummed manifests, raw per-seed rows, aggregate tables, ablations, scaling curves, and claim decisions.

- [ ] Run smoke fixtures, then IOHunter seeds `42,43,44,45,46` with campaign/time holdouts and all required baselines/ablations.
- [ ] Run TSGS scaling and spectral audits against the dense reference at sizes permitted by local memory.
- [ ] Run Cresci auxiliary experiments with an explicit `not_harmful_cib_claim` label.
- [ ] Generate tables comparing actual results to every numerical document target; mark each `supported`, `not_supported`, or `blocked`.
- [ ] Have an independent reviewer verify artifacts against the report before committing the results document.

### Task 8: Research Documentation and Final Gates

**Files:**
- Modify: `system/research/coordination_discover/README.md`
- Modify: `system/research/coordination_discover/DISCOVER_DETECT_FINAL_PLAN.md`
- Create: `system/research/coordination_detect/README.md`
- Create: `docs/adr/0014-coordination-two-stage-research-boundary.md`
- Modify: `doc/engineering/project-map.md`

**Interfaces:**
- Documents the one-way seam `DiscoveredClusterBatch`, activation gate, dataset capabilities, actual supported claims, and blocked work.

- [ ] Replace proposal language that states unverified results as fact with target/result/claim-status tables.
- [ ] Document that the production Discovery mainline is frozen and no candidate is activated by this plan.
- [ ] Run all focused research tests, full backend tests, lint, and typecheck; preserve pre-existing unrelated failures separately.
- [ ] Run a final whole-branch spec and quality review and fix all Critical/Important findings.
- [ ] Commit documentation and verification artifacts without staging unrelated dirty-worktree files.
