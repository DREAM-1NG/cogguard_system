"""Lightweight semantic enrichment for case-oriented analysis runs."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from app.core.analysis.contracts import EventSnapshot

EMBEDDING_MODEL_VERSION = "BAAI/bge-small-zh-v1.5@7999e1d"
SENTIMENT_MODEL_VERSION = "lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110"
STANCE_MODEL_VERSION = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92"
NER_MODEL_VERSION = "shibing624/bert4ner-base-chinese@5d660ed"

MODEL_STATUS = "candidate_unvalidated"
TECHNOLOGY = "semantic_enrichment"
TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_]{1,}")
ENTITY_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]{2,}(?:新闻|日报|社|网|央视|新华社|白宫|中国|美国|特朗普|北京|华盛顿)")

POSITIVE_TERMS = {
    "欢迎",
    "稳定",
    "合作",
    "平稳",
    "正确",
    "积极",
    "友好",
    "共识",
    "历史性",
    "推动",
}
NEGATIVE_TERMS = {
    "质疑",
    "冲突",
    "风险",
    "攻击",
    "反对",
    "谣言",
    "操纵",
    "煽动",
    "抹黑",
    "担忧",
}
STOP_TERMS = {
    "一个",
    "一些",
    "我们",
    "他们",
    "这个",
    "那个",
    "进行",
    "相关",
    "大量",
    "网友",
}


class SemanticEnrichmentEngine:
    """Deterministic semantic helper used when model bytes are unavailable."""

    async def analyze(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        return analyze_semantic_enrichment_snapshot(snapshot, options)


def analyze_semantic_enrichment_snapshot(
    snapshot: EventSnapshot,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return case-facing semantic artifacts without changing core risk scores."""

    options = dict(options or {})
    primary_claim = _primary_claim_text(options)
    main_posts = _content_rows(snapshot.posts, content_kind="main_post")
    comments = _content_rows(snapshot.comments, content_kind="comment")
    all_rows = [*main_posts, *comments]

    sentiment = {
        "summary": _sentiment_summary(all_rows),
        "main_posts": _sentiment_summary(main_posts),
        "comments": _sentiment_summary(comments),
    }
    keywords = {
        "main_posts": _keywords(main_posts),
        "comments": _keywords(comments),
    }
    topics = {
        "main_posts": _topics(main_posts),
        "comments": _topics(comments),
    }
    entities = {
        "main_posts": _entities(main_posts),
        "comments": _entities(comments),
    }
    near_duplicates = {
        "main_posts": _near_duplicates(main_posts),
        "comments": _near_duplicates(comments),
    }
    community_comparison = _community_comparison(main_posts, comments)
    stance = _stance(all_rows, primary_claim)
    status = "partial" if stance.get("status") == "blocked" else "ok"

    payload = {
        "schema_version": "cogguard.semantic_enrichment.v1",
        "technology": TECHNOLOGY,
        "status": status,
        "model_status": MODEL_STATUS,
        "model_version": "semantic-rule-overlay-v1",
        "candidate_models": {
            "embedding": EMBEDDING_MODEL_VERSION,
            "sentiment": SENTIMENT_MODEL_VERSION,
            "stance": STANCE_MODEL_VERSION,
            "ner": NER_MODEL_VERSION,
        },
        "validation_status": MODEL_STATUS,
        "snapshot_id": snapshot.snapshot_id,
        "event_id": snapshot.event_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "platforms": list(snapshot.platforms),
            "main_posts": len(main_posts),
            "comments": len(comments),
            "total_texts": len(all_rows),
        },
        "sentiment": sentiment,
        "keywords": keywords,
        "topics": topics,
        "entities": entities,
        "stance": stance,
        "near_duplicates": near_duplicates,
        "community_comparison": community_comparison,
        "provenance": {
            "embedding_reuse": "shared_text_token_pass",
            "device": "cpu",
            "degradation_reason": "model_bytes_not_required_for_mvp_rule_overlay",
            "score_policy": "semantic_artifacts_are_evidence_overlay_only",
            "does_not_modify": [
                "coordination_discover",
                "propagation_analysis",
                "student",
                "teacher",
            ],
        },
        "claimability": "non_claimable",
    }
    payload["artifact_sha256"] = _sha256(payload)
    return payload


