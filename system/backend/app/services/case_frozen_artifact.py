"""Immutable filesystem artifacts for precomputed Case Workbench projections."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

FROZEN_ARTIFACT_SCHEMA = "cogguard.case_workbench.frozen.v1"
DEFAULT_FROZEN_CASE_OUTPUT_ROOT = Path(__file__).resolve().parents[3] / "output" / "case_workbench"


class FrozenArtifactError(ValueError):
    """Raised when caller-supplied precompute evidence is incomplete or unsafe."""


class FrozenCaseArtifactStore:
    """Persist and load append-only Case artifacts without a database dependency."""

    def __init__(self, output_root: str | Path = DEFAULT_FROZEN_CASE_OUTPUT_ROOT) -> None:
        self.output_root = Path(output_root)

    def artifact_path(self, case_id: str) -> Path:
        return self.output_root / _safe_case_id(case_id) / "case_artifact.json"

    def report_path(self, case_id: str) -> Path:
        return self.output_root / _safe_case_id(case_id) / "report.html"

    def exists(self, case_id: str) -> bool:
        return self.artifact_path(case_id).is_file()

    def load(self, case_id: str) -> dict[str, Any] | None:
        path = self.artifact_path(case_id)
        if not path.is_file():
            return None
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FrozenArtifactError(f"Frozen Case artifact is unreadable: {path}") from exc
        _validate_artifact(artifact, expected_case_id=case_id)
        return artifact

    def write(self, artifact: dict[str, Any]) -> "FrozenArtifactWrite":
        _validate_artifact(artifact)
        case_id = str(artifact["case"]["case_id"])
        destination = self.artifact_path(case_id).parent
        artifact_path = destination / "case_artifact.json"
        report_path = destination / "report.html"
        if destination.exists():
            raise FileExistsError(f"Frozen Case artifact already exists: {destination}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{_safe_case_id(case_id)}-", dir=destination.parent))
        try:
            temporary_artifact = temporary / artifact_path.name
            temporary_report = temporary / report_path.name
            _write_json(temporary_artifact, artifact)
            _write_text(temporary_report, render_frozen_case_report(artifact))
            _fsync_directory_files(temporary_artifact, temporary_report)
            os.replace(temporary, destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return FrozenArtifactWrite(artifact_path=artifact_path, report_path=report_path)


class FrozenArtifactWrite:
    def __init__(self, *, artifact_path: Path, report_path: Path) -> None:
        self.artifact_path = artifact_path
        self.report_path = report_path


def build_frozen_case_artifact(
    *,
    case_id: str,
    event_id: str,
    normalized_records: dict[str, Any],
    runtime_info: dict[str, Any],
    authority_claims: list[dict[str, Any]],
    coordination: dict[str, Any],
    propagation: dict[str, Any],
    semantic: dict[str, Any],
    review: dict[str, Any],
    title: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic Case projection from already-normalized caller data.

    This function intentionally does not instantiate a model runtime or query a DB.
    The caller must supply observed runtime identity and all analytic outputs.
    """

    case_id = _required_text(case_id, "case_id")
    event_id = _required_text(event_id, "event_id")
    if not isinstance(normalized_records, dict):
        raise FrozenArtifactError("normalized_records must be a mapping")
    _require_runtime_info(runtime_info)
    posts = _record_list(normalized_records, "posts")
    comments = _record_list(normalized_records, "comments")
    snapshot = {
        "snapshot_id": _snapshot_id(case_id, event_id, posts, comments),
        "event_id": event_id,
        "posts": posts,
        "comments": comments,
        "post_count": len(posts),
        "comment_count": len(comments),
        "data_fingerprint": _sha256({"posts": posts, "comments": comments}),
        "provenance": _normalized_provenance(posts, comments),
    }
    canonical_review = dict(review) if isinstance(review, dict) else {}
    canonical_review["status"] = "awaiting_human_review"
    canonical_review["canonical_verdict"] = {
        "status": "not_approved",
        "label": "human_review_required",
        "source": "frozen_precompute",
    }
    canonical_review["closeout_review"] = None
    canonical_review["claimability"] = "non_claimable_until_human_review"
    artifact = {
        "schema_version": FROZEN_ARTIFACT_SCHEMA,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "case": {
            "case_id": case_id,
            "event_id": event_id,
            "title": title or case_id,
            "state": "awaiting_review",
            "mutability": "immutable_artifact",
        },
        "snapshot": snapshot,
        "authority_claims": [dict(item) for item in authority_claims if isinstance(item, dict)],
        "coordination": dict(coordination) if isinstance(coordination, dict) else {},
        "propagation": dict(propagation) if isinstance(propagation, dict) else {},
        "semantic": {
            **(dict(semantic) if isinstance(semantic, dict) else {}),
            "runtime": _canonical_value(runtime_info),
            "score_policy": "evidence_overlay_only",
        },
        "review": canonical_review,
    }
    artifact["report_manifest"] = {
        "version": 1,
        "status": "frozen_pending_human_review",
        "format": "html",
        "html_file": "report.html",
        "contains": [
            "case",
            "snapshot",
            "authority_claims",
            "coordination",
            "propagation",
            "semantic",
            "review",
            "content_hashes",
        ],
    }
    artifact["content_hashes"] = {
        section: _sha256(artifact[section])
        for section in (
            "case",
            "snapshot",
            "authority_claims",
            "coordination",
            "propagation",
            "semantic",
            "review",
            "report_manifest",
        )
    }
    artifact["artifact_sha256"] = _artifact_hash(artifact)
    return artifact


