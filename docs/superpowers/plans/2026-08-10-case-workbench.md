# Case Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable Case Workbench that turns immutable event evidence and analysis runs into governed claims, actions, feedback, closeout, semantic artifacts, and frozen reports.

**Architecture:** Add a persistent Case aggregate beside the existing analysis registry, keep immutable snapshots and Analysis Runs independently addressable, and project append-only Case operations into a dense `/api/v2` and Vue workbench. Add `semantic_enrichment` as an explicit opt-in Analysis Stage used by Case orchestration while preserving the existing four-stage default and isolating semantic outputs from core scores.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2 async, Alembic, MySQL, MongoDB, existing REST/SSE helpers, sentence-transformers, Transformers, scikit-learn, one bounded `jieba` dependency, Vue 3, TypeScript, Vite 6, Ant Design Vue 4, and headless Chromium PDF printing.

## Global Constraints

- Work from `release-0.2` lineage in the isolated feature worktree; never implement on `main`.
- Product code stays under `system/`; do not modify `MediaCrawler-main`, `NewsCrawler-main`, or `CooRTweet-master`.
- Use the lifecycle `event -> evidence -> Coordination Discover -> Propagation Analysis -> Risk Review -> governance action -> feedback` and display `事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈`.
- Case states are exactly `draft`, `collecting`, `evidence_ready`, `analyzing`, `awaiting_review`, `actioning`, `ready_to_close`, and `closed`.
- Return blockers separately; never encode a blocker as a lifecycle state.
- Authority Source tiers are exactly `government_official`, `central_mainstream_original`, and `provincial_official_media`; unregistered URLs remain `pending_review`.
- Preserve verbatim claim excerpt, character span, URL, account, publication time, tier, source content hash, and excerpt hash.
- Each Case has at most one approved Primary Claim pointer and zero or more approved Supplementary Claims.
- Missing Primary Claim permits Coordination Discover, Propagation Analysis, sentiment, topics, keywords, entities, and near-duplicate analysis; stance returns exact code `blocked_missing_primary_claim`.
- Closure requires an approved Canonical Verdict, all required Case Actions completed or explicitly waived, and a submitted Closeout Review.
- Student Review and Teacher Review remain advisory. One analyst may perform all roles in the first release, but accepted operations are append-only.
- Keep `DEFAULT_ANALYSIS_STAGES` exactly `("coordination_discover", "propagation_analysis", "student", "teacher")`; only Case orchestration adds `semantic_enrichment` by default.
- Semantic artifacts never change Coordination Discover, Propagation Analysis, or Risk Review scores.
- Pin models exactly to `BAAI/bge-small-zh-v1.5@7999e1d`, `lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110`, `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92`, and `shibing624/bert4ner-base-chinese@5d660ed`.
- Model-backed semantic artifacts stay `candidate_unvalidated` until a local evaluation manifest approves the exact model hash and configuration.
- Load semantic models sequentially, retry GPU allocation failure once on CPU, and persist version, aggregate artifact SHA-256, device, and degradation reason.
- Analyze posts and comments separately, then cross-analyze by time, platform, Coordination Community, and Propagation Tree/path.
- Use local KeyBERT-style Maximal Marginal Relevance, BERTopic-style clustering, and class-based TF-IDF; add no dependency other than `jieba>=0.42.1,<0.43.0`.
- A successful report version is a frozen HTML/PDF pair containing Case, snapshot, run, model-version, and content-hash provenance.
- Main Case id is `trump_visit_2026_05_21`; never fabricate a Douyin/XHS source or combine unrelated evidence.
- Keep the Twitter CSV separate and commit only its schema, statistics, byte size, and SHA-256 manifest, never its full Markdown conversion.
- Python modules are shallow, one concept per file, use absolute imports, and define explicit `__all__` for public surfaces.
- Every task follows RED, GREEN, self-review, Documentation Sync where applicable, and one independently reviewable Lore commit.

---

### Task 1: Governance, Design, Plan, And Language Baseline

**Files:**
- Create: `docs/superpowers/specs/2026-08-10-case-workbench-design.md`
- Create: `docs/superpowers/plans/2026-08-10-case-workbench.md`
- Modify: `UBIQUITOUS_LANGUAGE.md`
- Test: `system/backend/tests/test_governance_docs.py`
- Test: `system/backend/tests/test_system_naming_governance.py`

**Interfaces:**
- Consumes: Existing canonical method names, package boundaries, and documentation governance tests.
- Produces: Approved Case Workbench design, this task-by-task implementation contract, and canonical Case vocabulary used by Tasks 2-10.

- [ ] **Step 1: Run the existing regression tests and observe RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_governance_docs.py::test_canonical_governance_sources_use_method_names_not_numbered_shorthand tests/test_system_naming_governance.py::test_source_and_documentation_do_not_use_numbered_shorthand -q
```

Expected: both tests fail on the existing Propagation Monitoring alias in `UBIQUITOUS_LANGUAGE.md`; no other file is reported.

- [ ] **Step 2: Write the approved design and executable implementation plan**

The design must contain the exact lifecycle, eight states, source tiers, claim rules, missing-primary behavior, semantic stage compatibility, pinned models, report contract, main Case facts, and isolated Twitter manifest facts from Global Constraints. This plan must contain all ten tasks, exact paths, owned interfaces, test commands, expected results, and Lore commit messages.

- [ ] **Step 3: Extend the canonical glossary and remove the stale alias**

Add definitions and relationships for Case, Case Workbench, Case State, Case Blocker, Authority Source, Source Tier, Case Claim, Primary Claim, Supplementary Claim, Semantic Artifact, Semantic Correction, Case Action, Closeout Review, Case Report Version, Audit Event, Partial Collection Acknowledgement, and Platform Gap. Explicitly flag the five approved ambiguities and retain the formal capability names.

- [ ] **Step 4: Verify GREEN and the complete governance selection**

Run:

```powershell
cd system\backend
uv run pytest tests/test_governance_docs.py::test_canonical_governance_sources_use_method_names_not_numbered_shorthand tests/test_system_naming_governance.py::test_source_and_documentation_do_not_use_numbered_shorthand -q
uv run pytest tests/test_governance_docs.py tests/test_system_naming_governance.py -q
```

Expected: the first command reports `2 passed`; the second command reports all selected governance tests passed with no failures.

- [ ] **Step 5: Scan the plan and review the scoped diff**

Run:

```powershell
$planPath = '..\..\docs\superpowers\plans\2026-08-10-case-workbench.md'
$patterns = @(('T' + 'BD'), ('T' + 'ODO'), ('implement ' + 'later'))
Select-String -Path $planPath -Pattern $patterns
git diff --check
git diff -- UBIQUITOUS_LANGUAGE.md docs/superpowers/specs/2026-08-10-case-workbench-design.md docs/superpowers/plans/2026-08-10-case-workbench.md
```

Expected: the placeholder scan and `git diff --check` produce no output; every interface referenced in a later task appears in that task's `Produces` list or the interface ownership matrix at the end of this plan.

- [ ] **Step 6: Commit only the three tracked documentation files**

```powershell
git add -- UBIQUITOUS_LANGUAGE.md docs/superpowers/specs/2026-08-10-case-workbench-design.md docs/superpowers/plans/2026-08-10-case-workbench.md
git commit -m "Make the Case boundary and terminology durable before implementation" -m "Record the approved investigative aggregate, execution sequence, and canonical language so subsequent implementation tasks share one auditable contract." -m "Constraint: Preserve the existing four-stage Analysis Run default and formal capability names" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: Targeted and complete governance documentation pytest selections" -m "Not-tested: Production runtime and frontend behavior because this task changes documentation only"
```

Expected: one commit containing exactly the three paths listed above.

---

### Task 2: Persisted Structured Search And MarkItDown Research Archive

**Files:**
- Create: `system/backend/app/schemas/case_research.py`
- Modify: `system/backend/app/schemas/__init__.py`
- Create: `system/backend/app/services/case_research_archive.py`
- Modify: `system/backend/app/services/__init__.py`
- Create: `system/backend/tests/test_case_research_archive.py`
- Create: `doc/research/case-workbench/README.md`
- Create: `doc/research/case-workbench/structured-search-records.jsonl`
- Create: `doc/research/case-workbench/archive-manifest.json`
- Create after verification: `doc/research/case-workbench/sources/cctv-news-primary-claim.md`
- Create after verification: `doc/research/case-workbench/sources/cctv-news-primary-claim.meta.json`
- Create after verification: `doc/research/case-workbench/sources/xinhua-supplementary-claim.md`
- Create after verification: `doc/research/case-workbench/sources/xinhua-supplementary-claim.meta.json`
- Create exactly one second-platform outcome: `doc/research/case-workbench/sources/second-platform-evidence.md` plus `.meta.json`, or `doc/research/case-workbench/platform-gap.json`

**Interfaces:**
- Consumes: `StructuredSearchRecord` JSONL entries written from a structured search provider and MarkItDown `<slug>.md` plus `<slug>.meta.json` output.
- Produces in `app.schemas.case_research`:

```python
class StructuredSearchHit(BaseModel):
    rank: int
    title: str
    url: AnyHttpUrl
    source_account: str | None
    published_at: datetime | None
    snippet: str
    disposition: Literal["candidate", "verified", "rejected"]
    disposition_reason: str | None

