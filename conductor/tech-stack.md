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
