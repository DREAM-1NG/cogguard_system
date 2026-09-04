"""Focused result projection module."""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import PROJECT_ROOT
from app.core.coordination_detect import (
    PRETRAINED_CHECKPOINT_PATH,
    ensure_china_pretrained_fusion_checkpoint,
    extract_labels,
    run_china_pretrained_detect,
    run_dyna_colm_detect,
)
from app.core.coordination_discover import (
    DEFAULT_RELATIONS,
    build_unmasking_similarity_graphs,
    fuse_similarity_graphs,
    normalize_event_table,
    read_event_table,
    run_dyna_colm_discover,
)
from app.db.mysql import async_session_factory
from app.models.coordination_registry import CoordinationDataset, CoordinationRun

from app.services.coordination_registry_common import (
    MODEL_SIGNATURE,
    OBJECT_ID_RELATION_HINTS,
    RELATION_LABELS,
    _json_load,
    _safe_json_loads,
    _str_column,
)

def _load_run_result_pair(run: CoordinationRun) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact_dir = Path(run.artifact_dir)
    discover_path = artifact_dir / "discovery_summary.json"
    detect_path = artifact_dir / "detection_summary.json"
    if not discover_path.exists():
        raise FileNotFoundError(f"Missing discovery_summary.json for run {run.id}: {discover_path}")
    if not detect_path.exists():
        raise FileNotFoundError(f"Missing detection_summary.json for run {run.id}: {detect_path}")
    return _json_load(discover_path), _json_load(detect_path)


def _compact_top_objects(discovery: Mapping[str, Any], *, limit: int = 20) -> list[dict[str, Any]]:
    evidence = discovery.get("evidence_summary", {}) if isinstance(discovery.get("evidence_summary"), Mapping) else {}
    top_objects = evidence.get("top_objects", []) if isinstance(evidence, Mapping) else []
    items = []
    for item in top_objects[:limit]:
        if isinstance(item, Mapping):
            items.append(_format_top_object_item(item))
    return items


def _cluster_key(value: Any) -> str:
    return str(value if value is not None else "")


def _sort_cluster_value(value: Any) -> tuple[int, str]:
    try:
        return (0, f"{int(value):010d}")
    except Exception:
        return (1, str(value))


