from __future__ import annotations

import asyncio
import hashlib
import inspect
from datetime import datetime, timezone
from pathlib import Path

from app.config import PROJECT_ROOT
from app.schemas.propagation import PropagationPredictionData
from app.services import propagation_model_service, propagation_prediction_service

PROPAGATION_ANALYSIS_ROOT = PROJECT_ROOT / "research" / "propagation_analysis"


def _posts() -> list[dict]:
    return [
        {"post_id": "p1", "author_id": "u1", "author_name": "Alice", "timestamp": "2026-05-11T00:00:00Z"},
        {"post_id": "p2", "author_id": "u2", "author_name": "Bob", "timestamp": "2026-05-11T00:01:00Z"},
        {"post_id": "p3", "author_id": "u3", "author_name": "Carol", "timestamp": "2026-05-11T00:02:00Z"},
    ]


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


def test_prediction_runtime_modules_have_single_responsibility_boundaries():
    adapter_source = inspect.getsource(propagation_prediction_service._load_propagation_analysis_event_adapter())
    runtime_source = inspect.getsource(propagation_prediction_service._load_propagation_analysis_checkpoint_runtime())

    assert "torch.load" not in adapter_source
    assert "make_sequence_joint_model" not in adapter_source
    assert "build_event_inference_bundle" in adapter_source
    assert "torch.load" in runtime_source
    assert "make_sequence_joint_model" in runtime_source


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
    assert bundle["obs_ratios"].tolist() == [0.5]


def test_event_adapter_counts_observed_records_for_each_real_candidate():
    bundle = propagation_prediction_service.build_event_inference_bundle(
        [
            {"post_id": "p1", "author_id": "u1", "author_name": "Alice", "timestamp": "2026-05-11T00:00:00Z"},
            {"post_id": "p2", "author_id": "u1", "author_name": "Alice", "timestamp": "2026-05-11T00:01:00Z"},
            {"post_id": "p3", "author_id": "u2", "author_name": "Bob", "timestamp": "2026-05-11T00:02:00Z"},
        ],
        [],
        max_sequence_len=8,
        user_hash_buckets=128,
        relation_neighbor_count=2,
        hyperedge_count=2,
        relation_neighbors={},
    )

    assert bundle["candidate_meta"]["u1"]["event_count"] == 2
    assert "u2" not in bundle["candidate_meta"]


def test_event_adapter_default_observation_ratio_is_supported_by_twitter_checkpoint():
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
    assert bundle["obs_ratios"].tolist() == [0.5]


def test_event_adapter_uses_valid_timestamp_alias_when_primary_field_is_invalid():
    rows = [
        {
            "post_id": "p1",
            "author_id": "u1",
            "author_name": "Alice",
            "timestamp": "not-a-timestamp",
            "created_at": "2026-05-11T00:00:00Z",
        },
        {
            "post_id": "p2",
            "author_id": "u2",
            "author_name": "Bob",
            "timestamp": "2026-05-11T00:01:00Z",
        },
        {
            "post_id": "p3",
            "author_id": "u3",
            "author_name": "Carol",
            "timestamp": "2026-05-11T00:02:00Z",
        },
    ]

    adapter = propagation_prediction_service._load_propagation_analysis_event_adapter()
    bundle = adapter.build_event_inference_bundle(
        rows,
        [],
        max_sequence_len=8,
        user_hash_buckets=128,
        relation_neighbor_count=2,
        hyperedge_count=2,
        relation_neighbors={},
    )

    assert bundle["status"] == "ok"
    assert bundle["candidate_meta"]["u1"]["first_seen_at"] == "2026-05-11T00:00:00+00:00"


