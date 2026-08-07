from __future__ import annotations

import asyncio
import threading
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.account_labeling import AccountModelTrainingDispatchOutbox, AccountModelTrainingRun
from app.services.account_training_dispatch_outbox import (
    account_training_dispatch_task_id,
    claim_account_training_dispatches,
    drain_account_training_dispatch_outbox,
    finalize_account_training_dispatch_claim,
    pending_account_training_dispatches_statement,
)


class _Rows:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return [
            value
            for value in self.values
            if (
                value.status == "pending" and value.available_at <= _utc_now()
            ) or (
                value.status == "publishing"
                and value.lease_expires_at is not None
                and value.lease_expires_at <= _utc_now()
            )
        ]

    def scalar_one_or_none(self):
        return self.values[0] if self.values else None


class _One:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


_UNSET = object()


class _PublisherSession:
    def __init__(self, committed_rows, *, run=_UNSET):
        self.committed_rows = committed_rows
        self.run = _training_run() if run is _UNSET else run
        self.statements = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        self.statements.append(statement)
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountModelTrainingRun:
            return _One(self.run)
        return _Rows(self.committed_rows)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class _SessionContext(AbstractAsyncContextManager):
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return None


def _pending_dispatch(*, run_id: str = "run-outbox", attempt: int = 1):
    return AccountModelTrainingDispatchOutbox(
        dispatch_id=f"account-training-dispatch:{run_id}:attempt:{attempt}",
        run_id=run_id,
        attempt=attempt,
        task_id=account_training_dispatch_task_id(run_id, attempt),
        status="pending",
        publish_attempts=0,
        available_at=_utc_now(),
    )


def _training_run(*, run_id: str = "run-outbox", attempt: int = 1, status: str = "queued"):
    return AccountModelTrainingRun(
        run_id=run_id,
        family="chinese_social_encoder",
        status=status,
        stage="queued",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=attempt,
        max_attempts=4,
        created_by=1,
    )


@pytest.mark.asyncio
async def test_outbox_drain_cannot_publish_an_uncommitted_dispatch():
    uncommitted = _pending_dispatch()
    session = _PublisherSession(committed_rows=[])
    published = []

    drained = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
    )

    assert drained == {"published": 0, "failed": 0}
    assert published == []
    assert uncommitted.status == "pending"


@pytest.mark.asyncio
async def test_outbox_drain_publishes_only_committed_dispatch_and_marks_it_published():
    dispatch = _pending_dispatch()
    session = _PublisherSession(committed_rows=[dispatch])
    published = []

    drained = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
    )

    assert drained == {"published": 1, "failed": 0}
    assert published == [("run-outbox", 1, account_training_dispatch_task_id("run-outbox", 1))]
    assert dispatch.status == "published"
    assert dispatch.publish_attempts == 1
    assert dispatch.published_at is not None
    assert session.commits == 2


@pytest.mark.asyncio
async def test_outbox_commits_claim_before_calling_the_broker():
    dispatch = _pending_dispatch()
    session = _PublisherSession(committed_rows=[dispatch])
    broker_commit_counts = []

    drained = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda *_args, **_kwargs: broker_commit_counts.append(session.commits),
    )

    assert drained == {"published": 1, "failed": 0}
    assert broker_commit_counts == [1]
    assert session.commits == 2


@pytest.mark.asyncio
async def test_expired_publishing_lease_is_claimed_and_published_again():
    dispatch = _pending_dispatch()
    dispatch.status = "publishing"
    dispatch.claim_token = "crashed-publisher"
    dispatch.lease_expires_at = _utc_now() - timedelta(seconds=1)
    session = _PublisherSession(committed_rows=[dispatch])

    drained = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda *_args, **_kwargs: None,
    )

    assert drained == {"published": 1, "failed": 0}
    assert dispatch.status == "published"
    assert dispatch.publish_attempts == 1
    assert dispatch.claim_token is None
    assert dispatch.lease_expires_at is None


@pytest.mark.asyncio
async def test_publish_before_finalize_crash_reuses_the_same_task_id_after_lease_reclaim():
    dispatch = _pending_dispatch()
    session = _PublisherSession(committed_rows=[dispatch])
    first_claims = await claim_account_training_dispatches(
        session_factory=lambda: _SessionContext(session),
        limit=1,
        lease_seconds=30,
    )

    assert len(first_claims) == 1
    first = first_claims[0]
    # The broker accepted this message, but the publisher crashed before its
    # token-fenced finalize transaction could run.
    broker_messages = [(first["run_id"], first["attempt"], first["task_id"])]
    dispatch.lease_expires_at = _utc_now() - timedelta(seconds=1)

    replay = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda run_id, *, attempt, task_id: broker_messages.append((run_id, attempt, task_id)),
    )

    assert replay == {"published": 1, "failed": 0}
    assert broker_messages == [
        (dispatch.run_id, dispatch.attempt, dispatch.task_id),
        (dispatch.run_id, dispatch.attempt, dispatch.task_id),
    ]
    assert dispatch.status == "published"
    assert dispatch.publish_attempts == 2


