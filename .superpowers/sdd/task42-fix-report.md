# Task 42 Fix Report

## Change

- Moved `semanticAssistancePanel` from the Overview tab's `事件证据` panel to
  the Evidence Matrix tab's `语义辅助` panel in
  `system/frontend/src/views/cases/index.vue`.
- Kept `openActionEvidenceRef` unchanged: selecting
  `semantic_case_workbench_demo` still switches to the `evidence` tab and
  scrolls the semantic-assistance panel into view.
- Strengthened the frontend contract test so it requires the ref and
  `语义辅助` title to be adjacent in the template. This prevents a future ref
  placement on an unrelated panel from satisfying the drill-down contract.

## TDD Evidence

1. RED: temporarily restored the old wrong anchor placement and ran:

   ```powershell
   python -m pytest tests/test_case_frontend_mvp_contract.py::test_case_action_evidence_refs_can_drill_down_to_semantic_assistance -q
   ```

   Output: `1 failed`; the expected failure was the new assertion that could
   not find `ref="semanticAssistancePanel"` immediately before `语义辅助`.

2. GREEN: restored the ref on the semantic-assistance panel and reran the same
   command.

   Output: `1 passed, 3 warnings in 0.05s`.

## Verification

```powershell
python -m pytest tests/test_case_frontend_mvp_contract.py -q
```

Output: `17 passed, 3 warnings in 0.15s`.

```powershell
npm run build
```

Output: `vue-tsc -b` and Vite production build completed successfully;
`4253 modules transformed`, `built in 1m 43s`.

```powershell
git diff --check
```

Output: exit code 0.

## Warnings And Risks

- Pytest emitted existing environment warnings for an ephemeral unset
  `JWT_SECRET_KEY`, the deprecated `TRANSFORMERS_CACHE` setting, and unknown
  `asyncio_mode`; none are caused by this template-only change.
- Vite emitted pre-existing chunk-size warnings for bundles above 500 kB.
- The change is covered by a static frontend contract and TypeScript/Vite build;
  no browser end-to-end interaction test was run in this scoped task.
- No files under `MediaCrawler-main`, `NewsCrawler-main`, or
  `CooRTweet-master` were modified.
