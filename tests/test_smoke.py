import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from propagation.analysis import analyze_events
from propagation.analysis import role_evidence_table
from propagation.loaders import load_dataset, make_synthetic_events
from propagation.prediction import run_prediction
from propagation.protocol import CoordinationScope, export_standard_cascades, load_coordination_scope
from propagation.reporting import build_final_report
from propagation.visualization import build_dashboard
from benchmark.adapters.cascade_io import forest_to_casft_dataset, load_forest_split
from benchmark.adapters.propagation_protocol import UNK_USER_ID
from benchmark.adapters.hyperidp_protocol_proxy import candidate_rows, parse_cascade, prefix_features, train_statistics
from benchmark.adapters.kt2_joint_model import (
    forest_policy_gradient_loss,
    run_kt2_joint_model,
    support_log_bounds,
    trend_target,
    trend_time_grid,
)
from benchmark.adapters.kt2_sequence_joint_model import (
    build_sequence_training_examples,
    stable_user_bucket,
    run_kt2_sequence_joint_model,
)
import benchmark.adapters.lgb_bot_detection as lgb_bot_detection_module
from benchmark.adapters.lgb_bot_detection import (
    audit_lgb_reproduction_status,
    build_unified_user_text,
    convert_lgb_official_dataset,
    export_lgb_lm_sft_features,
    generate_lgb_data_request_package,
    inspect_lgb_official_data_readiness,
    load_lgb_dataset,
    load_lgb_text_features,
    run_lgb_ablation_suite,
    run_lgb_strict_reproduction_gate,
    run_lgb_strict_reproduction_pipeline,
    run_lgb_multiseed,
    run_lgb_reproduction,
    write_lgb_strict_gate_report,
)
from benchmark.completion_gate import run_completion_gate
from benchmark.experiment_audit import build_audit, write_audit
from benchmark.kt1_coordination_adapter import convert_kt1_predictions, run_kt1_role_evidence_validation, run_pheme_role_evidence_sample
from benchmark.kt2_baseline_comparison import build_report as build_baseline_comparison
import benchmark.kt2_minds_comparison as kt2_minds_comparison
from benchmark.kt2_original_fusion_ablation import REQUIRED_VARIANTS as ORIGINAL_FUSION_ABLATION_VARIANTS
from benchmark.kt2_original_fusion_ablation import run_ablation as run_original_fusion_ablation
import benchmark.kt2_original_fusion_experiment as original_fusion_experiment
import benchmark.same_protocol_full_run_baselines as same_protocol_baselines
from benchmark.kt2_original_fusion_gate import build_gate as build_original_fusion_gate
from benchmark.kt2_original_fusion_experiment import (
    load_existing_rows,
    matrix_coverage,
    normalize_row_identity,
    original_alignment_failures,
    original_subpath_audit,
    original_subpath_failures,
)
from benchmark.macro_micro import build_macro_micro_framework_summary, macro_micro_result_rows
from benchmark.role_evidence_review import generate_review_template, init_review_file, review_status, validate_review_file
from benchmark.run_benchmark import _forest_data_dir, _minds_work_dir, external_reproduction_status, run_casft_frontier, run_temporal_graph_frontier
from benchmark.same_protocol_full_run_template import write_template as write_full_run_template
from benchmark.schema import validate_benchmark_results


def test_smoke_pipeline():
    events = make_synthetic_events()
    with tempfile.TemporaryDirectory() as tmp:
        summary = analyze_events(events, tmp)
        report = run_prediction(events, tmp, 0.3, dataset="synthetic_demo")
        dashboard = build_dashboard(events, tmp, report)
        dashboard_text = Path(dashboard).read_text(encoding="utf-8")
        prediction_json = json.loads((Path(tmp) / "prediction_report.json").read_text(encoding="utf-8"))
    assert summary["dataset_events"] == len(events)
    assert report["size_prediction"]["status"] == "ok"
    assert prediction_json["schema"] == "cogguard.kt2.prediction_report.v1"
    assert prediction_json["dataset"] == "synthetic_demo"
    assert prediction_json["t_obs"] == 0.3
    assert prediction_json["size_prediction"]["model_name"] == "RandomForestRegressor"
    assert prediction_json["path_prediction"]["reproduction_level"] == "local_baseline"
    assert prediction_json["macro_micro_framework"]["schema"] == "cogguard.kt2.macro_micro_framework.v1"
    assert prediction_json["macro_micro_framework"]["reproduction_level"] == "local_baseline"
    assert Path(dashboard).name == "dashboard.html"
    assert "实验预测" in dashboard_text
    assert "Macro/Micro 统一框架审计" in dashboard_text
    assert "macro_micro_consistency" in dashboard_text
    assert "synthetic_demo" in dashboard_text
    assert "t_obs/observation_ratio" in dashboard_text
    assert "reproduction_level" in dashboard_text
    assert "uncertainty/error_note" in dashboard_text


def test_lgb_unified_text_and_smoke_training_schema():
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_lgb_fixture(Path(tmp))
        text = build_unified_user_text(
            {
                "name": "demo",
                "description": "hello @someone https://example.com #topic",
                "followers_count": 3,
                "friends_count": 2,
                "label": "bot",
            },
            ["visit https://example.com @abc #tag"],
        )
        assert "User profile:" in text
        assert "Description:" in text
        assert "Tweet:" in text
        assert "HTTPURL" in text
        assert "@USER" in text
        assert "#HASHTAG" in text
        dataset = load_lgb_dataset(root, seed=7)
        assert len(dataset.node_ids) == 12
        assert len(dataset.edges) >= 8
        result = run_lgb_reproduction(
            root,
            dataset="synthetic_lgb",
            seed=7,
            text_dim=32,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
        )
    schema = validate_benchmark_results([result])
    assert result["schema"] == "cogguard.kt2.lgb_bot_detection.v1"
    assert result["task"] == "bot_detection"
    assert result["status"] == "ok"
    assert result["training_protocol"]["stages"] == [
        "LM supervised fine-tuning",
        "GNN graph contrastive pre-training",
        "GNN fine-tuning with concat fusion",
    ]
    assert result["training_protocol"]["full_reproduction_required_datasets"] == ["TwiBot-22", "TwiBot-20"]
    assert 0.0 <= result["accuracy"] <= 1.0
    assert 0.0 <= result["f1"] <= 1.0
    assert schema["ok"], schema


def test_lgb_loader_and_training_keep_unlabeled_graph_context_for_gcl_only():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        nodes = [
            {"id": "u1", "label": "human", "name": "human", "description": "ordinary user", "tweets": ["hello"]},
            {"id": "u2", "label": "bot", "name": "bot", "description": "automated user", "tweets": ["promo"]},
            {"id": "u3", "name": "support", "description": "unlabeled graph context", "tweets": ["context"]},
        ]
        (root / "nodes.jsonl").write_text("\n".join(json.dumps(row) for row in nodes), encoding="utf-8")
        (root / "edges.csv").write_text("source,target\nu1,u3\nu3,u2\n", encoding="utf-8")
        (root / "split.csv").write_text("id,split\nu1,train\nu2,test\n", encoding="utf-8")

        dataset = load_lgb_dataset(root, seed=9)
        result = run_lgb_reproduction(
            root,
            dataset="synthetic_lgb_unlabeled_context",
            seed=9,
            text_dim=16,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
        )

    assert dataset.node_ids == ["u1", "u2", "u3"]
    assert dataset.labels.tolist() == [0, 1, -1]
    assert dataset.labeled_idx.tolist() == [0, 1]
    assert dataset.unlabeled_idx.tolist() == [2]
    assert dataset.edges == [(0, 2), (2, 1)]
    assert result["status"] == "ok"
    assert result["node_count"] == 3
    assert result["labeled_count"] == 2
    assert result["unlabeled_context_count"] == 1
    assert result["training_protocol"]["unlabeled_context_usage"] == "GCL graph context only; excluded from supervised LM/GNN losses and metrics"


def test_lgb_uses_paper_gcl_defaults_for_twibot22_and_twibot20():
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_lgb_fixture(Path(tmp))
        twibot22 = run_lgb_reproduction(
            root,
            dataset="TwiBot-22",
            seed=7,
            text_dim=16,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
        )
        twibot20 = run_lgb_reproduction(
            root,
            dataset="TwiBot-20",
            seed=7,
            text_dim=16,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
        )

    assert twibot22["training_protocol"]["gcl_temperature"] == 0.4
    assert twibot22["training_protocol"]["edge_dropout_views"] == [0.2, 0.4]
    assert twibot20["training_protocol"]["gcl_temperature"] == 0.4
    assert twibot20["training_protocol"]["edge_dropout_views"] == [0.4, 0.6]


def test_lgb_gnn_variants_have_distinct_executable_paths():
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_lgb_fixture(Path(tmp))
        results = {}
        for variant in ("GCN", "GIN", "GAT"):
            results[variant] = run_lgb_reproduction(
                root,
                dataset="TwiBot-22",
                seed=7,
                text_dim=16,
                hidden_dim=8,
                epochs_lm=1,
                epochs_gcl=1,
                epochs_finetune=1,
                device="cpu",
                gnn_variant=variant,
            )

    assert {row["gnn_variant"] for row in results.values()} == {"GCN", "GIN", "GAT"}
    assert results["GCN"]["training_protocol"]["gnn"] == "LGB(GCN)"
    assert results["GIN"]["training_protocol"]["gnn"] == "LGB(GIN)"
    assert results["GAT"]["training_protocol"]["gnn"] == "LGB(GAT)"
    assert len({results[variant]["training_protocol"]["gnn_operator"] for variant in results}) == 3
    for result in results.values():
        assert result["status"] == "ok"
        assert 0.0 <= result["accuracy"] <= 1.0


def test_lgb_uses_external_lm_feature_file_and_records_encoder_protocol():
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_lgb_fixture(Path(tmp))
        dataset = load_lgb_dataset(root, seed=7)
        features_path = root / "lm_features.jsonl"
        rows = []
        for idx, node_id in enumerate(dataset.node_ids):
            rows.append({"id": node_id, "embedding": [float(idx), float(idx + 1), float(idx % 3)]})
        features_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

        features = load_lgb_text_features(features_path, dataset.node_ids)
        result = run_lgb_reproduction(
            root,
            dataset="synthetic_lgb_lm_features",
            seed=7,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
            text_features_path=str(features_path),
            text_encoder="roberta_sft_features",
            reproduction_level="frontier_reproduction_small_run",
        )

    schema = validate_benchmark_results([result])
    assert features.shape == (12, 3)
    assert result["status"] == "ok"
    assert result["training_protocol"]["text_encoder"] == "roberta_sft_features"
    assert result["training_protocol"]["text_features_source"] == str(features_path)
    assert result["text_feature_dim"] == 3
    assert schema["ok"], schema


def test_lgb_lm_sft_feature_exporter_writes_aligned_embeddings_and_report():
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_lgb_fixture(Path(tmp))
        out_dir = Path(tmp) / "lm_sft"
        report = export_lgb_lm_sft_features(
            root,
            out_dir,
            encoder_backend="lightweight_hashing_sft",
            model_name="unit-lightweight-roberta-proxy",
            feature_dim=16,
            epochs=1,
            seed=17,
            device="cpu",
        )
        dataset = load_lgb_dataset(root, seed=17)
        features = load_lgb_text_features(out_dir / "lm_features.jsonl", dataset.node_ids)
        written_report = json.loads((out_dir / "lm_sft_report.json").read_text(encoding="utf-8"))

    assert report["schema"] == "cogguard.kt2.lgb_lm_sft_features.v1"
    assert report["status"] == "ok"
    assert report["encoder_backend"] == "lightweight_hashing_sft"
    assert report["model_name"] == "unit-lightweight-roberta-proxy"
    assert report["feature_file"].endswith("lm_features.jsonl")
    assert report["feature_dim"] == 16
    assert report["node_count"] == 12
    assert report["strict_lgb_text_encoder"] is False
    assert "RoBERTa/T5" in report["strict_reproduction_note"]
    assert features.shape == (12, 16)
    assert written_report == report


def test_lgb_multiseed_summary_reports_mean_std_and_required_protocol():
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_lgb_fixture(Path(tmp))
        summary = run_lgb_multiseed(
            root,
            dataset="synthetic_lgb_multiseed",
            seeds=[3, 5],
            text_dim=32,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
        )

    assert summary["schema"] == "cogguard.kt2.lgb_multiseed_summary.v1"
    assert summary["task"] == "bot_detection"
    assert summary["num_runs"] == 2
    assert summary["seeds"] == [3, 5]
    assert summary["gnn_variant"] == "GCN"
    assert summary["paper_target"]["table"] == "Table II"
    assert summary["paper_target"]["model"] == "LGB(GCN)"
    assert set(summary["metrics_mean_std"]) == {"accuracy", "f1", "roc_auc"}
    for metric, stats in summary["metrics_mean_std"].items():
        assert "mean" in stats
        assert "std" in stats
        if stats["mean"] is not None:
            assert 0.0 <= stats["mean"] <= 1.0
    assert summary["required_paper_runs"] == 5
    assert summary["meets_paper_seed_count"] is False


def test_lgb_multiseed_and_ablation_can_write_gate_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_lgb_fixture(Path(tmp))
        out_dir = Path(tmp) / "artifacts" / "TwiBot-22"
        multiseed_path = out_dir / "lgb_multiseed_summary.json"
        ablation_path = out_dir / "lgb_ablation_suite.json"
        multiseed = run_lgb_multiseed(
            root,
            dataset="synthetic_lgb_artifact",
            seeds=[3, 5],
            text_dim=32,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
            output_path=multiseed_path,
        )
        ablation = run_lgb_ablation_suite(
            root,
            dataset="synthetic_lgb_artifact",
            seeds=[3],
            variants=["full", "lm_only"],
            text_dim=32,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
            output_path=ablation_path,
        )
        assert multiseed_path.is_file()
        assert ablation_path.is_file()
        loaded_multiseed = json.loads(multiseed_path.read_text(encoding="utf-8"))
        loaded_ablation = json.loads(ablation_path.read_text(encoding="utf-8"))

    assert loaded_multiseed == multiseed
    assert loaded_ablation == ablation
    assert loaded_multiseed["schema"] == "cogguard.kt2.lgb_multiseed_summary.v1"
    assert loaded_ablation["schema"] == "cogguard.kt2.lgb_ablation_suite.v1"
    assert loaded_multiseed["run_metadata"]["artifact_type"] == "lgb_multiseed_summary"
    assert loaded_multiseed["run_metadata"]["data_dir"] == str(root)
    assert loaded_multiseed["run_metadata"]["command_or_entrypoint"]
    assert loaded_ablation["run_metadata"]["artifact_type"] == "lgb_ablation_suite"
    assert loaded_ablation["run_metadata"]["data_dir"] == str(root)
    assert loaded_ablation["run_metadata"]["command_or_entrypoint"]


def test_lgb_ablation_suite_reports_table3_variants_without_claiming_full_reproduction():
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_lgb_fixture(Path(tmp))
        summary = run_lgb_ablation_suite(
            root,
            dataset="synthetic_lgb_ablation",
            seeds=[11],
            variants=["full", "wo_lm_sft", "wo_gnn_pretraining", "wo_concat", "lm_only"],
            text_dim=32,
            hidden_dim=8,
            epochs_lm=1,
            epochs_gcl=1,
            epochs_finetune=1,
            device="cpu",
        )

    assert summary["schema"] == "cogguard.kt2.lgb_ablation_suite.v1"
    assert summary["task"] == "bot_detection"
    assert summary["dataset"] == "synthetic_lgb_ablation"
    assert summary["required_table3_variants"] == [
        "full",
        "wo_lm_sft",
        "wo_gnn_finetuning",
        "wo_gnn_pretraining",
        "wo_concat",
        "average_fusion",
        "max_fusion",
        "lm_only",
    ]
    assert summary["completed_variants"] == ["full", "wo_lm_sft", "wo_gnn_pretraining", "wo_concat", "lm_only"]
    assert summary["table3_complete"] is False
    for variant in summary["variants"]:
        assert variant["variant"] in summary["completed_variants"]
        assert variant["summary"]["num_runs"] == 1
        assert variant["summary"]["status"] == "ok"
        assert variant["summary"]["runs"][0]["ablation_variant"] == variant["variant"]


def test_lgb_strict_reproduction_gate_requires_two_datasets_sft_five_seeds_and_table3():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)

        passed = run_lgb_strict_reproduction_gate(root)
        incomplete_root = root / "incomplete"
        (incomplete_root / "TwiBot-22").mkdir(parents=True)
        _write_lgb_gate_artifacts(incomplete_root / "TwiBot-22", "TwiBot-22", complete=False)
        failed = run_lgb_strict_reproduction_gate(incomplete_root)
        no_context_root = root / "no_context"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = no_context_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True, include_context=False)
        no_context = run_lgb_strict_reproduction_gate(no_context_root)
        bad_gcl_root = root / "bad_gcl"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = bad_gcl_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True, bad_gcl=True)
        bad_gcl = run_lgb_strict_reproduction_gate(bad_gcl_root)
        missing_metadata_root = root / "missing_metadata"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = missing_metadata_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            for name in ("lgb_multiseed_summary.json", "lgb_ablation_suite.json"):
                path = artifact_dir / name
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload.pop("run_metadata", None)
                path.write_text(json.dumps(payload), encoding="utf-8")
        missing_metadata = run_lgb_strict_reproduction_gate(missing_metadata_root)
        missing_paper_target_root = root / "missing_paper_target"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = missing_paper_target_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "lgb_multiseed_summary.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("paper_target", None)
            path.write_text(json.dumps(payload), encoding="utf-8")
        missing_paper_target = run_lgb_strict_reproduction_gate(missing_paper_target_root)
        missing_gnn_variant_root = root / "missing_gnn_variant"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = missing_gnn_variant_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "lgb_multiseed_summary.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("gnn_variant", None)
            path.write_text(json.dumps(payload), encoding="utf-8")
        missing_gnn_variant = run_lgb_strict_reproduction_gate(missing_gnn_variant_root)
        mismatched_run_protocol_root = root / "mismatched_run_protocol"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = mismatched_run_protocol_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "lgb_multiseed_summary.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runs"][0]["training_protocol"]["gnn"] = "LGB(GAT)"
            path.write_text(json.dumps(payload), encoding="utf-8")
        mismatched_run_protocol = run_lgb_strict_reproduction_gate(mismatched_run_protocol_root)
        proxy_ablation_protocol_root = root / "proxy_ablation_protocol"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = proxy_ablation_protocol_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "lgb_ablation_suite.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["variants"][0]["summary"]["runs"][0]["training_protocol"]["text_encoder"] = "HashingVectorizer local proxy"
            path.write_text(json.dumps(payload), encoding="utf-8")
        proxy_ablation_protocol = run_lgb_strict_reproduction_gate(proxy_ablation_protocol_root)
        small_conversion_root = root / "small_conversion"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = small_conversion_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "conversion_summary.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["node_count"] = 100
            payload["labeled_nodes"] = 100
            payload["label_counts"] = {"human": 50, "bot": 50}
            payload["split_counts"] = {"train": 70, "valid": 20, "test": 10}
            path.write_text(json.dumps(payload), encoding="utf-8")
        small_conversion = run_lgb_strict_reproduction_gate(small_conversion_root)
        mismatched_lm_count_root = root / "mismatched_lm_count"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = mismatched_lm_count_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "lm_sft_report.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["node_count"] = 12
            path.write_text(json.dumps(payload), encoding="utf-8")
        mismatched_lm_count = run_lgb_strict_reproduction_gate(mismatched_lm_count_root)
        mismatched_feature_source_root = root / "mismatched_feature_source"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = mismatched_feature_source_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "lgb_multiseed_summary.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runs"][0]["training_protocol"]["text_features_source"] = str(artifact_dir / "other_features.jsonl")
            path.write_text(json.dumps(payload), encoding="utf-8")
        mismatched_feature_source = run_lgb_strict_reproduction_gate(mismatched_feature_source_root)
        weak_reproduction_level_root = root / "weak_reproduction_level"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = weak_reproduction_level_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            for name in ("lgb_multiseed_summary.json", "lgb_ablation_suite.json"):
                path = artifact_dir / name
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["reproduction_level"] = "public_code_adapter"
                payload["run_metadata"]["reproduction_level"] = "public_code_adapter"
                path.write_text(json.dumps(payload), encoding="utf-8")
        weak_reproduction_level = run_lgb_strict_reproduction_gate(weak_reproduction_level_root)
        missing_run_metric_root = root / "missing_run_metric"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = missing_run_metric_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "lgb_multiseed_summary.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runs"][0].pop("roc_auc", None)
            path.write_text(json.dumps(payload), encoding="utf-8")
        missing_run_metric = run_lgb_strict_reproduction_gate(missing_run_metric_root)
        incomplete_ablation_seed_root = root / "incomplete_ablation_seed"
        for dataset in ("TwiBot-22", "TwiBot-20"):
            artifact_dir = incomplete_ablation_seed_root / dataset
            artifact_dir.mkdir(parents=True)
            _write_lgb_gate_artifacts(artifact_dir, dataset, complete=True)
            path = artifact_dir / "lgb_ablation_suite.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["variants"][0]["summary"]["num_runs"] = 1
            payload["variants"][0]["summary"]["seeds"] = [42]
            payload["variants"][0]["summary"]["runs"] = payload["variants"][0]["summary"]["runs"][:1]
            path.write_text(json.dumps(payload), encoding="utf-8")
        incomplete_ablation_seed = run_lgb_strict_reproduction_gate(incomplete_ablation_seed_root)

    assert passed["schema"] == "cogguard.kt2.lgb_strict_reproduction_gate.v1"
    assert passed["status"] == "passed"
    assert passed["strict_reproduction_complete"] is True
    assert passed["datasets_checked"] == ["TwiBot-22", "TwiBot-20"]
    assert all(section["status"] == "passed" for section in passed["dataset_sections"])
    assert failed["status"] == "incomplete"
    assert failed["strict_reproduction_complete"] is False
    assert any("TwiBot-20" in item for item in failed["open_items"])
    assert any("Table III" in item or "ablation" in item for item in failed["open_items"])
    assert no_context["status"] == "incomplete"
    assert any("unlabeled context" in item for item in no_context["open_items"])
    assert bad_gcl["status"] == "incomplete"
    assert any("GCL" in item for item in bad_gcl["open_items"])
    assert missing_metadata["status"] == "incomplete"
    assert any("run metadata" in item for item in missing_metadata["open_items"])
    assert missing_paper_target["status"] == "incomplete"
    assert any("Table II" in item or "paper target" in item for item in missing_paper_target["open_items"])
    assert missing_gnn_variant["status"] == "incomplete"
    assert any("GNN variant" in item for item in missing_gnn_variant["open_items"])
    assert mismatched_run_protocol["status"] == "incomplete"
    assert any("run-level protocol" in item for item in mismatched_run_protocol["open_items"])
    assert proxy_ablation_protocol["status"] == "incomplete"
    assert any("run-level protocol" in item for item in proxy_ablation_protocol["open_items"])
    assert small_conversion["status"] == "incomplete"
    assert any("official dataset" in item for item in small_conversion["open_items"])
    assert mismatched_lm_count["status"] == "incomplete"
    assert any("cross-artifact" in item for item in mismatched_lm_count["open_items"])
    assert mismatched_feature_source["status"] == "incomplete"
    assert any("cross-artifact" in item for item in mismatched_feature_source["open_items"])
    assert weak_reproduction_level["status"] == "incomplete"
    assert any("reproduction level" in item for item in weak_reproduction_level["open_items"])
    assert missing_run_metric["status"] == "incomplete"
    assert any("run-level metrics" in item for item in missing_run_metric["open_items"])
    assert incomplete_ablation_seed["status"] == "incomplete"
    assert any("ablation run metrics" in item for item in incomplete_ablation_seed["open_items"])


