"""Import existing vendored social runtime JSONL search outputs into MongoDB.

This is meant for backfilling real raw social data that already exists under
``system/runtimes/social_runtime/data/<platform>/jsonl`` without rerunning a crawl task.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pymongo import UpdateOne

from app.config import PROJECT_ROOT
from app.core.crawler.social import (
    generic_jsonl_to_comment,
    generic_jsonl_to_post,
    weibo_comment_line_to_comment,
    weibo_content_line_to_post,
)
from app.db.mongodb import close_mongo, get_mongo_db
from app.models.post import StandardComment, StandardPost

DATE_PATTERN = re.compile(r"search_(?:contents|comments)_(\d{4}-\d{2}-\d{2})\.jsonl$")
EVENT_TOKEN_PATTERN = re.compile(r"[^\w\u4e00-\u9fff-]+", re.UNICODE)


@dataclass
class PlatformImportConfig:
    post_loader: Callable[[dict[str, Any], str], StandardPost]
    comment_loader: Callable[[dict[str, Any], str], StandardComment]


PLATFORM_CONFIG: dict[str, PlatformImportConfig] = {
    "weibo": PlatformImportConfig(
        post_loader=weibo_content_line_to_post,
        comment_loader=weibo_comment_line_to_comment,
    ),
    "douyin": PlatformImportConfig(
        post_loader=generic_jsonl_to_post,
        comment_loader=generic_jsonl_to_comment,
    ),
    "xhs": PlatformImportConfig(
        post_loader=generic_jsonl_to_post,
        comment_loader=generic_jsonl_to_comment,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import real MediaCrawler JSONL data into MongoDB.")
    parser.add_argument(
        "--platform",
        action="append",
        choices=sorted(PLATFORM_CONFIG),
        help="Platform to import. Can be specified multiple times. Defaults to all supported platforms.",
    )
    parser.add_argument(
        "--data-root",
        default=str(PROJECT_ROOT / "runtimes" / "social_runtime"),
        help="Built-in social runtime root. Defaults to system/runtimes/social_runtime.",
    )
    parser.add_argument(
        "--date",
        action="append",
        help="Only import JSONL files for these YYYY-MM-DD dates. Can be repeated. Defaults to all available dates.",
    )
    parser.add_argument(
        "--job-id",
        type=int,
        default=0,
        help="Synthetic crawl_job_id to stamp on imported documents. Defaults to 0.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and normalize data without writing to MongoDB.",
    )
    return parser.parse_args()


def iter_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def event_id_from_keyword(keyword: str, date_part: str, platform: str) -> str:
    text = str(keyword or "").strip()
    if text:
        token = EVENT_TOKEN_PATTERN.sub("_", text).strip("_")
        token = re.sub(r"_+", "_", token)
        if token:
            return f"{token}_{date_part.replace('-', '_')}"
    return f"historical_sync_{platform}_{date_part.replace('-', '_')}"


def infer_date_part(path: Path) -> str:
    match = DATE_PATTERN.search(path.name)
    if match:
        return match.group(1)
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def build_crawl_metadata(platform: str, content_path: Path, comment_path: Path | None, date_part: str) -> dict[str, Any]:
    return {
        "ingestion_mode": "historical_jsonl_sync",
        "platform": platform,
        "jsonl_date": date_part,
        "content_file": str(content_path),
        "comment_file": str(comment_path) if comment_path else None,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


def build_document(
    payload: dict[str, Any],
    *,
    item_type: str,
    item_id: str,
    event_id: str,
    source_keyword: str,
    job_id: int,
    crawl_metadata: dict[str, Any],
) -> dict[str, Any]:
    document = dict(payload)
    document["crawl_job_id"] = job_id
    document["event_id"] = event_id
    document["source_keyword"] = source_keyword
    document["crawl_metadata"] = crawl_metadata
    if item_id:
        document["dedupe_key"] = f"{event_id}:{document.get('platform', '')}:{item_type}:{item_id}"
    return document


async def write_documents(collection, documents: list[dict[str, Any]]) -> None:
    if not documents:
        return
    await collection.bulk_write(
        [
            UpdateOne({"dedupe_key": document["dedupe_key"]}, {"$set": document}, upsert=True)
            for document in documents
            if document.get("dedupe_key")
        ],
        ordered=False,
    )


def find_file_pairs(data_root: Path, platforms: list[str], dates: set[str] | None) -> list[tuple[str, Path, Path | None]]:
    pairs: list[tuple[str, Path, Path | None]] = []
    for platform in platforms:
        jsonl_dir = data_root / "data" / platform / "jsonl"
        if not jsonl_dir.is_dir():
            continue
        for content_path in sorted(jsonl_dir.glob("search_contents_*.jsonl")):
            date_part = infer_date_part(content_path)
            if dates and date_part not in dates:
                continue
            comment_path = jsonl_dir / f"search_comments_{date_part}.jsonl"
            pairs.append((platform, content_path, comment_path if comment_path.is_file() else None))
    return pairs


async def import_pair(
    mongo_db,
    *,
    platform: str,
    content_path: Path,
    comment_path: Path | None,
    job_id: int,
    dry_run: bool,
) -> dict[str, Any]:
    config = PLATFORM_CONFIG[platform]
    date_part = infer_date_part(content_path)
    crawl_metadata = build_crawl_metadata(platform, content_path, comment_path, date_part)

    content_rows = iter_jsonl_rows(content_path)
    comment_rows = iter_jsonl_rows(comment_path) if comment_path else []

    post_keyword_map: dict[str, str] = {}
    post_event_map: dict[str, str] = {}
    post_documents: list[dict[str, Any]] = []
    comment_documents: list[dict[str, Any]] = []

    for raw in content_rows:
        post = config.post_loader(raw, platform)
        payload = post.model_dump(mode="json")
        source_keyword = str(raw.get("source_keyword") or "").strip()
        event_id = event_id_from_keyword(source_keyword, date_part, platform)
        post_keyword_map[post.post_id] = source_keyword
        post_event_map[post.post_id] = event_id
        post_documents.append(
            build_document(
                payload,
                item_type="post",
                item_id=post.post_id,
                event_id=event_id,
                source_keyword=source_keyword,
                job_id=job_id,
                crawl_metadata=crawl_metadata,
            )
        )

    for raw in comment_rows:
        comment = config.comment_loader(raw, platform)
        payload = comment.model_dump(mode="json")
        source_keyword = post_keyword_map.get(comment.post_id, "")
        event_id = post_event_map.get(comment.post_id, event_id_from_keyword(source_keyword, date_part, platform))
        comment_documents.append(
            build_document(
                payload,
                item_type="comment",
                item_id=comment.comment_id,
                event_id=event_id,
                source_keyword=source_keyword,
                job_id=job_id,
                crawl_metadata=crawl_metadata,
            )
        )

    if not dry_run:
        await write_documents(mongo_db["raw_posts"], post_documents)
        await write_documents(mongo_db["raw_comments"], comment_documents)

    return {
        "platform": platform,
        "date": date_part,
        "content_file": str(content_path),
        "comment_file": str(comment_path) if comment_path else None,
        "posts": len(post_documents),
        "comments": len(comment_documents),
        "event_ids": sorted({document["event_id"] for document in post_documents})[:10],
    }


async def main() -> int:
    args = parse_args()
    data_root = Path(args.data_root).resolve() if args.data_root else None
    if data_root is None or not data_root.is_dir():
        raise SystemExit("Built-in social runtime root does not exist.")

    platforms = args.platform or sorted(PLATFORM_CONFIG)
    dates = set(args.date or [])
    pairs = find_file_pairs(data_root, platforms, dates or None)
    if not pairs:
        raise SystemExit("No matching MediaCrawler JSONL files were found for import.")

    mongo_db = get_mongo_db()
    summaries: list[dict[str, Any]] = []
    totals = defaultdict(int)
    try:
        for platform, content_path, comment_path in pairs:
            summary = await import_pair(
                mongo_db,
                platform=platform,
                content_path=content_path,
                comment_path=comment_path,
                job_id=args.job_id,
                dry_run=args.dry_run,
            )
            summaries.append(summary)
            totals["posts"] += summary["posts"]
            totals["comments"] += summary["comments"]
            print(json.dumps(summary, ensure_ascii=False))

        print(json.dumps({"totals": dict(totals), "dry_run": args.dry_run}, ensure_ascii=False))
        return 0
    finally:
        await close_mongo()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
