# Coordination Discovery + Harmful Detection Final Plan

## Mainline Freeze And Research Reset

The backend evidence-constrained dynamic Coordination Discover path is frozen as
the system mainline. The `TemporalMAGNN + Leiden` research branch is
deprecated/non-claimable after its IOHunter reconstruction regression and remains
available only for replay, comparison, and negative-result analysis.

The current research architecture is explicitly two-stage: label-free TSGS/MHCR
Discovery emits a versioned `DiscoveredClusterBatch`; learned harmful-CIB
Detection consumes only that batch and detection-only features. This is not the
multi-agent review pipeline and does not change the frozen product runtime.
`heuristic_baseline_v1` remains a comparison baseline, not the learned
detector. ADR-0014 defines the binding input, output, and activation rules.

The replacement research line is a goal-aligned continuous-time heterogeneous
evidence model. It must first repair evaluation integrity, then implement a
lightweight account-pair temporal edge model, and only then consider
HGT/TGN-level message passing. A research model can enter the system only after
it beats the frozen engineering implementation and `magnn_legacy` under the
accepted validation gates.

## Accepted Priority Order

1. Recommendation 1: upgrade the evidence graph into a directed weighted multigraph.
2. Recommendation 2: upgrade static windows into dynamic community discovery.
3. Recommendation 4: upgrade Detect readiness through representation inputs and public labeled validation boundaries.
4. Recommendation 6: add process motifs as exploratory evidence only.

This order is intentional. Evidence semantics and temporal locality determine whether the system can produce defensible Discovery results. Detect performance claims come later and require labels. Process mining is useful for analyst hypotheses, but it is not a claimable causal method in the current system.

## Literature Alignment

- Survey boundary: `Detection and Characterization of Coordinated Online Behavior: A Survey` frames coordination work as detection plus characterization and motivates strict claim boundaries.
- Evidence graph baseline: `Coordination Network Toolkit` motivates multi-behavior, weighted, directed coordination networks instead of a single flattened co-object graph.
- Temporal baseline: `Temporal Dynamics of Coordinated Online Behavior` motivates window-level graphs, community lineage, membership transitions, stability, archetypes, and influence-oriented analysis.
- External-account proxy baseline: `IOHunter` supports supervised scarce-label and cross-IO account-recovery comparisons. It does not provide harmful-CIB Gold, true coordination communities, or observed-time evidence, so it is not the Stage 2 Detect protocol.
- Representation target: `SoMeR` motivates future multi-view user representation with temporal activity, text, profile, and network views.
- Process branch: `Discovering Coordinated Processes From Social Online Networks` motivates ordered behavior motifs, but the current system keeps them descriptive and non-claimable.

Reference boundary is captured in `research-wiki/preflight_runs/20260722T171047Z-align-coordination-discover-detect-with-high-level-literature/preflight.json`.

## Current Implementation

- `contracts.py` now exposes `AccountMultigraphEdge`, `EvidenceGraph.account_edges`, `EvidenceGraph.representation_inputs`, and `DiscoverResult.dynamic_communities`.
- `evidence.py` builds platform-generic account-object evidence, directed weighted account multigraph edges, higher-order co-evidence edges, precomputed text embedding registries, and SimHash/LSH plus token-shingle near-duplicate candidate evidence.
- `models.py` keeps topology features out of the model input, consumes only precomputed text embeddings, and uses bounded temporal pair projection for large shared objects. The current `TemporalMAGNN-style` scorer is retained only as a deprecated comparison artifact.
- `pipelines.py` exports centered overlapping window graphs, layer/relation counts per window, lineage, membership transitions, transition matrix, stability rows, archetype counts, and a process-motif branch marked `exploratory_non_claimable`.
- `evaluation.py` returns Detect metrics only with labels and records `claim_readiness`; missing split/campaign/platform/seed metadata keeps metrics in `exploratory_metrics_only` status.
- `process_experiments.py` extracts ordered evidence-kind motifs but returns `causal_tests.status=not_run`.
- `scripts/run_coordination_local_discover_detect.py` builds local three-platform `EventSnapshot` inputs and writes lightweight Discover/Detect validation artifacts.

Large shared objects use this policy: exhaustive pairs for small groups, temporal-neighbor capped projection for large groups. This prevents public keywords or discussion targets from turning into unbounded complete graphs while preserving local temporal support.

Near-duplicate evidence uses a deterministic candidate policy: SimHash bands and shared token shingles generate candidates, Hamming distance plus shingle Jaccard or token containment confirms candidates, and very large buckets are capped. This is a candidate evidence mechanism for Discovery, not a supervised label.

## Local Validation

Input inventory:

- Source: 11 readable local Trump-visit JSONL files under `MediaCrawler-main/data_runs` as offline experiment input only.
- Raw normalized posts: 433 total: douyin 41, weibo 236, xhs 156.
- Raw normalized comments: 21433 total: douyin 13396, weibo 4665, xhs 3372.
- Detect labels: absent; the correct local Detect output is `missing_labels`.

Experiment matrix:

| run | scope | cap | output | conclusion |
|---|---|---:|---|---|
| smoke | per-platform | 1500 comments/platform | `system/output/coordination_discover_detect_local/20260722T182955Z` | all platforms `ok`; Detect `missing_labels`; fast regression gate |
| budgeted matrix | per-platform | 3000 comments/platform | `system/output/coordination_discover_detect_local/20260722T185519Z` | execution and contract gates passed; Detect remained `missing_labels` |
| full local matrix | per-platform | uncapped | `system/output/coordination_discover_detect_local/20260723T015347Z` | all local posts/comments loaded; execution gates passed; no effectiveness claim |
| bounded fusion | combined | 1500 comments/platform | `system/output/coordination_discover_detect_local/20260722T185931Z` | cross-platform snapshot gates passed; no identity or causal claim |
| long-run attempt | combined / uncapped | uncapped comments | timed out at short interactive budgets | requires explicit long-job budget and artifact strategy |

