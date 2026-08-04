"""Two-stage trainable BotRHG transfer workflow."""

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
from .base_detector import BaseDetector
from .contracts import AccountSample, TrainingConfig
from .correction import ResidualCorrection
from .dataset import load_social_dataset, split_samples
from .evaluation import evaluate_predictions, prediction_rows
from .hypergraph import build_reference_hyperedges, build_support_hyperedges, neighbor_similarities, propagate_support
from .reliability import compute_correction_risk, select_routed_accounts
from .text_encoder import TextEncoder, TextEncoderConfig

__all__ = ["train_botrhg"]


def train_botrhg(
    dataset_root: str | Path,
    output_dir: str | Path,
    *,
    config: TrainingConfig,
) -> dict[str, Any]:
    """Train base detector, freeze it, then train selective correction."""

    _seed_everything(config.seed)
    device = _resolve_device(config.device)
    samples, manifest = load_social_dataset(
        config.dataset_name,
        dataset_root,
        max_posts_per_account=config.model.max_posts_per_account,
    )
    splits = split_samples(
        samples,
        validation_size=config.validation_size,
        test_size=config.test_size,
        seed=config.seed,
    )
    model_path = config.model.text_model_path
    if not model_path:
        raise ValueError("TrainingConfig.model.text_model_path must point to a local Transformer checkpoint")

    text_encoder = TextEncoder(
        TextEncoderConfig(
            model_path=model_path,
            max_length=config.model.max_length,
            batch_size=config.model.batch_size,
            max_chunks_per_account=config.model.max_chunks_per_account,
            trainable=config.model.encoder_trainable,
        )
    ).to(device)
    base_detector = BaseDetector(text_encoder.hidden_size, config.model.hidden_dim, config.model.dropout).to(device)
    all_samples = splits["train"] + splits["validation"] + splits["test"]
    all_texts = [item.text for item in all_samples]
    if config.model.encoder_trainable:
        base_history = _train_base_detector_with_finetuning(
            base_detector,
            text_encoder,
            [item.text for item in splits["train"]],
            splits["train"],
            config,
            device,
        )
        all_embeddings = text_encoder.encode_all(all_texts, device=device).detach()
    else:
        all_embeddings = text_encoder.encode_all(all_texts, device=device)
        base_history = _train_base_detector(base_detector, all_embeddings[: len(splits["train"])], splits["train"], config)
    split_embeddings = {
        "train": all_embeddings[: len(splits["train"])],
        "validation": all_embeddings[len(splits["train"]) : len(splits["train"]) + len(splits["validation"])],
        "test": all_embeddings[len(splits["train"]) + len(splits["validation"]) :],
    }

    base_detector.eval()
    with torch.no_grad():
        base_logits, train_representation = base_detector(split_embeddings["train"])
    train_probabilities = base_logits.softmax(dim=1)
    train_neighbors = build_support_hyperedges(train_representation.detach(), config.model.support_k)
    train_weights = neighbor_similarities(train_representation.detach(), train_neighbors)
    train_risk = compute_correction_risk(train_probabilities.detach(), train_neighbors, train_weights)
    routed = select_routed_accounts(train_risk, config.model.routing_budget)

    correction = ResidualCorrection(config.model.hidden_dim, config.model.projection_dim, config.model.dropout).to(device)
    correction_history = _train_correction(
        correction,
        base_detector,
        split_embeddings["train"],
        splits["train"],
        train_neighbors,
        routed,
        config,
    )
    metrics, predictions = _evaluate_all_splits(
        base_detector,
        correction,
        split_embeddings,
        splits,
        train_representation.detach(),
        train_probabilities.detach(),
        config,
        device,
    )
    metrics["same_split_text_baseline"] = evaluate_text_baseline(splits["train"], splits["test"])
    calibration = _fit_temperature_calibration(predictions)
    metrics["calibration"] = calibration
    checkpoint = {
        "schema": "cogguard.botrhg.account.v2",
        "method": "BotRHG",
        "paper_method": "reliability_guided_hypergraph_learning",
        "text_model_path": str(Path(model_path).resolve()),
        "text_sampling_strategy": "uniform_account_chunks",
        "max_chunks_per_account": config.model.max_chunks_per_account,
        "text_hidden_size": text_encoder.hidden_size,
        "text_encoder_finetuned": bool(config.model.encoder_trainable),
        "text_encoder_state_dict": text_encoder.encoder.state_dict() if config.model.encoder_trainable else None,
        "base_config": {
            "input_dim": text_encoder.hidden_size,
            "hidden_dim": config.model.hidden_dim,
            "dropout": config.model.dropout,
        },
        "correction_config": {
            "representation_dim": config.model.hidden_dim,
            "projection_dim": config.model.projection_dim,
            "dropout": config.model.dropout,
        },
        "base_state_dict": base_detector.state_dict(),
        "correction_state_dict": correction.state_dict(),
        "training_config": asdict(config),
        "dataset_name": config.dataset_name,
        "data_fingerprint": manifest.data_fingerprint,
        "calibration": calibration,
        "routing_budget": config.model.routing_budget,
        "support_k": config.model.support_k,
        "device": str(device),
    }
    model_card = _model_card(manifest, config, device, metrics, len(routed))
    artifact_paths = write_training_artifacts(
        output_dir,
        checkpoint=checkpoint,
        config=config,
        manifest=manifest,
        metrics=metrics,
        predictions=predictions,
        history=base_history + correction_history,
        model_card=model_card,
    )
    return {
        "method": "BotRHG",
        "dataset": manifest.to_dict(),
        "metrics": metrics,
        "routed_count": int(len(routed)),
        "artifact_paths": artifact_paths,
    }


