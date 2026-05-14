"""风险研判相关的请求 / 响应数据模式。"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 请求模式
# ---------------------------------------------------------------------------

class RiskAssessRequest(BaseModel):
    """风险评估请求体。"""
    platform: str | None = Field(None, description="限定平台（为空则全量）")
    time_window: int = Field(60, ge=1, le=3600, description="协同检测时间窗口（秒）")
    min_participation: int = Field(2, ge=1, description="最低参与次数")
    edge_weight: float = Field(0.5, ge=0, le=1, description="边权百分位阈值")
    window_minutes: int = Field(30, ge=5, le=360, description="阶段检测滑动窗口（分钟）")


class RiskListQuery(BaseModel):
    """风险报告列表查询参数。"""
    platform: str | None = None
    risk_level: str | None = None
    phase: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ---------------------------------------------------------------------------
# 内部数据结构
# ---------------------------------------------------------------------------

class BeliefInterval(BaseModel):
    """D-S 证据理论的信念区间。"""
    belief: float = Field(..., ge=0, le=1, description="信念下界")
    plausibility: float = Field(..., ge=0, le=1, description="似然上界")


class DimensionScore(BaseModel):
    """单维度评分（含 D-S 信念区间）。"""
    score: float = Field(..., ge=0, le=100)
    belief: float = Field(..., ge=0, le=1)
    plausibility: float = Field(..., ge=0, le=1)


# ---------------------------------------------------------------------------
# 响应模式
# ---------------------------------------------------------------------------

class PhaseResponse(BaseModel):
    """阶段检测结果。"""
    current_phase: str
    phase_confidence: float
    hazard_scores: dict[str, float]
    time_to_breakout_estimate: float | None = None
    window_count: int = 0


class ScoresResponse(BaseModel):
    """综合评分结果（含 D-S 信念区间）。"""
    overall_risk_score: float = Field(..., ge=0, le=100)
    risk_level: str
    manipulation: DimensionScore
    authenticity: DimensionScore
    impact: DimensionScore


class FusionResponse(BaseModel):
    """D-S 融合结果。"""
    conflict_mass: float
    escalation_required: bool
    per_source_masses: dict


class ObservedTechniqueResponse(BaseModel):
    """观测到的 DISARM 技术。"""
    technique_id: str
    tactic: str
    name: str
    belief: float
    evidence: str


class PredictedTechniqueResponse(BaseModel):
    """预测的下一步 DISARM 技术。"""
    technique_id: str
    name: str
    probability: float


class CountermeasureResponse(BaseModel):
    """反制建议。"""
    technique_id: str
    action: str
    priority: str
    probability: float = 0.0


class AttackPathResponse(BaseModel):
    """攻击路径评分。"""
    depth: int
    breadth: int
    completeness: float
    score: float


class DisarmAnalysisResponse(BaseModel):
    """DISARM 分析结果。"""
    observed_techniques: list[ObservedTechniqueResponse]
    attack_path: AttackPathResponse
    predicted_next: list[PredictedTechniqueResponse]
    countermeasures: list[CountermeasureResponse]


class RiskReportResponse(BaseModel):
    """完整风险评估报告响应体。"""
    report_id: str
    event_id: str
    platform: str
    assessed_at: datetime
    phase: PhaseResponse
    scores: ScoresResponse
    fusion: FusionResponse
    evidence: dict
    claims: list[dict]
    disarm_analysis: DisarmAnalysisResponse
    risk_factors: dict[str, list[str]]
    recommendations: list[dict]


class RiskReportSummary(BaseModel):
    """风险报告摘要（列表用）。"""
    report_id: str
    event_id: str
    platform: str
    assessed_at: datetime
    overall_risk_score: float
    risk_level: str
    current_phase: str
    conflict_mass: float
    escalation_required: bool
    attack_path_score: float

    model_config = {"from_attributes": True}


class RiskReportListResponse(BaseModel):
    """风险报告列表响应体。"""
    total: int
    items: list[RiskReportSummary]
