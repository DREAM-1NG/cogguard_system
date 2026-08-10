# Case Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an authenticated, evidence-first Case Workbench that carries one event from immutable collection evidence through analysis, review, action, feedback, frozen reporting, and closure without replacing the current Event Review Case experience.

**Architecture:** Add a focused `case_workbench` domain alongside the current `review_case` domain. Case data is append-only or versioned, while current `review-cases` remains a compatibility facade. Case orchestration explicitly requests `semantic_enrichment`; the existing default analysis stage list remains unchanged. The frontend gets `/case-workbench` as a parallel dense route and keeps `/risk` plus the specialist pages intact.

**Tech Stack:** FastAPI, SQLAlchemy async models, Alembic, Pydantic v2, existing AnalysisRegistry/AnalysisExecutor, Vue 3, TypeScript, Ant Design Vue, Node built-in tests, pytest, existing model/runtime packages only.

## Global Constraints

- Preserve the default four-stage analysis request exactly: `coordination_discover`, `propagation_analysis`, `student`, `teacher`.
- Case orchestration explicitly requests `semantic_enrichment` and records the requested list in `CaseAnalysisLink`.
- `semantic_enrichment` is auxiliary and must never alter Coordination, Propagation, Review, preliminary finding, canonical verdict, or risk scores.
- Keep posts and comments separately stratified and scope semantic work by time, platform, Coordination community, and propagation path.
- Pin candidate models exactly: `BAAI/bge-small-zh-v1.5@7999e1d`, `lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110`, `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92`, and `shibing624/bert4ner-base-chinese@5d660ed`.
- Candidate semantic outputs are `candidate_unvalidated` until a local evaluation record says otherwise; a correction retains the original prediction.
- Do not add dependencies. A later separately approved change may add only a lightweight Chinese tokenizer after local evaluation proves the need.
- One `CaseRecord` is unique per `event_id`; snapshots, analysis links, verdicts, actions, feedback, reports, and audit history are immutable or append-only.
- Claims save the exact quote, Unicode code-point span, URL, account, `published_at`, AuthoritySource class/review snapshots, independent `claim_role`, and content SHA-256. There is one selected primary claim and zero or more supporting claims. No generated summary substitutes for a quote.
- `AuthorityTier` has exactly three organizational values: `government_official`, `central_mainstream_media`, and `provincial_official_media`. `AuthorityReviewStatus` is separate: `pending_review`, `allowlisted`, or `rejected`. A non-whitelisted URL has `authority_tier = null` and `review_status = pending_review`; `ClaimRole` is independently `primary` or `supporting`.
- Missing primary claim produces `blocked_missing_primary_claim` for stance only. It does not block other analysis or collection.
- `POST /api/v2/cases/{case_id}/reports` freezes ordinary reports only and its request cannot set `closure_flag`, `is_closure`, lifecycle, closure note, closure-review provenance, target lifecycle, or any other server-owned closure field. `POST /api/v2/cases/{case_id}/close` is the only creator of a closure report: one locked transaction validates the approved current immutable CaseVerdictVersion, required actions, and non-empty note; appends and hashes immutable CaseClosureReview; freezes exactly one linked closure report; advances lifecycle to `closed`; appends audit; and returns the server-created `closure_report_id` and `closure_report_version`. Note persistence, rendering/freezing, hash creation, or audit failure rolls back every effect of that close attempt.
- `/api/v2/review-cases`, `/risk`, coordination, propagation, account, and dashboard behavior stay compatible while `/api/v2/cases`, `/api/v2/authority-sources`, and `/case-workbench` are introduced.
- Product summaries remain business-safe. Detailed model/run/hash data is authenticated and report-scoped; it must not leak into the existing dashboard or `/risk` projections.
- All new requests use shared JWT auth, `extra="forbid"`, server-side URL validation, idempotency keys, and stable structured error codes.
- Seed event is `trump_visit_2026_05_21`: existing Weibo coverage is 74 unique main posts/57 authors and 5,048 unique comments/4,492 comment users; core is 2026-05-14..17 Beijing and context is 2026-05-08..20. Add one same-event Douyin collection manifest without inventing counts; report `partial_collection` until it exists.
- Never commit `C:\Users\p\AppData\Local\Temp\cogguard-032020-twitter-io-full.csv` or a full Markdown conversion. Its manifest only records 39,964 rows, 60 users, 16,310 retweets, 8,697 replies, 4,814 quotes, and SHA-256 `E4D12CC8F56D09FCFBEAC3B09C5D45537B8E390536E3860AFD768DDC651FB8B4`.
- Maintain the two user-owned dirty files under `system/doc/research/propagation_paper_deep_reads/`; neither may be edited or staged.

## File Structure

| Path | Responsibility |
| --- | --- |
| `system/backend/app/models/case_workbench.py` | Focused persistence records for the new aggregate, claims, immutable CaseVerdictVersions, links, semantic artifacts/corrections, actions, CaseClosureReview, feedback, reports, and audit. |
| `system/backend/app/schemas/case_workbench.py` | Pydantic request/response contracts and lifecycle/authority/review-status/verdict/error enums, including ordinary-only report freeze and a close result that exposes closure-review ID/hash plus server-created closure-report ID/version. |
| `system/backend/app/services/case_workbench_service.py` | Transactional aggregate behavior, gate evaluation, immutable/append-only writes, and response projection. |
| `system/backend/app/services/case_workbench_repository.py` | Persistence-specific locking, idempotency, audit append, and historical backfill helpers. |
| `system/backend/app/services/case_workbench_orchestrator.py` | Snapshot-to-case linkage and explicit semantic-enrichment requests. |
| `system/backend/app/core/analysis/contracts.py` | Add `semantic_enrichment` to the allowlist without changing `DEFAULT_ANALYSIS_STAGES`. |
| `system/backend/app/core/analysis/semantic_enrichment.py` | Isolated, sequential, CPU-first auxiliary semantic stage and model manifest construction. |
| `system/backend/app/api/v2/cases.py` | Authenticated Case Workbench endpoints. |
| `system/backend/app/api/v2/authority_sources.py` | Authenticated authority-source endpoints. |
| `system/backend/app/api/v2/router.py` | Mount new routers while retaining `review_cases.router`. |
| `system/backend/alembic/versions/<generated_revision>_add_case_workbench.py` | One reversible schema/backfill migration generated at Task 2 execution from the then-current single Alembic head. Task 01 verified the current unique head as `e5c1b7d9a204`; this is evidence, not a future `down_revision` constant. |
| `system/backend/tests/test_case_workbench_*.py` | Small contract, persistence, service, orchestration, API, report, and migration tests. |
| `system/frontend/src/types/caseWorkbench.ts` | Narrow Case Workbench TypeScript contracts. |
| `system/frontend/src/api/caseWorkbench.ts` | Typed API client and safe endpoint encoders. |
| `system/frontend/src/views/case-workbench/index.vue` | Route-level persistent header and five dense tabs. |
| `system/frontend/tests/case-workbench.spec.mjs` | Node tests for API helper/route source contracts. |
| `docs/superpowers/specs/2026-08-10-case-workbench-design.md` | Approved design; update only when an implementation decision changes. |
| `doc/research/case-workbench/` | Research/collection manifests and source provenance; no benchmark CSV. |

