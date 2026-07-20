"""Internal analysis runtimes for the KT3 student/teacher seam."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.review.layered_harmfulness import assess_layered_harmfulness
from app.core.review.kt3_multi_agent import execute_kt3_multi_agent_review
from app.core.review.kt3_review_executor import execute_kt3_review_queue
from app.core.review.kt3_reviewer import build_kt3_review_queue
from app.core.review.kt3_trainable_post import build_agent_review
from app.core.review.kt3_trainable_post import fuse_detector_outputs
from app.core.review.kt3_trainable_post import standard_detector_output
from app.core.review.post_semantics import assess_post_semantics
from app.db.mysql import async_session_factory
from app.models.analysis import ReviewVerdictVersion


ANALYSIS_STUDENT_MODEL_VERSION = "analysis-student-runtime-v1"
ANALYSIS_TEACHER_MODEL_VERSION = "analysis-teacher-runtime-v1"
ANALYSIS_TEACHER_SOURCE = "analysis.teacher.runtime.v1"
SYSTEM_ROOT = Path(__file__).resolve().parents[4]
REVIEW_STUDENT_RUNTIME_PATH = SYSTEM_ROOT / "runtimes" / "review_student" / "runtime.py"
REVIEW_TEACHER_DAG_PATH = SYSTEM_ROOT / "research" / "review_teacher" / "dag.py"
TEACHER_JOB_CACHE: dict[str, dict[str, Any]] = {}


class InternalStudentRuntime:
    async def predict(self, case: dict[str, Any]) -> dict[str, Any]:
        return build_student_verdict(case)


class InternalTeacherJobPort:
    async def submit(self, case: dict[str, Any]) -> dict[str, Any]:
        return await submit_teacher_review_job(case)


def build_student_verdict(case: dict[str, Any]) -> dict[str, Any]:
    runtime = _load_review_student_runtime().StudentRuntime()
    return runtime.predict_sync(case)


def build_teacher_advisory_verdict(
    case: dict[str, Any],
    *,
    job_id: str | None = None,
) -> dict[str, Any]:
    student = build_student_verdict(case)
    return _load_review_teacher_dag().run_teacher_dag(case, student=student, job_id=job_id)


def _load_review_student_runtime():
    return _load_internal_module(
        path=REVIEW_STUDENT_RUNTIME_PATH,
        module_name="cogguard_review_student_runtime",
        label="Review Student runtime",
    )


def _load_review_teacher_dag():
    return _load_internal_module(
        path=REVIEW_TEACHER_DAG_PATH,
        module_name="cogguard_review_teacher_dag",
        label="Review Teacher DAG",
    )


def _load_internal_module(*, path: Path, module_name: str, label: str):
    if not path.is_file():
        raise RuntimeError(f"{label} not found: {path}")
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {label} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _legacy_build_student_verdict(case: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_case(case)
    quality_report = normalized["quality_report"]
    if _quality_status(quality_report) == "reject" or not normalized["posts"]:
        return {
            "technology": "student",
            "status": "data_insufficient",
            "verdict_type": "preliminary",
            "verdict_id": _verdict_id("student", normalized),
            "snapshot_id": normalized["snapshot_id"],
            "event_id": normalized["event_id"],
            "model_version": ANALYSIS_STUDENT_MODEL_VERSION,
            "reason": "Event snapshot has insufficient evidence for a deployed student verdict.",
            "capability_boundary": _capability_boundary("student"),
            "quality_report": quality_report,
            "review_required": True,
            "abstain": True,
        }

    post_semantics = assess_post_semantics(
        normalized["posts"],
        _build_post_semantics_context(normalized),
        prefer_embeddings=False,
    )
    coordination = _build_coordination_context(normalized)
    propagation = _build_propagation_context(normalized)
    layered = assess_layered_harmfulness(
        post_semantics=post_semantics,
        account_profiles=_build_account_profiles(normalized),
        coordination=coordination,
        propagation=propagation,
        event_id=normalized["event_id"],
        platform=normalized["platform"],
    )
    detector_outputs = _build_student_detector_outputs(post_semantics)
    fusion = fuse_detector_outputs(detector_outputs)
    agent_review = build_agent_review(detector_outputs, fusion)
    confidence = round(max(fusion["final_score"], 1.0 - fusion["final_score"]), 4)
    review_required = bool(agent_review["review_required"] or fusion["review_required"])
    verdict = {
        "technology": "student",
        "status": "ok",
        "verdict_type": "preliminary",
        "verdict_id": _verdict_id("student", normalized),
        "snapshot_id": normalized["snapshot_id"],
        "event_id": normalized["event_id"],
        "platforms": normalized["platforms"],
        "model_version": ANALYSIS_STUDENT_MODEL_VERSION,
        "label": fusion["final_harmfulness"],
        "score": fusion["final_score"],
        "confidence": confidence,
        "risk_level": _student_risk_level(post_semantics, layered, fusion),
        "abstain": confidence < 0.55,
        "review_required": review_required,
        "review_reason": list(fusion["review_reason"]),
        "capability_boundary": _capability_boundary("student"),
        "quality_report": quality_report,
        "summary": {
            "input_posts": post_semantics["summary"]["input_posts"],
            "analyzed_posts": post_semantics["summary"]["analyzed_posts"],
            "harmful_posts": post_semantics["summary"]["harmful_posts"],
            "harmful_ratio": post_semantics["summary"]["harmful_ratio"],
            "linked_posts": post_semantics["summary"]["linked_posts"],
            "available_claims": post_semantics["summary"]["available_claims"],
            "account_count": layered["user_level"]["summary"]["account_count"],
            "community_count": layered["community_level"]["summary"]["community_count"],
        },
        "signals": {
            "post_semantics": {
                "backend": post_semantics["summary"]["backend"],
                "harmful_ratio": post_semantics["summary"]["harmful_ratio"],
                "stance_distribution": post_semantics["summary"]["stance_distribution"],
                "top_claims": post_semantics["summary"]["top_claims"][:5],
            },
            "layered_harmfulness": {
                "user_level": layered["user_level"]["summary"],
                "community_level": layered["community_level"]["summary"],
                "global_summary": layered["global_summary"],
            },
            "fusion": fusion,
            "agent_review": agent_review,
        },
        "evidence": _student_evidence(post_semantics, layered, detector_outputs),
    }
    return verdict


def _legacy_build_teacher_advisory_verdict(
    case: dict[str, Any],
    *,
    job_id: str | None = None,
) -> dict[str, Any]:
    normalized = _normalize_case(case)
    student = build_student_verdict(case)
    if student["status"] == "data_insufficient":
        return {
            "technology": "teacher",
            "status": "data_insufficient",
            "verdict_type": "teacher_advisory",
            "verdict_id": job_id or _verdict_id("teacher", normalized),
            "snapshot_id": normalized["snapshot_id"],
            "event_id": normalized["event_id"],
            "model_version": ANALYSIS_TEACHER_MODEL_VERSION,
            "capability_boundary": _capability_boundary("teacher"),
            "reason": "Event snapshot has insufficient evidence for a teacher advisory review.",
            "review_required": True,
            "advisory": {
                "decision": "needs_evidence",
                "recommended_actions": {"human_review": 1},
                "avg_agent_confidence": 0.0,
                "external_followup_required": False,
            },
            "student_reference": {
                "verdict_id": student["verdict_id"],
                "label": student["label"],
                "score": student["score"],
            },
        }

    post_semantics = assess_post_semantics(
        normalized["posts"],
        _build_post_semantics_context(normalized),
        prefer_embeddings=False,
    )
    coordination = _build_coordination_context(normalized)
    propagation = _build_propagation_context(normalized)
    layered = assess_layered_harmfulness(
        post_semantics=post_semantics,
        account_profiles=_build_account_profiles(normalized),
        coordination=coordination,
        propagation=propagation,
        event_id=normalized["event_id"],
        platform=normalized["platform"],
    )
    review_queue = build_kt3_review_queue(
        post_semantics=post_semantics,
        kt3_harmfulness=layered,
        max_items=int(normalized["options"].get("teacher_max_review_items", 20) or 20),
    )
    review_execution = execute_kt3_review_queue(
        post_semantics=post_semantics,
        kt3_harmfulness=layered,
        review_queue=review_queue,
    )
    multi_agent = execute_kt3_multi_agent_review(
        post_semantics=post_semantics,
        kt3_harmfulness=layered,
        review_execution=review_execution,
    )
    final_decision = multi_agent["final_decision"]
    verdict = {
        "technology": "teacher",
        "status": "completed",
        "verdict_type": "teacher_advisory",
        "verdict_id": job_id or _verdict_id("teacher", normalized),
        "snapshot_id": normalized["snapshot_id"],
        "event_id": normalized["event_id"],
        "platforms": normalized["platforms"],
        "model_version": ANALYSIS_TEACHER_MODEL_VERSION,
        "capability_boundary": _capability_boundary("teacher"),
        "review_required": bool(final_decision["external_followup_required"]),
        "advisory": {
            "decision": final_decision["decision"],
            "recommended_actions": final_decision["recommended_actions"],
            "avg_agent_confidence": final_decision["avg_agent_confidence"],
            "external_followup_required": final_decision["external_followup_required"],
        },
        "summary": {
            "review_items": review_queue["summary"]["review_items"],
            "retrieval_tasks": review_queue["summary"]["retrieval_tasks"],
            "agent_tasks": review_queue["summary"]["agent_tasks"],
            "external_followup_required": final_decision["external_followup_required"],
            "agents_executed": multi_agent["summary"]["agents_executed"],
            "blackboard_posts": multi_agent["summary"]["blackboard_posts"],
        },
        "signals": {
            "post_semantics": {
                "backend": post_semantics["summary"]["backend"],
                "harmful_ratio": post_semantics["summary"]["harmful_ratio"],
                "top_claims": post_semantics["summary"]["top_claims"][:5],
            },
            "layered_harmfulness": {
                "user_level": layered["user_level"]["summary"],
                "community_level": layered["community_level"]["summary"],
                "global_summary": layered["global_summary"],
            },
            "review_queue": review_queue["summary"],
            "review_execution": review_execution["summary"],
            "multi_agent": multi_agent["summary"],
            "final_decision": final_decision,
        },
        "evidence": _teacher_evidence(post_semantics, layered, review_execution, multi_agent),
    }
    return verdict


async def submit_teacher_review_job(case: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_case(case)
    job_id = _verdict_id("teacher", normalized)
    queued_result = {
        "technology": "teacher",
        "job_id": job_id,
        "status": "queued",
        "verdict_type": "teacher_advisory",
        "snapshot_id": normalized["snapshot_id"],
        "event_id": normalized["event_id"],
        "platforms": normalized["platforms"],
        "model_version": ANALYSIS_TEACHER_MODEL_VERSION,
        "task_state": "submitted",
        "capability_boundary": _capability_boundary("teacher"),
    }
    TEACHER_JOB_CACHE[job_id] = queued_result
    await _persist_teacher_review_row(job_id=job_id, case=normalized, verdict=queued_result, status="draft")
    dispatch = await _queue_teacher_review_job(job_id=job_id, case=normalized)
    queued_result.update(dispatch)
    return queued_result


async def finalize_teacher_review_job(job_id: str, case: dict[str, Any]) -> dict[str, Any]:
    verdict = build_teacher_advisory_verdict(case, job_id=job_id)
    TEACHER_JOB_CACHE[job_id] = verdict
    await _persist_teacher_review_row(job_id=job_id, case=_normalize_case(case), verdict=verdict, status="completed")
    return verdict


async def _queue_teacher_review_job(job_id: str, case: dict[str, Any]) -> dict[str, Any]:
    try:
        from app.tasks.analysis_tasks import execute_analysis_teacher_review

        async_result = execute_analysis_teacher_review.delay(job_id, case)
        return {"task_id": async_result.id, "dispatch_backend": "celery"}
    except Exception as exc:
        asyncio.create_task(_finalize_teacher_job_inline(job_id, case))
        return {
            "dispatch_backend": "inline_fallback",
            "dispatch_error": f"{type(exc).__name__}: {exc}",
        }


async def _finalize_teacher_job_inline(job_id: str, case: dict[str, Any]) -> dict[str, Any]:
    return await finalize_teacher_review_job(job_id, case)


async def _persist_teacher_review_row(
    *,
    job_id: str,
    case: dict[str, Any],
    verdict: dict[str, Any],
    status: str,
) -> None:
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(ReviewVerdictVersion).where(ReviewVerdictVersion.verdict_id == job_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                db.add(
                    ReviewVerdictVersion(
                        verdict_id=job_id,
                        run_id=_run_id(case, job_id),
                        snapshot_id=case["snapshot_id"],
                        version=1,
                        verdict_type="teacher_advisory",
                        status=status,
                        verdict_json=_json_dumps(verdict),
                        immutable_source=ANALYSIS_TEACHER_SOURCE,
                        canonical_source_id=None,
                        provenance_json=_json_dumps(_teacher_provenance(case, verdict, status)),
                        approved_by=None,
                        approved_at=None,
                        approval_notes=None,
                        created_by=int(case.get("created_by") or 0),
                    )
                )
            else:
                row.run_id = _run_id(case, job_id)
                row.snapshot_id = case["snapshot_id"]
                row.verdict_type = "teacher_advisory"
                row.status = status
                row.verdict_json = _json_dumps(verdict)
                row.immutable_source = ANALYSIS_TEACHER_SOURCE
                row.provenance_json = _json_dumps(_teacher_provenance(case, verdict, status))
                row.canonical_source_id = None
                row.approval_notes = None
                row.created_by = int(case.get("created_by") or 0)
            await db.commit()
    except Exception:
        TEACHER_JOB_CACHE[job_id] = {**TEACHER_JOB_CACHE.get(job_id, {}), "verdict": verdict, "status": status}


def _normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    options = dict(case.get("options") or {})
    posts = [_normalize_content_row(row, default_kind="post") for row in _as_list(case.get("posts"))]
    comments = [_normalize_content_row(row, default_kind="comment") for row in _as_list(case.get("comments"))]
    relationships = [row for row in _as_list(case.get("relationships")) if isinstance(row, dict)]
    provenance = [row for row in _as_list(case.get("provenance")) if isinstance(row, dict)]
    quality_report = dict(case.get("quality_report") or {})
    platforms = [str(platform) for platform in _as_list(case.get("platforms")) if str(platform).strip()]
    if not platforms:
        platforms = sorted({str(row.get("platform") or "").strip() for row in [*posts, *comments] if str(row.get("platform") or "").strip()})
    return {
        "snapshot_id": str(case.get("snapshot_id") or ""),
        "event_id": str(case.get("event_id") or ""),
        "platforms": platforms,
        "platform": platforms[0] if len(platforms) == 1 else None,
        "posts": posts,
        "comments": comments,
        "relationships": relationships,
        "provenance": provenance,
        "quality_report": quality_report,
        "options": options,
        "created_by": case.get("created_by") or 0,
    }


def _build_post_semantics_context(case: dict[str, Any]) -> dict[str, Any]:
    claims = []
    evidence_chains = []
    seen: set[str] = set()
    for post in case["posts"]:
        content = _text(post.get("content") or post.get("text") or "")
        anchors = _extract_claim_anchors(content)
        if not anchors:
            continue
        for anchor in anchors:
            claim_id = _stable_id(anchor)
            if claim_id not in seen:
                seen.add(claim_id)
                claims.append(
                    {
                        "object_id": claim_id,
                        "claim_id": claim_id,
                        "claim_text": anchor,
                        "share_count": 1,
                        "account_count": 1,
                        "first_share": post.get("timestamp") or "",
                        "source": "snapshot",
                    }
                )
            evidence_chains.append(
                {
                    "claim_id": claim_id,
                    "supporting_posts": [
                        {
                            "post_id": post.get("post_id"),
                            "author_id": post.get("author_id"),
                            "content": content[:240],
                            "timestamp": post.get("timestamp"),
                        }
                    ],
                }
            )
    return {"claims": claims, "evidence_chains": evidence_chains}


def _build_account_profiles(case: dict[str, Any]) -> list[dict[str, Any]]:
    posts_by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    comments_by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in case["posts"]:
        account_id = str(post.get("author_id") or "").strip()
        if account_id:
            posts_by_account[account_id].append(post)
    for comment in case["comments"]:
        account_id = str(comment.get("author_id") or "").strip()
        if account_id:
            comments_by_account[account_id].append(comment)

    profiles = []
    for account_id in sorted(set(posts_by_account) | set(comments_by_account)):
        posts = posts_by_account.get(account_id, [])
        comments = comments_by_account.get(account_id, [])
        author_name = _first_non_empty(
            [post.get("author_name") for post in posts] + [comment.get("author_name") for comment in comments]
        ) or account_id
        profiles.append(
            {
                "account_id": account_id,
                "author_name": author_name,
                "platform": _first_non_empty([post.get("platform") for post in posts] + [comment.get("platform") for comment in comments]),
                "automation_score": 0.0,
                "post_count": len(posts),
                "comment_count": len(comments),
                "representative_posts": [
                    {
                        "post_id": post.get("post_id"),
                        "content": _text(post.get("content") or post.get("text") or "")[:240],
                    }
                    for post in posts[:3]
                ],
            }
        )
    return profiles


def _build_coordination_context(case: dict[str, Any]) -> dict[str, Any]:
    authors = {
        _content_ref(post, kind="post"): str(post.get("author_id") or "").strip()
        for post in case["posts"]
        if str(post.get("post_id") or "").strip()
    }
    authors.update(
        {
            _content_ref(comment, kind="comment"): str(comment.get("author_id") or "").strip()
            for comment in case["comments"]
            if str(comment.get("comment_id") or "").strip()
        }
    )

    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    degree: Counter[str] = Counter()
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in case["relationships"]:
        source_ref = str(row.get("source_id") or row.get("source_ref") or "").strip()
        target_ref = str(row.get("target_id") or row.get("target_ref") or "").strip()
        source_account = authors.get(source_ref)
        target_account = authors.get(target_ref)
        if not source_account or not target_account:
            continue
        key = (source_account, target_account, str(row.get("relation_type") or "related"))
        edges[key] = {
            "source": source_account,
            "target": target_account,
            "relation_type": str(row.get("relation_type") or "related"),
            "platform": str(row.get("platform") or ""),
            "weight": 1,
        }
        adjacency[source_account].add(target_account)
        adjacency[target_account].add(source_account)
        degree[source_account] += 1
        degree[target_account] += 1

    clusters = _connected_components(adjacency)
    cluster_rows = []
    for index, members in enumerate(clusters):
        member_list = sorted(members)
        cluster_edges = [
            edge
            for edge in edges.values()
            if edge["source"] in members and edge["target"] in members
        ]
        cluster_rows.append(
            {
                "cluster_id": f"cluster_{index}",
                "members": member_list,
                "size": len(member_list),
                "edge_count": len(cluster_edges),
                "total_weight": len(cluster_edges),
                "shared_objects": [],
            }
        )

    account_stats = [
        {
            "account_id": account_id,
            "account_label": account_id,
            "degree": int(degree[account_id]),
            "avg_weight": float(degree[account_id] or 0),
            "avg_time_delta": 0.0,
            "coordinated_shares_count": int(degree[account_id]),
            "shared_objects_preview": [],
        }
        for account_id in sorted({*authors.values(), *degree.keys()})
        if account_id
    ]
    return {
        "network": {
            "nodes": [
                {"id": account_id, "account_id": account_id}
                for account_id in sorted({*authors.values(), *degree.keys()})
                if account_id
            ],
            "edges": list(edges.values()),
            "clusters": cluster_rows,
        },
        "account_stats": account_stats,
        "group_stats": cluster_rows,
        "cluster_stats": cluster_rows,
    }


def _build_propagation_context(case: dict[str, Any]) -> dict[str, Any]:
    posts = sorted(case["posts"], key=_timestamp_key)
    comments = sorted(case["comments"], key=_timestamp_key)
    timeline = [
        {
            "post_id": post.get("post_id"),
            "author_id": post.get("author_id"),
            "timestamp": post.get("timestamp"),
            "content": _text(post.get("content") or post.get("text") or "")[:240],
        }
        for post in posts
    ]
    claims = []
    evidence_chains = []
    for post in posts:
        content = _text(post.get("content") or post.get("text") or "")
        if not content:
            continue
        anchors = _extract_claim_anchors(content)
        if not anchors:
            continue
        for anchor in anchors:
            claim_id = _stable_id(anchor)
            claims.append(
                {
                    "claim_id": claim_id,
                    "object_id": claim_id,
                    "claim_text": anchor,
                    "share_count": 1,
                    "account_count": 1,
                    "first_share": post.get("timestamp") or "",
                }
            )
            evidence_chains.append(
                {
                    "claim_id": claim_id,
                    "supporting_posts": [
                        {
                            "post_id": post.get("post_id"),
                            "author_id": post.get("author_id"),
                            "timestamp": post.get("timestamp"),
                            "content": content[:240],
                        }
                    ],
                }
            )
    graph_nodes = []
    graph_edges = []
    seen_nodes: set[str] = set()
    for post in posts:
        author_id = str(post.get("author_id") or "").strip()
        if author_id and author_id not in seen_nodes:
            seen_nodes.add(author_id)
            graph_nodes.append({"id": author_id, "account_id": author_id})
    for comment in comments:
        author_id = str(comment.get("author_id") or "").strip()
        if author_id and author_id not in seen_nodes:
            seen_nodes.add(author_id)
            graph_nodes.append({"id": author_id, "account_id": author_id})
    for row in case["relationships"]:
        graph_edges.append(
            {
                "relation_type": str(row.get("relation_type") or ""),
                "source_ref": row.get("source_id") or row.get("source_ref"),
                "target_ref": row.get("target_id") or row.get("target_ref"),
                "platform": row.get("platform"),
            }
        )
    originators = [
        {"account_id": posts[0].get("author_id"), "role": "originator", "evidence": posts[0].get("post_id")}
    ] if posts else []
    bridges = [
        {"account_id": account_id, "role": "bridge"}
        for account_id, count in Counter(str(post.get("author_id") or "").strip() for post in posts).items()
        if account_id and count > 1
    ][:5]
    amplifiers = [
        {"account_id": account_id, "role": "amplifier"}
        for account_id, count in Counter(str(post.get("author_id") or "").strip() for post in posts).items()
        if account_id and count > 1
    ][:5]
    return {
        "timeline": timeline,
        "claims": claims[:20],
        "evidence_chains": evidence_chains[:20],
        "key_roles": {
            "originators": originators,
            "bridges": bridges,
            "amplifiers": amplifiers,
        },
        "graph": {
            "nodes": graph_nodes,
            "edges": graph_edges,
        },
        "comment_count": len(comments),
    }


def _build_student_detector_outputs(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    detector_outputs = []
    for index, post in enumerate(_semantic_posts(post_semantics)[:3]):
        probability = float(_get(post, "harmfulness", "score") or 0.5)
        text = str(post.get("excerpt") or post.get("text") or post.get("content") or "")
        detector_case = {
            "case_id": f"{post.get('post_id') or index}",
            "text": text,
            "labels": {
                "harm_type": list(_as_list(_get(post, "harmfulness", "types"))),
            },
            "claim_context": {
                "claim_text": str(_get(post, "primary_claim", "claim_text") or ""),
                "evidence_text": text[:240],
            },
        }
        detector_outputs.append(
            standard_detector_output(
                detector_case,
                view=str(post.get("post_view") or "tweet"),
                probability=probability,
                evidence=[text[:240]],
                capability_boundary="analysis.student.runtime.v1",
                stance=str(_get(post, "stance", "label") or "neutral"),
            )
        )
    if not detector_outputs:
        detector_outputs.append(
            standard_detector_output(
                {"case_id": "snapshot", "text": "", "labels": {}},
                view="tweet",
                probability=0.5,
                evidence=["No representative posts were available."],
                capability_boundary="analysis.student.runtime.v1",
                stance="neutral",
            )
        )
    return detector_outputs


def _student_risk_level(
    post_semantics: dict[str, Any],
    layered: dict[str, Any],
    fusion: dict[str, Any],
) -> str:
    harmful_ratio = float(post_semantics["summary"]["harmful_ratio"] or 0.0)
    harmful_accounts = int(layered["user_level"]["summary"]["harmful_accounts"] or 0)
    if fusion["final_harmfulness"] == "harmful" and harmful_ratio >= 0.65:
        return "high"
    if fusion["final_harmfulness"] == "harmful" or harmful_accounts > 0:
        return "medium"
    return "low"


def _student_evidence(
    post_semantics: dict[str, Any],
    layered: dict[str, Any],
    detector_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "top_claims": post_semantics["summary"]["top_claims"][:5],
        "harm_types": post_semantics["summary"]["harm_types"],
        "stance_distribution": post_semantics["summary"]["stance_distribution"],
        "account_summary": layered["user_level"]["summary"],
        "community_summary": layered["community_level"]["summary"],
        "detectors": detector_outputs,
    }


def _teacher_evidence(
    post_semantics: dict[str, Any],
    layered: dict[str, Any],
    review_execution: dict[str, Any],
    multi_agent: dict[str, Any],
) -> dict[str, Any]:
    return {
        "top_claims": post_semantics["summary"]["top_claims"][:5],
        "harm_types": post_semantics["summary"]["harm_types"],
        "stance_distribution": post_semantics["summary"]["stance_distribution"],
        "account_summary": layered["user_level"]["summary"],
        "community_summary": layered["community_level"]["summary"],
        "review_execution": {
            "summary": review_execution["summary"],
            "provider_audit": review_execution["provider_audit"],
        },
        "multi_agent": {
            "summary": multi_agent["summary"],
            "final_decision": multi_agent["final_decision"],
        },
    }


def _teacher_provenance(case: dict[str, Any], verdict: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "source": ANALYSIS_TEACHER_SOURCE,
        "status": status,
        "snapshot_id": case["snapshot_id"],
        "event_id": case["event_id"],
        "platforms": case["platforms"],
        "verdict_type": verdict["verdict_type"],
        "verdict_id": verdict["verdict_id"],
        "case_digest": _case_digest(case),
    }


def _student_evidence_strings(case: dict[str, Any]) -> list[str]:
    texts = []
    for post in case["posts"][:3]:
        text = _text(post.get("content") or post.get("text") or "")
        if text:
            texts.append(text[:240])
    return texts


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = post_semantics.get("aggregation_posts")
    if isinstance(posts, list):
        return posts
    posts = post_semantics.get("posts")
    return posts if isinstance(posts, list) else []


def _quality_status(quality_report: dict[str, Any]) -> str:
    return str(quality_report.get("status") or "").strip().lower()


def _verdict_id(prefix: str, case: dict[str, Any]) -> str:
    return f"{prefix}_{_case_digest(case)[:24]}"


def _run_id(case: dict[str, Any], job_id: str) -> str:
    return str(case.get("run_id") or f"analysis:{job_id}")


def _capability_boundary(role: str) -> dict[str, Any]:
    return {
        "runtime": f"internal-{role}-runtime",
        "live_external_call": False,
        "trainable_scaffold": role == "student",
        "teacher_advisory_only": role == "teacher",
        "description": (
            "Snapshot-derived runtime scaffold that stays inside the analysis boundary "
            "and does not treat teacher outputs as canonical verdicts."
        ),
    }


def _normalize_content_row(row: dict[str, Any], *, default_kind: str) -> dict[str, Any]:
    normalized = dict(row)
    if not normalized.get("content"):
        normalized["content"] = normalized.get("text") or normalized.get("summary") or ""
    if not normalized.get("kind"):
        normalized["kind"] = default_kind
    return normalized


def _extract_claim_anchors(text: str) -> list[str]:
    if not text:
        return []
    anchors = []
    for token in _words(text):
        if token.startswith("http") or token.startswith("#"):
            anchors.append(token)
    if not anchors:
        trimmed = " ".join(_words(text)[:10]).strip()
        if trimmed:
            anchors.append(trimmed)
    return anchors[:3]


def _connected_components(adjacency: dict[str, set[str]]) -> list[set[str]]:
    remaining = set(adjacency)
    components: list[set[str]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = {start}
        while stack:
            node = stack.pop()
            for neighbor in adjacency.get(node, set()):
                if neighbor not in component:
                    component.add(neighbor)
                    stack.append(neighbor)
                    remaining.discard(neighbor)
        components.append(component)
    return components


def _timestamp_key(row: dict[str, Any]) -> str:
    value = row.get("timestamp")
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return str(value or "")


def _case_digest(case: dict[str, Any]) -> str:
    payload = {
        "snapshot_id": case.get("snapshot_id"),
        "event_id": case.get("event_id"),
        "platforms": list(case.get("platforms") or []),
        "posts": [
            {
                "post_id": row.get("post_id"),
                "author_id": row.get("author_id"),
                "timestamp": row.get("timestamp"),
                "content": row.get("content") or row.get("text") or "",
            }
            for row in case.get("posts") or []
        ],
        "comments": [
            {
                "comment_id": row.get("comment_id"),
                "author_id": row.get("author_id"),
                "timestamp": row.get("timestamp"),
                "content": row.get("content") or row.get("text") or "",
            }
            for row in case.get("comments") or []
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _content_ref(row: dict[str, Any], *, kind: str) -> str:
    identifier = row.get("post_id") if kind == "post" else row.get("comment_id")
    return f"{str(row.get('platform') or 'unknown')}:{kind}:{identifier}"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _get(value: Any, *path: str) -> Any:
    current = value or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _words(text: str) -> list[str]:
    parts = []
    for raw in str(text or "").replace("\n", " ").split():
        token = raw.strip()
        if token:
            parts.append(token)
    return parts


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _first_non_empty(values: list[Any]) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
