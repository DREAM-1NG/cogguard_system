"""Case Workbench read model for the fast prototype workflow."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.core.analysis.semantic_enrichment import analyze_semantic_enrichment_snapshot
from app.core.analysis.snapshots import build_event_snapshot
from app.core.analysis.contracts import TimeWindow
from app.db.mongodb import get_mongo_db
from app.services.event_data import load_event_comments, load_event_posts

DEFAULT_EVENT_ID = "trump_visit_2026_05_21"
DEFAULT_CASE_ID = "case_trump_visit_2026_05_21"
CASE_STATES = (
    "draft",
    "collecting",
    "evidence_ready",
    "analyzing",
    "awaiting_review",
    "actioning",
    "ready_to_close",
    "closed",
)
SOURCE_TIERS = (
    "government_official",
    "central_mainstream_original",
    "provincial_official_media",
)

PRIMARY_CLAIM = {
    "claim_id": "claim_cctv_primary",
    "role": "primary",
    "status": "approved",
    "excerpt": "推动中美关系这艘巨轮沿着正确航道平稳前行。",
    "span": {"start": 0, "end": 22},
    "url": "https://news.cctv.com/cogguard/archive/trump-visit-primary",
    "account": "央视新闻",
    "published_at": "2026-05-14T20:00:00+08:00",
    "source_tier": "central_mainstream_original",
    "source": {
        "source_id": "authority_cctv_news",
        "name": "央视新闻",
        "tier": "central_mainstream_original",
        "url": "https://news.cctv.com/cogguard/archive/trump-visit-primary",
        "status": "approved",
    },
}
SUPPLEMENTARY_CLAIM = {
    "claim_id": "claim_xinhua_support",
    "role": "supplementary",
    "status": "approved",
    "excerpt": "一次历史性访问。",
    "span": {"start": 0, "end": 8},
    "url": "https://www.news.cn/cogguard/archive/trump-visit-supplementary",
    "account": "新华社",
    "published_at": "2026-05-15T10:30:00+08:00",
    "source_tier": "central_mainstream_original",
    "source": {
        "source_id": "authority_xinhua",
        "name": "新华社",
        "tier": "central_mainstream_original",
        "url": "https://www.news.cn/cogguard/archive/trump-visit-supplementary",
        "status": "approved",
    },
}


class CaseWorkbenchService:
    """Build a case-level projection from current event evidence and analysis contracts."""

    def __init__(self, mongo_db: Any | None = None) -> None:
        self.mongo_db = mongo_db

    async def list_cases(self, *, event_id: str | None = None) -> dict[str, Any]:
        case = await self.get_case(DEFAULT_CASE_ID)
        if event_id and case["event_id"] != event_id:
            return {"items": [], "total": 0}
        return {
            "items": [_summary(case)],
            "total": 1,
            "meta": {
                "states": list(CASE_STATES),
                "source_tiers": list(SOURCE_TIERS),
            },
        }

    async def get_case(self, case_id: str) -> dict[str, Any]:
        if case_id != DEFAULT_CASE_ID:
            raise KeyError(f"Case not found: {case_id}")
        posts, comments, source_mode = await self._load_evidence(DEFAULT_EVENT_ID)
        snapshot = _snapshot_from_evidence(posts, comments)
        semantic = analyze_semantic_enrichment_snapshot(
            snapshot,
            {"primary_claim": PRIMARY_CLAIM},
        )
        platforms = _platforms(posts, comments)
        blockers = _blockers(platforms)
        state = "awaiting_review" if not blockers else "evidence_ready"
        report_hash = _hash_payload(
            {
                "case_id": DEFAULT_CASE_ID,
                "snapshot_id": snapshot.snapshot_id,
                "primary_claim": PRIMARY_CLAIM,
                "semantic_artifact_hash": semantic["artifact_sha256"],
            }
        )

        return {
            "case_id": DEFAULT_CASE_ID,
            "event_id": DEFAULT_EVENT_ID,
            "title": "特朗普访华案例闭环",
            "description": "围绕已归档特朗普访华事件样本构建事件、证据、分析、研判、处置和反馈的闭环展示。",
            "state": state,
            "state_options": list(CASE_STATES),
            "created_at": "2026-08-10T00:00:00+08:00",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "expected_platforms": ["weibo", "xhs"],
            "platforms": platforms,
            "evidence": {
                "snapshot_id": snapshot.snapshot_id,
                "data_fingerprint": snapshot.data_fingerprint,
                "posts": len(posts),
                "comments": len(comments),
                "source_mode": source_mode,
                "authors": len({str(post.get("author_id") or "") for post in posts if post.get("author_id")}),
                "comment_authors": len(
                    {str(comment.get("author_id") or "") for comment in comments if comment.get("author_id")}
                ),
                "platform_distribution": _platform_distribution(posts, comments),
                "recent_posts": _recent_posts(posts),
            },
            "lifecycle": _lifecycle(state=state),
            "primary_claim": _claim_with_hash(PRIMARY_CLAIM),
            "supplementary_claims": [_claim_with_hash(SUPPLEMENTARY_CLAIM)],
            "analysis_runs": [
                {
                    "run_id": "run_case_workbench_demo",
                    "snapshot_id": snapshot.snapshot_id,
                    "status": "awaiting_review",
                    "requested_stages": [
                        "coordination_discover",
                        "propagation_analysis",
                        "semantic_enrichment",
                        "student",
                        "teacher",
                    ],
                    "semantic_enrichment_explicit": True,
                }
            ],
            "semantic_artifacts": [
                {
                    "artifact_id": "semantic_case_workbench_demo",
                    "artifact_type": "semantic_enrichment",
                    "status": semantic["status"],
                    "model_status": semantic["model_status"],
                    "artifact_sha256": semantic["artifact_sha256"],
                    "summary": {
                        "sentiment": semantic["sentiment"]["summary"],
                        "top_keywords": semantic["keywords"]["main_posts"][:8],
                        "topics": semantic["topics"]["main_posts"],
                        "entities": semantic["entities"]["main_posts"][:12],
                        "stance": semantic["stance"],
                        "near_duplicates": semantic["near_duplicates"]["main_posts"],
                        "community_comparison": semantic["community_comparison"],
                    },
                    "provenance": semantic["provenance"],
                }
            ],
            "evidence_matrix": _evidence_matrix(posts, comments, semantic),
            "graph": _graph_projection(posts),
            "actions": [
                {
                    "action_id": "action_review_public_response",
                    "title": "复核公开回应口径",
                    "status": "required",
                    "required": True,
                    "assignee": "analyst",
                    "evidence_refs": [PRIMARY_CLAIM["claim_id"], "semantic_case_workbench_demo"],
                },
                {
                    "action_id": "action_record_feedback",
                    "title": "记录研判反馈",
                    "status": "required",
                    "required": True,
                    "assignee": "analyst",
                    "evidence_refs": ["run_case_workbench_demo"],
                },
            ],
            "feedback": [],
            "reports": [
                {
                    "version": 1,
                    "status": "placeholder",
                    "format": "html_pdf_pending",
                    "content_hash": report_hash,
                    "contains": ["case", "snapshot", "run", "model_versions", "content_hashes"],
                    "message": "正式冻结 HTML/PDF 报告文件服务待后续迭代接入。",
                }
            ],
            "active_blockers": blockers,
            "workflow_summary": {
                "closed_loop": "事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈",
                "display_loop": "事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈",
                "core_claim_source": "official_media",
                "semantic_score_policy": "evidence_overlay_only",
                "stance_block_code": "blocked_missing_primary_claim",
                "default_analysis_stage_compatibility": "semantic_enrichment is explicit and does not change the four-stage default",
            },
        }

    async def _load_evidence(self, event_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        try:
            mongo_db = self.mongo_db if self.mongo_db is not None else get_mongo_db()
            posts = await load_event_posts(mongo_db, event_id=event_id)
            comments = await load_event_comments(mongo_db, event_id=event_id)
        except Exception:
            posts, comments = [], []
        if posts or comments:
            return posts, comments, "mongo"
        return _fixture_posts(), _fixture_comments(), "demo_fixture"


def _snapshot_from_evidence(posts: list[dict[str, Any]], comments: list[dict[str, Any]]):
    return build_event_snapshot(
        event_id=DEFAULT_EVENT_ID,
        posts=posts,
        comments=comments,
        core_window=TimeWindow(
            start=datetime.fromisoformat("2026-05-11T00:00:00+00:00"),
            end=datetime.fromisoformat("2026-05-22T00:00:00+00:00"),
        ),
        context_window=TimeWindow(
            start=datetime.fromisoformat("2026-05-01T00:00:00+00:00"),
            end=datetime.fromisoformat("2026-05-31T00:00:00+00:00"),
        ),
    )


def _fixture_posts() -> list[dict[str, Any]]:
    return [
        {
            "event_id": DEFAULT_EVENT_ID,
            "platform": "weibo",
            "post_id": "weibo_demo_1",
            "author_id": "xinhua",
            "author_name": "新华社",
            "timestamp": "2026-05-14T12:00:00+00:00",
            "content": "特朗普访华欢迎仪式开始，中美关系稳定前行引发关注。",
            "hashtags": ["特朗普访华", "中美关系"],
        },
        {
            "event_id": DEFAULT_EVENT_ID,
            "platform": "weibo",
            "post_id": "weibo_demo_2",
            "author_id": "observer_1",
            "author_name": "观察账号",
            "timestamp": "2026-05-14T13:00:00+00:00",
            "content": "欢迎宴会更多细节曝光，大家关注特朗普访华行程。",
            "hashtags": ["特朗普访华"],
        },
    ]


def _fixture_comments() -> list[dict[str, Any]]:
    return [
        {
            "event_id": DEFAULT_EVENT_ID,
            "platform": "weibo",
            "comment_id": "weibo_comment_1",
            "post_id": "weibo_demo_1",
            "reply_to": "weibo_demo_1",
            "author_id": "commenter_1",
            "timestamp": "2026-05-14T14:00:00+00:00",
            "content": "希望关系稳定合作。",
        }
    ]


def _summary(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "event_id": case["event_id"],
        "title": case["title"],
        "state": case["state"],
        "primary_claim": case["primary_claim"],
        "active_blockers": case["active_blockers"],
        "platforms": case["platforms"],
        "evidence": case["evidence"],
    }


def _platforms(posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("platform") or "").strip()
            for row in [*posts, *comments]
            if str(row.get("platform") or "").strip()
        }
    )


def _blockers(platforms: list[str]) -> list[dict[str, Any]]:
    expected = {"weibo", "xhs"}
    missing = sorted(expected - set(platforms))
    if not missing:
        return []
    return [
        {
            "blocker_id": "blocker_platform_gap_" + "_".join(missing),
            "code": "platform_gap",
            "scope": "collection",
            "operation": "evidence_ready",
            "severity": "advisory",
            "message": "缺少同事件平台归档证据：" + ", ".join(missing),
            "missing_platforms": missing,
        }
    ]


def _lifecycle(*, state: str) -> list[dict[str, str]]:
    order = [
        ("event", "事件"),
        ("evidence", "证据"),
        ("coordination", "Coordination"),
        ("propagation", "Propagation"),
        ("review", "Review"),
        ("action", "处置"),
        ("feedback", "反馈"),
    ]
    active_index = 4 if state == "awaiting_review" else 1
    return [
        {
            "key": key,
            "label": label,
            "status": "done" if index < active_index else ("active" if index == active_index else "pending"),
        }
        for index, (key, label) in enumerate(order)
    ]


def _claim_with_hash(claim: dict[str, Any]) -> dict[str, Any]:
    excerpt = str(claim["excerpt"])
    return {
        **claim,
        "source_content_hash": hashlib.sha256((claim["url"] + excerpt).encode("utf-8")).hexdigest(),
        "excerpt_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }


def _platform_distribution(posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    post_counts = Counter(str(post.get("platform") or "unknown") for post in posts)
    comment_counts = Counter(str(comment.get("platform") or "unknown") for comment in comments)
    return [
        {
            "platform": platform,
            "posts": post_counts.get(platform, 0),
            "comments": comment_counts.get(platform, 0),
            "total": post_counts.get(platform, 0) + comment_counts.get(platform, 0),
        }
        for platform in sorted(set(post_counts) | set(comment_counts))
    ]


def _recent_posts(posts: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, Any]]:
    return [
        {
            "post_id": post.get("post_id"),
            "platform": post.get("platform"),
            "author_name": post.get("author_name") or post.get("author_id"),
            "timestamp": str(post.get("timestamp") or ""),
            "content": str(post.get("content") or "")[:180],
        }
        for post in sorted(posts, key=lambda row: str(row.get("timestamp") or ""))[:limit]
    ]


def _evidence_matrix(posts: list[dict[str, Any]], comments: list[dict[str, Any]], semantic: dict[str, Any]) -> dict[str, Any]:
    return {
        "claims": [_claim_with_hash(PRIMARY_CLAIM), _claim_with_hash(SUPPLEMENTARY_CLAIM)],
        "posts": _recent_posts(posts, limit=20),
        "comments": [
            {
                "comment_id": comment.get("comment_id"),
                "post_id": comment.get("post_id"),
                "platform": comment.get("platform"),
                "author_name": comment.get("author_name") or comment.get("author_id"),
                "content": str(comment.get("content") or "")[:180],
            }
            for comment in comments[:20]
        ],
        "semantic": {
            "keywords": semantic["keywords"],
            "topics": semantic["topics"],
            "entities": semantic["entities"],
            "sentiment": semantic["sentiment"],
            "stance": semantic["stance"],
            "near_duplicates": semantic["near_duplicates"],
            "community_comparison": semantic["community_comparison"],
        },
    }


def _graph_projection(posts: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = []
    seen = set()
    for post in posts:
        author = str(post.get("author_id") or "").strip()
        if author and author not in seen:
            seen.add(author)
            nodes.append({"id": author, "label": post.get("author_name") or author, "type": "account"})
    return {
        "nodes": nodes,
        "edges": [],
        "provenance": "case_workbench_projection_only",
    }


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        str(sorted(payload.items())).encode("utf-8", errors="ignore")
    ).hexdigest()


__all__ = [
    "CASE_STATES",
    "DEFAULT_CASE_ID",
    "DEFAULT_EVENT_ID",
    "SOURCE_TIERS",
    "CaseWorkbenchService",
]
