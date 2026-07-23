# F-RISK（报告研判与攻击路径）代码开发需求文档

> **所属功能**：报告研判与攻击路径（F-RISK）
> **主要技术**：Risk Review Phase-Aware Hazard + DISARM 路径推理
> **文档类型**：功能级代码开发需求（research + engineering 拆分）
> **最后更新**：2026-05-17
> **配套文档**：[../tech-02-propagation/ZHIWEI_PRODUCT_ANALYSIS.md](../tech-02-propagation/ZHIWEI_PRODUCT_ANALYSIS.md)（产品对标参考风格）、[../../doc/engineering/research-engineering-split.md](../../doc/engineering/research-engineering-split.md)（系统总览）

---

## 一、功能定位与产品对标

### 1.1 在 CogGuard 中的定位

F-RISK 是 CogGuard 主链路 `事件 → 证据 → 协同 → 传播 → 风险 → 处置` 的**末端推理引擎**。承接 F-COORD（协同检测）与 F-PROP（传播监控）的结构化输出，输出**阶段感知风险预测 + 攻击路径推理 + 反制建议 + 结构化报告**。

**输入**：

- F-COORD 输出：`coord_groups` / `network_density` / `asymmetry_index` / `evidence_edges`
- F-PROP 输出：`trend / stance / harm / scope / source`
- 账户监测输出：`automation_score` / `regularity` / `activity_pattern`

**输出**：

- **阶段判定**：5 状态生命周期（seed / synchronize / breakout / saturation / regeneration）+ 转换风险（hazard）
- **三维风险评分**：真实性（authenticity）/ 操纵性（manipulation）/ 危害性（impact）+ 信念区间
- **DISARM 映射**：观测到的技术 + 路径评分 + 下一步预测 + 反制建议
- **结构化报告**：18 顶层字段 JSON（含证据链、风险因子、推荐处置）

### 1.2 学界 + 工业界对标

| 对标对象 | 类型 | 与 F-RISK 的关系 |
|---|---|---|
| DISARM Framework | 行业标准 | F-RISK 的技术分类骨架（45 种技术 → 18 条路径） |
| Agentic DISARM 2026 | 学术方法 | LLM 驱动的 flat tagging，F-RISK 差异化为"预测 + 反制推理" |
| MITRE ATT&CK | 行业标准 | DISARM 转换图的方法论参照 |
| Recorded Future | 工业界 | 威胁情报平台，F-RISK 的报告形态参考 |
| Graphika | 工业界 | 跨平台影响行动分析，F-RISK 的整体功能参考 |
| Dempster-Shafer Theory | 数学方法 | 三维证据融合的数学基础 |

### 1.3 产品对标缺口

Propagation Analysis 有「知微」对标，Coordination Discover 缺乏单一商业对标，Risk Review 同样以学界 + 工业威胁情报平台为主：

- 试用 Recorded Future / ThreatConnect 试用版，整理风险评分形态
- 关注 Agentic DISARM 后续工作（2026 论文方向）
- 收集 EU DisinfoLab、Stanford SIO 等智库的报告结构

---

## 二、主要技术：Risk Review Phase-Aware Hazard + DISARM 核心创新（research）

### 2.1 核心命题

**传统风险评分系统**回答："观测到了什么风险？"
**F-RISK 回答**："**下一步会发生什么？应该如何拦截？**"

这是 F-RISK 相对于 Agentic DISARM 2026 的**核心差异化**——从"flat tagging（标签映射）"升级为"阶段感知预测 + 路径推理 + 反制建议"。

### 2.2 vs. Agentic DISARM 2026 对比

