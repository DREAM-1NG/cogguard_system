#!/usr/bin/env python3
"""
Benchmark orchestrator for propagation prediction models.

Runs FOREST, MINDS, RF, LR, temporal, heuristic, ranker, and HyperIDP proxy adapters on specified datasets,
collects results into a unified JSON file, and prints a comparison table.

Usage:
    python -m benchmark.run_benchmark --datasets douban twitter christianity
    python -m benchmark.run_benchmark --models minds rf --datasets douban
    python -m benchmark.run_benchmark --forest_dir /path/to/FOREST --minds_dir /path/to/MINDS
"""
import argparse
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from .macro_micro import build_macro_micro_framework_summary, macro_micro_result_rows
from .schema import validate_benchmark_results

SCRIPT_DIR = Path(__file__).resolve().parent
ADAPTERS_DIR = SCRIPT_DIR / "adapters"
DEFAULT_OUTPUT = SCRIPT_DIR / "results.json"
DEFAULT_FOREST_DATA = Path(r"G:\CISCN\dataset\forest-data")
DEFAULT_KT2_REPOS = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos")
DEFAULT_MINDS_REPO = DEFAULT_KT2_REPOS / "MINDS"
DEFAULT_CASFT_REPO = DEFAULT_KT2_REPOS / "CasFT"
DEFAULT_DYGLIB_REPO = DEFAULT_KT2_REPOS / "DyGLib"
DEFAULT_TGN_REPO = DEFAULT_KT2_REPOS / "tgn"

MODELS = [
    "minds",
    "forest",
    "rf",
    "temporal",
    "lr",
    "heuristic",
    "ranker",
    "hyperidp_proxy",
    "hyperidp_adv_proxy",
    "casft",
    "dyglib",
    "tgn",
    "kt2_joint",
]
TASKS = {
    "scale": ["rf", "temporal", "minds", "hyperidp_proxy", "hyperidp_adv_proxy", "casft"],
    "next_hop": ["heuristic", "ranker", "lr", "forest", "minds", "hyperidp_proxy", "hyperidp_adv_proxy", "dyglib", "tgn"],
    "multi_scale": ["kt2_joint", "minds", "forest", "hyperidp_proxy", "hyperidp_adv_proxy"],
}
DATASETS = ["douban", "twitter", "memetracker", "christianity"]
K_LIST = [10, 50, 100]


def run_adapter(cmd: List[str], cwd: str, timeout: int = 1800) -> Optional[Dict]:
    """Run an adapter subprocess and parse JSON from its last stdout line."""
    print(f"  CMD: {' '.join(cmd)}")
    print(f"  CWD: {cwd}")
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return None
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return None

    parsed = _parse_last_json(proc.stdout)
    if proc.returncode != 0:
        print(f"  FAILED (rc={proc.returncode})")
        if proc.stderr:
            for line in proc.stderr.strip().split("\n")[-5:]:
                print(f"    stderr: {line}")
        if parsed:
            parsed.setdefault("status", "failed")
            parsed.setdefault("returncode", proc.returncode)
            return parsed
        return None

    if parsed:
        return parsed

    print("  WARNING: no JSON found in output")
    if proc.stdout:
        for line in proc.stdout.strip().split("\n")[-3:]:
            print(f"    stdout: {line}")
    return None


def _parse_last_json(stdout: str) -> Optional[Dict]:
    for line in reversed((stdout or "").strip().split("\n")):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def run_minds(dataset: str, minds_dir: str, python: str, epochs: int, device: str) -> Optional[Dict]:
    """Run MINDS adapter."""
    adapter = str(ADAPTERS_DIR / "minds_runner.py")
    cmd = [
        python, adapter,
        "--dataset_name", dataset,
        "--epochs", str(epochs),
        "--device", device,
    ]
    cwd = _minds_work_dir(minds_dir)
    if cwd is None:
        print(f"  SKIP: MINDS source directory not found under {minds_dir}")
        return None
    return run_adapter(cmd, cwd=cwd)


def _minds_work_dir(minds_dir: str) -> Optional[str]:
    """Resolve MINDS source root, including the local clone state where only MINDS.zip exists."""

    root = Path(minds_dir)
    candidates = [root / "MINDS", root]
    for candidate in candidates:
        if (candidate / "run.py").is_file() and (candidate / "Module.py").is_file():
            return str(candidate)

    zip_path = root / "MINDS.zip"
    extract_root = root / ".kt2_extracted"
    extracted = extract_root / "MINDS"
    if zip_path.is_file():
        if not (extracted / "run.py").is_file():
            extract_root.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_root)
        if (extracted / "run.py").is_file() and (extracted / "Module.py").is_file():
            return str(extracted)
    return None


def run_forest(
    dataset: str,
    forest_dir: str,
    python: str,
    epochs: int,
    device: str,
    batch_size: int,
    max_train_batches: int,
    max_eval_batches: int,
    rl_epochs: int,
    rl_start_size: int,
    rl_max_batches: int,
    rl_rollout_len: int,
) -> Optional[Dict]:
    """Run FOREST adapter."""
    adapter = str(ADAPTERS_DIR / "forest_runner.py")
    forest_code_dir = _forest_code_dir(forest_dir)
    if forest_code_dir is None:
        print(f"  SKIP: FOREST code dir not found from {forest_dir}")
        return None
    data_root = _forest_data_root(forest_dir, dataset)
    cmd = [
        python, adapter,
        "--data_name", dataset,
        "--epochs", str(epochs),
        "--batch_size", str(batch_size),
        "--max_train_batches", str(max_train_batches),
        "--max_eval_batches", str(max_eval_batches),
        "--device", device,
        "--rl_epochs", str(rl_epochs),
        "--rl_start_size", str(rl_start_size),
        "--rl_max_batches", str(rl_max_batches),
        "--rl_rollout_len", str(rl_rollout_len),
    ]
    if data_root:
        cmd.extend(["--data_root", data_root])
    return run_adapter(cmd, cwd=forest_code_dir)


