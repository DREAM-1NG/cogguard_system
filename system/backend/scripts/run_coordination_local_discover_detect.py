from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_ROOT = BACKEND_ROOT.parent
REPO_ROOT = SYSTEM_ROOT.parent
CHINA_TZ = timezone(timedelta(hours=8))
DEFAULT_EVENT_ID = "trump_visit_2026_05"
DEFAULT_CORE_WINDOW = (
    datetime(2026, 5, 11, 0, 0, tzinfo=CHINA_TZ),
    datetime(2026, 5, 22, 0, 0, tzinfo=CHINA_TZ),
)
DEFAULT_CONTEXT_WINDOW = (
    datetime(2026, 5, 1, 0, 0, tzinfo=CHINA_TZ),
    datetime(2026, 6, 1, 0, 0, tzinfo=CHINA_TZ),
)
PRECOMPUTED_TEXT_EMBEDDING_FIELDS = ("lm_text_embedding", "semantic_text_embedding", "text_embedding")


def _ensure_app_package() -> None:
    if "app" in sys.modules:
        return
    init_file = BACKEND_ROOT / "app" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "app",
        init_file,
        submodule_search_locations=[str(BACKEND_ROOT / "app")],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load backend app package from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["app"] = module
    spec.loader.exec_module(module)


_ensure_app_package()

from app.core.analysis import TimeWindow, build_event_snapshot  # noqa: E402


@dataclass(frozen=True)
class SourceFileRecord:
    path: Path
    platform: str
    kind: str
    line_count: int
    loaded_count: int
    failed_count: int
    sha256: str

    def to_dict(self, root: Path) -> dict[str, Any]:
        return {
            "path": _safe_relative(self.path, root),
            "platform": self.platform,
            "kind": self.kind,
            "line_count": self.line_count,
            "loaded_count": self.loaded_count,
            "failed_count": self.failed_count,
            "sha256": self.sha256,
        }