def test_event_adapter_observation_ratio_truncates_unspecified_cutoff_to_sorted_prefix():
    rows = [
        {"post_id": "p6", "author_id": "u6", "timestamp": "2026-05-11T00:05:00Z"},
        {"post_id": "p2", "author_id": "u2", "timestamp": "2026-05-11T00:01:00Z"},
        {"post_id": "p4", "author_id": "u4", "timestamp": "2026-05-11T00:03:00Z"},
        {"post_id": "p1", "author_id": "u1", "timestamp": "2026-05-11T00:00:00Z"},
        {"post_id": "p5", "author_id": "u5", "timestamp": "2026-05-11T00:04:00Z"},
        {"post_id": "p3", "author_id": "u3", "timestamp": "2026-05-11T00:02:00Z"},
    ]

    adapter = propagation_prediction_service._load_propagation_analysis_event_adapter()
    bundle = adapter.build_event_inference_bundle(
        rows,
        [],
        max_sequence_len=8,
        user_hash_buckets=128,
        relation_neighbor_count=2,
        hyperedge_count=2,
        relation_neighbors={},
        observation_ratio=0.5,
    )

    assert bundle["status"] == "ok"
    expected_buckets = [
        2 + (int(hashlib.sha1(user.encode("utf-8")).hexdigest()[:16], 16) % 126)
        for user in ("u1", "u2", "u3")
    ]
    assert bundle["seq_user_ids"][0, :3].tolist() == expected_buckets
    assert bundle["observed_counts"].tolist() == [3.0]
    assert bundle["latest_timestamp"].isoformat() == "2026-05-11T00:02:00+00:00"
    assert set(bundle["candidate_meta"]) == {"u1", "u2", "u3"}
    assert all(meta["activation_type"] == "reactivation" for meta in bundle["candidate_meta"].values())


def test_event_adapter_rejects_observation_ratio_outside_closed_interval():
    rows = [
        {"post_id": "p1", "author_id": "u1", "timestamp": "2026-05-11T00:00:00Z"},
        {"post_id": "p2", "author_id": "u2", "timestamp": "2026-05-11T00:01:00Z"},
        {"post_id": "p3", "author_id": "u3", "timestamp": "2026-05-11T00:02:00Z"},
    ]

    for invalid_ratio in (0.0, 1.01):
        try:
            propagation_prediction_service.build_event_inference_bundle(
                rows,
                [],
                max_sequence_len=8,
                user_hash_buckets=128,
                relation_neighbor_count=2,
                hyperedge_count=2,
                relation_neighbors={},
                observation_ratio=invalid_ratio,
            )
        except ValueError as exc:
            assert "observation_ratio" in str(exc)
        else:
            raise AssertionError(f"invalid observation_ratio {invalid_ratio} was accepted")


def test_event_adapter_keeps_unmapped_candidate_buckets_without_fabricated_identity():
    rows = [
        {"post_id": "p1", "author_id": "u1", "timestamp": "2026-05-11T00:00:00Z"},
        {"post_id": "p2", "author_id": "u2", "timestamp": "2026-05-11T00:01:00Z"},
        {"post_id": "p3", "author_id": "u3", "timestamp": "2026-05-11T00:02:00Z"},
        {"post_id": "p4", "author_id": "u4", "timestamp": "2026-05-11T00:03:00Z"},
    ]
    observed_bucket = 2 + (int(hashlib.sha1(b"u1").hexdigest()[:16], 16) % 126)

    adapter = propagation_prediction_service._load_propagation_analysis_event_adapter()
    bundle = adapter.build_event_inference_bundle(
        rows,
        [],
        max_sequence_len=8,
        user_hash_buckets=128,
        relation_neighbor_count=2,
        hyperedge_count=2,
        relation_neighbors={observed_bucket: [77]},
        train_user_buckets=[66],
        observation_ratio=0.5,
    )

    assert bundle["status"] == "ok"
    assert 66 in bundle["candidate_buckets"]
    assert 77 in bundle["candidate_buckets"]
    assert bundle["bucket_to_users"].get(66, []) == []
    assert bundle["bucket_to_users"].get(77, []) == []
    assert bundle["candidate_source_counts"]["checkpoint_train_buckets"] == 1
    assert bundle["candidate_source_counts"]["observed_relation_neighbor_buckets"] == 1
    assert bundle["candidate_coverage"]["legal_candidate_buckets"] == len(bundle["candidate_buckets"])
    assert bundle["candidate_coverage"]["mapped_candidate_buckets"] == 2
    assert bundle["candidate_coverage"]["unmapped_candidate_buckets"] == len(bundle["candidate_buckets"]) - 2
    assert bundle["candidate_coverage"]["mapped_probability_mass"] == 0.0


