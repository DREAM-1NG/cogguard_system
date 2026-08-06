from __future__ import annotations

import dataclasses
import importlib.util
import inspect
import math
import sys
import types
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import torch

from app.config import PROJECT_ROOT


def _load_stage1_modules():
    package_name = "_test_cogguard_coordination_stage1_mhcr"
    package_dir = PROJECT_ROOT / "research" / "coordination_discover" / "stage1"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_dir)]
        sys.modules[package_name] = package

    loaded = []
    for child_name in ("events", "tsgs", "mhcr"):
        module_name = f"{package_name}.{child_name}"
        module = sys.modules.get(module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(
                module_name, package_dir / f"{child_name}.py"
            )
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        loaded.append(module)
    return tuple(loaded)


def _events(events_module):
    start = datetime(2026, 8, 7, tzinfo=timezone.utc)
    rows = (
        ("account-a", "shared_url", "url-1", 0),
        ("account-b", "shared_url", "url-1", 8),
        ("account-c", "shared_url", "url-1", 15),
        ("account-a", "shared_hashtag", "topic-1", 20),
        ("account-b", "shared_hashtag", "topic-1", 28),
        ("account-c", "reply_target", "post-9", 35),
        ("account-d", "reply_target", "post-9", 39),
    )
    return tuple(
        events_module.CoordinationEvent(
            account_id=account_id,
            relation=relation,
            object_id=object_id,
            observed_at=start + timedelta(seconds=offset),
            weight=1.0,
            evidence_ref=f"evidence:{index}",
        )
        for index, (account_id, relation, object_id, offset) in enumerate(rows)
    )


def _fit(events_module, tsgs_module, mhcr_module):
    events = _events(events_module)
    tsgs_result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(
            seed=17,
            time_bucket_seconds=60,
            hyperplane_count=8,
            band_size=1,
            bucket_cap=16,
            sampling_multiplier=2.0,
        )
    ).fit_transform(events)
    representation = mhcr_module.MHCREncoder(
        mhcr_module.MHCRConfig(
            seed=17,
            time_bucket_seconds=60,
            hidden_dimension=8,
            epochs=5,
            learning_rate=0.03,
            temperature=0.2,
            temporal_jitter_seconds=12,
            hyperedge_drop_rate=0.25,
        )
    ).fit_transform(events, tsgs_result)
    return events, tsgs_result, representation


def test_mhcr_exports_relation_specific_hyperedge_incidence_and_label_free_features():
    events_module, tsgs_module, mhcr_module = _load_stage1_modules()

    _, _, representation = _fit(events_module, tsgs_module, mhcr_module)

    assert representation.account_ids == (
        "account-a",
        "account-b",
        "account-c",
        "account-d",
    )
    assert representation.objective == "self_supervised_infonce"
    assert representation.label_policy == "stage1_label_free"
    assert representation.feature_source == "events_only_structural_activity"
    assert representation.feature_names == (
        "event_count",
        "weight_sum",
        "relation_diversity",
        "object_diversity",
        "active_bucket_count",
        "temporal_span",
    )
    assert representation.relation_names == (
        "reply_target",
        "shared_hashtag",
        "shared_url",
    )
    assert {edge.relation for edge in representation.hyperedges} == set(
        representation.relation_names
    )
    shared_url = next(
        edge
        for edge in representation.hyperedges
        if edge.relation == "shared_url" and edge.object_id == "url-1"
    )
    assert shared_url.time_bucket == 29767680
    assert tuple(item.account_id for item in shared_url.incidence) == (
        "account-a",
        "account-b",
        "account-c",
    )
    assert all(item.weight == pytest.approx(1.0) for item in shared_url.incidence)
    assert representation.training_diagnostics.relation_transform_count == 3
    assert representation.training_diagnostics.node_to_hyperedge_normalization == "hyperedge_degree"
    assert representation.training_diagnostics.hyperedge_to_node_normalization == "node_incidence_degree"
    assert representation.training_diagnostics.node_channel == "explicit_tsgs_candidate_graph"


