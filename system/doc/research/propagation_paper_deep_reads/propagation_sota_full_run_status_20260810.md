# Propagation SOTA Baseline 拉取与全量运行状态

> 日期：2026-08-10  
> 本地仓库根目录：`G:\CISCN\CogGuard\subsystems\kt2_repos`  
> 本地数据根目录：`G:\CISCN\dataset\forest-data`  
> 运行入口目录：`G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark`

## 1. 已拉取到本地的 SOTA / baseline 仓库

| baseline / repo | 本地路径 | 远端仓库 | 当前状态 |
|---|---|---|---|
| MINDS | `G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS` | `https://github.com/cspjiao/MINDS` | 已存在；有本地 `.kt2_extracted`，已 fetch，未覆盖 |
| FOREST | `G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST` | `https://github.com/yangchengbupt/FOREST` | 已存在；数据迁移后 worktree 有删除痕迹，已 fetch，未覆盖 |
| CasFT | `G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT` | `https://github.com/UM-Data-Intelligence-Lab/CasFT` | 已存在；有实验产物，已 fetch，未覆盖 |
| DyGLib / DyGFormer | `G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib` | `https://github.com/yule-BUAA/DyGLib` | 已存在；`git pull --ff-only` 已同步 |
| TGN | `G:\CISCN\CogGuard\subsystems\kt2_repos\tgn` | `https://github.com/twitter-research/tgn` | 已存在；`git pull --ff-only` 已同步 |
| CasFlow | `G:\CISCN\CogGuard\subsystems\kt2_repos\casflow` | `https://github.com/Xovee/casflow` | 已存在；`git pull --ff-only` 已同步 |
| ConCat | `G:\CISCN\CogGuard\subsystems\kt2_repos\ConCat` | `https://github.com/UM-Data-Intelligence-Lab/ConCat` | 已存在；`git pull --ff-only` 已同步 |
| DeepHawkes | `G:\CISCN\CogGuard\subsystems\kt2_repos\DeepHawkes` | `https://github.com/CaoQi92/DeepHawkes` | 已存在；`git pull --ff-only` 已同步 |
| TopoLSTM | `G:\CISCN\CogGuard\subsystems\kt2_repos\topolstm` | `https://github.com/vwz/topolstm` | 已存在；`git pull --ff-only` 已同步 |
| CasDO | `G:\CISCN\CogGuard\subsystems\kt2_repos\CasDO` | `https://github.com/CZ-TAO12/CasDO` | 已存在；`git pull --ff-only` 已同步 |
| MS-HGAT | `G:\CISCN\CogGuard\subsystems\kt2_repos\MS-HGAT` | `https://github.com/slingling/MS-HGAT` | 本轮新增 clone 成功 |
| TGB | `G:\CISCN\CogGuard\subsystems\kt2_repos\TGB` | `https://github.com/shenyangHuang/TGB` | 本轮新增 clone 成功；Windows 大小写路径有 `pipeline.PNG/png` 碰撞警告 |
| DyGLib_TGB | `G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib_TGB` | `https://github.com/yule-BUAA/DyGLib_TGB` | 本轮新增 clone 成功 |
| GODEN | `G:\CISCN\CogGuard\subsystems\kt2_repos\GODEN` | `https://github.com/869277160/GODEN` | 本轮新增 clone 成功 |
| CAW | `G:\CISCN\CogGuard\subsystems\kt2_repos\CAW` | `https://github.com/snap-stanford/CAW` | 本轮新增 clone 成功 |

没有验证到可 clone 官方仓库的参考方法：

| method | 状态 |
|---|---|
| HyperIDP | 当前只有本地 proxy adapter，没有原始公开实现仓库 |
| Ghidorah / T3MAL | 已检索论文方向，未验证到可 clone 官方代码 |
| RotDiff | 未验证到可 clone 官方代码 |
| H-Diffu | 未验证到可 clone 官方代码 |

## 2. 进入本轮全量运行的对象

本轮只把已有统一 adapter 的可运行对象放进实验。没有 adapter 的仓库只记录为“已拉取，待协议适配”，不伪装成已完成对比。