def _forest_code_dir(forest_dir: str) -> Optional[str]:
    root = Path(forest_dir)
    candidates = [
        root,
        Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST"),
        SCRIPT_DIR.parent / "kt2_repos" / "FOREST",
    ]
    for candidate in candidates:
        if (candidate / "model.py").is_file() and (candidate / "DataLoader.py").is_file():
            return str(candidate)
    return None


def _forest_data_root(forest_dir: str, dataset: str) -> Optional[str]:
    root = Path(forest_dir)
    candidates = [
        root,
        root / "data",
        Path(r"G:\CISCN\dataset\forest-data"),
    ]
    for candidate in candidates:
        if (candidate / dataset / "cascade.txt").is_file():
            return str(candidate)
    return None


def run_rf(dataset: str, forest_dir: str, python: str, obs_ratio: float) -> Optional[Dict]:
    """Run RF baseline adapter."""
    adapter = str(ADAPTERS_DIR / "rf_baseline.py")
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        print(f"  SKIP: data dir not found at {data_dir}")
        return None
    cmd = [
        python, adapter,
        "--data_dir", data_dir,
        "--obs_ratio", str(obs_ratio),
    ]
    return run_adapter(cmd, cwd=forest_dir)


def run_temporal(dataset: str, forest_dir: str, python: str, obs_window_seconds: int) -> Optional[Dict]:
    """Run fixed-time temporal size extrapolation baseline."""
    adapter = str(ADAPTERS_DIR / "temporal_size_baseline.py")
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        print(f"  SKIP: data dir not found at {data_dir}")
        return None
    cmd = [
        python, adapter,
        "--data_dir", data_dir,
        "--obs_window_seconds", str(obs_window_seconds),
    ]
    return run_adapter(cmd, cwd=forest_dir)


def run_lr(
    dataset: str,
    forest_dir: str,
    python: str,
    obs_ratio: float,
    max_future: int,
    max_candidates: int,
    inject_true_parent: bool,
) -> Optional[Dict]:
    """Run LogisticRegression offline edge-classifier adapter."""
    adapter = str(ADAPTERS_DIR / "lr_edge_baseline.py")
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        print(f"  SKIP: data dir not found at {data_dir}")
        return None
    cmd = [
        python, adapter,
        "--data_dir", data_dir,
        "--obs_ratio", str(obs_ratio),
        "--max_future_per_cascade", str(max_future),
        "--max_candidates", str(max_candidates),
    ]
    if inject_true_parent:
        cmd.append("--inject_true_parent")
    return run_adapter(cmd, cwd=forest_dir)


def run_heuristic(
    dataset: str,
    forest_dir: str,
    python: str,
    obs_ratio: float,
    max_future: int,
    global_top_n: int,
    max_candidates: int,
) -> Optional[Dict]:
    """Run prospective non-learning next-user baseline."""
    adapter = str(ADAPTERS_DIR / "prospective_heuristic.py")
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        print(f"  SKIP: data dir not found at {data_dir}")
        return None
    cmd = [
        python, adapter,
        "--data_dir", data_dir,
        "--obs_ratio", str(obs_ratio),
        "--max_future_per_cascade", str(max_future),
        "--global_top_n", str(global_top_n),
        "--max_candidates", str(max_candidates),
    ]
    return run_adapter(cmd, cwd=forest_dir)


def run_ranker(
    dataset: str,
    forest_dir: str,
    python: str,
    obs_ratio: float,
    max_future: int,
    global_top_n: int,
    max_candidates: int,
    negatives_per_cascade: int,
) -> Optional[Dict]:
    """Run prospective learned next-user ranker."""
    adapter = str(ADAPTERS_DIR / "prospective_ranker.py")
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        print(f"  SKIP: data dir not found at {data_dir}")
        return None
    cmd = [
        python, adapter,
        "--data_dir", data_dir,
        "--obs_ratio", str(obs_ratio),
        "--max_future_per_cascade", str(max_future),
        "--global_top_n", str(global_top_n),
        "--max_candidates", str(max_candidates),
        "--negatives_per_cascade", str(negatives_per_cascade),
    ]
    return run_adapter(cmd, cwd=forest_dir)


def run_hyperidp_proxy(
    dataset: str,
    forest_dir: str,
    python: str,
    obs_ratio: float,
    max_future: int,
    global_top_n: int,
    max_candidates: int,
    negatives_per_cascade: int,
    bucket_seconds: int,
) -> Optional[Dict]:
    """Run protocol-level temporal hypergraph proxy for HyperIDP-style evaluation."""
    adapter = str(ADAPTERS_DIR / "hyperidp_protocol_proxy.py")
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        print(f"  SKIP: data dir not found at {data_dir}")
        return None
    cmd = [
        python, adapter,
        "--data_dir", data_dir,
        "--obs_ratio", str(obs_ratio),
        "--max_future_per_cascade", str(max_future),
        "--global_top_n", str(global_top_n),
        "--max_candidates", str(max_candidates),
        "--negatives_per_cascade", str(negatives_per_cascade),
        "--bucket_seconds", str(bucket_seconds),
    ]
    return run_adapter(cmd, cwd=forest_dir)