def test_bucket_probability_mapping_excludes_ambiguous_current_event_identities():
    contract = propagation_prediction_service._load_internal_module(
        path=PROPAGATION_ANALYSIS_ROOT / "benchmark" / "adapters" / "prediction_contract.py",
        module_name="cogguard_propagation_analysis_prediction_contract",
        label="PropagationAnalysis prediction contract",
    )

    mapped = contract.map_bucket_probabilities_to_unique_users(
        [10, 11],
        [0.7, 0.3],
        {
            10: [{"author_id": "u1"}, {"author_id": "u2"}],
            11: [{"author_id": "u3"}],
        },
    )

    assert mapped["user_scores"] == {"u3": 0.3}
    assert mapped["mapped_bucket_count"] == 2
    assert mapped["ambiguous_mapped_buckets"] == 1
    assert mapped["excluded_ambiguous_users"] == 2
    assert mapped["unique_identity_probability_mass"] == 0.3


def test_propagation_analysis_event_checkpoint_missing_abstains_with_public_schema(tmp_path):
    result = propagation_prediction_service.predict_event_with_checkpoint(
        tmp_path / "missing-twitter-checkpoint.pt",
        _posts(),
        [],
    )

    assert result["status"] == "missing_checkpoint"
    assert result["model_status"] == "unavailable"
    assert result["macro"] == {
        "observed_size": 0,
        "predicted_size": None,
        "trend_points": [],
        "intervals": None,
        "direction": None,
        "score_concentration": None,
        "calibration_status": "unavailable",
    }
    assert result["micro"]["top_users"] == []


def test_propagation_analysis_event_checkpoint_runs_real_internal_torch_model():
    result = asyncio.run(
        propagation_prediction_service.predict_event_macro_micro(
            posts=_posts(),
            comments=[],
            top_k=2,
        )
    )

    assert result["status"] == "ok"
    assert result["model_status"] == "available"
    assert result["model"]["checkpoint"].startswith(str(PROPAGATION_ANALYSIS_ROOT))
    assert result["macro"]["predicted_size"] >= result["macro"]["observed_size"]
    assert result["macro"]["trend_points"]
    assert result["macro"]["intervals"] is None
    assert result["macro"]["calibration_status"] == "unavailable"
    top_ids = {row["author_id"] for row in result["micro"]["top_users"]}
    assert len(top_ids) == 2
    assert top_ids.issubset({"u1", "u2", "u3"})
    assert result["micro"]["candidate_count"] == 2
    assert result["micro"]["candidate_bucket_count"] >= result["micro"]["candidate_count"]
    assert result["micro"]["new_activation_count"] == 0
    assert result["micro"]["coverage"]["identity_mapping_status"] == "unique_current_event_bucket_proxy_only"
    assert all(
        row["identity_resolution"].endswith("current_event_bucket_proxy")
        for row in result["micro"]["top_users"]
    )
    assert all(row["candidate_source"] == "observed_user_hash_bucket_proxy" for row in result["micro"]["top_users"])
    assert all(row["bucket_collision_size"] == 1 for row in result["micro"]["top_users"])
    assert result["micro"]["coverage"]["legal_candidate_buckets"] == result["micro"]["candidate_bucket_count"]
    assert 0.0 <= result["micro"]["coverage"]["mapped_probability_mass"] <= 1.0
    assert result["micro"]["coverage"]["unmapped_candidate_buckets"] >= 0
    PropagationPredictionData.model_validate({**result, "data_scope": {"observed_until": None}})


def test_bson_datetime_rows_are_accepted_by_event_checkpoint_adapter():
    rows = [
        {**row, "timestamp": datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))}
        for row in _posts()
    ]

    result = propagation_prediction_service.predict_event_with_checkpoint(
        propagation_prediction_service.PROPAGATION_TWITTER_CHECKPOINT,
        rows,
        [],
        top_k=2,
    )

    assert result["status"] == "ok"
    assert result["macro"]["observed_size"] == 2
    assert result["macro"]["trend_points"]


def test_model_runtime_error_returns_structured_unavailable_result(monkeypatch):
    async def fake_posts(*_args, **_kwargs):
        return _posts()

    async def fake_comments(*_args, **_kwargs):
        return []

    async def failing_predictor(**_kwargs):
        raise RuntimeError("checkpoint tensor shape mismatch")

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", fake_posts)
    monkeypatch.setattr(propagation_model_service, "load_event_comments", fake_comments)
    monkeypatch.setattr(
        propagation_model_service.propagation_prediction_service,
        "predict_event_macro_micro",
        failing_predictor,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="twitter",
        )
    )

    assert result["status"] == "model_error"
    assert result["model_status"] == "unavailable"
    assert result["macro"]["trend_points"] == []
    assert result["micro"]["top_users"] == []
    assert result["data_scope"]["posts"] == 3