def _safe_score(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _relation_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return RELATION_LABELS.get(text.lower(), text)


def _is_raw_shared_object(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text and text.startswith(("http://", "https://", "#", "@", "tweet:", "target:")))


def _infer_relation_from_object_id(object_id: str) -> str:
    text = str(object_id or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return "url_share"
    if text.startswith("#"):
        return "hashtag_share"
    if text.startswith(("tweet:", "target:", "@")):
        return "retweet_target"
    prefix = text.split(":", 1)[0].strip().lower()
    return OBJECT_ID_RELATION_HINTS.get(prefix, "")


def _format_top_object_item(item: Mapping[str, Any]) -> dict[str, Any]:
    object_id = str(item.get("object_id") or "")
    relation = str(item.get("relation") or "")
    parts = object_id.split(":") if object_id else []
    if not relation:
        if _is_raw_shared_object(object_id):
            relation = _infer_relation_from_object_id(object_id)
        elif len(parts) >= 2:
            relation = OBJECT_ID_RELATION_HINTS.get(parts[1].strip().lower(), parts[1])
        elif parts:
            relation = OBJECT_ID_RELATION_HINTS.get(parts[0].strip().lower(), parts[0])
    normalized_relation = relation.lower()
    display_value = object_id
    if not _is_raw_shared_object(object_id):
        relation_hint = parts[1].strip().lower() if len(parts) >= 2 else ""
        if len(parts) >= 3 and relation_hint not in OBJECT_ID_RELATION_HINTS:
            display_value = parts[-1]
    readable_description = ""
    object_kind = "structured_object"
    if normalized_relation in {"url_share", "courl"}:
        object_kind = "url"
        readable_description = (
            f"该对象表示社区成员共享的 URL 标识：{display_value}。"
            if display_value.startswith("http")
            else f"该对象是 URL 共享证据的结构化标识：{display_value}。当前归档数据集中未保留原始完整 URL。"
        )
    elif normalized_relation in {"retweet_target", "cort"}:
        object_kind = "retweet_target"
        readable_description = f"该对象表示成员共同转推的目标推文/转推证据标识：{display_value}。当前归档数据集中未保留原始推文正文。"
    elif normalized_relation == "hashtag_share":
        object_kind = "hashtag"
        readable_description = f"该对象表示成员共同使用的话题标签：{display_value}。"
    elif normalized_relation in {"fast_retweet", "fastrt"}:
        object_kind = "fast_retweet"
        readable_description = f"该对象表示快速转推协同行为证据：{display_value}。"
    elif normalized_relation == "profile":
        object_kind = "profile"
        readable_description = f"该对象是账号画像/占位节点：{display_value}。"
    else:
        readable_description = f"该对象是 { _relation_label(normalized_relation) } 的结构化共享对象标识：{display_value}。"
    object_url = ""
    if display_value.startswith(("http://", "https://")):
        object_url = display_value
    elif object_id.startswith("tweet:"):
        note_id = object_id.split(":", 1)[1].strip()
        if note_id:
            object_url = f"https://m.weibo.cn/detail/{note_id}"
    return {
        "object_id": object_id,
        "relation": normalized_relation or None,
        "relation_label": _relation_label(normalized_relation),
        "display_value": display_value,
        "count": item.get("count"),
        "share": item.get("share"),
        "object_kind": object_kind,
        "readable_description": readable_description,
        "has_raw_value": _is_raw_shared_object(display_value),
        "object_url": object_url or None,
    }


def _normalize_text_cell(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _truncate_text(value: Any, *, limit: int = 96) -> str:
    text = re.sub(r"\s+", " ", _normalize_text_cell(value)).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _extract_note_id_from_post_url(value: Any) -> str:
    text = _normalize_text_cell(value)
    if not text:
        return ""
    match = re.search(r"/detail/(\d+)", text)
    return match.group(1) if match else ""


def _extract_xhs_note_id_from_url(value: Any) -> str:
    text = _normalize_text_cell(value)
    if not text:
        return ""
    patterns = (
        r"/explore/([A-Za-z0-9]+)",
        r"/discovery/item/([A-Za-z0-9]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _extract_douyin_aweme_id_from_url(value: Any) -> str:
    text = _normalize_text_cell(value)
    if not text:
        return ""
    patterns = (
        r"/video/(\d+)",
        r"modal_id=(\d+)",
        r"/note/(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _load_dataset_event_frame(dataset: CoordinationDataset) -> pd.DataFrame | None:
    source_path = Path(str(dataset.source_path))
    if not source_path.exists():
        return None
    try:
        return read_event_table(source_path)
    except Exception:
        return None


def _normalize_platform_name(value: Any) -> str:
    text = _normalize_text_cell(value).lower()
    if not text:
        return ""
    if text in {"x", "twitter", "x/twitter"}:
        return "twitter"
    if text in {"weibo", "sina_weibo", "sina-weibo"}:
        return "weibo"
    if text in {"xiaohongshu", "xhs", "red", "rednote", "little_red_book"}:
        return "xiaohongshu"
    if text in {"douyin", "抖音", "dy"}:
        return "douyin"
    if text in {"tiktok", "tik_tok"}:
        return "tiktok"
    return text


def _default_dataset_platform(dataset: CoordinationDataset, dataset_events: pd.DataFrame | None = None) -> str:
    if dataset_events is not None and not dataset_events.empty and "platform" in dataset_events.columns:
        platform_series = (
            dataset_events["platform"]
            .fillna("")
            .astype(str)
            .map(_normalize_platform_name)
        )
        non_empty = platform_series[platform_series != ""]
        if not non_empty.empty:
            counts = non_empty.value_counts()
            if not counts.empty:
                return str(counts.index[0])

    dataset_text = f"{dataset.slug} {dataset.display_name} {dataset.source_type}".lower()
    if "weibo" in dataset_text:
        return "weibo"
    if "xiaohongshu" in dataset_text or "xhs" in dataset_text:
        return "xiaohongshu"
    if "douyin" in dataset_text:
        return "douyin"
    if dataset.source_type == "system_archive":
        return "twitter"
    return ""


def _build_account_profile_url(
    *,
    platform: str,
    account_id: str,
    screen_name: str,
    explicit_url: str = "",
) -> str:
    if explicit_url:
        return explicit_url
    normalized_platform = _normalize_platform_name(platform)
    normalized_account_id = _normalize_text_cell(account_id)
    normalized_screen_name = _normalize_text_cell(screen_name).lstrip("@")

    if normalized_platform == "weibo" and normalized_account_id:
        return f"https://m.weibo.cn/u/{normalized_account_id}"

    if normalized_platform == "twitter":
        if normalized_screen_name:
            return f"https://x.com/{normalized_screen_name}"
        if normalized_account_id.isdigit():
            return f"https://x.com/i/user/{normalized_account_id}"

    if normalized_platform == "xiaohongshu" and normalized_account_id:
        return f"https://www.xiaohongshu.com/user/profile/{normalized_account_id}"

    if normalized_platform in {"douyin", "tiktok"} and normalized_account_id:
        return f"https://www.douyin.com/user/{normalized_account_id}"
    return ""


def _build_account_profile_map(
    dataset: CoordinationDataset,
    *,
    account_ids: set[str],
    discovery_nodes: Sequence[Mapping[str, Any]] | None = None,
    dataset_events: pd.DataFrame | None = None,
) -> dict[str, dict[str, Any]]:
    if not account_ids:
        return {}

    profiles: dict[str, dict[str, Any]] = {}
    default_platform = _default_dataset_platform(dataset, dataset_events)

    for node in discovery_nodes or []:
        if not isinstance(node, Mapping):
            continue
        account_id = _normalize_text_cell(node.get("account_id"))
        if not account_id or account_id not in account_ids:
            continue
        nickname = _normalize_text_cell(node.get("nickname") or node.get("screen_name"))
        screen_name = _normalize_text_cell(node.get("screen_name"))
        platform = _normalize_platform_name(node.get("platform")) or default_platform
        profile_url = _build_account_profile_url(
            platform=platform,
            account_id=account_id,
            screen_name=screen_name,
        )
        profiles[account_id] = {
            "account_id": account_id,
            "nickname": nickname or account_id,
            "screen_name": screen_name or None,
            "platform": platform or None,
            "profile_url": profile_url or None,
        }

    if dataset_events is None or dataset_events.empty or "account_id" not in dataset_events.columns:
        return profiles

    event_rows = dataset_events[dataset_events["account_id"].astype(str).isin(account_ids)].copy()
    if event_rows.empty:
        return profiles

    best_candidates: dict[str, tuple[tuple[int, int, int, int, int], dict[str, Any]]] = {}
    for _, row in event_rows.iterrows():
        account_id = _normalize_text_cell(row.get("account_id"))
        if not account_id:
            continue
        nickname = _normalize_text_cell(row.get("nickname") or row.get("screen_name"))
        screen_name = _normalize_text_cell(row.get("screen_name"))
        explicit_url = _normalize_text_cell(
            row.get("profile_url")
            or row.get("account_url")
            or row.get("user_url")
            or row.get("author_url")
        )
        platform = _normalize_platform_name(row.get("platform")) or default_platform
        profile_url = _build_account_profile_url(
            platform=platform,
            account_id=account_id,
            screen_name=screen_name,
            explicit_url=explicit_url,
        )
        content_len = len(_normalize_text_cell(row.get("content")))
        score = (
            1 if nickname else 0,
            1 if screen_name else 0,
            1 if platform else 0,
            1 if profile_url else 0,
            content_len,
        )
        candidate = {
            "account_id": account_id,
            "nickname": nickname or account_id,
            "screen_name": screen_name or None,
            "platform": platform or None,
            "profile_url": profile_url or None,
        }
        previous = best_candidates.get(account_id)
        if previous is None or score > previous[0]:
            best_candidates[account_id] = (score, candidate)

    for account_id, (_score, candidate) in best_candidates.items():
        profiles[account_id] = candidate

    for account_id in account_ids:
        if account_id not in profiles:
            profiles[account_id] = {
                "account_id": account_id,
                "nickname": account_id,
                "screen_name": None,
                "platform": default_platform or None,
                "profile_url": _build_account_profile_url(
                    platform=default_platform,
                    account_id=account_id,
                    screen_name="",
                )
                or None,
            }
    return profiles


def _build_community_event_frame(dataset: CoordinationDataset, member_ids: set[str]) -> pd.DataFrame | None:
    if not member_ids:
        return None
    events = _load_dataset_event_frame(dataset)
    if events is None or events.empty or "account_id" not in events.columns:
        return None
    return events[events["account_id"].astype(str).isin(member_ids)].copy()


def _resolve_shared_object_text(
    dataset_events: pd.DataFrame | None,
    *,
    object_id: str,
    relation: str,
) -> dict[str, Any]:
    if dataset_events is None or dataset_events.empty:
        return {}

    normalized_relation = str(relation or "").strip().lower()
    object_text = str(object_id or "").strip()
    if not object_text:
        return {}

    rows = dataset_events.copy()

    if "post_url" in rows.columns:
        if object_text.startswith("tweet:"):
            note_id = object_text.split(":", 1)[1].strip()
            if note_id:
                post_url_note_ids = rows["post_url"].map(_extract_note_id_from_post_url)
                matched_rows = rows[post_url_note_ids == note_id].copy()
                if not matched_rows.empty:
                    matched_rows["relation_rank"] = _str_column(matched_rows, "relation").str.lower().map(
                        {"profile": 0, "hashtag_share": 1, "reply_target": 2}
                    ).fillna(3)
                    matched_rows["content_len"] = _str_column(matched_rows, "content").str.len()
                    matched_rows = matched_rows.sort_values(
                        by=["relation_rank", "content_len"],
                        ascending=[True, False],
                        kind="stable",
                    )
                    best = matched_rows.iloc[0]
                    resolved_text = _truncate_text(best.get("content"), limit=140)
                    resolved_url = _normalize_text_cell(best.get("post_url"))
                    if resolved_text:
                        return {
                            "display_value": resolved_text,
                            "object_url": resolved_url or f"https://m.weibo.cn/detail/{note_id}",
                            "resolved_from": "post_content",
                        }
                    return {"object_url": resolved_url or f"https://m.weibo.cn/detail/{note_id}"}

        if object_text.startswith("note:"):
            note_id = object_text.split(":", 1)[1].strip()
            if note_id:
                xhs_note_ids = rows["post_url"].map(_extract_xhs_note_id_from_url)
                matched_rows = rows[xhs_note_ids == note_id].copy()
                if not matched_rows.empty:
                    matched_rows["content_len"] = _str_column(matched_rows, "content").str.len()
                    matched_rows = matched_rows.sort_values(by=["content_len"], ascending=[False], kind="stable")
                    best = matched_rows.iloc[0]
                    resolved_text = _truncate_text(best.get("content"), limit=140)
                    resolved_url = _normalize_text_cell(best.get("post_url"))
                    if resolved_text:
                        return {
                            "display_value": resolved_text,
                            "object_url": resolved_url or f"https://www.xiaohongshu.com/explore/{note_id}",
                            "resolved_from": "xhs_note_content",
                        }
                    return {"object_url": resolved_url or f"https://www.xiaohongshu.com/explore/{note_id}"}

        if object_text.startswith(("video:", "aweme:")):
            aweme_id = object_text.split(":", 1)[1].strip()
            if aweme_id:
                aweme_ids = rows["post_url"].map(_extract_douyin_aweme_id_from_url)
                matched_rows = rows[aweme_ids == aweme_id].copy()
                if not matched_rows.empty:
                    matched_rows["content_len"] = _str_column(matched_rows, "content").str.len()
                    matched_rows = matched_rows.sort_values(by=["content_len"], ascending=[False], kind="stable")
                    best = matched_rows.iloc[0]
                    resolved_text = _truncate_text(best.get("content"), limit=140)
                    resolved_url = _normalize_text_cell(best.get("post_url"))
                    if resolved_text:
                        return {
                            "display_value": resolved_text,
                            "object_url": resolved_url or f"https://www.douyin.com/video/{aweme_id}",
                            "resolved_from": "douyin_video_content",
                        }
                    return {"object_url": resolved_url or f"https://www.douyin.com/video/{aweme_id}"}

    if object_text.startswith("tweet:"):
        note_id = object_text.split(":", 1)[1].strip()
        if not note_id:
            return {}
        matched_frames: list[pd.DataFrame] = []

        if "post_url" in rows.columns:
            post_url_note_ids = rows["post_url"].map(_extract_note_id_from_post_url)
            matched = rows[post_url_note_ids == note_id].copy()
            if not matched.empty:
                matched_frames.append(matched)

        if not matched_frames and "object_id" in rows.columns:
            matched = rows[rows["object_id"].astype(str) == object_text].copy()
            if not matched.empty:
                matched_frames.append(matched)

        if not matched_frames:
            return {}

        matched_rows = pd.concat(matched_frames, ignore_index=True).drop_duplicates()
        matched_rows["relation_rank"] = _str_column(matched_rows, "relation").str.lower().map(
            {
                "profile": 0,
                "hashtag_share": 1,
                "reply_target": 2,
            }
        ).fillna(3)
        matched_rows["content_len"] = _str_column(matched_rows, "content").str.len()
        matched_rows = matched_rows.sort_values(
            by=["relation_rank", "content_len"],
            ascending=[True, False],
            kind="stable",
        )
        best = matched_rows.iloc[0]
        resolved_text = _truncate_text(best.get("content"), limit=140)
        resolved_url = _normalize_text_cell(best.get("post_url"))
        if resolved_text:
            return {
                "display_value": resolved_text,
                "object_url": resolved_url or f"https://m.weibo.cn/detail/{note_id}",
                "resolved_from": "post_content",
            }
        return {
            "object_url": resolved_url or f"https://m.weibo.cn/detail/{note_id}",
        }

    if object_text.startswith("comment:"):
        comment_id = object_text.split(":", 1)[1].strip()
        if not comment_id or "comment_id" not in dataset_events.columns:
            return {}
        matched_rows = dataset_events[dataset_events["comment_id"].astype(str) == comment_id].copy()
        if matched_rows.empty:
            return {}
        matched_rows["content_len"] = _str_column(matched_rows, "content").str.len()
        matched_rows = matched_rows.sort_values(by=["content_len"], ascending=[False], kind="stable")
        best = matched_rows.iloc[0]
        resolved_text = _truncate_text(best.get("content"), limit=140)
        resolved_url = _normalize_text_cell(best.get("post_url"))
        if resolved_text:
            return {
                "display_value": resolved_text,
                "object_url": resolved_url or None,
                "resolved_from": "comment_content",
            }
        return {
            "object_url": resolved_url or None,
        }

    if normalized_relation in {"url_share", "courl"} and object_text.startswith(("http://", "https://")):
        return {
            "display_value": object_text,
            "object_url": object_text,
            "resolved_from": "raw_url",
        }

    if "object_id" in rows.columns:
        matched_rows = rows[rows["object_id"].astype(str) == object_text].copy()
        if not matched_rows.empty:
            matched_rows["content_len"] = _str_column(matched_rows, "content").str.len()
            matched_rows = matched_rows.sort_values(by=["content_len"], ascending=[False], kind="stable")
            best = matched_rows.iloc[0]
            resolved_text = _truncate_text(best.get("content"), limit=140)
            resolved_url = _normalize_text_cell(best.get("post_url"))
            if resolved_text or resolved_url:
                return {
                    "display_value": resolved_text or object_text,
                    "object_url": resolved_url or None,
                    "resolved_from": "object_id_match",
                }

    return {}


def _extract_object_evidence_examples(
    community_events: pd.DataFrame | None,
    *,
    object_id: str,
    relation: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    if community_events is None or community_events.empty or "object_id" not in community_events.columns:
        return []
    rows = community_events[community_events["object_id"].astype(str) == str(object_id)].copy()
    if rows.empty:
        return []
    if relation and "relation" in rows.columns:
        relation_text = str(relation).strip().lower()
        relation_mask = rows["relation"].astype(str).str.lower() == relation_text
        if relation_mask.any():
            rows = rows[relation_mask].copy()
    if rows.empty:
        return []
    if "timestamp" in rows.columns:
        rows = rows.sort_values("timestamp", kind="stable")

    examples: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for _, row in rows.iterrows():
        account_id = _normalize_text_cell(row.get("account_id"))
        nickname = _normalize_text_cell(row.get("nickname") or row.get("screen_name"))
        content = _truncate_text(row.get("content"), limit=72)
        post_url = _normalize_text_cell(row.get("post_url"))
        unique_key = (account_id, content, post_url)
        if unique_key in seen:
            continue
        seen.add(unique_key)
        examples.append(
            {
                "account_id": account_id,
                "nickname": nickname or account_id,
                "content": content,
                "post_url": post_url or None,
                "timestamp": _normalize_text_cell(row.get("timestamp")) or None,
            }
        )
        if len(examples) >= limit:
            break
    return examples


def _enrich_top_object_item(
    item: Mapping[str, Any],
    *,
    community_events: pd.DataFrame | None,
    dataset_events: pd.DataFrame | None,
) -> dict[str, Any]:
    formatted = _format_top_object_item(item)
    relation = str(formatted.get("relation") or "")
    resolved = _resolve_shared_object_text(
        dataset_events,
        object_id=str(formatted.get("object_id") or ""),
        relation=relation,
    )
    examples = _extract_object_evidence_examples(
        community_events,
        object_id=str(formatted.get("object_id") or ""),
        relation=relation,
    )
    object_url = _normalize_text_cell(resolved.get("object_url") or formatted.get("object_url"))
    if not object_url:
        for example in examples:
            candidate = _normalize_text_cell(example.get("post_url"))
            if candidate:
                object_url = candidate
                break
    return {
        **formatted,
        "display_value": _normalize_text_cell(resolved.get("display_value")) or formatted.get("display_value"),
        "object_url": object_url or None,
        "evidence_examples": examples,
        "resolved_from": resolved.get("resolved_from"),
    }


def _build_relation_evidence(
    top_objects: Sequence[Mapping[str, Any]],
    relation_breakdown: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    relation_counts: Counter[str] = Counter()
    for item in top_objects:
        relation = str(item.get("relation") or "").strip().lower()
        if relation:
            relation_counts[relation] += int(item.get("count", 0) or 0)

    total_breakdown = 0
    if relation_breakdown:
        for value in relation_breakdown.values():
            try:
                total_breakdown += int(value or 0)
            except Exception:
                continue

    relation_keys = set(relation_counts.keys())
    if relation_breakdown:
        relation_keys.update(str(key).strip().lower() for key in relation_breakdown.keys())

    rows = []
    for relation in sorted(
        relation_keys,
        key=lambda item: (
            -int(relation_breakdown.get(item, relation_counts.get(item, 0)) if relation_breakdown else relation_counts.get(item, 0)),
            item,
        ),
    ):
        breakdown_count = 0
        if relation_breakdown:
            try:
                breakdown_count = int(relation_breakdown.get(relation, 0) or 0)
            except Exception:
                breakdown_count = 0
        top_object_count = int(relation_counts.get(relation, 0))
        rows.append(
            {
                "relation": relation,
                "relation_label": _relation_label(relation),
                "top_object_count": top_object_count,
                "relation_count": breakdown_count,
                "display_text": f"{_relation_label(relation)} · {top_object_count}/{breakdown_count or total_breakdown}",
            }
        )
    return rows


def _community_maps(discovery: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, list[Mapping[str, Any]]]]:
    communities = discovery.get("communities", []) if isinstance(discovery.get("communities"), list) else []
    discovery_nodes = discovery.get("nodes", []) if isinstance(discovery.get("nodes"), list) else []
    community_by_key = {
        _cluster_key(community.get("cluster_id")): community
        for community in communities
        if isinstance(community, Mapping)
    }
    members_by_cluster: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for node in discovery_nodes:
        if not isinstance(node, Mapping):
            continue
        members_by_cluster[_cluster_key(node.get("cluster_id"))].append(node)
    return community_by_key, members_by_cluster


def _prediction_maps(detect: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, float]]:
    predictions = detect.get("predictions", []) if isinstance(detect.get("predictions"), list) else []
    prediction_by_account: dict[str, Mapping[str, Any]] = {}
    score_by_account: dict[str, float] = {}
    for row in predictions:
        if not isinstance(row, Mapping):
            continue
        account_id = str(row.get("account_id"))
        prediction_by_account[account_id] = row
        score_by_account[account_id] = _safe_score(row.get("node_score"))
    return prediction_by_account, score_by_account


def _build_coordination_graph_payload(
    dataset: CoordinationDataset,
    discovery: Mapping[str, Any],
    detect: Mapping[str, Any],
    *,
    node_limit: int = 200,
    min_node_score: float = 0.0,
) -> dict[str, Any]:
    discovery_nodes = discovery.get("nodes", []) if isinstance(discovery.get("nodes"), list) else []
    discovery_edges = discovery.get("edges", []) if isinstance(discovery.get("edges"), list) else []
    community_by_key, members_by_cluster = _community_maps(discovery)
    _prediction_by_account, score_by_account = _prediction_maps(detect)
    dataset_events = _load_dataset_event_frame(dataset)
    account_ids = {
        str(node.get("account_id"))
        for node in discovery_nodes
        if isinstance(node, Mapping) and node.get("account_id") is not None
    }
    account_profiles = _build_account_profile_map(
        dataset,
        account_ids=account_ids,
        discovery_nodes=discovery_nodes,
        dataset_events=dataset_events,
    )
    threshold = max(0.0, float(min_node_score or 0.0))

    candidate_nodes = []
    for node in discovery_nodes:
        if not isinstance(node, Mapping):
            continue
        account_id = str(node.get("account_id"))
        profile = account_profiles.get(account_id, {})
        node_score = _safe_score(score_by_account.get(account_id, node.get("node_score")))
        if node_score < threshold:
            continue
        cluster_id = node.get("cluster_id")
        community = community_by_key.get(_cluster_key(cluster_id), {})
        candidate_nodes.append(
            {
                "id": account_id,
                "label": str(profile.get("nickname") or node.get("nickname") or node.get("screen_name") or account_id),
                "nickname": profile.get("nickname") or node.get("nickname") or node.get("screen_name"),
                "platform": profile.get("platform"),
                "profile_url": profile.get("profile_url"),
                "cluster_id": cluster_id,
                "node_score": round(node_score, 6),
                "community_score": community.get("community_score") if isinstance(community, Mapping) else None,
                "community_size": community.get("size") if isinstance(community, Mapping) else len(members_by_cluster.get(_cluster_key(cluster_id), [])),
            }
        )

    candidate_nodes.sort(
        key=lambda item: (
            -_safe_score(item.get("node_score")),
            _sort_cluster_value(item.get("cluster_id")),
            str(item.get("id")),
        )
    )
    raw_limit = int(node_limit or 0)
    capped_limit = len(candidate_nodes) if raw_limit <= 0 else max(1, min(raw_limit, 50000))
    rendered_nodes = candidate_nodes[:capped_limit]
    rendered_node_ids = {str(node["id"]) for node in rendered_nodes}

    rendered_links = []
    for edge in discovery_edges:
        if not isinstance(edge, Mapping):
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source not in rendered_node_ids or target not in rendered_node_ids:
            continue
        rendered_links.append(
            {
                "source": source,
                "target": target,
                "weight": edge.get("weight"),
                "edge_score": edge.get("edge_score"),
                "relations": edge.get("relations"),
            }
        )
    rendered_links.sort(
        key=lambda item: (
            -_safe_score(item.get("edge_score"), _safe_score(item.get("weight"))),
            str(item.get("source")),
            str(item.get("target")),
        )
    )

    return {
        "dataset_summary": {
            "dataset_id": dataset.id,
            "display_name": dataset.display_name,
            "source_type": dataset.source_type,
        },
        "nodes": rendered_nodes,
        "links": rendered_links,
        "summary": {
            "total_nodes": len(discovery_nodes),
            "total_edges": len(discovery_edges),
            "rendered_node_count": len(rendered_nodes),
            "rendered_edge_count": len(rendered_links),
            "filters": {
                "node_limit": capped_limit,
                "min_node_score": threshold,
            },
        },
    }


_TOPWORD_STOPWORDS = {
    "the",
    "and",
    "for",
    "are",
    "but",
    "with",
    "you",
    "your",
    "this",
    "that",
    "from",
    "have",
    "has",
    "was",
    "were",
    "will",
    "not",
    "all",
    "our",
    "their",
    "they",
    "them",
    "about",
    "http",
    "https",
    "com",
    "www",
    "一个",
    "我们",
    "你们",
    "他们",
    "她们",
    "这个",
    "那个",
    "这些",
    "那些",
    "以及",
    "不是",
    "没有",
    "进行",
    "已经",
}


def _tokenize_topwords(text: Any) -> list[str]:
    if text is None:
        return []
    raw = str(text).lower()
    tokens = re.findall(r"#[\w\u4e00-\u9fff-]+|[\w\u4e00-\u9fff-]+", raw)
    cleaned = []
    for token in tokens:
        token = token.strip("_-")
        if len(token) < 2:
            continue
        if token.isdigit():
            continue
        if token in _TOPWORD_STOPWORDS:
            continue
        cleaned.append(token)
    return cleaned


def _compute_community_topwords(dataset: CoordinationDataset, member_ids: set[str], *, limit: int = 20) -> list[dict[str, Any]]:
    if not member_ids:
        return []
    events = _build_community_event_frame(dataset, member_ids)
    if events is None or "content" not in events.columns:
        return []

    rows = events.copy()
    if "relation" in rows.columns:
        rows = rows[rows["relation"].astype(str).str.lower() != "profile"]

    frequency: Counter[str] = Counter()
    accounts_by_term: dict[str, set[str]] = defaultdict(set)
    for row in rows[["account_id", "content"]].itertuples(index=False):
        account_id = str(row.account_id)
        tokens = _tokenize_topwords(row.content)
        if not tokens:
            continue
        frequency.update(tokens)
        for token in set(tokens):
            accounts_by_term[token].add(account_id)

    ordered_terms = sorted(
        frequency.keys(),
        key=lambda term: (-len(accounts_by_term[term]), -frequency[term], term),
    )
    return [
        {
            "term": term,
            "account_count": len(accounts_by_term[term]),
            "frequency": int(frequency[term]),
        }
        for term in ordered_terms[:limit]
    ]


def _build_coordination_community_payload(
    dataset: CoordinationDataset,
    discovery: Mapping[str, Any],
    detect: Mapping[str, Any],
    *,
    cluster_id: str,
    member_limit: int = 500,
) -> dict[str, Any]:
    community_by_key, members_by_cluster = _community_maps(discovery)
    prediction_by_account, score_by_account = _prediction_maps(detect)
    cluster_key = _cluster_key(cluster_id)
    community = community_by_key.get(cluster_key)
    if community is None:
        raise ValueError(f"Community {cluster_id} not found")

    raw_top_objects = community.get("top_objects", []) if isinstance(community, Mapping) else []
    formatted_top_objects = [
        _format_top_object_item(item)
        for item in raw_top_objects
        if isinstance(item, Mapping)
    ]
    relation_breakdown = community.get("relation_breakdown", {}) if isinstance(community, Mapping) else {}

    members = []
    dataset_events = _load_dataset_event_frame(dataset)
    member_account_ids = {
        str(node.get("account_id"))
        for node in members_by_cluster.get(cluster_key, [])
        if isinstance(node, Mapping)
    }
    account_profiles = _build_account_profile_map(
        dataset,
        account_ids=member_account_ids,
        discovery_nodes=members_by_cluster.get(cluster_key, []),
        dataset_events=dataset_events,
    )
    for node in members_by_cluster.get(cluster_key, []):
        account_id = str(node.get("account_id"))
        prediction = prediction_by_account.get(account_id, {})
        profile = account_profiles.get(account_id, {})
        members.append(
            {
                "id": account_id,
                "label": str(node.get("nickname") or node.get("screen_name") or account_id),
                "nickname": profile.get("nickname") or node.get("nickname") or node.get("screen_name"),
                "platform": profile.get("platform"),
                "profile_url": profile.get("profile_url"),
                "node_score": round(_safe_score(score_by_account.get(account_id, node.get("node_score"))), 6),
                "predicted_label": prediction.get("predicted_label") if isinstance(prediction, Mapping) else None,
                "directed_out_weight": node.get("directed_out_weight"),
                "directed_in_weight": node.get("directed_in_weight"),
            }
        )
    members.sort(key=lambda item: (-_safe_score(item.get("node_score")), str(item.get("id"))))
    capped_member_limit = max(1, min(int(member_limit or 500), 2000))
    member_ids = {str(member["id"]) for member in members}
    community_events = _build_community_event_frame(dataset, member_ids)
    enriched_top_objects = [
        _enrich_top_object_item(
            item,
            community_events=community_events,
            dataset_events=dataset_events,
        )
        for item in raw_top_objects
        if isinstance(item, Mapping)
    ]

    return {
        "cluster_id": community.get("cluster_id"),
        "size": community.get("size", len(members)),
        "community_score": community.get("community_score"),
        "density": community.get("density"),
        "object_concentration": community.get("object_concentration"),
        "relation_breakdown": relation_breakdown,
        "members": members[:capped_member_limit],
        "topwords": _compute_community_topwords(dataset, member_ids),
        "top_objects": enriched_top_objects,
        "relation_evidence": _build_relation_evidence(enriched_top_objects, relation_breakdown if isinstance(relation_breakdown, Mapping) else {}),
    }


def _build_result_snapshot(
    dataset: CoordinationDataset,
    discovery: Mapping[str, Any],
    detect: Mapping[str, Any],
    *,
    result_source: str,
    run: CoordinationRun | None = None,
) -> dict[str, Any]:
    discovery_nodes = discovery.get("nodes", []) if isinstance(discovery.get("nodes"), list) else []
    discovery_edges = discovery.get("edges", []) if isinstance(discovery.get("edges"), list) else []
    communities = discovery.get("communities", []) if isinstance(discovery.get("communities"), list) else []
    predictions = detect.get("predictions", []) if isinstance(detect.get("predictions"), list) else []
    dataset_events = _load_dataset_event_frame(dataset)

    community_by_id = {
        community.get("cluster_id"): community
        for community in communities
        if isinstance(community, Mapping)
    }
    score_by_account = {
        str(row.get("account_id")): float(row.get("node_score", 0.0) or 0.0)
        for row in predictions
        if isinstance(row, Mapping)
    }
    node_record_map = {
        str(node.get("account_id")): node
        for node in discovery_nodes
        if isinstance(node, Mapping)
    }
    account_ids = {
        str(node.get("account_id"))
        for node in discovery_nodes
        if isinstance(node, Mapping) and node.get("account_id") is not None
    }
    account_profiles = _build_account_profile_map(
        dataset,
        account_ids=account_ids,
        discovery_nodes=discovery_nodes,
        dataset_events=dataset_events,
    )

    sorted_predictions = [
        row for row in predictions if isinstance(row, Mapping)
    ]
    sorted_predictions.sort(key=lambda row: (-float(row.get("node_score", 0.0) or 0.0), str(row.get("account_id"))))
    global_key_nodes = []
    for row in sorted_predictions[:60]:
        account_id = str(row.get("account_id"))
        community = community_by_id.get(row.get("cluster_id"), {})
        profile = account_profiles.get(account_id, {})
        shared_objects = [
            _format_top_object_item(item)
            for item in (community.get("top_objects", []) if isinstance(community, Mapping) else [])[:3]
            if isinstance(item, Mapping)
        ]
        global_key_nodes.append(
            {
                "account_id": account_id,
                "nickname": profile.get("nickname") or account_id,
                "platform": profile.get("platform"),
                "profile_url": profile.get("profile_url"),
                "node_score": round(float(row.get("node_score", 0.0) or 0.0), 6),
                "predicted_label": row.get("predicted_label"),
                "cluster_id": row.get("cluster_id"),
                "community_score": community.get("community_score") if isinstance(community, Mapping) else None,
                "community_size": community.get("size") if isinstance(community, Mapping) else None,
                "shared_objects": shared_objects,
            }
        )

    top_communities = [
        community for community in communities if isinstance(community, Mapping)
    ]
    top_communities.sort(key=lambda item: (-float(item.get("community_score", 0.0) or 0.0), int(item.get("cluster_id", 0) or 0)))
    top_communities = top_communities[:20]

    selected_node_ids: list[str] = []
    for community in top_communities[:12]:
        for node_id in community.get("top_nodes", [])[:8]:
            node_text = str(node_id)
            if node_text not in selected_node_ids:
                selected_node_ids.append(node_text)
    for row in global_key_nodes[:40]:
        node_text = str(row["account_id"])
        if node_text not in selected_node_ids:
            selected_node_ids.append(node_text)
    selected_node_ids = selected_node_ids[:180]
    selected_node_set = set(selected_node_ids)

    network_nodes = []
    for account_id in selected_node_ids:
        node = node_record_map.get(account_id, {})
        cluster_id = node.get("cluster_id")
        community = community_by_id.get(cluster_id, {})
        profile = account_profiles.get(account_id, {})
        network_nodes.append(
            {
                "id": account_id,
                "name": profile.get("nickname") or account_id,
                "nickname": profile.get("nickname") or account_id,
                "platform": profile.get("platform"),
                "profile_url": profile.get("profile_url"),
                "cluster_id": cluster_id,
                "node_score": round(float(score_by_account.get(account_id, node.get("node_score", 0.0) or 0.0)), 6),
                "community_score": community.get("community_score") if isinstance(community, Mapping) else None,
                "community_size": community.get("size") if isinstance(community, Mapping) else None,
                "directed_out_weight": node.get("directed_out_weight"),
                "directed_in_weight": node.get("directed_in_weight"),
            }
        )

    filtered_edges = []
    for edge in discovery_edges:
        if not isinstance(edge, Mapping):
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source in selected_node_set and target in selected_node_set:
            filtered_edges.append(edge)
    filtered_edges.sort(
        key=lambda item: (
            -float(item.get("edge_score", item.get("weight", 0.0)) or 0.0),
            str(item.get("source")),
            str(item.get("target")),
        )
    )
    filtered_edges = filtered_edges[:320]
    network_edges = [
        {
            "source": str(edge.get("source")),
            "target": str(edge.get("target")),
            "weight": edge.get("weight"),
            "edge_score": edge.get("edge_score"),
            "relations": edge.get("relations"),
        }
        for edge in filtered_edges
    ]

    has_labels = bool(dataset.has_labels)
    detect_metrics = detect.get("metrics", {}) if isinstance(detect.get("metrics"), Mapping) else {}
    unlabeled_inference = (
        detect.get("unlabeled_inference_summary", {})
        if isinstance(detect.get("unlabeled_inference_summary"), Mapping)
        else {}
    )
    detect_model = detect.get("detect_model", {}) if isinstance(detect.get("detect_model"), Mapping) else {}
    if run is not None:
        label_mode = run.label_mode
    else:
        label_mode = "labeled_mainline" if has_labels else "unlabeled_china_pretrained"

    run_summary = {
        "result_source": result_source,
        "status": run.status if run is not None else "archived",
        "run_id": run.id if run is not None else None,
        "created_at": run.created_at.isoformat() if run is not None and run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run is not None and run.finished_at else None,
        "label_mode": label_mode,
        "model_signature": MODEL_SIGNATURE,
        "actual_lm_feature_source": detect_model.get("lm_feature_source"),
        "pretrained_weight_path": detect_model.get("pretrained_metadata", {}).get("checkpoint_path")
        if isinstance(detect_model.get("pretrained_metadata"), Mapping)
        else None,
    }

    snapshot = {
        "dataset_summary": {
            "dataset_id": dataset.id,
            "slug": dataset.slug,
            "display_name": dataset.display_name,
            "source_type": dataset.source_type,
            "has_labels": bool(dataset.has_labels),
            "event_rows": int(dataset.event_rows),
            "account_nodes": int(dataset.account_nodes),
            "object_ids": int(dataset.object_ids),
            "user_user_edges": int(dataset.user_user_edges),
            "available_relations": _safe_json_loads(dataset.available_relations, []),
        },
        "run_summary": run_summary,
        "metrics": {
            "discover": discovery.get("metrics", {}) if isinstance(discovery.get("metrics"), Mapping) else {},
            "detect": detect_metrics if has_labels else {},
            "detect_inference": unlabeled_inference if not has_labels else {},
        },
        "network": {
            "nodes": network_nodes,
            "edges": network_edges,
            "total_nodes": len(discovery_nodes),
            "total_edges": len(discovery_edges),
            "rendered_node_count": len(network_nodes),
            "rendered_edge_count": len(network_edges),
            "truncated": len(network_nodes) < len(discovery_nodes) or len(network_edges) < len(discovery_edges),
        },
        "communities": [
            {
                "cluster_id": community.get("cluster_id"),
                "size": community.get("size"),
                "community_score": community.get("community_score"),
                "density": community.get("density"),
                "object_concentration": community.get("object_concentration"),
                "relation_breakdown": community.get("relation_breakdown"),
                "top_nodes": community.get("top_nodes", [])[:10],
                "top_objects": community.get("top_objects", [])[:5],
            }
            for community in top_communities
        ],
        "global_key_nodes": global_key_nodes,
        "shared_objects": _compact_top_objects(discovery),
        "model_signature": {
            **MODEL_SIGNATURE,
            "actual_lm_feature_source": detect_model.get("lm_feature_source"),
            "result_source": result_source,
            "pretrained_detect": "China pretrained detect" if not has_labels else None,
        },
        "label_status": {
            "has_labels": has_labels,
            "mode": label_mode,
            "shows_supervised_metrics": has_labels,
            "uses_pretrained_detect": not has_labels,
        },
    }
    return snapshot

__all__ = [
]
