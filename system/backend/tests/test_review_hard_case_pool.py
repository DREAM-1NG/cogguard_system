from __future__ import annotations

import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "scripts" / "build_review_hard_case_pool.py"
    spec = importlib.util.spec_from_file_location("build_review_hard_case_pool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hard_case_pool_is_gold_free_and_stratified():
    module = _module()
    rows = [
        {
            "case_id": "harm-1",
            "dataset": "HateXplain",
            "task": "interpersonal_harm",
            "student": {"interpersonal_aggression": 0.5},
            "gold_label": "harmful",
        },
        {
            "case_id": "claim-1",
            "dataset": "PHEME",
            "task": "claim_deception",
            "student": {"misinfo_claim_risk": 0.99},
            "evidence_bundle": {"relation": "conflicting"},
            "gold_label": "non_harmful",
        },
    ]

    manifest = module.build_manifest(rows, source="predictions.jsonl", max_cases=2)

    assert manifest["gold_labels_used"] is False
    assert manifest["teacher_called"] is False
    assert {case["case_id"] for case in manifest["cases"]} == {"harm-1", "claim-1"}
    assert all("gold_label" not in case for case in manifest["cases"])
    assert all("selection_score" in case for case in manifest["cases"])


def test_hard_case_pool_handles_missing_predictions_without_fabricating_scores():
    module = _module()
    scored = module.score_hard_case({"case_id": "empty", "dataset": "unknown"})

    assert scored["selection_score"] == 0.0
    assert scored["axis_probabilities"] == {}
