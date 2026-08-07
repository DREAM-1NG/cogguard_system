"""Feature assembly utilities for the strict BotRHG implementation."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
import torch

from .strict_contracts import StrictAccountRecord, StrictFeatureSchema, StrictGraph, StrictRelationEdge

__all__ = [
    "STRICT_CATEGORICAL_FIELDS",
    "STRICT_NUMERIC_FIELDS",
    "assemble_property_tensor",
    "assemble_relation_tensors",
    "build_feature_schema",
    "build_node_index",
    "derive_numeric_stats",
    "linearize_account_text",
    "normalize_nlpcc_text",
    "sample_texts",
    "split_records",
]

STRICT_NUMERIC_FIELDS: tuple[str, ...] = (
    "followers_count",
    "friends_count",
    "statuses_count",
    "favourites_count",
    "listed_count",
    "post_count",
    "description_length",
    "avg_tweet_length",
    "duplicate_ratio",
    "url_rate",
    "mention_rate",
    "hashtag_rate",
    "reply_rate",
    "retweet_rate",
    "account_age_days",
)

STRICT_CATEGORICAL_FIELDS: tuple[str, ...] = (
    "verified",
    "protected",
    "geo_enabled",
    "default_profile",
    "default_profile_image",
    "profile_use_background_image",
    "lang",
    "time_zone",
)


def normalize_nlpcc_text(text: str) -> str:
    """Normalize URLs, mentions, hashtags, and whitespace for RoBERTa input."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"https?://\S+", " HTTPURL ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)@\w+", " @USER ", text)
    text = re.sub(r"(?<!\w)#\w+", " #HASHTAG ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def linearize_account_text(
    profile_parts: list[str],
    description: str,
    tweets: list[str],
) -> str:
    """Compose the strict BotRHG text sequence with explicit segment markers."""

    segments: list[str] = []
    if profile_parts:
        segments.append("[P] " + " ".join(part for part in profile_parts if part))
    if description:
        segments.append("[D] " + description)
    if tweets:
        segments.append("[T] " + " </s> ".join(tweets))
    return normalize_nlpcc_text(" ".join(segment for segment in segments if segment))


def sample_texts(texts: list[str], limit: int) -> list[str]:
    """Deterministically sample a bounded number of texts while covering the span."""

    if limit <= 0 or len(texts) <= limit:
        return texts
    positions = sorted({round(index * (len(texts) - 1) / max(limit - 1, 1)) for index in range(limit)})
    return [texts[position] for position in positions]


def build_feature_schema(records: list[StrictAccountRecord]) -> StrictFeatureSchema:
    """Derive categorical vocabularies from the training split."""

    categorical_vocab: dict[str, tuple[str, ...]] = {}
    for field in STRICT_CATEGORICAL_FIELDS:
        values = sorted({str(record.categorical_features.get(field, "")).strip() for record in records if str(record.categorical_features.get(field, "")).strip()})
        categorical_vocab[field] = tuple(values)
    return StrictFeatureSchema(
        numeric_fields=STRICT_NUMERIC_FIELDS,
        categorical_fields=STRICT_CATEGORICAL_FIELDS,
        categorical_vocab=categorical_vocab,
    )


def derive_numeric_stats(
    records: list[StrictAccountRecord],
    schema: StrictFeatureSchema,
) -> dict[str, tuple[float, float]]:
    """Compute normalization statistics from the training split."""

    stats: dict[str, tuple[float, float]] = {}
    for field in schema.numeric_fields:
        values = np.asarray([float(record.numeric_features.get(field, 0.0)) for record in records], dtype=np.float32)
        if values.size == 0:
            stats[field] = (0.0, 1.0)
            continue
        mean = float(values.mean())
        std = float(values.std())
        if std <= 1e-6:
            std = 1.0
        stats[field] = (mean, std)
    return stats


