# CogGuard：面向跨平台协同操纵分析的证据驱动原型系统

CogGuard 是一个面向竞赛和研究验证的开源原型，目标是围绕跨平台协同操纵活动建立一条可解释、可复核的分析链路：

`事件 -> 证据 -> 协同 -> 传播 -> 风险 -> 处置`

仓库当前以 `release-0.2` 为工程基线，主线代码位于 [system/README.md](system/README.md) 对应的 `system/` 目录。

## 当前基线

- 当前工程基线：`release-0.2`
- 当前唯一产品代码根：`system/`
- 当前短期验证范围：`mock_weibo`、`weibo`、`news`
- 参考/依赖边界：`MediaCrawler-main/`、`NewsCrawler-main/`、`CooRTweet-master/`
- 术语源头：[`UBIQUITOUS_LANGUAGE.md`](UBIQUITOUS_LANGUAGE.md)
- 系统治理：[`doc/engineering/system-governance.md`](doc/engineering/system-governance.md)
- 架构决策：[`docs/adr/`](docs/adr/)
- 竞赛材料目录：[`../materials/`](../materials/)（PPT、申报书、开题材料等，不放入产品代码目录）
- 仓库级上下文入口：[`AGENTS.md`](AGENTS.md)
- ARIS 工作空间入口：[`aris/README.md`](aris/README.md)
- 项目结构边界说明：[`doc/engineering/project-map.md`](doc/engineering/project-map.md)

## 仓库分层

| 层 | 路径 | 作用 |
|------|------|------|
| 长期文档层 | [`doc/`](doc/) | 开发进度、环境说明、技术背景、变更日志 |
| 架构决策层 | [`docs/adr/`](docs/adr/) | 重要架构、术语和边界决策记录 |
| ARIS 工作空间层 | [`aris/`](aris/) | 针对 Coordination Discover、Propagation Analysis、Risk Review 的独立 ARIS 执行入口 |
| 产品代码层 | [`system/`](system/) | 当前唯一有效的后端、前端、部署与测试代码 |
| 参考边界层 | `MediaCrawler-main/` `NewsCrawler-main/` `CooRTweet-master/` | 上游参考与依赖，不作为默认修改范围 |
| 外层竞赛材料层 | [`../materials/`](../materials/) | PPT、申报书、开题材料与竞赛交付材料 |

## 当前工程状态

以 [`doc/engineering/development-roadmap.md`](doc/engineering/development-roadmap.md) 为准，当前状态可概括为：

| 模块 | 状态 | 说明 |
|------|------|------|
| 数据采集 | MVP 已完成 | Mock + 真实爬虫封装已接入 |
| Coordination Discover / Coordination Detect | MVP 已完成 | 已有共享对象协同检测（旧方向），正式方法名已统一为 `Coordination Discover` / `Coordination Detect`，PSL 新方向在 `aris/tech-01-coordination/` 已完成系统设计 |
| 传播监控 | WP1-3 已完成 | Hybrid TS + LLM 路线，已实现 `ts_features` / `llm_context` / `regime_model` / `trend_predictor`；WP4-5（立场/危害）未启动 |
| 账户监测 | MVP 已完成 | 已有画像、自动化评分与 BotRHG 风格社交机器人检测 API，待补历史参与与前端深度展示 |
| 报告研判 | MVP 已完成 | `core/risk/` 1,340 行（DISARM 评分 / D-S 融合 / 证据链 / 报告生成 / 阶段检测）+ `risk_service` 编排层 + 风险 API + 前端风险页 |
| 看板/预警/报告 | 待开发 | `dashboard/index.vue` 仍为占位，预警与报告管理未启动 |

## 快速开始

```bash
# 1. 启动基础服务
cd system
cp .env.example .env
docker compose up -d

# 2. 启动后端
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 3. 启动前端
cd ../frontend
npm install
npm run dev
```

- 详细环境与启动步骤见 [`doc/engineering/environment-setup.md`](doc/engineering/environment-setup.md)
- 详细系统开发说明见 [`system/README.md`](system/README.md)

## ARIS 工作流

如果任务由 ARIS/Claude Code/Codex 驱动，不直接在仓库根随意开工，按下面路径执行：

1. 先读 [`AGENTS.md`](AGENTS.md)、[`doc/engineering/development-roadmap.md`](doc/engineering/development-roadmap.md)、[`system/README.md`](system/README.md)
2. 进入 [`aris/README.md`](aris/README.md)，选择目标技术工作空间
3. 从 `release-0.2` 拉出技术分支：
   - `aris/t1-*`
   - `aris/t2-*`
   - `aris/t3-*`
4. 阅读该技术目录下的 `README.md`、`RESEARCH_BRIEF.md`、`ACCEPTANCE.md`
5. 只在该工作空间明确允许的路径内修改代码与文档

说明：

- 本仓库不 vendoring 上游 ARIS skill 代码，只提供本地适配层和稳定文档
- 不使用仓库根单一 `RESEARCH_BRIEF.md`
- 每次执行都从目标 `aris/tech-*` 工作空间进入，避免不同技术线互相覆盖

## 仓库结构

```text
cogguard_system/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── aris/
│   ├── README.md
│   ├── shared/
│   ├── tech-01-coordination/
│   ├── tech-02-propagation/
│   └── tech-03-risk/
├── doc/
│   ├── engineering/
│   │   ├── product-requirements.md
│   │   ├── project-map.md
│   │   ├── development-roadmap.md
│   │   ├── development-log.md
│   │   └── environment-setup.md
│   └── research/
│       ├── project-positioning-baseline.md
│       ├── literature-references.md
│       ├── time-series-forecasting-notes.md
│       └── key-technology-background/
├── system/
├── MediaCrawler-main/
├── NewsCrawler-main/
└── CooRTweet-master/
```

## 关键文档

- [`AGENTS.md`](AGENTS.md)：仓库级上下文、约束与主线叙事
- [`UBIQUITOUS_LANGUAGE.md`](UBIQUITOUS_LANGUAGE.md)：全局术语、别名与边界定义
- [`doc/engineering/system-governance.md`](doc/engineering/system-governance.md)：代码结构、命名与文档同步规则
- [`doc/engineering/project-map.md`](doc/engineering/project-map.md)：项目地图、目录边界与默认修改范围
- [`doc/engineering/development-roadmap.md`](doc/engineering/development-roadmap.md)：当前状态与优先级
- [`doc/research/key-technology-background/overview.md`](doc/research/key-technology-background/overview.md)：总技术背景
- [`aris/README.md`](aris/README.md)：ARIS 入口与工作流说明
- [`system/README.md`](system/README.md)：主线代码运行与接口说明
- [`../materials/README.md`](../materials/README.md)：竞赛材料目录说明（位于仓库外层）

## 参考边界

- `MediaCrawler-main/`：社交媒体采集参考与上游依赖
- `NewsCrawler-main/`：新闻提取参考与上游依赖
- `CooRTweet-master/`：协同检测方法参考

默认情况下，这三个目录不在当前实现范围内，除非任务明确要求修改。

## 许可证

本项目仅用于学术研究、教学演示和竞赛原型验证。