Full local per-platform matrix:

| platform | core_posts | comments | account_edges | higher_order | windows | lineage | transitions | process_motifs | detect |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| weibo | 166 | 2680 | 40395 | 2114 | 62 | 204 | 10371 | 25 | missing_labels |
| douyin | 31 | 10137 | 191140 | 34614 | 69 | 325 | 28734 | 18 | missing_labels |
| xhs | 86 | 1677 | 15363 | 448 | 62 | 131 | 3644 | 22 | missing_labels |

Bounded combined validation:

| snapshot | core_posts | comments | account_edges | higher_order | windows | lineage | transitions | process_motifs | detect |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| combined | 283 | 4297 | 74623 | 6075 | 65 | 321 | 12254 | 25 | missing_labels |

Local demonstration conclusion:

- Evidence multigraph implementation gate passed: every validated snapshot has directed weighted account multigraph edges and higher-order co-evidence.
- Dynamic community implementation gate passed: every validated snapshot exports centered window graphs, lineage, and membership transitions.
- Detect boundary gate passed: every local run returns `missing_labels` instead of fabricating supervised accuracy.
- Process motif boundary gate passed: motifs are exported only as `exploratory_non_claimable`, with causal tests not run.
- The local paths demonstrate that evidence construction and dynamic-community exports run on the case study. They are not an effectiveness comparison or evidence of supervised Detect performance.

## Claim Boundary

- Deprecated result: the TemporalMAGNN-style/Leiden research version is non-claimable after IOHunter showed severe reconstruction regression versus `magnn_legacy` (complete 5-dataset/3-seed Recon AUC `-0.086226`, Recon AP `-0.064126`). Use it only for historical replay and negative-result analysis.
- We can claim: the system now implements a two-stage shape where Discovery produces evidence-constrained dynamic coordination structure and Detect refuses supervised performance claims when labels are absent.
- We can claim: the Trump data supports system demonstration and Discovery case-study evidence with provenance and data-quality reporting.
- We cannot claim: supervised Detect accuracy, cross-event generalization, cross-platform identity resolution, or causal coordination.
- We cannot claim: the current scorer is a full MAGNN/HGT/TGN/GFM. It is a TemporalMAGNN-style embedding scorer with strict boundary language.

## Final Two-Stage Scheme

Stage 1: Coordination Discover.

- Input: `EventSnapshot` with platform, window, normalized posts/comments, relations, quality report, provenance, and data fingerprint.
- Evidence construction: platform-generic objects only: URL/domain, hashtag/topic/keyword, entity, target, discussion target, native relation, and near-duplicate template.
- Graph semantics: account-object evidence plus directed weighted account multigraph edges; large shared objects and large near-duplicate buckets use bounded deterministic projection, not unbounded complete graphs.
- Temporal structure: 1h/6h/24h centered overlapping windows, dynamic community lineage, membership transitions, transition matrix, stability, and archetype counts.
- Output: ordinal risk/evidence structures, community lineage, account tiers, evidence edges, abstain/fallback metadata, and process motifs marked exploratory.

Stage 2: Coordination Detect.

- Local Trump data path: Detect runs only as a boundary check and returns `missing_labels`.
- Target-task labeled path: Detect consumes serialized `DiscoveredClusterBatch` artifacts plus detection-only features from an approved harmful-CIB corpus, and must report AUPRC, MaxF1, ECE/calibration, abstain rate, 5-seed confidence intervals, and campaign/platform/time holdout results.
- Metadata rule: Detect metrics without split/campaign/platform/seed metadata are explicitly `exploratory_metrics_only`.
- Activation rule: no Detect performance claim or production activation without public labeled validation and cross-event checks.
- Representation rule: text LM features are consumed only as precomputed embeddings; no generated semantic shortcuts are allowed from mojibake or damaged text.

## Next Optimization Work

1. **P0: repair evaluation integrity.** Use campaign/platform/time holdouts, fit TF-IDF/SVD/scalers and text representations on training data only, use matched hard negatives, run 5 seeds, and add no-edge/no-text/no-higher-order/no-Leiden ablations.
2. **P1: build a lightweight temporal edge model.** Keep the evidence graph, train directly on account-pair coordination targets, and use continuous time deltas, learnable temporal decay, relation attention, text evidence inputs, and learned edge weights.
3. **P2: evaluate a real hetero-temporal GNN only after P1 passes.** Add account/content/object/platform node types, relation-specific message passing, event-level temporal memory, and a dynamic-community consistency head only when the lighter model improves reconstruction and Detect transfer.
4. Run Stage 2 Detect experiments only on an approved harmful-CIB corpus with campaign/platform/time holdout, AUPRC, MaxF1, ECE, abstain, and confidence-interval gates. Keep IOHunter separate as an external-account proxy benchmark.
5. Add combined-event long-run jobs with signed manifests, size budgets, and artifact compression.
6. Add analyst review fixtures for community evidence support/contradiction/unknown without turning them into training labels prematurely.

The activation gate is strict: no candidate research model becomes the system
model unless it beats the frozen engineering path and `magnn_legacy`; a
modularity increase alone is insufficient.
