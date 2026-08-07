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
| Chinese social encoder | Local Chinese MLM checkpoint and DAPT with replay and resumable state. | A provenance-bound corpus contains 17,520 documents and 415,686 WordPiece tokens; it is 84,314 tokens below the first DAPT gate, so no DAPT claim is made. |
| Account detector | BotRHG training/inference, strict feature allowlist, account representation, calibration payload, and BADGE gradient embedding. | Existing transfer/checkpoint paths run; full Chinese retraining bundle not yet produced. |
| Acquisition | ALPS + Core-set in cold start; calibrated uncertainty + BADGE in warm start. | Implemented fail-closed selector; no completed real annotation round. |
| Evaluation | Frozen holdout plus account/event/community/time/platform audits. | Protocol code implemented; no signed real-data report. |
| Artifact delivery | `cogguard.account-model-bundle.v1`, file hashes, feature schema, calibration, and metrics. | Canonical verification is shared by registration and runtime. Activation rejects non-deployable bundles; runtime loads the verified encoder, feature schema, and calibration and checks them against the detector checkpoint. No completed production bundle is active. |
| Operations | Celery `account_training`, transactional dispatch outbox, persisted training-run records, candidate/approval/activation/rollback policy. | MySQL migration round trip, Redis/Celery receipt, stable task identity, duplicate-delivery gating, and no-pointer fail-closed smoke are complete. Real shadow evaluation, activation, and rollback remain pending. |

## Explicit Non-Claims

- A deterministic compatibility detector or a legacy checkpoint is not the
  complete NLPCC training implementation.
- Public Twitter benchmark transfer does not demonstrate Chinese Weibo
  generalization.
- A unit-tested DAPT or bundle function does not prove GPU throughput, model
  quality, calibration, or deployment safety.
- The account-profile page remains unchanged in this delivery phase. Governance
  and training controls are backend control-plane work.

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

`system/start-system.ps1` starts `account_training` in a separate hidden
Celery process using `--concurrency 1 --pool solo`; inspect
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

## Measured Deployment Evidence

- MySQL migration `c3a7e5d8f914 -> b3e5d8a7c421 -> c3a7e5d8f914`
  completed; both outbox timestamps are `NOT NULL` at head.
- The dedicated `account_training` worker received the stable task ID
  `account-training:account-training-a864b99c98f74b14:attempt:1`; the induced
  missing-corpus failure was persisted instead of starting an uncontrolled
  training run.
- The current Active Pointer is empty. A real Trump/Weibo request returned
  `unavailable_without_active_pointer` and `no_active_account_model_pointer`;
  no legacy or heuristic detector ran.
- The host exposes an RTX 4060 Laptop GPU with 8,188 MiB, but the backend venv
  currently contains `torch 2.12.1+cpu`. CUDA DAPT, VRAM, and latency acceptance
  remain blocked until a CUDA-enabled training environment is installed.
