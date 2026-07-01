"""Risk assessment orchestration service."""

from __future__ import annotations

import json

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.risk.disarm_scorer import score_attack_path_full
from app.core.risk.ds_fusion import fuse_evidence
from app.core.risk.evidence_builder import build_evidence_pack
from app.core.risk.kt3_agent_review import agent_review_suggestions
from app.core.risk.kt3_agent_review import build_llm_provider_from_settings
from app.core.risk.kt3_agent_review import run_manual_kt3_agent_review
from app.core.risk.kt3_agent_policy import apply_policy_to_agent_suggestions
from app.core.risk.kt3_agent_policy import DEFAULT_POLICY
from app.core.risk.kt3_agent_policy import optimize_kt3_agent_policy
from app.core.risk.kt3_agent_policy import refine_kt3_agent_policy_loop
from app.core.risk.kt3_gate_suite import evaluate_kt3_gate_suite
from app.core.risk.kt3_graph_exporter import export_kt3_heterogeneous_graph
from app.core.risk.kt3_multi_agent import execute_kt3_multi_agent_review
from app.core.risk.kt3_review_executor import execute_kt3_review_queue
from app.core.risk.kt3_reviewer import build_kt3_review_queue
from app.core.risk.kt3_user_mil import score_user_mil
from app.core.risk.layered_harmfulness import assess_layered_harmfulness
from app.core.risk.phase_detector import detect_phase
from app.core.risk.post_semantics import assess_post_semantics
from app.core.risk.report_builder import build_report
from app.config import settings
from app.db.mongodb import get_mongo_db
from app.models.risk_assessment import RiskAssessment
from app.services.event_data import load_event_posts
from app.services import account_service, coordination_service, propagation_service

_KT3_POLICY_REGISTRY: dict[str, dict] = {}
_KT3_ACTIVE_POLICY_ID: str | None = None


async def assess_risk(
    platform: str | None = None,
    time_window: int = 60,
    min_participation: int = 2,
    edge_weight: float = 0.5,
    user_id: int = 0,
    db: AsyncSession | None = None,
    event_id: str | None = None,
    kt3_gate_dataset: dict | None = None,
    run_legacy_multi_agent: bool = False,
) -> dict:
    """Run the full risk assessment pipeline over one optional event scope."""
    coord_data = await coordination_service.run_coordination_detection(
        time_window=time_window,
        min_participation=min_participation,
        edge_weight=edge_weight,
        platform=platform,
        event_id=event_id,
    )
    prop_data = await propagation_service.analyze_propagation(platform=platform, event_id=event_id)
    acct_data = await account_service.get_account_profiles(platform=platform, event_id=event_id)

    evidence_pack = build_evidence_pack(coord_data, prop_data, acct_data)
    phase_result = detect_phase(evidence_pack)
    fusion_result = fuse_evidence(evidence_pack, phase_result)
    disarm_result = score_attack_path_full(evidence_pack, phase_result, fusion_result)
    posts = await _load_posts_for_semantics(platform=platform, event_id=event_id, prop_data=prop_data)
    post_semantics = assess_post_semantics(posts, prop_data) if posts else None

    report_event_id = event_id or platform or "all_platforms"
    kt3_harmfulness = (
        assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=acct_data,
            coordination=coord_data,
            propagation=prop_data,
            event_id=report_event_id,
            platform=platform or "all",
        )
        if post_semantics
        else None
    )
    if kt3_harmfulness is not None:
        kt3_harmfulness["user_mil"] = score_user_mil(
            post_semantics=post_semantics,
            account_profiles=acct_data,
            coordination=coord_data,
            propagation=prop_data,
            existing_user_level=kt3_harmfulness.get("user_level"),
            event_id=report_event_id,
            platform=platform or "all",
        )
        kt3_harmfulness["graph_export"] = export_kt3_heterogeneous_graph(
            post_semantics=post_semantics,
            kt3_harmfulness=kt3_harmfulness,
            coordination=coord_data,
            propagation=prop_data,
        )
        kt3_harmfulness["review_queue"] = build_kt3_review_queue(
            post_semantics=post_semantics,
            kt3_harmfulness=kt3_harmfulness,
        )
        kt3_harmfulness["review_execution"] = execute_kt3_review_queue(
            post_semantics=post_semantics,
            kt3_harmfulness=kt3_harmfulness,
            review_queue=kt3_harmfulness["review_queue"],
        )
        kt3_harmfulness["agent_review_suggestions"] = apply_policy_to_agent_suggestions(
            agent_review_suggestions(
                {
                    "report_id": None,
                    "event_id": report_event_id,
                    "platform": platform or "all",
                    "post_semantics": post_semantics,
                    "kt3_harmfulness": kt3_harmfulness,
                }
            ),
            {"policy_id": "kt3-default-policy", "policy": DEFAULT_POLICY},
        )
        if run_legacy_multi_agent:
            kt3_harmfulness["multi_agent_review"] = execute_kt3_multi_agent_review(
                post_semantics=post_semantics,
                kt3_harmfulness=kt3_harmfulness,
                user_mil=kt3_harmfulness["user_mil"],
                graph_export=kt3_harmfulness["graph_export"],
                review_execution=kt3_harmfulness["review_execution"],
            )
        else:
            kt3_harmfulness["multi_agent_review"] = {
                "capability_boundary": {
                    "status": "disabled_by_default",
                    "manual_llm_agent_review": True,
                    "legacy_deterministic_runtime_available": True,
                    "description": (
                        "KT3 LLM agents are analyst-triggered. The legacy "
                        "deterministic multi-agent runtime is not executed by "
                        "default during risk assessment."
                    ),
                },
                "summary": {"agents_executed": 0, "manual_trigger_required": True},
                "agent_results": [],
            }
        kt3_harmfulness["gate_suite"] = evaluate_kt3_gate_suite(
            gate_dataset=kt3_gate_dataset,
            kt3_harmfulness=kt3_harmfulness,
            graph_export=kt3_harmfulness["graph_export"],
        )
    report = build_report(
        event_id=report_event_id,
        platform=platform or "all",
        evidence_pack=evidence_pack,
        phase_result=phase_result,
        fusion_result=fusion_result,
        disarm_result=disarm_result,
        post_semantics=post_semantics,
        kt3_harmfulness=kt3_harmfulness,
    )

    if db is not None:
        scores = report["scores"]
        phase = report["phase"]
        fusion = report["fusion"]
        row = RiskAssessment(
            report_id=report["report_id"],
            event_id=report["event_id"],
            platform=report["platform"],
            current_phase=phase["current_phase"],
            phase_confidence=phase["phase_confidence"],
            hazard_breakout=phase["hazard_scores"].get("breakout", 0),
            overall_risk_score=scores["overall_risk_score"],
            risk_level=scores["risk_level"],
            manipulation_belief=scores["manipulation"]["belief"],
            authenticity_belief=scores["authenticity"]["belief"],
            impact_belief=scores["impact"]["belief"],
            conflict_mass=fusion["conflict_mass"],
            escalation_required=1 if fusion["escalation_required"] else 0,
            attack_path_score=report["disarm_analysis"]["attack_path"]["score"],
            attack_path_depth=report["disarm_analysis"]["attack_path"]["depth"],
            report_json=json.dumps(report, ensure_ascii=False, default=str),
            assessed_by=user_id,
        )
        db.add(row)

    return report


