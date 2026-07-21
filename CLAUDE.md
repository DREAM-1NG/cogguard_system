# CLAUDE.md

本仓库将”产品代码”和”ARIS 执行工作空间”分离管理。

## Session Startup (< 2 分钟)

> Harness Engineering 原则: Maps over manuals. 先读地图，再读细节。

**每次新会话的读取顺序**:
1. `memory/PLAYBOOK.md` — 全局视图 + 当前 Harness Window（60s）
2. `memory/state_<workspace>.md`（仅目标工作流）— 文件路径 + 阻塞点（30s）
3. 本文件 — 仓库规则确认（20s）
4. `aris/tech-N-*/ACCEPTANCE.md` — 范围边界确认（20s）
5. `aris/tech-N-*/TASK_TRACKER.md` — 接续上次进度（10s）
6. `UBIQUITOUS_LANGUAGE.md` 与 `doc/engineering/system-governance.md` — 全局术语与代码治理确认（20s）

**不需要读**: research-wiki/（除非做文献工作）、其他工作流的文件

## Harness Window Protocol

每次自主执行前，在 `memory/PLAYBOOK.md` 的 Active Harness Window 区域定义：

```
scope: [workspace / work-package 具体任务]
success_criteria: [可验证的完成标准]
time_boundary: [预计时长，ARIS 标准：6-7 小时/窗口]
checkpoint_at: [中间检查点]
human_review_trigger: [触发人工介入的条件]
out_of_scope: [明确排除的内容]
```

**人工介入触发器**（预定义，不临时决定）:
- 范围边界命中（ACCEPTANCE.md 明确禁止）
- 需要架构决策的阻塞点
- 测试失败率 > 30% 且 2 次修复尝试后仍失败
- 任何跨工作流依赖变更（参考 `aris/shared/CROSS_KT_DEPS.md`）

## 必读顺序

1. `AGENTS.md`
2. `doc/engineering/development-roadmap.md`
3. `doc/engineering/development-log.md`
4. `system/README.md`
5. `aris/README.md`
6. `UBIQUITOUS_LANGUAGE.md`
7. `doc/engineering/system-governance.md`
8. 如果任务属于三个工作流之一或由 ARIS 驱动，继续读取：
   - 目标 `aris/tech-*/README.md`
   - 目标 `aris/tech-*/ACCEPTANCE.md`
   - 对应 `doc/research/key-technology-background/*.md`

## 仓库规则

- 当前工程基线：`release-0.2`
- 当前唯一产品代码根：`system/`
- `Coordination Discover` + `Coordination Detect` 是正式方法名
- 参考仓库边界：`MediaCrawler-main/`、`NewsCrawler-main/`、`CooRTweet-master/`
- 不在仓库内 vendoring 上游 ARIS skill 实现
- 不创建仓库根单一 `RESEARCH_BRIEF.md`
- 稳定 Markdown 和实际代码可以提交；`outputs/`、`logs/`、`refine-logs/` 等实验产物只保留本地
- 每次完成代码变更后都要执行 **Documentation Sync**，同步更新受影响的文档、术语表或 ADR，避免代码与治理说明失配

## ARIS 执行约定

- Claude Code 与 Codex 都使用本仓库的 `aris/` 工作空间文档
- 每条技术线单独起分支：
  - `aris/t1-*`
  - `aris/t2-*`
  - `aris/t3-*`
- 每次从目标 `aris/tech-*` 工作空间进入，不跨技术线混用 brief、plan、tracker
- 如果任务已经有 `ACCEPTANCE.md`，实现范围以其中“允许修改路径 / 禁止修改路径”为准
