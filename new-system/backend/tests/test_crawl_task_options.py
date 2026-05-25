from app.core.crawler.social import MediaSocialCrawler
from app.tasks.crawl_tasks import apply_crawl_options


def test_apply_crawl_options_configures_media_social_crawler():
    crawler = MediaSocialCrawler("xhs")
    params = {
        "recursive_comments": True,
        "enrich_author_profiles": True,
        "comment_sort": "like_count_desc",
    }

    apply_crawl_options(crawler, params)

    assert crawler.recursive_comments is True
    assert crawler.enrich_author_profiles is True
    assert crawler.comment_sort == "like_count_desc"
    assert crawler.crawl_metadata["effective_comment_depth"] == 2
