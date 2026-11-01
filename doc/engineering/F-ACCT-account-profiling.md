# F-ACCT（深度账号画像）代码开发需求文档

> **Historical / Non-normative**：这是早期功能提案，保留用于追溯。当前账户能力以产品路由、`system-governance.md` 和 `UBIQUITOUS_LANGUAGE.md` 为准；本文不得作为产品 runtime 输入。

> **功能类型**：横向支撑功能（supporting function），不是第 4 个关键技术
> **主要技术**：预训练 Bot 检测模型（Botometer / RoBERTa Twibot-22）+ 账号级 stance 聚合 + 规则化 KOL 识别
> **文档类型**：功能级代码开发需求（research / engineering 拆分）
> **最后更新**：2026-05-20
> **配套文档**：[research-engineering-split.md](./research-engineering-split.md)（系统总览）、[../../aris/tech-02-propagation/REQUIREMENTS.md](../../aris/tech-02-propagation/REQUIREMENTS.md)（与 F-PROP WP4 的分层契约）

---

## 一、功能定位

### 1.1 在 CogGuard 中的角色

F-ACCT 是 CogGuard 主链路的**横向证据层**，被三大核心功能（F-COORD / F-PROP / F-RISK）**共同消费**，自身不直接对外做风险判定。

```
                ┌──────────────────────────────┐
                │   F-ACCT 深度账号画像（本文）  │
                │  ┌────────────────────────┐  │
                │  │ bot detection          │  │
                │  │ stance aggregation     │  │
                │  │ KOL identification     │  │
                │  │ activity profiling     │  │
                │  │ work-rest pattern      │  │
                │  └────────────────────────┘  │
                └────┬────────┬────────┬───────┘
                     │        │        │
                     ▼        ▼        ▼
                F-COORD   F-PROP    F-RISK
                (协同检测) (传播监控) (报告研判)
```

**关键认识**：F-ACCT **不是第 4 个关键技术**，原因：

| 判定维度 | F-ACCT 属性 |
|---|---|
| 算法创新性 | ⚠️ 低 — bot detection / stance 聚合都是工业界成熟方法 |
| 是否独立可演示 | ❌ 否 — 单个账号的 bot_score 没有竞赛叙事价值 |
| 是否被多功能消费 | ✅ 是 — Coordination Discover / Detect 用 bot_prob 过滤、Propagation Analysis 用 stance 分布、Risk Review 用 KOL 标识 |
| 与上游关键技术关系 | 平行 + 支撑（非依赖） |
| 论文 ROI | 低 — 单写不够发表，作为 ablation 子项更合适 |

**定位结论**：90% engineering + 10% research 边界（仅 stance 聚合的统计建模 + bot detection 模型选择需调参）。

### 1.2 输入与输出

**输入**：

- MongoDB `raw_posts` / `raw_comments`（账号的全部发文与互动）
- 单个用户主页采集结果（主页 URL、昵称、简介、粉丝/关注/获赞、认证、IP 属地、主页内容流）
- 账号元数据（粉丝数 / 认证类型 / 注册时间 / 头像 URL / IP 归属）
- F-PROP WP4 的**帖级 stance 输出**（用于账号级聚合）

**输出**：

```python
account_profile = {
    "account_id": str,
    "platform": str,

    # 自动化检测（新增）
    "bot": {
        "score": float,            # 0-1，越高越像 bot
        "model": str,              # "botometer-v4" | "twibot22-roberta" | "rule-based"
        "confidence": float,
        "explanation": [str],      # 触发的关键特征
    },

    # 立场聚合（新增，消费 F-PROP WP4）
    "stance": {
        "distribution": {"support": float, "against": float, "neutral": float,
                         "sarcasm": float, "questioning": float, "ambiguous": float},
        "extremity_index": float,  # 极化程度 0-1
        "consistency": float,      # 立场一致性（多帖之间）
        "sample_size": int,        # 参与聚合的帖数
    },

    # KOL 识别（新增）
    "kol": {
        "is_kol": bool,
        "tier": str,               # "head" | "mid" | "tail" | "none"
        "influence_score": float,  # 0-100
        "reasons": [str],          # 触发标签
    },

    # 行为画像（旧 account_profiler.py 保留）
    "activity": {
        "post_frequency": float,
        "interval_cv": float,      # 发文间隔变异系数
        "work_rest_pattern": [float],   # 24h 直方图
        "interaction_breakdown": {"like": int, "share": int, "comment": int},
        "content_diversity": float,
    },

    # 旧 automation_score（与 bot.score 共存，便于回归）
    "automation_score": float,     # 0-100
}
```

