from __future__ import annotations

import dataclasses
import importlib.util
import math
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

from app.config import PROJECT_ROOT


def _load_stage1_modules():
    package_name = "_test_cogguard_coordination_stage1_tsgs"
    package_dir = PROJECT_ROOT / "research" / "coordination_discover" / "stage1"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_dir)]
        sys.modules[package_name] = package

    loaded = []
    for child_name in ("events", "tsgs"):
        module_name = f"{package_name}.{child_name}"
        module = sys.modules.get(module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(module_name, package_dir / f"{child_name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        loaded.append(module)
    return tuple(loaded)


def _coordinated_events(events_module, account_count: int = 6):
    start = datetime(2026, 8, 7, tzinfo=timezone.utc)
    events = []
    for account_index in range(account_count):
        account_id = f"account-{account_index:02d}"
        for offset, object_id in enumerate(("url-a", "url-b", "url-c")):
            events.append(
                events_module.CoordinationEvent(
                    account_id=account_id,
                    relation="shared_url",
                    object_id=object_id,
                    observed_at=start + timedelta(seconds=offset * 10),
                    weight=1.0,
                    evidence_ref=f"evidence:{account_id}:{object_id}",
                )
            )
    return events


def test_coordination_event_has_exact_label_free_schema_and_rejects_label_keys():
    events_module, _ = _load_stage1_modules()
    assert [field.name for field in dataclasses.fields(events_module.CoordinationEvent)] == [
        "account_id",
        "relation",
        "object_id",
        "observed_at",
        "weight",
        "evidence_ref",
    ]
    valid = {
        "account_id": "account-a",
        "relation": "shared_url",
        "object_id": "url-a",
        "observed_at": "2026-08-07T00:00:00Z",
        "weight": 1.0,
        "evidence_ref": "evidence:1",
    }

    event = events_module.CoordinationEvent.from_mapping(valid)

    assert event.observed_at == datetime(2026, 8, 7, tzinfo=timezone.utc)
    for forbidden in ("label", "risk", "verdict", "class", "bot", "harmful"):
        with pytest.raises(ValueError, match="forbidden label-bearing fields"):
            events_module.CoordinationEvent.from_mapping({**valid, forbidden: "positive"})


def test_runtime_lsh_caps_buckets_and_never_calls_dense_reference(monkeypatch: pytest.MonkeyPatch):
    events_module, tsgs_module = _load_stage1_modules()
    events = _coordinated_events(events_module, account_count=12)

    def fail_dense_reference(*_args, **_kwargs):
        raise AssertionError("runtime path called the all-pairs reference builder")

    monkeypatch.setattr(tsgs_module, "build_dense_reference_graph", fail_dense_reference)
    result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(
            seed=31,
            hyperplane_count=12,
            band_size=3,
            bucket_cap=3,
            sampling_multiplier=2.0,
        )
    ).fit_transform(events)

    assert result.full_pair_count == 66
    assert 0 < result.candidate_pair_count < result.full_pair_count
    assert result.candidate_reduction == pytest.approx(1.0 - result.candidate_pair_count / 66)
    assert result.bucket_diagnostics.capped_bucket_count > 0
    assert result.bucket_diagnostics.max_bucket_size == 12
    assert result.bucket_diagnostics.dropped_membership_count > 0


def test_exact_cosine_is_scored_only_for_lsh_candidate_pairs(monkeypatch: pytest.MonkeyPatch):
    events_module, tsgs_module = _load_stage1_modules()
    events = _coordinated_events(events_module, account_count=10)
    original = tsgs_module._exact_cosine
    scored_pairs = []

    def recording_cosine(left, right):
        scored_pairs.append((left, right))
        return original(left, right)

    monkeypatch.setattr(tsgs_module, "_exact_cosine", recording_cosine)
    result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(seed=7, hyperplane_count=8, band_size=2, bucket_cap=3)
    ).fit_transform(events)

    assert len(scored_pairs) == result.candidate_pair_count
    assert result.candidate_pair_count < result.full_pair_count


