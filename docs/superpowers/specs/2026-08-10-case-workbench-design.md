# Case Workbench Design

Status: implementation-ready design
Date: 2026-08-10
Scope: persistent case investigation, governed semantic enrichment, and frozen reporting

## 1. Decision Summary

CogGuard will introduce **Case** as the durable investigative aggregate above immutable **Event Snapshots** and versioned **Analysis Runs**. A Case keeps authoritative claims, approved decisions, actions, feedback, frozen reports, semantic artifacts and corrections, and append-only audit history without replacing the existing specialist analysis pages or changing their scoring ownership.

The case lifecycle narrative is:

```text
事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈
```

The design is governed by these invariants:

1. Evidence and decisions are versioned or appended; prior records are never overwritten.
2. Case lifecycle and executable analysis lifecycle remain separate.
3. A Case Blocker is data attached to a Case, never an invented Case State.
4. Authoritative Case Claims are verbatim and source-spanned; generated language cannot substitute for them.
5. Semantic enrichment is opt-in, provenance-bound, and score-isolated from Coordination Discover, Propagation Analysis, and Risk Review.
6. A closed Case has a frozen decision and action record, not merely a completed analysis run.
7. Dataset identities and evidence windows cannot be blended to make a demonstration appear more complete.

## 2. Goals And Non-Goals

### 2.1 Goals

- Give analysts one long-lived investigation record spanning collection, analysis, review, action, feedback, and reporting.
- Preserve exact evidence provenance from source capture through claim approval and report rendering.
- Make lifecycle state, the approved Primary Claim, and active blockers immediately visible throughout the workbench.
- Reuse current Event Snapshot, Analysis Run, Coordination Discover, Propagation Analysis, Student Review, Teacher Review, feedback, and Canonical Verdict boundaries.
- Add semantic enrichment for sentiment, stance, topics, keywords, entities, near duplicates, and community comparison without changing existing risk or graph scores.
- Support incremental reruns when a Primary Claim or model version changes instead of recomputing unrelated stages.
- Produce frozen, reproducible report versions suitable for browser viewing and print-friendly PDF output.
- Provide explicit audit, permission, idempotency, failure, and partial-data contracts for later implementation.

### 2.2 Non-Goals

- Replacing specialist Coordination, Propagation, account, or Risk Review pages.
- Treating a Case as a mutable copy of an Event Snapshot or as an Analysis Run wrapper.
- Automatically approving a claim, Canonical Verdict, Case Action waiver, or closure decision.
- Allowing semantic results to alter Coordination Discover, Propagation Analysis, or Risk Review scores.
- Declaring candidate semantic models valid before local evaluation.
- Fabricating a missing Douyin or XHS source, mixing an unrelated event, or importing Twitter benchmark content into the demonstration Case.
- Replacing a source excerpt with a topic label, generated summary, or analyst paraphrase.
- Building a general records-management, legal-hold, or external case-sharing product in the first release.
- Claiming feature or quality superiority over the products and research tools compared in this document.

## 3. Personas And Workflows

### 3.1 Personas

| Persona | Responsibilities | First-release boundary |
| --- | --- | --- |
| Analyst | Creates Cases, binds snapshots, reviews collection quality, proposes claims, runs analysis, records corrections, and drafts actions. | One analyst may perform all responsibilities, but each action remains separately attributed. |
| Approver | Approves the Primary Claim, Canonical Verdict, and action waivers; submits the Closeout Review rationale. | May be the same authenticated analyst; self-approval and closeout submission are visible in Audit Events. |
| Source administrator | Maintains Authority Sources and Source Tiers. | Requires administrative permission; URL discovery alone does not grant authority status. |
| Viewer | Reads Cases, evidence, analysis, actions, and frozen reports. | Cannot mutate case data or generate a new authoritative version. |
| System operator | Manages model candidates, execution health, retention, and failed jobs. | Cannot silently convert model output into an analyst decision. |

### 3.2 Core Workflow

1. The analyst creates a draft Case with an event scope, core window, context window, and explicit platform expectations.
2. Collection produces immutable Event Snapshots; the analyst binds one or more snapshot versions to the Case.
3. Collection quality is reviewed. Known incompleteness requires a Partial Collection Acknowledgement, and missing expected platforms remain visible as Platform Gap blockers.
4. Authority Source candidates are matched to the registry. Non-registry URLs stay pending review.
5. The analyst records Case Claims from verbatim excerpts and exact source spans, then approves exactly one as the Primary Claim.
6. The Case orchestrator requests relevant Analysis Runs. Discover, propagation, and non-stance semantic analysis may run before Primary Claim approval.
7. Primary Claim approval incrementally triggers stance and Risk Review while reusing compatible prior artifacts.
8. The analyst compares evidence, semantic artifacts, Review Verdicts, and provenance, then approves one immutable Canonical Verdict.
9. Required Case Actions are completed or explicitly waived with reasons.
10. A Closeout Review verifies closure gates, after which the Case becomes `closed` and a final frozen Case Report Version can be issued.
11. Feedback, corrections, and follow-up evidence remain append-only. Material follow-up after closure creates a linked Case rather than reopening history in place.

## 4. Domain Model And Cardinalities

### 4.1 Aggregate Boundary

**Case** is the aggregate root for investigative consistency. Large immutable snapshot payloads and analysis artifacts remain in their owning stores; the Case holds stable identifiers, hashes, approval records, and version links rather than copying mutable payloads.

