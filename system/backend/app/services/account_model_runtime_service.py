"""Resolve and bootstrap the database-controlled account detector pointer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import resolve_project_path, settings
from app.core.account_model_artifact import (
    file_sha256,
    load_deployable_bundle_manifest,
    resolve_bundle_component,
    verify_bundle_files,
)
from app.db.mysql import async_session_factory, close_mysql
from app.models.account_labeling import (
    AccountDetectionModelActivation,
    AccountDetectionModelVersion,
    AccountModelGovernanceDecision,
)
from app.utils.exceptions import AppException
from app.utils.logger import logger

__all__ = [
    "ActiveAccountModel",
    "ActiveAccountModelResolution",
    "get_active_account_model",
    "get_active_account_model_resolution",
    "resolve_active_account_model",
    "resolve_active_account_model_resolution",
]


@dataclass(frozen=True, slots=True)
class ActiveAccountModel:
    model_version: str
    artifact_uri: str
    artifact_hash: str
    data_fingerprint: str
    pointer_revision: int
    source_schema: str
    governance_status: str = "governed_active"
    research_approved: bool = True

    @property
    def checkpoint_path(self) -> str:
        return str(_checkpoint_path(self.artifact_uri))

    @property
    def encoder_path(self) -> str | None:
        return _bundle_component_path(self.artifact_uri, "encoder")

    @property
    def feature_schema_path(self) -> str | None:
        return _bundle_component_path(self.artifact_uri, "feature_schema")

    @property
    def calibration_path(self) -> str | None:
        return _bundle_component_path(self.artifact_uri, "calibration")


@dataclass(frozen=True, slots=True)
class ActiveAccountModelResolution:
    """Pointer resolution result that preserves invalid model identity for audit."""

    status: str
    model: ActiveAccountModel | None = None
    model_version: str = ""
    artifact_hash: str = ""
    pointer_revision: int = 0
    reason: str = ""
    detail: str = ""


async def get_active_account_model() -> ActiveAccountModel | None:
    """Resolve the active pointer for request paths without leaking sessions."""

    resolution = await get_active_account_model_resolution()
    return resolution.model if resolution.status == "available" else None


async def get_active_account_model_resolution() -> ActiveAccountModelResolution:
    """Resolve an active pointer without conflating missing and invalid state."""

    try:
        async with async_session_factory() as session:
            resolution = await resolve_active_account_model_resolution(session)
            await session.commit()
            return resolution
    except (ImportError, SQLAlchemyError, RuntimeError, OSError) as error:
        try:
            await close_mysql()
        except Exception:
            logger.debug("Failed to clear account model pointer database pool", exc_info=True)
        logger.warning("Account model pointer is unavailable: {}", error)
        return ActiveAccountModelResolution(
            status="invalid",
            reason="active_pointer_store_unavailable",
            detail=str(error),
        )
    except AppException as error:
        logger.warning("Account model pointer failed closed: {}", error.msg)
        return ActiveAccountModelResolution(
            status="invalid",
            reason="active_pointer_resolution_failed",
            detail=error.msg,
        )


async def resolve_active_account_model(session) -> ActiveAccountModel | None:
    """Compatibility interface that raises when a persisted pointer is invalid."""

    resolution = await resolve_active_account_model_resolution(session)
    if resolution.status == "invalid":
        raise AppException(code=409, msg=resolution.detail or "Account model active pointer is invalid.")
    return resolution.model


async def resolve_active_account_model_resolution(session) -> ActiveAccountModelResolution:
    """Resolve a pointer into available, missing, or identity-preserving invalid state."""

    activation = (
        await session.execute(
            select(AccountDetectionModelActivation).where(
                AccountDetectionModelActivation.model_family == "chinese_account_detection"
            )
        )
    ).scalar_one_or_none()
    if activation is None:
        model = await _bootstrap_pointer(session)
        return _available_resolution(model) if model is not None else ActiveAccountModelResolution(status="missing")
    model = (
        await session.execute(
            select(AccountDetectionModelVersion).where(
                AccountDetectionModelVersion.model_version == activation.model_version
            )
        )
    ).scalar_one_or_none()
    if model is None:
        return ActiveAccountModelResolution(
            status="invalid",
            model_version=str(activation.model_version),
            pointer_revision=int(activation.pointer_revision),
            reason="active_model_version_missing",
            detail="Account model active pointer references a missing model version.",
        )
    try:
        active_model = _materialize_active_account_model(activation, model)
    except (AppException, OSError, RuntimeError, ValueError) as error:
        detail = error.msg if isinstance(error, AppException) else str(error)
        return ActiveAccountModelResolution(
            status="invalid",
            model_version=str(model.model_version),
            artifact_hash=str(model.artifact_hash or ""),
            pointer_revision=int(activation.pointer_revision),
            reason="active_model_bundle_invalid",
            detail=detail,
        )
    return _available_resolution(active_model)


def _materialize_active_account_model(
    activation: AccountDetectionModelActivation,
    model: AccountDetectionModelVersion,
) -> ActiveAccountModel:
    metrics = _loads(model.metrics_json)
    activation_payload = _loads(activation.activation_json)
    is_local_bootstrap = bool(
        activation_payload.get("bootstrap")
        or metrics.get("bootstrap")
        or model.status == "local_bootstrap"
    )
    if is_local_bootstrap and settings.BACKEND_ENV.strip().lower() == "production":
        raise AppException(code=409, msg="Production cannot use a persisted local bootstrap account model pointer.")
    if is_local_bootstrap and not settings.account_model_local_bootstrap_allowed:
        raise AppException(code=409, msg="The persisted local bootstrap account model pointer is disabled.")

    artifact_path = Path(model.artifact_uri).expanduser().resolve()
    if is_local_bootstrap:
        bundle_manifest = None
    else:
        if not artifact_path.is_dir() or not (artifact_path / "manifest.json").is_file():
            raise AppException(code=409, msg="Governed runtime requires a deployable account model bundle.")
        bundle_manifest = load_deployable_bundle_manifest(artifact_path)
    checkpoint = _checkpoint_path(model.artifact_uri)
    actual_hash = _file_sha256(checkpoint)
    if actual_hash != model.artifact_hash.lower():
        raise AppException(code=409, msg="Active account model artifact hash verification failed.")
    return ActiveAccountModel(
        model_version=model.model_version,
        artifact_uri=str(model.artifact_uri),
        artifact_hash=actual_hash,
        data_fingerprint=str(metrics.get("data_fingerprint") or metrics.get("dataset_fingerprint") or ""),
        pointer_revision=int(activation.pointer_revision),
        source_schema=str(
            metrics.get("schema") or metrics.get("source_schema") or ""
            if is_local_bootstrap
            else (bundle_manifest or {}).get("source_schema") or ""
        ),
        governance_status="local_bootstrap_unreviewed" if is_local_bootstrap else "governed_active",
        research_approved=not is_local_bootstrap,
    )


def _available_resolution(model: ActiveAccountModel) -> ActiveAccountModelResolution:
    return ActiveAccountModelResolution(
        status="available",
        model=model,
        model_version=model.model_version,
        artifact_hash=model.artifact_hash,
        pointer_revision=model.pointer_revision,
    )


async def _bootstrap_pointer(session) -> ActiveAccountModel | None:
    if not settings.account_model_local_bootstrap_allowed:
        return None
    checkpoint = resolve_project_path(settings.BOTRHG_CHECKPOINT_PATH)
    if not checkpoint.is_file():
        return None
    artifact_hash = _file_sha256(checkpoint)
    model_version = f"bootstrap-{artifact_hash[:16]}"
    model = (
        await session.execute(
            select(AccountDetectionModelVersion).where(AccountDetectionModelVersion.model_version == model_version)
        )
    ).scalar_one_or_none()
    if model is None:
        model = AccountDetectionModelVersion(
            model_version=model_version,
            dataset_version_id="bootstrap",
            artifact_hash=artifact_hash,
            artifact_uri=str(checkpoint),
            metrics_json=json.dumps(
                {
                    "schema": "cogguard.botrhg.weibo.v1",
                    "source_schema": "cogguard.botrhg.weibo.v1",
                    "dataset_fingerprint": settings.BOTRHG_DATA_FINGERPRINT,
                    "bootstrap": True,
                    "governance_status": "local_bootstrap_unreviewed",
                    "research_approved": False,
                },
                ensure_ascii=False,
            ),
            gates_json=json.dumps(
                {
                    "deployment": "local_bootstrap_only",
                    "activation_allowed": False,
                    "research_approved": False,
                    "production_eligible": False,
                }
            ),
            status="local_bootstrap",
            created_by=0,
        )
        session.add(model)
        await session.flush()
    else:
        model.status = "local_bootstrap"
    bootstrap_decision = {
        "bootstrap": True,
        "source": "BOTRHG_CHECKPOINT_PATH",
        "governance_status": "local_bootstrap_unreviewed",
        "research_approved": False,
        "production_eligible": False,
    }
    activation = AccountDetectionModelActivation(
        model_family="chinese_account_detection",
        model_version=model.model_version,
        pointer_revision=1,
        activation_json=json.dumps(bootstrap_decision),
        activated_by=0,
    )
    session.add(activation)
    session.add(
        AccountModelGovernanceDecision(
            decision_id=f"account-model-decision-{uuid4().hex[:16]}",
            family="chinese_account_detection",
            model_version=model.model_version,
            previous_model_version=None,
            pointer_revision=1,
            decision_type="bootstrap",
            decision_json=json.dumps(bootstrap_decision),
            decided_by=0,
        )
    )
    await session.flush()
    return ActiveAccountModel(
        model_version=model.model_version,
        artifact_uri=str(model.artifact_uri),
        artifact_hash=artifact_hash,
        data_fingerprint=settings.BOTRHG_DATA_FINGERPRINT,
        pointer_revision=1,
        source_schema="cogguard.botrhg.weibo.v1",
        governance_status="local_bootstrap_unreviewed",
        research_approved=False,
    )


def _checkpoint_path(artifact_uri: str) -> Path:
    path = Path(artifact_uri).expanduser().resolve()
    if path.is_dir() and (path / "manifest.json").is_file():
        verify_bundle_files(path)
    checkpoint = resolve_bundle_component(path, "detector") if path.is_dir() else path
    if not checkpoint.is_file():
        raise AppException(code=404, msg="Active account model checkpoint is missing.")
    return checkpoint


def _bundle_component_path(artifact_uri: str, component: str) -> str | None:
    bundle_dir = Path(artifact_uri).expanduser().resolve()
    if not bundle_dir.is_dir() or not (bundle_dir / "manifest.json").is_file():
        return None
    verify_bundle_files(bundle_dir)
    path = resolve_bundle_component(bundle_dir, component)
    if not path.is_file():
        raise AppException(code=404, msg=f"Active account model {component} artifact is missing.")
    return str(path)


def _file_sha256(path: Path) -> str:
    return file_sha256(path)


def _loads(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
        return payload if isinstance(payload, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}
