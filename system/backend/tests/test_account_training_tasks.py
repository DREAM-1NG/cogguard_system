from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from contextlib import AbstractAsyncContextManager

import pytest

from app.models.account_labeling import AccountModelTrainingRun
from app.tasks import account_training_tasks
from app.tasks.async_runtime import close_async_runtime, run_async
from app.utils.exceptions import AppException


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    def __init__(self, run):
        self.run = run
        self.added = []
        self.commits = 0
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Result(self.run)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _value):
        return None


class _SessionContext(AbstractAsyncContextManager):
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_periodic_model_monitoring_is_idle_without_an_active_pointer(monkeypatch):
    session = _Session(None)

    async def no_pointer(*_args, **_kwargs):
        raise AppException(code=409, msg="Account monitoring requires an active model pointer.")

    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))
    monkeypatch.setattr(account_training_tasks, "create_account_monitor_snapshot", no_pointer, raising=False)

    result = await account_training_tasks._monitor_active_account_model(window_seconds=300)

    assert result == {"status": "unavailable", "reason": "Account monitoring requires an active model pointer."}
    assert session.commits == 0


def test_periodic_monitoring_invalidates_the_runtime_cache_only_after_an_automatic_rollback_commit(monkeypatch):
    session = _Session(None)
    events = []

    async def create_snapshot(*_args, **_kwargs):
        events.append("snapshot")
        return {"snapshot_id": "snapshot-rollback"}

    async def rollback(_session, *, snapshot_id):
        assert snapshot_id == "snapshot-rollback"
        assert session.commits == 0
        events.append("rollback")
        return {"status": "rolled_back", "snapshot_id": snapshot_id}

    def invalidate_cache():
        assert session.commits == 1
        events.append("invalidate")

    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))
    monkeypatch.setattr(account_training_tasks, "create_account_monitor_snapshot", create_snapshot, raising=False)
    monkeypatch.setattr(
        account_training_tasks,
        "attempt_automatic_account_model_rollback",
        rollback,
        raising=False,
    )
    monkeypatch.setattr(
        account_training_tasks,
        "invalidate_trained_botrhg_runtime_cache",
        invalidate_cache,
        raising=False,
    )

    result = asyncio.run(account_training_tasks._monitor_active_account_model(window_seconds=300))

    assert result == {
        "status": "completed",
        "snapshot": {"snapshot_id": "snapshot-rollback"},
        "automatic_rollback": {"status": "rolled_back", "snapshot_id": "snapshot-rollback"},
    }
    assert events == ["snapshot", "rollback", "invalidate"]


@pytest.mark.asyncio
async def test_worker_records_all_durable_training_stages(monkeypatch):
    run = AccountModelTrainingRun(
        run_id="run-worker",
        family="chinese_social_encoder",
        status="queued",
        stage="queued",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json=json.dumps({"output_dir": "account_detection/run-worker"}),
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    session = _Session(run)
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))
    monkeypatch.setattr(
        account_training_tasks,
        "execute_account_training_artifact",
        lambda **_kwargs: {"checkpoint_path": "account_detection/run-worker/checkpoint.pt"},
    )

    async def register_encoder(_session, *, training_run, result):
        assert training_run is run
        return result

    monkeypatch.setattr(account_training_tasks, "_register_chinese_social_encoder_version", register_encoder)

    result = await account_training_tasks._execute_account_training_run("run-worker", expected_attempt=1)

    assert result["status"] == "completed"
    assert run.status == "completed"
    assert run.resume_checkpoint_uri.endswith("checkpoint.pt")
    assert [event.event_type for event in session.added] == [
        "worker_claimed",
        "training_started",
        "evaluation_started",
        "completed",
    ]
    assert session.commits == 4
    assert session.statements[0]._for_update_arg is not None


