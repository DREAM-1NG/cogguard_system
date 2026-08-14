# TypeScript And Vue Style Guide

- Keep route pages in `src/views/`, reusable visual modules in `src/components/`, and feature-local state/transformations in `src/features/`.
- Keep HTTP contracts in `src/api/`; do not construct backend URLs inside visual modules.
- Treat a semantic artifact as evidence assistance, never as a replacement for a product conclusion.
- Clear route-local data on event changes or unavailable artifacts; do not retain stale evidence.
- Use Chinese product copy and canonical domain terms from `UBIQUITOUS_LANGUAGE.md`.
- Preserve existing risk conclusions when adding visual evidence drill-downs.
- Verify with `npm test` and `npm run build` for frontend changes.
