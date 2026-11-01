# Risk Review PropagationTreeAgent 方法与开发计划

## 定界

本轮解决的是 `PropagationTreeAgent` 的输入证据不足问题：让它读取真实的社交媒体线程结构，并输出可审计的传播树复核报告。

本轮不解决：

- 不训练 GCN、HGT、Graph Transformer 或动态图模型。
- 不把传播树 Agent 的报告当成自动判别标签。
- 不把只有 claim 或 reaction count 的样本伪装成传播树样本。

成功标准：

- 本地 PHEME case 带有真实 `thread_context` 节点和边。
- 离线 Agent runner 将 `selected_tree_ids` 和 `review-propagation-context-v1` 传给 `PropagationTreeAgent`。
- 只有真实线程上下文或图边时才推荐 `PropagationTreeAgent`。
- 测试覆盖 thread 构建、上下文压缩和 claim-only 不触发传播树 Agent。

## 文献证据

| 方向 | 代表证据 | 可迁移方法 | Risk Review 采纳方式 |
| --- | --- | --- | --- |
| LLM 传播上下文裁剪 | [LeRuD: Can Large Language Models Detect Rumors on Social Media?](https://arxiv.org/abs/2402.03916) | 将冗长传播信息拆成 Chain-of-Propagation，降低 LLM 在大量评论中的注意力负担。 | 不把整棵树直接塞给 Agent，先生成 key branches、central nodes、temporal snapshots。 |
| 协作式 LLM + 社交上下文 | [Do not wait: Preemptive rumor detection with cooperative LLMs and accessible social context](https://www.sciencedirect.com/science/article/pii/S0306457324003546) | 用可访问社交上下文辅助早期研判，并服务 human decision-making。 | PropagationTreeAgent 输出“升级点”和“证据缺口”，不直接替代 Judge。 |
| 可解释 stance / evidence tree | [Stance Detection with Explanations](https://aclanthology.org/2024.cl-1.7/) | 构造 stance tree / evidence tree，并聚合支持、反驳、询问等证据。 | 在 `Propagation Context` 中保留 `stance_by_depth` 和 `Branch Evidence`。 |
| 反事实树状提示 | [Tree-of-Counterfactual Prompting for Zero-Shot Stance Detection](https://aclanthology.org/2024.acl-long.49/) | 将 stance 判断拆成树状反事实链和对比验证。 | 后续 prompt 可要求 Agent 针对关键分支提出“如果该回复为真/假会怎样”的反事实核验问题。 |
| 显式线程链接对 LLM 的价值 | [Leveraging Large Language Models to Identify Conversation Threads in Collaborative Learning](https://arxiv.org/abs/2510.22844) | 显式 thread linkages 能改善 LLM 对长对话结构的编码。 | `selected_tree_ids` 和 reply edges 成为一等输入；缺失时必须标记 evidence-limited。 |
| 线程辨析工程证据 | [A Large-Scale Corpus for Conversation Disentanglement](https://arxiv.org/abs/1810.11118) / [repo](https://github.com/jkkummerfeld/irc-disentanglement) | reply-structure graphs 是对话线程理解的基础数据结构。 | 以 node-edge `Thread Context` 表示传播线程，而不是只保存 reaction count。 |

## 方法论

### 数据表示

`Thread Context` 是源帖和回复/反应的原始树结构：

- `tree_id`
- `root_post_id`
- `nodes`
- `edges`
- `summary`

`Propagation Context` 是给 Agent 的压缩上下文：

- `tree_metrics`
- `central_nodes`
- `key_branches`
- `stance_by_depth`
- `temporal_snapshots`
- `evidence_nodes`
- `missing_fields`

### Agent 职责

`PropagationTreeAgent` 不做传播图分类。它只回答：

- 树结构是否足以支持传播研判？
- 哪些分支是关键证据？
- stance 是否随深度或时间发生变化？
- 是否存在异常放大或证据缺口？
- 哪些节点需要人工或后续 Agent 复核？

### 与 MARO 主链关系

这仍然符合 MARO 的“专家报告 -> 追问 -> Judge”主链：

- `PropagationTreeAgent` 是专家分析 Agent。
- `QuestionReflectionAgent` 读取其缺口和冲突。
- `HarmfulnessJudgeAgent` 综合内容、证据、传播结构和 policy 后给建议性裁决。

## 开发计划

已完成第一阶段：

- 新增 `app.core.review.propagation_context`。
- 新增 `app.core.review.propagation_agent`，集中管理 `PropagationTreeAgent` 的字段约束 prompt、输出契约、证据路由和 context selection。
- PHEME 转换写入 `thread_context`。
- 离线 Agent runner 在 case 存在真实 `tree_id` 时自动插入 `PropagationTreeAgent`。
- 离线 Agent runner 传入 `selected_tree_ids`。
- Agent context 优先读取 `review-propagation-context-v1`。
- 推荐逻辑不再把 claim-only 当成 propagation tree。
- 增加单元测试。

下一阶段建议：

- 在 teacher silver 中记录 `propagation_trace_refs` 和 `escalation_points`。
- 对 PHEME 跑一个 1-2 case 的 GPT smoke，确认报告正文不再自由臆测传播树。
