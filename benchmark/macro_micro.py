from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Mapping, Optional


SCALE_MODELS = {
    "KT2JointModel": 95,
    "CasFT": 100,
    "HyperIDPAdversarialProxy": 70,
    "HyperIDPProtocolProxy": 65,
    "MINDS": 60,
    "RF_Baseline": 45,
    "TemporalSizeBaseline": 35,
}

MICRO_MODELS = {
    "DyGFormer/DyGLib": 100,
    "KT2JointModel": 95,
    "TGN": 85,
    "MINDS": 70,
    "FOREST": 65,
    "HyperIDPAdversarialProxy": 60,
    "HyperIDPProtocolProxy": 55,
    "ProspectiveRanker": 45,
    "ProspectiveHeuristic": 40,
    "LR_EdgeClassifier": 20,
}

FRONTIER_LEVEL_BONUS = {
    "frontier_reproduction_full_run": 30,
    "frontier_reproduction_small_run": 20,
    "kt2_joint_model_small_run": 15,
    "frontier_data_adapter_ready_not_model_run": 5,
    "protocol_proxy_not_original_architecture": 0,
    "public_code_adapter": 0,
    "local_baseline": 0,
}


def build_macro_micro_framework_summary(results: Iterable[Mapping]) -> Dict:
    """Summarize whether a benchmark run supports KT2 macro/micro evaluation.

    This is an audit layer, not a new model. It pairs the best available macro
    scale row and micro next-hop row per dataset, then reports a consistency
    proxy. A count-level consistency score is used only when both branches expose
    comparable growth counts; otherwise the score is explicitly marked as a
    protocol-readiness proxy.
    """

    rows = [row for row in results if isinstance(row, Mapping)]
    by_dataset: Dict[str, List[Mapping]] = defaultdict(list)
    for row in rows:
        dataset = str(row.get("dataset") or "unknown")
        by_dataset[dataset].append(row)

    dataset_summaries = []
    for dataset, dataset_rows in sorted(by_dataset.items()):
        joint_row = _select_joint_row(dataset_rows)
        scale_row = joint_row or _select_row(dataset_rows, "scale", SCALE_MODELS)
        micro_row = joint_row or _select_row(dataset_rows, "next_hop", MICRO_MODELS)
        if not scale_row or not micro_row:
            dataset_summaries.append(
                {
                    "dataset": dataset,
                    "status": "missing_pair",
                    "scale_model": scale_row.get("model") if scale_row else None,
                    "micro_model": micro_row.get("model") if micro_row else None,
                    "macro_micro_consistency": None,
                    "consistency_mode": "missing_macro_or_micro_branch",
                }
            )
            continue
        score = _consistency_score(scale_row, micro_row)
        dataset_summaries.append(
            {
                "dataset": dataset,
                "status": "ok",
                "scale_model": scale_row.get("model"),
                "micro_model": micro_row.get("model"),
                "scale_reproduction_level": scale_row.get("reproduction_level"),
                "micro_reproduction_level": micro_row.get("reproduction_level"),
                **score,
            }
        )

    valid_scores = [
        item["macro_micro_consistency"]
        for item in dataset_summaries
        if isinstance(item.get("macro_micro_consistency"), (int, float))
    ]
    return {
        "schema": "cogguard.kt2.macro_micro_framework.v1",
        "status": "ok" if valid_scores else "missing_pair",
        "definition": (
            "KT2 macro/micro framework pairs macro scale/trend prediction with "
            "micro next-hop ranking under one leak-checked benchmark protocol."
        ),
        "macro_micro_consistency_mean": round(sum(valid_scores) / len(valid_scores), 6) if valid_scores else None,
        "datasets": dataset_summaries,
        "note": (
            "This summary is an evaluation/protocol layer. It must not be cited "
            "as a new frontier model or full-run reproduction result."
        ),
    }


def macro_micro_result_rows(summary: Mapping) -> List[Dict]:
    rows = []
    for item in summary.get("datasets", []):
        if item.get("status") != "ok":
            continue
        rows.append(
            {
                "model": "KT2MacroMicroFramework",
                "dataset": item.get("dataset"),
                "task": "multi_scale",
                "status": "ok",
                "reproduction_level": "protocol_proxy_not_original_architecture",
                "macro_micro_consistency": item.get("macro_micro_consistency"),
                "consistency_mode": item.get("consistency_mode"),
                "scale_model": item.get("scale_model"),
                "micro_model": item.get("micro_model"),
                "note": "Unified framework audit row; not a standalone paper-model reproduction.",
            }
        )
    return rows


