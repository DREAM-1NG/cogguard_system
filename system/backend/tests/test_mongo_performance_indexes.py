from pathlib import Path


def test_performance_indexes_cover_event_scoped_ingestion_markers():
    script_path = Path(__file__).resolve().parents[2] / "ops" / "mongo" / "apply_performance_indexes.js"
    script = script_path.read_text(encoding="utf-8")

    assert 'name: "ix_raw_posts_event_crawl_job_id"' in script
    assert 'name: "ix_raw_comments_event_crawl_job_id"' in script
    assert script.count("key: { event_id: 1, crawl_job_id: -1, _id: -1 }") == 2