@dataclass
class LocalRows:
    posts: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    source_files: list[SourceFileRecord]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CoordinationDiscover Discover/Detect validation on local three-platform Trump-visit JSONL data."
    )
    parser.add_argument(
        "--data-root",
        default=str(REPO_ROOT / "MediaCrawler-main" / "data_runs"),
        help="Offline JSONL input root. This is an experiment input, not a runtime dependency.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory. Defaults to system/output/coordination_discover_detect_local/<utc timestamp>.",
    )
    parser.add_argument("--event-id", default=DEFAULT_EVENT_ID)
    parser.add_argument("--platforms", nargs="*", default=["weibo", "douyin", "xhs"])
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--embedding-dim", type=int, default=12)
    parser.add_argument("--negative-ratio", type=int, default=1)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--min-learned-edge-score", type=float, default=0.05)
    parser.add_argument("--snapshot-scope", choices=("per-platform", "combined", "all"), default="per-platform")
    parser.add_argument("--max-posts-per-platform", type=int, default=0, help="0 means no cap.")
    parser.add_argument("--max-comments-per-platform", type=int, default=0, help="0 means no cap.")
    parser.add_argument("--write-discover-artifacts", action="store_true")
    parser.add_argument("--include-full-results", action="store_true")
    parser.add_argument("--allow-non-leiden-exploration", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = _output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    rows = load_local_rows(Path(args.data_root), platforms=set(args.platforms), event_id=args.event_id)
    capped_posts, post_cap_report = _cap_by_platform(rows.posts, max_per_platform=args.max_posts_per_platform, id_field="post_id")
    capped_comments, comment_cap_report = _cap_by_platform(
        rows.comments,
        max_per_platform=args.max_comments_per_platform,
        id_field="comment_id",
    )
    all_snapshots = _build_snapshots(
        event_id=args.event_id,
        platforms=tuple(args.platforms),
        posts=capped_posts,
        comments=capped_comments,
    )
    snapshots = _select_snapshots(all_snapshots, scope=args.snapshot_scope)
    coordination_discover = _load_coordination_discover()

    result_records = []
    summary_rows = []
    for snapshot_name, snapshot in snapshots.items():
        artifact_dir = output_dir / "artifacts" / snapshot_name if args.write_discover_artifacts else None
        run_result = _run_snapshot(
            coordination_discover=coordination_discover,
            snapshot_name=snapshot_name,
            snapshot=snapshot,
            artifact_dir=artifact_dir,
            args=args,
        )
        result_records.append(run_result)
        summary_rows.append(_summary_row(run_result))

    inventory = _dataset_inventory(
        rows=rows,
        data_root=Path(args.data_root).resolve(),
        post_cap_report=post_cap_report,
        comment_cap_report=comment_cap_report,
        snapshots=snapshots,
    )
    manifest = {
        "run_id": output_dir.name,
        "generated_at": _utc_now(),
        "runtime_seconds": round(time.time() - started, 3),
        "script": _safe_relative(Path(__file__).resolve(), REPO_ROOT),
        "preflight": _safe_relative(
            REPO_ROOT
            / "research-wiki"
            / "preflight_runs"
            / "20260722T171047Z-align-coordination-discover-detect-with-high-level-literature"
            / "preflight.json",
            REPO_ROOT,
        ),
        "event_id": args.event_id,
        "data_root": str(Path(args.data_root).resolve()),
        "claim_boundary": {
            "discovery": "case_study_and_system_validation",
            "detect": "validation_only_missing_labels_on_local_trump_data",
            "process_motifs": "exploratory_non_claimable",
        },
        "config": {
            "platforms": list(args.platforms),
            "epochs": args.epochs,
            "embedding_dim": args.embedding_dim,
            "negative_ratio": args.negative_ratio,
            "device": args.device,
            "min_learned_edge_score": args.min_learned_edge_score,
            "snapshot_scope": args.snapshot_scope,
            "max_posts_per_platform": args.max_posts_per_platform,
            "max_comments_per_platform": args.max_comments_per_platform,
            "write_discover_artifacts": args.write_discover_artifacts,
            "include_full_results": args.include_full_results,
            "require_leiden": not args.allow_non_leiden_exploration,
        },
        "outputs": {
            "dataset_inventory": "dataset_inventory.json",
            "discover_detect_results": "discover_detect_results.json",
            "effectiveness_summary": "effectiveness_summary.json",
            "summary_csv": "summary.csv",
            "report": "report.md",
        },
    }
    effectiveness = _effectiveness_summary(
        manifest=manifest,
        inventory=inventory,
        summary_rows=summary_rows,
        result_records=result_records,
    )

    _write_json(output_dir / "dataset_inventory.json", inventory)
    _write_json(output_dir / "discover_detect_results.json", {"results": result_records})
    _write_json(output_dir / "effectiveness_summary.json", effectiveness)
    _write_json(output_dir / "manifest.json", manifest)
    _write_csv(output_dir / "summary.csv", summary_rows)
    (output_dir / "report.md").write_text(
        _report_markdown(manifest, inventory, summary_rows, effectiveness),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output_dir), "summary": summary_rows}, ensure_ascii=False, indent=2))


def load_local_rows(data_root: Path, *, platforms: set[str], event_id: str = DEFAULT_EVENT_ID) -> LocalRows:
    posts: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    source_files: list[SourceFileRecord] = []
    for path in _discover_input_files(data_root, platforms=platforms):
        platform = _platform_from_path(path)
        kind = _source_kind_from_path(path)
        loaded_rows, record = _read_jsonl(path, platform=platform, kind=kind)
        source_files.append(record)
        if kind == "post":
            posts.extend(_normalize_post(row, platform=platform, event_id=event_id, source_path=path) for row in loaded_rows)
        elif kind == "comment":
            comments.extend(_normalize_comment(row, platform=platform, event_id=event_id, source_path=path) for row in loaded_rows)
    return LocalRows(posts=posts, comments=comments, source_files=source_files)


def _discover_input_files(data_root: Path, *, platforms: set[str]) -> list[Path]:
    if not data_root.exists():
        raise FileNotFoundError(f"Local data root not found: {data_root}")
    files = []
    for path in data_root.rglob("*.jsonl"):
        lowered = path.as_posix().lower()
        if "trump_visit" not in lowered:
            continue
        if "/creator/" in lowered or "\\creator\\" in str(path).lower():
            continue
        platform = _platform_from_path(path)
        kind = _source_kind_from_path(path)
        if platform in platforms and kind in {"post", "comment"}:
            files.append(path)
    return sorted(files)


