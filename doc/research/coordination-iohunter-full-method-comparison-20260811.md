# IOHunter 全量 Coordination Discovery Proxy 对比

日期：2026-08-11  
范围：IOHunter processed 全量 external-account recovery proxy  
输出目录：`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-full-crossed-v3-20260810`

## 协议

本轮已经完成全量矩阵：

| 维度 | 数量 |
---|---:|
| Campaign | 6：China、Cuba、Iran、Russia、UAE、Venezuela |
| Model seed | 5：42、43、44、45、46 |
| Official fold | 5：fold-000 至 fold-004 |
| 方法 | 8 |
| 总坐标 | 1,200 |
| 成功 | 975 |
| 显式 blocked | 225 |

评价范围固定为：`external_account_recovery_not_coordination_ground_truth`。

IOHunter processed 不包含真实时间戳、协同边 Gold、社区 Gold 或 harmfulness Gold。因此本报告只能说明 external-account recovery proxy，不能说明真实协同边/社区恢复、时序 Discovery、Coordination Detection 或生产激活。

## 方法

| 方法 | 角色 | 论文/方法来源 | 年份 | 覆盖 |
|---|---|---|---:|---:|
| `frozen_system_account_score_prior` | 系统部署等价账号排序先验 | CogGuard production evidence weighted-degree ranking | 2026 | 6 campaigns |
| `frozen_system_evidence_prior` | 冻结生产图核心 adapter | CogGuard production evidence graph core | 2026 | 2 campaigns |
| `tsgs_mhcr_compact` | 研究候选 | 文档设想：TSGS + MHCR compact graph model | 2026 | 6 campaigns |
| `edgebank` | 强简单基线 | EdgeBank / history-based temporal link prediction baseline | 2022 | 6 campaigns |
| `dense_cosine_leiden` | Dense cosine + Leiden 对照 | Coordination network / community detection reference baseline | 2008-2021 | 1 campaign |
| `no_tsgs` | 消融 | 去 TSGS | 2026 | 6 campaigns |
| `no_mhcr` | 消融 | 去 MHCR | 2026 | 6 campaigns |
| `no_relation_specific` | 消融 | 去 relation-specific transform | 2026 | 6 campaigns |

## 全量 Campaign 平均

数值为 6 个 campaign 的宏平均；`frozen_system_evidence_prior` 与 `dense_cosine_leiden` 只列成功 campaign 平均，不能和 6-campaign 方法直接等价比较。

| 方法 | 可用 campaign | AUPRC | Macro F1 | Recall@K | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| `frozen_system_account_score_prior` | 6 | **0.5886** | **0.7470** | **0.5288** | **0.8130** |
| `tsgs_mhcr_compact` | 6 | 0.4581 | 0.6548 | 0.3979 | 0.7332 |
| `no_relation_specific` | 6 | 0.4596 | 0.6547 | 0.3975 | 0.7356 |
| `no_mhcr` | 6 | 0.4583 | 0.6553 | 0.3959 | 0.7354 |
| `no_tsgs` | 6 | 0.4059 | 0.6137 | 0.3486 | 0.6233 |
| `edgebank` | 6 | 0.4044 | 0.6075 | 0.3497 | 0.6210 |
| `frozen_system_evidence_prior` | 2 | 0.8346 | 0.8552 | 0.7568 | 0.8782 |
| `dense_cosine_leiden` | 1 | 0.4131 | 0.5615 | 0.4255 | 0.4590 |

## AUPRC 分 Campaign

