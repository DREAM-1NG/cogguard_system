from __future__ import annotations

import importlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

from app.config import PROJECT_ROOT


def test_canonical_packages_publish_explicit_public_boundaries():
    analysis = importlib.import_module("app.core.analysis")
    review = importlib.import_module("app.core.review")
    coordination_baseline = importlib.import_module("app.core.coordination_baseline")

    assert "analyze_coordination_discover_snapshot" in analysis.__all__
    assert "build_coordination_discover_evidence_edges" in analysis.__all__
    assert "try_load_coordination_discover_result" in analysis.__all__
    assert "agent_review" in review.__all__
    assert "detect_groups" in coordination_baseline.__all__


def test_legacy_risk_submodule_imports_resolve_to_review_boundary():
    legacy_names = [
        "active_retrieval",
        "agent_contracts",
        "agent_media",
        "agent_policy",
        "agent_provider",
        "agent_review",
        "agent_runtime",
        "community_gate",
        "gate_dataset",
        "gate_suite",
        "governance_reference",
        "graph_exporter",
        "multi_agent",
        "post_gate",
        "propagation_agent",
        "propagation_context",
        "rag",
        "review_executor",
        "review_queue",
        "selective_student",
        "teacher_silver",
        "trainable_post",
        "user_gate",
        "user_mil",
    ]

    for name in legacy_names:
        legacy = importlib.import_module(f"app.core.risk.{name}")
        canonical = importlib.import_module(f"app.core.review.{name}")
        assert legacy is canonical


def test_review_boundary_is_the_canonical_import_surface():
    review = importlib.import_module("app.core.review")
    assert review.__all__
    assert "agent_review" in review.__all__
    assert "app.core.risk" in importlib.import_module("app.core.review").__doc__


def test_research_runtime_semantic_packages_load():
    discover = _load_package(PROJECT_ROOT / "research" / "coordination_discover", "_test_coordination_discover")
    detect = _load_package(PROJECT_ROOT / "research" / "coordination_detect", "_test_coordination_detect")
    propagation = _load_package(PROJECT_ROOT / "research" / "propagation_analysis", "_test_propagation_analysis")
    teacher = _load_package(PROJECT_ROOT / "research" / "review_teacher", "_test_review_teacher")
    student = _load_package(PROJECT_ROOT / "runtimes" / "review_student", "_test_review_student")

    assert "run_dynamic_discover" in discover.__all__
    assert discover.COORDINATION_DISCOVER_MODEL_VERSION.startswith("coordination_discover-")
    assert detect.run_detect_validation is not None
    assert "runtime" in propagation.__all__
    assert teacher.run_teacher_dag is not None
    assert student.build_distillation_plan is not None


def test_product_backend_does_not_import_reference_runtime_roots():
    app_root = Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []
    path_markers = [
        "MediaCrawler-main",
        "NewsCrawler-main",
        "CooRTweet-master",
    ]

    for path in app_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in path_markers):
            offenders.append(str(path.relative_to(app_root)))

    assert offenders == []


def test_backend_scripts_do_not_embed_reference_runtime_roots():
    scripts_root = Path(__file__).resolve().parents[1] / "scripts"
    path_markers = (
        "MediaCrawler-main",
        "NewsCrawler-main",
        "CooRTweet-master",
    )
    offenders: list[str] = []
    for path in scripts_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in path_markers):
            offenders.append(str(path.relative_to(scripts_root)))

    assert offenders == []