---

### Task 1: Lock The New Domain Contract Before Persistence

**Files:**

- Create: `system/backend/tests/test_case_workbench_schema.py`
- Create: `system/backend/app/schemas/case_workbench.py`
- Modify: `system/backend/app/schemas/__init__.py`

**Interfaces:**

- Produces `CaseLifecycle`, `AuthorityTier`, `AuthorityReviewStatus`, `ClaimRole`, `SemanticValidationStatus`, `CaseActionOperationType`, `CaseReportFreezeRequest`, `CaseCloseRequest`, `CaseCloseResult`, `AuthoritySourceCreate`, `AuthoritySourceReview`, `CaseClaimCreate`, `CaseVerdictCreate`, `CaseVerdictApprove`, `CaseVerdictSupersede`, and `CaseDetail`.
- `AuthoritySourceCreate` registers source identity/provenance but cannot let an analyst choose a tier or review state. `AuthoritySourceReview` is administrator-only and sets one organizational tier with `allowlisted`, or no tier with `rejected`. `CaseClaimCreate` requires an `authority_source_id`, `exact_quote`, `span_start`, `span_end`, `account`, `published_at`, independent `claim_role`, and a 64-character SHA-256 content hash; the service snapshots source class/review state instead of accepting caller-controlled authority fields.
- `CaseReportFreezeRequest` is `extra="forbid"` and has no closure fields. `CaseCloseRequest` has the non-empty closure review note and no caller-controlled lifecycle/report/provenance fields. `CaseCloseResult` returns the closed CaseRecord projection plus `closure_review_id`, `closure_review_sha256`, `closure_report_id`, and `closure_report_version`; no caller supplies any of those values.

- [ ] **Step 1: Write failing schema tests.**

```python
def test_case_claim_rejects_missing_source_provenance():
    with pytest.raises(ValidationError):
        CaseClaimCreate.model_validate({
            "exact_quote": "原文",
            "span_start": 0,
            "span_end": 2,
            "claim_role": "primary",
        })


def test_lifecycle_does_not_use_blocked_as_a_state():
    assert "blocked" not in {item.value for item in CaseLifecycle}
    assert CaseLifecycle.CLOSED.value == "closed"


def test_authority_tier_review_status_and_claim_role_are_independent():
    assert {item.value for item in AuthorityTier} == {
        "government_official", "central_mainstream_media", "provincial_official_media"
    }
    assert {item.value for item in AuthorityReviewStatus} == {
        "pending_review", "allowlisted", "rejected"
    }
    claim = CaseClaimCreate.model_validate({
        **VALID_CLAIM,
        "authority_source_id": "source_1",
        "claim_role": "supporting",
    })
    assert claim.claim_role is ClaimRole.SUPPORTING


def test_ordinary_report_request_rejects_server_owned_closure_fields():
    for field, value in {
        "closure_flag": True,
        "is_closure": True,
        "lifecycle": "closed",
        "closure_review_note": "checked",
        "closure_note": "checked",
        "closure_review_id": "closure_1",
        "closure_review_sha256": "0" * 64,
        "target_lifecycle": "closed",
        "closure_report_id": "report_1",
    }.items():
        with pytest.raises(ValidationError):
            CaseReportFreezeRequest.model_validate({field: value})
```

- [ ] **Step 2: Run the tests and verify RED.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_schema.py -q`

Expected: import failure for `app.schemas.case_workbench` because the new contract does not exist.

- [ ] **Step 3: Implement only the contract types and validators.**

```python
class CaseLifecycle(StrEnum):
    DRAFT = "draft"
    COLLECTING = "collecting"
    EVIDENCE_READY = "evidence_ready"
    ANALYZING = "analyzing"
    AWAITING_REVIEW = "awaiting_review"
    ACTIONING = "actioning"
    READY_TO_CLOSE = "ready_to_close"
    CLOSED = "closed"


class AuthorityTier(StrEnum):
    GOVERNMENT_OFFICIAL = "government_official"
    CENTRAL_MAINSTREAM_MEDIA = "central_mainstream_media"
    PROVINCIAL_OFFICIAL_MEDIA = "provincial_official_media"


class AuthorityReviewStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    ALLOWLISTED = "allowlisted"
    REJECTED = "rejected"


class CaseClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authority_source_id: str = Field(min_length=1)
    exact_quote: str = Field(min_length=1, max_length=16000)
    span_start: int = Field(ge=0)
    span_end: int = Field(gt=0)
    account: str = Field(min_length=1, max_length=512)
    published_at: datetime
    claim_role: ClaimRole
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
```

Validate `span_end > span_start`, lowercase hash normalization, all enums from the approved design, and the administrator-only authority-review state transition. `CaseClaimCreate` must reject authority-tier or review-status extras. Reject whitespace-only `CaseCloseRequest.closure_review_note`; reserve note sanitization, CaseClosureReview persistence, and all closure-report fields for `close_case`. `CaseReportFreezeRequest` must reject every server-owned closure field. Do not create persistence or API code in this task.

- [ ] **Step 4: Run GREEN and existing schema regression.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_schema.py tests/test_review_case_contracts.py tests/test_analysis_run_schema.py -q`

Expected: all pass; legacy schema/default-stage behavior remains unchanged.

- [ ] **Step 5: Review and commit.**

Rollback boundary: this task is an additive schema module and export only; revert its commit without database impact.

Commit only these paths with a Lore message explaining that the contract fixes terminology and validation before storage.

### Task 2: Add Immutable Case Workbench Persistence And A Reversible Migration

**Files:**

