from __future__ import annotations

import asyncio
import hashlib
import json
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient
import pytest

from app.api.v1 import accounts as accounts_api
from app.core.account_active_learning import select_account_detection_label_batch
from app.core.account_labeling import (
    AccountBehaviorLabel,
    build_account_detection_cases,
    normalize_account_behavior_label,
)
from app.core.security import get_current_user
from app.db.mysql import get_db
from app.main import app
from app.models.account_labeling import (
    AccountBehaviorLabelRecord,
    AccountDetectionCaseRecord,
    AccountDetectionDatasetVersion,
    AccountDetectionModelVersion,
    AccountLabelBatchItem,
)
from app.models.user import User
from app.services.account_dataset_service import export_approved_account_dataset
from app.services.account_label_service import adjudicate_account_label
from app.services.account_label_service import submit_account_label as submit_account_label_service
from app.services.account_model_governance_service import activate_account_detection_model
from app.services.account_model_governance_service import approve_account_detection_model
from app.services.account_model_governance_service import evaluate_account_model_activation_gates
from app.services.account_model_governance_service import register_account_training_candidate
from app.utils.exceptions import AppException


def _post(account_id: str, content: str, *, platform: str = "weibo", post_id: str | None = None) -> dict:
    return {
        "event_id": "event-1",
        "platform": platform,
        "post_id": post_id or f"{account_id}-1",
        "author_id": account_id,
        "author_name": account_id,
        "timestamp": "2026-05-21T00:00:00+08:00",
        "content": content,
    }


def test_case_registry_builds_stable_account_fingerprints():
    posts = [
        _post("u1", "第一条公开发言", post_id="p1"),
        _post("u1", "第二条公开发言", post_id="p2"),
        _post("u2", "另一个账号", post_id="p3"),
    ]

    cases = build_account_detection_cases(posts, event_id="event-1", platform="weibo")
    cases_again = build_account_detection_cases(list(reversed(posts)), event_id="event-1", platform="weibo")

    assert [case.account_id for case in cases] == ["u1", "u2"]
    assert cases[0].post_ids == ["p1", "p2"]
    assert cases[0].case_fingerprint == cases_again[0].case_fingerprint
    assert cases[0].label_source_policy == "analyst_observed_behavior_only"


def test_label_taxonomy_rejects_identity_or_attribution_labels():
    assert normalize_account_behavior_label("bot").training_target == "bot"
    assert normalize_account_behavior_label(AccountBehaviorLabel.HUMAN).training_target == "non_bot"
    assert normalize_account_behavior_label("insufficient_evidence").training_target == "abstain"

    with pytest.raises(ValueError, match="human, bot, or insufficient_evidence"):
        normalize_account_behavior_label("foreign_actor")


def test_label_batch_excludes_approved_cases_and_marks_review_only_outputs(monkeypatch):
    cases = build_account_detection_cases(
        [
            _post("u1", "短时间重复转发链接", post_id="p1"),
            _post("u2", "正常讨论", post_id="p2"),
            _post("u3", "相似文本模板", platform="xhs", post_id="p3"),
        ],
        event_id="event-1",
        platform=None,
    )

    monkeypatch.setattr("app.core.account_active_learning.settings.ACCOUNT_ACQUISITION_TEXT_MODEL_PATH", "local-mlm")
    monkeypatch.setattr(
        "app.core.account_active_learning._alps_embeddings_for_cases",
        lambda _active_learning, rows: {
            row.case_id: [1.0 if index == 0 else 0.0, float(index)]
            for index, row in enumerate(rows)
        },
    )

    batch = select_account_detection_label_batch(
        cases,
        model_outputs={
            "u1": {"bot_probability": 0.52},
            "u2": {"bot_probability": 0.05},
            "u3": {"bot_probability": 0.48},
        },
        approved_case_ids={cases[1].case_id},
        budget=2,
    )

    assert batch["policy"] == "human_review_required"
    assert len(batch["items"]) == 2
    assert cases[1].case_id not in {item["case_id"] for item in batch["items"]}
    assert batch["strategy"] == "cold_start_alps_core_set"
    assert batch["manifest"]["excluded_approved_label_count"] == 1


def test_label_batch_requires_configured_alps_model_for_cold_start(monkeypatch):
    cases = build_account_detection_cases(
        [_post("u1", "public weibo text", post_id="p1")],
        event_id="event-1",
        platform="weibo",
    )

    monkeypatch.setattr("app.core.account_active_learning.settings.ACCOUNT_ACQUISITION_TEXT_MODEL_PATH", "")
    with pytest.raises(AppException, match="ACCOUNT_ACQUISITION_TEXT_MODEL_PATH"):
        select_account_detection_label_batch(cases, budget=1, cold_start=True)


