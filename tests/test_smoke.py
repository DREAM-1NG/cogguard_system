import json
import tempfile
from pathlib import Path

from propagation.analysis import analyze_events
from propagation.loaders import load_dataset, make_synthetic_events
from propagation.prediction import run_prediction
from propagation.reporting import build_final_report
from propagation.visualization import build_dashboard


def test_smoke_pipeline():
    events = make_synthetic_events()
    with tempfile.TemporaryDirectory() as tmp:
        summary = analyze_events(events, tmp)
        report = run_prediction(events, tmp, 0.3)
        dashboard = build_dashboard(events, tmp, report)
    assert summary["dataset_events"] == len(events)
    assert report["size_prediction"]["status"] == "ok"
    assert Path(dashboard).name == "dashboard.html"


def test_weibo_rumor_loader_sciencedb_shape():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "events.csv").write_text("e1,1,p1 p2 p3\n", encoding="utf-8")
        posts = root / "posts"
        posts.mkdir()
        (posts / "e1.json").write_text(
            json.dumps(
                [
                    {"id": "p1", "user": {"id": "u1"}, "text": "source", "created_at": "2024-01-01 00:00:00"},
                    {"id": "p2", "user": {"id": "u2"}, "parent_id": "p1", "text": "repost"},
                    {"id": "p3", "user": {"id": "u3"}, "parent_id": "p2", "text": "reply"},
                ]
            ),
            encoding="utf-8",
        )
        events = load_dataset("weibo_rumor", tmp)
    graph = events[0].to_graph()
    assert events[0].label == "rumor"
    assert graph.has_edge("p1", "p2")
    assert graph.has_edge("p2", "p3")


def test_rumor_rvnn_twitter_loader_shape():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        resource = root / "resource"
        resource.mkdir()
        (resource / "Twitter15_label_All.txt").write_text("false\tthread\troot1\t0\t0\n", encoding="utf-8")
        (resource / "data.TD_RvNN.vol_5000.txt").write_text(
            "root1\tNone\t1\t2\t9\t1:1\nroot1\t1\t2\t2\t9\t0:2\n",
            encoding="utf-8",
        )
        events = load_dataset("rumor_rvnn_twitter", tmp)
    graph = events[0].to_graph()
    assert events[0].label == "false"
    assert graph.has_edge("1", "2")


def test_pheme_loader_uses_thread_tweets_only():
    with tempfile.TemporaryDirectory() as tmp:
        thread = Path(tmp) / "all-rnr-annotated-threads" / "topic-all-rnr-threads" / "rumours" / "100"
        (thread / "source-tweets").mkdir(parents=True)
        (thread / "reactions").mkdir()
        (thread / "annotation.json").write_text(
            json.dumps({"category": "claim text", "true": "1", "misinformation": 0}),
            encoding="utf-8",
        )
        (thread / "structure.json").write_text(json.dumps({"100": {"101": []}}), encoding="utf-8")
        (thread / "source-tweets" / "100.json").write_text(
            json.dumps(
                {
                    "id_str": "100",
                    "text": "source",
                    "created_at": "Tue Mar 24 10:51:21 +0000 2015",
                    "user": {"id_str": "u1", "screen_name": "source_user", "followers_count": 10, "verified": True},
                }
            ),
            encoding="utf-8",
        )
        (thread / "reactions" / "101.json").write_text(
            json.dumps(
                {
                    "id_str": "101",
                    "text": "reply",
                    "created_at": "Tue Mar 24 10:52:21 +0000 2015",
                    "in_reply_to_status_id_str": "100",
                    "user": {"id_str": "u2"},
                }
            ),
            encoding="utf-8",
        )
        events = load_dataset("pheme", tmp)
    graph = events[0].to_graph()
    assert events[0].label == "true-rumour"
    assert events[0].metadata["claim"] == "claim text"
    assert set(graph.nodes) == {"100", "101"}
    assert graph.has_edge("100", "101")
    assert events[0].participants["u1"].screen_name == "source_user"


def test_final_report_builder_handles_missing_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        result = build_final_report("FINAL_REPORT.md", tmp)
        report = Path(result["report"])
        assert report.exists()
        text = report.read_text(encoding="utf-8")
        assert "任务覆盖" in text
        assert "验收结论" in text
