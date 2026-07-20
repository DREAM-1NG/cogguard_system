"""Standalone coordination experiments for Twitter IO archives.

This module is intentionally independent from the web service layer so it can
run on a lightweight Python environment on remote servers.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import subprocess
import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import networkx as nx
import numpy as np
from networkx.algorithms.community import greedy_modularity_communities
from networkx.algorithms.community.quality import modularity

try:
    import torch
    import torch.nn.functional as F
except ImportError:  # pragma: no cover - optional runtime dependency
    torch = None
    F = None


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}
TRACKING_QUERY_PREFIXES = ("utm_",)
BASE_RELATIONS = (
    "url_share",
    "hashtag_share",
    "retweet_target",
    "reply_target",
    "quote_target",
    "mention_target",
)
DEFAULT_METHODS = (
    "url_share",
    "hashtag_share",
    "retweet_target",
    "reply_target",
    "multi_relation",
)
DEFAULT_RELATION_WEIGHTS = {
    "url_share": 1.0,
    "hashtag_share": 0.6,
    "retweet_target": 0.9,
    "reply_target": 0.8,
    "quote_target": 0.7,
    "mention_target": 0.4,
}
DEFAULT_ATTENTION_EPOCHS = 200
DEFAULT_ATTENTION_LEARNING_RATE = 0.1
DEFAULT_ATTENTION_L2 = 1e-3
DEFAULT_ATTENTION_MAX_SAMPLES = 20000
DEFAULT_RANDOM_SEED = 42
DEFAULT_ATTENTION_BACKEND = "auto"
DEFAULT_ATTENTION_HIDDEN_DIM = 16
DEFAULT_ATTENTION_NEGATIVE_RATIO = 1.0
METHOD_CATALOG = {
    "url_share": {
        "label": "Shared URL Coordination",
        "paper_anchor": "Giglietto et al. 2020 / CooRTweet-style coordinated link sharing",
        "relations": ["url_share"],
    },
    "hashtag_share": {
        "label": "Shared Hashtag Coordination",
        "paper_anchor": "Pacheco et al. 2020 / coordination network object sharing",
        "relations": ["hashtag_share"],
    },
    "retweet_target": {
        "label": "Co-retweet Target Coordination",
        "paper_anchor": "Co-retweet style synchronized amplification baseline",
        "relations": ["retweet_target"],
    },
    "reply_target": {
        "label": "Shared Reply-target Coordination",
        "paper_anchor": "Coordinated Reply Attacks in Influence Operations",
        "relations": ["reply_target"],
    },
    "quote_target": {
        "label": "Shared Quote-target Coordination",
        "paper_anchor": "Coordination network object sharing via quoted targets",
        "relations": ["quote_target"],
    },
    "mention_target": {
        "label": "Shared Mention-target Coordination",
        "paper_anchor": "Mention-target overlap as lightweight interaction coordination",
        "relations": ["mention_target"],
    },
    "multi_relation": {
        "label": "Learned Multi-relation Attention Coordination",
        "paper_anchor": "CooRTweet-style multi-relation graph with learnable relation attention",
        "relations": list(BASE_RELATIONS),
    },
    "multi_relation_static": {
        "label": "Static Multi-relation Weighted Coordination",
        "paper_anchor": "Coordination Network Toolkit / multi-relation weighted fusion",
        "relations": list(BASE_RELATIONS),
    },
}


@dataclass(slots=True)
class ExperimentConfig:
    tweets_zip_path: Path
    output_dir: Path
    methods: tuple[str, ...] = DEFAULT_METHODS
    languages: tuple[str, ...] = ()
    time_window_seconds: int = 60
    min_accounts_per_object: int = 2
    max_accounts_per_object: int = 50
    min_events_per_object: int = 2
    limit_rows: int | None = None
    sqlite_path: Path | None = None
    relation_weights: dict[str, float] | None = None
    attention_epochs: int = DEFAULT_ATTENTION_EPOCHS
    attention_learning_rate: float = DEFAULT_ATTENTION_LEARNING_RATE
    attention_l2: float = DEFAULT_ATTENTION_L2
    attention_max_samples: int = DEFAULT_ATTENTION_MAX_SAMPLES
    random_seed: int = DEFAULT_RANDOM_SEED
    attention_backend: str = DEFAULT_ATTENTION_BACKEND
    attention_hidden_dim: int = DEFAULT_ATTENTION_HIDDEN_DIM
    attention_negative_ratio: float = DEFAULT_ATTENTION_NEGATIVE_RATIO


@dataclass(slots=True)
class RelationResult:
    method: str
    label: str
    paper_anchor: str
    relation_names: tuple[str, ...]
    event_count: int
    filtered_object_count: int
    pair_count: int
    node_count: int
    edge_count: int
    component_count: int
    cluster_count: int
    largest_component_size: int
    largest_cluster_size: int
    avg_edge_weight: float
    modularity_score: float | None
    top_nodes: list[dict[str, object]]
    top_edges: list[dict[str, object]]
    top_objects: list[dict[str, object]]
    component_sizes: list[int]
    cluster_sizes: list[int]
    relation_breakdown: dict[str, float] | None = None
    learning_metadata: dict[str, object] | None = None
    edge_weights: Counter[tuple[str, str]] | None = None


def parse_archive_list(raw_value: str | None) -> list[str]:
    text = (raw_value or "").strip()
    if not text or text == "[]":
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if not text:
        return []
    items = []
    for item in text.split(","):
        normalized = item.strip().strip('"').strip("'")
        if normalized:
            items.append(normalized)
    return items


def normalize_archive_url(raw_url: str) -> str:
    text = raw_url.strip()
    if not text:
        return ""
    parts = urlsplit(text)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TRACKING_QUERY_KEYS or lowered.startswith(TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((key, value))
    query = urlencode(query_items, doseq=True)
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    return normalized.rstrip("/") if path == "/" and not query else normalized


def normalize_hashtag(raw_hashtag: str) -> str:
    text = raw_hashtag.strip().lstrip("#").strip()
    return text.lower()


def parse_tweet_timestamp(raw_value: str | None) -> int | None:
    text = (raw_value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return int(datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    return None


def expand_methods(methods: Iterable[str]) -> tuple[str, ...]:
    expanded: set[str] = set()
    for method in methods:
        if method in {"multi_relation", "multi_relation_static"}:
            expanded.update(BASE_RELATIONS)
            continue
        expanded.add(method)
    return tuple(sorted(expanded))


def _find_archive_csv_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        return next(
            name for name in archive.namelist()
            if name.endswith(".csv") and not name.startswith("__MACOSX/")
        )


def _build_archive_stream_command(zip_path: Path, member_name: str) -> tuple[str, list[str]] | None:
    unzip_path = shutil.which("unzip")
    if unzip_path:
        return "unzip", [unzip_path, "-p", str(zip_path), member_name]

    powershell_path = shutil.which("powershell.exe") or shutil.which("powershell")
    if os.name == "nt" and powershell_path:
        escaped_zip = str(zip_path).replace("'", "''")
        escaped_member = member_name.replace("'", "''")
        script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead('{escaped_zip}')
try {{
    $entry = $zip.GetEntry('{escaped_member}')
    if ($null -eq $entry) {{
        throw "Archive member not found: {escaped_member}"
    }}
    $stream = $entry.Open()
    try {{
        $stream.CopyTo([Console]::OpenStandardOutput())
    }} finally {{
        $stream.Dispose()
    }}
}} finally {{
    $zip.Dispose()
}}
""".strip()
        return "powershell_zip", [powershell_path, "-NoProfile", "-Command", script]

    return None


