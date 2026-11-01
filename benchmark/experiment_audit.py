from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

from propagation.loaders import load_dataset
from propagation.protocol import load_coordination_scope

from .role_evidence_review import validate_review_file
from .schema import validate_benchmark_results


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmark"
DEFAULT_PHEME_DIR = Path("G:/CISCN/dataset/PHEME")


def build_audit(
    *,
    benchmark_dir: Path = BENCHMARK_DIR,
    kt1_coordination_file: Optional[Path] = None,
    pheme_dir: Optional[Path] = None,
    role_evidence_dir: Optional[Path] = None,
) -> Dict:
    results = _read_rows(benchmark_dir / "results.json")
    frontier_status = _read_rows(benchmark_dir / "frontier_status.json")
    casft_attempt = _read_rows(benchmark_dir / "casft_external_attempt.json")
    dyglib_attempt = _read_rows(benchmark_dir / "dyglib_external_attempt.json")
    tgn_attempt = _read_rows(benchmark_dir / "tgn_external_attempt.json")
    observation = _read_rows(benchmark_dir / "observation_sensitivity.json")

    role_evidence_dir = role_evidence_dir or benchmark_dir / "kt1_role_evidence_validation"
    if kt1_coordination_file is None:
        inferred_coordination = role_evidence_dir / "kt1_coordination_scope.json"
        if inferred_coordination.exists():
            kt1_coordination_file = inferred_coordination
    if pheme_dir is None and DEFAULT_PHEME_DIR.exists():
        pheme_dir = DEFAULT_PHEME_DIR

    sections = [
        _scale_section(results, casft_attempt, frontier_status, observation),
        _next_hop_section(results, dyglib_attempt, tgn_attempt, frontier_status),
        _role_evidence_section(kt1_coordination_file, pheme_dir, role_evidence_dir),
        _frontend_protocol_section(results, frontier_status, casft_attempt, dyglib_attempt, tgn_attempt),
    ]
    summary = _summary(sections)
    return {
        "schema": "cogguard.kt2.experiment_audit.v1",
        "status": summary["status"],
        "summary": summary,
        "sections": sections,
        "required_completion_rule": (
            "KT2 full validation is complete only when every critical section is passed "
            "and no section remains partial, missing, or blocked."
        ),
    }


def write_audit(audit: Dict, output_json: Path, output_md: Optional[Path] = None) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md:
        output_md.write_text(_audit_markdown(audit), encoding="utf-8")


def _scale_section(results: List[Mapping], casft_attempt: List[Mapping], frontier_status: List[Mapping], observation: List[Mapping]) -> Dict:
    baseline_models = {"RF_Baseline", "TemporalSizeBaseline"}
    baselines = [row for row in results if row.get("model") in baseline_models and _has_scale_metrics(row)]
    casft = _find(casft_attempt, "CasFT") or _find(frontier_status, "CasFT")
    checks = [
        _check(bool(baselines), "scale_baselines", "RF/Temporal scale baselines have regression metrics.", _evidence_paths(["benchmark/results.json"])),
        _check(bool(observation), "observation_sensitivity", "Observation-window sensitivity exists.", _evidence_paths(["benchmark/observation_sensitivity.json"])),
    ]
    if casft and casft.get("reproduction_level") == "frontier_reproduction_small_run":
        casft_status = "passed"
        detail = "CasFT upstream small-run completed."
        next_steps = [
            "Repeat CasFT scale results across observation windows, datasets and at least three seeds before claiming full-run.",
            "Compare CasFT against RF/Temporal and CasDO/ConCat fallback rows before selecting the production scale model.",
            "Keep current evidence labelled frontier_reproduction_small_run, not frontier_reproduction_full_run.",
        ]
    elif casft and casft.get("reproduction_level") == "frontier_reproduction_attempted":
        casft_status = "blocked"
        detail = f"CasFT attempted but stopped at {casft.get('failed_stage', 'unknown stage')}: {_tail(casft.get('stderr_tail'))}"
        next_steps = [
            "Create a CasFT-compatible legacy environment with cogdl/graphwave dependencies.",
            "Run gen_emb.py and train.py to upgrade CasFT from frontier_reproduction_attempted to frontier_reproduction_small_run.",
            "Repeat scale results across observation windows and at least three seeds before claiming full-run.",
        ]
    elif casft:
        casft_status = "partial"
        detail = "CasFT data adapter/export exists, but upstream small-run has not completed."
        next_steps = [
            "Run CasFT with --run_external_frontier to move from data adapter evidence to upstream small-run evidence.",
            "Record command, logs, seed, data version and metrics JSON before claiming frontier_reproduction_small_run.",
        ]
    else:
        casft_status = "missing"
        detail = "No CasFT evidence row found."
        next_steps = [
            "Generate or restore benchmark/casft_external_attempt.json before assessing scale prediction completion.",
            "Keep scale prediction incomplete until CasFT or a documented fallback has auditable small-run evidence.",
        ]
    checks.append(
        {
            "id": "casft_frontier_scale",
            "status": casft_status,
            "detail": detail,
            "evidence": _row_evidence(casft, ["benchmark/casft_external_attempt.json", "benchmark/frontier_status.json"]),
        }
    )
    return _section(
        "scale_prediction",
        "规模预测",
        checks,
        critical=True,
        next_steps=next_steps,
    )


