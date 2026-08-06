from __future__ import annotations

import math
import warnings

from .contracts import ClusterDetectionVerdict


_WEIGHTS = (0.25, 0.35, 0.25, 0.15)
_SIGMOID_SCALE = 10.0
_LOWER_THRESHOLD = 0.65
_UPPER_THRESHOLD = 0.85
_WARNING = "Research-only heuristic baseline; output is not a learned or production decision."


def _unit(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{field_name} must be finite and within [0, 1]")
    return result


class HeuristicBayesianBaseline:
    __slots__ = ()

    def predict(
        self,
        *,
        cluster_id: str,
        tsgs_density: float,
        mhcr_coherence: float,
        temporal_sync_score: float,
        unsupervised_ranking: float,
    ) -> ClusterDetectionVerdict:
        values = tuple(
            _unit(value, name)
            for name, value in (
                ("tsgs_density", tsgs_density),
                ("mhcr_coherence", mhcr_coherence),
                ("temporal_sync_score", temporal_sync_score),
                ("unsupervised_ranking", unsupervised_ranking),
            )
        )
        score = sum(weight * value for weight, value in zip(_WEIGHTS, values, strict=True))
        probability = 1.0 / (1.0 + math.exp(-_SIGMOID_SCALE * (score - 0.5)))
        if probability <= _LOWER_THRESHOLD:
            decision = "benign_coordination"
        elif probability >= _UPPER_THRESHOLD:
            decision = "harmful_coordination"
        else:
            decision = "abstain"
        warnings.warn(_WARNING, UserWarning, stacklevel=2)
        return ClusterDetectionVerdict(
            cluster_id=cluster_id,
            decision=decision,
            harmful_probability=probability,
            model_version="heuristic_baseline_v1",
            model_role="heuristic_baseline",
            abstain_reason="heuristic_uncertainty" if decision == "abstain" else None,
            warning=_WARNING,
        )


__all__ = ["HeuristicBayesianBaseline"]