def _select_row(rows: List[Mapping], task: str, priorities: Mapping[str, int]) -> Optional[Mapping]:
    candidates = [row for row in rows if row.get("task") == task and row.get("status") in {"ok", "protocol_export_only", "temporal_edge_export_only"}]
    if not candidates:
        return None
    return max(candidates, key=lambda row: _row_priority(row, priorities))


def _select_joint_row(rows: List[Mapping]) -> Optional[Mapping]:
    candidates = [
        row
        for row in rows
        if row.get("task") == "multi_scale"
        and row.get("status") == "ok"
        and row.get("model") == "KT2JointModel"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: _row_priority(row, SCALE_MODELS))


def _row_priority(row: Mapping, priorities: Mapping[str, int]) -> int:
    model = str(row.get("model") or "")
    level = str(row.get("reproduction_level") or "")
    return priorities.get(model, 1) + FRONTIER_LEVEL_BONUS.get(level, 0)


def _consistency_score(scale_row: Mapping, micro_row: Mapping) -> Dict:
    count_score = _growth_count_alignment(scale_row, micro_row)
    if count_score is not None:
        return {
            "macro_micro_consistency": round(count_score, 6),
            "consistency_mode": "growth_count_alignment",
            "consistency_components": {
                "count_alignment": round(count_score, 6),
                "candidate_leakage_ok": _candidate_leakage_ok(micro_row),
            },
        }

    macro_quality = _macro_quality_proxy(scale_row)
    micro_quality = _micro_quality_proxy(micro_row)
    leakage = 1.0 if _candidate_leakage_ok(micro_row) else 0.0
    score = (macro_quality + micro_quality + leakage) / 3.0
    return {
        "macro_micro_consistency": round(score, 6),
        "consistency_mode": "protocol_readiness_proxy",
        "consistency_components": {
            "macro_quality_proxy": round(macro_quality, 6),
            "micro_quality_proxy": round(micro_quality, 6),
            "candidate_leakage_ok": leakage,
        },
    }


def _growth_count_alignment(scale_row: Mapping, micro_row: Mapping) -> Optional[float]:
    macro_growth = _first_number(scale_row, "predicted_growth_mean", "mean_predicted_growth", "macro_predicted_growth")
    micro_growth = _first_number(micro_row, "micro_predicted_growth_mean", "predicted_next_hop_count_mean", "covered_future_users_mean")
    if macro_growth is None or micro_growth is None:
        return None
    if macro_growth < 0 or micro_growth < 0:
        return None
    denom = max(abs(math.log1p(macro_growth)), abs(math.log1p(micro_growth)), 1e-9)
    return max(0.0, 1.0 - abs(math.log1p(macro_growth) - math.log1p(micro_growth)) / denom)


def _macro_quality_proxy(row: Mapping) -> float:
    direction = _as_float(row.get("direction_accuracy"))
    if direction is not None:
        return _clamp01(direction)
    msle = _as_float(row.get("msle"))
    if msle is not None:
        return _clamp01(1.0 / (1.0 + max(msle, 0.0)))
    mape = _as_float(row.get("mape_percent"))
    if mape is not None:
        return _clamp01(1.0 / (1.0 + max(mape, 0.0) / 100.0))
    return 0.0


def _micro_quality_proxy(row: Mapping) -> float:
    values = [
        _as_float(row.get("candidate_recall_full")),
        _as_float(row.get("hits@100")),
        _as_float(row.get("ndcg@100")),
        _as_float(row.get("mrr")),
    ]
    present = [_clamp01(value) for value in values if value is not None]
    return sum(present) / len(present) if present else 0.0


def _candidate_leakage_ok(row: Mapping) -> bool:
    audit = row.get("candidate_protocol_audit")
    if isinstance(audit, Mapping):
        return audit.get("leakage_check_passed") is True
    return True


def _first_number(row: Mapping, *keys: str) -> Optional[float]:
    for key in keys:
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return None


def _as_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