async def run_kt3_agent_review(
    *,
    report_id: str,
    agent_names: list[str],
    case_id: str | None = None,
    selected_post_ids: list[str] | None = None,
    selected_tree_ids: list[str] | None = None,
    enable_active_retrieval: bool = False,
    enable_light_debate: bool = False,
    enable_full_debate: bool = False,
    debate_max_rounds: int = 3,
    policy_id: str | None = None,
    active_policy_id: str | None = None,
    retrieval_top_k: int = 3,
    user_id: int = 0,
    db: AsyncSession | None = None,
    provider=None,
    active_retriever=None,
) -> dict:
    """Run analyst-triggered KT3 LLM agent reports and append them to report JSON."""
    if db is None:
        raise ValueError("db is required for persisted KT3 agent reviews")
    stmt = select(RiskAssessment).where(RiskAssessment.report_id == report_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"risk report not found: {report_id}")

    report = json.loads(row.report_json)
    llm_provider = provider if provider is not None else build_llm_provider_from_settings(settings)
    selected_policy_id = active_policy_id or policy_id or _KT3_ACTIVE_POLICY_ID
    policy = _KT3_POLICY_REGISTRY.get(selected_policy_id or "") if selected_policy_id else None
    review_result = await run_manual_kt3_agent_review(
        report=report,
        agent_names=agent_names,
        case_id=case_id,
        selected_post_ids=selected_post_ids or [],
        selected_tree_ids=selected_tree_ids or [],
        human_triggered_by=user_id,
        provider=llm_provider,
        model=settings.LLM_MODEL,
        provider_name="openai-compatible",
        include_media_base64=bool(getattr(settings, "LLM_INCLUDE_MEDIA_BASE64", False)),
        require_vision=bool(getattr(settings, "LLM_REQUIRE_VISION", False)),
        enable_active_retrieval=enable_active_retrieval,
        enable_light_debate=enable_light_debate,
        enable_full_debate=enable_full_debate,
        debate_max_rounds=debate_max_rounds,
        retrieval_top_k=retrieval_top_k,
        active_retriever=active_retriever,
        external_retrieval_enabled=bool(getattr(settings, "KT3_EXTERNAL_RETRIEVAL_ENABLED", False)),
        policy=policy,
    )
    existing_reviews = report.get("agent_reviews")
    if not isinstance(existing_reviews, list):
        existing_reviews = []
    existing_reviews.extend(review_result["agent_reports"])
    report["agent_reviews"] = existing_reviews
    existing_runs = report.get("agent_review_runs")
    if not isinstance(existing_runs, list):
        existing_runs = []
    report["agent_review_runs"] = [*existing_runs, review_result["audit"]]
    kt3 = report.get("kt3_harmfulness")
    if isinstance(kt3, dict):
        kt3["agent_review_suggestions"] = apply_policy_to_agent_suggestions(
            agent_review_suggestions(report),
            policy,
        )

    row.report_json = json.dumps(report, ensure_ascii=False, default=str)
    await db.flush()
    return {
        "report_id": report_id,
        "review_result": review_result,
        "agent_reviews": review_result["agent_reports"],
        "summary": review_result["summary"],
        "persistence": {"persisted": True, "target": "risk_assessments.report_json.agent_reviews"},
    }


