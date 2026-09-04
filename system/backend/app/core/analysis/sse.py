from __future__ import annotations

import json
from typing import Any


def format_sse_event(event: dict[str, Any]) -> str:
    event_id = int(event["id"])
    event_type = str(event.get("event_type") or "message")
    data = {
        "run_id": event.get("run_id"),
        "status": event.get("status"),
        "payload": event.get("payload") or {},
    }
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"
    )


async def iter_sse_events(events: list[dict[str, Any]]):
    for event in events:
        yield format_sse_event(event)


def parse_last_event_id(value: str | None, *, fallback: int = 0) -> int:
    text = str(value or "").strip()
    if not text:
        return max(0, int(fallback or 0))
    try:
        return max(0, int(text))
    except ValueError:
        return max(0, int(fallback or 0))
