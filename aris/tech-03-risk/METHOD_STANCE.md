# METHOD_STANCE: Risk Review 方法论定位

## 核心主张

**Risk Review 不是一个"更准确的风险评分系统"，而是一个"阶段感知的风险预测与 DISARM 路径驱动的反制推理框架"。**

## 三个核心问题与回答

| 问题 | 传统方法 | Agentic DISARM (2026) | Risk Review |
|------|---------|----------------------|-----|
| **当前风险多高？** | 静态评分 | LLM 生成风险描述 | 信念区间 + 冲突检测 |
| **接下来会发生什么？** | ❌ 不回答 | ❌ 不回答 | ✅ 阶段转换预测 + 下一步技术预测 |
| **应该如何应对？** | ❌ 不回答 | ❌ 不回答 | ✅ 基于路径的反制建议 |

## 方法论对比

### vs. 传统静态评分系统

| 维度 | 传统静态评分 | Risk Review |
|------|------------|-----|
| 时序建模 | 单时间点快照 | 5 状态生命周期 + 滑动窗口 |
| 输出类型 | 风险分数（0-100） | 阶段 + 转换风险 + 预测 + 反制 |
| 决策支持 | "这个事件风险高" | "即将进入 breakout，建议部署 X 反制措施" |
| 可操作性 | 低（只知道风险高，不知道怎么办） | 高（给出具体反制路径） |
| 不确定性 | 点估计（虚假确定性） | 信念区间 + 冲突标记 |

### vs. Agentic DISARM (2026)

| 维度 | Agentic DISARM | Risk Review |
|------|----------------|-----|
| **核心方法** | LLM-driven | Rule-based + Graph reasoning |
| **DISARM 使用** | Flat tagging（标签映射） | Path reasoning（路径推理结构） |
| **主要输出** | 观测到的技术标签 | 预测下一步 + 反制建议 |
| **时序建模** | 静态映射 | 阶段感知（5 状态生命周期） |
| **可解释性** | 黑盒（LLM 内部推理） | 白盒（转换图可视化 + 路径可追溯） |
| **计算资源** | GPU（LLM 推理） | CPU-only（规则 + 图算法） |
| **不确定性** | 置信度分数 | 信念区间 + 冲突检测 + 升级标记 |
| **决策支持** | "检测到 T0105 协同活动" | "检测到 T0105，预测下一步 T0049 信息洪流，建议部署洪流检测" |
| **适用场景** | 需要 GPU、可接受黑盒 | 竞赛/实战、需要可审计、CPU-only |

**关键差异**：Agentic DISARM 回答"观测到了什么"（detection），Risk Review 回答"下一步会发生什么 + 如何拦截"（anticipation + countermeasure）。

## 贡献层级

### Dominant Contribution（主贡献）

**Phase-Aware Hazard + DISARM Attack-Path**：阶段感知的风险预测与路径驱动的反制推理

- **Phase-Aware Hazard Model**：
  - 把静态风险评估提升为动态战役演化推理
  - 5 状态生命周期建模（seed → synchronize → breakout → saturation → regeneration）
  - Logistic hazard estimation 预测阶段转换风险
  - 输出：当前阶段、转换风险、breakout 预估时间

- **DISARM Attack-Path Scoring**：
  - 把 DISARM 从标签体系提升为攻击路径推理结构
  - 技术转换图（从 MITRE ATT&CK 迁移）
  - 路径评分（depth × breadth × completeness）
  - 下一步预测（基于转换概率）
  - 反制建议（基于预测路径）

### Supporting Contribution（辅助贡献）

**Contradiction-Aware Evidential Fusion**：证据冲突感知与信念区间输出

- Dempster-Shafer 证据理论融合
- Phase-conditioned mass adjustment（阶段调制置信度）
- 冲突检测与升级标记
- 输出：信念区间（belief intervals）而非点估计

### Non-Contribution（明确不作为主创新）

- **三维评分本身**：authenticity / manipulation / impact 评分只是 supporting summary signal
- **自动 DISARM 映射**：这是基础层，Agentic DISARM 已做，不是 Risk Review 的主要创新点
- **多源证据融合**：常见方法，只有 phase-conditioned adjustment 是新的

## Risk Review 在 Characterization 中的职责边界

