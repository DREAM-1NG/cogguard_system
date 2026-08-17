# MARO Teacher + Text Student Implementation Plan

## Purpose and claim boundary

CogGuard implements an evidence-driven Review workbench with two delivery
lines, not a single universal content classifier:

```text
Review Student -> low-cost synchronous task-specific text analysis
Review Teacher -> analyst-triggered MARO-compatible complex-case audit
```

The MARO transfer claim is limited to orchestration: role-separated analysis,
evidence-gap questioning, bounded targeted follow-up, and constrained Judge
integration. MARO's misinformation benchmark result is not evidence that the
same label, prompt, or chain generalizes directly to hate speech, multimodal
consistency, or propagation behavior.

## Mechanism -> assumption -> evidence -> adaptation

| Source | Mechanism | Required assumption | What the source actually supports | CogGuard adaptation |
| --- | --- | --- | --- | --- |
| [MARO, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.291/) | Independent expert analysis, QuestionReflection, targeted follow-up, Judge | Roles expose non-duplicate evidence and questions identify real gaps | Complex misinformation review under the paper's protocol | Necessary experts -> optional reflection -> max two targeted responses -> task-specific Judge |
| [RAG, NeurIPS 2020](https://papers.nips.cc/paper_files/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html) | Non-parametric retrieved context supplements model memory | The corpus is relevant, traceable, and sufficiently authoritative | Knowledge-intensive QA gains from retrieval | Claim-gated `EvidenceRAG`, never global retrieval |
| [Adaptive-RAG, NAACL 2024](https://aclanthology.org/2024.naacl-long.389/) | Select retrieval depth according to query complexity | Complexity predicts retrieval need | Retrieval efficiency/quality trade-off on QA | No claim -> no evidence retrieval; insufficient evidence may request another pass |
| [RECOMP](https://arxiv.org/abs/2310.04408) | Compress retrieved context to task-relevant evidence | Compression preserves decisive spans | Context compression can reduce noise and cost | Preserve source refs and quoted spans in an evidence capsule |
| [RAGAs, EACL 2024](https://aclanthology.org/2024.eacl-demo.16/) | Evaluate retrieval and grounded generation separately | Automatic metrics correlate enough with human assessment | A decomposed RAG evaluation interface | Measure coverage, source traceability, relation validity, citation coverage, and clause match separately |
| [HateCOT, Findings EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.343/) | Explanation-enhanced harmful-speech supervision | Explanation is task-relevant and quality is bounded | Explanation can help offensive-speech transfer under its protocol | Use explanation only for a harm rationale projection; do not call it a faithful CoT |
| [TinyBERT](https://aclanthology.org/2020.findings-emnlp.372/) | Distill accessible predictions/representations into a smaller encoder | Teacher and Student spaces/tasks are alignable | Encoder distillation for matched tasks | Align typed rationale vectors and hard/structured labels, not black-box Agent hidden states |
| [Distilling Step-by-Step](https://aclanthology.org/2023.findings-acl.507/) | Use explanations as additional supervision | Explanations are correct and Student can represent the signal | Rationale supervision can improve small models on supported tasks | Use short quality-gated capsules as auxiliary loss only |
| [ERASER](https://aclanthology.org/2020.acl-main.408/) | Separate prediction quality from rationale quality | Comparable spans or explanation annotations exist | Faithfulness/plausibility need independent metrics | Report label metrics and span/capsule metrics separately |
| [ContextAware, IJCAI 2025](https://www.ijcai.org/proceedings/2025/1103) | Specialized multimodal roles and task-specific fusion | Modalities and conflict labels are available | Specific image-comment harm task performance | Keep multimodal consistency as a later candidate, not a current claim |

The mechanism cards and source notes are also recorded in
`G:\CISCN\teamwork_projects\cogguard_research\LITERATURE_MECHANISM_ASSUMPTION_PROOF_ADAPTATION.md`.

## Current implementation

### Review Teacher

The runtime stores `review_task` as one of:

- `interpersonal_harm`: PostHarmAgent plus active policy context;
- `claim_deception`: ClaimEvidenceAgent first performs claim assessment; only a
  `checkable` claim may enter EvidenceRAG.

The existing runtime still supports legacy expert names for compatibility, but
capability filtering prevents an inapplicable claim, media, or propagation
expert from being called unless an analyst explicitly forces it. Simple mode
executes necessary experts and one Judge. Complex mode executes the bounded
MARO chain. Countermeasure is appended only when the analyst explicitly
selects it and only after Judge.

When `review_task` is explicit, the planner also scopes expert selection:
`interpersonal_harm` selects PostHarmAgent and `claim_deception` selects
ClaimEvidenceAgent. An invalid or missing claim does not get substituted with a
harm expert; it remains a non-relational claim-assessment state and forces the
Judge's factual-risk axis to `unavailable`. Each provider
payload is projected by role so PostHarmAgent does not receive claim evidence,
ClaimEvidenceAgent does not receive media payloads, and Judge/Countermeasure
receive typed bundles plus compact case summaries rather than the full raw
context.

### Retrieval contracts

- `EvidenceRAG` returns claim, query, source references, quoted spans, relation,
  retrieval status, publication time, and snapshot metadata. Local retrieval
  remains unverified until relation validation is supplied by a provider.
- `PolicyRAG` filters inactive documents and returns versioned policy clauses.
  Policy clauses are advisory and cannot overwrite fact evidence or detector
  outputs.
- `ReasonBank` is a rationale/example lookup for offline analysis; it is not an
  evidence source.

### Claim evidence state invariant

The implementation follows the task decomposition in
[FEVER](https://aclanthology.org/N18-1074/),
[MultiFC](https://aclanthology.org/K19-1046/),
[CheckThat!](https://doi.org/10.1007/978-3-031-28241-6_59), and
[AVeriTeC](https://aclanthology.org/2024.fever-1.1/):

1. `claim_assessment` is `not_assessed`, `checkable`,
   `no_verifiable_claim`, or `extraction_failed`.
2. `retrieval_status` is an execution state, including skipped, provider
   unavailable/failed, completed with no relevant evidence, and completed.
3. `evidence_relation` is `not_applicable` until the claim is checkable and
   completed retrieval supplies traceable sources and quoted spans. Only then
   can `supported`, `contradicted`, `conflicting`, or `insufficient` be emitted.

This is an implementation conformance correction, not a claimed research
novelty. The full source-grounded comparison is recorded in
[`claim-deception Teacher/RAG review`](../../research-wiki/literature_runs/20260815T132401Z-cogguard-claim-deception-teacher-review-rag-prov/report.md).

### Review Student

`XLMRTextifiedReviewStudent` keeps separate interpersonal-harm and
claim-deception heads, optional fine-label/stance heads, and rationale
projection heads. The current canonical input is primary text and hashtags;
derived OCR/ASR/caption fields remain behind a legacy compatibility option and
do not constitute raw-media understanding.

The default supervision contract is:

```text
gold hard labels
+ quality-gated structured Teacher labels/spans
+ optional rationale capsule alignment
```

Teacher confidence, Teacher probabilities, full Agent reports, raw retrieval
documents, and DISARM reasoning paths remain audit artifacts. Student
calibration is a separate validation concern, not a Teacher-confidence target.

### Hard-case candidates

`build_review_hard_case_pool.py` reads Student prediction records and creates a
stratified, gold-free manifest using entropy, evidence conflict, OOD score, and
dataset/task coverage. It never calls Teacher, reads test labels, or writes
silver data. Production activation remains:

```text
Student -> internal Hard-Case Candidate -> analyst Review API -> Teacher
```

## Reference implementations

The following shallow clones are external coding references only:

| Repository | Local path | Commit | License-file status | Use |
| --- | --- | --- | --- | --- |
| [MARO](https://github.com/Brtulien/MARO) | `G:\CISCN\references\cogguard-methods\MARO` | `20aea25462c5ee55af5bf777084a0eb8553b8920` | `LICENSE` | Teacher chain and prompt/data organization |
| [HateCOT](https://github.com/hnghiem-nlp/hatecot) | `G:\CISCN\references\cogguard-methods\HateCOT` | `64444acf646303abbc6db075bd93a33f8559974d` | no standalone file found | explanation-enhanced harm supervision |
| [Adaptive-RAG](https://github.com/starsuzi/Adaptive-RAG) | `G:\CISCN\references\cogguard-methods\Adaptive-RAG` | `0c88670af8707667eb5c1163151bb5ce61b14acb` | `LICENSE` | retrieval-depth routing reference |
| [RAGAs](https://github.com/vibrantlabsai/ragas) | `G:\CISCN\references\cogguard-methods\RAGAs` | `298b68274234c060deacab3cf5fb52aa3a20e885` | `LICENSE` | RAG evaluation interface |
| [Distilling Step-by-Step](https://github.com/google-research/distilling-step-by-step) | `G:\CISCN\references\cogguard-methods\Distilling-Step-by-Step` | `ef944263c9ddfd40a9888557f3e7d17513fd1a7e` | `LICENSE` | explanation supervision reference |
| [IRCoT](https://github.com/StonyBrookNLP/ircot) | `G:\CISCN\references\cogguard-methods\IRCoT` | `3c1820f698eea5eeddb4fba3c56b64c961e063e4` | `LICENSE` | iterative retrieval boundary |
| [DPR](https://github.com/facebookresearch/DPR) | `G:\CISCN\references\cogguard-methods\DPR` | `a31212dc0a54dfa85d8bfa01e1669f149ac832b7` | `LICENSE` | dense evidence retrieval baseline |
| [Huawei Pretrained-Language-Model](https://github.com/huawei-noah/Pretrained-Language-Model) | `G:\CISCN\references\cogguard-methods\Pretrained-Language-Model` | `0598f02d7fc4eaa7b4cbc1e9d7ab18bc875c24f` | `LICENSE` | TinyBERT and pretraining reference |

These repositories are not copied into `system/`, imported by production code,
or added as Python dependencies.

## Verification and deferred work

This coding stage verifies contracts, call bounds, importability, and the
gold-free hard-case manifest only. It deliberately does not run dataset
training, DeepSeek/API calls, RAG quality experiments, Teacher cost/latency
benchmarks, continuous pretraining, or multimodal consistency. Those require
separate experiment protocols and independent result-to-claim review.