- Create: `system/backend/app/models/case_workbench.py`
- Modify: `system/backend/app/models/__init__.py`
- Create: `system/backend/alembic/versions/<generated_revision>_add_case_workbench.py`
- Create: `system/backend/tests/test_case_workbench_persistence.py`
- Create: `system/backend/tests/test_case_workbench_migration_contract.py`

**Interfaces:**

- Produces `CaseRecord`, `AuthoritySource`, `CaseClaim`, `CaseVerdictVersion`, `CaseAnalysisLink`, `SemanticArtifact`, `SemanticCorrection`, `CaseAction`, `CaseActionOperation`, `CaseClosureReview`, `CaseFeedback`, `CaseReportVersion`, and `CaseAuditEvent`.
- `CaseRecord.event_id` is unique; `CaseRecord.primary_claim_id` is nullable and is the only mutable primary pointer. `CaseRecord.canonical_verdict_id` is the only mutable pointer to an immutable CaseVerdictVersion.

- [ ] **Step 1: Write persistence/migration RED tests.**

```python
def test_case_record_has_one_event_unique_constraint_and_primary_pointer():
    names = {constraint.name for constraint in CaseRecord.__table__.constraints}
    assert "uq_case_records_event_id" in names
    assert CaseRecord.__table__.c.primary_claim_id.nullable


def test_case_audit_event_has_hash_chain_and_idempotency_fields():
    columns = CaseAuditEvent.__table__.c
    assert {"previous_event_hash", "event_hash", "idempotency_key"} <= set(columns)


def test_case_verdict_versions_are_append_only_and_case_versioned():
    columns = CaseVerdictVersion.__table__.c
    assert {"case_id", "version", "payload_sha256", "supersedes_verdict_id"} <= set(columns)
    assert "uq_case_verdict_versions_case_version" in {
        constraint.name for constraint in CaseVerdictVersion.__table__.constraints
    }


def test_closure_review_and_closure_report_provenance_are_immutable_and_case_owned():
    review = CaseClosureReview.__table__.c
    report = CaseReportVersion.__table__.c
    assert {
        "case_id", "sanitized_note", "note_sha256", "closure_review_sha256", "canonical_verdict_id",
        "canonical_verdict_payload_sha256", "action_state_summary_sha256", "target_lifecycle",
    } <= set(review)
    assert {"is_closure", "closure_review_id", "closure_review_sha256", "target_lifecycle"} <= set(report)
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_persistence.py tests/test_case_workbench_migration_contract.py -q`

Expected: import failure because `case_workbench.py` and migration do not exist.

- [ ] **Step 3: Preflight, then create focused models and one Alembic revision.**

At Task 2 execution, run `cd system/backend; python -m alembic heads` before generating any migration and require exactly one head. Task 01's correction verification observed the unique head `e5c1b7d9a204`, but implementers must not reuse it as a fixed parent: record the then-current output, run `python -m alembic revision -m "add case workbench"`, use the generated `<generated_revision>_add_case_workbench.py` path, and verify its `down_revision` equals that observed head. Re-run `python -m alembic heads` after creation and require one head.

Use explicit foreign keys and named indexes/constraints. Add `case_actions` plus `case_action_operations` so state changes are append-only. Add `case_verdict_versions` with a per-case monotonic version, immutable payload/hash, source snapshot/run/claim references, proposal-origin reference, optional `supersedes_verdict_id`, and actor/timestamps; no update/delete path exists. Add `case_closure_reviews` as an immutable case-owned table with sanitized-note/hash, canonical `closure_review_sha256`, final canonical-verdict ID/hash, action-state summary/hash, target lifecycle, actor, and timestamp. Add server-owned closure provenance columns to `case_report_versions`; ordinary reports persist `is_closure = false` with null closure fields, while a closure report requires its CaseClosureReview foreign key/`closure_review_sha256` and target lifecycle. Keep JSON as canonical-text payloads with a payload SHA-256. In `upgrade`, create tables and backfill a CaseRecord per existing `review_cases.event_id` plus provenance-marked CaseVerdictVersions for existing confirmed decisions/verdict versions; do not synthesize CaseClosureReview records, mark imported reports as closure reports, or backfill `closed` without the complete public-close provenance. Imported historical reports remain ordinary versions with null closure fields. In `downgrade`, drop only the new tables and never delete or write historical `review_cases` data.

- [ ] **Step 4: Verify GREEN and migration round trip.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_persistence.py tests/test_case_workbench_migration_contract.py tests/test_review_case_persistence_models.py -q`

Run: `cd system/backend; python -m alembic upgrade head; python -m alembic downgrade -1; python -m alembic upgrade head`

Expected: all tests pass and the migration chain has exactly one head.

- [ ] **Step 5: Review and commit.**

Rollback boundary: downgrade removes only new Case Workbench tables; no current `review_cases` table/row is modified or dropped.

### Task 3: Implement Authority Sources, Exact Claims, And Blocker Evaluation

**Files:**

- Create: `system/backend/app/services/case_workbench_repository.py`
- Create: `system/backend/app/services/case_workbench_service.py`
- Create: `system/backend/tests/test_case_workbench_claims.py`
- Create: `system/backend/tests/test_case_workbench_blockers.py`

**Interfaces:**

- Consumes Task 1 schema types and Task 2 models.
- Produces `register_authority_source`, `review_authority_source`, `add_case_claim`, `select_primary_claim`, and `evaluate_case_blockers`.

- [ ] **Step 1: Write RED behavior tests.**

```python
def test_non_whitelisted_url_has_no_tier_and_is_pending_review(service, actor):
    source = run(service.register_authority_source(
        AuthoritySourceCreate(canonical_url="https://example.invalid/source"), actor=actor
    ))
    assert source.authority_tier is None
    assert source.review_status == "pending_review"


def test_same_allowlisted_tier_can_anchor_primary_or_supporting_claims(service, case, actor):
    cctv = allowlist_source(service, "https://news.cctv.com/article", "central_mainstream_media")
    xinhua = allowlist_source(service, "https://www.news.cn/article", "central_mainstream_media")
    primary = run(service.add_case_claim(case.case_id, source_id=cctv.id, claim_role="primary", actor=actor))
    supporting = run(service.add_case_claim(case.case_id, source_id=xinhua.id, claim_role="supporting", actor=actor))
    assert primary.authority_tier_snapshot == supporting.authority_tier_snapshot
    assert {primary.claim_role, supporting.claim_role} == {"primary", "supporting"}


def test_missing_primary_claim_blocks_stance_only(service, case, run):
    blockers = run(service.evaluate_case_blockers(case.case_id, requested_stages=["semantic_enrichment"]))
    assert blockers["stance"] == ["blocked_missing_primary_claim"]
    assert "coordination_discover" not in blockers
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_claims.py tests/test_case_workbench_blockers.py -q`

Expected: missing service functions.

- [ ] **Step 3: Implement transactional source/claim behavior.**

Canonicalize/validate URLs server-side; do not fetch private hosts. Source registration resolves a server-managed allowlist: a non-whitelisted URL is persisted as `authority_tier = null`, `review_status = pending_review`; administrator review can allowlist exactly one organizational tier or reject it. Save an exact quote, code-point span, account, publication timestamp, `authority_tier_snapshot`, `authority_review_status_snapshot`, independent `claim_role`, and 64-character source hash. Claim creation and primary selection require an allowlisted source with a non-null tier, while `select_primary_claim` additionally requires `claim_role = primary`; no organizational tier implies primary or supporting eligibility. Lock the CaseRecord while changing its primary pointer and append one audit event for every mutation.

- [ ] **Step 4: Verify GREEN plus legacy case regressions.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_claims.py tests/test_case_workbench_blockers.py tests/test_review_case_service.py tests/test_review_case_workflows.py -q`

Expected: exact-quote, source class/review status, independent claim-role, blocker scope, and legacy review workflow tests all pass.

- [ ] **Step 5: Review and commit.**

Rollback boundary: no network fetch or model run occurs; the commit is limited to new repository/service behavior and tests.

### Task 4: Extend Analysis Contracts Without Changing Legacy Defaults

**Files:**

- Modify: `system/backend/app/core/analysis/contracts.py`
- Create: `system/backend/app/services/case_workbench_orchestrator.py`
- Create: `system/backend/tests/test_case_workbench_orchestrator.py`
- Modify: `system/backend/tests/test_analysis_run_schema.py`

**Interfaces:**

- Produces `CASE_WORKBENCH_STAGES = ("semantic_enrichment", "coordination_discover", "propagation_analysis", "student", "teacher")`.
- `request_case_analysis(case_id, snapshot_revision_id, actor)` creates CaseAnalysisLink and passes the explicit list to AnalysisRegistry.

- [ ] **Step 1: Write RED tests.**

```python
def test_default_analysis_stages_remain_the_legacy_four():
    assert list(DEFAULT_ANALYSIS_STAGES) == [
        "coordination_discover", "propagation_analysis", "student", "teacher"
    ]


def test_case_orchestration_explicitly_requests_semantic_enrichment(registry, service):
    run(service.request_case_analysis("case_1", "revision_1", actor_id=7))
    assert registry.create_run.await_args.kwargs["requested_stages"][0] == "semantic_enrichment"
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_orchestrator.py tests/test_analysis_run_schema.py -q`

Expected: `semantic_enrichment` is rejected or the orchestrator is absent.

- [ ] **Step 3: Implement allowlist addition and explicit orchestration only.**

Add the stage to `ANALYSIS_STAGE_ALLOWLIST`/normalization and engine registration seam. Do not add it to `DEFAULT_ANALYSIS_STAGES`. If a primary claim is absent, request non-stance semantic work and persist a stance blocker rather than marking the entire run failed.

- [ ] **Step 4: Verify GREEN and old API contracts.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_orchestrator.py tests/test_analysis_run_schema.py tests/test_analysis_v2_api.py tests/test_review_case_orchestrator.py -q`

Expected: explicit case request includes semantic enrichment; old defaults and existing Event Review Case orchestration pass.

- [ ] **Step 5: Review and commit.**

Rollback boundary: reverting removes only opt-in case orchestration; all default callers retain their current four stages.

### Task 5: Build Isolated Auxiliary Semantic Enrichment

**Files:**

- Create: `system/backend/app/core/analysis/semantic_enrichment.py`
- Modify: `system/backend/app/core/analysis/__init__.py`
- Create: `system/backend/tests/test_semantic_enrichment_scope.py`
- Create: `system/backend/tests/test_semantic_enrichment_isolation.py`

**Interfaces:**

- Produces `SemanticScope`, `SemanticEnrichmentEngine`, and a stage payload that contains only `SemanticArtifact` references.
- Inputs are posts/comments grouped separately; outputs include model ID/revision, input hash, scope hash, validation status, and artifact hashes.

- [ ] **Step 1: Write RED tests for scope and non-interference.**

```python
def test_scope_stratifies_posts_and_comments_and_hashes_filters():
    scope = SemanticScope(platforms=["weibo"], community_ids=["c1"], path_ids=["p1"])
    result = build_scoped_documents(posts=[POST], comments=[COMMENT], scope=scope)
    assert result.post_documents and result.comment_documents
    assert result.scope_hash


def test_semantic_artifact_cannot_change_core_risk_projection():
    core = {"coordination": {"risk_score": 0.7}, "review": {"risk_score": 0.4}}
    projected = project_case_semantics(core, semantic_artifacts=[CANDIDATE_ARTIFACT])
    assert projected["coordination"]["risk_score"] == 0.7
    assert projected["review"]["risk_score"] == 0.4
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/backend; python -m pytest tests/test_semantic_enrichment_scope.py tests/test_semantic_enrichment_isolation.py -q`

Expected: missing semantic module/functions.

- [ ] **Step 3: Implement minimum CPU-first stage.**

Create a sequential loader that records exactly the four pinned model IDs/revisions. Implement shared embedding cache, KeyBERT-style MMR, BERTopic-style clustering/c-TF-IDF using existing packages, sentiment, NER, and primary-claim-relative stance. Set all outputs to `candidate_unvalidated`; stance output is a typed blocker when no primary claim exists. Do not import or call core Coordination/Propagation/Review projection writers.

- [ ] **Step 4: Verify GREEN and score isolation.**

Run: `cd system/backend; python -m pytest tests/test_semantic_enrichment_scope.py tests/test_semantic_enrichment_isolation.py tests/test_analysis_review_runtime.py tests/test_event_scoped_analysis.py -q`

Expected: scope/model manifests and score isolation pass; current analysis behavior passes.

- [ ] **Step 5: Review and commit.**

Rollback boundary: the isolated engine is reachable only through the explicit case stage; disable the stage registration to stop it without affecting core runs.

### Task 6: Add Semantic Artifact Corrections, Actions, Feedback, Reports, And Closure Gates

**Files:**

- Modify: `system/backend/app/services/case_workbench_service.py`
- Modify: `system/backend/app/services/case_workbench_repository.py`
- Create: `system/backend/tests/test_case_workbench_artifacts.py`
- Create: `system/backend/tests/test_case_workbench_actions.py`
- Create: `system/backend/tests/test_case_workbench_verdicts.py`
- Create: `system/backend/tests/test_case_workbench_reports.py`

**Interfaces:**

- Produces `append_semantic_correction`, `append_action_operation`, `append_feedback`, `create_case_verdict`, `approve_case_verdict`, `supersede_case_verdict`, `freeze_report_version`, and `close_case`.
- `freeze_report_version(case_id, request, actor)` creates only an ordinary `CaseReportVersion` and unconditionally persists `is_closure = false` with null closure provenance. `close_case(case_id, request, actor) -> CaseCloseResult` is the only service method that can append CaseClosureReview or an `is_closure = true` report, and it returns the closure-review ID/hash plus the server-created closure-report ID/version.

- [ ] **Step 1: Write RED tests.**

```python
def test_correction_keeps_original_prediction(service):
    correction = run(service.append_semantic_correction(ARTIFACT, corrected_value="neutral", actor=ACTOR))
    assert correction.original_prediction_json == ARTIFACT.prediction_json
    assert ARTIFACT.prediction_json == ORIGINAL_PREDICTION


