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


def test_canonical_governance_sources_use_method_names_not_numbered_shorthand():
    root = Path(__file__).resolve().parents[3]
    canonical_sources = [
        root / "UBIQUITOUS_LANGUAGE.md",
        root / "doc" / "engineering" / "project-map.md",
        root / "doc" / "engineering" / "system-governance.md",
    ]
    shorthand_pattern = re.compile("".join(["K", "T", "[123]"]) + "|" + "".join(["k", "t", "[123]"]))

    for path in canonical_sources:
        assert shorthand_pattern.search(path.read_text(encoding="utf-8")) is None, path


def test_governance_boundaries_have_unique_adrs_and_explicit_public_modules():
    root = Path(__file__).resolve().parents[3]
    adr_numbers = []
    for path in (root / "docs" / "adr").glob("*.md"):
        match = re.match(r"^(\d{4})-", path.name)
        assert match, path
        adr_numbers.append(match.group(1))
    assert len(adr_numbers) == len(set(adr_numbers))

    core = importlib.import_module("app.core")
    coordination_detect = importlib.import_module("app.core.coordination_detect")
    coordination_discover = importlib.import_module("app.core.coordination_discover")
    crawler = importlib.import_module("app.core.crawler")
    propagation_analysis = importlib.import_module("app.core.propagation_analysis")

    assert "coordination_detect" in core.__all__
    assert "coordination_discover" in core.__all__
    assert "review" in core.__all__
    assert "risk" in core.__all__
    assert "detect_groups" in coordination_detect.__all__
    assert "generate_coordinated_network" in coordination_discover.__all__
    assert "graph_to_dict" in coordination_discover.__all__
    assert "run_dyna_colm_discover" in coordination_discover.__all__
    assert "run_dyna_colm_detect" in coordination_detect.__all__
    assert "run_china_pretrained_detect" in coordination_detect.__all__
    assert "crawler" in core.__all__
    assert "propagation_analysis" in core.__all__
    assert "predict_trend" in propagation_analysis.__all__
    assert "build_propagation_graph" in propagation_analysis.__all__
    assert "social" in crawler.__all__
    assert "news" in crawler.__all__


def test_public_package_initializers_use_readable_boundary_docstrings():
    root = Path(__file__).resolve().parents[3]
    package_inits = [
        root / "system" / "backend" / "app" / "core" / "__init__.py",
        root / "system" / "backend" / "app" / "core" / "coordination_detect" / "__init__.py",
        root / "system" / "backend" / "app" / "core" / "coordination_discover" / "__init__.py",
        root / "system" / "backend" / "app" / "core" / "crawler" / "__init__.py",
        root / "system" / "backend" / "app" / "core" / "coordination" / "__init__.py",
        root / "system" / "backend" / "app" / "core" / "propagation" / "__init__.py",
        root / "system" / "backend" / "app" / "core" / "propagation_analysis" / "__init__.py",
        root / "system" / "backend" / "app" / "core" / "review" / "__init__.py",
    ]
    mojibake_markers = ("鏍", "鍖", "鐖", "鍗", "浼", "銆", "€?", "鈥")

    for path in package_inits:
        text = path.read_text(encoding="utf-8")
        assert text.startswith('"""'), path
        assert not any(marker in text for marker in mojibake_markers), path


def test_coordination_method_facades_alias_current_baseline_implementation():
    baseline = importlib.import_module("app.core.coordination")
    detect = importlib.import_module("app.core.coordination_detect")
    discover = importlib.import_module("app.core.coordination_discover")

    assert detect.detect_groups is baseline.detect_groups
    assert detect.flag_speed_share is baseline.flag_speed_share
    assert detect.account_stats is baseline.account_stats
    assert detect.group_stats is baseline.group_stats
    assert discover.generate_coordinated_network is baseline.generate_coordinated_network
    assert discover.graph_to_dict.__module__ == "app.core.coordination.network"
    assert discover.run_dyna_colm_characterize is baseline.run_dyna_colm_characterize
    assert "app.core.coordination" in (detect.__doc__ or "")
    assert "app.core.coordination" in (discover.__doc__ or "")
    assert "independent" in (detect.__doc__ or "")
    assert "duplicating" in (discover.__doc__ or "")


def test_current_coordination_service_uses_canonical_facades():
    root = Path(__file__).resolve().parents[3]
    service_path = root / "system" / "backend" / "app" / "services" / "coordination_service.py"
    model_service_path = root / "system" / "backend" / "app" / "services" / "coordination_model_service.py"
    service_text = service_path.read_text(encoding="utf-8")
    model_service_text = model_service_path.read_text(encoding="utf-8")

    assert "from app.core.coordination_detect import account_stats, detect_groups, group_stats" in service_text
    assert "from app.core.coordination_discover import generate_coordinated_network, graph_to_dict" in service_text
    assert "from app.core.coordination_detect import (" in model_service_text
    assert "from app.core.coordination_discover import (" in model_service_text
    for text in (service_text, model_service_text):
        assert "from app.core.coordination import" not in text
        assert "from app.core.coordination." not in text