@pytest.mark.asyncio
async def test_detector_worker_uses_service_bound_config_without_resolving_again(monkeypatch, tmp_path):
    encoder_dir = tmp_path / "encoder-v1"
    config = {
        "strict_protocol": True,
        "encoder_version": "encoder-v1",
        "encoder_artifact_hash": "a" * 64,
        "text_model_path": str(encoder_dir),
        "encoder_binding_payload_path": str(encoder_dir / "payload"),
        "frozen_holdout_manifest_path": "caller-controlled",
        "frozen_holdout_manifest_sha256": "b" * 64,
    }
    run = AccountModelTrainingRun(
        run_id="run-bound-detector",
        family="chinese_account_detector",
        status="queued",
        stage="queued",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json=json.dumps(config),
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    session = _Session(run)
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))
    monkeypatch.setattr(
        account_training_tasks,
        "_resolve_governed_detector_config",
        lambda *_args: pytest.fail("service-bound detector config must not be resolved again"),
    )
    monkeypatch.setattr(
        account_training_tasks,
        "execute_account_training_artifact",
        lambda **kwargs: {"bundle_manifest_path": "manifest.json", "observed_config": kwargs["config"]},
    )

    async def register_detector(_session, _run, result):
        return result

    monkeypatch.setattr(account_training_tasks, "_register_detector_candidate", register_detector)
    result = await account_training_tasks._execute_account_training_run(run.run_id, expected_attempt=1)

    assert result["status"] == "completed"
    assert "frozen_holdout_manifest_path" not in result["result"]["observed_config"]
    assert "frozen_holdout_manifest_sha256" not in result["result"]["observed_config"]


@pytest.mark.asyncio
async def test_detector_worker_resolves_legacy_unbound_config(monkeypatch, tmp_path):
    encoder_dir = tmp_path / "encoder-v1"
    run = AccountModelTrainingRun(
        run_id="run-legacy-detector",
        family="chinese_account_detector",
        status="queued",
        stage="queued",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json=json.dumps({"encoder_version": "encoder-v1"}),
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    session = _Session(run)
    resolved = {
        "strict_protocol": True,
        "encoder_version": "encoder-v1",
        "encoder_artifact_hash": "a" * 64,
        "text_model_path": str(encoder_dir),
        "encoder_binding_payload_path": str(encoder_dir / "payload"),
    }
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))

    async def resolve(_session, config):
        assert config == {"encoder_version": "encoder-v1"}
        return resolved

    monkeypatch.setattr(account_training_tasks, "_resolve_governed_detector_config", resolve)
    monkeypatch.setattr(
        account_training_tasks,
        "execute_account_training_artifact",
        lambda **kwargs: {"bundle_manifest_path": "manifest.json", "observed_config": kwargs["config"]},
    )

    async def register_detector(_session, _run, result):
        return result

    monkeypatch.setattr(account_training_tasks, "_register_detector_candidate", register_detector)
    result = await account_training_tasks._execute_account_training_run(run.run_id, expected_attempt=1)

    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_duplicate_worker_delivery_never_restarts_active_training(monkeypatch):
    run = AccountModelTrainingRun(
        run_id="run-active",
        family="chinese_social_encoder",
        status="running",
        stage="training",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    session = _Session(run)
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))

    result = await account_training_tasks._execute_account_training_run("run-active", expected_attempt=1)

    assert result == {"run_id": "run-active", "status": "already_running"}
    assert not session.added


@pytest.mark.asyncio
async def test_gpu_fence_is_released_when_run_fence_acquisition_raises(monkeypatch):
    run = AccountModelTrainingRun(
        run_id="run-lock-error",
        family="chinese_social_encoder",
        status="queued",
        stage="queued",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    session = _Session(run)

    class _GpuOwnership:
        released = False

        def release(self):
            self.released = True

    gpu_ownership = _GpuOwnership()
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))
    monkeypatch.setattr(
        account_training_tasks,
        "acquire_account_model_gpu_ownership",
        lambda _operation_id: gpu_ownership,
    )
    monkeypatch.setattr(
        account_training_tasks,
        "acquire_account_training_ownership",
        lambda *_args: (_ for _ in ()).throw(OSError("run fence unavailable")),
    )

    with pytest.raises(OSError, match="run fence unavailable"):
        await account_training_tasks._execute_account_training_run(run.run_id, expected_attempt=1)

    assert gpu_ownership.released is True


