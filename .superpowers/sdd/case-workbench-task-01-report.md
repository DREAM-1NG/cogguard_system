# Case Workbench Task 01 Report

## Status

Ready for fresh independent re-review: the independent review of `425a8f2..cc4dde6` found 5 Important and 1 Minor issue. This correction pass resolves the documented contract, provenance, and delivery findings; content, staging, and scope validation have passed, while re-review remains required before implementation begins.

## Scope

- Branch/worktree: `refactor-system` at rollback baseline `425a8f2`.
- Production code changed: no.
- Protected dirty files edited/staged: no, including `propagation_fair_learned_matrix_20260810.md`.
- Network evidence: bounded GitHub/API downloads only; Jina Reader vendor-page attempts returned authentication blocks and are recorded transparently.

## Work Products

- Design: `docs/superpowers/specs/2026-08-10-case-workbench-design.md`
- Plan: `docs/superpowers/plans/2026-08-10-case-workbench.md`
- Research: `doc/research/case-workbench/`
- Progress ledger: `.superpowers/sdd/case-workbench-progress.md`

## Planned Validation Record

| Check | Status | Result |
| --- | --- | --- |
| JSON parse | passed | `source-metadata.json`, Twitter manifest, and both retained conversion metadata files parse successfully. |
| Retained source hash check | passed | BERTopic and KeyBERT retained originals match source metadata and conversion metadata SHA-256 values. |
| Markdown/link check | passed | Eight authored Task 01 Markdown files have no missing relative links; generated conversion image links remain upstream-only by design. |
| MarkItDown conversion provenance | passed | Both retained conversions identify source URL, retrieval timing boundary, content type, command, MarkItDown `0.1.5`, and converted status. |
| Git diff/restricted-file check | passed | `git diff --cached --check` passed; the staged set contains only Task 01 paths and excludes the protected dirty files. |

## Independent Review And Fix Record

- Review artifact: `.superpowers/sdd/case-workbench-task-01-review.md`.
- Review disposition: 5 Important and 1 Minor finding; no production code was changed.
- Authority correction: `AuthorityTier` now means only `government_official`, `central_mainstream_media`, or `provincial_official_media`; `AuthorityReviewStatus` is independently `pending_review`, `allowlisted`, or `rejected`; `ClaimRole` is independently `primary` or `supporting`. A non-whitelisted URL is `authority_tier = null`, `review_status = pending_review`. CCTV and Xinhua use the same expected central-media class after allowlisting and distinct intended claim roles.
- Migration correction: Task 01 observed a unique `e5c1b7d9a204` Alembic head. Task 2 now requires an execution-time one-head preflight, a fresh generated revision, and a `<generated_revision>` migration path rather than a stale fixed parent.
- Verdict correction: immutable CaseVerdictVersion proposal, approval, supersession, mutable-pointer, audit, closure, API, backfill, report-provenance, and no-dual-write contracts are now specified.
- Vendor correction: Brandwatch, Talkwalker, Pulsar, NewsWhip, and Blackbird are unverified comparison hypotheses with no captured capability statement and no design-evidence role. Their original source statuses remain recorded.
- Delivery/provenance correction: the existing concise progress-index pointer is force-added; both retained conversion manifests now use repository-relative source/output paths while preserving URL/hash/time/command/version/status provenance.

## Amendment Validation Record

| Command | Result |
| --- | --- |
| `Get-Content -Raw -Encoding utf8 'doc/research/case-workbench/source-metadata.json' \| ConvertFrom-Json` plus the Twitter manifest and both conversion manifests | Passed: all four changed JSON files parsed. |
| `Get-FileHash -Algorithm SHA256 'doc/research/case-workbench/sources/originals/bertopic-readme.html'` | Passed: `75B3C2CE622C33054678D099613A6AB63D1626F72F62AC6EB5208467A1E1E6B1`, matching source and conversion metadata. |
| `Get-FileHash -Algorithm SHA256 'doc/research/case-workbench/sources/originals/keybert-readme.html'` | Passed: `6EC3F46944A991695F8669F9BF7DB9F40C0F41FCFF4575E8B49E93708A3A2D25`, matching source and conversion metadata. |
| PowerShell provenance validator over retained metadata fields `source_path`, `output_markdown`, and `output_meta` | Passed: all three fields are repository-relative `doc/research/case-workbench/...` paths; converter URL/time/content-type/command/version/status and source hashes remain valid. |
| PowerShell forbidden-token scan over amended Task 01 design/plan/research/ledger/report files for the prior coupled taxonomy and stale fixed migration identifiers | Passed: no matches outside the retained independent-review artifact. Required taxonomy, CaseVerdictVersion, `<generated_revision>`, and `e5c1b7d9a204` terms are present. |
| `Select-String -Path <amended vendor prose> -Pattern 'Social listening\|Multi-source listening\|Audience intelligence\|Monitoring/alerting\|Narrative intelligence\|Vendor self-description\|useful for capability vocabulary'` | Passed: no unsupported vendor capability claims remain. The five recorded retrieval statuses remain unchanged. |
| PowerShell authored-relative-link validator over `progress.md`, Task 01 ledgers/reports, design, plan, and research Markdown | Passed: all local authored links resolve. Generated upstream conversion-image links remain intentionally outside this check. |
| `cd system/backend; python -m alembic heads` | Passed: `e5c1b7d9a204 (head)`; exactly one live head was observed. |
| `git diff --check` | Passed with exit code 0. Git emitted only CRLF-to-LF normalization warnings for working files; no whitespace error was reported. |

| `git diff --cached --check` | Passed with no output and exit code 0. |
| `git diff --cached --name-status` plus an exact allowed-path comparison | Passed: exactly 11 paths are staged: 10 Task 01 correction artifacts plus force-added `.superpowers/sdd/progress.md`. No protected/user-owned research path, production-code path, CSV, or full benchmark conversion is staged. |
| `git diff --quiet -- <11 authorized paths>` | Passed: no unstaged change remains in an authorized Task 01 path after staging. |

## Review Placeholder

- Task specification/quality review: fresh re-review required after the fix commit.
- No production-code review is required for this documentation-only task; implementation remains blocked on the documentation re-review.

## Commit Placeholder

- Commit: this report is included in the Task 01 Lore correction commit; the controller records its SHA in the handoff.
- Push: not performed and not authorized.