def run_hyperidp_adv_proxy(
    dataset: str,
    forest_dir: str,
    python: str,
    obs_ratio: float,
    max_future: int,
    global_top_n: int,
    max_candidates: int,
    negatives_per_cascade: int,
    bucket_seconds: int,
    epochs: int,
    device: str,
) -> Optional[Dict]:
    """Run adversarial multi-task proxy for HyperIDP-style evaluation."""
    adapter = str(ADAPTERS_DIR / "hyperidp_adversarial_proxy.py")
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        print(f"  SKIP: data dir not found at {data_dir}")
        return None
    cmd = [
        python, adapter,
        "--data_dir", data_dir,
        "--obs_ratio", str(obs_ratio),
        "--max_future_per_cascade", str(max_future),
        "--global_top_n", str(global_top_n),
        "--max_candidates", str(max_candidates),
        "--negatives_per_cascade", str(negatives_per_cascade),
        "--bucket_seconds", str(bucket_seconds),
        "--epochs", str(epochs),
        "--device", device,
    ]
    return run_adapter(cmd, cwd=forest_dir)


def run_kt2_joint_model(
    dataset: str,
    forest_dir: str,
    python: str,
    obs_ratio: float,
    max_future: int,
    global_top_n: int,
    max_candidates: int,
    negatives_per_cascade: int,
    bucket_seconds: int,
    epochs: int,
    batch_size: int,
    hidden_dim: int,
    lambda_consistency: float,
    lambda_trend: float,
    lambda_orthogonality: float,
    lambda_adversarial: float,
    lambda_diffusion: float,
    lambda_forest_pg: float,
    diffusion_noise_std: float,
    forest_pg_rollout_samples: int,
    max_consistency_candidates_per_event: int,
    max_sequence_len: int,
    max_train_cascades: int,
    max_test_cascades: int,
    use_original_casft_diffusion: bool,
    use_original_casft_spatiotemporal: bool,
    lambda_original_casft_spatiotemporal: float,
    casft_spatiotemporal_interval_num: int,
    casft_spatiotemporal_tpp_hdim: int,
    casft_repo: Optional[str],
    use_original_minds_components: bool,
    use_original_minds_full_module: bool,
    lambda_original_minds_module: float,
    minds_repo: Optional[str],
    use_original_forest_components: bool,
    lambda_original_forest_ce: float,
    lambda_original_forest_rl: float,
    original_forest_rollout_samples: int,
    original_forest_start_size: int,
    casft_diffusion_timesteps: int,
    casft_sampling_timesteps: int,
    device: str,
) -> Optional[Dict]:
    """Run KT2's own joint macro/micro model."""
    adapter = str(ADAPTERS_DIR / "kt2_joint_model.py")
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        print(f"  SKIP: data dir not found at {data_dir}")
        return None
    cmd = [
        python, adapter,
        "--data_dir", data_dir,
        "--obs_ratio", str(obs_ratio),
        "--max_future_per_cascade", str(max_future),
        "--global_top_n", str(global_top_n),
        "--max_candidates", str(max_candidates),
        "--negatives_per_cascade", str(negatives_per_cascade),
        "--bucket_seconds", str(bucket_seconds),
        "--epochs", str(epochs),
        "--batch_size", str(batch_size),
        "--hidden_dim", str(hidden_dim),
        "--lambda_consistency", str(lambda_consistency),
        "--lambda_trend", str(lambda_trend),
        "--lambda_orthogonality", str(lambda_orthogonality),
        "--lambda_adversarial", str(lambda_adversarial),
        "--lambda_diffusion", str(lambda_diffusion),
        "--lambda_forest_pg", str(lambda_forest_pg),
        "--diffusion_noise_std", str(diffusion_noise_std),
        "--forest_pg_rollout_samples", str(forest_pg_rollout_samples),
        "--max_consistency_candidates_per_event", str(max_consistency_candidates_per_event),
        "--max_sequence_len", str(max_sequence_len),
        "--max_train_cascades", str(max_train_cascades),
        "--max_test_cascades", str(max_test_cascades),
        "--device", device,
    ]
    if use_original_casft_diffusion:
        cmd.append("--use_original_casft_diffusion")
        if casft_repo:
            cmd.extend(["--casft_repo", casft_repo])
        cmd.extend(
            [
                "--casft_diffusion_timesteps", str(casft_diffusion_timesteps),
                "--casft_sampling_timesteps", str(casft_sampling_timesteps),
            ]
        )
    if use_original_casft_spatiotemporal:
        cmd.append("--use_original_casft_spatiotemporal")
        if casft_repo:
            cmd.extend(["--casft_repo", casft_repo])
        cmd.extend(
            [
                "--lambda_original_casft_spatiotemporal", str(lambda_original_casft_spatiotemporal),
                "--casft_spatiotemporal_interval_num", str(casft_spatiotemporal_interval_num),
                "--casft_spatiotemporal_tpp_hdim", str(casft_spatiotemporal_tpp_hdim),
            ]
        )
    if use_original_minds_components:
        cmd.append("--use_original_minds_components")
        if minds_repo:
            cmd.extend(["--minds_repo", minds_repo])
    else:
        cmd.append("--disable_original_minds_components")
    if use_original_minds_full_module:
        cmd.append("--use_original_minds_full_module")
        cmd.extend(["--lambda_original_minds_module", str(lambda_original_minds_module)])
        if minds_repo:
            cmd.extend(["--minds_repo", minds_repo])
    else:
        cmd.append("--disable_original_minds_full_module")
    if use_original_forest_components:
        cmd.append("--use_original_forest_components")
        cmd.extend(["--forest_repo", _forest_code_dir(forest_dir) or forest_dir])
        cmd.extend(
            [
                "--lambda_original_forest_ce", str(lambda_original_forest_ce),
                "--lambda_original_forest_rl", str(lambda_original_forest_rl),
                "--original_forest_rollout_samples", str(original_forest_rollout_samples),
                "--original_forest_start_size", str(original_forest_start_size),
            ]
        )
    return run_adapter(cmd, cwd=forest_dir)