### 1.3 对标系统

| 对标 | 类型 | 与 F-ACCT 关系 |
|---|---|---|
| Botometer X (Indiana U) | 学术 + 公开 API | bot detection 的工业基线 |
| Twibot-22 (RoBERTa) | 学术开源模型 | bot detection 的预训练模型选项 |
| Pegabot / BotSentinel | 工业界 | KOL 识别的产品参考 |
| 微博 / 抖音原生认证 | 平台原生 | KOL 等级的事实参照 |

---

## 二、子功能拆解

### 2.1 子功能清单（5 个）

| # | 子功能 | 做什么 | 输入 | 输出 | 落点文件 | 状态 |
|---|---|---|---|---|---|---|
| F-ACCT-1 | Bot detection | 区分真人 / 机器人 / 半自动 | 账号元数据 + 历史发文 | `bot.score / model / explanation` | `core/account/bot_detector.py`（新增） | ❌ 未开始 |
| F-ACCT-2 | 账号级 stance 聚合 | 聚合多帖立场为账号级分布 | F-PROP WP4 帖级 stance | `stance.distribution / extremity / consistency` | `core/account/stance_aggregator.py`（新增） | ❌ 依赖 Propagation Analysis WP4 |
| F-ACCT-3 | KOL 识别 | 头部 / 中部 / 尾部分级 | 粉丝数 + 认证 + 互动量 + F-PROP 影响力 | `kol.tier / influence_score / reasons` | `core/account/kol_identifier.py`（新增） | ❌ 未开始 |
| F-ACCT-4 | 行为画像 | 发文频率 / 作息 / 内容多样性 | 账号历史发文 | `activity.*` | `core/account_profiler.py` (185)（已有，需迁入 `core/account/`） | ✅ MVP |
| F-ACCT-5 | 自动化倾向评分（旧） | 多维综合 0-100 评分 | F-ACCT-4 输出 | `automation_score` | `core/account_profiler.py`（已有） | ✅ MVP |
| F-ACCT-6 | 单用户主页采集与内容巡检 | 按主页链接/用户 ID 抓取主页元数据和全部内容，并对内容做风险/立场/模板化检测 | MediaCrawler 用户主页能力 + raw_posts/raw_comments | `homepage / posts / content_checks` | `services/account_service.py` + crawler 扩展 | ❌ 未开始 |

### 2.2 目录重组（建议）

当前 `core/account_profiler.py` 是单文件。新增 3 个子功能后，建议提升为包：

```
new-system/backend/app/core/account/                  ← 新建包
├── __init__.py                                       ← 重新导出旧 API
├── activity_profiler.py    ← 迁自 core/account_profiler.py（185 行）
├── bot_detector.py         ← 新增（F-ACCT-1，~250 行）
├── stance_aggregator.py    ← 新增（F-ACCT-2，~150 行）
├── kol_identifier.py       ← 新增（F-ACCT-3，~200 行）
└── config/
    ├── bot_features.yaml   ← 规则模型特征清单（fallback）
    └── kol_thresholds.yaml ← KOL 分级阈值
```

**向后兼容**：`core/account_profiler.py` 保留为 thin shim：

```python
# core/account_profiler.py（保留，shim）
from .account.activity_profiler import *  # 原 API 全部 re-export
```

---

## 三、主要技术（research / engineering 边界）

### 3.1 F-ACCT-1 Bot Detection：混合架构（用户选定预训练路线）

**架构**（双层）：

```
账号 → [Layer 1: 规则统计特征]
       发文间隔CV / 作息规律性 / 跨平台重贴率 / 头像缺失 / 名字模式 / ...
       输出 rule_score ∈ [0, 1]
           │
           ▼
       [Layer 2: 预训练模型推断]
       Botometer X API（首选，需外网）
         或 twibot22-roberta（本地 transformers，CPU 友好）
       输出 ml_score ∈ [0, 1]
           │
           ▼
       [Fusion]
       final_score = 0.4 · rule_score + 0.6 · ml_score
           │
           ▼
       {score, model="botometer-v4" | "twibot22-roberta" | "rule-based",
        confidence, explanation: top-5 features}
```

**降级链**：

1. **首选**：Botometer X API（需 `RAPIDAPI_KEY` 环境变量）
2. **次选**：本地 `twibot22-roberta` 模型推断（HuggingFace transformers）
3. **降级**：纯规则统计（与现有 `automation_score` 同源）

