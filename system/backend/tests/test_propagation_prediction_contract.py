"""HTTP contract tests for the event-scoped propagation prediction page.

These tests deliberately exercise the route boundary rather than only the
prediction service.  The frontend consumes the response under ``data`` and
needs a stable list-shaped ``macro.trend_points`` value before it can render
the chart.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pathlib import Path

from app.core.security import get_current_user_or_local_preview
from app.main import app
from app.api.v1 import propagation as propagation_api
from app.schemas.propagation import PropagationPredictionData
from app.services import propagation_model_service, propagation_observation_service
from app.services import propagation_prediction_service


def _prediction_payload(*, status: str = "ok", model_status: str = "available") -> dict:
    return {
        "status": status,
        "model_status": model_status,
        "event_id": "event-1",
        "platform": "twitter",
        "macro": {
            "observed_size": 3,
            "predicted_size": 8,
            "trend_points": [
                {"step": 1, "at": "2026-05-11T01:00:00+00:00", "predicted_size": 4},
                {"step": 2, "at": "2026-05-11T02:00:00+00:00", "predicted_size": 8},
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
                    "score": 0.75,
                    "candidate_source": "observed_user",
                    "activation_type": "reactivation",
                    "identity_resolution": "unique_current_event_bucket_proxy",
                    "score_semantics": "bucket_probability_shared_across_observed_bucket_members",
                    "bucket_collision_size": 1,
                    "evidence_refs": [],
                    "trace_available": True,
                }
            ],
            "candidate_count": 3,
            "candidate_bucket_count": 3,
            "candidate_source_counts": {"observed_user_buckets": 3},
            "reactivation_count": 1,
            "new_activation_count": 0,
            "coverage": {
                "mapped_candidate_buckets": 3,
                "unmapped_candidate_buckets": 0,
                "legal_candidate_buckets": 3,
                "mapped_probability_mass": 1.0,
                "new_activation_status": "abstain_no_identity_mapping",
                "identity_mapping_status": "unique_current_event_bucket_proxy_only",
            },
        },
        "data_scope": {
            "event_id": "event-1",
            "platform": "twitter",
            "observed_until": "2026-05-11T00:00:00+00:00",
            "prediction_horizon_hours": None,
            "trajectory_time_basis": "normalized_model_steps",
            "observation_ratio": 0.3,
        },
        "model": {
            "name": "PropagationSequenceJointModel",
            "dataset": "twitter",
            "checkpoint": "system-checkpoint.pt",
        },
    }


async def _request_prediction(query: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(f"/api/v1/propagation/model-event-predict?{query}")


def test_cached_benchmark_evidence_is_research_only_route():
    paths = {
        route.path
        for route in propagation_api.router.routes
        if hasattr(route, "path")
    }

    assert "/model-predict" not in paths
    assert "/research/model-predict" in paths


def test_frontend_api_does_not_export_research_prediction_route():
    source_path = Path(__file__).parents[2] / "frontend" / "src" / "api" / "propagation.ts"
    source = source_path.read_text(encoding="utf-8")

    assert "predictPropagationModel" not in source
    assert "request.post('/propagation/research/model-predict'" not in source
    assert "request.post('/propagation/model-predict'" not in source
    assert "request.post('/propagation/model-event-predict'" in source


def test_frontend_prediction_normalizer_preserves_scope_and_identity_coverage():
    source_path = Path(__file__).parents[2] / "frontend" / "src" / "views" / "propagation" / "index.vue"
    source = source_path.read_text(encoding="utf-8")

    assert "identity_mapping_status" in source
    assert "coverage: {" in source
    assert "scope: typeof rawModel.scope" in source
    assert "checkpoint_conditioning_ratio" in source
    assert ':disabled="!eventId.trim()"' in source


def test_prediction_contract_exposes_coverage_calibration_and_model_scope():
    payload = _prediction_payload()
    payload["model"]["scope"] = "current_event"

    parsed = PropagationPredictionData.model_validate(payload)

    assert parsed.macro.calibration_status == "unavailable"
    assert parsed.macro.intervals is None
    assert parsed.micro.coverage.mapped_candidate_buckets == 3
    assert parsed.micro.coverage.legal_candidate_buckets == 3
    assert parsed.micro.coverage.identity_mapping_status == "unique_current_event_bucket_proxy_only"
    assert parsed.micro.top_users[0].identity_resolution == "unique_current_event_bucket_proxy"
    assert parsed.model is not None
    assert parsed.model.scope == "current_event"


def test_cached_result_uses_readable_experimental_label():
    result = propagation_prediction_service._format_result(
        propagation_analysis_rows=[
            {
                "model": propagation_prediction_service.PROPAGATION_MODEL_NAME,
                "status": "ok",
                "dataset": "twitter",
                "seed": 42,
                "training_protocol": {},
            }
        ],
        minds_rows=[],
        dataset="twitter",
        seed=42,
        source="cached_artifact",
        artifact="fixture.json",
        evidence_level="sampled_experiment",
        full_validation_passed=False,
        boundary="",
    )

    assert result["label"] == "实验预测"


def test_prediction_service_description_does_not_claim_checkpoint_unavailable():
    description = propagation_prediction_service.__doc__ or ""

    assert "event checkpoint inference stay unavailable" not in description
    assert "deployed checkpoint inference" in description


@pytest.mark.asyncio
async def test_benchmark_prediction_route_is_research_only_and_hidden_from_schema(monkeypatch):
    async def fake_benchmark_model_evidence(**kwargs):
        assert kwargs == {"dataset": "twitter", "seed": 42, "run_live": False}
        return {
            "status": "ok",
            "dataset": "twitter",
            "seed": 42,
            "source": "cached",
            "macro": {},
            "micro": {},
        }

    async def fake_preview_user():
        return None

    monkeypatch.setattr(
        propagation_model_service,
        "predict_benchmark_model_evidence",
        fake_benchmark_model_evidence,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            old_response = await client.post("/api/v1/propagation/model-predict?dataset=twitter")
            research_response = await client.post(
                "/api/v1/propagation/research/model-predict?dataset=twitter"
            )
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert old_response.status_code == 404
    assert research_response.status_code == 200
    assert research_response.json()["data"]["source"] == "cached"
    schema_paths = app.openapi()["paths"]
    assert "/api/v1/propagation/model-predict" not in schema_paths
    assert "/api/v1/propagation/research/model-predict" not in schema_paths


@pytest.mark.asyncio
async def test_event_prediction_route_exposes_frontend_render_contract(monkeypatch):
    async def fake_predict_current_event_model(**kwargs):
        assert kwargs == {
            "platform": "twitter",
            "event_id": "event-1",
            "top_k": 5,
            "observed_until": "2026-05-11T00:00:00+00:00",
            "observation_ratio": 0.3,
        }
        return _prediction_payload()

    async def fake_preview_user():
        return None

    monkeypatch.setattr(
        propagation_model_service,
        "predict_current_event_model",
        fake_predict_current_event_model,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        response = await _request_prediction(
            "event_id=event-1&platform=twitter&top_k=5"
            "&observed_until=2026-05-11T00:00:00%2B00:00&observation_ratio=0.3"
        )
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["status"] == "ok"
    assert data["model_status"] == "available"
    assert isinstance(data["macro"]["trend_points"], list)
    assert [point["predicted_size"] for point in data["macro"]["trend_points"]] == [4, 8]
    assert data["micro"]["top_users"][0]["author_id"] == "u2"
    assert data["data_scope"]["observed_until"].endswith("+00:00")


@pytest.mark.asyncio
async def test_event_prediction_route_requires_event_id(monkeypatch):
    async def fake_preview_user():
        return None

    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        response = await _request_prediction("platform=twitter")
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 422
    assert any(error.get("loc", [])[-1:] == ["event_id"] for error in response.json()["detail"])


@pytest.mark.asyncio
async def test_event_prediction_route_rejects_conflicting_cutoff_aliases(monkeypatch):
    model_calls = []

    async def fake_predict_current_event_model(**kwargs):
        model_calls.append(kwargs)
        return _prediction_payload()

    async def fake_preview_user():
        return None

    monkeypatch.setattr(
        propagation_model_service,
        "predict_current_event_model",
        fake_predict_current_event_model,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        response = await _request_prediction(
            "event_id=event-1&observed_until=2026-05-11T00:00:00%2B00:00"
            "&t_obs=2026-05-11T01:00:00%2B00:00"
        )
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 422
    assert "must identify the same instant" in response.json()["detail"]
    assert model_calls == []


@pytest.mark.asyncio
async def test_event_prediction_route_rejects_unsupported_wall_clock_horizon(monkeypatch):
    async def fake_preview_user():
        return None

    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        response = await _request_prediction(
            "event_id=event-1&platform=twitter&prediction_horizon=6"
        )
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 422
    assert "normalized trajectory steps" in response.json()["detail"]


@pytest.mark.asyncio
async def test_event_prediction_route_rejects_unsupported_observation_ratio(monkeypatch):
    model_calls = []

    async def fake_predict_current_event_model(**kwargs):
        model_calls.append(kwargs)
        return _prediction_payload()

    async def fake_preview_user():
        return None

    monkeypatch.setattr(
        propagation_model_service,
        "predict_current_event_model",
        fake_predict_current_event_model,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        response = await _request_prediction(
            "event_id=event-1&platform=twitter&observation_ratio=0.2"
        )
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 422
    assert "observation_ratio must be one of" in response.json()["detail"]
    assert model_calls == []


@pytest.mark.asyncio
async def test_event_prediction_route_preserves_silent_abstain_schema(monkeypatch):
    async def fake_predict_current_event_model(**_kwargs):
        return propagation_model_service.empty_prediction_result("event-1", "twitter")

    async def fake_preview_user():
        return None

    monkeypatch.setattr(
        propagation_model_service,
        "predict_current_event_model",
        fake_predict_current_event_model,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        response = await _request_prediction("event_id=event-1&platform=twitter")
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "data_insufficient"
    assert data["model_status"] == "unavailable"
    assert data["macro"]["trend_points"] == []
    assert data["micro"]["top_users"] == []
    assert data["event_id"] == "event-1"
    assert data["platform"] == "twitter"


@pytest.mark.asyncio
async def test_event_prediction_route_converts_nested_contract_errors_to_abstain(monkeypatch):
    async def fake_predict_current_event_model(**_kwargs):
        payload = _prediction_payload()
        payload["macro"]["trend_points"] = "not-a-list"
        return payload

    async def fake_preview_user():
        return None

    monkeypatch.setattr(
        propagation_model_service,
        "predict_current_event_model",
        fake_predict_current_event_model,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        response = await _request_prediction("event_id=event-1&platform=twitter")
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "model_error"
    assert data["model_status"] == "unavailable"
    assert data["macro"]["trend_points"] == []
    assert data["micro"]["top_users"] == []


@pytest.mark.asyncio
async def test_event_prediction_route_accepts_pointwise_prediction_intervals(monkeypatch):
    async def fake_predict_current_event_model(**_kwargs):
        payload = _prediction_payload()
        payload["macro"]["intervals"] = [
            {"step": 1, "at": "2026-05-11T01:00:00+00:00", "lower": 3, "upper": 6},
            {"step": 2, "at": "2026-05-11T02:00:00+00:00", "lower": 5, "upper": 10},
        ]
        return payload

    async def fake_preview_user():
        return None

    monkeypatch.setattr(
        propagation_model_service,
        "predict_current_event_model",
        fake_predict_current_event_model,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        response = await _request_prediction("event_id=event-1&platform=twitter")
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 200
    intervals = response.json()["data"]["macro"]["intervals"]
    assert isinstance(intervals, list)
    assert intervals[1]["upper"] == 10.0


@pytest.mark.asyncio
async def test_observed_analysis_route_does_not_call_prediction(monkeypatch):
    calls = []

    async def fake_observed_analysis(**kwargs):
        return {"graph": {}, "event_id": kwargs.get("event_id")}

    async def fail_prediction(**_kwargs):
        calls.append("prediction")
        raise AssertionError("observed analysis must not invoke prediction")

    async def fake_preview_user():
        return None

    monkeypatch.setattr(
        propagation_observation_service,
        "analyze_observed_propagation",
        fake_observed_analysis,
    )
    monkeypatch.setattr(
        propagation_model_service,
        "predict_current_event_model",
        fail_prediction,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/propagation/observed-analysis?event_id=event-1&platform=twitter"
            )
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert response.status_code == 200
    assert response.json()["data"] == {"graph": {}, "event_id": "event-1"}
    assert calls == []