def test_label_batch_uses_only_calibrated_model_uncertainty_and_passes_warm_start_signals():
    cases = build_account_detection_cases(
        [
            _post("u1", "重复模板和链接", post_id="p1"),
            _post("u2", "普通讨论", post_id="p2"),
        ],
        event_id="event-1",
        platform="weibo",
    )

    batch = select_account_detection_label_batch(
        cases,
        model_outputs={
            "u1": {
                "calibrated_probability": 0.51,
                "calibrated": True,
                "calibration_source": "temperature_scaling",
                "badge_embedding": [1.0, 0.0, 0.0, 0.0],
            },
            "u2": {
                "calibrated_probability": 0.8,
                "calibrated": True,
                "calibration_source": "temperature_scaling",
                "badge_embedding": [0.0, 1.0, 0.0, 0.0],
            },
        },
        budget=1,
    )

    assert batch["strategy"] == "warm_start_calibrated_uncertainty_badge"
    assert batch["items"][0]["account_id"] == "u1"
    assert batch["items"][0]["scores"]["calibrated_uncertainty"] > 0.9
    assert "badge_vector_norm" in batch["items"][0]["scores"]


def test_label_batch_rejects_incomplete_warm_start_payload():
    cases = build_account_detection_cases(
        [
            _post("u1", "异常模型输出不应破坏选样", post_id="p1"),
            _post("u2", "另一个候选", post_id="p2"),
        ],
        event_id="event-1",
        platform="weibo",
    )

    with pytest.raises(AppException, match="badge_embedding"):
        select_account_detection_label_batch(
            cases,
            model_outputs={
                "u1": {
                    "calibrated_probability": 0.51,
                    "calibrated": True,
                    "calibration_source": "temperature_scaling",
                },
                "u2": {
                    "calibrated_probability": 0.49,
                    "calibrated": True,
                    "calibration_source": "temperature_scaling",
                    "badge_embedding": [0.0, 1.0],
                },
            },
            budget=1,
        )


def test_account_model_activation_requires_frozen_holdout_and_dual_approval():
    failed = evaluate_account_model_activation_gates(
        {
            "frozen_holdout_passed": True,
            "time_forward_passed": True,
            "platform_stratified_passed": True,
            "community_disjoint_passed": False,
            "ece": 0.05,
            "false_positive_burden_passed": True,
            "shadow_run_passed": True,
        },
        approver_ids=[7, 7],
    )

    assert failed["activation_allowed"] is False
    assert failed["gates"]["dual_approval"] is False
    assert failed["gates"]["community_disjoint"] is False

    passed = evaluate_account_model_activation_gates(
        {
            "frozen_holdout_passed": True,
            "time_forward_passed": True,
            "platform_stratified_passed": True,
            "community_disjoint_passed": True,
            "ece": 0.05,
            "false_positive_burden_passed": True,
            "shadow_run_passed": True,
        },
        approver_ids=[7, 9],
    )

    assert passed["activation_allowed"] is True


def test_account_active_learning_api_routes_to_service(monkeypatch):
    calls = {}

    async def override_db():
        yield SimpleNamespace()

    async def fake_create_batch(session, **kwargs):
        calls.update(kwargs)
        return {"batch_id": "account-label-batch-1", "items": []}

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role="analyst", is_active=True)
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(accounts_api.account_active_learning_service, "create_account_label_batch", fake_create_batch)

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/accounts/active-learning/batches",
                json={"event_id": "event-1", "platform": "weibo", "budget": 3, "cold_start": True},
            )

    try:
        response = asyncio.run(_request())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["data"]["batch_id"] == "account-label-batch-1"
    assert calls == {
        "event_id": "event-1",
        "platform": "weibo",
        "budget": 3,
        "cold_start": True,
        "operator_id": 7,
    }


def test_account_label_api_rejects_non_observable_labels(monkeypatch):
    async def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role="analyst", is_active=True)
    app.dependency_overrides[get_db] = override_db

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/accounts/labels",
                json={
                    "case_id": "case-1",
                    "behavior_label": "foreign_actor",
                    "confidence": 0.7,
                },
            )

    try:
        response = asyncio.run(_request())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert response.json()["code"] == 400
    assert "human, bot, or insufficient_evidence" in response.json()["msg"]