| 维度 | Agentic DISARM 2026 | **F-RISK** |
|---|---|---|
| 核心问题 | "观测到了什么技术？" | **"下一步会发生什么？应该如何拦截？"** |
| 方法学 | LLM 驱动的标签映射（flat tagging） | **规则 + 图算法：阶段生命周期 + 路径推理** |
| 时序建模 | 静态映射（无历史上下文） | **5 状态 + hazard 估计 + 阶段调制** |
| 可解释性 | 黑盒（LLM 推理过程不透明） | **白盒：转换图可视化 + 路径可追踪** |
| 计算成本 | GPU（LLM 推理） | **CPU-only（规则 + Dempster-Shafer）** |
| 输出形式 | 技术标签（T0105 = 协同） | **完整推理链：当前阶段 → 下一步预测 → 反制措施** |
| 部署成本 | 高（GPU 集群） | **低（CPU + 规则 + 配置文件）** |

### 2.3 Phase-Aware Hazard 模型

**5 状态生命周期**：

| 状态 | 简述 | 主要特征 |
|---|---|---|
| seed | 信息播种期 | 少量账户 / 低速度 / 高 Gini（集中度） |
| synchronize | 同步组织期 | 协同信号增强 / 速度上升 / 网络密度增长 |
| breakout | 爆发突破期 | 速度跳跃 / 跨集群扩散 / KOL 介入 |
| saturation | 饱和稳定期 | 速度趋于平稳 / 峰值附近 / 多元参与 |
| regeneration | 再生潜伏期 | 衰减但有再次激活迹象 / 残留协同 |

**logistic hazard 模型**：

```
hazard(s_t+1 | s_t, features) = σ(w_0 + w_1·velocity + w_2·burst_zscore
                                   + w_3·coord_signal + w_4·stance_polarization)
```

**research 部分**：5 个权重参数 `w_0...w_4` 需在历史战役数据上校准。

### 2.4 Contradiction-Aware Dempster-Shafer 融合

**三维证据空间**：
- 真实性（authenticity）
- 操纵性（manipulation）
- 危害性（impact）

**焦元设定**：{risk, safe, uncertain}

**质量分配**（mass assignment）：

```
m(risk) = α_1 · coord_signal + α_2 · stance_extremity + α_3 · harm_score
m(safe) = β_1 · official_response_factor + β_2 · diverse_participation
m(uncertain) = 1 - m(risk) - m(safe)
```

**阶段调制**：在不同生命周期阶段下，权重系数 α / β 会按 5 套预设进行调制（breakout 阶段提升 manipulation 权重等）。

**冲突质量检测**：

```
conflict_mass = K = Σ_{A ∩ B = ∅} m_1(A) · m_2(B)
```

**逻辑**：当 `conflict_mass > 0.3` 时触发人工介入（多源证据矛盾）。

**research 部分**：
- 9 个质量分配权重（3 个 α + 2 个 β + 4 个交叉项）
- 5 套阶段调制系数（5 个阶段 × 1 套权重组）
- 冲突阈值（默认 0.3）

### 2.5 DISARM 攻击路径推理

**核心思想**：把 DISARM 45 种技术构造成有向图（18 条转换边 + 转换概率），从观测到的技术沿路径推演**下一步可能发生什么**，再给出针对性的反制建议。

**18 条转换边示例**（部分）：

```
T0011(Create Fake Persona) → T0013(Create Inauthentic Sites)    [prob=0.45]
T0013 → T0017(Conduct Fundraising)                              [prob=0.20]
T0017 → T0049(Flood Information Space)                          [prob=0.55]
T0049 → T0061(Amplify on Platforms)                             [prob=0.70]
T0061 → T0085(Mass Posting)                                     [prob=0.60]
T0085 → T0103(Bypass Content Moderation)                        [prob=0.35]
...
```

**路径评分**：

```
path_score = w_d · depth + w_b · breadth + w_c · completeness

depth：路径长度（observed 技术数）
breadth：可触达的下一步技术数
completeness：路径覆盖的 DISARM 阶段数（reconnaissance / development / 
                                          establishment / deployment / closure）
```

**反制建议生成**：基于"下一步预测"反查 DISARM 反制库（每种技术配 2-3 个反制措施模板）。

**research 部分**：
- 18 条边的转换概率（领域知识初始化，待实战数据迭代）
- 路径评分 3 个权重 `w_d / w_b / w_c`
- 反制建议模板库（需领域专家校验）

### 2.6 研究 claim

