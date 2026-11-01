# Final Architecture Cleanup Specification

## Goal

在保持现有 V1/V2 HTTP 路径和响应兼容的前提下，将 CogGuard 整理为可测试、可导航、可发布的 Product System，并从 `cleanup/final-architecture` 向 `release-0.2` 创建 PR。

## Required Outcomes

- 后端完整测试零失败，前端 production build 成功。
- 运行输出、缓存、截图、placeholder 和重复前端树不进入 PR。
- Propagation Monitoring 由 HTTP 与 Celery adapters 共享一个 deep module interface。
- Coordination canonical facades 直达 implementation，兼容路径只单跳转发。
- Student Review 以 XLM-R 多头分类、latent rationale distillation 和外部不确定性路由为主线。
- Analysis Run stages 通过单一 stage interface 注册和执行。
- 领域词汇、ADR、project map、governance、roadmap 和运行文档一致。

## Compatibility

- 保留已有 V1 capability 页面和 V2 Analysis/Event Review Case 路径。
- Coordination compatibility alias 保留到下一版本。
- 已失效且无调用者的 `selective_student` alias 不恢复。
- 缺少批准 Student checkpoint 时必须返回 `shadow_untrained` 与 `abstain`，不得随机初始化后给出产品判断。

## Non-Goals

- 不新增产品功能。
- 不完成模型训练或研究 claim。
- 不重写 Git 历史，不自动合并 PR。
- 不处理现有前端大 chunk 性能警告。
