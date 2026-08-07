from __future__ import annotations

import torch

from research.social_bot_detection.strict_contracts import StrictAccountRecord, StrictFeatureSchema
from research.social_bot_detection.strict_features import (
    STRICT_CATEGORICAL_FIELDS,
    assemble_property_tensor,
    build_feature_schema,
    derive_numeric_stats,
)


def test_feature_schema_uses_explicit_allowlist_and_excludes_dataset_label_proxies():
    record = StrictAccountRecord(
        account_id="account-1",
        label=1,
        text="fixture",
        post_count=1,
        source_file_hash="hash",
        source_encoding="utf-8",
        source_label="known-bot-source",
        split_group="known-bot-source",
        numeric_features={"followers_count": 10.0, "label_score": 1.0},
        categorical_features={
            "verified": "false",
            "lang": "en",
            "source_label": "known-bot-source",
            "dataset_label": "bot",
            "arbitrary_column": "must-not-enter-model",
        },
    )

    schema = build_feature_schema([record])
    tensor = assemble_property_tensor(
        [record],
        schema,
        derive_numeric_stats([record], schema),
        device=torch.device("cpu"),
    )

    assert "source_label" not in STRICT_CATEGORICAL_FIELDS
    assert schema.categorical_fields == STRICT_CATEGORICAL_FIELDS
    assert "source_label" not in schema.categorical_vocab
    assert "dataset_label" not in schema.categorical_vocab
    assert tensor.shape[1] == len(schema.numeric_fields) + sum(
        len(schema.categorical_vocab[field]) + 1 for field in schema.categorical_fields
    )


def test_assemble_property_tensor_never_encodes_source_label_from_a_supplied_schema():
    record = StrictAccountRecord(
        account_id="account-1",
        label=1,
        text="fixture",
        post_count=1,
        source_file_hash="hash",
        source_encoding="utf-8",
        categorical_features={"source_label": "bot-source", "verified": "false"},
    )
    schema = StrictFeatureSchema(
        numeric_fields=(),
        categorical_fields=("source_label", "verified"),
        categorical_vocab={"source_label": ("bot-source",), "verified": ("false",)},
    )

    tensor = assemble_property_tensor(
        [record],
        schema,
        {},
        device=torch.device("cpu"),
    )

    assert tensor.shape[1] == 2
