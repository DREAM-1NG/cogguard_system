# CogGuard Case Workbench Design

> Status: approved design baseline for Task 01 only. This document specifies future implementation; it does not claim that the described API, schema, route, models, or reports exist on `refactor-system` today.
>
> Scope: a durable, evidence-first Case Workbench for one `event_id`, with an auditable closed loop from collection through closure. Existing specialist pages remain available.

## Goal

Provide one formal **CaseRecord** aggregate per `event_id` that ties immutable event evidence to reproducible analysis, analyst review, actions, feedback, and frozen reports. The workbench must make the operative chain visible without turning a prediction into a fact:

```text
事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈
```

The primary user is an authenticated analyst who needs to answer: what was collected, which claim is primary, what is blocked, what analysis is reproducible, what action remains, and what was frozen at closure.

## Decisions And Non-Goals

### Decisions

- One `CaseRecord` is unique per `event_id`. A new data fingerprint creates an immutable EventSnapshot revision and a new `CaseAnalysisLink`; it does not overwrite prior evidence or decisions.
- Case lifecycle and blockers are different dimensions. Lifecycle is progress; blockers are independently recomputed gate reasons.
- A claim is evidence, not generated prose. The system stores exact quotation text and a source span; it must not create a paraphrased claim summary.
- There is exactly one current primary claim pointer per case. Supporting claims may be many; an immutable claim can only be replaced by a later claim and an append-only audit event.
- `semantic_enrichment` is an explicitly requested **Case-only** stage. The analysis engine may register it internally, but generic `/api/v2/analysis` requests and every non-Case orchestrator must reject it with the stable structured error `semantic_enrichment_case_only`. Existing default callers retain the current four-stage chain unchanged.
- Semantic outputs are auxiliary. Artifacts and corrections cannot change Coordination, Propagation, Student, Teacher, preliminary finding, canonical verdict, or any core risk score.
- The case page is a new parallel route. `/risk`, coordination, propagation, and account pages stay present and keep their current responsibility.
- Reports are versioned, frozen artifacts. `POST /api/v2/cases/{case_id}/reports` creates ordinary report versions only; it never changes claims, verdicts, actions, feedback, lifecycle, or an EventSnapshot and cannot set closure-owned fields. `POST /api/v2/cases/{case_id}/close` is the sole operation that creates a closure report, coupled to the closure review, lifecycle advance, and audit chain.

### Non-goals

- No Task 01 production migration, endpoint, crawler run, model download, UI route, or model performance claim.
- No new dependency other than a later, separately reviewed lightweight Chinese tokenizer if local evaluation proves it necessary.
- No cross-event aggregate, public API, automatic response action, automated closure, or replacement of the existing specialist tools.
- No claim that vendor product pages validate Chinese-domain quality, and no claim that model cards establish local performance.

## Compatibility With The Existing Event Review Case Contract

The existing contract is implemented as `ReviewCase`, `/api/v2/review-cases`, and `/risk`; it already has one event per case, immutable snapshot revisions, analyst decision drafts, confirmed decisions, activities, and an SSE stream. The following resolution is intentional rather than an accidental rename.

| Existing contract | Case Workbench decision | Compatibility rule |
| --- | --- | --- |
| `ReviewCase` is the current product aggregate. | `CaseRecord` becomes the canonical future aggregate and retains one `event_id` per case. | Migrate data into `case_records`; keep a read-compatible `review-cases` facade until its documented retirement release. |
| `/api/v2/review-cases` suppresses runtime/model fields from product projections. | `/api/v2/cases` is an authenticated analyst and reproducibility API with claim/run/artifact/report links. | Dashboard and `/risk` remain business-safe; technical metadata is not added to their existing summaries. |
| `/risk` is the single Event Review Case workspace. | `/case-workbench` is an additional dense case-closure page. | Do not redirect or remove `/risk`; link between the pages by case/event identity only. |
| Default analysis stages are `coordination_discover`, `propagation_analysis`, `student`, `teacher`. | Cases explicitly request `semantic_enrichment` plus the existing stages when appropriate. | `DEFAULT_ANALYSIS_STAGES` and legacy aliases remain byte-for-byte behaviorally compatible. |
| A Confirmed Decision is immutable and a later snapshot requires reconfirmation. | Every `CaseVerdictVersion` is immutable; the CaseRecord canonical-verdict pointer may advance only through an append-only approval or supersession transaction. | Existing decisions are represented as historical canonical-verdict sources rather than mutated or dual-written. |
| Governance details are not a main-product UI. | Frozen reports include reproducibility metadata required for audit. | Model/version/hash detail remains authenticated, report-scoped, and absent from ordinary dashboard copy. |

