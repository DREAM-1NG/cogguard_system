"""Focused iohunter implementation for coordination reproduction."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import pickle
import re
import shlex
import shutil
import subprocess
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import networkx as nx
import numpy as np
import pandas as pd
from networkx.algorithms.community import greedy_modularity_communities, louvain_communities
from networkx.algorithms.community.quality import modularity
from app.core.coordination_baseline.characterization import CharacterizationConfig, characterize_detect_output
from app.core.coordination_baseline.deep_graph import (
    DEPRECATED_DISCOVER_ENCODERS,
    DeepGraphDiscoverConfig,
    DeepGraphDiscoverResult,
    STABLE_DISCOVER_ENCODER,
    run_deep_graph_discover,
)

from app.core.coordination_baseline.reproduction_common import (
    DEFAULT_RELATIONS,
    IOHUNTER_BASELINE_SCRIPTS,
    IOHUNTER_CANONICAL_RELATIONS,
    IOHUNTER_CROSS_COUNTRY_SCRIPT,
    IOHUNTER_DATASETS,
    IOHUNTER_LOG_METRIC_RE,
    IOHUNTER_PRIMARY_SCRIPT,
    IOHUNTER_REPO_URL,
    IOHUNTER_REQUIRED_PACKAGES,
    IOHUNTER_ZENODO_DATA_SIZE,
    IOHUNTER_ZENODO_DATA_URL,
    read_event_table,
    write_iohunter_event_table,
    write_metric_exports,
)
from app.core.coordination_baseline.reproduction_graphs import (
    build_unmasking_similarity_graphs,
    fuse_similarity_graphs,
)
from app.core.coordination_baseline.reproduction_discover import (
    run_dyna_colm_gnn_ablations,
    run_lightweight_llm_baselines,
    run_unmasking_reproduction,
)

def _iohunter_repo_dir(workspace: Path) -> Path:
    return workspace / "SocGFM"


def _iohunter_src_dir(workspace: Path) -> Path:
    return _iohunter_repo_dir(workspace) / "src"


def _iohunter_workspace_data_root(workspace: Path) -> Path:
    return workspace / "data" / "processed"


def _iohunter_official_data_root(workspace: Path) -> Path:
    return _iohunter_repo_dir(workspace) / "data" / "processed"


def _iohunter_effective_data_root(workspace: Path) -> Path:
    official_root = _iohunter_official_data_root(workspace)
    if official_root.exists():
        return official_root
    return _iohunter_workspace_data_root(workspace)


def ensure_iohunter_official_data_layout(workspace: Path) -> dict[str, object]:
    """Expose downloaded Zenodo data at the path expected by official IOHunter scripts."""
    source = _iohunter_workspace_data_root(workspace)
    target = _iohunter_official_data_root(workspace)
    actions: list[str] = []
    if target.exists():
        return {
            "source": str(source),
            "target": str(target),
            "ready": True,
            "actions": ["official_data_layout_exists"],
        }
    if not source.exists():
        return {
            "source": str(source),
            "target": str(target),
            "ready": False,
            "actions": ["workspace_data_missing"],
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(source, target, target_is_directory=True)
        actions.append("created_directory_symlink")
    except (NotImplementedError, OSError) as exc:
        actions.append(f"directory_symlink_failed:{type(exc).__name__}:{exc}")
        if os.name == "nt":
            process = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                text=True,
                capture_output=True,
                check=False,
            )
            if process.returncode == 0:
                actions.append("created_windows_junction")
            else:
                stderr = process.stderr.strip() or process.stdout.strip()
                actions.append(f"windows_junction_failed:{process.returncode}:{stderr}")
    return {
        "source": str(source),
        "target": str(target),
        "ready": target.exists(),
        "actions": actions,
    }


def patch_iohunter_official_scripts(workspace: Path) -> dict[str, object]:
    """Apply small reproducibility patches to the local official IOHunter clone."""
    actions: list[str] = []
    node_pruning = _iohunter_script_path(workspace, "run_NodePruning.py")
    node2vec = _iohunter_script_path(workspace, "run_Node2Vec.py")

    if node_pruning.exists():
        text = node_pruning.read_text(encoding="utf-8")
        if "return interim_data_dir" in text:
            actions.append("nodepruning_return_already_present")
        else:
            old = "    save_metrics(val_logger, interim_data_dir, 'VAL')\n    save_metrics(test_logger, interim_data_dir, 'TEST')\n"
            new = old + "    return interim_data_dir\n"
            if old in text:
                node_pruning.write_text(text.replace(old, new, 1), encoding="utf-8")
                actions.append("nodepruning_return_added")
            else:
                actions.append("nodepruning_return_anchor_missing")
    else:
        actions.append("nodepruning_script_missing")

    if node2vec.exists():
        text = node2vec.read_text(encoding="utf-8")
        changed = False
        if "import sys\n" in text:
            actions.append("node2vec_sys_import_already_present")
        elif "import os\nimport torch" in text:
            text = text.replace("import os\nimport torch", "import os\nimport sys\nimport torch", 1)
            changed = True
            actions.append("node2vec_sys_import_added")
        else:
            actions.append("node2vec_sys_import_anchor_missing")

        if 'sys.platform.startswith("win")' in text:
            actions.append("node2vec_windows_loader_already_present")
        else:
            old = "        num_workers = 4\n        loader = model.loader(batch_size=128, shuffle=True, num_workers=num_workers)\n"
            new = (
                "        # Windows spawn cannot pickle PyG's Node2Vec sampler capsule; use a\n"
                "        # single-process loader there while preserving the official method.\n"
                '        num_workers = 0 if sys.platform.startswith("win") else 4\n'
                "        loader = model.loader(batch_size=128, shuffle=True, num_workers=num_workers)\n"
            )
            if old in text:
                text = text.replace(old, new, 1)
                changed = True
                actions.append("node2vec_windows_loader_added")
            else:
                actions.append("node2vec_loader_anchor_missing")

        if "return interim_data_dir" in text:
            actions.append("node2vec_return_already_present")
        else:
            old = "    save_metrics(val_logger, interim_data_dir, 'VAL')\n    save_metrics(test_logger, interim_data_dir, 'TEST')\n"
            new = old + "    return interim_data_dir\n"
            if old in text:
                text = text.replace(old, new, 1)
                changed = True
                actions.append("node2vec_return_added")
            else:
                actions.append("node2vec_return_anchor_missing")

        if changed:
            node2vec.write_text(text, encoding="utf-8")
    else:
        actions.append("node2vec_script_missing")

    return {
        "workspace": str(workspace),
        "actions": actions,
        "ready": not any(action.endswith("_missing") for action in actions),
    }


def _iohunter_script_path(workspace: Path, script_name: str) -> Path:
    repo_dir = _iohunter_repo_dir(workspace)
    candidates = (repo_dir / "src" / script_name, repo_dir / script_name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _quote_ps(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _iohunter_run_command(cwd: Path, script: Path, args: Sequence[str]) -> str:
    quoted_args = [str(item) if re.fullmatch(r"[A-Za-z0-9_.:/+-]+", str(item)) else _quote_ps(str(item)) for item in args]
    return " ".join(
        [
            "Set-Location",
            "-LiteralPath",
            _quote_ps(str(cwd)),
            ";",
            "python",
            _quote_ps(f".\\{script.name}"),
            *quoted_args,
        ]
    )


def _iohunter_shell_command(cwd: Path, script: Path, args: Sequence[str]) -> str:
    quoted_args = [shlex.quote(str(item)) for item in args]
    return " ".join(["cd", shlex.quote(str(cwd)), "&&", "python", shlex.quote(script.name), *quoted_args])


def build_iohunter_run_plan(
    workspace: Path,
    *,
    datasets: Sequence[str] = IOHUNTER_DATASETS,
    seeds: Sequence[int] = (42, 43, 44, 45, 46),
    gnns: Sequence[str] = ("sage",),
    learning_rates: Sequence[float] = (1e-2,),
    early: int = 30,
    splits: int = 5,
    device: str = "0",
    epochs: int | None = None,
    check: int | None = None,
    latent: int | None = None,
    embed_type: str | None = None,
    undersampling: Sequence[float | str | None] = (None,),
    include_primary: bool = True,
    include_official_baselines: bool = True,
    include_cross_country: bool = False,
) -> list[dict[str, object]]:
    """Build executable IOHunter commands with the correct official working directory."""
    src_dir = _iohunter_src_dir(workspace)
    plan: list[dict[str, object]] = []
    if include_primary:
        for dataset in datasets:
            for gnn in gnns:
                for learning_rate in learning_rates:
                    for seed in seeds:
                        for under in undersampling:
                            script = _iohunter_script_path(workspace, IOHUNTER_PRIMARY_SCRIPT)
                            args = [
                                "--dataset",
                                dataset,
                                "--lr",
                                f"{learning_rate:g}",
                                "--early",
                                str(early),
                                "--gnn",
                                gnn,
                                "--seed",
                                str(seed),
                                "--splits",
                                str(splits),
                                "--device",
                                device,
                            ]
                            if epochs is not None:
                                args.extend(["--epochs", str(epochs)])
                            if check is not None:
                                args.extend(["--check", str(check)])
                            if latent is not None:
                                args.extend(["--latent", str(latent)])
                            if embed_type is not None:
                                args.extend(["--embed_type", embed_type])
                            setting = "supervised" if under is None else "scarce_supervised"
                            if under is not None:
                                args.extend(["--under", str(under)])
                            command = _iohunter_run_command(src_dir, script, args)
                            shell_command = _iohunter_shell_command(src_dir, script, args)
                            plan.append(
                                {
                                    "family": "iohunter",
                                    "method": "MultiModalGNN_CrossAttention",
                                    "setting": setting,
                                    "dataset": dataset,
                                    "seed": seed,
                                    "gnn": gnn,
                                    "lr": learning_rate,
                                    "early": early,
                                    "splits": splits,
                                    "epochs": epochs,
                                    "check": check,
                                    "latent": latent,
                                    "embed_type": embed_type,
                                    "undersampling": under,
                                    "cwd": str(src_dir),
                                    "script": str(script),
                                    "args": args,
                                    "command": command,
                                    "shell_command": shell_command,
                                }
                            )
    if include_official_baselines:
        for script_name in IOHUNTER_BASELINE_SCRIPTS:
            method = script_name.removeprefix("run_").removesuffix(".py")
            script = _iohunter_script_path(workspace, script_name)
            for dataset in datasets:
                for seed in seeds:
                    args = ["--dataset", dataset, "--seed", str(seed), "--splits", str(splits)]
                    if script_name == "run_Node2Vec.py":
                        args.extend(["--lr", f"{learning_rates[0]:g}", "--early", str(early), "--device", device])
                        if epochs is not None:
                            args.extend(["--epochs", str(epochs)])
                        if check is not None:
                            args.extend(["--check", str(check)])
                        if latent is not None:
                            args.extend(["--latent", str(latent)])
                    command = _iohunter_run_command(src_dir, script, args)
                    shell_command = _iohunter_shell_command(src_dir, script, args)
                    plan.append(
                        {
                            "family": "iohunter_official_baseline",
                            "method": method,
                            "setting": "supervised",
                            "dataset": dataset,
                            "seed": seed,
                            "cwd": str(src_dir),
                            "script": str(script),
                            "args": args,
                            "command": command,
                            "shell_command": shell_command,
                        }
                    )
    if include_cross_country:
        script = _iohunter_script_path(workspace, IOHUNTER_CROSS_COUNTRY_SCRIPT)
        for dataset in datasets:
            for gnn in gnns:
                for learning_rate in learning_rates:
                    for seed in seeds:
                        for under in undersampling:
                            args = [
                                "--dataset",
                                dataset,
                                "--lr",
                                f"{learning_rate:g}",
                                "--early",
                                str(early),
                                "--gnn",
                                gnn,
                                "--seed",
                                str(seed),
                                "--splits",
                                str(splits),
                                "--device",
                                device,
                            ]
                            if epochs is not None:
                                args.extend(["--epochs", str(epochs)])
                            if check is not None:
                                args.extend(["--check", str(check)])
                            if latent is not None:
                                args.extend(["--latent", str(latent)])
                            if embed_type is not None:
                                args.extend(["--embed_type", embed_type])
                            if under is not None:
                                args.extend(["--under", str(under)])
                            command = _iohunter_run_command(src_dir, script, args)
                            shell_command = _iohunter_shell_command(src_dir, script, args)
                            plan.append(
                                {
                                    "family": "iohunter",
                                    "method": "MultiModalGNN_CrossAttention_CrossCountryPlusFineTuning",
                                    "setting": "cross_io_finetuning",
                                    "dataset": dataset,
                                    "seed": seed,
                                    "gnn": gnn,
                                    "lr": learning_rate,
                                    "early": early,
                                    "splits": splits,
                                    "epochs": epochs,
                                    "check": check,
                                    "latent": latent,
                                    "embed_type": embed_type,
                                    "undersampling": under,
                                    "cwd": str(src_dir),
                                    "script": str(script),
                                    "args": args,
                                    "command": command,
                                    "shell_command": shell_command,
                                }
                            )
    return plan


def build_iohunter_commands(
    workspace: Path,
    *,
    datasets: Sequence[str] = IOHUNTER_DATASETS,
    seeds: Sequence[int] = (42, 43, 44, 45, 46),
    gnns: Sequence[str] = ("sage",),
    learning_rates: Sequence[float] = (1e-2,),
    early: int = 30,
    splits: int = 5,
    device: str = "0",
    epochs: int | None = None,
    check: int | None = None,
    latent: int | None = None,
    embed_type: str | None = None,
    undersampling: Sequence[float | str | None] = (None,),
    include_primary: bool = True,
    include_official_baselines: bool = False,
    include_cross_country: bool = False,
) -> list[str]:
    plan = build_iohunter_run_plan(
        workspace,
        datasets=datasets,
        seeds=seeds,
        gnns=gnns,
        learning_rates=learning_rates,
        early=early,
        splits=splits,
        device=device,
        epochs=epochs,
        check=check,
        latent=latent,
        embed_type=embed_type,
        undersampling=undersampling,
        include_primary=include_primary,
        include_official_baselines=include_official_baselines,
        include_cross_country=include_cross_country,
    )
    return [str(item["command"]) for item in plan]


def inspect_iohunter_data(workspace: Path) -> dict[str, object]:
    workspace_data_root = _iohunter_workspace_data_root(workspace)
    official_data_root = _iohunter_official_data_root(workspace)
    data_root = _iohunter_effective_data_root(workspace)
    official_data_layout_ready = official_data_root.exists()
    datasets = {}
    for dataset in IOHUNTER_DATASETS:
        dataset_dir = data_root / dataset
        files: list[Path] = []
        if dataset_dir.exists():
            files = [path for path in dataset_dir.rglob("*") if path.is_file()]
        has_dataset_pickle = any(path.name.endswith("datasets.pkl") for path in files)
        has_sbert_features = any(path.name.startswith("sbert_nodeattributes") and path.suffix == ".pt" for path in files)
        datasets[dataset] = {
            "exists": dataset_dir.exists(),
            "file_count": len(files),
            "has_dataset_pickle": has_dataset_pickle,
            "has_sbert_features": has_sbert_features,
            "ready_for_official_run": dataset_dir.exists() and has_dataset_pickle and has_sbert_features,
            "files": sorted(str(path.relative_to(dataset_dir)) for path in files)[:20] if dataset_dir.exists() else [],
        }
    repo_dir = _iohunter_repo_dir(workspace)
    src_dir = _iohunter_src_dir(workspace)
    scripts = {
        "primary": str(_iohunter_script_path(workspace, IOHUNTER_PRIMARY_SCRIPT)),
        "node_pruning": str(_iohunter_script_path(workspace, "run_NodePruning.py")),
        "node2vec": str(_iohunter_script_path(workspace, "run_Node2Vec.py")),
    }
    return {
        "repo_dir": str(repo_dir),
        "src_dir": str(src_dir),
        "data_root": str(data_root),
        "workspace_data_root": str(workspace_data_root),
        "official_data_root": str(official_data_root),
        "official_data_layout_ready": official_data_layout_ready,
        "workspace_data_layout_ready": workspace_data_root.exists(),
        "repo_exists": repo_dir.exists(),
        "src_exists": src_dir.exists(),
        "scripts": scripts,
        "datasets": datasets,
    }


def inspect_iohunter_environment(python_executable: str | None = None) -> dict[str, object]:
    if python_executable:
        probe = (
            "import importlib.util, json; "
            f"packages = {list(IOHUNTER_REQUIRED_PACKAGES)!r}; "
            "result = {name: importlib.util.find_spec(name) is not None for name in packages}; "
            "print(json.dumps(result))"
        )
        process = subprocess.run(
            [python_executable, "-c", probe],
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            return {
                "python_executable": python_executable,
                "python_packages": {},
                "missing_packages": list(IOHUNTER_REQUIRED_PACKAGES),
                "ready_for_official_run": False,
                "error": process.stderr.strip() or process.stdout.strip(),
            }
        packages = json.loads(process.stdout.strip())
        return {
            "python_executable": python_executable,
            "python_packages": packages,
            "missing_packages": [name for name, exists in packages.items() if not exists],
            "ready_for_official_run": all(packages.values()),
        }
    packages = {}
    for package_name in IOHUNTER_REQUIRED_PACKAGES:
        packages[package_name] = importlib.util.find_spec(package_name) is not None
    return {
        "python_executable": None,
        "python_packages": packages,
        "missing_packages": [name for name, exists in packages.items() if not exists],
        "ready_for_official_run": all(packages.values()),
    }


def iohunter_workspace_status(workspace: Path, *, python_executable: str | None = None) -> dict[str, object]:
    data_status = inspect_iohunter_data(workspace)
    environment_status = inspect_iohunter_environment(python_executable)
    dataset_values = data_status["datasets"].values()
    data_ready = bool(data_status["official_data_layout_ready"]) and all(
        bool(item["ready_for_official_run"]) for item in dataset_values
    )
    repo_ready = bool(data_status["repo_exists"]) and bool(data_status["src_exists"])
    return {
        "workspace": str(workspace),
        "repository_ready": repo_ready,
        "data_ready": data_ready,
        "environment_ready": environment_status["ready_for_official_run"],
        "ready_for_official_run": repo_ready and data_ready and environment_status["ready_for_official_run"],
        "data": data_status,
        "environment": environment_status,
    }


def write_iohunter_run_exports(
    workspace: Path,
    output_dir: Path,
    *,
    run_plan: Sequence[Mapping[str, object]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_plan_path = output_dir / "iohunter_run_plan.json"
    ps1_path = output_dir / "iohunter_commands.ps1"
    sh_path = output_dir / "iohunter_commands.sh"
    run_plan_path.write_text(json.dumps(list(run_plan), ensure_ascii=False, indent=2), encoding="utf-8")
    ps_lines = [
        "$ErrorActionPreference = 'Stop'",
        f"# Workspace: {workspace}",
        "",
    ]
    sh_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"# Workspace: {workspace}",
        "",
    ]
    for index, item in enumerate(run_plan, start=1):
        command = str(item["command"])
        shell_command = str(item.get("shell_command", command))
        ps_lines.append(f"# {index}. {item.get('family')} / {item.get('method')} / {item.get('dataset')} / seed={item.get('seed')}")
        ps_lines.append(command)
        sh_lines.append(f"# {index}. {item.get('family')} / {item.get('method')} / {item.get('dataset')} / seed={item.get('seed')}")
        sh_lines.append(shell_command)
    ps1_path.write_text("\n".join(ps_lines) + "\n", encoding="utf-8")
    sh_path.write_text("\n".join(sh_lines) + "\n", encoding="utf-8")
    return {
        "run_plan_json": str(run_plan_path),
        "powershell": str(ps1_path),
        "shell": str(sh_path),
    }


def load_iohunter_run_plan(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"IOHunter run plan must be a JSON list: {path}")
    return [dict(item) for item in data]


def _slug(value: object) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return text or "unknown"


def _run_plan_item_id(item: Mapping[str, object], index: int) -> str:
    parts = [
        f"{index:04d}",
        _slug(item.get("family", "family")),
        _slug(item.get("method", "method")),
        _slug(item.get("setting", "setting")),
        _slug(item.get("dataset", "dataset")),
        f"seed{_slug(item.get('seed', 'na'))}",
    ]
    if item.get("gnn"):
        parts.append(_slug(item["gnn"]))
    if item.get("undersampling") not in {None, "None", ""}:
        parts.append(f"under{_slug(item.get('undersampling'))}")
    return "__".join(parts)


def _iohunter_completed_despite_cleanup_error(stdout: str, stderr: str) -> bool:
    log_text = f"{stdout}\n{stderr}"
    has_test_metrics = bool(re.search(r"^\s*\[TEST[^\]]*\]\s+\w+:", log_text, re.MULTILINE))
    cleanup_error = "shutil.rmtree(exp_dir" in log_text and "not NoneType" in log_text
    return has_test_metrics and cleanup_error


def run_iohunter_plan(
    run_plan: Sequence[Mapping[str, object]],
    *,
    output_dir: Path,
    python_executable: str = "python",
    limit: int | None = None,
    dry_run: bool = False,
    stop_on_error: bool = False,
    resume: bool = True,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "iohunter_run_manifest.json"
    previous_records: dict[str, dict[str, object]] = {}
    if resume and manifest_path.exists():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous_records = {
            str(record.get("run_id")): dict(record)
            for record in previous_manifest.get("records", [])
            if record.get("run_id")
        }
    selected = list(run_plan[:limit]) if limit is not None else list(run_plan)
    records = []
    for index, item in enumerate(selected, start=1):
        cwd = Path(str(item["cwd"]))
        script = Path(str(item["script"]))
        args = [str(value) for value in item.get("args", [])]
        run_id = _run_plan_item_id(item, index)
        stdout_path = log_dir / f"{run_id}.stdout.log"
        stderr_path = log_dir / f"{run_id}.stderr.log"
        record = {
            **dict(item),
            "run_id": run_id,
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
            "dry_run": dry_run,
        }
        previous_record = previous_records.get(run_id)
        if previous_record and previous_record.get("status") == "passed":
            previous_record["status"] = "skipped_existing_success"
            records.append(previous_record)
            continue
        if dry_run:
            stdout_path.touch()
            stderr_path.touch()
            record.update({"returncode": None, "status": "dry_run"})
            records.append(record)
            continue
        started_at = datetime.now(timezone.utc).isoformat()
        process = subprocess.run(
            [python_executable, script.name, *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_path.write_text(process.stdout, encoding="utf-8", errors="replace")
        stderr_path.write_text(process.stderr, encoding="utf-8", errors="replace")
        finished_at = datetime.now(timezone.utc).isoformat()
        status = "passed" if process.returncode == 0 else "failed"
        warning = ""
        if process.returncode != 0 and _iohunter_completed_despite_cleanup_error(process.stdout, process.stderr):
            status = "passed_with_cleanup_warning"
            warning = "official_script_completed_metrics_but_failed_cleanup"
        record.update(
            {
                "returncode": process.returncode,
                "status": status,
                "warning": warning,
                "started_at": started_at,
                "finished_at": finished_at,
            }
        )
        records.append(record)
        if status == "failed" and stop_on_error:
            break
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "resume": resume,
        "python_executable": python_executable,
        "total_requested": len(run_plan),
        "total_selected": len(selected),
        "completed": len(records),
        "failed": sum(1 for item in records if item.get("status") == "failed"),
        "records": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _parse_float_maybe(value: str) -> float | None:
    if value in {"None", "nan", "NaN"}:
        return None
    return float(value)


def parse_iohunter_log_metrics(log_text: str) -> list[dict[str, object]]:
    rows = []
    for match in IOHUNTER_LOG_METRIC_RE.finditer(log_text):
        rows.append(
            {
                "split": match.group("split"),
                "metric": match.group("metric"),
                "mean": _parse_float_maybe(match.group("mean")),
                "std": _parse_float_maybe(match.group("std")),
            }
        )
    return rows


def summarize_iohunter_runs(run_output_dir: Path, *, output_dir: Path | None = None) -> dict[str, object]:
    manifest_path = run_output_dir / "iohunter_run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing IOHunter run manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for record in manifest.get("records", []):
        stdout_path = Path(str(record.get("stdout_log", "")))
        stderr_path = Path(str(record.get("stderr_log", "")))
        log_text_parts = []
        if stdout_path.exists():
            log_text_parts.append(stdout_path.read_text(encoding="utf-8", errors="replace"))
        if stderr_path.exists():
            log_text_parts.append(stderr_path.read_text(encoding="utf-8", errors="replace"))
        for metric in parse_iohunter_log_metrics("\n".join(log_text_parts)):
            rows.append(
                {
                    "family": record.get("family"),
                    "method": record.get("method"),
                    "setting": record.get("setting"),
                    "dataset": record.get("dataset"),
                    "seed": record.get("seed"),
                    "gnn": record.get("gnn"),
                    "undersampling": record.get("undersampling"),
                    "status": record.get("status"),
                    **metric,
                    "run_id": record.get("run_id"),
                }
            )
    target_dir = output_dir or run_output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    csv_path = target_dir / "iohunter_metrics.csv"
    json_path = target_dir / "iohunter_metrics.json"
    aggregate_csv_path = target_dir / "iohunter_metric_summary.csv"
    aggregate_json_path = target_dir / "iohunter_metric_summary.json"
    fields = (
        "family",
        "method",
        "setting",
        "dataset",
        "seed",
        "gnn",
        "undersampling",
        "split",
        "metric",
        "mean",
        "std",
        "status",
        "run_id",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    aggregate_rows = aggregate_iohunter_metric_rows(rows)
    aggregate_fields = (
        "family",
        "method",
        "setting",
        "dataset",
        "gnn",
        "undersampling",
        "split",
        "metric",
        "run_count",
        "mean",
        "std",
    )
    with aggregate_csv_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=aggregate_fields)
        writer.writeheader()
        for row in aggregate_rows:
            writer.writerow({field: row.get(field) for field in aggregate_fields})
    aggregate_json_path.write_text(json.dumps(aggregate_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "manifest": str(manifest_path),
        "metric_count": len(rows),
        "metrics_csv": str(csv_path),
        "metrics_json": str(json_path),
        "summary_csv": str(aggregate_csv_path),
        "summary_json": str(aggregate_json_path),
        "rows": rows,
        "summary_rows": aggregate_rows,
    }


def aggregate_iohunter_metric_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[float]] = defaultdict(list)
    for row in rows:
        value = row.get("mean")
        if value is None:
            continue
        key = (
            row.get("family"),
            row.get("method"),
            row.get("setting"),
            row.get("dataset"),
            row.get("gnn"),
            row.get("undersampling"),
            row.get("split"),
            row.get("metric"),
        )
        groups[key].append(float(value))
    output = []
    for key, values in sorted(groups.items(), key=lambda item: tuple(str(part) for part in item[0])):
        array = np.asarray(values, dtype=float)
        output.append(
            {
                "family": key[0],
                "method": key[1],
                "setting": key[2],
                "dataset": key[3],
                "gnn": key[4],
                "undersampling": key[5],
                "split": key[6],
                "metric": key[7],
                "run_count": len(values),
                "mean": round(float(np.mean(array)), 6),
                "std": round(float(np.std(array, ddof=1)), 6) if len(values) > 1 else 0.0,
            }
        )
    return output


def _read_csv_dicts(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV file: {path}")
    with path.open("r", encoding="utf-8", newline="") as file_handle:
        return [dict(row) for row in csv.DictReader(file_handle)]


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _load_lightweight_report_rows(directory: Path) -> list[dict[str, object]]:
    metrics_path = directory / "metrics.csv"
    rows = []
    dataset = directory.name
    summary_path = directory / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        conversion = summary.get("iohunter_conversion")
        if isinstance(conversion, Mapping):
            dataset = str(conversion.get("dataset") or dataset)
    for row in _read_csv_dicts(metrics_path):
        f1 = _float_or_none(row.get("f1"))
        auc = _float_or_none(row.get("auc"))
        precision = _float_or_none(row.get("precision"))
        recall = _float_or_none(row.get("recall"))
        rows.append(
            {
                "source": "lightweight_reproduction",
                "setting": row.get("setting") or "detect",
                "family": row.get("family"),
                "method": row.get("method"),
                "dataset": dataset,
                "scope": row.get("scope") or "user",
                "split": "TEST",
                "run_count": 1,
                "macro_f1": f1,
                "auc": auc,
                "precision": precision,
                "recall": recall,
                "accuracy": None,
                "primary_metric": f1,
                "notes": row.get("notes", ""),
            }
        )
    return rows


def _load_iohunter_report_rows(directory: Path) -> list[dict[str, object]]:
    summary_path = directory / "iohunter_metric_summary.csv"
    metric_rows = _read_csv_dicts(summary_path)
    grouped: dict[tuple[object, ...], dict[str, object]] = {}
    for row in metric_rows:
        split = str(row.get("split") or "")
        if split != "TEST":
            continue
        key = (
            row.get("family"),
            row.get("method"),
            row.get("setting"),
            row.get("dataset"),
            row.get("gnn"),
            row.get("undersampling"),
        )
        record = grouped.setdefault(
            key,
            {
                "source": "iohunter_official",
                "setting": row.get("setting"),
                "family": row.get("family"),
                "method": row.get("method"),
                "dataset": row.get("dataset"),
                "scope": "user",
                "split": "TEST",
                "run_count": int(float(str(row.get("run_count") or 0))),
                "macro_f1": None,
                "auc": None,
                "precision": None,
                "recall": None,
                "accuracy": None,
                "primary_metric": None,
                "notes": "",
            },
        )
        metric = str(row.get("metric") or "")
        value = _float_or_none(row.get("mean"))
        if metric in {"f1_macro", "macro_f1"}:
            record["macro_f1"] = value
            record["primary_metric"] = value
        elif metric in {"roc_auc", "auc"}:
            record["auc"] = value
        elif metric == "precision":
            record["precision"] = value
        elif metric == "recall":
            record["recall"] = value
        elif metric == "accuracy":
            record["accuracy"] = value
        notes = []
        if row.get("gnn"):
            notes.append(f"gnn={row.get('gnn')}")
        if row.get("undersampling"):
            notes.append(f"under={row.get('undersampling')}")
        record["notes"] = ";".join(notes)
    return list(grouped.values())


def _write_markdown_table(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    headers = ("source", "setting", "family", "method", "dataset", "macro_f1", "auc", "precision", "recall", "accuracy", "notes")
    lines = [
        "# CoordinationDiscover IO Coordination Comparison",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = []
        for header in headers:
            value = row.get(header)
            if isinstance(value, float):
                value = f"{value:.6f}"
            values.append(str(value) if value is not None else "")
        lines.append("| " + " | ".join(values) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_coordination_discover_comparison_report(
    *,
    output_dir: Path,
    lightweight_dirs: Sequence[Path] = (),
    iohunter_summary_dirs: Sequence[Path] = (),
) -> dict[str, object]:
    """Merge CoordinationDiscover lightweight and official IOHunter metrics into one report table."""
    rows: list[dict[str, object]] = []
    for directory in lightweight_dirs:
        rows.extend(_load_lightweight_report_rows(Path(directory)))
    for directory in iohunter_summary_dirs:
        rows.extend(_load_iohunter_report_rows(Path(directory)))
    rows = sorted(
        rows,
        key=lambda row: (
            str(row.get("dataset") or ""),
            str(row.get("source") or ""),
            str(row.get("family") or ""),
            str(row.get("method") or ""),
            str(row.get("notes") or ""),
        ),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "coordination_discover_comparison_report.csv"
    json_path = output_dir / "coordination_discover_comparison_report.json"
    markdown_path = output_dir / "CoordinationDiscover_COMPARISON_REPORT.md"
    fields = (
        "source",
        "setting",
        "family",
        "method",
        "dataset",
        "scope",
        "split",
        "run_count",
        "macro_f1",
        "auc",
        "precision",
        "recall",
        "accuracy",
        "primary_metric",
        "notes",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_table(markdown_path, rows)
    return {
        "row_count": len(rows),
        "csv": str(csv_path),
        "json": str(json_path),
        "markdown": str(markdown_path),
        "rows": rows,
    }


def run_iohunter_lightweight_batch(
    processed_root: Path,
    *,
    output_dir: Path,
    datasets: Sequence[str] = IOHUNTER_DATASETS,
    threshold: str = "0.7",
    train_percentage: str | None = None,
    undersampling: str | None = None,
    max_edges_per_relation: int | None = None,
    seed: int = 42,
    relations: Sequence[str] = IOHUNTER_CANONICAL_RELATIONS,
    include_text_similarity: bool = False,
    max_edges_per_node: int | None = 50,
    embedding_dim: int = 32,
    continue_on_error: bool = False,
) -> dict[str, object]:
    """Run lightweight CoordinationDiscover baselines over multiple IOHunter processed datasets."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_results: dict[str, dict[str, object]] = {}
    failures: dict[str, str] = {}
    for dataset_name in datasets:
        dataset_dir = processed_root / dataset_name
        dataset_output_dir = output_dir / dataset_name
        try:
            events_path = dataset_output_dir / "iohunter_events.csv"
            conversion = write_iohunter_event_table(
                dataset_dir,
                events_path,
                dataset_name=dataset_name,
                threshold=threshold,
                train_percentage=train_percentage,
                undersampling=undersampling,
                max_edges_per_relation=max_edges_per_relation,
            )
            events = read_event_table(events_path)
            summary = run_reproduction_suite(
                events,
                output_dir=dataset_output_dir,
                relations=relations,
                include_text_similarity=include_text_similarity,
                max_edges_per_node=max_edges_per_node,
                embedding_dim=embedding_dim,
                seed=seed,
            )
            summary["iohunter_conversion"] = conversion
            (dataset_output_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            dataset_results[dataset_name] = {
                "dataset_dir": str(dataset_dir),
                "output_dir": str(dataset_output_dir),
                "metrics_csv": str(dataset_output_dir / "metrics.csv"),
                "summary_json": str(dataset_output_dir / "summary.json"),
                "row_count": conversion["row_count"],
                "account_count": conversion["account_count"],
                "positive_label_count": conversion["positive_label_count"],
            }
        except Exception as exc:
            failures[dataset_name] = str(exc)
            if not continue_on_error:
                raise
    report = build_coordination_discover_comparison_report(
        output_dir=output_dir / "coordination_discover_report",
        lightweight_dirs=tuple(Path(item["output_dir"]) for item in dataset_results.values()),
    )
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processed_root": str(processed_root),
        "output_dir": str(output_dir),
        "dataset_count": len(dataset_results),
        "failed": len(failures),
        "datasets": dataset_results,
        "failures": failures,
        "include_text_similarity": include_text_similarity,
        "max_edges_per_node": max_edges_per_node,
        "embedding_dim": embedding_dim,
        "report": {
            key: value
            for key, value in report.items()
            if key != "rows"
        },
    }
    manifest_path = output_dir / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        **manifest,
        "manifest": str(manifest_path),
        "report": report,
    }


def _is_valid_zip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except zipfile.BadZipFile:
        return False


def _download_file_with_resume(
    url: str,
    destination: Path,
    *,
    expected_size: int | None = None,
    retries: int = 3,
) -> list[str]:
    actions: list[str] = []
    part_path = destination.with_suffix(destination.suffix + ".part")
    if destination.exists() and expected_size and destination.stat().st_size < expected_size:
        destination.replace(part_path)
        actions.append(f"moved_incomplete_zip_to_part:{part_path}")
    for attempt in range(1, retries + 1):
        resume_at = part_path.stat().st_size if part_path.exists() else 0
        request = urllib.request.Request(url)
        if resume_at:
            request.add_header("Range", f"bytes={resume_at}-")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status = getattr(response, "status", None)
                if resume_at and status == 200:
                    part_path.unlink(missing_ok=True)
                    resume_at = 0
                    actions.append("server_ignored_range_restart_download")
                mode = "ab" if resume_at else "wb"
                with part_path.open(mode) as file_handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        file_handle.write(chunk)
            current_size = part_path.stat().st_size
            actions.append(f"download_attempt_{attempt}:{current_size}")
            if expected_size is None or current_size >= expected_size:
                part_path.replace(destination)
                actions.append(f"downloaded:{destination}")
                return actions
        except Exception as exc:
            actions.append(f"download_attempt_{attempt}_failed:{type(exc).__name__}:{exc}")
            if attempt == retries:
                raise
            time.sleep(min(2**attempt, 10))
    if part_path.exists():
        part_path.replace(destination)
    return actions


def prepare_iohunter_workspace(
    workspace: Path,
    *,
    clone_code: bool = False,
    download_data: bool = False,
    python_executable: str | None = None,
) -> dict[str, object]:
    workspace.mkdir(parents=True, exist_ok=True)
    repo_dir = workspace / "SocGFM"
    data_zip = workspace / "data.zip"
    actions: list[str] = []
    if clone_code and not repo_dir.exists():
        subprocess.run(["git", "clone", IOHUNTER_REPO_URL, str(repo_dir)], check=True)
        actions.append(f"cloned:{repo_dir}")
    if download_data and not _is_valid_zip(data_zip):
        actions.extend(
            _download_file_with_resume(
                IOHUNTER_ZENODO_DATA_URL,
                data_zip,
                expected_size=IOHUNTER_ZENODO_DATA_SIZE,
            )
        )
    if download_data and data_zip.exists() and not _is_valid_zip(data_zip):
        actions.append(f"invalid_zip:{data_zip}")
        raise zipfile.BadZipFile(f"Downloaded IOHunter archive is not a valid zip: {data_zip}")
    if download_data and data_zip.exists() and _is_valid_zip(data_zip) and not (workspace / "data" / "processed").exists():
        with zipfile.ZipFile(data_zip) as archive:
            archive.extractall(workspace)
        actions.append(f"extracted:{data_zip}")
    return {
        "workspace": str(workspace),
        "repo_dir": str(repo_dir),
        "data_zip": str(data_zip),
        "actions": actions,
        "status": iohunter_workspace_status(workspace, python_executable=python_executable),
        "commands": build_iohunter_commands(workspace),
    }


