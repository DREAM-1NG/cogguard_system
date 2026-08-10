# Coordination Discover Research Runtime

Coordination Discover is the platform-generic Coordination Discover research pipeline. It learns dynamic coordination structure from observed account-object evidence without using platform-specific video, audio, image, OCR, ASR, or media embedding fields.

## Current Status

The backend evidence-constrained dynamic Discover path is frozen as the system mainline. This research runtime is deprecated for system activation and claim-making. IOHunter validation showed the TemporalMAGNN-style/Leiden version improves some modularity-style community separation while severely reducing reconstruction quality against the stable `magnn_legacy` baseline: complete 5-dataset/3-seed deltas were Recon AUC `-0.086226` and Recon AP `-0.064126`. Keep artifacts only for historical replay and negative-result analysis; backend artifact-first loading rejects this model version and falls back to `coordination-evidence-runtime-v2`. See `DEPRECATION_NOTICE.md` and ADR-0012.

The current two-stage research implementation is separate from that deprecated
TemporalMAGNN-style branch. Its Stage 1 modules are label-free TSGS/MHCR
Discovery and export `cogguard.discovered-cluster-batch/v1`
`DiscoveredClusterBatch` artifacts. Stage 2 lives in
`system/research/coordination_detect`, reads only that batch plus
detection-only features, and fits its classifier/calibration on labeled
train/validation cases. The fixed Bayesian rule is retained only as
`heuristic_baseline_v1`.

The two-stage implementation is supported as research code and contract
coverage, not as a product cutover. The current IOHunter smoke covers only one
Russia campaign/seed external-account proxy. Its G-drive artifact and blocked
claim decisions are under
`system/output/coordination_two_stage_reproduction/iohunter-matrix-artifact-smoke-v2-20260808`.
It does not support harmful-CIB, true coordination recovery, causal, observed-
time, or production-activation claims. ADR-0014 is the normative boundary.

## Research Interfaces

The current Stage 1 interface is
`CoordinationDiscoveryEngine.discover(events, provenance) -> DiscoveredClusterBatch`.
The serialized batch is the only interface into the learned Stage 2 package.

`build_evidence_graph`, `run_dynamic_discover`, `run_detect_validation`, and
`export_coordination_result` belong to the deprecated TemporalMAGNN-style
research branch. They remain for historical replay and regression coverage;
`run_detect_validation(request, discovery)` is not the Stage 2 seam and cannot
support a harmful-CIB claim. `build_process_causal_experiment_report` is an
exploratory, non-claimable analysis helper.

## Optimization Priority

The engineering path is not waiting for a research model cutover. Future research work follows this order:

1. **P0: Evaluation integrity.** Use campaign/platform/time holdouts, split-safe feature fitting, matched hard negatives, 5 seeds, calibration, abstain gates, and no-edge/no-text/no-higher-order/no-Leiden ablations.
2. **P1: Lightweight temporal edge model.** Keep the evidence graph, but train directly on account-pair coordination targets with continuous time deltas, learnable temporal decay, relation attention, text evidence inputs, and learned edge weights.
3. **P2: Full hetero-temporal GNN.** Consider relation-specific message passing and event-level temporal memory only after P1 beats the frozen engineering path and `magnn_legacy`.
4. **Exploratory process branch.** Keep ordered process motifs descriptive and non-claimable until a separate labeled or quasi-experimental protocol exists.

The opt-in P1 research candidate now lives in `temporal_edge_model.py` and exports
`TemporalEdgeModelConfig`, `split_temporal_account_edges`, `build_matched_hard_negatives`,
`fit_temporal_edge_model`, `fit_temporal_edge_model_multi_seed`, and
`run_temporal_edge_ablation_suite`. It is not wired into the backend mainline.

### P1 Temporal History Edge Candidate

`temporal_history_edge_mlp_v2` is a research-only account-pair candidate for strict
chronological future-edge evaluation. It fixes the earlier proxy mistakes:

- Model inputs exclude observed edge `weight` and sample-construction `observed_rank`.
- Validation and test history features use train-only evidence by default.
- The frozen system comparison is `system_future_edge_prior`; `observed_edge_upper_bound`
  remains a diagnostic ceiling and is not treated as a deployable baseline.
- Final ranking uses a validation-selected `system_prior + residual` ensemble. If residual
  gain is large, selection favors the smallest residual within the validation tolerance;
  if residual gain is marginal, selection uses the validation winner.
- `raw_model_metrics` are exported separately from final ensemble metrics.
- The fair comparison set also includes `edgebank_repeat`, `tgn_style_memory_prior`,
  and `degree_time_prior`; `observed_edge_upper_bound` is diagnostic only.
- Multi-seed aggregation reports mean, population standard deviation, per-seed values,
  and win rates against both the frozen system prior and the strongest fair baseline.
- Ablations are configuration-driven: `learned_only`, `no_system_prior_feature`,
  `no_exact_pair_history`, and `no_relation_memory`. They remain research-only and
  are exported separately from user-level Detect metrics.

Latest strict Discovery IOHunter batch on `2026-08-06` used the six processed datasets,
`max_edges_per_relation=3000`, 20 requested epochs, full seeds `42..46`, and one
ablation seed (`42`). The target is chronological future account-pair edge discovery,
not IOHunter's user-level node-label Detect task.

