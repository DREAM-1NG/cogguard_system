# ARIS 工作空间入口

`aris/` 是本仓库的执行工作空间层，负责把三条关键技术拆成可独立运行的 ARIS 任务。它不是产品代码目录，也不是上游 skill 仓库镜像。

## 1. 怎么选择技术线

| 技术线 | 目录 | 目标 |
|------|------|------|
| 关键技术一 | [`tech-01-coordination/`](tech-01-coordination/README.md) | 多行为协同网络构建与显著性筛查 |
| 关键技术二 | [`tech-02-propagation/`](tech-02-propagation/README.md) | 传播证据链、关键路径与角色解释 |
| 关键技术三 | [`tech-03-risk/`](tech-03-risk/README.md) | 报告研判 MVP、DISARM 映射与结构化报告 |

对应背景文档：

- [`../doc/research/key-technology-background/coordination-detection.md`](../doc/research/key-technology-background/coordination-detection.md)
- [`../doc/research/key-technology-background/propagation-analysis.md`](../doc/research/key-technology-background/propagation-analysis.md)
- [`../doc/research/key-technology-background/risk-disarm.md`](../doc/research/key-technology-background/risk-disarm.md)

## 2. 分支约定

每条技术线单独起分支，统一从 `release-0.2` 出发：

- `aris/t1-*`
- `aris/t2-*`
- `aris/t3-*`

不要从 `main` 起分支，也不要在一个分支里混做多条技术线。

## 3. 启动顺序

1. 读根 `AGENTS.md`
2. 读 `doc/engineering/development-roadmap.md`
3. 读目标 `tech-*/README.md`
4. 读目标 `tech-*/RESEARCH_BRIEF.md`
5. 读目标 `tech-*/ACCEPTANCE.md`
6. 按 `shared/RUNNERS.md` 选择 Claude Code 或 Codex 路径

## 4. 本仓不做的事情

- 不把上游 ARIS skill 代码复制进本仓
- 不在仓库根创建单一 `RESEARCH_BRIEF.md`
- 不把不同技术线的实验日志混到同一个目录

## 5. 哪些文件会提交

会提交：

- `README.md`
- `RESEARCH_BRIEF.md`
- `EXPERIMENT_PLAN.md`
- `TASK_TRACKER.md`
- `ACCEPTANCE.md`
- 实际代码改动和必要文档改动

默认不提交：

- `outputs/`
- `logs/`
- `refine-logs/`
- `.cache/`
- `scratch/`

具体策略见 [`shared/ARTIFACT_POLICY.md`](shared/ARTIFACT_POLICY.md)。

## 6. 共享文档

- [`shared/RUNNERS.md`](shared/RUNNERS.md)：Claude Code / Codex 运行方式
- [`shared/GPU_SETUP_TEMPLATE.md`](shared/GPU_SETUP_TEMPLATE.md)：远端 GPU 配置模板
- [`shared/ARTIFACT_POLICY.md`](shared/ARTIFACT_POLICY.md)：产物入库策略
- [`shared/REVIEW_CHECKLIST.md`](shared/REVIEW_CHECKLIST.md)：实现与评审清单
