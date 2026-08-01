"""Public contracts for the internal BotRHG transfer pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "AccountSample",
    "DatasetManifest",
    "EvaluationReport",
    "ModelConfig",
    "TrainingConfig",
]


@dataclass(frozen=True, slots=True)
class AccountSample:
    """One labeled account with normalized account-level text."""

    account_id: str
    label: int
    text: str
    post_count: int
    source_file_hash: str
    source_encoding: str
    dataset_name: str = "botection"
    source_label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    split_group: str = ""


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Provenance and coverage information for one loaded corpus."""

    source_root: str
    label_file: str
    text_directory: str
    data_fingerprint: str
    labeled_account_count: int
    usable_account_count: int
    skipped_empty_text_count: int
    missing_text_count: int
    class_counts: dict[str, int]
    property_field_coverage: dict[str, float] = field(default_factory=dict)
    social_graph_coverage: str = "unavailable"
    dataset_name: str = "botection"
    label_provenance: str = ""
    text_provenance: str = ""
    source_archive_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Trainable model settings, separated from dataset and output paths."""

    text_model_path: str = ""
    hidden_dim: int = 128
    projection_dim: int = 64
    dropout: float = 0.2
    max_length: int = 256
    batch_size: int = 8
    max_chunks_per_account: int = 8
    encoder_trainable: bool = False
    support_k: int = 8
    routing_budget: float = 0.10
    correction_weight: float = 1.0
    max_posts_per_account: int = 64


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    """Reproducible training and split settings."""

    seed: int = 42
    validation_size: float = 0.15
    test_size: float = 0.20
    base_epochs: int = 3
    correction_epochs: int = 3
    learning_rate: float = 2e-3
    encoder_learning_rate: float = 2e-5
    device: str = "cpu"
    dataset_name: str = "botection"
    model: ModelConfig = field(default_factory=ModelConfig)


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Comparable classification metrics for base and corrected predictions."""

    sample_count: int
    accuracy: float
    macro_f1: float
    macro_precision: float
    macro_recall: float
    roc_auc: float | None
    confusion_matrix: list[list[int]]
    routed_count: int
    routing_budget: float
    split: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def as_numpy(values: list[float] | np.ndarray) -> np.ndarray:
    """Convert a numeric sequence to a stable float32 vector."""

    return np.asarray(values, dtype=np.float32)


def ensure_output_path(path: str | Path) -> Path:
    """Create and return an output directory path."""

    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    return output