| Claim | 命题 | 验证方式 |
|---|---|---|
| Claim 1 | Phase-Aware Hazard 比静态评分提前 N 小时预警 | 在历史 case 上的提前量评估 |
| Claim 2 | Contradiction-Aware D-S 的冲突检测能识别多源矛盾 | mass=0 / mass=1 / 极高冲突边界 case |
| Claim 3 | DISARM 路径推理能预测下一步技术（top-3 准确率） | 实战 case 验证 |
| Claim 4 | 反制建议的可操作性（专家评估） | 5-7 个 case 的盲评 |

---

## 三、其他技术支持

### 3.1 证据特征提取

- **标签**：engineering（已实现）
- **位置**：`new-system/backend/app/core/risk/evidence_builder.py`（244 行）
- **职责**：从 F-COORD / F-PROP / 账户监测输出提取标准化证据特征
- **计算项**：
  - Gini 系数（活跃度集中度）
  - Shannon 熵（多样性）
  - 突发性（burst velocity）
  - 跨集群扩散度
  - KOL 参与度
- **公式**：通用统计公式，无调参

### 3.2 DISARM 技术映射规则表

- **标签**：engineering（已实现，需专家校验）
- **位置**：`disarm_scorer.py` 内的映射表
- **职责**：把证据特征映射到 45 种 DISARM 技术
- **格式**：硬编码字典 `{technique_id: detection_rule}`
- **research → engineering 边界**：映射规则的"领域知识"属于 research，规则在代码中的硬编码属于 engineering

### 3.3 结构化报告 JSON 模板

- **标签**：engineering（已实现）
- **位置**：`report_builder.py`（278 行）
- **职责**：把所有分析结果组装为 18 顶层字段的结构化 JSON
- **18 顶层字段**：
  - `event_id`, `time_range`, `phase`, `phase_confidence`
  - `fusion_belief_intervals`（authenticity/manipulation/impact）
  - `conflict_mass`, `escalation_flag`
  - `observed_techniques[]`, `predicted_next_techniques[]`
  - `path_score`, `path_completeness`
  - `evidence_chain[]`, `risk_factors[]`
  - `recommendations[]`, `countermeasures[]`
  - `confidence_level`, `human_review_required`
  - `generated_at`, `version`

### 3.4 LLM 桥接（待补）

- **标签**：engineering（30 行 stub 待替换）
- **位置**：`new-system/backend/app/core/risk/llm_bridge.py`
- **职责**：把规则生成的反制建议 + 报告解释自然语言化
- **不做的事**：F-RISK 的核心推理**不依赖 LLM**，LLM 仅做后处理（语言生成）
- **本期改动**：替换 stub，调用 F-PROP 的 `llm_client.py`（避免重复实现）

### 3.5 报告研判 API

- **标签**：engineering（已实现）
- **位置**：`new-system/backend/app/api/v1/risk.py`（68 行）
- **端点**：
  - `POST /api/v1/risk/assess`（触发风险评估）
  - `GET /api/v1/risk/reports`（报告列表）
  - `GET /api/v1/risk/reports/{id}`（报告详情）

### 3.6 服务层编排

- **标签**：engineering（已实现）
- **位置**：`new-system/backend/app/services/risk_service.py`（153 行）
- **职责**：串联 evidence → phase → fusion → DISARM → report，并持久化到 MySQL
- **当前状态**：核心流水线完成，但依赖 Propagation Analysis WP4-5 的"立场 / 危害"输入用占位数据

### 3.7 数据库持久化（⚠️ 阻塞）

- **标签**：engineering（缺迁移）
- **位置**：`new-system/backend/app/models/risk_assessment.py`（50 行）
- **问题**：ORM 模型已建，alembic 迁移未补 → 部署即失败
- **本期必须**：新增 `alembic/versions/xxx_add_risk_assessment.py`

### 3.8 前端报告研判页

