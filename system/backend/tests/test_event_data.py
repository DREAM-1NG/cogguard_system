from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.event_data import load_event_account_names


class _Cursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.length: int | None = None

    async def to_list(self, *, length: int) -> list[dict[str, object]]:
        self.length = length
        return self.rows[:length]


class _Collection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.cursor = _Cursor(rows)
        self.query: dict[str, object] | None = None
        self.projection: dict[str, int] | None = None

    def find(self, query: dict[str, object], projection: dict[str, int]) -> _Cursor:
        self.query = query
        self.projection = projection
        return self.cursor


def test_account_name_projection_reads_only_requested_event_accounts():
    async def scenario() -> None:
        collection = _Collection(
            [
                {"author_id": "account-a", "author_name": "Analyst A"},
                {"author_id": "account-b", "author_name": ""},
                {"author_id": "account-b", "author_name": "Analyst B"},
                {"author_id": "account-c", "author_name": "Ignored"},
            ]
        )

        names = await load_event_account_names(
            {"raw_posts": collection},
            event_id="event-1",
            account_ids=["account-a", "account-b", "account-a", ""],
        )

        assert names == {"account-a": "Analyst A", "account-b": "Analyst B"}
        assert collection.query == {
            "event_id": "event-1",
            "author_id": {"$in": ["account-a", "account-b"]},
        }
        assert collection.projection == {"_id": 0, "author_id": 1, "author_name": 1}
        assert collection.cursor.length == 100

    asyncio.run(scenario())


def test_account_name_projection_has_a_managed_event_account_index():
    index_script = (
        Path(__file__).resolve().parents[2]
        / "ops"
        / "mongo"
        / "apply_performance_indexes.js"
    ).read_text(encoding="utf-8")

    assert "ix_raw_posts_event_author_id" in index_script
    assert "key: { event_id: 1, author_id: 1 }" in index_script
