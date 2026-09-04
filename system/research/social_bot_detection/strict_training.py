"""Strict BotRHG training workflow aligned with the paper structure."""

from __future__ import annotations

import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor
from torch.nn import functional as F

from .artifacts import write_training_artifacts
from .baseline import evaluate_text_baseline
from .contracts import TrainingConfig
from .evaluation import evaluate_predictions, prediction_rows
from .hypergraph import build_reference_hyperedges, build_support_hyperedges, neighbor_similarities, propagate_support
from .reliability import compute_correction_risk, select_routed_accounts
from .strict_contracts import StrictAccountRecord, StrictCorpus
from .strict_datasets import load_strict_social_corpus
from .strict_features import assemble_property_tensor, assemble_relation_tensors, build_feature_schema, build_node_index, derive_numeric_stats, split_records
from .strict_model import StrictBotRHGModel
from .text_encoder import TextEncoder, TextEncoderConfig

__all__ = ["train_strict_botrhg"]


def train_strict_botrhg(
    dataset_root: str | Path,
    output_dir: str | Path,
    *,
    dataset_name: str,
    config: TrainingConfig,
) -> dict[str, Any]:
    """Train the paper-aligned BotRHG stack on one supported corpus."""

    _seed_everything(config.seed)
    device = _resolve_device(config.device)
    corpus = load_strict_social_corpus(
        dataset_name,
        dataset_root,
        max_posts_per_account=config.model.max_posts_per_account,
    )
    splits = split_records(
        corpus.records,
        validation_size=config.validation_size,
        test_size=config.test_size,
        seed=config.seed,
    )
    schema = build_feature_schema(splits["train"])
    numeric_stats = derive_numeric_stats(splits["train"], schema)
    node_index = build_node_index(corpus.records)
    property_tensor = assemble_property_tensor(corpus.records, schema, numeric_stats, device=device)
    edge_index, edge_type, relation_types = assemble_relation_tensors(corpus.graph, node_index, device=device)

    text_encoder = TextEncoder(
        TextEncoderConfig(
            model_path=config.model.text_model_path,
            max_length=config.model.max_length,
            batch_size=config.model.batch_size,
            max_chunks_per_account=config.model.max_chunks_per_account,
            trainable=config.model.encoder_trainable,
        )
    ).to(device)
    model = StrictBotRHGModel(
        text_dim=text_encoder.hidden_size,
        property_dim=property_tensor.shape[1],
        graph_dim=config.model.hidden_dim,
        hidden_dim=config.model.hidden_dim,
        projection_dim=config.model.projection_dim,
        dropout=config.model.dropout,
        num_relations=len(relation_types),
    ).to(device)

    all_texts = [record.text for record in corpus.records]
    split_indices = {name: indices.to(device) for name, indices in _split_indices(corpus.records, splits).items()}
    train_labels = torch.tensor([record.label for record in splits["train"]], dtype=torch.long, device=device)
    class_weights = _class_weights(train_labels)

    base_history = _train_base_stage(
        text_encoder,
        model,
        all_texts,
        property_tensor,
        edge_index,
        edge_type,
        split_indices["train"],
        train_labels,
        class_weights,
        config,
        device,
    )

    with torch.no_grad():
        text_embeddings = text_encoder.encode_all(all_texts, device=device)
        logits, low_repr, _combined_repr, support_anchor, _property_repr = model.encode_nodes(
            text_embeddings,
            property_tensor,
            edge_index,
            edge_type,
        )
        train_low_repr = low_repr[split_indices["train"]]
        train_support_anchor = support_anchor[split_indices["train"]]
        train_logits = logits[split_indices["train"]]
        train_probabilities = train_logits.softmax(dim=1)
        train_neighbors = build_support_hyperedges(train_support_anchor, config.model.support_k)
        train_weights = neighbor_similarities(train_support_anchor, train_neighbors)
        train_risk = compute_correction_risk(train_probabilities, train_neighbors, train_weights)
        routed = select_routed_accounts(train_risk, config.model.routing_budget)
        train_support = propagate_support(train_support_anchor, train_neighbors, train_weights)

    correction_history = _train_correction_stage(
        model,
        train_low_repr,
        train_support,
        routed,
        train_labels,
        config,
    )

    metrics, predictions = _evaluate_splits(
        text_encoder=text_encoder,
        model=model,
        corpus=corpus,
        property_tensor=property_tensor,
        edge_index=edge_index,
        edge_type=edge_type,
        split_indices=split_indices,
        train_support_anchor=train_support_anchor,
        train_probabilities=train_probabilities,
        config=config,
        device=device,
    )
    metrics["same_split_text_baseline"] = evaluate_text_baseline(splits["train"], splits["test"])
    model.eval()
    text_encoder.eval()
    checkpoint = {
        "schema": "cogguard.botrhg.strict.v1",
        "method": "BotRHG",
        "paper_method": "reliability_guided_hypergraph_learning",
        "strict_method": True,
        "dataset_name": corpus.manifest.dataset_name,
        "data_fingerprint": corpus.manifest.data_fingerprint,
        "text_model_path": str(Path(config.model.text_model_path).resolve()),
        "text_sampling_strategy": "unified_profile_description_tweets",
        "max_chunks_per_account": config.model.max_chunks_per_account,
        "text_hidden_size": text_encoder.hidden_size,
        "text_encoder_finetuned": bool(config.model.encoder_trainable),
        "text_encoder_state_dict": text_encoder.encoder.state_dict(),
        "feature_schema": schema.to_dict(),
        "numeric_stats": {field: {"mean": mean, "std": std} for field, (mean, std) in numeric_stats.items()},
        "graph_available": corpus.graph.available,
        "graph_relation_types": list(corpus.graph.relation_types),
        "graph_state_dict": model.graph_encoder.state_dict(),
        "property_state_dict": model.property_encoder.state_dict(),
        "support_projection_state_dict": model.support_projection.state_dict(),
        "base_config": {
            "input_dim": text_encoder.hidden_size + model.property_encoder.network[0].out_features + config.model.hidden_dim,
            "hidden_dim": config.model.hidden_dim,
            "dropout": config.model.dropout,
        },
        "correction_config": {
            "representation_dim": config.model.hidden_dim,
            "projection_dim": config.model.projection_dim,
            "dropout": config.model.dropout,
        },
        "base_state_dict": model.base_detector.state_dict(),
        "correction_state_dict": model.correction.state_dict(),
        "training_config": asdict(config),
        "routing_budget": config.model.routing_budget,
        "support_k": config.model.support_k,
        "device": str(device),
    }
    model_card = _model_card(corpus, config, device, metrics, int(routed.numel()), corpus.graph.available)
    artifact_paths = write_training_artifacts(
        output_dir,
        checkpoint=checkpoint,
        config=config,
        manifest=corpus.manifest,
        metrics=metrics,
        predictions=predictions,
        history=base_history + correction_history,
        model_card=model_card,
    )
    return {
        "method": "BotRHG",
        "dataset": corpus.manifest.to_dict(),
        "metrics": metrics,
        "routed_count": int(routed.numel()),
        "artifact_paths": artifact_paths,
    }


