# CogGuard Context

This file defines how CogGuard's product and internal analysis contexts relate. Canonical term definitions live only in `UBIQUITOUS_LANGUAGE.md`.

## Product Context

The analyst-facing aggregate is the **Event Review Case**. Product copy may expose its **Preliminary Finding**, **Evidence Sufficiency**, **Evidence Annotation**, optional **Review Advisory**, **Confirmed Decision**, and **Case Activity**.

Product interfaces must not require an analyst to understand **Analysis Run**, model, checkpoint, artifact, queue, Agent, or stage implementation details.

The product terms in this context are **Event Review Case**, **Propagation
Monitoring**, **Review Advisory**, and **Confirmed Decision**. A Confirmed
Decision is the product case decision. A Confirmed Decision may cite a Canonical Verdict, but the two terms describe different owners and lifecycles.

## Internal Analysis Context

The internal analysis context starts from an **Event Snapshot** and may execute
**Review**, **Propagation Analysis**, **Coordination Discover**, **Propagation
Monitoring**, **Student Review**, and **Teacher Review** through an **Analysis
Run**. Review and Propagation Analysis are internal capability terms;
Student Review and Teacher Review identify runtime roles.

An **Artifact Manifest** records the artifact or checkpoint reference,
execution status, fallback reason, and claimability for each analysis stage. A
**Celery Task** is the worker execution lifecycle for one dispatched job; it is
not interchangeable with an Analysis Run or Teacher Job.

Internal outputs remain evidence or advisory inputs. They do not become a **Confirmed Decision** through execution completion, model activation, or queue completion.

## Cross-Context Relationships

- One event owns at most one current **Event Review Case**, with immutable evidence and decision history.
- One **Event Snapshot** may create or revise the evidence available to an **Event Review Case**.
- A **Student Review** result may become a **Preliminary Finding** but never a **Confirmed Decision**.
- A **Teacher Review** result may become a **Review Advisory** but never a **Confirmed Decision**.
- **Model Activation** changes future internal execution; it does not mutate an existing case decision.
- Product V1 and V2 adapters may coexist, but shared behavior must cross the same internal module seam.
- Both V1 capability APIs and V2 case/governance APIs are current contracts.
  Only endpoints explicitly marked deprecated are legacy.
- Current-product-contract completeness covers the implemented source-checkout
  capabilities for release-0.2 and excludes future roadmap features.
- Source-checkout deployment is canonical. Windows and Ubuntu CI plus required
  GitHub checks are binding acceptance gates.

## Context Ambiguities

- **Review** names the internal capability; **Event Review Case** names the product aggregate. Do not use them interchangeably.
- **Analysis Run**, **Teacher Job**, and **Celery Task** are separate lifecycles. A run owns analysis state, a job owns one Teacher dispatch, and a task owns queue execution.
- **Propagation Monitoring** includes observed analysis and governed forecast; neither implies a causal claim.
