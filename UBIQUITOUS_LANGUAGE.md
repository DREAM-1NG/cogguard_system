# Ubiquitous Language

This glossary is the canonical vocabulary for CogGuard. Use these names in code, file names, docs, API descriptions, tests, scripts, and research notes. Numbered shorthand is not a domain term and must not be introduced into current system language.

Use `Coordination Discover`, `Coordination Detect`, `Propagation Analysis`, and `Review`. Do not introduce numbered capability aliases.

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
| **Static Delivery Build** | The canonical frontend build that typechecks, emits content-addressed assets, creates a **Delivery Preload Plan**, and verifies delivery budgets. | Dev build, preview build |
| **Delivery Preload Plan** | Build-time metadata that prepares only static route assets after authentication or navigation interaction; it never requests case data, runs analysis, or warms a model. | Data warmup, analysis warmup |

Current semantic package paths: `system/research/coordination_discover/`, `system/research/coordination_detect/`, `system/research/propagation_analysis/`, `system/research/review_teacher/`, `system/research/social_bot_detection/`, and `system/runtimes/review_student/`. These are runtime/research-only boundaries; do not use them in product copy.

## Event Review Case

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Event Review Case** | The product-facing aggregate that binds one event, its evidence, its advisory history, and its analyst decision trail. | Ticket, issue, review job |
| **Preliminary Finding** | The first structured case finding produced before analyst confirmation. | First guess, preliminary score |
| **Review Advisory** | An internal or manually requested advisory verdict that can differ from the preliminary finding. | Final verdict, automatic decision |
| **Review Audit** | A bounded read-only projection of a persisted review advisory run, including stages, source excerpts, queries, and available short rationale capsules. | Model trace, final verdict, chain-of-thought dump |
| **Confirmed Decision** | The immutable analyst-confirmed case decision. | Mutable decision, draft approval |
| **Evidence Sufficiency** | The assessment of whether the current evidence set is enough to support a case action. | Completeness score, confidence score |
| **Evidence Annotation** | A note attached to a specific evidence item, including its assessment and supporting context. | Comment, tag, annotation blob |
| **Case Activity** | An append-only business activity record that explains what happened to a case and when. | Audit spam, task log |
| **Semantic Evidence Assistance** | Auxiliary, model-derived evidence projections such as keywords, topics, sentiment, stance, and entities that help an analyst inspect an Event Review Case without changing its conclusions. | Semantic enrichment, semantic result, model conclusion |
| **Authority Source Account** | A reviewed exact binding from an allowlisted Authority Source to one platform account. Platform verification is preserved as evidence but does not itself establish authority. | Official-looking account, verified media guess |
| **Claim Response Landscape** | An observed Propagation Analysis view that aligns a bound authority claim, official account publications, influential account responses, and their path evidence. A direct comment path is valid only when its `post_id` matches the bound authority publication; nested comment ancestry uses only recorded `reply_to` values. | Fact checker, public opinion verdict |
| **Claim Response Path Semantic Overlay** | A read-only aggregation of sentiment, raw NLI stance, keywords, topics, entities, platforms, time range, and evidence references for one direct-comment path. It is emitted only when every canonical path reference maps to a ready non-fallback semantic-layer item. | Path label, inferred stance, propagation score |

