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

## Case Investigation

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Case** | A long-lived investigative aggregate that preserves immutable evidence, analysis, claims, decisions, actions, feedback, reports, semantic records, and audit history for one bounded inquiry. | Event, project, report |
| **Case Workbench** | The dense case-level page that keeps lifecycle status, the **Primary Claim**, and active **Case Blockers** visible across investigation tabs. | Dashboard, specialist page, report page |
| **Case State** | One lifecycle value from `draft`, `collecting`, `evidence_ready`, `analyzing`, `awaiting_review`, `actioning`, `ready_to_close`, or `closed`. | Analysis status, blocker, phase |
| **Case Blocker** | A separately persisted condition that prevents a named case operation without impersonating a **Case State**. | Blocked state, warning, error state |
| **Authority Source** | An administered registry record for a source account or publisher eligible to support authoritative claims. | Trusted URL, verified post, allowlisted article |
| **Source Tier** | The administered classification of an **Authority Source** as government or official institution, central mainstream media original, or provincial official media. | Credibility score, source rank, confidence |
| **Case Claim** | An authoritative-source evidence record containing a verbatim excerpt, exact source span, URL, account, publication time, **Source Tier**, and content hash. | Topic, generated summary, analyst paraphrase |
| **Primary Claim** | The single approved **Case Claim** that anchors stance and **Risk Review** for a **Case**. | Main topic, inferred claim, headline |
| **Supplementary Claim** | An approved or pending **Case Claim** that adds authoritative context without replacing the **Primary Claim**. | Secondary verdict, supporting summary |
| **Semantic Artifact** | An immutable, provenance-bound output of the explicit `semantic_enrichment` **Analysis Stage**. | Tag cache, model guess, score input |
| **Semantic Correction** | An append-only human correction that references a **Semantic Artifact** and preserves both the original output and the correction rationale. | Artifact edit, overwrite, relabel in place |
| **Case Action** | A required, completed, or explicitly waived disposition record attached to a **Case**. | Task, note, recommendation |
| **Closeout Review** | The recorded human check that closure gates are satisfied and that unresolved limitations remain visible. | Canonical Verdict, approval click, final report |
| **Case Report Version** | A frozen, versioned HTML report with print-friendly PDF output bound to exact case, snapshot, run, model, and content hashes. | Live report, export view, mutable dashboard |
| **Audit Event** | An append-only record of an actor, action, target, timestamp, request identity, and before/after references for a case mutation. | Log line, history overwrite, activity note |
| **Partial Collection Acknowledgement** | An explicit analyst record accepting known collection incompleteness for a named scope without claiming that evidence is complete. | Ignore warning, complete collection, waiver |
| **Platform Gap** | A **Case Blocker** recording that a required same-event platform source lacks a verifiable archived source. | Empty dataset, fabricated source, unrelated substitute |

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
| **Propagation Monitoring** | The product capability that combines observed propagation analysis and gated propagation prediction for one event snapshot. | Propagation page, numbered shorthand, propagation monitor |
| **Propagation Forecast** | The output that estimates spread size and next-hop behavior from a snapshot. | Trend guess, prediction blob |
| **Observed Propagation Analysis** | A non-predictive reconstruction of paths, objects, roles, provenance, timelines, and stability from the event snapshot. | Forecast, causal proof |
| **Propagation Evidence Type** | `explicit`, `reconstructed`, or `inferred`; respectively platform-observed, parent-ID-rebuilt, or shared-object temporal-proximity evidence. | All edges are reposts |
| **Observation Cutoff** | A timezone-aware inclusive `observed_until` boundary applied before any prediction input or candidate construction. | Optional display time |
| **Hindcast** | A retrospective propagation forecast over an observed event window. | Backtest, replay |
| **Next-Hop Ranking** | The ordered identity-mapped accounts predicted for reactivation after the observation cutoff; anonymous buckets are coverage only. | Candidate list, new-user identity prediction |
| **Candidate Coverage** | The share and count of legal model candidate buckets that can be mapped back to displayable event identities. | Recall proof, complete user universe |
| **Identity Mapping** | The mapping from model bucket or candidate representation back to a real `author_id` and `author_name`. | User recovery, identity proof |
| **Calibration Status** | The explicit state of whether prediction intervals or probabilities have validation-backed calibration evidence. | Confidence, certainty |
| **Abstain** | A structured non-prediction response used when model artifacts, data, identity mapping, or calibration are insufficient. | Fallback prediction, guessed result |
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

