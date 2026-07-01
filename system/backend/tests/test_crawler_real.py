"""真实爬虫封装单元测试（不启动 MediaCrawler / News 进程）。"""

import pytest

from app.core.crawler.factory import build_crawler
from app.core.crawler.social import weibo_comment_line_to_comment, weibo_content_line_to_post
from app.core.crawler.news import news_data_to_post


def test_build_crawler_mock():
    c = build_crawler("mock_weibo")
    assert c.platform == "mock_weibo"


def test_build_crawler_weibo():
    c = build_crawler("weibo")
    assert c.platform == "weibo"


def test_build_crawler_unknown():
    with pytest.raises(ValueError):
        build_crawler("unknown_platform")


def test_weibo_jsonl_to_post():
    raw = {
        "note_id": "123",
        "content": "正文",
        "user_id": "u1",
        "nickname": "名",
        "create_time": 1710000000,
        "note_url": "https://m.weibo.cn/detail/123",
        "liked_count": "5",
        "comments_count": "2",
        "shared_count": "1",
    }
    p = weibo_content_line_to_post(raw, "weibo")
    assert p.post_id == "123"
    assert p.content == "正文"
    assert p.likes == 5


def test_weibo_comment_line():
    raw = {
        "comment_id": "c1",
        "note_id": "123",
        "content": "回复",
        "user_id": "u2",
        "nickname": "b",
        "create_time": 1710000001,
        "parent_comment_id": "",
        "comment_like_count": "0",
    }
    c = weibo_comment_line_to_comment(raw, "weibo")
    assert c.post_id == "123"
    assert c.comment_id == "c1"


def test_news_dict_to_post():
    data = {
        "title": "标题",
        "news_url": "https://example.com/a",
        "news_id": "nid",
        "texts": ["段落"],
        "meta_info": {"author_name": "作者", "publish_time": "2026-01-01T00:00:00"},
    }
    p = news_data_to_post(data, "toutiao")
    assert p.platform == "news"
    assert "段落" in p.content