def _train_base_detector(
    detector: BaseDetector,
    embeddings: Tensor,
    samples: list[AccountSample],
    config: TrainingConfig,
) -> list[dict[str, Any]]:
    labels = torch.tensor([item.label for item in samples], dtype=torch.long, device=embeddings.device)
    class_counts = torch.bincount(labels, minlength=2).float()
    class_weights = (class_counts.sum() / class_counts.clamp_min(1.0)).to(embeddings.device)
    class_weights = class_weights / class_weights.mean()
    optimizer = torch.optim.AdamW(detector.parameters(), lr=config.learning_rate)
    history = []
    detector.train()
    for epoch in range(config.base_epochs):
        optimizer.zero_grad(set_to_none=True)
        logits, _ = detector(embeddings)
        loss = F.cross_entropy(logits, labels, weight=class_weights)
        loss.backward()
        optimizer.step()
        history.append({"stage": "base", "epoch": epoch + 1, "loss": float(loss.detach().cpu())})
    return history


def _train_base_detector_with_finetuning(
    detector: BaseDetector,
    text_encoder: TextEncoder,
    texts: list[str],
    samples: list[AccountSample],
    config: TrainingConfig,
    device: torch.device,
) -> list[dict[str, Any]]:
    """Jointly fine-tune the local Transformer and account classifier."""

    labels = torch.tensor([item.label for item in samples], dtype=torch.long, device=device)
    class_counts = torch.bincount(labels, minlength=2).float()
    class_weights = (class_counts.sum() / class_counts.clamp_min(1.0)).to(device)
    class_weights = class_weights / class_weights.mean()
    optimizer = torch.optim.AdamW(
        [
            {"params": detector.parameters(), "lr": config.learning_rate},
            {"params": text_encoder.encoder.parameters(), "lr": config.encoder_learning_rate},
        ]
    )
    history: list[dict[str, Any]] = []
    detector.train()
    text_encoder.train()
    for epoch in range(config.base_epochs):
        optimizer.zero_grad(set_to_none=True)
        embeddings = text_encoder.encode_all(texts, device=device)
        logits, _representation = detector(embeddings)
        loss = F.cross_entropy(logits, labels, weight=class_weights)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(text_encoder.parameters(), max_norm=1.0)
        optimizer.step()
        history.append(
            {
                "stage": "base_finetune",
                "epoch": epoch + 1,
                "loss": float(loss.detach().cpu()),
                "encoder_trainable": True,
            }
        )
    text_encoder.eval()
    return history


