# Coordination Discover Research Cutover

## Status

Accepted on 2026-08-05. This document supersedes conflicting research-model
descriptions in the older coordination detection background document.

## System Mainline

The backend system mainline is the evidence-constrained dynamic Coordination
Discover path:

`EventSnapshot -> evidence graph -> coordinated evidence edges -> dynamic
communities -> evidence and ordinal risk output`

The mainline keeps:

- platform-generic evidence extraction;
- directed weighted account multigraphs;
- higher-order co-evidence as auditable evidence;
- centered overlapping windows and community lineage;
- Leiden as an analyst-facing community partition and interpretation component.

The mainline does not use the research `TemporalMAGNN + Leiden` encoder.

## Research Model Boundary

`coordination_discover-temporal-magnn-leiden-v0` and the newer `magnn` encoder
are deprecated and non-claimable. They remain available for replay, comparison,
and negative-result analysis only.

The current scorer is not a full MAGNN, HGT, TGN, or graph foundation model.
It is a shallow account/object/relation/time embedding scorer with optional
precomputed text projection. Leiden is a post-hoc partitioner and cannot be
used as evidence that reconstruction or Detect performance improved.

## Replacement Research Direction

The replacement research line is:

**evidence-constrained continuous-time heterogeneous coordination encoder +
account-pair coordination decoder + dynamic-community auxiliary head**

The work must proceed in this order:

1. **P0: Evaluation integrity**
   - Hold out by campaign, platform, and event time.
   - Fit TF-IDF/SVD/scalers and text representations on training data only.
   - Use matched hard negatives by relation, time, platform, and degree.
   - Run 5 seeds with confidence intervals, calibration, and abstain metrics.
   - Require no-edge, no-text, no-higher-order, and no-Leiden ablations.

2. **P1: Lightweight temporal edge model**
   - Keep the existing evidence graph and provenance.
   - Predict account-pair coordination directly.
   - Use continuous time deltas, learnable temporal decay, relation attention,
     text evidence inputs, and learned edge weights.
   - Keep Leiden outside the main scoring path as an interpretation head.

3. **P2: Full hetero-temporal GNN**
   - Add account, content, object, and platform node types.
   - Add relation-specific message passing and event-level temporal memory.
   - Add dynamic-community consistency only as an auxiliary objective, never as
     a fabricated label.

## Activation Gate

A candidate research model may become the system model only when it beats both
the frozen engineering mainline and `magnn_legacy` under the same protocol.
Modularity improvement alone is insufficient. The candidate must not regress
reconstruction quality or labeled Detect transfer, and all reported gains must
survive the split, seed, calibration, and leakage gates.

## References

- `docs/adr/0012-coordination-discover-research-model-cutover.md`
- `system/research/coordination_discover/DEPRECATION_NOTICE.md`
- `system/research/coordination_discover/DISCOVER_DETECT_FINAL_PLAN.md`
