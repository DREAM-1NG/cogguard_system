"""风险评估 ORM 模型（MySQL）。

存储每次风险评估的元数据与完整 JSON 报告，
支持按平台、风险等级、阶段和时间范围查询。
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class RiskAssessment(Base):
    """风险评估表。"""
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True, comment="UUID")
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # 阶段检测
    current_phase: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="seed/synchronize/breakout/saturation/regeneration")
    phase_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    hazard_breakout: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # 综合评分
    overall_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="low/medium/high/critical")

    # D-S 融合
    manipulation_belief: Mapped[float] = mapped_column(Float, nullable=False)
    authenticity_belief: Mapped[float] = mapped_column(Float, nullable=False)
    impact_belief: Mapped[float] = mapped_column(Float, nullable=False)
    conflict_mass: Mapped[float] = mapped_column(Float, nullable=False)
    escalation_required: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="0/1")

    # DISARM 攻击路径
    attack_path_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attack_path_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 完整报告 JSON
    report_json: Mapped[str] = mapped_column(Text, nullable=False)

    # 元数据
    assessed_by: Mapped[int] = mapped_column(Integer, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