**research 部分**：

- 预训练模型选择（Botometer v4 vs twibot22-roberta vs Cresci-2017）
- 中文社交媒体上的 zero-shot 准确率（这些模型主要在英文 Twitter 训练）
- 规则统计特征清单（10-15 个）+ 各特征权重
- Fusion 权重（0.4 / 0.6 是否合理）

**engineering 部分**：

- API 客户端 + 重试 + 限流 + 缓存（Redis）
- HuggingFace 模型加载（lazy + LRU cache）
- 规则统计实现（pandas 向量化）
- 配置文件 `bot_features.yaml` 加载
- 单元测试 + mock fallback

### 3.2 F-ACCT-2 账号级 Stance 聚合（与 Propagation Analysis WP4 分层契约）

**职责边界**（用户选定的"拆层"方案）：

| 层级 | 谁负责 | 输入 | 输出 |
|---|---|---|---|
| **帖级 stance** | F-PROP WP4 `stance_detector.py` | 单帖文本 | `{stance: support/against/.../ambiguous, confidence}` |
| **账号级 stance 聚合** | **F-ACCT-2 `stance_aggregator.py`**（本文） | 账号所有帖的帖级 stance 列表 | 账号级 6 维分布 + 极化指数 + 一致性 |

**聚合算法**：

```python
def aggregate(post_stances: list[PostStance]) -> AccountStance:
    """
    post_stances: [{stance: 'support', confidence: 0.82}, ...]
    """
    # 加权频率（用置信度加权）
    distribution = weighted_frequency(post_stances)

    # 极化指数：support 与 against 的较大值
    extremity = max(distribution["support"], distribution["against"])

    # 一致性：1 - normalized entropy
    consistency = 1.0 - shannon_entropy(distribution) / log(6)

    return {
        "distribution": distribution,
        "extremity_index": extremity,
        "consistency": consistency,
        "sample_size": len(post_stances),
    }
```

**research 部分**：

- 加权频率 vs 简单频率（是否用置信度加权）
- 极化指数定义（max vs L2 距离 from uniform vs Wasserstein from uniform）
- 一致性指标选择（entropy / variance / Gini）
- 小样本（< 5 帖）的处理

**engineering 部分**：

- 调用 F-PROP API 获取帖级 stance
- 加权频率 / 熵 / Wasserstein 等公式实现
- 缓存（账号 + 时间窗 → 聚合结果）
- 与 F-PROP WP4 的接口对齐

### 3.3 F-ACCT-3 KOL 识别（纯 engineering）

**规则化**（无 research）：

```yaml
# config/kol_thresholds.yaml
head:
  followers_min: 1000000
  verified_required: true
  influence_score_min: 80
mid:
  followers_min: 100000
  followers_max: 999999
  influence_score_min: 50
tail:
  followers_min: 10000
  followers_max: 99999
  influence_score_min: 30
none:
  # fallback
```

**influence_score 公式**：

```
influence_score = 0.3 · normalized(followers)
                + 0.2 · normalized(avg_likes_per_post)
                + 0.2 · verified_factor    # 蓝V/黄V/媒体认证
                + 0.2 · post_frequency_factor
                + 0.1 · network_centrality  # 由 F-COORD 提供
```

**research 部分**：无（规则全部可配置）
**engineering 部分**：全部

### 3.4 F-ACCT-4 / F-ACCT-5 已有，迁入新包

已实现于 `core/account_profiler.py`（185 行），本期仅做**目录迁移 + 包 import 路径调整**，无功能改动。

### 3.5 F-ACCT-6 单用户主页采集与内容巡检

**职责边界**：本子功能聚焦"按主页链接/用户 ID 抓取 + 内容检测落库"，不重复实现爬虫——**复用 MediaCrawler 已有的 creator/profile 模式**。

**架构**（三段流水线）：

```
请求（profile_url 或 platform+account_id）
  │
  ├──→ [Stage 1: 主页采集] homepage_collector.py
  │     调用 MediaCrawler creator 模式 → 主页元数据 + 主页内容流（全量发文/视频）
  │     落库：raw_posts（已有）+ account_homepage（新增）
  │
  ├──→ [Stage 2: 内容巡检（content_checks）] content_checker.py
  │     对该用户的全部发文调用：
  │       • 风险检测   ← 复用 F-RISK harm_assessor 或 Propagation Analysis WP5（按帖级聚合）
  │       • 立场检测   ← 复用 F-PROP WP4 stance_detector（按帖级）+ F-ACCT-2 账号级聚合
  │       • 模板化检测 ← 复用 F-COORD channels.py 的语义重复 / hashtag 模板检测
  │     输出 per-post checks + 账号级聚合指标
  │
  └──→ [Stage 3: 详情页响应组装] account_service.py
        homepage 元数据 + posts[] + per-post checks[] + 账号级聚合
```

