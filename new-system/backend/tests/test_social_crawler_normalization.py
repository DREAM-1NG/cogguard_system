import json

from app.config import settings
from app.core.crawler.social import (
    MediaCrawlBatch,
    MediaSocialCrawler,
    generic_jsonl_to_comment,
    generic_jsonl_to_post,
    sort_comments,
    weibo_comment_line_to_comment,
    weibo_content_line_to_post,
)


def test_media_social_crawler_build_command_includes_sub_comments_and_comment_cap(monkeypatch):
    crawler = MediaSocialCrawler("xhs")
    crawler.configure_runtime_options(recursive_comments=True, max_comments_per_post=1000)
    monkeypatch.setattr(settings, "MEDIACRAWLER_LOGIN_TYPE", "cookie")
    monkeypatch.setattr(settings, "MEDIACRAWLER_COOKIES", "sid=abc")
    monkeypatch.setattr(settings, "MEDIACRAWLER_MAX_COMMENTS_PER_POST", 200)

    cmd = crawler._build_command("G:/mc/.venv/Scripts/python.exe", None, ["事件A", " 事件B "])

    assert cmd[:2] == ["G:/mc/.venv/Scripts/python.exe", "main.py"]
    assert cmd[cmd.index("--get_sub_comment") + 1] == "yes"
    assert cmd[cmd.index("--max_comments_count_singlenotes") + 1] == "1000"
    assert cmd[cmd.index("--keywords") + 1] == "事件A,事件B"
    assert cmd[cmd.index("--cookies") + 1] == "sid=abc"


def test_media_social_crawler_runtime_options_record_effective_limits():
    crawler = MediaSocialCrawler("weibo")

    crawler.configure_runtime_options(
        recursive_comments=True,
        enrich_author_profiles=True,
        comment_sort="reply_count_desc",
    )

    assert crawler.recursive_comments is True
    assert crawler.enrich_author_profiles is True
    assert crawler.comment_sort == "reply_count_desc"
    assert crawler.crawl_metadata["recursive_comments_requested"] is True
    assert crawler.crawl_metadata["effective_comment_depth"] == 2
    assert crawler.crawl_metadata["recursive_comments_supported"] is False
    assert crawler.crawl_metadata["author_profile_enrichment_requested"] is True
    assert crawler.crawl_metadata["author_profile_enrichment_supported"] is False


def test_generic_jsonl_to_post_preserves_media_and_author_profile():
    raw = {
        "aweme_id": "a1",
        "desc": "同一事件视频",
        "user_id": "u1",
        "nickname": "douyin-user",
        "create_time": 1710000000,
        "aweme_url": "https://www.douyin.com/video/a1",
        "liked_count": "12",
        "share_count": "3",
        "comment_count": "9",
        "video_download_url": "https://cdn.example.com/video.mp4",
        "cover_url": "https://cdn.example.com/cover.jpg",
        "music_download_url": "https://cdn.example.com/music.mp3",
        "note_download_url": "https://cdn.example.com/note.webp",
        "tag_list": "事件A,热点",
        "avatar": "https://cdn.example.com/avatar.jpg",
        "ip_location": "北京",
        "sec_uid": "sec-1",
        "short_user_id": "short-1",
        "user_unique_id": "unique-1",
    }

    post = generic_jsonl_to_post(raw, "douyin")

    assert post.post_id == "a1"
    assert post.media_urls == [
        "https://cdn.example.com/video.mp4",
        "https://cdn.example.com/note.webp",
        "https://cdn.example.com/music.mp3",
        "https://cdn.example.com/cover.jpg",
    ]
    assert post.hashtags == ["事件A", "热点"]
    assert post.author_profile == {
        "user_id": "u1",
        "nickname": "douyin-user",
        "avatar": "https://cdn.example.com/avatar.jpg",
        "ip_location": "北京",
        "sec_uid": "sec-1",
        "short_user_id": "short-1",
        "user_unique_id": "unique-1",
        "desc": "同一事件视频",
        "tag_list": "事件A,热点",
    }
    assert post.raw_data == raw


def test_xhs_post_uses_millisecond_timestamp_chinese_counts_and_title_desc_content():
    raw = {
        "note_id": "xhs-1",
        "title": "特朗普狂晒中国行的满足感",
        "desc": "回到美国的特朗普，好像开始戒断反应了",
        "time": 1779201805000,
        "user_id": "u1",
        "nickname": "小红书作者",
        "liked_count": "4.3万",
        "comment_count": "1,318",
        "share_count": "5620",
        "video_url": "http://sns-video.example/video.mp4",
        "image_list": "http://sns-img.example/a.jpg,http://sns-img.example/b.jpg",
    }

    post = generic_jsonl_to_post(raw, "xhs")

    assert post.content == "特朗普狂晒中国行的满足感\n回到美国的特朗普，好像开始戒断反应了"
    assert post.timestamp.year == 2026
    assert post.likes == 43000
    assert post.comments_count == 1318
    assert post.reposts == 5620
    assert post.media_urls == [
        "http://sns-img.example/a.jpg",
        "http://sns-img.example/b.jpg",
        "http://sns-video.example/video.mp4",
    ]


