# Chinese Account Detection Active Learning Loop

Updated: 2026-08-07

## Scope And Claim Boundary

CogGuard's Chinese account detection is an analyst-governed learning loop for
collected Chinese social-media accounts. It is not an automatic identity,
nationality, intent, or attribution system, and it does not turn model output
into a gold label.

The current supervised target is binary account automation detection:

- `human` is exported as `non_bot` for supervised training.
- `bot` is exported as `bot` for supervised training.
- `insufficient_evidence` is a review abstention outcome. It is excluded from
  the binary training loss and routed to additional evidence collection.

Coordination, spam, template reuse, OOD, temporal bursts, and disagreement are
evidence or acquisition signals. They are not extra target labels.

## Implemented Contract

The repository now contains the following capability boundaries. Their
existence does not mean that a production model has passed deployment
acceptance.

| Stage | Implemented boundary | Current status |
| --- | --- | --- |
| Case and labels | Account case fingerprints, label batches, evidence-bound labels, approval records, corpus-version records, and frozen-holdout records. | The append-only `supersedes_id` revision chain, corpus-scope filtering, platform-scoped holdout membership, and holdout exclusion are implemented. The current deployment database contains no approved binary account labels. |
| Cold-start acquisition | Local Chinese MLM ALPS surprisal vectors followed by Core-set k-center selection. | Implemented and fail-closed. A missing `ACCOUNT_ACQUISITION_TEXT_MODEL_PATH` prevents batch creation. |
| Warm-start acquisition | Calibrated uncertainty with BotRHG classifier-gradient BADGE embeddings. | Implemented and fail-closed. Uncalibrated probability or missing BADGE payload prevents batch creation. |
| DAPT | Chinese-text filtering, exact deduplication, 20% historical replay, local-only MLM training, resumable checkpoints, and resolved precision provenance. | Connected to a registered three-platform Mongo corpus version containing 17,520 documents and 415,686 locally tokenized WordPieces. CUDA BF16 smoke and immutable encoder export pass; no 500,000-token full DAPT run has completed. |
| Detector evaluation | Account/event/community-disjoint, time-forward, platform-stratified, and frozen-holdout protocol reports. | Implemented as a record-derived gate. No signed real-data report is available yet. |
| Model artifact | `cogguard.account-model-bundle.v1` with encoder, detector, feature schema, calibration, metrics, data fingerprints, and per-file SHA-256 checks. | Implemented and tested for local integrity checks. No accepted deployable bundle has been produced. |
| Training and activation | Persistent training-run records, Celery `account_training` and `account_evaluation` entry points, candidate registration, Active Pointer lookup, and audited rollback boundary. | Schema migration, dispatch recovery, worker-loss handling, and rollback policy are implemented. The only local pointer targets an invalid historical bootstrap bundle; real shadow execution, governed activation, and rollback rehearsal remain open. |
| Monitoring | Latency, calibration, coverage, abstention, false-positive load, PSI drift, and hard-error calculations. | Immutable snapshot persistence, read API, scheduled monitoring, and bounded automatic rollback are implemented. They have not been exercised against a governed active model. |

## Closed Loop

1. **Account Detection Case** records collected posts, provenance, evidence
   identifiers, and a stable case fingerprint.
2. **Account Label Batch** selects unlabeled cases under a fixed budget. Cold
   start uses ALPS plus Core-set; warm start uses calibrated uncertainty plus
   BADGE. Neither path silently substitutes weighted scores or hashed text
   vectors.
3. **Account Detection Label** records an analyst decision, the fingerprint
   observed by the analyst, evidence identifiers, confidence, and reason tags.
4. **Approved Account Corpus** exports only eligible approved/adjudicated
   `human` and `bot` records with a dataset manifest and data fingerprint.
5. **Chinese Social Encoder** performs domain-adaptive masked-language-model
   training (DAPT) on a versioned Chinese corpus. The default design is 15%
   masking, sequence length 128, micro-batch 2, accumulation 32, mixed
   precision, gradient checkpointing, and 20% historical replay.