- A **Case** references one or more immutable **Event Snapshots**; a snapshot is analysis input, while the case is the durable investigation that outlives any one snapshot or run.
- A **Case** owns zero or more **Analysis Runs**, while an **Analysis Run** executes stages and never represents a **Case State**.
- A **Case State** records lifecycle progress; a **Case Blocker** records an independently resolvable impediment and never adds a synthetic lifecycle value.
- A **Case** may have many **Case Claims** and **Supplementary Claims**, but it must have exactly one approved **Primary Claim** before stance or **Risk Review** can complete.
- A **Case Claim** is a verbatim, source-spanned authority record; a topic, generated summary, or analyst paraphrase is semantic or narrative material and cannot substitute for it.
- **Student Review** and **Teacher Review** produce advisory **Review Verdicts**; analyst approval creates an immutable **Canonical Verdict**, and a later **Closeout Review** verifies closure gates rather than changing that verdict.
- A **Case** can close only after it has an approved **Canonical Verdict**, every required **Case Action** is completed or explicitly waived, and a **Closeout Review** is recorded.
- A **Semantic Correction** points to one **Semantic Artifact** and never overwrites its model output or provenance.
- Each **Case Report Version** freezes the case, snapshot, run, model-version, and content-hash references used to render it.
- Every case mutation emits an **Audit Event**; repeated idempotent requests reuse the prior result without erasing history.
- An **Event Snapshot** feeds one or more **Analysis Stage** executions.
- A **Crawl Request** yields a **Crawl Batch**.
- A **Coordination Signal** creates one or more **Evidence Objects**.
- An **Evidence Graph** links accounts to **Evidence Objects** and preserves relation type plus timestamp.
- **Coordination Discover** consumes an **Evidence Graph** and produces **Learned Edge Scores**.
- **Coordination Communities** are partitioned from learned weighted edges, not from fixed topology scores.
- **Coordination Detect** can consume **Coordination Discover** representations, but it does not label unlabeled project events.
- **Propagation Monitoring** consumes one **Event Snapshot** and separates **Observed Propagation Analysis** from **Propagation Forecast**.
- **Observed Propagation Analysis** never calls prediction code and must preserve **Propagation Evidence Type** provenance.
- **Propagation Forecast** must apply an **Observation Cutoff** before candidate construction and may return **Abstain** instead of a fallback prediction.
- A **Next-Hop Ranking** is displayable only when **Identity Mapping** resolves the candidate to a real event identity.
- **Candidate Coverage** and **Calibration Status** qualify a **Propagation Forecast**; they are not evidence that a future outcome is certain.
- **Propagation Analysis** consumes an **Event Snapshot** and may emit a **Propagation Forecast**, **Next-Hop Ranking**, and **Propagation Tree** evidence.
- **Risk Review** consumes content, coordination, and propagation evidence and produces a **Review Verdict**.
- **Teacher Review** may create **Teacher Silver Records** for **Selective Student** distillation after governance approval.
- An **Artifact Manifest** must match the snapshot fingerprint before an artifact-first result can serve a backend response.
- A **BotRHG Transfer** artifact must record the dataset fingerprint, checkpoint hash, text sampling policy, missing property/social graph coverage, and same-split reference baseline.
- A **Compatibility Alias** may forward to a canonical package, but it must not be imported by new product code.
- An **Offline Experiment Input** may point to a **Vendored Data Root** or an explicit user path, but never to a reference boundary by default.

## Example Dialogue

> **Dev:** "Can an **Event Snapshot** become the investigation record after analysis finishes?"
>
> **Domain expert:** "No. The immutable snapshot remains analysis input; the **Case** keeps every snapshot, run, claim, decision, action, report, and audit record over time."
>
> **Dev:** "If a source is missing, should I move the case into a blocked state and use a generated summary as the claim?"
>
> **Domain expert:** "No. Keep the current **Case State**, add a **Case Blocker**, and wait for a source-spanned **Case Claim**; semantic output cannot become a **Primary Claim**."

## Flagged Ambiguities

- "analysis" can mean product orchestration or a statistical act; use **Analysis Run** or **Analysis Stage** for product code.
- "run", "job", and "task" are distinct; a **run** is a persisted lifecycle instance, a **job** is a queued execution unit, and a **task** is a Celery or worker unit.
- "model" can mean an ML artifact or a database model; use **ML model** or **DB model** when the distinction matters.
- "feature" can mean a model input or a descriptive statistic; use **Coordination Signal** for evidence and **Topology Audit Feature** for audit statistics.
- "community" is not automatically a campaign or botnet; use **Coordination Community** unless human review or external labels justify a stronger claim.
- "case" and "event" are not synonyms; an event is captured in an immutable **Event Snapshot**, while a **Case** is the durable investigation aggregate.
- "claim" is overloaded; use **Case Claim** only for verbatim authority evidence and use topic, generated summary, or analyst paraphrase for derived language.
- "review" can mean advisory model output, approval, or closure checking; use **Review Verdict**, **Canonical Verdict**, or **Closeout Review** respectively.
- "status" can mean execution or lifecycle progress; use **Analysis Run** status for execution and **Case State** for the investigation lifecycle.
- Numbered shorthand was previously used for the three research workstreams; current code and documentation must use **Coordination Discover/Detect**, **Propagation Analysis**, and **Risk Review** instead.