def render_frozen_case_report(artifact: dict[str, Any]) -> str:
    """Render a concise, print-friendly summary of the immutable artifact."""

    _validate_artifact(artifact)
    case = artifact["case"]
    snapshot = artifact["snapshot"]
    semantic = artifact.get("semantic") if isinstance(artifact.get("semantic"), dict) else {}
    runtime = semantic.get("runtime") if isinstance(semantic.get("runtime"), dict) else {}
    coordination = artifact.get("coordination") if isinstance(artifact.get("coordination"), dict) else {}
    propagation = artifact.get("propagation") if isinstance(artifact.get("propagation"), dict) else {}
    review = artifact.get("review") if isinstance(artifact.get("review"), dict) else {}
    claims = artifact.get("authority_claims") if isinstance(artifact.get("authority_claims"), list) else []
    model_versions = runtime.get("model_versions") if isinstance(runtime.get("model_versions"), dict) else {}
    claim_items = _html_list(
        (
            f"{claim.get('role', 'claim')}: {claim.get('excerpt', claim.get('claim_id', '-'))}"
            for claim in claims[:8]
            if isinstance(claim, dict)
        ),
        empty="No authority claims recorded",
    )
    coordination_metrics = coordination.get("metrics") or coordination.get("graph_metrics") or {}
    propagation_paths = propagation.get("paths") if isinstance(propagation.get("paths"), list) else []
    semantic_summary = _frozen_semantic_report_summary(semantic)
    hashes = artifact.get("content_hashes") if isinstance(artifact.get("content_hashes"), dict) else {}
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{escape(str(case['case_id']))} frozen Case report</title>"
        "<style>body{font-family:Arial,sans-serif;line-height:1.45;margin:2rem;max-width:900px}"
        "section{border-top:1px solid #bbb;margin-top:1.25rem;padding-top:.65rem}"
        "dt{font-weight:bold}dd{margin:0 0 .45rem}code{word-break:break-all}@media print{body{margin:1cm}}</style>"
        "</head><body><h1>CogGuard Frozen Case Report</h1>"
        "<section><h2>Case</h2><dl>"
        f"<dt>Case ID</dt><dd><code>{escape(str(case['case_id']))}</code></dd>"
        f"<dt>Event ID</dt><dd><code>{escape(str(case['event_id']))}</code></dd>"
        f"<dt>State</dt><dd>{escape(str(case['state']))}</dd>"
        f"<dt>Frozen at</dt><dd>{escape(str(artifact.get('frozen_at') or 'unknown'))}</dd>"
        "</dl></section>"
        "<section><h2>Snapshot</h2><dl>"
        f"<dt>Snapshot ID</dt><dd><code>{escape(str(snapshot.get('snapshot_id') or 'unknown'))}</code></dd>"
        f"<dt>Posts</dt><dd>{escape(str(snapshot.get('post_count', 0)))}</dd>"
        f"<dt>Comments</dt><dd>{escape(str(snapshot.get('comment_count', 0)))}</dd>"
        f"<dt>Data fingerprint</dt><dd><code>{escape(str(snapshot.get('data_fingerprint') or 'unknown'))}</code></dd>"
        f"<dt>Provenance</dt><dd>{escape(_compact_text(snapshot.get('provenance') or []))}</dd>"
        "</dl></section>"
        "<section><h2>Model runtime</h2><dl>"
        f"<dt>Status</dt><dd>{escape(str(runtime.get('runtime_status') or semantic.get('runtime_status') or 'unknown'))}</dd>"
        f"<dt>Backend</dt><dd>{escape(str(runtime.get('runtime_backend') or semantic.get('runtime_backend') or 'unknown'))}</dd>"
        f"<dt>Device</dt><dd>{escape(str(runtime.get('device') or 'unknown'))}</dd>"
        f"<dt>Run ID</dt><dd><code>{escape(str(runtime.get('run_id') or 'unknown'))}</code></dd>"
        f"<dt>Model versions</dt><dd>{escape(_compact_text(model_versions))}</dd>"
        "</dl></section>"
        f"<section><h2>Authority claims</h2><ul>{claim_items}</ul></section>"
        "<section><h2>Coordination</h2><dl>"
        f"<dt>Status</dt><dd>{escape(str(coordination.get('status') or 'unknown'))}</dd>"
        f"<dt>Implementation</dt><dd>{escape(str(coordination.get('implementation') or 'unknown'))}</dd>"
        f"<dt>Metrics</dt><dd>{escape(_compact_text(coordination_metrics))}</dd>"
        f"<dt>Communities</dt><dd>{escape(str(len(coordination.get('communities') or [])))}</dd>"
        "</dl></section>"
        "<section><h2>Propagation</h2><dl>"
        f"<dt>Status</dt><dd>{escape(str(propagation.get('status') or 'unknown'))}</dd>"
        f"<dt>Relationships</dt><dd>{escape(str(propagation.get('relationship_count', len(propagation_paths))))}</dd>"
        f"<dt>Path summary</dt><dd>{escape(_compact_path_summary(propagation_paths))}</dd>"
        "</dl></section>"
        f"<section><h2>Semantic summary</h2>{semantic_summary}</section>"
        "<section><h2>Review status</h2><dl>"
        f"<dt>Status</dt><dd>{escape(str(review.get('status') or 'awaiting_human_review'))}</dd>"
        f"<dt>Canonical verdict</dt><dd>{escape(_compact_text(review.get('canonical_verdict') or {}))}</dd>"
        "<dt>Blocker</dt><dd>Human review is required before canonical approval or closeout.</dd>"
        "</dl></section>"
        "<section><h2>Artifact evidence</h2><dl>"
        f"<dt>Artifact SHA-256</dt><dd><code>{escape(str(artifact.get('artifact_sha256') or 'unknown'))}</code></dd>"
        f"<dt>Content hashes</dt><dd>{escape(_compact_text(hashes))}</dd>"
        f"<dt>Report manifest</dt><dd>{escape(_compact_text(artifact.get('report_manifest') or {}))}</dd>"
        "</dl></section></body></html>"
    )


