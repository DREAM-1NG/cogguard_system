from __future__ import annotations

import csv
import importlib.util
import json
import sys
import types
import uuid
from pathlib import Path

from app.config import PROJECT_ROOT


def _load_experiments():
    research_name = "research"
    research_dir = PROJECT_ROOT / "research"
    if research_name not in sys.modules:
        research_package = types.ModuleType(research_name)
        research_package.__path__ = [str(research_dir)]
        sys.modules[research_name] = research_package

    package_name = "research.coordination_experiments"
    cached = sys.modules.get(package_name)
    if cached is not None:
        return cached
    package_dir = research_dir / "coordination_experiments"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def _write_len_graph(path: Path, *, label: str, nodes: int, edges: int, timestamp_step: int) -> None:
    graph_nodes = [
        {
            "id": index,
            "node_attr": [float(index % 3), float(nodes - index)],
            "kcore": [float((index % 2) + 1)],
        }
        for index in range(nodes)
    ]
    links = []
    for index in range(edges):
        source = index % nodes
        target = (index + 1) % nodes
        links.append(
            {
                "source": source,
                "target": target,
                "Interaction_Count": 1 + (index % 4),
                "timestamp": 1_700_000_000 + index * timestamp_step,
                "text": f"#{label} https://example.test/{label}/{index}",
                "edge_attr": [0.1 + index / 100.0, 0.2],
            }
        )
    path.write_text(
        json.dumps(
            {
                "directed": True,
                "multigraph": False,
                "graph": {},
                "nodes": graph_nodes,
                "links": links,
            },
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def _write_len_fixture(root: Path) -> Path:
    root.mkdir(parents=True)
    specs = [
        ("#alpha_campaign_fulldata.json", "campaign", 8, 24, 30),
        ("#beta_campaign_fulldata.json", "campaign", 9, 28, 20),
        ("#gamma_campaign_fulldata.json", "campaign", 10, 32, 15),
        ("#delta_noncampaign_fulldata.json", "noncampaign", 8, 8, 3600),
        ("#epsilon_noncampaign_fulldata.json", "noncampaign", 9, 9, 4200),
        ("#zeta_noncampaign_fulldata.json", "noncampaign", 10, 10, 4800),
    ]
    for filename, label, nodes, edges, step in specs:
        _write_len_graph(root / filename, label=label, nodes=nodes, edges=edges, timestamp_step=step)
    return root


def _write_len_many_fixture(root: Path, *, per_class: int = 10) -> Path:
    root.mkdir(parents=True)
    for index in range(per_class):
        _write_len_graph(
            root / f"#campaign{index:02d}_campaign_fulldata.json",
            label="campaign",
            nodes=8 + index,
            edges=24 + index,
            timestamp_step=30 + index,
        )
        _write_len_graph(
            root / f"#noncampaign{index:02d}_noncampaign_fulldata.json",
            label="noncampaign",
            nodes=8 + index,
            edges=8 + index,
            timestamp_step=3600 + index,
        )
    return root


def _write_arff_fixture(root: Path) -> Path:
    root.mkdir(parents=True)
    path = root / "data.arff"
    rows = [
        (10, 8, 0.8, 0.2, "legitimate"),
        (12, 9, 0.75, 0.1, "legitimate"),
        (14, 10, 0.71, 0.3, "legitimate"),
        (40, 90, 2.25, 0.9, "truthy"),
        (42, 96, 2.28, 0.8, "truthy"),
        (44, 100, 2.27, 0.7, "truthy"),
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        stream.write("@RELATION truthy_memes\n")
        stream.write("@ATTRIBUTE meme_statistics.nodes NUMERIC\n")
        stream.write("@ATTRIBUTE meme_statistics.edges NUMERIC\n")
        stream.write("@ATTRIBUTE meme_statistics.mean_w NUMERIC\n")
        stream.write("@ATTRIBUTE meme_display_statistics.num_truthy NUMERIC\n")
        stream.write("@ATTRIBUTE class {truthy,legitimate}\n")
        stream.write("@DATA\n")
        writer.writerows(rows)
    return root


def _g_fixture_root(module, name: str) -> Path:
    return module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-public-detection-fixture-{name}-{uuid.uuid4().hex}"


def test_public_detection_method_registry_fixes_dataset_method_boundaries():
    module = _load_experiments()
    registry = module.default_public_detection_method_registry()

    assert {
        "cogguard_learned_fused_detector",
        "cogguard_heuristic_bayesian",
        "len_graph_stat_logistic",
        "vargas_coordination_activity_classifier",
        "gcn_graph_classifier",
        "graphsage_graph_classifier",
        "compact_graphsage_fused_detector",
        "gin_graph_classifier",
        "diffpool_graph_classifier",
        "deep_pyg_graphsage_fused_detector",
        "deep_pyg_gin_fused_detector",
        "deep_pyg_gcn_fused_detector",
        "deep_len_mlp_fused_detector",
        "deep_len_fast_mlp_fused_detector",
        "inductive_io_graph_learning",
        "iohunter_account_graph_learning",
        "truthy_classic_feature_classifier",
        "deep_tabular_mlp_detector",
        "deep_tabular_residual_detector",
        "tgat",
        "tgn",
        "dygformer",
    }.issubset(set(registry.method_ids))
    assert registry.feasibility("large_engagement_networks", "tgn").status == "blocked"
    assert "observed_timestamps" in registry.feasibility("large_engagement_networks", "tgn").missing_signals
    assert registry.feasibility("large_engagement_networks", "len_graph_stat_logistic").status == "ready"
    assert registry.feasibility("large_engagement_networks", "gcn_graph_classifier").status == "ready"
    assert registry.feasibility("large_engagement_networks", "compact_graphsage_fused_detector").status == "ready"
    assert registry.feasibility("large_engagement_networks", "deep_pyg_graphsage_fused_detector").status == "ready"
    assert registry.feasibility("large_engagement_networks", "deep_len_mlp_fused_detector").status == "ready"
    assert registry.feasibility("large_engagement_networks", "deep_len_fast_mlp_fused_detector").status == "ready"
    assert registry.feasibility("astroturf_legitimate_classification", "truthy_classic_feature_classifier").status == "ready"
    assert registry.feasibility("astroturf_legitimate_classification", "deep_tabular_mlp_detector").status == "ready"
    assert registry.feasibility("astroturf_legitimate_classification", "gcn_graph_classifier").status == "blocked"
    assert registry.feasibility("astroturf_legitimate_classification", "compact_graphsage_fused_detector").status == "blocked"
    assert registry.feasibility("astroturf_legitimate_classification", "deep_pyg_graphsage_fused_detector").status == "blocked"
    assert registry.feasibility("astroturf_legitimate_classification", "deep_len_mlp_fused_detector").status == "blocked"
    assert registry.feasibility("astroturf_legitimate_classification", "deep_len_fast_mlp_fused_detector").status == "blocked"
    assert registry.feasibility("large_engagement_networks", "deep_tabular_mlp_detector").status == "blocked"


def test_len_and_astroturf_adapters_build_same_detection_contract():
    module = _load_experiments()
    fixture_root = _g_fixture_root(module, "adapter")
    len_root = _write_len_fixture(fixture_root / "len")
    arff_root = _write_arff_fixture(fixture_root / "al")

    len_dataset = module.build_public_detection_dataset(
        module.PublicDetectionDatasetConfig(
            dataset_id="large_engagement_networks",
            kind="len_graph_json_dir",
            path=str(len_root),
        ),
        seed=11,
    )
    al_dataset = module.build_public_detection_dataset(
        module.PublicDetectionDatasetConfig(
            dataset_id="astroturf_legitimate_classification",
            kind="alclassification_arff",
            path=str(arff_root / "data.arff"),
        ),
        seed=11,
    )

    assert len_dataset.manifest.label_semantics == "LEN graph label: campaign=1, noncampaign=0"
    assert al_dataset.manifest.label_semantics == "Truthy astroturf label: truthy=1, legitimate=0"
    assert len_dataset.partitions.train_cases[0].feature_schema_fingerprint == len_dataset.schema.fingerprint
    assert al_dataset.partitions.train_cases[0].feature_schema_fingerprint == al_dataset.schema.fingerprint
    assert set(len_dataset.evaluation.test_labels.values()) == {0, 1}
    assert set(al_dataset.evaluation.test_labels.values()) == {0, 1}
    assert "static_placeholder_not_observed_time" in al_dataset.manifest.claim_markers
    assert "node_count" in len_dataset.schema.names
    assert "meme_statistics.nodes" in al_dataset.schema.names


def test_public_detection_stratified_split_uses_proportional_holdout():
    module = _load_experiments()
    fixture_root = _g_fixture_root(module, "split")
    len_root = _write_len_many_fixture(fixture_root / "len", per_class=10)

    dataset = module.build_public_detection_dataset(
        module.PublicDetectionDatasetConfig(
            dataset_id="large_engagement_networks",
            kind="len_graph_json_dir",
            path=str(len_root),
        ),
        seed=17,
    )

    assert len(dataset.partitions.validation_cases) == 4
    assert len(dataset.partitions.test_cases) == 4
    assert set(dataset.evaluation.test_labels.values()) == {0, 1}


def test_deep_detection_standardization_uses_train_statistics_only():
    _load_experiments()
    from research.coordination_experiments.deep_detection import _standardize_arrays

    train = _np_array([[1.0, 10.0], [3.0, 14.0]])
    validation = _np_array([[101.0, 110.0]])
    test = _np_array([[201.0, 210.0]])

    train_x, validation_x, test_x, mean, scale = _standardize_arrays(train, validation, test)

    assert mean == (2.0, 12.0)
    assert scale == (1.0, 2.0)
    assert train_x.tolist() == [[-1.0, -1.0], [1.0, 1.0]]
    assert validation_x.tolist() == [[99.0, 49.0]]
    assert test_x.tolist() == [[199.0, 99.0]]


def _np_array(rows):
    import numpy as np

    return np.asarray(rows, dtype=np.float64)


def test_deep_detection_graph_features_clean_empty_and_invalid_sketches():
    _load_experiments()
    from research.coordination_experiments.deep_detection import (
        _graph_edges_for_pyg,
        _graph_internal_features,
        _graph_node_features_for_pyg,
        _GraphSketch,
    )

    empty = _GraphSketch(node_features=(), edge_index=((0, 9),), edge_weight=(1.0,))
    assert _graph_node_features_for_pyg(empty) == ((0.0,) * 12,)
    assert _graph_edges_for_pyg(empty, 1) == ((), ())
    assert len(_graph_internal_features(empty)) == 42

    dirty = _GraphSketch(
        node_features=((1.0, 2.0), (float("nan"),) * 20),
        edge_index=((0, 1), (1, 7), (-1, 0)),
        edge_weight=(2.0, 9.0, 3.0),
    )
    nodes = _graph_node_features_for_pyg(dirty)
    assert len(nodes) == 2
    assert all(len(row) == 12 for row in nodes)
    assert _graph_edges_for_pyg(dirty, len(nodes)) == (((0, 1),), (2.0,))


def test_public_detection_runner_writes_g_drive_results_for_executable_and_blocked_methods():
    module = _load_experiments()
    fixture_root = _g_fixture_root(module, "runner")
    len_root = _write_len_fixture(fixture_root / "len")
    arff_root = _write_arff_fixture(fixture_root / "al")
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-public-detection-{uuid.uuid4().hex}"

    manifest = module.run_public_detection_comparison(
        (
            module.PublicDetectionDatasetConfig(
                dataset_id="large_engagement_networks",
                kind="len_graph_json_dir",
                path=str(len_root),
            ),
            module.PublicDetectionDatasetConfig(
                dataset_id="astroturf_legitimate_classification",
                kind="alclassification_arff",
                path=str(arff_root / "data.arff"),
            ),
        ),
        output,
        seeds=(3,),
        method_ids=(
            "learned_fused_detector",
            "heuristic_baseline_v1",
            "len_graph_stat_logistic",
            "vargas_coordination_activity_classifier",
            "truthy_feature_logistic",
            "gcn_graph_classifier",
            "compact_graphsage_fused_detector",
            "deep_pyg_graphsage_fused_detector",
            "deep_len_mlp_fused_detector",
            "deep_len_fast_mlp_fused_detector",
            "deep_tabular_mlp_detector",
            "tgn",
        ),
        bootstrap_resamples=25,
    )

    assert manifest["schema_version"] == module.PUBLIC_DETECTION_SCHEMA_VERSION
    assert Path(manifest["artifact_paths"]["per_seed_json"]).drive.upper() == "G:"
    assert manifest["runtime_warmup"]["status"] == "completed"
    assert manifest["runtime_warmup"]["runtime_seconds"] >= 0.0
    assert manifest["dataset_protocols"][0]["test_count"] >= 2
    assert (output / "public_detection_manifest.json").exists()
    assert (output / "per_seed_rows.json").exists()
    assert Path(manifest["artifact_paths"]["deep_detection_claim_gates_json"]).drive.upper() == "G:"
    assert (output / "deep_detection_claim_gates.json").exists()
    claim_gates = json.loads((output / "claim_gates.json").read_text(encoding="utf-8"))["claim_gates"]
    assert {gate["status"] for gate in claim_gates} == {"blocked"}
    deep_gates = json.loads((output / "deep_detection_claim_gates.json").read_text(encoding="utf-8"))["gates"]
    assert {
        (gate["dataset_id"], gate["candidate_method_id"])
        for gate in deep_gates
    } == {
        ("large_engagement_networks", "compact_graphsage_fused_detector"),
        ("large_engagement_networks", "deep_pyg_graphsage_fused_detector"),
        ("large_engagement_networks", "deep_len_mlp_fused_detector"),
        ("large_engagement_networks", "deep_len_fast_mlp_fused_detector"),
        ("large_engagement_networks", "deep_tabular_mlp_detector"),
        ("astroturf_legitimate_classification", "compact_graphsage_fused_detector"),
        ("astroturf_legitimate_classification", "deep_pyg_graphsage_fused_detector"),
        ("astroturf_legitimate_classification", "deep_len_mlp_fused_detector"),
        ("astroturf_legitimate_classification", "deep_len_fast_mlp_fused_detector"),
        ("astroturf_legitimate_classification", "deep_tabular_mlp_detector"),
    }
    assert all(gate["selection_eligible"] is False for gate in deep_gates)
    row_methods = {
        row["method_id"]
        for row in manifest["rows"]
        if row["dataset_id"] == "large_engagement_networks" and row["status"] == "success"
    }
    assert {
        "learned_fused_detector",
        "heuristic_baseline_v1",
        "len_graph_stat_logistic",
        "gcn_graph_classifier",
        "compact_graphsage_fused_detector",
        "deep_pyg_graphsage_fused_detector",
        "deep_len_mlp_fused_detector",
        "deep_len_fast_mlp_fused_detector",
    }.issubset(row_methods)
    al_success = {
        row["method_id"]
        for row in manifest["rows"]
        if row["dataset_id"] == "astroturf_legitimate_classification" and row["status"] == "success"
    }
    assert "deep_tabular_mlp_detector" in al_success
    blocked_rows = {
        (row["dataset_id"], row["method_id"]): row["status"]
        for row in manifest["rows"]
        if row["status"] == "blocked"
    }
    assert blocked_rows[("large_engagement_networks", "tgn")] == "blocked"
    assert blocked_rows[("astroturf_legitimate_classification", "gcn_graph_classifier")] == "blocked"
    assert blocked_rows[("astroturf_legitimate_classification", "compact_graphsage_fused_detector")] == "blocked"
    assert blocked_rows[("astroturf_legitimate_classification", "deep_pyg_graphsage_fused_detector")] == "blocked"
    assert blocked_rows[("astroturf_legitimate_classification", "deep_len_mlp_fused_detector")] == "blocked"
    assert blocked_rows[("astroturf_legitimate_classification", "deep_len_fast_mlp_fused_detector")] == "blocked"
    assert blocked_rows[("large_engagement_networks", "deep_tabular_mlp_detector")] == "blocked"
    blocked = {
        (item["dataset_id"], item["method_id"]): item["status"]
        for item in manifest["feasibility_matrix"]
    }
    assert blocked[("large_engagement_networks", "tgn")] == "blocked"
    assert blocked[("astroturf_legitimate_classification", "gcn_graph_classifier")] == "blocked"
    assert blocked[("astroturf_legitimate_classification", "deep_pyg_graphsage_fused_detector")] == "blocked"
    assert blocked[("astroturf_legitimate_classification", "deep_len_mlp_fused_detector")] == "blocked"
    assert blocked[("astroturf_legitimate_classification", "deep_len_fast_mlp_fused_detector")] == "blocked"
    assert blocked[("large_engagement_networks", "deep_tabular_mlp_detector")] == "blocked"
    deep_row = next(
        row
        for row in manifest["rows"]
        if row["dataset_id"] == "large_engagement_networks"
        and row["method_id"] == "deep_pyg_graphsage_fused_detector"
    )
    artifact = deep_row["model_artifact"]
    assert artifact["train_fit_case_ids_fingerprint"] == deep_row["train_partition_fingerprint"]
    assert artifact["validation_calibration_case_ids_fingerprint"] == deep_row["validation_partition_fingerprint"]
    assert artifact["validation_threshold_case_ids_fingerprint"] == deep_row["validation_partition_fingerprint"]
    assert artifact["validation_ood_case_ids_fingerprint"] == deep_row["validation_partition_fingerprint"]
    assert artifact["optimizer_config"]["internal_feature_width"] == 42
    assert deep_row["test_partition_fingerprint"] not in json.dumps(artifact, sort_keys=True)
    assert deep_row["selection_eligible"] is False
    assert "test_labels" not in json.dumps(artifact, sort_keys=True)
    len_mlp_row = next(
        row
        for row in manifest["rows"]
        if row["dataset_id"] == "large_engagement_networks"
        and row["method_id"] == "deep_len_mlp_fused_detector"
    )
    len_mlp_artifact = len_mlp_row["model_artifact"]
    assert len_mlp_artifact["optimizer_config"]["algorithm"] == "deep_len_graph_stat_mlp_fused_detector"
    assert len_mlp_artifact["optimizer_config"]["search_budget"] in {
        "smoke_small_fixture",
        "fast_len_sklearn_mlp_grid_v2",
    }
    assert len_mlp_artifact["optimizer_config"]["device"] == "cpu/sklearn"
    assert len_mlp_artifact["optimizer_config"]["internal_feature_width"] == 42
    assert len_mlp_row["test_partition_fingerprint"] not in json.dumps(len_mlp_artifact, sort_keys=True)
    assert len_mlp_row["selection_eligible"] is False
    assert "test_labels" not in json.dumps(len_mlp_artifact, sort_keys=True)
    fast_len_mlp_row = next(
        row
        for row in manifest["rows"]
        if row["dataset_id"] == "large_engagement_networks"
        and row["method_id"] == "deep_len_fast_mlp_fused_detector"
    )
    fast_artifact = fast_len_mlp_row["model_artifact"]
    assert fast_artifact["optimizer_config"]["search_budget"] in {
        "smoke_small_fixture",
        "fast_len_sklearn_mlp_single_v1",
    }
    assert fast_artifact["optimizer_config"]["device"] == "cpu/sklearn"
    assert fast_len_mlp_row["test_partition_fingerprint"] not in json.dumps(fast_artifact, sort_keys=True)
    assert fast_len_mlp_row["selection_eligible"] is False
    assert "test_labels" not in json.dumps(fast_artifact, sort_keys=True)
    compact_row = next(
        row
        for row in manifest["rows"]
        if row["dataset_id"] == "large_engagement_networks"
        and row["method_id"] == "compact_graphsage_fused_detector"
    )
    compact_artifact = compact_row["model_artifact"]
    assert compact_artifact["train_fit_case_ids_fingerprint"] == compact_row["train_partition_fingerprint"]
    assert compact_artifact["validation_calibration_case_ids_fingerprint"] == compact_row["validation_partition_fingerprint"]
    assert compact_artifact["optimizer_config"]["fused_feature_width"] == manifest["dataset_protocols"][0]["feature_count"]
    assert compact_row["test_partition_fingerprint"] not in json.dumps(compact_artifact, sort_keys=True)
    assert compact_row["selection_eligible"] is False


def test_public_detection_runner_clears_stale_source_registry_between_runs():
    module = _load_experiments()
    fixture_root = _g_fixture_root(module, "source-registry")
    len_root = _write_len_fixture(fixture_root / "len")
    stale_root = _write_len_fixture(fixture_root / "stale")
    stale_case_id = module.build_public_detection_dataset(
        module.PublicDetectionDatasetConfig(
            dataset_id="large_engagement_networks",
            kind="len_graph_json_dir",
            path=str(stale_root),
        ),
        seed=3,
    ).manifest.source_case_ids[0]
    assert "stale" in module.resolve_public_detection_source_path(stale_case_id).as_posix()
    stale_sketch = module.resolve_public_detection_graph_sketch(stale_case_id)
    assert stale_sketch is not None

    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-public-detection-registry-{uuid.uuid4().hex}"
    module.run_public_detection_comparison(
        (
            module.PublicDetectionDatasetConfig(
                dataset_id="large_engagement_networks",
                kind="len_graph_json_dir",
                path=str(len_root),
            ),
        ),
        output,
        seeds=(3,),
        method_ids=("gcn_graph_classifier",),
        bootstrap_resamples=25,
    )

    assert "stale" not in module.resolve_public_detection_source_path(stale_case_id).as_posix()
    assert module.resolve_public_detection_graph_sketch(stale_case_id) is not stale_sketch
