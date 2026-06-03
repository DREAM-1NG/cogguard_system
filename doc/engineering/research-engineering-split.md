# CogGuard research / engineering 分工总览

> **用途**：作为后续团队分工的权威分割表。把三大核心功能（F-COORD / F-PROP / F-RISK）+ 横向支撑功能（F-ACCT）按"算法创新（research）"与"工程拼装（engineering）"二分，明确哪些任务由 Claude Code 在本仓库快速完成、哪些任务需要本地实验探究。
> **维护规则**：每条 research 任务完成本地实验产出后，要回写参数 / 结论到对应 `aris/tech-NN/REQUIREMENTS.md` 或 `doc/engineering/F-ACCT-account-profiling.md`；每条 engineering 任务完成提交后，要勾选状态并同步 `development-log.md`。
> **最后更新**：2026-05-20

---

## 一、功能架构与主要技术对应表

CogGuard 主链路：`事件 → 证据 → 协同 → 传播 → 风险 → 处置`。

**三大核心功能**各由一项关键技术（KT）支撑，**一项横向支撑功能（F-ACCT）**被三大功能共同消费。

```
                ┌──────────────────────────────────────┐
                │     F-ACCT 深度账号画像（横向支撑）    │
                │  bot / stance 聚合 / KOL / activity   │
                └────┬───────────┬───────────┬─────────┘
                     │           │           │
                     ▼           ▼           ▼
                  F-COORD    F-PROP      F-RISK
                  (KT1 PSL)  (KT2 CSw)  (KT3 PA-H+DISARM)
```

| 功能简称 | 中文名 | 类型 | 主要技术（创新载体） | 其他技术支持 | 系统位置 |
|---|---|---|---|---|---|
| **F-COORD** | 跨平台协同检测 | 核心 | KT1 PSL（Pair Surprisal Layer） | CooRTweet 共享对象、统计检验、语义向量、图算法、ECharts | `core/coordination/` + `aris/tech-01-coordination/` |
| **F-PROP** | 传播监控与趋势预测 | 核心 | KT2 CascadeSwitch（体制切换预测） | 时序特征工程、LLM API、立场/危害评估（帖级）、混合预测、可视化 | `core/propagation/` + `aris/tech-02-propagation/` |
| **F-RISK** | 报告研判与攻击路径 | 核心 | KT3 Phase-Aware Hazard + DISARM 路径推理 | Dempster-Shafer 融合、证据特征、DISARM 映射、报告模板、规则引擎 | `core/risk/` + `aris/tech-03-risk/` |
| **F-ACCT** | 深度账号画像 | **支撑** | 预训练 Bot 检测（Botometer / Twibot-22 RoBERTa） | 账号级 stance 聚合、规则化 KOL 识别、行为画像、作息节律 | `core/account/` + `doc/engineering/F-ACCT-account-profiling.md` |

---

## 二、研究 vs 工程的判定规则

| 标签 | 判定条件（满足其一即归入） |
|---|---|
| **research** | (1) 参数需调，效果不确定；(2) 需要消融实验或数据集验证；(3) 有论文新颖性，可写文章；(4) 算法选择本身仍在比较中（含 LLM prompt 工程） |
| **engineering** | (1) 输入输出规范明确；(2) 公式 / 算法 / 模板已经确定，按规格写就能跑；(3) 跑出来结果可预期；(4) 失败模式不来自算法本身而来自集成 |
| **边界** | 同时满足两边部分条件（如 LLM 立场检测——既需要 prompt 调优又有大量工程接入） |

---

## 三、F-COORD（跨平台协同检测）拆分

### 3.1 主要技术：KT1 PSL（全部 research）