## Internal Analysis Lifecycle

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Event Snapshot** | An immutable event bundle used as the input seam for unified analysis. | Batch, dataset, payload |
| **Analysis Run** | A persisted execution instance over one snapshot and one ordered stage list. | Job, workflow, request |
| **Analysis Stage** | One item in the ordered analysis chain such as `coordination_discover`, `propagation_analysis`, `student_review`, or `teacher_review`. | Mode, phase, numbered stage |
| **Analysis Port** | A typed seam used by the executor to call `Coordination Discover`, `Propagation Analysis`, `Student Review`, or `Teacher Review`. | Service, plugin |
| **Review Verdict** | A review output produced by `Student Review` or `Teacher Review` before human approval. | Scorecard, opinion |
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
| **Evidence-Constrained Discovery** | The system **Coordination Discover** mainline that discovers candidate coordination groups from observable account-object evidence, time proximity, weighted graph construction, and community lineage. | MAGNN mainline, GFM discovery, classifier discovery |
| **Coordination Discover** | The label-free process that resolves cross-platform evidence and discovers candidate coordination groups from an **Evidence Graph**. | Dynamic discover, detection, classifier, scoring rule |
| **Coordination Detect** | The governed runtime that consumes **Coordination Discover** output and an active detection artifact to emit harmful/benign coordination evidence hints. | Detect validation only, final verdict, event labeler |
| **SocGFM Cross-Attention Detection** | The offline deep Detection family used to produce account-level IO membership probabilities from SocGFM-style text/graph experiments. | Logistic mainline, heuristic detector, final CIB judge |
| **China Checkpoint Local Precompute** | The G-drive offline bridge that loads the official China SocGFM CrossAttention/SAGE `model0.pth` through `model4.pth`, builds local account text/graph features, executes Torch/PyG forward, and writes precomputed account probabilities for Coordination Detect v1. | Online neural forward, internal fusion checkpoint, group-level harmful F1 |
| **Precomputed Member Probability Aggregation** | The deployed SocGFM v1 inference mode that aggregates precomputed account-level probabilities and cluster features into cluster-level proxy verdict hints without online neural forward. | Live Cross-Attention forward, group-level harmful F1, heuristic fallback |
| **Historical Detection Projection** | A read-time group-level projection reconstructed only from persisted member predictions and stored Coordination Community membership when an archive artifact has no materialized `coordination_detection` block. | New inference, heuristic completion, automatic decision |
| **Shadow Coordination Classifier** | The retained learned/logistic detector used for backend audit, rollback comparison, and research tables but not frontend primary display. | Primary classifier, fallback detector |
| **Coordination Archive Replay** | The legacy dataset-registry rerun surface for historical MAGNN/Leiden/SBERT results, used for visualization and comparison but not as the current **Coordination Detect** primary output. | Current Detection run, primary model, live SocGFM inference |
| **MAGNN-Leiden Hybrid Discovery** | A research-only **Coordination Discover** candidate that learns relation-aware account embeddings and edge affinities on the evidence-constrained graph, then uses Leiden only as the community explanation head. | System discovery, deprecated MAGNN, production model |
| **Learned Edge Score** | A scored weight for an account-object or account-account coordination edge. | Rule score, degree score, fixed weight |
| **Coordination Community** | A group of accounts partitioned from a learned weighted account graph. | Cluster, campaign, botnet |
| **Topology Audit Feature** | A descriptive graph statistic used only for auditing, baselines, or ablations, not as main model input. | Main feature, risk score |
| **Evidence Runtime Mainline** | The `coordination-evidence-runtime-v2` path used as the system **Evidence-Constrained Discovery** implementation. | Research model, fallback-only method |
| **Platform-Generic Policy** | The rule that excludes video, audio, image, OCR, ASR, and platform-specific media fields from the current main coordination method. | Multimodal policy, media policy |

## Propagation Analysis

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Propagation Forecast** | The output that estimates spread size and next-hop behavior from a snapshot. | Trend guess, prediction blob |
| **Hindcast** | A retrospective propagation forecast over an observed event window. | Backtest, replay |
| **Next-Hop Ranking** | The ordered list of accounts or nodes predicted to be reached next. | Candidate list, neighbor list |
| **Propagation Tree** | A source post and its reply, repost, quote, or reaction descendants. | Thread blob, cascade dump |
| **Split-Conformal Interval** | A calibrated prediction interval derived from a held-out calibration split. | Confidence band, heuristic range |

