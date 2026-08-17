# Plan

- [x] Read the propagation page, evidence-chain contract, and frontend test conventions.
- [x] Add a compact ECharts ignition overview fed only by direct evidence-chain edges.
- [x] Add a frontend contract test and run type validation.
- [x] Run the production build and record validation results.

Validation: `npm.cmd test -- propagation-path-graph-contract.spec.mjs` (76 passed),
`npx.cmd vue-tsc -b --pretty false`, `npm.cmd run build`, and
`node scripts/verify-build.mjs` all passed on 2026-08-15. The local browser
check reached the expected authentication screen; no account was used to
bypass authentication for an authenticated role-tab screenshot.