def assemble_property_tensor(
    records: list[StrictAccountRecord],
    schema: StrictFeatureSchema,
    numeric_stats: dict[str, tuple[float, float]],
    *,
    device: torch.device,
) -> torch.Tensor:
    """Assemble normalized numeric features plus one-hot categorical indicators."""

    numeric_rows: list[list[float]] = []
    cat_rows: list[list[float]] = []
    cat_offsets: dict[str, int] = {}
    categorical_fields = tuple(
        field for field in schema.categorical_fields if field in STRICT_CATEGORICAL_FIELDS
    )
    offset = 0
    for field in categorical_fields:
        vocab = schema.categorical_vocab.get(field, ())
        cat_offsets[field] = offset
        offset += len(vocab) + 1

    for record in records:
        numeric_row = []
        for field in schema.numeric_fields:
            mean, std = numeric_stats.get(field, (0.0, 1.0))
            raw_value = float(record.numeric_features.get(field, 0.0))
            numeric_row.append((raw_value - mean) / std)
        cat_row = [0.0] * offset
        for field in categorical_fields:
            value = str(record.categorical_features.get(field, "")).strip()
            vocab = schema.categorical_vocab.get(field, ())
            if not vocab:
                continue
            try:
                index = vocab.index(value) + 1
            except ValueError:
                index = 0
            cat_row[cat_offsets[field] + index] = 1.0
        numeric_rows.append(numeric_row)
        cat_rows.append(cat_row)

    numeric_tensor = torch.tensor(numeric_rows, dtype=torch.float32, device=device)
    categorical_tensor = torch.tensor(cat_rows, dtype=torch.float32, device=device)
    if categorical_tensor.numel():
        return torch.cat([numeric_tensor, categorical_tensor], dim=1)
    return numeric_tensor


def build_node_index(records: list[StrictAccountRecord]) -> dict[str, int]:
    """Map account ids to stable node indices."""

    return {record.account_id: index for index, record in enumerate(records)}


def assemble_relation_tensors(
    graph: StrictGraph,
    node_index: dict[str, int],
    *,
    device: torch.device,
) -> tuple[torch.Tensor | None, torch.Tensor | None, tuple[str, ...]]:
    """Convert graph edges into PyG-compatible tensors."""

    if not graph.available or not graph.edges:
        return None, None, graph.relation_types
    relation_index = {relation: index for index, relation in enumerate(graph.relation_types)}
    edge_index_rows: list[tuple[int, int]] = []
    edge_types: list[int] = []
    for edge in graph.edges:
        if edge.source_account_id not in node_index or edge.target_account_id not in node_index:
            continue
        edge_index_rows.append((node_index[edge.source_account_id], node_index[edge.target_account_id]))
        edge_types.append(relation_index.get(edge.relation_type, 0))
    if not edge_index_rows:
        return None, None, graph.relation_types
    edge_index = torch.tensor(edge_index_rows, dtype=torch.long, device=device).t().contiguous()
    edge_type = torch.tensor(edge_types, dtype=torch.long, device=device)
    return edge_index, edge_type, graph.relation_types


def split_records(
    records: list[StrictAccountRecord],
    *,
    validation_size: float = 0.15,
    test_size: float = 0.20,
    seed: int = 42,
) -> dict[str, list[StrictAccountRecord]]:
    """Create deterministic stratified train/validation/test splits."""

    if validation_size < 0 or test_size < 0 or validation_size + test_size >= 1:
        raise ValueError("validation_size and test_size must be non-negative and sum below one")
    if len(records) < 4:
        raise ValueError("at least four labeled accounts are required for a split")
    from sklearn.model_selection import train_test_split

    indices = list(range(len(records)))
    labels = [record.label for record in records]
    train_idx, holdout_idx = train_test_split(
        indices,
        test_size=validation_size + test_size,
        random_state=seed,
        stratify=labels,
    )
    holdout_labels = [labels[index] for index in holdout_idx]
    relative_test = test_size / (validation_size + test_size)
    validation_idx, test_idx = train_test_split(
        holdout_idx,
        test_size=relative_test,
        random_state=seed,
        stratify=holdout_labels,
    )
    return {
        "train": [records[index] for index in train_idx],
        "validation": [records[index] for index in validation_idx],
        "test": [records[index] for index in test_idx],
    }


def feature_coverage(records: list[StrictAccountRecord], field_names: tuple[str, ...], *, numeric: bool) -> dict[str, float]:
    """Measure how much of each strict feature field is populated."""

    coverage: dict[str, float] = {}
    total = max(len(records), 1)
    for field in field_names:
        if numeric:
            count = sum(1 for record in records if field in record.numeric_features)
        else:
            count = sum(1 for record in records if str(record.categorical_features.get(field, "")).strip())
        coverage[field] = round(count / total, 4)
    return coverage


def parse_timestamp(value: Any) -> datetime | None:
    """Parse a few common dataset timestamp formats."""

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.removesuffix("Z") + ("+00:00" if text.endswith("Z") else ""))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        pass
    candidates = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%d",
    )
    for pattern in candidates:
        try:
            parsed = datetime.strptime(text, pattern)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    return None
