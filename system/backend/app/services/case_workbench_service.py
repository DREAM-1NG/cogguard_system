"""Case Workbench read model for the fast prototype workflow."""

from __future__ import annotations

import hashlib
from html import escape
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.analysis.semantic_enrichment import (
    HuggingFaceSemanticRuntime,
    SemanticModelUnavailable,
    analyze_semantic_enrichment_snapshot,
    blocked_semantic_artifact,
    propagation_path_overlay,
)
from app.core.analysis.snapshots import build_event_snapshot
from app.core.analysis.contracts import TimeWindow
from app.db.mongodb import get_mongo_db
from app.schemas.case_research import ResearchArchiveEntry
from app.services.case_frozen_artifact import FrozenCaseArtifactStore
from app.services.event_data import load_event_comments, load_event_posts
from app.services.case_research_archive import verify_research_archive

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
PROTOTYPE_CONSTRAINTS = {
    "platform_evidence_scope": "weibo_only_with_xhs_gap",
    "semantic_examples_text_scope": "excerpt_only_not_full_source_text",
    "semantic_score_policy": "evidence_overlay_only",
    "risk_score_boundary": "semantic_artifacts_do_not_mutate_coordination_propagation_review_scores",
    "model_validation_status": "candidate_unvalidated",
    "pdf_export_status": "html_pdf_fallback",
}
_DEFAULT_ARTIFACT_STORE = object()
PRIMARY_CLAIM = {
    "claim_id": "claim_cctv_primary",
    "role": "primary",
    "status": "candidate_unvalidated",
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
        "status": "candidate_unvalidated",
        "content_capture": "unavailable",
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
    "status": "candidate_unvalidated",
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
        "status": "candidate_unvalidated",
        "content_capture": "unavailable",
    },
}