| Record | Cardinality from Case | Mutability and ownership |
| --- | --- | --- |
| Event Snapshot reference | `1..n` | Immutable snapshot owned by the existing analysis boundary; binding is append-only. |
| Analysis Run reference | `0..n` | Versioned execution owned by the existing analysis boundary. |
| Authority Source | `0..n` through claims | Administered registry record, versioned when tier or account metadata changes. |
| Case Claim | `0..n` | Immutable excerpt and provenance; approval or retirement is a separate record. |
| Approved Primary Claim | `0..1` before approval, exactly `1` before stance completion | One active approved version; Risk Review may run without it, while approval/replacement triggers incremental stance plus Risk Review. |
| Supplementary Claim | `0..n` | Contextual claim versions that cannot implicitly replace the Primary Claim. |
| Review Verdict | `0..n` | Advisory Student or Teacher output associated with one run. |
| Canonical Verdict | `0..n` versions, exactly `1` active approved version before closure | Human-approved and immutable; supersession points to the prior version. |
| Case Action | `0..n` | Append-only status transitions; required actions must finish or be waived before closure. |
| Feedback | `0..n` | Existing run/verdict feedback plus case-level attribution; never rewrites its target. |
| Semantic Artifact | `0..n` | Immutable result of `semantic_enrichment`, keyed by snapshot, run, model, scope, and hashes. |
| Semantic Correction | `0..n` per artifact | Human overlay preserving original artifact and correction history. |
| Case Report Version | `0..n` | Frozen rendered version with immutable inputs and hashes. |
| Case Blocker | `0..n` active or resolved | Separately resolved condition; not a lifecycle value. |
| Partial Collection Acknowledgement | `0..n` | Signed acknowledgement bound to collection scope and snapshot set. |
| Closeout Review | `0..n`, exactly `1` submitted for closure | Human rationale record referencing the closing state of verdicts, actions, blockers, and reports; submission is the gate and no separate acceptance status exists. |
| Audit Event | `1..n` | Append-only mutation ledger owned by the Case boundary. |

### 4.2 Required Identifiers And Version Links

Every Case-owned record has a stable identifier, `case_id`, creation actor and time, and an immutable payload hash. Versioned records additionally carry `version`, `supersedes_id`, and the reason for replacement. External analysis references include `snapshot_id`, `snapshot_content_hash`, `run_id`, stage name, model version, artifact hash, and claimability status as applicable.

Case timestamps are stored as timezone-aware instants. User-facing demonstration windows are interpreted in Beijing time and rendered with the timezone explicitly shown.

## 5. Lifecycle, Transitions, And Blockers

### 5.1 Case States

The complete Case State set is exactly:

```text
draft
collecting
evidence_ready
analyzing
awaiting_review
actioning
ready_to_close
closed
```

No failure, pause, or blocker value may be added to this set.

### 5.2 Transition Contract

| From | To | Minimum gate | Audit requirement |
| --- | --- | --- | --- |
| `draft` | `collecting` | Event scope and collection intent recorded. | Actor, scope hash, request identity. |
| `collecting` | `evidence_ready` | At least one immutable Event Snapshot bound; collection gaps either resolved or acknowledged according to policy. | Snapshot IDs/hashes and acknowledgement references. |
| `evidence_ready` | `analyzing` | An Analysis Run is requested for a bound snapshot. | Run ID, requested stages, options hash. |
| `analyzing` | `awaiting_review` | Requested runnable stages reach terminal outcomes; any abstentions or blocks are persisted. | Run and Artifact Manifest references. |
| `awaiting_review` | `analyzing` | A new snapshot, approved Primary Claim, or permitted rerun request requires incremental analysis. | Rerun reason and reused/invalidated artifacts. |
| `awaiting_review` | `actioning` | An approved Canonical Verdict exists and required Case Actions are declared. | Verdict and action-set version. |
| `actioning` | `ready_to_close` | Every required Case Action is completed or explicitly waived. | Completion/waiver record IDs. |
| `ready_to_close` | `actioning` | A closure gate regresses because an action or decision is superseded before closure. | Regression reason and affected records. |
| `ready_to_close` | `closed` | Approved Canonical Verdict, all actions completed/waived, and submitted Closeout Review. | Closeout Review ID and final aggregate hash. |

`closed` is terminal in the first release. Material new evidence creates a linked follow-up Case so the original closeout remains reproducible.

### 5.3 Case Blockers

A blocker is an append-only `CaseBlockerRecord` with stable `blocker_id`, `case_id`, `identity_key`, `code`, `scope`, `operation`, `severity`, evidence references, creation actor/time, and payload hash. Each resolution is a separate append-only `CaseBlockerResolutionRecord` with `resolution_id`, `blocker_id`, `resolution_code`, reason, evidence references, actor/time, and payload hash. The original blocker is never updated or deleted. The UI and API project `active` and derive `is_blocked_for(operation)` from the latest blocker plus resolution history; they do not derive a synthetic state.

Minimum blocker cases include:

| Condition | Blocked operation | Required behavior |
| --- | --- | --- |
| Missing approved Primary Claim | Stance only | Stance returns exactly `blocked_missing_primary_claim`; Risk Review and every other permitted stage may complete with the missing-stance limitation recorded. |
| Non-registry authority URL | Claim approval | Keep the source and claim pending until source administration resolves it. |
| Platform Gap | Collection completeness or a policy-selected closure gate | Display the absent platform and archive search evidence; never substitute unrelated content. |
| Unacknowledged partial collection | Transition to `evidence_ready` | Require more collection or a Partial Collection Acknowledgement. |
| Snapshot/hash mismatch | Artifact reuse and report freezing | Fail closed and require reconstruction from verified inputs. |
| Missing approved Canonical Verdict | Transition to `actioning` or `closed` | Keep review/action gates visible. |
| Incomplete required action | Transition to `ready_to_close` or `closed` | Complete or explicitly waive the action. |
| Missing Closeout Review | Transition to `closed` | Require a submitted review record; do not introduce an approval or acceptance decision. |

