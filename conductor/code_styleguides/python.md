# Python Style Guide

- Use absolute imports rooted at `app` for product backend modules.
- Use `snake_case` files, `PascalCase` types, and `UPPER_SNAKE_CASE` constants.
- Keep Pydantic contracts in `app/schemas/`, persisted records in `app/models/`, and orchestration in canonical `app/core/` or `app/services/` modules.
- Define `__all__` for public package interfaces; imports outside it are implementation details.
- Depend inward: route handlers adapt HTTP, application modules orchestrate, and adapters own external systems.
- Prefer typed immutable input/output records over hidden mutation.
- Test behavior through the public module interface; do not make internal helpers public solely for tests.
- Do not import reference-boundary repositories from product code.