| 子项 | 简述 | 标签 | 当前状态 | 落点 / 阻塞 |
|---|---|---|---|---|
| 对称双账号超几何检验 | `p_pair = max(p_u, p_v)` 校正活跃度差异 | research | 未开始 | `core/coordination/significance.py`，需消融对比 max / min / product |
| Cauchy combination | 融合多 object / 多通道 p-values（无独立性假设） | research | 未开始 | 同上 |
| Pair-level BH-FDR | 配对层级多重检验校正 | research | 未开始 | 同上，需 permutation-based FDR 校准 |
| 多通道证据融合 | Object / Semantic / Cascade 通道权重 | research | 未开始 | 同上 + `channels.py` |
| ADR-001 触发条件 | 多模态扩展触发（融合 FDR > 0.2） | research | 设计完成 | `systemDesign.md` 已设计，代码侧无 |

### 3.2 其他技术支持

| 子项 | 简述 | 标签 | 当前状态 | 落点 |
|---|---|---|---|---|
| CooRTweet 共享对象检测 | 时间窗内配对、快窗标记 | engineering | ✅ 已实现 | `core/coordination/detector.py` (177) |
| 多通道 Object 提取 | url / hashtag / media / cascade → object_id | engineering | 未开始 | `core/coordination/channels.py` |
| 语义向量编码 | 冻结句向量 + mutual-kNN | 边界 | 未开始 | `semantic.py`（模型选择是研究、调用是工程） |
| statsmodels BH-FDR 调用 | 现成包包装 | engineering | 未开始 | `significance.py` 内 |
| 协同图聚合 | NetworkX 加权图 / 连通分量 / 社区 | engineering | ✅ 已实现 | `core/coordination/network.py` (166) |
| 协同检测 API | `POST /api/v1/coordination/detect` | engineering | ✅ 已实现 | `api/v1/coordination.py` (27) |
| 服务层编排 | 串联通道提取 → PSL → 网络聚合 | engineering | 雏形 | `services/coordination_service.py` (90, 待扩) |
| 前端协同网络可视化 | ECharts force-directed | engineering | ✅ 已实现 | `frontend/src/views/coordination/index.vue` |
| 多模态展示承载（M1） | 文本/图片/视频/外链/元数据 5 要素同屏 | engineering | 未开始 | 前端搜索子系统 C2，待新增 |

详见 [aris/tech-01-coordination/REQUIREMENTS.md](../../aris/tech-01-coordination/REQUIREMENTS.md)。

---

## 四、F-PROP（传播监控与趋势预测）拆分

### 4.1 主要技术：KT2 CascadeSwitch

| 子项 | 简述 | 标签 | 当前状态 | 落点 / 阻塞 |
|---|---|---|---|---|
| 4 体制混合预测 | Seeding/Amplification/Peak/Decay 参数化模型 | research | ✅ 代码已实现 | `regime_model.py` (224)，需 DeepHawkes/CasFlow 校准 |
| 体制后验计算 | `p(z) = softmax((W·e + b) / τ)` | research | ✅ 代码已实现 | `trend_predictor.py` (180)，W/b/τ 默认值未校准 |
| LLM 事件上下文提取 | 6 类事件类型 prompt + JSON Schema | research（prompt） | ✅ 代码已实现 | `llm_context.py` (162)，prompt 需迭代 |
| 不确定性估计 | 混合方差 `σ²(t) = Σ p(z)·[f_z² + σ_z²] - ŷ²` | research | ✅ 代码已实现 | `trend_predictor.py` 内 |
| 立场检测（WP4） | LLM 零样本分类 + 6 类立场标签 | 边界 | ❌ 文件不存在 | `stance_detector.py`，需先定标签体系 |
| 危害性评估（WP5） | 规则 + LLM 增强的 0-100 评分 | 边界 | ❌ 文件不存在 | `harm_assessor.py`，需先定评分维度 |

### 4.2 其他技术支持