The future glossary belongs in this design until implementation lands. `UBIQUITOUS_LANGUAGE.md` stays a record of the currently shipped Event Review Case terms; changing it now would falsely assert that the Case Workbench has shipped.

## Ubiquitous Language

| Term | Definition | Avoid |
| --- | --- | --- |
| **CaseRecord** | The durable aggregate for exactly one event and its evidence-to-closure history. | Ticket, task, generic case row |
| **Case lifecycle** | The ordered progress state of a CaseRecord. | Blocked state, run state |
| **Blocker** | A separately evaluated reason that prevents a specific transition or result. | Lifecycle, error bucket |
| **AuthoritySource** | A versioned quoted-source record with an administrator-maintained `AuthorityTier` (or `null`) and independent review status. | URL string, source blob, claim role |
| **AuthorityTier** | One organizational class: `government_official`, `central_mainstream_media`, or `provincial_official_media`. | Claim role, pending state |
| **AuthorityReviewStatus** | Source review/allowlist state: `pending_review`, `allowlisted`, or `rejected`. | Authority tier, claim role |
| **CaseClaim** | An immutable exact quotation anchored to an AuthoritySource, source span, and independent `ClaimRole` (`primary` or `supporting`). | Generated summary, paraphrase, source tier |
| **Primary claim** | The one CaseClaim currently selected as the case's main stance evidence. | Best quote, default claim |
| **CaseVerdictVersion** | An immutable case-owned proposed or approved verdict payload/version; an approved version may supersede a prior canonical version without mutating it. | Mutable verdict row, legacy ReviewDecision write |
| **CaseAnalysisLink** | The immutable relationship between a case, snapshot revision, and analysis run. | Current run field |
| **SemanticArtifact** | An auxiliary semantic output with explicit scope, model identity, payload hash, and validation state. | Risk score, final interpretation |
| **SemanticCorrection** | An analyst correction that retains the original semantic prediction. | In-place label edit |
| **CaseAction** | A required or optional operational item with append-only state operations. | Verdict, workflow task |
| **CaseClosureReview** | An immutable case-owned record created only by a successful close transaction. It preserves the sanitized closure note and note hash, final canonical verdict identity/hash, action-state summary/hash, canonical `closure_review_sha256`, intended final lifecycle, actor, and timestamp. | Activity comment, mutable note, report request field |
| **CaseReportVersion** | An immutable frozen web/print/PDF report manifest. | Live export |
| **Closure review note** | The non-empty analyst input to `close`; it becomes a CaseClosureReview only if the entire close transaction succeeds. | Activity comment, pre-created closure report |

## Lifecycle And Gates

### Lifecycle

```text
draft -> collecting -> evidence_ready -> analyzing -> awaiting_review
      -> actioning -> ready_to_close -> closed
```

`closed -> collecting` is allowed only when a new EventSnapshot revision is linked after closure. It writes `case_reopened_for_snapshot` to the audit trail, preserves every prior report/version/verdict, and requires closure again. No lifecycle transition silently changes a historical report or CaseVerdictVersion.

| State | Entry condition | Exit condition |
| --- | --- | --- |
| `draft` | Case identity reserved; no collection manifest accepted. | Analyst/system starts collection. |
| `collecting` | Collection manifests or snapshot candidates are being added. | At least one valid EventSnapshot revision is linked. |
| `evidence_ready` | Snapshot evidence exists with declared quality and collection coverage. | Case requests analysis. A missing primary claim is allowed here. |
| `analyzing` | At least one CaseAnalysisLink is running. | Requested runs are terminal or have recorded non-fatal stage blockers. |
| `awaiting_review` | Analysis results and required evidence are ready for human review. | Analyst appends and approves a CaseVerdictVersion, or appends an approved successor that supersedes the current canonical version; action planning may then begin. |
| `actioning` | CaseRecord points to an approved canonical CaseVerdictVersion and actions are being resolved. | Every required action is complete or waived with an accountable reason. |
| `ready_to_close` | The current canonical CaseVerdictVersion is approved and required actions are complete/waived. | The public `close` operation receives a non-empty note, appends CaseClosureReview, freezes exactly one closure report, advances lifecycle, and appends audit atomically. |
| `closed` | A single successful close transaction committed an immutable CaseClosureReview, exactly one new closure report, the final lifecycle, and its audit-chain events. | Only a new snapshot revision can reopen it. |