@pytest.mark.asyncio
async def test_duplicate_delivery_after_completion_is_gated_before_a_second_training_execution(monkeypatch):
    run = AccountModelTrainingRun(
        run_id="run-completed-delivery",
        family="chinese_social_encoder",
        status="completed",
        stage="completed",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    session = _Session(run)
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))
    monkeypatch.setattr(
        account_training_tasks,
        "execute_account_training_artifact",
        lambda **_kwargs: pytest.fail("a repeated delivery must not execute training twice"),
    )

    result = await account_training_tasks._execute_account_training_run(
        run.run_id,
        expected_attempt=1,
    )

    assert result == {"run_id": run.run_id, "status": "already_completed"}
    assert not session.added


@pytest.mark.asyncio
async def test_old_attempt_delivery_never_executes_the_current_attempt(monkeypatch):
    run = AccountModelTrainingRun(
        run_id="run-stale-attempt",
        family="chinese_social_encoder",
        status="queued",
        stage="resume_queued",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=2,
        max_attempts=4,
        created_by=1,
    )
    session = _Session(run)
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))
    monkeypatch.setattr(
        account_training_tasks,
        "execute_account_training_artifact",
        lambda **_kwargs: pytest.fail("a stale delivery must not execute training"),
    )

    result = await account_training_tasks._execute_account_training_run(
        run.run_id,
        expected_attempt=1,
    )

    assert result == {
        "run_id": run.run_id,
        "status": "stale_attempt",
        "expected_attempt": 1,
        "current_attempt": 2,
    }
    assert run.status == "queued"
    assert not session.added


def test_enqueue_carries_attempt_and_disables_celery_publish_retry(monkeypatch):
    observed = {}

    def apply_async(**kwargs):
        observed.update(kwargs)
        return "queued"

    monkeypatch.setattr(account_training_tasks.execute_account_training_run, "apply_async", apply_async)

    result = account_training_tasks.enqueue_account_training_run(
        "run-message-contract",
        attempt=3,
        task_id="task-attempt-3",
    )

    assert result == "queued"
    assert observed == {
        "args": ["run-message-contract", 3],
        "queue": "account_training",
        "task_id": "task-attempt-3",
        "retry": False,
    }


def test_training_task_retries_while_the_shared_gpu_is_owned(monkeypatch):
    retry_calls = []

    async def gpu_busy(_run_id, *, expected_attempt):
        assert expected_attempt == 2
        return {"run_id": "run-gpu-busy", "status": "gpu_busy"}

    monkeypatch.setattr(account_training_tasks, "_execute_account_training_run", gpu_busy)
    monkeypatch.setattr(account_training_tasks, "run_async", lambda coroutine: asyncio.run(coroutine))
    monkeypatch.setattr(
        account_training_tasks.execute_account_training_run,
        "retry",
        lambda **kwargs: retry_calls.append(kwargs) or "gpu-wait",
    )

    result = account_training_tasks.execute_account_training_run.run("run-gpu-busy", 2)

    assert result == "gpu-wait"
    assert retry_calls == [{"countdown": 30}]
    assert account_training_tasks.execute_account_training_run.max_retries is None