def run_reproduction_suite(
    events: pd.DataFrame,
    *,
    output_dir: Path,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    include_text_similarity: bool = True,
    max_edges_per_node: int | None = None,
    embedding_dim: int = 128,
    seed: int = 42,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    unmasking = run_unmasking_reproduction(
        events,
        relations=relations,
        include_text_similarity=include_text_similarity,
        max_edges_per_node=max_edges_per_node,
        embedding_dim=embedding_dim,
        seed=seed,
    )
    graphs = build_unmasking_similarity_graphs(
        events,
        relations=relations,
        include_text_similarity=include_text_similarity,
        max_edges_per_node=max_edges_per_node,
    )
    fused = fuse_similarity_graphs(graphs)
    llm = run_lightweight_llm_baselines(events, fused, output_dir=output_dir, seed=seed)
    ours_ablations = run_dyna_colm_gnn_ablations(events, relations=relations, seed=seed)
    ours = ours_ablations["full"]
    summary = {
        "manifest": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "row_count": int(len(events)),
            "account_count": int(events["account_id"].nunique()),
            "relations": list(relations),
            "include_text_similarity": include_text_similarity,
            "max_edges_per_node": max_edges_per_node,
            "embedding_dim": embedding_dim,
            "seed": seed,
            "implementation": "coordination_discover_io_reproduction_lightweight",
        },
        "unmasking": unmasking,
        "leveraging_llms": llm,
        "ours": ours,
        "ours_ablations": {
            variant: result
            for variant, result in ours_ablations.items()
            if variant != "full"
        },
    }
    exports = write_metric_exports(summary, output_dir)
    summary["exports"] = exports
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(summary["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")
    return summary

__all__ = [
    "aggregate_iohunter_metric_rows",
    "build_coordination_discover_comparison_report",
    "build_iohunter_commands",
    "build_iohunter_run_plan",
    "ensure_iohunter_official_data_layout",
    "inspect_iohunter_data",
    "inspect_iohunter_environment",
    "iohunter_workspace_status",
    "load_iohunter_run_plan",
    "parse_iohunter_log_metrics",
    "patch_iohunter_official_scripts",
    "prepare_iohunter_workspace",
    "run_iohunter_lightweight_batch",
    "run_iohunter_plan",
    "run_reproduction_suite",
    "summarize_iohunter_runs",
    "write_iohunter_run_exports",
]