### Blockers

Blockers are a set of typed records, never an overloaded lifecycle value. Each has `code`, `scope`, `opened_at`, `resolved_at`, `evidence_refs`, and `details`. Baseline codes are:

- `blocked_missing_primary_claim`: blocks stance-specific enrichment and a stance-dependent canonical verdict; does **not** block Coordination, Propagation, other semantic work, or data collection.
- `blocked_partial_collection`: records coverage limits such as one incomplete platform; it is visible to review but is not automatically fatal.
- `blocked_analysis_failure`: identifies the exact stage/run and allows unaffected stages to remain usable.
- `blocked_required_action`: prevents `ready_to_close` while a required action is neither complete nor formally waived.
- `blocked_missing_closure_review_note`: rejects a close request with an empty or whitespace-only note after the other readiness gates pass; it never creates a partial closure review.
- `blocked_report_generation`: represents a rendering/freezing/hash/audit failure during `close`. The close transaction rolls back rather than persisting a partial closure review, closure report, lifecycle change, blocker, or audit event from that attempt; the failure is returned as a structured close error rather than recorded as a partial closure effect.

The closure gate is deterministic and is executed only by `close_case`/`POST /api/v2/cases/{case_id}/close`: lock the CaseRecord; validate its approved current CaseVerdictVersion and every required action; validate and sanitize the non-empty close-request note; append and canonically hash CaseClosureReview as `closure_review_sha256`; render and freeze exactly one CaseReportVersion marked as the closure report; set its immutable `closure_review_id`/`closure_review_sha256` and target lifecycle `closed`; advance lifecycle; then append the audit-chain events. These writes share one database transaction. Failure while persisting the note, rendering/freezing, creating a content/hash value, or appending audit aborts the transaction, leaving no lifecycle, closure-review, closure-report, blocker, or audit mutation from that attempt. `POST /reports` can never create or mark a closure report. Earlier ordinary reports and earlier completed closure cycles remain immutable and distinct; a failed close does not turn either into a closure artifact.

## Aggregate And Data Model

The implementation creates focused SQLAlchemy model modules and one migration. JSON payloads are canonicalized before hashing; immutable references use stable IDs, not mutable display text.

| Record | Required fields and invariants |
| --- | --- |
| `CaseRecord` (`case_records`) | `case_id`, unique `event_id`, title, `lifecycle`, `current_snapshot_revision_id`, `primary_claim_id`, mutable `canonical_verdict_id` pointer to an immutable `CaseVerdictVersion`, `lifecycle_version`, timestamps/actors. The primary pointer is nullable until selected and is the only current-primary invariant. |
| `AuthoritySource` (`authority_sources`) | `authority_source_id`, canonical URL/root domain, publisher/account, nullable `authority_tier`, independent `review_status`, content hash, retrieval time, published time, source metadata, timestamps. A newly registered or unreviewed non-whitelisted source has `authority_tier = null` and `review_status = pending_review`; an administrator-rejected source has `authority_tier = null` and `review_status = rejected`; an allowlisted source has exactly one of `government_official`, `central_mainstream_media`, or `provincial_official_media`. The source record is versioned or superseded, never rewritten. |
| `CaseClaim` (`case_claims`) | `claim_id`, `case_id`, `authority_source_id`, exact quote, `span_start`, `span_end`, original URL, account, `published_at`, `authority_tier_snapshot`, `authority_review_status_snapshot`, content SHA-256, independent `claim_role` (`primary` or `supporting`), `supersedes_claim_id`. Quote span indexes Unicode code points in the exact captured source content. |
| `CaseVerdictVersion` (`case_verdict_versions`) | `case_verdict_version_id`, case, monotonic case version, immutable verdict payload/hash, source snapshot/run/primary-claim references, proposed/approved state, proposal-origin reference when approved from a proposal, optional `supersedes_verdict_id`, actor/timestamps, and provenance. No row is updated or deleted. A locked CaseRecord transaction may append an approved version, advance only `canonical_verdict_id`, transition lifecycle as appropriate, and append the matching audit event. |
| `CaseAnalysisLink` (`case_analysis_links`) | `case_analysis_link_id`, case, EventSnapshot revision ID, `run_id`, requested stage list, scope hash, link status, timestamps. A link is unique for `(case_id, snapshot_revision_id, run_id)`. |
| `SemanticArtifact` (`semantic_artifacts`) | `semantic_artifact_id`, `case_analysis_link_id`, artifact type, immutable monotonic `attempt_version`, scope JSON/hash, model identifier/revision/hash, run/input/output hashes, validation status, payload reference, timestamps. Every attempt, including an identical input/scope/model rerun, appends a new row; `uq_semantic_artifacts_link_type_attempt_version` prevents replacing an earlier attempt. |
| `SemanticCorrection` (`semantic_corrections`) | `correction_id`, immutable artifact-attempt ID, original prediction JSON/hash, corrected value, rationale, analyst, timestamp. Corrections are separate append-only rows and never overwrite an artifact or its payload. |
| `CaseAction` and `CaseActionOperation` (`case_actions`, `case_action_operations`) | Action creation is immutable; each state change (`assigned`, `in_progress`, `completed`, `waived`) is a new operation. Waive requires an accountable reason. The current state is a derived projection. |
| `CaseClosureReview` (`case_closure_reviews`) | `closure_review_id`, `case_id`, sanitized immutable note, note SHA-256, canonical `closure_review_sha256`, final canonical CaseVerdictVersion ID and payload SHA-256, canonical action-state summary JSON/SHA-256, intended final lifecycle (`closed`), actor, and timestamp. It is appended only inside a successful locked CaseRecord close transaction; no update/delete path exists. |
| `CaseIdempotencyRecord` (`case_idempotency_records`) | `case_id`, `operation`, `idempotency_key`, request hash, immutable stored response identity/payload hash, actor, timestamp. Close uses unique `(case_id, operation, idempotency_key)`; every mutation has an equivalent aggregate-scoped record so a retry cannot append a second domain effect. |
| `CaseFeedback` (`case_feedback`) | Feedback links a case, snapshot revision, run, optional CaseVerdictVersion, optional artifact/correction, and structured feedback. It never updates an original prediction. |
| `CaseReportVersion` (`case_report_versions`) | `report_id`, case, monotonic version, frozen report manifest/content hashes, web/print/PDF references, generation actor/time, and server-owned `is_closure`. Ordinary reports have `is_closure = false` and null closure fields. A closure report is appended only by `close_case`, has `is_closure = true`, immutable `closure_review_id`/`closure_review_sha256`, target lifecycle `closed`, and closure provenance in its frozen manifest. No update or delete after creation. |
| `CaseAuditEvent` (`case_audit_events`) | Append-only event ID, case, aggregate type/ID, actor, event type, canonical JSON payload, `previous_event_hash`, event hash, idempotency key, timestamp. The hash chain detects application-level alteration; it is not a claim of protection from a privileged database administrator. |

`ReviewCaseSnapshotRevision`, `ReviewDecision`, `ReviewVerdictVersion`, and `ReviewFeedback` remain historical inputs during migration. An explicit migration/backfill maps each existing `ReviewCase.event_id` to one CaseRecord, links existing snapshot revisions/runs, creates provenance-marked immutable CaseVerdictVersions from confirmed decisions/verdict versions, and emits backfill audit events. It must never synthesize a CaseClosureReview, mark a legacy/imported report as a closure report, or place a backfilled CaseRecord in `closed` without the public close transaction and its complete provenance; imported reports remain ordinary historical versions with null closure fields. New Case Workbench verdict writes must not dual-write into `review_cases`, `ReviewDecision`, or `ReviewVerdictVersion`.

## Authority, Claim, And Evidence Policy

### Authority class, source review, and claim role

`AuthorityTier`, `AuthorityReviewStatus`, and `ClaimRole` are deliberately separate. Authority classification is organizational; source review records allowlist state; claim role is an analyst-selected property of an immutable claim. No organizational tier implies either claim role.

| Concept | Allowed values | Invariant |
| --- | --- | --- |
| `AuthorityTier` | `government_official`, `central_mainstream_media`, `provincial_official_media` | The administrator-managed organizational class for an allowlisted source. It never encodes primary/supporting claim role. |
| `AuthorityReviewStatus` | `pending_review`, `allowlisted`, `rejected` | The server-managed source review/allowlist state. A newly registered/unreviewed non-whitelisted URL is stored as `authority_tier = null`, `review_status = pending_review`; an administrator-rejected source is stored as `authority_tier = null`, `review_status = rejected`. |
| `ClaimRole` | `primary`, `supporting` | The independent role of a CaseClaim. A source in any allowlisted organizational tier may anchor either role when the analyst selects it. |

The allowlist is exact-domain plus HTTPS policy, is server-managed, and is audited when changed. Registering a source never silently elevates it: a newly registered/unreviewed non-whitelisted source remains `authority_tier = null`, `review_status = pending_review`. An administrator review may move a source to `allowlisted` with one organizational tier or to `rejected` with no tier. Claim creation and primary selection require an `allowlisted` AuthoritySource with a non-null tier, but selection also requires the claim's independent `claim_role = primary`.

