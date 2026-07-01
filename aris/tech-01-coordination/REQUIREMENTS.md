# F-COORD（跨平台协同检测）代码开发需求文档

> **所属功能**：跨平台协同检测（F-COORD）
> **主要技术**：KT1 PSL（Pair Surprisal Layer）—— 即插即用的配对显著性评估层
> **文档类型**：功能级代码开发需求（research + engineering 拆分）
> **最后更新**：2026-05-17
> **配套文档**：[../tech-02-propagation/ZHIWEI_PRODUCT_ANALYSIS.md](../tech-02-propagation/ZHIWEI_PRODUCT_ANALYSIS.md)（产品对标参考风格）、[../../doc/engineering/research-engineering-split.md](../../doc/engineering/research-engineering-split.md)（系统级总览）

---

## 一、功能定位与产品对标

### 1.1 在 CogGuard 中的定位

F-COORD 是 CogGuard 主链路 `事件 → 证据 → 协同 → 传播 → 风险 → 处置` 中的**协同发现引擎**。承接事件信息窗口的原始证据池（多源、多模态），输出**多通道协同网络 + 协同群组结构**，供下游 F-PROP（传播监控）和 F-RISK（报告研判）消费。

**输入**：

- MongoDB 中的 `raw_posts` / `raw_comments`（采集自 mock_weibo / weibo / news 三源）
- 事件窗口边界（时间范围 + 主题关键词）
- 检测参数（`enable_channels`、`alpha`、`sim_threshold`、`time_window`）

**输出**：

- `coordinated_network` 图：节点 = 账户，边 = `(u, v, channels[], adjusted_p, edge_score, evidence_samples[])`
- `coord_groups` 群组聚类：每组含 `members[]`、`size`、`dominant_channels`、`group_score`
- 边级证据链：每条边给出最显著的样本（具体 url / hashtag / 媒体哈希 / cascade root）

### 1.2 学界 + 工业界对标

| 对标对象 | 类型 | 与 F-COORD 的关系 |
|---|---|---|
| CooRTweet (R) | 学界开源算法 | 共享对象协同检测的基线，已 Python 重写为 `core/coordination/detector.py` |
| Pacheco et al. 2020 (KDD) | 学术方法 | 单侧 z-score 配对显著性，PSL 升级为对称双账号超几何 |
| Sharma 2021 (KDD) | 学术方法 | object-level 显著性，PSL 升级为 pair-level + Cauchy combination |
| Seckin et al. 2024 | 数据集 | 26 个 IO campaign + 13M 有机对照，PSL 的 FDR 校准数据来源 |
| Graphika | 工业界 | 跨平台影响行动分析平台，提供 F-COORD 的产品形态参考 |
| AIM-trics | 学术工具 | 多平台协同检测工具集，PSL 借鉴其多通道融合思路 |

### 1.3 产品对标缺口

KT2 有「知微传播」这种成熟商业对标，KT1 缺乏单一商业产品对标，主要参照学界。建议后续补充：

- 试用 Graphika / CrowdTangle 类产品，整理截图与功能清单
- 关注 Pacheco / Sharma 在 2024-2025 的后续工作
- 收集 DARPA INCAS、SemEval 等评测中的协同检测系统

---

## 二、主要技术：KT1 PSL 的核心创新（research）

### 2.1 PSL 是什么

**Pair Surprisal Layer** 是一个**即插即用的配对显著性评估层**，叠加在冻结的 CooRTweet 共享对象检测引擎之上。核心创新在于**从 object-level 显著性升级到 pair-level 显著性**，通过三层统计机制消除热门话题误报。

### 2.2 算法四步流程

```
输入：multi-channel object groups（来自 CooRTweet detect_groups 等）
  │
  Step 1：对称双账号超几何检验
    p_u = hypergeom.sf(k-1, N, K_u, n_pair)
    p_v = hypergeom.sf(k-1, N, K_v, n_pair)
    p_pair = max(p_u, p_v)              ← 对称化，校正活跃度差异
  │
  Step 2：Cauchy combination
    T = (1/m) Σ tan((0.5 - p_i) · π)    ← 跨 object / 跨 channel 融合
    p_combined = 0.5 - arctan(T) / π    ← 无独立性假设
  │
  Step 3：Pair-level BH-FDR
    在配对层级（非 object 层级）做 BH 校正
    输出 adjusted_p, edge_score = -log10(adjusted_p)
  │
  Step 4：证据组装
    每条 (u, v) 边给出 top-1 evidence per channel
    {channel, object, k, K_u, K_v, n_pair, p_channel, raw_example_id}
  │
输出：coordinated edges with FDR-controlled significance + per-channel evidence
```

