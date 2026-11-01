from app.config import settings
from app.core.crawler.types import CrawlBatch
from app.schemas.crawl import CrawlRequest
from app.tasks.crawl_tasks import _build_request_options
from app.tasks.crawl_tasks import prepare_crawl_document


def test_crawl_request_accepts_frontend_runtime_params():
    req = CrawlRequest(
        platform="weibo",
        keywords=["特朗普访华"],
        event_id="trump_visit_2026_05_21",
        source_keyword="特朗普访华",
        max_posts=200,
        crawl_comments=True,
        recursive_comments=True,
        enrich_author_profiles=True,
        comment_sort="reply_count_desc",
        max_comments_per_post=1000,
        execution_mode="local",
    )

    dumped = req.model_dump()

    assert dumped["event_id"] == "trump_visit_2026_05_21"
    assert dumped["source_keyword"] == "特朗普访华"
    assert dumped["max_comments_per_post"] == 1000
    assert dumped["execution_mode"] == "local"


def test_crawl_request_uses_runtime_sub_comment_default(monkeypatch):
    monkeypatch.setattr(settings, "MEDIACRAWLER_GET_SUB_COMMENTS", True)
    monkeypatch.setattr(settings, "MEDIACRAWLER_MAX_COMMENTS_PER_POST", 321)

    defaulted = CrawlRequest(platform="weibo", keywords=["event"])
    explicitly_disabled = CrawlRequest(
        platform="weibo",
        keywords=["event"],
        recursive_comments=False,
    )

    assert defaulted.recursive_comments is True
    assert defaulted.max_comments_per_post == 321
    assert explicitly_disabled.recursive_comments is False


def test_prepare_crawl_document_adds_event_source_and_dedupe_key():
    doc = prepare_crawl_document(
        {"platform": "weibo", "post_id": "5298543512521068", "content": "帖子"},
        params={
            "platform": "weibo",
            "keywords": ["特朗普访华"],
            "event_id": "trump_visit_2026_05_21",
            "source_keyword": "特朗普访华",
        },
        job_id=7,
        item_type="post",
        crawl_metadata={"execution_mode": "local"},
    )

    assert doc["crawl_job_id"] == 7
    assert doc["event_id"] == "trump_visit_2026_05_21"
    assert doc["source_keyword"] == "特朗普访华"
    assert doc["dedupe_key"] == "trump_visit_2026_05_21:weibo:post:5298543512521068"
    assert doc["crawl_metadata"] == {"execution_mode": "local"}


def test_build_request_options_captures_unified_collect_inputs():
    options = _build_request_options(
        {
            "keywords": ["事件"],
            "post_ids": ["p1"],
            "max_posts": 12,
            "crawl_comments": False,
            "recursive_comments": True,
            "enrich_author_profiles": True,
            "comment_sort": "reply_count_desc",
            "max_comments_per_post": 88,
        }
    )

    assert options.keywords == ["事件"]
    assert options.post_ids == ["p1"]
    assert options.max_posts == 12
    assert options.crawl_comments is False
    assert options.recursive_comments is True
    assert options.enrich_author_profiles is True
    assert options.comment_sort == "reply_count_desc"
    assert options.max_comments_per_post == 88


def test_build_request_options_uses_sub_comment_setting_for_legacy_jobs(monkeypatch):
    monkeypatch.setattr(settings, "MEDIACRAWLER_GET_SUB_COMMENTS", True)
    monkeypatch.setattr(settings, "MEDIACRAWLER_MAX_COMMENTS_PER_POST", 321)

    options = _build_request_options({"keywords": ["event"]})

    assert options.recursive_comments is True
    assert options.max_comments_per_post == 321