def test_mhcr_builds_two_seeded_views_and_fits_only_symmetric_infonce():
    events_module, tsgs_module, mhcr_module = _load_stage1_modules()

    _, _, representation = _fit(events_module, tsgs_module, mhcr_module)
    diagnostics = representation.training_diagnostics

    assert diagnostics.objective == "self_supervised_infonce"
    assert diagnostics.augmentations == ("seeded_temporal_jitter", "seeded_hyperedge_drop")
    assert diagnostics.view_count == 2
    assert tuple(view.name for view in diagnostics.views) == ("view_a", "view_b")
    assert diagnostics.views[0].seed != diagnostics.views[1].seed
    assert all(view.temporal_jitter_seconds == 12 for view in diagnostics.views)
    assert all(view.hyperedge_drop_rate == pytest.approx(0.25) for view in diagnostics.views)
    assert all(view.retained_hyperedge_count > 0 for view in diagnostics.views)
    assert all(view.dropped_hyperedge_ids for view in diagnostics.views)
    assert diagnostics.views[0].dropped_hyperedge_ids != diagnostics.views[1].dropped_hyperedge_ids
    assert diagnostics.views[0].content_signature != diagnostics.views[1].content_signature
    assert len(diagnostics.epoch_infonce_losses) == 5
    assert diagnostics.final_infonce_loss == diagnostics.epoch_infonce_losses[-1]
    assert math.isfinite(diagnostics.final_infonce_loss)
    assert diagnostics.final_infonce_loss >= 0.0

    source = inspect.getsource(mhcr_module).lower()
    for prohibited in (
        "classifier",
        "supervised_loss",
        "risk_score",
        "harmful_verdict",
        "class_logits",
    ):
        assert prohibited not in source


def test_seeded_cpu_fit_is_deterministic_for_reordered_events():
    events_module, tsgs_module, mhcr_module = _load_stage1_modules()
    events = _events(events_module)
    tsgs_result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(seed=29, time_bucket_seconds=60)
    ).fit_transform(events)
    config = mhcr_module.MHCRConfig(
        seed=29,
        time_bucket_seconds=60,
        hidden_dimension=8,
        epochs=4,
        temporal_jitter_seconds=10,
        hyperedge_drop_rate=0.3,
    )

    first = mhcr_module.MHCREncoder(config).fit_transform(events, tsgs_result)
    second = mhcr_module.MHCREncoder(config).fit_transform(reversed(events), tsgs_result)

    np.testing.assert_array_equal(np.asarray(first.embeddings), np.asarray(second.embeddings))
    assert first.hyperedges == second.hyperedges
    assert first.training_diagnostics == second.training_diagnostics
    assert list(inspect.signature(mhcr_module.MHCREncoder.fit_transform).parameters) == [
        "self",
        "events",
        "tsgs_result",
    ]


def test_temporal_jitter_changes_propagated_view_content_without_bucket_crossing():
    events_module, _, mhcr_module = _load_stage1_modules()
    start = datetime(2026, 8, 7, tzinfo=timezone.utc) + timedelta(seconds=20)
    events = tuple(
        events_module.CoordinationEvent(
            account_id=account_id,
            relation=relation,
            object_id=object_id,
            observed_at=start + timedelta(seconds=offset),
            weight=1.0,
            evidence_ref=f"evidence:{index}",
        )
        for index, (account_id, relation, object_id, offset) in enumerate(
            (
                ("account-a", "shared_url", "url-1", 0),
                ("account-b", "shared_url", "url-1", 2),
                ("account-a", "shared_hashtag", "topic-1", 8),
                ("account-b", "shared_hashtag", "topic-1", 10),
            )
        )
    )
    config = mhcr_module.MHCRConfig(
        seed=101,
        time_bucket_seconds=60,
        epochs=1,
        temporal_jitter_seconds=1,
        hyperedge_drop_rate=0.0,
    )

    first, second, diagnostics = mhcr_module._build_two_views(events, config)

    assert {edge.time_bucket for edge in first} == {29767680}
    assert {edge.time_bucket for edge in second} == {29767680}
    assert diagnostics[0].content_signature != diagnostics[1].content_signature
    first_temporal_values = tuple(
        item.temporal_position for edge in first for item in edge.incidence
    )
    second_temporal_values = tuple(
        item.temporal_position for edge in second for item in edge.incidence
    )
    assert first_temporal_values != second_temporal_values


