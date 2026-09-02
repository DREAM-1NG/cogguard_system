# ADR Index

This index tracks every accepted CogGuard ADR in the canonical `doc/adr/` directory. When a newer decision changes an older one, the index records the supersession while preserving the accepted body.

| ADR | Title | Body | Status | Note |
| --- | --- | --- | --- | --- |
| 0001 | Review uses analyst-triggered MARO-style LLM agent reviews | [body](0001-review-manual-maro-agent-review.md) | partially superseded | ADR 0007 supersedes only the manual-trigger-only rule; its evidence and advisory constraints remain current. |
| 0002 | Review MARO-style self-iteration uses auditable policy refinement | [body](0002-review-maro-self-iteration-policy-loop.md) | accepted | Internal policy refinement decision; still informative for research and runtime boundaries. |
| 0003 | Semantic Package Governance | [body](0003-semantic-package-governance.md) | accepted | Extended by the Event Review Case vocabulary; its semantic package rules remain current. |
| 0004 | Review First-Stage Student Boundary | [body](0004-review-text-mainline-student-boundary.md) | superseded | Superseded by ADR 0010; ADR 0007 separately supersedes the manual-trigger-only product rule. |
| 0005 | System Governance And Documentation Sync | [body](0005-system-governance-and-documentation-sync.md) | accepted | Current documentation-sync contract and package policy. |
| 0006 | Review PropagationTreeAgent Evidence Boundary | [body](0006-review-propagation-tree-agent-boundary.md) | accepted | Narrow runtime evidence rule for Teacher Review. |
| 0007 | Event Review Case Product Boundary | [body](0007-event-review-case-product-boundary.md) | accepted | Product-facing case workspace and automatic review routing. |
| 0008 | LAN Prototype Governance Boundary | [body](0008-lan-prototype-governance-boundary.md) | partially superseded | Local login and single-operator rule remains; production governance is extended by ADR 0009. |
| 0009 | Durable Review Dispatch And Model Governance Boundary | [body](0009-durable-review-and-model-governance-boundary.md) | accepted | Durable Teacher dispatch and authenticated model approvals. |
| 0010 | Student Review Runtime And Distillation | [body](0010-review-student-runtime-and-distillation.md) | accepted | XLM-R heads, latent rationale distillation, external hardcase routing, and checkpoint-gated deployment. |