def test_lgb_strict_gate_can_write_human_readable_report():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "TwiBot-22").mkdir(parents=True)
        _write_lgb_gate_artifacts(root / "TwiBot-22", "TwiBot-22", complete=False)
        gate = run_lgb_strict_reproduction_gate(root)
        report_path = root / "lgb_strict_gate.md"
        markdown = write_lgb_strict_gate_report(gate, report_path)
        written = report_path.read_text(encoding="utf-8")

    assert markdown == written
    assert "# LGB Strict Reproduction Gate" in markdown
    assert "Strict reproduction complete: `False`" in markdown
    assert "TwiBot-22" in markdown
    assert "TwiBot-20" in markdown
    assert "Open Items" in markdown


def test_lgb_strict_reproduction_pipeline_reports_missing_official_datasets():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_lgb_strict_reproduction_pipeline(
            dataset_root=root / "dataset",
            artifacts_root=root / "artifacts",
            device="cpu",
        )

    assert result["schema"] == "cogguard.kt2.lgb_strict_reproduction_pipeline.v1"
    assert result["status"] == "incomplete"
    assert result["strict_reproduction_complete"] is False
    assert {dataset["dataset"] for dataset in result["datasets"]} == {"TwiBot-22", "TwiBot-20"}
    assert all(dataset["status"] == "missing_official_dataset" for dataset in result["datasets"])
    assert any("TwiBot-22" in item for item in result["open_items"])
    assert any("TwiBot-20" in item for item in result["open_items"])