Blocker resolution appends a resolution record. It never deletes the blocker or its original evidence.

## 6. Authority Sources And Claim Trust

### 6.1 Source Registry

Authority Sources are administered records rather than dynamically trusted URLs. Each registry version contains publisher identity, canonical accounts/domains, applicable platform, Source Tier, effective dates, evidence for classification, administrator, and version hash.

The three Source Tiers and their persisted identifiers are:

1. Government or official institutions: `government_official`.
2. Central mainstream media originals: `central_mainstream_original`.
3. Provincial official media: `provincial_official_media`.

Tier indicates the governed source category, not the truth of every statement and not a numeric confidence score. Redirects, mirrors, screenshots, aggregators, and reposts do not inherit a tier automatically. A URL or account absent from the registry remains pending review even when its appearance seems familiar.

### 6.2 Case Claim Contract

A Case Claim must store:

- the verbatim excerpt;
- the exact source span, using stable offsets or a source-native locator plus captured text;
- the canonical URL and resolved URL where applicable;
- the publishing account;
- publication time with timezone and capture time;
- Authority Source registry version and Source Tier;
- source content hash and captured-content reference;
- claimant, creation time, role proposal, and approval history.

Hash verification is required before approval and report freezing. If live content changes or disappears, the captured version remains addressable and the live mismatch is recorded rather than silently replacing the excerpt.

### 6.3 Primary And Supplementary Claims

A Case may contain many claim candidates and multiple Supplementary Claims. It may have at most one active approved Primary Claim, and it must have exactly one before stance can complete. Risk Review may complete before that approval with the missing-stance limitation explicit. Approving or replacing the Primary Claim creates a new approval version, supersedes the prior active link, and triggers incremental stance plus Risk Review so the later review can consume the stance result; it does not rewrite earlier results.

Topics, keywords, model-generated summaries, analyst paraphrases, and inferred narratives are not Case Claims. They may link to claims as aids, but cannot satisfy a Primary Claim gate.

## 7. Semantic Enrichment

### 7.1 Stage Boundary

Semantic enrichment is an explicit `semantic_enrichment` Analysis Stage. Existing callers that omit `requested_stages` retain the default four-stage run:

```text
coordination_discover
propagation_analysis
student
teacher
```

Case orchestration requests `semantic_enrichment` explicitly and may target sentiment, stance, topics, keywords, entities, near duplicates, and community comparison. Stance requires an approved Primary Claim; the remaining listed enrichment tasks may run without one.

Student Review and Teacher Review remain advisory. Semantic outputs do not become Review Verdicts, Canonical Verdicts, Case Claims, or action decisions.

### 7.2 Pinned Candidate Models

| Purpose | Pinned model | Status |
| --- | --- | --- |
| Shared embeddings | `BAAI/bge-small-zh-v1.5@7999e1d` | `candidate_unvalidated` |
| Sentiment | `lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110` | `candidate_unvalidated` |
| Stance | `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92` | `candidate_unvalidated` |
| Named entities | `shibing624/bert4ner-base-chinese@5d660ed` | `candidate_unvalidated` |

All four remain `candidate_unvalidated` until local evaluation passes on declared datasets and metrics. Pinning identifies bytes and configuration; it is not validation, activation, calibration, or a quality claim.

### 7.3 Shared Embedding Pass

For each immutable snapshot and preprocessing configuration, the stage performs one shared embedding pass. The resulting embedding artifact is reused for:

- keyword ranking with maximal marginal relevance;
- topic clustering plus c-TF-IDF labeling;
- near-duplicate grouping;
- Coordination Community comparison.

Main posts and comments are embedded, analyzed, evaluated, and summarized as separate scopes. Aggregates must expose the scope and denominators; comment volume cannot silently dominate main-post results. Auxiliary evidence may be cross-analyzed by time, platform, Coordination Community, and Propagation Tree or path, always preserving references back to source content.

### 7.4 Provenance And Degradation

Every Semantic Artifact records:

- `artifact_id`, type, schema version, `case_id`, `snapshot_id`, and `run_id`;
- content scope (`main_posts` or `comments`) and included content IDs;
- model repository, pinned revision, local artifact digest, tokenizer/config digest, and runtime version;
- preprocessing policy, language handling, thresholds, random seed, and options hash;
- input snapshot/content hashes, shared-embedding artifact reference, output hash, and creation time;
- status, coverage counts, excluded counts, degradation reasons, and validation status.

Degradation is explicit and machine-readable. Examples include unavailable model bytes, digest mismatch, unsupported language, truncated content, insufficient cluster size, missing Primary Claim for stance, partial comments, or low entity coverage. A degraded artifact remains inspectable but cannot be relabeled as complete or validated.

### 7.5 Semantic Corrections

A Semantic Correction references the original artifact, affected content IDs or cluster, corrected value, reason, actor, timestamp, and optional supporting Case Claim. Corrections are overlay records used in the workbench and reports. They never mutate embeddings or original model output, never change Coordination Discover, Propagation Analysis, or Risk Review scores, and never train or activate a model without a separate governed workflow.

## 8. Orchestration And Incremental Reruns

### 8.1 Execution Rules

