# Ubiquitous Language

This glossary is the canonical vocabulary for CogGuard engineering, research,
and agent-assisted development. Code names should use the English terms; Chinese
phrasing can appear in narrative docs when helpful.

## System Boundary

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Product System** | The runnable backend, frontend, deployment config, and tests under `system/`. | app root, new-system |
| **ARIS Workspace** | The research execution workspace under `aris/` for KT1, KT2, and KT3 planning and acceptance. | product code, scratch repo |
| **Reference Boundary** | An upstream or source repository retained for provenance and diffing only. | runtime root, product dependency |
| **Engineering Documentation** | Long-lived project and runnable-system documentation under `doc/engineering/`. | notes, scratch docs |
| **Architecture Decision Record** | A durable decision record under `docs/adr/` explaining why a boundary or method choice changed. | comment, changelog |
| **Documentation Sync** | The required update pass that keeps code, tests, glossary, roadmap, and governance docs aligned after a change. | optional cleanup, later docs |

## Analysis Lifecycle

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Event** | A real-world topic or incident being monitored across platforms. | keyword only, task |
| **Evidence** | Observable content, relation, or metadata used to support a system conclusion. | feature guess, raw noise |
| **Analysis Run** | One persisted execution over a chosen event, dataset, or snapshot. | job, task, workflow |
| **Job** | A queued or asynchronous execution unit such as a crawl or teacher review. | run, task |
| **Task** | A worker-level implementation unit, usually a Celery task or local script step. | run, job |
| **Artifact** | A reproducible output file or directory produced by an experiment, model, or analysis run. | temp file, note |
| **Checkpoint** | Serialized model weights or state used for inference or training resume. | artifact, model version |
| **Model Version** | A governed identifier for a model or runtime contract. | checkpoint path, filename |

## Acquisition

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Crawler** | The acquisition module that collects social or news content into normalized records. | scraper glue, crawler runtime root |
| **Crawl Request** | The user or system request that starts a collection job. | search query, run |
| **Crawl Batch** | The normalized posts, comments, and metadata returned by a crawler. | dump, payload |
| **Raw Post** | A source content item captured from a platform. | article, feed row |
| **Raw Comment** | A reply or comment captured from a source platform. | remark, note |

## Key Technologies

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Coordination Discover** | KT1 discovery of coordinated actors and evidence patterns across social content. | bot detection, coordination score |
| **Coordination Detect** | KT1 validation or classification of coordinated behavior using approved evidence and labels. | cluster naming, campaign claim |
| **Propagation Analysis** | KT2 analysis of spread, next-hop behavior, trend, and evidence chains. | trend chart only, propagation guess |
| **Risk Review** | KT3 harmfulness and manipulation review combining evidence, student models, teacher review, and governance. | risk score only, LLM verdict |
| **Student** | The deployable low-latency KT3 model used for preliminary triage. | final judge, report generator |
| **Teacher** | The expensive multi-agent KT3 review path used for advisory supervision and hard cases. | canonical verdict, automatic authority |
| **Teacher Silver** | Structured supervision exported by the Teacher for Student distillation and audit. | full agent report, rationale text |
| **Selective Student** | The KT3 Student protocol with two semantic axes, stance auxiliary head, and defer routing. | all-label classifier, rationale student |
| **Hard Case** | A case routed to Teacher or human review due to uncertainty, disagreement, OOD, or missing evidence. | harmful case, every positive sample |
| **Canonical Verdict** | An immutable analyst-approved KT3 verdict. | teacher output, student output |
| **Propagation Thread** | A source post plus linked replies, reposts, or reactions that form a conversation or spread tree. | claim list, graph summary only |
| **Thread Context** | The normalized node-edge representation of one Propagation Thread. | reaction count, raw comments |
| **Propagation Context** | The compact Agent-readable summary of Thread Context, including key branches, stance by depth, temporal snapshots, and missing fields. | whole graph dump, propagation score |
| **Branch Evidence** | A selected source-to-leaf path used to explain how a claim, stance, or uncertainty evolved. | random replies, full thread |
| **Escalation Point** | A thread node or branch that requires Teacher or human review because evidence is conflicting, missing, or unusually amplified. | harmful proof, final verdict |

## Governance

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Public Boundary** | A package, module, API, CLI, or document surface that other code or agents may rely on. | incidental import, helper |
| **Compatibility Layer** | A thin temporary alias that preserves old imports while canonical names migrate. | duplicate implementation, fork |
| **Governance Gate** | A test, scan, or checklist item that prevents drift in naming, structure, or documentation. | style preference, optional lint |
| **Development Log** | The chronological record of completed engineering changes. | changelog maybe, scratch note |
| **Project Map** | The maintained map of repository directories, ownership, and edit policy. | tree dump, README duplicate |

## Relationships

- An **Event** produces evidence that can be used by **Coordination Discover**, **Propagation Analysis**, and **Risk Review**.
- A **Crawl Request** yields one **Crawl Batch**.
- An **Analysis Run** may create one or more **Artifacts**.
- A **Checkpoint** can be part of an **Artifact**, but the **Model Version** is the governed identifier.
- **Teacher Silver** can supervise a **Selective Student**, but it is not a **Canonical Verdict**.
- A **Propagation Thread** is represented as **Thread Context** and summarized into **Propagation Context** before it reaches the **Teacher**.
- **Branch Evidence** may justify an **Escalation Point**, but it is not itself a **Canonical Verdict**.
- A **Compatibility Layer** must not contain independent business logic.
- Every structural code change requires **Documentation Sync**.

## Example Dialogue

> **Dev:** "I added a new KT3 training helper. Is that just a utility in `kt3_trainable_post.py`?"
>
> **Domain expert:** "Only if it belongs to the existing post-feature training boundary. If it owns Teacher Silver or Selective Student behavior, create a focused module and expose a clear **Public Boundary**."
>
> **Dev:** "Do I update only tests?"
>
> **Domain expert:** "No. Run tests and perform **Documentation Sync**: update the glossary, governance docs, ADR or roadmap when the architecture or method language changes."
>
> **Dev:** "Can Teacher output become the final system conclusion?"
>
> **Domain expert:** "No. Teacher output is advisory or silver supervision. Only an analyst-approved **Canonical Verdict** is final."

## Flagged Ambiguities

- "risk" is an implementation package name in the current branch; use **Risk Review** for the KT3 domain concept.
- "student" can mean a training model or a deployable runtime; use **Selective Student** when referring to the current 2+1 KT3 protocol.
- "teacher" can mean a multi-agent runtime or exported supervision; use **Teacher Silver** when referring to distillation data.
- "propagation analysis" can mean trend/graph modeling or Agent review; use **Propagation Context** when referring to the compact input for `PropagationTreeAgent`.
- "tree" must not mean a claim list or empty graph summary; use **Thread Context** only when node-edge reply/reaction links are present.
- "run", "job", and "task" must not be used interchangeably.
- "docs" and "doc" are distinct: `doc/engineering/` stores maintained engineering docs, while `docs/adr/` stores ADRs.
