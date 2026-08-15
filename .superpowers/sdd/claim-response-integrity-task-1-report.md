# Claim Response Integrity Task 1 Report

## Status

Implemented and verified.

## Scope

Task-owned files changed:

- `system/backend/app/services/claim_response_landscape_service.py`
- `system/backend/app/services/case_workbench_service.py`
- `system/backend/app/schemas/case_workbench.py`
- `system/backend/tests/test_claim_response_landscape_service.py`
- `system/backend/tests/test_case_workbench_mvp_service.py`
- `.superpowers/sdd/claim-response-integrity-task-1-report.md`

The worktree already contained many unrelated modified and untracked files before this task. I left them untouched and staged only the files listed above.

## Root-Cause Evidence

Observed in `claim_response_landscape_service._verified_paths_for_platform` before the fix:

- A path with `primary_claim_id` set and no `claim_id` was accepted because the filter only rejected present, mismatched IDs.
- Path anchoring used every returned official publication ref from allowlisted authority accounts, so a secondary post by the same bound account could validate a path for the primary claim.

Observed in case-workbench boundaries before the fix:

- `ClaimCreate` accepted whitespace-only `source_url`.
- `CaseWorkbenchService.add_claim` stored whitespace-only `source_url`.

## Red Test Evidence

Command:

```powershell
pytest tests/test_claim_response_landscape_service.py tests/test_case_workbench_mvp_service.py -q
```

Result before implementation:

```text
........FF......F.                                                       [100%]
FAILED tests/test_claim_response_landscape_service.py::test_landscape_excludes_path_without_primary_claim_id_even_when_primary_post_is_referenced
FAILED tests/test_claim_response_landscape_service.py::test_landscape_excludes_secondary_post_from_same_allowlisted_account
FAILED tests/test_case_workbench_mvp_service.py::test_claim_rejects_blank_source_url_at_schema_and_service_boundaries
3 failed, 15 passed, 2 warnings in 1.40s
```

Expected failures:

- `missing-claim-id` appeared in returned path refs.
- `secondary-official-post` appeared in returned path refs.
- Blank URL rejection reported `{"schema": False, "service": False}` instead of both `True`.

## Implementation

- Resolve the primary `CaseClaim.source_url` against loaded raw post `url` fields and convert matching real raw posts to normal refs like `weibo:post:p-official`.
- Require verified paths to have an exact non-blank `claim_id` matching the primary claim.
- Require verified paths to contain the primary claim source post ref, not merely any post from an allowlisted authority account.
- Preserve observed path `score`, `nodes`, and existing evidence refs; no risk score logic changed.
- Reject blank `source_url` in `ClaimCreate` and in `CaseWorkbenchService.add_claim`, trimming the accepted value at both boundaries.

One existing test expectation was updated: with no platform filter, an XHS path is now excluded when it does not contain the primary claim source post ref. This follows the new exact-original-post contract.

## Green Test Evidence

Command:

```powershell
pytest tests/test_claim_response_landscape_service.py tests/test_case_workbench_mvp_service.py -q
```

Result after implementation:

```text
..................                                                       [100%]
18 passed, 2 warnings in 0.45s
```

Warnings were pre-existing environment/config warnings:

- `TRANSFORMERS_CACHE` deprecation warning from `transformers`.
- Unknown pytest config option `asyncio_mode`.

## Documentation Sync

Checked:

```powershell
git grep -n "claim_response_landscape\|source_url" -- README.md system/README.md UBIQUITOUS_LANGUAGE.md doc/engineering/system-governance.md doc/engineering/development-log.md doc/engineering/development-roadmap.md
```

No matches were returned in those sync files, so no documentation update was needed for this scoped internal evidence-filtering and validation fix.

## Commit

Prepared as:

```text
fix(propagation): require exact claim path evidence
```

## Concerns

- The focused backend tests pass. I did not run the full backend suite because the task brief requested the focused command and the shared worktree contains many unrelated active edits.
- When no raw post URL matches the primary claim `source_url`, propagation paths for that claim are now excluded as unverified. That is intentional under the exact-original-post evidence contract, but seeded or imported cases must keep claim `source_url` aligned with raw post `url`.