| Dataset | Candidate | System prior | EdgeBank | TGN-style | Degree-time | Strongest fair |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| UAE | 0.456076 | 0.438869 | 0.332882 | 0.400581 | 0.331731 | 0.438869 |
| china | 0.339209 | 0.340732 | 0.332621 | 0.350208 | 0.332536 | 0.350208 |
| cuba | 0.578586 | 0.582034 | 0.333018 | 0.565317 | 0.334187 | 0.582034 |
| iran | 0.442016 | 0.436669 | 0.331303 | 0.424098 | 0.331303 | 0.436669 |
| russia | 0.342857 | 0.323267 | 0.332772 | 0.377982 | 0.336501 | 0.377982 |
| venezuela | 0.432656 | 0.414955 | 0.331077 | 0.441544 | 0.326366 | 0.441544 |
| Macro mean | 0.431900 | 0.422754 | 0.332279 | 0.426622 | 0.332104 | 0.437884 |

The candidate beats the strongest fair baseline on two of six datasets (UAE and Iran)
by majority seed win rate. It beats the frozen system prior on four of six datasets
(UAE, Iran, Russia, and Venezuela), and its macro mean is above that prior but below
the strongest fair baseline. This is not evidence that the candidate is ready to
replace the frozen Discovery path.

The strict candidate summary above is retained as a non-claimable historical
comparison. New reproducible research outputs must use the explicit G-drive
Coordination reproduction root. C-drive temporary paths are not valid artifact
locations for future runs.

Directional one-seed ablation macro AUPRC:

| Variant | Macro AUPRC | Delta vs full |
| --- | ---: | ---: |
| full | 0.431043 | 0.000000 |
| learned_only | 0.391331 | -0.039712 |
| no_system_prior_feature | 0.371126 | -0.059917 |
| no_exact_pair_history | 0.397294 | -0.033749 |
| no_relation_memory | 0.426074 | -0.004969 |

The result indicates that the current candidate depends heavily on the system-prior
feature/ensemble and exact-pair recurrence. The present relation-memory block does
not show a reliable aggregate contribution and should be removed, regularized, or
redesigned before adding a deeper temporal GNN.

The ablation CSVs use one seed and are directional only; they do not replace a
multi-seed ablation table. This remains an account-pair self-supervised proxy. It
does not establish IOHunter user-level Coordination Detect performance and does not
activate a system model.

## Frontline Alignment Updates

- Near-duplicate evidence now uses `simhash64_lsh_token_shingle_jaccard`: SimHash bands and shared token shingles generate candidates, then Hamming distance plus shingle Jaccard or token containment confirms the match. This replaces the earlier prefix-hash behavior and is recorded under `coverage.near_duplicate_policy` as `candidate_evidence_only`.
- Evidence coverage now reports `account_edge_layer_counts` and `evidence_layer_matrix`, so CNT-style behavior layers and higher-order co-evidence can be audited without turning topology counts into model inputs.
- Dynamic community artifacts now include window-level evidence/relation counts and a membership `transition_matrix`, aligning the output with temporal multiplex community analysis while keeping the current event-level result descriptive.
- Detect validation now records the required public-labeled protocol and a `claim_readiness` block. Metrics computed without split/campaign/platform/seed metadata remain `exploratory_metrics_only` and must not be cited as supervised Detect performance.

See `DISCOVER_DETECT_FINAL_PLAN.md` for the accepted recommendation order, literature alignment, local three-platform validation, and remaining research gates.

## Method Boundary

The default model input is account id, evidence object id, relation type, and time bucket. If `lm_text_embedding`, `semantic_text_embedding`, or `text_embedding` already exists on snapshot rows, the scorer may add it as a text semantic feature. Degree, density, pagerank, object concentration, and related topology statistics are emitted as `Topology Audit Feature` rows for audit and ablation only.

Image, video, audio, OCR, ASR, frame, and media embedding fields remain excluded from the platform-generic Coordination Discover artifact. Text embeddings are accepted only as precomputed language-model features and are recorded under `representation_inputs.text_embeddings` with `policy=precomputed_only_no_synthetic_embeddings`.

Research artifacts require strict Leiden partitioning through `python-igraph` and `leidenalg` when a research artifact includes a community partition. The backend rejects Coordination Discover artifacts whose manifest does not record `partition_backend=leiden`; it also rejects this deprecated `coordination_discover-temporal-magnn-leiden-v0` model version. Leiden is an analyst-facing interpretation head and comparison component, not an activation criterion or a substitute for a learned temporal heterogeneous encoder.

Large shared objects use bounded temporal pair projection: small groups remain exhaustive, while large groups connect temporal neighbors up to a recorded cap. This prevents public keywords and discussion targets from creating unbounded complete graphs.

Near-duplicate candidate buckets are also bounded. Very common phrases can generate large shared-shingle buckets, so the runtime samples candidates with a deterministic cap and records that cap in the policy. The near-duplicate edge is evidence for analyst review and graph construction, not a label or causal assertion.

## Backend Integration

The backend is artifact-first. It validates `manifest.json` against the `EventSnapshot.data_fingerprint` and `modality_policy=platform_generic_only`; incompatible or missing artifacts fall back to `coordination-evidence-runtime-v2`.

Coordination Detect lives in `system/research/coordination_detect` and uses these representations only for public labeled validation.

## Frozen Production Proxy Comparison

The 2026-08-10 IOHunter comparison includes `coordination-evidence-runtime-v2`
through the research-only `frozen_system_evidence_prior` adapter. This adapter
starts after static relation projection and is not the complete production
Discovery pipeline. Same-protocol pairs require matching source, evaluator,
and fold fingerprints; confidence intervals use campaign means rather than 30
IID seed-fold rows.

Only Russia and Venezuela completed both methods. Production wins all four
external-account proxy metrics on Russia, while `tsgs_mhcr_compact` wins all
four on Venezuela. The cross-campaign result is unstable and the matrix is
incomplete, so the research candidate remains non-claimable and offline-only.
See `doc/research/coordination-production-comparison-20260810.md` and ADR 0015.
