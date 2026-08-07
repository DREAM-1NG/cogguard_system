"""Focused regression coverage for the system-owned account evaluation job."""

from __future__ import annotations

import json
import asyncio
from types import SimpleNamespace
from unittest.mock import ANY

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.api.v1 import accounts as accounts_api
from app.core.security import get_current_user
from app.models.account_labeling import (
    AccountDetectionModelVersion,
    AccountModelEvaluationJob,
    AccountTrainingExportMembership,
)
from app.config import settings
from app.main import app
from app.services.account_dataset_service import record_account_training_export_memberships
from app.services import account_model_evaluation_service as evaluation_service
from app.services.account_model_evaluation_service import (
    compute_holdout_fingerprint,
    create_account_model_evaluation_job,
    prepare_frozen_holdout_cases,
)
from app.utils.exceptions import AppException


class _Result:
    def __init__(self, *, scalar=None, rows=()):
        self.scalar = scalar
        self.rows = list(rows)

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _CreationSession:
    def __init__(self, candidate, holdout_rows):
        self.candidate = candidate
        self.holdout_rows = holdout_rows
        self.jobs = []

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountDetectionModelVersion:
            return _Result(scalar=self.candidate)
        if entity is AccountModelEvaluationJob:
            parameters = {str(value) for value in statement.compile().params.values()}
            jobs = [
                row
                for row in self.jobs
                if {
                    row.model_version,
                    row.artifact_hash,
                    row.corpus_version_id,
                    row.config_fingerprint,
                }.issubset(parameters)
            ]
            return _Result(scalar=jobs[0] if jobs else None, rows=jobs)
        return _Result(rows=self.holdout_rows)

    def add(self, value):
        if isinstance(value, AccountModelEvaluationJob):
            self.jobs.append(value)

    async def flush(self):
        return None


class _WorkerSession:
    def __init__(self, job, candidate, holdout_rows):
        self.job = job
        self.candidate = candidate
        self.holdout_rows = holdout_rows

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountModelEvaluationJob:
            return _Result(scalar=self.job)
        if entity is AccountDetectionModelVersion:
            return _Result(scalar=self.candidate)
        return _Result(rows=self.holdout_rows)

    async def flush(self):
        return None


class _ExportMembershipSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


def _holdout_row(
    *,
    membership_id: str = "member-1",
    label_id: str = "label-1",
    target: str = "bot",
    case_fingerprint: str = "a" * 64,
    label_fingerprint: str | None = None,
    label_status: str = "approved",
    current: bool = True,
):
    return (
        SimpleNamespace(
            membership_id=membership_id,
            corpus_version_id="corpus-1",
            case_id="case-1",
            label_id=label_id,
        ),
        SimpleNamespace(
            label_id=label_id,
            case_id="case-1",
            training_target=target,
            label_status=label_status,
            case_fingerprint=label_fingerprint or case_fingerprint,
            current=current,
        ),
        SimpleNamespace(
            case_id="case-1",
            account_id="account-1",
            platform="weibo",
            event_id="event-1",
            case_fingerprint=case_fingerprint,
            payload_json=json.dumps({"text": "persisted account evidence"}),
        ),
    )


def test_frozen_holdout_fingerprint_is_order_independent_and_rejects_stale_or_superseded_labels():
    first = _holdout_row(membership_id="member-b", label_id="label-b", target="non_bot")
    second = _holdout_row(membership_id="member-a", label_id="label-a")

    prepared = prepare_frozen_holdout_cases([first, second], corpus_version_id="corpus-1")

    assert [row.membership_id for row in prepared] == ["member-a", "member-b"]
    assert compute_holdout_fingerprint(prepared) == compute_holdout_fingerprint(list(reversed(prepared)))

    with pytest.raises(AppException, match="stale"):
        prepare_frozen_holdout_cases(
            [_holdout_row(label_fingerprint="b" * 64)],
            corpus_version_id="corpus-1",
        )
    with pytest.raises(AppException, match="superseded"):
        prepare_frozen_holdout_cases(
            [_holdout_row(current=False)],
            corpus_version_id="corpus-1",
        )


