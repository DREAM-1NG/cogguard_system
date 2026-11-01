"""Verify the built-in social runtime used by CogGuard."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.core.crawler.mediacrawler_env import (  # noqa: E402
    build_mediacrawler_env,
    resolve_mediacrawler_runtime_python,
    resolve_node_bin,
    resolve_python_bin,
    resolve_social_runtime_root,
    resolve_uv_bin,
)


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    required: bool = True


def run_command(args: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def check_root() -> tuple[Path, CheckResult]:
    root = resolve_social_runtime_root()
    if not root.is_dir():
        return root, CheckResult("social runtime root", False, f"Directory not found: {root}")
    main_py = root / "main.py"
    if not main_py.is_file():
        return root, CheckResult("social runtime main.py", False, f"Entrypoint missing: {main_py}")
    return root, CheckResult("social runtime root", True, str(root))


def check_uv() -> tuple[str | None, CheckResult]:
    uv_bin = resolve_uv_bin()
    if not uv_bin:
        return None, CheckResult("uv", False, "uv not found on PATH.")
    result = run_command([uv_bin, "--version"])
    ok = result.returncode == 0
    detail = (result.stdout or result.stderr).strip() or uv_bin
    return uv_bin, CheckResult("uv", ok, detail)


def check_runtime_python(root: Path) -> tuple[str | None, CheckResult]:
    runtime_python = resolve_mediacrawler_runtime_python(root)
    if not runtime_python:
        return None, CheckResult(
            "social runtime python",
            False,
            "No runtime .venv interpreter found; will fall back to uv run.",
            required=False,
        )

    result = run_command([runtime_python, "-V"], env=build_mediacrawler_env())
    ok = result.returncode == 0
    detail = (result.stdout or result.stderr).strip() or runtime_python
    return runtime_python, CheckResult("social runtime python", ok, detail)


def check_node() -> tuple[str | None, CheckResult]:
    node_bin = resolve_node_bin()
    if not node_bin:
        return None, CheckResult("node", False, "node not found; set MEDIACRAWLER_NODE_DIR if needed.")
    result = run_command([node_bin, "-v"], env=build_mediacrawler_env())
    ok = result.returncode == 0
    detail = (result.stdout or result.stderr).strip() or node_bin
    return node_bin, CheckResult("node", ok, detail)


def build_runtime_command(runtime_python: str | None, uv_bin: str | None, args: list[str]) -> list[str]:
    if runtime_python:
        return [runtime_python, *args]
    if not uv_bin:
        raise RuntimeError("No runtime python and no uv available.")
    return [uv_bin, "run", "--python", resolve_python_bin(), *args]


def check_cli_help(root: Path, runtime_python: str | None, uv_bin: str | None) -> CheckResult:
    result = run_command(
        build_runtime_command(runtime_python, uv_bin, ["main.py", "--help"]),
        cwd=root,
        env=build_mediacrawler_env(),
    )
    ok = result.returncode == 0
    detail = (result.stdout or result.stderr).strip() or "social runtime CLI --help completed"
    return CheckResult("social runtime CLI", ok, detail[:800])


def print_result(result: CheckResult) -> None:
    status = "OK" if result.ok else "FAIL"
    print(f"[{status}] {result.name}: {result.detail}")


def main() -> int:
    print("== CogGuard Built-in Social Runtime Verification ==")
    print(f"Login type: {settings.MEDIACRAWLER_LOGIN_TYPE or 'cookie'}")
    print(f"Python bin: {resolve_python_bin()}")
    print(f"Node dir: {settings.MEDIACRAWLER_NODE_DIR or '(inherit PATH)'}")
    print(f"Sub comments: {'enabled' if settings.MEDIACRAWLER_GET_SUB_COMMENTS else 'disabled'}")
    print(f"Max comments per post: {settings.MEDIACRAWLER_MAX_COMMENTS_PER_POST}")
    print()

    critical_failures = False

    root, root_result = check_root()
    print_result(root_result)
    critical_failures = critical_failures or root_result.required and not root_result.ok

    runtime_python = None
    if root_result.ok:
        runtime_python, runtime_result = check_runtime_python(root)
        print_result(runtime_result)
        critical_failures = critical_failures or runtime_result.required and not runtime_result.ok

    uv_bin, uv_result = check_uv()
    print_result(uv_result)
    critical_failures = critical_failures or uv_result.required and not uv_result.ok

    node_bin, node_result = check_node()
    print_result(node_result)

    if root_result.ok and (runtime_python or (uv_bin and uv_result.ok)):
        cli_result = check_cli_help(root, runtime_python, uv_bin)
        print_result(cli_result)
        critical_failures = critical_failures or cli_result.required and not cli_result.ok

    print()
    platform_summary = {
        "weibo": "ready" if root_result.ok else "blocked",
        "xhs": "ready" if root_result.ok else "blocked",
        "douyin": "ready" if root_result.ok and node_result.ok and bool(node_bin) else "blocked",
    }
    print("Platform summary:")
    for platform, state in platform_summary.items():
        print(f"- {platform}: {state}")

    if critical_failures:
        print()
        print("Verification result: FAIL")
        return 1

    print()
    print("Verification result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
