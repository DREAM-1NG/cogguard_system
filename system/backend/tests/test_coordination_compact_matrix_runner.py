from __future__ import annotations

import gc
import hashlib
import importlib
import importlib.util
import json
import pickle
import shutil
import sys
import tracemalloc
import types
import uuid
import weakref
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


def _payload(*, labels=(0, 1, 0, 1, 0, 1)):
    node_count = len(labels)

    def graph(edges=()):
        value = nx.Graph()
        value.add_nodes_from(range(node_count))
        value.add_edges_from(edges)
        return value

    partitions = (
        ((0, 1), (2, 3), (4, 5)),
        ((2, 3), (4, 5), (0, 1)),
        ((4, 5), (0, 1), (2, 3)),
        ((0, 3), (1, 4), (2, 5)),
        ((1, 2), (3, 4), (0, 5)),
    )
    splits = {
        fold_id: {
            name: np.asarray([index in members for index in range(node_count)], dtype=np.bool_)
            for name, members in (("train", train), ("val", validation), ("test", test))
        }
        for fold_id, (train, validation, test) in enumerate(partitions)
    }
    return {
        "graph": graph([(0, 1), (1, 2), (3, 4)]),
        "coRT": graph([(0, 1, {"weight": 2.0}), (1, 2, {"weight": 1.0})]),
        "coURL": graph([(1, 2, {"weight": 3.0})]),
        "hashSeq": graph([(2, 3, {"weight": 4.0})]),
        "fastRT": graph([(3, 4, {"weight": 5.0})]),
        "tweetSim": graph([(4, 5, {"weight": 0.75})]),
        "labels": np.asarray(labels, dtype=np.float64),
        "splits": splits,
    }


def _dataset_root(tmp_path: Path, campaigns=("russia",), *, labels=None) -> Path:
    root = tmp_path / "processed"
    raw = pickle.dumps(_payload(labels=labels) if labels is not None else _payload())
    for campaign in campaigns:
        source = root / campaign / "0.7_datasets.pkl"
        source.parent.mkdir(parents=True)
        source.write_bytes(raw)
    return root


def _output_dir(package, name: str) -> Path:
    return package.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-task7c-{name}-{uuid.uuid4().hex}"


def _claim_provenance(package, seed: int) -> dict[str, object]:
    fold_index = package.IOHUNTER_COMPACT_SEEDS.index(seed)
    return {
        "source_layer_fingerprint": "sha256:" + "a" * 64,
        "source_sha256": "sha256:" + "b" * 64,
        "evaluator_fingerprint": "sha256:" + "c" * 64,
        "fold_fingerprint": "sha256:" + str(fold_index + 1) * 64,
        "evaluation_scope": "external_account_recovery_not_coordination_ground_truth",
    }


def _run_one(package, dataset_root: Path, output: Path, **kwargs):
    return package.run_compact_iohunter_matrix(
        dataset_root,
        output,
        campaigns=("russia",),
        seeds=(42,),
        methods=("edgebank",),
        memory_budget_bytes=256 * 1024 * 1024,
        bootstrap_resamples=100,
        **kwargs,
    )


def test_compact_matrix_api_and_exact_canonical_identity():
    package = _load_experiments()

    coordinates = package.compact_iohunter_matrix_coordinates()

    assert package.IOHUNTER_COMPACT_CAMPAIGNS == ("china", "cuba", "iran", "russia", "UAE", "venezuela")
    assert package.IOHUNTER_COMPACT_SEEDS == (42, 43, 44, 45, 46)
    assert package.IOHUNTER_COMPACT_CLAIM_SCHEMA_VERSION == (
        "cogguard.iohunter-compact-claims/v2"
    )
    assert package.IOHUNTER_COMPACT_METHODS == (
        "tsgs_mhcr_compact",
        "frozen_system_evidence_prior",
        "edgebank",
        "dense_cosine_leiden",
        "no_tsgs",
        "no_mhcr",
        "no_relation_specific",
    )
    assert len(coordinates) == 6 * 5 * 7
    assert len(set(coordinates)) == len(coordinates)
    assert {(row.seed, row.fold_id) for row in coordinates} == {
        (42, "fold-000"),
        (43, "fold-001"),
        (44, "fold-002"),
        (45, "fold-003"),
        (46, "fold-004"),
    }


