from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx
import numpy as np
import pandas as pd

from .analysis import _depths, ignition_points, key_paths, participant_table, summarize_event, write_event_report
from .models import PropagationEvent, sorted_nodes_by_time


DARK_HTML_TEMPLATE = """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>传播分析驾驶舱</title>
  <script src=\"https://cdn.plot.ly/plotly-2.35.2.min.js\"></script>
  <style>
    :root {{
      --bg: #070b16; --panel: rgba(17, 25, 44, .78); --panel2: rgba(13, 20, 36, .92);
      --text: #e8f1ff; --muted: #90a4c3; --cyan: #2ee9ff; --blue: #5d7cff;
      --pink: #ff4ecd; --orange: #ffb84d; --green: #52ffa8; --red: #ff5b7f;
      --line: rgba(130, 170, 255, .18);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at 12% 8%, rgba(46,233,255,.18), transparent 26%),
                  radial-gradient(circle at 80% 0%, rgba(255,78,205,.13), transparent 22%),
                  linear-gradient(135deg, #050713, #091225 48%, #050713); min-height: 100vh; }}
    body:before {{ content: \"\"; position: fixed; inset: 0; pointer-events: none;
      background-image: linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
      background-size: 42px 42px; mask-image: linear-gradient(to bottom, rgba(0,0,0,.9), transparent); }}
    .wrap {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
    .hero {{ display: grid; grid-template-columns: 1.5fr .9fr; gap: 18px; align-items: stretch; }}
    .card {{ border: 1px solid var(--line); border-radius: 22px; background: var(--panel); box-shadow: 0 20px 80px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.06); backdrop-filter: blur(16px); }}
    .title {{ padding: 28px; position: relative; overflow: hidden; }}
    .title h1 {{ margin: 0; font-size: clamp(30px, 4vw, 56px); letter-spacing: -.04em; line-height: 1; }}
    .title p {{ color: var(--muted); font-size: 16px; line-height: 1.7; max-width: 980px; }}
    .badge {{ display: inline-flex; gap: 8px; align-items: center; padding: 8px 12px; border: 1px solid rgba(46,233,255,.28); border-radius: 999px; color: var(--cyan); background: rgba(46,233,255,.08); font-size: 13px; margin-bottom: 14px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 18px; }}
    .metric {{ padding: 18px; border-radius: 18px; background: linear-gradient(160deg, rgba(255,255,255,.08), rgba(255,255,255,.025)); border: 1px solid var(--line); }}
    .metric .k {{ color: var(--muted); font-size: 13px; }} .metric .v {{ font-size: 30px; font-weight: 800; margin-top: 7px; }}
    .metric .s {{ color: var(--cyan); font-size: 12px; margin-top: 6px; }}
    .side {{ padding: 22px; }} .side h2 {{ margin: 0 0 12px; }} .narrative {{ color: #c9d8ef; line-height: 1.8; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 18px; }}
    .wide {{ grid-column: 1 / -1; }} .panel-title {{ padding: 18px 20px 0; display:flex; justify-content:space-between; align-items:center; }}
    .panel-title h3 {{ margin: 0; font-size: 17px; }} .hint {{ color: var(--muted); font-size: 12px; }}
    .plot {{ height: 420px; }} .plot.tall {{ height: 620px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }} th, td {{ padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; }} th {{ color: var(--cyan); font-weight: 700; }} td {{ color: #d4e1f7; }}
    .table-wrap {{ padding: 12px 18px 22px; max-height: 430px; overflow:auto; }}
    .pill {{ padding: 4px 8px; border-radius: 999px; background: rgba(93,124,255,.16); color: #b8c5ff; }}
    .footer {{ color: var(--muted); text-align: center; padding: 20px; font-size: 12px; }}
    @media (max-width: 980px) {{ .hero, .grid {{ grid-template-columns: 1fr; }} .metrics {{ grid-template-columns: repeat(2,1fr); }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <section class=\"hero\">
      <div class=\"card title\">
        <div class=\"badge\">✦ Weibo/PHEME Rumour Propagation Intelligence</div>
        <h1>传播分析驾驶舱</h1>
        <p>复现传播分析、传播路径、参与者信息、引爆点与预测模块。当前页面为本地静态报告，适合课堂展示、实验汇报和真实数据集验证。</p>
        <div class=\"metrics\">
          <div class=\"metric\"><div class=\"k\">事件数</div><div class=\"v\">{event_count}</div><div class=\"s\">Cascades</div></div>
          <div class=\"metric\"><div class=\"k\">传播节点</div><div class=\"v\">{node_count}</div><div class=\"s\">Posts/Reposts</div></div>
          <div class=\"metric\"><div class=\"k\">参与者</div><div class=\"v\">{participant_count}</div><div class=\"s\">Unique Users</div></div>
          <div class=\"metric\"><div class=\"k\">引爆点</div><div class=\"v\">{ignition_count}</div><div class=\"s\">Growth Spikes</div></div>
        </div>
      </div>
      <div class=\"card side\"><h2>事件总结</h2><div class=\"narrative\">{narrative}</div></div>
    </section>

    <section class=\"grid\">
      <div class=\"card wide\"><div class=\"panel-title\"><h3>传播路径星图</h3><span class=\"hint\">节点越大代表扩散贡献越高；红色为引爆点</span></div><div id=\"network\" class=\"plot tall\"></div></div>
      <div class=\"card\"><div class=\"panel-title\"><h3>传播增长时间线</h3><span class=\"hint\">新增节点 / 累计规模</span></div><div id=\"timeline\" class=\"plot\"></div></div>
      <div class=\"card\"><div class=\"panel-title\"><h3>深度-宽度结构</h3><span class=\"hint\">传播层级剖面</span></div><div id=\"depth\" class=\"plot\"></div></div>
      <div class=\"card\"><div class=\"panel-title\"><h3>事件规模矩阵</h3><span class=\"hint\">规模 / 深度 / 宽度</span></div><div id=\"events\" class=\"plot\"></div></div>
      <div class=\"card\"><div class=\"panel-title\"><h3>参与者角色分布</h3><span class=\"hint\">KOL / 桥接 / 二传 / 普通</span></div><div id=\"roles\" class=\"plot\"></div></div>
      <div class=\"card\"><div class=\"panel-title\"><h3>TOP 参与者</h3><span class=\"hint\">按影响力排序</span></div><div class=\"table-wrap\">{participant_table}</div></div>
      <div class=\"card\"><div class=\"panel-title\"><h3>引爆点清单</h3><span class=\"hint\">时间异常 + 结构影响</span></div><div class=\"table-wrap\">{ignition_table}</div></div>
      <div class=\"card wide\"><div class=\"panel-title\"><h3>关键传播路径</h3><span class=\"hint\">最长链路 Top 10</span></div><div class=\"table-wrap\">{path_table}</div></div>
    </section>
    <div class=\"footer\">Generated by local propagation-analysis toolkit · static HTML · no server required</div>
  </div>
<script>
const DATA = {payload};
const layoutBase = {{ paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: {{color: '#dce8ff'}}, margin: {{l:45,r:25,t:20,b:45}}, xaxis: {{gridcolor:'rgba(150,180,255,.12)'}}, yaxis: {{gridcolor:'rgba(150,180,255,.12)'}} }};
Plotly.newPlot('timeline', [
  {{x: DATA.timeline.x, y: DATA.timeline.new_nodes, type:'bar', name:'新增', marker:{{color:'#2ee9ff'}}}},
  {{x: DATA.timeline.x, y: DATA.timeline.cumulative, type:'scatter', mode:'lines+markers', name:'累计', line:{{color:'#ff4ecd', width:3}}}}
], {{...layoutBase, legend:{{orientation:'h'}}}}, {{displayModeBar:false, responsive:true}});
Plotly.newPlot('depth', [{{x: DATA.depth.depth, y: DATA.depth.count, type:'bar', marker:{{color: DATA.depth.count.map((_,i)=>`rgba(${{46+i*28}},233,255,.78)`)}} }}], {{...layoutBase, xaxis:{{title:'传播深度', gridcolor:'rgba(150,180,255,.12)'}}, yaxis:{{title:'节点数', gridcolor:'rgba(150,180,255,.12)'}}}}, {{displayModeBar:false, responsive:true}});
Plotly.newPlot('events', [{{x: DATA.events.node_count, y: DATA.events.max_depth, text: DATA.events.event_id, mode:'markers', type:'scatter', marker:{{size: DATA.events.max_width, sizemode:'area', sizeref: Math.max(...DATA.events.max_width)/80, color: DATA.events.duration_minutes, colorscale:'Turbo', showscale:true, colorbar:{{title:'分钟'}}}} }}], {{...layoutBase, xaxis:{{title:'规模', gridcolor:'rgba(150,180,255,.12)'}}, yaxis:{{title:'最大深度', gridcolor:'rgba(150,180,255,.12)'}}}}, {{displayModeBar:false, responsive:true}});
Plotly.newPlot('roles', [{{labels: DATA.roles.labels, values: DATA.roles.values, type:'pie', hole:.55, marker:{{colors:['#2ee9ff','#ff4ecd','#ffb84d','#52ffa8']}} }}], {{...layoutBase, showlegend:true}}, {{displayModeBar:false, responsive:true}});
Plotly.newPlot('network', [
  {{x: DATA.network.edge_x, y: DATA.network.edge_y, mode:'lines', type:'scatter', hoverinfo:'none', line:{{width:1, color:'rgba(130,170,255,.23)'}}}},
  {{x: DATA.network.x, y: DATA.network.y, mode:'markers+text', type:'scatter', text: DATA.network.label, textposition:'top center', hovertext: DATA.network.hover, hoverinfo:'text', marker:{{size: DATA.network.size, color: DATA.network.color, line:{{color:'#ffffff', width:1}}, opacity:.92}}}}
], {{...layoutBase, xaxis:{{visible:false}}, yaxis:{{visible:false}}, margin:{{l:10,r:10,t:10,b:10}}}}, {{displayModeBar:false, responsive:true}});
</script>
</body>
</html>"""


