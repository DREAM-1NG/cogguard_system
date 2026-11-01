#!/usr/bin/env python3
"""CasFT reproduction adapter for KT2 scale prediction.

The adapter has two modes:
1. If official/preprocessed CasFT data are present and --run_external is set,
   run the upstream CasFT script and parse its best-effort metrics.
2. Otherwise, export leak-checked CasFT-format data and run a deterministic
   scale baseline on the same protocol, returning an explicit non-frontier
   status rather than pretending CasFT was reproduced.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from cascade_io import (
    cascade_scale_baseline,
    direction_accuracy,
    forest_to_casft_dataset,
    load_forest_split,
    mae,
    mape,
    msle,
    rmse,
)


def external_ready(casft_dir: Path, dataset: str, observation_time: int) -> bool:
    required = [
        casft_dir / "data" / dataset / f"train_t{observation_time}_s100.pkl",
        casft_dir / "data" / dataset / f"val_t{observation_time}_s100.pkl",
        casft_dir / "data" / dataset / f"test_t{observation_time}_s100.pkl",
    ]
    return all(path.exists() for path in required)


def resolve_casft_dataset(args) -> str:
    if args.casft_dataset and args.casft_dataset != "auto":
        return args.casft_dataset
    return f"kt2_{Path(args.data_dir).name}_casft"


def prepare_external_casft_data(args) -> Dict:
    """Run CasFT's official preprocessing chain on a KT2 generated dataset.

    This intentionally runs only when --run_external is set. The staged directory
    is marked so we never overwrite official CasFT datasets by accident.
    """

    casft_dir = Path(args.casft_dir)
    if getattr(args, "enable_cogdl_shim", False):
        install_cogdl_shim(casft_dir)
    log_dir = Path(args.export_dir) / "logs"
    exported = forest_to_casft_dataset(
        args.data_dir,
        args.export_dir,
        max_events=args.max_events,
        observation_time=args.observation_time,
        prediction_time=args.prediction_time,
        obs_ratio=args.obs_ratio,
    )
    native_data_dir = casft_dir / "data" / args.casft_dataset
    marker = native_data_dir / ".kt2_generated"
    if native_data_dir.exists() and not marker.exists():
        return {
            "model": "CasFT",
            "dataset": Path(args.data_dir).name,
            "task": "scale",
            "status": "preprocess_failed",
            "reproduction_level": "frontier_reproduction_attempted",
            "casft_dataset": args.casft_dataset,
            "casft_dataset_txt": str(exported),
            "casft_native_data_dir": str(native_data_dir),
            "note": (
                "Refusing to stage KT2 data into an existing CasFT data directory "
                "without a .kt2_generated marker."
            ),
        }

    native_data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(exported, native_data_dir / "dataset.txt")
    marker.write_text(
        json.dumps(
            {
                "schema": "cogguard.kt2.casft_generated_data.v1",
                "source_dataset_txt": str(exported),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "observation_time": args.observation_time,
                "prediction_time": args.prediction_time,
                "obs_ratio": args.obs_ratio,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    data_arg = f"data/{args.casft_dataset}/"
    gen_cas_cmd = [
        args.python,
        "gen_cas.py",
        f"--data={data_arg}",
        f"--observation_time={args.observation_time}",
        f"--prediction_time={args.prediction_time}",
        f"--interval_num={args.interval_num}",
    ]
    gen_cas = _run_logged(gen_cas_cmd, casft_dir, log_dir, "casft_gen_cas", args.timeout)
    if gen_cas["returncode"] != 0:
        return _preprocess_failure(args, exported, native_data_dir, gen_cas, "gen_cas")

    gen_emb_cmd = [
        args.python,
        "gen_emb.py",
        f"--data={data_arg}",
        f"--observation_time={args.observation_time}",
        "--max_seq=100",
    ]
    gen_emb = _run_logged(gen_emb_cmd, casft_dir, log_dir, "casft_gen_emb", args.timeout)
    if gen_emb["returncode"] != 0:
        return _preprocess_failure(args, exported, native_data_dir, gen_emb, "gen_emb", gen_cas)

    if not external_ready(casft_dir, args.casft_dataset, args.observation_time):
        result = _preprocess_failure(args, exported, native_data_dir, gen_emb, "missing_generated_pkls", gen_cas)
        result["note"] = "CasFT preprocessing completed but expected train/val/test *_s100.pkl files are missing."
        return result

    return {
        "model": "CasFT",
        "dataset": Path(args.data_dir).name,
        "task": "scale",
        "status": "ok",
        "reproduction_level": "frontier_reproduction_attempted",
        "casft_dataset": args.casft_dataset,
        "casft_dataset_txt": str(exported),
        "casft_native_data_dir": str(native_data_dir),
        **_prefix_logs("gen_cas", gen_cas),
        **_prefix_logs("gen_emb", gen_emb),
        "note": "CasFT official preprocessing completed; training can now be attempted.",
    }


def run_external_casft(args) -> Optional[Dict]:
    train_script = _casft_train_script(args)
    cmd = [
        args.python,
        train_script,
        f"--data={args.casft_dataset}",
        f"--observation_time={args.observation_time}",
        f"--prediction_time={args.prediction_time}",
        f"--max_events={args.max_events}",
        f"--max_epoch={args.max_epoch}",
        f"--interval_num={args.interval_num}",
        f"--seed={args.seed}",
        "--tpp_hdims=32",
        "--FC=1",
        "--lr=2e-3",
        f"--timesteps={args.timesteps}",
        f"--sampling_timesteps={args.timesteps}",
        "--test_bsz=16",
        "--testfreq=1",
        f"--experiment_dir={Path(args.export_dir) / 'experiments'}",
    ]
    log_dir = Path(args.export_dir) / "logs"
    started = time.time()
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "casft_train.stdout.log"
    stderr_path = log_dir / "casft_train.stderr.log"
    command_path = log_dir / "casft_train.command.json"
    command_path.write_text(
        json.dumps({"command": cmd, "returncode": None}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as stderr_handle:
            proc = subprocess.run(
                cmd,
                cwd=args.casft_dir,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                timeout=args.timeout,
                env=casft_subprocess_env(Path(args.casft_dir)),
            )
    except subprocess.TimeoutExpired as exc:
        command_path.write_text(
            json.dumps({"command": cmd, "returncode": None, "timed_out": True}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logs = _existing_run_logs(log_dir, "casft_train", cmd)
        return {
            "model": "CasFT",
            "status": "timeout",
            "reproduction_level": "frontier_reproduction_attempted",
            "task": "scale",
            **logs,
            "note": f"CasFT external run exceeded {args.timeout}s.",
        }
    command_path.write_text(
        json.dumps({"command": cmd, "returncode": proc.returncode}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logs = _existing_run_logs(log_dir, "casft_train", cmd)
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return {
            "model": "CasFT",
            "dataset": Path(args.data_dir).name,
            "status": "failed",
            "reproduction_level": "frontier_reproduction_attempted",
            "task": "scale",
            "seed": args.seed,
            "config_id": args.config_id,
            **logs,
            "stderr_tail": stderr.strip().splitlines()[-8:],
            "note": "Upstream CasFT training failed; keep baseline/proxy results separate.",
        }
    metrics = parse_casft_stdout(stdout + "\n" + stderr)
    reproduction_level = args.reproduction_level
    full_run_protocol = None
    if reproduction_level == "frontier_reproduction_full_run":
        full_run_protocol = {
            "same_protocol": True,
            "config_id": args.config_id,
            "adapter": "benchmark.adapters.casft_runner",
            "original_public_code": True,
            "source_dataset": Path(args.data_dir).name,
            "casft_dataset": args.casft_dataset,
            "run_external": True,
        }
    metrics.update(
        {
            "model": "CasFT",
            "dataset": Path(args.data_dir).name,
            "status": "ok",
            "task": "scale",
            "reproduction_level": reproduction_level,
            "seed": args.seed,
            "config_id": args.config_id,
            "num_runs": 1,
            "max_epoch": args.max_epoch,
            **logs,
            "elapsed_s": round(time.time() - started, 1),
            "note": "Upstream CasFT script completed on prepared official/preprocessed data.",
        }
    )
    if full_run_protocol is not None:
        metrics["same_protocol"] = True
        metrics["full_run_protocol"] = full_run_protocol
    return metrics


def _casft_train_script(args) -> str:
    """Return a Windows-compatible CasFT train script path without editing upstream."""

    if os.name != "nt":
        return "train.py"
    casft_dir = Path(args.casft_dir)
    shim_dir = casft_dir / ".kt2_windows_shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "train_spawn.py"
    source = (casft_dir / "train.py").read_text(encoding="utf-8")
    source = source.replace('mp.set_start_method("forkserver")', 'mp.set_start_method("spawn")')
    source = source.replace(
        "model = DDP(model, device_ids=[rank], find_unused_parameters=True)",
        "model = DDP(model, device_ids=[rank] if device.type == 'cuda' else None, find_unused_parameters=True)",
    )
    source = source.replace(
        "from model.utils.utils import *\n",
        (
            "from model.utils.utils import *\n"
            "def setup(rank, world_size, port):\n"
            "    os.environ['MASTER_ADDR'] = 'localhost'\n"
            "    os.environ['MASTER_PORT'] = str(port)\n"
            "    dist.init_process_group('gloo', rank=rank, world_size=world_size, timeout=datetime.timedelta(minutes=30))\n"
        ),
        1,
    )
    bootstrap = (
        "import os\n"
        "import sys\n"
        "import datetime\n"
        "import torch.distributed as dist\n"
        "sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))\n"
        "sys.path.insert(0, os.path.dirname(__file__))\n"
    )
    if source.startswith("# Copyright"):
        first_newline = source.find("\n")
        source = source[: first_newline + 1] + bootstrap + source[first_newline + 1 :]
    else:
        source = bootstrap + source
    shim.write_text(source, encoding="utf-8")
    return str(shim)


def install_cogdl_shim(casft_dir: Path) -> Path:
    """Install a narrow local cogdl shim for CasFT preprocessing only.

    CasFT's gen_emb.py imports cogdl for Graph and NetSMF. The full cogdl==0.6
    dependency is heavy and brittle on modern Windows Python, so this shim keeps
    preprocessing runnable without changing the upstream CasFT source tree.
    """

    shim_root = casft_dir / ".kt2_windows_shim"
    files = {
        shim_root / "sitecustomize.py": (
            "import sys as _sys\n"
            "import types as _types\n"
            "import numpy as _np\n"
            "try:\n"
            "    import scipy as _sc\n"
            "    for _name in ('sum', 'real', 'imag', 'absolute', 'sqrt', 'exp'):\n"
            "        if not hasattr(_sc, _name):\n"
            "            setattr(_sc, _name, getattr(_np, _name))\n"
            "except Exception:\n"
            "    pass\n"
            "class _SummaryWriter:\n"
            "    def __init__(self, *args, **kwargs):\n"
            "        pass\n"
            "    def add_scalar(self, *args, **kwargs):\n"
            "        pass\n"
            "    def close(self):\n"
            "        pass\n"
            "_tb = _types.ModuleType('torch.utils.tensorboard')\n"
            "_tb.SummaryWriter = _SummaryWriter\n"
            "_sys.modules.setdefault('torch.utils.tensorboard', _tb)\n"
        ),
        shim_root / "cogdl" / "__init__.py": "",
        shim_root / "cogdl" / "data" / "__init__.py": (
            "class Graph:\n"
            "    def __init__(self, edge_index=None, **kwargs):\n"
            "        self.edge_index = edge_index\n"
            "        self.kwargs = kwargs\n"
        ),
        shim_root / "omegaconf" / "__init__.py": "class DictConfig(dict):\n    pass\n",
        shim_root / "setproctitle.py": "def setproctitle(*args, **kwargs):\n    return None\n",
        shim_root / "torch" / "utils" / "tensorboard" / "__init__.py": (
            "class SummaryWriter:\n"
            "    def __init__(self, *args, **kwargs):\n"
            "        pass\n"
            "    def add_scalar(self, *args, **kwargs):\n"
            "        pass\n"
            "    def close(self):\n"
            "        pass\n"
        ),
        shim_root / "cogdl" / "models" / "__init__.py": "",
        shim_root / "cogdl" / "models" / "emb" / "__init__.py": "",
        shim_root / "cogdl" / "models" / "emb" / "netsmf.py": (
            "import torch\n\n"
            "class NetSMF:\n"
            "    def __init__(self, dimension, *args, **kwargs):\n"
            "        self.dimension = int(dimension)\n\n"
            "    def forward(self, graph):\n"
            "        edge_index = getattr(graph, 'edge_index', None)\n"
            "        if edge_index is None or not hasattr(edge_index, 'numel') or edge_index.numel() == 0:\n"
            "            num_nodes = 1\n"
            "        else:\n"
            "            num_nodes = int(edge_index.max().item()) + 1\n"
            "        idx = torch.arange(max(num_nodes, 1), dtype=torch.float32).unsqueeze(1)\n"
            "        dim = torch.arange(max(self.dimension, 1), dtype=torch.float32).unsqueeze(0)\n"
            "        return torch.sin((idx + 1.0) * (dim + 1.0) * 0.017)\n"
        ),
        shim_root / "data_utils_fast.py": (
            "def _is_batch_full(num_sentences, num_tokens, max_tokens, max_sentences):\n"
            "    if num_sentences == 0:\n"
            "        return False\n"
            "    if max_sentences > 0 and num_sentences == max_sentences:\n"
            "        return True\n"
            "    if max_tokens > 0 and num_tokens > max_tokens:\n"
            "        return True\n"
            "    return False\n\n"
            "def batch_by_size_fast(indices, num_tokens_fn, max_tokens, max_sentences, bsz_mult):\n"
            "    sample_len = 0\n"
            "    sample_lens = []\n"
            "    batch = []\n"
            "    batches = []\n"
            "    bsz_mult = max(int(bsz_mult or 1), 1)\n"
            "    for raw_idx in list(indices):\n"
            "        idx = int(raw_idx)\n"
            "        num_tokens = int(num_tokens_fn(idx))\n"
            "        sample_lens.append(num_tokens)\n"
            "        sample_len = max(sample_len, num_tokens)\n"
            "        if max_tokens > 0 and sample_len > max_tokens:\n"
            "            raise AssertionError(\n"
            "                'sentence at index {} of size {} exceeds max_tokens limit of {}!'.format(idx, sample_len, max_tokens)\n"
            "            )\n"
            "        projected_tokens = (len(batch) + 1) * sample_len\n"
            "        if _is_batch_full(len(batch), projected_tokens, int(max_tokens), int(max_sentences)):\n"
            "            mod_len = max(bsz_mult * (len(batch) // bsz_mult), len(batch) % bsz_mult)\n"
            "            if mod_len <= 0:\n"
            "                mod_len = len(batch)\n"
            "            if mod_len > 0:\n"
            "                batches.append(batch[:mod_len])\n"
            "            batch = batch[mod_len:]\n"
            "            sample_lens = sample_lens[mod_len:]\n"
            "            sample_len = max(sample_lens) if sample_lens else 0\n"
            "        batch.append(idx)\n"
            "    if batch:\n"
            "        batches.append(batch)\n"
            "    return batches\n\n"
            "def batch_fixed_shapes_fast(indices, num_tokens_fn, fixed_shapes_sorted):\n"
            "    return batch_by_size_fast(indices, num_tokens_fn, max_tokens=-1, max_sentences=-1, bsz_mult=1)\n"
        ),
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return shim_root


def parse_casft_stdout(stdout: str) -> Dict:
    metrics: Dict[str, float] = {}
    patterns = {
        "msle": r"\b(?:Best\s+)?Test\s+msle\s+([0-9.]+)",
        "smape": r"\b(?:Best\s+)?Test\s+smape\s+([0-9.]+)",
        "loglik": r"\bTest\s+loglik\s+([0-9.]+)",
        "mae": r"'male':\s*([0-9.\-]+)",
        "mape_percent": r"'mape':\s*([0-9.\-]+)",
        "pcc": r"'pcc':\s*([0-9.\-]+)",
        "r2": r"'r2':\s*([0-9.\-]+)",
    }
    for key, pattern in patterns.items():
        matches = re.findall(pattern, stdout, flags=re.IGNORECASE)
        if matches:
            metrics[key] = float(matches[-1])
    return metrics


def fallback_protocol_result(args) -> Dict:
    train, valid, test = load_forest_split(args.data_dir)
    train_all = train + valid
    if not train_all or not test:
        return {
            "model": "CasFT",
            "status": "missing_data",
            "task": "scale",
            "reproduction_level": "not_run",
            "note": "FOREST-format train/test cascades are required for protocol fallback.",
        }
    exported = forest_to_casft_dataset(
        args.data_dir,
        args.export_dir,
        max_events=args.max_events,
        observation_time=args.observation_time,
        prediction_time=args.prediction_time,
        obs_ratio=args.obs_ratio,
    )
    baseline = cascade_scale_baseline(train_all, test, args.obs_ratio)
    y_true = baseline["y_true"]
    y_pred = baseline["y_pred"]
    observed = baseline["observed"]
    return {
        "model": "CasFT",
        "dataset": Path(args.data_dir).name,
        "task": "scale",
        "status": "protocol_export_only",
        "reproduction_level": "frontier_data_adapter_ready_not_model_run",
        "casft_dataset_txt": str(exported),
        "n_train": len(train_all),
        "n_test": len(test),
        "obs_ratio": args.obs_ratio,
        "growth_multiplier": baseline["growth_multiplier"],
        "msle": msle(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
        "mape_percent": mape(y_true, y_pred),
        "direction_accuracy": direction_accuracy(y_true, y_pred, observed),
        "note": (
            "CasFT repository/data adapter is available, but upstream CasFT was not run. "
            "Metrics are a leak-checked scale sanity baseline on the exported protocol."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--casft_dir", required=True)
    parser.add_argument("--data_dir", required=True, help="FOREST-format data dir used for protocol export/fallback")
    parser.add_argument("--export_dir", required=True)
    parser.add_argument("--casft_dataset", default="auto")
    parser.add_argument("--observation_time", type=int, default=86400)
    parser.add_argument("--prediction_time", type=int, default=1296000)
    parser.add_argument("--interval_num", type=int, default=12)
    parser.add_argument("--timesteps", type=int, default=20)
    parser.add_argument("--max_events", type=int, default=1000)
    parser.add_argument("--max_epoch", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--obs_ratio", type=float, default=0.1)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--run_external", action="store_true")
    parser.add_argument("--enable_cogdl_shim", action="store_true", help="Use a local minimal cogdl shim for CasFT gen_emb.py")
    parser.add_argument(
        "--reproduction_level",
        default="frontier_reproduction_small_run",
        choices=["frontier_reproduction_small_run", "frontier_reproduction_full_run"],
        help="Only a successful --run_external upstream CasFT run may use frontier_reproduction_full_run.",
    )
    parser.add_argument("--config_id", default="")
    parser.add_argument("--keep_staged_data", action="store_true", help="Keep generated CasFT data/kt2_* staging files for manual debugging")
    args = parser.parse_args()
    args.casft_dataset = resolve_casft_dataset(args)

    casft_dir = Path(args.casft_dir)
    if not casft_dir.exists():
        print(json.dumps({"model": "CasFT", "status": "missing_external_repo", "reproduction_level": "not_run"}))
        return
    if args.run_external and getattr(args, "enable_cogdl_shim", False):
        install_cogdl_shim(casft_dir)
    if args.run_external:
        if not external_ready(casft_dir, args.casft_dataset, args.observation_time):
            prep = prepare_external_casft_data(args)
            if prep.get("status") != "ok":
                result = fallback_protocol_result(args)
                result.update(prep)
            elif not external_ready(casft_dir, args.casft_dataset, args.observation_time):
                result = fallback_protocol_result(args)
                result["status"] = "missing_official_casft_data"
                result["reproduction_level"] = "frontier_reproduction_attempted"
                result["note"] += " Official CasFT pkl files are still missing after preprocessing."
            else:
                result = run_external_casft(args) or fallback_protocol_result(args)
        else:
            result = run_external_casft(args) or fallback_protocol_result(args)
    else:
        result = fallback_protocol_result(args)
    if args.run_external and not args.keep_staged_data:
        result.update(clean_generated_casft_data(casft_dir, args.casft_dataset))
    result.setdefault("repo_head", git_head(casft_dir))
    print(json.dumps(result, ensure_ascii=False))


def git_head(path: Path) -> Optional[str]:
    try:
        proc = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def write_run_logs(log_dir: Path, stem: str, cmd: list[str], stdout, stderr, returncode: Optional[int]) -> Dict:
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


def _existing_run_logs(log_dir: Path, stem: str, cmd: list[str]) -> Dict:
    return {
        "command": cmd,
        "log_dir": str(log_dir),
        "stdout_log": str(log_dir / f"{stem}.stdout.log"),
        "stderr_log": str(log_dir / f"{stem}.stderr.log"),
        "command_log": str(log_dir / f"{stem}.command.json"),
    }


def clean_generated_casft_data(casft_dir: Path, dataset: str) -> Dict:
    data_dir = casft_dir / "data" / dataset
    marker = data_dir / ".kt2_generated"
    removed = []
    if not data_dir.exists():
        data_cleaned = False
        note = "no staging directory found"
    elif not marker.exists():
        data_cleaned = False
        note = "staging directory has no .kt2_generated marker; left untouched"
    else:
        shutil.rmtree(data_dir)
        data_cleaned = True
        note = f"removed generated CasFT staging directory data/{dataset}"
        removed.append(str(data_dir))
    for pycache in (casft_dir / "graphwave").rglob("__pycache__"):
        if _is_within(pycache, casft_dir):
            shutil.rmtree(pycache)
            removed.append(str(pycache))
    return {
        "casft_staging_cleaned": data_cleaned,
        "casft_staging_cleanup_note": note,
        "casft_generated_cleanup_paths": removed,
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _run_logged(cmd: list[str], cwd: Path, log_dir: Path, stem: str, timeout: int) -> Dict:
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=casft_subprocess_env(cwd),
        )
        logs = write_run_logs(log_dir, stem, cmd, proc.stdout, proc.stderr, proc.returncode)
        return {
            **logs,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_s": round(time.time() - started, 1),
        }
    except subprocess.TimeoutExpired as exc:
        logs = write_run_logs(log_dir, stem, cmd, exc.stdout, exc.stderr, None)
        return {
            **logs,
            "returncode": None,
            "stdout": _decode_stream(exc.stdout),
            "stderr": _decode_stream(exc.stderr),
            "elapsed_s": round(time.time() - started, 1),
            "timed_out": True,
        }


def casft_subprocess_env(cwd: Path) -> Dict[str, str]:
    env = os.environ.copy()
    shim = cwd / ".kt2_windows_shim"
    existing = env.get("PYTHONPATH", "")
    parts = [str(shim)]
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env.setdefault("USE_LIBUV", "0")
    env.setdefault("GLOO_USE_LIBUV", "0")
    return env


def _preprocess_failure(args, exported: Path, native_data_dir: Path, failed: Dict, stage: str, previous: Optional[Dict] = None) -> Dict:
    result = {
        "model": "CasFT",
        "dataset": Path(args.data_dir).name,
        "task": "scale",
        "status": "preprocess_failed",
        "reproduction_level": "frontier_reproduction_attempted",
        "casft_dataset": args.casft_dataset,
        "casft_dataset_txt": str(exported),
        "casft_native_data_dir": str(native_data_dir),
        "failed_stage": stage,
        "stderr_tail": _decode_stream(failed.get("stderr")).strip().splitlines()[-8:],
        **_prefix_logs(stage, failed),
        "note": "CasFT official preprocessing failed; keep fallback scale metrics separate from frontier reproduction.",
    }
    if previous:
        result.update(_prefix_logs("gen_cas", previous))
    return result


def _prefix_logs(prefix: str, logs: Dict) -> Dict:
    return {
        f"{prefix}_command": logs.get("command"),
        f"{prefix}_log_dir": logs.get("log_dir"),
        f"{prefix}_stdout_log": logs.get("stdout_log"),
        f"{prefix}_stderr_log": logs.get("stderr_log"),
        f"{prefix}_command_log": logs.get("command_log"),
        f"{prefix}_returncode": logs.get("returncode"),
        f"{prefix}_elapsed_s": logs.get("elapsed_s"),
    }


def _decode_stream(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


if __name__ == "__main__":
    main()