def test_current_event_platform_filters_data_without_blocking_model(monkeypatch):
    calls = {}

    async def fake_posts(_mongo_db, *, event_id, platform):
        calls["posts_scope"] = {"event_id": event_id, "platform": platform}
        return _posts()

    async def fake_comments(_mongo_db, *, event_id, platform):
        calls["comments_scope"] = {"event_id": event_id, "platform": platform}
        return []

    async def fake_predictor(**kwargs):
        calls["predictor"] = kwargs
        result = propagation_model_service.empty_prediction_result("event-1", "weibo")
        result["status"] = "ok"
        result["model_status"] = "available"
        result["macro"].update({
            "observed_size": 3,
            "predicted_size": 5,
            "trend_points": [{"step": 1, "predicted_size": 5}],
        })
        return result

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", fake_posts)
    monkeypatch.setattr(propagation_model_service, "load_event_comments", fake_comments)
    monkeypatch.setattr(
        propagation_model_service.propagation_prediction_service,
        "predict_event_macro_micro",
        fake_predictor,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="weibo",
            observation_ratio=0.3,
        )
    )

    assert result["status"] == "ok"
    assert result["model_status"] == "available"
    assert result["data_scope"]["event_id"] == "event-1"
    assert result["data_scope"]["platform"] == "weibo"
    assert result["data_scope"]["observation_ratio"] == 1.0
    assert result["data_scope"]["checkpoint_conditioning_ratio"] == 0.3
    assert calls["posts_scope"] == {"event_id": "event-1", "platform": "weibo"}
    assert calls["comments_scope"] == {"event_id": "event-1", "platform": "weibo"}
    assert calls["predictor"]["posts"] == _posts()


def test_unspecified_current_event_platform_uses_all_platform_data(monkeypatch):
    captured = {}

    async def fake_event_data(*, event_id, platform):
        captured.update({"event_id": event_id, "platform": platform})
        return [], []

    monkeypatch.setattr(
        propagation_model_service,
        "_load_prediction_event_data",
        fake_event_data,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform=None,
        )
    )

    assert captured == {"event_id": "event-1", "platform": None}
    assert result["platform"] is None
    assert result["data_scope"]["platform"] is None


def test_missing_event_id_abstains_before_data_access(monkeypatch):
    calls = []

    async def fail_event_data(**_kwargs):
        calls.append("data")
        raise AssertionError("missing event_id must not query MongoDB")

    monkeypatch.setattr(
        propagation_model_service,
        "_load_prediction_event_data",
        fail_event_data,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id=" ",
            platform="twitter",
        )
    )

    assert result["status"] == "invalid_scope"
    assert result["model_status"] == "unavailable"
    assert calls == []


def test_event_data_source_failure_returns_structured_unavailable_result(monkeypatch):
    async def failing_posts(*_args, **_kwargs):
        raise RuntimeError("mongo server selection timeout")

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", failing_posts)

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="twitter",
        )
    )

    assert result["status"] == "data_unavailable"
    assert result["model_status"] == "unavailable"
    assert result["macro"]["trend_points"] == []
    assert result["micro"]["top_users"] == []
    assert result["data_scope"]["event_id"] == "event-1"


def test_event_data_source_failure_preserves_cutoff_and_effective_ratio(monkeypatch):
    async def failing_posts(*_args, **_kwargs):
        raise RuntimeError("mongo server selection timeout")

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", failing_posts)

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="twitter",
            observed_until="2026-05-11T00:02:00Z",
            observation_ratio=0.3,
        )
    )

    assert result["status"] == "data_unavailable"
    assert result["data_scope"]["observed_until"] == "2026-05-11T00:02:00Z"
    assert result["data_scope"]["observation_ratio"] == 0.3


def test_malformed_model_result_returns_structured_unavailable_result(monkeypatch):
    async def fake_posts(*_args, **_kwargs):
        return _posts()

    async def fake_comments(*_args, **_kwargs):
        return []

    async def malformed_predictor(**_kwargs):
        return {"error": "legacy adapter failure"}

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", fake_posts)
    monkeypatch.setattr(propagation_model_service, "load_event_comments", fake_comments)
    monkeypatch.setattr(
        propagation_model_service.propagation_prediction_service,
        "predict_event_macro_micro",
        malformed_predictor,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="twitter",
        )
    )

    assert result["status"] == "model_error"
    assert result["model_status"] == "unavailable"
    assert result["macro"]["observed_size"] == 3
    assert result["macro"]["trend_points"] == []
    assert result["micro"]["top_users"] == []