**关键产物 schema**：

```python
homepage_response = {
    "account_id": str, "platform": str,
    "homepage": {
        "profile_url": str, "nickname": str, "bio": str,
        "followers": int, "following": int, "likes_total": int,
        "verified": bool, "verified_type": str,
        "ip_location": str, "registered_at": str,
        "avatar_url": str,
        "collected_at": str,
    },
    "posts": [   # 该账号全部发文（按时间倒序）
        {"post_id": ..., "created_at": ..., "content": ..., "media_urls": [...],
         "engagement": {"like": ..., "share": ..., "comment": ...}}
    ],
    "content_checks": [  # 与 posts 一一对应
        {
            "post_id": ...,
            "harm": {"score": float, "dimensions": {...}},   # 复用 Propagation Analysis WP5
            "stance": {"label": str, "confidence": float},   # 复用 Propagation Analysis WP4
            "template": {"is_template": bool, "template_id": str | None,
                         "duplicate_count": int}             # 复用 F-COORD 通道
        }
    ],
    "aggregated": {
        "harm_score_avg": float, "harm_score_max": float,
        "stance_distribution": {...},                         # F-ACCT-2 账号级
        "template_post_ratio": float,
    }
}
```

**降级策略**：

1. **首选**：MediaCrawler creator 模式（weibo / douyin / xhs，已支持）
2. **次选**：当平台不支持 creator 模式（如新闻类）时，退化为搜索式采集（MediaCrawler 的 keyword 模式 + author filter）
3. **最低降级**：仅返回 MongoDB 已有的 raw_posts（不触发新爬虫），加注 `data_freshness="cached_only"`

**research 部分**：无（爬虫复用 + 检测复用，不引入新算法）

**engineering 部分**：

- MediaCrawler creator 模式封装 + 失败重试 + 频率控制（避免账号风控）
- 内容巡检的并发批处理（一个账号可能有数百条发文）
- 模板化检测：F-COORD `channels.py` 的语义/hashtag 模板抽取需要 batch 单账号模式（不同于群体协同模式）
- account_homepage 表 / `services.collect_homepage()` 编排
- 前端账户详情页（主页元数据 + 内容流 + 巡检结果三栏）

**与现有 crawler 模块的关系**：

- 不在 `core/crawler/` 下新增爬虫，而是在 `core/account/homepage_collector.py` 中**调用** `core/crawler/social.py` 的现有子进程入口（带 `mode=creator` 参数）
- 若 `core/crawler/social.py` 当前不支持 `mode=creator`，需在 `social.py` 中扩展一个参数（属于 crawler 模块的 engineering 工作，归入 F-ACCT-6 范围）

---

## 四、API 设计

### 4.1 新增端点

```http
GET  /api/v1/accounts/profile/{account_id}        # 获取完整画像
POST /api/v1/accounts/batch-profile                # 批量画像
GET  /api/v1/accounts/{account_id}/bot              # 仅 bot 子项
GET  /api/v1/accounts/{account_id}/stance           # 仅 stance 聚合
GET  /api/v1/accounts/{account_id}/kol              # 仅 KOL 子项
POST /api/v1/accounts/homepage/collect              # 采集单个用户主页内容
GET  /api/v1/accounts/{account_id}/homepage          # 查看主页元数据与主页内容流
GET  /api/v1/accounts/{account_id}/contents          # 查看该用户全部发文及内容检测结果
```

### 4.2 服务层

```
new-system/backend/app/services/account_service.py（已有，扩到 ~150 行）
  ├─ get_profile(account_id) → 调用 4 个子模块聚合
  ├─ get_bot(account_id) → bot_detector.detect()
  ├─ get_stance(account_id, time_range) → 拉 F-PROP WP4 + stance_aggregator
  ├─ get_kol(account_id) → kol_identifier.identify()
  ├─ collect_homepage(profile_url | account_id, platform) → 调用 MediaCrawler 用户主页能力
  └─ get_account_contents(account_id, platform, event_id) → 返回全部发文与内容检测结果
```

### 4.3 数据库持久化

新增 MySQL 表（待 alembic 迁移）：

