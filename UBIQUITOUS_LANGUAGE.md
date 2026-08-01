# Ubiquitous Language

This glossary is the canonical vocabulary for CogGuard. Use these names in code, file names, docs, API descriptions, tests, scripts, and research notes. Numbered shorthand is not a domain term and must not be introduced into current system language.

## System Boundary

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Product System** | The runnable backend, frontend, and vendored runtimes under `system/`. | App, platform, product code |
| **Research Package** | System-readable algorithm code under `system/research/`. | Scratch code, notebook, external workspace |
| **Vendored Runtime** | Executable runtime code under `system/runtimes/` used directly by the product. | Upstream repo, external dependency |
| **Reference Boundary** | An upstream repository kept for provenance and diffing only. | Runtime dependency, execution root |
| **Compatibility Alias** | A one-version import path that forwards to a canonical package without owning business logic. | Legacy implementation, second source |
| **Offline Experiment Input** | Local JSONL or fixture data used by a research script and never resolved as a product runtime dependency. | Runtime data, production source |
| **Vendored Data Root** | A data directory owned by a vendored runtime and safe for local system experiments. | Upstream data root, external input |
| **Artifact Manifest** | A reproducibility record that binds a run or model artifact to data, config, and policy metadata. | Metadata, note |
| **Strict Leiden Artifact** | A **Coordination Discover** artifact whose manifest records `partition_backend=leiden`. | NetworkX artifact, smoke artifact |

Current semantic package paths: `system/research/coordination_discover/`, `system/research/coordination_detect/`, `system/research/propagation_analysis/`, `system/research/review_teacher/`, `system/research/social_bot_detection/`, and `system/runtimes/review_student/`.

## Analysis Lifecycle

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Event Snapshot** | An immutable event bundle used as the input seam for unified analysis. | Batch, dataset, payload |
| **Analysis Run** | A persisted execution instance over one snapshot and one ordered stage list. | Job, workflow, request |
| **Analysis Stage** | One item in the ordered analysis chain such as `coordination_discover`, `propagation_analysis`, `student_review`, or `teacher_review`. | Mode, phase, numbered stage |
| **Analysis Port** | A typed seam used by the executor to call **Coordination Discover**, **Propagation Analysis**, **Student Review**, or **Teacher Review**. | Service, plugin |
| **Review Verdict** | A review output produced by **Student Review** or **Teacher Review** before human approval. | Scorecard, opinion |
| **Canonical Verdict** | An analyst-approved immutable verdict version. | Final guess, model output |
| **Model Activation** | The governed decision that selects the active model version pointer. | Deploy, publish |
| **Rollback Decision** | The governed decision to move the active pointer back to a prior version. | Undo, reset |

## Acquisition And Ingestion

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Crawl Request** | The request object for starting an acquisition task. | Search request, job |
| **Crawl Batch** | The batch returned by a crawler after collect. | Dump, raw payload |
| **Raw Post** | A source content item captured from a platform. | Article, feed item |
| **Raw Comment** | A source reply or comment captured from a platform. | Remark, note |
| **Social Runtime** | The vendored social crawler runtime used for `weibo`, `douyin`, and `xhs`. | External crawler, reference repository |
| **News Runtime** | The vendored news extraction runtime used for `news` URLs. | External extractor, reference repository |
| **Mock Platform** | The test-only adapter used for synthetic crawl data. | Production platform |

## Coordination Discover And Detect

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Coordination Signal** | A platform-generic observable cue that multiple accounts acted around the same object or target with temporal proximity. | Platform feature, risk feature, handcrafted feature |
| **Evidence Object** | A shared URL, domain, topic, keyword, entity, target, discussion target, or near-duplicate template referenced by content. | Media object, feature |
| **Evidence Graph** | A temporal graph connecting accounts to **Evidence Objects** through typed observed relations. | Coordination network, feature graph |
| **Coordination Discover** | The unsupervised process that learns temporal coordination structure from an **Evidence Graph**. | Dynamic discover, detection, classifier, scoring rule |
| **Coordination Detect** | A supervised validation layer used on public labeled data to test whether **Coordination Discover** representations improve detection. | Detect validation, main detector, event labeler |
| **Learned Edge Score** | A model-produced weight for an account-object or account-account coordination edge. | Rule score, degree score, fixed weight |
| **Coordination Community** | A group of accounts partitioned from a learned weighted account graph. | Cluster, campaign, botnet |
| **Topology Audit Feature** | A descriptive graph statistic used only for auditing, baselines, or ablations, not as main model input. | Main feature, risk score |
| **Evidence Runtime Fallback** | The `coordination-evidence-runtime-v2` path used when no compatible **Coordination Discover** artifact is available. | Research model, primary method |
| **Platform-Generic Policy** | The rule that excludes video, audio, image, OCR, ASR, and platform-specific media fields from the current main coordination method. | Multimodal policy, media policy |

## Propagation Analysis

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Propagation Forecast** | The output that estimates spread size and next-hop behavior from a snapshot. | Trend guess, prediction blob |
| **Hindcast** | A retrospective propagation forecast over an observed event window. | Backtest, replay |
| **Next-Hop Ranking** | The ordered list of accounts or nodes predicted to be reached next. | Candidate list, neighbor list |
| **Propagation Tree** | A source post and its reply, repost, quote, or reaction descendants. | Thread blob, cascade dump |
| **Split-Conformal Interval** | A calibrated prediction interval derived from a held-out calibration split. | Confidence band, heuristic range |

## Risk Review And Governance

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Risk Review** | The product-facing review capability that evaluates harmfulness, evidence, and governance action needs. | Numbered technology, risk shortcut |
| **Student Review** | The synchronous deployable review model used for preliminary verdicts. | Demo model, inline classifier |
| **Teacher Review** | The asynchronous multi-agent research review pipeline used to generate advisory verdicts. | Chain, workflow, prompt graph |
| **Teacher Job** | The queued asynchronous execution unit for **Teacher Review**. | Task, batch job |
| **Teacher Advisory** | A non-canonical verdict produced by **Teacher Review**. | Final verdict, automatic decision |
| **Review Queue** | The structured set of posts, accounts, communities, retrieval requests, and agent tasks that need review. | Manual queue, task dump |
| **Review Graph** | A heterogeneous graph export of post, account, claim, community, target, media, coordination, and propagation evidence. | Graph dump, feature graph |
| **Teacher Silver Record** | A distillation supervision record derived from approved or replayed teacher review traces. | Pseudo label, generated label |
| **Selective Student** | A student model that predicts main review axes and defers uncertain cases. | Gate model, shortcut classifier |
| **Active Pointer** | The currently selected model-version reference for a review capability. | Default model, live model |

## Account Detection

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Social Bot Detection** | Account-level classification of social automation using learned account representations and approved evidence. | Automation score, activity rule |
| **BotRHG Transfer** | The internal trainable transfer implementation of Reliability-Guided Hypergraph Learning for Social Bot Detection. | NLPCC proxy, graph detector shell |
| **Low-Order Detector** | The first-stage trainable account classifier whose representation and posterior seed reliability routing. | Base rule, heuristic detector |
| **Support Hyperedge** | A target-centered KNN reference set built from learned account representations, excluding the target itself. | Similar-user list, handcrafted neighborhood |
| **Reliability Route** | The label-free top-budget selection of accounts eligible for second-stage correction. | Manual correction list, risk shortcut |
| **Residual Correction** | The learned second-stage fusion of a routed account representation with its support hyperedge representation. | Fixed score adjustment, proxy correction |
| **Text-Only Weibo Transfer** | The current adaptation boundary using labeled Weibo account text while property fields and explicit social graph coverage are unavailable. | Exact paper reproduction, cross-platform claim |

## Relationships

- An **Event Snapshot** feeds one or more **Analysis Stage** executions.
- A **Crawl Request** yields a **Crawl Batch**.
- A **Coordination Signal** creates one or more **Evidence Objects**.
- An **Evidence Graph** links accounts to **Evidence Objects** and preserves relation type plus timestamp.
- **Coordination Discover** consumes an **Evidence Graph** and produces **Learned Edge Scores**.
- **Coordination Communities** are partitioned from learned weighted edges, not from fixed topology scores.
- **Coordination Detect** can consume **Coordination Discover** representations, but it does not label unlabeled project events.
- **Propagation Analysis** consumes an **Event Snapshot** and may emit a **Propagation Forecast**, **Next-Hop Ranking**, and **Propagation Tree** evidence.
- **Risk Review** consumes content, coordination, and propagation evidence and produces a **Review Verdict**.
- **Teacher Review** may create **Teacher Silver Records** for **Selective Student** distillation after governance approval.
- An **Artifact Manifest** must match the snapshot fingerprint before an artifact-first result can serve a backend response.
- A **BotRHG Transfer** artifact must record the dataset fingerprint, checkpoint hash, text sampling policy, missing property/social graph coverage, and same-split reference baseline.
- A **Compatibility Alias** may forward to a canonical package, but it must not be imported by new product code.
- An **Offline Experiment Input** may point to a **Vendored Data Root** or an explicit user path, but never to a reference boundary by default.

## Example Dialogue

> **Dev:** "Should `media_urls` become a **Coordination Signal**?"
>
> **Domain expert:** "Not in this phase. The **Platform-Generic Policy** excludes media-specific objects; shared URLs, domains, targets, entities, topics, and near-duplicate templates are in scope."
>
> **Dev:** "Can I call the review path by the old numbered shorthand in a file name?"
>
> **Domain expert:** "No. Use **Risk Review**, **Student Review**, or **Teacher Review** depending on the boundary. Numbered shorthand is not part of the system language."
>
> **Dev:** "If there is no compatible coordination artifact, what should the backend return?"
>
> **Domain expert:** "Use **Evidence Runtime Fallback** and record the fallback reason explicitly."

## Flagged Ambiguities

- "analysis" can mean product orchestration or a statistical act; use **Analysis Run** or **Analysis Stage** for product code.
- "run", "job", and "task" are distinct; a **run** is a persisted lifecycle instance, a **job** is a queued execution unit, and a **task** is a Celery or worker unit.
- "model" can mean an ML artifact or a database model; use **ML model** or **DB model** when the distinction matters.
- "feature" can mean a model input or a descriptive statistic; use **Coordination Signal** for evidence and **Topology Audit Feature** for audit statistics.
- "community" is not automatically a campaign or botnet; use **Coordination Community** unless human review or external labels justify a stronger claim.
- Numbered shorthand was previously used for the three research workstreams; current code and documentation must use **Coordination Discover/Detect**, **Propagation Analysis**, and **Risk Review** instead.
