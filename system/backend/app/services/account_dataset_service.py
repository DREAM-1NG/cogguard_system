"""Approved-corpus export service for Chinese account detection."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PROJECT_ROOT, resolve_project_path, settings
from app.models.account_labeling import (
    AccountBehaviorLabelRecord,
    AccountDetectionCaseRecord,
    AccountDetectionDatasetVersion,
    AccountFrozenHoldoutMembership,
    AccountTrainingExportMembership,
)
from app.core.account_labeling import account_scope_key
from app.utils.exceptions import AppException

__all__ = [
    "export_approved_account_dataset",
    "list_account_detection_datasets",
    "record_account_training_export_memberships",
]

_PACKAGE_NAME = "_cogguard_social_bot_detection_chinese_corpus"


async def export_approved_account_dataset(
    session: AsyncSession,
    *,
    dataset_version_id: str | None = None,
    corpus_version_id: str | None = None,
    output_dir: str | Path | None = None,
    operator_id: int,
) -> dict[str, Any]:
    """Export approved labels into a versioned corpus and register its manifest."""

    version_id = dataset_version_id or f"account-dataset-{uuid.uuid4().hex[:12]}"
    target_dir = _resolve_account_dataset_output_dir(output_dir, version_id)
    chinese_corpus = _load_chinese_corpus_module()
    holdout_exists = (
        await session.execute(select(AccountFrozenHoldoutMembership.id).limit(1))
    ).scalar_one_or_none()
    if holdout_exists is not None and not str(corpus_version_id or "").strip():
        raise AppException(
            code=400,
            msg="corpus_version_id is required when frozen holdout memberships exist.",
        )
    rows = await _approved_label_rows(session, corpus_version_id=str(corpus_version_id or "").strip())
    if not rows:
        raise AppException(
            code=400,
            msg="No approved or adjudicated account labels are available for export.",
        )
    output_path = target_dir / "approved_account_labels.jsonl"
    records = [
        chinese_corpus.ApprovedAccountLabel(
            case_id=str(label.case_id),
            account_id=account_scope_key(case.platform, case.account_id),
            source_account_id=str(case.account_id),
            platform=str(case.platform),
            event_id=str(case.event_id),
            text=str((case_payload.get("text") or "")),
            behavior_label=str(label.behavior_label),
            training_target=str(label.training_target),
            evidence_post_ids=_loads(label.evidence_post_ids_json, []),
            case_fingerprint=str(label.case_fingerprint or case.case_fingerprint),
            label_id=str(label.label_id),
            observed_at=_governed_observed_at(case_payload),
            community_id=_governed_community_id(case_payload),
            provenance={
                "label_status": label.label_status,
                "analyst_id": label.analyst_id,
                "adjudicated_by": label.adjudicated_by,
                "case_fingerprint": case.case_fingerprint,
                "source": "account_behavior_labels+account_detection_cases",
            },
        )
        for label, case, case_payload in rows
    ]
    manifest = chinese_corpus.export_approved_account_corpus(
        records,
        output_path,
        dataset_version_id=version_id,
    )
    manifest_payload = manifest.to_dict()
    await record_account_training_export_memberships(
        session,
        dataset_version_id=version_id,
        dataset_fingerprint=manifest.data_fingerprint,
        rows=rows,
    )
    manifest_path = target_dir / "dataset_manifest.json"
    dataset_card_path = target_dir / "dataset_card.md"
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    dataset_card_path.write_text(_dataset_card(manifest_payload), encoding="utf-8")

    record = AccountDetectionDatasetVersion(
        dataset_version_id=version_id,
        data_fingerprint=manifest.data_fingerprint,
        source_label_count=manifest.record_count,
        artifact_uri=str(target_dir),
        manifest_json=json.dumps(
            {
                **manifest_payload,
                "manifest_path": str(manifest_path),
                "dataset_card_path": str(dataset_card_path),
                "dataset_card_policy": "generated_datasheet_draft_requires_review_before_public_claims",
                "frozen_holdout_policy": "cases in account_frozen_holdout_memberships are excluded from training export",
                "corpus_version_id": str(corpus_version_id or "") or None,
            },
            ensure_ascii=False,
        ),
        status="candidate",
        created_by=operator_id,
    )
    session.add(record)
    await session.flush()
    return _dataset_projection(record)


async def record_account_training_export_memberships(
    session: AsyncSession,
    *,
    dataset_version_id: str,
    dataset_fingerprint: str,
    rows: list[tuple[AccountBehaviorLabelRecord, AccountDetectionCaseRecord, dict[str, Any]]],
) -> None:
    """Persist label-level training lineage with the same export transaction."""

    for label, case, _payload in rows:
        case_fingerprint = str(label.case_fingerprint or case.case_fingerprint)
        membership_fingerprint = _canonical_digest(
            {
                "dataset_version_id": str(dataset_version_id),
                "dataset_fingerprint": str(dataset_fingerprint),
                "case_id": str(case.case_id),
                "label_id": str(label.label_id),
                "case_fingerprint": case_fingerprint,
            }
        )
        session.add(
            AccountTrainingExportMembership(
                export_membership_id="account-training-export-" + membership_fingerprint[:32],
                dataset_version_id=str(dataset_version_id),
                case_id=str(case.case_id),
                label_id=str(label.label_id),
                case_fingerprint=case_fingerprint,
                export_fingerprint=membership_fingerprint,
            )
        )
    await session.flush()


async def list_account_detection_datasets(session: AsyncSession) -> list[dict[str, Any]]:
    """Return registered approved-corpus versions."""

    rows = (
        await session.execute(
            select(AccountDetectionDatasetVersion).order_by(
                AccountDetectionDatasetVersion.created_at.desc()
            )
        )
    ).scalars().all()
    return [_dataset_projection(row) for row in rows]


async def _approved_label_rows(
    session: AsyncSession,
    *,
    corpus_version_id: str = "",
) -> list[tuple[AccountBehaviorLabelRecord, AccountDetectionCaseRecord, dict[str, Any]]]:
    result = await session.execute(
        select(AccountBehaviorLabelRecord, AccountDetectionCaseRecord)
        .join(
            AccountDetectionCaseRecord,
            AccountDetectionCaseRecord.case_id == AccountBehaviorLabelRecord.case_id,
        )
        .where(AccountBehaviorLabelRecord.label_status.in_(("approved", "adjudicated")))
        .where(AccountBehaviorLabelRecord.behavior_label.in_(("bot", "human")))
        .where(AccountBehaviorLabelRecord.training_target.in_(("bot", "non_bot")))
        .where(AccountBehaviorLabelRecord.case_fingerprint == AccountDetectionCaseRecord.case_fingerprint)
        .where(
            True
            if not corpus_version_id
            else ~exists(
                select(1).where(
                    AccountFrozenHoldoutMembership.corpus_version_id == corpus_version_id,
                    (
                        (
                            AccountFrozenHoldoutMembership.account_id == AccountDetectionCaseRecord.account_id
                        )
                        & (
                            AccountFrozenHoldoutMembership.platform == AccountDetectionCaseRecord.platform
                        )
                        |
                        (
                            AccountFrozenHoldoutMembership.platform.is_(None)
                            & (AccountFrozenHoldoutMembership.case_id == AccountBehaviorLabelRecord.case_id)
                        )
                        | (
                            AccountFrozenHoldoutMembership.account_id.is_(None)
                            & (AccountFrozenHoldoutMembership.case_id == AccountBehaviorLabelRecord.case_id)
                        )
                    ),
                )
            )
        )
        .order_by(
            AccountDetectionCaseRecord.platform.asc(),
            AccountDetectionCaseRecord.event_id.asc(),
            AccountDetectionCaseRecord.account_id.asc(),
            AccountBehaviorLabelRecord.label_id.asc(),
        )
        .with_for_update()
    )
    rows = []
    for label, case in result.all():
        rows.append((label, case, _loads(case.payload_json, {})))
    return rows


def _dataset_projection(record: AccountDetectionDatasetVersion) -> dict[str, Any]:
    return {
        "dataset_version_id": record.dataset_version_id,
        "data_fingerprint": record.data_fingerprint,
        "source_label_count": record.source_label_count,
        "artifact_uri": record.artifact_uri,
        "manifest": _loads(record.manifest_json, {}),
        "status": record.status,
    }


def _loads(payload: str, fallback: Any) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return fallback


def _governed_observed_at(payload: dict[str, Any]) -> str | None:
    """Return persisted case time only when its timezone is explicit."""

    raw_value = payload.get("last_seen_at")
    if raw_value is None or not str(raw_value).strip():
        raw_value = payload.get("first_seen_at")
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _governed_community_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("community_id")
    if value is None or not str(value).strip():
        value = payload.get("community")
    normalized = str(value or "").strip()
    return normalized or None


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _resolve_account_dataset_output_dir(
    output_dir: str | Path | None,
    dataset_version_id: str,
) -> Path:
    """Resolve an export directory without letting caller input escape artifacts."""

    artifact_root = resolve_project_path(settings.MODEL_ARTIFACT_ROOT)
    requested = (
        Path("account_detection") / dataset_version_id
        if output_dir is None or not str(output_dir).strip()
        else Path(output_dir)
    )
    raw_requested = str(requested)
    windows_path = PureWindowsPath(raw_requested)
    posix_path = PurePosixPath(raw_requested)
    if (
        requested.is_absolute()
        or windows_path.is_absolute()
        or posix_path.is_absolute()
        or windows_path.drive
    ):
        raise AppException(code=400, msg="Account dataset output_dir must be relative to MODEL_ARTIFACT_ROOT.")
    if ".." in requested.parts or ".." in windows_path.parts or ".." in posix_path.parts:
        raise AppException(code=400, msg="Account dataset output_dir must not escape or resolve outside MODEL_ARTIFACT_ROOT.")

    target_dir = (artifact_root / requested).resolve()
    try:
        target_dir.relative_to(artifact_root)
    except ValueError as exc:
        raise AppException(code=400, msg="Account dataset output_dir must remain inside MODEL_ARTIFACT_ROOT.") from exc
    return target_dir


def _dataset_card(manifest: dict[str, Any]) -> str:
    class_counts = manifest.get("class_counts") or {}
    class_rows = "\n".join(
        f"- `{target}`: {count}" for target, count in sorted(class_counts.items())
    ) or "- no approved labels"
    return f"""# Chinese Account Detection Dataset Card