def test_training_timestamps_use_aware_utc_before_database_normalization(monkeypatch):
    expected = datetime(2026, 8, 7, 12, 30, tzinfo=timezone.utc)

    class _DateTimeProbe:
        @classmethod
        def now(cls, tz):
            assert tz is timezone.utc
            return expected

        @classmethod
        def utcnow(cls):
            raise AssertionError("datetime.utcnow() must not be used")

    monkeypatch.setattr(account_training_tasks, "datetime", _DateTimeProbe)

    assert account_training_tasks._utc_now() == expected.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_worker_releases_its_database_session_when_heartbeat_lease_is_lost(monkeypatch):
    run = AccountModelTrainingRun(
        run_id="run-lease-lost",
        family="chinese_social_encoder",
        status="running",
        stage="training",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    session = _Session(run)
    started = threading.Event()
    release = threading.Event()

    async def refresh(_value):
        run.status = "interrupted"

    def blocked_runtime(**_kwargs):
        started.set()
        release.wait(timeout=1)
        return {"checkpoint_path": "discarded.pt"}

    session.refresh = refresh
    monkeypatch.setattr(account_training_tasks, "_HEARTBEAT_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(account_training_tasks, "execute_account_training_artifact", blocked_runtime)

    try:
        result = await asyncio.wait_for(
            account_training_tasks._run_with_heartbeats(session, run, {}),
            timeout=0.1,
        )
    finally:
        release.set()

    assert result == {}
    assert started.is_set()


@pytest.mark.asyncio
async def test_cancelling_blocking_runtime_waits_before_releasing_ownership(monkeypatch, tmp_path):
    from app.config import settings
    from app.core import account_training_runtime

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    started = threading.Event()
    release = threading.Event()
    run = AccountModelTrainingRun(
        run_id="run-cancel-fence",
        family="chinese_social_encoder",
        status="running",
        stage="training",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    ownership = account_training_runtime.acquire_account_training_ownership(run.run_id, run.attempt)

    def blocked_runtime(**_kwargs):
        started.set()
        release.wait(timeout=2)
        return {"checkpoint_path": "cancelled.pt"}

    monkeypatch.setattr(account_training_tasks, "execute_account_training_artifact", blocked_runtime)

    async def worker() -> None:
        try:
            await account_training_tasks._run_with_heartbeats(_Session(run), run, {}, ownership=ownership)
        finally:
            ownership.release()

    task = asyncio.create_task(worker())
    await asyncio.to_thread(started.wait, 1)
    task.cancel()
    await asyncio.sleep(0)

    assert not task.done()
    assert account_training_runtime.account_training_ownership_path(run.run_id).exists()

    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not account_training_runtime.account_training_ownership_path(run.run_id).exists()


@pytest.mark.asyncio
async def test_runtime_exception_waits_before_releasing_ownership(monkeypatch, tmp_path):
    from app.config import settings
    from app.core import account_training_runtime

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(account_training_tasks, "_HEARTBEAT_INTERVAL_SECONDS", 0)
    started = threading.Event()
    release = threading.Event()
    run = AccountModelTrainingRun(
        run_id="run-exception-fence",
        family="chinese_social_encoder",
        status="running",
        stage="training",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    ownership = account_training_runtime.acquire_account_training_ownership(run.run_id, run.attempt)

    def blocked_runtime(**_kwargs):
        started.set()
        release.wait(timeout=2)
        return {"checkpoint_path": "failed-heartbeat.pt"}

    class _FailingSession(_Session):
        async def refresh(self, _value):
            raise RuntimeError("database refresh failed")

    monkeypatch.setattr(account_training_tasks, "execute_account_training_artifact", blocked_runtime)

    async def worker() -> None:
        try:
            await account_training_tasks._run_with_heartbeats(_FailingSession(run), run, {}, ownership=ownership)
        finally:
            ownership.release()

    task = asyncio.create_task(worker())
    await asyncio.to_thread(started.wait, 1)
    await asyncio.sleep(0)

    assert not task.done()
    assert account_training_runtime.account_training_ownership_path(run.run_id).exists()

    release.set()
    with pytest.raises(RuntimeError, match="database refresh failed"):
        await task
    assert not account_training_runtime.account_training_ownership_path(run.run_id).exists()


@pytest.mark.parametrize("stopped_status", ["interrupted", "cancelled"])
def test_detached_runtime_releases_fence_after_run_async_loop_stops(
    monkeypatch,
    tmp_path,
    stopped_status,
):
    from app.config import settings
    from app.core import account_training_runtime

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(account_training_tasks, "_HEARTBEAT_INTERVAL_SECONDS", 0)
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    run = AccountModelTrainingRun(
        run_id=f"run-loop-stop-{stopped_status}",
        family="chinese_social_encoder",
        status="running",
        stage="training",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    ownership = account_training_runtime.acquire_account_training_ownership(run.run_id, run.attempt)
    lock_path = account_training_runtime.account_training_ownership_path(run.run_id)

    class _StoppedSession(_Session):
        async def refresh(self, _value):
            run.status = stopped_status

    def blocked_runtime(**_kwargs):
        started.set()
        release.wait(timeout=2)
        finished.set()
        return {"checkpoint_path": "detached.pt"}

    monkeypatch.setattr(account_training_tasks, "execute_account_training_artifact", blocked_runtime)

    async def worker():
        try:
            return await account_training_tasks._run_with_heartbeats(
                _StoppedSession(run),
                run,
                {},
                ownership=ownership,
            )
        finally:
            if not ownership.release_deferred:
                ownership.release()

    try:
        assert run_async(worker()) == {}
        assert started.is_set()
        assert lock_path.exists()

        release.set()
        assert finished.wait(timeout=1)
        deadline = time.monotonic() + 1
        while lock_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not lock_path.exists()
    finally:
        release.set()
        close_async_runtime()


def test_runtime_ownership_fence_binds_pid_to_a_stable_process_identity(monkeypatch, tmp_path):
    from app.config import settings
    from app.core import account_training_runtime

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(account_training_runtime, "_process_identity", lambda pid: f"identity-{pid}")
    ownership = account_training_runtime.acquire_account_training_ownership("run-fence", 1)
    try:
        assert account_training_runtime.account_training_run_is_live("run-fence")
        with pytest.raises(account_training_runtime.AccountTrainingOwnershipBusyError):
            account_training_runtime.acquire_account_training_ownership("run-fence", 2)
    finally:
        ownership.release()

    lock_path = tmp_path / "account_training" / "locks" / "run-fence.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "process_identity": "reused-pid-owner",
                "token": "dead",
                "attempt": 1,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    recovered = account_training_runtime.acquire_account_training_ownership("run-fence", 2)
    try:
        assert recovered.attempt == 2
        assert not lock_path.read_text(encoding="utf-8").startswith('{"pid": 999999')
    finally:
        recovered.release()


def test_shared_account_model_gpu_fence_serializes_training_and_evaluation(monkeypatch, tmp_path):
    from app.config import settings
    from app.core import account_training_runtime

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(account_training_runtime, "_process_identity", lambda pid: f"identity-{pid}")

    training = account_training_runtime.acquire_account_model_gpu_ownership("training:run-1")
    try:
        with pytest.raises(account_training_runtime.AccountModelGpuOwnershipBusyError):
            account_training_runtime.acquire_account_model_gpu_ownership("evaluation:job-1")
    finally:
        training.release()

    evaluation = account_training_runtime.acquire_account_model_gpu_ownership("evaluation:job-1")
    evaluation.release()


def test_internal_dapt_loader_registers_the_module_before_dataclass_execution(monkeypatch):
    from app.core import account_training_runtime

    name = "_cogguard_account_dapt"
    monkeypatch.delitem(sys.modules, name, raising=False)

    module = account_training_runtime._load_dapt_module()

    assert sys.modules[name] is module
    assert module.DAPTConfig.__module__ == name


def test_legacy_or_malformed_ownership_fence_is_never_reclaimed(monkeypatch, tmp_path):
    from app.config import settings
    from app.core import account_training_runtime

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    lock_path = account_training_runtime.account_training_ownership_path("run-legacy-fence")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text('{"pid": 999999, "token": "legacy", "attempt": 1}', encoding="utf-8")

    assert account_training_runtime.account_training_run_is_live("run-legacy-fence")
    with pytest.raises(account_training_runtime.AccountTrainingOwnershipBusyError, match="unrecognized"):
        account_training_runtime.acquire_account_training_ownership("run-legacy-fence", 2)
    assert lock_path.exists()


def test_stale_reclaim_does_not_delete_a_new_owner_created_during_compare_and_delete(monkeypatch, tmp_path):
    from app.config import settings
    from app.core import account_training_runtime

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(account_training_runtime, "_process_identity", lambda pid: f"identity-{pid}")
    lock_path = account_training_runtime.account_training_ownership_path("run-reclaim-race")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "process_identity": "stale-identity",
                "token": "stale-token",
                "attempt": 1,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    replacement = json.dumps(
        {
            "pid": os.getpid(),
            "process_identity": f"identity-{os.getpid()}",
            "token": "replacement-token",
            "attempt": 2,
        },
        sort_keys=True,
    ).encode("utf-8")
    original_guard = account_training_runtime._fence_guard
    replaced = False

    @contextmanager
    def racing_guard(path):
        nonlocal replaced
        with original_guard(path):
            if not replaced:
                path.write_bytes(replacement)
                replaced = True
            yield

    monkeypatch.setattr(account_training_runtime, "_fence_guard", racing_guard)

    with pytest.raises(account_training_runtime.AccountTrainingOwnershipBusyError):
        account_training_runtime.acquire_account_training_ownership("run-reclaim-race", 3)

    assert lock_path.read_bytes() == replacement


@pytest.mark.skipif(os.name != "nt", reason="Windows PID liveness regression")
def test_windows_pid_liveness_uses_a_non_signaling_kernel_query(monkeypatch):
    from app.core import account_training_runtime

    def unexpected_signal(*_args):
        raise AssertionError("Windows PID liveness must not call os.kill")

    monkeypatch.setattr(account_training_runtime.os, "kill", unexpected_signal)
    assert account_training_runtime._pid_is_live(os.getpid())

    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait(timeout=10)
    assert not account_training_runtime._pid_is_live(process.pid)


@pytest.mark.asyncio
async def test_worker_uses_an_attempt_scoped_artifact_directory(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    run = AccountModelTrainingRun(
        run_id="run-attempt-output",
        family="chinese_social_encoder",
        status="queued",
        stage="queued",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json=json.dumps({"output_dir": "ignored/by/worker"}),
        attempt=2,
        max_attempts=4,
        created_by=1,
    )
    session = _Session(run)
    observed = {}
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))

    def runtime(**kwargs):
        observed.update(kwargs)
        return {"checkpoint_path": "checkpoint.pt"}

    monkeypatch.setattr(account_training_tasks, "execute_account_training_artifact", runtime)

    async def register_encoder(_session, *, training_run, result):
        assert training_run is run
        return result

    monkeypatch.setattr(account_training_tasks, "_register_chinese_social_encoder_version", register_encoder)

    result = await account_training_tasks._execute_account_training_run(run.run_id, expected_attempt=2)

    assert result["status"] == "completed"
    assert observed["output_dir"] == "account_training/run-attempt-output/attempt-2"


def test_worker_registers_completed_dapt_encoder_before_marking_the_run_complete(monkeypatch):
    run = AccountModelTrainingRun(
        run_id="run-register-encoder",
        family="chinese_social_encoder",
        status="queued",
        stage="queued",
        corpus_version_id="corpus-1",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=1,
    )
    session = _Session(run)
    observed = []
    monkeypatch.setattr(account_training_tasks, "async_session_factory", lambda: _SessionContext(session))
    monkeypatch.setattr(
        account_training_tasks,
        "execute_account_training_artifact",
        lambda **_kwargs: {
            "encoder_artifact_dir": "account_training/run-register-encoder/chinese_social_encoder",
            "encoder_artifact_hash": "c" * 64,
            "encoder_manifest_path": "account_training/run-register-encoder/chinese_social_encoder/encoder_manifest.json",
        },
    )

    async def register_encoder(_session, *, training_run, result):
        observed.append((training_run.run_id, result["encoder_artifact_hash"]))
        return {**result, "encoder_version": "chinese-social-encoder-run-register-encoder"}

    monkeypatch.setattr(
        account_training_tasks,
        "_register_chinese_social_encoder_version",
        register_encoder,
        raising=False,
    )

    result = asyncio.run(account_training_tasks._execute_account_training_run(run.run_id, expected_attempt=1))

    assert result["status"] == "completed"
    assert observed == [(run.run_id, "c" * 64)]
    assert result["result"]["encoder_version"] == "chinese-social-encoder-run-register-encoder"
