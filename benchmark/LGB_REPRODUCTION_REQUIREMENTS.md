# LGB 社交机器人检测严格复现要求

## 目标定位

LGB 作为 KT2 传播监控的参与者风险辅助模块，不替代规模预测、角色定位和下一跳预测三项核心能力。它的任务是 social bot detection / node classification：将社交账号视作图节点，输入账号文本语义和社交关系结构，输出 human/bot 标签、bot probability，并为传播图中的异常账号、协同账号和关键传播角色提供风险证据。

主参考论文：

| 论文 | 作者 | 链接 | KT2 迁移方式 |
|---|---|---|---|
| LGB: Language Model and Graph Neural Network-Driven Social Bot Detection | Zhou, Zhang, Wang, Geng, Dong, Tang | arXiv: https://arxiv.org/abs/2406.08762；系统页: https://botdetection.aminer.cn/robotmain | 复现 LM supervised fine-tuning、GNN graph contrastive pretraining、GNN concat fusion fine-tuning，并接入 KT2 参与者风险解释 |

本地参考 PDF 已复制到：

`G:\CISCN\CogGuard\subsystems\cogguard_dev\tmp\papers\lgb_social_bot_detection_2024.pdf`

论文正文抽取文件：

`G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_paper_extract.txt`

## 论文方法要求

LGB 由三段训练构成：

| 阶段 | 论文定义 | 复现要求 |
|---|---|---|
| LM supervised fine-tuning | 将用户属性、description、tweets 构造成 unified user textual sequence，用 LM 编码并用 MLP 做账号二分类 | 必须实现 Fig. 5 格式的 `User profile / Description / Tweet` 序列；严格复现阶段应使用 RoBERTa 或 T5，并在标注数据上 SFT |
| GNN graph contrastive pretraining | 用 SFT 后的 LM 表示作为节点特征，随机 drop edges 生成两张图视图，用 InfoNCE/GCL 学结构表示 | 必须实现两视图 edge dropout、同节点正样本、不同节点负样本和温度参数 `tau=0.4` |
| GNN fine-tuning with multimodal fusion | 输入 LM 表示 `X` 和图 `A`，GNN 得到结构表示 `H`，`Concat(X,H)` 后接 MLP 分类 | 必须报告 LGB(GCN)，建议同时报告 LGB(GIN)、LGB(GAT)；融合方式默认为 concat |

论文关键超参数和实验协议：

| 项目 | 论文设置 |
|---|---|
| 数据集 | TwiBot-22、TwiBot-20 |
| TwiBot-22 采样 | 81,433 human + 81,432 bot，共 162,865 accounts |
| TwiBot-22 划分 | 7:2:1 train/valid/test |
| TwiBot-20 | 采用 TwiBot-20 原始数据设置 |
| GNN hidden layers | 2 layers，每层 512 channels |
| GCL temperature | `tau=0.4` |
| TwiBot-22 edge dropout views | 0.2 和 0.4 |
| TwiBot-20 edge dropout views | 0.4 和 0.6 |
| 优化器 | AdamW |
| 重复次数 | 5 次 random weight initialization，报告 mean ± std |
| 指标 | Accuracy、F1-Score、ROC-AUC |
| 硬件 | 论文使用 NVIDIA A100 80GB、PyTorch、PyTorch Geometric |

## 论文目标结果

表 II 的主结果应作为复现对齐目标，而不是本地 smoke 指标：

| Model | TwiBot-22 Accuracy | TwiBot-22 F1 | TwiBot-22 ROC-AUC | TwiBot-20 Accuracy | TwiBot-20 F1 | TwiBot-20 ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|
| LGB(GAT) | 80.30 ± 0.06 | 81.06 ± 0.05 | 80.30 ± 0.06 | 84.83 ± 0.52 | 87.33 ± 0.47 | 83.79 ± 0.53 |
| LGB(GIN) | 80.33 ± 0.03 | 80.93 ± 0.03 | 80.33 ± 0.03 | 84.89 ± 0.68 | 87.16 ± 0.63 | 84.17 ± 0.63 |
| LGB(GCN) | 80.42 ± 0.05 | 81.31 ± 0.08 | 80.42 ± 0.05 | 85.09 ± 0.51 | 87.44 ± 0.31 | 84.23 ± 0.71 |

## 必做消融

