"""Replay cache for LLM responses.

A live walkthrough should not fail because an upstream API is slow, rate
limited, or unreachable. This module records genuine successful responses and
replays them on a later identical request.

Integrity rule: the cache is only ever written from a real successful provider
response. Nothing in this module fabricates model output, and a cache miss is
reported as a miss rather than being filled with a plausible-looking answer. A
replayed response is therefore always something the model actually returned.

Modes (``settings.LLM_CACHE_MODE``):

``off``
    No caching. Every call goes to the provider.
``record``
    Call the provider, then persist each successful response.
``replay``
    Serve a matching recorded response when one exists; otherwise call the
    provider and record the result, so a replay run self-heals on new inputs.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

__all__ = [
    "cache_mode",
    "cache_root",
    "cache_stats",
    "load_cached_response",
    "record_response",
    "response_cache_key",
]

logger = logging.getLogger(__name__)

_OFF = "off"
_REPLAY = "replay"
_RECORD = "record"
_VALID_MODES = (_OFF, _REPLAY, _RECORD)

CACHE_SCHEMA = "cogguard.llm.response_cache.v1"


def cache_mode() -> str:
    """Return the normalized cache mode, defaulting to ``off``."""
    mode = str(getattr(settings, "LLM_CACHE_MODE", _OFF) or _OFF).strip().lower()
    return mode if mode in _VALID_MODES else _OFF


def cache_root() -> Path:
    return Path(str(getattr(settings, "LLM_CACHE_ROOT", "") or "")).expanduser()


def response_cache_key(
    *,
    channel: str,
    model: str,
    payload: Any,
) -> str:
    """Build a stable key for one logical LLM request.

    ``channel`` separates callers that happen to share a model (for example
    propagation event extraction versus a named review agent) so their caches
    cannot collide.
    """

    canonical = json.dumps(
        {"channel": channel, "model": model, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{_safe_segment(channel)}-{digest[:32]}"


def _safe_segment(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "").strip())
    return cleaned[:60] or "unknown"


def _entry_path(key: str) -> Path:
    return cache_root() / f"{key}.json"


def load_cached_response(key: str) -> str | None:
    """Return a recorded response for ``key``, or ``None`` on a miss."""
    if cache_mode() != _REPLAY:
        return None
    path = _entry_path(key)
    if not path.is_file():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Ignoring unreadable LLM cache entry: %s", path.name)
        return None
    if entry.get("schema") != CACHE_SCHEMA:
        return None
    response = entry.get("response")
    if not isinstance(response, str) or not response.strip():
        return None
    if not entry.get("recorded_from_live_call"):
        # Defensive: refuse anything not marked as a genuine recorded response.
        logger.warning("Ignoring LLM cache entry not recorded from a live call: %s", path.name)
        return None
    return response


def record_response(
    key: str,
    response: str,
    *,
    channel: str,
    model: str,
) -> None:
    """Persist a genuine successful provider response.

    Failures to write are logged and swallowed: caching is an availability aid,
    never a reason to fail a request that already succeeded.
    """

    if cache_mode() == _OFF:
        return
    if not isinstance(response, str) or not response.strip():
        return
    entry = {
        "schema": CACHE_SCHEMA,
        "key": key,
        "channel": channel,
        "model": model,
        "response": response,
        "recorded_from_live_call": True,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        root = cache_root()
        root.mkdir(parents=True, exist_ok=True)
        _entry_path(key).write_text(
            json.dumps(entry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not write LLM cache entry %s: %s", key, exc)


def cache_stats() -> dict[str, Any]:
    """Summarize the cache for status endpoints and demo disclosure."""
    root = cache_root()
    entries = sorted(root.glob("*.json")) if root.is_dir() else []
    channels: dict[str, int] = {}
    for path in entries:
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        channel = str(entry.get("channel") or "unknown")
        channels[channel] = channels.get(channel, 0) + 1
    return {
        "schema": CACHE_SCHEMA,
        "mode": cache_mode(),
        "root": str(root),
        "entry_count": len(entries),
        "channels": channels,
        "integrity": "entries are recorded from real successful provider responses only",
    }