| 子项 | 简述 | 标签 | 当前状态 | 落点 |
|---|---|---|---|---|
| 时序特征工程 | volume/velocity/acceleration/burst_zscore | engineering | ✅ 已实现 | `ts_features.py` (107) |
| 级联形态事件检测 | 无 LLM 时从级联动态推断（规则化降级） | engineering | 未开始 | `cascade_events.py` 待新增 |
| LLM API 客户端 | openai/dashscope 异步 + 重试 + mock | engineering | ❌ 缺依赖 | `llm_client.py` 待新增，`pyproject.toml` 待补 |
| 旧方向源头追溯 | MultiDiGraph + 证据链 + 关键路径 | engineering | ✅ 保留 | `core/propagation_legacy.py` |
| 传播监控 API | `GET /api/v1/propagation/analyze` | engineering | 雏形 | `api/v1/propagation.py` (29, 待扩) |
| 服务层编排 | 串联 ts_features → llm_context → trend_predictor | engineering | 雏形 | `propagation_service.py` (48, 待扩) |
| 前端传播预测可视化 | 时序曲线 + 置信区间带 + 体制概率堆叠图 | engineering | 基础页已有 | `frontend/src/views/propagation/index.vue` |

详见 [aris/tech-02-propagation/REQUIREMENTS.md](../../aris/tech-02-propagation/REQUIREMENTS.md)。

---

## 五、F-RISK（报告研判与攻击路径）拆分

### 5.1 主要技术：KT3 Phase-Aware Hazard + DISARM

| 子项 | 简述 | 标签 | 当前状态 | 落点 / 阻塞 |
|---|---|---|---|---|
| 5 状态生命周期 + logistic hazard | seed → synchronize → breakout → saturation → regeneration | research（5 参数） | ✅ 代码已实现 | `phase_detector.py` (169)，参数未校准 |
| Dempster-Shafer 三维融合 | 真实性/操纵性/危害性 + 阶段调制 + 冲突质量 | research（9+5 参数） | ✅ 代码已实现 | `ds_fusion.py` (234)，需边界 case 测试 |
| DISARM 攻击路径推理 | 18 条边 + 转换概率 + 下一步预测 + 反制建议 | research（18 概率） | ✅ 代码已实现 | `disarm_scorer.py` (381)，概率为领域先验 |
| 阶段感知冲突检测 | conflict_mass > 0.3 触发人工介入 | research | ✅ 代码已实现 | `ds_fusion.py` 内 |
| 路径评分 | depth/breadth/completeness 加权 | research（3 参数） | ✅ 代码已实现 | `disarm_scorer.py` 内 |

### 5.2 其他技术支持

| 子项 | 简述 | 标签 | 当前状态 | 落点 |
|---|---|---|---|---|
| 证据特征提取 | Gini/Shannon/突发性等通用公式 | engineering | ✅ 已实现 | `evidence_builder.py` (244) |
| DISARM 技术映射规则表 | 45 种技术硬编码映射 | engineering | ✅ 已实现 | `disarm_scorer.py` 内（需专家校验） |
| 结构化报告 JSON 模板 | 18 顶层字段 + 证据链 + 风险因子 + 建议 | engineering | ✅ 已实现 | `report_builder.py` (278) |
| LLM 桥接 | 报告解释生成 + 反制建议自然语言化 | engineering | ❌ stub | `llm_bridge.py` (30, 待补) |
| 报告研判 API | `POST /api/v1/risk/assess` + 报告列表/详情 | engineering | ✅ 已实现 | `api/v1/risk.py` (68) |
| 服务层编排 | 串联 evidence → phase → fusion → DISARM → report | engineering | ✅ 已实现 | `risk_service.py` (153) |
| 数据库持久化 | RiskAssessment 表 + alembic 迁移 | engineering | ⚠️ 缺迁移 | `alembic/versions/xxx_add_risk.py` 待新增 |
| 前端报告研判页 | 报告列表 + 详情 + DISARM 路径可视化 | engineering | 基础页已有 | `risk/index.vue`（路径图待补） |

详见 [aris/tech-03-risk/REQUIREMENTS.md](../../aris/tech-03-risk/REQUIREMENTS.md)。

---

## 五bis、F-ACCT（深度账号画像，横向支撑功能）拆分

