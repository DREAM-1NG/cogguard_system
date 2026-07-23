"""Celery tasks for Review Agent review, policy refinement, and backfill."""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import settings
from app.core.review.agent_policy import refine_agent_policy_loop
from app.core.review.agent_review import OpenAICompatibleAgentProvider
from app.core.review.agent_review import OpenAICompatibleConfig
from app.models.risk_assessment import RiskAssessment
from app.services import review_system_service, risk_service


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="review.execute", bind=True)
def execute_review_job(self, job_id: int):
    """Execute a persisted Review job and update its DB audit row."""
    return _execute_review_job_with_audit(job_id)


def execute_review_job_inline(job_id: int, *, startup_delay_seconds: float = 0.0):
    """Run a Review job in-process for local deployments without Celery workers."""
    if startup_delay_seconds > 0:
        time.sleep(startup_delay_seconds)
    return _execute_review_job_with_audit(job_id, claim_attempts=60, claim_delay_seconds=0.5)


def _execute_review_job_with_audit(
    job_id: int,
    *,
    claim_attempts: int = 1,
    claim_delay_seconds: float = 0.0,
):
    try:
        claimed = False
        last_status = None
        for attempt in range(max(1, claim_attempts)):
            if _claim_job(job_id):
                claimed = True
                break
            last_status = _read_job_status(job_id)
            if last_status in {"running", "completed", "failed"}:
                return {"job_id": job_id, "status": f"already_{last_status}"}
            if attempt < claim_attempts - 1 and claim_delay_seconds > 0:
                time.sleep(claim_delay_seconds)
        if not claimed:
            return {"job_id": job_id, "status": last_status or "not_found_or_not_ready"}
        result = _run_async(_execute_review_job_async(job_id))
        _update_job(job_id, status="completed", progress=100, result=result)
        return result
    except Exception:
        err = traceback.format_exc()
        _update_job(job_id, status="failed", progress=0, error=err[-8000:])
        raise


