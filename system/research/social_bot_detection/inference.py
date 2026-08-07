"""Checkpoint-backed BotRHG inference for account-level social posts."""

from __future__ import annotations

import json
from contextlib import contextmanager
from io import BytesIO
from dataclasses import replace
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, Mapping

import numpy as np
import torch

from .artifacts import load_training_artifact, load_training_artifact_bytes
from .base_detector import BaseDetector
from .correction import ResidualCorrection
from .dataset import normalize_account_text
from .hypergraph import build_support_hyperedges, neighbor_similarities, propagate_support
from .reliability import compute_correction_risk, select_routed_accounts
from .strict_contracts import StrictAccountRecord, StrictFeatureSchema, StrictGraph, StrictRelationEdge
from .strict_features import (
    STRICT_CATEGORICAL_FIELDS,
    STRICT_NUMERIC_FIELDS,
    assemble_property_tensor,
    assemble_relation_tensors,
    linearize_account_text,
    normalize_nlpcc_text,
    parse_timestamp,
)
from .strict_model import StrictBotRHGModel
from .text_encoder import TextEncoder, TextEncoderConfig

__all__ = ["BotRHGInference", "StrictBotRHGInference", "create_botrhg_inference"]


def create_botrhg_inference(
    checkpoint_path: str | Path,
    *,
    device: str = "cpu",
    encoder_path: str | Path | None = None,
    feature_schema_path: str | Path | None = None,
    calibration_path: str | Path | None = None,
    expected_source_schema: str = "",
    checkpoint_bytes: bytes | None = None,
    encoder_bytes: bytes | None = None,
    feature_schema_bytes: bytes | None = None,
    calibration_bytes: bytes | None = None,
) -> Any:
    """Create the runtime matching the checkpoint schema."""

    payload = (
        load_training_artifact_bytes(checkpoint_bytes, map_location="cpu", source=str(checkpoint_path))
        if checkpoint_bytes is not None
        else load_training_artifact(checkpoint_path, map_location="cpu")
    )
    if isinstance(payload, dict) and payload.get("schema") in {
        "cogguard.botrhg.strict.v1",
        "cogguard.botrhg.account.v3",
    }:
        return StrictBotRHGInference(
            checkpoint_path,
            device=device,
            encoder_path=encoder_path,
            feature_schema_path=feature_schema_path,
            calibration_path=calibration_path,
            expected_source_schema=expected_source_schema,
            checkpoint_payload=payload,
            encoder_bytes=encoder_bytes,
            feature_schema_bytes=feature_schema_bytes,
            calibration_bytes=calibration_bytes,
        )
    if any(
        (
            encoder_path,
            feature_schema_path,
            calibration_path,
            expected_source_schema,
            encoder_bytes,
            feature_schema_bytes,
            calibration_bytes,
        )
    ):
        raise ValueError("verified bundle components require a strict account checkpoint")
    return BotRHGInference(checkpoint_path, device=device, checkpoint_payload=payload)


