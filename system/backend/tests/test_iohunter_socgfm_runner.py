from __future__ import annotations

import importlib.util
import json
import sys
import types
import uuid
from pathlib import Path

import numpy as np
import pytest

from app.config import PROJECT_ROOT


def _load_module():
    research_name = "research"
    research_dir = PROJECT_ROOT / "research"
    if research_name not in sys.modules:
        package = types.ModuleType(research_name)
        package.__path__ = [str(research_dir)]
        sys.modules[research_name] = package

    package_name = "research.coordination_experiments"
    if package_name not in sys.modules:
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

    module_name = f"{package_name}.iohunter_socgfm"
    spec = importlib.util.spec_from_file_location(
        module_name,
        research_dir / "coordination_experiments" / "iohunter_socgfm.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_socgfm_config_and_command_keep_official_reproduction_boundary():
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-socgfm-config"
    config = module.SocGFMReproductionConfig(
        dataset="russia",
        output_dir=output,
        smoke=True,
    )

    command = module._build_official_command(config)

    assert command[1] == "run_with_mlflow.py"
    assert "--dataset" in command
    assert command[command.index("--dataset") + 1] == "russia"
    assert command[command.index("--splits") + 1] == "1"
    assert command[command.index("--epochs") + 1] == "1"
    assert command[command.index("--gnn") + 1] == "sage"
    assert output.drive.upper() == "G:"


def test_infoopsgfm_method_command_only_passes_supported_official_arguments():
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-gnn"
    config = module.SocGFMReproductionConfig(
        dataset="russia",
        output_dir=output,
        method="gnn",
        smoke=True,
    )

    command = module._build_official_command(config)

    assert command[1] == "run_with_mlflow.py"
    assert config.official_script_name == "run_GNN.py"
    assert "--most_pop" not in command
    assert "--min_tweets" not in command
    assert command[command.index("--gnn") + 1] == "sage"


def test_infoopsgfm_baseline_commands_match_each_upstream_parser_surface():
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-baselines"
    node2vec = module.SocGFMReproductionConfig(
        dataset="russia",
        output_dir=output / "node2vec",
        method="node2vec",
        smoke=True,
    )
    node_pruning = module.SocGFMReproductionConfig(
        dataset="russia",
        output_dir=output / "node-pruning",
        method="node_pruning",
        smoke=True,
    )

    node2vec_command = module._build_official_command(node2vec)
    pruning_command = module._build_official_command(node_pruning)

    assert node2vec.official_script_name == "run_Node2Vec.py"
    assert "--epochs" in node2vec_command
    assert "--latent" in node2vec_command
    assert "--gnn" not in node2vec_command
    assert node_pruning.official_script_name == "run_NodePruning.py"
    assert "--dataset" in pruning_command
    assert "--splits" in pruning_command
    assert "--epochs" not in pruning_command
    assert "--device" not in pruning_command


def test_infoopsgfm_baselines_default_to_the_clean_official_checkout():
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-clean-baselines"
    node2vec = module.SocGFMReproductionConfig(
        dataset="russia",
        output_dir=output / "node2vec",
        method="node2vec",
    )
    pruning = module.SocGFMReproductionConfig(
        dataset="russia",
        output_dir=output / "node-pruning",
        method="node_pruning",
    )
    gnn = module.SocGFMReproductionConfig(
        dataset="russia",
        output_dir=output / "gnn",
        method="gnn",
    )

    assert node2vec.execution_repository == module.DEFAULT_OFFICIAL_CLEAN_REPOSITORY
    assert pruning.execution_repository == module.DEFAULT_OFFICIAL_CLEAN_REPOSITORY
    assert gnn.execution_repository == module.DEFAULT_OFFICIAL_REPOSITORY


def test_infoopsgfm_baseline_rejects_modified_executed_source_before_running(monkeypatch):
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-dirty-baseline-{uuid.uuid4().hex}"
    output_dir = root / "output"
    try:
        monkeypatch.setattr(
            module,
            "_git_metadata",
            lambda repository, config: {
                "repository": str(repository),
                "commit": "abc123",
                "origin": "https://example.invalid/InfoOpsGFM.git",
                "dirty": True,
                "executed_source_files": [{"path": "src/run_NodePruning.py", "modified": True}],
                "executed_source_clean": False,
            },
        )
        monkeypatch.setattr(
            module,
            "same_country_preflight",
            lambda *args, **kwargs: {
                "ready": True,
                "dataset": "russia",
                "method": "node_pruning",
                "blockers": [],
            },
        )
        monkeypatch.setattr(
            module,
            "_copy_official_source",
            lambda *args, **kwargs: pytest.fail("dirty baseline must not enter the official sandbox"),
        )
        config = module.SocGFMReproductionConfig(
            dataset="russia",
            output_dir=output_dir,
            method="node_pruning",
            official_repository=module.DEFAULT_OFFICIAL_CLEAN_REPOSITORY,
        )

        manifest = module.run_socgfm_reproduction(config)

        assert manifest["status"] == "blocked"
        assert manifest["returncode"] is None
        assert manifest["failure_reason"].startswith("source_preflight_blocked:")
        assert manifest["official_git"]["executed_source_clean"] is False
        assert not (output_dir / "sandbox").exists()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_node2vec_blocks_known_windows_worker_path_before_sandbox(monkeypatch):
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-node2vec-windows-{uuid.uuid4().hex}"
    output_dir = root / "output"
    try:
        monkeypatch.setattr(module.os, "name", "nt")
        monkeypatch.delenv("COGGUARD_INFOOPSGFM_ALLOW_WINDOWS_NODE2VEC", raising=False)
        monkeypatch.setattr(
            module,
            "_git_metadata",
            lambda repository, config: {
                "repository": str(repository),
                "commit": "abc123",
                "origin": "https://example.invalid/InfoOpsGFM.git",
                "dirty": False,
                "executed_source_files": [{"path": "src/run_Node2Vec.py", "modified": False}],
                "executed_source_clean": True,
            },
        )
        monkeypatch.setattr(
            module,
            "_copy_official_source",
            lambda *args, **kwargs: pytest.fail("known Windows Node2Vec path must not enter the sandbox"),
        )
        config = module.SocGFMReproductionConfig(
            dataset="russia",
            output_dir=output_dir,
            method="node2vec",
            official_repository=module.DEFAULT_OFFICIAL_CLEAN_REPOSITORY,
        )

        manifest = module.run_socgfm_reproduction(config)

        assert manifest["status"] == "blocked"
        assert manifest["returncode"] is None
        assert manifest["failure_reason"].startswith("node2vec_windows_preflight_blocked:")
        assert "num_workers=4" in manifest["failure_reason"]
        assert not (output_dir / "sandbox").exists()
        assert (output_dir / "node2vec_windows_preflight.json").is_file()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_cli_passes_method_to_reproduction_config(monkeypatch):
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-cli"
    captured = {}

    def fake_run(config):
        captured["config"] = config
        return {"status": "success"}

    monkeypatch.setattr(module, "run_socgfm_reproduction", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["iohunter_socgfm.py", "--output-dir", str(output), "--method", "gnn"],
    )

    assert module.main() == 0
    assert captured["config"].method == "gnn"


def test_infoopsgfm_cli_builds_same_country_matrix_config(monkeypatch):
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-cli-matrix"
    captured = {}

    def fake_run_matrix(config):
        captured["config"] = config
        return {
            "success_count": 1,
            "expected_rows": 1,
        }

    monkeypatch.setattr(module, "run_socgfm_official_matrix", fake_run_matrix)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "iohunter_socgfm.py",
            "--output-dir",
            str(output),
            "--run-matrix",
            "--matrix-dataset",
            "russia",
            "--matrix-method",
            "cross_attention",
        ],
    )

    assert module.main() == 0
    assert captured["config"].datasets == ("russia",)
    assert captured["config"].methods == ("cross_attention",)