def run_casft_frontier(
    dataset: str,
    forest_dir: Optional[str],
    casft_dir: Optional[str],
    python: str,
    export_root: str,
    max_events: int,
    obs_ratio: float,
    timeout: int,
    run_external: bool,
    casft_dataset: str,
    observation_time: int,
    prediction_time: int,
    max_epoch: int,
) -> Optional[Dict]:
    """Run the KT2 CasFT adapter or record why frontier reproduction is not ready."""
    if not casft_dir:
        return external_reproduction_status("CasFT", dataset, None, "scale")
    if not forest_dir:
        status = external_reproduction_status("CasFT", dataset, casft_dir, "scale")
        status["status"] = "missing_protocol_data"
        status["note"] = "CasFT repo is available, but --forest_dir was not provided for protocol export/comparison."
        return status
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        status = external_reproduction_status("CasFT", dataset, casft_dir, "scale")
        status["status"] = "missing_protocol_data"
        status["note"] = f"FOREST-format data dir not found at {data_dir}; cannot export CasFT protocol data."
        return status
    adapter = str(ADAPTERS_DIR / "casft_runner.py")
    export_dir = os.path.join(export_root, dataset, "casft")
    cmd = [
        python, adapter,
        "--casft_dir", casft_dir,
        "--data_dir", data_dir,
        "--export_dir", export_dir,
        "--max_events", str(max_events),
        "--obs_ratio", str(obs_ratio),
        "--timeout", str(timeout),
        "--python", python,
        "--casft_dataset", casft_dataset,
        "--observation_time", str(observation_time),
        "--prediction_time", str(prediction_time),
        "--max_epoch", str(max_epoch),
        "--seed", "0",
    ]
    if run_external:
        cmd.append("--run_external")
    return run_adapter(cmd, cwd=str(SCRIPT_DIR.parent), timeout=timeout + 30)


def run_temporal_graph_frontier(
    framework: str,
    dataset: str,
    forest_dir: Optional[str],
    repo_dir: Optional[str],
    python: str,
    export_root: str,
    max_cascades: int,
    obs_ratio: float,
    max_future: int,
    global_top_n: int,
    max_candidates: int,
    epochs: int,
    batch_size: int,
    num_runs: int,
    gpu: int,
    timeout: int,
    run_external: bool,
) -> Optional[Dict]:
    """Run DyGLib/TGN temporal graph adapter under the shared no-leakage protocol."""
    model_name = "DyGFormer/DyGLib" if framework == "dyglib" else "TGN"
    if not repo_dir:
        return external_reproduction_status(model_name, dataset, None, "next_hop")
    if not forest_dir:
        status = external_reproduction_status(model_name, dataset, repo_dir, "next_hop")
        status["status"] = "missing_protocol_data"
        status["note"] = f"{model_name} repo is available, but --forest_dir was not provided for temporal edge export."
        return status
    data_dir = _forest_data_dir(forest_dir, dataset)
    if not os.path.isdir(data_dir):
        status = external_reproduction_status(model_name, dataset, repo_dir, "next_hop")
        status["status"] = "missing_protocol_data"
        status["note"] = f"FOREST-format data dir not found at {data_dir}; cannot export temporal edge stream."
        return status
    adapter = str(ADAPTERS_DIR / "temporal_graph_runner.py")
    export_dir = os.path.join(export_root, dataset, framework)
    export_dataset = f"kt2_{dataset}_{framework}"
    cmd = [
        python, adapter,
        "--framework", framework,
        "--repo_dir", repo_dir,
        "--data_dir", data_dir,
        "--export_dir", export_dir,
        "--export_dataset_name", export_dataset,
        "--obs_ratio", str(obs_ratio),
        "--max_future_per_cascade", str(max_future),
        "--global_top_n", str(global_top_n),
        "--max_candidates", str(max_candidates),
        "--max_cascades", str(max_cascades),
        "--epochs", str(epochs),
        "--batch_size", str(batch_size),
        "--num_runs", str(num_runs),
        "--gpu", str(gpu),
        "--timeout", str(timeout),
        "--python", python,
    ]
    if run_external:
        cmd.append("--run_external")
    return run_adapter(cmd, cwd=str(SCRIPT_DIR.parent), timeout=timeout + 30)