def test_lgb_strict_reproduction_pipeline_builds_gate_artifacts(monkeypatch):
    calls = []

    def fake_find(dataset_root, dataset, **_kwargs):
        source = Path(dataset_root) / f"{dataset}-source"
        source.mkdir(parents=True, exist_ok=True)
        return source

    def fake_readiness(dataset_root, required_datasets=("TwiBot-22", "TwiBot-20")):
        rows = []
        for dataset in required_datasets:
            source = fake_find(dataset_root, dataset)
            rows.append(
                {
                    "dataset": dataset,
                    "source_format": "twibot22" if dataset == "TwiBot-22" else "twibot20",
                    "path": str(source),
                    "strict_ready": True,
                    "sample_only": False,
                    "open_items": [],
                }
            )
        return {
            "schema": "cogguard.kt2.lgb_official_data_readiness.v1",
            "dataset_root": str(dataset_root),
            "required_datasets": list(required_datasets),
            "strict_data_ready": True,
            "datasets": rows,
            "open_items": [],
        }

    def fake_convert(source, out_dir, **kwargs):
        calls.append(("convert", Path(source).name, Path(out_dir).name, kwargs.get("source_format")))
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        official_node_count = 162865 if "22" in out.name else 229580
        label_counts = {"human": 81433, "bot": 81432} if "22" in out.name else {"human": 5237, "bot": 6589}
        summary = {
            "schema": "cogguard.kt2.lgb_conversion_summary.v1",
            "source_format": "twibot22" if "22" in out.name else "twibot20",
            "node_count": official_node_count,
            "edge_count": 10,
            "labeled_nodes": sum(label_counts.values()),
            "label_counts": label_counts,
            "split_counts": {"train": 10, "valid": 2, "test": 1},
            "include_unlabeled_context": True,
            "unlabeled_context_nodes": 1,
        }
        (out / "conversion_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return summary

    def fake_export(data_dir, out_dir, **kwargs):
        calls.append(("export_lm", Path(data_dir).name, kwargs.get("encoder_backend")))
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        dataset = Path(data_dir).name
        feature_file = str(out / "lm_features.jsonl")
        report = {
            "schema": "cogguard.kt2.lgb_lm_sft_features.v1",
            "status": "ok",
            "encoder_backend": kwargs.get("encoder_backend"),
            "strict_lgb_text_encoder": True,
            "feature_file": feature_file,
            "node_count": 162865 if "22" in dataset else 229580,
        }
        (out / "lm_sft_report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    def seed_runs(data_dir, *, seeds, **kwargs):
        calls.append(("multiseed", Path(data_dir).name, tuple(seeds), kwargs.get("text_features_path")))
        dataset = kwargs["dataset"]
        edge_views = [0.2, 0.4] if dataset == "TwiBot-22" else [0.4, 0.6]
        runs = [
            {
                "status": "ok",
                "seed": int(seed),
                "accuracy": 0.8,
                "f1": 0.81,
                "roc_auc": 0.8,
                "training_protocol": {
                    "gnn": "LGB(GCN)",
                    "text_encoder": kwargs["text_encoder"],
                    "text_features_source": kwargs["text_features_path"],
                    "edge_dropout_views": edge_views,
                    "gcl_temperature": 0.4,
                },
            }
            for seed in seeds
        ]
        payload = {
            "schema": "cogguard.kt2.lgb_multiseed_summary.v1",
            "status": "ok",
            "dataset": dataset,
            "reproduction_level": kwargs["reproduction_level"],
            "gnn_variant": "GCN",
            "paper_target": {
                "table": "Table II",
                "model": "LGB(GCN)",
                "accuracy": 0.8042 if dataset == "TwiBot-22" else 0.8509,
                "f1": 0.8131 if dataset == "TwiBot-22" else 0.8744,
                "roc_auc": 0.8042 if dataset == "TwiBot-22" else 0.8423,
            },
            "num_runs": len(seeds),
            "seeds": list(seeds),
            "meets_paper_seed_count": len(seeds) >= 5,
            "metrics_mean_std": {
                "accuracy": {"mean": 0.8, "std": 0.01},
                "f1": {"mean": 0.81, "std": 0.01},
                "roc_auc": {"mean": 0.8, "std": 0.01},
            },
            "runs": runs,
            "run_metadata": {
                "artifact_type": "lgb_multiseed_summary",
                "dataset": dataset,
                "data_dir": str(data_dir),
                "command_or_entrypoint": "benchmark.adapters.lgb_bot_detection",
                "seeds": list(seeds),
                "reproduction_level": kwargs["reproduction_level"],
            },
        }
        output_path = kwargs.get("output_path")
        if output_path:
            Path(output_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def fake_ablation(data_dir, *, seeds, variants, **kwargs):
        calls.append(("ablation", Path(data_dir).name, tuple(variants)))
        dataset = kwargs["dataset"]
        output_path = kwargs.pop("output_path", None)
        main = seed_runs(data_dir, seeds=seeds, output_path=None, **kwargs)
        payload = {
            "schema": "cogguard.kt2.lgb_ablation_suite.v1",
            "status": "ok",
            "dataset": dataset,
            "reproduction_level": kwargs["reproduction_level"],
            "seeds": list(seeds),
            "completed_variants": list(variants),
            "required_table3_variants": list(lgb_bot_detection_module.LGB_TABLE3_VARIANTS),
            "table3_complete": True,
            "variants": [{"variant": variant, "summary": main} for variant in variants],
            "run_metadata": {
                "artifact_type": "lgb_ablation_suite",
                "dataset": dataset,
                "data_dir": str(data_dir),
                "command_or_entrypoint": "benchmark.adapters.lgb_bot_detection",
                "seeds": list(seeds),
                "variants": list(variants),
                "reproduction_level": kwargs["reproduction_level"],
            },
        }
        if output_path:
            Path(output_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(lgb_bot_detection_module, "_find_lgb_official_dataset_root", fake_find)
    monkeypatch.setattr(lgb_bot_detection_module, "inspect_lgb_official_data_readiness", fake_readiness)
    monkeypatch.setattr(lgb_bot_detection_module, "convert_lgb_official_dataset", fake_convert)
    monkeypatch.setattr(lgb_bot_detection_module, "export_lgb_lm_sft_features", fake_export)
    monkeypatch.setattr(lgb_bot_detection_module, "run_lgb_multiseed", seed_runs)
    monkeypatch.setattr(lgb_bot_detection_module, "run_lgb_ablation_suite", fake_ablation)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_lgb_strict_reproduction_pipeline(
            dataset_root=root / "dataset",
            artifacts_root=root / "artifacts",
            device="cpu",
            seeds=[42, 43, 44, 45, 46],
            encoder_backend="transformers_roberta_sft",
        )

    assert result["status"] == "passed"
    assert result["strict_reproduction_complete"] is True
    assert result["gate"]["status"] == "passed"
    assert all(dataset["status"] == "passed" for dataset in result["datasets"])
    assert any(call[0] == "convert" and call[1] == "TwiBot-22-source" for call in calls)
    assert any(call[0] == "export_lm" and call[2] == "transformers_roberta_sft" for call in calls)
    assert any(call[0] == "ablation" and set(call[2]) == set(lgb_bot_detection_module.LGB_TABLE3_VARIANTS) for call in calls)


def test_lgb_strict_pipeline_cli_defaults_to_strict_reproduction_level(monkeypatch, capsys):
    captured = {}

    def fake_pipeline(**kwargs):
        captured.update(kwargs)
        return {
            "schema": "cogguard.kt2.lgb_strict_reproduction_pipeline.v1",
            "status": "incomplete",
            "strict_reproduction_complete": False,
        }

    monkeypatch.setattr(lgb_bot_detection_module, "run_lgb_strict_reproduction_pipeline", fake_pipeline)

    code = lgb_bot_detection_module.main(
        [
            "--strict_pipeline",
            "--dataset_root",
            "dataset",
            "--artifacts_root",
            "artifacts",
        ]
    )
    captured_output = capsys.readouterr().out

    assert code == 1
    assert json.loads(captured_output)["status"] == "incomplete"
    assert captured["reproduction_level"] == "strict_lgb_reproduction_full_run"


def test_lgb_official_data_readiness_detects_required_full_dataset_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        twibot22 = root / "TwiBot-22"
        twibot22.mkdir()
        (twibot22 / "user.json").write_text("[]", encoding="utf-8")
        (twibot22 / "label.csv").write_text("id,label\n", encoding="utf-8")
        (twibot22 / "split.csv").write_text("id,split\n", encoding="utf-8")
        (twibot22 / "edge.csv").write_text("source,target\n", encoding="utf-8")
        (twibot22 / "tweet_0.json").write_text("[]", encoding="utf-8")
        twibot20 = root / "TwiBot-20"
        twibot20.mkdir()
        for name in ("train.json", "dev.json", "test.json"):
            (twibot20 / name).write_text("[]", encoding="utf-8")

        readiness = inspect_lgb_official_data_readiness(root)

    twibot22_row = {row["dataset"]: row for row in readiness["datasets"]}["TwiBot-22"]
    twibot20_row = {row["dataset"]: row for row in readiness["datasets"]}["TwiBot-20"]
    assert readiness["strict_data_ready"] is True
    assert twibot22_row["strict_ready"] is True
    assert twibot22_row["source_format"] == "twibot22"
    assert twibot20_row["strict_ready"] is True
    assert twibot20_row["sample_only"] is False


def test_lgb_official_data_readiness_rejects_twibot20_sample_only():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sample = root / "TwiBot-20"
        sample.mkdir()
        (sample / "TwiBot-20_sample.json").write_text("[]", encoding="utf-8")

        readiness = inspect_lgb_official_data_readiness(root)

    twibot20_row = {row["dataset"]: row for row in readiness["datasets"]}["TwiBot-20"]
    assert readiness["strict_data_ready"] is False
    assert twibot20_row["strict_ready"] is False
    assert twibot20_row["sample_only"] is True
    assert any("sample" in item.lower() for item in twibot20_row["open_items"])


def test_lgb_inspect_data_cli_reports_incomplete_for_missing_data(monkeypatch, capsys):
    def fake_readiness(dataset_root):
        return {
            "schema": "cogguard.kt2.lgb_official_data_readiness.v1",
            "dataset_root": str(dataset_root),
            "strict_data_ready": False,
            "datasets": [],
            "open_items": ["missing official data"],
        }

    monkeypatch.setattr(lgb_bot_detection_module, "inspect_lgb_official_data_readiness", fake_readiness)

    code = lgb_bot_detection_module.main(["--inspect_data", "--dataset_root", "dataset"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["strict_data_ready"] is False
    assert payload["open_items"] == ["missing official data"]


def test_lgb_data_request_package_records_official_sources_and_next_commands():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = generate_lgb_data_request_package(
            dataset_root=root / "dataset",
            output_dir=root / "request",
            repo_root=root / "repo",
        )
        written_json = json.loads((root / "request" / "lgb_data_request_package.json").read_text(encoding="utf-8"))
        written_md = (root / "request" / "lgb_data_request_package.md").read_text(encoding="utf-8")

    assert package == written_json
    assert package["schema"] == "cogguard.kt2.lgb_data_request_package.v1"
    assert package["status"] == "pending_authorized_data"
    assert package["strict_reproduction_unblocked"] is False
    assert {item["dataset"] for item in package["datasets"]} == {"TwiBot-22", "TwiBot-20"}
    assert any("LuoUndergradXJTU/TwiBot-22" in item["official_repository"] for item in package["datasets"])
    assert any("BunsenFeng/TwiBot-20" in item["official_repository"] for item in package["datasets"])
    assert "TwiBot-20_sample.json" in package["sample_data_policy"]
    assert "--inspect_data" in package["commands"]["preflight"]
    assert "--strict_pipeline" in package["commands"]["strict_pipeline"]
    assert "TwiBot-20_sample.json" in written_md
    assert "pending_authorized_data" in written_md


def test_lgb_twibot22_official_schema_conversion_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "twibot22"
        root.mkdir()
        (root / "user.json").write_text(
            json.dumps(
                [
                    {
                        "id": "u1",
                        "name": "human user",
                        "username": "human1",
                        "description": "community news",
                        "created_at": "2024-01-01",
                        "public_metrics": {"followers_count": 9, "following_count": 3, "tweet_count": 2, "listed_count": 1},
                        "verified": False,
                    },
                    {
                        "id": "u2",
                        "name": "bot user",
                        "username": "bot2",
                        "description": "promo HTTPURL",
                        "public_metrics": {"followers_count": 2, "following_count": 100, "tweet_count": 50, "listed_count": 0},
                        "verified": False,
                    },
                    {"id": "u3", "name": "unlabeled context"},
                ]
            ),
            encoding="utf-8",
        )
        (root / "tweet_0.json").write_text(
            json.dumps(
                [
                    {"id": "t1", "author_id": "u1", "text": "hello @friend"},
                    {"id": "t2", "author_id": "u2", "text": "buy now https://example.com"},
                ]
            ),
            encoding="utf-8",
        )
        (root / "label.csv").write_text("id,label\nu1,human\nu2,bot\n", encoding="utf-8")
        (root / "split.csv").write_text("id,split\nu1,train\nu2,test\n", encoding="utf-8")
        (root / "edge.csv").write_text("source_id,target_id,relation\nu1,u2,following\nu2,u3,following\n", encoding="utf-8")

        out_dir = Path(tmp) / "compact"
        summary = convert_lgb_official_dataset(root, out_dir, source_format="twibot22")
        dataset = load_lgb_dataset(out_dir)

    assert summary["source_format"] == "twibot22"
    assert summary["labeled_nodes"] == 2
    assert summary["label_counts"] == {"human": 1, "bot": 1}
    assert summary["skipped_unlabeled_users"] == 1
    assert summary["unlabeled_context_nodes"] == 1
    assert dataset.node_ids == ["u1", "u2", "u3"]
    assert dataset.labels.tolist() == [0, 1, -1]
    assert dataset.edges == [(0, 1), (1, 2)]
    assert "Tweet:" in dataset.texts[0]
    assert "HTTPURL" in dataset.texts[1]


def test_lgb_twibot22_jsonl_official_schema_conversion_streams_records():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "twibot22_jsonl"
        root.mkdir()
        users = [
            {
                "id": "u1",
                "name": "jsonl human",
                "description": "community news",
                "public_metrics": {"followers_count": 5, "following_count": 2, "tweet_count": 1, "listed_count": 0},
            },
            {
                "id": "u2",
                "name": "jsonl bot",
                "description": "automated promo",
                "public_metrics": {"followers_count": 1, "following_count": 50, "tweet_count": 10, "listed_count": 0},
            },
        ]
        tweets = [
            {"id": "t1", "author_id": "u1", "text": "hello from jsonl"},
            {"id": "t2", "author_id": "u2", "text": "promo https://example.com"},
        ]
        (root / "user.jsonl").write_text("\n".join(json.dumps(row) for row in users), encoding="utf-8")
        (root / "tweet_0.jsonl").write_text("\n".join(json.dumps(row) for row in tweets), encoding="utf-8")
        (root / "label.csv").write_text("id,label\nu1,human\nu2,bot\n", encoding="utf-8")
        (root / "split.csv").write_text("id,split\nu1,train\nu2,test\n", encoding="utf-8")
        (root / "edge.csv").write_text("source_id,target_id,relation\nu1,u2,following\n", encoding="utf-8")

        out_dir = Path(tmp) / "compact"
        summary = convert_lgb_official_dataset(root, out_dir, source_format="twibot22")
        dataset = load_lgb_dataset(out_dir)

    assert summary["source_format"] == "twibot22"
    assert summary["raw_user_count"] == 2
    assert summary["tweet_files"] == ["tweet_0.jsonl"]
    assert dataset.node_ids == ["u1", "u2"]
    assert dataset.edges == [(0, 1)]
    assert "HTTPURL" in dataset.texts[1]


def test_lgb_twibot20_raw_schema_conversion_and_audit():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "twibot20"
        root.mkdir()
        (root / "train.json").write_text(
            json.dumps(
                [
                    {
                        "ID": "10",
                        "profile": {"name": "human ten", "description": "ordinary", "followers_count": 5},
                        "tweet": ["local sports"],
                        "neighbor": {"following": ["11"], "followers": []},
                        "label": 0,
                    },
                    {
                        "ID": "11",
                        "profile": {"name": "bot eleven", "description": "automated", "followers_count": 1},
                        "tweet": ["promo @user"],
                        "neighbor": {"following": [], "followers": ["10"]},
                        "label": 1,
                    },
                ]
            ),
            encoding="utf-8",
        )
        (root / "dev.json").write_text(
            json.dumps(
                [
                    {
                        "ID": "12",
                        "profile": {"name": "human dev", "description": "valid account"},
                        "tweet": ["validation"],
                        "neighbor": ["10"],
                        "label": "human",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (root / "test.json").write_text(
            json.dumps(
                [
                    {
                        "ID": "13",
                        "profile": {"name": "bot test", "description": "bot account"},
                        "tweet": ["test bot"],
                        "neighbor": ["11"],
                        "label": "bot",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (root / "support.json").write_text(
            json.dumps([{"ID": "14", "profile": {"name": "support"}, "tweet": [], "neighbor": ["10"]}]),
            encoding="utf-8",
        )

        out_dir = Path(tmp) / "compact"
        summary = convert_lgb_official_dataset(root, out_dir, source_format="twibot20")
        dataset = load_lgb_dataset(out_dir)
        audit = audit_lgb_reproduction_status(Path(tmp), dataset_root=Path(tmp), output_dir=Path(tmp) / "audit")

    assert summary["source_format"] == "twibot20"
    assert summary["labeled_nodes"] == 4
    assert summary["label_counts"] == {"human": 2, "bot": 2}
    assert summary["skipped_unlabeled_users"] == 1
    assert summary["unlabeled_context_nodes"] == 1
    assert set(dataset.node_ids) == {"10", "11", "12", "13", "14"}
    assert set(dataset.train_idx.tolist()) == {0, 1}
    assert set(dataset.valid_idx.tolist()) == {2}
    assert set(dataset.test_idx.tolist()) == {3}
    assert len(dataset.edges) >= 2
    assert audit["schema"] == "cogguard.kt2.lgb_reproduction_audit.v1"
    assert audit["strict_reproduction_ready"] is False
    assert audit["strict_pipeline_ready"] is True
    assert "TwiBot-22" in audit["missing_required_datasets"]


def test_weibo_rumor_loader_sciencedb_shape():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "events.csv").write_text("e1,1,p1 p2 p3\n", encoding="utf-8")
        posts = root / "posts"
        posts.mkdir()
        (posts / "e1.json").write_text(
            json.dumps(
                [
                    {"id": "p1", "user": {"id": "u1"}, "text": "source", "created_at": "2024-01-01 00:00:00"},
                    {"id": "p2", "user": {"id": "u2"}, "parent_id": "p1", "text": "repost"},
                    {"id": "p3", "user": {"id": "u3"}, "parent_id": "p2", "text": "reply"},
                ]
            ),
            encoding="utf-8",
        )
        events = load_dataset("weibo_rumor", tmp)
    graph = events[0].to_graph()
    assert events[0].label == "rumor"
    assert graph.has_edge("p1", "p2")
    assert graph.has_edge("p2", "p3")


def test_rumor_rvnn_twitter_loader_shape():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        resource = root / "resource"
        resource.mkdir()
        (resource / "Twitter15_label_All.txt").write_text("false\tthread\troot1\t0\t0\n", encoding="utf-8")
        (resource / "data.TD_RvNN.vol_5000.txt").write_text(
            "root1\tNone\t1\t2\t9\t1:1\nroot1\t1\t2\t2\t9\t0:2\n",
            encoding="utf-8",
        )
        events = load_dataset("rumor_rvnn_twitter", tmp)
    graph = events[0].to_graph()
    assert events[0].label == "false"
    assert graph.has_edge("1", "2")


def test_pheme_loader_uses_thread_tweets_only():
    with tempfile.TemporaryDirectory() as tmp:
        thread = Path(tmp) / "all-rnr-annotated-threads" / "topic-all-rnr-threads" / "rumours" / "100"
        (thread / "source-tweets").mkdir(parents=True)
        (thread / "reactions").mkdir()
        (thread / "annotation.json").write_text(
            json.dumps({"category": "claim text", "true": "1", "misinformation": 0}),
            encoding="utf-8",
        )
        (thread / "structure.json").write_text(json.dumps({"100": {"101": []}}), encoding="utf-8")
        (thread / "source-tweets" / "100.json").write_text(
            json.dumps(
                {
                    "id_str": "100",
                    "text": "source",
                    "created_at": "Tue Mar 24 10:51:21 +0000 2015",
                    "user": {"id_str": "u1", "screen_name": "source_user", "followers_count": 10, "verified": True},
                }
            ),
            encoding="utf-8",
        )
        (thread / "reactions" / "101.json").write_text(
            json.dumps(
                {
                    "id_str": "101",
                    "text": "reply",
                    "created_at": "Tue Mar 24 10:52:21 +0000 2015",
                    "in_reply_to_status_id_str": "100",
                    "user": {"id_str": "u2"},
                }
            ),
            encoding="utf-8",
        )
        events = load_dataset("pheme", tmp)
    graph = events[0].to_graph()
    assert events[0].label == "true-rumour"
    assert events[0].metadata["claim"] == "claim text"
    assert set(graph.nodes) == {"100", "101"}
    assert graph.has_edge("100", "101")
    assert events[0].participants["u1"].screen_name == "source_user"


def test_final_report_builder_handles_missing_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        result = build_final_report("FINAL_REPORT.md", tmp)
        report = Path(result["report"])
        assert report.exists()
        text = report.read_text(encoding="utf-8")
        assert "任务覆盖" in text
        assert "验收结论" in text


def test_hyperidp_protocol_proxy_temporal_hyperedge_candidates():
    cascades = [
        [(1, 0), (2, 10), (3, 20), (4, 90000)],
        [(1, 0), (3, 10), (5, 20), (6, 30)],
    ]
    popularity, transitions, hyper_neighbors = train_statistics(
        cascades,
        bucket_seconds=3600,
        max_bucket_users=10,
    )
    social_neighbors = {1: {7}, 7: {1}}

    rows = candidate_rows(
        observed_users=[1],
        popularity=popularity,
        transitions=transitions,
        hyper_neighbors=hyper_neighbors,
        social_neighbors=social_neighbors,
        global_candidates=[],
        max_candidates=10,
    )
    candidates = {row[0] for row in rows}

    assert 1 not in candidates
    assert {2, 3, 7}.issubset(candidates)
    assert hyper_neighbors[1][3] == 2
    assert len(prefix_features([1, 2], [0, 10], popularity, transitions, hyper_neighbors, social_neighbors)) == 10


def test_kt2_joint_model_trains_macro_micro_small_run():
    minds_repo = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS")
    assert minds_repo.exists()
    with tempfile.TemporaryDirectory() as tmp:
        data_root = _write_forest_fixture(Path(tmp), "douban")
        result = run_kt2_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_candidates=20,
            global_top_n=20,
            negatives_per_cascade=5,
            max_future_per_cascade=3,
            lambda_consistency=0.1,
            lambda_forest_pg=0.03,
            forest_pg_rollout_samples=2,
            minds_repo=minds_repo,
            seed=7,
        )
        schema = validate_benchmark_results([result])

    assert result["model"] == "KT2JointModel"
    assert result["task"] == "multi_scale"
    assert result["status"] == "ok"
    assert result["reproduction_level"] == "kt2_joint_model_small_run"
    assert result["msle"] is not None
    assert result["mae"] is not None
    assert result["hits@100"] >= 0
    assert result["mrr"] >= 0
    assert result["macro_micro_consistency"] is not None
    assert result["trend_mae"] is not None
    assert result["trend_rmse"] is not None
    assert result["candidate_protocol_audit"]["leakage_check_passed"] is True
    assert result["joint_training"]["consistency_loss_weight"] == 0.1
    assert "MINDS original public-code" in result["joint_training"]["methodology"]
    assert "adversarial" in result["joint_training"]["methodology"]
    assert "FOREST RNN hidden-state fusion" in result["joint_training"]["methodology"]
    assert "sampled growth reward" in result["joint_training"]["methodology"]
    assert "CasFT neural-ODE-style" in result["joint_training"]["methodology"]
    assert "shared-state-conditioned Gaussian noising and denoising loss" in result["joint_training"]["methodology"]
    assert result["joint_training"]["sequence_encoder"].startswith("GRU")
    assert "upstream MINDS DynamicCasHGNN/SharedLSTM" in result["joint_training"]["cross_context_encoder"]
    assert "fallback/ablation only" in result["joint_training"]["cross_context_encoder"]
    assert "upstream MINDS DynamicCasHGNN" in result["joint_training"]["minds_dynamic_hypergraph"]
    assert result["joint_training"]["minds_context_source"] == "original_minds_dynamic_cas_hgnn"
    assert result["joint_training"]["minds_shared_lstm_source"] == "original_minds_shared_lstm"
    assert result["joint_training"]["minds_component_status"] == "original_dynamic_cas_hgnn_fusion_shared_lstm"
    assert result["joint_training"]["minds_module_runtime_status"] == "original_module_forward_auxiliary"
    assert "neural-ODE-style" in result["joint_training"]["trend_auxiliary"]
    assert "denoising" in result["joint_training"]["diffusion_auxiliary"]
    assert "shared-state-conditioned" in result["joint_training"]["diffusion_auxiliary"]
    assert "gradient-reversal" in result["joint_training"]["adversarial_regularizer"]
    assert "sampled growth reward" in result["joint_training"]["reinforced_coupling"]
    assert "sampled growth reward" in result["joint_training"]["consistency_loss"]
    assert "not an original" in result["note"]
    assert "not the original CasFT diffusion generator" in result["research_migration"]["CasFT"]
    assert "MINDS original public-code" in result["research_migration"]["MINDS"]
    assert result["joint_training"]["orthogonality_loss_weight"] == 0.05
    assert result["joint_training"]["adversarial_loss_weight"] == 0.02
    assert result["joint_training"]["diffusion_loss_weight"] == 0.05
    assert result["joint_training"]["forest_pg_loss_weight"] == 0.03
    assert result["joint_training"]["forest_pg_rollout_samples"] == 2
    assert result["joint_training"]["diffusion_noise_std"] == 0.15
    assert result["joint_training"]["trend_loss_weight"] == 0.4
    assert result["trend_time_supervision"] == "timestamp-aware full-horizon normalized checkpoints with count-proportional fallback"
    assert result["joint_training"]["trend_time_supervision"] == result["trend_time_supervision"]
    assert result["joint_training"]["consistency_candidate_scope"] == "full_candidate_set"
    assert result["joint_training"]["max_consistency_candidates_per_event"] == 0
    assert result["joint_training"]["macro_log_support"]["source"] == "train macro and CasFT-style trend log-size labels"
    assert result["joint_training"]["macro_log_support"]["max"] >= result["joint_training"]["macro_log_support"]["min"]


def test_kt2_sequence_joint_model_builds_multi_window_sequence_examples():
    cascades = [
        [(1, 0), (2, 10), (3, 20), (4, 30), (5, 40)],
        [(2, 0), (3, 5), (6, 10), (7, 15), (8, 20)],
    ]

    bundle = build_sequence_training_examples(
        cascades,
        obs_ratios=[0.1, 0.3, 0.5],
        max_sequence_len=8,
        trend_steps=4,
        user_hash_buckets=64,
        negative_samples=3,
        seed=7,
    )

    assert bundle["window_count"] == 6
    assert bundle["macro_y"].shape[0] == 6
    assert bundle["trend_y"].shape == (6, 4)
    assert bundle["next_user_y"].shape[0] == 6
    assert bundle["negative_user_ids"].shape == (6, 3)
    assert bundle["relation_neighbor_ids"].shape == (6, 8, 4)
    assert bundle["hyperedge_user_ids"].shape == (6, 4, 8)
    assert bundle["window_weights"].shape == (6,)
    assert bundle["candidate_features_used_as_model_input"] is False
    assert np.all(bundle["observed_counts"] < bundle["final_counts"])
    assert np.all(np.diff(np.expm1(bundle["trend_y"]), axis=1) >= -1e-6)


def test_kt2_sequence_negative_sampling_uses_training_vocabulary_without_future_tail_reads():
    cascades = [[(10, 0), (11, 1), (12, 2), (13, 3), (14, 4)]]
    bundle = build_sequence_training_examples(
        cascades,
        obs_ratios=[0.4],
        max_sequence_len=8,
        trend_steps=4,
        user_hash_buckets=128,
        negative_samples=6,
        seed=7,
    )
    observed_count = int(bundle["observed_counts"][0])
    observed = set(int(value) for value in bundle["seq_user_ids"][0, :observed_count])
    negatives = set(int(value) for value in bundle["negative_user_ids"][0])

    assert int(bundle["next_user_y"][0]) not in negatives
    assert observed.isdisjoint(negatives)
    assert bundle["candidate_features_used_as_model_input"] is False


def test_kt2_sequence_training_examples_do_not_use_test_cascades_for_train_statistics():
    train = [[(1, 0), (2, 1), (3, 2), (4, 3)]]
    test = [[(90, 0), (91, 1), (92, 2), (93, 3)]]
    train_bundle = build_sequence_training_examples(
        train,
        obs_ratios=[0.5],
        user_hash_buckets=512,
        negative_samples=3,
        seed=7,
    )
    train_users = {user for user, _timestamp in train[0]}
    test_users = {user for user, _timestamp in test[0]}
    vocabulary = train_bundle["training_vocabulary"]
    train_ids = {vocabulary.encode(user) for user in train_users}

    assert set(int(value) for value in train_bundle["train_user_buckets"]) == train_ids
    assert all(vocabulary.encode(user) == UNK_USER_ID for user in test_users)
    assert set(int(value) for value in train_bundle["negative_user_ids"][0]).issubset(train_ids)


def test_kt2_sequence_joint_model_trains_sequence_macro_micro_small_run():
    with tempfile.TemporaryDirectory() as tmp:
        data_root = _write_forest_fixture(Path(tmp), "douban")
        result = run_kt2_sequence_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=4,
            hidden_dim=16,
            obs_ratios=[0.1, 0.3, 0.5],
            max_sequence_len=8,
            trend_steps=4,
            negative_samples=4,
            rollout_steps=3,
            seed=7,
        )
        schema = validate_benchmark_results([result])

    assert result["model"] == "KT2SequenceJointModel"
    assert result["status"] == "ok"
    assert result["task"] == "multi_scale"
    assert result["reproduction_level"] == "kt2_sequence_joint_model_small_run"
    assert result["training_protocol"]["micro_target"] == "next_user_autoregressive_sampled_softmax"
    assert result["training_protocol"]["candidate_features_used_as_model_input"] is False
    assert result["training_protocol"]["obs_ratios"] == [0.1, 0.3, 0.5]
    assert result["training_protocol"]["backbone_components"] == [
        "DynamicCasHGNN",
        "RelationGNN",
        "SharedLSTM",
        "EulerTrendDecoder",
    ]
    assert "event_id" in result["training_protocol"]["loss_normalization"]
    assert "Euler latent dynamics" in result["training_protocol"]["trend_decoder"]
    assert result["training_protocol"]["loss_weights"] == {
        "final_size": 1.0,
        "trend": 0.5,
        "next_user": 0.5,
        "soft_coupling": 0.05,
        "adversarial": 0.02,
        "diff_orthogonality": 0.01,
    }
    assert result["candidate_protocol_audit"]["leakage_check_passed"] is True
    assert result["candidate_protocol_audit"]["future_nodes_injected"] is False
    assert result["macro_micro_soft_consistency"] is not None
    assert result["msle"] is not None
    assert result["trend_mae"] is not None
    assert result["hits@100"] >= 0
    assert result["mrr"] >= 0
    assert result["rollout_summary"]["rollout_steps"] == 3
    assert result["rollout_summary"]["rollout_step_count_mean"] >= 1
    assert isinstance(result["rollout_summary"]["topk_examples"], list)
    assert "MINDS backbone" in result["methodology"]
    assert "candidate-row" in result["legacy_boundary"]
    assert schema["ok"] is True


def test_kt2_joint_model_local_minds_bridge_is_explicit_fallback_only():
    with tempfile.TemporaryDirectory() as tmp:
        data_root = _write_forest_fixture(Path(tmp), "douban")
        result = run_kt2_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_candidates=20,
            global_top_n=20,
            negatives_per_cascade=5,
            max_future_per_cascade=3,
            lambda_consistency=0.1,
            use_original_minds_components=False,
            use_original_minds_full_module=False,
            seed=7,
        )
        schema = validate_benchmark_results([result])

    assert result["status"] == "ok"
    assert result["joint_training"]["minds_component_status"] == "disabled"
    assert result["joint_training"]["minds_context_source"] == "local_minds_style_fallback"
    assert result["joint_training"]["minds_shared_lstm_source"] == "local_context_fusion_fallback"
    assert result["joint_training"]["minds_module_runtime_status"] == "disabled"
    assert "local MINDS-style fallback" in result["joint_training"]["methodology"]
    assert "sanity checks only" in result["baseline_role"]
    assert schema["ok"] is True


def test_kt2_trend_target_uses_timestamp_checkpoints_before_count_fallback():
    cascade = [(1, 0), (2, 10), (3, 11), (4, 100)]

    time_aware = trend_target(cascade, observed_count=2, trend_steps=2)
    count_fallback = trend_target(cascade, observed_count=2, trend_steps=2, time_aware=False)
    times = trend_time_grid(cascade, observed_count=2, trend_steps=2)

    assert np.allclose(np.expm1(time_aware), [3.0, 4.0])
    assert np.allclose(np.expm1(count_fallback), [3.0, 4.0])
    assert 0.0 < times[0] < times[1] <= 1.0

    skewed = [(1, 0), (2, 10), (3, 99), (4, 100)]
    assert np.allclose(np.expm1(trend_target(skewed, observed_count=2, trend_steps=2)), [2.0, 4.0])
    assert np.allclose(np.expm1(trend_target(skewed, observed_count=2, trend_steps=2, time_aware=False)), [3.0, 4.0])


def test_kt2_forest_policy_gradient_single_rollout_keeps_gradient():
    import torch

    torch.manual_seed(0)
    pred_micro = torch.tensor([0.25, -0.15, 0.4], requires_grad=True)

    loss = forest_policy_gradient_loss(
        pred_micro,
        observed_count=2,
        true_size=5,
        rollout_samples=1,
        device=pred_micro.device,
    )
    loss.backward()

    assert torch.isfinite(loss)
    assert pred_micro.grad is not None
    assert torch.any(torch.abs(pred_micro.grad) > 0)


def test_kt2_support_log_bounds_are_conservative_and_finite():
    macro_y = np.asarray([np.log1p(3), np.log1p(8), np.log1p(13)], dtype=np.float32)
    trend_y = np.asarray(
        [
            [np.log1p(4), np.log1p(6)],
            [np.log1p(8), np.log1p(13)],
        ],
        dtype=np.float32,
    )

    low, high, margin = support_log_bounds(macro_y, trend_y)

    assert np.isfinite(low)
    assert np.isfinite(high)
    assert np.isfinite(margin)
    assert low <= float(np.min(macro_y))
    assert high >= float(np.max(trend_y))
    assert np.expm1(high) < 100


def test_kt2_joint_model_can_use_original_minds_dynamic_hgnn_fusion_shared_lstm():
    minds_repo = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS")
    assert minds_repo.exists()
    with tempfile.TemporaryDirectory() as tmp:
        data_root = _write_forest_fixture(Path(tmp), "douban")
        result = run_kt2_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_candidates=20,
            global_top_n=20,
            negatives_per_cascade=5,
            max_future_per_cascade=3,
            lambda_consistency=0.1,
            use_original_minds_components=True,
            use_original_minds_full_module=False,
            minds_repo=minds_repo,
            seed=7,
        )
        schema = validate_benchmark_results([result])

    assert result["status"] == "ok"
    assert result["minds_component_status"] == "original_dynamic_cas_hgnn_fusion_shared_lstm"
    assert result["joint_training"]["minds_component_status"] == "original_dynamic_cas_hgnn_fusion_shared_lstm"
    assert result["joint_training"]["minds_dynamic_hgnn_runtime_status"] == "original_dynamic_cas_hgnn"
    assert result["joint_training"]["minds_context_source"] == "original_minds_dynamic_cas_hgnn"
    assert result["joint_training"]["minds_shared_lstm_source"] == "original_minds_shared_lstm"
    assert "upstream MINDS DynamicCasHGNN" in result["joint_training"]["minds_dynamic_hypergraph"]
    assert "MINDS original public-code DynamicCasHGNN/Fusion/SharedLSTM components are active" in result["research_migration"]["MINDS"]
    assert "full Module auxiliary status=disabled" in result["research_migration"]["MINDS"]
    assert schema["ok"] is True


def test_kt2_joint_model_can_use_original_minds_module_forward_auxiliary():
    minds_repo = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS")
    assert minds_repo.exists()
    with tempfile.TemporaryDirectory() as tmp:
        data_root = _write_forest_fixture(Path(tmp), "douban")
        result = run_kt2_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_candidates=20,
            global_top_n=20,
            negatives_per_cascade=5,
            max_future_per_cascade=3,
            max_sequence_len=8,
            lambda_consistency=0.1,
            use_original_minds_components=True,
            use_original_minds_full_module=True,
            lambda_original_minds_module=0.01,
            minds_repo=minds_repo,
            seed=7,
        )
        schema = validate_benchmark_results([result])

    assert result["status"] == "ok"
    assert result["minds_module_status"] == "original_module_forward_relationgnn_dynamiccashgnn"
    assert result["minds_module_runtime_status"] == "original_module_forward_auxiliary"
    assert result["joint_training"]["minds_module_macro_loss_mean"] > 0
    assert result["joint_training"]["minds_module_micro_loss_mean"] > 0
    assert result["joint_training"]["minds_module_alignment_loss_mean"] >= 0
    assert "teacher signals" in result["joint_training"]["original_component_distillation"]
    assert "Module.forward/RelationGNN" in result["research_migration"]["MINDS"]
    assert schema["ok"] is True


def test_kt2_joint_model_can_use_original_forest_rnnmodel_auxiliary():
    forest_repo = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST")
    assert forest_repo.exists()
    with tempfile.TemporaryDirectory() as tmp:
        data_root = _write_forest_fixture(Path(tmp), "douban")
        result = run_kt2_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_candidates=20,
            global_top_n=20,
            negatives_per_cascade=5,
            max_future_per_cascade=3,
            lambda_consistency=0.1,
            use_original_forest_components=True,
            forest_repo=forest_repo,
            lambda_original_forest_ce=0.02,
            seed=7,
        )
        schema = validate_benchmark_results([result])

    assert result["status"] == "ok"
    assert result["forest_component_status"] == "original_rnnmodel_rrmodel"
    assert result["joint_training"]["forest_component_status"] == "original_rnnmodel_rrmodel"
    assert result["joint_training"]["forest_hidden_fusion_status"] == "original_rnnmodel_hidden_fused"
    assert result["joint_training"]["forest_runtime_status"] == "original_rnnmodel_rrmodel_auxiliary"
    assert result["joint_training"]["forest_auxiliary_ce_mean"] > 0
    assert result["joint_training"]["forest_size_alignment_loss_mean"] >= 0
    assert "FOREST RRModel sampled EOS sizes" in result["joint_training"]["original_component_distillation"]
    assert "optional upstream FOREST RNNModel/RRModel auxiliary" in result["research_migration"]["FOREST"]
    assert "not the full FOREST training protocol" in result["research_migration"]["FOREST"]
    assert schema["ok"] is True


def _write_fake_casft_repo(root: Path) -> Path:
    repo = root / "fake_CasFT"
    model_dir = repo / "model"
    diffusion_dir = repo / "model" / "diffusion"
    temporal_dir = repo / "model" / "temporal"
    diffusion_dir.mkdir(parents=True)
    temporal_dir.mkdir(parents=True)
    (model_dir / "__init__.py").write_text("", encoding="utf-8")
    (diffusion_dir / "__init__.py").write_text(
        "from .DiffusionModel import GaussianDiffusion_ST, ST_Diffusion\n",
        encoding="utf-8",
    )
    (diffusion_dir / "DiffusionModel.py").write_text(
        """
import torch
import torch.nn as nn


class ST_Diffusion(nn.Module):
    def __init__(self, num_units=20, self_condition=False, condition=True, cond_dim=4, output_dim=4):
        super().__init__()
        self.channels = 1
        self.self_condition = self_condition
        self.net = nn.Linear(cond_dim, output_dim)

    def forward(self, x, t, cond=None):
        return self.net(cond)


class GaussianDiffusion_ST(nn.Module):
    def __init__(self, model, *, seq_length, timesteps=2, sampling_timesteps=1, loss_type='l2', objective='pred_noise', beta_schedule='cosine'):
        super().__init__()
        self.model = model
        self.channels = model.channels
        self.self_condition = model.self_condition
        self.seq_length = seq_length

    def forward(self, img, cond, *args, **kwargs):
        t = torch.zeros(img.shape[0], dtype=torch.long, device=img.device)
        output = self.model(img, t, cond=cond)
        loss = torch.mean((output - img) ** 2)
        return output, loss
""".strip(),
        encoding="utf-8",
    )
    (temporal_dir / "__init__.py").write_text(
        """
import torch
import torch.nn as nn


class NeuralPointProcess(nn.Module):
    def __init__(self, cond_dim=0, hidden_dims=None, cond=True, style='split', actfn='softplus', otreg_strength=1e-4, tol=1e-4, solver='euler'):
        super().__init__()
        hidden_dims = hidden_dims or [8, 8]
        self.hdim = hidden_dims[0]
        self.proj = nn.Linear(max(cond_dim, 1), self.hdim)

    def logprob(self, event_times, spatial_locations, input_mask, t0, t1):
        base = spatial_locations
        if base.shape[-1] == 0:
            base = torch.zeros(event_times.shape[0], event_times.shape[1], 1, device=event_times.device)
        hidden = torch.tanh(self.proj(base))
        steps = len(t1)
        lamdas = [event_times.mean(dim=1) + float(idx) for idx in range(steps)]
        intensities = torch.stack(lamdas, dim=1)
        prejump = hidden[:, :1, :].repeat(1, steps, 1)
        return intensities, lamdas, prejump
""".strip(),
        encoding="utf-8",
    )
    (model_dir / "spatiotemporal.py").write_text(
        """
import torch
import torch.nn as nn


class CombinedSpatiotemporalModel5(nn.Module):
    def __init__(self, temporal_model, encoder_model, args):
        super().__init__()
        self.temporal_model = temporal_model
        self.args = args
        self.pred = nn.Linear(int(args.tpp_hdims) + int(args.interval_num), 1)

    def forward(self, event_times, spatial_events, input_mask, t0, t1, label, seq, cum_seq):
        event_times = event_times * float(self.args.observation_time) / float(self.args.prediction_time)
        intensities, lamdas, prejump_hidden_states = self.temporal_model.logprob(event_times, spatial_events, input_mask, t0, t1)
        all_lamdas = torch.stack(lamdas, dim=1)
        time_emb = prejump_hidden_states[:, 0, :]
        cond = torch.cat([time_emb, all_lamdas[:, 1:]], dim=1)
        pre_label = torch.nn.functional.softplus(self.pred(cond))
        loss = torch.mean((pre_label - label) ** 2) + torch.mean((seq - seq.detach().mean(dim=1, keepdim=True)) ** 2)
        return pre_label, loss * float(self.args.loss_scale)
""".strip(),
        encoding="utf-8",
    )
    return repo


def test_kt2_joint_model_can_use_original_casft_diffusion_adapter_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_root = _write_forest_fixture(root, "douban")
        fake_casft = _write_fake_casft_repo(root)
        result = run_kt2_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_candidates=20,
            global_top_n=20,
            negatives_per_cascade=5,
            max_future_per_cascade=3,
            lambda_consistency=0.1,
            seed=7,
            use_original_casft_diffusion=True,
            casft_repo=fake_casft,
            casft_diffusion_timesteps=2,
            casft_sampling_timesteps=1,
        )
        schema = validate_benchmark_results([result])

    assert result["status"] == "ok"
    assert result["reproduction_level"] == "kt2_joint_model_small_run"
    assert result["casft_diffusion_status"] == "original_gaussian_diffusion_st"
    assert "CasFT original GaussianDiffusion_ST" in result["joint_training"]["diffusion_auxiliary"]
    assert "not the full CasFT" in result["research_migration"]["CasFT"]
    assert schema["ok"] is True


def test_kt2_joint_model_can_use_original_casft_spatiotemporal_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_root = _write_forest_fixture(root, "douban")
        fake_casft = _write_fake_casft_repo(root)
        result = run_kt2_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_candidates=20,
            global_top_n=20,
            negatives_per_cascade=5,
            max_future_per_cascade=3,
            lambda_consistency=0.1,
            seed=7,
            use_original_casft_spatiotemporal=True,
            casft_repo=fake_casft,
            lambda_original_casft_spatiotemporal=0.01,
            casft_spatiotemporal_interval_num=4,
            casft_spatiotemporal_tpp_hdim=8,
        )
        schema = validate_benchmark_results([result])

    assert result["status"] == "ok"
    assert result["casft_spatiotemporal_status"] == "original_combined_spatiotemporal_model5_neural_point_process"
    assert result["casft_spatiotemporal_runtime_status"] == "original_combined_spatiotemporal_model5_auxiliary"
    assert result["casft_spatiotemporal_fusion_status"] == "original_combined_spatiotemporal_model5_main_fused"
    assert result["joint_training"]["casft_spatiotemporal_fusion_status"] == "original_combined_spatiotemporal_model5_main_fused"
    assert result["joint_training"]["casft_spatiotemporal_loss_mean"] > 0
    assert result["joint_training"]["casft_spatiotemporal_alignment_loss_mean"] >= 0
    assert "prefix-only continuous-time size/trend signal" in result["joint_training"]["original_component_distillation"]
    assert "CombinedSpatiotemporalModel5/NeuralPointProcess" in result["research_migration"]["CasFT"]
    assert schema["ok"] is True


def test_kt2_joint_model_can_combine_original_minds_forest_casft_components():
    minds_repo = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS")
    forest_repo = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_root = _write_forest_fixture(root, "douban")
        fake_casft = _write_fake_casft_repo(root)
        result = run_kt2_joint_model(
            data_root / "data" / "douban",
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_candidates=20,
            global_top_n=20,
            negatives_per_cascade=5,
            max_future_per_cascade=3,
            lambda_consistency=0.1,
            seed=7,
            use_original_minds_components=True,
            use_original_minds_full_module=True,
            lambda_original_minds_module=0.01,
            minds_repo=minds_repo,
            use_original_forest_components=True,
            forest_repo=forest_repo,
            lambda_original_forest_ce=0.02,
            use_original_casft_diffusion=True,
            use_original_casft_spatiotemporal=True,
            casft_repo=fake_casft,
            casft_diffusion_timesteps=2,
            casft_sampling_timesteps=1,
            lambda_original_casft_spatiotemporal=0.01,
            casft_spatiotemporal_interval_num=4,
            casft_spatiotemporal_tpp_hdim=8,
        )
        schema = validate_benchmark_results([result])

    assert result["status"] == "ok"
    assert result["minds_component_status"] == "original_dynamic_cas_hgnn_fusion_shared_lstm"
    assert result["forest_component_status"] == "original_rnnmodel_rrmodel"
    assert result["casft_diffusion_status"] == "original_gaussian_diffusion_st"
    assert result["casft_spatiotemporal_runtime_status"] == "original_combined_spatiotemporal_model5_auxiliary"
    assert result["casft_spatiotemporal_fusion_status"] == "original_combined_spatiotemporal_model5_main_fused"
    assert result["joint_training"]["minds_dynamic_hgnn_runtime_status"] == "original_dynamic_cas_hgnn"
    assert result["minds_module_runtime_status"] == "original_module_forward_auxiliary"
    assert result["joint_training"]["forest_runtime_status"] == "original_rnnmodel_rrmodel_auxiliary"
    assert result["joint_training"]["forest_auxiliary_ce_mean"] > 0
    assert result["joint_training"]["minds_module_alignment_loss_mean"] >= 0
    assert result["joint_training"]["forest_size_alignment_loss_mean"] >= 0
    assert result["joint_training"]["casft_spatiotemporal_alignment_loss_mean"] >= 0
    assert schema["ok"] is True


def test_kt2_joint_schema_rejects_overclaim_and_missing_metrics():
    row = {
        "model": "KT2JointModel",
        "dataset": "douban",
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "kt2_joint_model_small_run",
        "msle": None,
        "mae": 1.0,
        "rmse": 1.0,
        "direction_accuracy": 0.5,
        "candidate_recall_full": 0.1,
        "hits@10": 0.1,
        "hits@50": 0.1,
        "hits@100": 0.1,
        "mrr": 0.1,
        "macro_micro_consistency": 0.1,
        "candidate_protocol_audit": {"leakage_check_passed": True},
        "note": "paper reproduction complete",
    }
    schema = validate_benchmark_results([row])

    assert schema["ok"] is False
    assert any("finite macro metric msle" in error for error in schema["errors"])
    assert any("not an original paper-architecture reproduction" in error for error in schema["errors"])


def test_forest_parser_accepts_float_and_scientific_timestamps():
    cascade = parse_cascade("158757627,1.285452422e+12 180,338299.765278 bad-token x,y")

    assert cascade == [(180, 338299), (158757627, 1285452422000)]


def test_kt2_joint_missing_data_keeps_candidate_audit_schema():
    row = {
        "model": "KT2JointModel",
        "dataset": "twitter",
        "task": "multi_scale",
        "status": "missing_data",
        "reproduction_level": "kt2_joint_model_small_run",
        "candidate_protocol_audit": {"leakage_check_passed": True},
        "note": "missing local parseable cascades",
    }

    schema = validate_benchmark_results([row])

    assert schema["ok"] is True


def test_original_fusion_gate_requires_all_original_subpaths():
    row = {
        "model": "KT2JointModel",
        "status": "ok",
        "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
        "minds_module_runtime_status": "original_module_forward_auxiliary",
        "forest_runtime_status": "disabled",
        "casft_diffusion_status": "original_gaussian_diffusion_st",
        "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
        "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
    }

    failures = original_subpath_failures(row)

    assert failures == [
        {
            "field": "forest_runtime_status",
            "expected": "original_rnnmodel_rrmodel_auxiliary",
            "actual": "disabled",
        }
    ]


def test_original_fusion_audit_requires_teacher_alignment_losses():
    row = {
        "model": "KT2JointModel",
        "dataset": "douban",
        "seed": 42,
        "status": "ok",
        "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
        "minds_module_runtime_status": "original_module_forward_auxiliary",
        "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
        "casft_diffusion_status": "original_gaussian_diffusion_st",
        "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
        "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
        "joint_training": {
            "minds_module_alignment_loss_mean": 1.0,
            "forest_size_alignment_loss_mean": 2.0,
            "casft_spatiotemporal_alignment_loss_mean": 3.0,
            "original_component_distillation": "teacher signals from upstream components",
        },
    }

    assert original_subpath_failures(row) == []
    assert original_alignment_failures(row) == []
    audit = original_subpath_audit([row])

    assert audit["all_original_subpaths_passed"] is True
    assert audit["all_alignment_losses_recorded"] is True
    row["joint_training"].pop("forest_size_alignment_loss_mean")
    assert original_alignment_failures(row) == [
        {
            "field": "forest_size_alignment_loss_mean",
            "expected": "FOREST RRModel sampled EOS-size teacher alignment",
            "actual": "None",
        }
    ]


def test_original_fusion_experiment_writes_incremental_checkpoints(monkeypatch):
    calls = []

    def fake_run_one(_args, dataset, seed, obs_ratio):
        calls.append((dataset, seed, obs_ratio))
        return {
            "model": "KT2JointModel",
            "dataset": dataset,
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "kt2_joint_model_small_run",
            "seed": seed,
            "msle": 1.0,
            "mae": 2.0,
            "rmse": 3.0,
            "direction_accuracy": 0.5,
            "candidate_recall_full": 0.2,
            "hits@10": 0.1,
            "hits@50": 0.2,
            "hits@100": 0.3,
            "mrr": 0.4,
            "macro_micro_consistency": 0.5,
            "candidate_protocol_audit": {"leakage_check_passed": True},
            "note": "not an original MINDS FOREST CasFT reproduction",
            "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
            "minds_module_runtime_status": "original_module_forward_auxiliary",
            "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
            "casft_diffusion_status": "original_gaussian_diffusion_st",
            "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
        "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
            "joint_training": {
                "methodology": "not the original MINDS FOREST CasFT reproduction",
                "minds_module_alignment_loss_mean": 1.0,
                "forest_size_alignment_loss_mean": 2.0,
                "casft_spatiotemporal_alignment_loss_mean": 3.0,
                "original_component_distillation": "teacher signals from upstream components",
            },
        }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "fusion.json"
        args = argparse.Namespace(
            datasets="douban,twitter",
            seeds="42",
            out=str(out),
            forest_data_root=str(Path(tmp)),
            resume=False,
            max_runs=0,
            obs_ratio=0.3,
            obs_ratios="0.3",
            config_id="default-small",
        )
        monkeypatch.setattr(original_fusion_experiment, "run_one", fake_run_one)
        summary = original_fusion_experiment.run_experiment(args)
        checkpoint = json.loads(out.read_text(encoding="utf-8"))
        markdown_written = out.with_suffix(".md").is_file()

    assert summary["status"] == "ok"
    assert checkpoint["runs"] == 2
    assert checkpoint["original_subpath_audit"]["all_original_subpaths_passed"] is True
    assert checkpoint["original_subpath_audit"]["all_alignment_losses_recorded"] is True
    assert markdown_written is True
    assert calls == [("douban", 42, 0.3), ("twitter", 42, 0.3)]


def test_original_fusion_experiment_resume_skips_completed_rows(monkeypatch):
    calls = []

    def fake_run_one(_args, dataset, seed, obs_ratio):
        calls.append((dataset, seed, obs_ratio))
        return {
            "model": "KT2JointModel",
            "dataset": dataset,
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "kt2_joint_model_small_run",
            "seed": seed,
            "msle": 1.0,
            "mae": 2.0,
            "rmse": 3.0,
            "direction_accuracy": 0.5,
            "candidate_recall_full": 0.2,
            "hits@10": 0.1,
            "hits@50": 0.2,
            "hits@100": 0.3,
            "mrr": 0.4,
            "macro_micro_consistency": 0.5,
            "candidate_protocol_audit": {"leakage_check_passed": True},
            "note": "not an original MINDS FOREST CasFT reproduction",
            "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
            "minds_module_runtime_status": "original_module_forward_auxiliary",
            "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
            "casft_diffusion_status": "original_gaussian_diffusion_st",
            "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
        "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
            "joint_training": {
                "methodology": "not the original MINDS FOREST CasFT reproduction",
                "minds_module_alignment_loss_mean": 1.0,
                "forest_size_alignment_loss_mean": 2.0,
                "casft_spatiotemporal_alignment_loss_mean": 3.0,
                "original_component_distillation": "teacher signals from upstream components",
            },
        }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "fusion.json"
        monkeypatch.setattr(original_fusion_experiment, "run_one", fake_run_one)
        first = argparse.Namespace(
            datasets="douban,twitter,memetracker",
            seeds="42",
            out=str(out),
            forest_data_root=str(Path(tmp)),
            resume=False,
            max_runs=1,
            obs_ratio=0.3,
            obs_ratios="0.3",
            config_id="default-small",
        )
        first_summary = original_fusion_experiment.run_experiment(first)
        second = argparse.Namespace(
            datasets="douban,twitter,memetracker",
            seeds="42",
            out=str(out),
            forest_data_root=str(Path(tmp)),
            resume=True,
            max_runs=0,
            obs_ratio=0.3,
            obs_ratios="0.3",
            config_id="default-small",
        )
        summary = original_fusion_experiment.run_experiment(second)
        rows = json.loads(out.read_text(encoding="utf-8"))["rows"]

    assert first_summary["status"] == "partial"
    assert first_summary["matrix_coverage"]["completed_expected_runs"] == 1
    assert first_summary["matrix_coverage"]["pending_keys"] == [
        {"dataset": "twitter", "seed": 42, "obs_ratio": 0.3, "config_id": "default-small"},
        {"dataset": "memetracker", "seed": 42, "obs_ratio": 0.3, "config_id": "default-small"},
    ]
    assert calls == [("douban", 42, 0.3), ("twitter", 42, 0.3), ("memetracker", 42, 0.3)]
    assert summary["runs"] == 3
    assert summary["status"] == "ok"
    assert summary["matrix_coverage"]["coverage_ratio"] == 1.0
    assert [(row["dataset"], row["seed"]) for row in rows] == [
        ("douban", 42),
        ("twitter", 42),
        ("memetracker", 42),
    ]


def test_original_fusion_matrix_coverage_reports_pending_pairs():
    rows = [{"model": "KT2JointModel", "dataset": "douban", "seed": 42}]

    coverage = matrix_coverage(rows, ["douban", "twitter"], [42, 43], [0.3], "default-small")

    assert coverage["expected_runs"] == 4
    assert coverage["completed_expected_runs"] == 1
    assert coverage["coverage_ratio"] == 0.25
    assert coverage["pending_keys"] == [
        {"dataset": "douban", "seed": 43, "obs_ratio": 0.3, "config_id": "default-small"},
        {"dataset": "twitter", "seed": 42, "obs_ratio": 0.3, "config_id": "default-small"},
        {"dataset": "twitter", "seed": 43, "obs_ratio": 0.3, "config_id": "default-small"},
    ]


def test_original_fusion_normalizes_legacy_checkpoint_rows():
    row = {"model": "KT2JointModel", "dataset": "douban", "seed": 42, "obs_ratio": 0.3}

    normalized = normalize_row_identity(row)

    assert normalized["experiment_dataset"] == "douban"
    assert normalized["experiment_seed"] == 42
    assert normalized["experiment_obs_ratio"] == 0.3
    assert normalized["experiment_config_id"] == "default-small"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "legacy.json"
        out.write_text(json.dumps({"rows": [row]}), encoding="utf-8")
        loaded = load_existing_rows(out)

    assert loaded[0]["experiment_dataset"] == "douban"
    assert loaded[0]["experiment_config_id"] == "default-small"


def test_kt2_baseline_comparison_marks_small_runs_not_full_reproduction():
    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp)
        (bench / "results.json").write_text(
            json.dumps(
                [
                    {"model": "MINDS", "dataset": "christianity", "msle": 0.1, "hits@100": 0.5, "map@100": 0.2},
                    {"model": "FOREST", "dataset": "douban", "hits@100": 0.3, "map@100": 0.08},
                ]
            ),
            encoding="utf-8",
        )
        (bench / "casft_external_attempt.json").write_text(
            json.dumps(
                [
                    {
                        "model": "CasFT",
                        "dataset": "douban",
                        "task": "scale",
                        "status": "ok",
                        "reproduction_level": "frontier_reproduction_small_run",
                        "seed": 0,
                        "msle": 1.0,
                        "mae": 2.0,
                    }
                ]
            ),
            encoding="utf-8",
        )
        (bench / "kt2_original_fusion_experiment_small_matrix.json").write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "model": "KT2JointModel",
                            "dataset": "douban",
                            "task": "multi_scale",
                            "status": "ok",
                            "reproduction_level": "kt2_joint_model_small_run",
                            "msle": 1.0,
                            "mae": 2.0,
                            "hits@100": 0.3,
                            "map@100": 0.1,
                            "mrr": 0.2,
                            "macro_micro_consistency": 0.7,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        report = build_baseline_comparison(bench)

    assert report["schema"] == "cogguard.kt2.baseline_comparison.v1"
    assert report["status"] == "partial"
    kt2 = [row for row in report["rows"] if row["model"] == "KT2JointModel"][0]
    casft = [row for row in report["rows"] if row["model"] == "CasFT"][0]
    assert kt2["comparability"] == "fusion_small_matrix_not_full_protocol"
    assert casft["comparability"] == "frontier_small_run_not_full_protocol"
    assert "KT2JointModel: same-protocol full-run evidence missing" in report["missing_requirements"]
    assert "CasFT: same-protocol full-run evidence missing" in report["missing_requirements"]


def test_kt2_baseline_comparison_accepts_same_protocol_full_run_evidence():
    full_rows = [
        {
            "model": model,
            "dataset": "douban",
            "task": "multi_scale" if model in {"KT2JointModel", "MINDS", "FOREST"} else "scale",
            "status": "ok",
            "reproduction_level": "kt2_joint_model_full_run" if model == "KT2JointModel" else "frontier_reproduction_full_run",
            "seed": 7,
            "msle": 1.0,
            "mae": 2.0,
            "hits@100": 0.3,
            "map@100": 0.1,
            "mrr": 0.2,
            "macro_micro_consistency": 0.7,
        }
        for model in ("KT2JointModel", "MINDS", "FOREST", "CasFT")
    ]
    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp)
        (bench / "same_protocol_full_run_baselines.json").write_text(json.dumps(full_rows[1:]), encoding="utf-8")
        (bench / "kt2_original_fusion_full_run.json").write_text(json.dumps({"rows": [full_rows[0]]}), encoding="utf-8")

        report = build_baseline_comparison(bench)

    assert report["status"] == "ok"
    assert report["missing_requirements"] == []
    full_run_rows = [
        row
        for row in report["rows"]
        if row["comparability"] in {"same_protocol_full_run", "kt2_integrated_same_protocol_full_run"}
    ]
    assert {row["model"] for row in full_run_rows} == {"KT2JointModel", "MINDS", "FOREST", "CasFT"}


def test_kt2_baseline_comparison_requires_shared_full_run_dataset():
    full_rows = [
        {
            "model": model,
            "dataset": dataset,
            "task": "multi_scale" if model in {"KT2JointModel", "MINDS", "FOREST"} else "scale",
            "status": "ok",
            "reproduction_level": "kt2_joint_model_full_run" if model == "KT2JointModel" else "frontier_reproduction_full_run",
            "seed": 7,
            "msle": 1.0,
            "mae": 2.0,
            "hits@100": 0.3,
            "map@100": 0.1,
            "mrr": 0.2,
            "macro_micro_consistency": 0.7,
        }
        for model, dataset in (
            ("KT2JointModel", "douban"),
            ("MINDS", "christianity"),
            ("FOREST", "douban"),
            ("CasFT", "twitter"),
        )
    ]
    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp)
        (bench / "same_protocol_full_run_baselines.json").write_text(json.dumps(full_rows[1:]), encoding="utf-8")
        (bench / "kt2_original_fusion_full_run.json").write_text(json.dumps({"rows": [full_rows[0]]}), encoding="utf-8")

        report = build_baseline_comparison(bench)

    assert report["status"] == "partial"
    assert "All models: same-protocol full-run comparison has no shared dataset" in report["missing_requirements"]


def test_kt2_baseline_comparison_ignores_failed_row_metrics():
    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp)
        (bench / "same_protocol_full_run_baselines.json").write_text(
            json.dumps(
                [
                    {
                        "model": "CasFT",
                        "dataset": "douban",
                        "task": "scale",
                        "status": "preprocess_failed",
                        "reproduction_level": "frontier_reproduction_attempted",
                        "seed": 42,
                        "msle": 0.01,
                        "mae": 1.0,
                    }
                ]
            ),
            encoding="utf-8",
        )

        report = build_baseline_comparison(bench)

    casft = [row for row in report["rows"] if row["model"] == "CasFT"][0]
    assert casft["status_counts"] == {"preprocess_failed": 1}
    assert casft["metric_summary"] == {}


def test_same_protocol_full_run_template_is_not_completion_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp)
        payload = write_full_run_template(bench / "same_protocol_full_run_baselines.template.json", "douban", "full-run-preflight")
        report = build_baseline_comparison(bench)

    assert payload["status"] == "template_not_evidence"
    assert {row["model"] for row in payload["rows"]} == {"MINDS", "FOREST", "CasFT"}
    assert report["status"] == "partial"
    assert not report["rows"]


