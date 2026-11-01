"""Create one immutable Case Workbench artifact from supplied normalized input."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.core.analysis.semantic_enrichment import (
    HuggingFaceSemanticRuntime,
    analyze_semantic_enrichment_snapshot,
    propagation_path_overlay,
    refresh_semantic_artifact_hash,
)
from app.core.analysis.snapshots import build_event_snapshot
from app.core.analysis.contracts import TimeWindow
from app.db.mongodb import close_mongo, get_mongo_db
from app.services.case_frozen_artifact import (
    DEFAULT_FROZEN_CASE_OUTPUT_ROOT,
    FrozenArtifactError,
    FrozenArtifactWrite,
    FrozenCaseArtifactStore,
    build_frozen_case_artifact,
)
from app.services.case_research_archive import verify_research_archive

DEFAULT_CASE_ID = "case_trump_visit_2026_05_21"
DEFAULT_EVENT_ID = "trump_visit_2026_05_21"
DEFAULT_TRUMP_VISIT_CRAWL_JOB_IDS = (4, 5, 6)
EXPECTED_TRUMP_VISIT_IMPORT_SCOPE = {
    "posts": {
        "weibo": {"crawl_job_id": 4, "count": 165},
        "xhs": {"crawl_job_id": 5, "count": 98},
        "douyin": {"crawl_job_id": 6, "count": 31},
    },
    "comments": {
        "weibo": {"crawl_job_id": 4, "count": 2680},
        "xhs": {"crawl_job_id": 5, "count": 1905},
        "douyin": {"crawl_job_id": 6, "count": 10137},
    },
}
DEFAULT_COORDINATION_ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "output"
    / "coordination_runs"
    / "weibo-trump-visit-2026-05-21-2"
    / "run_20260702_133310_565249"
)


def precompute_case_artifact(
    normalized_input_path: str | Path,
    runtime_info_path: str | Path,
    *,
    output_root: str | Path = DEFAULT_FROZEN_CASE_OUTPUT_ROOT,
) -> FrozenArtifactWrite:
    """Persist a frozen artifact from existing normalized records and observed runtime facts.

    It deliberately does not query MongoDB or initialize model weights. A future
    runtime driver can produce the two JSON inputs and resume safely because a
    completed case directory is never overwritten.
    """

    normalized_input = _load_json(normalized_input_path, "normalized input")
    runtime_info = _load_json(runtime_info_path, "runtime info")
    case = normalized_input.get("case") if isinstance(normalized_input.get("case"), dict) else {}
    case_id = case.get("case_id") or normalized_input.get("case_id")
    event_id = case.get("event_id") or normalized_input.get("event_id")
    artifact = build_frozen_case_artifact(
        case_id=str(case_id or ""),
        event_id=str(event_id or ""),
        title=case.get("title") if isinstance(case, dict) else None,
        normalized_records={"posts": normalized_input.get("posts", []), "comments": normalized_input.get("comments", [])},
        runtime_info=runtime_info,
        authority_claims=_mapping_list(normalized_input.get("authority_claims")),
        coordination=_mapping(normalized_input.get("coordination")),
        propagation=_mapping(normalized_input.get("propagation")),
        semantic=_mapping(normalized_input.get("semantic")),
        review=_mapping(normalized_input.get("review")),
    )
    return FrozenCaseArtifactStore(output_root).write(artifact)


async def precompute_trump_visit_case(
    *,
    output_root: str | Path = DEFAULT_FROZEN_CASE_OUTPUT_ROOT,
    limit: int | None = None,
    crawl_job_ids: Iterable[int] | None = None,
) -> FrozenArtifactWrite:
    """Run the real local semantic runtime over the imported three-platform Case."""

    selected_crawl_job_ids = _validate_trump_visit_crawl_job_ids(crawl_job_ids)
    if limit is not None:
        raise FrozenArtifactError(
            "The expected three-platform import scope is incomplete or contaminated when --limit is used."
        )
    query = {
        "event_id": DEFAULT_EVENT_ID,
        "crawl_job_id": {"$in": list(selected_crawl_job_ids)},
    }
    database = get_mongo_db()
    try:
        posts = await database["raw_posts"].find(query, {"_id": 0}).to_list(length=None)
        comments = await database["raw_comments"].find(query, {"_id": 0}).to_list(length=None)
    finally:
        await close_mongo()
    _validate_trump_visit_import_scope(posts, comments, crawl_job_ids=selected_crawl_job_ids)
    snapshot = build_event_snapshot(
        event_id=DEFAULT_EVENT_ID,
        posts=posts,
        comments=comments,
        core_window=TimeWindow(start="2026-05-11T00:00:00+00:00", end="2026-05-22T00:00:00+00:00"),
        context_window=TimeWindow(start="2025-01-01T00:00:00+00:00", end="2026-05-31T00:00:00+00:00"),
    )
    expected_post_count = len(posts)
    expected_comment_count = len(comments)
    actual_post_count = len(snapshot.posts)
    actual_comment_count = len(snapshot.comments)
    if (actual_post_count, actual_comment_count) != (expected_post_count, expected_comment_count):
        raise FrozenArtifactError(
            "EventSnapshot normalization excluded imported records: "
            f"expected {expected_post_count:,} posts and {expected_comment_count:,} comments; "
            f"actual {actual_post_count:,} posts and {actual_comment_count:,} comments."
        )
    _attach_archived_coordination_communities(snapshot.posts)
    claims = _authority_claims()
    primary_claim = next((item for item in claims if item.get("role") == "primary"), None)
    runtime = HuggingFaceSemanticRuntime()
    semantic = analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim": primary_claim},
        runtime=runtime,
    )
    coordination = _coordination_artifact()
    propagation = _observed_propagation(
        snapshot,
        semantic=semantic,
        primary_claim_ref=str(primary_claim.get("claim_id") or "") if primary_claim else None,
    )
    runtime_info = {
        "runtime_status": semantic["runtime_status"],
        "runtime_backend": semantic["runtime_backend"],
        "device": semantic["provenance"]["device"],
        "model_versions": semantic["model_versions"],
        "run_id": f"run_trump_visit_semantic_{snapshot.data_fingerprint[:12]}",
    }
    artifact = build_frozen_case_artifact(
        case_id=DEFAULT_CASE_ID,
        event_id=DEFAULT_EVENT_ID,
        title="特朗普访华三平台案例闭环",
        normalized_records={"posts": snapshot.posts, "comments": snapshot.comments},
        runtime_info=runtime_info,
        authority_claims=claims,
        coordination=coordination,
        propagation=propagation,
        semantic={key: value for key, value in semantic.items() if key != "_runtime_rows"},
        review={
            "status": "awaiting_review",
            "reason": "Real Coordination, Propagation, and semantic evidence were precomputed; canonical review remains human-only.",
        },
    )
    return FrozenCaseArtifactStore(output_root).write(artifact)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.trump_visit:
        result = asyncio.run(
            precompute_trump_visit_case(
                output_root=args.output_root,
                limit=args.limit,
                crawl_job_ids=args.crawl_job_ids,
            )
        )
    elif args.normalized_input is not None and args.runtime_info is not None:
        result = precompute_case_artifact(args.normalized_input, args.runtime_info, output_root=args.output_root)
    else:
        parser.error("provide --trump-visit or both --normalized-input and --runtime-info")
    print(json.dumps({"artifact_path": str(result.artifact_path), "report_path": str(result.report_path)}, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-input", type=Path)
    parser.add_argument("--runtime-info", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_FROZEN_CASE_OUTPUT_ROOT)
    parser.add_argument("--trump-visit", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--crawl-job-ids",
        type=_parse_crawl_job_ids,
        default=DEFAULT_TRUMP_VISIT_CRAWL_JOB_IDS,
        metavar="4,5,6",
        help="comma-separated imported crawl job ids; the frozen Trump-visit Case requires 4,5,6",
    )
    return parser


def _load_json(path: str | Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrozenArtifactError(f"Unable to read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise FrozenArtifactError(f"{label} must be a JSON object")
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value] if isinstance(value, list) and all(isinstance(item, dict) for item in value) else []


def _parse_crawl_job_ids(value: str) -> tuple[int, ...]:
    try:
        values = tuple(int(item.strip()) for item in str(value).split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("crawl job ids must be comma-separated integers") from exc
    if not values:
        raise argparse.ArgumentTypeError("crawl job ids must not be empty")
    return values


def _validate_trump_visit_crawl_job_ids(crawl_job_ids: Iterable[int] | None) -> tuple[int, ...]:
    selected = tuple(DEFAULT_TRUMP_VISIT_CRAWL_JOB_IDS if crawl_job_ids is None else crawl_job_ids)
    try:
        normalized = tuple(int(value) for value in selected)
    except (TypeError, ValueError) as exc:
        raise FrozenArtifactError("The expected three-platform import scope is incomplete or contaminated.") from exc
    if len(normalized) != len(set(normalized)) or set(normalized) != set(DEFAULT_TRUMP_VISIT_CRAWL_JOB_IDS):
        raise FrozenArtifactError("The expected three-platform import scope is incomplete or contaminated.")
    return tuple(sorted(normalized))


def _validate_trump_visit_import_scope(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    *,
    crawl_job_ids: Iterable[int] | None = None,
) -> None:
    _validate_trump_visit_crawl_job_ids(crawl_job_ids)
    actual_scopes = {
        "posts": _platform_job_counts(posts),
        "comments": _platform_job_counts(comments),
    }
    expected_scopes = {
        kind: Counter(
            {
                (platform, specification["crawl_job_id"]): specification["count"]
                for platform, specification in platforms.items()
            }
        )
        for kind, platforms in EXPECTED_TRUMP_VISIT_IMPORT_SCOPE.items()
    }
    if actual_scopes != expected_scopes:
        raise FrozenArtifactError("The expected three-platform import scope is incomplete or contaminated.")


def _platform_job_counts(rows: Iterable[dict[str, Any]]) -> Counter[tuple[str, int]]:
    counts: Counter[tuple[str, int]] = Counter()
    for row in rows:
        if not isinstance(row, dict) or str(row.get("event_id") or "") != DEFAULT_EVENT_ID:
            return Counter({("invalid", -1): 1})
        try:
            crawl_job_id = int(row.get("crawl_job_id"))
        except (TypeError, ValueError):
            return Counter({("invalid", -1): 1})
        platform = str(row.get("platform") or "").strip()
        if not platform:
            return Counter({("invalid", -1): 1})
        counts[(platform, crawl_job_id)] += 1
    return counts


def _authority_claims() -> list[dict[str, Any]]:
    archive_root = Path(__file__).resolve().parents[3] / "doc" / "research" / "case-workbench"
    entries = {entry.purpose: entry for entry in verify_research_archive(archive_root)}
    definitions = (
        ("primary_claim", "claim_cctv_primary", "primary", "推动中美关系这艘巨轮沿着正确航道平稳前行", "央视新闻"),
        ("supplementary_claim", "claim_xinhua_support", "supplementary", "历史性、标志性的访问", "新华社"),
    )
    claims = []
    for purpose, claim_id, role, excerpt, account in definitions:
        entry = entries.get(purpose)
        if entry is None:
            raise FrozenArtifactError(f"Verified archive is missing {purpose}.")
        claims.append(
            {
                "claim_id": claim_id,
                "role": role,
                "status": "candidate_unvalidated",
                "excerpt": excerpt,
                "account": account,
                "url": entry.source_url,
                "source_tier": "central_mainstream_original",
                "source_archive_id": entry.archive_id,
                "source_content_hash": entry.source_sha256,
                "source_markdown_hash": entry.markdown_sha256,
                "source_content_capture": "markitdown_archive",
            }
        )
    return claims


def _coordination_artifact() -> dict[str, Any]:
    discovery_path = DEFAULT_COORDINATION_ARTIFACT / "discovery_summary.json"
    detection_path = DEFAULT_COORDINATION_ARTIFACT / "detection_summary.json"
    if not discovery_path.is_file() or not detection_path.is_file():
        raise FrozenArtifactError("The archived CooRTweet-derived Coordination artifact is required.")
    discovery = _load_json(discovery_path, "Coordination discovery artifact")
    detection = _load_json(detection_path, "Coordination detection artifact")
    return {
        "status": "precomputed",
        "implementation": "coortweet_internalized",
        "artifact_dir": str(DEFAULT_COORDINATION_ARTIFACT),
        "discovery_sha256": hashlib.sha256(discovery_path.read_bytes()).hexdigest(),
        "detection_sha256": hashlib.sha256(detection_path.read_bytes()).hexdigest(),
        "community_algorithm": discovery.get("community_algorithm_effective"),
        "metrics": discovery.get("metrics") or {},
        "graph_metrics": discovery.get("graph_metrics") or {},
        "communities": discovery.get("communities") or [],
        "detection_summary": detection.get("metrics") or detection,
    }


def _observed_propagation(
    snapshot: Any,
    *,
    semantic: dict[str, Any] | None = None,
    primary_claim_ref: str | None = None,
) -> dict[str, Any]:
    paths = []
    for relation in snapshot.relationships:
        source_ref = str(relation.source_id or "")
        target_ref = str(relation.target_id or "")
        evidence_ref = str(relation.evidence_ref or "")
        path = {
            "path_id": evidence_ref,
            "relation_type": relation.relation_type,
            "source_id": source_ref,
            "target_id": target_ref,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "platform": relation.platform,
            "observed_at": relation.observed_at.isoformat() if relation.observed_at else None,
            "evidence_ref": evidence_ref,
            "evidence_refs": sorted({ref for ref in (source_ref, target_ref, evidence_ref) if ref}),
            "edges": [
                {
                    "source_ref": source_ref,
                    "target_ref": target_ref,
                    "evidence_ref": evidence_ref,
                }
            ],
        }
        paths.append(path)
    if semantic and semantic.get("runtime_status") == "ok":
        runtime_rows = semantic.get("_runtime_rows")
        successful_rows = runtime_rows if isinstance(runtime_rows, list) else []
        for path in paths:
            path["semantic_overlay"] = propagation_path_overlay(
                path,
                successful_rows,
                primary_claim_ref=primary_claim_ref,
            )
        semantic.setdefault("cross_analysis", {})["propagation_path_overlays"] = [
            {"path_id": path["path_id"], **path["semantic_overlay"]}
            for path in paths
        ]
        refresh_semantic_artifact_hash(semantic)
    return {
        "status": "observed_precomputed",
        "implementation": "hoaxy_style_observed_claim_diffusion",
        "relationship_count": len(paths),
        "paths": paths,
        "source": "event_snapshot_relationships",
    }


def _attach_archived_coordination_communities(posts: list[dict[str, Any]]) -> None:
    """Attach only real CooRTweet-derived cluster ids to matching Weibo accounts."""

    discovery_path = DEFAULT_COORDINATION_ARTIFACT / "discovery_summary.json"
    discovery = _load_json(discovery_path, "Coordination discovery artifact")
    communities = {
        str(node.get("account_id") or ""): str(node.get("cluster_id"))
        for node in discovery.get("nodes") or []
        if str(node.get("account_id") or "") and node.get("cluster_id") is not None
    }
    for post in posts:
        if str(post.get("platform") or "") != "weibo":
            continue
        cluster_id = communities.get(str(post.get("author_id") or ""))
        if cluster_id:
            post["coordination_community_id"] = cluster_id


if __name__ == "__main__":
    main()


__all__ = ["main", "precompute_case_artifact", "precompute_trump_visit_case"]
