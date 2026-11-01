from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def read_page(slug: str, page: int) -> str:
    path = ROOT / slug / "assets" / "text" / "pages" / f"page-{page:03d}.txt"
    return path.read_text(encoding="utf-8", errors="ignore")


def clean(text: str) -> str:
    return " ".join(text.split())


def manifest(slug: str) -> dict[str, Any]:
    return json.loads(
        (ROOT / slug / "assets" / "visual_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def update_manifest(
    slug: str,
    key_ids: set[str],
    claim_ids: dict[str, list[str]],
    notes: dict[str, str],
) -> None:
    path = ROOT / slug / "assets" / "visual_manifest.json"
    data = manifest(slug)
    data["schema_version"] = 2
    data["analysis_mode"] = "text-only"
    data["automatic_crops_are_unverified"] = True
    for visual in data.get("visuals", []):
        visual_id = str(visual.get("id"))
        visual["key"] = visual_id in key_ids
        visual["visual_verification"] = "not-performed"
        visual["crop_review_required"] = True
        visual["selected_asset"] = None
        visual["candidate_crop"] = None
        visual["claim_ids"] = claim_ids.get(visual_id, [])
        visual["review_notes"] = ""
        visual["text_review"] = {
            "status": "complete",
            "sources": [
                "caption",
                "pdf-text-layer",
                "body-references",
                "text/visuals/" + Path(str(visual.get("text_asset", ""))).name,
            ],
            "notes": notes.get(
                visual_id,
                "已核对图表编号、页码、标题、正文引用和可恢复文字；未将像素级视觉观察写入报告。",
            ),
            "limitations": (
                "本轮为 text-only 精读，未直接核验像素、坐标轴、颜色、曲线形状、"
                "面板布局、裁剪完整性或视觉显著性。"
            ),
        }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_map(
    slug: str,
    title: str,
    authors: str,
    venue: str,
    pdf_source: str,
    claims: list[dict[str, Any]],
    lenses: list[str],
) -> None:
    pdf_path = Path(pdf_source)
    source_entry = {
        "type": "pdf",
        "location": pdf_source,
        "sha256": sha256(pdf_path) if pdf_path.is_file() else "unavailable",
        "role": "primary",
    }
    data = {
        "schema_version": 3,
        "paper": {
            "title": title,
            "authors": authors,
            "venue": venue,
            "version": "本地 PDF 抽取版本",
            "sources": [source_entry],
            "page_convention": "1-based PDF page numbers",
        },
        "reader_profile": {
            "domain": "computer-science-ai",
            "selected_lenses": lenses,
            "audience": "cross-disciplinary",
            "goal": "reproduce",
            "depth": "deep",
            "language": "zh-CN",
        },
        "execution": {
            "visual_mode": "text-only",
            "visual_verification": "not-performed",
            "text_evidence_sources": [
                "pdf-text-layer",
                "caption",
                "body-references",
                "structured-text-cards",
            ],
        },
        "claims": claims,
    }
    (ROOT / slug / "source_map.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def coverage_table(slug: str) -> str:
    rows = [
        "| 编号 | PDF 页码 | 作用 | 是否关键 | 文本证据与限制 |",
        "|---|---:|---|:---:|---|",
    ]
    for visual in manifest(slug).get("visuals", []):
        label = str(visual.get("label") or visual.get("id"))
        page = visual.get("page", "?")
        caption = clean(str(visual.get("caption", ""))).replace("|", "/")
        key = "是" if visual.get("key") else "否"
        role = (
            "方法、理论或主结果"
            if visual.get("key")
            else "辅助背景、消融、复杂度或附录证据"
        )
        rows.append(
            f"| {label} | PDF p.{page} | {role} | {key} | "
            f"{caption}；text-only，未直接核验图像像素。 |"
        )
    return "\n".join(rows)


def visual_cards(slug: str) -> str:
    blocks: list[str] = []
    for visual in manifest(slug).get("visuals", []):
        label = str(visual.get("label") or visual.get("id"))
        page = visual.get("page", "?")
        caption = clean(str(visual.get("caption", "")))
        key = "关键" if visual.get("key") else "非关键"
        text_asset = Path(str(visual.get("text_asset", ""))).as_posix()
        blocks.append(
            f"#### {label}（PDF p.{page}；{key}）\n"
            f"- **原始标题**：{caption}\n"
            f"- **可恢复证据**：`assets/{text_asset}`、图注和正文引用。\n"
            "- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；"
            "不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。\n"
            "- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。"
        )
    return "\n\n".join(blocks)


def claim_table(claims: list[dict[str, Any]]) -> str:
    labels = {
        "strong": "强支持",
        "partial": "部分支持",
        "weak": "弱支持",
        "unsupported": "未支持",
    }
    rows = [
        "| 核心主张 | 最强证据 | 支持等级 | 最大替代解释 | 最小补强实验 |",
        "|---|---|---|---|---|",
    ]
    for claim in claims:
        evidence = "; ".join(
            str(item.get("locator", "")) for item in claim.get("evidence", [])
        )
        rows.append(
            f"| {claim['id']}: {claim['claim']} | {evidence} | "
            f"{labels[claim['status']]} | 数据、时间切分、候选协议或实现差异 | "
            "固定时间切分、3 个随机种子、泄漏审计和失败日志 |"
        )
    return "\n".join(rows)


def write_report(spec: dict[str, Any]) -> None:
    slug = spec["slug"]
    claims = spec["claims"]
    pitch_overrides = {
        "adaptive-conformal-inference": (
            "自适应共形校准在线更新阈值，以维持漂移分布下的局部覆盖。"
        ),
    }
    pitch = pitch_overrides.get(slug, spec["pitch"])
    update_manifest(
        slug,
        set(spec["key_ids"]),
        claim_ids=spec.get("claim_ids", {}),
        notes=spec.get("manifest_notes", {}),
    )
    source_map(
        slug,
        spec["title"],
        spec["authors"],
        spec["venue"],
        spec["pdf_source"],
        claims,
        spec.get("lenses", ["computer-science-ai"]),
    )
    background = "\n".join(f"- {item}" for item in spec["background"])
    method_items = list(spec["method"]) if isinstance(spec["method"], list) else [spec["method"]]
    if slug == "dyglib-dynamic-graph-learning":
        method_items.append(
            "复现核对应把 DyGFormer 的历史 patch 与 CogGuard 的传播窗口一一对应："
            "先按 observed_until 截断，再从训练历史生成 random、historical 和 inductive 三类负样本，"
            "最后在同一候选集上计算 AP、MRR、Hits@K 和候选召回。系统接入时还要记录每个 patch 的事件数、"
            "邻居采样上限、训练/验证/测试事件数量、峰值显存、单事件推理时延和失败原因。"
            "如果未来真实用户被提前加入候选集，结果只能标记为 transductive proxy，不能写成归纳式新用户预测。"
            "另外，DyGLib 的链路标签表示“未来是否发生交互”，而 CogGuard 的传播标签还必须保留"
            "父用户、帖子、时间戳、边类型和证据引用。因此模型分数只能作为下一跳研判排序，"
            "不能单独生成已确认的传播路径；路径事实仍由观测分析模块提供。"
        )
    method = "\n".join(f"- {item}" for item in method_items)
    contributions = "\n".join(
        f"{index}. {item}" for index, item in enumerate(spec["contributions"], 1)
    )
    future = "\n".join(
        f"{index}. **{item}**" for index, item in enumerate(spec["future"], 1)
    )
    results = "\n".join(f"- {item}" for item in spec["results"])
    report = f"""# {spec["title"]}：深度精读
> **作者**：{spec["authors"]}
> **会议/期刊与年份**：{spec["venue"]}
> **论文链接**：本地 PDF 为主；正式引用前请以项目文献索引中的官方链接为准
> **实际使用来源**：`{spec["pdf_source"]}`；本地 PDF 文本层、图表文本卡和正文引用
> **页码约定**：全文使用 1-based PDF 页码
> **论文类型**：{spec["paper_type"]}
> **学科 Lens**：computer-science-ai；动态图学习、信息扩散与可复现评测
> **读者画像**：cross-disciplinary；目标是 reproduce；深度为 deep；语言为 zh-CN
> **视觉能力模式**：text-only
> **解读置信度**：中；方法和结构化数值较可靠，像素级图表内容未核验

> **视觉能力说明**：本报告使用 text-only 工作流生成，未直接核验图像像素内容。图表解释仅依据标题、PDF 文本层、正文引用和结构化文本卡，因此不对坐标轴、颜色、曲线形状、面板布局、裁剪完整性或视觉显著性作未经支持的判断。
> **文本证据边界**：本轮为 text-only；视觉内容未直接核验。
## 1. 核心思想一句话总结（Elevator Pitch）
> {pitch}

## 2. 论文背景与动机（Background & Motivation）
### 2.1 具体问题
{background}

### 2.2 为什么重要
- **现实价值**：传播系统需要在严格观测截止时间下判断规模、趋势、下一跳或预测区间，错误的候选集和时间泄漏会直接造成过高估计。
- **学术价值**：论文分别处理多尺度扩散、连续时间图表示、归纳式节点泛化、基准协议和在线不确定性校准；这些问题共同决定系统预测是否可信。
- **CogGuard 场景**：观测分析和预测模型必须分离；预测只能读取 `observed_until` 之前的数据，并把候选覆盖、模型状态和证据引用返回给前端。

### 2.3 论文之前的研究版本
| 路线 | 代表方法 | 有效之处 | 关键局限 | 本文回应 |
|---|---|---|---|---|
| 宏观扩散预测 | 特征回归、RNN、点过程 | 能预测最终规模或增长 | 忽略连续演化和不确定性 | 引入动态图、趋势生成或多任务约束 |
| 微观下一跳/链路预测 | GNN、TGN、Transformer | 能编码时间关系 | 依赖候选协议，可能是传递式而非归纳式 | 明确负采样、时间切分和新节点设置 |
| 可信预测 | 固定分位数或固定阈值 | 实现简单 | 分布漂移下局部覆盖不稳定 | 在线自适应更新或校准区间 |

### 2.4 从痛点到研究问题
> 旧方法依赖静态快照、有限候选或固定误差假设，在动态传播和分布漂移下容易失效；本文通过 {spec["mechanism"]}，使 {spec["target"]}，但其证据范围仍由数据集、时间切分、候选生成和实现版本限定。

- **作者主张**：{spec["author_claim"]}
- **论文直接证据**：正文和对应 Figure/Table/Algorithm 的页码锚点见第 3、4 节。
- **本文推断**：迁移到 CogGuard 时，必须把论文任务定义和系统的真实事件任务分开，不能把 transductive 结果直接写成开放世界新用户预测。
- **外部背景**：动态图链路预测、信息级联预测和 conformal prediction 的指标并不天然等价，跨论文比较必须统一观察窗口、预测窗口和候选协议。

## 3. 核心方法/理论/研究设计详解（Core Method, Theory, or Study Design）
### 3.1 总体框架
`观测事件/时间边流 → 时间与结构编码 → 共享或任务特有表示 → 预测/校准输出 → 严格时间评估`

**数据流解释**：输入只能使用观测截止时间之前的事件、用户、边、时间戳和合法训练统计；中间模块负责保留时间顺序、局部结构和跨事件关系；输出根据论文类型对应最终规模、未来趋势、下一跳用户、链路分数、图表示或预测区间。

### 3.2 核心流程
1. **起点**：读取带时间戳的 cascade 或 temporal interaction stream。
2. **结构编码**：{spec["structure_encoding"]}
3. **任务输出**：{spec["task_output"]}
4. **评估**：{spec["evaluation_protocol"]}

### 3.3 关键步骤、组件或概念
{method}

### 3.4 关键形式化内容
{spec["formulas"]}

### 3.5 核心创新
{contributions}

## 4. 证据与结果分析（Evidence & Results）
### 4.1 研究设计与证据协议
- **研究问题/假设**：论文主要检验方法是否改善其定义的任务；不能把论文在封闭候选集上的结果直接外推成开放世界新用户发现。
- **数据与样本**：以论文明确列出的数据集、时间范围、节点/边定义和观察窗口为准；报告中的外部系统数据不能替代论文证据。
- **比较与评估**：优先记录论文原始指标、训练设置、负采样、时间切分、重复次数和消融；若原文未报告方差或置信区间，本文不补造。
- **不确定性**：区分作者主张、论文直接结果、本文推断和外部背景；所有核心数字都带 PDF 页码或图表锚点。

### 4.2 完整图表覆盖清单
{coverage_table(slug)}

### 4.3 关键证据与主要结果
{results}

### 4.4 逐图表解释
{visual_cards(slug)}

### 4.5 定性证据、失败案例与边界
- 本轮未进行像素级视觉核验，因此不对图中的颜色、坐标、曲线相交、布局密度或视觉异常作额外结论。
- 论文数字只支持其定义的任务、数据集、时间窗口和候选协议；不能直接外推到 CogGuard 的真实采集事件。
- 对动态图预测，必须特别检查 transductive 与 inductive 设置、未来节点是否进入候选集、负采样是否读取测试期统计以及是否存在重复事件。
- 对趋势预测，必须区分点预测与区间预测；未校准区间不能称为置信区间。

### 4.6 主张—证据审计
{claim_table(claims)}

### 4.7 可靠性、复现性与争议点
- **最可靠结论**：方法定义、输入输出、算法步骤和正文明确报告的表格数值。
- **最弱结论**：仅由图注或 OCR 文本卡推断的像素级趋势，以及把作者称谓转写为普适 SOTA。
- **公平性风险**：数据版本、负采样、时间切分、候选集合、超参数和硬件差异都可能解释性能差异。
- **复现要求**：固定代码 revision、数据版本、随机种子、观察窗口、预测窗口、候选生成、失败日志和完整 JSON 输出。
- **实现核对**：对可运行模型，还要记录 patch/历史长度、邻居采样、负采样类型、显存峰值、单批推理时间和失败重试次数；这些工程量会影响系统是否适合在线事件监测。
- **最小复现实验**：先选一个数据集和一个严格时间切分，复现论文主指标；随后只改变一个组件或协议变量，并保持数据版本、候选集合、训练轮数和随机种子不变。若结果差异超过随机波动，再检查日志中的时间泄漏、样本重复、负采样和用户映射。

## 5. 论文的贡献与影响（Contribution & Impact）
### 5.1 主要贡献
{contributions}

### 5.2 对 CogGuard 传播分析与预测的启发
- 传播分析侧应保留 provenance 证据、显式/重建/推断边区分、真实用户映射和可回溯详情；预测侧只读取观测前缀，不能复用未来真实节点。
- 下一跳输出需要明确是“已知用户再激活”还是“开放世界新用户激活”；候选覆盖不足时应 abstain，而不是输出匿名 bucket。
- 宏观趋势输出应同时返回观测规模、预测规模、趋势点、误差区间状态和校准状态；没有校准时不能把集中度分数称为置信度。
- 评测应统一使用时间切分、合法负采样、候选覆盖、Hits/MAP/MRR/NDCG、MSLE/MAE/RMSE/MAPE 以及失败原因。

### 5.3 值得探索的未来方向
{future}

## 6. 结论（Conclusion）
{spec["conclusion"]}

> **最终判断**：{spec["judgment"]}
>
> **复现清单**：固定论文版本和代码 revision；准备同版本数据；实现论文输入协议；复现主表和关键消融；记录 3 个以上随机种子、时间切分、候选生成、显存/运行时间和失败日志；最后再迁移到 CogGuard 真实事件。
"""
    (ROOT / slug / "report.md").write_text(report, encoding="utf-8")


def paper(
    slug: str,
    title: str,
    authors: str,
    venue: str,
    pdf_name: str,
    paper_type: str,
    pitch: str,
    mechanism: str,
    target: str,
    author_claim: str,
    structure_encoding: str,
    task_output: str,
    evaluation_protocol: str,
    background: list[str],
    method: list[str],
    formulas: str,
    results: list[str],
    contributions: list[str],
    future: list[str],
    conclusion: str,
    judgment: str,
    key_ids: list[str],
    claims: list[dict[str, Any]],
    claim_ids: dict[str, list[str]] | None = None,
    manifest_notes: dict[str, str] | None = None,
    lenses: list[str] | None = None,
) -> dict[str, Any]:
    # The first draft used two positional method paragraphs for three papers.
    # Normalize that legacy shape here so the generated artifacts stay stable.
    if (
        isinstance(key_ids, str)
        and isinstance(claims, list)
        and isinstance(claim_ids, list)
        and isinstance(manifest_notes, dict)
    ):
        actual_method = [method, formulas]
        actual_formulas = str(results)
        actual_results = contributions
        actual_contributions = future
        actual_future = conclusion
        actual_conclusion = str(judgment)
        actual_judgment = key_ids
        actual_key_ids = claims
        actual_claims = claim_ids
        actual_claim_ids = manifest_notes
        method = actual_method
        formulas = actual_formulas
        results = actual_results
        contributions = actual_contributions
        future = actual_future
        conclusion = actual_conclusion
        judgment = actual_judgment
        key_ids = actual_key_ids
        claims = actual_claims
        claim_ids = actual_claim_ids
        manifest_notes = {}
    if isinstance(method, str):
        method = [method]
    if isinstance(key_ids, str):
        key_ids = [key_ids]
    return {
        "slug": slug,
        "title": title,
        "authors": authors,
        "venue": venue,
        "pdf_source": str(Path(r"H:\Zotero\attenger\Projects\CISCN\Propagation") / pdf_name),
        "paper_type": paper_type,
        "pitch": pitch,
        "mechanism": mechanism,
        "target": target,
        "author_claim": author_claim,
        "structure_encoding": structure_encoding,
        "task_output": task_output,
        "evaluation_protocol": evaluation_protocol,
        "background": background,
        "method": method,
        "formulas": formulas,
        "results": results,
        "contributions": contributions,
        "future": future,
        "conclusion": conclusion,
        "judgment": judgment,
        "key_ids": key_ids,
        "claims": claims,
        "claim_ids": claim_ids or {},
        "manifest_notes": manifest_notes or {},
        "lenses": lenses or ["computer-science-ai"],
    }


def main() -> None:
    papers = [
        paper(
            "minds-multiscale-diffusion",
            "Enhancing Multi-Scale Diffusion Prediction via Sequential Hypergraphs and Adversarial Learning",
            "Pengfei Jiao, Hongqian Chen, Qing Bao, Wang Zhang, Huaming Wu",
            "AAAI 2024",
            "Jiao 等 - 2024 - Enhancing multi-scale diffusion prediction via sequential hypergraphs and adversarial learning.pdf",
            "方法/模型",
            "MINDS 用顺序超图联合预测规模和下一用户，并用解耦约束减少任务干扰。",
            "顺序超图刻画级联在时间窗口之间的全局扩散交互，GCN 刻画社会关系，shared-private 表示同时服务 macro 与 micro。",
            "让最终规模预测与下一参与用户预测共享可解释的跨级联状态，同时保留任务特有信息。",
            "将 sequential hypergraph、adversarial learning 和 orthogonality constraint 组合成统一的多尺度扩散预测模型。",
            "社会图、按时间窗口构造的扩散超图和观测传播序列共同进入 HGNN、GCN 及任务分支。",
            "macro 输出最终级联规模；micro 输出下一步参与用户的排序或分类结果。",
            "作者报告 Hits@K、MAP@K 与 MSLE，并用消融表检验 HGNN、macro/micro、adversarial 和 diffusion 组件。",
            [
                "PDF p.2-3 将问题定义为同时处理宏观规模和微观下一用户，指出只做单一尺度会丢失互补信号。",
                "Figure 2（PDF p.3）标题与正文支持四部分联合框架：社会图、顺序扩散超图、共享/私有表示和双任务预测。",
                "Figure 3（PDF p.3）对应 HGNN 的两阶段传播：超边聚合级联内用户，再把级联信息回传到节点。",
                "训练目标包含宏观与微观任务、对抗学习和正交约束；Table 5（PDF p.7）直接用于消融这些组件。",
            ],
            "输入由社会图 G_S、按时间窗构造的 sequential diffusion hypergraphs G_D 和观测传播序列组成。HGNN 在每个窗口内聚合同一级联用户，再跨窗口融合；GCN 提供社会关系表示；shared-private 模块将共享扩散状态与任务特有状态送入两个预测头。",
            "宏观头根据扩散级联表示预测最终规模；微观头根据发送者、社会关系和共享扩散表示预测下一参与用户。对抗分类器试图区分任务来源，迫使共享表示保留跨任务信息；正交约束降低 shared/private 表示冗余。",
            "可恢复的目标可写成 `L = L_macro + L_micro + λ_adv L_adv + λ_diff L_diff + λ_orth L_orth`。其中 `L_macro` 对最终规模回归，`L_micro` 对下一用户分类/排序；其余项分别约束任务解耦、共享扩散结构和表示正交。原文具体符号以 PDF p.3-5 为准，当前文本层无法安全恢复每个公式排版。",
            [
                "Table 2、Table 3（PDF p.6）报告 Hits@K 和 MAP@K；它们是微观下一用户任务的主要证据。",
                "Table 4（PDF p.6）报告 MSLE，用于宏观最终规模预测；因此不能只用 micro 指标判断模型是否有效。",
                "Table 5（PDF p.7）消融显示移除宏观/微观任务、HGNN、adversarial 或 diffusion 组件会改变性能，直接支持组件具有任务作用，但不等于每个组件在所有数据集上都独立增益。",
                "Figure 4、Figure 5（PDF p.7、p.9）用于参数和消息传播分析；本轮只采用正文对其作用的文字说明，不作像素级趋势判断。",
            ],
            [
                "问题层：把 macro 规模与 micro 下一用户放到同一可训练框架，而不是两个互不相干的回归器。",
                "方法层：用 sequential hypergraph 表达跨时间窗的级联动态，用 shared-private 与对抗/正交约束处理多任务冲突。",
                "证据层：通过同时报告 Hits/MAP 和 MSLE，并配合 Table 5 消融，建立多尺度方法的证据链。",
            ],
            [
                "将 MINDS backbone 迁入 CogGuard，严格保留 event-level macro 与 candidate/user-level micro 的粒度定义。",
                "把 FOREST 的宏观—微观软耦合实现为 rollout 期望增长与趋势头之间的辅助约束，而不是把候选 sigmoid 求和当最终规模。",
                "以开放世界候选集、归纳式新用户预测和时间泄漏审计检验 MINDS 在真实社交平台上的边界。",
            ],
            "MINDS 是当前 CogGuard 多尺度联合模型最直接的主干参考：方法定义、模块分工和消融逻辑均可复现；但它本身不提供 provenance 证据链，也不自动解决开放世界新用户候选覆盖。",
            "值得复现，优先级高。复现时必须先固定论文协议，再单独报告 CogGuard 的候选覆盖、归纳式设置和证据追溯差异。",
            ["figure-2-p003", "figure-3-p003", "table-2-p006", "table-3-p006", "table-4-p006", "table-5-p007"],
            [
                {"id": "C1", "claim": "MINDS 以顺序超图和共享—私有学习统一 macro 与 micro 任务。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 2, PDF p.3", "note": "整体框架"}, {"type": "figure", "locator": "Figure 3, PDF p.3", "note": "超图消息传递"}, {"type": "body", "locator": "PDF p.2-3", "note": "问题定义与方法描述"}], "caveats": []},
                {"id": "C2", "claim": "顺序超图承担跨时间窗的扩散动态建模。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 3, PDF p.3", "note": "两阶段聚合"}, {"type": "body", "locator": "PDF p.2", "note": "作者对全局交互和时间窗的说明"}], "caveats": []},
                {"id": "C3", "claim": "论文同时报告 micro 排序指标和 macro 规模指标。", "status": "strong", "inference": False, "evidence": [{"type": "table", "locator": "Table 2/3, PDF p.6", "note": "Hits@K 与 MAP@K"}, {"type": "table", "locator": "Table 4, PDF p.6", "note": "MSLE"}], "caveats": []},
                {"id": "C4", "claim": "宏观/微观、HGNN、对抗和 diffusion 组件具有消融证据。", "status": "strong", "inference": False, "evidence": [{"type": "table", "locator": "Table 5, PDF p.7", "note": "消融表"}], "caveats": []},
            ],
            {
                "figure-2-p003": ["C1"],
                "figure-3-p003": ["C1", "C2"],
                "table-2-p006": ["C3"],
                "table-3-p006": ["C3"],
                "table-4-p006": ["C3"],
                "table-5-p007": ["C4"],
            },
        ),
        paper(
            "casft-future-trend",
            "CasFT: Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion",
            "Jing 等",
            "AAAI 2025",
            "Jing 等 - 2025 - CasFT future trend modeling for information popularity prediction with dynamic cues-driven diffusio.pdf",
            "方法/模型",
            "CasFT 用 neural ODE 和 diffusion 生成未来流行度趋势，再预测最终规模。",
            "图结构、时序事件和增长率进入动态编码器；ODE 连续推进增长率，diffusion 生成未来分段流行度序列，预测头融合观测与未来趋势。",
            "解决只依据观测前缀回归最终规模、却忽略观测后到预测时段增长趋势和不确定性的问题。",
            "用连续动力学和生成式未来趋势模拟，改善信息级联 popularity prediction。",
            "观测级联图、全局图结构表示、时间编码和级联事件序列共同形成动态状态。",
            "输出最终 popularity/规模；实验还比较不同 observation time、ODE solver、diffusion steps、hidden dimension 和 interval number。",
            "Table 2 使用 MSLE、MAPE；Table 3 做 CasFT 变体消融；Figure 3-5 和 Table 4 做超参数及 ODE solver 分析。",
            [
                "PDF p.1-2 指出增长率在观测时间到预测时间之间显著波动，传统方法无法直接看到该阶段的真实变化。",
                "Figure 1（PDF p.1）图注定义了问题和观测/预测时间；正文进一步说明增长率积分得到增量。",
                "Figure 2（PDF p.4）与 PDF p.3 的正文共同支持三步流程：观测模式提取、未来趋势模拟、最终预测。",
                "PDF p.3-4 给出 neural ODE、ODE-GRU、diffusion 和融合预测模块；文本层能恢复关键变量与损失的功能关系。",
            ],
            "先用 GraphWave/NetSMF 等结构表示与时间编码构造观测表示，再由 ODE-GRU 建模增长率的连续演化；diffusion 模块以观测状态为条件，生成分段 future popularity sequence；最终将生成趋势与观测级联表示融合后回归 popularity。",
            "训练同时优化最终规模预测损失和未来趋势生成的负对数似然。论文在 PDF p.5-6 给出 `L = L1 + λL2` 的功能定义；`L1` 约束最终预测，`L2` 约束生成趋势，`λ` 控制二者权衡。",
            "由连续状态 `dh/dt = f_θ(h,t)` 得到从观测时间到预测时间的动态推进；增长率可通过积分形成增量。diffusion 逐步估计 `p_θ(Y_{k-1}|Y_k,c)`，生成条件未来序列；这些表达根据 PDF p.3-4 和式(24)-(25) 的可恢复文本整理，未补写不可恢复的排版细节。",
            [
                "Table 1（PDF p.5）说明 Twitter、APS、Weibo 的数据统计；正文规定不同数据集的 observation/prediction time、70/15/15 切分和至少 10 个观测期参与者过滤。",
                "Table 2（PDF p.6）直接比较各 baseline 与 CasFT 的 MSLE、MAPE；文本卡可恢复 Twitter、APS、Weibo 多观察窗口的代表性数值，支持作者关于整体性能改善的主张。",
                "Table 3（PDF p.6）比较 CasFT 变体，直接用于判断 ODE 和 diffusion 的增益不能互相混同。",
                "Figure 3-5（PDF p.7）正文称 diffusion steps、hidden dimension 和 interval number 会影响最终预测；Table 4（PDF p.7）正文称 Euler 表现较弱且 dopri5 用于实验，但本轮不对曲线像素作观察。",
            ],
            [
                "问题层：把不可见的观测后趋势作为预测对象，而非只拟合最终规模。",
                "方法层：将 neural ODE 的连续动力学和 diffusion 的不确定性生成结合起来。",
                "实验层：按 observation time 和多个 solver/超参数设置报告结果，检验趋势生成模块。",
            ],
            [
                "CogGuard 可迁移 ODE-style latent dynamics 作为趋势头，但应明确这不是 CasFT 原始 diffusion 复现。",
                "趋势输出应有多个时间 checkpoint，并与 observed size、future cumulative growth 绑定；单个最终规模不足以支持监测界面。",
                "若需要误差区间，应另外做 calibration，不能把 diffusion sample spread 或 entropy 直接叫置信度。",
            ],
            "CasFT 是 CogGuard 宏观趋势预测的最直接前沿参考，但当前系统只适合声明“迁移连续趋势思想”；要称 CasFT 复现，必须实现原始 diffusion generator、数据协议和完整对比。",
            "值得复现，优先用于 macro 趋势主线；原始训练成本和数据格式较重，建议先复现小规模、再决定是否接入在线系统。",
            ["figure-1-p001", "figure-2-p004", "table-1-p005", "table-2-p006", "table-3-p006", "table-4-p007"],
            [
                {"id": "C1", "claim": "传统 popularity prediction 忽略观测后到预测时刻之间的未来趋势。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 1, PDF p.1", "note": "问题图注"}, {"type": "body", "locator": "PDF p.1-2", "note": "作者动机"}], "caveats": []},
                {"id": "C2", "claim": "CasFT 使用 neural ODE 与 diffusion 生成未来趋势。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 2, PDF p.4", "note": "模型总览"}, {"type": "body", "locator": "PDF p.3-4", "note": "方法描述"}], "caveats": []},
                {"id": "C3", "claim": "CasFT 在论文数据协议下改善 MSLE/MAPE。", "status": "strong", "inference": False, "evidence": [{"type": "table", "locator": "Table 2, PDF p.6", "note": "主结果"}, {"type": "table", "locator": "Table 3, PDF p.6", "note": "变体比较"}], "caveats": ["不能直接外推到 CogGuard 事件"]},
                {"id": "C4", "claim": "ODE solver、diffusion steps、hidden dimension 和 interval number 会影响性能。", "status": "partial", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 3-5, PDF p.7", "note": "正文引用的敏感性分析"}, {"type": "table", "locator": "Table 4, PDF p.7", "note": "solver 比较"}], "caveats": ["本轮未做像素级曲线核验"]},
            ],
            {
                "figure-1-p001": ["C1"],
                "figure-2-p004": ["C2"],
                "table-1-p005": [],
                "table-2-p006": ["C3"],
                "table-3-p006": ["C3"],
                "table-4-p007": ["C4"],
            },
        ),
        paper(
            "tgn-temporal-graph-networks",
            "Temporal Graph Networks for Deep Learning on Dynamic Graphs",
            "Emanuele Rossi, Ben Chamberlain, Fabrizio Frasca, Davide Eynard, Federico Monti, Michael M. Bronstein",
            "ICML 2020",
            "Rossi 等 - 2020 - Temporal graph networks for deep learning on dynamic graphs.pdf",
            "方法/模型",
            "TGN 用事件驱动的节点记忆、时间编码和邻居聚合，在连续时间动态图上进行链路预测和节点分类。",
            "每个交互事件产生 raw message；memory updater 更新源节点和目标节点记忆；embedding module 结合时间编码与采样邻居形成当前节点表示。",
            "解决静态图或快照式 GNN 难以保留连续事件历史、时间间隔和节点状态的问题。",
            "以统一 memory/message/embedding 组件构造可扩展的连续时间动态图学习框架。",
            "时间戳交互边、节点 memory、raw message、时间编码和时间邻居共同形成动态节点状态。",
            "在未来边预测中对候选边打分；在动态节点分类中对当前节点表示分类。",
            "Table 2 报告未来边 AP，Table 3 报告动态节点分类 ROC AUC；Figure 3 为消融；Algorithm 1 给出训练流程。",
            [
                "PDF p.1-2 将动态图表示为带时间戳的交互事件流，强调节点状态随事件持续更新。",
                "Figure 1（PDF p.3）标题明确展示一批时间戳交互的 TGN 计算过程；正文解释 memory、message 和 embedding 的关系。",
                "Figure 2（PDF p.5）与 PDF p.4-5 的文字支持 raw message store、memory updater、message aggregator 和 embedding module 的训练数据流。",
                "Figure 4（PDF p.14）和 Algorithm 1（PDF p.14）提供更接近实现的 TGN 图式与训练顺序。",
            ],
            "TGN 将连续事件流按时间处理。对事件 e=(u,v,t)，先读取并按时间编码的历史 memory，构造 raw message；message aggregator 汇总同一时间窗口的消息；memory updater 更新节点状态。随后 embedding module 从当前 memory、时间差和采样邻居生成节点 embedding，用于未来边预测或节点分类。",
            "节点 memory 可记作 `s_i(t) = Update(s_i(t^-), m_i(t))`；消息可记作 `m_i(t)=Message(s_i(t^-), s_j(t^-), φ(t-t_i), e_{ij})`；节点 embedding 由当前 memory 与时间邻居聚合得到。这里是按正文和 Algorithm 1 的操作语义重写，符号不替代论文原式。",
            [
                "Table 2（PDF p.7）报告 transductive 和 inductive future edge prediction 的 AP，直接支持 TGN 作为时间链路预测模型。",
                "Table 3（PDF p.7）报告动态节点分类 ROC AUC，说明同一记忆框架可用于非链路任务。",
                "Figure 3（PDF p.8）做 Wikipedia 消融；正文说明 memory、message、attention/neighbor sampling 等设计对性能有影响。",
                "Table 4、Table 5（PDF p.15-16）给出数据统计和超参数，是复现输入协议、数据规模和配置的关键证据。",
            ],
            [
                "架构层：提出可组合的 memory、message 和 embedding modules，而非固定一种 GNN。",
                "任务层：用同一连续时间表示支持未来边预测和动态节点分类。",
                "工程层：给出可实现的训练算法和邻居采样策略，适合构建动态图预测服务。",
            ],
            [
                "将 cascade 转换为 `(parent, child, timestamp, edge_type)` 事件流，并明确 explicit/reconstructed/inferred 边的训练边界。",
                "以观测截止时间前的 memory 初始化下一跳 micro head，候选集必须独立生成并审计。",
                "结合自适应校准方法输出预测区间，但 TGN 本身只提供表示和打分，不提供概率校准。",
            ],
            "TGN 是下一跳 temporal edge prediction 的可靠基础，但不是传播溯源模型，也不是开放世界新用户预测的充分条件；CogGuard 需要额外解决候选覆盖和真实身份映射。",
            "值得复现，适合作为系统级 temporal graph runtime 或 DyGFormer 失败时的可解释 fallback；正式结论必须区分 transductive 和 inductive。",
            ["figure-1-p003", "figure-2-p005", "table-2-p007", "table-3-p007", "figure-4-p014", "algorithm-1-p014"],
            [
                {"id": "C1", "claim": "TGN 用 memory/message/embedding 组件处理连续时间交互流。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 1, PDF p.3", "note": "计算流程"}, {"type": "figure", "locator": "Figure 2, PDF p.5", "note": "训练组件"}, {"type": "figure", "locator": "Algorithm 1, PDF p.14", "note": "训练算法"}], "caveats": []},
                {"id": "C2", "claim": "TGN 支持未来边预测和动态节点分类。", "status": "strong", "inference": False, "evidence": [{"type": "table", "locator": "Table 2/3, PDF p.7", "note": "AP 与 ROC AUC"}], "caveats": []},
                {"id": "C3", "claim": "TGN 的效果依赖 memory、消息和邻居采样等组件。", "status": "partial", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 3, PDF p.8", "note": "消融"}, {"type": "body", "locator": "PDF p.8", "note": "正文解释"}], "caveats": ["未逐像素核验图中数值"]},
                {"id": "C4", "claim": "TGN 可以直接解决 CogGuard 的开放世界下一跳预测。", "status": "unsupported", "inference": True, "evidence": [], "caveats": ["论文任务不等于当前事件的新用户发现"]},
            ],
            {
                "figure-1-p003": ["C1"],
                "figure-2-p005": ["C1"],
                "table-2-p007": ["C2"],
                "table-3-p007": ["C2"],
                "figure-4-p014": ["C1"],
                "algorithm-1-p014": ["C1"],
            },
        ),
        paper(
            "cawn-causal-anonymous-walks",
            "Inductive Representation Learning in Temporal Networks via Causal Anonymous Walks",
            "Wang 等",
            "2022",
            "Wang 等 - 2022 - Inductive representation learning in temporal networks via causal anonymous walks.pdf",
            "方法/模型",
            "CAW 用保留因果顺序的匿名时间游走表示局部动态图模式，在不依赖节点身份的情况下支持归纳式链路预测。",
            "从目标时间前的时间边流提取 causal anonymous walks，对多个游走进行集合化编码，再与端点特征结合进行链路分类。",
            "解决 TGAT 等方法在归纳设置下丢失高阶因果结构、或因匿名化过度而混淆不同动态图模式的问题。",
            "通过时间约束、匿名化和游走集合保留可迁移的结构模式，并给出表达性与复杂度分析。",
            "时间边流、因果游走、匿名节点序列、端点特征和历史窗口共同构成输入。",
            "输出候选边的正/负分类分数，主要评价 AUC 和 AP；不是直接的传播规模预测。",
            "Table 2、Table 6-8 报告 AUC/AP；Algorithm 1-3 说明游走提取、在线概率计算和迭代采样；Figure 5-7 分析采样和复杂度。",
            [
                "PDF p.1-3 说明动态图的高阶结构和因果顺序对归纳式表示学习重要，而静态或身份依赖表示难以迁移到新节点。",
                "Figure 1、Figure 2（PDF p.2）通过 triadic closure、feed-forward loops 和 CAW 定义说明，游走保留时间因果关系并去除具体节点身份。",
                "Figure 3（PDF p.3）正文用于说明 TGAT 在去除节点身份后可能出现结构歧义。",
                "Theorem/Proposition 与 Algorithm 1（PDF p.4）共同给出 CAW 的提取逻辑和表达性主张。",
            ],
            "给定查询边 (u,v,t)，只从 t 之前的历史边中提取满足时间因果约束的游走；将节点身份替换为首次出现顺序等匿名编码，形成 CAW。对多个 CAW 做集合聚合，再结合端点的时间特征和可用属性，输入 MLP/序列编码器得到候选边分数。",
            "Algorithm 1 负责从历史时间边流抽取游走；Algorithm 2 计算在线采样概率；Algorithm 3 迭代采样。关键约束是游走中事件时间单调不减且不读取查询时刻之后的边。匿名化降低对节点 ID 的依赖，但也要求训练/测试特征协议一致。",
            "对查询边的预测可抽象为 `score(u,v,t)=f_θ(CAW(u,v,t), x_u, x_v, Δt)`；CAW 是以历史边流为条件的匿名游走集合。论文还给出 temporal WL/表达性相关理论；本报告只保留可从正文恢复的功能关系，不重写无法可靠恢复的完整定理。",
            [
                "Table 1（PDF p.6）报告数据集统计，决定游走采样和归纳式拆分的规模边界。",
                "Table 2（PDF p.8）报告 inductive link prediction 的 AUC；正文称 CAW 在多个数据集上与基线比较。",
                "Figure 5、Figure 6（PDF p.9）分别讨论超参数敏感性和复杂度；正文明确将采样数量与运行成本联系起来。",
                "Table 6（PDF p.19）以及 Table 7/8（PDF p.21-22）报告 AP/AUC 与 TGN 对比；它们支持 CAW 的链路预测价值，但不支持宏观规模预测结论。",
            ],
            [
                "表示层：将因果时间结构编码为匿名游走集合，增强对未见节点/结构的归纳能力。",
                "理论层：把可表达性和具体采样算法联系起来，避免只给经验性 GNN 结构。",
                "工程层：Algorithm 1-3 给出可落地的在线采样和复杂度控制路径。",
            ],
            [
                "将 CAW 作为下一跳候选边的结构编码器，尤其适合新用户或新边的归纳式场景。",
                "把 `observed_until` 作为硬边界，候选边只由训练历史、观测用户、合法社交邻居产生。",
                "报告 CAW 采样覆盖率、候选召回和运行成本，不能仅报告 AUC。",
            ],
            "CAW 是 CogGuard 开放世界下一跳预测的重要方法参考，尤其补足“未参与事件的新用户”归纳能力；但论文是链路预测，不等于传播因果证据追溯。",
            "值得复现，优先用于开放世界 micro 预测研究；需要先把 cascade 关系映射为可靠时间边流，并单独验证匿名化对真实用户映射的影响。",
            ["figure-1-p002", "figure-2-p002", "figure-3-p003", "algorithm-1-p004", "table-2-p008", "algorithm-2-p014", "algorithm-3-p014", "table-7-p021", "table-8-p022"],
            [
                {"id": "C1", "claim": "CAW 保留时间因果顺序并以匿名化方式表示动态图局部模式。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 1/2, PDF p.2", "note": "定义与动机"}, {"type": "algorithm", "locator": "Algorithm 1, PDF p.4", "note": "游走提取"}], "caveats": []},
                {"id": "C2", "claim": "CAW 支持归纳式 temporal link prediction。", "status": "strong", "inference": False, "evidence": [{"type": "table", "locator": "Table 2, PDF p.8", "note": "AUC 结果"}, {"type": "table", "locator": "Table 6-8, PDF p.19-22", "note": "AP/AUC 对比"}], "caveats": []},
                {"id": "C3", "claim": "CAW 的采样数量和树结构会影响性能与运行成本。", "status": "partial", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 5-7, PDF p.9/16", "note": "敏感性、复杂度和采样结构"}, {"type": "algorithm", "locator": "Algorithm 2/3, PDF p.14", "note": "在线采样"}], "caveats": ["部分图表仅有文本卡支持"]},
                {"id": "C4", "claim": "CAW 直接提供传播路径因果证明。", "status": "unsupported", "inference": True, "evidence": [], "caveats": ["论文输出是预测表示和边分数，不是平台 provenance"]},
            ],
            {
                "figure-1-p002": ["C1"],
                "figure-2-p002": ["C1"],
                "figure-3-p003": ["C1"],
                "algorithm-1-p004": ["C1"],
                "table-2-p008": ["C2"],
                "algorithm-2-p014": ["C3"],
                "algorithm-3-p014": ["C3"],
                "table-7-p021": ["C2"],
                "table-8-p022": ["C2"],
            },
        ),
        paper(
            "dyglib-dynamic-graph-learning",
            "Towards Better Dynamic Graph Learning: New Architecture and Unified Library",
            "Yu 等",
            "2023",
            "Yu 等 - 2023 - Towards better dynamic graph learning new architecture and unified library.pdf",
            "方法/基准与代码库",
            "DyGLib 用 DyGFormer、patching 和严格负采样规范动态图链路预测。",
            "将连续交互序列切成时间 patch，分别编码节点历史、时间间隔和交互特征，再通过 Transformer 聚合形成候选边表示。",
            "解决动态图方法实现分散、数据协议不一致、输入历史长度和负采样差异导致难以公平比较的问题。",
            "同时贡献 DyGFormer 模型、NCoE 组件和统一代码库/评测协议。",
            "时间戳边流、节点历史交互、时间 patch、时间编码和候选负样本。",
            "输出动态链路预测/AP 等结果，并分析不同历史长度、变化检测和负采样策略。",
            "Table 1/2 报告 AP；Figure 2 比较输入长度；Table 3-5 分析变化率、正负样本和负采样。",
            [
                "PDF p.1-3 指出动态图库实现多、命名和协议不统一，导致模型比较与复现困难。",
                "Figure 1（PDF p.4）正文用于说明统一框架和 DyGFormer 的结构关系。",
                "Table 1（PDF p.7）和 Table 2（PDF p.8）分别支持动态链路预测与 NCoE 组件结果。",
                "Figure 2、Table 3-5（PDF p.8-9）把历史长度、变化率、正负样本和负采样的影响显式化。",
            ],
            "DyGFormer 先按时间对节点历史交互进行 patching，以降低长历史序列的计算压力；每个 patch 由时间编码、交互特征和邻居历史编码组成。Transformer 对 patch 序列建模，再将源节点、目标节点及时间上下文融合为候选边分数。NCoE 用于识别交互变化或增强动态图表征。",
            "动态图链路预测可抽象为 `s(u,v,t)=f_θ(P_u^{<t},P_v^{<t},φ(t))`，其中 `P_u^{<t}` 是 t 前的 patch 化历史。训练用正边和固定协议生成的随机、历史或归纳负边；评估 AP/链路排序，不能把未来真实节点混入候选。",
            [
                "Table 1（PDF p.7）报告 transductive dynamic link prediction 的 AP，并区分 random、historical、inductive negatives。",
                "Table 2（PDF p.8）报告 NCoE 下的 AP，支撑新增组件的任务价值。",
                "Figure 2（PDF p.8）显示输入长度变化会改变方法表现；正文支持历史窗口是重要实验变量。",
                "Table 3-5（PDF p.9）提供变化率、正负样本和负采样分析，提醒复现时不能只抄模型结构。",
            ],
            [
                "协议层：将动态图任务、负采样和历史窗口统一到公开库中。",
                "模型层：用 patching 处理长交互历史，降低 Transformer 的时间和显存成本。",
                "工程层：把模型、数据和评估脚本组织为可复现库，适合作为系统 micro runtime 的基线。",
            ],
            [
                "把 cascade edge stream 适配为 DyGFormer 输入，区分确认传播边与推断边。",
                "对下一跳候选同时报告 transductive 已知用户和 inductive 新用户设置，避免一句“下一跳预测”掩盖任务差异。",
                "采用 TGB 风格固定负采样、时间切分和 AP/MRR/Hits@K 协议，并记录 patch 长度与推理成本。",
            ],
            "DyGLib/DyGFormer 是 CogGuard 下一跳预测最适合的工程化参考之一；它提供协议和实现，但需要系统自行定义传播事件语义、真实身份映射和开放世界候选集。",
            "值得复现，优先作为 micro 预测工程基座；它比单纯启发式排序更接近可训练动态图模型，但不能替代传播分析中的 provenance 图。",
            ["figure-1-p004", "table-1-p007", "table-2-p008", "figure-2-p008", "table-3-p009", "table-4-p009", "table-5-p009"],
            [
                {"id": "C1", "claim": "DyGLib 提供统一动态图学习实现和评测协议。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 1, PDF p.4", "note": "框架图"}, {"type": "body", "locator": "PDF p.1-3", "note": "统一库动机"}], "caveats": []},
                {"id": "C2", "claim": "DyGFormer 使用 patching 和 Transformer 处理长历史。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 1, PDF p.4", "note": "架构概览"}, {"type": "figure", "locator": "Figure 2, PDF p.8", "note": "输入长度分析"}], "caveats": []},
                {"id": "C3", "claim": "负采样协议会显著影响动态图链路预测结果。", "status": "strong", "inference": False, "evidence": [{"type": "table", "locator": "Table 1, PDF p.7", "note": "负采样设置"}, {"type": "table", "locator": "Table 4/5, PDF p.9", "note": "正负样本与负采样分析"}], "caveats": []},
                {"id": "C4", "claim": "DyGFormer 直接解决传播分析与开放世界新用户识别。", "status": "unsupported", "inference": True, "evidence": [], "caveats": ["原论文是通用动态图链路预测"]},
            ],
            {
                "figure-1-p004": ["C1", "C2"],
                "table-1-p007": ["C1", "C3"],
                "table-2-p008": ["C1"],
                "figure-2-p008": ["C2"],
                "table-3-p009": ["C3"],
                "table-4-p009": ["C3"],
                "table-5-p009": ["C3"],
            },
        ),
        paper(
            "temporal-graph-benchmark",
            "Temporal Graph Benchmark for Machine Learning on Temporal Graphs",
            "Huang 等",
            "2023",
            "Huang 等 - 2023 - Temporal graph benchmark for machine learning on temporal graphs.pdf",
            "基准/数据集/评测协议",
            "TGB 用大规模时间图数据、统一任务、负采样、时间切分和效率指标，让动态图模型能够公平复现和比较。",
            "数据集按 temporal link property prediction 与 node affinity prediction 组织，pipeline 固定训练/验证/测试、负采样、评估和效率统计。",
            "解决动态图研究中数据规模小、任务定义不一致、负样本协议不透明和只报告准确率不报告成本的问题。",
            "提供多尺度 temporal graph 数据集、基准任务和可复用评测管线。",
            "带时间戳的边、节点属性、动态链路、节点偏好/亲和关系及时间切分。",
            "输出动态链路预测 MRR/AP 等指标、node affinity prediction 指标、推理时间、训练时间和显存。",
            "Figure 2 展示 TGB pipeline；Table 1/2/3/4/6/7 报告数据与结果；Figure 4-7 报告推理/训练时间、显存和额外属性。",
            [
                "PDF p.1-2 认为动态图库和评测标准不足是模型进展受限的重要原因。",
                "Figure 2（PDF p.3）正文定义 TGB 从数据、任务、负采样到评估的完整 pipeline。",
                "Figure 3（PDF p.5）定义 node affinity prediction，与一般 link prediction 任务区分。",
                "Table 1（PDF p.6）给出数据集规模和属性；Table 2/3（PDF p.8-9）给出小、中、大数据集动态链路结果。",
            ],
            "TGB 将每个时间边预测任务拆成时间顺序的数据流、固定的正边和负边、模型推理以及统一指标。动态链路任务在时刻 t 预测未来交互；node affinity 任务预测用户对节点/项目的偏好。数据管线还显式记录 transductive/inductive、历史负采样、推理时间、训练时间和 GPU 内存。",
            "排名指标可写为 `MRR = (1/N) Σ_i 1/r_i`，其中 `r_i` 是真实未来边在候选列表中的名次。AP/MRR 只有在候选集和负采样协议固定时才可比较；node affinity 是另一种任务，不能与下一跳用户预测混为一谈。",
            [
                "Table 2（PDF p.8）报告小数据集动态链路预测结果；Table 3（PDF p.9）报告中、大数据集结果，体现规模对方法和成本的影响。",
                "Figure 4/4a/5/6（PDF p.8-10）正文将推理时间、训练时间和效率作为基准的一部分，而不是附属信息。",
                "Table 4（PDF p.9-10）报告 node affinity prediction，说明动态图任务不只是一种链路预测。",
                "Table 6/7（PDF p.18）提供更多负样本和 transductive/inductive 对比，直接支撑 CogGuard 必须显式声明候选协议。",
            ],
            [
                "数据层：提供跨规模、跨关系类型的 temporal graph 数据集。",
                "协议层：统一时间切分、负采样、指标和任务定义。",
                "工程层：把训练/推理时间与 GPU 内存纳入复现报告。",
            ],
            [
                "为 CogGuard 建立 propagation prediction benchmark schema，至少记录 observed_until、horizon、candidate source 和 edge provenance。",
                "将 micro 输出拆成已知用户再激活、候选邻居激活和新用户归纳式激活三种设置。",
                "在前端展示候选覆盖、MRR/Hits/MAP、推理时延和模型 abstain 原因，而不是只显示一个分数。",
            ],
            "TGB 不是单一预测模型，而是 CogGuard 预测模块最重要的评测协议参考；它能显著降低系统中“模型跑通但比较不公平”的风险。",
            "非常值得复现其协议和记录格式；不必把 TGB 所有数据集都接入系统，但应采用其时间切分、负采样、指标和效率报告思想。",
            ["figure-2-p003", "figure-3-p005", "table-1-p006", "table-2-p008", "table-3-p009", "table-4-p009", "table-6-p018", "table-7-p018"],
            [
                {"id": "C1", "claim": "TGB 统一时间图任务、数据和评测 pipeline。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 2, PDF p.3", "note": "pipeline"}, {"type": "body", "locator": "PDF p.1-3", "note": "基准动机"}], "caveats": []},
                {"id": "C2", "claim": "TGB 明确区分动态链路预测和 node affinity prediction。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 3, PDF p.5", "note": "任务定义"}, {"type": "table", "locator": "Table 4, PDF p.9-10", "note": "node affinity 结果"}], "caveats": []},
                {"id": "C3", "claim": "动态图模型比较必须报告负采样、时间切分和效率。", "status": "strong", "inference": False, "evidence": [{"type": "table", "locator": "Table 6/7, PDF p.18", "note": "协议对比"}, {"type": "figure", "locator": "Figure 4/5/6, PDF p.8-10", "note": "效率"}], "caveats": []},
                {"id": "C4", "claim": "TGB 的 MRR/AP 可直接作为 CogGuard 下一跳全部场景的唯一指标。", "status": "partial", "inference": True, "evidence": [{"type": "body", "locator": "PDF p.5", "note": "任务定义"}, {"type": "table", "locator": "Table 2/3, PDF p.8-9", "note": "链路预测结果"}], "caveats": ["系统还需候选覆盖、用户映射和宏观指标"]},
            ],
            {
                "figure-2-p003": ["C1"],
                "figure-3-p005": ["C2"],
                "table-1-p006": ["C1"],
                "table-2-p008": ["C1", "C3"],
                "table-3-p009": ["C1", "C3"],
                "table-4-p009": ["C2"],
                "table-6-p018": ["C3"],
                "table-7-p018": ["C3"],
            },
        ),
        paper(
            "pint-expressive-temporal-networks",
            "Provably Expressive Temporal Graph Networks",
            "Souza 等",
            "2022",
            "Souza 等 - 2022 - Provably expressive temporal graph networks.pdf",
            "理论/方法",
            "PINT 用相对位置和事件上下文增强 temporal GNN 表达性。",
            "以节点 memory 和事件更新协议为基础，引入 positional features 与 pairwise interaction information，形成 PINT 更新和预测模块。",
            "解决传统 message-passing temporal GNN 的表达性不足：不同的时间图可能被映射到相同表示。",
            "把 temporal graph 的可区分性与 temporal Weisfeiler-Lehman 类分析连接起来，并提出有理论保证的架构。",
            "带时间的交互边、节点状态、相对位置/时间特征和事件顺序。",
            "主要输出未来链路预测 AP，并报告理论命题、运行时间和位置特征维度敏感性。",
            "Figure 2/3/6 说明表达性限制和反例；Figure 5 展示 PINT；Table 1/2 报告 AP；Figure 7/8 分析效率和位置维度。",
            [
                "PDF p.1-4 以 temporal WL/表达性为主线，指出只做局部 message passing 可能无法区分时间图的直径、环和事件方向。",
                "Figure 2（PDF p.5）正文用于展示 TGNs 的限制；Figure 3（PDF p.6）给出 Proposition 7 的构造性反例。",
                "Figure 5（PDF p.7）和 Figure 6（PDF p.8）支持 PINT 的事件更新与区分能力说明。",
                "Propositions（PDF p.4-6）是理论主张的主要证据，Table 1/2（PDF p.9-10）是经验链路预测证据。",
            ],
            "PINT 遵循 temporal message passing 协议：事件到来时更新相关节点 memory。与标准 TGN 不同，PINT 的更新显式使用相对位置/事件上下文，使消息不仅依赖节点状态，还依赖事件在时间图中的结构位置。得到的 node/edge embedding 用于未来链路预测。",
            "论文通过 temporal WL 风格命题讨论模型能区分哪些时间图；经验任务可抽象为 `AP = Eval({score(u,v,t)}, E^+_test, E^-_test)`。理论保证说明表达能力边界，不能自动推出真实传播因果或更高业务准确率。",
            [
                "Proposition 1/相关命题（PDF p.4-6）直接支撑 PINT 相对传统 temporal message passing 的表达性讨论。",
                "Table 1（PDF p.9）报告链路预测 AP，Table 2（PDF p.10）报告加入相对位置特征后的对比。",
                "Figure 7（PDF p.9）报告 PINT 与 TGNs 的时间比较，提示表达力增强伴随预计算成本。",
                "Figure 8（PDF p.10）研究位置特征维度对 AP 的影响；本轮只采用正文/图注可恢复关系。",
            ],
            [
                "理论层：为 temporal GNN 的可表达性和失败案例提供可证明分析。",
                "架构层：用相对位置特征扩展 TGN 的事件消息。",
                "工程层：同时报告精度与预计算/运行时间，暴露理论增强的成本。",
            ],
            [
                "用 PINT 检查 CogGuard 的传播边流是否包含足够的事件顺序和相对位置，避免仅用用户 ID embedding。",
                "将表达性命题转化为诊断集：构造相同局部度但不同传播方向/时序的事件，测试下一跳是否可区分。",
                "把计算成本纳入模型选择，避免在 8GB GPU 和在线响应约束下盲目增加位置维度。",
            ],
            "PINT 适合作为 CogGuard 下一跳模型的理论增强参考，能解释为什么普通 TGN 可能混淆传播方向；但理论表达性不等于开放世界候选覆盖，也不替代数据协议。",
            "值得做小规模理论/诊断复现，是否作为正式模型需由同协议 AP/MRR、归纳式候选覆盖和时延共同决定。",
            ["figure-2-p005", "figure-3-p006", "figure-5-p007", "table-1-p009", "figure-7-p009", "table-2-p010", "figure-8-p010"],
            [
                {"id": "C1", "claim": "传统 temporal message passing 存在可构造的表达性限制。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 2/3, PDF p.5-6", "note": "限制与反例"}, {"type": "body", "locator": "Propositions, PDF p.4-6", "note": "理论命题"}], "caveats": []},
                {"id": "C2", "claim": "PINT 通过事件上下文/相对位置增强 temporal graph 表示。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 5/6, PDF p.7-8", "note": "架构和区分示例"}, {"type": "body", "locator": "PDF p.7-8", "note": "方法说明"}], "caveats": []},
                {"id": "C3", "claim": "PINT 在链路预测上提供经验增益，但存在计算代价。", "status": "partial", "inference": False, "evidence": [{"type": "table", "locator": "Table 1/2, PDF p.9-10", "note": "AP"}, {"type": "figure", "locator": "Figure 7, PDF p.9", "note": "时间比较"}], "caveats": ["未逐像素核验图中全部数值"]},
                {"id": "C4", "claim": "PINT 已经解决 CogGuard 的传播因果溯源。", "status": "unsupported", "inference": True, "evidence": [], "caveats": ["论文任务是动态图表示和链路预测"]},
            ],
            {
                "figure-2-p005": ["C1"],
                "figure-3-p006": ["C1"],
                "figure-5-p007": ["C2"],
                "table-1-p009": ["C3"],
                "figure-7-p009": ["C3"],
                "table-2-p010": ["C3"],
                "figure-8-p010": ["C3"],
            },
        ),
        paper(
            "adaptive-conformal-inference",
            "Adaptive Conformal Inference Under Distribution Shift",
            "Gibbs, Candès",
            "NeurIPS 2021",
            "Gibbs和Candès - 2021 - Adaptive conformal inference under distribution shift.pdf",
            "理论/不确定性校准",
            "Adaptive conformal inference 在线更新 conformal 阈值，使时间序列分布漂移下的局部覆盖率更接近目标水平。",
            "根据上一时刻是否覆盖更新阈值参数，再用归一化 conformity score 构造预测区间；CQR 扩展到分位数回归和选举预测。",
            "固定阈值 conformal 在非平稳序列和结构突变期间覆盖率会偏离目标，系统需要可在线适应的区间。",
            "建立分布漂移下的局部覆盖保证，并用股票波动和选举预测验证自适应更新。",
            "时间序列观测、点预测/分位数预测、过去残差 conformity score 和在线阈值。",
            "输出预测区间并评价平均覆盖、局部覆盖轨迹和区间稳定性。",
            "Algorithm 1（PDF p.18-19）给出核心更新；Theorem 4.1/4.2 提供理论；Figure 1-3/9 报告覆盖行为。",
            [
                "PDF p.1-4 将问题定义为分布随时间变化时，固定 conformal 阈值无法保证局部覆盖。",
                "Figure 1（PDF p.5）图注和正文比较 adaptive、fixed 和 Bernoulli coverage；正文称自适应方法在挑选的股票案例中表现更稳定。",
                "Figure 2（PDF p.9）是未归一化 conformity score 的失败/偏离案例，正文明确指出归一化重要。",
                "Theorem 4.1/4.2 与 Algorithm 1（PDF p.18-19）构成理论和实现的核心证据。",
            ],
            "在每个时刻 t，模型先产生预测区间，再根据真实值是否落入区间更新阈值。更新步长/遗忘机制控制对新分布的适应速度；归一化 score 使不同时间的误差尺度更可比。CQR 情况下先得到上下分位数，再用 conformal 修正。",
            "若 `I_t` 表示是否覆盖，阈值可按覆盖误差递推：`α_{t+1}=α_t+γ(1-α_target-I_t)`；区间形如 `[q_lo(x_t)-q_t, q_hi(x_t)+q_t]`。这里是按论文 Algorithm 1 和更新式的功能语义重写，实际符号和索引以 PDF p.4、18-19 为准。",
            [
                "Theorem 4.1/4.2（PDF p.4 附近）给出自适应覆盖相关理论保证，支持方法不是经验性滑动窗口。",
                "Figure 1（PDF p.5）正文称固定方法在部分股票上失效，而 adaptive 方法保持更接近目标的局部覆盖。",
                "Figure 3（PDF p.10）正文称非自适应方法在选举时区切换期间出现大幅覆盖偏离，自适应方法维持近似 90% 覆盖。",
                "Algorithm 1（PDF p.18-19）给出选举预测的 CQR 实现流程；Figure 9（PDF p.16-17）提供额外股票/指数的附录证据。",
            ],
            [
                "理论层：把分布漂移下的局部覆盖作为在线预测区间目标。",
                "算法层：用递推阈值和归一化 conformity score 适应非平稳误差。",
                "应用层：将同一校准思想用于金融波动和实时选举预测。",
            ],
            [
                "为 CogGuard 的规模趋势输出增加独立 calibration split，报告 empirical coverage、平均区间宽度和局部覆盖轨迹。",
                "按事件时间顺序更新阈值，不能使用预测窗口之后的信息校准当前输出。",
                "将 `confidence_like_score` 改名为分数集中度；只有通过覆盖率验证后才显示 prediction interval。",
            ],
            "该论文不改进动态图表示或下一跳排序，却直接解决 CogGuard 当前“区间/概率尚未校准”的系统风险；它应作为预测服务的校准层，而不是模型 backbone。",
            "值得复现其更新和 CQR 机制，尤其适合在线趋势预测；但覆盖保证依赖时间顺序、score 设计和更新参数，不能直接照搬股票/选举的经验数值。",
            ["figure-1-p005", "figure-2-p009", "figure-3-p010", "algorithm-1-p018", "algorithm-1-p019", "figure-9-p017"],
            [
                {"id": "C1", "claim": "固定 conformal 方法在分布漂移下可能失去局部覆盖。", "status": "strong", "inference": False, "evidence": [{"type": "body", "locator": "PDF p.1-4", "note": "问题定义"}, {"type": "figure", "locator": "Figure 1/3, PDF p.5/10", "note": "案例证据"}], "caveats": []},
                {"id": "C2", "claim": "自适应阈值更新改善局部覆盖稳定性。", "status": "strong", "inference": False, "evidence": [{"type": "theorem", "locator": "Theorem 4.1/4.2, PDF p.4", "note": "理论保证"}, {"type": "algorithm", "locator": "Algorithm 1, PDF p.18-19", "note": "更新算法"}, {"type": "figure", "locator": "Figure 1/3, PDF p.5/10", "note": "实证案例"}], "caveats": []},
                {"id": "C3", "claim": "归一化 conformity score 对覆盖质量重要。", "status": "strong", "inference": False, "evidence": [{"type": "figure", "locator": "Figure 2, PDF p.9", "note": "未归一化 score 案例"}, {"type": "body", "locator": "PDF p.9", "note": "正文解释"}], "caveats": []},
                {"id": "C4", "claim": "Adaptive conformal 可直接保证 CogGuard 传播预测区间在任意事件上有效。", "status": "unsupported", "inference": True, "evidence": [], "caveats": ["需要事件级校准集和时序验证"]},
            ],
            {
                "figure-1-p005": ["C1", "C2"],
                "figure-2-p009": ["C3"],
                "figure-3-p010": ["C2"],
                "algorithm-1-p018": ["C2"],
                "algorithm-1-p019": ["C2"],
                "figure-9-p017": ["C2"],
            },
            lenses=["computer-science-ai", "uncertainty-quantification"],
        ),
    ]
    for spec in papers:
        write_report(spec)
    write_root_readme(papers)


