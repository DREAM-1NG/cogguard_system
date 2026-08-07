from __future__ import annotations

from pathlib import Path

import torch
from torch import nn

from research.social_bot_detection import train_strict_botrhg
from research.social_bot_detection import strict_training
from research.social_bot_detection.base_detector import BaseDetector
from research.social_bot_detection.contracts import DatasetManifest, ModelConfig, TrainingConfig
from research.social_bot_detection.correction import ResidualCorrection
from research.social_bot_detection.strict_contracts import StrictAccountRecord, StrictCorpus, StrictFeatureSchema, StrictGraph, StrictRelationEdge
from research.social_bot_detection.strict_model import PropertyEncoder
from research.social_bot_detection.model_bundle import load_account_model_bundle


class DummyTextEncoder(nn.Module):
    def __init__(self, config) -> None:
        super().__init__()
        self.config = config
        self.hidden_size = 4
        self.encoder = nn.Linear(1, 1)

    def encode_all(self, texts: list[str], *, device: torch.device) -> torch.Tensor:
        if not texts:
            return torch.empty((0, self.hidden_size), dtype=torch.float32, device=device)
        rows = [
            [float(len(text)), float(text.count("bot")), float(text.count("human")), float(index % 5)]
            for index, text in enumerate(texts)
        ]
        return torch.tensor(rows, dtype=torch.float32, device=device)


class DummyGraphEncoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, num_relations: int, dropout: float) -> None:
        super().__init__()
        del num_relations, dropout
        self.proj = nn.Linear(input_dim, hidden_dim)

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor | None = None,
        edge_type: torch.Tensor | None = None,
    ) -> torch.Tensor:
        del edge_index, edge_type
        return self.proj(node_features)


