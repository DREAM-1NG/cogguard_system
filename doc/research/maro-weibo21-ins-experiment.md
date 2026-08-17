# MARO Weibo21 INS Experiment

## Scope

This experiment is a local Weibo21 adaptation of MARO's cross-domain
misinformation protocol. It is not an official MARO benchmark reproduction:
the upstream repository leaves its prompts, endpoint configuration, report
paths, and external search provider as placeholders. The reference repository
and commit are recorded in the runner and in
`doc/research/maro-student-rag-implementation-plan.md`.

The task is binary misinformation/rumor detection only. Coordination,
Propagation Analysis, harmful-content axes, multimodal consistency, Student
training, and Countermeasure are outside this experiment.

## Paper-to-code mapping

| Paper mechanism | Local implementation |
| --- | --- |
| Linguistic Feature Analysis Agent | `MAROContentAnalysisAgent` |
| Comment Analysis Agent | `MAROCommentAnalysisAgent`, with comments kept in a separate input view |
| Fact-Questioning -> search -> fact checking | `MAROFactCheckingQuestionAgent` -> configured traceable retriever -> `MAROFactCheckingAgent` |
| Questioning Agent reflection | `MAROQuestionReflectionAgent` -> one bounded response for each of the three analysis dimensions |
| Decision Rule Optimization | `maro_rule_optimization.py`, strict `s_i > s_max` retention, top-10 trajectory |
| Inference | top-`K` returned rules with odd-`K` majority voting |

The analysis-only path does not run a second final Judge. Its reports are
cached and passed to the INS Judge so that the report-generation path matches
the paper's separation between multi-dimensional analysis and decision-rule
evaluation.

## Protocol boundary

The paper reports `Nvt=500`, 100 samples per source domain, `Niter=500`,
`Natt=10`, `K=3`, rule temperature 1, Judge temperature 0, and accuracy/F1.
The paper text also says 8-fold cross-validation, while its Weibo21 tables and
the local snapshot expose 9 domains. The local runner therefore evaluates one
held-out fold per available local domain and records this discrepancy instead
of calling it an exact 8-fold reproduction.

The local adapter uses source domains only to construct validation tasks. A
query receives four demonstrations from four different source domains other
than its own, with two fake and two real labels. The held-out target domain is
never used in rule optimization. Target labels are used only by the evaluator;
the Judge prompt receives the target text and cached analysis, not its label.

## Commands

Inspect the full local protocol without external calls:

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system\system\backend
D:\Anaconda\python.exe -u scripts\run_maro_weibo21_ins_experiment.py `
  --output-dir G:\CISCN\.tmp\maro_weibo21_ins_dry_run `
  --dry-run
```

Run a small real pilot after setting `DEEPSEEK_API_KEY` and the configured
traceable retrieval provider in the current process only:

```powershell
D:\Anaconda\python.exe -u scripts\run_maro_weibo21_ins_experiment.py `
  --output-dir G:\CISCN\.tmp\maro_weibo21_ins_pilot `
  --target-domains 科技 `
  --validation-tasks 20 `
  --samples-per-source-domain 20 `
  --max-iterations 5 `
  --max-attempts 2 `
  --max-target-cases 20 `
  --enable-retrieval