The Case orchestrator composes existing Analysis Runs; it does not introduce a second executor. Each run still targets one immutable Event Snapshot and an ordered requested-stage list. The orchestrator records which outputs are reused, rerun, blocked, abstained, degraded, or superseded.

Permitted work before Primary Claim approval:

- Coordination Discover;
- Propagation Analysis;
- sentiment;
- topics;
- keywords;
- entities;
- near-duplicate analysis.

Stance returns `blocked_missing_primary_claim`. Risk Review may complete without stance when that limitation is explicit, and Primary Claim approval later triggers incremental stance plus Risk Review. The Case remains in its actual Case State with an active stance-scoped blocker record.

### 8.2 Invalidation Matrix

| Change | Reuse | Rerun or action |
| --- | --- | --- |
| Primary Claim approved or replaced, snapshot unchanged | Coordination, propagation, non-stance semantic artifacts | Run stance incrementally, then Student Review and Teacher Review/Risk Review; preserve prior blocked/advisory records. |
| Supplementary Claim added | All score artifacts by default | Refresh claim-linked presentation; rerun only a stage explicitly configured to consume supplementary claims. |
| New collection content | Nothing whose input hash changes | Build a new Event Snapshot and new Analysis Run; never mutate the old snapshot. |
| Semantic model revision or preprocessing change | Coordination, propagation, Risk Review scores | Rerun affected semantic artifact types and shared embeddings when their dependency hash changes. |
| Semantic Correction added | All original artifacts | Apply correction overlay to UI/report; no automatic score rerun. |
| Case Action or waiver changed | All analysis artifacts | Recompute closure gates only. |
| Canonical Verdict approved or superseded | Evidence and analysis artifacts | Refresh action/closeout eligibility and report inputs; do not back-propagate into model scores. |
| Authority Source tier version changes | Unrelated claims and analysis | Mark affected claims stale for approval review; preserve the historical registry version used by frozen reports. |

Artifact reuse requires matching snapshot hash, content scope, stage options, model/config dependency hashes, and applicable claim version. A reuse decision is itself audited.

### 8.3 Concurrency

Case mutations use optimistic version checks. Analysis completion may arrive out of order, but an artifact is attached only when its requested snapshot and dependency hashes still match. A late result remains recorded and may be viewed, but cannot silently replace the active artifact set.

## 9. API Surface Summary

The proposed API is additive under `/api/v2`; existing `/api/v2/analysis/*` routes remain valid.

| Method and path | Purpose |
| --- | --- |
| `POST /api/v2/cases` | Create a draft Case with event scope and platform expectations. |
| `GET /api/v2/cases` | Filter and paginate Cases by state, owner, blocker, time, and event ID. |
| `GET /api/v2/cases/{case_id}` | Return the aggregate summary, active versions, lifecycle, and blocker projection. |
| `PATCH /api/v2/cases/{case_id}` | Update mutable draft metadata using an expected aggregate version. |
| `GET /api/v2/cases/{case_id}/blockers` | List stable blocker identities with scope, severity, evidence, active status, and append-only resolution history. |
| `POST /api/v2/cases/{case_id}/blockers/{blocker_id}/resolutions` | Append a governed blocker resolution without changing or deleting the blocker. |
| `POST /api/v2/cases/{case_id}/transitions` | Request a governed Case State transition and return unmet gates. |
| `POST /api/v2/cases/{case_id}/snapshots` | Bind an existing immutable Event Snapshot by ID and hash. |
| `POST /api/v2/cases/{case_id}/analysis-runs` | Create a Case-orchestrated Analysis Run with explicit stages and reuse policy. |
| `GET /api/v2/cases/{case_id}/matrix` | Return paginated evidence, claim, artifact, community, and propagation cross-links. |
| `POST /api/v2/cases/{case_id}/claims` | Record a verbatim Case Claim candidate. |
| `GET /api/v2/cases/{case_id}/claims` | List immutable claim versions and current role/decision projections. |
| `POST /api/v2/cases/{case_id}/claims/{claim_id}/approve-primary` | Approve or supersede the single active Primary Claim. |
| `POST /api/v2/cases/{case_id}/claims/{claim_id}/approve-supplementary` | Approve a Supplementary Claim. |
| `POST /api/v2/cases/{case_id}/semantic-corrections` | Append a correction to a Semantic Artifact. |
| `GET /api/v2/cases/{case_id}/semantic-corrections` | List correction overlays with artifact/version ownership and provenance. |
| `POST /api/v2/cases/{case_id}/actions` | Create a required Case Action. |
| `GET /api/v2/cases/{case_id}/actions` | List latest action versions plus immutable transition history. |
| `POST /api/v2/cases/{case_id}/actions/{action_id}/transitions` | Complete or explicitly waive an action. |
| `POST /api/v2/cases/{case_id}/collection-acknowledgements` | Record a Partial Collection Acknowledgement. |
| `POST /api/v2/cases/{case_id}/feedback` | Append Case-, run-, or verdict-scoped analyst feedback. |
| `POST /api/v2/cases/{case_id}/closeout-reviews` | Evaluate and record closure gates. |
| `POST /api/v2/cases/{case_id}/close` | Close a Case after all three closure gates pass. |
| `POST /api/v2/cases/{case_id}/reports` | Freeze a new Case Report Version from exact active inputs. |
| `GET /api/v2/cases/{case_id}/reports` | List successfully frozen report records and their provenance manifests. |
| `GET /api/v2/cases/{case_id}/reports/{version}/html` | Retrieve immutable frozen HTML with its stored digest as the ETag. |
| `GET /api/v2/cases/{case_id}/reports/{version}/pdf` | Retrieve the print-friendly PDF rendered from that frozen HTML. |
| `GET /api/v2/cases/{case_id}/events` | Page append-only Case Audit Events strictly after `after_id`. |
| `GET /api/v2/cases/{case_id}/events/stream` | Stream Case Audit Events with `Last-Event-ID` recovery. |
| `GET /api/v2/authority-sources` | Filter and paginate latest Authority Source versions. |
| `POST /api/v2/authority-sources` | Create a pending Authority Source candidate. |
| `POST /api/v2/authority-sources/{source_id}/approve` | Append an approved registry version with tier and classification evidence. |
| `POST /api/v2/authority-sources/{source_id}/revoke` | Append a revoked registry version with a reason. |

