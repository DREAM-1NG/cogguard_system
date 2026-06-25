# KT2 / F-PROP 传播监控完成计划

> 更新时间：2026-06-26  
> 当前阶段：`request.md` 研究复现与数据集验证闭环已完成，系统落地后置。

## 当前判断

当前仓库已经完成 `request.md` 要求的研究对齐、协议修正、可运行 baseline、主复现目标 protocol-level reproduction、公开数据集验证和文档同步。规模预测与下一节点预测仍应标记为研究/离线 baseline，不应写成产品级 KT2 核心功能完成。

本轮路线从原 CascadeSwitch 设想收敛为：

1. 以 HyperIDP 作为唯一主复现目标。
2. 以 MINDS / FOREST 作为可运行统一多尺度 baseline。
3. 保留 RandomForestRegressor 和 LogisticRegression 作为传统 baseline。
4. 在进入产品 API 和前端展示前，先完成无泄漏协议与完整训练对比。

## 与 CascadeSwitch 的关系

CascadeSwitch 暂不作为本轮主实现。若后续恢复该路线，LLM 或事件抽取模块应作为外生上下文/事件阶段特征抽取器，而不是直接输出传播规模数值。

替代路线的关系：

| 原设计关注点 | 当前替代实现 | 缺口 |
|---|---|---|
| 事件条件体制切换 | HyperIDP/MINDS temporal hypergraph 协议参照 | 尚未显式建模 seeding/amplification/peak/decay |
| 规模预测 | TemporalSizeBaseline + RF baseline + MINDS macro MSLE + HyperIDP protocol/adversarial proxy | 已有简单时间外推 baseline；MINDS Christianity 已完成 30 epochs；HyperIDP proxy 已产出 douban macro/micro 联合指标与 t_obs 曲线；douban/android 数据仍待补齐 |
| 下一节点预测 | ProspectiveRanker + ProspectiveHeuristic + LR observed-candidate baseline + FOREST/MINDS micro metrics + HyperIDP protocol/adversarial proxy | 已有严格前瞻浅层学习排序 baseline；HyperIDP proxy 已补 temporal hyperedge proxy 和 adversarial multi-task proxy；MINDS Christianity 已完成 30 epochs；FOREST 仍缺完整长训，强 temporal graph/GNN 排序模型仍待补 |
| 系统解释 | 已观测图角色和证据链 | 与协同检测结果的联动接口需固化 |

## 分阶段计划

| 阶段 | 目标 | 交付物 | 完成标准 |
|---|---|---|---|
| P0 | 固化当前 baseline 与文档口径 | `benchmark/`、`REPRODUCTION_REPORT.md`、状态矩阵 | RF/LR/Temporal/Prospective/MINDS/FOREST 均有可复现实验记录，并明确泄漏边界 |
| P1 | 完整训练可运行 baseline | MINDS 30 epochs、FOREST 可选 30 epochs、固定时间窗规模预测对照 | MINDS Christianity 已完成；FOREST 完整训练和 MINDS douban/android 需数据/算力继续补齐 |
| P2 | prospective next-hop 协议 | 候选生成、Candidate Recall、Hits/MAP/MRR/NDCG | 已完成非学习和浅层学习排序 sanity baseline；下一步增强特征或接入 temporal graph/GNN |
| P3 | HyperIDP protocol-level 模型 | temporal hypergraph + adversarial/macro-micro loss 最小复现 | 已完成 douban temporal coactivation hyperedge proxy、gradient-reversal adversarial proxy 与 t_obs 曲线；剩余为 NAS 或官方实现 |
| P4 | 系统集成 | 预测 API、dashboard/前端展示口径 | 仅展示已验证能力，未完成能力带实验标签 |

## 当前禁止项

- 不把 LR 离线边分类 AUC/AP 写成线上下一节点预测完成。
- 不把 ProspectiveHeuristic 写成最终模型；它只是无泄漏协议和候选覆盖/排序拆分的 sanity baseline。
- 不把按最终序列比例切分的 RF 结果当成唯一规模预测证据；固定时间窗 baseline 应作为更接近早期预警的最低对照。
- 不把 FOREST 1 epoch sanity run 写成论文复现结果；MINDS Christianity 30 epochs 可作为当前完整训练 baseline，但不代表 douban/android 已完成。
- 不把 HyperIDPProtocolProxy / HyperIDPAdversarialProxy 写成 HyperIDP 论文架构复现；它们只证明 macro/micro 协议支架、temporal hyperedge proxy 和 adversarial multi-task 代理可运行。
- 不把 HyperIDP 预设为最终落地模型；当前只是主复现目标。