6. **Shadow Account Model** trains a BotRHG detector bound to one encoder
   version and an explicit feature allowlist. `source_label` and other label
   proxies are excluded from the strict feature path.
7. **Evaluation And Bundle** computes the leakage-safe split report, writes a
   verified model bundle, and records calibration and deployment eligibility.
   The evaluator HMAC manifest binds the candidate version, artifact hash,
   evaluation run ID, protocol fingerprint, and raw audit fingerprint;
   candidate-provided ECE or calibration fields are not operational evidence.
8. **Activation Or Rollback** must reverify the artifact, persisted evaluator
   manifest HMAC, audit/identity fingerprints, current gates, and relevant
   approvals under a row lock before atomically moving the MySQL Active Pointer.
   Rollback can restore only a previously governed active or retired model with
   persisted activation history, never an arbitrary approved candidate.

## Method Rationale

| Decision | Evidence | System consequence |
| --- | --- | --- |
| Human/bot with explicit abstention | Ferrara et al. 2016; Varol et al. 2017; Geifman and El-Yaniv 2017. | Labels remain minimal and `insufficient_evidence` stays outside binary loss. |
| DAPT before Chinese detector retraining | Cui et al. 2021; Gururangan et al. 2020. | A detector candidate declares and binds its encoder version; generic multilingual checkpoints are not the default Chinese claim. |
| Cold-start ALPS plus Core-set | Yuan et al. 2020; Sener and Savarese 2018. | No classifier uncertainty is used before a trustworthy calibrated ranker exists. |
| Warm-start calibrated uncertainty plus BADGE | Guo et al. 2017; Ash et al. 2020. | The product accepts only recorded calibration provenance and classifier-gradient embeddings. |
| Equal-budget active-learning evaluation | Ein-Dor et al. 2020; Lowell et al. 2019; Karamcheti et al. 2024. | Random, uncertainty, Core-set, ALPS/Core-set, and BADGE require the same label budget. |
| Leakage-safe graph/account evaluation | OGB; TGB; Shchur et al. 2018; Kapoor and Narayanan 2023. | Account, event, community, temporal, platform, and frozen-holdout checks are computed from records, not trusted caller flags. |
| Analyst-governed deployment | Artstein and Poesio 2008; Mitchell et al. 2019; Breck et al. 2017. | Artifact hashes, audit records, approvals, and rollback are prerequisites rather than UI options. |

See [account-detection-reference-map.md](account-detection-reference-map.md)
for publication status and verified locators. `BotRHG` is an internal NLPCC
submission method in this repository, not a peer-reviewed citation.

## Deployment Acceptance Is Still Blocked

The system must not claim a complete deployable Chinese bot-detection loop
until all of the following evidence exists:

- Alembic upgrade/downgrade/upgrade succeeds against the target MySQL
  deployment, including the account-training governance migration.
- A real 500,000-token Chinese DAPT run completes and resumes correctly after
  interruption; new-domain MLM loss improves by at least 2% while historical
  anchor loss worsens by no more than 1%.
- A supervised BotRHG retraining run produces a verified bundle and real
  frozen-holdout, time-forward, platform-stratified, and community-disjoint
  reports.
- Candidate macro-F1 and AUPRC confidence-interval lower bounds are not more
  than one percentage point below the active model; no platform loses more
  than two points; ECE is at most 0.05; and projected false-positive load is
  within the configured analyst capacity.
- Shadow inference, two-person production approval, atomic activation, worker
  interruption recovery, artifact tampering rejection, and rollback are
  exercised against MySQL, MongoDB, Redis, Celery, and the target GPU.

Until then, existing Weibo and public-benchmark checkpoints remain transfer
artifacts. They are not evidence of Chinese cross-platform superiority or a
production-ready retraining loop.

## Verification Scope

Research-unit coverage currently includes DAPT, evaluation protocol, model
bundle, strict feature, and acquisition contracts. Full backend, live service,
database migration, Celery, GPU, and browser acceptance are separate gates and
have not been claimed by this document.