Mutation endpoints require `Idempotency-Key`, actor identity, and expected aggregate version where state can conflict. A repeated key with the same actor, endpoint, and canonical request hash returns the original status and body. Reuse with a different request hash returns `409 idempotency_conflict`.

## 10. Dense Case Workbench UI

### 10.1 Navigation And Persistent Context

Case Workbench is a new route-level page parallel to the specialist pages, not a card nested inside one of them. Its approved tabs are exactly:

```text
概览 / 证据矩阵 / 图谱 / 处置 / 报告
```

A compact sticky case header remains visible across all tabs and shows Case ID/title, Case State, owner, active Primary Claim status and excerpt, active Case Blockers, snapshot/run freshness, and the permitted next transition. Blockers open a focused drawer with evidence and resolution history rather than changing the state label.

### 10.2 Tab Behavior

| Tab | Dense behavior |
| --- | --- |
| `概览` | Lifecycle timeline, scope/windows, collection coverage, Primary/Supplementary Claims, current verdict, recent runs, blockers, and action readiness in scan-friendly rows. |
| `证据矩阵` | Virtualized, filterable rows crossing main posts/comments with platform, time, claim span, source tier, semantic artifacts/corrections, community, tree/path, and hashes; columns can be pinned. |
| `图谱` | Unframed graph workspace switching Coordination Community and Propagation Tree/path views while preserving evidence type, cutoff, selection, and provenance details. |
| `处置` | Required actions, completion/waiver controls, ownership, deadlines, verdict references, feedback, and Closeout Review gates in a compact operational table. |
| `报告` | Frozen version list, input/hash manifest, HTML view, print-friendly PDF action, render status, and immutable version comparison. |

Rows link to specialist pages at the same snapshot/run and return to the prior workbench filters. Claims and corrections use side panels so the evidence matrix retains context. Destructive-looking actions are explicit commands with confirmation and reason capture; familiar icon buttons carry tooltips.

### 10.3 States And Responsiveness

- Loading skeletons reserve stable table, graph, and header dimensions.
- Empty states state the missing data category, not a claim that no manipulation exists.
- Partial, stale, degraded, abstained, pending-source, and blocked states use text plus icons, never color alone.
- On narrow screens, the persistent header wraps into compact rows, tabs scroll horizontally, table columns collapse behind a column selector, and no lifecycle, Primary Claim, or blocker indicator is hidden.
- Live Analysis Run updates may use the existing SSE recovery surface; reconnect resumes from the last event and does not reset workbench state.
- Permission-disabled controls remain discoverable with the policy reason; unavailable actions do not appear to have succeeded.

## 11. Frozen Reports

A Case Report Version is rendered from a manifest that freezes:

- Case ID, Case version, Case State, title, scope, and time windows;
- Event Snapshot IDs, source content hashes, and collection acknowledgements;
- Analysis Run IDs, requested stages, stage statuses, and Artifact Manifests;
- active Primary and Supplementary Claim versions with source spans and hashes;
- Review Verdict references and approved Canonical Verdict version;
- Case Actions and waivers as of freeze time;
- Semantic Artifact and Semantic Correction versions;
- model repositories, pinned revisions, validation statuses, runtime/config digests;
- active and resolved blockers plus Closeout Review where present;
- renderer version, template hash, generated-at time, actor, and report content hash.

The canonical stored render is versioned HTML with local, content-addressed assets. PDF is a print-friendly rendering of that frozen HTML, not a second independently assembled report. A report version number and `CaseReportVersionRecord` are allocated only after both renders and hashes succeed. A render failure removes temporary files, writes diagnostic operational/audit evidence, and creates no report-version row or published output. Retrying after renderer correction therefore attempts the next successful immutable version rather than preserving a failed version.

## 12. Permissions, Audit, And Idempotency

### 12.1 Permissions

| Operation | Viewer | Analyst | Admin/source administrator |
| --- | --- | --- | --- |
| Read Cases and frozen reports | Yes | Yes | Yes |
| Create/update draft Case and run analysis | No | Yes | Yes |
| Propose claims/corrections/actions | No | Yes | Yes |
| Approve Primary Claim, Canonical Verdict, waivers; submit Closeout Review | No | Yes in first release | Yes |
| Administer Authority Sources and Source Tiers | No | No | Yes |
| Register/activate model candidates | No | No | Yes under existing model governance |

One analyst may perform every analyst/approver operation in the first release. The system still writes distinct Audit Events for proposal and approval and displays when the actors are the same. Future separation of duties can tighten policy without changing stored history.

### 12.2 Audit