class BotRHGInference:
    """Load one approved checkpoint and infer over an account post pool."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        *,
        device: str = "cpu",
        checkpoint_payload: Mapping[str, Any] | None = None,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path).resolve()
        self.payload = (
            dict(checkpoint_payload)
            if checkpoint_payload is not None
            else load_training_artifact(self.checkpoint_path, map_location="cpu")
        )
        self.device = torch.device("cuda" if device.startswith("cuda") and torch.cuda.is_available() else "cpu")
        self.calibration = self.payload.get("calibration") if isinstance(self.payload.get("calibration"), dict) else {}
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
            base_probability = float(base_probabilities[index, 1])
            final_probability = float(corrected_probabilities[index])
            calibrated_probability = _calibrated_probability(final_probability, self.calibration)
            representation_row = representation[index].detach().cpu().tolist()
            badge_embedding = _badge_gradient_embedding(
                representation[index],
                self.base_detector.classifier,
            )
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
            accounts.append(
                {
                    "account_id": account_id,
                    "post_count": len(grouped[account_id]),
                    "base_bot_probability": round(base_probability, 6),
                    "final_bot_probability": round(final_probability, 6),
                    "calibrated_bot_probability": round(float(calibrated_probability), 6)
                    if calibrated_probability is not None
                    else None,
                    "calibrated_probability": round(float(calibrated_probability), 6)
                    if calibrated_probability is not None
                    else None,
                    "calibrated": calibrated_probability is not None,
                    "calibration_passed": calibrated_probability is not None,
                    "calibration_source": str(self.calibration.get("method") or "")
                    if calibrated_probability is not None
                    else "",
                    "representation": [round(float(value), 8) for value in representation_row],
                    "badge_embedding": badge_embedding,
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
                "calibration_status": "available" if self.calibration else "unavailable",
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


class StrictBotRHGInference:
    """Inference adapter for the strict research checkpoint schema."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        *,
        device: str = "cpu",
        encoder_path: str | Path | None = None,
        feature_schema_path: str | Path | None = None,
        calibration_path: str | Path | None = None,
        expected_source_schema: str = "",
        checkpoint_payload: Mapping[str, Any] | None = None,
        encoder_bytes: bytes | None = None,
        feature_schema_bytes: bytes | None = None,
        calibration_bytes: bytes | None = None,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path).resolve()
        self.payload = (
            dict(checkpoint_payload)
            if checkpoint_payload is not None
            else load_training_artifact(self.checkpoint_path, map_location="cpu")
        )
        source_schema = str(self.payload.get("schema") or "")
        if expected_source_schema and source_schema != expected_source_schema:
            raise ValueError("detector checkpoint source schema does not match the verified bundle")
        self.device = torch.device("cuda" if device.startswith("cuda") and torch.cuda.is_available() else "cpu")
        training_config = self.payload.get("training_config", {})
        model_config = training_config.get("model", {})
        self.routing_budget = float(self.payload.get("routing_budget", 0.10))
        self.support_k = int(self.payload.get("support_k", 8))
        checkpoint_calibration = self.payload.get("calibration")
        checkpoint_calibration = checkpoint_calibration if isinstance(checkpoint_calibration, dict) else {}
        bundle_calibration = (
            _read_json_mapping(calibration_path, "calibration", payload_bytes=calibration_bytes)
            if calibration_path is not None or calibration_bytes is not None
            else None
        )
        if bundle_calibration is not None and bundle_calibration != checkpoint_calibration:
            raise ValueError("bundle calibration differs from the detector checkpoint")
        self.calibration = dict(bundle_calibration) if bundle_calibration is not None else checkpoint_calibration
        with _text_runtime_model_path(
            self.payload,
            require_embedded=bool(expected_source_schema),
        ) as runtime_model_path:
            self.encoder = TextEncoder(
                TextEncoderConfig(
                    model_path=str(runtime_model_path),
                    max_length=int(model_config.get("max_length", 256)),
                    batch_size=int(model_config.get("batch_size", 8)),
                    max_chunks_per_account=int(model_config.get("max_chunks_per_account", 8)),
                    trainable=False,
                    initialize_from_config=runtime_model_path != Path(str(self.payload["text_model_path"])),
                )
            ).to(self.device)
        encoder_state = self.payload.get("text_encoder_state_dict")
        if encoder_path is not None or encoder_bytes is not None:
            bundle_encoder_state = _load_encoder_component(
                encoder_path,
                source_schema,
                payload_bytes=encoder_bytes,
            )
            if not _state_dicts_equal(bundle_encoder_state, encoder_state):
                raise ValueError("bundle encoder differs from the detector checkpoint")
            encoder_state = bundle_encoder_state
        if encoder_state is not None:
            self.encoder.encoder.load_state_dict(encoder_state)
        checkpoint_feature_schema = _checkpoint_feature_schema(self.payload.get("feature_schema"))
        if feature_schema_path is not None or feature_schema_bytes is not None:
            bundle_feature_schema = _checkpoint_feature_schema(
                _read_json_mapping(
                    feature_schema_path,
                    "feature schema",
                    payload_bytes=feature_schema_bytes,
                )
            )
            if bundle_feature_schema.to_dict() != checkpoint_feature_schema.to_dict():
                raise ValueError("bundle feature schema differs from the detector checkpoint")
            self.feature_schema = bundle_feature_schema
        else:
            self.feature_schema = checkpoint_feature_schema
        self.numeric_stats = _checkpoint_numeric_stats(self.payload.get("numeric_stats"), self.feature_schema)
        self.graph_relation_types = tuple(
            str(value).strip()
            for value in (self.payload.get("graph_relation_types") or ())
            if str(value).strip()
        )
        property_dim = len(self.feature_schema.numeric_fields) + sum(
            len(self.feature_schema.categorical_vocab.get(field, ())) + 1
            for field in self.feature_schema.categorical_fields
        )
        hidden_dim = int((self.payload.get("base_config") or {}).get("hidden_dim", 128))
        projection_dim = int((self.payload.get("correction_config") or {}).get("projection_dim", 64))
        dropout = float((self.payload.get("base_config") or {}).get("dropout", 0.2))
        self.model = StrictBotRHGModel(
            text_dim=int(self.payload.get("text_hidden_size", self.encoder.hidden_size)),
            property_dim=property_dim,
            graph_dim=hidden_dim,
            hidden_dim=hidden_dim,
            projection_dim=projection_dim,
            dropout=dropout,
            num_relations=len(self.graph_relation_types),
        ).to(self.device)
        self.model.property_encoder.load_state_dict(self.payload["property_state_dict"])
        self.model.graph_encoder.load_state_dict(self.payload["graph_state_dict"])
        self.model.support_projection.load_state_dict(self.payload["support_projection_state_dict"])
        self.model.base_detector.load_state_dict(self.payload["base_state_dict"])
        self.model.correction.load_state_dict(self.payload["correction_state_dict"])
        self.encoder.eval()
        self.model.eval()

    def predict(self, posts: list[dict[str, Any]]) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for post in posts:
            account_id = str(post.get("author_id") or post.get("user_id") or "").strip()
            if account_id:
                grouped.setdefault(account_id, []).append(post)
        account_ids = sorted(grouped)
        if not account_ids:
            return self._empty_result()
        records = [self._record(account_id, grouped[account_id]) for account_id in account_ids]
        properties = assemble_property_tensor(
            records,
            self.feature_schema,
            self.numeric_stats,
            device=self.device,
        )
        edge_index, edge_type, _relation_types = self._relation_tensors(account_ids, grouped)
        with torch.no_grad():
            text_embeddings = self.encoder.encode_all([record.text for record in records], device=self.device)
            logits, low_repr, _combined, support_anchor, _property = self.model.encode_nodes(
                text_embeddings,
                properties,
                edge_index,
                edge_type,
            )
            probabilities = logits.softmax(dim=1)
            neighbors = build_support_hyperedges(support_anchor, self.support_k)
            weights = neighbor_similarities(support_anchor, neighbors)
            support = propagate_support(support_anchor, neighbors, weights)
            risk = compute_correction_risk(probabilities, neighbors, weights)
            routed = select_routed_accounts(risk, self.routing_budget)
            corrected = probabilities[:, 1].clone()
            if routed.numel():
                corrected[routed] = self.model.correction(low_repr[routed], support[routed]).softmax(dim=1)[:, 1]
        routed_set = set(routed.cpu().tolist())
        accounts = []
        for index, (account_id, record) in enumerate(zip(account_ids, records, strict=True)):
            final_probability = float(corrected[index])
            calibrated = _calibrated_probability(final_probability, self.calibration)
            accounts.append(
                {
                    "account_id": account_id,
                    "post_count": len(grouped[account_id]),
                    "base_bot_probability": round(float(probabilities[index, 1]), 6),
                    "final_bot_probability": round(final_probability, 6),
                    "calibrated_probability": round(float(calibrated), 6) if calibrated is not None else None,
                    "calibrated_bot_probability": round(float(calibrated), 6) if calibrated is not None else None,
                    "calibrated": calibrated is not None,
                    "calibration_passed": calibrated is not None,
                    "calibration_source": str(self.calibration.get("method") or "") if calibrated is not None else "",
                    "representation": [round(float(value), 8) for value in low_repr[index].detach().cpu().tolist()],
                    "badge_embedding": _badge_gradient_embedding(
                        low_repr[index],
                        self.model.base_detector.classifier,
                    ),
                    "base_prediction": "bot" if probabilities[index, 1] >= 0.5 else "human",
                    "final_prediction": "bot" if final_probability >= 0.5 else "human",
                    "confidence_deficit": round(float(1.0 - probabilities[index].max()), 6),
                    "correction_risk": round(float(risk[index]), 6),
                    "routed": index in routed_set,
                    "hyperedge": {
                        "center": account_id,
                        "support_nodes": [account_ids[int(neighbor)] for neighbor in neighbors[index].cpu().tolist()],
                        "support_k": int(neighbors[index].numel()),
                    },
                    "support_evidence": [
                        {
                            "account_id": account_ids[int(neighbor)],
                            "similarity": float(_cosine(support_anchor[index], support_anchor[int(neighbor)])),
                            "base_bot_probability": round(float(probabilities[int(neighbor), 1]), 6),
                            "final_bot_probability": round(float(corrected[int(neighbor)]), 6),
                            "routed": int(neighbor) in routed_set,
                        }
                        for neighbor in neighbors[index].cpu().tolist()
                    ],
                    "feature_coverage": _runtime_feature_coverage(record, self.feature_schema),
                }
            )
        return {
            "method": "BotRHG",
            "runtime_mode": "strict_trained_checkpoint",
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
            "graph": {
                "available": edge_index is not None and edge_index.numel() > 0,
                "edge_count": int(edge_index.shape[1]) if edge_index is not None else 0,
                "relation_types": list(self.graph_relation_types),
            },
            "model_card": {
                "system_adapter": "internal_strict_botrhg_checkpoint",
                "calibration_status": "available" if self.calibration else "unavailable",
            },
        }

    def _record(self, account_id: str, posts: list[dict[str, Any]]) -> StrictAccountRecord:
        profile = _runtime_profile(posts)
        texts = [normalize_nlpcc_text(_post_text(post)) for post in posts]
        texts = [text for text in texts if text]
        numeric = _runtime_numeric_features(posts, texts, profile, self.feature_schema.numeric_fields)
        categorical = _runtime_categorical_features(profile, self.feature_schema.categorical_fields)
        profile_parts = [
            f"Name: {profile.get('name', '')}",
            f"Screen name: {profile.get('screen_name', '')}",
            f"Created at: {profile.get('created_at', '')}",
            f"Followers count: {profile.get('followers_count', '')}",
            f"Friends count: {profile.get('friends_count', '')}",
            f"Statuses count: {profile.get('statuses_count', '')}",
            f"Listed count: {profile.get('listed_count', '')}",
            f"Verified: {profile.get('verified', '')}",
            f"Protected: {profile.get('protected', '')}",
        ]
        return StrictAccountRecord(
            account_id=account_id,
            label=0,
            text=linearize_account_text(profile_parts, str(profile.get("description") or ""), texts),
            post_count=len(posts),
            source_file_hash="runtime",
            source_encoding="utf-8",
            numeric_features=numeric,
            categorical_features=categorical,
        )

    def _relation_tensors(
        self,
        account_ids: list[str],
        grouped: dict[str, list[dict[str, Any]]],
    ) -> tuple[torch.Tensor | None, torch.Tensor | None, tuple[str, ...]]:
        allowed = set(self.graph_relation_types)
        if not allowed:
            return None, None, self.graph_relation_types
        post_owners = {
            post_id: account_id
            for account_id, rows in grouped.items()
            for post in rows
            if (post_id := _post_identifier(post))
        }
        edges: list[StrictRelationEdge] = []
        account_id_set = set(account_ids)
        for source_id, rows in grouped.items():
            for post in rows:
                if "reply" in allowed:
                    target_id = _post_value(post, "in_reply_to_user_id", "reply_to_user_id", "reply_to_author_id")
                    if target_id in account_id_set and target_id != source_id:
                        edges.append(StrictRelationEdge(source_id, target_id, "reply"))
                if "retweet" in allowed:
                    target_id = _post_value(post, "retweeted_user_id", "repost_user_id")
                    if not target_id:
                        target_id = post_owners.get(_post_value(post, "retweeted_status_id", "repost_of_id"), "")
                    if target_id in account_id_set and target_id != source_id:
                        edges.append(StrictRelationEdge(source_id, target_id, "retweet"))
        graph = StrictGraph(
            node_ids=tuple(account_ids),
            edges=tuple(edges),
            relation_types=self.graph_relation_types,
            available=bool(edges),
        )
        return assemble_relation_tensors(graph, {account_id: index for index, account_id in enumerate(account_ids)}, device=self.device)

    def _empty_result(self) -> dict[str, Any]:
        return {
            "method": "BotRHG",
            "runtime_mode": "strict_trained_checkpoint",
            "checkpoint_path": str(self.checkpoint_path),
            "accounts": [],
            "summary": {"account_count": 0, "bot_count": 0},
            "model_card": {"system_adapter": "internal_strict_botrhg_checkpoint"},
        }


