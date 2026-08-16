from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.mysql import Base
from app.models.case_workbench import (
    AuthoritySource,
    AuthoritySourceAccount,
    CaseClaim,
    CaseRecord,
)
from app.services import claim_response_landscape_service


class AsyncSessionAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


class FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def to_list(self, length):
        return self.rows[:length] if length is not None else list(self.rows)


class FakeCollection:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[dict] = []

    def find(self, query, projection=None):
        self.calls.append({"query": dict(query), "projection": projection})
        rows = [row for row in self.rows if _matches(row, query)]
        return FakeCursor(rows)


class FakeMongo(dict):
    pass


def _matches(row: dict, query: dict) -> bool:
    for key, expected in query.items():
        value = row.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if value not in expected["$in"]:
                return False
        elif value != expected:
            return False
    return True


def _db_with_case_material() -> tuple[AsyncSessionAdapter, Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            CaseRecord.__table__,
            AuthoritySource.__table__,
            AuthoritySourceAccount.__table__,
            CaseClaim.__table__,
        ],
    )
    session = Session(engine, expire_on_commit=False)
    session.add_all(
        [
            CaseRecord(case_id="case-1", event_id="event-1", title="Case one", created_by=7),
            AuthoritySource(
                source_id="source-1",
                name="Official Desk",
                url="https://authority.example",
                review_status="allowlisted",
                tier="government_official",
                reviewed_by=7,
            ),
            AuthoritySource(
                source_id="source-2",
                name="Different Desk",
                url="https://other.example",
                review_status="allowlisted",
                tier="media",
                reviewed_by=7,
            ),
            AuthoritySourceAccount(
                source_id="source-1",
                platform="weibo",
                author_id="official-1",
                display_name_snapshot="Official Desk",
                verification_snapshot=json.dumps({"is_verified": True}),
                reviewed_by=7,
            ),
            AuthoritySourceAccount(
                source_id="source-1",
                platform="xhs",
                author_id="official-1",
                display_name_snapshot="Official Desk",
                verification_snapshot=json.dumps({"is_verified": True}),
                reviewed_by=7,
            ),
            AuthoritySourceAccount(
                source_id="source-2",
                platform="weibo",
                author_id="official-other",
                display_name_snapshot="Official Desk",
                verification_snapshot=json.dumps({"is_verified": True}),
                reviewed_by=7,
            ),
            CaseClaim(
                claim_id="claim-1",
                case_id="case-1",
                authority_source_id="source-1",
                exact_quote="The primary authority claim.",
                quote_start=0,
                quote_end=len("The primary authority claim."),
                source_url="https://authority.example/post",
                account="Official Desk",
                published_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
                role="primary",
                source_tier_snapshot="government_official",
                source_review_snapshot="allowlisted",
                content_sha256="a" * 64,
            ),
        ]
    )
    session.commit()
    return AsyncSessionAdapter(session), session


def _post(
    platform: str,
    post_id: str,
    author_id: str,
    *,
    likes: int,
    author_name: str | None = None,
    url: str | None = None,
) -> dict:
    row = {
        "event_id": "event-1",
        "platform": platform,
        "post_id": post_id,
        "author_id": author_id,
        "author_name": author_name or author_id,
        "timestamp": f"2026-08-15T00:{len(post_id):02d}:00+00:00",
        "content": f"content for {post_id}",
        "likes": likes,
        "reposts": 0,
        "comments_count": 0,
        "author_profile": {
            "verification_snapshot": {"is_verified": True, "reason": "platform badge"}
        },
    }
    if url is not None:
        row["url"] = url
    return row


def _mongo() -> FakeMongo:
    posts = [
        _post(
            "weibo",
            "p-official",
            "official-1",
            likes=10,
            author_name="Official Desk",
            url="https://authority.example/post",
        ),
        _post("weibo", "p-same-name", "impostor-1", likes=900, author_name="Official Desk"),
        _post("weibo", "p-other-source", "official-other", likes=800, author_name="Official Desk"),
        _post("weibo", "p-responder-a", "responder-a", likes=1, author_name="Responder A"),
        _post("weibo", "p-responder-b", "responder-b", likes=500, author_name="Responder B"),
        _post("weibo", "p-responder-c", "responder-c", likes=50, author_name="Responder C"),
        _post("xhs", "p-xhs-official", "official-1", likes=5_000, author_name="Official Desk"),
        _post("xhs", "p-xhs-responder", "xhs-responder", likes=6_000, author_name="XHS Responder"),
    ]
    return FakeMongo(raw_posts=FakeCollection(posts), raw_comments=FakeCollection([]))


