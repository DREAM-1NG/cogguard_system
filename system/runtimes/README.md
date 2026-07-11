# Vendored Runtime Attribution

This directory contains the crawler runtimes that CogGuard executes directly.

## social_runtime

- Source lineage: `MediaCrawler-main/`
- Purpose: internal social crawl runtime for `weibo`, `douyin`, and `xhs`
- Scope kept in-tree: entrypoint, config, shared libs, store/tools, required platform adapters, and direct shared dependencies
- Scope intentionally excluded: API layer, docs, tests, unused platforms, and upstream scaffolding
- License / attribution: preserved via `system/runtimes/social_runtime/LICENSE`

## news_runtime

- Source lineage: `NewsCrawler-main/`
- Purpose: internal URL-based news extraction runtime
- Scope kept in-tree: `news_extractor_core`, detector wiring, registered adapters, and direct support libs
- Scope intentionally excluded: backend service, UI, MCP, Docker, and unrelated top-level tools
- License / attribution: preserved via `system/runtimes/news_runtime/LICENSE`

## License / Distribution

- `social_runtime` follows the upstream non-commercial learning/research license and must not be treated as permissive commercial code.
- `news_runtime` is GPL-3.0.
- Distributors must review combined-work obligations before redistribution and preserve all upstream attribution and license files.

## Policy

- Product code must call these vendored runtimes, not the upstream reference directories.
- Upstream directories remain in the repo only for provenance, auditing, and selective diffing.
