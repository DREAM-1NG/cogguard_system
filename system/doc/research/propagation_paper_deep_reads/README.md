# 传播监测论文精读与实验索引

本目录记录 `H:\Zotero\attenger\Projects\CISCN\Propagation` 下信息扩散、动态传播预测和不确定性校准相关论文的精读材料，以及本地 Propagation 方法对比实验报告。

## 核心报告

| 文件 | 内容 |
|---|---|
| `information_diffusion_system_transfer_report.md` | 多论文精读综合、信息扩散问题意识、方法谱系、当前传播监测系统迁移和优化计划 |
| `propagation_prediction_research_line_and_local_experiments.md` | 传播预测方法研究线补充、本地 FOREST 数据集实验路径、MINDS 与系统方法采样对比、后续严格评测计划 |
| `propagation_sota_full_run_status_20260810.md` | Propagation SOTA baseline 本地拉取状态、可运行 adapter 边界、全量运行命令与输出路径 |
| `propagation_sota_stable_matrix_report_20260810.md` | 资源受限稳定矩阵结果，覆盖 Douban/Twitter/Memetracker、MINDS/FOREST/CasFT/DyGFormer/TGN/Ours |

## 抽取资产

| 目录或文件 | 内容 |
|---|---|
| `assets/pdf_text_manifest.json` | PDF 文本抽取 manifest、页数、章节和 page summaries |
| `assets/paper_text_summary.json` | 每篇论文标题候选、摘要、章节、图表标题和全文文本路径 |
| `assets/evidence_snippets.json` | 按论文和关键词抽取的页码证据片段 |
| `assets/text/` | 每篇 PDF 的 `full_text.txt` |
| `assets/standard_inventory/` | 按 `paper-deep-reader` text-only inventory 生成的逐论文结构化材料 |

## 使用边界

本目录中的综合报告和稳定矩阵用于系统设计、实现审查和工程可运行性证据。`propagation_sota_stable_matrix_report_20260810.md` 是本机资源受限矩阵，不是无裁剪严格全量验证；正式论文结论仍需要更大算力下的 uncapped full validation。

建议后续按以下顺序拆单篇深读与复现：

| 顺序 | 论文 | 原因 |
|---:|---|---|
| 1 | MINDS 2024 | 当前传播预测模型主干最直接的方法依据 |
| 2 | CasFT 2025 | 趋势曲线和未来增长建模的主要依据 |
| 3 | TGB 2023 / DyGFormer 2023 | 下一跳评测协议和动态图实现管线 |
| 4 | CAW 2022 / TGN 2020 | 开放世界归纳式下一跳和连续时间事件流 |
| 5 | ACI 2021 | 预测区间和在线校准 |
| 6 | Zhou 2021 / Guo 2025 | 系统数据字典、任务定位和汇报口径 |
