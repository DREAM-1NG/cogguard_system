"""Normalization helpers for internal social runtime JSONL outputs."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.post import StandardComment, StandardPost

COMMENT_SORT_OPTIONS = {"none", "like_count_desc", "reply_count_desc"}
URL_PATTERN = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", re.IGNORECASE)
HASHTAG_BLOCK_PATTERN = re.compile(r"#([^#\r\n]{1,64})#")
HASHTAG_WORD_PATTERN = re.compile(r"(?<!\w)#([A-Za-z0-9_\-\u4e00-\u9fff]{1,64})")
SHARED_URL_FIELD_KEYS = {
    "shared_urls",
    "share_url",
    "content_url",
    "link_url",
    "jump_url",
    "web_url",
    "copy_link",
    "short_url",
    "schema",
}
SHARED_URL_CONTAINER_KEYS = {
    "share",
    "share_info",
    "share_data",
    "share_link",
    "link",
    "link_info",
    "link_data",
    "card",
    "card_info",
    "external",
    "external_link",
    "attachment",
    "attachments",
    "quote",
    "quoted",
    "jump",
    "web",
}
SHARED_URL_EXCLUDED_KEYS = {
    "avatar",
    "profile_url",
    "note_url",
    "aweme_url",
    "cover_url",
    "video_url",
    "video_download_url",
    "music_download_url",
    "note_download_url",
}


def parse_ts(value: Any) -> datetime:
    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        text = str(value).strip()
        if text.isdigit():
            timestamp = float(text)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, OSError):
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def to_int(*values: Any) -> int:
    unit_multiplier = {
        "\u4e07": 10_000,
        "w": 10_000,
        "W": 10_000,
        "\u4ebf": 100_000_000,
    }
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() == "none":
                continue
            value = value.replace(",", "").replace(" ", "")
            multiplier = 1
            if value[-1:] in unit_multiplier:
                multiplier = unit_multiplier[value[-1]]
                value = value[:-1]
            try:
                return int(float(value) * multiplier)
            except (TypeError, ValueError):
                continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0


def to_optional_int(*values: Any) -> int | None:
    unit_multiplier = {
        "\u4e07": 10_000,
        "w": 10_000,
        "W": 10_000,
        "\u4ebf": 100_000_000,
    }
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() == "none":
                continue
            value = value.replace(",", "").replace(" ", "")
            multiplier = 1
            if value[-1:] in unit_multiplier:
                multiplier = unit_multiplier[value[-1]]
                value = value[:-1]
            try:
                return int(float(value) * multiplier)
            except (TypeError, ValueError):
                continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return None


def to_optional_bool(*values: Any) -> bool | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if not text or text == "none":
            continue
        if text in {"1", "true", "yes", "y", "verified"}:
            return True
        if text in {"0", "false", "no", "n", "unverified"}:
            return False
    return None


def normalize_url(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("//"):
        return f"https:{text}"
    if text.startswith(("http://", "https://")):
        return text
    return None


def split_string_values(value: str) -> list[str]:
    text = value.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    parts = re.split(r"[\n,;|]+", text)
    return [part.strip() for part in parts if part.strip()]


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def extract_text_urls(text: str | None) -> list[str]:
    if not text:
        return []
    urls: list[str] = []
    for match in URL_PATTERN.findall(text):
        normalized = normalize_url(match.rstrip(".,!?;:'\")]}>"))
        if normalized:
            urls.append(normalized)
    return unique_preserve_order(urls)


def extract_text_hashtags(text: str | None) -> list[str]:
    if not text:
        return []
    hashtags: list[str] = []
    for match in HASHTAG_BLOCK_PATTERN.findall(text):
        tag = match.strip()
        if tag:
            hashtags.append(tag)
    for match in HASHTAG_WORD_PATTERN.findall(text):
        tag = match.strip()
        if tag:
            hashtags.append(tag)
    return unique_preserve_order(hashtags)


def collect_media_urls(target: list[str], value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str):
        for item in split_string_values(value):
            normalized = normalize_url(item)
            if normalized:
                target.append(normalized)
        return
    if isinstance(value, dict):
        for key in (
            "url",
            "urls",
            "src",
            "image_url",
            "video_url",
            "cover_url",
            "download_url",
            "origin_url",
            "play_url",
            "url_default",
        ):
            if key in value:
                collect_media_urls(target, value.get(key))
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            collect_media_urls(target, item)


def collect_direct_media_url(target: list[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    normalized = normalize_url(value)
    if normalized:
        target.append(normalized)


def collect_dict_url(target: list[str], value: Any, key: str = "url") -> None:
    if isinstance(value, dict):
        collect_direct_media_url(target, value.get(key))


def collect_weibo_page_info_media_urls(target: list[str], page_info: Any) -> None:
    if not isinstance(page_info, dict):
        return

    collect_dict_url(target, page_info.get("page_pic"))
    media_info = page_info.get("media_info")
    if isinstance(media_info, dict):
        for key in (
            "stream_url",
            "stream_url_hd",
            "mp4_sd_url",
            "mp4_hd_url",
            "mp4_720p_mp4",
            "mp4_1080p_mp4",
        ):
            collect_direct_media_url(target, media_info.get(key))

    urls = page_info.get("urls")
    if isinstance(urls, dict):
        for key, value in urls.items():
            key_text = str(key).lower()
            value_text = str(value).lower()
            if "mp4" in key_text or ".mp4" in value_text:
                collect_direct_media_url(target, value)


def collect_weibo_pic_media_urls(target: list[str], pics: Any) -> None:
    if not isinstance(pics, list):
        return
    for pic in pics:
        if isinstance(pic, str):
            collect_direct_media_url(target, pic)
            continue
        if not isinstance(pic, dict):
            continue
        collect_direct_media_url(target, pic.get("url"))
        collect_dict_url(target, pic.get("large"))


def collect_weibo_pic_infos_media_urls(target: list[str], pic_infos: Any) -> None:
    if not isinstance(pic_infos, dict):
        return
    for pic_info in pic_infos.values():
        if not isinstance(pic_info, dict):
            continue
        for key in ("thumbnail", "bmiddle", "large", "original"):
            collect_dict_url(target, pic_info.get(key))


def collect_weibo_mix_media_urls(target: list[str], mix_media_info: Any) -> None:
    if isinstance(mix_media_info, dict):
        items = mix_media_info.get("items") or []
    elif isinstance(mix_media_info, list):
        items = mix_media_info
    else:
        return

    for item in items:
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else item
        collect_weibo_pic_media_urls(target, data.get("pics"))
        collect_weibo_page_info_media_urls(target, data.get("page_info"))
        for key in ("thumbnail_pic", "bmiddle_pic", "original_pic"):
            collect_direct_media_url(target, data.get(key))


def collect_weibo_mblog_media_urls(target: list[str], mblog: Any) -> None:
    if not isinstance(mblog, dict):
        return

    collect_media_urls(target, mblog.get("media_urls"))
    collect_weibo_pic_media_urls(target, mblog.get("pics"))
    collect_weibo_pic_infos_media_urls(target, mblog.get("pic_infos"))
    for key in ("thumbnail_pic", "bmiddle_pic", "original_pic"):
        collect_direct_media_url(target, mblog.get(key))
    collect_weibo_page_info_media_urls(target, mblog.get("page_info"))
    collect_weibo_mix_media_urls(target, mblog.get("mix_media_info"))


def iter_weibo_mblog_payloads(raw: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = [raw]
    for key in ("mblog", "status"):
        value = raw.get(key)
        if isinstance(value, dict):
            payloads.append(value)

    detail_raw = raw.get("post_details_raw")
    if isinstance(detail_raw, dict):
        for key in ("raw", "mblog", "status"):
            value = detail_raw.get(key)
            if isinstance(value, dict):
                payloads.append(value)
                for nested_key in ("mblog", "status"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, dict):
                        payloads.append(nested_value)

    return payloads


def extract_media_urls(raw: dict[str, Any]) -> list[str]:
    collected: list[str] = []
    for key in (
        "media_urls",
        "image_list",
        "images",
        "pictures",
        "video_url",
        "video_download_url",
        "note_download_url",
        "music_download_url",
        "cover_url",
        "video_cover_url",
        "play_url",
    ):
        collect_media_urls(collected, raw.get(key))
    for payload in iter_weibo_mblog_payloads(raw):
        collect_weibo_mblog_media_urls(collected, payload)
    return unique_preserve_order(collected)


def extract_hashtags(raw: dict[str, Any]) -> list[str]:
    values = first_non_empty(raw.get("hashtags"), raw.get("tag_list"), raw.get("tags"))
    if values is None:
        return []
    if isinstance(values, (list, tuple, set)):
        return unique_preserve_order([str(item).strip() for item in values if str(item).strip()])
    if isinstance(values, dict):
        return unique_preserve_order([str(item).strip() for item in values.values() if str(item).strip()])
    if isinstance(values, str):
        return unique_preserve_order(split_string_values(values))
    return []


def normalize_key_name(value: Any) -> str:
    return str(value).strip().lower()


def is_shared_url_container(key: str) -> bool:
    if key in SHARED_URL_CONTAINER_KEYS or key in SHARED_URL_FIELD_KEYS:
        return True
    return key.endswith(("_card", "_info", "_link", "_attachment"))


def should_collect_shared_url_value(key: str, parent_key: str | None = None) -> bool:
    if key in SHARED_URL_FIELD_KEYS:
        return True
    return key in {"url", "urls"} and bool(parent_key) and is_shared_url_container(parent_key)


def collect_nested_shared_urls(
    target: list[str],
    value: Any,
    *,
    parent_key: str | None = None,
    depth: int = 0,
) -> None:
    if value is None or depth > 4:
        return
    if isinstance(value, dict):
        for key, nested_value in value.items():
            key_name = normalize_key_name(key)
            if should_collect_shared_url_value(key_name, parent_key):
                collect_media_urls(target, nested_value)
                if isinstance(nested_value, str):
                    target.extend(extract_text_urls(nested_value))
            if is_shared_url_container(key_name):
                collect_nested_shared_urls(target, nested_value, parent_key=key_name, depth=depth + 1)
        return
    if isinstance(value, (list, tuple, set)):
        for nested_value in value:
            collect_nested_shared_urls(target, nested_value, parent_key=parent_key, depth=depth + 1)


def shared_url_exclusions(raw: dict[str, Any]) -> set[str]:
    excluded: list[str] = []
    for key in SHARED_URL_EXCLUDED_KEYS:
        collect_media_urls(excluded, raw.get(key))
    excluded.extend(extract_media_urls(raw))
    return set(unique_preserve_order(excluded))


def extract_shared_urls(raw: dict[str, Any], text: str | None = None) -> list[str]:
    collected: list[str] = []
    for key in ("shared_urls", "url", "urls", "share_url", "content_url", "link_url", "jump_url", "web_url"):
        raw_value = raw.get(key)
        collect_media_urls(collected, raw_value)
        if isinstance(raw_value, str):
            collected.extend(extract_text_urls(raw_value))
    collect_nested_shared_urls(collected, raw)
    collected.extend(extract_text_urls(text))
    exclusions = shared_url_exclusions(raw)
    return [url for url in unique_preserve_order(collected) if url not in exclusions]


def extract_author_profile(raw: dict[str, Any]) -> dict[str, Any] | None:
    profile: dict[str, Any] = {}
    for key in (
        "user_id",
        "nickname",
        "avatar",
        "gender",
        "profile_url",
        "ip_location",
        "sec_uid",
        "short_user_id",
        "user_unique_id",
        "user_signature",
        "desc",
        "follows",
        "fans",
        "interaction",
        "videos_count",
        "tag_list",
        "xsec_token",
    ):
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        profile[key] = value
    verification_snapshot: dict[str, Any] = {}
    verified = to_optional_bool(
        raw.get("is_verified"),
        raw.get("verified"),
        raw.get("user_verified"),
        raw.get("author_verified"),
    )
    if verified is not None:
        verification_snapshot["is_verified"] = verified
    verification_type = first_non_empty(
        raw.get("verify_type"),
        raw.get("verified_type"),
        raw.get("verification_type"),
        raw.get("author_verification_type"),
    )
    if verification_type is not None:
        verification_snapshot["verification_type"] = str(verification_type).strip()
    verification_reason = first_non_empty(
        raw.get("verify_reason"),
        raw.get("verified_reason"),
        raw.get("verification_reason"),
        raw.get("author_verification_reason"),
    )
    if verification_reason is not None:
        verification_snapshot["verification_reason"] = str(verification_reason).strip()
    if verification_snapshot:
        profile["verification_snapshot"] = verification_snapshot
    followers_count = to_optional_int(
        raw.get("followers_count"),
        raw.get("follower_count"),
        raw.get("fans_count"),
        raw.get("fans"),
    )
    if followers_count is not None:
        profile["followers_count"] = followers_count
    following_count = to_optional_int(
        raw.get("following_count"),
        raw.get("follow_count"),
        raw.get("follows_count"),
        raw.get("follows"),
    )
    if following_count is not None:
        profile["following_count"] = following_count
    return profile or None


def normalize_reply_to(value: Any, comment_id: str | None = None) -> str | None:
    if value in (None, "", 0, "0"):
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    if comment_id and text == str(comment_id).strip():
        return None
    return text or None


def combine_title_desc(raw: dict[str, Any], platform: str) -> str:
    if platform == "xhs":
        parts: list[str] = []
        for value in (raw.get("title"), raw.get("desc")):
            if value is None:
                continue
            text = str(value).strip()
            if text and text not in parts:
                parts.append(text)
        return "\n".join(parts)
    return str(first_non_empty(raw.get("content"), raw.get("desc"), raw.get("title")) or "")


def build_standard_post(
    raw: dict[str, Any],
    platform: str,
    *,
    post_id: str,
    content: str,
    url: str,
) -> StandardPost:
    return StandardPost(
        platform=platform,
        post_id=post_id or str(hash(json.dumps(raw, sort_keys=True, default=str)))[:16],
        content=content,
        author_id=str(first_non_empty(raw.get("user_id"), raw.get("uid"), raw.get("author_id")) or ""),
        author_name=str(
            first_non_empty(
                raw.get("nickname"),
                raw.get("author_name"),
                raw.get("user_name"),
                raw.get("user_nickname"),
                "unknown",
            )
        ),
        timestamp=parse_ts(
            first_non_empty(
                raw.get("create_time"),
                raw.get("create_ts"),
                raw.get("time"),
                raw.get("publish_time"),
                raw.get("pub_ts"),
            )
        ),
        url=url,
        likes=to_int(raw.get("liked_count"), raw.get("digg_count"), raw.get("like_count")),
        reposts=to_int(raw.get("shared_count"), raw.get("share_count"), raw.get("repost_count")),
        comments_count=to_int(raw.get("comments_count"), raw.get("comment_count"), raw.get("video_comment")),
        media_urls=extract_media_urls(raw),
        hashtags=extract_hashtags(raw),
        author_profile=extract_author_profile(raw),
        raw_data=raw,
    )


def build_standard_comment(
    raw: dict[str, Any],
    platform: str,
    *,
    comment_id: str,
    post_id: str,
    content: str,
) -> StandardComment:
    comment_hashtags = unique_preserve_order(extract_hashtags(raw) + extract_text_hashtags(content))
    return StandardComment(
        platform=platform,
        comment_id=comment_id,
        post_id=post_id,
        content=content,
        author_id=str(first_non_empty(raw.get("user_id"), raw.get("uid"), raw.get("author_id")) or ""),
        author_name=str(
            first_non_empty(
                raw.get("nickname"),
                raw.get("author_name"),
                raw.get("user_name"),
                raw.get("user_nickname"),
                "unknown",
            )
        ),
        timestamp=parse_ts(
            first_non_empty(
                raw.get("create_time"),
                raw.get("time"),
                raw.get("publish_time"),
                raw.get("created_at"),
            )
        ),
        reply_to=normalize_reply_to(
            first_non_empty(raw.get("parent_comment_id"), raw.get("reply_to")),
            comment_id,
        ),
        likes=to_int(raw.get("comment_like_count"), raw.get("like_count"), raw.get("liked_count")),
        shared_urls=extract_shared_urls(raw, content),
        media_urls=extract_media_urls(raw),
        hashtags=comment_hashtags,
        sub_comment_count=to_int(raw.get("sub_comment_count")),
        author_profile=extract_author_profile(raw),
        raw_data=raw,
    )


def weibo_content_line_to_post(raw: dict[str, Any], platform: str) -> StandardPost:
    return build_standard_post(
        raw,
        platform,
        post_id=str(raw.get("note_id", "")),
        content=str(raw.get("content", "")),
        url=str(raw.get("note_url", "")),
    )


def weibo_comment_line_to_comment(raw: dict[str, Any], platform: str) -> StandardComment:
    return build_standard_comment(
        raw,
        platform,
        comment_id=str(raw.get("comment_id", "")),
        post_id=str(raw.get("note_id", "")),
        content=str(raw.get("content", "")),
    )


def generic_jsonl_to_post(raw: dict[str, Any], platform: str) -> StandardPost:
    return build_standard_post(
        raw,
        platform,
        post_id=str(
            first_non_empty(
                raw.get("note_id"),
                raw.get("aweme_id"),
                raw.get("id"),
                raw.get("video_id"),
                raw.get("content_id"),
            )
            or ""
        ),
        content=combine_title_desc(raw, platform),
        url=str(first_non_empty(raw.get("note_url"), raw.get("aweme_url"), raw.get("url"), raw.get("share_url")) or ""),
    )


def generic_jsonl_to_comment(raw: dict[str, Any], platform: str) -> StandardComment:
    return build_standard_comment(
        raw,
        platform,
        comment_id=str(first_non_empty(raw.get("comment_id"), raw.get("cid"), raw.get("id")) or ""),
        post_id=str(
            first_non_empty(
                raw.get("note_id"),
                raw.get("aweme_id"),
                raw.get("video_id"),
                raw.get("post_id"),
                raw.get("content_id"),
            )
            or ""
        ),
        content=str(first_non_empty(raw.get("content"), raw.get("text")) or ""),
    )


def sort_comments(comments: list[StandardComment], sort_mode: str = "none") -> list[StandardComment]:
    if sort_mode == "like_count_desc":
        return sorted(comments, key=lambda comment: (comment.likes, comment.sub_comment_count), reverse=True)
    if sort_mode == "reply_count_desc":
        return sorted(comments, key=lambda comment: (comment.sub_comment_count, comment.likes), reverse=True)
    return comments


def read_appended_jsonl_rows(path: Path, start_offset: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    file_size = path.stat().st_size
    seek_offset = start_offset if 0 <= start_offset <= file_size else 0
    rows: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        if seek_offset:
            handle.seek(seek_offset)
        for raw_line in handle:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows
