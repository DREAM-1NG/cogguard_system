"""KT3 main-system integration service.

This service owns persistence-oriented transformations for the MARO-style KT3
layer: encrypted provider configs, Gate Dataset ingestion, normalized Agent
report rows, human feedback memory, async job records, and JSON backfill.
"""

from __future__ import annotations

import base64
import json
import threading
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.risk.kt3_gate_dataset import normalize_kt3_gate_dataset
from app.core.risk.kt3_gate_dataset import validate_kt3_gate_dataset_contract
from app.models.kt3_system import KT3AgentDebateTrace
from app.models.kt3_system import KT3AgentFeedback
from app.models.kt3_system import KT3AgentReport
from app.models.kt3_system import KT3AgentReportAction
from app.models.kt3_system import KT3AgentReportEvidenceRef
from app.models.kt3_system import KT3AgentReportQuery
from app.models.kt3_system import KT3AgentReportUncertainty
from app.models.kt3_system import KT3AgentRun
from app.models.kt3_system import KT3GateCase
from app.models.kt3_system import KT3GateDataset
from app.models.kt3_system import KT3GateLabel
from app.models.kt3_system import KT3Job
from app.models.kt3_system import KT3Policy
from app.models.kt3_system import KT3PolicyAgentWeight
from app.models.kt3_system import KT3PolicyMetric
from app.models.kt3_system import KT3PolicyRefinementRound
from app.models.kt3_system import KT3PolicyRule
from app.models.kt3_system import KT3PolicyThreshold
from app.models.kt3_system import KT3ProviderConfig
from app.models.risk_assessment import RiskAssessment


PROVIDER_TYPES = {"text_llm", "vision_llm", "retrieval"}
JOB_TYPES = {"agent_review", "policy_refine", "gate_dataset_ingest", "backfill"}


def encrypted_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a provider payload and encrypt any supplied API key."""
    api_key = str(payload.get("api_key") or "").strip()
    encrypted_api_key = payload.get("encrypted_api_key")
    if api_key:
        encrypted_api_key = encrypt_provider_api_key(api_key)
    return {
        "name": str(payload.get("name") or "KT3 Provider").strip(),
        "provider_type": _normalize_provider_type(payload.get("provider_type")),
        "base_url": str(payload.get("base_url") or "").strip(),
        "model": str(payload.get("model") or "").strip(),
        "wire_api": str(payload.get("wire_api") or "chat_completions").strip(),
        "encrypted_api_key": encrypted_api_key,
        "supports_vision": bool(payload.get("supports_vision")),
        "is_active": bool(payload.get("is_active", False)),
        "metadata_json": _json_dumps(payload.get("metadata") or payload.get("metadata_json") or {}),
    }


def encrypt_provider_api_key(api_key: str) -> str:
    """Encrypt a provider API key using a KT3-specific master key."""
    if not str(api_key or "").strip():
        return ""
    return _fernet().encrypt(str(api_key).encode("utf-8")).decode("ascii")


def decrypt_provider_api_key(encrypted_value: str | None) -> str:
    if not encrypted_value:
        return ""
    try:
        return _fernet().decrypt(str(encrypted_value).encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("KT3 provider API key cannot be decrypted with current key") from exc


def provider_public_view(provider: dict[str, Any] | KT3ProviderConfig, *, source: str = "database") -> dict[str, Any]:
    """Return a frontend-safe provider view without encrypted/plaintext keys."""
    data = _object_dict(provider)
    encrypted = data.get("encrypted_api_key")
    masked = ""
    if encrypted:
        try:
            masked = _mask_key(decrypt_provider_api_key(str(encrypted)))
        except Exception:
            masked = "configured"
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "provider_type": data.get("provider_type"),
        "base_url": data.get("base_url"),
        "model": data.get("model"),
        "wire_api": data.get("wire_api"),
        "supports_vision": bool(data.get("supports_vision")),
        "is_active": bool(data.get("is_active")),
        "api_key_status": "configured" if encrypted else "missing",
        "api_key_masked": masked,
        "source": source,
        "created_at": _iso(data.get("created_at")),
        "updated_at": _iso(data.get("updated_at")),
    }


def normalize_gate_dataset_upload(dataset: dict[str, Any], *, uploaded_by: int = 0) -> dict[str, Any]:
    """Validate and flatten an uploaded KT3 Gate Dataset contract."""
    validation = validate_kt3_gate_dataset_contract(dataset)
    normalized = normalize_kt3_gate_dataset(dataset)
    manifest = validation.get("manifest") or {}
    metadata = validation.get("normalized_contract", {}).get("metadata") or normalized.get("metadata") or {}
    dataset_row = {
        "dataset_id": metadata.get("dataset_id") or "unspecified",
        "version": metadata.get("version") or "",
        "source": metadata.get("source") or "",
        "manifest_fingerprint": manifest.get("dataset_fingerprint") or _fingerprint(dataset),
        "contract_version": validation.get("contract_version") or "kt3-gate-dataset-v1",
        "metadata_json": _json_dumps(metadata),
        "manifest_json": _json_dumps(manifest),
        "raw_payload_json": _json_dumps(dataset),
        "uploaded_by": uploaded_by,
    }
    cases: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    metadata_split = str(metadata.get("split") or "unspecified")

    for index, case in enumerate(_as_list(normalized.get("post_cases"))):
        case_id = str(case.get("case_id") or f"post_case_{index}")
        split = str(case.get("split") or metadata_split or "unspecified")
        media_refs, media_hashes = _extract_media_refs(case)
        case_row = {
            "case_id": case_id,
            "layer": "post",
            "split": split,
            "payload": case,
            "payload_json": _json_dumps(case),
            "media_refs": media_refs,
            "media_hashes": media_hashes,
            "media_refs_json": _json_dumps(media_refs),
            "media_hashes_json": _json_dumps(media_hashes),
        }
        cases.append(case_row)
        gold = case.get("gold") or case.get("labels") or {}
        for subject_id, label in _iter_gold(gold, "post_id"):
            labels.append(
                {
                    "case_id": case_id,
                    "label_subject_id": subject_id,
                    "label_type": "post_gold",
                    "label": label,
                    "label_json": _json_dumps(label),
                }
            )

    for layer, gold_field, subject_field in (
        ("user", normalized.get("user_gold"), "account_id"),
        ("community", normalized.get("community_gold"), "community_id"),
    ):
        for index, (subject_id, label) in enumerate(_iter_gold(gold_field, subject_field)):
            split = str((label if isinstance(label, dict) else {}).get("split") or metadata_split or "unspecified")
            case_id = str(subject_id or f"{layer}_case_{index}")
            case_row = {
                "case_id": case_id,
                "layer": layer,
                "split": split,
                "payload": label,
                "payload_json": _json_dumps(label),
                "media_refs": [],
                "media_hashes": [],
                "media_refs_json": "[]",
                "media_hashes_json": "[]",
            }
            cases.append(case_row)
            labels.append(
                {
                    "case_id": case_id,
                    "label_subject_id": subject_id,
                    "label_type": f"{layer}_gold",
                    "label": label,
                    "label_json": _json_dumps(label),
                }
            )

    split_counts: dict[str, int] = {}
    layer_counts: dict[str, int] = {}
    for case in cases:
        split_counts[case["split"]] = split_counts.get(case["split"], 0) + 1
        layer_counts[case["layer"]] = layer_counts.get(case["layer"], 0) + 1
    summary = {
        "valid": bool(validation.get("valid")),
        "case_count": len(cases),
        "gold_label_count": len(labels),
        "split_counts": split_counts,
        "layer_counts": layer_counts,
        "media_ref_count": sum(len(case["media_refs"]) for case in cases),
        "warnings": validation.get("warnings") or [],
        "formal_acceptance_ready": bool(validation.get("formal_acceptance_ready")),
    }
    dataset_row["summary_json"] = _json_dumps(summary)
    return {
        "dataset": dataset_row,
        "cases": cases,
        "labels": labels,
        "summary": summary,
        "validation": validation,
    }


def normalize_agent_review_result(
    *,
    report_id: str,
    case_id: str | None,
    result: dict[str, Any],
    created_by: int = 0,
) -> dict[str, Any]:
    """Flatten a manual Agent review result into normalized DB rows."""
    audit = result.get("audit") or {}
    run_id = str(audit.get("run_id") or result.get("run_id") or uuid4())
    input_hash = str(audit.get("input_hash") or result.get("input_hash") or "")
    agent_reports = _as_list(result.get("agent_reports") or result.get("agent_reviews"))
    run = {
        "run_id": run_id,
        "report_id": report_id,
        "case_id": case_id,
        "status": "completed" if all(item.get("status") != "failed" for item in agent_reports if isinstance(item, dict)) else "failed",
        "requested_agents": [item.get("agent_name") for item in agent_reports if isinstance(item, dict)],
        "requested_agents_json": _json_dumps([item.get("agent_name") for item in agent_reports if isinstance(item, dict)]),
        "selected_post_ids_json": _json_dumps(_get(audit, "input_refs", "post_ids") or []),
        "selected_tree_ids_json": _json_dumps(_get(audit, "input_refs", "tree_ids") or []),
        "active_policy_id": audit.get("policy_id"),
        "input_refs_json": _json_dumps(audit.get("input_refs") or {}),
        "input_hash": input_hash,
        "audit_json": _json_dumps(audit),
        "created_by": created_by,
    }
    reports: list[dict[str, Any]] = []
    evidence_refs: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    uncertainties: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    debate_traces: list[dict[str, Any]] = []

    for index, item in enumerate(agent_reports):
        if not isinstance(item, dict):
            continue
        review_id = str(item.get("review_id") or f"{run_id}:{index}:{item.get('agent_name') or 'agent'}")
        sidecar = item.get("system_audit_sidecar") or item.get("structured_sidecar") or {}
        analysis = item.get("analysis_report") or {}
        analysis_text = analysis.get("text") or item.get("report_text")
        report_row = {
            "run_id": run_id,
            "review_id": review_id,
            "report_id": report_id,
            "agent_name": str(item.get("agent_name") or "UnknownAgent"),
            "report_role": str(item.get("report_role") or "expert_initial"),
            "status": str(item.get("status") or "unknown"),
            "model": str(item.get("model") or audit.get("model") or ""),
            "analysis_text": analysis_text,
            "error": item.get("error") or analysis.get("error"),
            "input_hash": input_hash,
            "confidence": _safe_float(sidecar.get("confidence"), None),
            "sidecar": sidecar,
            "sidecar_json": _json_dumps(sidecar),
            "created_by": created_by,
        }
        reports.append(report_row)
        for evidence in _as_list(sidecar.get("evidence_refs")):
            if not isinstance(evidence, dict):
                continue
            evidence_refs.append(
                {
                    "review_id": review_id,
                    "doc_id": evidence.get("doc_id"),
                    "source": evidence.get("source"),
                    "title": evidence.get("title"),
                    "url": evidence.get("url"),
                    "evidence": evidence,
                    "evidence_json": _json_dumps(evidence),
                }
            )
        for order, query in enumerate(_as_list(sidecar.get("retrieval_queries"))):
            queries.append({"review_id": review_id, "query": str(query), "query_order": order})
        for uncertainty in _as_list(sidecar.get("uncertainties")):
            uncertainties.append({"review_id": review_id, "uncertainty": str(uncertainty)})
        for action in _as_list(sidecar.get("suggested_actions")):
            actions.append({"review_id": review_id, "suggested_action": str(action)})
        debate_mode = str(sidecar.get("debate_mode") or "light_debate")
        for trace_ref in _as_list(sidecar.get("debate_trace_refs")) + _as_list(sidecar.get("full_debate_trace_refs")):
            debate_traces.append(
                {
                    "run_id": run_id,
                    "review_id": review_id,
                    "trace_ref": str(trace_ref),
                    "debate_mode": debate_mode,
                    "trace": {"trace_ref": trace_ref, "debate_mode": debate_mode},
                    "trace_json": _json_dumps({"trace_ref": trace_ref, "debate_mode": debate_mode}),
                }
            )
    return {
        "run": run,
        "reports": reports,
        "evidence_refs": evidence_refs,
        "queries": queries,
        "uncertainties": uncertainties,
        "actions": actions,
        "debate_traces": _dedupe_by(debate_traces, ("run_id", "review_id", "trace_ref")),
    }


def extract_kt3_backfill_records(report_id: str, report_json: dict[str, Any], *, created_by: int = 0) -> dict[str, Any]:
    """Extract legacy JSON Agent reviews/feedback in an idempotent shape."""
    seen_reviews: set[str] = set()
    unique_reviews = []
    for item in _as_list(report_json.get("agent_reviews")):
        if not isinstance(item, dict):
            continue
        key = str(item.get("review_id") or f"{item.get('run_id')}:{item.get('agent_name')}:{item.get('report_role')}")
        if key in seen_reviews:
            continue
        seen_reviews.add(key)
        unique_reviews.append(item)
    normalized = normalize_agent_review_result(
        report_id=report_id,
        case_id=None,
        result={
            "audit": {"run_id": unique_reviews[0].get("run_id") if unique_reviews else f"backfill-{report_id}"},
            "agent_reports": unique_reviews,
        },
        created_by=created_by,
    )
    seen_feedback: set[str] = set()
    feedback_rows = []
    for index, item in enumerate(_as_list(report_json.get("agent_feedback"))):
        if not isinstance(item, dict):
            continue
        feedback_id = str(item.get("feedback_id") or f"{report_id}:feedback:{index}")
        if feedback_id in seen_feedback:
            continue
        seen_feedback.add(feedback_id)
        feedback_rows.append(_feedback_row(report_id=report_id, feedback=item, feedback_id=feedback_id, created_by=created_by))
    return {
        **normalized,
        "agent_reports": normalized["reports"],
        "feedback": feedback_rows,
        "summary": {
            "agent_reviews_seen": len(_as_list(report_json.get("agent_reviews"))),
            "agent_reports_extracted": len(normalized["reports"]),
            "feedback_seen": len(_as_list(report_json.get("agent_feedback"))),
            "feedback_extracted": len(feedback_rows),
        },
    }


async def create_kt3_job(
    *,
    job_type: str,
    payload: dict[str, Any],
    user_id: int,
    db: AsyncSession,
    enqueue: bool = True,
) -> dict[str, Any]:
    """Create a KT3 background job and enqueue execution.

    Celery remains the preferred worker path.  Local desktop deployments often
    start only FastAPI, so we also launch an in-process fallback thread.  The
    task code uses a DB claim step, which keeps the two paths from executing the
    same job twice when a real Celery worker is available.
    """
    if job_type not in JOB_TYPES:
        raise ValueError(f"Unsupported KT3 job type: {job_type}")
    row = KT3Job(
        job_type=job_type,
        status="pending",
        progress=0,
        payload_json=_json_dumps(payload),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await db.commit()
    celery_task_id = None
    if enqueue:
        try:
            from app.tasks.kt3_tasks import execute_kt3_job

            async_result = execute_kt3_job.delay(row.id)
            celery_task_id = async_result.id
            row.celery_task_id = celery_task_id
            await db.flush()
        except Exception as exc:
            row.error = f"celery_enqueue_failed_fallback_started: {type(exc).__name__}: {exc}"
            await db.flush()
        await db.commit()
        _start_inline_job_fallback(row.id)
    return {
        "job_id": row.id,
        "job_type": row.job_type,
        "status": row.status,
        "progress": row.progress,
        "poll_url": f"/api/v1/risk/kt3/jobs/{row.id}",
        "celery_task_id": celery_task_id,
    }


def _start_inline_job_fallback(job_id: int) -> None:
    """Start a best-effort local task runner for non-Celery deployments."""

    def _runner() -> None:
        try:
            from app.tasks.kt3_tasks import execute_kt3_job_inline

            execute_kt3_job_inline(job_id, startup_delay_seconds=0.5)
        except Exception:
            # The task itself persists failure details.  Avoid crashing the API
            # process if the fallback thread encounters an unexpected issue.
            return

    thread = threading.Thread(target=_runner, name=f"kt3-inline-job-{job_id}", daemon=True)
    thread.start()


async def create_provider_config(
    *,
    payload: dict[str, Any],
    user_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    data = encrypted_provider_payload(payload)
    row = KT3ProviderConfig(
        name=data["name"],
        provider_type=data["provider_type"],
        base_url=data["base_url"],
        model=data["model"],
        wire_api=data["wire_api"],
        encrypted_api_key=data["encrypted_api_key"],
        supports_vision=data["supports_vision"],
        is_active=False,
        metadata_json=data["metadata_json"],
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    if payload.get("is_active"):
        await activate_provider_config(provider_id=row.id, is_active=True, db=db)
    return provider_public_view(row)


async def update_provider_config(
    *,
    provider_id: int,
    payload: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    row = await _get_provider_row(provider_id, db)
    data = encrypted_provider_payload({**_provider_payload_from_row(row), **payload})
    row.name = data["name"]
    row.provider_type = data["provider_type"]
    row.base_url = data["base_url"]
    row.model = data["model"]
    row.wire_api = data["wire_api"]
    if data["encrypted_api_key"]:
        row.encrypted_api_key = data["encrypted_api_key"]
    row.supports_vision = data["supports_vision"]
    row.metadata_json = data["metadata_json"]
    await db.flush()
    return provider_public_view(row)


async def list_provider_configs(db: AsyncSession, *, include_env_fallback: bool = True) -> dict[str, Any]:
    result = await db.execute(select(KT3ProviderConfig).order_by(KT3ProviderConfig.provider_type, desc(KT3ProviderConfig.is_active), KT3ProviderConfig.id))
    items = [provider_public_view(row) for row in result.scalars().all()]
    if include_env_fallback:
        for provider_type in ("text_llm", "vision_llm", "retrieval"):
            if not any(item["provider_type"] == provider_type and item["is_active"] for item in items):
                env_item = env_provider_public_view(provider_type)
                if env_item:
                    items.append(env_item)
    return {"items": items}


async def activate_provider_config(
    *,
    provider_id: int,
    is_active: bool,
    db: AsyncSession,
) -> dict[str, Any]:
    row = await _get_provider_row(provider_id, db)
    if is_active:
        await db.execute(
            update(KT3ProviderConfig)
            .where(KT3ProviderConfig.provider_type == row.provider_type)
            .values(is_active=False)
        )
    row.is_active = bool(is_active)
    await db.flush()
    return provider_public_view(row)


async def test_provider_config(provider_id: int, db: AsyncSession) -> dict[str, Any]:
    row = await _get_provider_row(provider_id, db)
    key_status = "configured" if row.encrypted_api_key else "missing"
    # The first version intentionally performs a dry configuration check only.
    # Live LLM calls stay inside analyst-triggered Agent jobs.
    return {
        "provider_id": row.id,
        "provider_type": row.provider_type,
        "status": "ready" if row.base_url and row.model and row.encrypted_api_key else "incomplete",
        "api_key_status": key_status,
        "supports_vision": row.supports_vision,
        "live_call_performed": False,
    }


async def persist_gate_dataset_upload(
    *,
    dataset: dict[str, Any],
    uploaded_by: int,
    db: AsyncSession,
) -> dict[str, Any]:
    normalized = normalize_gate_dataset_upload(dataset, uploaded_by=uploaded_by)
    data = normalized["dataset"]
    row = KT3GateDataset(
        dataset_id=data["dataset_id"],
        version=data["version"],
        source=data["source"],
        manifest_fingerprint=data["manifest_fingerprint"],
        contract_version=data["contract_version"],
        metadata_json=data["metadata_json"],
        manifest_json=data["manifest_json"],
        summary_json=data["summary_json"],
        raw_payload_json=data["raw_payload_json"],
        uploaded_by=uploaded_by,
    )
    db.add(row)
    await db.flush()
    case_db_ids: dict[str, int] = {}
    for case in normalized["cases"]:
        case_row = KT3GateCase(
            dataset_id=row.id,
            case_id=case["case_id"],
            layer=case["layer"],
            split=case["split"],
            payload_json=case["payload_json"],
            media_refs_json=case["media_refs_json"],
            media_hashes_json=case["media_hashes_json"],
        )
        db.add(case_row)
        await db.flush()
        case_db_ids[case["case_id"]] = case_row.id
    for label in normalized["labels"]:
        db.add(
            KT3GateLabel(
                dataset_id=row.id,
                gate_case_id=case_db_ids.get(label["case_id"]),
                label_subject_id=label["label_subject_id"],
                label_type=label["label_type"],
                label_json=label["label_json"],
            )
        )
    await db.flush()
    return {
        "dataset_db_id": row.id,
        "dataset_id": row.dataset_id,
        "manifest_fingerprint": row.manifest_fingerprint,
        "summary": normalized["summary"],
        "validation": normalized["validation"],
    }


async def list_gate_datasets(db: AsyncSession, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    stmt = select(KT3GateDataset).order_by(desc(KT3GateDataset.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = []
    for row in result.scalars().all():
        rows.append(
            {
                "id": row.id,
                "dataset_id": row.dataset_id,
                "version": row.version,
                "source": row.source,
                "manifest_fingerprint": row.manifest_fingerprint,
                "summary": _json_loads(row.summary_json, {}),
                "created_at": _iso(row.created_at),
            }
        )
    return {"items": rows, "page": page, "page_size": page_size}


async def get_gate_dataset_detail(dataset_db_id: int, db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(select(KT3GateDataset).where(KT3GateDataset.id == dataset_db_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "dataset_id": row.dataset_id,
        "version": row.version,
        "source": row.source,
        "manifest_fingerprint": row.manifest_fingerprint,
        "metadata": _json_loads(row.metadata_json, {}),
        "manifest": _json_loads(row.manifest_json, {}),
        "summary": _json_loads(row.summary_json, {}),
        "created_at": _iso(row.created_at),
    }


async def get_kt3_job(job_id: int, db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(select(KT3Job).where(KT3Job.id == job_id))
    row = result.scalar_one_or_none()
    if row and row.status in {"pending", "queued"}:
        _start_inline_job_fallback(row.id)
    return kt3_job_public_view(row) if row else None


async def _get_provider_row(provider_id: int, db: AsyncSession) -> KT3ProviderConfig:
    result = await db.execute(select(KT3ProviderConfig).where(KT3ProviderConfig.id == provider_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"KT3 provider not found: {provider_id}")
    return row


def _provider_payload_from_row(row: KT3ProviderConfig) -> dict[str, Any]:
    return {
        "name": row.name,
        "provider_type": row.provider_type,
        "base_url": row.base_url,
        "model": row.model,
        "wire_api": row.wire_api,
        "encrypted_api_key": row.encrypted_api_key,
        "supports_vision": row.supports_vision,
        "metadata_json": row.metadata_json,
    }


async def list_kt3_jobs(db: AsyncSession, *, page: int = 1, page_size: int = 20, job_type: str | None = None) -> dict[str, Any]:
    stmt = select(KT3Job)
    if job_type:
        stmt = stmt.where(KT3Job.job_type == job_type)
    stmt = stmt.order_by(desc(KT3Job.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = [kt3_job_public_view(row) for row in result.scalars().all()]
    return {"items": rows, "page": page, "page_size": page_size}


def kt3_job_public_view(row: KT3Job) -> dict[str, Any]:
    result = _json_loads(row.result_json) if row.result_json else None
    return {
        "job_id": row.id,
        "job_type": row.job_type,
        "status": row.status,
        "progress": row.progress,
        "payload": _json_loads(row.payload_json),
        "result": result,
        "error": row.error,
        "celery_task_id": row.celery_task_id,
        "created_by": row.created_by,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "finished_at": _iso(row.finished_at),
    }


async def persist_agent_review_result(
    *,
    report_id: str,
    case_id: str | None,
    result: dict[str, Any],
    user_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    rows = normalize_agent_review_result(report_id=report_id, case_id=case_id, result=result, created_by=user_id)
    persisted = await persist_agent_review_rows(rows=rows, user_id=user_id, db=db)
    return {
        "run_id": rows["run"]["run_id"],
        "report_count": persisted["inserted_report_count"],
        "skipped_report_count": persisted["skipped_report_count"],
        "evidence_ref_count": len(rows["evidence_refs"]),
        "query_count": len(rows["queries"]),
    }


async def persist_agent_review_rows(
    *,
    rows: dict[str, Any],
    user_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """Persist pre-normalized backfill rows with idempotent run/review keys."""
    run = rows["run"]
    existing_run = await db.execute(select(KT3AgentRun).where(KT3AgentRun.run_id == run["run_id"]))
    inserted_run = existing_run.scalar_one_or_none() is None
    if inserted_run:
        db.add(
            KT3AgentRun(
                run_id=run["run_id"],
                report_id=run["report_id"],
                case_id=run["case_id"],
                status=run["status"],
                requested_agents_json=run["requested_agents_json"],
                selected_post_ids_json=run["selected_post_ids_json"],
                selected_tree_ids_json=run["selected_tree_ids_json"],
                active_policy_id=run["active_policy_id"],
                input_refs_json=run["input_refs_json"],
                input_hash=run["input_hash"],
                audit_json=run["audit_json"],
                created_by=user_id,
            )
        )
    review_ids = [item["review_id"] for item in rows["reports"]]
    existing_review_ids = {
        item[0]
        for item in (await db.execute(select(KT3AgentReport.review_id).where(KT3AgentReport.review_id.in_(review_ids)))).all()
    } if review_ids else set()
    inserted_reports = 0
    skipped_reports = 0
    for item in rows["reports"]:
        if item["review_id"] in existing_review_ids:
            skipped_reports += 1
            continue
        inserted_reports += 1
        db.add(
            KT3AgentReport(
                run_id=item["run_id"],
                review_id=item["review_id"],
                report_id=item["report_id"],
                agent_name=item["agent_name"],
                report_role=item["report_role"],
                status=item["status"],
                model=item["model"],
                analysis_text=item["analysis_text"],
                error=item["error"],
                input_hash=item["input_hash"],
                confidence=item["confidence"],
                sidecar_json=item["sidecar_json"],
                created_by=user_id,
            )
        )
        for evidence in [row for row in rows["evidence_refs"] if row["review_id"] == item["review_id"]]:
            db.add(KT3AgentReportEvidenceRef(**{k: evidence[k] for k in ("review_id", "doc_id", "source", "title", "url", "evidence_json")}))
        for query in [row for row in rows["queries"] if row["review_id"] == item["review_id"]]:
            db.add(KT3AgentReportQuery(**query))
        for uncertainty in [row for row in rows["uncertainties"] if row["review_id"] == item["review_id"]]:
            db.add(KT3AgentReportUncertainty(**uncertainty))
        for action in [row for row in rows["actions"] if row["review_id"] == item["review_id"]]:
            db.add(KT3AgentReportAction(**action))
        for trace in [row for row in rows["debate_traces"] if row["review_id"] == item["review_id"]]:
            db.add(KT3AgentDebateTrace(**{k: trace[k] for k in ("run_id", "review_id", "trace_ref", "debate_mode", "trace_json")}))
    await db.flush()
    return {
        "inserted_run": inserted_run,
        "inserted_report_count": inserted_reports,
        "skipped_report_count": skipped_reports,
    }


async def persist_feedback_row(
    *,
    row_data: dict[str, Any],
    user_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    existing = await db.execute(select(KT3AgentFeedback).where(KT3AgentFeedback.feedback_id == row_data["feedback_id"]))
    if existing.scalar_one_or_none() is not None:
        return {"feedback_id": row_data["feedback_id"], "inserted": False}
    db.add(
        KT3AgentFeedback(
            feedback_id=row_data["feedback_id"],
            report_id=row_data["report_id"],
            review_id=row_data["review_id"],
            run_id=row_data["run_id"],
            case_id=row_data["case_id"],
            human_label=row_data["human_label"],
            corrected_label=row_data["corrected_label"],
            error_types_json=_json_dumps(row_data["error_types"]),
            notes=row_data["notes"],
            evidence_refs_json=_json_dumps(row_data["evidence_refs"]),
            reviewer_confidence=row_data["reviewer_confidence"],
            created_by=user_id,
        )
    )
    await db.flush()
    return {"feedback_id": row_data["feedback_id"], "inserted": True}


async def persist_feedback(
    *,
    report_id: str,
    feedback: dict[str, Any],
    user_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    feedback_id = str(feedback.get("feedback_id") or f"kt3-feedback-{uuid4().hex[:12]}")
    row_data = _feedback_row(report_id=report_id, feedback=feedback, feedback_id=feedback_id, created_by=user_id)
    await persist_feedback_row(row_data=row_data, user_id=user_id, db=db)
    return row_data


async def feedback_memory_from_db(report_ids: list[str], db: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(KT3AgentFeedback)
    if report_ids:
        stmt = stmt.where(KT3AgentFeedback.report_id.in_(report_ids))
    result = await db.execute(stmt)
    rows = []
    for row in result.scalars().all():
        rows.append(
            {
                "feedback_id": row.feedback_id,
                "report_id": row.report_id,
                "review_id": row.review_id,
                "run_id": row.run_id,
                "case_id": row.case_id,
                "human_label": row.human_label,
                "corrected_label": row.corrected_label,
                "corrected_harmfulness": row.corrected_label,
                "error_types": _json_loads(row.error_types_json, []),
                "notes": row.notes,
                "evidence_refs": _json_loads(row.evidence_refs_json, []),
                "reviewer_confidence": row.reviewer_confidence,
            }
        )
    return rows


async def persist_policy_artifact(
    *,
    artifact: dict[str, Any],
    user_id: int,
    db: AsyncSession,
    dataset_db_id: int | None = None,
) -> dict[str, Any]:
    policy_id = str(artifact.get("policy_id"))
    policy = artifact.get("policy") or {}
    db.add(
        KT3Policy(
            policy_id=policy_id,
            status=str(artifact.get("activation_status") or "candidate_pending_human_approval"),
            dataset_id=dataset_db_id,
            policy_json=_json_dumps(policy),
            optimization_json=_json_dumps(artifact.get("optimization") or {}),
            error_memory_summary_json=_json_dumps(artifact.get("error_memory_summary") or {}),
            held_out_audit_json=_json_dumps(artifact.get("held_out_audit")) if artifact.get("held_out_audit") is not None else None,
            can_activate=bool(artifact.get("can_activate", True)),
            non_activatable_reasons_json=_json_dumps(artifact.get("non_activatable_reasons") or []),
            created_by=user_id,
        )
    )
    for name, value in (policy.get("agent_weights") or {}).items():
        db.add(KT3PolicyAgentWeight(policy_id=policy_id, agent_name=str(name), weight=float(value)))
    for name in ("review_threshold", "abstain_threshold", "retrieval_threshold", "countermeasure_threshold"):
        if name in policy:
            db.add(KT3PolicyThreshold(policy_id=policy_id, threshold_name=name, threshold_value=float(policy[name])))
    for rule in _as_list(artifact.get("candidate_rules")):
        if isinstance(rule, dict):
            db.add(
                KT3PolicyRule(
                    policy_id=policy_id,
                    rule_id=str(rule.get("rule_id") or uuid4()),
                    round=int(rule.get("round") or 0),
                    source=str(rule.get("source") or ""),
                    description=str(rule.get("description") or ""),
                    status=str(rule.get("status") or ""),
                    rule_json=_json_dumps(rule),
                )
            )
    for round_item in _as_list(artifact.get("validation_metrics_by_round")):
        if not isinstance(round_item, dict):
            continue
        round_no = int(round_item.get("round") or 0)
        for metric_name, metric_value in _flatten_metrics(round_item.get("metrics") or {}).items():
            db.add(
                KT3PolicyMetric(
                    policy_id=policy_id,
                    split_name=str(round_item.get("stage") or "validation"),
                    round=round_no,
                    metric_name=metric_name,
                    metric_value=metric_value if isinstance(metric_value, (int, float)) else None,
                    metric_json=None if isinstance(metric_value, (int, float)) else _json_dumps(metric_value),
                )
            )
    for trace in _as_list(artifact.get("refinement_trace")):
        if isinstance(trace, dict):
            db.add(
                KT3PolicyRefinementRound(
                    policy_id=policy_id,
                    round=int(trace.get("round") or 0),
                    accepted_rule_id=trace.get("accepted_rule_id"),
                    trace_json=_json_dumps(trace),
                )
            )
    await db.flush()
    return {"policy_id": policy_id, "status": "persisted", "can_activate": bool(artifact.get("can_activate", True))}


async def activate_policy_in_db(policy_id: str, *, user_id: int, db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(select(KT3Policy).where(KT3Policy.policy_id == policy_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"KT3 policy not found: {policy_id}")
    if not row.can_activate:
        reasons = ", ".join(_json_loads(row.non_activatable_reasons_json, []))
        raise ValueError(f"KT3 policy cannot be activated: {reasons or 'unknown_reason'}")
    await db.execute(update(KT3Policy).where(KT3Policy.status == "active_human_approved").values(status="inactive"))
    row.status = "active_human_approved"
    row.activated_by = user_id
    row.activated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"policy_id": policy_id, "activation_status": row.status, "activated_by": user_id, "activated_at": _iso(row.activated_at)}


async def get_active_policy_artifact(db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(select(KT3Policy).where(KT3Policy.status == "active_human_approved").order_by(desc(KT3Policy.activated_at)).limit(1))
    row = result.scalar_one_or_none()
    if row is None or not hasattr(row, "policy_id"):
        return None
    return await _policy_artifact_from_row(row, db=db)


async def get_policy_artifact_from_db(policy_id: str, db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(select(KT3Policy).where(KT3Policy.policy_id == policy_id))
    row = result.scalar_one_or_none()
    return await _policy_artifact_from_row(row, db=db) if row else None


async def list_policies(db: AsyncSession, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    stmt = select(KT3Policy).order_by(desc(KT3Policy.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = [_policy_artifact_summary_from_row(row) for row in result.scalars().all()]
    return {"items": rows, "page": page, "page_size": page_size}


async def _policy_artifact_from_row(row: KT3Policy, *, db: AsyncSession) -> dict[str, Any]:
    artifact = {
        "policy_id": row.policy_id,
        "activation_status": row.status,
        "policy": _json_loads(row.policy_json, {}),
        "optimization": _json_loads(row.optimization_json, {}),
        "error_memory_summary": _json_loads(row.error_memory_summary_json, {}),
        "held_out_audit": _json_loads(row.held_out_audit_json) if row.held_out_audit_json else None,
        "can_activate": row.can_activate,
        "non_activatable_reasons": _json_loads(row.non_activatable_reasons_json, []),
        "created_by": row.created_by,
        "activated_by": row.activated_by,
        "created_at": _iso(row.created_at),
        "activated_at": _iso(row.activated_at),
    }
    rule_result = await db.execute(select(KT3PolicyRule).where(KT3PolicyRule.policy_id == row.policy_id).order_by(KT3PolicyRule.round, KT3PolicyRule.id))
    artifact["candidate_rules"] = [_json_loads(item.rule_json, {}) for item in rule_result.scalars().all()]
    trace_result = await db.execute(
        select(KT3PolicyRefinementRound)
        .where(KT3PolicyRefinementRound.policy_id == row.policy_id)
        .order_by(KT3PolicyRefinementRound.round, KT3PolicyRefinementRound.id)
    )
    artifact["refinement_trace"] = [_json_loads(item.trace_json, {}) for item in trace_result.scalars().all()]
    metric_result = await db.execute(
        select(KT3PolicyMetric)
        .where(KT3PolicyMetric.policy_id == row.policy_id)
        .order_by(KT3PolicyMetric.round, KT3PolicyMetric.split_name, KT3PolicyMetric.metric_name)
    )
    by_round: dict[tuple[int, str], dict[str, Any]] = {}
    for metric in metric_result.scalars().all():
        key = (metric.round, metric.split_name)
        row_metrics = by_round.setdefault(key, {"round": metric.round, "stage": metric.split_name, "metrics": {}})
        row_metrics["metrics"][metric.metric_name] = metric.metric_value if metric.metric_json is None else _json_loads(metric.metric_json)
    artifact["validation_metrics_by_round"] = list(by_round.values())
    return artifact


def _policy_artifact_summary_from_row(row: KT3Policy) -> dict[str, Any]:
    return {
        "policy_id": row.policy_id,
        "activation_status": row.status,
        "policy": _json_loads(row.policy_json, {}),
        "can_activate": row.can_activate,
        "non_activatable_reasons": _json_loads(row.non_activatable_reasons_json, []),
        "created_by": row.created_by,
        "activated_by": row.activated_by,
        "created_at": _iso(row.created_at),
        "activated_at": _iso(row.activated_at),
    }


async def append_report_json_agent_summary(
    *,
    report_id: str,
    review_result: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Keep old report_json consumers working with a lightweight summary."""
    result = await db.execute(select(RiskAssessment).where(RiskAssessment.report_id == report_id))
    row = result.scalar_one_or_none()
    if row is None:
        return
    try:
        report = json.loads(row.report_json)
    except Exception:
        return
    reviews = report.get("agent_reviews") if isinstance(report.get("agent_reviews"), list) else []
    reviews.extend(_as_list(review_result.get("agent_reports")))
    report["agent_reviews"] = reviews[-50:]
    runs = report.get("agent_review_runs") if isinstance(report.get("agent_review_runs"), list) else []
    if review_result.get("audit"):
        runs.append(review_result["audit"])
    report["agent_review_runs"] = runs[-20:]
    row.report_json = _json_dumps(report)
    await db.flush()


def env_provider_public_view(provider_type: str) -> dict[str, Any] | None:
    if provider_type == "retrieval":
        if not settings.KT3_RETRIEVAL_API_KEY or not settings.KT3_RETRIEVAL_BASE_URL:
            return None
        return {
            "id": None,
            "name": settings.KT3_RETRIEVAL_PROVIDER_NAME or "Environment Retrieval Provider",
            "provider_type": "retrieval",
            "base_url": settings.KT3_RETRIEVAL_BASE_URL,
            "model": "",
            "wire_api": "http_json",
            "supports_vision": False,
            "is_active": True,
            "api_key_status": "configured",
            "api_key_masked": _mask_key(settings.KT3_RETRIEVAL_API_KEY),
            "source": "env_fallback",
            "metadata": {
                "search_path": settings.KT3_RETRIEVAL_SEARCH_PATH,
                "adapter": settings.KT3_RETRIEVAL_ADAPTER,
            },
        }
    if provider_type not in {"text_llm", "vision_llm"}:
        return None
    if not settings.LLM_API_KEY:
        return None
    supports_vision = provider_type == "vision_llm" and bool(settings.LLM_REQUIRE_VISION)
    return {
        "id": None,
        "name": "Environment LLM Provider",
        "provider_type": provider_type,
        "base_url": settings.LLM_API_BASE,
        "model": settings.LLM_MODEL,
        "wire_api": settings.LLM_API_WIRE,
        "supports_vision": supports_vision,
        "is_active": True,
        "api_key_status": "configured",
        "api_key_masked": _mask_key(settings.LLM_API_KEY),
        "source": "env_fallback",
    }


