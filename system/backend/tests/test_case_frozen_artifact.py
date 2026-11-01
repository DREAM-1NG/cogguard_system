from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2.cases import get_case_workbench_service, router
from app.core.security import get_current_user_or_local_preview
from app.services.case_frozen_artifact import (
    FrozenArtifactError,
    FrozenCaseArtifactStore,
    build_frozen_case_artifact,
    render_frozen_case_report,
)
from app.services.case_workbench_service import CaseOperationConflict, CaseWorkbenchService
from scripts.precompute_case_workbench import precompute_case_artifact


CASE_ID = "case_trump_visit_2026_05_21"
EVENT_ID = "trump_visit_2026_05_21"


def _records() -> dict[str, list[dict[str, object]]]:
    return {
        "posts": [
            {
                "post_id": "weibo_1",
                "platform": "weibo",
                "author_id": "account_1",
                "timestamp": "2026-05-14T12:00:00+00:00",
                "content": "A normalized post",
            }
        ],
        "comments": [],
    }


def _runtime_info() -> dict[str, object]:
    return {
        "runtime_status": "ok",
        "runtime_backend": "sentence_transformers",
        "device": "cpu",
        "model_versions": {"embedding": "embedding-v1", "sentiment": "sentiment-v1"},
        "run_id": "run-real-1",
    }


def test_build_frozen_artifact_has_hashed_sections_and_pending_human_review():
    artifact = build_frozen_case_artifact(
        case_id=CASE_ID,
        event_id=EVENT_ID,
        normalized_records=_records(),
        runtime_info=_runtime_info(),
        authority_claims=[{"claim_id": "claim_1", "status": "candidate_unvalidated"}],
        coordination={"run_id": "coord_1", "status": "available"},
        propagation={"run_id": "prop_1", "paths": []},
        semantic={"artifact_id": "semantic_1", "status": "ok", "validation_status": "candidate_unvalidated"},
        review={"status": "awaiting_review"},
    )

    assert artifact["schema_version"] == "cogguard.case_workbench.frozen.v1"
    assert artifact["case"]["case_id"] == CASE_ID
    assert artifact["case"]["state"] != "closed"
    assert artifact["review"]["status"] == "awaiting_human_review"
    assert artifact["review"]["canonical_verdict"]["status"] != "approved"
    for section in (
        "case",
        "snapshot",
        "authority_claims",
        "coordination",
        "propagation",
        "semantic",
        "review",
        "report_manifest",
    ):
        assert section in artifact
        assert len(artifact["content_hashes"][section]) == 64
    assert artifact["semantic"]["runtime"]["runtime_backend"] == "sentence_transformers"


def test_frozen_store_writes_json_and_html_once_without_overwriting(tmp_path: Path):
    artifact = build_frozen_case_artifact(
        case_id=CASE_ID,
        event_id=EVENT_ID,
        normalized_records=_records(),
        runtime_info=_runtime_info(),
        authority_claims=[],
        coordination={},
        propagation={},
        semantic={"status": "blocked", "validation_status": "candidate_unvalidated"},
        review={},
    )
    store = FrozenCaseArtifactStore(tmp_path)
    written = store.write(artifact)

    assert written.artifact_path == tmp_path / CASE_ID / "case_artifact.json"
    assert written.report_path == tmp_path / CASE_ID / "report.html"
    loaded = store.load(CASE_ID)
    assert loaded["case"]["event_id"] == EVENT_ID
    before = written.artifact_path.read_bytes()
    with pytest.raises(FileExistsError):
        store.write(artifact)
    assert written.artifact_path.read_bytes() == before


