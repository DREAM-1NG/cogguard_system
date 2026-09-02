from __future__ import annotations

import os
import subprocess
from pathlib import Path


CURATED_FIXTURES_PREFIX = "system/backend/tests/fixtures/"
ROOT_GENERATED_PREFIXES = (
    ".playwright-cli/",
    "system/output/",
    "system/frontend/output/",
    "system/backend/output/",
    "tmp/",
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _tracked_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [path for path in result.stdout.decode().split("\0") if path]


def _is_generated_release_path(path: str) -> bool:
    if any(path.startswith(prefix) for prefix in ROOT_GENERATED_PREFIXES):
        return True

    path_parts = path.split("/")
    return path_parts[0] == "system" and ".playwright-cli" in path_parts


def _is_curated_fixture(path: str) -> bool:
    return path.startswith(CURATED_FIXTURES_PREFIX)


def test_release_surface_does_not_track_generated_files():
    root = _repository_root()
    violations = sorted(
        path
        for path in _tracked_paths(root)
        if _is_generated_release_path(path) and not _is_curated_fixture(path)
    )

    assert not violations, "Tracked generated release-surface paths:\n" + "\n".join(violations)


def _export_body(text: str) -> str:
    lines = text.replace("\r\n", "\n").splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    return "\n".join(lines).rstrip() + "\n"


def test_requirements_export_matches_frozen_lock(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    result = subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--extra",
            "dev",
            "--no-hashes",
            "--format",
            "requirements-txt",
        ],
        cwd=backend,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    committed = (backend / "requirements.txt").read_text(encoding="utf-8")
    assert _export_body(committed) == _export_body(result.stdout)
