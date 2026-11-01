"""Download collected social media files from stored post media links."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.task import CrawlJob

SUPPORTED_MEDIA_PLATFORMS = {"xhs", "douyin"}
DEFAULT_MEDIA_TYPES = {"video", "image"}
VIDEO_PATTERNS = (
    ".mp4",
    ".m3u8",
    "/aweme/v1/play/",
    "video_id=",
    "sns-video",
    "douyinvod",
    "playwm",
)
IMAGE_PATTERNS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    "douyinpic",
    "xhscdn",
    "cover",
)
MEDIA_DOWNLOAD_JOB_TYPE = "media_download"
MEDIA_DOWNLOAD_PLATFORM = "media_download"
MEDIA_DOWNLOAD_TIMEOUT_SECONDS = 60.0
MEDIA_DOWNLOAD_CONCURRENCY = 3
# Cap redirect following so a hostile CDN cannot bounce us onto an internal
# address after the initial host check.
MEDIA_DOWNLOAD_MAX_REDIRECTS = 3


class BlockedMediaHostError(Exception):
    """Raised when a media URL resolves to a non-public address."""


def _is_public_ip(candidate: str) -> bool:
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_public_media_url(url: str) -> None:
    """Reject URLs whose host resolves to a private/loopback/link-local address.

    Media URLs come from crawled third-party content, so fetching them puts the
    backend in an SSRF position (cloud metadata endpoints, internal services).
    Every host is resolved and every resolved address must be public.
    """
    if settings.MEDIA_DOWNLOAD_ALLOW_PRIVATE_HOSTS:
        return

    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"}:
        raise BlockedMediaHostError(f"unsupported scheme: {parsed.scheme or 'none'}")
    host = parsed.hostname
    if not host:
        raise BlockedMediaHostError("missing host")

    # Literal IP in the URL: check directly, no DNS needed.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not _is_public_ip(host):
            raise BlockedMediaHostError(f"non-public address: {host}")
        return

    try:
        resolved = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except OSError as exc:
        raise BlockedMediaHostError(f"cannot resolve host {host}: {exc}") from exc

    addresses = {info[4][0] for info in resolved}
    if not addresses:
        raise BlockedMediaHostError(f"cannot resolve host {host}")
    for address in addresses:
        if not _is_public_ip(address):
            raise BlockedMediaHostError(f"host {host} resolves to non-public address {address}")


def _create_job_mongo_client():
    """Create a Mongo client owned by the download job's own event loop.

    The process-global Motor client is bound to whichever loop first used it, so
    reusing it from this job's private loop raises "Future attached to a
    different loop" (and poisons the global client once this loop closes).
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    return AsyncIOMotorClient(settings.mongo_url)


def classify_media_url(url: str) -> str | None:
    """Return video/image for supported media URLs, otherwise None."""
    text = unquote(str(url or "").strip()).lower()
    if not text.startswith(("http://", "https://")):
        return None
    if any(pattern in text for pattern in VIDEO_PATTERNS):
        return "video"
    if any(pattern in text for pattern in IMAGE_PATTERNS):
        return "image"
    return None


def sanitize_path_part(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r"[^\w.-]+", "_", text, flags=re.UNICODE).strip("._")
    return (text or fallback)[:96]


def file_extension_for_url(url: str, media_type: str, content_type: str | None = None) -> str:
    content_type_text = (content_type or "").lower()
    if "mp4" in content_type_text:
        return ".mp4"
    if "mpegurl" in content_type_text or "m3u8" in content_type_text:
        return ".m3u8"
    if "jpeg" in content_type_text:
        return ".jpg"
    if "png" in content_type_text:
        return ".png"
    if "webp" in content_type_text:
        return ".webp"

    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".mp4", ".m3u8", ".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    query = parse_qs(parsed.query)
    video_id = query.get("video_id", [""])[0]
    if media_type == "video" and video_id:
        return ".mp4"
    return ".mp4" if media_type == "video" else ".jpg"