def test_infoopsgfm_cli_summarizes_explicit_official_manifests(monkeypatch):
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-cli-summary"
    manifest = output / "input" / "manifest.json"
    captured = {}

    def fake_summary(manifest_paths, output_dir):
        captured["manifest_paths"] = manifest_paths
        captured["output_dir"] = output_dir
        return {"status": "success"}

    monkeypatch.setattr(module, "summarize_infoopsgfm_manifests", fake_summary)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "iohunter_socgfm.py",
            "--output-dir",
            str(output),
            "--manifest",
            str(manifest),
        ],
    )

    assert module.main() == 0
    assert captured["manifest_paths"] == [manifest]
    assert captured["output_dir"] == output


def test_infoopsgfm_cli_writes_status_report(monkeypatch):
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-cli-status"
    matrix = output / "matrix"
    manifest = output / "run" / "manifest.json"
    captured = {}

    def fake_status_report(*, output_root, destination, matrix_roots, manifest_paths):
        captured["output_root"] = output_root
        captured["destination"] = destination
        captured["matrix_roots"] = matrix_roots
        captured["manifest_paths"] = manifest_paths
        return {"status": "success"}

    monkeypatch.setattr(module, "write_infoopsgfm_status_report", fake_status_report)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "iohunter_socgfm.py",
            "--output-dir",
            str(output),
            "--status-report",
            "--status-output-root",
            str(module.CANONICAL_REPRODUCTION_OUTPUT_ROOT),
            "--status-matrix-root",
            str(matrix),
            "--manifest",
            str(manifest),
        ],
    )

    assert module.main() == 0
    assert captured["destination"] == output
    assert captured["matrix_roots"] == [matrix]
    assert captured["manifest_paths"] == [manifest]


