# Coordination Discover TemporalMAGNN Deprecation Notice

## Decision

`coordination_discover-temporal-magnn-leiden-v0` and the newer `magnn` Discover encoder are deprecated and non-claimable.

The implementation remains in the repository only for historical replay, negative-result analysis, and future redesign reference. It must not be used as the default system path, production artifact, or paper-facing performance claim.

The backend Coordination Discover engineering path is frozen as the system mainline. Any future research model must beat both the frozen engineering path and `magnn_legacy` under the accepted validation gates before it can be considered for system activation.

## Evidence

Bounded IOHunter validation against `magnn_legacy` showed:

| Scope | Metric | Delta |
|---|---:|---:|
| complete 5 datasets x 3 seeds | Modularity | `+0.00115` |
| complete 5 datasets x 3 seeds | Recon AUC | `-0.086226` |
| complete 5 datasets x 3 seeds | Recon AP | `-0.064126` |
| complete 5 datasets x 3 seeds, all Detect backends | Detect AUPRC | `-0.000806` |
| complete 5 datasets x 3 seeds, all Detect backends | Detect MaxF1 | `-0.003277` |

The version improves one analyst-facing community-separation signal, but causes a severe reconstruction regression and does not transfer to Detect.

## Operational Boundary

- Default Discover/Detect scripts use `magnn_legacy`.
- `magnn` can be passed explicitly only for replay or comparison.
- Backend artifact loading rejects `coordination_discover-temporal-magnn-leiden-v0` and falls back to `coordination-evidence-runtime-v2`.
- Reports must call this version deprecated/non-claimable, not mainline.

## Next Detect Direction

The next Detect iteration should optimize the supervised detector independently of this deprecated encoder:

- Run ablations for LM features, Discover embeddings, edge reweighting, community features, and relation GNN.
- Replace TF-IDF fallback with verified SBERT/XLM-R features before making semantic claims.
- Evaluate `supervised`, `scarce_supervised`, and `cross_io` protocols across IOHunter datasets.
- Add calibration, abstain, and gating so Discover features are used only when validation improves Detect.

## Replacement Research Direction

Do not keep patching `TemporalMAGNN + Leiden`. The replacement research line is a goal-aligned continuous-time heterogeneous evidence model:

1. **P0: Repair evaluation integrity first.** Use campaign/platform/time holdouts, split-safe feature fitting, matched hard negatives, 5 seeds, calibration, abstain gates, and no-edge/no-text/no-higher-order/no-Leiden ablations.
2. **P1: Build a lightweight temporal account-pair edge model.** Keep the evidence graph, but train directly on account-pair coordination targets with continuous time deltas, learnable temporal decay, relation attention, text evidence inputs, and learned edge weights. Leiden remains an explanation head only.
3. **P2: Consider full hetero-temporal GNN only after P1 passes.** Introduce account/content/object/platform node types, relation-specific message passing, and event-level temporal memory only if the lighter model improves reconstruction and downstream Detect transfer.

No future report may describe a candidate model as a system model until it beats the frozen engineering implementation under the accepted gates.