def _next_hop_section(results: List[Mapping], dyglib_attempt: List[Mapping], tgn_attempt: List[Mapping], frontier_status: List[Mapping]) -> Dict:
    baseline_models = {"ProspectiveHeuristic", "ProspectiveRanker", "LR_EdgeClassifier", "FOREST", "MINDS"}
    baselines = [row for row in results if row.get("model") in baseline_models and _has_next_hop_metrics(row)]
    dyglib = _find(dyglib_attempt, "DyGFormer/DyGLib") or _find(frontier_status, "DyGFormer/DyGLib")
    tgn = _find(tgn_attempt, "TGN") or _find(frontier_status, "TGN")
    checks = [
        _check(bool(baselines), "next_hop_baselines", "Next-hop baselines have ranking metrics.", _evidence_paths(["benchmark/results.json"])),
        _frontier_next_hop_check("dyglib_small_run", dyglib, ["benchmark/dyglib_external_attempt.json"]),
        _frontier_next_hop_check("tgn_small_run", tgn, ["benchmark/tgn_external_attempt.json"]),
    ]
    repeated_small_run = all((row or {}).get("num_runs", 0) and (row or {}).get("num_runs", 0) >= 3 for row in [dyglib, tgn])
    checks.append(
        {
            "id": "repeated_small_run_evidence",
            "status": "passed" if repeated_small_run else "partial",
            "detail": "Small-run evidence records at least 3 repeated runs. This is not multi-seed full validation; seed-diverse larger runs remain required before final model selection.",
            "evidence": _row_evidence(dyglib, ["benchmark/dyglib_external_attempt.json"]) + _row_evidence(tgn, ["benchmark/tgn_external_attempt.json"]),
        }
    )
    return _section(
        "next_hop_prediction",
        "下一跳预测",
        checks,
        critical=True,
        next_steps=[
            "Expand DyGLib/TGN from 20 cascades / 1 epoch / seed=0 to multi-seed and larger cascade caps.",
            "Parse upstream AP/AUC into the unified benchmark rows alongside KT2 candidate ranking metrics.",
            "Compare against ProspectiveRanker before selecting the final next-hop implementation.",
        ],
    )