def optimize_kt3_policy(dataset_manifest: dict) -> dict:
    """Optimize and store an auditable KT3 Agent review policy."""
    result = optimize_kt3_agent_policy(dataset_manifest)
    _KT3_POLICY_REGISTRY[result["policy_id"]] = result
    return result


async def record_kt3_agent_feedback(
    *,
    report_id: str,
    feedback: dict,
    user_id: int = 0,
    db: AsyncSession | None = None,
) -> dict:
    """Append human audit feedback to RiskAssessment.report_json.agent_feedback."""
    if db is None:
        raise ValueError("db is required for persisted KT3 agent feedback")
    stmt = select(RiskAssessment).where(RiskAssessment.report_id == report_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"risk report not found: {report_id}")
    report = json.loads(row.report_json)
    feedback_rows = report.get("agent_feedback")
    if not isinstance(feedback_rows, list):
        feedback_rows = []
    corrected_label = feedback.get("corrected_label") or feedback.get("corrected_harmfulness")
    record = {
        "feedback_id": f"kt3-feedback-{len(feedback_rows) + 1}",
        "report_id": report_id,
        "review_id": feedback.get("review_id"),
        "run_id": feedback.get("run_id"),
        "case_id": feedback.get("case_id"),
        "human_label": feedback.get("human_label"),
        "corrected_harmfulness": corrected_label,
        "corrected_label": corrected_label,
        "error_types": feedback.get("error_types") or [],
        "notes": feedback.get("notes") or "",
        "evidence_refs": feedback.get("evidence_refs") or [],
        "reviewer_confidence": feedback.get("reviewer_confidence", 0.5),
        "created_at": _utc_now(),
        "human_triggered_by": str(user_id),
        "capability_boundary": {
            "human_feedback_memory": True,
            "does_not_overwrite_detector_outputs": True,
            "used_by_next_policy_refinement_only": True,
        },
    }
    feedback_rows.append(record)
    report["agent_feedback"] = feedback_rows
    row.report_json = json.dumps(report, ensure_ascii=False, default=str)
    await db.flush()
    return {
        "report_id": report_id,
        "feedback": record,
        "summary": {"feedback_count": len(feedback_rows)},
        "persistence": {"persisted": True, "target": "risk_assessments.report_json.agent_feedback"},
    }


async def refine_kt3_policy(
    *,
    dataset_manifest: dict,
    feedback_report_ids: list[str] | None = None,
    baseline_policy_id: str | None = None,
    max_iterations: int = 3,
    enable_llm_rule_generator: bool = False,
    held_out_required: bool = True,
    db: AsyncSession | None = None,
    rule_generator=None,
) -> dict:
    """Run MARO-style rule refinement and store the candidate policy."""
    feedback_memory = []
    if feedback_report_ids and db is not None:
        feedback_memory = await _load_agent_feedback(feedback_report_ids, db)
    baseline = _KT3_POLICY_REGISTRY.get(baseline_policy_id or "") if baseline_policy_id else None
    baseline_policy = baseline.get("policy") if isinstance(baseline, dict) else None
    result = refine_kt3_agent_policy_loop(
        dataset_manifest,
        feedback_memory=feedback_memory,
        baseline_policy=baseline_policy,
        max_iterations=max_iterations,
        enable_llm_rule_generator=enable_llm_rule_generator,
        rule_generator=rule_generator,
        held_out_required=held_out_required,
    )
    _KT3_POLICY_REGISTRY[result["policy_id"]] = result
    return result