def _train_correction(
    correction: ResidualCorrection,
    detector: BaseDetector,
    embeddings: Tensor,
    samples: list[AccountSample],
    neighbors: Tensor,
    routed: Tensor,
    config: TrainingConfig,
) -> list[dict[str, Any]]:
    if routed.numel() == 0:
        return [{"stage": "correction", "epoch": 0, "loss": None, "skipped": True}]
    detector.eval()
    correction.train()
    optimizer = torch.optim.AdamW(correction.parameters(), lr=config.learning_rate)
    with torch.no_grad():
        _logits, representation = detector(embeddings)
        support = propagate_support(representation, neighbors, neighbor_similarities(representation, neighbors))
    labels = torch.tensor([item.label for item in samples], dtype=torch.long, device=embeddings.device)
    history = []
    for epoch in range(config.correction_epochs):
        optimizer.zero_grad(set_to_none=True)
        routed_logits = correction(representation[routed], support[routed])
        loss = F.cross_entropy(routed_logits, labels[routed]) * config.model.correction_weight
        loss.backward()
        optimizer.step()
        history.append({"stage": "correction", "epoch": epoch + 1, "loss": float(loss.detach().cpu()), "routed_count": int(routed.numel())})
    return history


def _evaluate_all_splits(
    detector: BaseDetector,
    correction: ResidualCorrection,
    split_embeddings: dict[str, Tensor],
    splits: dict[str, list[AccountSample]],
    reference_representation: Tensor,
    reference_probabilities: Tensor,
    config: TrainingConfig,
    device: torch.device,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    detector.eval()
    correction.eval()
    metrics: dict[str, Any] = {}
    predictions: list[dict[str, Any]] = []
    with torch.no_grad():
        for split_name, samples in splits.items():
            embeddings = split_embeddings[split_name]
            logits, representation = detector(embeddings)
            base_probabilities = logits.softmax(dim=1)[:, 1]
            if split_name == "train":
                neighbors = build_support_hyperedges(representation, config.model.support_k)
            else:
                neighbors = _build_reference_neighbors(representation, reference_representation, config.model.support_k)
            weights = (
                neighbor_similarities(representation, neighbors)
                if split_name == "train"
                else _reference_weights(representation, reference_representation, neighbors)
            )
            support = (
                propagate_support(representation, neighbors, weights)
                if split_name == "train"
                else _weighted_reference_support(reference_representation, neighbors, weights)
            )
            risk = compute_correction_risk(
                torch.stack([1.0 - base_probabilities, base_probabilities], dim=1),
                neighbors,
                weights,
            ) if split_name == "train" else _reference_risk(base_probabilities, reference_probabilities, neighbors, weights)
            routed = select_routed_accounts(risk, config.model.routing_budget)
            corrected_probabilities = base_probabilities.clone()
            if routed.numel():
                correction_logits = correction(representation[routed], support[routed])
                corrected_probabilities[routed] = correction_logits.softmax(dim=1)[:, 1]
            labels = [item.label for item in samples]
            metrics[f"{split_name}_base"] = evaluate_predictions(labels, base_probabilities.cpu().numpy(), routed_count=0, routing_budget=config.model.routing_budget, split=f"{split_name}_base").to_dict()
            metrics[f"{split_name}_corrected"] = evaluate_predictions(labels, corrected_probabilities.cpu().numpy(), routed_count=int(routed.numel()), routing_budget=config.model.routing_budget, split=f"{split_name}_corrected").to_dict()
            predictions.extend(
                prediction_rows(
                    [item.account_id for item in samples],
                    labels,
                    base_probabilities.cpu().numpy(),
                    corrected_probabilities.cpu().numpy(),
                    np.isin(np.arange(len(samples)), routed.cpu().numpy()),
                    [item.source_label for item in samples],
                    split=f"{split_name}_corrected",
                )
            )
    return metrics, predictions


def _build_reference_neighbors(query: Tensor, reference: Tensor, support_k: int) -> Tensor:
    return build_reference_hyperedges(query, reference, support_k)


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
    reference = (reference_probabilities[neighbors] * normalized_weights.unsqueeze(-1)).sum(dim=1)
    disagreement = (reference[:, 1] - probabilities).abs()
    return (0.5 * confidence_deficit + 0.5 * disagreement).clamp(0.0, 1.0)


def _resolve_device(requested: str) -> torch.device:
    if requested.startswith("cuda") and not torch.cuda.is_available():
        return torch.device("cpu")
    return torch.device(requested)


def _fit_temperature_calibration(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    validation_rows = [row for row in predictions if str(row.get("split") or "") == "validation_corrected"]
    if not validation_rows:
        return {"method": "temperature_scaling", "passed": False, "reason": "validation split unavailable"}
    labels = np.asarray([int(row["label"]) for row in validation_rows], dtype=np.float64)
    probabilities = np.asarray([float(row["corrected_bot_probability"]) for row in validation_rows], dtype=np.float64)
    if len(np.unique(labels)) < 2:
        return {"method": "temperature_scaling", "passed": False, "reason": "validation split has one class"}
    best_temperature = 1.0
    best_nll = float("inf")
    for temperature in np.linspace(0.5, 5.0, 46):
        calibrated = _apply_temperature(probabilities, float(temperature))
        nll = -np.mean(
            labels * np.log(np.clip(calibrated, 1e-8, 1.0))
            + (1.0 - labels) * np.log(np.clip(1.0 - calibrated, 1e-8, 1.0))
        )
        if nll < best_nll:
            best_nll = float(nll)
            best_temperature = float(temperature)
    calibrated_probabilities = _apply_temperature(probabilities, best_temperature)
    ece = _expected_calibration_error(labels, calibrated_probabilities)
    return {
        "method": "temperature_scaling",
        "passed": bool(ece <= 0.08),
        "temperature": round(best_temperature, 6),
        "ece": round(float(ece), 6),
        "validation_count": int(len(validation_rows)),
    }


def _apply_temperature(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1e-8, 1.0 - 1e-8) / np.clip(1.0 - probabilities, 1e-8, 1.0))
    return 1.0 / (1.0 + np.exp(-(logits / temperature)))


def _expected_calibration_error(labels: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> float:
    predictions = (probabilities >= 0.5).astype(np.float64)
    confidences = np.maximum(probabilities, 1.0 - probabilities)
    correct = (predictions == labels).astype(np.float64)
    ece = 0.0
    for start in np.linspace(0.0, 1.0, bins, endpoint=False):
        end = start + (1.0 / bins)
        mask = (confidences > start) & (confidences <= end)
        if not np.any(mask):
            continue
        ece += float(mask.mean()) * abs(float(correct[mask].mean()) - float(confidences[mask].mean()))
    return ece


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _model_card(manifest: Any, config: TrainingConfig, device: torch.device, metrics: dict[str, Any], routed_count: int) -> str:
    return f"""# BotRHG Social-Bot Transfer Model Card

## Status

This is a trainable local transfer implementation of **BotRHG: Reliability-Guided Hypergraph Learning for Social Bot Detection**. It is not a claim of exact reproduction of the paper's original benchmark.

## Method

1. A local RoBERTa-family Transformer encodes each account's unified profile/post sequence.
   Long accounts are represented by a deterministic sample of up to {config.model.max_posts_per_account} posts and {config.model.max_chunks_per_account} token chunks.
2. A trainable low-order account detector is optimized with supervised cross-entropy.
3. The detector is frozen; target-centered KNN support hyperedges are built from learned representations, excluding each target from its own support.
4. Confidence deficit and label-free neighborhood disagreement determine a top-{config.model.routing_budget:.0%} correction route.
5. Only routed accounts receive learned support fusion and residual correction; other accounts preserve the base posterior.

## Dataset and transfer boundary

- Dataset: `{manifest.dataset_name or config.dataset_name}`
- Source: `{manifest.source_root}`
- Fingerprint: `{manifest.data_fingerprint}`
- Usable accounts: `{manifest.usable_account_count}`
- Label provenance: `{manifest.label_provenance}`
- Text provenance: `{manifest.text_provenance}`
- Property fields: retained for provenance only; no fabricated metadata is used.
- Explicit social graph: `{manifest.social_graph_coverage}`
- Adaptation: KNN support hyperedges in learned representation space replace unavailable explicit social edges.
- Device: `{device}`
- Checkpoint SHA-256: recorded in `checkpoint.sha256`
- Text sampling: bounded deterministic account posts, max `{config.model.max_posts_per_account}` posts and `{config.model.max_chunks_per_account}` chunks
- Routed accounts in training: `{routed_count}`

The original NLPCC research directory is not imported or executed. The existing TF-IDF baseline and deterministic proxy remain separate reference paths.

## Limitations

This is a text-only transfer implementation and not an exact reproduction of the paper's original benchmark. The supplied corpora differ in label construction, profile coverage, and availability of tweet text. Results require per-dataset baselines and must not be read as a cross-dataset generalization claim.
"""
