# Coordination Discovery 全交叉公平比较

日期：2026-08-11  
范围：IOHunter external-account recovery proxy 的离线研究评估  
生产状态：`coordination-evidence-runtime-v2` 保持冻结，研究候选不进入 active pointer

## 结论

在相同 campaign、相同 Discovery 输入指纹、相同 5 个 model seeds、相同 5 个官方 folds、相同后置 evaluator 和相同指标协议下，完成了 `6 campaigns x 5 seeds x 5 folds x 8 methods = 1200` 个坐标。研究候选 `tsgs_mhcr_compact` 与生产账号排序等价先验完成 `150/150` 配对。

候选相对生产账号排序等价先验的四项 campaign-level 均值差均为负：AUPRC `-0.1305`、Macro F1 `-0.0921`、Recall@K `-0.1309`、ROC-AUC `-0.0798`。Bonferroni 同时 95% 区间均跨过 0，因此没有通过“替换生产 Discovery”的优越性门禁。候选仍为 `offline-only/non-claimable`。

相对 `EdgeBank`，候选仅在 AUPRC 和 ROC-AUC 通过同时区间门禁；相对 `no_tsgs` 消融也仅在 AUPRC 和 ROC-AUC 通过。`no_mhcr` 与 `no_relation_specific` 的四项消融差异均未通过门禁，当前结果不能支持 MHCR 或关系特异参数化带来稳定增益。

这些结果只评价 IOHunter 的 external-account recovery proxy，不证明真实协同边恢复、社区恢复、动态 Discovery、harmful Coordination Detection 或因果归因。

## 固定协议

- Campaign：`china`、`cuba`、`iran`、`russia`、`UAE`、`venezuela`。
- Model seeds：`42, 43, 44, 45, 46`。
- Official folds：`fold-000` 至 `fold-004`；seed 与 fold 完全交叉，不再绑定。
- Discovery：每个 `campaign/seed/method` 只执行一次，同一预测制品复用于五个 folds；预测制品不读取 evaluator、labels 或 fold。
- Evaluation：标签只进入后置 evaluator；validation 仅用于 Macro F1 threshold，test 仅用于报告指标。
- 配对：`campaign/seed/fold`，要求 source、evaluator 和 fold 指纹一致。
- 推断：先对 campaign 内 25 个 seed-fold 单元取均值，再对 6 个 campaign 均值做 5,000 次 bootstrap；四项主指标使用 Bonferroni simultaneous 95% CI。
- 运行环境和产物：全部位于 `G:`；无 C 盘实验输出。

## 方法覆盖

| 方法 | 角色 | 成功坐标 | 阻断坐标 | 说明 |
|---|---|---:|---:|---|
| `tsgs_mhcr_compact` | 研究候选 | 150 | 0 | TSGS-style evidence selection + MHCR-style self-supervised encoder + Leiden interpretation |
| `frozen_system_account_score_prior` | 生产账号排序等价先验 | 150 | 0 | 与生产静态图 weighted-degree 账号排序等价；不代表生产社区输出 |
| `frozen_system_evidence_prior` | 冻结生产图核心 adapter | 50 | 100 | 仅 Russia/Venezuela 通过 100,000 occurrence guard |
| `edgebank` | 静态历史边强基线 | 150 | 0 | 完整六 campaign 运行 |
| `dense_cosine_leiden` | Dense Cosine/Leiden 对照 | 25 | 125 | 只有 Russia 在 2,048 账号 feasibility limit 内 |
| `no_tsgs` | 去 TSGS 消融 | 150 | 0 | 保留 encoder/clustering 其余路径 |
| `no_mhcr` | 去 MHCR 消融 | 150 | 0 | 使用输入关系特征，不运行 MHCR encoder |
| `no_relation_specific` | 共享关系变换消融 | 150 | 0 | 去除 relation-specific transform |

阻断是显式能力或资源边界，不是失败结果。Dense 对照因账号规模超限阻断；冻结生产图核心因 occurrence 超过声明的 100,000 runtime budget 阻断，未截断数据、未替换生产算法。

## 全量代理结果

数值为 campaign 均值；`blocked` 表示该方法在该 campaign 没有可比 test 结果。

### AUPRC

