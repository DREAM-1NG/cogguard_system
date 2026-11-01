from __future__ import annotations

import argparse
import csv
import html
import json
import random
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


DEFAULT_ROLE_EVIDENCE = Path("benchmark/kt1_role_evidence_validation/analysis/role_evidence.csv")
DEFAULT_OUTPUT = Path("benchmark/kt1_role_evidence_validation/analysis/role_evidence_manual_review_template.csv")
DEFAULT_PACKET = Path("benchmark/kt1_role_evidence_validation/analysis/ROLE_EVIDENCE_REVIEW_PACKET.md")
DEFAULT_HTML = Path("benchmark/kt1_role_evidence_validation/analysis/ROLE_EVIDENCE_REVIEW.html")
DEFAULT_FILLED_REVIEW = DEFAULT_OUTPUT.with_name("role_evidence_manual_review.csv")
REVIEW_FIELDS = [
    "event_id",
    "user_id",
    "coord_group_id",
    "is_coordinated",
    "role",
    "evidence_summary",
    "node_ids",
    "evidence_paths",
    "first_evidence_node",
    "first_seen",
    "out_degree_sum",
    "betweenness_sum",
    "pagerank_sum",
    "post_count",
    "reviewer",
    "review_pass",
    "evidence_match",
    "confidence_1to5",
    "review_timestamp",
    "reason_if_fail",
    "reviewer_note",
]

PASS_VALUES = {"1", "true", "yes", "y", "pass", "passed", "approved", "ok"}
FAIL_VALUES = {"0", "false", "no", "n", "fail", "failed", "reject", "rejected"}

REVIEW_INSTRUCTIONS = (
    "Template only: leave review_pass empty until a human reviewer checks whether "
    "the role label is supported by the observed propagation path, timestamp and "
    "structural evidence. The experiment audit only passes after a filled review "
    "CSV is saved as analysis/role_evidence_manual_review.csv or analysis/manual_review.csv."
)