def _checkpoint_feature_schema(value: Any) -> StrictFeatureSchema:
    if not isinstance(value, dict):
        raise ValueError("strict checkpoint feature_schema is missing")
    numeric_fields = tuple(str(field).strip() for field in (value.get("numeric_fields") or ()))
    categorical_fields = tuple(str(field).strip() for field in (value.get("categorical_fields") or ()))
    if (
        len(numeric_fields) != len(set(numeric_fields))
        or len(categorical_fields) != len(set(categorical_fields))
        or any(not field or field not in STRICT_NUMERIC_FIELDS for field in numeric_fields)
        or any(not field or field not in STRICT_CATEGORICAL_FIELDS for field in categorical_fields)
    ):
        raise ValueError("strict checkpoint declares unsupported account properties")
    raw_vocab = value.get("categorical_vocab") or {}
    if not isinstance(raw_vocab, dict) or any(str(field) not in categorical_fields for field in raw_vocab):
        raise ValueError("strict checkpoint categorical vocabulary is invalid")
    categorical_vocab: dict[str, tuple[str, ...]] = {}
    for field in categorical_fields:
        raw_values = raw_vocab.get(field, ())
        if not isinstance(raw_values, (list, tuple)):
            raise ValueError("strict checkpoint categorical vocabulary is invalid")
        values = tuple(str(item).strip() for item in raw_values)
        if any(not item for item in values) or len(values) != len(set(values)):
            raise ValueError("strict checkpoint categorical vocabulary is invalid")
        categorical_vocab[field] = values
    return StrictFeatureSchema(numeric_fields, categorical_fields, categorical_vocab)


def _checkpoint_numeric_stats(value: Any, schema: StrictFeatureSchema) -> dict[str, tuple[float, float]]:
    if not isinstance(value, dict):
        raise ValueError("strict checkpoint numeric_stats is missing")
    stats: dict[str, tuple[float, float]] = {}
    for field in schema.numeric_fields:
        item = value.get(field)
        if not isinstance(item, dict):
            raise ValueError(f"strict checkpoint is missing numeric stats for {field}")
        try:
            mean = float(item["mean"])
            std = float(item["std"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"strict checkpoint has invalid numeric stats for {field}") from error
        if not np.isfinite(mean) or not np.isfinite(std) or std <= 0:
            raise ValueError(f"strict checkpoint has invalid numeric stats for {field}")
        stats[field] = (mean, std)
    return stats


def _runtime_profile(posts: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "followers_count", "friends_count", "statuses_count", "favourites_count", "listed_count",
        "description", "verified", "protected", "geo_enabled", "default_profile",
        "default_profile_image", "profile_use_background_image", "lang", "time_zone", "name",
        "screen_name", "created_at",
    )
    profile: dict[str, Any] = {}
    for post in posts:
        for field in fields:
            if field in profile:
                continue
            value = _profile_value(post, field)
            if value is not None:
                profile[field] = value
    return profile


def _profile_value(post: dict[str, Any], field: str) -> Any:
    aliases = {
        "followers_count": ("followers_count", "followers", "followersCount"),
        "friends_count": ("friends_count", "friends", "following_count", "following"),
        "statuses_count": ("statuses_count", "posts_count", "tweet_count"),
        "favourites_count": ("favourites_count", "favorites_count"),
        "listed_count": ("listed_count", "lists_count"),
        "time_zone": ("time_zone", "timezone"),
    }
    names = aliases.get(field, (field,))
    for source in _profile_sources(post):
        for name in names:
            if name in source and source[name] is not None:
                return source[name]
    if field != "created_at":
        for name in names:
            if name in post and post[name] is not None:
                return post[name]
    return None


def _profile_sources(post: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for key in ("author_profile", "profile", "author", "user"):
        value = post.get(key)
        if isinstance(value, dict):
            sources.append(value)
    raw = post.get("raw_data")
    if isinstance(raw, dict):
        for key in ("author_profile", "profile", "author", "user"):
            value = raw.get(key)
            if isinstance(value, dict):
                sources.append(value)
        mblog = raw.get("mblog")
        if isinstance(mblog, dict) and isinstance(mblog.get("user"), dict):
            sources.append(mblog["user"])
        sources.append(raw)
    return sources


def _runtime_numeric_features(
    posts: list[dict[str, Any]],
    texts: list[str],
    profile: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, float]:
    derived: dict[str, float] = {
        "post_count": float(len(posts)),
        "avg_tweet_length": float(sum(map(len, texts)) / len(texts)) if texts else 0.0,
        "duplicate_ratio": float(1.0 - len(set(texts)) / len(texts)) if texts else 0.0,
        "url_rate": _marker_rate(texts, "HTTPURL"),
        "mention_rate": _marker_rate(texts, "@USER"),
        "hashtag_rate": _marker_rate(texts, "#HASHTAG"),
        "reply_rate": float(sum(bool(_post_value(post, "in_reply_to_user_id", "reply_to_user_id", "reply_to_author_id")) for post in posts) / len(posts)) if posts else 0.0,
        "retweet_rate": float(sum(bool(_post_value(post, "retweeted_status_id", "repost_of_id", "retweeted_user_id", "repost_user_id")) for post in posts) / len(posts)) if posts else 0.0,
    }
    if "description" in profile:
        derived["description_length"] = float(len(str(profile["description"]).strip()))
    if "created_at" in profile:
        observed_times = [
            timestamp
            for post in posts
            if (timestamp := parse_timestamp(_post_value(post, "timestamp", "created_at"))) is not None
        ]
        observed_at = max(observed_times, default=None)
        created_at = parse_timestamp(profile["created_at"])
        if observed_at is not None and created_at is not None:
            derived["account_age_days"] = max(0.0, (observed_at - created_at).total_seconds() / 86400.0)
    numeric: dict[str, float] = {}
    for field in fields:
        if field in derived:
            numeric[field] = derived[field]
        elif field in profile and (value := _coerce_float(profile[field])) is not None:
            numeric[field] = value
    return numeric


def _runtime_categorical_features(profile: dict[str, Any], fields: tuple[str, ...]) -> dict[str, str]:
    categorical: dict[str, str] = {}
    for field in fields:
        if field not in profile:
            continue
        if field in {"verified", "protected", "geo_enabled", "default_profile", "default_profile_image", "profile_use_background_image"}:
            categorical[field] = _coerce_bool(profile[field])
        else:
            categorical[field] = str(profile[field]).strip().lower() if field == "lang" else str(profile[field]).strip()
    return categorical


def _runtime_feature_coverage(record: StrictAccountRecord, schema: StrictFeatureSchema) -> dict[str, Any]:
    available = [
        *[field for field in schema.numeric_fields if field in record.numeric_features],
        *[field for field in schema.categorical_fields if str(record.categorical_features.get(field, "")).strip()],
    ]
    expected = [*schema.numeric_fields, *schema.categorical_fields]
    missing = [field for field in expected if field not in available]
    return {"available": available, "missing": missing, "observed_count": len(available), "total_count": len(expected)}


def _marker_rate(texts: list[str], marker: str) -> float:
    return float(sum(marker in text.upper() for text in texts) / len(texts)) if texts else 0.0


def _coerce_float(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) else None


def _coerce_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "true" if str(value).strip().lower() in {"1", "true", "yes", "y"} else "false"


def _post_text(post: dict[str, Any]) -> str:
    return str(post.get("content") or post.get("text") or "")


def _post_identifier(post: dict[str, Any]) -> str:
    return _post_value(post, "post_id", "id", "mid")


def _post_value(post: dict[str, Any], *names: str) -> str:
    for source in (post, post.get("raw_data")):
        if not isinstance(source, dict):
            continue
        for name in names:
            value = source.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
    return ""


def _cosine(left: torch.Tensor, right: torch.Tensor) -> float:
    return float(torch.nn.functional.cosine_similarity(left.unsqueeze(0), right.unsqueeze(0)).item())


def _read_json_mapping(
    path: str | Path | None,
    label: str,
    *,
    payload_bytes: bytes | None = None,
) -> dict[str, Any]:
    try:
        encoded = payload_bytes.decode("utf-8") if payload_bytes is not None else Path(path).read_text(encoding="utf-8")
        payload = json.loads(encoded)
    except (AttributeError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"bundle {label} is unreadable") from error
    if not isinstance(payload, dict):
        raise ValueError(f"bundle {label} must be an object")
    return payload


def _load_encoder_component(
    path: str | Path | None,
    source_schema: str,
    *,
    payload_bytes: bytes | None = None,
) -> Mapping[str, Any]:
    source = BytesIO(payload_bytes) if payload_bytes is not None else Path(path)
    payload = torch.load(source, map_location="cpu", weights_only=True)
    if (
        not isinstance(payload, dict)
        or payload.get("component") != "encoder"
        or payload.get("schema") != source_schema
        or not isinstance(payload.get("state_dict"), Mapping)
    ):
        raise ValueError("bundle encoder component is incompatible with the detector checkpoint")
    return payload["state_dict"]


@contextmanager
def _text_runtime_model_path(
    checkpoint: Mapping[str, Any],
    *,
    require_embedded: bool,
):
    assets = _validated_text_runtime_assets(checkpoint.get("text_runtime_assets"))
    if not assets:
        if require_embedded:
            raise ValueError("governed detector checkpoint has no verified text runtime assets")
        yield Path(str(checkpoint.get("text_model_path") or ""))
        return
    with TemporaryDirectory(prefix="cogguard-text-runtime-") as directory:
        root = Path(directory).resolve()
        for relative, payload in assets.items():
            target = root / Path(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        yield root


def _validated_text_runtime_assets(value: Any) -> dict[str, bytes]:
    if value is None:
        return {}
    if not isinstance(value, Mapping) or not value:
        raise ValueError("checkpoint text runtime assets must be a non-empty mapping")
    assets: dict[str, bytes] = {}
    total_size = 0
    for relative_value, payload in value.items():
        relative = str(relative_value)
        path = PurePosixPath(relative)
        if not relative or path.is_absolute() or ".." in path.parts or "\\" in relative:
            raise ValueError("checkpoint text runtime assets contain an unsafe path")
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("checkpoint text runtime assets must contain non-empty bytes")
        if path.name in {"model.safetensors", "pytorch_model.bin"}:
            raise ValueError("checkpoint text runtime assets must not duplicate model weights")
        total_size += len(payload)
        if total_size > 64 * 1024 * 1024:
            raise ValueError("checkpoint text runtime assets exceed the size limit")
        assets[path.as_posix()] = payload
    if "config.json" not in assets:
        raise ValueError("checkpoint text runtime assets are missing config.json")
    tokenizer_files = {"tokenizer.json", "vocab.txt", "spiece.model", "sentencepiece.bpe.model", "merges.txt"}
    if not tokenizer_files.intersection(assets):
        raise ValueError("checkpoint text runtime assets are missing tokenizer vocabulary")
    return assets


def _state_dicts_equal(left: Any, right: Any) -> bool:
    if not isinstance(left, Mapping) or not isinstance(right, Mapping) or set(left) != set(right):
        return False
    for key in left:
        left_value = left[key]
        right_value = right[key]
        if isinstance(left_value, torch.Tensor) and isinstance(right_value, torch.Tensor):
            if not torch.equal(left_value, right_value):
                return False
        elif left_value != right_value:
            return False
    return True


def _calibrated_probability(probability: float, calibration: dict[str, Any]) -> float | None:
    """Apply checkpoint calibration only when the artifact records a passed gate."""

    if not calibration or not bool(calibration.get("passed")):
        return None
    method = str(calibration.get("method") or "").strip().lower()
    if method in {"temperature_scaling", "temperature"}:
        temperature = float(calibration.get("temperature") or 1.0)
        if temperature <= 0:
            return None
        logit = torch.logit(torch.tensor(probability).clamp(1e-6, 1 - 1e-6))
        return float(torch.sigmoid(logit / temperature))
    if method in {"identity", "already_calibrated"}:
        return float(probability)
    return None


def _badge_gradient_embedding(
    representation: torch.Tensor,
    classifier: torch.nn.Linear,
) -> list[float]:
    """Return the BADGE gradient embedding for a binary classifier head."""

    with torch.no_grad():
        probabilities = classifier(representation.unsqueeze(0)).squeeze(0).softmax(dim=0)
        pseudo_label = int(torch.argmax(probabilities).item())
        one_hot = torch.zeros_like(probabilities)
        one_hot[pseudo_label] = 1.0
        gradient_factor = probabilities - one_hot
        weight_gradient = torch.outer(gradient_factor, representation)
        bias_gradient = gradient_factor
        vector = torch.cat([weight_gradient.flatten(), bias_gradient], dim=0)
    return [round(float(value), 8) for value in vector.detach().cpu().tolist()]