| Campaign | Candidate | Production score | EdgeBank | no_tsgs | no_mhcr | no_relation_specific | Dense Cosine/Leiden |
|---|---:|---:|---:|---:|---:|---:|---:|
| China | 0.0525 | 0.0969 | 0.0371 | 0.0370 | 0.0580 | 0.0554 | blocked |
| Cuba | 0.0590 | 0.1778 | 0.0221 | 0.0215 | 0.0597 | 0.0565 | blocked |
| Iran | 0.3146 | 0.6508 | 0.3046 | 0.3052 | 0.3129 | 0.3150 | blocked |
| Russia | 0.5078 | 0.8521 | 0.5101 | 0.5078 | 0.5052 | 0.5101 | 0.4131 |
| UAE | 0.9226 | 0.9367 | 0.6614 | 0.6719 | 0.9220 | 0.9285 | blocked |
| Venezuela | 0.8919 | 0.8171 | 0.8909 | 0.8917 | 0.8922 | 0.8921 | blocked |

### Macro F1

| Campaign | Candidate | Production score | EdgeBank | no_tsgs | no_mhcr | no_relation_specific | Dense Cosine/Leiden |
|---|---:|---:|---:|---:|---:|---:|---:|
| China | 0.5038 | 0.5829 | 0.5068 | 0.5101 | 0.5140 | 0.5072 | blocked |
| Cuba | 0.5438 | 0.5823 | 0.4949 | 0.4951 | 0.5452 | 0.5376 | blocked |
| Iran | 0.5630 | 0.7264 | 0.5206 | 0.5289 | 0.5601 | 0.5653 | blocked |
| Russia | 0.5329 | 0.8425 | 0.5349 | 0.5329 | 0.5315 | 0.5364 | 0.5615 |
| UAE | 0.8846 | 0.8798 | 0.6894 | 0.7140 | 0.8821 | 0.8832 | blocked |
| Venezuela | 0.9010 | 0.8679 | 0.8987 | 0.9010 | 0.8989 | 0.8983 | blocked |

### Recall@K

| Campaign | Candidate | Production score | EdgeBank | no_tsgs | no_mhcr | no_relation_specific | Dense Cosine/Leiden |
|---|---:|---:|---:|---:|---:|---:|---:|
| China | 0.0190 | 0.1260 | 0.0013 | 0.0013 | 0.0210 | 0.0190 | blocked |
| Cuba | 0.0017 | 0.1109 | 0.0113 | 0.0143 | 0.0026 | 0.0017 | blocked |
| Iran | 0.3148 | 0.5983 | 0.2624 | 0.2615 | 0.3046 | 0.3137 | blocked |
| Russia | 0.3811 | 0.7491 | 0.3927 | 0.3811 | 0.3804 | 0.3789 | 0.4255 |
| UAE | 0.8272 | 0.8242 | 0.5877 | 0.5894 | 0.8217 | 0.8269 | blocked |
| Venezuela | 0.8437 | 0.7645 | 0.8430 | 0.8437 | 0.8449 | 0.8449 | blocked |

### ROC-AUC

| Campaign | Candidate | Production score | EdgeBank | no_tsgs | no_mhcr | no_relation_specific | Dense Cosine/Leiden |
|---|---:|---:|---:|---:|---:|---:|---:|
| China | 0.6761 | 0.6783 | 0.5356 | 0.5360 | 0.6961 | 0.6876 | blocked |
| Cuba | 0.8123 | 0.8524 | 0.4902 | 0.4893 | 0.8140 | 0.8047 | blocked |
| Iran | 0.4808 | 0.6397 | 0.4509 | 0.4534 | 0.4769 | 0.4804 | blocked |
| Russia | 0.5046 | 0.8102 | 0.5033 | 0.5046 | 0.4981 | 0.5101 | 0.4590 |
| UAE | 0.9470 | 0.9510 | 0.7680 | 0.7781 | 0.9487 | 0.9524 | blocked |
| Venezuela | 0.9787 | 0.9463 | 0.9778 | 0.9786 | 0.9783 | 0.9785 | blocked |

## 配对统计

### Candidate vs production account-score prior

差值定义为 `candidate - frozen_system_account_score_prior`。

| 指标 | 均值差 | 未校正 95% CI | Bonferroni simultaneous 95% CI | 判定 |
|---|---:|---:|---:|---|
| AUPRC | -0.1305 | [-0.2651, -0.0070] | [-0.2916, 0.0155] | 未支持优越性 |
| Macro F1 | -0.0921 | [-0.1944, -0.0070] | [-0.2157, 0.0070] | 未支持优越性 |
| Recall@K | -0.1309 | [-0.2535, -0.0086] | [-0.2826, 0.0224] | 未支持优越性 |
| ROC-AUC | -0.0798 | [-0.1817, 0.0027] | [-0.2108, 0.0142] | 未支持优越性 |