| 消融 | 目的 |
|---|---|
| w/o LM supervised fine-tuning | 验证 SFT 后语义表示对稀疏节点的贡献 |
| w/o GNN fine-tuning | 验证最终任务监督下语义和结构对齐的重要性 |
| w/o GNN pre-training | 验证 unlabeled graph contrastive learning 的贡献 |
| w/o concat | 验证多模态融合是否必要 |
| w/ average fusion | 对比 concat 与平均融合 |
| w/ max fusion | 对比 concat 与最大融合 |
| supervised fine-tuned LM only | 验证仅 LM 对孤立/稀疏节点的能力边界 |

## 数据准备

官方数据优先：

| 数据集 | 链接 | 当前本地状态 |
|---|---|---|
| TwiBot-22 | https://github.com/LuoUndergradXJTU/TwiBot-22 | 本地 `G:\CISCN\dataset` 暂未发现官方 TwiBot-22 目录 |
| TwiBot-20 | https://github.com/BunsenFeng/TwiBot-20 | 本地 `G:\CISCN\dataset` 暂未发现官方 TwiBot-20 目录 |

本地 smoke adapter 支持 compact schema：

| 文件 | 字段 |
|---|---|
| `nodes.jsonl` | `id`、`label`、`name`、`description`、profile 计数字段、`tweets` |
| `edges.csv` | `source,target` |
| `split.csv` | `id,split`，split 为 `train/valid/test` |

官方格式转换器已接入 `benchmark/adapters/lgb_bot_detection.py`，用于把论文数据格式转换到本地 compact schema，便于先跑 KT2 本地 adapter 和后续统一复现实验入口：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --convert_official `
  --source_format twibot22 `
  --data_dir G:\CISCN\dataset\TwiBot-22 `
  --out_dir G:\CISCN\dataset\TwiBot-22-lgb-compact

python -m benchmark.adapters.lgb_bot_detection `
  --convert_official `
  --source_format twibot20 `
  --data_dir G:\CISCN\dataset\TwiBot-20 `
  --out_dir G:\CISCN\dataset\TwiBot-20-lgb-compact
```

转换器支持：

| 来源格式 | 输入文件 | 输出 |
|---|---|---|
| TwiBot-22 official 4-file schema | `user.json`/`user.jsonl` 或 `node.json`/`node.jsonl`、`tweet_*.json`/`tweet_*.jsonl`、`label.csv`、`split.csv`、`edge.csv` | `nodes.jsonl`、`edges.csv`、`split.csv`、`conversion_summary.json` |
| TwiBot-20 raw schema | `train.json`/`train.jsonl`、`dev.json`/`dev.jsonl`/`valid.json`/`valid.jsonl`、`test.json`/`test.jsonl`、可选 `support.json`/`support.jsonl` 或 `TwiBot-20_sample.json` | `nodes.jsonl`、`edges.csv`、`split.csv`、`conversion_summary.json` |

注意：转换器默认保留未标注 support/context 用户作为图上下文节点，并在 `conversion_summary.json` 中记录 `unlabeled_context_nodes`。本地 LGB loader 用 `label=-1` 表示无标签节点；这些节点可参与 edge-dropout GCL 图结构预训练，但会从 LM supervised fine-tuning、GNN supervised fine-tuning 和 Accuracy/F1/ROC-AUC 评估中排除。严格论文级复现应继续保留官方完整图或显式记录 unlabeled 节点使用策略。

转换器支持 JSON array 和 JSONL 两种输入。对于较大的官方文件，优先保留 JSONL 形式，避免为了转换而一次性载入完整 JSON array。

本地严格复现审计命令：

```powershell
python -m benchmark.lgb_reproduction_audit `
  --repo_root G:\CISCN\CogGuard\subsystems\cogguard_dev `
  --dataset_root G:\CISCN\dataset `
  --output_dir G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark
```

该命令会生成 `lgb_reproduction_audit.json` 与 `lgb_reproduction_audit.md`，用于判断是否具备 TwiBot-22/TwiBot-20 官方数据、是否仍被 HashingVectorizer proxy、缺哪些 5-seed / ablation 证据。

官方数据预检命令：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --inspect_data `
  --dataset_root G:\CISCN\dataset
```

预检只检查 strict reproduction 所需的官方数据结构，不会启动训练。`TwiBot-22` 必须包含 `label.csv`、`split.csv`、`edge.csv`、用户文件和 `tweet_*` 文件；`TwiBot-20` 必须包含 full dataset 的 `train/dev(or valid)/test` 文件。`TwiBot-20_sample.json` 只允许用于转换器 smoke test，不能作为严格复现数据。

官方数据申请包生成命令：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --write_data_request `
  --dataset_root G:\CISCN\dataset `
  --out_dir G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark
```

