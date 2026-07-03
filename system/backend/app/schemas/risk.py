"""风险研判相关的请求 / 响应数据模式。"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 请求模式
# ---------------------------------------------------------------------------

class RiskAssessRequest(BaseModel):
    """风险评估请求体。"""
    platform: str | None = Field(None, description="限定平台（为空则全量）")
    event_id: str | None = Field(None, description="限定事件 ID")
    time_window: int = Field(60, ge=1, le=3600, description="协同检测时间窗口（秒）")
    min_participation: int = Field(2, ge=1, description="最低参与次数")
    edge_weight: float = Field(0.5, ge=0, le=1, description="边权百分位阈值")
    window_minutes: int = Field(30, ge=5, le=360, description="阶段检测滑动窗口（分钟）")


class KT3GateSuiteRequest(BaseModel):
    """KT3 三层 Gate Suite 离线评测请求体。"""
    platform: str | None = Field(None, description="限定平台（为空则全量）")
    event_id: str | None = Field(None, description="限定事件 ID")
    time_window: int = Field(60, ge=1, le=3600, description="协同检测时间窗口（秒）")
    min_participation: int = Field(2, ge=1, description="最低参与次数")
    edge_weight: float = Field(0.5, ge=0, le=1, description="边权百分位阈值")
    kt3_gate_dataset: dict = Field(
        default_factory=dict,
        description=(
            "显式 KT3 gold/control set 契约，包含 metadata、post_cases、"
            "user_gold、community_gold、thresholds。该数据只用于离线评测。"
        ),
    )


class KT3GateDatasetValidationRequest(BaseModel):
    """KT3 Gate Dataset contract validation request."""
    kt3_gate_dataset: dict = Field(
        default_factory=dict,
        description=(
            "KT3 Gate Dataset JSON to validate. This endpoint checks contract "
            "shape only; it does not assess risk, persist results, or use gold "
            "labels for training/calibration."
        ),
    )


class KT3AgentReviewRunRequest(BaseModel):
    """Analyst-triggered KT3 MARO-style LLM agent review request."""
    report_id: str = Field(..., description="Persisted risk report ID to review")
    case_id: str | None = Field(None, description="Optional case/thread identifier for analyst context")
    selected_post_ids: list[str] = Field(
        default_factory=list,
        description="Post IDs selected by the analyst for LLM agent review",
    )
    selected_tree_ids: list[str] = Field(
        default_factory=list,
        description="Propagation tree/thread IDs selected by the analyst",
    )
    agent_names: list[str] = Field(
        default_factory=list,
        description=(
            "Selected agents. Supported values include PostHarmAgent, "
            "MultimodalConsistencyAgent, ClaimEvidenceAgent, PropagationTreeAgent, "
            "QuestionReflectionAgent, HarmfulnessJudgeAgent, CountermeasureAgent."
        ),
    )
    enable_active_retrieval: bool = Field(
        False,
        description="Run active evidence retrieval during manual review",
    )
    enable_external_retrieval: bool | None = Field(
        None,
        description=(
            "Whether manual review should try external retrieval in addition to local evidence. "
            "None means use the manual-review default when active retrieval is enabled."
        ),
    )
    enable_light_debate: bool = Field(
        False,
        description="Run lightweight debate trace when conflict/uncertainty triggers are present",
    )
    enable_full_debate: bool = Field(
        False,
        description="Run optional multi-round LLM debate when high-conflict triggers are present",
    )
    debate_max_rounds: int = Field(
        3,
        ge=1,
        le=5,
        description="Maximum free-debate rounds for optional full debate",
    )
    policy_id: str | None = Field(None, description="Optional optimized KT3 Agent policy ID")
    active_policy_id: str | None = Field(
        None,
        description="Optional activated KT3 policy ID to inject into Judge/Agent context",
    )
    retrieval_top_k: int = Field(3, ge=1, le=10, description="Top-k evidence per active retrieval query")


class KT3PolicyOptimizeRequest(BaseModel):
    """Request body for MARO-style KT3 review policy optimization."""
    dataset_manifest: dict = Field(
        default_factory=dict,
        description=(
            "Explicit manifest with splits.validation and optional splits.held_out/gate. "
            "Validation is used for policy optimization; held-out/gate is evaluation only."
        ),
    )


class KT3PolicyRefineRequest(BaseModel):
    """Request body for MARO-style self-iterative KT3 policy refinement."""
    dataset_manifest: dict = Field(
        default_factory=dict,
        description="Explicit manifest with validation and held-out/gate splits",
    )
    feedback_report_ids: list[str] = Field(
        default_factory=list,
        description="Risk report IDs whose report_json.agent_feedback should feed error memory",
    )
    baseline_policy_id: str | None = Field(None, description="Optional stored policy used as refinement baseline")
    max_iterations: int = Field(3, ge=1, le=8, description="Maximum rule refinement iterations")
    enable_llm_rule_generator: bool = Field(
        False,
        description="Enable DecisionRuleOptimizerAgent rule proposal hook; deterministic evaluator remains mandatory",
    )
    held_out_required: bool = Field(
        True,
        description="Require held-out/gate split audit before candidate policy can be activatable",
    )


class KT3ProviderConfigRequest(BaseModel):
    """Create/update request for KT3 LLM or retrieval providers."""
    name: str = Field(..., min_length=1, max_length=128)
    provider_type: str = Field(..., description="text_llm | vision_llm | retrieval")
    base_url: str = Field("", description="OpenAI-compatible base URL or retrieval endpoint")
    model: str = Field("", description="Provider model identifier")
    wire_api: str = Field("chat_completions", description="chat_completions | responses")
    api_key: str | None = Field(None, description="Plaintext key; encrypted server-side and never returned")
    supports_vision: bool = Field(False)
    metadata: dict = Field(default_factory=dict)


class KT3ProviderUpdateRequest(BaseModel):
    """Partial update request for KT3 provider configs."""
    name: str | None = Field(None, min_length=1, max_length=128)
    provider_type: str | None = Field(None, description="text_llm | vision_llm | retrieval")
    base_url: str | None = Field(None, description="OpenAI-compatible base URL or retrieval endpoint")
    model: str | None = Field(None, description="Provider model identifier")
    wire_api: str | None = Field(None, description="chat_completions | responses")
    api_key: str | None = Field(None, description="Plaintext key; encrypted server-side and never returned")
    supports_vision: bool | None = Field(None)
    metadata: dict | None = Field(None)


class KT3ProviderActivateRequest(BaseModel):
    """Activate/deactivate a provider for its capability bucket."""
    is_active: bool = Field(True)


class KT3GateDatasetUploadRequest(BaseModel):
    """JSON-body alternative to multipart Gate Dataset upload."""
    kt3_gate_dataset: dict = Field(default_factory=dict)


class KT3BackfillRequest(BaseModel):
    """Start idempotent backfill from legacy RiskAssessment.report_json."""
    report_ids: list[str] = Field(default_factory=list)
    limit: int = Field(500, ge=1, le=5000)


class KT3AgentFeedbackRequest(BaseModel):
    """Human audit feedback appended to RiskAssessment.report_json.agent_feedback."""
    report_id: str = Field(..., description="Persisted risk report ID")
    review_id: str | None = Field(None, description="Agent review ID being corrected")
    run_id: str | None = Field(None, description="Agent review run ID being corrected")
    case_id: str | None = Field(None, description="Case/thread/post identifier")
    human_label: str | None = Field(None, description="Human-readable feedback label")
    corrected_harmfulness: str | None = Field(None, description="Corrected harmfulness label")
    corrected_label: str | None = Field(None, description="Alias for corrected_harmfulness")
    error_types: list[str] = Field(default_factory=list, description="Error types such as false_positive/false_negative")
    notes: str = Field("", description="Human reviewer notes")
    evidence_refs: list[dict] = Field(default_factory=list, description="Evidence references supporting the correction")
    reviewer_confidence: float = Field(0.5, ge=0, le=1, description="Reviewer confidence in the correction")


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
    post_semantics: dict | None = None
    kt3_harmfulness: dict | None = None
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