## Review Runtime And Governance

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Review** | The product-facing review capability that evaluates harmfulness, evidence, and governance action needs. | Numbered technology, shortcut |
| **Student Review** | The synchronous deployable review runtime used for preliminary verdicts. Runtime-only term. | Demo model, inline classifier |
| **Teacher Review** | The asynchronous multi-agent research review pipeline used to generate advisory verdicts. Runtime-only term. | Chain, workflow, prompt graph |
| **Teacher Job** | The queued asynchronous execution unit for **Teacher Review**. | Task, batch job |
| **Teacher Advisory** | A non-canonical verdict produced by **Teacher Review**. | Final verdict, automatic decision |
| **Review Queue** | The structured set of posts, accounts, communities, retrieval requests, and review tasks that need attention. | Manual queue, task dump |
| **Review Graph** | A heterogeneous graph export of post, account, claim, community, target, media, coordination, and propagation evidence. | Graph dump, feature graph |
| **Teacher Silver Record** | A distillation supervision record derived from approved or replayed teacher review traces. | Pseudo label, generated label |
| **Selective Student** | Historical compatibility terminology for the retired student defer-head design; it is not the target architecture for the current Review Student. | Gate model, defer classifier, current Student |
| **Review Student** | The low-cost synchronous text encoder that predicts independent Review task axes and emits auxiliary rationale projections. | Unified risk classifier, defer model |
| **Review Teacher** | The analyst-triggered asynchronous MARO-compatible expert chain that produces an advisory report and typed sidecars. | Automatic reviewer, final verdict |
| **Claim Assessment** | The explicit state that says whether a supplied or extracted statement is an externally checkable factual claim. | Missing claim, evidence insufficiency |
| **Retrieval Status** | The execution and coverage state of a claim retrieval attempt, independent of factual truth. | Evidence relation, truth label |
| **Evidence Relation** | The relation between a checkable claim and completed, traceable quoted evidence. | Provider result, retrieval score |
| **EvidenceRAG** | Claim-gated retrieval of traceable external evidence; it may not query a raw post before **Claim Assessment** is `checkable`. | General web search, policy search |
| **PolicyRAG** | Retrieval of currently effective governance clauses and allowed/prohibited action references. | Fact evidence, legal authority |
| **ReasonBank** | Offline retrieval of rationale examples for analysis or auxiliary supervision; it cannot establish factual support. | Evidence store, truth database |
| **Rationale Capsule** | A short rationale linked to input spans and, when applicable, evidence or policy references, subject to a quality gate. | Full chain of thought, confidence explanation |
| **Hard-Case Candidate** | An offline Student-derived manifest row selected for later analyst or explicitly authorized Teacher review. | Deferred prediction, automatic escalation |
| **Active Pointer** | The currently selected version reference for a review capability. | Default model, live model |
| **Model Candidate** | A registered, versioned model artifact that is eligible for review but is not yet selected by an Active Pointer. | Live model, deployed model |
| **Model Candidate Approval** | An authenticated administrator action that verifies a candidate artifact and its capability gates before recording approval evidence. | Caller-supplied approval, automatic activation |
| **Model Activation Approval** | An immutable database record linking one Model Candidate to one authenticated administrator; the records are the evidence used by the deployment approval policy. | Approval flag, approver list |
| **Deployment Approval Policy** | The environment-specific rule for the number of distinct active administrators required before Model Activation. | UI approval setting, client policy |
| **Teacher Dispatch Policy** | The environment-specific rule that determines whether Teacher Review may use local inline execution or must use a durable queue. | Silent fallback, in-process queue |

## MARO-Compatible Harm Evaluation

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **HateCoT Harm Adaptation** | The text-only three-way MARO-compatible research protocol that applies source-domain rule optimization to interpersonal-harm labels. | Official MARO reproduction, hate misinformation model |
| **Source-Train Pool** | The source-domain cases visible to rule proposal and strict-improvement evaluation. | Training set, target support |
| **Source-Dev Pool** | A disjoint source-domain case pool used only to rank the fixed candidate rules after proposal generation. | Validation feedback loop, proposer set |
| **Held-Out Target Test** | The target-domain sample whose labels are withheld from every prompt and read only for final metrics. | Target training set, support pool |
| **Strict Candidate Rule** | A rule retained only when its source-train accuracy strictly exceeds the current best rule. | Prompt variant, rejected rule |
| **Local Advisory Policy Context** | A fixed local governance reference context used as an ablation and audit aid, not as a label source or semantic PolicyRAG adaptation. | Policy-trained classifier, factual evidence |
| **Fold Protocol Hash** | A digest of the MARO protocol version, split manifests, label mapping, policy arm, and run parameters used to authorize resume. | Cache key, model hash |

## Relationships

- A **Source-Train Pool** generates **Strict Candidate Rules**; a **Source-Dev Pool** ranks them but never feeds scores back to the proposer.
- A **Held-Out Target Test** is evaluated only after the **Source-Dev Pool** selects the final odd rule set.
- **Local Advisory Policy Context** is independent of the primary policy-off arm and cannot alter the declared harm label space.
- A **Fold Protocol Hash** must match before a persisted fold report or current analysis cache can be resumed.

