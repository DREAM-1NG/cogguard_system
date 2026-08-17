from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from app.config import PROJECT_ROOT
from app.core.coordination_baseline.io_reproduction import (
    DEFAULT_RELATIONS,
    LABEL_COLUMNS,
    normalize_event_table,
    read_event_table,
)

SOCGFM_PRECOMPUTE_SCHEMA_VERSION = "cogguard.socgfm-china-local-precompute/v1"
SOCGFM_INFERENCE_MODE = "precomputed_member_probability_cluster_aggregation"
SOCGFM_CLAIM_SCOPE = "account_level_io_membership_to_cluster_proxy"
SOCGFM_MODEL_ROLE = "primary_socgfm_cross_attention"
SOCGFM_MODEL_VERSION = "socgfm_cross_attention/v1"
SOCGFM_CHECKPOINT_FAMILY = "official_china_socgfm_cross_attention_sage"
SOCGFM_TEXT_MODEL = "sentence-transformers/all-mpnet-base-v2"
SOCGFM_TEXT_DIM = 768
SOCGFM_STRUCT_DIM = 128
SOCGFM_LATENT_DIM = 128
SOCGFM_DEFAULT_CHECKPOINT_ROOT = (
    PROJECT_ROOT
    / "output"
    / "coordination_two_stage_reproduction"
    / "iohunter-socgfm-official-sage-matrix-20260812-194000"
    / "china"
)
SOCGFM_DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "coordination_two_stage_reproduction"
_DIRECT_RELATIONS = frozenset({"retweet_target", "reply_target", "quote_target", "mention_target"})
_OBJECT_RELATION_HINTS = (
    ("url", "url_share"),
    ("link", "url_share"),
    ("hashtag", "hashtag_share"),
    ("topic", "hashtag_share"),
    ("tag", "hashtag_share"),
    ("mention", "mention_target"),
    ("reply", "reply_target"),
    ("quote", "quote_target"),
    ("retweet", "retweet_target"),
    ("repost", "retweet_target"),
)


@dataclass(frozen=True, slots=True)
class SocGFMLocalGraphInputs:
    account_keys: tuple[str, ...]
    account_ids: tuple[str, ...]
    platforms: tuple[str, ...]
    node_mapping: dict[str, int]
    account_texts: dict[str, str]
    text_features: np.ndarray
    struct_features: np.ndarray
    edge_index: np.ndarray
    label_by_account_key: dict[str, int | None]
    feature_audit: dict[str, Any]


TextEncoder = Callable[[list[str]], np.ndarray | Sequence[Sequence[float]]]
InferenceRunner = Callable[[SocGFMLocalGraphInputs, Sequence[Path]], Sequence[np.ndarray]]


def discover_china_checkpoint_paths(root: str | Path | None = None) -> list[Path]:
    """Return the five official China CrossAttention/SAGE split checkpoints."""

    search_root = Path(root or SOCGFM_DEFAULT_CHECKPOINT_ROOT).expanduser().resolve()
    if search_root.is_file():
        candidates = [search_root]
    else:
        direct = search_root / "best_models_f1_macro"
        if direct.exists():
            candidates = sorted(direct.glob("model*.pth"), key=_model_path_sort_key)
        else:
            candidates = sorted(
                search_root.rglob("best_models_f1_macro/model*.pth"),
                key=_model_path_sort_key,
            )
            if not candidates:
                candidates = sorted(search_root.rglob("model*.pth"), key=_model_path_sort_key)
    expected = [f"model{index}.pth" for index in range(5)]
    by_name = {path.name: path for path in candidates}
    if sorted(by_name) != expected:
        raise FileNotFoundError(
            "Official China SocGFM checkpoint root must contain exactly model0.pth through model4.pth "
            f"under best_models_f1_macro; found {sorted(by_name)} in {search_root}"
        )
    return [by_name[name].resolve() for name in expected]


def hash_checkpoint_files(paths: Sequence[str | Path]) -> dict[str, str]:
    return {Path(path).name: _sha256_file(Path(path)) for path in paths}