```sql
CREATE TABLE account_profile_cache (
    id INT PRIMARY KEY AUTO_INCREMENT,
    account_id VARCHAR(64) NOT NULL,
    platform VARCHAR(32) NOT NULL,
    profile_json JSON,
    computed_at DATETIME,
    expires_at DATETIME,
    INDEX (account_id, platform)
);

-- F-ACCT-6 主页元数据（与发文流分离，发文流仍写 raw_posts）
CREATE TABLE account_homepage (
    id INT PRIMARY KEY AUTO_INCREMENT,
    account_id VARCHAR(64) NOT NULL,
    platform VARCHAR(32) NOT NULL,
    profile_url VARCHAR(512),
    nickname VARCHAR(128),
    bio TEXT,
    followers INT, following INT, likes_total BIGINT,
    verified BOOLEAN, verified_type VARCHAR(32),
    ip_location VARCHAR(64),
    registered_at DATETIME,
    avatar_url VARCHAR(512),
    collected_at DATETIME,
    UNIQUE KEY (platform, account_id)
);
```

**缓存策略**：

- bot.score：7 天过期（账号特征慢变化）
- stance：6 小时过期（与事件窗口对齐）
- kol：30 天过期
- activity：1 天过期

---

## 五、现有代码资产 vs 待新增

### 5.1 已有

| 文件 | 行数 | 状态 | 本期处理 |
|---|---|---|---|
| `core/account_profiler.py` | 185 | ✅ MVP | 迁入 `core/account/activity_profiler.py`，保留 shim |
| `services/account_service.py` | 43 | ⚠️ 雏形 | 扩到 ~150 行 |
| `api/v1/accounts.py` | 30 | ⚠️ 雏形 | 新增 4 个端点 |
| `frontend/src/views/accounts/index.vue` | — | ✅ MVP（评分 + 排序） | 补 bot / stance / KOL 三段展示 |

### 5.2 待新增

| 文件 | 工作量 | 标签 |
|---|---|---|
| `core/account/__init__.py` | 15 min | engineering |
| `core/account/bot_detector.py` | 5-7 h | research-边界（模型选 + 调参） |
| `core/account/stance_aggregator.py` | 2-3 h | research-边界（聚合公式）+ engineering（实现） |
| `core/account/kol_identifier.py` | 2-3 h | engineering（纯规则） |
| `core/account/homepage_collector.py` | 4-5 h | engineering（封装 MediaCrawler creator 模式 + 重试 + 降级） |
| `core/account/content_checker.py` | 3-4 h | engineering（编排 Propagation Analysis WP4/WP5 + F-COORD 模板检测的批处理） |
| `core/account/config/bot_features.yaml` | 1-2 h（含特征论证） | engineering |
| `core/account/config/kol_thresholds.yaml` | 30 min | engineering |
| `core/crawler/social.py` 扩展 `mode=creator` 参数 | 2-3 h | engineering（依赖 MediaCrawler creator 子命令封装） |
| `models/account_homepage.py` | 30 min | engineering |
| `alembic/versions/xxx_add_account_profile_cache.py` | 30 min | engineering |
| `alembic/versions/xxx_add_account_homepage.py` | 30 min | engineering |
| `tests/test_account_profile.py` | 3-4 h | engineering |
| `tests/test_homepage_collector.py` | 2 h | engineering |
| `frontend/views/accounts/components/BotPanel.vue` | 2 h | engineering |
| `frontend/views/accounts/components/StancePanel.vue` | 2 h | engineering |
| `frontend/views/accounts/components/KOLPanel.vue` | 1.5 h | engineering |
| `frontend/views/accounts/detail/index.vue` | 6-8 h | engineering（账户详情页：主页 + 内容流 + 巡检三栏） |

### 5.3 配置 / 依赖

- `pyproject.toml`：补 `transformers`、`torch`（CPU 版）依赖（如选 twibot22-roberta 本地路线）
- `pyproject.toml`：补 `httpx` 调用 Botometer API（已有）
- `.env.example`：补 `RAPIDAPI_KEY`、`BOT_DETECTOR_PROVIDER`（`botometer` / `twibot22` / `rule`）、`BOT_DETECTOR_MOCK`

---

## 六、research vs engineering 拆分边界（F-ACCT 视角）

### 6.1 research 任务（本地实验，少量）

