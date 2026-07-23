"""CoordinationDiscover reproduction utilities for IO coordination experiments.

The module is intentionally lightweight: it implements paper-faithful smoke
versions of Unmasking/LLM baselines and a DynaCoLM-GNN prototype. Optional
dependencies are used when present, while deterministic numpy/networkx
fallbacks keep tests and small server runs reproducible.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import pickle
import re
import shlex
import shutil
import subprocess
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import networkx as nx
import numpy as np
import pandas as pd
from networkx.algorithms.community import greedy_modularity_communities, louvain_communities
from networkx.algorithms.community.quality import modularity

from app.core.coordination_baseline.characterization import CharacterizationConfig, characterize_detect_output
from app.core.coordination_baseline.deep_graph import (
    DEPRECATED_DISCOVER_ENCODERS,
    DeepGraphDiscoverConfig,
    DeepGraphDiscoverResult,
    STABLE_DISCOVER_ENCODER,
    run_deep_graph_discover,
)


IOHUNTER_REPO_URL = "https://github.com/mminici/SocGFM.git"
IOHUNTER_ZENODO_DATA_URL = "https://zenodo.org/api/records/13357621/files/data.zip/content"
IOHUNTER_ZENODO_DATA_SIZE = 1_214_021_087
IOHUNTER_DATASETS = ("UAE", "cuba", "russia", "venezuela", "iran", "china")
IOHUNTER_PRIMARY_SCRIPT = "run_MultiModalGNN_CrossAttention.py"
IOHUNTER_CROSS_COUNTRY_SCRIPT = "run_MultiModalGNN_CrossAttention_CrossCountryPlusFineTuning.py"
IOHUNTER_BASELINE_SCRIPTS = ("run_NodePruning.py", "run_Node2Vec.py")
IOHUNTER_REQUIRED_PACKAGES = (
    "numpy",
    "pandas",
    "networkx",
    "scipy",
    "sklearn",
    "torch",
    "torch_geometric",
    "node2vec",
    "mlflow",
    "tqdm",
)
DEFAULT_RELATIONS = (
    "url_share",
    "hashtag_share",
    "retweet_target",
    "reply_target",
    "quote_target",
    "mention_target",
)
IOHUNTER_GRAPH_RELATION_MAP = {
    "coRT": "retweet_target",
    "coURL": "url_share",
    "hashSeq": "hashtag_share",
    "fastRT": "fast_retweet",
    "tweetSim": "tweet_similarity",
}
IOHUNTER_CANONICAL_RELATIONS = tuple(dict.fromkeys(IOHUNTER_GRAPH_RELATION_MAP.values()))
TARGET_RELATIONS = {"retweet_target", "reply_target", "quote_target", "mention_target"}
TEXT_COLUMNS = (
    "content",
    "text",
    "tweet_text",
    "body",
    "desc",
    "description",
    "title",
    "note_text",
    "post_text",
)
LABEL_COLUMNS = ("label", "is_io_driver", "io_driver", "target")
# Kept for backward-compatible CLI parsing and historical ablation replay.
# CoordinationDiscover Discover mainline no longer activates Unmasking-style node pruning.
DISCOVER_STRUCTURE_FILTERS = ("none", "node_pruning")
DISCOVER_STRUCTURE_FILTER_METRICS = ("degree", "pagerank", "eigenvector")
_LM_FEATURE_CACHE: dict[tuple[str, int, int, int, tuple[str, ...]], tuple[np.ndarray, str]] = {}
TOKEN_RE = re.compile(r"[A-Za-z0-9_#@:/.-]+", re.UNICODE)
METRIC_FIELDS = ("precision", "recall", "f1", "auc", "support", "positive_count")
IOHUNTER_LOG_METRIC_RE = re.compile(
    r"^[\ufeff\s]*\[(?P<split>[^\]]+)\]\s+(?P<metric>[A-Za-z0-9_]+):\s+"
    r"(?P<mean>[-+0-9.eE]+|nan|None)\+\-(?P<std>[-+0-9.eE]+|nan|None)",
    re.MULTILINE,
)


@dataclass(slots=True)
class MetricResult:
    precision: float
    recall: float
    f1: float
    auc: float | None
    support: int
    positive_count: int


@dataclass(slots=True)
class Split:
    train: np.ndarray
    test: np.ndarray


@dataclass(slots=True)
class PreparedDetectInputs:
    discovery: Mapping[str, object]
    labels: Mapping[str, int]
    nodes: list[str]
    discover_features: np.ndarray
    lm_features: np.ndarray
    features: np.ndarray
    y: np.ndarray
    node_records: dict[str, dict[str, object]]
    graphs: dict[str, nx.Graph]
    lm_feature_source: str
    discover_feature_count: int
    lm_feature_count: int
    discover_embedding_dim: int
    reweighted_edge_count: int
    uses_discover_reweighted_edges: bool


@dataclass(slots=True)
class CommunityDetectionResult:
    communities: list[set[str]]
    requested_algorithm: str
    effective_algorithm: str
    backend: str
    fallback_reason: str | None = None


def read_event_table(path: Path) -> pd.DataFrame:
    """Read a CSV/JSON/JSONL event table and normalize common column names."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path)
    elif suffix in {".jsonl", ".ndjson"}:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        frame = pd.DataFrame(rows)
    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        frame = pd.DataFrame(data if isinstance(data, list) else data.get("records", []))
    else:
        raise ValueError(f"Unsupported event table format: {path}")
    return normalize_event_table(frame)