- **标签**：engineering（基础页已有，路径图待补）
- **位置**：`new-system/frontend/src/views/risk/index.vue`
- **本期改动**：
  - 报告列表 + 详情已实现
  - 新增 DISARM 攻击路径力导向图（ECharts force-directed，节点 = 技术，边 = 转换概率）
  - 新增三维信念区间堆叠图
  - 新增阶段时间轴 + hazard 曲线

---

## 四、功能拆解：产品级功能点

| # | 功能点 | 做什么 | 输入 | 输出 | 落点文件 | 标签 |
|---|---|---|---|---|---|---|
| F1 | 证据构建 | 从上游模块提取特征 + 统一证据包 | F-COORD/F-PROP/account 输出 | `EvidencePack` | `evidence_builder.py` (244) | engineering ✅ |
| F2 | 阶段检测 | 5 状态分类 + logistic hazard 估计 + breakout ETA | `EvidencePack.features` | `PhaseResult` | `phase_detector.py` (169) | research ✅ |
| F3 | D-S 三维融合 | 阶段调制 + 信念区间 + 冲突检测 | F1 + F2 输出 | `FusionResult`：belief intervals + conflict_mass | `ds_fusion.py` (234) | research ✅ |
| F4 | DISARM 映射 | 证据 → 技术 + 路径评分 + 下一步预测 + 反制 | F1 + F3 输出 | `DisarmResult` | `disarm_scorer.py` (381) | research ✅ |
| F5 | 报告组装 | 18 顶层字段 JSON | F1-F4 输出 | 结构化报告 | `report_builder.py` (278) | engineering ✅ |
| F6 | LLM 后处理 | 反制建议 + 报告解释自然语言化 | F4 输出 | 自然语言文本 | `llm_bridge.py` (待补) | engineering |
| F7 | 编排与持久化 | 调度 F1-F6 + 存入 MySQL | API 参数 | report_json | `risk_service.py` (153) | engineering ✅ |
| F8 | API 端点 | `assess / reports / reports/{id}` | HTTP | JSON | `api/v1/risk.py` (68) | engineering ✅ |
| F9 | 数据库持久化 | RiskAssessment 表 + alembic 迁移 | report_json | DB row | `models/risk_assessment.py` + alembic | engineering ⚠️ |
| F10 | 前端报告列表 + 详情 | 列表 / 详情 / 状态 | API 响应 | UI | `frontend/views/risk/` | engineering ✅ |
| F11 | DISARM 路径可视化 | 力导向图 | F4 输出 | UI | `frontend/views/risk/path.vue`（待新增） | engineering |
| F12 | 信念区间堆叠图 | 三维评分可视化 | F3 输出 | UI | 同上 | engineering |
| F13 | 阶段时间轴 + hazard 曲线 | 阶段演化可视化 | F2 输出 | UI | 同上 | engineering |

---

## 五、现有代码资产 vs 待新增

### 5.1 已有（MVP 1,340 行）

| 文件 | 行数 | 完整度 | 本期改动 |
|---|---|---|---|
| `core/risk/evidence_builder.py` | 244 | 100% | 等 Propagation Analysis WP4-5 完成后替换占位数据 |
| `core/risk/phase_detector.py` | 169 | 100% | 参数校准（research） |
| `core/risk/ds_fusion.py` | 234 | 100% | 参数校准（research）+ 边界 case 测试 |
| `core/risk/disarm_scorer.py` | 381 | 100% | 转换概率迭代（research）+ 反制库扩充 |
| `core/risk/report_builder.py` | 278 | 100% | 无 |
| `core/risk/llm_bridge.py` | 30 | ❌ stub | 替换为真实调用（复用 F-PROP 的 llm_client.py） |
| `services/risk_service.py` | 153 | 80% | 等 Propagation Analysis WP4-5 完成后替换占位 |
| `api/v1/risk.py` | 68 | 100% | 无 |
| `models/risk_assessment.py` | 50 | 100% | 无（但需补 alembic 迁移） |
| `frontend/views/risk/index.vue` | — | 60% | 补 DISARM 路径 + 信念区间 + 时间轴 |
| `tests/test_risk.py` | 348 | 70% | 补边界 case |