async def _execute_review_job_async(job_id: int) -> dict[str, Any]:
    engine = create_async_engine(settings.mysql_url, echo=settings.BACKEND_DEBUG, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            row = await _load_job(job_id, db)
            payload = json.loads(row.payload_json or "{}")
            if row.job_type == "agent_review":
                result = await _execute_agent_review(payload=payload, user_id=row.created_by, db=db)
            elif row.job_type == "policy_refine":
                result = await _execute_policy_refine(payload=payload, user_id=row.created_by, db=db)
            elif row.job_type == "backfill":
                result = await _execute_backfill(payload=payload, user_id=row.created_by, db=db)
            elif row.job_type == "gate_dataset_ingest":
                result = await review_system_service.persist_gate_dataset_upload(
                    dataset=payload.get("gate_dataset") or payload,
                    uploaded_by=row.created_by,
                    db=db,
                )
            else:
                raise ValueError(f"Unsupported Review job type: {row.job_type}")
            await db.commit()
            return result
    finally:
        await engine.dispose()


def _claim_job(job_id: int) -> bool:
    sync_url = settings.mysql_url.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE review_jobs
                    SET status='running', progress=5, updated_at=NOW()
                    WHERE id=:id AND status IN ('pending', 'queued')
                    """
                ),
                {"id": job_id},
            )
            conn.commit()
            return result.rowcount == 1
    finally:
        engine.dispose()


def _read_job_status(job_id: int) -> str | None:
    sync_url = settings.mysql_url.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT status FROM review_jobs WHERE id=:id"),
                {"id": job_id},
            )
            row = result.first()
            return str(row[0]) if row else None
    finally:
        engine.dispose()


async def _load_job(job_id: int, db: AsyncSession):
    from sqlalchemy import select
    from app.models.review_system import ReviewJob

    result = await db.execute(select(ReviewJob).where(ReviewJob.id == job_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"Review job not found: {job_id}")
    return row


async def _execute_agent_review(*, payload: dict[str, Any], user_id: int, db: AsyncSession) -> dict[str, Any]:
    provider_info = await _provider_for_agent_run(db)
    retrieval_info = await _retrieval_provider_for_agent_run(db)
    review_result = await risk_service.run_agent_review(
        report_id=str(payload["report_id"]),
        agent_names=list(payload.get("agent_names") or []),
        case_id=payload.get("case_id"),
        selected_post_ids=list(payload.get("selected_post_ids") or []),
        selected_tree_ids=list(payload.get("selected_tree_ids") or []),
        enable_active_retrieval=bool(payload.get("enable_active_retrieval")),
        enable_external_retrieval=payload.get("enable_external_retrieval"),
        enable_light_debate=bool(payload.get("enable_light_debate")),
        enable_full_debate=bool(payload.get("enable_full_debate")),
        debate_max_rounds=int(payload.get("debate_max_rounds") or 3),
        runtime_mode=str(payload.get("runtime_mode") or "auto"),
        enable_deep_judge=bool(payload.get("enable_deep_judge")),
        policy_id=payload.get("policy_id"),
        active_policy_id=payload.get("active_policy_id"),
        retrieval_top_k=int(payload.get("retrieval_top_k") or 3),
        user_id=user_id,
        db=db,
        provider=provider_info["provider"],
        provider_name=provider_info["source"],
        provider_model=provider_info["model"],
        include_media_base64=provider_info["include_media_base64"],
        require_vision=provider_info["require_vision"],
        active_retriever=retrieval_info["provider"],
        append_legacy_report_json=False,
    )
    normalized = await review_system_service.persist_agent_review_result(
        report_id=str(payload["report_id"]),
        case_id=payload.get("case_id"),
        result=review_result["review_result"],
        user_id=user_id,
        db=db,
    )
    await review_system_service.append_report_json_agent_summary(
        report_id=str(payload["report_id"]),
        review_result=review_result["review_result"],
        db=db,
    )
    return {
        "report_id": payload["report_id"],
        "summary": review_result.get("summary"),
        "normalized_persistence": normalized,
        "provider_source": provider_info["source"],
        "retrieval_provider_source": retrieval_info["source"],
    }


async def _execute_policy_refine(*, payload: dict[str, Any], user_id: int, db: AsyncSession) -> dict[str, Any]:
    feedback_memory = await review_system_service.feedback_memory_from_db(
        list(payload.get("feedback_report_ids") or []),
        db,
    )
    text_llm = await _provider_for_policy_refine(db)
    baseline_policy = None
    baseline_policy_id = payload.get("baseline_policy_id")
    if baseline_policy_id:
        artifact = await review_system_service.get_policy_artifact_from_db(str(baseline_policy_id), db)
        baseline_policy = (artifact or {}).get("policy") if isinstance(artifact, dict) else None
    artifact = await asyncio.to_thread(
        refine_agent_policy_loop,
        payload.get("dataset_manifest") or {},
        feedback_memory=feedback_memory,
        baseline_policy=baseline_policy,
        max_iterations=int(payload.get("max_iterations") or 3),
        enable_llm_rule_generator=bool(payload.get("enable_llm_rule_generator")),
        rule_generator=text_llm["rule_generator"],
        held_out_required=bool(payload.get("held_out_required", True)),
    )
    persisted = await review_system_service.persist_policy_artifact(
        artifact=artifact,
        user_id=user_id,
        db=db,
    )
    return {"policy": artifact, "persistence": persisted, "provider_source": text_llm["source"]}


async def _execute_backfill(*, payload: dict[str, Any], user_id: int, db: AsyncSession) -> dict[str, Any]:
    from sqlalchemy import select

    report_ids = [str(item) for item in payload.get("report_ids") or [] if str(item)]
    limit = int(payload.get("limit") or 500)
    stmt = select(RiskAssessment)
    if report_ids:
        stmt = stmt.where(RiskAssessment.report_id.in_(report_ids))
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    reports_seen = 0
    agent_reports_extracted = 0
    feedback_extracted = 0
    agent_reports_inserted = 0
    agent_reports_skipped = 0
    feedback_inserted = 0
    feedback_skipped = 0
    for row in result.scalars().all():
        reports_seen += 1
        try:
            report_json = json.loads(row.report_json)
        except Exception:
            continue
        extracted = review_system_service.extract_review_backfill_records(row.report_id, report_json, created_by=user_id)
        agent_reports_extracted += extracted["summary"]["agent_reports_extracted"]
        feedback_extracted += extracted["summary"]["feedback_extracted"]
        persisted_reports = await review_system_service.persist_agent_review_rows(
            rows=extracted,
            user_id=user_id,
            db=db,
        )
        agent_reports_inserted += persisted_reports["inserted_report_count"]
        agent_reports_skipped += persisted_reports["skipped_report_count"]
        for feedback in extracted["feedback"]:
            persisted_feedback = await review_system_service.persist_feedback_row(
                row_data=feedback,
                user_id=user_id,
                db=db,
            )
            if persisted_feedback["inserted"]:
                feedback_inserted += 1
            else:
                feedback_skipped += 1
    return {
        "reports_seen": reports_seen,
        "agent_reports_extracted": agent_reports_extracted,
        "feedback_extracted": feedback_extracted,
        "agent_reports_inserted": agent_reports_inserted,
        "agent_reports_skipped": agent_reports_skipped,
        "feedback_inserted": feedback_inserted,
        "feedback_skipped": feedback_skipped,
        "idempotent": True,
    }


async def _provider_for_agent_run(db: AsyncSession) -> dict[str, Any]:
    from sqlalchemy import select
    from app.models.review_system import ReviewProviderConfig

    result = await db.execute(
        select(ReviewProviderConfig)
        .where(ReviewProviderConfig.provider_type.in_(["text_llm", "vision_llm"]))
        .where(ReviewProviderConfig.is_active.is_(True))
        .order_by(ReviewProviderConfig.provider_type.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is not None and row.encrypted_api_key:
        api_key = review_system_service.decrypt_provider_api_key(row.encrypted_api_key)
        config = OpenAICompatibleConfig(
            api_key=api_key,
            base_url=row.base_url,
            model=row.model,
            wire_api=row.wire_api,
            timeout_seconds=float(settings.LLM_TIMEOUT_SECONDS),
            include_media_base64=True,
            require_vision=bool(row.supports_vision),
        )
        return {
            "provider": OpenAICompatibleAgentProvider(config),
            "source": "database",
            "model": row.model,
            "include_media_base64": True,
            "require_vision": bool(row.supports_vision),
        }
    if settings.LLM_API_KEY:
        config = OpenAICompatibleConfig(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            model=settings.LLM_MODEL,
            wire_api=settings.LLM_API_WIRE,
            timeout_seconds=float(settings.LLM_TIMEOUT_SECONDS),
            include_media_base64=bool(settings.LLM_INCLUDE_MEDIA_BASE64),
            require_vision=bool(settings.LLM_REQUIRE_VISION),
        )
        return {
            "provider": OpenAICompatibleAgentProvider(config),
            "source": "env_fallback",
            "model": settings.LLM_MODEL,
            "include_media_base64": bool(settings.LLM_INCLUDE_MEDIA_BASE64),
            "require_vision": bool(settings.LLM_REQUIRE_VISION),
        }
    return {
        "provider": None,
        "source": "not_configured",
        "model": "",
        "include_media_base64": False,
        "require_vision": False,
    }


async def _retrieval_provider_for_agent_run(db: AsyncSession) -> dict[str, Any]:
    from sqlalchemy import select
    from app.models.review_system import ReviewProviderConfig

    result = await db.execute(
        select(ReviewProviderConfig)
        .where(ReviewProviderConfig.provider_type == "retrieval")
        .where(ReviewProviderConfig.is_active.is_(True))
        .order_by(ReviewProviderConfig.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        if getattr(settings, "REVIEW_RETRIEVAL_API_KEY", "") and getattr(settings, "REVIEW_RETRIEVAL_BASE_URL", ""):
            return {
                "provider": _build_http_retrieval_provider(
                    base_url=str(settings.REVIEW_RETRIEVAL_BASE_URL),
                    api_key=str(settings.REVIEW_RETRIEVAL_API_KEY),
                    search_path=str(getattr(settings, "REVIEW_RETRIEVAL_SEARCH_PATH", "/search") or "/search"),
                    timeout_seconds=20.0,
                    provider_name=str(getattr(settings, "REVIEW_RETRIEVAL_PROVIDER_NAME", "") or "env_retrieval"),
                    adapter=str(getattr(settings, "REVIEW_RETRIEVAL_ADAPTER", "") or ""),
                ),
                "source": "env_fallback",
            }
        return {"provider": None, "source": "not_configured"}
    metadata = json.loads(row.metadata_json or "{}")
    api_key = review_system_service.decrypt_provider_api_key(row.encrypted_api_key) if row.encrypted_api_key else ""
    timeout_seconds = float(metadata.get("timeout_seconds") or 20.0)
    search_path = str(metadata.get("search_path") or "/search")
    adapter = str(metadata.get("adapter") or "")
    return {
        "provider": _build_http_retrieval_provider(
            base_url=row.base_url,
            api_key=api_key,
            search_path=search_path,
            timeout_seconds=timeout_seconds,
            provider_name=row.name,
            adapter=adapter,
        ),
        "source": "database",
    }


def _build_http_retrieval_provider(
    *,
    base_url: str,
    api_key: str,
    search_path: str,
    timeout_seconds: float,
    provider_name: str,
    adapter: str = "",
):
    async def _provider(*, query: str, context: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
        url = base_url.rstrip("/") + "/" + search_path.lstrip("/")
        adapter_name = str(adapter or "").strip().lower()
        headers = {"Content-Type": "application/json"}
        if api_key:
            if adapter_name == "exa":
                headers["x-api-key"] = api_key
            else:
                headers["Authorization"] = f"Bearer {api_key}"
        request_body = _retrieval_request_body(
            adapter=adapter_name,
            query=query,
            context=context,
            top_k=top_k,
        )
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=request_body)
            response.raise_for_status()
            payload = response.json()
        return _normalize_retrieval_results(
            adapter=adapter_name,
            payload=payload,
            provider_name=provider_name,
            top_k=top_k,
        )

    return _provider


def _retrieval_request_body(*, adapter: str, query: str, context: dict[str, Any], top_k: int) -> dict[str, Any]:
    shared_context = {
        "report_id": _context_ref(context, "report_id"),
        "event_id": _context_ref(context, "event_id"),
        "platform": _context_ref(context, "platform"),
        "case_id": _context_ref(context, "case_id"),
        "selected_post_ids": list((_context_ref(context, "post_ids") or [])),
        "selected_tree_ids": list((_context_ref(context, "tree_ids") or [])),
        "claim_summary": _claim_summary(context),
        "post_snippets": _post_snippets(context),
    }
    if adapter == "exa":
        return {
            "query": query,
            "numResults": int(top_k),
            "contents": {"text": True, "highlights": True, "summary": True},
            "context": shared_context,
        }
    return {
        "query": query,
        "top_k": int(top_k),
        "context": shared_context,
    }


def _normalize_retrieval_results(*, adapter: str, payload: dict[str, Any], provider_name: str, top_k: int) -> list[dict[str, Any]]:
    if adapter == "exa":
        rows = payload.get("results") or payload.get("data") or []
        if not isinstance(rows, list):
            raise RuntimeError(f"{provider_name} Exa retrieval response missing results list")
        normalized = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            snippet = ""
            highlights = row.get("highlights")
            if isinstance(highlights, list) and highlights:
                snippet = " ".join(str(item).strip() for item in highlights[:3] if str(item).strip())
            snippet = snippet or row.get("summary") or row.get("text") or ""
            normalized.append(
                {
                    "title": row.get("title"),
                    "url": row.get("url"),
                    "snippet": snippet,
                    "text": row.get("text") or snippet,
                    "source": row.get("author") or "exa",
                    "score": row.get("score") or 0.5,
                    "doc_id": row.get("id") or row.get("url"),
                }
            )
        return normalized[: max(1, int(top_k))]
    rows = payload.get("results") or []
    if not isinstance(rows, list):
        raise RuntimeError(f"{provider_name} retrieval response missing results list")
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "snippet": row.get("snippet"),
                "text": row.get("text") or row.get("snippet"),
                "source": row.get("source") or provider_name,
                "score": row.get("score"),
                "doc_id": row.get("doc_id"),
            }
        )
    return normalized[: max(1, int(top_k))]


async def _provider_for_policy_refine(db: AsyncSession) -> dict[str, Any]:
    provider_info = await _provider_for_agent_run(db)
    provider = provider_info["provider"]
    if provider is None:
        return {"rule_generator": None, "source": provider_info["source"]}

    def _rule_generator(**kwargs):
        return _run_async(
            _generate_policy_rule_candidates(
                provider=provider,
                provider_model=str(provider_info["model"] or ""),
                **kwargs,
            )
        )

    return {"rule_generator": _rule_generator, "source": provider_info["source"]}


async def _generate_policy_rule_candidates(
    *,
    provider,
    provider_model: str,
    iteration: int,
    current_policy: dict[str, Any],
    error_summary: dict[str, Any],
    feedback_summary: dict[str, Any],
    validation_metrics: dict[str, Any],
    held_out_audit: dict[str, Any] | None = None,
    historical_rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    payload = {
        "task": "DecisionRuleOptimizerAgent",
        "iteration": iteration,
        "allowed_patch_fields": [
            "review_threshold",
            "abstain_threshold",
            "retrieval_threshold",
            "countermeasure_threshold",
            "trigger_conditions",
            "agent_weights",
        ],
        "must_not_change": [
            "detector_outputs",
            "agent_order",
            "agent_set",
            "workflow_structure",
            "dataset_labels",
        ],
        "current_policy": current_policy,
        "validation_metrics": validation_metrics,
        "held_out_audit": held_out_audit or {},
        "error_summary": error_summary,
        "feedback_summary": feedback_summary,
        "historical_rules": historical_rules or [],
        "expected_output": {
            "candidate_rules": [
                {
                    "rule_id": "string",
                    "source": "DecisionRuleOptimizerAgent",
                    "description": "string",
                    "policy_patch": {
                        "review_threshold": 0.55,
                        "retrieval_threshold": 0.62,
                    },
                }
            ]
        },
    }
    system_prompt = (
        "You are DecisionRuleOptimizerAgent for a MARO-style social-media governance system. "
        "Propose only policy parameter patches in JSON. Do not modify model outputs, agent order, "
        "agent set, or workflow structure. Return strict JSON with candidate_rules."
    )
    response = await provider(
        agent_name="DecisionRuleOptimizerAgent",
        system_prompt=system_prompt,
        user_prompt=json.dumps(payload, ensure_ascii=False),
        input_bundle={"media_inputs": []},
        model=provider_model,
    )
    parsed = json.loads(response)
    if isinstance(parsed, dict):
        return parsed.get("candidate_rules") or []
    if isinstance(parsed, list):
        return parsed
    return []


def _context_ref(context: dict[str, Any], key: str) -> Any:
    refs = context.get("input_refs") or {}
    return refs.get(key)


def _claim_summary(context: dict[str, Any]) -> list[dict[str, Any]]:
    summary = []
    for post in context.get("selected_posts") or []:
        claim = (post.get("primary_claim") or {}).get("claim_text")
        stance = (post.get("stance") or {}).get("label")
        uncertainty = bool((post.get("stance") or {}).get("abstain"))
        if claim:
            summary.append(
                {
                    "post_id": post.get("post_id"),
                    "claim_text": claim,
                    "stance": stance,
                    "uncertain": uncertainty,
                }
            )
    return summary[:10]


def _post_snippets(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for post in context.get("selected_posts") or []:
        rows.append(
            {
                "post_id": post.get("post_id"),
                "excerpt": post.get("excerpt"),
                "ocr_text": ((post.get("evidence") or {}).get("ocr_text")),
                "asr_text": ((post.get("evidence") or {}).get("asr_text")),
                "caption": ((post.get("evidence") or {}).get("caption")),
            }
        )
    return rows[:20]


def _update_job(
    job_id: int,
    *,
    status: str,
    progress: int,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    sync_url = settings.mysql_url.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url)
    result_json = json.dumps(result, ensure_ascii=False, default=str) if result is not None else None
    finished_at = datetime.now(timezone.utc) if status in {"completed", "failed"} else None
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                UPDATE review_jobs
                SET status=:status, progress=:progress, result_json=:result_json,
                    error=:error, finished_at=:finished_at, updated_at=NOW()
                WHERE id=:id
                """
            ),
            {
                "status": status,
                "progress": progress,
                "result_json": result_json,
                "error": error,
                "finished_at": finished_at,
                "id": job_id,
            },
        )
        conn.commit()
    engine.dispose()
