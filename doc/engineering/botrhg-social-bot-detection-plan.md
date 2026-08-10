# Chinese Account Detection And BotRHG Delivery Plan

Updated: 2026-08-07

## Purpose

`BotRHG` names the repository's internal NLPCC-submission method direction for
Chinese account automation detection. The implementation combines a Chinese
text encoder, account-level detector features, support-hyperedge reasoning,
reliability-guided routing, and selective residual correction. It is an
internal research method, not a published-paper result and not an external
runtime dependency.

The active boundary is `system/research/social_bot_detection/`. The external
research directory is reference material only and must not be imported or
executed by CogGuard.

## Delivery Architecture

| Layer | Responsibility | Delivery status |
| --- | --- | --- |
| Chinese social encoder | Local Chinese MLM checkpoint and DAPT with replay, resumable state, and immutable encoder versions. | DAPT exports a portable encoder/tokenizer and frozen `encoder_state.pt`; the registry binds version, artifact hash, corpus, and training run. The current provenance-bound corpus contains 17,520 documents and 415,686 WordPiece tokens, so no 500,000-token DAPT claim is made. |
| Account detector | BotRHG training/inference, strict feature allowlist, account representation, calibration payload, and BADGE gradient embedding. | Deployable detectors must bind an immutable encoder version and hash. Existing transfer/checkpoint paths run; a fully retrained Chinese detector bundle has not yet been produced. |
| Acquisition | ALPS + Core-set in cold start; calibrated uncertainty + BADGE in warm start. | Implemented fail-closed selector; no completed real annotation round. |
| Evaluation | Frozen holdout plus account/event/community/time/platform audits. | A durable system-owned evaluation job locks the candidate and holdout identity, rejects training/holdout overlap, runs inference without a database lock, rechecks fingerprints, and writes an HMAC-signed immutable result. No signed real-data report has completed yet. |
| Artifact delivery | `cogguard.account-model-bundle.v1`, file hashes, feature schema, calibration, and metrics. | Canonical verification is shared by registration and runtime. Activation rejects non-deployable bundles; runtime loads the verified encoder, feature schema, and calibration and checks them against the detector checkpoint. No completed production bundle is active. |
| Operations | Celery `account_training` and `account_evaluation`, transactional dispatch outbox, persisted training/evaluation records, Active Pointer, monitoring, and rollback policy. | Migration round trip, Redis/Celery registration, duplicate-delivery gating, pointer-invalid rejection, and bounded automatic rollback are implemented and tested. A real candidate shadow run, activation, and rollback exercise remain pending. |

## Explicit Non-Claims

- A deterministic compatibility detector or a legacy checkpoint is not the
  complete NLPCC training implementation.
- Public Twitter benchmark transfer does not demonstrate Chinese Weibo
  generalization.
- A unit-tested DAPT or bundle function does not prove GPU throughput, model
  quality, calibration, or deployment safety.
- The existing account-profile layout is intentionally preserved. Its current
  projection now exposes only governed detector conclusions: bot probability,
  prediction, model version, routing path, and support-hypergraph neighbor
  summaries. Training and governance controls remain backend control-plane
  work.

## Acceptance Sequence

1. Apply and round-trip the account-training Alembic migration on the target
   MySQL instance.
2. Build a provenance-bound Chinese corpus from collected posts/comments and
   reserve a frozen holdout before DAPT or label acquisition consumes it.
3. Run and resume a 500,000-token DAPT job on the target GPU; retain checkpoint
   and corpus manifests.
4. Train a detector from approved `human`/`bot` labels only, bind it to the
   encoder version, and produce a verified bundle.
5. Compute real leakage, calibration, risk-coverage, quality, latency, and
   false-positive-load gates.
6. Shadow the candidate, collect auditable monitoring, obtain approvals, then
   activate atomically through the database Active Pointer.
7. Exercise tamper rejection, worker interruption recovery, and rollback to a
   previously approved bundle.

The detailed research rationale and citation status are maintained in
`doc/research/account-detection-active-learning.md` and
`doc/research/account-detection-reference-map.md`.