### 2.3 与对标方法的差异

| 维度 | Pacheco 2020 | Sharma 2021 | CooRTweet | **PSL** |
|---|---|---|---|---|
| 显著性层级 | pair-level | object-level | percentile-based | **pair-level** |
| 多重检验校正 | 无 | object-level FDR | 无 | **pair-level BH-FDR** |
| 多通道融合 | 单通道 | 单通道 | 单通道 | **Cauchy combination** |
| 活跃度校正 | 单侧 z-score | object-level | 无 | **对称 max(p_u, p_v)** |
| 形式化 FDR 保证 | 无 | 局部有 | 无 | **有** |
| 证据可解释性 | 弱 | 中 | 强 | **强（per-channel evidence）** |

### 2.4 错位矩阵 M1-M5 与 ADR-001（systemDesign.md:87-112）

系统设计文档明确了 5 个"系统功能 ↔ 关键技术"错位项，本期 MVP 的处理策略：

| 错位项 | 错位内容 | MVP 策略 |
|---|---|---|
| M1 多模态展示 | 系统宣传跨模态融合，但检测层单模态 | 由 C2（前端搜索）承载 5 要素同屏展示，C3（检测）保持单模态 PSL |
| M2 跨平台身份 | 宣传跨平台，实际是跨源 | 对外口径改为"跨源协同（社交+新闻）"，延后跨平台身份解析 |
| M3 类型分类 | 想做 astroturfing / brigading 多任务 | 本期仅二分类 + 边类型标签（object/semantic/cascade） |
| M4 证据输出 | `detect_groups` 缺 `evidence_samples` | PSL Step 4 补齐 evidence per channel |
| M5 搜索 API | 系统级搜索能力缺失 | 新增 MongoDB text index + 6 facets（C2 子系统） |

**ADR-001**（多模态扩展触发）：当 Object + Semantic 通道融合 FDR > 0.2 时，激活 CLIP 图像通道（本期预留接口，不实现）。

### 2.5 研究 claim 与消融

EXPERIMENT_PLAN.md 定义了 4 个核心 claim：

| Claim | 命题 | 验证方式 |
|---|---|---|
| Claim 1 | `max(p_u, p_v)` 优于 min / product / 单侧 | 在 Seckin 2024 数据集上的 5 变体消融 |
| Claim 2 | Cauchy combination 优于 Fisher's method | 在依赖结构下的 type-I error 对比 |
| Claim 3 | Pair-level BH-FDR 优于 object-level | permutation-based FDR 校准图 |
| Claim 4 | 多通道融合优于单通道 | 在热门话题压力测试上对比 |

---

## 三、其他技术支持（标签：research / engineering / 边界）

### 3.1 共享对象检测（CooRTweet 算法移植）

- **标签**：engineering（已实现，冻结）
- **位置**：`new-system/backend/app/core/coordination/detector.py`（177 行）
- **职责**：时间窗内配对 + `flag_speed_share()` 快窗标记 + `account_stats()` / `group_stats()` 统计
- **接口约束**：本期对 `detect_groups` 输出**只增不改**——新增 `evidence_samples[]`、`channels[]`、`q_adjusted` 字段，保持向后兼容

### 3.2 多通道 Object 提取

- **标签**：engineering（规则化提取）
- **位置**：`new-system/backend/app/core/coordination/channels.py`（**待新增**）
- **职责**：从 raw_posts / raw_comments 提取多通道 object，统一为 `[object_id, channel, subtype, account_id, content_id, timestamp]` DataFrame
- **通道清单**：
  - `object/link`：URL（包括短链展开后的最终 URL）
  - `object/hashtag`：# 话题
  - `object/media`：图片 / 视频的内容哈希（pHash）
  - `cascade/reply_chain`：评论链向上回溯到根 post