> **定位提醒**：F-ACCT 不是第 4 个关键技术，而是被 F-COORD / F-PROP / F-RISK 共同消费的横向证据层。

### 5bis.1 主要技术：Bot 检测预训练模型

| 子项 | 简述 | 标签 | 当前状态 | 落点 / 阻塞 |
|---|---|---|---|---|
| Botometer X API 调用 | 工业基线，准确率高，需 RAPIDAPI_KEY | engineering | 未开始 | `core/account/bot_detector.py`（待新增） |
| Twibot-22 RoBERTa 本地推断 | HuggingFace transformers，CPU 友好 | research（中文 zero-shot 性能未知） | 未开始 | 同上 |
| 规则统计特征（10-15 个） | 发文间隔CV / 作息规律 / 跨平台重贴 / 头像缺失等 | research（特征清单待论证） | 部分已在 `automation_score` | `core/account/bot_detector.py` |
| 三路降级 + Fusion | API → 模型 → 规则；final=0.4·rule+0.6·ml | engineering | 未开始 | 同上 |

### 5bis.2 其他技术支持

| 子项 | 简述 | 标签 | 当前状态 | 落点 |
|---|---|---|---|---|
| 账号级 stance 聚合 | 加权频率 + 极化指数 + 一致性 | 边界（公式 research + 实现 engineering） | ❌ 阻塞于 KT2 WP4 | `core/account/stance_aggregator.py`（待新增） |
| KOL 识别 | 规则化分级（head/mid/tail） + 配置阈值 | engineering | 未开始 | `core/account/kol_identifier.py`（待新增） |
| 行为画像（旧） | 发文频率/作息/内容多样性 | engineering | ✅ MVP 已实现 | `core/account_profiler.py` (185)，待迁入新包 |
| 自动化倾向评分（旧） | 多维 0-100 综合评分 | engineering | ✅ MVP 已实现 | 同上 |
| **单用户主页采集（F-ACCT-6）** | 调用 MediaCrawler creator 模式抓主页元数据 + 全部发文 | engineering | 未开始 | `core/account/homepage_collector.py` + `core/crawler/social.py` 扩展 `mode=creator` |
| **内容巡检（F-ACCT-6）** | 对账号全部发文做风险/立场/模板化检测，**全部复用上游算法** | engineering（编排） | ❌ 阻塞于 KT2 WP4/5 + F-COORD 通道 | `core/account/content_checker.py` |
| 账号画像 API | `GET /accounts/profile/{id}` + 4 个子端点 + F-ACCT-6 三个新端点 | engineering | 雏形 | `api/v1/accounts.py` (30) |
| 服务层 | 聚合所有子模块 + 缓存 + 编排主页采集 | engineering | 雏形 | `services/account_service.py` (43, 待扩) |
| 缓存层 | Redis + TTL（bot 7d / stance 6h / kol 30d） | engineering | 未开始 | `account_service.py` 内 |
| 前端账号画像页 | 评分 + 排序 + bot / stance / KOL 三段 | engineering | 基础页已有 | `frontend/views/accounts/` |
| **前端账户详情页（F-ACCT-6）** | 主页元数据 + 内容流 + 巡检结果三栏 | engineering | 未开始 | `frontend/views/accounts/detail/index.vue` |

详见 [F-ACCT-account-profiling.md](./F-ACCT-account-profiling.md)。

---

## 六、全系统共用 engineering（不属于单一功能）