def test_execution_precedes_label_fold_and_evaluator_construction_for_mixed_resume_runs(
    tmp_path, monkeypatch
):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    compact_module = importlib.import_module("research.coordination_experiments.iohunter_compact")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "ordering")
    first = _run_one(package, dataset_root, output)
    assert first.resume_counts == {"executed": 1}
    events = []
    original_execute = matrix_module.execute_compact_discovery_method
    original_labels = compact_module._labels
    original_folds = compact_module._folds
    original_post_init = compact_module.CompactIOHunterEvaluator.__post_init__

    def observed_execute(*args, **kwargs):
        events.append("execute")
        return original_execute(*args, **kwargs)

    def observed_labels(*args, **kwargs):
        events.append("labels")
        return original_labels(*args, **kwargs)

    def observed_folds(*args, **kwargs):
        events.append("folds")
        return original_folds(*args, **kwargs)

    def observed_post_init(self):
        events.append("evaluator")
        return original_post_init(self)

    monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", observed_execute)
    monkeypatch.setattr(compact_module, "_labels", observed_labels)
    monkeypatch.setattr(compact_module, "_folds", observed_folds)
    monkeypatch.setattr(compact_module.CompactIOHunterEvaluator, "__post_init__", observed_post_init)
    try:
        result = package.run_compact_iohunter_matrix(
            dataset_root,
            output,
            campaigns=("russia",),
            seeds=(42,),
            methods=("edgebank", "tsgs_mhcr_compact"),
            memory_budget_bytes=256 * 1024 * 1024,
            bootstrap_resamples=100,
        )
        row_path = Path(result.rows[0]["row_path"])
        persisted = json.loads(row_path.read_text(encoding="utf-8"))
        serialized = json.dumps(persisted, sort_keys=True).lower()

        assert events[0] == "execute"
        assert "labels" in events
        assert "folds" in events
        assert "evaluator" in events
        assert events.index("execute") < events.index("labels") < events.index("folds") < events.index("evaluator")
        assert result.resume_counts == {"executed": 1, "resumed": 1}
        assert persisted["status"] == "success"
        assert persisted["evaluation_scope"] == "external_account_recovery_not_coordination_ground_truth"
        assert persisted["prediction_artifact_identity"].startswith("sha256:")
        assert persisted["execution_input_fingerprint"].startswith("sha256:")
        assert persisted["row_checksum"].startswith("sha256:")
        assert "candidate_endpoints" not in serialized
        assert "cluster_assignments" not in serialized
        assert "account_labels" not in serialized
        assert "train_indices" not in serialized
        assert not tuple(output.rglob("*.tmp"))
        assert (output / "matrix_manifest.json").is_file()
        assert (output / "aggregate_table.json").is_file()
        assert (output / "aggregate_table.csv").is_file()
        assert (output / "claim_decisions.json").is_file()
        manifest = json.loads((output / "matrix_manifest.json").read_text(encoding="utf-8"))
        assert manifest["rows"][0]["file_checksum"] == (
            "sha256:" + hashlib.sha256(row_path.read_bytes()).hexdigest()
        )
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_complete_checksum_valid_row_resumes_without_recomputation(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "resume")
    try:
        first = _run_one(package, dataset_root, output)
        row_path = Path(first.rows[0]["row_path"])
        before = row_path.read_bytes()
        first_manifest = json.loads((output / "matrix_manifest.json").read_text(encoding="utf-8"))

        def forbidden_execute(*args, **kwargs):
            raise AssertionError("completed run was recomputed")

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", forbidden_execute)
        second = _run_one(package, dataset_root, output)

        assert second.status_counts == {"success": 1}
        assert second.resume_counts == {"resumed": 1}
        assert row_path.read_bytes() == before
        second_manifest = json.loads((output / "matrix_manifest.json").read_text(encoding="utf-8"))
        assert first.manifest_fingerprint == second.manifest_fingerprint
        assert first_manifest["manifest_fingerprint"] == second_manifest["manifest_fingerprint"]
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_predictions_are_spooled_and_released_before_evaluator_loading(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "prediction-spool-release")
    original_execute = matrix_module.execute_compact_discovery_method
    original_evaluator_load = matrix_module.load_compact_iohunter_evaluator_result
    prediction_arrays = []

    def observed_execute(*args, **kwargs):
        outcome = original_execute(*args, **kwargs)
        if outcome.prediction is not None:
            prediction_arrays.append(weakref.ref(outcome.prediction.account_scores))
        return outcome

    def observed_evaluator_load(*args, **kwargs):
        gc.collect()
        assert prediction_arrays
        assert all(reference() is None for reference in prediction_arrays)
        artifacts = tuple((output / "p").rglob("*.json"))
        arrays = tuple((output / "p").rglob("*.bin"))
        assert len(artifacts) == 2
        assert len(arrays) == 2
        return original_evaluator_load(*args, **kwargs)

    monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", observed_execute)
    monkeypatch.setattr(matrix_module, "load_compact_iohunter_evaluator_result", observed_evaluator_load)
    try:
        result = package.run_compact_iohunter_matrix(
            dataset_root,
            output,
            campaigns=("russia",),
            seeds=(42,),
            methods=("edgebank", "no_mhcr"),
            memory_budget_bytes=256 * 1024 * 1024,
            bootstrap_resamples=20,
        )

        assert result.status_counts == {"success": 2}
        for row in result.rows:
            descriptor = row["prediction_artifact"]
            assert descriptor["schema_version"] == "cogguard.compact-discovery-prediction-artifact/v1"
            assert Path(descriptor["metadata_path"]).drive.upper() == "G:"
            assert Path(descriptor["arrays_path"]).drive.upper() == "G:"
            assert descriptor["metadata_checksum"].startswith("sha256:")
            assert descriptor["arrays_checksum"].startswith("sha256:")
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_valid_prediction_artifact_recovers_without_discovery_recomputation(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "prediction-artifact-resume")
    original_evaluator_load = matrix_module.load_compact_iohunter_evaluator_result

    def unavailable_evaluator(*args, **kwargs):
        raise RuntimeError("simulated interruption before evaluation")

    monkeypatch.setattr(matrix_module, "load_compact_iohunter_evaluator_result", unavailable_evaluator)
    try:
        first = _run_one(package, dataset_root, output)
        assert first.status_counts == {"failed": 1}
        descriptor = first.rows[0]["prediction_artifact"]
        assert Path(descriptor["metadata_path"]).is_file()
        assert Path(descriptor["arrays_path"]).is_file()

        monkeypatch.setattr(matrix_module, "load_compact_iohunter_evaluator_result", original_evaluator_load)

        def forbidden_execute(*args, **kwargs):
            raise AssertionError("valid prediction artifact was recomputed")

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", forbidden_execute)
        second = _run_one(package, dataset_root, output)

        assert second.status_counts == {"success": 1}
        assert second.resume_counts == {"rewritten": 1}
        assert second.rows[0]["prediction_artifact_identity"] == descriptor["artifact_identity"]
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_corrupt_prediction_artifact_invalidates_completed_row_and_is_rewritten(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "prediction-artifact-corrupt")
    try:
        first = _run_one(package, dataset_root, output)
        descriptor = first.rows[0]["prediction_artifact"]
        arrays_path = Path(descriptor["arrays_path"])
        arrays_path.write_bytes(b"corrupt")
        calls = 0
        original_execute = matrix_module.execute_compact_discovery_method

        def counted_execute(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original_execute(*args, **kwargs)

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", counted_execute)
        second = _run_one(package, dataset_root, output)

        assert calls == 1
        assert second.resume_counts == {"rewritten": 1}
        rewritten = second.rows[0]["prediction_artifact"]
        assert matrix_module._file_checksum(Path(rewritten["arrays_path"])) == rewritten["arrays_checksum"]
    finally:
        shutil.rmtree(output, ignore_errors=True)


@pytest.mark.parametrize("metadata_payload", ["[]", "null"])
def test_non_object_prediction_metadata_is_recomputed_instead_of_aborting(
    tmp_path, monkeypatch, metadata_payload
):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "prediction-metadata-not-object")
    try:
        first = _run_one(package, dataset_root, output)
        metadata_path = Path(first.rows[0]["prediction_artifact"]["metadata_path"])
        metadata_path.write_text(metadata_payload, encoding="utf-8")
        calls = 0
        original_execute = matrix_module.execute_compact_discovery_method

        def counted_execute(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original_execute(*args, **kwargs)

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", counted_execute)
        second = _run_one(package, dataset_root, output)

        assert calls == 1
        assert second.status_counts == {"success": 1}
        assert second.resume_counts == {"rewritten": 1}
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_non_finite_prediction_runtime_is_recomputed_instead_of_aborting(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "prediction-runtime-non-finite")
    try:
        first = _run_one(package, dataset_root, output)
        metadata_path = Path(first.rows[0]["prediction_artifact"]["metadata_path"])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["runtime_seconds"] = "__NON_FINITE_RUNTIME__"
        metadata_payload = json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2)
        metadata_path.write_text(
            metadata_payload.replace('"__NON_FINITE_RUNTIME__"', "1e309") + "\n",
            encoding="utf-8",
        )
        calls = 0
        original_execute = matrix_module.execute_compact_discovery_method

        def counted_execute(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original_execute(*args, **kwargs)

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", counted_execute)
        second = _run_one(package, dataset_root, output)

        assert calls == 1
        assert second.status_counts == {"success": 1}
        assert second.resume_counts == {"rewritten": 1}
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_self_checksummed_structural_artifact_damage_is_recomputed(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "prediction-artifact-structural-damage")
    try:
        first = _run_one(package, dataset_root, output)
        metadata_path = Path(first.rows[0]["prediction_artifact"]["metadata_path"])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["array_layout"].pop("account_scores")
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        calls = 0
        original_execute = matrix_module.execute_compact_discovery_method

        def counted_execute(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original_execute(*args, **kwargs)

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", counted_execute)
        second = _run_one(package, dataset_root, output)

        assert calls == 1
        assert second.status_counts == {"success": 1}
    finally:
        shutil.rmtree(output, ignore_errors=True)


@pytest.mark.parametrize(
    ("provenance_field", "stale_value"),
    (
        ("source_dataset", "iohunter-china"),
        ("data_fingerprint", "sha256:" + ("0" * 64)),
    ),
)
def test_stale_prediction_provenance_is_recomputed_before_evaluation(
    tmp_path, monkeypatch, provenance_field, stale_value
):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, f"stale-prediction-{provenance_field}")
    try:
        first = _run_one(package, dataset_root, output)
        descriptor = first.rows[0]["prediction_artifact"]
        metadata_path = Path(descriptor["metadata_path"])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        original_identity = metadata["artifact_identity"]
        metadata["discovered_cluster_batch"]["provenance"][provenance_field] = stale_value
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

        executions = 0
        evaluated_provenance = []
        original_execute = matrix_module.execute_compact_discovery_method
        original_evaluate = matrix_module.evaluate_iohunter_external_account_recovery

        def counted_execute(*args, **kwargs):
            nonlocal executions
            executions += 1
            return original_execute(*args, **kwargs)

        def observed_evaluate(prediction, *args, **kwargs):
            provenance = prediction.discovered_cluster_batch.provenance
            evaluated_provenance.append((provenance.source_dataset, provenance.data_fingerprint))
            return original_evaluate(prediction, *args, **kwargs)

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", counted_execute)
        monkeypatch.setattr(matrix_module, "evaluate_iohunter_external_account_recovery", observed_evaluate)
        second = _run_one(package, dataset_root, output)

        assert metadata["artifact_identity"] == original_identity
        assert executions == 1
        assert evaluated_provenance == [
            (
                "iohunter-russia",
                second.rows[0]["source_layer_fingerprint"],
            )
        ]
        assert second.status_counts == {"success": 1}
        assert second.resume_counts == {"rewritten": 1}
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_prediction_bundle_loads_read_only_memory_maps_without_array_copies(tmp_path):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "prediction-artifact-memmap")
    try:
        first = _run_one(package, dataset_root, output)
        descriptor = first.rows[0]["prediction_artifact"]
        metadata = json.loads(Path(descriptor["metadata_path"]).read_text(encoding="utf-8"))
        prediction = matrix_module._load_prediction_artifact(
            output,
            package.CompactMatrixCoordinate("russia", 42, "fold-000", "edgebank"),
            metadata,
        )

        assert metadata["storage_format"] == "raw_array_bundle_v1"
        assert all(
            isinstance(getattr(prediction, field_name), np.memmap)
            and not getattr(prediction, field_name).flags.writeable
            for field_name in (
                "candidate_endpoints",
                "edge_scores",
                "account_scores",
                "cluster_assignments",
            )
        )
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_compact_array_identity_hashes_in_bounded_chunks():
    _load_experiments()
    execution_module = importlib.import_module("research.coordination_experiments.compact_execution")
    array = np.zeros(24 * 1024 * 1024, dtype=np.uint8)
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        digest = execution_module._array_digest(array)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert digest.startswith("sha256:")
    assert peak < 2 * 1024 * 1024


