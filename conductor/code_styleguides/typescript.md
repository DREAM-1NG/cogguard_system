# TypeScript Style Guide

- 开启并保持现有严格类型检查，不引入隐式 `any`。
- HTTP 类型集中在 canonical `src/api/`，页面不复制 wire contract。
- 页面保持现有路由和响应兼容；异步请求必须防止旧响应覆盖新状态。
- ECharts 使用显式 `ECharts` / `EChartsOption` 类型。
- 响应式布局遵循现有 Ant Design Vue 和断点约定。
