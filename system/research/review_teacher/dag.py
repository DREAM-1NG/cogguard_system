"""Review Teacher multi-agent DAG.

The Teacher is advisory. It produces evidence, calibration, and disagreement
signals for analysts, but cannot create a canonical verdict by itself.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping


TEACHER_MODEL_VERSION = "review-teacher-dag-v2"
NODE_ORDER = (
    "claim_planning",
    "trusted_retrieval",
    "text_verification",
    "multimodal_verification",
    "harm_stance_context",
    "gold_aggregator",
    "critic_judge",
)


@dataclass(slots=True)
class TeacherDAG:
    """Small interface for the 5+1+1 Teacher research runtime."""

    retriever: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None

    def run(self, case: dict[str, Any], *, student: dict[str, Any] | None = None, job_id: str | None = None) -> dict[str, Any]:
        normalized = _normalize_case(case)
        student_reference = dict(student or {})
        node_results: dict[str, dict[str, Any]] = {}
        node_results["claim_planning"] = _claim_planning(normalized)
        node_results["trusted_retrieval"] = _trusted_retrieval(
            normalized,
            claims=node_results["claim_planning"]["claims"],
            retriever=self.retriever,
        )
        node_results["text_verification"] = _text_verification(
            normalized,
            claims=node_results["claim_planning"]["claims"],
            retrieval=node_results["trusted_retrieval"],
        )
        node_results["multimodal_verification"] = _multimodal_verification(normalized)
        node_results["harm_stance_context"] = _harm_stance_context(normalized)
        node_results["gold_aggregator"] = _gold_aggregator(node_results, student_reference)
        if _needs_critic(node_results["gold_aggregator"], student_reference):
            node_results["critic_judge"] = _critic_judge(node_results, student_reference)
        else:
            node_results["critic_judge"] = {
                "status": "skipped",
                "reason": "No material disagreement between Student and Gold aggregator.",
            }

        final = _final_decision(node_results)
        return {
            "technology": "teacher",
            "schema": "cogguard.review.teacher_dag.v2",
            "status": "completed" if normalized["posts"] else "data_insufficient",
            "verdict_type": "teacher_advisory",
            "verdict_id": job_id or _verdict_id("teacher", normalized),
            "snapshot_id": normalized["snapshot_id"],
            "event_id": normalized["event_id"],
            "platforms": normalized["platforms"],
            "model_version": TEACHER_MODEL_VERSION,
            "teacher_model_families": [
                {"family": "evidence_planner", "mode": "local_replay"},
                {"family": "verification_auditor", "mode": "local_replay"},
            ],
            "advisory": final,
            "review_required": True,
            "canonical_allowed": False,
            "reasoning_trace_saved": False,
            "dag": {
                "version": "5+1+1",
                "nodes": [
                    {
                        "node": name,
                        "status": node_results.get(name, {}).get("status", "missing"),
                        "summary": _node_summary(node_results.get(name, {})),
                    }
                    for name in NODE_ORDER
                ],
            },
            "signals": {
                "nodes": node_results,
                "student_reference": _student_reference(student_reference),
            },
            "evidence": {
                "claims": node_results["claim_planning"]["claims"],
                "retrieval": node_results["trusted_retrieval"]["evidence"][:10],
                "text_verification": node_results["text_verification"]["items"][:10],
                "multimodal": node_results["multimodal_verification"]["items"][:10],
                "context": node_results["harm_stance_context"],
            },
        }


def run_teacher_dag(case: dict[str, Any], *, student: dict[str, Any] | None = None, job_id: str | None = None) -> dict[str, Any]:
    return TeacherDAG().run(case, student=student, job_id=job_id)


def _claim_planning(case: Mapping[str, Any]) -> dict[str, Any]:
    claims = []
    seen = set()
    for row in case.get("posts") or []:
        text = _text(row.get("content") or row.get("text") or row.get("title") or "")
        if not text:
            continue
        anchors = _claim_anchors(text)
        for anchor in anchors:
            claim_id = _stable_id(anchor)
            if claim_id in seen:
                continue
            seen.add(claim_id)
            claims.append(
                {
                    "claim_id": claim_id,
                    "claim_text": anchor,
                    "source_post_id": _first_text(row, ("post_id", "note_id", "item_id", "id")),
                    "platform": _first_text(row, ("platform",)) or "unknown",
                    "stance_target": _target_hint(text),
                }
            )
    return {
        "status": "ok" if claims else "data_insufficient",
        "claims": claims[:20],
        "claim_count": len(claims),
    }


def _trusted_retrieval(
    case: Mapping[str, Any],
    *,
    claims: list[dict[str, Any]],
    retriever: Callable[[dict[str, Any]], list[dict[str, Any]]] | None,
) -> dict[str, Any]:
    evidence = []
    provided = list(dict(case.get("options") or {}).get("retrieval_records") or [])
    for row in provided:
        if isinstance(row, Mapping):
            evidence.append(dict(row))
    if retriever is not None:
        for claim in claims:
            evidence.extend(retriever(claim))
    if not evidence:
        evidence = [
            {
                "source": "event_snapshot",
                "trust_tier": "local_observed",
                "claim_id": claim["claim_id"],
                "snippet": claim["claim_text"],
            }
            for claim in claims
        ]
    return {
        "status": "ok" if evidence else "needs_evidence",
        "evidence": evidence,
        "external_retrieval_used": bool(provided or retriever),
    }


def _text_verification(
    case: Mapping[str, Any],
    *,
    claims: list[dict[str, Any]],
    retrieval: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_text = " ".join(_text(row.get("snippet") or row.get("text") or "") for row in retrieval.get("evidence") or [])
    items = []
    for claim in claims:
        claim_text = _text(claim.get("claim_text"))
        support = _overlap_score(claim_text, evidence_text)
        contradiction = any(term in claim_text.lower() for term in ("fake", "hoax", "\u8c23\u8a00", "\u9020\u5047"))
        if contradiction and support < 0.2:
            status = "needs_evidence"
        elif support >= 0.25:
            status = "supported_by_observed_context"
        else:
            status = "unverified"
        items.append(
            {
                "claim_id": claim["claim_id"],
                "status": status,
                "support_score": round(support, 6),
                "contradiction_signal": contradiction,
            }
        )
    return {
        "status": "ok" if items else "data_insufficient",
        "items": items,
        "supported_count": sum(1 for item in items if item["status"] == "supported_by_observed_context"),
        "needs_evidence_count": sum(1 for item in items if item["status"] == "needs_evidence"),
    }


def _multimodal_verification(case: Mapping[str, Any]) -> dict[str, Any]:
    items = []
    for row in case.get("posts") or []:
        media = _flatten(row.get("media_urls")) + _flatten(row.get("images")) + _flatten(row.get("video_url"))
        decodable = _first_text(row, ("ocr_text", "asr_text", "caption", "alt_text", "image_text"))
        if not media and not decodable:
            continue
        items.append(
            {
                "post_id": _first_text(row, ("post_id", "note_id", "item_id", "id")),
                "status": "verified_decodable" if decodable else "abstain_no_decodable_media",
                "media_count": len(media),
                "decodable_evidence": bool(decodable),
            }
        )
    return {
        "status": "ok" if items else "abstain",
        "items": items,
        "abstained_count": sum(1 for item in items if item["status"].startswith("abstain")),
    }


def _harm_stance_context(case: Mapping[str, Any]) -> dict[str, Any]:
    texts = [_text(row.get("content") or row.get("text") or "") for row in case.get("posts") or []]
    harm_terms = Counter()
    for text in texts:
        lowered = text.lower()
        for term in (
            "hate",
            "attack",
            "threat",
            "rumor",
            "fake",
            "\u4ec7\u6068",
            "\u653b\u51fb",
            "\u717d\u52a8",
            "\u8c23\u8a00",
        ):
            if term in lowered:
                harm_terms[term] += 1
    coordination_discover = dict(dict(case.get("options") or {}).get("coordination_discover_context") or {})
    propagation_analysis = dict(dict(case.get("options") or {}).get("propagation_analysis_context") or {})
    return {
        "status": "ok",
        "harm_term_counts": dict(harm_terms),
        "platforms": list(case.get("platforms") or []),
        "coordination_discover_context": _compact_context(coordination_discover),
        "propagation_analysis_context": _compact_context(propagation_analysis),
    }


def _gold_aggregator(nodes: Mapping[str, dict[str, Any]], student: Mapping[str, Any]) -> dict[str, Any]:
    verification = nodes["text_verification"]
    context = nodes["harm_stance_context"]
    supported = int(verification.get("supported_count") or 0)
    needs_evidence = int(verification.get("needs_evidence_count") or 0)
    harm_count = sum(int(value) for value in dict(context.get("harm_term_counts") or {}).values())
    student_score = _as_float(student.get("score"))
    score = min(0.99, 0.2 + 0.12 * supported + 0.08 * harm_count + 0.2 * student_score)
    if needs_evidence > supported:
        decision = "needs_evidence"
    elif score >= 0.55:
        decision = "harmful_advisory"
    elif abs(score - 0.5) < 0.08:
        decision = "uncertain"
    else:
        decision = "non_harmful_advisory"
    return {
        "status": "ok",
        "decision": decision,
        "score": round(score, 6),
        "calibration": {
            "aggregator": "gold_calibrated_contract",
            "gold_labels_available": False,
            "canonical_requires_analyst_approval": True,
        },
    }


def _critic_judge(nodes: Mapping[str, dict[str, Any]], student: Mapping[str, Any]) -> dict[str, Any]:
    gold = nodes["gold_aggregator"]
    student_label = str(student.get("label") or "uncertain")
    return {
        "status": "completed",
        "disagreement": {
            "student_label": student_label,
            "teacher_decision": gold.get("decision"),
            "student_score": student.get("score"),
            "teacher_score": gold.get("score"),
        },
        "judge": "prefer_needs_evidence" if gold.get("decision") == "needs_evidence" else "prefer_teacher_advisory",
    }


def _final_decision(nodes: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    gold = nodes["gold_aggregator"]
    critic = nodes["critic_judge"]
    decision = str(gold.get("decision") or "needs_evidence")
    if critic.get("judge") == "prefer_needs_evidence":
        decision = "needs_evidence"
    return {
        "decision": decision,
        "score": gold.get("score", 0.0),
        "recommended_actions": {
            "human_review": 1,
            "collect_more_evidence": 1 if decision == "needs_evidence" else 0,
            "use_for_distillation_after_approval": 1,
        },
        "avg_agent_confidence": round(max(_as_float(gold.get("score")), 1.0 - _as_float(gold.get("score"))), 6),
        "external_followup_required": decision == "needs_evidence",
    }


def _needs_critic(gold: Mapping[str, Any], student: Mapping[str, Any]) -> bool:
    student_label = str(student.get("label") or "")
    teacher_decision = str(gold.get("decision") or "")
    if teacher_decision == "needs_evidence":
        return True
    if not student_label:
        return False
    return (student_label == "harmful" and "non_harmful" in teacher_decision) or (
        student_label == "non_harmful" and "harmful" in teacher_decision
    )


def _normalize_case(case: Mapping[str, Any]) -> dict[str, Any]:
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
        "options": dict(case.get("options") or {}),
    }


def _node_summary(node: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in node.items()
        if key in {"claim_count", "supported_count", "needs_evidence_count", "abstained_count", "decision", "score", "reason"}
    }


def _student_reference(student: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "verdict_id": student.get("verdict_id"),
        "label": student.get("label"),
        "score": student.get("score"),
        "model_version": student.get("model_version"),
    }


def _claim_anchors(text: str) -> list[str]:
    words = _words(text)
    anchors = [word for word in words if word.startswith("#") or word.startswith("http")]
    if not anchors and words:
        anchors.append(" ".join(words[:12]))
    return anchors[:3]


def _target_hint(text: str) -> str:
    lowered = text.lower()
    for target in ("trump", "\u7279\u6717\u666e", "china", "\u4e2d\u56fd", "\u8bbf\u534e"):
        if target in lowered:
            return target
    return ""


def _overlap_score(left: str, right: str) -> float:
    left_tokens = set(_words(left.lower()))
    right_tokens = set(_words(right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _compact_context(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value.get(key)
        for key in ("status", "model_version", "summary", "scale_forecast", "next_hop_ranking")
        if key in value
    }


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


def _words(text: str) -> list[str]:
    return [part.strip() for part in str(text or "").replace("\n", " ").split() if part.strip()]


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _verdict_id(prefix: str, case: Mapping[str, Any]) -> str:
    return f"{prefix}_{hashlib.sha256(_json(case).encode('utf-8')).hexdigest()[:24]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        timestamp = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc).isoformat()
    return str(value)
