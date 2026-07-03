"""add_kt3_system_tables

Revision ID: 7b4c2f9a0d31
Revises: 1e7f4d2b3c90
Create Date: 2026-07-02 20:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b4c2f9a0d31"
down_revision: Union[str, None] = "1e7f4d2b3c90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kt3_provider_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False, comment="text_llm / vision_llm / retrieval"),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("wire_api", sa.String(length=32), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("supports_vision", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_provider_configs_provider_type"), "kt3_provider_configs", ["provider_type"], unique=False)
    op.create_index(op.f("ix_kt3_provider_configs_is_active"), "kt3_provider_configs", ["is_active"], unique=False)

    op.create_table(
        "kt3_gate_datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=256), nullable=False),
        sa.Column("manifest_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("contract_version", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("raw_payload_json", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_gate_datasets_dataset_id"), "kt3_gate_datasets", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_kt3_gate_datasets_manifest_fingerprint"), "kt3_gate_datasets", ["manifest_fingerprint"], unique=True)

    op.create_table(
        "kt3_gate_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.String(length=192), nullable=False),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("split", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("media_refs_json", sa.Text(), nullable=False),
        sa.Column("media_hashes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_gate_cases_dataset_id"), "kt3_gate_cases", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_kt3_gate_cases_case_id"), "kt3_gate_cases", ["case_id"], unique=False)
    op.create_index(op.f("ix_kt3_gate_cases_layer"), "kt3_gate_cases", ["layer"], unique=False)
    op.create_index(op.f("ix_kt3_gate_cases_split"), "kt3_gate_cases", ["split"], unique=False)

    op.create_table(
        "kt3_gate_labels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("gate_case_id", sa.Integer(), nullable=True),
        sa.Column("label_subject_id", sa.String(length=192), nullable=False),
        sa.Column("label_type", sa.String(length=64), nullable=False),
        sa.Column("label_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_gate_labels_dataset_id"), "kt3_gate_labels", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_kt3_gate_labels_gate_case_id"), "kt3_gate_labels", ["gate_case_id"], unique=False)
    op.create_index(op.f("ix_kt3_gate_labels_label_subject_id"), "kt3_gate_labels", ["label_subject_id"], unique=False)

    op.create_table(
        "kt3_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_jobs_job_type"), "kt3_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_kt3_jobs_status"), "kt3_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_kt3_jobs_created_by"), "kt3_jobs", ["created_by"], unique=False)
    op.create_index(op.f("ix_kt3_jobs_celery_task_id"), "kt3_jobs", ["celery_task_id"], unique=False)

    op.create_table(
        "kt3_agent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=192), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_agents_json", sa.Text(), nullable=False),
        sa.Column("selected_post_ids_json", sa.Text(), nullable=False),
        sa.Column("selected_tree_ids_json", sa.Text(), nullable=False),
        sa.Column("provider_config_id", sa.Integer(), nullable=True),
        sa.Column("active_policy_id", sa.String(length=128), nullable=True),
        sa.Column("input_refs_json", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("audit_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_agent_runs_run_id"), "kt3_agent_runs", ["run_id"], unique=True)
    op.create_index(op.f("ix_kt3_agent_runs_report_id"), "kt3_agent_runs", ["report_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_runs_case_id"), "kt3_agent_runs", ["case_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_runs_status"), "kt3_agent_runs", ["status"], unique=False)

    op.create_table(
        "kt3_agent_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("report_role", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("analysis_text", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sidecar_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_agent_reports_run_id"), "kt3_agent_reports", ["run_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_reports_review_id"), "kt3_agent_reports", ["review_id"], unique=True)
    op.create_index(op.f("ix_kt3_agent_reports_report_id"), "kt3_agent_reports", ["report_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_reports_agent_name"), "kt3_agent_reports", ["agent_name"], unique=False)
    op.create_index(op.f("ix_kt3_agent_reports_status"), "kt3_agent_reports", ["status"], unique=False)

    op.create_table("kt3_agent_report_evidence_refs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("doc_id", sa.String(length=192), nullable=True),
        sa.Column("source", sa.String(length=256), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_agent_report_evidence_refs_review_id"), "kt3_agent_report_evidence_refs", ["review_id"], unique=False)

    op.create_table("kt3_agent_report_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_agent_report_queries_review_id"), "kt3_agent_report_queries", ["review_id"], unique=False)

    op.create_table("kt3_agent_report_uncertainties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("uncertainty", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_agent_report_uncertainties_review_id"), "kt3_agent_report_uncertainties", ["review_id"], unique=False)

    op.create_table("kt3_agent_report_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_agent_report_actions_review_id"), "kt3_agent_report_actions", ["review_id"], unique=False)

    op.create_table("kt3_agent_debate_traces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=True),
        sa.Column("trace_ref", sa.String(length=192), nullable=False),
        sa.Column("debate_mode", sa.String(length=32), nullable=False),
        sa.Column("trace_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_agent_debate_traces_run_id"), "kt3_agent_debate_traces", ["run_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_debate_traces_review_id"), "kt3_agent_debate_traces", ["review_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_debate_traces_trace_ref"), "kt3_agent_debate_traces", ["trace_ref"], unique=False)

    op.create_table(
        "kt3_agent_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feedback_id", sa.String(length=128), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("case_id", sa.String(length=192), nullable=True),
        sa.Column("human_label", sa.String(length=64), nullable=True),
        sa.Column("corrected_label", sa.String(length=64), nullable=True),
        sa.Column("error_types_json", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False),
        sa.Column("reviewer_confidence", sa.Float(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_agent_feedback_feedback_id"), "kt3_agent_feedback", ["feedback_id"], unique=True)
    op.create_index(op.f("ix_kt3_agent_feedback_report_id"), "kt3_agent_feedback", ["report_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_feedback_review_id"), "kt3_agent_feedback", ["review_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_feedback_run_id"), "kt3_agent_feedback", ["run_id"], unique=False)
    op.create_index(op.f("ix_kt3_agent_feedback_case_id"), "kt3_agent_feedback", ["case_id"], unique=False)

    op.create_table(
        "kt3_policies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("baseline_policy_id", sa.String(length=128), nullable=True),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("policy_json", sa.Text(), nullable=False),
        sa.Column("optimization_json", sa.Text(), nullable=False),
        sa.Column("error_memory_summary_json", sa.Text(), nullable=False),
        sa.Column("held_out_audit_json", sa.Text(), nullable=True),
        sa.Column("can_activate", sa.Boolean(), nullable=False),
        sa.Column("non_activatable_reasons_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("activated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt3_policies_policy_id"), "kt3_policies", ["policy_id"], unique=True)
    op.create_index(op.f("ix_kt3_policies_dataset_id"), "kt3_policies", ["dataset_id"], unique=False)

    op.create_table("kt3_policy_agent_weights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_policy_agent_weights_policy_id"), "kt3_policy_agent_weights", ["policy_id"], unique=False)
    op.create_index(op.f("ix_kt3_policy_agent_weights_agent_name"), "kt3_policy_agent_weights", ["agent_name"], unique=False)

    op.create_table("kt3_policy_thresholds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("threshold_name", sa.String(length=64), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_policy_thresholds_policy_id"), "kt3_policy_thresholds", ["policy_id"], unique=False)

    op.create_table("kt3_policy_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("rule_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_policy_rules_policy_id"), "kt3_policy_rules", ["policy_id"], unique=False)
    op.create_index(op.f("ix_kt3_policy_rules_rule_id"), "kt3_policy_rules", ["rule_id"], unique=False)

    op.create_table("kt3_policy_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("split_name", sa.String(length=64), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("metric_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_policy_metrics_policy_id"), "kt3_policy_metrics", ["policy_id"], unique=False)

    op.create_table("kt3_policy_refinement_rounds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("accepted_rule_id", sa.String(length=128), nullable=True),
        sa.Column("trace_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_kt3_policy_refinement_rounds_policy_id"), "kt3_policy_refinement_rounds", ["policy_id"], unique=False)


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_kt3_policy_refinement_rounds_policy_id", "kt3_policy_refinement_rounds"),
        ("ix_kt3_policy_metrics_policy_id", "kt3_policy_metrics"),
        ("ix_kt3_policy_rules_rule_id", "kt3_policy_rules"),
        ("ix_kt3_policy_rules_policy_id", "kt3_policy_rules"),
        ("ix_kt3_policy_thresholds_policy_id", "kt3_policy_thresholds"),
        ("ix_kt3_policy_agent_weights_agent_name", "kt3_policy_agent_weights"),
        ("ix_kt3_policy_agent_weights_policy_id", "kt3_policy_agent_weights"),
        ("ix_kt3_policies_dataset_id", "kt3_policies"),
        ("ix_kt3_policies_policy_id", "kt3_policies"),
        ("ix_kt3_agent_feedback_case_id", "kt3_agent_feedback"),
        ("ix_kt3_agent_feedback_run_id", "kt3_agent_feedback"),
        ("ix_kt3_agent_feedback_review_id", "kt3_agent_feedback"),
        ("ix_kt3_agent_feedback_report_id", "kt3_agent_feedback"),
        ("ix_kt3_agent_feedback_feedback_id", "kt3_agent_feedback"),
        ("ix_kt3_agent_debate_traces_trace_ref", "kt3_agent_debate_traces"),
        ("ix_kt3_agent_debate_traces_review_id", "kt3_agent_debate_traces"),
        ("ix_kt3_agent_debate_traces_run_id", "kt3_agent_debate_traces"),
        ("ix_kt3_agent_report_actions_review_id", "kt3_agent_report_actions"),
        ("ix_kt3_agent_report_uncertainties_review_id", "kt3_agent_report_uncertainties"),
        ("ix_kt3_agent_report_queries_review_id", "kt3_agent_report_queries"),
        ("ix_kt3_agent_report_evidence_refs_review_id", "kt3_agent_report_evidence_refs"),
        ("ix_kt3_agent_reports_status", "kt3_agent_reports"),
        ("ix_kt3_agent_reports_agent_name", "kt3_agent_reports"),
        ("ix_kt3_agent_reports_report_id", "kt3_agent_reports"),
        ("ix_kt3_agent_reports_review_id", "kt3_agent_reports"),
        ("ix_kt3_agent_reports_run_id", "kt3_agent_reports"),
        ("ix_kt3_agent_runs_status", "kt3_agent_runs"),
        ("ix_kt3_agent_runs_case_id", "kt3_agent_runs"),
        ("ix_kt3_agent_runs_report_id", "kt3_agent_runs"),
        ("ix_kt3_agent_runs_run_id", "kt3_agent_runs"),
        ("ix_kt3_jobs_celery_task_id", "kt3_jobs"),
        ("ix_kt3_jobs_created_by", "kt3_jobs"),
        ("ix_kt3_jobs_status", "kt3_jobs"),
        ("ix_kt3_jobs_job_type", "kt3_jobs"),
        ("ix_kt3_gate_labels_label_subject_id", "kt3_gate_labels"),
        ("ix_kt3_gate_labels_gate_case_id", "kt3_gate_labels"),
        ("ix_kt3_gate_labels_dataset_id", "kt3_gate_labels"),
        ("ix_kt3_gate_cases_split", "kt3_gate_cases"),
        ("ix_kt3_gate_cases_layer", "kt3_gate_cases"),
        ("ix_kt3_gate_cases_case_id", "kt3_gate_cases"),
        ("ix_kt3_gate_cases_dataset_id", "kt3_gate_cases"),
        ("ix_kt3_gate_datasets_manifest_fingerprint", "kt3_gate_datasets"),
        ("ix_kt3_gate_datasets_dataset_id", "kt3_gate_datasets"),
        ("ix_kt3_provider_configs_is_active", "kt3_provider_configs"),
        ("ix_kt3_provider_configs_provider_type", "kt3_provider_configs"),
    ]:
        op.drop_index(op.f(index_name), table_name=table_name)
    for table in [
        "kt3_policy_refinement_rounds",
        "kt3_policy_metrics",
        "kt3_policy_rules",
        "kt3_policy_thresholds",
        "kt3_policy_agent_weights",
        "kt3_policies",
        "kt3_agent_feedback",
        "kt3_agent_debate_traces",
        "kt3_agent_report_actions",
        "kt3_agent_report_uncertainties",
        "kt3_agent_report_queries",
        "kt3_agent_report_evidence_refs",
        "kt3_agent_reports",
        "kt3_agent_runs",
        "kt3_jobs",
        "kt3_gate_labels",
        "kt3_gate_cases",
        "kt3_gate_datasets",
        "kt3_provider_configs",
    ]:
        op.drop_table(table)