def _observed_result() -> dict:
    return {
        "graph": {
            "nodes": [
                {"id": "official-1", "author_name": "Official Desk"},
                {"id": "responder-a", "author_name": "Responder A"},
                {"id": "responder-b", "author_name": "Responder B"},
                {"id": "responder-c", "author_name": "Responder C"},
                {"id": "xhs-responder", "author_name": "XHS Responder"},
            ],
            "edges": [
                {"source": "official-1", "target": "responder-a"},
                {"source": "responder-a", "target": "responder-b"},
                {"source": "official-1", "target": "responder-c"},
                {"source": "official-1", "target": "xhs-responder"},
            ],
        },
        "path_analysis": {
            "key_paths": [
                {
                    "path_id": "claim-1:0",
                    "claim_id": "claim-1",
                    "nodes": ["official-1", "responder-a", "responder-b"],
                    "score": 8.0,
                    "evidence_refs": [
                        {"platform": "weibo", "post_id": "p-official"},
                        {"platform": "weibo", "post_id": "p-responder-a"},
                        {"platform": "weibo", "post_id": "p-responder-b"},
                    ],
                },
                {
                    "path_id": "claim-1:1",
                    "claim_id": "claim-1",
                    "nodes": ["official-1", "responder-c"],
                    "score": 4.0,
                    "evidence_refs": [
                        {"platform": "weibo", "post_id": "p-official"},
                        {"platform": "weibo", "post_id": "p-responder-c"},
                    ],
                },
                {
                    "path_id": "claim-1:xhs",
                    "claim_id": "claim-1",
                    "nodes": ["official-1", "xhs-responder"],
                    "score": 20.0,
                    "evidence_refs": [
                        {"platform": "xhs", "post_id": "p-xhs-official"},
                        {"platform": "xhs", "post_id": "p-xhs-responder"},
                    ],
                },
            ]
        },
    }


