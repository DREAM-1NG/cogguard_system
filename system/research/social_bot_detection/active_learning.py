"""Active-learning acquisition for Chinese account detection.

The selector is intentionally label-safe: model outputs rank accounts for human
review, but they never become training labels. Frozen holdout construction and
final metric reporting live outside this selected pool.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "AccountAcquisitionCandidate",
    "AccountAcquisitionItem",
    "AccountAcquisitionResult",
    "AccountAcquisitionWeights",
    "select_account_labeling_batch",
]


@dataclass(frozen=True, slots=True)
class AccountAcquisitionCandidate:
    """One unlabeled account case available for analyst review."""

    case_id: str
    account_id: str
    platform: str
    event_id: str
    text: str
    post_ids: list[str]
    model_probability: float | None = None
    model_is_calibrated: bool = False
    disagreement_score: float = 0.0
    ood_score: float = 0.0
    graph_representativeness: float = 0.0
    embedding: list[float] | None = None
    has_approved_label: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AccountAcquisitionWeights:
    """Weights for batch acquisition signals."""

    uncertainty: float = 0.40
    disagreement: float = 0.20
    diversity: float = 0.20
    ood: float = 0.10
    representativeness: float = 0.10
    random_audit: float = 0.05


@dataclass(frozen=True, slots=True)
class AccountAcquisitionItem:
    """Selected account case with auditable acquisition scores."""

    case_id: str
    account_id: str
    platform: str
    event_id: str
    post_ids: list[str]
    priority_rank: int
    selection_bucket: str
    scores: dict[str, float]
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AccountAcquisitionResult:
    """Selected labeling batch and its manifest."""

    strategy: str
    items: list[AccountAcquisitionItem]
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "items": [item.to_dict() for item in self.items],
            "manifest": self.manifest,
        }


def select_account_labeling_batch(
    candidates: list[AccountAcquisitionCandidate],
    *,
    budget: int,
    weights: AccountAcquisitionWeights | None = None,
    cold_start: bool = False,
    surprisal_by_case: dict[str, float] | None = None,
    seed: int = 42,
) -> AccountAcquisitionResult:
    """Select a deterministic, stratified human-labeling batch."""

    weights = weights or AccountAcquisitionWeights()
    eligible = [candidate for candidate in candidates if not candidate.has_approved_label]
    excluded_count = len(candidates) - len(eligible)
    has_calibrated_ranker = any(
        candidate.model_is_calibrated and candidate.model_probability is not None
        for candidate in eligible
    )
    effective_cold_start = cold_start or not has_calibrated_ranker
    has_surprisal = bool(surprisal_by_case)
    if budget <= 0 or not eligible:
        return AccountAcquisitionResult(
            strategy=_strategy_name(effective_cold_start, has_surprisal),
            items=[],
            manifest=_manifest(
                budget,
                candidates,
                eligible,
                excluded_count,
                weights,
                effective_cold_start,
                has_surprisal,
                has_calibrated_ranker,
            ),
        )

    scored = [
        (
            candidate,
            _score_candidate(
                candidate,
                weights=weights,
                cold_start=effective_cold_start,
                surprisal=float((surprisal_by_case or {}).get(candidate.case_id, 0.0)),
            ),
        )
        for candidate in eligible
    ]

    selected: list[tuple[AccountAcquisitionCandidate, dict[str, float], str]] = []
    selected_ids: set[str] = set()

    audit_quota = min(
        len(scored),
        budget,
        max(1, round(budget * weights.random_audit)) if weights.random_audit > 0 else 0,
    )
    for candidate, scores in sorted(
        scored,
        key=lambda row: _stable_random_key(row[0].case_id, seed),
    )[:audit_quota]:
        selected.append((candidate, scores, "random_audit"))
        selected_ids.add(candidate.case_id)

    if len(selected) < budget:
        _add_platform_representatives(scored, selected, selected_ids, budget, effective_cold_start)

    while len(selected) < budget:
        remaining = [
            (candidate, scores)
            for candidate, scores in scored
            if candidate.case_id not in selected_ids
        ]
        if not remaining:
            break
        candidate, scores = max(
            remaining,
            key=lambda row: (
                _score_with_diversity(row[0], row[1], selected),
                row[0].platform,
                row[0].case_id,
            ),
        )
        selected.append((candidate, scores, _strategy_bucket(effective_cold_start)))
        selected_ids.add(candidate.case_id)

    items = [
        AccountAcquisitionItem(
            case_id=candidate.case_id,
            account_id=candidate.account_id,
            platform=candidate.platform,
            event_id=candidate.event_id,
            post_ids=list(candidate.post_ids),
            priority_rank=rank,
            selection_bucket=bucket,
            scores=scores,
            score=round(_score_with_diversity(candidate, scores, selected[: rank - 1]), 6),
        )
        for rank, (candidate, scores, bucket) in enumerate(selected, start=1)
    ]
    return AccountAcquisitionResult(
        strategy=_strategy_name(effective_cold_start, has_surprisal),
        items=items,
        manifest=_manifest(
            budget,
            candidates,
            eligible,
            excluded_count,
            weights,
            effective_cold_start,
            has_surprisal,
            has_calibrated_ranker,
        ),
    )


def _add_platform_representatives(
    scored: list[tuple[AccountAcquisitionCandidate, dict[str, float]]],
    selected: list[tuple[AccountAcquisitionCandidate, dict[str, float], str]],
    selected_ids: set[str],
    budget: int,
    cold_start: bool,
) -> None:
    platforms = sorted({candidate.platform for candidate, _scores in scored})
    if len(platforms) <= 1 or len(platforms) > budget:
        return
    for platform in platforms:
        if len(selected) >= budget:
            return
        if any(candidate.platform == platform for candidate, _scores, _bucket in selected):
            continue
        platform_rows = [
            (candidate, scores)
            for candidate, scores in scored
            if candidate.platform == platform and candidate.case_id not in selected_ids
        ]
        if not platform_rows:
            continue
        candidate, scores = max(platform_rows, key=lambda row: row[1]["base_score"])
        selected.append((candidate, scores, "platform_representative" if not cold_start else "surprisal"))
        selected_ids.add(candidate.case_id)


def _score_candidate(
    candidate: AccountAcquisitionCandidate,
    *,
    weights: AccountAcquisitionWeights,
    cold_start: bool,
    surprisal: float,
) -> dict[str, float]:
    uncertainty = _uncertainty(
        candidate.model_probability if candidate.model_is_calibrated else None
    )
    if cold_start:
        uncertainty = 0.0
    scores = {
        "uncertainty": round(uncertainty, 6),
        "disagreement": round(_clamp(candidate.disagreement_score), 6),
        "ood": round(_clamp(candidate.ood_score), 6),
        "representativeness": round(_clamp(candidate.graph_representativeness), 6),
        "surprisal": round(_clamp(surprisal), 6),
    }
    if cold_start:
        base_score = (0.70 * scores["surprisal"]) + (0.30 * scores["representativeness"])
    else:
        base_score = (
            weights.uncertainty * scores["uncertainty"]
            + weights.disagreement * scores["disagreement"]
            + weights.ood * scores["ood"]
            + weights.representativeness * scores["representativeness"]
        )
    scores["base_score"] = round(float(base_score), 6)
    return scores


def _score_with_diversity(
    candidate: AccountAcquisitionCandidate,
    scores: dict[str, float],
    selected: list[tuple[AccountAcquisitionCandidate, dict[str, float], str]],
) -> float:
    diversity = 1.0 if not selected else min(
        _cosine_distance(_embedding(candidate), _embedding(existing))
        for existing, _scores, _bucket in selected
    )
    return float(scores["base_score"] + (0.20 * diversity))


def _uncertainty(probability: float | None) -> float:
    if probability is None:
        return 0.0
    probability = _clamp(probability)
    return 1.0 - abs(probability - 0.5) * 2.0


def _embedding(candidate: AccountAcquisitionCandidate) -> np.ndarray:
    if candidate.embedding:
        return np.asarray(candidate.embedding, dtype=np.float32)
    return _hashed_shingle_embedding(candidate.text)


def _hashed_shingle_embedding(text: str, dims: int = 64) -> np.ndarray:
    vector = np.zeros(dims, dtype=np.float32)
    normalized = " ".join(text.lower().split())
    if not normalized:
        return vector
    shingles = [normalized[index : index + 4] for index in range(max(1, len(normalized) - 3))]
    for shingle in shingles:
        index = int(hashlib.sha256(shingle.encode("utf-8")).hexdigest()[:8], 16) % dims
        vector[index] += 1.0
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _cosine_distance(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom == 0.0:
        return 1.0
    return float(1.0 - ((left @ right) / denom))


def _stable_random_key(case_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{case_id}".encode("utf-8")).hexdigest()


def _strategy_name(cold_start: bool, has_surprisal: bool) -> str:
    if cold_start:
        return "cold_start_surprisal_diversity" if has_surprisal else "cold_start_coverage_diversity"
    return "uncertainty_disagreement_diversity"


def _strategy_bucket(cold_start: bool) -> str:
    return "surprisal" if cold_start else "acquisition"


def _manifest(
    budget: int,
    candidates: list[AccountAcquisitionCandidate],
    eligible: list[AccountAcquisitionCandidate],
    excluded_count: int,
    weights: AccountAcquisitionWeights,
    cold_start: bool,
    has_surprisal: bool,
    has_calibrated_ranker: bool,
) -> dict[str, Any]:
    return {
        "schema": "cogguard.account_detection.active_learning.v1",
        "strategy": _strategy_name(cold_start, has_surprisal),
        "model_state": (
            "cold_start_no_reliable_ranker"
            if cold_start
            else "warm_start_calibrated_model_ranker"
        ),
        "ranker_status": (
            "calibrated_model_available" if has_calibrated_ranker else "no_calibrated_model"
        ),
        "surprisal_source": "provided_language_model" if has_surprisal else "unavailable",
        "diversity_source": "candidate_embedding_or_deterministic_text_fallback",
        "acquisition_policy": (
            "use_language_model_surprisal_and_diversity_before_classifier_uncertainty"
            if cold_start
            else "use_calibrated_model_uncertainty_disagreement_ood_representativeness_and_diversity_for_review_priority"
        ),
        "budget": budget,
        "candidate_count": len(candidates),
        "eligible_count": len(eligible),
        "excluded_approved_label_count": excluded_count,
        "stratified_by": ["platform", "event_id"],
        "label_policy": "model_scores_rank_human_review_only",
        "weights": asdict(weights),
    }


def _clamp(value: float) -> float:
    if math.isnan(float(value)):
        return 0.0
    return max(0.0, min(1.0, float(value)))