def normalize_event_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a defensive copy with the minimum schema used by experiments."""
    normalized = frame.copy()
    rename_map = {
        "userid": "account_id",
        "user_id": "account_id",
        "uid": "account_id",
        "author_id": "account_id",
        "relation_type": "relation",
        "event_type": "relation",
        "action_type": "relation",
        "interaction_type": "relation",
        "channel": "relation",
        "entity": "object_id",
        "object": "object_id",
        "tweet_time": "timestamp",
        "created_at": "timestamp",
        "time": "timestamp",
        "tweetid": "content_id",
        "post_id": "content_id",
        "note_id": "content_id",
        "aweme_id": "content_id",
        "video_id": "content_id",
        "target_user": "target_account_id",
        "target_user_id": "target_account_id",
        "target_uid": "target_account_id",
        "reply_to_user_id": "target_account_id",
    }
    normalized = normalized.rename(columns={key: value for key, value in rename_map.items() if key in normalized})
    copy_alias_map = {
        "platform": ("source_platform", "platform_name", "app_name"),
        "nickname": ("author_name", "user_name", "display_name", "name"),
        "screen_name": ("username", "handle", "user_handle", "author_handle"),
        "profile_url": ("user_url", "account_url", "author_url", "homepage", "home_url", "profile_link"),
        "post_url": ("note_url", "video_url", "aweme_url", "share_url", "link", "post_link"),
        "comment_id": ("commentid",),
        "note_id": ("noteid",),
        "aweme_id": ("awemeid",),
        "video_id": ("videoid",),
    }
    for canonical, aliases in copy_alias_map.items():
        if canonical in normalized:
            continue
        for alias in aliases:
            if alias in normalized:
                normalized[canonical] = normalized[alias]
                break
    if "account_id" not in normalized:
        raise ValueError("Event table must contain account_id/userid/user_id")
    if "relation" not in normalized:
        normalized["relation"] = "content"
    if "object_id" not in normalized:
        normalized["object_id"] = normalized.get("target_account_id", normalized["relation"]).astype(str)
    if "timestamp" not in normalized:
        normalized["timestamp"] = 0
    if "content_id" not in normalized:
        normalized["content_id"] = [f"content-{index}" for index in range(len(normalized))]
    if "content" not in normalized:
        for alias in TEXT_COLUMNS[1:]:
            if alias in normalized:
                normalized["content"] = normalized[alias]
                break
    normalized["account_id"] = normalized["account_id"].map(_canonical_account_id)
    normalized["relation"] = normalized["relation"].astype(str)
    normalized["object_id"] = normalized["object_id"].astype(str)
    normalized["content_id"] = normalized["content_id"].astype(str)
    if "target_account_id" in normalized:
        normalized["target_account_id"] = normalized["target_account_id"].map(_canonical_account_id)
    for column in TEXT_COLUMNS:
        if column in normalized:
            normalized[column] = normalized[column].fillna("").astype(str)
    for column in LABEL_COLUMNS:
        if column in normalized:
            normalized[column] = normalized[column].fillna(0).astype(int)
            break
    return normalized


def _canonical_account_id(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer() and re.fullmatch(r"[-+]?\d+(?:\.0+)?", text):
        return str(int(number))
    return text


def load_iohunter_processed_dataset(
    dataset_dir: Path,
    *,
    threshold: str = "0.7",
    train_percentage: str | None = None,
    undersampling: str | None = None,
) -> dict[str, object]:
    filename = f"{threshold}_datasets.pkl"
    if train_percentage and train_percentage != "0.6":
        filename += f"_{train_percentage}"
    if undersampling is not None:
        filename += f"_{undersampling}U"
    path = dataset_dir / filename
    with path.open("rb") as file_handle:
        data = pickle.load(file_handle)
    if not isinstance(data, dict):
        raise ValueError(f"Unsupported IOHunter processed dataset object: {path}")
    return data


def iohunter_processed_to_event_table(
    dataset: Mapping[str, object],
    *,
    dataset_name: str,
    relations: Mapping[str, str] = IOHUNTER_GRAPH_RELATION_MAP,
    max_edges_per_relation: int | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    labels = np.asarray(dataset.get("labels", []), dtype=int)
    graph = dataset.get("graph")
    all_nodes = set(range(int(labels.shape[0]))) if labels.size else set()
    if hasattr(graph, "nodes"):
        all_nodes.update(int(node) for node in graph.nodes())
    for node in sorted(all_nodes):
        label = int(labels[node]) if 0 <= node < labels.shape[0] else 0
        rows.append(
            {
                "account_id": str(node),
                "relation": "profile",
                "object_id": f"{dataset_name}:profile:{node}",
                "timestamp": 0.0,
                "content_id": f"{dataset_name}:profile:{node}",
                "content": f"iohunter user {node} label {label}",
                "label": label,
                "source_graph": "labels",
                "edge_weight": 0.0,
            }
        )

    for graph_name, relation in relations.items():
        relation_graph = dataset.get(graph_name)
        if not hasattr(relation_graph, "edges"):
            continue
        edges = list(relation_graph.edges(data=True))
        edges = sorted(
            edges,
            key=lambda item: (-float(item[2].get("weight", 1.0)), str(item[0]), str(item[1])),
        )
        if max_edges_per_relation is not None:
            edges = edges[:max_edges_per_relation]
        for edge_index, (source, target, attrs) in enumerate(edges):
            if source == target:
                continue
            weight = float(attrs.get("weight", 1.0))
            object_id = f"{dataset_name}:{graph_name}:edge:{source}:{target}"
            timestamp = float(edge_index)
            for account_id, peer_id, direction in ((source, target, "source"), (target, source, "target")):
                account_index = int(account_id)
                label = int(labels[account_index]) if 0 <= account_index < labels.shape[0] else 0
                rows.append(
                    {
                        "account_id": str(account_id),
                        "relation": relation,
                        "object_id": object_id,
                        "timestamp": timestamp,
                        "content_id": f"{object_id}:{direction}",
                        "content": f"{relation} {graph_name} edge with user {peer_id} weight {weight:.6f}",
                        "label": label,
                        "source_graph": graph_name,
                        "edge_weight": weight,
                        "target_account_id": str(peer_id),
                    }
                )
    return normalize_event_table(pd.DataFrame(rows))


def write_iohunter_event_table(
    dataset_dir: Path,
    output: Path,
    *,
    dataset_name: str | None = None,
    threshold: str = "0.7",
    train_percentage: str | None = None,
    undersampling: str | None = None,
    max_edges_per_relation: int | None = None,
) -> dict[str, object]:
    data = load_iohunter_processed_dataset(
        dataset_dir,
        threshold=threshold,
        train_percentage=train_percentage,
        undersampling=undersampling,
    )
    name = dataset_name or dataset_dir.name
    events = iohunter_processed_to_event_table(
        data,
        dataset_name=name,
        max_edges_per_relation=max_edges_per_relation,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() in {".jsonl", ".ndjson"}:
        output.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in events.to_dict(orient="records")) + "\n",
            encoding="utf-8",
        )
    else:
        events.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return {
        "dataset_dir": str(dataset_dir),
        "output": str(output),
        "dataset": name,
        "row_count": int(len(events)),
        "account_count": int(events["account_id"].nunique()),
        "relation_counts": events["relation"].value_counts().sort_index().to_dict(),
        "positive_label_count": int(events.groupby("account_id")["label"].max().sum()),
    }


def extract_labels(events: pd.DataFrame) -> dict[str, int]:
    label_column = next((column for column in LABEL_COLUMNS if column in events.columns), None)
    if label_column is None:
        return {}
    grouped = events.groupby("account_id")[label_column].max()
    return {str(account_id): int(value) for account_id, value in grouped.items()}


def _tokenize(text: str) -> list[str]:
    text = str(text).lower()
    tokens = TOKEN_RE.findall(text)
    if tokens:
        return tokens
    return [char for char in text if not char.isspace()]


def _safe_divide(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(value, 30.0), -30.0)))


def _normalize_vector(values: np.ndarray) -> np.ndarray:
    values = values.astype(float, copy=True)
    if values.size == 0:
        return values
    max_value = float(np.max(values))
    min_value = float(np.min(values))
    if max_value <= min_value:
        return np.zeros_like(values)
    return (values - min_value) / (max_value - min_value)


def _timestamp_to_float(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float, np.integer, np.floating)):
        if math.isnan(float(value)):
            return 0.0
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass
    try:
        parsed = pd.to_datetime(text, utc=True, errors="coerce")
        if pd.isna(parsed):
            return 0.0
        return float(parsed.timestamp())
    except Exception:
        return 0.0


def _clean_object_id(value: object) -> str:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _looks_like_account_id(value: str, known_accounts: set[str]) -> bool:
    if value in known_accounts:
        return True
    if value.startswith("@") and len(value) > 1:
        return True
    return False


def binary_metrics(
    y_true: Sequence[int],
    y_score: Sequence[float],
    *,
    threshold: float = 0.5,
) -> MetricResult:
    y = np.asarray(y_true, dtype=int)
    scores = np.asarray(y_score, dtype=float)
    if y.size == 0:
        return MetricResult(0.0, 0.0, 0.0, None, 0, 0)
    predictions = (scores >= threshold).astype(int)
    tp = int(np.sum((predictions == 1) & (y == 1)))
    fp = int(np.sum((predictions == 1) & (y == 0)))
    fn = int(np.sum((predictions == 0) & (y == 1)))
    precision = _safe_divide(tp, tp + fp)
    recall = _safe_divide(tp, tp + fn)
    f1 = _safe_divide(2.0 * precision * recall, precision + recall)
    auc = _roc_auc_score(y, scores)
    return MetricResult(
        precision=round(precision, 6),
        recall=round(recall, 6),
        f1=round(f1, 6),
        auc=round(auc, 6) if auc is not None else None,
        support=int(y.size),
        positive_count=int(np.sum(y == 1)),
    )


def _roc_auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    positives = y_score[y_true == 1]
    negatives = y_score[y_true == 0]
    if positives.size == 0 or negatives.size == 0:
        return None
    greater = 0.0
    for positive_score in positives:
        greater += float(np.sum(positive_score > negatives))
        greater += 0.5 * float(np.sum(positive_score == negatives))
    return greater / float(positives.size * negatives.size)


def _average_precision_score(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    y = np.asarray(y_true, dtype=int)
    scores = np.asarray(y_score, dtype=float)
    positives = int(np.sum(y == 1))
    if y.size == 0 or positives == 0:
        return None
    hits = 0
    precision_sum = 0.0
    for rank, index in enumerate(np.argsort(-scores), start=1):
        if y[index] == 1:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / positives


def _precision_recall_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int | None = None) -> tuple[float, float]:
    y = np.asarray(y_true, dtype=int)
    scores = np.asarray(y_score, dtype=float)
    if y.size == 0:
        return 0.0, 0.0
    positive_count = int(np.sum(y == 1))
    top_k = min(k or max(1, positive_count), y.size)
    order = np.argsort(-scores)[:top_k]
    true_positive = int(np.sum(y[order] == 1))
    return _safe_divide(true_positive, top_k), _safe_divide(true_positive, positive_count)


def _metric_to_dict(metric: MetricResult | None) -> dict[str, object] | None:
    if metric is None:
        return None
    return {
        "precision": metric.precision,
        "recall": metric.recall,
        "f1": metric.f1,
        "macro_f1": metric.f1,
        "auc": metric.auc,
        "support": metric.support,
        "positive_count": metric.positive_count,
    }


def _detection_metric_dict(y_true: Sequence[int], y_score: Sequence[float]) -> dict[str, object]:
    y = np.asarray(y_true, dtype=int)
    scores = np.asarray(y_score, dtype=float)
    metric = binary_metrics(y, scores)
    result = _metric_to_dict(metric) or {}
    auprc = _average_precision_score(y, scores)
    precision_at_k, recall_at_k = _precision_recall_at_k(y, scores)
    max_f1, max_f1_threshold = _max_f1(y, scores)
    predictions = (scores >= 0.5).astype(int)
    result.update(
        {
            "auprc": round(float(auprc), 6) if auprc is not None else None,
            "max_f1": round(float(max_f1), 6),
            "max_f1_threshold": round(float(max_f1_threshold), 6),
            "precision_at_k": round(precision_at_k, 6),
            "recall_at_k": round(recall_at_k, 6),
            "accuracy": round(_safe_divide(float(np.sum(predictions == y)), float(y.size)), 6),
            "primary_f1_metric": "max_f1",
            "fixed_threshold_f1_policy": "diagnostic_only",
        }
    )
    return result


def _macro_f1_at_threshold(y_true: np.ndarray, y_score: np.ndarray, threshold: float = 0.5) -> float:
    predictions = (y_score >= threshold).astype(int)
    values = []
    for label in (0, 1):
        tp = int(np.sum((predictions == label) & (y_true == label)))
        fp = int(np.sum((predictions == label) & (y_true != label)))
        fn = int(np.sum((predictions != label) & (y_true == label)))
        precision = _safe_divide(tp, tp + fp)
        recall = _safe_divide(tp, tp + fn)
        values.append(_safe_divide(2.0 * precision * recall, precision + recall))
    return float(np.mean(values)) if values else 0.0


def _max_f1(y_true: np.ndarray, y_score: np.ndarray) -> tuple[float, float]:
    if y_true.size == 0:
        return 0.0, 0.5
    order = np.argsort(-y_score)
    sorted_scores = y_score[order]
    sorted_labels = y_true[order]
    positive_total = int(np.sum(y_true == 1))
    tp = 0
    fp = 0
    best_f1 = 0.0
    best_threshold = 0.5
    for index, label in enumerate(sorted_labels):
        if int(label) == 1:
            tp += 1
        else:
            fp += 1
        next_score = sorted_scores[index + 1] if index + 1 < sorted_scores.size else None
        if next_score is not None and float(next_score) == float(sorted_scores[index]):
            continue
        fn = positive_total - tp
        precision = _safe_divide(tp, tp + fp)
        recall = _safe_divide(tp, tp + fn)
        f1 = _safe_divide(2.0 * precision * recall, precision + recall)
        if f1 > best_f1:
            best_f1 = float(f1)
            best_threshold = float(sorted_scores[index])
    default_predictions = (y_score >= 0.5).astype(int)
    default_tp = int(np.sum((default_predictions == 1) & (y_true == 1)))
    default_fp = int(np.sum((default_predictions == 1) & (y_true == 0)))
    default_fn = int(np.sum((default_predictions == 0) & (y_true == 1)))
    default_precision = _safe_divide(default_tp, default_tp + default_fp)
    default_recall = _safe_divide(default_tp, default_tp + default_fn)
    default_f1 = _safe_divide(2.0 * default_precision * default_recall, default_precision + default_recall)
    if default_f1 > best_f1:
        best_f1 = float(default_f1)
        best_threshold = 0.5
    return best_f1, best_threshold


def _amdn_hage_style_metrics(y_true: Sequence[int], y_score: Sequence[float]) -> dict[str, object]:
    y = np.asarray(y_true, dtype=int)
    scores = np.asarray(y_score, dtype=float)
    metric = binary_metrics(y, scores, threshold=0.5)
    ap = _average_precision_score(y, scores)
    max_f1, best_threshold = _max_f1(y, scores)
    return {
        "ap": round(float(ap), 6) if ap is not None else None,
        "auc": metric.auc,
        "f1_at_0_5": metric.f1,
        "precision_at_0_5": metric.precision,
        "recall_at_0_5": metric.recall,
        "max_f1": round(float(max_f1), 6),
        "max_f1_threshold": round(float(best_threshold), 6),
        "macro_f1_at_0_5": round(_macro_f1_at_threshold(y, scores, threshold=0.5), 6),
    }


def _append_metric_row(
    rows: list[dict[str, object]],
    *,
    family: str,
    method: str,
    metric: Mapping[str, object] | None,
    scope: str = "user",
    setting: str = "detect",
    notes: str = "",
) -> None:
    row: dict[str, object] = {
        "setting": setting,
        "family": family,
        "method": method,
        "scope": scope,
        "notes": notes,
    }
    for field in METRIC_FIELDS:
        row[field] = None if metric is None else metric.get(field)
    rows.append(row)


def flatten_reproduction_metrics(summary: Mapping[str, object]) -> list[dict[str, object]]:
    """Flatten nested reproduction results into a paper-table friendly format."""
    rows: list[dict[str, object]] = []
    unmasking = summary.get("unmasking")
    if isinstance(unmasking, Mapping):
        pruning = unmasking.get("node_pruning")
        if isinstance(pruning, Mapping):
            for relation, result in pruning.items():
                if isinstance(result, Mapping):
                    _append_metric_row(
                        rows,
                        family="unmasking",
                        method=f"node_pruning:{relation}",
                        metric=result.get("metrics") if isinstance(result.get("metrics"), Mapping) else None,
                    )
        embedding = unmasking.get("node_embedding_classifier")
        if isinstance(embedding, Mapping):
            _append_metric_row(
                rows,
                family="unmasking",
                method="node_embedding_classifier",
                metric=embedding.get("metrics") if isinstance(embedding.get("metrics"), Mapping) else None,
                notes=str(embedding.get("classifier_backend", "")),
            )

    llm = summary.get("leveraging_llms")
    if isinstance(llm, Mapping):
        modes = llm.get("modes")
        if isinstance(modes, Mapping):
            for mode, result in modes.items():
                if isinstance(result, Mapping):
                    _append_metric_row(
                        rows,
                        family="leveraging_llms",
                        method=str(mode),
                        metric=result.get("metrics") if isinstance(result.get("metrics"), Mapping) else None,
                        notes=str(result.get("backend", "")),
                    )

    ours = summary.get("ours")
    if isinstance(ours, Mapping):
        ours_method = str(ours.get("method", "dyna_colm_gnn_prototype"))
        variant = str(ours.get("variant", "") or "")
        if variant and ":" not in ours_method:
            ours_method = f"{ours_method}:{variant}"
        _append_metric_row(
            rows,
            family="ours",
            method=ours_method,
            metric=ours.get("metrics") if isinstance(ours.get("metrics"), Mapping) else None,
            notes=str(ours.get("classifier_backend", "")),
        )
    ablations = summary.get("ours_ablations")
    if isinstance(ablations, Mapping):
        for variant, result in ablations.items():
            if isinstance(result, Mapping):
                method = str(result.get("method", "dyna_colm_gnn_prototype"))
                if ":" not in method:
                    method = f"{method}:{variant}"
                notes = [
                    str(result.get("classifier_backend", "")),
                    f"use_lm={bool(result.get('uses_lm_features', False))}",
                    f"use_gnn={bool(result.get('uses_gnn_message_passing', False))}",
                    f"use_direction_time={bool(result.get('uses_direction_time_features', False))}",
                ]
                _append_metric_row(
                    rows,
                    family="ours",
                    method=method,
                    metric=result.get("metrics") if isinstance(result.get("metrics"), Mapping) else None,
                    notes=";".join(item for item in notes if item),
                )
    return rows


def write_metric_exports(summary: Mapping[str, object], output_dir: Path) -> dict[str, str]:
    rows = flatten_reproduction_metrics(summary)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "metrics.csv"
    json_path = output_dir / "comparison_table.json"
    fields = ("setting", "family", "method", "scope", *METRIC_FIELDS, "notes")
    with csv_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"metrics_csv": str(csv_path), "comparison_json": str(json_path)}


def build_user_entity_tfidf_vectors(
    events: pd.DataFrame,
    relation: str,
) -> dict[str, dict[str, float]]:
    relation_events = events[events["relation"] == relation]
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in relation_events.itertuples(index=False):
        account_id = str(getattr(row, "account_id"))
        object_id = str(getattr(row, "object_id"))
        if object_id and object_id.lower() != "nan":
            counts[account_id][object_id] += 1
    user_count = max(len(counts), 1)
    document_frequency: Counter[str] = Counter()
    for object_counts in counts.values():
        document_frequency.update(object_counts.keys())
    vectors: dict[str, dict[str, float]] = {}
    for account_id, object_counts in counts.items():
        total = float(sum(object_counts.values())) or 1.0
        vectors[account_id] = {}
        for object_id, count in object_counts.items():
            tf = count / total
            idf = math.log((1.0 + user_count) / (1.0 + document_frequency[object_id])) + 1.0
            vectors[account_id][object_id] = tf * idf
    return vectors


def attach_user_object_instances(
    graph: nx.Graph,
    vectors: Mapping[str, Mapping[str, float]],
    *,
    relation: str,
) -> nx.Graph:
    """Attach explicit U-O-U path instances to a projected user-user graph."""
    if graph.number_of_edges() == 0:
        return graph
    common_objects: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    inverted: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for account_id, vector in vectors.items():
        for object_id, value in vector.items():
            if value:
                inverted[str(object_id)].append((str(account_id), float(value)))
    for object_id, accounts in inverted.items():
        sorted_accounts = sorted(accounts)
        for left_index, (left, left_value) in enumerate(sorted_accounts):
            for right, right_value in sorted_accounts[left_index + 1 :]:
                key = tuple(sorted((str(left), str(right))))
                common_objects[key].append(
                    {
                        "relation": relation,
                        "object_id": object_id,
                        "left_weight": float(left_value),
                        "right_weight": float(right_value),
                        "path_weight": float(left_value * right_value),
                    }
                )
    for source, target, attrs in graph.edges(data=True):
        key = tuple(sorted((str(source), str(target))))
        instances = sorted(
            common_objects.get(key, []),
            key=lambda item: (-float(item["path_weight"]), str(item["object_id"])),
        )
        attrs["object_instances"] = instances
        attrs["objects"] = [str(item["object_id"]) for item in instances]
    return graph


def build_text_tfidf_vectors(events: pd.DataFrame) -> dict[str, dict[str, float]]:
    text_column = next((column for column in TEXT_COLUMNS if column in events.columns), None)
    if text_column is None:
        return {}
    documents: dict[str, list[str]] = defaultdict(list)
    for row in events.itertuples(index=False):
        documents[str(getattr(row, "account_id"))].extend(_tokenize(str(getattr(row, text_column))))
    user_count = max(len(documents), 1)
    document_frequency: Counter[str] = Counter()
    for tokens in documents.values():
        document_frequency.update(set(tokens))
    vectors: dict[str, dict[str, float]] = {}
    for account_id, tokens in documents.items():
        counts = Counter(tokens)
        total = float(sum(counts.values())) or 1.0
        vectors[account_id] = {}
        for token, count in counts.items():
            tf = count / total
            idf = math.log((1.0 + user_count) / (1.0 + document_frequency[token])) + 1.0
            vectors[account_id][token] = tf * idf
    return vectors


def similarity_graph_from_vectors(
    vectors: Mapping[str, Mapping[str, float]],
    *,
    relation: str,
    min_similarity: float = 0.0,
    max_edges_per_node: int | None = None,
) -> nx.Graph:
    graph = nx.Graph(relation=relation)
    for account_id in vectors:
        graph.add_node(account_id)
    norms = {
        account_id: math.sqrt(sum(value * value for value in vector.values()))
        for account_id, vector in vectors.items()
    }
    inverted: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for account_id, vector in vectors.items():
        for object_id, value in vector.items():
            if value:
                inverted[object_id].append((account_id, float(value)))
    pair_dots: Counter[tuple[str, str]] = Counter()
    for accounts in inverted.values():
        sorted_accounts = sorted(accounts)
        for left_index, (left, left_value) in enumerate(sorted_accounts):
            for right, right_value in sorted_accounts[left_index + 1 :]:
                pair_dots[tuple(sorted((left, right)))] += left_value * right_value
    by_node: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for (source, target), dot in pair_dots.items():
        similarity = _safe_divide(float(dot), norms.get(source, 0.0) * norms.get(target, 0.0))
        if similarity >= min_similarity and similarity > 0.0:
            by_node[source].append((source, target, similarity))
            by_node[target].append((source, target, similarity))
    if max_edges_per_node is None:
        selected = {(source, target, weight) for edges in by_node.values() for source, target, weight in edges}
    else:
        selected = set()
        for edges in by_node.values():
            selected.update(sorted(edges, key=lambda item: (-item[2], item[0], item[1]))[:max_edges_per_node])
    for source, target, weight in selected:
        graph.add_edge(source, target, weight=float(weight), relations={relation})
    return graph


def build_unmasking_similarity_graphs(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    include_text_similarity: bool = True,
    min_similarity: float = 0.0,
    max_edges_per_node: int | None = None,
) -> dict[str, nx.Graph]:
    graphs: dict[str, nx.Graph] = {}
    for relation in relations:
        vectors = build_user_entity_tfidf_vectors(events, relation)
        graph = similarity_graph_from_vectors(
            vectors,
            relation=relation,
            min_similarity=min_similarity,
            max_edges_per_node=max_edges_per_node,
        )
        graphs[relation] = attach_user_object_instances(graph, vectors, relation=relation)
    if include_text_similarity:
        vectors = build_text_tfidf_vectors(events)
        if vectors:
            graph = similarity_graph_from_vectors(
                vectors,
                relation="text_similarity",
                min_similarity=min_similarity,
                max_edges_per_node=max_edges_per_node,
            )
            graphs["text_similarity"] = attach_user_object_instances(graph, vectors, relation="text_similarity")
    return graphs


def fuse_similarity_graphs(graphs: Mapping[str, nx.Graph]) -> nx.Graph:
    fused = nx.Graph(relation="fused")
    for relation, graph in graphs.items():
        for node in graph.nodes:
            fused.add_node(node)
        for source, target, attrs in graph.edges(data=True):
            weight = float(attrs.get("weight", 1.0))
            if fused.has_edge(source, target):
                fused[source][target]["weight"] += weight
                fused[source][target]["relations"].add(relation)
            else:
                fused.add_edge(source, target, weight=weight, relations={relation})
    for source, target in fused.edges:
        fused[source][target]["relations"] = sorted(fused[source][target]["relations"])
    return fused


def build_dynamic_relation_graphs(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
) -> dict[str, nx.DiGraph]:
    """Build directed relation graphs while preserving temporal object evidence."""
    known_accounts = set(events["account_id"].astype(str))
    graphs: dict[str, nx.DiGraph] = {relation: nx.DiGraph(relation=relation) for relation in relations}
    for relation, relation_events in events[events["relation"].isin(relations)].groupby("relation"):
        graph = graphs.setdefault(str(relation), nx.DiGraph(relation=str(relation)))
        for account_id in relation_events["account_id"].astype(str).unique():
            graph.add_node(account_id)

        if relation in TARGET_RELATIONS and "target_account_id" in relation_events.columns:
            target_events = relation_events[relation_events["target_account_id"].astype(str).str.len() > 0]
            for row in target_events.itertuples(index=False):
                source = str(getattr(row, "account_id"))
                target = str(getattr(row, "target_account_id"))
                object_id = _clean_object_id(getattr(row, "object_id", ""))
                timestamp = _timestamp_to_float(getattr(row, "timestamp", 0))
                if not target or source == target:
                    continue
                graph.add_node(source)
                graph.add_node(target)
                _upsert_dynamic_edge(graph, source, target, relation, object_id, timestamp, delta=0.0)
            continue

        if relation in TARGET_RELATIONS:
            keep_shared_object_rows = []
            for row in relation_events.itertuples(index=False):
                source = str(getattr(row, "account_id"))
                object_id = _clean_object_id(getattr(row, "object_id", ""))
                if not _looks_like_account_id(object_id, known_accounts) or source == object_id:
                    keep_shared_object_rows.append(True)
                    continue
                keep_shared_object_rows.append(False)
                graph.add_node(source)
                graph.add_node(object_id)
                _upsert_dynamic_edge(
                    graph,
                    source,
                    object_id,
                    relation,
                    object_id,
                    _timestamp_to_float(getattr(row, "timestamp", 0)),
                    delta=0.0,
                )
            relation_events = relation_events.loc[keep_shared_object_rows] if keep_shared_object_rows else relation_events.iloc[0:0]

        for object_id, object_events in relation_events.groupby("object_id"):
            clean_object_id = _clean_object_id(object_id)
            if not clean_object_id:
                continue
            ordered = sorted(
                (
                    (
                        str(row.account_id),
                        _timestamp_to_float(getattr(row, "timestamp", 0)),
                    )
                    for row in object_events.itertuples(index=False)
                ),
                key=lambda item: (item[1], item[0]),
            )
            for index, (source, source_time) in enumerate(ordered):
                for target, target_time in ordered[index + 1 :]:
                    if source == target:
                        continue
                    delta = max(0.0, target_time - source_time)
                    time_weight = 1.0 / (1.0 + math.log1p(delta)) if delta > 0 else 1.0
                    _upsert_dynamic_edge(
                        graph,
                        source,
                        target,
                        str(relation),
                        clean_object_id,
                        target_time,
                        delta=delta,
                        weight=time_weight,
                    )
    for relation in relations:
        graphs.setdefault(relation, nx.DiGraph(relation=relation))
    return graphs


def _upsert_dynamic_edge(
    graph: nx.DiGraph,
    source: str,
    target: str,
    relation: str,
    object_id: str,
    timestamp: float,
    *,
    delta: float,
    weight: float = 1.0,
) -> None:
    if graph.has_edge(source, target):
        attrs = graph[source][target]
        attrs["weight"] = float(attrs.get("weight", 0.0)) + float(weight)
        attrs["count"] = int(attrs.get("count", 0)) + 1
        attrs["objects"].add(object_id)
        attrs["timestamps"].append(timestamp)
        attrs["time_deltas"].append(delta)
    else:
        graph.add_edge(
            source,
            target,
            weight=float(weight),
            count=1,
            relation=relation,
            objects={object_id},
            timestamps=[timestamp],
            time_deltas=[delta],
        )


def fuse_directed_graphs(graphs: Mapping[str, nx.DiGraph]) -> nx.DiGraph:
    fused = nx.DiGraph(relation="dynamic_fused")
    for relation, graph in graphs.items():
        for node in graph.nodes:
            fused.add_node(node)
        for source, target, attrs in graph.edges(data=True):
            weight = float(attrs.get("weight", 1.0))
            objects = set(attrs.get("objects", set()))
            timestamps = list(attrs.get("timestamps", []))
            deltas = list(attrs.get("time_deltas", []))
            if fused.has_edge(source, target):
                fused[source][target]["weight"] += weight
                fused[source][target]["count"] += int(attrs.get("count", 1))
                fused[source][target]["relations"].add(relation)
                fused[source][target]["objects"].update(objects)
                fused[source][target]["timestamps"].extend(timestamps)
                fused[source][target]["time_deltas"].extend(deltas)
            else:
                fused.add_edge(
                    source,
                    target,
                    weight=weight,
                    count=int(attrs.get("count", 1)),
                    relations={relation},
                    objects=objects,
                    timestamps=timestamps,
                    time_deltas=deltas,
                )
    for _, _, attrs in fused.edges(data=True):
        attrs["relations"] = sorted(attrs["relations"])
        attrs["objects"] = sorted(object_id for object_id in attrs["objects"] if object_id)
    return fused


def dynamic_graph_summary(graph: nx.DiGraph) -> dict[str, object]:
    time_deltas = [
        float(delta)
        for _, _, attrs in graph.edges(data=True)
        for delta in attrs.get("time_deltas", [])
        if float(delta) >= 0.0
    ]
    relation_counts: Counter[str] = Counter()
    object_counts: Counter[str] = Counter()
    for _, _, attrs in graph.edges(data=True):
        relation_counts.update(attrs.get("relations", [attrs.get("relation", "")]))
        object_counts.update(attrs.get("objects", []))
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "density": round(float(nx.density(graph)), 6) if graph.number_of_nodes() > 1 else 0.0,
        "relation_counts": dict(sorted(relation_counts.items())),
        "object_count": len(object_counts),
        "top_objects": [
            {"object_id": object_id, "count": count}
            for object_id, count in object_counts.most_common(10)
        ],
        "avg_time_delta": round(float(np.mean(time_deltas)), 6) if time_deltas else None,
        "median_time_delta": round(float(np.median(time_deltas)), 6) if time_deltas else None,
    }


def _detect_communities_with_metadata(
    graph: nx.Graph,
    *,
    algorithm: str = "leiden",
    seed: int = 42,
) -> CommunityDetectionResult:
    requested = algorithm.lower().strip()
    if graph.number_of_edges() == 0:
        return CommunityDetectionResult(
            communities=[{str(node)} for node in graph.nodes],
            requested_algorithm=requested,
            effective_algorithm=requested,
            backend=f"{requested}:no_edges_singletons",
        )
    if requested not in {"leiden", "louvain", "greedy"}:
        raise ValueError("community_algorithm must be one of: leiden, louvain, greedy")
    if requested == "leiden":
        leiden_result = _try_leiden_communities(graph, seed=seed)
        if leiden_result.fallback_reason is None:
            return leiden_result
        louvain_result = _try_louvain_communities(graph, requested_algorithm=requested, seed=seed)
        if louvain_result.fallback_reason is None:
            louvain_result.fallback_reason = leiden_result.fallback_reason
            return louvain_result
        greedy_result = _greedy_communities_result(
            graph,
            requested_algorithm=requested,
            fallback_reason=f"{leiden_result.fallback_reason}; {louvain_result.fallback_reason}",
        )
        return greedy_result
    if requested == "louvain":
        louvain_result = _try_louvain_communities(graph, requested_algorithm=requested, seed=seed)
        if louvain_result.fallback_reason is None:
            return louvain_result
        return _greedy_communities_result(
            graph,
            requested_algorithm=requested,
            fallback_reason=louvain_result.fallback_reason,
        )
    return _greedy_communities_result(graph, requested_algorithm=requested)


def _detect_communities(graph: nx.Graph, *, algorithm: str = "leiden", seed: int = 42) -> list[set[str]]:
    return _detect_communities_with_metadata(graph, algorithm=algorithm, seed=seed).communities


def _try_leiden_communities(graph: nx.Graph, *, seed: int = 42) -> CommunityDetectionResult:
    try:
        import igraph as ig  # type: ignore[import-not-found]
        import leidenalg  # type: ignore[import-not-found]
    except Exception as exc:
        return CommunityDetectionResult(
            communities=[],
            requested_algorithm="leiden",
            effective_algorithm="",
            backend="leidenalg",
            fallback_reason=f"leiden unavailable: {exc.__class__.__name__}",
        )
    try:
        nodes = [str(node) for node in graph.nodes]
        node_index = {node: index for index, node in enumerate(nodes)}
        edges = [(node_index[str(source)], node_index[str(target)]) for source, target in graph.edges]
        weights = [float(attrs.get("weight", 1.0)) for _, _, attrs in graph.edges(data=True)]
        igraph_graph = ig.Graph(n=len(nodes), edges=edges, directed=False)
        partition = leidenalg.find_partition(
            igraph_graph,
            leidenalg.RBConfigurationVertexPartition,
            weights=weights if weights else None,
            seed=int(seed),
        )
        communities = [
            {nodes[int(index)] for index in community}
            for community in partition
            if len(community) > 0
        ]
        return CommunityDetectionResult(
            communities=communities,
            requested_algorithm="leiden",
            effective_algorithm="leiden",
            backend="leidenalg.RBConfigurationVertexPartition",
        )
    except Exception as exc:
        return CommunityDetectionResult(
            communities=[],
            requested_algorithm="leiden",
            effective_algorithm="",
            backend="leidenalg",
            fallback_reason=f"leiden failed: {exc.__class__.__name__}: {exc}",
        )


def _try_louvain_communities(
    graph: nx.Graph,
    *,
    requested_algorithm: str,
    seed: int = 42,
) -> CommunityDetectionResult:
    try:
        communities = [
            set(map(str, community))
            for community in louvain_communities(graph, weight="weight", seed=seed)
        ]
        return CommunityDetectionResult(
            communities=communities,
            requested_algorithm=requested_algorithm,
            effective_algorithm="louvain",
            backend="networkx.louvain_communities",
        )
    except Exception as exc:
        return CommunityDetectionResult(
            communities=[],
            requested_algorithm=requested_algorithm,
            effective_algorithm="",
            backend="networkx.louvain_communities",
            fallback_reason=f"louvain failed: {exc.__class__.__name__}: {exc}",
        )


def _greedy_communities_result(
    graph: nx.Graph,
    *,
    requested_algorithm: str,
    fallback_reason: str | None = None,
) -> CommunityDetectionResult:
    communities = [
        set(map(str, community))
        for community in greedy_modularity_communities(graph, weight="weight")
    ]
    return CommunityDetectionResult(
        communities=communities,
        requested_algorithm=requested_algorithm,
        effective_algorithm="greedy",
        backend="networkx.greedy_modularity_communities",
        fallback_reason=fallback_reason,
    )


def graph_summary(
    graph: nx.Graph,
    labels: Mapping[str, int] | None = None,
    *,
    community_algorithm: str = "leiden",
    seed: int = 42,
    communities: Sequence[set[str]] | None = None,
    community_algorithm_effective: str | None = None,
    community_algorithm_backend: str | None = None,
    community_algorithm_fallback_reason: str | None = None,
) -> dict[str, object]:
    partition = [set(map(str, community)) for community in communities] if communities is not None else []
    modularity_score = None
    conductance_score = None
    community_result = CommunityDetectionResult(
        communities=[],
        requested_algorithm=community_algorithm,
        effective_algorithm=community_algorithm,
        backend=f"{community_algorithm}:not_run",
    )
    if communities is not None:
        community_result = CommunityDetectionResult(
            communities=partition,
            requested_algorithm=community_algorithm,
            effective_algorithm=community_algorithm_effective or community_algorithm,
            backend=community_algorithm_backend or "provided_partition",
            fallback_reason=community_algorithm_fallback_reason,
        )
    elif graph.number_of_edges() > 0:
        community_result = _detect_communities_with_metadata(graph, algorithm=community_algorithm, seed=seed)
        partition = community_result.communities
    if partition:
        modularity_score = float(modularity(graph, partition, weight="weight")) if graph.number_of_edges() > 0 else None
        conductance_values = []
        for community in sorted(partition, key=len, reverse=True)[:100]:
            if community and len(community) < graph.number_of_nodes():
                try:
                    conductance_values.append(nx.algorithms.cuts.conductance(graph, community, weight="weight"))
                except Exception:
                    continue
        conductance_score = float(np.mean(conductance_values)) if conductance_values else None
    label_values = list(labels.values()) if labels else []
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "density": round(float(nx.density(graph)), 6) if graph.number_of_nodes() > 1 else 0.0,
        "component_count": nx.number_connected_components(graph) if graph.number_of_nodes() else 0,
        "cluster_count": len(partition),
        "largest_cluster_size": max((len(community) for community in partition), default=0),
        "modularity": round(modularity_score, 6) if modularity_score is not None else None,
        "conductance": round(conductance_score, 6) if conductance_score is not None else None,
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": community_result.effective_algorithm,
        "community_algorithm_backend": community_result.backend,
        "community_algorithm_fallback_reason": community_result.fallback_reason,
        "positive_label_count": int(sum(label_values)) if label_values else None,
    }


def _centrality_scores(graph: nx.Graph, metric: str) -> dict[str, float]:
    if graph.number_of_nodes() == 0:
        return {}
    if metric == "degree":
        return {node: float(graph.degree(node, weight="weight")) for node in graph.nodes}
    if metric == "pagerank":
        try:
            return nx.pagerank(graph, weight="weight")
        except Exception:
            return _pagerank_fallback(graph)
    if metric == "eigenvector":
        try:
            return nx.eigenvector_centrality_numpy(graph, weight="weight")
        except Exception:
            return {node: float(graph.degree(node, weight="weight")) for node in graph.nodes}
    raise ValueError(f"Unsupported centrality metric: {metric}")


def _pagerank_fallback(
    graph: nx.Graph,
    *,
    alpha: float = 0.85,
    max_iter: int = 100,
    tol: float = 1e-9,
) -> dict[str, float]:
    nodes = list(graph.nodes)
    if not nodes:
        return {}
    index = {node: offset for offset, node in enumerate(nodes)}
    n = len(nodes)
    scores = np.full(n, 1.0 / n, dtype=float)
    adjacency = np.zeros((n, n), dtype=float)
    for source, target, attrs in graph.edges(data=True):
        weight = float(attrs.get("weight", 1.0))
        adjacency[index[source], index[target]] += weight
        adjacency[index[target], index[source]] += weight
    row_sum = adjacency.sum(axis=1, keepdims=True)
    dangling = row_sum[:, 0] <= 0.0
    row_sum[row_sum <= 0.0] = 1.0
    transition = adjacency / row_sum
    teleport = np.full(n, (1.0 - alpha) / n, dtype=float)
    for _ in range(max_iter):
        dangling_mass = float(np.sum(scores[dangling])) / n
        updated = teleport + alpha * (transition.T @ scores + dangling_mass)
        if float(np.sum(np.abs(updated - scores))) < tol:
            scores = updated
            break
        scores = updated
    total = float(np.sum(scores)) or 1.0
    return {node: float(scores[index[node]] / total) for node in nodes}


def node_pruning_baseline(
    graph: nx.Graph,
    labels: Mapping[str, int] | None = None,
    *,
    metric: str = "eigenvector",
    percentile: float = 90.0,
) -> dict[str, object]:
    scores = _centrality_scores(graph, metric)
    if not scores:
        return {"metric": metric, "selected_nodes": [], "threshold": None, "metrics": None}
    threshold = float(np.percentile(list(scores.values()), percentile))
    selected_nodes = sorted(node for node, value in scores.items() if value >= threshold)
    metrics = None
    if labels:
        ordered_nodes = sorted(scores)
        y_true = [int(labels.get(node, 0)) for node in ordered_nodes]
        y_score = [float(scores[node]) for node in ordered_nodes]
        metrics = binary_metrics(y_true, y_score, threshold=threshold)
    return {
        "metric": metric,
        "percentile": percentile,
        "threshold": threshold,
        "selected_nodes": selected_nodes,
        "metrics": _metric_to_dict(metrics),
    }


def _unweighted_graph_copy(graph: nx.Graph) -> nx.Graph:
    copied = nx.Graph()
    copied.add_nodes_from(graph.nodes)
    copied.add_edges_from((source, target, {"weight": 1.0}) for source, target in graph.edges())
    return copied


def _apply_discover_structure_filter(
    graph: nx.Graph,
    *,
    mode: str,
    metric: str,
    percentile: float,
    use_weights: bool,
    min_selected_nodes: int = 2,
) -> tuple[nx.Graph, dict[str, object], set[str], dict[str, float]]:
    # Historical helper kept for compatibility with old experiment manifests.
    # CoordinationDiscover Discover now runs on the stable full-graph encoder
    # and does not perform Unmasking-style structural screening first.
    original_node_count = int(graph.number_of_nodes())
    original_edge_count = int(graph.number_of_edges())
    if mode == "none" or original_node_count == 0:
        all_nodes = set(map(str, graph.nodes))
        default_scores = {str(node): 1.0 for node in graph.nodes}
        return (
            graph,
            {
                "mode": "none",
                "metric": metric,
                "percentile": float(percentile),
                "use_weights": bool(use_weights),
                "effective": False,
                "threshold": None,
                "selected_node_count": original_node_count,
                "removed_node_count": 0,
                "selected_node_fraction": 1.0 if original_node_count else 0.0,
                "removed_node_fraction": 0.0,
                "graph_node_count_before": original_node_count,
                "graph_edge_count_before": original_edge_count,
                "graph_node_count_after": original_node_count,
                "graph_edge_count_after": original_edge_count,
                "selected_nodes_preview": sorted(all_nodes)[:20],
                "selection_graph": "fused_similarity_network",
                "fallback_reason": None,
            },
            all_nodes,
            default_scores,
        )
    if mode != "node_pruning":
        raise ValueError(f"Unsupported Discover structure filter: {mode}")
    centrality_graph = graph if use_weights else _unweighted_graph_copy(graph)
    scores = _centrality_scores(centrality_graph, metric)
    if not scores:
        return (
            graph,
            {
                "mode": mode,
                "metric": metric,
                "percentile": float(percentile),
                "use_weights": bool(use_weights),
                "effective": False,
                "threshold": None,
                "selected_node_count": original_node_count,
                "removed_node_count": 0,
                "selected_node_fraction": 1.0 if original_node_count else 0.0,
                "removed_node_fraction": 0.0,
                "graph_node_count_before": original_node_count,
                "graph_edge_count_before": original_edge_count,
                "graph_node_count_after": original_node_count,
                "graph_edge_count_after": original_edge_count,
                "selected_nodes_preview": sorted(map(str, graph.nodes))[:20],
                "selection_graph": "weighted_fused_similarity_network" if use_weights else "unweighted_fused_similarity_network",
                "fallback_reason": "empty_centrality_scores",
            },
            set(map(str, graph.nodes)),
            {str(node): 1.0 for node in graph.nodes},
        )
    threshold = float(np.percentile(list(scores.values()), percentile))
    selected_nodes = sorted(str(node) for node, value in scores.items() if float(value) >= threshold)
    if 0 < len(selected_nodes) < min_selected_nodes and len(scores) >= min_selected_nodes:
        selected_nodes = [
            str(node)
            for node, _ in sorted(scores.items(), key=lambda item: (-float(item[1]), str(item[0])))[:min_selected_nodes]
        ]
    selected_node_set = set(selected_nodes)
    filtered_graph = graph.subgraph(selected_nodes).copy()
    normalized_scores = _normalize_vector(np.asarray([float(scores[str(node)]) for node in scores], dtype=float))
    normalized_score_map = {
        str(node): float(normalized_scores[index])
        for index, node in enumerate(scores)
    }
    selected_node_count = int(filtered_graph.number_of_nodes())
    removed_node_count = max(0, original_node_count - selected_node_count)
    return (
        filtered_graph,
        {
            "mode": mode,
            "metric": metric,
            "percentile": float(percentile),
            "use_weights": bool(use_weights),
            "effective": selected_node_count < original_node_count,
            "threshold": round(threshold, 6),
            "selected_node_count": selected_node_count,
            "removed_node_count": removed_node_count,
            "selected_node_fraction": round(_safe_divide(selected_node_count, original_node_count), 6),
            "removed_node_fraction": round(_safe_divide(removed_node_count, original_node_count), 6),
            "graph_node_count_before": original_node_count,
            "graph_edge_count_before": original_edge_count,
            "graph_node_count_after": selected_node_count,
            "graph_edge_count_after": int(filtered_graph.number_of_edges()),
            "selected_nodes_preview": selected_nodes[:20],
            "selection_graph": "weighted_fused_similarity_network" if use_weights else "unweighted_fused_similarity_network",
            "fallback_reason": None,
        },
        selected_node_set,
        normalized_score_map,
    )


def _expand_core_communities(
    graph: nx.Graph,
    *,
    core_communities: Sequence[set[str]],
    core_nodes: set[str],
    nodes: Sequence[str],
) -> tuple[list[set[str]], dict[str, int], dict[str, object]]:
    expanded = [set(map(str, community)) for community in core_communities if community]
    cluster_by_node: dict[str, int] = {}
    for cluster_id, community in enumerate(expanded):
        for node in community:
            cluster_by_node[str(node)] = cluster_id

    expanded_count = 0
    singleton_count = 0
    attachment_scores: list[float] = []
    for node in nodes:
        node = str(node)
        if node in cluster_by_node:
            continue
        best_cluster = None
        best_score = 0.0
        if node in graph:
            for cluster_id, community in enumerate(expanded):
                attachment = 0.0
                for neighbor, attrs in graph[node].items():
                    if str(neighbor) in community:
                        attachment += float(attrs.get("weight", 1.0))
                if attachment > best_score:
                    best_score = attachment
                    best_cluster = cluster_id
        if best_cluster is not None and best_score > 0.0:
            expanded[best_cluster].add(node)
            cluster_by_node[node] = best_cluster
            expanded_count += 1
            attachment_scores.append(best_score)
            continue
        cluster_id = len(expanded)
        expanded.append({node})
        cluster_by_node[node] = cluster_id
        singleton_count += 1

    return expanded, cluster_by_node, {
        "assignment_mode": "core_then_expand",
        "core_node_count": len(core_nodes),
        "expanded_node_count": expanded_count,
        "singleton_remainder_count": singleton_count,
        "mean_attachment_weight": round(float(np.mean(attachment_scores)), 6) if attachment_scores else 0.0,
        "max_attachment_weight": round(float(np.max(attachment_scores)), 6) if attachment_scores else 0.0,
    }


def _spectral_embedding(graph: nx.Graph, nodes: Sequence[str], dim: int = 16) -> np.ndarray:
    if not nodes:
        return np.zeros((0, dim), dtype=float)
    graph_for_embedding = graph.copy()
    graph_for_embedding.add_nodes_from(nodes)
    adjacency = nx.to_numpy_array(graph_for_embedding, nodelist=list(nodes), weight="weight", dtype=float)
    if not np.any(adjacency):
        return np.zeros((len(nodes), dim), dtype=float)
    values, vectors = np.linalg.eigh(adjacency)
    order = np.argsort(np.abs(values))[::-1][:dim]
    selected_values = np.sqrt(np.abs(values[order]))
    embedding = vectors[:, order] * selected_values
    if embedding.shape[1] < dim:
        embedding = np.pad(embedding, ((0, 0), (0, dim - embedding.shape[1])))
    return embedding.astype(float)


def _structural_embedding(graph: nx.Graph, nodes: Sequence[str], dim: int = 16) -> np.ndarray:
    graph_for_embedding = graph.copy()
    graph_for_embedding.add_nodes_from(nodes)
    degree = _centrality_scores(graph_for_embedding, "degree")
    pagerank = _centrality_scores(graph_for_embedding, "pagerank")
    weighted_degree = {
        node: float(graph_for_embedding.degree(node, weight="weight"))
        for node in nodes
    }
    matrix = np.asarray(
        [
            [
                degree.get(node, 0.0),
                pagerank.get(node, 0.0),
                weighted_degree.get(node, 0.0),
                float(graph_for_embedding.degree(node)),
            ]
            for node in nodes
        ],
        dtype=float,
    )
    for column in range(matrix.shape[1]):
        matrix[:, column] = _normalize_vector(matrix[:, column])
    if dim <= matrix.shape[1]:
        return matrix[:, :dim]
    return np.pad(matrix, ((0, 0), (0, dim - matrix.shape[1])))


def _make_split(y: np.ndarray, *, seed: int = 42, train_ratio: float = 0.7) -> Split:
    rng = np.random.default_rng(seed)
    train_indices: list[int] = []
    test_indices: list[int] = []
    for label in sorted(set(y.tolist())):
        indices = np.where(y == label)[0]
        rng.shuffle(indices)
        cut = max(1, int(round(len(indices) * train_ratio))) if len(indices) > 1 else len(indices)
        train_indices.extend(indices[:cut].tolist())
        test_indices.extend(indices[cut:].tolist())
    if not test_indices and len(y) > 1:
        test_indices.append(train_indices.pop())
    return Split(train=np.asarray(sorted(train_indices)), test=np.asarray(sorted(test_indices)))


def _split_for_detect(
    events: pd.DataFrame,
    nodes: Sequence[str],
    y: np.ndarray,
    *,
    split_mode: str = "supervised",
    seed: int = 42,
) -> tuple[Split, str]:
    mode = split_mode.lower().strip()
    if mode == "scarce_supervised":
        return _make_split(y, seed=seed, train_ratio=0.2), "scarce_supervised"
    if mode != "cross_io":
        return _make_split(y, seed=seed), "supervised"

    group_column = next(
        (column for column in ("campaign", "dataset", "source_graph", "operation", "country") if column in events.columns),
        None,
    )
    if group_column is None:
        return _make_split(y, seed=seed), "cross_io_fallback_supervised_no_group"
    node_group = (
        events.groupby("account_id")[group_column]
        .agg(lambda values: str(values.iloc[0]))
        .to_dict()
    )
    groups = sorted({str(node_group.get(node, "")) for node in nodes if str(node_group.get(node, ""))})
    if len(groups) < 2:
        return _make_split(y, seed=seed), "cross_io_fallback_supervised_single_group"
    rng = np.random.default_rng(seed)
    test_group = groups[int(rng.integers(0, len(groups)))]
    test_indices = np.asarray([index for index, node in enumerate(nodes) if str(node_group.get(node, "")) == test_group], dtype=int)
    train_indices = np.asarray([index for index, node in enumerate(nodes) if str(node_group.get(node, "")) != test_group], dtype=int)
    if train_indices.size == 0 or test_indices.size == 0 or len(set(y[train_indices].tolist())) < 2:
        return _make_split(y, seed=seed), "cross_io_fallback_supervised_unusable_group"
    return Split(train=np.asarray(sorted(train_indices)), test=np.asarray(sorted(test_indices))), f"cross_io:{group_column}:{test_group}"


def _standardize_train_test(x_train: np.ndarray, x_test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.mean(x_train, axis=0, keepdims=True)
    std = np.std(x_train, axis=0, keepdims=True)
    std[std <= 1e-9] = 1.0
    return (x_train - mean) / std, (x_test - mean) / std


def _fit_numpy_logistic(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    *,
    epochs: int = 300,
    learning_rate: float = 0.1,
    l2: float = 1e-3,
) -> np.ndarray:
    x_train, x_test = _standardize_train_test(x_train, x_test)
    weights = np.zeros(x_train.shape[1], dtype=float)
    bias = 0.0
    positives = max(float(np.sum(y_train == 1)), 1.0)
    negatives = max(float(np.sum(y_train == 0)), 1.0)
    class_weights = np.where(y_train == 1, len(y_train) / (2.0 * positives), len(y_train) / (2.0 * negatives))
    for _ in range(epochs):
        logits = x_train @ weights + bias
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
        error = (probs - y_train) * class_weights
        grad_w = (x_train.T @ error) / len(y_train) + l2 * weights
        grad_b = float(np.mean(error))
        weights -= learning_rate * grad_w
        bias -= learning_rate * grad_b
    return 1.0 / (1.0 + np.exp(-np.clip(x_test @ weights + bias, -30.0, 30.0)))


def _fit_classifier_scores(
    x: np.ndarray,
    y: np.ndarray,
    *,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, str]:
    split = _make_split(y, seed=seed)
    if split.test.size == 0:
        return np.asarray([], dtype=int), np.asarray([], dtype=float), "not_enough_test_data"
    x_train = x[split.train]
    x_test = x[split.test]
    y_train = y[split.train]
    try:
        from sklearn.ensemble import RandomForestClassifier

        classifier = RandomForestClassifier(n_estimators=200, random_state=seed, class_weight="balanced")
        classifier.fit(x_train, y_train)
        scores = classifier.predict_proba(x_test)[:, 1]
        backend = "sklearn_random_forest"
    except Exception:
        scores = _fit_numpy_logistic(x_train, y_train, x_test)
        backend = "numpy_logistic"
    return split.test, scores, backend


def node_embedding_classifier_baseline(
    graph: nx.Graph,
    labels: Mapping[str, int],
    *,
    dim: int = 128,
    spectral_node_limit: int = 1000,
    seed: int = 42,
) -> dict[str, object]:
    nodes = sorted(labels)
    if not nodes or len(set(labels.values())) < 2:
        return {"embedding_backend": "spectral", "classifier_backend": "not_applicable", "metrics": None}
    embedding_dim = min(dim, max(1, len(nodes)))
    if len(nodes) > spectral_node_limit:
        embedding = _structural_embedding(graph, nodes, dim=embedding_dim)
        embedding_backend = "structural_fallback"
    else:
        embedding = _spectral_embedding(graph, nodes, dim=embedding_dim)
        embedding_backend = "spectral_fallback"
    y = np.asarray([int(labels[node]) for node in nodes], dtype=int)
    test_indices, scores, classifier_backend = _fit_classifier_scores(embedding, y, seed=seed)
    metrics = binary_metrics(y[test_indices], scores) if test_indices.size else None
    return {
        "embedding_backend": embedding_backend,
        "classifier_backend": classifier_backend,
        "metrics": _metric_to_dict(metrics),
        "test_nodes": [nodes[int(index)] for index in test_indices.tolist()],
    }


def run_unmasking_reproduction(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    include_text_similarity: bool = True,
    min_similarity: float = 0.0,
    max_edges_per_node: int | None = None,
    node_pruning_percentile: float = 90.0,
    embedding_dim: int = 128,
    seed: int = 42,
) -> dict[str, object]:
    labels = extract_labels(events)
    graphs = build_unmasking_similarity_graphs(
        events,
        relations=relations,
        include_text_similarity=include_text_similarity,
        min_similarity=min_similarity,
        max_edges_per_node=max_edges_per_node,
    )
    fused = fuse_similarity_graphs(graphs)
    graph_summaries = {relation: graph_summary(graph, labels) for relation, graph in graphs.items()}
    graph_summaries["fused"] = graph_summary(fused, labels)
    pruning = {
        relation: node_pruning_baseline(graph, labels, percentile=node_pruning_percentile)
        for relation, graph in {**graphs, "fused": fused}.items()
    }
    embedding_classifier = node_embedding_classifier_baseline(fused, labels, dim=embedding_dim, seed=seed) if labels else None
    return {
        "method": "unmasking_reproduction",
        "relations": list(relations),
        "include_text_similarity": include_text_similarity,
        "graph_summaries": graph_summaries,
        "node_pruning": pruning,
        "node_embedding_classifier": embedding_classifier,
    }


def _user_content(events: pd.DataFrame) -> dict[str, str]:
    text_column = next((column for column in TEXT_COLUMNS if column in events.columns), None)
    documents: dict[str, list[str]] = defaultdict(list)
    if text_column is None:
        return {}
    for row in events.itertuples(index=False):
        documents[str(getattr(row, "account_id"))].append(str(getattr(row, text_column)))
    return {account_id: " ".join(parts) for account_id, parts in documents.items()}


def _account_display_name_map(events: pd.DataFrame) -> dict[str, str]:
    display_names: dict[str, str] = {}
    candidate_columns = ("nickname", "screen_name", "author_name", "user_name")
    available_columns = [column for column in candidate_columns if column in events.columns]
    if not available_columns:
        return display_names
    for row in events.itertuples(index=False):
        account_id = str(getattr(row, "account_id", "")).strip()
        if not account_id or account_id in display_names:
            continue
        for column in available_columns:
            value = str(getattr(row, column, "") or "").strip()
            if value:
                display_names[account_id] = value
                break
    return display_names


def _metadata_text(events: pd.DataFrame) -> dict[str, str]:
    metadata: dict[str, list[str]] = defaultdict(list)
    for row in events.itertuples(index=False):
        relation = str(getattr(row, "relation"))
        object_id = str(getattr(row, "object_id"))
        account_id = str(getattr(row, "account_id"))
        metadata[account_id].append(f"{relation}:{object_id}")
    return {account_id: " ".join(items) for account_id, items in metadata.items()}


def _interaction_text(graph: nx.Graph) -> dict[str, str]:
    output: dict[str, str] = {}
    for node in graph.nodes:
        neighbors = sorted(graph.neighbors(node), key=lambda item: (-float(graph[node][item].get("weight", 1.0)), item))
        output[str(node)] = " ".join(f"connected:{neighbor}" for neighbor in neighbors[:25])
    return output


def _bag_feature_matrix(text_by_user: Mapping[str, str], nodes: Sequence[str], max_features: int = 128) -> np.ndarray:
    document_tokens = {node: _tokenize(text_by_user.get(node, "")) for node in nodes}
    document_frequency: Counter[str] = Counter()
    for tokens in document_tokens.values():
        document_frequency.update(set(tokens))
    vocabulary = [
        token
        for token, _ in sorted(document_frequency.items(), key=lambda item: (-item[1], item[0]))[:max_features]
    ]
    index = {token: offset for offset, token in enumerate(vocabulary)}
    matrix = np.zeros((len(nodes), len(vocabulary)), dtype=float)
    node_count = max(len(nodes), 1)
    for row_index, node in enumerate(nodes):
        counts = Counter(document_tokens[node])
        total = float(sum(counts.values())) or 1.0
        for token, count in counts.items():
            if token not in index:
                continue
            idf = math.log((1.0 + node_count) / (1.0 + document_frequency[token])) + 1.0
            matrix[row_index, index[token]] = (count / total) * idf
    return matrix


def _reduce_feature_dim(matrix: np.ndarray, max_dim: int) -> np.ndarray:
    if matrix.size == 0 or matrix.shape[1] <= max_dim:
        return matrix
    try:
        _, _, vt = np.linalg.svd(matrix, full_matrices=False)
        return matrix @ vt[:max_dim].T
    except Exception:
        return matrix[:, :max_dim]


def _lm_feature_matrix(
    events: pd.DataFrame,
    nodes: Sequence[str],
    *,
    backend: str = "sbert",
    max_dim: int = 32,
    cache_dir: Path | None = None,
) -> tuple[np.ndarray, str]:
    content = _user_content(events)
    metadata = _metadata_text(events)
    texts = [
        " ".join(part for part in (content.get(node, ""), metadata.get(node, "")) if part).strip()
        for node in nodes
    ]
    requested = backend.lower().strip()
    cache_key = (
        requested,
        int(max_dim),
        len(nodes),
        hash(tuple(texts)),
        tuple(str(node) for node in nodes[:10]),
    )
    disk_cache_path: Path | None = None
    if cache_dir is not None:
        try:
            import hashlib

            digest = hashlib.sha1(
                json.dumps(
                    {
                        "backend": requested,
                        "max_dim": int(max_dim),
                        "nodes": [str(node) for node in nodes],
                        "texts": texts,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()[:20]
            disk_cache_path = Path(cache_dir) / f"lm_features_{requested}_{max_dim}_{digest}.npz"
            if disk_cache_path.exists():
                cached_npz = np.load(disk_cache_path, allow_pickle=False)
                return np.asarray(cached_npz["features"], dtype=float), str(cached_npz["source"].item())
        except Exception:
            disk_cache_path = None
    cached = _LM_FEATURE_CACHE.get(cache_key)
    if cached is not None:
        matrix, source = cached
        return matrix.copy(), source
    if requested == "sbert":
        try:
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            embeddings = model.encode(
                texts,
                batch_size=128,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            matrix = _reduce_feature_dim(np.asarray(embeddings, dtype=float), max_dim)
            source = "sbert:sentence-transformers/all-MiniLM-L6-v2"
            _LM_FEATURE_CACHE[cache_key] = (matrix.copy(), source)
            if disk_cache_path is not None:
                disk_cache_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(disk_cache_path, features=matrix, source=np.asarray(source))
            return matrix, source
        except Exception:
            pass
    content_features = _bag_feature_matrix(content, nodes, max_features=max_dim)
    metadata_features = _bag_feature_matrix(metadata, nodes, max_features=max_dim)
    features = np.concatenate([content_features, metadata_features], axis=1)
    if features.shape[1] == 0:
        features = np.zeros((len(nodes), 1), dtype=float)
    matrix = _reduce_feature_dim(features, max_dim)
    source = "tfidf_object_bag_fallback"
    _LM_FEATURE_CACHE[cache_key] = (matrix.copy(), source)
    if disk_cache_path is not None:
        disk_cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(disk_cache_path, features=matrix, source=np.asarray(source))
    return matrix, source


def _centrality_feature_matrix(graph: nx.Graph, nodes: Sequence[str]) -> np.ndarray:
    degree = _centrality_scores(graph, "degree")
    pagerank = _centrality_scores(graph, "pagerank")
    eigenvector = _centrality_scores(graph, "eigenvector")
    matrix = np.asarray(
        [
            [
                float(degree.get(node, 0.0)),
                float(pagerank.get(node, 0.0)),
                float(eigenvector.get(node, 0.0)),
            ]
            for node in nodes
        ],
        dtype=float,
    )
    for column in range(matrix.shape[1]):
        matrix[:, column] = _normalize_vector(matrix[:, column])
    return matrix


def _directed_feature_matrix(graph: nx.DiGraph, nodes: Sequence[str]) -> np.ndarray:
    matrix = np.asarray(
        [
            [
                float(graph.out_degree(node, weight="weight")),
                float(graph.in_degree(node, weight="weight")),
                float(graph.out_degree(node)),
                float(graph.in_degree(node)),
            ]
            for node in nodes
        ],
        dtype=float,
    )
    for column in range(matrix.shape[1]):
        matrix[:, column] = _normalize_vector(matrix[:, column])
    return matrix


def _community_evidence(
    events: pd.DataFrame,
    community: set[str],
    *,
    top_k: int = 10,
) -> dict[str, object]:
    community_events = events[events["account_id"].astype(str).isin(community)]
    object_counts: Counter[tuple[str, str]] = Counter()
    relation_counts: Counter[str] = Counter()
    for row in community_events.itertuples(index=False):
        object_id = _clean_object_id(getattr(row, "object_id", ""))
        relation = str(getattr(row, "relation", ""))
        if object_id:
            object_counts[(relation, object_id)] += 1
        if relation:
            relation_counts[relation] += 1
    total_objects = sum(object_counts.values())
    top_objects = [
        {
            "relation": relation,
            "object_id": object_id,
            "count": count,
            "share": round(_safe_divide(count, total_objects), 6),
        }
        for (relation, object_id), count in object_counts.most_common(top_k)
    ]
    return {
        "top_objects": top_objects,
        "object_concentration": top_objects[0]["share"] if top_objects else 0.0,
        "relation_breakdown": dict(relation_counts.most_common()),
    }


def generate_llm_prompt_records(
    events: pd.DataFrame,
    graph: nx.Graph,
    *,
    mode: str,
    labels: Mapping[str, int] | None = None,
) -> list[dict[str, object]]:
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, graph.nodes))))
    centrality = _centrality_feature_matrix(graph, nodes)
    metadata = _metadata_text(events)
    content = _user_content(events)
    interaction = _interaction_text(graph)
    records: list[dict[str, object]] = []
    for index, node in enumerate(nodes):
        if mode == "centrality":
            input_text = (
                f"User {node} has degree centrality {centrality[index, 0]:.4f}, "
                f"PageRank {centrality[index, 1]:.4f}, and eigenvector centrality {centrality[index, 2]:.4f}."
            )
        elif mode == "metadata":
            input_text = f"User {node} has metadata: {metadata.get(node, '')}"
        elif mode == "content":
            input_text = f"User {node} shared content: {content.get(node, '')[:2000]}"
        elif mode == "interaction":
            input_text = f"User {node} is {interaction.get(node, '')}"
        elif mode == "multi_input":
            input_text = (
                f"{interaction.get(node, '')} {metadata.get(node, '')} "
                f"centrality={centrality[index].round(4).tolist()} content={content.get(node, '')[:1000]}"
            )
        else:
            raise ValueError(f"Unsupported LLM baseline mode: {mode}")
        record = {
            "account_id": node,
            "instruction": "Determine if the user is actively driving an influence campaign.",
            "input": input_text.strip(),
        }
        if labels:
            record["output"] = bool(labels.get(node, 0))
        records.append(record)
    return records


def _write_jsonl(path: Path, records: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_handle:
        for record in records:
            file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_lightweight_llm_baselines(
    events: pd.DataFrame,
    graph: nx.Graph,
    *,
    output_dir: Path | None = None,
    seed: int = 42,
) -> dict[str, object]:
    labels = extract_labels(events)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, graph.nodes))))
    if not labels or len(set(labels.values())) < 2:
        return {"method": "lightweight_llm_baselines", "modes": {}, "prompt_files": {}}
    y = np.asarray([int(labels.get(node, 0)) for node in nodes], dtype=int)
    feature_sources = {
        "interaction": _bag_feature_matrix(_interaction_text(graph), nodes),
        "centrality": _centrality_feature_matrix(graph, nodes),
        "metadata": _bag_feature_matrix(_metadata_text(events), nodes),
        "content": _bag_feature_matrix(_user_content(events), nodes),
    }
    feature_sources["multi_input"] = np.concatenate(
        [feature_sources[name] for name in ("interaction", "centrality", "metadata", "content")],
        axis=1,
    )
    results: dict[str, object] = {}
    prompt_files: dict[str, str] = {}
    for mode, matrix in feature_sources.items():
        test_indices, scores, backend = _fit_classifier_scores(matrix, y, seed=seed)
        metrics = binary_metrics(y[test_indices], scores) if test_indices.size else None
        results[mode] = {
            "backend": backend,
            "metrics": _metric_to_dict(metrics),
            "test_nodes": [nodes[int(index)] for index in test_indices.tolist()],
        }
        if output_dir is not None:
            records = generate_llm_prompt_records(events, graph, mode=mode, labels=labels)
            prompt_path = output_dir / "leveraging_llms" / f"{mode}_prompts.jsonl"
            _write_jsonl(prompt_path, records)
            prompt_files[mode] = str(prompt_path)
    return {"method": "lightweight_llm_baselines", "modes": results, "prompt_files": prompt_files}


def _relation_degree_features(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
) -> tuple[np.ndarray, dict[str, float]]:
    matrix = np.zeros((len(nodes), len(graphs)), dtype=float)
    relation_scores: dict[str, float] = {}
    for column, (relation, graph) in enumerate(graphs.items()):
        values = np.asarray([float(graph.degree(node, weight="weight")) for node in nodes], dtype=float)
        matrix[:, column] = _normalize_vector(values)
        relation_scores[relation] = float(np.mean(values) + graph.number_of_edges())
    return matrix, relation_scores


def _relation_attention(
    relation_scores: Mapping[str, float],
    relation_degrees: np.ndarray,
    labels: Mapping[str, int],
    nodes: Sequence[str],
) -> dict[str, float]:
    scores = np.asarray(list(relation_scores.values()), dtype=float)
    if labels and len(set(labels.values())) >= 2 and relation_degrees.size:
        y = np.asarray([int(labels.get(node, 0)) for node in nodes], dtype=float)
        for column in range(relation_degrees.shape[1]):
            x = relation_degrees[:, column]
            if np.std(x) > 1e-9 and np.std(y) > 1e-9:
                scores[column] += abs(float(np.corrcoef(x, y)[0, 1]))
    if scores.size == 0:
        return {}
    scores = scores - np.max(scores)
    exp_values = np.exp(scores)
    total = float(np.sum(exp_values)) or 1.0
    return {
        relation: float(exp_values[index] / total)
        for index, relation in enumerate(relation_scores)
    }


def _message_pass(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    features: np.ndarray,
    attention: Mapping[str, float],
) -> np.ndarray:
    if features.size == 0:
        return features
    aggregate = np.zeros_like(features)
    node_index = {node: index for index, node in enumerate(nodes)}
    for relation, graph in graphs.items():
        if graph.number_of_edges() == 0:
            continue
        relation_weight = float(attention.get(relation, 0.0))
        if relation_weight <= 0.0:
            continue
        relation_aggregate = np.zeros_like(features)
        degree_weight = np.zeros((len(nodes), 1), dtype=float)
        for source, target, attrs in graph.edges(data=True):
            if source not in node_index or target not in node_index:
                continue
            source_index = node_index[source]
            target_index = node_index[target]
            weight = float(attrs.get("weight", 1.0))
            relation_aggregate[source_index] += weight * features[target_index]
            relation_aggregate[target_index] += weight * features[source_index]
            degree_weight[source_index, 0] += weight
            degree_weight[target_index, 0] += weight
        degree_weight[degree_weight <= 0.0] = 1.0
        aggregate += relation_weight * (relation_aggregate / degree_weight)
    return np.maximum(0.0, 0.5 * features + 0.5 * aggregate)


def _label_free_events(events: pd.DataFrame) -> pd.DataFrame:
    label_like_columns = [column for column in LABEL_COLUMNS if column in events.columns]
    return events.drop(columns=label_like_columns) if label_like_columns else events.copy()


def _base_discover_feature_matrix(
    fused: nx.Graph,
    dynamic_fused: nx.DiGraph,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
) -> tuple[np.ndarray, dict[str, float]]:
    centrality_features = _centrality_feature_matrix(fused, nodes)
    relation_features, relation_scores = _relation_degree_features(graphs, nodes)
    directed_features = _directed_feature_matrix(dynamic_fused, nodes)
    return np.concatenate([centrality_features, relation_features, directed_features], axis=1), relation_scores


def _community_records_from_graph(
    graph: nx.Graph,
    events: pd.DataFrame,
    nodes: Sequence[str],
    node_score_map: Mapping[str, float],
    *,
    community_algorithm: str = "leiden",
    seed: int = 42,
    communities: Sequence[set[str]] | None = None,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    partition = (
        [set(map(str, community)) for community in communities]
        if communities is not None
        else (
            _detect_communities(graph, algorithm=community_algorithm, seed=seed)
            if graph.number_of_edges()
            else [{node} for node in nodes]
        )
    )
    cluster_by_node: dict[str, int] = {}
    community_records = []
    for cluster_id, community in enumerate(partition):
        for node in community:
            cluster_by_node[node] = cluster_id
        subgraph = graph.subgraph(community)
        evidence = _community_evidence(events, community)
        community_records.append(
            {
                "cluster_id": cluster_id,
                "size": len(community),
                "community_score": round(float(np.mean([float(node_score_map.get(node, 0.0)) for node in community])), 6),
                "density": round(float(nx.density(subgraph)), 6) if len(community) > 1 else 0.0,
                "top_nodes": sorted(community, key=lambda node: (-float(node_score_map.get(node, 0.0)), node))[:10],
                "top_objects": evidence["top_objects"],
                "object_concentration": evidence["object_concentration"],
                "relation_breakdown": evidence["relation_breakdown"],
            }
        )
    return sorted(community_records, key=lambda item: (-float(item["community_score"]), item["cluster_id"])), cluster_by_node


def _graph_with_deep_edge_scores(graph: nx.Graph, edge_scores: Mapping[tuple[str, str], float]) -> nx.Graph:
    weighted = graph.copy()
    for source, target, attrs in weighted.edges(data=True):
        key = tuple(sorted((str(source), str(target))))
        learned_score = float(edge_scores.get(key, 0.0))
        attrs["edge_score"] = learned_score
        attrs["original_weight"] = float(attrs.get("weight", 1.0))
        if learned_score > 0.0:
            attrs["weight"] = attrs["original_weight"] * learned_score
    return weighted


def _edge_key_text(source: object, target: object) -> str:
    left, right = sorted((str(source), str(target)))
    return f"{left}\t{right}"


def _serialize_observed_edge_scores(edge_scores: Mapping[tuple[str, str], float]) -> dict[str, float]:
    return {
        _edge_key_text(source, target): round(float(score), 6)
        for (source, target), score in sorted(edge_scores.items())
    }


def _embedding_row(embedding: np.ndarray, index: int) -> list[float]:
    if embedding.size == 0 or index >= embedding.shape[0]:
        return []
    return [round(float(value), 6) for value in embedding[index].tolist()]


def _deep_discover_summary(
    events: pd.DataFrame,
    *,
    relations: Sequence[str],
    seed: int,
    config: DeepGraphDiscoverConfig,
    community_algorithm: str = "leiden",
    structure_filter: str = "none",
    structure_filter_metric: str = "eigenvector",
    structure_filter_percentile: float = 90.0,
    structure_filter_use_weights: bool = False,
) -> dict[str, object]:
    events = _label_free_events(events)
    display_names = _account_display_name_map(events)
    graphs = build_unmasking_similarity_graphs(events, relations=relations, include_text_similarity=False)
    fused = fuse_similarity_graphs(graphs)
    dynamic_relation_graphs = build_dynamic_relation_graphs(events, relations=relations)
    dynamic_fused = fuse_directed_graphs(dynamic_relation_graphs)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, fused.nodes))))
    for node in nodes:
        fused.add_node(node)
        dynamic_fused.add_node(node)
        for graph in graphs.values():
            graph.add_node(node)
    features, relation_scores = _base_discover_feature_matrix(fused, dynamic_fused, graphs, nodes)
    if config.encoder == "lightweight":
        attention = _relation_attention(relation_scores, features[:, 4 : 4 + len(graphs)] if graphs else features, {}, nodes)
        embedding = _message_pass(graphs, nodes, features, attention)
        node_scores = _normalize_vector(np.linalg.norm(embedding, axis=1))
        deep_result = None
        weighted_fused = fused
    else:
        deep_result = run_deep_graph_discover(graphs, nodes, features, config)
        attention = deep_result.relation_attention
        embedding = deep_result.embeddings
        node_scores = _normalize_vector(np.linalg.norm(embedding, axis=1))
        weighted_fused = _graph_with_deep_edge_scores(fused, deep_result.edge_scores)
    node_score_map = {node: float(node_scores[index]) for index, node in enumerate(nodes)}

    # Discover is fixed to the full-graph stable encoder path. We keep the
    # old structure-filter arguments only so older scripts do not break, but
    # the requested pruning mode is ignored because it changes the task from
    # label-free community discovery into a structural screening variant and
    # empirically degraded community quality in our CoordinationDiscover runs.
    requested_structure_filter = {
        "mode": str(structure_filter),
        "metric": str(structure_filter_metric),
        "percentile": float(structure_filter_percentile),
        "use_weights": bool(structure_filter_use_weights),
    }
    filtered_graph, structure_filter_summary, selected_nodes, structure_filter_scores = _apply_discover_structure_filter(
        weighted_fused,
        mode="none",
        metric=structure_filter_metric,
        percentile=structure_filter_percentile,
        use_weights=False,
    )
    structure_filter_summary = {
        **structure_filter_summary,
        "mode": "none",
        "effective": False,
        "selection_graph": "weighted_fused_similarity_network" if config.encoder != "lightweight" else "fused_similarity_network",
        "selection_semantics": "full_graph_mainline",
        "requested_mode": requested_structure_filter["mode"],
        "requested_metric": requested_structure_filter["metric"],
        "requested_percentile": requested_structure_filter["percentile"],
        "requested_use_weights": requested_structure_filter["use_weights"],
        "deprecated_ignored": requested_structure_filter["mode"] != "none",
        "disabled_reason": (
            "CoordinationDiscover Discover is fixed to the stable full-graph encoder; "
            "Unmasking-style structural screening is no longer applied."
        ),
    }
    communities, cluster_by_node = _community_records_from_graph(
        filtered_graph,
        events,
        nodes,
        node_score_map,
        community_algorithm=community_algorithm,
        seed=seed,
    )
    graph_stats = graph_summary(filtered_graph, None, community_algorithm=community_algorithm, seed=seed)
    edge_graph = filtered_graph
    edge_records = _edge_records_from_graph(edge_graph, node_score_map)
    dynamic_edge_records = _dynamic_edge_records_from_graph(dynamic_fused, node_score_map)
    result = {
        "method": "dyna_colm_discover",
        "variant": "discover",
        "task": "coordination_community_discovery",
        "uses_lm_features": False,
        "uses_gnn_message_passing": config.encoder != "lightweight",
        "uses_direction_time_features": True,
        "uses_relation_attention": True,
        "relation_attention_mode": _discover_attention_mode(config.encoder),
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": graph_stats.get("community_algorithm_effective"),
        "community_algorithm_backend": graph_stats.get("community_algorithm_backend"),
        "community_algorithm_fallback_reason": graph_stats.get("community_algorithm_fallback_reason"),
        "uses_community_features": False,
        "graph_summary": graph_stats,
        "dynamic_graph_summary": dynamic_graph_summary(dynamic_fused),
        "relation_attention": {key: round(float(value), 6) for key, value in attention.items()},
        "structure_filter": {
            **structure_filter_summary,
            "metric_scores_preview": {
                key: round(float(value), 6)
                for key, value in sorted(structure_filter_scores.items(), key=lambda item: (-float(item[1]), item[0]))[:20]
            },
        },
        "classifier_backend": f"{config.encoder}_discover_encoder",
        "metrics": None,
        "nodes": [
            {
                "account_id": node,
                "nickname": display_names.get(node),
                "node_score": round(node_score_map[node], 6),
                "deep_node_score": round(node_score_map[node], 6),
                "embedding_norm": round(float(np.linalg.norm(embedding[index])), 6) if embedding.size else 0.0,
                "discover_embedding": _embedding_row(embedding, index),
                "cluster_id": cluster_by_node.get(node),
                # These compatibility fields stay in the schema because Detect
                # feature builders and old reports expect them, but Discover
                # no longer prunes nodes so every node passes with a neutral
                # full-graph score.
                "passed_structure_filter": node in selected_nodes,
                "structure_filter_score": round(float(structure_filter_scores.get(node, 0.0)), 6),
                "directed_out_weight": round(float(dynamic_fused.out_degree(node, weight="weight")), 6),
                "directed_in_weight": round(float(dynamic_fused.in_degree(node, weight="weight")), 6),
            }
            for index, node in enumerate(nodes)
        ],
        "edges": edge_records,
        "dynamic_edges": dynamic_edge_records,
        "communities": communities,
        "deep_graph_model": _deep_graph_model_summary(config, deep_result),
        "model_governance": _discover_encoder_governance(config.encoder),
    }
    return result


def run_zeyan_coexpression_discover(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    community_algorithm: str = "leiden",
    include_text_similarity: bool = False,
) -> dict[str, object]:
    """Zeyan-style co-expression baseline: static user-user graph plus community detection."""
    events = _label_free_events(events)
    graphs = build_unmasking_similarity_graphs(
        events,
        relations=relations,
        include_text_similarity=include_text_similarity,
    )
    fused = fuse_similarity_graphs(graphs)
    dynamic_relation_graphs = build_dynamic_relation_graphs(events, relations=relations)
    dynamic_fused = fuse_directed_graphs(dynamic_relation_graphs)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, fused.nodes))))
    fused.add_nodes_from(nodes)
    dynamic_fused.add_nodes_from(nodes)
    for graph in graphs.values():
        graph.add_nodes_from(nodes)
    centrality = _centrality_feature_matrix(fused, nodes)
    degree_scores = _normalize_vector(
        np.asarray([float(fused.degree(node, weight="weight")) for node in nodes], dtype=float)
    )
    node_scores = _normalize_vector(centrality[:, 0] + centrality[:, 1] + degree_scores)
    node_score_map = {node: float(node_scores[index]) for index, node in enumerate(nodes)}
    communities, cluster_by_node = _community_records_from_graph(
        fused,
        events,
        nodes,
        node_score_map,
        community_algorithm=community_algorithm,
        seed=seed,
    )
    edge_records = _edge_records_from_graph(fused, node_score_map)
    dynamic_edge_records = _dynamic_edge_records_from_graph(dynamic_fused, node_score_map)
    active_relations = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0]
    relation_weight = _safe_divide(1.0, len(active_relations))
    graph_stats = graph_summary(fused, None, community_algorithm=community_algorithm, seed=seed)
    result = {
        "method": "zeyan_coexpression_discover",
        "variant": "zeyan_coexpression",
        "task": "coordination_community_discovery",
        "uses_lm_features": include_text_similarity,
        "uses_gnn_message_passing": False,
        "uses_direction_time_features": True,
        "uses_relation_attention": False,
        "relation_attention_mode": "static_zeyan_coexpression",
        "uses_community_features": False,
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": graph_stats.get("community_algorithm_effective"),
        "community_algorithm_backend": graph_stats.get("community_algorithm_backend"),
        "community_algorithm_fallback_reason": graph_stats.get("community_algorithm_fallback_reason"),
        "graph_summary": graph_stats,
        "dynamic_graph_summary": dynamic_graph_summary(dynamic_fused),
        "relation_attention": {relation: round(relation_weight, 6) for relation in active_relations},
        "classifier_backend": "zeyan_static_coexpression",
        "metrics": None,
        "nodes": [
            {
                "account_id": node,
                "node_score": round(node_score_map[node], 6),
                "deep_node_score": round(node_score_map[node], 6),
                "embedding_norm": round(float(np.linalg.norm(centrality[index])), 6),
                "cluster_id": cluster_by_node.get(node),
                "directed_out_weight": round(float(dynamic_fused.out_degree(node, weight="weight")), 6),
                "directed_in_weight": round(float(dynamic_fused.in_degree(node, weight="weight")), 6),
            }
            for index, node in enumerate(nodes)
        ],
        "edges": edge_records,
        "dynamic_edges": dynamic_edge_records,
        "communities": communities,
        "deep_graph_model": {
            "encoder": "zeyan_coexpression",
            "training_loss": [],
            "reconstruction_metrics": {},
            "device": "cpu",
            "epochs": 0,
            "embedding_dim": int(centrality.shape[1]) if centrality.ndim == 2 else 0,
            "uses_labels": False,
            "metapath_attention": {},
            "intra_metapath_attention": {},
            "intra_metapath_attention_summary": {},
            "metapath_instance_counts": {},
            "object_node_count": 0,
            "edge_score_source": "static_coexpression_weight",
        },
    }
    return result


def run_zeyan_coexpression_summary(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    community_algorithm: str = "leiden",
    include_text_similarity: bool = False,
) -> dict[str, object]:
    result = run_zeyan_coexpression_discover(
        events,
        relations=relations,
        seed=seed,
        community_algorithm=community_algorithm,
        include_text_similarity=include_text_similarity,
    )
    summary = {
        "setting": "discover",
        "task": "coordination_community_discovery",
        "method": "zeyan_coexpression_discover",
        "relations": list(relations),
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": result.get("community_algorithm_effective"),
        "metrics": _discovery_metrics(result),
        "relation_attention": result.get("relation_attention", {}),
        "graph_metrics": result.get("graph_summary", {}),
        "dynamic_graph_metrics": result.get("dynamic_graph_summary", {}),
        "nodes": result.get("nodes", []),
        "edges": result.get("edges", []),
        "dynamic_edges": result.get("dynamic_edges", []),
        "communities": result.get("communities", []),
        "evidence_summary": _evidence_summary(result),
        "deep_graph_model": result.get("deep_graph_model", {}),
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "discovery_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return summary


def run_discover_ablation_suite(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    epochs: int = 5,
    embedding_dim: int = 16,
    hidden_dim: int = 16,
    device: str = "auto",
    community_algorithm: str = "leiden",
) -> dict[str, dict[str, object]]:
    variants = {
        "raw_graph_community": lambda: run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder="lightweight",
            community_algorithm=community_algorithm,
        ),
        "zeyan_coexpression": lambda: {
            **run_zeyan_coexpression_summary(
                events,
                relations=relations,
                seed=seed,
                community_algorithm=community_algorithm,
            )
        },
        "magnn_legacy": lambda: run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder="magnn_legacy",
            epochs=epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
            community_algorithm=community_algorithm,
        ),
        "han": lambda: run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder="han",
            epochs=epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
            community_algorithm=community_algorithm,
        ),
        "amdn_hage": lambda: run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder="amdn_hage",
            epochs=epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
            community_algorithm=community_algorithm,
        ),
    }
    output: dict[str, dict[str, object]] = {}
    for name, factory in variants.items():
        summary = factory()
        output[name] = summary
    return output


def _discover_attention_mode(encoder: str) -> str:
    if encoder == "lightweight":
        return "lightweight"
    if encoder == "han_relation":
        return "relation_semantic_attention"
    if encoder == "han":
        return "metapath_hierarchical_attention"
    if encoder == "magnn_legacy":
        return "metapath_instance_attention_legacy_gated"
    if encoder == "magnn":
        return "metapath_instance_attention"
    if encoder == "amdn_hage":
        return "temporal_hidden_group_estimation"
    return encoder


def _discover_encoder_governance(encoder: str) -> dict[str, object]:
    if encoder in DEPRECATED_DISCOVER_ENCODERS:
        return {
            "encoder": encoder,
            "status": "deprecated_non_claimable",
            "reason": DEPRECATED_DISCOVER_ENCODERS[encoder],
            "stable_default_encoder": STABLE_DISCOVER_ENCODER,
            "activation_policy": "historical_replay_only",
        }
    return {
        "encoder": encoder,
        "status": "stable_default" if encoder == STABLE_DISCOVER_ENCODER else "experimental_comparison",
        "reason": "iohunter_reconstruction_gate_passed_baseline" if encoder == STABLE_DISCOVER_ENCODER else "explicit_non_default_encoder",
        "stable_default_encoder": STABLE_DISCOVER_ENCODER,
        "activation_policy": "claimable_only_after_reconstruction_and_detect_gates",
    }


def _deep_graph_model_summary(
    config: DeepGraphDiscoverConfig,
    result: DeepGraphDiscoverResult | None,
) -> dict[str, object]:
    if result is None:
        return {
            "encoder": config.encoder,
            "training_loss": [],
            "reconstruction_metrics": {},
            "device": config.device,
            "epochs": int(config.epochs),
            "embedding_dim": int(config.embedding_dim),
            "uses_labels": False,
            "observed_edge_scores": {},
        }
    return {
        "encoder": result.encoder,
        "training_loss": result.training_loss,
        "reconstruction_metrics": result.reconstruction_metrics,
        "device": result.device,
        "epochs": int(config.epochs),
        "embedding_dim": int(config.embedding_dim),
        "uses_labels": result.uses_labels,
        "metapath_attention": result.metapath_attention,
        "intra_metapath_attention": result.intra_metapath_attention,
        "intra_metapath_attention_summary": {
            key: value
            for key, value in result.reconstruction_metrics.items()
            if key in {"attention_mechanism", "mean_target_attention_entropy", "max_instance_attention"}
        },
        "metapath_instance_counts": result.metapath_instance_counts,
        "object_node_count": result.object_node_count,
        "edge_score_source": result.edge_score_source,
        "observed_edge_scores": _serialize_observed_edge_scores(result.edge_scores),
        "hidden_group_count": len(set(result.hidden_groups.values())) if result.hidden_groups else 0,
        "temporal_nll": result.temporal_nll,
    }


def _edge_records_from_graph(graph: nx.Graph, node_score_map: Mapping[str, float]) -> list[dict[str, object]]:
    edge_records = []
    for source, target, attrs in graph.edges(data=True):
        edge_weight = float(attrs.get("weight", 1.0))
        learned_score = attrs.get("edge_score")
        edge_score = (
            float(learned_score)
            if learned_score is not None and float(learned_score) > 0.0
            else _sigmoid(math.log1p(edge_weight) + 0.5 * (float(node_score_map[source]) + float(node_score_map[target])))
        )
        edge_records.append(
            {
                "source": source,
                "target": target,
                "edge_score": round(edge_score, 6),
                "weight": edge_weight,
                "relations": attrs.get("relations", []),
            }
        )
    return sorted(edge_records, key=lambda item: (-float(item["edge_score"]), item["source"], item["target"]))[:100]


def _dynamic_edge_records_from_graph(graph: nx.DiGraph, node_score_map: Mapping[str, float]) -> list[dict[str, object]]:
    dynamic_edge_records = []
    for source, target, attrs in graph.edges(data=True):
        deltas = [float(delta) for delta in attrs.get("time_deltas", [])]
        edge_weight = float(attrs.get("weight", 1.0))
        # Target-only accounts can appear in directed retweet/reply/mention edges
        # even when they were not observed as event authors in the Discover graph.
        source_score = float(node_score_map.get(source, 0.0))
        target_score = float(node_score_map.get(target, 0.0))
        edge_score = _sigmoid(math.log1p(edge_weight) + 0.5 * (source_score + target_score))
        dynamic_edge_records.append(
            {
                "source": source,
                "target": target,
                "edge_score": round(edge_score, 6),
                "weight": round(edge_weight, 6),
                "count": int(attrs.get("count", 1)),
                "relations": attrs.get("relations", []),
                "objects": attrs.get("objects", [])[:10],
                "avg_time_delta": round(float(np.mean(deltas)), 6) if deltas else None,
            }
        )
    return sorted(
        dynamic_edge_records,
        key=lambda item: (-float(item["edge_score"]), item["source"], item["target"]),
    )[:100]


def run_dyna_colm_gnn_prototype(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    variant: str = "full",
    use_lm_features: bool = True,
    use_gnn_message_passing: bool = True,
    use_direction_time_features: bool = True,
    use_relation_attention: bool = True,
    relation_attention_mode: str = "learned",
    use_community_features: bool = True,
) -> dict[str, object]:
    labels = extract_labels(events)
    graphs = build_unmasking_similarity_graphs(events, relations=relations, include_text_similarity=False)
    fused = fuse_similarity_graphs(graphs)
    dynamic_relation_graphs = build_dynamic_relation_graphs(events, relations=relations)
    dynamic_fused = fuse_directed_graphs(dynamic_relation_graphs)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, fused.nodes))))
    for node in nodes:
        fused.add_node(node)
        dynamic_fused.add_node(node)
        for graph in graphs.values():
            graph.add_node(node)
    centrality_features = _centrality_feature_matrix(fused, nodes)
    relation_features, relation_scores = _relation_degree_features(graphs, nodes)
    if relation_attention_mode == "static":
        active_relations = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0]
        static_weight = _safe_divide(1.0, len(active_relations))
        attention = {relation: static_weight for relation in active_relations}
    elif not use_relation_attention:
        attention = {relation: 1.0 for relation in graphs}
    else:
        attention = _relation_attention(relation_scores, relation_features, labels, nodes)
    if not use_relation_attention and relation_attention_mode != "static":
        total_attention = float(sum(attention.values())) or 1.0
        attention = {relation: value / total_attention for relation, value in attention.items()}
    preliminary_scores = _normalize_vector(
        centrality_features[:, 0] + centrality_features[:, 1] + relation_features.sum(axis=1)
    )
    preliminary_score_map = {node: float(preliminary_scores[index]) for index, node in enumerate(nodes)}
    communities = (
        [set(map(str, community)) for community in greedy_modularity_communities(fused, weight="weight")]
        if fused.number_of_edges()
        else [{node} for node in nodes]
    )
    cluster_by_node: dict[str, int] = {}
    community_feature_by_node: dict[str, tuple[float, float, float, float]] = {}
    for cluster_id, community in enumerate(communities):
        for node in community:
            cluster_by_node[node] = cluster_id
        subgraph = fused.subgraph(community)
        evidence = _community_evidence(events, community)
        density = float(nx.density(subgraph)) if len(community) > 1 else 0.0
        mean_preliminary_score = float(np.mean([preliminary_score_map[node] for node in community]))
        for node in community:
            community_feature_by_node[node] = (
                float(len(community)),
                density,
                float(evidence["object_concentration"]),
                mean_preliminary_score,
            )
    feature_blocks = [centrality_features, relation_features]
    if use_direction_time_features:
        feature_blocks.append(_directed_feature_matrix(dynamic_fused, nodes))
    if use_lm_features:
        lm_features = np.concatenate(
            [
                _bag_feature_matrix(_user_content(events), nodes, max_features=64),
                _bag_feature_matrix(_metadata_text(events), nodes, max_features=64),
            ],
            axis=1,
        )
        if lm_features.shape[1] > 16:
            _, _, vt = np.linalg.svd(lm_features, full_matrices=False)
            lm_features = lm_features @ vt[:16].T
        feature_blocks.append(lm_features)
    if use_community_features:
        community_features = np.asarray(
            [community_feature_by_node.get(node, (1.0, 0.0, 0.0, 0.0)) for node in nodes],
            dtype=float,
        )
        for column in range(community_features.shape[1]):
            community_features[:, column] = _normalize_vector(community_features[:, column])
        feature_blocks.append(community_features)
    features = np.concatenate(feature_blocks, axis=1)
    embedding = _message_pass(graphs, nodes, features, attention) if use_gnn_message_passing else features
    if labels and len(set(labels.values())) >= 2:
        y = np.asarray([int(labels.get(node, 0)) for node in nodes], dtype=int)
        test_indices, scores, backend = _fit_classifier_scores(embedding, y, seed=seed)
        node_scores = np.zeros(len(nodes), dtype=float)
        if test_indices.size:
            node_scores[test_indices] = scores
        degree_scores = _normalize_vector(np.asarray([fused.degree(node, weight="weight") for node in nodes], dtype=float))
        node_scores = np.where(node_scores > 0.0, node_scores, degree_scores)
        metrics = binary_metrics(y[test_indices], scores) if test_indices.size else None
    else:
        backend = "unsupervised_degree_pagerank"
        metrics = None
        node_scores = preliminary_scores
    node_score_map = {node: float(node_scores[index]) for index, node in enumerate(nodes)}
    community_records = []
    for cluster_id, community in enumerate(communities):
        subgraph = fused.subgraph(community)
        evidence = _community_evidence(events, community)
        community_records.append(
            {
                "cluster_id": cluster_id,
                "size": len(community),
                "community_score": round(float(np.mean([node_score_map[node] for node in community])), 6),
                "density": round(float(nx.density(subgraph)), 6) if len(community) > 1 else 0.0,
                "top_nodes": sorted(community, key=lambda node: (-node_score_map[node], node))[:10],
                "top_objects": evidence["top_objects"],
                "object_concentration": evidence["object_concentration"],
                "relation_breakdown": evidence["relation_breakdown"],
            }
        )
    edge_records = []
    for source, target, attrs in fused.edges(data=True):
        edge_weight = float(attrs.get("weight", 1.0))
        edge_score = _sigmoid(
            math.log1p(edge_weight)
            + 0.5 * (node_score_map.get(source, 0.0) + node_score_map.get(target, 0.0))
        )
        edge_records.append(
            {
                "source": source,
                "target": target,
                "edge_score": round(edge_score, 6),
                "weight": edge_weight,
                "relations": attrs.get("relations", []),
            }
        )
    dynamic_edge_records = []
    for source, target, attrs in dynamic_fused.edges(data=True):
        deltas = [float(delta) for delta in attrs.get("time_deltas", [])]
        edge_weight = float(attrs.get("weight", 1.0))
        edge_score = _sigmoid(
            math.log1p(edge_weight)
            + 0.5 * (node_score_map.get(source, 0.0) + node_score_map.get(target, 0.0))
        )
        dynamic_edge_records.append(
            {
                "source": source,
                "target": target,
                "edge_score": round(edge_score, 6),
                "weight": round(edge_weight, 6),
                "count": int(attrs.get("count", 1)),
                "relations": attrs.get("relations", []),
                "objects": attrs.get("objects", [])[:10],
                "avg_time_delta": round(float(np.mean(deltas)), 6) if deltas else None,
            }
        )
    return {
        "method": "dyna_colm_gnn_prototype",
        "variant": variant,
        "task": "coordination_community_discovery_then_discrimination",
        "uses_lm_features": use_lm_features,
        "uses_gnn_message_passing": use_gnn_message_passing,
        "uses_direction_time_features": use_direction_time_features,
        "uses_relation_attention": use_relation_attention,
        "relation_attention_mode": relation_attention_mode,
        "uses_community_features": use_community_features,
        "graph_summary": graph_summary(fused, labels),
        "dynamic_graph_summary": dynamic_graph_summary(dynamic_fused),
        "relation_attention": {key: round(value, 6) for key, value in attention.items()},
        "classifier_backend": backend,
        "metrics": _metric_to_dict(metrics),
        "nodes": [
            {
                "account_id": node,
                "node_score": round(node_score_map[node], 6),
                "cluster_id": cluster_by_node.get(node),
                "directed_out_weight": round(float(dynamic_fused.out_degree(node, weight="weight")), 6),
                "directed_in_weight": round(float(dynamic_fused.in_degree(node, weight="weight")), 6),
            }
            for node in nodes
        ],
        "edges": sorted(edge_records, key=lambda item: (-float(item["edge_score"]), item["source"], item["target"]))[:100],
        "dynamic_edges": sorted(
            dynamic_edge_records,
            key=lambda item: (-float(item["edge_score"]), item["source"], item["target"]),
        )[:100],
        "communities": sorted(community_records, key=lambda item: (-float(item["community_score"]), item["cluster_id"])),
    }


def run_dyna_colm_gnn_ablations(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, dict[str, object]]:
    """Run the first-version DynaCoLM-GNN ablations used in CoordinationDiscover comparison tables."""
    variants = {
        "full": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
        },
        "without_lm": {
            "use_lm_features": False,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
        },
        "without_gnn": {
            "use_lm_features": True,
            "use_gnn_message_passing": False,
            "use_direction_time_features": True,
        },
        "without_direction_time": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": False,
        },
        "without_relation_attention": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
            "use_relation_attention": False,
        },
        "static_relation_weight": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
            "relation_attention_mode": "static",
        },
        "no_community_features": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
            "use_community_features": False,
        },
    }
    return {
        name: run_dyna_colm_gnn_prototype(
            events,
            relations=relations,
            seed=seed,
            variant=name,
            **options,
        )
        for name, options in variants.items()
    }


def _community_avg_time_delta(dynamic_edges: Sequence[Mapping[str, object]], community_nodes: set[str]) -> float | None:
    values = [
        float(edge["avg_time_delta"])
        for edge in dynamic_edges
        if edge.get("avg_time_delta") is not None
        and str(edge.get("source")) in community_nodes
        and str(edge.get("target")) in community_nodes
    ]
    if not values:
        return None
    return round(float(np.mean(values)), 6)


def _discovery_metrics(result: Mapping[str, object]) -> dict[str, object]:
    graph = result.get("graph_summary") if isinstance(result.get("graph_summary"), Mapping) else {}
    dynamic_graph = result.get("dynamic_graph_summary") if isinstance(result.get("dynamic_graph_summary"), Mapping) else {}
    communities = result.get("communities") if isinstance(result.get("communities"), Sequence) else []
    structure_filter = result.get("structure_filter") if isinstance(result.get("structure_filter"), Mapping) else {}
    object_concentration = [
        float(community.get("object_concentration", 0.0))
        for community in communities
        if isinstance(community, Mapping)
    ]
    relation_counts: Counter[str] = Counter()
    for community in communities:
        if not isinstance(community, Mapping):
            continue
        breakdown = community.get("relation_breakdown")
        if isinstance(breakdown, Mapping):
            relation_counts.update({str(key): int(value) for key, value in breakdown.items()})
    deep_model = result.get("deep_graph_model") if isinstance(result.get("deep_graph_model"), Mapping) else {}
    reconstruction = deep_model.get("reconstruction_metrics") if isinstance(deep_model.get("reconstruction_metrics"), Mapping) else {}
    return {
        "modularity": graph.get("modularity"),
        "density": graph.get("density"),
        "conductance": graph.get("conductance"),
        "cluster_count": graph.get("cluster_count", len(communities)),
        "largest_cluster_size": graph.get("largest_cluster_size"),
        "dynamic_edge_count": dynamic_graph.get("edge_count"),
        "mean_object_concentration": round(float(np.mean(object_concentration)), 6) if object_concentration else 0.0,
        "max_object_concentration": round(float(np.max(object_concentration)), 6) if object_concentration else 0.0,
        "relation_entropy": _counter_entropy(relation_counts),
        "structure_filter_removed_fraction": structure_filter.get("removed_node_fraction"),
        "structure_filter_selected_fraction": structure_filter.get("selected_node_fraction"),
        "reconstruction_auc": reconstruction.get("auc"),
        "reconstruction_ap": reconstruction.get("average_precision"),
        "final_training_loss": _final_training_loss(deep_model),
    }


def _final_training_loss(deep_model: Mapping[str, object]) -> float | None:
    losses = deep_model.get("training_loss")
    if isinstance(losses, Sequence) and losses:
        return float(losses[-1])
    return None


def _counter_entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for value in counter.values():
        probability = value / total
        if probability > 0:
            entropy -= probability * math.log(probability, 2)
    return round(float(entropy), 6)


def _evidence_summary(result: Mapping[str, object], top_k: int = 10) -> dict[str, object]:
    relation_counts: Counter[str] = Counter()
    top_objects: Counter[tuple[str, str]] = Counter()
    communities = result.get("communities") if isinstance(result.get("communities"), Sequence) else []
    for community in communities:
        if not isinstance(community, Mapping):
            continue
        breakdown = community.get("relation_breakdown")
        if isinstance(breakdown, Mapping):
            relation_counts.update({str(key): int(value) for key, value in breakdown.items()})
        for item in community.get("top_objects", []):
            if isinstance(item, Mapping):
                top_objects[(str(item.get("relation", "") or ""), str(item.get("object_id")))] += int(item.get("count", 0))
    return {
        "top_objects": [
            {"relation": relation, "object_id": object_id, "count": count}
            for (relation, object_id), count in top_objects.most_common(top_k)
        ],
        "relation_breakdown": dict(relation_counts),
        "top_edges": result.get("edges", [])[:top_k],
        "top_dynamic_edges": result.get("dynamic_edges", [])[:top_k],
        "structure_filter": result.get("structure_filter", {}),
    }


def _prediction_rows(result: Mapping[str, object], labels: Mapping[str, int]) -> list[dict[str, object]]:
    rows = []
    for node in result.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        score = float(node.get("node_score", 0.0))
        account_id = str(node.get("account_id"))
        rows.append(
            {
                "account_id": account_id,
                "node_score": round(score, 6),
                "predicted_label": int(score >= 0.5),
                "label": int(labels.get(account_id, 0)),
                "cluster_id": node.get("cluster_id"),
                "directed_out_weight": node.get("directed_out_weight"),
                "directed_in_weight": node.get("directed_in_weight"),
            }
        )
    return sorted(rows, key=lambda row: (-float(row["node_score"]), row["account_id"]))


def _discover_node_feature_table(
    discovery: Mapping[str, object],
    labels: Mapping[str, int],
) -> tuple[list[str], np.ndarray, np.ndarray, dict[str, dict[str, object]]]:
    nodes = [str(node.get("account_id")) for node in discovery.get("nodes", []) if isinstance(node, Mapping)]
    node_records = {
        str(node.get("account_id")): dict(node)
        for node in discovery.get("nodes", [])
        if isinstance(node, Mapping)
    }
    community_records = {
        community.get("cluster_id"): community
        for community in discovery.get("communities", [])
        if isinstance(community, Mapping)
    }
    attention = discovery.get("relation_attention", {})
    attention_values = [
        float(attention[key])
        for key in sorted(attention)
    ] if isinstance(attention, Mapping) else []
    graph_metrics = discovery.get("graph_metrics", {}) if isinstance(discovery.get("graph_metrics"), Mapping) else {}
    dynamic_metrics = discovery.get("dynamic_graph_metrics", {}) if isinstance(discovery.get("dynamic_graph_metrics"), Mapping) else {}
    model = discovery.get("deep_graph_model", {}) if isinstance(discovery.get("deep_graph_model"), Mapping) else {}
    metapath_counts = model.get("metapath_instance_counts", {}) if isinstance(model.get("metapath_instance_counts"), Mapping) else {}
    metapath_values = [
        math.log1p(float(metapath_counts[key]))
        for key in sorted(metapath_counts)
    ]
    embedding_dim = 0
    for account_id in nodes:
        values = node_records.get(account_id, {}).get("discover_embedding", [])
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            embedding_dim = max(embedding_dim, len(values))
    rows: list[list[float]] = []
    for account_id in nodes:
        node = node_records[account_id]
        cluster_id = node.get("cluster_id")
        community = community_records.get(cluster_id, {})
        relation_breakdown = community.get("relation_breakdown", {}) if isinstance(community, Mapping) else {}
        relation_total = float(sum(float(value) for value in relation_breakdown.values())) if isinstance(relation_breakdown, Mapping) else 0.0
        feature_row = [
            float(node.get("node_score", 0.0)),
            float(node.get("deep_node_score", node.get("node_score", 0.0))),
            math.log1p(float(node.get("embedding_norm", 0.0))),
            # Legacy placeholders preserved for Detect feature-shape stability.
            # Since Discover no longer performs structural filtering, these
            # fields stay neutral (score~=1, passed=True) on the full graph.
            float(node.get("structure_filter_score", 0.0)),
            float(bool(node.get("passed_structure_filter", False))),
            math.log1p(float(node.get("directed_out_weight", 0.0))),
            math.log1p(float(node.get("directed_in_weight", 0.0))),
            math.log1p(float(community.get("size", 1.0))) if isinstance(community, Mapping) else 0.0,
            float(community.get("community_score", 0.0)) if isinstance(community, Mapping) else 0.0,
            float(community.get("density", 0.0)) if isinstance(community, Mapping) else 0.0,
            float(community.get("object_concentration", 0.0)) if isinstance(community, Mapping) else 0.0,
            math.log1p(relation_total),
            float(graph_metrics.get("modularity", 0.0) or 0.0),
            float(graph_metrics.get("density", 0.0) or 0.0),
            math.log1p(float(dynamic_metrics.get("edge_count", 0.0) or 0.0)),
            math.log1p(float(model.get("object_node_count", 0.0) or 0.0)),
        ]
        feature_row.extend(attention_values)
        feature_row.extend(metapath_values)
        embedding_values = node.get("discover_embedding", [])
        if embedding_dim:
            if isinstance(embedding_values, Sequence) and not isinstance(embedding_values, (str, bytes)):
                padded_embedding = [float(value) for value in embedding_values[:embedding_dim]]
            else:
                padded_embedding = []
            padded_embedding.extend([0.0] * (embedding_dim - len(padded_embedding)))
            # Full Discover embeddings carry the MAGNN/HAN latent representation;
            # embedding_norm above is kept only as a backward-compatible summary.
            feature_row.extend(padded_embedding)
        rows.append(feature_row)
    if not rows:
        return [], np.empty((0, 0), dtype=float), np.empty(0, dtype=int), node_records
    features = np.asarray(rows, dtype=float)
    for column in range(features.shape[1]):
        features[:, column] = _normalize_vector(features[:, column])
    y = np.asarray([int(labels.get(node, 0)) for node in nodes], dtype=int)
    return nodes, features, y, node_records


def _discover_embedding_dim(discovery: Mapping[str, object]) -> int:
    for node in discovery.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        embedding = node.get("discover_embedding")
        if isinstance(embedding, Sequence) and not isinstance(embedding, (str, bytes)):
            return len(embedding)
    return 0


def _discover_edge_score_lookup(discovery: Mapping[str, object]) -> dict[tuple[str, str], float]:
    model = discovery.get("deep_graph_model", {}) if isinstance(discovery.get("deep_graph_model"), Mapping) else {}
    raw_scores = model.get("observed_edge_scores", {}) if isinstance(model.get("observed_edge_scores"), Mapping) else {}
    lookup: dict[tuple[str, str], float] = {}
    for key, value in raw_scores.items():
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if score <= 0.0:
            continue
        if isinstance(key, str) and "\t" in key:
            left, right = key.split("\t", 1)
        elif isinstance(key, str) and "|" in key:
            left, right = key.split("|", 1)
        elif isinstance(key, Sequence) and not isinstance(key, (str, bytes)) and len(key) == 2:
            left, right = str(key[0]), str(key[1])
        else:
            continue
        lookup[tuple(sorted((str(left), str(right))))] = score
    if lookup:
        return lookup
    # Backward compatibility: older cached discoveries only wrote top-K edge records.
    for edge in discovery.get("edges", []):
        if not isinstance(edge, Mapping):
            continue
        source = edge.get("source")
        target = edge.get("target")
        if source is None or target is None:
            continue
        try:
            score = float(edge.get("edge_score", 0.0))
        except (TypeError, ValueError):
            continue
        if score > 0.0:
            lookup[tuple(sorted((str(source), str(target))))] = score
    return lookup


def _apply_discover_edge_scores_to_relation_graphs(
    graphs: Mapping[str, nx.Graph],
    discovery: Mapping[str, object],
) -> tuple[dict[str, nx.Graph], int]:
    edge_scores = _discover_edge_score_lookup(discovery)
    reweighted: dict[str, nx.Graph] = {}
    changed = 0
    for relation, graph in graphs.items():
        relation_graph = graph.copy()
        for source, target, attrs in relation_graph.edges(data=True):
            key = tuple(sorted((str(source), str(target))))
            score = edge_scores.get(key)
            attrs["original_weight"] = float(attrs.get("weight", 1.0))
            if score is None:
                attrs["discover_edge_score"] = None
                continue
            attrs["discover_edge_score"] = float(score)
            attrs["weight"] = attrs["original_weight"] * float(score)
            changed += 1
        reweighted[relation] = relation_graph
    return reweighted, changed


def prepare_dyna_colm_detect_inputs(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    discover_encoder: str = STABLE_DISCOVER_ENCODER,
    discover_epochs: int = 20,
    embedding_dim: int = 32,
    hidden_dim: int = 32,
    device: str = "auto",
    lm_backend: str = "sbert",
    gnn_backend: str = "gfm_lm_gnn",
    precomputed_discovery: Mapping[str, object] | None = None,
    lm_cache_dir: Path | None = None,
) -> PreparedDetectInputs:
    labels = extract_labels(events)
    if not labels or len(set(labels.values())) < 2:
        raise ValueError("DynaCoLM-Detect requires at least two label classes")
    discovery = (
        dict(precomputed_discovery)
        if precomputed_discovery is not None
        else run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder=discover_encoder,
            epochs=discover_epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
        )
    )
    nodes, discover_features, y, node_records = _discover_node_feature_table(discovery, labels)
    lm_features, lm_feature_source = _lm_feature_matrix(
        events,
        nodes,
        backend=lm_backend,
        max_dim=max(8, embedding_dim),
        cache_dir=lm_cache_dir,
    )
    discover_feature_count = int(discover_features.shape[1]) if discover_features.ndim == 2 else 0
    lm_feature_count = int(lm_features.shape[1]) if lm_features.ndim == 2 else 0
    discover_embedding_dim = _discover_embedding_dim(discovery)
    features = np.concatenate([discover_features, lm_features], axis=1)
    for column in range(features.shape[1]):
        features[:, column] = _normalize_vector(features[:, column])
    graphs: dict[str, nx.Graph] = {}
    reweighted_edge_count = 0
    uses_discover_reweighted_edges = False
    if gnn_backend in {"relation_gnn", "fusion_gnn", "gfm_lm_gnn", "gfm_lm_gnn_cpu_light"}:
        raw_graphs = build_unmasking_similarity_graphs(_label_free_events(events), relations=relations, include_text_similarity=False)
        graphs, reweighted_edge_count = _apply_discover_edge_scores_to_relation_graphs(raw_graphs, discovery)
        uses_discover_reweighted_edges = reweighted_edge_count > 0
        for graph in graphs.values():
            graph.add_nodes_from(nodes)
    return PreparedDetectInputs(
        discovery=discovery,
        labels=labels,
        nodes=list(nodes),
        discover_features=discover_features,
        lm_features=lm_features,
        features=features,
        y=y,
        node_records=node_records,
        graphs=graphs,
        lm_feature_source=lm_feature_source,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
        discover_embedding_dim=discover_embedding_dim,
        reweighted_edge_count=int(reweighted_edge_count),
        uses_discover_reweighted_edges=uses_discover_reweighted_edges,
    )


def _fit_transductive_scores(features: np.ndarray, y: np.ndarray, *, seed: int = 42) -> tuple[np.ndarray, str]:
    return _fit_transductive_scores_with_split(features, y, seed=seed)


def _fit_transductive_scores_with_split(
    features: np.ndarray,
    y: np.ndarray,
    *,
    seed: int = 42,
    split: Split | None = None,
) -> tuple[np.ndarray, str]:
    if y.size == 0:
        return np.asarray([], dtype=float), "no_nodes"
    if len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "single_class"
    split = split or _make_split(y, seed=seed)
    scores = np.zeros(y.size, dtype=float)
    if split.test.size:
        try:
            from sklearn.ensemble import RandomForestClassifier

            classifier = RandomForestClassifier(n_estimators=200, random_state=seed, class_weight="balanced")
            classifier.fit(features[split.train], y[split.train])
            scores[split.test] = classifier.predict_proba(features[split.test])[:, 1]
            backend = "discover_features_random_forest"
        except Exception:
            scores[split.test] = _fit_numpy_logistic(features[split.train], y[split.train], features[split.test])
            backend = "discover_features_numpy_logistic"
    else:
        backend = "discover_features_no_test_split"
    if split.train.size:
        scores[split.train] = _fit_numpy_logistic(features[split.train], y[split.train], features[split.train])
    fallback = _normalize_vector(features[:, 0]) if features.shape[1] else np.zeros(y.size, dtype=float)
    scores = np.where(scores > 0.0, scores, fallback)
    return scores, backend


def _split_detect_feature_groups(
    features: np.ndarray,
    *,
    discover_feature_count: int,
    lm_feature_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    node_count = int(features.shape[0]) if features.ndim == 2 else 0
    feature_width = int(features.shape[1]) if features.ndim == 2 else 0
    discover_stop = max(0, min(int(discover_feature_count), feature_width))
    lm_start = discover_stop
    lm_stop = max(lm_start, min(lm_start + max(0, int(lm_feature_count)), feature_width))
    struct_features = features[:, :discover_stop] if discover_stop > 0 else np.zeros((node_count, 1), dtype=float)
    lm_features = features[:, lm_start:lm_stop] if lm_stop > lm_start else np.zeros((node_count, 1), dtype=float)
    return np.asarray(struct_features, dtype=float), np.asarray(lm_features, dtype=float)


def _build_relation_adjacency_tensors(torch, graphs: Mapping[str, nx.Graph], nodes: Sequence[str], target_device: str):
    node_index = {node: index for index, node in enumerate(nodes)}
    relation_names = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0] or list(graphs) or ["empty_relation"]

    def adjacency_for(graph: nx.Graph):
        rows: list[int] = []
        cols: list[int] = []
        vals: list[float] = []
        for source, target, attrs in graph.edges(data=True):
            if source not in node_index or target not in node_index:
                continue
            left = node_index[str(source)]
            right = node_index[str(target)]
            weight = max(float(attrs.get("weight", 1.0)), 1e-6)
            rows.extend((left, right))
            cols.extend((right, left))
            vals.extend((weight, weight))
        for idx in range(len(nodes)):
            rows.append(idx)
            cols.append(idx)
            vals.append(1.0)
        row_array = np.asarray(rows, dtype=np.int64)
        col_array = np.asarray(cols, dtype=np.int64)
        val_array = np.asarray(vals, dtype=np.float32)
        degree = np.bincount(row_array, weights=val_array, minlength=len(nodes)).astype(np.float32)
        degree[degree <= 0.0] = 1.0
        val_array = val_array / degree[row_array]
        indices = torch.as_tensor(np.vstack([row_array, col_array]), dtype=torch.long, device=target_device)
        values = torch.as_tensor(val_array, dtype=torch.float32, device=target_device)
        return torch.sparse_coo_tensor(indices, values, (len(nodes), len(nodes)), device=target_device).coalesce()

    adjacency_tensors = [adjacency_for(graphs.get(relation, nx.Graph())) for relation in relation_names]
    return relation_names, adjacency_tensors


def _sample_relation_edge_pairs(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    relation_names: Sequence[str],
    *,
    seed: int = 42,
    max_positive: int = 4096,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample observed and unobserved user pairs for Detect graph-reconstruction loss."""
    node_index = {str(node): index for index, node in enumerate(nodes)}
    relation_index = {relation: index for index, relation in enumerate(relation_names)}
    positives: list[tuple[int, int, int, float]] = []
    connected: set[tuple[int, int]] = set()
    for relation in relation_names:
        graph = graphs.get(relation)
        if graph is None:
            continue
        rel_idx = relation_index.get(relation, 0)
        for source, target, attrs in graph.edges(data=True):
            if str(source) not in node_index or str(target) not in node_index:
                continue
            left = node_index[str(source)]
            right = node_index[str(target)]
            if left == right:
                continue
            pair = tuple(sorted((left, right)))
            connected.add(pair)
            weight = max(float(attrs.get("weight", 1.0)), 1e-6)
            positives.append((left, right, rel_idx, min(math.log1p(weight) + 1.0, 5.0)))
    if not positives or len(nodes) < 2:
        return (
            np.empty((0, 2), dtype=np.int64),
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.float32),
            np.empty(0, dtype=np.float32),
        )
    rng = np.random.default_rng(seed)
    if len(positives) > max_positive:
        keep = rng.choice(len(positives), size=max_positive, replace=False)
        positives = [positives[int(index)] for index in keep]
    negatives: set[tuple[int, int]] = set()
    attempts = 0
    target_negative_count = len(positives)
    while len(negatives) < target_negative_count and attempts < target_negative_count * 50:
        attempts += 1
        left = int(rng.integers(0, len(nodes)))
        right = int(rng.integers(0, len(nodes)))
        if left == right:
            continue
        pair = tuple(sorted((left, right)))
        if pair in connected or pair in negatives:
            continue
        negatives.add(pair)
    if len(negatives) < target_negative_count:
        for left in range(len(nodes)):
            for right in range(left + 1, len(nodes)):
                pair = (left, right)
                if pair in connected or pair in negatives:
                    continue
                negatives.add(pair)
                if len(negatives) >= target_negative_count:
                    break
            if len(negatives) >= target_negative_count:
                break
    relation_count = max(len(relation_names), 1)
    pairs: list[tuple[int, int]] = []
    relations: list[int] = []
    labels: list[float] = []
    weights: list[float] = []
    for left, right, rel_idx, weight in positives:
        pairs.append((left, right))
        relations.append(rel_idx)
        labels.append(1.0)
        weights.append(weight)
    for left, right in sorted(negatives):
        pairs.append((left, right))
        relations.append(int(rng.integers(0, relation_count)))
        labels.append(0.0)
        weights.append(1.0)
    return (
        np.asarray(pairs, dtype=np.int64),
        np.asarray(relations, dtype=np.int64),
        np.asarray(labels, dtype=np.float32),
        np.asarray(weights, dtype=np.float32),
    )


