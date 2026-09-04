import asyncio

from store.weibo import _extract_mblog_media_fields
from media_platform.weibo import core as weibo_core
from media_platform.weibo.core import WeiboCrawler


def test_extract_mblog_media_fields_preserves_images_video_and_raw_detail():
    mblog = {
        "id": "w1",
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
    }

    fields = _extract_mblog_media_fields(mblog)

    assert fields["media_urls"] == [
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
    assert fields["pics"] == mblog["pics"]
    assert fields["page_info"] == mblog["page_info"]
    assert fields["post_details_raw"] == {"note_id": "w1", "raw": mblog}


def test_get_note_full_text_fetches_detail_raw_for_non_long_posts(monkeypatch):
    crawler = WeiboCrawler()
    calls = []

    class FakeClient:
        async def get_note_info_by_id(self, note_id):
            calls.append(note_id)
            return {
                "mblog": {
                    "id": note_id,
                    "text": "full detail text",
                    "isLongText": False,
                    "pics": [{"url": "https://wx1.sinaimg.cn/orj360/detail.jpg"}],
                }
            }

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(weibo_core.config, "ENABLE_WEIBO_FULL_TEXT", True)
    monkeypatch.setattr(weibo_core.asyncio, "sleep", fake_sleep)
    crawler.wb_client = FakeClient()

    result = asyncio.run(
        crawler.get_note_full_text(
            {"mblog": {"id": "w1", "text": "search text", "isLongText": False}}
        )
    )

    assert calls == ["w1"]
    assert result["mblog"]["text"] == "full detail text"
    assert result["mblog"]["pics"] == [{"url": "https://wx1.sinaimg.cn/orj360/detail.jpg"}]