For the seed case, the initial intended claims are stored exactly, with source URL/account/published time populated only after an analyst selects the authoritative source page:

| ClaimRole | Expected organizational source tier after administrator allowlisting | Required source review state before save/selection | Exact quote |
| --- | --- | --- | --- |
| `primary` | `central_mainstream_media` (CCTV) | `allowlisted` | `我们应当共同扛起这个历史重任，推动中美关系这艘巨轮沿着正确航道平稳前行。` |
| `supporting` | `central_mainstream_media` (Xinhua) | `allowlisted` | `一次历史性标志性访问。` |

The seed table expresses intended classification only. Before an administrator allowlists the selected article URL, its AuthoritySource remains `authority_tier = null` and `review_status = pending_review`. The quote fields must remain byte-for-byte/user-visible text. A claim cannot be saved until its URL, account, published timestamp, AuthoritySource review/classification snapshot, content hash, span, and independent claim role are present; no inferred source summary fills a missing field.

### Evidence integrity

- Canonicalize URLs, reject non-HTTPS, IP-literal, localhost, private, link-local, and redirect-to-private targets before any server fetch.
- Fetch source content through a bounded server-side retriever with content-type/size/time limits; do not render arbitrary remote HTML in the UI.
- Store source content hashes with claims and snapshot provenance; hash mismatch produces a new source/case-claim revision rather than changing an old one.
- Raw primary/source content is access-controlled, escaped on rendering, and never interpolated into report HTML without sanitization.
- Primary claim selection and CaseVerdictVersion approval/supersession require an authenticated analyst; authority-source review and allowlist administration are authenticated administrator operations.

## Analysis And Semantic Enrichment

### Requested stages

Existing callers keep:

```python
DEFAULT_ANALYSIS_STAGES = (
    "coordination_discover",
    "propagation_analysis",
    "student",
    "teacher",
)
```

Case orchestration explicitly creates a run with:

```python
CASE_WORKBENCH_STAGES = (
    "semantic_enrichment",
    "coordination_discover",
    "propagation_analysis",
    "student",
    "teacher",
)
```

The exact `CASE_WORKBENCH_STAGES` tuple above is persisted unchanged in every `CaseAnalysisLink`; it is neither reordered nor subsetted at this boundary. A generic `/api/v2/analysis` request or non-Case orchestrator that explicitly asks for `semantic_enrichment` receives `semantic_enrichment_case_only`, while a legacy caller that omits it sees the old behavior. `semantic_enrichment` is allowed as an independently terminal **engine** stage only after Case orchestration has admitted it and must report `blocked_missing_primary_claim` for stance only, rather than failing the entire run.

### Semantic contract

1. Materialize separate post and comment collections before embedding, extraction, clustering, sentiment, stance, or entity recognition.
2. Apply explicit `SemanticScope` filters: source time window, `platforms`, selected Coordination communities, optional propagation path IDs, content types, and deterministic ordering. Store scope JSON and its SHA-256.
3. Sequentially load models on CPU by default. On load/inference failure, emit a typed artifact status and continue unaffected stages; do not use an unpinned network fallback.
4. Write every output attempt as a new `SemanticArtifact` with `candidate_unvalidated` until a local evaluation is recorded. The per-link/per-artifact-type `attempt_version` is monotonic even when run/input/scope/model hashes are identical; a correction is a separate `SemanticCorrection`, never an overwritten label.
5. Project only descriptive semantic artifacts into the Case Workbench. Coordination, Propagation, Student, Teacher, preliminary finding, canonical verdict, and every core risk score must receive no semantic artifact field or correction and must compare byte-for-byte/equivalently before and after artifact or correction creation.

Pinned initial candidates:

| Capability | Candidate model | Use |
| --- | --- | --- |
| Shared embedding | `BAAI/bge-small-zh-v1.5@7999e1d` | One embedding cache for MMR, clustering, and similarity. |
| Sentiment | `lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110` | Auxiliary sentiment distribution. |
| Stance | `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92` | Primary-claim-relative stance only; blocked without a primary claim. |
| NER | `shibing624/bert4ner-base-chinese@5d660ed` | Candidate Chinese entity extraction. |