def test_precompute_cli_persists_supplied_normalized_bundle_and_runtime(tmp_path: Path):
    input_path = tmp_path / "normalized.json"
    input_path.write_text(
        json.dumps(
            {
                "case": {"case_id": CASE_ID, "event_id": EVENT_ID, "title": "Frozen visit"},
                **_records(),
                "authority_claims": [],
                "coordination": {},
                "propagation": {},
                "semantic": {"status": "ok", "validation_status": "candidate_unvalidated"},
                "review": {},
            }
        ),
        encoding="utf-8",
    )
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text(json.dumps(_runtime_info()), encoding="utf-8")

    result = precompute_case_artifact(input_path, runtime_path, output_root=tmp_path / "output")

    assert result.artifact_path.exists()
    assert result.report_path.exists()
    assert "awaiting_human_review" in result.report_path.read_text(encoding="utf-8")


def test_precompute_requires_runtime_info_and_does_not_rule_fallback(tmp_path: Path):
    with pytest.raises(FrozenArtifactError, match="runtime_info"):
        build_frozen_case_artifact(
            case_id=CASE_ID,
            event_id=EVENT_ID,
            normalized_records=_records(),
            runtime_info={},
            authority_claims=[],
            coordination={},
            propagation={},
            semantic={},
            review={},
        )


def test_case_service_prefers_frozen_artifact_over_demo_fixture(tmp_path: Path):
    artifact = build_frozen_case_artifact(
        case_id=CASE_ID,
        event_id=EVENT_ID,
        normalized_records=_records(),
        runtime_info=_runtime_info(),
        authority_claims=[],
        coordination={},
        propagation={},
        semantic={"status": "ok", "validation_status": "candidate_unvalidated"},
        review={},
    )
    store = FrozenCaseArtifactStore(tmp_path)
    store.write(artifact)

    async def scenario():
        service = CaseWorkbenchService(mongo_db={}, artifact_store=store)
        case = await service.get_case(CASE_ID)
        assert case["source_mode"] == "frozen_artifact"
        assert case["artifact_evidence"]["artifact_sha256"] == artifact["artifact_sha256"]
        assert case["state"] == "awaiting_review"

    asyncio.run(scenario())


def test_case_api_returns_frozen_projection_without_a_database(tmp_path: Path):
    artifact = build_frozen_case_artifact(
        case_id=CASE_ID,
        event_id=EVENT_ID,
        normalized_records=_records(),
        runtime_info=_runtime_info(),
        authority_claims=[],
        coordination={},
        propagation={},
        semantic={"status": "ok", "validation_status": "candidate_unvalidated"},
        review={},
    )
    store = FrozenCaseArtifactStore(tmp_path)
    store.write(artifact)

    async def scenario():
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: CaseWorkbenchService(
            mongo_db=None,
            artifact_store=store,
        )
        app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v2/cases/{CASE_ID}")

        assert response.status_code == 200
        assert response.json()["data"]["source_mode"] == "frozen_artifact"
        assert response.json()["data"]["artifact_evidence"]["artifact_sha256"] == artifact["artifact_sha256"]

    asyncio.run(scenario())


def test_mock_mongo_does_not_get_an_implicit_frozen_store():
    service = CaseWorkbenchService(mongo_db={})

    assert service.artifact_store is None


