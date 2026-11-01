"""Public platform governance references for Review analyst reports.

The library is used as report-template and action-vocabulary guidance only.
It must not override detector outputs, policy scores, or human decisions.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
import json


CONFIG_PATH = Path(__file__).resolve().parent / "config" / "governance_references.json"


@lru_cache(maxsize=1)
def load_governance_reference_library() -> dict[str, Any]:
    """Load the read-only public platform governance reference library."""
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data


def build_governance_reference_context(
    context: dict[str, Any],
    *,
    max_categories: int = 3,
    max_references: int = 5,
) -> dict[str, Any]:
    """Select compact governance references for a manual review context."""
    library = load_governance_reference_library()
    categories = _rank_categories(context, library)[:max_categories]
    if not categories:
        categories = [_fallback_category(library)]

    refs_by_id = {str(item.get("ref_id")): item for item in library.get("platform_references") or []}
    selected_refs: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for category in categories:
        for ref_id in category.get("reference_refs") or []:
            ref = refs_by_id.get(str(ref_id))
            if ref and ref_id not in seen_refs:
                selected_refs.append(_compact_reference(ref))
                seen_refs.add(str(ref_id))
            if len(selected_refs) >= max_references:
                break
        if len(selected_refs) >= max_references:
            break

    return {
        "schema_version": "review-governance-reference-context-v1",
        "report_audience": (library.get("report_template") or {}).get("audience"),
        "matched_categories": [_compact_category(item) for item in categories],
        "platform_reference_refs": selected_refs,
        "report_template": library.get("report_template") or {},
        "matching_basis": _matching_basis(context),
        "usage_boundary": {
            "public_references_only": True,
            "guides_report_structure_only": True,
            "does_not_override_detector_outputs": True,
            "does_not_make_legal_conclusions": True,
            "no_auto_enforcement": True,
        },
    }


def build_governance_report_sidecar(
    *,
    context: dict[str, Any],
    report_text: str | None = None,
) -> dict[str, Any]:
    """Build a normalized audit summary for the Judge's governance report."""
    governance = context.get("governance_reference") or build_governance_reference_context(context)
    categories = [item for item in governance.get("matched_categories") or [] if isinstance(item, dict)]
    primary_category = categories[0] if categories else {}
    actions = _recommended_actions(context, primary_category, governance)
    sufficiency = _evidence_sufficiency(context)
    confirmation_items = _human_confirmation_items(context, sufficiency)
    default_text = _default_governance_report_text(
        category=str(primary_category.get("name") or "无直接平台模板匹配"),
        evidence_sufficiency=sufficiency,
        actions=actions,
        confirmation_items=confirmation_items,
        refs=governance.get("platform_reference_refs") or [],
    )
    return {
        "schema_version": "review-governance-report-sidecar-v1",
        "governance_report_text": (report_text or "").strip() or default_text,
        "governance_category": primary_category.get("name") or "无直接平台模板匹配",
        "governance_category_id": primary_category.get("category_id"),
        "evidence_sufficiency": sufficiency,
        "recommended_action": actions[0] if actions else "补证",
        "recommended_actions": actions,
        "platform_reference_refs": governance.get("platform_reference_refs") or [],
        "human_confirmation_items": confirmation_items,
        "matched_categories": categories,
        "usage_boundary": governance.get("usage_boundary") or {},
    }


def _rank_categories(context: dict[str, Any], library: dict[str, Any]) -> list[dict[str, Any]]:
    haystack = _context_text(context)
    media_conflict = _has_media_conflict(context)
    has_media = bool(context.get("media_inputs"))
    has_claim_context = _has_claim_context(context)
    has_propagation = bool((context.get("propagation_context") or {}).get("graph_summary"))
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for index, category in enumerate(library.get("governance_categories") or []):
        score = 0.0
        for signal in category.get("signals") or []:
            if signal and str(signal).lower() in haystack:
                score += 2.0
        category_id = str(category.get("category_id") or "")
        if category_id == "multimodal_context_mismatch" and (media_conflict or has_media):
            score += 3.0 if media_conflict else 1.2
        if category_id == "misinformation" and has_claim_context:
            score += 2.0
        if category_id == "group_polarization" and has_propagation:
            score += 0.8
        if score > 0:
            scored.append((score, -index, category))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored]


def _fallback_category(library: dict[str, Any]) -> dict[str, Any]:
    categories = library.get("governance_categories") or []
    for category in categories:
        if category.get("category_id") == "misinformation":
            return category
    return categories[0] if categories else {"category_id": None, "name": "无直接平台模板匹配"}


def _compact_reference(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "ref_id": ref.get("ref_id"),
        "platform": ref.get("platform"),
        "title": ref.get("title"),
        "url": ref.get("url"),
        "reference_type": ref.get("reference_type"),
        "governance_use": ref.get("governance_use"),
    }