def test_small_enabled_drop_rate_keeps_two_deterministic_masks_distinct():
    events_module, _, mhcr_module = _load_stage1_modules()
    events = _events(events_module)[:5]
    config = mhcr_module.MHCRConfig(
        seed=103,
        time_bucket_seconds=60,
        epochs=1,
        temporal_jitter_seconds=1,
        hyperedge_drop_rate=0.01,
    )

    first = mhcr_module._build_two_views(events, config)
    second = mhcr_module._build_two_views(tuple(reversed(events)), config)

    assert first == second
    assert all(view.dropped_hyperedge_count >= 1 for view in first[2])
    assert first[2][0].dropped_hyperedge_ids != first[2][1].dropped_hyperedge_ids


def test_symmetric_infonce_is_invoked_with_distinct_view_tensors(
    monkeypatch: pytest.MonkeyPatch,
):
    events_module, tsgs_module, mhcr_module = _load_stage1_modules()
    original = mhcr_module._symmetric_infonce
    observed_distinct = []

    def recording_infonce(first, second, temperature):
        observed_distinct.append(not torch.equal(first.detach(), second.detach()))
        return original(first, second, temperature)

    monkeypatch.setattr(mhcr_module, "_symmetric_infonce", recording_infonce)
    _, _, representation = _fit(events_module, tsgs_module, mhcr_module)

    assert observed_distinct == [True] * len(
        representation.training_diagnostics.epoch_infonce_losses
    )


def test_relation_specific_transform_perturbation_changes_propagated_output():
    events_module, tsgs_module, mhcr_module = _load_stage1_modules()
    events = _events(events_module)
    account_ids = tuple(sorted({event.account_id for event in events}))
    hyperedges = mhcr_module._build_hyperedges(events, 60)
    relation_names = tuple(sorted({event.relation for event in events}))
    torch.manual_seed(211)
    model = mhcr_module._RelationAwareHypergraphEncoder(6, 8, relation_names)
    features = torch.arange(24, dtype=torch.float32).reshape(4, 6) / 24.0
    empty_tsgs = tsgs_module.TemporalSketchGraphSparsifier().fit_transform([])
    sparse_channel = mhcr_module._candidate_channel(
        dataclasses.replace(empty_tsgs, account_ids=account_ids)
    )

    before = model(features, hyperedges, account_ids, sparse_channel).detach().clone()
    relation_index = model.relation_index["shared_url"]
    with torch.no_grad():
        model.relation_transforms[relation_index].weight.add_(0.5)
    after = model(features, hyperedges, account_ids, sparse_channel).detach()

    assert not torch.allclose(before, after)


def test_candidate_node_channel_is_sparse_linear_and_preserves_gradients(
    monkeypatch: pytest.MonkeyPatch,
):
    _, tsgs_module, mhcr_module = _load_stage1_modules()
    account_count = 4096
    account_ids = tuple(f"account-{index:05d}" for index in range(account_count))
    empty_tsgs = tsgs_module.TemporalSketchGraphSparsifier().fit_transform([])
    tsgs_result = dataclasses.replace(
        empty_tsgs,
        account_ids=account_ids,
        full_pair_count=account_count * (account_count - 1) // 2,
        candidate_graph_edges=(
            tsgs_module.WeightedEdge(account_ids[0], account_ids[1], 2.0),
            tsgs_module.WeightedEdge(account_ids[0], account_ids[2], 1.0),
        ),
    )
    original_zeros = torch.zeros

    def reject_square_node_allocation(size, *args, **kwargs):
        if (
            isinstance(size, (tuple, list))
            and len(size) == 2
            and size[0] == account_count
            and size[1] == account_count
        ):
            raise AssertionError("allocated dense account-by-account candidate tensor")
        return original_zeros(size, *args, **kwargs)

    monkeypatch.setattr(torch, "zeros", reject_square_node_allocation)
    channel = mhcr_module._candidate_channel(tsgs_result)

    assert channel.account_count == account_count
    assert channel.source_indices.shape == channel.target_indices.shape == (4,)
    assert channel.normalized_weights.shape == (4,)
    assert torch.isfinite(channel.normalized_weights).all()
    target_weight_sums = original_zeros(account_count, dtype=torch.float32)
    target_weight_sums.index_add_(
        0, channel.target_indices, channel.normalized_weights
    )
    np.testing.assert_allclose(
        target_weight_sums[:3].numpy(), np.ones(3, dtype=np.float32)
    )

    torch.manual_seed(307)
    model = mhcr_module._RelationAwareHypergraphEncoder(6, 8, ())
    features = torch.randn(account_count, 6, requires_grad=True)
    output = model(features, (), account_ids, channel)
    output.square().sum().backward()

    assert output.shape == (account_count, 8)
    assert features.grad is not None and torch.isfinite(features.grad).all()
    assert model.graph_transform.weight.grad is not None
    assert torch.isfinite(model.graph_transform.weight.grad).all()