@pytest.mark.asyncio
async def test_approved_account_dataset_export_registers_manifest(db_session, tmp_path):
    case = AccountDetectionCaseRecord(
        case_id="case-1",
        account_id="account-1",
        platform="weibo",
        event_id="event-1",
        author_name="account-1",
        case_fingerprint="f" * 64,
        post_ids_json=json.dumps(["post-1"]),
        evidence_post_ids_json=json.dumps(["post-1"]),
        payload_json=json.dumps(
            {
                "case_id": "case-1",
                "account_id": "account-1",
                "platform": "weibo",
                "event_id": "event-1",
                "text": "公开微博文本",
            },
            ensure_ascii=False,
        ),
        model_output_json="{}",
        label_status="labeled",
    )
    label = AccountBehaviorLabelRecord(
        label_id="label-1",
        case_id="case-1",
        batch_id=None,
        behavior_label="bot",
        training_target="bot",
        label_status="approved",
        analyst_id=7,
        confidence=0.9,
        evidence_post_ids_json=json.dumps(["post-1"]),
        reason_tags_json=json.dumps(["temporal_activity_evidence"]),
        notes="approved observable behavior",
        case_fingerprint="f" * 64,
    )
    db_session.add_all([case, label])
    await db_session.flush()

    dataset = await export_approved_account_dataset(
        db_session,
        dataset_version_id="account-dataset-test",
        output_dir=tmp_path / "account-dataset-test",
        operator_id=7,
    )

    assert dataset["dataset_version_id"] == "account-dataset-test"
    assert dataset["source_label_count"] == 1
    assert dataset["manifest"]["source_policy"] == "approved_or_adjudicated_observable_behavior_labels_only"
    output_path = tmp_path / "account-dataset-test" / "approved_account_labels.jsonl"
    assert output_path.is_file()
    assert (tmp_path / "account-dataset-test" / "dataset_card.md").is_file()
    exported = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert exported["training_target"] == "bot"
    assert exported["text"] == "公开微博文本"


@pytest.mark.asyncio
async def test_approved_account_dataset_export_rejects_empty_corpus(db_session, tmp_path):
    with pytest.raises(AppException, match="No approved or adjudicated account labels"):
        await export_approved_account_dataset(
            db_session,
            dataset_version_id="empty-dataset",
            output_dir=tmp_path / "empty-dataset",
            operator_id=7,
        )


@pytest.mark.asyncio
async def test_adjudication_status_is_recorded_when_label_changes(db_session):
    label = AccountBehaviorLabelRecord(
        label_id="label-change-1",
        case_id="case-change-1",
        batch_id=None,
        behavior_label="insufficient_evidence",
        training_target="abstain",
        label_status="submitted",
        analyst_id=7,
        confidence=0.4,
        evidence_post_ids_json="[]",
        reason_tags_json="[]",
        notes="submitted with thin evidence",
        case_fingerprint="",
    )
    db_session.add(label)
    await db_session.flush()

    result = await adjudicate_account_label(
        db_session,
        label_id="label-change-1",
        approved=True,
        adjudicator_id=9,
        behavior_label="human",
        notes="adjudicator changed the label after review",
    )

    assert result is not None
    assert result["behavior_label"] == "human"
    assert result["training_target"] == "non_bot"
    assert result["label_status"] == "adjudicated"


@pytest.mark.asyncio
async def test_account_label_submission_validates_case_batch_fingerprint_and_evidence(db_session):
    case = AccountDetectionCaseRecord(
        case_id="case-validate-1",
        account_id="account-1",
        platform="weibo",
        event_id="event-1",
        author_name="account-1",
        case_fingerprint="a" * 64,
        post_ids_json=json.dumps(["post-1"]),
        evidence_post_ids_json=json.dumps(["post-1"]),
        payload_json="{}",
        model_output_json="{}",
    )
    item = AccountLabelBatchItem(
        batch_id="batch-validate-1",
        case_id="case-validate-1",
        account_id="account-1",
        platform="weibo",
        event_id="event-1",
        priority_rank=1,
        selection_bucket="random_audit",
        acquisition_scores_json="{}",
        status="queued",
    )
    db_session.add_all([case, item])
    await db_session.flush()

    with pytest.raises(AppException, match="fingerprint"):
        await submit_account_label_service(
            db_session,
            case_id="case-validate-1",
            batch_id="batch-validate-1",
            behavior_label="bot",
            confidence=0.8,
            evidence_post_ids=["post-1"],
            reason_tags=[],
            notes="",
            case_fingerprint="b" * 64,
            analyst_id=7,
        )

    with pytest.raises(AppException, match="evidence_post_ids"):
        await submit_account_label_service(
            db_session,
            case_id="case-validate-1",
            batch_id="batch-validate-1",
            behavior_label="bot",
            confidence=0.8,
            evidence_post_ids=["foreign-post"],
            reason_tags=[],
            notes="",
            case_fingerprint="a" * 64,
            analyst_id=7,
        )

    result = await submit_account_label_service(
        db_session,
        case_id="case-validate-1",
        batch_id="batch-validate-1",
        behavior_label="bot",
        confidence=0.8,
        evidence_post_ids=["post-1"],
        reason_tags=["temporal_activity_evidence"],
        notes="approved observable behavior",
        case_fingerprint="a" * 64,
        analyst_id=7,
    )

    assert result["case_fingerprint"] == "a" * 64
    assert result["behavior_label"] == "bot"