@pytest.mark.asyncio
async def test_stale_claim_token_cannot_finalize_a_newer_claim():
    dispatch = _pending_dispatch()
    session = _PublisherSession(committed_rows=[dispatch])

    claims = await claim_account_training_dispatches(
        session_factory=lambda: _SessionContext(session),
        limit=1,
        lease_seconds=30,
    )
    assert len(claims) == 1
    dispatch.claim_token = "newer-claim-token"

    finalized = await finalize_account_training_dispatch_claim(
        session_factory=lambda: _SessionContext(session),
        claim=claims[0],
        published=True,
    )

    assert finalized is False
    assert dispatch.status == "publishing"
    assert dispatch.claim_token == "newer-claim-token"


@pytest.mark.asyncio
async def test_two_publishers_do_not_publish_the_same_active_claim():
    dispatch = _pending_dispatch()
    session = _PublisherSession(committed_rows=[dispatch])
    started = threading.Event()
    release = threading.Event()
    published = []

    def blocked_publish(run_id, *, attempt, task_id):
        started.set()
        release.wait(timeout=1)
        published.append((run_id, attempt, task_id))

    first = asyncio.create_task(
        drain_account_training_dispatch_outbox(
            session_factory=lambda: _SessionContext(session),
            publish=blocked_publish,
        )
    )
    try:
        assert await asyncio.to_thread(started.wait, 1)
        second = await drain_account_training_dispatch_outbox(
            session_factory=lambda: _SessionContext(session),
            publish=blocked_publish,
        )
        assert second == {"published": 0, "failed": 0}
    finally:
        release.set()
    assert await first == {"published": 1, "failed": 0}
    assert published == [(dispatch.run_id, dispatch.attempt, dispatch.task_id)]


@pytest.mark.asyncio
async def test_outbox_broker_failure_leaves_dispatch_pending_for_a_later_retry():
    dispatch = _pending_dispatch()
    session = _PublisherSession(committed_rows=[dispatch])

    def unavailable(_run_id, *, attempt, task_id):
        del attempt, task_id
        raise ConnectionError("broker unavailable")

    drained = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=unavailable,
        retry_delay_seconds=3,
    )

    assert drained == {"published": 0, "failed": 1}
    assert dispatch.status == "pending"
    assert dispatch.publish_attempts == 1
    assert "ConnectionError: broker unavailable" in dispatch.last_error
    assert dispatch.available_at > _utc_now() - timedelta(seconds=2)
    assert dispatch.published_at is None

    dispatch.available_at = _utc_now()
    retried = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda _run_id, *, attempt, task_id: (attempt, task_id),
    )

    assert retried == {"published": 1, "failed": 0}
    assert dispatch.status == "published"
    assert dispatch.publish_attempts == 2


@pytest.mark.asyncio
async def test_outbox_drain_is_idempotent_after_a_successful_publish():
    dispatch = _pending_dispatch()
    session = _PublisherSession(committed_rows=[dispatch])
    published = []

    first = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
    )
    second = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
    )

    assert first == {"published": 1, "failed": 0}
    assert second == {"published": 0, "failed": 0}
    assert published == [("run-outbox", 1, account_training_dispatch_task_id("run-outbox", 1))]


@pytest.mark.asyncio
async def test_cancelled_pending_dispatch_is_superseded_without_broker_publish():
    dispatch = _pending_dispatch()
    run = _training_run(status="cancelled")
    session = _PublisherSession([dispatch], run=run)
    published = []

    result = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
    )

    assert result == {"published": 0, "failed": 0}
    assert dispatch.status == "superseded"
    assert dispatch.publish_attempts == 0
    assert published == []


@pytest.mark.asyncio
async def test_missing_run_pending_dispatch_is_superseded_without_broker_publish():
    dispatch = _pending_dispatch()
    session = _PublisherSession([dispatch], run=None)
    published = []

    result = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
    )

    assert result == {"published": 0, "failed": 0}
    assert dispatch.status == "superseded"
    assert dispatch.publish_attempts == 0
    assert dispatch.last_error == "training run is missing"
    assert published == []