def test_training_export_membership_is_persisted_and_rejects_export_before_freeze():
    membership, label, case = _holdout_row()
    session = _ExportMembershipSession()

    async def scenario():
        await record_account_training_export_memberships(
            session,
            dataset_version_id="dataset-1",
            dataset_fingerprint="d" * 64,
            rows=[(label, case, {"text": "persisted account evidence"})],
        )

    asyncio.run(scenario())

    persisted = session.added[0]
    assert persisted.dataset_version_id == "dataset-1"
    assert persisted.case_id == case.case_id
    assert persisted.label_id == label.label_id
    assert persisted.case_fingerprint == case.case_fingerprint
    assert len(persisted.export_fingerprint) == 64
    with pytest.raises(AppException, match="training export"):
        prepare_frozen_holdout_cases(
            [(membership, label, case, True)],
            corpus_version_id="corpus-1",
        )


def test_job_creation_is_idempotent_for_the_same_immutable_candidate_and_config():
    candidate = AccountDetectionModelVersion(
        model_version="candidate-1",
        dataset_version_id="dataset-1",
        artifact_uri="artifacts/candidate-1",
        artifact_hash="a" * 64,
        metrics_json="{}",
        gates_json="{}",
        status="shadow",
        created_by=7,
    )
    session = _CreationSession(candidate, [_holdout_row()])

    async def scenario():
        first = await create_account_model_evaluation_job(
            session,
            model_version="candidate-1",
            corpus_version_id="corpus-1",
            evaluator_config={"evaluation_profile": "standard"},
            operator_id=7,
        )
        repeated = await create_account_model_evaluation_job(
            session,
            model_version="candidate-1",
            corpus_version_id="corpus-1",
            evaluator_config={"evaluation_profile": "standard"},
            operator_id=9,
        )
        candidate.artifact_hash = "b" * 64
        changed_candidate = await create_account_model_evaluation_job(
            session,
            model_version="candidate-1",
            corpus_version_id="corpus-1",
            evaluator_config={"evaluation_profile": "standard"},
            operator_id=7,
        )
        return first, repeated, changed_candidate

    first, repeated, changed_candidate = asyncio.run(scenario())

    assert first["status"] == "queued"
    assert first["job_id"] == repeated["job_id"]
    assert first["holdout_fingerprint"] == repeated["holdout_fingerprint"]
    assert changed_candidate["job_id"] != first["job_id"]
    assert len(session.jobs) == 2


