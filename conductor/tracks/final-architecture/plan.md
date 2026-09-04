# Final Architecture Cleanup Plan

## Ordered Tasks

- [x] 恢复绿色基线：修复传播参数、传播 evidence refs、角色依赖和失效 Student alias。
- [x] 整理发布表面：停止跟踪生成物，收口 frontend-sandbox，归档 placeholder，统一依赖源。
- [x] 深化 Propagation Monitoring module。
- [x] 折叠 Coordination facades，拆分 reproduction 与 registry 巨型文件。
- [x] 统一 XLM-R Student Review runtime、training package 和 checkpoint governance。
- [x] 以 `AnalysisStageContext` + `AnalysisStagePort.execute` 深化 Analysis Run seam。
- [x] 统一 glossary、CONTEXT、ADR、governance、roadmap、development log 和 README。
- [x] 执行首轮完整验证与最终 branch review。
- [x] 清除 `MediaCrawler-main/data_runs/` 与生成诊断报告等发布泄露，并扩展 release guard。
- [x] 将 Student checkpoint 与 canonical manifest 绑定为同一可验证制品，并补齐不可伪造的激活指标输入契约。
- [x] 修复 Propagation Monitoring snapshot 可重建性、内容寻址、并发 claim、告警唯一性和状态转换。
- [x] 在成功 crawl/import 变更后失效 observed propagation cache。
- [x] 修复 Propagation 与 Coordination 页面在快速切换 scope/dataset 时的陈旧响应覆盖。
- [x] 运行完整验证和 Alembic smoke，完成第二轮 branch review。
- [x] 推送分支并创建 PR；不自动合并。

## Commit Sequence

- `fix: restore release baseline contracts`
- `chore: establish a clean release surface`
- `refactor: deepen propagation monitoring`
- `refactor: collapse coordination facades`
- `refactor: unify the review student runtime`
- `refactor: consolidate analysis stage adapters`
- `docs: align architecture and domain language`

每个任务先写失败测试、确认红灯、实现最小改动、运行目标与邻近测试、复核 diff，再提交。远端引入的 ADR 0007 至 0009 已迁入 canonical `doc/adr/` 并保留编号；新的 Student Review 决策使用 `doc/adr/0010-review-student-runtime-and-distillation.md` 并 supersede ADR-0004。