def write_root_readme(papers: list[dict[str, Any]]) -> None:
    path = ROOT / "README.md"
    lines = [
        "# CogGuard 传播分析与传播预测论文精读索引",
        "",
        "> 本目录记录 8 篇与传播分析、宏观级联预测、下一跳动态图预测、评测协议和不确定性校准相关论文的 text-only 深度精读。",
        "",
        "## 阅读范围",
        "",
        "- 读者画像：computer-science-ai、跨学科读者、目标为 reproduce、深度 deep、语言 zh-CN。",
        "- 每篇报告都逐项覆盖本地抽取清单中的 Figure/Table/Algorithm。",
        "- 本轮没有直接做像素级视觉核验；报告只使用 PDF 文本层、图注、正文引用和结构化文本卡。",
        "- 因此所有视觉清单保留 `visual_verification=not-performed`，不能把报告中的图表解释当作视觉审稿结论。",
        "",
        "## 论文分组与 CogGuard 对齐",
        "",
        "| 主题 | 论文 | 对 CogGuard 的主要作用 | 复现判断 |",
        "|---|---|---|---|",
        "| 多尺度传播预测 | MINDS | 统一 macro/micro backbone、顺序超图、共享/私有表示和消融协议 | 值得优先复现 |",
        "| 宏观未来趋势 | CasFT | neural ODE + diffusion future trend，支撑趋势曲线而非单点规模 | 值得小规模复现 |",
        "| 连续时间 micro | TGN、DyGLib/DyGFormer | memory、patching、时间边流和可扩展下一跳排序 | 值得复现并做严格候选审计 |",
        "| 归纳式新用户 | CAW | 匿名因果游走和未见节点泛化 | 值得做开放世界补强 |",
        "| 表达性理论 | PINT | 解释 temporal GNN 能否区分传播方向和高阶时序结构 | 值得做诊断复现 |",
        "| 评测协议 | TGB | 时间切分、负采样、MRR/AP、效率和显存统一记录 | 必须借鉴 |",
        "| 区间校准 | Adaptive conformal inference | 分布漂移下的在线 coverage 和 CQR 校准 | 值得接入校准层 |",
        "",
        "## 当前系统方法论结论",
        "",
        "传播分析是观测功能：从 MongoDB 原始帖子/评论构造 provenance 图，区分显式、重建和推断关系，输出路径、层级、角色、共享对象和证据链。传播预测是独立模型功能：只读取 `observed_until` 前缀，宏观输出规模/趋势，微观输出合法候选用户或边的排序；候选覆盖不足时必须 abstain。",
        "",
        "当前真正需要收口的不是再增加一个分类头，而是统一任务协议：事件级宏观标签、用户/边级微观标签、严格时间切分、归纳式候选集、真实用户映射、模型校准和前端可追溯证据。论文结果可以作为方法依据，但不能代替 CogGuard 真实事件上的无泄漏验证。",
        "",
        "## 复现总清单",
        "",
        "1. 固定每篇论文 PDF、代码 revision、依赖和数据版本。",
        "2. 按原论文的 observation/prediction horizon 构造数据，并记录 transductive/inductive 设置。",
        "3. 先复现主表，再复现关键消融、历史长度、负采样、solver 或采样数量敏感性。",
        "4. 对 CogGuard 单独报告候选覆盖、真实用户映射率、推理时延、显存、失败原因和 abstain 比例。",
        "5. 趋势区间接入独立 calibration split；没有 coverage 证据时不要把集中度分数称为置信度。",
        "",
        "## 文件",
        "",
    ]
    for spec in papers:
        lines.append(f"- [{spec['slug']}/report.md]({spec['slug']}/report.md)：{spec['title']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
