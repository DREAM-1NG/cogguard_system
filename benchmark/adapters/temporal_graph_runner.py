#!/usr/bin/env python3
"""DyGLib/TGN temporal-graph adapter for KT2 next-hop prediction.

This adapter exports FOREST cascades to temporal edge streams and can optionally
launch upstream DyGLib/TGN scripts. When the external environment is not ready,
it returns a protocol-level temporal graph baseline with explicit status.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from cascade_io import (
    dyglib_raw_csv_from_edge_stream,
    forest_to_temporal_edges,
    hits_map_mrr_ndcg,
    load_forest_split,
    train_statistics,
    unique_preserving_order,
)

K_LIST = (10, 50, 100)


def candidate_rank(
    observed_users: Sequence[int],
    global_candidates: Sequence[int],
    transitions: Dict[int, Counter],
    max_candidates: int,
) -> List[int]:
    observed_set = set(observed_users)
    candidate_set = set(global_candidates)
    transition_counts = Counter()
    for recency_rank, user in enumerate(reversed(observed_users)):
        weight = 1.0 / (recency_rank + 1)
        for nxt, count in transitions.get(user, {}).items():
            if nxt not in observed_set:
                candidate_set.add(nxt)
                transition_counts[nxt] += count * weight
    candidate_set.difference_update(observed_set)
    scored = []
    for candidate in candidate_set:
        score = transition_counts.get(candidate, 0.0)
        scored.append((score, -candidate, candidate))
    scored.sort(reverse=True)
    return [candidate for _, _, candidate in scored[:max_candidates]]


def protocol_next_hop_baseline(data_dir: str | Path, obs_ratio: float, max_future: int, global_top_n: int, max_candidates: int) -> Dict:
    train, valid, test = load_forest_split(data_dir)
    train_all = train + valid
    popularity, transitions = train_statistics(train_all)
    allowed_candidate_users = set(popularity)
    global_candidates = [user for user, _ in popularity.most_common(global_top_n)]
    total_relevant = 0
    total_covered = 0
    events = 0
    audit_observed_violations = 0
    audit_future_only_violations = 0
    audit_candidates_checked = 0
    metric_sums = {f"hits@{k}": 0.0 for k in K_LIST}
    metric_sums.update({f"map@{k}": 0.0 for k in K_LIST})
    metric_sums.update({f"ndcg@{k}": 0.0 for k in K_LIST})
    metric_sums["mrr"] = 0.0

    for cascade in test:
        users = [user for user, _ in cascade]
        cut = max(2, int(len(users) * obs_ratio))
        if cut >= len(users):
            continue
        observed_users = unique_preserving_order(users[:cut])
        observed_set = set(observed_users)
        future_users = set(users[cut : min(len(users), cut + max_future)]) - observed_set
        if not future_users:
            continue
        ranked = candidate_rank(observed_users, global_candidates, transitions, max_candidates)
        audit_candidates_checked += len(ranked)
        audit_observed_violations += sum(1 for candidate in ranked if candidate in observed_set)
        future_only_users = set(users[cut:]) - observed_set - allowed_candidate_users
        audit_future_only_violations += sum(1 for candidate in ranked if candidate in future_only_users)
        labels = np.asarray([1 if candidate in future_users else 0 for candidate in ranked], dtype=int)
        metrics = hits_map_mrr_ndcg(labels, len(future_users), K_LIST)
        events += 1
        total_relevant += len(future_users)
        total_covered += int(labels.sum())
        for key, value in metrics.items():
            metric_sums[key] += value

    result = {
        "events_test": events,
        "relevant_users_test": total_relevant,
        "candidate_recall_full": total_covered / max(total_relevant, 1),
        "candidate_protocol_audit": {
            "candidate_source": "train+valid popularity and train+valid transition statistics plus observed-prefix users",
            "future_nodes_injected": False,
            "observed_user_candidate_violations": audit_observed_violations,
            "future_only_candidate_violations": audit_future_only_violations,
            "candidates_checked": audit_candidates_checked,
            "leakage_check_passed": audit_observed_violations == 0 and audit_future_only_violations == 0,
        },
    }
    for key, value in metric_sums.items():
        result[key] = value / max(events, 1)
    return result


def prepare_dyglib_dataset(repo_dir: Path, dataset_name: str, edge_csv: Path) -> Path:
    upstream_name = dyglib_upstream_dataset_alias(dataset_name)
    raw_dir = repo_dir / "DG_data" / upstream_name
    if raw_dir.exists() and not (raw_dir / ".kt2_generated").exists():
        raise RuntimeError(f"Refusing to overwrite existing DyGLib dataset alias: {raw_dir}")
    raw_path = raw_dir / f"{upstream_name}.csv"
    dyglib_raw_csv_from_edge_stream(edge_csv, raw_path, reindex=True)
    (raw_dir / ".kt2_generated").write_text(dataset_name, encoding="utf-8")
    write_dyglib_check_baseline(raw_path, raw_dir, upstream_name)
    return raw_path


def prepare_tgn_dataset(repo_dir: Path, dataset_name: str, edge_csv: Path) -> Path:
    data_dir = repo_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_path = data_dir / f"{dataset_name}.csv"
    dyglib_raw_csv_from_edge_stream(edge_csv, raw_path, reindex=True)
    return raw_path


def dyglib_upstream_dataset_alias(dataset_name: str) -> str:
    return dataset_name if dataset_name in {"wikipedia", "reddit"} else "wikipedia"


def write_dyglib_check_baseline(raw_path: Path, raw_dir: Path, dataset_name: str, node_feat_dim: int = 16) -> None:
    """Mirror DyGLib preprocessing outputs so its built-in check_data passes for KT2 data."""

    df = pd.read_csv(raw_path)
    new_df = df[["u", "i", "ts", "label"]].copy()
    new_df["label"] = new_df["label"].astype(float)
    upper_u = int(df.u.max()) + 1
    new_df["i"] = new_df["i"] + upper_u
    new_df["u"] = new_df["u"] + 1
    new_df["i"] = new_df["i"] + 1
    new_df["idx"] = list(range(1, len(new_df) + 1))
    edge_feats = df.drop(columns=["u", "i", "ts", "label"], errors="ignore").to_numpy(dtype=float)
    if edge_feats.size == 0:
        edge_feats = np.zeros((len(df), 1), dtype=float)
    edge_feats = np.vstack([np.zeros(edge_feats.shape[1], dtype=float)[np.newaxis, :], edge_feats])
    max_idx = int(max(new_df.u.max(), new_df.i.max()))
    node_feats = np.zeros((max_idx + 1, node_feat_dim), dtype=float)
    new_df.to_csv(raw_dir / f"ml_{dataset_name}.csv")
    np.save(raw_dir / f"ml_{dataset_name}.npy", edge_feats)
    np.save(raw_dir / f"ml_{dataset_name}_node.npy", node_feats)


def run_external_dyglib(args, edge_csv: Path) -> Dict:
    repo = Path(args.repo_dir)
    kt2_dataset_name = args.export_dataset_name
    dataset_name = dyglib_upstream_dataset_alias(kt2_dataset_name)
    try:
        raw_path = prepare_dyglib_dataset(repo, kt2_dataset_name, edge_csv)
    except RuntimeError as exc:
        return external_failure(
            "DyGFormer/DyGLib",
            "external_dataset_conflict",
            str(exc),
            {"kt2_export_dataset_name": kt2_dataset_name, "dyglib_dataset_alias": dataset_name},
        )
    preprocess_cmd = [args.python, "preprocess_data.py", "--dataset_name", dataset_name, "--node_feat_dim", "16"]
    train_cmd = [
        args.python,
        "train_link_prediction.py",
        "--dataset_name",
        dataset_name,
        "--model_name",
        args.model_name,
        "--num_runs",
        str(args.num_runs),
        "--num_epochs",
        str(args.epochs),
        "--batch_size",
        str(args.batch_size),
        "--patch_size",
        "2",
        "--max_input_sequence_length",
        "32",
        "--gpu",
        str(args.gpu),
    ]
    log_dir = Path(args.export_dir) / "logs"
    started = time.time()
    env = external_env(Path(args.export_dir))
    pre = subprocess.run(preprocess_cmd, cwd=repo / "preprocess_data", capture_output=True, text=True, timeout=args.timeout, env=env)
    pre_logs = write_run_logs(log_dir, "dyglib_preprocess", preprocess_cmd, pre.stdout, pre.stderr, pre.returncode)
    if pre.returncode != 0:
        return external_failure("DyGFormer/DyGLib", "preprocess_failed", pre.stderr, pre_logs)
    proc = subprocess.run(train_cmd, cwd=repo, capture_output=True, text=True, timeout=args.timeout, env=env)
    train_logs = write_run_logs(log_dir, "dyglib_train", train_cmd, proc.stdout, proc.stderr, proc.returncode)
    cleanup = clean_dyglib_generated_outputs(repo)
    if proc.returncode != 0:
        merged_logs = {**pre_logs, "train_stdout_log": train_logs["stdout_log"], "train_stderr_log": train_logs["stderr_log"], "train_command_log": train_logs["command_log"]}
        merged_logs.update(cleanup)
        return external_failure("DyGFormer/DyGLib", "train_failed", proc.stderr, merged_logs)
    return {
        "model": "DyGFormer/DyGLib",
        "status": "ok",
        "task": "next_hop",
        "reproduction_level": "frontier_reproduction_small_run",
        "kt2_export_dataset_name": kt2_dataset_name,
        "dyglib_dataset_alias": dataset_name,
        "dyglib_raw_csv": str(raw_path),
        "seed": 0,
        "num_runs": args.num_runs,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "log_dir": str(log_dir),
        "preprocess_stdout_log": pre_logs["stdout_log"],
        "preprocess_stderr_log": pre_logs["stderr_log"],
        "preprocess_command_log": pre_logs["command_log"],
        "train_stdout_log": train_logs["stdout_log"],
        "train_stderr_log": train_logs["stderr_log"],
        "train_command_log": train_logs["command_log"],
        **cleanup,
        "elapsed_s": round(time.time() - started, 1),
        "note": "DyGLib upstream training completed; event-level Top-K still uses KT2 candidate protocol metrics for comparability.",
    }


def run_external_tgn(args, edge_csv: Path) -> Dict:
    repo = Path(args.repo_dir)
    dataset_name = args.export_dataset_name
    prepare_tgn_dataset(repo, dataset_name, edge_csv)
    log_dir = Path(args.export_dir) / "logs"
    pre_cmd = [args.python, "utils/preprocess_data.py", "--data", dataset_name]
    env = external_env(Path(args.export_dir))
    pre = subprocess.run(pre_cmd, cwd=repo, capture_output=True, text=True, timeout=args.timeout, env=env)
    pre_logs = write_run_logs(log_dir, "tgn_preprocess", pre_cmd, pre.stdout, pre.stderr, pre.returncode)
    if pre.returncode != 0:
        return external_failure("TGN", "preprocess_failed", pre.stderr, pre_logs)
    cmd = [
        args.python,
        "train_self_supervised.py",
        "-d",
        dataset_name,
        "--prefix",
        f"kt2_{dataset_name}",
        "--n_runs",
        str(args.num_runs),
        "--n_epoch",
        str(args.epochs),
        "--bs",
        str(args.batch_size),
        "--n_degree",
        "10",
    ]
    if args.gpu >= 0:
        cmd += ["--gpu", str(args.gpu)]
    proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=args.timeout, env=env)
    train_logs = write_run_logs(log_dir, "tgn_train", cmd, proc.stdout, proc.stderr, proc.returncode)
    cleanup = clean_tgn_generated_outputs(repo)
    if proc.returncode != 0:
        merged_logs = {**pre_logs, "train_stdout_log": train_logs["stdout_log"], "train_stderr_log": train_logs["stderr_log"], "train_command_log": train_logs["command_log"]}
        merged_logs.update(cleanup)
        return external_failure("TGN", "train_failed", proc.stderr, merged_logs)
    return {
        "model": "TGN",
        "status": "ok",
        "task": "next_hop",
        "reproduction_level": "frontier_reproduction_small_run",
        "seed": 0,
        "num_runs": args.num_runs,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "log_dir": str(log_dir),
        "preprocess_stdout_log": pre_logs["stdout_log"],
        "preprocess_stderr_log": pre_logs["stderr_log"],
        "preprocess_command_log": pre_logs["command_log"],
        "train_stdout_log": train_logs["stdout_log"],
        "train_stderr_log": train_logs["stderr_log"],
        "train_command_log": train_logs["command_log"],
        **cleanup,
        "note": "TGN upstream self-supervised training completed; event-level Top-K uses KT2 protocol metrics for comparability.",
    }


def external_failure(model: str, status: str, stderr: str, logs: Optional[Dict] = None) -> Dict:
    logs = logs or {}
    return {
        "model": model,
        "status": status,
        "task": "next_hop",
        "reproduction_level": "frontier_reproduction_attempted",
        **logs,
        "stderr_tail": stderr.strip().splitlines()[-8:],
        "note": "External temporal graph run failed; do not claim frontier reproduction completion.",
    }


def clean_tgn_generated_outputs(repo: Path) -> Dict:
    removed = []
    for name in ("saved_models", "saved_results"):
        target = repo / name
        if target.exists() and _is_within(target, repo):
            shutil.rmtree(target)
            removed.append(str(target))
    return {
        "tgn_generated_outputs_cleaned": bool(removed),
        "tgn_generated_cleanup_paths": removed,
    }


def clean_dyglib_generated_outputs(repo: Path) -> Dict:
    removed = []
    for name in ("logs", "saved_models", "saved_results"):
        target = repo / name
        if target.exists() and _is_within(target, repo):
            shutil.rmtree(target)
            removed.append(str(target))
    return {
        "dyglib_generated_outputs_cleaned": bool(removed),
        "dyglib_generated_cleanup_paths": removed,
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework", choices=["dyglib", "tgn"], required=True)
    parser.add_argument("--repo_dir", required=True)
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--export_dir", required=True)
    parser.add_argument("--export_dataset_name", default="kt2_forest")
    parser.add_argument("--model_name", default="DyGFormer")
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--max_future_per_cascade", type=int, default=50)
    parser.add_argument("--global_top_n", type=int, default=5000)
    parser.add_argument("--max_candidates", type=int, default=10000)
    parser.add_argument("--max_cascades", type=int, default=1000)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--num_runs", type=int, default=1)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--gpu", type=int, default=-1)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--run_external", action="store_true")
    parser.add_argument(
        "--use_proxy_metrics",
        action="store_true",
        help=(
            "Opt in to the transition/popularity protocol baseline metrics. "
            "By default DyGFormer/TGN rows do not emit event-level Top-K metrics unless learned scores are wired."
        ),
    )
    args = parser.parse_args()

    repo = Path(args.repo_dir)
    if not repo.exists():
        model = "DyGFormer/DyGLib" if args.framework == "dyglib" else "TGN"
        print(json.dumps({"model": model, "status": "missing_external_repo", "reproduction_level": "not_run"}))
        return

    export_dir = Path(args.export_dir)
    edge_csv = forest_to_temporal_edges(args.data_dir, export_dir / f"{args.export_dataset_name}_temporal_edges.csv", max_cascades=args.max_cascades)
    result = {
        "model": "DyGFormer/DyGLib" if args.framework == "dyglib" else "TGN",
        "dataset": Path(args.data_dir).name,
        "task": "next_hop",
        "status": "temporal_edge_export_only",
        "reproduction_level": "frontier_data_adapter_ready_not_model_run",
        "temporal_edge_csv": str(edge_csv),
        "repo_head": git_head(repo),
        "event_topk_score_source": "unavailable",
        "learned_event_topk_available": False,
        "note": (
            "Temporal edge stream exported without future-node injection. "
            "No event-level Top-K metrics are emitted by default because the upstream learned scores "
            "are not yet wired into the cascade-prefix candidate ranking evaluator."
        ),
    }
    if args.use_proxy_metrics:
        proxy = protocol_next_hop_baseline(
            args.data_dir,
            args.obs_ratio,
            args.max_future_per_cascade,
            args.global_top_n,
            args.max_candidates,
        )
        proxy.update(
            {
                "event_topk_score_source": "transition_popularity_proxy_not_learned",
                "learned_event_topk_available": False,
                "proxy_metrics_opt_in": True,
                "proxy_warning": (
                    "These Top-K metrics come from the protocol transition/popularity baseline, "
                    "not from DyGFormer/TGN learned scores. Do not use them for learned SOTA comparison."
                ),
            }
        )
        result.update(proxy)
    if args.run_external:
        external = run_external_dyglib(args, edge_csv) if args.framework == "dyglib" else run_external_tgn(args, edge_csv)
        result.update(external)
        result.setdefault("event_topk_score_source", "unavailable")
        result.setdefault("learned_event_topk_available", False)
        if not result.get("learned_event_topk_available"):
            result["event_topk_status"] = "learned_score_adapter_missing"
            result["note"] = (
                f"{result.get('model')} upstream training/export path completed or was attempted, "
                "but event-level Top-K user ranking is not reported because learned per-candidate scores "
                "are not yet extracted from the trained model."
            )
    print(json.dumps(result, ensure_ascii=False))


def git_head(path: Path) -> Optional[str]:
    try:
        proc = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def write_run_logs(log_dir: Path, stem: str, cmd: List[str], stdout, stderr, returncode: Optional[int]) -> Dict:
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{stem}.stdout.log"
    stderr_path = log_dir / f"{stem}.stderr.log"
    command_path = log_dir / f"{stem}.command.json"
    stdout_path.write_text(_decode_stream(stdout), encoding="utf-8")
    stderr_path.write_text(_decode_stream(stderr), encoding="utf-8")
    command_path.write_text(
        json.dumps({"command": cmd, "returncode": returncode}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "command": cmd,
        "log_dir": str(log_dir),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "command_log": str(command_path),
    }


def _decode_stream(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def external_env(export_dir: Path) -> Dict[str, str]:
    shim_dir = export_dir.resolve() / "runtime_shims"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "sitecustomize.py"
    shim.write_text(
        "import random\n"
        "_orig_sample = random.sample\n"
        "def _kt2_sample(population, k, *args, **kwargs):\n"
        "    if isinstance(population, set):\n"
        "        population = sorted(population)\n"
        "    return _orig_sample(population, k, *args, **kwargs)\n"
        "random.sample = _kt2_sample\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    previous = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(shim_dir) + (os.pathsep + previous if previous else "")
    return env


if __name__ == "__main__":
    main()
