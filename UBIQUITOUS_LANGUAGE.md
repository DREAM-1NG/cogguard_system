# Ubiquitous Language

This glossary is the canonical vocabulary for CogGuard. Use these names in code, docs, UI copy, and research notes.

## System Boundary

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Product System** | The runnable backend, frontend, and vendored runtimes under `system/`. | App, platform, product code |
| **Research Package** | System-readable algorithm code under `system/research/`. | Scratch code, notebook, external workspace |
| **Vendored Runtime** | Executable runtime code under `system/runtimes/` used directly by the product. | Upstream repo, external dependency |
| **Reference Boundary** | An upstream repository kept for provenance and diffing only. | Runtime dependency, execution root |
| **Artifact Manifest** | A reproducibility record that binds a run or model artifact to data, config, and policy metadata. | Metadata, note |
| **Strict Leiden Artifact** | A KT1 artifact whose manifest records `partition_backend=leiden`. | NetworkX artifact, smoke artifact |

## Analysis Lifecycle

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **EventSnapshot** | An immutable event bundle used as the input seam for unified analysis. | Batch, dataset, payload |
| **AnalysisRun** | A persisted execution instance over one snapshot and one ordered stage list. | Job, workflow, request |
| **Analysis Stage** | One item in the ordered analysis chain such as `kt1`, `kt2`, `student`, or `teacher`. | Mode, phase, step |
| **Analysis Port** | A typed seam used by the executor to call KT1, KT2, Student, or Teacher. | Service, plugin |
| **ReviewVerdict** | A review output produced by Student or Teacher before human approval. | Scorecard, opinion |
| **Canonical Verdict** | An analyst-approved immutable verdict version. | Final guess, model output |
| **Model Activation** | The governed decision that selects the active model version pointer. | Deploy, publish |
| **Rollback Decision** | The governed decision to move the active pointer back to a prior version. | Undo, reset |

## Acquisition And Ingestion

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **CrawlRequest** | The request object for starting an acquisition task. | Search request, job |
| **CrawlBatch** | The batch returned by a crawler after collect. | Dump, raw payload |
| **Raw Post** | A source content item captured from a platform. | Article, feed item |
| **Raw Comment** | A source reply or comment captured from a platform. | Remark, note |
| **Social Runtime** | The vendored social crawler runtime used for `weibo`, `douyin`, and `xhs`. | MediaCrawler main, external crawler |
| **News Runtime** | The vendored news extraction runtime used for `news` URLs. | NewsCrawler main, external extractor |
| **Mock Platform** | The test-only adapter used for synthetic crawl data. | Production platform |

## KT1 Coordination Discovery

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Coordination Signal** | A platform-generic observable cue that multiple accounts acted around the same object or target with temporal proximity. | Platform feature, risk feature, handcrafted feature |
| **Evidence Object** | A shared URL, domain, topic, keyword, entity, target, discussion target, or near-duplicate template referenced by content. | Media object, feature |
| **Evidence Graph** | A temporal graph connecting accounts to **Evidence Objects** through typed observed relations. | Coordination network, feature graph |
| **Coordination Discover** | The unsupervised KT1 process that learns temporal coordination structure from an **Evidence Graph**. | Dynamic Discover, detection, classifier, scoring rule |
| **Coordination Detect** | A supervised validation layer used on public labeled data to test whether **Coordination Discover** representations improve detection. | Detect Validation, main detector, Trump-event labeler |
| **Learned Edge Score** | A model-produced weight for an account-object or account-account coordination edge. | Rule score, degree score, fixed weight |
| **Coordination Community** | A group of accounts partitioned from a learned weighted account graph. | Cluster, campaign, botnet |
| **Topology Audit Feature** | A descriptive graph statistic used only for auditing, baselines, or ablations, not as main model input. | Main feature, risk score |
| **Evidence Runtime Fallback** | The `coordination-evidence-runtime-v2` path used when no compatible KT1 artifact is available. | Research model, primary method |
| **Platform-Generic Policy** | The KT1 rule that excludes video, audio, image, OCR, ASR, and platform-specific media fields from the current main method. | Multimodal policy, media policy |

## KT2 Propagation

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Propagation Forecast** | The KT2 output that estimates spread size and next-hop behavior from a snapshot. | Trend guess, prediction blob |
| **Hindcast** | A retrospective propagation forecast over an observed event window. | Backtest, replay |
| **Next-Hop Ranking** | The ordered list of accounts or nodes predicted to be reached next. | Candidate list, neighbor list |
| **Split-Conformal Interval** | A calibrated prediction interval derived from a held-out calibration split. | Confidence band, heuristic range |

## KT3 Review And Governance

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Student Runtime** | The synchronous deployable review model used for preliminary verdicts. | Demo model, inline classifier |
| **Teacher DAG** | The asynchronous multi-agent review pipeline used to generate advisory verdicts. | Chain, workflow, prompt graph |
| **Teacher Job** | The queued asynchronous execution unit for the Teacher DAG. | Task, batch job |
| **Teacher Advisory** | A non-canonical verdict produced by the Teacher path. | Final verdict, automatic decision |
| **Active Pointer** | The currently selected model-version reference for a technology. | Default model, live model |

## Relationships

- An **EventSnapshot** feeds one or more **Analysis Stage** executions.
- A **CrawlRequest** yields a **CrawlBatch**.
- A **Coordination Signal** creates one or more **Evidence Objects**.
- An **Evidence Graph** links accounts to **Evidence Objects** and preserves relation type plus timestamp.
- **Coordination Discover** consumes an **Evidence Graph** and produces **Learned Edge Scores**.
- **Coordination Communities** are partitioned from learned weighted edges, not from fixed topology scores.
- **Coordination Detect** can consume **Coordination Discover** representations, but it does not label the three-platform Trump event.
- An **Artifact Manifest** must match the snapshot fingerprint before **Artifact-First KT1** can serve a backend result.
- A **Strict Leiden Artifact** is required before KT1 outputs can be used as research evidence.

## Example Dialogue

> **Dev:** "Should `media_urls` become a **Coordination Signal** for KT1?"
>
> **Domain expert:** "Not in this phase. The **Platform-Generic Policy** excludes media-specific objects; shared URLs, domains, targets, entities, topics, and near-duplicate templates are in scope."
>
> **Dev:** "Can I use degree or density in the main model?"
>
> **Domain expert:** "No. Those are **Topology Audit Features** for audit and ablation. **Coordination Discover** should learn **Learned Edge Scores** from the temporal **Evidence Graph**."
>
> **Dev:** "If there is no compatible artifact, what should the backend return?"
>
> **Domain expert:** "Use **Evidence Runtime Fallback** and record the fallback reason explicitly."

## Flagged Ambiguities

- "analysis" can mean the product orchestration layer or the statistical act of reasoning; use **AnalysisRun** or **Analysis Stage** when referring to product code.
- "run", "job", and "task" are distinct; a **run** is a persisted lifecycle instance, a **job** is a queued execution unit, and a **task** is a Celery or worker unit.
- "model" can mean an ML artifact or a database model; use **ML model** or **DB model** when the distinction matters.
- "feature" can mean a model input or a descriptive statistic; use **Coordination Signal** for evidence and **Topology Audit Feature** for audit statistics.
- "community" is not automatically a campaign or botnet; use **Coordination Community** unless human review or external labels justify a stronger claim.
