"""Contracts for task-scoped crawl evidence and local media preview."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.models.task import CrawlJob
from app.models.user import User
from app.schemas.crawl import CrawlDataQuery
from app.services import crawl_service
from app.services import media_download_service
from tests.conftest import needs_db, test_session_factory


class _FakeCursor:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.limit_value: int | None = None

    def sort(self, *_args):
        return self

    def skip(self, _value: int):
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    async def to_list(self, length: int | None):
        limit = self.limit_value if self.limit_value is not None else length
        return self.rows[:limit]


class _FakeCollection:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.count_query: dict | None = None
        self.find_query: dict | None = None

    async def count_documents(self, query: dict) -> int:
        self.count_query = query
        return len(self.rows)

    def find(self, query: dict, _projection: dict):
        self.find_query = query
        return _FakeCursor(self.rows)


@pytest.mark.asyncio
async def test_posts_query_is_scoped_to_selected_crawl_job(monkeypatch):
    collection = _FakeCollection([{"post_id": "p-1"}])
    monkeypatch.setattr(crawl_service, "get_mongo_db", lambda: {"raw_posts": collection})

    items, total = await crawl_service.query_posts(
        CrawlDataQuery(crawl_job_id=42, page=1, page_size=20)
    )

    assert items == [{"post_id": "p-1"}]
    assert total == 1
    assert collection.count_query == {"crawl_job_id": 42}
    assert collection.find_query == {"crawl_job_id": 42}


def test_post_local_media_summary_exposes_only_availability_metadata():
    post = {"platform": "douyin", "post_id": "post-9", "content": "video"}
    local_items = [
        {
            "job_id": 14,
            "item_index": 0,
            "media_type": "video",
            "filename": "clip.mp4",
            "preview_url": "/api/v1/crawl/media-downloads/14/items/0/content",
            "path": "G:/private/clip.mp4",
        },
        {
            "job_id": 14,
            "item_index": 1,
            "media_type": "image",
            "filename": "cover.jpg",
        },
    ]

    enriched = crawl_service.with_local_media_summary(post, local_items)

    assert enriched["local_media"] == {"available_count": 2, "types": ["image", "video"]}
    assert "path" not in enriched["local_media"]
    assert "preview_url" not in enriched["local_media"]


@pytest.mark.asyncio
async def test_comment_preview_is_bound_to_one_post_and_limit(monkeypatch):
    collection = _FakeCollection(
        [{"comment_id": "c-1"}, {"comment_id": "c-2"}, {"comment_id": "c-3"}, {"comment_id": "c-4"}]
    )
    monkeypatch.setattr(crawl_service, "get_mongo_db", lambda: {"raw_comments": collection})

    comments = await crawl_service.query_post_comments(
        platform="douyin",
        post_id="post-9",
        crawl_job_id=42,
        limit=3,
    )

    assert [comment["comment_id"] for comment in comments] == ["c-1", "c-2", "c-3"]
    assert collection.find_query == {
        "platform": "douyin",
        "post_id": "post-9",
        "crawl_job_id": 42,
    }


def test_manifest_media_item_returns_only_existing_file_within_media_root(tmp_path: Path):
    media_root = tmp_path / "media"
    file_path = media_root / "douyin" / "post-9" / "clip.mp4"
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"video")
    manifest = {
        "items": [
            {
                "platform": "douyin",
                "post_id": "post-9",
                "media_type": "video",
                "local_path": str(file_path),
                "status": "downloaded",
            }
        ]
    }

    item = media_download_service.resolve_manifest_media_item(
        manifest,
        item_index=0,
        media_root=media_root,
    )

    assert item is not None
    assert item["media_type"] == "video"
    assert item["filename"] == "clip.mp4"
    assert item["path"] == file_path.resolve()


def test_manifest_media_item_rejects_missing_and_outside_root_paths(tmp_path: Path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    outside_path = tmp_path / "outside.mp4"
    outside_path.write_bytes(b"outside")

    outside = media_download_service.resolve_manifest_media_item(
        {"items": [{"status": "downloaded", "media_type": "video", "local_path": str(outside_path)}]},
        item_index=0,
        media_root=media_root,
    )
    missing = media_download_service.resolve_manifest_media_item(
        {
            "items": [
                {
                    "status": "downloaded",
                    "media_type": "image",
                    "local_path": str(media_root / "missing.jpg"),
                }
            ]
        },
        item_index=0,
        media_root=media_root,
    )

    assert outside is None
    assert missing is None


@pytest.mark.asyncio
async def test_post_comment_preview_route_requires_authentication(client: AsyncClient):
    response = await client.get(
        "/api/v1/crawl/posts/douyin/post-9/comments?crawl_job_id=42&limit=3"
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_local_media_content_route_requires_authentication(client: AsyncClient):
    response = await client.get("/api/v1/crawl/media-downloads/7/items/0/content")

    assert response.status_code == 401


@pytest.mark.asyncio
@needs_db
async def test_user_cannot_query_posts_from_another_users_crawl_job(setup_database, auth_client: AsyncClient):
    async with test_session_factory() as session:
        session.add(
            CrawlJob(
                job_type="social",
                platform="weibo",
                params_json="{}",
                status="completed",
                progress=100,
                created_by=999,
            )
        )
        await session.commit()
        job_id = (await session.execute(select(CrawlJob.id))).scalar_one()

    response = await auth_client.get(f"/api/v1/crawl/data?crawl_job_id={job_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "无权读取该任务"


@pytest.mark.asyncio
@needs_db
async def test_authorized_video_content_supports_range_requests(
    setup_database,
    auth_client: AsyncClient,
    monkeypatch,
    tmp_path: Path,
):
    media_root = tmp_path / "media"
    media_file = media_root / "douyin" / "post-9" / "clip.mp4"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"0123456789")
    manifest_path = media_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "platform": "douyin",
                        "post_id": "post-9",
                        "media_type": "video",
                        "local_path": str(media_file),
                        "status": "downloaded",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "MEDIA_DOWNLOAD_ROOT", str(media_root))

    async with test_session_factory() as session:
        user_id = (
            await session.execute(select(User.id).where(User.username == "testuser"))
        ).scalar_one()
        job = CrawlJob(
            job_type="media_download",
            platform="media_download",
            params_json="{}",
            status="completed",
            progress=100,
            created_by=user_id,
            result_summary=json.dumps({"manifest_path": str(manifest_path)}),
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    response = await auth_client.get(
        f"/api/v1/crawl/media-downloads/{job_id}/items/0/content",
        headers={"Range": "bytes=2-5"},
    )

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 2-5/10"
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == b"2345"


@pytest.mark.asyncio
@needs_db
async def test_administrator_can_list_and_stream_completed_media_from_another_user(
    setup_database,
    auth_client: AsyncClient,
    monkeypatch,
    tmp_path: Path,
):
    media_root = tmp_path / "media"
    media_file = media_root / "douyin" / "post-9" / "clip.mp4"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"0123456789")
    manifest_path = media_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "platform": "douyin",
                        "post_id": "post-9",
                        "media_type": "video",
                        "local_path": str(media_file),
                        "status": "downloaded",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "MEDIA_DOWNLOAD_ROOT", str(media_root))

    async with test_session_factory() as session:
        owner_id = (
            await session.execute(select(User.id).where(User.username == "testuser"))
        ).scalar_one()
        administrator = User(
            username="media-admin",
            email="media-admin@example.com",
            hashed_password=hash_password("adminpass123"),
            role="admin",
        )
        job = CrawlJob(
            job_type="media_download",
            platform="media_download",
            params_json="{}",
            status="completed",
            progress=100,
            created_by=owner_id,
            result_summary=json.dumps({"manifest_path": str(manifest_path)}),
        )
        incomplete_job = CrawlJob(
            job_type="media_download",
            platform="media_download",
            params_json="{}",
            status="running",
            progress=80,
            created_by=owner_id,
            result_summary=json.dumps({"manifest_path": str(manifest_path)}),
        )
        session.add_all([administrator, job, incomplete_job])
        await session.commit()
        await session.refresh(administrator)
        await session.refresh(job)

    auth_client.headers["Authorization"] = (
        f"Bearer {create_access_token(administrator.id, administrator.role)}"
    )
    listing = await auth_client.get("/api/v1/crawl/posts/douyin/post-9/media")

    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["job_id"] == job.id

    content = await auth_client.get(
        items[0]["preview_url"],
        headers={"Range": "bytes=2-5"},
    )

    assert content.status_code == 206
    assert content.headers["content-range"] == "bytes 2-5/10"
    assert content.content == b"2345"