## Training Operations

`system/start-system.ps1` stops stale workers consuming either account-model
queue, then starts one hidden Celery process using `--queues
account_training,account_evaluation --concurrency 1 --pool solo`. Training and
candidate evaluation also acquire the same process-bound GPU fence under
`MODEL_ARTIFACT_ROOT`, so a separately started local worker cannot bypass the
single-node resource boundary; inspect
`system/logs/account-training-worker-*.out.log` and `.err.log` when a run is
deferred or interrupted. The runtime reads these deployment policy values from
`system/.env` (or `system/backend/.env`):

| Variable | Default | Meaning |
| --- | ---: | --- |
| `ACCOUNT_TRAINING_DAPT_TOKEN_THRESHOLD` | 500000 | New eligible Chinese tokens required for automatic DAPT. |
| `ACCOUNT_TRAINING_SUPERVISED_LABEL_THRESHOLD` | 200 | Approved binary labels required for automatic detector retraining. |
| `ACCOUNT_TRAINING_COOLDOWN_DAYS` | 7 | Minimum interval between dispatches of the same training family. |
| `ACCOUNT_TRAINING_HEARTBEAT_TIMEOUT_SECONDS` | 300 | Lease timeout before an active run is marked interrupted. |
| `ACCOUNT_TRAINING_MAX_RESUMES` | 3 | Maximum explicit recoveries after the initial execution. |

Manual dispatch can bypass only a quantity threshold. Corpus readiness,
cooldown, persisted configuration, heartbeat recovery, and the recovery limit
remain enforced.

Celery Beat reconciles training heartbeats, records five-minute active-model
monitor snapshots, and drains the evaluation dispatch outbox every minute. The
outbox claims only committed `pending` intents or expired `publishing` leases,
publishes outside the database transaction, and token-finalizes the claim. A
broker failure returns the intent to `pending`; a successful publish is not
periodically replayed because a database timer cannot distinguish a task waiting
in the Celery queue from a lost broker message. `dispatch_acknowledged_at` is
retained as execution telemetry, not as a re-publish trigger. Reclaimed claims
reuse the persisted task ID, while job and GPU ownership make at-least-once
delivery safe.

## Measured Deployment Evidence

- The previous MySQL migration round trip completed through
  `c4f7a9d2e618`. The new `e5c1b7d9a204` platform-scope migration is present
  in the worktree, and the full offline upgrade script now generates through
  that head. Online upgrade and downgrade round-trip still require a
  responsive MySQL service.
- The offline migration pass also fixed two legacy migration checks that used
  database inspection or result fetching during SQL rendering; online
  duplicate-data protection remains enabled.
- The dedicated `account_training` worker received the stable task ID
  `account-training:account-training-a864b99c98f74b14:attempt:1`; the induced
  missing-corpus failure was persisted instead of starting an uncontrolled
  training run.
- A real Celery worker smoke registered `account_training.execute`,
  `account_training.monitor_active_model`, `account_evaluation.execute`, and
  `account_evaluation.reconcile_dispatches` while listening to both
  account-model queues.
- Automatic rollback is deliberately narrow: immediate rollback is limited to
  bundle corruption or runtime load failure; other hard errors require two
  adjacent persisted monitor snapshots. The target must be the previously
  activated, approved, signed, hash-valid model recorded by the current pointer
  revision.
- The current local database contains a historical bootstrap pointer, but the
  strict runtime rejects its bundle as `active_model_bundle_invalid`. Account
  profiles therefore fail closed to `暂无研判`; no heuristic detector runs and
  no governed retrained model is active.
- The backend venv now contains `torch 2.11.0+cu128`; CUDA and torch-geometric
  import checks pass on the RTX 4060 Laptop GPU. A real local Chinese RoBERTa
  DAPT smoke completed two optimizer updates with BF16, exported a verified
  encoder artifact, and peaked at 1,972.8 MiB. Full-run VRAM, latency, and model
  quality acceptance remain blocked by the 500,000-token and approved-label
  data gates rather than by the runtime environment.
