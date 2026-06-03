# 关键技术二：传播监测与关键角色识别

> **用途**：定义 KT2 的研究问题、当前工程落点、研究目标、实现方向和验证方式。  
> **受众**：KT2 研究实现者、传播归因/趋势预测模块维护者。  
> **维护规则**：只写关键技术背景与研究方案；产品接口和任务状态放入 `../../engineering/`。

> 方向更新（2026-06-02）：KT2 关键技术定位为 **LLM + 时序预测**，核心任务从“传播归因/画一张传播图”转为 **传播趋势预测**——预测事件规模与传播走向。功能层借鉴“知微”(Zhiwei) 商业传播分析产品的呈现形态；已有的传播子图 / 时间线 / 关键角色 / 证据链作为“源头追溯与范围估计”子功能保留。

## 1. 问题定义

KT2 要回答的核心问题不是“这条叙事长什么样”，而是 **“这条叙事接下来会怎么扩散、会扩散到多大”**。围绕一个已识别的协同攻击事件及其早期传播数据：

- **事件规模预测**：给定早期观测窗口 [0, t_obs]，预测 t_pred 时刻的最终级联规模（转发/传播量）+ 方向 + 置信区间（关键技术，已落地）
- **传播态势刻画**：传播子图、时间线、起爆/桥接/扩散关键角色（子功能，已落地）
- **源头追溯与证据链**：claim 源头、关键路径回溯、支撑帖子（子功能，已落地）
- **传播路径预测**：预测未来下一跳/路径结构（**功能创新方向，当前未落地，仅有已观测图上的路径回溯/取证，不是预测**）
- **立场检测 / 危害性评估**：内容层子功能（**未落地；按闭环分工，内容分析统一归 KT3，KT2 是否承载待与 KT3 切分**）

## 2. 当前代码基线

当前代码落点：

- `new-system/backend/app/core/propagation/`：`ts_features.py` / `llm_context.py` / `regime_model.py` / `trend_predictor.py`（CascadeSwitch 趋势预测，WP1-3）
- `new-system/backend/app/core/propagation_legacy.py`：源头追溯 + 证据链 + 关键路径（MultiDiGraph，子功能保留）
- `new-system/backend/app/services/propagation_service.py`
- `new-system/backend/app/api/v1/propagation.py`

当前已实现：

- 时序特征提取（volume / velocity / acceleration / burst_zscore）
- 事件条件体制切换级联规模预测（CascadeSwitch：4 体制混合预测 + 置信区间 + 解释）
- 传播子图、时间线、关键角色、证据链、关键路径回溯（legacy 子功能）

当前未实现 / 需注意：

- **传播路径预测**（未来结构预测）——尚无设计与代码，对外表述须区分“路径预测”与已落地的“路径回溯/取证”
- 在线 LLM 事件提取尚未接通（`propagation_service.py` 趋势预测当前走 `mock_llm=True`，`pyproject.toml` 缺 LLM 客户端依赖）
- 评估脚本与公开数据集基准（DeepHawkes/CasFlow）未落地，“超越基线”暂无实证
- 立场检测 / 危害性评估子功能未启动

## 3. 这一技术线要解决的核心问题

- 如何在非平稳（受外生事件驱动发生体制转换）的级联上做可解释、零训练的规模前瞻预测
- LLM 如何作为“事件抽取器”增强时序预测，而非不可靠的数值预测器
- 如何借鉴知微的产品形态（功能/可视化）而不沦为“抄产品”——差异化锚在方法层（CascadeSwitch 可计算后验、可解释、自带预测能力，知微以事后分析为主）

## 4. 推荐实现方向

- 关键技术 = 事件条件体制切换（CascadeSwitch）：时序特征 + LLM/级联形态事件检测 + 4 体制 softmax 后验混合预测，零训练、白盒、带置信区间
- 优先接通真实 LLM 事件提取并补基准实验数值，把“方法设计”坐实为“已验证”
- “传播路径预测”若要成为关键技术，需补未来结构预测的设计与数据；否则诚实表述为“路径回溯/取证（事后）+ 规模预测（事前）”
- 输出格式优先面向 KT3 报告研判消费

## 5. 推荐验证方式

- 用 `mock_weibo` 验证时间线和路径输出的稳定性
- 用真实 `weibo`/`news` 样例验证角色排序是否可解释
- 在服务层补回归测试，验证新增证据链字段不破坏现有响应

## 6. 参考文献线索

- `Temporally Evolving Graph Neural Network for Fake News Detection` (IPM 2021)
- `Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks` (AAAI 2020)
- `A Weakly Supervised Propagation Model for Rumor Verification and Stance Detection with Multiple Instance Learning` (SIGIR 2022)
- `Filter-based Stance Network for Rumor Verification` (TOIS 2024)