def _train_base_stage(
    text_encoder: TextEncoder,
    model: StrictBotRHGModel,
    texts: list[str],
    property_tensor: Tensor,
    edge_index: Tensor | None,
    edge_type: Tensor | None,
    train_indices: Tensor,
    train_labels: Tensor,
    class_weights: Tensor,
    config: TrainingConfig,
    device: torch.device,
) -> list[dict[str, Any]]:
    trainable_groups = [
        {"params": model.property_encoder.parameters(), "lr": config.learning_rate},
        {"params": model.graph_encoder.parameters(), "lr": config.learning_rate},
        {"params": model.support_projection.parameters(), "lr": config.learning_rate},
        {"params": model.base_detector.parameters(), "lr": config.learning_rate},
    ]
    if text_encoder.config.trainable:
        trainable_groups.insert(0, {"params": text_encoder.encoder.parameters(), "lr": config.encoder_learning_rate})
        text_encoder.train()
    else:
        text_encoder.eval()
    model.train()
    optimizer = torch.optim.AdamW(trainable_groups)
    history: list[dict[str, Any]] = []
    for epoch in range(config.base_epochs):
        optimizer.zero_grad(set_to_none=True)
        text_embeddings = text_encoder.encode_all(texts, device=device)
        logits, _low_repr, _combined_repr, _support_anchor, _property_repr = model.encode_nodes(
            text_embeddings,
            property_tensor,
            edge_index,
            edge_type,
        )
        loss = F.cross_entropy(logits[train_indices], train_labels, weight=class_weights)
        loss.backward()
        if text_encoder.config.trainable:
            torch.nn.utils.clip_grad_norm_(text_encoder.encoder.parameters(), max_norm=1.0)
        torch.nn.utils.clip_grad_norm_(
            [
                *model.property_encoder.parameters(),
                *model.graph_encoder.parameters(),
                *model.support_projection.parameters(),
                *model.base_detector.parameters(),
            ],
            max_norm=5.0,
        )
        optimizer.step()
        history.append(
            {
                "stage": "base",
                "epoch": epoch + 1,
                "loss": float(loss.detach().cpu()),
                "encoder_trainable": bool(text_encoder.config.trainable),
            }
        )
    model.eval()
    text_encoder.eval()
    return history


