"""Import a real MediaCrawler Weibo run into the KT1 coordination registry.

This script converts raw Weibo JSONL crawl outputs into the standard
coordination event-table schema used by the `/coordination` page:

    account_id, relation, object_id, timestamp, content, target_account_id

The resulting dataset can then run the fixed KT1 mainline:
    Discover = MAGNN + Leiden
    Detect   = SBERT + fusion_gnn (China pretrained inference for unlabeled data)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import html
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd
from sqlalchemy import select

from app.core.coordination_baseline.io_reproduction import normalize_event_table
from app.core.crawler.social import weibo_comment_line_to_comment, weibo_content_line_to_post
from app.db.mysql import async_session_factory
from app.models.coordination_registry import CoordinationDataset
from app.services.coordination_model_service import (
    create_coordination_run,
    run_coordination_model_job,
    upload_coordination_dataset,
)

HASHTAG_PATTERN = re.compile(r"#([^#\r\n]{1,64})#|#([A-Za-z0-9_\-\u4e00-\u9fff]{1,64})")
MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_\-\u4e00-\u9fff]{1,64})")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class WeiboRunPaths:
    posts_paths: list[Path]
    comments_paths: list[Path]
    post_details_path: Path | None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _dedupe_by_key(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_key = str(row.get(key) or "").strip()
        if not row_key:
            continue
        current = deduped.get(row_key)
        if current is None or int(row.get("last_modify_ts", 0) or 0) >= int(current.get("last_modify_ts", 0) or 0):
            deduped[row_key] = row
    return list(deduped.values())


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    cleaned = HTML_TAG_PATTERN.sub(" ", html.unescape(str(text)))
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_hashtags_from_text(text: str) -> list[str]:
    tags: list[str] = []
    for left, right in HASHTAG_PATTERN.findall(text):
        value = (left or right or "").strip()
        if value:
            tags.append(value)
    return list(dict.fromkeys(tags))


def _extract_mentions(text: str) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in MENTION_PATTERN.findall(text) if value.strip()))


def _default_weibo_run_paths(run_root: Path) -> WeiboRunPaths:
    return WeiboRunPaths(
        posts_paths=[
            run_root / "search" / "weibo" / "jsonl" / "search_contents_2026-05-21.jsonl",
            run_root / "search_more" / "weibo" / "jsonl" / "search_contents_2026-05-21.jsonl",
        ],
        comments_paths=[
            run_root / "search" / "weibo" / "jsonl" / "search_comments_2026-05-21.jsonl",
            run_root / "search_more" / "weibo" / "jsonl" / "search_comments_2026-05-21.jsonl",
        ],
        post_details_path=run_root / "post_raw" / "weibo" / "jsonl" / "post_details_raw_2026-05-21.jsonl",
    )


def _merge_post_details(posts: list[dict[str, Any]], post_details_path: Path | None) -> list[dict[str, Any]]:
    if not post_details_path or not post_details_path.exists():
        return posts
    detail_map: dict[str, dict[str, Any]] = {}
    for row in _load_jsonl(post_details_path):
        note_id = str(row.get("note_id") or "").strip()
        if note_id:
            detail_map[note_id] = row
    merged: list[dict[str, Any]] = []
    for row in posts:
        note_id = str(row.get("note_id") or "").strip()
        new_row = dict(row)
        if note_id and note_id in detail_map:
            new_row["post_details_raw"] = detail_map[note_id]
            raw_payload = detail_map[note_id].get("raw")
            if isinstance(raw_payload, dict):
                hashtags = []
                page_info = raw_payload.get("page_info")
                if isinstance(page_info, dict):
                    page_title = str(page_info.get("page_title") or "").strip()
                    hashtags.extend(_extract_hashtags_from_text(page_title))
                hashtags.extend(_extract_hashtags_from_text(str(raw_payload.get("text") or "")))
                if hashtags:
                    new_row["hashtags"] = list(dict.fromkeys(hashtags))
        merged.append(new_row)
    return merged


def _note_url(note_id: str) -> str:
    return f"https://m.weibo.cn/detail/{note_id}"


def _build_coordination_rows(run_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    paths = _default_weibo_run_paths(run_root)
    post_rows: list[dict[str, Any]] = []
    for path in paths.posts_paths:
        if path.exists():
            post_rows.extend(_load_jsonl(path))
    comment_rows: list[dict[str, Any]] = []
    for path in paths.comments_paths:
        if path.exists():
            comment_rows.extend(_load_jsonl(path))

    posts = _merge_post_details(_dedupe_by_key(post_rows, "note_id"), paths.post_details_path)
    comments = _dedupe_by_key(comment_rows, "comment_id")
    rows: list[dict[str, Any]] = []

    stats = Counter()

    for raw in posts:
        post = weibo_content_line_to_post(raw, "weibo")
        account_id = str(post.author_id).strip()
        if not account_id:
            continue
        post_content = _strip_html(post.content)
        source_keyword = str(raw.get("source_keyword") or "").strip()

        rows.append(
            {
                "account_id": account_id,
                "relation": "profile",
                "object_id": f"profile:weibo:{account_id}",
                "timestamp": post.timestamp.isoformat(),
                "content_id": f"profile:{account_id}",
                "content": post_content,
                "target_account_id": "",
                "nickname": post.author_name,
                "platform": "weibo",
                "source_keyword": source_keyword,
                "post_id": post.post_id,
                "post_url": post.url or _note_url(post.post_id),
            }
        )
        stats["profile"] += 1

        for hashtag in list(dict.fromkeys(post.hashtags or _extract_hashtags_from_text(post_content))):
            rows.append(
                {
                    "account_id": account_id,
                    "relation": "hashtag_share",
                    "object_id": f"#{hashtag}",
                    "timestamp": post.timestamp.isoformat(),
                    "content_id": f"post:{post.post_id}:hashtag:{hashtag}",
                    "content": post_content,
                    "target_account_id": "",
                    "nickname": post.author_name,
                    "platform": "weibo",
                    "source_keyword": source_keyword,
                    "post_id": post.post_id,
                    "post_url": post.url or _note_url(post.post_id),
                }
            )
            stats["hashtag_share"] += 1

    for raw in comments:
        comment = weibo_comment_line_to_comment(raw, "weibo")
        account_id = str(comment.author_id).strip()
        if not account_id:
            continue
        note_id = str(comment.post_id).strip()
        content = _strip_html(comment.content)
        timestamp = comment.timestamp.isoformat()
        nickname = comment.author_name

        rows.append(
            {
                "account_id": account_id,
                "relation": "reply_target",
                "object_id": f"tweet:{note_id}",
                "timestamp": timestamp,
                "content_id": f"comment:{comment.comment_id}:reply_target",
                "content": content,
                "target_account_id": "",
                "nickname": nickname,
                "platform": "weibo",
                "source_keyword": "",
                "post_id": note_id,
                "post_url": _note_url(note_id),
                "comment_id": comment.comment_id,
            }
        )
        stats["reply_target"] += 1

        if comment.reply_to:
            rows.append(
                {
                    "account_id": account_id,
                    "relation": "reply_target",
                    "object_id": f"comment:{comment.reply_to}",
                    "timestamp": timestamp,
                    "content_id": f"comment:{comment.comment_id}:reply_parent",
                    "content": content,
                    "target_account_id": str(comment.reply_to),
                    "nickname": nickname,
                    "platform": "weibo",
                    "source_keyword": "",
                    "post_id": note_id,
                    "post_url": _note_url(note_id),
                    "comment_id": comment.comment_id,
                }
            )
            stats["reply_target_parent"] += 1

        for hashtag in list(dict.fromkeys(comment.hashtags or _extract_hashtags_from_text(content))):
            rows.append(
                {
                    "account_id": account_id,
                    "relation": "hashtag_share",
                    "object_id": f"#{hashtag}",
                    "timestamp": timestamp,
                    "content_id": f"comment:{comment.comment_id}:hashtag:{hashtag}",
                    "content": content,
                    "target_account_id": "",
                    "nickname": nickname,
                    "platform": "weibo",
                    "source_keyword": "",
                    "post_id": note_id,
                    "post_url": _note_url(note_id),
                    "comment_id": comment.comment_id,
                }
            )
            stats["comment_hashtag_share"] += 1

        for mention in _extract_mentions(content):
            rows.append(
                {
                    "account_id": account_id,
                    "relation": "mention_target",
                    "object_id": f"@{mention}",
                    "timestamp": timestamp,
                    "content_id": f"comment:{comment.comment_id}:mention:{mention}",
                    "content": content,
                    "target_account_id": f"@{mention}",
                    "nickname": nickname,
                    "platform": "weibo",
                    "source_keyword": "",
                    "post_id": note_id,
                    "post_url": _note_url(note_id),
                    "comment_id": comment.comment_id,
                }
            )
            stats["mention_target"] += 1

    frame = normalize_event_table(pd.DataFrame(rows))
    meta = {
        "posts": len(posts),
        "comments": len(comments),
        "event_rows": int(len(frame)),
        "relation_counts": dict(stats),
        "accounts": int(frame["account_id"].astype(str).nunique()) if not frame.empty else 0,
    }
    return frame, meta


async def _find_dataset_id_by_slug(slug: str) -> int | None:
    async with async_session_factory() as session:
        result = await session.execute(select(CoordinationDataset).where(CoordinationDataset.slug == slug))
        dataset = result.scalar_one_or_none()
        return int(dataset.id) if dataset is not None else None


async def _import_dataset(
    *,
    run_root: Path,
    display_name: str,
    output_csv: Path | None,
    created_by: int,
    trigger_run: bool,
) -> dict[str, Any]:
    frame, meta = _build_coordination_rows(run_root)
    if frame.empty:
        raise RuntimeError(f"No coordination rows were built from {run_root}")

    csv_payload = frame.to_csv(index=False).encode("utf-8")
    if output_csv is not None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        output_csv.write_bytes(csv_payload)

    async with async_session_factory() as session:
        dataset_record = await upload_coordination_dataset(
            db=session,
            filename=f"{display_name}.csv",
            content=csv_payload,
            created_by=created_by,
            display_name=display_name,
        )

    run_record = None
    if trigger_run:
        async with async_session_factory() as session:
            run_record = await create_coordination_run(
                db=session,
                dataset_id=int(dataset_record["dataset_id"]),
                created_by=created_by,
            )
        await run_coordination_model_job(int(run_record["run_id"]))

    return {
        "dataset": dataset_record,
        "run": run_record,
        "meta": meta,
        "output_csv": str(output_csv) if output_csv is not None else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a real Weibo MediaCrawler run into coordination datasets")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=BACKEND_DIR.parents[1] / "runtimes" / "social_runtime" / "data_runs" / "weibo_trump_visit_2026-05-21",
        help="Root folder of the vendored social runtime Weibo data run",
    )
    parser.add_argument(
        "--display-name",
        default="Weibo Trump Visit 2026-05-21",
        help="Dataset display name shown in /coordination",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=BACKEND_DIR / "tmp" / "real_weibo_trump_visit_2026_05_21_events.csv",
        help="Optional local export of the generated coordination event table",
    )
    parser.add_argument("--created-by", type=int, default=0, help="User id recorded in the dataset registry")
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Only register the dataset; do not trigger Discover/Detect rerun",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await _import_dataset(
        run_root=args.run_root,
        display_name=args.display_name,
        output_csv=args.output_csv,
        created_by=int(args.created_by),
        trigger_run=not args.no_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
