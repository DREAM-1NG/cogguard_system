---
status: accepted
date: 2026-08-15
---

# Propagation Monitoring Alert Lifecycle

## Context

Observed Propagation Analysis and Propagation Forecast were available only as
on-demand views. Analysts had no event-scoped configuration, periodic
evaluation, durable evidence snapshot, deduplication, or disposition audit.
Putting those concerns into the propagation graph builder would mix observed
facts, predictive output, and operational state.

## Decision

Propagation Monitoring owns a separate operational lifecycle.

- `PropagationMonitorProfile` stores event/platform scope, enablement,
  interval, effective thresholds, and the last successful snapshot.
- Each due cycle creates an `EventSnapshot`, reuses observed analysis,
  forecast, and coordination detection, then evaluates four signals:
  propagation surge, forecast scale jump, path structure change, and
  coordination spread.
- A `PropagationAlert` is deduplicated by event, platform, and alert type for
  thirty minutes. An open alert is refreshed with the latest snapshot rather
  than duplicated.
- A `PropagationAlertAction` is append-only. Administrator and analyst actions
  are acknowledge, ignore, and close, with actor and note recorded.
- Celery Beat checks for due profiles every minute. The profile's own interval,
  five minutes by default, determines whether a cycle runs.

## Consequences

- The propagation graph builder remains an observed-analysis projection and is
  not coupled to database alert state.
- The monitoring service is the only owner of snapshots, deduplication, and
  disposition persistence; the alert service remains a pure rule module.
- A profile may use the active unified checkpoint for any collected platform
  scope, but the UI must not claim platform-specific validation that has not
  been performed.
- Deployment must run MySQL, MongoDB, Redis, Celery worker, and Beat for
  periodic monitoring. Unit and frontend tests verify contracts but do not
  replace that deployment smoke test.

## Rejected

- Browser-only polling and in-memory alerts: rejected because evidence and
  analyst actions would disappear on reload or process restart.
- Calling the legacy speed/acceleration predictor when checkpoint inference is
  unavailable: rejected because it would make alert evidence semantically
  inconsistent with the trend page.
- Creating a new alert on every monitoring cycle: rejected because sustained
  signals need one continuously updated case for analyst review.