按 Mannocci 等对 coordinated behavior 的 `Detect -> Characterize` 两阶段定义，`Harmfulness` 与 `Authenticity / Orchestration / Time-variance` 正交，且明确依赖观察者视角。对本项目而言，Risk Review 站在**网络舆论安全**视角负责 harmfulness 维度，至少覆盖三个层级：

| 层级 | 应回答的问题 | Risk Review 本轮落点 |
|------|-------------|-------------|
| 帖子级 | 这条内容是否 harmful、属于哪类 harmful、关联哪个 claim、对 claim 持何立场 | **本轮优先落地** |
| 账户级 | 这个账户是否持续传播 harmful 内容、其 harm 模式是否稳定 | 由帖子级结果向上聚合 |
| 社区级 | 这个协同群体整体体现为哪类 harmful（谣言、仇恨、骚扰、动员、放大） | 由账户级和传播结构继续聚合 |

因此，Risk Review 的帖子级不是一个孤立的“文本分类器”，而是后续账户级、社区级 harmfulness 刻画的**最小语义单元**。

## 帖子级任务定义（正式版）

### 问题定义

帖子级模块应被定义为**多模态、claim-conditioned、multi-task** 联合建模问题，而不是“harmful 分类”和“stance 分类”两个彼此割裂的小工具。单条帖子至少回答四个问题：

1. 这条内容是否 harmful。
2. 它属于哪类 harmful。
3. 它链接到哪个 claim，若没有则输出 `NIL`。
4. 它对该 claim 持何立场。

### 输入

```json
{
  "post_id": "string",
  "text": "原始文本",
  "emoji_text": "表情语义描述",
  "ocr_text": "图片/视频 OCR",
  "asr_text": "视频/音频转写",
  "image_regions": ["image evidence 1", "image evidence 2"],
  "video_keyframes": ["frame_1", "frame_2", "frame_3"],
  "candidate_claims": [
    {"claim_id": "c1", "claim_text": "claim text 1"},
    {"claim_id": "c2", "claim_text": "claim text 2"}
  ]
}
```

### 输出

```json
{
  "post_id": "string",
  "harm_label": "safe | borderline | harmful",
  "harm_types": ["misleading", "hate", "harassment", "mobilization", "violence"],
  "linked_claims": [{"claim_id": "c1", "score": 0.91}],
  "stance": [
    {
      "claim_id": "c1",
      "label": "support | deny | query | comment | none",
      "score": 0.88
    }
  ],
  "evidence": {
    "text_spans": ["..."],
    "ocr_spans": ["..."],
    "frame_ids": [1, 3],
    "rationale": "..."
  },
  "confidence": 0.87,
  "abstain": false
}
```

### 任务约束

- `harm_label` 建议使用三分类：`safe / borderline / harmful`。
- `harm_types` 应为**多标签**，因为“误导 + 动员”或“仇恨 + 骚扰”可共存。
- `stance` 必须是**claim-conditioned** 的；没有 claim linking，就不存在可解释的 stance。
- 多模态证据应同时来自文本、表情、OCR、视频关键帧、ASR，而不是把媒体字段只当作附件保存。

## 帖子级参考文献与方法映射（已核实）

