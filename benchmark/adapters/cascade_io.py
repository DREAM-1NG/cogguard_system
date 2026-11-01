from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

from benchmark.adapters.propagation_protocol import (
    load_forest_cascades as _load_protocol_cascades,
    load_original_cascade_splits,
    parse_forest_cascade,
)


Cascade = List[Tuple[int, int]]
EdgeStream = List[Tuple[int, int, float]]


def load_forest_cascades(path: str | Path, min_length: int = 3) -> List[Cascade]:
    return _load_protocol_cascades(path, min_length=min_length)


def load_forest_split(data_dir: str | Path) -> Tuple[List[Cascade], List[Cascade], List[Cascade]]:
    splits = load_original_cascade_splits(data_dir, min_length=4)
    return splits["train"], splits["valid"], splits["test"]


def train_statistics(cascades: Sequence[Cascade]) -> Tuple[Counter, Dict[int, Counter]]:
    popularity = Counter()
    transitions: Dict[int, Counter] = defaultdict(Counter)
    for cascade in cascades:
        users = [user for user, _ in cascade]
        popularity.update(users)
        for parent, child in zip(users, users[1:]):
            if parent != child:
                transitions[parent][child] += 1
    return popularity, transitions


def unique_preserving_order(values: Iterable[int]) -> List[int]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def msle(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    pred = y_pred.copy()
    pred[pred < 1] = 1
    return float(np.mean(np.square(np.log2(pred) - np.log2(y_true))))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_pred - y_true)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(y_pred - y_true))))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1))) * 100.0)


def direction_accuracy(y_true: np.ndarray, y_pred: np.ndarray, observed: np.ndarray, threshold: float = 0.1) -> float:
    true_growth = y_true >= observed * (1.0 + threshold)
    pred_growth = y_pred >= observed * (1.0 + threshold)
    return float(np.mean(true_growth == pred_growth))


def forest_to_casft_dataset(
    data_dir: str | Path,
    output_dir: str | Path,
    max_events: int | None = None,
    *,
    observation_time: int = 86400,
    prediction_time: int = 1296000,
    obs_ratio: float = 0.3,
    min_observed: int = 10,
) -> Path:
    """Export FOREST cascades to the raw CasFT dataset.txt shape.

    CasFT expects five tab-separated fields:
    cascade_id, source/user id, publish_time, adoption_count, path:time items.
    FOREST does not expose true retweet parents. To keep CasFT preprocessing from
    seeing an empty global graph, each non-source adoption is represented as a
    conservative source/child star path. FOREST timestamps can be much sparser
    than CasFT's one-day observation window, so relative times are monotonically
    rescaled into the requested prediction horizon and enough early adoptions are
    placed before ``observation_time`` for CasFT's ``p_o >= 10`` filter. This is
    a protocol adapter, not a replacement for the official CasFT tree-path
    datasets.
    """

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "dataset.txt"
    train, valid, test = load_forest_split(data_dir)
    cascades = (train + valid + test)[:max_events] if max_events else (train + valid + test)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for idx, cascade in enumerate(cascades):
            if not cascade:
                continue
            start = cascade[0][1]
            adoptions = []
            source = cascade[0][0]
            rel_times = _scale_cascade_times_for_casft(
                [timestamp for _user, timestamp in cascade],
                observation_time=observation_time,
                prediction_time=prediction_time,
                obs_ratio=obs_ratio,
                min_observed=min_observed,
            )
            for index, (user, ts) in enumerate(cascade):
                rel_ts = rel_times[index] if index < len(rel_times) else max(int(ts - start), 0)
                if index == 0 or user == source:
                    adoptions.append(f"{user}:{rel_ts}")
                else:
                    adoptions.append(f"{source}/{user}:{rel_ts}")
            handle.write(f"{idx}\t{source}\t{start}\t{len(cascade)}\t{' '.join(adoptions)}\n")
    return path


def _scale_cascade_times_for_casft(
    timestamps: Sequence[int],
    *,
    observation_time: int,
    prediction_time: int,
    obs_ratio: float,
    min_observed: int,
) -> List[int]:
    """Map arbitrary FOREST cascade times to CasFT's relative time horizon."""

    if not timestamps:
        return []
    n_items = len(timestamps)
    observation_time = max(1, int(observation_time))
    prediction_time = max(observation_time + 1, int(prediction_time))
    min_observed = max(1, int(min_observed))
    obs_count = min(n_items, max(min_observed, int(math.ceil(n_items * max(0.0, min(obs_ratio, 1.0))))))
    obs_count = max(1, obs_count)
    early_span = max(1, observation_time - 1)
    late_span = max(1, prediction_time - observation_time - 1)

    if n_items == 1:
        return [0]

    scaled: List[int] = []
    for idx in range(n_items):
        if idx < obs_count:
            denom = max(obs_count, 1)
            rel_ts = int(math.floor(idx * early_span / denom))
            rel_ts = min(rel_ts, observation_time - 1)
        else:
            denom = max(n_items - obs_count, 1)
            rel_ts = observation_time + int(math.floor((idx - obs_count) * late_span / denom))
            rel_ts = min(rel_ts, prediction_time - 1)
        if scaled and rel_ts <= scaled[-1]:
            rel_ts = min(prediction_time - 1, scaled[-1] + 1)
        scaled.append(rel_ts)
    return scaled


