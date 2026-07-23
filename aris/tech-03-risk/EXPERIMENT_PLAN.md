# EXPERIMENT_PLAN

## 当前目标

构建一个**基于多 Agent 编排的协同操纵事件检测、研判与反馈系统**，覆盖从"发现异常"到"支持处置"的完整闭环。RAG + Agent 报告生成作为子任务，解决风险报告的主观性问题。LLM 后端统一使用 **DeepSeek API**。

**核心价值主张**：不只告诉你"当前风险多高"，还通过多 Agent 协作实现恶意内容检测、立场追踪、攻击路径预测、反制叙事生成和结构化报告输出。

## 技术路线（Agent 编排版）

经过 idea-discovery → novelty-check → research-refine → 用户确认，技术路线最终收敛为：

### 三层架构

```
Layer 1: Agent-based Detection & Assessment（复用现有核心模块）
  ├── Phase Agent: 战役阶段感知（tool: phase_detector.py）
  ├── Evidence Agent: 多源证据融合（tool: ds_fusion.py）
  └── DISARM Agent: 攻击路径推理（tool: disarm_scorer.py）

Layer 2: RAG + Agent Report Generation
  ├── 检索：历史报告库 + DISARM 知识库 + 事件证据库
  └── 生成：DeepSeek Agent 基于检索结果生成结构化风险报告

Layer 3: Agent-based Feedback & Detection Extension
  ├── Harmful Content Agent: 恶意言论/仇恨言论检测
  ├── Stance Detection Agent: 立场检测与演化追踪
  └── Counter-narrative Agent: 反制叙事建议生成
```

### LLM 后端
- **统一使用 DeepSeek API**
- Agent 不做最终裁决，只做辅助检测和报告生成
- 核心检测仍走现有统计/规则路线，LLM 调用走 API

### 与现有代码的关系

| 现有模块 | 新角色 |
|---------|--------|
| `evidence_builder.py` | Evidence Agent 的 tool |
| `phase_detector.py` | Phase Agent 的 tool |
| `ds_fusion.py` | Evidence Agent 的 fusion tool |
| `disarm_scorer.py` | DISARM Agent 的 tool |
| `report_builder.py` | Report Agent 的 template engine |
| `llm_bridge.py` | 升级为 Agent orchestrator（DeepSeek） |

## 工作包（优先级同等）

- [ ] WP-A1：升级 `llm_bridge.py` 为 DeepSeek Agent 编排器
- [ ] WP-A2：实现 Harmful Content Detection Agent
- [ ] WP-A3：实现 Stance Detection Agent
- [ ] WP-A4：实现 RAG + Agent Report Generation
- [ ] WP-A5：实现 Counter-narrative Agent
- [ ] WP-A6：更新 `risk_service.py` 支持 Agent 编排
- [ ] WP-A7：更新 API 端点支持新 Agent 功能
- [ ] WP-A8：补充测试
- [ ] WP-A9：更新前端展示 Agent 检测结果

## 各 Agent 设计

### Harmful Content Detection Agent
- 输入：单条帖子多模态包 `text + emoji + OCR + ASR + keyframes`
- 方法：teacher-student 多任务学习；teacher 用 DeepSeek/多模态指令模型做 `harm label + harm types + rationale`，student 做可部署分类
- 输出：`{post_id, harm_label, harm_types, evidence, confidence, abstain}`

### Stance Detection Agent
- 输入：帖子多模态包 + 候选 claim 集
- 方法：先做 `claim linking`，再做 claim-conditioned stance；stance 标签统一为 `support / deny / query / comment / none`
- 输出：`{post_id, linked_claims, stance, confidence}`

### RAG Report Generation Agent
- 输入：事件证据包 + 阶段结果 + DISARM 分析
- 检索源：历史报告库（MySQL）、DISARM 知识库（本地 YAML）、事件证据
- 方法：检索相关上下文 → DeepSeek 生成结构化报告
- 输出：自然语言风险报告

### Counter-narrative Agent
- 输入：检测到的操纵叙事 + DISARM 路径分析
- 方法：DeepSeek 基于攻击路径生成反制策略
- 输出：`{narrative, counter_strategy, target_audience, priority}`

