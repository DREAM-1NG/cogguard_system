# 技术相关高水平论文检索与引用记录

> **用途**：统一记录可直接引用的论文、出处、CCF/DOI 信息和与三条关键技术的关系。  
> **受众**：研究撰写者、开题/答辩材料撰写者、关键技术实现者。  
> **维护规则**：新增文献必须写明适用技术线和引用价值；工程实现细节放入 `../engineering/` 或 `../../aris/`。

更新日期：2026-04-02

本文档用于统一记录当前项目可直接引用的技术相关高水平论文，按三条核心技术主线组织，并补充 DOI、出处、CCF 等级与适用说明，便于后续写入开题报告、答辩 PPT 与系统设计文档。

## 0. 说明

### 0.1 选取原则

- 优先收录与本项目三条核心技术主线直接相关的论文：协同群体发现、传播监控与高危定位、事件/叙事报告研判。
- 优先收录 CCF A / B 论文；如为 PNAS、Science Advances 等高影响力交叉期刊，则标注为“非 CCF”。
- 优先使用 DOI、出版社页面、期刊官网或作者机构页面核验元数据。

### 0.2 CCF 等级判定口径

CCF 等级以中国计算机学会 2024-06-28 后更新的推荐目录页面为准，常用入口如下：

- 数据库/数据挖掘/内容检索：https://www.ccf.org.cn/Academic_Evaluation/DM_CS/
- 人工智能：https://www.ccf.org.cn/Academic_Evaluation/AI/
- 人机交互与普适计算：https://www.ccf.org.cn/Academic_Evaluation/HCIAndPC/
- 交叉/综合/新兴：https://www.ccf.org.cn/Academic_Evaluation/Cross_Compre_Emerging/

### 0.3 已纠正的信息

1. `CatchSync: Catching Synchronized Behavior in Large Directed Graphs` 的会议版本是 `KDD 2014`，不是 `KDD 2016`；其扩展期刊版本为 `TKDD 2016`。
2. `End-to-End Multimodal Fact-Checking and Explanation Generation: A Challenging Dataset and Models` 的正式会议发表为 `SIGIR 2023`，不是 `TOIS 2023`。
3. `Exposing Cross-Platform Coordinated Inauthentic Activity in the Run-Up to the 2024 U.S. Election` 已有 `WWW 2025` 正式会议 DOI，不只是 arXiv 预印本。

## 1. 协同群体发现与跨平台证据对齐

### 1.1 CatchSync: Catching Synchronized Behavior in Large Directed Graphs

- 作者：Meng Jiang, Peng Cui, Alex Beutel, Christos Faloutsos, Shiqiang Yang
- 出处：KDD 2014
- CCF：A
- 价值：同步行为检测的经典会议论文，可作为“异常同步边”“群体协同候选发现”的早期图挖掘基础。
- DOI：https://doi.org/10.1145/2623330.2623632

### 1.2 Catching Synchronized Behaviors in Large Networks: A Graph Mining Approach

- 作者：Meng Jiang, Peng Cui, Alex Beutel, Christos Faloutsos, Shiqiang Yang
- 出处：ACM Transactions on Knowledge Discovery from Data, 10(4), 2016
- CCF：B
- 价值：`CatchSync` 的期刊扩展版，适合支撑“同步行为检测 + 稀有行为检测 + 参数无关图异常识别”。
- DOI：https://doi.org/10.1145/2744204

### 1.3 Identifying Coordinated Accounts on Social Media through Hidden Influence and Group Behaviours

- 作者：Karishma Sharma, Yizhou Zhang, Emilio Ferrara, Yan Liu
- 出处：KDD 2021
- CCF：A
- 价值：非常契合本项目“不是先做 bot 再拼群体，而是直接围绕 hidden influence 与 group behaviours 建模”的主轴。
- DOI：https://doi.org/10.1145/3447548.3467391

### 1.4 Content-based Features Predict Social Media Influence Operations

- 作者：Meysam Alizadeh, Jacob N. Shapiro, Cody Buntain, Joshua A. Tucker
- 出处：Science Advances, 6(30), 2020
- CCF：非 CCF
- 价值：强调平台无关、内容驱动的影响行动识别信号，适合作为“跨平台软对齐”和“内容模板化检测”的补强依据。
- DOI：https://doi.org/10.1126/sciadv.abb5824

### 1.5 Temporal Dynamics of Coordinated Online Behavior: Stability, Archetypes, and Influence

