# Product Context

## Product

CogGuard is a local or LAN prototype for evidence-driven, cross-platform event
review of coordinated manipulation. The runnable product is entirely under
`system/`.

## Product flow

`event -> evidence -> Coordination Discover -> Propagation Analysis -> Review -> Event Review Case -> governance action`

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
- Semantic evidence assistance for the event-review workspace, with model/runtime state remaining diagnostic.

## Scope limits

- The prototype is authenticated and intended for local or LAN use.
- Coordination research outputs do not establish a harmful-CIB claim or activate production behavior without the gates in ADR 0014 and ADR 0015.
- An advisory never replaces the analyst-owned Confirmed Decision.

## Success criteria

- An analyst can follow the product flow for a real event without exposing internal runtime details in business-facing pages.
- Evidence projections are reproducible from their source identity and artifact manifest.
- Product, research, and reference code remain distinguishable and independently testable.
