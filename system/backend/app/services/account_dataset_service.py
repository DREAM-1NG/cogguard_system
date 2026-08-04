"""Approved-corpus export service for Chinese account detection."""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PROJECT_ROOT, settings
from app.models.account_labeling import (
    AccountBehaviorLabelRecord,
    AccountDetectionCaseRecord,
    AccountDetectionDatasetVersion,
)
from app.utils.exceptions import AppException

__all__ = ["export_approved_account_dataset", "list_account_detection_datasets"]

_PACKAGE_NAME = "_cogguard_social_bot_detection_chinese_corpus"


async def export_approved_account_dataset(
    session: AsyncSession,
    *,
    dataset_version_id: str | None = None,
    output_dir: str | Path | None = None,
    operator_id: int,
) -> dict[str, Any]:
    """Export approved labels into a versioned corpus and register its manifest."""

    chinese_corpus = _load_chinese_corpus_module()
    rows = await _approved_label_rows(session)
    if not rows:
        raise AppException(
            code=400,
            msg="No approved or adjudicated account labels are available for export.",
        )
    version_id = dataset_version_id or f"account-dataset-{uuid.uuid4().hex[:12]}"
    target_dir = Path(output_dir) if output_dir else Path(settings.MODEL_ARTIFACT_ROOT) / "account_detection" / version_id
    output_path = target_dir / "approved_account_labels.jsonl"
    records = [
        chinese_corpus.ApprovedAccountLabel(
            case_id=str(label.case_id),
            account_id=str(case.account_id),
            platform=str(case.platform),
            event_id=str(case.event_id),
            text=str((case_payload.get("text") or "")),
            behavior_label=str(label.behavior_label),
            training_target=str(label.training_target),
            evidence_post_ids=_loads(label.evidence_post_ids_json, []),
            case_fingerprint=str(label.case_fingerprint or case.case_fingerprint),
            label_id=str(label.label_id),
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
            },
            ensure_ascii=False,
        ),
        status="candidate",
        created_by=operator_id,
    )
    session.add(record)
    await session.flush()
    return _dataset_projection(record)


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
) -> list[tuple[AccountBehaviorLabelRecord, AccountDetectionCaseRecord, dict[str, Any]]]:
    result = await session.execute(
        select(AccountBehaviorLabelRecord, AccountDetectionCaseRecord)
        .join(
            AccountDetectionCaseRecord,
            AccountDetectionCaseRecord.case_id == AccountBehaviorLabelRecord.case_id,
        )
        .where(AccountBehaviorLabelRecord.label_status.in_(("approved", "adjudicated")))
        .where(AccountBehaviorLabelRecord.training_target.in_(("bot", "non_bot", "abstain")))
        .where(AccountBehaviorLabelRecord.case_fingerprint == AccountDetectionCaseRecord.case_fingerprint)
        .order_by(
            AccountDetectionCaseRecord.platform.asc(),
            AccountDetectionCaseRecord.event_id.asc(),
            AccountDetectionCaseRecord.account_id.asc(),
            AccountBehaviorLabelRecord.label_id.asc(),
        )
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
