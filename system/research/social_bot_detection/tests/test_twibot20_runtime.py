from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import torch

from research.social_bot_detection.twibot20_runtime import (
    TWIBOT20_DEPLOYMENT_SCOPE,
    TwiBot20ResearchRuntime,
    build_twibot20_research_bundle,
)


def _write_source_artifacts(root: Path) -> dict[str, Path]:
    root.mkdir()
    checkpoint = root / "checkpoint.pt"
    outputs = root / "outputs.pt"
    node_ids = root / "node_ids.json"
    source_manifest = root / "source_manifest.json"
    selection_metrics = root / "selection_metrics.json"
    torch.save(
        {
            "model": {"linear_out.weight": torch.ones((2, 3))},
            "model_config": {"GNN_model": "rgcn_hyperscan_dhg_nodeinput"},
            "selection_metrics": {"accuracy": 0.9, "macro_f1": 0.89},
        },
        checkpoint,
    )
    torch.save(
        {
            "prob": torch.tensor([[0.8, 0.2], [0.1, 0.9]]),
            "pred": torch.tensor([0, 1]),
            "labels": torch.tensor([[1.0, 0.0], [0.0, 1.0]]),
        },
        outputs,
    )
    node_ids.write_text(json.dumps(["u1", "u2"]), encoding="utf-8")
    source_manifest.write_text(
        json.dumps(
            {
                "backbone": "rgcn_hyperscan_dhg_nodeinput",
                "node_id_manifest": {"num_nodes": 2},
                "checkpoint_selection": {"primary": "validation_accuracy"},
                "seed": 3,
            }
        ),
        encoding="utf-8",
    )
    selection_metrics.write_text(
        json.dumps({"accuracy": 0.9, "macro_f1": 0.89, "loss": 0.2}),
        encoding="utf-8",
    )
    return {
        "checkpoint": checkpoint,
        "outputs": outputs,
        "node_ids": node_ids,
        "source_manifest": source_manifest,
        "selection_metrics": selection_metrics,
    }


def test_bundle_builds_hash_managed_transductive_runtime(tmp_path: Path) -> None:
    sources = _write_source_artifacts(tmp_path / "source")
    bundle = tmp_path / "bundle"

    manifest = build_twibot20_research_bundle(
        bundle,
        checkpoint_path=sources["checkpoint"],
        outputs_path=sources["outputs"],
        node_ids_path=sources["node_ids"],
        source_manifest_path=sources["source_manifest"],
        selection_metrics_path=sources["selection_metrics"],
    )

    assert manifest["schema"] == "cogguard.nlpcc.twibot20.transductive.v1"
    assert manifest["deployment_scope"] == TWIBOT20_DEPLOYMENT_SCOPE
    assert manifest["online_account_activation_allowed"] is False
    assert manifest["selection"]["seed"] == 3
    for name, metadata in manifest["files"].items():
        path = bundle / name
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"]


def test_runtime_queries_only_fixed_twibot20_nodes(tmp_path: Path) -> None:
    sources = _write_source_artifacts(tmp_path / "source")
    bundle = tmp_path / "bundle"
    build_twibot20_research_bundle(
        bundle,
        checkpoint_path=sources["checkpoint"],
        outputs_path=sources["outputs"],
        node_ids_path=sources["node_ids"],
        source_manifest_path=sources["source_manifest"],
        selection_metrics_path=sources["selection_metrics"],
    )

    runtime = TwiBot20ResearchRuntime(bundle)
    result = runtime.predict_nodes(["u2", "u1"])

    assert [row["node_id"] for row in result["accounts"]] == ["u2", "u1"]
    assert result["accounts"][0]["prediction"] == "bot"
    assert result["accounts"][0]["bot_probability"] == pytest.approx(0.9)
    assert result["deployment_scope"] == TWIBOT20_DEPLOYMENT_SCOPE
    with pytest.raises(KeyError, match="not part of the deployed TwiBot-20 graph"):
        runtime.predict_nodes(["new-weibo-account"])


def test_runtime_rejects_tampered_bundle(tmp_path: Path) -> None:
    sources = _write_source_artifacts(tmp_path / "source")
    bundle = tmp_path / "bundle"
    build_twibot20_research_bundle(
        bundle,
        checkpoint_path=sources["checkpoint"],
        outputs_path=sources["outputs"],
        node_ids_path=sources["node_ids"],
        source_manifest_path=sources["source_manifest"],
        selection_metrics_path=sources["selection_metrics"],
    )
    (bundle / "node_ids.json").write_text('["tampered"]', encoding="utf-8")

    with pytest.raises(ValueError, match="hash verification failed"):
        TwiBot20ResearchRuntime(bundle)


def test_online_model_bundle_rejects_twibot20_research_schema(tmp_path: Path) -> None:
    from research.social_bot_detection.model_bundle import write_account_model_bundle

    checkpoint = tmp_path / "checkpoint.pt"
    encoder = tmp_path / "encoder.pt"
    torch.save({"schema": "cogguard.nlpcc.twibot20.transductive.v1"}, checkpoint)
    torch.save({"component": "encoder"}, encoder)

    with pytest.raises(ValueError, match="unsupported detector source schema"):
        write_account_model_bundle(
            tmp_path / "online",
            encoder=encoder,
            detector=checkpoint,
            feature_schema={"schema": "fixture"},
            calibration={"status": "unavailable"},
            metrics={},
            data_fingerprints={"twibot20": "fixed-graph"},
            source_schema="cogguard.nlpcc.twibot20.transductive.v1",
        )
