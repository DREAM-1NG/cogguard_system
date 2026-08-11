# Coordination Discovery Public Proxy 多数据集对比

日期：2026-08-11  
状态：sample/preflight，对比 runner 已接通；结果不可作为论文主结论  
输出目录：`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\public-proxy-multidataset-20260811`

## 任务定义

本轮对比不使用 harmfulness、社区 Gold 或协同边 Gold。为了让只有 IO 正样本的公开 archive 也能进入同一协议，proxy 任务定义为：

用训练时间段内的多关系证据边，预测测试时间段中新出现或再次出现的协同账号对。

评价范围固定为：`future_coordination_pair_recovery_proxy_not_harmful_detection`。

该任务可以比较不同 evidence/backbone/recency scoring 的 Discovery proxy 能力，但不能证明 harmful Coordination Detection。

## 数据与设置

| 数据集 | 本地来源 | 行数限制 | 可用事件 | 账号数 | 测试正样本账号对 |
|---|---|---:|---:|---:|---:|
| `twitter_io_ira_2018_10` | `G:\CISCN\dataset\twitter_io\2018_10\ira\ira_tweets_csv_hashed.zip` | 50,000 | 45,509 | 1,939 | 572 |
| `fivethirtyeight_russian_troll_tweets` | `G:\CISCN\dataset\russian-troll-tweets` | 50,000 | 50,000 | 73 | 5 |
| `twitter_state_backed_ops_sample` | `G:\CISCN\dataset\TwitterStateBackedOps\datasets` | 50,000 | 49,989 | 30 | 141 |

参数：

| 参数 | 值 |
|---|---:|
| `train_fraction` | 0.7 |
| `window_seconds` | 3600 |
| `max_accounts_per_object` | 50 |
| `negative_multiplier` | 5 |
| `seed` | 42 |

## 方法

| 方法 | 含义 |
|---|---|
| `system_weighted_evidence` | 按关系类型权重累计历史账号对证据 |
| `edgebank_binary` | 历史出现过该账号对则为 1 |
| `unweighted_count` | 当前实现等价于 binary presence，作为计数基线占位 |
| `recency_decay` | 历史证据加 24h half-life 时间衰减 |
| `relation_max` | 多关系中取最大关系证据 |

## 结果

### AUPRC

| 数据集 | system_weighted | EdgeBank | recency_decay | relation_max |
|---|---:|---:|---:|---:|
| twitter_io IRA 2018-10 | 0.0277 | 0.0268 | 0.0389 | 0.0290 |
| FiveThirtyEight IRA | 0.0771 | 0.0192 | 0.2105 | 0.0771 |
| TwitterStateBackedOps sample | 0.3303 | 0.3324 | 0.3359 | 0.3312 |

### ROC-AUC

| 数据集 | system_weighted | EdgeBank | recency_decay | relation_max |
|---|---:|---:|---:|---:|
| twitter_io IRA 2018-10 | 0.1529 | 0.1514 | 0.1728 | 0.1528 |
| FiveThirtyEight IRA | 0.3515 | 0.2913 | 0.3530 | 0.3515 |
| TwitterStateBackedOps sample | 0.4933 | 0.4933 | 0.4934 | 0.4934 |

### Recall@K

| 数据集 | system_weighted | EdgeBank | recency_decay | relation_max |
|---|---:|---:|---:|---:|
| twitter_io IRA 2018-10 | 0.0122 | 0.0017 | 0.0455 | 0.0087 |
| FiveThirtyEight IRA | 0.2000 | 0.0000 | 0.2000 | 0.2000 |
| TwitterStateBackedOps sample | 0.3333 | 0.3333 | 0.3333 | 0.3333 |

## 判断

1. Runner 已接通三类本地公开数据，能够从 raw CSV/zip 中重新抽取 timestamped evidence objects，不依赖旧中间产物。
2. 目前最有统计价值的是 `twitter_io_ira_2018_10`，因为它有 1,939 个账号和 572 个测试正样本对。
3. FiveThirtyEight 的 50k sample 只有 5 个测试正样本对，当前数值不稳定，只能证明 runner 可运行。
4. TwitterStateBackedOps 当前 sample 只有 30 个账号，说明 file selection 还偏窄，下一步要按 campaign 显式选择 tweet CSV，而不是简单扫描前 16 个 CSV。
5. `recency_decay` 在三个 sample 中均为最强或并列最强，但这只是 sample/preflight 现象，不能主张为稳定提升。

## 下一步

1. 把 `state_backed_ops` 配置改为按 campaign 显式选择，例如 Cuba、Iran、Russia、Venezuela、China。
2. 把 `limit_rows` 提升到 200k/500k，并按 seed 重采样负样本。
3. 加入 Pólya、Noise-Corrected 和 ECM backbone 真实现，替换当前轻量 scoring baseline。
4. 在 timestamped event stream 基础上接 TGAT/TGN/DyGFormer 和 Flow Stability。
5. 形成 multi-dataset、multi-seed、multi-window 的正式矩阵后，再写 result-to-claim。

## 可复核产物

- `public_proxy_manifest.json`
- `public_proxy_table.csv`
- manifest fingerprint: `sha256:051cc22ae011a5474cc6f3b9824152ab03d8ba8a322b857bc2d14c047751cc58`
