from __future__ import annotations

import importlib.util
import json
import pickle
import shutil
import sys
import types
import uuid
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from app.config import PROJECT_ROOT


def _load_experiments():
    research_dir = PROJECT_ROOT / "research"
    if "research" not in sys.modules:
        package = types.ModuleType("research")
        package.__path__ = [str(research_dir)]
        sys.modules["research"] = package
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


def _payload():
    node_count = 6

    def graph(edges=()):
        value = nx.Graph()
        value.add_nodes_from(range(node_count))
        value.add_edges_from(edges)
        return value

    splits = {}
    for fold_id in range(5):
        test = ((fold_id + 4) % node_count, (fold_id + 5) % node_count)
        validation = ((fold_id + 3) % node_count,)
        train = tuple(index for index in range(node_count) if index not in test + validation)
        splits[fold_id] = {
            name: np.asarray([index in members for index in range(node_count)], dtype=np.bool_)
            for name, members in (("train", train), ("val", validation), ("test", test))
        }
    return {
        "graph": graph([(0, 1), (1, 2)]),
        "coRT": graph([(0, 1, {"weight": 1.0})]),
        "coURL": graph([(1, 2, {"weight": 2.0})]),
        "hashSeq": graph([(2, 3, {"weight": 3.0})]),
        "fastRT": graph([(3, 4, {"weight": 4.0})]),
        "tweetSim": graph([(4, 5, {"weight": 5.0})]),
        "labels": np.asarray([0, 1, 0, 1, 0, 1], dtype=np.float64),
        "splits": splits,
    }


def _dataset_root(
    tmp_path: Path,
    module,
    *,
    payload=None,
    directory_name: str = "processed",
) -> Path:
    root = tmp_path / directory_name
    raw = pickle.dumps(payload or _payload(), protocol=pickle.HIGHEST_PROTOCOL)
    for campaign in module.IOHUNTER_PREFLIGHT_CAMPAIGNS:
        path = root / campaign / "0.7_datasets.pkl"
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
    return root


def _output_dir(module, name: str) -> Path:
    return module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-task7a-{name}-{uuid.uuid4().hex}"


def test_matrix_protocol_api_exists_before_contract_tests():
    module = _load_experiments()
    assert hasattr(module, "preflight_iohunter_matrix")
    assert hasattr(module, "validate_iohunter_preflight_output_dir")
    assert module.IOHUNTER_OFFICIAL_SEEDS == (42, 43, 44, 45, 46)


