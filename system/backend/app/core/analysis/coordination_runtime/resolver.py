from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

from app.core.analysis.contracts import EventSnapshot, ProvenanceRecord

from .types import ResolvedSnapshotView


_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "gbraid",
    "wbraid",
    "igshid",
    "mc_cid",
    "mc_eid",
}
_CONTENT_URL_KEYS = {
    "url",
    "shared_url",
    "shared_urls",
    "link",
    "links",
}
_IDENTITY_URL_KEYS = {
    "profile_url",
    "homepage_url",
    "author_profile_url",
    "verified_url",
    "external_url",
    "website",
    "bio_url",
}
_ACCOUNT_STRONG_KEYS = {
    "profile_url",
    "homepage_url",
    "author_profile_url",
    "verified_url",
    "external_url",
    "website",
    "bio_url",
    "avatar_hash",
    "profile_image_hash",
    "external_id",
    "author_external_id",
    "account_external_id",
}
_ACCOUNT_WEAK_KEYS = {
    "author_name",
    "display_name",
    "screen_name",
    "nickname",
    "handle",
}
_TEXT_FIELDS = {
    "content",
    "text",
    "title",
    "desc",
    "summary",
    "comment",
    "caption",
}
_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


@dataclass(frozen=True, slots=True)
class _ResolvedAccountGroup:
    resolved_account_id: str
    original_account_ids: tuple[str, ...]
    strong_signals: tuple[str, ...]
    weak_signals: tuple[str, ...]
    platforms: tuple[str, ...]


