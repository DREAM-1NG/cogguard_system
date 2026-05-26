from app.core.crawler.social import MediaSocialCrawler
from app.schemas.crawl import CrawlRequest
from app.tasks.crawl_tasks import apply_crawl_options
from app.tasks.crawl_tasks import prepare_crawl_document


def test_apply_crawl_options_configures_media_social_crawler():
    crawler = MediaSocialCrawler("xhs")
    params = {
        "recursive_comments": True,
        "enrich_author_profiles": True,
        "comment_sort": "like_count_desc",
        "max_comments_per_post": 1000,
    }

    apply_crawl_options(crawler, params)

    assert crawler.recursive_comments is True
    assert crawler.enrich_author_profiles is True
    assert crawler.comment_sort == "like_count_desc"
    assert crawler.max_comments_per_post == 1000
    assert crawler.crawl_metadata["effective_comment_depth"] == 2
    assert crawler.crawl_metadata["max_comments_per_post"] == 1000


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
