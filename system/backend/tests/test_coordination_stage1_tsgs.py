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


def test_coordination_event_accepts_only_typed_canonical_relations():
    events_module, _ = _load_stage1_modules()
    permitted = {
        "shared_url",
        "shared_domain",
        "shared_hashtag",
        "shared_keyword",
        "shared_entity",
        "shared_target",
        "discussion_target",
        "repost_target",
        "reply_target",
        "mention_target",
        "near_duplicate",
        "native_relation",
        "higher_order",
    }
    assert events_module.CANONICAL_COORDINATION_RELATIONS == frozenset(permitted)
    observed_at = datetime(2026, 8, 7, tzinfo=timezone.utc)
    for relation in sorted(permitted):
        event = events_module.CoordinationEvent(
            "account-a", relation, "object-a", observed_at, 1.0, "evidence:1"
        )
        assert event.relation == relation

    base = {
        "account_id": "account-a",
        "object_id": "object-a",
        "observed_at": "2026-08-07T00:00:00Z",
        "weight": 1.0,
        "evidence_ref": "evidence:1",
    }
    for relation in (
        "harmful",
        "bot",
        "faction",
        "risk",
        "stance",
        "intent",
        "class",
        "arbitrary_relation",
    ):
        with pytest.raises(ValueError, match="canonical label-free relation"):
            events_module.CoordinationEvent(
                "account-a", relation, "object-a", observed_at, 1.0, "evidence:1"
            )
        with pytest.raises(ValueError, match="canonical label-free relation"):
            events_module.CoordinationEvent.from_mapping({**base, "relation": relation})


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


def test_p_one_identity_sample_passes_empirical_quadratic_form_audit():
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

    assert result.resistance_backend == "exact_component_grounded_laplacian_solve"
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
    assert result.resistance_backend == "exact_component_grounded_laplacian_solve"
    assert result.guarantee_scope == "candidate_graph_only"
    assert result.audit.sample_count == 0
    assert result.audit.status == "trivial_empty_graph"
    assert result.audit.passed is True
    assert result.audit.observed_min_ratio is None
    assert result.audit.observed_max_ratio is None
    assert result.audit.observed_min_distortion is None
    assert result.audit.observed_max_distortion is None


def test_zero_weight_event_preserves_its_account_row_and_full_pair_count():
    events_module, tsgs_module = _load_stage1_modules()
    observed_at = datetime(2026, 8, 7, tzinfo=timezone.utc)
    events = [
        events_module.CoordinationEvent("account-active", "shared_keyword", "object-a", observed_at, 1.0, "e:1"),
        events_module.CoordinationEvent("account-zero", "shared_keyword", "object-b", observed_at, 0.0, "e:2"),
    ]

    result = tsgs_module.TemporalSketchGraphSparsifier().fit_transform(events)

    assert result.account_ids == ("account-active", "account-zero")
    assert result.full_pair_count == 1
    assert result.candidate_graph_edges == ()


def test_exact_resistance_solves_disconnected_components_without_pseudoinverse(
    monkeypatch: pytest.MonkeyPatch,
):
    _, tsgs_module = _load_stage1_modules()
    edges = (
        tsgs_module.WeightedEdge("account-a", "account-b", 2.0),
        tsgs_module.WeightedEdge("account-c", "account-d", 0.5),
    )

    def fail_pseudoinverse(*_args, **_kwargs):
        raise AssertionError("exact resistance used np.linalg.pinv")

    monkeypatch.setattr(tsgs_module.np.linalg, "pinv", fail_pseudoinverse)

    resistances = tsgs_module._exact_effective_resistances(
        ("account-a", "account-b", "account-c", "account-d", "account-isolated"),
        edges,
        condition_limit=1e12,
    )

    assert resistances == pytest.approx((0.5, 2.0))


def test_numerically_ill_conditioned_component_uses_named_fallback():
    _, tsgs_module = _load_stage1_modules()
    edges = (
        tsgs_module.WeightedEdge("account-a", "account-b", 1.0),
        tsgs_module.WeightedEdge("account-b", "account-c", 1e-15),
    )
    config = tsgs_module.TSGSConfig(
        seed=23,
        sampling_multiplier=0.5,
        exact_resistance_max_nodes=3,
        exact_resistance_condition_limit=1e8,
    )

    sampled, backend = tsgs_module._sample_candidate_graph(
        ("account-a", "account-b", "account-c"), edges, config
    )

    assert backend == "numerical_fallback_diagonal_degree_resistance_approximation"
    assert all(math.isfinite(edge.weight) and edge.weight > 0.0 for edge in sampled)


def test_controlled_nontrivial_sampling_retains_strict_subset_with_inverse_probability_weights():
    _, tsgs_module = _load_stage1_modules()
    edges = (
        tsgs_module.WeightedEdge("account-a", "account-b", 1.0),
        tsgs_module.WeightedEdge("account-b", "account-c", 1.0),
        tsgs_module.WeightedEdge("account-c", "account-d", 1.0),
    )
    config = tsgs_module.TSGSConfig(
        seed=17,
        sampling_multiplier=0.4,
        exact_resistance_max_nodes=4,
    )
    probability = config.sampling_multiplier * math.log(4)
    assert 0.0 < probability < 1.0

    sampled, backend = tsgs_module._sample_candidate_graph(
        ("account-a", "account-b", "account-c", "account-d"), edges, config
    )

    assert backend == "exact_component_grounded_laplacian_solve"
    assert 0 < len(sampled) < len(edges)
    assert all(edge.weight == pytest.approx(1.0 / probability) for edge in sampled)


def test_tiny_positive_candidate_energy_is_audited_and_cannot_false_pass():
    _, tsgs_module = _load_stage1_modules()
    candidate_edges = (tsgs_module.WeightedEdge("account-a", "account-b", 1e-300),)

    audit = tsgs_module._spectral_audit(
        ("account-a", "account-b"),
        candidate_edges,
        (),
        tsgs_module.TSGSConfig(seed=29, audit_vector_count=8, audit_tolerance=0.5),
    )

    assert audit.status == "ok"
    assert audit.sample_count == 8
    assert audit.observed_min_ratio == pytest.approx(0.0)
    assert audit.observed_max_ratio == pytest.approx(0.0)
    assert audit.observed_max_distortion == pytest.approx(1.0)
    assert audit.passed is False


def test_nonempty_graph_without_informative_probes_is_an_explicit_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    _, tsgs_module = _load_stage1_modules()
    edge = tsgs_module.WeightedEdge("account-a", "account-b", 1.0)
    monkeypatch.setattr(tsgs_module, "_quadratic_form", lambda *_args, **_kwargs: 0.0)

    audit = tsgs_module._spectral_audit(
        ("account-a", "account-b"),
        (edge,),
        (edge,),
        tsgs_module.TSGSConfig(seed=31, audit_vector_count=4),
    )

    assert audit.status == "no_informative_probes"
    assert audit.sample_count == 0
    assert audit.passed is False
    assert audit.observed_min_ratio is None
    assert audit.observed_max_ratio is None
    assert audit.observed_min_distortion is None
    assert audit.observed_max_distortion is None