候选的均值在四项指标均更低；由于替换门禁使用同时区间，不能把未校正区间直接写成研究模型的正式显著性结论。

### Candidate vs EdgeBank

| 指标 | 均值差 | simultaneous 95% CI | 判定 |
|---|---:|---:|---|
| AUPRC | +0.0537 | [+0.0015, +0.1769] | 通过代理任务门禁 |
| Macro F1 | +0.0473 | [-0.0012, +0.1368] | 未支持 |
| Recall@K | +0.0482 | [-0.0085, +0.1610] | 未支持 |
| ROC-AUC | +0.1123 | [+0.0060, +0.2432] | 通过代理任务门禁 |

### Ablation

| 对照 | AUPRC 差值 | ROC-AUC 差值 | Macro F1 / Recall@K | 结论 |
|---|---:|---:|---|---|
| `no_tsgs` | +0.0522, CI [+0.0017,+0.1697] | +0.1099, CI [+0.0046,+0.2411] | simultaneous CI 跨 0 | 仅 TSGS 相关代理指标通过 |
| `no_mhcr` | -0.0003, CI [-0.0034,+0.0019] | -0.0021, CI [-0.0130,+0.0046] | simultaneous CI 均跨 0 | 未支持 MHCR 增益 |
| `no_relation_specific` | -0.0015, CI [-0.0043,+0.0011] | -0.0024, CI [-0.0085,+0.0039] | simultaneous CI 均跨 0 | 未支持关系特异增益 |

## 生产图核心的等价性边界

`frozen_system_account_score_prior` 只在本实验实际评分的账号排序上与生产静态图核心等价；它没有运行生产 greedy-modularity，不能比较社区边界、社区覆盖、谱系或稳定性。

`frozen_system_evidence_prior` 才调用冻结生产静态图核心，但只有 Russia/Venezuela 的 `50/150` 行成功；China、Cuba、Iran、UAE 的 `100` 行因 occurrence guard 阻断。因此本矩阵完成了生产账号排序全量对比，但没有完成冻结生产社区核心的全 campaign 全量对比。

## IOHunter 能力边界

IOHunter processed graphs 提供 external-account 标签和官方 folds，但不提供：

- 真实协同账号对或协同边；
- 真实协同社区及 split/merge lineage；
- 可用于动态 Discovery 的原始观测时间戳；
- harmful-CIB intent/impact 标签；
- campaign 因果和 orchestration 标注。

所以当前结果不能支持 `true coordination edge/community recovery`、`temporal Discovery`、`harmful Coordination Detection`、因果归因或生产激活。它只能回答：在统一代理协议下，候选是否比生产账号排序先验和强简单基线更能恢复 IOHunter external accounts。答案是：候选相对生产先验没有通过替换门禁；相对 EdgeBank 的提升仅在 AUPRC/ROC-AUC 上被支持。

## 可复核制品与门禁

- 主目录：`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-full-crossed-v3-20260810`
- `matrix_manifest.json`：1200 行，manifest fingerprint `sha256:fd34429f3b62c2796bbc8ab27a8536d8e64b4c25bcf5b7be2b96f70726a8b37f`。
- `aggregate_table.json/csv`：campaign 与矩阵聚合。
- `claim_decisions.json`：v5 配对统计、同时区间、固定 blocked claims 和消融。
- `integrity_audit.json`：独立重算通过；1200 行、240 个 execution groups、195 个 prediction artifacts，错误数为 0。
- `runs/`：1200 个逐坐标结果；`p/`：按 `campaign/seed/method` 复用的预测数组和 metadata。
- 定向协议测试：`66 passed, 1 warning`。

## 后续决策

1. 生产 Discovery 继续冻结，不修改 active pointer。
2. 不再把 TSGS+MHCR 写成已优于生产模型；当前研究证据只支持相对 EdgeBank 的部分代理改进。
3. 研究线下一步先解释 TSGS 贡献的 campaign 敏感性、MHCR 无增益和生产先验优势，再考虑复杂模型。
4. 增加具有协同边、社区或事件时间 Gold 的数据集，分别评估 pair retrieval、community recovery 和 temporal lineage；IOHunter 不承担它没有标签的主张。
5. Detection 与四维 characterization 独立建设 authenticity、harmfulness、orchestration 和 time-variance 的合格标签、跨 campaign/platform/time 协议与 selective prediction，不从 external-account proxy 推导有害协同结论。
