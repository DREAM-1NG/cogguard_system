"""Helpers for resolving MediaCrawler runtime dependencies."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

from app.config import settings


def resolve_executable(candidate: str | None, default_name: str) -> str | None:
    raw = (candidate or "").strip()
    if raw:
        candidate_path = Path(raw)
        if candidate_path.is_file():
            return str(candidate_path)
        resolved = shutil.which(raw)
        if resolved:
            return resolved
    return shutil.which(default_name)


def resolve_uv_bin() -> str | None:
    return resolve_executable(settings.MEDIACRAWLER_UV_BIN, "uv")


def resolve_python_bin() -> str:
    raw = (settings.MEDIACRAWLER_PYTHON_BIN or "").strip()
    if raw:
        candidate_path = Path(raw)
        if candidate_path.is_file():
            return str(candidate_path)
        resolved = shutil.which(raw)
        if resolved:
            return resolved
    return sys.executable


def resolve_mediacrawler_runtime_python(root: str | Path | None) -> str | None:
    if not root:
        return None

    root_path = Path(root)
    for candidate in (
        root_path / ".venv" / "Scripts" / "python.exe",
        root_path / ".venv" / "bin" / "python",
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

    # Remove the parent uv virtualenv markers before nesting another
    # ``uv run`` for MediaCrawler. Otherwise the child process may inherit
    # backend-specific execution state and fail to bootstrap cleanly.
    for key in ("UV_RUN_RECURSION_DEPTH", "VIRTUAL_ENV"):
        env.pop(key, None)

    uv_cache_dir = (settings.MEDIACRAWLER_UV_CACHE_DIR or "").strip()
    if uv_cache_dir:
        env["UV_CACHE_DIR"] = uv_cache_dir

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