def test_single_hyperedge_drop_builds_distinct_reproducible_propagated_views():
    events_module, tsgs_module, mhcr_module = _load_stage1_modules()
    observed_at = datetime(2026, 8, 7, tzinfo=timezone.utc) + timedelta(seconds=20)
    events = (
        events_module.CoordinationEvent(
            "account-a", "shared_url", "url-1", observed_at, 1.0, "evidence:1"
        ),
        events_module.CoordinationEvent(
            "account-b",
            "shared_url",
            "url-1",
            observed_at + timedelta(seconds=2),
            1.0,
            "evidence:2",
        ),
    )
    config = mhcr_module.MHCRConfig(
        seed=313,
        time_bucket_seconds=60,
        epochs=1,
        temporal_jitter_seconds=0,
        hyperedge_drop_rate=0.5,
    )

    first = mhcr_module._build_two_views(events, config)
    repeated = mhcr_module._build_two_views(tuple(reversed(events)), config)

    assert first == repeated
    assert sorted((len(first[0]), len(first[1]))) == [0, 1]
    assert first[2][0].content_signature != first[2][1].content_signature
    assert sorted(view.dropped_hyperedge_count for view in first[2]) == [0, 1]

    tsgs_result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(seed=313, time_bucket_seconds=60)
    ).fit_transform(events)
    channel = mhcr_module._candidate_channel(tsgs_result)
    account_ids = tsgs_result.account_ids
    features = mhcr_module._initial_features(events, account_ids, 60)
    torch.manual_seed(313)
    model = mhcr_module._RelationAwareHypergraphEncoder(6, 8, ("shared_url",))
    first_tensor = model(features, first[0], account_ids, channel)
    second_tensor = model(features, first[1], account_ids, channel)
    assert not torch.equal(first_tensor, second_tensor)

    disabled = mhcr_module._build_two_views(
        events, dataclasses.replace(config, hyperedge_drop_rate=0.0)
    )
    assert disabled[0] == disabled[1]
    assert disabled[2][0].content_signature == disabled[2][1].content_signature
    empty = mhcr_module._build_two_views((), config)
    assert empty[0] == empty[1] == ()
    assert empty[2][0].content_signature == empty[2][1].content_signature


def test_event_mapping_with_any_label_bearing_field_remains_rejected():
    events_module, _, _ = _load_stage1_modules()
    valid = {
        "account_id": "account-a",
        "relation": "shared_url",
        "object_id": "url-1",
        "observed_at": "2026-08-07T00:00:00Z",
        "weight": 1.0,
        "evidence_ref": "evidence:1",
    }

    for field in ("label", "risk", "verdict", "class", "bot", "harmful"):
        with pytest.raises(ValueError, match="forbidden label-bearing fields"):
            events_module.CoordinationEvent.from_mapping({**valid, field: "opposite"})


def test_mhcr_revalidates_relation_semantics_before_fitting():
    events_module, tsgs_module, mhcr_module = _load_stage1_modules()
    events = list(_events(events_module))
    tsgs_result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(seed=7, time_bucket_seconds=60)
    ).fit_transform(events)
    object.__setattr__(events[0], "relation", "harmful")

    with pytest.raises(ValueError, match="canonical label-free relation"):
        mhcr_module.MHCREncoder(
            mhcr_module.MHCRConfig(seed=7, time_bucket_seconds=60, epochs=1)
        ).fit_transform(events, tsgs_result)


def test_mhcr_representation_is_a_frozen_auditable_value():
    events_module, tsgs_module, mhcr_module = _load_stage1_modules()
    _, _, representation = _fit(events_module, tsgs_module, mhcr_module)

    assert dataclasses.is_dataclass(representation)
    with pytest.raises(dataclasses.FrozenInstanceError):
        representation.embeddings = ()
