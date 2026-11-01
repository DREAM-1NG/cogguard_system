---
status: accepted
date: 2026-08-03
---

# ADR 0009: Durable Review Dispatch And Model Governance Boundary

## Context

The primary CogGuard workspace is a dashboard-first analyst product. It must
explain the current evidence and the action required without exposing model
graphs, checkpoints, routing policy, or deployment controls. Those controls
still need a durable, auditable backend boundary because a Teacher advisory is
asynchronous and model activation changes future analysis behavior.

The previous implementation had two gaps:

- a Celery dispatch exception could silently fall through to an in-process
  finalizer, which is not recoverable after a backend restart;
- a production dual-approval rule could be represented by caller-supplied
  administrator IDs instead of independent authenticated approval records.

## Decision

### Product surface

The main frontend remains unchanged and dashboard-first. The Event Review Case
workflow may show only business-safe outcomes:

- case status and action required;
- evidence sufficiency, key evidence, and evidence annotations;
- the Preliminary Finding and any Review Advisory difference;
- the Confirmed Decision and analyst activity history.

The main frontend does not expose model versions, artifact paths or hashes,
agent DAGs, queue internals, activation pointers, or rollback controls.

### Teacher dispatch

`ANALYSIS_TEACHER_DISPATCH_MODE=auto` resolves to local inline fallback for
`BACKEND_ENV=local` and to queue-required dispatch for `BACKEND_ENV=production`.

- Local fallback is explicit and is suitable for a single-machine prototype.
- Production requires a durable Celery queue. A broker dispatch failure is
  persisted as a retryable failed Teacher advisory and emits a failed analysis
  event; it is never silently executed in the API process.
- Celery execution uses late acknowledgement, worker-loss rejection, and
  bounded retries. A final execution failure is persisted before the task
  reports its terminal result.

### Model activation

`ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE=auto` resolves to single-operator
activation locally and persisted dual approval in production.

- `POST /api/v2/governance/models/{model_version_id}/approvals` records one
  approval using the authenticated administrator identity. The request cannot
  name another approver.
- Production activation requires two distinct active administrator approval
  records for the same candidate, including the activating administrator.
- Local activation records one operator approval atomically before moving the
  active pointer.
- Artifact hash verification and capability quality gates are required in both
  modes. A failed gate cannot be bypassed by an approval record.
- Rollback targets a previously approved artifact and is performed by one
  active administrator as an audited recovery action; it does not create a new
  model approval requirement.

Canonical verdict approval remains a separate analyst action. A Review Advisory
or Student preliminary output can never become canonical by model activation or
by queue completion.

## Consequences

- The product workflow stays compact and explainable while backend governance
  remains inspectable through authenticated diagnostic APIs and append-only
  records.
- Local demonstrations do not require a Celery worker, while production cannot
  lose an advisory to process memory.
- Production model activation requires an operational path for two admins to
  authenticate and approve the same candidate; no frontend governance page is
  required.
- The new approval table is append-only and must be migrated before production
  activation endpoints are enabled.

## Rejected

- Put `approver_ids` in the activation request | Rejected because an ID in a
  request is not evidence that the named administrator approved anything.
- Always inline Teacher work after broker failure | Rejected because process
  memory is not durable queue state.
- Add a model-governance page to the primary frontend | Rejected because it
  exposes control-plane detail without improving the analyst decision.
- Require two administrators for the LAN prototype | Rejected because ADR 0008
  intentionally keeps the local prototype usable by one accountable operator.

## Verification

- Backend targeted regression suite covers failed dispatch, local fallback,
  executor state/event classification, activation policy, and append-only
  approval schema.
- Migration head is `a2d8e5c1b904`.
