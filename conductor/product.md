# Product Context

## Product

CogGuard is a local or LAN prototype for evidence-driven, cross-platform event
review of coordinated manipulation. The runnable product is entirely under
`system/`.

## Product flow

`Event Review Case -> evidence -> Coordination Discover / Coordination Detection / Propagation Analysis / Review -> findings and advisory -> Confirmed Decision -> governance action`

An Event Review Case is the product-facing aggregate. Event Snapshot,
Analysis Run, model checkpoints, artifact paths, and queue internals are
diagnostic concepts, not primary product copy.

## Users

| User | Need |
| --- | --- |
| Analyst | Inspect evidence, compare coordination and propagation signals, request advisory review, and record a Confirmed Decision. |
| Operator | Start the local prototype, maintain infrastructure, and diagnose governed runtime failures. |
| Research maintainer | Improve research packages without promoting unsupported research claims into the product runtime. |

## Implemented product capabilities

- Evidence acquisition from Weibo, Douyin, Xiaohongshu, and news.
- Event Review Case evidence, annotation, advisory, draft, decision, and activity workflows.
- Coordination Discover, Propagation Analysis, and Review as evidence-producing capabilities.
- Coordination Discover workspace now surfaces cross-platform resolution, cluster discovery, and cluster-level detection evidence as analyst-facing workflow stages.
- Semantic Evidence Assistance for the event-review workspace, with model/runtime state remaining diagnostic.
- Claim Response Landscape as an observed Propagation Analysis projection: it
  aligns a bound authority claim, exact official-account publications,
  influential account responses, and path-backed evidence without changing a
  case conclusion. A graph edge, account name, certification, follower count,
  or shared topic is never treated as a claim-response path without its
  observed path identity and evidence references.

## Scope limits

- The prototype is authenticated and intended for local or LAN use.
- Coordination research outputs do not establish a harmful-CIB claim or activate production behavior without the gates in ADR 0014 and ADR 0015.
- An advisory never replaces the analyst-owned Confirmed Decision.

## Success criteria

- An analyst can follow the product flow for a real event without exposing internal runtime details in business-facing pages.
- Evidence projections are reproducible from their source identity and artifact manifest.
- Product, research, and reference code remain distinguishable and independently testable.

## Review implementation boundary

- The product exposes Review as an analyst workflow, not as a public Agent graph.
- Review Student provides a low-cost synchronous preliminary analysis; Review
  Teacher provides an analyst-triggered advisory audit.
- A Student-generated hard-case candidate is an internal work item only. It
  does not automatically invoke Teacher Review or change a Confirmed Decision.
- EvidenceRAG, PolicyRAG, and rationale supervision are internal implementation
  details. Their provenance and quality fields remain available to audit code.
- Countermeasure is an explicit post-Judge advisory capability with human
  approval and no automatic publication. Multimodal consistency remains a
  later candidate capability.
