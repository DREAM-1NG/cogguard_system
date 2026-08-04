"""Active-learning case selection for account detection."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.core.account_labeling import AccountDetectionCase

__all__ = ["select_account_detection_label_batch"]

_PACKAGE_NAME = "_cogguard_social_bot_detection_active_learning"


def select_account_detection_label_batch(
    cases: list[AccountDetectionCase],
    *,
    model_outputs: dict[str, dict[str, Any]] | None = None,
    approved_case_ids: set[str] | None = None,
    budget: int = 20,
    cold_start: bool = False,
    surprisal_by_case: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Select cases for human labeling without turning predictions into labels."""

    active_learning = _load_active_learning_module()
    approved_case_ids = approved_case_ids or set()
    model_outputs = model_outputs or {}
    candidates = [
        active_learning.AccountAcquisitionCandidate(
            case_id=case.case_id,
            account_id=case.account_id,
            platform=case.platform,
            event_id=case.event_id,
            text=case.text,
            post_ids=case.post_ids,
            model_probability=_probability_for(case, model_outputs),
            model_is_calibrated=_is_calibrated(_payload_for(case, model_outputs)),
            disagreement_score=_score_for(case, model_outputs, "disagreement_score", "disagreement"),
            ood_score=_score_for(case, model_outputs, "ood_score", "ood"),
            graph_representativeness=_score_for(
                case,
                model_outputs,
                "graph_representativeness",
                "representativeness",
            ),
            embedding=_embedding_for(case, model_outputs),
            has_approved_label=case.case_id in approved_case_ids,
            metadata={"case_fingerprint": case.case_fingerprint},
        )
        for case in cases
    ]
    result = active_learning.select_account_labeling_batch(
        candidates,
        budget=budget,
        cold_start=cold_start,
        surprisal_by_case=surprisal_by_case,
    ).to_dict()
    return {
        **result,
        "policy": "human_review_required",
        "label_source_policy": "analyst_observed_behavior_only",
    }


def _probability_for(case: AccountDetectionCase, model_outputs: dict[str, dict[str, Any]]) -> float | None:
    payload = _payload_for(case, model_outputs)
    for key in ("bot_probability", "final_bot_probability", "probability", "score"):
        if key in payload and payload[key] is not None:
            return _safe_float(payload[key])
    return None


def _payload_for(case: AccountDetectionCase, model_outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return model_outputs.get(case.case_id) or model_outputs.get(case.account_id) or {}


def _is_calibrated(payload: dict[str, Any]) -> bool:
    return bool(payload.get("calibrated") or payload.get("calibration_passed"))


def _score_for(
    case: AccountDetectionCase,
    model_outputs: dict[str, dict[str, Any]],
    *keys: str,
) -> float:
    payload = _payload_for(case, model_outputs)
    for key in keys:
        if key in payload and payload[key] is not None:
            value = _safe_float(payload[key])
            if value is None:
                continue
            return max(0.0, min(1.0, value))
    return 0.0


def _embedding_for(
    case: AccountDetectionCase,
    model_outputs: dict[str, dict[str, Any]],
) -> list[float] | None:
    payload = _payload_for(case, model_outputs)
    raw_embedding = payload.get("embedding") or payload.get("representation")
    if not isinstance(raw_embedding, list) or not raw_embedding:
        return None
    try:
        parsed = [_safe_float(value) for value in raw_embedding]
    except (TypeError, ValueError):
        return None
    if any(value is None for value in parsed):
        return None
    return [float(value) for value in parsed]


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _load_active_learning_module() -> Any:
    existing = sys.modules.get(_PACKAGE_NAME)
    if existing is not None:
        return existing
    package_dir = PROJECT_ROOT / "research" / "social_bot_detection"
    module_path = package_dir / "active_learning.py"
    spec = importlib.util.spec_from_file_location(_PACKAGE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load account active-learning module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PACKAGE_NAME] = module
    spec.loader.exec_module(module)
    return module
