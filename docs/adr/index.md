# ADR Index

This index tracks the current ADR set for the event-review refactor. Historical accepted bodies remain under `doc/adr/` and are left unchanged. When an older decision conflicts with the current product boundary, this index marks it `superseded` instead of rewriting the accepted body.

| ADR | Title | Body | Status | Note |
| --- | --- | --- | --- | --- |
| 0001 | Review uses analyst-triggered MARO-style LLM agent reviews | [`doc/adr/0001-review-manual-maro-agent-review.md`](../../doc/adr/0001-review-manual-maro-agent-review.md) | partially superseded | ADR 0007 supersedes only the manual-trigger-only rule; its evidence and advisory constraints remain current. |
| 0002 | Review MARO-style self-iteration uses auditable policy refinement | [`doc/adr/0002-review-maro-self-iteration-policy-loop.md`](../../doc/adr/0002-review-maro-self-iteration-policy-loop.md) | accepted | Internal policy refinement decision; still informative for research and runtime boundaries. |
| 0003 | Semantic Package Governance | [`doc/adr/0003-semantic-package-governance.md`](../../doc/adr/0003-semantic-package-governance.md) | accepted | Extended by the Event Review Case vocabulary; its semantic package rules remain current. |
| 0004 | Review First-Stage Student Boundary | [`doc/adr/0004-review-text-mainline-student-boundary.md`](../../doc/adr/0004-review-text-mainline-student-boundary.md) | partially superseded | ADR 0007 supersedes only the manual-trigger-only rule; its deployable review runtime boundary remains current. |
| 0005 | System Governance And Documentation Sync | [`doc/adr/0005-system-governance-and-documentation-sync.md`](../../doc/adr/0005-system-governance-and-documentation-sync.md) | accepted | Still current as the documentation-sync contract and package-boundary policy. |
| 0006 | Review PropagationTreeAgent Evidence Boundary | [`doc/adr/0006-review-propagation-tree-agent-boundary.md`](../../doc/adr/0006-review-propagation-tree-agent-boundary.md) | accepted | Narrow runtime evidence boundary; still relevant for internal review research. |
| 0007 | Event Review Case Product Boundary | [`docs/adr/0007-event-review-case-product-boundary.md`](0007-event-review-case-product-boundary.md) | accepted | Current product-facing boundary for the case workspace and automatic review routing. |
| 0008 | LAN Prototype Governance Boundary | [`docs/adr/0008-lan-prototype-governance-boundary.md`](0008-lan-prototype-governance-boundary.md) | partially superseded | Local login and single-operator prototype boundary remains current; production governance is extended by ADR 0009. |
| 0009 | Durable Review Dispatch And Model Governance Boundary | [`docs/adr/0009-durable-review-and-model-governance-boundary.md`](0009-durable-review-and-model-governance-boundary.md) | accepted | Establishes business-safe frontend boundaries, durable Teacher dispatch, authenticated persisted model approvals, and the current `/api/v2/governance` control-plane prefix. |