- 作者：Serena Tardelli, Leonardo Nizzoli, Maurizio Tesconi, Mauro Conti, Preslav Nakov, Giovanni Da San Martino, Stefano Cresci
- 出处：PNAS, 121(20), 2024
- CCF：非 CCF
- 价值：直接支持“协同群体是动态演化而非静态团块”的设计，适合作为“时间峰值、群体稳定性、动态 archetype”分析依据。
- DOI：https://doi.org/10.1073/pnas.2307038121

### 1.6 Exposing Cross-Platform Coordinated Inauthentic Activity in the Run-Up to the 2024 U.S. Election

- 作者：Federico Cinus, Marco Minici, Luca Luceri, Emilio Ferrara
- 出处：WWW 2025
- CCF：A
- 价值：高度贴合“跨平台协同操纵网络”问题对象，可直接支撑“跨平台 similarity network + suspicious community”方案。
- DOI：https://doi.org/10.1145/3696410.3714698

### 1.7 A Compression-Based Approach to Detecting Automated and Coordinated Behavior on Social Media

- 作者：Edoardo Loru, Niccolò Di Marco, Matteo Cinelli, Walter Quattrociocchi
- 出处：ACM Transactions on Knowledge Discovery from Data, 20(2), 2026
- CCF：B
- 价值：平台无关、行为无关的统一检测思路，适合为“跨平台证据标准化后的一致性度量”提供候选方法。
- DOI：https://doi.org/10.1145/3778356

### 1.8 Coordinated Reply Attacks in Influence Operations: Characterization and Detection

- 作者：Manita Pote, Tugrulcan Elmas, Alessandro Flammini, Filippo Menczer
- 出处：ICWSM 2025
- CCF：B
- 价值：对“thread / reply 区域被组织化注入”的检测非常直接，适合支撑“高危 thread 定位”和“目标账号作为传感器”的思路。
- DOI：https://doi.org/10.1609/icwsm.v19i1.35889

## 2. 传播监控、角色识别与高危定位

### 2.1 Catch me if you can: A Participant-Level Rumor Detection Framework via Fine-Grained User Representation Learning

- 作者：Xueqin Chen, Fan Zhou, Fengli Zhang, Marcello Bonsangue
- 出处：Information Processing & Management, 58(5), 2021
- CCF：B
- 价值：可支撑“账号层是参与者表征层，而不是 bot/human 二元裁决层”的表述。
- DOI：https://doi.org/10.1016/j.ipm.2021.102678

### 2.2 Temporally Evolving Graph Neural Network for Fake News Detection

- 作者：Chenguang Song, Kai Shu, Bin Wu
- 出处：Information Processing & Management, 58(6), 2021
- CCF：B
- 价值：适合作为“事件传播子图的连续时间动态图编码”参考，而不必对全网历史做全局动态图。
- DOI：https://doi.org/10.1016/j.ipm.2021.102712

### 2.3 Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks

- 作者：Tian Bian, Xi Xiao, Tingyang Xu, Peilin Zhao, Wenbing Huang, Yu Rong, Junzhou Huang
- 出处：AAAI 2020
- CCF：A
- 价值：传播结构建模的强基线，适合在本项目中作为“事件传播子图建模”的对照组方法。
- DOI：https://doi.org/10.1609/aaai.v34i01.5393

### 2.4 A Weakly Supervised Propagation Model for Rumor Verification and Stance Detection with Multiple Instance Learning

- 作者：Ruichao Yang, Jing Ma, Hongzhan Lin, Wei Gao
- 出处：SIGIR 2022
- CCF：A
- 价值：可作为“传播树 + 立场联合建模”的代表工作，适合支撑 claim / thread 级传播证据分析。
- DOI：https://doi.org/10.1145/3477495.3531930

### 2.5 Filter-based Stance Network for Rumor Verification

- 作者：Jun Li, Yi Bin, Yunshan Ma, Yang Yang, Zi Huang, Tat-Seng Chua
- 出处：ACM Transactions on Information Systems, 42(4), 2024
- CCF：A
- 价值：非常适合支撑“stance 是传播证据，不只是内容标签”的论述，尤其适合 thread 内争议强度与立场演化建模。
- DOI：https://doi.org/10.1145/3649462

### 2.6 The Hoaxy Misinformation and Fact-Checking Diffusion Network

- 作者：Pik-Mai Hui, Chengcheng Shao, Alessandro Flammini, Filippo Menczer, Giovanni Luca Ciampaglia
- 出处：ICWSM 2018
- CCF：B
- 价值：适合作为“claim 与 fact-check diffusion tracking”以及扩散可视化流程的参考文献。
- DOI：https://doi.org/10.1609/icwsm.v12i1.14986