def test_same_protocol_full_run_baselines_aggregates_real_adapter_rows(monkeypatch):
    calls = []

    def fake_run_adapter(cmd, cwd, timeout, model, dataset, config_id, seed):
        calls.append((model, dataset, list(cmd)))
        status = "failed" if model == "CasFT" else "ok"
        return {
            "model": model,
            "dataset": dataset,
            "task": "scale" if model == "CasFT" else "multi_scale",
            "status": status,
            "reproduction_level": "frontier_reproduction_full_run" if status == "ok" else "frontier_reproduction_attempted",
            "seed": seed,
            "config_id": config_id,
            "msle": 1.0 if model != "FOREST" else None,
            "hits@100": 0.3 if model != "CasFT" else None,
            "map@100": 0.1 if model != "CasFT" else None,
            "note": "simulated adapter row",
        }

    def fake_prepare(_forest_dataset_dir, _minds_work_dir, dataset, _max_cascades):
        return {"status": "ok", "dataset_name": f"kt2_{dataset}", "path": "staged"}

    monkeypatch.setattr(same_protocol_baselines, "run_adapter", fake_run_adapter)
    monkeypatch.setattr(same_protocol_baselines, "prepare_minds_forest_dataset", fake_prepare)
    monkeypatch.setattr(same_protocol_baselines, "resolve_minds_work_dir", lambda _repo: Path("MINDS"))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = root / "same_protocol_full_run_baselines.json"
        forest = root / "forest-data"
        (forest / "douban").mkdir(parents=True)
        args = argparse.Namespace(
            datasets="douban",
            seeds="42",
            models="MINDS,FOREST,CasFT",
            forest_data_root=str(forest),
            minds_repo=str(root / "MINDS"),
            forest_repo=str(root / "FOREST"),
            casft_repo=str(root / "CasFT"),
            out=str(out),
            config_id="unit-full-run",
            python=sys.executable,
            device="cpu",
            timeout=1,
            obs_ratio=0.3,
            max_minds_cascades=10,
            minds_epochs=1,
            minds_batch_size=2,
            minds_emb_dim=8,
            minds_step_split=2,
            forest_epochs=1,
            forest_batch_size=2,
            forest_d_model=8,
            forest_max_train_batches=1,
            forest_max_eval_batches=1,
            forest_rl_epochs=0,
            forest_rl_max_batches=0,
            forest_rl_rollout_len=0,
            casft_dataset="auto",
            casft_max_events=10,
            casft_max_epoch=1,
            casft_observation_time=86400,
            casft_prediction_time=1296000,
            casft_interval_num=12,
            casft_timesteps=2,
        )

        payload = same_protocol_baselines.run_matrix(args, started=None)
        same_protocol_baselines.write_payload(args, payload["rows"], payload["failures"], started=None)
        written = json.loads(out.read_text(encoding="utf-8"))

    assert [call[0] for call in calls] == ["MINDS", "FOREST", "CasFT"]
    assert written["schema"] == "cogguard.kt2.same_protocol_full_run_baselines.v1"
    assert written["status"] == "partial"
    assert len(written["rows"]) == 3
    assert any(failure["model"] == "CasFT" for failure in written["failures"])


