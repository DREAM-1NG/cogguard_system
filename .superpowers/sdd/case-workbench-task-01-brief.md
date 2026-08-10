# Case Workbench Task 01 Brief

## Objective

Create an auditable documentation and research baseline for the CogGuard Case Workbench, then make one documentation-only Lore commit on `refactor-system` without pushing.

## Required Outputs

1. `docs/superpowers/specs/2026-08-10-case-workbench-design.md`
2. `docs/superpowers/plans/2026-08-10-case-workbench.md`
3. `doc/research/case-workbench/` with index, implementation comparison, model governance, Twitter metadata-only manifest, source metadata, retained originals, and MarkItDown conversions.
4. `.superpowers/sdd/case-workbench-progress.md` plus this brief/report and a concise pointer appended to the existing `progress.md`.

## Hard Constraints

- Rollback baseline is `425a8f2`.
- Do not edit/stage `system/doc/research/propagation_paper_deep_reads/README.md` or `system/doc/research/propagation_paper_deep_reads/propagation_sota_stable_matrix_report_20260810.md`.
- Do not change production code.
- Do not commit the Twitter CSV or a full Markdown conversion.
- Source provenance must not claim a download/conversion that did not succeed.
- Use the Lore Commit Protocol and do not push.

## Required Verification

- Parse all new/modified JSON.
- Recompute retained-source SHA-256 values against metadata.
- Confirm conversions have source URL/retrieval provenance/content type/command/version/status.
- Check Markdown relative links and `git diff --check`.
- Confirm the staged set excludes the two protected dirty files.
