# Idea Discovery Report: Propagation Analysis 传播趋势预测（LLM+时序预测）

**Direction**: LLM + 时序预测 传播趋势预测
**Date**: 2026-04-28
**Pipeline**: research-lit → idea-creator → novelty-check → research-review

## Executive Summary

技术路线收敛为 **Hybrid: 轻量时序模型 + LLM 上下文编码器**。核心思路：CPU 时序/图特征模型负责数值预测，LLM API 负责事件语义理解和异常模式识别，融合后输出结构化趋势预测。GPT-5.4 评审评分：技术 6/10、竞赛影响 7/10。新颖性 7/10（竞赛系统级别）。



## Literature Landscape

### Track A: LLM for Time Series

- Time-LLM (ICLR 2024): 通过文本原型对齐重编程 LLM 做时序预测

- LLMTime (NeurIPS 2023): 将数字序列化为文本做零样本预测

- "Rethinking LLMs in TSF" (2026): LLM 在分布偏移下有价值；信息丰富的 prompt > 更大模型

- 结论：LLM 对高方差、上下文依赖的社交媒体传播数据有价值



### Track B: 信息级联预测
- AutoCas (2025): LLM 自回归级联预测器（需训练，不适用）
- Variational Neural ODEs (2026): 连续时间 ODE 建模趋势动态
- 结论：最近工作开始用 LLM 做级联预测，但都需要训练



### Track D: 立场检测
- LLM-Enhanced MIL (2025): 联合谣言+立场检测
- Collaborative SLM-LLM (2025): 小大模型一致性验证
- 结论：LLM 零样本立场分类已成熟，可直接用作特征



### 结构性空白
1. 无人将 LLM 上下文理解 + 轻量时序模型用于协同攻击趋势预测
2. AutoCas 需训练；我们需要纯 API 方案
3. 无系统将立场/危害性特征整合进传播趋势预测
4. 无工作同时预测 volume + scope + speed 三个目标



## Ranked Approaches

### 🏆 Approach 1: Hybrid TS + LLM Context Encoder — RECOMMENDED

**架构**: TS 分支(时序特征) + Graph 分支(图特征) + LLM 分支(上下文) → 融合预测

**机制**:

- 时序分支：帖子按小时聚合，提取 volume/velocity/acceleration/periodicity
- 图分支：NetworkX MultiDiGraph 特征（节点增长、边增长、社区数、桥接节点）
- LLM 分支：API 调用，输出结构化 JSON（事件类型、叙事阶段、情感、协同线索）
- 融合：HistGradientBoosting/量化回归 → volume/scope/speed 预测

**Novelty**: 7/10（竞赛系统）
- 最近先例：AutoCas (需训练)、BuzzProphet (通用热度)
- 差异化：协同攻击专用 + 三输出 + 图集成 + CPU-only + 中文解释

**External Review**: 技术 6/10、竞赛影响 7/10
- 优势：结构合理、可解释、部署友好
- 风险：无训练数据时预测缺乏校准

**Risk**: LOW-MEDIUM | **Effort**: 5-7 days

### Approach 2: Historical Analog Retrieval — BACKUP

从历史事件中检索最相似案例，外推其轨迹。

**Risk**: LOW | **Effort**: 3-5 days
**优势**: 小数据可用、可解释
**劣势**: 无相似历史案例时失效

### Approach 3: Graph-Feature Cascade Forecaster — BACKUP

纯图特征（节点增长、社区数、桥接节点）+ CPU 回归器。

**Risk**: LOW | **Effort**: 4-6 days
**优势**: 与现有 propagation.py 强集成
**劣势**: 缺乏语义理解

## Eliminated Approaches

| Approach | Reason |
|----------|--------|
| #7 LLMTime-style numeric prompting | 文献警告 LLM 数值预测不可靠 |
| #10 Event-logic graph | 过于复杂，7-10 天，错误传播风险高 |
| Full neural TS (PatchTST) | 需 GPU 训练，违反约束 |

## External Review Key Feedback

**Top 3 Weaknesses:**
1. 无训练/回测 → 预测缺乏验证
2. LLM 分支脆弱（延迟、幻觉、prompt 注入）
3. 图特征在大规模突发时可能变慢

**Top 3 Improvements:**

1. 添加基线回测（即使无训练，也可回放历史事件对比）
2. 加固 LLM 层（JSON schema 验证、超时降级、缓存）
3. 诚实暴露置信度（反映数据量、特征一致性、LLM 有效性）

**Demo Advice:**
- 不要过度宣称"准确预测"，除非有指标
- 定位为"可解释的早期预警 + 风险评分"，辅以回放证据

## Implementation Roadmap

| Step | File | Description | Days |
|------|------|-------------|------|
| 1 | `core/propagation/ts_features.py` | 时序特征提取 | 1 |
| 2 | `core/propagation/llm_context.py` | LLM prompt + API + fallback | 1.5 |
| 3 | `core/propagation/trend_predictor.py` | 融合预测器 | 2 |
| 4 | `core/propagation/stance_detector.py` | 立场检测子功能 | 1 |
| 5 | `core/propagation/harm_assessor.py` | 危害性评估子功能 | 1 |
| 6 | `services/propagation_service.py` | 服务层集成 | 0.5 |
| 7 | `tests/test_trend_prediction.py` | 测试（mock LLM） | 1 |

**Total**: ~8 days

## Next Steps

- [ ] 实现 Step 1-7（代码落地）
- [ ] 用 mock_weibo 数据回测验证
- [ ] 更新 EXPERIMENT_PLAN.md 和 TASK_TRACKER.md
- [ ] 前端趋势预测展示面板

## 产业参考与差异化定位

**产品对标**：[知微传播分析（WeiboReach）](../ZHIWEI_PRODUCT_ANALYSIS.md)

导师建议参考知微数据（zhiweidata.com，2012 年成立，A 轮 1300 万融资）的传播分析产品作为工业界标杆。已输出详细产品分析文档 `ZHIWEI_PRODUCT_ANALYSIS.md`。

### 知微产品能力覆盖

| 能力 | 知微 | CascadeSwitch |
|------|------|---------------|
| 单条传播分析 | ✅ | ✅ propagation_legacy.py |
| 传播路径可视化 | ✅ | ✅ |
| 关键节点识别 | ✅ | ✅ key_roles |
| 传播力指数 | ✅ 0-100 | 🔲 待补充 |
| 事件阶段划分 | ✅ 5 阶段经验 | ✅ 4 体制可学习 |
| **趋势预测** | ❌ | ✅ **核心创新** |
| 跨平台验证 | ❌ 仅微博 | ✅ DeepHawkes + CasFlow |
| 开源/可发表 | ❌ 商业封闭 | ✅ |
| LLM 增强 | ❌ | ✅ 事件提取 |

### Propagation Analysis 的差异化定位

- **前瞻预测**（知微侧重事后分析）
- **可学习 regime**（知微用经验阶段）
- **跨平台泛化**（知微绑定微博生态）
- **透明白盒**（知微算法黑盒）
- **公开学术基准**（知微用内部客户数据）

### 借鉴的具体动作

1. **特征扩展**：加入 max_chain_depth、unique_reposter_count、kol_ratio 等知微使用的核心指标
2. **输出扩展**：新增 stage_transition_eta、peak_eta_hours、influence_score（类知微传播力指数）
3. **评估扩展**：按事件类别（社会/娱乐/政治）分别评估
4. **可视化扩展**：参考知微的路径图、体制堆叠图、阶段时间轴

详细分析见 [ZHIWEI_PRODUCT_ANALYSIS.md](../ZHIWEI_PRODUCT_ANALYSIS.md)。
