"""Case Workbench read model for the fast prototype workflow."""

from __future__ import annotations

import hashlib
from html import escape
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
ACTION_TEMPLATES = (
    {
        "action_id": "action_review_public_response",
        "title": "复核公开回应口径",
        "required": True,
        "assignee": "analyst",
        "evidence_refs": [PRIMARY_CLAIM["claim_id"], "semantic_case_workbench_demo"],
    },
    {
        "action_id": "action_record_feedback",
        "title": "记录研判反馈",
        "required": True,
        "assignee": "analyst",
        "evidence_refs": ["run_case_workbench_demo"],
    },
)
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

    def __init__(self, mongo_db: Any | None = None, demo_state: dict[str, Any] | None = None) -> None:
        self.mongo_db = mongo_db
        self.demo_state = demo_state if demo_state is not None else _new_demo_state()

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
        acknowledgements = list(self.demo_state["blocker_acknowledgements"])
        acknowledged_blocker_ids = {record["blocker_id"] for record in acknowledgements}
        active_blockers = [blocker for blocker in blockers if blocker["blocker_id"] not in acknowledged_blocker_ids]
        actions = _action_rows(self.demo_state)
        feedback = list(self.demo_state["feedback"])
        closeout_review = self.demo_state.get("closeout_review")
        state = _case_state(blockers=active_blockers, actions=actions, feedback=feedback, closeout_review=closeout_review)
        report_hash = _hash_payload(
            {
                "case_id": DEFAULT_CASE_ID,
                "event_id": DEFAULT_EVENT_ID,
                "state": state,
                "snapshot_id": snapshot.snapshot_id,
                "run_id": "run_case_workbench_demo",
                "primary_claim_excerpt": PRIMARY_CLAIM["excerpt"],
                "primary_claim_source": PRIMARY_CLAIM["source"],
                "semantic_artifact_hash": semantic["artifact_sha256"],
                "semantic_model_status": semantic["model_status"],
                "blockers": [(blocker["code"], blocker["message"]) for blocker in active_blockers],
                "blocker_acknowledgements": acknowledgements,
                "actions": [(action["action_id"], action["status"]) for action in actions],
                "feedback_count": len(feedback),
                "closeout_summary": closeout_review.get("summary") if closeout_review else None,
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
            "canonical_verdict": {
                "verdict_id": "canonical_demo_verdict",
                "status": "approved",
                "label": "needs_human_review",
                "source": "demo_analyst_approval",
            },
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
            "actions": actions,
            "feedback": feedback,
            "closeout_review": closeout_review,
            "reports": [
                {
                    "version": 1,
                    "status": "prototype_preview",
                    "format": "html_pdf_fallback",
                    "content_hash": report_hash,
                    "html_url": f"/api/v2/cases/{DEFAULT_CASE_ID}/reports/1.html",
                    "pdf_url": f"/api/v2/cases/{DEFAULT_CASE_ID}/reports/1.pdf",
                    "contains": ["case", "snapshot", "run", "model_versions", "content_hashes"],
                    "message": "Prototype HTML report is available; production PDF rendering is pending.",
                }
            ],
            "active_blockers": active_blockers,
            "blocker_acknowledgements": acknowledgements,
            "audit_events": list(self.demo_state["audit_events"]),
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

    async def complete_action(
        self,
        case_id: str,
        action_id: str,
        *,
        actor_id: str,
        note: str = "",
    ) -> dict[str, Any]:
        self._assert_case(case_id)
        _assert_action(action_id)
        now = _now()
        self.demo_state["actions"][action_id] = "completed"
        self.demo_state["action_history"][action_id].append(
            {
                "status": "completed",
                "actor_id": actor_id,
                "note": note,
                "created_at": now,
            }
        )
        self._append_audit("complete_case_action", actor_id=actor_id, target_id=action_id, payload={"note": note})
        return await self.get_case(case_id)

    async def waive_action(
        self,
        case_id: str,
        action_id: str,
        *,
        actor_id: str,
        note: str = "",
    ) -> dict[str, Any]:
        self._assert_case(case_id)
        _assert_action(action_id)
        now = _now()
        self.demo_state["actions"][action_id] = "waived"
        self.demo_state["action_history"][action_id].append(
            {
                "status": "waived",
                "actor_id": actor_id,
                "note": note,
                "created_at": now,
            }
        )
        self._append_audit("waive_case_action", actor_id=actor_id, target_id=action_id, payload={"note": note})
        return await self.get_case(case_id)

    async def acknowledge_blocker(
        self,
        case_id: str,
        blocker_id: str,
        *,
        actor_id: str,
        reason: str,
    ) -> dict[str, Any]:
        self._assert_case(case_id)
        posts, comments, _source_mode = await self._load_evidence(DEFAULT_EVENT_ID)
        blocker = next(
            (item for item in _blockers(_platforms(posts, comments)) if item["blocker_id"] == blocker_id),
            None,
        )
        if blocker is None:
            raise KeyError(f"Case blocker not found: {blocker_id}")
        acknowledgement = {
            "acknowledgement_id": f"blocker_acknowledgement_{len(self.demo_state['blocker_acknowledgements']) + 1}",
            "blocker_id": blocker_id,
            "actor_id": actor_id,
            "reason": reason,
            "missing_platforms": list(blocker["missing_platforms"]),
            "created_at": _now(),
            "status": "policy_acknowledged",
            "code": "policy_acknowledged",
        }
        self.demo_state["blocker_acknowledgements"].append(acknowledgement)
        self._append_audit(
            "acknowledge_case_blocker",
            actor_id=actor_id,
            target_id=blocker_id,
            payload={"acknowledgement_id": acknowledgement["acknowledgement_id"], "reason": reason},
        )
        return await self.get_case(case_id)

    async def submit_feedback(self, case_id: str, *, actor_id: str, content: str) -> dict[str, Any]:
        self._assert_case(case_id)
        feedback = {
            "feedback_id": f"feedback_{len(self.demo_state['feedback']) + 1}",
            "actor_id": actor_id,
            "content": content,
            "created_at": _now(),
        }
        self.demo_state["feedback"].append(feedback)
        self._append_audit("submit_case_feedback", actor_id=actor_id, target_id=feedback["feedback_id"], payload={})
        return await self.get_case(case_id)

    async def submit_closeout_review(self, case_id: str, *, actor_id: str, summary: str) -> dict[str, Any]:
        self._assert_case(case_id)
        case = await self.get_case(case_id)
        if case["state"] != "ready_to_close":
            raise CaseOperationConflict("Closeout review requires completed or waived actions, feedback, and no blockers.")
        self.demo_state["closeout_review"] = {
            "review_id": "closeout_review_demo",
            "actor_id": actor_id,
            "summary": summary,
            "submitted_at": _now(),
        }
        self._append_audit("submit_closeout_review", actor_id=actor_id, target_id="closeout_review_demo", payload={})
        return await self.get_case(case_id)

    async def render_report_html(self, case_id: str, version: int, *, pdf_fallback: bool = False) -> str:
        self._assert_case(case_id)
        if version != 1:
            raise KeyError(f"Case report version not found: {version}")

        case = await self.get_case(case_id)
        semantic = case["semantic_artifacts"][0]
        primary_claim = case["primary_claim"]
        actions = "".join(
            f"<li>{_report_text(action['action_id'])}: {_report_text(action['status'])}</li>"
            for action in case["actions"]
        ) or "<li>None</li>"
        blockers = "".join(
            f"<li>{_report_text(blocker['code'])}: {_report_text(blocker['message'])}</li>"
            for blocker in case["active_blockers"]
        ) or "<li>None</li>"
        acknowledgements = "".join(
            "<li>"
            f"{_report_text(record['blocker_id'])}: {_report_text(record['reason'])} "
            f"(missing: {_report_text(', '.join(record.get('missing_platforms') or []))})"
            "</li>"
            for record in case.get("blocker_acknowledgements", [])
        ) or "<li>None</li>"
        closeout = case.get("closeout_review") or {}
        pending_note = (
            "<p><strong>Production PDF rendering is pending.</strong> This HTML is the MVP PDF fallback.</p>"
            if pdf_fallback
            else ""
        )
        return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Case report {version}</title>
<style>body{{font-family:Arial,sans-serif;line-height:1.5;margin:2rem;max-width:900px}}section{{border-top:1px solid #bbb;margin-top:1.25rem;padding-top:.75rem}}dt{{font-weight:bold}}dd{{margin:0 0 .6rem}}code{{word-break:break-all}}@media print{{body{{margin:1cm}}}}</style>
</head><body><h1>CogGuard Case Report</h1>{pending_note}
<section><dl><dt>Case ID</dt><dd>{_report_text(case['case_id'])}</dd><dt>Event ID</dt><dd>{_report_text(case['event_id'])}</dd><dt>Title</dt><dd>{_report_text(case['title'])}</dd><dt>State</dt><dd>{_report_text(case['state'])}</dd><dt>Snapshot ID</dt><dd><code>{_report_text(case['evidence']['snapshot_id'])}</code></dd><dt>Run ID</dt><dd><code>{_report_text(case['analysis_runs'][0]['run_id'])}</code></dd></dl></section>
<section><h2>Primary claim</h2><p>{_report_text(primary_claim['excerpt'])}</p><dl><dt>Source</dt><dd>{_report_text(primary_claim['source']['name'])}</dd><dt>Source tier</dt><dd>{_report_text(primary_claim['source']['tier'])}</dd></dl></section>
<section><h2>Semantic evidence overlay</h2><dl><dt>artifact_sha256</dt><dd><code>{_report_text(semantic['artifact_sha256'])}</code></dd><dt>Model status</dt><dd>{_report_text(semantic['model_status'])}</dd><dt>Score policy</dt><dd>evidence_overlay_only</dd></dl></section>
<section><h2>Active blockers</h2><ul>{blockers}</ul></section><section><h2>Policy acknowledgements</h2><ul>{acknowledgements}</ul></section><section><h2>Actions</h2><ul>{actions}</ul></section><section><h2>Feedback</h2><p>Count: {len(case['feedback'])}</p></section><section><h2>Closeout review</h2><p>{_report_text(closeout.get('summary') or 'Not submitted')}</p></section>
</body></html>"""

    def _assert_case(self, case_id: str) -> None:
        if case_id != DEFAULT_CASE_ID:
            raise KeyError(f"Case not found: {case_id}")

    def _append_audit(self, action: str, *, actor_id: str, target_id: str, payload: dict[str, Any]) -> None:
        self.demo_state["audit_events"].append(
            {
                "event_id": f"audit_{len(self.demo_state['audit_events']) + 1}",
                "action": action,
                "actor_id": actor_id,
                "target_id": target_id,
                "payload": payload,
                "created_at": _now(),
            }
        )


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


class CaseOperationConflict(ValueError):
    """Raised when a prototype Case operation violates lifecycle gates."""


def _new_demo_state() -> dict[str, Any]:
    return {
        "actions": {},
        "action_history": {template["action_id"]: [] for template in ACTION_TEMPLATES},
        "feedback": [],
        "blocker_acknowledgements": [],
        "closeout_review": None,
        "audit_events": [],
    }


def _action_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    statuses = state["actions"]
    history = state["action_history"]
    return [
        {
            **template,
            "status": statuses.get(template["action_id"], "required"),
            "history": list(history.get(template["action_id"], [])),
        }
        for template in ACTION_TEMPLATES
    ]


def _assert_action(action_id: str) -> None:
    if action_id not in {template["action_id"] for template in ACTION_TEMPLATES}:
        raise KeyError(f"Case action not found: {action_id}")


def _case_state(
    *,
    blockers: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    closeout_review: dict[str, Any] | None,
) -> str:
    if blockers:
        return "evidence_ready"
    actions_terminal = all(action["status"] in {"completed", "waived"} for action in actions)
    if actions_terminal and feedback and closeout_review:
        return "closed"
    if actions_terminal and feedback:
        return "ready_to_close"
    return "actioning"


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
    active_index = {
        "evidence_ready": 1,
        "analyzing": 2,
        "awaiting_review": 4,
        "actioning": 5,
        "ready_to_close": 6,
        "closed": len(order),
    }.get(state, 0)
    return [
        {
            "key": key,
            "label": label,
            "status": "done"
            if index < active_index or state == "closed"
            else ("active" if index == active_index else "pending"),
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report_text(value: Any) -> str:
    return escape(str(value))


__all__ = [
    "ACTION_TEMPLATES",
    "CASE_STATES",
    "CaseOperationConflict",
    "DEFAULT_CASE_ID",
    "DEFAULT_EVENT_ID",
    "SOURCE_TIERS",
    "CaseWorkbenchService",
]
