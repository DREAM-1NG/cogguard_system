# Key Propagation Path Delivery Plan

1. Add a backend key-path projection derived from the full observed graph:
   select evidence-backed role accounts, retain real ancestor closure, and
   preserve independent components as separate islands.
2. Add a scoped branch endpoint that returns the selected node's complete
   observable descendant subgraph without synthetic edges.
3. Make `/propagation` render that projection by default and add deterministic
   branch expand/collapse handling.
4. Reset branch state on scope changes; retain existing node evidence drawer.
5. Add backend/frontend contract tests, update product terminology, and run
   propagation tests, TypeScript checks, and the production build.
