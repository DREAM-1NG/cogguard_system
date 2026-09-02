# Final Architecture Cleanup Plan

## Ordered Tasks

1. 恢复绿色基线：修复传播参数、传播 evidence refs、角色依赖和失效 Student alias。
2. 整理发布表面：停止跟踪生成物，收口 frontend-sandbox，归档 placeholder，统一依赖源。
3. 深化 Propagation Monitoring module。
4. 折叠 Coordination facades，拆分 reproduction 与 registry 巨型文件。
5. 统一 XLM-R Student Review runtime、training package 和 checkpoint governance。
6. 以 `AnalysisStageContext` + `AnalysisStagePort.execute` 深化 Analysis Run seam。
7. 统一 glossary、CONTEXT、ADR、governance、roadmap、development log 和 README。
8. 执行完整验证、最终 code review、推送分支并创建 PR。

## Commit Sequence

- `fix: restore release baseline contracts`
- `chore: establish a clean release surface`
- `refactor: deepen propagation monitoring`
- `refactor: collapse coordination facades`
- `refactor: unify the review student runtime`
- `refactor: consolidate analysis stage adapters`
- `docs: align architecture and domain language`

每个任务先写失败测试、确认红灯、实现最小改动、运行目标与邻近测试、复核 diff，再提交。远端引入的 ADR 0007 至 0009 已迁入 canonical `doc/adr/` 并保留编号；新的 Student Review 决策使用 `doc/adr/0010-review-student-runtime-and-distillation.md` 并 supersede ADR-0004。