| Campaign | 系统账号排序 | 研究候选 | EdgeBank | no_tsgs | no_mhcr | no_relation_specific | 生产图核心 | Dense Cosine/Leiden |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| China | **0.0969** | 0.0525 | 0.0371 | 0.0370 | 0.0580 | 0.0554 | blocked | blocked |
| Cuba | **0.1778** | 0.0590 | 0.0221 | 0.0215 | 0.0597 | 0.0565 | blocked | blocked |
| Iran | **0.6508** | 0.3146 | 0.3046 | 0.3052 | 0.3129 | 0.3150 | blocked | blocked |
| Russia | 0.8521 | 0.5078 | 0.5101 | 0.5078 | 0.5052 | 0.5101 | **0.8521** | 0.4131 |
| UAE | **0.9367** | 0.9226 | 0.6614 | 0.6719 | 0.9220 | 0.9285 | blocked | blocked |
| Venezuela | 0.8171 | **0.8919** | 0.8909 | 0.8917 | 0.8922 | 0.8921 | 0.8171 | blocked |

## 关键配对结论

### 研究候选 vs 系统账号排序

差值定义为 `tsgs_mhcr_compact - frozen_system_account_score_prior`。

| 指标 | 平均差 | simultaneous 95% CI | 判定 |
|---|---:|---:|---|
| AUPRC | -0.1305 | [-0.2916, 0.0155] | 不支持研究候选优于系统 |
| Macro F1 | -0.0921 | [-0.2157, 0.0070] | 不支持研究候选优于系统 |
| Recall@K | -0.1309 | [-0.2826, 0.0224] | 不支持研究候选优于系统 |
| ROC-AUC | -0.0798 | [-0.2108, 0.0142] | 不支持研究候选优于系统 |

结论：系统账号排序先验是完整 6-campaign 协议下最强方法。研究候选不能替代系统 Discovery 主线。

### 研究候选 vs EdgeBank

差值定义为 `tsgs_mhcr_compact - edgebank`。

| 指标 | 平均差 | simultaneous 95% CI | 判定 |
|---|---:|---:|---|
| AUPRC | +0.0537 | [0.0015, 0.1769] | 支持 proxy 改进 |
| Macro F1 | +0.0473 | [-0.0012, 0.1368] | 不支持 |
| Recall@K | +0.0482 | [-0.0085, 0.1610] | 不支持 |
| ROC-AUC | +0.1123 | [0.0060, 0.2432] | 支持 proxy 改进 |

结论：研究候选只相对 EdgeBank 在 AUPRC 和 ROC-AUC 上有 proxy 改进；不能说全面优于强简单基线。

### 消融

| 对照 | AUPRC 差 | ROC-AUC 差 | 判定 |
|---|---:|---:|---|
| `tsgs_mhcr_compact - no_tsgs` | +0.0522 | +0.1099 | AUPRC/ROC-AUC 支持 TSGS proxy 贡献 |
| `tsgs_mhcr_compact - no_mhcr` | -0.0003 | -0.0021 | 不支持 MHCR 增益 |
| `tsgs_mhcr_compact - no_relation_specific` | -0.0015 | -0.0024 | 不支持 relation-specific 增益 |

## 总结

1. IOHunter 全量对比已经完成，不需要重复跑。
2. 完整 6 campaign 上最好的方法是 `frozen_system_account_score_prior`，即系统部署等价账号排序先验。
3. 研究候选 `tsgs_mhcr_compact` 没有超过系统方法，不能进入生产或作为主张模型。
4. 研究候选相对 EdgeBank 有部分 proxy 改进，但不全面。
5. MHCR 与 relation-specific transform 当前没有稳定增益，后续研究应优先分析为什么系统简单先验更强，而不是继续堆复杂模块。
6. 由于 IOHunter processed 缺少真实时间戳和真实协同 Gold，TGAT、TGN、DyGFormer、Flow Stability 等时序方法不应在该数据集上声称公平复现。

## 可复核产物

- `matrix_manifest.json`：1,200 rows，fingerprint `sha256:fd34429f3b62c2796bbc8ab27a8536d8e64b4c25bcf5b7be2b96f70726a8b37f`
- `aggregate_table.json/csv`
- `claim_decisions.json`
- `integrity_audit.json`
