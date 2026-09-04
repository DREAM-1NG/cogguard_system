---
status: accepted
date: 2026-08-02
extended_by: ADR-0009
---

# ADR 0008: LAN Prototype Governance Boundary

## Context

The current branch includes a local/contest prototype of the analyst workspace. The prototype must be usable by a single operator on a LAN or local machine without inventing a second authorization model that diverges from the product workspace.

The code already relies on the existing login dependency for the event-review routes, and internal activation actions remain tied to one accountable operator. Adding a separate preview-only permission model would make the prototype harder to reason about and easier to misuse.

## Decision

The LAN/local prototype uses the same login-level authorization boundary as the event-review workspace.

The prototype boundary is:

- login-gated for case browsing and edits
- role-gated for analyst actions
- single-operator for internal activation and rollback actions
- audit-logged through the existing case and governance history

The prototype does not introduce a separate preview-only role, and it does not require multi-approver activation payloads in the product surface.

## Consequences

- Analysts can use the local prototype with the same login boundary as the product workspace.
- Internal activation remains an accountable single-operator action.
- Product and prototype docs should describe the boundary as login-level access, not as a special LAN-only exception.
- The UI should not grow a second permission model just for the prototype.

## Rejected

- Add a separate preview-only role for the LAN prototype | Rejected because it would duplicate the existing login boundary without adding safety.
- Require multiple approvers for every prototype activation | Rejected because the current branch needs one accountable operator, not a second governance layer.
- Expose unauthenticated LAN preview access | Rejected because the case workspace still handles analyst-facing decisions.
- Treat the prototype as production-ready | Rejected because the current branch still needs production smoke and rollout validation.
