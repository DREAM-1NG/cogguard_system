from pathlib import Path

from app.config import BASE_DIR, PROJECT_ROOT, Settings, settings
from app.core.crawler.mediacrawler_env import (
    build_mediacrawler_env,
    resolve_mediacrawler_runtime_python,
    resolve_node_bin,
    resolve_python_bin,
    resolve_social_runtime_root,
    resolve_uv_bin,
)


def test_settings_env_files_cover_project_root_and_backend():
    env_files = Settings.model_config["env_file"]
    assert env_files == (str(PROJECT_ROOT / ".env"), str(BASE_DIR / ".env"))


def test_removed_external_runtime_settings_are_no_longer_modeled():
    for attr in (
        "MEDIACRAWLER_ROOT",
        "MEDIACRAWLER_UV_BIN",
        "MEDIACRAWLER_PYTHON_BIN",
        "MEDIACRAWLER_UV_CACHE_DIR",
        "NEWSCRAWLER_API_BASE",
        "NEWSCRAWLER_ROOT",
    ):
        assert not hasattr(settings, attr)


def test_build_mediacrawler_env_prepends_node_dir(monkeypatch, tmp_path: Path):
    node_dir = tmp_path / "node"
    node_dir.mkdir()
    monkeypatch.setattr(settings, "MEDIACRAWLER_NODE_DIR", str(node_dir))

    env = build_mediacrawler_env({"PATH": "C:/Windows/System32"})

    assert env["PATH"].split(";")[0] == str(node_dir)


def test_build_mediacrawler_env_sets_proxy_for_browser_and_http(monkeypatch):
    proxy = "http://127.0.0.1:7897"
    monkeypatch.setattr(settings, "MEDIACRAWLER_NODE_DIR", "")
    monkeypatch.setattr(settings, "MEDIACRAWLER_PROXY", proxy)

    env = build_mediacrawler_env({"PATH": "C:/Windows/System32"})

    assert env["MEDIACRAWLER_BROWSER_PROXY"] == proxy
    assert env["HTTP_PROXY"] == proxy
    assert env["HTTPS_PROXY"] == proxy
    assert env["http_proxy"] == proxy
    assert env["https_proxy"] == proxy


def test_build_mediacrawler_env_strips_parent_uv_markers(monkeypatch):
    monkeypatch.setattr(settings, "MEDIACRAWLER_NODE_DIR", "")
    monkeypatch.setattr(settings, "MEDIACRAWLER_PROXY", "")

    env = build_mediacrawler_env(
        {
            "PATH": "C:/Windows/System32",
            "UV_RUN_RECURSION_DEPTH": "1",
            "VIRTUAL_ENV": "G:/CISCN/cogguard_system/new-system/backend/.venv",
        }
    )

    assert "UV_RUN_RECURSION_DEPTH" not in env
    assert "VIRTUAL_ENV" not in env


def test_resolve_node_bin_from_node_dir(monkeypatch, tmp_path: Path):
    node_dir = tmp_path / "node"
    node_dir.mkdir()
    node_bin = node_dir / "node.exe"
    node_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "MEDIACRAWLER_NODE_DIR", str(node_dir))

    assert resolve_node_bin() == str(node_bin)


def test_resolve_uv_bin_uses_path_lookup():
    uv_bin = resolve_uv_bin()
    assert uv_bin is None or isinstance(uv_bin, str)


def test_resolve_python_bin_returns_current_interpreter():
    python_bin = resolve_python_bin()
    assert python_bin
    assert python_bin.endswith(("python", "python.exe"))


def test_resolve_social_runtime_root_points_inside_repo():
    runtime_root = resolve_social_runtime_root()
    assert runtime_root == (PROJECT_ROOT / "runtimes" / "social_runtime").resolve()


def test_resolve_mediacrawler_runtime_python_prefers_project_venv(tmp_path: Path):
    runtime_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")

    assert resolve_mediacrawler_runtime_python(tmp_path) == str(runtime_python)