def test_normalization_never_marks_an_error_result_as_available():
    result = propagation_model_service.normalize_prediction_result(
        {
            "model_status": "available",
            "macro": {},
            "micro": {},
        },
        event_id="event-1",
        platform="twitter",
        observed_size=3,
    )

    assert result["status"] == "model_error"
    assert result["model_status"] == "unavailable"


def test_event_cutoff_excludes_future_rows_before_inference():
    rows = _posts() + [
        {"post_id": "p4", "author_id": "future", "author_name": "Future", "timestamp": "2026-05-11T02:00:00Z"}
    ]

    scoped = propagation_model_service.filter_rows_until(rows, "2026-05-11T00:02:00Z")
    result = asyncio.run(
        propagation_prediction_service.predict_event_macro_micro(
            posts=scoped,
            comments=[],
            top_k=10,
        )
    )

    assert {row["author_id"] for row in result["micro"]["top_users"]} <= {"u1", "u2", "u3"}
    assert result["macro"]["observed_size"] == 2


def test_explicit_event_cutoff_takes_precedence_over_observation_ratio(monkeypatch):
    captured = {}

    async def fake_posts(*_args, **_kwargs):
        return _posts() + [
            {"post_id": "p4", "author_id": "future", "timestamp": "2026-05-11T02:00:00Z"}
        ]

    async def fake_comments(*_args, **_kwargs):
        return []

    async def fake_predictor(*, posts, comments, top_k, observation_ratio, prefix_is_preselected):
        captured.update({
            "posts": posts,
            "comments": comments,
            "top_k": top_k,
            "observation_ratio": observation_ratio,
            "prefix_is_preselected": prefix_is_preselected,
        })
        result = propagation_model_service.empty_prediction_result("event-1", "twitter")
        result["status"] = "ok"
        result["model_status"] = "available"
        result["macro"].update({
            "observed_size": len(posts) + len(comments),
            "predicted_size": len(posts) + len(comments),
            "trend_points": [{"step": 1, "predicted_size": len(posts) + len(comments)}],
        })
        return result

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", fake_posts)
    monkeypatch.setattr(propagation_model_service, "load_event_comments", fake_comments)
    monkeypatch.setattr(
        propagation_model_service.propagation_prediction_service,
        "predict_event_macro_micro",
        fake_predictor,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="twitter",
            observed_until="2026-05-11T00:02:00Z",
            observation_ratio=0.1,
        )
    )

    assert result["status"] == "ok"
    assert len(captured["posts"]) == 3
    assert captured["observation_ratio"] == 0.5
    assert captured["prefix_is_preselected"] is True
    assert result["data_scope"]["observation_ratio"] == 0.75
    assert result["data_scope"]["actual_observation_ratio"] == 0.75
    assert result["data_scope"]["checkpoint_conditioning_ratio"] == 0.5
    assert result["data_scope"]["loaded_event_count"] == 4
    assert result["data_scope"]["model_input_event_count"] == 3


def test_invalid_or_timezone_free_cutoff_never_falls_back_to_full_snapshot():
    for value in ("not-a-time", "2026-05-11T00:02:00"):
        try:
            propagation_model_service.filter_rows_until(_posts(), value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid cutoff {value!r} must be rejected")


def test_current_event_result_records_cutoff_and_normalized_trajectory_without_heuristic(monkeypatch):
    async def fake_posts(*_args, **_kwargs):
        return _posts() + [
            {"post_id": "p4", "author_id": "future", "timestamp": "2026-05-11T02:00:00Z"}
        ]

    async def fake_comments(*_args, **_kwargs):
        return []

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", fake_posts)
    monkeypatch.setattr(propagation_model_service, "load_event_comments", fake_comments)
    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="twitter",
            observed_until="2026-05-11T00:02:00Z",
        )
    )

    assert result["model_status"] == "available"
    assert result["data_scope"]["observed_until"] == "2026-05-11T00:02:00Z"
    assert result["data_scope"]["prediction_horizon_hours"] is None
    assert result["data_scope"]["trajectory_time_basis"] == "normalized_model_steps"
    assert result["data_scope"]["excluded_after_cutoff"]["posts"] == 1
    assert "future" not in {row["author_id"] for row in result["micro"]["top_users"]}


