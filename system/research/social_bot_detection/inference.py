"""Checkpoint-backed BotRHG inference for account-level social posts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .artifacts import load_training_artifact
from .base_detector import BaseDetector
from .correction import ResidualCorrection
from .dataset import normalize_account_text
from .hypergraph import build_support_hyperedges, neighbor_similarities, propagate_support
from .reliability import compute_correction_risk, select_routed_accounts
from .text_encoder import TextEncoder, TextEncoderConfig

__all__ = ["BotRHGInference"]


class BotRHGInference:
    """Load one approved checkpoint and infer over an account post pool."""

    def __init__(self, checkpoint_path: str | Path, *, device: str = "cpu") -> None:
        self.checkpoint_path = Path(checkpoint_path).resolve()
        self.payload = load_training_artifact(self.checkpoint_path, map_location="cpu")
        self.device = torch.device("cuda" if device.startswith("cuda") and torch.cuda.is_available() else "cpu")
        training_config = self.payload.get("training_config", {})
        model_config = training_config.get("model", {})
        self.routing_budget = float(self.payload["routing_budget"])
        self.support_k = int(self.payload["support_k"])
        self.encoder = TextEncoder(
            TextEncoderConfig(
                model_path=self.payload["text_model_path"],
                max_length=int(model_config.get("max_length", 256)),
                batch_size=int(model_config.get("batch_size", 8)),
                max_chunks_per_account=int(model_config.get("max_chunks_per_account", self.payload.get("max_chunks_per_account", 8))),
                trainable=False,
            )
        ).to(self.device)
        encoder_state = self.payload.get("text_encoder_state_dict")
        if encoder_state is not None:
            self.encoder.encoder.load_state_dict(encoder_state)
        base_config = self.payload["base_config"]
        self.base_detector = BaseDetector(
            input_dim=int(base_config["input_dim"]),
            hidden_dim=int(base_config["hidden_dim"]),
            dropout=float(base_config["dropout"]),
        ).to(self.device)
        correction_config = self.payload["correction_config"]
        self.correction = ResidualCorrection(
            representation_dim=int(correction_config["representation_dim"]),
            projection_dim=int(correction_config["projection_dim"]),
            dropout=float(correction_config["dropout"]),
        ).to(self.device)
        self.base_detector.load_state_dict(self.payload["base_state_dict"])
        self.correction.load_state_dict(self.payload["correction_state_dict"])
        self.encoder.eval()
        self.base_detector.eval()
        self.correction.eval()

    def predict(self, posts: list[dict[str, Any]]) -> dict[str, Any]:
        """Infer all accounts in a post pool without requiring labels."""

        grouped: dict[str, list[dict[str, Any]]] = {}
        for post in posts:
            account_id = str(post.get("author_id") or "").strip()
            if account_id:
                grouped.setdefault(account_id, []).append(post)
        account_ids = sorted(grouped)
        if not account_ids:
            return self._empty_result()
        texts = [
            normalize_account_text("\n".join(str(post.get("content") or "") for post in grouped[account_id]))
            for account_id in account_ids
        ]
        with torch.no_grad():
            encoded = self.encoder.encode_all(texts, device=self.device)
            base_logits, representation = self.base_detector(encoded)
            base_probabilities = base_logits.softmax(dim=1)
            neighbors = build_support_hyperedges(representation, self.support_k)
            weights = neighbor_similarities(representation, neighbors)
            support = propagate_support(representation, neighbors, weights)
            risk = compute_correction_risk(base_probabilities, neighbors, weights)
            routed = select_routed_accounts(risk, self.routing_budget)
            corrected_probabilities = base_probabilities[:, 1].clone()
            if routed.numel():
                correction_logits = self.correction(representation[routed], support[routed])
                corrected_probabilities[routed] = correction_logits.softmax(dim=1)[:, 1]
        routed_set = set(routed.cpu().tolist())
        accounts = []
        for index, account_id in enumerate(account_ids):
            support_rows = [
                {
                    "account_id": account_ids[int(neighbor)],
                    "similarity": float(_cosine(representation[index], representation[int(neighbor)])),
                    "base_bot_probability": round(float(base_probabilities[int(neighbor), 1]), 6),
                    "final_bot_probability": round(float(corrected_probabilities[int(neighbor)]), 6),
                    "base_prediction": "bot" if base_probabilities[int(neighbor), 1] >= 0.5 else "human",
                    "final_prediction": "bot" if corrected_probabilities[int(neighbor)] >= 0.5 else "human",
                    "routed": int(neighbor) in routed_set,
                }
                for neighbor in neighbors[index].cpu().tolist()
            ]
            base_probability = float(base_probabilities[index, 1])
            final_probability = float(corrected_probabilities[index])
            accounts.append(
                {
                    "account_id": account_id,
                    "post_count": len(grouped[account_id]),
                    "base_bot_probability": round(base_probability, 6),
                    "final_bot_probability": round(final_probability, 6),
                    "base_prediction": "bot" if base_probability >= 0.5 else "human",
                    "final_prediction": "bot" if final_probability >= 0.5 else "human",
                    "confidence_deficit": round(float(1.0 - base_probabilities[index].max()), 6),
                    "correction_risk": round(float(risk[index]), 6),
                    "routed": index in routed_set,
                    "hyperedge": {
                        "center": account_id,
                        "support_nodes": [row["account_id"] for row in support_rows],
                        "support_k": len(support_rows),
                    },
                    "support_evidence": support_rows,
                }
            )
        return {
            "method": "BotRHG",
            "runtime_mode": "trained_checkpoint",
            "checkpoint_path": str(self.checkpoint_path),
            "data_fingerprint": self.payload.get("data_fingerprint", ""),
            "accounts": accounts,
            "summary": {
                "account_count": len(accounts),
                "routed_count": len(routed_set),
                "routing_budget": self.routing_budget,
                "support_k": self.support_k,
                "bot_count": sum(row["final_prediction"] == "bot" for row in accounts),
            },
            "model_card": {
                "paper_title": "BotRHG: Reliability-Guided Hypergraph Learning for Social Bot Detection",
                "feature_encoder": "local_chinese_transformer",
                "hypergraph_construction": "target_centered_knn_support_hyperedges",
                "routing": "label_free_local_disagreement_top_budget",
                "selective_rule": "preserve_base_unless_routed",
                "system_adapter": "internal_trained_checkpoint",
                "transfer_status": "weibo_text_only_adaptation",
            },
        }

    def _empty_result(self) -> dict[str, Any]:
        return {
            "method": "BotRHG",
            "runtime_mode": "trained_checkpoint",
            "checkpoint_path": str(self.checkpoint_path),
            "accounts": [],
            "summary": {"account_count": 0, "routed_count": 0, "routing_budget": self.routing_budget, "support_k": self.support_k, "bot_count": 0},
            "model_card": {"system_adapter": "internal_trained_checkpoint"},
        }


def _cosine(left: torch.Tensor, right: torch.Tensor) -> float:
    return float(torch.nn.functional.cosine_similarity(left.unsqueeze(0), right.unsqueeze(0)).item())
