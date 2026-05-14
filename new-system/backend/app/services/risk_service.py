"""风险研判业务逻辑服务。

编排完整风险评估流水线：
  上游数据 → 证据构建 → 阶段检测 → D-S 融合 → DISARM 评分 → 报告生成 → 持久化
"""

from __future__ import annotations

import json

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.risk.disarm_scorer import score_attack_path_full
from app.core.risk.ds_fusion import fuse_evidence
from app.core.risk.evidence_builder import build_evidence_pack
from app.core.risk.phase_detector import detect_phase
from app.core.risk.report_builder import build_report
from app.models.risk_assessment import RiskAssessment
from app.services import coordination_service, propagation_service, account_service


async def assess_risk(
    platform: str | None = None,
    time_window: int = 60,
    min_participation: int = 2,
    edge_weight: float = 0.5,
    user_id: int = 0,
    db: AsyncSession | None = None,
) -> dict:
    """执行完整风险评估流水线。"""

    # 1. 调用上游服务
    coord_data = await coordination_service.run_coordination_detection(
        time_window=time_window,
        min_participation=min_participation,
        edge_weight=edge_weight,
        platform=platform,
    )
    prop_data = await propagation_service.analyze_propagation(platform=platform)
    acct_data = await account_service.get_account_profiles(platform=platform)

    # 2. 构建证据包
    evidence_pack = build_evidence_pack(coord_data, prop_data, acct_data)

    # 3. 阶段检测
    phase_result = detect_phase(evidence_pack)

    # 4. D-S 证据融合
    fusion_result = fuse_evidence(evidence_pack, phase_result)

    # 5. DISARM 攻击路径评分
    disarm_result = score_attack_path_full(evidence_pack, phase_result, fusion_result)

    # 6. 组装报告
    event_id = platform or "all_platforms"
    report = build_report(
        event_id=event_id,
        platform=platform or "all",
        evidence_pack=evidence_pack,
        phase_result=phase_result,
        fusion_result=fusion_result,
        disarm_result=disarm_result,
    )

    # 7. 持久化到 MySQL
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
) -> tuple[list[dict], int]:
    """查询历史风险报告列表。"""
    if db is None:
        return [], 0

    stmt = select(RiskAssessment)
    count_stmt = select(func.count(RiskAssessment.id))

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
            "report_id": r.report_id,
            "event_id": r.event_id,
            "platform": r.platform,
            "assessed_at": r.assessed_at.isoformat() if r.assessed_at else None,
            "overall_risk_score": r.overall_risk_score,
            "risk_level": r.risk_level,
            "current_phase": r.current_phase,
            "conflict_mass": r.conflict_mass,
            "escalation_required": bool(r.escalation_required),
            "attack_path_score": r.attack_path_score,
        }
        for r in rows
    ]
    return items, total


async def get_report_detail(report_id: str, db: AsyncSession) -> dict | None:
    """获取单个报告的完整 JSON。"""
    stmt = select(RiskAssessment).where(RiskAssessment.report_id == report_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return json.loads(row.report_json)