Keyword extraction is KeyBERT-style Maximal Marginal Relevance over shared embeddings. Topic discovery is BERTopic-style clustering plus c-TF-IDF using packages already present in the repository. A lightweight Chinese tokenizer is the only possible later dependency, and only after a local evaluation documents the need. No model card or upstream readme is evidence of Chinese-domain performance.

## API Contract

All endpoints are under shared JWT authentication. Product-safe legacy projections remain at `/api/v2/review-cases`; the following endpoints are explicit Case Workbench contracts.

| Endpoint | Operation | Contract |
| --- | --- | --- |
| `GET /api/v2/cases` | List | Filter by lifecycle, blocker, event ID, and updated time; returns only analyst-authorized case fields. |
| `POST /api/v2/cases` | Create/upsert | Creates the one case for an event or returns it idempotently; no duplicate event case. |
| `GET /api/v2/cases/{case_id}` | Detail | Returns lifecycle, blockers, primary claim pointer, current snapshot/run links, verdict/action/report summaries. |
| `POST /api/v2/authority-sources` | Register | Adds source without caller-controlled classification; a newly registered/unreviewed non-whitelisted domain becomes `authority_tier = null`, `pending_review`. |
| `POST /api/v2/authority-sources/{id}/review` | Review | Administrator-only append/version action that allowlists one organizational tier or rejects the source; it cannot choose a claim role. |
| `GET /api/v2/authority-sources` and `/{id}` | Read | Lists authoritative sources and immutable version metadata. |
| `POST /api/v2/cases/{case_id}/claims` | Add claim | Requires an allowlisted AuthoritySource, exact quote, span, URL/account/published-time consistency, content hash, and independent `claim_role`; service snapshots source class/review state rather than accepting caller-controlled tier. |
| `POST /api/v2/cases/{case_id}/claims/{claim_id}/select-primary` | Select | Atomically changes only the CaseRecord primary pointer and writes audit. |
| `POST /api/v2/cases/{case_id}/verdicts` | Create | Appends an immutable proposed CaseVerdictVersion with snapshot/run/claim references and a payload hash; it does not change the canonical pointer. |
| `POST /api/v2/cases/{case_id}/verdicts/{verdict_id}/approve` | Approve | Appends an approved CaseVerdictVersion derived from the proposal, locks the CaseRecord, advances only its canonical pointer, transitions lifecycle, and writes audit. |
| `POST /api/v2/cases/{case_id}/verdicts/{verdict_id}/supersede` | Supersede | Appends an approved successor with `supersedes_verdict_id`; it never updates/deletes the prior verdict row and advances the mutable pointer atomically. |
| `GET /api/v2/cases/{case_id}/verdicts` and `/{verdict_id}` | Read | Reads immutable verdict versions, provenance, supersession relationships, and the current-pointer projection. |
| `POST /api/v2/cases/{case_id}/runs` | Request | Creates a CaseAnalysisLink and explicitly requests exactly `("semantic_enrichment", "coordination_discover", "propagation_analysis", "student", "teacher")`. |
| `GET /api/v2/cases/{case_id}/runs` | Read | Reads immutable links and stage statuses. |
| `GET /api/v2/cases/{case_id}/artifacts` | Read | Reads scoped semantic artifacts without merging them into risk scores. |
| `POST /api/v2/cases/{case_id}/artifacts/{artifact_id}/corrections` | Correct | Appends SemanticCorrection with original prediction preserved. |
| `POST /api/v2/cases/{case_id}/actions` | Create | Creates required/optional action. |
| `POST /api/v2/cases/{case_id}/actions/{action_id}/operations` | Operate | Appends state operation; waiver requires rationale. |
| `POST /api/v2/cases/{case_id}/feedback` | Add feedback | Appends feedback bound to the proper case/snapshot/run/verdict/artifact IDs. |
| `POST /api/v2/cases/{case_id}/reports` | Freeze ordinary report | Generates a new frozen ordinary report version only. Its `extra="forbid"` request contract accepts no `closure_flag`, `is_closure`, lifecycle, closure note, `closure_review_id`, `closure_review_sha256`, target lifecycle, or other server-owned closure field; the service always persists `is_closure = false` and null closure provenance. |
| `GET /api/v2/cases/{case_id}/reports` and `/{report_id}` | Read | Retrieves report manifest and authenticated web/print/PDF references. |
| `POST /api/v2/cases/{case_id}/close` | Close | The only operation permitted to create a closure report. Requires an idempotency key. In one locked CaseRecord transaction it validates the approved current CaseVerdictVersion, all required actions, and a non-empty request note; creates a `CaseIdempotencyRecord`; appends/hashes CaseClosureReview; freezes exactly one `is_closure = true` report with `closure_review_id`/`closure_review_sha256` and target lifecycle provenance; advances lifecycle to `closed`; and appends audit. The record persists the response identity/hash. A same-key/same-request replay returns the original CaseCloseResult without a second review/report/audit; a same-key/different-request collision returns `idempotency_conflict`; concurrent different keys serialize on the CaseRecord so one commits and the loser returns `close_already_committed` with the committed closure identities. Any note/render/freeze/hash/audit failure rolls back every effect of this attempt, including the idempotency record. |