def _iter_archive_rows(zip_path: Path) -> tuple[str, Iterable[dict[str, str]]]:
    member_name = _find_archive_csv_member(zip_path)
    command_spec = _build_archive_stream_command(zip_path, member_name)
    if command_spec is None:
        def _zipfile_rows() -> Iterable[dict[str, str]]:
            with zipfile.ZipFile(zip_path) as archive:
                with archive.open(member_name) as file_handle:
                    wrapper = io.TextIOWrapper(file_handle, encoding="utf-8", errors="replace", newline="")
                    reader = csv.DictReader(wrapper)
                    yield from reader

        return "python_zipfile", _zipfile_rows()

    backend_name, command = command_spec

    def _stream_rows() -> Iterable[dict[str, str]]:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdout is not None
        assert process.stderr is not None
        wrapper = io.TextIOWrapper(process.stdout, encoding="utf-8", errors="replace", newline="")
        try:
            reader = csv.DictReader(wrapper)
            yield from reader
        finally:
            wrapper.close()
            stderr_text = process.stderr.read().decode("utf-8", errors="replace").strip()
            return_code = process.wait()
            if return_code in (-13, 141):
                return
            if return_code != 0:
                raise RuntimeError(
                    f"Archive stream command failed with exit code {return_code}: {stderr_text or command[0]}"
                )

    return backend_name, _stream_rows()


def iter_archive_relation_events(
    row: dict[str, str],
    relations: Iterable[str],
) -> Iterable[tuple[str, str]]:
    requested = set(relations)
    if "url_share" in requested:
        for raw_url in parse_archive_list(row.get("urls")):
            normalized = normalize_archive_url(raw_url)
            if normalized:
                yield "url_share", normalized

    if "hashtag_share" in requested:
        for raw_hashtag in parse_archive_list(row.get("hashtags")):
            normalized = normalize_hashtag(raw_hashtag)
            if normalized:
                yield "hashtag_share", normalized

    if "retweet_target" in requested and row.get("is_retweet", "").strip().lower() == "true":
        retweet_tweetid = (row.get("retweet_tweetid") or "").strip()
        retweet_userid = (row.get("retweet_userid") or "").strip()
        if retweet_tweetid:
            yield "retweet_target", f"tweet:{retweet_tweetid}"
        elif retweet_userid:
            yield "retweet_target", f"user:{retweet_userid}"

    if "reply_target" in requested:
        reply_target = (row.get("in_reply_to_userid") or "").strip()
        if reply_target:
            yield "reply_target", reply_target

    if "quote_target" in requested:
        quote_target = (row.get("quoted_tweet_tweetid") or "").strip()
        if quote_target:
            yield "quote_target", quote_target

    if "mention_target" in requested:
        for mention in parse_archive_list(row.get("user_mentions")):
            normalized = mention.strip()
            if normalized:
                yield "mention_target", normalized


