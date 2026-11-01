# KT2 角色证据人工抽查指南

## 审核目的

本文件用于把 `role_evidence` 从审计 `partial` 推进到 `passed`。审核对象是已观测传播图上的角色解释，不是未来传播预测，也不是监督学习标签。

## 输入与输出

- 待填写模板：`benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review_template.csv`
- 审计读取文件：`benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review.csv` 或同目录 `manual_review.csv`
- 本地审核页：`benchmark\kt1_role_evidence_validation\analysis\ROLE_EVIDENCE_REVIEW.html`
- 抽样行数：`8` / 可用行数 `8`

## 抽样角色分布

- `普通参与者`: 1
- `桥接`: 5
- `起爆/源头`: 2

## 审核字段

- `review_pass`：必填。支持 `true/false`、`pass/fail`、`yes/no`、`1/0`。
- `evidence_match`：必填，说明路径、时间、结构指标是否支持角色判断。
- `confidence_1to5`：必填 1 到 5 的主观置信度。
- `reviewer`：必填，便于追溯审核责任；`review_timestamp`、`reviewer_note` 建议填写。
- `reason_if_fail`：当 `review_pass=false` 时必填。

## 通过标准

- 至少有 1 条人工审核记录。
- 所有样本都应填写可识别的 `review_pass` 值，不要留空。
- 所有样本都应填写 `reviewer`、`evidence_match` 和 `confidence_1to5`。
- 所有不通过样本都应填写 `reason_if_fail`。
- `review_pass` 通过率必须大于等于 0.8。
- 第一次审核前先初始化待填写 CSV，然后打开 HTML/证据包逐条审核：

```powershell
python -m benchmark.role_evidence_review init --template benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review_template.csv --output benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review.csv
python -m benchmark.role_evidence_review status
python -m benchmark.role_evidence_review validate --review-file benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review.csv
python -m benchmark.experiment_audit
python -m benchmark.completion_gate
```

说明：`status` 会检查模板、证据包和最终审核 CSV 是否齐全；`validate` 是比审计更严格的预检查，要求所有抽样行都填写。只有 `benchmark.experiment_audit` 中 `manual_review_records` 变为 `passed` 且 `benchmark.completion_gate` 返回 `passed`，KT2 才能判断达到 full validation。