def _torch_relation_gnn_scores(
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    seed: int = 42,
    epochs: int = 120,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    device: str = "auto",
    split: Split | None = None,
) -> tuple[np.ndarray, str, dict[str, object]]:
    if y.size == 0 or len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "relation_gnn_single_class", {}
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except Exception:
        scores, backend = _fit_transductive_scores(features, y, seed=seed)
        return scores, f"{backend}_fallback_no_torch", {}

    split = split or _make_split(y, seed=seed)
    if split.test.size == 0 or split.train.size == 0:
        return np.zeros(y.size, dtype=float), "relation_gnn_no_test_split", {}
    if len(set(y[split.train].tolist())) < 2:
        scores, backend = _fit_transductive_scores(features, y, seed=seed)
        return scores, f"{backend}_fallback_single_train_class", {}

    torch.manual_seed(seed)
    target_device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    if target_device == "cuda" and not torch.cuda.is_available():
        target_device = "cpu"

    relation_names, adjacency_tensors = _build_relation_adjacency_tensors(torch, graphs, nodes, target_device)
    x = torch.as_tensor(features, dtype=torch.float32, device=target_device)
    labels = torch.as_tensor(y.astype(np.float32), dtype=torch.float32, device=target_device)
    train_index = torch.as_tensor(split.train, dtype=torch.long, device=target_device)

    class RelationGNN(nn.Module):
        def __init__(self, input_dim: int, hidden: int, relation_count: int):
            super().__init__()
            self.input_projection = nn.Linear(input_dim, hidden)
            self.relation_linears = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(relation_count)])
            self.semantic_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.semantic_context.view(1, -1))
            self.output = nn.Linear(hidden, 1)

        def forward(self, feature_tensor):
            base = functional.relu(self.input_projection(feature_tensor))
            relation_outputs = []
            for relation_index, adjacency in enumerate(adjacency_tensors):
                aggregated = torch.sparse.mm(adjacency, base)
                relation_outputs.append(functional.relu(self.relation_linears[relation_index](aggregated)))
            stacked = torch.stack(relation_outputs, dim=1)
            semantic_scores = (torch.tanh(stacked) * self.semantic_context.view(1, 1, -1)).sum(dim=2).mean(dim=0)
            attention = torch.softmax(semantic_scores, dim=0)
            combined = (stacked * attention.view(1, -1, 1)).sum(dim=1)
            return self.output(combined).squeeze(1), attention

    model = RelationGNN(features.shape[1], max(2, int(hidden_dim)), len(relation_names)).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    positives = max(float(np.sum(y[split.train] == 1)), 1.0)
    negatives = max(float(np.sum(y[split.train] == 0)), 1.0)
    pos_weight = torch.as_tensor([negatives / positives], dtype=torch.float32, device=target_device)
    for _ in range(max(1, int(epochs))):
        model.train()
        optimizer.zero_grad()
        logits, _ = model(x)
        loss = functional.binary_cross_entropy_with_logits(logits[train_index], labels[train_index], pos_weight=pos_weight)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits, attention = model(x)
        probabilities = torch.sigmoid(logits).detach().cpu().numpy()
        attention_map = {
            relation: round(float(attention[index].detach().cpu().item()), 6)
            for index, relation in enumerate(relation_names)
        }
    scores = np.zeros(y.size, dtype=float)
    scores[split.test] = probabilities[split.test]
    details = {
        "fusion_architecture": "single_graph_branch",
        "relation_attention": attention_map,
        "branch_attention": {"graph": 1.0},
    }
    return scores, f"relation_gnn_torch:{json.dumps(attention_map, sort_keys=True)}", details


