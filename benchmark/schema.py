from __future__ import annotations

import math

from typing import Dict, Iterable, List, Mapping


REPRODUCTION_LEVELS = {
    "local_baseline",
    "public_code_adapter",
    "protocol_proxy_not_original_architecture",
    "planned_frontier_reproduction",
    "not_run",
    "frontier_data_adapter_ready_not_model_run",
    "frontier_reproduction_attempted",
    "frontier_reproduction_small_run",
    "frontier_reproduction_full_run",
    "kt2_joint_model_small_run",
    "kt2_joint_model_full_run",
    "kt2_sequence_joint_model_small_run",
    "kt2_sequence_joint_model_full_run",
}

TASKS = {"scale", "next_hop", "multi_scale", "bot_detection"}
STATUSES = {
    "ok",
    "failed",
    "skipped",
    "missing_data",
    "missing_external_repo",
    "missing_protocol_data",
    "adapter_pending",
    "protocol_export_only",
    "temporal_edge_export_only",
    "missing_official_casft_data",
    "timeout",
    "preprocess_failed",
    "train_failed",
}


def validate_benchmark_results(results: Iterable[Mapping]) -> Dict:
    """Validate KT2 benchmark JSON rows without adding a heavyweight dependency."""

    errors: List[str] = []
    warnings: List[str] = []
    rows = list(results)
    if not isinstance(rows, list):
        return {"ok": False, "errors": ["benchmark result root must be a list"], "warnings": []}
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(f"row {idx}: result must be an object")
            continue
        _validate_required(row, idx, errors)
        _validate_task(row, idx, errors)
        _validate_status(row, idx, errors, warnings)
        _validate_reproduction(row, idx, errors)
        _validate_metric_shape(row, idx, errors, warnings)
    return {
        "schema": "cogguard.kt2.benchmark_result.v1",
        "ok": not errors,
        "rows": len(rows),
        "errors": errors,
        "warnings": warnings,
    }


def _validate_required(row: Mapping, idx: int, errors: List[str]) -> None:
    for key in ("model", "dataset", "task", "status", "reproduction_level"):
        if key not in row:
            errors.append(f"row {idx}: missing required field {key}")


def _validate_task(row: Mapping, idx: int, errors: List[str]) -> None:
    task = row.get("task")
    if task is not None and task not in TASKS:
        errors.append(f"row {idx}: unknown task {task}")


def _validate_status(row: Mapping, idx: int, errors: List[str], warnings: List[str]) -> None:
    status = row.get("status")
    if status is not None and status not in STATUSES:
        warnings.append(f"row {idx}: unrecognized status {status}")
    if status == "ok" and row.get("reproduction_level") == "frontier_data_adapter_ready_not_model_run":
        errors.append(f"row {idx}: ok status cannot be paired with export-only reproduction level")


def _validate_reproduction(row: Mapping, idx: int, errors: List[str]) -> None:
    level = row.get("reproduction_level")
    if level is not None and level not in REPRODUCTION_LEVELS:
        errors.append(f"row {idx}: unknown reproduction_level {level}")
    if level in {"frontier_reproduction_small_run", "frontier_reproduction_full_run"}:
        if row.get("status") != "ok":
            errors.append(f"row {idx}: frontier reproduction requires status=ok")
        if not any(_has_recorded_value(row, key) for key in ("seed", "random_seed", "num_runs")):
            errors.append(f"row {idx}: frontier reproduction must record seed/random_seed/num_runs")


