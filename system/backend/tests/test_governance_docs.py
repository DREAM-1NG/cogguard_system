from __future__ import annotations

import importlib
from pathlib import Path


def test_governance_docs_and_glossary_are_present_and_cross_linked():
    root = Path(__file__).resolve().parents[3]
    files = {
        "glossary": root / "UBIQUITOUS_LANGUAGE.md",
        "system_governance": root / "doc" / "engineering" / "system-governance.md",
        "adr": root / "docs" / "adr" / "0002-system-governance-and-documentation-sync.md",
        "agents": root / "AGENTS.md",
        "claude": root / "CLAUDE.md",
        "readme": root / "README.md",
        "system_readme": root / "system" / "README.md",
        "project_map": root / "doc" / "engineering" / "project-map.md",
        "environment_setup": root / "doc" / "engineering" / "environment-setup.md",
        "data_contract_mediacrawler": root / "doc" / "engineering" / "data-contract-mediacrawler.md",
        "research_overview": root / "doc" / "research" / "key-technology-background" / "overview.md",
        "kt1_background": root / "doc" / "research" / "key-technology-background" / "coordination-detection.md",
        "kt2_background": root / "doc" / "research" / "key-technology-background" / "propagation-analysis.md",
        "kt3_background": root / "doc" / "research" / "key-technology-background" / "risk-disarm.md",
    }

    for path in files.values():
        assert path.exists(), path

    glossary = files["glossary"].read_text(encoding="utf-8")
    system_governance = files["system_governance"].read_text(encoding="utf-8")
    adr = files["adr"].read_text(encoding="utf-8")
    agents = files["agents"].read_text(encoding="utf-8")
    claude = files["claude"].read_text(encoding="utf-8")
    readme = files["readme"].read_text(encoding="utf-8")
    system_readme = files["system_readme"].read_text(encoding="utf-8")
    project_map = files["project_map"].read_text(encoding="utf-8")

    for text in (glossary, system_governance, adr, agents, claude, readme, system_readme, project_map):
        assert "system/" in text

    assert "UBIQUITOUS_LANGUAGE.md" in agents
    assert "UBIQUITOUS_LANGUAGE.md" in claude
    assert "UBIQUITOUS_LANGUAGE.md" in readme
    assert "doc/engineering/system-governance.md" in agents
    assert "doc/engineering/system-governance.md" in claude
    assert "docs/adr/" in readme
    assert "docs/adr/" in project_map
    assert "Documentation Sync" in system_governance
    assert "Documentation Sync" in agents
    assert "Coordination Discover" in glossary
    assert "Coordination Detect" in glossary
    assert "Coordination Discover" in system_governance
    assert "Coordination Detect" in system_governance

    current_facing_docs = [
        files["agents"],
        files["claude"],
        files["readme"],
        files["system_readme"],
        files["system_governance"],
        files["environment_setup"],
        files["data_contract_mediacrawler"],
        files["research_overview"],
        files["kt1_background"],
        files["kt2_background"],
        files["kt3_background"],
    ]
    for path in current_facing_docs:
        assert "new-system/" not in path.read_text(encoding="utf-8"), path


def test_kt3_trainable_post_exposes_split_boundaries_and_lazily_resolves_moved_symbols():
    trainable = importlib.import_module("app.core.risk.kt3_trainable_post")
    teacher = importlib.import_module("app.core.risk.kt3_teacher_silver")
    student = importlib.import_module("app.core.risk.kt3_selective_student")

    assert "write_jsonl" in getattr(trainable, "__all__", []) or hasattr(trainable, "write_jsonl")
    assert "build_teacher_silver_record" in teacher.__all__
    assert "SelectiveStudentEncoder" in student.__all__
    assert hasattr(trainable, "build_teacher_silver_record")
    assert hasattr(trainable, "SelectiveStudentEncoder")
    assert hasattr(trainable, "build_selective_student_targets")