class StructuredSearchRecord(BaseModel):
    schema_version: Literal["cogguard.case_research.search.v1"]
    search_id: str
    purpose: Literal["primary_claim", "supplementary_claim", "second_platform"]
    query: str
    provider: str
    searched_at: datetime
    filters: dict[str, str]
    hits: list[StructuredSearchHit]

class ResearchArchiveEntry(BaseModel):
    archive_id: str
    purpose: Literal["primary_claim", "supplementary_claim", "second_platform"]
    source_url: AnyHttpUrl
    source_path: str
    markdown_path: str
    metadata_path: str
    source_sha256: str
    markdown_sha256: str
    converter: Literal["Microsoft MarkItDown"]
    converter_version: str
    verified_excerpt: str
    verified_span_start: int
    verified_span_end: int
    archived_at: datetime

def load_structured_search_records(path: Path) -> tuple[StructuredSearchRecord, ...]: ...
def load_research_archive_manifest(path: Path) -> tuple[ResearchArchiveEntry, ...]: ...
def verify_research_archive(root: Path, *, source_root: Path | None = None) -> tuple[ResearchArchiveEntry, ...]: ...
```

- [ ] **Step 1: Write archive contract tests**

Create tests that validate JSONL records with Pydantic, reject a verified hit without publication/source provenance, recompute every Markdown SHA-256, recompute each original-source SHA-256 when `source_root` is supplied, assert the exact excerpt slice, require both CCTV News and Xinhua entries, and accept the second-platform outcome only when it is either a verified Douyin/XHS archive or an explicit Platform Gap record.

```python
def test_archive_requires_verified_claim_sources_and_explicit_platform_outcome(tmp_path: Path):
    entries = verify_research_archive(tmp_path)
    assert {entry.purpose for entry in entries} >= {"primary_claim", "supplementary_claim"}
    assert all(entry.verified_excerpt == read_nfc(entry.markdown_path)[entry.verified_span_start:entry.verified_span_end] for entry in entries)
```

- [ ] **Step 2: Run RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_research_archive.py -q
```

Expected: collection fails because `app.schemas.case_research` and `app.services.case_research_archive` do not exist.

- [ ] **Step 3: Implement the schemas, loader, and archive protocol**

Use absolute imports and export every public symbol through module `__all__`, `app.schemas.__all__`, and `app.services.__all__`. `verify_research_archive` must normalize text with NFC, verify 64-hex SHA-256 values, reject Markdown/metadata paths outside `root`, validate `[start, end)` character spans, and never execute converted content. When `source_root` is provided, resolve `source_path` only beneath that ignored staging root and recompute `source_sha256`; when it is omitted, validate the committed source digest and converter metadata without pretending the untracked original bytes are present.

Document an append-only search record protocol in `README.md`: record every query and returned hit before source selection, record why rejected hits were rejected, preserve downloaded originals outside Git, and commit only converted Markdown plus provenance metadata. A hostname or title match alone is not authoritative-source approval.

- [ ] **Step 4: Search, convert, and inspect the verified sources**

Persist actual provider output in `structured-search-records.jsonl`. Download only selected source files into the ignored staging directory `system/backend/.case-research-input/`. Convert each selected file with the installed MarkItDown wrapper:

```powershell
$converter = Join-Path $env:USERPROFILE '.codex\skills\markitdown\scripts\convert_literature.py'
python $converter '.case-research-input\cctv-news-primary-claim.html' --out-dir '..\..\doc\research\case-workbench\sources'
python $converter '.case-research-input\xinhua-supplementary-claim.html' --out-dir '..\..\doc\research\case-workbench\sources'
```

Rename the generated pairs to the exact paths in this task, inspect both Markdown and metadata files, and build `archive-manifest.json` with recomputed hashes and exact spans. Search Douyin and XHS for the same event and window. Convert a verified same-event source to the exact second-platform path; otherwise write `platform-gap.json` with searched queries, providers, time, rejection reasons, and `status: "unverified_second_platform"`.

- [ ] **Step 5: Run GREEN and archive-integrity checks**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_research_archive.py -q
uv run python -c "from pathlib import Path; from app.services.case_research_archive import verify_research_archive; print(len(verify_research_archive(Path('../../doc/research/case-workbench'))))"
uv run python -c "from pathlib import Path; from app.services.case_research_archive import verify_research_archive; verify_research_archive(Path('../../doc/research/case-workbench'), source_root=Path('.case-research-input'))"
```

Expected: all archive tests pass; committed-archive verification prints at least `2`, or `3` when a verified second-platform source exists; staging verification recomputes every selected original-source digest and exits zero.

- [ ] **Step 6: Commit the reviewed research boundary**

```powershell
git add -- system/backend/app/schemas/case_research.py system/backend/app/schemas/__init__.py system/backend/app/services/case_research_archive.py system/backend/app/services/__init__.py system/backend/tests/test_case_research_archive.py doc/research/case-workbench
git commit -m "Preserve source research before Case evidence is approved" -m "Persist structured search decisions and MarkItDown provenance so claim extraction starts from reviewable source bytes and exact excerpts." -m "Constraint: Unverified second-platform content must remain an explicit Platform Gap" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: uv run pytest tests/test_case_research_archive.py -q" -m "Not-tested: Source availability after the recorded archive timestamp"
```

---

### Task 3: Case Persistence, Schemas, Repositories, And Migration

**Files:**
- Create: `system/backend/app/models/case.py`
- Create: `system/backend/app/models/case_snapshot.py`
- Create: `system/backend/app/models/case_run.py`
- Create: `system/backend/app/models/authority_source.py`
- Create: `system/backend/app/models/case_claim.py`
- Create: `system/backend/app/models/case_action.py`
- Create: `system/backend/app/models/case_report.py`
- Create: `system/backend/app/models/case_audit.py`
- Create: `system/backend/app/models/case_idempotency.py`
- Modify: `system/backend/app/models/__init__.py`
- Create: `system/backend/app/schemas/case.py`
- Create: `system/backend/app/schemas/authority_source.py`
- Modify: `system/backend/app/schemas/__init__.py`
- Create: `system/backend/app/services/case_repository.py`
- Create: `system/backend/app/services/authority_source_repository.py`
- Modify: `system/backend/app/services/__init__.py`
- Create: `system/backend/alembic/versions/4c6a9d2e7f10_add_case_workbench_core.py`
- Create: `system/backend/tests/test_case_models.py`
- Create: `system/backend/tests/test_case_schemas.py`
- Create: `system/backend/tests/test_case_repositories.py`
- Create: `system/backend/tests/test_case_migration.py`

**Interfaces:**
- Consumes: Existing `Base`, `AsyncSession`, `EventSnapshotRecord.snapshot_id`, `AnalysisRun.run_id`, `ReviewVerdictVersion.verdict_id`, and User ids.
- Produces in `app.schemas.case`:

```python
class CaseState(StrEnum):
    DRAFT = "draft"
    COLLECTING = "collecting"
    EVIDENCE_READY = "evidence_ready"
    ANALYZING = "analyzing"
    AWAITING_REVIEW = "awaiting_review"
    ACTIONING = "actioning"
    READY_TO_CLOSE = "ready_to_close"
    CLOSED = "closed"

class CaseCreate(BaseModel):
    event_id: str
    title: str
    snapshot_id: str
    owner_id: int | None = None

class CaseBlockerView(BaseModel):
    code: str
    operation: str
    message: str
    evidence_refs: list[str]
    acknowledged_by: int | None = None
    acknowledged_at: datetime | None = None

class CaseView(BaseModel):
    case_id: str
    event_id: str
    title: str
    state: CaseState
    version: int
    current_snapshot_id: str
    primary_claim_id: str | None
    blockers: list[CaseBlockerView]
```

- Produces in `app.schemas.authority_source`: `SourceTier`, `AuthoritySourceStatus`, `AuthoritySourceCreate`, `AuthoritySourceDecision`, `AuthoritySourceView`, and `AuthorityMatchView`, using the exact tier and pending-review values in Global Constraints.
- Produces model classes: `CaseRecord`, `CaseSnapshotLink`, `CaseRunLink`, `AuthoritySourceVersion`, `CaseClaimRecord`, `CaseActionVersion`, `CaseReportVersionRecord`, `CaseAuditEventRecord`, and `CaseIdempotencyRecord`.
- Produces repository interfaces:

```python
class CaseRepository:
    def __init__(self, session: AsyncSession) -> None: ...
    async def create_case(self, payload: CaseCreate, *, actor_id: int, case_id: str | None = None) -> CaseRecord: ...
    async def get_case(self, case_id: str, *, for_update: bool = False) -> CaseRecord | None: ...
    async def list_cases(self, *, state: CaseState | None, offset: int, limit: int) -> tuple[list[CaseRecord], int]: ...
    async def append_snapshot_link(self, *, case_id: str, snapshot_id: str, actor_id: int) -> CaseSnapshotLink: ...
    async def append_run_link(self, *, case_id: str, run_id: str, run_kind: str, actor_id: int) -> CaseRunLink: ...
    async def append_audit_event(self, *, case_id: str, event_type: str, actor_id: int, payload: dict[str, Any]) -> CaseAuditEventRecord: ...
    async def list_audit_events(self, *, case_id: str, after_id: int, limit: int) -> list[CaseAuditEventRecord]: ...