- **降级策略**：raw_comments 为空时禁用 cascade 通道

### 3.3 语义向量编码（边界）

- **标签**：边界（模型选择是 research、调用是 engineering）
- **位置**：`new-system/backend/app/core/coordination/semantic.py`（**待新增**）
- **职责**：冻结句向量编码器 + mutual-kNN 找到语义近似账户对
- **当前选择**：text2vec-base-chinese（CPU 友好，384 维）
- **工程降级**：编码失败时降级为 jieba + TF-IDF + sparse cosine
- **research 部分**：kNN 池大小 M（默认 1000）、相似度阈值（默认 0.85）、零分布近似的合理性

### 3.4 统计检验包装

- **标签**：engineering
- **位置**：`significance.py` 内
- **依赖**：`scipy.stats.hypergeom`、`statsmodels.stats.multitest.multipletests`
- **职责**：把 PSL 算法实现包装为可单元测试的纯函数

### 3.5 协同图聚合

- **标签**：engineering（已实现）
- **位置**：`new-system/backend/app/core/coordination/network.py`（166 行）
- **职责**：加权无向图构建 + 分位数阈值 + 连通分量
- **本期改动**：扩展边属性以接收 PSL 输出（`channels[]`、`adjusted_p`、`edge_score`、`evidence_samples[]`）

### 3.6 协同检测 API

- **标签**：engineering（已实现，需扩参数）
- **位置**：`new-system/backend/app/api/v1/coordination.py`（27 行）
- **端点**：`POST /api/v1/coordination/detect`
- **本期改动**：新增请求参数 `enable_channels`、`alpha`、`sim_threshold`、`time_window`，向后兼容默认值

### 3.7 服务层编排

- **标签**：engineering
- **位置**：`new-system/backend/app/services/coordination_service.py`（90 行，待扩）
- **职责**：串联 raw_posts → channels.extract → detector.detect_groups → significance.compute → network.aggregate

### 3.8 前端协同网络可视化

- **标签**：engineering（已实现）
- **位置**：`new-system/frontend/src/views/coordination/index.vue`
- **本期改动**：边的颜色按 `dominant_channel` 区分（object=蓝 / semantic=绿 / cascade=橙）；点击边弹出 `evidence_samples` 详情

### 3.9 多模态展示承载（C2 搜索子系统）

- **标签**：engineering（待新增）
- **职责**：M1 错位项的产品级承载——5 要素同屏（文本 / 图片 / 视频 / 外链 / 元数据）
- **依赖**：MongoDB text index + 6 facets（事件 / 时间 / 平台 / 媒体类型 / 协同标签 / 风险等级）

---

## 四、功能拆解：产品级功能点

| # | 功能点 | 做什么 | 输入 | 输出 | 落点文件 | 标签 |
|---|---|---|---|---|---|---|
| F1 | 多通道 Object 提取 | url/hashtag/media/cascade → object_id | posts + comments DataFrame | `[object_id, channel, subtype, account_id, content_id, timestamp]` | `channels.py`（新增） | engineering |
| F2 | 共链接对检测 | 同一 link 的账号对 | F1 输出（link subtype） | `(u, v, object_id, count)` | `detector.py`（冻结） | engineering |
| F3 | 共媒体对检测 | 媒体内容哈希相同的账号对 | F1 输出（media subtype） | `(u, v, object_id, count)` | `detector.py`（冻结） | engineering |
| F4 | 语义近似对检测 | 冻结句向量 + mutual-kNN | posts content + frozen encoder | `(u, v, p_sem)` | `semantic.py`（新增） | 边界 |
| F5 | 级联对检测 | reply_to 链向根帖 | raw_comments reply_to → root_post_id | `(u, v, cascade_*, count)` | `channels.py`（新增） | engineering |
| F6 | 配对惊讶值计算 | 对称超几何检验 per (u,v,o) | F1-F5 输出 | per-object p-values | `significance.py`（新增） | research |
| F7 | 共振 vs 协同筛查 | Cauchy combine + BH-FDR per pair | F6 输出 | `combined_p, adjusted_p, edge_score` | `significance.py`（新增） | research |
| F8 | 协同群组聚合 | 连通分量 + 社区发现 | F7 输出 | `coord_group_id, members[], size` | `network.py`（小改） | engineering |
| F9 | 边证据展示 | 聚合通道证据 + 选 top-1 | F6 + F1 raw 数据 | `evidence_samples[]` per edge | `significance.py`（新增） | engineering |
| F10 | API 检测端点 | 处理 HTTP 请求 + 调用服务层 | 请求参数 | JSON 响应 | `api/v1/coordination.py`（扩） | engineering |
| F11 | 前端网络可视化 | ECharts force-directed | 服务端 JSON | 交互式图 | `frontend/views/coordination/` | engineering |
| F12 | 多模态搜索（C2） | text index + 6 facets | 搜索关键词 | 命中帖子（5 要素同屏） | 前端新增 | engineering |

