from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.core.analysis import query_result_cache
from app.core.analysis.query_result_cache import (
    build_query_cache_key,
    clear_local_query_result_cache,
    get_or_build_query_result,
    put_query_result,
)
from app.services import coordination_model_service, propagation_observation_service


@pytest.mark.asyncio
async def test_query_cache_single_flight_builds_one_projection(monkeypatch):
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", False)
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_MAX_ENTRIES", 8)
    clear_local_query_result_cache()
    calls = 0

    async def builder():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return {"value": calls}

    key = build_query_cache_key("projection", "snapshot-a", "model-1")
    results = await asyncio.gather(
        *(get_or_build_query_result(key, builder) for _ in range(5))
    )

    assert calls == 1
    assert results == [{"value": 1}] * 5


@pytest.mark.asyncio
async def test_query_cache_key_changes_with_source_version(monkeypatch):
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", False)
    clear_local_query_result_cache()

    first = build_query_cache_key("propagation", "event-1", "fingerprint-a", 300)
    second = build_query_cache_key("propagation", "event-1", "fingerprint-b", 300)
    third = build_query_cache_key("propagation", "event-1", "fingerprint-a", 600)

    assert first != second
    assert first != third


@pytest.mark.asyncio
async def test_query_cache_applies_configured_redis_ttl(monkeypatch):
    class RecordingRedis:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, int | None]] = []

        async def set(self, key: str, payload: str, ex: int | None = None) -> bool:
            self.calls.append((key, payload, ex))
            return True

    redis = RecordingRedis()
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_TTL_SECONDS", 604800)
    monkeypatch.setattr(query_result_cache, "get_redis", lambda: redis)
    monkeypatch.setattr(query_result_cache, "_redis_disabled_until", 0.0)
    clear_local_query_result_cache()

    await put_query_result("cache-key", {"value": "projection"})

    assert len(redis.calls) == 1
    assert redis.calls[0][0] == "cache-key"
    assert redis.calls[0][2] == 604800


class _SourceCollection:
    def __init__(self, job_id: int):
        self.job_id = job_id

    async def count_documents(self, _query):
        return 1

    async def find_one(self, _query, _projection, sort=None):
        return {"_id": "row-1", "crawl_job_id": self.job_id}


@pytest.mark.asyncio
async def test_propagation_service_reuses_projection_until_ingestion_changes(monkeypatch):
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", False)
    clear_local_query_result_cache()
    posts = _SourceCollection(10)
    comments = _SourceCollection(10)
    mongo_db = {"raw_posts": posts, "raw_comments": comments}
    graph_calls = 0

    async def load_posts(*_args, **_kwargs):
        return [{"post_id": "p1"}]

    async def load_comments(*_args, **_kwargs):
        return []

    def build_graph(*_args, **_kwargs):
        nonlocal graph_calls
        graph_calls += 1
        return {"graph": {"nodes": []}}

    monkeypatch.setattr(propagation_observation_service, "get_mongo_db", lambda: mongo_db)
    monkeypatch.setattr(propagation_observation_service, "load_event_posts", load_posts)
    monkeypatch.setattr(propagation_observation_service, "load_event_comments", load_comments)
    monkeypatch.setattr(propagation_observation_service, "build_observed_propagation_graph", build_graph)

    await propagation_observation_service.analyze_observed_propagation(event_id="event-1")
    await propagation_observation_service.analyze_observed_propagation(event_id="event-1")
    assert graph_calls == 1

    posts.job_id = 11
    await propagation_observation_service.analyze_observed_propagation(event_id="event-1")
    assert graph_calls == 2


@pytest.mark.asyncio
async def test_coordination_latest_result_reuses_completed_run_projection(monkeypatch):
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", False)
    clear_local_query_result_cache()
    dataset = type(
        "Dataset",
        (),
        {
            "id": 7,
            "latest_run_id": 12,
            "source_type": "uploaded",
            "updated_at": None,
            "created_at": None,
            "metadata_json": "{}",
        },
    )()
    run = type(
        "Run",
        (),
        {"id": 12, "status": "completed", "finished_at": None, "created_at": None},
    )()
    artifact_reads = 0

    async def first_context(_db, _dataset_id):
        return dataset, run

    monkeypatch.setattr(coordination_model_service, "_load_dataset_and_latest_run", first_context)
    monkeypatch.setattr(
        coordination_model_service,
        "_load_run_result_pair",
        lambda _run: (artifact_reads.__class__ and _read_pair()),
    )

    def _read_pair():
        nonlocal artifact_reads
        artifact_reads += 1
        return {}, {}

    monkeypatch.setattr(
        coordination_model_service,
        "_build_result_snapshot",
        lambda *_args, **_kwargs: {"status": "completed", "dataset_id": 7},
    )

    first = await coordination_model_service.get_coordination_dataset_latest_result(object(), 7)
    second = await coordination_model_service.get_coordination_dataset_latest_result(object(), 7)
    assert first == second
    assert artifact_reads == 1