该命令会生成 `lgb_data_request_package.json` 和 `lgb_data_request_package.md`，记录 TwiBot-22/TwiBot-20 官方仓库、授权/申请说明、目标放置目录、必备文件、预检命令和 strict pipeline 命令。该申请包用于组内数据申请与复现审计，不代表数据已经获得，也不能替代 strict gate。

严格复现一键 pipeline：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --strict_pipeline `
  --dataset_root G:\CISCN\dataset `
  --artifacts_root G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict `
  --device cuda `
  --encoder_backend transformers_roberta_sft `
  --model_name roberta-base `
  --seeds 42,43,44,45,46
```

该入口会依次执行官方数据定位、TwiBot 格式转换、RoBERTa/T5 SFT 特征导出、5-seed 主实验、Table III 消融实验，并在最后调用 strict artifact gate。当前本地 `G:\CISCN\dataset` 尚未发现官方 `TwiBot-22` 和 `TwiBot-20` 目录，因此该命令当前会返回 `status=incomplete`；只有官方数据、Transformer SFT 特征、5-seed 主结果和完整消融 artifact 都生成后，才会返回 `strict_reproduction_complete=true`。

严格复现 artifact gate：

每个数据集的复现实验结果应保存为独立目录，例如：

```text
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict\
  TwiBot-22\
    conversion_summary.json
    lm_sft_report.json
    lgb_multiseed_summary.json
    lgb_ablation_suite.json
  TwiBot-20\
    conversion_summary.json
    lm_sft_report.json
    lgb_multiseed_summary.json
    lgb_ablation_suite.json
```

门禁命令：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --strict_gate `
  --artifacts_root G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict `
  --write_report_md G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict_gate.md
```

通过条件：

| Artifact | 通过条件 |
|---|---|
| `conversion_summary.json` | schema 为 `cogguard.kt2.lgb_conversion_summary.v1` |
| `lm_sft_report.json` | schema 为 `cogguard.kt2.lgb_lm_sft_features.v1`，`strict_lgb_text_encoder=true`，`encoder_backend` 以 `transformers_` 开头 |
| `lgb_multiseed_summary.json` | schema 为 `cogguard.kt2.lgb_multiseed_summary.v1`，`num_runs>=5`，`meets_paper_seed_count=true`，Accuracy/F1/ROC-AUC 均有 mean/std；每个 run 必须记录论文 GCL 协议 |
| `lgb_ablation_suite.json` | schema 为 `cogguard.kt2.lgb_ablation_suite.v1`，`table3_complete=true`，覆盖 full、w/o LM SFT、w/o GNN fine-tuning、w/o GNN pretraining、w/o concat、average、max、LM only；每个消融 run 必须记录论文 GCL 协议 |

额外严格证据要求：

- `conversion_summary.json` 必须证明使用官方级数据规模，记录 `source_format`、`node_count`、`labeled_nodes`、`label_counts`、`split_counts`、`include_unlabeled_context` 和 `unlabeled_context_nodes`；小型 smoke/toy conversion 不能通过 strict gate。
- `lgb_multiseed_summary.json` 必须包含 `run_metadata`，记录 `artifact_type=lgb_multiseed_summary`、`data_dir`、`command_or_entrypoint`、`device`、`seeds` 和 `reproduction_level`。
- `lgb_multiseed_summary.json` 和 `lgb_ablation_suite.json` 的顶层 `reproduction_level` 及其 `run_metadata.reproduction_level` 必须达到 `frontier_reproduction_full_run` 或 `strict_lgb_reproduction_full_run`；`public_code_adapter`、small-run、proxy 级别不能通过 strict gate。
- `lgb_multiseed_summary.json` 必须包含 `gnn_variant` 和 `paper_target`；`paper_target` 需指向论文 Table II 中对应的 `LGB(GCN)` / `LGB(GIN)` / `LGB(GAT)` 目标指标，不能只报告本地 smoke 指标。
- `lgb_ablation_suite.json` 必须包含 `run_metadata`，记录 `artifact_type=lgb_ablation_suite`、`data_dir`、`command_or_entrypoint`、`device`、`seeds`、`variants` 和 `reproduction_level`。
- `lgb_multiseed_summary.json` 和 `lgb_ablation_suite.json` 的每个 run 都必须记录 run-level `training_protocol`，其中 `gnn` 必须与顶层 `gnn_variant` 一致，`text_encoder` 不能是 HashingVectorizer/proxy，且必须记录 `text_features_source`。
- `conversion_summary.json`、`lm_sft_report.json`、`lgb_multiseed_summary.json` 和 `lgb_ablation_suite.json` 必须跨 artifact 一致：LM feature `node_count` 要与转换后的 `node_count` 一致，所有 run-level `text_features_source` 必须指向 `lm_sft_report.json` 记录的 `feature_file`。
- `--write_report_md` 会额外写出人可读 Markdown 门禁报告，用于复现实验汇报和人工审查；最终是否完成仍以 JSON gate 的 `strict_reproduction_complete` 为准。