def _compact_category(category: dict[str, Any]) -> dict[str, Any]:
    return {
        "category_id": category.get("category_id"),
        "name": category.get("name"),
        "default_actions": category.get("default_actions") or [],
        "reference_refs": category.get("reference_refs") or [],
    }


def _context_text(context: dict[str, Any]) -> str:
    snippets: list[str] = []
    for post in context.get("selected_posts") or []:
        if not isinstance(post, dict):
            continue
        snippets.extend(
            str(post.get(key) or "")
            for key in (
                "text",
                "content",
                "harm_label",
                "label",
                "harm_type",
                "target",
                "rationale",
            )
        )
        snippets.append(json.dumps(post.get("evidence") or {}, ensure_ascii=False, default=str))
        snippets.append(json.dumps(post.get("stance") or {}, ensure_ascii=False, default=str))
        snippets.append(json.dumps(post.get("post_view_detection") or {}, ensure_ascii=False, default=str))
    snippets.append(json.dumps(context.get("review_queue") or {}, ensure_ascii=False, default=str))
    snippets.append(json.dumps(context.get("active_retrieval") or {}, ensure_ascii=False, default=str))
    return "\n".join(snippets).lower()


def _matching_basis(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_post_count": len(context.get("selected_posts") or []),
        "media_input_count": len(context.get("media_inputs") or []),
        "has_media_conflict": _has_media_conflict(context),
        "has_claim_or_evidence_context": _has_claim_context(context),
        "has_propagation_context": bool((context.get("propagation_context") or {}).get("graph_summary")),
    }


def _has_media_conflict(context: dict[str, Any]) -> bool:
    for post in context.get("selected_posts") or []:
        if not isinstance(post, dict):
            continue
        view = post.get("post_view_detection") or {}
        conflict = view.get("conflict")
        if bool(conflict):
            return True
    return False


def _has_claim_context(context: dict[str, Any]) -> bool:
    if (context.get("active_retrieval") or {}).get("queries"):
        return True
    propagation = context.get("propagation_context") or {}
    if propagation.get("claim_rank"):
        return True
    for post in context.get("selected_posts") or []:
        if not isinstance(post, dict):
            continue
        stance = post.get("stance") or {}
        if stance.get("claim_id") or stance.get("label"):
            return True
    return False


def _evidence_sufficiency(context: dict[str, Any]) -> str:
    evidence_count = 0
    for post in context.get("selected_posts") or []:
        if isinstance(post, dict) and post.get("evidence"):
            evidence_count += 1
    retrieval = context.get("active_retrieval") or {}
    evidence_count += sum(len(item.get("top_evidence") or []) for item in retrieval.get("local_results") or [])
    evidence_count += sum(len(item.get("top_evidence") or []) for item in retrieval.get("external_results") or [])
    if evidence_count >= 4:
        return "充分"
    if evidence_count >= 1 or context.get("media_inputs"):
        return "部分充分"
    return "不充分"


def _recommended_actions(
    context: dict[str, Any],
    primary_category: dict[str, Any],
    governance: dict[str, Any],
) -> list[str]:
    actions = list(primary_category.get("default_actions") or [])
    if _evidence_sufficiency(context) == "不充分":
        actions = ["补证", "人审", *[item for item in actions if item not in {"补证", "人审"}]]
    if _has_media_conflict(context) and "标注" not in actions:
        actions.append("标注")
    allowed = set((governance.get("report_template") or {}).get("recommended_actions") or [])
    deduped = []
    for action in actions or ["补证", "人审"]:
        if action in allowed and action not in deduped:
            deduped.append(action)
    return deduped[:5]


def _human_confirmation_items(context: dict[str, Any], sufficiency: str) -> list[str]:
    items: list[str] = []
    if sufficiency != "充分":
        items.append("补充核验证据是否足以支撑处置建议")
    if _has_media_conflict(context):
        items.append("人工确认图文、音视或视频关键帧是否存在语境错配")
    if _has_claim_context(context):
        items.append("人工确认主张核验结论与帖子表达对象是否一致")
    if not items:
        items.append("人工确认该建议仅作为内部治理研判依据")
    return items[:6]


def _default_governance_report_text(
    *,
    category: str,
    evidence_sufficiency: str,
    actions: list[str],
    confirmation_items: list[str],
    refs: list[dict[str, Any]],
) -> str:
    ref_titles = "、".join(str(item.get("title") or item.get("ref_id")) for item in refs[:3]) or "无直接平台模板匹配"
    action_text = "、".join(actions) if actions else "补证"
    confirm_text = "；".join(confirmation_items)
    return (
        f"治理研判总报告\n\n"
        f"风险类型：{category}。\n"
        f"证据充分性：{evidence_sufficiency}。\n"
        f"参考依据：{ref_titles}。\n"
        f"处置建议：{action_text}。本建议仅供平台内部人工研判，不自动处置、不自动发布。\n"
        f"人工确认项：{confirm_text}。"
    )