def test_kt2_minds_comparison_uses_trainable_pair_only(monkeypatch):
    calls = []

    def fake_minds(args, dataset, seed):
        calls.append(("MINDS", dataset, seed))
        return {
            "model": "MINDS",
            "dataset": dataset,
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "frontier_reproduction_full_run",
            "seed": seed,
            "config_id": args.config_id,
            "msle": 1.0,
            "hits@10": 0.1,
            "hits@50": 0.2,
            "hits@100": 0.3,
            "map@10": 0.05,
            "map@50": 0.06,
            "map@100": 0.07,
        }

    def fake_kt2(args, dataset, seed):
        calls.append(("KT2", dataset, seed))
        return _kt2_sequence_row(dataset, seed, args.config_id)

    monkeypatch.setattr(kt2_minds_comparison, "run_minds_baseline", fake_minds)
    monkeypatch.setattr(kt2_minds_comparison, "run_kt2_candidate", fake_kt2)
    with tempfile.TemporaryDirectory() as tmp:
        args = argparse.Namespace(
            datasets="douban,twitter",
            seeds="42",
            config_id="unit-kt2-vs-minds",
            out=str(Path(tmp) / "comparison.json"),
            minds_epochs=1,
            kt2_epochs=1,
            max_minds_cascades=10,
            kt2_max_train_cascades=4,
            kt2_max_test_cascades=4,
        )
        payload = kt2_minds_comparison.run_comparison(args)

    assert calls == [
        ("MINDS", "douban", 42),
        ("KT2", "douban", 42),
        ("MINDS", "twitter", 42),
        ("KT2", "twitter", 42),
    ]
    assert payload["status"] == "ok"
    assert payload["evidence_level"] == "preflight"
    assert payload["full_validation_passed"] is False
    assert payload["overall_verdict"] == "supports_kt2_improvement_on_all_completed_pairs"
    assert payload["schema_report"]["ok"] is True
    assert all(row["verdict"] == "supports_kt2_improvement" for row in payload["comparisons"])


def test_kt2_minds_comparison_marks_failed_pairs_incomplete():
    rows = [
        {
            "model": "MINDS",
            "dataset": "douban",
            "task": "multi_scale",
            "status": "failed",
            "reproduction_level": "frontier_reproduction_attempted",
            "seed": 42,
        },
        {
            "model": "KT2SequenceJointModel",
            "dataset": "douban",
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "kt2_sequence_joint_model_small_run",
            "seed": 42,
            "msle": 0.8,
            "mae": 1.0,
            "rmse": 1.0,
            "direction_accuracy": 0.5,
            "trend_mae": 1.0,
            "trend_rmse": 1.0,
            "candidate_recall_full": 0.4,
            "hits@10": 0.2,
            "hits@50": 0.3,
            "hits@100": 0.4,
            "map@10": 0.08,
            "map@50": 0.09,
            "map@100": 0.1,
            "mrr": 0.2,
            "macro_micro_consistency": 0.7,
            "macro_micro_soft_consistency": 0.7,
            "candidate_protocol_audit": {"leakage_check_passed": True, "future_nodes_injected": False},
            "note": "not an original MINDS FOREST CasFT reproduction",
            "methodology": "MINDS FOREST CasFT sequence migration",
            "legacy_boundary": "candidate-row legacy path excluded",
            "training_protocol": {
                "micro_target": "next_user_autoregressive_sampled_softmax",
                "candidate_features_used_as_model_input": False,
            },
        },
    ]
    args = argparse.Namespace(
        datasets="douban",
        seeds="42",
        config_id="unit",
        out="unused",
        minds_epochs=1,
        kt2_epochs=1,
        max_minds_cascades=10,
        kt2_max_train_cascades=4,
        kt2_max_test_cascades=4,
    )

    payload = kt2_minds_comparison.build_payload(args, rows, started=0.0)

    assert payload["status"] == "partial"
    assert payload["full_validation_passed"] is False
    assert payload["overall_verdict"] == "insufficient_evidence"
    assert payload["missing_pairs"] == [{"dataset": "douban", "seed": 42, "minds_status": "failed", "kt2_status": "ok"}]


def test_kt2_minds_comparison_full_validation_requires_scope():
    args = argparse.Namespace(
        datasets="douban,twitter,memetracker",
        seeds="1,2,3",
        config_id="unit-full-scope",
        out="unused",
        minds_epochs=5,
        kt2_epochs=5,
        max_minds_cascades=0,
        kt2_max_train_cascades=0,
        kt2_max_test_cascades=0,
    )
    rows = []
    for dataset in ["douban", "twitter", "memetracker"]:
        for seed in [1, 2, 3]:
            rows.append(
                {
                    "model": "MINDS",
                    "dataset": dataset,
                    "task": "multi_scale",
                    "status": "ok",
                    "reproduction_level": "frontier_reproduction_full_run",
                    "seed": seed,
                    "msle": 1.0,
                    "hits@100": 0.3,
                    "map@100": 0.1,
                }
            )
            rows.append(_kt2_sequence_row(dataset, seed, "unit-full-scope"))

    payload = kt2_minds_comparison.build_payload(args, rows, started=0.0)

    assert payload["evidence_level"] == "full_run_candidate"
    assert payload["full_validation_passed"] is True


def test_kt2_minds_comparison_budgeted_runs_are_not_full_validation():
    args = argparse.Namespace(
        datasets="douban,twitter,memetracker",
        seeds="1,2,3",
        config_id="unit-budgeted-scope",
        out="unused",
        minds_epochs=5,
        kt2_epochs=5,
        max_minds_cascades=0,
        kt2_max_train_cascades=0,
        kt2_max_test_cascades=0,
        kt2_max_steps_per_epoch=25,
        kt2_max_eval_cascades=100,
    )
    rows = []
    for dataset in ["douban", "twitter", "memetracker"]:
        for seed in [1, 2, 3]:
            rows.append(
                {
                    "model": "MINDS",
                    "dataset": dataset,
                    "task": "multi_scale",
                    "status": "ok",
                    "reproduction_level": "frontier_reproduction_full_run",
                    "seed": seed,
                    "msle": 1.0,
                    "hits@100": 0.3,
                    "map@100": 0.1,
                }
            )
            rows.append(_kt2_sequence_row(dataset, seed, "unit-budgeted-scope"))

    payload = kt2_minds_comparison.build_payload(args, rows, started=0.0)

    assert payload["evidence_level"] == "resource_bounded_full_source_candidate"
    assert payload["full_validation_passed"] is False
    assert payload["full_run_requirements"]["checks"]["kt2_unbudgeted_training_and_eval"] is False


def test_kt2_minds_comparison_resume_skips_completed_pair(monkeypatch):
    calls = []

    def fake_minds(args, dataset, seed):
        calls.append(("MINDS", dataset, seed))
        return {
            "model": "MINDS",
            "dataset": dataset,
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "frontier_reproduction_full_run",
            "seed": seed,
            "config_id": args.config_id,
            "msle": 1.0,
            "hits@100": 0.3,
            "map@100": 0.1,
        }

    def fake_kt2(args, dataset, seed):
        calls.append(("KT2", dataset, seed))
        return _kt2_sequence_row(dataset, seed, args.config_id)

    monkeypatch.setattr(kt2_minds_comparison, "run_minds_baseline", fake_minds)
    monkeypatch.setattr(kt2_minds_comparison, "run_kt2_candidate", fake_kt2)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "comparison.json"
        args = argparse.Namespace(
            datasets="douban,twitter",
            seeds="42",
            config_id="unit-resume",
            out=str(out),
            minds_epochs=1,
            kt2_epochs=1,
            max_minds_cascades=10,
            kt2_max_train_cascades=4,
            kt2_max_test_cascades=4,
            resume=False,
            max_pairs=1,
            models="MINDS,KT2SequenceJointModel",
        )
        first = kt2_minds_comparison.run_comparison(args)
        kt2_minds_comparison.write_payload(first, out)
        args.resume = True
        args.max_pairs = 0
        second = kt2_minds_comparison.run_comparison(args)

    assert calls == [
        ("MINDS", "douban", 42),
        ("KT2", "douban", 42),
        ("MINDS", "twitter", 42),
        ("KT2", "twitter", 42),
    ]
    assert second["status"] == "ok"
    assert len(second["comparisons"]) == 2


def test_kt2_minds_comparison_can_run_selected_model_subset(monkeypatch):
    calls = []

    def fake_minds(args, dataset, seed):
        calls.append(("MINDS", dataset, seed))
        return {
            "model": "MINDS",
            "dataset": dataset,
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "frontier_reproduction_full_run",
            "seed": seed,
            "msle": 1.0,
            "hits@100": 0.3,
            "map@100": 0.1,
        }

    def fail_kt2(_args, _dataset, _seed):
        raise AssertionError("KT2 should not run when --models=MINDS")

    monkeypatch.setattr(kt2_minds_comparison, "run_minds_baseline", fake_minds)
    monkeypatch.setattr(kt2_minds_comparison, "run_kt2_candidate", fail_kt2)
    with tempfile.TemporaryDirectory() as tmp:
        args = argparse.Namespace(
            datasets="douban",
            seeds="42",
            config_id="unit-subset",
            out=str(Path(tmp) / "comparison.json"),
            minds_epochs=1,
            kt2_epochs=1,
            max_minds_cascades=10,
            kt2_max_train_cascades=4,
            kt2_max_test_cascades=4,
            resume=False,
            max_pairs=0,
            models="MINDS",
        )
        payload = kt2_minds_comparison.run_comparison(args)

    assert calls == [("MINDS", "douban", 42)]
    assert payload["status"] == "partial"
    assert payload["missing_pairs"] == [{"dataset": "douban", "seed": 42, "minds_status": "ok", "kt2_status": None}]


def test_kt2_minds_comparison_rejects_handcrafted_models():
    args = argparse.Namespace(
        datasets="douban",
        seeds="42",
        config_id="unit-reject-handcrafted",
        out="unused",
        minds_epochs=1,
        kt2_epochs=1,
        max_minds_cascades=10,
        kt2_max_train_cascades=4,
        kt2_max_test_cascades=4,
        resume=False,
        max_pairs=0,
        models="MINDS,ProspectiveRanker",
    )

    with pytest.raises(ValueError, match="Handcrafted/heuristic baselines must stay outside this verdict"):
        kt2_minds_comparison.run_comparison(args)


def test_kt2_minds_comparison_filters_non_trainable_resume_rows():
    args = argparse.Namespace(
        datasets="douban",
        seeds="42",
        config_id="unit-filter",
        out="unused",
        minds_epochs=1,
        kt2_epochs=1,
        max_minds_cascades=10,
        kt2_max_train_cascades=4,
        kt2_max_test_cascades=4,
    )
    rows = [
        {
            "model": "MINDS",
            "dataset": "douban",
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "frontier_reproduction_full_run",
            "seed": 42,
            "msle": 1.0,
            "hits@100": 0.3,
            "map@100": 0.1,
        },
        _kt2_sequence_row("douban", 42, "unit-filter"),
        {
            "model": "KT2JointModel",
            "dataset": "douban",
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "kt2_joint_model_small_run",
            "seed": 42,
        },
        {
            "model": "ProspectiveRanker",
            "dataset": "douban",
            "task": "next_hop",
            "status": "ok",
            "reproduction_level": "local_baseline",
            "seed": 42,
            "hits@100": 0.9,
            "map@100": 0.9,
        },
    ]

    payload = kt2_minds_comparison.build_payload(args, rows, started=0.0)

    assert payload["status"] == "ok"
    assert [row["model"] for row in payload["rows"]] == ["MINDS", "KT2SequenceJointModel"]
    assert payload["comparison_model_filter"]["ignored_non_comparison_row_count"] == 2
    assert {row["model"] for row in payload["comparison_model_filter"]["ignored_non_comparison_rows"]} == {
        "KT2JointModel",
        "ProspectiveRanker",
    }
    assert payload["comparisons"][0]["metrics"]["hits@100"]["kt2"] == 0.4


def test_kt2_minds_resume_skips_existing_failed_model_row(monkeypatch):
    calls = []

    def fail_if_minds_reruns(_args, _dataset, _seed):
        raise AssertionError("existing timeout MINDS row should not rerun on resume")

    def fake_kt2(args, dataset, seed):
        calls.append(("KT2", dataset, seed))
        return _kt2_sequence_row(dataset, seed, args.config_id)

    monkeypatch.setattr(kt2_minds_comparison, "run_minds_baseline", fail_if_minds_reruns)
    monkeypatch.setattr(kt2_minds_comparison, "run_kt2_candidate", fake_kt2)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "comparison.json"
        out.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "model": "MINDS",
                            "dataset": "douban",
                            "task": "multi_scale",
                            "status": "timeout",
                            "reproduction_level": "frontier_reproduction_attempted",
                            "seed": 42,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(
            datasets="douban",
            seeds="42",
            config_id="unit-resume-failed",
            out=str(out),
            minds_epochs=1,
            kt2_epochs=1,
            max_minds_cascades=10,
            kt2_max_train_cascades=4,
            kt2_max_test_cascades=4,
            resume=True,
            max_pairs=0,
            models="MINDS,KT2SequenceJointModel",
        )
        payload = kt2_minds_comparison.run_comparison(args)

    assert calls == [("KT2", "douban", 42)]
    assert payload["status"] == "partial"
    assert payload["missing_pairs"] == [{"dataset": "douban", "seed": 42, "minds_status": "timeout", "kt2_status": "ok"}]


def test_kt2_minds_comparison_rejects_legacy_candidate_level_kt2():
    with pytest.raises(ValueError, match="KT2JointModel is legacy candidate-level ablation only"):
        kt2_minds_comparison.normalize_selected_models("MINDS,KT2JointModel")


def test_original_fusion_resume_does_not_skip_new_observation_ratio(monkeypatch):
    calls = []

    def fake_run_one(_args, dataset, seed, obs_ratio):
        calls.append((dataset, seed, obs_ratio))
        return {
            "model": "KT2JointModel",
            "dataset": dataset,
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "kt2_joint_model_small_run",
            "seed": seed,
            "obs_ratio": obs_ratio,
            "experiment_obs_ratio": obs_ratio,
            "experiment_config_id": "obs-sweep",
            "msle": 1.0,
            "mae": 2.0,
            "rmse": 3.0,
            "direction_accuracy": 0.5,
            "candidate_recall_full": 0.2,
            "hits@10": 0.1,
            "hits@50": 0.2,
            "hits@100": 0.3,
            "mrr": 0.4,
            "macro_micro_consistency": 0.5,
            "candidate_protocol_audit": {"leakage_check_passed": True},
            "note": "not an original MINDS FOREST CasFT reproduction",
            "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
            "minds_module_runtime_status": "original_module_forward_auxiliary",
            "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
            "casft_diffusion_status": "original_gaussian_diffusion_st",
            "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
        "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
            "joint_training": {
                "methodology": "not the original MINDS FOREST CasFT reproduction",
                "minds_module_alignment_loss_mean": 1.0,
                "forest_size_alignment_loss_mean": 2.0,
                "casft_spatiotemporal_alignment_loss_mean": 3.0,
                "original_component_distillation": "teacher signals from upstream components",
            },
        }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "fusion.json"
        monkeypatch.setattr(original_fusion_experiment, "run_one", fake_run_one)
        first = argparse.Namespace(
            datasets="douban",
            seeds="42",
            out=str(out),
            forest_data_root=str(Path(tmp)),
            resume=False,
            max_runs=0,
            obs_ratio=0.3,
            obs_ratios="0.3",
            config_id="obs-sweep",
        )
        original_fusion_experiment.run_experiment(first)
        second = argparse.Namespace(
            datasets="douban",
            seeds="42",
            out=str(out),
            forest_data_root=str(Path(tmp)),
            resume=True,
            max_runs=0,
            obs_ratio=0.3,
            obs_ratios="0.3,0.5",
            config_id="obs-sweep",
        )
        summary = original_fusion_experiment.run_experiment(second)

    assert calls == [("douban", 42, 0.3), ("douban", 42, 0.5)]
    assert summary["matrix_coverage"]["expected_runs"] == 2
    assert summary["matrix_coverage"]["completed_expected_runs"] == 2
    assert summary["matrix_coverage"]["pending_keys"] == []


def test_original_fusion_ablation_requires_all_research_variants(monkeypatch):
    def fake_run_kt2_joint_model(_data_dir, **kwargs):
        if kwargs.get("use_original_forest_components") and kwargs.get("use_original_casft_diffusion"):
            variant = "full_minds_forest_casft"
        elif kwargs.get("use_original_forest_components"):
            variant = "minds_plus_forest"
        elif kwargs.get("use_original_casft_diffusion"):
            variant = "minds_plus_casft"
        elif kwargs.get("use_original_minds_components"):
            variant = "minds_baseline"
        else:
            variant = "local_kt2_bridge"
        return {
            "model": "KT2JointModel",
            "dataset": "douban",
            "task": "multi_scale",
            "status": "ok",
            "reproduction_level": "kt2_joint_model_small_run",
            "obs_ratio": 0.3,
            "msle": 1.0 if variant != "full_minds_forest_casft" else 0.8,
            "mae": 2.0,
            "rmse": 3.0,
            "direction_accuracy": 0.5,
            "candidate_recall_full": 0.4,
            "hits@10": 0.1,
            "hits@50": 0.2,
            "hits@100": 0.3 if variant != "full_minds_forest_casft" else 0.4,
            "map@100": 0.05,
            "mrr": 0.06,
            "macro_micro_consistency": 0.7,
            "candidate_protocol_audit": {"leakage_check_passed": True},
            "note": "not an original MINDS FOREST CasFT reproduction",
            "minds_component_status": (
                "original_dynamic_cas_hgnn_fusion_shared_lstm"
                if kwargs.get("use_original_minds_components")
                else "disabled"
            ),
            "minds_module_runtime_status": (
                "original_module_forward_auxiliary"
                if kwargs.get("use_original_minds_full_module")
                else "disabled"
            ),
            "forest_runtime_status": (
                "original_rnnmodel_rrmodel_auxiliary"
                if kwargs.get("use_original_forest_components")
                else "disabled"
            ),
            "casft_diffusion_status": (
                "original_gaussian_diffusion_st"
                if kwargs.get("use_original_casft_diffusion")
                else "disabled"
            ),
            "casft_spatiotemporal_runtime_status": (
                "original_combined_spatiotemporal_model5_auxiliary"
                if kwargs.get("use_original_casft_spatiotemporal")
                else "disabled"
            ),
            "casft_spatiotemporal_fusion_status": (
                "original_combined_spatiotemporal_model5_main_fused"
                if kwargs.get("use_original_casft_spatiotemporal")
                else "disabled"
            ),
            "joint_training": {
                "methodology": "not an original MINDS FOREST CasFT reproduction",
                "minds_module_alignment_loss_mean": 1.0 if kwargs.get("use_original_minds_full_module") else 0.0,
                "forest_size_alignment_loss_mean": 2.0 if kwargs.get("use_original_forest_components") else 0.0,
                "casft_spatiotemporal_alignment_loss_mean": 3.0 if kwargs.get("use_original_casft_spatiotemporal") else 0.0,
                "original_component_distillation": "teacher signals from upstream MINDS, FOREST, and CasFT components",
            },
        }

    import benchmark.kt2_original_fusion_ablation as ablation_module

    monkeypatch.setattr(ablation_module, "run_kt2_joint_model", fake_run_kt2_joint_model)
    with tempfile.TemporaryDirectory() as tmp:
        args = argparse.Namespace(
            datasets="douban",
            seeds="42",
            forest_data_root=str(Path(tmp)),
            minds_repo=str(Path(tmp) / "MINDS"),
            forest_repo=str(Path(tmp) / "FOREST"),
            casft_repo=str(Path(tmp) / "CasFT"),
            obs_ratio=0.3,
            obs_ratios="",
            variants=",".join(ORIGINAL_FUSION_ABLATION_VARIANTS),
            max_future_per_cascade=20,
            global_top_n=50,
            max_candidates=50,
            negatives_per_cascade=8,
            epochs=1,
            batch_size=8,
            hidden_dim=16,
            max_train_cascades=4,
            max_test_cascades=4,
            max_sequence_len=8,
            lambda_original_minds_module=0.01,
            lambda_consistency=0.2,
            lambda_forest_pg=0.02,
            forest_pg_rollout_samples=1,
            lambda_original_forest_ce=0.02,
            lambda_original_forest_rl=0.001,
            original_forest_rollout_samples=1,
            original_forest_start_size=3,
            lambda_trend=0.4,
            lambda_diffusion=0.05,
            lambda_original_casft_spatiotemporal=0.01,
            casft_diffusion_timesteps=2,
            casft_sampling_timesteps=1,
            casft_spatiotemporal_interval_num=4,
            casft_spatiotemporal_tpp_hdim=16,
            device="cpu",
            out=str(Path(tmp) / "ablation.json"),
            config_id="unit-ablation",
            resume=False,
            max_runs=0,
        )
        summary = run_original_fusion_ablation(args)

    assert summary["status"] == "ok"
    assert summary["matrix_coverage"]["coverage_ratio"] == 1.0
    assert {row["ablation_variant"] for row in summary["rows"]} == set(ORIGINAL_FUSION_ABLATION_VARIANTS)
    assert summary["original_subpath_status"]["all_full_variant_original_subpaths_passed"] is True
    assert summary["original_subpath_status"]["all_full_variant_alignment_losses_recorded"] is True
    assert summary["full_vs_minds_baseline_delta"]["msle"]["better_direction_delta"] > 0
    assert summary["full_vs_minds_baseline_delta"]["hits@100"]["better_direction_delta"] > 0