def generate_review_template(
    role_evidence_csv: str | Path = DEFAULT_ROLE_EVIDENCE,
    output_csv: str | Path = DEFAULT_OUTPUT,
    *,
    sample_size: int = 30,
    per_role: int = 5,
    seed: int = 0,
) -> Dict:
    """Generate a balanced manual-review template without auto-approving rows."""

    source = Path(role_evidence_csv)
    output = Path(output_csv)
    rows = _read_role_evidence(source)
    sampled = _balanced_sample(rows, sample_size=sample_size, per_role=per_role, seed=seed)
    review_rows = [_review_row(row) for row in sampled]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(review_rows)

    summary = {
        "schema": "cogguard.kt2.role_evidence_manual_review_template.v1",
        "source": str(source),
        "output": str(output),
        "rows_available": len(rows),
        "rows_sampled": len(review_rows),
        "sample_size": sample_size,
        "per_role": per_role,
        "seed": seed,
        "role_counts": _role_counts(review_rows),
        "review_pass_prefilled": False,
        "instructions": REVIEW_INSTRUCTIONS,
    }
    guide = output.parent / "ROLE_EVIDENCE_REVIEW_GUIDE.md"
    packet = output.parent / "ROLE_EVIDENCE_REVIEW_PACKET.md"
    html_page = output.parent / "ROLE_EVIDENCE_REVIEW.html"
    summary["guide"] = str(guide)
    summary["packet"] = str(packet)
    summary["html"] = str(html_page)
    output.with_suffix(".json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    guide.write_text(review_guide_markdown(summary, template_path=output), encoding="utf-8")
    packet.write_text(review_packet_markdown(review_rows, template_path=output), encoding="utf-8")
    html_page.write_text(review_html_page(review_rows, template_path=output), encoding="utf-8")
    return summary


def init_review_file(
    template_csv: str | Path = DEFAULT_OUTPUT,
    output_csv: str | Path = DEFAULT_FILLED_REVIEW,
    *,
    overwrite: bool = False,
) -> Dict:
    """Create the filled-review CSV shell from the template without approving rows."""

    template = Path(template_csv)
    output = Path(output_csv)
    if not template.exists():
        return {
            "schema": "cogguard.kt2.role_evidence_manual_review_init.v1",
            "ok": False,
            "template": str(template),
            "output": str(output),
            "rows": 0,
            "detail": "review template CSV does not exist",
        }
    if output.exists() and not overwrite:
        return {
            "schema": "cogguard.kt2.role_evidence_manual_review_init.v1",
            "ok": False,
            "template": str(template),
            "output": str(output),
            "rows": _csv_summary(output)["rows"],
            "detail": "output review CSV already exists; pass --overwrite to recreate it",
        }
    rows = _read_role_evidence(template)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for row in rows:
            review_row = {field: str(row.get(field, "") or "") for field in REVIEW_FIELDS}
            review_row["review_pass"] = ""
            writer.writerow(review_row)
    return {
        "schema": "cogguard.kt2.role_evidence_manual_review_init.v1",
        "ok": True,
        "template": str(template),
        "output": str(output),
        "rows": len(rows),
        "review_pass_prefilled": False,
        "detail": "initialized review CSV with blank review_pass values",
    }


def validate_review_file(review_csv: str | Path, *, min_pass_rate: float = 0.8, template_csv: str | Path | None = None) -> Dict:
    """Preflight a filled manual-review CSV before running the full audit.

    This is intentionally stricter than experiment_audit: every sampled row should
    be reviewed so a sparse file cannot appear stronger than the human evidence is.
    """

    path = Path(review_csv)
    if not path.exists():
        return _review_validation_result(False, path, 0, 0, 0, 0.0, "manual review CSV does not exist")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return _review_validation_result(False, path, 0, 0, 0, 0.0, "manual review CSV contains no sampled rows")

    template_check = _template_coverage_check(rows, Path(template_csv) if template_csv else None)
    if not template_check["ok"]:
        result = _review_validation_result(False, path, len(rows), 0, 0, 0.0, template_check["detail"])
        result["template_check"] = template_check
        return result

    pass_values = []
    blank_rows = 0
    invalid_values = []
    incomplete_metadata = []
    for index, row in enumerate(rows, start=2):
        raw = row.get("review_pass") or row.get("passed") or row.get("approved") or row.get("status")
        value = str(raw or "").strip().lower()
        if not value:
            blank_rows += 1
            continue
        if value in PASS_VALUES:
            pass_values.append(True)
        elif value in FAIL_VALUES:
            pass_values.append(False)
        else:
            invalid_values.append({"row": index, "value": raw})
            continue
        metadata_issue = _manual_review_metadata_issue(row, passed=value in PASS_VALUES)
        if metadata_issue:
            incomplete_metadata.append({"row": index, "issue": metadata_issue})

    reviewed = len(pass_values)
    passed = sum(1 for value in pass_values if value)
    pass_rate = passed / max(reviewed, 1)
    ok = reviewed > 0 and not blank_rows and not invalid_values and not incomplete_metadata and pass_rate >= min_pass_rate
    if ok:
        detail = f"manual review passed with {passed}/{reviewed} approved rows; pass_rate={pass_rate:.2f}"
    elif not pass_values:
        detail = "manual review has no recognized pass/fail values"
    elif blank_rows:
        detail = f"manual review still has {blank_rows} blank review_pass rows"
    elif invalid_values:
        detail = f"manual review has unrecognized review_pass values: {invalid_values[:3]}"
    elif incomplete_metadata:
        detail = f"manual review has incomplete reviewer metadata: {incomplete_metadata[:3]}"
    else:
        detail = f"manual review pass_rate={pass_rate:.2f}, below required {min_pass_rate:.2f}"
    result = _review_validation_result(ok, path, len(rows), reviewed, passed, pass_rate, detail)
    result["blank_rows"] = blank_rows
    result["invalid_values"] = invalid_values
    result["incomplete_metadata"] = incomplete_metadata
    result["min_pass_rate"] = min_pass_rate
    result["recognized_pass_values"] = sorted(PASS_VALUES)
    result["recognized_fail_values"] = sorted(FAIL_VALUES)
    result["template_check"] = template_check
    return result


def review_status(
    *,
    role_evidence_csv: str | Path = DEFAULT_ROLE_EVIDENCE,
    template_csv: str | Path = DEFAULT_OUTPUT,
    review_csv: str | Path = DEFAULT_FILLED_REVIEW,
    min_pass_rate: float = 0.8,
) -> Dict:
    """Summarize whether the manual-review package is ready and what remains."""

    role_path = Path(role_evidence_csv)
    template_path = Path(template_csv)
    review_path = Path(review_csv)
    guide_path = template_path.parent / "ROLE_EVIDENCE_REVIEW_GUIDE.md"
    packet_path = template_path.parent / "ROLE_EVIDENCE_REVIEW_PACKET.md"
    html_path = template_path.parent / "ROLE_EVIDENCE_REVIEW.html"
    template_summary_path = template_path.with_suffix(".json")

    source_summary = _csv_summary(role_path)
    template_summary = _csv_summary(template_path)
    review_validation = validate_review_file(review_path, min_pass_rate=min_pass_rate, template_csv=template_path)
    packet_ready = all(path.exists() for path in [template_path, template_summary_path, guide_path, packet_path, html_path])
    review_ready = bool(review_validation["ok"])

    if review_ready:
        next_action = "Manual review is valid; rerun python -m benchmark.experiment_audit and python -m benchmark.completion_gate."
    elif not source_summary["exists"]:
        next_action = f"Generate role evidence first; missing source CSV: {role_path}"
    elif not packet_ready:
        next_action = "Generate the review package with python -m benchmark.role_evidence_review generate."
    elif not review_path.exists():
        next_action = f"Initialize {review_path} with python -m benchmark.role_evidence_review init, fill review_pass values, then run validate."
    elif review_validation.get("blank_rows"):
        rows = int(review_validation.get("rows") or 0)
        reviewed_rows = int(review_validation.get("reviewed_rows") or 0)
        blank_rows = int(review_validation.get("blank_rows") or 0)
        next_action = (
            f"Fill all sampled review_pass values in {review_path} "
            f"({reviewed_rows}/{rows} reviewed; {blank_rows} blank), plus reviewer, evidence_match, "
            "confidence_1to5, and any required reason_if_fail; then rerun validate."
        )
    else:
        next_action = "Fix the filled review CSV according to validation detail, then rerun validate."

    return {
        "schema": "cogguard.kt2.role_evidence_review_status.v1",
        "ok": review_ready,
        "role_evidence_csv": str(role_path),
        "role_evidence_rows": source_summary["rows"],
        "template_csv": str(template_path),
        "template_rows": template_summary["rows"],
        "template_ready": bool(template_summary["exists"] and template_summary["rows"] > 0),
        "template_summary": str(template_summary_path),
        "guide": str(guide_path),
        "packet": str(packet_path),
        "packet_ready": packet_ready,
        "html": str(html_path),
        "html_ready": html_path.exists(),
        "review_csv": str(review_path),
        "review_validation": review_validation,
        "next_action": next_action,
    }


def review_guide_markdown(summary: Mapping, *, template_path: str | Path) -> str:
    template = Path(template_path)
    filled_path = template.with_name("role_evidence_manual_review.csv")
    html_path = template.with_name("ROLE_EVIDENCE_REVIEW.html")
    role_counts = summary.get("role_counts") or {}
    role_lines = [f"- `{role}`: {count}" for role, count in role_counts.items()] or ["- none"]
    return "\n".join(
        [
            "# KT2 角色证据人工抽查指南",
            "",
            "## 审核目的",
            "",
            "本文件用于把 `role_evidence` 从审计 `partial` 推进到 `passed`。审核对象是已观测传播图上的角色解释，不是未来传播预测，也不是监督学习标签。",
            "",
            "## 输入与输出",
            "",
            f"- 待填写模板：`{template}`",
            f"- 审计读取文件：`{filled_path}` 或同目录 `manual_review.csv`",
            f"- 本地审核页：`{html_path}`",
            f"- 抽样行数：`{summary.get('rows_sampled', 0)}` / 可用行数 `{summary.get('rows_available', 0)}`",
            "",
            "## 抽样角色分布",
            "",
            *role_lines,
            "",
            "## 审核字段",
            "",
            "- `review_pass`：必填。支持 `true/false`、`pass/fail`、`yes/no`、`1/0`。",
            "- `evidence_match`：必填，说明路径、时间、结构指标是否支持角色判断。",
            "- `confidence_1to5`：必填 1 到 5 的主观置信度。",
            "- `reviewer`：必填，便于追溯审核责任；`review_timestamp`、`reviewer_note` 建议填写。",
            "- `reason_if_fail`：当 `review_pass=false` 时必填。",
            "",
            "## 通过标准",
            "",
            "- 至少有 1 条人工审核记录。",
            "- 所有样本都应填写可识别的 `review_pass` 值，不要留空。",
            "- 所有样本都应填写 `reviewer`、`evidence_match` 和 `confidence_1to5`。",
            "- 所有不通过样本都应填写 `reason_if_fail`。",
            "- `review_pass` 通过率必须大于等于 0.8。",
            "- 第一次审核前先初始化待填写 CSV，然后打开 HTML/证据包逐条审核：",
            "",
            "```powershell",
            f"python -m benchmark.role_evidence_review init --template {template} --output {filled_path}",
            "python -m benchmark.role_evidence_review status",
            f"python -m benchmark.role_evidence_review validate --review-file {filled_path}",
            "python -m benchmark.experiment_audit",
            "python -m benchmark.completion_gate",
            "```",
            "",
            "说明：`status` 会检查模板、证据包和最终审核 CSV 是否齐全；`validate` 是比审计更严格的预检查，要求所有抽样行都填写。只有 `benchmark.experiment_audit` 中 `manual_review_records` 变为 `passed` 且 `benchmark.completion_gate` 返回 `passed`，KT2 才能判断达到 full validation。",
            "",
        ]
    )


def review_packet_markdown(rows: Sequence[Mapping[str, str]], *, template_path: str | Path) -> str:
    """Create human-readable review cards for sampled role-evidence rows."""

    template = Path(template_path)
    lines = [
        "# KT2 角色证据人工抽查证据包",
        "",
        f"待填写 CSV：`{template}`",
        "",
        "本证据包只帮助人工审核，不自动判定通过。审核者仍需在 CSV 中填写 `review_pass`、`reviewer`、`evidence_match`、`confidence_1to5`；若不通过，还必须填写 `reason_if_fail`。",
        "",
        "## 角色判定参考",
        "",
        "- `起爆/源头`：通常位于根节点或浅层位置，出边贡献高，承担早期触发或源头扩散作用。",
        "- `桥接`：介数中心性较高，关键路径经过该用户，连接不同扩散分支。",
        "- `放大`：出边贡献较高，主要表现为放大传播覆盖。",
        "- `二级扩散`：有一定出边贡献，但不是源头或高介数桥接节点。",
        "- `普通参与者`：缺少明显出边、桥接或源头证据。",
        "",
        "## 审核样本",
        "",
    ]
    for index, row in enumerate(rows, start=1):
        lines.extend(_review_card_lines(index, row))
    return "\n".join(lines)


def review_html_page(rows: Sequence[Mapping[str, str]], *, template_path: str | Path) -> str:
    """Create a local human-review page without writing review decisions."""

    template = Path(template_path)
    cards = "\n".join(_review_card_html(index, row) for index, row in enumerate(rows, start=1))
    review_json = json.dumps([{field: str(row.get(field, "") or "") for field in REVIEW_FIELDS} for row in rows], ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KT2 角色证据人工抽查</title>
  <style>
    :root {{
      --ink: #18202a;
      --muted: #5a6675;
      --line: #d8e0ea;
      --paper: #fbf8f1;
      --card: #ffffff;
      --accent: #1f6f68;
      --warn: #a15620;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 8%, rgba(31, 111, 104, 0.12), transparent 28rem),
        linear-gradient(135deg, #fbf8f1 0%, #eef4f0 100%);
      font-family: "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", serif;
      line-height: 1.65;
    }}
    header {{
      padding: 36px clamp(18px, 5vw, 72px) 20px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(26px, 4vw, 46px);
      letter-spacing: 0.02em;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 24px auto 56px;
    }}
    .notice, .card {{
      background: rgba(255, 255, 255, 0.86);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 16px 42px rgba(25, 37, 49, 0.08);
    }}
    .notice {{
      padding: 18px 20px;
      margin-bottom: 20px;
    }}
    .card {{
      padding: 22px;
      margin: 18px 0;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 10px 0 16px;
    }}
    .pill {{
      display: inline-flex;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 10px;
      color: var(--muted);
      background: #fff;
      font-size: 13px;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #f3f6f5;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      overflow-x: auto;
      font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin: 14px 0;
    }}
    .metric {{
      border-left: 4px solid var(--accent);
      background: #f7faf8;
      padding: 8px 10px;
      border-radius: 10px;
    }}
    .hint {{
      color: var(--warn);
      font-weight: 700;
    }}
    .decision {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
      margin-top: 16px;
      padding-top: 14px;
      border-top: 1px dashed var(--line);
    }}
    label {{
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 13px;
    }}
    input, select, textarea {{
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }}
    textarea {{
      min-height: 72px;
      resize: vertical;
    }}
    .actions {{
      position: sticky;
      bottom: 0;
      margin-top: 26px;
      padding: 16px;
      background: rgba(251, 248, 241, 0.95);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 -10px 30px rgba(25, 37, 49, 0.08);
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      margin-right: 8px;
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      cursor: pointer;
    }}
    #csvOutput {{
      width: 100%;
      min-height: 140px;
      margin-top: 12px;
      font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>KT2 角色证据人工抽查</h1>
    <p>本页面只展示审核样本和证据，不自动判定通过。审核结论仍需填写到 CSV 的 <code>review_pass</code> 字段。</p>
  </header>
  <main>
    <section class="notice">
      <strong>填写目标：</strong>打开 <code>{_escape(template)}</code>，另存为 <code>role_evidence_manual_review.csv</code>，逐行填写 <code>review_pass</code>、<code>reviewer</code>、<code>evidence_match</code>、<code>confidence_1to5</code>；若不通过，还必须填写 <code>reason_if_fail</code>。
      <br>
      <span class="hint">注意：</span>本页面可在浏览器中生成 CSV 文本/下载文件，但不会直接写入本地仓库，也不会让 completion gate 自动通过。
    </section>
    {cards}
    <section class="actions">
      <strong>审核导出</strong>
      <p>填写每张卡片后，点击生成 CSV。随后将下载内容保存/覆盖为 <code>role_evidence_manual_review.csv</code>，再运行 <code>python -m benchmark.role_evidence_review validate</code>。</p>
      <button type="button" onclick="generateCsv()">生成 CSV 文本</button>
      <button type="button" onclick="downloadCsv()">下载 role_evidence_manual_review.csv</button>
      <textarea id="csvOutput" placeholder="生成后的 CSV 会显示在这里，便于复制检查。"></textarea>
    </section>
  </main>
  <script>
    const reviewRows = {review_json};
    const reviewFields = {json.dumps(REVIEW_FIELDS, ensure_ascii=False)};

    function csvEscape(value) {{
      const text = String(value ?? "");
      if (/[",\r\n]/.test(text)) {{
        return '"' + text.replace(/"/g, '""') + '"';
      }}
      return text;
    }}

    function collectRows() {{
      return reviewRows.map((row, index) => {{
        const out = {{...row}};
        const pass = document.querySelector(`[name="review_pass_${{index}}"]`)?.value || "";
        out.review_pass = pass;
        out.evidence_match = document.querySelector(`[name="evidence_match_${{index}}"]`)?.value || "";
        out.confidence_1to5 = document.querySelector(`[name="confidence_${{index}}"]`)?.value || "";
        out.reviewer = document.querySelector(`[name="reviewer_${{index}}"]`)?.value || "";
        out.review_timestamp = document.querySelector(`[name="timestamp_${{index}}"]`)?.value || "";
        out.reason_if_fail = document.querySelector(`[name="reason_${{index}}"]`)?.value || "";
        out.reviewer_note = document.querySelector(`[name="note_${{index}}"]`)?.value || "";
        return out;
      }});
    }}

    function generateCsv() {{
      const lines = [reviewFields.join(",")];
      for (const row of collectRows()) {{
        lines.push(reviewFields.map((field) => csvEscape(row[field])).join(","));
      }}
      const csv = lines.join("\\n") + "\\n";
      document.getElementById("csvOutput").value = csv;
      return csv;
    }}

    function downloadCsv() {{
      const csv = generateCsv();
      const blob = new Blob([csv], {{type: "text/csv;charset=utf-8"}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "role_evidence_manual_review.csv";
      link.click();
      URL.revokeObjectURL(url);
    }}
  </script>
</body>
</html>
"""


def _read_role_evidence(path: Path) -> List[Mapping[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"role evidence CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"role evidence CSV has no rows: {path}")
    return rows


def _balanced_sample(rows: Sequence[Mapping[str, str]], *, sample_size: int, per_role: int, seed: int) -> List[Mapping[str, str]]:
    if sample_size <= 0:
        return []
    rng = random.Random(seed)
    grouped: Dict[str, List[Mapping[str, str]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("role") or "unknown"), []).append(row)

    selected: List[Mapping[str, str]] = []
    selected_ids = set()
    for role in sorted(grouped):
        candidates = _shuffled(grouped[role], rng)
        for row in candidates[: max(per_role, 0)]:
            selected.append(row)
            selected_ids.add(id(row))
            if len(selected) >= sample_size:
                return _stable_order(selected)

    remainder = [row for row in rows if id(row) not in selected_ids]
    for row in _shuffled(remainder, rng):
        selected.append(row)
        if len(selected) >= sample_size:
            break
    return _stable_order(selected)


def _shuffled(rows: Iterable[Mapping[str, str]], rng: random.Random) -> List[Mapping[str, str]]:
    result = list(rows)
    rng.shuffle(result)
    return result


def _stable_order(rows: Sequence[Mapping[str, str]]) -> List[Mapping[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("event_id") or ""),
            str(row.get("first_seen") or ""),
            str(row.get("user_id") or ""),
            str(row.get("role") or ""),
        ),
    )


def _review_row(row: Mapping[str, str]) -> Dict[str, str]:
    return {field: str(row.get(field, "") or "") for field in REVIEW_FIELDS}


def _role_counts(rows: Iterable[Mapping[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        role = str(row.get("role") or "unknown")
        counts[role] = counts.get(role, 0) + 1
    return dict(sorted(counts.items()))


def _review_card_lines(index: int, row: Mapping[str, str]) -> List[str]:
    role = str(row.get("role") or "unknown")
    return [
        f"### 样本 {index}: `{row.get('event_id', '')}` / `{row.get('user_id', '')}` / `{role}`",
        "",
        f"- 协同组：`{row.get('coord_group_id', '')}`；是否协同：`{row.get('is_coordinated', '')}`",
        f"- 首次证据节点：`{row.get('first_evidence_node', '')}`；首次出现时间：`{row.get('first_seen', '')}`",
        f"- 结构指标：出度贡献 `{row.get('out_degree_sum', '')}`，介数中心性 `{row.get('betweenness_sum', '')}`，PageRank `{row.get('pagerank_sum', '')}`，发帖数 `{row.get('post_count', '')}`",
        f"- 命中节点：`{row.get('node_ids', '')}`",
        f"- 关键路径：`{row.get('evidence_paths', '')}`",
        f"- 自动摘要：{row.get('evidence_summary', '')}",
        "",
        "审核建议：",
        *_role_review_hints(role),
        "",
        "填写建议：如果路径、时间和结构指标能支撑该角色，`review_pass=true`；否则写 `false` 并在 `reason_if_fail` 说明原因。",
        "",
    ]


def _review_card_html(index: int, row: Mapping[str, str]) -> str:
    zero_index = index - 1
    role = str(row.get("role") or "unknown")
    hints = "".join(f"<li>{_escape(hint.lstrip('- '))}</li>" for hint in _role_review_hints(role))
    metrics = [
        ("出度贡献", row.get("out_degree_sum", "")),
        ("介数中心性", row.get("betweenness_sum", "")),
        ("PageRank", row.get("pagerank_sum", "")),
        ("发帖数", row.get("post_count", "")),
    ]
    metric_html = "".join(
        f"<div class=\"metric\"><strong>{_escape(name)}</strong><br>{_escape(value)}</div>"
        for name, value in metrics
    )
    return f"""
    <article class="card">
      <h2>样本 {index}: {_escape(row.get('event_id', ''))} / {_escape(row.get('user_id', ''))} / {_escape(role)}</h2>
      <div class="meta">
        <span class="pill">协同组：{_escape(row.get('coord_group_id', ''))}</span>
        <span class="pill">是否协同：{_escape(row.get('is_coordinated', ''))}</span>
        <span class="pill">首次节点：{_escape(row.get('first_evidence_node', ''))}</span>
        <span class="pill">首次时间：{_escape(row.get('first_seen', ''))}</span>
      </div>
      <div class="grid">{metric_html}</div>
      <p><strong>自动摘要：</strong>{_escape(row.get('evidence_summary', ''))}</p>
      <p><strong>命中节点：</strong></p>
      <pre>{_escape(row.get('node_ids', ''))}</pre>
      <p><strong>关键路径：</strong></p>
      <pre>{_escape(row.get('evidence_paths', ''))}</pre>
      <p><strong>审核建议：</strong></p>
      <ul>{hints}</ul>
      <p class="hint">填写建议：若路径、时间和结构指标能支撑该角色，在 CSV 中填写 review_pass=true；否则填写 false 并说明原因。</p>
      <div class="decision">
        <label>review_pass
          <select name="review_pass_{zero_index}">
            <option value="">待审核</option>
            <option value="true">true / 通过</option>
            <option value="false">false / 不通过</option>
          </select>
        </label>
        <label>evidence_match
          <select name="evidence_match_{zero_index}">
            <option value="">未填写</option>
            <option value="yes">yes</option>
            <option value="partial">partial</option>
            <option value="no">no</option>
          </select>
        </label>
        <label>confidence_1to5
          <input name="confidence_{zero_index}" type="number" min="1" max="5" placeholder="1-5">
        </label>
        <label>reviewer
          <input name="reviewer_{zero_index}" placeholder="审核人">
        </label>
        <label>review_timestamp
          <input name="timestamp_{zero_index}" placeholder="YYYY-MM-DD">
        </label>
        <label>reason_if_fail
          <textarea name="reason_{zero_index}" placeholder="不通过时说明原因"></textarea>
        </label>
        <label>reviewer_note
          <textarea name="note_{zero_index}" placeholder="补充说明"></textarea>
        </label>
      </div>
    </article>
    """


def _escape(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _role_review_hints(role: str) -> List[str]:
    if role == "起爆/源头":
        return ["- 检查该用户是否足够早出现，且命中节点是否位于根节点或浅层传播路径。", "- 检查出边贡献是否确实支撑源头/起爆解释。"]
    if role == "桥接":
        return ["- 检查关键路径是否多次经过该用户。", "- 检查介数中心性是否是主要证据，而不只是普通转发节点。"]
    if role == "放大":
        return ["- 检查出边贡献是否明显高于普通参与者。", "- 检查命中路径是否体现扩散覆盖扩大。"]
    if role == "二级扩散":
        return ["- 检查该用户是否有出边贡献但不是源头。", "- 检查路径位置是否处在源头之后的扩散层。"]
    if role == "普通参与者":
        return ["- 检查该用户是否缺少出边、桥接或源头证据。", "- 若路径显示明显传播贡献，应标记为不通过并说明。"]
    return ["- 检查角色名称、路径、时间和结构指标是否互相一致。"]


def _manual_review_metadata_issue(row: Mapping, *, passed: bool) -> str:
    reviewer = str(row.get("reviewer") or "").strip()
    evidence_match = str(row.get("evidence_match") or "").strip()
    confidence = str(row.get("confidence_1to5") or "").strip()
    reason_if_fail = str(row.get("reason_if_fail") or "").strip()
    if not reviewer:
        return "missing reviewer"
    if not evidence_match:
        return "missing evidence_match"
    try:
        confidence_value = int(confidence)
    except ValueError:
        return "confidence_1to5 must be an integer from 1 to 5"
    if confidence_value < 1 or confidence_value > 5:
        return "confidence_1to5 must be an integer from 1 to 5"
    if not passed and not reason_if_fail:
        return "failed reviews must include reason_if_fail"
    return ""


def _review_validation_result(ok: bool, path: Path, rows: int, reviewed: int, passed: int, pass_rate: float, detail: str) -> Dict:
    return {
        "schema": "cogguard.kt2.role_evidence_manual_review_validation.v1",
        "ok": ok,
        "review_file": str(path),
        "rows": rows,
        "reviewed_rows": reviewed,
        "passed_rows": passed,
        "pass_rate": pass_rate,
        "detail": detail,
    }


def _csv_summary(path: Path) -> Dict:
    if not path.exists():
        return {"exists": False, "rows": 0}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {"exists": True, "rows": len(rows)}


def _template_coverage_check(review_rows: Sequence[Mapping[str, str]], template_path: Optional[Path]) -> Dict:
    if template_path is None:
        return {"ok": True, "template": None, "detail": "template coverage check disabled"}
    if not template_path.exists():
        return {"ok": False, "template": str(template_path), "detail": f"review template CSV does not exist: {template_path}"}
    template_rows = _read_role_evidence(template_path)
    template_keys = [_review_key(row) for row in template_rows]
    review_keys = [_review_key(row) for row in review_rows]
    missing = sorted(set(template_keys) - set(review_keys))
    extra = sorted(set(review_keys) - set(template_keys))
    duplicates = sorted(key for key in set(review_keys) if review_keys.count(key) > 1)
    ok = len(review_rows) == len(template_rows) and not missing and not extra and not duplicates
    if ok:
        detail = f"review CSV covers all {len(template_rows)} template rows"
    elif len(review_rows) != len(template_rows):
        detail = f"review CSV row count {len(review_rows)} does not match template row count {len(template_rows)}"
    elif missing:
        detail = f"review CSV is missing template rows: {missing[:3]}"
    elif extra:
        detail = f"review CSV has rows not present in template: {extra[:3]}"
    else:
        detail = f"review CSV has duplicate sampled rows: {duplicates[:3]}"
    return {
        "ok": ok,
        "template": str(template_path),
        "template_rows": len(template_rows),
        "review_rows": len(review_rows),
        "missing_rows": missing[:10],
        "extra_rows": extra[:10],
        "duplicate_rows": duplicates[:10],
        "detail": detail,
    }


def _review_key(row: Mapping[str, str]) -> str:
    return "|".join(
        [
            str(row.get("event_id") or ""),
            str(row.get("user_id") or ""),
            str(row.get("role") or ""),
            str(row.get("first_evidence_node") or ""),
            str(row.get("first_seen") or ""),
        ]
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        import sys

        raw_args = sys.argv[1:]
    else:
        raw_args = list(argv)
    if not raw_args or raw_args[0] not in {"generate", "init", "validate", "packet", "html", "status", "-h", "--help"}:
        raw_args = ["generate", *raw_args]

    parser = argparse.ArgumentParser(description="Generate or validate KT2 role-evidence manual-review files.")
    subparsers = parser.add_subparsers(dest="command")

    generate_parser = subparsers.add_parser("generate", description="Generate a manual-review template.")
    generate_parser.add_argument("--role-evidence", default=str(DEFAULT_ROLE_EVIDENCE))
    generate_parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    generate_parser.add_argument("--sample-size", type=int, default=30)
    generate_parser.add_argument("--per-role", type=int, default=5)
    generate_parser.add_argument("--seed", type=int, default=0)

    init_parser = subparsers.add_parser("init", description="Copy the review template to a fillable review CSV without approving rows.")
    init_parser.add_argument("--template", default=str(DEFAULT_OUTPUT))
    init_parser.add_argument("--output", default=str(DEFAULT_FILLED_REVIEW))
    init_parser.add_argument("--overwrite", action="store_true")

    validate_parser = subparsers.add_parser("validate", description="Validate a filled manual-review CSV.")
    validate_parser.add_argument("--review-file", default=str(DEFAULT_OUTPUT.with_name("role_evidence_manual_review.csv")))
    validate_parser.add_argument("--min-pass-rate", type=float, default=0.8)
    validate_parser.add_argument("--template", default=str(DEFAULT_OUTPUT), help="Template CSV that the filled review must cover; pass empty string to disable.")

    packet_parser = subparsers.add_parser("packet", description="Generate a Markdown evidence packet from a review CSV.")
    packet_parser.add_argument("--review-template", default=str(DEFAULT_OUTPUT))
    packet_parser.add_argument("--output", default=str(DEFAULT_PACKET))

    html_parser = subparsers.add_parser("html", description="Generate a local HTML evidence-review page.")
    html_parser.add_argument("--review-template", default=str(DEFAULT_OUTPUT))
    html_parser.add_argument("--output", default=str(DEFAULT_HTML))

    status_parser = subparsers.add_parser("status", description="Check manual-review package readiness without approving rows.")
    status_parser.add_argument("--role-evidence", default=str(DEFAULT_ROLE_EVIDENCE))
    status_parser.add_argument("--template", default=str(DEFAULT_OUTPUT))
    status_parser.add_argument("--review-file", default=str(DEFAULT_FILLED_REVIEW))
    status_parser.add_argument("--min-pass-rate", type=float, default=0.8)
    args = parser.parse_args(raw_args)

    if args.command == "init":
        summary = init_review_file(args.template, args.output, overwrite=args.overwrite)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["ok"] else 1
    if args.command == "validate":
        template = args.template if args.template else None
        summary = validate_review_file(args.review_file, min_pass_rate=args.min_pass_rate, template_csv=template)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["ok"] else 1
    if args.command == "status":
        summary = review_status(
            role_evidence_csv=args.role_evidence,
            template_csv=args.template,
            review_csv=args.review_file,
            min_pass_rate=args.min_pass_rate,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["ok"] else 1
    if args.command == "packet":
        rows = _read_role_evidence(Path(args.review_template))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(review_packet_markdown(rows, template_path=args.review_template), encoding="utf-8")
        summary = {
            "schema": "cogguard.kt2.role_evidence_review_packet.v1",
            "review_template": args.review_template,
            "output": str(output),
            "rows": len(rows),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "html":
        rows = _read_role_evidence(Path(args.review_template))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(review_html_page(rows, template_path=args.review_template), encoding="utf-8")
        summary = {
            "schema": "cogguard.kt2.role_evidence_review_html.v1",
            "review_template": args.review_template,
            "output": str(output),
            "rows": len(rows),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    summary = generate_review_template(
        args.role_evidence,
        args.output,
        sample_size=args.sample_size,
        per_role=args.per_role,
        seed=args.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