def build_media_filename(platform: str, post_id: str, index: int, url: str, media_type: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    base = f"{sanitize_path_part(platform)}_{sanitize_path_part(post_id, 'post')}_{index:03d}_{digest}"
    return f"{base}{file_extension_for_url(url, media_type)}"


def normalize_media_types(media_types: Iterable[str] | None) -> set[str]:
    normalized = {str(item).strip().lower() for item in (media_types or DEFAULT_MEDIA_TYPES)}
    return (normalized & DEFAULT_MEDIA_TYPES) or set(DEFAULT_MEDIA_TYPES)


def build_post_filter(params: dict[str, Any]) -> dict[str, Any]:
    platform = str(params.get("platform") or "").strip()
    platforms = [platform] if platform else sorted(SUPPORTED_MEDIA_PLATFORMS)
    mongo_filter: dict[str, Any] = {
        "platform": {"$in": [item for item in platforms if item in SUPPORTED_MEDIA_PLATFORMS]},
        "media_urls.0": {"$exists": True},
    }
    keyword = str(params.get("keyword") or "").strip()
    if keyword:
        mongo_filter["content"] = {"$regex": re.escape(keyword), "$options": "i"}
    event_id = str(params.get("event_id") or "").strip()
    if event_id:
        mongo_filter["event_id"] = event_id
    post_ids = [str(item).strip() for item in (params.get("post_ids") or []) if str(item).strip()]
    if post_ids:
        mongo_filter["post_id"] = {"$in": post_ids}
    return mongo_filter


def build_save_dir(params: dict[str, Any]) -> Path:
    root = Path(settings.MEDIA_DOWNLOAD_ROOT).resolve()
    platform = sanitize_path_part(params.get("platform") or "mixed")
    event_or_keyword = sanitize_path_part(params.get("event_id") or params.get("keyword") or "all")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return root / platform / event_or_keyword / timestamp


async def create_media_download_job(req: Any, user_id: int, db: AsyncSession) -> CrawlJob:
    params = req.model_dump()
    params["media_types"] = sorted(normalize_media_types(params.get("media_types")))
    job = CrawlJob(
        job_type=MEDIA_DOWNLOAD_JOB_TYPE,
        platform=MEDIA_DOWNLOAD_PLATFORM,
        params_json=json.dumps(params, ensure_ascii=False, default=str),
        status="pending",
        progress=0,
        created_by=user_id,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def get_media_download_job(job_id: int, db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.job_type == MEDIA_DOWNLOAD_JOB_TYPE)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    payload = _job_to_dict(job)
    summary = _parse_json(job.result_summary) if job.result_summary else None
    payload["summary"] = summary
    payload["items"] = []
    manifest_path = summary.get("manifest_path") if isinstance(summary, dict) else None
    if manifest_path:
        manifest = read_manifest(Path(str(manifest_path)))
        payload["summary"] = manifest.get("summary") or summary
        payload["items"] = manifest.get("items") or []
    return payload


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def run_media_download_job(job_id: int, params_json: str) -> dict[str, Any]:
    """Synchronous entry point for FastAPI background tasks."""
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_run_media_download_job_async(job_id, params_json))

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run_media_download_job_async(job_id, params_json))
        finally:
            loop.close()
    except Exception as exc:
        _update_job_sync(
            job_id,
            status="failed",
            progress=100,
            result_summary={
                "save_root": str(Path(settings.MEDIA_DOWNLOAD_ROOT).resolve()),
                "total": 0,
                "downloaded": 0,
                "failed": 1,
                "skipped": 0,
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise


async def _run_media_download_job_async(job_id: int, params_json: str) -> dict[str, Any]:
    params = json.loads(params_json or "{}")
    requested_types = normalize_media_types(params.get("media_types"))
    save_dir = build_save_dir(params)
    save_dir.mkdir(parents=True, exist_ok=True)

    mongo_client = _create_job_mongo_client()
    try:
        mongo_db = mongo_client[settings.MONGO_DATABASE]
        cursor = mongo_db["raw_posts"].find(build_post_filter(params), {"_id": 0}).sort("timestamp", -1)
        posts = await cursor.to_list(length=None)
    finally:
        mongo_client.close()

    items = _build_download_items(posts, requested_types, save_dir)

    # Job status writes use the synchronous engine: the shared async engine's
    # pool holds connections created on the main event loop, and checking one
    # out from this job's private loop would cross event loops.
    _update_job_sync(
        job_id,
        status="running",
        progress=0,
        result_summary={
            "save_root": str(save_dir),
            "manifest_path": str(save_dir / "manifest.json"),
            "total": len(items),
            "downloaded": 0,
            "failed": 0,
            "skipped": 0,
        },
        finished=False,
    )

    semaphore = asyncio.Semaphore(MEDIA_DOWNLOAD_CONCURRENCY)
    async with httpx.AsyncClient(
        timeout=MEDIA_DOWNLOAD_TIMEOUT_SECONDS,
        follow_redirects=True,
        max_redirects=MEDIA_DOWNLOAD_MAX_REDIRECTS,
        headers=_download_headers(),
    ) as client:
        completed = 0
        results: list[dict[str, Any]] = []
        for batch_start in range(0, len(items), MEDIA_DOWNLOAD_CONCURRENCY):
            batch = items[batch_start : batch_start + MEDIA_DOWNLOAD_CONCURRENCY]
            batch_results = await asyncio.gather(
                *[_download_one(client, item, semaphore) for item in batch],
                return_exceptions=False,
            )
            results.extend(batch_results)
            completed += len(batch_results)
            _update_job_sync(
                job_id,
                status="running",
                progress=_progress(completed, len(items)),
                result_summary=None,
                finished=False,
            )

    summary = _summarize_results(results, save_dir)
    manifest_path = save_dir / "manifest.json"
    summary["manifest_path"] = str(manifest_path)
    manifest = {"summary": summary, "items": results}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    _update_job_sync(job_id, status="completed", progress=100, result_summary=summary)
    return summary


def _build_download_items(posts: list[dict[str, Any]], requested_types: set[str], save_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for post in posts:
        platform = str(post.get("platform") or "")
        post_id = str(post.get("post_id") or "")
        if platform not in SUPPORTED_MEDIA_PLATFORMS or not post_id:
            continue
        post_dir = save_dir / platform / sanitize_path_part(post_id, "post")
        media_index = 0
        for raw_url in post.get("media_urls") or []:
            url = str(raw_url or "").strip()
            if not url or url in seen_urls:
                continue
            media_type = classify_media_url(url)
            if media_type not in requested_types:
                continue
            seen_urls.add(url)
            media_index += 1
            items.append(
                {
                    "platform": platform,
                    "post_id": post_id,
                    "post_url": post.get("url") or "",
                    "author_name": post.get("author_name") or "",
                    "media_type": media_type,
                    "url": url,
                    "local_path": str(post_dir / build_media_filename(platform, post_id, media_index, url, media_type)),
                    "status": "pending",
                }
            )
    return items


async def _download_one(client: httpx.AsyncClient, item: dict[str, Any], semaphore: asyncio.Semaphore) -> dict[str, Any]:
    async with semaphore:
        target = Path(str(item["local_path"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size > 0:
            return {**item, "status": "skipped", "bytes": target.stat().st_size, "reason": "file_exists"}
        try:
            assert_public_media_url(str(item["url"]))
        except BlockedMediaHostError as exc:
            return {**item, "status": "failed", "error": f"blocked_host: {exc}"}
        try:
            async with client.stream("GET", str(item["url"])) as response:
                if response.status_code >= 400:
                    return {**item, "status": "failed", "error": f"HTTP {response.status_code}"}
                content_type = response.headers.get("Content-Type")
                corrected_target = _with_content_type_extension(target, str(item["url"]), str(item["media_type"]), content_type)
                if corrected_target != target:
                    item = {**item, "local_path": str(corrected_target)}
                    target = corrected_target
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() and target.stat().st_size > 0:
                        return {**item, "status": "skipped", "bytes": target.stat().st_size, "reason": "file_exists"}

                tmp_path = target.with_suffix(target.suffix + ".part")
                bytes_written = 0
                with tmp_path.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        if not chunk:
                            continue
                        handle.write(chunk)
                        bytes_written += len(chunk)
                tmp_path.replace(target)
                return {
                    **item,
                    "status": "downloaded",
                    "bytes": bytes_written,
                    "content_type": content_type,
                }
        except Exception as exc:
            tmp_path = target.with_suffix(target.suffix + ".part")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            return {**item, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def _with_content_type_extension(target: Path, url: str, media_type: str, content_type: str | None) -> Path:
    ext = file_extension_for_url(url, media_type, content_type)
    if ext and target.suffix.lower() != ext:
        return target.with_suffix(ext)
    return target


def _download_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
        "Accept": "*/*",
        "Referer": "https://www.douyin.com/",
    }


def _summarize_results(results: list[dict[str, Any]], save_dir: Path) -> dict[str, Any]:
    downloaded = sum(1 for item in results if item.get("status") == "downloaded")
    failed = sum(1 for item in results if item.get("status") == "failed")
    skipped = sum(1 for item in results if item.get("status") == "skipped")
    return {
        "save_root": str(save_dir),
        "total": len(results),
        "downloaded": downloaded,
        "failed": failed,
        "skipped": skipped,
    }


def _progress(done: int, total: int) -> int:
    if total <= 0:
        return 95
    return min(95, max(1, int(done / total * 95)))


# NOTE: job status updates from the background download job deliberately go
# through the synchronous `_update_job_sync` above. An async variant using the
# shared engine existed here previously and crossed event loops; do not
# reintroduce it without giving the job its own engine.


def _update_job_sync(
    job_id: int,
    *,
    status: str,
    progress: int,
    result_summary: dict[str, Any] | None,
    finished: bool | None = None,
) -> None:
    """Update job state over a short-lived synchronous connection.

    Used from the background job's private event loop, where the shared async
    engine's pool cannot be touched. ``finished`` defaults to True for terminal
    statuses so in-progress updates do not stamp ``finished_at``.
    """
    from sqlalchemy import create_engine, text

    if finished is None:
        finished = status in {"completed", "failed"}

    assignments = ["status=:status", "progress=:progress"]
    payload: dict[str, Any] = {"id": job_id, "status": status, "progress": progress}
    if result_summary is not None:
        assignments.append("result_summary=:summary")
        payload["summary"] = json.dumps(result_summary, ensure_ascii=False, default=str)
    if finished:
        assignments.append("finished_at=NOW()")

    engine = create_engine(settings.mysql_url.replace("+aiomysql", "+pymysql"))
    try:
        with engine.connect() as conn:
            conn.execute(
                text(f"UPDATE crawl_jobs SET {', '.join(assignments)} WHERE id=:id"),
                payload,
            )
            conn.commit()
    finally:
        engine.dispose()


def _parse_json(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _job_to_dict(job: CrawlJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "platform": job.platform,
        "status": job.status,
        "progress": job.progress,
        "result_summary": job.result_summary,
        "celery_task_id": job.celery_task_id,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }
