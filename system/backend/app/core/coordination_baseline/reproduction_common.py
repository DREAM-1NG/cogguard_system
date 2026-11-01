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

__all__ = [
    "CommunityDetectionResult",
    "DEFAULT_RELATIONS",
    "DISCOVER_STRUCTURE_FILTERS",
    "DISCOVER_STRUCTURE_FILTER_METRICS",
    "IOHUNTER_BASELINE_SCRIPTS",
    "IOHUNTER_CANONICAL_RELATIONS",
    "IOHUNTER_CROSS_COUNTRY_SCRIPT",
    "IOHUNTER_DATASETS",
    "IOHUNTER_GRAPH_RELATION_MAP",
    "IOHUNTER_LOG_METRIC_RE",
    "IOHUNTER_PRIMARY_SCRIPT",
    "IOHUNTER_REPO_URL",
    "IOHUNTER_REQUIRED_PACKAGES",
    "IOHUNTER_ZENODO_DATA_SIZE",
    "IOHUNTER_ZENODO_DATA_URL",
    "LABEL_COLUMNS",
    "METRIC_FIELDS",
    "MetricResult",
    "PreparedDetectInputs",
    "Split",
    "TARGET_RELATIONS",
    "TEXT_COLUMNS",
    "TOKEN_RE",
    "binary_metrics",
    "extract_labels",
    "flatten_reproduction_metrics",
    "iohunter_processed_to_event_table",
    "load_iohunter_processed_dataset",
    "normalize_event_table",
    "read_event_table",
    "write_iohunter_event_table",
    "write_metric_exports",
]
