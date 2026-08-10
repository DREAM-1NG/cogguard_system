from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core import account_training_runtime
from app.models.account_labeling import (
    AccountCorpusVersion,
    AccountDetectionDatasetVersion,
    AccountModelTrainingDispatchOutbox,
    AccountModelTrainingRun,
)
from app.services.account_training_service import (
    cancel_account_training_run,
    create_account_training_run,
    interrupt_stale_account_training_runs,
    resume_account_training_run,
)
from app.utils.exceptions import AppException


@pytest.fixture(autouse=True)
def _stub_preflight_for_synthetic_training_paths(request, monkeypatch):
    """Lifecycle tests deliberately use paths that do not exist on disk."""

    if "real_training_preflight" in request.fixturenames:
        return

    monkeypatch.setattr(
        "app.services.account_training_service.preflight_account_training_artifact",
        lambda *, family, config: {"family": family},
        raising=False,
    )
    async def resolve_synthetic_detector(_session, config):
        return dict(config)

    monkeypatch.setattr(
        "app.services.account_training_service._resolve_governed_detector_config",
        resolve_synthetic_detector,
        raising=False,
    )


@pytest.fixture
def real_training_preflight():
    """Opt into real local preflight in a service test."""


def _write_local_mlm(tmp_path: Path) -> Path:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"model_type": "bert", "architectures": ["BertForMaskedLM"]}), encoding="utf-8"
    )
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
    (model_dir / "pytorch_model.bin").write_bytes(b"weights")
    return model_dir