def test_landscape_uses_exact_bound_authority_accounts_and_excludes_verified_same_name(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()

            async def fake_observed(**kwargs):
                assert kwargs == {"event_id": "event-1", "platform": "weibo", "node_limit": 300}
                return _observed_result()

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=mongo,
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            assert result["status"] == "ready"
            assert result["claim_anchor"] == {
                "case_id": "case-1",
                "claim_id": "claim-1",
                "authority_source_id": "source-1",
                "text": "The primary authority claim.",
                "source_url": "https://authority.example/post",
                "account": "Official Desk",
                "published_at": "2026-08-15T00:00:00",
                "role": "primary",
                "source_review_status": "allowlisted",
                "source_tier": "government_official",
                "evidence_refs": ["case:case-1:claim:claim-1"],
            }
            assert [row["post_id"] for row in result["official_publications"]] == ["p-official"]
            assert result["official_publications"][0]["authority_binding"] == {
                "source_id": "source-1",
                "platform": "weibo",
                "author_id": "official-1",
            }
            assert result["official_publications"][0]["evidence_refs"] == ["weibo:post:p-official"]
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_ranks_responses_by_platform_local_paths_before_engagement(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()

            async def fake_observed(**_kwargs):
                return _observed_result()

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=mongo,
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            ranked_ids = [row["author_id"] for row in result["influential_responses"]]
            assert ranked_ids == ["responder-a", "responder-b", "responder-c"]
            assert result["influential_responses"][0]["downstream_reach"] == 1
            assert result["influential_responses"][0]["engagement_percentile"] < result["influential_responses"][1]["engagement_percentile"]
            assert all(row["platform"] == "weibo" for row in result["influential_responses"])
            assert all(row["rank_scope"] == "platform" for row in result["influential_responses"])
            assert all("xhs-responder" != row["author_id"] for row in result["influential_responses"])
            assert result["influential_responses"][0]["path_refs"] == [
                {
                    "path_id": "claim-1:0",
                    "evidence_refs": [
                        "weibo:post:p-official",
                        "weibo:post:p-responder-a",
                        "weibo:post:p-responder-b",
                    ],
                    "nodes": ["official-1", "responder-a", "responder-b"],
                    "score": 8.0,
                }
            ]
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_reports_path_and_semantic_coverage_gaps(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()

            async def fake_observed(**_kwargs):
                return {"graph": {"nodes": [], "edges": []}, "path_analysis": {"key_paths": []}}

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=mongo,
                semantic_projection={
                    "status": "not_found",
                    "blocking_reason": "semantic_artifact_not_found",
                    "artifact": None,
                },
            )

            assert result["status"] == "ready"
            assert result["coverage"]["observed_paths"] == {
                "status": "unavailable",
                "reason": "observed_path_evidence_unavailable",
                "path_count": 0,
            }
            assert result["coverage"]["semantic"] == {
                "status": "unavailable",
                "reason": "semantic_artifact_not_found",
            }
            assert result["influential_responses"] == []
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_reports_no_path_when_graph_has_no_observed_official_path(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            observed = _observed_result()
            observed["path_analysis"]["key_paths"] = []

            async def fake_observed(**_kwargs):
                return observed

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=_mongo(),
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            assert result["official_publications"]
            assert result["coverage"]["observed_paths"] == {
                "status": "unavailable",
                "reason": "observed_path_evidence_unavailable",
                "path_count": 0,
            }
            assert result["influential_responses"] == []
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_projects_direct_comment_thread_as_primary_claim_response_without_graph_inference(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()
            mongo["raw_posts"].rows.append(
                {
                    **_post(
                        "weibo",
                        "unrelated-earlier-post",
                        "responder-child",
                        likes=1,
                        author_name="Child responder",
                    ),
                    "timestamp": "2026-08-14T00:00:00+00:00",
                }
            )
            mongo["raw_comments"].rows.extend(
                [
                    {
                        "event_id": "event-1",
                        "platform": "weibo",
                        "comment_id": "comment-root",
                        "post_id": "p-official",
                        "author_id": "responder-root",
                        "author_name": "Root responder",
                        "timestamp": "2026-08-15T00:10:00+00:00",
                        "likes": 5,
                    },
                    {
                        "event_id": "event-1",
                        "platform": "weibo",
                        "comment_id": "comment-child",
                        "post_id": "p-official",
                        "author_id": "responder-child",
                        "author_name": "Child responder",
                        "timestamp": "2026-08-15T00:11:00+00:00",
                        "reply_to": "comment-root",
                        "likes": 9,
                    },
                ]
            )

            async def graph_must_not_be_used(**_kwargs):
                raise AssertionError("direct comment evidence must not require inferred graph paths")

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                graph_must_not_be_used,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=mongo,
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            child = next(
                row
                for row in result["influential_responses"]
                if row["author_id"] == "responder-child"
            )
            assert child["path_refs"] == [
                {
                    "path_id": "weibo:comment:comment-child",
                    "evidence_refs": [
                        "weibo:post:p-official",
                        "weibo:comment:comment-root",
                        "weibo:comment:comment-child",
                    ],
                    "nodes": ["official-1", "responder-root", "responder-child"],
                    "score": 1.0,
                }
            ]
            assert child["first_seen_at"] == "2026-08-15T00:11:00+00:00"
            assert result["coverage"]["observed_paths"] == {
                "status": "available",
                "path_count": 2,
            }
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_projects_direct_comment_path_semantic_overlay_from_exact_ready_layers(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()
            mongo["raw_comments"].rows.extend(
                [
                    {
                        "event_id": "event-1",
                        "platform": "weibo",
                        "comment_id": "comment-root",
                        "post_id": "p-official",
                        "author_id": "responder-root",
                        "author_name": "Root responder",
                        "timestamp": "2026-08-15T00:10:00+00:00",
                        "likes": 5,
                    },
                    {
                        "event_id": "event-1",
                        "platform": "weibo",
                        "comment_id": "comment-child",
                        "post_id": "p-official",
                        "author_id": "responder-child",
                        "author_name": "Child responder",
                        "timestamp": "2026-08-15T00:11:00+00:00",
                        "reply_to": "comment-root",
                        "likes": 9,
                    },
                ]
            )

            async def graph_must_not_be_used(**_kwargs):
                raise AssertionError("direct comment evidence must not require inferred graph paths")

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                graph_must_not_be_used,
            )

            semantic_projection = {
                "status": "ready",
                "snapshot_id": "snapshot-current",
                "snapshot": SimpleNamespace(
                    snapshot_id="snapshot-current",
                    data_fingerprint="current-fingerprint",
                    posts=list(mongo["raw_posts"].rows),
                    comments=list(mongo["raw_comments"].rows),
                ),
                "artifact": {
                    "technology": "semantic_enrichment",
                    "status": "ok",
                    "runtime_status": "ready",
                    "fallback": False,
                    "embedding_manifest": {"snapshot_fingerprint": "current-fingerprint"},
                    "layers": {
                        "posts": [
                            {
                                "id": "p-official",
                                "platform": "weibo",
                                "timestamp": "2026-08-15T00:00:00+00:00",
                                "sentiment": {"label": "neutral"},
                                "stance": {"label": "entailment"},
                                "keywords": [{"term": "visit"}, {"term": "claim"}],
                                "topics": [{"id": "topic-1", "label": "diplomacy"}],
                                "entities": [{"text": "Beijing", "label": "LOC"}],
                            }
                        ],
                        "comments": [
                            {
                                "id": "comment-root",
                                "platform": "weibo",
                                "timestamp": "2026-08-15T00:10:00+00:00",
                                "sentiment": {"label": "negative"},
                                "stance": {"label": "contradiction"},
                                "keywords": [{"term": "visit"}, {"term": "concern"}],
                                "topics": [{"id": "topic-2", "label": "public response"}],
                                "entities": [{"text": "tariff", "label": "POLICY"}],
                            },
                            {
                                "id": "comment-child",
                                "platform": "weibo",
                                "timestamp": "2026-08-15T00:11:00+00:00",
                                "sentiment": {"label": "positive"},
                                "stance": {"label": "neutral"},
                                "keywords": [{"term": "dialogue"}],
                                "topics": [{"id": "topic-2", "label": "public response"}],
                                "entities": [{"text": "Beijing", "label": "LOC"}],
                            },
                            {
                                "id": "comment-child-same-author-wrong-ref",
                                "platform": "weibo",
                                "timestamp": "2026-08-15T00:12:00+00:00",
                                "sentiment": {"label": "negative"},
                                "stance": {"label": "contradiction"},
                                "keywords": [{"term": "wrong"}],
                                "topics": [{"id": "topic-wrong", "label": "wrong"}],
                                "entities": [{"text": "Wrong", "label": "ORG"}],
                            },
                        ],
                    },
                    "cross_analysis": {"propagation_path_overlays": []},
                },
            }

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=mongo,
                semantic_projection=semantic_projection,
            )

            child = next(row for row in result["influential_responses"] if row["author_id"] == "responder-child")
            assert child["downstream_reach"] is None
            assert child["downstream_reach_status"] == "unavailable"
            assert child["downstream_reach_reason"] == "direct_comment_thread_network_reach_not_computed"
            assert child["path_refs"][0]["semantic_overlay"] == {
                "sentiment": {"negative": 1, "neutral": 1, "positive": 1},
                "stance": {"contradiction": 1, "entailment": 1, "neutral": 1},
                "keywords": [
                    {"term": "visit", "count": 2},
                    {"term": "claim", "count": 1},
                    {"term": "concern", "count": 1},
                    {"term": "dialogue", "count": 1},
                ],
                "topics": [
                    {"id": "topic-2", "label": "public response", "count": 2},
                    {"id": "topic-1", "label": "diplomacy", "count": 1},
                ],
                "entities": [
                    {"text": "Beijing", "label": "LOC", "count": 2},
                    {"text": "tariff", "label": "POLICY", "count": 1},
                ],
                "platforms": ["weibo"],
                "time_range": {
                    "start": "2026-08-15T00:00:00+00:00",
                    "end": "2026-08-15T00:11:00+00:00",
                },
                "evidence_refs": [
                    "weibo:post:p-official",
                    "weibo:comment:comment-root",
                    "weibo:comment:comment-child",
                ],
            }
            assert result["coverage"]["semantic"] == {
                "status": "available",
                "path_overlay_count": 0,
                "claim_response_path_overlay_count": 2,
            }
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_omits_direct_comment_path_semantic_overlay_when_any_exact_ref_is_unmapped(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()
            mongo["raw_comments"].rows.extend(
                [
                    {
                        "event_id": "event-1",
                        "platform": "weibo",
                        "comment_id": "comment-root",
                        "post_id": "p-official",
                        "author_id": "responder-root",
                        "author_name": "Root responder",
                        "timestamp": "2026-08-15T00:10:00+00:00",
                    },
                    {
                        "event_id": "event-1",
                        "platform": "weibo",
                        "comment_id": "comment-child",
                        "post_id": "p-official",
                        "author_id": "responder-child",
                        "author_name": "Child responder",
                        "timestamp": "2026-08-15T00:11:00+00:00",
                        "reply_to": "comment-root",
                    },
                ]
            )

            async def graph_must_not_be_used(**_kwargs):
                raise AssertionError("direct comment evidence must not require inferred graph paths")

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                graph_must_not_be_used,
            )

            semantic_projection = {
                "status": "ready",
                "snapshot_id": "snapshot-current",
                "snapshot": SimpleNamespace(
                    snapshot_id="snapshot-current",
                    data_fingerprint="current-fingerprint",
                    posts=list(mongo["raw_posts"].rows),
                    comments=list(mongo["raw_comments"].rows),
                ),
                "artifact": {
                    "technology": "semantic_enrichment",
                    "status": "ok",
                    "runtime_status": "ready",
                    "fallback": False,
                    "embedding_manifest": {"snapshot_fingerprint": "current-fingerprint"},
                    "layers": {
                        "posts": [{"id": "p-official", "platform": "weibo", "sentiment": {"label": "neutral"}}],
                        "comments": [
                            {"id": "comment-child", "platform": "weibo", "sentiment": {"label": "positive"}},
                            {"id": "comment-root-wrong-ref", "platform": "weibo", "sentiment": {"label": "negative"}},
                        ],
                    },
                    "cross_analysis": {"propagation_path_overlays": []},
                },
            }

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=mongo,
                semantic_projection=semantic_projection,
            )

            child = next(row for row in result["influential_responses"] if row["author_id"] == "responder-child")
            assert "semantic_overlay" not in child["path_refs"][0]
            assert "semantic" not in child
            assert "stance" not in child
            assert result["coverage"]["semantic"] == {
                "status": "available",
                "path_overlay_count": 0,
                "claim_response_path_overlay_count": 0,
            }
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_marks_fallback_semantic_artifact_unavailable_for_direct_comment_paths(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()
            mongo["raw_comments"].rows.append(
                {
                    "event_id": "event-1",
                    "platform": "weibo",
                    "comment_id": "comment-root",
                    "post_id": "p-official",
                    "author_id": "responder-root",
                    "author_name": "Root responder",
                    "timestamp": "2026-08-15T00:10:00+00:00",
                }
            )

            async def graph_must_not_be_used(**_kwargs):
                raise AssertionError("direct comment evidence must not require inferred graph paths")

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                graph_must_not_be_used,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=mongo,
                semantic_projection={
                    "status": "ready",
                    "artifact": {
                        "technology": "semantic_enrichment",
                        "status": "ok",
                        "runtime_status": "ready",
                        "fallback": True,
                        "layers": {
                            "posts": [
                                {
                                    "id": "p-official",
                                    "platform": "weibo",
                                    "sentiment": {"label": "positive"},
                                    "stance": {"label": "entailment"},
                                }
                            ],
                            "comments": [
                                {
                                    "id": "comment-root",
                                    "platform": "weibo",
                                    "sentiment": {"label": "negative"},
                                    "stance": {"label": "contradiction"},
                                }
                            ],
                        },
                    },
                },
            )

            response = next(row for row in result["influential_responses"] if row["author_id"] == "responder-root")
            assert "semantic_overlay" not in response["path_refs"][0]
            assert result["coverage"]["semantic"] == {
                "status": "unavailable",
                "reason": "semantic_artifact_fallback",
            }
        finally:
            session.close()

    asyncio.run(scenario())


def test_semantic_overlay_rejects_missing_nli_labels_instead_of_synthesizing_unknown():
    overlay = claim_response_landscape_service._semantic_overlay_for_refs(
        ["weibo:post:p-official", "weibo:comment:comment-root"],
        {
            "weibo:post:p-official": {
                "platform": "weibo",
                "sentiment": {"label": "neutral"},
                "stance": {"label": "entailment"},
            },
            "weibo:comment:comment-root": {
                "platform": "weibo",
                "sentiment": {"label": "negative"},
                "stance": {"label": None},
            },
        },
    )

    assert overlay is None


def test_semantic_overlay_rejects_missing_semantic_timestamps():
    overlay = claim_response_landscape_service._semantic_overlay_for_refs(
        ["weibo:post:p-official", "weibo:comment:comment-root"],
        {
            "weibo:post:p-official": {
                "platform": "weibo",
                "sentiment": {"label": "neutral"},
                "stance": {"label": "entailment"},
            },
            "weibo:comment:comment-root": {
                "platform": "weibo",
                "sentiment": {"label": "negative"},
                "stance": {"label": "contradiction"},
            },
        },
    )

    assert overlay is None


def test_semantic_overlay_rejects_incomplete_ready_evidence_records():
    overlay = claim_response_landscape_service._semantic_overlay_for_refs(
        ["weibo:post:official", "weibo:comment:response"],
        {
            "weibo:post:official": {
                "platform": "weibo",
                "timestamp": "2026-08-15T00:00:00+00:00",
                "sentiment": {"label": "neutral"},
                "stance": {"label": "entailment"},
                "keywords": [{"term": "claim"}],
                "topics": [{"label": "official claim"}],
                "entities": [{"text": "Beijing"}],
            },
            "weibo:comment:response": {
                "platform": "weibo",
                "timestamp": "2026-08-15T00:01:00+00:00",
                "sentiment": {"label": "negative"},
                "stance": {"label": "contradiction"},
                "keywords": [{"term": "response"}],
                "topics": [],
                "entities": [{"text": "policy"}],
            },
        },
    )

    assert overlay is None


def test_semantic_evidence_record_rejects_an_invalid_timestamp():
    assert not claim_response_landscape_service._is_complete_semantic_evidence_item(
        {
            "platform": "weibo",
            "timestamp": "not-a-timestamp",
            "sentiment": {"label": "neutral"},
            "stance": {"label": "entailment"},
            "keywords": [{"term": "claim"}],
            "topics": [{"label": "official claim"}],
            "entities": [{"text": "Beijing"}],
        }
    )


def test_semantic_coverage_rejects_ready_artifact_without_semantic_layer_lists():
    assert claim_response_landscape_service._semantic_coverage(
        {
            "status": "ready",
            "artifact": {
                "technology": "semantic_enrichment",
                "status": "ok",
                "runtime_status": "ready",
                "fallback": False,
                "layers": {"posts": []},
            },
        }
    ) == {
        "status": "unavailable",
        "reason": "semantic_artifact_malformed",
    }


def test_latest_semantic_projection_continues_after_newest_candidate_is_unavailable(monkeypatch):
    async def scenario():
        load_order: list[str] = []

        class FakeRegistry:
            def __init__(self, **_kwargs) -> None:
                pass

            async def list_semantic_artifact_candidates(self, event_id):
                assert event_id == "event-1"
                return [
                    {"run_id": "newest-missing", "snapshot_id": "snapshot-new"},
                    {"run_id": "older-ready", "snapshot_id": "snapshot-old"},
                ]

            async def load_run_artifact(self, run_id, artifact_key):
                assert artifact_key == claim_response_landscape_service.SEMANTIC_ARTIFACT_KEY
                load_order.append(run_id)
                if run_id == "newest-missing":
                    raise KeyError("artifact not found")
                return {
                    "technology": "semantic_enrichment",
                    "status": "ok",
                    "runtime_status": "ready",
                    "fallback": False,
                    "embedding_manifest": {"snapshot_fingerprint": "older-fingerprint"},
                    "layers": {"posts": [], "comments": []},
                    "cross_analysis": {"propagation_path_overlays": [{"path_id": "claim-1:0"}]},
                }

            async def load_event_snapshot(self, snapshot_id):
                assert snapshot_id == "snapshot-old"
                return SimpleNamespace(snapshot_id=snapshot_id, data_fingerprint="older-fingerprint")

        monkeypatch.setattr(claim_response_landscape_service, "AnalysisRegistry", FakeRegistry)

        result = await claim_response_landscape_service._load_latest_semantic_projection(
            "event-1",
            db=SimpleNamespace(name="db"),
            mongo_db=SimpleNamespace(name="mongo"),
        )

        assert result["status"] == "ready"
        assert result["run_id"] == "older-ready"
        assert result["snapshot_id"] == "snapshot-old"
        assert load_order == ["newest-missing", "older-ready"]

    asyncio.run(scenario())


def test_latest_semantic_projection_rejects_artifact_with_stale_snapshot_fingerprint(monkeypatch):
    async def scenario():
        class FakeRegistry:
            def __init__(self, **_kwargs):
                pass

            async def list_semantic_artifact_candidates(self, event_id):
                assert event_id == "event-1"
                return [{"run_id": "stale-run", "snapshot_id": "snapshot-current"}]

            async def load_event_snapshot(self, snapshot_id):
                assert snapshot_id == "snapshot-current"
                return SimpleNamespace(
                    snapshot_id="snapshot-current",
                    data_fingerprint="current-fingerprint",
                )

            async def load_run_artifact(self, run_id, artifact_key):
                assert run_id == "stale-run"
                assert artifact_key == claim_response_landscape_service.SEMANTIC_ARTIFACT_KEY
                return {
                    "technology": "semantic_enrichment",
                    "status": "ok",
                    "runtime_status": "ready",
                    "fallback": False,
                    "embedding_manifest": {"snapshot_fingerprint": "stale-fingerprint"},
                    "layers": {"posts": [], "comments": []},
                }

        monkeypatch.setattr(claim_response_landscape_service, "AnalysisRegistry", FakeRegistry)

        result = await claim_response_landscape_service._load_latest_semantic_projection(
            "event-1",
            db=SimpleNamespace(),
            mongo_db=SimpleNamespace(),
        )

        assert result == {
            "status": "blocked",
            "blocking_reason": "semantic_artifact_snapshot_mismatch",
            "artifact": None,
        }

    asyncio.run(scenario())


def test_semantic_projection_rejects_current_rows_that_do_not_match_its_snapshot():
    projection = {
        "status": "ready",
        "snapshot_id": "snapshot-current",
        "snapshot": SimpleNamespace(
            snapshot_id="snapshot-current",
            data_fingerprint="current-fingerprint",
            posts=[{"platform": "weibo", "post_id": "official", "content": "old claim"}],
            comments=[{"platform": "weibo", "comment_id": "response", "content": "old response"}],
        ),
        "artifact": {
            "technology": "semantic_enrichment",
            "status": "ok",
            "runtime_status": "ready",
            "fallback": False,
            "embedding_manifest": {"snapshot_fingerprint": "current-fingerprint"},
            "layers": {"posts": [], "comments": []},
        },
    }

    assert claim_response_landscape_service._semantic_projection_matches_current_source(
        projection,
        posts=[{"platform": "weibo", "post_id": "official", "content": "old claim"}],
        comments=[{"platform": "weibo", "comment_id": "response", "content": "old response"}],
        platform="weibo",
    )
    assert not claim_response_landscape_service._semantic_projection_matches_current_source(
        projection,
        posts=[{"platform": "weibo", "post_id": "official", "content": "updated claim"}],
        comments=[{"platform": "weibo", "comment_id": "response", "content": "old response"}],
        platform="weibo",
    )


def test_landscape_accepts_database_object_that_disallows_truthiness(monkeypatch):
    async def scenario():
        class BoolBlockedMongo:
            def __bool__(self):
                raise NotImplementedError("database truth value is not supported")

        async def fake_load_case(_db, event_id):
            assert event_id == "event-1"
            return None

        monkeypatch.setattr(claim_response_landscape_service, "_load_case", fake_load_case)

        result = await claim_response_landscape_service.build_claim_response_landscape(
            "event-1",
            db=SimpleNamespace(name="db"),
            mongo_db=BoolBlockedMongo(),
        )

        assert result["status"] == "not_found"
        assert result["blocking_reason"] == "event_review_case_not_found"

    asyncio.run(scenario())


def test_landscape_keeps_ranks_platform_local_and_projects_exact_semantic_evidence(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()
            async def fake_observed(**_kwargs):
                return _observed_result()

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )
            semantic_projection = {
                "status": "ready",
                "snapshot_id": "snapshot-current",
                "snapshot": SimpleNamespace(
                    snapshot_id="snapshot-current",
                    data_fingerprint="current-fingerprint",
                    posts=list(mongo["raw_posts"].rows),
                    comments=list(mongo["raw_comments"].rows),
                ),
                "artifact": {
                    "technology": "semantic_enrichment",
                    "status": "ok",
                    "runtime_status": "ready",
                    "fallback": False,
                    "embedding_manifest": {"snapshot_fingerprint": "current-fingerprint"},
                    "layers": {
                        "posts": [
                            {"id": "p-official", "platform": "weibo", "stance": {"label": "entailment"}},
                            {"id": "p-responder-a", "platform": "weibo", "stance": {"label": "entailment"}},
                            {"id": "p-responder-b", "platform": "weibo", "stance": {"label": "contradiction"}},
                            {"id": "p-responder-c", "platform": "weibo", "stance": {"label": "neutral"}},
                            {"id": "p-xhs-responder", "platform": "xhs", "stance": {"label": "entailment"}},
                        ],
                        "comments": [],
                    },
                },
            }

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                db=db,
                mongo_db=mongo,
                semantic_projection=semantic_projection,
            )

            rows_by_platform: dict[str, list[dict]] = {}
            for row in result["influential_responses"]:
                rows_by_platform.setdefault(row["platform"], []).append(row)
            assert [row["rank"] for row in rows_by_platform["weibo"]] == [1, 2, 3]
            assert "xhs" not in rows_by_platform
            assert result["official_publications"][0]["semantic"] == {"stance": "support"}
            responder_a = next(row for row in rows_by_platform["weibo"] if row["author_id"] == "responder-a")
            assert responder_a["stance"] == "support"
            assert responder_a["semantic"]["stance_distribution"] == {"support": 1}
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_excludes_same_event_path_without_bound_official_publication(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            observed = _observed_result()
            observed["path_analysis"]["key_paths"].append(
                {
                    "path_id": "same-event-unrelated",
                    "nodes": ["responder-b", "responder-c"],
                    "score": 99.0,
                    "evidence_refs": [
                        {"platform": "weibo", "post_id": "p-responder-b"},
                        {"platform": "weibo", "post_id": "p-responder-c"},
                    ],
                }
            )

            async def fake_observed(**_kwargs):
                return observed

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=_mongo(),
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            assert all(
                path_ref["path_id"] != "same-event-unrelated"
                for response in result["influential_responses"]
                for path_ref in response["path_refs"]
            )
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_excludes_path_without_primary_claim_id_even_when_primary_post_is_referenced(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            observed = _observed_result()
            observed["path_analysis"]["key_paths"].append(
                {
                    "path_id": "missing-claim-id",
                    "nodes": ["official-1", "responder-c"],
                    "score": 99.0,
                    "evidence_refs": [
                        {"platform": "weibo", "post_id": "p-official"},
                        {"platform": "weibo", "post_id": "p-responder-c"},
                    ],
                }
            )

            async def fake_observed(**_kwargs):
                return observed

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=_mongo(),
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            assert all(
                path_ref["path_id"] != "missing-claim-id"
                for response in result["influential_responses"]
                for path_ref in response["path_refs"]
            )
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_excludes_secondary_post_from_same_allowlisted_account(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            mongo = _mongo()
            mongo["raw_posts"].rows.append(
                _post(
                    "weibo",
                    "p-official-secondary",
                    "official-1",
                    likes=700,
                    author_name="Official Desk",
                    url="https://authority.example/secondary-post",
                )
            )
            observed = _observed_result()
            observed["path_analysis"]["key_paths"].append(
                {
                    "path_id": "secondary-official-post",
                    "claim_id": "claim-1",
                    "nodes": ["official-1", "responder-c"],
                    "score": 99.0,
                    "evidence_refs": [
                        {"platform": "weibo", "post_id": "p-official-secondary"},
                        {"platform": "weibo", "post_id": "p-responder-c"},
                    ],
                }
            )

            async def fake_observed(**_kwargs):
                return observed

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=mongo,
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            assert all(
                path_ref["path_id"] != "secondary-official-post"
                for response in result["influential_responses"]
                for path_ref in response["path_refs"]
            )
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_excludes_path_with_mismatched_claim_id(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            observed = _observed_result()
            observed["path_analysis"]["key_paths"].append(
                {
                    "path_id": "other-claim",
                    "claim_id": "claim-2",
                    "nodes": ["official-1", "responder-c"],
                    "score": 99.0,
                    "evidence_refs": [
                        {"platform": "weibo", "post_id": "p-official"},
                        {"platform": "weibo", "post_id": "p-responder-c"},
                    ],
                }
            )

            async def fake_observed(**_kwargs):
                return observed

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=_mongo(),
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            assert all(
                path_ref["path_id"] != "other-claim"
                for response in result["influential_responses"]
                for path_ref in response["path_refs"]
            )
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_preserves_observed_nodes_and_score_in_path_refs(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            async def fake_observed(**_kwargs):
                return _observed_result()

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=_mongo(),
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            assert result["influential_responses"][0]["path_refs"] == [
                {
                    "path_id": "claim-1:0",
                    "evidence_refs": [
                        "weibo:post:p-official",
                        "weibo:post:p-responder-a",
                        "weibo:post:p-responder-b",
                    ],
                    "nodes": ["official-1", "responder-a", "responder-b"],
                    "score": 8.0,
                }
            ]
        finally:
            session.close()

    asyncio.run(scenario())


def test_landscape_omits_path_ref_without_observed_path_identity(monkeypatch):
    async def scenario():
        db, session = _db_with_case_material()
        try:
            observed = _observed_result()
            observed["path_analysis"]["key_paths"].append(
                {
                    "claim_id": "claim-1",
                    "nodes": ["official-1", "responder-c"],
                    "score": 99.0,
                    "evidence_refs": [
                        {"platform": "weibo", "post_id": "p-official"},
                        {"platform": "weibo", "post_id": "p-responder-c"},
                    ],
                }
            )

            async def fake_observed(**_kwargs):
                return observed

            monkeypatch.setattr(
                claim_response_landscape_service.propagation_observation_service,
                "analyze_observed_propagation",
                fake_observed,
            )

            result = await claim_response_landscape_service.build_claim_response_landscape(
                "event-1",
                platform="weibo",
                db=db,
                mongo_db=_mongo(),
                semantic_projection={"status": "ready", "artifact": {"cross_analysis": {}}},
            )

            responder_c = next(
                row for row in result["influential_responses"] if row["author_id"] == "responder-c"
            )
            assert responder_c["path_refs"] == [
                {
                    "path_id": "claim-1:1",
                    "evidence_refs": [
                        "weibo:post:p-official",
                        "weibo:post:p-responder-c",
                    ],
                    "nodes": ["official-1", "responder-c"],
                    "score": 4.0,
                }
            ]
        finally:
            session.close()

    asyncio.run(scenario())