def test_worker_uses_the_exact_candidate_bundle_and_signs_server_owned_evidence(monkeypatch):
    candidate = AccountDetectionModelVersion(
        model_version="candidate-worker-1",
        dataset_version_id="dataset-worker-1",
        artifact_uri="artifacts/candidate-worker-1",
        artifact_hash="c" * 64,
        metrics_json=json.dumps({"dataset_fingerprint": "d" * 64}),
        gates_json="{}",
        status="shadow",
        created_by=7,
    )
    holdout_rows = [_holdout_row()]
    prepared = prepare_frozen_holdout_cases(holdout_rows, corpus_version_id="corpus-1")
    job = AccountModelEvaluationJob(
        job_id="evaluation-job-1",
        model_version=candidate.model_version,
        artifact_hash=candidate.artifact_hash,
        corpus_version_id="corpus-1",
        holdout_fingerprint=compute_holdout_fingerprint(prepared),
        config_fingerprint="e" * 64,
        evaluator_config_json="{}",
        status="queued",
        task_id="task-1",
        operator_id=7,
    )
    session = _WorkerSession(job, candidate, holdout_rows)
    captured = {}

    class _Inference:
        def predict(self, posts):
            captured["posts"] = posts
            return {
                "accounts": [
                    {
                        "account_id": "account-1",
                        "calibrated_probability": 0.8,
                        "final_prediction": "bot",
                        "calibrated": True,
                    }
                ]
            }

    def fake_inference(source, *, allow_legacy_fallback):
        captured["source"] = source
        captured["allow_legacy_fallback"] = allow_legacy_fallback
        return _Inference()

    async def fake_writeback(_session, **kwargs):
        captured["writeback"] = kwargs
        return {"metrics": {"shadow_evaluation": {"evaluation_run_id": kwargs["evaluation_run_id"]}}}

    monkeypatch.setattr(settings, "ACCOUNT_MODEL_EVALUATION_HMAC_SECRET", "s" * 32, raising=False)
    monkeypatch.setattr(evaluation_service, "load_deployable_bundle_manifest", lambda _path: {"source_schema": "cogguard.botrhg.account.v3"})
    monkeypatch.setattr(evaluation_service, "get_trained_botrhg_inference", fake_inference)
    monkeypatch.setattr(evaluation_service, "write_account_model_evaluation", fake_writeback)

    async def scenario():
        prepared_job = await evaluation_service.prepare_account_model_evaluation_job(session, job.job_id)
        assert not isinstance(prepared_job, dict)
        audits = await evaluation_service.run_prepared_account_model_evaluation(prepared_job)
        return await evaluation_service.finalize_account_model_evaluation_job(session, prepared_job, audits)

    result = asyncio.run(scenario())

    assert result["status"] == "completed"
    assert job.completed_evaluation_run_id == result["completed_evaluation_run_id"]
    assert captured["source"].model_version == candidate.model_version
    assert captured["source"].artifact_hash == candidate.artifact_hash
    assert captured["allow_legacy_fallback"] is False
    assert captured["posts"][0]["author_id"] == "account-1"
    assert "target" not in captured["posts"][0]
    assert captured["writeback"]["evaluation_manifest"]["signature_sha256"]
    assert captured["writeback"]["prediction_audits"][0]["target"] == 1