### 5.2 待新增 / 待补

| 文件 | 工作量 | 核心职责 |
|---|---|---|
| `alembic/versions/xxx_add_risk_assessment.py` | 30 min | 创建 RiskAssessment 表 |
| `frontend/views/risk/path.vue` | 4-6 h | DISARM 路径力导向图 + 信念区间 + 阶段时间轴 |
| `frontend/api/risk.ts` 扩展 | 1 h | 新增路径详情 API 调用 |
| 反制建议模板库扩充 | 2-3 d（含专家评审） | 18 条转换路径 × 2-3 模板 = 36-54 条 |

### 5.3 配置文件（research 校准产物）

| 文件 | 内容 | 状态 |
|---|---|---|
| `core/risk/config/phase_config.yaml` | 5 个 logistic hazard 权重 | 默认值，待校准 |
| `core/risk/config/fusion_config.yaml` | 9 个质量分配权重 + 5 套阶段调制 | 默认值，待校准 |
| `core/risk/config/disarm_paths.yaml` | 18 条转换边 + 概率 | 领域先验，待实战迭代 |

---

## 六、research vs engineering 拆分边界（F-RISK 视角）

### 6.1 research 任务（本地实验）

| # | 任务 | 阻塞 / 数据来源 | 验证 |
|---|---|---|---|
| R1 | Phase-Aware Hazard 5 参数校准 | 代码已实现，参数为默认值 | 历史 case 的提前量 + 转换准确率 |
| R2 | D-S 融合 9+5 参数校准 | 代码已实现，参数为默认值 | 边界 case（mass=0/1/极高冲突）+ 与人工标注一致性 |
| R3 | DISARM 18 条转换概率迭代 | 当前为领域先验 | 实战 case + 专家评估 |
| R4 | 反制建议模板库构建 | 待领域专家协作 | 36-54 条模板 + 专家盲评可操作性 |
| R5 | Claim 1 提前量验证 | 历史战役 case 数据 | 在 N=24h 提前量下的 precision/recall |
| R6 | Claim 3 下一步预测 | 实战数据 | top-3 准确率 |
| R7 | 边界 case 测试 | mock 数据 | mass=0 / mass=1 / conflict>0.3 三类 |

### 6.2 engineering 任务（Claude Code）

| 优先级 | # | 任务 | 工作量 |
|---|---|---|---|
| P0 | E1 | 补 `alembic` 迁移以支持 `risk_assessment` 表 | 30 min |
| P0 | E2 | `llm_bridge.py` 替换 stub，调用 F-PROP 的 `llm_client.py` | 1-2 h |
| P1 | E3 | 前端 DISARM 路径力导向图（ECharts） | 4-6 h |
| P1 | E4 | 前端信念区间堆叠图 | 2 h |
| P1 | E5 | 前端阶段时间轴 + hazard 曲线 | 2 h |
| P1 | E6 | 反制建议模板库代码框架（YAML 配置 + 加载器） | 2 h |
| P2 | E7 | 报告 PDF 导出（依赖报告中心 P2 任务） | 1 d |
| P2 | E8 | 跨 analysis capability 依赖替换（等 F-PROP WP4-5 完成后替换占位数据） | 1 d |

### 6.3 边界 case

- **DISARM 映射规则**：规则的"领域知识"属于 research（需专家整理），规则在代码中硬编码属于 engineering。当前 45 条已实现，本期 engineering 任务是把规则从 disarm_scorer.py 内嵌字典迁移到 `disarm_techniques.yaml` 配置文件（便于专家修改）。

- **反制建议模板库**：模板内容属于 research（需专家协作），模板加载器与渲染属于 engineering。

---

## 七、关键设计决策与开放问题

### 7.1 关键决策

1. **规则 + 统计优先，LLM 仅做后处理**
   - 理由：可审计、可复核、CPU-only 部署、与 Agentic DISARM 黑盒形成差异化
   - 影响：F-RISK 的核心推理（阶段判定 / D-S 融合 / DISARM 路径）全部白盒

