"""Security regressions for account labeling and dataset exports."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import accounts as accounts_api
from app.config import settings
from app.core.security import get_current_user
from app.main import app
from app.models.account_labeling import AccountBehaviorLabelRecord
from app.services import account_dataset_service
from app.services import account_label_service
from app.utils.exceptions import AppException


def _set_user(user: SimpleNamespace) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _clear_user() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def test_account_label_submission_allows_analyst_and_denies_viewer(monkeypatch):
    calls: list[int] = []

    async def override_db():
        yield SimpleNamespace()

    async def fake_submit(_session, **kwargs):
        calls.append(kwargs["analyst_id"])
        return {"label_id": "label-1"}

    app.dependency_overrides[accounts_api.get_db] = override_db
    monkeypatch.setattr(accounts_api.account_label_service, "submit_account_label", fake_submit)

    async def request_as(role: str):
        _set_user(SimpleNamespace(id=3, role=role, is_active=True))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/accounts/labels",
                json={
                    "case_id": "case-1",
                    "behavior_label": "bot",
                    "case_fingerprint": "a" * 64,
                },
            )

    try:
        viewer = asyncio.run(request_as("viewer"))
        analyst = asyncio.run(request_as("analyst"))
    finally:
        _clear_user()
        app.dependency_overrides.pop(accounts_api.get_db, None)

    assert viewer.status_code == 403
    assert analyst.status_code == 200
    assert calls == [3]


def test_viewer_cannot_start_bot_detection(monkeypatch):
    called = False

    async def fake_detect(**_kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(accounts_api.bot_detection_service, "detect_social_bots", fake_detect)
    _set_user(SimpleNamespace(id=3, role="viewer", is_active=True))

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/accounts/bot-detection")

    try:
        response = asyncio.run(request())
    finally:
        _clear_user()

    assert response.status_code == 403
    assert called is False


def test_only_admin_can_export_account_datasets(monkeypatch):
    calls: list[int] = []

    async def override_db():
        yield SimpleNamespace()

    async def fake_export(_session, **kwargs):
        calls.append(kwargs["operator_id"])
        return {"dataset_version_id": "dataset-1"}

    app.dependency_overrides[accounts_api.get_db] = override_db
    monkeypatch.setattr(accounts_api.account_dataset_service, "export_approved_account_dataset", fake_export)

    async def request_as(role: str):
        _set_user(SimpleNamespace(id=7, role=role, is_active=True))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/accounts/datasets/export", json={"output_dir": "exports/dataset-1"})

    try:
        viewer = asyncio.run(request_as("viewer"))
        analyst = asyncio.run(request_as("analyst"))
        admin = asyncio.run(request_as("admin"))
    finally:
        _clear_user()
        app.dependency_overrides.pop(accounts_api.get_db, None)

    assert viewer.status_code == 403
    assert analyst.status_code == 403
    assert admin.status_code == 200
    assert calls == [7]


def test_only_admin_can_control_account_training_runs(monkeypatch):
    async def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[accounts_api.get_db] = override_db
    monkeypatch.setattr(accounts_api.account_training_service, "create_account_training_run", _unexpected_call)
    monkeypatch.setattr(accounts_api.account_training_service, "cancel_account_training_run", _unexpected_call)
    monkeypatch.setattr(accounts_api.account_training_service, "resume_account_training_run", _unexpected_call)

    async def request_as(role: str, path: str, payload: dict | None = None):
        _set_user(SimpleNamespace(id=7, role=role, is_active=True))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            if payload is None:
                return await client.post(path)
            return await client.post(path, json=payload)

    try:
        responses = [
            asyncio.run(
                request_as(
                    "analyst",
                    "/api/v1/accounts/training-runs",
                    {"family": "encoder", "corpus_version_id": "corpus-1", "input_fingerprint": "a" * 64},
                )
            ),
            asyncio.run(request_as("analyst", "/api/v1/accounts/training-runs/run-1/cancel")),
            asyncio.run(request_as("analyst", "/api/v1/accounts/training-runs/run-1/resume")),
        ]
    finally:
        _clear_user()
        app.dependency_overrides.pop(accounts_api.get_db, None)

    assert [response.status_code for response in responses] == [403, 403, 403]


def test_account_model_evaluation_compatibility_api_requires_signed_manifest(monkeypatch):
    called = False

    async def override_db():
        yield SimpleNamespace()

    async def fake_writeback(_session, **_kwargs):
        nonlocal called
        called = True
        return {"status": "shadow"}

    app.dependency_overrides[accounts_api.get_db] = override_db
    monkeypatch.setattr(
        accounts_api.account_model_governance_service,
        "write_account_model_evaluation",
        fake_writeback,
    )
    _set_user(SimpleNamespace(id=7, role="admin", is_active=True))

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/accounts/models/model-1/evaluation-writeback-compatibility",
                json={
                    "artifact_hash": "a" * 64,
                    "evaluation_run_id": "run-1",
                    "prediction_audits": [],
                },
            )

    try:
        response = asyncio.run(request())
    finally:
        _clear_user()
        app.dependency_overrides.pop(accounts_api.get_db, None)

    assert response.status_code == 422
    assert called is False


def test_account_label_api_requires_case_fingerprint():
    async def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[accounts_api.get_db] = override_db
    _set_user(SimpleNamespace(id=7, role="analyst", is_active=True))

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/accounts/labels",
                json={"case_id": "case-1", "behavior_label": "bot"},
            )

    try:
        response = asyncio.run(request())
    finally:
        _clear_user()
        app.dependency_overrides.pop(accounts_api.get_db, None)

    assert response.status_code == 400
    assert "case_fingerprint" in response.json()["msg"]


def test_label_service_rejects_empty_case_fingerprint():
    case = SimpleNamespace(case_fingerprint="a" * 64)

    class Result:
        def scalar_one_or_none(self):
            return case

    class Session:
        async def execute(self, _statement):
            return Result()

    with pytest.raises(AppException, match="required"):
        asyncio.run(
            account_label_service.submit_account_label(
                Session(),
                case_id="case-1",
                batch_id=None,
                behavior_label="bot",
                confidence=0.9,
                evidence_post_ids=[],
                reason_tags=[],
                notes="",
                case_fingerprint="",
                analyst_id=7,
            )
        )


def test_dataset_export_rejects_absolute_and_parent_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))

    with pytest.raises(AppException, match="relative"):
        account_dataset_service._resolve_account_dataset_output_dir(tmp_path / "outside", "dataset-1")
    with pytest.raises(AppException, match="outside"):
        account_dataset_service._resolve_account_dataset_output_dir("exports/../outside", "dataset-1")


def test_dataset_export_resolves_compatible_relative_output_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))

    target = account_dataset_service._resolve_account_dataset_output_dir("exports/dataset-1", "dataset-1")

    assert target == tmp_path / "exports" / "dataset-1"


def test_label_author_cannot_adjudicate_own_label():
    record = SimpleNamespace(analyst_id=7)

    class Result:
        def scalar_one_or_none(self):
            return record

    class Session:
        async def execute(self, _statement):
            return Result()

    with pytest.raises(AppException, match="own label"):
        asyncio.run(
            account_label_service.adjudicate_account_label(
                Session(),
                label_id="label-self-review",
                approved=True,
                adjudicator_id=7,
            )
        )


def test_adjudication_requires_matching_active_review_assignment():
    record = SimpleNamespace(
        label_id="label-1",
        case_id="case-1",
        batch_id=None,
        behavior_label="bot",
        training_target="bot",
        label_status="submitted",
        analyst_id=7,
        confidence=0.9,
        evidence_post_ids_json="[]",
        reason_tags_json="[]",
        notes="submitted evidence",
        case_fingerprint="f" * 64,
        supersedes_id=None,
        review_required=True,
        second_review_status="assigned",
    )

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Session:
        def __init__(self):
            self.values = [record, None, None]

        async def execute(self, _statement):
            return Result(self.values.pop(0))

    with pytest.raises(AppException, match="active review assignment"):
        asyncio.run(
            account_label_service.adjudicate_account_label(
                Session(),
                label_id="label-1",
                approved=True,
                adjudicator_id=9,
            )
        )


def test_adjudication_appends_revision_without_mutating_submitted_label():
    record = SimpleNamespace(
        label_id="label-1",
        case_id="case-1",
        batch_id="batch-1",
        behavior_label="insufficient_evidence",
        training_target="abstain",
        label_status="submitted",
        analyst_id=7,
        confidence=0.4,
        evidence_post_ids_json="[\"post-1\"]",
        reason_tags_json="[\"insufficient_evidence\"]",
        notes="submitted evidence",
        case_fingerprint="f" * 64,
        supersedes_id=None,
        review_required=True,
        second_review_status="assigned",
    )
    assignment = SimpleNamespace(review_status="assigned", completed_at=None)

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Session:
        def __init__(self):
            self.values = [record, None, assignment]
            self.added = []

        async def execute(self, _statement):
            return Result(self.values.pop(0))

        def add(self, value):
            self.added.append(value)

        async def flush(self):
            return None

    session = Session()
    result = asyncio.run(
        account_label_service.adjudicate_account_label(
            session,
            label_id="label-1",
            approved=True,
            adjudicator_id=9,
            behavior_label="human",
        )
    )

    assert result is not None
    assert result["supersedes_id"] == "label-1"
    assert result["behavior_label"] == "human"
    assert record.behavior_label == "insufficient_evidence"
    assert record.label_status == "submitted"
    assert assignment.review_status == "completed"
    assert len(session.added) == 1


def test_export_query_excludes_insufficient_evidence_training_target():
    class Result:
        def all(self):
            return []

    class Session:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return Result()

    session = Session()
    assert asyncio.run(account_dataset_service._approved_label_rows(session)) == []
    bound_values = session.statement.compile().params.values()

    assert {"bot", "non_bot"} in [set(value) for value in bound_values if isinstance(value, (list, tuple))]
    assert {"bot", "human"} in [set(value) for value in bound_values if isinstance(value, (list, tuple))]
    assert all("abstain" not in value for value in bound_values if isinstance(value, (list, tuple)))


async def _unexpected_call(*_args, **_kwargs):
    raise AssertionError("non-admin reached account training governance service")
