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
- Coordination experiment artifacts, model bundles, manifests, and reports must stay under the G-drive worktree or dataset roots; C-drive output paths fail closed.

## Review and documentation

- For structural work, use one implementation task at a time followed by specification and quality review.
- Do not advance with Critical or Important review findings unresolved.
- Update `CONTEXT.md`, `UBIQUITOUS_LANGUAGE.md`, governance documentation, and an ADR only when the change actually affects them.
- Update `conductor/tracks.md` when a structural track changes state.
- When Coordination Detection changes, document whether a result is the primary SocGFM path, a shadow classifier output, a heuristic baseline, or a research-only method.
- When an archive artifact is projected at read time, record whether its group
  evidence comes from persisted member predictions or is explicitly
  unavailable. Never describe that projection as a fresh neural inference or a
  final analyst decision.

## Git and recovery

- This checkout is a linked worktree. Do not create a nested worktree.
- Never reset, clean, or overwrite unrelated dirty files.
- Stage only files owned by the current task.
- Keep an external snapshot or an intentional commit before any broad migration.
- Use the repository's Lore commit protocol for task commits.

## Review implementation sequence

For the MARO Teacher + Review Student boundary, use this order:

1. Define typed contracts and explicit public module surfaces.
2. Add focused unit tests for task routing, quality gates, and call bounds.
3. Implement runtime adapters and offline hard-case manifest generation.
4. Synchronize `CONTEXT.md`, `UBIQUITOUS_LANGUAGE.md`, the relevant ADR, and
   research implementation notes.
5. Run syntax checks and targeted tests without training data, external LLM
   calls, or performance experiments.
6. Only a later, explicitly scoped experiment track may call Teacher in batch
  or train Student artifacts.

## HateCoT MARO experiment sequence

For the expanded HateCoT harm adaptation, the order is fixed:

1. Build and hash the source-train/source-dev/held-out-target manifests.
2. Run the no-provider dry-run and verify label counts, case-ID disjointness,
   demonstration isolation, and policy-arm namespacing.
3. Generate the candidate rule pool from source-train strict improvements only.
4. Rank that fixed pool on source-dev Macro-F1, then run the held-out target
   test with exactly three rule votes per case.
5. Run `local_advisory` only as a separate ablation with the same manifests.
6. Audit provider failures, retries, cache hits, prompt boundaries, and hashes
   before reporting metrics.

The primary arm is policy-off. A failed Judge is a failed run, never a hidden
abstention or a reduced metric denominator. A resumed run must use `--resume`
and an exact Fold Protocol Hash.
