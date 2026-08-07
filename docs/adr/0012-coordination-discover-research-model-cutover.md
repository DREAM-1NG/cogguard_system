# ADR-0012: Coordination Discover Research Model Cutover

## Status

Accepted

## Date

2026-08-05

## Context

The backend Coordination Discover path has a closed engineering loop:
`EventSnapshot -> evidence graph -> coordinated evidence edges -> dynamic communities -> ordinal risk/evidence output`.
This path is useful for product demonstration, analyst review, provenance tracking, and unlabeled event case studies.

The research runtime branch named `coordination_discover-temporal-magnn-leiden-v0`
and the newer `magnn` encoder did not improve the research metrics that matter.
Bounded IOHunter validation against `magnn_legacy` showed severe reconstruction
regression:

- Recon AUC delta: `-0.086226`
- Recon AP delta: `-0.064126`
- Detect AUPRC delta across all backends: `-0.000806`
- Detect MaxF1 delta across all backends: `-0.003277`
- Modularity delta: only `+0.00115`

The current research encoder is not a full MAGNN, HGT, TGN, or graph foundation
model. It is a shallow account/object/relation/time embedding scorer with optional
precomputed text projection, followed by Leiden community partitioning. Leiden is
valuable as an analyst-facing community explanation backend, but it does not prove
edge reconstruction quality or downstream Detect performance.

## Decision

Freeze the current backend Coordination Discover engineering implementation as the
system mainline.

Deprecate the `TemporalMAGNN + Leiden` research branch for activation and
paper-facing claims. It remains in the repository only for historical replay,
negative-result analysis, and comparison.

Redirect the research model line to a goal-aligned continuous-time heterogeneous
evidence model:

1. **P0: Evaluation repair first.** Use campaign/platform/time holdouts, 5 seeds,
   split-safe feature fitting, matched hard negatives, calibration, abstain gates,
   and no-edge/no-text/no-higher-order/no-Leiden ablations.
2. **P1: Lightweight temporal edge model.** Keep the evidence graph, but train
   directly on account-pair coordination targets with continuous time deltas,
   learnable temporal decay, relation attention, text evidence inputs, and learned
   edge weights.
3. **P2: Full hetero-temporal GNN only after P1 passes.** Introduce account,
   content, object, and platform node types plus relation-specific message passing
   and event-level temporal memory only if the lighter model improves reconstruction
   and Detect transfer.

No new research model can become the system model unless it beats the frozen
engineering implementation and `magnn_legacy` under the accepted validation gates.

## Consequences

### Positive

- The product path stays stable and explainable.
- Failed research results remain visible instead of being silently overwritten.
- Future research work starts from a clear metric and protocol gate.
- Leiden stays useful as an interpretation component without being overclaimed as
  a supervised Detect method.

### Negative

- The current research runtime cannot support performance claims.
- Engineering and research paths remain split until a new model passes the gates.
- Model work must spend effort on evaluation integrity before adding architecture
  complexity.

## Implementation Notes

- Backend artifact loading must continue to reject
  `coordination_discover-temporal-magnn-leiden-v0` for system activation.
- Reports must describe `TemporalMAGNN + Leiden` as deprecated/non-claimable.
- Detect claims require labeled IOHunter-style validation with holdout metadata,
  AUPRC, MaxF1, ECE, abstain rate, and confidence intervals.
- The system model activation decision must be explicit and recorded in a future
  ADR after successful experiments.

## Related Documents

- `system/research/coordination_discover/DEPRECATION_NOTICE.md`
- `system/research/coordination_discover/DISCOVER_DETECT_FINAL_PLAN.md`
- `system/research/coordination_discover/README.md`
