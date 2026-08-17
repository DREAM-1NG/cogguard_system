# MARO-Compatible HateCoT Benchmark Transfer Evaluation

## Boundary

This record evaluates the existing MARO-compatible interpersonal-harm Teacher
on three downstream benchmarks associated with the HateCoT evaluation context:
HateCheck, HateXplain, and Latent Hate stage one. It is not an official
reproduction of either MARO or HateCoT.

MARO provides the source-validation-only rule optimization, strict-improvement
retention, ranked odd-rule voting, role-specialized analysis, and separate
Judge mechanisms. It does not provide a validated universal harmful-language
label space. The current study therefore declares a target-specific label
contract before each run and never claims a pooled score across benchmarks.

The Teacher chain is unchanged:

```text
PostHarmAgent -> local advisory policy-reference selection
              -> QuestionReflectionAgent
              -> PostHarmAgent refinement
              -> independent rule-conditioned HarmfulnessJudgeAgent
```

No external factual retrieval or Exa call is appropriate for these
post-only harmful-language tasks. The local governance library is advisory
audit provenance, not a gold-label source, fact source, or enforcement rule.

## Executed Protocol

- Source: `G:\CISCN\dataset\HateCoT\hatecot_final_D3.csv`.
- The 52,137 raw rows resolve to 16,937 unique Agent-visible cases after
  removal of 33,874 exact duplicates. `Animosity` is excluded because it has
  no stable mapping in the three-way source taxonomy.
- Source labels are visible only to source-domain validation-rule scoring.
- The target label is excluded from every PostHarm, reflection, rule proposal,
  and Judge prompt. It is read only after prediction for metrics.
- Each benchmark uses 30 source-only validation tasks, 3 rule proposals, an
  odd pool of 3 rules, DeepSeek Chat at concurrency 8, and fixed seed 42.
- Every frozen target sample must receive all three rule votes. Judge format
  failures are retried once and an exhausted retry fails the whole run rather
  than removing a case from the metric denominator.

## Target Contracts

| Benchmark | Local snapshot | Frozen sample | Target labels | Source mapping status |
| --- | --- | ---: | --- | --- |
| HateCheck | 3,728 official test cases | 20/class, 40 total | `non_hateful`, `hateful` | A declared binary collapse: both HateCoT `offensive` and `hate` are source positives. It is not official HateCheck training. |
| HateXplain | 1,924 official test cases | 20/class, 60 total | `normal`, `offensive`, `hate` | Direct audited three-way source-to-target mapping. |
| Latent Hate stage one | 20,391 local TSV rows | 20/class, 40 total | `not_hate`, `implicit_hate` | Explicit proxy. Stage-one latent-hate presence is not annotated by HateCoT, so its two harmful source classes are only a proxy positive class. |

`Latent_Hate` does not use an invented `explicit_hate` class: the local
stage-one snapshot contains only `not_hate` and `implicit_hate`.

## Results

| Benchmark | Cases | Accuracy | Macro-F1 | Per-class F1 |
| --- | ---: | ---: | ---: | --- |
| HateCheck | 40 | 1.000000 | 1.000000 | `non_hateful=1.000000`, `hateful=1.000000` |
| HateXplain | 60 | 0.616667 | 0.607758 | `normal=0.647059`, `offensive=0.410256`, `hate=0.765957` |
| Latent Hate stage one | 40 | 0.750000 | 0.739583 | `not_hate=0.791667`, `implicit_hate=0.687500` |

These scores are intentionally not averaged. The label spaces differ, and the
Latent Hate source mapping is expressly a proxy. HateCheck's perfect score is
also not evidence of broad robustness: it is a single, deterministic 40-case
sample from a templated functional test suite and requires wider functional
and multi-seed sampling before any comparative claim.

The most informative comparable result is HateXplain: the direct three-way
transfer retains a strong `hate` F1 but confuses many `offensive` cases with
`normal` or `hate`. This is consistent with the earlier HateCoT leave-domain
study and is insufficient to establish a strong general-purpose Teacher.

## Execution Audit

- 140/140 selected target cases remained in the metric denominator.
- 750/750 Judge attempts completed; no invalid-format output and no provider
  error occurred.
- Every target Judge input recorded `gold_label_included=false`.
- 140/140 target analyses produced a quality-gated rationale capsule with a
  literal input span and an advisory policy reference.
- DeepSeek completed 1,320 logical calls, with zero retries, zero 429 events,
  zero failed calls, and mean completed latency of 1.886591 seconds.
- Exa completed zero calls.

Passing the artifact gate only proves span/policy traceability. It does not
establish that the Teacher's natural-language rationale is semantically correct.

## Consequence For Student Distillation

No target benchmark output from this run may enter Student training or
distillation. Before Teacher capsules are used as the auxiliary rationale
target, run the Teacher only on a disjoint HateCoT source/train or Student
hard-case pool, quality-gate the capsules, and compare on an untouched target
test split:

```text
gold-only Student
gold + HateCoT explanation LRKD
gold + quality-gated Teacher-capsule alignment
```

Teacher probabilities, raw traces, proposed rules, and these frozen target
outputs remain audit-only.

## Artifacts

- Final report: `G:\CISCN\.tmp\maro_hatecot_benchmark_sampled_20260816\report.json`
- Frozen target manifests and per-case predictions:
  `G:\CISCN\.tmp\maro_hatecot_benchmark_sampled_20260816\benchmarks\`
- Runner: `system/backend/scripts/run_maro_hatecot_benchmark_experiment.py`
- Dataset/label contract: `system/backend/app/core/review/hatecot_harm_benchmarks.py`
- Dynamic Judge contract: `system/backend/app/core/review/maro_harm_benchmark_protocol.py`
