"""Research-grade acquisition for Chinese account detection.

The default selector implements the deployed research line:

* cold start: ALPS-style masked-language-model surprisal embeddings followed
  by core-set farthest-first selection;
* warm start: calibrated classifier uncertainty followed by BADGE gradient
  embedding selection.

Heuristic weighted scoring remains available only as an explicit baseline for
ablation. The default path never fabricates ALPS or BADGE vectors from hashed
text features.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "AccountAcquisitionCandidate",
    "AccountAcquisitionItem",
    "AccountAcquisitionResult",
    "AccountAcquisitionWeights",
    "AcquisitionInputError",
    "badge_select",
    "calibrated_uncertainty",
    "compute_alps_embeddings",
    "core_set_select",
    "select_account_labeling_batch",
    "select_heuristic_labeling_batch",
]


class AcquisitionInputError(ValueError):
    """Raised when a research acquisition strategy lacks required true inputs."""


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
    alps_embedding: list[float] | None = None
    badge_embedding: list[float] | None = None
    calibrated_probability: float | None = None
    calibration_source: str = ""
    has_approved_label: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AccountAcquisitionWeights:
    """Weights for the explicit heuristic baseline only."""

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


@dataclass(frozen=True, slots=True)
class _ScoredCandidate:
    candidate: AccountAcquisitionCandidate
    vector: np.ndarray
    scores: dict[str, float]


def select_account_labeling_batch(
    candidates: list[AccountAcquisitionCandidate],
    *,
    budget: int,
    weights: AccountAcquisitionWeights | None = None,
    cold_start: bool = False,
    surprisal_by_case: dict[str, float] | None = None,
    seed: int = 42,
) -> AccountAcquisitionResult:
    """Select a deterministic research-grade human-labeling batch.

    ``weights`` and ``surprisal_by_case`` are accepted for API compatibility
    but ignored by the research path. Use ``select_heuristic_labeling_batch``
    for the legacy weighted baseline.
    """

    del weights, surprisal_by_case
    eligible, excluded_count = _eligible_candidates(candidates)
    has_calibrated_ranker = _has_calibrated_ranker(eligible)
    effective_cold_start = cold_start or not has_calibrated_ranker
    strategy = "cold_start_alps_core_set" if effective_cold_start else "warm_start_calibrated_uncertainty_badge"
    if budget <= 0 or not eligible:
        return AccountAcquisitionResult(
            strategy=strategy,
            items=[],
            manifest=_research_manifest(
                budget=budget,
                candidates=candidates,
                eligible=eligible,
                excluded_count=excluded_count,
                strategy=strategy,
                model_state="cold_start_no_reliable_ranker"
                if effective_cold_start
                else "warm_start_calibrated_model_ranker",
                ranker_status="calibrated_model_available" if has_calibrated_ranker else "no_calibrated_model",
                selected_count=0,
                seed=seed,
            ),
        )
    if effective_cold_start:
        return _select_cold_start_alps_core_set(
            candidates=candidates,
            eligible=eligible,
            excluded_count=excluded_count,
            budget=budget,
            seed=seed,
            has_calibrated_ranker=has_calibrated_ranker,
        )
    return _select_warm_start_badge(
        candidates=candidates,
        eligible=eligible,
        excluded_count=excluded_count,
        budget=budget,
        seed=seed,
    )


def compute_alps_embeddings(
    texts: list[str],
    *,
    model_path: str | Path,
    max_length: int = 128,
    batch_size: int = 4,
    device: str = "cpu",
) -> list[list[float]]:
    """Compute ALPS-style token surprisal embeddings with a local MLM.

    Each vector is the negative log probability assigned by the MLM to the
    observed input tokens. This follows the ALPS cold-start idea while staying
    independent from an external service.
    """

    model_dir = Path(model_path).expanduser()
    if not model_dir.exists():
        raise AcquisitionInputError(f"ACCOUNT_ACQUISITION_TEXT_MODEL_PATH does not exist: {model_dir}")
    import torch
    from transformers import AutoModelForMaskedLM, AutoTokenizer

    requested_device = torch.device("cuda" if str(device).startswith("cuda") and torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForMaskedLM.from_pretrained(model_dir, local_files_only=True).to(requested_device)
    model.eval()
    vectors: list[list[float]] = []
    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start : start + batch_size]
            encoded = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(requested_device) for key, value in encoded.items()}
            logits = model(**encoded).logits
            log_probs = logits.log_softmax(dim=-1)
            token_log_probs = log_probs.gather(2, encoded["input_ids"].unsqueeze(-1)).squeeze(-1)
            surprisal = -token_log_probs * encoded["attention_mask"].to(token_log_probs.dtype)
            for row in surprisal.detach().cpu().numpy():
                vectors.append([float(value) for value in row.tolist()])
    return vectors


def core_set_select(
    vectors: list[list[float]] | np.ndarray,
    *,
    budget: int,
    seed: int = 42,
    initial_indices: list[int] | None = None,
) -> list[int]:
    """Run deterministic k-center greedy selection over representation vectors."""

    matrix = _normalize_matrix(np.asarray(vectors, dtype=np.float32))
    if budget <= 0 or matrix.shape[0] == 0:
        return []
    budget = min(int(budget), matrix.shape[0])
    selected: list[int] = []
    selected_set: set[int] = set()
    for index in initial_indices or []:
        if 0 <= index < matrix.shape[0] and index not in selected_set:
            selected.append(int(index))
            selected_set.add(int(index))
            if len(selected) >= budget:
                return selected
    if not selected:
        norms = np.linalg.norm(matrix, axis=1)
        selected.append(int(np.lexsort((np.arange(matrix.shape[0]), -norms))[0]))
        selected_set.add(selected[0])
    while len(selected) < budget:
        distances = _distance_to_selected(matrix, selected)
        for index in selected_set:
            distances[index] = -1.0
        max_distance = float(distances.max())
        tied = np.where(np.isclose(distances, max_distance))[0]
        next_index = _stable_index_choice(tied.tolist(), seed=seed + len(selected))
        selected.append(next_index)
        selected_set.add(next_index)
    return selected


def calibrated_uncertainty(probability: float | None, *, calibrated: bool) -> float:
    """Return binary least-confidence uncertainty after calibration passed."""

    if not calibrated or probability is None:
        raise AcquisitionInputError("warm-start acquisition requires calibrated_probability and calibration metadata")
    probability = _clamp(probability)
    return 1.0 - abs(probability - 0.5) * 2.0


def badge_select(
    candidates: list[AccountAcquisitionCandidate],
    *,
    budget: int,
    seed: int = 42,
) -> list[int]:
    """Select accounts from BADGE gradient embeddings with k-center greedy."""

    vectors = [_required_vector(candidate.badge_embedding, candidate.case_id, "badge_embedding") for candidate in candidates]
    initial = _highest_uncertainty_indices(candidates)
    return core_set_select(vectors, budget=budget, seed=seed, initial_indices=initial[:1])


def select_heuristic_labeling_batch(
    candidates: list[AccountAcquisitionCandidate],
    *,
    budget: int,
    weights: AccountAcquisitionWeights | None = None,
    cold_start: bool = False,
    surprisal_by_case: dict[str, float] | None = None,
    seed: int = 42,
) -> AccountAcquisitionResult:
    """Legacy weighted acquisition baseline for ablation only."""

    weights = weights or AccountAcquisitionWeights()
    eligible, excluded_count = _eligible_candidates(candidates)
    has_calibrated_ranker = _has_calibrated_ranker(eligible)
    effective_cold_start = cold_start or not has_calibrated_ranker
    has_surprisal = bool(surprisal_by_case)
    strategy = "heuristic_baseline"
    if budget <= 0 or not eligible:
        return AccountAcquisitionResult(
            strategy=strategy,
            items=[],
            manifest=_heuristic_manifest(
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
            _score_heuristic_candidate(
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
    for candidate, scores in sorted(scored, key=lambda row: _stable_random_key(row[0].case_id, seed))[:audit_quota]:
        selected.append((candidate, scores, "random_audit"))
        selected_ids.add(candidate.case_id)

    while len(selected) < budget:
        remaining = [(candidate, scores) for candidate, scores in scored if candidate.case_id not in selected_ids]
        if not remaining:
            break
        candidate, scores = max(
            remaining,
            key=lambda row: (
                _score_with_heuristic_diversity(row[0], row[1], selected),
                row[0].platform,
                row[0].case_id,
            ),
        )
        selected.append((candidate, scores, "heuristic_acquisition"))
        selected_ids.add(candidate.case_id)

    items = [
        AccountAcquisitionItem(
            case_id=candidate.case_id,
            account_id=candidate.account_id,
            platform=candidate.platform,
            event_id=candidate.event_id,
            post_ids=list(candidate.post_ids),
            priority_rank=rank,
            selection_bucket=bucket_name,
            scores=scores,
            score=round(_score_with_heuristic_diversity(candidate, scores, selected[: rank - 1]), 6),
        )
        for rank, (candidate, scores, bucket_name) in enumerate(selected, start=1)
    ]
    return AccountAcquisitionResult(
        strategy=strategy,
        items=items,
        manifest=_heuristic_manifest(
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


def _select_cold_start_alps_core_set(
    *,
    candidates: list[AccountAcquisitionCandidate],
    eligible: list[AccountAcquisitionCandidate],
    excluded_count: int,
    budget: int,
    seed: int,
    has_calibrated_ranker: bool,
) -> AccountAcquisitionResult:
    rows = [
        _ScoredCandidate(
            candidate=candidate,
            vector=_required_vector(candidate.alps_embedding, candidate.case_id, "alps_embedding"),
            scores={"alps_vector_norm": round(_vector_norm(candidate.alps_embedding), 6)},
        )
        for candidate in eligible
    ]
    selected_rows = _select_with_platform_coverage(rows, budget=budget, seed=seed, vector_mode="core_set")
    items = _items_from_rows(selected_rows, "alps_core_set")
    return AccountAcquisitionResult(
        strategy="cold_start_alps_core_set",
        items=items,
        manifest=_research_manifest(
            budget=budget,
            candidates=candidates,
            eligible=eligible,
            excluded_count=excluded_count,
            strategy="cold_start_alps_core_set",
            model_state="cold_start_no_reliable_ranker",
            ranker_status="calibrated_model_available" if has_calibrated_ranker else "no_calibrated_model",
            selected_count=len(items),
            seed=seed,
        ),
    )


def _select_warm_start_badge(
    *,
    candidates: list[AccountAcquisitionCandidate],
    eligible: list[AccountAcquisitionCandidate],
    excluded_count: int,
    budget: int,
    seed: int,
) -> AccountAcquisitionResult:
    rows = []
    for candidate in eligible:
        probability = _calibrated_probability(candidate)
        uncertainty = calibrated_uncertainty(probability, calibrated=True)
        rows.append(
            _ScoredCandidate(
                candidate=candidate,
                vector=_required_vector(candidate.badge_embedding, candidate.case_id, "badge_embedding"),
                scores={
                    "calibrated_uncertainty": round(uncertainty, 6),
                    "calibrated_probability": round(float(probability), 6),
                    "badge_vector_norm": round(_vector_norm(candidate.badge_embedding), 6),
                },
            )
        )
    selected_rows = _select_with_platform_coverage(rows, budget=budget, seed=seed, vector_mode="badge")
    items = _items_from_rows(selected_rows, "badge")
    return AccountAcquisitionResult(
        strategy="warm_start_calibrated_uncertainty_badge",
        items=items,
        manifest=_research_manifest(
            budget=budget,
            candidates=candidates,
            eligible=eligible,
            excluded_count=excluded_count,
            strategy="warm_start_calibrated_uncertainty_badge",
            model_state="warm_start_calibrated_model_ranker",
            ranker_status="calibrated_model_available",
            selected_count=len(items),
            seed=seed,
        ),
    )


def _select_with_platform_coverage(
    rows: list[_ScoredCandidate],
    *,
    budget: int,
    seed: int,
    vector_mode: str,
) -> list[_ScoredCandidate]:
    if budget <= 0:
        return []
    selected: list[_ScoredCandidate] = []
    selected_ids: set[str] = set()
    platforms = sorted({row.candidate.platform for row in rows})
    if 1 < len(platforms) <= budget:
        for platform in platforms:
            platform_rows = [row for row in rows if row.candidate.platform == platform]
            index = _initial_index(platform_rows, vector_mode)
            selected.append(platform_rows[index])
            selected_ids.add(platform_rows[index].candidate.case_id)
    remaining = [row for row in rows if row.candidate.case_id not in selected_ids]
    if len(selected) < budget and remaining:
        initial_indices = [_index_by_case_id(remaining, row.candidate.case_id) for row in selected if _index_by_case_id(remaining, row.candidate.case_id) >= 0]
        selected_indices = core_set_select(
            [row.vector.tolist() for row in remaining],
            budget=budget - len(selected),
            seed=seed,
            initial_indices=initial_indices,
        )
        for index in selected_indices:
            row = remaining[index]
            if row.candidate.case_id not in selected_ids:
                selected.append(row)
                selected_ids.add(row.candidate.case_id)
    return selected[:budget]


def _items_from_rows(rows: list[_ScoredCandidate], bucket: str) -> list[AccountAcquisitionItem]:
    items: list[AccountAcquisitionItem] = []
    for rank, row in enumerate(rows, start=1):
        prior = [existing.vector for existing in rows[: rank - 1]]
        diversity = 1.0 if not prior else min(_cosine_distance(row.vector, existing) for existing in prior)
        scores = {**row.scores, "batch_diversity": round(float(diversity), 6)}
        score = float(scores.get("calibrated_uncertainty", 0.0)) + diversity
        items.append(
            AccountAcquisitionItem(
                case_id=row.candidate.case_id,
                account_id=row.candidate.account_id,
                platform=row.candidate.platform,
                event_id=row.candidate.event_id,
                post_ids=list(row.candidate.post_ids),
                priority_rank=rank,
                selection_bucket=bucket,
                scores=scores,
                score=round(score, 6),
            )
        )
    return items


def _eligible_candidates(
    candidates: list[AccountAcquisitionCandidate],
) -> tuple[list[AccountAcquisitionCandidate], int]:
    eligible = [candidate for candidate in candidates if not candidate.has_approved_label]
    return eligible, len(candidates) - len(eligible)


def _has_calibrated_ranker(candidates: list[AccountAcquisitionCandidate]) -> bool:
    return any(
        _candidate_is_calibrated(candidate)
        and _safe_probability(candidate.calibrated_probability if candidate.calibrated_probability is not None else candidate.model_probability) is not None
        for candidate in candidates
    )


def _candidate_is_calibrated(candidate: AccountAcquisitionCandidate) -> bool:
    return bool(candidate.model_is_calibrated and candidate.calibration_source.strip())


def _calibrated_probability(candidate: AccountAcquisitionCandidate) -> float:
    if not _candidate_is_calibrated(candidate):
        raise AcquisitionInputError(
            f"{candidate.case_id} is missing calibration metadata required by warm-start BADGE acquisition"
        )
    probability = _safe_probability(
        candidate.calibrated_probability if candidate.calibrated_probability is not None else candidate.model_probability
    )
    if probability is None:
        raise AcquisitionInputError(f"{candidate.case_id} is missing calibrated_probability")
    return probability


def _required_vector(values: list[float] | None, case_id: str, field_name: str) -> np.ndarray:
    if not values:
        raise AcquisitionInputError(f"{case_id} is missing required {field_name}")
    vector = np.asarray(values, dtype=np.float32)
    if vector.ndim != 1 or vector.size == 0 or not np.isfinite(vector).all():
        raise AcquisitionInputError(f"{case_id} has invalid {field_name}")
    return vector


def _vector_norm(values: list[float] | None) -> float:
    if not values:
        return 0.0
    return float(np.linalg.norm(np.asarray(values, dtype=np.float32)))


def _initial_index(rows: list[_ScoredCandidate], vector_mode: str) -> int:
    if vector_mode == "badge":
        return max(
            range(len(rows)),
            key=lambda index: (
                rows[index].scores.get("calibrated_uncertainty", 0.0),
                rows[index].candidate.case_id,
            ),
        )
    norms = [float(np.linalg.norm(row.vector)) for row in rows]
    return int(np.lexsort((np.arange(len(rows)), -np.asarray(norms)))[0])


def _index_by_case_id(rows: list[_ScoredCandidate], case_id: str) -> int:
    for index, row in enumerate(rows):
        if row.candidate.case_id == case_id:
            return index
    return -1


def _highest_uncertainty_indices(candidates: list[AccountAcquisitionCandidate]) -> list[int]:
    rows = []
    for index, candidate in enumerate(candidates):
        try:
            probability = _calibrated_probability(candidate)
            uncertainty = calibrated_uncertainty(probability, calibrated=True)
        except AcquisitionInputError:
            uncertainty = -1.0
        rows.append((index, uncertainty, candidate.case_id))
    rows.sort(key=lambda row: (row[1], row[2]), reverse=True)
    return [index for index, _uncertainty_value, _case_id in rows if _uncertainty_value >= 0.0]


def _normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    if matrix.ndim == 1:
        matrix = matrix.reshape(-1, 1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-8, None)


def _distance_to_selected(matrix: np.ndarray, selected: list[int]) -> np.ndarray:
    selected_matrix = matrix[selected]
    similarities = matrix @ selected_matrix.T
    distances = 1.0 - similarities.max(axis=1)
    return distances.astype(np.float32)


def _stable_index_choice(indices: list[int], *, seed: int) -> int:
    if not indices:
        raise AcquisitionInputError("cannot choose from an empty candidate list")
    keyed = [
        (hashlib.sha256(f"{seed}:{index}".encode("utf-8")).hexdigest(), index)
        for index in indices
    ]
    return int(min(keyed)[1])


def _score_heuristic_candidate(
    candidate: AccountAcquisitionCandidate,
    *,
    weights: AccountAcquisitionWeights,
    cold_start: bool,
    surprisal: float,
) -> dict[str, float]:
    uncertainty = _uncertainty(candidate.model_probability if candidate.model_is_calibrated else None)
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


def _score_with_heuristic_diversity(
    candidate: AccountAcquisitionCandidate,
    scores: dict[str, float],
    selected: list[tuple[AccountAcquisitionCandidate, dict[str, float], str]],
) -> float:
    diversity = 1.0 if not selected else min(
        _cosine_distance(_heuristic_embedding(candidate), _heuristic_embedding(existing))
        for existing, _scores, _bucket in selected
    )
    return float(scores["base_score"] + (0.20 * diversity))


def _uncertainty(probability: float | None) -> float:
    if probability is None:
        return 0.0
    probability = _clamp(probability)
    return 1.0 - abs(probability - 0.5) * 2.0


def _heuristic_embedding(candidate: AccountAcquisitionCandidate) -> np.ndarray:
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


def _research_manifest(
    *,
    budget: int,
    candidates: list[AccountAcquisitionCandidate],
    eligible: list[AccountAcquisitionCandidate],
    excluded_count: int,
    strategy: str,
    model_state: str,
    ranker_status: str,
    selected_count: int,
    seed: int,
) -> dict[str, Any]:
    return {
        "schema": "cogguard.account_detection.active_learning.v2",
        "algorithm_family": "research_acquisition",
        "strategy": strategy,
        "cold_start_strategy": "alps_core_set",
        "warm_start_strategy": "calibrated_uncertainty_badge",
        "model_state": model_state,
        "ranker_status": ranker_status,
        "selection_backend": "core_set_farthest_first",
        "alps_source": "local_chinese_masked_language_model_or_precomputed_alps_embedding",
        "badge_source": "internal_botrhg_classifier_gradient_embedding",
        "non_claimable_fallback_used": False,
        "budget": int(budget),
        "selected_count": int(selected_count),
        "candidate_count": len(candidates),
        "eligible_count": len(eligible),
        "excluded_approved_label_count": excluded_count,
        "stratified_by": ["platform", "event_id"],
        "label_policy": "model_scores_rank_human_review_only",
        "seed": int(seed),
    }


def _heuristic_manifest(
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
        "schema": "cogguard.account_detection.active_learning.heuristic_baseline.v1",
        "algorithm_family": "heuristic_baseline",
        "strategy": "heuristic_baseline",
        "model_state": "cold_start_no_reliable_ranker" if cold_start else "warm_start_calibrated_model_ranker",
        "ranker_status": "calibrated_model_available" if has_calibrated_ranker else "no_calibrated_model",
        "surprisal_source": "provided_language_model" if has_surprisal else "unavailable",
        "diversity_source": "candidate_embedding_or_deterministic_text_fallback",
        "non_claimable_fallback_used": True,
        "budget": budget,
        "candidate_count": len(candidates),
        "eligible_count": len(eligible),
        "excluded_approved_label_count": excluded_count,
        "stratified_by": ["platform", "event_id"],
        "label_policy": "model_scores_rank_human_review_only",
        "weights": asdict(weights),
    }


def _safe_probability(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return _clamp(number)


def _clamp(value: float) -> float:
    if math.isnan(float(value)):
        return 0.0
    return max(0.0, min(1.0, float(value)))