class AuthoritySourceRepository:
    def __init__(self, session: AsyncSession) -> None: ...
    async def append_version(self, payload: AuthoritySourceCreate | AuthoritySourceDecision, *, actor_id: int) -> AuthoritySourceVersion: ...
    async def get_latest(self, source_id: str, *, for_update: bool = False) -> AuthoritySourceVersion | None: ...
    async def list_latest(self, *, status: AuthoritySourceStatus | None, offset: int, limit: int) -> tuple[list[AuthoritySourceVersion], int]: ...
```

- [ ] **Step 1: Write metadata, schema, repository, and migration tests**

Test exact table names, indexes, unique version constraints, append-only revision fields, string lengths, JSON/Text columns, enum validation, repository locking, monotonic link versions, audit cursor ordering, and Alembic parent `d2f7a8b9c0e1`. Assert no Case state accepts blocker codes.

```python
def test_case_state_is_exact_and_excludes_blockers():
    assert {state.value for state in CaseState} == {
        "draft", "collecting", "evidence_ready", "analyzing",
        "awaiting_review", "actioning", "ready_to_close", "closed",
    }
    with pytest.raises(ValueError):
        CaseState("blocked_missing_primary_claim")
```

- [ ] **Step 2: Run RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_models.py tests/test_case_schemas.py tests/test_case_repositories.py tests/test_case_migration.py -q
```

Expected: collection fails on missing Case model, schema, and repository modules.

- [ ] **Step 3: Implement focused records and explicit exports**

Use one model concept per file. Store logical ids as `String(128)`, status/state as `String(32)`, JSON payloads as non-null `Text`, and audit ids as auto-increment integer cursors. Use unique constraints on `(case_id, version)` snapshot links, `(case_id, run_id)` run links, `(source_id, version)` source versions, `(claim_id, version)` claim records, `(action_id, version)` action versions, `(case_id, report_version)` reports, and the idempotency scope.

Keep `CaseRecord.state`, `version`, `current_snapshot_id`, and nullable `primary_claim_id` as read projections. Do not add a default `semantic_enrichment` stage to `AnalysisRun`. Export public models, schemas, and repositories through explicit `__all__` with absolute imports.

- [ ] **Step 4: Implement migration `4c6a9d2e7f10`**

Create the nine Case core tables and indexes matching SQLAlchemy metadata. Use `down_revision = "d2f7a8b9c0e1"`, reversible downgrade order, foreign keys only where the referenced MySQL table is guaranteed to exist, and explicit logical-id indexes for external snapshot/run/verdict references.

- [ ] **Step 5: Run GREEN and migration checks**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_models.py tests/test_case_schemas.py tests/test_case_repositories.py tests/test_case_migration.py -q
uv run alembic heads
uv run python -m compileall app
```

Expected: all targeted tests pass, Alembic prints only `4c6a9d2e7f10 (head)`, and compileall succeeds.

- [ ] **Step 6: Commit the persistence boundary**

```powershell
git add -- system/backend/app/models system/backend/app/schemas system/backend/app/services system/backend/alembic/versions/4c6a9d2e7f10_add_case_workbench_core.py system/backend/tests/test_case_models.py system/backend/tests/test_case_schemas.py system/backend/tests/test_case_repositories.py system/backend/tests/test_case_migration.py
git commit -m "Give investigations a durable aggregate and audit cursor" -m "Persist focused Case records and repository seams while keeping snapshots, runs, blockers, and advisory verdicts distinct." -m "Constraint: Existing Analysis Run persistence and defaults remain compatible" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: Case metadata, schema, repository, migration, Alembic-head, and compile checks" -m "Not-tested: Migration against a production-sized MySQL dataset"
```

---

### Task 4: Authority Matching And Verbatim Claim Governance

**Files:**
- Create: `system/backend/app/core/analysis/source_matching.py`
- Create: `system/backend/app/core/analysis/claim_extraction.py`
- Modify: `system/backend/app/core/analysis/__init__.py`
- Create: `system/backend/app/services/authority_source_service.py`
- Create: `system/backend/app/services/case_claim_service.py`
- Modify: `system/backend/app/services/__init__.py`
- Create: `system/backend/tests/test_source_matching.py`
- Create: `system/backend/tests/test_case_claim_service.py`

**Interfaces:**
- Consumes: `AuthoritySourceRepository`, `CaseRepository`, research archive entries from Task 2, and core records from Task 3.
- Produces:

```python
@dataclass(frozen=True, slots=True)
class ArchivedSourceText:
    archive_id: str
    url: str
    source_account: str
    published_at: datetime
    text: str
    content_hash: str

@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    verbatim_excerpt: str
    span_start: int
    span_end: int
    excerpt_hash: str
    archive_id: str

def normalize_source_url(url: str) -> str: ...
def compute_content_hash(text: str) -> str: ...
def validate_claim_span(source: ArchivedSourceText, candidate: ClaimCandidate) -> None: ...
def extract_verbatim_candidates(source: ArchivedSourceText, *, exact_anchors: tuple[str, ...]) -> tuple[ClaimCandidate, ...]: ...

class AuthoritySourceService:
    async def match(self, *, url: str, source_account: str | None, published_at: datetime | None) -> AuthorityMatchView: ...
    async def create_candidate(self, payload: AuthoritySourceCreate, *, admin_id: int) -> AuthoritySourceView: ...
    async def approve(self, source_id: str, decision: AuthoritySourceDecision, *, admin_id: int) -> AuthoritySourceView: ...
    async def revoke(self, source_id: str, decision: AuthoritySourceDecision, *, admin_id: int) -> AuthoritySourceView: ...

class CaseClaimService:
    async def register_candidates(self, *, case_id: str, source: ArchivedSourceText, anchors: tuple[str, ...], actor_id: int) -> tuple[CaseClaimRecord, ...]: ...
    async def approve_primary(self, *, case_id: str, claim_id: str, expected_case_version: int, actor_id: int) -> CaseView: ...
    async def approve_supplementary(self, *, case_id: str, claim_id: str, actor_id: int) -> CaseClaimRecord: ...
    async def reject(self, *, case_id: str, claim_id: str, reason: str, actor_id: int) -> CaseClaimRecord: ...
```

- [ ] **Step 1: Write matching and claim invariant tests**

Cover URL normalization without query-tracking fields, exact domain/account rules, effective intervals, revoked versions, pending results for non-registry URLs, NFC span validation, content-hash mismatch, exact anchor extraction, primary pointer replacement with an explicit supersession event, and unlimited supplementary approvals.

```python
def test_non_registry_url_remains_pending_review():
    match = await service.match(url="https://unregistered.example/item", source_account=None, published_at=None)
    assert match.status == AuthoritySourceStatus.PENDING_REVIEW
    assert match.source_tier is None
```

- [ ] **Step 2: Run RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_source_matching.py tests/test_case_claim_service.py -q
```

Expected: collection fails because source matching, claim extraction, and governance services are absent.

- [ ] **Step 3: Implement deterministic source matching and extraction**

Normalize scheme/host case, IDNA host, default ports, path dot segments, and approved tracking parameters without changing meaningful path/query values. Match only active approved registry versions whose domain/account rule and effective interval both pass. Candidate extraction searches exact NFC anchors in the archived source, returns every non-overlapping exact span, and never generates or paraphrases text.

- [ ] **Step 4: Implement transactional claim decisions**

Lock the Case projection and latest claim records. Validate archive hash, excerpt hash, span, Authority Source status, and tier before approval. Primary approval updates the nullable Case pointer, appends a claim decision and Audit Event, increments Case version, and records any superseded primary id. Supplementary approval appends a decision without changing the pointer.

- [ ] **Step 5: Run GREEN and relevant regressions**

Run:

```powershell
cd system\backend
uv run pytest tests/test_source_matching.py tests/test_case_claim_service.py tests/test_case_models.py tests/test_case_repositories.py -q
```

Expected: all selected tests pass; no claim mutation test observes an in-place rewrite of a prior decision row.

- [ ] **Step 6: Commit source and claim governance**

```powershell
git add -- system/backend/app/core/analysis/source_matching.py system/backend/app/core/analysis/claim_extraction.py system/backend/app/core/analysis/__init__.py system/backend/app/services/authority_source_service.py system/backend/app/services/case_claim_service.py system/backend/app/services/__init__.py system/backend/tests/test_source_matching.py system/backend/tests/test_case_claim_service.py
git commit -m "Keep Case claims tied to exact authoritative source text" -m "Use versioned registry matching and span/hash validation so approved claims remain sourced assertions rather than generated summaries." -m "Constraint: Unregistered URLs stay pending and claim text is never paraphrased" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: Source matching, span fidelity, and primary/supplementary governance tests" -m "Not-tested: Live publisher URL stability after archival"
```

---

### Task 5: Versioned Semantic Enrichment And Shared Embedding Cache

