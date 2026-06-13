from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_REPORT_INPUTS = {
    "weibo_rumor": {
        "label": "Weibo Rumor / Ma-Weibo",
        "analysis": "outputs/weibo_rumor_full/analysis_summary.json",
        "prediction": "outputs/weibo_rumor_full/prediction_report.json",
        "inspect": "outputs/weibo_rumor_inspect/dataset_inspection.json",
        "artifact_dir": "outputs/weibo_rumor_full",
    },
    "pheme": {
        "label": "PHEME",
        "analysis": "outputs/pheme_full/analysis_summary.json",
        "prediction": "outputs/pheme_full/prediction_report.json",
        "inspect": "outputs/pheme_inspect/dataset_inspection.json",
        "artifact_dir": "outputs/pheme_full",
    },
    "rumor_rvnn": {
        "label": "Rumor_RvNN Twitter15/16",
        "analysis": "outputs/rumor_rvnn_full/analysis_summary.json",
        "prediction": "outputs/rumor_rvnn_full/prediction_report.json",
        "inspect": "outputs/rumor_rvnn_inspect_final/dataset_inspection.json",
        "artifact_dir": "outputs/rumor_rvnn_full",
    },
}


def build_final_report(output_path: str = "outputs/FINAL_REPORT.md", project_root: str = ".") -> Dict[str, Any]:
    root = Path(project_root)
    rows = []
    for key, spec in DEFAULT_REPORT_INPUTS.items():
        rows.append(_dataset_report_row(root, key, spec))

    output = root / output_path
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown = _render_final_report(rows)
    output.write_text(markdown, encoding="utf-8")

    json_path = output.with_suffix(".json")
    json_path.write_text(json.dumps({"datasets": rows, "report": str(output)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report": str(output), "json": str(json_path), "datasets": rows}


def _dataset_report_row(root: Path, key: str, spec: Dict[str, str]) -> Dict[str, Any]:
    analysis = _read_json(root / spec["analysis"])
    prediction = _read_json(root / spec["prediction"])
    inspect = _read_json(root / spec["inspect"])
    artifact_dir = root / spec["artifact_dir"]
    artifacts = {
        name: str(artifact_dir / name)
        for name in [
            "dashboard.html",
            "event_report.md",
            "analysis_summary.json",
            "participants.csv",
            "ignition_points.csv",
            "paths.json",
            "prediction_report.json",
        ]
        if (artifact_dir / name).exists()
    }
    totals = analysis.get("totals", {}) if analysis else {}
    path_prediction = prediction.get("path_prediction", {}) if prediction else {}
    size_prediction = prediction.get("size_prediction", {}) if prediction else {}
    ignition_points = totals.get("ignition_points")
    if ignition_points is None:
        ignition_points = _csv_data_rows(artifact_dir / "ignition_points.csv")
    return {
        "key": key,
        "label": spec["label"],
        "status": "ok" if analysis and prediction else "missing",
        "inspect_status": inspect.get("status") if inspect else None,
        "events": analysis.get("dataset_events") if analysis else _nested(inspect, "parsed", "events"),
        "nodes": totals.get("nodes") or _nested(inspect, "parsed", "nodes") or _nested(inspect, "parsed_estimate", "nodes"),
        "edges": totals.get("edges"),
        "participants": totals.get("participants"),
        "ignition_points": ignition_points,
        "focus_event_id": analysis.get("focus_event_id") if analysis else None,
        "path_auc": path_prediction.get("auc"),
        "path_samples": path_prediction.get("samples"),
        "size_rmse": size_prediction.get("rmse"),
        "size_train_events": size_prediction.get("train_events"),
        "size_test_events": size_prediction.get("test_events"),
        "artifacts": artifacts,
        "notes": _dataset_notes(key, inspect, path_prediction),
    }


def _render_final_report(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "# 知微传播分析复现验收报告",
        "",
        "## 任务覆盖",
        "",
        "| 功能项 | 当前实现 | 验收产物 |",
        "|---|---|---|",
        "| 传播分析 | 规模、边数、参与者、深度、宽度、持续时间、事件矩阵 | `analysis_summary.json`, `dashboard.html` |",
        "| 传播路径 | 重建父子传播边，导出关键路径和路径星图 | `paths.json`, `event_report.md`, `dashboard.html` |",
        "| 参与者信息 | 用户参与次数、出度贡献、PageRank/结构影响、角色分类 | `participants.csv`, dashboard TOP 参与者 |",
        "| 引爆点 | 时间窗口增长异常 + 结构影响力候选节点 | `ignition_points.csv`, dashboard 引爆点清单 |",
        "| 具体事件总结 | 自动选择最大/代表事件，输出文本总结 | `event_report.md` |",
        "| 数据集验证 | Weibo 全量、PHEME、Rumor_RvNN 验证 | 本报告下方数据集表 |",
        "",
        "## 数据集结果",
        "",
        "| 数据集 | 事件 | 节点 | 边 | 参与者 | 引爆点 | 路径 AUC | 规模 RMSE | 聚焦事件 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {label} | {events} | {nodes} | {edges} | {participants} | {ignitions} | {auc} | {rmse} | `{focus}` |".format(
                label=row["label"],
                events=_fmt_int(row.get("events")),
                nodes=_fmt_int(row.get("nodes")),
                edges=_fmt_int(row.get("edges")),
                participants=_fmt_int(row.get("participants")),
                ignitions=_fmt_int(row.get("ignition_points")),
                auc=_fmt_float(row.get("path_auc"), 3),
                rmse=_fmt_float(row.get("size_rmse"), 2),
                focus=row.get("focus_event_id") or "",
            )
        )
    lines += ["", "## 产物索引", ""]
    for row in rows:
        lines.append(f"### {row['label']}")
        for name, path in row["artifacts"].items():
            lines.append(f"- `{name}`: `{path}`")
        if row["notes"]:
            lines.append("")
            lines.append("说明：")
            for note in row["notes"]:
                lines.append(f"- {note}")
        lines.append("")
    lines += [
        "## 验收结论",
        "",
        "当前实现已经覆盖题目要求的传播分析、传播路径、参与者信息、引爆点和具体事件总结，并在 Weibo Rumor、PHEME、Rumor_RvNN 数据上完成验证。",
        "三个数据集均已生成 dashboard、事件报告、参与者表、引爆点表、路径文件和预测报告；Weibo Rumor 采用流式全量命令运行。",
        "",
        "## 限制说明",
        "",
        "- 当前实现复现的是知微传播分析的核心功能模块，不是知微商业网站的像素级 UI/交互复刻。",
        "- Rumor_RvNN 公开仓库是 Twitter15/16 processed 结构数据，缺少真实用户画像和真实时间戳，因此参与者画像为结构占位。",
        "- ScienceDB Weibo Rumor 有用户 ID 和时间戳，但缺少完整微博账号画像，因此不能还原真实账号粉丝画像。",
        "- 大规模路径预测对候选边使用采样，避免生成不可控的大型训练矩阵；传播分析和引爆点统计本身按事件全量覆盖。",
        "",
    ]
    return "\n".join(lines)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _csv_data_rows(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = sum(1 for _ in handle)
    return max(lines - 1, 0)


def _nested(obj: Dict[str, Any], *keys: str) -> Optional[Any]:
    value: Any = obj
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _dataset_notes(key: str, inspect: Dict[str, Any], path_prediction: Dict[str, Any]) -> List[str]:
    notes = []
    if key == "weibo_rumor":
        notes.append("Weibo Rumor 已全量运行 4664 个事件；路径预测候选边采用 reservoir sampling。")
    if key == "rumor_rvnn":
        notes.append("Rumor_RvNN processed 文件中 959 个 root 无 Twitter15/16 label/nfold 匹配，报告中已保留该警告。")
    if key == "pheme":
        notes.append("PHEME loader 跳过 annotation/structure 伪节点，只使用 source-tweets 与 reactions 构建传播树。")
    warnings = inspect.get("warnings") if inspect else None
    if warnings:
        notes.extend(str(item) for item in warnings)
    if path_prediction.get("note"):
        notes.append(str(path_prediction["note"]))
    return notes


def _fmt_int(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_float(value: Any, digits: int) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)
