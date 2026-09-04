# Product Guidelines

## Language

- 产品叙事使用 `事件 -> 证据 -> 协同 -> 传播 -> 风险 -> 处置`。
- 领域术语以 `UBIQUITOUS_LANGUAGE.md` 为全局事实源，`CONTEXT.md` 只补充上下文专用术语。
- 使用 **Coordination Discover**、**Coordination Detect**、**Propagation Monitoring**、**Review Advisory**、**Confirmed Decision** 和 **Event Review Case**；Student Review 与 Teacher Review 仅用于内部 runtime/research 文档。
- 禁止用编号技术、`risk shortcut`、`prediction blob`、`final model output` 替代 canonical 术语。

## User-Facing Behavior

- 观察事实、模型预测和人工决定必须清楚区分。
- 缺少批准 checkpoint、校准或证据时返回明确 `abstain`/不可用状态，不生成看似成功的结果。
- Teacher Review 和 Student Review 均不能直接生成 Canonical Verdict。
- 错误信息说明可恢复动作，不暴露密钥、内部路径或模型供应商凭据。

## Documentation

- 行为、环境变量、依赖或启动方式变化必须同步运行文档。
- package ownership 或长期 interface 变化必须同步治理文档和 ADR。
- 完成状态只能在验证命令成功后写入 roadmap、development log 和 track。