def test_generic_jsonl_to_comment_preserves_tree_media_and_raw_payload():
    raw = {
        "comment_id": "c1",
        "aweme_id": "a1",
        "content": "二级评论",
        "user_id": "u2",
        "nickname": "reply-user",
        "create_time": 1710000010,
        "parent_comment_id": "root-1",
        "comment_like_count": "5",
        "sub_comment_count": "2",
        "pictures": "https://cdn.example.com/comment-1.jpg,https://cdn.example.com/comment-2.jpg",
        "avatar": "https://cdn.example.com/avatar-2.jpg",
        "ip_location": "上海",
    }

    comment = generic_jsonl_to_comment(raw, "douyin")

    assert comment.post_id == "a1"
    assert comment.reply_to == "root-1"
    assert comment.likes == 5
    assert comment.sub_comment_count == 2
    assert comment.media_urls == [
        "https://cdn.example.com/comment-1.jpg",
        "https://cdn.example.com/comment-2.jpg",
    ]
    assert comment.author_profile == {
        "user_id": "u2",
        "nickname": "reply-user",
        "avatar": "https://cdn.example.com/avatar-2.jpg",
        "ip_location": "上海",
    }
    assert comment.raw_data == raw


def test_generic_jsonl_to_comment_extracts_shared_urls_and_hashtags_from_content():
    raw = {
        "comment_id": "c2",
        "note_id": "x1",
        "content": "鏌ョ湅 #浜嬩欢A# https://example.com/topic?a=1锛屽啀鐪? #Topic_2",
        "user_id": "u3",
        "nickname": "annotator",
        "create_time": 1710000020,
        "note_url": "https://www.xiaohongshu.com/explore/x1",
    }

    comment = generic_jsonl_to_comment(raw, "xhs")

    assert comment.shared_urls == ["https://example.com/topic?a=1"]
    assert comment.hashtags == ["浜嬩欢A", "Topic_2"]
    assert "https://www.xiaohongshu.com/explore/x1" not in comment.shared_urls


def test_generic_jsonl_to_comment_extracts_nested_share_urls_but_skips_profile_and_media_urls():
    raw = {
        "comment_id": "c3",
        "note_id": "x2",
        "content": "璇勮鏈韩涓嶅惈閾炬帴",
        "user_id": "u4",
        "nickname": "link-user",
        "create_time": 1710000030,
        "share_info": {
            "url": "https://share.example.com/a",
            "deep_link": {"url": "https://share.example.com/b"},
        },
        "attachment": {"web_url": "https://share.example.com/c"},
        "profile_url": "https://example.com/u/u4",
        "avatar": "https://cdn.example.com/avatar-4.jpg",
        "pictures": "https://cdn.example.com/comment-3.jpg",
        "note_url": "https://www.xiaohongshu.com/explore/x2",
    }

    comment = generic_jsonl_to_comment(raw, "xhs")

    assert comment.shared_urls == [
        "https://share.example.com/a",
        "https://share.example.com/b",
        "https://share.example.com/c",
    ]
    assert "https://example.com/u/u4" not in comment.shared_urls
    assert "https://cdn.example.com/comment-3.jpg" not in comment.shared_urls
    assert "https://www.xiaohongshu.com/explore/x2" not in comment.shared_urls


def test_sort_comments_by_likes_or_reply_count_desc():
    comments = [
        generic_jsonl_to_comment(
            {"comment_id": "c1", "aweme_id": "a1", "content": "low", "like_count": 1, "sub_comment_count": 9},
            "douyin",
        ),
        generic_jsonl_to_comment(
            {"comment_id": "c2", "aweme_id": "a1", "content": "high", "like_count": 8, "sub_comment_count": 2},
            "douyin",
        ),
        generic_jsonl_to_comment(
            {"comment_id": "c3", "aweme_id": "a1", "content": "mid", "like_count": 4, "sub_comment_count": 5},
            "douyin",
        ),
    ]

    assert [comment.comment_id for comment in sort_comments(comments, "like_count_desc")] == ["c2", "c3", "c1"]
    assert [comment.comment_id for comment in sort_comments(comments, "reply_count_desc")] == ["c1", "c3", "c2"]


def test_weibo_comment_treats_root_placeholder_as_no_parent():
    raw = {
        "comment_id": "c2",
        "note_id": "w1",
        "content": "一级评论",
        "user_id": "u3",
        "nickname": "wb-user",
        "create_time": 1710000020,
        "parent_comment_id": "0",
        "comment_like_count": "1",
        "profile_url": "/u/123",
        "avatar": "https://wx.example.com/avatar.jpg",
    }

    comment = weibo_comment_line_to_comment(raw, "weibo")

    assert comment.reply_to is None
    assert comment.author_profile == {
        "user_id": "u3",
        "nickname": "wb-user",
        "avatar": "https://wx.example.com/avatar.jpg",
        "profile_url": "/u/123",
    }