论文 GCL 协议门禁：

| 数据集 | edge dropout views | tau |
|---|---:|---:|
| TwiBot-22 | `0.2, 0.4` | `0.4` |
| TwiBot-20 | `0.4, 0.6` | `0.4` |

只有 TwiBot-22 和 TwiBot-20 两个目录都通过该 gate，才能把 LGB 写为“严格复现完成”。

## 当前代码状态

| 文件 | 作用 | 当前边界 |
|---|---|---|
| `benchmark/adapters/lgb_bot_detection.py` | LGB 本地可复现 adapter：统一文本序列、TwiBot 官方格式转换、GCL、GCN/GIN/GAT 可执行图编码、GNN concat fusion、Accuracy/F1/ROC-AUC 输出 | 使用 HashingVectorizer 作为本地 smoke 语义代理；不是 RoBERTa/T5 full reproduction；compact 转换默认保留 unlabeled support/context 节点作为 GCL 图上下文，但不把无标签节点用于监督损失和指标 |
| `benchmark.adapters.lgb_bot_detection --strict_pipeline` | 官方数据到 strict artifact 的一键调度入口：conversion、LM SFT、5-seed、Table III、strict gate | pipeline 已就绪；当前本地缺官方 TwiBot-22/TwiBot-20 数据，因此只能返回 incomplete，不能宣称严格复现完成 |
| `benchmark/lgb_reproduction_audit.py` | 输出 LGB 严格复现准备度审计 JSON/Markdown | 只做状态审计，不运行 RoBERTa/T5 或 5-seed full-run |
| `benchmark/schema.py` | 新增 `bot_detection` task schema 校验 | 仅校验 LGB 输出结构和关键指标 |
| `tests/test_smoke.py` | 合成数据、TwiBot-22 官方 4-file fixture、TwiBot-20 raw fixture 的 smoke test | 只证明本地数据入口和训练闭环，不证明论文结果复现 |

运行 smoke 示例：

```powershell
python -m pytest tests\test_smoke.py -q
```

compact 数据运行示例：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --data_dir path\to\compact_lgb_dataset `
  --dataset compact_lgb `
  --seed 42 `
  --device cpu
```

外部 RoBERTa/T5 SFT 特征接入示例：

本地 smoke/proxy 特征导出示例，仅用于验证 KT2 管线，不可作为论文复现结果：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --export_lm_features `
  --data_dir G:\CISCN\dataset\TwiBot-22-lgb-compact `
  --out_dir G:\CISCN\dataset\TwiBot-22-lgb-compact\lm_sft `
  --encoder_backend lightweight_hashing_sft `
  --model_name local-lightweight-proxy `
  --feature_dim 128 `
  --epochs_lm 1 `
  --seed 42 `
  --device cpu
```

严格复现所需 RoBERTa/T5 SFT 特征导出示例：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --export_lm_features `
  --data_dir G:\CISCN\dataset\TwiBot-22-lgb-compact `
  --out_dir G:\CISCN\dataset\TwiBot-22-lgb-compact\lm_sft `
  --encoder_backend transformers_roberta_sft `
  --model_name roberta-base `
  --epochs_lm 3 `
  --batch_size 8 `
  --max_length 256 `
  --seed 42 `
  --device cuda
```

导出后会生成 `lm_features.jsonl` 与 `lm_sft_report.json`。严格复现报告必须使用 `encoder_backend=transformers_roberta_sft` 或 `transformers_t5_sft`，并记录模型名、epoch、batch size、max length、seed、设备、训练日志和特征文件路径。

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --data_dir G:\CISCN\dataset\TwiBot-22-lgb-compact `
  --dataset TwiBot-22 `
  --text_features_path G:\CISCN\dataset\TwiBot-22-lgb-compact\lm_sft\lm_features.jsonl `
  --text_encoder roberta_sft_features `
  --seed 42 `
  --device cuda
