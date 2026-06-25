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
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
ADAPTERS_DIR = SCRIPT_DIR / "adapters"
DEFAULT_OUTPUT = SCRIPT_DIR / "results.json"

MODELS = ["minds", "forest", "rf", "temporal", "lr", "heuristic", "ranker", "hyperidp_proxy", "hyperidp_adv_proxy"]
DATASETS = ["douban", "twitter", "christianity"]
K_LIST = [10, 50, 100]


def run_adapter(cmd: List[str], cwd: str, timeout: int = 1800) -> Optional[Dict]:
    """Run an adapter subprocess and parse JSON from its last stdout line."""
    print(f"  CMD: {' '.join(cmd)}")
    print(f"  CWD: {cwd}")
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return None
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return None

    if proc.returncode != 0:
        print(f"  FAILED (rc={proc.returncode})")
        if proc.stderr:
            for line in proc.stderr.strip().split("\n")[-5:]:
                print(f"    stderr: {line}")
        return None

    for line in reversed(proc.stdout.strip().split("\n")):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    print("  WARNING: no JSON found in output")
    if proc.stdout:
        for line in proc.stdout.strip().split("\n")[-3:]:
            print(f"    stdout: {line}")
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
    cwd = os.path.join(minds_dir, "MINDS")
    if not os.path.isdir(cwd):
        cwd = minds_dir
    return run_adapter(cmd, cwd=cwd)


def run_forest(dataset: str, forest_dir: str, python: str, epochs: int, device: str) -> Optional[Dict]:
    """Run FOREST adapter."""
    adapter = str(ADAPTERS_DIR / "forest_runner.py")
    cmd = [
        python, adapter,
        "--data_name", dataset,
        "--epochs", str(epochs),
        "--device", device,
    ]
    return run_adapter(cmd, cwd=forest_dir)


def run_rf(dataset: str, forest_dir: str, python: str, obs_ratio: float) -> Optional[Dict]:
    """Run RF baseline adapter."""
    adapter = str(ADAPTERS_DIR / "rf_baseline.py")
    data_dir = os.path.join(forest_dir, "data", dataset)
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
    data_dir = os.path.join(forest_dir, "data", dataset)
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
    data_dir = os.path.join(forest_dir, "data", dataset)
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
    data_dir = os.path.join(forest_dir, "data", dataset)
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
    data_dir = os.path.join(forest_dir, "data", dataset)
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
    data_dir = os.path.join(forest_dir, "data", dataset)
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
    data_dir = os.path.join(forest_dir, "data", dataset)
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


def print_table(results: List[Dict]) -> None:
    """Print a comparison table to stdout."""
    cols = [
        "model", "dataset", "msle", "mae", "direction_accuracy", "auc", "average_precision", "candidate_recall_full",
        "hits@10", "map@10", "hits@50", "map@50", "hits@100", "map@100", "mrr", "ndcg@100",
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


def main():
    parser = argparse.ArgumentParser(description="Run propagation benchmark suite")
    parser.add_argument("--models", nargs="+", choices=MODELS, default=MODELS)
    parser.add_argument("--datasets", nargs="+", choices=DATASETS, default=["douban"])
    parser.add_argument("--epochs", type=int, default=30)
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
    parser.add_argument("--hyperidp_adv_epochs", type=int, default=5)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--forest_dir", default=None, help="Path to FOREST repo root")
    parser.add_argument("--minds_dir", default=None, help="Path to MINDS repo root")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter to use")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    args = parser.parse_args()

    all_results: List[Dict] = []

    for dataset in args.datasets:
        for model in args.models:
            print(f"\n[benchmark] Running {model.upper()} on {dataset}...")
            t0 = time.time()
            result = None

            if model == "minds":
                if not args.minds_dir:
                    print("  SKIP: --minds_dir not provided")
                    continue
                result = run_minds(dataset, args.minds_dir, args.python, args.epochs, args.device)

            elif model == "forest":
                if not args.forest_dir:
                    print("  SKIP: --forest_dir not provided")
                    continue
                result = run_forest(dataset, args.forest_dir, args.python, args.epochs, args.device)

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

            elapsed = time.time() - t0
            if result:
                result.setdefault("dataset", dataset)
                result["elapsed_s"] = round(elapsed, 1)
                all_results.append(result)
                print(f"  Done in {elapsed:.0f}s")
            else:
                all_results.append({"model": model.upper(), "dataset": dataset, "status": "failed"})

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[benchmark] Results saved to {out_path}")

    successful = [r for r in all_results if "msle" in r or "hits@10" in r or "auc" in r]
    if successful:
        print()
        print_table(successful)


if __name__ == "__main__":
    main()
