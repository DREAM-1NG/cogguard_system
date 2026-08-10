# Coordination Research Candidate vs Frozen Production Prior

Date: 2026-08-10

## Decision

`tsgs_mhcr_compact` has not demonstrated stable superiority over the frozen
`coordination-evidence-runtime-v2` production prior. The research candidate
remains offline-only and the production activation pointer is unchanged.

The comparison is deliberately narrow. IOHunter provides five static account
relation layers and external-account labels, but no original evidence objects,
observed timestamps, true coordination edges, true communities, or harmful-CIB
Gold labels. The production adapter therefore evaluates only
`post_evidence_projection_static_graph_only`; it is not an end-to-end production
run.

## Reproduction Identity

- Output: `G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-system-comparison-v2-20260810`
- Manifest fingerprint: `sha256:212d330fccaea9f4bbf603e79ae5771404cb1f5c22301ea5f2ceb466ca8a7ac3`
- Matrix implementation: `task-7c-compact-matrix-v4`
- Claim schema: `cogguard.iohunter-compact-claims/v2`
- Methods: `tsgs_mhcr_compact`, `frozen_system_evidence_prior`
- Requested folds: seeds `42..46`, coupled one-to-one with official folds
- Rows: 50 (`35 success`, `15 blocked`)
- Claim inference unit: campaign mean over the five paired seed-fold rows
- Bootstrap: 5,000 resamples, seed 11, 95% interval

Cuba was excluded from the final five-campaign execution after its 1.8 GB
pickle repeatedly failed or stalled during deserialization under the available
workstation memory. The preceding full-v2 matrix records five `MemoryError`
rows for every method on Cuba. This is a dataset-load capability failure, not a
method score.

## Same-Protocol Results

Values are mean +/- sample standard deviation over five official folds. For the
candidate, this also includes model-seed variation because the current protocol
couples model seed and fold. For the deterministic production prior, variation
comes from the evaluation folds.

| Campaign | Method | AUPRC | Macro F1 | Recall@K | ROC-AUC |
| --- | --- | ---: | ---: | ---: | ---: |
| Russia | Research candidate | 0.511387 +/- 0.063561 | 0.535261 +/- 0.064178 | 0.385455 +/- 0.067297 | 0.509724 +/- 0.056602 |
| Russia | Frozen production prior | **0.852149 +/- 0.024187** | **0.842536 +/- 0.025449** | **0.749091 +/- 0.056627** | **0.810194 +/- 0.029014** |
| Venezuela | Research candidate | **0.891058 +/- 0.017461** | **0.898928 +/- 0.022788** | **0.842991 +/- 0.027566** | **0.978581 +/- 0.004803** |
| Venezuela | Frozen production prior | 0.817088 +/- 0.028002 | 0.867901 +/- 0.019152 | 0.764486 +/- 0.028347 | 0.946296 +/- 0.008092 |

Only Russia and Venezuela completed both methods. Across those two campaign
means, candidate-minus-production was negative for every metric:

| Metric | Mean delta | Campaign-bootstrap 95% interval | Gate |
| --- | ---: | ---: | --- |
| AUPRC | -0.133396 | [-0.340762, 0.073970] | blocked: 10/30 pairs |
| Macro F1 | -0.138124 | [-0.307276, 0.031027] | blocked: 10/30 pairs |
| Recall@K | -0.142566 | [-0.363636, 0.078505] | blocked: 10/30 pairs |
| ROC-AUC | -0.134093 | [-0.300470, 0.032285] | blocked: 10/30 pairs |

The direction reverses by campaign: production wins all four metrics on Russia,
while the candidate wins all four on Venezuela. This is evidence of domain
sensitivity, not stable superiority.

## Runtime And Coverage

The recorded candidate execution times are lower on the two completed static
projections, but this is descriptive only. It is neither an equal-compute-budget
claim nor an equal-timer-boundary claim: candidate rows use outer wall-clock
execution while production rows retain a cold projection timer. The candidate
controls selected edge count; the frozen production graph core consumes the
complete projected graph and uses NetworkX greedy modularity.

| Campaign | Accounts | Projected relation occurrences | Candidate mean runtime | Production cold projection |
| --- | ---: | ---: | ---: | ---: |
| Russia | 716 | 10,968 | 0.2003 s | 4.8154 s |
| Venezuela | 5,021 | 57,749 | 0.7057 s | 109.7550 s |

The frozen adapter blocks before graph fusion above 100,000 source relation
occurrences. It does not truncate the graph or replace the production
algorithm. China, Iran, and UAE produced five explicit production-budget blocks
each; their candidate rows succeeded. A prior uncontrolled China attempt spent
more than 14 minutes in greedy modularity before termination, motivating this
reproducible safety gate.

Method-level peak-memory superiority is not claimable. Python `tracemalloc` and
the shared evaluator estimate do not measure Torch and NetworkX allocations in
an equivalent way.

## Where The Candidate Has Not Surpassed Production

1. **Russia account recovery:** the candidate trails the production prior by
   roughly 0.30 to 0.36 on all four external-account proxy metrics.
2. **Cross-campaign stability:** wins reverse between the only two comparable
   campaigns, and all campaign-level confidence intervals cross zero.
3. **Production semantics:** the candidate has not been compared against
   production evidence extraction, overlapping temporal windows, null-model
   controls, perturbation stability, domain-shift reporting, abstention, or risk
   tiers. IOHunter cannot represent these inputs.
4. **Harmful-CIB Detection:** neither method was evaluated on harmful-CIB Gold.
   External-account recovery is not Coordination Detect.
5. **Pure seed stability:** model seed and official fold remain coupled. The
   current standard deviations cannot separate optimization variance from fold
   variance.
6. **Method memory:** the current probes are not comparable enough to support a
   memory claim.

The likely Russia failure is objective/ranking mismatch rather than edge-budget
loss: Russia has only 9,715 fused edges, so the candidate does not sparsify it.
The candidate multiplies evidence strength by self-supervised MHCR affinity and
blends weighted degree, incident strength, and cluster coherence into account
scores. IOHunter's external-account labels strongly favor the simpler
production weighted-degree prior on this campaign. This is a diagnostic
hypothesis; true coordination-edge labels are absent.

## Next Research Gate

1. Fully cross model seeds and official folds, then use campaign-clustered
   inference rather than treating 30 rows as independent datasets.
2. Diagnose Russia with account-rank error analysis and score-component
   ablations: production weighted degree, candidate evidence-only score, MHCR
   affinity, and cluster-coherence term.
3. Add a streaming or scalable production community baseline instead of hiding
   greedy-modularity timeouts, but keep it as a separately named baseline.
4. Evaluate true Discovery only on data with coordination-edge/community Gold
   or a defensible temporal self-supervised protocol.
5. Run Stage 2 only on an approved harmful-CIB corpus. Do not infer Detect
   quality from IOHunter external-account labels.

## Verification And Integrity

- 95 extended compact loader, execution, matrix protocol, production network,
  and adapter tests passed.
- Python compile checks and `git diff --check` passed.
- All 50 row files and three derived artifacts match the checksums recorded in
  the final manifest.
- Independent experiment audit verdict: `WARN`. Ground-truth provenance, metric
  computation, result existence, and executed call paths passed; scope and
  evaluation-type checks warn because only 10/30 production pairs exist and
  the task is an external-account proxy rather than coordination Gold.
- External Claude/Gemini cross-provider audit attempts returned upstream
  503/500 errors. The completed independent reviewer was a read-only GPT-5.4
  subagent.