def _torch_fusion_gnn_scores(
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    discover_feature_count: int,
    lm_feature_count: int,
    seed: int = 42,
    epochs: int = 120,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    device: str = "auto",
    split: Split | None = None,
) -> tuple[np.ndarray, str, dict[str, object]]:
    if y.size == 0 or len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "fusion_gnn_single_class", {}
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except Exception:
        scores, backend = _fit_transductive_scores(features, y, seed=seed)
        return scores, f"{backend}_fallback_no_torch", {}

    split = split or _make_split(y, seed=seed)
    if split.test.size == 0 or split.train.size == 0:
        return np.zeros(y.size, dtype=float), "fusion_gnn_no_test_split", {}
    if len(set(y[split.train].tolist())) < 2:
        scores, backend = _fit_transductive_scores(features, y, seed=seed)
        return scores, f"{backend}_fallback_single_train_class", {}

    torch.manual_seed(seed)
    target_device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    if target_device == "cuda" and not torch.cuda.is_available():
        target_device = "cpu"

    relation_names, adjacency_tensors = _build_relation_adjacency_tensors(torch, graphs, nodes, target_device)
    struct_matrix, lm_matrix = _split_detect_feature_groups(
        features,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
    )
    x_struct = torch.as_tensor(struct_matrix, dtype=torch.float32, device=target_device)
    x_lm = torch.as_tensor(lm_matrix, dtype=torch.float32, device=target_device)
    labels = torch.as_tensor(y.astype(np.float32), dtype=torch.float32, device=target_device)
    train_index = torch.as_tensor(split.train, dtype=torch.long, device=target_device)

    class FusionGNN(nn.Module):
        def __init__(self, struct_dim: int, lm_dim: int, hidden: int, relation_count: int):
            super().__init__()
            self.struct_projection = nn.Linear(struct_dim, hidden)
            self.lm_projection = nn.Linear(lm_dim, hidden)
            self.struct_query = nn.Linear(hidden, hidden)
            self.struct_key = nn.Linear(hidden, hidden)
            self.lm_query = nn.Linear(hidden, hidden)
            self.lm_key = nn.Linear(hidden, hidden)
            self.graph_seed_projection = nn.Linear(hidden * 2, hidden)
            self.relation_linears = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(relation_count)])
            self.graph_semantic_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.graph_semantic_context.view(1, -1))
            self.branch_projection = nn.Linear(hidden, hidden)
            self.branch_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.branch_context.view(1, -1))
            self.output_hidden = nn.Linear(hidden, hidden)
            self.output = nn.Linear(hidden, 1)
            self.dropout = nn.Dropout(0.1)

        def forward(self, struct_x, lm_x):
            struct_base = functional.relu(self.struct_projection(struct_x))
            lm_base = functional.relu(self.lm_projection(lm_x))
            scale = math.sqrt(max(struct_base.shape[1], 1))
            struct_to_lm = torch.sigmoid(
                (self.struct_query(struct_base) * self.lm_key(lm_base)).sum(dim=1, keepdim=True) / scale
            )
            lm_to_struct = torch.sigmoid(
                (self.lm_query(lm_base) * self.struct_key(struct_base)).sum(dim=1, keepdim=True) / scale
            )
            struct_hidden = struct_base + struct_to_lm * lm_base
            lm_hidden = lm_base + lm_to_struct * struct_base
            graph_seed = functional.relu(self.graph_seed_projection(torch.cat([struct_hidden, lm_hidden], dim=1)))
            relation_outputs = []
            for relation_index, adjacency in enumerate(adjacency_tensors):
                aggregated = torch.sparse.mm(adjacency, graph_seed)
                relation_outputs.append(functional.relu(self.relation_linears[relation_index](aggregated)))
            stacked = torch.stack(relation_outputs, dim=1)
            graph_semantic_hidden = torch.tanh(stacked)
            graph_semantic_scores = (
                graph_semantic_hidden * self.graph_semantic_context.view(1, 1, -1)
            ).sum(dim=2).mean(dim=0)
            relation_attention = torch.softmax(graph_semantic_scores, dim=0)
            graph_hidden = (stacked * relation_attention.view(1, -1, 1)).sum(dim=1)
            branches = torch.stack([struct_hidden, lm_hidden, graph_hidden], dim=1)
            branch_scores = (
                torch.tanh(self.branch_projection(branches)) * self.branch_context.view(1, 1, -1)
            ).sum(dim=2)
            branch_attention = torch.softmax(branch_scores, dim=1)
            fused = (branches * branch_attention.unsqueeze(-1)).sum(dim=1)
            fused = functional.relu(self.output_hidden(self.dropout(fused)))
            logits = self.output(self.dropout(fused)).squeeze(1)
            cross_means = torch.stack([struct_to_lm.mean(), lm_to_struct.mean()])
            return logits, relation_attention, branch_attention.mean(dim=0), cross_means

    model = FusionGNN(
        x_struct.shape[1],
        x_lm.shape[1],
        max(4, int(hidden_dim)),
        len(relation_names),
    ).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    positives = max(float(np.sum(y[split.train] == 1)), 1.0)
    negatives = max(float(np.sum(y[split.train] == 0)), 1.0)
    pos_weight = torch.as_tensor([negatives / positives], dtype=torch.float32, device=target_device)
    for _ in range(max(1, int(epochs))):
        model.train()
        optimizer.zero_grad()
        logits, _, _, _ = model(x_struct, x_lm)
        loss = functional.binary_cross_entropy_with_logits(logits[train_index], labels[train_index], pos_weight=pos_weight)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits, relation_attention, branch_attention, cross_means = model(x_struct, x_lm)
        probabilities = torch.sigmoid(logits).detach().cpu().numpy()
        relation_attention_map = {
            relation: round(float(relation_attention[index].detach().cpu().item()), 6)
            for index, relation in enumerate(relation_names)
        }
        branch_names = ("struct", "lm", "graph")
        branch_attention_map = {
            branch_names[index]: round(float(branch_attention[index].detach().cpu().item()), 6)
            for index in range(len(branch_names))
        }
        cross_attention_mean = {
            "struct_to_lm": round(float(cross_means[0].detach().cpu().item()), 6),
            "lm_to_struct": round(float(cross_means[1].detach().cpu().item()), 6),
        }
    scores = np.zeros(y.size, dtype=float)
    scores[split.test] = probabilities[split.test]
    details = {
        "fusion_architecture": "discover_lm_graph_attention",
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": cross_attention_mean,
        "feature_group_sizes": {
            "discover": int(discover_feature_count),
            "lm": int(lm_feature_count),
        },
    }
    backend = {
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": cross_attention_mean,
    }
    return scores, f"fusion_gnn_torch:{json.dumps(backend, sort_keys=True)}", details


