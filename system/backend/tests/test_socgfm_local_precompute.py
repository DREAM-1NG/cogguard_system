from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from app.config import PROJECT_ROOT
from app.core.analysis.coordination_runtime.socgfm_artifact_builder import (
    build_socgfm_detection_artifact,
)
from app.core.analysis.coordination_runtime.socgfm_local_precompute import (
    discover_china_checkpoint_paths,
    hash_checkpoint_files,
    load_socgfm_local_events,
    precompute_socgfm_china_local_detection,
    prepare_socgfm_local_graph_inputs,
)


def _write_checkpoint_fixture(root: Path) -> Path:
    checkpoint_root = root / "china" / "sandbox" / "data" / "processed" / "china" / "best_models_f1_macro"
    checkpoint_root.mkdir(parents=True)
    for index in range(5):
        (checkpoint_root / f"model{index}.pth").write_bytes(f"checkpoint-{index}".encode("utf-8"))
    return root / "china"


def _write_event_table(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "platform,account_id,relation,object_id,timestamp,content_id,content",
                "weibo,u1,url_share,https://example.test/a,2026-05-21T10:00:00+00:00,p1,共同转发同一链接",
                "xiaohongshu,u2,url_share,https://example.test/a,2026-05-21T10:01:00+00:00,p2,共同转发同一链接",
                "weibo,u3,reply_target,post:77,2026-05-21T10:02:00+00:00,p3,",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _fake_text_encoder(texts: list[str]) -> np.ndarray:
    rows = []
    for index, text in enumerate(texts):
        value = (index + 1) / 100.0
        if text.strip():
            rows.append(np.full(768, value, dtype=np.float32))
        else:
            rows.append(np.zeros(768, dtype=np.float32))
    return np.vstack(rows)


def _fake_inference_runner(inputs, checkpoint_paths, *, device: str):
    assert len(checkpoint_paths) == 5
    assert inputs.text_features.shape[1] == 768
    assert inputs.struct_features.shape[1] == 128
    assert inputs.edge_index.shape[0] == 2
    base = np.linspace(0.25, 0.85, num=len(inputs.account_keys), dtype=np.float32)
    return [base + (index * 0.01) for index, _path in enumerate(checkpoint_paths)]


def test_china_checkpoint_discovery_requires_exactly_five_models(tmp_path: Path):
    root = _write_checkpoint_fixture(tmp_path)

    checkpoint_paths = discover_china_checkpoint_paths(root)
    checkpoint_hashes = hash_checkpoint_files(checkpoint_paths)

    assert [path.name for path in checkpoint_paths] == [f"model{index}.pth" for index in range(5)]
    assert set(checkpoint_hashes) == {f"model{index}.pth" for index in range(5)}
    assert all(value.startswith("sha256:") for value in checkpoint_hashes.values())


def test_local_event_table_adapter_builds_stable_account_mapping_and_features(tmp_path: Path):
    event_path = _write_event_table(tmp_path / "events.csv")

    events = load_socgfm_local_events(event_table=event_path)
    prepared = prepare_socgfm_local_graph_inputs(events, text_encoder=_fake_text_encoder)

    assert prepared.account_keys == ("weibo:u1", "weibo:u3", "xiaohongshu:u2")
    assert prepared.node_mapping == {"weibo:u1": 0, "weibo:u3": 1, "xiaohongshu:u2": 2}
    assert prepared.text_features.shape == (3, 768)
    assert prepared.struct_features.shape == (3, 128)
    assert prepared.feature_audit["missing_text_account_count"] == 1
    assert prepared.feature_audit["isolated_node_repair_count"] >= 0


def test_snapshot_json_adapter_uses_platform_scoped_account_keys(tmp_path: Path):
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "posts": [
                    {
                        "platform": "weibo",
                        "author_id": "u1",
                        "post_id": "p1",
                        "content": "微博正文",
                        "url": "https://example.test/a",
                        "created_at": "2026-05-21T10:00:00+00:00",
                    }
                ],
                "comments": [
                    {
                        "platform": "douyin",
                        "account_id": "u1",
                        "comment_id": "c1",
                        "content": "抖音评论",
                        "target_id": "video:1",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    events = load_socgfm_local_events(snapshot_json=snapshot_path)
    prepared = prepare_socgfm_local_graph_inputs(events, text_encoder=_fake_text_encoder)

    assert prepared.account_keys == ("douyin:u1", "weibo:u1")
    assert set(events["platform"].astype(str)) == {"weibo", "douyin"}


def test_precompute_writes_predictions_consumable_by_artifact_builder(tmp_path: Path):
    checkpoint_root = _write_checkpoint_fixture(tmp_path / "checkpoints")
    event_path = _write_event_table(tmp_path / "events.csv")
    output_dir = (
        PROJECT_ROOT
        / "output"
        / "pytest-socgfm-china-local-precompute"
        / hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
    )

    summary = precompute_socgfm_china_local_detection(
        event_table=event_path,
        output_dir=output_dir,
        checkpoint_root=checkpoint_root,
        text_encoder=_fake_text_encoder,
        inference_runner=_fake_inference_runner,
        device="cpu",
        dataset_id="pytest-local",
    )

    predictions = list(csv.DictReader((output_dir / "predictions.csv").open(encoding="utf-8")))
    node_mapping = list(csv.DictReader((output_dir / "node_mapping.csv").open(encoding="utf-8")))
    manifest = json.loads((output_dir / "prediction_manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((output_dir / "feature_audit.json").read_text(encoding="utf-8"))

    assert summary["prediction_count"] == 3
    assert predictions[0]["account_key"] == "xiaohongshu:u2"
    assert set(predictions[0]) >= {"platform", "account_id", "account_key", "node_score", "predicted_label"}
    assert [row["node_id"] for row in node_mapping] == ["0", "1", "2"]
    assert manifest["checkpoint_family"] == "official_china_socgfm_cross_attention_sage"
    assert manifest["online_neural_forward"] is False
    assert manifest["neural_forward_executed_offline"] is True
    assert manifest["claim_scope"] == "account_level_io_membership_to_cluster_proxy"
    assert audit["text_feature_source"].startswith("sbert:")

    artifact_dir = output_dir / "deployable_artifact"
    artifact = build_socgfm_detection_artifact(
        source_run_dir=output_dir,
        output_dir=artifact_dir,
        version="china-local-precomputed-pytest",
        account_namespace="local",
    )
    assert artifact["account_probability_count"] == 3


def test_precompute_rejects_non_g_drive_output(tmp_path: Path):
    checkpoint_root = _write_checkpoint_fixture(tmp_path / "checkpoints")
    event_path = _write_event_table(tmp_path / "events.csv")

    with pytest.raises(ValueError, match="G: drive"):
        precompute_socgfm_china_local_detection(
            event_table=event_path,
            output_dir=Path("C:/socgfm-local-precompute"),
            checkpoint_root=checkpoint_root,
            text_encoder=_fake_text_encoder,
            inference_runner=_fake_inference_runner,
            device="cpu",
        )
