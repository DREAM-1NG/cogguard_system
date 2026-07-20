from __future__ import annotations

import importlib
import importlib.util
import re
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
    assert "kt3_agent_review" in review.__all__
    assert "detect_groups" in coordination_baseline.__all__


def test_legacy_backend_imports_are_thin_compatibility_aliases():
    canonical_review = importlib.import_module("app.core.review.kt3_agent_review")
    legacy_risk = importlib.import_module("app.core.risk.kt3_agent_review")
    canonical_coordination = importlib.import_module("app.core.coordination_baseline.detector")
    legacy_coordination = importlib.import_module("app.core.coordination.detector")

    assert legacy_risk.OpenAICompatibleAgentProvider is canonical_review.OpenAICompatibleAgentProvider
    assert legacy_risk.OpenAICompatibleConfig is canonical_review.OpenAICompatibleConfig
    assert legacy_coordination.detect_groups is canonical_coordination.detect_groups


def test_research_runtime_semantic_packages_and_legacy_aliases_load():
    discover = _load_package(PROJECT_ROOT / "research" / "coordination_discover", "_test_coordination_discover")
    detect = _load_package(PROJECT_ROOT / "research" / "coordination_detect", "_test_coordination_detect")
    legacy_kt1 = _load_package(PROJECT_ROOT / "research" / "kt1", "_test_legacy_kt1")
    teacher = _load_package(PROJECT_ROOT / "research" / "review_teacher", "_test_review_teacher")
    legacy_teacher = _load_package(PROJECT_ROOT / "research" / "kt3_teacher", "_test_legacy_kt3_teacher")
    student = _load_package(PROJECT_ROOT / "runtimes" / "review_student", "_test_review_student")
    legacy_student = _load_package(PROJECT_ROOT / "runtimes" / "kt3_student", "_test_legacy_kt3_student")

    assert "run_dynamic_discover" in discover.__all__
    assert detect.run_detect_validation is not None
    assert legacy_kt1.KT1_MODEL_VERSION == discover.KT1_MODEL_VERSION
    assert legacy_teacher.TeacherDAG is not None
    assert teacher.run_teacher_dag is not None
    assert legacy_student.StudentRuntime is not None
    assert student.build_distillation_plan is not None


def test_product_backend_does_not_import_legacy_package_or_runtime_roots():
    app_root = Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []
    import_patterns = [
        re.compile(r"^\s*(?:from|import)\s+app\.core\.risk\b", re.MULTILINE),
        re.compile(r"^\s*(?:from|import)\s+app\.core\.coordination(?:\s|\.|$)", re.MULTILINE),
    ]
    path_markers = [
        'PROJECT_ROOT / "research" / "kt1"',
        'SYSTEM_ROOT / "research" / "kt2"',
        'SYSTEM_ROOT / "research" / "kt3_teacher"',
        'SYSTEM_ROOT / "runtimes" / "kt3_student"',
        "system/research/kt1",
        "system/research/kt2",
        "system/research/kt3_teacher",
        "system/runtimes/kt3_student",
        "MediaCrawler-main",
        "NewsCrawler-main",
        "CooRTweet-master",
    ]
    compatibility_roots = {
        app_root / "core" / "risk",
        app_root / "core" / "coordination",
    }

    for path in app_root.rglob("*.py"):
        if "__pycache__" in path.parts or _under_any(path, compatibility_roots):
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in import_patterns) or any(marker in text for marker in path_markers):
            offenders.append(str(path.relative_to(app_root)))

    assert offenders == []


def test_governance_docs_describe_semantic_current_paths():
    repo_root = Path(__file__).resolve().parents[3]
    project_map = (repo_root / "doc" / "engineering" / "project-map.md").read_text(encoding="utf-8")
    system_readme = (repo_root / "system" / "README.md").read_text(encoding="utf-8")
    root_readme = (repo_root / "README.md").read_text(encoding="utf-8")

    for text in (project_map, system_readme, root_readme):
        assert "system/research/coordination_discover/" in text
        assert "system/research/coordination_detect/" in text
        assert "system/research/propagation_analysis/" in text
        assert "system/research/review_teacher/" in text
        assert "system/runtimes/review_student/" in text

    current_functional_map = project_map.split("## Current Functional Map", 1)[1].split(
        "## Runtime Boundary Policy",
        1,
    )[0]
    system_tree = system_readme.split("## 环境要求", 1)[0]
    forbidden_current_paths = [
        "kt2/",
        "kt3_teacher/",
        "kt3_student/",
    ]

    for text in (current_functional_map, system_tree):
        assert all(path not in text for path in forbidden_current_paths)


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


def _under_any(path: Path, roots: set[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False
