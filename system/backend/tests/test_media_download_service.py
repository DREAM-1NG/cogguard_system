import json

import httpx
import pytest

from app.services import media_download_service as service


def test_classifies_collected_video_and_image_links():
    assert service.classify_media_url("https://www.douyin.com/aweme/v1/play/?video_id=abc") == "video"
    assert service.classify_media_url("http://sns-video-v3.xhscdn.com/stream/a.mp4?sign=1") == "video"
    assert service.classify_media_url("https://p3-pc-sign.douyinpic.com/obj/tos-cn-i-dy/cover") == "image"
    assert service.classify_media_url("https://example.com/story") is None


def test_build_media_filename_is_stable_and_filesystem_safe():
    url = "https://www.douyin.com/aweme/v1/play/?video_id=abc&sign=bad/chars"
    first = service.build_media_filename("douyin", "post/123", 1, url, "video")
    second = service.build_media_filename("douyin", "post/123", 1, url, "video")

    assert first == second
    assert first.endswith(".mp4")
    assert "/" not in first
    assert "\\" not in first


@pytest.mark.asyncio
async def test_download_one_skips_existing_file(tmp_path):
    target = tmp_path / "existing.mp4"
    target.write_bytes(b"already here")
    item = {
        "platform": "douyin",
        "post_id": "p1",
        "post_url": "https://www.douyin.com/video/p1",
        "author_name": "u",
        "media_type": "video",
        "url": "https://example.com/video.mp4",
        "local_path": str(target),
        "status": "pending",
    }

    async with httpx.AsyncClient() as client:
        result = await service._download_one(client, item, service.asyncio.Semaphore(1))

    assert result["status"] == "skipped"
    assert result["reason"] == "file_exists"
    assert target.read_bytes() == b"already here"


@pytest.mark.asyncio
async def test_download_one_records_http_failure_without_raising(tmp_path):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="blocked")

    item = {
        "platform": "xhs",
        "post_id": "p1",
        "post_url": "https://www.xiaohongshu.com/explore/p1",
        "author_name": "u",
        "media_type": "video",
        "url": "https://example.com/video.mp4",
        "local_path": str(tmp_path / "blocked.mp4"),
        "status": "pending",
    }

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await service._download_one(client, item, service.asyncio.Semaphore(1))

    assert result["status"] == "failed"
    assert result["error"] == "HTTP 403"
    assert not (tmp_path / "blocked.mp4").exists()


def test_build_download_items_filters_platform_type_and_duplicates(tmp_path):
    posts = [
        {
            "platform": "douyin",
            "post_id": "p1",
            "url": "https://www.douyin.com/video/p1",
            "author_name": "a",
            "media_urls": [
                "https://www.douyin.com/aweme/v1/play/?video_id=v1",
                "https://p3-pc-sign.douyinpic.com/obj/cover",
                "https://example.com/story",
                "https://www.douyin.com/aweme/v1/play/?video_id=v1",
            ],
        },
        {
            "platform": "weibo",
            "post_id": "p2",
            "media_urls": ["https://example.com/video.mp4"],
        },
    ]

    items = service._build_download_items(posts, {"video", "image"}, tmp_path)

    assert [item["media_type"] for item in items] == ["video", "image"]
    assert all(item["platform"] == "douyin" for item in items)


def test_summary_counts_downloaded_failed_and_skipped(tmp_path):
    summary = service._summarize_results(
        [
            {"status": "downloaded"},
            {"status": "failed"},
            {"status": "skipped"},
        ],
        tmp_path,
    )

    assert summary == {
        "save_root": str(tmp_path),
        "total": 3,
        "downloaded": 1,
        "failed": 1,
        "skipped": 1,
    }