## 帖子级实现闭环（本轮确定版）

### 一、问题定义

帖子级 Risk Review 子模块统一回答四个问题：

1. 单条内容是否 harmful。
2. 属于哪类 harmful。
3. 链接到哪个 claim。
4. 对该 claim 持何立场。

这一定义要求帖子级模块是**多模态、claim-conditioned、multi-task**，不能继续停留在 `文本关键词规则 + stance 规则` 的 MVP 形式。

### 二、输入与输出规范

**输入字段**

```json
{
  "post_id": "string",
  "content": "原始文本",
  "emoji_text": "表情语义",
  "media_urls": ["..."],
  "ocr_text": "图片/视频 OCR",
  "asr_text": "音频/视频转写",
  "keyframes": ["frame_1", "frame_2", "frame_3"],
  "candidate_claims": [{"claim_id": "c1", "claim_text": "..." }]
}
```

**输出字段**

```json
{
  "post_id": "string",
  "harm_label": "safe | borderline | harmful",
  "harm_types": ["misleading", "hate", "harassment", "mobilization", "violence"],
  "linked_claims": [{"claim_id": "c1", "score": 0.91}],
  "stance": [{"claim_id": "c1", "label": "support", "score": 0.88}],
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

### 三、模型栈

#### Step 1. 多模态解析层

- 文本：保留原始 `content`
- 表情：将 emoji 转成可读语义短语
- 图片：OCR + 图像区域描述
- 视频：关键帧抽样，不直接全视频建模
- 音频：ASR 转写

第一版不追求复杂视频 Transformer，优先采用“关键帧 + OCR + ASR”的轻量稳定路线。

#### Step 2. Claim Linking

- 输入：帖子多模态表示 + claim 库
- 方法：双塔检索召回 top-k claim，再用交叉编码器重排
- 输出：`top-k claims + NIL`

这是 stance 检测的前置步骤；不做 claim linking，stance 结果将缺乏可解释性。

#### Step 3. Harmfulness 多任务头

- 主任务：`safe / borderline / harmful`
- 辅任务：harm type 多标签分类
- 解释任务：输出 evidence span / rationale

建议采用 teacher-student：

- teacher：DeepSeek 或多模态指令模型，生成 `label + type + rationale`
- student：部署侧轻量模型，只保留统一编码器和分类头

#### Step 4. Claim-conditioned Stance 头

- 输入：帖子表示 + claim 表示
- 输出：`support / deny / query / comment / none`
- 方法：cross-attention 或 claim-conditioned 分类头

#### Step 5. Agent 复核层

- Harm Agent：汇总 harmful 证据并做解释
- Stance Agent：复核 claim-post 对
- Verification/Framing Agent：对“事实可能为真但框架有害”的样本做补充判断

Agent 在帖子级的作用是**复核与解释**，不是替代底层学生模型。

### 四、训练路线

#### 阶段 A：文本 warm-start

- Harmful：HateXplain
- Stance：RumourEval 2019

目标：先把文本 harmful 与 claim-conditioned stance 学稳。

#### 阶段 B：图文多模态 warm-start

- Hateful Memes
- MultiOFF
- Fakeddit

目标：学会图文联合 harmfulness 和 misinformation 表示。

#### 阶段 C：短视频迁移

- FakeSV

目标：把帖子级能力扩展到视频帖子。

#### 阶段 D：图谱与多语言扩展

- MuMiN

目标：增强 claim linking、多语言迁移，以及向账户级/社区级扩展的兼容性。

#### 阶段 E：域内蒸馏

- 用真实平台帖子 + Propagation Analysis claim 库
- teacher 自动生成弱标注、rationale、claim 链接
- student 蒸馏成运行时模型

### 五、与当前代码的衔接

建议按以下模块补齐，而不是继续在 `harmful_detector.py` / `stance_detector.py` 上堆规则：

| 模块 | 建议职责 |
|------|---------|
| `post_multimodal_parser.py` | OCR / ASR / keyframe / emoji 解析 |
| `claim_linker.py` | top-k claim 检索与重排 |
| `post_harm_encoder.py` | harmful 三分类 + harm type 多标签 |
| `post_stance_classifier.py` | claim-conditioned stance |
| `post_evidence_explainer.py` | evidence span / rationale 汇总 |
| `agent_orchestrator.py` | 调用 DeepSeek 做复核与报告解释 |

### 六、评测指标

- Harm label：Macro-F1 / AUROC
- Harm type：Micro-F1 / Macro-F1
- Claim linking：Recall@k / MRR
- Stance：Macro-F1
- 多模态解释：evidence span overlap / 人工可用性评估
- 运行时：平均每帖推理延迟、拒答率、人工复核触发率

### 七、最小可交付版本（建议）

第一阶段最值得做的不是“全量多 Agent”，而是：

1. 接通 `media_urls -> OCR / keyframe / ASR` 解析链。
2. 完成 `claim linking + harmful + stance` 的统一帖子级输出。
3. 只在低置信度样本上调用 Agent 复核。

这样既符合 Risk Review 的学术定位，也最容易和当前 `system/` 主干对接。

## 退出标准

- Agent 编排器可调用 DeepSeek API 完成各 Agent 任务
- 恶意言论检测 Agent 可对**多模态帖子**输出 `harm_label + harm_types + evidence`
- 立场检测 Agent 可对 `claim-post` 对输出 claim-conditioned stance
- RAG 报告生成 Agent 可基于检索结果生成自然语言报告
- 反制叙事 Agent 可基于 DISARM 路径输出反制建议
- 现有 Phase/Evidence/DISARM 三个核心 Agent 继续正常工作
- 所有 Agent 结果可通过 API 返回
- 测试覆盖各 Agent 基本功能

## 高水平文献支撑（帖子级优先）

| 论文 | 年份/来源 | 核心贡献 | 与帖子级 Risk Review 的关系 |
|------|----------|---------|-----------------------|
| Mannocci et al. CIB Survey | 2024 / arXiv 2408.01257 | `Detect -> Characterize` 与 harmfulness 维度定义 | 给出 Risk Review 问题边界 |
| HateXplain | 2021 / AAAI | 可解释 harmful 文本检测 | 文本 harmful warm-start |
| The Hateful Memes Challenge | 2020 / NeurIPS | 图文 harmful meme 检测 | 图文多模态 harmful 基准 |
| RumourEval 2019 | 2019 / SemEval | claim-conditioned stance 标签 | stance 主基准 |
| Fakeddit | 2020 / LREC | 多模态虚假信息细粒度检测 | 图文 misinformation 表示学习 |
| MuMiN | 2022 / arXiv + dataset | 多语言、多模态、fact-checked misinformation 图谱 | claim linking 与后续图谱扩展 |
| FakeSV | 2023 / AAAI | 短视频虚假信息基准 | 视频帖子迁移主基准 |
| MultiOFF | 2020 / TRAC | offensive meme 检测 | 图文 harmful 补充基准 |
| LLM-based Semantic Augmentation for Harmful Content Detection | 2025 / arXiv | LLM 语义增强 | teacher 弱监督与扩标 |
| A Multi-Agent Framework with Automated Decision Rule Optimization | 2025 / EMNLP | 多 Agent 反思与规则优化 | 仅借鉴编排与复核层 |

## 数据集链接（帖子级）

| 数据集 | 链接 | 主要使用方式 |
|--------|------|-------------|
| HateXplain | https://ojs.aaai.org/index.php/AAAI/article/view/17745 | harmful 文本 + rationale |
| Hateful Memes | https://ai.meta.com/tools/hatefulmemes/ | 图文 harmful |
| RumourEval 2019 | https://figshare.com/articles/dataset/RumourEval_2019_data/8845580 | claim-conditioned stance |
| Fakeddit | https://github.com/entitize/Fakeddit | 图文 misinformation |
| MuMiN | https://github.com/MuMiN-dataset/mumin-build | claim 图谱、多语言、多模态 |
| FakeSV | https://github.com/ICTMCG/FakeSV | 视频帖子 |
| MultiOFF | https://aclanthology.org/2020.trac-1.6/ | offensive meme 迁移 |