def test_frozen_projection_is_compact_and_keeps_ui_summaries(tmp_path: Path):
    artifact = build_frozen_case_artifact(
        case_id=CASE_ID,
        event_id=EVENT_ID,
        normalized_records={
            "posts": [
                {
                    "post_id": "post-1",
                    "platform": "weibo",
                    "author_id": "author-1",
                    "timestamp": "2026-05-14T12:00:00+00:00",
                    "content": "secret full post body that must remain out of the API projection",
                }
            ],
            "comments": [
                {
                    "comment_id": "comment-1",
                    "platform": "weibo",
                    "author_id": "commenter-1",
                    "content": "secret full comment body that must remain out of the API projection",
                }
            ],
        },
        runtime_info=_runtime_info(),
        authority_claims=[
            {"claim_id": "claim-primary", "role": "primary", "excerpt": "Primary claim"},
            {"claim_id": "claim-supplementary", "role": "supplementary", "excerpt": "Supplementary claim"},
        ],
        coordination={"status": "precomputed", "metrics": {"accounts": 2}, "communities": [{"id": "c1"}]},
        propagation={
            "status": "observed_precomputed",
            "relationship_count": 1,
            "paths": [{"path_id": "path-1", "source_id": "a", "target_id": "b", "relation_type": "repost"}],
        },
        semantic={
            "artifact_id": "semantic-1",
            "status": "ok",
            "validation_status": "candidate_unvalidated",
            "sentiment": {"summary": {"positive": 1}},
            "keywords": {"main_posts": [{"term": "visit", "count": 1}]},
            "topics": {"main_posts": {"items": [{"label": "visit", "size": 1}]}},
            "records": [{"content": "a very large semantic record map"} for _ in range(100)],
        },
        review={},
    )
    store = FrozenCaseArtifactStore(tmp_path)
    store.write(artifact)

    case = asyncio.run(CaseWorkbenchService(mongo_db={}, artifact_store=store).get_case(CASE_ID))

    assert "frozen_artifact" not in case
    assert "posts" not in case["evidence_matrix"]
    assert "comments" not in case["evidence_matrix"]
    assert case["evidence"]["posts"] == 1
    assert case["evidence"]["comments"] == 1
    assert case["evidence"]["samples"]["posts"][0]["post_id"] == "post-1"
    assert case["primary_claim"]["claim_id"] == "claim-primary"
    assert case["supplementary_claims"][0]["claim_id"] == "claim-supplementary"
    assert case["graph"]["coordination"]["metrics"]["accounts"] == 2
    assert case["graph"]["propagation"]["paths"][0]["path_id"] == "path-1"
    assert case["semantic_artifacts"][0]["summary"]["top_keywords"]
    assert case["semantic_artifacts"][0]["summary"].get("records") is None
    assert len(json.dumps(case).encode("utf-8")) < 50_000


def test_frozen_projection_exposes_path_semantic_overlay_for_graph_cards(tmp_path: Path):
    overlay = {
        "status": "available",
        "sentiment": {"positive": 2, "negative": 1},
        "stance": {"support": 2, "neutral": 1},
        "keywords": ["visit", "claim"],
        "entities": ["China", "United States"],
        "platforms": ["weibo", "xhs"],
        "time_range": {
            "start": "2026-05-14T12:00:00+00:00",
            "end": "2026-05-14T12:05:00+00:00",
        },
        "claim_refs": ["claim-primary"],
        "evidence_refs": ["weibo:post-1", "xhs:comment-1"],
        "score_policy": "evidence_overlay_only",
    }
    artifact = build_frozen_case_artifact(
        case_id=CASE_ID,
        event_id=EVENT_ID,
        normalized_records=_records(),
        runtime_info=_runtime_info(),
        authority_claims=[{"claim_id": "claim-primary", "role": "primary", "excerpt": "Primary claim"}],
        coordination={"status": "precomputed", "metrics": {"accounts": 2}},
        propagation={
            "status": "observed_precomputed",
            "relationship_count": 1,
            "paths": [
                {
                    "path_id": "path-1",
                    "source_id": "account-a",
                    "target_id": "account-b",
                    "evidence_ref": "weibo:post-1",
                    "relation_type": "reply",
                    "semantic_overlay": overlay,
                }
            ],
        },
        semantic={
            "artifact_id": "semantic-1",
            "status": "ok",
            "validation_status": "candidate_unvalidated",
            "cross_analysis": {
                "propagation_path_overlays": [
                    {
                        "path_id": "path-1",
                        **overlay,
                    }
                ]
            },
        },
        review={},
    )
    store = FrozenCaseArtifactStore(tmp_path)
    store.write(artifact)

    case = asyncio.run(CaseWorkbenchService(mongo_db={}, artifact_store=store).get_case(CASE_ID))

    graph_path = case["graph"]["propagation_paths"][0]
    assert graph_path["path_id"] == "path-1"
    assert graph_path["semantic_overlay"]["status"] == "available"
    assert graph_path["semantic_overlay"]["sentiment"] == {"positive": 2, "negative": 1}
    assert graph_path["semantic_overlay"]["stance"] == {"support": 2, "neutral": 1}
    assert graph_path["semantic_overlay"]["keywords"] == ["visit", "claim"]
    assert graph_path["semantic_overlay"]["entities"] == ["China", "United States"]
    assert graph_path["semantic_overlay"]["platforms"] == ["weibo", "xhs"]
    assert graph_path["semantic_overlay"]["evidence_refs"] == ["weibo:post-1", "xhs:comment-1"]
    assert graph_path["semantic_overlay"]["claim_refs"] == ["claim-primary"]
    assert graph_path["semantic_overlay"]["score_policy"] == "evidence_overlay_only"
    assert case["graph"]["path_analysis"]["key_paths"][0]["semantic_overlay"] == graph_path["semantic_overlay"]