def _torch_gfm_lm_gnn_scores(
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    discover_feature_count: int,
    lm_feature_count: int,
    seed: int = 42,
    epochs: int = 120,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    device: str = "auto",
    split: Split | None = None,
    max_edge_reconstruction_positive: int = 1024,
) -> tuple[np.ndarray, str, dict[str, object]]:
    if y.size == 0 or len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "gfm_lm_gnn_single_class", {}
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except Exception:
        scores, backend = _fit_transductive_scores_with_split(features, y, seed=seed, split=split)
        return scores, f"{backend}_fallback_no_torch", {}

    split = split or _make_split(y, seed=seed)
    if split.test.size == 0 or split.train.size == 0:
        return np.zeros(y.size, dtype=float), "gfm_lm_gnn_no_test_split", {}
    if len(set(y[split.train].tolist())) < 2:
        scores, backend = _fit_transductive_scores_with_split(features, y, seed=seed, split=split)
        return scores, f"{backend}_fallback_single_train_class", {}

    torch.manual_seed(seed)
    target_device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    if target_device == "cuda" and not torch.cuda.is_available():
        target_device = "cpu"

    relation_names, adjacency_tensors = _build_relation_adjacency_tensors(torch, graphs, nodes, target_device)
    edge_pairs, edge_relations, edge_labels, edge_weights = _sample_relation_edge_pairs(
        graphs,
        nodes,
        relation_names,
        seed=seed,
        max_positive=max(1, int(max_edge_reconstruction_positive)),
    )
    struct_matrix, lm_matrix = _split_detect_feature_groups(
        features,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
    )
    x_struct = torch.as_tensor(struct_matrix, dtype=torch.float32, device=target_device)
    x_lm = torch.as_tensor(lm_matrix, dtype=torch.float32, device=target_device)
    labels = torch.as_tensor(y.astype(np.float32), dtype=torch.float32, device=target_device)
    train_index = torch.as_tensor(split.train, dtype=torch.long, device=target_device)
    if edge_pairs.size:
        edge_pair_tensor = torch.as_tensor(edge_pairs, dtype=torch.long, device=target_device)
        edge_relation_tensor = torch.as_tensor(edge_relations, dtype=torch.long, device=target_device)
        edge_label_tensor = torch.as_tensor(edge_labels, dtype=torch.float32, device=target_device)
        edge_weight_tensor = torch.as_tensor(edge_weights, dtype=torch.float32, device=target_device)
    else:
        edge_pair_tensor = torch.empty((0, 2), dtype=torch.long, device=target_device)
        edge_relation_tensor = torch.empty(0, dtype=torch.long, device=target_device)
        edge_label_tensor = torch.empty(0, dtype=torch.float32, device=target_device)
        edge_weight_tensor = torch.empty(0, dtype=torch.float32, device=target_device)

    class GFMLMGNN(nn.Module):
        def __init__(self, struct_dim: int, lm_dim: int, hidden: int, relation_count: int):
            super().__init__()
            self.discover_projection = nn.Sequential(nn.Linear(struct_dim, hidden), nn.ReLU(), nn.Dropout(0.1))
            self.lm_projection = nn.Sequential(nn.Linear(lm_dim, hidden), nn.ReLU(), nn.Dropout(0.1))
            self.discover_to_lm = nn.MultiheadAttention(hidden, num_heads=1, batch_first=True)
            self.lm_to_discover = nn.MultiheadAttention(hidden, num_heads=1, batch_first=True)
            self.graph_seed_projection = nn.Linear(hidden * 2, hidden)
            self.relation_linears = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(relation_count)])
            self.relation_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.relation_context.view(1, -1))
            self.branch_projection = nn.Linear(hidden, hidden)
            self.branch_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.branch_context.view(1, -1))
            self.output_hidden = nn.Linear(hidden, hidden)
            self.output = nn.Linear(hidden, 1)
            self.edge_relation_scale = nn.Embedding(relation_count, hidden)
            self.edge_relation_bias = nn.Embedding(relation_count, 1)
            nn.init.ones_(self.edge_relation_scale.weight)
            nn.init.zeros_(self.edge_relation_bias.weight)
            self.dropout = nn.Dropout(0.1)

        def forward(self, struct_x, lm_x):
            discover_base = self.discover_projection(struct_x)
            lm_base = self.lm_projection(lm_x)
            discover_context, discover_attention = self.discover_to_lm(
                discover_base.unsqueeze(1),
                lm_base.unsqueeze(1),
                lm_base.unsqueeze(1),
                need_weights=True,
            )
            lm_context, lm_attention = self.lm_to_discover(
                lm_base.unsqueeze(1),
                discover_base.unsqueeze(1),
                discover_base.unsqueeze(1),
                need_weights=True,
            )
            discover_hidden = discover_base + discover_context.squeeze(1)
            lm_hidden = lm_base + lm_context.squeeze(1)
            graph_seed = functional.relu(self.graph_seed_projection(torch.cat([discover_hidden, lm_hidden], dim=1)))
            relation_outputs = []
            for relation_index, adjacency in enumerate(adjacency_tensors):
                aggregated = torch.sparse.mm(adjacency, graph_seed)
                relation_outputs.append(functional.relu(self.relation_linears[relation_index](aggregated)))
            stacked = torch.stack(relation_outputs, dim=1)
            relation_scores = (torch.tanh(stacked) * self.relation_context.view(1, 1, -1)).sum(dim=2).mean(dim=0)
            relation_attention = torch.softmax(relation_scores, dim=0)
            graph_hidden = (stacked * relation_attention.view(1, -1, 1)).sum(dim=1)
            branches = torch.stack([discover_hidden, lm_hidden, graph_hidden], dim=1)
            branch_scores = (
                torch.tanh(self.branch_projection(branches)) * self.branch_context.view(1, 1, -1)
            ).sum(dim=2)
            branch_attention = torch.softmax(branch_scores, dim=1)
            fused = (branches * branch_attention.unsqueeze(-1)).sum(dim=1)
            hidden = functional.relu(self.output_hidden(self.dropout(fused)))
            logits = self.output(self.dropout(hidden)).squeeze(1)
            cross_attention_mean = torch.stack([discover_attention.mean(), lm_attention.mean()])
            return logits, fused, discover_hidden, lm_hidden, relation_attention, branch_attention.mean(dim=0), cross_attention_mean

        def edge_logits(self, node_embeddings, pairs, relation_ids):
            if pairs.numel() == 0:
                return torch.empty(0, dtype=node_embeddings.dtype, device=node_embeddings.device)
            left = node_embeddings[pairs[:, 0]]
            right = node_embeddings[pairs[:, 1]]
            relation_scale = self.edge_relation_scale(relation_ids)
            relation_bias = self.edge_relation_bias(relation_ids).squeeze(1)
            score = (left * right * relation_scale).sum(dim=1) / math.sqrt(max(node_embeddings.shape[1], 1))
            return score + relation_bias

    model = GFMLMGNN(
        x_struct.shape[1],
        x_lm.shape[1],
        max(4, int(hidden_dim)),
        len(relation_names),
    ).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    positives = max(float(np.sum(y[split.train] == 1)), 1.0)
    negatives = max(float(np.sum(y[split.train] == 0)), 1.0)
    pos_weight = torch.as_tensor([negatives / positives], dtype=torch.float32, device=target_device)
    final_losses = {"classification": 0.0, "edge_reconstruction": 0.0, "discover_lm_alignment": 0.0}
    for _ in range(max(1, int(epochs))):
        model.train()
        optimizer.zero_grad()
        logits, fused, discover_hidden, lm_hidden, _, _, _ = model(x_struct, x_lm)
        classification_loss = functional.binary_cross_entropy_with_logits(
            logits[train_index],
            labels[train_index],
            pos_weight=pos_weight,
        )
        if edge_pair_tensor.numel():
            reconstruction_logits = model.edge_logits(fused, edge_pair_tensor, edge_relation_tensor)
            reconstruction_loss = functional.binary_cross_entropy_with_logits(
                reconstruction_logits,
                edge_label_tensor,
                weight=edge_weight_tensor,
            )
        else:
            reconstruction_loss = logits.sum() * 0.0
        alignment_loss = 1.0 - functional.cosine_similarity(discover_hidden[train_index], lm_hidden[train_index], dim=1).mean()
        loss = classification_loss + 0.15 * reconstruction_loss + 0.05 * alignment_loss
        loss.backward()
        optimizer.step()
        final_losses = {
            "classification": float(classification_loss.detach().cpu().item()),
            "edge_reconstruction": float(reconstruction_loss.detach().cpu().item()),
            "discover_lm_alignment": float(alignment_loss.detach().cpu().item()),
        }

    model.eval()
    with torch.no_grad():
        logits, fused, discover_hidden, lm_hidden, relation_attention, branch_attention, cross_attention_mean = model(x_struct, x_lm)
        probabilities = torch.sigmoid(logits).detach().cpu().numpy()
        relation_attention_map = {
            relation: round(float(relation_attention[index].detach().cpu().item()), 6)
            for index, relation in enumerate(relation_names)
        }
        branch_names = ("discover", "lm", "graph")
        branch_attention_map = {
            branch_names[index]: round(float(branch_attention[index].detach().cpu().item()), 6)
            for index in range(len(branch_names))
        }
        cross_attention_map = {
            "discover_to_lm": round(float(cross_attention_mean[0].detach().cpu().item()), 6),
            "lm_to_discover": round(float(cross_attention_mean[1].detach().cpu().item()), 6),
        }
        if edge_pair_tensor.numel():
            reconstruction_scores = torch.sigmoid(model.edge_logits(fused, edge_pair_tensor, edge_relation_tensor)).detach().cpu().numpy()
            reconstruction_labels = edge_labels.astype(float)
            reconstruction_metrics = _detection_metric_dict(reconstruction_labels.tolist(), reconstruction_scores.tolist())
        else:
            reconstruction_metrics = {}
    scores = np.zeros(y.size, dtype=float)
    scores[split.test] = probabilities[split.test]
    details = {
        "fusion_architecture": "iohunter_style_graph_foundation_lm_gnn",
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": cross_attention_map,
        "feature_group_sizes": {
            "discover": int(discover_feature_count),
            "lm": int(lm_feature_count),
        },
        "pretraining_objectives": {
            "supervised_node_classification": True,
            "edge_reconstruction_auxiliary": bool(edge_pair_tensor.numel()),
            "discover_lm_alignment_auxiliary": True,
        },
        "auxiliary_loss_weights": {
            "edge_reconstruction": 0.15,
            "discover_lm_alignment": 0.05,
        },
        "final_training_losses": {key: round(value, 6) for key, value in final_losses.items()},
        "edge_reconstruction_metrics": reconstruction_metrics,
        "edge_reconstruction_pair_count": int(edge_pair_tensor.shape[0]),
        "paper_reference_style": "IOHunter/SocGFM supervised-scarce-cross-IO LM+GNN detection",
    }
    backend = {
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": cross_attention_map,
        "edge_aux": bool(edge_pair_tensor.numel()),
    }
    return scores, f"gfm_lm_gnn_torch:{json.dumps(backend, sort_keys=True)}", details


