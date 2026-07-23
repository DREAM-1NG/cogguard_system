from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from app.config import PROJECT_ROOT
from app.services import propagation_prediction_service

PROPAGATION_ANALYSIS_ROOT = PROJECT_ROOT / "research" / "propagation_analysis"


def _posts() -> list[dict]:
    return [
        {"post_id": "p1", "author_id": "u1", "author_name": "Alice", "timestamp": "2026-05-11T00:00:00Z"},
        {"post_id": "p2", "author_id": "u2", "author_name": "Bob", "timestamp": "2026-05-11T00:01:00Z"},
        {"post_id": "p3", "author_id": "u3", "author_name": "Carol", "timestamp": "2026-05-11T00:02:00Z"},
    ]


def test_propagation_analysis_cached_prediction_uses_internal_research_artifact():
    result = asyncio.run(
        propagation_prediction_service.predict_propagation_analysis_macro_micro(
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


def test_propagation_analysis_current_event_prediction_uses_internal_live_runtime():
    result = asyncio.run(
        propagation_prediction_service.predict_event_macro_micro(
            posts=_posts(),
            comments=[],
            top_k=2,
        )
    )

    assert result["status"] == "ok"
    assert result["source"] == "internal_live_runtime"
    assert result["model"] == "PropagationAnalysisLiveRuntime"
    top_ids = {row["author_id"] for row in result["micro"]["topk_examples"]}
    assert len(top_ids) == 2
    assert top_ids.issubset({"u1", "u2", "u3"})
    assert result["micro"]["metrics"]["candidate_count"] == 3
    assert result["macro"]["metrics"]["volume_1h"] >= 0


def test_propagation_analysis_current_event_prediction_adds_hindcast_protocol():
    result = asyncio.run(
        propagation_prediction_service.predict_event_macro_micro(
            posts=_posts(),
            comments=[],
            top_k=2,
        )
    )

    assert result["schema"] == "cogguard.propagation_analysis.hindcast_protocol.v1"
    assert result["model_version"] == "propagation_analysis-hindcast-protocol-v1"
    assert result["scale_forecast"]["target"] == "independent_active_accounts"
    assert {"80", "95"}.issubset(result["conformal_intervals"])
    assert result["next_hop_ranking"]["target"] == "next_independent_active_accounts"
    assert len(result["next_hop_ranking"]["items"]) == 2
    assert {"edgebank", "hawkes_recency", "tgn", "dygformer", "casflow", "casft"}.issubset(result["baselines"])
    assert result["baselines"]["tgn"]["activation_allowed"] is False
    assert result["protocol"]["claim_status"] == "fallback_only_not_research_claim"


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