def test_close_rejects_missing_required_action_and_review_note(service):
    with pytest.raises(CaseGateError, match="close_gate_unmet"):
        run(service.close_case("case_1", CaseCloseRequest(closure_review_note=""), actor=ACTOR))


def test_close_case_creates_one_closure_review_report_and_audit_atomically(
    service, session, ready_case_without_reports
):
    case = ready_case_without_reports
    result = run(service.close_case(
        case.case_id,
        CaseCloseRequest(closure_review_note="All required actions were verified."),
        actor=ACTOR,
    ))

    closed = load_case(session, case.case_id)
    reviews = load_case_closure_reviews(session, case.case_id)
    closure_reports = [
        report for report in load_case_reports(session, case.case_id) if report.is_closure
    ]
    assert closed.lifecycle is CaseLifecycle.CLOSED
    assert len(reviews) == len(closure_reports) == 1
    review, closure_report = reviews[0], closure_reports[0]
    assert (result.closure_review_id, result.closure_review_sha256) == (
        review.closure_review_id, review.closure_review_sha256
    )
    assert (result.closure_report_id, result.closure_report_version) == (
        closure_report.report_id, closure_report.version
    )
    assert closure_report.closure_review_id == review.closure_review_id
    assert closure_report.closure_review_sha256 == review.closure_review_sha256
    assert closure_report.target_lifecycle is CaseLifecycle.CLOSED
    manifest = load_frozen_report_manifest(closure_report)
    assert manifest["closure_review"]["note_sha256"] == review.note_sha256
    assert manifest["closure_review"]["canonical_verdict_payload_sha256"] == review.canonical_verdict_payload_sha256
    assert manifest["closure_review"]["action_state_summary_sha256"] == review.action_state_summary_sha256
    assert {"snapshot_hashes", "run_hashes", "model_hashes", "content_hashes"} <= set(manifest["provenance"])
    closed_event = next(event for event in load_case_audit_events(session, case.case_id) if event.event_type == "case_closed")
    assert closed_event.payload["closure_report_id"] == closure_report.report_id
    assert closed_event.payload["closure_review_sha256"] == review.closure_review_sha256


def test_close_case_rolls_back_all_effects_when_closure_report_freeze_fails(
    service, session, ready_case_without_reports, monkeypatch
):
    case = ready_case_without_reports
    before_audit = list(load_case_audit_events(session, case.case_id))

    async def fail_freeze(*args, **kwargs):
        raise ReportFreezeError("forced report freeze failure")

    monkeypatch.setattr(service, "_freeze_closure_report_locked", fail_freeze)
    with pytest.raises(ReportFreezeError, match="forced report freeze failure"):
        run(service.close_case(
            case.case_id,
            CaseCloseRequest(closure_review_note="All required actions were verified."),
            actor=ACTOR,
        ))

    assert load_case(session, case.case_id).lifecycle is CaseLifecycle.READY_TO_CLOSE
    assert load_case_closure_reviews(session, case.case_id) == []
    assert [report for report in load_case_reports(session, case.case_id) if report.is_closure] == []
    assert load_case_audit_events(session, case.case_id) == before_audit


def test_approval_and_supersession_append_immutable_case_verdict_versions(service, case, actor):
    proposal = run(service.create_case_verdict(case.case_id, VALID_VERDICT, actor=actor))
    approved = run(service.approve_case_verdict(case.case_id, proposal.id, actor=actor))
    successor = run(service.supersede_case_verdict(case.case_id, approved.id, REPLACEMENT_VERDICT, actor=actor))
    assert approved.payload_json == proposal.payload_json
    assert successor.supersedes_verdict_id == approved.id
    assert read_case(case.case_id).canonical_verdict_id == successor.id
    assert read_verdict(approved.id).payload_json == proposal.payload_json
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_artifacts.py tests/test_case_workbench_actions.py tests/test_case_workbench_verdicts.py tests/test_case_workbench_reports.py -q`

Expected: methods/exceptions absent.

- [ ] **Step 3: Implement append-only operations and frozen report manifest.**

Derive action state from operations. Require waiver rationale. Bind feedback to case/snapshot/run/CaseVerdictVersion/artifact ownership. `create_case_verdict` appends an immutable proposed row. `approve_case_verdict` locks CaseRecord, appends a separate immutable approved row derived from the proposal, advances only `canonical_verdict_id`, performs the lifecycle transition, and appends audit. `supersede_case_verdict` appends an approved successor with `supersedes_verdict_id`, advances the pointer in the same transaction, and never updates/deletes a prior verdict row or writes to a legacy review aggregate. `freeze_report_version` accepts only `CaseReportFreezeRequest`, unconditionally writes an ordinary report with null closure provenance, and is never used to mark a report as closure. Freeze each report payload with current CaseVerdictVersion ID/version/supersession/payload hash plus case/snapshot/run/model/content-hash provenance, sanitized web/print content hashes, and PDF hash. `close_case` queries the new current approved CaseVerdictVersion rather than `ReviewDecision`/`ReviewVerdictVersion`, then uses one locked transaction to validate required actions and the non-empty note, persist/hash CaseClosureReview, call the server-only `_freeze_closure_report_locked`, advance lifecycle, and append a `case_closed` audit event containing the review ID/hash and report ID/version. The closure manifest must contain `closure_review` (`closure_review_id`, `closure_review_sha256`, sanitized note/note hash, canonical verdict ID/hash, action summary/hash, target lifecycle) and `provenance` (`snapshot_hashes`, `run_hashes`, `model_hashes`, `content_hashes`). Do not call the public ordinary-report path from `close_case`. Any exception from persisting the review, rendering/freezing the report, creating hashes, or appending audit escapes the single unit of work so no closure-review/report/lifecycle/blocker/audit write survives; add equivalent injected-failure checks for `_append_closure_review_locked`, `_hash_closure_report_locked`, and `_append_close_audit_locked` in addition to the direct report-freeze test above.

- [ ] **Step 4: Verify GREEN.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_artifacts.py tests/test_case_workbench_actions.py tests/test_case_workbench_verdicts.py tests/test_case_workbench_reports.py tests/test_review_case_feedback.py -q`