## Dataset

- Dataset version: `{manifest.get("dataset_version_id", "")}`
- Record count: `{manifest.get("record_count", 0)}`
- Data fingerprint: `{manifest.get("data_fingerprint", "")}`
- Source policy: `{manifest.get("source_policy", "")}`
- Output path: `{manifest.get("output_path", "")}`

## Composition

{class_rows}

## Label Boundary

The exported labels are analyst-approved or adjudicated observable account
behavior labels. Model predictions and active-learning scores are review
priority signals only; they are not exported as labels.

## Intended Use

This corpus version is intended for shadow training and leakage-safe evaluation
of Chinese account detection models inside CogGuard. It is not sufficient by
itself for public claims until frozen holdout, time-forward, platform-stratified,
community-disjoint, calibration, false-positive burden, and approval gates pass.

## Known Limitations

- The active-learning selected pool is biased by the acquisition policy.
- The corpus should not be used as a frozen holdout.
- Account labels do not encode identity, nationality, intent, ideology, or
  attribution.
"""


def _load_chinese_corpus_module() -> Any:
    existing = sys.modules.get(_PACKAGE_NAME)
    if existing is not None:
        return existing
    package_dir = PROJECT_ROOT / "research" / "social_bot_detection"
    module_path = package_dir / "chinese_corpus.py"
    spec = importlib.util.spec_from_file_location(_PACKAGE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load account corpus export module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PACKAGE_NAME] = module
    spec.loader.exec_module(module)
    return module
