# Technology Context

## Product stack

| Area | Technology | Source of truth |
| --- | --- | --- |
| Backend | Python 3.11+, FastAPI, Pydantic, SQLAlchemy, Alembic | `system/backend/pyproject.toml` |
| Data and work | MySQL, MongoDB, Redis, Celery | `system/docker-compose.yml`, backend settings |
| Frontend | Vue 3, TypeScript, Vite, Ant Design Vue, ECharts | `system/frontend/package.json` |
| Graph and ML | NetworkX, igraph, leidenalg, PyTorch, sentence-transformers, Transformers, scikit-learn | `system/backend/pyproject.toml` |
| Delivery | Docker Compose, Nginx static delivery, PowerShell operations | `system/deploy/`, `system/ops/`, `system/start-system.ps1` |

## Layout

- `system/backend/app/`: product backend code.
- `system/frontend/src/`: product frontend code.
- `system/research/`: system-readable research packages.
- `system/runtimes/`: executable vendored runtimes.
- `MediaCrawler-main/`, `NewsCrawler-main/`, `CooRTweet-master/`: Reference Boundaries only.

## Dependency policy

1. Reuse an existing dependency when it satisfies the need.
2. Add a dependency only with a documented product or research rationale.
3. Keep runtime dependencies out of reference trees.
4. Record new production dependencies in the corresponding package manifest and this file.

## Verification commands

```powershell
cd system\backend
uv run python -m pytest tests -q

cd ..\frontend
npm test
npm run build
```

## Frontend API client boundaries

- The default frontend `request` client is scoped to `/api/v1`.
- A v2 product module must create its own client with the exact v2 base URL,
  then use paths relative to that base. It must not append `/v2` beneath the
  default v1 client.
- The static Nginx delivery proxy forwards both `/api/v1` and `/api/v2`
  unchanged to the backend.

## Coordination projection cache

- Coordination archive replay results are cached with an explicit projection
  schema version. The current `coordination-latest-result-v3` key invalidates
  earlier cache entries that predate read-time reconstruction of stored member
  predictions into a group evidence projection.
- This cache is a rendering optimization only: it must not substitute for a
  compatible Detection artifact or generate a verdict where no persisted
  prediction exists.

## Review runtime dependencies and references

- The current Review Student implementation uses the existing PyTorch and
  Transformers stack and the existing sentence-transformers capability for
  offline rationale vectors.
- Review Teacher and RAG contracts are pure Python serializable interfaces;
  this coding stage adds no production dependency.
- Reference repositories are checked out under
  `G:\CISCN\references\cogguard-methods`. They are coding and protocol
  references only, are not imported by `system/`, and are not runtime
  dependencies.
- No external LLM provider or API key is needed for the current checks.

The HateCoT MARO-compatible runner reuses the existing DeepSeek provider
adapter when a later live experiment explicitly enables it. The coding and
dry-run path adds no dependency and performs no provider call. Analysis caches,
split manifests, and reports are experiment artifacts under the G-drive output
root; they are not production model state. Resume authorization is based on a
protocol hash rather than an implicit cache hit.
