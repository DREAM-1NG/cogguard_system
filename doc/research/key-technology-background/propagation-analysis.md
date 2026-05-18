# 关键技术二：传播归因与关键角色识别

> **用途**：定义 KT2 的研究问题、当前工程落点、研究目标、实现方向和验证方式。  
> **受众**：KT2 研究实现者、传播归因/趋势预测模块维护者。  
> **维护规则**：只写关键技术背景与研究方案；产品接口和任务状态放入 `../../engineering/`。

## 1. 问题定义

当前系统已经可以从帖子集合中构建传播子图、重建时间线并识别关键角色，但还缺少开题报告中强调的“证据链”和“关键路径”层。

这条技术线的目标不是单纯画一张传播图，而是回答：

- 这条叙事是怎么扩散的
- 谁是起爆、桥接、扩散节点
- 哪条路径最值得人工复核
- 哪些 claim / thread 应该进入风险研判

## 2. 当前代码基线

当前代码落点：

- `new-system/backend/app/core/propagation.py`
- `new-system/backend/app/services/propagation_service.py`
- `new-system/backend/app/api/v1/propagation.py`

当前已实现：

- 传播子图构建
- 传播时间线重建
- 关键角色识别
- 高危 claim / thread 排序

当前未实现：

- 传播证据链生成
- 关键路径提取与解释
- 更系统的显式边 / 隐式边区分

## 3. 这一技术线要解决的核心问题

- 如何从已有帖子集合中提炼“最有解释力的路径”
- 如何把显式互动边与隐式传播边区分建模
- 如何把角色输出和证据链输出对齐，而不是两个平行结果

## 4. 推荐实现方向

- 继续沿用轻量图分析路线，先补结构化证据链
- 显式边优先支持回复、转发、引用、提及
- 隐式边优先支持时序接近、语义承接、资源复用
- 输出格式优先面向风险研判消费，而不是面向论文式中间表示

## 5. 推荐验证方式

- 用 `mock_weibo` 验证时间线和路径输出的稳定性
- 用真实 `weibo`/`news` 样例验证角色排序是否可解释
- 在服务层补回归测试，验证新增证据链字段不破坏现有响应

## 6. 参考文献线索

- `Temporally Evolving Graph Neural Network for Fake News Detection` (IPM 2021)
- `Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks` (AAAI 2020)
- `A Weakly Supervised Propagation Model for Rumor Verification and Stance Detection with Multiple Instance Learning` (SIGIR 2022)
- `Filter-based Stance Network for Rumor Verification` (TOIS 2024)