def _read_jsonl(path: Path, *, platform: str, kind: str) -> tuple[list[dict[str, Any]], SourceFileRecord]:
    rows = []
    line_count = 0
    failed_count = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            line_count += 1
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                failed_count += 1
                continue
            if isinstance(value, dict):
                rows.append(value)
            else:
                failed_count += 1
    return rows, SourceFileRecord(
        path=path.resolve(),
        platform=platform,
        kind=kind,
        line_count=line_count,
        loaded_count=len(rows),
        failed_count=failed_count,
        sha256=digest.hexdigest(),
    )


def _normalize_post(row: dict[str, Any], *, platform: str, event_id: str, source_path: Path) -> dict[str, Any]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    raw_user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    post_id = _first_text(row, "post_id", "note_id", "aweme_id", "id") or _text(raw.get("id"))
    timestamp = _timestamp_iso(
        row.get("timestamp")
        or row.get("create_date_time")
        or row.get("create_time")
        or row.get("time")
        or raw.get("created_at")
    )
    content = _join_text(
        row.get("content"),
        row.get("title"),
        row.get("desc"),
        raw.get("text"),
        raw.get("status_title"),
    )
    url = _first_text(row, "url", "note_url", "aweme_url", "source_url") or _nested_text(raw, ("page_info", "page_url"))
    source_keyword = _text(row.get("source_keyword"))
    return _strip_empty(
        {
            "event_id": event_id,
            "platform": platform,
            "post_id": post_id,
            "author_id": _first_text(row, "author_id", "user_id", "account_id") or _text(raw_user.get("id")),
            "author_name": _first_text(row, "author_name", "nickname") or _text(raw_user.get("screen_name")),
            "timestamp": timestamp,
            "content": content,
            "url": url,
            "hashtags": _hashtags(row),
            "keywords": [source_keyword] if source_keyword else [],
            "source_keyword": source_keyword,
            "like_count": _first_text(row, "liked_count", "like_count"),
            "comment_count": _first_text(row, "comments_count", "comment_count"),
            "share_count": _first_text(row, "shared_count", "share_count"),
            "crawl_job_id": _source_id(source_path),
            "crawl_metadata": _crawl_metadata(row, source_path=source_path, source_kind="post"),
        }
    )


def _normalize_comment(row: dict[str, Any], *, platform: str, event_id: str, source_path: Path) -> dict[str, Any]:
    post_id = _first_text(row, "post_id", "note_id", "aweme_id")
    comment_id = _first_text(row, "comment_id", "id")
    parent_comment_id = _text(row.get("parent_comment_id"))
    reply_to = "" if parent_comment_id in {"", "0", comment_id} else parent_comment_id
    return _strip_empty(
        {
            "event_id": event_id,
            "platform": platform,
            "comment_id": comment_id,
            "post_id": post_id,
            "author_id": _first_text(row, "author_id", "user_id", "account_id"),
            "author_name": _first_text(row, "author_name", "nickname"),
            "timestamp": _timestamp_iso(row.get("timestamp") or row.get("create_date_time") or row.get("create_time")),
            "content": _join_text(row.get("content"), row.get("text")),
            "reply_to": reply_to,
            "discussion_id": post_id,
            "like_count": _first_text(row, "comment_like_count", "like_count"),
            "crawl_job_id": _source_id(source_path),
            "crawl_metadata": _crawl_metadata(row, source_path=source_path, source_kind="comment"),
        }
    )


