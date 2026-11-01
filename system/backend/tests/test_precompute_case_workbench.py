from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.analysis import TimeWindow, build_event_snapshot
from app.core.analysis.semantic_enrichment import (
    analyze_semantic_enrichment_snapshot,
    refresh_semantic_artifact_hash,
)
from app.services.case_frozen_artifact import FrozenArtifactError, build_frozen_case_artifact
from scripts import precompute_case_workbench as precompute


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def to_list(self, *, length: int | None) -> list[dict[str, Any]]:
        return list(self.rows)


class FakeCollection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.queries: list[dict[str, Any]] = []

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> FakeCursor:
        self.queries.append(query)
        return FakeCursor(self.rows)


class FakeSemanticRuntime:
    runtime_backend = "fake_lm_encoder"
    cache_dir = "test-cache"
    device = "cpu"
    model_versions = {
        "embedding": "embedding-test",
        "sentiment": "sentiment-test",
        "stance": "stance-test",
        "ner": "ner-test",
    }

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if index % 2 == 0 else [0.0, 1.0] for index, _text in enumerate(texts)]

    def classify_sentiment(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"label": "positive", "score": 0.9} for _row in rows]

    def classify_stance(self, rows: list[dict[str, Any]], primary_claim: str) -> list[dict[str, Any]]:
        return [{"label": "support", "score": 0.8} for _row in rows]

    def extract_entities(self, rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        return [[{"entity": "Trump", "entity_type": "person", "score": 0.9}] for _row in rows]


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


def _snapshot():
    return build_event_snapshot(
        event_id=precompute.DEFAULT_EVENT_ID,
        posts=[
            {
                "event_id": precompute.DEFAULT_EVENT_ID,
                "platform": "weibo",
                "crawl_job_id": 4,
                "post_id": "source",
                "author_id": "author-source",
                "timestamp": _dt(14),
                "content": "source evidence",
            },
            {
                "event_id": precompute.DEFAULT_EVENT_ID,
                "platform": "weibo",
                "crawl_job_id": 4,
                "post_id": "target",
                "author_id": "author-target",
                "timestamp": _dt(14, 1),
                "content": "target evidence",
                "repost_id": "source",
            },
        ],
        comments=[
            {
                "event_id": precompute.DEFAULT_EVENT_ID,
                "platform": "weibo",
                "crawl_job_id": 4,
                "comment_id": "reply",
                "post_id": "target",
                "reply_to": "target",
                "author_id": "author-reply",
                "timestamp": _dt(14, 2),
                "content": "reply evidence",
            }
        ],
        core_window=TimeWindow(start=_dt(11), end=_dt(22)),
        context_window=TimeWindow(start=_dt(1), end=_dt(31)),
    )


def _scope_rows(kind: str) -> list[dict[str, Any]]:
    counts = precompute.EXPECTED_TRUMP_VISIT_IMPORT_SCOPE[kind]
    rows: list[dict[str, Any]] = []
    for platform, expected in counts.items():
        for index in range(expected["count"]):
            rows.append(
                {
                    "event_id": precompute.DEFAULT_EVENT_ID,
                    "platform": platform,
                    "crawl_job_id": expected["crawl_job_id"],
                }
            )
    return rows


def _normalized_scope_rows(kind: str, *, historical_xhs_rows: int = 0) -> list[dict[str, Any]]:
    counts = precompute.EXPECTED_TRUMP_VISIT_IMPORT_SCOPE[kind]
    id_field = "post_id" if kind == "posts" else "comment_id"
    rows: list[dict[str, Any]] = []
    for platform, expected in counts.items():
        for index in range(expected["count"]):
            rows.append(
                {
                    "event_id": precompute.DEFAULT_EVENT_ID,
                    "platform": platform,
                    "crawl_job_id": expected["crawl_job_id"],
                    id_field: f"{platform}-{kind}-{index}",
                    "author_id": f"{platform}-author-{index}",
                    "timestamp": (
                        "2025-02-13T05:47:33+00:00"
                        if platform == "xhs" and index < historical_xhs_rows
                        else "2026-05-14T12:00:00+00:00"
                    ),
                    "content": f"{platform} {kind} {index}",
                }
            )
    return rows


def _patch_precompute_before_runtime(monkeypatch, posts, comments):
    async def close_mongo() -> None:
        return None

    monkeypatch.setattr(
        precompute,
        "get_mongo_db",
        lambda: {"raw_posts": FakeCollection(posts), "raw_comments": FakeCollection(comments)},
    )
    monkeypatch.setattr(precompute, "close_mongo", close_mongo)
    monkeypatch.setattr(precompute, "_attach_archived_coordination_communities", lambda _posts: None)
    monkeypatch.setattr(
        precompute,
        "_authority_claims",
        lambda: [{"claim_id": "claim_primary", "role": "primary"}],
    )


def test_trump_visit_precompute_preserves_historical_xhs_rows_through_snapshot(monkeypatch, tmp_path):
    posts = _normalized_scope_rows("posts", historical_xhs_rows=12)
    comments = _normalized_scope_rows("comments", historical_xhs_rows=231)
    captured_counts: dict[str, int] = {}
    real_build_event_snapshot = precompute.build_event_snapshot

    def capture_snapshot(**kwargs):
        snapshot = real_build_event_snapshot(**kwargs)
        captured_counts["posts"] = len(snapshot.posts)
        captured_counts["comments"] = len(snapshot.comments)
        return snapshot

    class StopAfterSnapshot(RuntimeError):
        pass

    def stop_before_model_runtime():
        raise StopAfterSnapshot("snapshot constructed")

    _patch_precompute_before_runtime(monkeypatch, posts, comments)
    monkeypatch.setattr(precompute, "build_event_snapshot", capture_snapshot)
    monkeypatch.setattr(precompute, "HuggingFaceSemanticRuntime", stop_before_model_runtime)

    with pytest.raises(StopAfterSnapshot, match="snapshot constructed"):
        asyncio.run(precompute.precompute_trump_visit_case(output_root=tmp_path))

    assert captured_counts == {"posts": 294, "comments": 14_722}


def test_trump_visit_precompute_rejects_snapshot_loss_before_model_runtime(monkeypatch, tmp_path):
    posts = _normalized_scope_rows("posts")
    comments = _normalized_scope_rows("comments")
    posts[1]["post_id"] = posts[0]["post_id"]
    runtime_initialized = False
    artifact_write_attempted = False

    def initialize_runtime():
        nonlocal runtime_initialized
        runtime_initialized = True
        raise AssertionError("model runtime must not start after snapshot normalization loss")

    def fail_on_artifact_write(self, artifact):
        nonlocal artifact_write_attempted
        artifact_write_attempted = True
        raise AssertionError("frozen artifact must not be written after snapshot normalization loss")

    _patch_precompute_before_runtime(monkeypatch, posts, comments)
    monkeypatch.setattr(precompute, "HuggingFaceSemanticRuntime", initialize_runtime)
    monkeypatch.setattr(precompute.FrozenCaseArtifactStore, "write", fail_on_artifact_write)

    with pytest.raises(
        FrozenArtifactError,
        match=(
            "EventSnapshot normalization excluded imported records: expected 294 posts and 14,722 comments; "
            "actual 293 posts and 14,722 comments"
        ),
    ):
        asyncio.run(precompute.precompute_trump_visit_case(output_root=tmp_path))

    assert runtime_initialized is False
    assert artifact_write_attempted is False
    assert not any(tmp_path.iterdir())


def test_trump_visit_cli_defaults_to_the_three_imported_jobs():
    args = precompute._build_parser().parse_args(["--trump-visit"])

    assert args.crawl_job_ids == precompute.DEFAULT_TRUMP_VISIT_CRAWL_JOB_IDS


def test_trump_visit_precompute_queries_only_the_default_import_scope(monkeypatch, tmp_path):
    posts = FakeCollection([])
    comments = FakeCollection([])

    async def close_mongo() -> None:
        return None

    monkeypatch.setattr(precompute, "get_mongo_db", lambda: {"raw_posts": posts, "raw_comments": comments})
    monkeypatch.setattr(precompute, "close_mongo", close_mongo)

    with pytest.raises(FrozenArtifactError, match="expected three-platform import scope is incomplete or contaminated"):
        asyncio.run(precompute.precompute_trump_visit_case(output_root=tmp_path))

    expected_query = {
        "event_id": precompute.DEFAULT_EVENT_ID,
        "crawl_job_id": {"$in": [4, 5, 6]},
    }
    assert posts.queries == [expected_query]
    assert comments.queries == [expected_query]


def test_trump_visit_precompute_rejects_limit_before_querying_mongo(monkeypatch, tmp_path):
    called = False

    def get_mongo_db():
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(precompute, "get_mongo_db", get_mongo_db)

    with pytest.raises(FrozenArtifactError, match="expected three-platform import scope is incomplete or contaminated"):
        asyncio.run(precompute.precompute_trump_visit_case(output_root=tmp_path, limit=1))

    assert called is False


def test_trump_visit_scope_guard_rejects_historical_weibo_contamination():
    posts = _scope_rows("posts")
    comments = _scope_rows("comments")

    precompute._validate_trump_visit_import_scope(posts, comments, crawl_job_ids=[4, 5, 6])

    posts.append(
        {
            "event_id": precompute.DEFAULT_EVENT_ID,
            "platform": "weibo",
            "crawl_job_id": 0,
        }
    )
    with pytest.raises(FrozenArtifactError, match="expected three-platform import scope is incomplete or contaminated"):
        precompute._validate_trump_visit_import_scope(posts, comments, crawl_job_ids=[4, 5, 6])


def test_observed_propagation_persists_matched_runtime_semantic_overlays_in_frozen_artifact():
    snapshot = _snapshot()
    semantic = analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim": {"excerpt": "A verified claim"}},
        runtime=FakeSemanticRuntime(),
    )

    propagation = precompute._observed_propagation(
        snapshot,
        semantic=semantic,
        primary_claim_ref="claim_primary",
    )

    assert propagation["paths"]
    assert all(path["source_ref"] and path["target_ref"] for path in propagation["paths"])
    assert all(path["evidence_refs"] for path in propagation["paths"])
    assert all(path["semantic_overlay"]["status"] == "available" for path in propagation["paths"])
    assert all(path["semantic_overlay"]["sentiment"] for path in propagation["paths"])
    assert all(path["semantic_overlay"]["stance"] for path in propagation["paths"])
    assert all(path["semantic_overlay"]["keywords"] for path in propagation["paths"])
    assert all(path["semantic_overlay"]["entities"] for path in propagation["paths"])
    assert all(path["semantic_overlay"]["platforms"] for path in propagation["paths"])
    assert all(path["semantic_overlay"]["time_range"]["start"] for path in propagation["paths"])
    assert all(path["semantic_overlay"]["claim_refs"] == ["claim_primary"] for path in propagation["paths"])
    assert semantic["cross_analysis"]["propagation_path_overlays"]
    artifact_hash = semantic["artifact_sha256"]
    refresh_semantic_artifact_hash(semantic)
    assert semantic["artifact_sha256"] == artifact_hash

    artifact = build_frozen_case_artifact(
        case_id=precompute.DEFAULT_CASE_ID,
        event_id=precompute.DEFAULT_EVENT_ID,
        normalized_records={"posts": snapshot.posts, "comments": snapshot.comments},
        runtime_info={
            "runtime_status": "ok",
            "runtime_backend": "fake_lm_encoder",
            "device": "cpu",
            "model_versions": FakeSemanticRuntime.model_versions,
            "run_id": "test-runtime",
        },
        authority_claims=[{"claim_id": "claim_primary", "role": "primary"}],
        coordination={"status": "precomputed", "risk_score": 0.2},
        propagation=propagation,
        semantic={key: value for key, value in semantic.items() if key != "_runtime_rows"},
        review={"risk_score": 0.1},
    )

    assert artifact["semantic"]["cross_analysis"]["propagation_path_overlays"]
    assert all(path["semantic_overlay"]["status"] == "available" for path in artifact["propagation"]["paths"])
