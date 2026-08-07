# ADR 0013: Versioned Analysis Query Projections

- Status: accepted
- Date: 2026-08-06
- Decision owners: CogGuard backend maintainers

## Context

The demonstration warmup previously called the same authenticated GET
endpoints that the browser later called. Those endpoints reconstructed the
observed propagation graph, reassembled Coordination Discover projections from
research artifacts, and converted an entire Event Review Case snapshot into
evidence items on every request. Account profile reads also reran the deployed
account detector after every backend restart. Browser asset caching could not
remove this server-side work.

## Decision

Cache immutable analysis query projections below the HTTP layer. Use a
process-local LRU for the fast path and Redis as a shared acceleration layer.
The source of truth remains MongoDB, MySQL, and the registered research
artifacts; a cache failure must fall back to the existing builder.

Every key includes a projection schema and a source identity:

- observed propagation uses the event/platform ingestion generation and query
  limit;
- coordination uses the dataset plus completed run or archive artifact
  markers and query options;
- review evidence uses the case, immutable snapshot revision, and annotation
  version.
- account detector assessments use a normalized post-corpus fingerprint plus
  the active model version, artifact hash, and activation pointer revision.

The cache never stores authentication credentials, access tokens, or model
provider secrets. No fixed TTL is used as the correctness mechanism. New crawl
data, a new completed run, a changed archive artifact, a new snapshot revision,
or a new annotation version produces a different key. The frontend response
contracts and page layout remain unchanged in this decision.

## Consequences

The first warmup still pays the real computation cost, but subsequent browser
requests and repeated warmups can read the generated projection. This removes
duplicate graph construction, account detector inference, and full-snapshot
projection work without
pretending that the first-run payloads are small. Summary-first evidence
pagination and a compact propagation viewport remain separate follow-up work.

If Redis is unavailable, correctness is preserved through the local cache and
the original builder path. A backend restart loses only the process-local
entries; a Redis-backed entry can still be reused when its version identity is
unchanged.

## Rejected alternatives

- Browser-only caching: API responses are authenticated and server computation
  still runs before a browser cache can help.
- Fixed-TTL caching: it can serve stale analysis after a crawl or model change.
- Nginx caching of authenticated API responses: it hides invalidation and
  authorization semantics from the application boundary.
- Caching by only `event_id` or `dataset_id`: it can return a result for an old
  data fingerprint or model run.

## Verification

`tests/test_analysis_query_result_cache.py` verifies deterministic version
keys and single-flight construction. `tests/test_event_data_fingerprint.py`
verifies ingestion-generation changes invalidate the propagation key. Existing
propagation, coordination, review, and account-service tests remain regression
gates.
