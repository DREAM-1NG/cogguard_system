"""Import historical MediaCrawler JSONL data runs into CogGuard storage.

The script normalizes platform-specific MediaCrawler rows into the CogGuard
standard post/comment shape, deduplicates by event/platform/id, and can upsert
the resulting documents into MongoDB while recording deterministic import jobs
in MySQL.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pymongo import ASCENDING, IndexModel, UpdateOne
from sqlalchemy import create_engine, text

from app.config import settings
from app.core.crawler.social import (
    generic_jsonl_to_comment,
    generic_jsonl_to_post,
    weibo_comment_line_to_comment,
    weibo_content_line_to_post,
)
from app.db.mongodb import close_mongo, get_mongo_db
from app.models.post import StandardComment, StandardPost

DEFAULT_EVENT_ID = "trump_visit_2026_05_21"
LEGACY_WEIBO_PLATFORM = "weibo"
LEGACY_WEIBO_CRAWL_JOB_ID = 0
LEGACY_WEIBO_INGESTION_MODE = "historical_jsonl_sync"
LEGACY_WEIBO_JSONL_DATE = "2026-05-20"
DEFAULT_KEYWORD = "特朗普访华"


@dataclass(frozen=True)
class PlatformSource:
    platform: str
    posts_path: Path
    comments_path: Path
    creator_profiles_path: Path | None = None
    post_details_path: Path | None = None


@dataclass
class PlatformImportResult:
    platform: str
    posts: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    stats: dict[str, int]
    missing_comment_post_refs: list[str] = field(default_factory=list)
    source_files: dict[str, str] = field(default_factory=dict)


def build_legacy_weibo_reconciliation_filters(
    normalized: list[PlatformImportResult], *, event_id: str
) -> dict[str, dict[str, Any]]:
    """Build exact manifest-absence filters for audited legacy Weibo rows."""

    if event_id != DEFAULT_EVENT_ID:
        raise ValueError(f"Legacy Weibo reconciliation is limited to event {DEFAULT_EVENT_ID}")
    weibo_results = [result for result in normalized if result.platform == LEGACY_WEIBO_PLATFORM]
    post_ids = sorted(
        {
            str(document.get("post_id") or "").strip()
            for result in weibo_results
            for document in result.posts
            if str(document.get("post_id") or "").strip()
        }
    )
    comment_ids = sorted(
        {
            str(document.get("comment_id") or "").strip()
            for result in weibo_results
            for document in result.comments
            if str(document.get("comment_id") or "").strip()
        }
    )
    if not post_ids or not comment_ids:
        raise ValueError("Legacy Weibo reconciliation requires a non-empty normalized Weibo manifest")

    legacy_signature = {
        "event_id": event_id,
        "platform": LEGACY_WEIBO_PLATFORM,
        "crawl_job_id": LEGACY_WEIBO_CRAWL_JOB_ID,
        "crawl_metadata.ingestion_mode": LEGACY_WEIBO_INGESTION_MODE,
        "crawl_metadata.jsonl_date": LEGACY_WEIBO_JSONL_DATE,
    }
    return {
        "posts": {**legacy_signature, "post_id": {"$nin": post_ids}},
        "comments": {**legacy_signature, "comment_id": {"$nin": comment_ids}},
    }


async def reconcile_legacy_weibo_manifest(
    normalized: list[PlatformImportResult], *, event_id: str, execute: bool
) -> dict[str, int]:
    """Preview or delete only audited legacy Weibo rows absent from the manifest."""

    filters = build_legacy_weibo_reconciliation_filters(normalized, event_id=event_id)
    mongo_db = get_mongo_db()
    posts = mongo_db["raw_posts"]
    comments = mongo_db["raw_comments"]
    counts = {
        "post_preview": await posts.count_documents(filters["posts"]),
        "post_deleted": 0,
        "comment_preview": await comments.count_documents(filters["comments"]),
        "comment_deleted": 0,
    }
    if not execute:
        return counts

    post_delete = await posts.delete_many(filters["posts"])
    comment_delete = await comments.delete_many(filters["comments"])
    counts["post_deleted"] = int(post_delete.deleted_count)
    counts["comment_deleted"] = int(comment_delete.deleted_count)
    return counts


def _latest_jsonl(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"No {pattern} file found under {directory}")
    return matches[0]


def build_latest_trump_visit_sources(data_runs_root: Path) -> dict[str, PlatformSource]:
    root = Path(data_runs_root)
    source_dirs = {
        "weibo": root / "weibo_trump_visit_2026-05-21" / "search_more" / "weibo" / "jsonl",
        "xhs": root / "xhs_trump_visit_2026-05-21" / "search_full2" / "xhs" / "jsonl",
        "douyin": root / "douyin_trump_visit_2026-05-21" / "search_full6" / "douyin" / "jsonl",
    }
    weibo_creator_dir = root / "weibo_trump_visit_2026-05-21" / "creator" / "weibo" / "jsonl"
    weibo_post_raw_dir = root / "weibo_trump_visit_2026-05-21" / "post_raw" / "weibo" / "jsonl"

    sources: dict[str, PlatformSource] = {}
    for platform, directory in source_dirs.items():
        sources[platform] = PlatformSource(
            platform=platform,
            posts_path=_latest_jsonl(directory, "search_contents_*.jsonl"),
            comments_path=_latest_jsonl(directory, "search_comments_*.jsonl"),
            creator_profiles_path=(
                _latest_jsonl(weibo_creator_dir, "creator_profiles_raw_*.jsonl")
                if platform == "weibo" and weibo_creator_dir.is_dir()
                else None
            ),
            post_details_path=(
                _latest_jsonl(weibo_post_raw_dir, "post_details_raw_*.jsonl")
                if platform == "weibo" and weibo_post_raw_dir.is_dir()
                else None
            ),
        )
    return sources


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad_json = 0
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                bad_json += 1
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows, bad_json


def _row_version(row: dict[str, Any]) -> int:
    for key in ("last_modify_ts", "last_update_time"):
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0


def dedupe_rows_by_id(rows: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = str(row.get(id_field) or "").strip()
        if not row_id:
            continue
        current = deduped.get(row_id)
        if current is None or _row_version(row) >= _row_version(current):
            deduped[row_id] = row
    return list(deduped.values())


def _merge_by_key(path: Path | None, key_field: str) -> dict[str, dict[str, Any]]:
    if not path or not path.is_file():
        return {}
    rows, _bad_json = read_jsonl(path)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_key = str(row.get(key_field) or "").strip()
        if not row_key:
            continue
        current = result.get(row_key, {})
        merged = {**current, **row}
        result[row_key] = merged
    return result


def _post_converter(platform: str) -> Callable[[dict[str, Any], str], StandardPost]:
    return weibo_content_line_to_post if platform == "weibo" else generic_jsonl_to_post


def _comment_converter(platform: str) -> Callable[[dict[str, Any], str], StandardComment]:
    return weibo_comment_line_to_comment if platform == "weibo" else generic_jsonl_to_comment


def _add_import_metadata(
    document: dict[str, Any],
    *,
    event_id: str,
    keyword: str,
    item_type: str,
) -> dict[str, Any]:
    platform = str(document["platform"])
    item_id = str(document["post_id"] if item_type == "post" else document["comment_id"])
    document["event_id"] = event_id
    document["source_keyword"] = keyword
    document["dedupe_key"] = f"{event_id}:{platform}:{item_type}:{item_id}"
    document["imported_at"] = datetime.now(timezone.utc)
    return document


def _model_to_document(model: StandardPost | StandardComment) -> dict[str, Any]:
    return model.model_dump()


def normalize_platform_files(
    *,
    platform: str,
    posts_path: Path,
    comments_path: Path,
    event_id: str,
    keyword: str,
    creator_profiles_path: Path | None = None,
    post_details_path: Path | None = None,
) -> PlatformImportResult:
    post_rows, post_bad_json = read_jsonl(posts_path)
    comment_rows, comment_bad_json = read_jsonl(comments_path)

    post_id_field = "aweme_id" if platform == "douyin" else "note_id"
    comment_post_id_field = "aweme_id" if platform == "douyin" else "note_id"
    post_rows = dedupe_rows_by_id(post_rows, post_id_field)
    comment_rows = dedupe_rows_by_id(comment_rows, "comment_id")

    creator_profiles = _merge_by_key(creator_profiles_path, "user_id")
    post_details = _merge_by_key(post_details_path, "note_id")

    posts: list[dict[str, Any]] = []
    post_ids: set[str] = set()
    for raw in post_rows:
        post_id = str(raw.get(post_id_field) or "").strip()
        if not post_id:
            continue
        enriched_raw = dict(raw)
        if platform == "weibo" and post_id in post_details:
            enriched_raw["post_details_raw"] = post_details[post_id]
        model = _post_converter(platform)(enriched_raw, platform)
        if platform == "weibo" and model.author_id in creator_profiles:
            profile = dict(model.author_profile or {})
            profile["homepage_raw"] = creator_profiles[model.author_id]
            model.author_profile = profile
        document = _add_import_metadata(
            _model_to_document(model),
            event_id=event_id,
            keyword=str(raw.get("source_keyword") or keyword),
            item_type="post",
        )
        posts.append(document)
        post_ids.add(document["post_id"])

    comments: list[dict[str, Any]] = []
    missing_refs: set[str] = set()
    for raw in comment_rows:
        post_ref = str(raw.get(comment_post_id_field) or "").strip()
        if post_ref and post_ref not in post_ids:
            missing_refs.add(post_ref)
        model = _comment_converter(platform)(raw, platform)
        document = _add_import_metadata(
            _model_to_document(model),
            event_id=event_id,
            keyword=str(raw.get("source_keyword") or keyword),
            item_type="comment",
        )
        comments.append(document)

    source_files = {
        "posts": str(posts_path),
        "comments": str(comments_path),
    }
    if creator_profiles_path:
        source_files["creator_profiles"] = str(creator_profiles_path)
    if post_details_path:
        source_files["post_details"] = str(post_details_path)

    return PlatformImportResult(
        platform=platform,
        posts=posts,
        comments=comments,
        stats={
            "raw_posts": len(read_jsonl(posts_path)[0]),
            "unique_posts": len(posts),
            "raw_comments": len(read_jsonl(comments_path)[0]),
            "unique_comments": len(comments),
            "bad_post_json": post_bad_json,
            "bad_comment_json": comment_bad_json,
            "missing_comment_post_refs": len(missing_refs),
        },
        missing_comment_post_refs=sorted(missing_refs),
        source_files=source_files,
    )


def _result_summary(result: PlatformImportResult, *, event_id: str, keyword: str, execute: bool) -> str:
    return json.dumps(
        {
            "mode": "mediacrawler_data_run_import",
            "execute": execute,
            "event_id": event_id,
            "keyword": keyword,
            "platform": result.platform,
            "stats": result.stats,
            "source_files": result.source_files,
        },
        ensure_ascii=False,
        default=str,
    )


def _import_job_key(event_id: str, platform: str) -> str:
    return f"mc_import:{event_id}:{platform}:latest-trump-visit"


def ensure_mysql_import_job(result: PlatformImportResult, *, event_id: str, keyword: str) -> int:
    import_job_key = _import_job_key(event_id, result.platform)
    params = {
        "platform": result.platform,
        "keywords": [keyword],
        "event_id": event_id,
        "import_job_key": import_job_key,
        "import_mode": "mediacrawler_data_runs",
        "source_files": result.source_files,
        "stats": result.stats,
    }
    params_json = json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)
    summary = _result_summary(result, event_id=event_id, keyword=keyword, execute=True)

    sync_url = settings.mysql_url.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text(
                    "SELECT id FROM crawl_jobs "
                    "WHERE platform=:platform AND params_json LIKE :job_key "
                    "ORDER BY id LIMIT 1"
                ),
                {"platform": result.platform, "job_key": f"%{import_job_key}%"},
            ).scalar()
            if existing:
                conn.execute(
                    text(
                        "UPDATE crawl_jobs SET status='completed', progress=100, "
                        "result_summary=:summary, finished_at=NOW() WHERE id=:id"
                    ),
                    {"summary": summary, "id": existing},
                )
                return int(existing)

            conn.execute(
                text(
                    "INSERT INTO crawl_jobs "
                    "(job_type, platform, params_json, status, progress, result_summary, created_by, finished_at) "
                    "VALUES ('social', :platform, :params_json, 'completed', 100, :summary, 0, NOW())"
                ),
                {"platform": result.platform, "params_json": params_json, "summary": summary},
            )
            return int(conn.execute(text("SELECT LAST_INSERT_ID()")).scalar_one())
    finally:
        engine.dispose()


async def ensure_mongo_indexes() -> None:
    mongo_db = get_mongo_db()
    await mongo_db["raw_posts"].create_indexes(
        [
            IndexModel(
                [("dedupe_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"dedupe_key": {"$exists": True}},
                name="uniq_raw_posts_dedupe_key",
            ),
            IndexModel([("event_id", ASCENDING), ("platform", ASCENDING), ("timestamp", ASCENDING)]),
            IndexModel([("post_id", ASCENDING)]),
            IndexModel([("author_id", ASCENDING)]),
        ]
    )
    await mongo_db["raw_comments"].create_indexes(
        [
            IndexModel(
                [("dedupe_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"dedupe_key": {"$exists": True}},
                name="uniq_raw_comments_dedupe_key",
            ),
            IndexModel([("event_id", ASCENDING), ("platform", ASCENDING), ("timestamp", ASCENDING)]),
            IndexModel([("post_id", ASCENDING)]),
            IndexModel([("author_id", ASCENDING)]),
        ]
    )


def _attach_job_id(documents: list[dict[str, Any]], job_id: int) -> list[dict[str, Any]]:
    for document in documents:
        document["crawl_job_id"] = job_id
    return documents


async def upsert_platform_result(result: PlatformImportResult, *, job_id: int) -> dict[str, int]:
    mongo_db = get_mongo_db()
    await ensure_mongo_indexes()

    post_ops = [
        UpdateOne({"dedupe_key": doc["dedupe_key"]}, {"$set": doc}, upsert=True)
        for doc in _attach_job_id(result.posts, job_id)
    ]
    comment_ops = [
        UpdateOne({"dedupe_key": doc["dedupe_key"]}, {"$set": doc}, upsert=True)
        for doc in _attach_job_id(result.comments, job_id)
    ]

    counts = {
        "post_upserts": 0,
        "post_modified": 0,
        "comment_upserts": 0,
        "comment_modified": 0,
    }
    if post_ops:
        write_result = await mongo_db["raw_posts"].bulk_write(post_ops, ordered=False)
        counts["post_upserts"] = len(write_result.upserted_ids)
        counts["post_modified"] = write_result.modified_count
    if comment_ops:
        write_result = await mongo_db["raw_comments"].bulk_write(comment_ops, ordered=False)
        counts["comment_upserts"] = len(write_result.upserted_ids)
        counts["comment_modified"] = write_result.modified_count
    return counts


def print_result(result: PlatformImportResult) -> None:
    print(json.dumps({
        "platform": result.platform,
        "stats": result.stats,
        "missing_comment_post_refs": result.missing_comment_post_refs[:20],
        "source_files": result.source_files,
    }, ensure_ascii=False, indent=2, default=str))


async def run_import(args: argparse.Namespace) -> int:
    if args.preset != "latest-trump-visit":
        raise ValueError(f"Unsupported preset: {args.preset}")

    sources = build_latest_trump_visit_sources(Path(args.data_runs_root))
    results = [
        normalize_platform_files(
            platform=source.platform,
            posts_path=source.posts_path,
            comments_path=source.comments_path,
            creator_profiles_path=source.creator_profiles_path,
            post_details_path=source.post_details_path,
            event_id=args.event_id,
            keyword=args.keyword,
        )
        for source in sources.values()
    ]

    for result in results:
        print_result(result)

    if not args.execute:
        print("Dry-run only. Re-run with --execute to write MySQL/MongoDB.")
        return 0

    try:
        for result in results:
            job_id = ensure_mysql_import_job(result, event_id=args.event_id, keyword=args.keyword)
            write_counts = await upsert_platform_result(result, job_id=job_id)
            print(json.dumps({
                "platform": result.platform,
                "crawl_job_id": job_id,
                "write_counts": write_counts,
            }, ensure_ascii=False, default=str))
    finally:
        await close_mongo()
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default="latest-trump-visit", choices=["latest-trump-visit"])
    parser.add_argument("--event-id", default=DEFAULT_EVENT_ID)
    parser.add_argument("--keyword", default=DEFAULT_KEYWORD)
    parser.add_argument(
        "--data-runs-root",
        default=str(BACKEND_DIR.parents[1] / "system" / "runtimes" / "social_runtime" / "data_runs"),
        help="Vendored social runtime data_runs root directory.",
    )
    parser.add_argument("--execute", action="store_true", help="Write to MySQL and MongoDB. Omit for dry-run.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(run_import(args))


if __name__ == "__main__":
    raise SystemExit(main())
