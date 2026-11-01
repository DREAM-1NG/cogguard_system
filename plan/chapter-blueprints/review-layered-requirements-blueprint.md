# Risk Review Layered Requirements Blueprint

## Section 1
- Role: 文档目标
- Main claim: 本文档是 Risk Review harmfulness characterization 的正式分层需求基线。
- Evidence IDs: EV-01
- Contrast or transition: 从现有实验路线过渡到正式需求、方法路线与能力边界。
- Forbidden content: 空泛“将来可以做很多”式表述。

## Section 2
- Role: 问题边界
- Main claim: Risk Review 只负责 characterization 中的 harmfulness 维度，而非重新做 detect。
- Evidence IDs: EV-01
- Contrast or transition: 连接至帖子级、用户级、社区级三层任务划分。
- Forbidden content: 混淆 Coordination Discover/Propagation Analysis/Risk Review 边界。

## Section 3
- Role: 反特征工程的方法论原则
- Main claim: 帖子级、用户级、社区级都不应由手工特征工程主导，而应采用 representation-first、claim-conditioned、retrieval-aware、graph-native、evidence-aware 的路线。
- Evidence IDs: EV-02, EV-03, EV-07, EV-12, EV-21, EV-25, EV-35, EV-42
- Contrast or transition: 从“为什么不能这么做”转向“应该怎样建模”。
- Forbidden content: 用字段清单替代方法分析。

## Section 4
- Role: 分层总览
- Main claim: Risk Review 三层分别对应帖子语义节点、用户轨迹表示和社区 collective harm graph。
- Evidence IDs: EV-01, EV-21, EV-25, EV-35
- Contrast or transition: 为后续每层详细需求提供索引。
- Forbidden content: 把三层写成互不相关的功能模块。

## Section 5
- Role: 帖子级问题分析与方法设计
- Main claim: 帖子级是多模态、claim-conditioned、evidence-aware 的联合推理问题。
- Evidence IDs: EV-02 to EV-24, EV-53, EV-56, EV-57, EV-62
- Contrast or transition: 从 harmfulness、stance、fact verification 三条文献线汇合到实现闭环。
- Forbidden content: 把当前 prototype / similarity 脚手架写成已完成的训练模型。

## Section 5.3-5.6
- Role: 帖子级实现路线
- Main claim: 实现应以 claim extraction/linking、multimodal encoder、joint harm-stance head、evidence-aware abstention、teacher-student reviewer 闭环展开。
- Evidence IDs: EV-04, EV-06, EV-08, EV-09, EV-12 to EV-24, EV-53, EV-56, EV-57, EV-62, EV-63
- Contrast or transition: 将公开 benchmark、项目数据、Agent/RAG 复核分成三级迁移链。
- Forbidden content: 将 OCR/ASR/emoji 写成简单手工特征堆叠。

## Section 6
- Role: 用户级问题分析与方法设计
- Main claim: 用户级应建模 persistence、role、trajectory，而不是 automation heuristics。
- Evidence IDs: EV-25 to EV-34, EV-54, EV-58
- Contrast or transition: 从 user-centric hateful users 与 cyberbullying session 建模转向 post-to-user representation learning。
- Forbidden content: 仅罗列发帖频率、URL 多样性、automation score。

## Section 6.3-6.5
- Role: 用户级实现路线
- Main claim: 用户级应采用 MIL、hierarchical attention、temporal Transformer、GNN、label propagation 或 relation-aware aggregation 聚合帖子级语义。
- Evidence IDs: EV-26, EV-27, EV-30, EV-31, EV-32, EV-33, EV-34, EV-54, EV-58
- Contrast or transition: 强调行为统计量只能作为辅助上下文。
- Forbidden content: 把用户 harmfulness 定义成 harmful post ratio。

## Section 7
- Role: 社区级问题分析与方法设计
- Main claim: 社区级应建模 collective harm、coordinated amplification、target-centric attack 与 cross-platform campaign，而不是社区成员均值。
- Evidence IDs: EV-35 to EV-48, EV-55, EV-56, EV-57, EV-59
- Contrast or transition: 从 toxic conversation、harassment incitement、IO campaign、cross-platform CIB 汇合到 collective harm graph。
- Forbidden content: 平均分式社区风险叙述。

## Section 7.3-7.5
- Role: 社区级实现路线
- Main claim: 社区级应构造 account-post-claim-target-media-platform 异构动态图，并采用 HGT/Graph Transformer/TGN/GNN explanation 等图表示方法。
- Evidence IDs: EV-42, EV-43, EV-49, EV-50, EV-51, EV-52, EV-55, EV-57, EV-59
- Contrast or transition: 从文献问题定义落到可实现的图节点、边和输出。
- Forbidden content: 只列节点边字段而不解释为什么这样建模。

## Section 8
- Role: Agent / RAG 定位
- Main claim: Agent/RAG 适合作为 teacher、reviewer、verifier、reporter，不适合作为唯一底层分类器。
- Evidence IDs: EV-22, EV-23, EV-24, EV-60, EV-61, EV-62, EV-63
- Contrast or transition: 与 Risk Review 主体表示模型层解耦。
- Forbidden content: 夸大当前 Agent 能力，或把 MultiAgent 写成无需训练/评估的万能方案。

## Section 9-10
- Role: 实施顺序与当前能力边界
- Main claim: Risk Review 应按帖子级正式化、用户级聚合、社区级 harmfulness 的依赖顺序落地；当前代码可以声称已有帖子级语义脚手架、用户/社区运行时聚合、异构图导出和本地复核 executor，但不能声称已训练多模态模型、用户 encoder、图 encoder 或在线 Agent/RAG。
- Evidence IDs: EV-01, EV-21, local code inspection
- Contrast or transition: 把研究目标与当前代码边界清晰分离。
- Forbidden content: 把未来目标写成当前已实现能力。

## Section 12
- Role: 主参考文献清单
- Main claim: 参考文献应按任务层和方法层组织，区分主锚点、方法补充和前沿参考。
- Evidence IDs: EV-02 to EV-63
- Contrast or transition: 作为研发、实验和论文叙事的共同参考池。
- Forbidden content: 无解释地堆引用。