def forest_to_temporal_edges(
    data_dir: str | Path,
    output_csv: str | Path,
    *,
    max_cascades: int | None = None,
    include_split: bool = True,
) -> Path:
    """Export FOREST cascades to a DyGLib/TGN-compatible temporal edge stream."""

    root = Path(data_dir)
    split_files = [("train", root / "cascade.txt"), ("valid", root / "cascadevalid.txt"), ("test", root / "cascadetest.txt")]
    rows: List[Tuple[int, int, float, int, int, str]] = []
    event_idx = 0
    for split, file_path in split_files:
        if not file_path.exists():
            continue
        for cascade in load_forest_cascades(file_path, min_length=4):
            if max_cascades is not None and event_idx >= max_cascades:
                break
            for (src, src_ts), (dst, dst_ts) in zip(cascade, cascade[1:]):
                if src == dst:
                    continue
                rows.append((src, dst, float(dst_ts), 0, event_idx, split))
            event_idx += 1
        if max_cascades is not None and event_idx >= max_cascades:
            break

    rows.sort(key=lambda row: row[2])
    path = Path(output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        header = ["u", "i", "ts", "label", "feat", "event_id"]
        if include_split:
            header.append("split")
        writer.writerow(header)
        for src, dst, ts, label, event_id, split in rows:
            row = [src, dst, ts, label, 0.0, event_id]
            if include_split:
                row.append(split)
            writer.writerow(row)
    return path


def dyglib_raw_csv_from_edge_stream(edge_csv: str | Path, output_csv: str | Path, *, reindex: bool = True) -> Path:
    """Create the exact raw CSV that DyGLib preprocess_data.py accepts."""

    source = Path(edge_csv)
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding="utf-8", newline="") as src:
        reader = csv.DictReader(src)
        rows = list(reader)
    src_map: Dict[str, int] = {}
    dst_map: Dict[str, int] = {}
    if reindex:
        for row in rows:
            src_value = str(row["u"])
            dst_value = str(row["i"])
            if src_value not in src_map:
                src_map[src_value] = len(src_map)
            if dst_value not in dst_map:
                dst_map[dst_value] = len(dst_map)
    with target.open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst)
        writer.writerow(["u", "i", "ts", "label", "feat"])
        for row in rows:
            src_id = src_map[str(row["u"])] if reindex else row["u"]
            dst_id = dst_map[str(row["i"])] if reindex else row["i"]
            writer.writerow([src_id, dst_id, row["ts"], row.get("label", 0), row.get("feat", 0.0)])
    return target


def cascade_scale_baseline(train: Sequence[Cascade], test: Sequence[Cascade], obs_ratio: float, multiplier: str = "median") -> Dict:
    ratios = []
    for cascade in train:
        cut = max(2, int(len(cascade) * obs_ratio))
        if cut < len(cascade):
            ratios.append(len(cascade) / cut)
    growth = float(np.mean(ratios) if multiplier == "mean" and ratios else np.median(ratios) if ratios else 1.0)
    observed = np.asarray([max(2, int(len(cascade) * obs_ratio)) for cascade in test], dtype=float)
    y_true = np.asarray([len(cascade) for cascade in test], dtype=float)
    y_pred = np.maximum(observed * growth, observed)
    return {
        "observed": observed,
        "y_true": y_true,
        "y_pred": y_pred,
        "growth_multiplier": growth,
    }


def hits_map_mrr_ndcg(labels: np.ndarray, relevant_count: int, k_list: Sequence[int]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    relevant_positions = np.flatnonzero(labels == 1)
    result["mrr"] = 1.0 / float(relevant_positions[0] + 1) if len(relevant_positions) else 0.0
    for k in k_list:
        top_k = labels[:k]
        result[f"hits@{k}"] = float(top_k.sum() / max(relevant_count, 1))
        result[f"map@{k}"] = average_precision_at_k(top_k, relevant_count)
        result[f"ndcg@{k}"] = ndcg_at_k(top_k, relevant_count)
    return result


def average_precision_at_k(labels: np.ndarray, relevant_count: int) -> float:
    relevant_seen = 0
    precision_sum = 0.0
    for idx, label in enumerate(labels, start=1):
        if label == 1:
            relevant_seen += 1
            precision_sum += relevant_seen / idx
    return float(precision_sum / max(relevant_count, 1))


def ndcg_at_k(labels: np.ndarray, relevant_count: int) -> float:
    dcg = 0.0
    for idx, label in enumerate(labels, start=1):
        if label == 1:
            dcg += 1.0 / math.log2(idx + 1)
    ideal_hits = min(relevant_count, len(labels))
    idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, ideal_hits + 1))
    return float(dcg / idcg) if idcg else 0.0
