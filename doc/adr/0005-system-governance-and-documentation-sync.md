---
status: accepted
date: 2026-07-21
---

# System Governance And Documentation Sync

## Context

CogGuard is now developed through a mix of product code, ARIS research
workspaces, reference repositories, and agent-assisted coding sessions. Earlier
docs still contained stale paths such as `new-system/`, and new Student Review work
started to grow inside one large training file. Without a governance contract,
future iterations would keep drifting across terminology, package ownership,
and documentation.

## Decision

The project adopts a durable governance stack:

- `UBIQUITOUS_LANGUAGE.md` is the global vocabulary source.
- `doc/engineering/system-governance.md` is the code structure and documentation
  sync source.
- `doc/engineering/project-map.md` remains the repository boundary map.
- `docs/adr/` records durable architecture and method decisions.
- `AGENTS.md` and `CLAUDE.md` must instruct future agents to update docs when
  code or architecture changes.

Teacher Silver and Selective Student logic are split out of
`trainable_post.py` into focused modules:

- `system/backend/app/core/review/teacher_silver.py`
- `system/backend/app/core/review/selective_student.py`

`trainable_post.py` remains the shared post-feature and legacy view
experiment boundary, with lazy compatibility exports for the moved symbols.

## Consequences

- Future code changes must include documentation sync in the same task.
- New public modules should declare `__all__`.
- Lasting architecture or method decisions should get an ADR.
- The product root is `system/`; `new-system/` is historical wording and should
  not reappear in current governance docs.

## Rejected

- Keeping all Student and Teacher Silver logic inside `trainable_post.py`:
  rejected because it creates a monolithic file with mixed responsibilities.
- Treating documentation as a final manual-only step: rejected because agent
  sessions need synchronized docs to avoid repeating stale assumptions.
- Moving all package names in one pass: rejected because current branch still
  depends on `app.core.risk`; semantic package migration should remain a
  separate, tested change.
