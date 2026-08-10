from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone

import pytest

from app.models.account_labeling import AccountModelEvaluationJob
from app.services.account_evaluation_dispatch import (
    acknowledge_account_model_evaluation_dispatch,
    claim_account_model_evaluation_dispatches,
    drain_account_model_evaluation_dispatch_outbox,
    finalize_account_model_evaluation_dispatch_claim,
)


class _Rows:
    def __init__(self, jobs):
        self.jobs = jobs

    def scalars(self):
        return self

    def all(self):
        now = _utc_now()
        return [
            job
            for job in self.jobs
            if (
                job.dispatch_status == "pending"
                and job.dispatch_available_at <= now
            )
            or (
                job.dispatch_status == "publishing"
                and job.dispatch_lease_expires_at is not None
                and job.dispatch_lease_expires_at <= now
            )
        ]

    def scalar_one_or_none(self):
        return self.jobs[0] if self.jobs else None


class _Session:
    def __init__(self, jobs):
        self.jobs = jobs
        self.commits = 0
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Rows(self.jobs)

    async def commit(self):
        self.commits += 1


class _SessionContext(AbstractAsyncContextManager):
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return None


def _pending_job() -> AccountModelEvaluationJob:
    return AccountModelEvaluationJob(
        job_id="evaluation-job-1",
        model_version="model-1",
        artifact_hash="a" * 64,
        corpus_version_id="corpus-1",
        holdout_fingerprint="b" * 64,
        config_fingerprint="c" * 64,
        evaluator_config_json="{}",
        status="queued",
        task_id="evaluation-task-1",
        operator_id=7,
        dispatch_status="pending",
        dispatch_publish_attempts=0,
        dispatch_available_at=_utc_now(),
    )


@pytest.mark.asyncio
async def test_evaluation_dispatch_is_published_once_after_claim_commit():
    job = _pending_job()
    session = _Session([job])
    published = []

    first = await drain_account_model_evaluation_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda job_id, *, task_id: published.append((job_id, task_id)),
    )
    second = await drain_account_model_evaluation_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=lambda job_id, *, task_id: published.append((job_id, task_id)),
    )

    assert first == {"published": 1, "failed": 0}
    assert second == {"published": 0, "failed": 0}
    assert published == [(job.job_id, job.task_id)]
    assert job.dispatch_status == "published"
    assert job.dispatch_publish_attempts == 1
    assert session.commits == 4
    claim_limits = [
        statement._limit_clause.value
        for statement in session.statements
        if getattr(statement, "_limit_clause", None) is not None
    ]
    assert claim_limits == [1, 1, 1]


@pytest.mark.asyncio
async def test_evaluation_dispatch_reclaims_only_an_expired_publish_lease():
    job = _pending_job()
    session = _Session([job])

    first = await claim_account_model_evaluation_dispatches(
        session_factory=lambda: _SessionContext(session),
        lease_seconds=30,
    )
    second = await claim_account_model_evaluation_dispatches(
        session_factory=lambda: _SessionContext(session),
        lease_seconds=30,
    )
    job.dispatch_lease_expires_at = _utc_now() - timedelta(seconds=1)
    reclaimed = await claim_account_model_evaluation_dispatches(
        session_factory=lambda: _SessionContext(session),
        lease_seconds=30,
    )

    assert len(first) == 1
    assert second == []
    assert len(reclaimed) == 1
    assert reclaimed[0]["task_id"] == first[0]["task_id"]
    assert reclaimed[0]["claim_token"] != first[0]["claim_token"]


@pytest.mark.asyncio
async def test_stale_evaluation_dispatch_claim_cannot_finalize_a_newer_claim():
    job = _pending_job()
    session = _Session([job])
    claims = await claim_account_model_evaluation_dispatches(
        session_factory=lambda: _SessionContext(session),
        lease_seconds=30,
    )
    job.dispatch_claim_token = "newer-owner"

    finalized = await finalize_account_model_evaluation_dispatch_claim(
        session_factory=lambda: _SessionContext(session),
        claim=claims[0],
        published=True,
    )

    assert finalized is False
    assert job.dispatch_status == "publishing"
    assert job.dispatch_claim_token == "newer-owner"


@pytest.mark.asyncio
async def test_evaluation_broker_failure_returns_dispatch_to_pending():
    job = _pending_job()
    session = _Session([job])

    def unavailable(_job_id, *, task_id):
        del task_id
        raise ConnectionError("broker unavailable")

    result = await drain_account_model_evaluation_dispatch_outbox(
        session_factory=lambda: _SessionContext(session),
        publish=unavailable,
        retry_delay_seconds=5,
    )

    assert result == {"published": 0, "failed": 1}
    assert job.dispatch_status == "pending"
    assert job.dispatch_publish_attempts == 1
    assert job.dispatch_available_at > _utc_now()
    assert "ConnectionError: broker unavailable" in job.dispatch_last_error


@pytest.mark.asyncio
async def test_published_but_unacknowledged_evaluation_is_not_republished_from_database_timeout():
    job = _pending_job()
    job.dispatch_status = "published"
    job.dispatch_published_at = _utc_now() - timedelta(seconds=61)
    session = _Session([job])

    claims = await claim_account_model_evaluation_dispatches(
        session_factory=lambda: _SessionContext(session),
        lease_seconds=30,
    )

    assert claims == []
    assert job.dispatch_status == "published"
    assert job.dispatch_acknowledged_at is None


@pytest.mark.asyncio
async def test_execution_acknowledgement_delays_republish_until_it_becomes_stale():
    job = _pending_job()
    job.dispatch_status = "published"
    job.dispatch_published_at = _utc_now() - timedelta(seconds=61)
    session = _Session([job])

    acknowledged = await acknowledge_account_model_evaluation_dispatch(
        session_factory=lambda: _SessionContext(session),
        job_id=job.job_id,
        task_id=job.task_id,
    )
    immediate = await claim_account_model_evaluation_dispatches(
        session_factory=lambda: _SessionContext(session),
    )
    job.dispatch_acknowledged_at = _utc_now() - timedelta(seconds=61)
    stale = await claim_account_model_evaluation_dispatches(
        session_factory=lambda: _SessionContext(session),
    )

    assert acknowledged is True
    assert immediate == []
    assert stale == []


@pytest.mark.asyncio
async def test_execution_acknowledgement_rejects_a_different_task_identity():
    job = _pending_job()
    job.dispatch_status = "published"
    session = _Session([job])

    acknowledged = await acknowledge_account_model_evaluation_dispatch(
        session_factory=lambda: _SessionContext(session),
        job_id=job.job_id,
        task_id="different-task",
    )

    assert acknowledged is False
    assert job.dispatch_acknowledged_at is None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