def build_dashboard(events: List[PropagationEvent], output_dir: str, prediction_report: Optional[Dict] = None) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summaries = [summarize_event(e) for e in events]
    participants = pd.concat([participant_table(e) for e in events], ignore_index=True) if events else pd.DataFrame()
    ignitions = pd.concat([ignition_points(e) for e in events], ignore_index=True) if events else pd.DataFrame()
    representative = max(events, key=lambda e: len(e.nodes)) if events else None

    payload = {
        "timeline": _timeline_payload(representative),
        "depth": _depth_payload(representative),
        "events": _events_payload(summaries),
        "roles": _roles_payload(participants),
        "network": _network_payload(representative, ignitions),
    }
    narrative = _dashboard_narrative(summaries, ignitions, prediction_report)
    html = DARK_HTML_TEMPLATE.format(
        event_count=len(events),
        node_count=sum(s["node_count"] for s in summaries),
        participant_count=participants["user_id"].nunique() if not participants.empty else 0,
        ignition_count=len(ignitions) if not ignitions.empty else 0,
        narrative=narrative,
        participant_table=_participant_html(participants),
        ignition_table=_ignition_html(ignitions),
        path_table=_path_html(representative),
        payload=json.dumps(payload, ensure_ascii=False, default=str),
    )
    path = out / "dashboard.html"
    path.write_text(html, encoding="utf-8")
    report_paths = {representative.event_id: key_paths(representative, 10)} if representative else {}
    write_event_report(out / "event_report.md", representative, summaries, participants, ignitions, report_paths)
    return path


