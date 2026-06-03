# 关键技术一：跨平台协同发现（共同行为特征复用融合检测）

> **用途**：定义 KT1 的研究问题、当前工程落点、研究目标、实现方向和验证方式。  
> **受众**：KT1 研究实现者、协同检测模块维护者。  
> **维护规则**：只写关键技术背景与研究方案；产品接口和任务状态放入 `../../engineering/`。

> 方向更新（2026-06-02）：KT1 是本项目核心关键技术。最新定位为 **跨平台协同发现——利用平台无关的“共同行为特征”做复用融合检测；具体的内容检测不作为协同发现的信号**。
> 立论：现有 CIB 检测文献大多依赖特定协同信号（cotweet/retweet/cofollow/time burst）；面向抖音等多媒体平台又提出更专用的内容型信号（如视频-语义 mismatch），这类内容信号平台特定、易被生成式 AI 改写、跨平台迁移成本高。KT1 转而只用各平台共有、可迁移的行为特征作为协同判据。

## 1. 问题定义

在事件窗口内，识别一组在该窗口内共同推动某叙事的账号集合（协同群体），并输出可解释的协同边与证据样本。核心原则：**协同判定只看“行为是否同步”，不看“内容说了什么”**。内容理解（立场/危害/图文一致）单向下沉到下游 KT2/KT3，绝不回流作为协同信号。

要补齐的能力：

- 多种共同行为信号的统一建模与融合（时间同步、共享对象、共转发级联、行为节律等）
- 自然共振 vs 人为协同的显著性筛查（抑制热门话题误报）
- 可解释的边类型与证据样本输出
- 跨平台/跨源的信号可复用性

## 2. 当前代码基线

当前代码落点：

- `new-system/backend/app/core/coordination/`（`detector.py` / `network.py` / `stats.py`）
- `new-system/backend/app/services/coordination_service.py`
- `new-system/backend/app/api/v1/coordination.py`

当前已实现（真实可运行）：

- 共享对象 + 时间窗配对（CooRTweet 重写，`detector.py`）
- 加权无向图 + 百分位阈值（`network.py`）
- 账户级 / 群体级统计、社区发现、网络序列化与前端可视化

当前未实现（设计稿，0 行代码）：

- **PSL（Pair Surprisal Layer）显著性筛查**：对称超几何 + Cauchy combination + pair-level BH-FDR（`significance.py` 不存在）
- 多行为通道抽取与融合（`channels.py` 不存在）
- 语义通道（`semantic.py` 不存在）——**注意：文本语义相似度属“内容理解”，与“排除内容信号”的新定位冲突，应移出 Detection 或仅以行为型模板指纹替代**

## 3. 这一技术线要解决的核心问题

- 哪些行为特征是跨平台可复用的（不依赖单平台特有机制、不依赖读懂内容）
- 如何把不同类型的行为协同边统一投影到账号协调图并融合
- 如何用显著性筛查区分自然共振与人为协同
- 如何输出可解释的边类型证据，而不只是一个黑盒分数

## 4. 推荐实现方向

- 协同信号只取“共同行为特征”：时间同步/共现、共享对象（URL/hashtag/媒体指纹 id）、共转发与回复级联、账号行为节律、共参与模式等
- 行为 vs 内容的边界判据：是否需要“理解内容说了什么”。共享同一媒体对象（按 id/指纹）= 行为；分析视频内容/字幕 mismatch/文本立场/毒性 = 内容（排除）
- 保持 pandas/numpy/networkx 轻量路线，优先落地 `significance.py` 的对称超几何 + BH-FDR（纯统计、不含语义），把核心从“设计”变“已验证”
- 映射到 Mannocci 2024 综述的 Detection + Characterization 两阶段：行为同步 = Detection（KT1 核心）；内容/毒性/立场 = Characterization 或下游 KT2/KT3
- 表述纪律：“跨平台”当前仅验证 mock_weibo/weibo/news（跨源，非跨平台身份解析），对外应表述为“平台无关的行为信号设计 + 跨源验证”，并坦白单平台上排除内容信号是鲁棒性 tradeoff（可能略损召回，换取可迁移性与抗 AI 改写）

## 5. 推荐验证方式

- `mock_weibo`：验证行为边拼接、统计逻辑和回归测试
- `weibo`：验证真实采集样例上的误报/漏报模式（热门话题压力测试）
- `news`：验证跨源场景下共享链接与资源复用信号

建议重点补充：

- 共同行为边构建的单元测试
- 显著性筛查的回归测试
- 响应结构变更时的最小前端兼容检查

## 6. 文献线索（注意核实，旧表中部分条目 venue/方法有误）

- Mannocci et al. *Detection and Characterization of Coordinated Online Behavior: A Survey* (arXiv 2408.01257, 2024) — Detection/Characterization 框架
- Luceri et al. *CIB on TikTok* (arXiv 2505.10867, 2025) — 行为型信号可迁移、内容型不可迁移的实证
- Schneider, Yuan, Rizoiu *Beyond Content* (arXiv 2602.02838, 2026) — platform-agnostic 行为 policy，最接近的先前工作（KT1 须明确差异，勿当原创首发）
- CooRTweet（共享对象配对，工程基线来源）
- Cinus/Minici/Luceri/Ferrara *Exposing Cross-Platform CIB* (arXiv 2410.22716, 2024)