| # | 任务 | 阻塞 / 数据来源 | 验证方式 |
|---|---|---|---|
| R1 | Bot detection 预训练模型选择 | 中文社交媒体 zero-shot 准确率未知 | 在 100 条人工标注微博账号上对比 Botometer / twibot22-roberta / 规则三种 |
| R2 | Fusion 权重（规则 vs ML） | 默认 0.4 / 0.6 未验证 | 网格搜索 + 标注集 F1 |
| R3 | 规则特征清单 | 10-15 个特征未定 | 与 `automation_score` 既有特征对比 + 文献综述 |
| R4 | Stance 聚合方法 | 加权 vs 简单频率 / 极化定义 | 在标注账号上人工评估 6 维分布一致性 |
| R5 | KOL 阈值校准 | 默认阈值（100w/10w/1w）需平台特异化 | 按平台（weibo/douyin/xhs）各自校准 |

### 6.2 engineering 任务（Claude Code）

| 优先级 | # | 任务 | 工作量 |
|---|---|---|---|
| P0 | E1 | 目录迁移：`core/account_profiler.py` → `core/account/activity_profiler.py` + shim | 1 h |
| P0 | E2 | 补 `pyproject.toml` 依赖（transformers / torch CPU）+ `.env` 环境变量 | 30 min |
| P0 | E3 | alembic 迁移 `account_profile_cache` 表 | 30 min |
| P1 | E4 | `bot_detector.py` 双层实现 + 3 路降级 + mock | 5-7 h |
| P1 | E5 | `kol_identifier.py` 规则化 + 配置加载 | 2-3 h |
| P1 | E6 | `account_service.py` 扩展 4 个新方法 | 2 h |
| P1 | E7 | `api/v1/accounts.py` 新增 4 个端点 | 2 h |
| P1 | E8 | 前端 3 个 Panel 组件 + 路由 | 5-6 h |
| P1 | E11 | F-ACCT-6 主页采集：`homepage_collector.py` + `core/crawler/social.py` 扩展 `mode=creator` | 6-8 h |
| P1 | E12 | F-ACCT-6 内容巡检：`content_checker.py` 编排 Propagation Analysis WP4/WP5 + 模板检测批处理 | 3-4 h |
| P1 | E13 | F-ACCT-6 alembic 迁移 `account_homepage` 表 + ORM 模型 | 1 h |
| P1 | E14 | F-ACCT-6 API 3 端点：`/homepage/collect` / `/homepage` / `/contents` | 2 h |
| P1 | E15 | F-ACCT-6 前端账户详情页（主页 + 内容流 + 巡检三栏） | 6-8 h |
| P2 | E9 | `stance_aggregator.py`（依赖 F-PROP WP4 完成） | 2-3 h |
| P2 | E10 | 缓存层（Redis）+ TTL 策略 | 2 h |

**关键依赖**：

- E9 阻塞于 **F-PROP WP4 stance_detector.py**（Propagation Analysis 未启动）
- E4 阻塞于 **R1 模型选择决策**（建议先用规则路径跑通 engineering，模型路径作为 R1 完成后切换）
- E11 阻塞于 **MediaCrawler creator 子命令的可用性确认**（已知 weibo / douyin / xhs 支持，需在 social.py 接入）
- E12 阻塞于 **Propagation Analysis WP4 / WP5 / F-COORD 通道模板检测**——若上游未完成，content_checker 启用 mock fallback（仅给规则化结果）

### 6.3 边界 case 处理

| Case | 归属 | 备注 |
|---|---|---|
| Bot 规则特征清单 | research（先定）→ engineering（实现） | 先在 `bot_features.yaml` 中以默认值起步 |
| Bot 模型选择 | research（R1） | engineering 实现按"3 路降级"框架先行，模型路径可在 R1 完成后接 |
| Stance 聚合公式 | research（R4） | engineering 用加权频率默认起步 |

---

## 七、关键设计决策与开放问题

### 7.1 关键决策

1. **F-ACCT 是支撑功能而非第 4 条关键技术线**
   - 理由：算法创新性低，无独立竞赛叙事，被多功能消费
   - 影响：文档放 `doc/engineering/` 而非新建 `aris/tech-04/`
   - 评审口径：在系统总览中明确"三大核心功能 + F-ACCT 横向支撑"

2. **Stance 拆层：F-PROP=帖级 / F-ACCT=账号级聚合**
   - 理由：避免双轨实现，复用 Propagation Analysis WP4 算法成果
   - 影响：F-ACCT-2 阻塞于 Propagation Analysis WP4 完成
   - 替代方案：先在 F-ACCT 内做"轻量句级 stance"作为 fallback（如果 Propagation Analysis WP4 进度落后），但仍以 Propagation Analysis 输出为最终来源

