from __future__ import annotations

import dataclasses
import importlib.util
import sys
import types

import pytest

from app.config import PROJECT_ROOT


def _load_experiments():
    research_name = "research"
    research_dir = PROJECT_ROOT / "research"
    if research_name not in sys.modules:
        research_package = types.ModuleType(research_name)
        research_package.__path__ = [str(research_dir)]
        sys.modules[research_name] = research_package

    package_name = "research.coordination_experiments"
    cached = sys.modules.get(package_name)
    if cached is not None:
        return cached
    package_dir = research_dir / "coordination_experiments"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def test_public_coordination_benchmark_registry_tracks_requested_sota_methods():
    module = _load_experiments()
    registry = module.default_public_benchmark_registry()

    assert set(registry.method_ids) == {
        "tgat",
        "tgn",
        "dygformer",
        "temporal_multiplex_multislice",
        "polya_filter",
        "noise_corrected_backbone",
        "ecm_backbone",
        "flow_stability",
    }
    assert {
        "iohunter",
        "seckin_2024_labeled_io",
        "twitter_state_backed_io_archive",
        "guo_vosoughi_2022_io_controls",
        "tgb_temporal_graph_benchmark",
        "large_engagement_networks",
        "astroturf_legitimate_classification",
    }.issubset(set(registry.dataset_ids))
    with pytest.raises(dataclasses.FrozenInstanceError):
        registry.dataset("iohunter").has_observed_timestamps = True
    with pytest.raises(AttributeError):
        registry.new_field = True


def test_temporal_sota_is_blocked_on_iohunter_processed_but_not_static_backbones():
    module = _load_experiments()
    registry = module.default_public_benchmark_registry()

    for method_id in ("tgat", "tgn", "dygformer", "temporal_multiplex_multislice", "flow_stability"):
        feasibility = registry.feasibility("iohunter", method_id)
        assert feasibility.status == "blocked"
        assert "observed_timestamps" in feasibility.missing_signals

    for method_id in ("polya_filter", "noise_corrected_backbone", "ecm_backbone"):
        feasibility = registry.feasibility("iohunter", method_id)
        assert feasibility.status == "proxy_only"
        assert feasibility.missing_signals == ()
        assert "account-recovery proxy" in feasibility.reason


def test_public_io_datasets_require_adapters_before_claims_are_made():
    module = _load_experiments()
    registry = module.default_public_benchmark_registry()

    seckin_tgn = registry.feasibility("seckin_2024_labeled_io", "tgn")
    assert seckin_tgn.status == "adapter_required"
    assert seckin_tgn.missing_signals == ()

    archive_flow = registry.feasibility("twitter_state_backed_io_archive", "flow_stability")
    assert archive_flow.status == "adapter_required"
    assert archive_flow.missing_signals == ()

    tgb_tgn = registry.feasibility("tgb_temporal_graph_benchmark", "tgn")
    assert tgb_tgn.status == "method_only"
    assert "no coordination labels" in tgb_tgn.reason


def test_local_len_and_astroturf_datasets_have_stage2_but_not_temporal_status():
    module = _load_experiments()
    registry = module.default_public_benchmark_registry()

    len_dataset = registry.dataset("large_engagement_networks")
    assert len_dataset.access_mode == "local_available"
    assert "graph_labels" in len_dataset.available_signals
    assert "binary_detection_gold" in len_dataset.available_signals
    assert "harmfulness_gold" not in len_dataset.available_signals
    assert len_dataset.capability.supports_binary_coordination_detection is True
    assert len_dataset.capability.supports_harmful_cib_detection is False
    assert registry.feasibility("large_engagement_networks", "polya_filter").status == "proxy_only"
    assert registry.feasibility("large_engagement_networks", "tgn").status == "blocked"

    astroturf_dataset = registry.dataset("astroturf_legitimate_classification")
    assert astroturf_dataset.access_mode == "local_available"
    assert "handcrafted_feature_table" in astroturf_dataset.available_signals
    assert "binary_detection_gold" in astroturf_dataset.available_signals
    assert "harmfulness_gold" not in astroturf_dataset.available_signals
    assert astroturf_dataset.capability.supports_binary_coordination_detection is True
    assert astroturf_dataset.capability.supports_harmful_cib_detection is False
    assert registry.feasibility("astroturf_legitimate_classification", "polya_filter").status == "blocked"
    assert registry.feasibility("astroturf_legitimate_classification", "tgn").status == "blocked"