Every mutation writes one append-only Audit Event in the same transaction as the authoritative record or through an atomic outbox. The event contains actor, roles, action, target type/ID/version, case aggregate version, timestamp, request/correlation/idempotency IDs, canonical request hash, before reference, after reference, and outcome. Sensitive payloads use references and hashes rather than duplicating source content into logs.

Deletion of an authoritative record is represented by a tombstone or retirement event where policy permits it. Audit Events, prior claims, verdicts, action states, corrections, and frozen reports are never updated in place.

### 12.3 Idempotency And Retry

- Create, transition, approval, action, correction, acknowledgement, closeout, and report-freeze commands are idempotent.
- Analysis reuse keys include Case, snapshot hash, ordered stages, options, applicable claim version, and model/config hashes.
- A worker retry cannot produce a second approval, action transition, report version, or Audit Event for the same accepted command.
- Optimistic version conflicts return the current aggregate version and no partial mutation.
- External rendering or execution uses an outbox/inbox receipt so retry is safe after a process crash.

## 13. Dataset Isolation And Demonstration Case

### 13.1 Demonstration Case

The demonstration Case uses:

- Case ID: `case_trump_visit_2026_05_21`;
- Event ID: `trump_visit_2026_05_21`;
- core window: 2026-05-14 through 2026-05-17, Beijing time;
- context window: 2026-05-08 through 2026-05-20, Beijing time;
- existing Weibo evidence: 74 unique posts, 57 authors, 5,048 comments, and 4,492 commenters;
- CCTV News Primary Claim candidate: `我们应当共同扛起这个历史重任，推动中美关系这艘巨轮沿着正确航道平稳前行。`;
- Xinhua Supplementary Claim: `一次历史性标志性访问。`.

The candidates are not approved merely because they appear in this design. The implementation must resolve registry entries, capture exact spans and metadata, and verify content hashes before approval.

A same-event Douyin or XHS source is required only when a verifiable archived source exists. If archive verification fails, the Case exposes a Platform Gap with the attempted source/time scope. It must not fabricate content, relax the event identity, or mix a different event to fill the matrix.

### 13.2 Twitter Benchmark

The Twitter benchmark is a fully separate research snapshot with:

- 39,964 rows;
- 60 users;
- 16,310 retweets;
- 8,697 replies;
- 4,814 quotes;
- SHA-256 `E4D12CC8F56D09FCFBEAC3B09C5D45537B8E390536E3860AFD768DDC651FB8B4`.

Only schema, statistics, provenance, and digest metadata may be committed. Full Markdown content is not committed. The benchmark has a different dataset identity and cannot contribute content, claims, platform completeness, semantic aggregates, or reports to the demonstration Case. Shared code evaluation must still emit separate snapshot and artifact hashes.

## 14. Failure States And Recovery

| Failure | Surface | Recovery |
| --- | --- | --- |
| Source not in Authority Source registry | Claim remains `pending_source_review`; blocker on approval. | Administrator versions the registry or rejects the candidate. |
| Primary Claim absent | Stance result `blocked_missing_primary_claim`; Risk Review may complete with the missing-stance limitation. | Approve a source-verified Primary Claim, then trigger incremental stance plus Risk Review. |
| Collection partial | Coverage and blocker shown without implying absence of activity. | Collect more or record a bounded Partial Collection Acknowledgement. |
| Platform archive unavailable | Platform Gap remains active. | Attach verifiable archive evidence later or retain the documented gap. |
| Model bytes missing or digest mismatch | Semantic task fails closed or degrades; no unpinned substitute. | Restore verified pinned bytes and rerun a new artifact. |
| Candidate model unvalidated | Artifact displays `candidate_unvalidated` and remains non-claimable. | Complete local evaluation and a separate governed status transition. |
| Insufficient topic/duplicate population | Artifact records coverage and abstains for that subtype. | Add a new snapshot or change policy in a new options version. |
| Snapshot or content hash mismatch | Reuse/report freeze rejected. | Rebuild references from verified immutable content. |
| Stale late worker result | Result retained but not promoted to active projection. | Run against current dependencies or explicitly inspect the historical result. |
| Concurrent Case mutation | `409` with current aggregate version. | Reload and submit a new intent with a new request hash. |
| Report render failure | Diagnostic audit/operational evidence is visible; temporary files are removed and no report-version row is created. | Retry idempotently after correcting renderer inputs; allocate a version only after HTML/PDF success. |
| PDF render differs from frozen HTML | Integrity check fails and PDF is unavailable. | Re-render from the exact stored HTML/assets and renderer version. |
| Audit persistence unavailable | Authoritative mutation fails atomically. | Retry after audit/outbox recovery; never accept an unaudited mutation. |

## 15. Package Boundaries

Implementation extends the active `system/` product root with shallow, cohesive boundaries. The only permitted new dependency is the bounded Chinese tokenizer `jieba>=0.42.1,<0.43.0`; sentence-transformers, Transformers, and scikit-learn remain existing dependencies.

```text
system/backend/app/
  api/v2/cases.py                 # thin HTTP mapping
  api/v2/authority_sources.py     # thin registry HTTP mapping
  core/analysis/                  # existing analysis boundary
    claim_extraction.py           # exact source-span extraction
    source_matching.py            # deterministic registry matching
    semantic_*.py                 # focused enrichment algorithms and port
  models/
    case.py
    case_snapshot.py
    case_run.py
    authority_source.py
    case_claim.py
    case_action.py
    case_report.py
    case_audit.py
    case_feedback.py
    case_closeout.py
    partial_collection.py
    semantic_artifact.py
  schemas/
    case.py
    authority_source.py
    case_lifecycle.py
    case_report.py
    semantic_artifact.py
  services/
    case_repository.py
    case_lifecycle_service.py
    case_orchestration_service.py
    case_report_service.py
    authority_source_service.py
    case_claim_service.py
    semantic_artifact_repository.py

system/frontend/src/
  api/cases.ts
  api/authority-sources.ts
  types/case.ts
  views/cases/index.vue
  views/cases/create.vue
  views/cases/workbench.vue
  views/cases/components/
```