Error responses use stable `code`, `message`, `details`, and request ID. Important codes are `case_event_conflict`, `primary_claim_invalid`, `blocked_missing_primary_claim`, `semantic_enrichment_case_only`, `immutable_record`, `verdict_approval_conflict`, `close_gate_unmet`, `close_already_committed`, `action_operation_conflict`, `source_pending_review`, and `idempotency_conflict`.

## Case Workbench UI

The new authenticated route is `/case-workbench` with route name `CaseWorkbench`. It presents dense operational information, not a marketing landing page. `/risk` and all specialist pages continue unchanged.

Persistent header on every tab:

- event title and `event_id`;
- current lifecycle state;
- primary claim exact quote/source link (or an explicit primary-claim blocker);
- visible blocker chips with scoped explanation;
- canonical verdict state and required-action count;
- closed-loop progress strip: `事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈`.

| Tab | Contents and commands |
| --- | --- |
| `概览` | Lifecycle timeline, data coverage, snapshot/run linkage, canonical verdict/review differences, primary claim, blocker details, recent append-only audit activity. |
| `证据矩阵` | Exact claims, AuthoritySource organizational tier/review status, independent claim role, evidence rows, quote spans, source hashes, supporting/contradictory relationship, and primary selection. |
| `图谱` | Read-only Coordination and Propagation references plus separately marked semantic communities/entities; filters always show time/platform/community/path and post/comment split. |
| `处置` | Canonical verdict, action list, append-only operations, waiver reasons, feedback form, closure-review-note input, and a readiness checklist. The close command is enabled only for API-provided ready gates plus a non-empty note; it calls `POST /close` and presents the returned immutable closure-report ID/version. It never pre-creates a report or exposes a closure flag. |
| `报告` | Version list, frozen web/print/PDF report access, included snapshot/run/model/hash manifest, report-content checksum, ordinary-report regeneration command only for authorized users, and a distinct immutable closure-report label/provenance when present. |

No semantic artifact is displayed as a risk score. The UI labels all candidate semantic values as `候选，待本地评估` until their evaluation record changes the status. Long exact quotes wrap without truncating the source link or overlapping lifecycle controls.

## Frozen Report Contract

A report version includes only data frozen at its creation timestamp. `POST /reports` creates ordinary versions with `is_closure = false`; it has no caller-controlled closure fields. Only the successful close transaction creates a closure version with `is_closure = true`.

- CaseRecord identity, lifecycle, primary claim selection, blockers, current canonical CaseVerdictVersion ID/version/supersession lineage, and its immutable payload hash;
- all linked EventSnapshot revisions with data fingerprints, windows, quality, and content/source hashes;
- CaseAnalysisLinks with requested stages, run IDs/statuses, artifact manifests, model identifiers/revisions, and their hashes;
- exact claim text/spans/source identities and action/feedback/audit references;
- report HTML checksum, print stylesheet checksum, PDF file checksum, generator version, and report version number.

A frozen closure report additionally includes, without a mutable live lookup:

- CaseClosureReview ID, canonical `closure_review_sha256`, sanitized closure note (or an immutable content reference), and note SHA-256;
- final canonical CaseVerdictVersion ID/version and immutable payload hash;
- canonical action-state summary and its hash;
- snapshot, run, model, and content hashes used at close; and
- target final lifecycle `closed` plus the close/audit provenance that binds the report to that transaction.

Web view is sanitized static HTML. Print view is a deterministic stylesheet over the same frozen payload. PDF is produced from the frozen print payload and has a content SHA-256. Later collection, analysis, action, or correction creates a later report version; it cannot revise a prior version. A reopened and subsequently re-closed case creates a new CaseClosureReview and exactly one new closure report for that later close transaction; it never rewrites earlier ordinary or closure reports.

## Data Seed And Collection Boundary

The first case seed is `trump_visit_2026_05_21`.