def test_ratio_prefix_scope_reports_the_actual_model_input_boundary(monkeypatch):
    async def fake_posts(*_args, **_kwargs):
        return _posts() + [
            {"post_id": "p4", "author_id": "u4", "timestamp": "2026-05-11T00:03:00Z"}
        ]

    async def fake_comments(*_args, **_kwargs):
        return []

    async def fake_predictor(**_kwargs):
        result = propagation_model_service.empty_prediction_result("event-1", "twitter")
        result["status"] = "ok"
        result["model_status"] = "available"
        result["macro"].update({
            "observed_size": 2,
            "predicted_size": 4,
            "trend_points": [{"step": 1, "predicted_size": 4}],
        })
        result["inference_scope"] = {
            "loaded_event_count": 4,
            "observed_event_count": 2,
            "observed_until": "2026-05-11T00:01:00+00:00",
            "observation_ratio": 0.5,
            "prefix_is_preselected": False,
        }
        return result

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", fake_posts)
    monkeypatch.setattr(propagation_model_service, "load_event_comments", fake_comments)
    monkeypatch.setattr(
        propagation_model_service.propagation_prediction_service,
        "predict_event_macro_micro",
        fake_predictor,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="twitter",
            observation_ratio=0.5,
        )
    )

    assert result["data_scope"]["loaded_event_count"] == 4
    assert result["data_scope"]["model_observed_event_count"] == 2
    assert result["data_scope"]["observed_until"] == "2026-05-11T00:01:00+00:00"
    assert result["data_scope"]["actual_observation_ratio"] == 0.5
    assert result["data_scope"]["checkpoint_conditioning_ratio"] == 0.5


def test_public_current_event_path_does_not_import_or_call_heuristics():
    source = inspect.getsource(propagation_prediction_service)

    assert "from app.core.propagation.trend_predictor import predict_trend" not in source
    assert "build_live_event_macro_micro" not in source
    assert "build_hindcast_protocol" not in source
    assert "PROPAGATION_PROTOCOL_PATH" not in source


def test_empty_current_event_is_an_abstain_response():
    result = propagation_model_service.empty_prediction_result("event-1", "weibo")

    assert result["status"] == "data_insufficient"
    assert result["model_status"] == "unavailable"
    assert result["macro"]["trend_points"] == []
    assert result["micro"]["top_users"] == []


def test_platform_scoped_prediction_reports_data_unavailable_when_data_access_fails(monkeypatch):
    def fail_database_access():
        raise RuntimeError("database down")

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", fail_database_access)

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="weibo",
        )
    )

    assert result["status"] == "data_unavailable"
    assert result["model_status"] == "unavailable"
    assert result["micro"]["top_users"] == []
    assert result["data_scope"]["platform"] == "weibo"


def test_comment_only_event_is_sent_to_model_instead_of_being_marked_empty(monkeypatch):
    captured = {}

    async def fake_posts(*_args, **_kwargs):
        return []

    async def fake_comments(*_args, **_kwargs):
        return [{
            "comment_id": "c1",
            "post_id": "p1",
            "author_id": "u1",
            "author_name": "Alice",
            "timestamp": "2026-05-11T00:00:00Z",
        }]

    async def fake_predictor(*, posts, comments, top_k, observation_ratio):
        captured.update({
            "posts": posts,
            "comments": comments,
            "observation_ratio": observation_ratio,
        })
        result = propagation_model_service.empty_prediction_result("event-1", "twitter")
        result["status"] = "ok"
        result["model_status"] = "available"
        result["macro"].update({
            "observed_size": 1,
            "predicted_size": 1,
            "trend_points": [{"step": 1, "predicted_size": 1}],
        })
        return result

    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: object())
    monkeypatch.setattr(propagation_model_service, "load_event_posts", fake_posts)
    monkeypatch.setattr(propagation_model_service, "load_event_comments", fake_comments)
    monkeypatch.setattr(
        propagation_model_service.propagation_prediction_service,
        "predict_event_macro_micro",
        fake_predictor,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="twitter",
        )
    )

    assert result["status"] == "ok"
    assert captured["posts"] == []
    assert len(captured["comments"]) == 1
    assert captured["observation_ratio"] == 0.5
    assert result["data_scope"]["posts"] == 0
    assert result["data_scope"]["comments"] == 1


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