Boundary rules:

- Focused services own Case transactions and lifecycle invariants; pure claim matching and semantic analysis extend the existing `app/core/analysis/` boundary.
- `models/` owns persistence records, `schemas/` owns API contracts, and `services/` owns transactions and orchestration.
- `case_orchestration_service.py` calls the existing analysis registry/executor and never duplicates stage execution.
- Focused `app/core/analysis/semantic_*.py` modules own deterministic semantic computation and provenance contracts behind the existing analysis port.
- Existing Analysis API routes and the default four-stage behavior remain backward compatible.
- Existing canonical score owners remain unchanged. Semantic artifacts are linked evidence only.
- The frontend Case route is parallel to specialist views and links into them with Case/snapshot/run context.
- Any later implementation of these proposed paths must update system governance, project map, README, development log, and relevant ADRs in that implementation change.

## 16. Test Strategy

### 16.1 Domain And Persistence Tests

- Enumerate the exact eight Case States and reject all other values.
- Test every allowed transition and every missing gate; prove blockers do not change Case State.
- Enforce one active approved Primary Claim per Case and preserve superseded approvals.
- Reject a Case Claim without verbatim excerpt, exact source span, publication metadata, registry version, or matching content hash.
- Verify non-registry URLs remain pending and tier changes are versioned.
- Prove Event Snapshots, claims, verdicts, corrections, reports, actions, and Audit Events are append-only.
- Enforce closure only with an approved Canonical Verdict, all required actions completed/waived, and a submitted Closeout Review; assert that no fourth acceptance status is defined.
- Exercise transaction rollback when Audit Event/outbox persistence fails.

### 16.2 Orchestration And Semantic Tests

- Preserve the existing four default Analysis Stages when `requested_stages` is omitted.
- Require explicit `semantic_enrichment` from Case orchestration.
- Without Primary Claim, allow Coordination Discover, Propagation Analysis, sentiment, topics, keywords, entities, near duplicates, and Risk Review; assert exact stance blocker code `blocked_missing_primary_claim` and no Risk Review blocker.
- On Primary Claim approval, assert only stance and Risk Review dependencies rerun when snapshot/model hashes are unchanged.
- Prove shared embeddings are computed once per dependency key and reused by keyword MMR, topic clustering plus c-TF-IDF, near duplicates, and community comparison.
- Prove main posts and comments remain separate scopes through artifacts and aggregates.
- Prove semantic results and corrections cannot alter Coordination Discover, Propagation Analysis, or Risk Review scores.
- Verify every pinned model revision and `candidate_unvalidated` status.
- Test degradation, abstention, digest mismatch, stale late results, and artifact reuse invalidation.

### 16.3 API, Permission, And Idempotency Tests

- Contract-test each Case, claim, action, report, audit, and Authority Source route.
- Verify viewers cannot mutate and analysts cannot administer Authority Sources.
- Verify the first-release same-actor approval path still emits distinct Audit Events.
- Replay every mutation with the same idempotency key/request hash and assert one result and one mutation event.
- Reuse a key with a different payload and assert `409 idempotency_conflict`.
- Exercise optimistic locking and out-of-order worker completion.

### 16.4 UI And Report Tests

- Route-level tests keep lifecycle, Primary Claim, and blockers visible on all five tabs.
- Test dense filters, pagination/virtualization, column persistence, deep links, SSE recovery, and permission states.
- Accessibility tests cover keyboard navigation, focus restoration, labels, non-color status cues, and narrow viewports.
- Snapshot tests compare frozen HTML manifests, while PDF smoke verifies page sizing, printable colors, asset embedding, and source/hash footers.
- Prove report versions do not change after later case mutations or renderer upgrades.

### 16.5 Dataset And Governance Tests

- Fixture tests assert the demonstration counts, Beijing windows, exact claim candidates, and platform-gap behavior.
- Isolation tests reject attaching Twitter benchmark content or claims to the demonstration Case.
- Metadata tests assert the Twitter statistics and SHA-256 while preventing full Markdown content from entering tracked files.
- Governance tests scan current docs and source for forbidden numbered shorthand and verify canonical method names.
- Migration and rollback tests verify unique constraints, indexes, append-only triggers/policies, and compatibility with existing Analysis Run callers.

## 17. Rollout

### Phase 0: Contracts And Evaluation

- Add an ADR, schema contracts, state/claim invariants, and local semantic evaluation protocol.
- Verify model bytes and digests; retain `candidate_unvalidated` until explicit evidence supports a status change.
- Create demonstration and benchmark metadata fixtures without full benchmark content.

### Phase 1: Read Model And Case Skeleton

- Add Case persistence, snapshot/run bindings, blockers, audit, and read-only workbench shell.
- Backfill no synthetic Cases automatically; allow explicit analyst creation from an existing Event Snapshot.
- Keep specialist pages and all existing APIs unchanged.

### Phase 2: Claims And Orchestration

- Add Authority Source administration, claim capture/approval, exact Primary Claim gate, and incremental Analysis Run orchestration.
- Ship with feature flags for case mutation and semantic execution.

### Phase 3: Semantic Evidence