def build_dashboard_from_artifacts(
    output_dir: str,
    summaries: List[Dict],
    representative: Optional[PropagationEvent],
    top_participants: pd.DataFrame,
    top_ignitions: pd.DataFrame,
    role_counts: Dict[str, int],
    total_participants: int,
    total_ignitions: int,
    prediction_report: Optional[Dict] = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "timeline": _timeline_payload(representative),
        "depth": _depth_payload(representative),
        "events": _events_payload(summaries),
        "roles": _roles_payload_from_counts(role_counts),
        "network": _network_payload(representative, top_ignitions),
    }
    narrative = _dashboard_narrative(summaries, top_ignitions, prediction_report)
    if summaries:
        largest = max(summaries, key=lambda s: s["node_count"])
        narrative = (
            f"系统共处理 <b>{len(summaries)}</b> 个事件，合计 <b>{sum(s['node_count'] for s in summaries)}</b> 个传播节点。"
            f"最大级联为 <b>{largest['event_id']}</b>，包含 <b>{largest['node_count']}</b> 个节点。"
            f"全量识别 <b>{total_ignitions}</b> 个候选引爆点。"
        )
        if prediction_report:
            size = prediction_report.get("size_prediction", {})
            path = prediction_report.get("path_prediction", {})
            if size.get("status") == "ok":
                narrative += f" 全量规模预测 RMSE 为 <b>{size.get('rmse', 0):.2f}</b>。"
            if path.get("status") == "ok":
                narrative += f" 路径预测采样 AUC 为 <b>{path.get('auc', 0):.3f}</b>。"
    html = DARK_HTML_TEMPLATE.format(
        event_count=len(summaries),
        node_count=sum(s["node_count"] for s in summaries),
        participant_count=total_participants,
        ignition_count=total_ignitions,
        narrative=narrative,
        participant_table=_participant_html(top_participants),
        ignition_table=_ignition_html(top_ignitions),
        path_table=_path_html(representative),
        payload=json.dumps(payload, ensure_ascii=False, default=str),
    )
    path = out / "dashboard.html"
    path.write_text(html, encoding="utf-8")
    return path


