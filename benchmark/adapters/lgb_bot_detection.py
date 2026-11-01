from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score


try:  # Torch is optional for docs-only environments, but required to train.
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception:  # pragma: no cover - exercised only when torch is absent.
    torch = None
    nn = None
    F = None


SCHEMA = "cogguard.kt2.lgb_bot_detection.v1"
DEFAULT_TEXT_DIM = 128
LGB_TABLE3_VARIANTS = [
    "full",
    "wo_lm_sft",
    "wo_gnn_finetuning",
    "wo_gnn_pretraining",
    "wo_concat",
    "average_fusion",
    "max_fusion",
    "lm_only",
]


@dataclass
class LGBDataset:
    node_ids: List[str]
    texts: List[str]
    labels: np.ndarray
    edges: List[Tuple[int, int]]
    train_idx: np.ndarray
    valid_idx: np.ndarray
    test_idx: np.ndarray
    labeled_idx: np.ndarray
    unlabeled_idx: np.ndarray


def build_unified_user_text(profile: Mapping, tweets: Optional[Sequence[str]] = None) -> str:
    """Build the LGB unified user textual sequence described in Fig. 5."""

    tweets = tweets or profile.get("tweets") or profile.get("tweet") or []
    if isinstance(tweets, str):
        tweets = [tweets]
    description = profile.get("description") or profile.get("desc") or ""
    fields = [
        ("Name", profile.get("name") or profile.get("screen_name") or profile.get("username") or ""),
        ("Created time", profile.get("created_at") or profile.get("created_time") or ""),
        ("Location", profile.get("location") or ""),
        ("protected", profile.get("protected") if "protected" in profile else ""),
        ("Fans count", profile.get("followers_count") or profile.get("followers") or profile.get("fans_count") or 0),
        ("Friend count", profile.get("friends_count") or profile.get("following_count") or profile.get("friend_count") or 0),
        ("Tweet count", profile.get("statuses_count") or profile.get("tweet_count") or len(tweets)),
        ("List count", profile.get("listed_count") or profile.get("list_count") or 0),
        ("verified", profile.get("verified") if "verified" in profile else ""),
    ]
    profile_text = " </s> ".join(f"{name}: {value}" for name, value in fields)
    tweet_text = " </s> ".join(_normalize_tweet(str(tweet)) for tweet in tweets[:20])
    return f"User profile: {profile_text} </s> Description: {_normalize_tweet(str(description))} </s> Tweet: {tweet_text}"


def load_lgb_dataset(path: str | Path, *, seed: int = 42, train_ratio: float = 0.7, valid_ratio: float = 0.2) -> LGBDataset:
    """Load a TwiBot-style or compact JSON/CSV bot-detection dataset.

    Supported compact fixtures:
    - ``nodes.jsonl`` rows with ``id``, ``label``, profile/text fields, and optional ``tweets``.
    - ``edges.csv`` with ``source,target`` or two-column rows.
    - optional ``split.csv`` with ``id,split`` where split is train/valid/test.

    This loader is intentionally conservative. Official TwiBot-22/20 adapters
    should convert raw files into this schema before claiming full reproduction.
    """

    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"LGB dataset path not found: {root}")
    nodes = _read_nodes(root)
    if not nodes:
        raise ValueError(f"No nodes found in {root}; expected nodes.jsonl, nodes.json, users.json, or node.json")
    id_to_idx = {str(row["id"]): idx for idx, row in enumerate(nodes)}
    node_ids = [str(row["id"]) for row in nodes]
    labels = np.asarray([_label_to_int_or_unlabeled(row.get("label", row.get("labels", row.get("bot")))) for row in nodes], dtype=np.int64)
    texts = [build_unified_user_text(row, row.get("tweets")) for row in nodes]
    edges = _read_edges(root, id_to_idx)
    split = _read_split(root, id_to_idx)
    labeled_idx = np.where(labels >= 0)[0].astype(np.int64)
    unlabeled_idx = np.where(labels < 0)[0].astype(np.int64)
    if split:
        train_idx = _filter_labeled_indices(split.get("train", []), labels)
        valid_idx = _filter_labeled_indices(split.get("valid", []), labels)
        test_idx = _filter_labeled_indices(split.get("test", []), labels)
    else:
        train_idx, valid_idx, test_idx = stratified_split(labels[labeled_idx], train_ratio=train_ratio, valid_ratio=valid_ratio, seed=seed)
        train_idx = labeled_idx[train_idx]
        valid_idx = labeled_idx[valid_idx]
        test_idx = labeled_idx[test_idx]
    return LGBDataset(
        node_ids=node_ids,
        texts=texts,
        labels=labels,
        edges=edges,
        train_idx=train_idx,
        valid_idx=valid_idx,
        test_idx=test_idx,
        labeled_idx=labeled_idx,
        unlabeled_idx=unlabeled_idx,
    )


def convert_lgb_official_dataset(
    source_dir: str | Path,
    out_dir: str | Path,
    *,
    source_format: str = "auto",
    max_tweets_per_user: int = 20,
    include_unlabeled_context: bool = True,
) -> Dict:
    """Convert official TwiBot schemas into the compact LGB adapter schema.

    The current KT2 LGB runner consumes labeled nodes only. Unlabeled support
    users are therefore recorded in the conversion summary and left out of the
    compact supervised fixture; full paper-level reproduction should keep them
    for GCL pretraining in a RoBERTa/T5 + PyG implementation.
    """

    source = Path(source_dir)
    out = Path(out_dir)
    if not source.exists():
        raise FileNotFoundError(f"LGB official source path not found: {source}")
    fmt = _detect_lgb_source_format(source, source_format)
    if fmt == "twibot22":
        nodes, edge_pairs, split, summary = _convert_twibot22_records(
            source,
            max_tweets_per_user=max_tweets_per_user,
            include_unlabeled_context=include_unlabeled_context,
        )
    elif fmt == "twibot20":
        nodes, edge_pairs, split, summary = _convert_twibot20_records(
            source,
            max_tweets_per_user=max_tweets_per_user,
            include_unlabeled_context=include_unlabeled_context,
        )
    else:
        raise ValueError(f"Unsupported LGB source_format: {source_format!r}")

    out.mkdir(parents=True, exist_ok=True)
    node_ids = {str(row["id"]) for row in nodes}
    filtered_edges = sorted({(src, dst) for src, dst in edge_pairs if src in node_ids and dst in node_ids and src != dst})
    _write_compact_lgb_dataset(out, nodes, filtered_edges, split)
    summary.update(
        {
            "schema": "cogguard.kt2.lgb_conversion_summary.v1",
            "source_dir": str(source),
            "out_dir": str(out),
            "node_count": len(nodes),
            "edge_count": len(filtered_edges),
            "split_counts": {name: len(values) for name, values in split.items()},
            "include_unlabeled_context": bool(include_unlabeled_context),
            "labeled_nodes": int(sum(1 for row in nodes if _label_to_int_or_unlabeled(row.get("label")) >= 0)),
            "unlabeled_context_nodes": int(sum(1 for row in nodes if _label_to_int_or_unlabeled(row.get("label")) < 0)),
            "compact_files": ["nodes.jsonl", "edges.csv", "split.csv", "conversion_summary.json"],
            "strict_reproduction_note": (
                "This conversion enables KT2 local LGB adapter runs. Paper-level LGB reproduction still "
                "requires supervised RoBERTa/T5 features, GCL over official graph data, five seeds, and ablations."
            ),
        }
    )
    (out / "conversion_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def audit_lgb_reproduction_status(
    repo_root: str | Path,
    *,
    dataset_root: str | Path = r"G:\CISCN\dataset",
    output_dir: str | Path | None = None,
) -> Dict:
    """Audit whether local files are sufficient for strict LGB reproduction."""

    repo = Path(repo_root)
    data_root = Path(dataset_root)
    twibot22 = _find_twibot22_root(data_root)
    twibot20 = _find_twibot20_root(data_root)
    missing = []
    if twibot22 is None:
        missing.append("TwiBot-22")
    if twibot20 is None:
        missing.append("TwiBot-20")
    blockers = []
    if missing:
        blockers.append(f"Missing official dataset(s): {', '.join(missing)}")
    blockers.extend(
        [
            "Current local adapter uses HashingVectorizer; strict LGB requires supervised RoBERTa/T5 SFT features.",
            "No verified five-seed TwiBot-22/TwiBot-20 mean +/- std result table is recorded locally.",
            "No verified Table III ablation suite is recorded locally.",
        ]
    )
    audit = {
        "schema": "cogguard.kt2.lgb_reproduction_audit.v1",
        "paper": "LGB: Language Model and Graph Neural Network-Driven Social Bot Detection",
        "task": "bot_detection",
        "kt2_position": "auxiliary_participant_risk_module",
        "repo_root": str(repo),
        "dataset_root": str(data_root),
        "twibot22_path": str(twibot22) if twibot22 else None,
        "twibot20_path": str(twibot20) if twibot20 else None,
        "missing_required_datasets": missing,
        "strict_reproduction_ready": False,
        "official_data_readiness": inspect_lgb_official_data_readiness(data_root),
        "local_adapter_ready": (repo / "benchmark" / "adapters" / "lgb_bot_detection.py").is_file(),
        "official_converter_ready": True,
        "lm_sft_feature_exporter_ready": True,
        "external_lm_feature_input_ready": True,
        "table3_ablation_scheduler_ready": True,
        "strict_artifact_gate_ready": True,
        "strict_pipeline_ready": True,
        "data_request_package_ready": True,
        "data_request_package_command": (
            "python -m benchmark.adapters.lgb_bot_detection --write_data_request "
            f"--dataset_root {data_root} --out_dir {repo / 'benchmark'}"
        ),
        "strict_pipeline_command": (
            "python -m benchmark.adapters.lgb_bot_detection --strict_pipeline "
            f"--dataset_root {data_root} "
            f"--artifacts_root {repo / 'benchmark' / 'lgb_strict'} "
            "--device cuda --encoder_backend transformers_roberta_sft"
        ),
        "required_full_reproduction": {
            "datasets": ["TwiBot-22", "TwiBot-20"],
            "text_encoder": "supervised fine-tuned RoBERTa or T5",
            "graph_stage": "edge-dropout GCL with InfoNCE, tau=0.4",
            "fusion": "Concat(LM representation, GNN representation) + MLP",
            "runs": "5 random initializations, mean +/- std",
            "metrics": ["Accuracy", "F1-Score", "ROC-AUC"],
            "ablations": [
                "w/o LM SFT",
                "w/o GNN fine-tuning",
                "w/o GNN pretraining",
                "w/o concat",
                "average fusion",
                "max fusion",
                "SFT LM only",
            ],
        },
        "blockers": blockers,
        "note": "Do not mark LGB as strict reproduction complete until all blockers are cleared.",
    }
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "lgb_reproduction_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "lgb_reproduction_audit.md").write_text(_format_lgb_audit_markdown(audit), encoding="utf-8")
    return audit


def inspect_lgb_official_data_readiness(
    dataset_root: str | Path,
    *,
    required_datasets: Sequence[str] = ("TwiBot-22", "TwiBot-20"),
) -> Dict:
    """Inspect whether official TwiBot data is present for strict LGB reproduction."""

    root = Path(dataset_root)
    datasets = []
    open_items: List[str] = []
    for dataset in required_datasets:
        candidate = _find_lgb_official_dataset_root(root, dataset, allow_sample=False)
        if _lgb_source_format_for_dataset(dataset) == "twibot22":
            row = _inspect_twibot22_readiness(root, dataset, candidate)
        elif _lgb_source_format_for_dataset(dataset) == "twibot20":
            row = _inspect_twibot20_readiness(root, dataset, candidate)
        else:
            row = {
                "dataset": dataset,
                "source_format": "unknown",
                "path": str(candidate) if candidate else None,
                "strict_ready": False,
                "open_items": [f"{dataset}: unsupported dataset for LGB strict reproduction"],
            }
        datasets.append(row)
        open_items.extend(row.get("open_items", []))
    strict_ready = all(bool(row.get("strict_ready")) for row in datasets)
    return {
        "schema": "cogguard.kt2.lgb_official_data_readiness.v1",
        "paper": "LGB: Language Model and Graph Neural Network-Driven Social Bot Detection",
        "dataset_root": str(root),
        "required_datasets": list(required_datasets),
        "strict_data_ready": bool(strict_ready),
        "datasets": datasets,
        "open_items": open_items,
        "download_sources": {
            "TwiBot-22": "https://github.com/LuoUndergradXJTU/TwiBot-22",
            "TwiBot-20": "https://github.com/BunsenFeng/TwiBot-20",
        },
        "note": "TwiBot-20_sample.json is accepted only for converter smoke tests, not for strict LGB reproduction.",
    }