def test_seed_reproduces_candidates_sampled_edges_and_empirical_audit():
    events_module, tsgs_module = _load_stage1_modules()
    events = _coordinated_events(events_module)
    config = tsgs_module.TSGSConfig(
        seed=19,
        hyperplane_count=8,
        band_size=1,
        bucket_cap=32,
        sampling_multiplier=1.2,
        audit_vector_count=32,
        audit_tolerance=3.0,
    )

    first = tsgs_module.TemporalSketchGraphSparsifier(config).fit_transform(events)
    second = tsgs_module.TemporalSketchGraphSparsifier(config).fit_transform(reversed(events))

    assert first.candidate_graph_edges == second.candidate_graph_edges
    assert first.sampled_edges == second.sampled_edges
    assert first.audit == second.audit
    assert first.sampled_edges
    assert all(math.isfinite(edge.weight) and edge.weight > 0.0 for edge in first.sampled_edges)


def test_small_candidate_graph_passes_empirical_quadratic_form_audit():
    events_module, tsgs_module = _load_stage1_modules()
    result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(
            seed=5,
            hyperplane_count=8,
            band_size=1,
            bucket_cap=32,
            sampling_multiplier=2.0,
            audit_vector_count=64,
            audit_tolerance=1e-10,
            exact_resistance_max_nodes=20,
        )
    ).fit_transform(_coordinated_events(events_module, account_count=5))

    assert result.resistance_backend == "exact_laplacian_pseudoinverse"
    assert result.guarantee_scope == "candidate_graph_only"
    assert result.audit.empirical is True
    assert result.audit.reference_graph == "candidate_graph"
    assert result.audit.passed is True
    assert result.audit.observed_min_ratio == pytest.approx(1.0)
    assert result.audit.observed_max_ratio == pytest.approx(1.0)
    assert result.audit.observed_min_distortion == pytest.approx(0.0)
    assert result.audit.observed_max_distortion == pytest.approx(0.0)


def test_large_candidate_graph_names_approximation_and_records_diagnostics():
    events_module, tsgs_module = _load_stage1_modules()
    result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(
            seed=11,
            hyperplane_count=8,
            band_size=1,
            bucket_cap=32,
            sampling_multiplier=2.0,
            exact_resistance_max_nodes=3,
        )
    ).fit_transform(_coordinated_events(events_module, account_count=6))

    assert result.resistance_backend == "diagonal_degree_resistance_approximation"
    assert result.guarantee_scope == "candidate_graph_only"
    assert result.memory_estimate_bytes > 0
    assert result.timings.total_seconds >= result.timings.vectorization_seconds >= 0.0
    assert result.bucket_diagnostics.bucket_count > 0
    assert result.audit.sample_count > 0


def test_dense_reference_builder_is_explicitly_separate_and_all_pairs():
    events_module, tsgs_module = _load_stage1_modules()
    edges = tsgs_module.build_dense_reference_graph(
        _coordinated_events(events_module, account_count=4),
        tsgs_module.TSGSConfig(min_cosine_similarity=0.0),
    )

    assert len(edges) == 6
    assert all(edge.weight == pytest.approx(1.0) for edge in edges)


def test_empty_snapshot_returns_an_auditable_empty_candidate_graph():
    _, tsgs_module = _load_stage1_modules()

    result = tsgs_module.TemporalSketchGraphSparsifier().fit_transform([])

    assert result.account_ids == ()
    assert result.candidate_pair_count == result.full_pair_count == 0
    assert result.candidate_graph_edges == result.sampled_edges == ()
    assert result.resistance_backend == "exact_laplacian_pseudoinverse"
    assert result.guarantee_scope == "candidate_graph_only"
    assert result.audit.sample_count == 0
    assert result.audit.passed is True


def test_zero_weight_event_preserves_its_account_row_and_full_pair_count():
    events_module, tsgs_module = _load_stage1_modules()
    observed_at = datetime(2026, 8, 7, tzinfo=timezone.utc)
    events = [
        events_module.CoordinationEvent("account-active", "shared", "object-a", observed_at, 1.0, "e:1"),
        events_module.CoordinationEvent("account-zero", "shared", "object-b", observed_at, 0.0, "e:2"),
    ]

    result = tsgs_module.TemporalSketchGraphSparsifier().fit_transform(events)

    assert result.account_ids == ("account-active", "account-zero")
    assert result.full_pair_count == 1
    assert result.candidate_graph_edges == ()