def load_socgfm_local_events(
    *,
    event_table: str | Path | None = None,
    snapshot_json: str | Path | None = None,
) -> pd.DataFrame:
    sources = [value is not None for value in (event_table, snapshot_json)]
    if sum(sources) != 1:
        raise ValueError("Provide exactly one local SocGFM input: event_table or snapshot_json")
    if event_table is not None:
        events = read_event_table(Path(event_table).expanduser().resolve())
    else:
        events = _events_from_snapshot_json(Path(snapshot_json or "").expanduser().resolve())
    if "platform" not in events.columns:
        events["platform"] = "local"
    events["platform"] = events["platform"].fillna("").astype(str).map(lambda value: value.strip().lower() or "local")
    events["account_key"] = [
        _account_key(platform, account_id)
        for platform, account_id in zip(events["platform"], events["account_id"], strict=False)
    ]
    return events


def prepare_socgfm_local_graph_inputs(
    events: pd.DataFrame,
    *,
    text_encoder: TextEncoder | None = None,
    seed: int = 42,
) -> SocGFMLocalGraphInputs:
    normalized = normalize_event_table(events)
    if "platform" not in normalized.columns:
        normalized["platform"] = "local"
    normalized["platform"] = normalized["platform"].fillna("").astype(str).map(lambda value: value.strip().lower() or "local")
    normalized["account_key"] = [
        _account_key(platform, account_id)
        for platform, account_id in zip(normalized["platform"], normalized["account_id"], strict=False)
    ]
    rows = normalized[normalized["account_key"].astype(str).str.len() > 0].copy()
    if rows.empty:
        raise ValueError("SocGFM local precompute requires at least one account row")

    account_keys = tuple(sorted(set(rows["account_key"].astype(str))))
    node_mapping = {account_key: index for index, account_key in enumerate(account_keys)}
    account_ids = tuple(_account_id_from_key(account_key) for account_key in account_keys)
    platforms = tuple(_platform_from_key(account_key) for account_key in account_keys)
    account_texts = _account_texts(rows, account_keys)
    if not any(text.strip() for text in account_texts.values()):
        raise ValueError("SocGFM local precompute requires non-empty account text for SBERT; TF-IDF fallback is forbidden")
    text_features, text_feature_source = encode_account_text_features(account_texts, account_keys, text_encoder=text_encoder)
    edge_index, edge_audit = _build_edge_index(rows, node_mapping, seed=seed)
    struct_features = _positional_degree_features(
        account_keys=account_keys,
        events=rows,
        edge_index=edge_index,
    )
    feature_audit = {
        "schema_version": SOCGFM_PRECOMPUTE_SCHEMA_VERSION,
        "account_count": len(account_keys),
        "event_count": int(len(rows)),
        "text_feature_source": text_feature_source,
        "text_feature_dim": int(text_features.shape[1]),
        "struct_feature_source": "positional_degree_local_128",
        "struct_feature_dim": int(struct_features.shape[1]),
        "missing_text_account_count": int(sum(1 for text in account_texts.values() if not text.strip())),
        "text_coverage": _safe_ratio(
            sum(1 for text in account_texts.values() if text.strip()),
            len(account_keys),
        ),
        **edge_audit,
    }
    return SocGFMLocalGraphInputs(
        account_keys=account_keys,
        account_ids=account_ids,
        platforms=platforms,
        node_mapping=node_mapping,
        account_texts=account_texts,
        text_features=text_features,
        struct_features=struct_features,
        edge_index=edge_index,
        label_by_account_key=_label_by_account_key(rows),
        feature_audit=feature_audit,
    )