class CrossPlatformResolver:
    def resolve(self, snapshot: EventSnapshot) -> ResolvedSnapshotView:
        post_rows = [dict(row) for row in snapshot.posts]
        comment_rows = [dict(row) for row in snapshot.comments]
        canonical_posts = [self._canonicalize_row(dict(row), kind="post") for row in post_rows]
        canonical_comments = [self._canonicalize_row(dict(row), kind="comment") for row in comment_rows]
        canonical_rows = [*canonical_posts, *canonical_comments]
        groups, blocked_same_name = self._cluster_accounts(canonical_rows)
        resolved_rows: list[dict[str, Any]] = []
        account_mapping: dict[str, str] = {}
        merged_groups: list[tuple[str, ...]] = []

        for group in groups:
            if len(group.original_account_ids) > 1:
                merged_groups.append(group.original_account_ids)
            for original_account_id in group.original_account_ids:
                account_mapping[original_account_id] = group.resolved_account_id

        for row in canonical_rows:
            platform = str(row.get("platform") or "unknown").strip() or "unknown"
            author_id = _required_text(row.get("author_id"), "author_id")
            original_account_id = f"{platform}:{author_id}"
            resolved_account_id = account_mapping.get(original_account_id, original_account_id)
            resolved_rows.append(self._rewrite_row(row, resolved_account_id=resolved_account_id))

        provenance = list(snapshot.provenance)
        provenance.append(
            ProvenanceRecord(
                source_type="analysis",
                source_id="cross_platform_resolver",
                platform="coordination",
                source_keyword="resolve",
                metadata={
                    "blocked_same_name_merge_count": blocked_same_name,
                    "cross_platform_merge_count": sum(1 for group in groups if len(group.original_account_ids) > 1),
                    "resolved_account_count": len({row["resolved_account_id"] for row in resolved_rows}),
                },
            )
        )
        resolved_snapshot = self._build_snapshot(snapshot, resolved_posts=resolved_rows[: len(canonical_posts)], resolved_comments=resolved_rows[len(canonical_posts) :], provenance=provenance)
        report = {
            "input_post_count": len(snapshot.posts),
            "input_comment_count": len(snapshot.comments),
            "resolved_row_count": len(resolved_rows),
            "resolved_account_count": len({row["resolved_account_id"] for row in resolved_rows}),
            "cross_platform_merge_count": sum(1 for group in groups if len(group.original_account_ids) > 1),
            "blocked_same_name_merge_count": blocked_same_name,
            "canonical_url_count": sum(len(row.get("normalized_urls") or []) for row in resolved_rows),
            "canonical_domain_count": sum(len(row.get("normalized_domains") or []) for row in resolved_rows),
            "canonical_topic_count": sum(len(row.get("normalized_topics") or []) for row in resolved_rows),
            "canonical_claim_count": sum(len(row.get("normalized_claims") or []) for row in resolved_rows),
        }
        return ResolvedSnapshotView(
            snapshot=resolved_snapshot,
            resolution_report=MappingProxyType(report),
            account_mapping=MappingProxyType(account_mapping),
            merged_account_groups=tuple(sorted(merged_groups)),
        )

    def _canonicalize_row(self, row: dict[str, Any], *, kind: str) -> dict[str, Any]:
        normalized = dict(row)
        normalized["platform"] = str(normalized.get("platform") or "unknown").strip() or "unknown"
        author_id = _required_text(normalized.get("author_id"), "author_id")
        normalized["author_id"] = author_id
        normalized["kind"] = kind

        urls = _normalize_text_list(_iter_text_values(row, _CONTENT_URL_KEYS), transform=_canonical_url)
        identity_urls = _normalize_text_list(_iter_text_values(row, _IDENTITY_URL_KEYS), transform=_canonical_url)
        domains = _normalize_text_list((_url_domain(url) for url in urls), transform=_normalize_domain)
        topics = _normalize_topic_list(_iter_text_values(row, {"hashtags", "keywords", "topics", "topic"}))
        claims = _normalize_claim_list(_content_claims(row))

        normalized["normalized_urls"] = urls
        normalized["identity_urls"] = identity_urls
        normalized["normalized_domains"] = domains
        normalized["normalized_topics"] = topics
        normalized["normalized_claims"] = claims
        normalized["hashtags"] = [f"#{topic}" for topic in topics]
        normalized["keywords"] = topics
        normalized["entities"] = _normalize_entity_list(
            [*_iter_text_values(row, {"entities", "entity_names"}), *topics, *claims]
        )
        normalized["raw_data"] = _normalize_nested_value(row.get("raw_data"))
        normalized["url"] = urls[0] if len(urls) == 1 else list(urls)
        normalized["shared_urls"] = list(urls)
        if domains:
            normalized["domain"] = domains[0] if len(domains) == 1 else list(domains)
        _identity_signals(normalized)
        return normalized

    def _rewrite_row(self, row: dict[str, Any], *, resolved_account_id: str) -> dict[str, Any]:
        rewritten = dict(row)
        original_account_id = f"{str(rewritten.get('platform') or 'unknown').strip() or 'unknown'}:{_required_text(rewritten.get('author_id'), 'author_id')}"
        rewritten["resolved_account_id"] = resolved_account_id
        rewritten["author_id"] = resolved_account_id
        rewritten["account_id"] = resolved_account_id
        rewritten["resolved_author_id"] = resolved_account_id
        rewritten["resolved_author_name"] = _canonical_display_name(rewritten)
        rewritten["discovery_account_id"] = original_account_id
        rewritten["source_account_id"] = original_account_id
        return rewritten

    def _cluster_accounts(
        self,
        rows: list[dict[str, Any]],
    ) -> tuple[list[_ResolvedAccountGroup], int]:
        parents = list(range(len(rows)))
        blocked_same_name = 0
        name_pairs: set[tuple[int, int]] = set()
        for left_index, left in enumerate(rows):
            for right_index in range(left_index + 1, len(rows)):
                right = rows[right_index]
                if left["platform"] == right["platform"]:
                    continue
                if _same_name(left, right):
                    name_pairs.add((left_index, right_index))
                if self._should_merge(left, right):
                    _union(parents, left_index, right_index)

        clusters: dict[int, list[int]] = defaultdict(list)
        for index in range(len(rows)):
            clusters[_find(parents, index)].append(index)

        groups: list[_ResolvedAccountGroup] = []
        for member_indexes in clusters.values():
            original_ids = tuple(
                sorted(
                    {
                        f"{rows[index]['platform']}:{rows[index]['author_id']}"
                        for index in member_indexes
                    }
                )
            )
            if len(original_ids) == 1:
                resolved_account_id = original_ids[0]
            else:
                resolved_account_id = _cross_platform_account_id(original_ids)
            strong_signals = tuple(
                sorted(
                    {
                        signal
                        for index in member_indexes
                        for signal in rows[index].get("_strong_identity_signals", ())
                    }
                )
            )
            weak_signals = tuple(
                sorted(
                    {
                        signal
                        for index in member_indexes
                        for signal in rows[index].get("_weak_identity_signals", ())
                    }
                )
            )
            platforms = tuple(sorted({str(rows[index]["platform"]) for index in member_indexes}))
            groups.append(
                _ResolvedAccountGroup(
                    resolved_account_id=resolved_account_id,
                    original_account_ids=original_ids,
                    strong_signals=strong_signals,
                    weak_signals=weak_signals,
                    platforms=platforms,
                )
            )

        for left_index, right_index in name_pairs:
            if _find(parents, left_index) != _find(parents, right_index):
                blocked_same_name += 1
        groups.sort(key=lambda group: group.resolved_account_id)
        return groups, blocked_same_name

    @staticmethod
    def _should_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
        shared_strong = set(left.get("_strong_identity_signals", ())) & set(right.get("_strong_identity_signals", ()))
        shared_weak = set(left.get("_weak_identity_signals", ())) & set(right.get("_weak_identity_signals", ()))
        return bool(shared_strong and (len(shared_strong) >= 2 or shared_weak))

    @staticmethod
    def _build_snapshot(
        snapshot: EventSnapshot,
        *,
        resolved_posts: list[dict[str, Any]],
        resolved_comments: list[dict[str, Any]],
        provenance: list[ProvenanceRecord],
    ) -> EventSnapshot:
        payload = snapshot.model_dump(mode="json")
        payload["posts"] = resolved_posts
        payload["comments"] = resolved_comments
        payload["provenance"] = [record.model_dump(mode="json") for record in provenance]
        payload["data_fingerprint"] = _fingerprint(
            {
                "event_id": payload["event_id"],
                "core_window": payload["core_window"],
                "context_window": payload["context_window"],
                "posts": payload["posts"],
                "comments": payload["comments"],
                "relationships": payload["relationships"],
                "provenance": payload["provenance"],
            }
        )
        return EventSnapshot.model_validate(payload)


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _iter_text_values(row: dict[str, Any], keys: set[str]) -> list[str]:
    values: list[str] = []
    for key, value in row.items():
        if key in keys:
            values.extend(_flatten(value))
    return values


