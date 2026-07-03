"""KT3 main-system persistence models.

These tables make the MARO-style KT3 layer auditable without turning the
natural-language Agent reports into classifier JSON. Large media objects are
kept as references/hashes instead of being stored in MySQL.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class KT3ProviderConfig(Base):
    """OpenAI-compatible LLM/retrieval provider config with encrypted key."""

    __tablename__ = "kt3_provider_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="text_llm / vision_llm / retrieval",
    )
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    wire_api: Mapped[str] = mapped_column(String(32), nullable=False, default="chat_completions")
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KT3GateDataset(Base):
    """Uploaded KT3 Gate Dataset manifest and provenance."""

    __tablename__ = "kt3_gate_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    manifest_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False, default="kt3-gate-dataset-v1")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    raw_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KT3GateCase(Base):
    """A normalized post/user/community gate case row."""

    __tablename__ = "kt3_gate_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    split: Mapped[str] = mapped_column(String(32), nullable=False, default="unspecified", index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    media_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    media_hashes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KT3GateLabel(Base):
    """Gold label row attached to a gate case."""

    __tablename__ = "kt3_gate_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gate_case_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    label_subject_id: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    label_type: Mapped[str] = mapped_column(String(64), nullable=False, default="gold")
    label_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KT3Job(Base):
    """Background job used by KT3 Agent review/refinement/backfill flows."""

    __tablename__ = "kt3_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KT3AgentRun(Base):
    """One analyst-triggered MARO Agent run."""

    __tablename__ = "kt3_agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    report_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(String(192), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    requested_agents_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    selected_post_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    selected_tree_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    provider_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    audit_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KT3AgentReport(Base):
    """Natural-language Agent report. Sidecar details live in child tables."""

    __tablename__ = "kt3_agent_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    review_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    report_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_role: Mapped[str] = mapped_column(String(64), nullable=False, default="expert_initial")
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    analysis_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sidecar_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KT3AgentReportEvidenceRef(Base):
    __tablename__ = "kt3_agent_report_evidence_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    doc_id: Mapped[str | None] = mapped_column(String(192), nullable=True)
    source: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class KT3AgentReportQuery(Base):
    __tablename__ = "kt3_agent_report_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class KT3AgentReportUncertainty(Base):
    __tablename__ = "kt3_agent_report_uncertainties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    uncertainty: Mapped[str] = mapped_column(Text, nullable=False)


class KT3AgentReportAction(Base):
    __tablename__ = "kt3_agent_report_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)


class KT3AgentDebateTrace(Base):
    __tablename__ = "kt3_agent_debate_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    review_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    trace_ref: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    debate_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="light_debate")
    trace_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class KT3AgentFeedback(Base):
    __tablename__ = "kt3_agent_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    report_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    review_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    case_id: Mapped[str | None] = mapped_column(String(192), nullable=True, index=True)
    human_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    corrected_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_types_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reviewer_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KT3Policy(Base):
    __tablename__ = "kt3_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate_pending_human_approval")
    baseline_policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dataset_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    optimization_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_memory_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    held_out_audit_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    can_activate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    non_activatable_reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KT3PolicyAgentWeight(Base):
    __tablename__ = "kt3_policy_agent_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)


class KT3PolicyThreshold(Base):
    __tablename__ = "kt3_policy_thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    threshold_name: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)


class KT3PolicyRule(Base):
    __tablename__ = "kt3_policy_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    rule_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class KT3PolicyMetric(Base):
    __tablename__ = "kt3_policy_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    split_name: Mapped[str] = mapped_column(String(64), nullable=False, default="validation")
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    metric_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class KT3PolicyRefinementRound(Base):
    __tablename__ = "kt3_policy_refinement_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trace_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