def generate_lgb_data_request_package(
    *,
    dataset_root: str | Path = r"G:\CISCN\dataset",
    output_dir: str | Path = "benchmark",
    repo_root: str | Path = ".",
) -> Dict:
    """Write an auditable data-request package for authorized LGB reproduction data."""

    data_root = Path(dataset_root)
    out = Path(output_dir)
    repo = Path(repo_root)
    artifacts_root = repo / "benchmark" / "lgb_strict"
    package = {
        "schema": "cogguard.kt2.lgb_data_request_package.v1",
        "paper": "LGB: Language Model and Graph Neural Network-Driven Social Bot Detection",
        "task": "bot_detection",
        "kt2_position": "auxiliary_participant_risk_module",
        "status": "pending_authorized_data",
        "strict_reproduction_unblocked": False,
        "dataset_root": str(data_root),
        "artifacts_root": str(artifacts_root),
        "datasets": [
            {
                "dataset": "TwiBot-22",
                "official_repository": "https://github.com/LuoUndergradXJTU/TwiBot-22",
                "access_note": "Official repository states the full dataset is available through a Google Drive request with authorized/institutional contact.",
                "target_directory": str(data_root / "TwiBot-22"),
                "required_files": [
                    "label.csv",
                    "split.csv",
                    "edge.csv",
                    "user.json or user.jsonl or node.json or node.jsonl",
                    "tweet_*.json or tweet_*.jsonl",
                ],
                "strict_preflight": "Must pass --inspect_data before running --strict_pipeline.",
            },
            {
                "dataset": "TwiBot-20",
                "official_repository": "https://github.com/BunsenFeng/TwiBot-20",
                "access_note": "Official repository does not treat the sample file as the full strict-reproduction dataset; request/use authorized full train/dev/test files.",
                "target_directory": str(data_root / "TwiBot-20"),
                "required_files": [
                    "train.json or train.jsonl",
                    "dev.json/dev.jsonl or valid.json/valid.jsonl",
                    "test.json or test.jsonl",
                ],
                "strict_preflight": "TwiBot-20_sample.json is insufficient for strict reproduction.",
            },
        ],
        "sample_data_policy": "TwiBot-20_sample.json may be used for converter smoke tests only; it must not pass strict LGB reproduction or be reported as paper-level evidence.",
        "commands": {
            "preflight": (
                "python -m benchmark.adapters.lgb_bot_detection "
                f"--inspect_data --dataset_root {data_root}"
            ),
            "strict_pipeline": (
                "python -m benchmark.adapters.lgb_bot_detection "
                f"--strict_pipeline --dataset_root {data_root} --artifacts_root {artifacts_root} "
                "--device cuda --encoder_backend transformers_roberta_sft --model_name roberta-base --seeds 42,43,44,45,46"
            ),
            "strict_gate": (
                "python -m benchmark.adapters.lgb_bot_detection "
                f"--strict_gate --artifacts_root {artifacts_root} "
                f"--write_report_md {repo / 'benchmark' / 'lgb_strict_gate.md'}"
            ),
        },
        "completion_rule": "Strict reproduction can be claimed only after official data passes preflight and strict gate reports strict_reproduction_complete=true.",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "lgb_data_request_package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "lgb_data_request_package.md").write_text(_format_lgb_data_request_markdown(package), encoding="utf-8")
    return package


def export_lgb_lm_sft_features(
    data_dir: str | Path,
    out_dir: str | Path,
    *,
    encoder_backend: str = "lightweight_hashing_sft",
    model_name: str = "roberta-base",
    feature_dim: int = DEFAULT_TEXT_DIM,
    epochs: int = 3,
    seed: int = 42,
    device: str = "cpu",
    batch_size: int = 8,
    max_length: int = 256,
) -> Dict:
    """Export node-aligned LM features for LGB.

    ``lightweight_hashing_sft`` is a deterministic local smoke backend. Strict
    paper reproduction must use ``transformers_roberta_sft`` or
    ``transformers_t5_sft`` with a supervised fine-tuned model.
    """

    dataset = load_lgb_dataset(data_dir, seed=seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    backend = encoder_backend.strip().lower()
    strict_backend = backend in {"transformers_roberta_sft", "transformers_t5_sft"}
    if backend == "lightweight_hashing_sft":
        features = encode_text_hashing(dataset.texts, text_dim=feature_dim)
        training_status = "local_proxy_no_transformer_sft"
    elif strict_backend:
        features, training_status = _export_transformer_sft_features(
            dataset,
            model_name=model_name,
            backend=backend,
            epochs=epochs,
            seed=seed,
            device=device,
            batch_size=batch_size,
            max_length=max_length,
        )
        feature_dim = int(features.shape[1])
    else:
        raise ValueError(f"Unsupported LGB LM SFT encoder_backend: {encoder_backend!r}")

    feature_file = out / "lm_features.jsonl"
    rows = [
        json.dumps({"id": node_id, "embedding": [float(value) for value in features[idx].tolist()]}, ensure_ascii=False)
        for idx, node_id in enumerate(dataset.node_ids)
    ]
    feature_file.write_text("\n".join(rows), encoding="utf-8")
    report = {
        "schema": "cogguard.kt2.lgb_lm_sft_features.v1",
        "paper": "LGB: Language Model and Graph Neural Network-Driven Social Bot Detection",
        "task": "bot_detection",
        "status": "ok",
        "data_dir": str(data_dir),
        "out_dir": str(out),
        "feature_file": str(feature_file),
        "encoder_backend": backend,
        "model_name": model_name,
        "feature_dim": int(features.shape[1]),
        "node_count": len(dataset.node_ids),
        "train_count": int(len(dataset.train_idx)),
        "valid_count": int(len(dataset.valid_idx)),
        "test_count": int(len(dataset.test_idx)),
        "epochs": int(epochs),
        "seed": int(seed),
        "device": str(device),
        "batch_size": int(batch_size),
        "max_length": int(max_length),
        "training_status": training_status,
        "strict_lgb_text_encoder": bool(strict_backend),
        "strict_reproduction_note": (
            "Strict LGB reproduction requires supervised RoBERTa/T5 fine-tuning on official TwiBot labels. "
            "The lightweight backend is only a local smoke/proxy feature exporter."
        ),
    }
    (out / "lm_sft_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_lgb_reproduction(data_dir: str | Path, **kwargs) -> Dict:
    """Train a local LGB-style model and return benchmark-compatible metrics.

    The implementation follows the paper's strict stages at small-run scale:
    supervised semantic encoder alignment, graph contrastive pretraining, and
    GNN fine-tuning with concat fusion. The default text encoder is a frozen
    hashing vectorizer so CI can run without downloading RoBERTa; full
    reproduction must replace it with supervised RoBERTa/T5 features.
    """

    if torch is None:
        return {
            "schema": SCHEMA,
            "model": "LGB",
            "dataset": Path(data_dir).name,
            "task": "bot_detection",
            "status": "failed",
            "reproduction_level": "not_run",
            "note": "PyTorch is required to run LGB reproduction.",
        }
    seed = int(kwargs.get("seed", 42))
    _seed_everything(seed)
    dataset = load_lgb_dataset(data_dir, seed=seed)
    text_dim = int(kwargs.get("text_dim", DEFAULT_TEXT_DIM))
    hidden_dim = int(kwargs.get("hidden_dim", 32))
    epochs_lm = int(kwargs.get("epochs_lm", 3))
    epochs_gcl = int(kwargs.get("epochs_gcl", 3))
    epochs_finetune = int(kwargs.get("epochs_finetune", 5))
    dataset_name = str(kwargs.get("dataset", Path(data_dir).name))
    gcl_defaults = _paper_lgb_gcl_config(dataset_name)
    edge_drop_1 = _kw_float(kwargs, "edge_drop_1", gcl_defaults["edge_drop_1"])
    edge_drop_2 = _kw_float(kwargs, "edge_drop_2", gcl_defaults["edge_drop_2"])
    gcl_temperature = _kw_float(kwargs, "gcl_temperature", gcl_defaults["temperature"])
    lr = float(kwargs.get("lr", 1e-3))
    weight_decay = float(kwargs.get("weight_decay", 1e-5))
    ablation_variant = _normalize_lgb_ablation_variant(str(kwargs.get("ablation_variant", "full")))
    fusion_mode = _fusion_mode_for_variant(ablation_variant, str(kwargs.get("fusion_mode", "concat")))
    device = torch.device(str(kwargs.get("device", "cpu")))
    if device.type == "cuda" and not torch.cuda.is_available():
        device = torch.device("cpu")

    text_features_path = kwargs.get("text_features_path")
    text_encoder = str(kwargs.get("text_encoder", "") or "")
    if text_features_path:
        features_np = load_lgb_text_features(text_features_path, dataset.node_ids)
        text_dim = int(features_np.shape[1])
        text_encoder = text_encoder or "external_lm_features"
    else:
        features_np = encode_text_hashing(dataset.texts, text_dim=text_dim)
        text_encoder = text_encoder or "HashingVectorizer local proxy; strict full reproduction must use supervised RoBERTa/T5 features"
    x = torch.tensor(features_np, dtype=torch.float32, device=device)
    y = torch.tensor(dataset.labels, dtype=torch.long, device=device)
    train_idx = torch.tensor(dataset.train_idx, dtype=torch.long, device=device)
    valid_idx = torch.tensor(dataset.valid_idx, dtype=torch.long, device=device)
    test_idx = torch.tensor(dataset.test_idx, dtype=torch.long, device=device)
    edge_index = torch.tensor(dataset.edges, dtype=torch.long, device=device).t().contiguous() if dataset.edges else torch.empty((2, 0), dtype=torch.long, device=device)

    gnn_variant = str(kwargs.get("gnn_variant", "GCN")).upper()
    model = LGBModel(
        text_dim,
        hidden_dim,
        fusion_mode=fusion_mode,
        lm_only=(ablation_variant == "lm_only"),
        gnn_variant=gnn_variant,
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    if ablation_variant != "wo_lm_sft":
        best_valid = -1.0
        best_state = None
        for _ in range(max(1, epochs_lm)):
            model.train()
            logits = model.semantic_logits(x)
            loss = F.cross_entropy(logits[train_idx], y[train_idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            valid_acc = _accuracy_from_logits(logits[valid_idx].detach(), y[valid_idx])
            if valid_acc >= best_valid:
                best_valid = valid_acc
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if best_state:
            model.load_state_dict(best_state)

    if ablation_variant != "wo_gnn_pretraining" and ablation_variant != "lm_only":
        for _ in range(max(0, epochs_gcl)):
            model.train()
            h1 = model.graph_encode(model.semantic_repr(x).detach(), _drop_edges(edge_index, edge_drop_1))
            h2 = model.graph_encode(model.semantic_repr(x).detach(), _drop_edges(edge_index, edge_drop_2))
            loss = info_nce_loss(h1, h2, temperature=gcl_temperature)
            opt.zero_grad()
            loss.backward()
            opt.step()

    finetune_epochs = 0 if ablation_variant == "wo_gnn_finetuning" else max(1, epochs_finetune)
    best_valid = -1.0
    best_state = None
    for _ in range(finetune_epochs):
        model.train()
        logits = model(x, edge_index)
        loss = F.cross_entropy(logits[train_idx], y[train_idx])
        opt.zero_grad()
        loss.backward()
        opt.step()
        valid_acc = _accuracy_from_logits(logits[valid_idx].detach(), y[valid_idx])
        if valid_acc >= best_valid:
            best_valid = valid_acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state:
        model.load_state_dict(best_state)

    metrics = evaluate_lgb_model(model, x, edge_index, y, test_idx)
    sparse_stats = neighbor_bucket_metrics(model, x, edge_index, y, test_idx, len(dataset.node_ids))
    return {
        "schema": SCHEMA,
        "model": "LGB",
        "dataset": dataset_name,
        "task": "bot_detection",
        "status": "ok",
        "reproduction_level": str(kwargs.get("reproduction_level", "public_code_adapter")),
        "ablation_variant": ablation_variant,
        "fusion_mode": fusion_mode,
        "gnn_variant": gnn_variant,
        "seed": seed,
        "node_count": len(dataset.node_ids),
        "labeled_count": int(len(dataset.labeled_idx)),
        "unlabeled_context_count": int(len(dataset.unlabeled_idx)),
        "edge_count": len(dataset.edges),
        "text_feature_dim": int(text_dim),
        "train_count": int(len(dataset.train_idx)),
        "valid_count": int(len(dataset.valid_idx)),
        "test_count": int(len(dataset.test_idx)),
        "accuracy": metrics["accuracy"],
        "f1": metrics["f1"],
        "roc_auc": metrics["roc_auc"],
        "sparse_bucket_metrics": sparse_stats,
        "training_protocol": {
            "paper": "LGB: Language Model and Graph Neural Network-Driven Social Bot Detection",
            "stages": ["LM supervised fine-tuning", "GNN graph contrastive pre-training", "GNN fine-tuning with concat fusion"],
            "text_sequence": "User profile + Description + Tweet with </s> delimiters",
            "text_encoder": text_encoder,
            "text_features_source": str(text_features_path) if text_features_path else None,
            "gnn": f"LGB({gnn_variant})",
            "gnn_operator": model.gnn_operator_description,
            "edge_dropout_views": [edge_drop_1, edge_drop_2],
            "gcl_temperature": gcl_temperature,
            "ablation_variant": ablation_variant,
            "fusion_mode": fusion_mode,
            "unlabeled_context_usage": "GCL graph context only; excluded from supervised LM/GNN losses and metrics",
            "metrics": ["accuracy", "f1", "roc_auc"],
            "full_reproduction_required_datasets": ["TwiBot-22", "TwiBot-20"],
        },
        "methodology": "LGB-style multimodal bot detection: supervised semantic representation, graph contrastive pretraining, concat-fusion GNN classification.",
        "note": "This runner is a local reproducible LGB adapter. Do not claim paper-level strict reproduction until official TwiBot-22/20 full-run with RoBERTa/T5 features and five random seeds is complete.",
    }


def run_lgb_multiseed(data_dir: str | Path, *, seeds: Sequence[int], **kwargs) -> Dict:
    output_path = kwargs.pop("output_path", None)
    dataset_name = str(kwargs.get("dataset", Path(data_dir).name))
    gnn_variant = str(kwargs.get("gnn_variant", "GCN")).upper()
    paper_model = f"LGB({gnn_variant})"
    rows = []
    for seed in seeds:
        run_kwargs = dict(kwargs)
        run_kwargs["seed"] = int(seed)
        rows.append(run_lgb_reproduction(data_dir, **run_kwargs))
    metrics = {}
    for metric in ("accuracy", "f1", "roc_auc"):
        values = [
            float(row[metric])
            for row in rows
            if row.get("status") == "ok" and isinstance(row.get(metric), (int, float)) and math.isfinite(float(row[metric]))
        ]
        if values:
            metrics[metric] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            }
        else:
            metrics[metric] = {"mean": None, "std": None}
    summary = {
        "schema": "cogguard.kt2.lgb_multiseed_summary.v1",
        "model": "LGB",
        "dataset": dataset_name,
        "task": "bot_detection",
        "status": "ok" if all(row.get("status") == "ok" for row in rows) else "failed",
        "reproduction_level": str(kwargs.get("reproduction_level", "public_code_adapter")),
        "gnn_variant": gnn_variant,
        "paper_target": _lgb_paper_target_payload(dataset_name, paper_model),
        "num_runs": len(rows),
        "seeds": [int(seed) for seed in seeds],
        "required_paper_runs": 5,
        "meets_paper_seed_count": len(rows) >= 5,
        "metrics_mean_std": metrics,
        "runs": rows,
        "run_metadata": _lgb_run_metadata(
            "lgb_multiseed_summary",
            data_dir,
            dataset_name,
            seeds=seeds,
            kwargs=kwargs,
        ),
        "note": "Multi-seed summary for LGB adapter. Paper-level reproduction still requires official TwiBot-22/20 data, RoBERTa/T5 SFT features, and ablations.",
    }
    if output_path:
        _write_json_artifact(output_path, summary)
    return summary


def run_lgb_ablation_suite(
    data_dir: str | Path,
    *,
    seeds: Sequence[int],
    variants: Optional[Sequence[str]] = None,
    **kwargs,
) -> Dict:
    output_path = kwargs.pop("output_path", None)
    dataset_name = str(kwargs.get("dataset", Path(data_dir).name))
    gnn_variant = str(kwargs.get("gnn_variant", "GCN")).upper()
    requested = [_normalize_lgb_ablation_variant(variant) for variant in (variants or LGB_TABLE3_VARIANTS)]
    out = []
    for variant in requested:
        run_kwargs = dict(kwargs)
        run_kwargs["ablation_variant"] = variant
        summary = run_lgb_multiseed(data_dir, seeds=seeds, **run_kwargs)
        out.append({"variant": variant, "summary": summary})
    completed = [row["variant"] for row in out if row["summary"].get("status") == "ok"]
    summary = {
        "schema": "cogguard.kt2.lgb_ablation_suite.v1",
        "model": "LGB",
        "dataset": dataset_name,
        "task": "bot_detection",
        "status": "ok" if len(completed) == len(requested) else "failed",
        "reproduction_level": str(kwargs.get("reproduction_level", "public_code_adapter")),
        "gnn_variant": gnn_variant,
        "seeds": [int(seed) for seed in seeds],
        "required_table3_variants": list(LGB_TABLE3_VARIANTS),
        "completed_variants": completed,
        "missing_table3_variants": [variant for variant in LGB_TABLE3_VARIANTS if variant not in completed],
        "table3_complete": set(LGB_TABLE3_VARIANTS).issubset(set(completed)) and len(seeds) >= 5,
        "variants": out,
        "run_metadata": _lgb_run_metadata(
            "lgb_ablation_suite",
            data_dir,
            dataset_name,
            seeds=seeds,
            variants=requested,
            kwargs=kwargs,
        ),
        "note": "Ablation scheduler for LGB Table III-style variants. Strict completion also requires official TwiBot data, RoBERTa/T5 SFT, and five seeds.",
    }
    if output_path:
        _write_json_artifact(output_path, summary)
    return summary


def run_lgb_strict_reproduction_pipeline(
    *,
    dataset_root: str | Path,
    artifacts_root: str | Path,
    required_datasets: Sequence[str] = ("TwiBot-22", "TwiBot-20"),
    seeds: Sequence[int] = (42, 43, 44, 45, 46),
    encoder_backend: str = "transformers_roberta_sft",
    model_name: str = "roberta-base",
    device: str = "cpu",
    hidden_dim: int = 512,
    text_dim: int = DEFAULT_TEXT_DIM,
    epochs_lm: int = 3,
    epochs_gcl: int = 3,
    epochs_finetune: int = 5,
    batch_size: int = 8,
    max_length: int = 256,
    gnn_variant: str = "GCN",
    reproduction_level: str = "strict_lgb_reproduction_full_run",
) -> Dict:
    """Run the strict LGB reproduction artifact pipeline when official data exists.

    This orchestrator does not weaken the strict gate. It only creates the
    artifacts that the gate already requires: official conversion, strict LM SFT
    features, five-seed main result, and Table III ablations for each official
    TwiBot dataset.
    """

    dataset_root = Path(dataset_root)
    artifacts_root = Path(artifacts_root)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    seed_list = [int(seed) for seed in seeds]
    data_readiness = inspect_lgb_official_data_readiness(dataset_root, required_datasets=required_datasets)
    readiness_by_dataset = {
        row.get("dataset"): row for row in data_readiness.get("datasets", []) if isinstance(row, Mapping)
    }
    datasets = []
    open_items: List[str] = []
    for dataset in required_datasets:
        dataset_artifact_dir = artifacts_root / dataset
        readiness = readiness_by_dataset.get(dataset, {})
        source_dir = Path(readiness["path"]) if readiness.get("strict_ready") and readiness.get("path") else None
        record = {
            "dataset": dataset,
            "source_dir": str(source_dir) if source_dir else None,
            "artifact_dir": str(dataset_artifact_dir),
            "data_readiness": readiness,
            "status": "pending",
            "stages": [],
        }
        if source_dir is None:
            record["status"] = "missing_official_dataset"
            open_items.extend(readiness.get("open_items", []) or [f"{dataset}: missing official dataset under {dataset_root}"])
            datasets.append(record)
            continue
        try:
            dataset_artifact_dir.mkdir(parents=True, exist_ok=True)
            source_format = _lgb_source_format_for_dataset(dataset)
            conversion = convert_lgb_official_dataset(
                source_dir,
                dataset_artifact_dir,
                source_format=source_format,
            )
            record["stages"].append({"stage": "official_conversion", "status": "ok", "summary": conversion})
            lm_report = export_lgb_lm_sft_features(
                dataset_artifact_dir,
                dataset_artifact_dir,
                encoder_backend=encoder_backend,
                model_name=model_name,
                feature_dim=text_dim,
                epochs=epochs_lm,
                seed=seed_list[0] if seed_list else 42,
                device=device,
                batch_size=batch_size,
                max_length=max_length,
            )
            record["stages"].append({"stage": "lm_sft_feature_export", "status": "ok", "summary": lm_report})
            text_features_path = str(lm_report.get("feature_file") or dataset_artifact_dir / "lm_features.jsonl")
            run_kwargs = {
                "dataset": dataset,
                "device": device,
                "hidden_dim": hidden_dim,
                "epochs_lm": epochs_lm,
                "epochs_gcl": epochs_gcl,
                "epochs_finetune": epochs_finetune,
                "text_features_path": text_features_path,
                "text_encoder": _lgb_text_encoder_name(encoder_backend),
                "gnn_variant": gnn_variant,
                "reproduction_level": reproduction_level,
            }
            multiseed = run_lgb_multiseed(
                dataset_artifact_dir,
                seeds=seed_list,
                output_path=dataset_artifact_dir / "lgb_multiseed_summary.json",
                **run_kwargs,
            )
            record["stages"].append({"stage": "five_seed_main_result", "status": multiseed.get("status"), "summary": multiseed})
            ablation = run_lgb_ablation_suite(
                dataset_artifact_dir,
                seeds=seed_list,
                variants=LGB_TABLE3_VARIANTS,
                output_path=dataset_artifact_dir / "lgb_ablation_suite.json",
                **run_kwargs,
            )
            record["stages"].append({"stage": "table3_ablation_suite", "status": ablation.get("status"), "summary": ablation})
            record["status"] = "artifacts_generated"
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = f"{type(exc).__name__}: {exc}"
            open_items.append(f"{dataset}: strict pipeline failed at {record['status']} - {record['error']}")
        datasets.append(record)

    gate = run_lgb_strict_reproduction_gate(artifacts_root, required_datasets=required_datasets)
    gate_sections = {section.get("dataset"): section for section in gate.get("dataset_sections", []) if isinstance(section, Mapping)}
    for record in datasets:
        section = gate_sections.get(record["dataset"])
        if record["status"] in {"missing_official_dataset", "failed"}:
            continue
        record["status"] = "passed" if section and section.get("status") == "passed" else "incomplete"
    combined_open_items = list(dict.fromkeys([*open_items, *gate.get("open_items", [])]))
    complete = gate.get("status") == "passed" and not combined_open_items
    return {
        "schema": "cogguard.kt2.lgb_strict_reproduction_pipeline.v1",
        "paper": "LGB: Language Model and Graph Neural Network-Driven Social Bot Detection",
        "task": "bot_detection",
        "kt2_position": "auxiliary_participant_risk_module",
        "status": "passed" if complete else "incomplete",
        "strict_reproduction_complete": bool(complete),
        "dataset_root": str(dataset_root),
        "artifacts_root": str(artifacts_root),
        "required_datasets": list(required_datasets),
        "seeds": seed_list,
        "encoder_backend": encoder_backend,
        "gnn_variant": str(gnn_variant).upper(),
        "data_readiness": data_readiness,
        "datasets": datasets,
        "gate": gate,
        "open_items": combined_open_items,
        "completion_rule": (
            "Strict LGB reproduction is complete only when official TwiBot-22 and TwiBot-20 artifacts "
            "pass the strict gate with transformer SFT features, five seeds, and complete Table III ablations."
        ),
    }


def run_lgb_strict_reproduction_gate(
    artifacts_root: str | Path,
    *,
    required_datasets: Sequence[str] = ("TwiBot-22", "TwiBot-20"),
) -> Dict:
    root = Path(artifacts_root)
    sections = []
    open_items: List[str] = []
    for dataset in required_datasets:
        dataset_dir = root / dataset
        section = _check_lgb_dataset_artifacts(dataset, dataset_dir)
        sections.append(section)
        open_items.extend(section["open_items"])
    complete = not open_items
    return {
        "schema": "cogguard.kt2.lgb_strict_reproduction_gate.v1",
        "paper": "LGB: Language Model and Graph Neural Network-Driven Social Bot Detection",
        "task": "bot_detection",
        "status": "passed" if complete else "incomplete",
        "strict_reproduction_complete": bool(complete),
        "artifacts_root": str(root),
        "datasets_checked": list(required_datasets),
        "dataset_sections": sections,
        "open_items": open_items,
        "completion_rule": (
            "Each dataset must provide conversion_summary.json, strict RoBERTa/T5 lm_sft_report.json, "
            "5-seed lgb_multiseed_summary.json with Accuracy/F1/ROC-AUC mean/std, and complete Table III ablation suite."
        ),
    }


def write_lgb_strict_gate_report(gate: Mapping, output_path: str | Path) -> str:
    """Write a human-readable strict reproduction gate report."""

    lines = [
        "# LGB Strict Reproduction Gate",
        "",
        f"- Paper: `{gate.get('paper', 'LGB')}`",
        f"- Task: `{gate.get('task', 'bot_detection')}`",
        f"- Status: `{gate.get('status')}`",
        f"- Strict reproduction complete: `{bool(gate.get('strict_reproduction_complete'))}`",
        f"- Artifacts root: `{gate.get('artifacts_root')}`",
        "",
        "## Dataset Checks",
        "",
    ]
    sections = gate.get("dataset_sections", [])
    if isinstance(sections, list) and sections:
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            lines.extend(
                [
                    f"### {section.get('dataset')}",
                    "",
                    f"- Directory: `{section.get('dataset_dir')}`",
                    f"- Status: `{section.get('status')}`",
                    "",
                    "| Check | Status |",
                    "|---|---|",
                ]
            )
            for check in section.get("checks", []) or []:
                if isinstance(check, Mapping):
                    lines.append(f"| `{check.get('id')}` | `{check.get('status')}` |")
            lines.append("")
    else:
        lines.append("_No dataset sections were recorded._")
        lines.append("")

    lines.extend(["## Open Items", ""])
    open_items = gate.get("open_items", [])
    if isinstance(open_items, list) and open_items:
        lines.extend(f"- {item}" for item in open_items)
    else:
        lines.append("- None")
    lines.extend(["", "## Completion Rule", "", str(gate.get("completion_rule", "")), ""])
    markdown = "\n".join(lines)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    return markdown


def encode_text_hashing(texts: Sequence[str], *, text_dim: int = DEFAULT_TEXT_DIM) -> np.ndarray:
    vectorizer = HashingVectorizer(n_features=text_dim, alternate_sign=False, norm="l2", lowercase=True)
    return vectorizer.transform(texts).astype(np.float32).toarray()


def load_lgb_text_features(path: str | Path, node_ids: Sequence[str]) -> np.ndarray:
    """Load supervised LM features aligned by node id for paper-level LGB runs."""

    feature_path = Path(path)
    if not feature_path.is_file():
        raise FileNotFoundError(f"LGB text feature file not found: {feature_path}")
    suffix = feature_path.suffix.lower()
    if suffix == ".jsonl":
        feature_map = _read_feature_jsonl(feature_path)
        return _align_feature_map(feature_map, node_ids, feature_path)
    if suffix == ".json":
        data = json.loads(feature_path.read_text(encoding="utf-8-sig"))
        if isinstance(data, Mapping):
            if "features" in data and isinstance(data["features"], list):
                feature_map = {_coerce_id(row.get("id")): row.get("embedding", row.get("features")) for row in data["features"]}
            else:
                feature_map = {_coerce_id(key): value for key, value in data.items()}
        elif isinstance(data, list):
            feature_map = {_coerce_id(row.get("id")): row.get("embedding", row.get("features")) for row in data if isinstance(row, Mapping)}
        else:
            raise ValueError(f"Unsupported JSON feature payload in {feature_path}")
        return _align_feature_map(feature_map, node_ids, feature_path)
    if suffix == ".csv":
        feature_map = _read_feature_csv(feature_path)
        return _align_feature_map(feature_map, node_ids, feature_path)
    if suffix == ".npy":
        arr = np.load(feature_path)
        return _validate_feature_array(arr, node_ids, feature_path)
    if suffix == ".npz":
        data = np.load(feature_path, allow_pickle=True)
        if "features" in data and "node_ids" in data:
            arr = np.asarray(data["features"], dtype=np.float32)
            ids = [_coerce_id(value) for value in data["node_ids"].tolist()]
            feature_map = {node_id: arr[idx].tolist() for idx, node_id in enumerate(ids)}
            return _align_feature_map(feature_map, node_ids, feature_path)
        if "arr_0" in data:
            return _validate_feature_array(data["arr_0"], node_ids, feature_path)
    raise ValueError(f"Unsupported LGB text feature format: {feature_path}")


class LGBModel(nn.Module):
    def __init__(
        self,
        text_dim: int,
        hidden_dim: int,
        *,
        fusion_mode: str = "concat",
        lm_only: bool = False,
        gnn_variant: str = "GCN",
    ):
        super().__init__()
        self.fusion_mode = fusion_mode
        self.lm_only = lm_only
        self.gnn_variant = str(gnn_variant).upper()
        if self.gnn_variant not in {"GCN", "GIN", "GAT"}:
            raise ValueError(f"Unsupported LGB GNN variant: {gnn_variant}")
        self.semantic = nn.Sequential(nn.Linear(text_dim, hidden_dim), nn.ReLU(), nn.Dropout(0.1))
        self.semantic_cls = nn.Linear(hidden_dim, 2)
        self.gnn1 = nn.Linear(hidden_dim, hidden_dim)
        self.gnn2 = nn.Linear(hidden_dim, hidden_dim)
        self.gin_eps1 = nn.Parameter(torch.zeros(1))
        self.gin_eps2 = nn.Parameter(torch.zeros(1))
        self.gat_attn1 = nn.Linear(hidden_dim * 2, 1)
        self.gat_attn2 = nn.Linear(hidden_dim * 2, 1)
        fusion_input_dim = hidden_dim * 2 if fusion_mode == "concat" else hidden_dim
        self.fusion = nn.Sequential(nn.Linear(fusion_input_dim, hidden_dim), nn.ReLU(), nn.Dropout(0.1), nn.Linear(hidden_dim, 2))
        self.gnn_operator_description = {
            "GCN": "mean aggregation + linear projection",
            "GIN": "sum aggregation with learnable epsilon + linear projection",
            "GAT": "single-head additive attention aggregation + linear projection",
        }[self.gnn_variant]

    def semantic_repr(self, x):
        return self.semantic(x)

    def semantic_logits(self, x):
        return self.semantic_cls(self.semantic_repr(x))

    def graph_encode(self, semantic_h, edge_index):
        if self.gnn_variant == "GIN":
            h = F.relu(self.gnn1(_gin_aggregate(semantic_h, edge_index, self.gin_eps1)))
            h = F.relu(self.gnn2(_gin_aggregate(h, edge_index, self.gin_eps2)))
        elif self.gnn_variant == "GAT":
            h = F.relu(self.gnn1(_gat_aggregate(semantic_h, edge_index, self.gat_attn1)))
            h = F.relu(self.gnn2(_gat_aggregate(h, edge_index, self.gat_attn2)))
        else:
            h = F.relu(self.gnn1(_mean_aggregate(semantic_h, edge_index)))
            h = F.relu(self.gnn2(_mean_aggregate(h, edge_index)))
        return h

    def forward(self, x, edge_index):
        semantic_h = self.semantic_repr(x)
        if self.lm_only:
            return self.semantic_cls(semantic_h)
        graph_h = self.graph_encode(semantic_h, edge_index)
        if self.fusion_mode == "average":
            fused = 0.5 * (semantic_h + graph_h)
        elif self.fusion_mode == "max":
            fused = torch.maximum(semantic_h, graph_h)
        elif self.fusion_mode == "graph_only":
            fused = graph_h
        else:
            fused = torch.cat([semantic_h, graph_h], dim=1)
        return self.fusion(fused)


def evaluate_lgb_model(model, x, edge_index, y, idx) -> Dict[str, float]:
    model.eval()
    with torch.no_grad():
        logits = model(x, edge_index)[idx]
        labels = y[idx]
        probs = torch.softmax(logits, dim=1)[:, 1].detach().cpu().numpy()
        pred = logits.argmax(dim=1).detach().cpu().numpy()
        true = labels.detach().cpu().numpy()
    return _classification_metrics(true, pred, probs)


def neighbor_bucket_metrics(model, x, edge_index, y, idx, node_count: int) -> Dict[str, Dict[str, float]]:
    degrees = np.zeros(node_count, dtype=int)
    if edge_index.numel() > 0:
        src = edge_index[0].detach().cpu().numpy()
        dst = edge_index[1].detach().cpu().numpy()
        for u, v in zip(src, dst):
            degrees[u] += 1
            degrees[v] += 1
    buckets = {"isolated": [], "sparse_1_2": [], "dense_gt2": []}
    for raw_idx in idx.detach().cpu().numpy().tolist():
        degree = degrees[int(raw_idx)]
        if degree == 0:
            buckets["isolated"].append(raw_idx)
        elif degree <= 2:
            buckets["sparse_1_2"].append(raw_idx)
        else:
            buckets["dense_gt2"].append(raw_idx)
    out = {}
    model.eval()
    with torch.no_grad():
        logits_all = model(x, edge_index)
        probs_all = torch.softmax(logits_all, dim=1)[:, 1].detach().cpu().numpy()
        pred_all = logits_all.argmax(dim=1).detach().cpu().numpy()
        true_all = y.detach().cpu().numpy()
    for name, members in buckets.items():
        if not members:
            out[name] = {"count": 0, "accuracy": None, "f1": None, "roc_auc": None}
            continue
        members_np = np.asarray(members, dtype=int)
        out[name] = {"count": int(len(members)), **_classification_metrics(true_all[members_np], pred_all[members_np], probs_all[members_np])}
    return out


def info_nce_loss(h1, h2, *, temperature: float = 0.4):
    h1 = F.normalize(h1, dim=1)
    h2 = F.normalize(h2, dim=1)
    logits = h1 @ h2.t() / max(temperature, 1e-6)
    labels = torch.arange(h1.size(0), device=h1.device)
    return 0.5 * (F.cross_entropy(logits, labels) + F.cross_entropy(logits.t(), labels))


def stratified_split(labels: np.ndarray, *, train_ratio: float, valid_ratio: float, seed: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train, valid, test = [], [], []
    for label in sorted(set(labels.tolist())):
        idx = np.where(labels == label)[0]
        rng.shuffle(idx)
        n_train = max(1, int(len(idx) * train_ratio))
        n_valid = max(1, int(len(idx) * valid_ratio))
        if len(idx) - n_train - n_valid <= 0 and len(idx) >= 3:
            n_train = max(1, len(idx) - 2)
            n_valid = 1
        train.extend(idx[:n_train].tolist())
        valid.extend(idx[n_train : n_train + n_valid].tolist())
        test.extend(idx[n_train + n_valid :].tolist())
    return np.asarray(train, dtype=np.int64), np.asarray(valid, dtype=np.int64), np.asarray(test, dtype=np.int64)


def _classification_metrics(true: np.ndarray, pred: np.ndarray, probs: np.ndarray) -> Dict[str, float]:
    metrics = {
        "accuracy": float(accuracy_score(true, pred)),
        "f1": float(f1_score(true, pred, zero_division=0)),
    }
    try:
        roc_auc = float(roc_auc_score(true, probs))
        metrics["roc_auc"] = roc_auc if math.isfinite(roc_auc) else None
    except ValueError:
        metrics["roc_auc"] = None
    return metrics


def _paper_lgb_gcl_config(dataset_name: str) -> Dict[str, float]:
    normalized = dataset_name.lower().replace("_", "-")
    if "twibot-20" in normalized or "twibot20" in normalized:
        return {"edge_drop_1": 0.4, "edge_drop_2": 0.6, "temperature": 0.4}
    return {"edge_drop_1": 0.2, "edge_drop_2": 0.4, "temperature": 0.4}


def _check_lgb_dataset_artifacts(dataset: str, dataset_dir: Path) -> Dict:
    checks = []
    open_items: List[str] = []
    if not dataset_dir.is_dir():
        return {
            "dataset": dataset,
            "dataset_dir": str(dataset_dir),
            "status": "missing",
            "checks": [],
            "open_items": [f"{dataset}: missing artifact directory {dataset_dir}"],
        }
    conversion = _load_json_if_exists(dataset_dir / "conversion_summary.json")
    checks.append(_lgb_check("conversion_summary", conversion is not None and conversion.get("schema") == "cogguard.kt2.lgb_conversion_summary.v1"))
    if checks[-1]["status"] != "passed":
        open_items.append(f"{dataset}: missing valid conversion_summary.json")
    official_conversion_ok = conversion is not None and _lgb_official_conversion_summary_complete(dataset, conversion)
    checks.append(_lgb_check("official_dataset_conversion_summary", official_conversion_ok))
    if not official_conversion_ok:
        open_items.append(f"{dataset}: missing official dataset scale/label/split evidence in conversion_summary.json")
    context_ok = (
        conversion is not None
        and conversion.get("include_unlabeled_context") is True
        and isinstance(conversion.get("unlabeled_context_nodes"), int)
    )
    checks.append(_lgb_check("unlabeled_graph_context_policy", context_ok))
    if not context_ok:
        open_items.append(f"{dataset}: missing explicit unlabeled context graph policy in conversion_summary.json")

    lm_report = _load_json_if_exists(dataset_dir / "lm_sft_report.json")
    lm_ok = (
        lm_report is not None
        and lm_report.get("schema") == "cogguard.kt2.lgb_lm_sft_features.v1"
        and lm_report.get("status") == "ok"
        and lm_report.get("strict_lgb_text_encoder") is True
        and str(lm_report.get("encoder_backend", "")).startswith("transformers_")
    )
    checks.append(_lgb_check("roberta_t5_sft_features", lm_ok))
    if not lm_ok:
        open_items.append(f"{dataset}: missing strict RoBERTa/T5 lm_sft_report.json")

    multiseed = _load_json_if_exists(dataset_dir / "lgb_multiseed_summary.json")
    multiseed_ok = (
        multiseed is not None
        and multiseed.get("schema") == "cogguard.kt2.lgb_multiseed_summary.v1"
        and multiseed.get("status") == "ok"
        and int(multiseed.get("num_runs", 0)) >= 5
        and multiseed.get("meets_paper_seed_count") is True
        and _lgb_metrics_complete(multiseed.get("metrics_mean_std", {}))
    )
    checks.append(_lgb_check("five_seed_main_metrics", multiseed_ok))
    if not multiseed_ok:
        open_items.append(f"{dataset}: missing 5-seed Accuracy/F1/ROC-AUC mean/std main result")
    main_gcl_ok = multiseed is not None and _lgb_gcl_protocol_complete(dataset, multiseed.get("runs", []))
    checks.append(_lgb_check("main_result_gcl_protocol", main_gcl_ok))
    if not main_gcl_ok:
        open_items.append(f"{dataset}: missing or incorrect LGB GCL edge-dropout/tau protocol in main result")
    multiseed_metadata_ok = multiseed is not None and _lgb_run_metadata_complete(
        multiseed.get("run_metadata"),
        "lgb_multiseed_summary",
        dataset,
    )
    checks.append(_lgb_check("main_result_run_metadata", multiseed_metadata_ok))
    if not multiseed_metadata_ok:
        open_items.append(f"{dataset}: missing run metadata in lgb_multiseed_summary.json")
    multiseed_level_ok = multiseed is not None and _lgb_strict_reproduction_level_complete(multiseed)
    checks.append(_lgb_check("main_result_reproduction_level", multiseed_level_ok))
    if not multiseed_level_ok:
        open_items.append(f"{dataset}: insufficient reproduction level in lgb_multiseed_summary.json")
    gnn_variant_ok = multiseed is not None and _lgb_gnn_variant_complete(multiseed)
    checks.append(_lgb_check("main_result_gnn_variant", gnn_variant_ok))
    if not gnn_variant_ok:
        open_items.append(f"{dataset}: missing GNN variant for LGB(GCN/GIN/GAT) main result")
    paper_target_ok = multiseed is not None and _lgb_paper_target_complete(multiseed.get("paper_target"), dataset)
    checks.append(_lgb_check("table2_paper_target_alignment", paper_target_ok))
    if not paper_target_ok:
        open_items.append(f"{dataset}: missing Table II paper target alignment in lgb_multiseed_summary.json")
    main_run_protocol_ok = multiseed is not None and _lgb_run_level_protocol_complete(
        multiseed.get("runs", []),
        str(multiseed.get("gnn_variant", "")),
    )
    checks.append(_lgb_check("main_result_run_level_protocol", main_run_protocol_ok))
    if not main_run_protocol_ok:
        open_items.append(f"{dataset}: missing strict run-level protocol in lgb_multiseed_summary.json")
    main_run_metrics_ok = multiseed is not None and _lgb_run_level_metrics_complete(multiseed.get("runs", []))
    checks.append(_lgb_check("main_result_run_level_metrics", main_run_metrics_ok))
    if not main_run_metrics_ok:
        open_items.append(f"{dataset}: missing strict run-level metrics in lgb_multiseed_summary.json")

    ablation = _load_json_if_exists(dataset_dir / "lgb_ablation_suite.json")
    completed_variants = set(ablation.get("completed_variants", []) if isinstance(ablation, Mapping) else [])
    ablation_ok = (
        ablation is not None
        and ablation.get("schema") == "cogguard.kt2.lgb_ablation_suite.v1"
        and ablation.get("status") == "ok"
        and ablation.get("table3_complete") is True
        and set(LGB_TABLE3_VARIANTS).issubset(completed_variants)
    )
    checks.append(_lgb_check("table3_ablation_suite", ablation_ok))
    if not ablation_ok:
        open_items.append(f"{dataset}: missing complete Table III ablation suite")
    ablation_gcl_ok = ablation is not None and _lgb_ablation_gcl_protocol_complete(dataset, ablation.get("variants", []))
    checks.append(_lgb_check("table3_ablation_gcl_protocol", ablation_gcl_ok))
    if not ablation_gcl_ok:
        open_items.append(f"{dataset}: missing or incorrect LGB GCL edge-dropout/tau protocol in Table III ablations")
    ablation_metadata_ok = ablation is not None and _lgb_run_metadata_complete(
        ablation.get("run_metadata"),
        "lgb_ablation_suite",
        dataset,
        require_variants=True,
    )
    checks.append(_lgb_check("table3_ablation_run_metadata", ablation_metadata_ok))
    if not ablation_metadata_ok:
        open_items.append(f"{dataset}: missing run metadata in lgb_ablation_suite.json")
    ablation_level_ok = ablation is not None and _lgb_strict_reproduction_level_complete(ablation)
    checks.append(_lgb_check("table3_ablation_reproduction_level", ablation_level_ok))
    if not ablation_level_ok:
        open_items.append(f"{dataset}: insufficient reproduction level in lgb_ablation_suite.json")
    ablation_run_protocol_ok = ablation is not None and _lgb_ablation_run_level_protocol_complete(
        ablation.get("variants", []),
        str(multiseed.get("gnn_variant", "")) if isinstance(multiseed, Mapping) else "",
    )
    checks.append(_lgb_check("table3_ablation_run_level_protocol", ablation_run_protocol_ok))
    if not ablation_run_protocol_ok:
        open_items.append(f"{dataset}: missing strict run-level protocol in lgb_ablation_suite.json")
    ablation_run_metrics_ok = ablation is not None and _lgb_ablation_run_metrics_complete(ablation.get("variants", []))
    checks.append(_lgb_check("table3_ablation_run_metrics", ablation_run_metrics_ok))
    if not ablation_run_metrics_ok:
        open_items.append(f"{dataset}: missing strict ablation run metrics in lgb_ablation_suite.json")
    cross_artifact_ok = _lgb_cross_artifact_consistency_complete(conversion, lm_report, multiseed, ablation)
    checks.append(_lgb_check("cross_artifact_feature_consistency", cross_artifact_ok))
    if not cross_artifact_ok:
        open_items.append(f"{dataset}: missing cross-artifact consistency between conversion, LM features, main result, and ablations")

    return {
        "dataset": dataset,
        "dataset_dir": str(dataset_dir),
        "status": "passed" if not open_items else "incomplete",
        "checks": checks,
        "open_items": open_items,
    }


def _load_json_if_exists(path: Path) -> Optional[Dict]:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else None


def _write_json_artifact(path: str | Path, payload: Mapping) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _lgb_run_metadata(
    artifact_type: str,
    data_dir: str | Path,
    dataset_name: str,
    *,
    seeds: Optional[Sequence[int]] = None,
    variants: Optional[Sequence[str]] = None,
    kwargs: Optional[Mapping] = None,
) -> Dict:
    kwargs = kwargs or {}
    return {
        "artifact_type": artifact_type,
        "dataset": dataset_name,
        "data_dir": str(data_dir),
        "command_or_entrypoint": "benchmark.adapters.lgb_bot_detection",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "torch_version": str(getattr(torch, "__version__", "unavailable")) if torch is not None else "unavailable",
        "device": str(kwargs.get("device", "cpu")),
        "seeds": [int(seed) for seed in seeds] if seeds is not None else [],
        "variants": list(variants or []),
        "text_features_path": str(kwargs.get("text_features_path")) if kwargs.get("text_features_path") else None,
        "text_encoder": str(kwargs.get("text_encoder", "")) if kwargs.get("text_encoder") else None,
        "reproduction_level": str(kwargs.get("reproduction_level", "public_code_adapter")),
    }


def _lgb_check(name: str, passed: bool) -> Dict:
    return {"id": name, "status": "passed" if passed else "missing"}


def _lgb_strict_reproduction_level_complete(artifact: Mapping) -> bool:
    allowed = {"strict_lgb_reproduction_full_run", "frontier_reproduction_full_run"}
    top_level = str(artifact.get("reproduction_level", ""))
    metadata = artifact.get("run_metadata", {})
    metadata_level = str(metadata.get("reproduction_level", "")) if isinstance(metadata, Mapping) else ""
    return top_level in allowed and metadata_level in allowed


def _lgb_metrics_complete(metrics: Mapping) -> bool:
    if not isinstance(metrics, Mapping):
        return False
    for metric in ("accuracy", "f1", "roc_auc"):
        row = metrics.get(metric)
        if not isinstance(row, Mapping):
            return False
        if not _is_finite_number(row.get("mean")) or not _is_finite_number(row.get("std")):
            return False
    return True


def _lgb_official_conversion_summary_complete(dataset: str, conversion: Mapping) -> bool:
    expected = _lgb_official_dataset_expectation(dataset)
    if not expected:
        return False
    if str(conversion.get("source_format", "")).lower() != expected["source_format"]:
        return False
    node_count = _safe_int(conversion.get("node_count"))
    labeled_nodes = _safe_int(conversion.get("labeled_nodes"))
    if node_count < expected["min_node_count"] or labeled_nodes < expected["min_labeled_nodes"]:
        return False
    label_counts = conversion.get("label_counts")
    if not isinstance(label_counts, Mapping):
        return False
    human_count = _safe_int(label_counts.get("human", label_counts.get("0")))
    bot_count = _safe_int(label_counts.get("bot", label_counts.get("1")))
    if human_count < expected["min_human"] or bot_count < expected["min_bot"]:
        return False
    split_counts = conversion.get("split_counts")
    if not isinstance(split_counts, Mapping):
        return False
    return all(_safe_int(split_counts.get(name)) > 0 for name in ("train", "valid", "test"))


def _lgb_official_dataset_expectation(dataset: str) -> Dict[str, int | str]:
    normalized = dataset.lower().replace("_", "-")
    if "twibot-22" in normalized or "twibot22" in normalized:
        return {
            "source_format": "twibot22",
            "min_node_count": 150000,
            "min_labeled_nodes": 150000,
            "min_human": 75000,
            "min_bot": 75000,
        }
    if "twibot-20" in normalized or "twibot20" in normalized:
        return {
            "source_format": "twibot20",
            "min_node_count": 10000,
            "min_labeled_nodes": 10000,
            "min_human": 4000,
            "min_bot": 4000,
        }
    return {}


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _lgb_gnn_variant_complete(summary: Mapping) -> bool:
    variant = str(summary.get("gnn_variant", "")).upper()
    return variant in {"GCN", "GIN", "GAT"}


def _lgb_paper_target_complete(target, dataset: str) -> bool:
    if not isinstance(target, Mapping):
        return False
    if str(target.get("table", "")).lower() != "table ii":
        return False
    model = str(target.get("model", ""))
    if model not in {"LGB(GCN)", "LGB(GIN)", "LGB(GAT)"}:
        return False
    expected = _lgb_table2_targets(dataset).get(model)
    if not expected:
        return False
    for metric in ("accuracy", "f1", "roc_auc"):
        if not _is_finite_number(target.get(metric)):
            return False
        # The gate checks the artifact records the correct paper target, not
        # that local reproduction matches it exactly.
        if abs(float(target[metric]) - expected[metric]) > 1e-4:
            return False
    return True


def _lgb_run_level_protocol_complete(runs, gnn_variant: str) -> bool:
    if not isinstance(runs, list) or not runs:
        return False
    expected_gnn = f"LGB({str(gnn_variant).upper()})"
    for row in runs:
        if not isinstance(row, Mapping):
            return False
        protocol = row.get("training_protocol")
        if not isinstance(protocol, Mapping):
            return False
        if protocol.get("gnn") != expected_gnn:
            return False
        text_encoder = str(protocol.get("text_encoder", ""))
        if not text_encoder or "hashing" in text_encoder.lower() or "proxy" in text_encoder.lower():
            return False
        if not protocol.get("text_features_source"):
            return False
    return True


def _lgb_run_level_metrics_complete(runs) -> bool:
    if not isinstance(runs, list) or len(runs) < 5:
        return False
    for row in runs:
        if not isinstance(row, Mapping):
            return False
        if row.get("status") != "ok":
            return False
        if not isinstance(row.get("seed"), int):
            return False
        for metric in ("accuracy", "f1", "roc_auc"):
            if not _is_finite_number(row.get(metric)):
                return False
    return True


def _lgb_ablation_run_metrics_complete(variants) -> bool:
    if not isinstance(variants, list) or not variants:
        return False
    for variant in variants:
        if not isinstance(variant, Mapping):
            return False
        summary = variant.get("summary")
        if not isinstance(summary, Mapping):
            return False
        if int(summary.get("num_runs", 0)) < 5:
            return False
        if summary.get("meets_paper_seed_count") is not True:
            return False
        if not _lgb_metrics_complete(summary.get("metrics_mean_std", {})):
            return False
        if not _lgb_run_level_metrics_complete(summary.get("runs", [])):
            return False
    return True


def _lgb_cross_artifact_consistency_complete(conversion, lm_report, multiseed, ablation) -> bool:
    if not all(isinstance(item, Mapping) for item in (conversion, lm_report, multiseed, ablation)):
        return False
    conversion_nodes = _safe_int(conversion.get("node_count"))
    lm_nodes = _safe_int(lm_report.get("node_count"))
    if conversion_nodes <= 0 or lm_nodes != conversion_nodes:
        return False
    feature_file = _normalize_artifact_path(lm_report.get("feature_file"))
    if not feature_file:
        return False
    for protocol in _iter_lgb_run_protocols(multiseed.get("runs", [])):
        if _normalize_artifact_path(protocol.get("text_features_source")) != feature_file:
            return False
    for variant in ablation.get("variants", []) if isinstance(ablation.get("variants"), list) else []:
        if not isinstance(variant, Mapping):
            return False
        summary = variant.get("summary")
        if not isinstance(summary, Mapping):
            return False
        for protocol in _iter_lgb_run_protocols(summary.get("runs", [])):
            if _normalize_artifact_path(protocol.get("text_features_source")) != feature_file:
                return False
    return True


def _iter_lgb_run_protocols(runs) -> Iterable[Mapping]:
    if not isinstance(runs, list):
        return
    for row in runs:
        if isinstance(row, Mapping) and isinstance(row.get("training_protocol"), Mapping):
            yield row["training_protocol"]


def _normalize_artifact_path(value) -> str:
    if not value:
        return ""
    return str(value).replace("\\", "/").rstrip("/")


def _lgb_ablation_run_level_protocol_complete(variants, gnn_variant: str) -> bool:
    if not isinstance(variants, list) or not variants:
        return False
    for variant in variants:
        if not isinstance(variant, Mapping):
            return False
        summary = variant.get("summary")
        if not isinstance(summary, Mapping):
            return False
        if not _lgb_run_level_protocol_complete(summary.get("runs", []), gnn_variant):
            return False
    return True


def _lgb_paper_target_payload(dataset: str, model: str) -> Dict:
    targets = _lgb_table2_targets(dataset)
    metrics = targets.get(model)
    if not metrics:
        return {
            "table": "Table II",
            "model": model,
            "status": "unknown_target",
            "comparison_note": "No Table II target is recorded for this model/dataset pair.",
        }
    return {
        "table": "Table II",
        "model": model,
        "accuracy": metrics["accuracy"],
        "f1": metrics["f1"],
        "roc_auc": metrics["roc_auc"],
        "comparison_note": "Paper target recorded for reproduction alignment; local metrics are reported separately as mean/std.",
    }


def _lgb_table2_targets(dataset: str) -> Dict[str, Dict[str, float]]:
    normalized = dataset.lower().replace("_", "-")
    if "twibot-20" in normalized or "twibot20" in normalized:
        return {
            "LGB(GAT)": {"accuracy": 0.8483, "f1": 0.8733, "roc_auc": 0.8379},
            "LGB(GIN)": {"accuracy": 0.8489, "f1": 0.8716, "roc_auc": 0.8417},
            "LGB(GCN)": {"accuracy": 0.8509, "f1": 0.8744, "roc_auc": 0.8423},
        }
    return {
        "LGB(GAT)": {"accuracy": 0.8030, "f1": 0.8106, "roc_auc": 0.8030},
        "LGB(GIN)": {"accuracy": 0.8033, "f1": 0.8093, "roc_auc": 0.8033},
        "LGB(GCN)": {"accuracy": 0.8042, "f1": 0.8131, "roc_auc": 0.8042},
    }


def _lgb_run_metadata_complete(metadata, artifact_type: str, dataset: str, *, require_variants: bool = False) -> bool:
    if not isinstance(metadata, Mapping):
        return False
    if metadata.get("artifact_type") != artifact_type:
        return False
    if str(metadata.get("dataset", "")) not in {dataset, dataset.replace("-", "")}:
        return False
    if not metadata.get("data_dir") or not metadata.get("command_or_entrypoint"):
        return False
    seeds = metadata.get("seeds")
    if not isinstance(seeds, list) or len(seeds) < 5:
        return False
    if require_variants:
        variants = metadata.get("variants")
        if not isinstance(variants, list) or not set(LGB_TABLE3_VARIANTS).issubset(set(variants)):
            return False
    return True


def _lgb_gcl_protocol_complete(dataset: str, runs) -> bool:
    if not isinstance(runs, list) or not runs:
        return False
    expected = _paper_lgb_gcl_config(dataset)
    expected_views = [expected["edge_drop_1"], expected["edge_drop_2"]]
    for row in runs:
        if not isinstance(row, Mapping):
            return False
        protocol = row.get("training_protocol", {})
        if not isinstance(protocol, Mapping):
            return False
        views = protocol.get("edge_dropout_views")
        tau = protocol.get("gcl_temperature")
        if not _float_list_close(views, expected_views):
            return False
        if not _float_close(tau, expected["temperature"]):
            return False
    return True


def _lgb_ablation_gcl_protocol_complete(dataset: str, variants) -> bool:
    if not isinstance(variants, list) or not variants:
        return False
    for variant in variants:
        if not isinstance(variant, Mapping):
            return False
        summary = variant.get("summary", {})
        if not isinstance(summary, Mapping):
            return False
        if not _lgb_gcl_protocol_complete(dataset, summary.get("runs", [])):
            return False
    return True


def _float_list_close(values, expected: Sequence[float], *, tol: float = 1e-8) -> bool:
    if not isinstance(values, list) or len(values) != len(expected):
        return False
    return all(_float_close(value, exp, tol=tol) for value, exp in zip(values, expected))


def _float_close(value, expected: float, *, tol: float = 1e-8) -> bool:
    return isinstance(value, (int, float)) and abs(float(value) - float(expected)) <= tol


def _is_finite_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _kw_float(kwargs: Mapping, key: str, default: float) -> float:
    value = kwargs.get(key)
    return float(default if value is None else value)


def _normalize_lgb_ablation_variant(variant: str) -> str:
    normalized = variant.strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
    aliases = {
        "lgb_gcn": "full",
        "full_model": "full",
        "without_lm_sft": "wo_lm_sft",
        "w_o_lm_supervised_fine_tuning": "wo_lm_sft",
        "without_gnn_finetuning": "wo_gnn_finetuning",
        "wo_gnn_fine_tuning": "wo_gnn_finetuning",
        "without_gnn_pretraining": "wo_gnn_pretraining",
        "wo_gnn_pre_training": "wo_gnn_pretraining",
        "without_concat": "wo_concat",
        "w_o_concat": "wo_concat",
        "average": "average_fusion",
        "avg_fusion": "average_fusion",
        "max": "max_fusion",
        "sft_lm_only": "lm_only",
        "supervised_fine_tuned_lm_only": "lm_only",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in LGB_TABLE3_VARIANTS:
        raise ValueError(f"Unsupported LGB ablation variant: {variant!r}")
    return normalized


def _fusion_mode_for_variant(variant: str, requested: str) -> str:
    if variant == "wo_concat":
        return "graph_only"
    if variant == "average_fusion":
        return "average"
    if variant == "max_fusion":
        return "max"
    requested = requested.strip().lower()
    if requested in {"concat", "average", "max", "graph_only"}:
        return requested
    raise ValueError(f"Unsupported LGB fusion mode: {requested!r}")


def _read_feature_jsonl(path: Path) -> Dict[str, Sequence[float]]:
    features = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        node_id = _coerce_id(row.get("id") or row.get("user_id") or row.get("node_id"))
        embedding = row.get("embedding", row.get("features"))
        if node_id:
            features[node_id] = embedding
    return features


def _export_transformer_sft_features(
    dataset: LGBDataset,
    *,
    model_name: str,
    backend: str,
    epochs: int,
    seed: int,
    device: str,
    batch_size: int,
    max_length: int,
) -> Tuple[np.ndarray, str]:
    if torch is None:
        raise RuntimeError("PyTorch is required for transformers RoBERTa/T5 SFT feature export.")
    try:
        from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer
    except Exception as exc:  # pragma: no cover - depends on optional package.
        raise RuntimeError("transformers is required for strict LGB RoBERTa/T5 SFT feature export.") from exc

    _seed_everything(seed)
    run_device = torch.device(device)
    if run_device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested for LGB LM SFT export but is not available.")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    classifier = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2).to(run_device)
    optimizer = torch.optim.AdamW(classifier.parameters(), lr=2e-5)
    train_indices = list(map(int, dataset.train_idx.tolist()))
    labels = torch.tensor(dataset.labels, dtype=torch.long, device=run_device)
    classifier.train()
    for _ in range(max(1, int(epochs))):
        random.shuffle(train_indices)
        for start in range(0, len(train_indices), max(1, int(batch_size))):
            batch_idx = train_indices[start : start + max(1, int(batch_size))]
            if not batch_idx:
                continue
            encoded = tokenizer(
                [dataset.texts[idx] for idx in batch_idx],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            ).to(run_device)
            out = classifier(**encoded, labels=labels[batch_idx])
            optimizer.zero_grad()
            out.loss.backward()
            optimizer.step()
    encoder = AutoModel.from_pretrained(model_name).to(run_device)
    base_state = getattr(classifier, "base_model", None)
    if base_state is not None:
        encoder.load_state_dict(base_state.state_dict(), strict=False)
    encoder.eval()
    vectors = []
    with torch.no_grad():
        for start in range(0, len(dataset.texts), max(1, int(batch_size))):
            batch_texts = dataset.texts[start : start + max(1, int(batch_size))]
            encoded = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            ).to(run_device)
            output = encoder(**encoded)
            hidden = output.last_hidden_state
            if backend == "transformers_t5_sft":
                mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
            else:
                pooled = hidden[:, 0, :]
            vectors.append(pooled.detach().cpu().numpy())
    return np.vstack(vectors).astype(np.float32), "transformer_supervised_finetuned"


def _read_feature_csv(path: Path) -> Dict[str, Sequence[float]]:
    features = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return features
        id_field = "id" if "id" in reader.fieldnames else "user_id" if "user_id" in reader.fieldnames else reader.fieldnames[0]
        feature_fields = [field for field in reader.fieldnames if field != id_field]
        for row in reader:
            node_id = _coerce_id(row.get(id_field))
            if node_id:
                features[node_id] = [float(row[field]) for field in feature_fields]
    return features


def _align_feature_map(feature_map: Mapping[str, Sequence[float]], node_ids: Sequence[str], path: Path) -> np.ndarray:
    missing = [node_id for node_id in node_ids if node_id not in feature_map]
    if missing:
        preview = ", ".join(missing[:5])
        raise ValueError(f"LGB feature file {path} missing embeddings for node id(s): {preview}")
    rows = []
    expected_dim = None
    for node_id in node_ids:
        vector = np.asarray(feature_map[node_id], dtype=np.float32)
        if vector.ndim != 1:
            raise ValueError(f"LGB feature for node {node_id} in {path} must be one-dimensional")
        if expected_dim is None:
            expected_dim = int(vector.shape[0])
        elif int(vector.shape[0]) != expected_dim:
            raise ValueError(f"LGB feature dimensions are inconsistent in {path}")
        rows.append(vector)
    arr = np.vstack(rows).astype(np.float32)
    return _validate_feature_array(arr, node_ids, path)


def _validate_feature_array(arr, node_ids: Sequence[str], path: Path) -> np.ndarray:
    features = np.asarray(arr, dtype=np.float32)
    if features.ndim != 2:
        raise ValueError(f"LGB feature array {path} must be 2-D")
    if features.shape[0] != len(node_ids):
        raise ValueError(f"LGB feature row count {features.shape[0]} does not match node count {len(node_ids)} for {path}")
    if features.shape[1] <= 0:
        raise ValueError(f"LGB feature array {path} has zero feature dimension")
    return features


def _mean_aggregate(h, edge_index):
    if edge_index.numel() == 0:
        return h
    src, dst = edge_index
    agg = torch.zeros_like(h)
    deg = torch.ones((h.size(0), 1), dtype=h.dtype, device=h.device)
    agg += h
    agg.index_add_(0, dst, h[src])
    deg.index_add_(0, dst, torch.ones((dst.size(0), 1), dtype=h.dtype, device=h.device))
    return agg / deg.clamp_min(1.0)


def _gin_aggregate(h, edge_index, eps):
    if edge_index.numel() == 0:
        return (1.0 + eps) * h
    src, dst = edge_index
    agg = torch.zeros_like(h)
    agg.index_add_(0, dst, h[src])
    return (1.0 + eps) * h + agg


def _gat_aggregate(h, edge_index, attn_layer):
    if edge_index.numel() == 0:
        return h
    src, dst = edge_index
    self_src = torch.arange(h.size(0), device=h.device)
    src_all = torch.cat([src, self_src])
    dst_all = torch.cat([dst, self_src])
    edge_repr = torch.cat([h[src_all], h[dst_all]], dim=1)
    scores = F.leaky_relu(attn_layer(edge_repr).squeeze(-1), negative_slope=0.2)
    exp_scores = torch.exp(scores - scores.max())
    denom = torch.zeros((h.size(0),), dtype=h.dtype, device=h.device)
    denom.index_add_(0, dst_all, exp_scores)
    weights = exp_scores / denom[dst_all].clamp_min(1e-12)
    out = torch.zeros_like(h)
    out.index_add_(0, dst_all, h[src_all] * weights.unsqueeze(1))
    return out


def _drop_edges(edge_index, drop_prob: float):
    if edge_index.numel() == 0 or drop_prob <= 0:
        return edge_index
    keep = torch.rand(edge_index.size(1), device=edge_index.device) >= drop_prob
    if not bool(keep.any()):
        return edge_index
    return edge_index[:, keep]


def _read_nodes(root: Path) -> List[Dict]:
    for name in ("nodes.jsonl", "users.jsonl", "node.jsonl"):
        path = root / name
        if path.is_file():
            return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    for name in ("nodes.json", "users.json", "node.json"):
        path = root / name
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, Mapping):
                data = data.get("nodes") or data.get("users") or data.get("data") or []
            return [dict(item) for item in data]
    path = root / "nodes.csv"
    if path.is_file():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    return []


def _detect_lgb_source_format(source: Path, requested: str) -> str:
    requested = requested.lower()
    if requested in {"twibot22", "twibot20"}:
        return requested
    if (source / "label.csv").is_file() and (source / "split.csv").is_file() and (source / "edge.csv").is_file():
        return "twibot22"
    if any((source / name).is_file() for name in ("train.json", "dev.json", "valid.json", "test.json", "support.json")):
        return "twibot20"
    if (source / "TwiBot-20_sample.json").is_file():
        return "twibot20"
    raise ValueError(f"Cannot auto-detect LGB source format under {source}")


def _convert_twibot22_records(
    source: Path,
    *,
    max_tweets_per_user: int,
    include_unlabeled_context: bool,
) -> Tuple[List[Dict], List[Tuple[str, str]], Dict[str, List[str]], Dict]:
    labels = _read_label_csv(source / "label.csv")
    split = _read_split_csv_ids(source / "split.csv")
    tweets_by_user = _read_twibot22_tweets(source, max_tweets_per_user=max_tweets_per_user)
    user_path = _first_existing(source, ("user.json", "user.jsonl", "node.json", "node.jsonl"))
    raw_users = list(_iter_json_records(user_path)) if user_path else []
    nodes: List[Dict] = []
    skipped_unlabeled = 0
    for raw in raw_users:
        user_id = _coerce_id(raw.get("id") or raw.get("id_str") or raw.get("user_id"))
        if not user_id:
            continue
        profile = _flatten_twibot22_profile(raw)
        profile["id"] = user_id
        profile["tweets"] = tweets_by_user.get(user_id, [])
        if user_id not in labels:
            skipped_unlabeled += 1
            if include_unlabeled_context:
                nodes.append(profile)
            continue
        profile["label"] = labels[user_id]
        nodes.append(profile)
    nodes.sort(key=lambda row: str(row["id"]))
    edges, skipped_edges = _read_twibot22_edges(source / "edge.csv")
    summary = {
        "source_format": "twibot22",
        "raw_user_count": len(raw_users),
        "labeled_nodes": len(nodes),
        "label_counts": _lgb_label_counts(nodes),
        "skipped_unlabeled_users": skipped_unlabeled,
        "raw_edge_count": len(edges) + skipped_edges,
        "skipped_edge_rows": skipped_edges,
        "tweet_files": sorted(path.name for path in _tweet_files(source)),
    }
    return nodes, edges, split, summary


def _convert_twibot20_records(
    source: Path,
    *,
    max_tweets_per_user: int,
    include_unlabeled_context: bool,
) -> Tuple[List[Dict], List[Tuple[str, str]], Dict[str, List[str]], Dict]:
    file_splits = [
        ("train.json", "train"),
        ("dev.json", "valid"),
        ("valid.json", "valid"),
        ("test.json", "test"),
        ("support.json", "support"),
        ("TwiBot-20_sample.json", "sample"),
    ]
    nodes: List[Dict] = []
    split: Dict[str, List[str]] = {"train": [], "valid": [], "test": []}
    edges: Set[Tuple[str, str]] = set()
    skipped_unlabeled = 0
    raw_count = 0
    seen: Set[str] = set()
    for filename, split_name in file_splits:
        path = source / filename
        if not path.is_file():
            jsonl_path = path.with_suffix(".jsonl")
            if jsonl_path.is_file():
                path = jsonl_path
            else:
                continue
        for raw in _iter_json_records(path):
            raw_count += 1
            user_id = _coerce_id(raw.get("ID") or raw.get("id") or raw.get("id_str"))
            if not user_id:
                continue
            if user_id in seen:
                _collect_twibot20_edges(user_id, raw.get("neighbor"), edges)
                continue
            profile = dict(raw.get("profile") or {})
            profile["id"] = user_id
            profile["tweets"] = list(raw.get("tweet") or [])[:max_tweets_per_user]
            label = raw.get("label")
            if label is None:
                skipped_unlabeled += 1
                if include_unlabeled_context:
                    nodes.append(profile)
                    seen.add(user_id)
                _collect_twibot20_edges(user_id, raw.get("neighbor"), edges)
                continue
            seen.add(user_id)
            profile["label"] = label
            nodes.append(profile)
            if split_name in split:
                split[split_name].append(user_id)
            _collect_twibot20_edges(user_id, raw.get("neighbor"), edges)
    nodes.sort(key=lambda row: str(row["id"]))
    summary = {
        "source_format": "twibot20",
        "raw_user_count": raw_count,
        "labeled_nodes": len(nodes),
        "label_counts": _lgb_label_counts(nodes),
        "skipped_unlabeled_users": skipped_unlabeled,
        "raw_edge_count": len(edges),
        "skipped_edge_rows": 0,
    }
    return nodes, sorted(edges), split, summary


def _lgb_label_counts(nodes: Sequence[Mapping]) -> Dict[str, int]:
    counts = {"human": 0, "bot": 0}
    for node in nodes:
        label = node.get("label")
        if label is None:
            continue
        try:
            value = _label_to_int(label)
        except ValueError:
            continue
        if value == 1:
            counts["bot"] += 1
        else:
            counts["human"] += 1
    return counts


def _write_compact_lgb_dataset(out: Path, nodes: Sequence[Mapping], edges: Sequence[Tuple[str, str]], split: Mapping[str, Sequence[str]]) -> None:
    (out / "nodes.jsonl").write_text("\n".join(json.dumps(dict(row), ensure_ascii=False) for row in nodes), encoding="utf-8")
    edge_lines = ["source,target"] + [f"{src},{dst}" for src, dst in edges]
    (out / "edges.csv").write_text("\n".join(edge_lines), encoding="utf-8")
    split_lines = ["id,split"]
    for name in ("train", "valid", "test"):
        for node_id in split.get(name, []):
            split_lines.append(f"{node_id},{name}")
    if len(split_lines) > 1:
        (out / "split.csv").write_text("\n".join(split_lines), encoding="utf-8")


def _read_label_csv(path: Path) -> Dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing TwiBot label.csv: {path}")
    labels: Dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            node_id = _coerce_id(row.get("id") or row.get("user_id"))
            label = row.get("label")
            if node_id and label is not None:
                labels[node_id] = str(label)
    return labels


def _read_split_csv_ids(path: Path) -> Dict[str, List[str]]:
    split: Dict[str, List[str]] = {"train": [], "valid": [], "test": []}
    if not path.is_file():
        return split
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            node_id = _coerce_id(row.get("id") or row.get("user_id"))
            split_name = str(row.get("split") or "").lower()
            if split_name in {"val", "dev"}:
                split_name = "valid"
            if node_id and split_name in split:
                split[split_name].append(node_id)
    return split


def _read_twibot22_tweets(source: Path, *, max_tweets_per_user: int) -> Dict[str, List[str]]:
    tweets_by_user: Dict[str, List[str]] = {}
    for path in _tweet_files(source):
        for row in _iter_json_records(path):
            author_id = _coerce_id(row.get("author_id") or row.get("user_id") or row.get("user") or row.get("uid"))
            text = row.get("text") or row.get("full_text") or row.get("tweet")
            if author_id and text:
                tweets = tweets_by_user.setdefault(author_id, [])
                if len(tweets) < max_tweets_per_user:
                    tweets.append(str(text))
    return tweets_by_user


def _flatten_twibot22_profile(raw: Mapping) -> Dict:
    metrics = raw.get("public_metrics") if isinstance(raw.get("public_metrics"), Mapping) else {}
    return {
        "name": raw.get("name") or raw.get("screen_name") or raw.get("username") or "",
        "screen_name": raw.get("username") or raw.get("screen_name") or "",
        "description": raw.get("description") or "",
        "created_at": raw.get("created_at") or "",
        "location": raw.get("location") or "",
        "protected": raw.get("protected", ""),
        "followers_count": raw.get("followers_count", metrics.get("followers_count", 0)),
        "friends_count": raw.get("friends_count", raw.get("following_count", metrics.get("following_count", 0))),
        "statuses_count": raw.get("statuses_count", raw.get("tweet_count", metrics.get("tweet_count", 0))),
        "listed_count": raw.get("listed_count", metrics.get("listed_count", 0)),
        "verified": raw.get("verified", ""),
    }


def _read_twibot22_edges(path: Path) -> Tuple[List[Tuple[str, str]], int]:
    if not path.is_file():
        return [], 0
    edges: List[Tuple[str, str]] = []
    skipped = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        has_header = "source" in sample.lower() and "target" in sample.lower()
        if has_header:
            for row in csv.DictReader(handle):
                src = _coerce_id(row.get("source_id") or row.get("source") or row.get("src") or row.get("from"))
                dst = _coerce_id(row.get("target_id") or row.get("target") or row.get("dst") or row.get("to"))
                if src and dst:
                    edges.append((src, dst))
                else:
                    skipped += 1
        else:
            for row in csv.reader(handle):
                if len(row) >= 2:
                    src = _coerce_id(row[0])
                    dst = _coerce_id(row[1])
                    if src and dst:
                        edges.append((src, dst))
                    else:
                        skipped += 1
    return edges, skipped


def _collect_twibot20_edges(user_id: str, neighbor, edges: Set[Tuple[str, str]]) -> None:
    if not neighbor:
        return
    if isinstance(neighbor, Mapping):
        for key, values in neighbor.items():
            if values is None:
                continue
            if not isinstance(values, (list, tuple, set)):
                values = [values]
            for value in values:
                other = _coerce_id(value)
                if not other:
                    continue
                key_lower = str(key).lower()
                if "follower" in key_lower:
                    edges.add((other, user_id))
                else:
                    edges.add((user_id, other))
        return
    if isinstance(neighbor, (list, tuple, set)):
        for value in neighbor:
            other = _coerce_id(value)
            if other:
                edges.add((user_id, other))


def _iter_json_records(path: Path) -> Iterable[Dict]:
    if not path.is_file():
        return []
    if path.suffix.lower() == ".jsonl":
        return _iter_jsonl_records(path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, Mapping):
        data = data.get("data") or data.get("nodes") or data.get("users") or data.get("tweets") or []
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    return (dict(item) for item in data if isinstance(item, Mapping))


def _iter_jsonl_records(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, Mapping):
                yield dict(row)


def _first_existing(root: Path, names: Sequence[str]) -> Optional[Path]:
    for name in names:
        path = root / name
        if path.is_file():
            return path
    return None


def _tweet_files(source: Path) -> List[Path]:
    return sorted([*source.glob("tweet*.json"), *source.glob("tweet*.jsonl")], key=lambda path: path.name)


def _coerce_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _find_twibot22_root(dataset_root: Path) -> Optional[Path]:
    for candidate in _candidate_dataset_dirs(dataset_root, "twibot-22", "twibot22", "TwiBot-22"):
        if (candidate / "label.csv").is_file() and (candidate / "split.csv").is_file():
            if _first_existing(candidate, ("user.json", "user.jsonl", "node.json", "node.jsonl")):
                return candidate
    return None


def _find_twibot20_root(dataset_root: Path, *, allow_sample: bool = False) -> Optional[Path]:
    for candidate in _candidate_dataset_dirs(dataset_root, "twibot-20", "twibot20", "TwiBot-20"):
        has_full_files = (
            (candidate / "train.json").is_file()
            or (candidate / "train.jsonl").is_file()
        ) and (
            (candidate / "dev.json").is_file()
            or (candidate / "dev.jsonl").is_file()
            or (candidate / "valid.json").is_file()
            or (candidate / "valid.jsonl").is_file()
        ) and (
            (candidate / "test.json").is_file()
            or (candidate / "test.jsonl").is_file()
        )
        if has_full_files:
            return candidate
        if allow_sample and (candidate / "TwiBot-20_sample.json").is_file():
            return candidate
    return None


def _inspect_twibot22_readiness(dataset_root: Path, dataset: str, candidate: Optional[Path]) -> Dict:
    required = ["label.csv", "split.csv", "edge.csv"]
    row = {
        "dataset": dataset,
        "source_format": "twibot22",
        "path": str(candidate) if candidate else None,
        "required_files": [*required, "user.json/user.jsonl/node.json/node.jsonl", "tweet_*.json/tweet_*.jsonl"],
        "present_files": [],
        "missing_files": [],
        "sample_only": False,
        "strict_ready": False,
        "open_items": [],
    }
    if candidate is None:
        row["missing_files"] = row["required_files"]
        row["open_items"].append(f"{dataset}: missing official TwiBot-22 directory under {dataset_root}")
        return row
    present = []
    missing = []
    for name in required:
        if (candidate / name).is_file():
            present.append(name)
        else:
            missing.append(name)
    if _first_existing(candidate, ("user.json", "user.jsonl", "node.json", "node.jsonl")):
        present.append("user.json/user.jsonl/node.json/node.jsonl")
    else:
        missing.append("user.json/user.jsonl/node.json/node.jsonl")
    if _tweet_files(candidate):
        present.append("tweet_*.json/tweet_*.jsonl")
    else:
        missing.append("tweet_*.json/tweet_*.jsonl")
    row["present_files"] = present
    row["missing_files"] = missing
    row["strict_ready"] = not missing
    if missing:
        row["open_items"].append(f"{dataset}: missing required official file(s): {', '.join(missing)}")
    return row


def _inspect_twibot20_readiness(dataset_root: Path, dataset: str, candidate: Optional[Path]) -> Dict:
    row = {
        "dataset": dataset,
        "source_format": "twibot20",
        "path": str(candidate) if candidate else None,
        "required_files": ["train.json/train.jsonl", "dev.json/dev.jsonl/valid.json/valid.jsonl", "test.json/test.jsonl"],
        "present_files": [],
        "missing_files": [],
        "sample_only": False,
        "strict_ready": False,
        "open_items": [],
    }
    sample_candidate = _find_twibot20_root(dataset_root, allow_sample=True)
    if candidate is None:
        row["path"] = str(sample_candidate) if sample_candidate else None
        row["sample_only"] = bool(sample_candidate and (sample_candidate / "TwiBot-20_sample.json").is_file())
        row["missing_files"] = row["required_files"]
        if row["sample_only"]:
            row["open_items"].append(f"{dataset}: TwiBot-20_sample.json is sample-only and cannot support strict reproduction")
        else:
            row["open_items"].append(f"{dataset}: missing official TwiBot-20 train/dev/test files under {dataset_root}")
        return row
    groups = [
        ("train.json/train.jsonl", ("train.json", "train.jsonl")),
        ("dev.json/dev.jsonl/valid.json/valid.jsonl", ("dev.json", "dev.jsonl", "valid.json", "valid.jsonl")),
        ("test.json/test.jsonl", ("test.json", "test.jsonl")),
    ]
    present = []
    missing = []
    for label, names in groups:
        if any((candidate / name).is_file() for name in names):
            present.append(label)
        else:
            missing.append(label)
    row["present_files"] = present
    row["missing_files"] = missing
    row["sample_only"] = (candidate / "TwiBot-20_sample.json").is_file() and bool(missing)
    row["strict_ready"] = not missing
    if missing:
        row["open_items"].append(f"{dataset}: missing required official file(s): {', '.join(missing)}")
    return row


def _find_lgb_official_dataset_root(dataset_root: str | Path, dataset: str, *, allow_sample: bool = False) -> Optional[Path]:
    normalized = dataset.lower().replace("_", "-")
    root = Path(dataset_root)
    if "twibot-22" in normalized or "twibot22" in normalized:
        return _find_twibot22_root(root)
    if "twibot-20" in normalized or "twibot20" in normalized:
        return _find_twibot20_root(root, allow_sample=allow_sample)
    return None


def _lgb_source_format_for_dataset(dataset: str) -> str:
    normalized = dataset.lower().replace("_", "-")
    if "twibot-22" in normalized or "twibot22" in normalized:
        return "twibot22"
    if "twibot-20" in normalized or "twibot20" in normalized:
        return "twibot20"
    return "auto"


def _lgb_text_encoder_name(encoder_backend: str) -> str:
    backend = str(encoder_backend)
    if backend == "transformers_roberta_sft":
        return "roberta_sft_features"
    if backend == "transformers_t5_sft":
        return "t5_sft_features"
    return backend


def _candidate_dataset_dirs(root: Path, *needles: str) -> Iterable[Path]:
    if not root.exists():
        return []
    lowered = [needle.lower() for needle in needles]
    candidates = [root]
    candidates.extend(path for path in root.iterdir() if path.is_dir())
    return [path for path in candidates if any(needle in path.name.lower() for needle in lowered)]


def _format_lgb_audit_markdown(audit: Mapping) -> str:
    lines = [
        "# LGB Reproduction Audit",
        "",
        f"- Task: `{audit.get('task')}`",
        f"- KT2 position: `{audit.get('kt2_position')}`",
        f"- Strict reproduction ready: `{audit.get('strict_reproduction_ready')}`",
        f"- Official data ready: `{(audit.get('official_data_readiness') or {}).get('strict_data_ready')}`",
        f"- Local adapter ready: `{audit.get('local_adapter_ready')}`",
        f"- Official converter ready: `{audit.get('official_converter_ready')}`",
        f"- LM SFT feature exporter ready: `{audit.get('lm_sft_feature_exporter_ready')}`",
        f"- External LM feature input ready: `{audit.get('external_lm_feature_input_ready')}`",
        f"- Table III ablation scheduler ready: `{audit.get('table3_ablation_scheduler_ready')}`",
        f"- Strict artifact gate ready: `{audit.get('strict_artifact_gate_ready')}`",
        f"- Strict pipeline ready: `{audit.get('strict_pipeline_ready')}`",
        f"- Data request package ready: `{audit.get('data_request_package_ready')}`",
        f"- TwiBot-22 path: `{audit.get('twibot22_path')}`",
        f"- TwiBot-20 path: `{audit.get('twibot20_path')}`",
        f"- Data request package command: `{audit.get('data_request_package_command')}`",
        f"- Strict pipeline command: `{audit.get('strict_pipeline_command')}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in audit.get("blockers", []))
    lines.extend(
        [
            "",
            "## Required Full Reproduction",
            "",
            "| Item | Requirement |",
            "|---|---|",
        ]
    )
    required = audit.get("required_full_reproduction", {})
    if isinstance(required, Mapping):
        for key, value in required.items():
            lines.append(f"| {key} | {value} |")
    lines.append("")
    return "\n".join(lines)


def _format_lgb_data_request_markdown(package: Mapping) -> str:
    lines = [
        "# LGB Official Data Request Package",
        "",
        f"- Status: `{package.get('status')}`",
        f"- Strict reproduction unblocked: `{package.get('strict_reproduction_unblocked')}`",
        f"- Dataset root: `{package.get('dataset_root')}`",
        f"- Artifacts root: `{package.get('artifacts_root')}`",
        "",
        "## Required Datasets",
        "",
        "| Dataset | Official Repository | Target Directory | Required Files |",
        "|---|---|---|---|",
    ]
    for item in package.get("datasets", []):
        if not isinstance(item, Mapping):
            continue
        lines.append(
            f"| {item.get('dataset')} | {item.get('official_repository')} | "
            f"`{item.get('target_directory')}` | {', '.join(item.get('required_files', []))} |"
        )
        lines.append(f"| {item.get('dataset')} access note | {item.get('access_note')} |  |  |")
    lines.extend(
        [
            "",
            "## Sample Data Policy",
            "",
            str(package.get("sample_data_policy")),
            "",
            "## Commands",
            "",
        ]
    )
    commands = package.get("commands", {})
    if isinstance(commands, Mapping):
        for name, command in commands.items():
            lines.extend([f"### {name}", "", "```powershell", str(command), "```", ""])
    lines.extend(["## Completion Rule", "", str(package.get("completion_rule")), ""])
    return "\n".join(lines)


def _read_edges(root: Path, id_to_idx: Mapping[str, int]) -> List[Tuple[int, int]]:
    for name in ("edges.csv", "edge.csv"):
        path = root / name
        if path.is_file():
            return _read_edge_csv(path, id_to_idx)
    path = root / "edges.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = data.get("edges", data) if isinstance(data, Mapping) else data
        edges = []
        for row in rows:
            src = str(row.get("source", row.get("src", row[0] if isinstance(row, list) and row else ""))) if not isinstance(row, str) else ""
            dst = str(row.get("target", row.get("dst", row[1] if isinstance(row, list) and len(row) > 1 else ""))) if not isinstance(row, str) else ""
            if src in id_to_idx and dst in id_to_idx:
                edges.append((id_to_idx[src], id_to_idx[dst]))
        return edges
    return []


def _read_edge_csv(path: Path, id_to_idx: Mapping[str, int]) -> List[Tuple[int, int]]:
    edges: List[Tuple[int, int]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        has_header = "source" in sample.lower() or "target" in sample.lower() or "src" in sample.lower()
        if has_header:
            for row in csv.DictReader(handle):
                src = str(row.get("source") or row.get("source_id") or row.get("src") or row.get("from") or "")
                dst = str(row.get("target") or row.get("target_id") or row.get("dst") or row.get("to") or "")
                if src in id_to_idx and dst in id_to_idx:
                    edges.append((id_to_idx[src], id_to_idx[dst]))
        else:
            for row in csv.reader(handle):
                if len(row) >= 2 and row[0] in id_to_idx and row[1] in id_to_idx:
                    edges.append((id_to_idx[row[0]], id_to_idx[row[1]]))
    return edges


def _read_split(root: Path, id_to_idx: Mapping[str, int]) -> Dict[str, List[int]]:
    path = root / "split.csv"
    if not path.is_file():
        return {}
    split = {"train": [], "valid": [], "test": []}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            node_id = str(row.get("id") or row.get("user_id") or "")
            split_name = str(row.get("split") or "").lower()
            if split_name == "val":
                split_name = "valid"
            if node_id in id_to_idx and split_name in split:
                split[split_name].append(id_to_idx[node_id])
    return split


def _normalize_tweet(text: str) -> str:
    text = re.sub(r"https?://\S+|www\.\S+", "HTTPURL", text)
    text = re.sub(r"@\w+", "@USER", text)
    text = re.sub(r"#\w+", "#HASHTAG", text)
    return " ".join(text.split())


def _label_to_int(value) -> int:
    if isinstance(value, bool):
        return int(value)
    text = str(value).strip().lower()
    if text in {"1", "bot", "bots", "true", "yes"}:
        return 1
    if text in {"0", "human", "humans", "normal", "false", "no"}:
        return 0
    raise ValueError(f"Unsupported bot label: {value!r}")


def _label_to_int_or_unlabeled(value) -> int:
    if value is None or str(value).strip().lower() in {"", "none", "null", "nan", "unlabeled", "unknown", "support"}:
        return -1
    return _label_to_int(value)


def _filter_labeled_indices(indices: Sequence[int], labels: np.ndarray) -> np.ndarray:
    return np.asarray([int(idx) for idx in indices if labels[int(idx)] >= 0], dtype=np.int64)


def _accuracy_from_logits(logits, labels) -> float:
    if labels.numel() == 0:
        return 0.0
    return float((logits.argmax(dim=1) == labels).float().mean().item())


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run LGB social bot detection reproduction adapter.")
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parser.add_argument("--data_dir", required=False)
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--hidden_dim", type=int, default=32)
    parser.add_argument("--text_dim", type=int, default=DEFAULT_TEXT_DIM)
    parser.add_argument("--epochs_lm", type=int, default=3)
    parser.add_argument("--epochs_gcl", type=int, default=3)
    parser.add_argument("--epochs_finetune", type=int, default=5)
    parser.add_argument("--edge_drop_1", type=float, default=None)
    parser.add_argument("--edge_drop_2", type=float, default=None)
    parser.add_argument("--gcl_temperature", type=float, default=None)
    parser.add_argument("--reproduction_level", default="public_code_adapter")
    parser.add_argument("--text_features_path", default=None)
    parser.add_argument("--text_encoder", default=None)
    parser.add_argument("--gnn_variant", default="GCN", choices=["GCN", "GIN", "GAT"])
    parser.add_argument("--seeds", default=None, help="Comma-separated seed list for multi-seed summary.")
    parser.add_argument("--ablation_variant", default="full")
    parser.add_argument("--ablation_variants", default=None, help="Comma-separated LGB Table III variants; triggers ablation suite when used with --seeds.")
    parser.add_argument("--fusion_mode", default="concat", choices=["concat", "average", "max", "graph_only"])
    parser.add_argument("--convert_official", action="store_true", help="Convert TwiBot official schema into compact adapter schema.")
    parser.add_argument("--export_lm_features", action="store_true", help="Export node-aligned LM SFT features for LGB.")
    parser.add_argument("--encoder_backend", default="lightweight_hashing_sft", choices=["lightweight_hashing_sft", "transformers_roberta_sft", "transformers_t5_sft"])
    parser.add_argument("--model_name", default="roberta-base")
    parser.add_argument("--feature_dim", type=int, default=DEFAULT_TEXT_DIM)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--max_length", type=int, default=256)
    parser.add_argument("--source_format", default="auto", choices=["auto", "twibot22", "twibot20"])
    parser.add_argument("--out_dir", default=None)
    parser.add_argument("--audit", action="store_true", help="Write LGB strict-reproduction readiness audit.")
    parser.add_argument("--inspect_data", action="store_true", help="Inspect official TwiBot data readiness for strict LGB reproduction.")
    parser.add_argument("--write_data_request", action="store_true", help="Write an auditable LGB official-data request package.")
    parser.add_argument("--strict_gate", action="store_true", help="Check whether LGB strict reproduction artifacts are complete.")
    parser.add_argument("--strict_pipeline", action="store_true", help="Run official-data strict LGB reproduction pipeline and then evaluate the strict gate.")
    parser.add_argument("--artifacts_root", default=None, help="Root containing TwiBot-22/TwiBot-20 LGB artifact subdirectories.")
    parser.add_argument("--write_report_md", default=None, help="Optional Markdown report path for --strict_gate output.")
    parser.add_argument("--dataset_root", default=r"G:\CISCN\dataset")
    args = parser.parse_args(argv)
    if args.audit:
        output_dir = args.out_dir or "benchmark"
        result = audit_lgb_reproduction_status(Path.cwd(), dataset_root=args.dataset_root, output_dir=output_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.inspect_data:
        result = inspect_lgb_official_data_readiness(args.dataset_root)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("strict_data_ready") else 1
    if args.write_data_request:
        result = generate_lgb_data_request_package(
            dataset_root=args.dataset_root,
            output_dir=args.out_dir or "benchmark",
            repo_root=Path.cwd(),
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.strict_gate:
        result = run_lgb_strict_reproduction_gate(args.artifacts_root or args.out_dir or "benchmark")
        if args.write_report_md:
            write_lgb_strict_gate_report(result, args.write_report_md)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "passed" else 1
    if args.strict_pipeline:
        seed_list = [int(item.strip()) for item in str(args.seeds or "42,43,44,45,46").split(",") if item.strip()]
        reproduction_level = (
            args.reproduction_level
            if "--reproduction_level" in raw_argv
            else "strict_lgb_reproduction_full_run"
        )
        result = run_lgb_strict_reproduction_pipeline(
            dataset_root=args.dataset_root,
            artifacts_root=args.artifacts_root or args.out_dir or Path("benchmark") / "lgb_strict",
            seeds=seed_list,
            encoder_backend=args.encoder_backend,
            model_name=args.model_name,
            device=args.device,
            hidden_dim=args.hidden_dim,
            text_dim=args.text_dim,
            epochs_lm=args.epochs_lm,
            epochs_gcl=args.epochs_gcl,
            epochs_finetune=args.epochs_finetune,
            batch_size=args.batch_size,
            max_length=args.max_length,
            gnn_variant=args.gnn_variant,
            reproduction_level=reproduction_level,
        )
        if args.write_report_md:
            write_lgb_strict_gate_report(result.get("gate", {}), args.write_report_md)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "passed" else 1
    if args.convert_official:
        if not args.data_dir or not args.out_dir:
            parser.error("--convert_official requires --data_dir and --out_dir")
        result = convert_lgb_official_dataset(args.data_dir, args.out_dir, source_format=args.source_format)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.export_lm_features:
        if not args.data_dir or not args.out_dir:
            parser.error("--export_lm_features requires --data_dir and --out_dir")
        result = export_lgb_lm_sft_features(
            args.data_dir,
            args.out_dir,
            encoder_backend=args.encoder_backend,
            model_name=args.model_name,
            feature_dim=args.feature_dim,
            epochs=args.epochs_lm,
            seed=args.seed,
            device=args.device,
            batch_size=args.batch_size,
            max_length=args.max_length,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if not args.data_dir:
        parser.error("--data_dir is required unless --audit is used")
    run_args = vars(args).copy()
    out_dir = args.out_dir
    for key in (
        "convert_official",
        "export_lm_features",
        "encoder_backend",
        "model_name",
        "feature_dim",
        "batch_size",
        "max_length",
        "source_format",
        "out_dir",
        "audit",
        "inspect_data",
        "write_data_request",
        "strict_gate",
        "strict_pipeline",
        "artifacts_root",
        "write_report_md",
        "dataset_root",
    ):
        run_args.pop(key, None)
    seeds = run_args.pop("seeds", None)
    if seeds:
        seed_list = [int(item.strip()) for item in str(seeds).split(",") if item.strip()]
        variants = run_args.pop("ablation_variants", None)
        if variants:
            variant_list = [item.strip() for item in str(variants).split(",") if item.strip()]
            if out_dir and "output_path" not in run_args:
                run_args["output_path"] = str(Path(out_dir) / "lgb_ablation_suite.json")
            result = run_lgb_ablation_suite(run_args.pop("data_dir"), seeds=seed_list, variants=variant_list, **run_args)
        else:
            run_args.pop("ablation_variants", None)
            if out_dir and "output_path" not in run_args:
                run_args["output_path"] = str(Path(out_dir) / "lgb_multiseed_summary.json")
            result = run_lgb_multiseed(run_args.pop("data_dir"), seeds=seed_list, **run_args)
    else:
        run_args.pop("ablation_variants", None)
        result = run_lgb_reproduction(**run_args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