```

For the paper-default local adaptation, omit the pilot overrides and use all
nine target domains. `--max-target-cases 0` is required to evaluate every
target-domain case; the default cap of 100 is an explicitly reported local
evaluation cap to prevent accidental API-cost explosions.

## Outputs and metrics

The runner writes `analysis_cache.jsonl`, one fold report under
`folds/<domain>/`, per-case predictions, `judge_audit.jsonl`,
`report.partial.json`, and final `report.json`. The final report contains
validation rule trajectories, accepted and returned rules, target accuracy,
macro-F1, positive fake F1/precision, execution-integrity audit fields, and
the protocol comparison notes.

MARO performance metrics always use every submitted target row. The INS parser
follows the released repository's explicit-label, numeric, penultimate-paragraph,
and similarity fallback sequence, so every non-empty Judge response becomes a
binary prediction. Empty responses or provider failures are retried; exhaustion
fails the whole run rather than excluding rows from the metric denominator.
`judge_audit.jsonl` is retained for execution review only and never gates a
prediction or changes a classification metric.

## Run record: 2026-08-16

The valid pilot is stored at
`G:\CISCN\.tmp\maro_weibo21_ins_pilot_tech_protocol_v2_20260816\report.json`.
It used DeepSeek Chat, the configured Exa provider, 20 cross-domain validation
tasks, three rule-generation iterations, three returned rules, and a balanced
20-item held-out `科技` target sample. The analysis cache contains 40 cases:
20 validation queries and 20 target queries. The target labels are not present
in the Judge input bundle and are read only by the final evaluator.

| Measure | Value |
| --- | ---: |
| Target Accuracy | 0.9000 |
| Target Macro-F1 | 0.9000 |
| Positive-fake F1 | 0.9000 |
| Positive-fake Precision | 0.9000 |
| Confusion matrix (`gold -> prediction`) | `harmful -> harmful=9`, `harmful -> non_harmful=1`, `non_harmful -> harmful=1`, `non_harmful -> non_harmful=9` |
| Validation Judge calls | 80 |
| Target Judge calls | 60 |
| Judge retries | 0 |

All 20 target examples received exactly three binary votes. All 140 Judge
responses were parsed from an explicit final label. The first v2 output in the
same directory used only one returned rule when no candidate strictly improved
the baseline; it is superseded and must not be used. The v3 report fixes this
by preserving strict improvement for `best_rule` while selecting the top three
scored candidates from the complete optimization trajectory, matching the
paper's top-10 trajectory and top-`K` inference mechanism.

The paper reports `74.60 Acc. / 75.51 F1` averaged over Weibo21 with
GPT-3.5-turbo-0125 under its reported 8-fold setup. Its Science-domain row is
`66.66 Acc. / 63.82 F1`. This pilot is not numerically comparable: it uses
DeepSeek, a locally converted snapshot, a different held-out domain name and
20 target cases rather than the paper's full folds, and the released repository
does not provide the paper prompts or endpoint configuration. For 18 correct
predictions out of 20, the 95% Wilson interval for accuracy is approximately
`[0.699, 0.972]`; it is too wide to establish equivalence or superiority.

Decision: do not trigger the nine-domain, paper-scale run from this pilot. A
paper-scale run would require 500 validation tasks and up to 500 optimization
iterations per fold, creating a material number of additional external LLM and
retrieval calls without a comparable pilot gate. The next valid escalation is a
pre-registered local protocol with a full held-out target domain, fixed model
and prompts, and an explicit cost budget; it remains a local adaptation rather
than an official MARO reproduction.

## Run record: 2026-08-16 concurrency calibration and full-domain attempt

A 50-case analysis-only calibration at concurrency `8` completed with the
configured DeepSeek and Exa providers. It recorded 441 logical DeepSeek calls
and 138 logical Exa calls, zero provider failures, zero retries, and zero HTTP
429 events. Mean completed latency was 5.005 seconds for DeepSeek and 4.168
seconds for Exa. The calibration report is
`G:\\CISCN\\.tmp\\maro_weibo21_provider_calibration_50_c8_20260816\\calibration_report.json`.

The first full-domain invocation accidentally inherited the runner's
paper-default `500` validation tasks and `500` optimization iterations because
the explicit local-budget arguments were omitted. It generated a reusable
analysis-stage cache but failed during Judge validation. Its output directory,
`G:\\CISCN\\.tmp\\maro_weibo21_priority_full_c16_20260816`, is an execution
artifact only: it contains no valid fold report and must not be used for
accuracy or F1 claims.

The runner now supports `--seed-analysis-cache` for a read-only, same-config
analysis cache and records non-secret provider HTTP/retry telemetry in
`judge_audit.jsonl`. Per-call telemetry is task-local, so concurrent calls do
not overwrite each other's audit values. A corrected local full-target command
used `20` validation tasks, `3` optimization iterations, `3` returned rules,
all cases in `政治` / `灾难事故` / `科技`, and concurrency `16`. It failed before
any fold metric when every first-round Judge request returned DeepSeek HTTP
`402`. This is an account availability or quota condition, not a classification
result, RAG quality result, or a MARO protocol outcome.

The corrected run directory is
`G:\\CISCN\\.tmp\\maro_weibo21_priority_full_c16_v20_i3_r3_seeded_20260816`.
The blocked state is reproducible from its `judge_audit.jsonl`; no target
prediction file or `report.json` exists. Resume only after DeepSeek provider
capacity is restored, using the explicit budgeted command and the existing
seed cache. Do not use the seed cache across a changed model, prompt, retrieval
provider, retrieval depth, input profile, or analysis protocol.

## Run record: 2026-08-16 stratified sampled evaluation

After the provider became available, the local evaluation was rerun in a clean
directory:
`G:\\CISCN\\.tmp\\maro_weibo21_stratified_3domain_final_c8_20260816`.
The effective protocol was fixed before execution: target domains `政治`,
`灾难事故`, and `科技`; 50 target cases per domain; exactly 25 fake and 25
real cases; 20 cross-domain validation tasks; 3 optimization iterations; 3
returned rules; concurrency 8; and no target labels in any Judge input.

| Held-out domain | Target cases | Accuracy | Macro-F1 | Target rule votes | Judge audit records |
| --- | ---: | ---: | ---: | ---: | ---: |
| 政治 | 50 (25/25) | 0.8200 | 0.81935 | 150 | 230 |
| 灾难事故 | 50 (25/25) | 0.6600 | 0.65 | 150 | 190 |
| 科技 | 50 (25/25) | 0.7800 | 0.78 | 150 | 230 |
| Mean | 150 | 0.753333 | 0.750822 | 450 | 650 |

Every target row has one prediction and three rule votes; all 150 target rows
remain in the metric denominator. The disaster fold has 190 rather than 230
Judge audit records because one proposed rule duplicated an already accepted
rule and was skipped by the released optimization logic; it still returned
three distinct trajectory rules and evaluated 150 target votes. This is not a
missing-target or defer condition.

The clean run reused the completed analysis cache from the preceding provider
run, so its own telemetry reports 659 new DeepSeek calls and zero new Exa calls.
The cached analysis records contain the traceable retrieval audits produced in
the preceding run; therefore this result is a cached-analysis plus fresh-rule-
and-target-Judge evaluation, not a fresh Exa retrieval ablation. Provider
telemetry recorded zero DeepSeek/Exa failures and zero 429 events for the clean
run. The output is a local, sampled MARO adaptation on Weibo21, not an official
MARO reproduction and not evidence that the method matches the paper's
GPT-3.5/AMTCele/MC_Fake protocol.

## Run record: 2026-08-16 all-domain live retrieval evaluation

The follow-up all-domain run used a new output directory and did not pass
`--seed-analysis-cache`, so the analysis stage performed live provider calls:
`G:\\CISCN\\.tmp\\maro_weibo21_all9_stratified_live_exa_c8_20260816`.
The protocol remained fixed at 50 target cases per domain, exact 25/25 label
stratification, 20 validation tasks, three optimization iterations, three
returned rules, and concurrency 8. The local snapshot contains 9,128 source
rows and 9,095 unique case instances.

| Held-out domain | Accuracy | Macro-F1 | Target cases | Target rule votes |
| --- | ---: | ---: | ---: | ---: |
| 财经商业 | 0.88 | 0.88 | 50 (25/25) | 150 |
| 教育考试 | 0.68 | 0.64 | 50 (25/25) | 150 |
| 军事 | 0.80 | 0.80 | 50 (25/25) | 150 |
| 科技 | 0.68 | 0.66 | 50 (25/25) | 150 |
| 社会生活 | 0.70 | 0.70 | 50 (25/25) | 150 |
| 文体娱乐 | 0.84 | 0.84 | 50 (25/25) | 150 |
| 医药健康 | 0.76 | 0.75 | 50 (25/25) | 150 |
| 灾难事故 | 0.70 | 0.68 | 50 (25/25) | 150 |
| 政治 | 0.86 | 0.859944 | 50 (25/25) | 150 |
| Mean | 0.766667 | 0.757093 | 450 | 1,350 |

All nine target folds have 50 unique predictions and exact label balance. The
target metric denominator is the full 450 rows; there is no defer or coverage
filter. Technology and entertainment have 210 Judge audit records rather than
230 because a duplicate candidate rule was skipped during validation, while
each still received 150 target votes and three returned rules.

The run made 1,446 successful Exa calls and no Exa failures or retries. It made
6,989 DeepSeek logical calls; 8 provider-level failures were recorded, while
the completed run emitted no provider-error target Judge records.
The final report is therefore a genuine live-retrieval sampled evaluation, not
a cache replay. It remains a local Weibo21 adaptation and is not an official
MARO AMTCele/MC_Fake reproduction; the paper's reported setup, prompts, model,
and full cross-validation protocol are different.