def test_infoopsgfm_cli_status_report_can_auto_discover_manifests(monkeypatch):
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-cli-status-auto"
    discovered_manifest = output / "auto" / "manifest.json"
    captured = {}

    monkeypatch.setattr(
        module,
        "discover_infoopsgfm_status_manifests",
        lambda output_root: [discovered_manifest],
    )

    def fake_status_report(*, output_root, destination, matrix_roots, manifest_paths):
        captured["manifest_paths"] = manifest_paths
        return {"status": "success"}

    monkeypatch.setattr(module, "write_infoopsgfm_status_report", fake_status_report)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "iohunter_socgfm.py",
            "--output-dir",
            str(output),
            "--status-report",
            "--status-discover-manifests",
            "--status-output-root",
            str(module.CANONICAL_REPRODUCTION_OUTPUT_ROOT),
        ],
    )

    assert module.main() == 0
    assert captured["manifest_paths"] == [discovered_manifest]


def test_infoopsgfm_mlflow_entrypoint_creates_a_sandbox_local_experiment(tmp_path):
    module = _load_module()
    entrypoint = tmp_path / "run_with_mlflow.py"

    module._write_mlflow_entrypoint(entrypoint, "run_GNN.py")

    content = entrypoint.read_text(encoding="utf-8")
    assert 'mlflow.set_experiment("CogGuard InfoOpsGFM Official Reproduction")' in content
    assert 'runpy.run_path(os.environ["COGGUARD_INFOOPSGFM_SCRIPT"]' in content


def test_infoopsgfm_mlflow_entrypoint_preserves_artifacts_after_windows_path_limit_failure(tmp_path):
    module = _load_module()
    entrypoint = tmp_path / "run_with_mlflow.py"

    module._write_mlflow_entrypoint(entrypoint, "run_GNNPlusLLM.py")

    content = entrypoint.read_text(encoding="utf-8")
    assert "def _log_artifact_with_windows_path_fallback" in content
    assert 'getattr(exc, "winerror", None) != 3' in content
    assert 'COGGUARD_INFOOPSGFM_ARTIFACT_STAGING' in content


def test_infoopsgfm_baseline_mlflow_entrypoint_defers_run_lifecycle_to_upstream(tmp_path):
    module = _load_module()
    entrypoint = tmp_path / "run_with_mlflow.py"

    module._write_mlflow_entrypoint(entrypoint, "run_NodePruning.py")

    content = entrypoint.read_text(encoding="utf-8")
    assert 'mlflow.set_experiment("CogGuard InfoOpsGFM Official Reproduction")' not in content
    assert "with mlflow.start_run(" not in content
    assert 'runpy.run_path(os.environ["COGGUARD_INFOOPSGFM_SCRIPT"]' in content


def test_infoopsgfm_sandbox_environment_keeps_temp_and_cache_artifacts_on_g_drive():
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-environment"
    sandbox = output / "sandbox"

    environment = module._sandbox_environment(
        output_dir=output,
        sandbox_root=sandbox,
        device="0",
        run_name="pytest",
    )

    for key in ("TEMP", "TMP", "TORCH_HOME", "XDG_CACHE_HOME", "MPLCONFIGDIR"):
        assert Path(environment[key]).drive.upper() == "G:"
        assert str(Path(environment[key])).startswith(str(sandbox))
    assert Path(environment["MLFLOW_TRACKING_URI"].removeprefix("file:///")).drive.upper() == "G:"
    assert Path(environment["COGGUARD_INFOOPSGFM_ARTIFACT_STAGING"]).drive.upper() == "G:"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "PYTHONPYCACHEPREFIX" not in environment


def test_infoopsgfm_environment_uses_the_same_mlflow_root_recorded_by_manifest():
    module = _load_module()
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-mlflow-root"
    environment = module._sandbox_environment(
        output_dir=output,
        sandbox_root=output / "sandbox",
        device="0",
        run_name="pytest",
    )

    assert module._mlflow_artifact_root(environment) == Path(
        environment["MLFLOW_TRACKING_URI"].removeprefix("file:///")
    )


def test_infoopsgfm_cross_country_copy_includes_each_official_dataset(tmp_path):
    module = _load_module()
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    for dataset in module.CROSS_COUNTRY_OFFICIAL_DATASETS:
        source = source_root / dataset
        source.mkdir(parents=True)
        (source / "0.7_datasets.pkl").write_bytes(dataset.encode("utf-8"))
        (source / "sbert_nodeattributes_mostPop5.pt").write_bytes(b"features")
        (source / "edge_index.th").write_bytes(b"edges")

    module._copy_cross_country_datasets(source_root, destination_root)

    copied = sorted(path.name for path in destination_root.iterdir())
    assert copied == sorted(module.CROSS_COUNTRY_OFFICIAL_DATASETS)
    assert (destination_root / "UAE_sample" / "edge_index.th").read_bytes() == b"edges"


def test_infoopsgfm_cross_country_preflight_reports_official_uae_alias_mismatch(tmp_path):
    module = _load_module()
    for dataset in ("china", "iran", "UAE", "cuba", "russia", "venezuela"):
        (tmp_path / dataset).mkdir()

    preflight = module.cross_country_preflight(tmp_path)

    assert preflight["ready"] is False
    assert preflight["official_required_datasets"][-1] == "venezuela"
    assert preflight["missing_datasets"] == ["UAE_sample"]
    assert "UAE_sample" in preflight["blockers"][0]