def _cpu_light_gfm_lm_gnn_scores(
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    discover_feature_count: int,
    lm_feature_count: int,
    seed: int = 42,
    split: Split | None = None,
) -> tuple[np.ndarray, str, dict[str, object]]:
    if y.size == 0 or len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "gfm_lm_gnn_cpu_light_single_class", {}
    split = split or _make_split(y, seed=seed)
    if split.test.size == 0 or split.train.size == 0:
        return np.zeros(y.size, dtype=float), "gfm_lm_gnn_cpu_light_no_test_split", {}
    struct_matrix, lm_matrix = _split_detect_feature_groups(
        features,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
    )
    node_index = {str(node): index for index, node in enumerate(nodes)}
    relation_names = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0] or list(graphs) or ["empty_relation"]
    relation_outputs: list[np.ndarray] = []
    relation_strength: dict[str, float] = {}
    seed_matrix = np.concatenate([struct_matrix, lm_matrix], axis=1)
    for relation in relation_names:
        graph = graphs.get(relation, nx.Graph())
        aggregated = np.zeros_like(seed_matrix, dtype=float)
        degree = np.ones(len(nodes), dtype=float)
        left_indices: list[int] = []
        right_indices: list[int] = []
        weights: list[float] = []
        for source, target, attrs in graph.edges(data=True):
            if str(source) not in node_index or str(target) not in node_index:
                continue
            left = node_index[str(source)]
            right = node_index[str(target)]
            weight = max(float(attrs.get("weight", 1.0)), 1e-6)
            left_indices.append(left)
            right_indices.append(right)
            weights.append(weight)
        if left_indices:
            left_array = np.asarray(left_indices, dtype=np.int64)
            right_array = np.asarray(right_indices, dtype=np.int64)
            weight_array = np.asarray(weights, dtype=float)
            np.add.at(aggregated, left_array, seed_matrix[right_array] * weight_array[:, None])
            np.add.at(aggregated, right_array, seed_matrix[left_array] * weight_array[:, None])
            np.add.at(degree, left_array, weight_array)
            np.add.at(degree, right_array, weight_array)
        aggregated = aggregated / degree[:, None]
        relation_outputs.append(aggregated)
        relation_strength[relation] = float(np.mean(np.linalg.norm(aggregated, axis=1)))
    strengths = np.asarray([relation_strength.get(relation, 0.0) for relation in relation_names], dtype=float)
    if np.all(strengths <= 1e-12):
        relation_attention = np.ones(len(relation_names), dtype=float) / max(len(relation_names), 1)
    else:
        shifted = strengths - float(np.max(strengths))
        exp_values = np.exp(shifted)
        relation_attention = exp_values / float(np.sum(exp_values))
    graph_branch = np.zeros_like(seed_matrix, dtype=float)
    for index, relation_matrix in enumerate(relation_outputs):
        graph_branch += float(relation_attention[index]) * relation_matrix
    fused = np.concatenate([struct_matrix, lm_matrix, graph_branch], axis=1)
    scores = np.zeros(y.size, dtype=float)
    scores[split.test] = _fit_numpy_logistic(
        fused[split.train],
        y[split.train],
        fused[split.test],
        epochs=80,
        learning_rate=0.08,
    )
    backend = "gfm_lm_gnn_cpu_light_numpy_logistic"
    relation_attention_map = {
        relation: round(float(relation_attention[index]), 6)
        for index, relation in enumerate(relation_names)
    }
    details = {
        "fusion_architecture": "iohunter_style_cpu_light_fixed_graph_lm_gnn",
        "relation_attention": relation_attention_map,
        "branch_attention": {"discover": 0.333333, "lm": 0.333333, "graph": 0.333333},
        "feature_group_sizes": {
            "discover": int(discover_feature_count),
            "lm": int(lm_feature_count),
            "graph": int(graph_branch.shape[1]),
        },
        "pretraining_objectives": {
            "supervised_node_classification": True,
            "fixed_relation_graph_propagation": True,
            "edge_reconstruction_auxiliary": False,
            "discover_lm_alignment_auxiliary": False,
        },
        "paper_reference_style": "IOHunter/SocGFM-inspired CPU-light LM+GNN full-matrix smoke",
    }
    return scores, f"gfm_lm_gnn_cpu_light:{backend}:{json.dumps(relation_attention_map, sort_keys=True)}", details


def _prediction_rows_from_discover_features(
    nodes: Sequence[str],
    scores: np.ndarray,
    labels: Mapping[str, int],
    node_records: Mapping[str, Mapping[str, object]],
    split: Split | None = None,
) -> list[dict[str, object]]:
    train_nodes = {nodes[int(index)] for index in split.train.tolist()} if split is not None else set()
    test_nodes = {nodes[int(index)] for index in split.test.tolist()} if split is not None else set()
    rows = []
    for index, account_id in enumerate(nodes):
        node = node_records.get(account_id, {})
        score = float(scores[index]) if index < scores.size else 0.0
        evaluation_split = "test" if account_id in test_nodes else "train" if account_id in train_nodes else "unassigned"
        rows.append(
            {
                "account_id": account_id,
                "node_score": round(score, 6),
                "predicted_label": int(score >= 0.5),
                "label": int(labels.get(account_id, 0)),
                "evaluation_split": evaluation_split,
                "cluster_id": node.get("cluster_id"),
                "passed_structure_filter": bool(node.get("passed_structure_filter", False)),
                "structure_filter_score": node.get("structure_filter_score"),
                "directed_out_weight": node.get("directed_out_weight"),
                "directed_in_weight": node.get("directed_in_weight"),
            }
        )
    return sorted(rows, key=lambda row: (-float(row["node_score"]), row["account_id"]))


def _community_scores(result: Mapping[str, object], predictions: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    predictions_by_cluster: dict[object, list[Mapping[str, object]]] = defaultdict(list)
    for row in predictions:
        predictions_by_cluster[row.get("cluster_id")].append(row)
    output = []
    for community in result.get("communities", []):
        if not isinstance(community, Mapping):
            continue
        cluster_id = community.get("cluster_id")
        cluster_predictions = predictions_by_cluster.get(cluster_id, [])
        mean_score = (
            float(np.mean([float(row.get("node_score", 0.0)) for row in cluster_predictions]))
            if cluster_predictions
            else float(community.get("community_score", 0.0))
        )
        output.append(
            {
                "cluster_id": cluster_id,
                "community_score": round(mean_score, 6),
                "size": community.get("size"),
                "positive_prediction_count": int(sum(int(row.get("predicted_label", 0)) for row in cluster_predictions)),
                "top_objects": community.get("top_objects", []),
                "relation_breakdown": community.get("relation_breakdown", {}),
            }
        )
    return sorted(output, key=lambda row: (-float(row["community_score"]), row["cluster_id"]))


def _detect_discovery_snapshot(discovery: Mapping[str, object]) -> dict[str, object]:
    deep_model = (
        dict(discovery.get("deep_graph_model", {}))
        if isinstance(discovery.get("deep_graph_model"), Mapping)
        else {}
    )
    observed_edge_scores = deep_model.pop("observed_edge_scores", {})
    deep_model["observed_edge_score_count"] = (
        len(observed_edge_scores)
        if isinstance(observed_edge_scores, Mapping)
        else 0
    )
    return {
        "metrics": discovery["metrics"],
        "relation_attention": discovery["relation_attention"],
        "evidence_summary": discovery["evidence_summary"],
        "structure_filter": discovery.get("structure_filter", {}),
        # Full edge-score maps remain in cached discovery outputs. Detect keeps a
        # compact snapshot so batch runs do not duplicate multi-MB maps per split.
        "deep_graph_model": deep_model,
    }


def _comparison_rows_for_detect(result: Mapping[str, object]) -> list[dict[str, object]]:
    rows = []
    main_metric = result.get("metrics") if isinstance(result.get("metrics"), Mapping) else None
    _append_metric_row(
        rows,
        family="ours",
        method="dyna_colm_gnn:full",
        metric=main_metric,
        notes="detection",
    )
    ablations = result.get("ablations")
    if isinstance(ablations, Mapping):
        for variant, ablation in ablations.items():
            if isinstance(ablation, Mapping):
                _append_metric_row(
                    rows,
                    family="ours",
                    method=f"dyna_colm_gnn:{variant}",
                    metric=ablation.get("metrics") if isinstance(ablation.get("metrics"), Mapping) else None,
                    notes="ablation",
                )
    return rows


def run_dyna_colm_discover(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    encoder: str = STABLE_DISCOVER_ENCODER,
    community_algorithm: str = "leiden",
    epochs: int = 80,
    embedding_dim: int = 64,
    hidden_dim: int = 64,
    lr: float = 1e-3,
    negative_ratio: float = 1.0,
    device: str = "auto",
    structure_filter: str = "none",
    structure_filter_metric: str = "eigenvector",
    structure_filter_percentile: float = 90.0,
    structure_filter_use_weights: bool = False,
) -> dict[str, object]:
    # The default stays on the stable legacy MAGNN path after the newer
    # instance encoder regressed IOHunter reconstruction AUC/AP.
    if structure_filter not in DISCOVER_STRUCTURE_FILTERS:
        raise ValueError(
            f"Discover structure_filter must be one of: {', '.join(DISCOVER_STRUCTURE_FILTERS)}"
        )
    if structure_filter_metric not in DISCOVER_STRUCTURE_FILTER_METRICS:
        raise ValueError(
            f"Discover structure_filter_metric must be one of: {', '.join(DISCOVER_STRUCTURE_FILTER_METRICS)}"
        )
    if structure_filter != "none":
        # Backward-compatible argument acceptance only. Mainline Discover is
        # fixed to the MAGNN full-graph workflow, so pruning requests are
        # recorded in the output summary but ignored during execution.
        structure_filter = "node_pruning"
    config = DeepGraphDiscoverConfig(
        encoder=encoder,  # type: ignore[arg-type]
        embedding_dim=embedding_dim,
        hidden_dim=hidden_dim,
        epochs=epochs,
        lr=lr,
        negative_ratio=negative_ratio,
        device=device,
        seed=seed,
    )
    if encoder == "lightweight":
        result = _deep_discover_summary(
            events,
            relations=relations,
            seed=seed,
            config=config,
            community_algorithm=community_algorithm,
            structure_filter=structure_filter,
            structure_filter_metric=structure_filter_metric,
            structure_filter_percentile=structure_filter_percentile,
            structure_filter_use_weights=structure_filter_use_weights,
        )
    elif encoder in {"han_relation", "han", "magnn_legacy", "magnn", "amdn_hage"}:
        result = _deep_discover_summary(
            events,
            relations=relations,
            seed=seed,
            config=config,
            community_algorithm=community_algorithm,
            structure_filter=structure_filter,
            structure_filter_metric=structure_filter_metric,
            structure_filter_percentile=structure_filter_percentile,
            structure_filter_use_weights=structure_filter_use_weights,
        )
    else:
        raise ValueError("Discover encoder must be one of: lightweight, han_relation, han, magnn_legacy, magnn, amdn_hage")
    dynamic_edges = result.get("dynamic_edges", [])
    communities = []
    for community in result.get("communities", []):
        if not isinstance(community, Mapping):
            continue
        community_nodes = set(map(str, community.get("top_nodes", [])))
        record = dict(community)
        record["avg_time_delta"] = _community_avg_time_delta(dynamic_edges, community_nodes)
        communities.append(record)
    summary = {
        "setting": "discover",
        "task": "coordination_community_discovery",
        "method": "dyna_colm_discover",
        "relations": list(relations),
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": result.get("community_algorithm_effective"),
        "community_algorithm_backend": result.get("community_algorithm_backend"),
        "community_algorithm_fallback_reason": result.get("community_algorithm_fallback_reason"),
        "structure_filter": result.get("structure_filter", {}),
        "metrics": _discovery_metrics(result),
        "relation_attention": result.get("relation_attention", {}),
        "graph_metrics": result.get("graph_summary", {}),
        "dynamic_graph_metrics": result.get("dynamic_graph_summary", {}),
        "nodes": result.get("nodes", []),
        "edges": result.get("edges", []),
        "dynamic_edges": dynamic_edges,
        "communities": sorted(communities, key=lambda item: (-float(item.get("community_score", 0.0)), item.get("cluster_id"))),
        "evidence_summary": _evidence_summary(result),
        "deep_graph_model": result.get("deep_graph_model", {}),
        "model_governance": result.get("model_governance", _discover_encoder_governance(encoder)),
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "discovery_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return summary


def run_discover_stability_analysis(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    encoder: str = STABLE_DISCOVER_ENCODER,
    community_algorithm: str = "leiden",
    epochs: int = 20,
    embedding_dim: int = 32,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    negative_ratio: float = 1.0,
    device: str = "auto",
    window_sizes: Sequence[float] = (3600.0, 21600.0, 86400.0),
    min_events_per_window: int = 2,
) -> dict[str, object]:
    """Evaluate label-free Discover stability across time windows and scales."""
    events = _label_free_events(normalize_event_table(events))
    timestamp_values = events["timestamp"].map(_timestamp_to_float).astype(float).to_numpy()
    if timestamp_values.size == 0:
        raise ValueError("Stability analysis requires at least one event")
    min_time = float(np.min(timestamp_values))
    max_time = float(np.max(timestamp_values))
    windows: list[dict[str, object]] = []
    pairwise: list[dict[str, object]] = []
    window_cache: list[dict[str, object]] = []
    for window_size in [float(value) for value in window_sizes if float(value) > 0.0]:
        current = min_time
        scale_windows: list[dict[str, object]] = []
        window_index = 0
        while current <= max_time:
            end_time = current + window_size
            mask = (
                ((timestamp_values >= current) & (timestamp_values <= max_time))
                if end_time > max_time
                else ((timestamp_values >= current) & (timestamp_values < end_time))
            )
            window_events = events.loc[mask].copy()
            if len(window_events) >= int(min_events_per_window):
                window_output_dir = (
                    output_dir / "windows" / _safe_window_name(window_size, window_index)
                    if output_dir is not None
                    else None
                )
                summary = run_dyna_colm_discover(
                    window_events,
                    output_dir=window_output_dir,
                    relations=relations,
                    seed=seed,
                    encoder=encoder,
                    community_algorithm=community_algorithm,
                    epochs=epochs,
                    embedding_dim=embedding_dim,
                    hidden_dim=hidden_dim,
                    lr=lr,
                    negative_ratio=negative_ratio,
                    device=device,
                )
                row = _stability_window_row(
                    summary,
                    window_size=window_size,
                    window_index=window_index,
                    start_time=current,
                    end_time=min(end_time, max_time),
                    event_count=len(window_events),
                )
                record = {"row": row, "summary": summary}
                windows.append(row)
                scale_windows.append(record)
                window_cache.append(record)
            current = end_time
            window_index += 1
    for window_size in sorted({float(row["window_size_seconds"]) for row in windows}):
        scale_windows = [
            record
            for record in window_cache
            if float(record["row"]["window_size_seconds"]) == window_size
        ]
        pairwise.extend(_adjacent_window_stability(scale_windows, window_size=window_size))
    pairwise.extend(_multiscale_stability(window_cache))
    summary = {
        "setting": "discover",
        "task": "coordination_community_stability",
        "method": "dyna_colm_discover_stability",
        "encoder": encoder,
        "community_algorithm": community_algorithm,
        "window_sizes": [float(value) for value in window_sizes],
        "min_events_per_window": int(min_events_per_window),
        "window_count": len(windows),
        "pairwise_count": len(pairwise),
        "windows": windows,
        "pairwise_stability": pairwise,
        "summary": _stability_summary(windows, pairwise),
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_dict_rows(output_dir / "discover_stability_windows.csv", windows)
        _write_dict_rows(output_dir / "discover_stability_pairwise.csv", pairwise)
        _write_dict_rows(output_dir / "discover_stability_summary.csv", [summary["summary"]])
        (output_dir / "stability_manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return summary


def _safe_window_name(window_size: float, window_index: int) -> str:
    return f"w{int(round(window_size))}_idx{window_index}"


def _stability_window_row(
    summary: Mapping[str, object],
    *,
    window_size: float,
    window_index: int,
    start_time: float,
    end_time: float,
    event_count: int,
) -> dict[str, object]:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), Mapping) else {}
    graph_metrics = summary.get("graph_metrics") if isinstance(summary.get("graph_metrics"), Mapping) else {}
    return {
        "window_size_seconds": float(window_size),
        "window_index": int(window_index),
        "window_start": round(float(start_time), 6),
        "window_end": round(float(end_time), 6),
        "event_count": int(event_count),
        "node_count": graph_metrics.get("node_count"),
        "edge_count": graph_metrics.get("edge_count"),
        "cluster_count": metrics.get("cluster_count"),
        "largest_cluster_size": metrics.get("largest_cluster_size"),
        "modularity": metrics.get("modularity"),
        "conductance": metrics.get("conductance"),
        "density": metrics.get("density"),
        "mean_object_concentration": metrics.get("mean_object_concentration"),
        "relation_entropy": metrics.get("relation_entropy"),
        "community_algorithm": summary.get("community_algorithm"),
        "community_algorithm_effective": summary.get("community_algorithm_effective"),
    }


def _adjacent_window_stability(
    scale_windows: Sequence[Mapping[str, object]],
    *,
    window_size: float,
) -> list[dict[str, object]]:
    rows = []
    for left, right in zip(scale_windows, scale_windows[1:]):
        left_row = left.get("row") if isinstance(left.get("row"), Mapping) else {}
        right_row = right.get("row") if isinstance(right.get("row"), Mapping) else {}
        rows.append(
            {
                **_community_assignment_stability(
                    left.get("summary") if isinstance(left.get("summary"), Mapping) else {},
                    right.get("summary") if isinstance(right.get("summary"), Mapping) else {},
                ),
                "comparison_type": "adjacent_time_windows",
                "left_window_size_seconds": float(window_size),
                "right_window_size_seconds": float(window_size),
                "left_window_index": left_row.get("window_index"),
                "right_window_index": right_row.get("window_index"),
            }
        )
    return rows


def _multiscale_stability(window_cache: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for record in window_cache:
        row = record.get("row") if isinstance(record.get("row"), Mapping) else {}
        grouped[int(row.get("window_index", 0))].append(record)
    rows = []
    for window_index, group in grouped.items():
        sorted_group = sorted(
            group,
            key=lambda item: float(item.get("row", {}).get("window_size_seconds", 0.0))
            if isinstance(item.get("row"), Mapping)
            else 0.0,
        )
        for left, right in zip(sorted_group, sorted_group[1:]):
            left_row = left.get("row") if isinstance(left.get("row"), Mapping) else {}
            right_row = right.get("row") if isinstance(right.get("row"), Mapping) else {}
            rows.append(
                {
                    **_community_assignment_stability(
                        left.get("summary") if isinstance(left.get("summary"), Mapping) else {},
                        right.get("summary") if isinstance(right.get("summary"), Mapping) else {},
                    ),
                    "comparison_type": "multiscale_same_index",
                    "left_window_size_seconds": left_row.get("window_size_seconds"),
                    "right_window_size_seconds": right_row.get("window_size_seconds"),
                    "left_window_index": window_index,
                    "right_window_index": window_index,
                }
            )
    return rows


def _community_assignment_stability(
    left_summary: Mapping[str, object],
    right_summary: Mapping[str, object],
) -> dict[str, object]:
    left_assignment = _cluster_assignment(left_summary)
    right_assignment = _cluster_assignment(right_summary)
    common_nodes = sorted(set(left_assignment).intersection(right_assignment))
    if not common_nodes:
        return {"nmi": None, "ari": None, "jaccard": None, "common_node_count": 0}
    left_labels = [left_assignment[node] for node in common_nodes]
    right_labels = [right_assignment[node] for node in common_nodes]
    return {
        "nmi": _normalized_mutual_info(left_labels, right_labels),
        "ari": _adjusted_rand_index(left_labels, right_labels),
        "jaccard": _assignment_pair_jaccard(left_assignment, right_assignment, common_nodes),
        "common_node_count": len(common_nodes),
    }


def _cluster_assignment(summary: Mapping[str, object]) -> dict[str, int]:
    assignment: dict[str, int] = {}
    nodes = summary.get("nodes") if isinstance(summary.get("nodes"), Sequence) else []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        account_id = str(node.get("account_id", ""))
        if not account_id:
            continue
        cluster_id = node.get("cluster_id")
        assignment[account_id] = int(cluster_id) if cluster_id is not None else -1
    return assignment


def _normalized_mutual_info(left_labels: Sequence[int], right_labels: Sequence[int]) -> float | None:
    try:
        from sklearn.metrics import normalized_mutual_info_score

        return round(float(normalized_mutual_info_score(left_labels, right_labels)), 6)
    except Exception:
        return _normalized_mutual_info_fallback(left_labels, right_labels)


def _adjusted_rand_index(left_labels: Sequence[int], right_labels: Sequence[int]) -> float | None:
    try:
        from sklearn.metrics import adjusted_rand_score

        return round(float(adjusted_rand_score(left_labels, right_labels)), 6)
    except Exception:
        return _adjusted_rand_index_fallback(left_labels, right_labels)


def _normalized_mutual_info_fallback(left_labels: Sequence[int], right_labels: Sequence[int]) -> float | None:
    if len(left_labels) != len(right_labels) or not left_labels:
        return None
    n = float(len(left_labels))
    left_counts = Counter(left_labels)
    right_counts = Counter(right_labels)
    joint_counts = Counter(zip(left_labels, right_labels))
    mutual_info = 0.0
    for (left, right), count in joint_counts.items():
        if count <= 0:
            continue
        mutual_info += (count / n) * math.log((count * n) / (left_counts[left] * right_counts[right]))
    left_entropy = -sum((count / n) * math.log(count / n) for count in left_counts.values() if count)
    right_entropy = -sum((count / n) * math.log(count / n) for count in right_counts.values() if count)
    denominator = (left_entropy + right_entropy) / 2.0
    if denominator <= 1e-12:
        return 1.0
    return round(float(mutual_info / denominator), 6)


def _adjusted_rand_index_fallback(left_labels: Sequence[int], right_labels: Sequence[int]) -> float | None:
    if len(left_labels) != len(right_labels) or not left_labels:
        return None
    n = len(left_labels)
    if n < 2:
        return 1.0
    left_counts = Counter(left_labels)
    right_counts = Counter(right_labels)
    joint_counts = Counter(zip(left_labels, right_labels))

    def comb2(value: int) -> float:
        return float(value * (value - 1) / 2)

    sum_comb_joint = sum(comb2(count) for count in joint_counts.values())
    sum_comb_left = sum(comb2(count) for count in left_counts.values())
    sum_comb_right = sum(comb2(count) for count in right_counts.values())
    total_pairs = comb2(n)
    if total_pairs <= 0:
        return 1.0
    expected_index = (sum_comb_left * sum_comb_right) / total_pairs
    max_index = 0.5 * (sum_comb_left + sum_comb_right)
    denominator = max_index - expected_index
    if abs(denominator) <= 1e-12:
        return 1.0
    return round(float((sum_comb_joint - expected_index) / denominator), 6)


def _assignment_pair_jaccard(
    left_assignment: Mapping[str, int],
    right_assignment: Mapping[str, int],
    common_nodes: Sequence[str],
) -> float:
    left_pairs = _co_cluster_pairs(left_assignment, common_nodes)
    right_pairs = _co_cluster_pairs(right_assignment, common_nodes)
    union = left_pairs.union(right_pairs)
    if not union:
        return 1.0
    return round(float(len(left_pairs.intersection(right_pairs)) / len(union)), 6)


def _co_cluster_pairs(assignment: Mapping[str, int], nodes: Sequence[str]) -> set[tuple[str, str]]:
    clusters: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        clusters[int(assignment[node])].append(node)
    pairs: set[tuple[str, str]] = set()
    for members in clusters.values():
        members = sorted(members)
        for index, source in enumerate(members):
            for target in members[index + 1 :]:
                pairs.add((source, target))
    return pairs


def _stability_summary(
    windows: Sequence[Mapping[str, object]],
    pairwise: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    adjacent = [row for row in pairwise if row.get("comparison_type") == "adjacent_time_windows"]
    return {
        "window_count": len(windows),
        "pairwise_count": len(pairwise),
        "mean_modularity": _mean_optional(row.get("modularity") for row in windows),
        "mean_conductance": _mean_optional(row.get("conductance") for row in windows),
        "mean_object_concentration": _mean_optional(row.get("mean_object_concentration") for row in windows),
        "mean_adjacent_nmi": _mean_optional(row.get("nmi") for row in adjacent),
        "mean_adjacent_ari": _mean_optional(row.get("ari") for row in adjacent),
        "mean_adjacent_jaccard": _mean_optional(row.get("jaccard") for row in adjacent),
    }


def _mean_optional(values: Iterable[object]) -> float | None:
    numeric = []
    for value in values:
        if value in {None, ""}:
            continue
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    return round(float(np.mean(numeric)), 6) if numeric else None


def _write_dict_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as file_handle:
        if not fields:
            return
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_dyna_colm_ablation_suite(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, dict[str, object]]:
    return run_dyna_colm_gnn_ablations(events, relations=relations, seed=seed)


def run_dyna_colm_detect(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    discover_encoder: str = STABLE_DISCOVER_ENCODER,
    discover_epochs: int = 20,
    embedding_dim: int = 32,
    hidden_dim: int = 32,
    device: str = "auto",
    lm_backend: str = "sbert",
    gnn_backend: str = "gfm_lm_gnn",
    detect_epochs: int | None = None,
    split_mode: str = "supervised",
    precomputed_discovery: Mapping[str, object] | None = None,
    include_diagnostics: bool = True,
    lm_cache_dir: Path | None = None,
) -> dict[str, object]:
    labels = extract_labels(events)
    if not labels or len(set(labels.values())) < 2:
        raise ValueError("DynaCoLM-Detect requires at least two label classes")
    discovery = (
        dict(precomputed_discovery)
        if precomputed_discovery is not None
        else run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder=discover_encoder,
            epochs=discover_epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
        )
    )
    nodes, discover_features, y, node_records = _discover_node_feature_table(discovery, labels)
    lm_features, lm_feature_source = _lm_feature_matrix(
        events,
        nodes,
        backend=lm_backend,
        max_dim=max(8, embedding_dim),
        cache_dir=lm_cache_dir,
    )
    discover_feature_count = int(discover_features.shape[1]) if discover_features.ndim == 2 else 0
    lm_feature_count = int(lm_features.shape[1]) if lm_features.ndim == 2 else 0
    discover_embedding_dim = _discover_embedding_dim(discovery)
    features = np.concatenate([discover_features, lm_features], axis=1)
    for column in range(features.shape[1]):
        features[:, column] = _normalize_vector(features[:, column])
    split, split_detail = _split_for_detect(events, nodes, y, split_mode=split_mode, seed=seed)
    reweighted_edge_count = 0
    uses_discover_reweighted_edges = False
    fusion_details: dict[str, object] = {}
    if gnn_backend in {"relation_gnn", "fusion_gnn", "gfm_lm_gnn", "gfm_lm_gnn_cpu_light"}:
        graphs = build_unmasking_similarity_graphs(_label_free_events(events), relations=relations, include_text_similarity=False)
        graphs, reweighted_edge_count = _apply_discover_edge_scores_to_relation_graphs(graphs, discovery)
        uses_discover_reweighted_edges = reweighted_edge_count > 0
        for graph in graphs.values():
            graph.add_nodes_from(nodes)
        supervised_epochs = max(1, int(detect_epochs)) if detect_epochs is not None else max(20, int(discover_epochs) * 5)
        if gnn_backend == "gfm_lm_gnn_cpu_light":
            scores, classifier_backend, fusion_details = _cpu_light_gfm_lm_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=discover_feature_count,
                lm_feature_count=lm_feature_count,
                seed=seed,
                split=split,
            )
        elif gnn_backend == "gfm_lm_gnn":
            scores, classifier_backend, fusion_details = _torch_gfm_lm_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=discover_feature_count,
                lm_feature_count=lm_feature_count,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
        elif gnn_backend == "fusion_gnn":
            scores, classifier_backend, fusion_details = _torch_fusion_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=discover_feature_count,
                lm_feature_count=lm_feature_count,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
        else:
            scores, classifier_backend, fusion_details = _torch_relation_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
    else:
        scores, classifier_backend = _fit_transductive_scores_with_split(features, y, seed=seed, split=split)
    predictions = _prediction_rows_from_discover_features(nodes, scores, labels, node_records, split=split)
    test_predictions = [row for row in predictions if row.get("evaluation_split") == "test"]
    test_y_true = [int(row["label"]) for row in test_predictions]
    test_y_score = [float(row["node_score"]) for row in test_predictions]
    all_y_true = [int(row["label"]) for row in predictions]
    all_y_score = [float(row["node_score"]) for row in predictions]
    # Paper-facing Detect metrics are held-out only. The all-node version is
    # retained for audits because train rows still receive diagnostic scores.
    metrics = _detection_metric_dict(test_y_true, test_y_score) if test_predictions else {}
    metrics["amdn_hage_style"] = _amdn_hage_style_metrics(test_y_true, test_y_score) if test_predictions else {}
    all_node_metrics = _detection_metric_dict(all_y_true, all_y_score)
    all_node_metrics["amdn_hage_style"] = _amdn_hage_style_metrics(all_y_true, all_y_score)
    legacy_full: dict[str, object] = {}
    ablations: dict[str, dict[str, object]] = {}
    if include_diagnostics:
        legacy_full = run_dyna_colm_gnn_prototype(events, relations=relations, seed=seed, variant="legacy_detect")
        ablations = run_dyna_colm_ablation_suite(events, relations=relations, seed=seed)
        for ablation in ablations.values():
            ablation_predictions = _prediction_rows(ablation, labels)
            ablation["metrics"] = _detection_metric_dict(
                [int(row["label"]) for row in ablation_predictions],
                [float(row["node_score"]) for row in ablation_predictions],
            )
    summary = {
        "setting": "detect",
        "task": "coordination_discrimination",
        "method": "dyna_colm_detect",
        "relations": list(relations),
        "detect_model": {
            "uses_discover_outputs": True,
            "discover_encoder": discover_encoder,
            "model_governance": _discover_encoder_governance(discover_encoder),
            "discover_epochs": discover_epochs,
            "detect_epochs": detect_epochs if detect_epochs is not None else max(20, int(discover_epochs) * 5),
            "lm_backend": lm_backend,
            "lm_feature_source": lm_feature_source,
            "gnn_backend": gnn_backend,
            "split_mode": split_mode,
            "split_detail": split_detail,
            "train_count": int(split.train.size),
            "test_count": int(split.test.size),
            "evaluation_protocol": "heldout_test_only",
            "feature_count": int(features.shape[1]) if features.ndim == 2 else 0,
            "discover_feature_count": discover_feature_count,
            "lm_feature_count": lm_feature_count,
            "discover_embedding_dim": discover_embedding_dim,
            "classifier_backend": classifier_backend,
            "uses_community_features": True,
            "uses_dynamic_features": True,
            "uses_metapath_instance_features": True,
            "uses_full_discover_embeddings": discover_embedding_dim > 0,
            "uses_discover_reweighted_edges": uses_discover_reweighted_edges,
            "reweighted_edge_count": int(reweighted_edge_count),
            "edge_score_source": (
                discovery.get("deep_graph_model", {}).get("edge_score_source")
                if isinstance(discovery.get("deep_graph_model"), Mapping)
                else None
            ),
            "uses_lm_features": True,
            "uses_precomputed_discovery": precomputed_discovery is not None,
            "uses_lm_disk_cache": lm_cache_dir is not None,
            "include_diagnostics": include_diagnostics,
            "fusion_details": fusion_details,
        },
        "metrics": metrics,
        "all_node_metrics": all_node_metrics,
        "predictions": predictions,
        "node_scores": {row["account_id"]: row["node_score"] for row in predictions},
        "community_scores": _community_scores(discovery, predictions),
        "discovery": _detect_discovery_snapshot(discovery),
        "legacy_prototype": (
            {
                "method": legacy_full.get("method"),
                "variant": legacy_full.get("variant"),
                "metrics": legacy_full.get("metrics"),
                "classifier_backend": legacy_full.get("classifier_backend"),
            }
            if include_diagnostics
            else {}
        ),
        "ablations": (
            {
                variant: {
                    "method": result.get("method"),
                    "variant": result.get("variant"),
                    "metrics": result.get("metrics"),
                    "uses_lm_features": result.get("uses_lm_features"),
                    "uses_gnn_message_passing": result.get("uses_gnn_message_passing"),
                    "uses_direction_time_features": result.get("uses_direction_time_features"),
                    "uses_relation_attention": result.get("uses_relation_attention"),
                    "relation_attention_mode": result.get("relation_attention_mode"),
                    "uses_community_features": result.get("uses_community_features"),
                    "relation_attention": result.get("relation_attention"),
                }
                for variant, result in ablations.items()
            }
            if include_diagnostics
            else {}
        ),
    }
    summary["characterization"] = characterize_detect_output(
        events=events,
        discovery=discovery,
        predictions=predictions,
        config=CharacterizationConfig(
            include_risk_report=include_diagnostics,
            include_observer_lens=True,
            observer_lens="network_security",
        ),
    )
    summary["comparison_rows"] = _comparison_rows_for_detect(summary)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "detection_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fields = (
            "account_id",
            "label",
            "evaluation_split",
            "predicted_label",
            "node_score",
            "cluster_id",
            "directed_out_weight",
            "directed_in_weight",
        )
        with (output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=fields)
            writer.writeheader()
            for row in predictions:
                writer.writerow({field: row.get(field) for field in fields})
    return summary


def run_dyna_colm_detect_from_prepared(
    events: pd.DataFrame,
    prepared: PreparedDetectInputs,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    discover_encoder: str = STABLE_DISCOVER_ENCODER,
    discover_epochs: int = 20,
    hidden_dim: int = 32,
    device: str = "auto",
    lm_backend: str = "sbert",
    gnn_backend: str = "gfm_lm_gnn",
    detect_epochs: int | None = None,
    split_mode: str = "supervised",
    uses_precomputed_discovery: bool = False,
    include_diagnostics: bool = True,
    include_characterization: bool = True,
    include_community_scores: bool = True,
    compact_summary: bool = False,
    uses_lm_disk_cache: bool = False,
) -> dict[str, object]:
    discovery = prepared.discovery
    labels = prepared.labels
    nodes = prepared.nodes
    features = prepared.features
    y = prepared.y
    node_records = prepared.node_records
    split, split_detail = _split_for_detect(events, nodes, y, split_mode=split_mode, seed=seed)
    fusion_details: dict[str, object] = {}
    if gnn_backend in {"relation_gnn", "fusion_gnn", "gfm_lm_gnn", "gfm_lm_gnn_cpu_light"}:
        graphs = prepared.graphs
        supervised_epochs = max(1, int(detect_epochs)) if detect_epochs is not None else max(20, int(discover_epochs) * 5)
        if gnn_backend == "gfm_lm_gnn_cpu_light":
            scores, classifier_backend, fusion_details = _cpu_light_gfm_lm_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=prepared.discover_feature_count,
                lm_feature_count=prepared.lm_feature_count,
                seed=seed,
                split=split,
            )
        elif gnn_backend == "gfm_lm_gnn":
            scores, classifier_backend, fusion_details = _torch_gfm_lm_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=prepared.discover_feature_count,
                lm_feature_count=prepared.lm_feature_count,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
        elif gnn_backend == "fusion_gnn":
            scores, classifier_backend, fusion_details = _torch_fusion_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=prepared.discover_feature_count,
                lm_feature_count=prepared.lm_feature_count,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
        else:
            scores, classifier_backend, fusion_details = _torch_relation_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
    else:
        scores, classifier_backend = _fit_transductive_scores_with_split(features, y, seed=seed, split=split)
    predictions = _prediction_rows_from_discover_features(nodes, scores, labels, node_records, split=split)
    test_predictions = [row for row in predictions if row.get("evaluation_split") == "test"]
    test_y_true = [int(row["label"]) for row in test_predictions]
    test_y_score = [float(row["node_score"]) for row in test_predictions]
    all_y_true = [int(row["label"]) for row in predictions]
    all_y_score = [float(row["node_score"]) for row in predictions]
    metrics = _detection_metric_dict(test_y_true, test_y_score) if test_predictions else {}
    metrics["amdn_hage_style"] = _amdn_hage_style_metrics(test_y_true, test_y_score) if test_predictions else {}
    all_node_metrics = _detection_metric_dict(all_y_true, all_y_score)
    all_node_metrics["amdn_hage_style"] = _amdn_hage_style_metrics(all_y_true, all_y_score)
    legacy_full: dict[str, object] = {}
    ablations: dict[str, dict[str, object]] = {}
    if include_diagnostics:
        legacy_full = run_dyna_colm_gnn_prototype(events, relations=relations, seed=seed, variant="legacy_detect")
        ablations = run_dyna_colm_ablation_suite(events, relations=relations, seed=seed)
        for ablation in ablations.values():
            ablation_predictions = _prediction_rows(ablation, labels)
            ablation["metrics"] = _detection_metric_dict(
                [int(row["label"]) for row in ablation_predictions],
                [float(row["node_score"]) for row in ablation_predictions],
            )
    summary = {
        "setting": "detect",
        "task": "coordination_discrimination",
        "method": "dyna_colm_detect",
        "relations": list(relations),
        "detect_model": {
            "uses_discover_outputs": True,
            "discover_encoder": discover_encoder,
            "model_governance": _discover_encoder_governance(discover_encoder),
            "discover_epochs": discover_epochs,
            "detect_epochs": detect_epochs if detect_epochs is not None else max(20, int(discover_epochs) * 5),
            "lm_backend": lm_backend,
            "lm_feature_source": prepared.lm_feature_source,
            "gnn_backend": gnn_backend,
            "split_mode": split_mode,
            "split_detail": split_detail,
            "train_count": int(split.train.size),
            "test_count": int(split.test.size),
            "evaluation_protocol": "heldout_test_only",
            "feature_count": int(features.shape[1]) if features.ndim == 2 else 0,
            "discover_feature_count": prepared.discover_feature_count,
            "lm_feature_count": prepared.lm_feature_count,
            "discover_embedding_dim": prepared.discover_embedding_dim,
            "classifier_backend": classifier_backend,
            "uses_community_features": True,
            "uses_dynamic_features": True,
            "uses_metapath_instance_features": True,
            "uses_full_discover_embeddings": prepared.discover_embedding_dim > 0,
            "uses_discover_reweighted_edges": prepared.uses_discover_reweighted_edges,
            "reweighted_edge_count": int(prepared.reweighted_edge_count),
            "edge_score_source": (
                discovery.get("deep_graph_model", {}).get("edge_score_source")
                if isinstance(discovery.get("deep_graph_model"), Mapping)
                else None
            ),
            "uses_lm_features": True,
            "uses_precomputed_discovery": uses_precomputed_discovery,
            "uses_lm_disk_cache": uses_lm_disk_cache,
            "uses_prepared_detect_inputs": True,
            "include_diagnostics": include_diagnostics,
            "include_characterization": include_characterization,
            "include_community_scores": include_community_scores,
            "compact_summary": compact_summary,
            "fusion_details": fusion_details,
        },
        "metrics": metrics,
        "all_node_metrics": all_node_metrics,
        "predictions": predictions,
        "node_scores": {row["account_id"]: row["node_score"] for row in predictions},
        "community_scores": _community_scores(discovery, predictions) if include_community_scores else [],
        "discovery": _detect_discovery_snapshot(discovery),
        "legacy_prototype": (
            {
                "method": legacy_full.get("method"),
                "variant": legacy_full.get("variant"),
                "metrics": legacy_full.get("metrics"),
                "classifier_backend": legacy_full.get("classifier_backend"),
            }
            if include_diagnostics
            else {}
        ),
        "ablations": (
            {
                variant: {
                    "method": result.get("method"),
                    "variant": result.get("variant"),
                    "metrics": result.get("metrics"),
                    "uses_lm_features": result.get("uses_lm_features"),
                    "uses_gnn_message_passing": result.get("uses_gnn_message_passing"),
                    "uses_direction_time_features": result.get("uses_direction_time_features"),
                    "uses_relation_attention": result.get("uses_relation_attention"),
                    "relation_attention_mode": result.get("relation_attention_mode"),
                    "uses_community_features": result.get("uses_community_features"),
                    "relation_attention": result.get("relation_attention"),
                }
                for variant, result in ablations.items()
            }
            if include_diagnostics
            else {}
        ),
    }
    if include_characterization:
        summary["characterization"] = characterize_detect_output(
            events=events,
            discovery=discovery,
            predictions=predictions,
            config=CharacterizationConfig(
                include_risk_report=include_diagnostics,
                include_observer_lens=True,
                observer_lens="network_security",
            ),
        )
    else:
        summary["characterization"] = {
            "task": "coordination_characterization",
            "method": "skipped_for_detect_only_batch",
            "communities": [],
            "summary": {
                "community_count": 0,
                "skip_reason": "CoordinationDiscover Detect acceptance reports held-out detection metrics; PropagationAnalysis handles heavy characterization.",
            },
        }
    summary["comparison_rows"] = _comparison_rows_for_detect(summary)
    prediction_rows_for_file = predictions
    if compact_summary:
        summary["prediction_count"] = len(predictions)
        summary["node_score_count"] = len(summary.get("node_scores", {}))
        summary["community_score_count"] = len(summary.get("community_scores", []))
        summary["compact_artifacts"] = {
            "predictions_csv": "predictions.csv",
            "omitted_from_json": ["predictions", "node_scores", "community_scores"],
        }
        summary["predictions"] = []
        summary["node_scores"] = {}
        summary["community_scores"] = []
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "detection_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fields = (
            "account_id",
            "label",
            "evaluation_split",
            "predicted_label",
            "node_score",
            "cluster_id",
            "directed_out_weight",
            "directed_in_weight",
        )
        with (output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=fields)
            writer.writeheader()
            for row in prediction_rows_for_file:
                writer.writerow({field: row.get(field) for field in fields})
    return summary