---

## 五、现有代码资产 vs 待新增

### 5.1 已有（旧方向 CooRTweet MVP）

| 文件 | 行数 | 状态 | 本期改动 |
|---|---|---|---|
| `core/coordination/detector.py` | 177 | 冻结 | 不改（仅扩 IO 字段） |
| `core/coordination/network.py` | 166 | 已实现 | 边属性扩展接收 PSL 输出 |
| `core/coordination/stats.py` | 90 | 已实现 | 增加通道分布列 |
| `services/coordination_service.py` | 90 | 已实现 | 注入多通道提取 + PSL 调用 |
| `api/v1/coordination.py` | 27 | 已实现 | 扩参数 enable_channels/alpha/sim_threshold |
| `frontend/views/coordination/index.vue` | — | 已实现 | 边颜色 + 证据点击 |

### 5.2 待新增（PSL 新方向）

| 文件 | 工作包 | 预估行数 | 核心职责 |
|---|---|---|---|
| `core/coordination/significance.py` | WP-2 | ~400 | PairSurprisalLayer（对称超几何 + Cauchy + BH-FDR + 证据组装） |
| `core/coordination/semantic.py` | WP-3 | ~300 | SemanticPairAdapter（冻结编码 + kNN + 零分布 + p_sem） |
| `core/coordination/channels.py` | WP-1/4 | ~200 | 多通道 Object/Semantic/Cascade 提取 + 统一 DataFrame |
| `tests/test_coordination_multi.py` | WP-6 | ~500 | 5 消融变体 + 通道覆盖 + 热门话题压力测试 + 证据完整性 |

**WP 执行顺序**：

```
WP-1 (多通道提取) ─┬──> WP-5 (network+API) ──> WP-7 (前端最小适配)
WP-2 (PSL)        ├──>
WP-3 (Semantic)   ├──>
WP-4 (Cascade)    ─┴──>
WP-6 (mock+测试) 贯穿全程
```

---

## 六、research vs engineering 拆分边界（F-COORD 视角）

### 6.1 research 任务（本地实验）

| # | 任务 | 阻塞 / 数据来源 | 验证 |
|---|---|---|---|
| R1 | PSL 对称超几何 + Cauchy + BH-FDR 核心算法实现 | 代码未开始 | 单元测试覆盖 4 步流程 |
| R2 | Claim 1 消融：max vs min vs product vs 单侧 | 需 Seckin 2024 IO 标注数据集 | 在 26 个 IO campaign 上的 precision-recall 对比 |
| R3 | Claim 3 FDR 校准：permutation-based FDP vs target α | 需打乱数据生成 null | observed FDP curve 接近 target α |
| R4 | 语义通道：模型选择 + kNN 池大小 M + 阈值 sim_threshold | 需 mock + 真实数据 | 在 mock 数据上验证 p_sem 零分布近似 |
| R5 | 级联通道：超几何检验在评论链上的合理性 | 子类型统计性质未验证 | 评论的独立性假设是否成立 |
| R6 | ADR-001 多模态扩展触发条件 | 设计完成，验证待 | 文本通道 FDR 边界 case |

### 6.2 engineering 任务（Claude Code）

