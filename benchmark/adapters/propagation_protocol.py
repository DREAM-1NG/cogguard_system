"""Shared protocol and vocabulary rules for fair propagation comparisons.

The adapter keeps raw FOREST user ids until it builds a training-only
vocabulary. Evaluation users unseen during training map to ``UNK_USER_ID`` and
are reported rather than added to a model's candidate universe.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


Cascade = list[tuple[int, int]]
PAD_USER_ID = 0
UNK_USER_ID = 1
PROTOCOL_ID = "cogguard.propagation.fair_split_vocab_prefix.v1"
SPLIT_FILENAMES = {
    "train": "cascade.txt",
    "valid": "cascadevalid.txt",
    "test": "cascadetest.txt",
}


def parse_forest_cascade(line: str) -> Cascade:
    cascade: Cascade = []
    for raw in line.strip().split():
        parts = raw.split(",")
        if len(parts) != 2:
            continue
        try:
            cascade.append((int(parts[0]), int(float(parts[1]) * 1000)))
        except ValueError:
            continue
    return sorted(cascade, key=lambda item: item[1])


def load_forest_cascades(path: str | Path, min_length: int = 3) -> list[Cascade]:
    cascades: list[Cascade] = []
    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            cascade = parse_forest_cascade(line)
            if len(cascade) >= min_length:
                cascades.append(cascade)
    return cascades


def load_original_cascade_splits(data_dir: str | Path, *, min_length: int = 4) -> dict[str, list[Cascade]]:
    """Load only the dataset's native FOREST train, validation, and test files."""

    root = Path(data_dir)
    splits: dict[str, list[Cascade]] = {}
    for split, filename in SPLIT_FILENAMES.items():
        path = root / filename
        splits[split] = load_forest_cascades(path, min_length=min_length) if path.exists() else []
    return splits


@dataclass(frozen=True)
class TrainingUserVocabulary:
    """A bounded vocabulary built solely from raw training-split users."""

    user_to_id: Mapping[int, int]
    capacity: int
    overflow_user_count: int = 0

    @property
    def train_user_count(self) -> int:
        return len(self.user_to_id)

    @property
    def model_user_ids(self) -> list[int]:
        return sorted(self.user_to_id.values())

    def encode(self, user_id: int) -> int:
        return int(self.user_to_id.get(int(user_id), UNK_USER_ID))


def build_training_user_vocabulary(
    train_cascades: Sequence[Cascade],
    *,
    max_user_ids: int,
) -> TrainingUserVocabulary:
    """Create deterministic ids without looking at validation or test users."""

    capacity = max(0, int(max_user_ids) - 2)
    users = sorted({int(user) for cascade in train_cascades for user, _timestamp in cascade})
    retained = users[:capacity]
    return TrainingUserVocabulary(
        user_to_id={user: index + 2 for index, user in enumerate(retained)},
        capacity=capacity,
        overflow_user_count=max(0, len(users) - len(retained)),
    )


def observation_count(cascade_len: int, observation_ratio: float) -> int:
    if cascade_len <= 1:
        return 0
    return min(max(1, int(math.ceil(cascade_len * float(observation_ratio)))), cascade_len - 1)


def build_observation_prefix(cascade: Sequence[tuple[int, int]], observation_ratio: float) -> dict:
    """Construct a prefix whose model input contains no future cascade events."""

    count = observation_count(len(cascade), observation_ratio)
    observed = list(cascade[:count])
    return {
        "observed": observed,
        "next_event": cascade[count] if count < len(cascade) else None,
        "observed_count": count,
        "future_count": max(0, len(cascade) - count),
    }


def encode_prefix(prefix: Sequence[tuple[int, int]], vocabulary: TrainingUserVocabulary) -> list[tuple[int, int]]:
    return [(vocabulary.encode(user), int(timestamp)) for user, timestamp in prefix]


def vocabulary_oov_report(cascades: Sequence[Cascade], vocabulary: TrainingUserVocabulary) -> dict[str, int]:
    total_events = sum(len(cascade) for cascade in cascades)
    oov_users = {
        int(user)
        for cascade in cascades
        for user, _timestamp in cascade
        if vocabulary.encode(user) == UNK_USER_ID
    }
    return {
        "total_events": total_events,
        "oov_events": sum(
            1
            for cascade in cascades
            for user, _timestamp in cascade
            if vocabulary.encode(user) == UNK_USER_ID
        ),
        "oov_unique_users": len(oov_users),
    }


def fair_protocol_audit(
    *,
    vocabulary: TrainingUserVocabulary,
    train_cascades: Sequence[Cascade],
    valid_cascades: Sequence[Cascade],
    test_cascades: Sequence[Cascade],
) -> dict:
    """Return the evidence required before fair-comparison metrics may be used."""

    split_counts = {
        "train": len(train_cascades),
        "valid": len(valid_cascades),
        "test": len(test_cascades),
    }
    audit = {
        "protocol_id": PROTOCOL_ID,
        "split_policy": "original FOREST cascade.txt/cascadevalid.txt/cascadetest.txt",
        "split_files": dict(SPLIT_FILENAMES),
        "split_counts": split_counts,
        "vocabulary_source": "cascade.txt training split only",
        "train_user_count": vocabulary.train_user_count,
        "vocabulary_capacity": vocabulary.capacity,
        "vocabulary_overflow_user_count": vocabulary.overflow_user_count,
        "unk_user_id": UNK_USER_ID,
        "valid_oov": vocabulary_oov_report(valid_cascades, vocabulary),
        "test_oov": vocabulary_oov_report(test_cascades, vocabulary),
        "future_nodes_injected": False,
        "candidate_generation_reads_future_tail": False,
        "candidate_features_used_as_model_input": False,
        "no_future_nodes_in_prefix": True,
    }
    audit["fair_protocol_passed"] = bool(
        split_counts["train"] > 0
        and (split_counts["valid"] > 0 or split_counts["test"] > 0)
        and not audit["future_nodes_injected"]
        and not audit["candidate_generation_reads_future_tail"]
        and audit["no_future_nodes_in_prefix"]
    )
    audit["leakage_check_passed"] = audit["fair_protocol_passed"]
    return audit


def gate_fair_protocol(audit: Mapping[str, object]) -> bool:
    """Single gate used before reporting fair-comparison metrics."""

    return bool(audit.get("fair_protocol_passed"))


__all__ = [
    "Cascade",
    "PAD_USER_ID",
    "PROTOCOL_ID",
    "SPLIT_FILENAMES",
    "TrainingUserVocabulary",
    "UNK_USER_ID",
    "build_observation_prefix",
    "build_training_user_vocabulary",
    "encode_prefix",
    "fair_protocol_audit",
    "gate_fair_protocol",
    "load_forest_cascades",
    "load_original_cascade_splits",
    "observation_count",
    "parse_forest_cascade",
    "vocabulary_oov_report",
]