def _train_correction_stage(
    model: StrictBotRHGModel,
    train_low_repr: Tensor,
    train_support: Tensor,
    routed: Tensor,
    train_labels: Tensor,
    config: TrainingConfig,
) -> list[dict[str, Any]]:
    if routed.numel() == 0:
        return [{"stage": "correction", "epoch": 0, "loss": None, "skipped": True}]
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for parameter in model.correction.parameters():
        parameter.requires_grad_(True)
    model.correction.train()
    optimizer = torch.optim.AdamW(model.correction.parameters(), lr=config.learning_rate)
    history: list[dict[str, Any]] = []
    for epoch in range(config.correction_epochs):
        optimizer.zero_grad(set_to_none=True)
        routed_logits = model.correction(train_low_repr[routed], train_support[routed])
        loss = F.cross_entropy(routed_logits, train_labels[routed]) * config.model.correction_weight
        loss.backward()
        optimizer.step()
        history.append({"stage": "correction", "epoch": epoch + 1, "loss": float(loss.detach().cpu()), "routed_count": int(routed.numel())})
    model.eval()
    return history


def _evaluate_splits(
    *,
    text_encoder: TextEncoder,
    model: StrictBotRHGModel,
    corpus: StrictCorpus,
    property_tensor: Tensor,
    edge_index: Tensor | None,
    edge_type: Tensor | None,
    split_indices: dict[str, Tensor],
    train_support_anchor: Tensor,
    train_probabilities: Tensor,
    config: TrainingConfig,
    device: torch.device,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    del device
    text_embeddings = text_encoder.encode_all([record.text for record in corpus.records], device=property_tensor.device)
    logits, low_repr, _combined_repr, support_anchor, _property_repr = model.encode_nodes(
        text_embeddings,
        property_tensor,
        edge_index,
        edge_type,
    )
    metrics: dict[str, Any] = {}
    predictions: list[dict[str, Any]] = []
    reference_probabilities = train_probabilities
    reference_support_anchor = train_support_anchor
    for split_name, indices in split_indices.items():
        split_logits = logits[indices]
        split_low = low_repr[indices]
        split_anchor = support_anchor[indices]
        base_probabilities = split_logits.softmax(dim=1)[:, 1]
        if split_name == "train":
            neighbors = build_support_hyperedges(split_anchor, config.model.support_k)
            weights = neighbor_similarities(split_anchor, neighbors)
            support = propagate_support(split_anchor, neighbors, weights)
            risk = compute_correction_risk(torch.stack([1.0 - base_probabilities, base_probabilities], dim=1), neighbors, weights)
        else:
            neighbors = build_reference_hyperedges(split_anchor, reference_support_anchor, config.model.support_k)
            weights = _reference_weights(split_anchor, reference_support_anchor, neighbors)
            support = _weighted_reference_support(reference_support_anchor, neighbors, weights)
            risk = _reference_risk(base_probabilities, reference_probabilities[:, 1], neighbors, weights)
        routed = select_routed_accounts(risk, config.model.routing_budget)
        corrected_probabilities = base_probabilities.clone()
        if routed.numel():
            correction_logits = model.correction(split_low[routed], support[routed])
            corrected_probabilities[routed] = correction_logits.softmax(dim=1)[:, 1]
        labels = [corpus.records[int(index)].label for index in indices.tolist()]
        source_labels = [corpus.records[int(index)].source_label for index in indices.tolist()]
        metrics[f"{split_name}_base"] = evaluate_predictions(
            labels,
            base_probabilities.detach().cpu().numpy(),
            routed_count=0,
            routing_budget=config.model.routing_budget,
            split=f"{split_name}_base",
        ).to_dict()
        metrics[f"{split_name}_corrected"] = evaluate_predictions(
            labels,
            corrected_probabilities.detach().cpu().numpy(),
            routed_count=int(routed.numel()),
            routing_budget=config.model.routing_budget,
            split=f"{split_name}_corrected",
        ).to_dict()
        predictions.extend(
            prediction_rows(
                [corpus.records[int(index)].account_id for index in indices.tolist()],
                labels,
                base_probabilities.detach().cpu().numpy(),
                corrected_probabilities.detach().cpu().numpy(),
                np.isin(np.arange(len(indices)), routed.detach().cpu().numpy()),
                source_labels,
            )
        )
    return metrics, predictions


def _reference_weights(query: Tensor, reference: Tensor, neighbors: Tensor) -> Tensor:
    query_norm = F.normalize(query, p=2, dim=1)
    reference_norm = F.normalize(reference, p=2, dim=1)
    return (query_norm.unsqueeze(1) * reference_norm[neighbors]).sum(dim=2).clamp_min(0.0)


def _weighted_reference_support(reference: Tensor, neighbors: Tensor, weights: Tensor) -> Tensor:
    normalized_weights = weights / weights.sum(dim=1, keepdim=True).clamp_min(1e-8)
    return (reference[neighbors] * normalized_weights.unsqueeze(-1)).sum(dim=1)


def _reference_risk(
    probabilities: Tensor,
    reference_probabilities: Tensor,
    neighbors: Tensor,
    weights: Tensor,
) -> Tensor:
    confidence_deficit = 1.0 - torch.stack([1.0 - probabilities, probabilities], dim=1).max(dim=1).values
    normalized_weights = weights / weights.sum(dim=1, keepdim=True).clamp_min(1e-8)
    reference = (reference_probabilities[neighbors] * normalized_weights).sum(dim=1)
    disagreement = (reference - probabilities).abs()
    return (0.5 * confidence_deficit + 0.5 * disagreement).clamp(0.0, 1.0)


def _split_indices(records: list[StrictAccountRecord], splits: dict[str, list[StrictAccountRecord]]) -> dict[str, Tensor]:
    index_by_id = {record.account_id: index for index, record in enumerate(records)}
    return {
        split_name: torch.tensor([index_by_id[record.account_id] for record in split_records], dtype=torch.long)
        for split_name, split_records in splits.items()
    }


def _class_weights(labels: Tensor) -> Tensor:
    class_counts = torch.bincount(labels.detach().cpu(), minlength=2).float().to(labels.device)
    weights = class_counts.sum() / class_counts.clamp_min(1.0)
    return weights / weights.mean().clamp_min(1e-8)


def _resolve_device(requested: str) -> torch.device:
    if requested.startswith("cuda") and not torch.cuda.is_available():
        return torch.device("cpu")
    return torch.device(requested)


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _model_card(
    corpus: StrictCorpus,
    config: TrainingConfig,
    device: torch.device,
    metrics: dict[str, Any],
    routed_count: int,
    graph_available: bool,
) -> str:
    return f"""# Strict BotRHG Social-Bot Model Card

## Status

This is a paper-aligned BotRHG training run that follows the NLPCC submission structure:
text encoder, property encoder, relational graph encoder, target-centered kNN hyperedges, reliability-guided routing, and selective residual correction.

## Dataset and adaptation

- Dataset: `{corpus.manifest.dataset_name}`
- Source: `{corpus.manifest.source_root}`
- Fingerprint: `{corpus.manifest.data_fingerprint}`
- Usable accounts: `{corpus.manifest.usable_account_count}`
- Label provenance: `{corpus.manifest.label_provenance}`
- Text provenance: `{corpus.manifest.text_provenance}`
- Property coverage: `{corpus.manifest.property_field_coverage}`
- Social graph coverage: `{corpus.manifest.social_graph_coverage}`
- Graph available: `{graph_available}`
- Device: `{device}`
- Checkpoint SHA-256: recorded in `checkpoint.sha256`
- Routed accounts in training: `{routed_count}`

## Strict method

1. Unified account text is linearized from profile, description, and sampled tweets.
2. Numeric and categorical profile/activity features are normalized into a property encoder.
3. A relational graph encoder consumes dataset-specific account relations when available.
4. The base detector learns low-order account representations.
5. Target-centered kNN hyperedges route low-reliability accounts for selective residual correction.

## Scope

The strict run uses dataset-specific adaptation:

- Cresci-2015: explicit follower/friend relations plus tweet text
- Cresci-2017: reply/retweet relations derived from tweet interactions
- Midterm-2018: profile properties and text only; graph evidence is unavailable and recorded as such

## Limitations

This is a strict adaptation of the paper structure, not an exact reproduction of the original published benchmarks. Differences in archive coverage, relation availability, and pretrained checkpoint choice remain documented in the manifest and checkpoint metadata.
"""
