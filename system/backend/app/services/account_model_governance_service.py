"""Governance gates for Chinese account-detection model versions."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.account_model_artifact import (
    file_sha256,
    load_verified_chinese_social_encoder_artifact,
    load_deployable_bundle_manifest,
    load_verified_bundle_manifest,
    resolve_bundle_component,
    verify_bundle_files,
)
from app.models.account_labeling import (
    AccountModelGovernanceDecision,
    AccountDetectionDatasetVersion,
    AccountDetectionModelActivation,
    AccountDetectionModelApproval,
    AccountDetectionModelVersion,
    AccountModelTrainingRun,
    AccountModelEvaluationRun,
    AccountMonitorSnapshot,
    AccountPredictionAudit,
    ChineseSocialEncoderVersion,
)
from app.core.account_model_monitoring import summarize_account_predictions
from app.models.user import User
from app.utils.exceptions import AppException

__all__ = [
    "activate_account_detection_model",
    "attempt_automatic_account_model_rollback",
    "approve_account_detection_model",
    "evaluate_account_model_activation_gates",
    "list_account_detection_models",
    "register_chinese_social_encoder_version",
    "rollback_account_detection_model",
    "register_account_training_candidate",
    "register_account_training_result",
    "sign_account_model_evaluation_manifest",
    "resolve_governed_chinese_social_encoder",
    "write_account_model_evaluation",
]

_EVALUATION_PACKAGE_NAME = "_cogguard_account_evaluation_protocol"
_EVALUATION_MANIFEST_SCHEMA = "cogguard.account-model-evaluation-manifest.v1"
_MODEL_FAMILY = "chinese_account_detection"
_EVALUATOR_OWNED_METRIC_KEYS = {
    "calibration",
    "ece",
    "evaluation_protocol",
    "shadow_evaluation",
    "shadow_run_passed",
    "false_positive_burden_passed",
}
_AUTOMATIC_ROLLBACK_IMMEDIATE_REASONS = (
    "active_model_bundle_invalid",
    "account_model_runtime_load_failure",
)


def evaluate_account_model_activation_gates(
    metrics: dict[str, Any],
    *,
    approver_ids: list[int] | tuple[int, ...],
    model_version: str | None = None,
    artifact_hash: str | None = None,
    max_ece: float = 0.05,
) -> dict[str, Any]:
    """Return account-model activation gates and final activation decision."""

    distinct_approvers = {int(approver_id) for approver_id in approver_ids if int(approver_id) > 0}
    protocol = metrics.get("evaluation_protocol")
    protocol_gates = protocol.get("gates") if isinstance(protocol, dict) else None
    calibration_passed = _trusted_calibration_gate(
        metrics,
        model_version=model_version,
        artifact_hash=artifact_hash,
        max_ece=max_ece,
    )
    shadow_gates = _shadow_evaluation_gates(
        metrics.get("shadow_evaluation"),
        model_version=model_version,
        artifact_hash=artifact_hash,
    )
    gates = {
        "evaluation_protocol": bool(
            _is_persisted_evaluation_protocol(protocol)
            and bool(protocol.get("activation_allowed"))
            and isinstance(protocol_gates, dict)
        ),
        "frozen_holdout": bool(protocol_gates.get("frozen_holdout")) if isinstance(protocol_gates, dict) else False,
        "account_disjoint": bool(protocol_gates.get("account_disjoint")) if isinstance(protocol_gates, dict) else False,
        "time_forward": bool(protocol_gates.get("time_forward")) if isinstance(protocol_gates, dict) else False,
        "platform_stratified": bool(protocol_gates.get("platform_stratified")) if isinstance(protocol_gates, dict) else False,
        "community_disjoint": bool(protocol_gates.get("community_disjoint")) if isinstance(protocol_gates, dict) else False,
        "calibration": calibration_passed,
        "false_positive_burden": shadow_gates["false_positive_burden"],
        "shadow_run": shadow_gates["shadow_run"],
        "dual_approval": len(distinct_approvers) >= 2,
    }
    return {
        "activation_allowed": all(gates.values()),
        "gates": gates,
        "requirements": {
            "label_source": "approved_or_adjudicated_observable_behavior_labels_only",
            "holdout_policy": "frozen_holdout_never_selected_by_active_learning",
            "deployment_policy": "review_aid_only_until_activated",
            "max_ece": max_ece,
            "evaluation_policy": "shadow and false-positive gates require candidate-bound evaluator audit writeback",
        },
    }


async def register_account_training_candidate(
    session: AsyncSession,
    *,
    model_version: str,
    dataset_version_id: str,
    artifact_uri: str,
    artifact_hash: str,
    metrics: dict[str, Any],
    operator_id: int,
    encoder_version: str | None = None,
    encoder_artifact_hash: str | None = None,
) -> dict[str, Any]:
    """Register a shadow candidate trained from approved account labels."""

    dataset = (
        await session.execute(
            select(AccountDetectionDatasetVersion).where(
                AccountDetectionDatasetVersion.dataset_version_id == dataset_version_id
            )
        )
    ).scalar_one_or_none()
    if dataset is None:
        raise AppException(code=404, msg="Account detection dataset version not found.")
    if dataset.source_label_count <= 0:
        raise AppException(code=409, msg="Account detection dataset version has no approved labels.")
    if dataset.status not in {"candidate", "approved", "training_ready"}:
        raise AppException(code=409, msg="Account detection dataset version is not eligible for training.")
    verified_artifact_hash = _verify_artifact_hash(artifact_uri, artifact_hash)
    normalized_encoder_version, normalized_encoder_hash = _normalize_encoder_binding(
        encoder_version,
        encoder_artifact_hash,
    )
    existing = (
        await session.execute(
            select(AccountDetectionModelVersion).where(AccountDetectionModelVersion.model_version == model_version)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if (
            existing.dataset_version_id != dataset_version_id
            or existing.artifact_uri != artifact_uri
            or existing.artifact_hash.lower() != verified_artifact_hash.lower()
            or existing.encoder_version != normalized_encoder_version
            or (existing.encoder_artifact_hash or "").lower() != (normalized_encoder_hash or "").lower()
        ):
            raise AppException(code=409, msg="Account model candidate registration conflicts with existing provenance.")
        return _model_projection(existing)
    persisted_metrics = {
        **_registration_metrics(metrics),
        "dataset_fingerprint": dataset.data_fingerprint,
        "source_label_count": dataset.source_label_count,
    }
    gates = evaluate_account_model_activation_gates(
        persisted_metrics,
        approver_ids=[],
        model_version=model_version,
        artifact_hash=verified_artifact_hash,
    )
    record = AccountDetectionModelVersion(
        model_version=model_version,
        dataset_version_id=dataset_version_id,
        encoder_version=normalized_encoder_version,
        encoder_artifact_hash=normalized_encoder_hash,
        artifact_uri=artifact_uri,
        artifact_hash=verified_artifact_hash,
        metrics_json=json.dumps(persisted_metrics, ensure_ascii=False),
        gates_json=json.dumps(gates, ensure_ascii=False),
        status="shadow",
        created_by=operator_id,
    )
    session.add(record)
    await session.flush()
    return _model_projection(record)


async def register_account_training_result(
    session: AsyncSession,
    *,
    run_id: str,
    dataset_version_id: str,
    artifact_uri: str,
    metrics: dict[str, Any],
    operator_id: int,
    encoder_version: str | None = None,
    encoder_artifact_hash: str | None = None,
) -> dict[str, Any]:
    """Register a worker-produced bundle idempotently as a shadow candidate."""

    normalized_encoder_version, normalized_encoder_hash = _normalize_encoder_binding(
        encoder_version,
        encoder_artifact_hash,
        required=True,
    )
    encoder = (
        await session.execute(
            select(ChineseSocialEncoderVersion).where(
                ChineseSocialEncoderVersion.encoder_version == normalized_encoder_version
            )
        )
    ).scalar_one_or_none()
    if encoder is None or encoder.status != "completed":
        raise AppException(code=409, msg="Detector training requires a completed registered Chinese social encoder version.")
    if encoder.artifact_hash.lower() != normalized_encoder_hash:
        raise AppException(code=409, msg="Detector training encoder artifact hash does not match the registered version.")
    load_verified_chinese_social_encoder_artifact(encoder.artifact_uri, expected_hash=encoder.artifact_hash)

    model_version = f"account-model-{run_id}"
    existing = (
        await session.execute(
            select(AccountDetectionModelVersion).where(
                AccountDetectionModelVersion.model_version == model_version
            )
        )
    ).scalar_one_or_none()
    bundle_path = Path(artifact_uri).resolve()
    bundle_manifest = load_verified_bundle_manifest(bundle_path)
    bundle_encoder_hash = str(((bundle_manifest.get("components") or {}).get("encoder") or {}).get("sha256") or "")
    if bundle_encoder_hash.lower() != normalized_encoder_hash:
        raise AppException(code=409, msg="Detector bundle encoder component does not match the registered encoder artifact.")
    artifact_path = resolve_bundle_component(bundle_path, "detector")
    artifact_hash = file_sha256(artifact_path)
    if existing is not None:
        if (
            existing.artifact_hash.lower() != artifact_hash.lower()
            or existing.encoder_version != normalized_encoder_version
            or (existing.encoder_artifact_hash or "").lower() != normalized_encoder_hash
        ):
            raise AppException(code=409, msg="Training result changed for an existing run candidate.")
        return _model_projection(existing)
    return await register_account_training_candidate(
        session,
        model_version=model_version,
        dataset_version_id=dataset_version_id,
        artifact_uri=artifact_uri,
        artifact_hash=artifact_hash,
        encoder_version=normalized_encoder_version,
        encoder_artifact_hash=normalized_encoder_hash,
        metrics={
            **metrics,
            "training_run_id": run_id,
            "artifact_schema": "cogguard.account-model-bundle.v1",
            "source_schema": str(bundle_manifest.get("source_schema") or ""),
        },
        operator_id=operator_id,
    )


async def register_chinese_social_encoder_version(
    session: AsyncSession,
    *,
    run: AccountModelTrainingRun,
    training_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist one immutable encoder version for a completed DAPT run."""

    if run.family != "chinese_social_encoder":
        raise AppException(code=409, msg="Only Chinese social encoder training runs can register an encoder version.")
    if not run.run_id or not run.corpus_version_id:
        raise AppException(code=409, msg="Chinese social encoder registration requires run and corpus provenance.")
    artifact_uri = str(training_result.get("encoder_artifact_dir") or "").strip()
    artifact_hash = str(training_result.get("encoder_artifact_hash") or "").strip().lower()
    if not artifact_uri or not artifact_hash:
        raise AppException(code=409, msg="Chinese social encoder training did not produce a registered artifact.")
    manifest = load_verified_chinese_social_encoder_artifact(artifact_uri, expected_hash=artifact_hash)
    provenance = manifest.get("provenance")
    corpus = provenance.get("corpus") if isinstance(provenance, Mapping) else None
    if not isinstance(corpus, Mapping) or corpus.get("input_fingerprint") != run.input_fingerprint:
        raise AppException(code=409, msg="Chinese social encoder artifact corpus fingerprint does not match its training run.")
    base_model_identity = str(manifest.get("base_model_identity") or "").strip()
    if not base_model_identity:
        raise AppException(code=409, msg="Chinese social encoder artifact has no base model identity.")
    encoder_version = f"chinese-social-encoder-{run.run_id}"
    existing = (
        await session.execute(
            select(ChineseSocialEncoderVersion)
            .where(ChineseSocialEncoderVersion.training_run_id == run.run_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is not None:
        if (
            existing.encoder_version != encoder_version
            or existing.corpus_version_id != run.corpus_version_id
            or existing.artifact_uri != str(Path(artifact_uri).resolve())
            or existing.artifact_hash.lower() != artifact_hash
            or existing.base_model_identity != base_model_identity
            or _loads(existing.manifest_json) != manifest
            or existing.status != "completed"
        ):
            raise AppException(code=409, msg="Chinese social encoder registration conflicts with immutable existing provenance.")
        return _encoder_projection(existing)
    record = ChineseSocialEncoderVersion(
        encoder_version=encoder_version,
        corpus_version_id=run.corpus_version_id,
        training_run_id=run.run_id,
        artifact_uri=str(Path(artifact_uri).resolve()),
        artifact_hash=artifact_hash,
        base_model_identity=base_model_identity,
        manifest_json=_canonical_json(manifest),
        status="completed",
        created_by=int(run.created_by),
    )
    session.add(record)
    await session.flush()
    return _encoder_projection(record)


async def resolve_governed_chinese_social_encoder(
    session: AsyncSession,
    *,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve a completed version and replace untrusted detector path inputs."""

    payload = dict(config)
    model_payload = dict(payload.get("model") or {})
    if str(payload.get("text_model_path") or "").strip() or str(model_payload.get("text_model_path") or "").strip():
        raise AppException(code=409, msg="Governed detector training text_model_path is not accepted; use encoder_version.")
    if bool(model_payload.get("encoder_trainable", False)):
        raise AppException(code=409, msg="Governed detector training requires an immutable frozen encoder version.")
    encoder_version = str(payload.get("encoder_version") or "").strip()
    if not encoder_version:
        raise AppException(code=409, msg="Governed detector training requires a registered encoder_version.")
    record = (
        await session.execute(
            select(ChineseSocialEncoderVersion).where(
                ChineseSocialEncoderVersion.encoder_version == encoder_version
            )
        )
    ).scalar_one_or_none()
    if record is None or record.status != "completed":
        raise AppException(code=409, msg="Governed detector training requires a completed registered encoder version.")
    manifest = load_verified_chinese_social_encoder_artifact(
        record.artifact_uri,
        expected_hash=record.artifact_hash,
    )
    if _loads(record.manifest_json) != manifest:
        raise AppException(code=409, msg="Registered Chinese social encoder manifest does not match its immutable artifact.")
    artifact_dir = str(Path(record.artifact_uri).resolve())
    encoder_payload = manifest.get("encoder_payload")
    if not isinstance(encoder_payload, Mapping) or not isinstance(encoder_payload.get("path"), str):
        raise AppException(code=409, msg="Registered Chinese social encoder payload is invalid.")
    payload.update(
        {
            "encoder_version": record.encoder_version,
            "encoder_artifact_hash": record.artifact_hash.lower(),
            "encoder_binding_payload_path": str(Path(artifact_dir) / encoder_payload["path"]),
            "text_model_path": artifact_dir,
            "model": {**model_payload, "encoder_trainable": False},
        }
    )
    return payload


async def list_account_detection_models(session: AsyncSession) -> list[dict[str, Any]]:
    """Return registered account model versions."""

    rows = (
        await session.execute(
            select(AccountDetectionModelVersion).order_by(AccountDetectionModelVersion.created_at.desc())
        )
    ).scalars().all()
    return [_model_projection(row) for row in rows]


def sign_account_model_evaluation_manifest(
    *,
    model_version: str,
    artifact_hash: str,
    evaluation_run_id: str,
    prediction_audits: list[dict[str, Any]],
    evaluation_protocol: dict[str, Any] | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Create evaluator evidence bound to the exact normalized writeback payload."""

    evidence = _prepare_evaluation_evidence(
        model_version=model_version,
        artifact_hash=artifact_hash,
        evaluation_run_id=evaluation_run_id,
        prediction_audits=prediction_audits,
        evaluation_protocol=evaluation_protocol,
    )
    body = _evaluation_manifest_body(evidence)
    signature = hmac.new(
        _evaluation_hmac_secret(secret),
        _canonical_json(body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**body, "signature_sha256": signature}


async def write_account_model_evaluation(
    session: AsyncSession,
    *,
    model_version: str,
    artifact_hash: str,
    evaluation_run_id: str,
    prediction_audits: list[dict[str, Any]],
    evaluation_protocol: dict[str, Any] | None = None,
    evaluation_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Persist evaluator-produced shadow evidence and derive activation gates.

    The writeback stores raw prediction audit summaries before deriving the
    monitor snapshot.  The candidate's registration payload is never used to
    assert operational shadow or false-positive gates.
    """

    evidence = _prepare_evaluation_evidence(
        model_version=model_version,
        artifact_hash=artifact_hash,
        evaluation_run_id=evaluation_run_id,
        prediction_audits=prediction_audits,
        evaluation_protocol=evaluation_protocol,
    )
    _verify_evaluation_manifest(evidence, evaluation_manifest)

    record = (
        await session.execute(
            select(AccountDetectionModelVersion)
            .with_for_update()
            .where(AccountDetectionModelVersion.model_version == model_version)
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    if record.status not in {"shadow", "approved"}:
        raise AppException(code=409, msg="Only a shadow candidate can receive evaluator writeback.")
    expected_hash = evidence["artifact_hash"]
    verified_hash = _verify_artifact_hash(record.artifact_uri, record.artifact_hash)
    if expected_hash != record.artifact_hash.lower() or verified_hash.lower() != expected_hash:
        raise AppException(code=409, msg="Evaluator writeback artifact hash does not match the candidate.")
    normalized_run_id = evidence["evaluation_run_id"]
    existing_evaluation = (
        await session.execute(
            select(AccountModelEvaluationRun)
            .with_for_update()
            .where(AccountModelEvaluationRun.evaluation_run_id == normalized_run_id)
        )
    ).scalar_one_or_none()
    if existing_evaluation is not None:
        if (
            existing_evaluation.family != _MODEL_FAMILY
            or existing_evaluation.model_version != model_version
            or existing_evaluation.artifact_hash.lower() != verified_hash.lower()
        ):
            raise AppException(
                code=409,
                msg="Evaluation run id already belongs to another candidate and cannot be reused.",
            )
        if existing_evaluation.evaluation_fingerprint != evidence["evaluation_fingerprint"]:
            raise AppException(
                code=409,
                msg="Evaluation run conflicts with immutable evaluator evidence already persisted for this candidate.",
            )
        return {
            **_model_projection(record),
            "approval_invalidated_count": 0,
            "evaluation_replayed": True,
        }

    for prepared_audit in evidence["audits"]:
        audit = prepared_audit["audit"]
        audit_id = prepared_audit["audit_id"]
        existing = (
            await session.execute(select(AccountPredictionAudit).where(AccountPredictionAudit.audit_id == audit_id))
        ).scalar_one_or_none()
        if existing is not None:
            continue
        payload = {
            **audit,
            "model_identity": {
                "family": _MODEL_FAMILY,
                "model_version": model_version,
                "artifact_hash": verified_hash,
                "evaluation_run_id": normalized_run_id,
            },
        }
        session.add(
            AccountPredictionAudit(
                audit_id=audit_id,
                case_id="account-shadow-case-" + _canonical_digest((normalized_run_id, audit["account_id"]))[:16],
                account_id=audit["account_id"],
                platform=audit["platform"],
                family=_MODEL_FAMILY,
                model_version=model_version,
                pointer_revision=0,
                input_fingerprint=audit["input_fingerprint"],
                prediction_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            )
        )
    await session.flush()

    audits = await _evaluation_audits(
        session,
        model_version=model_version,
        artifact_hash=verified_hash,
        evaluation_run_id=normalized_run_id,
    )
    summary = summarize_account_predictions(_evaluation_prediction_rows(audits))
    persisted_audit_ids = sorted(audit.audit_id for audit in audits)
    audit_fingerprint = _canonical_digest(persisted_audit_ids)
    if audit_fingerprint != evidence["audit_fingerprint"]:
        raise AppException(code=409, msg="Persisted evaluator audits do not match the signed evaluation manifest.")
    snapshot_id = "account-shadow-monitor-" + _canonical_digest(
        (model_version, verified_hash, normalized_run_id, evidence["evaluation_fingerprint"])
    )[:32]
    snapshot = (
        await session.execute(select(AccountMonitorSnapshot).where(AccountMonitorSnapshot.snapshot_id == snapshot_id))
    ).scalar_one_or_none()
    if snapshot is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        snapshot = AccountMonitorSnapshot(
            snapshot_id=snapshot_id,
            family=_MODEL_FAMILY,
            model_version=model_version,
            pointer_revision=0,
            window_started_at=now,
            window_finished_at=now,
            status=str(summary["status"]),
            metrics_json=json.dumps(
                {
                    **summary,
                    "model_identity": {
                        "family": _MODEL_FAMILY,
                        "model_version": model_version,
                        "artifact_hash": verified_hash,
                        "evaluation_run_id": normalized_run_id,
                    },
                    "audit_fingerprint": audit_fingerprint,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        session.add(snapshot)

    prior_metrics = _loads(record.metrics_json)
    prior_fingerprint = _metrics_fingerprint(prior_metrics)
    metrics = {
        **_registration_metrics(prior_metrics),
        "shadow_evaluation": {
            "model_version": model_version,
            "artifact_hash": verified_hash,
            "evaluation_run_id": normalized_run_id,
            "audit_fingerprint": audit_fingerprint,
            "evaluation_fingerprint": evidence["evaluation_fingerprint"],
            "monitor_snapshot_id": snapshot_id,
            "summary": summary,
            "calibration": {
                "source": "signed_evaluator_audit",
                "evaluation_fingerprint": evidence["evaluation_fingerprint"],
                "ece": summary["ece"],
                "labeled_prediction_count": summary["labeled_prediction_count"],
            },
        },
    }
    if evaluation_protocol is not None:
        metrics["evaluation_protocol"] = evaluation_protocol
    session.add(
        AccountModelEvaluationRun(
            evaluation_run_id=normalized_run_id,
            family=_MODEL_FAMILY,
            model_version=model_version,
            artifact_hash=verified_hash,
            evaluation_fingerprint=evidence["evaluation_fingerprint"],
            audit_fingerprint=audit_fingerprint,
            manifest_json=_canonical_json(dict(evaluation_manifest or {})),
        )
    )
    record.metrics_json = json.dumps(metrics, ensure_ascii=False, sort_keys=True)
    record.gates_json = json.dumps(
        evaluate_account_model_activation_gates(
            metrics,
            approver_ids=[],
            model_version=model_version,
            artifact_hash=verified_hash,
        ),
        ensure_ascii=False,
    )
    invalidated = 0
    if _metrics_fingerprint(metrics) != prior_fingerprint:
        approvals = (
            await session.execute(
                select(AccountDetectionModelApproval).where(AccountDetectionModelApproval.model_version == model_version)
            )
        ).scalars().all()
        invalidated = len(approvals)
        if invalidated and record.status == "approved":
            record.status = "shadow"
    await session.flush()
    return {**_model_projection(record), "approval_invalidated_count": invalidated}


async def approve_account_detection_model(
    session: AsyncSession,
    *,
    model_version: str,
    approver_id: int,
    approval_notes: str = "",
) -> dict[str, Any] | None:
    """Record one immutable active-administrator approval for a shadow model."""

    await _require_active_admin(session, approver_id)
    record = (
        await session.execute(
            select(AccountDetectionModelVersion).where(
                AccountDetectionModelVersion.model_version == model_version
            )
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    if record.status not in {"shadow", "approved"}:
        raise AppException(code=409, msg="Only a shadow or approved account model can receive approvals.")
    existing = (
        await session.execute(
            select(AccountDetectionModelApproval).where(
                AccountDetectionModelApproval.model_version == model_version,
                AccountDetectionModelApproval.approver_id == int(approver_id),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        current_fingerprint = _metrics_fingerprint(_loads(record.metrics_json))
        if (
            existing.artifact_hash.lower() != record.artifact_hash.lower()
            or existing.metrics_fingerprint != current_fingerprint
        ):
            raise AppException(
                code=409,
                msg="Approval was invalidated by changed candidate metrics; register a new candidate version for reapproval.",
            )
        return {
            "approval": _approval_projection(existing),
            "approval_recorded": False,
            "active_approval_count": await _approval_count(session, model_version=model_version),
        }
    approval = AccountDetectionModelApproval(
        approval_id=f"account-model-approval-{uuid4().hex[:16]}",
        model_version=model_version,
        approver_id=int(approver_id),
        artifact_hash=record.artifact_hash,
        metrics_fingerprint=_metrics_fingerprint(_loads(record.metrics_json)),
        approval_notes=approval_notes,
    )
    session.add(approval)
    await session.flush()
    count = await _approval_count(session, model_version=model_version)
    if count >= 2 and record.status == "shadow":
        record.status = "approved"
    await session.flush()
    return {
        "approval": _approval_projection(approval),
        "approval_recorded": True,
        "active_approval_count": count,
        "ready_for_activation": count >= 2,
    }


async def activate_account_detection_model(
    session: AsyncSession,
    *,
    model_version: str,
    operator_id: int,
    activation_notes: str = "",
) -> dict[str, Any] | None:
    """Activate a candidate model only when persisted gates and admin approvals pass."""

    record = (
        await session.execute(
            select(AccountDetectionModelVersion)
            .with_for_update()
            .where(AccountDetectionModelVersion.model_version == model_version)
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    persisted_metrics = _loads(record.metrics_json)
    locked_metrics_fingerprint = _metrics_fingerprint(persisted_metrics)
    locked_artifact_hash = record.artifact_hash.lower()
    locked_artifact_uri = record.artifact_uri
    await _require_active_admin(session, operator_id)
    approver_ids = await _active_model_approval_ids(
        session,
        model_version=model_version,
        artifact_hash=record.artifact_hash,
        metrics_fingerprint=locked_metrics_fingerprint,
    )
    _require_recorded_approvals(approver_ids=approver_ids, operator_id=operator_id)
    decision = evaluate_account_model_activation_gates(
        persisted_metrics,
        approver_ids=approver_ids,
        model_version=record.model_version,
        artifact_hash=record.artifact_hash,
    )
    if decision["activation_allowed"]:
        verified_artifact_hash = _verify_artifact_hash(
            record.artifact_uri,
            record.artifact_hash,
            require_deployable=True,
        )
        if verified_artifact_hash.lower() != locked_artifact_hash:
            raise AppException(code=409, msg="Account model artifact changed after candidate registration.")
        await session.refresh(
            record,
            attribute_names=["artifact_hash", "artifact_uri", "metrics_json", "status"],
        )
        refreshed_metrics = _loads(record.metrics_json)
        if _metrics_fingerprint(refreshed_metrics) != locked_metrics_fingerprint:
            raise AppException(code=409, msg="Account model candidate metrics changed during activation.")
        if record.artifact_hash.lower() != locked_artifact_hash or record.artifact_uri != locked_artifact_uri:
            raise AppException(code=409, msg="Account model candidate artifact identity changed during activation.")
        reverified_artifact_hash = _verify_artifact_hash(
            record.artifact_uri,
            record.artifact_hash,
            require_deployable=True,
        )
        if reverified_artifact_hash.lower() != locked_artifact_hash:
            raise AppException(code=409, msg="Account model artifact changed during activation.")
        await _verify_persisted_evaluation_evidence(
            session,
            metrics=refreshed_metrics,
            model_version=record.model_version,
            artifact_hash=locked_artifact_hash,
        )
        record.status = "active"
        existing = (
            await session.execute(
                select(AccountDetectionModelActivation).with_for_update().where(
                    AccountDetectionModelActivation.model_family == "chinese_account_detection"
                )
            )
        ).scalar_one_or_none()
        payload = {
            "decision": decision,
            "approver_ids": approver_ids,
            "activation_notes": activation_notes,
        }
        previous_model_version = existing.model_version if existing else None
        pointer_revision = (int(existing.pointer_revision) + 1) if existing else 1
        if existing and existing.model_version != model_version:
            previous = (
                await session.execute(
                    select(AccountDetectionModelVersion).where(
                        AccountDetectionModelVersion.model_version == existing.model_version
                    )
                )
            ).scalar_one_or_none()
            if previous is not None and previous.status == "active":
                previous.status = "retired"
        payload["pointer_revision"] = pointer_revision
        if existing is None:
            session.add(
                AccountDetectionModelActivation(
                    model_family="chinese_account_detection",
                    model_version=model_version,
                    pointer_revision=pointer_revision,
                    activation_json=json.dumps(payload, ensure_ascii=False),
                    activated_by=operator_id,
                )
            )
        else:
            existing.model_version = model_version
            existing.pointer_revision = pointer_revision
            existing.activation_json = json.dumps(payload, ensure_ascii=False)
            existing.activated_by = operator_id
        session.add(
            AccountModelGovernanceDecision(
                decision_id=f"account-model-decision-{uuid4().hex[:16]}",
                family="chinese_account_detection",
                model_version=model_version,
                previous_model_version=previous_model_version,
                pointer_revision=pointer_revision,
                decision_type="activation",
                decision_json=json.dumps(payload, ensure_ascii=False),
                decided_by=operator_id,
            )
        )
    record.gates_json = json.dumps(decision, ensure_ascii=False)
    await session.flush()
    return {**_model_projection(record), "activation_decision": decision}


async def rollback_account_detection_model(
    session: AsyncSession,
    *,
    model_version: str,
    operator_id: int,
    reason: str,
) -> dict[str, Any] | None:
    """Restore a previously governed model without creating a new activation path."""

    await _require_active_admin(session, operator_id)
    target = (
        await session.execute(
            select(AccountDetectionModelVersion)
            .with_for_update()
            .where(AccountDetectionModelVersion.model_version == model_version)
        )
    ).scalar_one_or_none()
    if target is None:
        return None
    if target.status not in {"active", "retired"}:
        raise AppException(code=409, msg="Rollback requires a previously governed active or retired account model.")
    activation_history = (
        await session.execute(
            select(AccountModelGovernanceDecision)
            .where(
                AccountModelGovernanceDecision.family == _MODEL_FAMILY,
                AccountModelGovernanceDecision.model_version == model_version,
                AccountModelGovernanceDecision.decision_type.in_(("activation", "rollback")),
            )
        )
    ).scalars().all()
    if not activation_history:
        raise AppException(code=409, msg="Rollback requires persisted governed activation history for the target model.")
    metrics = _loads(target.metrics_json)
    locked_metrics_fingerprint = _metrics_fingerprint(metrics)
    locked_artifact_hash = target.artifact_hash.lower()
    locked_artifact_uri = target.artifact_uri
    approver_ids = await _active_model_approval_ids(
        session,
        model_version=model_version,
        artifact_hash=target.artifact_hash,
        metrics_fingerprint=locked_metrics_fingerprint,
    )
    _require_recorded_approvals(approver_ids=approver_ids, operator_id=operator_id)
    decision = evaluate_account_model_activation_gates(
        metrics,
        approver_ids=approver_ids,
        model_version=target.model_version,
        artifact_hash=target.artifact_hash,
    )
    if not decision["activation_allowed"]:
        raise AppException(code=409, msg="Rollback target no longer satisfies current activation gates.")
    verified_artifact_hash = _verify_artifact_hash(
        target.artifact_uri,
        target.artifact_hash,
        require_deployable=True,
    )
    if verified_artifact_hash.lower() != locked_artifact_hash:
        raise AppException(code=409, msg="Rollback target artifact changed after prior activation.")
    if target.artifact_uri != locked_artifact_uri or _metrics_fingerprint(_loads(target.metrics_json)) != locked_metrics_fingerprint:
        raise AppException(code=409, msg="Rollback target identity changed while locked.")
    await _verify_persisted_evaluation_evidence(
        session,
        metrics=metrics,
        model_version=target.model_version,
        artifact_hash=locked_artifact_hash,
    )
    pointer = (
        await session.execute(
            select(AccountDetectionModelActivation).with_for_update().where(
                AccountDetectionModelActivation.model_family == "chinese_account_detection"
            )
        )
    ).scalar_one_or_none()
    previous = pointer.model_version if pointer else None
    revision = (int(pointer.pointer_revision) + 1) if pointer else 1
    if pointer is None:
        pointer = AccountDetectionModelActivation(
            model_family="chinese_account_detection",
            model_version=model_version,
            pointer_revision=revision,
            activation_json=json.dumps(
                {"reason": reason, "decision": decision, "approver_ids": approver_ids}, ensure_ascii=False
            ),
            activated_by=operator_id,
        )
        session.add(pointer)
    else:
        pointer.model_version = model_version
        pointer.pointer_revision = revision
        pointer.activation_json = json.dumps(
            {"reason": reason, "decision": decision, "approver_ids": approver_ids}, ensure_ascii=False
        )
        pointer.activated_by = operator_id
    if previous and previous != model_version:
        old = (
            await session.execute(
                select(AccountDetectionModelVersion).where(AccountDetectionModelVersion.model_version == previous)
            )
        ).scalar_one_or_none()
        if old is not None and old.status == "active":
            old.status = "retired"
    target.status = "active"
    session.add(
        AccountModelGovernanceDecision(
            decision_id=f"account-model-decision-{uuid4().hex[:16]}",
            family="chinese_account_detection",
            model_version=model_version,
            previous_model_version=previous,
            pointer_revision=revision,
            decision_type="rollback",
            decision_json=json.dumps(
                {"reason": reason, "decision": decision, "approver_ids": approver_ids}, ensure_ascii=False
            ),
            decided_by=operator_id,
        )
    )
    await session.flush()
    return {**_model_projection(target), "pointer_revision": revision, "previous_model_version": previous}


async def attempt_automatic_account_model_rollback(
    session: AsyncSession,
    *,
    snapshot_id: str,
) -> dict[str, Any]:
    """Restore the exact governed predecessor selected by a monitor snapshot.

    The snapshot is the only scheduler input. Its immutable identity derives
    the target before this path follows the manual rollback lock order.
    """

    snapshot = (
        await session.execute(
            select(AccountMonitorSnapshot)
            .where(AccountMonitorSnapshot.snapshot_id == str(snapshot_id))
        )
    ).scalar_one_or_none()
    if snapshot is None:
        return _automatic_rollback_noop("snapshot_missing")

    eligibility = await _automatic_rollback_eligibility(session, snapshot=snapshot)
    if eligibility is None:
        return _automatic_rollback_noop("rollback_not_eligible", snapshot_id=snapshot.snapshot_id)

    # The append-only source decision supplies only an unlocked target identity.
    # The decision is re-locked after the target, pointer, and current model.
    snapshot_source = await _source_decision_for_pointer_identity(
        session,
        family=snapshot.family,
        model_version=snapshot.model_version,
        pointer_revision=int(snapshot.pointer_revision),
        lock=False,
    )
    if snapshot_source is None:
        return _automatic_rollback_blocked("source_decision_missing", snapshot_id=snapshot.snapshot_id)
    target_version = str(snapshot_source.previous_model_version or "").strip()
    if not target_version or target_version == snapshot.model_version:
        return _automatic_rollback_blocked("previous_target_missing", snapshot_id=snapshot.snapshot_id)

    # Match manual rollback: target model first, active pointer second, then
    # the current/old model that may be retired by the pointer transition.
    target = (
        await session.execute(
            select(AccountDetectionModelVersion)
            .with_for_update()
            .where(AccountDetectionModelVersion.model_version == target_version)
        )
    ).scalar_one_or_none()
    if target is None or target.status not in {"active", "retired"}:
        return _automatic_rollback_blocked("previous_target_not_deployable", snapshot_id=snapshot.snapshot_id)

    pointer = (
        await session.execute(
            select(AccountDetectionModelActivation)
            .with_for_update()
            .where(AccountDetectionModelActivation.model_family == _MODEL_FAMILY)
        )
    ).scalar_one_or_none()
    if pointer is None:
        return _automatic_rollback_noop("active_pointer_missing", snapshot_id=snapshot.snapshot_id)
    current = (
        await session.execute(
            select(AccountDetectionModelVersion)
            .with_for_update()
            .where(AccountDetectionModelVersion.model_version == pointer.model_version)
        )
    ).scalar_one_or_none()
    if current is None:
        return _automatic_rollback_noop("active_model_missing", snapshot_id=snapshot.snapshot_id)
    source_decision = await _source_decision_for_pointer_identity(
        session,
        family=pointer.model_family,
        model_version=pointer.model_version,
        pointer_revision=int(pointer.pointer_revision),
        lock=True,
    )

    existing = await _automatic_rollback_decision_for_snapshot(session, snapshot.snapshot_id)
    if existing is not None:
        return {
            "status": "already_rolled_back",
            "snapshot_id": snapshot.snapshot_id,
            "decision_id": existing.decision_id,
            "pointer_revision": int(existing.pointer_revision),
        }

    if not _snapshot_matches_active_pointer(snapshot, pointer=pointer, current=current):
        return _automatic_rollback_noop("snapshot_stale", snapshot_id=snapshot.snapshot_id)
    if (
        source_decision is None
        or source_decision.decision_id != snapshot_source.decision_id
        or source_decision.previous_model_version != target_version
    ):
        return _automatic_rollback_noop("source_decision_changed", snapshot_id=snapshot.snapshot_id)
    if not await _was_previously_activated(session, model_version=target.model_version):
        return _automatic_rollback_blocked("previous_target_not_previously_activated", snapshot_id=snapshot.snapshot_id)

    metrics = _loads(target.metrics_json)
    locked_target_hash = target.artifact_hash.lower()
    locked_target_uri = target.artifact_uri
    locked_target_metrics = _metrics_fingerprint(metrics)
    try:
        verified_hash = _verify_artifact_hash(
            target.artifact_uri,
            target.artifact_hash,
            require_deployable=True,
        )
        if verified_hash.lower() != locked_target_hash:
            return _automatic_rollback_blocked("previous_target_hash_invalid", snapshot_id=snapshot.snapshot_id)
        await _verify_persisted_evaluation_evidence(
            session,
            metrics=metrics,
            model_version=target.model_version,
            artifact_hash=locked_target_hash,
        )
        approver_ids = await _active_model_approval_ids(
            session,
            model_version=target.model_version,
            artifact_hash=locked_target_hash,
            metrics_fingerprint=locked_target_metrics,
            lock=True,
        )
    except AppException:
        return _automatic_rollback_blocked("previous_target_verification_failed", snapshot_id=snapshot.snapshot_id)
    if len({int(value) for value in approver_ids if int(value) > 0}) < 2:
        return _automatic_rollback_blocked("previous_target_approvals_invalid", snapshot_id=snapshot.snapshot_id)
    decision = evaluate_account_model_activation_gates(
        metrics,
        approver_ids=approver_ids,
        model_version=target.model_version,
        artifact_hash=locked_target_hash,
    )
    if not decision["activation_allowed"]:
        return _automatic_rollback_blocked("previous_target_gates_invalid", snapshot_id=snapshot.snapshot_id)

    # Row locks prevent concurrent pointer mutation; compare every bound identity
    # immediately before moving the pointer so stale state cannot be repurposed.
    if (
        not _snapshot_matches_active_pointer(snapshot, pointer=pointer, current=current)
        or source_decision.model_version != current.model_version
        or int(source_decision.pointer_revision) != int(pointer.pointer_revision)
        or source_decision.previous_model_version != target.model_version
        or target.status not in {"active", "retired"}
        or target.artifact_hash.lower() != locked_target_hash
        or target.artifact_uri != locked_target_uri
        or _metrics_fingerprint(_loads(target.metrics_json)) != locked_target_metrics
        or _verify_artifact_hash(target.artifact_uri, target.artifact_hash, require_deployable=True).lower()
        != locked_target_hash
    ):
        return _automatic_rollback_noop("rollback_identity_changed", snapshot_id=snapshot.snapshot_id)

    previous_version = current.model_version
    revision = int(pointer.pointer_revision) + 1
    payload = {
        "triggering_snapshot_id": snapshot.snapshot_id,
        "reason_category": eligibility,
        "source_model_version": previous_version,
        "source_pointer_revision": int(pointer.pointer_revision),
        "target_model_version": target.model_version,
        "target_artifact_hash": locked_target_hash,
        "approver_ids": approver_ids,
        "decision": decision,
        "pointer_revision": revision,
    }
    current.status = "retired"
    target.status = "active"
    pointer.model_version = target.model_version
    pointer.pointer_revision = revision
    pointer.activation_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    pointer.activated_by = 0
    decision_record = AccountModelGovernanceDecision(
        decision_id=f"account-model-decision-{uuid4().hex[:16]}",
        family=_MODEL_FAMILY,
        model_version=target.model_version,
        previous_model_version=previous_version,
        pointer_revision=revision,
        decision_type="automatic_rollback",
        decision_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        decided_by=0,
    )
    session.add(decision_record)
    await session.flush()
    return {
        "status": "rolled_back",
        "snapshot_id": snapshot.snapshot_id,
        "decision_id": decision_record.decision_id,
        "reason_category": eligibility,
        "model_version": target.model_version,
        "previous_model_version": previous_version,
        "pointer_revision": revision,
    }


async def _source_decision_for_pointer_identity(
    session: AsyncSession,
    *,
    family: str,
    model_version: str,
    pointer_revision: int,
    lock: bool,
) -> AccountModelGovernanceDecision | None:
    statement = select(AccountModelGovernanceDecision).where(
        AccountModelGovernanceDecision.family == family,
        AccountModelGovernanceDecision.model_version == model_version,
        AccountModelGovernanceDecision.pointer_revision == int(pointer_revision),
    )
    if lock:
        statement = statement.with_for_update()
    return (await session.execute(statement)).scalar_one_or_none()


def _snapshot_matches_active_pointer(
    snapshot: AccountMonitorSnapshot,
    *,
    pointer: AccountDetectionModelActivation,
    current: AccountDetectionModelVersion,
) -> bool:
    metrics = _loads(snapshot.metrics_json)
    identity = metrics.get("model_identity")
    if not isinstance(identity, dict):
        return False
    expected = {
        "family": _MODEL_FAMILY,
        "model_version": str(pointer.model_version),
        "artifact_hash": str(current.artifact_hash).lower(),
        "pointer_revision": int(pointer.pointer_revision),
    }
    return bool(
        snapshot.family == expected["family"]
        and snapshot.model_version == expected["model_version"]
        and int(snapshot.pointer_revision) == expected["pointer_revision"]
        and str(identity.get("family") or "") == expected["family"]
        and str(identity.get("model_version") or "") == expected["model_version"]
        and str(identity.get("artifact_hash") or "").lower() == expected["artifact_hash"]
        and int(identity.get("pointer_revision") or 0) == expected["pointer_revision"]
    )


async def _automatic_rollback_decision_for_snapshot(
    session: AsyncSession,
    snapshot_id: str,
) -> AccountModelGovernanceDecision | None:
    rows = (
        await session.execute(
            select(AccountModelGovernanceDecision)
            .with_for_update()
            .where(
                AccountModelGovernanceDecision.family == _MODEL_FAMILY,
                AccountModelGovernanceDecision.decision_type == "automatic_rollback",
            )
        )
    ).scalars().all()
    for row in rows:
        payload = _loads(row.decision_json)
        if payload.get("triggering_snapshot_id") == snapshot_id:
            return row
    return None


async def _automatic_rollback_eligibility(
    session: AsyncSession,
    *,
    snapshot: AccountMonitorSnapshot,
) -> str | None:
    metrics = _loads(snapshot.metrics_json)
    if snapshot.status != "hard_failure" or metrics.get("automatic_rollback_allowed") is not True:
        return None
    reason_counts = metrics.get("hard_error_reason_counts")
    if isinstance(reason_counts, dict):
        for reason in _AUTOMATIC_ROLLBACK_IMMEDIATE_REASONS:
            count = reason_counts.get(reason)
            if not isinstance(count, bool):
                try:
                    if int(count) > 0:
                        return reason
                except (TypeError, ValueError):
                    continue
    if snapshot.id is None:
        return None
    prior = (
        await session.execute(
            select(AccountMonitorSnapshot)
            .where(
                AccountMonitorSnapshot.family == snapshot.family,
                AccountMonitorSnapshot.id < int(snapshot.id),
            )
            .order_by(AccountMonitorSnapshot.id.desc())
            .limit(1)
        )
    ).scalars().all()
    if not prior:
        return None
    prior_metrics = _loads(prior[0].metrics_json)
    if (
        _snapshot_identity(prior[0]) != _snapshot_identity(snapshot)
        or prior[0].status != "hard_failure"
        or prior_metrics.get("automatic_rollback_allowed") is not True
    ):
        return None
    return "sustained_hard_error_budget"


def _snapshot_identity(snapshot: AccountMonitorSnapshot) -> tuple[str, str, str, int] | None:
    metrics = _loads(snapshot.metrics_json)
    identity = metrics.get("model_identity")
    if not isinstance(identity, dict):
        return None
    family = str(identity.get("family") or "")
    model_version = str(identity.get("model_version") or "")
    artifact_hash = str(identity.get("artifact_hash") or "").lower()
    pointer_revision = identity.get("pointer_revision")
    if (
        family != snapshot.family
        or model_version != snapshot.model_version
        or not artifact_hash
        or isinstance(pointer_revision, bool)
    ):
        return None
    try:
        revision = int(pointer_revision)
    except (TypeError, ValueError):
        return None
    if revision != int(snapshot.pointer_revision):
        return None
    return family, model_version, artifact_hash, revision


async def _was_previously_activated(session: AsyncSession, *, model_version: str) -> bool:
    decisions = (
        await session.execute(
            select(AccountModelGovernanceDecision)
            .with_for_update()
            .where(
                AccountModelGovernanceDecision.family == _MODEL_FAMILY,
                AccountModelGovernanceDecision.model_version == model_version,
                AccountModelGovernanceDecision.decision_type.in_(("activation", "rollback", "automatic_rollback")),
            )
        )
    ).scalars().all()
    return bool(decisions)


def _automatic_rollback_noop(reason: str, *, snapshot_id: str | None = None) -> dict[str, Any]:
    result = {"status": "no_op", "reason": reason}
    if snapshot_id:
        result["snapshot_id"] = snapshot_id
    return result


def _automatic_rollback_blocked(reason: str, *, snapshot_id: str) -> dict[str, Any]:
    return {"status": "blocked", "reason": reason, "snapshot_id": snapshot_id}


def _verify_artifact_hash(
    artifact_uri: str,
    expected_hash: str,
    *,
    require_deployable: bool = False,
) -> str:
    if not artifact_uri:
        raise AppException(code=400, msg="Account model artifact_uri is required.")
    if not expected_hash:
        raise AppException(code=400, msg="Account model artifact_hash is required.")
    path = Path(artifact_uri)
    if require_deployable and not path.is_dir():
        raise AppException(code=409, msg="Activation requires a deployable account model bundle.")
    if path.is_dir():
        if require_deployable:
            load_deployable_bundle_manifest(path)
        else:
            verify_bundle_files(path)
        path = resolve_bundle_component(path, "detector")
    if not path.is_file():
        raise AppException(code=404, msg="Account model artifact file not found.")
    actual = file_sha256(path)
    expected = expected_hash.strip().split()[0].lower()
    if actual.lower() != expected:
        raise AppException(code=409, msg="Account model artifact_hash does not match artifact bytes.")
    return actual




async def _require_active_admin(session: AsyncSession, user_id: int) -> None:
    row = (
        await session.execute(
            select(User.id).where(
                User.id == int(user_id),
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise AppException(code=403, msg="Account model governance requires an active administrator.")


def _require_recorded_approvals(
    approver_ids: list[int],
    operator_id: int,
) -> None:
    distinct = {int(value) for value in approver_ids if int(value) > 0}
    if int(operator_id) not in distinct:
        raise AppException(code=403, msg="The activating administrator must be present in the recorded approval records.")
    if len(distinct) < 2:
        raise AppException(code=403, msg="Account model activation requires two distinct active administrator approval records.")


async def _active_model_approval_ids(
    session: AsyncSession,
    *,
    model_version: str,
    artifact_hash: str | None = None,
    metrics_fingerprint: str | None = None,
    lock: bool = False,
) -> list[int]:
    statement = (
        select(AccountDetectionModelApproval.approver_id)
        .join(User, User.id == AccountDetectionModelApproval.approver_id)
        .where(
            AccountDetectionModelApproval.model_version == model_version,
            User.role == "admin",
            User.is_active.is_(True),
        )
    )
    if lock:
        statement = statement.with_for_update()
    rows = (await session.execute(statement)).scalars().all()
    if artifact_hash is not None or metrics_fingerprint is not None:
        approval_statement = select(AccountDetectionModelApproval).where(
            AccountDetectionModelApproval.model_version == model_version
        )
        if lock:
            approval_statement = approval_statement.with_for_update()
        approvals = (await session.execute(approval_statement)).scalars().all()
        permitted = {
            int(approval.approver_id)
            for approval in approvals
            if (artifact_hash is None or approval.artifact_hash.lower() == artifact_hash.lower())
            and (metrics_fingerprint is None or approval.metrics_fingerprint == metrics_fingerprint)
        }
        rows = [user_id for user_id in rows if int(user_id) in permitted]
    return sorted({int(value) for value in rows})


async def _approval_count(session: AsyncSession, *, model_version: str) -> int:
    return len(await _active_model_approval_ids(session, model_version=model_version))


def _metrics_fingerprint(metrics: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(metrics, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _registration_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Keep training metadata while reserving operational gates for evaluators."""

    return {key: value for key, value in metrics.items() if key not in _EVALUATOR_OWNED_METRIC_KEYS}


def _prepare_evaluation_evidence(
    *,
    model_version: str,
    artifact_hash: str,
    evaluation_run_id: str,
    prediction_audits: list[dict[str, Any]],
    evaluation_protocol: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_model_version = model_version.strip()
    normalized_artifact_hash = artifact_hash.strip().split()[0].lower()
    normalized_run_id = evaluation_run_id.strip()
    if not normalized_model_version or not normalized_run_id:
        raise AppException(code=400, msg="Evaluator writeback requires model_version and evaluation_run_id.")
    if len(normalized_artifact_hash) != 64 or any(
        character not in "0123456789abcdef" for character in normalized_artifact_hash
    ):
        raise AppException(code=400, msg="Evaluator writeback requires a SHA-256 artifact_hash.")
    if evaluation_protocol is not None and not _is_persisted_evaluation_protocol(evaluation_protocol):
        raise AppException(code=400, msg="Evaluator writeback evaluation_protocol is not a valid persisted report.")

    prepared_by_id: dict[str, dict[str, Any]] = {}
    for raw_audit in prediction_audits:
        audit = _normalize_evaluation_audit(raw_audit)
        audit_id = "account-shadow-audit-" + _canonical_digest(
            (normalized_model_version, normalized_artifact_hash, normalized_run_id, audit)
        )[:32]
        prepared_by_id[audit_id] = {"audit_id": audit_id, "audit": audit}
    audit_ids = sorted(prepared_by_id)
    audit_fingerprint = _canonical_digest(audit_ids)
    protocol_fingerprint = _canonical_digest(evaluation_protocol) if evaluation_protocol is not None else None
    evaluation_fingerprint = _canonical_digest(
        {
            "schema": _EVALUATION_MANIFEST_SCHEMA,
            "model_family": _MODEL_FAMILY,
            "model_version": normalized_model_version,
            "artifact_hash": normalized_artifact_hash,
            "evaluation_run_id": normalized_run_id,
            "audit_fingerprint": audit_fingerprint,
            "evaluation_protocol_fingerprint": protocol_fingerprint,
        }
    )
    return {
        "model_version": normalized_model_version,
        "artifact_hash": normalized_artifact_hash,
        "evaluation_run_id": normalized_run_id,
        "audits": [prepared_by_id[audit_id] for audit_id in audit_ids],
        "audit_fingerprint": audit_fingerprint,
        "evaluation_protocol_fingerprint": protocol_fingerprint,
        "evaluation_fingerprint": evaluation_fingerprint,
    }


def _evaluation_manifest_body(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": _EVALUATION_MANIFEST_SCHEMA,
        "signature_algorithm": "hmac-sha256",
        "model_family": _MODEL_FAMILY,
        "model_version": evidence["model_version"],
        "artifact_hash": evidence["artifact_hash"],
        "evaluation_run_id": evidence["evaluation_run_id"],
        "audit_fingerprint": evidence["audit_fingerprint"],
        "evaluation_protocol_fingerprint": evidence["evaluation_protocol_fingerprint"],
        "evaluation_fingerprint": evidence["evaluation_fingerprint"],
    }


def _verify_evaluation_manifest(
    evidence: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
) -> None:
    if not isinstance(manifest, Mapping):
        raise AppException(code=403, msg="Evaluator writeback requires a signed evaluator manifest.")
    expected_body = _evaluation_manifest_body(evidence)
    expected_keys = {*expected_body, "signature_sha256"}
    if set(manifest) != expected_keys or any(manifest.get(key) != value for key, value in expected_body.items()):
        raise AppException(code=403, msg="Evaluator manifest does not match the submitted evaluation evidence.")
    supplied_signature = str(manifest.get("signature_sha256") or "").lower()
    expected_signature = hmac.new(
        _evaluation_hmac_secret(None),
        _canonical_json(expected_body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise AppException(code=403, msg="Evaluator manifest signature verification failed.")


def _evaluation_hmac_secret(value: str | None) -> bytes:
    secret = settings.ACCOUNT_MODEL_EVALUATION_HMAC_SECRET if value is None else value
    normalized = secret.strip()
    if not normalized:
        raise AppException(code=503, msg="Account model evaluator signing secret is not configured.")
    return normalized.encode("utf-8")


async def _verify_persisted_evaluation_evidence(
    session: AsyncSession,
    *,
    metrics: dict[str, Any],
    model_version: str,
    artifact_hash: str,
) -> None:
    shadow = metrics.get("shadow_evaluation")
    if not isinstance(shadow, dict):
        raise AppException(code=409, msg="Account model activation requires persisted evaluator evidence.")
    evaluation_run_id = str(shadow.get("evaluation_run_id") or "")
    evaluation_fingerprint = str(shadow.get("evaluation_fingerprint") or "")
    audit_fingerprint = str(shadow.get("audit_fingerprint") or "")
    row = (
        await session.execute(
            select(AccountModelEvaluationRun)
            .with_for_update()
            .where(AccountModelEvaluationRun.evaluation_run_id == evaluation_run_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise AppException(code=409, msg="Account model activation requires persisted signed evaluator evidence.")
    protocol = metrics.get("evaluation_protocol")
    protocol_fingerprint = _canonical_digest(protocol) if isinstance(protocol, dict) else None
    if (
        row.family != _MODEL_FAMILY
        or row.model_version != model_version
        or row.artifact_hash.lower() != artifact_hash.lower()
        or row.evaluation_fingerprint != evaluation_fingerprint
        or row.audit_fingerprint != audit_fingerprint
    ):
        raise AppException(code=409, msg="Persisted evaluator evidence does not match the activation candidate.")
    expected_fingerprint = _canonical_digest(
        {
            "schema": _EVALUATION_MANIFEST_SCHEMA,
            "model_family": _MODEL_FAMILY,
            "model_version": model_version,
            "artifact_hash": artifact_hash.lower(),
            "evaluation_run_id": evaluation_run_id,
            "audit_fingerprint": audit_fingerprint,
            "evaluation_protocol_fingerprint": protocol_fingerprint,
        }
    )
    if expected_fingerprint != evaluation_fingerprint:
        raise AppException(code=409, msg="Persisted evaluator fingerprint does not bind the activation candidate.")
    expected_body = {
        "schema": _EVALUATION_MANIFEST_SCHEMA,
        "signature_algorithm": "hmac-sha256",
        "model_family": _MODEL_FAMILY,
        "model_version": model_version,
        "artifact_hash": artifact_hash.lower(),
        "evaluation_run_id": evaluation_run_id,
        "audit_fingerprint": audit_fingerprint,
        "evaluation_protocol_fingerprint": protocol_fingerprint,
        "evaluation_fingerprint": evaluation_fingerprint,
    }
    _verify_persisted_evaluation_manifest(_loads(row.manifest_json), expected_body)
    audits = await _evaluation_audits(
        session,
        model_version=model_version,
        artifact_hash=artifact_hash,
        evaluation_run_id=evaluation_run_id,
    )
    normalized_audits: list[dict[str, Any]] = []
    for audit in audits:
        payload = _loads(audit.prediction_json)
        identity = payload.get("model_identity")
        if not isinstance(identity, dict) or identity != {
            "family": _MODEL_FAMILY,
            "model_version": model_version,
            "artifact_hash": artifact_hash.lower(),
            "evaluation_run_id": evaluation_run_id,
        }:
            raise AppException(code=409, msg="Persisted evaluator audit identity does not match the activation candidate.")
        normalized = _normalize_evaluation_audit(payload)
        expected_audit_id = "account-shadow-audit-" + _canonical_digest(
            (model_version, artifact_hash.lower(), evaluation_run_id, normalized)
        )[:32]
        if audit.audit_id != expected_audit_id:
            raise AppException(code=409, msg="Persisted evaluator audit fingerprint is invalid.")
        normalized_audits.append(normalized)
    if _canonical_digest(sorted(audit.audit_id for audit in audits)) != audit_fingerprint:
        raise AppException(code=409, msg="Persisted evaluator audits do not match the signed evidence.")
    summary = summarize_account_predictions(normalized_audits)
    if _canonical_json(summary) != _canonical_json(shadow.get("summary")):
        raise AppException(code=409, msg="Persisted evaluator summary does not match signed audit evidence.")
    if not _trusted_calibration_gate(
        metrics,
        model_version=model_version,
        artifact_hash=artifact_hash,
        max_ece=0.05,
    ):
        raise AppException(code=409, msg="Persisted evaluator calibration evidence is missing or invalid.")


def _verify_persisted_evaluation_manifest(manifest: Any, expected_body: Mapping[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise AppException(code=409, msg="Persisted evaluator manifest is invalid.")
    expected_keys = {*expected_body, "signature_sha256"}
    if set(manifest) != expected_keys or any(manifest.get(key) != value for key, value in expected_body.items()):
        raise AppException(code=409, msg="Persisted evaluator manifest does not match signed evidence.")
    supplied_signature = str(manifest.get("signature_sha256") or "").lower()
    expected_signature = hmac.new(
        _evaluation_hmac_secret(None),
        _canonical_json(expected_body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise AppException(code=409, msg="Persisted evaluator manifest signature verification failed.")


def _trusted_calibration_gate(
    metrics: Mapping[str, Any],
    *,
    model_version: str | None,
    artifact_hash: str | None,
    max_ece: float,
) -> bool:
    shadow = metrics.get("shadow_evaluation")
    if not isinstance(shadow, dict):
        return False
    calibration = shadow.get("calibration")
    summary = shadow.get("summary")
    if not isinstance(calibration, dict) or not isinstance(summary, dict):
        return False
    if calibration.get("source") != "signed_evaluator_audit":
        return False
    evaluation_fingerprint = str(shadow.get("evaluation_fingerprint") or "")
    if not evaluation_fingerprint or calibration.get("evaluation_fingerprint") != evaluation_fingerprint:
        return False
    if model_version is not None and shadow.get("model_version") != model_version:
        return False
    if artifact_hash is not None and str(shadow.get("artifact_hash") or "").lower() != artifact_hash.lower():
        return False
    ece = summary.get("ece")
    if isinstance(ece, bool) or not isinstance(ece, (int, float)) or not math.isfinite(float(ece)):
        return False
    if calibration.get("ece") != ece or int(summary.get("labeled_prediction_count", 0)) <= 0:
        return False
    return 0.0 <= float(ece) <= max_ece


def _shadow_evaluation_gates(
    value: Any,
    *,
    model_version: str | None,
    artifact_hash: str | None,
) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {"shadow_run": False, "false_positive_burden": False}
    summary = value.get("summary")
    if not isinstance(summary, dict):
        return {"shadow_run": False, "false_positive_burden": False}
    identity_matches = bool(
        value.get("evaluation_run_id")
        and value.get("audit_fingerprint")
        and value.get("evaluation_fingerprint")
        and value.get("monitor_snapshot_id")
    )
    if model_version is not None:
        identity_matches = identity_matches and value.get("model_version") == model_version
    if artifact_hash is not None:
        identity_matches = identity_matches and str(value.get("artifact_hash", "")).lower() == artifact_hash.lower()
    prediction_count = int(summary.get("prediction_count", 0))
    thresholds = summary.get("thresholds") if isinstance(summary.get("thresholds"), dict) else {}
    within_false_positive_budget = int(summary.get("estimated_daily_false_positives", 1)) <= int(
        thresholds.get("daily_review_capacity", 0)
    )
    return {
        "shadow_run": identity_matches and prediction_count > 0 and summary.get("status") == "healthy",
        "false_positive_burden": identity_matches and prediction_count > 0 and within_false_positive_budget,
    }


def _normalize_evaluation_audit(value: dict[str, Any]) -> dict[str, Any]:
    account_id = str(value.get("account_id") or "").strip()
    platform = str(value.get("platform") or "").strip()
    input_fingerprint = str(value.get("input_fingerprint") or "").strip().lower()
    if not account_id or not platform or len(input_fingerprint) != 64:
        raise AppException(code=400, msg="Evaluator audit requires account_id, platform, and a SHA-256 input_fingerprint.")
    try:
        probability = float(value.get("probability"))
        latency_ms = float(value.get("latency_ms", 0.0))
    except (TypeError, ValueError) as error:
        raise AppException(code=400, msg="Evaluator audit probability and latency_ms must be numeric.") from error
    if not 0.0 <= probability <= 1.0 or latency_ms < 0:
        raise AppException(code=400, msg="Evaluator audit probability or latency_ms is out of range.")
    target = value.get("target")
    return {
        "account_id": account_id,
        "platform": platform,
        "input_fingerprint": input_fingerprint,
        "probability": probability,
        "target": int(target) if target in {0, 1, False, True} else None,
        "abstained": bool(value.get("abstained", False)),
        "latency_ms": latency_ms,
        "hard_error": bool(value.get("hard_error", False)),
    }


async def _evaluation_audits(
    session: AsyncSession,
    *,
    model_version: str,
    artifact_hash: str,
    evaluation_run_id: str,
) -> list[AccountPredictionAudit]:
    rows = (
        await session.execute(
            select(AccountPredictionAudit).where(
                AccountPredictionAudit.family == _MODEL_FAMILY,
                AccountPredictionAudit.model_version == model_version,
                AccountPredictionAudit.pointer_revision == 0,
            )
        )
    ).scalars().all()
    result: list[AccountPredictionAudit] = []
    for row in rows:
        identity = _loads(row.prediction_json).get("model_identity")
        if not isinstance(identity, dict):
            continue
        if (
            identity.get("model_version") == model_version
            and str(identity.get("artifact_hash", "")).lower() == artifact_hash.lower()
            and identity.get("evaluation_run_id") == evaluation_run_id
        ):
            result.append(row)
    return result


def _evaluation_prediction_rows(audits: list[AccountPredictionAudit]) -> list[dict[str, Any]]:
    return [_loads(audit.prediction_json) for audit in audits]


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _approval_projection(record: AccountDetectionModelApproval) -> dict[str, Any]:
    return {
        "approval_id": record.approval_id,
        "model_version": record.model_version,
        "approver_id": record.approver_id,
        "artifact_hash": record.artifact_hash,
        "metrics_fingerprint": record.metrics_fingerprint,
        "approval_notes": record.approval_notes,
    }


def _model_projection(record: AccountDetectionModelVersion) -> dict[str, Any]:
    return {
        "model_version": record.model_version,
        "dataset_version_id": record.dataset_version_id,
        "encoder_version": record.encoder_version,
        "encoder_artifact_hash": record.encoder_artifact_hash,
        "artifact_uri": record.artifact_uri,
        "artifact_hash": record.artifact_hash,
        "metrics": _loads(record.metrics_json),
        "gates": _loads(record.gates_json),
        "status": record.status,
    }


def _encoder_projection(record: ChineseSocialEncoderVersion) -> dict[str, Any]:
    return {
        "encoder_version": record.encoder_version,
        "corpus_version_id": record.corpus_version_id,
        "training_run_id": record.training_run_id,
        "artifact_uri": record.artifact_uri,
        "artifact_hash": record.artifact_hash,
        "base_model_identity": record.base_model_identity,
        "manifest": _loads(record.manifest_json),
        "status": record.status,
    }


def _normalize_encoder_binding(
    encoder_version: str | None,
    encoder_artifact_hash: str | None,
    *,
    required: bool = False,
) -> tuple[str | None, str | None]:
    normalized_version = str(encoder_version or "").strip()
    normalized_hash = str(encoder_artifact_hash or "").strip().lower()
    if not normalized_version and not normalized_hash and not required:
        return None, None
    if not normalized_version or len(normalized_hash) != 64 or any(
        character not in "0123456789abcdef" for character in normalized_hash
    ):
        raise AppException(
            code=409,
            msg="Governed detector candidate requires encoder_version and a SHA-256 encoder_artifact_hash.",
        )
    return normalized_version, normalized_hash


def _loads(payload: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {}


def _is_persisted_evaluation_protocol(value: Any) -> bool:
    """Validate the cryptographically self-describing protocol report.

    The API may persist a JSON representation, so the research package's
    runtime-only marker is unavailable here. Its persisted validator still
    checks the report digest and all record-derived audit fields; flat caller
    booleans and hand-written partial reports therefore fail closed.
    """

    if not isinstance(value, dict):
        return False
    try:
        package = _load_evaluation_package()
        return bool(package.is_protocol_report_payload(value))
    except (ImportError, OSError, AttributeError, TypeError, ValueError):
        return False


def _load_evaluation_package() -> Any:
    existing = sys.modules.get(_EVALUATION_PACKAGE_NAME)
    if existing is not None:
        return existing
    package_dir = Path(__file__).resolve().parents[3] / "research" / "social_bot_detection"
    init_file = package_dir / "__init__.py"
    if not init_file.is_file():
        raise ImportError(f"internal account-evaluation package not found: {init_file}")
    spec = importlib.util.spec_from_file_location(
        _EVALUATION_PACKAGE_NAME,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load internal account-evaluation package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_EVALUATION_PACKAGE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(_EVALUATION_PACKAGE_NAME) is module:
            sys.modules.pop(_EVALUATION_PACKAGE_NAME, None)
        raise
    return module