Expected: correction and CaseVerdictVersion immutability, pointer-only verdict progression, action derivation, ordinary-versus-closure report ownership, atomic close/rollback behavior, closure-result identity/version, and existing review feedback behavior pass.

- [ ] **Step 5: Review and commit.**

Rollback boundary: report/action/feedback rows are append-only. Revert application access only; do not delete persisted audit/history data.

### Task 7: Expose Authenticated Case And Authority APIs

**Files:**

- Create: `system/backend/app/api/v2/cases.py`
- Create: `system/backend/app/api/v2/authority_sources.py`
- Modify: `system/backend/app/api/v2/router.py`
- Create: `system/backend/tests/test_case_workbench_v2_api.py`
- Create: `system/backend/tests/test_authority_sources_v2_api.py`

**Interfaces:**

- Implements the endpoint matrix in the approved design, including authority-source review and `/api/v2/cases/{case_id}/claims`, `/verdicts`, `/runs`, `/artifacts`, `/actions`, `/feedback`, ordinary-only `/reports`, and transactional `/close` returning closure-report identity/version.

- [ ] **Step 1: Write RED API tests.**

```python
def test_case_claim_endpoint_rejects_unknown_fields(client, token):
    response = client.post(
        "/api/v2/cases/case_1/claims",
        headers={"Authorization": f"Bearer {token}"},
        json={**VALID_CLAIM, "run_id": "not-accepted"},
    )
    assert response.status_code == 422


def test_close_returns_structured_gate_details(client, token):
    response = client.post("/api/v2/cases/case_1/close", headers=AUTH, json={"closure_review_note": "checked"})
    assert response.status_code == 409
    assert response.json()["code"] == "close_gate_unmet"


@pytest.mark.parametrize("field, value", [
    ("closure_flag", True),
    ("is_closure", True),
    ("closure_review_note", "checked"),
    ("closure_review_id", "closure_1"),
    ("closure_review_sha256", "0" * 64),
    ("target_lifecycle", "closed"),
])
def test_ordinary_report_endpoint_rejects_caller_closure_fields(client, ready_case_without_reports, field, value):
    response = client.post(
        f"/api/v2/cases/{ready_case_without_reports.case_id}/reports",
        headers=AUTH,
        json={field: value},
    )
    assert response.status_code == 422
    reports = client.get(
        f"/api/v2/cases/{ready_case_without_reports.case_id}/reports", headers=AUTH
    ).json()["data"]["items"]
    assert reports == []


def test_close_endpoint_creates_and_returns_the_only_closure_report(client, ready_case_without_reports):
    case_id = ready_case_without_reports.case_id
    assert client.get(f"/api/v2/cases/{case_id}/reports", headers=AUTH).json()["data"]["items"] == []

    response = client.post(
        f"/api/v2/cases/{case_id}/close",
        headers=AUTH,
        json={"closure_review_note": "All required actions were verified."},
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["case"]["lifecycle"] == "closed"
    assert result["closure_review_id"]
    assert result["closure_review_sha256"]
    assert result["closure_report_id"]
    assert result["closure_report_version"] == 1
    reports = client.get(f"/api/v2/cases/{case_id}/reports", headers=AUTH).json()["data"]["items"]
    closure_reports = [report for report in reports if report["is_closure"]]
    assert len(closure_reports) == 1
    assert closure_reports[0]["report_id"] == result["closure_report_id"]
    assert closure_reports[0]["version"] == result["closure_report_version"]


def test_verdict_approval_and_supersession_are_append_only_case_operations(client, token):
    proposal = client.post("/api/v2/cases/case_1/verdicts", headers=AUTH, json=VALID_VERDICT)
    approved = client.post(f"/api/v2/cases/case_1/verdicts/{proposal.json()['id']}/approve", headers=AUTH)
    successor = client.post(f"/api/v2/cases/case_1/verdicts/{approved.json()['id']}/supersede", headers=AUTH, json=REPLACEMENT_VERDICT)
    assert successor.status_code == 201
    assert successor.json()["supersedes_verdict_id"] == approved.json()["id"]
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_v2_api.py tests/test_authority_sources_v2_api.py -q`

Expected: 404 routes or missing imports.

- [ ] **Step 3: Implement thin auth-bound routers.**

Use shared `get_current_user`, construct one service per request, return existing API envelope shape, and forbid unknown request fields. Authority-source registration must not accept caller-controlled organizational tier/review state; an administrator-only review endpoint sets `allowlisted` plus one tier or `rejected` plus no tier. Expose create, approve, supersede, and read-only CaseVerdictVersion endpoints that only append new rows and move the CaseRecord pointer transactionally. Route `POST /reports` only to `freeze_report_version` with the ordinary-only request contract, and route `POST /close` only to `close_case`; the close response must expose `closure_review_id`, `closure_review_sha256`, `closure_report_id`, and `closure_report_version` from the committed transaction. Map domain errors to stable 409/422 responses. Mount both routers in `api_router` without changing the `review-cases` prefix or tag.