| 优先级 | # | 任务 | 工作量 |
|---|---|---|---|
| P1 | E1 | `channels.py` 多通道 Object 提取（规则化） | 3-4 h |
| P1 | E2 | `coordination_service.py` 扩展以串通新通道 | 2 h |
| P1 | E3 | `api/v1/coordination.py` 扩参数 + 向后兼容 | 1 h |
| P1 | E4 | `network.py` 边属性扩展 + 颜色映射 | 2 h |
| P1 | E5 | 前端协同网络可视化更新（边颜色 + 证据 popover） | 3 h |
| P2 | E6 | C2 搜索子系统：MongoDB text index + 6 facets API | 1-2 d |
| P2 | E7 | C2 搜索子系统：前端 5 要素同屏页 | 1-2 d |

### 6.3 边界 case

- **语义通道**：模型选择属于 research，但加载 + 调用 + 降级是 engineering。处理方式：R4 决定模型后，E2 的服务层调用是 engineering。

---

## 七、关键设计决策与开放问题

### 7.1 关键决策

1. **PSL 即插即用，detector.py 冻结**（systemDesign.md ADR-001）
   - 理由：减小回归风险，确保旧 API 完全向后兼容
   - 影响：所有新算法逻辑在 `significance.py` 中实现

2. **默认 `enable_channels=["object"]` 向后兼容**
   - 理由：现有客户端代码无须改动
   - 影响：需回归测试验证默认参数返回结构完全不变

3. **本期 MVP 仅文本语义，CLIP 图像延后**（ADR-001 触发条件）
   - 理由：避免过度承诺，CPU-only 部署
   - 影响：M1 多模态错位由前端 C2 承载，不在检测层

4. **时间同步降级为全局约束，不作为独立通道**（EXPERIMENT_PLAN.md:18-26）
   - 理由：避免重复计数，时间窗已在 detector 内
   - 影响：检测通道清单只剩 object / semantic / cascade

### 7.2 开放问题

1. **`max(p_u, p_v)` 的理论合理性**
   - 现状：直觉上对称、避免活跃账号单方面拉高
   - 待验证：与 intersection-union 测试的形式化关系
   - 阻塞：Claim 1 消融实验必须包含此对比

2. **语义 kNN 池过小时的降级**
   - 现状：池跨账号对 < 100 时方案未定
   - 候选：扩大 k / 全窗口随机对 / 禁用语义通道
   - 阻塞：需 R4 实验决定

3. **级联通道的独立性假设**
   - 现状：超几何检验假设回复是随机抽样
   - 风险：实际可能有演员倾向，违反假设
   - 缓解：降级策略（raw_comments 过小时禁用 cascade）

4. **C2 搜索子系统的工作量**
   - 现状：M5 错位项要求新增搜索能力
   - 范围：MongoDB text index + 6 facets + 5 要素同屏页
   - 估计：1-2 周 engineering 工作，影响 MVP 时间表

5. **跨平台身份解析（M2 延后项）**
   - 现状：对外口径为"跨源协同"而非"跨平台身份"
   - 长期：未来引入 user embedding 跨平台对齐

---

## 八、对其他 KT / 全系统的接口契约

### 8.1 F-COORD → F-PROP（KT1 → KT2）

**契约文件**：`aris/shared/CROSS_KT_DEPS.md`

```python
# F-COORD 输出
coordination_result = {
    "coord_groups": [
        {
            "group_id": "G_001",
            "members": ["uid_a", "uid_b", "uid_c"],
            "size": 3,
            "dominant_channels": ["object/link", "semantic"],
            "group_score": 0.85,
            "evidence_edges": [
                {"u": "uid_a", "v": "uid_b", "channels": ["object/link"],
                 "adjusted_p": 1e-5, "evidence_samples": [...]}
            ]
        }
    ],
    "network_density": 0.42,
    "asymmetry_index": 0.18,
}
```

**消费方**：F-PROP 的 `trend_predictor.py` 把 `coord_groups` 数量、`network_density` 作为特征输入。

### 8.2 F-COORD → F-RISK（KT1 → KT3）

**契约**：F-RISK 的 `evidence_builder.py` 消费同样的 `coordination_result`，提取 Gini / Shannon 等聚合统计。