def test_matrix_enumerates_campaign_seed_fold_method_and_time_rows_deterministically(tmp_path):
    module = _load_experiments()
    dataset_root = _dataset_root(tmp_path, module)
    output = _output_dir(module, "deterministic")
    try:
        first = module.preflight_iohunter_matrix(dataset_root, output, memory_budget_bytes=256 * 1024 * 1024)
        second = module.preflight_iohunter_matrix(dataset_root, output, memory_budget_bytes=256 * 1024 * 1024)
        method_count = len(module.default_baseline_registry().specs())
        assert len(first.rows) == 6 * 5 * method_count * 2
        assert first.matrix_fingerprint == second.matrix_fingerprint
        assert [row.run_id for row in first.rows] == [row.run_id for row in second.rows]
        assert len({row.run_id for row in first.rows}) == len(first.rows)
        assert {row.resume_action for row in second.rows} == {"skip_preflight"}
        assert {(row.seed, row.fold_id) for row in first.rows} == {
            (42, "fold-000"),
            (43, "fold-001"),
            (44, "fold-002"),
            (45, "fold-003"),
            (46, "fold-004"),
        }
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_matrix_rows_record_dependencies_capabilities_fingerprints_and_descendant_paths(tmp_path):
    module = _load_experiments()
    dataset_root = _dataset_root(tmp_path, module)
    output = _output_dir(module, "row-contract")
    try:
        matrix = module.preflight_iohunter_matrix(dataset_root, output, memory_budget_bytes=256 * 1024 * 1024)
        for row in matrix.rows:
            spec = module.default_baseline_registry().get(row.method_id)
            assert row.dependencies == spec.optional_dependencies
            assert row.required_capabilities == spec.required_capabilities
            expected_execution_inputs = (
                {"discovery"}
                if spec.stage == "discovery"
                else {"discovery", "evaluator", "fold"}
            )
            assert set(row.input_fingerprints) == expected_execution_inputs
            assert set(row.evaluation_fingerprints) == {"evaluator", "fold"}
            assert row.execution_id.startswith("iohunter-execution-")
            expected = Path(row.expected_output_path).resolve()
            expected.relative_to(output.resolve())
            assert expected.suffix == ".json"
            assert row.status in {"ready", "blocked"}
            assert (row.status == "blocked") == bool(row.reason)
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_discovery_execution_identity_is_independent_of_evaluator_labels_folds_and_fused_graph(tmp_path):
    module = _load_experiments()
    original = _payload()
    changed = _payload()
    changed["labels"] = 1.0 - changed["labels"]
    changed_graph = nx.Graph()
    changed_graph.add_nodes_from(range(6))
    changed_graph.add_edges_from(((0, 5), (2, 4)))
    changed["graph"] = changed_graph
    changed["splits"][0], changed["splits"][1] = (
        changed["splits"][1],
        changed["splits"][0],
    )
    first_root = _dataset_root(
        tmp_path,
        module,
        payload=original,
        directory_name="first-processed",
    )
    second_root = _dataset_root(
        tmp_path,
        module,
        payload=changed,
        directory_name="second-processed",
    )
    first_output = _output_dir(module, "label-free-first")
    second_output = _output_dir(module, "label-free-second")
    try:
        first = module.preflight_iohunter_matrix(
            first_root,
            first_output,
            memory_budget_bytes=256 * 1024 * 1024,
        )
        second = module.preflight_iohunter_matrix(
            second_root,
            second_output,
            memory_budget_bytes=256 * 1024 * 1024,
        )

        def row(matrix, method_id):
            return next(
                item
                for item in matrix.rows
                if item.campaign == "russia"
                and item.seed == 42
                and item.split_policy == "official_fold"
                and item.method_id == method_id
            )

        first_discovery = row(first, "dense_cosine_leiden")
        second_discovery = row(second, "dense_cosine_leiden")
        assert first_discovery.input_fingerprints == second_discovery.input_fingerprints
        assert first_discovery.execution_id == second_discovery.execution_id
        assert first_discovery.evaluation_fingerprints != second_discovery.evaluation_fingerprints
        assert first_discovery.run_id != second_discovery.run_id

        first_detection = row(first, module.HEURISTIC_BASELINE_ID)
        second_detection = row(second, module.HEURISTIC_BASELINE_ID)
        assert first_detection.input_fingerprints != second_detection.input_fingerprints
        assert first_detection.execution_id != second_detection.execution_id
    finally:
        shutil.rmtree(first_output, ignore_errors=True)
        shutil.rmtree(second_output, ignore_errors=True)