- [ ] **Step 4: Verify GREEN and compatibility.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_v2_api.py tests/test_authority_sources_v2_api.py tests/test_review_case_v2_api.py tests/test_analysis_v2_api.py -q`

Expected: new auth/error contracts pass and prior v2 routes retain behavior.

- [ ] **Step 5: Review and commit.**

Rollback boundary: router registrations are additive. Remove the two mounts to disable the new surface without changing `/api/v2/review-cases`.

### Task 8: Seed The First Case And Preserve The Separate Twitter Benchmark

**Files:**

- Create: `system/backend/tests/fixtures/cases/trump_visit_2026_05_21.json`
- Create: `system/backend/tests/test_case_workbench_seed_manifest.py`
- Modify: `doc/research/case-workbench/twitter-benchmark-manifest.json`
- Modify: `doc/research/case-workbench/source-metadata.json`

**Interfaces:**

- Seed fixture has no invented Douyin metrics and explicitly contains `collection_status: "partial_collection"`.
- Seed claim templates preserve the exact quotes, separate intended organizational class from independent claim role, and remain `pending_review` with no saved AuthoritySource tier until article capture and administrator review.
- Twitter manifest remains metadata/stats/hash only.

- [ ] **Step 1: Write RED fixture tests.**

```python
def test_seed_manifest_preserves_known_weibo_counts_and_partial_douyin_status():
    manifest = load_json(FIXTURE)
    assert manifest["event_id"] == "trump_visit_2026_05_21"
    assert manifest["weibo"]["unique_main_posts"] == 74
    assert manifest["douyin"]["collection_status"] == "partial_collection"
    assert "unique_main_posts" not in manifest["douyin"]


def test_seed_claim_templates_keep_authority_class_distinct_from_claim_role():
    templates = manifest["claim_templates"]
    assert {item["expected_authority_tier"] for item in templates} == {"central_mainstream_media"}
    assert {item["claim_role"] for item in templates} == {"primary", "supporting"}
    assert {item["review_status"] for item in templates} == {"pending_review"}
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_seed_manifest.py -q`

Expected: fixture is missing.

- [ ] **Step 3: Add minimal fixture and metadata-only benchmark references.**

Use half-open Beijing-derived windows and exact primary/supporting quote text but leave canonical source URL/account/published-at unset until authoritative capture. Represent CCTV and Xinhua as `expected_authority_tier: "central_mainstream_media"` with independent `claim_role` values `primary` and `supporting`; the actual AuthoritySource remains `authority_tier = null`, `review_status = pending_review` until administrator allowlisting. Do not copy the Twitter CSV, its rows, or converted text into any repository file.

- [ ] **Step 4: Verify GREEN.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_seed_manifest.py -q`

Run: `git status --short -- doc/research/case-workbench`

Expected: fixture contract passes; no CSV or full benchmark Markdown appears in the diff.

- [ ] **Step 5: Review and commit.**

Rollback boundary: fixture/research metadata is additive and contains no operational collection data.

### Task 9: Add Parallel Typed Frontend API And Route

**Files:**

- Create: `system/frontend/src/types/caseWorkbench.ts`
- Create: `system/frontend/src/api/caseWorkbench.ts`
- Modify: `system/frontend/src/router/index.ts`
- Create: `system/frontend/tests/case-workbench.spec.mjs`

**Interfaces:**

- Produces typed functions `getCaseWorkbench`, `listCaseWorkbench`, `createCaseClaim`, `requestCaseRun`, `appendCaseActionOperation`, ordinary-only `freezeCaseReport`, and `closeCase`. `closeCase` returns `CaseCloseResult` with closure-review ID/hash plus server-created closure-report ID/version; `freezeCaseReport` accepts no closure fields.
- Adds `/case-workbench` route named `CaseWorkbench`; keeps `/risk` unchanged.

- [ ] **Step 1: Write RED source-contract tests.**

```js
test('case workbench adds a parallel authenticated route without replacing risk', async () => {
  const routerSource = await readFile('src/router/index.ts', 'utf8')
  assert.match(routerSource, /path: 'case-workbench'/)
  assert.match(routerSource, /path: 'risk'/)
})
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/frontend; npm test -- case-workbench.spec.mjs`

Expected: assertion fails because the route/API module is absent.

- [ ] **Step 3: Implement narrow TypeScript contracts and route only.**

Use `/api/v2/cases` base client, `encodeURIComponent` for IDs, explicit request/response types, and no broad `any`. Model `CaseReportFreezeRequest` without closure fields and `CaseCloseResult` with `closure_review_id`, `closure_review_sha256`, `closure_report_id`, and `closure_report_version`. Add the authenticated route under `BasicLayout`; do not alter `Risk` route metadata or component.

- [ ] **Step 4: Verify GREEN and build.**

Run: `cd system/frontend; npm test -- case-workbench.spec.mjs`

Run: `cd system/frontend; npm run build`

Expected: route contract passes and the TypeScript/Vite build succeeds.

- [ ] **Step 5: Review and commit.**

Rollback boundary: delete the isolated route/API/type files and one route entry; `/risk` remains unchanged.

### Task 10: Implement The Dense Five-Tab Case Workbench View

**Files:**

- Create: `system/frontend/src/views/case-workbench/index.vue`
- Modify: `system/frontend/tests/case-workbench.spec.mjs`

**Interfaces:**

- Uses Task 9 types/API and renders persistent case context plus tabs `概览`, `证据矩阵`, `图谱`, `处置`, `报告`.

- [ ] **Step 1: Write RED UI source-contract tests.**

```js
test('workbench keeps lifecycle, primary claim, blockers, and closed loop visible', async () => {
  const source = await readFile('src/views/case-workbench/index.vue', 'utf8')
  for (const text of ['概览', '证据矩阵', '图谱', '处置', '报告', '事件', '反馈']) {
    assert.ok(source.includes(text))
  }
  assert.match(source, /blocked_missing_primary_claim/)
})


test('close control uses closeCase and shows the committed closure report identity', async () => {
  const source = await readFile('src/views/case-workbench/index.vue', 'utf8')
  assert.match(source, /async function submitClose\(\)[\s\S]*await closeCase\([\s\S]*closure_review_note/)
  assert.match(source, /closure_report_id/)
  assert.match(source, /closure_report_version/)
  assert.doesNotMatch(source, /async function submitClose\(\)[\s\S]*freezeCaseReport\(/)
})
```

- [ ] **Step 2: Verify RED.**

Run: `cd system/frontend; npm test -- case-workbench.spec.mjs`

Expected: view file is absent.

- [ ] **Step 3: Implement the route-level UI.**

