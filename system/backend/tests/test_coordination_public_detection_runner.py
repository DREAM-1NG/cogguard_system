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
        "gin_graph_classifier",
        "diffpool_graph_classifier",
        "inductive_io_graph_learning",
        "iohunter_account_graph_learning",
        "truthy_classic_feature_classifier",
        "tgat",
        "tgn",
        "dygformer",
    }.issubset(set(registry.method_ids))
    assert registry.feasibility("large_engagement_networks", "tgn").status == "blocked"
    assert "observed_timestamps" in registry.feasibility("large_engagement_networks", "tgn").missing_signals
    assert registry.feasibility("large_engagement_networks", "len_graph_stat_logistic").status == "ready"
    assert registry.feasibility("large_engagement_networks", "gcn_graph_classifier").status == "ready"
    assert registry.feasibility("astroturf_legitimate_classification", "truthy_classic_feature_classifier").status == "ready"
    assert registry.feasibility("astroturf_legitimate_classification", "gcn_graph_classifier").status == "blocked"


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
            "tgn",
        ),
        bootstrap_resamples=25,
    )

    assert manifest["schema_version"] == module.PUBLIC_DETECTION_SCHEMA_VERSION
    assert Path(manifest["artifact_paths"]["per_seed_json"]).drive.upper() == "G:"
    assert manifest["dataset_protocols"][0]["test_count"] >= 2
    assert (output / "public_detection_manifest.json").exists()
    assert (output / "per_seed_rows.json").exists()
    claim_gates = json.loads((output / "claim_gates.json").read_text(encoding="utf-8"))["claim_gates"]
    assert {gate["status"] for gate in claim_gates} == {"blocked"}
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
    }.issubset(row_methods)
    blocked_rows = {
        (row["dataset_id"], row["method_id"]): row["status"]
        for row in manifest["rows"]
        if row["status"] == "blocked"
    }
    assert blocked_rows[("large_engagement_networks", "tgn")] == "blocked"
    assert blocked_rows[("astroturf_legitimate_classification", "gcn_graph_classifier")] == "blocked"
    blocked = {
        (item["dataset_id"], item["method_id"]): item["status"]
        for item in manifest["feasibility_matrix"]
    }
    assert blocked[("large_engagement_networks", "tgn")] == "blocked"
    assert blocked[("astroturf_legitimate_classification", "gcn_graph_classifier")] == "blocked"


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