def run_setting_a_discovery(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, object]:
    return run_dyna_colm_discover(events, output_dir=output_dir, relations=relations, seed=seed)


def run_setting_ablation_suite(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, dict[str, object]]:
    return run_dyna_colm_ablation_suite(events, relations=relations, seed=seed)


def run_setting_b_detection(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, object]:
    return run_dyna_colm_detect(events, output_dir=output_dir, relations=relations, seed=seed)


def run_dyna_colm_characterize(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    detect_result: Mapping[str, object] | None = None,
    include_risk_report: bool = True,
    observer_lens: str = "network_security",
) -> dict[str, object]:
    detect_summary = (
        dict(detect_result)
        if detect_result is not None
        else run_dyna_colm_detect(
            events,
            output_dir=output_dir,
            relations=relations,
            seed=seed,
        )
    )
    existing = detect_summary.get("characterization")
    if isinstance(existing, Mapping) and existing.get("communities"):
        characterization = dict(existing)
    else:
        full_discovery = detect_summary.get("_full_discovery_for_characterization")
        if not isinstance(full_discovery, Mapping):
            full_discovery = run_dyna_colm_discover(
                events,
                output_dir=None,
                relations=relations,
                seed=seed,
            )
        characterization = characterize_detect_output(
            events=events,
            discovery=full_discovery,
            predictions=detect_summary.get("predictions", []),
            config=CharacterizationConfig(
                include_risk_report=include_risk_report,
                include_observer_lens=True,
                observer_lens=observer_lens,
            ),
        )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "characterization_summary.json").write_text(
            json.dumps(characterization, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return characterization


def _iohunter_repo_dir(workspace: Path) -> Path:
    return workspace / "SocGFM"


def _iohunter_src_dir(workspace: Path) -> Path:
    return _iohunter_repo_dir(workspace) / "src"


def _iohunter_workspace_data_root(workspace: Path) -> Path:
    return workspace / "data" / "processed"


def _iohunter_official_data_root(workspace: Path) -> Path:
    return _iohunter_repo_dir(workspace) / "data" / "processed"


def _iohunter_effective_data_root(workspace: Path) -> Path:
    official_root = _iohunter_official_data_root(workspace)
    if official_root.exists():
        return official_root
    return _iohunter_workspace_data_root(workspace)


def ensure_iohunter_official_data_layout(workspace: Path) -> dict[str, object]:
    """Expose downloaded Zenodo data at the path expected by official IOHunter scripts."""
    source = _iohunter_workspace_data_root(workspace)
    target = _iohunter_official_data_root(workspace)
    actions: list[str] = []
    if target.exists():
        return {
            "source": str(source),
            "target": str(target),
            "ready": True,
            "actions": ["official_data_layout_exists"],
        }
    if not source.exists():
        return {
            "source": str(source),
            "target": str(target),
            "ready": False,
            "actions": ["workspace_data_missing"],
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(source, target, target_is_directory=True)
        actions.append("created_directory_symlink")
    except (NotImplementedError, OSError) as exc:
        actions.append(f"directory_symlink_failed:{type(exc).__name__}:{exc}")
        if os.name == "nt":
            process = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                text=True,
                capture_output=True,
                check=False,
            )
            if process.returncode == 0:
                actions.append("created_windows_junction")
            else:
                stderr = process.stderr.strip() or process.stdout.strip()
                actions.append(f"windows_junction_failed:{process.returncode}:{stderr}")
    return {
        "source": str(source),
        "target": str(target),
        "ready": target.exists(),
        "actions": actions,
    }


def patch_iohunter_official_scripts(workspace: Path) -> dict[str, object]:
    """Apply small reproducibility patches to the local official IOHunter clone."""
    actions: list[str] = []
    node_pruning = _iohunter_script_path(workspace, "run_NodePruning.py")
    node2vec = _iohunter_script_path(workspace, "run_Node2Vec.py")

    if node_pruning.exists():
        text = node_pruning.read_text(encoding="utf-8")
        if "return interim_data_dir" in text:
            actions.append("nodepruning_return_already_present")
        else:
            old = "    save_metrics(val_logger, interim_data_dir, 'VAL')\n    save_metrics(test_logger, interim_data_dir, 'TEST')\n"
            new = old + "    return interim_data_dir\n"
            if old in text:
                node_pruning.write_text(text.replace(old, new, 1), encoding="utf-8")
                actions.append("nodepruning_return_added")
            else:
                actions.append("nodepruning_return_anchor_missing")
    else:
        actions.append("nodepruning_script_missing")

    if node2vec.exists():
        text = node2vec.read_text(encoding="utf-8")
        changed = False
        if "import sys\n" in text:
            actions.append("node2vec_sys_import_already_present")
        elif "import os\nimport torch" in text:
            text = text.replace("import os\nimport torch", "import os\nimport sys\nimport torch", 1)
            changed = True
            actions.append("node2vec_sys_import_added")
        else:
            actions.append("node2vec_sys_import_anchor_missing")

        if 'sys.platform.startswith("win")' in text:
            actions.append("node2vec_windows_loader_already_present")
        else:
            old = "        num_workers = 4\n        loader = model.loader(batch_size=128, shuffle=True, num_workers=num_workers)\n"
            new = (
                "        # Windows spawn cannot pickle PyG's Node2Vec sampler capsule; use a\n"
                "        # single-process loader there while preserving the official method.\n"
                '        num_workers = 0 if sys.platform.startswith("win") else 4\n'
                "        loader = model.loader(batch_size=128, shuffle=True, num_workers=num_workers)\n"
            )
            if old in text:
                text = text.replace(old, new, 1)
                changed = True
                actions.append("node2vec_windows_loader_added")
            else:
                actions.append("node2vec_loader_anchor_missing")

        if "return interim_data_dir" in text:
            actions.append("node2vec_return_already_present")
        else:
            old = "    save_metrics(val_logger, interim_data_dir, 'VAL')\n    save_metrics(test_logger, interim_data_dir, 'TEST')\n"
            new = old + "    return interim_data_dir\n"
            if old in text:
                text = text.replace(old, new, 1)
                changed = True
                actions.append("node2vec_return_added")
            else:
                actions.append("node2vec_return_anchor_missing")

        if changed:
            node2vec.write_text(text, encoding="utf-8")
    else:
        actions.append("node2vec_script_missing")

    return {
        "workspace": str(workspace),
        "actions": actions,
        "ready": not any(action.endswith("_missing") for action in actions),
    }


def _iohunter_script_path(workspace: Path, script_name: str) -> Path:
    repo_dir = _iohunter_repo_dir(workspace)
    candidates = (repo_dir / "src" / script_name, repo_dir / script_name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _quote_ps(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _iohunter_run_command(cwd: Path, script: Path, args: Sequence[str]) -> str:
    quoted_args = [str(item) if re.fullmatch(r"[A-Za-z0-9_.:/+-]+", str(item)) else _quote_ps(str(item)) for item in args]
    return " ".join(
        [
            "Set-Location",
            "-LiteralPath",
            _quote_ps(str(cwd)),
            ";",
            "python",
            _quote_ps(f".\\{script.name}"),
            *quoted_args,
        ]
    )


def _iohunter_shell_command(cwd: Path, script: Path, args: Sequence[str]) -> str:
    quoted_args = [shlex.quote(str(item)) for item in args]
    return " ".join(["cd", shlex.quote(str(cwd)), "&&", "python", shlex.quote(script.name), *quoted_args])


def build_iohunter_run_plan(
    workspace: Path,
    *,
    datasets: Sequence[str] = IOHUNTER_DATASETS,
    seeds: Sequence[int] = (42, 43, 44, 45, 46),
    gnns: Sequence[str] = ("sage",),
    learning_rates: Sequence[float] = (1e-2,),
    early: int = 30,
    splits: int = 5,
    device: str = "0",
    epochs: int | None = None,
    check: int | None = None,
    latent: int | None = None,
    embed_type: str | None = None,
    undersampling: Sequence[float | str | None] = (None,),
    include_primary: bool = True,
    include_official_baselines: bool = True,
    include_cross_country: bool = False,
) -> list[dict[str, object]]:
    """Build executable IOHunter commands with the correct official working directory."""
    src_dir = _iohunter_src_dir(workspace)
    plan: list[dict[str, object]] = []
    if include_primary:
        for dataset in datasets:
            for gnn in gnns:
                for learning_rate in learning_rates:
                    for seed in seeds:
                        for under in undersampling:
                            script = _iohunter_script_path(workspace, IOHUNTER_PRIMARY_SCRIPT)
                            args = [
                                "--dataset",
                                dataset,
                                "--lr",
                                f"{learning_rate:g}",
                                "--early",
                                str(early),
                                "--gnn",
                                gnn,
                                "--seed",
                                str(seed),
                                "--splits",
                                str(splits),
                                "--device",
                                device,
                            ]
                            if epochs is not None:
                                args.extend(["--epochs", str(epochs)])
                            if check is not None:
                                args.extend(["--check", str(check)])
                            if latent is not None:
                                args.extend(["--latent", str(latent)])
                            if embed_type is not None:
                                args.extend(["--embed_type", embed_type])
                            setting = "supervised" if under is None else "scarce_supervised"
                            if under is not None:
                                args.extend(["--under", str(under)])
                            command = _iohunter_run_command(src_dir, script, args)
                            shell_command = _iohunter_shell_command(src_dir, script, args)
                            plan.append(
                                {
                                    "family": "iohunter",
                                    "method": "MultiModalGNN_CrossAttention",
                                    "setting": setting,
                                    "dataset": dataset,
                                    "seed": seed,
                                    "gnn": gnn,
                                    "lr": learning_rate,
                                    "early": early,
                                    "splits": splits,
                                    "epochs": epochs,
                                    "check": check,
                                    "latent": latent,
                                    "embed_type": embed_type,
                                    "undersampling": under,
                                    "cwd": str(src_dir),
                                    "script": str(script),
                                    "args": args,
                                    "command": command,
                                    "shell_command": shell_command,
                                }
                            )
    if include_official_baselines:
        for script_name in IOHUNTER_BASELINE_SCRIPTS:
            method = script_name.removeprefix("run_").removesuffix(".py")
            script = _iohunter_script_path(workspace, script_name)
            for dataset in datasets:
                for seed in seeds:
                    args = ["--dataset", dataset, "--seed", str(seed), "--splits", str(splits)]
                    if script_name == "run_Node2Vec.py":
                        args.extend(["--lr", f"{learning_rates[0]:g}", "--early", str(early), "--device", device])
                        if epochs is not None:
                            args.extend(["--epochs", str(epochs)])
                        if check is not None:
                            args.extend(["--check", str(check)])
                        if latent is not None:
                            args.extend(["--latent", str(latent)])
                    command = _iohunter_run_command(src_dir, script, args)
                    shell_command = _iohunter_shell_command(src_dir, script, args)
                    plan.append(
                        {
                            "family": "iohunter_official_baseline",
                            "method": method,
                            "setting": "supervised",
                            "dataset": dataset,
                            "seed": seed,
                            "cwd": str(src_dir),
                            "script": str(script),
                            "args": args,
                            "command": command,
                            "shell_command": shell_command,
                        }
                    )
    if include_cross_country:
        script = _iohunter_script_path(workspace, IOHUNTER_CROSS_COUNTRY_SCRIPT)
        for dataset in datasets:
            for gnn in gnns:
                for learning_rate in learning_rates:
                    for seed in seeds:
                        for under in undersampling:
                            args = [
                                "--dataset",
                                dataset,
                                "--lr",
                                f"{learning_rate:g}",
                                "--early",
                                str(early),
                                "--gnn",
                                gnn,
                                "--seed",
                                str(seed),
                                "--splits",
                                str(splits),
                                "--device",
                                device,
                            ]
                            if epochs is not None:
                                args.extend(["--epochs", str(epochs)])
                            if check is not None:
                                args.extend(["--check", str(check)])
                            if latent is not None:
                                args.extend(["--latent", str(latent)])
                            if embed_type is not None:
                                args.extend(["--embed_type", embed_type])
                            if under is not None:
                                args.extend(["--under", str(under)])
                            command = _iohunter_run_command(src_dir, script, args)
                            shell_command = _iohunter_shell_command(src_dir, script, args)
                            plan.append(
                                {
                                    "family": "iohunter",
                                    "method": "MultiModalGNN_CrossAttention_CrossCountryPlusFineTuning",
                                    "setting": "cross_io_finetuning",
                                    "dataset": dataset,
                                    "seed": seed,
                                    "gnn": gnn,
                                    "lr": learning_rate,
                                    "early": early,
                                    "splits": splits,
                                    "epochs": epochs,
                                    "check": check,
                                    "latent": latent,
                                    "embed_type": embed_type,
                                    "undersampling": under,
                                    "cwd": str(src_dir),
                                    "script": str(script),
                                    "args": args,
                                    "command": command,
                                    "shell_command": shell_command,
                                }
                            )
    return plan


def build_iohunter_commands(
    workspace: Path,
    *,
    datasets: Sequence[str] = IOHUNTER_DATASETS,
    seeds: Sequence[int] = (42, 43, 44, 45, 46),
    gnns: Sequence[str] = ("sage",),
    learning_rates: Sequence[float] = (1e-2,),
    early: int = 30,
    splits: int = 5,
    device: str = "0",
    epochs: int | None = None,
    check: int | None = None,
    latent: int | None = None,
    embed_type: str | None = None,
    undersampling: Sequence[float | str | None] = (None,),
    include_primary: bool = True,
    include_official_baselines: bool = False,
    include_cross_country: bool = False,
) -> list[str]:
    plan = build_iohunter_run_plan(
        workspace,
        datasets=datasets,
        seeds=seeds,
        gnns=gnns,
        learning_rates=learning_rates,
        early=early,
        splits=splits,
        device=device,
        epochs=epochs,
        check=check,
        latent=latent,
        embed_type=embed_type,
        undersampling=undersampling,
        include_primary=include_primary,
        include_official_baselines=include_official_baselines,
        include_cross_country=include_cross_country,
    )
    return [str(item["command"]) for item in plan]


def inspect_iohunter_data(workspace: Path) -> dict[str, object]:
    workspace_data_root = _iohunter_workspace_data_root(workspace)
    official_data_root = _iohunter_official_data_root(workspace)
    data_root = _iohunter_effective_data_root(workspace)
    official_data_layout_ready = official_data_root.exists()
    datasets = {}
    for dataset in IOHUNTER_DATASETS:
        dataset_dir = data_root / dataset
        files: list[Path] = []
        if dataset_dir.exists():
            files = [path for path in dataset_dir.rglob("*") if path.is_file()]
        has_dataset_pickle = any(path.name.endswith("datasets.pkl") for path in files)
        has_sbert_features = any(path.name.startswith("sbert_nodeattributes") and path.suffix == ".pt" for path in files)
        datasets[dataset] = {
            "exists": dataset_dir.exists(),
            "file_count": len(files),
            "has_dataset_pickle": has_dataset_pickle,
            "has_sbert_features": has_sbert_features,
            "ready_for_official_run": dataset_dir.exists() and has_dataset_pickle and has_sbert_features,
            "files": sorted(str(path.relative_to(dataset_dir)) for path in files)[:20] if dataset_dir.exists() else [],
        }
    repo_dir = _iohunter_repo_dir(workspace)
    src_dir = _iohunter_src_dir(workspace)
    scripts = {
        "primary": str(_iohunter_script_path(workspace, IOHUNTER_PRIMARY_SCRIPT)),
        "node_pruning": str(_iohunter_script_path(workspace, "run_NodePruning.py")),
        "node2vec": str(_iohunter_script_path(workspace, "run_Node2Vec.py")),
    }
    return {
        "repo_dir": str(repo_dir),
        "src_dir": str(src_dir),
        "data_root": str(data_root),
        "workspace_data_root": str(workspace_data_root),
        "official_data_root": str(official_data_root),
        "official_data_layout_ready": official_data_layout_ready,
        "workspace_data_layout_ready": workspace_data_root.exists(),
        "repo_exists": repo_dir.exists(),
        "src_exists": src_dir.exists(),
        "scripts": scripts,
        "datasets": datasets,
    }


def inspect_iohunter_environment(python_executable: str | None = None) -> dict[str, object]:
    if python_executable:
        probe = (
            "import importlib.util, json; "
            f"packages = {list(IOHUNTER_REQUIRED_PACKAGES)!r}; "
            "result = {name: importlib.util.find_spec(name) is not None for name in packages}; "
            "print(json.dumps(result))"
        )
        process = subprocess.run(
            [python_executable, "-c", probe],
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            return {
                "python_executable": python_executable,
                "python_packages": {},
                "missing_packages": list(IOHUNTER_REQUIRED_PACKAGES),
                "ready_for_official_run": False,
                "error": process.stderr.strip() or process.stdout.strip(),
            }
        packages = json.loads(process.stdout.strip())
        return {
            "python_executable": python_executable,
            "python_packages": packages,
            "missing_packages": [name for name, exists in packages.items() if not exists],
            "ready_for_official_run": all(packages.values()),
        }
    packages = {}
    for package_name in IOHUNTER_REQUIRED_PACKAGES:
        packages[package_name] = importlib.util.find_spec(package_name) is not None
    return {
        "python_executable": None,
        "python_packages": packages,
        "missing_packages": [name for name, exists in packages.items() if not exists],
        "ready_for_official_run": all(packages.values()),
    }


def iohunter_workspace_status(workspace: Path, *, python_executable: str | None = None) -> dict[str, object]:
    data_status = inspect_iohunter_data(workspace)
    environment_status = inspect_iohunter_environment(python_executable)
    dataset_values = data_status["datasets"].values()
    data_ready = bool(data_status["official_data_layout_ready"]) and all(
        bool(item["ready_for_official_run"]) for item in dataset_values
    )
    repo_ready = bool(data_status["repo_exists"]) and bool(data_status["src_exists"])
    return {
        "workspace": str(workspace),
        "repository_ready": repo_ready,
        "data_ready": data_ready,
        "environment_ready": environment_status["ready_for_official_run"],
        "ready_for_official_run": repo_ready and data_ready and environment_status["ready_for_official_run"],
        "data": data_status,
        "environment": environment_status,
    }


def write_iohunter_run_exports(
    workspace: Path,
    output_dir: Path,
    *,
    run_plan: Sequence[Mapping[str, object]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_plan_path = output_dir / "iohunter_run_plan.json"
    ps1_path = output_dir / "iohunter_commands.ps1"
    sh_path = output_dir / "iohunter_commands.sh"
    run_plan_path.write_text(json.dumps(list(run_plan), ensure_ascii=False, indent=2), encoding="utf-8")
    ps_lines = [
        "$ErrorActionPreference = 'Stop'",
        f"# Workspace: {workspace}",
        "",
    ]
    sh_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"# Workspace: {workspace}",
        "",
    ]
    for index, item in enumerate(run_plan, start=1):
        command = str(item["command"])
        shell_command = str(item.get("shell_command", command))
        ps_lines.append(f"# {index}. {item.get('family')} / {item.get('method')} / {item.get('dataset')} / seed={item.get('seed')}")
        ps_lines.append(command)
        sh_lines.append(f"# {index}. {item.get('family')} / {item.get('method')} / {item.get('dataset')} / seed={item.get('seed')}")
        sh_lines.append(shell_command)
    ps1_path.write_text("\n".join(ps_lines) + "\n", encoding="utf-8")
    sh_path.write_text("\n".join(sh_lines) + "\n", encoding="utf-8")
    return {
        "run_plan_json": str(run_plan_path),
        "powershell": str(ps1_path),
        "shell": str(sh_path),
    }


def load_iohunter_run_plan(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"IOHunter run plan must be a JSON list: {path}")
    return [dict(item) for item in data]


def _slug(value: object) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return text or "unknown"


def _run_plan_item_id(item: Mapping[str, object], index: int) -> str:
    parts = [
        f"{index:04d}",
        _slug(item.get("family", "family")),
        _slug(item.get("method", "method")),
        _slug(item.get("setting", "setting")),
        _slug(item.get("dataset", "dataset")),
        f"seed{_slug(item.get('seed', 'na'))}",
    ]
    if item.get("gnn"):
        parts.append(_slug(item["gnn"]))
    if item.get("undersampling") not in {None, "None", ""}:
        parts.append(f"under{_slug(item.get('undersampling'))}")
    return "__".join(parts)


def _iohunter_completed_despite_cleanup_error(stdout: str, stderr: str) -> bool:
    log_text = f"{stdout}\n{stderr}"
    has_test_metrics = bool(re.search(r"^\s*\[TEST[^\]]*\]\s+\w+:", log_text, re.MULTILINE))
    cleanup_error = "shutil.rmtree(exp_dir" in log_text and "not NoneType" in log_text
    return has_test_metrics and cleanup_error


def run_iohunter_plan(
    run_plan: Sequence[Mapping[str, object]],
    *,
    output_dir: Path,
    python_executable: str = "python",
    limit: int | None = None,
    dry_run: bool = False,
    stop_on_error: bool = False,
    resume: bool = True,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "iohunter_run_manifest.json"
    previous_records: dict[str, dict[str, object]] = {}
    if resume and manifest_path.exists():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous_records = {
            str(record.get("run_id")): dict(record)
            for record in previous_manifest.get("records", [])
            if record.get("run_id")
        }
    selected = list(run_plan[:limit]) if limit is not None else list(run_plan)
    records = []
    for index, item in enumerate(selected, start=1):
        cwd = Path(str(item["cwd"]))
        script = Path(str(item["script"]))
        args = [str(value) for value in item.get("args", [])]
        run_id = _run_plan_item_id(item, index)
        stdout_path = log_dir / f"{run_id}.stdout.log"
        stderr_path = log_dir / f"{run_id}.stderr.log"
        record = {
            **dict(item),
            "run_id": run_id,
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
            "dry_run": dry_run,
        }
        previous_record = previous_records.get(run_id)
        if previous_record and previous_record.get("status") == "passed":
            previous_record["status"] = "skipped_existing_success"
            records.append(previous_record)
            continue
        if dry_run:
            stdout_path.touch()
            stderr_path.touch()
            record.update({"returncode": None, "status": "dry_run"})
            records.append(record)
            continue
        started_at = datetime.now(timezone.utc).isoformat()
        process = subprocess.run(
            [python_executable, script.name, *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_path.write_text(process.stdout, encoding="utf-8", errors="replace")
        stderr_path.write_text(process.stderr, encoding="utf-8", errors="replace")
        finished_at = datetime.now(timezone.utc).isoformat()
        status = "passed" if process.returncode == 0 else "failed"
        warning = ""
        if process.returncode != 0 and _iohunter_completed_despite_cleanup_error(process.stdout, process.stderr):
            status = "passed_with_cleanup_warning"
            warning = "official_script_completed_metrics_but_failed_cleanup"
        record.update(
            {
                "returncode": process.returncode,
                "status": status,
                "warning": warning,
                "started_at": started_at,
                "finished_at": finished_at,
            }
        )
        records.append(record)
        if status == "failed" and stop_on_error:
            break
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "resume": resume,
        "python_executable": python_executable,
        "total_requested": len(run_plan),
        "total_selected": len(selected),
        "completed": len(records),
        "failed": sum(1 for item in records if item.get("status") == "failed"),
        "records": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _parse_float_maybe(value: str) -> float | None:
    if value in {"None", "nan", "NaN"}:
        return None
    return float(value)


def parse_iohunter_log_metrics(log_text: str) -> list[dict[str, object]]:
    rows = []
    for match in IOHUNTER_LOG_METRIC_RE.finditer(log_text):
        rows.append(
            {
                "split": match.group("split"),
                "metric": match.group("metric"),
                "mean": _parse_float_maybe(match.group("mean")),
                "std": _parse_float_maybe(match.group("std")),
            }
        )
    return rows


def summarize_iohunter_runs(run_output_dir: Path, *, output_dir: Path | None = None) -> dict[str, object]:
    manifest_path = run_output_dir / "iohunter_run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing IOHunter run manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for record in manifest.get("records", []):
        stdout_path = Path(str(record.get("stdout_log", "")))
        stderr_path = Path(str(record.get("stderr_log", "")))
        log_text_parts = []
        if stdout_path.exists():
            log_text_parts.append(stdout_path.read_text(encoding="utf-8", errors="replace"))
        if stderr_path.exists():
            log_text_parts.append(stderr_path.read_text(encoding="utf-8", errors="replace"))
        for metric in parse_iohunter_log_metrics("\n".join(log_text_parts)):
            rows.append(
                {
                    "family": record.get("family"),
                    "method": record.get("method"),
                    "setting": record.get("setting"),
                    "dataset": record.get("dataset"),
                    "seed": record.get("seed"),
                    "gnn": record.get("gnn"),
                    "undersampling": record.get("undersampling"),
                    "status": record.get("status"),
                    **metric,
                    "run_id": record.get("run_id"),
                }
            )
    target_dir = output_dir or run_output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    csv_path = target_dir / "iohunter_metrics.csv"
    json_path = target_dir / "iohunter_metrics.json"
    aggregate_csv_path = target_dir / "iohunter_metric_summary.csv"
    aggregate_json_path = target_dir / "iohunter_metric_summary.json"
    fields = (
        "family",
        "method",
        "setting",
        "dataset",
        "seed",
        "gnn",
        "undersampling",
        "split",
        "metric",
        "mean",
        "std",
        "status",
        "run_id",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    aggregate_rows = aggregate_iohunter_metric_rows(rows)
    aggregate_fields = (
        "family",
        "method",
        "setting",
        "dataset",
        "gnn",
        "undersampling",
        "split",
        "metric",
        "run_count",
        "mean",
        "std",
    )
    with aggregate_csv_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=aggregate_fields)
        writer.writeheader()
        for row in aggregate_rows:
            writer.writerow({field: row.get(field) for field in aggregate_fields})
    aggregate_json_path.write_text(json.dumps(aggregate_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "manifest": str(manifest_path),
        "metric_count": len(rows),
        "metrics_csv": str(csv_path),
        "metrics_json": str(json_path),
        "summary_csv": str(aggregate_csv_path),
        "summary_json": str(aggregate_json_path),
        "rows": rows,
        "summary_rows": aggregate_rows,
    }


def aggregate_iohunter_metric_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[float]] = defaultdict(list)
    for row in rows:
        value = row.get("mean")
        if value is None:
            continue
        key = (
            row.get("family"),
            row.get("method"),
            row.get("setting"),
            row.get("dataset"),
            row.get("gnn"),
            row.get("undersampling"),
            row.get("split"),
            row.get("metric"),
        )
        groups[key].append(float(value))
    output = []
    for key, values in sorted(groups.items(), key=lambda item: tuple(str(part) for part in item[0])):
        array = np.asarray(values, dtype=float)
        output.append(
            {
                "family": key[0],
                "method": key[1],
                "setting": key[2],
                "dataset": key[3],
                "gnn": key[4],
                "undersampling": key[5],
                "split": key[6],
                "metric": key[7],
                "run_count": len(values),
                "mean": round(float(np.mean(array)), 6),
                "std": round(float(np.std(array, ddof=1)), 6) if len(values) > 1 else 0.0,
            }
        )
    return output


def _read_csv_dicts(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV file: {path}")
    with path.open("r", encoding="utf-8", newline="") as file_handle:
        return [dict(row) for row in csv.DictReader(file_handle)]


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _load_lightweight_report_rows(directory: Path) -> list[dict[str, object]]:
    metrics_path = directory / "metrics.csv"
    rows = []
    dataset = directory.name
    summary_path = directory / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        conversion = summary.get("iohunter_conversion")
        if isinstance(conversion, Mapping):
            dataset = str(conversion.get("dataset") or dataset)
    for row in _read_csv_dicts(metrics_path):
        f1 = _float_or_none(row.get("f1"))
        auc = _float_or_none(row.get("auc"))
        precision = _float_or_none(row.get("precision"))
        recall = _float_or_none(row.get("recall"))
        rows.append(
            {
                "source": "lightweight_reproduction",
                "setting": row.get("setting") or "detect",
                "family": row.get("family"),
                "method": row.get("method"),
                "dataset": dataset,
                "scope": row.get("scope") or "user",
                "split": "TEST",
                "run_count": 1,
                "macro_f1": f1,
                "auc": auc,
                "precision": precision,
                "recall": recall,
                "accuracy": None,
                "primary_metric": f1,
                "notes": row.get("notes", ""),
            }
        )
    return rows


def _load_iohunter_report_rows(directory: Path) -> list[dict[str, object]]:
    summary_path = directory / "iohunter_metric_summary.csv"
    metric_rows = _read_csv_dicts(summary_path)
    grouped: dict[tuple[object, ...], dict[str, object]] = {}
    for row in metric_rows:
        split = str(row.get("split") or "")
        if split != "TEST":
            continue
        key = (
            row.get("family"),
            row.get("method"),
            row.get("setting"),
            row.get("dataset"),
            row.get("gnn"),
            row.get("undersampling"),
        )
        record = grouped.setdefault(
            key,
            {
                "source": "iohunter_official",
                "setting": row.get("setting"),
                "family": row.get("family"),
                "method": row.get("method"),
                "dataset": row.get("dataset"),
                "scope": "user",
                "split": "TEST",
                "run_count": int(float(str(row.get("run_count") or 0))),
                "macro_f1": None,
                "auc": None,
                "precision": None,
                "recall": None,
                "accuracy": None,
                "primary_metric": None,
                "notes": "",
            },
        )
        metric = str(row.get("metric") or "")
        value = _float_or_none(row.get("mean"))
        if metric in {"f1_macro", "macro_f1"}:
            record["macro_f1"] = value
            record["primary_metric"] = value
        elif metric in {"roc_auc", "auc"}:
            record["auc"] = value
        elif metric == "precision":
            record["precision"] = value
        elif metric == "recall":
            record["recall"] = value
        elif metric == "accuracy":
            record["accuracy"] = value
        notes = []
        if row.get("gnn"):
            notes.append(f"gnn={row.get('gnn')}")
        if row.get("undersampling"):
            notes.append(f"under={row.get('undersampling')}")
        record["notes"] = ";".join(notes)
    return list(grouped.values())


def _write_markdown_table(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    headers = ("source", "setting", "family", "method", "dataset", "macro_f1", "auc", "precision", "recall", "accuracy", "notes")
    lines = [
        "# CoordinationDiscover IO Coordination Comparison",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = []
        for header in headers:
            value = row.get(header)
            if isinstance(value, float):
                value = f"{value:.6f}"
            values.append(str(value) if value is not None else "")
        lines.append("| " + " | ".join(values) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_coordination_discover_comparison_report(
    *,
    output_dir: Path,
    lightweight_dirs: Sequence[Path] = (),
    iohunter_summary_dirs: Sequence[Path] = (),
) -> dict[str, object]:
    """Merge CoordinationDiscover lightweight and official IOHunter metrics into one report table."""
    rows: list[dict[str, object]] = []
    for directory in lightweight_dirs:
        rows.extend(_load_lightweight_report_rows(Path(directory)))
    for directory in iohunter_summary_dirs:
        rows.extend(_load_iohunter_report_rows(Path(directory)))
    rows = sorted(
        rows,
        key=lambda row: (
            str(row.get("dataset") or ""),
            str(row.get("source") or ""),
            str(row.get("family") or ""),
            str(row.get("method") or ""),
            str(row.get("notes") or ""),
        ),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "coordination_discover_comparison_report.csv"
    json_path = output_dir / "coordination_discover_comparison_report.json"
    markdown_path = output_dir / "CoordinationDiscover_COMPARISON_REPORT.md"
    fields = (
        "source",
        "setting",
        "family",
        "method",
        "dataset",
        "scope",
        "split",
        "run_count",
        "macro_f1",
        "auc",
        "precision",
        "recall",
        "accuracy",
        "primary_metric",
        "notes",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_table(markdown_path, rows)
    return {
        "row_count": len(rows),
        "csv": str(csv_path),
        "json": str(json_path),
        "markdown": str(markdown_path),
        "rows": rows,
    }


def run_iohunter_lightweight_batch(
    processed_root: Path,
    *,
    output_dir: Path,
    datasets: Sequence[str] = IOHUNTER_DATASETS,
    threshold: str = "0.7",
    train_percentage: str | None = None,
    undersampling: str | None = None,
    max_edges_per_relation: int | None = None,
    seed: int = 42,
    relations: Sequence[str] = IOHUNTER_CANONICAL_RELATIONS,
    include_text_similarity: bool = False,
    max_edges_per_node: int | None = 50,
    embedding_dim: int = 32,
    continue_on_error: bool = False,
) -> dict[str, object]:
    """Run lightweight CoordinationDiscover baselines over multiple IOHunter processed datasets."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_results: dict[str, dict[str, object]] = {}
    failures: dict[str, str] = {}
    for dataset_name in datasets:
        dataset_dir = processed_root / dataset_name
        dataset_output_dir = output_dir / dataset_name
        try:
            events_path = dataset_output_dir / "iohunter_events.csv"
            conversion = write_iohunter_event_table(
                dataset_dir,
                events_path,
                dataset_name=dataset_name,
                threshold=threshold,
                train_percentage=train_percentage,
                undersampling=undersampling,
                max_edges_per_relation=max_edges_per_relation,
            )
            events = read_event_table(events_path)
            summary = run_reproduction_suite(
                events,
                output_dir=dataset_output_dir,
                relations=relations,
                include_text_similarity=include_text_similarity,
                max_edges_per_node=max_edges_per_node,
                embedding_dim=embedding_dim,
                seed=seed,
            )
            summary["iohunter_conversion"] = conversion
            (dataset_output_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            dataset_results[dataset_name] = {
                "dataset_dir": str(dataset_dir),
                "output_dir": str(dataset_output_dir),
                "metrics_csv": str(dataset_output_dir / "metrics.csv"),
                "summary_json": str(dataset_output_dir / "summary.json"),
                "row_count": conversion["row_count"],
                "account_count": conversion["account_count"],
                "positive_label_count": conversion["positive_label_count"],
            }
        except Exception as exc:
            failures[dataset_name] = str(exc)
            if not continue_on_error:
                raise
    report = build_coordination_discover_comparison_report(
        output_dir=output_dir / "coordination_discover_report",
        lightweight_dirs=tuple(Path(item["output_dir"]) for item in dataset_results.values()),
    )
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processed_root": str(processed_root),
        "output_dir": str(output_dir),
        "dataset_count": len(dataset_results),
        "failed": len(failures),
        "datasets": dataset_results,
        "failures": failures,
        "include_text_similarity": include_text_similarity,
        "max_edges_per_node": max_edges_per_node,
        "embedding_dim": embedding_dim,
        "report": {
            key: value
            for key, value in report.items()
            if key != "rows"
        },
    }
    manifest_path = output_dir / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        **manifest,
        "manifest": str(manifest_path),
        "report": report,
    }


def _is_valid_zip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except zipfile.BadZipFile:
        return False


def _download_file_with_resume(
    url: str,
    destination: Path,
    *,
    expected_size: int | None = None,
    retries: int = 3,
) -> list[str]:
    actions: list[str] = []
    part_path = destination.with_suffix(destination.suffix + ".part")
    if destination.exists() and expected_size and destination.stat().st_size < expected_size:
        destination.replace(part_path)
        actions.append(f"moved_incomplete_zip_to_part:{part_path}")
    for attempt in range(1, retries + 1):
        resume_at = part_path.stat().st_size if part_path.exists() else 0
        request = urllib.request.Request(url)
        if resume_at:
            request.add_header("Range", f"bytes={resume_at}-")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status = getattr(response, "status", None)
                if resume_at and status == 200:
                    part_path.unlink(missing_ok=True)
                    resume_at = 0
                    actions.append("server_ignored_range_restart_download")
                mode = "ab" if resume_at else "wb"
                with part_path.open(mode) as file_handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        file_handle.write(chunk)
            current_size = part_path.stat().st_size
            actions.append(f"download_attempt_{attempt}:{current_size}")
            if expected_size is None or current_size >= expected_size:
                part_path.replace(destination)
                actions.append(f"downloaded:{destination}")
                return actions
        except Exception as exc:
            actions.append(f"download_attempt_{attempt}_failed:{type(exc).__name__}:{exc}")
            if attempt == retries:
                raise
            time.sleep(min(2**attempt, 10))
    if part_path.exists():
        part_path.replace(destination)
    return actions


def prepare_iohunter_workspace(
    workspace: Path,
    *,
    clone_code: bool = False,
    download_data: bool = False,
    python_executable: str | None = None,
) -> dict[str, object]:
    workspace.mkdir(parents=True, exist_ok=True)
    repo_dir = workspace / "SocGFM"
    data_zip = workspace / "data.zip"
    actions: list[str] = []
    if clone_code and not repo_dir.exists():
        subprocess.run(["git", "clone", IOHUNTER_REPO_URL, str(repo_dir)], check=True)
        actions.append(f"cloned:{repo_dir}")
    if download_data and not _is_valid_zip(data_zip):
        actions.extend(
            _download_file_with_resume(
                IOHUNTER_ZENODO_DATA_URL,
                data_zip,
                expected_size=IOHUNTER_ZENODO_DATA_SIZE,
            )
        )
    if download_data and data_zip.exists() and not _is_valid_zip(data_zip):
        actions.append(f"invalid_zip:{data_zip}")
        raise zipfile.BadZipFile(f"Downloaded IOHunter archive is not a valid zip: {data_zip}")
    if download_data and data_zip.exists() and _is_valid_zip(data_zip) and not (workspace / "data" / "processed").exists():
        with zipfile.ZipFile(data_zip) as archive:
            archive.extractall(workspace)
        actions.append(f"extracted:{data_zip}")
    return {
        "workspace": str(workspace),
        "repo_dir": str(repo_dir),
        "data_zip": str(data_zip),
        "actions": actions,
        "status": iohunter_workspace_status(workspace, python_executable=python_executable),
        "commands": build_iohunter_commands(workspace),
    }


def run_reproduction_suite(
    events: pd.DataFrame,
    *,
    output_dir: Path,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    include_text_similarity: bool = True,
    max_edges_per_node: int | None = None,
    embedding_dim: int = 128,
    seed: int = 42,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    unmasking = run_unmasking_reproduction(
        events,
        relations=relations,
        include_text_similarity=include_text_similarity,
        max_edges_per_node=max_edges_per_node,
        embedding_dim=embedding_dim,
        seed=seed,
    )
    graphs = build_unmasking_similarity_graphs(
        events,
        relations=relations,
        include_text_similarity=include_text_similarity,
        max_edges_per_node=max_edges_per_node,
    )
    fused = fuse_similarity_graphs(graphs)
    llm = run_lightweight_llm_baselines(events, fused, output_dir=output_dir, seed=seed)
    ours_ablations = run_dyna_colm_gnn_ablations(events, relations=relations, seed=seed)
    ours = ours_ablations["full"]
    summary = {
        "manifest": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "row_count": int(len(events)),
            "account_count": int(events["account_id"].nunique()),
            "relations": list(relations),
            "include_text_similarity": include_text_similarity,
            "max_edges_per_node": max_edges_per_node,
            "embedding_dim": embedding_dim,
            "seed": seed,
            "implementation": "coordination_discover_io_reproduction_lightweight",
        },
        "unmasking": unmasking,
        "leveraging_llms": llm,
        "ours": ours,
        "ours_ablations": {
            variant: result
            for variant, result in ours_ablations.items()
            if variant != "full"
        },
    }
    exports = write_metric_exports(summary, output_dir)
    summary["exports"] = exports
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(summary["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def make_sample_events() -> pd.DataFrame:
    rows = [
        ("u1", "url_share", "https://a.example/story", 1, "p1", "same story alpha", 1),
        ("u2", "url_share", "https://a.example/story", 2, "p2", "same story alpha", 1),
        ("u3", "url_share", "https://b.example/organic", 3, "p3", "organic comment beta", 0),
        ("u1", "hashtag_share", "topic-a", 4, "p4", "topic alpha", 1),
        ("u2", "hashtag_share", "topic-a", 5, "p5", "topic alpha", 1),
        ("u4", "hashtag_share", "topic-b", 6, "p6", "organic beta", 0),
        ("u1", "retweet_target", "tweet:root-1", 7, "p7", "amplify root", 1),
        ("u2", "retweet_target", "tweet:root-1", 8, "p8", "amplify root", 1),
        ("u3", "mention_target", "u4", 9, "p9", "talk to friend", 0),
        ("u4", "mention_target", "u3", 10, "p10", "reply to friend", 0),
    ]
    return pd.DataFrame(
        rows,
        columns=["account_id", "relation", "object_id", "timestamp", "content_id", "content", "label"],
    )


def write_sample_events(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    make_sample_events().to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)
