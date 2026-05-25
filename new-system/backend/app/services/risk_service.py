"""Risk assessment orchestration service."""

from __future__ import annotations

import json

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.risk.disarm_scorer import score_attack_path_full
from app.core.risk.ds_fusion import fuse_evidence
from app.core.risk.evidence_builder import build_evidence_pack
from app.core.risk.phase_detector import detect_phase
from app.core.risk.report_builder import build_report
from app.models.risk_assessment import RiskAssessment
from app.services import account_service, coordination_service, propagation_service


async def assess_risk(
    platform: str | None = None,
    time_window: int = 60,
    min_participation: int = 2,
    edge_weight: float = 0.5,
    user_id: int = 0,
    db: AsyncSession | None = None,
    event_id: str | None = None,
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

    report_event_id = event_id or platform or "all_platforms"
    report = build_report(
        event_id=report_event_id,
        platform=platform or "all",
        evidence_pack=evidence_pack,
        phase_result=phase_result,
        fusion_result=fusion_result,
        disarm_result=disarm_result,
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
