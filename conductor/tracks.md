# Work Tracks

| Track | Status | Scope | Next decision |
| --- | --- | --- | --- |
| Semantic evidence workbench | In progress in the existing dirty worktree | Real semantic artifacts and their `/risk` and `/propagation` projections | Preserve existing work; validate and integrate separately from structural refactoring. |
| Coordination two-stage research | Implemented with gated research claims | Discovery/Detection seam and reproduction contracts | Maintain ADR 0014 and ADR 0015 constraints. |
| Structural deepening | In progress | The first completed subtask narrowed the Review runtime interface and removed retired builders without changing runtime behavior. | Decide the next deepening candidate only after the current Review runtime interface remains stable. |

## Structural deepening rules

- One selected module per track.
- No large move-only refactor.
- Preserve the Event Review Case product boundary and research activation gates.
- Complete focused tests, review, and documentation synchronization before starting another structural track.
