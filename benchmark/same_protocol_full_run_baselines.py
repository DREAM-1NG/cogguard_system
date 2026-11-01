from __future__ import annotations

import argparse
import json
import pickle
import subprocess
import threading
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmark"
ADAPTERS_DIR = BENCHMARK_DIR / "adapters"
DEFAULT_FOREST_DATA = Path(r"G:\CISCN\dataset\forest-data")
DEFAULT_MINDS_REPO = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS")
DEFAULT_FOREST_REPO = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST")
DEFAULT_CASFT_REPO = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT")

PRIMARY_BASELINES = ("MINDS", "FOREST", "CasFT")


def parse_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def baseline_row_key(row: Dict) -> Tuple[str, str, int, str]:
    seed = row.get("seed", -1)
    try:
        seed_value = int(seed)
    except (TypeError, ValueError):
        seed_value = -1
    return (
        str(row.get("dataset", "")),
        str(row.get("model", "")),
        seed_value,
        str(row.get("config_id", "")),
    )


def load_existing_rows(out: Path) -> List[Dict]:
    if not out.is_file():
        return []
    try:
        payload = json.loads(out.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        raw_rows = payload.get("rows", [])
    elif isinstance(payload, list):
        raw_rows = payload
    else:
        raw_rows = []
    dedup: Dict[Tuple[str, str, int, str], Dict] = {}
    for row in raw_rows:
        if isinstance(row, dict):
            dedup[baseline_row_key(row)] = row
    return list(dedup.values())


def upsert_row(rows: List[Dict], row: Dict) -> List[Dict]:
    key = baseline_row_key(row)
    replaced = False
    merged: List[Dict] = []
    for existing in rows:
        if baseline_row_key(existing) == key:
            merged.append(row)
            replaced = True
        else:
            merged.append(existing)
    if not replaced:
        merged.append(row)
    return merged


def failure_records(rows: List[Dict]) -> List[Dict]:
    failures = []
    for row in rows:
        if row.get("status") != "ok":
            failures.append(
                {
                    "model": row.get("model"),
                    "dataset": row.get("dataset"),
                    "seed": row.get("seed"),
                    "status": row.get("status"),
                    "note": row.get("note"),
                }
            )
    return failures


def last_json(stdout: str) -> Optional[Dict]:
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def run_adapter(
    cmd: Sequence[str],
    cwd: Path,
    timeout: int,
    model: str,
    dataset: str,
    config_id: str,
    seed: int,
    log_path: Optional[Path] = None,
) -> Dict:
    started = time.time()
    if log_path is not None:
        return run_adapter_streaming(cmd, cwd, timeout, model, dataset, config_id, seed, Path(log_path), started)
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return failure_row(
            model,
            dataset,
            "timeout",
            config_id,
            seed,
            f"{model} adapter exceeded {timeout}s.",
            list(cmd),
            cwd,
            stdout=decode_stream(exc.stdout),
            stderr=decode_stream(exc.stderr),
            elapsed_s=round(time.time() - started, 1),
        )
    except Exception as exc:  # pragma: no cover - defensive subprocess failure.
        return failure_row(
            model,
            dataset,
            "failed",
            config_id,
            seed,
            f"{model} adapter could not start: {type(exc).__name__}: {exc}",
            list(cmd),
            cwd,
            elapsed_s=round(time.time() - started, 1),
        )

    parsed = last_json(proc.stdout)
    if parsed is None:
        return failure_row(
            model,
            dataset,
            "failed",
            config_id,
            seed,
            f"{model} adapter produced no parseable JSON.",
            list(cmd),
            cwd,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
            elapsed_s=round(time.time() - started, 1),
        )
    parsed.setdefault("model", model)
    parsed.setdefault("dataset", dataset)
    parsed.setdefault("config_id", config_id)
    parsed.setdefault("seed", seed)
    parsed.setdefault("command", list(cmd))
    parsed.setdefault("cwd", str(cwd))
    parsed.setdefault("returncode", proc.returncode)
    parsed.setdefault("elapsed_s", round(time.time() - started, 1))
    if proc.returncode != 0:
        parsed.setdefault("status", "failed")
        parsed.setdefault("note", f"{model} adapter exited with returncode={proc.returncode}.")
        parsed.setdefault("stderr_tail", proc.stderr.strip().splitlines()[-8:])
    return parsed


def run_adapter_streaming(
    cmd: Sequence[str],
    cwd: Path,
    timeout: int,
    model: str,
    dataset: str,
    config_id: str,
    seed: int,
    log_path: Path,
    started: float,
) -> Dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []

    def drain(stream, sink: List[str], log_handle, prefix: str) -> None:
        for line in iter(stream.readline, ""):
            sink.append(line)
            log_handle.write(f"{prefix}{line}")
            log_handle.flush()

    with log_path.open("w", encoding="utf-8", errors="replace") as log_handle:
        log_handle.write("$ " + " ".join(str(part) for part in cmd) + "\n")
        log_handle.flush()
        try:
            proc = subprocess.Popen(
                list(cmd),
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:  # pragma: no cover - defensive subprocess failure.
            return failure_row(
                model,
                dataset,
                "failed",
                config_id,
                seed,
                f"{model} adapter could not start: {type(exc).__name__}: {exc}",
                list(cmd),
                cwd,
                elapsed_s=round(time.time() - started, 1),
            )

        threads = [
            threading.Thread(target=drain, args=(proc.stdout, stdout_lines, log_handle, ""), daemon=True),
            threading.Thread(target=drain, args=(proc.stderr, stderr_lines, log_handle, "[stderr] "), daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            returncode = proc.wait()
            for thread in threads:
                thread.join(timeout=2)
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)
            return failure_row(
                model,
                dataset,
                "timeout",
                config_id,
                seed,
                f"{model} adapter exceeded {timeout}s.",
                list(cmd),
                cwd,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                elapsed_s=round(time.time() - started, 1),
            )
        for thread in threads:
            thread.join(timeout=2)

    stdout = "".join(stdout_lines)
    stderr = "".join(stderr_lines)
    parsed = last_json(stdout)
    if parsed is None:
        return failure_row(
            model,
            dataset,
            "failed",
            config_id,
            seed,
            f"{model} adapter produced no parseable JSON.",
            list(cmd),
            cwd,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            elapsed_s=round(time.time() - started, 1),
        )
    parsed.setdefault("model", model)
    parsed.setdefault("dataset", dataset)
    parsed.setdefault("config_id", config_id)
    parsed.setdefault("seed", seed)
    parsed.setdefault("command", list(cmd))
    parsed.setdefault("cwd", str(cwd))
    parsed.setdefault("returncode", returncode)
    parsed.setdefault("elapsed_s", round(time.time() - started, 1))
    parsed.setdefault("log_path", str(log_path))
    if returncode != 0:
        parsed.setdefault("status", "failed")
        parsed.setdefault("note", f"{model} adapter exited with returncode={returncode}.")
        parsed.setdefault("stderr_tail", stderr.strip().splitlines()[-8:])
    return parsed


def failure_row(
    model: str,
    dataset: str,
    status: str,
    config_id: str,
    seed: int,
    note: str,
    cmd: Sequence[str],
    cwd: Path,
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: Optional[int] = None,
    elapsed_s: Optional[float] = None,
) -> Dict:
    return {
        "model": model,
        "dataset": dataset,
        "task": "scale" if model == "CasFT" else "multi_scale",
        "status": status,
        "reproduction_level": "frontier_reproduction_attempted",
        "config_id": config_id,
        "seed": seed,
        "command": list(cmd),
        "cwd": str(cwd),
        "returncode": returncode,
        "elapsed_s": elapsed_s,
        "stdout_tail": (stdout or "").strip().splitlines()[-8:],
        "stderr_tail": (stderr or "").strip().splitlines()[-8:],
        "note": note,
    }


def decode_stream(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def resolve_minds_work_dir(minds_repo: Path) -> Optional[Path]:
    candidates = [minds_repo / "MINDS", minds_repo, minds_repo / ".kt2_extracted" / "MINDS"]
    for candidate in candidates:
        if (candidate / "run.py").is_file() and (candidate / "Module.py").is_file():
            return candidate
    zip_path = minds_repo / "MINDS.zip"
    extract_root = minds_repo / ".kt2_extracted"
    extracted = extract_root / "MINDS"
    if zip_path.is_file():
        if not (extracted / "run.py").is_file():
            extract_root.mkdir(parents=True, exist_ok=True)
            import zipfile

            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_root)
        if (extracted / "run.py").is_file() and (extracted / "Module.py").is_file():
            return extracted
    return None


def prepare_minds_forest_dataset(forest_dataset_dir: Path, minds_work_dir: Path, dataset: str, max_cascades: int) -> Dict:
    target = minds_work_dir / "data" / f"kt2_{dataset}"
    target.mkdir(parents=True, exist_ok=True)
    cascade_rows, users = convert_forest_cascades_to_minds(
        forest_dataset_dir / "cascade.txt",
        max_cascades=max_cascades,
    )
    if not cascade_rows:
        return {"status": "missing_data", "dataset_name": target.name, "note": f"No cascades converted from {forest_dataset_dir}."}
    (target / "cascades.txt").write_text("".join(cascade_rows), encoding="utf-8")
    edge_rows = convert_edges_to_minds(forest_dataset_dir / "edges.txt", users)
    (target / "edges.txt").write_text("".join(edge_rows), encoding="utf-8")
    idx2u = ["<blank>", "</s>"] + sorted(users, key=lambda value: int(value) if str(value).isdigit() else str(value))
    u2idx = {user: idx for idx, user in enumerate(idx2u)}
    with (target / "idx2u.pickle").open("wb") as handle:
        pickle.dump(idx2u, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with (target / "u2idx.pickle").open("wb") as handle:
        pickle.dump(u2idx, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return {
        "status": "ok",
        "dataset_name": target.name,
        "path": str(target),
        "cascades": len(cascade_rows),
        "users": len(users),
        "edges": len(edge_rows),
    }


def convert_forest_cascades_to_minds(path: Path, max_cascades: int) -> Tuple[List[str], set[str]]:
    rows: List[str] = []
    users: set[str] = set()
    if not path.is_file():
        return rows, users
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            chunks = [chunk.strip() for chunk in line.strip().split() if chunk.strip()]
            pairs = []
            for chunk in chunks:
                if "," not in chunk:
                    continue
                user, timestamp = chunk.rsplit(",", 1)
                if not user:
                    continue
                try:
                    ts = float(timestamp)
                except ValueError:
                    continue
                pairs.append((user, ts))
                users.add(user)
            if len(pairs) < 2:
                continue
            rows.append(",".join(f"{user} {timestamp:g}" for user, timestamp in pairs) + "\n")
            if max_cascades > 0 and len(rows) >= max_cascades:
                break
    return rows, users


def convert_edges_to_minds(path: Path, users: set[str]) -> List[str]:
    rows = []
    if not path.is_file():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            if "," in raw:
                src, dst = [part.strip() for part in raw.split(",", 1)]
            else:
                parts = raw.split()
                if len(parts) < 2:
                    continue
                src, dst = parts[0], parts[1]
            if src in users and dst in users:
                rows.append(f"{src} {dst}\n")
    if not rows and len(users) >= 2:
        user_list = sorted(users)[:2]
        rows.append(f"{user_list[0]} {user_list[1]}\n")
    return rows


def forest_data_dir(data_root: Path, dataset: str) -> Path:
    return data_root / dataset


def run_minds(args, dataset: str, seed: int) -> Dict:
    minds_work = resolve_minds_work_dir(Path(args.minds_repo))
    if minds_work is None:
        return failure_row(
            "MINDS",
            dataset,
            "missing_external_repo",
            args.config_id,
            seed,
            f"MINDS source not found under {args.minds_repo}.",
            [],
            Path(args.minds_repo),
        )
    prepared = prepare_minds_forest_dataset(
        forest_data_dir(Path(args.forest_data_root), dataset),
        minds_work,
        dataset,
        args.max_minds_cascades,
    )
    if prepared.get("status") != "ok":
        return failure_row("MINDS", dataset, "missing_data", args.config_id, seed, prepared.get("note", ""), [], minds_work)
    cmd = [
        args.python,
        str(ADAPTERS_DIR / "minds_runner.py"),
        "--dataset_name",
        str(prepared["dataset_name"]),
        "--report_dataset",
        dataset,
        "--protocol_source",
        f"converted from FOREST {dataset} cascade.txt",
        "--epochs",
        str(args.minds_epochs),
        "--batch_size",
        str(args.minds_batch_size),
        "--emb_dim",
        str(args.minds_emb_dim),
        "--step_split",
        str(args.minds_step_split),
        "--device",
        args.device,
        "--reproduction_level",
        "frontier_reproduction_full_run",
        "--config_id",
        args.config_id,
        "--seed",
        str(seed),
    ]
    row = run_adapter(cmd, minds_work, args.timeout, "MINDS", dataset, args.config_id, seed)
    row["minds_staged_dataset"] = prepared
    return row


def run_forest(args, dataset: str, seed: int) -> Dict:
    forest_repo = Path(args.forest_repo)
    cmd = [
        args.python,
        str(ADAPTERS_DIR / "forest_runner.py"),
        "--data_name",
        dataset,
        "--data_root",
        str(Path(args.forest_data_root)),
        "--epochs",
        str(args.forest_epochs),
        "--batch_size",
        str(args.forest_batch_size),
        "--d_model",
        str(args.forest_d_model),
        "--max_train_batches",
        str(args.forest_max_train_batches),
        "--max_eval_batches",
        str(args.forest_max_eval_batches),
        "--rl_epochs",
        str(args.forest_rl_epochs),
        "--rl_max_batches",
        str(args.forest_rl_max_batches),
        "--rl_rollout_len",
        str(args.forest_rl_rollout_len),
        "--device",
        args.device,
        "--reproduction_level",
        "frontier_reproduction_full_run",
        "--config_id",
        args.config_id,
        "--seed",
        str(seed),
    ]
    return run_adapter(cmd, forest_repo, args.timeout, "FOREST", dataset, args.config_id, seed)


def run_casft(args, dataset: str, seed: int) -> Dict:
    export_dir = Path(args.out).with_suffix("") / "casft_exports" / dataset / f"seed_{seed}"
    cmd = [
        args.python,
        str(ADAPTERS_DIR / "casft_runner.py"),
        "--casft_dir",
        str(Path(args.casft_repo)),
        "--data_dir",
        str(forest_data_dir(Path(args.forest_data_root), dataset)),
        "--export_dir",
        str(export_dir),
        "--casft_dataset",
        args.casft_dataset if args.casft_dataset != "auto" else f"kt2_{dataset}_casft",
        "--max_events",
        str(args.casft_max_events),
        "--max_epoch",
        str(args.casft_max_epoch),
        "--observation_time",
        str(args.casft_observation_time),
        "--prediction_time",
        str(args.casft_prediction_time),
        "--interval_num",
        str(args.casft_interval_num),
        "--timesteps",
        str(args.casft_timesteps),
        "--timeout",
        str(args.timeout),
        "--obs_ratio",
        str(args.obs_ratio),
        "--seed",
        str(seed),
        "--reproduction_level",
        "frontier_reproduction_full_run",
        "--config_id",
        args.config_id,
        "--enable_cogdl_shim",
        "--run_external",
    ]
    return run_adapter(cmd, ROOT, args.timeout + 30, "CasFT", dataset, args.config_id, seed)


def run_matrix(args, started: Optional[float] = None) -> Dict:
    rows = load_existing_rows(Path(args.out)) if args.resume else []
    failures = failure_records(rows)
    datasets = parse_csv(args.datasets)
    seeds = [int(seed) for seed in parse_csv(args.seeds)]
    run_map = {
        "MINDS": run_minds,
        "FOREST": run_forest,
        "CasFT": run_casft,
    }
    existing_ok = {baseline_row_key(row) for row in rows if row.get("status") == "ok"}
    for dataset in datasets:
        for seed in seeds:
            for model in parse_csv(args.models):
                runner = run_map.get(model)
                if runner is None:
                    continue
                key = (dataset, model, seed, args.config_id)
                if key in existing_ok:
                    print(
                        f"[same-protocol-baselines] skip existing dataset={dataset} "
                        f"model={model} seed={seed}",
                        flush=True,
                    )
                    continue
                row = runner(args, dataset, seed)
                rows = upsert_row(rows, row)
                failures = failure_records(rows)
                if row.get("status") == "ok":
                    existing_ok.add(baseline_row_key(row))
                write_payload(args, rows, failures, started=started)
    return build_payload(args, rows, failures, started=started)


def build_payload(args, rows: List[Dict], failures: List[Dict], started: Optional[float]) -> Dict:
    requested_models = parse_csv(args.models)
    requested_datasets = parse_csv(args.datasets)
    requested_seeds = [int(seed) for seed in parse_csv(args.seeds)]
    expected_keys = {
        (dataset, model, seed, str(args.config_id))
        for dataset in requested_datasets
        for model in requested_models
        for seed in requested_seeds
    }
    completed_keys = {
        baseline_row_key(row)
        for row in rows
        if row.get("status") == "ok"
        and row.get("reproduction_level") == "frontier_reproduction_full_run"
    }
    missing_keys = sorted(expected_keys - completed_keys)
    ok_models_by_dataset = {
        dataset: sorted(
            {
                row.get("model")
                for row in rows
                if row.get("dataset") == dataset
                and row.get("status") == "ok"
                and row.get("reproduction_level") == "frontier_reproduction_full_run"
            }
        )
        for dataset in requested_datasets
    }
    completed = {
        dataset: models
        for dataset, models in ok_models_by_dataset.items()
        if all(
            (dataset, model, seed, str(args.config_id)) in completed_keys
            for model in requested_models
            for seed in requested_seeds
        )
    }
    all_requested_complete = not missing_keys
    payload = {
        "schema": "cogguard.kt2.same_protocol_full_run_baselines.v1",
        "status": "ok" if all_requested_complete and not failures else "partial",
        "boundary": "Rows are real adapter runs only; failed rows remain failed and are not completion evidence.",
        "datasets": requested_datasets,
        "seeds": requested_seeds,
        "models": requested_models,
        "config_id": args.config_id,
        "ok_models_by_dataset": ok_models_by_dataset,
        "completed_datasets": completed,
        "failures": failures,
        "protocol_audit": {
            "passed": all_requested_complete and not failures,
            "requested_count": len(expected_keys),
            "row_count": len(rows),
            "fair_ok_count": len(completed_keys),
            "missing_or_nonfair_count": len(missing_keys),
            "missing_or_nonfair_rows": [
                {
                    "dataset": dataset,
                    "model": model,
                    "seed": seed,
                    "config_id": config_id,
                }
                for dataset, model, seed, config_id in missing_keys[:30]
            ],
        },
        "rows": rows,
    }
    if started is not None:
        payload["elapsed_s"] = round(time.time() - started, 1)
    return payload


def write_payload(args, rows: List[Dict], failures: List[Dict], started: Optional[float]) -> Dict:
    payload = build_payload(args, rows, failures, started)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", default="douban")
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--models", default="MINDS,FOREST,CasFT")
    parser.add_argument("--forest_data_root", default=str(DEFAULT_FOREST_DATA))
    parser.add_argument("--minds_repo", default=str(DEFAULT_MINDS_REPO))
    parser.add_argument("--forest_repo", default=str(DEFAULT_FOREST_REPO))
    parser.add_argument("--casft_repo", default=str(DEFAULT_CASFT_REPO))
    parser.add_argument("--out", default=str(BENCHMARK_DIR / "same_protocol_full_run_baselines.json"))
    parser.add_argument("--config_id", default="full-run-preflight")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--timeout", type=int, default=86400)
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--max_minds_cascades", type=int, default=300)
    parser.add_argument("--minds_epochs", type=int, default=200)
    parser.add_argument("--minds_batch_size", type=int, default=32)
    parser.add_argument("--minds_emb_dim", type=int, default=32)
    parser.add_argument("--minds_step_split", type=int, default=4)
    parser.add_argument("--forest_epochs", type=int, default=200)
    parser.add_argument("--forest_batch_size", type=int, default=16)
    parser.add_argument("--forest_d_model", type=int, default=32)
    parser.add_argument("--forest_max_train_batches", type=int, default=2)
    parser.add_argument("--forest_max_eval_batches", type=int, default=2)
    parser.add_argument("--forest_rl_epochs", type=int, default=200)
    parser.add_argument("--forest_rl_max_batches", type=int, default=0)
    parser.add_argument("--forest_rl_rollout_len", type=int, default=5)
    parser.add_argument("--casft_dataset", default="auto")
    parser.add_argument("--casft_max_events", type=int, default=20000)
    parser.add_argument("--casft_max_epoch", type=int, default=200)
    parser.add_argument("--casft_observation_time", type=int, default=86400)
    parser.add_argument("--casft_prediction_time", type=int, default=1296000)
    parser.add_argument("--casft_interval_num", type=int, default=12)
    parser.add_argument("--casft_timesteps", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    started = time.time()
    payload = run_matrix(args, started=started)
    write_payload(args, payload["rows"], payload["failures"], started)
    print(json.dumps({"status": payload["status"], "rows": len(payload["rows"]), "out": args.out}))


if __name__ == "__main__":
    main()