def _validate_metric_shape(row: Mapping, idx: int, errors: List[str], warnings: List[str]) -> None:
    task = row.get("task")
    status = row.get("status")
    if task == "scale" and status in {"ok", "protocol_export_only"}:
        if not any(key in row for key in ("msle", "mae", "rmse", "mape_percent")):
            warnings.append(f"row {idx}: scale result has no regression metrics")
    if task == "next_hop" and status in {"ok", "temporal_edge_export_only"}:
        if not any(key in row for key in ("hits@10", "hits@50", "hits@100", "mrr", "candidate_recall_full")):
            warnings.append(f"row {idx}: next_hop result has no ranking metrics")
        audit = row.get("candidate_protocol_audit")
        if status == "temporal_edge_export_only":
            if not isinstance(audit, Mapping):
                errors.append(f"row {idx}: temporal export result must include candidate_protocol_audit")
            elif audit.get("leakage_check_passed") is not True:
                errors.append(f"row {idx}: candidate protocol audit did not pass")
    if task == "multi_scale" and row.get("model") == "KT2MacroMicroFramework":
        if row.get("reproduction_level") != "protocol_proxy_not_original_architecture":
            errors.append(f"row {idx}: KT2 macro/micro framework row must remain a protocol proxy, not a frontier reproduction")
        if "macro_micro_consistency" not in row:
            warnings.append(f"row {idx}: KT2 macro/micro framework row has no consistency score")
    if task == "multi_scale" and row.get("model") == "KT2JointModel":
        if row.get("reproduction_level") not in {"kt2_joint_model_small_run", "kt2_joint_model_full_run"}:
            errors.append(
                f"row {idx}: KT2JointModel must use kt2_joint_model_small_run or kt2_joint_model_full_run"
            )
        if row.get("reproduction_level") == "kt2_joint_model_full_run":
            full_run = row.get("full_run_protocol", {})
            if not isinstance(full_run, Mapping):
                errors.append(f"row {idx}: KT2JointModel full-run row must include full_run_protocol")
            else:
                required = ("same_protocol", "original_subpaths_passed", "teacher_alignment_recorded")
                for key in required:
                    if full_run.get(key) is not True:
                        errors.append(f"row {idx}: KT2JointModel full-run protocol requires {key}=true")
                if not _has_recorded_value(full_run, "config_id"):
                    errors.append(f"row {idx}: KT2JointModel full-run protocol must record config_id")
        if status == "ok":
            for key in ("msle", "mae", "rmse", "direction_accuracy"):
                if not _has_finite_number(row, key):
                    errors.append(f"row {idx}: KT2JointModel status=ok requires finite macro metric {key}")
            for key in ("candidate_recall_full", "hits@10", "hits@50", "hits@100", "mrr", "macro_micro_consistency"):
                if not _has_finite_number(row, key):
                    errors.append(f"row {idx}: KT2JointModel status=ok requires finite micro/consistency metric {key}")
            note = str(row.get("note", "")).lower()
            migration = str(row.get("research_migration", "")).lower()
            training = row.get("joint_training", {})
            methodology = str(training.get("methodology", "") if isinstance(training, Mapping) else "").lower()
            boundary_text = " ".join([note, migration, methodology])
            if "not an original" not in boundary_text and "not the original" not in boundary_text:
                errors.append(f"row {idx}: KT2JointModel must state it is not an original paper-architecture reproduction")
            for phrase in ("minds", "forest", "casft"):
                if phrase not in boundary_text:
                    errors.append(f"row {idx}: KT2JointModel boundary text must mention {phrase.upper()} migration scope")
        audit = row.get("candidate_protocol_audit")
        if not isinstance(audit, Mapping):
            errors.append(f"row {idx}: KT2JointModel must include candidate_protocol_audit")
        elif audit.get("leakage_check_passed") is not True:
            errors.append(f"row {idx}: KT2JointModel candidate protocol audit did not pass")
    if task == "multi_scale" and row.get("model") == "KT2SequenceJointModel":
        if row.get("reproduction_level") not in {
            "kt2_sequence_joint_model_small_run",
            "kt2_sequence_joint_model_full_run",
        }:
            errors.append(
                f"row {idx}: KT2SequenceJointModel must use kt2_sequence_joint_model_small_run or kt2_sequence_joint_model_full_run"
            )
        if status == "ok":
            for key in ("msle", "mae", "rmse", "direction_accuracy", "trend_mae", "trend_rmse"):
                if not _has_finite_number(row, key):
                    errors.append(f"row {idx}: KT2SequenceJointModel status=ok requires finite macro/trend metric {key}")
            for key in (
                "candidate_recall_full",
                "hits@10",
                "hits@50",
                "hits@100",
                "mrr",
                "macro_micro_soft_consistency",
            ):
                if not _has_finite_number(row, key):
                    errors.append(f"row {idx}: KT2SequenceJointModel status=ok requires finite micro/consistency metric {key}")
            protocol = row.get("training_protocol", {})
            if not isinstance(protocol, Mapping):
                errors.append(f"row {idx}: KT2SequenceJointModel must include training_protocol")
            else:
                if protocol.get("micro_target") != "next_user_autoregressive_sampled_softmax":
                    errors.append(f"row {idx}: KT2SequenceJointModel must use sequence next-user micro target")
                if protocol.get("candidate_features_used_as_model_input") is not False:
                    errors.append(f"row {idx}: KT2SequenceJointModel must not use candidate features as model input")
                components = set(protocol.get("backbone_components", []))
                required_components = {"DynamicCasHGNN", "RelationGNN", "SharedLSTM", "EulerTrendDecoder"}
                if not required_components.issubset(components):
                    errors.append(
                        f"row {idx}: KT2SequenceJointModel backbone_components must include {sorted(required_components)}"
                    )
                if "Euler" not in str(protocol.get("trend_decoder", "")):
                    errors.append(f"row {idx}: KT2SequenceJointModel must record Euler trend decoder")
                if "rollout" not in str(protocol.get("rollout", "")).lower():
                    errors.append(f"row {idx}: KT2SequenceJointModel must record rollout protocol")
            rollout = row.get("rollout_summary")
            if not isinstance(rollout, Mapping):
                errors.append(f"row {idx}: KT2SequenceJointModel must include rollout_summary")
            else:
                if not _has_finite_number(rollout, "rollout_steps") or int(rollout.get("rollout_steps", 0)) <= 0:
                    errors.append(f"row {idx}: KT2SequenceJointModel rollout_summary requires positive rollout_steps")
            boundary_text = " ".join(
                [
                    str(row.get("note", "")).lower(),
                    str(row.get("methodology", "")).lower(),
                    str(row.get("legacy_boundary", "")).lower(),
                    str(row.get("research_migration", "")).lower(),
                ]
            )
            for phrase in ("minds", "forest", "casft"):
                if phrase not in boundary_text:
                    errors.append(f"row {idx}: KT2SequenceJointModel boundary text must mention {phrase.upper()} migration scope")
        audit = row.get("candidate_protocol_audit")
        if not isinstance(audit, Mapping):
            errors.append(f"row {idx}: KT2SequenceJointModel must include candidate_protocol_audit")
        elif audit.get("leakage_check_passed") is not True:
            errors.append(f"row {idx}: KT2SequenceJointModel candidate protocol audit did not pass")
        elif audit.get("future_nodes_injected") is not False:
            errors.append(f"row {idx}: KT2SequenceJointModel candidate protocol must not inject future nodes")
    if task == "bot_detection" and row.get("model") == "LGB":
        if status == "ok":
            for key in ("accuracy", "f1", "roc_auc"):
                if not _has_finite_number(row, key):
                    errors.append(f"row {idx}: LGB status=ok requires finite bot-detection metric {key}")
            protocol = row.get("training_protocol", {})
            if not isinstance(protocol, Mapping):
                errors.append(f"row {idx}: LGB must include training_protocol")
            else:
                stages = " ".join(str(item).lower() for item in protocol.get("stages", []))
                for phrase in ("lm supervised", "gnn graph contrastive", "gnn fine-tuning"):
                    if phrase not in stages:
                        errors.append(f"row {idx}: LGB training_protocol must record stage {phrase}")
                if "twibot-22" not in str(protocol.get("full_reproduction_required_datasets", [])).lower():
                    errors.append(f"row {idx}: LGB must record TwiBot-22 as required full-reproduction dataset")


def _has_recorded_value(row: Mapping, key: str) -> bool:
    if key not in row:
        return False
    value = row.get(key)
    return value is not None and str(value) != ""


def _has_finite_number(row: Mapping, key: str) -> bool:
    value = row.get(key)
    return isinstance(value, (int, float)) and math.isfinite(float(value))
