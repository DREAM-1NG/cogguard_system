from collections import Counter
from pathlib import Path

from scripts.run_twitter_io_coordination_experiment import parse_args

from app.core.coordination.twitter_io_experiment import (
    BASE_RELATIONS,
    ExperimentConfig,
    METHOD_CATALOG,
    _build_archive_stream_command,
    run_multi_relation_benchmark,
    _update_pairs_for_object,
    expand_methods,
    normalize_archive_url,
    parse_archive_list,
    RelationResult,
)


def test_parse_archive_list_handles_empty_and_bracket_values():
    assert parse_archive_list("") == []
    assert parse_archive_list("[]") == []
    assert parse_archive_list("[foo, bar]") == ["foo", "bar"]


def test_normalize_archive_url_strips_tracking_query_and_trailing_slash():
    assert (
        normalize_archive_url("https://Example.com/path/?utm_source=test&x=1#frag")
        == "https://example.com/path?x=1"
    )


def test_expand_methods_includes_base_relations_for_multi_relation():
    expanded = expand_methods(("url_share", "multi_relation"))
    assert "url_share" in expanded
    assert "reply_target" in expanded
    assert "mention_target" in expanded


def test_cli_accepts_all_catalog_methods(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_twitter_io_coordination_experiment.py",
            "--tweets-zip",
            "archive.zip",
            "--output-dir",
            "out",
            "--methods",
            *sorted(METHOD_CATALOG.keys()),
        ],
    )
    args = parse_args()
    assert tuple(args.methods) == tuple(sorted(METHOD_CATALOG.keys()))


def test_build_archive_stream_command_prefers_unzip(monkeypatch):
    monkeypatch.setattr(
        "app.core.coordination.twitter_io_experiment.shutil.which",
        lambda name: "/usr/bin/unzip" if name == "unzip" else None,
    )
    backend, command = _build_archive_stream_command(Path("archive.zip"), "tweets.csv")
    assert backend == "unzip"
    assert command == ["/usr/bin/unzip", "-p", "archive.zip", "tweets.csv"]


def test_expand_methods_supports_static_multi_relation():
    expanded = expand_methods(("multi_relation_static",))
    assert set(BASE_RELATIONS).issubset(set(expanded))


def test_learned_multi_relation_returns_attention_distribution():
    relation_results = {
        "url_share": RelationResult(
            method="url_share",
            label="",
            paper_anchor="",
            relation_names=("url_share",),
            event_count=10,
            filtered_object_count=1,
            pair_count=3,
            node_count=3,
            edge_count=2,
            component_count=1,
            cluster_count=1,
            largest_component_size=3,
            largest_cluster_size=3,
            avg_edge_weight=1.5,
            modularity_score=0.0,
            top_nodes=[],
            top_edges=[],
            top_objects=[],
            component_sizes=[3],
            cluster_sizes=[3],
            relation_breakdown=None,
            learning_metadata=None,
            edge_weights=Counter({("u1", "u2"): 3.0, ("u2", "u3"): 1.0}),
        ),
        "retweet_target": RelationResult(
            method="retweet_target",
            label="",
            paper_anchor="",
            relation_names=("retweet_target",),
            event_count=8,
            filtered_object_count=1,
            pair_count=2,
            node_count=3,
            edge_count=2,
            component_count=1,
            cluster_count=1,
            largest_component_size=3,
            largest_cluster_size=3,
            avg_edge_weight=1.0,
            modularity_score=0.0,
            top_nodes=[],
            top_edges=[],
            top_objects=[],
            component_sizes=[3],
            cluster_sizes=[3],
            relation_breakdown=None,
            learning_metadata=None,
            edge_weights=Counter({("u1", "u2"): 1.0, ("u1", "u3"): 2.0}),
        ),
        "reply_target": RelationResult(
            method="reply_target",
            label="",
            paper_anchor="",
            relation_names=("reply_target",),
            event_count=5,
            filtered_object_count=1,
            pair_count=1,
            node_count=2,
            edge_count=1,
            component_count=1,
            cluster_count=1,
            largest_component_size=2,
            largest_cluster_size=2,
            avg_edge_weight=1.0,
            modularity_score=0.0,
            top_nodes=[],
            top_edges=[],
            top_objects=[],
            component_sizes=[2],
            cluster_sizes=[2],
            relation_breakdown=None,
            learning_metadata=None,
            edge_weights=Counter({("u2", "u3"): 2.0}),
        ),
    }
    for relation_name in ("hashtag_share", "quote_target", "mention_target"):
        relation_results[relation_name] = RelationResult(
            method=relation_name,
            label="",
            paper_anchor="",
            relation_names=(relation_name,),
            event_count=0,
            filtered_object_count=0,
            pair_count=0,
            node_count=0,
            edge_count=0,
            component_count=0,
            cluster_count=0,
            largest_component_size=0,
            largest_cluster_size=0,
            avg_edge_weight=0.0,
            modularity_score=None,
            top_nodes=[],
            top_edges=[],
            top_objects=[],
            component_sizes=[],
            cluster_sizes=[],
            relation_breakdown=None,
            learning_metadata=None,
            edge_weights=Counter({("u1", "u3"): 1.0}),
        )

    config = ExperimentConfig(
        tweets_zip_path=Path("archive.zip"),
        output_dir=Path("out"),
        methods=("multi_relation",),
        attention_epochs=25,
        attention_learning_rate=0.2,
        attention_max_samples=100,
    )
    result = run_multi_relation_benchmark(config, relation_results)

    assert result.method == "multi_relation"
    assert result.learning_metadata is not None
    assert result.learning_metadata["mode"] == "learned_relation_attention"
    assert result.relation_breakdown is not None
    assert abs(sum(result.relation_breakdown.values()) - 1.0) < 1e-6
    assert result.edge_count > 0


def test_update_pairs_for_object_respects_time_window_and_same_account_filter():
    edge_weights = Counter()
    pair_counter = Counter()
    pair_count = _update_pairs_for_object(
        "obj-1",
        [
            (0, "u1", "c1"),
            (10, "u2", "c2"),
            (20, "u1", "c3"),
            (90, "u3", "c4"),
        ],
        time_window_seconds=30,
        edge_weights=edge_weights,
        object_pair_counts=pair_counter,
    )

    assert pair_count == 2
    assert edge_weights[("u1", "u2")] == 2
    assert pair_counter["obj-1"] == 2
