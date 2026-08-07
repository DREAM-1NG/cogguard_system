"""System-owned frozen-holdout evaluation for account model candidates."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

from sqlalchemy import exists, select
from sqlalchemy.orm import aliased

from app.models.account_labeling import (
    AccountBehaviorLabelRecord,
    AccountDetectionCaseRecord,
    AccountDetectionModelVersion,
    AccountFrozenHoldoutMembership,
    AccountModelEvaluationJob,
    AccountTrainingExportMembership,
)
from app.core.account_model_artifact import load_deployable_bundle_manifest
from app.core.trained_bot_detection import get_trained_botrhg_inference
from app.services.account_model_governance_service import (
    sign_account_model_evaluation_manifest,
    write_account_model_evaluation,
)
from app.utils.exceptions import AppException

__all__ = [
    "CandidateEvaluationSnapshot",
    "FrozenHoldoutCase",
    "PreparedAccountModelEvaluation",
    "compute_holdout_fingerprint",
    "create_account_model_evaluation_job",
    "finalize_account_model_evaluation_job",
    "get_account_model_evaluation_job",
    "prepare_account_model_evaluation_job",
    "prepare_frozen_holdout_cases",
    "run_prepared_account_model_evaluation",
]

_MODEL_FAMILY = "chinese_account_detection"
_FORBIDDEN_CONFIG_KEYS = frozenset(
    {
        "artifact_hash",
        "audits",
        "evaluation_manifest",
        "evaluation_run_id",
        "gate",
        "gates",
        "metrics",
        "model_identity",
        "model_version",
        "prediction_audits",
        "signature",
        "signature_sha256",
    }
)


@dataclass(frozen=True, slots=True)
class FrozenHoldoutCase:
    """One validated immutable membership used by the evaluator."""

    membership_id: str
    corpus_version_id: str
    case_id: str
    label_id: str
    account_id: str
    platform: str
    event_id: str
    community: str
    target: str
    case_fingerprint: str
    source_payload_fingerprint: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CandidateEvaluationSource:
    """Explicit runtime source that cannot resolve an active model pointer."""

    model_version: str
    artifact_uri: str
    artifact_hash: str
    data_fingerprint: str
    source_schema: str
    pointer_revision: int = 0
    governance_status: str = "governed_active"


@dataclass(frozen=True, slots=True)
class CandidateEvaluationSnapshot:
    """Candidate fields captured while the database identity is locked."""

    model_version: str
    artifact_hash: str
    artifact_uri: str
    metrics_json: str


@dataclass(frozen=True, slots=True)
class PreparedAccountModelEvaluation:
    """Immutable inputs that may safely be evaluated after the prepare commit."""

    job_id: str
    model_version: str
    artifact_hash: str
    corpus_version_id: str
    holdout_fingerprint: str
    candidate: CandidateEvaluationSnapshot
    holdout_cases: tuple[FrozenHoldoutCase, ...]


def prepare_frozen_holdout_cases(
    rows: Iterable[tuple[Any, Any, Any]],
    *,
    corpus_version_id: str,
) -> list[FrozenHoldoutCase]:
    """Validate selected membership rows before their data reaches inference."""

    prepared: list[FrozenHoldoutCase] = []
    for row in rows:
        membership, label, case = row[:3]
        training_exported = bool(row[3]) if len(row) > 3 else False
        if str(getattr(membership, "corpus_version_id", "")) != corpus_version_id:
            raise AppException(code=409, msg="Frozen holdout membership belongs to another corpus version.")
        if (
            str(getattr(membership, "case_id", "")) != str(getattr(case, "case_id", ""))
            or str(getattr(membership, "label_id", "")) != str(getattr(label, "label_id", ""))
            or str(getattr(label, "case_id", "")) != str(getattr(case, "case_id", ""))
        ):
            raise AppException(code=409, msg="Frozen holdout membership does not match its persisted case and label.")
        if str(getattr(label, "label_status", "")) not in {"approved", "adjudicated"}:
            raise AppException(code=409, msg="Frozen holdout contains a label that is not approved or adjudicated.")
        if str(getattr(label, "training_target", "")) not in {"bot", "non_bot"}:
            raise AppException(code=409, msg="Frozen holdout contains a label outside bot/non_bot targets.")
        if str(getattr(label, "case_fingerprint", "")) != str(getattr(case, "case_fingerprint", "")):
            raise AppException(code=409, msg="Frozen holdout contains a stale case fingerprint.")
        if not bool(getattr(label, "current", True)):
            raise AppException(code=409, msg="Frozen holdout contains a superseded label revision.")
        if training_exported:
            raise AppException(code=409, msg="Frozen holdout contains a training export membership.")

        payload = _loads_mapping(getattr(case, "payload_json", "{}"))
        prepared.append(
            FrozenHoldoutCase(
                membership_id=str(getattr(membership, "membership_id", "")),
                corpus_version_id=corpus_version_id,
                case_id=str(getattr(case, "case_id", "")),
                label_id=str(getattr(label, "label_id", "")),
                account_id=str(getattr(case, "account_id", "")),
                platform=str(getattr(case, "platform", "")),
                event_id=str(getattr(case, "event_id", "")),
                community=str(payload.get("community") or getattr(case, "community", "") or ""),
                target=str(getattr(label, "training_target", "")),
                case_fingerprint=str(getattr(case, "case_fingerprint", "")),
                source_payload_fingerprint=_canonical_digest(payload),
                payload=payload,
            )
        )
    if not prepared:
        raise AppException(code=409, msg="Frozen holdout is empty.")
    return sorted(prepared, key=lambda row: row.membership_id)


def compute_holdout_fingerprint(rows: Iterable[FrozenHoldoutCase]) -> str:
    """Hash the durable membership and persisted source identity, never caller data."""

    normalized = [
        {
            "membership_id": row.membership_id,
            "case_fingerprint": row.case_fingerprint,
            "label_id": row.label_id,
            "target": row.target,
            "platform": row.platform,
            "event_id": row.event_id,
            "community": row.community,
            "source_payload_fingerprint": row.source_payload_fingerprint,
        }
        for row in sorted(rows, key=lambda item: item.membership_id)
    ]
    if not normalized:
        raise AppException(code=409, msg="Frozen holdout is empty.")
    return _canonical_digest(normalized)


async def create_account_model_evaluation_job(
    session,
    *,
    model_version: str,
    corpus_version_id: str,
    evaluator_config: Mapping[str, Any] | None,
    operator_id: int,
) -> dict[str, Any]:
    """Persist one idempotent, system-owned candidate evaluation request."""

    normalized_model_version = str(model_version or "").strip()
    normalized_corpus_version = str(corpus_version_id or "").strip()
    if not normalized_model_version or not normalized_corpus_version:
        raise AppException(code=400, msg="Account model evaluation requires model and frozen corpus versions.")
    config = _normalize_evaluator_config(evaluator_config)
    candidate = await _lock_candidate(session, normalized_model_version)
    if candidate is None:
        raise AppException(code=404, msg="Account model candidate not found.")
    if candidate.status not in {"shadow", "approved"}:
        raise AppException(code=409, msg="Only a shadow or approved account candidate can be evaluated.")
    artifact_hash = _sha256_identity(candidate.artifact_hash, label="candidate artifact hash")

    # Every evaluation path locks candidate, job, then frozen-holdout state.
    potential_jobs = (
        await session.execute(
            select(AccountModelEvaluationJob)
            .where(
                AccountModelEvaluationJob.model_version == normalized_model_version,
                AccountModelEvaluationJob.artifact_hash == artifact_hash,
                AccountModelEvaluationJob.corpus_version_id == normalized_corpus_version,
                AccountModelEvaluationJob.config_fingerprint == _canonical_digest(config),
            )
            .order_by(AccountModelEvaluationJob.job_id.asc())
            .with_for_update()
        )
    ).scalars().all()
    await _lock_frozen_holdout_state(session, corpus_version_id=normalized_corpus_version)
    holdout_cases = await _load_frozen_holdout_cases(session, corpus_version_id=normalized_corpus_version)
    holdout_fingerprint = compute_holdout_fingerprint(holdout_cases)
    config_fingerprint = _canonical_digest(config)
    existing = next(
        (row for row in potential_jobs if row.holdout_fingerprint == holdout_fingerprint),
        None,
    )
    if existing is not None:
        return _job_projection(existing)

    job = AccountModelEvaluationJob(
        job_id=f"account-evaluation-{uuid4().hex}",
        model_version=normalized_model_version,
        artifact_hash=artifact_hash,
        corpus_version_id=normalized_corpus_version,
        holdout_fingerprint=holdout_fingerprint,
        config_fingerprint=config_fingerprint,
        evaluator_config_json=_canonical_json(config),
        status="queued",
        task_id=f"account-evaluation-task-{uuid4().hex}",
        operator_id=int(operator_id),
    )
    session.add(job)
    await session.flush()
    return _job_projection(job)


async def get_account_model_evaluation_job(session, job_id: str) -> dict[str, Any] | None:
    """Project lifecycle status and immutable identities without case text or config."""

    row = (
        await session.execute(
            select(AccountModelEvaluationJob).where(AccountModelEvaluationJob.job_id == str(job_id).strip())
        )
    ).scalar_one_or_none()
    return _job_projection(row) if row is not None else None


async def prepare_account_model_evaluation_job(
    session,
    job_id: str,
) -> PreparedAccountModelEvaluation | dict[str, Any]:
    """Lock and snapshot a runnable job, leaving inference for after commit."""

    job_identity = (
        await session.execute(
            select(AccountModelEvaluationJob).where(AccountModelEvaluationJob.job_id == str(job_id).strip())
        )
    ).scalar_one_or_none()
    if job_identity is None:
        return {"job_id": str(job_id), "status": "missing"}

    candidate = await _lock_candidate(session, str(job_identity.model_version))
    job = await _lock_job(session, str(job_id))
    if job is None:
        return {"job_id": str(job_id), "status": "missing"}
    if job.status in {"completed", "failed", "cancelled"}:
        return _job_projection(job)
    if job.status not in {"queued", "running"}:
        raise AppException(code=409, msg="Account model evaluation job is not runnable.")
    _verify_candidate_job_identity(candidate, job)

    await _lock_frozen_holdout_state(session, corpus_version_id=job.corpus_version_id)
    holdout_cases = await _load_frozen_holdout_cases(session, corpus_version_id=job.corpus_version_id)
    holdout_fingerprint = compute_holdout_fingerprint(holdout_cases)
    if holdout_fingerprint != job.holdout_fingerprint:
        raise AppException(code=409, msg="Frozen holdout fingerprint changed before evaluation inference.")

    job.status = "running"
    job.started_at = job.started_at or _utc_now()
    job.error = None
    await session.flush()
    return PreparedAccountModelEvaluation(
        job_id=str(job.job_id),
        model_version=str(job.model_version),
        artifact_hash=str(job.artifact_hash),
        corpus_version_id=str(job.corpus_version_id),
        holdout_fingerprint=holdout_fingerprint,
        candidate=_candidate_evaluation_snapshot(candidate),
        holdout_cases=tuple(holdout_cases),
    )


async def run_prepared_account_model_evaluation(
    prepared: PreparedAccountModelEvaluation,
) -> list[dict[str, Any]]:
    """Load the verified candidate bundle and run inference without DB locks."""

    source = await asyncio.to_thread(_candidate_evaluation_source, prepared.candidate)
    inference = await asyncio.to_thread(_load_candidate_inference, source)
    posts = _holdout_inference_posts(list(prepared.holdout_cases))
    started = time.perf_counter()
    result = await asyncio.to_thread(inference.predict, posts)
    return _candidate_bound_audits(
        result,
        holdout_cases=list(prepared.holdout_cases),
        total_latency_ms=(time.perf_counter() - started) * 1000.0,
    )


async def finalize_account_model_evaluation_job(
    session,
    prepared: PreparedAccountModelEvaluation,
    prediction_audits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Re-lock and revalidate state before immutable evidence is signed or written."""

    job_identity = (
        await session.execute(
            select(AccountModelEvaluationJob).where(AccountModelEvaluationJob.job_id == prepared.job_id)
        )
    ).scalar_one_or_none()
    if job_identity is None:
        raise AppException(code=409, msg="Account model evaluation job disappeared before finalization.")
    candidate = await _lock_candidate(session, str(job_identity.model_version))
    job = await _lock_job(session, prepared.job_id)
    if job is None:
        raise AppException(code=409, msg="Account model evaluation job disappeared before finalization.")
    if job.status == "completed":
        return _job_projection(job)
    if job.status != "running":
        raise AppException(code=409, msg="Account model evaluation job is not awaiting finalization.")
    _verify_candidate_job_identity(candidate, job)
    if (
        str(job.model_version) != prepared.model_version
        or str(job.artifact_hash) != prepared.artifact_hash
        or str(job.corpus_version_id) != prepared.corpus_version_id
        or _candidate_evaluation_snapshot(candidate) != prepared.candidate
    ):
        raise AppException(code=409, msg="Account model candidate changed after evaluation inference.")

    await _lock_frozen_holdout_state(session, corpus_version_id=job.corpus_version_id)
    holdout_cases = await _load_frozen_holdout_cases(session, corpus_version_id=job.corpus_version_id)
    holdout_fingerprint = compute_holdout_fingerprint(holdout_cases)
    if holdout_fingerprint != prepared.holdout_fingerprint or holdout_fingerprint != job.holdout_fingerprint:
        raise AppException(code=409, msg="Frozen holdout fingerprint changed after evaluation inference.")

    evaluation_run_id = _evaluation_run_id(job)
    manifest = sign_account_model_evaluation_manifest(
        model_version=job.model_version,
        artifact_hash=job.artifact_hash,
        evaluation_run_id=evaluation_run_id,
        prediction_audits=prediction_audits,
    )
    evaluation = await write_account_model_evaluation(
        session,
        model_version=job.model_version,
        artifact_hash=job.artifact_hash,
        evaluation_run_id=evaluation_run_id,
        prediction_audits=prediction_audits,
        evaluation_manifest=manifest,
    )
    if evaluation is None:
        raise AppException(code=409, msg="Account model candidate disappeared during evaluation.")
    job.status = "completed"
    job.completed_evaluation_run_id = evaluation_run_id
    job.finished_at = _utc_now()
    await session.flush()
    return _job_projection(job)