- Add shared embeddings and semantic artifact types after local evaluation infrastructure exists.
- Expose degraded/abstained/candidate status in API and UI before enabling report inclusion.

### Phase 4: Actions, Closeout, And Reports

- Add action/waiver workflow, Closeout Review, frozen HTML, and print-friendly PDF.
- Validate idempotency, permissions, audit recovery, and long-report rendering before enabling closure.

### Phase 5: Operational Hardening

- Run realistic data-volume, concurrent-worker, migration, backup/restore, and accessibility tests.
- Review separation-of-duties policy and decide whether production requires distinct approvers.

## 18. Comparison With Existing Products And Methods

This is a scope comparison based on publicly described categories, not a procurement evaluation, benchmark, or superiority claim. Product editions and capabilities change; implementation decisions require version, deployment, license, and data-access verification.

| Product or method | Commonly described focus | Relevant design lesson | Boundary in this design |
| --- | --- | --- | --- |
| Brandwatch | Commercial social listening, search, dashboards, alerts, and consumer intelligence. | Analysts expect strong query, filtering, dashboard, and reporting ergonomics. | Case governance and evidence immutability are project requirements, not claims about Brandwatch coverage. |
| Talkwalker | Commercial media/social monitoring, analytics, alerts, and reporting across source types. | Cross-source navigation and operational reporting need dense, consistent context. | No parity claim; connector breadth and commercial data access are out of scope. |
| Pulsar TRAC | Audience intelligence and social/cultural research workflows. | Community and audience context can complement event evidence when provenance remains visible. | Coordination Community comparison is evidence context, not audience identity inference. |
| NewsWhip | Media monitoring and predictive attention/engagement signals. | Forecasts must expose observation cutoffs, calibration, and abstention instead of blending with observed facts. | CogGuard retains its existing Propagation Analysis contract; no forecast-accuracy comparison is asserted. |
| Blackbird.AI | Narrative and influence-risk intelligence positioned around cross-platform analysis. | Narrative labels should remain traceable to evidence and human decisions. | Topics and semantic artifacts remain derived, non-authoritative, and score-isolated. |
| CooRTweet | Research tooling for detecting coordinated behavior through shared actions and timing. | Coordination evidence needs transparent objects, windows, graphs, and reproducible parameters. | It remains a Reference Boundary; current product methods are Coordination Discover/Detect. |
| Hoaxy | Research visualization of claim/information diffusion and account networks. | Interactive propagation views benefit from explicit edge provenance and source paths. | The graph tab uses existing Propagation Analysis and does not infer truth from topology. |
| BERTopic | Topic modeling pipeline combining embeddings, clustering, and topic representation techniques. | Topic artifacts need model/config provenance, cluster coverage, and stable scope separation. | Topic clustering plus class-based TF-IDF is a semantic aid, not a Case Claim or required dependency choice. |
| KeyBERT | Embedding-based keyword/keyphrase extraction with diversity options such as maximal marginal relevance. | Reusing one embedding pass can reduce cost and keep keyword provenance aligned. | Keyword output is derived evidence and cannot anchor stance or Risk Review. |
| DISARM | A framework/taxonomy for describing information-manipulation behaviors and countermeasures. | A shared taxonomy can organize observed tactics and actions without becoming automatic proof. | Existing Risk Review mappings may be referenced, while Canonical Verdict and actions remain human-governed. |

These products and methods operate at different layers: some are commercial monitoring suites, some are research tools, and some are algorithms or taxonomies. The Case Workbench composes CogGuard's existing evidence, analysis, and governance boundaries; it is not positioned as a drop-in replacement for any one of them.

## 19. Residual Risks

- Authority Source administration can become stale or politically sensitive; tier assignment needs explicit evidence, effective dates, and review ownership.
- Single-analyst approval reduces operational friction but weakens separation of duties; audit visibility does not remove that risk.
- Deleted, edited, inaccessible, or dynamically rendered source content may prevent exact span verification despite a known URL.
- Platform collection gaps and API restrictions can bias cross-platform conclusions even when acknowledged.
- Candidate multilingual models may underperform on domain language, sarcasm, mixed scripts, short comments, or named entities; no model is claimable before local evaluation.
- One shared embedding pass improves reuse but couples downstream artifacts to preprocessing/model choices; dependency hashes and selective invalidation are essential.
- Topic and near-duplicate clusters may be overinterpreted as coordinated intent; UI labels and review policy must preserve their descriptive status.
- Append-only records and frozen assets increase storage and retention complexity.
- HTML-to-PDF rendering can vary by platform; renderer pinning and visual regression reduce but do not eliminate variance.
- Optimistic locking and idempotency reduce duplicate mutations but require careful transaction/outbox implementation under worker retries.
- The demonstration Case may lack verifiable same-event Douyin or XHS evidence; a visible Platform Gap is an acceptable outcome, not a reason to broaden the event.
- Public feature descriptions used in the comparison can change; no architecture dependency should rely on unverified commercial product behavior.

## 20. Acceptance Summary

The design is ready for implementation planning when reviewers confirm that:

- the exact Case States and closure gates are treated as normative;
- blockers remain separate data;
- source registry and verbatim claim rules are enforceable;
- Primary Claim approval drives only the specified incremental work;
- semantic provenance, degradation, correction, and score isolation are explicit;
- existing four-stage callers remain compatible;
- reports freeze exact versions and hashes;
- the demonstration and Twitter benchmark remain isolated;
- proposed package/API boundaries remain additive and shallow;
- comparison language is descriptive and makes no unsupported superiority claim.
