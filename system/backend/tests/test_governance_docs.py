from __future__ import annotations

import importlib
import re
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


def test_governance_boundaries_have_unique_adrs_and_explicit_public_modules():
    root = Path(__file__).resolve().parents[3]
    adr_numbers = []
    for path in (root / "docs" / "adr").glob("*.md"):
        match = re.match(r"^(\d{4})-", path.name)
        assert match, path
        adr_numbers.append(match.group(1))
    assert len(adr_numbers) == len(set(adr_numbers))

    core = importlib.import_module("app.core")
    crawler = importlib.import_module("app.core.crawler")

    assert "risk" in core.__all__
    assert "crawler" in core.__all__
    assert "social" in crawler.__all__
    assert "news" in crawler.__all__


def test_kt3_trainable_post_exposes_split_boundaries_and_lazily_resolves_moved_symbols():
    agent_review = importlib.import_module("app.core.risk.kt3_agent_review")
    contracts = importlib.import_module("app.core.risk.kt3_agent_contracts")
    provider = importlib.import_module("app.core.risk.kt3_agent_provider")
    trainable = importlib.import_module("app.core.risk.kt3_trainable_post")
    teacher = importlib.import_module("app.core.risk.kt3_teacher_silver")
    student = importlib.import_module("app.core.risk.kt3_selective_student")

    assert "AGENT_REPORT_SECTIONS" in contracts.__all__
    assert "build_agent_system_prompt" in contracts.__all__
    assert agent_review.AGENT_REPORT_SECTIONS is contracts.AGENT_REPORT_SECTIONS
    assert "OpenAICompatibleAgentProvider" in provider.__all__
    assert agent_review.OpenAICompatibleAgentProvider is provider.OpenAICompatibleAgentProvider
    assert agent_review.OpenAICompatibleConfig is provider.OpenAICompatibleConfig
    assert "write_jsonl" in getattr(trainable, "__all__", []) or hasattr(trainable, "write_jsonl")
    assert "build_teacher_silver_record" in teacher.__all__
    assert "SelectiveStudentEncoder" in student.__all__
    assert hasattr(trainable, "build_teacher_silver_record")
    assert hasattr(trainable, "SelectiveStudentEncoder")
    assert hasattr(trainable, "build_selective_student_targets")