## 3. 事件 / 叙事报告研判、证据推理与可审计解释

### 3.1 Detecting Breaking News Rumors of Emerging Topics in Social Media

- 作者：S. A. Alkhodair et al.
- 出处：Information Processing & Management, 57(2), 2020
- CCF：B
- 价值：直接支撑“面向 emerging topic / event 的事件化检测单元”，适合说明为什么系统应围绕事件窗口组织证据池。
- DOI：https://doi.org/10.1016/j.ipm.2019.02.016

### 3.2 A Unified Framework for Multi-Modal Rumor Detection via Multi-Level Dynamic Interaction with Evolving Stances

- 作者：Tiening Sun, Chengwei Liu, Lizhi Chen, Zhong Qian, Peifeng Li, Qiaoming Zhu
- 出处：Information Processing & Management, 2025
- CCF：B
- 价值：直接支撑“多模态源信息 + 动态对话图 + evolving stances”的三级报告研判框架。
- DOI：https://doi.org/10.1016/j.ipm.2025.104066

### 3.3 End-to-End Multimodal Fact-Checking and Explanation Generation: A Challenging Dataset and Models

- 作者：Barry Menglong Yao, Aditya Shah, Lichao Sun, Jin-Hee Cho, Lifu Huang
- 出处：SIGIR 2023
- CCF：A
- 价值：适合作为“外部证据检索 + 多模态核查 + 解释生成”一体化链路的关键文献。
- DOI：https://doi.org/10.1145/3539618.3591879

### 3.4 Adversarial Contrastive Learning for Evidence-Aware Fake News Detection With Graph Neural Networks

- 作者：Junfei Wu, Weizhi Xu, Qiang Liu, Shu Wu, Shu Z. Wu, Liang Wang
- 出处：IEEE Transactions on Knowledge and Data Engineering, 36(11), 2024
- CCF：A
- 价值：适合支撑“evidence-aware 图推理”与“证据对比增强”的技术路线。
- DOI：https://doi.org/10.1109/TKDE.2023.3341640

### 3.5 MCFEND: A Multi-source Benchmark Dataset for Chinese Fake News Detection

- 作者：Yupeng Li, Haorui He, Jin Bai, Dacheng Wen
- 出处：WWW 2024
- CCF：A
- 价值：对中文多来源场景非常重要，适合作为“跨源泛化、中文多平台 / 多来源”部分的数据支撑文献。
- DOI：https://doi.org/10.1145/3589334.3645385

## 4. 当前最建议优先进正式参考文献表的核心清单

如果后续要从上面的长清单中选一版“最能支撑本项目设计”的短清单，建议优先保留以下 12 篇：

1. `Identifying Coordinated Accounts on Social Media through Hidden Influence and Group Behaviours`，KDD 2021
2. `Exposing Cross-Platform Coordinated Inauthentic Activity in the Run-Up to the 2024 U.S. Election`，WWW 2025
3. `A Compression-Based Approach to Detecting Automated and Coordinated Behavior on Social Media`，TKDD 2026
4. `Coordinated Reply Attacks in Influence Operations: Characterization and Detection`，ICWSM 2025
5. `Catch me if you can: A participant-level rumor detection framework via fine-grained user representation learning`，IPM 2021
6. `Temporally Evolving Graph Neural Network for Fake News Detection`，IPM 2021
7. `A Weakly Supervised Propagation Model for Rumor Verification and Stance Detection with Multiple Instance Learning`，SIGIR 2022
8. `Filter-based Stance Network for Rumor Verification`，TOIS 2024
9. `Detecting Breaking News Rumors of Emerging Topics in Social Media`，IPM 2020
10. `A Unified Framework for Multi-Modal Rumor Detection via Multi-Level Dynamic Interaction with Evolving Stances`，IPM 2025
11. `End-to-End Multimodal Fact-Checking and Explanation Generation: A Challenging Dataset and Models`，SIGIR 2023
12. `Adversarial Contrastive Learning for Evidence-Aware Fake News Detection With Graph Neural Networks`，TKDE 2024

## 5. 后续补检方向

下一轮若继续扩展文献池，建议优先补以下方向：

- 跨平台 claim 对齐 / 事件对齐 / 资源对齐
- role inference / key-path extraction / evidence subgraph extraction
- 对话图中的 stance 演化与 thread-level 风险传播
- 中文场景下的多平台公开数据集与早期预警 benchmark
- 事实核查检索、结构化解释生成、审计化报告生成