| 模块 | 子项 | 当前状态 | 优先级 |
|---|---|---|---|
| 数据采集 | Mock + 真实爬虫（MediaCrawler/NewsCrawler 封装） | ✅ MVP | — |
| 数据标准化 | DataNormalizer 跨平台字段 | ✅ 完成 | — |
| 数据库 | MySQL + MongoDB + Redis 部署 | ✅ docker-compose | — |
| 用户认证 | JWT + 角色权限（admin/analyst/viewer） | ✅ 完成 | — |
| **监测看板** | 系统概览/热点排行/平台统计/风险趋势图 | 🔲 待开发（`dashboard/index.vue` 占位） | P1 |
| **预警管理** | 事件级/群体级/claim 级告警 | 🔲 待开发 | P2 |
| **报告中心** | 报告列表/PDF 导出/案例归档 | 🔲 待开发 | P2 |
| **系统部署** | Dockerfile + 全栈 Compose 一键部署 | 🔲 待开发 | P2 |

---

## 七、research 任务清单（本地实验）

按所属功能与优先级排列：

| 优先级 | 功能 | 任务 | 当前阻塞 | 验证方式 |
|---|---|---|---|---|
| P0 | F-PROP | CascadeSwitch W/b/τ 参数校准 | 参数为默认值 | 在 DeepHawkes Weibo / CasFlow Twitter 上对比 ARIMA/Prophet 基线 |
| P0 | F-PROP | LLM event prompt 工程 | prompt 未在真实样本迭代 | 100 条标注样本上的事件类型分类准确率 |
| P1 | F-COORD | PSL 对称超几何 + Cauchy + BH-FDR | 代码未开始 | 5 消融变体 + Seckin 2024 IO 标注数据集 FDR 校准 |
| P1 | F-COORD | 语义通道（SemanticPairAdapter） | 模型选择 + kNN 池大小 | 在 mock 数据上验证 p_sem 的零分布近似 |
| P1 | F-RISK | Phase-Aware Hazard 5 参数 | 参数未校准 | 历史战役 case study + 转换准确率 |
| P1 | F-RISK | D-S 融合 9+5 参数 | 边界 case 未测试 | mass=0 / mass=1 / 冲突质量极高 三种边界 |
| P2 | F-COORD | 级联通道（Cascade Channel） | 子类型统计性质未验证 | 评论链超几何检验合理性 |
| P2 | F-PROP | 立场检测 + 危害评估（**帖级**，KT2 WP4-5） | 标签体系未定 | 先与导师/竞赛指导确定 6 类立场 + 危害维度 |
| P2 | F-RISK | DISARM 18 条路径转换概率 | 当前为领域先验 | 实战 case 迭代 |
| P2 | F-ACCT | Bot detection 预训练模型选择（R1） | 中文 zero-shot 性能未知 | 100 条标注微博账号上对比 Botometer / Twibot-22 / 规则 |
| P2 | F-ACCT | 规则特征清单论证（R3） | 10-15 个特征未定 | 与现有 `automation_score` 特征对比 + 文献综述 |
| P2 | F-ACCT | 账号级 stance 聚合公式（R4） | 加权 vs 简单频率 / 极化定义 | 标注账号上人工评估 6 维分布 |
| P2 | F-ACCT | KOL 阈值平台校准（R5） | 跨平台阈值差异 | weibo/douyin/xhs 各 50 个标注账号 |

**本地实验执行约定**：

- 每个 research 任务在本地分支 `aris/t{1,2,3}-experiment-{name}` 下进行
- 实验产物（`outputs/`、`logs/`）不入 git，结论回写到对应 `aris/tech-NN/REQUIREMENTS.md`
- GPU 任务可用 vast.ai / Modal / 启智平台（参见 `qzcli` skill）

---

## 八、engineering 任务清单（Claude Code 快速完成）

按优先级排列，每条带工作量预估：