## Account Detection

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Social Bot Detection** | Account-level classification of social automation using learned account representations and approved evidence. | Automation score, activity rule |
| **Fixed-Graph Research Runtime** | A hash-verified runtime that replays or queries predictions for a fixed benchmark graph and is not an online model activation source. | Online detector, active model |
| **Account Finding** | The concise analyst-facing conclusion projected from Social Bot Detection for an Account Profile. | Bot probability, automation rating, model result panel |
| **Account Profile** | The business-facing view of a collected account, including nickname, platform, activity context, recent public posts, and an Account Finding. | User scorecard, detection dashboard |
| **BotRHG Transfer** | The internal trainable transfer implementation of Reliability-Guided Hypergraph Learning for Social Bot Detection. | NLPCC proxy, graph detector shell |
| **Low-Order Detector** | The first-stage trainable account classifier whose representation and posterior seed reliability routing. | Base rule, heuristic detector |
| **Support Hyperedge** | A target-centered KNN reference set built from learned account representations, excluding the target itself. | Similar-user list, handcrafted neighborhood |
| **Reliability Route** | The label-free top-budget selection of accounts eligible for second-stage correction. | Manual correction list, risk shortcut |
| **Residual Correction** | The learned second-stage fusion of a routed account representation with its support hyperedge representation. | Fixed score adjustment, proxy correction |
| **Text-Only Weibo Transfer** | The current adaptation boundary using labeled Weibo account text while property fields and explicit social graph coverage are unavailable. | Exact paper reproduction, cross-platform claim |
| **Account Detection Case** | A platform-scoped account case built from collected posts with evidence post ids, provenance, and a stable fingerprint. | User row, profile card |
| **Account Detection Label** | The minimal task label `human`, `bot`, or `insufficient_evidence`; richer signals remain evidence or reason tags. | Identity label, attribution label, invented behavior class |
| **Account Label Batch** | A stratified active-learning batch selected for analyst labeling under a fixed budget. | Training batch, pseudo-label set |
| **Approved Account Corpus** | A versioned training corpus exported only from approved or adjudicated account behavior labels. | Active-learning selected pool |
| **Cold-Start Acquisition** | Label selection before a reliable account ranker exists; uses surprisal, diversity, coverage, and random audit rather than classifier uncertainty. | Uncalibrated uncertainty sampling |
| **Warm-Start Acquisition** | Label selection after a versioned account ranker exists; uses uncertainty, disagreement, OOD, representativeness, and diversity only for review priority. | Model score as label |
| **Random Audit Slice** | A small random portion of each label batch used to monitor selection bias and reviewer drift. | Noise, filler items |
| **Frozen Holdout** | A manually approved evaluation split that is never selected by active learning and never used for training. | Validation set, sampled queue |
| **Shadow Account Model** | A candidate account detector evaluated in parallel before it can become the active model. | Production model, default model |
| **Approved Corpus Training** | Training that consumes a versioned **Approved Account Corpus** through the `approved_account_corpus` dataset adapter. | JSONL shortcut, pseudo-label training |
| **Account Model Approval Evidence** | Immutable active-administrator approval rows required before a **Shadow Account Model** can become active. | Caller-supplied approval, analyst approval |

## Relationships

- An **Event Snapshot** feeds one or more **Event Review Case** revisions.
- An **Event Review Case** surfaces a **Preliminary Finding**, **Evidence Sufficiency**, optional **Review Advisory**, and an optional **Confirmed Decision**.
- An **Evidence Annotation** belongs to one immutable evidence item and can update the case activity stream.
- Automatic routing can request an internal review advisory after successful collection when evidence sufficiency or urgency warrants it.
- A **Coordination Signal** creates one or more **Evidence Objects**.
- An **Evidence Graph** links accounts to **Evidence Objects** and preserves relation type plus timestamp.
- **Evidence-Constrained Discovery** consumes an **Evidence Graph** and produces candidate **Coordination Communities** with auditable evidence references.
- **MAGNN-Leiden Hybrid Discovery** may produce **Learned Edge Scores** in offline research, but it is not the system **Coordination Discover** mainline.
- **Coordination Communities** are partitioned from weighted evidence edges or research learned edges, not from a harmfulness label.
- **Coordination Detect** consumes **Coordination Discover** communities and a governed active artifact; its output is an evidence hint and does not replace a **Confirmed Decision**.
- **SocGFM Cross-Attention Detection** produces account-level IO probabilities offline; **China Checkpoint Local Precompute** is the local bridge for uploaded unlabeled data, and **Precomputed Member Probability Aggregation** is the frontend-visible primary **Coordination Detect** result in v1.
- A **Historical Detection Projection** may aggregate persisted real member predictions into a group evidence hint, but it must return `model_unavailable` when those predictions are absent; it cannot invent a group verdict.
- The **Shadow Coordination Classifier** remains backend-only unless an analyst explicitly inspects diagnostics.
- A **Coordination Archive Replay** may expose historical account scores as `archive_detection_*` audit fields, but `node_score` in the Coordination workspace is a **Coordination Discover** evidence score.
- **Propagation Analysis** consumes an **Event Snapshot** and may emit a **Propagation Forecast**, **Next-Hop Ranking**, and **Propagation Tree** evidence.
- A **Claim Response Path Semantic Overlay** is auxiliary evidence for one observed path only. It never creates a path, supplies an uncomputed downstream-reach value, or changes a **Propagation Analysis** or **Review** conclusion.
- **Review** consumes content, coordination, and propagation evidence and produces a **Review Verdict**.
- **Teacher Review** may create quality-gated **Teacher Silver Records** for **Review Student** auxiliary supervision after the appropriate review and provenance checks.
- **Review Student** may create a **Hard-Case Candidate**, but only an analyst Review API request activates **Review Teacher** in production.
- **EvidenceRAG**, **PolicyRAG**, and **ReasonBank** are separate retrieval boundaries; policy text cannot be treated as factual evidence, and factual retrieval cannot authorize a governance action.
- An **Evidence Relation** is `not_applicable` until **Claim Assessment** is `checkable` and **Retrieval Status** is completed with traceable sources and quoted spans; only then can it be `supported`, `contradicted`, `conflicting`, or `insufficient`.
- **Rationale Capsules** are auxiliary supervision artifacts, not faithful reconstructions of an Agent chain or causal explanations.
- An **Artifact Manifest** must match the snapshot fingerprint before an artifact-first result can serve a backend response.
- A **Model Candidate Approval** creates at most one **Model Activation Approval** per candidate and authenticated administrator.
- Production **Model Activation** requires two distinct active administrator records, including the activating administrator; local activation requires one accountable operator.
- A **Teacher Dispatch Policy** may allow local inline fallback only in local deployments. Production dispatch failure is a durable failed advisory, never an API-process success.
- A **BotRHG Transfer** artifact must record the dataset fingerprint, checkpoint hash, text sampling policy, missing property/social graph coverage, and same-split reference baseline.
- A **Fixed-Graph Research Runtime** must record its node mapping, split provenance, checkpoint hash, and deployment scope; it must never become the Chinese account-model **Active Pointer**.
- An **Account Label Batch** only selects review priorities; it is not an **Approved Account Corpus** until analysts approve or adjudicate labels.
- **Approved Corpus Training** excludes `insufficient_evidence` / `abstain` rows from binary supervised BotRHG training.
- A **Shadow Account Model** cannot become active unless the **Frozen Holdout**, leakage, calibration, checkpoint-hash, persisted-metrics, and **Account Model Approval Evidence** gates pass.
- A **Compatibility Alias** may forward to a canonical package, but it must not be imported by new product code.
- An **Offline Experiment Input** may point to a **Vendored Data Root** or an explicit user path, but never to a reference boundary by default.