**Files:**
- Modify: `system/backend/pyproject.toml`
- Modify: `system/backend/uv.lock`
- Create: `system/backend/app/models/semantic_artifact.py`
- Create: `system/backend/app/models/embedding_cache.py`
- Modify: `system/backend/app/models/__init__.py`
- Create: `system/backend/app/schemas/semantic_artifact.py`
- Modify: `system/backend/app/schemas/__init__.py`
- Create: `system/backend/app/core/analysis/semantic_contracts.py`
- Create: `system/backend/app/core/analysis/semantic_models.py`
- Create: `system/backend/app/core/analysis/semantic_embeddings.py`
- Create: `system/backend/app/core/analysis/semantic_sentiment.py`
- Create: `system/backend/app/core/analysis/semantic_stance.py`
- Create: `system/backend/app/core/analysis/semantic_topics.py`
- Create: `system/backend/app/core/analysis/semantic_keywords.py`
- Create: `system/backend/app/core/analysis/semantic_entities.py`
- Create: `system/backend/app/core/analysis/semantic_duplicates.py`
- Create: `system/backend/app/core/analysis/semantic_enrichment.py`
- Modify: `system/backend/app/core/analysis/contracts.py`
- Modify: `system/backend/app/core/analysis/executor.py`
- Modify: `system/backend/app/core/analysis/__init__.py`
- Create: `system/backend/app/services/semantic_artifact_repository.py`
- Create: `system/backend/app/services/semantic_correction_service.py`
- Modify: `system/backend/app/services/__init__.py`
- Create: `system/backend/alembic/versions/5d7b0e3f8a21_add_semantic_artifacts.py`
- Create: `system/backend/tests/test_semantic_stage_compatibility.py`
- Create: `system/backend/tests/test_semantic_persistence_models.py`
- Create: `system/backend/tests/test_semantic_enrichment.py`
- Create: `system/backend/tests/test_semantic_corrections.py`

**Interfaces:**
- Consumes: `EventSnapshot`, explicit stage options, optional approved Primary Claim payload, Coordination Community ids, Propagation Tree/path ids, and the Case repository link context.
- Produces:

```python
SEMANTIC_MODEL_IDENTITIES = {
    "embedding": "BAAI/bge-small-zh-v1.5@7999e1d",
    "sentiment": "lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110",
    "stance": "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92",
    "ner": "shibing624/bert4ner-base-chinese@5d660ed",
}

class SemanticArtifactKind(StrEnum):
    EMBEDDING = "embedding"
    SENTIMENT = "sentiment"
    STANCE = "stance"
    TOPIC = "topic"
    KEYWORD = "keyword"
    ENTITY = "entity"
    NEAR_DUPLICATE = "near_duplicate"

class SemanticEnrichmentOptions(BaseModel):
    case_id: str
    primary_claim: dict[str, Any] | None = None
    artifact_kinds: set[SemanticArtifactKind] | None = None
    device_preference: Literal["auto", "cpu", "cuda"] = "auto"
    time_bucket_minutes: int = 60

class SemanticEnrichmentResult(BaseModel):
    technology: Literal["semantic_enrichment"]
    snapshot_id: str
    validation_status: Literal["candidate_unvalidated", "validated"]
    artifacts: list[SemanticArtifactView]
    model_manifest: dict[str, ModelLoadRecord]
    degradation_reasons: list[str]

class SemanticEnrichmentEngine:
    async def analyze(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]: ...

class SemanticModelManager:
    async def use_model(self, capability: Literal["embedding", "sentiment", "stance", "ner"], device_preference: str) -> AsyncContextManager[LoadedSemanticModel]: ...

def maximal_marginal_relevance(document_embedding: NDArray, candidate_embeddings: NDArray, *, top_n: int, diversity: float) -> tuple[int, ...]: ...
def cluster_documents(embeddings: NDArray, *, min_cluster_size: int) -> NDArray: ...
def class_tfidf(tokenized_documents: Sequence[Sequence[str]], labels: Sequence[int]) -> dict[int, list[tuple[str, float]]]: ...
```

- Produces `SemanticArtifactRecord`, `SemanticCorrectionRecord`, and `EmbeddingCacheRecord`, plus repositories that append artifact/correction versions and get-or-create cache rows by `(model_identity, model_hash, content_hash, preprocessing_version)`.

- [ ] **Step 1: Write compatibility, algorithm, persistence, degradation, and correction tests**

Assert the default stage tuple is byte-for-byte unchanged, explicit `semantic_enrichment` normalizes successfully, ordinary Analysis Run requests still default to four stages, and the executor calls semantics only when requested. Test deterministic MMR, local clustering/class-based TF-IDF, separate post/comment subjects, cross-slice keys, shared cache reuse, exact model identities, aggregate hash recording, sequential model acquisition, GPU-to-CPU retry, missing-primary stance blocking, and append-only corrections.

```python
def test_default_analysis_stages_remain_compatible():
    assert DEFAULT_ANALYSIS_STAGES == (
        "coordination_discover", "propagation_analysis", "student", "teacher",
    )
    assert normalize_analysis_stage("semantic_enrichment") == "semantic_enrichment"
```

- [ ] **Step 2: Run RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_semantic_stage_compatibility.py tests/test_semantic_persistence_models.py tests/test_semantic_enrichment.py tests/test_semantic_corrections.py -q
```

Expected: tests fail because the semantic stage is unknown and semantic modules/records are absent; the existing four-stage assertion already passes.

- [ ] **Step 3: Add the bounded dependency and focused semantic modules**

Run `uv add "jieba>=0.42.1,<0.43.0"`, which updates only `pyproject.toml` and `uv.lock`. Reuse the existing sentence-transformers, Transformers, numpy, and scikit-learn installations. Implement each artifact kind in its named module, define explicit `__all__`, keep model I/O inside `semantic_models.py`, and keep persistence outside algorithm modules.

The model manager acquires one process-wide async lock, loads one pinned model, yields it, releases device memory, then permits the next model. Hash sorted relative model files and bytes. Retry a CUDA allocation failure once on CPU and record `degraded_cpu`; do not convert other model exceptions into heuristic output.

- [ ] **Step 4: Implement cache, versioned artifacts, local algorithms, and corrections**

Normalize content before SHA-256, store float32 embedding bytes plus dimension/dtype, and reject cache metadata mismatch. Run post and comment batches separately. Build cross-analysis subjects for time bucket, platform, Coordination Community, and Propagation Tree/path. Implement MMR, clustering, and class-based TF-IDF locally with deterministic seeds/order. A missing Primary Claim writes a stance artifact with `status="blocked"`, `code="blocked_missing_primary_claim"`, and no score.

All model-backed results start with `validation_status="candidate_unvalidated"`; only an exact model/config evaluation manifest may set `validated`. Corrections append a new correction record referencing the immutable artifact version.

- [ ] **Step 5: Integrate the explicit stage without changing defaults**

Add `semantic_enrichment` to aliases/allowlist only. Add a `semantic` port to `AnalysisEnginePorts`, route only that stage to `SemanticEnrichmentEngine.analyze`, include its model/artifact manifest in existing run persistence, and leave `AnalysisRunCreateRequest.requested_stages` default unchanged. Do not pass semantic outputs into the coordination, propagation, student, or teacher stage option mappings.

- [ ] **Step 6: Add migration `5d7b0e3f8a21` and run GREEN**

Use `down_revision = "4c6a9d2e7f10"`. Then run:

```powershell
cd system\backend
uv run pytest tests/test_semantic_stage_compatibility.py tests/test_semantic_persistence_models.py tests/test_semantic_enrichment.py tests/test_semantic_corrections.py tests/test_analysis_contracts.py tests/test_analysis_executor.py tests/test_analysis_run_schema.py -q
uv run alembic heads
uv run python -m compileall app
```

Expected: all selected tests pass, Alembic prints only `5d7b0e3f8a21 (head)`, compileall succeeds, and the compatibility test still observes four default stages.

- [ ] **Step 7: Commit semantic enrichment**

```powershell
git add -- system/backend/pyproject.toml system/backend/uv.lock system/backend/app/models system/backend/app/schemas system/backend/app/core/analysis system/backend/app/services system/backend/alembic/versions/5d7b0e3f8a21_add_semantic_artifacts.py system/backend/tests/test_semantic_stage_compatibility.py system/backend/tests/test_semantic_persistence_models.py system/backend/tests/test_semantic_enrichment.py system/backend/tests/test_semantic_corrections.py
git commit -m "Enrich Case evidence without changing core analysis scores" -m "Add an explicit versioned semantic stage, shared embedding cache, local topic/keyword algorithms, and append-only corrections behind pinned model provenance." -m "Constraint: Existing four-stage callers remain unchanged and semantic outputs stay auxiliary" -m "Rejected: Add semantic enrichment to the global default | would change existing Analysis Run behavior" -m "Confidence: medium" -m "Scope-risk: broad" -m "Tested: Semantic compatibility, algorithms, persistence, degradation, correction, executor, schema, migration, and compile checks" -m "Not-tested: Full-corpus GPU memory and latency"
```

---

### Task 6: Case Orchestration, Lifecycle Gates, Feedback, And Frozen Reports

**Files:**
- Create: `system/backend/app/models/case_feedback.py`
- Create: `system/backend/app/models/case_closeout.py`
- Create: `system/backend/app/models/partial_collection.py`
- Modify: `system/backend/app/models/__init__.py`
- Create: `system/backend/app/schemas/case_lifecycle.py`
- Create: `system/backend/app/schemas/case_report.py`
- Modify: `system/backend/app/schemas/__init__.py`
- Create: `system/backend/app/core/analysis/case_review_context.py`
- Modify: `system/backend/app/core/analysis/__init__.py`
- Create: `system/backend/app/services/case_blocker_service.py`
- Create: `system/backend/app/services/case_lifecycle_service.py`
- Create: `system/backend/app/services/case_orchestration_service.py`
- Create: `system/backend/app/services/case_feedback_service.py`
- Create: `system/backend/app/services/case_report_service.py`
- Create: `system/backend/app/services/chromium_pdf_renderer.py`
- Modify: `system/backend/app/services/__init__.py`
- Create: `system/backend/alembic/versions/6e8c1f4a9b32_add_case_workflow_records.py`
- Create: `system/backend/tests/test_case_blockers.py`
- Create: `system/backend/tests/test_case_lifecycle.py`
- Create: `system/backend/tests/test_case_orchestration.py`
- Create: `system/backend/tests/test_case_feedback.py`
- Create: `system/backend/tests/test_case_reports.py`

**Interfaces:**
- Consumes: `CaseRepository`, `AnalysisRegistry`, `AnalysisExecutor`, claim services, semantic artifacts, review verdict versions, report storage root, and a PDF renderer port.
- Produces `CaseFeedbackRecord`, `CloseoutReviewRecord`, and `PartialCollectionAcknowledgementRecord` as immutable append-only rows.
- Produces:

```python
CASE_ANALYSIS_STAGES = (
    "coordination_discover",
    "propagation_analysis",
    "semantic_enrichment",
    "student",
    "teacher",
)
INCREMENTAL_PRIMARY_CLAIM_STAGES = ("semantic_enrichment", "student", "teacher")