def test_infoopsgfm_cross_country_finetune_preflight_keeps_uae_and_reports_cuba_gpu_gate(tmp_path):
    module = _load_module()
    for dataset in ("china", "iran", "UAE", "cuba", "russia", "venezuela"):
        (tmp_path / dataset).mkdir()

    preflight = module.cross_country_preflight(
        tmp_path,
        method="cross_country_finetune",
        gpu_total_mib=8188,
    )

    assert preflight["missing_datasets"] == []
    assert preflight["ready"] is False
    assert "Cuba" in preflight["blockers"][0]
    assert "8188 MiB" in preflight["blockers"][0]


def test_infoopsgfm_same_country_cuba_preflight_blocks_under_recorded_gpu_gate(tmp_path):
    module = _load_module()
    (tmp_path / "cuba").mkdir()

    preflight = module.same_country_preflight(
        tmp_path,
        dataset="cuba",
        method="gnn",
        gpu_total_mib=8188,
    )

    assert preflight["missing_datasets"] == []
    assert preflight["ready"] is False
    assert "Cuba" in preflight["blockers"][0]
    assert "8188 MiB" in preflight["blockers"][0]


def test_infoopsgfm_same_country_cuba_preflight_does_not_generalize_gnn_oom_to_node_pruning(
    tmp_path,
):
    module = _load_module()
    (tmp_path / "cuba").mkdir()

    preflight = module.same_country_preflight(
        tmp_path,
        dataset="cuba",
        method="node_pruning",
        gpu_total_mib=8188,
    )

    assert preflight["ready"] is True
    assert preflight["blockers"] == []


def test_infoopsgfm_same_country_cuba_preflight_writes_blocked_manifest_without_running_upstream(
    monkeypatch,
):
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-cuba-preflight-{uuid.uuid4().hex}"
    processed_root = root / "processed"
    output_dir = root / "output"
    try:
        (processed_root / "cuba").mkdir(parents=True)
        monkeypatch.setattr(module, "_configured_gpu_total_mib", lambda device: 8188)
        config = module.SocGFMReproductionConfig(
            dataset="cuba",
            output_dir=output_dir,
            processed_data_root=processed_root,
            method="gnn",
        )

        manifest = module.run_socgfm_reproduction(config)

        assert manifest["status"] == "blocked"
        assert manifest["returncode"] is None
        assert manifest["preflight"]["dataset"] == "cuba"
        assert Path(manifest["artifacts"]["log"]).is_file()
        assert (output_dir / "same_country_preflight.json").is_file()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_cross_country_preflight_writes_blocked_manifest_without_running_upstream():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-preflight-{uuid.uuid4().hex}"
    processed_root = root / "processed"
    output_dir = root / "output"
    try:
        for dataset in ("china", "iran", "UAE", "cuba", "russia", "venezuela"):
            (processed_root / dataset).mkdir(parents=True)
        config = module.SocGFMReproductionConfig(
            dataset="russia",
            output_dir=output_dir,
            processed_data_root=processed_root,
            method="cross_country",
        )

        manifest = module.run_socgfm_reproduction(config)

        assert manifest["status"] == "blocked"
        assert manifest["returncode"] is None
        assert manifest["preflight"]["missing_datasets"] == ["UAE_sample"]
        assert Path(manifest["artifacts"]["log"]).is_file()
        assert (output_dir / "manifest.json").is_file()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_official_matrix_plan_covers_requested_methods_and_campaigns():
    module = _load_module()
    matrix_root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-infoopsgfm-matrix"
    config = module.SocGFMOfficialMatrixConfig(
        output_dir=matrix_root,
        datasets=("russia", "venezuela"),
        methods=("gnn", "cross_attention"),
        device="0",
    )

    plan = module.build_socgfm_official_matrix_plan(config)

    assert [(item.dataset, item.method) for item in plan] == [
        ("russia", "gnn"),
        ("russia", "cross_attention"),
        ("venezuela", "gnn"),
        ("venezuela", "cross_attention"),
    ]
    assert all(item.output_dir.parent == matrix_root for item in plan)
    assert all(item.output_dir.drive.upper() == "G:" for item in plan)