## Example Dialogue

> **Dev:** "What should the workspace show when evidence is thin?"
>
> **Domain expert:** "Use a **Preliminary Finding** with low **Evidence Sufficiency**, and keep the case open for more evidence."
>
> **Dev:** "Can the product copy mention the internal runtime labels?"
>
> **Domain expert:** "No. Use **Event Review Case**, **Preliminary Finding**, **Review Advisory**, and **Confirmed Decision** in product copy; keep runtime-only terms inside engineering docs."
>
> **Dev:** "If there is no compatible coordination detection artifact, what should the backend return?"
>
> **Domain expert:** "Return `model_unavailable`; **Coordination Detect** must not pretend a heuristic or shadow classifier is the active model."

## Flagged Ambiguities

- "analysis" can mean product orchestration or a statistical act; use **Event Review Case** for product copy and **Analysis Run** for internal diagnostics.
- "review" is the product capability; use **Review Advisory** or **Confirmed Decision** when the distinction matters.
- "run", "job", and "task" are distinct; a **run** is a persisted lifecycle instance, a **job** is a queued execution unit, and a **task** is a Celery or worker unit.
- "model" can mean an ML artifact or a database model; use **ML model** or **DB model** when the distinction matters.
- A **Model Candidate** is not an active model. Use **Model Candidate Approval** for the action and **Model Activation Approval** for the persisted evidence record.
- "feature" can mean a model input or a descriptive statistic; use **Coordination Signal** for evidence and **Topology Audit Feature** for audit statistics.
- "community" is not automatically a campaign or botnet; use **Coordination Community** unless human review or external labels justify a stronger claim.
- "Detection" can mean a system evidence hint or a research superiority claim; use **Coordination Detect** for the governed runtime and state separately whether a paper/result claim is supported.
- "MAGNN" can mean the deprecated TemporalMAGNN-style runtime, the retained `magnn_legacy` baseline, or the new **MAGNN-Leiden Hybrid Discovery** candidate; name the exact method in code and reports.
- Numbered shorthand was previously used for the three research workstreams; current code and documentation must use **Coordination Discover**, **Coordination Detect**, **Propagation Analysis**, and **Review** instead.
- "MARO" can mean the official binary misinformation protocol or this three-way **HateCoT Harm Adaptation**; always state the dataset, label space, and protocol boundary.
- "policy context" can mean local advisory governance text or semantic PolicyRAG retrieval; use **Local Advisory Policy Context** for this experiment and do not conflate them.