| Item | Baseline |
| --- | --- |
| Core window | 2026-05-14 through 2026-05-17, Beijing time, stored as a half-open UTC-normalized interval. |
| Context window | 2026-05-08 through 2026-05-20, Beijing time, stored as a half-open UTC-normalized interval. |
| Existing Weibo main posts | 74 unique posts from 57 authors. |
| Existing Weibo comments | 5,048 unique comments from 4,492 comment users. |
| Additional platform | One same-event Douyin collection is required before the seed may be marked complete; Task 01 does not invent counts or claim it has been collected. |
| Coverage status | `partial_collection` until the additional platform is collected and recorded. |

The separate Twitter benchmark is not case evidence and must never be folded into `trump_visit_2026_05_21`. Its manifest holds only verified metadata/statistics/hash; the CSV and any full conversion remain outside the repository.

## Security, Retention, And Audit

- Use existing JWT authentication and least-privilege roles. Analysts can create claims, verdict proposals/approvals, actions, feedback, and close; administrators manage AuthoritySource organizational tiers, review/allowlist status, and retention configuration.
- Validate all external URLs server-side; no browser-controlled fetches, no internal-address fetches, and no arbitrary report embeds.
- Redact access tokens, credentials, cookies, and unapproved raw source bodies from API responses, audit payloads, browser logs, and reports.
- All mutation commands require idempotency keys and append an audit event in the same database transaction. Close persists its replayable response behind unique `(case_id, operation, idempotency_key)` and locks CaseRecord: same-key/same-request retries return the stored result, while concurrent different keys serialize to exactly one closure review/report/audit and the losing key gets `close_already_committed` with the committed identities. The close path commits its idempotency record, closure review, rendered/frozen closure report, lifecycle transition, hashes, and audit-chain append as one transaction; a failure at any step rolls all of those effects back. Report/PDF data references are immutable after the write commits.
- Preserve audit events and report manifests according to deployment retention policy; redaction uses a new audited event describing the withdrawn view, never an unrecorded deletion.
- Audit verification checks event ordering, hash-chain linkage, payload hashes, foreign-key ownership, action-operation derivation, and report-manifest checksums.

## Acceptance Criteria

1. A case for one event can retain multiple immutable snapshot revisions, runs, reports, and decisions without replacing history.
2. The seed CCTV primary quote and Xinhua supporting quote can be represented exactly with all required provenance fields. Both use `central_mainstream_media` after allowlisting while their independent ClaimRoles remain `primary` and `supporting`; a newly registered/unreviewed non-whitelisted URL has `authority_tier = null` and `review_status = pending_review`, while an administrator-rejected source has `authority_tier = null` and `review_status = rejected`.
3. Missing primary claim yields `blocked_missing_primary_claim` for stance only, while Coordination/Propagation and other permitted semantic outputs proceed.
4. Existing four-stage default analysis calls and `/api/v2/review-cases` contract tests continue unchanged.
5. Every semantic attempt, including identical reruns, is append-only and candidate/unvalidated until local evaluation. Artifacts and corrections cannot alter Coordination, Propagation, Student, Teacher, preliminary finding, canonical verdict, or any core risk score.
6. `/case-workbench` is usable alongside `/risk` and specialist pages, with the specified five tabs and persistent lifecycle/claim/blocker context.
7. `POST /reports` creates ordinary frozen reports only and rejects caller-controlled `closure_flag`, `is_closure`, lifecycle, closure-note, closure-review, target-lifecycle, and other server-owned closure fields.
8. A ready-to-close case can reach `closed` through the public service/API close operation without a pre-created report: the one transaction locks CaseRecord, validates the approved current CaseVerdictVersion/actions/non-empty note, appends and hashes immutable CaseClosureReview, freezes exactly one linked closure report, advances lifecycle, appends the audit chain, and returns the server-created closure-report ID/version.
9. A note-persistence, rendering/freezing, hash-creation, or audit-append failure rolls back the attempted closure review, closure report, lifecycle transition, and audit effects; earlier ordinary reports and failed attempts remain distinct.
10. A frozen closure report contains the sanitized note or immutable note reference plus hash, final canonical verdict identity/hash, action-state summary, snapshot/run/model/content hashes, and target final lifecycle. Previous report versions remain immutable.
11. Verdict proposal, approval, supersession, pointer advance, and all other operations remain auditable and append-only.
12. `semantic_enrichment` is rejected at generic/non-Case request boundaries and only a CaseAnalysisLink can persist the exact five-stage Case tuple.
13. Same-key close retries replay the committed result without duplicate history; concurrent same-key or different-key closes leave exactly one closure review/report/audit.