def _timeline_payload(event: Optional[PropagationEvent]) -> Dict:
    if not event:
        return {"x": [], "new_nodes": [], "cumulative": []}
    nodes = [n for n in sorted_nodes_by_time(event) if n.timestamp]
    counts = Counter(n.timestamp.strftime("%Y-%m-%d %H:%M") for n in nodes)
    x = sorted(counts)
    new_nodes = [counts[t] for t in x]
    cumulative = list(np.cumsum(new_nodes).astype(int))
    return {"x": x, "new_nodes": new_nodes, "cumulative": cumulative}


def _depth_payload(event: Optional[PropagationEvent]) -> Dict:
    if not event:
        return {"depth": [], "count": []}
    depths = _depths(event.to_graph())
    counts = Counter(depths.values())
    keys = sorted(counts)
    return {"depth": keys, "count": [counts[k] for k in keys]}


def _events_payload(summaries: List[Dict]) -> Dict:
    return {
        "event_id": [s["event_id"] for s in summaries],
        "node_count": [s["node_count"] for s in summaries],
        "max_depth": [s["max_depth"] for s in summaries],
        "max_width": [max(s["max_width"], 5) for s in summaries],
        "duration_minutes": [s["duration_minutes"] for s in summaries],
    }


def _roles_payload(participants: pd.DataFrame) -> Dict:
    if participants.empty or "role" not in participants:
        return {"labels": [], "values": []}
    counts = participants["role"].value_counts()
    return {"labels": counts.index.tolist(), "values": counts.values.astype(int).tolist()}


def _roles_payload_from_counts(counts: Dict[str, int]) -> Dict:
    if not counts:
        return {"labels": [], "values": []}
    items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return {"labels": [key for key, _ in items], "values": [int(value) for _, value in items]}


def _network_payload(event: Optional[PropagationEvent], ignitions: pd.DataFrame) -> Dict:
    if not event:
        return {"x": [], "y": [], "edge_x": [], "edge_y": [], "size": [], "color": [], "label": [], "hover": []}
    graph = event.to_graph()
    if graph.number_of_nodes() > 450:
        keep = sorted(graph.nodes, key=lambda n: graph.out_degree(n), reverse=True)[:450]
        graph = graph.subgraph(keep).copy()
    pos = nx.spring_layout(graph, seed=42, k=1 / max(graph.number_of_nodes(), 1) ** 0.5)
    ignition_nodes = set(ignitions.loc[ignitions["event_id"] == event.event_id, "node_id"].astype(str)) if not ignitions.empty else set()
    edge_x, edge_y = [], []
    for a, b in graph.edges:
        edge_x += [pos[a][0], pos[b][0], None]
        edge_y += [pos[a][1], pos[b][1], None]
    x, y, size, color, label, hover = [], [], [], [], [], []
    roots = {n for n, d in graph.in_degree() if d == 0}
    for n in graph.nodes:
        x.append(float(pos[n][0])); y.append(float(pos[n][1]))
        outd = graph.out_degree(n)
        size.append(float(8 + min(outd, 30) * 2.2))
        if str(n) in ignition_nodes:
            color.append("#ff5b7f")
        elif n in roots:
            color.append("#ffb84d")
        elif outd >= 5:
            color.append("#2ee9ff")
        else:
            color.append("#5d7cff")
        label.append(str(n) if outd >= 5 or n in roots or str(n) in ignition_nodes else "")
        hover.append(f"节点 {n}<br>用户 {graph.nodes[n].get('user_id')}<br>出度 {outd}<br>入度 {graph.in_degree(n)}")
    return {"x": x, "y": y, "edge_x": edge_x, "edge_y": edge_y, "size": size, "color": color, "label": label, "hover": hover}