class CaseRunKind(StrEnum):
    FULL = "full"
    INCREMENTAL_PRIMARY_CLAIM = "incremental_primary_claim"

class CaseTransitionRequest(BaseModel):
    target_state: CaseState
    expected_version: int
    reason: str

class PartialCollectionAcknowledgementCreate(BaseModel):
    missing_platforms: list[Literal["douyin", "xhs"]]
    searched_archive_ids: list[str]
    rationale: str

class CloseoutReviewCreate(BaseModel):
    canonical_verdict_id: str
    rationale: str
    residual_risks: list[str]

class CaseBlockerService:
    async def list_blockers(self, case_id: str, *, operation: str | None = None) -> tuple[CaseBlockerView, ...]: ...

class CaseLifecycleService:
    async def transition(self, *, case_id: str, request: CaseTransitionRequest, actor_id: int) -> CaseView: ...
    async def acknowledge_partial_collection(self, *, case_id: str, payload: PartialCollectionAcknowledgementCreate, actor_id: int) -> CaseView: ...
    async def submit_closeout_review(self, *, case_id: str, payload: CloseoutReviewCreate, actor_id: int) -> CloseoutReviewRecord: ...
    async def close(self, *, case_id: str, expected_version: int, actor_id: int) -> CaseView: ...

class CaseOrchestrationService:
    async def request_run(self, *, case_id: str, run_kind: CaseRunKind, actor_id: int) -> dict[str, Any]: ...

class CaseFeedbackService:
    async def append_feedback(self, *, case_id: str, run_id: str | None, verdict_id: str | None, payload: dict[str, Any], actor_id: int) -> CaseFeedbackRecord: ...

class PdfRendererPort(Protocol):
    async def render(self, *, html_path: Path, pdf_path: Path) -> None: ...

class CaseReportService:
    async def freeze(self, *, case_id: str, actor_id: int) -> CaseReportVersionRecord: ...
    async def resolve_html(self, *, case_id: str, version: int) -> FrozenReportFile: ...
    async def resolve_pdf(self, *, case_id: str, version: int) -> FrozenReportFile: ...
```

- [ ] **Step 1: Write lifecycle, orchestration, feedback, and report tests**

Test every forward state transition, permitted re-analysis transitions, optimistic version conflict, closed immutability, scoped blocker computation, acknowledgement behavior, exact closure gates, action waiver rationale, Case/run/snapshot ownership, full and incremental stage lists, Risk Review evidence references, feedback ownership, deterministic report manifests, atomic HTML/PDF promotion, hashes, and PDF-render failure rollback.

```python
def test_case_full_run_is_only_default_that_requests_semantics():
    assert DEFAULT_ANALYSIS_STAGES == (
        "coordination_discover", "propagation_analysis", "student", "teacher",
    )
    assert CASE_ANALYSIS_STAGES == (
        "coordination_discover", "propagation_analysis", "semantic_enrichment", "student", "teacher",
    )
```

- [ ] **Step 2: Run RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_blockers.py tests/test_case_lifecycle.py tests/test_case_orchestration.py tests/test_case_feedback.py tests/test_case_reports.py -q
```

Expected: collection fails because lifecycle, orchestration, feedback, and report modules do not exist.

- [ ] **Step 3: Implement blocker and lifecycle services**

Compute blockers from stored facts without mutating Case State. Missing primary returns `blocked_missing_primary_claim` scoped to `stance`; a Platform Gap blocks collection advancement until acknowledged. Transition inside one transaction: lock Case, compare `expected_version`, validate allowed edge and scoped blockers, update projection, append one Audit Event, then commit. Closure checks only approved Canonical Verdict ownership, latest required action versions, and submitted Closeout Review.

- [ ] **Step 4: Implement full and incremental orchestration**

For `full`, create the Analysis Run with `CASE_ANALYSIS_STAGES`, options containing `case_id`, approved primary claim or null, and evidence references. For `incremental_primary_claim`, require an approved primary and create a run with `INCREMENTAL_PRIMARY_CLAIM_STAGES`; semantic options contain `artifact_kinds=["stance"]`, while review options receive the approved claim and prior core artifact references. Never pass semantic payloads or scores into coordination, propagation, Student Review, or Teacher Review option maps.

Append the run link, transition to `analyzing`, and add an Audit Event in the same transaction. Mirror completion by reference, not by copying or mutating Analysis Run events.

- [ ] **Step 5: Implement append-only feedback, closeout, and report freezing**

Validate that feedback run/verdict belongs to the Case, then append. Render deterministic HTML with escaped source text and `@media print` rules. Write HTML to a temporary version directory, call `ChromiumPdfRenderer` using configured `CASE_REPORT_CHROMIUM_PATH --headless --disable-gpu --print-to-pdf=<path> <file-uri>`, compute both hashes, and atomically rename the directory before appending `CaseReportVersionRecord` and an Audit Event. A renderer error removes only temporary files and creates no version row.

- [ ] **Step 6: Add migration `6e8c1f4a9b32` and run GREEN**

Use `down_revision = "5d7b0e3f8a21"`. Then run:

```powershell
cd system\backend
uv run pytest tests/test_case_blockers.py tests/test_case_lifecycle.py tests/test_case_orchestration.py tests/test_case_feedback.py tests/test_case_reports.py tests/test_analysis_executor.py tests/test_analysis_governance.py -q
uv run alembic heads
uv run python -m compileall app
```

Expected: all selected tests pass, Alembic prints only `6e8c1f4a9b32 (head)`, compileall succeeds, and report failure tests leave no published version.

- [ ] **Step 7: Commit the workflow boundary**

```powershell
git add -- system/backend/app/models system/backend/app/schemas system/backend/app/core/analysis system/backend/app/services system/backend/alembic/versions/6e8c1f4a9b32_add_case_workflow_records.py system/backend/tests/test_case_blockers.py system/backend/tests/test_case_lifecycle.py system/backend/tests/test_case_orchestration.py system/backend/tests/test_case_feedback.py system/backend/tests/test_case_reports.py
git commit -m "Make Case decisions replayable from evidence through closeout" -m "Coordinate explicit full and incremental runs, scoped blockers, append-only operations, strict closure, and atomic report versions around the durable Case aggregate." -m "Constraint: Semantic artifacts remain auxiliary and closure has exactly three domain gates" -m "Rejected: Encode blockers as Case states | conflates lifecycle with operation readiness" -m "Confidence: high" -m "Scope-risk: broad" -m "Tested: Blocker, lifecycle, orchestration, feedback, report, analysis governance, migration, and compile checks" -m "Not-tested: Chromium rendering across non-Windows deployment images"
```

---

### Task 7: Main Case Fixture And Isolated Twitter Benchmark Manifest

**Files:**
- Create: `system/backend/fixtures/case_workbench/trump_visit_2026_05_21.json`
- Create: `system/backend/fixtures/case_workbench/twitter_io_manifest.json`
- Create: `system/backend/app/services/case_fixture_importer.py`
- Modify: `system/backend/app/services/__init__.py`
- Create: `system/backend/scripts/import_case_workbench_fixture.py`
- Create: `system/backend/scripts/verify_twitter_benchmark.py`
- Create: `system/backend/tests/test_case_fixture_importer.py`
- Create: `system/backend/tests/test_twitter_benchmark_manifest.py`
- Modify: `doc/research/case-workbench/archive-manifest.json`

**Interfaces:**
- Consumes: Verified Task 2 archive entries, Task 3-6 services, existing Mongo event data, and the external CSV only when running the benchmark verifier.
- Produces:

```python
class MainCaseFixture(BaseModel):
    case_id: Literal["case_trump_visit_2026_05_21"]
    event_id: Literal["trump_visit_2026_05_21"]
    core_window: TimeWindow
    context_window: TimeWindow
    expected_weibo_counts: dict[Literal["posts", "authors", "comments", "commenters"], int]
    primary_claim_archive_id: str
    supplementary_claim_archive_ids: list[str]
    second_platform_archive_id: str | None
    platform_gap: dict[str, Any] | None

class TwitterBenchmarkManifest(BaseModel):
    schema_version: Literal["cogguard.twitter_io.manifest.v1"]
    source_path: str
    byte_size: Literal[25604849]
    sha256: Literal["E4D12CC8F56D09FCFBEAC3B09C5D45537B8E390536E3860AFD768DDC651FB8B4"]
    columns: tuple[str, ...]
    rows: Literal[39964]
    users: Literal[60]
    retweets: Literal[16310]
    replies: Literal[8697]
    quotes: Literal[4814]

class CaseFixtureImporter:
    async def import_main_case(self, fixture: MainCaseFixture, *, actor_id: int) -> CaseView: ...

def scan_twitter_benchmark(path: Path) -> TwitterBenchmarkManifest: ...
def verify_twitter_benchmark(path: Path, expected: TwitterBenchmarkManifest) -> None: ...
```

- [ ] **Step 1: Write fixture and benchmark contract tests**

Test exact Case/event ids, inclusive Beijing display dates represented as half-open aware windows, the four Weibo counts, both exact claim excerpts, source archive ownership, mutually exclusive verified second-platform/archive-gap fields, idempotent import, and absence of Twitter links in the main Case. Test the complete 31-column CSV header, digest/stat definitions, and a guard that rejects a Markdown or CSV payload in the committed fixture directory.

The column tuple is exactly:

```python
(
    "tweetid", "userid", "user_display_name", "user_screen_name",
    "user_reported_location", "user_profile_description", "user_profile_url",
    "follower_count", "following_count", "account_creation_date",
    "account_language", "tweet_language", "tweet_text", "tweet_time",
    "tweet_client_name", "in_reply_to_userid", "in_reply_to_tweetid",
    "quoted_tweet_tweetid", "is_retweet", "retweet_userid", "retweet_tweetid",
    "latitude", "longitude", "quote_count", "reply_count", "like_count",
    "retweet_count", "hashtags", "urls", "user_mentions", "poll_choices",
)
```

- [ ] **Step 2: Run RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_fixture_importer.py tests/test_twitter_benchmark_manifest.py -q
```

Expected: collection fails because fixture files, importer, and verifier do not exist.

- [ ] **Step 3: Build and import the main Case fixture**

Set the core window to `[2026-05-14T00:00:00+08:00, 2026-05-18T00:00:00+08:00)` and context window to `[2026-05-08T00:00:00+08:00, 2026-05-21T00:00:00+08:00)`. Require exact existing Weibo counts `74`, `57`, `5048`, and `4492` before import.

Use Primary Claim `我们应当共同扛起这个历史重任，推动中美关系这艘巨轮沿着正确航道平稳前行。` and Supplementary Claim `一次历史性标志性访问。` only through verified archive ids. If Task 2 verified same-event Douyin/XHS evidence, link that archive; otherwise persist the Platform Gap and provenance disclosure. The importer uses stable ids and repository idempotency so rerunning returns the same Case without duplicate operations.

- [ ] **Step 4: Implement the separate streaming benchmark verifier**

Use Python `csv.DictReader` and `hashlib`, never pandas or Markdown conversion. Count data rows, distinct `userid`, case-insensitive truthy `is_retweet`, non-empty `in_reply_to_tweetid`, and non-empty `quoted_tweet_tweetid`. Store only source path, byte size, header, counts, and digest in `twitter_io_manifest.json`. Do not call the Case importer from this script.

- [ ] **Step 5: Run GREEN and real read-only regression verification**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_fixture_importer.py tests/test_twitter_benchmark_manifest.py -q
uv run python scripts/verify_twitter_benchmark.py --source 'C:\Users\p\AppData\Local\Temp\cogguard-032020-twitter-io-full.csv' --manifest fixtures/case_workbench/twitter_io_manifest.json
```

Expected: all tests pass; the verifier reports 39,964 rows, 60 users, 16,310 retweets, 8,697 replies, 4,814 quotes, and the exact expected SHA-256, then exits zero.

- [ ] **Step 6: Commit fixtures without source payloads**

```powershell
git add -- system/backend/fixtures/case_workbench system/backend/app/services/case_fixture_importer.py system/backend/app/services/__init__.py system/backend/scripts/import_case_workbench_fixture.py system/backend/scripts/verify_twitter_benchmark.py system/backend/tests/test_case_fixture_importer.py system/backend/tests/test_twitter_benchmark_manifest.py doc/research/case-workbench/archive-manifest.json
git diff --cached --numstat
git commit -m "Ground the Case demonstration in verified and isolated evidence" -m "Import the main Case from archived same-event sources while preserving a separate digest-only Twitter research snapshot." -m "Constraint: Never commit or link the full Twitter CSV and never fabricate a second platform" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: Fixture importer, manifest contract, and real CSV digest/stat regression" -m "Not-tested: Future availability of the external temporary CSV path"
```

Expected: staged paths contain no `.csv` and no full benchmark Markdown file.

---

### Task 8: Case And Authority Source API, Permissions, Idempotency, SSE, And Reports

**Files:**
- Create: `system/backend/app/api/v2/dependencies.py`
- Create: `system/backend/app/api/v2/cases.py`
- Create: `system/backend/app/api/v2/authority_sources.py`
- Modify: `system/backend/app/api/v2/router.py`
- Create: `system/backend/app/services/idempotency_service.py`
- Modify: `system/backend/app/services/__init__.py`
- Create: `system/backend/tests/test_case_api.py`
- Create: `system/backend/tests/test_authority_source_api.py`
- Create: `system/backend/tests/test_case_api_permissions.py`
- Create: `system/backend/tests/test_case_api_idempotency.py`
- Create: `system/backend/tests/test_case_api_sse.py`
- Create: `system/backend/tests/test_case_report_api.py`

**Interfaces:**
- Consumes: Task 3-7 repositories/services, existing `get_db`, `require_roles`, `success`, `parse_last_event_id`, and `iter_sse_events`.
- Produces:

```python
@dataclass(slots=True)
class CaseServiceBundle:
    repository: CaseRepository
    lifecycle: CaseLifecycleService
    orchestration: CaseOrchestrationService
    claims: CaseClaimService
    feedback: CaseFeedbackService
    reports: CaseReportService
    blockers: CaseBlockerService
    idempotency: IdempotencyService

def get_case_service_bundle(db: AsyncSession = Depends(get_db)) -> CaseServiceBundle: ...
def get_authority_source_service(db: AsyncSession = Depends(get_db)) -> AuthoritySourceService: ...

class IdempotencyService:
    async def execute(self, *, actor_id: int, method: str, canonical_path: str, key: str, request_body: bytes, operation: Callable[[], Awaitable[IdempotentResponse]]) -> IdempotentResponse: ...
```

- Produces all routes in the design API table, mounted as `cases.router` at `/api/v2/cases` and `authority_sources.router` at `/api/v2/authority-sources`.

- [ ] **Step 1: Write API contract, authorization, retry, stream, and file-response tests**

Use a FastAPI test app with dependency overrides, ASGI transport, real Pydantic bodies, and fake service bundles. Cover list/create/detail/state/snapshot/claim/run/action/acknowledgement/feedback/closeout/close/report/event routes, all Authority Source routes, viewer/analyst/admin boundaries, missing idempotency key, identical retry replay, conflicting retry `409`, expected-version `409`, `after_id`, `Last-Event-ID`, HTML/PDF content types, ETag, and not-found behavior.

```python
def test_mutation_replays_same_response_and_rejects_changed_body():
    first = await client.post("/api/v2/cases", headers={**analyst, "Idempotency-Key": "create-a"}, json=body)
    replay = await client.post("/api/v2/cases", headers={**analyst, "Idempotency-Key": "create-a"}, json=body)
    conflict = await client.post("/api/v2/cases", headers={**analyst, "Idempotency-Key": "create-a"}, json={**body, "title": "changed"})
    assert replay.json() == first.json()
    assert conflict.status_code == 409
```