def _html_list(values: Any, *, empty: str) -> str:
    items = [str(value) for value in values if value]
    return "".join(f"<li>{escape(value)}</li>" for value in items) or f"<li>{escape(empty)}</li>"


def _compact_text(value: Any, *, limit: int = 1_200) -> str:
    text = _json(value)
    return text if len(text) <= limit else f"{text[:limit]}..."


def _compact_path_summary(paths: list[Any]) -> str:
    summaries = []
    for path in paths[:8]:
        if not isinstance(path, dict):
            continue
        summaries.append(
            f"{path.get('path_id') or '-'}: {path.get('source_id') or '-'} -> {path.get('target_id') or '-'}"
        )
    return "; ".join(summaries) or "No displayable path summary recorded"


def _frozen_semantic_report_summary(semantic: dict[str, Any]) -> str:
    keywords = (semantic.get("keywords") or {}).get("main_posts") or []
    topics = ((semantic.get("topics") or {}).get("main_posts") or {}).get("items") or []
    sentiment = ((semantic.get("sentiment") or {}).get("summary") or {}).get("distribution") or {}
    stance = semantic.get("stance") or {}
    return (
        "<dl>"
        f"<dt>Status</dt><dd>{escape(str(semantic.get('status') or 'unknown'))}</dd>"
        f"<dt>Validation</dt><dd>{escape(str(semantic.get('validation_status') or semantic.get('model_status') or 'unknown'))}</dd>"
        f"<dt>Score policy</dt><dd>{escape(str(semantic.get('score_policy') or 'evidence_overlay_only'))}</dd>"
        f"<dt>Sentiment</dt><dd>{escape(_compact_text(sentiment, limit=400))}</dd>"
        f"<dt>Keywords</dt><dd>{escape(', '.join(str(item.get('term') or '') for item in keywords[:8] if isinstance(item, dict)) or 'None')}</dd>"
        f"<dt>Topics</dt><dd>{escape(', '.join(str(item.get('label') or '') for item in topics[:6] if isinstance(item, dict)) or 'None')}</dd>"
        f"<dt>Stance</dt><dd>{escape(_compact_text({key: stance.get(key) for key in ('status', 'distribution', 'code')}, limit=400))}</dd>"
        "</dl>"
    )