| 优先级 | 功能 | 任务 | 工作量 | 验证 |
|---|---|---|---|---|
| P0 | F-RISK | 补 `alembic` 迁移以支持 `risk_assessment` 表 | 30 min | `alembic upgrade head` 不报错 |
| P0 | F-PROP/F-RISK | 补 `pyproject.toml` LLM 客户端依赖（openai/dashscope） | 30 min | `uv sync` 通过 |
| P0 | F-PROP/F-RISK | 实现 `llm_client.py`（异步 + 重试 + mock fallback），替换 `llm_bridge.py` stub | 2 h | mock 模式下完整调用通过 |
| P0 | 治理 | git 治理性提交（aris/doc/memory/AGENTS.md/CLAUDE.md） | 30 min | `git status` 清洁 |
| P1 | F-COORD | `channels.py` 多通道 Object 提取（规则化，不涉算法） | 3-4 h | 单元测试覆盖 4 种 channel |
| P1 | F-COORD | `coordination_service.py` 扩展以串通新通道 | 2 h | API 联调通过 |
| P1 | F-PROP | `cascade_events.py` 级联形态事件检测（规则化降级） | 3 h | 在 mock 数据上输出 6 类事件 |
| P1 | F-PROP | `propagation_service.py` 扩展以串通 WP1-3 | 2 h | API 联调通过 |
| P1 | F-RISK | 前端 DISARM 路径可视化（ECharts force-directed） | 4-6 h | 18 条边渲染正确 |
| P0 | F-ACCT | 目录迁移：`core/account_profiler.py` → `core/account/activity_profiler.py` + shim | 1 h | 旧 import 路径不破坏 |
| P0 | F-ACCT | 补 `pyproject.toml`（transformers/torch CPU）+ `.env` 环境变量 | 30 min | `uv sync` 通过 |
| P0 | F-ACCT | alembic 迁移 `account_profile_cache` 表 | 30 min | `alembic upgrade head` 不报错 |
| P1 | F-ACCT | `bot_detector.py` 双层 + 3 路降级 + mock（规则路径先行） | 5-7 h | API/模型/规则三路均可触发 |
| P1 | F-ACCT | `kol_identifier.py` 规则化 + 配置加载 | 2-3 h | 三种 KOL tier 标注正确 |
| P1 | F-ACCT | `account_service.py` 扩展 4 个新方法 | 2 h | 服务层联调通过 |
| P1 | F-ACCT | `api/v1/accounts.py` 新增 4 个端点 | 2 h | API 联调通过 |
| P1 | F-ACCT | 前端 3 个 Panel 组件（Bot/Stance/KOL） + 路由 | 5-6 h | 三段展示正确 |
| P2 | F-ACCT | `stance_aggregator.py`（依赖 F-PROP WP4 完成） | 2-3 h | 与 F-PROP 接口联调 |
| P2 | F-ACCT | Redis 缓存层 + TTL 策略 | 2 h | 命中率监控 |
| P1 | F-ACCT | F-ACCT-6 主页采集：`homepage_collector.py` + `social.py` 扩展 `mode=creator` | 6-8 h | weibo/douyin/xhs 三平台主页可拉取 |
| P1 | F-ACCT | F-ACCT-6 内容巡检：`content_checker.py` 编排（上游缺失时 mock fallback） | 3-4 h | 单账号语料批处理 |
| P1 | F-ACCT | F-ACCT-6 alembic 迁移 `account_homepage` 表 + ORM | 1 h | `alembic upgrade head` |
| P1 | F-ACCT | F-ACCT-6 API 3 端点 + 前端账户详情页（主页 + 内容流 + 巡检三栏） | 8-10 h | E2E 渲染正确 |
| P2 | 全局 | 监测看板（系统概览 + 热点排行 + 风险趋势） | 1-2 d | 接入后端统计 API |
| P2 | 全局 | 报告中心（列表 + PDF 导出 + 案例归档） | 1-2 d | 端到端生成报告 |
| P2 | 全局 | 预警管理（规则配置 + 告警状态） | 1-2 d | 触发流程联调 |

---

## 九、跨 KT 依赖与契约