def test_stale_row_identity_is_rewritten_from_valid_prediction_artifact(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "stale-run-identity")
    try:
        first = _run_one(package, dataset_root, output)
        row_path = Path(first.rows[0]["row_path"])
        row = json.loads(row_path.read_text(encoding="utf-8"))
        row["run_identity"] = "sha256:" + ("0" * 64)
        row["row_checksum"] = matrix_module._row_checksum(row)
        row_path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        manifest_path = output / "matrix_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["rows"][0]["row_payload_checksum"] = row["row_checksum"]
        manifest["rows"][0]["file_checksum"] = "sha256:" + hashlib.sha256(row_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        calls = 0
        original_execute = matrix_module.execute_compact_discovery_method

        def counted_execute(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original_execute(*args, **kwargs)

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", counted_execute)
        second = _run_one(package, dataset_root, output)

        assert calls == 0
        assert second.resume_counts == {"rewritten": 1}
    finally:
        shutil.rmtree(output, ignore_errors=True)


@pytest.mark.parametrize("damage", ["corrupt", "stale"])
def test_corrupt_or_stale_rows_are_rewritten_from_valid_prediction_artifacts(
    tmp_path, monkeypatch, damage
):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, f"rewrite-{damage}")
    try:
        first = _run_one(package, dataset_root, output)
        row_path = Path(first.rows[0]["row_path"])
        if damage == "corrupt":
            row_path.write_text("{broken", encoding="utf-8")
        else:
            payload = json.loads(row_path.read_text(encoding="utf-8"))
            payload["schema_version"] = "stale-schema"
            row_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        calls = 0
        original_execute = matrix_module.execute_compact_discovery_method

        def counted_execute(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original_execute(*args, **kwargs)

        monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", counted_execute)
        second = _run_one(package, dataset_root, output)
        rewritten = json.loads(row_path.read_text(encoding="utf-8"))

        assert calls == 0
        assert second.resume_counts == {"rewritten": 1}
        assert rewritten["schema_version"] == package.IOHUNTER_COMPACT_ROW_SCHEMA_VERSION
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_source_change_between_discovery_execution_and_evaluator_load_fails_coherently(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    source = dataset_root / "russia" / "0.7_datasets.pkl"
    output = _output_dir(package, "source-swap")
    original_execute = matrix_module.execute_compact_discovery_method
    mutated = False

    def mutate_after_execution(*args, **kwargs):
        nonlocal mutated
        outcome = original_execute(*args, **kwargs)
        if not mutated:
            source.write_bytes(pickle.dumps(_payload(labels=(1, 0, 1, 0, 1, 0)), protocol=pickle.HIGHEST_PROTOCOL))
            mutated = True
        return outcome

    monkeypatch.setattr(matrix_module, "execute_compact_discovery_method", mutate_after_execution)
    try:
        result = _run_one(package, dataset_root, output)
        row = result.rows[0]

        assert mutated is True
        assert row["status"] == "failed"
        assert "source changed between Discovery and evaluator phases" in row["reason"]
        assert row["source_sha256"] == result.rows[0]["source_sha256"]
        assert row["evaluator_fingerprint"] is None
        assert row["proxy_metrics"] == {}
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_dense_limit_blocks_without_subsampling_or_evaluator_access(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "dense-block")

    def forbidden_evaluator(*args, **kwargs):
        raise AssertionError("blocked execution accessed evaluator")

    monkeypatch.setattr(matrix_module, "IOHunterExternalEvaluationInput", forbidden_evaluator)
    try:
        result = package.run_compact_iohunter_matrix(
            dataset_root,
            output,
            campaigns=("russia",),
            seeds=(42,),
            methods=("dense_cosine_leiden",),
            method_config_overrides={"dense_cosine_leiden": {"dense_feasible_account_limit": 4}},
            memory_budget_bytes=256 * 1024 * 1024,
            bootstrap_resamples=50,
        )

        assert result.status_counts == {"blocked": 1}
        assert "feasibility limit 4" in result.rows[0]["reason"]
        assert result.rows[0]["account_count"] == 6
        assert result.rows[0]["prediction_artifact_identity"] is None
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_combined_discovery_prediction_and_evaluator_memory_blocks_before_evaluation(tmp_path):
    package = _load_experiments()
    dataset_root = _dataset_root(tmp_path)
    source = dataset_root / "russia" / "0.7_datasets.pkl"
    high_budget = 256 * 1024 * 1024
    discovery = package.load_compact_iohunter_discovery(
        source,
        campaign="russia",
        trusted_local=True,
        memory_budget_bytes=high_budget,
    )
    combined = package.load_compact_iohunter(
        source,
        campaign="russia",
        trusted_local=True,
        memory_budget_bytes=high_budget,
    )
    budget = combined.memory_profile.estimated_peak_bytes - 1
    assert budget >= discovery.memory_profile.estimated_peak_bytes
    output = _output_dir(package, "combined-memory")
    try:
        result = package.run_compact_iohunter_matrix(
            dataset_root,
            output,
            campaigns=("russia",),
            seeds=(42,),
            methods=("edgebank",),
            memory_budget_bytes=budget,
            bootstrap_resamples=100,
        )
        row = result.rows[0]

        assert row["status"] == "failed"
        assert "combined compact IOHunter evaluator memory" in row["reason"]
        assert row["memory_profile"]["estimated_peak_bytes"] > budget
        assert row["peak_memory_bytes"] >= row["memory_profile"]["estimated_peak_bytes"]
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_load_budget_blocks_every_coordinate_and_counts_actions(tmp_path):
    package = _load_experiments()
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "load-budget")
    try:
        result = package.run_compact_iohunter_matrix(
            dataset_root,
            output,
            campaigns=("russia",),
            seeds=(42,),
            methods=("tsgs_mhcr_compact", "edgebank"),
            memory_budget_bytes=1,
            bootstrap_resamples=10,
        )

        assert len(result.rows) == 2
        assert result.status_counts == {"blocked": 2}
        assert result.resume_counts == {"executed": 2}
        assert all("before model execution" in row["reason"] for row in result.rows)
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_selected_rows_preserve_canonical_campaign_order(tmp_path):
    package = _load_experiments()
    dataset_root = _dataset_root(tmp_path, campaigns=package.IOHUNTER_COMPACT_CAMPAIGNS)
    output = _output_dir(package, "canonical-order")
    try:
        result = package.run_compact_iohunter_matrix(
            dataset_root,
            output,
            seeds=(42,),
            methods=("edgebank",),
            memory_budget_bytes=256 * 1024 * 1024,
            bootstrap_resamples=10,
        )

        assert tuple(row["campaign"] for row in result.rows) == package.IOHUNTER_COMPACT_CAMPAIGNS
    finally:
        shutil.rmtree(output, ignore_errors=True)


@pytest.mark.parametrize(
    "candidate",
    [
        r"C:\\tmp\\matrix",
        r"G:\\CISCN\\CogGuard\\.worktrees\\refactor-system\\system\\output\\sibling",
        r"G:\\CISCN\\CogGuard\\.worktrees\\refactor-system\\system\\output\\coordination_two_stage_reproduction\\..\\escape",
        "relative-matrix",
    ],
)
def test_matrix_rejects_c_relative_sibling_and_traversal_outputs(candidate):
    package = _load_experiments()
    with pytest.raises(ValueError, match="canonical G-drive reproduction output root"):
        package.validate_compact_matrix_output_dir(candidate)


def test_aggregates_are_deterministic_use_sample_std_and_pair_campaign_seed_rows():
    package = _load_experiments()
    rows = []
    for campaign, candidate, baseline in (("china", (0.8, 0.6), (0.3, 0.4)), ("russia", (0.7, 0.5), (0.2, 0.2))):
        for offset, seed in enumerate((42, 43)):
            for method, values in (("tsgs_mhcr_compact", candidate), ("edgebank", baseline)):
                rows.append({
                    "campaign": campaign,
                    "seed": seed,
                    "fold_id": f"fold-{offset:03d}",
                    "method_id": method,
                    "status": "success",
                    "proxy_metrics": {"external_account_macro_f1": values[offset]},
                    **_claim_provenance(package, seed),
                })

    first = package.aggregate_compact_matrix_rows(rows, bootstrap_seed=11, bootstrap_resamples=200)
    second = package.aggregate_compact_matrix_rows(rows, bootstrap_seed=11, bootstrap_resamples=200)
    decisions = package.build_compact_claim_decisions(rows, bootstrap_seed=11, bootstrap_resamples=200)
    china = next(row for row in first if row["scope"] == "campaign" and row["campaign"] == "china" and row["method_id"] == "tsgs_mhcr_compact")
    overall = next(row for row in first if row["scope"] == "matrix" and row["method_id"] == "tsgs_mhcr_compact")
    paired = next(row for row in decisions["paired_external_account_proxy"] if row["metric_name"] == "external_account_macro_f1")

    assert first == second
    assert china["count"] == 2
    assert china["sample_std"] == pytest.approx(np.std([0.8, 0.6], ddof=1))
    assert overall["count"] == 4
    assert paired["pair_count"] == 4
    assert paired["decision"] == "blocked_incomplete_matrix"
    assert paired["required_pair_count"] == 30
    assert paired["missing_pair_count"] == 26
    assert paired["inference_unit"] == "campaign_mean_over_seed_fold_pairs"
    assert paired["campaign_count"] == 2
    assert paired["claim_scope"] == "external_account_recovery_not_coordination_ground_truth"


def test_claim_decisions_compare_candidate_with_frozen_system_separately_from_edgebank():
    package = _load_experiments()
    rows = []
    for campaign in package.IOHUNTER_COMPACT_CAMPAIGNS:
        for seed in package.IOHUNTER_COMPACT_SEEDS:
            for method_id, score in (
                ("tsgs_mhcr_compact", 0.65),
                ("edgebank", 0.50),
                ("frozen_system_evidence_prior", 0.70),
            ):
                rows.append(
                    {
                        "campaign": campaign,
                        "seed": seed,
                        "fold_id": f"fold-{package.IOHUNTER_COMPACT_SEEDS.index(seed):03d}",
                        "method_id": method_id,
                        "status": "success",
                        "proxy_metrics": {"external_account_auprc": score},
                        "runtime_seconds": 2.0 if method_id == "tsgs_mhcr_compact" else 1.0,
                        **_claim_provenance(package, seed),
                    }
                )

    decisions = package.build_compact_claim_decisions(
        rows, bootstrap_seed=11, bootstrap_resamples=200
    )
    system = {
        row["metric_name"]: row
        for row in decisions["paired_frozen_system_proxy"]
    }["external_account_auprc"]

    assert system["candidate_method_id"] == "tsgs_mhcr_compact"
    assert system["baseline_method_id"] == "frozen_system_evidence_prior"
    assert system["pair_count"] == 30
    assert system["campaign_count"] == 6
    assert system["inference_unit"] == "campaign_mean_over_seed_fold_pairs"
    assert system["provenance_mismatch_count"] == 0
    assert system["mean_candidate_minus_baseline"] == pytest.approx(-0.05)
    assert system["decision"] == "not_supported"
    runtime = decisions["paired_frozen_system_runtime"]
    assert runtime["mean_candidate_minus_baseline_seconds"] == pytest.approx(1.0)
    assert runtime["decision"] == "blocked_noncomparable_measurement_boundary"
    assert runtime["measurement_boundary_comparable"] is False


def test_frozen_system_claim_blocks_mismatched_pair_provenance():
    package = _load_experiments()
    rows = []
    for campaign in package.IOHUNTER_COMPACT_CAMPAIGNS:
        for seed in package.IOHUNTER_COMPACT_SEEDS:
            provenance = _claim_provenance(package, seed)
            for method_id in ("tsgs_mhcr_compact", "frozen_system_evidence_prior"):
                row_provenance = dict(provenance)
                if campaign == "china" and seed == 42 and method_id == "frozen_system_evidence_prior":
                    row_provenance["fold_fingerprint"] = "sha256:" + "f" * 64
                rows.append(
                    {
                        "campaign": campaign,
                        "seed": seed,
                        "fold_id": f"fold-{package.IOHUNTER_COMPACT_SEEDS.index(seed):03d}",
                        "method_id": method_id,
                        "status": "success",
                        "proxy_metrics": {"external_account_auprc": 0.7},
                        "runtime_seconds": 1.0,
                        **row_provenance,
                    }
                )

    decisions = package.build_compact_claim_decisions(rows, bootstrap_resamples=50)
    comparison = next(
        row
        for row in decisions["paired_frozen_system_proxy"]
        if row["metric_name"] == "external_account_auprc"
    )

    assert comparison["decision"] == "blocked_provenance_mismatch"
    assert comparison["provenance_mismatch_count"] == 1
    assert comparison["pair_count"] == 29


@pytest.mark.parametrize(
    "rows_factory",
    [
        lambda package: (),
        lambda package: [
            {
                "campaign": "russia",
                "seed": 42,
                "fold_id": "fold-000",
                "method_id": "tsgs_mhcr_compact",
                "status": "success",
                "proxy_metrics": {
                    "external_account_auprc": 0.7,
                    "external_account_macro_f1": 0.8,
                    "external_account_recall_at_k": 0.6,
                    "external_account_roc_auc": 0.65,
                    "external_account_evaluated_count": 100.0,
                },
            }
        ],
        lambda package: [
            {
                "campaign": "russia",
                "seed": 42,
                "fold_id": "fold-000",
                "method_id": "edgebank",
                "status": "success",
                "proxy_metrics": {
                    "external_account_auprc": 0.5,
                    "external_account_macro_f1": 0.4,
                    "external_account_recall_at_k": 0.45,
                    "external_account_roc_auc": 0.42,
                    "external_account_evaluated_count": 100.0,
                },
            }
        ],
    ],
)
def test_proxy_claims_are_explicitly_blocked_for_empty_and_one_sided_subsets(rows_factory):
    package = _load_experiments()
    rows = rows_factory(package)
    decisions = package.build_compact_claim_decisions(rows, bootstrap_seed=11, bootstrap_resamples=50)
    paired = {row["metric_name"]: row for row in decisions["paired_external_account_proxy"]}

    assert set(paired) == {
        "external_account_auprc",
        "external_account_macro_f1",
        "external_account_recall_at_k",
        "external_account_roc_auc",
    }
    assert all(row["decision"] == "blocked_incomplete_matrix" for row in paired.values())
    assert all(row["required_pair_count"] == 30 for row in paired.values())
    assert all(row["missing_pair_count"] == 30 for row in paired.values())
    assert "external_account_evaluated_count" not in paired


def test_proxy_claim_requires_complete_matrix_and_positive_paired_confidence_interval():
    package = _load_experiments()
    rows = []
    for campaign in package.IOHUNTER_COMPACT_CAMPAIGNS:
        for seed in package.IOHUNTER_COMPACT_SEEDS:
            for method_id, scores in (
                ("tsgs_mhcr_compact", {
                    "external_account_auprc": 0.7,
                    "external_account_macro_f1": 0.8,
                    "external_account_recall_at_k": 0.6,
                    "external_account_roc_auc": 0.65,
                }),
                ("edgebank", {
                    "external_account_auprc": 0.4,
                    "external_account_macro_f1": 0.4,
                    "external_account_recall_at_k": 0.3,
                    "external_account_roc_auc": 0.35,
                }),
            ):
                rows.append(
                    {
                        "campaign": campaign,
                        "seed": seed,
                        "fold_id": f"fold-{package.IOHUNTER_COMPACT_SEEDS.index(seed):03d}",
                        "method_id": method_id,
                        "status": "success",
                        "proxy_metrics": {**scores, "external_account_evaluated_count": 100.0},
                        **_claim_provenance(package, seed),
                    }
                )

    decisions = package.build_compact_claim_decisions(
        rows, bootstrap_seed=11, bootstrap_resamples=200
    )
    paired = decisions["paired_external_account_proxy"]

    assert [row["metric_name"] for row in paired] == [
        "external_account_auprc",
        "external_account_macro_f1",
        "external_account_recall_at_k",
        "external_account_roc_auc",
    ]
    assert all(row["pair_count"] == 30 for row in paired)
    assert all(row["missing_pair_count"] == 0 for row in paired)
    assert all(row["campaign_count"] == 6 for row in paired)
    assert all(row["inference_unit"] == "campaign_mean_over_seed_fold_pairs" for row in paired)
    assert all(row["ci_95_low"] > 0.0 for row in paired)
    assert all(row["decision"] == "supported_external_account_proxy_only" for row in paired)


def test_claim_decisions_fix_unsupported_research_scopes():
    package = _load_experiments()
    decisions = package.build_compact_claim_decisions((), bootstrap_resamples=10)
    blocked = {row["claim_id"]: row for row in decisions["fixed_blocked_claims"]}

    assert set(blocked) == {
        "harmful_cib_detection",
        "true_coordination_edge_community_recovery",
        "causal_campaign_claims",
        "observed_time_claims",
        "production_activation",
        "end_to_end_production_model_superiority",
        "method_peak_memory_superiority",
        "equal_compute_budget",
        "pure_cross_seed_stability",
    }
    assert all(row["decision"] == "blocked" and row["missing_capability"] for row in blocked.values())
    assert decisions["numerical_document_targets"] == []


def test_campaign_loads_are_released_before_the_next_campaign(tmp_path, monkeypatch):
    package = _load_experiments()
    matrix_module = importlib.import_module("research.coordination_experiments.compact_matrix_runner")
    dataset_root = _dataset_root(tmp_path, campaigns=("china", "russia"))
    output = _output_dir(package, "release")
    original_discovery_load = matrix_module.load_compact_iohunter_discovery
    original_evaluator_load = matrix_module.load_compact_iohunter_evaluator_result
    previous_discovery = None
    previous_evaluator = None
    discovery_calls = 0
    evaluator_calls = 0

    class DiscoveryBox:
        def __init__(self, loaded):
            self.discovery_view = loaded.discovery_view
            self.source_path = loaded.source_path
            self.source_sha256 = loaded.source_sha256
            self.memory_profile = loaded.memory_profile

    class EvaluatorBox:
        def __init__(self, loaded):
            self.evaluator = loaded.evaluator
            self.memory_profile = loaded.memory_profile

    def observed_discovery_load(*args, **kwargs):
        nonlocal previous_discovery, discovery_calls
        gc.collect()
        assert previous_discovery is None or previous_discovery() is None
        loaded = DiscoveryBox(original_discovery_load(*args, **kwargs))
        previous_discovery = weakref.ref(loaded)
        discovery_calls += 1
        return loaded

    def observed_evaluator_load(*args, **kwargs):
        nonlocal previous_evaluator, evaluator_calls
        gc.collect()
        assert previous_evaluator is None or previous_evaluator() is None
        loaded = EvaluatorBox(original_evaluator_load(*args, **kwargs))
        previous_evaluator = weakref.ref(loaded)
        evaluator_calls += 1
        return loaded

    monkeypatch.setattr(matrix_module, "load_compact_iohunter_discovery", observed_discovery_load)
    monkeypatch.setattr(matrix_module, "load_compact_iohunter_evaluator_result", observed_evaluator_load)
    try:
        result = package.run_compact_iohunter_matrix(
            dataset_root,
            output,
            campaigns=("china", "russia"),
            seeds=(42,),
            methods=("edgebank",),
            memory_budget_bytes=256 * 1024 * 1024,
            bootstrap_resamples=20,
        )
        assert len(result.rows) == 2
        assert discovery_calls == 2
        assert evaluator_calls == 2
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_cli_requires_g_output_and_prints_only_compact_json(tmp_path, capsys):
    package = _load_experiments()
    dataset_root = _dataset_root(tmp_path)
    output = _output_dir(package, "cli")
    script_path = PROJECT_ROOT / "backend" / "scripts" / "run_coordination_iohunter_matrix.py"
    spec = importlib.util.spec_from_file_location("task7c_matrix_cli", script_path)
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    try:
        exit_code = script.main([
            "--dataset-root", str(dataset_root),
            "--output", str(output),
            "--campaign", "russia",
            "--seed", "42",
            "--method", "edgebank",
            "--memory-budget-bytes", str(256 * 1024 * 1024),
            "--bootstrap-resamples", "20",
            "--method-config-override", "edgebank.max_candidate_edges=3",
        ])
        summary = json.loads(capsys.readouterr().out)

        assert exit_code == 0
        assert summary["row_count"] == 1
        assert summary["status_counts"] == {"success": 1}
        assert Path(summary["output"]).resolve() == output.resolve()
        assert set(summary) == {"manifest_fingerprint", "output", "resume_counts", "row_count", "status_counts"}
    finally:
        shutil.rmtree(output, ignore_errors=True)
