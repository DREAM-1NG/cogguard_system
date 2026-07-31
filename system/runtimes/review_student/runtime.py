"""Review Student deployable runtime.

The runtime exposes a stable ``predict(case) -> ReviewVerdict`` seam. A fitted
checkpoint can be registered later; until then the runtime returns a shadow
preliminary verdict and explicitly requires review.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from pathlib import Path
from typing import Any, Mapping


STUDENT_MODEL_VERSION = "review-student-runtime-v2"
ARCHITECTURE = {
    "post_encoder": "xlm-roberta-base",
    "multimodal": "frozen_feature_inputs",
    "post_fusion": "learned_gating_contract",
    "user_level": "attention_mil_temporal_contract",
    "community_level": "heterogeneous_gnn_contract",
    "distillation_losses": ["gold_ce", "teacher_kl", "evidence_alignment", "contrastive", "disagreement_weight"],
}
HARM_TERMS = {
    "rumor": 0.12,
    "fake": 0.12,
    "hoax": 0.12,
    "attack": 0.1,
    "hate": 0.16,
    "threat": 0.16,
    "\u8c23\u8a00": 0.14,
    "\u717d\u52a8": 0.16,
    "\u4ec7\u6068": 0.18,
    "\u653b\u51fb": 0.12,
    "\u9020\u5047": 0.14,
    "\u9634\u8c0b": 0.1,
}


class StudentRuntime:
    """Synchronous runtime for deployed Review review."""

    def predict_sync(self, case: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_case(case)
        if not normalized["posts"]:
            return _insufficient_verdict(normalized, reason="No posts are available in the EventSnapshot.")

        options = dict(normalized.get("options") or {})
        active_model = options.get("active_model") if isinstance(options.get("active_model"), Mapping) else {}
        checkpoint = _checkpoint_status(
            options.get("student_checkpoint")
            or options.get("student_checkpoint_path")
            or active_model.get("artifact_uri")
        )
        post_scores = [_score_post(row) for row in normalized["posts"]]
        user_scores = _attention_mil_scores(post_scores)
        community_scores = _community_message_passing(normalized, user_scores)
        score = _fuse_case_score(post_scores, user_scores, community_scores)
        confidence = round(max(score, 1.0 - score), 6)
        label = _label(score, confidence)
        active_learning = build_active_learning_signal(
            score=score,
            confidence=confidence,
            case=normalized,
            teacher_reference=options.get("teacher_reference"),
        )
        model_status = "checkpoint_active" if checkpoint["available"] and active_model else (
            "checkpoint_registered_shadow" if checkpoint["available"] else "shadow_untrained"
        )
        review_required = bool(model_status != "checkpoint_active" or active_learning["priority"] >= 0.35)

        return {
            "technology": "student",
            "schema": "cogguard.review.review_verdict.v2",
            "status": "ok",
            "verdict_type": "preliminary",
            "verdict_id": _verdict_id("student", normalized),
            "snapshot_id": normalized["snapshot_id"],
            "event_id": normalized["event_id"],
            "platforms": normalized["platforms"],
            "model_version": STUDENT_MODEL_VERSION,
            "model_status": model_status,
            "label": label,
            "score": round(score, 6),
            "confidence": confidence,
            "risk_level": _risk_level(score, community_scores),
            "abstain": confidence < 0.62 or model_status != "checkpoint_active",
            "review_required": review_required,
            "review_reason": _review_reasons(active_learning, model_status=model_status),
            "architecture": ARCHITECTURE,
            "checkpoint": checkpoint,
            "distillation": build_distillation_plan(
                teacher_traces=options.get("teacher_traces") or [],
                approved_verdicts=options.get("approved_verdicts") or [],
            ),
            "signals": {
                "post": _summarize_post_scores(post_scores),
                "user_mil": user_scores,
                "community_gnn": community_scores,
                "active_learning": active_learning,
            },
            "evidence": {
                "top_posts": _top_post_evidence(post_scores),
                "active_learning": active_learning,
                "capability_boundary": _capability_boundary(model_status),
            },
        }


def build_active_learning_signal(
    *,
    score: float,
    confidence: float,
    case: Mapping[str, Any],
    teacher_reference: Any = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    uncertainty = 1.0 - abs(float(score) - 0.5) * 2.0
    if uncertainty >= 0.45:
        reasons.append("uncertainty")

    teacher_disagreement = 0.0
    if isinstance(teacher_reference, Mapping):
        teacher_label = str(teacher_reference.get("label") or teacher_reference.get("decision") or "")
        student_label = _label(score, confidence)
        if teacher_label and teacher_label not in {student_label, "uncertain"}:
            teacher_disagreement = 1.0
            reasons.append("teacher_student_disagreement")

    platforms = list(case.get("platforms") or [])
    if len(platforms) > 1:
        reasons.append("diversity")
    if _ood_score(case) >= 0.5:
        reasons.append("ood")
    if _drift_score(case) >= 0.5:
        reasons.append("drift")
    if _random_audit_bucket(case) == 0:
        reasons.append("random_audit")

    priority = min(
        1.0,
        0.38 * uncertainty
        + 0.25 * teacher_disagreement
        + 0.15 * _ood_score(case)
        + 0.12 * _drift_score(case)
        + (0.1 if "diversity" in reasons else 0.0)
        + (0.03 if "random_audit" in reasons else 0.0),
    )
    return {
        "priority": round(priority, 6),
        "reasons": sorted(set(reasons)),
        "policy": {
            "feedback_threshold": 200,
            "minimum_retrain_interval_days": 7,
            "random_audit_rate": 0.01,
            "activation_requires_dual_approval": True,
        },
    }


def build_distillation_plan(*, teacher_traces: list[Any], approved_verdicts: list[Any]) -> dict[str, Any]:
    trace_count = len([row for row in teacher_traces if isinstance(row, Mapping)])
    approved_count = len([row for row in approved_verdicts if isinstance(row, Mapping)])
    return {
        "status": "ready_for_candidate_training" if approved_count >= 200 else "insufficient_approved_feedback",
        "teacher_trace_count": trace_count,
        "approved_verdict_count": approved_count,
        "losses": ARCHITECTURE["distillation_losses"],
        "student_deploy_gate": {
            "teacher_macro_f1_gap_max": 0.03,
            "ece_max": 0.08,
            "single_post_p95_seconds_on_8gb_gpu": 2.0,
        },
    }


def _score_post(row: Mapping[str, Any]) -> dict[str, Any]:
    text = _text(row.get("content") or row.get("text") or row.get("title") or "")
    lowered = text.lower()
    score = 0.18
    matched = []
    for term, weight in HARM_TERMS.items():
        if term.lower() in lowered:
            score += weight
            matched.append(term)
    media_fields = _flatten(row.get("media_urls")) + _flatten(row.get("images")) + _flatten(row.get("video_url"))
    multimodal_score = 0.08 if media_fields and any(
        term in lowered for term in ("fake", "\u8c23\u8a00", "\u653b\u51fb", "hate")
    ) else 0.0
    score = min(0.95, score + multimodal_score)
    return {
        "post_id": _first_text(row, ("post_id", "note_id", "item_id", "id")),
        "author_id": _first_text(row, ("author_id", "user_id", "uid", "account_id")),
        "platform": _first_text(row, ("platform",)) or "unknown",
        "timestamp": _timestamp_key(row.get("timestamp") or row.get("created_at") or row.get("publish_time")),
        "score": round(score, 6),
        "text_score": round(score - multimodal_score, 6),
        "multimodal_score": round(multimodal_score, 6),
        "matched_terms": matched,
        "excerpt": text[:240],
    }


def _attention_mil_scores(post_scores: list[dict[str, Any]]) -> dict[str, Any]:
    by_user: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in post_scores:
        author_id = row.get("author_id")
        if author_id:
            by_user[author_id].append(row)
    accounts = []
    for author_id, rows in sorted(by_user.items()):
        weights = _softmax([float(row["score"]) for row in rows])
        score = sum(float(row["score"]) * weight for row, weight in zip(rows, weights))
        accounts.append(
            {
                "account_id": author_id,
                "score": round(score, 6),
                "post_count": len(rows),
                "attention": [
                    {"post_id": row["post_id"], "weight": round(weight, 6)}
                    for row, weight in zip(rows, weights)
                ],
            }
        )
    accounts.sort(key=lambda row: (row["score"], row["post_count"], row["account_id"]), reverse=True)
    return {
        "schema": "review-student-user-mil-v1",
        "accounts": accounts,
        "summary": {
            "account_count": len(accounts),
            "high_risk_accounts": sum(1 for row in accounts if row["score"] >= 0.65),
        },
    }


def _community_message_passing(case: Mapping[str, Any], user_scores: Mapping[str, Any]) -> dict[str, Any]:
    base = {row["account_id"]: float(row["score"]) for row in user_scores.get("accounts", [])}
    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    content_author = {}
    for row in list(case.get("posts") or []) + list(case.get("comments") or []):
        author = _first_text(row, ("author_id", "user_id", "uid", "account_id"))
        content_id = _first_text(row, ("post_id", "comment_id", "note_id", "item_id", "id"))
        if author and content_id:
            content_author[content_id] = author
    for relation in case.get("relationships") or []:
        if not isinstance(relation, Mapping):
            continue
        source = content_author.get(str(relation.get("source_id") or relation.get("source_ref") or ""))
        target = content_author.get(str(relation.get("target_id") or relation.get("target_ref") or ""))
        if source and target and source != target:
            adjacency[source].add(target)
            adjacency[target].add(source)

    propagated = dict(base)
    for account, neighbors in adjacency.items():
        neighbor_scores = [base.get(neighbor, 0.0) for neighbor in neighbors]
        if neighbor_scores:
            propagated[account] = 0.7 * base.get(account, 0.0) + 0.3 * mean(neighbor_scores)
    communities = _components(adjacency)
    community_rows = []
    for index, members in enumerate(communities):
        scores = [propagated.get(member, 0.0) for member in members]
        community_rows.append(
            {
                "community_id": f"community_{index}",
                "members": sorted(members),
                "score": round(mean(scores), 6) if scores else 0.0,
                "edge_count": sum(len(adjacency.get(member, set())) for member in members) // 2,
            }
        )
    return {
        "schema": "review-student-community-gnn-v1",
        "checkpoint_status": "untrained_message_passing_scaffold",
        "communities": community_rows,
        "summary": {
            "community_count": len(community_rows),
            "high_risk_communities": sum(1 for row in community_rows if row["score"] >= 0.65),
        },
    }


def _fuse_case_score(
    post_scores: list[dict[str, Any]],
    user_scores: Mapping[str, Any],
    community_scores: Mapping[str, Any],
) -> float:
    post_mean = mean([float(row["score"]) for row in post_scores]) if post_scores else 0.5
    user_rows = list(user_scores.get("accounts") or [])
    user_mean = mean([float(row["score"]) for row in user_rows]) if user_rows else post_mean
    community_rows = list(community_scores.get("communities") or [])
    community_mean = mean([float(row["score"]) for row in community_rows]) if community_rows else user_mean
    return min(0.99, max(0.01, 0.5 * post_mean + 0.3 * user_mean + 0.2 * community_mean))


def _normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    posts = [dict(row) for row in case.get("posts") or [] if isinstance(row, Mapping)]
    comments = [dict(row) for row in case.get("comments") or [] if isinstance(row, Mapping)]
    platforms = [str(row) for row in case.get("platforms") or [] if str(row).strip()]
    if not platforms:
        platforms = sorted({str(row.get("platform") or "").strip() for row in posts + comments if str(row.get("platform") or "").strip()})
    return {
        "snapshot_id": str(case.get("snapshot_id") or ""),
        "event_id": str(case.get("event_id") or ""),
        "platforms": platforms,
        "posts": posts,
        "comments": comments,
        "relationships": [dict(row) for row in case.get("relationships") or [] if isinstance(row, Mapping)],
        "quality_report": dict(case.get("quality_report") or {}),
        "options": dict(case.get("options") or {}),
    }


def _insufficient_verdict(case: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "technology": "student",
        "schema": "cogguard.review.review_verdict.v2",
        "status": "data_insufficient",
        "verdict_type": "preliminary",
        "verdict_id": _verdict_id("student", case),
        "snapshot_id": case.get("snapshot_id"),
        "event_id": case.get("event_id"),
        "model_version": STUDENT_MODEL_VERSION,
        "model_status": "shadow_untrained",
        "reason": reason,
        "architecture": ARCHITECTURE,
        "review_required": True,
        "abstain": True,
    }


def _checkpoint_status(value: Any) -> dict[str, Any]:
    if not value:
        return {"available": False, "path": "", "status": "missing_checkpoint"}
    path = Path(str(value))
    return {
        "available": path.exists(),
        "path": str(path),
        "status": "registered" if path.exists() else "missing_checkpoint",
    }


def _review_reasons(active_learning: Mapping[str, Any], *, model_status: str) -> list[str]:
    reasons = list(active_learning.get("reasons") or [])
    if model_status != "checkpoint_active":
        reasons.append("student_checkpoint_not_active")
    return sorted(set(reasons))


def _summarize_post_scores(post_scores: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(row["score"]) for row in post_scores]
    labels = Counter(_label(score, max(score, 1.0 - score)) for score in scores)
    return {
        "post_count": len(post_scores),
        "mean_score": round(mean(scores), 6) if scores else 0.0,
        "max_score": round(max(scores), 6) if scores else 0.0,
        "label_counts": dict(labels),
    }


def _top_post_evidence(post_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(post_scores, key=lambda row: (row["score"], row["post_id"]), reverse=True)
    return [
        {
            "post_id": row["post_id"],
            "author_id": row["author_id"],
            "platform": row["platform"],
            "score": row["score"],
            "matched_terms": row["matched_terms"],
            "excerpt": row["excerpt"],
        }
        for row in ranked[:5]
    ]


def _capability_boundary(model_status: str) -> dict[str, Any]:
    return {
        "runtime": "system/runtimes/review_student",
        "model_status": model_status,
        "canonical_allowed": False,
        "reason": "Student output is preliminary until analyst approval creates an immutable canonical verdict.",
    }


def _label(score: float, confidence: float) -> str:
    if confidence < 0.58:
        return "uncertain"
    return "harmful" if score >= 0.5 else "non_harmful"


def _risk_level(score: float, community_scores: Mapping[str, Any]) -> str:
    if score >= 0.72 or int(dict(community_scores.get("summary") or {}).get("high_risk_communities") or 0) > 0:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _ood_score(case: Mapping[str, Any]) -> float:
    platforms = list(case.get("platforms") or [])
    known = {"weibo", "douyin", "xhs", "news"}
    unknown = [platform for platform in platforms if platform not in known]
    return min(1.0, len(unknown) / max(len(platforms), 1))


def _drift_score(case: Mapping[str, Any]) -> float:
    quality = dict(case.get("quality_report") or {})
    issues = list(quality.get("issues") or [])
    missing = int(quality.get("missing_timestamps") or 0) + int(quality.get("missing_authors") or 0)
    return min(1.0, 0.1 * len(issues) + 0.02 * missing)


def _random_audit_bucket(case: Mapping[str, Any]) -> int:
    digest = hashlib.sha256(_json(case).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _components(adjacency: Mapping[str, set[str]]) -> list[set[str]]:
    remaining = set(adjacency)
    components = []
    while remaining:
        node = remaining.pop()
        stack = [node]
        component = {node}
        while stack:
            current = stack.pop()
            for neighbor in adjacency.get(current, set()):
                if neighbor not in component:
                    component.add(neighbor)
                    stack.append(neighbor)
                    remaining.discard(neighbor)
        components.append(component)
    return components


def _softmax(values: list[float]) -> list[float]:
    if not values:
        return []
    top = max(values)
    exps = [math.exp(value - top) for value in values]
    total = sum(exps) or 1.0
    return [value / total for value in exps]


def _timestamp_key(value: Any) -> str:
    if isinstance(value, datetime):
        timestamp = value
    elif value in (None, ""):
        return ""
    else:
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat()


def _verdict_id(prefix: str, case: Mapping[str, Any]) -> str:
    return f"{prefix}_{hashlib.sha256(_json(case).encode('utf-8')).hexdigest()[:24]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _flatten(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        result = []
        for item in value.values():
            result.extend(_flatten(item))
        return result
    if isinstance(value, (list, tuple, set)):
        result = []
        for item in value:
            result.extend(_flatten(item))
        return result
    return [str(value)]


def _first_text(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        text = _text(row.get(key))
        if text:
            return text
    return ""


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()