@pytest.mark.asyncio
async def test_stale_attempt_pending_dispatch_is_superseded_without_broker_publish():
    dispatch = _pending_dispatch(attempt=1)
    session = _PublisherSession([dispatch], run=_training_run(attempt=2))
    published = []

    result = await drain_account_training_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
    )

    assert result == {"published": 0, "failed": 0}
    assert dispatch.status == "superseded"
    assert dispatch.publish_attempts == 0
    assert dispatch.last_error == "training run attempt no longer matches dispatch"
    assert published == []


@pytest.mark.asyncio
async def test_broker_publish_runs_off_event_loop_and_cancellation_is_bounded():
    dispatch = _pending_dispatch()
    session = _PublisherSession([dispatch])
    started = threading.Event()
    release = threading.Event()

    def blocked_publish(_run_id, *, attempt, task_id):
        del attempt, task_id
        started.set()
        release.wait(timeout=1)

    task = asyncio.create_task(
        drain_account_training_dispatch_outbox(
            session_factory=lambda: _SessionContext(session),
            publish=blocked_publish,
        )
    )
    try:
        await asyncio.sleep(0.05)
        assert started.is_set()
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.2)
    finally:
        release.set()


def test_pending_dispatch_query_uses_skip_locked_row_claiming():
    statement = pending_account_training_dispatches_statement(limit=8)

    assert statement._for_update_arg is not None
    assert statement._for_update_arg.skip_locked is True


@pytest.mark.asyncio
async def test_outbox_publisher_only_reads_dispatches_after_the_creator_commits(db_session):
    dispatch = _pending_dispatch(run_id="mysql-commit-boundary")
    run = _training_run(run_id=dispatch.run_id)
    db_session.add_all([run, dispatch])
    await db_session.flush()
    engine = create_async_engine(settings.mysql_url_test, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    published = []
    try:
        before_commit = await drain_account_training_dispatch_outbox(
            session_factory=sessions,
            publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
        )
        assert before_commit == {"published": 0, "failed": 0}
        assert published == []

        await db_session.commit()
        after_commit = await drain_account_training_dispatch_outbox(
            session_factory=sessions,
            publish=lambda run_id, *, attempt, task_id: published.append((run_id, attempt, task_id)),
        )
        assert after_commit == {"published": 1, "failed": 0}
        assert published == [(dispatch.run_id, dispatch.attempt, dispatch.task_id)]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mysql_publishers_skip_each_others_locked_dispatches(db_session):
    first_dispatch = _pending_dispatch(run_id="mysql-publisher-first")
    second_dispatch = _pending_dispatch(run_id="mysql-publisher-second")
    db_session.add_all(
        [
            _training_run(run_id=first_dispatch.run_id),
            _training_run(run_id=second_dispatch.run_id),
            first_dispatch,
            second_dispatch,
        ]
    )
    await db_session.commit()
    engine = create_async_engine(settings.mysql_url_test, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    first_started = threading.Event()
    release_first = threading.Event()
    published = []

    def publish(run_id, *, attempt, task_id):
        if run_id == first_dispatch.run_id:
            first_started.set()
            release_first.wait(timeout=2)
        published.append((run_id, attempt, task_id))

    first_drain = asyncio.create_task(
        drain_account_training_dispatch_outbox(session_factory=sessions, publish=publish, limit=1)
    )
    try:
        assert await asyncio.to_thread(first_started.wait, 1)
        second_result = await asyncio.wait_for(
            drain_account_training_dispatch_outbox(session_factory=sessions, publish=publish, limit=1),
            timeout=1,
        )
        assert second_result == {"published": 1, "failed": 0}
        assert published == [
            (second_dispatch.run_id, second_dispatch.attempt, second_dispatch.task_id)
        ]
    finally:
        release_first.set()
        await first_drain
        await engine.dispose()


@pytest.mark.asyncio
async def test_lifespan_cancels_the_outbox_publisher_without_leaving_a_task(monkeypatch):
    from fastapi import FastAPI

    from app import main

    stopped = asyncio.Event()

    class _StartupSession(AbstractAsyncContextManager):
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def commit(self):
            return None

    async def publisher(stop_event):
        await stop_event.wait()
        stopped.set()

    async def no_op(*_args, **_kwargs):
        return None

    monkeypatch.setattr(main, "async_session_factory", lambda: _StartupSession())
    monkeypatch.setattr(main, "ensure_default_admin", no_op)
    monkeypatch.setattr(main, "run_account_training_dispatch_outbox_publisher", publisher)
    monkeypatch.setattr(main, "close_mongo", no_op)
    monkeypatch.setattr(main, "close_redis", no_op)
    monkeypatch.setattr(main, "close_mysql", no_op)

    app = FastAPI()
    async with main.lifespan(app):
        task = app.state.account_training_outbox_publisher_task
        assert not task.done()

    assert stopped.is_set()
    assert task.done()
    assert task.cancelled() is False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
