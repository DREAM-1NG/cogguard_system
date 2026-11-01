---
status: accepted
date: 2026-08-02
---

# ADR 0007: Event Review Case Product Boundary

## Context

The current branch exposes a new analyst-facing case workspace built around one event, one case, and one evidence trail. The implementation already includes:

- one durable case per event
- immutable snapshot revisions
- evidence annotations grouped by case
- draft autosave and immutable decision confirmation
- case activity history and SSE recovery
- automatic routing after successful event collection

The product boundary needs to name this workspace directly and keep internal execution details out of product copy. The workspace should describe what analysts see and do, not the internal runtime graph that produced the current case state.

## Decision

CogGuard uses **Event Review Case** as the product-facing boundary for the analyst workspace.

This decision supersedes only the manual-trigger-only portions of ADR 0001 and ADR 0004. Their remaining research, evidence, distillation, and advisory constraints continue to apply.

The Event Review Case product surface is the `review-cases` API family and the case workspace UI. It exposes:

- latest, search, and detail views
- grouped evidence and evidence annotations
- review advisory requests
- draft decision autosave
- confirmed decision creation
- case activity history and streaming recovery

Automatic routing remains part of the implementation. After successful event collection, the backend may create or revise a case, run the internal review routing path, and request a review advisory when evidence sufficiency or urgency warrants it. The analyst can still request a review advisory manually.

Internal diagnostic routes remain behind `/api/v2/analysis` and are not part of product copy.

## Consequences

- Product copy must use `Event Review Case`, `Preliminary Finding`, `Review Advisory`, `Confirmed Decision`, `Evidence Sufficiency`, `Evidence Annotation`, and `Case Activity`.
- Product copy must not surface internal execution details such as run, job, task, model, checkpoint, artifact, or Agent terminology.
- The case workspace can keep its automatic routing behavior without exposing the internal routing graph as a product object.
- The older `Risk Review` wording is no longer the product boundary and should be treated as legacy/internal vocabulary only.

## Rejected

- Keep the product boundary as `Risk Review` | Rejected because the new case workspace is event-scoped and product-safe, while `Risk Review` leaks internal implementation language.
- Expose internal analysis execution details in the product UI | Rejected because analysts need the workspace outcome, not the internal runtime graph.
- Split the workspace into separate product objects for evidence, advisories, and decisions | Rejected because the current branch already models them as one case aggregate.
- Rename the case workspace with numbered shorthand | Rejected because numbered shorthand is not part of the current system language.