2. **5 状态生命周期 vs 更细粒度**
   - 候选：5 状态 vs 7-9 状态
   - 当前：5 状态（操作可行性优先）
   - 风险：可能过于简化，需 R1/R5 实验验证

3. **DISARM 路径图手工设计 + 数据迭代**
   - 18 条边初始概率基于领域知识
   - 实战 case 迭代后更新（R3）
   - 影响：初期 MVP 准确率受限，但具备可解释性

4. **Dempster-Shafer 而非贝叶斯网络**
   - 优势：支持信念区间输出 + 显式冲突检测
   - 三元焦元 `{risk, safe, uncertain}` 比纯概率更适合表达"不确定"
   - 风险：参数空间大，需谨慎校准

5. **跨 analysis capability 占位数据策略**
   - 当前：F-RISK 已用占位数据（Propagation Analysis WP4-5 未实现）
   - 解锁条件：F-PROP `stance_detector.py` / `harm_assessor.py` 完成
   - 影响：不阻塞 F-RISK MVP 演示，但报告中"立场/危害"字段不准确

### 7.2 开放问题

1. **5 状态模型是否过于简化？**
   - 质疑：战役演化是否真的只有 5 个离散状态？
   - 缓解：强调这是 **operational model**，关键是预测有用性而非分类完美性
   - 阻塞：R1 + R5 实验

2. **DISARM 转换图的完整性**
   - 质疑：18 条路径是否足以覆盖真实操纵行为？
   - 缓解：这是 **domain-informed prior**，关键创新在路径推理框架而非具体概率
   - 阻塞：R3 实战数据迭代

3. **与 Agentic DISARM 2026 的差异是否足够大？**
   - 缓解：明确差异化定位（路径推理 vs 标签映射、白盒 vs 黑盒、预测+反制 vs 检测）
   - 长期：可发表论文对比实验

4. **验证数据稀缺**
   - 质疑：真实标注的战役演化数据难以获得
   - 缓解：mock + 专家评估 + 5-7 个 case study；强调 PoC 性质
   - 阻塞：R5 / R6 / R4 都依赖此

5. **DISARM 反制库的可操作性**
   - 质疑：建议是否真的可操作？
   - 缓解：与领域专家协作，每条反制带"前置条件 / 期望效果 / 失败模式"
   - 阻塞：R4 模板库构建

---

## 八、对其他 analysis capability / 全系统的接口契约

### 8.1 F-COORD → F-RISK（消费 Coordination Discover 输出）

```python
# F-RISK 期望的输入
coordination_input = {
    "coord_groups": [
        {"group_id": str, "members": [str], "size": int,
         "dominant_channels": [str], "group_score": float}
    ],
    "network_density": float,
    "asymmetry_index": float,
    "evidence_edges": [...],  # PSL 输出的边级证据
}
```

**消费位置**：`evidence_builder.py` 计算 Gini / Shannon 等聚合统计

### 8.2 F-PROP → F-RISK（消费 Propagation Analysis 输出）

```python
# F-RISK 期望的输入
monitoring_input = {
    "trend": {...},          # CascadeSwitch 预测
    "stance": {...},         # WP4 立场（当前用占位）
    "harm": {...},           # WP5 危害（当前用占位）
    "scope": {...},
    "source": {...},
}
```

**消费位置**：`ds_fusion.py` 的 mass assignment 用 `stance_extremity` / `harm_score`

**当前阻塞**：Propagation Analysis WP4-5 未实现，F-RISK 用占位数据

### 8.3 F-RISK → 数据库

```sql
-- RiskAssessment 表（待 alembic 迁移）
CREATE TABLE risk_assessment (
    id INT PRIMARY KEY AUTO_INCREMENT,
    event_id VARCHAR(64),
    phase VARCHAR(32),
    conflict_mass FLOAT,
    escalation_flag BOOLEAN,
    report_json JSON,
    created_at DATETIME,
    confidence_level VARCHAR(16),
    human_review_required BOOLEAN
);
```

### 8.4 F-RISK → 前端

**API 契约**：