3. **Bot detection 走预训练模型路线**
   - 理由：用户选定，准确率高于纯规则
   - 影响：需补 transformers / torch 依赖，或保留 Botometer API
   - 降级：API 不可用 + 模型未加载时退到规则路径，与现有 `automation_score` 同源

4. **KOL 识别保持规则化**
   - 理由：商业平台都用粉丝数 + 认证作为分级，规则可解释
   - 影响：无 research 工作量
   - 风险：跨平台阈值需各自校准

5. **目录从单文件提升为包**
   - 理由：从 1 个子功能扩到 5 个，需要清晰命名空间
   - 影响：现有 `core/account_profiler.py` 保留为 shim，旧 import 不变

6. **F-ACCT-6 复用 MediaCrawler，不新增爬虫**
   - 理由：MediaCrawler 已支持 weibo / douyin / xhs 的 creator 模式，重新造轮成本高
   - 影响：在 `core/crawler/social.py` 扩展 `mode=creator` 参数，`homepage_collector.py` 通过该入口调用
   - 风险：若 MediaCrawler 后续 creator 模式有 breaking change，需要 social.py 适配

7. **F-ACCT-6 内容巡检全部复用上游算法（不重新实现）**
   - 理由：风险检测复用 Propagation Analysis WP5 / 立场复用 Propagation Analysis WP4 / 模板化复用 F-COORD 通道
   - 影响：F-ACCT-6 仅做编排 + 批处理，不涉及新算法 → research = 0
   - 降级：若上游未完成（特别是 Propagation Analysis WP4/5），content_checker 用 mock fallback（仅给规则化结果），并在响应中明确 `data_completeness="partial"`

### 7.2 开放问题

1. **Bot 模型在中文社交媒体的 zero-shot 性能**
   - 阻塞：R1 实验未做
   - 缓解：起步阶段用规则路径，模型路径作为可选

2. **Stance 聚合的小样本问题**
   - 阻塞：账号在事件窗口内可能只发 1-2 帖
   - 缓解：扩展窗口（事件外 7 天内的相关帖）+ `sample_size < 5` 标记低置信度

3. **缓存失效与一致性**
   - 问题：bot.score 7 天 cache 期间，账号可能转为活跃
   - 缓解：发文频率突变时主动失效（webhook 或定时扫描）

4. **跨平台账号同一性**
   - 问题：同一用户在 weibo / douyin / xhs 的画像互不打通
   - 缓解：本期不做跨平台对齐（M2 错位项已延后），用 `(platform, account_id)` 唯一键

5. **隐私与合规**
   - 问题：bot 评分可能带歧视效应（误判真人为 bot）
   - 缓解：所有评分带 `explanation` 字段；前端显示"算法判定"而非"事实标签"

---

## 八、对其他功能的接口契约

### 8.1 F-ACCT → F-COORD

```python
# F-COORD 消费 F-ACCT 用于过滤 / 加权
bot_filter = client.get_bot_scores(account_ids=[...])
# 用法 1：在 PSL 计算前过滤掉高 bot_score 账号（去除噪声）
# 用法 2：把 bot_score 作为 edge_score 加权因子
```

### 8.2 F-ACCT → F-PROP

```python
# F-PROP 消费 F-ACCT 用于 KOL 信号 + 自动化倾向
account_profiles = client.get_batch_profiles(account_ids=[...])
# 用法 1：trend_predictor.py 的事件评分向量 e 中加入 kol_ratio
# 用法 2：burst 是否被 KOL 推动作为 amplification 体制的强信号
```

### 8.3 F-ACCT → F-RISK

```python
# F-RISK 消费 F-ACCT 用于风险因子
profiles = client.get_batch_profiles(account_ids=coord_group_members)
# 用法 1：evidence_builder 计算 group 的 bot_ratio
# 用法 2：ds_fusion 的 mass(manipulation) 与 bot_ratio 正相关
```

### 8.4 F-ACCT ← F-PROP WP4（反向依赖）

```python
# F-ACCT-2 stance_aggregator 调用 F-PROP 帖级 stance
post_stances = client.get_post_stances(
    account_id=..., time_range=...)
# 返回 [{post_id, stance, confidence}, ...]
```

**契约要求**：F-PROP WP4 必须暴露 `GET /api/v1/propagation/stance/by-account?account_id=...` 端点。

### 8.5 F-ACCT-6 → 上游算法模块（横向编排消费）