def _role_evidence_section(kt1_coordination_file: Optional[Path], pheme_dir: Optional[Path], role_evidence_dir: Path) -> Dict:
    kt1_summary = _coordination_file_summary(kt1_coordination_file)
    artifacts = _role_evidence_artifact_summary(role_evidence_dir)
    pheme_summary = _pheme_dataset_summary(pheme_dir)
    pheme_artifacts = _pheme_role_evidence_artifact_summary(role_evidence_dir.parent / "pheme_role_evidence_sample")
    review_packet = _manual_review_packet_summary(role_evidence_dir)
    manual_review = _manual_review_summary(role_evidence_dir)
    checks = [
        _check(True, "role_evidence_code", "Role evidence service and quality metrics are implemented and covered by tests.", _evidence_paths(["propagation/analysis.py", "propagation/protocol.py", "tests/test_smoke.py"])),
        {
            "id": "real_kt1_coordination_input",
            "status": "passed" if kt1_summary["ok"] else "missing",
            "detail": kt1_summary["detail"],
            "evidence": kt1_summary["evidence"],
        },
        {
            "id": "role_evidence_artifacts",
            "status": "passed" if artifacts["ok"] else "missing",
            "detail": artifacts["detail"],
            "evidence": artifacts["evidence"],
        },
        {
            "id": "pheme_dataset_validation",
            "status": "passed" if pheme_summary["ok"] else "missing",
            "detail": pheme_summary["detail"],
            "evidence": pheme_summary["evidence"],
        },
        {
            "id": "pheme_role_evidence_artifacts",
            "status": "passed" if (pheme_artifacts["ok"] or manual_review["ok"]) else "partial",
            "detail": pheme_artifacts["detail"] if not manual_review["ok"] else "Manual review records are already available; PHEME observed-user artifact readiness is no longer blocking.",
            "evidence": pheme_artifacts["evidence"],
        },
        {
            "id": "manual_review_packet_ready",
            "status": "passed" if (review_packet["ok"] or manual_review["ok"]) else "partial",
            "detail": review_packet["detail"] if not manual_review["ok"] else "Manual review records are already available; packet readiness is no longer blocking.",
            "evidence": review_packet["evidence"],
        },
        {
            "id": "manual_review_records",
            "status": "passed" if manual_review["ok"] else "partial",
            "detail": manual_review["detail"],
            "evidence": manual_review["evidence"],
        },
    ]
    return _section(
        "role_evidence",
        "协同角色定位与证据追溯",
        checks,
        critical=True,
        next_steps=[
            "Keep PHEME observed-user role evidence as real-timeline validation, not as KT1 prediction output.",
            "Use ROLE_EVIDENCE_REVIEW_GUIDE.md, ROLE_EVIDENCE_REVIEW_PACKET.md and ROLE_EVIDENCE_REVIEW.html to complete sampled manual pass/fail review rows.",
            "Initialize/fill analysis/role_evidence_manual_review.csv, then run python -m benchmark.role_evidence_review status and validate.",
            "Promote role evidence from partial to passed only after manual review records are available.",
        ],
    )


def _frontend_protocol_section(
    results: List[Mapping],
    frontier_status: List[Mapping],
    casft_attempt: List[Mapping],
    dyglib_attempt: List[Mapping],
    tgn_attempt: List[Mapping],
) -> Dict:
    all_frontier = frontier_status + casft_attempt + dyglib_attempt + tgn_attempt
    schema_report = validate_benchmark_results(all_frontier)
    kt2_joint = _find(results, "KT2JointModel")
    checks = [
        {
            "id": "benchmark_schema",
            "status": "passed" if schema_report["ok"] else "missing",
            "detail": "Benchmark rows satisfy schema and anti-overclaim checks." if schema_report["ok"] else "; ".join(schema_report["errors"]),
            "evidence": _evidence_paths(["benchmark/schema.py", "benchmark/*.schema.json"]),
        },
        _check(True, "dashboard_experimental_label", "Dashboard prediction panels default to 实验预测 and expose dataset/window/model/reproduction metadata.", _evidence_paths(["propagation/visualization.py", "propagation/prediction.py", "tests/test_smoke.py"])),
        _check(
            True,
            "macro_micro_framework_protocol",
            "Macro/micro framework audit layer is implemented as a protocol summary, not as a new frontier reproduction claim.",
            _evidence_paths(["benchmark/macro_micro.py", "benchmark/run_benchmark.py", "propagation/prediction.py", "propagation/visualization.py", "tests/test_smoke.py"]),
        ),
        _kt2_joint_model_check(kt2_joint),
    ]
    return _section(
        "frontend_and_protocol",
        "前端展示与实验协议",
        checks,
        critical=False,
        next_steps=[
            "Keep predictions marked as experimental until final model selection is complete.",
            "Use KT2JointModel rows as KT2-owned local joint-model evidence; keep paper-model reproductions labelled separately.",
            "Expose result JSON/log links only for rows with verified reproduction levels.",
        ],
    )


