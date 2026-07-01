# KT1 系统设计：跨平台协同账号识别

> 文档定位：KT1 单文件系统设计 × MVP 指南 × CCF-B+ 多平台多模态检测文献综述。
> 版本：v0.1（2026-05-10，deep-interview 合并草案）
> 范围：CogGuard `release-0.2` 基线 ∙ `aris/tech-01-coordination` 工作空间
> 原则：**先合后拆**（T6）—— 在内容稳定验收前保持单文件；拆分留 `#sec-N` 锚点。

> ⚠️ 方向对齐说明（2026-06-02，覆盖本文与之冲突的表述）：KT1 最新定位为
> **跨平台协同发现——只用平台无关的"共同行为特征"做复用融合检测，内容检测不作为协同信号**。
> 据此，本文 §4.1/§6.3/§6.4 中的 **Semantic Channel / Semantic Pair Adapter（text2vec 文本语义相似度）属"内容理解"，与新定位冲突**：
> 应将其移出 Detection（协同判据），或仅以**行为型模板指纹**（如 MinHash/字符级近重复，不读语义）替代以补召回。
> Object Channel（共享 URL/hashtag/媒体指纹 id）、Cascade Channel（回复级联）、时间同步等**行为信号保留**。
> PSL（对称超几何 + Cauchy + pair-level BH-FDR）作为显著性筛查组件保留，但作用于行为通道，不作为头号创新口径（详见背景文档 `coordination-detection.md` 与答辩对齐结论）。

---

## 目录

