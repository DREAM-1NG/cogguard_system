# MARO-Compatible HateCoT Harm Experiment

## Purpose And Boundary

This study tests a **MARO-compatible interpersonal-harm Teacher** on a fixed,
sampled HateCoT cross-domain protocol. It is not an official reproduction of
[MARO](https://aclanthology.org/2025.emnlp-main.291/): MARO studies binary
cross-domain misinformation detection, while this study evaluates three-way
text harm classification.

The transfer keeps MARO's mechanism of source-only validation rule
optimization, strict-improvement retention, a ranked rule pool, and a separate
Judge. It deliberately does **not** transfer its fact-questioning, external
search, comment analysis, or fake/real label space to harmful-language
classification.

The Teacher chain is:

```text
PostHarmAgent -> local advisory policy-reference selection
              -> QuestionReflectionAgent
              -> one PostHarmAgent refinement
              -> independent rule-conditioned HarmfulnessJudgeAgent
```

The policy source is the local public-governance reference library. It is not
an external EvidenceRAG call, is not factual evidence, and cannot supply a
dataset label or an enforcement decision. This run made zero Exa calls.

## Data Protocol

Source data: `G:\CISCN\dataset\HateCoT\hatecot_final_D3.csv`, associated
with [HateCoT](https://aclanthology.org/2024.findings-emnlp.343/) and its
[public repository](https://github.com/hnghiem-nlp/hatecot).

The raw CSV has 52,137 rows. It contains three exact copies of each eligible
`domain + id` record. The loader retains 16,937 unique, Agent-visible cases;
33,874 exact duplicate rows are removed. A duplicate with different text,
raw label, mapped label, domain, or target causes the run to fail.

| Normalized class | Source labels |
| --- | --- |
| `non_harmful` | Benign, Neutral, Normal, Not Hate, Not Hate Speech, Not Offensive |
| `offensive` | Offensive, Toxic, Derogation, Person Directed Abuse |
| `hate` | Hate, Hate Speech, Hateful, Identity Directed Abuse, Affiliation Directed Abuse, Dehumanization |
| excluded | Animosity |

`Animosity` (1,326 source rows before duplicate removal) is excluded because
its boundary against offensive and hate is not stable enough for silent
three-way remapping.

Only `cad`, `dynahate`, and `toraman` contain all three normalized classes, so
only they are eligible held-out target domains. Dataset `label` and
`explanation` are never sent to any Teacher role. HateCoT explanations remain
dataset-provided supervision for the separate XLM-R LRKD study; they are not
human gold rationales and are not used in this Teacher evaluation.

## Executed Protocol

Final output: `G:\CISCN\.tmp\maro_hatecot_harm_final_dedup_contract_c8_20260816\report.json`.

- One leave-one-domain-out fold for each of `cad`, `dynahate`, and `toraman`.
- 30 source-only validation tasks per fold, balanced across three labels.
- Each validation task uses one demo per label from distinct non-query source
  domains. This is a necessary three-way adaptation, not MARO's original
  `2 fake + 2 real` demonstration layout.
- At most 100 source cases per domain, 3 rule-optimization iterations, 3
  consecutive non-improvement limit, and 3 returned rules.
- Exactly 20 frozen target cases per class per domain: 60 target cases/fold,
  180 target cases total.
- DeepSeek Chat, temperature 0 for analysis/Judge and 1 for rule proposals,
  timeout 45 seconds, provider retries 0, concurrency 8.
- Every Judge output must end in `JUDGMENT: 0|1|2`; a malformed output is
  retried and exhaustion fails the run. One validation format retry occurred;
  no target case was removed from metrics.

The original MARO binary odd-vote property does not prevent a three-way
`1-1-1` tie. The runner records this explicit adaptation: if a tie occurs, it
uses the first returned rule, which is ranked first by source-validation
accuracy. No tie occurred in the final 180 target predictions.

## Results

Label order for every matrix is `non_harmful`, `offensive`, `hate`; rows are
gold labels and columns are predictions.

| Held-out domain | Cases | Accuracy | Macro-F1 | Per-class F1 (`non_harmful / offensive / hate`) | Confusion matrix |
| --- | ---: | ---: | ---: | --- | --- |
| `cad` | 60 | 0.533333 | 0.499496 | 0.586207 / 0.578947 / 0.333333 | `[[17,3,0],[9,11,0],[12,4,4]]` |
| `dynahate` | 60 | 0.600000 | 0.602186 | 0.685714 / 0.439024 / 0.681818 | `[[12,7,1],[3,9,8],[0,5,15]]` |
| `toraman` | 60 | 0.533333 | 0.444092 | 0.703704 / 0.533333 / 0.095238 | `[[19,1,0],[8,12,0],[7,12,1]]` |
| Mean | 180 | 0.555555 | 0.515258 | not pooled | not pooled |

Execution audit:

- 250 unique analysis records; all have an internally valid PostHarm and
  reflection sidecar (`parse_error=0`).
- All 250 records have an input-grounded span, a matched advisory policy
  clause, and a quality-gated `RationaleCapsule`.
- All 180 target rows received exactly three rule votes and remain in the
  denominator; no tie-break was invoked.
- DeepSeek: 1,600 completed logical calls, zero provider failures, zero 429
  events, mean completed latency 2.037 seconds, maximum in-flight 8.
- Exa: zero calls.

## Interpretation

The experiment establishes that the MARO mechanism can be **executed and
audited** for text-only interpersonal harm under an explicit three-way
adaptation. It does not establish general performance parity with MARO,
because the task, model, dataset, and protocol differ.

Macro-F1 of 0.515258 is insufficient to claim a strong cross-domain harm
Teacher. The chief errors are hate cases predicted as non-harmful or offensive
in `cad` and especially `toraman`. The output must therefore not replace the
existing gold-label HateCoT Student training, and the 180 held-out target rows
must never be used for Student training or distillation.

The quality-gated capsules show that the *artifact contract* now works, not
that the Teacher rationale is correct. Before Teacher-generated harm capsules
enter Student loss, run the Teacher only over a disjoint source/train or
Student hard-case pool, retain gold labels as primary supervision, and compare
gold-only Student versus gold-plus-capsule training on a frozen target test
set. Teacher probabilities, full traces, rule text, and target-fold outputs
remain audit-only.

## Implementation

- `system/backend/app/core/review/maro_harm_protocol.py`: PostHarm,
  reflection, advisory policy references, literal input-span validation, and
  rationale-capsule gate.
- `system/backend/app/core/review/hatecot_harm_experiment.py`: label mapping,
  duplicate integrity checks, target sampling, and three-way evaluation.
- `system/backend/app/core/review/maro_rule_optimization.py`: explicit label
  space and demonstration-plan support while preserving the default binary
  MARO behavior.
- `system/backend/scripts/run_maro_hatecot_harm_experiment.py`: live offline
  experiment runner, audit artifacts, and strict final-label parsing.

Targeted validation command:

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system\system\backend
.\.venv\Scripts\python.exe -m pytest -q `
  tests\test_maro_rule_optimization.py `
  tests\test_maro_harm_protocol.py `
  tests\test_hatecot_harm_experiment.py `
  tests\test_maro_hatecot_harm_experiment.py
```

## Expanded Protocol (2026-08-17)

The next registered protocol supersedes the small 20-per-class sample for
method development. It keeps the same three-way label mapping and target
domains, but uses an exact 100-per-class held-out target sample in each fold
(900 target cases total). For every target fold, all non-target cases are
stratified by `domain + normalized_label` into an 80/20 `source-train` /
`source-dev` split with `random_state=42`.

Each fold constructs 120 balanced source-train tasks and 120 balanced
source-dev tasks, with 40 queries per label. Rule proposals see only the
source-train trajectory and its accuracy. Rejected rules are not eligible for
the candidate pool. After proposal generation, source-dev ranks the fixed pool
by Macro-F1 and Accuracy; it does not send feedback to the proposer. The final
three selected rules are run on every held-out target case.

The main arm is `policy_context_mode=off`. The optional `local_advisory` arm
uses the same manifests and candidate pool, with isolated analysis-cache
namespaces. It is a local governance-context ablation, not evidence that
PolicyRAG has learned domain adaptation. There is no Exa, fact retrieval,
defer, coverage, abstention, Student/LRKD, Countermeasure, or multimodal
component in this protocol.

The runner writes split manifests, rule trajectories, source-dev scores,
predictions, confusion matrices, audit records, and a protocol manifest. Each
fold includes a protocol hash over the MARO harm protocol version, label
mapping, split hashes, policy arm, and run parameters. `--resume` only accepts
an exact hash match; stale reports fail closed. A Judge provider or format
failure after retries fails the run instead of changing the target metric
denominator.
