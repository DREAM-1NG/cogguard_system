# KT2 / F-PROP 传播监控参考文献

> 更新时间：2026-06-26  
> 记录方式：每条文献说明对 KT2 的价值和引用方式。

## 主复现目标

| 文献 | 链接 | 对 KT2 的价值 | 引用方式 |
|---|---|---|---|
| HyperIDP: Customizing Temporal Hypergraph Neural Networks for Multi-Scale Information Diffusion Prediction | https://aclanthology.org/2025.coling-main.64.pdf；论文标注代码 URL: https://github.com/HowieHsu0126/HyperIDP（2026-06-26 公开访问 404） | 同时覆盖宏观规模预测和微观下一用户预测，是当前最贴近 KT2 双任务定义的主复现目标 | 作为主复现目标与论文指标上界 |

## 统一多尺度 baseline

| 文献 | 链接 | 对 KT2 的价值 | 引用方式 |
|---|---|---|---|
| MINDS: Enhancing Multi-Scale Diffusion Prediction via Sequential Hypergraphs and Adversarial Learning | https://ojs.aaai.org/index.php/AAAI/article/view/28701 | 开源统一 macro/micro baseline，数据集与 HyperIDP 部分重合 | 作为可运行统一 baseline |
| FOREST: Multi-scale Information Diffusion Prediction with Reinforced Recurrent Networks | https://www.ijcai.org/proceedings/2019/0560.pdf | 经典多尺度扩散预测开源 baseline，适合 Douban/Twitter sanity run | 作为经典统一 baseline 和微观预测对照 |

## 规模预测 baseline

| 文献 | 链接 | 对 KT2 的价值 | 引用方式 |
|---|---|---|---|
| Can Cascades be Predicted? | https://www.cs.cornell.edu/home/kleinber/www14-cascades.pdf | 早期观测窗口与 cascade predictability 经典定义 | 作为任务定义与传统 baseline 背景 |
| SEISMIC | https://snap.stanford.edu/seismic/ | 自激点过程规模预测强统计 baseline | 作为未来统计 baseline 参考 |
| DeepCas | https://arxiv.org/abs/1611.05373 | 深度级联表示经典规模预测方法 | 作为规模预测深度 baseline 参考 |
| DeepHawkes | https://github.com/CaoQi92/DeepHawkes | Hawkes 机制与可解释传播强度建模 | 作为规模预测和可解释性参考 |
| CasFlow | https://github.com/Xovee/casflow | 结构不确定性与跨平台 cascade prediction | 作为跨平台泛化参考 |
| CasDO | https://github.com/CZ-TAO12/CasDO | 概率扩散和 neural ODE 方向 | 作为前沿规模预测 baseline 参考 |
| ConCat / CasFT | https://github.com/UM-Data-Intelligence-Lab/ConCat | 连续时间动态和未来趋势建模 | 作为连续时间规模预测参考 |

## 下一节点 / temporal graph baseline

| 文献 | 链接 | 对 KT2 的价值 | 引用方式 |
|---|---|---|---|
| Topo-LSTM | https://github.com/vwz/topolstm | 下一节点预测经典 diffusion baseline | 作为微观预测历史强基线 |
| DeepInf | https://arxiv.org/abs/1807.05560 | 社会影响预测 GNN 方向 | 作为影响传播建模参考 |
| TGAT | https://github.com/StatsDLMathsRecomSys/Inductive-representation-learning-on-temporal-graphs | temporal link prediction 标准基线 | 作为无未来泄漏动态图协议参考 |
| TGN | https://github.com/twitter-research/tgn | memory-based temporal graph baseline | 作为候选边时间建模参考 |
| CAW | https://github.com/snap-stanford/CAW | causal anonymous walks，强调归纳和时间约束 | 作为 prospective link prediction 参考 |
| DyGFormer / DyGLib | https://github.com/yule-BUAA/DyGLib | 统一动态图复现库 | 作为后续统一 temporal baseline 工具 |

## 角色判定与证据追溯

| 文献 / 资源 | 链接 | 对 KT2 的价值 | 引用方式 |
|---|---|---|---|
| Finding Rumor Sources on Random Trees | https://doi.org/10.1287/opre.1110.0975 | 谣言源头追溯理论基础 | 作为 provenance/source detection 背景 |
| Provenance for Online Information Diffusion | https://link.springer.com/article/10.1007/s10619-017-7205-1 | 在线信息扩散 provenance 直接参照 | 作为证据链任务定义参考 |
| Bi-GCN | https://github.com/TianBian95/BiGCN | 谣言传播图结构建模 | 作为已观测图双向结构参考 |
| PHEME | https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078 | 线程结构、证据链和 claim 分析数据 | 作为证据追溯数据集参考 |