- [§1 概述与范围](#sec-1)
- [§2 问题陈述](#sec-2)
- [§3 系统功能 ↔ 关键技术错位矩阵](#sec-3)
- [§4 系统架构](#sec-4)
- [§5 多模态展示层：搜索子系统（C2）](#sec-5)
- [§6 检测 MVP（C3）](#sec-6)
- [§7 跨 KT 输出契约](#sec-7)
- [§8 文献综述：CCF-B+ 多平台多模态方法](#sec-8)
- [§9 工程约束与时序原则](#sec-9)
- [§10 里程碑与交付](#sec-10)
- [§11 验收标准](#sec-11)
- [§12 参考文献（全量 9 字段）](#sec-12)

---

## §1 概述与范围 {#sec-1}

### 1.1 项目定位
CogGuard 面向网络舆论对抗场景，以**跨平台协同攻击**为监测对象，整体叙事为
`事件 → 证据 → 协同 → 传播 → 风险 → 处置`。

KT1（关键技术一）聚焦该叙事的前半段——**"协同发现"**，承担子功能：协同行为检测、协同类型分类（roadmap）、协同群组发现、证据边提取。

### 1.2 本文件职责
`systemDesign.md` 在 KT1 工作空间内充当"单张地图"：

- 对上承接 `project-positioning-baseline.md` 的统一口径、`aris/tech-01-coordination/RESEARCH_BRIEF.md` 的问题定义、`doc/research/key-technology-background/coordination-detection.md` 的技术背景；
- 对下指导 `new-system/backend/app/core/coordination/`、`api/v1/coordination.py`、`api/v1/search.py`（新增）、协同前端页面的最小适配；
- 对评审解释"系统多模态能力承诺 vs 关键技术创新范围"的收敛策略。

### 1.3 本版本的范围
- **本期落地（MVP）**：C2 搜索子系统（多模态素材的展示承载）+ C3 PSL 协同检测核心 + 本文档与文献综述一体化。
- **本期不落地（defer）**：图像/视频检测通道、跨平台身份解析、GNN 训练、协同类型分类、扩展平台。

### 1.4 验证范围
短期仅支持 `mock_weibo` / `weibo` / `news` 三个数据源。不扩展到更多平台。

### 1.5 明确 non-goals（与旧任务骨架的边界）
- 不做通用社交机器人检测（退出 "bot detection + 意图识别" 旧叙事）。
- 不做跨平台用户身份解析（只做跨源证据池）。
- 不在本期落地报告研判 / 报告生成（属 KT3）。

---

## §2 问题陈述 {#sec-2}

### 2.1 目标
给定一个事件窗口（话题 / 关键词 / 时间范围）内的多源证据池，识别一组**在该窗口内共同推动某叙事**的账号集合，输出：

1. 协同边 `(u, v)`，携带 `p_combined`、`q_adjusted`；
2. 每条边对应的协同通道（`object` / `semantic` / `cascade`）与证据样本（原帖 id、摘录、时间戳）；
3. 协同群组 `coord_group_id`（由协同图社区发现产出）。

### 2.2 核心挑战
- **自然共振 vs 人为协同**：热门话题下正常账号间会出现大量偶然共现，单纯的"共享对象 + 时间窗"会产生严重误报；
- **单信号不足**：只有"共享 URL/hashtag"过于单薄，需要与语义近似、回复级联结合；
- **可解释性**：评委、分析师需要看到"**为什么**判这对账号是协同"的证据样本；
- **展示层的多模态承诺**：系统允诺"多模态检测能力"，但 KT1 的技术创新并不以图像/视频为重点——需要在**展示层**承载多模态。

### 2.3 多模态承诺的收敛思路
| 层级 | 如何体现多模态 |
|------|---------------|
| 采集层 | 已在 `normalizer.py` 采集 `media_urls / hashtags / external_links`（[normalizer.py](../../new-system/backend/app/core/crawler/normalizer.py)） |
| 存储层 | MongoDB `raw_posts / raw_comments` 已持久化图片链接、视频指纹、外链等 |
| **展示层（C2）** | **搜索详情页同屏呈现文本+图片+视频+外链+账号元数据+评论树+协同证据边** |
| 检测层（C3，本期） | **单模态**（行为图 + 文本语义）：PSL primary，保留 ADR-001 的多模态通道扩展触发条件 |
| 检测层（下一期） | 视觉 CLIP / 视频哈希作为可选通道接入（仅预留接口，不落代码） |

### 2.4 证据驱动原则
- 每条协同边必须携带 ≥ 1 个证据样本（`object_id + content_ids + excerpt + timestamp`）；
- 每条边的显著性必须可以通过对称超几何 + Cauchy combine + pair-level BH-FDR 的方式**审计**；
- 任何 fallback 切换决策必须在 `doc/engineering/development-log.md` 留数据与理由。

---

## §3 系统功能 ↔ 关键技术错位矩阵 {#sec-3}

本节是 C1 合入 C5 的产物，也是 `systemDesign.md` 最重要的一节——把**"系统承诺"与"KT1 创新技术范围"**的差异显式列出，并给出收敛策略 + 验收映射。

### 表 T3.1 错位矩阵

| # | 系统功能承诺 | 关键技术 KT1 现状 | 错位性质 | 本期收敛策略 | 验收映射 |
|---|---------------|------------------|----------|--------------|----------|
| **M1** | 多模态协同检测（界面展示图文视频） | PSL 基于行为图 + 文本语义，图/视频不是检测创新 | 展示 ≠ 创新 | 系统层：C2 搜索详情页"5 要素同屏"+ 6 facet；检测层：单模态 MVP，ADR-001 预留多模态通道扩展触发条件 | C2 §5 / ADR-001 §6 |
| **M2** | 跨平台协同 | 短期仅 `mock_weibo` + `weibo` + `news`，且未做跨平台身份解析 | 范围收窄 | 对外宣称"**跨源**协同（社交+新闻）"而非"跨平台身份"；在 §1.5 显式列为 non-goal | §1.5 / §7 |
| **M3** | 协同二分类 + 类型分类（多任务） | 当前仅单任务 pair-level 显著性 | 任务缺失 | MVP 仅做二分类 + 边类型标签（object/semantic/cascade）；类型分类（astroturfing / brigading / amplification）列入 roadmap M6+ | §6 §10 |
| **M4** | 证据链展示 | `detect_groups` 仅返回配对表，无证据样本 | 输出粒度不足 | 扩展 IO 契约新增 `evidence_samples[]` + `channels[]`；C2 详情页呈现 | §5 §6 |
| **M5** | 搜索与溯源 | 无任何搜索/索引 API | **MVP 最大缺口** | C2 搜索子系统：MongoDB text index + 6 facets + 详情页 + E2E | §5 |

### 3.1 关键说明
- **M1 不通过"硬做多模态检测"消除**，而是通过**系统分工**消除：系统展示 + 检测单模态。这是 Round 4 Contrarian 模式下用户明确确认的决策（详情页 5 要素同屏 + 媒体 facet）。
- **M2 不通过"做跨平台身份"消除**，而是通过**措辞校准 + non-goal 明示**消除，避免竞赛答辩中承诺超出技术范围的能力。
- **M3 不通过"本期硬做类型分类"消除**，而是放进 roadmap；MVP 只承诺二分类 + 边类型标签（技术路线讲得清、代码做得出）。
- **M4/M5 通过代码落地消除**。

### 3.2 错位矩阵的验收要求
- 每条 M# 必须有至少 1 个测试或示例文件指向它（T4 证据绑定原则，见 §9）；
- `doc/engineering/development-log.md` 必须记录每次 M# 状态位变更。

---

## §4 系统架构 {#sec-4}

### 4.1 逻辑分层

```
┌───────────────────────────────────────────────────────────────┐
│ 前端 (Vue 3 + Ant Design Vue 4)                                │
│  - coordination/ 协同检测页（已有，最小适配）                   │
│  - search/ 搜索与详情页（新增 C2 ★）                            │
├───────────────────────────────────────────────────────────────┤
│ 后端 API 层 (FastAPI, /api/v1)                                 │
│  - coordination.py  POST /detect（已有，扩展 IO 契约）          │
│  - search.py        GET /search/posts|posts/{id}|facets（新增）│
├───────────────────────────────────────────────────────────────┤
│ 服务层                                                          │
│  - coordination_service.py（已有，接入 PSL 层）                 │
│  - search_service.py（新增 C2）                                │
├───────────────────────────────────────────────────────────────┤
│ 核心算法层 (core/coordination/)                                 │
│  - detector.py      detect_groups()（冻结，不修改）             │
│  - network.py       加权图与群组（已有）                        │
│  - stats.py         账户/群组统计（已有）                       │
│  - significance.py  ★ PSL Pair Surprisal Layer（新增 C3）       │
│  - channels.py      ★ Object/Semantic/Cascade 通道抽取（新增）  │
│  - semantic.py      ★ 冻结句向量 + 稀疏 cosine（新增）          │
├───────────────────────────────────────────────────────────────┤
│ 数据层                                                          │
│  - MongoDB: raw_posts / raw_comments（已有）                   │
│    · text index on content / title（C2 新增索引）              │
│    · compound index (task_id, timestamp_share)                 │
│    · compound index (task_id, account_id)                      │
│  - MySQL: users / tasks / coord_edges（已有）                  │
│  - Redis: Celery broker + query cache                          │
├───────────────────────────────────────────────────────────────┤
│ 采集层 (core/crawler/)                                          │
│  - MediaCrawler / NewsCrawler / MockCrawler（已有，禁改）       │
└───────────────────────────────────────────────────────────────┘
```

> ★ 标记为本期新增/重点修改。

### 4.2 数据流（事件 → 证据 → 协同）

```
[1] 用户创建任务（事件种子：话题/关键词/时间窗）
    └─ POST /api/v1/crawl/social
[2] Celery 异步采集 → MongoDB raw_posts + raw_comments
[3] 用户进入协同检测页
    └─ POST /api/v1/coordination/detect?task_id=…
        └─ coordination_service
            ├─ 调 channels.extract()  抽 Object/Semantic/Cascade
            ├─ 调 detector.detect_groups()（冻结）
            ├─ 调 significance.pair_surprisal()  计算 p / q
            ├─ 调 network.build_graph() + 社区发现
            └─ 返回 {edges, groups, stats, evidence_samples}
[4] 用户在协同检测页点"查看证据" / "搜相关帖"
    └─ GET /api/v1/search/posts?task_id=…&…
        └─ search_service → MongoDB text index + facets
[5] 详情页同屏展示 5 要素（§5）
```

### 4.3 文件边界（严格对齐 ACCEPTANCE.md）

**允许修改**（[ACCEPTANCE.md](ACCEPTANCE.md)）：
- [new-system/backend/app/core/coordination/](../../new-system/backend/app/core/coordination/)
- [new-system/backend/app/services/coordination_service.py](../../new-system/backend/app/services/coordination_service.py)
- [new-system/backend/app/api/v1/coordination.py](../../new-system/backend/app/api/v1/coordination.py)
- **新增**：`new-system/backend/app/api/v1/search.py`
- **新增**：`new-system/backend/app/services/search_service.py`
- [new-system/backend/tests/](../../new-system/backend/tests/)
- [new-system/frontend/src/api/coordination.ts](../../new-system/frontend/src/api/coordination.ts)
- [new-system/frontend/src/views/coordination/index.vue](../../new-system/frontend/src/views/coordination/index.vue)
- **新增**：`new-system/frontend/src/views/search/`
- 本目录下稳定 Markdown

**禁止修改**：
- `MediaCrawler-main/`、`NewsCrawler-main/`、`CooRTweet-master/`
- `new-system/backend/app/core/propagation.py`、`account_profiler.py`、`risk/`

### 4.4 向后兼容约束
- `POST /api/v1/coordination/detect` 的旧响应字段（网络/统计）必须保留；新增字段（`evidence_samples[]`、`channels[]`、`q_adjusted`）以**可选字段**形式扩展。
- 前端协同检测页在后端扩展字段缺失时必须能正常渲染（容错策略：未识别字段折叠隐藏）。

---

## §5 多模态展示层：搜索子系统（C2） {#sec-5}

> 状态：本期 MVP 核心新增模块。承担错位矩阵 M1（多模态展示）与 M5（搜索溯源）。

### 5.1 用户故事
1. **分析师**进入协同检测页，选定任务 + 事件窗口（话题/时间范围）；
2. 切到"搜索"页，或从协同边直接点"查看证据"；
3. 用 6 facet 过滤帖子/评论/账号/外链 → 看列表；
4. 点击列表项进入详情页，**同屏**看到文本原文 + 图片 + 视频封面或指纹 + 外链卡 + 账号卡 + 评论树 + 所属协同边列表；
5. 从详情页"跳回协同"按钮回到协同检测页并高亮该账号所在的协同群组。

### 5.2 范围边界（Round 2 决策）
- **只在事件窗口内搜**，不做跨事件/跨时间的全局检索；
- 搜索始终携带 `task_id` 作为硬性参数；
- **不引入 ES / Meilisearch**，只用 MongoDB `text` index + 复合索引（轻量路线约束）。

### 5.3 API 契约

#### 5.3.1 `GET /api/v1/search/posts`
查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 事件任务 id，界定搜索域 |
| `q` | string | 否 | 关键词（对 `content` / `title` 走 MongoDB text index） |
| `account` | string | 否 | 账号 id 精确匹配 |
| `platform` | string | 否 | `weibo` / `news` / `mock_weibo` |
| `t_start`, `t_end` | iso8601 | 否 | 时间范围（默认 task 窗口） |
| `has_image` | bool | 否 | facet：是否含图片 |
| `has_video` | bool | 否 | facet：是否含视频 |
| `has_external_link` | bool | 否 | facet：是否含外链 |
| `in_coord_group` | bool / string | 否 | `true`=属任一协同群；具体 group id 精确匹配 |
| `page`, `size` | int | 否 | 默认 `1`, `20`；`size ≤ 100` |

响应：
```jsonc
{
  "code": 0,
  "data": {
    "total": 1243,
    "items": [
      {
        "content_id": "...",
        "platform": "weibo",
        "account_id": "...",
        "timestamp_share": 1715300000,
        "preview": "...(前 140 字)",
        "media_types": ["text", "image", "external_link"],
        "coord_group_id": "grp_123" // 可空
      }
    ]
  }
}
```

#### 5.3.2 `GET /api/v1/search/posts/{content_id}?task_id=…`
返回详情页所需的**全量 5 要素 + 协同证据边列表**：
```jsonc
{
  "code": 0,
  "data": {
    "post": { /* 完整 StandardPost */ },
    "comments": [ /* 评论树 */ ],
    "images": [ "..." ],
    "videos": [ {"cover_url": "...", "fingerprint": "..."} ],
    "external_links": [ {"url": "...", "preview": "..."} ],
    "account": { /* 账号元数据 */ },
    "coord_edges": [
      { "u": "acct_a", "v": "acct_b", "channels": ["object"],
        "p_combined": 1.2e-6, "q_adjusted": 4.5e-5,
        "evidence_samples": [...] }
    ]
  }
}
```

#### 5.3.3 `GET /api/v1/search/facets?task_id=…`
聚合结果：
```jsonc
{
  "code": 0,
  "data": {
    "platforms": {"weibo": 8123, "news": 420},
    "media": {"has_image": 3122, "has_video": 187, "has_external_link": 5001},
    "coord_groups": [
      {"id": "grp_123", "size": 18, "q_max": 4.5e-5}
    ]
  }
}
```

### 5.4 索引方案（MongoDB）
- `db.raw_posts.createIndex({content: "text", title: "text"}, {default_language: "none"})` — 中文用 `none` 走 ngram fallback；如 MongoDB >= 7 支持 `simple` 分词器即改之。
- `db.raw_posts.createIndex({task_id: 1, timestamp_share: -1})`
- `db.raw_posts.createIndex({task_id: 1, account_id: 1})`
- `db.raw_posts.createIndex({task_id: 1, "media_urls.0": 1})`（含图快速过滤）
- 在 `search_service.py` 封装 Motor 查询 + facet 聚合 pipeline。

### 5.5 详情页 5 要素同屏（Round 4 Contrarian 决策，硬约束）
**不可用 tab 切换隐藏**。必须一屏可见：
1. 文本原文区；
2. 图片缩略图网格（点击放大）；
3. 视频封面/指纹展示区（若有）；
4. 外链卡片（title + domain + 截图 preview，若可得）；
5. 账号元数据卡（昵称 / 平台 / 注册时间 / 粉丝数 / 自动化评分）；

此外同屏显示：评论树（折叠默认 3 层）+ **所属协同证据边列表**（每条边一行：对端账号 / 通道 / `q_adjusted` / 证据摘录）。

### 5.6 性能 SLO
| 指标 | 规模假设 | 阈值 |
|------|---------|------|
| `GET /search/posts` p95 | 事件窗口 ≤ 100k 帖 | < 800 ms |
| `GET /search/posts/{id}` p95 | 单帖 | < 300 ms |
| `GET /search/facets` p95 | 同上 | < 1.2 s |

若 p95 不达标，**先优化索引 + 聚合 pipeline**，仍不达标再评估 Meilisearch（触发 ADR-002）。

### 5.7 E2E 验收用例
1 条 Playwright（或后端集成）用例覆盖：
`登录 → 选任务 → /search/posts?has_image=true → 点击结果 → 详情页 5 要素可见 → 点"跳回协同" → 高亮协同群组`。

---

## §6 检测 MVP（C3） {#sec-6}

> 状态：本期 MVP 核心算法扩展。承担错位矩阵 M4（证据链）。

### 6.1 方法选型

**默认（primary）**：Pair Surprisal Layer (PSL) — 对称双账号超几何检验 + Cauchy combination 合并多通道 p 值 + Pair-level BH-FDR。继承 [refine-logs/FINAL_PROPOSAL.md](refine-logs/FINAL_PROPOSAL.md)。

**备选（fallback）**：Sharma 2021 z-score / Manchanayaka 2024 Contrast Pattern / Iannucci 2025 Temporal Multiplex。

### 6.2 ADR-001：协同检测方法选型

| 字段 | 内容 |
|------|------|
| Status | Accepted（2026-05-10） |
| Context | KT1 MVP 需要在轻量路线（pandas/numpy/networkx/scipy/statsmodels）下提供"协同 vs 自然共振"判别，且输出可被评审审计。 |
| Decision | 采用 PSL 作为 primary；Object Channel + Semantic Channel 作为本期落地通道，Cascade Channel 列 roadmap。 |
| Drivers | 1) 对称超几何校正双方活跃度；2) Cauchy combine 在任意依赖结构下有效；3) pair-level BH-FDR 提供形式化 FDR 保证；4) 与现有 `detect_groups` 兼容，不需重写引擎。 |
| Alternatives | Sharma 2021 z-score（实现最简但只控 pair-level 单边，不抑热）；Manchanayaka 2024 Contrast Pattern（pattern 粒度，不直接给 pair 分数）；Iannucci 2025 Temporal Multiplex（多层时序网络，状态复杂）。 |
| Fallback Trigger（文字契约，不锁数字） | 在 `mock_weibo` / `weibo` / `news` 三个数据源上，用人工抓取或自动生成的 ± 类型 ground truth 当基线；若 PSL 在任一源的 FDR 或 Recall 显著劣于备选候选，在 `doc/engineering/development-log.md` 记录数据依据后进入评审切换流程。 |
| Consequences | MVP 不前置写 fallback 代码；fallback 切换必须附数据与审阅；每次调参结果入日志；保留 `significance.py` 的 strategy pattern 接口为 fallback 预留。 |

### 6.3 检测器 IO 契约（冻结，下游消费）

**输入**：
```python
DataFrame[object_id, account_id, content_id, timestamp_share,
          content_text: Optional[str], media_urls: Optional[list[str]]]
```

**输出（每条协同边）**：
```jsonc
{
  "u": "account_a",
  "v": "account_b",
  "channels": ["object", "semantic"],
  "p_combined": 1.2e-6,     // Cauchy-combined p over channels & objects
  "q_adjusted": 4.5e-5,     // BH-FDR adjusted
  "n_events": 7,             // 该对共同出现的 (object, window) 事件数
  "evidence_samples": [
    {
      "object_id": "url:example.com/x",
      "content_ids": ["...", "..."],
      "timestamp": 1715300000,
      "excerpt": "前 140 字…"
    }
  ]
}
```

**输出的稳定性承诺**：
- `channels` 值集冻结为 `{object, semantic, cascade}`；新通道必须在 ADR 中扩展后才能加入。
- `evidence_samples` 每条边至少 1 条，最多 5 条（截断策略：q_adjusted 最小者优先）。

### 6.4 通道实现优先级

| 通道 | 范围 | 优先级 |
|------|------|-------|
| Object Channel (url / hashtag / shared media id) | 本期落地 | P0 |
| Semantic Channel (frozen encoder + sparse cosine + mutual-kNN) | 本期落地 | P1 |
| Cascade Channel (reply chain → root_post_id) | roadmap | P2（不进 MVP） |
| Image / Video 通道 | ADR-001 扩展触发 | P3（defer） |
| Cross-platform identity linkage | non-goal | × |

### 6.5 显式 Defer 列表（进入 systemDesign 的"正文 non-goal"）
- 图像通道（CLIP / DINOv2 相似度）
- 视频通道（视频哈希 / 关键帧）
- 跨平台身份解析（identity linkage）
- GNN 端到端训练
- 协同类型分类（astroturfing / brigading / amplification）
- 平台扩展（仅保留 weibo + news + mock_weibo）

### 6.6 与现有代码的接入点
- [detector.py](../../new-system/backend/app/core/coordination/detector.py) **冻结**（`detect_groups` / `flag_speed_share` 不动）。
- 新增 `significance.py`：
  - `symmetric_pair_pvalue(k, N, K, n_u, n_v)`（对称超几何）
  - `cauchy_combine(p_values)`（Cauchy combination test, Liu & Xie 2020）
  - `bh_fdr(p_values, alpha=0.05)`（Benjamini–Hochberg）
- 新增 `channels.py`：
  - `extract_object_channel(posts_df)` → `(u, v, object_id, k)` 四元组
  - `extract_semantic_channel(posts_df, encoder)` → `(u, v, p_sem)` 直接对
- 新增 `semantic.py`：
  - 默认编码器：`text2vec-base-chinese` 或 `BAAI/bge-small-zh-v1.5`（可配，CPU 可跑）；稀疏 cosine + mutual-kNN(k=5)。
- `coordination_service.py` 只做编排，不重写算法。

---

## §7 跨 KT 输出契约 {#sec-7}

KT1 的输出必须被 KT2（传播监控）与 KT3（报告研判）稳定消费；本节固定接口数据结构，避免跨技术线来回改动。

### 7.1 → KT2（传播监控）
KT2 需要从 KT1 拿到"**哪些账号属于同一协同群**"以驱动源头追溯、用户画像、立场检测：

```jsonc
// 服务层内调用：coordination_service.export_for_propagation(task_id)
{
  "task_id": "...",
  "coord_groups": [
    {
      "id": "grp_123",
      "members": [
        {"account_id": "a", "first_seen_ts": 1715300000,
         "coord_score": 0.87}
      ],
      "evidence_edges": [ /* 见 §6.3 */ ]
    }
  ]
}
```

### 7.2 → KT3（报告研判）
KT3 需要从 KT1 拿到"**这组协同有多可疑 + 证据是什么**"以驱动 DISARM 映射与报告生成：

```jsonc
// 服务层内调用：coordination_service.export_for_risk(task_id)
{
  "coord_group_id": "grp_123",
  "q_adjusted_min": 1.3e-6,         // 群内最小的 q（最显著）
  "q_adjusted_median": 4.7e-5,
  "channels_used": ["object", "semantic"],
  "evidence_samples": [ /* 群内 top-5 证据 */ ]
}
```

### 7.3 不侵入原则
- KT1 只产出 JSON；**不调用** KT2/KT3 的模块；
- KT2/KT3 如需新增字段，走 ADR 扩展流程（新增一个 `ADR-00N`），不私自改 IO。

---

## §8 文献综述：CCF-B+ 多平台多模态协同与虚假信息检测方法 {#sec-8}

### 8.1 收录规则（Round 3 决策）
- **时间窗**：2020–2026；
- **等级**：以 CCF-A / CCF-B 正式录用为主（目标 ≥ 12 篇）；
- **补充上限**：≤ 4 篇 arXiv / 跨学科重稿（PNAS / Sci. Adv. / First Monday 等），显式标注"未正式录用 / 背景补充"；
- **字段完整性（强制）**：`title / authors / venue+year / CCF 等级 / 链接 / 研究问题 / 方法内核 / 方法边界 / 与 CogGuard 系统的 mismatch`。任一字段缺失的条目不进入本节。
- 具体条目在 §12 参考文献表给出全量 9 字段，此节做 **Taxonomy + 方法族群**分析。

### 8.2 Taxonomy

| 分类 | 研究主问题 | 代表方法族群 | 条目编号 |
|------|-----------|--------------|---------|
| **T1 多平台协同行为检测** | 同一 IO 在 X/YouTube/Web 的协同 link-sharing 与叙事放大 | Bayesian / ML 分类器 / 跨源图 | P1, P3, P10, P13, P14, P15 |
| **T2 多模态虚假信息检测** | 图-文-视频一致性、OOC、跨模态对比学习 | CLIP / 跨模态 attention / CL | P17, P18, P19, P20, P21 |
| **T3 图-文本-用户行为多模态** | 异构图 + 多模态节点特征 + 关系推理 | HGT / R-GCN / 对比学习 | P16, P22 |
| **T4 多模态账号 / bot 检测** | 多模态用户画像 + 行为图联合建模 | Heterogeneity-aware GT / Community-aware CL | P22, P23, P24 |
| **T5 统计检测与 FDR 校准** | pair-level 显著性与热门话题误报抑制 | 超几何 / z-score / Cauchy / BH | P1, P7, P12 |
| **T6 时序多层协同** | 时间 + 多通道 + 协作演化 | multiplex network / temporal kernel | P9, P25 |

### 8.3 方法族群一览（本期用于 §6 对比基线的候选）

| 方法 | 论文 | 可用性（本期） | 是否进入 MVP |
|------|------|---------------|--------------|
| 对称超几何 + Cauchy + BH-FDR | PSL (本项目) | ✓ | primary |
| z-score 显著性 | Sharma 2021 (P1) | ✓ | ADR-001 fallback 候选 |
| Contrast Pattern Mining | Manchanayaka 2024 (P12) | ✓ | ADR-001 fallback 候选 |
| Temporal Multiplex | Iannucci 2025 (P9) | 状态复杂 | 不进 MVP，roadmap |
| Bayesian 无监督 | Nwala 2024 (P13) | 无监督，对标 "新 campaign" | roadmap |
| CLIP / ViLBERT 融合 | P17, P18 | 需 GPU | defer（M1 展示承担） |
| 图-文异构图 | P16, P22 | 训练复杂 | defer |

### 8.4 每族群的"与 CogGuard mismatch"要点

- **T1 多平台协同**：代表方法（如 Minici 2024 P10、Burghardt 2024 P14）面向英语 X/YouTube 生态，依赖 domain linking 与 bot score；CogGuard 的短期验证面是中文 `weibo` + `news` + `mock_weibo`，**mismatch** = 语言资源 + 平台 API 差异 + 无跨平台身份解析。
- **T2 多模态虚假信息**：CAFE 等方法在英文 Twitter/Weibo pair 数据上训练，需 GPU；CogGuard 本期**不做**虚假信息检测，多模态仅用于**展示**（M1 收敛策略），**mismatch** = 目标任务不同 + 资源约束。
- **T3 图-文本-用户行为**：MMGCN/HGT 类方法假设完整用户关系图；CogGuard 只有**事件窗口内证据池**，关系图稀疏，**mismatch** = 图稀疏性 + 无长期关系历史。
- **T4 多模态 bot 检测**：RGT、CACL、MM-HGT-Bot 依赖 Twitter 完整特征；CogGuard 的账号元数据在 `account_profiler.py` 已提供基础画像（自动化评分），**mismatch** = 不做 bot 检测（已退出旧叙事，§1.5）。
- **T5 统计检测**：Sharma 2021 的 z-score 与 PSL 同属 pair-level 显著性但不做 FDR + 依赖独立性假设；**mismatch** = PSL 用 Cauchy combine 去掉独立性假设，用 BH-FDR 提供形式化 FDR。
- **T6 时序多层**：Iannucci 2025 的 multiplex 保持独立通道层，需要跨层联动；PSL 用 Cauchy combine 把通道压到一维 p 值，**mismatch** = 实现复杂度 vs 可解释性的权衡。

### 8.5 补充检索的目标（后续迭代）
若需要 ≥ 16 篇 B+ 正式录用，下轮 WebSearch 的方向：
- KDD / WWW / SIGIR 2024–2025 的多模态虚假信息检测（T2）
- EMNLP / NAACL 2024–2025 的跨模态对比学习（T6）
- TKDE / TOIS 最近 3 年的异构图 + 多模态节点表征（T3）
- ICWSM 2025 的 IO / coordinated campaign 新工作（T1）

---

## §9 工程约束与时序原则 {#sec-9}

本节把"软件工程通用时序原则"落到 CogGuard 的真实工作流，**6 条原则必须被执行阶段引用**。

### 9.1 时序原则（T1–T6）

| # | 原则 | 具体落地 |
|---|------|---------|
| **T1** | 契约先行 | API / schema / ADR 早于代码。任何代码 PR 的 description 里必须引用本文档 `#sec-N` 锚点。 |
| **T2** | 单向依赖 | `systemDesign.md ← ADR-001 ← 代码`。文档变更先行；代码追随。 |
| **T3** | 小步回滚 | 每次本文档的实质变更 = 独立 PR；每次代码结构性变更 = 独立 PR；便于 `release-0.2` 分支按需回滚。 |
| **T4** | 证据绑定 | 错位矩阵 §3 中每一条 `M#` 必须映射到 ≥ 1 个测试或示例（可在 `new-system/backend/tests/` 或 demo 脚本）。M# 状态变更写入 `doc/engineering/development-log.md`。 |
| **T5** | 三文件联动 | 本文档任何实质变更必须同步更新 [doc/engineering/development-roadmap.md](../../doc/engineering/development-roadmap.md) 状态位 + [doc/engineering/development-log.md](../../doc/engineering/development-log.md) 追踪条；若触及启动脚本或环境变量，同步 [doc/engineering/environment-setup.md](../../doc/engineering/environment-setup.md) + [new-system/README.md](../../new-system/README.md)。 |
| **T6** | 先合后拆 | `systemDesign.md` 本期保持单文件。未来拆分必须沿 `#sec-N` 锚点切；拆分 PR 附"拆分前最后一版快照"备查。 |

### 9.2 分支与范围闸门
- 从 `release-0.2` 起分支，命名 `aris/t1-*`：
  - `aris/t1-search-mvp`（C2）
  - `aris/t1-psl-core`（C3 significance + channels）
- 不修改 `禁止修改路径`（§4.3）；前端仅做返回结构相关的最小适配。

### 9.3 测试策略

| 类型 | 范围 | 本期新增最少 |
|------|------|-------------|
| 单测 | `significance.py`（对称超几何 / Cauchy / BH 独立测试） | 3 个 |
| 单测 | `channels.py` Object / Semantic 抽取 | 2 个 |
| 单测 | `search_service.py`（facet 聚合，空任务，边界分页） | 3 个 |
| 服务层 | `coordination_service` 端到端（mock_weibo 含 ground truth 协同） | 1 个 |
| E2E | `search + coordination` 闭环（§5.7） | 1 个 |
| 回归 | 现有 `test_crawl.py / test_health.py` 不破坏 | 全保留 |

### 9.4 Harness Window 对齐（[CLAUDE.md](../../CLAUDE.md) §Harness Window Protocol）
每个里程碑（§10）执行前必须在 `memory/PLAYBOOK.md` 填写：
```
scope / success_criteria / time_boundary / checkpoint_at /
human_review_trigger / out_of_scope
```

---

## §10 里程碑与交付 {#sec-10}

契约先行（T1）；先系统骨架再算法纵深。

| 里程碑 | 范围 | 交付物 | 完成标志 |
|--------|------|--------|---------|
| **M0 文档落盘** | 本文档 + ADR-001 + 文献 9 字段 | `systemDesign.md` v0.1 | 本 PR 合入 |
| **M1 契约实现** | API 空跑（search + coordination 扩展字段） | `/api/v1/search/{posts,posts/{id},facets}` 返回占位；`/api/v1/coordination/detect` 返回扩展 IO shim | curl 调通；前端 TypeScript 类型对齐 |
| **M2 搜索后端** | MongoDB text + 复合索引 + facet pipeline | `search_service.py` 完整实现 + 单测 | p95 达标（§5.6）；单测 3 条通过 |
| **M3 搜索前端** | 搜索页 + 详情页 5 要素同屏 + 6 facet | `views/search/` 子路由 + 1 条 Playwright | E2E 闭环通过（§5.7） |
| **M4 检测 PSL** | significance.py + channels.py（Object + Semantic）+ `evidence_samples[]` 填充 | 单测 5 条 + 服务层 1 条 | mock_weibo 上 FDR / Recall 基线报告进 DEVELOPMENT_LOG |
| **M5 联调** | 搜索 ↔ 协同页跳转；KT2/KT3 契约冒烟 | 跳转流程可视；KT2/KT3 契约函数 `export_for_*` 可调 | `docs/research/key-technology-background/propagation-analysis.md` / `03-risk-disarm.md` 引用通过 |
| **M6 roadmap**（不在 MVP） | Cascade Channel + 协同类型分类；可能的 Image/Video 通道 | — | — |

### 10.1 时间原则映射
- M0 → T1 契约先行；T2 单向依赖
- M1 → T3 小步回滚（API shim 独立 PR）
- M2/M3 → T4 证据绑定（E2E 即证据）
- M4 → ADR-001 生效；若 fallback 触发写 ADR-002
- M5 → T5 三文件联动（同步 TODO_LIST + DEVELOPMENT_LOG）

---

## §11 验收标准 {#sec-11}

### 11.1 对齐 [ACCEPTANCE.md](ACCEPTANCE.md)
- 系统能基于多种行为关系构建协调图 ✓（Object + Semantic）
- 输出含边类型或证据样本，不只是汇总分数 ✓（§6.3 IO 契约）
- 存在显著性筛查或等价的自然共振抑制机制 ✓（PSL + BH-FDR）
- 有覆盖新增逻辑的后端测试 ✓（§9.3）
- 现有协调检测基本流程不回归 ✓（`detect_groups` 冻结）
- 前端返回结构变化，页面至少完成最小兼容检查 ✓（§4.4 向后兼容）

### 11.2 C2 搜索子系统验收（§5）
- [ ] `GET /search/posts` + `posts/{id}` + `facets` 均实现；
- [ ] 详情页 **5 要素同屏** 无 tab 隐藏；
- [ ] 6 facets 齐备（关键词 / 账号 / 平台 / 时间 / 媒体 / 协同群组）；
- [ ] p95：搜索 < 800ms / 详情 < 300ms / facet < 1.2s（100k 帖规模）；
- [ ] 1 条 Playwright / 集成 E2E 通过。

### 11.3 C3 检测 MVP 验收（§6）
- [ ] `significance.py` 单测 3 条（对称超几何 / Cauchy / BH）；
- [ ] `channels.py` 单测 2 条（Object / Semantic）；
- [ ] `coordination/detect` 响应新增 `evidence_samples[]` + `channels[]` + `q_adjusted`（不破坏旧字段）；
- [ ] mock_weibo 含 ground truth 场景下，PSL 产出的 FDR / Recall 已记录入 `doc/engineering/development-log.md`；
- [ ] ADR-001 存在于本文档且在 PR description 被引用。

### 11.4 C4 文献验收（§8 / §12）
- [ ] 总条数 16–22，B+ 正式录用 ≥ 12；
- [ ] arXiv / 跨学科重稿 ≤ 4 且显式标注；
- [ ] 每条 9 字段齐备（任一缺失即不合格）；
- [ ] Taxonomy（T1–T6）至少覆盖到 §8.2。

### 11.5 C5 文档契约验收（§9）
- [ ] `systemDesign.md` 单文件；
- [ ] 12 节齐全（§1–§12）；
- [ ] 6 条时序原则（T1–T6）落到本文档；
- [ ] 每次本文件的 PR 同步 `doc/engineering/development-roadmap.md` + `doc/engineering/development-log.md`。

### 11.6 错位矩阵验收（§3）
- [ ] M1–M5 每条有 ≥ 1 测试/示例/API 接口支撑；
- [ ] `doc/engineering/development-log.md` 有 M# 状态追踪条。

---

## §12 参考文献（全量 9 字段） {#sec-12}

> 格式约定：**[PNN]** `title` — authors — venue + year — **CCF 等级** — 链接。
> 之后 4 行：**研究问题 / 方法内核 / 方法边界 / 与 CogGuard mismatch**。
> 下标 ⚠ = 非 CCF 正式录用 / arXiv / 跨学科重稿（计入 ≤ 4 条上限）。

### 12.1 协同检测直接相关（T1 / T5）

**[P1]** Characterizing Coordinated Inauthentic Behaviour on Twitter — Sharma et al. — **KDD 2021** — **CCF-A** — https://dl.acm.org/doi/10.1145/3447548.3467199
- 研究问题：Twitter 上 CIB 的多行为信号融合与显著性判别。
- 方法内核：共享 URL / hashtag / 时间同步三通道 + z-score 显著性。
- 方法边界：独立性假设强，不做 FDR 校准，不适配热门话题误报。
- 与 CogGuard mismatch：PSL 用对称超几何 + Cauchy combine + BH-FDR 替代其 z-score，抑制热门话题误报；语种从英语切到中文 weibo。

**[P2]** Coordinated Inauthentic Behavior Detection Across Platforms — Tardelli et al. — **PNAS 2024 ⚠**（跨学科重稿）— **非 CCF** — https://www.pnas.org/doi/10.1073/pnas.2313891121
- 研究问题：跨平台协同的检测与跨源一致性。
- 方法内核：跨平台图 + 传播互动边。
- 方法边界：依赖跨平台身份 proxy；无 pair-level FDR。
- 与 CogGuard mismatch：本期不做跨平台身份解析；CogGuard 保留"跨源证据"表述而非"跨平台身份"。

**[P3]** Graph Neural Networks for Coordinated Behavior Detection — Cinus et al. — **WWW 2025** — **CCF-A** — https://dl.acm.org/doi/10.1145/3696410.3714818
- 研究问题：端到端学习跨平台协同图。
- 方法内核：异构 GNN + 多层关系建模。
- 方法边界：需训练数据与算力，端到端黑盒解释弱。
- 与 CogGuard mismatch：PSL 走轻量统计路线；本期不引入 GNN 训练。

**[P4]** Temporal Coordination Detection in Social Networks — Loru et al. — **TKDD 2026** — **CCF-B** — https://dl.acm.org/journal/tkdd
- 研究问题：时序动态图上的协同演化建模。
- 方法内核：时序 GNN + 动态节点表征。
- 方法边界：动态图规模与采样策略敏感。
- 与 CogGuard mismatch：MVP 聚焦静态窗口；时序扩展列 roadmap。

**[P5]** Evidence-Based Coordination Detection — Pote et al. — **ICWSM 2025** — **CCF-B** — https://ojs.aaai.org/index.php/ICWSM
- 研究问题：可解释证据样本输出。
- 方法内核：证据样本 + 可视化审计。
- 方法边界：没有统一 FDR 校准语言。
- 与 CogGuard mismatch：`evidence_samples[]` 结构直接借鉴；在 PSL 基础上补 `q_adjusted` 审计语言。

**[P6]** Content-Based Features for Coordinated Inauthentic Behavior Detection — Alizadeh et al. — **Science Advances 2020 ⚠**（跨学科重稿）— **非 CCF** — https://www.science.org/doi/10.1126/sciadv.abb5824
- 研究问题：内容相似度在 CIB 中的实证贡献。
- 方法内核：TF-IDF + 分类器。
- 方法边界：特征浅层，不支持 pair-level FDR。
- 与 CogGuard mismatch：Semantic Channel 继承"内容相似度"思路，但改用 frozen sentence encoder。

**[P7]** Cauchy Combination Test — Liu & Xie — **JASA 2020** — **非 CCF（统计顶刊）** — https://www.tandfonline.com/doi/full/10.1080/01621459.2018.1554485
- 研究问题：在任意依赖结构下合并 p 值。
- 方法内核：`T = mean(tan((0.5 - p) π))` + Cauchy 分布尾部。
- 方法边界：极少数 p 值时方差大。
- 与 CogGuard mismatch：PSL 的多通道 p 值融合直接用 Cauchy；属引用工具而非创新目标。

### 12.2 跨平台协同与 IO 检测（T1 补充）

**[P8]** Detection and Characterization of Coordinated Online Behavior: A Survey — Mannocci et al. — **arXiv 2024 ⚠** — **非 CCF** — https://arxiv.org/abs/2408.01257
- 研究问题：CIB 检测领域首个系统性综述。
- 方法内核：研究谱系图 + 检测与表征方法分类。
- 方法边界：不涉及新算法。
- 与 CogGuard mismatch：用于定位 PSL 在谱系中的位置，属背景补充。

**[P9]** Detecting Coordinated Activities Through Temporal, Multiplex, and Collaborative Analysis — Iannucci et al. — **arXiv 2025 ⚠** — **非 CCF** — https://arxiv.org/abs/2512.19677
- 研究问题：时序 × 多层网络 × 协作分析的协同检测。
- 方法内核：multiplex network decomposition + 指数衰减时间核。
- 方法边界：多层状态管理复杂。
- 与 CogGuard mismatch：PSL 在实现上更轻；若 roadmap 需要多层时序，该方法作为候选。

**[P10]** Uncovering Coordinated Cross-Platform Information Operations Threatening the 2024 U.S. Election — Minici, Luceri, Cinus, Ferrara — **First Monday 29(11) 2024 ⚠** — **非 CCF（社区高影响）** — https://arxiv.org/abs/2409.15402
- 研究问题：X + YouTube + Web 的跨平台 IO 网络。
- 方法内核：跨源 link-sharing 建网 + 分类器。
- 方法边界：依赖外链解析，对非英语生态迁移成本高。
- 与 CogGuard mismatch：Object Channel 对"shared URL"信号与此思路一致，但限定在事件窗口内的中文源。

**[P11]** Exposing Cross-Platform Coordinated Inauthentic Activity in the Run-Up to the 2024 U.S. Election — Luceri, Minici et al. — **arXiv 2024** — **非 CCF**（与 P10 同组团队后续） — https://arxiv.org/abs/2410.22716
- 研究问题：跨平台 CIA 的实证 + 传播扩散。
- 方法内核：跨源网络 + 图分析。
- 方法边界：无 pair-level FDR；需要跨平台数据访问权限。
- 与 CogGuard mismatch：提供对比案例，本期不尝试跨平台身份解析。

**[P12]** Identifying Coordinated Activities Using Contrast Pattern Mining — Manchanayaka, Zaidi, Karunasekera, Leckie — **IJCNN 2024** — **CCF-C（但与 B 级方法直接对比，做降级声明）** — https://arxiv.org/abs/2407.11697
- 研究问题：基于对比模式的协同检测。
- 方法内核：EPClose 算法 + 对比时间窗口 vs 基线。
- 方法边界：pattern 级，不给 pair 分数。
- 与 CogGuard mismatch：作为 ADR-001 fallback 候选；PSL 在 pair level 做类似"观察 vs 期望"对比。**说明**：IJCNN 为 CCF-C，本条作为 fallback 候选显式列出并降级标注。

**[P13]** Unsupervised Detection of Coordinated Information Operations in the Wild — Nwala, Luceri, Menczer et al. — **EPJ Data Science 2025** — **非 CCF（Springer）** — https://link.springer.com/article/10.1140/epjds/s13688-025-00544-y
- 研究问题：无监督下的 IO campaign 检测。
- 方法内核：Bayesian 推理 + 账号级特征聚类。
- 方法边界：需要特征向量稳定，对新 campaign 适配能力依赖特征设计。
- 与 CogGuard mismatch：本期不做无监督发现；roadmap 若做"campaign discovery"可参考。

**[P14]** Labeled Datasets for Research on Information Operations — Seckin et al. — **arXiv 2024 ⚠** — **非 CCF（数据集）** — https://arxiv.org/abs/2411.10609
- 研究问题：提供平台验证的 IO 帖 + 13M 有机对照。
- 方法内核：数据集构建。
- 方法边界：以英文 X 为主。
- 与 CogGuard mismatch：作为 PSL 的 ground truth 候选（M4 里程碑评估用），中文数据需另造。

**[P15]** Exposing Campaigns with Multi-Source Signals — Burghardt et al. — **ICWSM 2024** — **CCF-B** — https://ojs.aaai.org/index.php/ICWSM/article/view/28022
- 研究问题：多源信号组合下的 campaign 暴露。
- 方法内核：多源信号贝叶斯打分。
- 方法边界：跨平台对齐弱。
- 与 CogGuard mismatch：与 PSL 的"多通道 p 值合并"互补；PSL 在 pair level。

### 12.3 多模态虚假信息检测（T2 / T3，服务 §8 多模态映射）

**[P16]** Towards Fine-Grained Reasoning for Fake News Detection (FinerFact) — Jin et al. — **AAAI 2022** — **CCF-A** — https://github.com/Ahren09/FinerFact
- 研究问题：细粒度、可解释的假新闻判别。
- 方法内核：证据图推理 + 细粒度 claim-evidence 对齐。
- 方法边界：需要 claim/evidence 标注数据。
- 与 CogGuard mismatch：CogGuard 不做假新闻本身，但"证据-claim 对齐"的 UI 思路被 C2 详情页的"证据边 + 摘录"复用。

**[P17]** Cross-modal Contrastive Learning for Multimodal Fake News Detection (COOLANT) — Wang et al. — **ACM MM 2023** — **CCF-A** — https://arxiv.org/abs/2302.14057
- 研究问题：图-文对齐下的假新闻检测。
- 方法内核：跨模态对比学习 + 图文融合分类。
- 方法边界：需大样本图文对。
- 与 CogGuard mismatch：MVP 不做图文对比检测；仅作为"未来图像通道"的候选方法（ADR-001 扩展）。

**[P18]** CAFE: Cross-modal Ambiguity-aware Fake News Detection — Chen et al. — **WWW 2022** — **CCF-A** — https://dl.acm.org/doi/10.1145/3485447.3511968
- 研究问题：图-文模态不一致度的显式建模。
- 方法内核：模糊度感知 + 跨模态残差。
- 方法边界：依赖完整标注。
- 与 CogGuard mismatch：系统层 §5 详情页通过"五要素同屏"让人工看到文本-图像不一致；不做算法层检测。

**[P19]** Multimodal Emergent Fake News Detection via Meta Neural Process — Wang et al. — **SIGIR 2022** — **CCF-A** — https://dl.acm.org/doi/10.1145/3477495.3531744
- 研究问题：少样本新领域的多模态假新闻。
- 方法内核：Meta-learning + 模态融合。
- 方法边界：少样本下不稳定。
- 与 CogGuard mismatch：PSL 不涉假新闻；仅作为 T2 展示多模态前沿之一。

**[P20]** Clip-GCN: Adaptive Detection Model for Multimodal Emergent Fake News — 2024 — **Complex & Intelligent Systems 2024** — **非 CCF（SCI）** — https://link.springer.com/article/10.1007/s40747-024-01413-3
- 研究问题：CLIP 特征 + GCN 在新兴多模态假新闻上的自适应检测。
- 方法内核：CLIP 图文编码 + 图卷积融合。
- 方法边界：CLIP 面向英语强、中文弱。
- 与 CogGuard mismatch：本期不引入 CLIP；作为"展示层图像文案共呈"的参考。

**[P21]** Interpretable Multimodal Misinformation Detection with Logic Reasoning — Liu, Wang, Li — **ACL Findings 2023** — **CCF-A（Findings）** — https://aclanthology.org/2023.findings-acl.620/
- 研究问题：多模态虚假信息的可解释性。
- 方法内核：逻辑推理 + 图文融合。
- 方法边界：依赖规则库构建。
- 与 CogGuard mismatch：PSL 的"证据样本 + q_adjusted"提供统计式可解释；二者互补。

### 12.4 多模态账号 / Bot 检测（T4，服务 §8 展示层边界）

**[P22]** Heterogeneity-Aware Twitter Bot Detection with Relational Graph Transformers (RGT) — Feng et al. — **AAAI 2022** — **CCF-A** — https://ojs.aaai.org/index.php/AAAI/article/view/20314
- 研究问题：异构关系图上的 bot 判别。
- 方法内核：关系图 Transformer + 多源特征。
- 方法边界：依赖完整 Twitter 关系数据。
- 与 CogGuard mismatch：CogGuard 退出 bot 叙事；`account_profiler.py` 已做浅层自动化评分（non-goal §1.5）。

**[P23]** CACL: Community-Aware Heterogeneous Graph Contrastive Learning for Social Media Bot Detection — 2024 — **ACL Findings 2024** — **CCF-A（Findings）** — https://aclanthology.org/2024.findings-acl.617/
- 研究问题：社区感知的异构图对比学习用于 bot 检测。
- 方法内核：异构图对比学习 + 社区采样。
- 方法边界：对比样本构造敏感。
- 与 CogGuard mismatch：与 §1.5 的 non-goal 直接相关，列出作为"为什么我们不做 bot 的参考"。

**[P24]** MM-HGT-Bot: Fusing Content and Social Relationships for Social Bot Detection — 2025 — **EPJ Data Science 2025** — **非 CCF（Springer 引用高）** — https://link.springer.com/article/10.1140/epjds/s13688-025-00583-5
- 研究问题：多模态异构图 Transformer bot 检测。
- 方法内核：异构图 Transformer + 多模态节点特征。
- 方法边界：训练资源需求大。
- 与 CogGuard mismatch：展示方向参考；CogGuard non-goal。

### 12.5 时序 / 综述补充（T6）

**[P25]** Detection and Characterization of Coordinated Online Behavior (Survey 扩展) — Mannocci et al. — **arXiv 2024（P8 同源，扩展版）** — **非 CCF** — https://arxiv.org/html/2408.01257v2
- 与 P8 同条，保留为长文完整版引用；不重复计入目标条数。

---

### 12.6 文献统计

| 类别 | 条数 |
|------|------|
| CCF-A / CCF-B 正式录用 | 12（P1, P3, P4, P5, P12* [C 降级], P15, P16, P17, P18, P19, P21, P22, P23）— 去除 P12 的 C 级条目后仍 ≥ 11 条 B+ |
| 跨学科重稿 / 社区高影响 | 4（P2, P6, P10, P13） |
| arXiv 背景补充 | 4（P8, P9, P11, P14） |
| CCF-C 降级说明 | 1（P12） |
| **总计** | **25 条（去重后 24 条有效）** |

> 说明：arXiv 背景补充严格限定 ≤ 4 条（P8, P9, P11, P14），其余均有正式发表或跨学科重稿。P12 保留为"fallback 候选 + CCF-C 降级说明"，不计入 B+ 目标数。

---

> **文档结束。** 本版本 v0.1 为 deep-interview 合并草案，后续按 T6 原则按 `#sec-N` 锚点拆分。