def _fernet() -> Fernet:
    secret = str(getattr(settings, "KT3_CONFIG_ENCRYPTION_KEY", "") or "").strip()
    if not secret:
        raise ValueError("KT3_CONFIG_ENCRYPTION_KEY is required to store provider API keys")
    key = base64.urlsafe_b64encode(sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _normalize_provider_type(value: Any) -> str:
    provider_type = str(value or "text_llm").strip()
    if provider_type not in PROVIDER_TYPES:
        raise ValueError(f"Unsupported KT3 provider_type: {provider_type}")
    return provider_type


def _mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return f"{value[:2]}...{value[-1:]}"
    return f"{value[:4]}...{value[-4:]}"


def _extract_media_refs(value: Any) -> tuple[list[str], list[dict[str, Any]]]:
    refs: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key in {"media_url", "media_urls", "image", "image_url", "video", "video_url", "uri", "path"}:
                    visit_media(child)
                else:
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    def visit_media(node: Any) -> None:
        if isinstance(node, str) and node.strip():
            refs.append(node.strip())
        elif isinstance(node, list):
            for child in node:
                visit_media(child)
        elif isinstance(node, dict):
            for child in node.values():
                visit_media(child)

    visit(value)
    deduped = _dedupe_text(refs)
    hashes = [{"uri": ref, "sha256": _file_hash_or_ref_hash(ref), "binary_stored": False} for ref in deduped]
    return deduped, hashes


def _file_hash_or_ref_hash(uri: str) -> str:
    path = Path(uri)
    try:
        if path.exists() and path.is_file():
            return sha256(path.read_bytes()).hexdigest()
    except OSError:
        pass
    return sha256(uri.encode("utf-8")).hexdigest()


def _iter_gold(value: Any, subject_field: str) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        for key, raw in value.items():
            label = raw if isinstance(raw, dict) else {"value": raw}
            subject_id = str(label.get(subject_field) or key)
            rows.append((subject_id, label))
    elif isinstance(value, list):
        for index, raw in enumerate(value):
            if not isinstance(raw, dict):
                continue
            subject_id = str(raw.get(subject_field) or raw.get("id") or f"{subject_field}_{index}")
            rows.append((subject_id, raw))
    return rows


def _feedback_row(*, report_id: str, feedback: dict[str, Any], feedback_id: str, created_by: int) -> dict[str, Any]:
    corrected_label = feedback.get("corrected_label") or feedback.get("corrected_harmfulness")
    return {
        "feedback_id": feedback_id,
        "report_id": report_id,
        "review_id": feedback.get("review_id"),
        "run_id": feedback.get("run_id"),
        "case_id": feedback.get("case_id"),
        "human_label": feedback.get("human_label"),
        "corrected_label": corrected_label,
        "corrected_harmfulness": corrected_label,
        "error_types": _as_list(feedback.get("error_types")),
        "notes": str(feedback.get("notes") or ""),
        "evidence_refs": _as_list(feedback.get("evidence_refs")),
        "reviewer_confidence": _safe_float(feedback.get("reviewer_confidence"), 0.5) or 0.5,
        "created_by": created_by,
    }


def _flatten_metrics(metrics: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for key, value in metrics.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            rows.update(_flatten_metrics(value, name))
        else:
            rows[name] = value
    return rows


def _object_dict(value: dict[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    keys = (
        "id",
        "name",
        "provider_type",
        "base_url",
        "model",
        "wire_api",
        "encrypted_api_key",
        "supports_vision",
        "is_active",
        "created_at",
        "updated_at",
    )
    return {key: getattr(value, key, None) for key in keys}


def _dedupe_by(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for row in rows:
        key = tuple(row.get(item) for item in keys)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _dedupe_text(values: list[str]) -> list[str]:
    seen = set()
    rows = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        rows.append(value)
    return rows


def _fingerprint(value: Any) -> str:
    return sha256(_json_dumps(value).encode("utf-8")).hexdigest()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _get(mapping: dict[str, Any], *path: str) -> Any:
    value: Any = mapping
    for item in path:
        if not isinstance(value, dict):
            return None
        value = value.get(item)
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