def _flatten(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(_flatten(item))
        return values
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_flatten(item))
        return values
    return [str(value)]


def _normalize_text_list(values: list[str], *, transform) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = transform(value)
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return sorted(normalized)


def _canonical_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    scheme = parsed.scheme.lower() or "https"
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if not hostname:
        return ""
    port = parsed.port
    netloc = hostname
    if port and port not in {80, 443}:
        netloc = f"{netloc}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "")
    path = path if path == "/" else path.rstrip("/")
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")
    ]
    query = urlencode(sorted(query_items), doseq=True)
    canonical = urlunparse((scheme, netloc, path, "", query, ""))
    return canonical.rstrip("?")


def _url_domain(value: str) -> str:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _normalize_domain(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_topic_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = re.sub(r"[#@。、,.!！?？:：\s]+", "", str(value or "").strip()).lower()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return sorted(normalized)


def _content_claims(row: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    for key in _TEXT_FIELDS:
        parts.extend(_flatten(row.get(key)))
    normalized = _claim_signature(" ".join(part for part in parts if part))
    return [normalized] if normalized else []


def _normalize_claim_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").strip().lower())
        if not text:
            continue
        claim = f"claim:{text}"
        if claim in seen:
            continue
        seen.add(claim)
        normalized.append(claim)
    return sorted(normalized)


def _normalize_entity_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").strip().lower())
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return sorted(normalized)


def _normalize_nested_value(value: Any, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_nested_value(item, str(key))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        return [_normalize_nested_value(item, parent_key) for item in value]
    if isinstance(value, tuple):
        return [_normalize_nested_value(item, parent_key) for item in value]
    if isinstance(value, str):
        key = parent_key.lower()
        if any(marker in key for marker in ("url", "link", "source", "homepage", "website")):
            return _canonical_url(value) or value
        return value.strip()
    return value


def _claim_signature(text: str) -> str:
    tokens = [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text or "")]
    if len(tokens) < 6:
        return ""
    compact = " ".join(tokens[:12])
    digest = hashlib.sha1(compact.encode("utf-8")).hexdigest()[:12]
    return f"claim:{digest}"


def _canonical_display_name(row: dict[str, Any]) -> str:
    for key in ("author_name", "display_name", "screen_name", "nickname", "handle"):
        text = str(row.get(key) or "").strip()
        if text:
            return text
    return str(row.get("author_id") or "")


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _same_name(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return _display_name(left) and _display_name(left) == _display_name(right)


def _display_name(row: dict[str, Any]) -> str:
    for key in ("author_name", "display_name", "screen_name", "nickname", "handle"):
        text = str(row.get(key) or "").strip().lower()
        if text:
            return text
    return ""


def _identity_signals(row: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    strong: list[str] = []
    weak: list[str] = []
    for key in _ACCOUNT_STRONG_KEYS:
        value = row.get(key)
        text = str(value or "").strip()
        if not text:
            continue
        if key.endswith("url") or key.endswith("_url"):
            canonical = _canonical_url(text)
            if canonical:
                strong.append(f"{key}:{canonical}")
            continue
        strong.append(f"{key}:{text.lower()}")
    for key in _ACCOUNT_WEAK_KEYS:
        text = str(row.get(key) or "").strip().lower()
        if text:
            weak.append(f"{key}:{text}")
    row["_strong_identity_signals"] = tuple(sorted(set(strong)))
    row["_weak_identity_signals"] = tuple(sorted(set(weak)))
    return row["_strong_identity_signals"], row["_weak_identity_signals"]


def _cluster_key(row: dict[str, Any]) -> str:
    return f"{row.get('platform')}:{row.get('author_id')}"


def _cross_platform_account_id(original_account_ids: tuple[str, ...]) -> str:
    digest = hashlib.sha256("|".join(original_account_ids).encode("utf-8")).hexdigest()[:20]
    return f"cross_platform_account:{digest}"


def _find(parents: list[int], index: int) -> int:
    while parents[index] != index:
        parents[index] = parents[parents[index]]
        index = parents[index]
    return index


def _union(parents: list[int], left: int, right: int) -> None:
    left_root = _find(parents, left)
    right_root = _find(parents, right)
    if left_root == right_root:
        return
    parents[right_root] = left_root


__all__ = ["CrossPlatformResolver"]
