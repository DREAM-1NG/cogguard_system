from pathlib import Path

from app.config import BASE_DIR, PROJECT_ROOT, Settings, settings
from app.core.crawler.mediacrawler_env import (
    build_mediacrawler_env,
    resolve_mediacrawler_runtime_python,
    resolve_node_bin,
    resolve_python_bin,
    resolve_uv_bin,
)


def test_settings_env_files_cover_project_root_and_backend():
    env_files = Settings.model_config["env_file"]
    assert env_files == (str(PROJECT_ROOT / ".env"), str(BASE_DIR / ".env"))


def test_build_mediacrawler_env_prepends_node_dir(monkeypatch, tmp_path: Path):
    node_dir = tmp_path / "node"
    node_dir.mkdir()
    monkeypatch.setattr(settings, "MEDIACRAWLER_NODE_DIR", str(node_dir))
    monkeypatch.setattr(settings, "MEDIACRAWLER_UV_CACHE_DIR", "")

    env = build_mediacrawler_env({"PATH": "C:/Windows/System32"})

    assert env["PATH"].split(";")[0] == str(node_dir)


def test_build_mediacrawler_env_sets_uv_cache_dir(monkeypatch, tmp_path: Path):
    cache_dir = tmp_path / ".uv-cache"
    monkeypatch.setattr(settings, "MEDIACRAWLER_NODE_DIR", "")
    monkeypatch.setattr(settings, "MEDIACRAWLER_UV_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(settings, "MEDIACRAWLER_PROXY", "")

    env = build_mediacrawler_env({"PATH": "C:/Windows/System32"})

    assert env["UV_CACHE_DIR"] == str(cache_dir)


def test_build_mediacrawler_env_sets_proxy_for_browser_and_http(monkeypatch):
    proxy = "http://127.0.0.1:7897"
    monkeypatch.setattr(settings, "MEDIACRAWLER_NODE_DIR", "")
    monkeypatch.setattr(settings, "MEDIACRAWLER_UV_CACHE_DIR", "")
    monkeypatch.setattr(settings, "MEDIACRAWLER_PROXY", proxy)

    env = build_mediacrawler_env({"PATH": "C:/Windows/System32"})

    assert env["MEDIACRAWLER_BROWSER_PROXY"] == proxy
    assert env["HTTP_PROXY"] == proxy
    assert env["HTTPS_PROXY"] == proxy
    assert env["http_proxy"] == proxy
    assert env["https_proxy"] == proxy


def test_build_mediacrawler_env_strips_parent_uv_markers(monkeypatch):
    monkeypatch.setattr(settings, "MEDIACRAWLER_NODE_DIR", "")
    monkeypatch.setattr(settings, "MEDIACRAWLER_UV_CACHE_DIR", "")
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


def test_resolve_uv_bin_from_absolute_path(monkeypatch, tmp_path: Path):
    uv_bin = tmp_path / "uv.exe"
    uv_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "MEDIACRAWLER_UV_BIN", str(uv_bin))

    assert resolve_uv_bin() == str(uv_bin)


def test_resolve_python_bin_from_absolute_path(monkeypatch, tmp_path: Path):
    python_bin = tmp_path / "python.exe"
    python_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "MEDIACRAWLER_PYTHON_BIN", str(python_bin))

    assert resolve_python_bin() == str(python_bin)


def test_resolve_mediacrawler_runtime_python_prefers_project_venv(tmp_path: Path):
    runtime_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")

    assert resolve_mediacrawler_runtime_python(tmp_path) == str(runtime_python)
