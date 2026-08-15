# Work Tracks

| Track | Status | Scope | Next decision |
| --- | --- | --- | --- |
| Semantic evidence workbench | In progress in the existing dirty worktree | Real semantic artifacts and their `/risk` and `/propagation` projections | Preserve existing work; validate and integrate separately from structural refactoring. |
| Claim response landscape | Planned | Exact authority-account bindings and a path-backed view of official publications and influential responses | Implement after TDD and task review; do not infer official identity from names or platform verification. |
| Coordination two-stage research | Implemented with gated research claims | Discovery/Detection seam and reproduction contracts | Maintain ADR 0014 and ADR 0015 constraints. |
| Structural deepening | First cleanup cycle complete | The Review runtime now has an explicit interface, retired deterministic builders are removed, and Analysis Stage aliases are canonicalized without changing product behavior. | Hold further structural migration until the existing semantic, propagation, and Coordination work is integrated; resume from the architecture review report. |

## Structural deepening rules

- One selected module per track.
- No large move-only refactor.
- Preserve the Event Review Case product boundary and research activation gates.
- Complete focused tests, review, and documentation synchronization before starting another structural track.
