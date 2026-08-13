from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from .runner import CANONICAL_REPRODUCTION_OUTPUT_ROOT, validate_reproduction_output_dir


DEFAULT_OFFICIAL_REPOSITORY = Path(r"G:\CISCN\dataset\iohunter\SocGFM")
DEFAULT_OFFICIAL_CLEAN_REPOSITORY = Path(r"G:\CISCN\dataset\iohunter\InfoOpsGFM-clean")
DEFAULT_PROCESSED_DATA_ROOT = Path(r"G:\CISCN\dataset\iohunter\data\processed")
SUPPORTED_DATASETS = ("UAE", "cuba", "russia", "venezuela", "iran", "china")
OFFICIAL_SCRIPT_NAME = "run_MultiModalGNN_CrossAttention.py"
OFFICIAL_GNN_SOURCE_FILES = (
    "models.py",
    "data_loader.py",
    "model_eval.py",
    "my_utils.py",
    "plot_utils.py",
)
OFFICIAL_BASELINE_SOURCE_FILES = (
    "data_loader.py",
    "model_eval.py",
    "my_utils.py",
)
OFFICIAL_BASELINE_SCRIPT_NAMES = (
    "run_Node2Vec.py",
    "run_NodePruning.py",
)
OFFICIAL_METHODS = {
    "gnn": {
        "display_name": "GNN",
        "script": "run_GNN.py",
        "uses_textual_options": False,
        "cross_country": False,
        "command_profile": "gnn",
        "source_files": OFFICIAL_GNN_SOURCE_FILES,
    },
    "gnn_plus_llm": {
        "display_name": "GNN+LLM",
        "script": "run_GNNPlusLLM.py",
        "uses_textual_options": True,
        "cross_country": False,
        "command_profile": "gnn",
        "source_files": OFFICIAL_GNN_SOURCE_FILES,
    },
    "multimodal_gnn": {
        "display_name": "MultiModalGNN",
        "script": "run_MultiModalGNN.py",
        "uses_textual_options": True,
        "cross_country": False,
        "command_profile": "gnn",
        "source_files": OFFICIAL_GNN_SOURCE_FILES,
    },
    "cross_attention": {
        "display_name": "MultiModalGNN CrossAttention",
        "script": OFFICIAL_SCRIPT_NAME,
        "uses_textual_options": True,
        "cross_country": False,
        "command_profile": "gnn",
        "source_files": OFFICIAL_GNN_SOURCE_FILES,
    },
    "cross_country": {
        "display_name": "MultiModalGNN CrossAttention CrossCountry",
        "script": "run_MultiModalGNN_CrossAttention_CrossCountry.py",
        "uses_textual_options": True,
        "cross_country": True,
        "command_profile": "gnn",
        "source_files": OFFICIAL_GNN_SOURCE_FILES,
    },
    "cross_country_finetune": {
        "display_name": "MultiModalGNN CrossAttention CrossCountryPlusFineTuning",
        "script": "run_MultiModalGNN_CrossAttention_CrossCountryPlusFineTuning.py",
        "uses_textual_options": True,
        "cross_country": True,
        "command_profile": "gnn",
        "source_files": OFFICIAL_GNN_SOURCE_FILES,
    },
    "node2vec": {
        "display_name": "Node2Vec + RandomForest",
        "script": "run_Node2Vec.py",
        "uses_textual_options": False,
        "cross_country": False,
        "command_profile": "node2vec",
        "source_files": OFFICIAL_BASELINE_SOURCE_FILES,
        "requires_clean_executed_source": True,
    },
    "node_pruning": {
        "display_name": "Node Pruning",
        "script": "run_NodePruning.py",
        "uses_textual_options": False,
        "cross_country": False,
        "command_profile": "node_pruning",
        "source_files": OFFICIAL_BASELINE_SOURCE_FILES,
        "requires_clean_executed_source": True,
    },
}
CROSS_COUNTRY_OFFICIAL_DATASETS_BY_METHOD = {
    "cross_country": ("china", "iran", "UAE_sample", "cuba", "russia", "venezuela"),
    "cross_country_finetune": ("china", "iran", "UAE", "cuba", "russia", "venezuela"),
}
# Preserve the original entry point's public constant for existing callers.
CROSS_COUNTRY_OFFICIAL_DATASETS = CROSS_COUNTRY_OFFICIAL_DATASETS_BY_METHOD["cross_country"]
CUBA_FULL_GRAPH_MINIMUM_GPU_MIB = 12 * 1024
DEFAULT_SAME_COUNTRY_METHODS = ("gnn", "gnn_plus_llm", "multimodal_gnn", "cross_attention")
METRIC_NAMES = ("accuracy", "precision", "f1_macro", "f1_micro", "roc_auc")
OFFICIAL_REPRODUCTION_SCHEMA = "cogguard.iohunter-infoopsgfm-official-reproduction/v2"
LEGACY_SOCGFM_REPRODUCTION_SCHEMA = "cogguard.iohunter-socgfm-official-reproduction/v1"
OFFICIAL_REPRODUCTION_SCHEMAS = frozenset(
    {
        OFFICIAL_REPRODUCTION_SCHEMA,
        LEGACY_SOCGFM_REPRODUCTION_SCHEMA,
    }
)
STATUS_MANIFEST_SCAN_SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        "_mlflow",
        "cache",
        "pycache",
        "runtime",
        "sandbox",
    }
)
_OFFICIAL_TEST_METRIC_PATTERN = re.compile(
    r"^\[TEST\]\s+(?P<name>accuracy|precision|f1_macro|f1_micro|roc_auc):\s+"
    r"(?P<mean>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|nan)"
    r"\+-"
    r"(?P<std>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|nan)\s*$",
    flags=re.MULTILINE,
)
_RESOURCE_GATE_LOG_PATTERN = re.compile(
    r"free_memory_mib=(?P<free_memory_mib>\d+)\s+"
    r"gpu_memory_mib=(?P<gpu_memory_mib>\d+)\s+"
    r"(?:gpu_utilization_percent=(?P<gpu_utilization_percent>\d+)\s+)?"
    r"ready=(?P<ready>True|False)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SocGFMReproductionConfig:
    dataset: str
    output_dir: Path
    official_repository: Path = DEFAULT_OFFICIAL_REPOSITORY
    processed_data_root: Path = DEFAULT_PROCESSED_DATA_ROOT
    seed: int = 12121995
    splits: int = 5
    epochs: int = 1000
    early_stopping_limit: int = 30
    learning_rate: float = 1e-2
    gnn: str = "sage"
    device: str = "0"
    latent_dim: int = 128
    most_popular: int = 5
    min_tweets: int = 10
    method: str = "cross_attention"
    smoke: bool = False

    def __post_init__(self) -> None:
        if self.dataset not in SUPPORTED_DATASETS:
            raise ValueError(f"unsupported SocGFM dataset: {self.dataset}")
        if self.gnn not in {"gcn", "sage"}:
            raise ValueError("gnn must be gcn or sage")
        if self.method not in OFFICIAL_METHODS:
            raise ValueError(f"unsupported official InfoOpsGFM method: {self.method}")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        for name in ("splits", "epochs", "early_stopping_limit", "latent_dim", "most_popular", "min_tweets"):
            value = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")

    @property
    def official_script_name(self) -> str:
        return str(OFFICIAL_METHODS[self.method]["script"])

    @property
    def method_display_name(self) -> str:
        return str(OFFICIAL_METHODS[self.method]["display_name"])

    @property
    def execution_repository(self) -> Path:
        """Select the clean upstream checkout for baseline scripts when needed."""
        method = OFFICIAL_METHODS[self.method]
        if bool(method.get("requires_clean_executed_source")) and self.official_repository == DEFAULT_OFFICIAL_REPOSITORY:
            return DEFAULT_OFFICIAL_CLEAN_REPOSITORY
        return self.official_repository


@dataclass(frozen=True, slots=True)
class SocGFMOfficialMatrixConfig:
    """Configuration for a serial, official same-country reproduction matrix."""

    output_dir: Path
    datasets: tuple[str, ...] = SUPPORTED_DATASETS
    methods: tuple[str, ...] = DEFAULT_SAME_COUNTRY_METHODS
    official_repository: Path = DEFAULT_OFFICIAL_REPOSITORY
    processed_data_root: Path = DEFAULT_PROCESSED_DATA_ROOT
    seed: int = 12121995
    splits: int = 5
    epochs: int = 1000
    early_stopping_limit: int = 30
    learning_rate: float = 1e-2
    gnn: str = "sage"
    device: str = "0"
    latent_dim: int = 128
    most_popular: int = 5
    min_tweets: int = 10
    retry_non_success: bool = False

    def __post_init__(self) -> None:
        validate_reproduction_output_dir(self.output_dir)
        if not self.datasets:
            raise ValueError("datasets must not be empty")
        if not self.methods:
            raise ValueError("methods must not be empty")
        if len(set(self.datasets)) != len(self.datasets):
            raise ValueError("datasets must not contain duplicates")
        if len(set(self.methods)) != len(self.methods):
            raise ValueError("methods must not contain duplicates")
        for dataset in self.datasets:
            if dataset not in SUPPORTED_DATASETS:
                raise ValueError(f"unsupported SocGFM dataset: {dataset}")
        for method in self.methods:
            if method not in DEFAULT_SAME_COUNTRY_METHODS:
                raise ValueError(
                    "official same-country matrix only supports: "
                    + ", ".join(DEFAULT_SAME_COUNTRY_METHODS)
                )
        SocGFMReproductionConfig(
            dataset=self.datasets[0],
            output_dir=self.output_dir / "validation",
            official_repository=self.official_repository,
            processed_data_root=self.processed_data_root,
            seed=self.seed,
            splits=self.splits,
            epochs=self.epochs,
            early_stopping_limit=self.early_stopping_limit,
            learning_rate=self.learning_rate,
            gnn=self.gnn,
            device=self.device,
            latent_dim=self.latent_dim,
            most_popular=self.most_popular,
            min_tweets=self.min_tweets,
            method=self.methods[0],
        )


def build_socgfm_official_matrix_plan(
    config: SocGFMOfficialMatrixConfig,
) -> tuple[SocGFMReproductionConfig, ...]:
    """Build deterministic per-entry configs without executing upstream code."""
    output_dir = validate_reproduction_output_dir(config.output_dir)
    return tuple(
        SocGFMReproductionConfig(
            dataset=dataset,
            output_dir=output_dir / f"{dataset}--{method}--{config.gnn}",
            official_repository=config.official_repository,
            processed_data_root=config.processed_data_root,
            seed=config.seed,
            splits=config.splits,
            epochs=config.epochs,
            early_stopping_limit=config.early_stopping_limit,
            learning_rate=config.learning_rate,
            gnn=config.gnn,
            device=config.device,
            latent_dim=config.latent_dim,
            most_popular=config.most_popular,
            min_tweets=config.min_tweets,
            method=method,
        )
        for dataset in config.datasets
        for method in config.methods
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _executed_source_files(config: SocGFMReproductionConfig) -> tuple[str, ...]:
    method_source_files = OFFICIAL_METHODS[config.method]["source_files"]
    return (config.official_script_name, *method_source_files)


def _git_metadata(repository: Path, config: SocGFMReproductionConfig) -> dict[str, Any]:
    def run_git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    executed_files = []
    for filename in _executed_source_files(config):
        relative_path = Path("src") / filename
        source_path = repository / relative_path
        if not source_path.is_file():
            raise FileNotFoundError(f"official InfoOpsGFM executed source is missing: {source_path}")
        diff = subprocess.run(
            ["git", "-C", str(repository), "diff", "--quiet", "--", str(relative_path)],
            check=False,
        )
        executed_files.append(
            {
                "path": relative_path.as_posix(),
                "sha256": _sha256_file(source_path),
                "modified": diff.returncode != 0,
            }
        )

    return {
        "repository": str(repository.resolve()),
        "commit": run_git("rev-parse", "HEAD"),
        "origin": run_git("remote", "get-url", "origin"),
        "dirty": bool(run_git("status", "--porcelain")),
        "executed_source_files": executed_files,
        "executed_source_clean": all(not item["modified"] for item in executed_files),
    }


def _copy_dataset(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"processed dataset directory does not exist: {source}")
    destination.mkdir(parents=True, exist_ok=False)
    required_files = (
        "0.7_datasets.pkl",
        "sbert_nodeattributes_mostPop5.pt",
        "edge_index.th",
    )
    for relative_path in required_files:
        source_path = source / relative_path
        if source_path.is_file():
            shutil.copy2(source_path, destination / relative_path)

    # The official runner creates caches when absent. Reuse only precomputed
    # structural features, never stale checkpoints or unused under-sampling data.
    source_features = source / "nodefeatures"
    if source_features.is_dir():
        shutil.copytree(source_features, destination / "nodefeatures")


def _cross_country_required_datasets(method: str) -> tuple[str, ...]:
    try:
        return CROSS_COUNTRY_OFFICIAL_DATASETS_BY_METHOD[method]
    except KeyError as exc:
        raise ValueError(f"method is not an official cross-country entry point: {method}") from exc


def _copy_cross_country_datasets(
    source_root: Path,
    destination_root: Path,
    *,
    method: str = "cross_country",
) -> None:
    destination_root.mkdir(parents=True, exist_ok=False)
    for dataset in _cross_country_required_datasets(method):
        _copy_dataset(source_root / dataset, destination_root / dataset)


def _copy_official_source(repository: Path, sandbox_src: Path) -> None:
    source_dir = repository / "src"
    if not source_dir.is_dir():
        raise FileNotFoundError(f"official InfoOpsGFM source directory does not exist: {source_dir}")
    sandbox_src.mkdir(parents=True, exist_ok=True)
    for source_file in source_dir.glob("*.py"):
        shutil.copy2(source_file, sandbox_src / source_file.name)


def _write_mlflow_entrypoint(path: Path, script_name: str) -> None:
    owns_mlflow_lifecycle = script_name in OFFICIAL_BASELINE_SCRIPT_NAMES
    run_invocation = (
        'runpy.run_path(os.environ["COGGUARD_INFOOPSGFM_SCRIPT"], run_name="__main__")'
        if owns_mlflow_lifecycle
        else (
            'mlflow.set_experiment("CogGuard InfoOpsGFM Official Reproduction")\n'
            'with mlflow.start_run(run_name=os.environ["COGGUARD_SOCGFM_RUN_NAME"]):\n'
            '    runpy.run_path(os.environ["COGGUARD_INFOOPSGFM_SCRIPT"], run_name="__main__")'
        )
    )
    path.write_text(
        f"""from __future__ import annotations

import os
import runpy
import shutil
from pathlib import Path

import mlflow


def _log_artifact_with_windows_path_fallback(local_path, artifact_path=None):
    try:
        return _ORIGINAL_LOG_ARTIFACT(local_path, artifact_path)
    except OSError as exc:
        if getattr(exc, "winerror", None) != 3:
            raise
        staging_dir = Path(os.environ["COGGUARD_INFOOPSGFM_ARTIFACT_STAGING"])
        staging_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, staging_dir / Path(local_path).name)


_ORIGINAL_LOG_ARTIFACT = mlflow.log_artifact
mlflow.log_artifact = _log_artifact_with_windows_path_fallback
{run_invocation}
""",
        encoding="utf-8",
    )


def _build_official_command(config: SocGFMReproductionConfig) -> list[str]:
    profile = str(OFFICIAL_METHODS[config.method]["command_profile"])
    command = [
        sys.executable,
        "run_with_mlflow.py",
        "--dataset",
        config.dataset,
        "--seed",
        str(config.seed),
        "--splits",
        str(1 if config.smoke else config.splits),
    ]
    if profile in {"gnn", "node2vec"}:
        command.extend(
            [
                "--epochs",
                str(1 if config.smoke else config.epochs),
                "--early",
                str(1 if config.smoke else config.early_stopping_limit),
                "--lr",
                str(config.learning_rate),
                "--latent",
                str(config.latent_dim),
            ]
        )
    if profile == "gnn":
        command.extend(["--gnn", config.gnn, "--device", config.device])
    elif profile == "node2vec":
        command.extend(["--device", config.device])
    elif profile != "node_pruning":
        raise ValueError(f"unsupported official command profile: {profile}")
    if bool(OFFICIAL_METHODS[config.method]["uses_textual_options"]):
        command.extend(
            [
                "--most_pop",
                str(config.most_popular),
                "--min_tweets",
                str(config.min_tweets),
            ]
        )
    return command


def _sandbox_environment(
    *,
    output_dir: Path,
    sandbox_root: Path,
    device: str,
    run_name: str,
    script_name: str = OFFICIAL_SCRIPT_NAME,
) -> dict[str, str]:
    runtime_root = sandbox_root / "runtime"
    temp_root = runtime_root / "tmp"
    cache_root = runtime_root / "cache"
    artifact_staging = runtime_root / "mlflow_artifact_staging"
    mlflow_run_key = hashlib.sha256(str(output_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    mlruns_root = CANONICAL_REPRODUCTION_OUTPUT_ROOT / "_mlflow" / mlflow_run_key
    paths = {
        "TEMP": temp_root,
        "TMP": temp_root,
        "TMPDIR": temp_root,
        "TORCH_HOME": cache_root / "torch",
        "TORCHINDUCTOR_CACHE_DIR": cache_root / "torchinductor",
        "TRITON_CACHE_DIR": cache_root / "triton",
        "XDG_CACHE_HOME": cache_root / "xdg",
        "MPLCONFIGDIR": cache_root / "matplotlib",
        "HF_HOME": cache_root / "huggingface",
        "TRANSFORMERS_CACHE": cache_root / "transformers",
        "COGGUARD_INFOOPSGFM_ARTIFACT_STAGING": artifact_staging,
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    mlruns_root.mkdir(parents=True, exist_ok=True)
    return {
        **{key: str(path) for key, path in paths.items()},
        "MLFLOW_TRACKING_URI": mlruns_root.as_uri(),
        "MLFLOW_ALLOW_FILE_STORE": "true",
        "COGGUARD_SOCGFM_RUN_NAME": run_name,
        "COGGUARD_INFOOPSGFM_SCRIPT": script_name,
        "CUDA_VISIBLE_DEVICES": device,
        "PYTHONDONTWRITEBYTECODE": "1",
        "COGGUARD_EXPERIMENT_OUTPUT_DIR": str(output_dir),
    }


def _mlflow_artifact_root(environment: dict[str, str]) -> Path:
    tracking_uri = environment["MLFLOW_TRACKING_URI"]
    if not tracking_uri.startswith("file:///"):
        raise ValueError(f"expected file MLflow tracking URI, got: {tracking_uri}")
    return Path(tracking_uri.removeprefix("file:///"))


def _configured_gpu_total_mib(device: str) -> int | None:
    """Return the selected CUDA device total memory when it can be inspected."""
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        device_index = int(device)
        total_bytes = torch.cuda.get_device_properties(device_index).total_memory
        return total_bytes // (1024 * 1024)
    except (ImportError, RuntimeError, ValueError):
        return None


def same_country_preflight(
    processed_data_root: Path,
    *,
    dataset: str,
    method: str,
    gpu_total_mib: int | None = None,
) -> dict[str, Any]:
    """Validate one official same-country entry before its full-graph execution."""
    if dataset not in SUPPORTED_DATASETS:
        raise ValueError(f"unsupported SocGFM dataset: {dataset}")
    if method not in OFFICIAL_METHODS:
        raise ValueError(f"unsupported official InfoOpsGFM method: {method}")
    root = processed_data_root.resolve()
    missing = [] if (root / dataset).is_dir() else [dataset]
    blockers = []
    if missing:
        blockers.append(
            "Official same-country script is missing processed dataset: "
            + dataset
        )
    if (
        dataset == "cuba"
        and str(OFFICIAL_METHODS[method]["command_profile"]) == "gnn"
        and gpu_total_mib is not None
        and gpu_total_mib < CUBA_FULL_GRAPH_MINIMUM_GPU_MIB
    ):
        blockers.append(
            "Official Cuba full-graph same-country execution is blocked: "
            f"the selected GPU has {gpu_total_mib} MiB total memory, below the "
            f"{CUBA_FULL_GRAPH_MINIMUM_GPU_MIB} MiB preflight gate established "
            "from the recorded official SAGE/GCN out-of-memory runs."
        )
    return {
        "ready": not blockers,
        "dataset": dataset,
        "method": method,
        "processed_data_root": str(root),
        "official_required_datasets": [dataset],
        "missing_datasets": missing,
        "gpu_total_mib": gpu_total_mib,
        "cuba_full_graph_minimum_gpu_mib": CUBA_FULL_GRAPH_MINIMUM_GPU_MIB,
        "blockers": blockers,
    }


def cross_country_preflight(
    processed_data_root: Path,
    *,
    method: str = "cross_country",
    gpu_total_mib: int | None = None,
) -> dict[str, Any]:
    root = processed_data_root.resolve()
    required_datasets = _cross_country_required_datasets(method)
    missing = [
        dataset
        for dataset in required_datasets
        if not (root / dataset).is_dir()
    ]
    blockers = []
    if method == "cross_country" and "UAE_sample" in missing and (root / "UAE").is_dir():
        blockers.append(
            "Official cross-country script requires processed/UAE_sample, "
            "but the local bundle provides processed/UAE. The runner will not "
            "create an alias because that would alter the official path contract."
        )
    elif missing:
        blockers.append(
            "Official cross-country script is missing processed datasets: "
            + ", ".join(missing)
        )
    if gpu_total_mib is not None and gpu_total_mib < CUBA_FULL_GRAPH_MINIMUM_GPU_MIB:
        blockers.append(
            "Official Cuba full-graph cross-country execution is blocked: "
            f"the selected GPU has {gpu_total_mib} MiB total memory, below the "
            f"{CUBA_FULL_GRAPH_MINIMUM_GPU_MIB} MiB preflight gate established "
            "from the recorded official SAGE/GCN out-of-memory runs."
        )
    return {
        "ready": not blockers,
        "method": method,
        "processed_data_root": str(root),
        "official_required_datasets": list(required_datasets),
        "missing_datasets": missing,
        "gpu_total_mib": gpu_total_mib,
        "cuba_full_graph_minimum_gpu_mib": CUBA_FULL_GRAPH_MINIMUM_GPU_MIB,
        "blockers": blockers,
    }


def _parse_official_global_test_metrics(log_path: Path) -> dict[str, Any]:
    """Read the only non-overwritten global test metrics emitted by InfoOpsGFM."""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    metrics: dict[str, Any] = {
        metric_name: {
            "mean": None,
            "std": None,
            "split_values": None,
            "source": str(log_path),
            "source_kind": "official_console_global_test_aggregate",
        }
        for metric_name in METRIC_NAMES
    }
    for match in _OFFICIAL_TEST_METRIC_PATTERN.finditer(text):
        metric_name = match.group("name")
        mean = float(match.group("mean"))
        std = float(match.group("std"))
        metrics[metric_name] = {
            "mean": mean if np.isfinite(mean) else None,
            "std": std if np.isfinite(std) else None,
            "split_values": None,
            "source": str(log_path),
            "source_kind": "official_console_global_test_aggregate",
        }
    return metrics


def _metric_summary(log_path: Path, interim_dir: Path) -> dict[str, Any]:
    summary = _parse_official_global_test_metrics(log_path)
    validation_files = sorted(interim_dir.glob("val_*.npy")) if interim_dir.exists() else []
    summary["validation_artifacts"] = [str(path) for path in validation_files]
    summary["official_output_caveat"] = (
        "The unmodified official script reuses root-level metric filenames while "
        "writing relation-subset results after the global test. Those .npy files "
        "are therefore not global test artifacts. This manifest uses only the "
        "printed [TEST] global aggregates from official.log."
    )
    return summary


def _find_interim_dir(sandbox_root: Path) -> Path | None:
    candidates = sorted((sandbox_root / "data" / "interim").glob("*"))
    return candidates[-1] if candidates else None


def _data_manifest(dataset_dir: Path) -> dict[str, Any]:
    files = []
    for path in sorted(dataset_dir.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append(
            {
                "relative_path": path.relative_to(dataset_dir).as_posix(),
                "size": int(stat.st_size),
                "sha256": _sha256_file(path),
            }
        )
    return {
        "root": str(dataset_dir.resolve()),
        "file_count": len(files),
        "files": files,
        "fingerprint": "sha256:"
        + hashlib.sha256(_canonical_json(files).encode("utf-8")).hexdigest(),
    }


def _failure_reason(log_path: Path, returncode: int) -> str | None:
    if returncode == 0:
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    oom_match = re.search(r"torch\.OutOfMemoryError:\s*(.+)", text)
    if oom_match:
        return "cuda_out_of_memory: " + oom_match.group(1).strip()
    has_test_metrics = all(
        re.search(rf"^\[TEST\]\s+{name}:\s+", text, flags=re.MULTILINE)
        for name in ("accuracy", "precision", "f1_macro", "f1_micro")
    )
    if (
        has_test_metrics
        and "shutil.rmtree(exp_dir, ignore_errors=True)" in text
        and "not NoneType" in text
    ):
        return "official_post_metrics_cleanup_failed: shutil.rmtree received exp_dir=None"
    if (
        "run_Node2Vec.py" in text
        and "for pos_rw, neg_rw in loader:" in text
        and "cannot pickle 'PyCapsule' object" in text
    ):
        return (
            "official_windows_node2vec_worker_failed: "
            "PyG Node2Vec num_workers=4 cannot pickle PyCapsule"
        )
    traceback_match = re.search(r"^Traceback \(most recent call last\):\s*$", text, flags=re.MULTILINE)
    if traceback_match:
        return "official_script_failed; see official.log"
    return f"official_script_exit_{returncode}; see official.log"


def run_socgfm_reproduction(config: SocGFMReproductionConfig) -> dict[str, Any]:
    config = replace(config, official_repository=config.execution_repository)
    output_dir = validate_reproduction_output_dir(config.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory must be new and empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    official_repository = config.official_repository.resolve()
    processed_dataset = (config.processed_data_root / config.dataset).resolve()
    command = _build_official_command(config)
    command_text = subprocess.list2cmdline(command)
    (output_dir / "command.txt").write_text(command_text + "\n", encoding="utf-8")
    git_metadata = _git_metadata(official_repository, config)
    config_manifest = {
        **{key: str(value) if isinstance(value, Path) else value for key, value in asdict(config).items()},
        "output_dir": str(output_dir),
        "official_script_name": config.official_script_name,
        "method_display_name": config.method_display_name,
    }
    requires_clean_source = bool(
        OFFICIAL_METHODS[config.method].get("requires_clean_executed_source")
    )
    if requires_clean_source and not bool(git_metadata["executed_source_clean"]):
        source_preflight = {
            "ready": False,
            "method": config.method,
            "official_script_name": config.official_script_name,
            "requires_clean_executed_source": True,
            "executed_source_files": git_metadata["executed_source_files"],
            "blockers": [
                "official baseline execution requires an unmodified upstream source checkout"
            ],
        }
        log_path = output_dir / "official.log"
        log_path.write_text(
            "Official InfoOpsGFM source preflight blocked before execution.\n"
            + "\n".join(source_preflight["blockers"])
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "official_git.json").write_text(
            json.dumps(git_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "source_preflight.json").write_text(
            json.dumps(source_preflight, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        metrics = _metric_summary(log_path, output_dir / "missing-interim")
        manifest = {
            "schema_version": "cogguard.iohunter-infoopsgfm-official-reproduction/v2",
            "status": "blocked",
            "claimable": False,
            "claimability_reason": (
                "Official InfoOpsGFM baseline execution was blocked because the "
                "recorded executed upstream source files are modified."
            ),
            "config": config_manifest,
            "command": command_text,
            "returncode": None,
            "failure_reason": "source_preflight_blocked: "
            + "; ".join(source_preflight["blockers"]),
            "runtime_seconds": 0.0,
            "official_git": git_metadata,
            "preflight": source_preflight,
            "dataset_manifest": None,
            "metrics": metrics,
            "artifacts": {
                "log": str(log_path),
                "sandbox": None,
                "mlruns": None,
                "mlflow_artifact_staging": None,
                "interim": None,
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return manifest

    allow_windows_node2vec = os.environ.get("COGGUARD_INFOOPSGFM_ALLOW_WINDOWS_NODE2VEC") == "1"
    if config.method == "node2vec" and os.name == "nt" and not allow_windows_node2vec:
        node2vec_preflight = {
            "ready": False,
            "method": config.method,
            "official_script_name": config.official_script_name,
            "platform": os.name,
            "override_env": "COGGUARD_INFOOPSGFM_ALLOW_WINDOWS_NODE2VEC=1",
            "blockers": [
                "official run_Node2Vec.py uses PyG Node2Vec.loader(num_workers=4), "
                "which fails on this Windows environment with cannot pickle 'PyCapsule' object"
            ],
        }
        log_path = output_dir / "official.log"
        log_path.write_text(
            "Official InfoOpsGFM Node2Vec Windows preflight blocked before execution.\n"
            + "\n".join(node2vec_preflight["blockers"])
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "official_git.json").write_text(
            json.dumps(git_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "node2vec_windows_preflight.json").write_text(
            json.dumps(node2vec_preflight, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        metrics = _metric_summary(log_path, output_dir / "missing-interim")
        manifest = {
            "schema_version": "cogguard.iohunter-infoopsgfm-official-reproduction/v2",
            "status": "blocked",
            "claimable": False,
            "claimability_reason": (
                "Official InfoOpsGFM Node2Vec execution was blocked on Windows because "
                "the upstream worker configuration is known to fail before test metrics."
            ),
            "config": config_manifest,
            "command": command_text,
            "returncode": None,
            "failure_reason": "node2vec_windows_preflight_blocked: "
            + "; ".join(node2vec_preflight["blockers"]),
            "runtime_seconds": 0.0,
            "official_git": git_metadata,
            "preflight": node2vec_preflight,
            "dataset_manifest": None,
            "metrics": metrics,
            "artifacts": {
                "log": str(log_path),
                "sandbox": None,
                "mlruns": None,
                "mlflow_artifact_staging": None,
                "interim": None,
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return manifest

    if bool(OFFICIAL_METHODS[config.method]["cross_country"]):
        preflight_kind = "cross_country"
        preflight = cross_country_preflight(
            config.processed_data_root,
            method=config.method,
            gpu_total_mib=_configured_gpu_total_mib(config.device),
        )
    else:
        preflight_kind = "same_country"
        preflight = same_country_preflight(
            config.processed_data_root,
            dataset=config.dataset,
            method=config.method,
            gpu_total_mib=_configured_gpu_total_mib(config.device),
        )
    if not preflight["ready"]:
        log_path = output_dir / "official.log"
        log_path.write_text(
            f"Official InfoOpsGFM {preflight_kind.replace('_', '-')} preflight blocked before execution.\n"
            + "\n".join(preflight["blockers"])
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "official_git.json").write_text(
            json.dumps(git_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / f"{preflight_kind}_preflight.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        metrics = _metric_summary(log_path, output_dir / "missing-interim")
        manifest = {
            "schema_version": "cogguard.iohunter-infoopsgfm-official-reproduction/v2",
            "status": "blocked",
            "claimable": False,
            "claimability_reason": (
                "Official InfoOpsGFM execution was blocked by the recorded local "
                "input or hardware preflight."
            ),
            "config": config_manifest,
            "command": command_text,
            "returncode": None,
            "failure_reason": f"{preflight_kind}_preflight_blocked: " + "; ".join(preflight["blockers"]),
            "runtime_seconds": 0.0,
            "official_git": git_metadata,
            "preflight": preflight,
            "dataset_manifest": None,
            "metrics": metrics,
            "artifacts": {
                "log": str(log_path),
                "sandbox": None,
                "mlruns": None,
                "mlflow_artifact_staging": None,
                "interim": None,
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return manifest

    sandbox_root = output_dir / "sandbox"
    sandbox_src = sandbox_root / "src"
    sandbox_dataset = sandbox_root / "data" / "processed" / config.dataset
    sandbox_root.mkdir()
    (sandbox_root / "data" / "interim").mkdir(parents=True)

    _copy_official_source(official_repository, sandbox_src)
    if bool(OFFICIAL_METHODS[config.method]["cross_country"]):
        _copy_cross_country_datasets(
            config.processed_data_root,
            sandbox_root / "data" / "processed",
            method=config.method,
        )
    else:
        _copy_dataset(processed_dataset, sandbox_dataset)
    _write_mlflow_entrypoint(sandbox_src / "run_with_mlflow.py", config.official_script_name)

    (output_dir / "official_git.json").write_text(
        json.dumps(git_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    dataset_manifest = _data_manifest(sandbox_dataset)
    (output_dir / "dataset_manifest.json").write_text(
        json.dumps(dataset_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    environment = {
        "python": sys.version,
        "executable": sys.executable,
        "cwd": str(sandbox_src.resolve()),
        "cuda_visible_devices": config.device,
    }
    (output_dir / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    log_path = output_dir / "official.log"
    env = os.environ.copy()
    sandbox_environment = _sandbox_environment(
        output_dir=output_dir,
        sandbox_root=sandbox_root,
        device=config.device,
        run_name=(
            f"infoopsgfm-{config.method}-{config.dataset}-"
            f"{'smoke' if config.smoke else 'official'}"
        ),
        script_name=config.official_script_name,
    )
    env.update(sandbox_environment)
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8", errors="replace") as log_stream:
        process = subprocess.run(
            command,
            cwd=sandbox_src,
            env=env,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    runtime_seconds = time.perf_counter() - started

    interim_dir = _find_interim_dir(sandbox_root)
    metrics = _metric_summary(log_path, interim_dir or sandbox_root / "missing-interim")
    failure_reason = _failure_reason(log_path, process.returncode)
    manifest = {
        "schema_version": "cogguard.iohunter-infoopsgfm-official-reproduction/v2",
        "status": "success" if process.returncode == 0 else "failed",
        "claimable": False,
        "claimability_reason": (
            "Official InfoOpsGFM script executed in an isolated G-drive sandbox; "
            "paper-level reproduction remains gated on the complete dataset matrix and protocol audit."
        ),
        "config": config_manifest,
        "command": command_text,
        "returncode": process.returncode,
        "failure_reason": failure_reason,
        "runtime_seconds": runtime_seconds,
        "official_git": git_metadata,
        "sandbox_environment": sandbox_environment,
        "dataset_manifest": dataset_manifest,
        "metrics": metrics,
        "artifacts": {
            "log": str(log_path),
            "sandbox": str(sandbox_root),
            "mlruns": str(_mlflow_artifact_root(sandbox_environment)),
            "mlflow_artifact_staging": sandbox_environment["COGGUARD_INFOOPSGFM_ARTIFACT_STAGING"],
            "interim": str(interim_dir) if interim_dir else None,
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _manifest_row(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = manifest["config"]
    metrics = manifest["metrics"]
    failure_reason = manifest.get("failure_reason")
    if failure_reason is None and manifest["status"] != "success":
        log_path = Path(manifest["artifacts"]["log"])
        if log_path.is_file():
            failure_reason = _failure_reason(log_path, int(manifest["returncode"]))
    return {
        "dataset": config["dataset"],
        "gnn": config["gnn"],
        "method": _manifest_method(config),
        "method_display_name": _manifest_method_display_name(config),
        "official_script_name": _manifest_official_script_name(config),
        "smoke": bool(config.get("smoke", False)),
        "status": manifest["status"],
        "returncode": manifest["returncode"],
        "failure_reason": failure_reason,
        "runtime_seconds": manifest["runtime_seconds"],
        "accuracy": metrics["accuracy"]["mean"],
        "accuracy_std": metrics["accuracy"]["std"],
        "precision": metrics["precision"]["mean"],
        "precision_std": metrics["precision"]["std"],
        "f1_macro": metrics["f1_macro"]["mean"],
        "f1_macro_std": metrics["f1_macro"]["std"],
        "f1_micro": metrics["f1_micro"]["mean"],
        "f1_micro_std": metrics["f1_micro"]["std"],
        "roc_auc": metrics["roc_auc"]["mean"],
        "official_commit": manifest["official_git"]["commit"],
        "executed_source_clean": manifest["official_git"].get("executed_source_clean"),
        "manifest": str(manifest_path),
    }


def _manifest_method(config: dict[str, Any]) -> str:
    return str(config.get("method") or "cross_attention")


def _manifest_method_display_name(config: dict[str, Any]) -> str:
    method = _manifest_method(config)
    return str(
        config.get("method_display_name")
        or OFFICIAL_METHODS.get(method, {}).get("display_name")
        or "MultiModalGNN CrossAttention"
    )


def _manifest_official_script_name(config: dict[str, Any]) -> str:
    method = _manifest_method(config)
    return str(
        config.get("official_script_name")
        or OFFICIAL_METHODS.get(method, {}).get("script")
        or OFFICIAL_SCRIPT_NAME
    )


def _sort_infoopsgfm_rows(rows: list[dict[str, Any]]) -> None:
    rows.sort(
        key=lambda row: (
            SUPPORTED_DATASETS.index(row["dataset"]),
            row["method"],
            row["gnn"],
        )
    )


def _write_infoopsgfm_summary(
    *,
    rows: list[dict[str, Any]],
    destination: Path,
    schema_version: str,
    summary_stem: str,
    matrix_root: Path | None,
) -> dict[str, Any]:
    _sort_infoopsgfm_rows(rows)
    success_count = sum(row["status"] == "success" for row in rows)
    summary = {
        "schema_version": schema_version,
        "matrix_root": str(matrix_root) if matrix_root is not None else None,
        "row_count": len(rows),
        "success_count": success_count,
        "failed_count": len(rows) - success_count,
        "protocol": {
            "method": "official InfoOpsGFM entry points",
            "task": "IOHunter external account membership classification",
            "source_commit": rows[0]["official_commit"] if rows else None,
            "fold_semantics": (
                "The official script iterates dataset-provided splits. They are not "
                "independent model-seed repetitions and must not be reported as multi-seed evidence."
            ),
            "claim_boundary": (
                "IOHunter account-membership labels are an external-account recovery proxy, "
                "not Coordination Discovery community Gold or harmful-CIB Coordination Detect Gold."
            ),
        },
        "rows": rows,
    }
    summary_path = destination / f"{summary_stem}.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Official InfoOpsGFM IOHunter Reproduction Summary",
        "",
        f"- Rows: `{len(rows)}`; success: `{success_count}`; failed: `{len(rows) - success_count}`",
        "- Task: IOHunter external account membership classification only.",
        "- The reported mean/std come from five dataset-provided official splits, not independent random-seed trials.",
        "- No harmful-CIB Coordination Detect or temporal generalization claim follows from this run.",
        "",
        "| Campaign | Method | Backbone | Status | Macro-F1 | Accuracy | Precision | Runtime (s) | Note |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    if matrix_root is not None:
        lines.insert(2, f"- Matrix root: `{matrix_root}`")
    for row in rows:
        metric = lambda name: "-" if row[name] is None else f"{row[name]:.4f}"
        if row["status"] == "success":
            note = (
                "executed source clean"
                if row["executed_source_clean"]
                else "source status not recorded in legacy manifest"
            )
        else:
            note = row["failure_reason"] or "failed; see official.log"
        lines.append(
            f"| {row['dataset']} | {row['method_display_name']} | {row['gnn']} | {row['status']} | "
            f"{metric('f1_macro')} | {metric('accuracy')} | {metric('precision')} | "
            f"{row['runtime_seconds']:.2f} | {note} |"
        )
    report_path = destination / f"{summary_stem}.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary["artifacts"] = {
        "summary_json": str(summary_path),
        "summary_markdown": str(report_path),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def summarize_infoopsgfm_manifests(
    manifest_paths: list[Path],
    output_dir: Path,
) -> dict[str, Any]:
    """Summarize one official full run per campaign/method/backbone combination."""
    destination = validate_reproduction_output_dir(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    seen_keys: set[tuple[str, str, str]] = set()
    for manifest_path in manifest_paths:
        resolved = manifest_path.resolve(strict=True)
        row = _manifest_row(resolved)
        if row["smoke"]:
            raise ValueError(f"smoke manifest is not eligible for an official summary: {resolved}")
        key = (row["dataset"], row["method"], row["gnn"])
        if key in seen_keys:
            raise ValueError(
                "duplicate official method row for "
                f"dataset={row['dataset']}, method={row['method']}, gnn={row['gnn']}"
            )
        seen_keys.add(key)
        rows.append(row)
    return _write_infoopsgfm_summary(
        rows=rows,
        destination=destination,
        schema_version="cogguard.iohunter-infoopsgfm-method-summary/v1",
        summary_stem="infoopsgfm_method_summary",
        matrix_root=None,
    )


def summarize_socgfm_matrix(matrix_root: Path, output_dir: Path) -> dict[str, Any]:
    """Aggregate isolated official runs without treating official folds as random seeds."""
    root = matrix_root.resolve(strict=True)
    destination = validate_reproduction_output_dir(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rows = [_manifest_row(path) for path in sorted(root.glob("*/manifest.json"))]
    return _write_infoopsgfm_summary(
        rows=rows,
        destination=destination,
        schema_version="cogguard.iohunter-socgfm-matrix-summary/v1",
        summary_stem="socgfm_matrix_summary",
        matrix_root=root,
    )


def _pending_matrix_row(matrix_root: Path) -> dict[str, Any]:
    log_path = matrix_root / "launcher" / "launcher.log"
    last_log_line = None
    if log_path.is_file():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        last_log_line = lines[-1] if lines else None
    resource_gate = _pending_resource_gate(matrix_root, last_log_line)
    blocker_text = "; ".join(resource_gate.get("blockers") or [])
    if blocker_text:
        failure_reason = f"resource_gate_waiting: {blocker_text}; {last_log_line}"
    else:
        failure_reason = "resource_gate_waiting; " + last_log_line if last_log_line else "resource_gate_waiting"
    return {
        "dataset": None,
        "gnn": None,
        "method": "official_same_country_matrix",
        "method_display_name": "Official same-country matrix",
        "official_script_name": None,
        "smoke": False,
        "status": "pending",
        "returncode": None,
        "failure_reason": failure_reason,
        "resource_gate": resource_gate,
        "runtime_seconds": None,
        "accuracy": None,
        "accuracy_std": None,
        "precision": None,
        "precision_std": None,
        "f1_macro": None,
        "f1_macro_std": None,
        "f1_micro": None,
        "f1_micro_std": None,
        "roc_auc": None,
        "official_commit": None,
        "executed_source_clean": None,
        "manifest": str(matrix_root / "matrix_manifest.json"),
    }


def _pending_resource_gate(matrix_root: Path, last_log_line: str | None) -> dict[str, Any]:
    launcher_path = matrix_root / "launcher" / "launcher.json"
    configured_gate: dict[str, Any] = {}
    if launcher_path.is_file():
        try:
            launcher = json.loads(launcher_path.read_text(encoding="utf-8-sig"))
            if isinstance(launcher.get("resource_gate"), dict):
                configured_gate = launcher["resource_gate"]
        except (OSError, json.JSONDecodeError):
            configured_gate = {}
    observed = _parse_resource_gate_log_line(last_log_line)
    blockers = _resource_gate_blockers(observed, configured_gate)
    return {
        "configured": configured_gate,
        "observed": observed,
        "blockers": blockers,
    }


def _parse_resource_gate_log_line(line: str | None) -> dict[str, Any]:
    if not line:
        return {}
    match = _RESOURCE_GATE_LOG_PATTERN.search(line)
    if not match:
        return {"raw": line}
    parsed: dict[str, Any] = {
        "free_memory_mib": int(match.group("free_memory_mib")),
        "gpu_memory_mib": int(match.group("gpu_memory_mib")),
        "ready": match.group("ready").lower() == "true",
    }
    if match.group("gpu_utilization_percent") is not None:
        parsed["gpu_utilization_percent"] = int(match.group("gpu_utilization_percent"))
    return parsed


def _resource_gate_blockers(observed: dict[str, Any], configured: dict[str, Any]) -> list[str]:
    blockers = []
    minimum_free_memory = configured.get("minimum_free_memory_mib")
    if (
        isinstance(minimum_free_memory, int)
        and isinstance(observed.get("free_memory_mib"), int)
        and observed["free_memory_mib"] < minimum_free_memory
    ):
        blockers.append(
            f"host_memory_below_minimum({observed['free_memory_mib']}<{minimum_free_memory} MiB)"
        )
    maximum_gpu_memory = configured.get("maximum_gpu_memory_used_mib")
    if (
        isinstance(maximum_gpu_memory, int)
        and isinstance(observed.get("gpu_memory_mib"), int)
        and observed["gpu_memory_mib"] > maximum_gpu_memory
    ):
        blockers.append(
            f"gpu_memory_above_idle({observed['gpu_memory_mib']}>{maximum_gpu_memory} MiB)"
        )
    maximum_gpu_utilization = configured.get("maximum_gpu_utilization_percent")
    if (
        isinstance(maximum_gpu_utilization, int)
        and isinstance(observed.get("gpu_utilization_percent"), int)
        and observed["gpu_utilization_percent"] > maximum_gpu_utilization
    ):
        blockers.append(
            "gpu_utilization_above_idle("
            f"{observed['gpu_utilization_percent']}>{maximum_gpu_utilization}%)"
        )
    return blockers


def discover_infoopsgfm_status_manifests(output_root: Path) -> list[Path]:
    """Find the latest official reproduction manifest for each comparable config."""
    root = output_root.resolve()
    latest_by_key: dict[tuple[Any, ...], Path] = {}
    for manifest_path in _iter_infoopsgfm_status_manifest_paths(root):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("schema_version") not in OFFICIAL_REPRODUCTION_SCHEMAS:
            continue
        config = manifest.get("config")
        if not isinstance(config, dict):
            continue
        key = (
            config.get("dataset"),
            _manifest_method(config),
            config.get("gnn"),
            bool(config.get("smoke", False)),
            _manifest_official_script_name(config),
        )
        previous = latest_by_key.get(key)
        if previous is None or manifest_path.stat().st_mtime > previous.stat().st_mtime:
            latest_by_key[key] = manifest_path
    return sorted(latest_by_key.values(), key=lambda path: str(path))


def _iter_infoopsgfm_status_manifest_paths(root: Path) -> list[Path]:
    """Scan reproduction run manifests without traversing volatile runtime caches."""
    manifest_paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=lambda _error: None):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in STATUS_MANIFEST_SCAN_SKIP_DIRS
        ]
        if "manifest.json" in filenames:
            manifest_paths.append(Path(dirpath) / "manifest.json")
    return sorted(manifest_paths, key=lambda path: str(path))


def write_infoopsgfm_status_report(
    *,
    output_root: Path,
    destination: Path,
    matrix_roots: list[Path],
    manifest_paths: list[Path],
) -> dict[str, Any]:
    """Write a point-in-time audit report for queued and completed official runs."""
    root = output_root.resolve()
    destination = validate_reproduction_output_dir(destination)
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for matrix_root in matrix_roots:
        resolved = matrix_root.resolve()
        matrix_manifest = resolved / "matrix_manifest.json"
        if matrix_manifest.is_file():
            for manifest_path in sorted(resolved.glob("*/manifest.json")):
                rows.append(_manifest_row(manifest_path))
        else:
            rows.append(_pending_matrix_row(resolved))
    for manifest_path in manifest_paths:
        rows.append(_manifest_row(manifest_path.resolve(strict=True)))
    _sort_infoopsgfm_rows(
        [row for row in rows if row["dataset"] in SUPPORTED_DATASETS and row["gnn"] in {"gcn", "sage"}]
    )
    report = {
        "schema_version": "cogguard.iohunter-infoopsgfm-status/v1",
        "output_root": str(root),
        "row_count": len(rows),
        "status_counts": {
            status: sum(row["status"] == status for row in rows)
            for status in sorted({row["status"] for row in rows})
        },
        "rows": rows,
    }
    json_path = destination / "infoopsgfm_status_report.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# InfoOpsGFM Official Reproduction Status",
        "",
        f"- Output root: `{root}`",
        f"- Rows: `{len(rows)}`",
        "",
        "| Entry | Status | Macro-F1 | Accuracy | Runtime (s) | Note |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        entry = row["method_display_name"]
        if row.get("dataset"):
            entry = f"{row['dataset']} / {entry}"
        metric = lambda name: "-" if row.get(name) is None else f"{row[name]:.4f}"
        runtime = "-" if row.get("runtime_seconds") is None else f"{row['runtime_seconds']:.2f}"
        note = row.get("failure_reason") or ("manifest: " + row["manifest"])
        lines.append(
            f"| {entry} | {row['status']} | {metric('f1_macro')} | "
            f"{metric('accuracy')} | {runtime} | {note} |"
        )
    markdown_path = destination / "infoopsgfm_status_report.md"
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["artifacts"] = {
        "summary_json": str(json_path),
        "summary_markdown": str(markdown_path),
    }
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def _matrix_entry_descriptor(
    config: SocGFMReproductionConfig,
    *,
    logical_output_dir: Path,
    reused_existing_manifest: bool,
) -> dict[str, Any]:
    return {
        "dataset": config.dataset,
        "method": config.method,
        "method_display_name": config.method_display_name,
        "gnn": config.gnn,
        "official_script_name": config.official_script_name,
        "logical_output_dir": str(logical_output_dir),
        "output_dir": str(config.output_dir),
        "manifest": str(config.output_dir / "manifest.json"),
        "reused_existing_manifest": reused_existing_manifest,
    }


def _assert_existing_matrix_manifest_matches(
    manifest_path: Path,
    config: SocGFMReproductionConfig,
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = manifest.get("config", {})
    expected = {
        "dataset": config.dataset,
        "method": config.method,
        "gnn": config.gnn,
        "official_script_name": config.official_script_name,
    }
    actual = {key: existing.get(key) for key in expected}
    if actual != expected:
        raise ValueError(
            "existing matrix manifest does not match the planned official entry: "
            f"{manifest_path}"
        )


def _manifest_status(manifest_path: Path) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    status = manifest.get("status")
    if not isinstance(status, str):
        raise ValueError(f"existing matrix manifest has no status: {manifest_path}")
    return status


def _next_matrix_attempt_config(
    logical_config: SocGFMReproductionConfig,
) -> SocGFMReproductionConfig:
    attempts_dir = logical_config.output_dir / "attempts"
    attempt_index = 1
    while (attempts_dir / f"attempt-{attempt_index:03d}").exists():
        attempt_index += 1
    return replace(
        logical_config,
        output_dir=attempts_dir / f"attempt-{attempt_index:03d}",
    )


def run_socgfm_official_matrix(config: SocGFMOfficialMatrixConfig) -> dict[str, Any]:
    """Execute or resume a serial official same-country reproduction matrix."""
    output_dir = validate_reproduction_output_dir(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = build_socgfm_official_matrix_plan(config)
    rows = []
    entries = []
    for logical_entry in plan:
        logical_manifest_path = logical_entry.output_dir / "manifest.json"
        entry = logical_entry
        reused = False
        if logical_manifest_path.is_file():
            _assert_existing_matrix_manifest_matches(logical_manifest_path, logical_entry)
            if _manifest_status(logical_manifest_path) == "success" or not config.retry_non_success:
                reused = True
            else:
                entry = _next_matrix_attempt_config(logical_entry)
        manifest_path = entry.output_dir / "manifest.json"
        if reused:
            manifest_path = logical_manifest_path
        else:
            run_socgfm_reproduction(entry)
        if not manifest_path.is_file():
            raise RuntimeError(
                "official reproduction runner returned without a manifest: "
                f"{entry.output_dir}"
            )
        rows.append(_manifest_row(manifest_path))
        entries.append(
            _matrix_entry_descriptor(
                entry,
                logical_output_dir=logical_entry.output_dir,
                reused_existing_manifest=reused,
            )
        )

    summary = _write_infoopsgfm_summary(
        rows=rows,
        destination=output_dir,
        schema_version="cogguard.iohunter-infoopsgfm-official-matrix/v1",
        summary_stem="socgfm_matrix_summary",
        matrix_root=output_dir,
    )
    summary["expected_rows"] = len(plan)
    summary["completed_rows"] = len(rows)
    matrix_manifest = {
        "schema_version": "cogguard.iohunter-infoopsgfm-official-matrix/v1",
        "matrix_root": str(output_dir),
        "protocol": summary["protocol"],
        "expected_rows": len(plan),
        "completed_rows": len(rows),
        "success_count": summary["success_count"],
        "non_success_count": len(rows) - summary["success_count"],
        "entries": entries,
        "summary_artifacts": summary["artifacts"],
    }
    (output_dir / "matrix_manifest.json").write_text(
        json.dumps(matrix_manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary_path = Path(summary["artifacts"]["summary_json"])
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run official InfoOpsGFM in a G-drive sandbox.")
    parser.add_argument("--dataset", choices=SUPPORTED_DATASETS, default="russia")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--official-repository", type=Path, default=DEFAULT_OFFICIAL_REPOSITORY)
    parser.add_argument("--processed-data-root", type=Path, default=DEFAULT_PROCESSED_DATA_ROOT)
    parser.add_argument("--seed", type=int, default=12121995)
    parser.add_argument("--splits", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=1000)
    parser.add_argument("--early", type=int, default=30)
    parser.add_argument("--lr", type=float, default=1e-2)
    parser.add_argument("--gnn", choices=("gcn", "sage"), default="sage")
    parser.add_argument("--device", default="0")
    parser.add_argument("--latent", type=int, default=128)
    parser.add_argument("--most-pop", type=int, default=5)
    parser.add_argument("--min-tweets", type=int, default=10)
    parser.add_argument("--method", choices=tuple(OFFICIAL_METHODS), default="cross_attention")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument(
        "--run-matrix",
        action="store_true",
        help="Run or resume a serial official same-country method matrix.",
    )
    parser.add_argument(
        "--retry-non-success",
        action="store_true",
        help="Create new attempt directories for existing blocked or failed matrix entries.",
    )
    parser.add_argument("--matrix-dataset", action="append", choices=SUPPORTED_DATASETS)
    parser.add_argument("--matrix-method", action="append", choices=DEFAULT_SAME_COUNTRY_METHODS)
    parser.add_argument("--summarize-matrix", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        action="append",
        help="Official non-smoke manifest to include in an explicit method summary.",
    )
    parser.add_argument(
        "--status-report",
        action="store_true",
        help="Write a point-in-time official reproduction status report.",
    )
    parser.add_argument(
        "--status-output-root",
        type=Path,
        default=CANONICAL_REPRODUCTION_OUTPUT_ROOT,
        help="Canonical output root used in the status report.",
    )
    parser.add_argument(
        "--status-matrix-root",
        type=Path,
        action="append",
        default=[],
        help="Matrix root to include as completed or pending in the status report.",
    )
    parser.add_argument(
        "--status-discover-manifests",
        action="store_true",
        help="Auto-discover latest official reproduction manifests under --status-output-root.",
    )
    args = parser.parse_args()
    if args.status_report:
        manifest_paths = list(args.manifest or [])
        if args.status_discover_manifests:
            discovered = discover_infoopsgfm_status_manifests(args.status_output_root)
            seen = {path.resolve() for path in manifest_paths if path.exists()}
            for path in discovered:
                resolved = path.resolve()
                if resolved not in seen:
                    manifest_paths.append(path)
                    seen.add(resolved)
        report = write_infoopsgfm_status_report(
            output_root=args.status_output_root,
            destination=args.output_dir,
            matrix_roots=args.status_matrix_root,
            manifest_paths=manifest_paths,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.manifest:
        summary = summarize_infoopsgfm_manifests(args.manifest, args.output_dir)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.summarize_matrix is not None:
        summary = summarize_socgfm_matrix(args.summarize_matrix, args.output_dir)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.run_matrix:
        summary = run_socgfm_official_matrix(
            SocGFMOfficialMatrixConfig(
                output_dir=args.output_dir,
                datasets=tuple(args.matrix_dataset or SUPPORTED_DATASETS),
                methods=tuple(args.matrix_method or DEFAULT_SAME_COUNTRY_METHODS),
                official_repository=args.official_repository,
                processed_data_root=args.processed_data_root,
                seed=args.seed,
                splits=args.splits,
                epochs=args.epochs,
                early_stopping_limit=args.early,
                learning_rate=args.lr,
                gnn=args.gnn,
                device=args.device,
                latent_dim=args.latent,
                most_popular=args.most_pop,
                min_tweets=args.min_tweets,
                retry_non_success=args.retry_non_success,
            )
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["success_count"] == summary["expected_rows"] else 1
    manifest = run_socgfm_reproduction(
        SocGFMReproductionConfig(
            dataset=args.dataset,
            output_dir=args.output_dir,
            official_repository=args.official_repository,
            processed_data_root=args.processed_data_root,
            seed=args.seed,
            splits=args.splits,
            epochs=args.epochs,
            early_stopping_limit=args.early,
            learning_rate=args.lr,
            gnn=args.gnn,
            device=args.device,
            latent_dim=args.latent,
            most_popular=args.most_pop,
            min_tweets=args.min_tweets,
            method=args.method,
            smoke=args.smoke,
        )
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_OFFICIAL_REPOSITORY",
    "DEFAULT_PROCESSED_DATA_ROOT",
    "DEFAULT_SAME_COUNTRY_METHODS",
    "METRIC_NAMES",
    "OFFICIAL_METHODS",
    "OFFICIAL_REPRODUCTION_SCHEMA",
    "OFFICIAL_REPRODUCTION_SCHEMAS",
    "OFFICIAL_SCRIPT_NAME",
    "OFFICIAL_SHARED_SOURCE_FILES",
    "SUPPORTED_DATASETS",
    "SocGFMOfficialMatrixConfig",
    "SocGFMReproductionConfig",
    "build_socgfm_official_matrix_plan",
    "cross_country_preflight",
    "run_socgfm_official_matrix",
    "run_socgfm_reproduction",
    "same_country_preflight",
    "summarize_infoopsgfm_manifests",
    "summarize_socgfm_matrix",
]