def _write_detector_inputs(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()
    records = [
        {"account_id": "account-1", "text": "\u53ef\u8bad\u7ec3\u8d26\u53f7\u8bed\u6599", "training_target": "non_bot"},
        {"account_id": "account-2", "text": "\u53e6\u4e00\u6761\u8bad\u7ec3\u8bed\u6599", "training_target": "bot"},
    ]
    serialized = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    (dataset_root / "approved_account_labels.jsonl").write_text(
        "\n".join(serialized) + "\n", encoding="utf-8"
    )
    (dataset_root / "dataset_manifest.json").write_text(
        json.dumps(
            {
                "data_fingerprint": hashlib.sha256(("\n".join(serialized) + "\n").encode("utf-8")).hexdigest(),
                "record_count": 2,
                "class_counts": {"bot": 1, "non_bot": 1},
            }
        ),
        encoding="utf-8",
    )
    holdout_payload = {
        "schema": "cogguard.account-frozen-holdout.v1",
        "account_ids": ["account-1"],
        "record_fingerprints": {"account-1": "a" * 64},
    }
    holdout = {
        **holdout_payload,
        "manifest_sha256": hashlib.sha256(
            json.dumps(holdout_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    holdout_path = tmp_path / "holdout.json"
    holdout_path.write_text(json.dumps(holdout), encoding="utf-8")
    encoder_dir = tmp_path / "encoder"
    encoder_dir.mkdir()
    payload_path = encoder_dir / "payload"
    payload_path.write_bytes(b"encoder")
    return dataset_root, holdout_path, {
        "encoder_version": "encoder-v1",
        "encoder_artifact_hash": "a" * 64,
        "text_model_path": str(encoder_dir),
        "encoder_binding_payload_path": str(payload_path),
    }


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return []


class _Session:
    def __init__(self, corpus):
        self.corpus = corpus
        self.added = []

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity in {AccountCorpusVersion, AccountDetectionDatasetVersion}:
            return _Result(self.corpus)
        return _Result(None)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if getattr(value, "created_at", None) is None and value.__class__.__name__ == "AccountModelTrainingRun":
                from datetime import datetime

                value.created_at = datetime.now(timezone.utc).replace(tzinfo=None)

class _RunSession:
    def __init__(self, run, *, dispatch=None):
        self.run = run
        self.dispatch = dispatch
        self.added = []
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountModelTrainingDispatchOutbox:
            return _RunResult(self.dispatch)
        return _RunResult(self.run)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


class _RunResult(_Result):
    def all(self):
        return [self.value]


@pytest.mark.asyncio
async def test_detector_training_service_creates_queued_run_only_after_200_approved_labels():
    corpus = AccountDetectionDatasetVersion(
        dataset_version_id="corpus-1",
        data_fingerprint="a" * 64,
        source_label_count=200,
        artifact_uri="approved",
        manifest_json=json.dumps({"record_count": 200}),
        status="candidate",
        created_by=7,
    )
    session = _Session(corpus)
    result = await create_account_training_run(
        session,
        family="chinese_account_detector",
        corpus_version_id="corpus-1",
        input_fingerprint="a" * 64,
        config={"dataset_root": "approved"},
        manual=False,
        operator_id=7,
        dispatch=False,
    )
    assert result["status"] == "queued"
    assert result["decision"]["reason"] == "trigger_gates_passed"
    assert result["config"]["family"] == "chinese_account_detector"
    assert result["config"]["schema"] == "cogguard.account-training-config.v1"
    assert result["config"]["corpus_version_id"] == "corpus-1"
    assert result["max_attempts"] == 4


@pytest.mark.asyncio
async def test_create_preflight_failure_persists_no_run_or_outbox(monkeypatch):
    corpus = AccountCorpusVersion(
        corpus_version_id="preflight-failure",
        input_fingerprint="p" * 64,
        source_label_count=0,
        manifest_json=json.dumps({"eligible_chinese_token_count": 500_000}),
        status="candidate",
        created_by=7,
    )
    session = _Session(corpus)

    def reject(*, family, config):
        raise AppException(code=409, msg="local model is incomplete")

    monkeypatch.setattr("app.services.account_training_service.preflight_account_training_artifact", reject)
    with pytest.raises(AppException, match="local model is incomplete"):
        await create_account_training_run(
            session,
            family="chinese_social_encoder",
            corpus_version_id=corpus.corpus_version_id,
            input_fingerprint=corpus.input_fingerprint,
            config={"corpus_documents_path": "synthetic.jsonl"},
            manual=False,
            operator_id=7,
        )

    assert session.added == []


@pytest.mark.asyncio
async def test_resume_preflight_failure_keeps_interrupted_state_and_config(monkeypatch):
    config = {"schema": "cogguard.account-training-config.v1", "corpus_documents_path": "synthetic.jsonl"}
    run = AccountModelTrainingRun(
        run_id="resume-preflight-failure",
        family="chinese_social_encoder",
        status="interrupted",
        stage="heartbeat_expired",
        input_fingerprint="r" * 64,
        config_hash="s" * 64,
        config_json=json.dumps(config),
        attempt=1,
        max_attempts=4,
        created_by=7,
    )

    def reject(*, family, config):
        raise AppException(code=409, msg="corpus changed after dispatch")

    monkeypatch.setattr("app.services.account_training_service.preflight_account_training_artifact", reject)
    session = _RunSession(run)
    with pytest.raises(AppException, match="corpus changed after dispatch"):
        await resume_account_training_run(session, run_id=run.run_id, operator_id=9, dispatch=False)

    assert run.status == "interrupted"
    assert run.stage == "heartbeat_expired"
    assert run.attempt == 1
    assert run.max_attempts == 4
    assert json.loads(run.config_json) == config
    assert session.added == []


@pytest.mark.asyncio
async def test_create_encoder_persists_effective_model_and_device_from_settings(
    tmp_path, monkeypatch, real_training_preflight
):
    model_dir = _write_local_mlm(tmp_path)
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_text('{"text":"\u53ef\u8bad\u7ec3\u8bed\u6599"}\n', encoding="utf-8")
    historical_path = tmp_path / "historical.jsonl"
    historical_path.write_text('{"text":"\u5386\u53f2\u8bed\u6599"}\n', encoding="utf-8")
    monkeypatch.setattr(settings, "ACCOUNT_ACQUISITION_TEXT_MODEL_PATH", str(model_dir))
    monkeypatch.setattr(settings, "ACCOUNT_ACQUISITION_DEVICE", "cuda")
    corpus = AccountCorpusVersion(
        corpus_version_id="effective-dapt-config",
        input_fingerprint="d" * 64,
        source_label_count=0,
        manifest_json=json.dumps({"eligible_chinese_token_count": 500_000, "corpus_path": str(corpus_path)}),
        status="candidate",
        created_by=7,
    )

    result = await create_account_training_run(
        _Session(corpus),
        family="chinese_social_encoder",
        corpus_version_id=corpus.corpus_version_id,
        input_fingerprint=corpus.input_fingerprint,
        config={"historical_documents_path": str(historical_path)},
        manual=False,
        operator_id=7,
        dispatch=False,
    )

    assert result["config"]["model_name_or_path"] == str(model_dir)
    assert result["config"]["device"] == "cuda"
    assert result["config"]["corpus_documents_path"] == str(corpus_path.resolve())
    assert result["config"]["historical_documents_path"] == str(historical_path.resolve())


@pytest.mark.asyncio
async def test_create_detector_defaults_strict_and_persists_resolved_binding(
    tmp_path, monkeypatch, real_training_preflight
):
    from app.core import account_training_runtime

    dataset_root, holdout_path, binding = _write_detector_inputs(tmp_path)
    dataset_fingerprint = json.loads((dataset_root / "dataset_manifest.json").read_text(encoding="utf-8"))["data_fingerprint"]
    corpus = AccountDetectionDatasetVersion(
        dataset_version_id="resolved-detector-config",
        data_fingerprint=dataset_fingerprint,
        source_label_count=200,
        artifact_uri=str(dataset_root),
        manifest_json=json.dumps({"record_count": 200}),
        status="candidate",
        created_by=7,
    )
    monkeypatch.setattr(
        account_training_runtime,
        "load_verified_chinese_social_encoder_artifact",
        lambda *_args, **_kwargs: {"artifact_hash": "a" * 64, "encoder_payload": {"path": "payload"}},
    )

    async def resolve(_session, config):
        assert config["strict_protocol"] is True
        return {**config, **binding}

    monkeypatch.setattr("app.services.account_training_service._resolve_governed_detector_config", resolve)
    result = await create_account_training_run(
        _Session(corpus),
        family="chinese_account_detector",
        corpus_version_id=corpus.dataset_version_id,
        input_fingerprint=corpus.data_fingerprint,
        config={"dataset_root": str(tmp_path / "untrusted"), "frozen_holdout_manifest_path": str(holdout_path)},
        manual=False,
        operator_id=7,
        dispatch=False,
    )

    assert result["config"]["strict_protocol"] is True
    assert result["config"]["text_model_path"] == binding["text_model_path"]
    assert result["config"]["encoder_artifact_hash"] == "a" * 64
    assert result["config"]["dataset_root"] == str(dataset_root.resolve())
    assert "frozen_holdout_manifest_path" not in result["config"]
    assert "frozen_holdout_manifest_sha256" not in result["config"]


@pytest.mark.asyncio
async def test_resume_legacy_detector_resolves_for_preflight_without_mutating_config(
    tmp_path, monkeypatch, real_training_preflight
):
    from app.core import account_training_runtime

    dataset_root, holdout_path, binding = _write_detector_inputs(tmp_path)
    dataset_fingerprint = json.loads((dataset_root / "dataset_manifest.json").read_text(encoding="utf-8"))["data_fingerprint"]
    persisted = {
        "strict_protocol": True,
        "dataset_name": "approved_account_corpus",
        "dataset_root": str(dataset_root),
        "frozen_holdout_manifest_path": str(holdout_path),
        "encoder_version": "encoder-v1",
        "input_fingerprint": dataset_fingerprint,
    }
    run = AccountModelTrainingRun(
        run_id="legacy-resume-detector",
        family="chinese_account_detector",
        status="interrupted",
        stage="heartbeat_expired",
        input_fingerprint="l" * 64,
        config_hash="m" * 64,
        config_json=json.dumps(persisted),
        attempt=1,
        max_attempts=4,
        created_by=7,
    )
    monkeypatch.setattr(
        account_training_runtime,
        "load_verified_chinese_social_encoder_artifact",
        lambda *_args, **_kwargs: {"artifact_hash": "a" * 64, "encoder_payload": {"path": "payload"}},
    )

    async def resolve(_session, config):
        assert config == persisted
        return {**config, **binding}

    monkeypatch.setattr("app.services.account_training_service._resolve_governed_detector_config", resolve)
    resumed = await resume_account_training_run(_RunSession(run), run_id=run.run_id, operator_id=7, dispatch=False)

    assert resumed["status"] == "queued"
    assert json.loads(run.config_json) == persisted


@pytest.mark.asyncio
async def test_mysql_training_run_creation_returns_without_lazy_loading_server_defaults(db_session):
    corpus = AccountCorpusVersion(
        corpus_version_id="mysql-create-run-corpus",
        input_fingerprint="1" * 64,
        source_label_count=0,
        manifest_json=json.dumps({"eligible_chinese_token_count": 500_000}),
        status="candidate",
        created_by=7,
    )
    db_session.add(corpus)
    await db_session.flush()

    result = await create_account_training_run(
        db_session,
        family="chinese_social_encoder",
        corpus_version_id=corpus.corpus_version_id,
        input_fingerprint=corpus.input_fingerprint,
        config={"corpus_documents_path": "missing-smoke-corpus.jsonl"},
        manual=False,
        operator_id=7,
    )

    assert result["status"] == "queued"
    assert result["created_at"] is not None
    assert result["dispatch"]["status"] == "pending"


@pytest.mark.asyncio
async def test_default_training_dispatch_is_persisted_pending_without_publishing_from_the_service(monkeypatch):
    from app.tasks import account_training_tasks

    def published_before_commit(*_args, **_kwargs):
        raise AssertionError("the service must persist an outbox intent instead of publishing directly")

    monkeypatch.setattr(account_training_tasks, "enqueue_account_training_run", published_before_commit)
    corpus = AccountDetectionDatasetVersion(
        dataset_version_id="outbox-corpus",
        data_fingerprint="d" * 64,
        source_label_count=200,
        artifact_uri="approved",
        manifest_json=json.dumps({"record_count": 200}),
        status="candidate",
        created_by=7,
    )
    session = _Session(corpus)

    result = await create_account_training_run(
        session,
        family="chinese_account_detector",
        corpus_version_id="outbox-corpus",
        input_fingerprint="d" * 64,
        config={"dataset_root": "approved"},
        manual=False,
        operator_id=7,
    )

    dispatches = [value for value in session.added if isinstance(value, AccountModelTrainingDispatchOutbox)]
    assert len(dispatches) == 1
    assert result["dispatch"]["status"] == "pending"
    assert result["dispatch"]["task_id"] == dispatches[0].task_id
    assert dispatches[0].attempt == 1


@pytest.mark.asyncio
async def test_resume_creates_a_new_persisted_dispatch_for_the_new_attempt(monkeypatch):
    from app.tasks import account_training_tasks

    def published_before_commit(*_args, **_kwargs):
        raise AssertionError("the service must persist an outbox intent instead of publishing directly")

    monkeypatch.setattr(account_training_tasks, "enqueue_account_training_run", published_before_commit)
    run = AccountModelTrainingRun(
        run_id="run-resume-outbox",
        family="chinese_social_encoder",
        status="interrupted",
        stage="heartbeat_expired",
        input_fingerprint="f" * 64,
        config_hash="a" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=4,
        created_by=7,
    )
    session = _RunSession(run)

    resumed = await resume_account_training_run(session, run_id=run.run_id, operator_id=9)

    dispatches = [value for value in session.added if isinstance(value, AccountModelTrainingDispatchOutbox)]
    assert resumed["attempt"] == 2
    assert resumed["dispatch"]["status"] == "pending"
    assert len(dispatches) == 1
    assert dispatches[0].attempt == 2
    assert dispatches[0].task_id.endswith(":attempt:2")


@pytest.mark.asyncio
async def test_service_uses_deployment_training_policy(monkeypatch):
    monkeypatch.setattr(settings, "ACCOUNT_TRAINING_SUPERVISED_LABEL_THRESHOLD", 7)
    monkeypatch.setattr(settings, "ACCOUNT_TRAINING_MAX_RESUMES", 1)
    corpus = AccountDetectionDatasetVersion(
        dataset_version_id="configured-policy",
        data_fingerprint="c" * 64,
        source_label_count=7,
        artifact_uri="approved",
        manifest_json=json.dumps({"record_count": 7}),
        status="candidate",
        created_by=7,
    )

    result = await create_account_training_run(
        _Session(corpus),
        family="chinese_account_detector",
        corpus_version_id="configured-policy",
        input_fingerprint="c" * 64,
        config={"dataset_root": "approved"},
        manual=False,
        operator_id=7,
        dispatch=False,
    )

    assert result["decision"]["threshold"] == 7
    assert result["max_attempts"] == 2


@pytest.mark.asyncio
async def test_encoder_training_service_rejects_unready_corpus_before_dispatch():
    corpus = AccountCorpusVersion(
        corpus_version_id="corpus-2",
        input_fingerprint="b" * 64,
        source_label_count=1,
        manifest_json=json.dumps({"eligible_chinese_token_count": 500_000}),
        status="rejected",
        created_by=7,
    )
    with pytest.raises(AppException, match="training cannot be dispatched"):
        await create_account_training_run(
            _Session(corpus),
            family="chinese_social_encoder",
            corpus_version_id="corpus-2",
            input_fingerprint="b" * 64,
            config={"corpus_documents_path": "documents.jsonl"},
            manual=False,
            operator_id=7,
            dispatch=False,
        )


@pytest.mark.asyncio
async def test_stale_active_run_becomes_interrupted_with_a_durable_event(monkeypatch):
    monkeypatch.setattr(settings, "ACCOUNT_TRAINING_HEARTBEAT_TIMEOUT_SECONDS", 90)
    run = AccountModelTrainingRun(
        run_id="run-stale",
        family="chinese_social_encoder",
        status="running",
        stage="training",
        input_fingerprint="c" * 64,
        config_hash="d" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=7,
        heartbeat_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=91),
    )
    session = _RunSession(run)
    interrupted = await interrupt_stale_account_training_runs(
        session,
        now=datetime.now(timezone.utc),
    )
    assert [item["run_id"] for item in interrupted] == ["run-stale"]
    assert run.status == "interrupted"
    assert run.stage == "heartbeat_expired"
    assert session.added[-1].event_type == "interrupted"
    assert session.statements[-1]._for_update_arg is not None


@pytest.mark.asyncio
async def test_resume_preserves_config_and_stops_after_configured_resume_limit():
    run = AccountModelTrainingRun(
        run_id="run-resume",
        family="chinese_social_encoder",
        status="interrupted",
        stage="heartbeat_expired",
        input_fingerprint="e" * 64,
        config_hash="f" * 64,
        config_json=json.dumps({"schema": "cogguard.account-training-config.v1", "epochs": 1}),
        attempt=3,
        max_attempts=4,
        created_by=7,
    )
    session = _RunSession(run)
    resumed = await resume_account_training_run(
        session,
        run_id="run-resume",
        operator_id=9,
        dispatch=False,
    )
    assert resumed["status"] == "queued"
    assert resumed["attempt"] == 4
    assert resumed["config"] == {"schema": "cogguard.account-training-config.v1", "epochs": 1}
    assert session.statements[0]._for_update_arg is not None

    run.status = "interrupted"
    with pytest.raises(AppException, match="retry limit"):
        await resume_account_training_run(session, run_id="run-resume", operator_id=9, dispatch=False)


@pytest.mark.asyncio
async def test_cancelling_a_queued_run_records_a_terminal_cancellation_event():
    run = AccountModelTrainingRun(
        run_id="run-cancel",
        family="chinese_social_encoder",
        status="queued",
        stage="queued",
        input_fingerprint="f" * 64,
        config_hash="a" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=7,
    )
    session = _RunSession(run)

    cancelled = await cancel_account_training_run(session, run_id="run-cancel", operator_id=9)

    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
    assert [event.event_type for event in session.added] == ["cancel_requested", "cancelled"]
    assert session.statements[0]._for_update_arg is not None


@pytest.mark.asyncio
async def test_cancelling_pending_dispatch_supersedes_it_before_broker_publication():
    run = AccountModelTrainingRun(
        run_id="run-cancel-pending",
        family="chinese_social_encoder",
        status="queued",
        stage="queued",
        input_fingerprint="f" * 64,
        config_hash="a" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=7,
    )
    dispatch = AccountModelTrainingDispatchOutbox(
        dispatch_id="dispatch-cancel-pending",
        run_id=run.run_id,
        attempt=1,
        task_id="task-cancel-pending",
        status="pending",
        publish_attempts=0,
        available_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session = _RunSession(run, dispatch=dispatch)

    cancelled = await cancel_account_training_run(session, run_id=run.run_id, operator_id=9)

    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
    assert dispatch.status == "superseded"
    assert dispatch.last_error == "superseded by cancellation before broker publication"
    assert [event.event_type for event in session.added] == [
        "cancel_requested",
        "dispatch_superseded",
        "cancelled",
    ]
    assert all(statement._for_update_arg is not None for statement in session.statements[:2])


@pytest.mark.asyncio
async def test_cancelling_claimed_dispatch_returns_conflict_without_changing_run_or_dispatch():
    run = AccountModelTrainingRun(
        run_id="run-cancel-publishing",
        family="chinese_social_encoder",
        status="queued",
        stage="queued",
        input_fingerprint="f" * 64,
        config_hash="a" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=7,
    )
    dispatch = AccountModelTrainingDispatchOutbox(
        dispatch_id="dispatch-cancel-publishing",
        run_id=run.run_id,
        attempt=1,
        task_id="task-cancel-publishing",
        status="publishing",
        claim_token="publisher-claim",
        publish_attempts=1,
        available_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    with pytest.raises(AppException, match="currently publishing") as error:
        await cancel_account_training_run(
            _RunSession(run, dispatch=dispatch),
            run_id=run.run_id,
            operator_id=9,
        )

    assert error.value.code == 409
    assert run.status == "queued"
    assert run.cancel_requested_at is None
    assert dispatch.status == "publishing"
    assert dispatch.claim_token == "publisher-claim"


@pytest.mark.asyncio
async def test_cancelling_after_publication_leaves_message_to_worker_state_gate():
    run = AccountModelTrainingRun(
        run_id="run-cancel-published",
        family="chinese_social_encoder",
        status="queued",
        stage="queued",
        input_fingerprint="f" * 64,
        config_hash="a" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=7,
    )
    dispatch = AccountModelTrainingDispatchOutbox(
        dispatch_id="dispatch-cancel-published",
        run_id=run.run_id,
        attempt=1,
        task_id="task-cancel-published",
        status="published",
        publish_attempts=1,
        available_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    cancelled = await cancel_account_training_run(
        _RunSession(run, dispatch=dispatch),
        run_id=run.run_id,
        operator_id=9,
    )

    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
    assert dispatch.status == "published"


@pytest.mark.asyncio
async def test_resume_uses_configured_limit_and_clamps_a_tampered_persisted_limit(monkeypatch):
    monkeypatch.setattr(settings, "ACCOUNT_TRAINING_MAX_RESUMES", 3)
    run = AccountModelTrainingRun(
        run_id="run-configured-cap",
        family="chinese_social_encoder",
        status="interrupted",
        stage="heartbeat_expired",
        input_fingerprint="e" * 64,
        config_hash="f" * 64,
        config_json="{}",
        attempt=4,
        max_attempts=999,
        created_by=7,
    )

    with pytest.raises(AppException, match="retry limit"):
        await resume_account_training_run(_RunSession(run), run_id=run.run_id, operator_id=9, dispatch=False)

    assert run.max_attempts == 999


@pytest.mark.asyncio
async def test_resume_rejects_a_live_runtime_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    run = AccountModelTrainingRun(
        run_id="run-live-owner",
        family="chinese_social_encoder",
        status="interrupted",
        stage="heartbeat_expired",
        input_fingerprint="e" * 64,
        config_hash="f" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=4,
        created_by=7,
    )
    ownership = account_training_runtime.acquire_account_training_ownership(run.run_id, run.attempt)
    try:
        with pytest.raises(AppException, match="still owned by a live runtime"):
            await resume_account_training_run(_RunSession(run), run_id=run.run_id, operator_id=9, dispatch=False)
    finally:
        ownership.release()


def _mysql_training_run(*, run_id: str, status: str, heartbeat_at=None) -> AccountModelTrainingRun:
    return AccountModelTrainingRun(
        run_id=run_id,
        family="chinese_social_encoder",
        status=status,
        stage="training" if status == "running" else "heartbeat_expired",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=4,
        created_by=7,
        heartbeat_at=heartbeat_at,
    )


async def _locked_mysql_run(session, run_id: str) -> AccountModelTrainingRun:
    return (
        await session.execute(
            select(AccountModelTrainingRun)
            .where(AccountModelTrainingRun.run_id == run_id)
            .with_for_update()
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_mysql_lifecycle_operations_recheck_newer_state_under_row_lock(db_session):
    """Exercise cancel, resume, and stale recovery against concurrent MySQL sessions."""

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add_all(
        [
            _mysql_training_run(run_id="mysql-cancel", status="queued"),
            _mysql_training_run(run_id="mysql-resume", status="interrupted"),
            _mysql_training_run(
                run_id="mysql-heartbeat",
                status="running",
                heartbeat_at=now - timedelta(minutes=10),
            ),
        ]
    )
    await db_session.commit()

    engine = create_async_engine(settings.mysql_url_test, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as holder, sessions() as contender:
            run = await _locked_mysql_run(holder, "mysql-cancel")
            cancellation = asyncio.create_task(
                cancel_account_training_run(contender, run_id="mysql-cancel", operator_id=9)
            )
            await asyncio.sleep(0.05)
            assert not cancellation.done()
            run.status = "completed"
            run.stage = "completed"
            await holder.commit()
            with pytest.raises(AppException, match="Terminal"):
                await cancellation

        async with sessions() as holder, sessions() as contender:
            run = await _locked_mysql_run(holder, "mysql-resume")
            resumption = asyncio.create_task(
                resume_account_training_run(contender, run_id="mysql-resume", operator_id=9, dispatch=False)
            )
            await asyncio.sleep(0.05)
            assert not resumption.done()
            run.status = "cancelled"
            run.stage = "cancelled"
            await holder.commit()
            with pytest.raises(AppException, match="Only interrupted"):
                await resumption

        async with sessions() as holder, sessions() as contender:
            run = await _locked_mysql_run(holder, "mysql-heartbeat")
            reconciliation = asyncio.create_task(
                interrupt_stale_account_training_runs(
                    contender,
                    now=datetime.now(timezone.utc),
                    timeout_seconds=60,
                )
            )
            await asyncio.sleep(0.05)
            assert not reconciliation.done()
            run.heartbeat_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await holder.commit()
            assert await reconciliation == []

        async with sessions() as observer:
            heartbeat = (
                await observer.execute(
                    select(AccountModelTrainingRun).where(AccountModelTrainingRun.run_id == "mysql-heartbeat")
                )
            ).scalar_one()
            assert heartbeat.status == "running"
    finally:
        await engine.dispose()
