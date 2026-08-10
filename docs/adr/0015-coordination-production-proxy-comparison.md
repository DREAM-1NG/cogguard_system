# ADR 0015: Coordination Production Proxy Comparison Boundary

- Status: accepted
- Date: 2026-08-10
- Decision owners: CogGuard research and backend maintainers
- Related: ADR 0012, ADR 0014

## Context

IOHunter can evaluate external-account recovery from five static relation
layers. It cannot reconstruct the production EventSnapshot evidence graph,
observed-time windows, null-model controls, dynamic community lineage,
domain-shift checks, abstention, or harmful-CIB Detection.

The frozen production graph core also uses NetworkX greedy modularity on the
complete projected graph. A China proxy attempt exceeded 14 minutes, while
larger UAE projections created avoidable memory pressure before execution.

## Decision

The method named `frozen_system_evidence_prior` is limited to
`post_evidence_projection_static_graph_only` and must retain explicit claim
markers. It invokes the canonical production graph and account-stat core. Its
account ranking is the normalized production weighted degree and is not a
probability or the complete production risk tier.

Same-protocol pairs must match `fold_id`, source-layer fingerprint, source
checksum, evaluator fingerprint, fold fingerprint, and evaluation scope.
Mismatches block the claim.

Statistical inference uses campaign means over the coupled seed-fold rows.
The five folds within one campaign are not treated as five independent
datasets. The current protocol still couples model seed and fold and therefore
does not establish pure cross-seed stability.

The frozen proxy has a 100,000 source-relation-occurrence offline safety gate.
Above the gate it blocks before fusion. It must not truncate the graph, replace
greedy modularity, or report a substituted algorithm under the frozen method
identity. Deterministic successful projections may be cached within one
campaign for evaluation against multiple folds; runtime reporting uses the cold
projection duration.

## Consequences

- Proxy score differences cannot establish end-to-end production superiority.
- Incomplete campaigns keep the 30-pair claim gate blocked.
- Runtime can be described for completed proxy pairs, but equal-compute and
  method-peak-memory claims remain blocked.
- A scalable production-style community baseline must use a separate method
  identity and cannot silently replace the frozen baseline.

## Verification

The compact Discovery and matrix tests cover deterministic cached projections,
pre-fusion runtime blocking, provenance mismatch rejection, campaign-level
bootstrap summaries, runtime claim boundaries, and fixed blocked claims.