def _participant_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>暂无参与者数据</p>"
    cols = ["event_id", "user_id", "screen_name", "followers_count", "verified", "post_count", "out_degree_sum", "pagerank_sum", "role"]
    cols = [col for col in cols if col in df.columns]
    view = df.sort_values(["pagerank_sum", "out_degree_sum"], ascending=False)[cols].head(18).copy()
    view["pagerank_sum"] = view["pagerank_sum"].map(lambda x: f"{x:.4f}")
    return view.to_html(index=False, escape=False)


def _ignition_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>暂无引爆点</p>"
    cols = ["event_id", "node_id", "user_id", "timestamp", "score", "reason"]
    view = df.sort_values("score", ascending=False)[cols].head(18).copy()
    view["score"] = view["score"].map(lambda x: f"{x:.2f}")
    return view.to_html(index=False, escape=False)


def _path_html(event: Optional[PropagationEvent]) -> str:
    if not event:
        return "<p>暂无路径数据</p>"
    rows = key_paths(event, 10)
    if not rows:
        return "<p>暂无路径数据</p>"
    html = "<table><thead><tr><th>排名</th><th>长度</th><th>传播链路</th></tr></thead><tbody>"
    for i, row in enumerate(rows, 1):
        html += f"<tr><td>{i}</td><td>{row['length']}</td><td>{' → '.join(map(str, row['nodes']))}</td></tr>"
    return html + "</tbody></table>"


def _dashboard_narrative(summaries: List[Dict], ignitions: pd.DataFrame, prediction_report: Optional[Dict]) -> str:
    if not summaries:
        return "暂无可展示事件。"
    largest = max(summaries, key=lambda s: s["node_count"])
    deepest = max(summaries, key=lambda s: s["max_depth"])
    text = (
        f"系统共处理 <b>{len(summaries)}</b> 个事件。最大级联为 <b>{largest['event_id']}</b>，"
        f"包含 <b>{largest['node_count']}</b> 个传播节点；最深传播链来自 <b>{deepest['event_id']}</b>，"
        f"深度为 <b>{deepest['max_depth']}</b>。引爆点模块发现 <b>{0 if ignitions.empty else len(ignitions)}</b> 个候选关键节点。"
    )
    if prediction_report:
        size = prediction_report.get("size_prediction", {})
        path = prediction_report.get("path_prediction", {})
        if size.get("status") == "ok":
            text += f" 规模预测 RMSE 为 <b>{size.get('rmse', 0):.2f}</b>，MAPE 为 <b>{size.get('mape_percent', 0):.2f}%</b>。"
        if path.get("status") == "ok":
            text += f" 路径预测 AUC 为 <b>{path.get('auc', 0):.3f}</b>。"
    return text


def _write_event_report_markdown(out: Path, summaries: List[Dict], participants: pd.DataFrame, ignitions: pd.DataFrame, representative: Optional[PropagationEvent], prediction_report: Optional[Dict]) -> None:
    lines = ["# 传播分析专业报告", "", "## 1. 总览", ""]
    lines.append(_dashboard_narrative(summaries, ignitions, prediction_report).replace("<b>", "**").replace("</b>", "**"))
    lines += ["", "## 2. 重点事件", ""]
    for s in sorted(summaries, key=lambda x: x["node_count"], reverse=True)[:10]:
        lines.append(f"- `{s['event_id']}`：规模 {s['node_count']}，深度 {s['max_depth']}，宽度 {s['max_width']}，参与者 {s['participant_count']}。")
    lines += ["", "## 3. 关键参与者", ""]
    if not participants.empty:
        for _, r in participants.sort_values(["pagerank_sum", "out_degree_sum"], ascending=False).head(10).iterrows():
            lines.append(f"- 用户 `{r['user_id']}`：角色 {r['role']}，发帖 {r['post_count']}，出度贡献 {r['out_degree_sum']}。")
    lines += ["", "## 4. 引爆点", ""]
    if not ignitions.empty:
        for _, r in ignitions.sort_values("score", ascending=False).head(10).iterrows():
            lines.append(f"- 事件 `{r['event_id']}` 节点 `{r['node_id']}`：分数 {r['score']:.2f}，原因：{r['reason']}。")
    lines += ["", "## 5. 传播路径", ""]
    if representative:
        for row in key_paths(representative, 10):
            lines.append(f"- 长度 {row['length']}：" + " → ".join(map(str, row["nodes"])))
    (out / "event_report.md").write_text("\n".join(lines), encoding="utf-8")
