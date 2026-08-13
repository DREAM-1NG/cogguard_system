# Semantic Model Selection And Governance

## Status

All models below are pinned **candidate** dependencies for a future `semantic_enrichment` analysis stage. No local evaluation, activation, Chinese-domain quality claim, calibration claim, or production readiness claim exists in Task 01.

The Case Workbench uses semantic material only as evidence-linked descriptive artifacts. Artifacts and corrections cannot feed or alter Coordination Discover, Propagation Analysis, Student Review, Teacher Review, preliminary finding, canonical verdict, or any core risk score.

## Pin Set

| Capability | Exact candidate | Input/output | Required artifact provenance |
| --- | --- | --- | --- |
| Shared embedding | `BAAI/bge-small-zh-v1.5@7999e1d` | Normalized post/comment/claim text -> embedding cache. | Model/revision, tokenizer/config identity, input hash, scope hash, vector-cache hash. |
| Sentiment | `lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110` | One scoped document -> auxiliary sentiment distribution. | Model/revision, label mapping, raw prediction, status, input/output hashes. |
| Stance | `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92` | Document plus selected exact primary claim -> claim-relative stance candidate. | Claim ID/content hash, model/revision, premise/hypothesis template version, raw output, status. |
| NER | `shibing624/bert4ner-base-chinese@5d660ed` | Chinese text -> candidate entity spans/types. | Model/revision, document hash, raw spans, normalized spans, status. |

The strings are immutable governance identifiers, not a statement that the local bytes or their upstream model cards have been verified yet. The implementation must store an artifact/file hash after acquiring an approved local copy; a remote repo revision alone is insufficient for activation.

## Execution Boundary

```text
EventSnapshot revision
  -> SemanticScope (time/platform/community/path/content-type)
  -> separate post documents + comment documents
  -> sequential CPU-first model execution
  -> SemanticArtifacts (candidate_unvalidated)
  -> optional SemanticCorrection (original prediction retained)
  -> Case Workbench descriptive projection only
```

### Scope rules

- Posts and comments are two separate populations. No aggregate sentiment/topic/stance number may silently mix them.
- Each request stores a half-open time window, platform allowlist, selected Coordination community IDs, optional propagation path IDs, selected content types, ordering rule, and a canonical JSON SHA-256 scope hash.
- A model sees only items admitted by the recorded scope. Every attempted artifact write appends a new immutable row, including an identical input/scope/model rerun. Each row carries a per-link/per-artifact-type monotonic attempt version plus run, input, scope, model, and output hashes; no retry updates an old row.
- Entities/keywords/topics may link to an evidence item, but link creation does not change an evidence assessment or risk result.

### CPU and availability rules

- Load the candidates sequentially to bound memory. CPU is the required baseline; a later accelerator path must report device/model artifact identity and preserve output equivalence tests.
- No unpinned remote fallback is allowed. A missing model, incompatible tokenizer, or inference error writes a typed terminal artifact failure with cause and affected capability.
- A stance request without a selected valid primary claim returns `blocked_missing_primary_claim` for stance. It does not prevent embeddings, MMR, topic, sentiment, NER, Coordination, Propagation, or Review from running.

## Auxiliary Methods

### KeyBERT-style MMR

Use the shared BGE embedding cache for documents and candidate n-grams. For a selected document, rank candidate phrases by cosine relevance and use Maximal Marginal Relevance with captured parameters:

```text
MMR(candidate) = lambda * relevance(document, candidate)
                 - (1 - lambda) * max_similarity(candidate, selected)
```

Persist `lambda`, candidate-generation configuration, top-k, tokenizer version, selected phrase IDs, and input/output hashes. The `KeyBERT` upstream documentation is an implementation reference only; this is not a claim that the resulting keywords are validated Chinese entities or claims.

### BERTopic-style clustering and c-TF-IDF

Cluster post documents and comment documents independently over the shared embedding cache. Produce topic labels from class-based TF-IDF only after a cluster is formed. Persist the clustering configuration, c-TF-IDF vocabulary/config hash, topic-to-document mapping hash, and topic artifact status. A topic is never a coordination community and must not be used as a case verdict feature.

The implementation must use packages already available in the repository. Any future Chinese tokenizer addition needs a local comparison that documents the tokenization failure, selected package/version, license, evaluation corpus, and rollback plan.

## Corrections And Feedback

Semantic correction is immutable:

| Field | Requirement |
| --- | --- |
| `original_prediction_json` | Exact original model output copied when correction is created. |
| `original_prediction_hash` | SHA-256 of the canonical original prediction payload. |
| `corrected_value` | Analyst-supplied replacement or abstention. |
| `rationale` | Required concise reason with linked evidence. |
| `actor`, `created_at` | Authenticated identity and server timestamp. |
| `SemanticArtifact` | Never updated to replace the original. A correction targets one immutable artifact attempt; projection renders correction alongside it. |

Feedback can refer to a correction but cannot mutate it. Feedback scoped to a canonical verdict must belong to the same CaseRecord, EventSnapshot revision, and CaseAnalysisLink.

## Promotion Gate

`candidate_unvalidated` is the only Task 01 state. A later promotion must be an audited evaluation record covering all items below:

1. Frozen local corpus manifest and content hashes, with post/comment/platform strata.
2. Explicit tasks and gold/analyst adjudication rules for sentiment, stance, NER, keyword relevance, and topic coherence/stability as applicable.
3. Split strategy that prevents event/time leakage; report population size and excluded data.
4. Per-stratum metrics, confidence intervals where applicable, error analysis, abstentions, and calibration/reliability evidence.
5. Exact local model bytes/checksum, code revision, runtime version/device, prompt/template version for stance, tokenizer/configuration, and reproducible command.
6. A comparison against no-semantic projection proving that artifact creation and correction creation leave Coordination, Propagation, Student, Teacher, preliminary finding, canonical verdict, and every core risk field unchanged.
7. Analyst correction/feedback agreement analysis and an explicit decision on whether output remains candidate-only.

The evaluation result may permit a display-status change, but it cannot make a semantic model automatically create a canonical verdict or action.

## Epistemic Limits

- Hugging Face model cards and upstream GitHub readmes identify source version and documented intended use. They do not prove Chinese-event effectiveness, cross-platform transfer, safety, bias behavior, or operational latency in CogGuard.
- The uncaptured vendor URLs are unverified discovery references and supply no comparative fact or design evidence.
- A semantic artifact may describe a document, but it does not prove coordination, intent, authenticity, causality, or harm.
- The current benchmark CSV is separate Twitter data and cannot establish the proposed models' performance on the case seed.

## Source Record

Source URLs and capture/retention status are in [source-metadata.json](source-metadata.json). The retained [BERTopic](sources/conversions/bertopic-readme-ce5816b8.md) and [KeyBERT](sources/conversions/keybert-readme-e8d74b8d.md) MarkItDown conversions support only the method-level statements above.