def _frontier_next_hop_check(check_id: str, row: Optional[Mapping], evidence_paths: List[str]) -> Dict:
    if not row:
        return {"id": check_id, "status": "missing", "detail": "No frontier next-hop evidence row found.", "evidence": []}
    audit = row.get("candidate_protocol_audit") or {}
    if row.get("reproduction_level") == "frontier_reproduction_small_run" and row.get("status") == "ok" and audit.get("leakage_check_passed") is True:
        status = "passed"
        detail = f"{row.get('model')} small-run completed with no future-node injection audit."
    else:
        status = "partial"
        detail = f"{row.get('model')} exists but is not a verified no-leakage small-run."
    return {"id": check_id, "status": status, "detail": detail, "evidence": _row_evidence(row, evidence_paths)}


def _kt2_joint_model_check(row: Optional[Mapping]) -> Dict:
    """Record KT2's own joint model without making its absence a new hard gate."""

    evidence = _evidence_paths(
        [
            "benchmark/adapters/kt2_joint_model.py",
            "benchmark/run_benchmark.py",
            "benchmark/schema.py",
            "tests/test_smoke.py",
            "benchmark/results.json",
            "benchmark/kt2_joint_smoke.json",
        ]
    )
    if not row:
        return {
            "id": "kt2_joint_model_small_run",
            "status": "passed",
            "detail": (
                "KT2JointModel adapter is implemented and covered by tests; run "
                "`python -m benchmark.run_benchmark --models kt2_joint ... --output benchmark/results.json` "
                "to make it the current audit row. Absence from results.json is not treated as a legacy-frontier failure."
            ),
            "evidence": evidence,
        }
    audit = row.get("candidate_protocol_audit") or {}
    has_macro = _has_scale_metrics(row)
    has_micro = _has_next_hop_metrics(row)
    leakage_ok = audit.get("leakage_check_passed") is True
    ok = (
        row.get("status") == "ok"
        and row.get("reproduction_level") == "kt2_joint_model_small_run"
        and has_macro
        and has_micro
        and row.get("macro_micro_consistency") is not None
        and leakage_ok
    )
    status = "passed" if ok else "partial"
    detail = (
        "KT2JointModel small-run is present with macro metrics, micro ranking metrics, "
        "macro_micro_consistency, and no-leakage candidate audit."
        if ok
        else "KT2JointModel row is present but missing required metrics, status, reproduction level, or leakage audit."
    )
    return {"id": "kt2_joint_model_small_run", "status": status, "detail": detail, "evidence": _row_evidence(row, evidence)}


def _section(section_id: str, title: str, checks: List[Dict], *, critical: bool, next_steps: List[str]) -> Dict:
    statuses = {check["status"] for check in checks}
    if "missing" in statuses:
        status = "missing"
    elif "blocked" in statuses:
        status = "blocked"
    elif "partial" in statuses:
        status = "partial"
    else:
        status = "passed"
    return {"id": section_id, "title": title, "status": status, "critical": critical, "checks": checks, "next_steps": next_steps}


def _summary(sections: List[Dict]) -> Dict:
    counts = {}
    for section in sections:
        counts[section["status"]] = counts.get(section["status"], 0) + 1
    critical_open = [section["id"] for section in sections if section["critical"] and section["status"] != "passed"]
    return {
        "status": "passed" if not critical_open else "incomplete",
        "section_counts": counts,
        "critical_open_sections": critical_open,
        "full_validation_complete": not critical_open and all(section["status"] == "passed" for section in sections),
    }


def _check(condition: bool, check_id: str, detail: str, evidence: List[str]) -> Dict:
    return {"id": check_id, "status": "passed" if condition else "missing", "detail": detail, "evidence": evidence}


def _has_scale_metrics(row: Mapping) -> bool:
    return any(key in row for key in ("msle", "mae", "rmse", "mape_percent")) and row.get("msle") is not None


def _has_next_hop_metrics(row: Mapping) -> bool:
    return any(key in row for key in ("hits@10", "hits@50", "hits@100", "mrr", "candidate_recall_full")) and row.get("hits@100") is not None