@pytest.mark.asyncio
async def test_training_candidate_requires_registered_dataset_and_matching_artifact_hash(db_session, tmp_path):
    artifact = tmp_path / "checkpoint.pt"
    artifact.write_bytes(b"checkpoint")

    with pytest.raises(AppException, match="dataset version not found"):
        await register_account_training_candidate(
            db_session,
            model_version="account-model-missing-dataset",
            dataset_version_id="missing-dataset",
            artifact_uri=str(artifact),
            artifact_hash="bad",
            metrics={},
            operator_id=7,
        )

    db_session.add(
        AccountDetectionDatasetVersion(
            dataset_version_id="dataset-ready-1",
            data_fingerprint="d" * 64,
            source_label_count=2,
            artifact_uri=str(tmp_path),
            manifest_json="{}",
            status="candidate",
            created_by=7,
        )
    )
    await db_session.flush()

    with pytest.raises(AppException, match="artifact_hash"):
        await register_account_training_candidate(
            db_session,
            model_version="account-model-bad-hash",
            dataset_version_id="dataset-ready-1",
            artifact_uri=str(artifact),
            artifact_hash="bad",
            metrics={},
            operator_id=7,
        )

    result = await register_account_training_candidate(
        db_session,
        model_version="account-model-good",
        dataset_version_id="dataset-ready-1",
        artifact_uri=str(artifact),
        artifact_hash=hashlib.sha256(b"checkpoint").hexdigest(),
        metrics={"frozen_holdout_passed": False},
        operator_id=7,
    )

    assert result["model_version"] == "account-model-good"
    assert result["artifact_hash"] == hashlib.sha256(b"checkpoint").hexdigest()
    assert result["metrics"]["dataset_fingerprint"] == "d" * 64


@pytest.mark.asyncio
async def test_account_model_activation_uses_immutable_admin_approval_records(db_session):
    admin_1 = User(
        username="admin-a",
        email="admin-a@example.com",
        hashed_password="x",
        role="admin",
        is_active=True,
    )
    admin_2 = User(
        username="admin-b",
        email="admin-b@example.com",
        hashed_password="x",
        role="admin",
        is_active=True,
    )
    db_session.add_all([admin_1, admin_2])
    await db_session.flush()
    metrics = {
        "frozen_holdout_passed": True,
        "time_forward_passed": True,
        "platform_stratified_passed": True,
        "community_disjoint_passed": True,
        "ece": 0.04,
        "false_positive_burden_passed": True,
        "shadow_run_passed": True,
    }
    db_session.add(
        AccountDetectionModelVersion(
            model_version="account-model-ready",
            dataset_version_id="dataset-ready-1",
            artifact_uri="artifact",
            artifact_hash="h",
            metrics_json=json.dumps(metrics),
            gates_json="{}",
            status="shadow",
            created_by=int(admin_1.id),
        )
    )
    await db_session.flush()

    with pytest.raises(AppException, match="approval records"):
        await activate_account_detection_model(
            db_session,
            model_version="account-model-ready",
            operator_id=int(admin_1.id),
        )

    approval_1 = await approve_account_detection_model(
        db_session,
        model_version="account-model-ready",
        approver_id=int(admin_1.id),
        approval_notes="first admin approval",
    )
    approval_2 = await approve_account_detection_model(
        db_session,
        model_version="account-model-ready",
        approver_id=int(admin_2.id),
        approval_notes="second admin approval",
    )
    assert approval_1 is not None and approval_1["approval_recorded"] is True
    assert approval_2 is not None and approval_2["ready_for_activation"] is True

    result = await activate_account_detection_model(
        db_session,
        model_version="account-model-ready",
        operator_id=int(admin_1.id),
    )

    assert result is not None
    assert result["status"] == "active"
    assert result["activation_decision"]["activation_allowed"] is True
