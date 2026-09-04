# 技术线 01：跨平台协同发现（共同行为特征复用融合检测）

## 目标

把当前"共享对象协同检测"升级为事件窗口内的多关系协同图，并进一步发展为 **GNN + LM 增强的协同社区构建与发现方法**。

> 方向更新（2026-06-02）：Coordination Discover 是核心关键技术，定位为 **跨平台协同发现——只用平台无关的"共同行为特征"做复用融合检测，内容检测不作为协同信号**。
> - 协同信号只取行为特征：时间同步/共现、共享对象（URL/hashtag/媒体指纹 id）、共转发与回复级联、账号行为节律等。
> - **排除内容型判据**（立场、毒性、图文一致/视频-语义 mismatch）直接作为协同边证据；但允许 LM 用于共享对象归一、节点/社区表征、Node Selection 后的 LLM annotation 和解释。
> - 方法升级：网络科学方法保留为 baseline 和解释审计；主方法应发展为 LM 表征 + 多关系 GNN 消息传递 + 社区发现/区分。

## 研究任务定位

Coordination Discover 的正式研究任务定义为两阶段的 **协同发现 -> 协同区分**：

1. **协同发现（coordination discovery）**：使用平台无关的共同行为信号构建多关系协同图，并结合 LM 表征与 GNN 消息传递发现协同账号簇、关键账号对和关键共享对象。该阶段不要求负样本，不把任务强行转写为账号二分类，核心目标是形成可解释的协同网络和社区表示。
2. **协同区分（coordination discrimination）**：在有 IO/control 或 coordinated/organic 标签的数据集上，检验第一阶段发现的协同图、边权、社区和结构表征是否能够区分自发行为与协同攻击。该阶段主表报告 AUPRC、Precision@K、Recall@K、MaxF1 等检测指标；固定阈值 F1@0.5 只保留为调试诊断，不进入论文主表。

因此，Coordination Discover 的主任务不是 bot detection、troll classification 或 fake news classification；这些方向只作为辅助表征或下游对照。主领域是 coordinated online behavior / information operations detection。

## 必读文档

- [`../../AGENTS.md`](../../AGENTS.md)
- [`../../doc/engineering/development-roadmap.md`](../../doc/engineering/development-roadmap.md)
- [`../../doc/research/key-technology-background/coordination-detection.md`](../../doc/research/key-technology-background/coordination-detection.md)
- [`../../new-system/README.md`](../../new-system/README.md)
- [`ACCEPTANCE.md`](ACCEPTANCE.md)
- [`GNN_LM_METHOD.md`](GNN_LM_METHOD.md)

## 建议分支

- `aris/t1-multi-behavior-coordination`
- `aris/t1-significance-filter`

都必须从 `release-0.2` 起分支。

## 允许修改路径

- `../../new-system/backend/app/core/coordination/`
- `../../new-system/backend/app/services/coordination_service.py`
- `../../new-system/backend/app/api/v1/coordination.py`
- `../../new-system/backend/tests/`
- `../../new-system/frontend/src/api/coordination.ts`
- `../../new-system/frontend/src/views/coordination/index.vue`
- 本目录下的稳定 Markdown

说明：

- 前端只允许做与返回结构直接相关的最小改动
- 如果发现需要更大范围改动，应先回写 `TASK_TRACKER.md` 并重新确认

## 禁止修改路径

- `../../MediaCrawler-main/`
- `../../NewsCrawler-main/`
- `../../CooRTweet-master/`
- `../../new-system/backend/app/core/propagation.py`
- `../../new-system/backend/app/core/account_profiler.py`
- `../../new-system/backend/app/core/risk/`（当前不存在，也不属于本技术线）

## 本轮预期交付

- 共同行为边构建：时间同步、共链接、共媒体（按指纹/id，不读内容）、共转发与回复级联、行为节律（**不含语义近似等内容型信号**）
- LM 增强的共享对象归一、节点/社区表征和高影响节点标注
- 多关系 GNN/learnable relation attention 融合后的账号协调图
- 自然共振 vs 人为协同的显著性筛查（PSL：对称超几何 + Cauchy + pair-level BH-FDR）
- 更强的证据样本输出
- 对应测试与必要文档同步

## 目标测试

- `new-system/backend/tests/` 下的协同检测相关单元/服务测试
- 回归已有采集与健康检查测试时不引入破坏
- 如果响应结构变化，最小检查 `coordination` 前端页面可继续消费

## 成功标准

- 后端能够在现有输入上输出多行为协同结果
- 显著性筛查可配置且可解释
- 返回结果能指出主要边类型和证据样本
- 相关实现和文档都限制在本技术线允许范围内