```

`--text_features_path` 支持以下格式，必须与 `nodes.jsonl` 中的 `id` 对齐：

| 格式 | 要求 |
|---|---|
| `.jsonl` | 每行包含 `id` 和 `embedding` 或 `features` |
| `.json` | 支持 `{id: vector}`、`[{id, embedding}]` 或 `{"features": [{id, embedding}]}` |
| `.csv` | 第一列为 `id`/`user_id`，其余列为数值向量 |
| `.npy` | 行顺序必须与 `nodes.jsonl` 一致 |
| `.npz` | 优先读取 `features` + `node_ids`；否则读取 `arr_0` 且要求行顺序一致 |

多 seed 汇总示例：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --data_dir G:\CISCN\dataset\TwiBot-22-lgb-compact `
  --dataset TwiBot-22 `
  --text_features_path G:\CISCN\dataset\TwiBot-22-lgb-compact\lm_sft\lm_features.jsonl `
  --text_encoder roberta_sft_features `
  --seeds 42,43,44,45,46 `
  --out_dir G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict\TwiBot-22 `
  --device cuda
```

该命令输出 `cogguard.kt2.lgb_multiseed_summary.v1`，包含 `accuracy/f1/roc_auc` 的 mean/std；如果提供 `--out_dir`，会自动写入 `lgb_multiseed_summary.json`，供 strict gate 检查。只有当官方 TwiBot-22/TwiBot-20、RoBERTa/T5 SFT 特征、5 seeds 和论文消融都齐全时，才可进入“严格复现完成”判断。

Table III 风格消融调度示例：

```powershell
python -m benchmark.adapters.lgb_bot_detection `
  --data_dir G:\CISCN\dataset\TwiBot-22-lgb-compact `
  --dataset TwiBot-22 `
  --text_features_path G:\CISCN\dataset\TwiBot-22-lgb-compact\lm_sft\lm_features.jsonl `
  --text_encoder roberta_sft_features `
  --seeds 42,43,44,45,46 `
  --ablation_variants full,wo_lm_sft,wo_gnn_finetuning,wo_gnn_pretraining,wo_concat,average_fusion,max_fusion,lm_only `
  --out_dir G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict\TwiBot-22 `
  --device cuda
```

如果提供 `--out_dir`，消融调度会自动写入 `lgb_ablation_suite.json`，供 strict gate 检查。

本地 adapter 当前支持的消融开关：

| 变体 | 对应论文消融 | 本地 adapter 行为 |
|---|---|---|
| `full` | LGB(GCN) full model | LM SFT proxy stage + GCL + GNN concat fusion fine-tuning |
| `wo_lm_sft` | w/o LM supervised fine-tuning | 跳过 semantic classifier 预训练阶段 |
| `wo_gnn_finetuning` | w/o GNN fine-tuning | 跳过最终 GNN 监督微调，仅使用前置阶段参数评估 |
| `wo_gnn_pretraining` | w/o GNN pre-training | 跳过 edge-dropout InfoNCE/GCL 阶段 |
| `wo_concat` | w/o concat | 不拼接语义/结构表示，使用 graph-only 表示进入分类器 |
| `average_fusion` | w/ average fusion | 用平均融合替代 concat |
| `max_fusion` | w/ max fusion | 用 max fusion 替代 concat |
| `lm_only` | supervised fine-tuned LM only | 只使用 semantic classifier，不使用图结构分支 |

边界：这些消融开关让实验形态可调度，但如果输入仍是 `HashingVectorizer` 或非官方数据，就只能作为 local adapter / smoke evidence，不能作为 LGB 论文 Table III 复现结果。

## 完成判定

不能把以下状态写成“严格复现完成”：

- 只跑通合成 smoke fixture。
- 只使用 HashingVectorizer、本地文本代理或传统 ML 特征。
- 只在非 TwiBot-22/TwiBot-20 数据上得到指标。
- 只跑 1 个 seed 或没有 mean ± std。
- 没有报告 Accuracy、F1-Score、ROC-AUC。
- 没有消融或没有按节点连接度分析 isolated/sparse/dense 节点。

可写成完成的最低证据：

1. TwiBot-22 与 TwiBot-20 官方数据准备完成，并记录数据版本、路径、节点/边/标签统计。
2. RoBERTa/T5 统一文本序列 SFT 可运行，并保存节点语义表示。
3. GNN GCL pretraining 可运行，并记录 edge dropout 两视图和 InfoNCE 配置。
4. LGB(GCN) concat fusion fine-tuning 完成 5 seeds，报告 mean ± std 的 Accuracy/F1/ROC-AUC。
5. 至少完成论文 Table III 的核心消融：w/o LM SFT、w/o GNN fine-tuning、w/o GNN pretraining、w/o concat、SFT LM only。
6. KT2 dashboard/API 接入时，只把 LGB 输出显示为“社交机器人风险检测”，不能写成传播规模或下一跳预测结果。