class CaseWorkbenchService:
    """Build a case-level projection from current event evidence and analysis contracts."""

    def __init__(
        self,
        mongo_db: Any | None = None,
        demo_state: dict[str, Any] | None = None,
        *,
        missing_primary_claim: bool = False,
        semantic_runtime: Any | None = None,
        artifact_store: FrozenCaseArtifactStore | None | object = _DEFAULT_ARTIFACT_STORE,
    ) -> None:
        self.mongo_db = mongo_db
        self.demo_state = demo_state if demo_state is not None else _new_demo_state()
        self.missing_primary_claim = missing_primary_claim
        self.semantic_runtime = semantic_runtime
        if artifact_store is _DEFAULT_ARTIFACT_STORE:
            self.artifact_store = FrozenCaseArtifactStore() if mongo_db is None else None
        else:
            self.artifact_store = artifact_store

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
        frozen_artifact = self._load_frozen_artifact(case_id)
        if frozen_artifact is not None:
            return _frozen_case_projection(frozen_artifact)
        posts, comments, source_mode = await self._load_evidence(DEFAULT_EVENT_ID)
        snapshot = _snapshot_from_evidence(posts, comments)
        primary_template, supplementary_claim = _archived_demo_claims()
        primary_claim = None if self.missing_primary_claim else PRIMARY_CLAIM
        if primary_claim is not None:
            primary_claim = primary_template
        semantic = self._semantic_artifact(snapshot, {"primary_claim": primary_claim})
        platforms = _platforms(posts, comments)
        blockers = [
            *_blockers(platforms),
            *_primary_claim_blockers(primary_claim),
            *semantic.get("active_blockers", []),
        ]
        acknowledgements = list(self.demo_state["blocker_acknowledgements"])
        acknowledged_blocker_ids = {record["blocker_id"] for record in acknowledgements}
        active_blockers = [blocker for blocker in blockers if blocker["blocker_id"] not in acknowledged_blocker_ids]
        actions = _action_rows(self.demo_state)
        feedback = list(self.demo_state["feedback"])
        semantic_corrections = list(self.demo_state["semantic_corrections"])
        closeout_review = self.demo_state.get("closeout_review")
        audit_events = list(self.demo_state["audit_events"])
        state = _case_state(blockers=active_blockers, actions=actions, feedback=feedback, closeout_review=closeout_review)
        canonical_verdict = {
            "verdict_id": "canonical_demo_verdict",
            "status": "approved",
            "label": "needs_human_review",
            "source": "demo_analyst_approval",
        }
        closure_checklist = _closure_checklist(
            canonical_verdict=canonical_verdict,
            actions=actions,
            feedback=feedback,
            closeout_review=closeout_review,
            active_blockers=active_blockers,
            blocker_acknowledgements=acknowledgements,
            primary_claim=primary_claim,
            supplementary_claims=[supplementary_claim],
            semantic=semantic,
            semantic_score_policy="evidence_overlay_only",
        )
        report_hash = _hash_payload(
            {
                "case_id": DEFAULT_CASE_ID,
                "event_id": DEFAULT_EVENT_ID,
                "state": state,
                "snapshot_id": snapshot.snapshot_id,
                "run_id": "run_case_workbench_demo",
                "primary_claim_excerpt": primary_claim["excerpt"] if primary_claim else None,
                "primary_claim_source": primary_claim["source"] if primary_claim else None,
                "semantic_artifact_hash": semantic["artifact_sha256"],
                "semantic_model_status": semantic["model_status"],
                "blockers": [(blocker["code"], blocker["message"]) for blocker in active_blockers],
                "blocker_acknowledgements": acknowledgements,
                "actions": [(action["action_id"], action["status"]) for action in actions],
                "feedback_count": len(feedback),
                "semantic_corrections": [
                    (
                        correction["correction_id"],
                        correction["artifact_id"],
                        correction["module"],
                        correction["target_ref"],
                        correction["corrected_value"],
                        correction["status"],
                    )
                    for correction in semantic_corrections
                ],
                "audit_events": [
                    (
                        event["event_id"],
                        event["action"],
                        event["actor_id"],
                        event["target_id"],
                        event["created_at"],
                        event.get("payload") or {},
                    )
                    for event in audit_events
                ],
                "closeout_summary": closeout_review.get("summary") if closeout_review else None,
                "closure_checklist": [(item["key"], item["status"]) for item in closure_checklist],
                "prototype_constraints": PROTOTYPE_CONSTRAINTS,
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
            "primary_claim": _claim_with_hash(primary_claim) if primary_claim else None,
            "supplementary_claims": [_claim_with_hash(supplementary_claim)],
            "canonical_verdict": canonical_verdict,
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
                    "runtime_status": semantic.get("runtime_status"),
                    "runtime_backend": semantic.get("runtime_backend"),
                    "model_status": semantic["model_status"],
                    "model_version": semantic.get("model_version"),
                    "model_versions": semantic.get("model_versions") or semantic.get("candidate_models") or {},
                    "validation_status": semantic.get("validation_status"),
                    "embedding_manifest": semantic.get("embedding_manifest"),
                    "semantic_blocker": semantic.get("semantic_blocker"),
                    "artifact_sha256": semantic["artifact_sha256"],
                    "summary": {
                        "sentiment": semantic["sentiment"]["summary"],
                        "top_keywords": semantic["keywords"]["main_posts"][:8],
                        "topics": semantic["topics"]["main_posts"],
                        "entities": semantic["entities"]["main_posts"][:12],
                        "stance": semantic["stance"],
                        "near_duplicates": semantic["near_duplicates"]["main_posts"],
                        "community_comparison": semantic["community_comparison"],
                        "layers": semantic.get("layers", {}),
                        "cross_analysis": semantic.get("cross_analysis", {}),
                        "embedding_manifest": semantic.get("embedding_manifest", {}),
                        "decision_support": semantic["decision_support"],
                        "action_recommendations": semantic["decision_support"]["action_recommendations"],
                    },
                    "provenance": semantic["provenance"],
                }
            ],
            "evidence_matrix": _evidence_matrix(
                posts,
                comments,
                semantic,
                primary_claim=primary_claim,
                supplementary_claim=supplementary_claim,
            ),
            "graph": _graph_projection(
                posts,
                snapshot.relationships,
                semantic=semantic,
                primary_claim_ref="claim_cctv_primary" if primary_claim else None,
            ),
            "actions": actions,
            "feedback": feedback,
            "semantic_corrections": semantic_corrections,
            "closeout_review": closeout_review,
            "closure_checklist": closure_checklist,
            "prototype_constraints": dict(PROTOTYPE_CONSTRAINTS),
            "reports": [
                {
                    "version": 1,
                    "status": "prototype_preview",
                    "format": "html_pdf_fallback",
                    "content_hash": report_hash,
                    "html_url": f"/api/v2/cases/{DEFAULT_CASE_ID}/reports/1.html",
                    "pdf_url": f"/api/v2/cases/{DEFAULT_CASE_ID}/reports/1.pdf",
                    "contains": ["case", "snapshot", "run", "model_versions", "content_hashes", "prototype_constraints"],
                    "message": "Prototype HTML report is available; production PDF rendering is pending.",
                }
            ],
            "active_blockers": active_blockers,
            "blocker_acknowledgements": acknowledgements,
            "audit_events": audit_events,
            "workflow_summary": {
                "closed_loop": "事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈",
                "display_loop": "事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈",
                "core_claim_source": "official_media",
                "semantic_score_policy": "evidence_overlay_only",
                "stance_block_code": "blocked_missing_primary_claim",
                "default_analysis_stage_compatibility": "semantic_enrichment is explicit and does not change the four-stage default",
            },
        }

    def _semantic_artifact(self, snapshot: Any, options: dict[str, Any]) -> dict[str, Any]:
        runtime = self.semantic_runtime
        try:
            if runtime is None:
                runtime = HuggingFaceSemanticRuntime()
                self.semantic_runtime = runtime
            return analyze_semantic_enrichment_snapshot(snapshot, options, runtime=runtime)
        except SemanticModelUnavailable as exc:
            return blocked_semantic_artifact(snapshot, exc)

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
        await self._assert_case_mutable(case_id)
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
        await self._assert_case_mutable(case_id)
        _assert_action(action_id)
        note = _require_nonblank_text(note, "Waiver note")
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
        await self._assert_case_mutable(case_id)
        reason = _require_nonblank_text(reason, "Blocker acknowledgement reason")
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
        await self._assert_case_mutable(case_id)
        content = _require_nonblank_text(content, "Feedback content")
        feedback = {
            "feedback_id": f"feedback_{len(self.demo_state['feedback']) + 1}",
            "actor_id": actor_id,
            "content": content,
            "created_at": _now(),
        }
        self.demo_state["feedback"].append(feedback)
        self._append_audit("submit_case_feedback", actor_id=actor_id, target_id=feedback["feedback_id"], payload={})
        return await self.get_case(case_id)

    async def record_semantic_correction(
        self,
        case_id: str,
        artifact_id: str,
        *,
        actor_id: str,
        module: str,
        target_ref: str,
        original_value: str = "",
        corrected_value: str,
        reason: str,
    ) -> dict[str, Any]:
        await self._assert_case_mutable(case_id)
        _assert_semantic_artifact(artifact_id)
        correction = {
            "correction_id": f"semantic_correction_{len(self.demo_state['semantic_corrections']) + 1}",
            "artifact_id": artifact_id,
            "module": _require_nonblank_text(module, "Semantic correction module"),
            "target_ref": _require_nonblank_text(target_ref, "Semantic correction target_ref"),
            "original_value": str(original_value or "").strip(),
            "corrected_value": _require_nonblank_text(corrected_value, "Semantic correction corrected_value"),
            "reason": _require_nonblank_text(reason, "Semantic correction reason"),
            "actor_id": actor_id,
            "status": "advisory_overlay",
            "created_at": _now(),
        }
        self.demo_state["semantic_corrections"].append(correction)
        self._append_audit(
            "record_semantic_correction",
            actor_id=actor_id,
            target_id=correction["correction_id"],
            payload={
                "artifact_id": artifact_id,
                "module": correction["module"],
                "target_ref": correction["target_ref"],
                "status": correction["status"],
            },
        )
        return await self.get_case(case_id)

    async def submit_closeout_review(self, case_id: str, *, actor_id: str, summary: str) -> dict[str, Any]:
        await self._assert_case_mutable(case_id)
        summary = _require_nonblank_text(summary, "Closeout summary")
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
        if self.artifact_store is not None and self.artifact_store.exists(case_id):
            report_path = self.artifact_store.report_path(case_id)
            try:
                return report_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise KeyError(f"Frozen Case report is unreadable: {report_path}") from exc

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
        evidence_layers = "".join(
            "<li>"
            f"<strong>{_report_text(layer['label'])}</strong> "
            f"({_report_text(layer['status'])}) - {_report_text(layer['summary'])}; "
            f"{_report_text(_format_report_metrics(layer.get('metrics') or {}))}"
            "</li>"
            for layer in case["graph"].get("evidence_layers", [])
        ) or "<li>None</li>"
        closure_checklist = "".join(
            "<li>"
            f"<strong>{_report_text(item['key'])}</strong> "
            f"({_report_text(item['status'])}) - {_report_text(item['label'])}; "
            f"{_report_text(_format_report_metrics(item.get('evidence') or {}))}"
            "</li>"
            for item in case.get("closure_checklist", [])
        ) or "<li>None</li>"
        acceptance_summary = _report_acceptance_summary(case)
        acceptance_summary_html = (
            "<section><h2>Acceptance summary</h2><dl>"
            f"<dt>Closeout</dt><dd>{_report_text(acceptance_summary['closeout'])}</dd>"
            f"<dt>Archive coverage</dt><dd>{_report_text(acceptance_summary['archive_coverage'])}</dd>"
            f"<dt>CPR coverage</dt><dd>{_report_text(acceptance_summary['cpr_coverage'])}</dd>"
            f"<dt>Semantic policy</dt><dd>{_report_text(acceptance_summary['semantic_policy'])}</dd>"
            f"<dt>Second platform honesty</dt><dd>{_report_text(acceptance_summary['second_platform_honesty'])}</dd>"
            "</dl></section>"
        )
        prototype_limitations_html = _report_prototype_limitations(case)
        semantic_decision_support_html = _report_semantic_decision_support(semantic)
        semantic_evidence_appendix_html = _report_semantic_evidence_appendix(semantic)
        semantic_traceability_html = _report_semantic_traceability(semantic, case["actions"])
        semantic_corrections_html = _report_semantic_corrections(case["semantic_corrections"])
        audit_trail_html = _report_audit_trail(case.get("audit_events", []))
        pending_note = (
            "<p><strong>Production PDF rendering is pending.</strong> This HTML is the MVP PDF fallback.</p>"
            if pdf_fallback
            else ""
        )
        if primary_claim is None:
            claim_provenance = (
                "<section><h2>Primary claim verification</h2><dl>"
                "<dt>Claim verification</dt><dd>Primary claim unavailable</dd>"
                "<dt>Blocking code</dt><dd>blocked_missing_primary_claim</dd>"
                "<dt>Source verification</dt><dd>unavailable</dd>"
                "<dt>Source content capture</dt><dd>unavailable</dd>"
                "<dt>Source archive ID</dt><dd>unavailable</dd>"
                "<dt>Source content hash</dt><dd><code>unavailable</code></dd>"
                "<dt>Source Markdown hash</dt><dd><code>unavailable</code></dd>"
                "</dl></section>"
            )
            primary_claim_html = (
                "<section><h2>Primary claim</h2>"
                "<p>Primary claim unavailable.</p>"
                "<p>blocked_missing_primary_claim</p>"
                "</section>"
            )
        else:
            claim_provenance = (
                "<section><h2>Primary claim verification</h2><dl>"
                f"<dt>Claim verification</dt><dd>{_report_text(primary_claim['status'])}</dd>"
                f"<dt>Source verification</dt><dd>{_report_text(primary_claim['source'].get('status') or 'unverified')}</dd>"
                f"<dt>Source content capture</dt><dd>{_report_text(primary_claim.get('source_content_capture') or 'unavailable')}</dd>"
                f"<dt>Source archive ID</dt><dd>{_report_text(primary_claim.get('source_archive_id') or 'unavailable')}</dd>"
                f"<dt>Source content hash</dt><dd><code>{_report_text(primary_claim.get('source_content_hash') or 'unavailable')}</code></dd>"
                f"<dt>Source Markdown hash</dt><dd><code>{_report_text(primary_claim.get('source_markdown_hash') or 'unavailable')}</code></dd>"
                "</dl></section>"
            )
            primary_claim_html = (
                "<section><h2>Primary claim</h2>"
                f"<p>{_report_text(primary_claim['excerpt'])}</p>"
                "<dl>"
                f"<dt>Source</dt><dd>{_report_text(primary_claim['source']['name'])}</dd>"
                f"<dt>Source tier</dt><dd>{_report_text(primary_claim['source']['tier'])}</dd>"
                "</dl></section>"
            )
        semantic_runtime_html = _report_semantic_runtime(semantic)
        semantic_path_overlay_html = _report_semantic_path_overlays(case.get("graph", {}).get("propagation_paths", []))
        return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Case report {version}</title>