- [ ] **Step 2: Run RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_api.py tests/test_authority_source_api.py tests/test_case_api_permissions.py tests/test_case_api_idempotency.py tests/test_case_api_sse.py tests/test_case_report_api.py -q
```

Expected: collection fails because the Case and Authority Source v2 routers and service dependencies are absent.

- [ ] **Step 3: Implement the dependency bundle and idempotent mutation wrapper**

Construct focused repositories/services from one request-scoped `AsyncSession`. Require a non-empty `Idempotency-Key` on every mutation. Canonicalize JSON request bytes before hashing, lock the persisted key scope, return the stored status/body for an exact retry, and return `409` for a hash mismatch. Persist the response and domain operation in one transaction.

- [ ] **Step 4: Implement all Case and Authority Source routes**

Use `require_roles("admin", "analyst", "viewer")` for reads, `require_roles("admin", "analyst")` for Case mutations, and `require_roles("admin")` for Authority Source creation/approval/revocation. Return `400` for validation, `404` for missing records, `409` for lifecycle/version/idempotency conflicts, and `422` through Pydantic. Preserve one-analyst operation without weakening actor audit.

The exact nested Case mutation paths are those in the design API table. The report GET routes return immutable bytes with `text/html; charset=utf-8` or `application/pdf`, `ETag` equal to the stored quoted SHA-256, and `Cache-Control: private, immutable`.

- [ ] **Step 5: Implement Case audit recovery and SSE**

Shape Case audit records as `{id, case_id, event_type, status, payload, created_at}` and reuse existing SSE formatting. REST returns strictly `id > after_id`; SSE uses `parse_last_event_id(last_event_id, fallback=after_id)` and `iter_sse_events`. Return `Cache-Control: no-cache` and never duplicate the cursor event.

- [ ] **Step 6: Run GREEN and existing v2 regressions**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_api.py tests/test_authority_source_api.py tests/test_case_api_permissions.py tests/test_case_api_idempotency.py tests/test_case_api_sse.py tests/test_case_report_api.py tests/test_analysis_v2_api.py tests/test_auth.py -q
uv run python -m compileall app
```

Expected: all selected tests pass and compileall succeeds; the existing `/api/v2/analysis` and auth tests remain green.

- [ ] **Step 7: Commit the current API surface**

```powershell
git add -- system/backend/app/api/v2 system/backend/app/services/idempotency_service.py system/backend/app/services/__init__.py system/backend/tests/test_case_api.py system/backend/tests/test_authority_source_api.py system/backend/tests/test_case_api_permissions.py system/backend/tests/test_case_api_idempotency.py system/backend/tests/test_case_api_sse.py system/backend/tests/test_case_report_api.py
git commit -m "Expose governed Case operations through a recoverable API" -m "Add role-gated, idempotent v2 routes with cursor recovery and immutable report delivery over the Case service boundary." -m "Constraint: Authority registry decisions are admin-only and every mutation is idempotent" -m "Confidence: high" -m "Scope-risk: broad" -m "Tested: Case, authority, permission, idempotency, SSE, report, existing v2, auth, and compile checks" -m "Not-tested: Reverse-proxy buffering behavior for long-lived SSE connections"
```

---

### Task 9: Vue Case List, Wizard, And Dense Five-Tab Workbench

**Files:**
- Create: `system/frontend/src/types/case.ts`
- Create: `system/frontend/src/api/cases.ts`
- Create: `system/frontend/src/api/authority-sources.ts`
- Create: `system/frontend/src/views/cases/index.vue`
- Create: `system/frontend/src/views/cases/create.vue`
- Create: `system/frontend/src/views/cases/workbench.vue`
- Create: `system/frontend/src/views/cases/components/CaseContextBar.vue`
- Create: `system/frontend/src/views/cases/components/OverviewTab.vue`
- Create: `system/frontend/src/views/cases/components/EvidenceMatrixTab.vue`
- Create: `system/frontend/src/views/cases/components/GraphTab.vue`
- Create: `system/frontend/src/views/cases/components/ActionsTab.vue`
- Create: `system/frontend/src/views/cases/components/ReportsTab.vue`
- Create: `system/frontend/src/views/cases/components/EvidenceDrawer.vue`
- Modify: `system/frontend/src/router/index.ts`
- Modify: `system/frontend/src/components/layout/BasicLayout.vue`
- Create: `system/backend/tests/test_case_frontend_contract.py`

**Interfaces:**
- Consumes: Task 8 JSON envelopes, report bytes, Case event stream URL, current auth store, existing specialist routes, Ant Design Vue, and icon components from `@ant-design/icons-vue`.
- Produces in `types/case.ts`: `CaseState`, `CaseBlocker`, `CaseSummary`, `CaseDetail`, `AuthoritySource`, `CaseClaim`, `SemanticArtifact`, `CaseAction`, `CaseReportVersion`, `CaseAuditEvent`, and request body types matching backend field names exactly.
- Produces in `api/cases.ts`:

```typescript
export function listCases(params: CaseListParams): Promise<ApiEnvelope<CasePage>>
export function createCase(body: CaseCreateRequest, idempotencyKey: string): Promise<ApiEnvelope<CaseDetail>>
export function getCase(caseId: string): Promise<ApiEnvelope<CaseDetail>>
export function transitionCase(caseId: string, body: CaseTransitionRequest, idempotencyKey: string): Promise<ApiEnvelope<CaseDetail>>
export function approvePrimaryClaim(caseId: string, claimId: string, body: ClaimApprovalRequest, idempotencyKey: string): Promise<ApiEnvelope<CaseDetail>>
export function requestCaseRun(caseId: string, body: CaseRunRequest, idempotencyKey: string): Promise<ApiEnvelope<AnalysisRunSummary>>
export function appendCaseAction(caseId: string, body: CaseActionCreateRequest, idempotencyKey: string): Promise<ApiEnvelope<CaseAction>>
export function appendCaseFeedback(caseId: string, body: CaseFeedbackCreateRequest, idempotencyKey: string): Promise<ApiEnvelope<CaseFeedback>>
export function freezeCaseReport(caseId: string, idempotencyKey: string): Promise<ApiEnvelope<CaseReportVersion>>
export function caseEventStreamUrl(caseId: string, afterId: number): string
export function caseReportUrl(caseId: string, version: number, format: 'html' | 'pdf'): string
```

- Produces routes `/cases`, `/cases/new`, and `/cases/:caseId`; a Case menu item with a familiar folder/search icon; and five tab keys `overview`, `evidence`, `graph`, `actions`, and `reports` labeled exactly `概览`, `证据矩阵`, `图谱`, `处置`, and `报告`.

- [ ] **Step 1: Write the frontend source contract test**

Because the current frontend has no component-test dependency, add a focused backend governance test that verifies files, route names, menu route, exported API functions, five exact labels, persistent `CaseContextBar` placement outside tab panels, evidence drawer, action/feedback controls, report print styles, and no nested-card selector. Behavioral validation remains in Task 10 Playwright.

```python
def test_workbench_keeps_case_context_outside_all_five_tabs():
    source = WORKBENCH.read_text(encoding="utf-8")
    assert source.index("<CaseContextBar") < source.index("<a-tabs")
    assert [label for label in ("概览", "证据矩阵", "图谱", "处置", "报告") if label in source] == [
        "概览", "证据矩阵", "图谱", "处置", "报告",
    ]
```