**当前状态**：KT3 已实现消费端，KT1 PSL 实现完成后即可联调。

### 8.3 F-COORD ← 数据采集

**契约**：
- MongoDB 集合 `raw_posts`：`{platform, post_id, account_id, content, created_at, urls[], hashtags[], media_hashes[], reply_to}`
- MongoDB 集合 `raw_comments`：`{platform, comment_id, account_id, post_id, root_post_id, content, created_at, reply_to}`

**已实现**：`core/crawler/normalizer.py` 已保证字段标准化。

### 8.4 F-COORD → 前端

**API 契约**：

```http
POST /api/v1/coordination/detect
{
  "event_id": "evt_001",
  "time_range": ["2026-05-10T00:00:00Z", "2026-05-17T00:00:00Z"],
  "platforms": ["weibo", "news"],
  "enable_channels": ["object", "semantic", "cascade"],  // 新增
  "alpha": 0.01,                                          // 新增
  "sim_threshold": 0.85,                                  // 新增
  "time_window": 300                                      // 秒
}
```

```json
// 响应
{
  "graph": {
    "nodes": [{"id": "uid_a", "label": "...", "size": 12}],
    "edges": [
      {
        "source": "uid_a", "target": "uid_b",
        "channels": ["object/link"],
        "adjusted_p": 1e-5,
        "edge_score": 5.0,
        "evidence_samples": [{"channel": "object/link", "object": "http://...", "k": 8, "n_pair": 12, ...}]
      }
    ]
  },
  "groups": [...]
}
```

---

## 九、引用

| 类别 | 路径 | 用途 |
|---|---|---|
| 系统设计 | [systemDesign.md](./systemDesign.md) | 12 节统一设计 + 错位矩阵 M1-M5 + ADR-001 + 里程碑 M0-M6 |
| 研究简述 | [RESEARCH_BRIEF.md](./RESEARCH_BRIEF.md) | 旧新方向对比 + 问题陈述 + 非目标 |
| 实验计划 | [EXPERIMENT_PLAN.md](./EXPERIMENT_PLAN.md) | WP-1~7 工作包 + 验证策略 + Claim 1-4 |
| 最终提案 | refine-logs/FINAL_PROPOSAL.md | PSL 完整技术规范 + 消融设计 + 集成表 |
| 文献综述 | LITERATURE_REFERENCES.md | 14 篇核心论文 + 5 数据集 + 关键概念定义 |
| 验收标准 | [ACCEPTANCE.md](./ACCEPTANCE.md) | 功能 + 测试 + 非目标 |
| 任务追踪 | [TASK_TRACKER.md](./TASK_TRACKER.md) | WP 进度 + 会话记录 |
| 背景文档 | [../../doc/research/key-technology-background/coordination-detection.md](../../doc/research/key-technology-background/coordination-detection.md) | 问题定义 + 技术背景 + 验证方式 |
| 状态记忆 | [../../memory/state_kt1.md](../../memory/state_kt1.md) | KT1 状态 + 阻塞点 |
| 系统总览 | [../../doc/engineering/research-engineering-split.md](../../doc/engineering/research-engineering-split.md) | 三大功能 research/engineering 总表 |

---

## 十、后续动作

**第一周（engineering，Claude Code 主导）**：

1. E1 `channels.py` 多通道 Object 提取 → 3-4 h
2. E4 `network.py` 边属性扩展 → 2 h
3. E2 `coordination_service.py` 串通 → 2 h
4. E3 `api/v1/coordination.py` 扩参数 → 1 h
5. E5 前端可视化更新 → 3 h

**第二周（research，本地实验）**：

1. R1 PSL 算法实现 → 4-5 d（含单元测试）
2. R4 语义通道实验（模型选择 + kNN 调参） → 2 d
3. R2 Claim 1 消融实验 → 2 d（需先获取 Seckin 2024 数据集）

**第三周（联调 + ADR-001 验证）**：

1. F-COORD ↔ F-PROP / F-RISK 联调
2. R3 FDR 校准实验
3. R6 ADR-001 触发条件验证（融合 FDR > 0.2）

**M5 搜索子系统（C2）作为独立 sprint，P2 优先级**。