def _content_rows(rows: Iterable[dict[str, Any]], *, content_kind: str) -> list[dict[str, Any]]:
    normalized = []
    id_key = "post_id" if content_kind == "main_post" else "comment_id"
    for row in rows:
        text = _text(row.get("content") or row.get("text") or row.get("title") or "")
        if not text:
            continue
        content_id = str(row.get(id_key) or row.get("post_id") or "").strip()
        normalized.append(
            {
                "content_id": content_id,
                "content_kind": content_kind,
                "post_id": str(row.get("post_id") or "").strip(),
                "author_id": str(row.get("author_id") or "").strip(),
                "author_name": str(row.get("author_name") or row.get("nickname") or row.get("author_id") or "").strip(),
                "platform": str(row.get("platform") or "unknown").strip(),
                "timestamp": str(row.get("timestamp") or row.get("created_at") or ""),
                "text": text,
                "tokens": _tokens(text),
            }
        )
    return normalized


def _sentiment_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {"positive": [], "negative": [], "neutral": []}
    score_total = 0.0
    for row in rows:
        label, score = _sentiment(row["text"])
        counts[label] += 1
        score_total += score
        if len(examples[label]) < 3:
            examples[label].append(_example(row, score=score))
    total = len(rows)
    return {
        "total_texts": total,
        "distribution": {key: counts.get(key, 0) for key in ("positive", "neutral", "negative")},
        "average_score": round(score_total / total, 4) if total else 0.0,
        "examples": examples,
    }


def _sentiment(text: str) -> tuple[str, float]:
    positive = sum(1 for term in POSITIVE_TERMS if term in text)
    negative = sum(1 for term in NEGATIVE_TERMS if term in text)
    raw = positive - negative
    if raw > 0:
        return "positive", min(1.0, 0.55 + 0.12 * raw)
    if raw < 0:
        return "negative", max(0.0, 0.45 + 0.12 * raw)
    return "neutral", 0.5


def _keywords(rows: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    doc_counts: Counter[str] = Counter()
    total_docs = len(rows) or 1
    for row in rows:
        tokens = [token for token in row["tokens"] if token not in STOP_TERMS]
        counts.update(tokens)
        doc_counts.update(set(tokens))
    scored = []
    for term, count in counts.items():
        if len(term) < 2:
            continue
        idf = math.log((1 + total_docs) / (1 + doc_counts[term])) + 1
        scored.append(
            {
                "term": term,
                "score": round(float(count) * idf, 4),
                "count": int(count),
                "document_count": int(doc_counts[term]),
            }
        )
    return sorted(scored, key=lambda item: (item["score"], item["count"], item["term"]), reverse=True)[:limit]


def _topics(rows: list[dict[str, Any]], *, limit: int = 6) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _topic_key(row["tokens"])
        grouped[key].append(row)
    topics = []
    for index, (key, members) in enumerate(sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:limit], 1):
        topics.append(
            {
                "topic_id": f"topic_{index}",
                "label": key,
                "size": len(members),
                "keywords": [item["term"] for item in _keywords(members, limit=5)],
                "representative_text": members[0]["text"][:160],
            }
        )
    return {
        "topic_count": len(topics),
        "method": "lightweight_cluster_plus_class_tfidf",
        "items": topics,
    }


def _topic_key(tokens: list[str]) -> str:
    for token in tokens:
        if token not in STOP_TERMS:
            return token
    return "general_discussion"


def _entities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    platforms: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for entity in _extract_entities(row["text"]):
            counts[entity] += 1
            platforms[entity].add(row["platform"])
    return [
        {
            "entity": entity,
            "count": int(count),
            "platforms": sorted(platforms[entity]),
            "entity_type": _entity_type(entity),
        }
        for entity, count in counts.most_common(20)
    ]