class DummyStrictBotRHGModel(nn.Module):
    def __init__(
        self,
        *,
        text_dim: int,
        property_dim: int,
        graph_dim: int,
        hidden_dim: int,
        projection_dim: int,
        dropout: float,
        num_relations: int,
    ) -> None:
        super().__init__()
        self.property_encoder = PropertyEncoder(property_dim, hidden_dim, dropout)
        self.graph_encoder = DummyGraphEncoder(text_dim + hidden_dim, graph_dim, num_relations, dropout)
        self.base_detector = BaseDetector(graph_dim + text_dim + hidden_dim, hidden_dim, dropout)
        self.support_projection = nn.Linear(graph_dim + text_dim + hidden_dim, hidden_dim)
        self.correction = ResidualCorrection(hidden_dim, projection_dim, dropout)

    def encode_nodes(
        self,
        text_repr: torch.Tensor,
        property_features: torch.Tensor,
        edge_index: torch.Tensor | None = None,
        edge_type: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        property_repr = self.property_encoder(property_features)
        node_features = torch.cat([text_repr, property_repr], dim=1)
        graph_repr = self.graph_encoder(node_features, edge_index, edge_type)
        combined = torch.cat([graph_repr, node_features], dim=1)
        support_anchor = self.support_projection(combined)
        logits, low_order_repr = self.base_detector(combined)
        return logits, low_order_repr, combined, support_anchor, property_repr


def test_strict_package_exports_training_api():
    assert train_strict_botrhg is strict_training.train_strict_botrhg


def test_strict_training_runs_with_dataset_specific_corpus(monkeypatch, tmp_path):
    corpus = _make_corpus()
    monkeypatch.setattr(strict_training, "load_strict_social_corpus", lambda dataset_name, dataset_root, max_posts_per_account: corpus)
    monkeypatch.setattr(strict_training, "TextEncoder", DummyTextEncoder)
    monkeypatch.setattr(strict_training, "StrictBotRHGModel", DummyStrictBotRHGModel)
    monkeypatch.setattr(strict_training, "evaluate_text_baseline", lambda train_samples, evaluation_samples: {"description": "stub", "train_size": len(train_samples), "test_size": len(evaluation_samples)})

    config = TrainingConfig(
        seed=3,
        base_epochs=1,
        correction_epochs=1,
        device="cpu",
        dataset_name="cresci_2015",
        model=ModelConfig(
            text_model_path="fixture",
            hidden_dim=4,
            projection_dim=3,
            dropout=0.0,
            max_length=32,
            batch_size=4,
            max_chunks_per_account=2,
            encoder_trainable=False,
            support_k=2,
            routing_budget=0.25,
            correction_weight=1.0,
            max_posts_per_account=4,
        ),
    )

    report = strict_training.train_strict_botrhg(tmp_path / "dataset", tmp_path / "output", dataset_name="cresci_2015", config=config)

    assert report["method"] == "BotRHG"
    assert report["dataset"]["dataset_name"] == "cresci_2015"
    assert report["routed_count"] >= 0
    assert "train_base" in report["metrics"]
    assert any(key.endswith("_corrected") for key in report["metrics"])

    checkpoint_path = Path(report["artifact_paths"]["checkpoint_path"])
    assert checkpoint_path.exists()
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    assert payload["schema"] == "cogguard.botrhg.strict.v1"
    assert payload["strict_method"] is True
    assert payload["text_encoder_finetuned"] is False
    assert payload["graph_available"] is True
    assert payload["base_config"]["input_dim"] > payload["text_hidden_size"]
    bundle_manifest = load_account_model_bundle(report["artifact_paths"]["model_bundle_manifest_path"])
    assert bundle_manifest["source_schema"] == "cogguard.botrhg.strict.v1"
    assert bundle_manifest["deployment"] == {"eligible": False, "status": "legacy_non_deployable"}


def _make_corpus() -> StrictCorpus:
    records: list[StrictAccountRecord] = []
    edges: list[StrictRelationEdge] = []
    for index in range(12):
        label = index % 2
        source_label = "human" if label == 0 else "bot"
        account_id = f"strict:{source_label}:{index}"
        text = f"{'human' if label == 0 else 'bot'} account {index} profile text with shared url HTTPURL @USER"
        records.append(
            StrictAccountRecord(
                account_id=account_id,
                label=label,
                text=text,
                post_count=3 + index % 3,
                source_file_hash=f"hash-{index}",
                source_encoding="utf-8",
                dataset_name="cresci_2015",
                source_label=source_label,
                metadata={"raw_account_id": str(index)},
                split_group=source_label,
                numeric_features=_numeric_features(index, label),
                categorical_features=_categorical_features(source_label),
            )
        )
    for index, record in enumerate(records):
        next_record = records[(index + 1) % len(records)]
        edges.append(
            StrictRelationEdge(
                source_account_id=record.account_id,
                target_account_id=next_record.account_id,
                relation_type="reply" if index % 2 == 0 else "retweet",
            )
        )
    graph = StrictGraph(node_ids=tuple(record.account_id for record in records), edges=tuple(edges), relation_types=("reply", "retweet"), available=True)
    manifest = DatasetManifest(
        source_root="fixture",
        label_file="fixture/cresci-2015.csv.tar.gz",
        text_directory="embedded archive members",
        data_fingerprint="strict-fixture-fingerprint",
        labeled_account_count=len(records),
        usable_account_count=len(records),
        skipped_empty_text_count=0,
        missing_text_count=0,
        class_counts={"0": 6, "1": 6},
        property_field_coverage={},
        social_graph_coverage="available: synthetic reply/retweet graph",
        dataset_name="cresci_2015",
        label_provenance="fixture",
        text_provenance="fixture",
        source_archive_sha256="fixture",
    )
    return StrictCorpus(records=records, graph=graph, manifest=manifest)


def _numeric_features(index: int, label: int) -> dict[str, float]:
    return {
        "followers_count": float(100 + index),
        "friends_count": float(80 + index),
        "statuses_count": float(20 + index),
        "favourites_count": float(index % 5),
        "listed_count": float(index % 3),
        "post_count": float(3 + index % 3),
        "description_length": float(24 + index),
        "avg_tweet_length": float(40 + index),
        "duplicate_ratio": float(index % 4) / 10.0,
        "url_rate": 0.1 * label,
        "mention_rate": 0.2,
        "hashtag_rate": 0.3,
        "reply_rate": 0.4 if label == 0 else 0.1,
        "retweet_rate": 0.5 if label == 1 else 0.1,
        "account_age_days": float(365 + index),
    }


def _categorical_features(source_label: str) -> dict[str, str]:
    return {
        "verified": "true" if source_label == "human" else "false",
        "protected": "false",
        "geo_enabled": "false",
        "default_profile": "true",
        "default_profile_image": "false",
        "profile_use_background_image": "false",
        "lang": "zh",
        "time_zone": "Asia/Shanghai",
        "source_label": source_label,
    }