async def _lock_candidate(session, model_version: str) -> AccountDetectionModelVersion | None:
    return (
        await session.execute(
            select(AccountDetectionModelVersion)
            .where(AccountDetectionModelVersion.model_version == model_version)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
    ).scalar_one_or_none()


async def _lock_job(session, job_id: str) -> AccountModelEvaluationJob | None:
    return (
        await session.execute(
            select(AccountModelEvaluationJob)
            .where(AccountModelEvaluationJob.job_id == str(job_id).strip())
            .execution_options(populate_existing=True)
            .with_for_update()
        )
    ).scalar_one_or_none()


async def _lock_frozen_holdout_state(session, *, corpus_version_id: str) -> None:
    """Lock membership, label/case, then existing export rows before a state read."""

    case_ids = (
        select(AccountFrozenHoldoutMembership.case_id)
        .where(AccountFrozenHoldoutMembership.corpus_version_id == corpus_version_id)
    )
    await session.execute(
        select(AccountFrozenHoldoutMembership)
        .where(AccountFrozenHoldoutMembership.corpus_version_id == corpus_version_id)
        .order_by(AccountFrozenHoldoutMembership.membership_id.asc())
        .with_for_update()
    )
    await session.execute(
        select(AccountBehaviorLabelRecord)
        .where(AccountBehaviorLabelRecord.label_id.in_(
            select(AccountFrozenHoldoutMembership.label_id).where(
                AccountFrozenHoldoutMembership.corpus_version_id == corpus_version_id
            )
        ))
        .order_by(AccountBehaviorLabelRecord.label_id.asc())
        .with_for_update()
    )
    await session.execute(
        select(AccountBehaviorLabelRecord)
        .where(AccountBehaviorLabelRecord.supersedes_id.in_(
            select(AccountFrozenHoldoutMembership.label_id).where(
                AccountFrozenHoldoutMembership.corpus_version_id == corpus_version_id
            )
        ))
        .order_by(AccountBehaviorLabelRecord.label_id.asc())
        .with_for_update()
    )
    await session.execute(
        select(AccountDetectionCaseRecord)
        .where(AccountDetectionCaseRecord.case_id.in_(case_ids))
        .order_by(AccountDetectionCaseRecord.case_id.asc())
        .with_for_update()
    )
    await session.execute(
        select(AccountTrainingExportMembership)
        .where(AccountTrainingExportMembership.case_id.in_(case_ids))
        .order_by(
            AccountTrainingExportMembership.case_id.asc(),
            AccountTrainingExportMembership.label_id.asc(),
            AccountTrainingExportMembership.export_membership_id.asc(),
        )
        .with_for_update()
    )


async def _load_frozen_holdout_cases(session, *, corpus_version_id: str) -> list[FrozenHoldoutCase]:
    newer_label = aliased(AccountBehaviorLabelRecord)
    rows = (
        await session.execute(
            select(
                AccountFrozenHoldoutMembership,
                AccountBehaviorLabelRecord,
                AccountDetectionCaseRecord,
                exists(
                    select(1).where(
                        AccountTrainingExportMembership.case_id == AccountFrozenHoldoutMembership.case_id,
                        AccountTrainingExportMembership.label_id == AccountFrozenHoldoutMembership.label_id,
                        AccountTrainingExportMembership.case_fingerprint
                        == AccountDetectionCaseRecord.case_fingerprint,
                    )
                ).label("training_exported"),
            )
            .join(
                AccountBehaviorLabelRecord,
                AccountBehaviorLabelRecord.label_id == AccountFrozenHoldoutMembership.label_id,
            )
            .join(
                AccountDetectionCaseRecord,
                AccountDetectionCaseRecord.case_id == AccountFrozenHoldoutMembership.case_id,
            )
            .where(AccountFrozenHoldoutMembership.corpus_version_id == corpus_version_id)
            .where(AccountBehaviorLabelRecord.case_id == AccountFrozenHoldoutMembership.case_id)
            .where(AccountBehaviorLabelRecord.label_status.in_(("approved", "adjudicated")))
            .where(AccountBehaviorLabelRecord.training_target.in_(("bot", "non_bot")))
            .where(AccountBehaviorLabelRecord.case_fingerprint == AccountDetectionCaseRecord.case_fingerprint)
            .where(
                ~exists(
                    select(1).where(
                        newer_label.case_id == AccountBehaviorLabelRecord.case_id,
                        newer_label.supersedes_id == AccountBehaviorLabelRecord.label_id,
                    )
                )
            )
            .order_by(AccountFrozenHoldoutMembership.membership_id.asc())
        )
    ).all()
    return prepare_frozen_holdout_cases(rows, corpus_version_id=corpus_version_id)


def _verify_candidate_job_identity(candidate: AccountDetectionModelVersion | None, job: AccountModelEvaluationJob) -> None:
    if candidate is None:
        raise AppException(code=409, msg="Account model candidate is missing for evaluation job.")
    if candidate.status not in {"shadow", "approved"}:
        raise AppException(code=409, msg="Account model candidate is no longer eligible for evaluation.")
    if _sha256_identity(candidate.artifact_hash, label="candidate artifact hash") != job.artifact_hash:
        raise AppException(code=409, msg="Account model candidate artifact changed after evaluation job creation.")


def _candidate_evaluation_snapshot(candidate: AccountDetectionModelVersion) -> CandidateEvaluationSnapshot:
    return CandidateEvaluationSnapshot(
        model_version=str(candidate.model_version),
        artifact_hash=_sha256_identity(candidate.artifact_hash, label="candidate artifact hash"),
        artifact_uri=str(candidate.artifact_uri),
        metrics_json=str(candidate.metrics_json),
    )


def _candidate_evaluation_source(candidate: CandidateEvaluationSnapshot) -> CandidateEvaluationSource:
    bundle_dir = Path(candidate.artifact_uri).expanduser().resolve()
    manifest = load_deployable_bundle_manifest(bundle_dir)
    source_schema = str(manifest.get("source_schema") or "").strip()
    if not source_schema:
        raise AppException(code=409, msg="Candidate deployable bundle has no source schema.")
    metrics = _loads_mapping(candidate.metrics_json)
    return CandidateEvaluationSource(
        model_version=str(candidate.model_version),
        artifact_uri=str(bundle_dir),
        artifact_hash=_sha256_identity(candidate.artifact_hash, label="candidate artifact hash"),
        data_fingerprint=str(metrics.get("data_fingerprint") or metrics.get("dataset_fingerprint") or ""),
        source_schema=source_schema,
    )


def _load_candidate_inference(source: CandidateEvaluationSource) -> Any:
    inference = get_trained_botrhg_inference(source, allow_legacy_fallback=False)
    if inference is None:
        raise AppException(code=409, msg="Candidate BotRHG bundle runtime is unavailable.")
    return inference


def _holdout_inference_posts(holdout_cases: list[FrozenHoldoutCase]) -> list[dict[str, Any]]:
    """Translate persisted case evidence to the existing runtime input without label features."""

    posts: list[dict[str, Any]] = []
    for row in holdout_cases:
        payload = row.payload
        text = str(payload.get("text") or payload.get("content") or "").strip()
        if not text:
            raise AppException(code=409, msg="Frozen holdout case has no persisted inference text.")
        posts.append(
            {
                "author_id": row.account_id,
                "user_id": row.account_id,
                "post_id": row.case_id,
                "platform": row.platform,
                "event_id": row.event_id,
                "content": text,
                "timestamp": str(payload.get("last_seen_at") or payload.get("first_seen_at") or ""),
                "author_name": str(payload.get("author_name") or ""),
            }
        )
    return posts


def _candidate_bound_audits(
    result: Any,
    *,
    holdout_cases: list[FrozenHoldoutCase],
    total_latency_ms: float,
) -> list[dict[str, Any]]:
    if not isinstance(result, Mapping) or not isinstance(result.get("accounts"), list):
        raise AppException(code=409, msg="Candidate BotRHG runtime returned an invalid prediction payload.")
    predictions = {
        str(row.get("account_id") or ""): row
        for row in result["accounts"]
        if isinstance(row, Mapping) and str(row.get("account_id") or "")
    }
    audits: list[dict[str, Any]] = []
    for row in holdout_cases:
        prediction = predictions.get(row.account_id)
        if prediction is None:
            raise AppException(code=409, msg="Candidate BotRHG runtime omitted a frozen holdout prediction.")
        probability = prediction.get("calibrated_probability")
        if probability is None:
            probability = prediction.get("calibrated_bot_probability")
        if probability is None:
            probability = prediction.get("final_bot_probability")
        try:
            normalized_probability = float(probability)
        except (TypeError, ValueError) as error:
            raise AppException(code=409, msg="Candidate BotRHG runtime returned an invalid frozen holdout probability.") from error
        if not 0.0 <= normalized_probability <= 1.0:
            raise AppException(code=409, msg="Candidate BotRHG runtime returned an out-of-range frozen holdout probability.")
        final_prediction = str(prediction.get("final_prediction") or "").strip().lower()
        if final_prediction not in {"bot", "human", "non_bot"}:
            raise AppException(code=409, msg="Candidate BotRHG runtime returned an invalid frozen holdout prediction.")
        audits.append(
            {
                "account_id": row.account_id,
                "platform": row.platform,
                "input_fingerprint": _canonical_digest(
                    {
                        "membership_id": row.membership_id,
                        "case_id": row.case_id,
                        "case_fingerprint": row.case_fingerprint,
                        "source_payload_fingerprint": row.source_payload_fingerprint,
                    }
                ),
                "probability": normalized_probability,
                "prediction": "bot" if final_prediction == "bot" else "non_bot",
                "target": 1 if row.target == "bot" else 0,
                "abstained": not bool(prediction.get("calibrated", prediction.get("calibration_passed", False))),
                "latency_ms": float(total_latency_ms),
                "hard_error": False,
            }
        )
    return audits


def _evaluation_run_id(job: AccountModelEvaluationJob) -> str:
    return "account-evaluation-run-" + _canonical_digest(
        {
            "job_id": job.job_id,
            "model_version": job.model_version,
            "artifact_hash": job.artifact_hash,
            "holdout_fingerprint": job.holdout_fingerprint,
            "config_fingerprint": job.config_fingerprint,
        }
    )[:32]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_evaluator_config(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise AppException(code=400, msg="Evaluator configuration must be an object.")
    payload = dict(value)
    if _contains_forbidden_config_key(payload):
        raise AppException(code=400, msg="Evaluator configuration cannot supply evaluation evidence or model identity.")
    return payload


def _contains_forbidden_config_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).strip().lower() in _FORBIDDEN_CONFIG_KEYS or _contains_forbidden_config_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_config_key(item) for item in value)
    return False


def _sha256_identity(value: Any, *, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise AppException(code=409, msg=f"Account evaluation {label} is invalid.")
    return normalized


def _job_projection(row: AccountModelEvaluationJob) -> dict[str, Any]:
    return {
        "job_id": row.job_id,
        "model_family": _MODEL_FAMILY,
        "model_version": row.model_version,
        "artifact_hash": row.artifact_hash,
        "corpus_version_id": row.corpus_version_id,
        "holdout_fingerprint": row.holdout_fingerprint,
        "config_fingerprint": row.config_fingerprint,
        "status": row.status,
        "task_id": row.task_id,
        "operator_id": row.operator_id,
        "completed_evaluation_run_id": row.completed_evaluation_run_id,
        "created_at": _isoformat(row.created_at),
        "started_at": _isoformat(row.started_at),
        "finished_at": _isoformat(row.finished_at),
    }


def _isoformat(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _loads_mapping(value: Any) -> dict[str, Any]:
    try:
        payload = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as error:
        raise AppException(code=409, msg="Frozen holdout case payload is invalid.") from error
    if not isinstance(payload, Mapping):
        raise AppException(code=409, msg="Frozen holdout case payload is invalid.")
    return dict(payload)


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