def _validate_artifact(artifact: Any, *, expected_case_id: str | None = None) -> None:
    if not isinstance(artifact, dict) or artifact.get("schema_version") != FROZEN_ARTIFACT_SCHEMA:
        raise FrozenArtifactError("Unsupported frozen Case artifact schema")
    case = artifact.get("case")
    if not isinstance(case, dict):
        raise FrozenArtifactError("Frozen Case artifact is missing case")
    case_id = _required_text(case.get("case_id"), "case.case_id")
    if expected_case_id is not None and case_id != expected_case_id:
        raise FrozenArtifactError("Frozen Case artifact case id does not match requested case")
    if case.get("state") == "closed":
        raise FrozenArtifactError("Frozen Case artifact cannot claim a closed Case")
    review = artifact.get("review")
    if not isinstance(review, dict) or review.get("status") != "awaiting_human_review":
        raise FrozenArtifactError("Frozen Case artifact must retain pending human review")
    verdict = review.get("canonical_verdict")
    if isinstance(verdict, dict) and verdict.get("status") == "approved":
        raise FrozenArtifactError("Frozen Case artifact cannot claim an approved human verdict")
    hashes = artifact.get("content_hashes")
    if not isinstance(hashes, dict):
        raise FrozenArtifactError("Frozen Case artifact is missing content hashes")
    for section, recorded_hash in hashes.items():
        if section not in artifact or recorded_hash != _sha256(artifact[section]):
            raise FrozenArtifactError(f"Frozen Case artifact hash mismatch: {section}")
    if artifact.get("artifact_sha256") != _artifact_hash(artifact):
        raise FrozenArtifactError("Frozen Case artifact aggregate hash mismatch")


def _require_runtime_info(runtime_info: Any) -> None:
    if not isinstance(runtime_info, dict):
        raise FrozenArtifactError("runtime_info must be supplied by the caller")
    required = ("runtime_status", "runtime_backend", "device", "model_versions", "run_id")
    missing = [field for field in required if not runtime_info.get(field)]
    if missing:
        raise FrozenArtifactError(f"runtime_info is missing required fields: {', '.join(missing)}")
    if str(runtime_info["runtime_status"]).lower() not in {"ok", "available", "completed"}:
        raise FrozenArtifactError("runtime_info must describe a successful real runtime")


def _record_list(records: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = records.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise FrozenArtifactError(f"normalized_records.{key} must be a list of mappings")
    return [_canonical_value(item) for item in value]


def _normalized_provenance(posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for item in [*posts, *comments]:
        source = item.get("crawl_job_id") or item.get("source_id") or item.get("source_keyword")
        if source:
            values.append({"source_id": str(source), "platform": str(item.get("platform") or "unknown")})
    return sorted({(item["source_id"], item["platform"]) for item in values}) and [
        {"source_id": source_id, "platform": platform}
        for source_id, platform in sorted({(item["source_id"], item["platform"]) for item in values})
    ]


def _snapshot_id(case_id: str, event_id: str, posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> str:
    return f"snapshot_{_sha256({'case_id': case_id, 'event_id': event_id, 'posts': posts, 'comments': comments})[:24]}"


def _artifact_hash(artifact: dict[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    return _sha256(payload)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    return value


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FrozenArtifactError(f"{name} is required")
    return text


def _safe_case_id(case_id: str) -> str:
    safe = _required_text(case_id, "case_id")
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in safe):
        raise FrozenArtifactError("case_id contains unsupported path characters")
    return safe


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(_json(value) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _fsync_directory_files(*paths: Path) -> None:
    for path in paths:
        with path.open("r+b") as handle:
            os.fsync(handle.fileno())


__all__ = [
    "DEFAULT_FROZEN_CASE_OUTPUT_ROOT",
    "FROZEN_ARTIFACT_SCHEMA",
    "FrozenArtifactError",
    "FrozenArtifactWrite",
    "FrozenCaseArtifactStore",
    "build_frozen_case_artifact",
    "render_frozen_case_report",
]
