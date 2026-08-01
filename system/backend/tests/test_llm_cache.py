"""Tests for the LLM response replay cache.

The cache exists so a walkthrough survives a slow or unreachable provider. Its
integrity rule matters more than its hit rate: a replayed answer must always be
something the model actually returned, never fabricated text.
"""

from __future__ import annotations

import json

import pytest

from app.config import settings
from app.core import llm_cache

CHANNEL = "review.agent.PostHarmAgent"
PAYLOAD = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE_ROOT", str(tmp_path))
    return tmp_path


def _key() -> str:
    return llm_cache.response_cache_key(channel=CHANNEL, model="m", payload=PAYLOAD)


def test_cache_key_is_stable_and_separates_channels_models_and_payloads():
    base = _key()

    assert base == _key()
    assert base != llm_cache.response_cache_key(
        channel="propagation.event_extraction", model="m", payload=PAYLOAD
    )
    assert base != llm_cache.response_cache_key(channel=CHANNEL, model="other", payload=PAYLOAD)
    assert base != llm_cache.response_cache_key(
        channel=CHANNEL, model="m", payload={**PAYLOAD, "temperature": 0.9}
    )
    # Keys go on disk as filenames, so they must stay filesystem-safe.
    assert all(ch.isalnum() or ch in {"-", "_"} for ch in base)


def test_key_order_of_payload_fields_does_not_change_the_key():
    reordered = {"messages": PAYLOAD["messages"], "model": PAYLOAD["model"]}

    assert llm_cache.response_cache_key(channel=CHANNEL, model="m", payload=reordered) == _key()


def test_off_mode_neither_records_nor_replays(cache_dir, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "off")

    llm_cache.record_response(_key(), "real response", channel=CHANNEL, model="m")

    assert list(cache_dir.iterdir()) == []
    assert llm_cache.load_cached_response(_key()) is None


def test_record_mode_persists_without_serving_replays(cache_dir, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "record")

    llm_cache.record_response(_key(), "real response", channel=CHANNEL, model="m")

    assert len(list(cache_dir.glob("*.json"))) == 1
    # Recording is for a later replay run; it must not short-circuit this one.
    assert llm_cache.load_cached_response(_key()) is None


def test_replay_mode_returns_recorded_response_and_reports_misses(cache_dir, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "record")
    llm_cache.record_response(_key(), "real response", channel=CHANNEL, model="m")

    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "replay")

    assert llm_cache.load_cached_response(_key()) == "real response"
    assert llm_cache.load_cached_response("review_agent-does-not-exist") is None


def test_replay_refuses_entries_not_recorded_from_a_live_call(cache_dir, monkeypatch):
    """A hand-authored entry must never be replayed as if the model said it."""
    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "replay")
    key = _key()
    (cache_dir / f"{key}.json").write_text(
        json.dumps(
            {
                "schema": llm_cache.CACHE_SCHEMA,
                "key": key,
                "channel": CHANNEL,
                "model": "m",
                "response": "hand-written answer",
                "recorded_from_live_call": False,
            }
        ),
        encoding="utf-8",
    )

    assert llm_cache.load_cached_response(key) is None


def test_replay_ignores_unknown_schema_empty_and_corrupt_entries(cache_dir, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "replay")
    key = _key()
    path = cache_dir / f"{key}.json"

    path.write_text("{not json", encoding="utf-8")
    assert llm_cache.load_cached_response(key) is None

    path.write_text(
        json.dumps({"schema": "other.schema.v9", "response": "x", "recorded_from_live_call": True}),
        encoding="utf-8",
    )
    assert llm_cache.load_cached_response(key) is None

    path.write_text(
        json.dumps(
            {"schema": llm_cache.CACHE_SCHEMA, "response": "   ", "recorded_from_live_call": True}
        ),
        encoding="utf-8",
    )
    assert llm_cache.load_cached_response(key) is None


def test_blank_responses_are_never_recorded(cache_dir, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "record")

    llm_cache.record_response(_key(), "   ", channel=CHANNEL, model="m")

    assert list(cache_dir.glob("*.json")) == []


def test_unknown_mode_falls_back_to_off(monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "aggressive")

    assert llm_cache.cache_mode() == "off"


def test_cache_stats_reports_mode_and_per_channel_counts(cache_dir, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE_MODE", "record")
    llm_cache.record_response(_key(), "a", channel=CHANNEL, model="m")
    llm_cache.record_response(
        llm_cache.response_cache_key(
            channel="propagation.event_extraction", model="m", payload=PAYLOAD
        ),
        "b",
        channel="propagation.event_extraction",
        model="m",
    )

    stats = llm_cache.cache_stats()

    assert stats["mode"] == "record"
    assert stats["entry_count"] == 2
    assert stats["channels"] == {CHANNEL: 1, "propagation.event_extraction": 1}