F-ACCT-6 内容巡检不重新实现算法，而是按帖批处理调用上游：

```python
# content_checker.py
for post in account_posts:
    harm = harm_assessor.score(post.content, post.metadata)        # 复用 Propagation Analysis WP5
    stance = stance_detector.detect(post.content)                  # 复用 Propagation Analysis WP4
    template = template_detector.check(post, account_corpus)       # 复用 F-COORD channels.py
    yield {post_id: post.id, harm, stance, template}
```

**契约要求**：

- Propagation Analysis WP5 `harm_assessor.score(text, metadata) -> {score, dimensions}` 必须暴露为可单帖调用的纯函数
- Propagation Analysis WP4 `stance_detector.detect(text) -> {label, confidence}` 同样
- F-COORD `channels.py` 需提供 `template_detector.check(post, corpus) -> {is_template, template_id, duplicate_count}` 子接口（单账号语料模板抽取）

**降级策略**：上游缺失时返回 `null` 字段并标 `data_completeness="partial"`，前端用占位符渲染。

---

## 九、引用

| 类别 | 路径 | 用途 |
|---|---|---|
| 系统总览 | [research-engineering-split.md](./research-engineering-split.md) | 加入 F-ACCT 横向支撑功能后的总图 |
| F-PROP 文档 | [../../aris/tech-02-propagation/REQUIREMENTS.md](../../aris/tech-02-propagation/REQUIREMENTS.md) | WP4 帖级 stance 实现细节 |
| F-COORD 文档 | [../../aris/tech-01-coordination/REQUIREMENTS.md](../../aris/tech-01-coordination/REQUIREMENTS.md) | 协同检测对 bot_score 的消费 |
| F-RISK 文档 | [../../aris/tech-03-risk/REQUIREMENTS.md](../../aris/tech-03-risk/REQUIREMENTS.md) | 报告研判对账号画像的消费 |
| 现有代码 | `new-system/backend/app/core/account_profiler.py` | 185 行 MVP，待迁入新包 |
| 现有服务层 | `new-system/backend/app/services/account_service.py` | 43 行雏形，待扩 |
| 现有 API | `new-system/backend/app/api/v1/accounts.py` | 30 行，待扩 |
| 现有前端 | `new-system/frontend/src/views/accounts/index.vue` | 已有评分页 |

---

## 十、后续动作

**第一周（engineering 主导，Claude Code）**：

1. E1：目录迁移 + shim → 1 h
2. E2 + E3：依赖 + alembic（含 E13 account_homepage 表） → 1.5 h
3. E4：`bot_detector.py` 框架 + 规则路径 + mock（模型路径占位） → 4 h
4. E5：`kol_identifier.py` 规则化 + 配置加载 → 3 h
5. E11：F-ACCT-6 `homepage_collector.py` + `social.py` 扩展 `mode=creator` → 6-8 h
6. E12：F-ACCT-6 `content_checker.py` 编排（上游缺失时 mock fallback） → 3-4 h
7. E6 + E7 + E14：服务层 + API（含 F-ACCT-6 三个新端点） → 6 h
8. E8 + E15：前端 3 Panel + 账户详情页 → 11-14 h

**第二周（research，本地实验）**：

1. R1：Bot 模型选择实验（100 条标注账号上对比 3 路） → 3 d
2. R3：规则特征清单论证 + 与 `automation_score` 既有特征对比 → 2 d
3. R5：KOL 阈值平台校准（weibo / douyin / xhs 各 50 个标注账号） → 2 d

**第三周（跨功能联调）**：

1. E9：`stance_aggregator.py`（依赖 Propagation Analysis WP4） → 3 h
2. E10：Redis 缓存层 + TTL → 2 h
3. R2 + R4：Fusion 权重 + 聚合公式调优 → 2 d
4. F-ACCT ↔ F-COORD / F-PROP / F-RISK 接口联调
5. F-ACCT-6 内容巡检从 mock fallback 切换到真实上游（依赖 Propagation Analysis WP4/5 + F-COORD 模板检测）

**关键里程碑**：

- 周末 1：F-ACCT MVP（bot 规则路径 + KOL + 旧 activity + **F-ACCT-6 主页采集 + 账户详情页**）端到端跑通
- 周末 2：bot 模型路径接入 + R1 数据结论 + F-ACCT-6 内容巡检 mock 全字段输出
- 周末 3：stance 聚合上线（依赖 Propagation Analysis WP4）+ 全链路联调 + F-ACCT-6 切换到真实算法