Use one unframed page shell, a persistent compact header, stable tab dimensions, loading/empty/error states, and accessible controls. Keep exact claims/source URLs visible in the evidence matrix. Mark semantic values as candidate/unvalidated, keep core graph and semantic graph material visually distinct, and expose closing only when API-provided gates pass plus the note is non-empty. Implement an `async function submitClose()` handler that calls `closeCase` exactly once; it never calls `freezeCaseReport` to create or mark a closure report, and it presents the committed `closure_report_id`/`closure_report_version` returned by `POST /close`. Do not create a nested-card dashboard or a duplicate specialist analytics page.

- [ ] **Step 4: Verify GREEN and responsive build.**

Run: `cd system/frontend; npm test -- case-workbench.spec.mjs`

Run: `cd system/frontend; npm run build`

Expected: five-tab source contract passes and production build remains clean.

- [ ] **Step 5: Review and commit.**

Rollback boundary: remove only the new case-workbench view/route/API; existing case and specialist pages stay intact.

### Task 11: Full Integration, Documentation Sync, And Regression Gate

**Files:**

- Modify: `UBIQUITOUS_LANGUAGE.md`
- Modify: `doc/engineering/system-governance.md`
- Modify: `doc/engineering/development-roadmap.md`
- Modify: `doc/engineering/development-log.md`
- Modify: `README.md` or `system/README.md`
- Create: `docs/adr/0015-case-workbench-boundary.md`
- Modify: `docs/superpowers/specs/2026-08-10-case-workbench-design.md`
- Create: `system/backend/tests/test_case_workbench_acceptance.py`

**Interfaces:**

- Documents only facts that passed the integration gate. The final ADR supersedes the relevant portions of ADR 0007 explicitly and preserves `/review-cases` compatibility status.

- [ ] **Step 1: Write a failing acceptance test before documentation claims.**

```python
def test_case_workbench_end_to_end_preserves_legacy_default_and_closure_history(client, actor):
    case = create_seed_case(client, actor)
    assert request_legacy_default_run(client, actor).requested_stages == LEGACY_FOUR
    assert request_case_run(client, case, actor).requested_stages[0] == "semantic_enrichment"
    proposal = create_case_verdict(client, case, actor)
    approved = approve_case_verdict(client, case, proposal, actor)
    successor = supersede_case_verdict(client, case, approved, actor)
    assert get_case(client, case).canonical_verdict_id == successor.id
    assert read_case_verdict(client, approved.id).payload_hash == approved.payload_hash
    assert no_legacy_review_case_verdict_write_occurred(case)
    case_id = case.case_id
    assert get_case(client, case_id).lifecycle == "ready_to_close"
    reports_before_close = client.get(
        f"/api/v2/cases/{case_id}/reports", headers=AUTH
    ).json()["data"]["items"]
    assert reports_before_close == []
    close_response = client.post(
        f"/api/v2/cases/{case_id}/close",
        headers=AUTH,
        json={"closure_review_note": "All required actions were verified."},
    )
    assert close_response.status_code == 200
    close_result = close_response.json()["data"]
    assert close_result["case"]["lifecycle"] == "closed"
    assert close_result["closure_review_id"]
    assert close_result["closure_review_sha256"]
    assert close_result["closure_report_id"]
    assert close_result["closure_report_version"] == 1
    reports_after_close = client.get(
        f"/api/v2/cases/{case_id}/reports", headers=AUTH
    ).json()["data"]["items"]
    closure_reports = [report for report in reports_after_close if report["is_closure"]]
    assert len(closure_reports) == 1
    assert closure_reports[0]["report_id"] == close_result["closure_report_id"]
    assert closure_reports[0]["version"] == close_result["closure_report_version"]
```

- [ ] **Step 2: Verify RED against the incomplete end-to-end feature.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_acceptance.py -q`

Expected: the test is initially absent or fails until prior tasks are integrated.

- [ ] **Step 3: Finish only integration gaps found by the acceptance test.**

Do not refactor unrelated areas. Resolve compatibility/migration/serialization defects, then update documentation with the implemented paths, test evidence, remaining model-evaluation gaps, and rollback guidance.

- [ ] **Step 4: Run final validation in order.**

Run: `cd system/backend; python -m pytest tests/test_case_workbench_*.py tests/test_semantic_enrichment_*.py tests/test_analysis_run_schema.py tests/test_review_case_*.py -q`

Run: `cd system/backend; python -m alembic upgrade head; python -m alembic downgrade -1; python -m alembic upgrade head`

Run: `cd system/frontend; npm test`

Run: `cd system/frontend; npm run build`

Run: `git diff --check`

Expected: all selected backend/frontend tests and build pass, migration round trip succeeds, and no whitespace errors appear.

- [ ] **Step 5: Final review and Lore commit.**

Rollback boundary: retain frozen reports/audit/history; rollback through the documented migration only when removal of the Case Workbench is approved. The commit message must include Scope-risk, Reversibility, Directive, Tested, and Not-tested trailers.

## Required Final Validation

- Verify `git status --short` contains only intentionally changed files; explicitly confirm the two propagation research files are still user-owned/unmodified by this work and unstaged.
- Confirm `git diff --check` passes and `git diff --name-only` has no Twitter CSV/full Markdown conversion.
- Confirm the analysis default test still expects exactly four legacy stages and case orchestration explicitly requests the fifth semantic stage.
- Confirm a missing primary claim blocks stance only, semantic corrections preserve originals, and core risk values do not change when semantic artifacts/corrections are present.
- Confirm the AuthorityTier enum has exactly the three organizational values, non-whitelisted sources persist as `authority_tier = null` plus `pending_review`, ClaimRole remains independent, exact-quote fields are present, and the source review endpoint is administrator-only.
- Confirm CaseVerdictVersion proposal/approval/supersession rows are append-only, only the CaseRecord pointer advances, no legacy review aggregate is dual-written, closure queries the approved current version, and frozen reports retain verdict version/hash/provenance.
- Confirm Task 6/7/10/11 exercise `close_case`/`POST /close` as the exclusive closure-report creator, ordinary `/reports` rejects caller closure fields, close returns the committed closure-report ID/version, failure injection rolls back every close effect, and no retired helper can combine action completion with closure.
- Confirm Task 2's execution-time Alembic preflight sees exactly one head before generating `<generated_revision>` and again after generation; do not reuse Task 01's observed head as a fixed parent.
- Run the focused tests above, then full backend suite, frontend test suite, frontend production build, and migration round trip before merge.
- Use a fresh reviewer for each task and one branch-wide reviewer after Task 11. Treat any Critical or Important finding as a required fix/re-review cycle.
