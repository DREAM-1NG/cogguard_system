# Coordination Discover TemporalMAGNN Deprecation Notice

## Decision

`coordination_discover-temporal-magnn-leiden-v0` and the newer `magnn` Discover encoder are deprecated and non-claimable.

The implementation remains in the repository only for historical replay, negative-result analysis, and future redesign reference. It must not be used as the default system path, production artifact, or paper-facing performance claim.

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
