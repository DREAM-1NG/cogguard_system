# Work Tracks

| Track | Status | Scope | Next decision |
| --- | --- | --- | --- |
| Frontend API contract integrity | Implemented in the existing dirty worktree | Page clients use their API-version base and contract tests protect mounted route prefixes | Keep v1 and v2 clients explicit; add a contract test whenever a new versioned client is introduced. |
| Crawl evidence workbench | Source checkpointed, acceptance pending | `/crawl` grouped retrieval-term controls, selected-job scoped posts/comments, and manifest-backed local media previews | Restore `vue-tsc`, scope batch media download to the selected Crawl Job, remove legacy filesystem-path exposure, then run task-visibility, media-root, manifest ownership, Range-response, and browser contracts. Keep remote URLs out of the preview path. |
| Semantic evidence workbench | Integrated for the Trump-visit event | Real semantic artifacts and their `/risk` and `/propagation` projections, with event-window freshness validation and fail-closed mismatch handling | Preserve the fixed local model revisions and rerun semantic enrichment only for a new immutable snapshot; never serve a stale artifact. |
| Claim response landscape | Integrated for the Trump-visit event; exact per-path semantic overlay available | Exact authority-account bindings, observed path evidence, and per-path real semantic overlays | Direct comment threads provide 130 observed primary-claim paths. Collect explicit repost and quote parent-child relations to extend coverage beyond comment threads; keep every path bound to the primary claim, official publication, and observed record identifiers. |
| Coordination runtime completion | Implemented in the existing dirty worktree | Cross-platform resolution, evidence-constrained Discovery, SocGFM primary Detection dispatch, China checkpoint local precompute for uploaded unlabeled data, frontend primary-verdict display, archive replay score demotion, read-time historical-prediction projection, and research-only MAGNN-Leiden hybrid registration | Keep classifier/archive replay output shadow or audit-only, distinguish read-time projections from new inference, keep online v1 as precomputed member-probability aggregation, keep `magnn_leiden_hybrid_discovery` research-only, and run the full proxy/stability matrix before any Discovery cutover claim. |
| Coordination two-stage research | Implemented with gated research claims | Discovery/Detection seam and reproduction contracts | Maintain ADR 0014 and ADR 0015 constraints; report LEN/IOHunter/Twitter-family results as proxy/stability evidence unless task-aligned Gold labels exist. |
| Structural deepening | First cleanup cycle complete | The Review runtime now has an explicit interface, retired deterministic builders are removed, and Analysis Stage aliases are canonicalized without changing product behavior. | Hold further structural migration until the existing semantic, propagation, and Coordination work is integrated; resume from the architecture review report. |
| MARO Teacher + Text Student | Coding stage in progress | Typed Review task/evidence/policy/rationale contracts, bounded MARO-compatible orchestration, strict Teacher Silver gate, offline hard-case manifest, and the isolated HateCoT source-train/source-dev/held-out-target experiment adapter. | Complete the expanded protocol dry-run and targeted validation; keep live DeepSeek execution, Student distillation, and multimodal work in explicitly scoped experiment tracks. |

## Structural deepening rules

- One selected module per track.
- No large move-only refactor.
- Preserve the Event Review Case product boundary and research activation gates.
- Complete focused tests, review, and documentation synchronization before starting another structural track.
- Keep Review Student, Review Teacher, EvidenceRAG, PolicyRAG, ReasonBank, and
  Countermeasure boundaries explicit; do not reintroduce a unified risk label
  or an automatic defer/Teacher trigger as part of this track.