def test_frozen_case_rejects_every_mutation_without_changing_demo_state(tmp_path: Path):
    artifact = build_frozen_case_artifact(
        case_id=CASE_ID,
        event_id=EVENT_ID,
        normalized_records=_records(),
        runtime_info=_runtime_info(),
        authority_claims=[],
        coordination={},
        propagation={},
        semantic={"artifact_id": "semantic-1", "status": "ok", "validation_status": "candidate_unvalidated"},
        review={},
    )
    store = FrozenCaseArtifactStore(tmp_path)
    store.write(artifact)
    service = CaseWorkbenchService(mongo_db={}, artifact_store=store)
    state_before = json.loads(json.dumps(service.demo_state))

    async def scenario():
        operations = (
            lambda: service.complete_action(CASE_ID, "action_review_public_response", actor_id="analyst"),
            lambda: service.waive_action(CASE_ID, "action_review_public_response", actor_id="analyst", note="waive"),
            lambda: service.acknowledge_blocker(
                CASE_ID,
                "blocker_human_review_required",
                actor_id="analyst",
                reason="review later",
            ),
            lambda: service.submit_feedback(CASE_ID, actor_id="analyst", content="feedback"),
            lambda: service.record_semantic_correction(
                CASE_ID,
                "semantic-1",
                actor_id="analyst",
                module="sentiment",
                target_ref="post-1",
                corrected_value="neutral",
                reason="review later",
            ),
            lambda: service.submit_closeout_review(CASE_ID, actor_id="analyst", summary="close later"),
        )
        for operation in operations:
            with pytest.raises(CaseOperationConflict, match="Frozen Case"):
                await operation()

    asyncio.run(scenario())
    assert service.demo_state == state_before


def test_frozen_report_is_concise_and_excludes_raw_records():
    artifact = build_frozen_case_artifact(
        case_id=CASE_ID,
        event_id=EVENT_ID,
        normalized_records={
            "posts": [{"post_id": "post-1", "content": "FULL_POST_BODY" * 1000}],
            "comments": [{"comment_id": "comment-1", "content": "FULL_COMMENT_BODY" * 1000}],
        },
        runtime_info=_runtime_info(),
        authority_claims=[{"claim_id": "claim-1", "role": "primary", "excerpt": "Primary claim"}],
        coordination={"status": "precomputed", "metrics": {"accounts": 2}},
        propagation={"status": "observed_precomputed", "relationship_count": 1, "paths": [{"path_id": "path-1"}]},
        semantic={
            "artifact_id": "semantic-1",
            "status": "ok",
            "validation_status": "candidate_unvalidated",
            "records": [{"raw": "SEMANTIC_RECORD" * 1000}],
        },
        review={},
    )

    report = render_frozen_case_report(artifact)

    assert len(report) < 20_000
    assert "FULL_POST_BODY" not in report
    assert "FULL_COMMENT_BODY" not in report
    assert "SEMANTIC_RECORD" not in report
    for heading in ("Case", "Snapshot", "Model runtime", "Authority claims", "Coordination", "Propagation", "Semantic summary", "Review status", "Artifact evidence"):
        assert heading in report