| 上游 | 下游 | 数据 | 契约文件 | 现状 |
|---|---|---|---|---|
| F-COORD | F-PROP | `coord_groups` / `network_density` / `evidence_edges` | `aris/shared/CROSS_KT_DEPS.md` | 字段约定完成，接口未联调 |
| F-PROP | F-RISK | `trend / stance / harm / source / scope` | 同上 | KT3 已用占位数据，等 KT2 WP4-5 完成后替换 |
| F-RISK | UI | `risk_assessment_report.json` 结构化 | `aris/tech-03-risk/ACCEPTANCE.md` | 字段约定完成，前端路径图待补 |
| F-ACCT | F-COORD | `bot_score` / `is_kol` 用于过滤 / 加权 | F-ACCT 文档 §8.1 | 字段约定完成，待 F-ACCT MVP 上线 |
| F-ACCT | F-PROP | 账号画像（KOL 标识 / 自动化倾向）作为事件评分 e 的输入 | F-ACCT 文档 §8.2 | 同上 |
| F-ACCT | F-RISK | group `bot_ratio` / KOL 分布作为 mass(manipulation) 输入 | F-ACCT 文档 §8.3 | 同上 |
| F-PROP WP4 | F-ACCT | **帖级** stance → F-ACCT 聚合为**账号级** stance | F-ACCT 文档 §8.4 | ⚠️ 阻塞 F-ACCT-2，需 F-PROP 暴露 `/propagation/stance/by-account` |
| KT2 WP4/WP5 | F-ACCT-6 | 帖级立场 + 帖级危害评分作为内容巡检的字段输入 | F-ACCT 文档 §8.5 | ⚠️ 阻塞 content_checker 真实输出；上游缺失时 mock fallback |
| F-COORD channels.py | F-ACCT-6 | 单账号语料模板化检测（语义重复 / hashtag 模板） | F-ACCT 文档 §8.5 | ⚠️ 阻塞 template_detector 子接口；上游缺失时返回 null |
| MediaCrawler creator 模式 | F-ACCT-6 | 主页元数据 + 全量发文流采集 | `core/crawler/social.py` 扩展 `mode=creator` | weibo / douyin / xhs 已支持，需 social.py 接入 |

---

## 十、推荐执行节奏

**第一周（engineering，Claude Code 主导）**：

1. Day 1：P0 全部完成（alembic + LLM 依赖 + `llm_client.py` + git 治理）
2. Day 2-3：F-COORD P1（`channels.py` + 服务层扩展）
3. Day 4：F-PROP P1（`cascade_events.py` + 服务层扩展）
4. Day 5：F-RISK P1（DISARM 路径前端可视化）

**第二周（research，本地实验）**：

1. F-PROP P0：CascadeSwitch 参数校准 + LLM event prompt 迭代
2. F-COORD P1：PSL 算法实现 + 消融实验
3. F-RISK P1：Phase-Aware Hazard 参数校准

**第三周（跨 KT 联调 + 全局 engineering P2）**：

1. F-COORD ↔ F-PROP ↔ F-RISK 接口联调
2. 监测看板 / 报告中心 / 预警管理

---

## 十一、引用

- 四份功能级需求文档：
  - [aris/tech-01-coordination/REQUIREMENTS.md](../../aris/tech-01-coordination/REQUIREMENTS.md)（F-COORD）
  - [aris/tech-02-propagation/REQUIREMENTS.md](../../aris/tech-02-propagation/REQUIREMENTS.md)（F-PROP）
  - [aris/tech-03-risk/REQUIREMENTS.md](../../aris/tech-03-risk/REQUIREMENTS.md)（F-RISK）
  - [F-ACCT-account-profiling.md](./F-ACCT-account-profiling.md)（F-ACCT 横向支撑）
- 工程主线文档：
  - [development-roadmap.md](./development-roadmap.md)
  - [development-log.md](./development-log.md)
- KT 研究背景：
  - [doc/research/key-technology-background/](../research/key-technology-background/)
- 记忆体（Session Startup）：
  - [memory/PLAYBOOK.md](../../memory/PLAYBOOK.md)
  - [memory/state_kt1.md](../../memory/state_kt1.md) / [state_kt2.md](../../memory/state_kt2.md) / [state_kt3.md](../../memory/state_kt3.md)