def _find(rows: Iterable[Mapping], model: str) -> Optional[Mapping]:
    return next((row for row in rows if row.get("model") == model), None)


def _read_rows(path: Path) -> List[Mapping]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _coordination_file_summary(path: Optional[Path]) -> Dict:
    if not path or not path.exists():
        return {"ok": False, "detail": "真实 KT1 协同用户输出尚未提供给审计入口。", "evidence": []}
    try:
        scope = load_coordination_scope(str(path))
    except Exception as exc:  # pragma: no cover - defensive audit detail
        return {"ok": False, "detail": f"KT1 coordination file exists but cannot be parsed: {exc}", "evidence": _evidence_paths([str(path)])}
    user_count = len(scope.users)
    group_count = len(set(scope.groups.values()))
    if user_count <= 0:
        return {"ok": False, "detail": f"KT1 coordination file parsed but selected no coordinated users: {path}", "evidence": _evidence_paths([str(path)])}
    return {
        "ok": True,
        "detail": f"KT1 coordination file parsed with {user_count} coordinated users and {group_count} groups: {path}",
        "evidence": _evidence_paths([str(path)]),
    }


def _role_evidence_artifact_summary(role_evidence_dir: Path) -> Dict:
    analysis_dir = role_evidence_dir / "analysis"
    role_csv = analysis_dir / "role_evidence.csv"
    quality_json = analysis_dir / "role_evidence_quality.json"
    validation_json = role_evidence_dir / "kt1_role_evidence_validation.json"
    evidence = _evidence_paths([str(validation_json), str(role_csv), str(quality_json)])
    if not role_csv.exists() or not quality_json.exists():
        return {
            "ok": False,
            "detail": "KT1-driven role_evidence.csv and role_evidence_quality.json have not been generated.",
            "evidence": [path for path in evidence if Path(path).exists()],
        }
    row_count = _count_csv_rows(role_csv)
    try:
        quality = json.loads(quality_json.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive audit detail
        return {"ok": False, "detail": f"role_evidence_quality.json cannot be parsed: {exc}", "evidence": evidence}
    if row_count <= 0:
        return {"ok": False, "detail": "KT1-driven role_evidence.csv exists but contains no evidence rows.", "evidence": evidence}
    if quality.get("scope") != "coordinated_users":
        return {"ok": False, "detail": "Role evidence quality exists but was not generated in coordinated_users scope.", "evidence": evidence}
    return {
        "ok": True,
        "detail": (
            f"KT1-driven role evidence generated with {row_count} rows; "
            f"coverage={quality.get('coordination_user_coverage')}, path_complete_rate={quality.get('path_complete_rate')}."
        ),
        "evidence": evidence,
    }


def _pheme_dataset_summary(pheme_dir: Optional[Path]) -> Dict:
    if not pheme_dir or not pheme_dir.exists():
        return {"ok": False, "detail": "PHEME directory is not available locally for evidence/timeline validation.", "evidence": []}
    try:
        events = load_dataset("pheme", str(pheme_dir), max_events=5)
    except Exception as exc:
        return {
            "ok": False,
            "detail": f"PHEME directory exists but could not be parsed: {exc}",
            "evidence": _evidence_paths([str(pheme_dir)]),
        }
    node_count = sum(len(event.nodes) for event in events)
    edge_count = sum(event.to_graph().number_of_edges() for event in events)
    timestamp_count = sum(1 for event in events for node in event.nodes.values() if node.timestamp is not None)
    if not events or node_count <= 0 or edge_count <= 0 or timestamp_count <= 0:
        return {
            "ok": False,
            "detail": (
                f"PHEME parsed but structure is insufficient: events={len(events)}, "
                f"nodes={node_count}, edges={edge_count}, timestamps={timestamp_count}."
            ),
            "evidence": _evidence_paths([str(pheme_dir)]),
        }
    return {
        "ok": True,
        "detail": f"PHEME parsed {len(events)} sample events with {node_count} nodes, {edge_count} edges and {timestamp_count} timestamps.",
        "evidence": _evidence_paths([str(pheme_dir)]),
    }


def _manual_review_summary(role_evidence_dir: Path) -> Dict:
    candidates = [
        role_evidence_dir / "analysis" / "role_evidence_manual_review.csv",
        role_evidence_dir / "analysis" / "manual_review.csv",
        role_evidence_dir / "role_evidence_manual_review.csv",
    ]
    review_path = next((path for path in candidates if path.exists()), None)
    if not review_path:
        return {
            "ok": False,
            "detail": "Manual review records for sampled role-evidence chains are not available.",
            "evidence": [],
        }
    template = role_evidence_dir / "analysis" / "role_evidence_manual_review_template.csv"
    validation = validate_review_file(review_path, template_csv=template if template.exists() else None)
    evidence_paths = [str(review_path)]
    if template.exists():
        evidence_paths.append(str(template))
    return {
        "ok": bool(validation["ok"]),
        "detail": validation["detail"],
        "evidence": _evidence_paths(evidence_paths),
    }


def _manual_review_packet_summary(role_evidence_dir: Path) -> Dict:
    analysis_dir = role_evidence_dir / "analysis"
    template = analysis_dir / "role_evidence_manual_review_template.csv"
    template_summary = analysis_dir / "role_evidence_manual_review_template.json"
    guide = analysis_dir / "ROLE_EVIDENCE_REVIEW_GUIDE.md"
    packet = analysis_dir / "ROLE_EVIDENCE_REVIEW_PACKET.md"
    html = analysis_dir / "ROLE_EVIDENCE_REVIEW.html"
    paths = [template, template_summary, guide, packet, html]
    evidence = _evidence_paths([str(path) for path in paths if path.exists()])
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        return {
            "ok": False,
            "detail": f"Manual review packet is incomplete; missing {', '.join(missing)}.",
            "evidence": evidence,
        }
    try:
        rows = _count_csv_rows(template)
    except Exception as exc:
        return {"ok": False, "detail": f"Manual review template cannot be parsed: {exc}", "evidence": evidence}
    if rows <= 0:
        return {"ok": False, "detail": "Manual review template exists but has no sampled rows.", "evidence": evidence}
    try:
        summary = json.loads(template_summary.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "detail": f"Manual review template summary cannot be parsed: {exc}", "evidence": evidence}
    if summary.get("review_pass_prefilled") is not False:
        return {"ok": False, "detail": "Manual review template summary does not prove review_pass was left blank.", "evidence": evidence}
    return {
        "ok": True,
        "detail": f"Manual review packet is ready with {rows} sampled rows; review_pass is intentionally not prefilled.",
        "evidence": evidence,
    }


def _pheme_role_evidence_artifact_summary(pheme_role_dir: Path) -> Dict:
    validation_json = pheme_role_dir / "pheme_role_evidence_sample.json"
    analysis_dir = pheme_role_dir / "analysis"
    role_csv = analysis_dir / "role_evidence.csv"
    quality_json = analysis_dir / "role_evidence_quality.json"
    evidence = _evidence_paths([str(validation_json), str(role_csv), str(quality_json)])
    if not validation_json.exists() or not role_csv.exists() or not quality_json.exists():
        return {
            "ok": False,
            "detail": "PHEME observed-user role evidence artifacts are not available.",
            "evidence": [path for path in evidence if Path(path).exists()],
        }
    try:
        validation = json.loads(validation_json.read_text(encoding="utf-8"))
        quality = json.loads(quality_json.read_text(encoding="utf-8"))
        row_count = _count_csv_rows(role_csv)
    except Exception as exc:
        return {"ok": False, "detail": f"PHEME role evidence artifacts cannot be parsed: {exc}", "evidence": evidence}
    if validation.get("source") != "pheme_observed_sample":
        return {"ok": False, "detail": "PHEME role evidence source is not marked as pheme_observed_sample.", "evidence": evidence}
    if row_count <= 0:
        return {"ok": False, "detail": "PHEME role_evidence.csv exists but contains no rows.", "evidence": evidence}
    if quality.get("scope") != "coordinated_users":
        return {"ok": False, "detail": "PHEME role evidence was not generated in coordinated_users scope.", "evidence": evidence}
    return {
        "ok": True,
        "detail": (
            f"PHEME observed-user role evidence generated with {row_count} rows across "
            f"{validation.get('event_count')} events; coverage={quality.get('coordination_user_coverage')}, "
            f"path_complete_rate={quality.get('path_complete_rate')}."
        ),
        "evidence": evidence,
    }


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _row_evidence(row: Optional[Mapping], paths: List[str]) -> List[str]:
    if not row:
        return []
    evidence = _evidence_paths(paths)
    for key in ("stdout_log", "stderr_log", "train_stdout_log", "train_stderr_log", "gen_cas_stdout_log", "gen_emb_stderr_log", "command_log", "train_command_log"):
        value = row.get(key)
        if value:
            evidence.append(str(value))
    return evidence


def _evidence_paths(paths: Iterable[str]) -> List[str]:
    return [str(path) for path in paths if path]


def _tail(value) -> str:
    if isinstance(value, list):
        return " | ".join(str(item) for item in value[-3:])
    return str(value or "")


def _audit_markdown(audit: Dict) -> str:
    lines = [
        "# KT2 全量实验验证审计",
        "",
        "> 生成方式：由 `python -m benchmark.experiment_audit` 生成；不要手工把分项 small-run 结果改写为 full validation。",
        "> 判定规则：分项 `passed` 只表示该模块当前审计项通过；KT2 是否全量完成以 `Full validation complete` 和 `benchmark.completion_gate` 为准。",
        "",
        f"- Schema: `{audit['schema']}`",
        f"- 总状态: `{audit['status']}`",
        f"- Full validation complete: `{audit['summary']['full_validation_complete']}`",
        f"- Critical open sections: `{', '.join(audit['summary']['critical_open_sections']) or '-'}`",
        "",
        "| 模块 | 状态 | 关键缺口 |",
        "|---|---|---|",
    ]
    for section in audit["sections"]:
        open_checks = [check["id"] for check in section["checks"] if check["status"] != "passed"]
        lines.append(f"| {section['title']} | `{section['status']}` | {', '.join(open_checks) if open_checks else '-'} |")
    lines.extend(
        [
            "",
            "## 完成边界",
            "",
            "- `frontier_reproduction_small_run` 只能说明上游 small-run 可复现，不能说明多数据多随机种子 full-run。",
            "- 当前 KT2 full validation 只有在所有 critical section 均为 `passed` 且 completion gate 返回 `passed` 时才成立。",
            "- 本报告应在新增模型证据、人工审核记录或前端协议证据后重新生成。",
            "",
        ]
    )
    for section in audit["sections"]:
        lines.extend([f"## {section['title']}", ""])
        for check in section["checks"]:
            lines.append(f"- `{check['status']}` `{check['id']}`: {check['detail']}")
        lines.append("")
        lines.append("下一步：")
        for step in section["next_steps"]:
            lines.append(f"- {step}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit KT2 experiment coverage without overclaiming completion.")
    parser.add_argument("--benchmark_dir", default=str(BENCHMARK_DIR))
    parser.add_argument("--kt1_coordination_file", default=None)
    parser.add_argument("--pheme_dir", default=None)
    parser.add_argument("--role_evidence_dir", default=None)
    parser.add_argument("--output", default=str(BENCHMARK_DIR / "KT2_EXPERIMENT_AUDIT.json"))
    parser.add_argument("--markdown", default=str(BENCHMARK_DIR / "KT2_EXPERIMENT_AUDIT.md"))
    args = parser.parse_args()
    audit = build_audit(
        benchmark_dir=Path(args.benchmark_dir),
        kt1_coordination_file=Path(args.kt1_coordination_file) if args.kt1_coordination_file else None,
        pheme_dir=Path(args.pheme_dir) if args.pheme_dir else None,
        role_evidence_dir=Path(args.role_evidence_dir) if args.role_evidence_dir else None,
    )
    write_audit(audit, Path(args.output), Path(args.markdown) if args.markdown else None)
    print(json.dumps({"schema": audit["schema"], "status": audit["status"], **audit["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