| 分组 | 模型 | 运行入口 | 是否进入本轮运行 |
|---|---|---|---|
| Primary SOTA | MINDS | `benchmark.same_protocol_full_run_baselines` / `adapters/minds_runner.py` | 是 |
| Primary SOTA | FOREST | `benchmark.same_protocol_full_run_baselines` / `adapters/forest_runner.py` | 是 |
| Primary SOTA | CasFT | `benchmark.same_protocol_full_run_baselines` / `adapters/casft_runner.py` | 是 |
| System formal model | PropagationAnalysisSequenceJointModel / KT2SequenceJointModel | `benchmark.kt2_minds_comparison` | 是，与 MINDS 做 full protocol 对比 |
| Frontier temporal graph | DyGLib / DyGFormer | `benchmark.run_benchmark` / `adapters/temporal_graph_runner.py` | 是，作为 next-hop frontier |
| Frontier temporal graph | TGN | `benchmark.run_benchmark` / `adapters/temporal_graph_runner.py` | 是，作为 next-hop frontier |
| Protocol / benchmark | TGB | 无统一数据转换与 evaluator 接入 | 否，待接入 |
| Macro SOTA | GODEN | 无统一 FOREST adapter | 否，待接入 |
| Multi-scale SOTA | MS-HGAT | 无统一 FOREST adapter | 否，待接入 |
| Inductive next-hop | CAW | 无统一 FOREST temporal link adapter | 否，待接入 |
| Legacy popularity baselines | CasFlow / ConCat / DeepHawkes / TopoLSTM / CasDO | 无统一 adapter | 否，待接入 |

## 3. 已启动的后台全量任务

launcher：

```text
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\run_propagation_sota_full_20260810.ps1
```

状态文件：

```text
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\propagation_sota_full_20260810_status.json
```

日志：

```text
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\logs\propagation_sota_primary_full_20260810.log
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\logs\propagation_sota_sequence_vs_minds_full_20260810.log
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\logs\propagation_sota_frontier_temporal_full_20260810.log
```

### Step 1：Primary SOTA full run

输出：

```text
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\propagation_sota_primary_full_20260810.json
```

配置：

| 项 | 值 |
|---|---|
| datasets | `douban,twitter,memetracker` |
| seeds | `42,43,44` |
| models | `MINDS,FOREST,CasFT` |
| MINDS | `5 epochs`，`max_minds_cascades=0` |
| FOREST | `5 epochs + 1 RL epoch`，`max_train_batches=0`，`max_eval_batches=0` |
| CasFT | `5 epochs`，`casft_max_events=0`，`run_external=true` |
| device | `cuda` |

### Step 2：System sequence model vs MINDS full protocol

输出：

```text
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\propagation_sota_sequence_vs_minds_full_20260810.json
```

配置：

| 项 | 值 |
|---|---|
| datasets | `douban,twitter,memetracker` |
| seeds | `42,43,44` |
| models | `MINDS,KT2SequenceJointModel` |
| epochs | `5` |
| cascade cap | `MINDS=0`，`KT2 train/test=0` |
| obs ratios | `0.1,0.3,0.5` |
| resume | enabled |
| device | `cuda` |

### Step 3：Frontier temporal graph full run

输出：

```text
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\propagation_sota_frontier_temporal_full_20260810.json
```

配置：

| 项 | 值 |
|---|---|
| datasets | `douban,twitter,memetracker` |
| models | `casft,dyglib,tgn` |
| frontier_max_cascades | `0` |
| frontier_epochs | `5` |
| run_external_frontier | enabled |
| device | `cuda` |

## 4. 当前严谨边界

当前已经完成的是“仓库拉取、本地同步、全量任务启动”。完整对比表必须等后台任务全部完成后才能生成。

以下对象暂不能进入 full-run verdict：

```text
MS-HGAT
GODEN
CAW
TGB
CasFlow
ConCat
DeepHawkes
TopoLSTM
CasDO
HyperIDP original
Ghidorah / T3MAL
RotDiff
H-Diffu
```

原因不是没有参考价值，而是当前尚缺统一 adapter、数据协议转换、指标解析和无泄漏评测接入。后续要把它们纳入同一张全量对比表，必须先完成对应 adapter。
