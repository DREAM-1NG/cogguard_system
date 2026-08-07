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
computation, graph initialization, and full evidence transfer. The delivery
layer can safely remove development-server overhead and prepare static route
assets, but it must not pre-run analysis or fetch business data merely to make
a navigation feel fast.

## Decision

- Keep Vite only as the explicit `-DevelopmentFrontend` workflow.
- Make `system/start-system.ps1` the default static-first delivery sequence:
  infrastructure, explicit indexes, migrations, backend health, then the
  `production-ui` Compose profile.
- Generate browser delivery metadata from the Vite manifest on every
  `npm run build`. Prepare only the authenticated layout and dashboard shell in
  idle time; prepare other route chunks on navigation hover or focus.
- Never prefetch API data, execute a route, run account inference, load full
  review evidence, or preload Three.js graph assets merely for delivery.
- Cache only content-addressed `/assets/*` responses; do not cache HTML, API
  responses, or review event streams.
- Reverse-proxy API calls to the existing backend origin and disable buffering
  for the review event stream.
- Define a versioned, explicit MongoDB index operation for the current
  `raw_posts` and `raw_comments` query shapes.
- Make index application idempotent and fail on a same-name/different-key
  conflict; never drop indexes automatically.

## Consequences

The delivery profile removes development-server overhead, gives repeat visits
compressed immutable assets, and prepares low-risk static route dependencies
without changing product-side data behavior. The index operation improves
selection and ordering for existing scoped queries when collection size
warrants it.

This does not resolve full evidence payloads, page-instance recreation,
full-corpus account inference, or graph rendering. Those remain separately
measured product-source work.

## Rejected

- Cache authenticated API responses in Nginx | Rejected because case state,
  analyst decisions, and activity events must remain current.
- Run unbounded model or API warmup during delivery startup | Rejected because
  it would delay availability, consume resources without an analyst request,
  and create hidden business execution.
- Preload all route chunks | Rejected because graph and analytical chunks
  compete with the dashboard first paint and can exceed constrained networks.
- Change page lifecycle, data contracts, or analytical code in this pass |
  Rejected because the scope explicitly excludes frontend and backend
  implementation changes.

## Verification

- Validate Compose interpolation and the Nginx template before deployment.
- Run the index script in dry-run mode before applying it to a live MongoDB
  collection.
- Capture a cold and repeat route trace after enabling the static profile.