def _extract_entities(text: str) -> list[str]:
    entities = set(ENTITY_PATTERN.findall(text))
    for term in ("特朗普", "中国", "美国", "中美关系", "央视新闻", "新华社", "白宫", "北京"):
        if term in text:
            entities.add(term)
    return sorted(entities)


def _entity_type(entity: str) -> str:
    if entity in {"中国", "美国", "北京", "华盛顿"}:
        return "location_or_country"
    if entity in {"央视新闻", "新华社"} or entity.endswith(("新闻", "日报", "社", "网")):
        return "organization"
    return "person_or_topic" if "特朗普" in entity else "named_entity"


def _stance(rows: list[dict[str, Any]], primary_claim: str | None) -> dict[str, Any]:
    if not primary_claim:
        return {
            "status": "blocked",
            "code": "blocked_missing_primary_claim",
            "message": "Stance requires an approved Primary Claim; other semantic artifacts remain available.",
        }
    claim_tokens = set(_tokens(primary_claim))
    distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    for row in rows:
        overlap = len(claim_tokens & set(row["tokens"]))
        label = "support" if overlap >= 2 else "neutral"
        if any(term in row["text"] for term in ("质疑", "反对", "辟谣", "不实")):
            label = "deny"
        distribution[label] += 1
        if len(examples) < 5:
            examples.append({**_example(row), "stance": label, "overlap": overlap})
    return {
        "status": "ok",
        "primary_claim_hash": hashlib.sha256(primary_claim.encode("utf-8")).hexdigest(),
        "distribution": dict(distribution),
        "examples": examples,
    }


def _near_duplicates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        normalized = "".join(row["tokens"])[:48]
        if normalized:
            buckets[normalized].append(row)
    groups = []
    for index, members in enumerate((values for values in buckets.values() if len(values) > 1), 1):
        groups.append(
            {
                "group_id": f"near_duplicate_{index}",
                "size": len(members),
                "content_ids": [member["content_id"] for member in members],
                "representative_text": members[0]["text"][:160],
            }
        )
    return groups[:20]


def _community_comparison(main_posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> dict[str, Any]:
    platform_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in [*main_posts, *comments]:
        platform_rows[row["platform"]].append(row)
    return {
        "group_by": "platform",
        "items": [
            {
                "community_id": platform,
                "texts": len(rows),
                "top_keywords": [item["term"] for item in _keywords(rows, limit=5)],
                "sentiment": _sentiment_summary(rows)["distribution"],
            }
            for platform, rows in sorted(platform_rows.items())
        ],
    }


def _primary_claim_text(options: dict[str, Any]) -> str | None:
    for key in ("primary_claim", "primary_claim_text", "approved_primary_claim"):
        value = options.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            text = value.get("excerpt") or value.get("claim_text") or value.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _tokens(text: str) -> list[str]:
    tokens = [token.lower() for token in TOKEN_PATTERN.findall(text)]
    if tokens:
        return tokens
    return [char for char in text if "\u4e00" <= char <= "\u9fff"]


def _example(row: dict[str, Any], *, score: float | None = None) -> dict[str, Any]:
    payload = {
        "content_id": row["content_id"],
        "content_kind": row["content_kind"],
        "platform": row["platform"],
        "author_id": row["author_id"],
        "excerpt": row["text"][:120],
    }
    if score is not None:
        payload["score"] = round(float(score), 4)
    return payload


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _sha256(payload: dict[str, Any]) -> str:
    stable = {key: value for key, value in payload.items() if key != "artifact_sha256"}
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


__all__ = [
    "EMBEDDING_MODEL_VERSION",
    "NER_MODEL_VERSION",
    "SENTIMENT_MODEL_VERSION",
    "STANCE_MODEL_VERSION",
    "SemanticEnrichmentEngine",
    "analyze_semantic_enrichment_snapshot",
]