def external_reproduction_status(model: str, dataset: str, repo_dir: Optional[str], task: str) -> Dict:
    """Record required frontier reproduction status without pretending it ran."""

    if repo_dir and os.path.isdir(repo_dir):
        status = "adapter_pending"
        note = f"{model} repository is available at {repo_dir}, but the frontier adapter was not executed in this run."
    else:
        status = "missing_external_repo"
        note = f"{model} is a planned frontier reproduction target for {task}; provide its repository/data path before claiming reproduction."
    return {
        "model": model,
        "dataset": dataset,
        "task": task,
        "status": status,
        "reproduction_level": "not_run",
        "is_frontier_target": True,
        "note": note,
    }


def _forest_data_dir(forest_dir: str, dataset: str) -> str:
    """Support both FOREST repo roots and migrated forest-data roots."""

    direct = os.path.join(forest_dir, dataset)
    if os.path.isdir(direct):
        return direct
    return os.path.join(forest_dir, "data", dataset)


def write_results_snapshot(results: List[Dict], output: str | Path):
    """Persist partial benchmark outputs after each completed adapter run."""

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    macro_micro_summary = build_macro_micro_framework_summary(results)
    payload_rows = [*results, *macro_micro_result_rows(macro_micro_summary)]
    out_path.write_text(json.dumps(payload_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    macro_micro_path = out_path.with_name(out_path.stem + "_macro_micro_framework.json")
    macro_micro_path.write_text(json.dumps(macro_micro_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    schema_report = validate_benchmark_results(payload_rows)
    schema_path = out_path.with_suffix(out_path.suffix + ".schema.json")
    schema_path.write_text(json.dumps(schema_report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path, macro_micro_path, schema_path, payload_rows, schema_report


def print_table(results: List[Dict]) -> None:
    """Print a comparison table to stdout."""
    cols = [
        "model", "dataset", "msle", "mae", "direction_accuracy", "auc", "average_precision", "candidate_recall_full",
        "hits@10", "map@10", "hits@50", "map@50", "hits@100", "map@100", "mrr", "ndcg@100", "macro_micro_consistency",
    ]
    widths = {c: max(len(c), 8) for c in cols}
    for r in results:
        for c in cols:
            widths[c] = max(widths[c], len(str(r.get(c, "-"))))

    def fmt(v, c):
        if v is None or v == "-":
            return "-".center(widths[c])
        if isinstance(v, float):
            return f"{v:.4f}".rjust(widths[c])
        return str(v).ljust(widths[c])

    sep = "+-" + "-+-".join("-" * widths[c] for c in cols) + "-+"
    header = "| " + " | ".join(c.ljust(widths[c]) for c in cols) + " |"
    print(sep)
    print(header)
    print(sep)
    for r in results:
        row = "| " + " | ".join(fmt(r.get(c, "-"), c) for c in cols) + " |"
        print(row)
    print(sep)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run propagation benchmark suite")
    parser.add_argument("--models", nargs="+", choices=MODELS, default=MODELS)
    parser.add_argument("--tasks", nargs="+", choices=sorted(TASKS), default=None, help="Run model groups by KT2 task")
    parser.add_argument("--datasets", nargs="+", choices=DATASETS, default=["douban"])
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--obs_ratio", type=float, default=0.1, help="RF observation ratio")
    parser.add_argument("--temporal_obs_window_seconds", type=int, default=7 * 24 * 3600)
    parser.add_argument("--lr_obs_ratio", type=float, default=0.3, help="LR edge baseline observation ratio")
    parser.add_argument("--lr_max_future_per_cascade", type=int, default=50)
    parser.add_argument("--lr_max_candidates", type=int, default=100)
    parser.add_argument("--lr_inject_true_parent", action="store_true", help="Reproduce the leaky offline setting by injecting true parent candidates")
    parser.add_argument("--heuristic_obs_ratio", type=float, default=0.3)
    parser.add_argument("--heuristic_max_future_per_cascade", type=int, default=50)
    parser.add_argument("--heuristic_global_top_n", type=int, default=5000)
    parser.add_argument("--heuristic_max_candidates", type=int, default=10000)
    parser.add_argument("--ranker_obs_ratio", type=float, default=0.3)
    parser.add_argument("--ranker_max_future_per_cascade", type=int, default=50)
    parser.add_argument("--ranker_global_top_n", type=int, default=5000)
    parser.add_argument("--ranker_max_candidates", type=int, default=10000)
    parser.add_argument("--ranker_negatives_per_cascade", type=int, default=200)
    parser.add_argument("--hyperidp_obs_ratio", type=float, default=0.3)
    parser.add_argument("--hyperidp_max_future_per_cascade", type=int, default=20)
    parser.add_argument("--hyperidp_global_top_n", type=int, default=3000)
    parser.add_argument("--hyperidp_max_candidates", type=int, default=5000)
    parser.add_argument("--hyperidp_negatives_per_cascade", type=int, default=120)
    parser.add_argument("--hyperidp_bucket_seconds", type=int, default=24 * 3600)
    parser.add_argument("--hyperidp_adv_epochs", type=int, default=200)
    parser.add_argument("--forest_batch_size", type=int, default=32)
    parser.add_argument("--forest_max_train_batches", type=int, default=0)
    parser.add_argument("--forest_max_eval_batches", type=int, default=0)
    parser.add_argument("--forest_rl_epochs", type=int, default=0)
    parser.add_argument("--forest_rl_start_size", type=int, default=5)
    parser.add_argument("--forest_rl_max_batches", type=int, default=0)
    parser.add_argument("--forest_rl_rollout_len", type=int, default=0)
    parser.add_argument("--kt2_joint_obs_ratio", type=float, default=0.3)
    parser.add_argument("--kt2_joint_max_future_per_cascade", type=int, default=20)
    parser.add_argument("--kt2_joint_global_top_n", type=int, default=3000)
    parser.add_argument("--kt2_joint_max_candidates", type=int, default=5000)
    parser.add_argument("--kt2_joint_negatives_per_cascade", type=int, default=120)
    parser.add_argument("--kt2_joint_bucket_seconds", type=int, default=24 * 3600)
    parser.add_argument("--kt2_joint_epochs", type=int, default=200)
    parser.add_argument("--kt2_joint_batch_size", type=int, default=4096)
    parser.add_argument("--kt2_joint_hidden_dim", type=int, default=64)
    parser.add_argument("--kt2_joint_consistency_weight", type=float, default=0.2)
    parser.add_argument("--kt2_joint_trend_weight", type=float, default=0.4)
    parser.add_argument("--kt2_joint_orthogonality_weight", type=float, default=0.05)
    parser.add_argument("--kt2_joint_adversarial_weight", type=float, default=0.02)
    parser.add_argument("--kt2_joint_diffusion_weight", type=float, default=0.05)
    parser.add_argument("--kt2_joint_forest_pg_weight", type=float, default=0.05)
    parser.add_argument("--kt2_joint_diffusion_noise_std", type=float, default=0.15)
    parser.add_argument("--kt2_joint_forest_pg_rollout_samples", type=int, default=2)
    parser.add_argument("--kt2_joint_max_consistency_candidates_per_event", type=int, default=0)
    parser.add_argument("--kt2_joint_use_original_casft_diffusion", action="store_true")
    parser.add_argument("--kt2_joint_use_original_casft_spatiotemporal", action="store_true")
    parser.add_argument("--kt2_joint_original_casft_spatiotemporal_weight", type=float, default=0.01)
    parser.add_argument("--kt2_joint_casft_spatiotemporal_interval_num", type=int, default=4)
    parser.add_argument("--kt2_joint_casft_spatiotemporal_tpp_hdim", type=int, default=16)
    parser.set_defaults(kt2_joint_use_original_minds_components=True, kt2_joint_use_original_minds_full_module=True)
    parser.add_argument(
        "--kt2_joint_use_original_minds_components",
        dest="kt2_joint_use_original_minds_components",
        action="store_true",
        help="Use upstream MINDS components inside KT2JointModel; enabled by default.",
    )
    parser.add_argument(
        "--kt2_joint_disable_original_minds_components",
        dest="kt2_joint_use_original_minds_components",
        action="store_false",
        help="Disable upstream MINDS components for explicit local-bridge ablations.",
    )
    parser.add_argument(
        "--kt2_joint_use_original_minds_full_module",
        dest="kt2_joint_use_original_minds_full_module",
        action="store_true",
        help="Use upstream MINDS Module.forward auxiliary inside KT2JointModel; enabled by default.",
    )
    parser.add_argument(
        "--kt2_joint_disable_original_minds_full_module",
        dest="kt2_joint_use_original_minds_full_module",
        action="store_false",
        help="Disable upstream MINDS Module.forward auxiliary.",
    )
    parser.add_argument("--kt2_joint_original_minds_module_weight", type=float, default=0.01)
    parser.add_argument("--kt2_joint_use_original_forest_components", action="store_true")
    parser.add_argument("--kt2_joint_original_forest_ce_weight", type=float, default=0.02)
    parser.add_argument("--kt2_joint_original_forest_rl_weight", type=float, default=0.0)
    parser.add_argument("--kt2_joint_original_forest_rollout_samples", type=int, default=0)
    parser.add_argument("--kt2_joint_original_forest_start_size", type=int, default=5)
    parser.add_argument("--kt2_joint_casft_diffusion_timesteps", type=int, default=10)
    parser.add_argument("--kt2_joint_casft_sampling_timesteps", type=int, default=5)
    parser.add_argument("--kt2_joint_max_sequence_len", type=int, default=32)
    parser.add_argument("--kt2_joint_max_train_cascades", type=int, default=0)
    parser.add_argument("--kt2_joint_max_test_cascades", type=int, default=0)
    parser.add_argument("--frontier_export_dir", default=str(SCRIPT_DIR / "frontier_exports"), help="Where CasFT/DyGLib/TGN adapters write protocol exports")
    parser.add_argument("--frontier_max_cascades", type=int, default=1000, help="Small-run/export cap for frontier adapters")
    parser.add_argument("--frontier_epochs", type=int, default=200, help="Epochs for external frontier repositories")
    parser.add_argument("--frontier_num_runs", type=int, default=1, help="Number of upstream runs for external temporal graph small-runs")
    parser.add_argument("--frontier_batch_size", type=int, default=64)
    parser.add_argument("--frontier_timeout", type=int, default=1800)
    parser.add_argument("--frontier_gpu", type=int, default=-1, help="GPU id for external frontier scripts; -1 means CPU/fallback where supported")
    parser.add_argument("--run_external_frontier", action="store_true", help="Actually launch upstream CasFT/DyGLib/TGN scripts when their native data/env are ready")
    parser.add_argument("--casft_dataset", default="auto", help="Native CasFT dataset name used only for upstream external runs; auto stages KT2 data under a generated dataset name")
    parser.add_argument("--casft_observation_time", type=int, default=86400)
    parser.add_argument("--casft_prediction_time", type=int, default=1296000)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--forest_dir", default=str(DEFAULT_FOREST_DATA), help="Path to FOREST repo root or migrated forest-data root")
    parser.add_argument("--minds_dir", default=str(DEFAULT_MINDS_REPO), help="Path to MINDS repo root")
    parser.add_argument("--casft_dir", default=str(DEFAULT_CASFT_REPO), help="Path to CasFT repo root")
    parser.add_argument("--dyglib_dir", default=str(DEFAULT_DYGLIB_REPO), help="Path to DyGLib repo root")
    parser.add_argument("--tgn_dir", default=str(DEFAULT_TGN_REPO), help="Path to TGN repo root")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter to use")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    selected_models = list(args.models)
    if args.tasks:
        selected_models = []
        for task in args.tasks:
            selected_models.extend(TASKS[task])
        selected_models = list(dict.fromkeys(selected_models))

    all_results: List[Dict] = []

    for dataset in args.datasets:
        for model in selected_models:
            print(f"\n[benchmark] Running {model.upper()} on {dataset}...")
            t0 = time.time()
            result = None
            task = _task_for_model(model)

            if model == "minds":
                if not args.minds_dir:
                    print("  SKIP: --minds_dir not provided")
                    continue
                result = run_minds(dataset, args.minds_dir, args.python, args.epochs, args.device)

            elif model == "forest":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided")
                    continue
                result = run_forest(
                    dataset,
                    args.forest_dir,
                    args.python,
                    args.epochs,
                    args.device,
                    args.forest_batch_size,
                    args.forest_max_train_batches,
                    args.forest_max_eval_batches,
                    args.forest_rl_epochs,
                    args.forest_rl_start_size,
                    args.forest_rl_max_batches,
                    args.forest_rl_rollout_len,
                )

            elif model == "rf":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided (RF needs FOREST-format data)")
                    continue
                result = run_rf(dataset, args.forest_dir, args.python, args.obs_ratio)

            elif model == "temporal":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided (temporal baseline needs FOREST-format data)")
                    continue
                result = run_temporal(dataset, args.forest_dir, args.python, args.temporal_obs_window_seconds)

            elif model == "lr":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided (LR needs FOREST-format data)")
                    continue
                result = run_lr(
                    dataset,
                    args.forest_dir,
                    args.python,
                    args.lr_obs_ratio,
                    args.lr_max_future_per_cascade,
                    args.lr_max_candidates,
                    args.lr_inject_true_parent,
                )

            elif model == "heuristic":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided (heuristic needs FOREST-format data)")
                    continue
                result = run_heuristic(
                    dataset,
                    args.forest_dir,
                    args.python,
                    args.heuristic_obs_ratio,
                    args.heuristic_max_future_per_cascade,
                    args.heuristic_global_top_n,
                    args.heuristic_max_candidates,
                )

            elif model == "ranker":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided (ranker needs FOREST-format data)")
                    continue
                result = run_ranker(
                    dataset,
                    args.forest_dir,
                    args.python,
                    args.ranker_obs_ratio,
                    args.ranker_max_future_per_cascade,
                    args.ranker_global_top_n,
                    args.ranker_max_candidates,
                    args.ranker_negatives_per_cascade,
                )

            elif model == "hyperidp_proxy":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided (HyperIDP proxy needs FOREST-format data)")
                    continue
                result = run_hyperidp_proxy(
                    dataset,
                    args.forest_dir,
                    args.python,
                    args.hyperidp_obs_ratio,
                    args.hyperidp_max_future_per_cascade,
                    args.hyperidp_global_top_n,
                    args.hyperidp_max_candidates,
                    args.hyperidp_negatives_per_cascade,
                    args.hyperidp_bucket_seconds,
                )

            elif model == "hyperidp_adv_proxy":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided (HyperIDP adversarial proxy needs FOREST-format data)")
                    continue
                result = run_hyperidp_adv_proxy(
                    dataset,
                    args.forest_dir,
                    args.python,
                    args.hyperidp_obs_ratio,
                    args.hyperidp_max_future_per_cascade,
                    args.hyperidp_global_top_n,
                    args.hyperidp_max_candidates,
                    args.hyperidp_negatives_per_cascade,
                    args.hyperidp_bucket_seconds,
                    args.hyperidp_adv_epochs,
                    args.device,
                )

            elif model == "kt2_joint":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided (KT2 joint model needs FOREST-format data)")
                    continue
                result = run_kt2_joint_model(
                    dataset,
                    args.forest_dir,
                    args.python,
                    args.kt2_joint_obs_ratio,
                    args.kt2_joint_max_future_per_cascade,
                    args.kt2_joint_global_top_n,
                    args.kt2_joint_max_candidates,
                    args.kt2_joint_negatives_per_cascade,
                    args.kt2_joint_bucket_seconds,
                    args.kt2_joint_epochs,
                    args.kt2_joint_batch_size,
                    args.kt2_joint_hidden_dim,
                    args.kt2_joint_consistency_weight,
                    args.kt2_joint_trend_weight,
                    args.kt2_joint_orthogonality_weight,
                    args.kt2_joint_adversarial_weight,
                    args.kt2_joint_diffusion_weight,
                    args.kt2_joint_forest_pg_weight,
                    args.kt2_joint_diffusion_noise_std,
                    args.kt2_joint_forest_pg_rollout_samples,
                    args.kt2_joint_max_consistency_candidates_per_event,
                    args.kt2_joint_max_sequence_len,
                    args.kt2_joint_max_train_cascades,
                    args.kt2_joint_max_test_cascades,
                    args.kt2_joint_use_original_casft_diffusion,
                    args.kt2_joint_use_original_casft_spatiotemporal,
                    args.kt2_joint_original_casft_spatiotemporal_weight,
                    args.kt2_joint_casft_spatiotemporal_interval_num,
                    args.kt2_joint_casft_spatiotemporal_tpp_hdim,
                    args.casft_dir,
                    args.kt2_joint_use_original_minds_components,
                    args.kt2_joint_use_original_minds_full_module,
                    args.kt2_joint_original_minds_module_weight,
                    args.minds_dir,
                    args.kt2_joint_use_original_forest_components,
                    args.kt2_joint_original_forest_ce_weight,
                    args.kt2_joint_original_forest_rl_weight,
                    args.kt2_joint_original_forest_rollout_samples,
                    args.kt2_joint_original_forest_start_size,
                    args.kt2_joint_casft_diffusion_timesteps,
                    args.kt2_joint_casft_sampling_timesteps,
                    args.device,
                )

            elif model == "casft":
                result = run_casft_frontier(
                    dataset,
                    args.forest_dir,
                    args.casft_dir,
                    args.python,
                    args.frontier_export_dir,
                    args.frontier_max_cascades,
                    args.obs_ratio,
                    args.frontier_timeout,
                    args.run_external_frontier,
                    args.casft_dataset,
                    args.casft_observation_time,
                    args.casft_prediction_time,
                    args.frontier_epochs,
                )

            elif model == "dyglib":
                result = run_temporal_graph_frontier(
                    "dyglib",
                    dataset,
                    args.forest_dir,
                    args.dyglib_dir,
                    args.python,
                    args.frontier_export_dir,
                    args.frontier_max_cascades,
                    args.ranker_obs_ratio,
                    args.ranker_max_future_per_cascade,
                    args.ranker_global_top_n,
                    args.ranker_max_candidates,
                    args.frontier_epochs,
                    args.frontier_batch_size,
                    args.frontier_num_runs,
                    args.frontier_gpu,
                    args.frontier_timeout,
                    args.run_external_frontier,
                )

            elif model == "tgn":
                result = run_temporal_graph_frontier(
                    "tgn",
                    dataset,
                    args.forest_dir,
                    args.tgn_dir,
                    args.python,
                    args.frontier_export_dir,
                    args.frontier_max_cascades,
                    args.ranker_obs_ratio,
                    args.ranker_max_future_per_cascade,
                    args.ranker_global_top_n,
                    args.ranker_max_candidates,
                    args.frontier_epochs,
                    args.frontier_batch_size,
                    args.frontier_num_runs,
                    args.frontier_gpu,
                    args.frontier_timeout,
                    args.run_external_frontier,
                )

            elapsed = time.time() - t0
            if result:
                result.setdefault("dataset", dataset)
                result.setdefault("task", task)
                result.setdefault("status", "ok")
                result.setdefault("reproduction_level", _reproduction_level(model))
                result["elapsed_s"] = round(elapsed, 1)
                all_results.append(result)
                write_results_snapshot(all_results, args.output)
                print(f"  Done in {elapsed:.0f}s")
            else:
                all_results.append(
                    {
                        "model": model.upper(),
                        "dataset": dataset,
                        "task": task,
                        "status": "failed",
                        "reproduction_level": _reproduction_level(model),
                    }
                )
                write_results_snapshot(all_results, args.output)

    out_path, macro_micro_path, schema_path, payload_rows, schema_report = write_results_snapshot(all_results, args.output)
    print(f"\n[benchmark] Results saved to {out_path}")
    print(f"[benchmark] Macro/micro framework summary saved to {macro_micro_path}")
    print(f"[benchmark] Schema report saved to {schema_path}")
    if not schema_report["ok"]:
        print("[benchmark] SCHEMA ERRORS:")
        for error in schema_report["errors"]:
            print(f"  - {error}")

    successful = [r for r in payload_rows if "msle" in r or "hits@10" in r or "auc" in r or "macro_micro_consistency" in r]
    if successful:
        print()
        print_table(successful)

def _task_for_model(model: str) -> str:
    if model in {"rf", "temporal", "casft"}:
        return "scale"
    if model in {"lr", "heuristic", "ranker", "dyglib", "tgn"}:
        return "next_hop"
    return "multi_scale"


def _reproduction_level(model: str) -> str:
    if model in {"minds", "forest"}:
        return "public_code_adapter"
    if model in {"hyperidp_proxy", "hyperidp_adv_proxy"}:
        return "protocol_proxy_not_original_architecture"
    if model == "kt2_joint":
        return "kt2_joint_model_small_run"
    if model in {"casft", "dyglib", "tgn"}:
        return "planned_frontier_reproduction"
    return "local_baseline"


if __name__ == "__main__":
    main()
