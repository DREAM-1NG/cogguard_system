# Tech Stack

## Backend

- Python 3.11+
- FastAPI 0.115+
- Pydantic 2+
- SQLAlchemy 2 async + Alembic
- MySQL 8、MongoDB 7、Redis 7、Celery 5
- NumPy、pandas、NetworkX、igraph、LeidenAlg
- PyTorch 2.3+、Transformers 4.45+、Sentence Transformers 3+

后端依赖以 `system/backend/pyproject.toml` 为唯一编辑源；`requirements.txt` 由 `uv export` 生成，不允许手工漂移。

## Frontend

- Vue 3.5、TypeScript 5.6、Vite 6
- Vue Router、Pinia、Ant Design Vue
- ECharts、Three.js、3d-force-graph

Canonical 前端位于 `system/frontend/`；`system/frontend-sandbox/` 不是产品源码根。

## Quality Tools

- pytest / pytest-asyncio
- vue-tsc + Vite production build
- `git diff --check`
- Alembic single-head 与 upgrade smoke

## Constraints

- 不为本 track 新增第三方依赖。
- Product System 不得从 Reference Boundary 直接 import 或修改 `sys.path`。
- 模型、数据集、缓存、截图和运行输出不进入最终 PR。