def test_infoopsgfm_official_matrix_runs_each_entry_and_writes_coverage_summary(monkeypatch):
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-matrix-{uuid.uuid4().hex}"
    calls = []

    def fake_run(config):
        calls.append((config.dataset, config.method, config.output_dir))
        config.output_dir.mkdir(parents=True)
        manifest = {
            "status": "success",
            "returncode": 0,
            "failure_reason": None,
            "runtime_seconds": 1.0,
            "config": {
                "dataset": config.dataset,
                "gnn": config.gnn,
                "method": config.method,
                "method_display_name": config.method_display_name,
                "official_script_name": config.official_script_name,
                "smoke": False,
            },
            "official_git": {"commit": "abc123", "executed_source_clean": True},
            "metrics": {
                name: {"mean": 0.7, "std": 0.1}
                for name in ("accuracy", "precision", "f1_macro", "f1_micro", "roc_auc")
            },
            "artifacts": {"log": str(config.output_dir / "official.log")},
        }
        (config.output_dir / "manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        return manifest

    try:
        monkeypatch.setattr(module, "run_socgfm_reproduction", fake_run)
        summary = module.run_socgfm_official_matrix(
            module.SocGFMOfficialMatrixConfig(
                output_dir=root,
                datasets=("russia", "venezuela"),
                methods=("gnn", "cross_attention"),
            )
        )

        assert [(dataset, method) for dataset, method, _ in calls] == [
            ("russia", "gnn"),
            ("russia", "cross_attention"),
            ("venezuela", "gnn"),
            ("venezuela", "cross_attention"),
        ]
        assert summary["completed_rows"] == 4
        assert summary["success_count"] == 4
        assert summary["expected_rows"] == 4
        assert (root / "matrix_manifest.json").is_file()
        assert (root / "socgfm_matrix_summary.json").is_file()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_official_matrix_retries_a_blocked_entry_in_a_new_attempt_directory_when_requested(
    monkeypatch,
):
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-matrix-retry-{uuid.uuid4().hex}"
    logical_entry = root / "cuba--gnn--sage"
    logical_entry.mkdir(parents=True)
    (logical_entry / "manifest.json").write_text(
        json.dumps(
            {
                "status": "blocked",
                "returncode": None,
                "failure_reason": "same_country_preflight_blocked",
                "runtime_seconds": 0.0,
                "config": {
                    "dataset": "cuba",
                    "gnn": "sage",
                    "method": "gnn",
                    "method_display_name": "GNN",
                    "official_script_name": "run_GNN.py",
                    "smoke": False,
                },
                "official_git": {"commit": "abc123", "executed_source_clean": True},
                "metrics": {
                    name: {"mean": None, "std": None}
                    for name in ("accuracy", "precision", "f1_macro", "f1_micro", "roc_auc")
                },
                "artifacts": {"log": str(logical_entry / "official.log")},
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_run(config):
        calls.append(config.output_dir)
        config.output_dir.mkdir(parents=True)
        manifest = {
            "status": "success",
            "returncode": 0,
            "failure_reason": None,
            "runtime_seconds": 1.0,
            "config": {
                "dataset": config.dataset,
                "gnn": config.gnn,
                "method": config.method,
                "method_display_name": config.method_display_name,
                "official_script_name": config.official_script_name,
                "smoke": False,
            },
            "official_git": {"commit": "abc123", "executed_source_clean": True},
            "metrics": {
                name: {"mean": 0.7, "std": 0.1}
                for name in ("accuracy", "precision", "f1_macro", "f1_micro", "roc_auc")
            },
            "artifacts": {"log": str(config.output_dir / "official.log")},
        }
        (config.output_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    try:
        monkeypatch.setattr(module, "run_socgfm_reproduction", fake_run)
        summary = module.run_socgfm_official_matrix(
            module.SocGFMOfficialMatrixConfig(
                output_dir=root,
                datasets=("cuba",),
                methods=("gnn",),
                retry_non_success=True,
            )
        )

        assert len(calls) == 1
        assert calls[0].parent.name == "attempts"
        assert calls[0] != logical_entry
        assert summary["success_count"] == 1
        matrix = json.loads((root / "matrix_manifest.json").read_text(encoding="utf-8"))
        assert matrix["entries"][0]["reused_existing_manifest"] is False
        assert matrix["entries"][0]["logical_output_dir"] == str(logical_entry)
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_official_matrix_reuses_a_still_blocked_entry_without_creating_an_attempt():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-matrix-blocked-{uuid.uuid4().hex}"
    logical_entry = root / "cuba--gnn--sage"
    logical_entry.mkdir(parents=True)
    (logical_entry / "manifest.json").write_text(
        json.dumps(
            {
                "status": "blocked",
                "returncode": None,
                "failure_reason": "same_country_preflight_blocked",
                "runtime_seconds": 0.0,
                "config": {
                    "dataset": "cuba",
                    "gnn": "sage",
                    "method": "gnn",
                    "method_display_name": "GNN",
                    "official_script_name": "run_GNN.py",
                    "smoke": False,
                },
                "official_git": {"commit": "abc123", "executed_source_clean": True},
                "metrics": {
                    name: {"mean": None, "std": None}
                    for name in ("accuracy", "precision", "f1_macro", "f1_micro", "roc_auc")
                },
                "artifacts": {"log": str(logical_entry / "official.log")},
            }
        ),
        encoding="utf-8",
    )
    try:
        summary = module.run_socgfm_official_matrix(
            module.SocGFMOfficialMatrixConfig(
                output_dir=root,
                datasets=("cuba",),
                methods=("gnn",),
            )
        )

        assert summary["success_count"] == 0
        matrix = json.loads((root / "matrix_manifest.json").read_text(encoding="utf-8"))
        assert matrix["entries"][0]["reused_existing_manifest"] is True
        assert not (logical_entry / "attempts").exists()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_matrix_launcher_allows_verified_desktop_gpu_headroom():
    launcher = PROJECT_ROOT / "backend" / "scripts" / "start_iohunter_infoopsgfm_official_matrix.ps1"
    content = launcher.read_text(encoding="utf-8")

    assert "[int]$GpuMemoryIdleMiB = 1536" in content
    assert "[int]$GpuUtilizationIdlePercent = 40" in content
    assert "[int]$FreeMemoryMinimumMiB = 4096" in content
    assert "[switch]$RetryNonSuccess" in content
    assert '"--retry-non-success"' in content


def test_infoopsgfm_baseline_launcher_waits_for_primary_matrix_and_runs_clean_source_baselines():
    launcher = (
        PROJECT_ROOT
        / "backend"
        / "scripts"
        / "start_iohunter_infoopsgfm_official_baselines.ps1"
    )
    content = launcher.read_text(encoding="utf-8")

    assert "[string]$PrimaryMatrixRoot" in content
    assert "matrix_manifest.json" in content
    assert '"--method", "node_pruning"' in content
    assert '"--method", "node2vec"' in content
    assert '"G:\\CISCN\\CogGuard\\.worktrees\\refactor-system\\system\\output"' in content
    assert "FreeMemoryMinimumMiB" in content
    assert "COGGUARD_INFOOPSGFM_ALLOW_WINDOWS_NODE2VEC" in content


def test_socgfm_dataset_copy_excludes_generated_best_model_artifacts():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-socgfm-copy-{uuid.uuid4().hex}"
    source = root / "source"
    destination = root / "destination"
    try:
        (source / "best_models_f1_macro").mkdir(parents=True)
        (source / "nodefeatures").mkdir()
        (source / "0.7_datasets.pkl").write_bytes(b"dataset")
        (source / "0.7_datasets.pkl_0.5U").write_bytes(b"undersampled")
        (source / "sbert_nodeattributes_mostPop5.pt").write_bytes(b"features")
        (source / "edge_index.th").write_bytes(b"edges")
        (source / "nodefeatures" / "all.pth").write_bytes(b"cached-features")
        (source / "best_models_f1_macro" / "model0.pth").write_bytes(b"generated")

        module._copy_dataset(source, destination)

        assert (destination / "0.7_datasets.pkl").exists()
        assert (destination / "sbert_nodeattributes_mostPop5.pt").exists()
        assert (destination / "edge_index.th").exists()
        assert (destination / "nodefeatures" / "all.pth").exists()
        assert not (destination / "0.7_datasets.pkl_0.5U").exists()
        assert not (destination / "best_models_f1_macro").exists()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_socgfm_metric_summary_normalizes_official_nan_values_to_null():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-socgfm-metrics-{uuid.uuid4().hex}"
    try:
        root.mkdir(parents=True)
        log_path = root / "official.log"
        log_path.write_text(
            "\n".join(
                [
                    "[TEST] accuracy: 0.7+-0.1",
                    "[TEST] precision: 0.8+-0.2",
                    "[TEST] f1_macro: 0.75+-0.05",
                    "[TEST] f1_micro: 0.7+-0.1",
                    "[TEST_coRT] roc_auc: nan+-nan",
                ]
            ),
            encoding="utf-8",
        )

        summary = module._metric_summary(log_path, root)

        assert summary["roc_auc"]["mean"] is None
        assert summary["f1_macro"]["mean"] == 0.75
        assert summary["f1_macro"]["std"] == 0.05
        assert summary["f1_macro"]["split_values"] is None
        assert "not global test artifacts" in summary["official_output_caveat"]
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_failure_reason_marks_metrics_then_cleanup_failure():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-socgfm-cleanup-failure-{uuid.uuid4().hex}"
    try:
        root.mkdir(parents=True)
        log_path = root / "official.log"
        log_path.write_text(
            "\n".join(
                [
                    "[TEST] accuracy: 0.8958+-0.0",
                    "[TEST] precision: 0.9545+-0.0",
                    "[TEST] f1_macro: 0.8846+-0.0",
                    "[TEST] f1_micro: 0.8958+-0.0",
                    "Traceback (most recent call last):",
                    '  File "run_NodePruning.py", line 120, in <module>',
                    "    shutil.rmtree(exp_dir, ignore_errors=True)",
                    "TypeError: lstat: path should be string, bytes or os.PathLike, not NoneType",
                ]
            ),
            encoding="utf-8",
        )

        assert (
            module._failure_reason(log_path, 1)
            == "official_post_metrics_cleanup_failed: shutil.rmtree received exp_dir=None"
        )
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_failure_reason_marks_windows_node2vec_worker_pickle_failure():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-socgfm-node2vec-worker-{uuid.uuid4().hex}"
    try:
        root.mkdir(parents=True)
        log_path = root / "official.log"
        log_path.write_text(
            "\n".join(
                [
                    '  File "run_Node2Vec.py", line 104, in main',
                    "    for pos_rw, neg_rw in loader:",
                    "TypeError: cannot pickle 'PyCapsule' object",
                ]
            ),
            encoding="utf-8",
        )

        assert (
            module._failure_reason(log_path, 1)
            == "official_windows_node2vec_worker_failed: PyG Node2Vec num_workers=4 cannot pickle PyCapsule"
        )
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_socgfm_matrix_summary_marks_official_folds_as_non_seed_evidence():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-socgfm-summary-{uuid.uuid4().hex}"
    try:
        run_dir = root / "russia"
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "status": "success",
                    "returncode": 0,
                    "failure_reason": None,
                    "runtime_seconds": 12.5,
                    "config": {
                        "dataset": "russia",
                        "gnn": "sage",
                        "method": "gnn",
                        "official_script_name": "run_GNN.py",
                        "method_display_name": "GNN",
                    },
                    "official_git": {
                        "commit": "abc123",
                        "executed_source_clean": True,
                    },
                    "metrics": {
                        name: {"mean": 0.7, "std": 0.1}
                        for name in ("accuracy", "precision", "f1_macro", "f1_micro", "roc_auc")
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        summary = module.summarize_socgfm_matrix(root, root)

        assert summary["success_count"] == 1
        assert summary["rows"][0]["method"] == "gnn"
        assert summary["rows"][0]["official_script_name"] == "run_GNN.py"
        assert "not independent model-seed" in summary["protocol"]["fold_semantics"]
        assert (root / "socgfm_matrix_summary.json").exists()
        assert (root / "socgfm_matrix_summary.md").exists()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_manifest_summary_rejects_duplicate_official_method_rows():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-duplicates-{uuid.uuid4().hex}"
    try:
        manifest_paths = []
        for index in range(2):
            run_dir = root / f"run-{index}"
            run_dir.mkdir(parents=True)
            manifest_path = run_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "returncode": 0,
                        "runtime_seconds": 1.0,
                        "config": {
                            "dataset": "russia",
                            "gnn": "sage",
                            "method": "gnn",
                            "method_display_name": "GNN",
                            "official_script_name": "run_GNN.py",
                        },
                        "official_git": {"commit": "abc123", "executed_source_clean": True},
                        "metrics": {
                            name: {"mean": 0.7, "std": 0.1}
                            for name in ("accuracy", "precision", "f1_macro", "f1_micro", "roc_auc")
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest_paths.append(manifest_path)

        with pytest.raises(ValueError, match="duplicate official method row"):
            module.summarize_infoopsgfm_manifests(manifest_paths, root / "summary")
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_status_report_marks_pending_matrix_and_baseline_smokes():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-status-{uuid.uuid4().hex}"
    try:
        matrix_root = root / "iohunter-infoopsgfm-official-matrix-pending"
        (matrix_root / "launcher").mkdir(parents=True)
        (matrix_root / "launcher" / "launcher.json").write_text(
            json.dumps(
                {
                    "resource_gate": {
                        "minimum_free_memory_mib": 4096,
                        "maximum_gpu_memory_used_mib": 1536,
                        "maximum_gpu_utilization_percent": 40,
                    }
                }
            ),
            encoding="utf-8-sig",
        )
        (matrix_root / "launcher" / "launcher.log").write_text(
            "2026-08-13T01:08:46 free_memory_mib=1236 gpu_memory_mib=1613 gpu_utilization_percent=29 ready=False\n",
            encoding="utf-8",
        )
        pruning = root / "node-pruning"
        pruning.mkdir(parents=True)
        (pruning / "manifest.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "returncode": 1,
                    "failure_reason": "official_post_metrics_cleanup_failed: shutil.rmtree received exp_dir=None",
                    "runtime_seconds": 53.6,
                    "config": {
                        "dataset": "russia",
                        "gnn": "sage",
                        "method": "node_pruning",
                        "method_display_name": "Node Pruning",
                        "official_script_name": "run_NodePruning.py",
                        "smoke": True,
                    },
                    "official_git": {"commit": "abc123", "executed_source_clean": True},
                    "metrics": {
                        name: {"mean": value, "std": 0.0}
                        for name, value in {
                            "accuracy": 0.8958,
                            "precision": 0.9545,
                            "f1_macro": 0.8846,
                            "f1_micro": 0.8958,
                            "roc_auc": None,
                        }.items()
                    },
                    "artifacts": {"log": str(pruning / "official.log")},
                }
            ),
            encoding="utf-8",
        )
        destination = root / "status"

        report = module.write_infoopsgfm_status_report(
            output_root=root,
            destination=destination,
            matrix_roots=[matrix_root],
            manifest_paths=[pruning / "manifest.json"],
        )

        assert report["row_count"] == 2
        pending = next(row for row in report["rows"] if row["status"] == "pending")
        assert pending["resource_gate"]["observed"]["free_memory_mib"] == 1236
        assert pending["resource_gate"]["observed"]["gpu_memory_mib"] == 1613
        assert pending["resource_gate"]["blockers"] == [
            "host_memory_below_minimum(1236<4096 MiB)",
            "gpu_memory_above_idle(1613>1536 MiB)",
        ]
        assert any(row["method"] == "node_pruning" and row["f1_macro"] == 0.8846 for row in report["rows"])
        assert (destination / "infoopsgfm_status_report.json").is_file()
        assert (destination / "infoopsgfm_status_report.md").is_file()
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_status_report_discovers_latest_unique_manifests():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-discover-{uuid.uuid4().hex}"
    try:
        old_run = root / "old"
        new_run = root / "new"
        old_run.mkdir(parents=True)
        new_run.mkdir(parents=True)

        def write_manifest(path, *, f1_macro):
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "cogguard.iohunter-socgfm-official-reproduction/v1",
                        "status": "success",
                        "returncode": 0,
                        "failure_reason": None,
                        "runtime_seconds": 1.0,
                        "config": {
                            "dataset": "russia",
                            "gnn": "sage",
                            "method": "gnn",
                            "method_display_name": "GNN",
                            "official_script_name": "run_GNN.py",
                            "smoke": False,
                        },
                        "official_git": {"commit": "abc123", "executed_source_clean": True},
                        "metrics": {
                            name: {"mean": value, "std": 0.0}
                            for name, value in {
                                "accuracy": f1_macro,
                                "precision": f1_macro,
                                "f1_macro": f1_macro,
                                "f1_micro": f1_macro,
                                "roc_auc": None,
                            }.items()
                        },
                        "artifacts": {"log": str(path.parent / "official.log")},
                    }
                ),
                encoding="utf-8",
            )

        write_manifest(old_run / "manifest.json", f1_macro=0.1)
        write_manifest(new_run / "manifest.json", f1_macro=0.9)

        discovered = module.discover_infoopsgfm_status_manifests(root)

        assert discovered == [new_run / "manifest.json"]
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_status_report_normalizes_legacy_cross_attention_manifests():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-legacy-discover-{uuid.uuid4().hex}"
    try:
        legacy_run = root / "legacy"
        current_run = root / "current"
        legacy_run.mkdir(parents=True)
        current_run.mkdir(parents=True)

        base_manifest = {
            "status": "success",
            "returncode": 0,
            "failure_reason": None,
            "runtime_seconds": 1.0,
            "official_git": {"commit": "abc123", "executed_source_clean": True},
            "metrics": {
                name: {"mean": 0.5, "std": 0.0}
                for name in module.METRIC_NAMES
            },
            "artifacts": {"log": str(root / "official.log")},
        }
        (legacy_run / "manifest.json").write_text(
            json.dumps(
                {
                    **base_manifest,
                    "schema_version": "cogguard.iohunter-socgfm-official-reproduction/v1",
                    "config": {
                        "dataset": "russia",
                        "gnn": "sage",
                        "smoke": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        (current_run / "manifest.json").write_text(
            json.dumps(
                {
                    **base_manifest,
                    "schema_version": module.OFFICIAL_REPRODUCTION_SCHEMA,
                    "config": {
                        "dataset": "russia",
                        "gnn": "sage",
                        "method": "cross_attention",
                        "official_script_name": module.OFFICIAL_SCRIPT_NAME,
                        "smoke": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        discovered = module.discover_infoopsgfm_status_manifests(root)

        assert discovered == [current_run / "manifest.json"]
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)


def test_infoopsgfm_status_report_discovery_skips_sandbox_runtime_cache():
    module = _load_module()
    root = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-infoopsgfm-skip-cache-{uuid.uuid4().hex}"
    try:
        valid_run = root / "valid-run"
        cache_run = root / "valid-run" / "sandbox" / "runtime" / "cache" / "nested"
        valid_run.mkdir(parents=True)
        cache_run.mkdir(parents=True)
        manifest = {
            "schema_version": module.OFFICIAL_REPRODUCTION_SCHEMA,
            "status": "success",
            "returncode": 0,
            "failure_reason": None,
            "runtime_seconds": 1.0,
            "config": {
                "dataset": "russia",
                "gnn": "sage",
                "method": "gnn",
                "method_display_name": "GNN",
                "official_script_name": "run_GNN.py",
                "smoke": False,
            },
            "official_git": {"commit": "abc123", "executed_source_clean": True},
            "metrics": {
                name: {"mean": 0.5, "std": 0.0}
                for name in module.METRIC_NAMES
            },
            "artifacts": {"log": str(valid_run / "official.log")},
        }
        (valid_run / "manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        (cache_run / "manifest.json").write_text(
            json.dumps({**manifest, "status": "failed"}),
            encoding="utf-8",
        )

        discovered = module.discover_infoopsgfm_status_manifests(root)

        assert discovered == [valid_run / "manifest.json"]
    finally:
        if root.exists():
            import shutil

            shutil.rmtree(root)