def _build_snapshots(
    *,
    event_id: str,
    platforms: tuple[str, ...],
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> dict[str, Any]:
    core_window = TimeWindow(start=DEFAULT_CORE_WINDOW[0], end=DEFAULT_CORE_WINDOW[1])
    context_window = TimeWindow(start=DEFAULT_CONTEXT_WINDOW[0], end=DEFAULT_CONTEXT_WINDOW[1])
    snapshots: dict[str, Any] = {}
    for platform in platforms:
        platform_posts = [row for row in posts if row.get("platform") == platform]
        platform_comments = [row for row in comments if row.get("platform") == platform]
        if platform_posts:
            snapshots[platform] = build_event_snapshot(
                event_id=f"{event_id}_{platform}",
                posts=platform_posts,
                comments=platform_comments,
                core_window=core_window,
                context_window=context_window,
            )
    if posts:
        snapshots["combined"] = build_event_snapshot(
            event_id=f"{event_id}_combined",
            posts=posts,
            comments=comments,
            core_window=core_window,
            context_window=context_window,
        )
    return snapshots


def _select_snapshots(snapshots: dict[str, Any], *, scope: str) -> dict[str, Any]:
    if scope == "all":
        return snapshots
    if scope == "combined":
        return {"combined": snapshots["combined"]} if "combined" in snapshots else {}
    return {name: snapshot for name, snapshot in snapshots.items() if name != "combined"}


def _run_snapshot(
    *,
    coordination_discover: Any,
    snapshot_name: str,
    snapshot: Any,
    artifact_dir: Path | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    config = coordination_discover.TemporalMAGNNConfig(
        embedding_dim=args.embedding_dim,
        epochs=args.epochs,
        negative_ratio=args.negative_ratio,
        device=args.device,
        min_learned_edge_score=args.min_learned_edge_score,
        require_leiden=not args.allow_non_leiden_exploration,
    )
    started = time.time()
    discovery = coordination_discover.run_dynamic_discover(
        coordination_discover.DynamicDiscoverRequest(
            snapshot=snapshot,
            artifact_dir=str(artifact_dir) if artifact_dir is not None else None,
            model_config=config,
            source_dataset=snapshot_name,
            source_event=snapshot.event_id,
        )
    )
    detect_rows = [
        {"score": edge.get("learned_score")}
        for edge in discovery.learned_edge_graph.get("edges", [])
    ]
    detect = coordination_discover.run_detect_validation(
        coordination_discover.DetectValidationRequest(rows=detect_rows),
        discovery=discovery,
    )
    exported = coordination_discover.export_coordination_result(discovery, detect=detect)
    coordination_result = (
        exported
        if getattr(args, "include_full_results", False)
        else _compact_coordination_result(exported)
    )
    return {
        "snapshot_name": snapshot_name,
        "runtime_seconds": round(time.time() - started, 3),
        "snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "event_id": snapshot.event_id,
            "platforms": list(snapshot.platforms),
            "data_fingerprint": snapshot.data_fingerprint,
            "quality_report": snapshot.quality_report.model_dump(mode="json"),
        },
        "v1_like_baseline": _v1_like_baseline(discovery),
        "v2_optimization": _v2_optimization(discovery),
        "detect_validation": detect.to_dict(),
        "coordination_result": coordination_result,
        "artifact_dir": str(artifact_dir) if artifact_dir is not None else None,
    }


def _compact_coordination_result(result: dict[str, Any]) -> dict[str, Any]:
    audit = dict(result.get("audit_metrics") or {})
    process = dict(audit.get("process_causal_experiment") or {})
    return {
        "status": result.get("status"),
        "technology": result.get("technology"),
        "model_version": result.get("model_version"),
        "model_role": result.get("model_role"),
        "detect_role": result.get("detect_role"),
        "summary": result.get("summary", {}),
        "evidence_coverage": result.get("evidence_coverage", {}),
        "attention": result.get("attention", {}),
        "dynamic_community_summary": dict(result.get("dynamic_communities", {})).get("summary", {}),
        "process_causal_experiment": {
            "status": process.get("status"),
            "role": process.get("role"),
            "claim_boundary": process.get("claim_boundary"),
            "process_motifs": list(process.get("process_motifs") or [])[:25],
            "causal_tests": process.get("causal_tests", {}),
        },
        "communities_preview": list(result.get("communities") or [])[:20],
        "account_risk_tiers_preview": list(result.get("account_risk_tiers") or [])[:50],
        "abstain": result.get("abstain"),
        "fallback": result.get("fallback"),
        "fallback_reason": result.get("fallback_reason"),
        "error": result.get("error"),
    }


def _v1_like_baseline(discovery: Any) -> dict[str, Any]:
    graph = discovery.evidence_graph
    learned = discovery.learned_edge_graph
    return {
        "role": "aggregate_account_object_baseline",
        "account_count": len(graph.get("accounts", [])),
        "evidence_object_count": len(graph.get("objects", [])),
        "account_object_edge_count": len(graph.get("edges", [])),
        "static_pair_edge_count": len(learned.get("edges", [])),
        "static_community_count": len(discovery.communities),
    }


def _v2_optimization(discovery: Any) -> dict[str, Any]:
    graph = discovery.evidence_graph
    dynamic = discovery.dynamic_communities
    audit = discovery.audit_metrics
    process = dict(audit.get("process_causal_experiment") or {})
    text_embedding = dict(audit.get("model_input", {}).get("text_embedding") or {})
    coverage = dict(audit.get("evidence_coverage") or {})
    return {
        "priority_order": [
            "1_evidence_directed_weighted_multigraph",
            "2_dynamic_community_lineage",
            "4_representation_and_detect_validation_boundary",
            "6_process_motif_exploratory_branch",
        ],
        "account_multigraph_edge_count": len(graph.get("account_edges", [])),
        "higher_order_edge_count": coverage.get("higher_order_edge_count", 0),
        "account_edge_projection_policy": coverage.get("account_edge_projection_policy", {}),
        "dynamic_window_graph_count": dynamic.get("summary", {}).get("window_graph_count", 0),
        "lineage_count": dynamic.get("summary", {}).get("lineage_count", 0),
        "membership_transition_count": dynamic.get("summary", {}).get("membership_transition_count", 0),
        "archetype_counts": dynamic.get("archetype_counts", {}),
        "text_embedding": text_embedding,
        "process_motif_count": len(process.get("process_motifs") or []),
        "process_role": process.get("role"),
        "process_status": process.get("status"),
    }


def _summary_row(record: dict[str, Any]) -> dict[str, Any]:
    quality = record["snapshot"]["quality_report"]
    baseline = record["v1_like_baseline"]
    optimized = record["v2_optimization"]
    detect = record["detect_validation"]
    return {
        "snapshot_name": record["snapshot_name"],
        "status": record["coordination_result"].get("status"),
        "quality_status": quality.get("status"),
        "core_posts": quality.get("core_posts"),
        "context_comments": quality.get("context_comments"),
        "account_count": baseline["account_count"],
        "evidence_object_count": baseline["evidence_object_count"],
        "account_object_edge_count": baseline["account_object_edge_count"],
        "static_pair_edge_count": baseline["static_pair_edge_count"],
        "static_community_count": baseline["static_community_count"],
        "account_multigraph_edge_count": optimized["account_multigraph_edge_count"],
        "higher_order_edge_count": optimized["higher_order_edge_count"],
        "dynamic_window_graph_count": optimized["dynamic_window_graph_count"],
        "lineage_count": optimized["lineage_count"],
        "membership_transition_count": optimized["membership_transition_count"],
        "process_motif_count": optimized["process_motif_count"],
        "text_embedding_status": optimized["text_embedding"].get("status", "missing"),
        "detect_status": detect.get("status"),
        "runtime_seconds": record["runtime_seconds"],
    }


def _effectiveness_summary(
    *,
    manifest: dict[str, Any],
    inventory: dict[str, Any],
    summary_rows: list[dict[str, Any]],
    result_records: list[dict[str, Any]],
) -> dict[str, Any]:
    cap_report = inventory.get("cap_report") or {}
    uncapped = (
        (cap_report.get("posts") or {}).get("mode") == "uncapped"
        and (cap_report.get("comments") or {}).get("mode") == "uncapped"
    )
    has_combined = any(row.get("snapshot_name") == "combined" for row in summary_rows)
    comment_cap_value = int(((cap_report.get("comments") or {}).get("max_per_platform") or 0))
    if uncapped and has_combined:
        experiment_scope = "full_all_snapshots"
    elif uncapped:
        experiment_scope = "uncapped_per_platform"
    elif has_combined:
        experiment_scope = "bounded_combined_validation"
    elif len(summary_rows) >= 3 and comment_cap_value >= 3000:
        experiment_scope = "budgeted_per_platform_matrix"
    else:
        experiment_scope = "sampled_smoke"

    by_snapshot = []
    for row in summary_rows:
        baseline_edges = int(row.get("account_object_edge_count") or 0)
        multigraph_edges = int(row.get("account_multigraph_edge_count") or 0)
        higher_order_edges = int(row.get("higher_order_edge_count") or 0)
        window_count = int(row.get("dynamic_window_graph_count") or 0)
        lineage_count = int(row.get("lineage_count") or 0)
        transition_count = int(row.get("membership_transition_count") or 0)
        process_count = int(row.get("process_motif_count") or 0)
        detect_status = str(row.get("detect_status") or "")
        by_snapshot.append(
            {
                "snapshot_name": row.get("snapshot_name"),
                "quality_status": row.get("quality_status"),
                "baseline_account_object_edges": baseline_edges,
                "optimized_account_multigraph_edges": multigraph_edges,
                "multigraph_coverage_ratio": _safe_ratio(multigraph_edges, baseline_edges),
                "evidence_multigraph_gate": multigraph_edges > 0,
                "higher_order_gate": higher_order_edges > 0,
                "dynamic_window_gate": window_count > 0,
                "lineage_gate": lineage_count > 0,
                "membership_transition_gate": transition_count > 0,
                "detect_boundary_gate": detect_status in {"missing_labels", "ok"},
                "detect_status": detect_status,
                "process_exploratory_gate": process_count > 0,
                "process_motif_count": process_count,
            }
        )

    gates = {
        "evidence_multigraph": all(item["evidence_multigraph_gate"] for item in by_snapshot) if by_snapshot else False,
        "higher_order_co_evidence": all(item["higher_order_gate"] for item in by_snapshot) if by_snapshot else False,
        "dynamic_communities": all(
            item["dynamic_window_gate"] and item["lineage_gate"] and item["membership_transition_gate"]
            for item in by_snapshot
        )
        if by_snapshot
        else False,
        "detect_abstain_boundary": all(item["detect_status"] == "missing_labels" for item in by_snapshot) if by_snapshot else False,
        "process_motif_boundary": all(_process_is_exploratory(record) for record in result_records) if result_records else False,
    }
    core_gate_names = (
        "evidence_multigraph",
        "higher_order_co_evidence",
        "dynamic_communities",
        "detect_abstain_boundary",
        "process_motif_boundary",
    )
    core_gates_passed = all(gates[name] for name in core_gate_names)
    overall = "effective_for_discovery_case_study" if core_gates_passed else "needs_followup"
    if experiment_scope == "budgeted_per_platform_matrix" and core_gates_passed:
        overall = "effective_for_budgeted_discovery_case_study"
    elif experiment_scope == "bounded_combined_validation" and core_gates_passed:
        overall = "effective_for_bounded_combined_validation"
    elif experiment_scope == "sampled_smoke":
        overall = "effective_for_sampled_smoke"

    return {
        "schema": "cogguard.coordination_discover.local_effectiveness.v1",
        "experiment_scope": experiment_scope,
        "overall_conclusion": overall,
        "claim_boundary": dict(manifest.get("claim_boundary") or {}),
        "cap_report": cap_report,
        "snapshot_count": len(summary_rows),
        "raw_loaded": dict(inventory.get("raw_loaded") or {}),
        "raw_loaded_by_platform": dict(inventory.get("raw_loaded_by_platform") or {}),
        "gates": gates,
        "by_snapshot": by_snapshot,
        "interpretation": [
            "Directed weighted account multigraph effectiveness is assessed as evidence coverage, not supervised accuracy.",
            "Dynamic community effectiveness is assessed by window graphs, lineage, and membership transitions.",
            "Detect effectiveness on the local Trump dataset is a boundary check: missing labels must produce abstain/missing_labels.",
            "Process motifs are counted only as exploratory analyst hypotheses and remain non-claimable causal evidence.",
        ],
        "remaining_research_requirements": [
            "Public labeled Detect data for AUPRC, MaxF1, ECE, calibration, and abstain evaluation.",
            "Precomputed text embeddings for with_lm versus without_lm ablation.",
            "Cross-event validation before generalization claims.",
        ],
    }


def _process_is_exploratory(record: dict[str, Any]) -> bool:
    optimized = record.get("v2_optimization") or {}
    compact = record.get("coordination_result") or {}
    process = compact.get("process_causal_experiment") or {}
    causal_tests = process.get("causal_tests") or {}
    claim_boundary = str(process.get("claim_boundary") or "")
    return (
        optimized.get("process_role") == "exploratory_non_claimable"
        and (
            process.get("claim_boundary") in {None, "exploratory_non_claimable"}
            or ("descriptive" in claim_boundary and "separate protocol" in claim_boundary)
        )
        and causal_tests.get("status") in {None, "not_run"}
    )


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _dataset_inventory(
    *,
    rows: LocalRows,
    data_root: Path,
    post_cap_report: dict[str, Any],
    comment_cap_report: dict[str, Any],
    snapshots: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_boundary": "offline local JSONL experiment input; not a system runtime dependency",
        "data_root": str(data_root),
        "source_files": [record.to_dict(data_root) for record in rows.source_files],
        "raw_loaded": {
            "posts": len(rows.posts),
            "comments": len(rows.comments),
        },
        "raw_loaded_by_platform": {
            "posts": _count_by_platform(rows.posts),
            "comments": _count_by_platform(rows.comments),
        },
        "cap_report": {
            "posts": post_cap_report,
            "comments": comment_cap_report,
        },
        "snapshots": {
            name: {
                "event_id": snapshot.event_id,
                "platforms": list(snapshot.platforms),
                "post_count": len(snapshot.posts),
                "comment_count": len(snapshot.comments),
                "quality_report": snapshot.quality_report.model_dump(mode="json"),
            }
            for name, snapshot in snapshots.items()
        },
    }


def _report_markdown(
    manifest: dict[str, Any],
    inventory: dict[str, Any],
    summary_rows: list[dict[str, Any]],
    effectiveness: dict[str, Any],
) -> str:
    lines = [
        "# CoordinationDiscover Local Discover/Detect Report",
        "",
        "## Boundary",
        "",
        f"- Discovery role: `{manifest['claim_boundary']['discovery']}`",
        f"- Detect role: `{manifest['claim_boundary']['detect']}`",
        f"- Process motif role: `{manifest['claim_boundary']['process_motifs']}`",
        f"- Data source: `{inventory['source_boundary']}`",
        "",
        "## Optimization Priority",
        "",
        "1. Evidence graph v2: directed weighted multigraph plus higher-order co-evidence.",
        "2. Dynamic communities: centered overlapping windows, lineage, transitions, and stability.",
        "3. Representation/Detect boundary: precomputed text embeddings only; missing labels force Detect abstain.",
        "4. Process motifs: descriptive branch only, non-claimable without separate causal validation.",
        "",
        "## Dataset",
        "",
        f"- Raw normalized posts: `{inventory['raw_loaded']['posts']}`",
        f"- Raw normalized comments: `{inventory['raw_loaded']['comments']}`",
        f"- Source files: `{len(inventory['source_files'])}`",
        f"- Raw posts by platform: `{inventory.get('raw_loaded_by_platform', {}).get('posts', {})}`",
        f"- Raw comments by platform: `{inventory.get('raw_loaded_by_platform', {}).get('comments', {})}`",
        "",
        "## Results",
        "",
        _markdown_table(summary_rows),
        "",
        "## Effectiveness Summary",
        "",
        f"- Experiment scope: `{effectiveness['experiment_scope']}`",
        f"- Overall conclusion: `{effectiveness['overall_conclusion']}`",
        f"- Evidence multigraph gate: `{effectiveness['gates']['evidence_multigraph']}`",
        f"- Higher-order co-evidence gate: `{effectiveness['gates']['higher_order_co_evidence']}`",
        f"- Dynamic community gate: `{effectiveness['gates']['dynamic_communities']}`",
        f"- Detect abstain boundary gate: `{effectiveness['gates']['detect_abstain_boundary']}`",
        f"- Process motif boundary gate: `{effectiveness['gates']['process_motif_boundary']}`",
        "",
        "## Claim Boundary",
        "",
        "- The local Trump-visit data has no analyst labels, so Detect outputs are `missing_labels` evidence-boundary checks only.",
        "- Mojibake text is not used to synthesize semantic embeddings; text LM features are consumed only when precomputed vectors exist.",
        "- The process branch reports motifs for analyst hypotheses and must not be described as causal detection.",
        "",
    ]
    return "\n".join(lines)


def _cap_by_platform(
    rows: list[dict[str, Any]],
    *,
    max_per_platform: int,
    id_field: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if max_per_platform <= 0:
        return rows, {"mode": "uncapped", "max_per_platform": 0, "dropped_by_platform": {}}
    selected: list[dict[str, Any]] = []
    dropped: dict[str, int] = {}
    by_platform: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_platform.setdefault(str(row.get("platform") or "unknown"), []).append(row)
    for platform, platform_rows in sorted(by_platform.items()):
        ordered = sorted(platform_rows, key=lambda item: (_text(item.get("timestamp")), _text(item.get(id_field))))
        if len(ordered) <= max_per_platform:
            selected.extend(ordered)
            continue
        selected.extend(_take_evenly(ordered, max_per_platform))
        dropped[platform] = len(ordered) - max_per_platform
    return selected, {"mode": "temporal_even_sample", "max_per_platform": max_per_platform, "dropped_by_platform": dropped}


def _count_by_platform(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        platform = str(row.get("platform") or "unknown")
        counts[platform] = counts.get(platform, 0) + 1
    return dict(sorted(counts.items()))


def _take_evenly(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit >= len(rows):
        return rows
    if limit <= 0:
        return []
    step = len(rows) / limit
    indexes = {min(len(rows) - 1, int(index * step)) for index in range(limit)}
    return [row for index, row in enumerate(rows) if index in indexes]


def _load_coordination_discover() -> Any:
    module_name = "_script_cogguard_coordination_discover"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    package_dir = SYSTEM_ROOT / "research" / "coordination_discover"
    spec = importlib.util.spec_from_file_location(
        module_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load CoordinationDiscover package from {package_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _output_dir(value: str) -> Path:
    if value.strip():
        return Path(value).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return SYSTEM_ROOT / "output" / "coordination_discover_detect_local" / run_id


def _platform_from_path(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    for platform in ("weibo", "douyin", "xhs"):
        if platform in parts:
            return platform
    return "unknown"


def _source_kind_from_path(path: Path) -> str:
    name = path.name.lower()
    if "comment" in name:
        return "comment"
    if "content" in name or "post_detail" in name or "post_details" in name:
        return "post"
    return "unknown"


def _timestamp_iso(value: Any) -> str:
    timestamp = _parse_timestamp(value)
    return timestamp.astimezone(timezone.utc).isoformat() if timestamp else ""


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _from_epoch(float(value))
    text = str(value).strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        numeric = None
    if numeric is not None:
        return _from_epoch(numeric)
    for fmt in ("%a %b %d %H:%M:%S %z %Y",):
        try:
            return datetime.strptime(text, fmt).astimezone(timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _from_epoch(value: float) -> datetime:
    seconds = value / 1000.0 if value > 10_000_000_000 else value
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def _hashtags(row: dict[str, Any]) -> list[str]:
    values = []
    for key in ("hashtag", "hashtags", "topic", "topics", "tags", "tag_list"):
        values.extend(_flatten_text_values(row.get(key)))
    return _dedupe([item for value in values for item in _split_tag_text(value)])


def _split_tag_text(value: Any) -> list[str]:
    text = _text(value)
    if not text:
        return []
    if "," in text:
        return [_text(item) for item in text.split(",") if _text(item)]
    return [_text(item) for item in text.split() if _text(item)] or [text]


def _flatten_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(_flatten_text_values(item))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for item in value:
            values.extend(_flatten_text_values(item))
        return values
    return [str(value)]


def _crawl_metadata(row: dict[str, Any], *, source_path: Path, source_kind: str) -> dict[str, Any]:
    metadata = {
        "source_id": _source_id(source_path),
        "source_file": _safe_relative(source_path.resolve(), REPO_ROOT),
        "source_kind": source_kind,
        "offline_input_only": True,
    }
    for field in PRECOMPUTED_TEXT_EMBEDDING_FIELDS:
        if isinstance(row.get(field), list):
            metadata["precomputed_text_embedding_field"] = field
            break
    return metadata


def _source_id(source_path: Path) -> str:
    try:
        relative = source_path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        relative = source_path.resolve()
    return hashlib.sha1(str(relative).encode("utf-8")).hexdigest()[:12]


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        text = _text(row.get(key))
        if text:
            return text
    return ""


def _nested_text(value: dict[str, Any], keys: tuple[str, ...]) -> str:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return _text(current)


def _join_text(*values: Any) -> str:
    return " ".join(_text(value) for value in values if _text(value)).strip()


def _strip_empty(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if value not in ("", [], {}, None)}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    rows = []
    for value in values:
        text = _text(value)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        rows.append(text)
    return rows


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows_"
    columns = [
        "snapshot_name",
        "quality_status",
        "core_posts",
        "context_comments",
        "account_count",
        "account_object_edge_count",
        "account_multigraph_edge_count",
        "higher_order_edge_count",
        "dynamic_window_graph_count",
        "lineage_count",
        "membership_transition_count",
        "process_motif_count",
        "detect_status",
    ]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()