| 文献 | 来源 | 作用 |
|------|------|------|
| [Mannocci et al., 2024](https://arxiv.org/abs/2408.01257) | arXiv | 给出 `Detect -> Characterize` 与 harmfulness 正交维度框架，是 Risk Review 的问题边界来源 |
| [HateXplain](https://ojs.aaai.org/index.php/AAAI/article/view/17745) | AAAI 2021 | 可解释有害文本检测，提供 harm label 与 rationale/span supervision |
| [The Hateful Memes Challenge](https://proceedings.neurips.cc/paper/2020/hash/1b84c4cee2b8b3d823b30e2d604b1878-Abstract.html) | NeurIPS 2020 | 图文联合 harmful meme 检测的经典基准，支撑帖子级多模态 harmfulness |
| [RumourEval 2019](https://aclanthology.org/S19-2147/) | SemEval 2019 | `support / deny / query / comment` 的 claim-conditioned stance 标注来源 |
| [Fakeddit](https://aclanthology.org/2020.lrec-1.755/) | LREC 2020 | 图文联合虚假信息检测，适合训练 coarse-to-fine 多模态表示 |
| [MuMiN](https://arxiv.org/abs/2202.11684) | arXiv 2022 + dataset | 多语言、多模态、fact-checked misinformation 图谱，适合 claim linking 与后续社区扩展 |
| [FakeSV](https://ojs.aaai.org/index.php/AAAI/article/view/26689) | AAAI 2023 | 面向短视频场景的视频、文本、社交上下文联合检测，最接近视频帖子场景 |
| [MultiOFF](https://aclanthology.org/2020.trac-1.6/) | TRAC 2020 | offensive meme 数据，补充图文 harmful 迁移能力 |
| [LLM-based Semantic Augmentation for Harmful Content Detection](https://arxiv.org/abs/2504.15548) | arXiv 2025 | 支撑 teacher 侧语义增强与弱监督扩标 |
| [A Multi-Agent Framework with Automated Decision Rule Optimization (MARO)](https://aclanthology.org/2025.emnlp-main.291/) | EMNLP 2025 | 作为 Agent 编排与反思机制参考，不作为底层帖子分类器 |

补充说明：Risk Review 不直接照搬 MARO 做底层分类，而是借鉴其 `agent orchestration / reflection` 思路，把 Agent 放在**解释、复核、报告**层，而把帖子级分类核心保留为可部署的多模态学生模型。

## 帖子级数据集与用途

| 数据/链接 | 模态 | 主要用途 |
|-----------|------|---------|
| [HateXplain](https://ojs.aaai.org/index.php/AAAI/article/view/17745) | 文本 | harmful 文本 warm-start，训练 rationale / evidence span |
| [Hateful Memes 数据主页](https://ai.meta.com/tools/hatefulmemes/) | 图像 + 文本 | 图文 harmful meme 检测，多模态 harmful 主基准 |
| [RumourEval 2019 数据](https://figshare.com/articles/dataset/RumourEval_2019_data/8845580) | 文本 + thread + claim | claim-conditioned stance 学习与 Rumour/stance 联合训练 |
| [Fakeddit 数据仓库](https://github.com/entitize/Fakeddit) | 图像 + 文本 | 图文 misinformation 粗到细粒度训练 |
| [MuMiN 数据仓库](https://github.com/MuMiN-dataset/mumin-build) | 图像 + 文本 + fact-check graph | claim linking、多语言迁移、后续账户/社区建模 |
| [FakeSV 数据仓库](https://github.com/ICTMCG/FakeSV) | 视频 + 文本 + 音频/社交上下文 | 视频帖子场景迁移，补齐 OCR/ASR/关键帧流程 |
| [MultiOFF 论文](https://aclanthology.org/2020.trac-1.6/) | 图像 + 文本 | offensive meme 迁移数据，补充有害表达识别 |

这些数据集在 Risk Review 中的分工不是“谁最好就全用谁”，而是形成互补：

- `HateXplain + RumourEval` 负责把文本 harmful 与 claim-conditioned stance 学稳。
- `Hateful Memes + MultiOFF + Fakeddit` 负责把图文 harmfulness 和 misinformation 表示学稳。
- `FakeSV` 负责把帖子级能力迁移到短视频场景。
- `MuMiN` 负责把帖子级输出接到 claim 图谱、账户级与社区级扩展上。

## 研究叙事

### 问题定位

**不是**："如何更准确地给信息操纵事件打分"
**而是**："如何把上游检测结果转化为可操作的风险预判，提前识别战役升级，并给出可复核的反制路径"

### 方法论主张

**不是**："我们提出一个三维评分框架"
**而是**："我们提出一个 phase-aware, contradiction-aware, DISARM-path-aware 报告研判框架，用阶段预测回答'接下来会发生什么'，用攻击路径回答'应该如何拦截'，用 evidential fusion 回答'结论有多可信'"

### 价值主张

**不是**："我们的评分更准确"
**而是**："我们从 detection 升级到 anticipation + countermeasure，让报告研判从'告诉你有风险'变成'告诉你下一步会发生什么、应该如何应对'"

## 验证重点

**不验证**："分数是否准确"
**验证**：
1. 阶段识别是否合理（5 状态分类是否符合真实战役演化）
2. 转换预测是否有用（hazard estimation 能否在 breakout 前提供有效预警）
3. 下一步预测是否有解释力（predicted next techniques 是否优于简单启发式）
4. 反制建议是否可操作（countermeasures 是否从 predicted path 自然推出并具有行动意义）
5. 冲突检测是否减少过度自信（ds_fusion 是否确实标记了矛盾证据）

## 论文/汇报叙事建议

### 标题方向

❌ "A Three-Dimensional Risk Scoring Framework for Information Manipulation"
✅ "Phase-Aware Risk Forecasting and DISARM Attack-Path Reasoning for Information Manipulation Campaigns"

### Abstract 结构

1. **Problem**: 现有方法只做静态检测，缺少面向事件演化的风险预判与处置支持
2. **Method**: Phase-aware hazard model + DISARM attack-path reasoning + contradiction-aware fusion
3. **Key innovation**: 不只告诉你"观测到了什么"，还预测"下一步会发生什么"并给出"如何拦截"
4. **Results**: 阶段识别准确率 X%，转换预测 AUC Y，反制建议与专家判断一致性 Z%

### Introduction 开场

❌ "Risk assessment is important for combating information manipulation..."
✅ "While detection of coordinated inauthentic behavior has advanced significantly, translating detection results into actionable risk forecasts remains an open challenge. Analysts need not just to know *what* manipulation techniques are observed, but *what will happen next* and *how to intervene*..."

### Related Work 定位

- 与静态评分系统对比：强调时序建模与预测能力
- 与 Agentic DISARM 对比：强调路径推理 vs 标签映射、可解释性 vs 黑盒
- 与 MITRE ATT&CK 对比：强调从网络安全到信息操纵的方法迁移

### Contribution 陈述

1. **Phase-Aware Hazard Model**: 首次将 campaign lifecycle 与 hazard estimation 结合用于信息操纵风险预测
2. **DISARM Attack-Path Reasoning**: 首次将网络安全攻击路径分析方法迁移到信息操纵领域
3. **Phase-Conditioned Evidential Fusion**: 让证据置信度随战役阶段动态调整

### Demo/竞赛展示重点

- **不展示**：风险分数仪表盘
- **展示**：
  1. 阶段演化时间线（seed → synchronize → breakout 预警）
  2. DISARM 攻击路径图（观测路径 + 预测下一步 + 反制建议）
  3. 证据冲突标记（"协同检测高置信 vs 传播影响低置信，建议人工复核"）

## 实施原则

1. **Prediction over Scoring**: 主打"预测下一步"而非"打分更准"
2. **Path Reasoning over Flat Tagging**: DISARM 作为路径推理结构，非标签表
3. **Explainable over Black-box**: 规则+图结构 vs 纯 LLM
4. **Anticipation over Detection**: 从"检测"升级到"预判+反制"
5. **Actionable over Descriptive**: 输出必须支持具体决策，不只是描述风险

## 风险与缓解

### 风险点

1. **Phase 分类可能过于简化**：5 状态是否足够刻画真实战役演化？
   - 缓解：强调这是 operational model，不是 descriptive taxonomy；验证时关注预测有用性而非分类完美性

2. **DISARM 转换图是手工设计**：可能不完整或有偏差
   - 缓解：强调这是 domain-informed prior，可随实战数据迭代；关键创新在于"路径推理"框架而非具体转换概率

3. **与 Agentic DISARM 的差异可能被质疑**：都做 DISARM 映射，差异是否足够大？
   - 缓解：明确差异在于"路径推理 + 预测 + 反制" vs "标签映射"；强调可解释性与 CPU-only 的实战价值

4. **验证数据可能不足**：真实标注的战役演化数据稀缺
   - 缓解：使用 mock 数据 + 专家评估 + 案例研究；强调这是 proof-of-concept，实战部署后可持续改进

## 总结

Risk Review 的核心价值不在于"评分更准"，而在于：

1. **从静态到动态**：阶段感知的风险演化建模
2. **从检测到预判**：预测下一步会发生什么
3. **从描述到行动**：给出可操作的反制建议
4. **从点估计到区间**：信念区间 + 冲突检测

这是一个**风险预测与反制推理系统**，不是一个**风险评分系统**。
