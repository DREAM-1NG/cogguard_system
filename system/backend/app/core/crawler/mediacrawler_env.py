"""Helpers for resolving the internal social crawler runtime."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

from app.config import PROJECT_ROOT, settings


def resolve_social_runtime_root() -> Path:
    return (PROJECT_ROOT / "runtimes" / "social_runtime").resolve()


def resolve_executable(default_name: str) -> str | None:
    return shutil.which(default_name)


def resolve_uv_bin() -> str | None:
    return resolve_executable("uv")


def resolve_python_bin() -> str:
    return sys.executable


def resolve_mediacrawler_runtime_python(root: str | Path | None = None) -> str | None:
    runtime_root = Path(root).resolve() if root else resolve_social_runtime_root()
    for candidate in (
        runtime_root / ".venv" / "Scripts" / "python.exe",
        runtime_root / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_node_bin() -> str | None:
    node_dir = (settings.MEDIACRAWLER_NODE_DIR or "").strip()
    if node_dir:
        node_root = Path(node_dir)
        for candidate in (node_root / "node.exe", node_root / "node"):
            if candidate.is_file():
                return str(candidate)
        resolved = shutil.which("node", path=str(node_root))
        if resolved:
            return resolved
    return shutil.which("node")


def build_mediacrawler_env(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)

    for key in ("UV_RUN_RECURSION_DEPTH", "VIRTUAL_ENV"):
        env.pop(key, None)

    proxy = (settings.MEDIACRAWLER_PROXY or "").strip()
    if proxy:
        env["MEDIACRAWLER_BROWSER_PROXY"] = proxy
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["http_proxy"] = proxy
        env["https_proxy"] = proxy

    node_dir = (settings.MEDIACRAWLER_NODE_DIR or "").strip()
    if not node_dir:
        return env

    node_root = Path(node_dir)
    if not node_root.is_dir():
        return env

    existing_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join([str(node_root), existing_path]) if existing_path else str(node_root)
    return env
