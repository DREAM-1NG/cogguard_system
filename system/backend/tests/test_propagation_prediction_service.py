from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from app.main import app
from app.config import PROJECT_ROOT
from app.services import propagation_model_service
from app.services import propagation_prediction_service

PROPAGATION_ANALYSIS_ROOT = PROJECT_ROOT / "research" / "propagation_analysis"


def _posts() -> list[dict]:
    return [
        {"post_id": "p1", "author_id": "u1", "author_name": "Alice", "timestamp": "2026-05-11T00:00:00Z"},
        {"post_id": "p2", "author_id": "u2", "author_name": "Bob", "timestamp": "2026-05-11T00:01:00Z"},
        {"post_id": "p3", "author_id": "u3", "author_name": "Carol", "timestamp": "2026-05-11T00:02:00Z"},
    ]


def test_current_event_prediction_service_returns_frontend_trend_contract(monkeypatch):
    async def fake_event_data(*, event_id, platform):
        assert event_id == "event-1"
        assert platform == "weibo"
        return (
            _posts(),
            [
                {
                    "comment_id": "c1",
                    "author_id": "u2",
                    "author_name": "Bob",
                    "timestamp": "2026-05-11T00:03:00Z",
                }
            ],
        )

    async def fake_predict_event_macro_micro(**kwargs):
        assert kwargs["top_k"] == 2
        assert kwargs["observation_ratio"] == 0.5
        return {
            "status": "ok",
            "model_status": "available",
            "macro": {
                "observed_size": 2,
                "predicted_size": 5,
                "trend_points": [
                    {"step": 1, "predicted_size": 3},
                    {"step": 2, "predicted_size": 5},
                ],
                "intervals": None,
                "direction": "rising",
                "score_concentration": 0.2,
                "calibration_status": "unavailable",
            },
            "micro": {
                "top_users": [
                    {
                        "rank": 1,
                        "author_id": "u2",
                        "author_name": "Bob",
                        "score": 0.7,
                        "candidate_source": "observed_user_hash_bucket_proxy",
                        "activation_type": "reactivation",
                    }
                ],
                "candidate_count": 3,
                "candidate_bucket_count": 3,
                "coverage": {
                    "mapped_candidate_buckets": 1,
                    "unmapped_candidate_buckets": 2,
                    "legal_candidate_buckets": 3,
                    "mapped_probability_mass": 0.7,
                    "new_activation_status": "abstain_no_identity_mapping",
                    "identity_mapping_status": "unique_current_event_bucket_proxy_only",
                },
            },
            "model": {"name": "PropagationSequenceJointModel", "dataset": "twitter", "scope": "current_event"},
        }

    monkeypatch.setattr(propagation_model_service, "_load_prediction_event_data", fake_event_data)
    monkeypatch.setattr(propagation_prediction_service, "predict_event_macro_micro", fake_predict_event_macro_micro)

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            platform="weibo",
            event_id="event-1",
            top_k=2,
            observation_ratio=0.5,
        )
    )

    assert result["status"] == "ok"
    assert result["model_status"] == "available"
    assert [point["predicted_size"] for point in result["macro"]["trend_points"]] == [3, 5]
    assert result["micro"]["top_users"][0]["author_id"] == "u2"
    assert result["data_scope"]["platform"] == "weibo"


def test_event_prediction_route_exposes_observed_prefix_parameters():
    parameters = app.openapi()["paths"]["/api/v1/propagation/model-event-predict"]["post"]["parameters"]
    names = {parameter["name"] for parameter in parameters}

    assert {"event_id", "platform", "top_k", "observed_until", "t_obs", "observation_ratio"}.issubset(names)


def test_propagation_analysis_cached_prediction_uses_internal_research_artifact():
    result = asyncio.run(
        propagation_prediction_service.predict_propagation_macro_micro(
            dataset="twitter",
            seed=42,
            run_live=False,
        )
    )

    artifact = Path(result["artifact"])
    assert result["status"] == "ok"
    assert artifact.is_relative_to(PROPAGATION_ANALYSIS_ROOT)


def test_propagation_prediction_service_has_no_external_cogguard_dev_path_or_sys_path_patch():
    source = inspect.getsource(propagation_prediction_service)

    assert "subsystems" not in source
    assert "cogguard_dev" not in source.lower()
    assert "sys.path.insert" not in source


def test_propagation_analysis_event_adapter_builds_bundle_from_internal_research_runtime():
    bundle = propagation_prediction_service.build_event_inference_bundle(
        _posts(),
        [],
        max_sequence_len=8,
        user_hash_buckets=128,
        relation_neighbor_count=2,
        hyperedge_count=2,
        relation_neighbors={},
    )

    assert bundle["status"] == "ok"
    assert bundle["adapter_boundary"].startswith(str(PROPAGATION_ANALYSIS_ROOT))
    assert bundle["candidate_meta"]["u1"]["author_name"] == "Alice"
    assert bundle["candidate_buckets"]


def test_propagation_analysis_event_checkpoint_missing_uses_internal_adapter(tmp_path):
    result = propagation_prediction_service.predict_event_with_checkpoint(
        tmp_path / "missing-twitter-checkpoint.pt",
        _posts(),
        [],
    )

    assert result["status"] == "missing_checkpoint"
    assert result["adapter_boundary"].startswith(str(PROPAGATION_ANALYSIS_ROOT))


def test_propagation_analysis_current_event_prediction_uses_checkpoint_contract():
    result = asyncio.run(
        propagation_prediction_service.predict_event_macro_micro(
            posts=_posts(),
            comments=[],
            top_k=2,
        )
    )

    assert result["status"] == "ok"
    assert result["model_status"] == "available"
    assert result["model"]["name"] == "PropagationSequenceJointModel"
    assert result["model"]["scope"] == "current_event"
    assert result["macro"]["trend_points"]
    top_ids = {row["author_id"] for row in result["micro"]["top_users"]}
    assert len(top_ids) == 2
    assert top_ids.issubset({"u1", "u2", "u3"})
    assert result["micro"]["candidate_count"] >= 2
    assert result["macro"]["predicted_size"] >= result["macro"]["observed_size"]


def test_propagation_analysis_current_event_prediction_does_not_use_live_fallback_protocol():
    result = asyncio.run(
        propagation_prediction_service.predict_event_macro_micro(
            posts=_posts(),
            comments=[],
            top_k=2,
        )
    )

    assert result["status"] == "ok"
    assert result["model_status"] == "available"
    assert "scale_forecast" not in result
    assert "next_hop_ranking" not in result
    assert "baselines" not in result
    assert "source" not in result or result["source"] != "internal_live_runtime"
    assert len(result["micro"]["top_users"]) == 2


def test_propagation_analysis_public_dataset_loader_normalizes_jsonl_fixture(tmp_path):
    fixture = tmp_path / "twitter.jsonl"
    fixture.write_text(
        "\n".join(
            [
                '{"cascade_id":"c1","tweet_id":"p1","user_id":"u1","timestamp":"2026-05-11T00:00:00Z"}',
                '{"cascade_id":"c1","tweet_id":"p2","user_id":"u2","timestamp":"2026-05-11T00:01:00Z","parent_id":"p1"}',
            ]
        ),
        encoding="utf-8",
    )

    result = propagation_prediction_service.load_public_cascade_fixture(fixture, dataset="twitter")

    assert result["status"] == "ok"
    assert result["schema"] == "cogguard.propagation_analysis.public_cascade_fixture.v1"
    assert result["cascade_count"] == 1
    assert result["cascades"][0]["targets"]["independent_active_accounts"] == 2