def test_propagation_analysis_facade_aliases_current_kt2_implementation():
    current = importlib.import_module("app.core.propagation")
    llm_context = importlib.import_module("app.core.propagation.llm_context")
    regime_model = importlib.import_module("app.core.propagation.regime_model")
    trend_predictor = importlib.import_module("app.core.propagation.trend_predictor")
    ts_features = importlib.import_module("app.core.propagation.ts_features")
    facade = importlib.import_module("app.core.propagation_analysis")

    assert facade.build_propagation_graph is current.build_propagation_graph
    assert facade.predict_trend is trend_predictor.predict_trend
    assert facade.extract_ts_features is ts_features.extract_ts_features
    assert facade.extract_events is llm_context.extract_events
    assert facade.compute_regime_posterior is regime_model.compute_regime_posterior
    assert facade.mixture_forecast is regime_model.mixture_forecast
    assert "app.core.propagation" in (facade.__doc__ or "")
    assert "app.core.propagation_legacy" in (facade.__doc__ or "")
    assert "independent business logic" in (facade.__doc__ or "")


def test_current_propagation_callers_use_canonical_facade():
    root = Path(__file__).resolve().parents[3]
    caller_paths = [
        root / "system" / "backend" / "app" / "services" / "propagation_service.py",
        root / "system" / "backend" / "app" / "core" / "coordination" / "characterization.py",
    ]
    legacy_imports = (
        "from app.core.propagation import",
        "from app.core.propagation.trend_predictor import",
        "from app.core.propagation_legacy import",
    )

    for path in caller_paths:
        text = path.read_text(encoding="utf-8")
        assert "from app.core.propagation_analysis import build_propagation_graph" in text, path
        assert not any(import_line in text for import_line in legacy_imports), path


def test_review_facade_is_thin_risk_review_compatibility_layer():
    review = importlib.import_module("app.core.review")
    risk = importlib.import_module("app.core.risk")
    media = importlib.import_module("app.core.risk.kt3_agent_media")

    assert review.__all__ == risk.__all__
    assert review.kt3_agent_media is media
    assert "kt3_agent_media" in dir(review)
    assert "kt3_agent_review" in review.__all__
    assert "app.core.risk" in (review.__doc__ or "")
    assert "business logic" in (review.__doc__ or "")


def test_current_risk_review_product_callers_use_canonical_facade():
    root = Path(__file__).resolve().parents[3]
    caller_paths = [
        root / "system" / "backend" / "app" / "api" / "v1" / "risk.py",
        root / "system" / "backend" / "app" / "services" / "kt3_system_service.py",
        root / "system" / "backend" / "app" / "services" / "risk_service.py",
        root / "system" / "backend" / "app" / "tasks" / "kt3_tasks.py",
    ]

    for path in caller_paths:
        text = path.read_text(encoding="utf-8")
        assert "from app.core import review" in text, path
        assert "from app.core.risk" not in text, path


def test_kt3_trainable_post_exposes_split_boundaries_and_lazily_resolves_moved_symbols():
    agent_review = importlib.import_module("app.core.risk.kt3_agent_review")
    contracts = importlib.import_module("app.core.risk.kt3_agent_contracts")
    media = importlib.import_module("app.core.risk.kt3_agent_media")
    provider = importlib.import_module("app.core.risk.kt3_agent_provider")
    risk = importlib.import_module("app.core.risk")
    runtime = importlib.import_module("app.core.risk.kt3_agent_runtime")
    trainable = importlib.import_module("app.core.risk.kt3_trainable_post")
    teacher = importlib.import_module("app.core.risk.kt3_teacher_silver")
    student = importlib.import_module("app.core.risk.kt3_selective_student")

    assert "AGENT_REPORT_SECTIONS" in contracts.__all__
    assert "build_agent_system_prompt" in contracts.__all__
    assert agent_review.AGENT_REPORT_SECTIONS is contracts.AGENT_REPORT_SECTIONS
    assert "kt3_agent_media" in risk.__all__
    assert "build_media_inputs_for_post" in media.__all__
    assert "build_provider_input_bundle_for_agent" in media.__all__
    assert agent_review._provider_should_receive_media("MultimodalConsistencyAgent") is True
    assert "OpenAICompatibleAgentProvider" in provider.__all__
    assert agent_review.OpenAICompatibleAgentProvider is provider.OpenAICompatibleAgentProvider
    assert agent_review.OpenAICompatibleConfig is provider.OpenAICompatibleConfig
    assert "resolve_runtime_mode" in runtime.__all__
    assert agent_review.AGENT_ORDER is runtime.AGENT_ORDER
    assert agent_review._normalize_agent_names(["ClaimEvidence", "PostHarm"]) == [
        "PostHarmAgent",
        "ClaimEvidenceAgent",
    ]
    assert "write_jsonl" in getattr(trainable, "__all__", []) or hasattr(trainable, "write_jsonl")
    assert "build_teacher_silver_record" in teacher.__all__
    assert "SelectiveStudentEncoder" in student.__all__
    assert hasattr(trainable, "build_teacher_silver_record")
    assert hasattr(trainable, "SelectiveStudentEncoder")
    assert hasattr(trainable, "build_selective_student_targets")