def test_prepare_fails_closed_when_the_persisted_holdout_fingerprint_changes(monkeypatch):
    candidate = AccountDetectionModelVersion(
        model_version="candidate-worker-2",
        dataset_version_id="dataset-worker-2",
        artifact_uri="artifacts/candidate-worker-2",
        artifact_hash="f" * 64,
        metrics_json="{}",
        gates_json="{}",
        status="shadow",
        created_by=7,
    )
    original_rows = [_holdout_row()]
    original_fingerprint = compute_holdout_fingerprint(
        prepare_frozen_holdout_cases(original_rows, corpus_version_id="corpus-1")
    )
    changed_rows = [_holdout_row()]
    changed_rows[0][2].payload_json = json.dumps({"text": "changed persisted account evidence"})
    job = AccountModelEvaluationJob(
        job_id="evaluation-job-2",
        model_version=candidate.model_version,
        artifact_hash=candidate.artifact_hash,
        corpus_version_id="corpus-1",
        holdout_fingerprint=original_fingerprint,
        config_fingerprint="e" * 64,
        evaluator_config_json="{}",
        status="queued",
        task_id="task-2",
        operator_id=7,
    )
    session = _WorkerSession(job, candidate, changed_rows)
    called = False

    async def unexpected_writeback(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(evaluation_service, "write_account_model_evaluation", unexpected_writeback)

    with pytest.raises(AppException, match="fingerprint"):
        asyncio.run(evaluation_service.prepare_account_model_evaluation_job(session, job.job_id))

    assert job.status == "queued"
    assert job.completed_evaluation_run_id is None
    assert called is False


def test_evaluation_job_create_and_query_api_are_admin_only_and_accept_no_client_evidence(monkeypatch):
    calls = []

    async def override_db():
        yield object()

    async def fake_create(_session, **kwargs):
        calls.append(kwargs)
        return {
            "job_id": "job-api-1",
            "model_version": kwargs["model_version"],
            "artifact_hash": "a" * 64,
            "corpus_version_id": kwargs["corpus_version_id"],
            "holdout_fingerprint": "b" * 64,
            "config_fingerprint": "c" * 64,
            "status": "queued",
            "task_id": "task-api-1",
            "completed_evaluation_run_id": None,
        }

    async def fake_get(_session, job_id):
        return {"job_id": job_id, "status": "completed", "completed_evaluation_run_id": "evaluation-run-1"}

    def fake_enqueue(job_id, *, task_id):
        calls.append({"enqueued": (job_id, task_id)})

    app.dependency_overrides[accounts_api.get_db] = override_db
    monkeypatch.setattr(accounts_api.account_model_evaluation_service, "create_account_model_evaluation_job", fake_create)
    monkeypatch.setattr(accounts_api.account_model_evaluation_service, "get_account_model_evaluation_job", fake_get)
    monkeypatch.setattr(accounts_api, "enqueue_account_model_evaluation_job", fake_enqueue)

    async def request_as(role, method, path, payload=None):
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role=role, is_active=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=payload)

    try:
        analyst = asyncio.run(
            request_as(
                "analyst",
                "POST",
                "/api/v1/accounts/models/model-api-1/evaluation-jobs",
                {"corpus_version_id": "corpus-api-1", "evaluator_config": {"evaluation_profile": "standard"}},
            )
        )
        admin = asyncio.run(
            request_as(
                "admin",
                "POST",
                "/api/v1/accounts/models/model-api-1/evaluation-jobs",
                {"corpus_version_id": "corpus-api-1", "evaluator_config": {"evaluation_profile": "standard"}},
            )
        )
        query = asyncio.run(request_as("admin", "GET", "/api/v1/accounts/evaluation-jobs/job-api-1"))
        client_evidence = asyncio.run(
            request_as(
                "admin",
                "POST",
                "/api/v1/accounts/models/model-api-1/evaluation-jobs",
                {
                    "corpus_version_id": "corpus-api-1",
                    "prediction_audits": [{"probability": 1.0}],
                },
            )
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(accounts_api.get_db, None)

    assert analyst.status_code == 403
    assert admin.status_code == 200
    assert query.status_code == 200
    assert client_evidence.status_code == 422
    assert calls[0]["operator_id"] == 7
    assert calls[1] == {"enqueued": ("job-api-1", "task-api-1")}


def test_account_evaluation_task_uses_the_dedicated_queue_and_late_acknowledgement(monkeypatch):
    from app.celery_app import celery_app
    from app.tasks.account_evaluation_tasks import enqueue_account_model_evaluation_job, execute_account_model_evaluation_job

    captured = {}

    def fake_apply_async(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(execute_account_model_evaluation_job, "apply_async", fake_apply_async)
    enqueue_account_model_evaluation_job("job-queue-1", task_id="task-queue-1")

    assert celery_app.conf.task_routes["account_evaluation.*"]["queue"] == "account_evaluation"
    assert captured == {
        "args": ["job-queue-1"],
        "queue": "account_evaluation",
        "task_id": "task-queue-1",
        "retry": False,
    }
    assert execute_account_model_evaluation_job.acks_late is True


def test_manual_writeback_is_exposed_only_as_an_explicit_compatibility_path():
    app.openapi_schema = None
    paths = app.openapi()["paths"]

    assert "/api/v1/accounts/models/{model_version}/evaluation-writeback-compatibility" in paths
    assert "/api/v1/accounts/models/{model_version}/evaluation-writeback" not in paths


def test_evaluation_job_creation_locks_candidate_then_job_then_holdout_state():
    candidate = AccountDetectionModelVersion(
        model_version="candidate-lock-order",
        dataset_version_id="dataset-lock-order",
        artifact_uri="artifacts/candidate-lock-order",
        artifact_hash="1" * 64,
        metrics_json="{}",
        gates_json="{}",
        status="shadow",
        created_by=7,
    )

    class _LockOrderSession(_CreationSession):
        def __init__(self):
            super().__init__(candidate, [_holdout_row()])
            self.lock_order = []

        async def execute(self, statement):
            entity = statement.column_descriptions[0].get("entity")
            if getattr(statement, "_for_update_arg", None) is not None:
                if entity is AccountDetectionModelVersion:
                    self.lock_order.append("candidate")
                elif entity is AccountModelEvaluationJob:
                    self.lock_order.append("job")
                else:
                    self.lock_order.append("holdout")
            return await super().execute(statement)

    session = _LockOrderSession()

    asyncio.run(
        create_account_model_evaluation_job(
            session,
            model_version=candidate.model_version,
            corpus_version_id="corpus-1",
            evaluator_config={},
            operator_id=7,
        )
    )

    assert session.lock_order[:3] == ["candidate", "job", "holdout"]


def test_prepare_and_finalize_recheck_after_inference_without_writing_evidence(monkeypatch):
    candidate = AccountDetectionModelVersion(
        model_version="candidate-phased",
        dataset_version_id="dataset-phased",
        artifact_uri="artifacts/candidate-phased",
        artifact_hash="2" * 64,
        metrics_json="{}",
        gates_json="{}",
        status="shadow",
        created_by=7,
    )
    original_rows = [_holdout_row()]
    job = AccountModelEvaluationJob(
        job_id="evaluation-job-phased",
        model_version=candidate.model_version,
        artifact_hash=candidate.artifact_hash,
        corpus_version_id="corpus-1",
        holdout_fingerprint=compute_holdout_fingerprint(
            prepare_frozen_holdout_cases(original_rows, corpus_version_id="corpus-1")
        ),
        config_fingerprint="e" * 64,
        evaluator_config_json="{}",
        status="queued",
        task_id="task-phased",
        operator_id=7,
    )
    changed_rows = [_holdout_row()]
    changed_rows[0][2].payload_json = json.dumps({"text": "changed after inference started"})
    prepare_session = _WorkerSession(job, candidate, original_rows)
    finalize_session = _WorkerSession(job, candidate, changed_rows)
    captured = {"writeback": False}

    class _Inference:
        def predict(self, _posts):
            return {
                "accounts": [
                    {
                        "account_id": "account-1",
                        "calibrated_probability": 0.8,
                        "final_prediction": "bot",
                        "calibrated": True,
                    }
                ]
            }

    async def no_op_lock(_session, *, corpus_version_id):
        assert corpus_version_id == "corpus-1"

    async def unexpected_writeback(*_args, **_kwargs):
        captured["writeback"] = True

    monkeypatch.setattr(evaluation_service, "_lock_frozen_holdout_state", no_op_lock)
    monkeypatch.setattr(
        evaluation_service,
        "load_deployable_bundle_manifest",
        lambda _path: {"source_schema": "cogguard.botrhg.account.v3"},
    )
    monkeypatch.setattr(evaluation_service, "get_trained_botrhg_inference", lambda *_args, **_kwargs: _Inference())
    monkeypatch.setattr(evaluation_service, "write_account_model_evaluation", unexpected_writeback)

    async def scenario():
        prepared = await evaluation_service.prepare_account_model_evaluation_job(prepare_session, job.job_id)
        audits = await evaluation_service.run_prepared_account_model_evaluation(prepared)
        with pytest.raises(AppException, match="fingerprint"):
            await evaluation_service.finalize_account_model_evaluation_job(finalize_session, prepared, audits)

    asyncio.run(scenario())

    assert job.status == "running"
    assert job.completed_evaluation_run_id is None
    assert captured["writeback"] is False


def test_evaluation_task_retries_operational_errors_without_terminal_failure(monkeypatch):
    from app.tasks import account_evaluation_tasks

    async def failing_execution(_job_id):
        raise OperationalError("SELECT 1", {}, RuntimeError("deadlock"))

    def run(coroutine):
        return asyncio.run(coroutine)

    retry_calls = []

    def retry(**kwargs):
        retry_calls.append(kwargs)
        return "retrying"

    monkeypatch.setattr(account_evaluation_tasks, "_execute_account_model_evaluation_job", failing_execution)
    monkeypatch.setattr(account_evaluation_tasks, "run_async", run)
    monkeypatch.setattr(account_evaluation_tasks.execute_account_model_evaluation_job, "retry", retry)
    monkeypatch.setattr(account_evaluation_tasks, "_record_failed_job_transaction", pytest.fail)

    result = account_evaluation_tasks.execute_account_model_evaluation_job.run("job-transient")

    assert result == "retrying"
    assert retry_calls == [{"exc": ANY, "countdown": 1}]


def test_evaluation_task_commits_prepare_before_runtime_and_uses_a_new_finalize_session(monkeypatch):
    from app.tasks import account_evaluation_tasks

    class _ManagedSession:
        def __init__(self, name):
            self.name = name
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def commit(self):
            self.committed = True

    prepare_session = _ManagedSession("prepare")
    finalize_session = _ManagedSession("finalize")
    sessions = iter((prepare_session, finalize_session))
    prepared = SimpleNamespace(job_id="job-phased")
    calls = []

    async def fake_prepare(session, job_id):
        calls.append(("prepare", session.name, job_id))
        return prepared

    async def fake_run(value):
        calls.append(("runtime", value.job_id))
        assert prepare_session.committed is True
        return [{"account_id": "account-1"}]

    async def fake_finalize(session, value, audits):
        calls.append(("finalize", session.name, value.job_id, audits))
        return {"job_id": value.job_id, "status": "completed"}

    monkeypatch.setattr(account_evaluation_tasks, "async_session_factory", lambda: next(sessions))
    monkeypatch.setattr(account_evaluation_tasks, "prepare_account_model_evaluation_job", fake_prepare)
    monkeypatch.setattr(account_evaluation_tasks, "run_prepared_account_model_evaluation", fake_run)
    monkeypatch.setattr(account_evaluation_tasks, "finalize_account_model_evaluation_job", fake_finalize)

    result = asyncio.run(account_evaluation_tasks._execute_account_model_evaluation_job("job-phased"))

    assert result == {"job_id": "job-phased", "status": "completed"}
    assert finalize_session.committed is True
    assert calls == [
        ("prepare", "prepare", "job-phased"),
        ("runtime", "job-phased"),
        ("finalize", "finalize", "job-phased", [{"account_id": "account-1"}]),
    ]


def test_evaluation_task_marks_deterministic_runtime_failure_without_evidence(monkeypatch):
    from app.tasks import account_evaluation_tasks

    class _ManagedSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def commit(self):
            return None

    recorded = []

    async def broken_prepare(_session, _job_id):
        raise AppException(code=409, msg="persisted holdout is invalid")

    async def record_failure(job_id, error):
        recorded.append((job_id, type(error).__name__, str(error)))

    monkeypatch.setattr(account_evaluation_tasks, "async_session_factory", _ManagedSession)
    monkeypatch.setattr(account_evaluation_tasks, "prepare_account_model_evaluation_job", broken_prepare)
    monkeypatch.setattr(account_evaluation_tasks, "_record_failed_job_transaction", record_failure)

    with pytest.raises(AppException, match="holdout"):
        asyncio.run(account_evaluation_tasks._execute_account_model_evaluation_job("job-deterministic"))

    assert recorded == [("job-deterministic", "AppException", "persisted holdout is invalid")]


def test_legacy_hidden_evaluation_writeback_route_is_not_registered():
    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/accounts/models/model-1/evaluation-writeback", json={})

    assert asyncio.run(request()).status_code == 404