def test_time_methods_are_blocked_while_compact_static_discovery_methods_are_ready(tmp_path):
    module = _load_experiments()
    dataset_root = _dataset_root(tmp_path, module)
    output = _output_dir(module, "blocked")
    try:
        matrix = module.preflight_iohunter_matrix(dataset_root, output, memory_budget_bytes=256 * 1024 * 1024)
        time_rows = [row for row in matrix.rows if row.split_policy == "observed_time_holdout"]
        assert time_rows and all(row.status == "blocked" for row in time_rows)
        assert all("observed timestamps" in row.reason for row in time_rows)
        tgn_rows = [row for row in matrix.rows if row.method_id == "tgn_style_memory_prior"]
        assert tgn_rows and all(row.status == "blocked" for row in tgn_rows)
        assert all("observed_time_holdout" in row.reason or "observed timestamps" in row.reason for row in tgn_rows)
        registry = module.default_baseline_registry()
        unavailable = {
            spec.method_id
            for spec in registry.specs()
            if registry.implementation(spec.method_id).unavailable_reason is not None
        }
        assert unavailable
        assert all(row.status == "blocked" for row in matrix.rows if row.method_id in unavailable)
        ready = [row for row in matrix.rows if row.status == "ready"]
        assert ready
        assert {row.method_id for row in ready} == {
            "tsgs_mhcr_compact",
            "frozen_system_evidence_prior",
            "edgebank",
            "dense_cosine_leiden",
            "no_tsgs",
            "no_mhcr",
            "no_relation_specific",
        }
        assert {row.split_policy for row in ready} == {"official_fold"}
        detection_rows = [row for row in matrix.rows if row.stage == "detection"]
        assert detection_rows and all(row.status == "blocked" for row in detection_rows)
        official_detection_rows = [
            row for row in detection_rows if row.split_policy == "official_fold"
        ]
        assert official_detection_rows
        assert all("harmful_cib_detection" in row.reason for row in official_detection_rows)
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_matrix_records_external_account_recovery_claim_boundary(tmp_path):
    module = _load_experiments()
    dataset_root = _dataset_root(tmp_path, module)
    output = _output_dir(module, "claims")
    try:
        matrix = module.preflight_iohunter_matrix(dataset_root, output, memory_budget_bytes=256 * 1024 * 1024)
        scope = matrix.evaluation_scope
        assert "external account-recovery evaluation" in scope
        assert "not ground-truth coordination edges" in scope
        assert "campaign communities" in scope
        assert "causal coordination claims" in scope
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_atomic_manifests_preserve_matching_completed_runs_for_resume(tmp_path):
    module = _load_experiments()
    dataset_root = _dataset_root(tmp_path, module)
    output = _output_dir(module, "resume")
    try:
        first = module.preflight_iohunter_matrix(dataset_root, output, memory_budget_bytes=256 * 1024 * 1024)
        ready = next(row for row in first.rows if row.status == "ready")
        run_manifest_path = Path(ready.run_manifest_path)
        run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        run_manifest["execution_status"] = "complete"
        run_manifest["completion_fingerprint"] = "sha256:" + "a" * 64
        run_manifest_path.write_text(json.dumps(run_manifest, sort_keys=True), encoding="utf-8")

        second = module.preflight_iohunter_matrix(dataset_root, output, memory_budget_bytes=256 * 1024 * 1024)
        persisted = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        top = json.loads((output / "matrix_manifest.json").read_text(encoding="utf-8"))
        top_row = next(row for row in top["rows"] if row["run_id"] == ready.run_id)
        assert second.matrix_fingerprint == first.matrix_fingerprint
        assert persisted["execution_status"] == "complete"
        assert persisted["completion_fingerprint"] == "sha256:" + "a" * 64
        assert top_row["resume_action"] == "skip_complete"
        assert not tuple(output.rglob("*.tmp"))
    finally:
        shutil.rmtree(output, ignore_errors=True)


@pytest.mark.parametrize(
    "candidate",
    [
        r"C:\\tmp\\preflight",
        r"G:\\CISCN\\CogGuard\\.worktrees\\refactor-system\\system\\output\\sibling",
        r"G:\\CISCN\\CogGuard\\.worktrees\\refactor-system\\system\\output\\coordination_two_stage_reproduction\\..\\escape",
    ],
)
def test_preflight_rejects_non_g_sibling_and_traversal_outputs(candidate):
    module = _load_experiments()
    with pytest.raises(ValueError, match="canonical G-drive reproduction output root"):
        module.validate_iohunter_preflight_output_dir(candidate)


def test_preflight_rejects_canonical_root_itself_because_output_must_be_descendant():
    module = _load_experiments()
    with pytest.raises(ValueError, match="descendant"):
        module.validate_iohunter_preflight_output_dir(module.CANONICAL_REPRODUCTION_OUTPUT_ROOT)


def test_preflight_cli_accepts_explicit_fixture_root_and_writes_json_only_under_g(tmp_path, capsys):
    module = _load_experiments()
    dataset_root = _dataset_root(tmp_path, module)
    output = _output_dir(module, "cli")
    script_path = PROJECT_ROOT / "backend" / "scripts" / "run_coordination_iohunter_preflight.py"
    spec = importlib.util.spec_from_file_location("task7a_preflight_cli", script_path)
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    try:
        assert script.main([
            "--dataset-root", str(dataset_root),
            "--output", str(output),
            "--memory-budget-bytes", str(256 * 1024 * 1024),
        ]) == 0
        summary = json.loads(capsys.readouterr().out)
        assert summary["status"] == "preflight_only_no_models_executed"
        assert Path(summary["output"]).resolve() == output.resolve()
        assert tuple(output.rglob("*.json"))
        assert not tuple(path for path in output.rglob("*") if path.is_file() and path.suffix != ".json")
    finally:
        shutil.rmtree(output, ignore_errors=True)
