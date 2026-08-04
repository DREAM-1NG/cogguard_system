---
status: accepted
date: 2026-08-04
---

# ADR 0011: Static Delivery And Query Index Operations

## Context

The product frontend is normally served by Vite during local development. That
mode intentionally retains hot-module tooling and does not provide a production
static-asset cache policy. The product also reads MongoDB event data through
event, platform, time, and crawl-job filters, but index creation was not a
managed deployment operation.

The observed page-transition delay also includes route recreation, analytical
computation, graph initialization, and full evidence transfer. Those are
product-source concerns and are out of scope for this decision.

## Decision

- Keep Vite as the local development server.
- Provide an opt-in `production-ui` Compose profile that builds the existing
  frontend and serves it with Nginx.
- Cache only content-addressed `/assets/*` responses; do not cache HTML, API
  responses, or review event streams.
- Reverse-proxy API calls to the existing backend origin and disable buffering
  for the review event stream.
- Define a versioned, explicit MongoDB index operation for the current
  `raw_posts` and `raw_comments` query shapes.
- Make index application idempotent and fail on a same-name/different-key
  conflict; never drop indexes automatically.

## Consequences

The delivery profile removes development-server overhead and allows repeat
visits to reuse compressed, immutable build assets without changing frontend
or backend implementation code. The index operation improves selection and
ordering for existing scoped queries when collection size warrants it.

This does not resolve full evidence payloads, page-instance recreation,
full-corpus account inference, or graph rendering. Those remain separately
measured product-source work.

## Rejected

- Cache authenticated API responses in Nginx | Rejected because case state,
  analyst decisions, and activity events must remain current.
- Create indexes during backend startup | Rejected because large builds are an
  operational concern and must not delay or destabilize application startup.
- Change page lifecycle, data contracts, or analytical code in this pass |
  Rejected because the scope explicitly excludes frontend and backend
  implementation changes.

## Verification

- Validate Compose interpolation and the Nginx template before deployment.
- Run the index script in dry-run mode before applying it to a live MongoDB
  collection.
- Capture a cold and repeat route trace after enabling the static profile.