```http
POST /api/v1/risk/assess
{
  "event_id": "evt_001",
  "force_refresh": false
}
```

```json
// 响应（report_builder.py 的 18 字段）
{
  "event_id": "evt_001",
  "time_range": [...],
  "phase": "breakout",
  "phase_confidence": 0.82,
  "fusion_belief_intervals": {
    "manipulation": [0.65, 0.78],
    "authenticity": [0.12, 0.25],
    "impact": [0.55, 0.70]
  },
  "conflict_mass": 0.18,
  "escalation_flag": true,
  "observed_techniques": ["T0011", "T0049", "T0061"],
  "predicted_next_techniques": [
    {"technique": "T0085", "probability": 0.65, "transition": "T0061→T0085"},
    {"technique": "T0103", "probability": 0.42, "transition": "T0085→T0103"}
  ],
  "path_score": 0.78,
  "evidence_chain": [...],
  "recommendations": [...],
  "countermeasures": [
    {"technique": "T0085", "measure": "...", "preconditions": [...],
     "expected_effect": "...", "failure_modes": [...]}
  ],
  "confidence_level": "high",
  "human_review_required": false,
  "generated_at": "2026-05-17T10:00:00Z",
  "version": "v0.2"
}
```

---

## 九、引用

| 类别 | 路径 | 用途 |
|---|---|---|
| 方法论定位 | [METHOD_STANCE.md](./METHOD_STANCE.md) | vs Agentic DISARM 2026 差异化定位 |
| 研究简述 | [RESEARCH_BRIEF.md](./RESEARCH_BRIEF.md) | Risk Review 问题陈述 + 非目标 |
| 实验计划 | [EXPERIMENT_PLAN.md](./EXPERIMENT_PLAN.md) | Phase-Aware Hazard + DISARM 实验设计 |
| 验收标准 | [ACCEPTANCE.md](./ACCEPTANCE.md) | 功能 + API 字段 + 非目标 |
| 任务追踪 | [TASK_TRACKER.md](./TASK_TRACKER.md) | WP 进度（WP1-6 100% / WP7 80%） |
| 背景文档 | [../../doc/research/key-technology-background/risk-disarm.md](../../doc/research/key-technology-background/risk-disarm.md) | Risk Review 技术背景 |
| 跨 analysis capability 契约 | [../shared/CROSS_ANALYSIS_DEPS.md](../shared/CROSS_ANALYSIS_DEPS.md) | 三 analysis capability 数据流契约 |
| 状态记忆 | [../../memory/state_review.md](../../memory/state_review.md) | Risk Review 状态 + WP 进度 + 阻塞 |
| 系统总览 | [../../doc/engineering/research-engineering-split.md](../../doc/engineering/research-engineering-split.md) | 三大功能 research/engineering 总表 |

---

## 十、后续动作

**第一周（engineering，Claude Code 主导）**：

1. E1：补 `alembic` 迁移（解锁部署） → 30 min
2. E2：`llm_bridge.py` 替换 stub（依赖 F-PROP 的 `llm_client.py`） → 1-2 h
3. E3-E5：前端 DISARM 路径 + 信念区间 + 阶段时间轴 → 8-10 h
4. E6：反制建议模板库代码框架（YAML 配置 + 加载器） → 2 h

**第二周（research，本地实验）**：

1. R1：Phase-Aware Hazard 5 参数校准（历史 case） → 3-4 d
2. R2：D-S 融合 9+5 参数 + 边界 case 测试 → 2-3 d
3. R7：边界 case 覆盖测试（mass=0/1/conflict>0.3） → 1 d

**第三周（领域专家协作）**：

1. R3：DISARM 18 条转换概率实战 case 迭代 → 1 周（依赖案例库）
2. R4：反制建议模板库构建（36-54 条模板） → 1 周

**第四周（跨 analysis capability 联调 + claim 验证）**：

1. E8：替换 Propagation Analysis 占位数据（依赖 F-PROP WP4-5 完成）
2. R5：Claim 1 提前量验证
3. R6：Claim 3 下一步预测验证
