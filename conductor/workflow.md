# Development Workflow

## Before a change

1. Confirm the active worktree, branch, and dirty files with Git.
2. Read `conductor/index.md`, the relevant ADRs, and the active track.
3. Treat existing dirty changes as user-owned unless their origin is known.
4. Define the behavior and test surface before changing implementation.

## Implementation

- Keep one business concept per module where practical.
- Use explicit `__all__` for public Python package surfaces.
- Keep a compatibility alias as a mapping only; new business logic belongs in its canonical module.
- Keep application interfaces small and move complexity behind an appropriate seam.
- Add targeted tests first for changed behavior, then run broader relevant gates.

## Review and documentation

- For structural work, use one implementation task at a time followed by specification and quality review.
- Do not advance with Critical or Important review findings unresolved.
- Update `CONTEXT.md`, `UBIQUITOUS_LANGUAGE.md`, governance documentation, and an ADR only when the change actually affects them.
- Update `conductor/tracks.md` when a structural track changes state.

## Git and recovery

- This checkout is a linked worktree. Do not create a nested worktree.
- Never reset, clean, or overwrite unrelated dirty files.
- Stage only files owned by the current task.
- Keep an external snapshot or an intentional commit before any broad migration.
- Use the repository's Lore commit protocol for task commits.
