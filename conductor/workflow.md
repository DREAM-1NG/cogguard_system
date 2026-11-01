# Workflow

## Development Method

1. 读取 Conductor、`AGENTS.md`、工程治理和相关 ADR。
2. 为行为变化先写失败测试并确认失败原因。
3. 实现最小改动，运行目标测试，再运行受影响测试集。
4. 每个 track task 使用独立便宜 subagent；主代理复核 diff、测试证据和范围。
5. Critical/Important review findings 修复并复审后才能进入下一任务。

## Git

- 工作分支：`cleanup/final-architecture`
- 目标分支：`release-0.2`
- 禁止 force push 和历史重写。
- 每个架构阶段独立提交；对应测试和文档与实现同提交。
- 生成物从索引停止跟踪，但不清除既有 Git 历史。

## Quality Gates

- 目标 pytest 测试先红后绿。
- 完整后端测试零失败；环境依赖项只能以明确原因 skip。
- 前端 `npm run build` 成功。
- `git diff --check` 无输出。
- `alembic heads` 只有一个 head。
- public package 明确 `__all__`，产品源码不新增 `sys.path.insert`。
- PR 前执行全分支 code review。

## Completion

只有代码、测试、文档、迁移、发布表面和 PR 描述全部通过门禁后，track 才能标记完成。PR 创建后不自动合并。