def activate_kt3_policy(policy_id: str, *, user_id: int | str = 0) -> dict:
    """Explicitly activate a candidate policy for future manual Judge context."""
    global _KT3_ACTIVE_POLICY_ID
    policy = _KT3_POLICY_REGISTRY.get(policy_id)
    if policy is None:
        raise ValueError(f"KT3 policy not found: {policy_id}")
    if policy.get("can_activate") is False:
        reasons = ", ".join(policy.get("non_activatable_reasons") or ["unknown_reason"])
        raise ValueError(f"KT3 policy cannot be activated: {reasons}")
    activated = dict(policy)
    activated["activation_status"] = "active_human_approved"
    activated["activated_by"] = str(user_id)
    activated["activated_at"] = _utc_now()
    _KT3_POLICY_REGISTRY[policy_id] = activated
    _KT3_ACTIVE_POLICY_ID = policy_id
    return {
        "policy_id": policy_id,
        "activation_status": activated["activation_status"],
        "activated_by": activated["activated_by"],
        "activated_at": activated["activated_at"],
        "active_policy": activated,
        "capability_boundary": {
            "human_approved_activation": True,
            "does_not_execute_llm": True,
            "does_not_modify_detector_outputs": True,
        },
    }


def get_kt3_policy(policy_id: str) -> dict | None:
    """Return a stored in-process KT3 policy artifact."""
    return _KT3_POLICY_REGISTRY.get(policy_id)


async def _load_agent_feedback(report_ids: list[str], db: AsyncSession) -> list[dict]:
    feedback_rows: list[dict] = []
    for report_id in report_ids:
        stmt = select(RiskAssessment).where(RiskAssessment.report_id == report_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            continue
        try:
            report = json.loads(row.report_json)
        except Exception:
            continue
        for item in report.get("agent_feedback") or []:
            if isinstance(item, dict):
                feedback_rows.append(item)
    return feedback_rows


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


async def _load_posts_for_semantics(
    *,
    platform: str | None,
    event_id: str | None,
    prop_data: dict,
) -> list[dict]:
    """Prefer raw posts from MongoDB and gracefully fall back to propagation timeline."""
    try:
        mongo_db = get_mongo_db()
        posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
        if posts:
            return posts
    except Exception:
        pass

    fallback_posts = []
    for row in prop_data.get("timeline") or []:
        fallback_posts.append(
            {
                "post_id": row.get("post_id", ""),
                "author_id": row.get("author_id", ""),
                "author_name": row.get("author_name", ""),
                "platform": platform or "",
                "event_id": event_id,
                "content": row.get("content", ""),
                "hashtags": [],
                "media_urls": [],
                "raw_data": {},
            }
        )
    return fallback_posts


async def list_reports(
    platform: str | None = None,
    risk_level: str | None = None,
    phase: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession | None = None,
    event_id: str | None = None,
) -> tuple[list[dict], int]:
    """List persisted risk reports, optionally filtered by event/platform."""
    if db is None:
        return [], 0

    stmt = select(RiskAssessment)
    count_stmt = select(func.count(RiskAssessment.id))

    if event_id:
        stmt = stmt.where(RiskAssessment.event_id == event_id)
        count_stmt = count_stmt.where(RiskAssessment.event_id == event_id)
    if platform:
        stmt = stmt.where(RiskAssessment.platform == platform)
        count_stmt = count_stmt.where(RiskAssessment.platform == platform)
    if risk_level:
        stmt = stmt.where(RiskAssessment.risk_level == risk_level)
        count_stmt = count_stmt.where(RiskAssessment.risk_level == risk_level)
    if phase:
        stmt = stmt.where(RiskAssessment.current_phase == phase)
        count_stmt = count_stmt.where(RiskAssessment.current_phase == phase)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(desc(RiskAssessment.assessed_at))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = [
        {
            "report_id": row.report_id,
            "event_id": row.event_id,
            "platform": row.platform,
            "assessed_at": row.assessed_at.isoformat() if row.assessed_at else None,
            "overall_risk_score": row.overall_risk_score,
            "risk_level": row.risk_level,
            "current_phase": row.current_phase,
            "conflict_mass": row.conflict_mass,
            "escalation_required": bool(row.escalation_required),
            "attack_path_score": row.attack_path_score,
        }
        for row in rows
    ]
    return items, total


async def get_report_detail(report_id: str, db: AsyncSession) -> dict | None:
    """Return the full JSON payload for one persisted risk report."""
    stmt = select(RiskAssessment).where(RiskAssessment.report_id == report_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return json.loads(row.report_json)