def test_source_and_documentation_do_not_use_numbered_shorthand():
    repo_root = Path(__file__).resolve().parents[3]
    shorthand_prefix = "k" + "t"
    forbidden = re.compile(rf"(?<![A-Za-z0-9]){shorthand_prefix}(?:[123])?(?![A-Za-z0-9])", re.IGNORECASE)
    text_suffixes = {
        ".css",
        ".env",
        ".example",
        ".html",
        ".ini",
        ".js",
        ".json",
        ".md",
        ".py",
        ".scss",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".vue",
        ".yaml",
        ".yml",
    }
    ignored_parts = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "MediaCrawler-main",
        "NewsCrawler-main",
        "CooRTweet-master",
    }
    ignored_prefixes = {
        Path("system") / "output",
    }

    paths = _git_controlled_paths(repo_root)
    offenders: list[str] = []
    for relative_path in paths:
        path = repo_root / relative_path
        if not path.exists() or not path.is_file():
            continue
        if ignored_parts.intersection(relative_path.parts):
            continue
        if any(_is_relative_to(relative_path, prefix) for prefix in ignored_prefixes):
            continue
        if path.suffix.lower() not in text_suffixes and path.name not in {
            ".env.example",
            "AGENTS.md",
            "CONTEXT.md",
            "README.md",
            "UBIQUITOUS_LANGUAGE.md",
        }:
            continue
        if forbidden.search(relative_path.as_posix()):
            offenders.append(relative_path.as_posix())
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if forbidden.search(line):
                offenders.append(f"{relative_path.as_posix()}:{line_number}")
                break

    assert offenders == []


def test_governance_docs_describe_semantic_current_paths():
    repo_root = Path(__file__).resolve().parents[3]
    project_map = (repo_root / "doc" / "engineering" / "project-map.md").read_text(encoding="utf-8")
    system_readme = (repo_root / "system" / "README.md").read_text(encoding="utf-8")
    root_readme = (repo_root / "README.md").read_text(encoding="utf-8")
    glossary = (repo_root / "UBIQUITOUS_LANGUAGE.md").read_text(encoding="utf-8")

    for text in (project_map, system_readme, root_readme, glossary):
        assert "Coordination Discover" in text
        assert "Propagation Analysis" in text
        assert "Event Review Case" in text
        assert "system/research/coordination_discover/" in text
        assert "system/research/coordination_detect/" in text
        assert "system/research/propagation_analysis/" in text
        assert "system/research/review_teacher/" in text
        assert "system/runtimes/review_student/" in text


def test_current_guidance_documents_use_system_boundary():
    repo_root = Path(__file__).resolve().parents[3]
    paths = (
        repo_root / "README.md",
        repo_root / "system" / "README.md",
        repo_root / "CLAUDE.md",
        repo_root / ".cursor" / "rules" / "cogguard-project-context.mdc",
        repo_root / ".cursor" / "rules" / "cogguard-change-sync.mdc",
        repo_root / "doc" / "engineering" / "system-governance.md",
        repo_root / "doc" / "engineering" / "project-map.md",
    )

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "new-system/" not in text
        assert "state_ktN" not in text


def test_product_templates_do_not_expose_internal_runtime_vocabulary():
    repo_root = Path(__file__).resolve().parents[3]
    frontend_root = repo_root / "system" / "frontend" / "src"
    product_templates = (
        frontend_root / "views" / "dashboard" / "index.vue",
        frontend_root / "views" / "risk" / "index.vue",
        frontend_root / "components" / "layout" / "BasicLayout.vue",
        frontend_root / "views" / "login" / "index.vue",
    )
    forbidden = re.compile(
        r"\b(?:student|teacher|agent|checkpoint|artifact|model[_ -]?version|run[_ -]?id|job[_ -]?id|task[_ -]?id)\b",
        re.IGNORECASE,
    )
    offenders: list[str] = []
    for path in product_templates:
        source = path.read_text(encoding="utf-8")
        template = source.split("<script", 1)[0]
        for line_number, line in enumerate(template.splitlines(), start=1):
            if forbidden.search(line):
                offenders.append(f"{path.relative_to(repo_root).as_posix()}:{line_number}")

    assert offenders == []


def test_frontend_has_no_preview_product_entrypoint():
    repo_root = Path(__file__).resolve().parents[3]
    frontend_root = repo_root / "system" / "frontend" / "src"
    offenders: list[str] = []
    for path in frontend_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".ts", ".vue"}:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "/preview" in line.lower():
                offenders.append(f"{path.relative_to(repo_root).as_posix()}:{line_number}")

    assert offenders == []


def _load_package(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(
        module_name,
        path / "__init__.py",
        submodule_search_locations=[str(path)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _git_controlled_paths(repo_root: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [Path(line) for line in output.splitlines() if line.strip()]


def _is_relative_to(path: Path, prefix: Path) -> bool:
    try:
        path.relative_to(prefix)
    except ValueError:
        return False
    return True
