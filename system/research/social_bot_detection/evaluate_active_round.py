"""Evaluation gates for active-learning account-detection rounds."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

__all__ = [
    "ActiveRoundEvaluationGate",
    "build_frozen_holdout_manifest",
    "compare_active_learning_efficiency",
    "evaluate_active_round_gates",
]


@dataclass(frozen=True, slots=True)
class ActiveRoundEvaluationGate:
    """One auditable gate for candidate model activation."""

    name: str
    passed: bool
    observed: Any
    requirement: str


@dataclass(frozen=True, slots=True)
class FrozenHoldoutManifest:
    """Leakage-safe holdout manifest for account-detection active rounds."""

    holdout_case_ids: list[str]
    active_pool_case_ids: list[str]
    leakage_case_ids: list[str]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_active_round_gates(metrics: dict[str, Any], *, max_ece: float = 0.08) -> dict[str, Any]:
    """Evaluate leakage, calibration, and deployment-safety gates."""

    gates = [
        ActiveRoundEvaluationGate(
            "frozen_holdout",
            bool(metrics.get("frozen_holdout_passed")),
            metrics.get("frozen_holdout_passed"),
            "frozen holdout is never selected by active learning",
        ),
        ActiveRoundEvaluationGate(
            "time_forward",
            bool(metrics.get("time_forward_passed")),
            metrics.get("time_forward_passed"),
            "later accounts/events are evaluated after earlier training data",
        ),
        ActiveRoundEvaluationGate(
            "platform_stratified",
            bool(metrics.get("platform_stratified_passed")),
            metrics.get("platform_stratified_passed"),
            "metrics are reported by platform, not only pooled",
        ),
        ActiveRoundEvaluationGate(
            "community_disjoint",
            bool(metrics.get("community_disjoint_passed")),
            metrics.get("community_disjoint_passed"),
            "train and test accounts do not share leakage-prone graph neighborhoods",
        ),
        ActiveRoundEvaluationGate(
            "calibration",
            float(metrics.get("ece", 1.0)) <= max_ece,
            metrics.get("ece"),
            f"expected calibration error <= {max_ece}",
        ),
        ActiveRoundEvaluationGate(
            "false_positive_burden",
            bool(metrics.get("false_positive_burden_passed")),
            metrics.get("false_positive_burden_passed"),
            "false positives fit the analyst review capacity",
        ),
    ]
    return {
        "activation_allowed": all(gate.passed for gate in gates),
        "gates": {gate.name: gate.passed for gate in gates},
        "details": [asdict(gate) for gate in gates],
    }


def build_frozen_holdout_manifest(
    *,
    holdout_case_ids: list[str] | set[str],
    active_pool_case_ids: list[str] | set[str],
) -> dict[str, Any]:
    """Verify that active-learning acquisition never selects holdout cases."""

    holdout = sorted({str(case_id) for case_id in holdout_case_ids})
    active_pool = sorted({str(case_id) for case_id in active_pool_case_ids})
    leakage = sorted(set(holdout) & set(active_pool))
    return FrozenHoldoutManifest(
        holdout_case_ids=holdout,
        active_pool_case_ids=active_pool,
        leakage_case_ids=leakage,
        passed=not leakage,
    ).to_dict()


def compare_active_learning_efficiency(
    strategy_scores: dict[str, list[float]],
    *,
    random_baseline: str = "random",
) -> dict[str, Any]:
    """Compare equal-budget active-learning rounds against a random baseline.

    Scores are ordered by acquisition round and represent the same metric
    across strategies, for example validation macro F1 or AUPRC.
    """

    if random_baseline not in strategy_scores:
        raise ValueError("random baseline scores are required for active-learning efficiency")
    normalized = {
        name: [float(value) for value in values]
        for name, values in strategy_scores.items()
    }
    baseline = normalized[random_baseline]
    rows = []
    for name, values in sorted(normalized.items()):
        if len(values) != len(baseline):
            raise ValueError("all active-learning strategies must use equal budget checkpoints")
        improvement = [round(score - base, 6) for score, base in zip(values, baseline)]
        rows.append(
            {
                "strategy": name,
                "round_count": len(values),
                "final_score": values[-1] if values else None,
                "final_delta_vs_random": improvement[-1] if improvement else None,
                "mean_delta_vs_random": round(sum(improvement) / len(improvement), 6) if improvement else None,
                "per_round_delta_vs_random": improvement,
            }
        )
    return {
        "baseline": random_baseline,
        "equal_budget": True,
        "rows": rows,
    }
