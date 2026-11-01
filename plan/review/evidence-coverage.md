# Evidence Coverage Review

## 覆盖结论

- Risk Review 问题边界：由 EV-01 覆盖。
- 帖子级 harmfulness / target / multimodality：由 EV-02 至 EV-06、EV-53、EV-62、EV-63 覆盖。
- 帖子级 claim-conditioned stance：由 EV-07 至 EV-11 覆盖。
- 帖子级 fact verification / evidence / uncertainty：由 EV-12 至 EV-24、EV-56、EV-57、EV-60、EV-61 覆盖。
- 用户级 persistence / role / trajectory：由 EV-25 至 EV-34、EV-54、EV-58 覆盖。
- 社区级 toxic conversation / harassment / IO / cross-platform / multimodal CIB：由 EV-35 至 EV-48 覆盖。
- 社区级 graph-native 方法：由 EV-49 至 EV-52、EV-55、EV-57、EV-59 覆盖。
- Agent / RAG 编排定位：由 EV-22 至 EV-24、EV-60 至 EV-63 覆盖。

## 强度判断

| 模块 | 覆盖强度 | 说明 |
|---|---|---|
| 问题定位 | 强 | Mannocci 综述直接支撑 Detect -> Characterize 与 harmfulness 维度 |
| 帖子级多模态 harmfulness | 强 | HateXplain、Hateful Memes、HarMeme、MOMENTA、RGCL、PromptHate、LMM/MIND Agent 覆盖 label、target、retrieval、prompting 与 multimodal reasoning |
| 帖子级 stance / fact verification | 强 | RumourEval、stance-fact unified corpus、FEVER、HoVer、MOCHEG、FACTIFY3M、AVeriTeC、CompareNet、GET、RAG-Fusion、ClaimCheck 覆盖 claim-conditioned、evidence-aware 与分解式检索 |
| 用户级 harmfulness | 中强 | hateful users、dynamic user representation、cyberbullying、label propagation、temporal session、community context 覆盖 persistence / role / trajectory，但与“协同群体 harmfulness”仍需项目域内标注适配 |
| 社区级 collective harm | 强 | toxic conversation、harassment incitement、reply attacks、IO datasets、cross-platform CIB 覆盖 community harm 的结构性 |
| 图表示方法 | 强 | HGT、Graphormer、TGN、GNNExplainer、GCAN、GET、CACL 给出解释性传播图、证据图、异构图对比学习和动态社区图方法基座 |
| Agent / RAG | 中强 | MARO、RAMA、DEFAME、RAG-Fusion、ClaimCheck、LMM Agents、MIND 适合作为 teacher/reviewer/orchestrator 启发，但不应写成当前成熟在线能力 |

## 主要风险

- 2025-2026 前沿文献如 MARO、RAMA、MIND、ClaimCheck、3MFact、IOHunter、reply attacks、IO datasets、TikTok CIB 部分仍应以“前沿参考 / 方法迁移启发”表述，不应写成已在本项目完整复现。
- 部分图方法文献是通用图表示学习，不是 harmfulness 专用方法；正文中应明确其作用是“社区图编码器候选”，而非直接证明 Risk Review 效果。
- 当前代码仍以语义脚手架和结构前置能力为主；需求文档中必须持续区分“目标设计”和“当前实现”。
- 中文/国内舆情场景还需要后续补充 CNKI 或本地标注案例，目前文档主要使用英文高水平文献作为方法锚点。