def test_original_fusion_gate_keeps_small_run_incomplete_until_full_run_and_ablation():
    row = {
        "model": "KT2JointModel",
        "dataset": "douban",
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "kt2_joint_model_small_run",
        "obs_ratio": 0.3,
        "msle": 1.0,
        "mae": 2.0,
        "rmse": 3.0,
        "direction_accuracy": 0.5,
        "candidate_recall_full": 0.4,
        "hits@100": 0.3,
        "map@100": 0.05,
        "mrr": 0.06,
        "macro_micro_consistency": 0.7,
        "candidate_protocol_audit": {"leakage_check_passed": True},
        "note": "not an original MINDS FOREST CasFT reproduction",
        "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
        "minds_module_runtime_status": "original_module_forward_auxiliary",
        "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
        "casft_diffusion_status": "original_gaussian_diffusion_st",
        "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
        "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
        "joint_training": {
            "methodology": "not an original MINDS FOREST CasFT reproduction",
            "minds_module_alignment_loss_mean": 1.0,
            "forest_size_alignment_loss_mean": 2.0,
            "casft_spatiotemporal_alignment_loss_mean": 3.0,
        },
    }
    small_matrix = {
        "original_subpath_audit": {
            "all_original_subpaths_passed": True,
            "all_alignment_losses_recorded": True,
        },
        "matrix_coverage": {"coverage_ratio": 1.0},
        "rows": [
            {
                **row,
                "experiment_dataset": dataset,
                "experiment_seed": seed,
                "experiment_obs_ratio": obs_ratio,
            }
            for dataset in ("douban", "twitter", "memetracker")
            for seed in (42, 43, 44)
            for obs_ratio in (0.1, 0.3, 0.5)
        ],
    }
    ablation_rows = [
        {
            **row,
            "ablation_variant": variant,
            "experiment_dataset": "douban",
            "experiment_seed": 42,
            "experiment_obs_ratio": 0.3,
        }
        for variant in ORIGINAL_FUSION_ABLATION_VARIANTS
    ]
    ablation = {
        "rows": ablation_rows,
        "original_subpath_status": {
            "all_full_variant_original_subpaths_passed": True,
            "all_full_variant_alignment_losses_recorded": True,
        },
        "full_vs_minds_baseline_delta": {"msle": {"better_direction_delta": 0.1}},
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        small = root / "small.json"
        abl = root / "ablation.json"
        cmp = root / "comparison.json"
        small.write_text(json.dumps(small_matrix), encoding="utf-8")
        abl.write_text(json.dumps(ablation), encoding="utf-8")
        cmp.write_text(json.dumps({"status": "partial", "missing_requirements": ["full-run missing"]}), encoding="utf-8")
        gate = build_original_fusion_gate(
            small_matrix_path=small,
            ablation_path=abl,
            baseline_comparison_path=cmp,
            min_datasets=3,
            min_seeds=3,
            min_obs_ratios=3,
        )

    assert gate["status"] == "incomplete"
    assert "not complete" in gate["claim"]
    by_id = {check["id"]: check for check in gate["checks"]}
    assert by_id["original_subpaths_and_teacher_alignment"]["status"] == "passed"
    assert by_id["small_matrix_coverage"]["status"] == "passed"
    assert by_id["same_protocol_component_ablation"]["status"] == "passed"
    assert by_id["same_protocol_full_run_claimability"]["status"] == "partial"


def test_original_fusion_gate_counts_kt2_full_run_from_baseline_comparison():
    base_row = {
        "model": "KT2JointModel",
        "dataset": "douban",
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "kt2_joint_model_small_run",
        "obs_ratio": 0.3,
        "msle": 1.0,
        "mae": 2.0,
        "rmse": 3.0,
        "direction_accuracy": 0.5,
        "candidate_recall_full": 0.4,
        "hits@100": 0.3,
        "map@100": 0.05,
        "mrr": 0.06,
        "macro_micro_consistency": 0.7,
        "candidate_protocol_audit": {"leakage_check_passed": True},
        "note": "not an original MINDS FOREST CasFT reproduction",
        "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
        "minds_module_runtime_status": "original_module_forward_auxiliary",
        "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
        "casft_diffusion_status": "original_gaussian_diffusion_st",
        "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
        "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
        "joint_training": {
            "methodology": "not an original MINDS FOREST CasFT reproduction",
            "minds_module_alignment_loss_mean": 1.0,
            "forest_size_alignment_loss_mean": 2.0,
            "casft_spatiotemporal_alignment_loss_mean": 3.0,
        },
    }
    small_matrix = {
        "original_subpath_audit": {
            "all_original_subpaths_passed": True,
            "all_alignment_losses_recorded": True,
        },
        "matrix_coverage": {"coverage_ratio": 1.0},
        "rows": [
            {
                **base_row,
                "experiment_dataset": dataset,
                "experiment_seed": seed,
                "experiment_obs_ratio": obs_ratio,
            }
            for dataset in ("douban", "twitter", "memetracker")
            for seed in (42, 43, 44)
            for obs_ratio in (0.1, 0.3, 0.5)
        ],
    }
    ablation = {
        "rows": [{**base_row, "ablation_variant": variant} for variant in ORIGINAL_FUSION_ABLATION_VARIANTS],
        "original_subpath_status": {
            "all_full_variant_original_subpaths_passed": True,
            "all_full_variant_alignment_losses_recorded": True,
        },
        "full_vs_minds_baseline_delta": {"msle": {"better_direction_delta": 0.1}},
    }
    comparison = {
        "status": "partial",
        "missing_requirements": ["MINDS: same-protocol full-run evidence missing"],
        "rows": [
            {
                "model": "KT2JointModel",
                "dataset": "douban",
                "task": "multi_scale",
                "reproduction_level": "kt2_joint_model_full_run",
                "comparability": "kt2_integrated_same_protocol_full_run",
                "runs": 1,
                "status_counts": {"ok": 1},
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        small = root / "small.json"
        abl = root / "ablation.json"
        cmp = root / "comparison.json"
        small.write_text(json.dumps(small_matrix), encoding="utf-8")
        abl.write_text(json.dumps(ablation), encoding="utf-8")
        cmp.write_text(json.dumps(comparison), encoding="utf-8")
        gate = build_original_fusion_gate(
            small_matrix_path=small,
            ablation_path=abl,
            baseline_comparison_path=cmp,
            min_datasets=3,
            min_seeds=3,
            min_obs_ratios=3,
        )

    by_id = {check["id"]: check for check in gate["checks"]}
    assert by_id["same_protocol_full_run_claimability"]["full_run_rows"] == 1
    assert by_id["same_protocol_full_run_claimability"]["status"] == "partial"


def test_original_fusion_gate_flags_metric_explosions():
    row = {
        "model": "KT2JointModel",
        "dataset": "twitter",
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "kt2_joint_model_small_run",
        "obs_ratio": 0.5,
        "msle": 570.0,
        "mae": 1_000_000.0,
        "rmse": 2_000_000.0,
        "direction_accuracy": 0.5,
        "candidate_recall_full": 0.4,
        "hits@100": 0.3,
        "map@100": 0.05,
        "mrr": 0.06,
        "macro_micro_consistency": 0.7,
        "candidate_protocol_audit": {"leakage_check_passed": True},
        "note": "not an original MINDS FOREST CasFT reproduction",
        "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
        "minds_module_runtime_status": "original_module_forward_auxiliary",
        "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
        "casft_diffusion_status": "original_gaussian_diffusion_st",
        "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
        "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
        "joint_training": {
            "methodology": "not an original MINDS FOREST CasFT reproduction",
            "minds_module_alignment_loss_mean": 1.0,
            "forest_size_alignment_loss_mean": 2.0,
            "casft_spatiotemporal_alignment_loss_mean": 3.0,
        },
    }
    small_matrix = {
        "original_subpath_audit": {
            "all_original_subpaths_passed": True,
            "all_alignment_losses_recorded": True,
        },
        "matrix_coverage": {"coverage_ratio": 1.0},
        "rows": [
            {
                **row,
                "experiment_dataset": dataset,
                "experiment_seed": seed,
                "experiment_obs_ratio": obs_ratio,
            }
            for dataset in ("douban", "twitter", "memetracker")
            for seed in (42, 43, 44)
            for obs_ratio in (0.1, 0.3, 0.5)
        ],
    }
    ablation = {
        "rows": [{**row, "ablation_variant": variant} for variant in ORIGINAL_FUSION_ABLATION_VARIANTS],
        "original_subpath_status": {
            "all_full_variant_original_subpaths_passed": True,
            "all_full_variant_alignment_losses_recorded": True,
        },
        "full_vs_minds_baseline_delta": {"msle": {"better_direction_delta": 0.1}},
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        small = root / "small.json"
        abl = root / "ablation.json"
        cmp = root / "comparison.json"
        small.write_text(json.dumps(small_matrix), encoding="utf-8")
        abl.write_text(json.dumps(ablation), encoding="utf-8")
        cmp.write_text(json.dumps({"status": "partial", "missing_requirements": ["full-run missing"]}), encoding="utf-8")
        gate = build_original_fusion_gate(
            small_matrix_path=small,
            ablation_path=abl,
            baseline_comparison_path=cmp,
            min_datasets=3,
            min_seeds=3,
            min_obs_ratios=3,
        )

    by_id = {check["id"]: check for check in gate["checks"]}
    assert by_id["small_matrix_metric_stability"]["status"] == "partial"
    assert by_id["small_matrix_metric_stability"]["failures"]
    assert any("Stabilize abnormal small-matrix metric rows" in action for action in gate["required_next_actions"])


def test_forest_rl_result_schema_accepts_public_code_adapter_metadata():
    row = {
        "model": "FOREST",
        "dataset": "douban",
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "public_code_adapter",
        "epochs": 1,
        "rl_epochs": 1,
        "hits@10": 0.1,
        "hits@50": 0.2,
        "hits@100": 0.3,
        "map@10": 0.05,
        "map@50": 0.06,
        "map@100": 0.07,
        "forest_rl": {
            "enabled": True,
            "rl_epochs": 1,
            "start_size": 5,
            "rollout_len": 32,
            "train_rewards": [-1.0],
            "test_reward": -1.1,
            "reward_definition": "-square(log(predicted_eos_position)-log(true_eos_position))",
            "policy_loss": "-sum(sampled_step_log_probs) * centered_macro_reward",
        },
    }
    schema = validate_benchmark_results([row])

    assert schema["ok"] is True


def test_coordination_scope_filters_role_evidence_and_protocol_export():
    events = make_synthetic_events()
    scope = CoordinationScope(users={"u0", "u7"}, groups={"u0": "g1"})
    evidence = role_evidence_table(events[0], scope)
    assert not evidence.empty
    assert set(evidence["user_id"]).issubset({"u0", "u7"})
    assert evidence["is_coordinated"].all()

    with tempfile.TemporaryDirectory() as tmp:
        path = export_standard_cascades(events[:1], tmp, scope, t_obs=0.3, split="unit")
        data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "cogguard.kt2.standard_cascade.v1"
    assert data["protocol"]["t_obs"] == 0.3
    assert {"event_id", "nodes", "edges"}.issubset(data["events"][0])
    assert any(node["is_coordinated"] for node in data["events"][0]["nodes"])

    with tempfile.TemporaryDirectory() as tmp:
        summary = analyze_events(events[:2], tmp, coordination=scope)
        quality_path = Path(tmp) / "role_evidence_quality.json"
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert quality_path.name == "role_evidence_quality.json"
    assert summary["role_evidence_quality"]["scope"] == "coordinated_users"
    assert quality["target_user_count"] == 2
    assert 0 <= quality["coordination_user_coverage"] <= 1
    assert 0 <= quality["path_complete_rate"] <= 1
    assert "role_stability" in quality


def test_load_coordination_scope_from_json_records():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "coord.json"
        path.write_text(json.dumps({"records": [{"user_id": "u1", "group_id": "g1"}, {"uid": "u2"}]}), encoding="utf-8")
        scope = load_coordination_scope(str(path))
    assert scope.users == {"u1", "u2"}
    assert scope.groups["u1"] == "g1"


def test_kt1_coordination_adapter_generates_role_evidence_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        predictions = root / "predictions.csv"
        predictions.write_text(
            "\n".join(
                [
                    "account_id,label,predicted_label,node_score,cluster_id",
                    "u1,1,1,0.99,0",
                    "u2,1,1,0.95,0",
                    "u3,0,0,0.01,1",
                ]
            ),
            encoding="utf-8",
        )
        adapter = convert_kt1_predictions(predictions, root / "coord")
        validation = run_kt1_role_evidence_validation(predictions, root / "validation", max_events=2)
        scope = load_coordination_scope(adapter["coordination_file"])

    assert scope.users == {"u1", "u2"}
    assert validation["status"] == "ok"
    assert validation["selected_user_count"] == 2
    assert validation["role_evidence_rows"] > 0
    assert validation["role_evidence_quality"]["scope"] == "coordinated_users"


def test_role_evidence_review_template_does_not_prefill_pass_column():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        predictions = root / "predictions.csv"
        predictions.write_text(
            "\n".join(
                [
                    "account_id,label,predicted_label,node_score,cluster_id",
                    "u1,1,1,0.99,0",
                    "u2,1,1,0.95,0",
                ]
            ),
            encoding="utf-8",
        )
        validation = run_kt1_role_evidence_validation(predictions, root / "validation", max_events=2)
        output = root / "validation" / "analysis" / "role_evidence_manual_review_template.csv"
        summary = generate_review_template(validation["role_evidence_csv"], output, sample_size=3, per_role=2, seed=7)
        guide = output.parent / "ROLE_EVIDENCE_REVIEW_GUIDE.md"
        packet = output.parent / "ROLE_EVIDENCE_REVIEW_PACKET.md"
        html_page = output.parent / "ROLE_EVIDENCE_REVIEW.html"

        with output.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(__import__("csv").DictReader(handle))
        validation_summary = validate_review_file(output, template_csv=output)
        guide_exists = guide.exists()
        packet_text = packet.read_text(encoding="utf-8")
        html_text = html_page.read_text(encoding="utf-8")
        filled_review_exists = output.with_name("role_evidence_manual_review.csv").exists()

    assert summary["rows_sampled"] == len(rows)
    assert summary["review_pass_prefilled"] is False
    assert guide_exists
    assert summary["packet"].endswith("ROLE_EVIDENCE_REVIEW_PACKET.md")
    assert summary["html"].endswith("ROLE_EVIDENCE_REVIEW.html")
    assert "role_evidence_manual_review_template.csv" in packet_text
    assert "evidence_match" in packet_text
    assert "<!doctype html>" in html_text.lower()
    assert "role_evidence_manual_review.csv" in html_text
    assert "downloadCsv" in html_text
    assert "generateCsv" in html_text
    assert "role_evidence_manual_review.csv" in html_text
    assert filled_review_exists is False
    assert rows
    assert {"event_id", "user_id", "role", "evidence_paths", "review_pass", "reviewer_note"}.issubset(rows[0])
    assert all(row["review_pass"] == "" for row in rows)
    assert validation_summary["ok"] is False
    assert "blank review_pass" in validation_summary["detail"] or "no recognized pass/fail" in validation_summary["detail"]


def test_role_evidence_review_init_creates_fillable_csv_without_prefilling():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        role_evidence = root / "role_evidence.csv"
        role_evidence.write_text(
            "\n".join(
                [
                    "event_id,user_id,coord_group_id,is_coordinated,role,evidence_summary,node_ids,evidence_paths,first_evidence_node,first_seen,out_degree_sum,betweenness_sum,pagerank_sum,post_count",
                    "e1,u1,g1,True,妗ユ帴,bridge evidence,['1'],\"[['0','1']]\",1,2024-01-01,1,0.2,0.1,1",
                ]
            ),
            encoding="utf-8",
        )
        template = root / "role_evidence_manual_review_template.csv"
        review = root / "role_evidence_manual_review.csv"
        generate_review_template(role_evidence, template, sample_size=1, per_role=1, seed=0)
        init_summary = init_review_file(template, review)
        with review.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(__import__("csv").DictReader(handle))

    assert init_summary["ok"] is True
    assert init_summary["review_pass_prefilled"] is False
    assert len(rows) == 1
    assert rows[0]["review_pass"] == ""


def test_role_evidence_review_validation_accepts_filled_review_file():
    with tempfile.TemporaryDirectory() as tmp:
        review = Path(tmp) / "role_evidence_manual_review.csv"
        review.write_text(
            "\n".join(
                [
                    "event_id,user_id,role,evidence_paths,review_pass,reviewer,evidence_match,confidence_1to5,reason_if_fail,reviewer_note",
                    "e1,u1,妗ユ帴,\"[['0','1']]\",true,r1,yes,5,,path and role match",
                    "e2,u2,璧风垎/婧愬ご,\"[['0','2']]\",pass,r1,yes,4,,source path match",
                    "e3,u3,鏅€氬弬涓庤€?\"[['0','3']]\",false,r1,no,3,role evidence is weak,weak evidence",
                ]
            ),
            encoding="utf-8",
        )
        summary = validate_review_file(review, min_pass_rate=0.6)

    assert summary["ok"] is True
    assert summary["rows"] == 3
    assert summary["reviewed_rows"] == 3
    assert summary["passed_rows"] == 2


def test_role_evidence_review_validation_rejects_missing_reviewer_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        review = Path(tmp) / "role_evidence_manual_review.csv"
        review.write_text(
            "\n".join(
                [
                    "event_id,user_id,role,evidence_paths,review_pass,reviewer,evidence_match,confidence_1to5,reason_if_fail,reviewer_note",
                    "e1,u1,妗ユ帴,\"[['0','1']]\",true,,yes,5,,missing reviewer",
                ]
            ),
            encoding="utf-8",
        )
        summary = validate_review_file(review)

    assert summary["ok"] is False
    assert summary["reviewed_rows"] == 1
    assert summary["incomplete_metadata"][0]["issue"] == "missing reviewer"
    assert "incomplete reviewer metadata" in summary["detail"]


def test_role_evidence_review_status_reports_missing_filled_review_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        role_evidence = root / "role_evidence.csv"
        role_evidence.write_text(
            "\n".join(
                [
                    "event_id,user_id,coord_group_id,is_coordinated,role,evidence_summary,node_ids,evidence_paths,first_evidence_node,first_seen,out_degree_sum,betweenness_sum,pagerank_sum,post_count",
                    "e1,u1,g1,True,妗ユ帴,bridge evidence,['1'],\"[['0','1']]\",1,2024-01-01,1,0.2,0.1,1",
                ]
            ),
            encoding="utf-8",
        )
        template = root / "role_evidence_manual_review_template.csv"
        review = root / "role_evidence_manual_review.csv"
        generate_review_template(role_evidence, template, sample_size=1, per_role=1, seed=0)
        status = review_status(role_evidence_csv=role_evidence, template_csv=template, review_csv=review)

    assert status["ok"] is False
    assert status["packet_ready"] is True
    assert status["template_ready"] is True
    assert status["review_validation"]["detail"] == "manual review CSV does not exist"
    assert "Initialize" in status["next_action"]


def test_role_evidence_review_status_reports_blank_initialized_review_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        role_evidence = root / "role_evidence.csv"
        role_evidence.write_text(
            "\n".join(
                [
                    "event_id,user_id,coord_group_id,is_coordinated,role,evidence_summary,node_ids,evidence_paths,first_evidence_node,first_seen,out_degree_sum,betweenness_sum,pagerank_sum,post_count",
                    "e1,u1,g1,True,妗ユ帴,bridge evidence,['1'],\"[['0','1']]\",1,2024-01-01,1,0.2,0.1,1",
                ]
            ),
            encoding="utf-8",
        )
        template = root / "role_evidence_manual_review_template.csv"
        review = root / "role_evidence_manual_review.csv"
        generate_review_template(role_evidence, template, sample_size=1, per_role=1, seed=0)
        init_review_file(template, review)
        status = review_status(role_evidence_csv=role_evidence, template_csv=template, review_csv=review)

    assert status["ok"] is False
    assert status["review_validation"]["blank_rows"] == 1
    assert "Fill all sampled review_pass values" in status["next_action"]
    assert "confidence_1to5" in status["next_action"]
    assert "1/1" not in status["next_action"]
    assert "0/1" in status["next_action"]


def test_role_evidence_review_status_passes_when_filled_review_is_valid():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        role_evidence = root / "role_evidence.csv"
        role_evidence.write_text(
            "\n".join(
                [
                    "event_id,user_id,coord_group_id,is_coordinated,role,evidence_summary,node_ids,evidence_paths,first_evidence_node,first_seen,out_degree_sum,betweenness_sum,pagerank_sum,post_count",
                    "e1,u1,g1,True,妗ユ帴,bridge evidence,['1'],\"[['0','1']]\",1,2024-01-01,1,0.2,0.1,1",
                ]
            ),
            encoding="utf-8",
        )
        template = root / "role_evidence_manual_review_template.csv"
        review = root / "role_evidence_manual_review.csv"
        generate_review_template(role_evidence, template, sample_size=1, per_role=1, seed=0)
        review.write_text(
            "event_id,user_id,coord_group_id,is_coordinated,role,evidence_summary,node_ids,evidence_paths,first_evidence_node,first_seen,out_degree_sum,betweenness_sum,pagerank_sum,post_count,reviewer,review_pass,evidence_match,confidence_1to5,review_timestamp,reason_if_fail,reviewer_note\n"
            "e1,u1,g1,True,妗ユ帴,bridge evidence,['1'],\"[['0','1']]\",1,2024-01-01,1,0.2,0.1,1,r1,true,yes,5,2026-01-01,,path supports bridge role\n",
            encoding="utf-8",
        )
        status = review_status(role_evidence_csv=role_evidence, template_csv=template, review_csv=review)

    assert status["ok"] is True
    assert status["review_validation"]["ok"] is True
    assert status["review_validation"]["pass_rate"] == 1.0
    assert "completion_gate" in status["next_action"]


def test_role_evidence_review_status_rejects_partial_review_file_against_template():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        role_evidence = root / "role_evidence.csv"
        role_evidence.write_text(
            "\n".join(
                [
                    "event_id,user_id,coord_group_id,is_coordinated,role,evidence_summary,node_ids,evidence_paths,first_evidence_node,first_seen,out_degree_sum,betweenness_sum,pagerank_sum,post_count",
                    "e1,u1,g1,True,妗ユ帴,bridge evidence,['1'],\"[['0','1']]\",1,2024-01-01,1,0.2,0.1,1",
                    "e2,u2,g1,True,璧风垎/婧愬ご,source evidence,['2'],\"[['0','2']]\",2,2024-01-02,2,0.3,0.2,1",
                ]
            ),
            encoding="utf-8",
        )
        template = root / "role_evidence_manual_review_template.csv"
        review = root / "role_evidence_manual_review.csv"
        generate_review_template(role_evidence, template, sample_size=2, per_role=2, seed=0)
        review.write_text(
            "event_id,user_id,role,first_evidence_node,first_seen,review_pass\n"
            "e1,u1,妗ユ帴,1,2024-01-01,true\n",
            encoding="utf-8",
        )
        status = review_status(role_evidence_csv=role_evidence, template_csv=template, review_csv=review)

    assert status["ok"] is False
    assert status["review_validation"]["template_check"]["ok"] is False
    assert "row count" in status["review_validation"]["detail"]


def test_frontier_reproduction_status_does_not_claim_completion():
    status = external_reproduction_status("CasFT", "weibo", None, "scale")
    assert status["status"] == "missing_external_repo"
    assert status["reproduction_level"] == "not_run"
    assert status["is_frontier_target"] is True


def test_casft_frontier_adapter_exports_without_claiming_reproduction():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        forest = _write_forest_fixture(root / "FOREST", "douban")
        casft = root / "CasFT"
        casft.mkdir()

        result = run_casft_frontier(
            "douban",
            str(forest),
            str(casft),
            sys.executable,
            str(root / "exports"),
            max_events=10,
            obs_ratio=0.5,
            timeout=30,
            run_external=False,
            casft_dataset="twitter",
            observation_time=86400,
            prediction_time=1296000,
            max_epoch=1,
        )
        exported = Path(result["casft_dataset_txt"])
        assert exported.exists()

    assert result["status"] == "protocol_export_only"
    assert result["reproduction_level"] == "frontier_data_adapter_ready_not_model_run"
    assert exported.name == "dataset.txt"
    assert "CasFT repository/data adapter is available" in result["note"]


def test_forest_to_casft_dataset_rescales_sparse_times_for_observation_filter():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_dir = root / "forest" / "data" / "douban"
        data_dir.mkdir(parents=True)
        sparse_cascade = " ".join(f"{idx},{idx * 1000000}" for idx in range(1, 16))
        (data_dir / "cascade.txt").write_text(sparse_cascade + "\n", encoding="utf-8")
        (data_dir / "cascadevalid.txt").write_text("", encoding="utf-8")
        (data_dir / "cascadetest.txt").write_text("", encoding="utf-8")

        exported = forest_to_casft_dataset(
            data_dir,
            root / "casft_export",
            observation_time=86400,
            prediction_time=1296000,
            obs_ratio=0.3,
        )
        line = exported.read_text(encoding="utf-8").strip()
        times = [int(item.rsplit(":", 1)[1]) for item in line.split("\t")[4].split()]

    assert len([value for value in times if value < 86400]) >= 10
    assert times == sorted(times)
    assert times[-1] < 1296000


def test_forest_split_loader_accepts_float_timestamps():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        (data_dir / "cascade.txt").write_text("1,0.1 2,0.2 3,0.3 4,0.4\n", encoding="utf-8")
        (data_dir / "cascadevalid.txt").write_text("1,1.1 2,1.2 3,1.3 4,1.4\n", encoding="utf-8")
        (data_dir / "cascadetest.txt").write_text("4,2.4 3,2.3 2,2.2 1,2.1\n", encoding="utf-8")

        train, valid, test = load_forest_split(data_dir)

    assert len(train) == 1
    assert len(valid) == 1
    assert len(test) == 1
    assert train[0][0] == (1, 100)
    assert test[0] == [(1, 2100), (2, 2200), (3, 2300), (4, 2400)]


def test_minds_runner_memory_optimized_mask_and_topk_match_legacy_metric():
    minds_work = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS\.kt2_extracted\MINDS")
    if not minds_work.exists():
        pytest.skip("MINDS extracted workdir is not available")
    sys.path.insert(0, str(minds_work))
    try:
        import Constants
        import torch
        from Metrics import compute_metric
        from benchmark.adapters.minds_runner import mask_previous_users_, update_topk_scores_from_logits

        def legacy_mask(seq, user_size):
            prev_shape = (seq.size(0), seq.size(1), seq.size(1))
            seqs = seq.repeat(1, 1, seq.size(1)).view(seq.size(0), seq.size(1), seq.size(1))
            previous_mask = np.tril(np.ones(prev_shape)).astype("float32")
            masked_seq = torch.from_numpy(previous_mask) * seqs.data.float()
            masked_seq = torch.cat([masked_seq, torch.zeros(seq.size(0), seq.size(1), 1)], dim=2)
            ans_tmp = torch.zeros(seq.size(0), seq.size(1), user_size)
            return ans_tmp.scatter_(2, masked_seq.long(), float("-inf"))

        seq = torch.tensor([[2, 3, 0, 4], [5, 5, 6, 0]], dtype=torch.long)
        logits = torch.randn(2, 4, 8)
        old_masked = logits + legacy_mask(seq, 8)
        new_masked = mask_previous_users_(logits.clone(), seq)
        assert torch.equal(torch.isinf(old_masked), torch.isinf(new_masked))

        y_pred = torch.randn(20, 12)
        gold = torch.tensor([2, 3, Constants.PAD, 5, 6, 7, 8, 9, 10, 11, 1, 2, 3, 4, 5, 6, Constants.PAD, 7, 8, 9])
        legacy_scores, legacy_count = compute_metric(y_pred.numpy(), gold.numpy(), [1, 5, 10])
        scores = {f"hits@{k}": 0.0 for k in [1, 5, 10]}
        scores.update({f"map@{k}": 0.0 for k in [1, 5, 10]})
        count = update_topk_scores_from_logits(scores, y_pred, gold, [1, 5, 10])
        for k in [1, 5, 10]:
            scores[f"hits@{k}"] /= count
            scores[f"map@{k}"] /= count

        assert count == legacy_count
        for key, value in legacy_scores.items():
            assert scores[key] == pytest.approx(float(value), abs=1e-6)
    finally:
        try:
            sys.path.remove(str(minds_work))
        except ValueError:
            pass


def test_casft_external_attempt_stages_generated_data_without_claiming_small_run():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        forest = _write_forest_fixture(root / "FOREST", "douban")
        casft = root / "CasFT"
        casft.mkdir()

        result = run_casft_frontier(
            "douban",
            str(forest),
            str(casft),
            sys.executable,
            str(root / "exports"),
            max_events=10,
            obs_ratio=0.5,
            timeout=5,
            run_external=True,
            casft_dataset="auto",
            observation_time=86400,
            prediction_time=1296000,
            max_epoch=1,
        )
        staged = casft / "data" / "kt2_douban_casft"

    assert result["status"] == "preprocess_failed"
    assert result["reproduction_level"] == "frontier_reproduction_attempted"
    assert result["casft_dataset"] == "kt2_douban_casft"
    assert result["failed_stage"] == "gen_cas"
    assert result["casft_staging_cleaned"] is True
    assert not staged.exists()
    assert not (casft / "data" / "twitter").exists()


def test_temporal_graph_frontier_adapter_exports_no_leakage_protocol():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        forest = _write_forest_fixture(root / "FOREST", "douban")
        dyglib = root / "DyGLib"
        dyglib.mkdir()

        result = run_temporal_graph_frontier(
            "dyglib",
            "douban",
            str(forest),
            str(dyglib),
            sys.executable,
            str(root / "exports"),
            max_cascades=10,
            obs_ratio=0.5,
            max_future=3,
            global_top_n=20,
            max_candidates=50,
            epochs=1,
            batch_size=8,
            num_runs=3,
            gpu=-1,
            timeout=30,
            run_external=False,
        )
        exported = Path(result["temporal_edge_csv"])
        assert exported.exists()

    assert result["status"] == "temporal_edge_export_only"
    assert result["reproduction_level"] == "frontier_data_adapter_ready_not_model_run"
    assert exported.name.endswith("_temporal_edges.csv")
    assert "without future-node injection" in result["note"]
    audit = result["candidate_protocol_audit"]
    assert audit["future_nodes_injected"] is False
    assert audit["leakage_check_passed"] is True
    assert audit["observed_user_candidate_violations"] == 0
    assert audit["future_only_candidate_violations"] == 0


def test_benchmark_schema_validates_frontier_rows():
    rows = [
        {
            "model": "CasFT",
            "dataset": "douban",
            "task": "scale",
            "status": "protocol_export_only",
            "reproduction_level": "frontier_data_adapter_ready_not_model_run",
            "msle": 0.1,
        },
        {
            "model": "DyGFormer/DyGLib",
            "dataset": "douban",
            "task": "next_hop",
            "status": "temporal_edge_export_only",
            "reproduction_level": "frontier_data_adapter_ready_not_model_run",
            "candidate_recall_full": 0.5,
            "candidate_protocol_audit": {"leakage_check_passed": True},
        },
    ]
    report = validate_benchmark_results(rows)
    assert report["ok"] is True
    assert report["schema"] == "cogguard.kt2.benchmark_result.v1"


def test_benchmark_schema_rejects_frontier_completion_without_seed():
    report = validate_benchmark_results(
        [
            {
                "model": "DyGFormer/DyGLib",
                "dataset": "douban",
                "task": "next_hop",
                "status": "ok",
                "reproduction_level": "frontier_reproduction_small_run",
                "hits@100": 0.5,
            }
        ]
    )
    assert report["ok"] is False
    assert any("seed" in error for error in report["errors"])


def test_benchmark_schema_accepts_zero_seed_for_frontier_reproduction():
    report = validate_benchmark_results(
        [
            {
                "model": "CasFT",
                "dataset": "douban",
                "task": "scale",
                "status": "ok",
                "reproduction_level": "frontier_reproduction_small_run",
                "seed": 0,
                "msle": 1.0,
            }
        ]
    )
    assert report["ok"] is True


def test_benchmark_schema_accepts_kt2_full_run_only_with_protocol_evidence():
    base = {
        "model": "KT2JointModel",
        "dataset": "douban",
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "kt2_joint_model_full_run",
        "seed": 7,
        "msle": 1.0,
        "mae": 2.0,
        "rmse": 3.0,
        "direction_accuracy": 0.5,
        "candidate_recall_full": 0.1,
        "hits@10": 0.1,
        "hits@50": 0.2,
        "hits@100": 0.3,
        "mrr": 0.2,
        "macro_micro_consistency": 0.7,
        "candidate_protocol_audit": {"leakage_check_passed": True},
        "note": "not an original MINDS FOREST CasFT paper reproduction; full-run protocol evidence only",
    }
    missing = validate_benchmark_results([base])
    passed = validate_benchmark_results(
        [
            {
                **base,
                "full_run_protocol": {
                    "same_protocol": True,
                    "original_subpaths_passed": True,
                    "teacher_alignment_recorded": True,
                    "config_id": "full-run-preflight",
                },
            }
        ]
    )

    assert missing["ok"] is False
    assert any("full-run protocol requires same_protocol=true" in error for error in missing["errors"])
    assert any("full-run protocol must record config_id" in error for error in missing["errors"])
    assert passed["ok"] is True

    overclaim = validate_benchmark_results([{**base, "reproduction_level": "frontier_reproduction_full_run"}])
    assert overclaim["ok"] is False
    assert any("KT2JointModel must use kt2_joint_model_small_run or kt2_joint_model_full_run" in error for error in overclaim["errors"])


def test_experiment_audit_keeps_full_validation_incomplete_until_critical_gaps_close():
    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp)
        (bench / "results.json").write_text(
            json.dumps(
                [
                    {"model": "RF_Baseline", "dataset": "douban", "msle": 0.5, "mae": 5.0},
                    {"model": "ProspectiveRanker", "dataset": "douban", "hits@100": 0.3, "mrr": 0.2},
                ]
            ),
            encoding="utf-8",
        )
        (bench / "observation_sensitivity.json").write_text(json.dumps([{"obs_ratio": 0.1, "msle": 0.3}]), encoding="utf-8")
        (bench / "casft_external_attempt.json").write_text(
            json.dumps(
                [
                    {
                        "model": "CasFT",
                        "dataset": "douban",
                        "task": "scale",
                        "status": "preprocess_failed",
                        "reproduction_level": "frontier_reproduction_attempted",
                        "failed_stage": "gen_emb",
                        "stderr_tail": ["ModuleNotFoundError: No module named 'cogdl'"],
                    }
                ]
            ),
            encoding="utf-8",
        )
        frontier_row = {
            "dataset": "douban",
            "task": "next_hop",
            "status": "ok",
            "reproduction_level": "frontier_reproduction_small_run",
            "num_runs": 1,
            "hits@100": 0.25,
            "mrr": 0.33,
            "candidate_protocol_audit": {"leakage_check_passed": True},
        }
        (bench / "dyglib_external_attempt.json").write_text(json.dumps([{**frontier_row, "model": "DyGFormer/DyGLib"}]), encoding="utf-8")
        (bench / "tgn_external_attempt.json").write_text(json.dumps([{**frontier_row, "model": "TGN"}]), encoding="utf-8")

        audit = build_audit(benchmark_dir=bench, pheme_dir=bench / "missing_pheme")
        out_json = bench / "audit.json"
        out_md = bench / "audit.md"
        write_audit(audit, out_json, out_md)
        assert out_json.exists()
        assert out_md.exists()

    sections = {section["id"]: section for section in audit["sections"]}
    assert audit["status"] == "incomplete"
    assert audit["summary"]["full_validation_complete"] is False
    assert sections["scale_prediction"]["status"] == "blocked"
    assert sections["next_hop_prediction"]["status"] == "partial"
    assert sections["role_evidence"]["status"] == "missing"


def test_experiment_audit_accepts_kt1_role_evidence_artifacts_without_pheme():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bench = root / "benchmark"
        role_dir = bench / "kt1_role_evidence_validation"
        analysis_dir = role_dir / "analysis"
        analysis_dir.mkdir(parents=True)
        coord = role_dir / "kt1_coordination_scope.json"
        coord.write_text(json.dumps({"records": [{"user_id": "u1", "group_id": "g1"}]}), encoding="utf-8")
        (analysis_dir / "role_evidence.csv").write_text(
            "event_id,user_id,coord_group_id,is_coordinated,role,evidence_paths\nsynthetic_0,u1,g1,True,bridge,\"[['0','1']]\"\n",
            encoding="utf-8",
        )
        (analysis_dir / "role_evidence_quality.json").write_text(
            json.dumps({"scope": "coordinated_users", "coordination_user_coverage": 1.0, "path_complete_rate": 1.0}),
            encoding="utf-8",
        )
        (role_dir / "kt1_role_evidence_validation.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        audit = build_audit(benchmark_dir=bench, pheme_dir=root / "missing_pheme")

    role_section = {section["id"]: section for section in audit["sections"]}["role_evidence"]
    checks = {check["id"]: check for check in role_section["checks"]}
    assert checks["real_kt1_coordination_input"]["status"] == "passed"
    assert checks["role_evidence_artifacts"]["status"] == "passed"
    assert checks["pheme_dataset_validation"]["status"] == "missing"
    assert role_section["status"] == "missing"


def test_experiment_audit_validates_parseable_pheme_dataset():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bench = root / "benchmark"
        role_dir = bench / "kt1_role_evidence_validation"
        analysis_dir = role_dir / "analysis"
        analysis_dir.mkdir(parents=True)
        coord = role_dir / "kt1_coordination_scope.json"
        coord.write_text(json.dumps({"records": [{"user_id": "u1", "group_id": "g1"}]}), encoding="utf-8")
        (analysis_dir / "role_evidence.csv").write_text(
            "event_id,user_id,coord_group_id,is_coordinated,role,evidence_summary,node_ids,evidence_paths,first_evidence_node,first_seen,out_degree_sum,betweenness_sum,pagerank_sum,post_count\n"
            "100,u1,g1,True,璧风垎/婧愬ご,source evidence,['100'],\"[['100','101']]\",100,2024-01-01,1,0.1,0.2,1\n",
            encoding="utf-8",
        )
        (analysis_dir / "role_evidence_quality.json").write_text(
            json.dumps({"scope": "coordinated_users", "coordination_user_coverage": 1.0, "path_complete_rate": 1.0}),
            encoding="utf-8",
        )
        (role_dir / "kt1_role_evidence_validation.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        template = analysis_dir / "role_evidence_manual_review_template.csv"
        template.write_text(
            "event_id,user_id,role,evidence_paths,review_pass\n100,u1,璧风垎/婧愬ご,\"[['100','101']]\",\n",
            encoding="utf-8",
        )
        (analysis_dir / "role_evidence_manual_review_template.json").write_text(
            json.dumps({"review_pass_prefilled": False, "rows_sampled": 1}),
            encoding="utf-8",
        )
        (analysis_dir / "ROLE_EVIDENCE_REVIEW_GUIDE.md").write_text("guide", encoding="utf-8")
        (analysis_dir / "ROLE_EVIDENCE_REVIEW_PACKET.md").write_text("packet", encoding="utf-8")
        (analysis_dir / "ROLE_EVIDENCE_REVIEW.html").write_text("<html>review</html>", encoding="utf-8")

        thread = root / "PHEME" / "all-rnr-annotated-threads" / "topic-all-rnr-threads" / "rumours" / "100"
        (thread / "source-tweets").mkdir(parents=True)
        (thread / "reactions").mkdir()
        (thread / "annotation.json").write_text(json.dumps({"category": "claim text", "true": "1", "misinformation": 0}), encoding="utf-8")
        (thread / "structure.json").write_text(json.dumps({"100": {"101": []}}), encoding="utf-8")
        (thread / "source-tweets" / "100.json").write_text(
            json.dumps({"id_str": "100", "text": "source", "created_at": "Tue Mar 24 10:51:21 +0000 2015", "user": {"id_str": "u1"}}),
            encoding="utf-8",
        )
        (thread / "reactions" / "101.json").write_text(
            json.dumps({"id_str": "101", "text": "reply", "created_at": "Tue Mar 24 10:52:21 +0000 2015", "user": {"id_str": "u2"}}),
            encoding="utf-8",
        )
        audit = build_audit(benchmark_dir=bench, pheme_dir=root / "PHEME")

    role_section = {section["id"]: section for section in audit["sections"]}["role_evidence"]
    checks = {check["id"]: check for check in role_section["checks"]}
    assert checks["pheme_dataset_validation"]["status"] == "passed"
    assert checks["manual_review_packet_ready"]["status"] == "passed"
    assert checks["manual_review_records"]["status"] == "partial"
    assert role_section["status"] == "partial"


def test_pheme_role_evidence_sample_artifacts_are_audited():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bench = root / "benchmark"
        role_dir = bench / "kt1_role_evidence_validation"
        analysis_dir = role_dir / "analysis"
        analysis_dir.mkdir(parents=True)
        coord = role_dir / "kt1_coordination_scope.json"
        coord.write_text(json.dumps({"records": [{"user_id": "u1", "group_id": "g1"}]}), encoding="utf-8")
        (analysis_dir / "role_evidence.csv").write_text(
            "event_id,user_id,coord_group_id,is_coordinated,role,evidence_paths\n100,u1,g1,True,璧风垎/婧愬ご,\"[['100','101']]\"\n",
            encoding="utf-8",
        )
        (analysis_dir / "role_evidence_quality.json").write_text(
            json.dumps({"scope": "coordinated_users", "coordination_user_coverage": 1.0, "path_complete_rate": 1.0}),
            encoding="utf-8",
        )
        (role_dir / "kt1_role_evidence_validation.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")

        thread = root / "PHEME" / "all-rnr-annotated-threads" / "topic-all-rnr-threads" / "rumours" / "100"
        (thread / "source-tweets").mkdir(parents=True)
        (thread / "reactions").mkdir()
        (thread / "annotation.json").write_text(json.dumps({"category": "claim text", "true": "1", "misinformation": 0}), encoding="utf-8")
        (thread / "structure.json").write_text(json.dumps({"100": {"101": []}}), encoding="utf-8")
        (thread / "source-tweets" / "100.json").write_text(
            json.dumps({"id_str": "100", "text": "source", "created_at": "Tue Mar 24 10:51:21 +0000 2015", "user": {"id_str": "u1"}}),
            encoding="utf-8",
        )
        (thread / "reactions" / "101.json").write_text(
            json.dumps({"id_str": "101", "text": "reply", "created_at": "Tue Mar 24 10:52:21 +0000 2015", "user": {"id_str": "u2"}}),
            encoding="utf-8",
        )
        sample = run_pheme_role_evidence_sample(root / "PHEME", bench / "pheme_role_evidence_sample", max_events=1, users_per_event=1)
        audit = build_audit(benchmark_dir=bench, pheme_dir=root / "PHEME")

    role_section = {section["id"]: section for section in audit["sections"]}["role_evidence"]
    checks = {check["id"]: check for check in role_section["checks"]}
    assert sample["status"] == "ok"
    assert sample["role_evidence_rows"] > 0
    assert checks["pheme_role_evidence_artifacts"]["status"] == "passed"


def test_completion_gate_reports_manual_review_as_remaining_action():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bench = root / "benchmark"
        role_dir = bench / "kt1_role_evidence_validation"
        analysis_dir = role_dir / "analysis"
        analysis_dir.mkdir(parents=True)
        coord = role_dir / "kt1_coordination_scope.json"
        coord.write_text(json.dumps({"records": [{"user_id": "u1", "group_id": "g1"}]}), encoding="utf-8")
        (analysis_dir / "role_evidence.csv").write_text(
            "event_id,user_id,coord_group_id,is_coordinated,role,evidence_paths\n100,u1,g1,True,璧风垎/婧愬ご,\"[['100','101']]\"\n",
            encoding="utf-8",
        )
        (analysis_dir / "role_evidence_quality.json").write_text(
            json.dumps({"scope": "coordinated_users", "coordination_user_coverage": 1.0, "path_complete_rate": 1.0}),
            encoding="utf-8",
        )
        (role_dir / "kt1_role_evidence_validation.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        gate = run_completion_gate(benchmark_dir=bench, review_file=analysis_dir / "missing_review.csv", pheme_dir=root / "missing_pheme")

    assert gate["status"] == "incomplete"
    assert gate["full_validation_complete"] is False
    assert gate["manual_review_preflight"]["ok"] is False
    assert "role_evidence_manual_review.csv" in gate["required_next_action"]


def test_completion_gate_passes_when_all_audit_and_review_gates_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bench = root / "benchmark"
        role_dir = bench / "kt1_role_evidence_validation"
        analysis_dir = role_dir / "analysis"
        analysis_dir.mkdir(parents=True)
        (bench / "results.json").write_text(
            json.dumps(
                [
                    {"model": "RF_Baseline", "dataset": "douban", "task": "scale", "status": "ok", "reproduction_level": "local_baseline", "msle": 0.5, "mae": 5.0},
                    {"model": "ProspectiveRanker", "dataset": "douban", "task": "next_hop", "status": "ok", "reproduction_level": "local_baseline", "hits@100": 0.3, "mrr": 0.2},
                ]
            ),
            encoding="utf-8",
        )
        (bench / "observation_sensitivity.json").write_text(json.dumps([{"obs_ratio": 0.1, "msle": 0.3}]), encoding="utf-8")
        (bench / "casft_external_attempt.json").write_text(
            json.dumps(
                [
                    {
                        "model": "CasFT",
                        "dataset": "douban",
                        "task": "scale",
                        "status": "ok",
                        "reproduction_level": "frontier_reproduction_small_run",
                        "seed": 0,
                        "msle": 1.0,
                        "mae": 2.0,
                    }
                ]
            ),
            encoding="utf-8",
        )
        frontier_row = {
            "dataset": "douban",
            "task": "next_hop",
            "status": "ok",
            "reproduction_level": "frontier_reproduction_small_run",
            "num_runs": 3,
            "hits@100": 0.25,
            "mrr": 0.33,
            "candidate_protocol_audit": {"leakage_check_passed": True},
        }
        (bench / "dyglib_external_attempt.json").write_text(json.dumps([{**frontier_row, "model": "DyGFormer/DyGLib"}]), encoding="utf-8")
        (bench / "tgn_external_attempt.json").write_text(json.dumps([{**frontier_row, "model": "TGN"}]), encoding="utf-8")

        coord = role_dir / "kt1_coordination_scope.json"
        coord.write_text(json.dumps({"records": [{"user_id": "u1", "group_id": "g1"}]}), encoding="utf-8")
        (analysis_dir / "role_evidence.csv").write_text(
            "event_id,user_id,coord_group_id,is_coordinated,role,evidence_paths\n100,u1,g1,True,璧风垎/婧愬ご,\"[['100','101']]\"\n",
            encoding="utf-8",
        )
        (analysis_dir / "role_evidence_quality.json").write_text(
            json.dumps({"scope": "coordinated_users", "coordination_user_coverage": 1.0, "path_complete_rate": 1.0}),
            encoding="utf-8",
        )
        (role_dir / "kt1_role_evidence_validation.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        template = analysis_dir / "role_evidence_manual_review_template.csv"
        review = analysis_dir / "role_evidence_manual_review.csv"
        generate_review_template(analysis_dir / "role_evidence.csv", template, sample_size=1, per_role=1, seed=0)
        init_review_file(template, review)
        with review.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(__import__("csv").DictReader(handle))
        rows[0]["review_pass"] = "true"
        rows[0]["reviewer"] = "r1"
        rows[0]["evidence_match"] = "yes"
        rows[0]["confidence_1to5"] = "5"
        rows[0]["reviewer_note"] = "evidence path matches observed chain"
        with review.open("w", encoding="utf-8", newline="") as handle:
            writer = __import__("csv").DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        _write_pheme_fixture(root / "PHEME")
        run_pheme_role_evidence_sample(root / "PHEME", bench / "pheme_role_evidence_sample", max_events=1, users_per_event=1)
        gate = run_completion_gate(benchmark_dir=bench, review_file=review, pheme_dir=root / "PHEME")

    assert gate["status"] == "passed"
    assert gate["full_validation_complete"] is True
    assert gate["open_checks"] == []
    assert gate["manual_review_preflight"]["ok"] is True


def test_experiment_audit_accepts_role_evidence_manual_review_records():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bench = root / "benchmark"
        role_dir = bench / "kt1_role_evidence_validation"
        analysis_dir = role_dir / "analysis"
        analysis_dir.mkdir(parents=True)
        coord = role_dir / "kt1_coordination_scope.json"
        coord.write_text(json.dumps({"records": [{"user_id": "u1", "group_id": "g1"}]}), encoding="utf-8")
        (analysis_dir / "role_evidence.csv").write_text(
            "event_id,user_id,coord_group_id,is_coordinated,role,evidence_summary,node_ids,evidence_paths,first_evidence_node,first_seen,out_degree_sum,betweenness_sum,pagerank_sum,post_count\n"
            "100,u1,g1,True,璧风垎/婧愬ご,source evidence,['100'],\"[['100','101']]\",100,2024-01-01,1,0.1,0.2,1\n",
            encoding="utf-8",
        )
        (analysis_dir / "role_evidence_quality.json").write_text(
            json.dumps({"scope": "coordinated_users", "coordination_user_coverage": 1.0, "path_complete_rate": 1.0}),
            encoding="utf-8",
        )
        (role_dir / "kt1_role_evidence_validation.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        template = analysis_dir / "role_evidence_manual_review_template.csv"
        review = analysis_dir / "role_evidence_manual_review.csv"
        generate_review_template(analysis_dir / "role_evidence.csv", template, sample_size=1, per_role=1, seed=0)
        init_review_file(template, review)
        with review.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(__import__("csv").DictReader(handle))
        rows[0]["review_pass"] = "true"
        rows[0]["reviewer"] = "r1"
        rows[0]["evidence_match"] = "yes"
        rows[0]["confidence_1to5"] = "5"
        rows[0]["reviewer_note"] = "evidence path matches observed chain"
        with review.open("w", encoding="utf-8", newline="") as handle:
            writer = __import__("csv").DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        thread = root / "PHEME" / "all-rnr-annotated-threads" / "topic-all-rnr-threads" / "rumours" / "100"
        (thread / "source-tweets").mkdir(parents=True)
        (thread / "reactions").mkdir()
        (thread / "annotation.json").write_text(json.dumps({"category": "claim text", "true": "1", "misinformation": 0}), encoding="utf-8")
        (thread / "structure.json").write_text(json.dumps({"100": {"101": []}}), encoding="utf-8")
        (thread / "source-tweets" / "100.json").write_text(
            json.dumps({"id_str": "100", "text": "source", "created_at": "Tue Mar 24 10:51:21 +0000 2015", "user": {"id_str": "u1"}}),
            encoding="utf-8",
        )
        (thread / "reactions" / "101.json").write_text(
            json.dumps({"id_str": "101", "text": "reply", "created_at": "Tue Mar 24 10:52:21 +0000 2015", "user": {"id_str": "u2"}}),
            encoding="utf-8",
        )
        audit = build_audit(benchmark_dir=bench, pheme_dir=root / "PHEME")

    role_section = {section["id"]: section for section in audit["sections"]}["role_evidence"]
    checks = {check["id"]: check for check in role_section["checks"]}
    assert checks["manual_review_records"]["status"] == "passed"
    assert role_section["status"] == "passed"


def test_experiment_audit_accepts_multirun_next_hop_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp)
        (bench / "results.json").write_text(json.dumps([{"model": "ProspectiveRanker", "hits@100": 0.3}]), encoding="utf-8")
        frontier_row = {
            "dataset": "douban",
            "task": "next_hop",
            "status": "ok",
            "reproduction_level": "frontier_reproduction_small_run",
            "num_runs": 3,
            "hits@100": 0.25,
            "mrr": 0.33,
            "candidate_protocol_audit": {"leakage_check_passed": True},
        }
        (bench / "dyglib_external_attempt.json").write_text(json.dumps([{**frontier_row, "model": "DyGFormer/DyGLib"}]), encoding="utf-8")
        (bench / "tgn_external_attempt.json").write_text(json.dumps([{**frontier_row, "model": "TGN"}]), encoding="utf-8")

        audit = build_audit(benchmark_dir=bench)

    sections = {section["id"]: section for section in audit["sections"]}
    assert sections["next_hop_prediction"]["status"] == "passed"
    checks = {check["id"]: check for check in sections["next_hop_prediction"]["checks"]}
    assert checks["repeated_small_run_evidence"]["status"] == "passed"
    assert "not multi-seed full validation" in checks["repeated_small_run_evidence"]["detail"]


def test_macro_micro_framework_pairs_scale_and_next_hop_without_overclaim():
    summary = build_macro_micro_framework_summary(
        [
            {
                "model": "CasFT",
                "dataset": "douban",
                "task": "scale",
                "status": "ok",
                "reproduction_level": "frontier_reproduction_small_run",
                "msle": 0.5,
            },
            {
                "model": "DyGFormer/DyGLib",
                "dataset": "douban",
                "task": "next_hop",
                "status": "ok",
                "reproduction_level": "frontier_reproduction_small_run",
                "candidate_recall_full": 0.8,
                "hits@100": 0.3,
                "mrr": 0.2,
                "candidate_protocol_audit": {"leakage_check_passed": True},
            },
        ]
    )
    rows = macro_micro_result_rows(summary)
    schema = validate_benchmark_results(rows)

    assert summary["schema"] == "cogguard.kt2.macro_micro_framework.v1"
    assert summary["status"] == "ok"
    assert summary["datasets"][0]["scale_model"] == "CasFT"
    assert summary["datasets"][0]["micro_model"] == "DyGFormer/DyGLib"
    assert 0 <= summary["datasets"][0]["macro_micro_consistency"] <= 1
    assert rows[0]["model"] == "KT2MacroMicroFramework"
    assert rows[0]["reproduction_level"] == "protocol_proxy_not_original_architecture"
    assert schema["ok"] is True


def test_forest_data_dir_accepts_migrated_dataset_root():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        migrated = root / "forest-data" / "douban"
        repo_style = root / "FOREST" / "data" / "douban"
        migrated.mkdir(parents=True)
        repo_style.mkdir(parents=True)

        assert _forest_data_dir(str(root / "forest-data"), "douban") == str(migrated)
        assert _forest_data_dir(str(root / "FOREST"), "douban") == str(repo_style)


def test_minds_work_dir_resolves_zip_only_repo():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / "MINDS"
        package.mkdir()
        (package / "run.py").write_text("print('run')\n", encoding="utf-8")
        (package / "Module.py").write_text("# module\n", encoding="utf-8")
        import zipfile

        with zipfile.ZipFile(root / "MINDS.zip", "w") as archive:
            archive.write(package / "run.py", "MINDS/run.py")
            archive.write(package / "Module.py", "MINDS/Module.py")
        for child in package.iterdir():
            child.unlink()
        package.rmdir()

        resolved = _minds_work_dir(str(root))

        assert resolved is not None
        assert Path(resolved).name == "MINDS"
        assert (Path(resolved) / "run.py").is_file()


def _write_forest_fixture(root: Path, dataset: str) -> Path:
    data_dir = root / "data" / dataset
    data_dir.mkdir(parents=True)
    (data_dir / "cascade.txt").write_text(
        "1,0 2,10 3,20 4,30 5,40\n2,0 3,5 6,10 7,15 8,20\n",
        encoding="utf-8",
    )
    (data_dir / "cascadevalid.txt").write_text(
        "1,0 4,10 9,20 10,30\n",
        encoding="utf-8",
    )
    (data_dir / "cascadetest.txt").write_text(
        "1,0 2,10 6,20 11,30 12,40\n3,0 4,10 5,20 13,30\n",
        encoding="utf-8",
    )
    return root


def _kt2_sequence_row(dataset: str, seed: int, config_id: str = "unit") -> dict:
    return {
        "model": "KT2SequenceJointModel",
        "dataset": dataset,
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "kt2_sequence_joint_model_small_run",
        "seed": seed,
        "config_id": config_id,
        "msle": 0.8,
        "mae": 1.0,
        "rmse": 1.0,
        "mape_percent": 1.0,
        "smape_percent": 1.0,
        "direction_accuracy": 0.5,
        "trend_mae": 1.0,
        "trend_rmse": 1.0,
        "candidate_recall_full": 0.4,
        "hits@10": 0.2,
        "hits@50": 0.3,
        "hits@100": 0.4,
        "map@10": 0.08,
        "map@50": 0.09,
        "map@100": 0.1,
        "mrr": 0.2,
        "macro_micro_consistency": 0.7,
        "macro_micro_soft_consistency": 0.7,
        "rollout_summary": {"rollout_steps": 3, "rollout_step_count_mean": 3.0, "rollout_unique_user_count_mean": 2.0},
        "candidate_protocol_audit": {"leakage_check_passed": True, "future_nodes_injected": False},
        "methodology": "MINDS backbone with FOREST soft coupling and CasFT continuous trend migration",
        "legacy_boundary": "candidate-row legacy path excluded",
        "note": "not an original MINDS FOREST CasFT reproduction",
        "research_migration": {
            "MINDS": "backbone",
            "FOREST": "soft coupling",
            "CasFT": "trend",
        },
        "training_protocol": {
            "backbone_components": ["DynamicCasHGNN", "RelationGNN", "SharedLSTM", "EulerTrendDecoder"],
            "micro_target": "next_user_autoregressive_sampled_softmax",
            "candidate_features_used_as_model_input": False,
            "rollout": "autoregressive multi-step rollout",
            "trend_decoder": "CasFT-style Euler latent dynamics",
        },
    }


def _write_pheme_fixture(root: Path) -> Path:
    thread = root / "all-rnr-annotated-threads" / "topic-all-rnr-threads" / "rumours" / "100"
    (thread / "source-tweets").mkdir(parents=True)
    (thread / "reactions").mkdir()
    (thread / "annotation.json").write_text(json.dumps({"category": "claim text", "true": "1", "misinformation": 0}), encoding="utf-8")
    (thread / "structure.json").write_text(json.dumps({"100": {"101": []}}), encoding="utf-8")
    (thread / "source-tweets" / "100.json").write_text(
        json.dumps({"id_str": "100", "text": "source", "created_at": "Tue Mar 24 10:51:21 +0000 2015", "user": {"id_str": "u1"}}),
        encoding="utf-8",
    )
    (thread / "reactions" / "101.json").write_text(
        json.dumps({"id_str": "101", "text": "reply", "created_at": "Tue Mar 24 10:52:21 +0000 2015", "user": {"id_str": "u2"}}),
        encoding="utf-8",
    )
    return root


def _write_lgb_fixture(root: Path) -> Path:
    nodes = []
    for idx in range(12):
        label = "bot" if idx % 2 else "human"
        nodes.append(
            {
                "id": f"u{idx}",
                "label": label,
                "name": f"user-{idx}",
                "description": "automated promo bot" if label == "bot" else "ordinary human account",
                "followers_count": idx + 2,
                "friends_count": idx + 1,
                "verified": False,
                "tweets": [
                    "buy now HTTPURL #deal" if label == "bot" else "chatting with friends about local news",
                    "@USER thanks for sharing",
                ],
            }
        )
    (root / "nodes.jsonl").write_text("\n".join(json.dumps(row) for row in nodes), encoding="utf-8")
    edges = [
        ("source", "target"),
        ("u1", "u3"),
        ("u3", "u5"),
        ("u5", "u7"),
        ("u0", "u2"),
        ("u2", "u4"),
        ("u4", "u6"),
        ("u6", "u8"),
        ("u8", "u10"),
    ]
    (root / "edges.csv").write_text("\n".join(",".join(row) for row in edges), encoding="utf-8")
    split_rows = [("id", "split")]
    for idx in range(12):
        split = "train" if idx < 8 else "valid" if idx < 10 else "test"
        split_rows.append((f"u{idx}", split))
    (root / "split.csv").write_text("\n".join(",".join(row) for row in split_rows), encoding="utf-8")
    return root


def _write_lgb_gate_artifacts(root: Path, dataset: str, *, complete: bool, include_context: bool = True, bad_gcl: bool = False) -> None:
    edge_views = [0.2, 0.4] if dataset == "TwiBot-22" else [0.4, 0.6]
    official_node_count = 162865 if dataset == "TwiBot-22" else 229580
    label_counts = {"human": 81433, "bot": 81432} if dataset == "TwiBot-22" else {"human": 5237, "bot": 6589}
    split_counts = (
        {"train": 114006, "valid": 32573, "test": 16286}
        if dataset == "TwiBot-22"
        else {"train": 8278, "valid": 2365, "test": 1183}
    )
    if bad_gcl:
        edge_views = [0.1, 0.1]
    seed_runs = [
        {
            "status": "ok",
            "seed": seed,
            "accuracy": 0.8,
            "f1": 0.81,
            "roc_auc": 0.8,
            "training_protocol": {
                "gnn": "LGB(GCN)",
                "text_encoder": "roberta_sft_features",
                "text_features_source": str(root / "lm_features.jsonl"),
                "edge_dropout_views": edge_views,
                "gcl_temperature": 0.4,
            },
        }
        for seed in (42, 43, 44, 45, 46)
    ]
    (root / "conversion_summary.json").write_text(
        json.dumps(
            {
                "schema": "cogguard.kt2.lgb_conversion_summary.v1",
                "source_format": "twibot22" if dataset == "TwiBot-22" else "twibot20",
                "node_count": official_node_count,
                "edge_count": official_node_count * 2,
                "labeled_nodes": sum(label_counts.values()),
                "label_counts": label_counts,
                "split_counts": split_counts,
                "include_unlabeled_context": include_context,
                "unlabeled_context_nodes": 10 if include_context else 0,
            }
        ),
        encoding="utf-8",
    )
    (root / "lm_sft_report.json").write_text(
        json.dumps(
            {
                "schema": "cogguard.kt2.lgb_lm_sft_features.v1",
                "status": "ok",
                "encoder_backend": "transformers_roberta_sft",
                "strict_lgb_text_encoder": True,
                "feature_file": str(root / "lm_features.jsonl"),
                "node_count": official_node_count,
            }
        ),
        encoding="utf-8",
    )
    (root / "lgb_multiseed_summary.json").write_text(
        json.dumps(
            {
                "schema": "cogguard.kt2.lgb_multiseed_summary.v1",
                "status": "ok",
                "dataset": dataset,
                "reproduction_level": "frontier_reproduction_full_run",
                "gnn_variant": "GCN",
                "num_runs": 5,
                "seeds": [42, 43, 44, 45, 46],
                "meets_paper_seed_count": True,
                "metrics_mean_std": {
                    "accuracy": {"mean": 0.8, "std": 0.01},
                    "f1": {"mean": 0.81, "std": 0.01},
                    "roc_auc": {"mean": 0.8, "std": 0.01},
                },
                "paper_target": {
                    "table": "Table II",
                    "model": "LGB(GCN)",
                    "accuracy": 0.8042 if dataset == "TwiBot-22" else 0.8509,
                    "f1": 0.8131 if dataset == "TwiBot-22" else 0.8744,
                    "roc_auc": 0.8042 if dataset == "TwiBot-22" else 0.8423,
                    "comparison_note": "unit fixture records paper target for strict gate coverage",
                },
                "runs": seed_runs,
                "run_metadata": {
                    "artifact_type": "lgb_multiseed_summary",
                    "dataset": dataset,
                    "data_dir": str(root),
                    "command_or_entrypoint": "benchmark.adapters.lgb_bot_detection",
                    "python_version": "3.x",
                    "platform": "unit-test",
                    "device": "cpu",
                    "seeds": [42, 43, 44, 45, 46],
                    "variants": [],
                    "reproduction_level": "frontier_reproduction_full_run",
                },
            }
        ),
        encoding="utf-8",
    )
    ablations = ["full", "wo_lm_sft"] if not complete else [
        "full",
        "wo_lm_sft",
        "wo_gnn_finetuning",
        "wo_gnn_pretraining",
        "wo_concat",
        "average_fusion",
        "max_fusion",
        "lm_only",
    ]
    (root / "lgb_ablation_suite.json").write_text(
        json.dumps(
            {
                "schema": "cogguard.kt2.lgb_ablation_suite.v1",
                "status": "ok",
                "dataset": dataset,
                "reproduction_level": "frontier_reproduction_full_run",
                "seeds": [42, 43, 44, 45, 46],
                "completed_variants": ablations,
                "required_table3_variants": [
                    "full",
                    "wo_lm_sft",
                    "wo_gnn_finetuning",
                    "wo_gnn_pretraining",
                    "wo_concat",
                    "average_fusion",
                    "max_fusion",
                    "lm_only",
                ],
                "table3_complete": complete,
                "variants": [
                    {
                        "variant": variant,
                        "summary": {
                            "schema": "cogguard.kt2.lgb_multiseed_summary.v1",
                            "status": "ok",
                            "num_runs": 5,
                            "seeds": [42, 43, 44, 45, 46],
                            "meets_paper_seed_count": True,
                            "metrics_mean_std": {
                                "accuracy": {"mean": 0.8, "std": 0.01},
                                "f1": {"mean": 0.81, "std": 0.01},
                                "roc_auc": {"mean": 0.8, "std": 0.01},
                            },
                            "runs": seed_runs,
                        },
                    }
                    for variant in ablations
                ],
                "run_metadata": {
                    "artifact_type": "lgb_ablation_suite",
                    "dataset": dataset,
                    "data_dir": str(root),
                    "command_or_entrypoint": "benchmark.adapters.lgb_bot_detection",
                    "python_version": "3.x",
                    "platform": "unit-test",
                    "device": "cpu",
                    "seeds": [42, 43, 44, 45, 46],
                    "variants": ablations,
                    "reproduction_level": "frontier_reproduction_full_run",
                },
            }
        ),
        encoding="utf-8",
    )


