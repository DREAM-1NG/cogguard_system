from __future__ import annotations

import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path


def _load_script():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_coordination_local_discover_detect.py"
    spec = importlib.util.spec_from_file_location("_test_coordination_local_discover_detect", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def test_local_discover_detect_script_normalizes_jsonl_and_preserves_missing_label_boundary(tmp_path: Path):
    script = _load_script()
    data_root = tmp_path / "data_runs"
    _write_jsonl(
        data_root / "weibo_trump_visit_2026-05-21" / "search" / "weibo" / "jsonl" / "search_contents_2026-05-21.jsonl",
        [
            {
                "note_id": "w1",
                "content": "shared alpha beta gamma delta epsilon zeta eta theta",
                "create_time": 1778830616,
                "note_url": "https://m.weibo.cn/detail/w1",
                "user_id": "u1",
                "nickname": "alice",
                "source_keyword": "trump_visit",
            },
            {
                "note_id": "w2",
                "content": "shared alpha beta gamma delta epsilon zeta eta theta followup",
                "create_time": 1778830816,
                "note_url": "https://m.weibo.cn/detail/w2",
                "user_id": "u4",
                "nickname": "carol",
                "source_keyword": "trump_visit",
            }
        ],
    )
    _write_jsonl(
        data_root / "weibo_trump_visit_2026-05-21" / "search" / "weibo" / "jsonl" / "search_comments_2026-05-21.jsonl",
        [
            {
                "comment_id": "wc1",
                "note_id": "w1",
                "create_time": 1778830716,
                "user_id": "u2",
                "content": "reply alpha",
                "parent_comment_id": "0",
            }
        ],
    )
    _write_jsonl(
        data_root / "douyin_trump_visit_2026-05-21" / "search_full6" / "douyin" / "jsonl" / "search_contents_2026-05-21.jsonl",
        [
            {
                "aweme_id": "d1",
                "title": "shared alpha beta gamma delta epsilon zeta eta theta",
                "desc": "same keyword",
                "create_time": 1778831016,
                "aweme_url": "https://www.douyin.com/video/d1",
                "user_id": "u3",
                "nickname": "bob",
                "source_keyword": "trump_visit",
            }
        ],
    )

    rows = script.load_local_rows(data_root, platforms={"weibo", "douyin"}, event_id="fixture_event")
    snapshots = script._build_snapshots(
        event_id="fixture_event",
        platforms=("weibo", "douyin"),
        posts=rows.posts,
        comments=rows.comments,
    )

    assert len(rows.source_files) == 3
    assert len(rows.posts) == 3
    assert rows.posts[0]["event_id"] == "fixture_event"
    assert "combined" in snapshots
    assert snapshots["combined"].quality_report.status in {"pass", "warn"}

    result = script._run_snapshot(
        coordination_discover=script._load_coordination_discover(),
        snapshot_name="combined",
        snapshot=snapshots["combined"],
        artifact_dir=tmp_path / "artifacts" / "combined",
        args=Namespace(
            embedding_dim=8,
            epochs=1,
            negative_ratio=1,
            device="cpu",
            min_learned_edge_score=0.0,
            allow_non_leiden_exploration=False,
        ),
    )

    assert result["detect_validation"]["status"] == "missing_labels"
    assert result["v2_optimization"]["account_multigraph_edge_count"] >= 1
    assert result["v2_optimization"]["dynamic_window_graph_count"] >= 1
    assert result["v2_optimization"]["process_role"] == "exploratory_non_claimable"

    summary_row = script._summary_row(result)
    inventory = script._dataset_inventory(
        rows=rows,
        data_root=data_root.resolve(),
        post_cap_report={"mode": "uncapped", "max_per_platform": 0, "dropped_by_platform": {}},
        comment_cap_report={"mode": "uncapped", "max_per_platform": 0, "dropped_by_platform": {}},
        snapshots={"combined": snapshots["combined"]},
    )
    manifest = {
        "claim_boundary": {
            "discovery": "case_study_and_system_validation",
            "detect": "validation_only_missing_labels_on_local_trump_data",
            "process_motifs": "exploratory_non_claimable",
        }
    }
    effectiveness = script._effectiveness_summary(
        manifest=manifest,
        inventory=inventory,
        summary_rows=[summary_row],
        result_records=[result],
    )

    assert effectiveness["experiment_scope"] == "full_all_snapshots"
    assert effectiveness["gates"]["evidence_multigraph"] is True
    assert effectiveness["gates"]["detect_label_boundary"] is True
    assert effectiveness["by_snapshot"][0]["dynamic_window_gate"] is True
    assert effectiveness["by_snapshot"][0]["process_exploratory_gate"] in {True, False}
    assert effectiveness["overall_conclusion"] in {"effective_for_discovery_case_study", "needs_followup"}


def test_local_discover_detect_script_defaults_to_vendored_social_runtime_boundary():
    script = _load_script()
    assert script.DEFAULT_LOCAL_DATA_ROOT == script.SYSTEM_ROOT / "runtimes" / "social_runtime" / "data_runs"

