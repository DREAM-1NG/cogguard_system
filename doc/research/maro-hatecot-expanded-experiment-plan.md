# Expanded HateCoT MARO-Compatible Experiment Plan

## Research Boundary

This is a three-way, text-only adaptation of the mechanism described by
[MARO](https://aclanthology.org/2025.emnlp-main.291/) and its
[open-source implementation](https://github.com/Brtulien/MARO). It is not an
official MARO misinformation reproduction: the task, labels, data, and harm
analysis chain differ from the paper's binary misinformation setting.

The adaptation retains source-only decision-rule optimization, strict
improvement, bounded rule search, cross-domain demonstrations, an independent
Judge, and top-three rule voting. HateCoT's `Animosity` label is excluded
because it is not stably mappable to the three declared classes:
`non_harmful`, `offensive`, and `hate`.

## Mechanism And Information Flow

```text
source-train
  -> DeepSeek rule proposal
  -> strict source-train improvement retention
  -> fixed candidate rule pool
source-dev
  -> one-time Macro-F1 ranking
  -> three selected rules
target-test
  -> three Judge calls per case
  -> majority vote
  -> final metrics only
```

The target gold label is not present in any Agent, proposer, analysis, or Judge
prompt. Rejected source-train rules are retained in the audit trajectory but
are excluded from the candidate pool. A failed Judge is a failed run, not an
abstention and not a removed denominator row.

## Data Protocol

- Source CSV: `G:\CISCN\dataset\HateCoT\hatecot_final_D3.csv`.
- Raw rows: 52,137; unique eligible cases after exact duplicate handling:
  16,937.
- Held-out domains: `cad`, `dynahate`, `toraman`.
- Target sample: 100 cases per class/domain, 300 per fold, 900 total.
- Source split: deterministic 80/20 stratification by domain and normalized
  label, `random_state=42`.
- Source tasks: 120 balanced source-train tasks and 120 balanced source-dev
  tasks per fold, 40 queries per class.
- Demonstrations are drawn from distinct non-query source domains and cover
  all three labels.

Every fold stores source/target case IDs, label counts, selection hashes, the
label mapping version, and a no-overlap assertion. The target split is frozen
before any rules are selected.

## Policy Ablation

`policy_context_mode=off` is the primary arm. `local_advisory` adds only the
local public governance reference library to the harm-analysis context. It
does not retrieve external facts, supply labels, change the task definition,
or represent semantic PolicyRAG domain adaptation. The two arms use distinct
analysis-cache namespaces and the same split/candidate-rule protocol.

## Fixed Parameters

```text
max_iterations = 10
max_attempts = 5
returned_rule_count = 3
llm_concurrency = 8
random_state = 42
source_train_fraction = 0.8
```

The runner supports `--dry-run` for no-provider protocol validation and
`--resume` only for exact Fold Protocol Hash matches. The dry-run is a code
and data check, not a performance result. Live DeepSeek execution, Student
distillation, LRKD, multimodal analysis, and Countermeasure are separate
scopes.

## Evidence And Claims

The experiment can support only these claims:

1. The MARO rule-optimization and audit mechanism runs on a three-way HateCoT
   harm task under explicit domain separation.
2. The selected Teacher can be compared across the frozen target domains under
   the stated local protocol.
3. The local advisory context arm can be compared with policy-off as an
   ablation.

It cannot support official MARO reproduction, generalization to visual harm,
semantic PolicyRAG domain adaptation, Student distillation benefit, causal
rationale faithfulness, or a product defer policy.