def encode_account_text_features(
    account_texts: Mapping[str, str],
    account_keys: Sequence[str],
    *,
    text_encoder: TextEncoder | None = None,
) -> tuple[np.ndarray, str]:
    texts = [str(account_texts.get(account_key, "")) for account_key in account_keys]
    if text_encoder is None:
        text_encoder = _load_sbert_text_encoder()
        source = f"sbert:{SOCGFM_TEXT_MODEL}"
    else:
        source = "sbert:injected-test-encoder"
    matrix = np.asarray(text_encoder(texts), dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape != (len(texts), SOCGFM_TEXT_DIM):
        raise ValueError(
            f"SocGFM China checkpoint requires SBERT text features with shape "
            f"({len(texts)}, {SOCGFM_TEXT_DIM}); got {tuple(matrix.shape)}"
        )
    if not np.isfinite(matrix).all():
        raise ValueError("SBERT text features contain non-finite values")
    return matrix, source


def precompute_socgfm_china_local_detection(
    *,
    output_dir: str | Path,
    event_table: str | Path | None = None,
    snapshot_json: str | Path | None = None,
    events: pd.DataFrame | None = None,
    checkpoint_root: str | Path | None = None,
    text_encoder: TextEncoder | None = None,
    inference_runner: InferenceRunner | None = None,
    device: str = "auto",
    seed: int = 42,
    dataset_id: str | int | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir).expanduser().resolve()
    _require_g_drive(output_root)
    if events is None:
        local_events = load_socgfm_local_events(event_table=event_table, snapshot_json=snapshot_json)
    else:
        local_events = events.copy()
        if "platform" not in local_events.columns:
            local_events["platform"] = "local"
    checkpoint_paths = discover_china_checkpoint_paths(checkpoint_root)
    checkpoint_hashes = hash_checkpoint_files(checkpoint_paths)
    prepared = prepare_socgfm_local_graph_inputs(local_events, text_encoder=text_encoder, seed=seed)
    runner = inference_runner or _run_official_ensemble_forward
    split_scores = [np.asarray(scores, dtype=np.float32).reshape(-1) for scores in runner(prepared, checkpoint_paths, device=device)]
    if len(split_scores) != len(checkpoint_paths):
        raise ValueError("SocGFM inference runner must return one score vector per checkpoint")
    for index, scores in enumerate(split_scores):
        if scores.shape != (len(prepared.account_keys),):
            raise ValueError(
                f"SocGFM checkpoint {checkpoint_paths[index].name} returned score shape {tuple(scores.shape)}, "
                f"expected {(len(prepared.account_keys),)}"
            )
        if not np.isfinite(scores).all():
            raise ValueError(f"SocGFM checkpoint {checkpoint_paths[index].name} returned non-finite scores")
    stacked = np.vstack([np.clip(scores, 0.0, 1.0) for scores in split_scores])
    ensemble_scores = np.mean(stacked, axis=0)
    output_root.mkdir(parents=True, exist_ok=True)

    predictions = _prediction_rows(prepared, ensemble_scores)
    _write_predictions_csv(output_root / "predictions.csv", predictions)
    _write_node_mapping_csv(output_root / "node_mapping.csv", prepared)
    feature_audit = {
        **prepared.feature_audit,
        "checkpoint_count": len(checkpoint_paths),
        "checkpoint_family": SOCGFM_CHECKPOINT_FAMILY,
        "score_mean": round(float(np.mean(ensemble_scores)), 12),
        "score_max": round(float(np.max(ensemble_scores)), 12),
    }
    _write_json(output_root / "feature_audit.json", feature_audit)
    _write_json(output_root / "checkpoint_hashes.json", checkpoint_hashes)
    manifest = {
        "schema_version": SOCGFM_PRECOMPUTE_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": str(dataset_id) if dataset_id is not None else None,
        "checkpoint_family": SOCGFM_CHECKPOINT_FAMILY,
        "checkpoint_paths": [str(path) for path in checkpoint_paths],
        "checkpoint_hashes": checkpoint_hashes,
        "prediction_path": str(output_root / "predictions.csv"),
        "node_mapping_path": str(output_root / "node_mapping.csv"),
        "feature_audit_path": str(output_root / "feature_audit.json"),
        "account_count": len(prepared.account_keys),
        "prediction_count": len(predictions),
        "inference_mode": SOCGFM_INFERENCE_MODE,
        "claim_scope": SOCGFM_CLAIM_SCOPE,
        "model_role": SOCGFM_MODEL_ROLE,
        "model_version": SOCGFM_MODEL_VERSION,
        "online_neural_forward": False,
        "neural_forward_executed_offline": True,
        "unsupported_claims": ["group_level_harmful_coordination_f1"],
        "text_feature_source": prepared.feature_audit["text_feature_source"],
        "struct_feature_source": prepared.feature_audit["struct_feature_source"],
        "device": device,
        "seed": int(seed),
    }
    _write_json(output_root / "prediction_manifest.json", manifest)
    detection_summary = _detection_summary(prepared, predictions, manifest, feature_audit)
    _write_json(output_root / "detection_summary.json", detection_summary)
    return {
        "output_dir": str(output_root),
        "prediction_path": str(output_root / "predictions.csv"),
        "prediction_manifest_path": str(output_root / "prediction_manifest.json"),
        "node_mapping_path": str(output_root / "node_mapping.csv"),
        "feature_audit_path": str(output_root / "feature_audit.json"),
        "checkpoint_hashes_path": str(output_root / "checkpoint_hashes.json"),
        "prediction_count": len(predictions),
        "account_count": len(prepared.account_keys),
        "checkpoint_count": len(checkpoint_paths),
        "checkpoint_family": SOCGFM_CHECKPOINT_FAMILY,
        "inference_mode": SOCGFM_INFERENCE_MODE,
        "claim_scope": SOCGFM_CLAIM_SCOPE,
        "online_neural_forward": False,
        "neural_forward_executed_offline": True,
    }


def default_socgfm_local_precompute_output_dir(timestamp: str | None = None) -> Path:
    suffix = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return SOCGFM_DEFAULT_OUTPUT_ROOT / f"socgfm-china-local-precompute-{suffix}"


def _events_from_snapshot_json(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return normalize_event_table(pd.DataFrame(payload))
    if not isinstance(payload, Mapping):
        raise ValueError("snapshot_json must contain an EventSnapshot object or a list of event rows")
    rows: list[dict[str, Any]] = []
    for source_name in ("posts", "comments"):
        records = payload.get(source_name, [])
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                continue
            rows.append(_snapshot_record_to_event(record, source_name=source_name, index=index))
    if not rows:
        raise ValueError(f"snapshot_json contains no posts/comments rows: {path}")
    return normalize_event_table(pd.DataFrame(rows))


def _snapshot_record_to_event(record: Mapping[str, Any], *, source_name: str, index: int) -> dict[str, Any]:
    account_id = _first_text(
        record,
        "account_id",
        "author_id",
        "user_id",
        "uid",
        "author",
    )
    platform = _first_text(record, "platform", "source_platform", "platform_name", default="local")
    content_id = _first_text(
        record,
        "content_id",
        "post_id",
        "comment_id",
        "id",
        default=f"{source_name}-{index}",
    )
    content = _first_text(record, "content", "text", "body", "title", "desc", default="")
    timestamp = _first_text(record, "timestamp", "created_at", "time", default=0)
    url = _first_text(record, "url", "canonical_url", "link", "post_url", default="")
    target = _first_text(record, "target_id", "target_account_id", "reply_to", "reply_to_id", default="")
    relation = _first_text(record, "relation", "relation_type", "event_type", default="")
    if not relation:
        relation = "reply_target" if source_name == "comments" and target else "url_share" if url else "content"
    object_id = _first_text(record, "object_id", "object", "entity", default="")
    if not object_id:
        object_id = url or target or content_id
    return {
        "platform": platform,
        "account_id": account_id,
        "relation": relation,
        "object_id": object_id,
        "timestamp": timestamp,
        "content_id": content_id,
        "content": content,
        "target_account_id": target,
        "post_url": _first_text(record, "post_url", "url", "link", default=""),
    }


def _account_key(platform: Any, account_id: Any) -> str:
    platform_text = str(platform or "").strip().lower() or "local"
    account_text = str(account_id or "").strip()
    if not account_text:
        return ""
    if ":" in account_text:
        return account_text
    return f"{platform_text}:{account_text}"


def _platform_from_key(account_key: str) -> str:
    return account_key.split(":", 1)[0] if ":" in account_key else "local"


def _account_id_from_key(account_key: str) -> str:
    return account_key.split(":", 1)[1] if ":" in account_key else account_key


def _account_texts(events: pd.DataFrame, account_keys: Sequence[str]) -> dict[str, str]:
    text_column = "content" if "content" in events.columns else None
    if text_column is None:
        return {account_key: "" for account_key in account_keys}
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in events[["account_key", text_column]].itertuples(index=False):
        text = str(getattr(row, text_column) or "").strip()
        if text:
            grouped[str(row.account_key)].append(text)
    return {
        account_key: "\n".join(grouped.get(account_key, [])[:50])
        for account_key in account_keys
    }


def _label_by_account_key(events: pd.DataFrame) -> dict[str, int | None]:
    label_column = next((column for column in LABEL_COLUMNS if column in events.columns), None)
    if label_column is None:
        return {str(account_key): None for account_key in sorted(set(events["account_key"].astype(str)))}
    labels: dict[str, int | None] = {}
    for account_key, rows in events.groupby("account_key"):
        values = []
        for value in rows[label_column].tolist():
            try:
                values.append(int(value))
            except (TypeError, ValueError):
                continue
        labels[str(account_key)] = int(round(sum(values) / len(values))) if values else None
    return labels


def _build_edge_index(events: pd.DataFrame, node_mapping: Mapping[str, int], *, seed: int) -> tuple[np.ndarray, dict[str, Any]]:
    edge_pairs: set[tuple[int, int]] = set()
    evidence_edge_count = 0
    if {"relation", "object_id", "account_key"}.issubset(events.columns):
        grouped = events[events["relation"].astype(str).str.lower() != "profile"].groupby(["relation", "object_id"], dropna=False)
        for (_relation, _object_id), rows in grouped:
            accounts = sorted({str(value) for value in rows["account_key"].tolist() if str(value) in node_mapping})
            if len(accounts) < 2:
                continue
            for left_index, left in enumerate(accounts):
                for right in accounts[left_index + 1 :]:
                    _add_bidirectional(edge_pairs, node_mapping[left], node_mapping[right])
                    evidence_edge_count += 1
    if {"relation", "target_account_id", "account_key"}.issubset(events.columns):
        for row in events.itertuples(index=False):
            relation = str(getattr(row, "relation", "")).lower()
            if relation not in _DIRECT_RELATIONS:
                continue
            source_key = str(getattr(row, "account_key", ""))
            target = str(getattr(row, "target_account_id", "") or "").strip()
            if not target:
                continue
            target_key = _account_key(getattr(row, "platform", "local"), target)
            if source_key in node_mapping and target_key in node_mapping:
                _add_bidirectional(edge_pairs, node_mapping[source_key], node_mapping[target_key])
                evidence_edge_count += 1
    node_count = len(node_mapping)
    connected = {node for pair in edge_pairs for node in pair}
    isolated = [index for index in range(node_count) if index not in connected]
    for index in isolated:
        edge_pairs.add((index, index))
    if not edge_pairs and node_count == 1:
        edge_pairs.add((0, 0))
    if not edge_pairs:
        rng = np.random.default_rng(seed)
        order = list(range(node_count))
        rng.shuffle(order)
        for left, right in zip(order, order[1:], strict=False):
            _add_bidirectional(edge_pairs, left, right)
    ordered = sorted(edge_pairs)
    edge_index = np.asarray(ordered, dtype=np.int64).T if ordered else np.zeros((2, 0), dtype=np.int64)
    return edge_index, {
        "evidence_edge_pair_count": int(evidence_edge_count),
        "edge_index_edge_count": int(edge_index.shape[1]),
        "isolated_node_repair_count": int(len(isolated)),
        "isolated_node_repair_policy": "deterministic_self_loop",
    }


def _add_bidirectional(edges: set[tuple[int, int]], left: int, right: int) -> None:
    if left == right:
        edges.add((left, right))
        return
    edges.add((left, right))
    edges.add((right, left))


def _positional_degree_features(
    *,
    account_keys: Sequence[str],
    events: pd.DataFrame,
    edge_index: np.ndarray,
) -> np.ndarray:
    node_count = len(account_keys)
    if node_count == 0:
        return np.zeros((0, SOCGFM_STRUCT_DIM), dtype=np.float32)
    degrees = np.zeros(node_count, dtype=np.float32)
    if edge_index.size:
        for source, target in edge_index.T:
            if int(source) != int(target):
                degrees[int(source)] += 1.0
    event_counts = np.zeros(node_count, dtype=np.float32)
    object_counts = np.zeros(node_count, dtype=np.float32)
    relation_counts = np.zeros(node_count, dtype=np.float32)
    index_by_key = {account_key: index for index, account_key in enumerate(account_keys)}
    for account_key, rows in events.groupby("account_key"):
        index = index_by_key.get(str(account_key))
        if index is None:
            continue
        event_counts[index] = float(len(rows))
        object_counts[index] = float(rows["object_id"].astype(str).nunique()) if "object_id" in rows else 0.0
        relation_counts[index] = float(rows["relation"].astype(str).nunique()) if "relation" in rows else 0.0
    base = np.vstack(
        [
            _normalize(degrees),
            _normalize(np.log1p(degrees)),
            _normalize(event_counts),
            _normalize(np.log1p(event_counts)),
            _normalize(object_counts),
            _normalize(relation_counts),
        ]
    ).T
    features = np.zeros((node_count, SOCGFM_STRUCT_DIM), dtype=np.float32)
    width = min(base.shape[1], SOCGFM_STRUCT_DIM)
    features[:, :width] = base[:, :width]
    positions = np.arange(node_count, dtype=np.float32).reshape(-1, 1)
    for column in range(width, SOCGFM_STRUCT_DIM):
        scale = 1.0 / float(column - width + 1)
        if column % 2 == 0:
            features[:, column] = np.sin(positions[:, 0] * scale)
        else:
            features[:, column] = np.cos(positions[:, 0] * scale)
    return features.astype(np.float32)


def _run_official_ensemble_forward(
    inputs: SocGFMLocalGraphInputs,
    checkpoint_paths: Sequence[Path],
    *,
    device: str = "auto",
) -> list[np.ndarray]:
    torch, nn, _ = _require_torch()
    target_device = _resolve_device(torch, device)
    edge_index = torch.as_tensor(inputs.edge_index, dtype=torch.long, device=target_device)
    text_features = torch.as_tensor(inputs.text_features, dtype=torch.float32, device=target_device)
    struct_features = torch.as_tensor(inputs.struct_features, dtype=torch.float32, device=target_device)
    scores: list[np.ndarray] = []
    for checkpoint_path in checkpoint_paths:
        model = _OfficialGNNCrossAttention(nn, gnn_type="sage").to(target_device)
        try:
            state = torch.load(checkpoint_path, map_location=target_device, weights_only=True)
        except TypeError:  # pragma: no cover - older torch compatibility
            state = torch.load(checkpoint_path, map_location=target_device)
        model.load_state_dict(state)
        model.eval()
        with torch.no_grad():
            probability = model(text_features, struct_features, edge_index).detach().cpu().numpy().reshape(-1)
        scores.append(probability.astype(np.float32))
    return scores


def _require_torch():
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Offline SocGFM China precompute requires torch") from exc
    try:
        import torch_geometric  # noqa: F401
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Offline SocGFM China precompute requires torch_geometric") from exc
    return torch, nn, functional


def _resolve_device(torch: Any, requested: str) -> str:
    value = str(requested or "auto").lower()
    if value == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if value.startswith("cuda") and not torch.cuda.is_available():
        return "cpu"
    return value


class _OfficialGNN:
    def __new__(cls, nn: Any, *, num_node_features: int, hidden_dim: int, num_classes: int, gnn_type: str):
        import torch
        from torch_geometric.nn import GATConv, GCNConv, SAGEConv

        class GNN(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                if gnn_type == "gcn":
                    block = GCNConv
                elif gnn_type == "gat":
                    block = GATConv
                elif gnn_type == "sage":
                    block = SAGEConv
                else:
                    raise ValueError(f"{gnn_type} is not supported")
                self.conv1 = block(num_node_features, hidden_dim)
                if num_classes > 2:
                    self.conv2 = block(hidden_dim, num_classes)
                    self.output_fn = torch.nn.LogSoftmax(dim=1)
                else:
                    self.conv2 = block(hidden_dim, 1)
                    self.output_fn = torch.nn.LogSigmoid()
                self.activation_fn = torch.nn.ReLU()
                self.dropout = torch.nn.Dropout(0.2)

            def forward(self, node_features, edge_index):
                node_features = self.conv1(node_features, edge_index)
                node_features = self.activation_fn(node_features)
                node_features = self.dropout(node_features)
                node_features = self.conv2(node_features, edge_index)
                return torch.exp(self.output_fn(node_features))

        return GNN()


class _OfficialGNNCrossAttention:
    def __new__(cls, nn: Any, *, gnn_type: str = "sage"):
        import torch

        class GNN_CrossAttention(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.gnn = _OfficialGNN(
                    nn,
                    num_node_features=SOCGFM_LATENT_DIM * 2,
                    hidden_dim=SOCGFM_LATENT_DIM * 2,
                    num_classes=2,
                    gnn_type=gnn_type,
                )
                self.cross_attention_to_text = torch.nn.Linear(SOCGFM_STRUCT_DIM, SOCGFM_LATENT_DIM)
                self.cross_attention_to_struct = torch.nn.Linear(SOCGFM_TEXT_DIM, SOCGFM_LATENT_DIM)
                self.struct_projector = torch.nn.Sequential(
                    torch.nn.Linear(SOCGFM_STRUCT_DIM, SOCGFM_LATENT_DIM),
                    torch.nn.Dropout(0.2),
                    torch.nn.ReLU(),
                )
                self.text_projector = torch.nn.Sequential(
                    torch.nn.Linear(SOCGFM_TEXT_DIM, SOCGFM_LATENT_DIM),
                    torch.nn.Dropout(0.2),
                    torch.nn.ReLU(),
                )
                self.joint_projector = torch.nn.Sequential(
                    torch.nn.Linear(SOCGFM_LATENT_DIM * 2, SOCGFM_LATENT_DIM * 2),
                    torch.nn.Dropout(0.2),
                    torch.nn.ReLU(),
                )

            def forward(self, text_node_features, struct_node_features, edge_index):
                struct_projection = self.struct_projector(struct_node_features) * self.cross_attention_to_struct(
                    text_node_features
                )
                text_projection = self.text_projector(text_node_features) * self.cross_attention_to_text(
                    struct_node_features
                )
                multimodal_node_features = self.joint_projector(
                    torch.concat([struct_projection, text_projection], dim=-1)
                )
                return self.gnn(multimodal_node_features, edge_index)

        return GNN_CrossAttention()


def _load_sbert_text_encoder() -> TextEncoder:
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("SBERT is required for SocGFM local precompute; TF-IDF fallback is forbidden") from exc
    model = SentenceTransformer(SOCGFM_TEXT_MODEL)

    def encode(texts: list[str]) -> np.ndarray:
        return np.asarray(
            model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True),
            dtype=np.float32,
        )

    return encode


def _prediction_rows(prepared: SocGFMLocalGraphInputs, scores: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, account_key in enumerate(prepared.account_keys):
        score = float(scores[index])
        label = prepared.label_by_account_key.get(account_key)
        rows.append(
            {
                "platform": prepared.platforms[index],
                "account_id": prepared.account_ids[index],
                "account_key": account_key,
                "node_id": index,
                "node_score": round(score, 12),
                "predicted_label": int(score >= 0.5),
                "label": "" if label is None else int(label),
                "evaluation_split": "inference",
            }
        )
    rows.sort(key=lambda row: (-float(row["node_score"]), str(row["account_key"])))
    return rows


def _detection_summary(
    prepared: SocGFMLocalGraphInputs,
    predictions: list[dict[str, Any]],
    manifest: Mapping[str, Any],
    feature_audit: Mapping[str, Any],
) -> dict[str, Any]:
    scores = np.asarray([float(row["node_score"]) for row in predictions], dtype=float)
    return {
        "setting": "coordination_detect",
        "task": "account_level_io_membership_to_cluster_proxy",
        "method": "socgfm_china_checkpoint_local_precompute",
        "detect_model": {
            "gnn_backend": "socgfm_cross_attention",
            "checkpoint_family": SOCGFM_CHECKPOINT_FAMILY,
            "model_role": SOCGFM_MODEL_ROLE,
            "model_version": SOCGFM_MODEL_VERSION,
            "inference_mode": SOCGFM_INFERENCE_MODE,
            "claim_scope": SOCGFM_CLAIM_SCOPE,
            "online_neural_forward": False,
            "neural_forward_executed_offline": True,
            "text_feature_source": feature_audit.get("text_feature_source"),
            "struct_feature_source": feature_audit.get("struct_feature_source"),
            "prediction_manifest": manifest.get("prediction_path"),
        },
        "metrics": {},
        "predictions": predictions,
        "node_scores": {row["account_id"]: row["node_score"] for row in predictions},
        "account_probabilities": {row["account_key"]: row["node_score"] for row in predictions},
        "unlabeled_inference_summary": {
            "score_mean": round(float(np.mean(scores)), 6) if scores.size else 0.0,
            "score_p90": round(float(np.quantile(scores, 0.9)), 6) if scores.size else 0.0,
            "score_max": round(float(np.max(scores)), 6) if scores.size else 0.0,
            "positive_at_0_5": int(np.sum(scores >= 0.5)),
            "node_count": int(scores.size),
            "member_probability_source": "china_checkpoint_offline_precompute",
            "claim_scope": SOCGFM_CLAIM_SCOPE,
            "online_neural_forward": False,
        },
        "feature_audit": dict(feature_audit),
        "prediction_manifest": dict(manifest),
        "node_mapping": prepared.node_mapping,
    }


def _write_predictions_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "platform",
        "account_id",
        "account_key",
        "node_id",
        "node_score",
        "predicted_label",
        "label",
        "evaluation_split",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_node_mapping_csv(path: Path, prepared: SocGFMLocalGraphInputs) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["node_id", "account_key", "platform", "account_id"])
        writer.writeheader()
        for account_key in prepared.account_keys:
            index = prepared.node_mapping[account_key]
            writer.writerow(
                {
                    "node_id": index,
                    "account_key": account_key,
                    "platform": prepared.platforms[index],
                    "account_id": prepared.account_ids[index],
                }
            )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _require_g_drive(path: Path) -> None:
    if path.drive.upper() != "G:":
        raise ValueError("SocGFM China local precompute outputs must be written under the G: drive")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _model_path_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"model(\d+)\.pth$", path.name)
    return (int(match.group(1)) if match else 9999, str(path))


def _first_text(record: Mapping[str, Any], *names: str, default: Any = "") -> str:
    for name in names:
        value = record.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return str(default)


def _normalize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if values.size == 0:
        return values
    min_value = float(np.min(values))
    max_value = float(np.max(values))
    if not math.isfinite(min_value) or not math.isfinite(max_value) or max_value <= min_value:
        return np.zeros_like(values, dtype=np.float32)
    return ((values - min_value) / (max_value - min_value)).astype(np.float32)


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    denominator = float(denominator)
    if denominator <= 0.0:
        return 0.0
    return round(float(numerator) / denominator, 12)


__all__ = [
    "SOCGFM_CHECKPOINT_FAMILY",
    "SOCGFM_CLAIM_SCOPE",
    "SOCGFM_DEFAULT_CHECKPOINT_ROOT",
    "SOCGFM_INFERENCE_MODE",
    "SOCGFM_MODEL_ROLE",
    "SOCGFM_MODEL_VERSION",
    "SOCGFM_PRECOMPUTE_SCHEMA_VERSION",
    "SocGFMLocalGraphInputs",
    "default_socgfm_local_precompute_output_dir",
    "discover_china_checkpoint_paths",
    "encode_account_text_features",
    "hash_checkpoint_files",
    "load_socgfm_local_events",
    "precompute_socgfm_china_local_detection",
    "prepare_socgfm_local_graph_inputs",
]