def test_weibo_post_extracts_media_urls_from_detail_raw_payload():
    raw = {
        "note_id": "w1",
        "content": "video and image post",
        "user_id": "u1",
        "nickname": "wb-user",
        "create_time": 1710000000,
        "post_details_raw": {
            "note_id": "w1",
            "raw": {
                "pics": [
                    {
                        "url": "https://wx1.sinaimg.cn/orj360/pic-a.jpg",
                        "large": {"url": "https://wx1.sinaimg.cn/mw2000/pic-a.jpg"},
                    }
                ],
                "thumbnail_pic": "https://wx1.sinaimg.cn/thumbnail/pic-a.jpg",
                "bmiddle_pic": "http://wx1.sinaimg.cn/bmiddle/pic-a.jpg",
                "original_pic": "https://wx1.sinaimg.cn/large/pic-a.jpg",
                "page_info": {
                    "page_pic": {"url": "https://wx1.sinaimg.cn/orj480/video-cover.jpg"},
                    "media_info": {
                        "stream_url": "https://f.video.weibocdn.com/video-ld.mp4",
                        "stream_url_hd": "https://f.video.weibocdn.com/video-hd.mp4",
                    },
                    "urls": {
                        "mp4_720p_mp4": "https://f.video.weibocdn.com/video-720.mp4",
                    },
                },
            },
        },
    }

    post = weibo_content_line_to_post(raw, "weibo")

    assert post.media_urls == [
        "https://wx1.sinaimg.cn/orj360/pic-a.jpg",
        "https://wx1.sinaimg.cn/mw2000/pic-a.jpg",
        "https://wx1.sinaimg.cn/thumbnail/pic-a.jpg",
        "http://wx1.sinaimg.cn/bmiddle/pic-a.jpg",
        "https://wx1.sinaimg.cn/large/pic-a.jpg",
        "https://wx1.sinaimg.cn/orj480/video-cover.jpg",
        "https://f.video.weibocdn.com/video-ld.mp4",
        "https://f.video.weibocdn.com/video-hd.mp4",
        "https://f.video.weibocdn.com/video-720.mp4",
    ]


def test_weibo_comment_treats_self_parent_as_root_and_preserves_child_parent():
    root = weibo_comment_line_to_comment(
        {
            "comment_id": "5298608695673083",
            "note_id": "5298543512521068",
            "content": "一级评论",
            "parent_comment_id": "5298608695673083",
            "user_id": "u1",
            "nickname": "root-user",
        },
        "weibo",
    )
    child = weibo_comment_line_to_comment(
        {
            "comment_id": "5298766575829412",
            "note_id": "5298543512521068",
            "content": "二级评论",
            "parent_comment_id": "5298608695673083",
            "user_id": "u2",
            "nickname": "child-user",
        },
        "weibo",
    )

    assert root.reply_to is None
    assert child.reply_to == "5298608695673083"


def test_standard_models_accept_event_source_and_dedupe_fields():
    post = generic_jsonl_to_post({"note_id": "x1", "title": "事件"}, "xhs")
    post.event_id = "trump_visit_2026_05_21"
    post.source_keyword = "特朗普访华"
    post.dedupe_key = "trump_visit_2026_05_21:xhs:post:x1"

    comment = generic_jsonl_to_comment({"comment_id": "c1", "note_id": "x1", "content": "评论"}, "xhs")
    comment.event_id = "trump_visit_2026_05_21"
    comment.source_keyword = "特朗普访华"
    comment.dedupe_key = "trump_visit_2026_05_21:xhs:comment:c1"

    assert post.model_dump()["event_id"] == "trump_visit_2026_05_21"
    assert comment.model_dump()["dedupe_key"] == "trump_visit_2026_05_21:xhs:comment:c1"


def test_read_appended_jsonl_rows_only_returns_current_batch(tmp_path):
    crawler = MediaSocialCrawler("douyin")
    output = tmp_path / "search_contents_2026-05-20.jsonl"
    old_row = {"aweme_id": "old", "desc": "older batch"}
    new_row = {"aweme_id": "new", "desc": "current batch"}
    newer_row = {"aweme_id": "newer", "desc": "current batch 2"}
    output.write_text(json.dumps(old_row, ensure_ascii=False) + "\n", encoding="utf-8")
    start_offset = output.stat().st_size
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(new_row, ensure_ascii=False) + "\n")
        handle.write("{invalid json\n")
        handle.write(json.dumps(newer_row, ensure_ascii=False) + "\n")

    rows = crawler._read_appended_jsonl_rows(output, start_offset)

    assert rows == [new_row, newer_row]


async def _fake_execute_search_batch(*, keywords, max_posts):
    return MediaCrawlBatch(posts=[], comments=[], output_files={}, raw_counts={})


def test_search_delegates_to_execute_search_batch(monkeypatch):
    crawler = MediaSocialCrawler("weibo")
    monkeypatch.setattr(crawler, "execute_search_batch", _fake_execute_search_batch)

    import asyncio

    posts = asyncio.run(crawler.search(["事件A"], max_posts=5))

    assert posts == []