<style>body{{font-family:Arial,sans-serif;line-height:1.5;margin:2rem;max-width:900px}}section{{border-top:1px solid #bbb;margin-top:1.25rem;padding-top:.75rem}}dt{{font-weight:bold}}dd{{margin:0 0 .6rem}}code{{word-break:break-all}}@media print{{body{{margin:1cm}}}}</style>
</head><body><h1>CogGuard Case Report</h1>{pending_note}{claim_provenance}
<section><dl><dt>Case ID</dt><dd>{_report_text(case['case_id'])}</dd><dt>Event ID</dt><dd>{_report_text(case['event_id'])}</dd><dt>Title</dt><dd>{_report_text(case['title'])}</dd><dt>State</dt><dd>{_report_text(case['state'])}</dd><dt>Snapshot ID</dt><dd><code>{_report_text(case['evidence']['snapshot_id'])}</code></dd><dt>Run ID</dt><dd><code>{_report_text(case['analysis_runs'][0]['run_id'])}</code></dd></dl></section>
{primary_claim_html}
<section><h2>Semantic evidence overlay</h2><dl><dt>artifact_sha256</dt><dd><code>{_report_text(semantic['artifact_sha256'])}</code></dd><dt>Model status</dt><dd>{_report_text(semantic['model_status'])}</dd><dt>Score policy</dt><dd>evidence_overlay_only</dd></dl></section>
{semantic_runtime_html}
{semantic_decision_support_html}
{semantic_evidence_appendix_html}
{semantic_traceability_html}
{semantic_path_overlay_html}
{semantic_corrections_html}
{audit_trail_html}
<section><h2>CPR evidence layers</h2><ul>{evidence_layers}</ul></section>
{acceptance_summary_html}
{prototype_limitations_html}
<section><h2>Closure checklist</h2><ul>{closure_checklist}</ul></section>
<section><h2>Active blockers</h2><ul>{blockers}</ul></section><section><h2>Policy acknowledgements</h2><ul>{acknowledgements}</ul></section><section><h2>Actions</h2><ul>{actions}</ul></section><section><h2>Feedback</h2><p>Count: {len(case['feedback'])}</p></section><section><h2>Closeout review</h2><p>{_report_text(closeout.get('summary') or 'Not submitted')}</p></section>
</body></html>"""

    def _assert_case(self, case_id: str) -> None:
        if case_id != DEFAULT_CASE_ID:
            raise KeyError(f"Case not found: {case_id}")

    async def _assert_case_mutable(self, case_id: str) -> None:
        self._assert_case(case_id)
        if self._load_frozen_artifact(case_id) is not None:
            raise CaseOperationConflict("Frozen Case artifacts are immutable and cannot be modified.")
        if (await self.get_case(case_id))["state"] == "closed":
            raise CaseOperationConflict("Closed cases cannot be modified.")

    def _load_frozen_artifact(self, case_id: str) -> dict[str, Any] | None:
        if self.artifact_store is None:
            return None
        return self.artifact_store.load(case_id)

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


def _frozen_case_projection(artifact: dict[str, Any]) -> dict[str, Any]:
    """Expose an immutable precomputed Case without recalculating or approving it."""

    case = artifact["case"]
    snapshot = artifact["snapshot"]
    semantic = _compact_frozen_semantic(artifact.get("semantic") or {})
    runtime = semantic.get("runtime") or {}
    review = artifact.get("review") or {}
    claims = [_compact_frozen_claim(claim) for claim in artifact.get("authority_claims") or [] if isinstance(claim, dict)]
    primary_claim = next((claim for claim in claims if claim.get("role") == "primary"), None)
    supplementary_claims = [claim for claim in claims if claim.get("role") != "primary"]
    platforms = _frozen_platforms(snapshot)
    samples = _frozen_evidence_samples(snapshot)
    coordination = _compact_frozen_coordination(artifact.get("coordination") or {})
    propagation = _compact_frozen_propagation(artifact.get("propagation") or {})
    graph = _frozen_graph_projection(coordination=coordination, propagation=propagation, semantic=semantic, review=review)
    artifact_evidence = {
        "schema_version": artifact.get("schema_version"),
        "artifact_sha256": artifact.get("artifact_sha256"),
        "content_hashes": dict(artifact.get("content_hashes") or {}),
        "frozen_at": artifact.get("frozen_at"),
        "report_manifest": {
            key: value
            for key, value in (artifact.get("report_manifest") or {}).items()
            if key in {"version", "status", "format", "html_file"}
        },
    }
    return {
        "case_id": case["case_id"],
        "event_id": case["event_id"],
        "title": case.get("title") or case["case_id"],
        "description": "冻结的三平台预计算案例；人工 Review 与结案仍需后续操作。",
        "state": case.get("state", "awaiting_review"),
        "state_options": list(CASE_STATES),
        "created_at": artifact.get("frozen_at"),
        "updated_at": artifact.get("frozen_at"),
        "source_mode": "frozen_artifact",
        "expected_platforms": ["weibo", "xhs", "douyin"],
        "platforms": platforms,
        "evidence": {
            "snapshot_id": snapshot.get("snapshot_id"),
            "data_fingerprint": snapshot.get("data_fingerprint"),
            "posts": snapshot.get("post_count", len(snapshot.get("posts") or [])),
            "comments": snapshot.get("comment_count", len(snapshot.get("comments") or [])),
            "source_mode": "frozen_artifact",
            "provenance": snapshot.get("provenance") or [],
            "platform_distribution": _frozen_platform_distribution(snapshot),
            "recent_posts": samples["posts"],
            "samples": samples,
        },
        "lifecycle": _lifecycle(state=case.get("state", "awaiting_review")),
        "primary_claim": primary_claim,
        "supplementary_claims": supplementary_claims,
        "canonical_verdict": review.get("canonical_verdict"),
        "analysis_runs": [
            {
                "run_id": runtime.get("run_id"),
                "snapshot_id": snapshot.get("snapshot_id"),
                "status": review.get("status", "awaiting_human_review"),
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
                "artifact_id": semantic.get("artifact_id", "semantic_precomputed"),
                "artifact_type": "semantic_enrichment",
                "status": semantic.get("status"),
                "runtime_status": runtime.get("runtime_status"),
                "runtime_backend": runtime.get("runtime_backend"),
                "model_status": semantic.get("validation_status") or semantic.get("model_status"),
                "model_version": semantic.get("model_version"),
                "model_versions": runtime.get("model_versions") or {},
                "validation_status": semantic.get("validation_status"),
                "artifact_sha256": artifact["content_hashes"].get("semantic"),
                "summary": semantic["summary"],
                "provenance": {
                    "score_policy": semantic.get("score_policy", "evidence_overlay_only"),
                    "frozen_artifact_sha256": artifact.get("artifact_sha256"),
                },
            }
        ],
        "evidence_matrix": {
            "claims": claims,
            "samples": samples,
            "semantic": semantic,
        },
        "graph": graph,
        "actions": [],
        "feedback": [],
        "semantic_corrections": [],
        "closeout_review": None,
        "closure_checklist": [
            {"key": "canonical_verdict", "status": "pending"},
            {"key": "required_actions", "status": "pending"},
            {"key": "feedback", "status": "pending"},
            {"key": "closeout_review", "status": "pending"},
        ],
        "prototype_constraints": {
            **PROTOTYPE_CONSTRAINTS,
            "platform_evidence_scope": "three_platform_frozen_precompute",
            "frozen_artifact": "immutable_pending_human_review",
        },
        "reports": [
            {
                "version": artifact.get("report_manifest", {}).get("version", 1),
                "status": artifact.get("report_manifest", {}).get("status", "frozen_pending_human_review"),
                "format": artifact.get("report_manifest", {}).get("format", "html"),
                "content_hash": artifact.get("content_hashes", {}).get("report_manifest"),
                "html_url": f"/api/v2/cases/{case['case_id']}/reports/1.html",
                "message": "Frozen report is pending human review and cannot close this Case.",
            }
        ],
        "active_blockers": [
            {
                "blocker_id": "blocker_human_review_required",
                "code": "awaiting_human_review",
                "scope": "review",
                "severity": "blocking",
                "message": "A frozen precompute cannot approve canonical verdicts or close a Case.",
            }
        ],
        "blocker_acknowledgements": [],
        "audit_events": [],
        "workflow_summary": {
            "closed_loop": "事件 -> 证据 -> Coordination -> Propagation -> semantic_enrichment -> Review -> 处置 -> 反馈",
            "core_claim_source": "official_media",
            "semantic_score_policy": "evidence_overlay_only",
            "frozen_artifact_status": "awaiting_human_review",
        },
        "artifact_evidence": artifact_evidence,
    }


def _compact_frozen_claim(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in claim.items()
        if key
        in {
            "claim_id",
            "role",
            "status",
            "excerpt",
            "span",
            "url",
            "account",
            "published_at",
            "source_tier",
            "source",
            "source_archive_id",
            "source_content_hash",
            "source_markdown_hash",
            "source_content_capture",
            "excerpt_hash",
        }
    }


def _compact_frozen_semantic(semantic: dict[str, Any]) -> dict[str, Any]:
    runtime = dict(semantic.get("runtime") or {})
    summary = {
        "sentiment": _compact_frozen_mapping(semantic.get("sentiment") or {}, keys={"summary"}),
        "top_keywords": _compact_frozen_list((semantic.get("keywords") or {}).get("main_posts"), limit=12),
        "topics": _compact_frozen_mapping((semantic.get("topics") or {}).get("main_posts") or {}, keys={"items", "method", "topic_count"}),
        "entities": _compact_frozen_list((semantic.get("entities") or {}).get("main_posts"), limit=12),
        "stance": _compact_frozen_mapping(
            semantic.get("stance") or {},
            keys={"status", "distribution", "examples", "method", "model_version", "primary_claim_hash"},
            list_limits={"examples": 8},
        ),
        "near_duplicates": _compact_frozen_list((semantic.get("near_duplicates") or {}).get("main_posts"), limit=8),
        "community_comparison": _compact_frozen_mapping(
            semantic.get("community_comparison") or {}, keys={"group_by", "items"}, list_limits={"items": 12}
        ),
        "layers": _compact_frozen_layers(semantic.get("layers") or {}),
        "cross_analysis": _compact_frozen_cross_analysis(semantic.get("cross_analysis") or {}),
        "embedding_manifest": _compact_frozen_mapping(
            semantic.get("embedding_manifest") or {}, keys={"status", "embedding_model", "encoded_texts", "reuse_policy", "cache_dir"}
        ),
        "decision_support": _compact_frozen_decision_support(semantic.get("decision_support") or {}),
    }
    summary["action_recommendations"] = list(summary["decision_support"].get("action_recommendations") or [])
    return {
        "artifact_id": semantic.get("artifact_id", "semantic_precomputed"),
        "status": semantic.get("status"),
        "runtime_status": semantic.get("runtime_status") or runtime.get("runtime_status"),
        "runtime_backend": semantic.get("runtime_backend") or runtime.get("runtime_backend"),
        "model_status": semantic.get("model_status") or semantic.get("validation_status"),
        "model_version": semantic.get("model_version"),
        "model_versions": semantic.get("model_versions") or runtime.get("model_versions") or {},
        "validation_status": semantic.get("validation_status"),
        "embedding_manifest": summary["embedding_manifest"],
        "semantic_blocker": _compact_frozen_mapping(semantic.get("semantic_blocker") or {}, keys={"code", "message", "manual_resolution", "missing_models"}),
        "summary": summary,
        "provenance": _compact_frozen_mapping(
            semantic.get("provenance") or {}, keys={"cache_dir", "device", "does_not_modify", "embedding_reuse", "score_policy"}
        ),
        "score_policy": semantic.get("score_policy", "evidence_overlay_only"),
        "runtime": runtime,
    }


def _compact_frozen_layers(layers: dict[str, Any]) -> dict[str, Any]:
    return {
        name: _compact_frozen_mapping(
            value if isinstance(value, dict) else {},
            keys={"sentiment", "stance", "keywords", "topics", "entities", "near_duplicates"},
            list_limits={"keywords": 8, "entities": 8, "near_duplicates": 5},
        )
        for name, value in layers.items()
        if name in {"main_posts", "comments"}
    }


def _compact_frozen_cross_analysis(cross_analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _compact_frozen_list(value, limit=12)
        for key, value in cross_analysis.items()
        if key in {"time_slices", "platform_slices", "community_slices", "propagation_path_overlays"}
    }


def _compact_frozen_decision_support(support: dict[str, Any]) -> dict[str, Any]:
    return _compact_frozen_mapping(
        support,
        keys={"coverage", "confidence", "module_coverage", "operator_prompt", "review_hints", "action_recommendations", "platform_slices", "time_slices"},
        list_limits={"review_hints": 8, "action_recommendations": 8, "platform_slices": 8, "time_slices": 12},
    )


def _compact_frozen_mapping(
    value: Any,
    *,
    keys: set[str],
    list_limits: dict[str, int] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    limits = list_limits or {}
    return {
        key: _compact_frozen_list(item, limit=limits[key]) if isinstance(item, list) and key in limits else item
        for key, item in value.items()
        if key in keys
    }


def _compact_frozen_list(value: Any, *, limit: int) -> list[Any]:
    return list(value[:limit]) if isinstance(value, list) else []


def _frozen_platforms(snapshot: dict[str, Any]) -> list[str]:
    return _platforms(list(snapshot.get("posts") or []), list(snapshot.get("comments") or []))


def _frozen_evidence_samples(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    posts = list(snapshot.get("posts") or [])
    comments = list(snapshot.get("comments") or [])
    return {
        "posts": _recent_posts(posts),
        "comments": [
            {
                "comment_id": comment.get("comment_id"),
                "post_id": comment.get("post_id"),
                "platform": comment.get("platform"),
                "author_name": comment.get("author_name") or comment.get("author_id"),
                "timestamp": str(comment.get("timestamp") or ""),
                "content": str(comment.get("content") or "")[:180],
            }
            for comment in comments[:6]
        ],
    }


def _frozen_platform_distribution(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return _platform_distribution(list(snapshot.get("posts") or []), list(snapshot.get("comments") or []))


def _compact_frozen_coordination(coordination: dict[str, Any]) -> dict[str, Any]:
    compact = _compact_frozen_mapping(
        coordination,
        keys={"status", "implementation", "community_algorithm", "metrics", "graph_metrics", "communities", "detection_summary", "discovery_sha256", "detection_sha256"},
        list_limits={"communities": 12},
    )
    detection = compact.get("detection_summary")
    if isinstance(detection, dict):
        compact["detection_summary"] = _compact_frozen_mapping(
            detection,
            keys={"task", "setting", "method", "relations", "metrics", "unlabeled_inference_summary"},
        )
    return compact


def _compact_frozen_propagation(propagation: dict[str, Any]) -> dict[str, Any]:
    return _compact_frozen_mapping(
        propagation,
        keys={"status", "implementation", "relationship_count", "source", "paths"},
        list_limits={"paths": 12},
    )


def _frozen_graph_projection(
    *,
    coordination: dict[str, Any],
    propagation: dict[str, Any],
    semantic: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    paths = []
    nodes: dict[str, dict[str, str]] = {}
    edges = []
    overlays_by_ref = _frozen_propagation_overlay_index(semantic)
    for index, path in enumerate(propagation.get("paths") or [], start=1):
        source_id = str(path.get("source_id") or "")
        target_id = str(path.get("target_id") or "")
        path_id = str(path.get("path_id") or f"frozen_path_{index}")
        if source_id:
            nodes.setdefault(source_id, {"id": source_id, "label": source_id, "type": "account"})
        if target_id:
            nodes.setdefault(target_id, {"id": target_id, "label": target_id, "type": "account"})
        edge = {
            "id": str(path.get("evidence_ref") or path_id),
            "source": source_id,
            "target": target_id,
            "relation_type": str(path.get("relation_type") or "related"),
            "platform": str(path.get("platform") or ""),
            "evidence_ref": str(path.get("evidence_ref") or path_id),
        }
        if source_id and target_id:
            edges.append(edge)
        graph_path = {
            "path_id": path_id,
            "label": f"{source_id or 'unknown'} -> {target_id or 'unknown'}",
            "nodes": [node for node in (nodes.get(source_id), nodes.get(target_id)) if node],
            "edges": [edge] if source_id and target_id else [],
            "evidence_type": "observed",
            "explanation": f"Precomputed {edge['relation_type']} relationship.",
        }
        semantic_overlay = _frozen_path_semantic_overlay(path, overlays_by_ref)
        if semantic_overlay:
            graph_path["semantic_overlay"] = semantic_overlay
        paths.append(graph_path)
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "propagation_paths": paths,
        "path_analysis": {"edge_count": len(edges), "key_paths": paths},
        "evidence_layers": [
            {
                "key": "coordination",
                "label": "Coordination",
                "status": coordination.get("status", "precomputed"),
                "summary": "Precomputed coordination summary from the frozen artifact.",
                "metrics": coordination.get("metrics") or coordination.get("graph_metrics") or {},
            },
            {
                "key": "propagation",
                "label": "Propagation",
                "status": propagation.get("status", "precomputed"),
                "summary": "Observed propagation summary from the frozen artifact.",
                "metrics": {"relationships": propagation.get("relationship_count", 0), "displayed_paths": len(paths)},
            },
            {
                "key": "review",
                "label": "Review",
                "status": review.get("status", "awaiting_human_review"),
                "summary": "Frozen artifacts remain pending human review.",
                "metrics": {"canonical_verdict_status": (review.get("canonical_verdict") or {}).get("status")},
            },
        ],
        "coordination": coordination,
        "propagation": propagation,
        "provenance": "frozen_precompute",
    }


def _frozen_propagation_overlay_index(semantic: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cross_analysis = ((semantic.get("summary") or {}).get("cross_analysis") or {})
    overlays = cross_analysis.get("propagation_path_overlays") or []
    indexed: dict[str, dict[str, Any]] = {}
    for overlay in overlays:
        if not isinstance(overlay, dict):
            continue
        for key in (overlay.get("path_id"), overlay.get("evidence_ref")):
            if key:
                indexed[str(key)] = overlay
        for evidence_ref in overlay.get("evidence_refs") or []:
            if evidence_ref:
                indexed.setdefault(str(evidence_ref), overlay)
    return indexed


def _frozen_path_semantic_overlay(path: dict[str, Any], overlays_by_ref: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    overlay = path.get("semantic_overlay")
    if not isinstance(overlay, dict):
        for key in (
            path.get("path_id"),
            path.get("evidence_ref"),
            path.get("source_ref"),
            path.get("target_ref"),
        ):
            if key and str(key) in overlays_by_ref:
                overlay = overlays_by_ref[str(key)]
                break
    if not isinstance(overlay, dict):
        return None
    return _compact_frozen_mapping(
        overlay,
        keys={
            "status",
            "sentiment",
            "stance",
            "keywords",
            "entities",
            "topics",
            "platforms",
            "time_range",
            "claim_refs",
            "evidence_refs",
            "evidence_examples",
            "score_policy",
            "texts",
            "message",
            "code",
        },
        list_limits={
            "keywords": 8,
            "entities": 8,
            "topics": 6,
            "platforms": 6,
            "claim_refs": 6,
            "evidence_refs": 8,
            "evidence_examples": 3,
        },
    )


class CaseOperationConflict(ValueError):
    """Raised when a prototype Case operation violates lifecycle gates."""


def _archived_demo_claims() -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        entries = verify_research_archive(_research_archive_root())
    except Exception:
        return _copy_claim(PRIMARY_CLAIM), _copy_claim(SUPPLEMENTARY_CLAIM)

    by_purpose = {entry.purpose: entry for entry in entries}
    return (
        _claim_bound_to_archive(PRIMARY_CLAIM, by_purpose.get("primary_claim")),
        _claim_bound_to_archive(SUPPLEMENTARY_CLAIM, by_purpose.get("supplementary_claim")),
    )


def _research_archive_root() -> Path:
    return Path(__file__).resolve().parents[4] / "doc" / "research" / "case-workbench"


def _claim_bound_to_archive(template: dict[str, Any], entry: ResearchArchiveEntry | None) -> dict[str, Any]:
    claim = _copy_claim(template)
    if entry is None:
        return claim
    source = dict(claim["source"])
    source.update(
        {
            "url": str(entry.source_url),
            "status": "verified_archive",
            "content_capture": "markitdown_archive",
            "archive_id": entry.archive_id,
            "source_sha256": entry.source_sha256,
            "markdown_sha256": entry.markdown_sha256,
        }
    )
    claim.update(
        {
            "excerpt": entry.verified_excerpt,
            "span": {"start": entry.verified_span_start, "end": entry.verified_span_end},
            "url": str(entry.source_url),
            "source_archive_id": entry.archive_id,
            "source_content_capture": "markitdown_archive",
            "source_content_hash": entry.source_sha256,
            "source_markdown_hash": entry.markdown_sha256,
            "source": source,
        }
    )
    return claim


def _copy_claim(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        **claim,
        "span": dict(claim["span"]),
        "source": dict(claim["source"]),
    }


def _new_demo_state() -> dict[str, Any]:
    return {
        "actions": {},
        "action_history": {template["action_id"]: [] for template in ACTION_TEMPLATES},
        "feedback": [],
        "semantic_corrections": [],
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


def _assert_semantic_artifact(artifact_id: str) -> None:
    if artifact_id != "semantic_case_workbench_demo":
        raise KeyError(f"Semantic artifact not found: {artifact_id}")


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


def _primary_claim_blockers(primary_claim: dict[str, Any] | None) -> list[dict[str, Any]]:
    if primary_claim is not None:
        return []
    return [
        {
            "blocker_id": "blocker_missing_primary_claim",
            "code": "blocked_missing_primary_claim",
            "scope": "claim",
            "operation": "stance_review_closeout",
            "severity": "blocking",
            "message": (
                "Stance, Review finalization, and Closeout require one approved Primary Claim; "
                "non-stance semantic artifacts remain available."
            ),
            "missing_platforms": [],
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
        "source_content_capture": claim.get("source_content_capture") or "unavailable",
        "excerpt_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }


def _require_nonblank_text(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise CaseOperationConflict(f"{field_name} must be non-blank.")
    return normalized


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


def _evidence_matrix(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    semantic: dict[str, Any],
    *,
    primary_claim: dict[str, Any] | None = PRIMARY_CLAIM,
    supplementary_claim: dict[str, Any] = SUPPLEMENTARY_CLAIM,
) -> dict[str, Any]:
    claims = [_claim_with_hash(supplementary_claim)]
    if primary_claim is not None:
        claims.insert(0, _claim_with_hash(primary_claim))
    return {
        "claims": claims,
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
            "runtime_status": semantic.get("runtime_status"),
            "runtime_backend": semantic.get("runtime_backend"),
            "validation_status": semantic.get("validation_status"),
            "semantic_blocker": semantic.get("semantic_blocker"),
            "embedding_manifest": semantic.get("embedding_manifest"),
            "layers": semantic.get("layers", {}),
            "cross_analysis": semantic.get("cross_analysis", {}),
            "keywords": semantic["keywords"],
            "topics": semantic["topics"],
            "entities": semantic["entities"],
            "sentiment": semantic["sentiment"],
            "stance": semantic["stance"],
            "near_duplicates": semantic["near_duplicates"],
            "community_comparison": semantic["community_comparison"],
            "decision_support": semantic["decision_support"],
            "action_recommendations": semantic["decision_support"]["action_recommendations"],
        },
    }


def _graph_projection(
    posts: list[dict[str, Any]],
    relationships: list[Any] | None = None,
    *,
    semantic: dict[str, Any] | None = None,
    primary_claim_ref: str | None = None,
) -> dict[str, Any]:
    nodes = []
    seen = set()
    content_accounts: dict[str, dict[str, str]] = {}
    for post in posts:
        author = str(post.get("author_id") or "").strip()
        platform = str(post.get("platform") or "unknown")
        post_id = str(post.get("post_id") or "").strip()
        if author and author not in seen:
            seen.add(author)
            nodes.append({"id": author, "label": post.get("author_name") or author, "type": "account"})
        if author and post_id:
            content_accounts[f"{platform}:post:{post_id}"] = {
                "id": author,
                "label": str(post.get("author_name") or author),
            }
    edges = _graph_relationship_edges(relationships or [], content_accounts)
    propagation_paths = _graph_propagation_paths(edges)
    if semantic and semantic.get("runtime_status") == "ok":
        semantic_rows = (
            semantic.get("_runtime_rows")
            or ((semantic.get("layers") or {}).get("all_texts") or [])
        )
        for path in propagation_paths:
            path["semantic_overlay"] = propagation_path_overlay(
                path,
                semantic_rows,
                primary_claim_ref=primary_claim_ref,
            )
        semantic.setdefault("cross_analysis", {})["propagation_path_overlays"] = [
            {
                "path_id": path["path_id"],
                **path.get("semantic_overlay", {}),
            }
            for path in propagation_paths
        ]
    else:
        semantic_blocker = (semantic or {}).get("semantic_blocker") or {}
        for path in propagation_paths:
            path["semantic_overlay"] = {
                "status": "blocked",
                "code": semantic_blocker.get("code", "semantic_unavailable"),
                "message": semantic_blocker.get("message", "Semantic overlay unavailable."),
                "score_policy": "evidence_overlay_only",
                "evidence_refs": sorted(
                    {
                        str(edge.get("evidence_ref") or "")
                        for edge in path.get("edges") or []
                        if str(edge.get("evidence_ref") or "")
                    }
                ),
            }
    return {
        "nodes": nodes,
        "edges": edges,
        "propagation_paths": propagation_paths,
        "path_analysis": {
            "edge_count": len(edges),
            "key_paths": propagation_paths,
        },
        "evidence_layers": _graph_evidence_layers(posts=posts, account_count=len(nodes), edge_count=len(edges)),
        "provenance": "event_snapshot_relationships",
    }


def _graph_relationship_edges(
    relationships: list[Any],
    content_accounts: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for relation in relationships:
        source_ref = str(getattr(relation, "source_id", "") or "")
        target_ref = str(getattr(relation, "target_id", "") or "")
        source = content_accounts.get(source_ref)
        target = content_accounts.get(target_ref)
        if not source or not target:
            continue
        relation_type = str(getattr(relation, "relation_type", "") or "related")
        key = (source["id"], target["id"], relation_type, target_ref)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            {
                "id": f"{relation_type}:{source_ref}->{target_ref}",
                "source": source["id"],
                "target": target["id"],
                "source_label": source["label"],
                "target_label": target["label"],
                "relation_type": relation_type,
                "platform": str(getattr(relation, "platform", "") or ""),
                "evidence_ref": str(getattr(relation, "evidence_ref", "") or target_ref),
                "source_ref": source_ref,
                "target_ref": target_ref,
            }
        )
    return edges


def _graph_propagation_paths(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    for index, edge in enumerate(edges[:8], start=1):
        nodes = [
            {"id": edge["source"], "label": edge.get("source_label") or edge["source"]},
            {"id": edge["target"], "label": edge.get("target_label") or edge["target"]},
        ]
        relation_type = edge.get("relation_type") or "related"
        paths.append(
            {
                "path_id": f"snapshot_path_{index}",
                "label": f"{nodes[0]['label']} -> {nodes[1]['label']}",
                "nodes": nodes,
                "edges": [edge],
                "evidence_type": "explicit",
                "explanation": f"Observed {relation_type} relationship from EventSnapshot.relationships.",
            }
        )
    return paths


def _graph_evidence_layers(*, posts: list[dict[str, Any]], account_count: int, edge_count: int = 0) -> list[dict[str, Any]]:
    post_count = len(posts)
    status = "available" if post_count else "partial"
    return [
        {
            "key": "coordination",
            "label": "Coordination",
            "status": status,
            "summary": "Accounts are grouped as prototype coordination evidence from shared event participation.",
            "metrics": {
                "accounts": account_count,
                "candidate_communities": 1 if account_count else 0,
            },
        },
        {
            "key": "propagation",
            "label": "Propagation",
            "status": status,
            "summary": "Posts form the current observed propagation sample; explicit repost edges remain source-dependent.",
            "metrics": {
                "posts": post_count,
                "explicit_edges": edge_count,
            },
        },
        {
            "key": "review",
            "label": "Review",
            "status": "available",
            "summary": "Risk Review is represented by the current canonical demo verdict and cited evidence overlays.",
            "metrics": {
                "canonical_verdict_status": "approved",
                "required_actions": len(ACTION_TEMPLATES),
            },
        },
    ]


def _closure_checklist(
    *,
    canonical_verdict: dict[str, Any],
    actions: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    closeout_review: dict[str, Any] | None,
    active_blockers: list[dict[str, Any]],
    blocker_acknowledgements: list[dict[str, Any]],
    primary_claim: dict[str, Any] | None,
    supplementary_claims: list[dict[str, Any]],
    semantic: dict[str, Any],
    semantic_score_policy: str,
) -> list[dict[str, Any]]:
    required_actions = [action for action in actions if action.get("required")]
    terminal_actions = [
        action
        for action in required_actions
        if action.get("status") in {"completed", "waived"}
    ]
    claims = ([primary_claim] if primary_claim else []) + supplementary_claims
    archived_claims = [
        claim
        for claim in claims
        if claim.get("source_archive_id")
        and claim.get("source_content_hash")
        and claim.get("source_markdown_hash")
    ]
    semantic_policy_passed = (
        semantic_score_policy == "evidence_overlay_only"
        and semantic.get("model_status") == "candidate_unvalidated"
    )

    return [
        {
            "key": "canonical_verdict",
            "label": "Canonical verdict approved",
            "status": "passed" if canonical_verdict.get("status") == "approved" else "pending",
            "evidence": {
                "verdict_id": canonical_verdict.get("verdict_id"),
                "status": canonical_verdict.get("status"),
                "source": canonical_verdict.get("source"),
            },
        },
        {
            "key": "required_actions",
            "label": "Required actions completed or waived",
            "status": "passed" if len(terminal_actions) == len(required_actions) else "pending",
            "evidence": {
                "required": len(required_actions),
                "terminal": len(terminal_actions),
                "pending_action_ids": [
                    action["action_id"]
                    for action in required_actions
                    if action.get("status") not in {"completed", "waived"}
                ],
            },
        },
        {
            "key": "feedback",
            "label": "Human feedback submitted",
            "status": "passed" if feedback else "pending",
            "evidence": {"feedback_count": len(feedback)},
        },
        {
            "key": "closeout_review",
            "label": "Closeout review submitted",
            "status": "passed" if closeout_review else "pending",
            "evidence": {
                "review_id": closeout_review.get("review_id") if closeout_review else None,
                "submitted_at": closeout_review.get("submitted_at") if closeout_review else None,
            },
        },
        {
            "key": "active_blockers",
            "label": "No active blocking items remain",
            "status": "blocked" if active_blockers else "passed",
            "evidence": {
                "active_count": len(active_blockers),
                "active_codes": [blocker["code"] for blocker in active_blockers],
                "acknowledgement_count": len(blocker_acknowledgements),
            },
        },
        {
            "key": "claim_archive",
            "label": "Primary and supplementary claims are archive-backed",
            "status": "passed" if primary_claim and len(archived_claims) == len(claims) else "blocked",
            "evidence": {
                "primary": primary_claim.get("source_archive_id") if primary_claim else "missing_primary_claim",
                "archived_claims": len(archived_claims),
                "claim_count": len(claims),
                "claim_statuses": [claim.get("status") for claim in claims],
            },
        },
        {
            "key": "semantic_overlay_policy",
            "label": "Semantic artifacts are candidate overlays only",
            "status": "passed" if semantic_policy_passed else "blocked",
            "evidence": {
                "score_policy": semantic_score_policy,
                "model_status": semantic.get("model_status"),
                "artifact_id": "semantic_case_workbench_demo",
            },
        },
    ]


def _report_acceptance_summary(case: dict[str, Any]) -> dict[str, str]:
    claims = [
        *([case["primary_claim"]] if case.get("primary_claim") else []),
        *case.get("supplementary_claims", []),
    ]
    archive_coverage = (
        "cctv_xinhua_markitdown_archive"
        if claims and all(claim.get("source_archive_id") for claim in claims)
        else "incomplete"
    )
    graph_layer_keys = {layer.get("key") for layer in case.get("graph", {}).get("evidence_layers", [])}
    cpr_coverage = (
        "coordination_propagation_review"
        if {"coordination", "propagation", "review"}.issubset(graph_layer_keys)
        else "incomplete"
    )
    second_platform_honesty = (
        "weibo_only_with_platform_gap"
        if case.get("platforms") == ["weibo"] and case.get("blocker_acknowledgements")
        else "check_required"
    )
    return {
        "closeout": "closed_loop_review_submitted" if case.get("closeout_review") else case.get("state", "not_loaded"),
        "archive_coverage": archive_coverage,
        "cpr_coverage": cpr_coverage,
        "semantic_policy": case.get("workflow_summary", {}).get("semantic_score_policy", "unknown"),
        "second_platform_honesty": second_platform_honesty,
    }


def _report_prototype_limitations(case: dict[str, Any]) -> str:
    constraints = case.get("prototype_constraints") or {}
    items = "".join(
        f"<dt>{_report_text(key)}</dt><dd>{_report_text(value)}</dd>"
        for key, value in constraints.items()
    )
    return (
        "<section><h2>Prototype limitations</h2>"
        "<p>These constraints make the demo evidence boundary explicit for review.</p>"
        f"<dl>{items}</dl>"
        "</section>"
    )


def _report_semantic_decision_support(semantic: dict[str, Any]) -> str:
    support = (semantic.get("summary") or {}).get("decision_support") or {}
    coverage = support.get("coverage") or {}
    confidence = support.get("confidence") or {}
    platform_slices = "".join(
        "<li>"
        f"{_report_text(item.get('platform', '-'))}: "
        f"{_report_text(item.get('texts', 0))} texts"
        "</li>"
        for item in support.get("platform_slices", [])
    ) or "<li>None</li>"
    time_slices = "".join(
        "<li>"
        f"{_report_text(item.get('time', '-'))}: "
        f"{_report_text(item.get('texts', 0))} texts"
        "</li>"
        for item in support.get("time_slices", [])
    ) or "<li>None</li>"
    return (
        "<section><h2>Semantic decision support</h2>"
        "<dl>"
        f"<dt>Coverage</dt><dd>{_report_text(coverage.get('coverage_ratio', 'unknown'))} "
        f"({_report_text(coverage.get('covered_texts', 0))}/{_report_text(coverage.get('total_texts', 0))} texts)</dd>"
        f"<dt>Confidence</dt><dd>{_report_text(confidence.get('level', 'unknown'))} / "
        f"{_report_text(confidence.get('status', 'unknown'))}</dd>"
        f"<dt>Operator prompt</dt><dd>{_report_text(support.get('operator_prompt', 'not_available'))}</dd>"
        "</dl>"
        f"<h3>Platform slices</h3><ul>{platform_slices}</ul>"
        f"<h3>Time slices</h3><ul>{time_slices}</ul>"
        "</section>"
    )


def _report_semantic_runtime(semantic: dict[str, Any]) -> str:
    versions = semantic.get("model_versions") or {}
    manifest = semantic.get("embedding_manifest") or {}
    blocker = semantic.get("semantic_blocker") or {}
    version_items = "".join(
        f"<dt>{_report_text(name)}</dt><dd><code>{_report_text(version)}</code></dd>"
        for name, version in versions.items()
    ) or "<dt>models</dt><dd>unavailable</dd>"
    blocker_html = (
        f"<dt>Semantic blocker</dt><dd>{_report_text(blocker.get('code'))}: "
        f"{_report_text(blocker.get('manual_resolution'))}</dd>"
        if blocker
        else ""
    )
    return (
        "<section><h2>Semantic runtime manifest</h2><dl>"
        f"<dt>Runtime status</dt><dd>{_report_text(semantic.get('runtime_status', 'unknown'))}</dd>"
        f"<dt>Runtime backend</dt><dd>{_report_text(semantic.get('runtime_backend', 'unknown'))}</dd>"
        f"<dt>Validation status</dt><dd>{_report_text(semantic.get('validation_status', 'unknown'))}</dd>"
        f"<dt>Cache dir</dt><dd><code>{_report_text((semantic.get('provenance') or {}).get('cache_dir') or manifest.get('cache_dir') or 'unknown')}</code></dd>"
        f"<dt>Encoded texts</dt><dd>{_report_text(manifest.get('encoded_texts', 'unknown'))}</dd>"
        f"{blocker_html}"
        f"{version_items}"
        "</dl></section>"
    )


def _report_semantic_path_overlays(paths: list[dict[str, Any]]) -> str:
    items = _report_term_items(
        (
            f"{path.get('path_id', '-')}: {path.get('label', '-')}; "
            f"status={(path.get('semantic_overlay') or {}).get('status', '-')}; "
            f"sentiment={_format_report_metrics((path.get('semantic_overlay') or {}).get('sentiment') or {})}; "
            f"keywords={', '.join((path.get('semantic_overlay') or {}).get('keywords') or []) or '-'}; "
            f"entities={', '.join((path.get('semantic_overlay') or {}).get('entities') or []) or '-'}; "
            f"refs={', '.join((path.get('semantic_overlay') or {}).get('evidence_refs') or []) or '-'}"
            for path in paths
        ),
        empty="No propagation path semantic overlay available",
    )
    return (
        "<section><h2>Propagation path semantic overlays</h2>"
        "<p>Path overlays are advisory semantic evidence and do not change CPR risk scores.</p>"
        f"<ul>{items}</ul>"
        "</section>"
    )


def _report_semantic_evidence_appendix(semantic: dict[str, Any]) -> str:
    summary = semantic.get("summary") or {}
    sentiment = summary.get("sentiment") or {}
    keywords = summary.get("top_keywords") or []
    topics = summary.get("topics") or {}
    entities = summary.get("entities") or []
    stance = summary.get("stance") or {}
    near_duplicates = summary.get("near_duplicates") or []
    community_comparison = summary.get("community_comparison") or {}
    distribution = sentiment.get("distribution") or {}
    stance_distribution = stance.get("distribution") or {}

    keyword_items = _report_term_items(
        (item.get("term") for item in keywords[:8]),
        empty="No keywords available",
    )
    topic_items = _report_term_items(
        (
            f"{item.get('topic_id', '-')}: {item.get('label', '-')} "
            f"({item.get('size', 0)} texts)"
            for item in (topics.get("items") or [])[:6]
        ),
        empty="No topics available",
    )
    entity_items = _report_term_items(
        (
            f"{item.get('entity', '-')} ({item.get('entity_type', 'entity')}, "
            f"{item.get('count', 0)})"
            for item in entities[:10]
        ),
        empty="No entities available",
    )
    near_duplicate_items = _report_term_items(
        (
            f"{item.get('group_id', '-')} ({item.get('size', 0)} texts)"
            for item in near_duplicates[:5]
        ),
        empty="None",
    )
    community_items = _report_term_items(
        (
            f"{item.get('community_id', '-')} ({item.get('texts', 0)} texts): "
            f"{_format_report_metrics(item.get('sentiment') or {})}"
            for item in (community_comparison.get("items") or [])[:6]
        ),
        empty="No community comparison available",
    )
    stance_status = stance.get("status", "unknown")
    stance_detail = (
        _format_report_metrics(stance_distribution)
        if stance_distribution
        else stance.get("code") or stance.get("message") or "unavailable"
    )
    return (
        "<section><h2>Semantic evidence appendix</h2>"
        "<p>candidate_unvalidated / evidence_overlay_only</p>"
        "<dl>"
        f"<dt>Sentiment</dt><dd>{_report_text(_format_report_metrics(distribution))}</dd>"
        f"<dt>Stance</dt><dd>{_report_text(stance_status)} - {_report_text(stance_detail)}"
        f"{_report_stance_message(stance)}</dd>"
        "</dl>"
        f"<h3>Keywords</h3><ul>{keyword_items}</ul>"
        f"<h3>Topics</h3><ul>{topic_items}</ul>"
        f"<h3>Entities</h3><ul>{entity_items}</ul>"
        f"<h3>Near duplicates</h3><ul>{near_duplicate_items}</ul>"
        f"<h3>Community comparison</h3><ul>{community_items}</ul>"
        "</section>"
    )


def _report_semantic_traceability(semantic: dict[str, Any], actions: list[dict[str, Any]]) -> str:
    summary = semantic.get("summary") or {}
    support = summary.get("decision_support") or {}
    review_hints = _report_term_items(
        support.get("review_hints") or [],
        empty="No review hints available",
    )
    module_coverage = support.get("module_coverage") or {}
    module_items = _report_term_items(
        (
            f"{module}: {(coverage or {}).get('status', 'unknown')} "
            f"{(coverage or {}).get('covered', 0)}/{(coverage or {}).get('total', 0)}"
            f"{_format_block_code(coverage or {})}"
            for module, coverage in module_coverage.items()
        ),
        empty="No module coverage available",
    )
    semantic_examples = _report_term_items(
        _semantic_example_lines(summary),
        empty="No semantic examples available",
    )
    action_recommendations = _report_term_items(
        (
            f"{item.get('recommendation_id', '-')}: {item.get('action_id', '-')} "
            f"({item.get('status', '-')}/{item.get('score_policy', '-')}); "
            f"refs={', '.join(item.get('evidence_refs') or []) or '-'}; {item.get('rationale', '-')}"
            for item in support.get("action_recommendations") or []
        ),
        empty="No semantic action recommendations available",
    )
    action_refs = _report_term_items(
        (
            f"{action.get('action_id', '-')}: {', '.join(action.get('evidence_refs') or []) or '-'}"
            for action in actions
        ),
        empty="No action evidence refs available",
    )
    return (
        "<section><h2>Semantic traceability pack</h2>"
        "<p>candidate_unvalidated / evidence_overlay_only</p>"
        f"<h3>Review hints</h3><ul>{review_hints}</ul>"
        f"<h3>Module coverage</h3><ul>{module_items}</ul>"
        f"<h3>Semantic examples</h3><ul>{semantic_examples}</ul>"
        f"<h3>Semantic action recommendations</h3><ul>{action_recommendations}</ul>"
        f"<h3>Semantic action evidence refs</h3><ul>{action_refs}</ul>"
        "</section>"
    )


def _report_semantic_corrections(corrections: list[dict[str, Any]]) -> str:
    items = _report_term_items(
        (
            f"{item.get('correction_id', '-')}: record_semantic_correction; "
            f"{item.get('artifact_id', '-')}; {item.get('module', '-')}; "
            f"{item.get('target_ref', '-')}; {item.get('original_value', '')} -> "
            f"{item.get('corrected_value', '-')}; {item.get('status', '-')}; "
            f"{item.get('reason', '-')}"
            for item in corrections
        ),
        empty="No semantic corrections recorded",
    )
    return (
        "<section><h2>Semantic corrections</h2>"
        "<p>Manual corrections are advisory overlays and do not change CPR scores or closure gates.</p>"
        f"<ul>{items}</ul>"
        "</section>"
    )


def _report_audit_trail(audit_events: list[dict[str, Any]]) -> str:
    items = _report_term_items(
        (
            f"{item.get('event_id', '-')}: action={item.get('action', '-')}; "
            f"actor_id={item.get('actor_id', '-')}; target_id={item.get('target_id', '-')}; "
            f"created_at={item.get('created_at', '-')}; payload={_format_report_metrics(item.get('payload') or {})}"
            for item in audit_events
        ),
        empty="No audit events recorded",
    )
    return (
        "<section><h2>Closed-loop audit trail</h2>"
        "<p>Only real Case mutation events are listed; this trail does not fabricate platform evidence.</p>"
        f"<ul>{items}</ul>"
        "</section>"
    )


def _semantic_example_lines(summary: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    sentiment_examples = (summary.get("sentiment") or {}).get("examples") or {}
    for label, examples in sentiment_examples.items():
        for example in examples or []:
            lines.append(_semantic_example_line(example, source=f"sentiment:{label}"))
    stance = summary.get("stance") or {}
    for example in stance.get("examples") or []:
        source = f"stance:{example.get('stance') or stance.get('status') or 'unknown'}"
        lines.append(_semantic_example_line(example, source=source))
    return lines


def _semantic_example_line(example: dict[str, Any], *, source: str) -> str:
    return (
        f"{example.get('content_id', '-')}: {source}; "
        f"{example.get('platform', '-')}; {example.get('author_id', '-')}; "
        f"{example.get('content_kind', '-')}; {example.get('excerpt', '-')}"
    )


def _format_block_code(coverage: dict[str, Any]) -> str:
    block_code = coverage.get("block_code")
    return f" ({block_code})" if block_code else ""


def _report_term_items(values: Any, *, empty: str) -> str:
    items = [value for value in values if value]
    return "".join(f"<li>{_report_text(value)}</li>" for value in items) or f"<li>{_report_text(empty)}</li>"


def _report_stance_message(stance: dict[str, Any]) -> str:
    message = stance.get("message")
    if not message:
        return ""
    return f" <span>{_report_text(message)}</span>"


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        str(sorted(payload.items())).encode("utf-8", errors="ignore")
    ).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_report_metrics(metrics: dict[str, Any]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in metrics.items())


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