- [ ] **Step 2: Run RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_frontend_contract.py -q
```

Expected: the test fails because the Case routes, views, types, and APIs do not exist.

- [ ] **Step 3: Implement typed APIs, list, and wizard**

Reuse the existing bearer-token interceptor behavior while adding `Idempotency-Key` per mutation. The list supports state, owner, blocker, and text filters plus pagination. The wizard captures event id/title, Beijing core/context windows, current snapshot creation/linking, verified source selection, Primary Claim candidate, and second-platform outcome. It never permits typed free-form text to masquerade as a sourced approved claim.

- [ ] **Step 4: Implement the workbench shell and five focused tabs**

Keep `CaseContextBar` above `a-tabs` and stable during loading, event updates, and tab changes. Overview shows timeline and runs; Evidence Matrix shows sources/claims/posts/comments/semantic versions and opens `EvidenceDrawer`; Graph reuses links/projections from Coordination and Propagation without recomputing; Actions handles action versions, explicit waivers, feedback, acknowledgement, and closeout; Reports shows frozen versions and icon actions for preview, print, and PDF download.

Use dense tables, split panes, drawers, segmented filters, status tags, tooltips for unfamiliar icons, and restrained colors. Do not put cards inside cards. On mobile, wrap the context band, horizontally scroll tabs, preserve 40px or larger action targets, and move row details to the drawer.

- [ ] **Step 5: Add navigation and lifecycle refresh**

Add the Case menu item next to the operational analysis pages and router records under the existing `BasicLayout`. Use REST cursor recovery followed by SSE where authentication permits; on stream failure, poll `GET /events?after_id=` without resetting the cursor. Merge events by integer id and refetch Case detail after accepted domain events.

- [ ] **Step 6: Run GREEN and TypeScript production build**

Run:

```powershell
cd system\backend
uv run pytest tests/test_case_frontend_contract.py -q
cd ..\frontend
npm run build
```

Expected: the contract test passes; `vue-tsc -b` and Vite production build complete with no errors or text-overflow warnings emitted by project checks.

- [ ] **Step 7: Commit the frontend workflow**

```powershell
git add -- system/frontend/src/types/case.ts system/frontend/src/api/cases.ts system/frontend/src/api/authority-sources.ts system/frontend/src/views/cases system/frontend/src/router/index.ts system/frontend/src/components/layout/BasicLayout.vue system/backend/tests/test_case_frontend_contract.py
git commit -m "Let analysts operate a Case without losing evidence context" -m "Add a dense list, creation wizard, persistent context band, and five focused workbench views over the governed v2 contracts." -m "Constraint: Case State, Primary Claim, and blockers remain visible across every tab" -m "Confidence: medium" -m "Scope-risk: broad" -m "Tested: Frontend source contract, vue-tsc, and Vite production build" -m "Not-tested: Real browser layout and interaction, reserved for the final Playwright gate"
```

---

### Task 10: Documentation Sync, Full Verification, Browser QA, Preview, And Final Review

**Files:**
- Modify: `UBIQUITOUS_LANGUAGE.md`
- Modify: `doc/engineering/system-governance.md`
- Modify: `doc/engineering/project-map.md`
- Modify: `doc/engineering/development-roadmap.md`
- Modify: `doc/engineering/development-log.md`
- Modify: `README.md`
- Modify: `system/README.md`
- Create: `doc/adr/0007-case-workbench-and-auditable-case-lifecycle.md`
- Review: every file changed by Tasks 1-9

**Interfaces:**
- Consumes: Completed Case implementation, targeted task reports, migration chain, built frontend, running preview, and all prior test evidence.
- Produces: Synchronized canonical docs and ADR, one migration head, full backend/frontend/browser evidence, preview URL, and broad reviewer verdict with no open Critical or Important findings.

- [ ] **Step 1: Write the Documentation Sync assertions first**

Extend existing governance tests so canonical docs name Case Workbench, the eight exact states, separate blockers, Authority Source tiers, opt-in semantic stage, report provenance, new model/schema/service/API/frontend boundaries, and ADR `0007`. Assert the roadmap/log no longer describe Case/report/semantic work as absent once implementation is complete.

- [ ] **Step 2: Run documentation RED**

Run:

```powershell
cd system\backend
uv run pytest tests/test_governance_docs.py tests/test_system_naming_governance.py -q
```

Expected: new Documentation Sync assertions fail on the still-unsynchronized roadmap, governance, map, README, or ADR paths; pre-existing assertions remain green.

- [ ] **Step 3: Synchronize the canonical documentation and ADR**

Update vocabulary relationships, package/file ownership, exact run flow, API routes, setup for `CASE_REPORT_CHROMIUM_PATH`, report storage policy, model provenance, Case permissions, migration head, demonstration importer, current status, and verification commands. ADR `0007` records why Case is distinct from Event Snapshot and Analysis Run, why blockers are separate, why semantic enrichment is opt-in and score-isolated, why operations are append-only, and why reports freeze HTML/PDF together.

- [ ] **Step 4: Run documentation GREEN, static checks, migrations, and the full backend suite**

Run sequentially:

```powershell
cd system\backend
uv run pytest tests/test_governance_docs.py tests/test_system_naming_governance.py -q
uv run python -m compileall app scripts
uv run alembic heads
uv run alembic upgrade head
uv run pytest tests -q
git diff --check
```

Expected: all governance and backend tests pass with only explicitly documented skips; compileall succeeds; Alembic prints one head `6e8c1f4a9b32` and upgrades successfully; `git diff --check` is silent. A failure is fixed and the affected command rerun before continuing.

- [ ] **Step 5: Build the frontend**

Run:

```powershell
cd system\frontend
npm run build
```

Expected: `vue-tsc -b` and Vite production build succeed with no errors.

- [ ] **Step 6: Start preview and run Playwright desktop/mobile validation**

Start backend and frontend on free local ports, using `8000` and `5173` when available:

```powershell
cd system\backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ..\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Use the `playwright` skill against `http://127.0.0.1:5173/preview`, then open the imported main Case. Verify at `1440x900` and `375x812`: Case list filtering, wizard validation, persistent context band on all five tabs, evidence drawer, graph evidence links, action completion and waiver, feedback, closeout gates, report HTML preview, print styling, PDF response, SSE reconnect cursor, no overlaps, no clipped button text, and no horizontal page overflow other than the intentional tab/table scrollers. Save screenshots and browser-console/network evidence under ignored `.superpowers/verification/case-workbench/`.

Expected: every workflow is usable at both viewports, screenshots are nonblank, console has no uncaught errors, API mutations are not duplicated, and the preview URL remains reachable for handoff.

- [ ] **Step 7: Commit Documentation Sync with Lore context**

```powershell
git add -- UBIQUITOUS_LANGUAGE.md doc/engineering/system-governance.md doc/engineering/project-map.md doc/engineering/development-roadmap.md doc/engineering/development-log.md README.md system/README.md doc/adr/0007-case-workbench-and-auditable-case-lifecycle.md system/backend/tests/test_governance_docs.py system/backend/tests/test_system_naming_governance.py
git commit -m "Keep the documented system aligned with the Case workflow" -m "Synchronize governance, maps, status, run instructions, and the durable architecture decision with the verified implementation." -m "Constraint: Documentation must describe real code and preserve formal method language" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: Full backend, governance, compile, migration, frontend build, and Playwright desktop/mobile preview" -m "Not-tested: Production infrastructure load and long-running GPU throughput"
```

- [ ] **Step 8: Run broad final review and fix every release-blocking finding**

Generate a review package from the branch merge base through `HEAD`. Dispatch a fresh broad reviewer with the design, this plan, task reports, review package, and Global Constraints. Require separate spec-compliance and code-quality verdicts. Send all Critical and Important findings together to one fixer, rerun each affected test command, and re-review until both verdicts are approved. Record Minor residuals explicitly.

Expected: review reports no open Critical or Important findings, all fixes have covering test evidence, and `git status --short` contains only intentional ignored verification artifacts.

---

## Interface Ownership Matrix

| Public surface | Owner task | Canonical path |
| --- | --- | --- |
| `StructuredSearchHit`, `StructuredSearchRecord`, `ResearchArchiveEntry` | 2 | `app/schemas/case_research.py` |
| `load_structured_search_records`, `load_research_archive_manifest`, `verify_research_archive` | 2 | `app/services/case_research_archive.py` |
| `CaseState`, `CaseCreate`, `CaseBlockerView`, `CaseView` | 3 | `app/schemas/case.py` |
| `SourceTier`, `AuthoritySourceStatus`, source request/view contracts | 3 | `app/schemas/authority_source.py` |
| Case, snapshot, run, claim, action, report, audit, idempotency records | 3 | Focused files under `app/models/` |
| `CaseRepository`, `AuthoritySourceRepository` | 3 | `app/services/case_repository.py`, `app/services/authority_source_repository.py` |
| `ArchivedSourceText`, `ClaimCandidate`, URL/hash/span functions | 4 | `app/core/analysis/source_matching.py`, `app/core/analysis/claim_extraction.py` |
| `AuthoritySourceService`, `CaseClaimService` | 4 | Focused files under `app/services/` |
| Semantic enums/options/results/model records | 5 | `app/core/analysis/semantic_contracts.py`, `app/schemas/semantic_artifact.py` |
| `SemanticModelManager`, `SemanticEnrichmentEngine` | 5 | `app/core/analysis/semantic_models.py`, `app/core/analysis/semantic_enrichment.py` |
| MMR, clustering, class-based TF-IDF | 5 | `semantic_keywords.py`, `semantic_topics.py` |
| Semantic artifact/correction/cache records and repositories | 5 | Focused model/service files from Task 5 |
| `CaseRunKind`, `CaseTransitionRequest`, acknowledgement and closeout bodies | 6 | `app/schemas/case_lifecycle.py` |
| `CaseBlockerService`, `CaseLifecycleService`, `CaseOrchestrationService` | 6 | Focused files under `app/services/` |
| `CaseFeedbackService`, `CaseReportService`, `PdfRendererPort` | 6 | Focused files under `app/services/` |
| `MainCaseFixture`, `TwitterBenchmarkManifest`, `CaseFixtureImporter` | 7 | Fixture JSON plus `app/services/case_fixture_importer.py` |
| `scan_twitter_benchmark`, `verify_twitter_benchmark` | 7 | `scripts/verify_twitter_benchmark.py` |
| `CaseServiceBundle`, service dependency factories | 8 | `app/api/v2/dependencies.py` |
| `IdempotencyService` | 8 | `app/services/idempotency_service.py` |
| `/api/v2/cases` and `/api/v2/authority-sources` | 8 | `app/api/v2/cases.py`, `app/api/v2/authority_sources.py` |
| TypeScript Case contracts and client functions | 9 | `src/types/case.ts`, `src/api/cases.ts`, `src/api/authority-sources.ts` |
| Case list, wizard, workbench, and tab components | 9 | `src/views/cases/` |
| Canonical documentation, ADR, and full verification record | 10 | Documentation paths listed in Task 10 |

## Plan Self-Review

- Spec coverage: each approved product, evidence, semantic, report, demonstration, API, UI, and verification requirement maps to Tasks 1-10.
- Type consistency: Case ids, snapshot ids, run ids, claim ids, source ids, versions, actor ids, cursors, and idempotency keys keep one spelling across producer and consumer tasks.
- Dependency control: Task 5 adds only bounded `jieba`; PDF uses a configured Chromium executable and Task 2 uses the external MarkItDown wrapper without adding product dependencies.
- Compatibility: Tasks 5 and 6 contain explicit regression assertions for the unchanged four-stage default.
- Evidence integrity: Tasks 2, 4, and 7 require exact excerpts, spans, source hashes, and an explicit Platform Gap instead of invented content.
- Reviewability: every task has one owned behavior boundary, a failing test command, a passing test command, expected evidence, and a Lore commit.