def ingest_twitter_io_archive(config: ExperimentConfig) -> dict[str, object]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = config.sqlite_path or config.output_dir / "events.sqlite3"
    if sqlite_path.exists():
        sqlite_path.unlink()

    relation_set = expand_methods(config.methods)
    languages = {item.strip().lower() for item in config.languages if item.strip()}
    relation_event_counts: Counter[str] = Counter()
    processed_rows = 0
    inserted_events = 0
    archive_reader_backend = ""

    connection = sqlite3.connect(sqlite_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE events (
                relation TEXT NOT NULL,
                object_id TEXT NOT NULL,
                ts INTEGER NOT NULL,
                account_id TEXT NOT NULL,
                content_id TEXT NOT NULL
            )
            """
        )

        batch: list[tuple[str, str, int, str, str]] = []
        archive_reader_backend, row_iter = _iter_archive_rows(config.tweets_zip_path)
        for row_index, row in enumerate(row_iter, start=1):
            if config.limit_rows is not None and row_index > config.limit_rows:
                break
            language = (row.get("tweet_language") or "").strip().lower()
            if languages and language not in languages:
                continue

            ts = parse_tweet_timestamp(row.get("tweet_time"))
            account_id = (row.get("userid") or "").strip()
            content_id = (row.get("tweetid") or "").strip()
            if ts is None or not account_id or not content_id:
                continue

            seen_pairs: set[tuple[str, str]] = set()
            processed_rows += 1
            for relation, object_id in iter_archive_relation_events(row, relation_set):
                event_key = (relation, object_id)
                if event_key in seen_pairs:
                    continue
                seen_pairs.add(event_key)
                batch.append((relation, object_id, ts, account_id, content_id))
                relation_event_counts[relation] += 1
                inserted_events += 1

            if len(batch) >= 5000:
                cursor.executemany(
                    "INSERT INTO events (relation, object_id, ts, account_id, content_id) VALUES (?, ?, ?, ?, ?)",
                    batch,
                )
                connection.commit()
                batch.clear()

        if batch:
            cursor.executemany(
                "INSERT INTO events (relation, object_id, ts, account_id, content_id) VALUES (?, ?, ?, ?, ?)",
                batch,
            )
            connection.commit()

        cursor.execute("CREATE INDEX idx_events_relation_object_ts ON events (relation, object_id, ts)")
        cursor.execute("CREATE INDEX idx_events_relation_account ON events (relation, account_id)")
        cursor.execute(
            """
            CREATE TABLE object_support AS
            SELECT
                relation,
                object_id,
                COUNT(*) AS event_count,
                COUNT(DISTINCT account_id) AS account_count
            FROM events
            GROUP BY relation, object_id
            """
        )
        cursor.execute("CREATE INDEX idx_object_support_relation_object ON object_support (relation, object_id)")
        connection.commit()
    finally:
        connection.close()

    return {
        "sqlite_path": str(sqlite_path),
        "archive_reader_backend": archive_reader_backend,
        "processed_rows": processed_rows,
        "inserted_events": inserted_events,
        "relation_event_counts": dict(sorted(relation_event_counts.items())),
    }


def _iter_filtered_objects(
    connection: sqlite3.Connection,
    relation_name: str,
    *,
    min_accounts_per_object: int,
    max_accounts_per_object: int,
    min_events_per_object: int,
) -> list[dict[str, int | str]]:
    cursor = connection.execute(
        """
        SELECT object_id, event_count, account_count
        FROM object_support
        WHERE relation = ?
          AND account_count >= ?
          AND account_count <= ?
          AND event_count >= ?
        ORDER BY event_count DESC, account_count DESC, object_id ASC
        """,
        (
            relation_name,
            min_accounts_per_object,
            max_accounts_per_object,
            min_events_per_object,
        ),
    )
    return [
        {
            "object_id": row[0],
            "event_count": int(row[1]),
            "account_count": int(row[2]),
        }
        for row in cursor.fetchall()
    ]


def _update_pairs_for_object(
    object_id: str,
    events: list[tuple[int, str, str]],
    *,
    time_window_seconds: int,
    edge_weights: Counter[tuple[str, str]],
    object_pair_counts: Counter[str],
) -> int:
    pair_count = 0
    window_start = 0
    for index, event in enumerate(events):
        event_ts, event_account_id, _ = event
        while event_ts - events[window_start][0] > time_window_seconds:
            window_start += 1
        for earlier_index in range(window_start, index):
            earlier_event = events[earlier_index]
            if earlier_event[1] == event_account_id:
                continue
            edge_key = tuple(sorted((earlier_event[1], event_account_id)))
            edge_weights[edge_key] += 1
            object_pair_counts[object_id] += 1
            pair_count += 1
    return pair_count


def _rank_top_nodes(graph: nx.Graph, *, limit: int = 10) -> list[dict[str, object]]:
    ranked = sorted(
        graph.nodes(),
        key=lambda node: (-float(graph.degree(node, weight="weight")), node),
    )
    return [
        {
            "account_id": node,
            "weighted_degree": float(graph.degree(node, weight="weight")),
            "degree": int(graph.degree(node)),
        }
        for node in ranked[:limit]
    ]


def _rank_top_edges(edge_weights: Counter[tuple[str, str]], *, limit: int = 10) -> list[dict[str, object]]:
    return [
        {
            "source": source,
            "target": target,
            "weight": float(weight),
        }
        for (source, target), weight in edge_weights.most_common(limit)
    ]


def _normalize_edge_feature_matrix(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    transformed = np.log1p(matrix.astype(float, copy=False))
    column_scale = np.max(transformed, axis=0)
    column_scale[column_scale <= 0.0] = 1.0
    return transformed / column_scale


def _softmax_rows(logits: np.ndarray) -> np.ndarray:
    if logits.size == 0:
        return logits
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp_values = np.exp(shifted)
    sums = np.sum(exp_values, axis=1, keepdims=True)
    sums[sums <= 0.0] = 1.0
    return exp_values / sums


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -30.0, 30.0)))


def _build_static_combined_edges(
    relation_results: dict[str, RelationResult],
    relation_weights: dict[str, float],
) -> Counter[tuple[str, str]]:
    combined_edges: Counter[tuple[str, str]] = Counter()
    for relation_name in BASE_RELATIONS:
        result = relation_results.get(relation_name)
        if result is None or result.edge_weights is None:
            continue
        weight_factor = float(relation_weights.get(relation_name, 1.0))
        for edge_key, edge_weight in result.edge_weights.items():
            combined_edges[edge_key] += edge_weight * weight_factor
    return combined_edges


def _build_relation_learning_bundle(
    relation_results: dict[str, RelationResult],
) -> dict[str, object] | None:
    node_ids: set[str] = set()
    active_relations: list[str] = []
    for relation_name in BASE_RELATIONS:
        result = relation_results.get(relation_name)
        if result is None or result.edge_weights is None or not result.edge_weights:
            continue
        active_relations.append(relation_name)
        for source, target in result.edge_weights.keys():
            node_ids.add(source)
            node_ids.add(target)

    if not node_ids:
        return None

    ordered_nodes = sorted(node_ids)
    node_index = {node_id: index for index, node_id in enumerate(ordered_nodes)}
    relation_count = len(BASE_RELATIONS)
    degree_matrix = np.zeros((len(ordered_nodes), relation_count), dtype=float)
    relation_context = np.zeros((len(ordered_nodes), relation_count), dtype=float)
    relation_context_norm = np.zeros((len(ordered_nodes), relation_count), dtype=float)
    edge_feature_map: dict[tuple[str, str], np.ndarray] = {}

    for relation_offset, relation_name in enumerate(BASE_RELATIONS):
        result = relation_results.get(relation_name)
        if result is None or result.edge_weights is None:
            continue
        for edge_key, edge_weight in result.edge_weights.items():
            source, target = edge_key
            source_index = node_index[source]
            target_index = node_index[target]
            edge_feature_map.setdefault(edge_key, np.zeros(relation_count, dtype=float))[relation_offset] = float(edge_weight)
            degree_matrix[source_index, relation_offset] += float(edge_weight)
            degree_matrix[target_index, relation_offset] += float(edge_weight)

    normalized_degrees = _normalize_edge_feature_matrix(degree_matrix)

    for relation_offset, relation_name in enumerate(BASE_RELATIONS):
        result = relation_results.get(relation_name)
        if result is None or result.edge_weights is None:
            continue
        for edge_key, edge_weight in result.edge_weights.items():
            source, target = edge_key
            source_index = node_index[source]
            target_index = node_index[target]
            weight_value = float(edge_weight)
            relation_context[source_index, relation_offset] += weight_value * normalized_degrees[target_index, relation_offset]
            relation_context[target_index, relation_offset] += weight_value * normalized_degrees[source_index, relation_offset]
            relation_context_norm[source_index, relation_offset] += weight_value
            relation_context_norm[target_index, relation_offset] += weight_value

    relation_context = np.divide(
        relation_context,
        np.maximum(relation_context_norm, 1.0),
        out=np.zeros_like(relation_context),
        where=relation_context_norm > 0.0,
    )

    return {
        "ordered_nodes": ordered_nodes,
        "node_index": node_index,
        "active_relations": active_relations,
        "degree_matrix": degree_matrix,
        "normalized_degrees": normalized_degrees,
        "relation_context": relation_context,
        "edge_feature_map": edge_feature_map,
    }


def _compute_teacher_scores(
    edge_feature_map: dict[tuple[str, str], np.ndarray],
    combined_edges: Counter[tuple[str, str]],
) -> dict[tuple[str, str], float]:
    graph = nx.Graph()
    for (source, target), weight in combined_edges.items():
        graph.add_edge(source, target, weight=float(weight))

    if graph.number_of_edges() == 0:
        return {}

    communities = [set(map(str, community)) for community in greedy_modularity_communities(graph, weight="weight")]
    community_index: dict[str, int] = {}
    for community_id, community_nodes in enumerate(communities):
        for node_id in community_nodes:
            community_index[node_id] = community_id

    neighbor_sets = {node_id: set(graph.neighbors(node_id)) for node_id in graph.nodes()}
    teacher_scores: dict[tuple[str, str], float] = {}
    for edge_key, raw_features in edge_feature_map.items():
        source, target = edge_key
        same_community = 1.0 if community_index.get(source) == community_index.get(target) else 0.0
        source_neighbors = neighbor_sets.get(source, set())
        target_neighbors = neighbor_sets.get(target, set())
        union_neighbors = source_neighbors | target_neighbors
        common_neighbors = source_neighbors & target_neighbors
        jaccard = (len(common_neighbors) / len(union_neighbors)) if union_neighbors else 0.0
        multi_relation_support = float(np.count_nonzero(raw_features) > 1)
        teacher_scores[edge_key] = float(np.clip(0.5 * same_community + 0.3 * jaccard + 0.2 * multi_relation_support, 0.0, 1.0))
    return teacher_scores


def _sample_learning_edges(
    edge_feature_map: dict[tuple[str, str], np.ndarray],
    teacher_scores: dict[tuple[str, str], float],
    max_samples: int,
    random_seed: int,
) -> list[tuple[str, str]]:
    edge_keys = list(edge_feature_map.keys())
    if len(edge_keys) <= max_samples:
        return edge_keys

    ranked_keys = sorted(
        edge_keys,
        key=lambda edge_key: (
            -teacher_scores.get(edge_key, 0.0),
            -float(np.count_nonzero(edge_feature_map[edge_key])),
            -float(np.sum(edge_feature_map[edge_key])),
            edge_key,
        ),
    )
    head_size = max_samples // 2
    tail_size = max_samples - head_size
    rng = np.random.default_rng(random_seed)
    remaining = ranked_keys[head_size:]
    if len(remaining) <= tail_size:
        return ranked_keys[:max_samples]
    sampled_tail_indices = rng.choice(len(remaining), size=tail_size, replace=False)
    sampled_tail = [remaining[int(index)] for index in sorted(sampled_tail_indices)]
    return ranked_keys[:head_size] + sampled_tail


def _train_relation_attention_model(
    edge_features: np.ndarray,
    context_features: np.ndarray,
    teacher_scores: np.ndarray,
    *,
    epochs: int,
    learning_rate: float,
    l2_penalty: float,
) -> dict[str, object]:
    relation_count = edge_features.shape[1]
    theta = np.zeros(relation_count, dtype=float)
    output_scale = 1.0
    bias = 0.0
    loss_history: list[float] = []

    for _ in range(max(epochs, 1)):
        logits = context_features * theta.reshape(1, -1)
        attention = _softmax_rows(logits)
        attended_strength = np.sum(attention * edge_features, axis=1)
        predictions = _sigmoid(bias + output_scale * attended_strength)
        epsilon = 1e-8
        loss = float(
            np.mean(
                -teacher_scores * np.log(predictions + epsilon)
                - (1.0 - teacher_scores) * np.log(1.0 - predictions + epsilon)
            )
            + 0.5 * l2_penalty * np.sum(theta ** 2)
        )
        loss_history.append(loss)

        error = predictions - teacher_scores
        grad_bias = float(np.mean(error))
        grad_scale = float(np.mean(error * attended_strength))
        grad_theta = np.zeros_like(theta)
        for relation_offset in range(relation_count):
            dz_dtheta = (
                output_scale
                * context_features[:, relation_offset]
                * attention[:, relation_offset]
                * (edge_features[:, relation_offset] - attended_strength)
            )
            grad_theta[relation_offset] = float(np.mean(error * dz_dtheta) + l2_penalty * theta[relation_offset])

        theta -= learning_rate * grad_theta
        output_scale -= learning_rate * grad_scale
        bias -= learning_rate * grad_bias

    return {
        "theta": theta,
        "output_scale": output_scale,
        "bias": bias,
        "loss_history": loss_history,
    }


def _sample_negative_edges(
    node_ids: list[str],
    positive_edges: set[tuple[str, str]],
    sample_size: int,
    random_seed: int,
) -> list[tuple[str, str]]:
    if sample_size <= 0 or len(node_ids) < 2:
        return []
    rng = np.random.default_rng(random_seed)
    negatives: set[tuple[str, str]] = set()
    max_attempts = max(sample_size * 20, 100)
    attempts = 0
    while len(negatives) < sample_size and attempts < max_attempts:
        idx_a = int(rng.integers(0, len(node_ids)))
        idx_b = int(rng.integers(0, len(node_ids)))
        attempts += 1
        if idx_a == idx_b:
            continue
        edge_key = tuple(sorted((node_ids[idx_a], node_ids[idx_b])))
        if edge_key in positive_edges or edge_key in negatives:
            continue
        negatives.add(edge_key)
    return sorted(negatives)


def _build_torch_training_dataset(
    learning_bundle: dict[str, object],
    teacher_scores: dict[tuple[str, str], float],
    config: ExperimentConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    edge_feature_map: dict[tuple[str, str], np.ndarray] = learning_bundle["edge_feature_map"]
    node_index: dict[str, int] = learning_bundle["node_index"]
    relation_context: np.ndarray = learning_bundle["relation_context"]
    ordered_nodes: list[str] = learning_bundle["ordered_nodes"]

    positive_edges = _sample_learning_edges(
        edge_feature_map,
        teacher_scores,
        max_samples=max(config.attention_max_samples, 1),
        random_seed=config.random_seed,
    )
    negative_count = int(max(len(positive_edges) * config.attention_negative_ratio, 0))
    negative_edges = _sample_negative_edges(
        ordered_nodes,
        set(edge_feature_map.keys()),
        negative_count,
        config.random_seed + 17,
    )

    edge_rows: list[np.ndarray] = []
    context_rows: list[np.ndarray] = []
    labels: list[float] = []
    for edge_key in positive_edges:
        raw_features = edge_feature_map[edge_key]
        normalized_features = _normalize_edge_feature_matrix(raw_features.reshape(1, -1))[0]
        source, target = edge_key
        source_index = node_index[source]
        target_index = node_index[target]
        context_vector = normalized_features + 0.5 * (
            relation_context[source_index] + relation_context[target_index]
        )
        edge_rows.append(normalized_features)
        context_rows.append(context_vector)
        labels.append(float(teacher_scores.get(edge_key, 0.0)))

    for edge_key in negative_edges:
        source, target = edge_key
        source_index = node_index[source]
        target_index = node_index[target]
        edge_rows.append(np.zeros(len(BASE_RELATIONS), dtype=float))
        context_rows.append(0.5 * (relation_context[source_index] + relation_context[target_index]))
        labels.append(0.0)

    return (
        np.asarray(edge_rows, dtype=float),
        np.asarray(context_rows, dtype=float),
        np.asarray(labels, dtype=float),
    )


def _train_relation_attention_torch_model(
    edge_features: np.ndarray,
    context_features: np.ndarray,
    teacher_scores: np.ndarray,
    *,
    epochs: int,
    learning_rate: float,
    l2_penalty: float,
    hidden_dim: int,
    random_seed: int,
) -> dict[str, object]:
    if torch is None or F is None:
        raise RuntimeError("torch backend requested but torch is not installed")

    torch.manual_seed(random_seed)
    edge_tensor = torch.tensor(edge_features, dtype=torch.float32)
    context_tensor = torch.tensor(context_features, dtype=torch.float32)
    label_tensor = torch.tensor(teacher_scores, dtype=torch.float32).unsqueeze(1)
    relation_count = edge_features.shape[1]

    class RelationAttentionModel(torch.nn.Module):
        def __init__(self, relation_dim: int, hidden_size: int) -> None:
            super().__init__()
            self.relation_dim = relation_dim
            self.query = torch.nn.Linear(relation_dim, relation_dim)
            self.key = torch.nn.Linear(relation_dim, relation_dim)
            self.relation_bias = torch.nn.Parameter(torch.zeros(relation_dim))
            self.output = torch.nn.Sequential(
                torch.nn.Linear(relation_dim * 2, hidden_size),
                torch.nn.ReLU(),
                torch.nn.Linear(hidden_size, 1),
            )

        def forward(self, edge_x: torch.Tensor, context_x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            q = self.query(context_x)
            k = self.key(edge_x + context_x)
            attention_logits = (q * k) / max(self.relation_dim, 1) ** 0.5
            attention_logits = attention_logits + self.relation_bias
            attention = torch.softmax(attention_logits, dim=1)
            aggregated = attention * edge_x
            score = self.output(torch.cat([aggregated, context_x], dim=1))
            return score, attention

    hidden_size = max(hidden_dim, 4)
    model = RelationAttentionModel(relation_count, hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=l2_penalty)
    loss_history: list[float] = []

    for _ in range(max(epochs, 1)):
        optimizer.zero_grad(set_to_none=True)
        logits, _ = model(edge_tensor, context_tensor)
        loss = F.binary_cross_entropy_with_logits(logits, label_tensor)
        loss.backward()
        optimizer.step()
        loss_history.append(float(loss.detach().cpu().item()))

    with torch.no_grad():
        _, attention = model(edge_tensor, context_tensor)
    attention_mean = attention.mean(dim=0).cpu().numpy()
    relation_bias = model.relation_bias.detach().cpu().numpy()

    return {
        "backend": "torch",
        "model": model,
        "loss_history": loss_history,
        "average_attention": {
            relation_name: float(attention_mean[index])
            for index, relation_name in enumerate(BASE_RELATIONS)
        },
        "relation_logits": {
            relation_name: float(relation_bias[index])
            for index, relation_name in enumerate(BASE_RELATIONS)
        },
    }


def _apply_relation_attention_torch_model(
    edge_feature_map: dict[tuple[str, str], np.ndarray],
    node_index: dict[str, int],
    relation_context: np.ndarray,
    model: object,
) -> tuple[Counter[tuple[str, str]], float]:
    assert torch is not None
    edge_weights: Counter[tuple[str, str]] = Counter()
    score_sum = 0.0

    for edge_key, raw_features in edge_feature_map.items():
        source, target = edge_key
        source_index = node_index[source]
        target_index = node_index[target]
        normalized_features = _normalize_edge_feature_matrix(raw_features.reshape(1, -1))[0]
        context_vector = normalized_features + 0.5 * (
            relation_context[source_index] + relation_context[target_index]
        )
        with torch.no_grad():
            edge_tensor = torch.tensor(normalized_features.reshape(1, -1), dtype=torch.float32)
            context_tensor = torch.tensor(context_vector.reshape(1, -1), dtype=torch.float32)
            logits, attention = model(edge_tensor, context_tensor)
            probability = torch.sigmoid(logits).cpu().item()
            attention_vector = attention.cpu().numpy()[0]
        fused_weight = float(np.sum(attention_vector * raw_features) * probability)
        if fused_weight <= 0.0:
            continue
        edge_weights[edge_key] = fused_weight
        score_sum += fused_weight

    return edge_weights, score_sum


def _apply_relation_attention_model(
    edge_feature_map: dict[tuple[str, str], np.ndarray],
    node_index: dict[str, int],
    relation_context: np.ndarray,
    parameters: dict[str, object],
) -> tuple[Counter[tuple[str, str]], dict[str, float], dict[str, float], float]:
    theta = np.asarray(parameters["theta"], dtype=float)
    edge_weights: Counter[tuple[str, str]] = Counter()
    attention_sum = np.zeros(len(BASE_RELATIONS), dtype=float)
    score_sum = 0.0

    if not edge_feature_map:
        return edge_weights, {}, {}, score_sum

    for edge_key, raw_features in edge_feature_map.items():
        source, target = edge_key
        source_index = node_index[source]
        target_index = node_index[target]
        normalized_features = _normalize_edge_feature_matrix(raw_features.reshape(1, -1))[0]
        context_vector = normalized_features + 0.5 * (
            relation_context[source_index] + relation_context[target_index]
        )
        logits = context_vector * theta
        attention = _softmax_rows(logits.reshape(1, -1))[0]
        fused_weight = float(np.sum(attention * raw_features))
        if fused_weight <= 0.0:
            continue
        edge_weights[edge_key] = fused_weight
        attention_sum += attention
        score_sum += fused_weight

    total_attention = float(np.sum(attention_sum))
    average_attention = {
        relation_name: float(attention_sum[index] / total_attention) if total_attention > 0.0 else 0.0
        for index, relation_name in enumerate(BASE_RELATIONS)
    }
    relation_logits = {
        relation_name: float(theta[index])
        for index, relation_name in enumerate(BASE_RELATIONS)
    }
    return edge_weights, average_attention, relation_logits, score_sum


def _summarize_graph(
    method: str,
    relation_names: tuple[str, ...],
    edge_weights: Counter[tuple[str, str]],
    *,
    event_count: int,
    filtered_objects: list[dict[str, int | str]],
    pair_count: int,
    relation_breakdown: dict[str, float] | None = None,
    learning_metadata: dict[str, object] | None = None,
) -> RelationResult:
    graph = nx.Graph()
    for (source, target), weight in edge_weights.items():
        graph.add_edge(source, target, weight=float(weight))

    if graph.number_of_nodes() == 0:
        components: list[set[str]] = []
        cluster_sizes: list[int] = []
        communities: list[set[str]] = []
        modularity_score = None
    else:
        components = sorted(nx.connected_components(graph), key=len, reverse=True)
        communities = [set(map(str, community)) for community in greedy_modularity_communities(graph, weight="weight")]
        cluster_sizes = sorted((len(community) for community in communities), reverse=True)
        modularity_score = round(float(modularity(graph, communities, weight="weight")), 6) if communities else None

    edge_weight_values = list(edge_weights.values())
    top_objects = [
        {
            "object_id": item["object_id"],
            "event_count": int(item["event_count"]),
            "account_count": int(item["account_count"]),
        }
        for item in filtered_objects[:10]
    ]

    catalog = METHOD_CATALOG[method]
    return RelationResult(
        method=method,
        label=str(catalog["label"]),
        paper_anchor=str(catalog["paper_anchor"]),
        relation_names=relation_names,
        event_count=event_count,
        filtered_object_count=len(filtered_objects),
        pair_count=pair_count,
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        component_count=len(components),
        cluster_count=len(cluster_sizes),
        largest_component_size=len(components[0]) if components else 0,
        largest_cluster_size=cluster_sizes[0] if cluster_sizes else 0,
        avg_edge_weight=round(sum(edge_weight_values) / len(edge_weight_values), 6) if edge_weight_values else 0.0,
        modularity_score=modularity_score,
        top_nodes=_rank_top_nodes(graph),
        top_edges=_rank_top_edges(edge_weights),
        top_objects=top_objects,
        component_sizes=[len(component) for component in components[:10]],
        cluster_sizes=cluster_sizes[:10],
        relation_breakdown=relation_breakdown,
        learning_metadata=learning_metadata,
        edge_weights=edge_weights,
    )


def run_relation_benchmark(
    connection: sqlite3.Connection,
    config: ExperimentConfig,
    relation_name: str,
) -> RelationResult:
    filtered_objects = _iter_filtered_objects(
        connection,
        relation_name,
        min_accounts_per_object=config.min_accounts_per_object,
        max_accounts_per_object=config.max_accounts_per_object,
        min_events_per_object=config.min_events_per_object,
    )
    edge_weights: Counter[tuple[str, str]] = Counter()
    object_pair_counts: Counter[str] = Counter()
    pair_count = 0

    query = connection.execute(
        """
        SELECT e.object_id, e.ts, e.account_id, e.content_id
        FROM events AS e
        JOIN object_support AS s
          ON e.relation = s.relation
         AND e.object_id = s.object_id
        WHERE e.relation = ?
          AND s.account_count >= ?
          AND s.account_count <= ?
          AND s.event_count >= ?
        ORDER BY e.object_id ASC, e.ts ASC, e.account_id ASC, e.content_id ASC
        """,
        (
            relation_name,
            config.min_accounts_per_object,
            config.max_accounts_per_object,
            config.min_events_per_object,
        ),
    )

    current_object = ""
    current_events: list[tuple[int, str, str]] = []
    for object_id, ts, account_id, content_id in query.fetchall():
        object_id = str(object_id)
        if current_object and object_id != current_object:
            pair_count += _update_pairs_for_object(
                current_object,
                current_events,
                time_window_seconds=config.time_window_seconds,
                edge_weights=edge_weights,
                object_pair_counts=object_pair_counts,
            )
            current_events = []
        current_object = object_id
        current_events.append((int(ts), str(account_id), str(content_id)))

    if current_object and current_events:
        pair_count += _update_pairs_for_object(
            current_object,
            current_events,
            time_window_seconds=config.time_window_seconds,
            edge_weights=edge_weights,
            object_pair_counts=object_pair_counts,
        )

    filtered_objects = [
        {
            **item,
            "pair_count": int(object_pair_counts.get(str(item["object_id"]), 0)),
        }
        for item in filtered_objects
    ]
    filtered_objects.sort(
        key=lambda item: (
            -int(item["pair_count"]),
            -int(item["event_count"]),
            -int(item["account_count"]),
            str(item["object_id"]),
        )
    )

    event_count_row = connection.execute(
        "SELECT COUNT(*) FROM events WHERE relation = ?",
        (relation_name,),
    ).fetchone()
    event_count = int(event_count_row[0]) if event_count_row else 0

    return _summarize_graph(
        relation_name,
        (relation_name,),
        edge_weights,
        event_count=event_count,
        filtered_objects=filtered_objects,
        pair_count=pair_count,
    )


def run_multi_relation_static_benchmark(
    config: ExperimentConfig,
    relation_results: dict[str, RelationResult],
) -> RelationResult:
    relation_weights = dict(DEFAULT_RELATION_WEIGHTS)
    if config.relation_weights:
        relation_weights.update(config.relation_weights)

    combined_edges: Counter[tuple[str, str]] = Counter()
    combined_objects: list[dict[str, object]] = []
    relation_breakdown: dict[str, float] = {}
    event_count = 0
    filtered_object_count = 0
    pair_count = 0

    for relation_name in BASE_RELATIONS:
        result = relation_results.get(relation_name)
        if result is None or result.edge_weights is None:
            continue
        weight_factor = float(relation_weights.get(relation_name, 1.0))
        relation_breakdown[relation_name] = weight_factor
        event_count += result.event_count
        filtered_object_count += result.filtered_object_count
        pair_count += result.pair_count
        for edge_key, edge_weight in result.edge_weights.items():
            combined_edges[edge_key] += edge_weight * weight_factor
        for item in result.top_objects[:5]:
            combined_objects.append(
                {
                    "relation": relation_name,
                    **item,
                }
            )

    combined_objects.sort(
        key=lambda item: (
            -int(item.get("pair_count", 0)),
            -int(item.get("event_count", 0)),
            str(item.get("object_id", "")),
        )
    )

    summary = _summarize_graph(
        "multi_relation_static",
        tuple(relation_breakdown.keys()),
        combined_edges,
        event_count=event_count,
        filtered_objects=combined_objects,
        pair_count=pair_count,
        relation_breakdown=relation_breakdown,
        learning_metadata={
            "mode": "static_relation_weight_fusion",
            "relation_weights": relation_breakdown,
        },
    )
    summary.filtered_object_count = filtered_object_count
    return summary


def run_multi_relation_benchmark(
    config: ExperimentConfig,
    relation_results: dict[str, RelationResult],
) -> RelationResult:
    static_result = run_multi_relation_static_benchmark(config, relation_results)
    learning_bundle = _build_relation_learning_bundle(relation_results)
    if learning_bundle is None:
        static_result.method = "multi_relation"
        static_result.label = str(METHOD_CATALOG["multi_relation"]["label"])
        static_result.paper_anchor = str(METHOD_CATALOG["multi_relation"]["paper_anchor"])
        static_result.learning_metadata = {
            "mode": "learned_relation_attention",
            "fallback": "no_relation_edges",
        }
        return static_result

    active_relations = list(learning_bundle["active_relations"])
    edge_feature_map = learning_bundle["edge_feature_map"]
    if len(active_relations) < 2 or len(edge_feature_map) < 2:
        static_result.method = "multi_relation"
        static_result.label = str(METHOD_CATALOG["multi_relation"]["label"])
        static_result.paper_anchor = str(METHOD_CATALOG["multi_relation"]["paper_anchor"])
        static_result.learning_metadata = {
            "mode": "learned_relation_attention",
            "fallback": "insufficient_relation_or_edge_support",
            "active_relations": active_relations,
            "edge_count": len(edge_feature_map),
        }
        return static_result

    relation_weights = dict(DEFAULT_RELATION_WEIGHTS)
    if config.relation_weights:
        relation_weights.update(config.relation_weights)
    static_combined_edges = _build_static_combined_edges(relation_results, relation_weights)
    teacher_scores = _compute_teacher_scores(edge_feature_map, static_combined_edges)
    node_index = learning_bundle["node_index"]
    relation_context = learning_bundle["relation_context"]
    selected_backend = config.attention_backend
    if selected_backend == "auto":
        selected_backend = "torch" if torch is not None else "numpy"

    if selected_backend == "torch":
        edge_matrix, context_matrix, teacher_vector = _build_torch_training_dataset(
            learning_bundle,
            teacher_scores,
            config,
        )
        torch_parameters = _train_relation_attention_torch_model(
            edge_matrix,
            context_matrix,
            teacher_vector,
            epochs=config.attention_epochs,
            learning_rate=config.attention_learning_rate,
            l2_penalty=config.attention_l2,
            hidden_dim=config.attention_hidden_dim,
            random_seed=config.random_seed,
        )
        learned_edges, learned_weight_sum = _apply_relation_attention_torch_model(
            edge_feature_map,
            node_index,
            relation_context,
            torch_parameters["model"],
        )
        average_attention = dict(torch_parameters["average_attention"])
        relation_logits = dict(torch_parameters["relation_logits"])
        final_loss = float(torch_parameters["loss_history"][-1]) if torch_parameters["loss_history"] else 0.0
        sampled_edge_count = int(edge_matrix.shape[0])
        teacher_score_mean = float(np.mean(teacher_vector)) if teacher_vector.size else 0.0
    else:
        sampled_edge_keys = _sample_learning_edges(
            edge_feature_map,
            teacher_scores,
            max_samples=max(config.attention_max_samples, 1),
            random_seed=config.random_seed,
        )

        edge_rows = []
        context_rows = []
        teacher_rows = []
        for edge_key in sampled_edge_keys:
            raw_features = edge_feature_map[edge_key]
            normalized_features = _normalize_edge_feature_matrix(raw_features.reshape(1, -1))[0]
            source, target = edge_key
            source_index = node_index[source]
            target_index = node_index[target]
            context_vector = normalized_features + 0.5 * (
                relation_context[source_index] + relation_context[target_index]
            )
            edge_rows.append(normalized_features)
            context_rows.append(context_vector)
            teacher_rows.append(float(teacher_scores.get(edge_key, 0.0)))

        edge_matrix = np.asarray(edge_rows, dtype=float)
        context_matrix = np.asarray(context_rows, dtype=float)
        teacher_vector = np.asarray(teacher_rows, dtype=float)
        parameters = _train_relation_attention_model(
            edge_matrix,
            context_matrix,
            teacher_vector,
            epochs=config.attention_epochs,
            learning_rate=config.attention_learning_rate,
            l2_penalty=config.attention_l2,
        )
        learned_edges, average_attention, relation_logits, learned_weight_sum = _apply_relation_attention_model(
            edge_feature_map,
            node_index,
            relation_context,
            parameters,
        )
        final_loss = float(parameters["loss_history"][-1]) if parameters["loss_history"] else 0.0
        sampled_edge_count = len(sampled_edge_keys)
        teacher_score_mean = float(np.mean(teacher_vector)) if teacher_vector.size else 0.0

    combined_objects: list[dict[str, object]] = []
    event_count = 0
    filtered_object_count = 0
    pair_count = 0
    for relation_name in BASE_RELATIONS:
        result = relation_results.get(relation_name)
        if result is None:
            continue
        event_count += result.event_count
        filtered_object_count += result.filtered_object_count
        pair_count += result.pair_count
        relation_attention = float(average_attention.get(relation_name, 0.0))
        for item in result.top_objects[:5]:
            combined_objects.append(
                {
                    "relation": relation_name,
                    "attention": relation_attention,
                    **item,
                }
            )

    combined_objects.sort(
        key=lambda item: (
            -float(item.get("attention", 0.0)),
            -int(item.get("pair_count", 0)),
            -int(item.get("event_count", 0)),
            str(item.get("object_id", "")),
        )
    )

    summary = _summarize_graph(
        "multi_relation",
        tuple(BASE_RELATIONS),
        learned_edges,
        event_count=event_count,
        filtered_objects=combined_objects,
        pair_count=pair_count,
        relation_breakdown=average_attention,
        learning_metadata={
            "mode": "learned_relation_attention",
            "backend": selected_backend,
            "teacher_graph": "static_multi_relation_community_overlap",
            "relation_logits": relation_logits,
            "teacher_score_mean": teacher_score_mean,
            "sampled_edge_count": sampled_edge_count,
            "trained_edge_count": len(edge_feature_map),
            "attention_epochs": config.attention_epochs,
            "attention_learning_rate": config.attention_learning_rate,
            "attention_l2": config.attention_l2,
            "attention_hidden_dim": config.attention_hidden_dim,
            "attention_negative_ratio": config.attention_negative_ratio,
            "final_loss": final_loss,
            "static_reference_weight_sum": float(sum(static_combined_edges.values())),
            "learned_weight_sum": learned_weight_sum,
        },
    )
    summary.filtered_object_count = filtered_object_count
    return summary


def export_relation_result(output_dir: Path, result: RelationResult) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = output_dir / f"{result.method}_nodes.csv"
    edges_path = output_dir / f"{result.method}_edges.csv"
    summary_path = output_dir / f"{result.method}_summary.json"

    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "method": result.method,
                "label": result.label,
                "paper_anchor": result.paper_anchor,
                "relation_names": list(result.relation_names),
                "event_count": result.event_count,
                "filtered_object_count": result.filtered_object_count,
                "pair_count": result.pair_count,
                "node_count": result.node_count,
                "edge_count": result.edge_count,
                "component_count": result.component_count,
                "cluster_count": result.cluster_count,
                "largest_component_size": result.largest_component_size,
                "largest_cluster_size": result.largest_cluster_size,
                "avg_edge_weight": result.avg_edge_weight,
                "modularity_score": result.modularity_score,
                "top_nodes": result.top_nodes,
                "top_edges": result.top_edges,
                "top_objects": result.top_objects,
                "component_sizes": result.component_sizes,
                "cluster_sizes": result.cluster_sizes,
                "relation_breakdown": result.relation_breakdown,
                "learning_metadata": result.learning_metadata,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    with nodes_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["account_id", "weighted_degree", "degree"])
        writer.writeheader()
        writer.writerows(result.top_nodes)

    with edges_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "target", "weight"])
        writer.writeheader()
        writer.writerows(result.top_edges if result.edge_weights is None else [
            {
                "source": source,
                "target": target,
                "weight": float(weight),
            }
            for (source, target), weight in result.edge_weights.most_common()
        ])


def run_twitter_io_experiment(config: ExperimentConfig) -> dict[str, object]:
    ingest_summary = ingest_twitter_io_archive(config)
    sqlite_path = Path(str(ingest_summary["sqlite_path"]))

    relation_results: dict[str, RelationResult] = {}
    requested_methods = set(config.methods)
    composite_methods = {"multi_relation", "multi_relation_static"}
    required_base_methods = {method for method in requested_methods if method not in composite_methods}
    if requested_methods & composite_methods:
        required_base_methods.update(BASE_RELATIONS)
    connection = sqlite3.connect(sqlite_path)
    try:
        for method in sorted(required_base_methods):
            relation_results[method] = run_relation_benchmark(connection, config, method)

        if "multi_relation_static" in requested_methods:
            relation_results["multi_relation_static"] = run_multi_relation_static_benchmark(config, relation_results)
        if "multi_relation" in requested_methods:
            relation_results["multi_relation"] = run_multi_relation_benchmark(config, relation_results)
    finally:
        connection.close()

    method_summaries = {}
    for method_name, result in relation_results.items():
        if method_name not in requested_methods and method_name not in DEFAULT_METHODS:
            continue
        if method_name not in requested_methods and (requested_methods & composite_methods):
            continue
        export_relation_result(config.output_dir, result)
        method_summaries[method_name] = {
            "method": result.method,
            "label": result.label,
            "paper_anchor": result.paper_anchor,
            "relation_names": list(result.relation_names),
            "event_count": result.event_count,
            "filtered_object_count": result.filtered_object_count,
            "pair_count": result.pair_count,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "component_count": result.component_count,
            "cluster_count": result.cluster_count,
            "largest_component_size": result.largest_component_size,
            "largest_cluster_size": result.largest_cluster_size,
            "avg_edge_weight": result.avg_edge_weight,
            "modularity_score": result.modularity_score,
            "component_sizes": result.component_sizes,
            "cluster_sizes": result.cluster_sizes,
            "top_nodes": result.top_nodes,
            "top_edges": result.top_edges,
            "top_objects": result.top_objects,
            "relation_breakdown": result.relation_breakdown,
            "learning_metadata": result.learning_metadata,
        }

    summary = {
        "config": {
            "tweets_zip_path": str(config.tweets_zip_path),
            "output_dir": str(config.output_dir),
            "methods": list(config.methods),
            "languages": list(config.languages),
            "time_window_seconds": config.time_window_seconds,
            "min_accounts_per_object": config.min_accounts_per_object,
            "max_accounts_per_object": config.max_accounts_per_object,
            "min_events_per_object": config.min_events_per_object,
            "limit_rows": config.limit_rows,
            "relation_weights": config.relation_weights or DEFAULT_RELATION_WEIGHTS,
            "attention_epochs": config.attention_epochs,
            "attention_learning_rate": config.attention_learning_rate,
            "attention_l2": config.attention_l2,
            "attention_max_samples": config.attention_max_samples,
            "random_seed": config.random_seed,
        },
        "ingest_summary": ingest_summary,
        "method_summaries": method_summaries,
    }
    with (config.output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    return summary
