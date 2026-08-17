# CogGuard System Context

This context defines the shared language for the current system refactor. It keeps the product-facing Event Review Case workspace separate from internal analysis and research boundaries so implementation, evaluation, and documentation do not drift.

## Event Review Case

**Event Review Case**:
The product-facing case aggregate keyed to one event. It binds the event identity, the current evidence set, the preliminary finding, the review advisory history, the confirmed decision trail, and the case activity stream.
_Avoid_: ticket, issue, review job

**Preliminary Finding**:
The first structured case finding produced before analyst confirmation.
_Avoid_: first guess, preliminary score

**Review Advisory**:
An internal or manually requested advisory verdict that can differ from the preliminary finding.
_Avoid_: final verdict, automatic decision

**Confirmed Decision**:
The immutable analyst-confirmed case decision.
_Avoid_: mutable decision, draft approval

**Evidence Sufficiency**:
The assessment of whether the current evidence set is enough to support a case action.
_Avoid_: completeness score, confidence score

**Evidence Annotation**:
A note attached to a specific evidence item, including its assessment and supporting context.
_Avoid_: comment, tag, annotation blob

**Case Activity**:
An append-only business activity record that explains what happened to a case and when.
_Avoid_: audit spam, task log

**Review Audit**:
A read-only projection of a persisted review advisory run. It exposes bounded
execution stages, traceable source excerpts, retrieval queries, and short
rationale capsules when available; it is not a decision or a confidence view.
_Avoid_: model trace, final verdict, chain-of-thought dump

Current implementation status: the case service, snapshot revisions, evidence annotations, decision drafts, confirmed decisions, and activity stream are implemented in the current branch. Automatic routing after successful collection creates or revises a case and can request an internal review advisory when evidence sufficiency or urgency warrants it. This workspace is prototype code in the branch; it is not a claim of production rollout.

The `/risk` workbench reads `Review Audit` from the `teacher-audit` endpoint
after loading a case. The page never invokes a review run while merely viewing
an audit; the existing analyst action remains the explicit trigger. Unavailable,
queued, completed, and failed states are rendered separately, and the final
case decision remains an analyst-confirmed `Confirmed Decision`.

---

## Internal Diagnostics

**Event Snapshot**:
An immutable content-addressed analysis input built from MongoDB `raw_posts` and `raw_comments`. It contains event identity, platforms, core/context windows, normalized content, observed relationships, quality report, provenance, and data fingerprint.
_Avoid_: ad hoc event query, temporary dataframe, surface count

**Coordination Discover**:
The evidence-constrained, label-free coordination pipeline that resolves cross-platform evidence, builds account-object coordination structure, and outputs auditable candidate groups.
_Avoid_: numbered stage label, classifier shortcut, harmfulness detector

**Coordination Detect**:
The governed group-level detection runtime that consumes Coordination Discover output and an active detection artifact to emit harmful/benign coordination evidence hints.
_Avoid_: detect shorthand, final verdict, event labeler

**Propagation Analysis**:
The propagation boundary that estimates spread size, next-hop behavior, and tree structure from a snapshot.
_Avoid_: trend guess, prediction blob

**Claim Response Path Semantic Overlay**:
A read-only semantic evidence summary for one observed authority-claim response
path. It is available only when every displayed platform-qualified post or
comment reference resolves to the same ready, non-fallback semantic artifact.
It is never inferred from account identity, text similarity, graph adjacency,
or event-level aggregates, and cannot change any propagation or risk result.
_Avoid_: path classification, inferred response, path risk score

**Review**:
The internal review routing boundary that produces advisory input and confirmed-decision prompts behind the case workspace.
_Avoid_: generic analysis, unbounded internal loop

The product workspace stays behind login-gated routes and does not expose the internal diagnostic boundary as a first-class product surface.

---

## Backend Governance Boundary

The backend control plane owns durable execution and model decisions while the
dashboard-first frontend stays focused on the Event Review Case workflow.

**Teacher Dispatch Policy**:
Production Teacher Review is activated only by an analyst Review API request.
Student Review may create an internal review candidate, but it never invokes
Teacher Review automatically. Offline data-production scripts may explicitly
batch-call Teacher Review under a separate experiment boundary. The legacy
`ANALYSIS_TEACHER_DISPATCH_MODE=auto` setting remains a compatibility setting
for local replay only and does not authorize an automatic product trigger.

**Model Candidate**:
A registered versioned artifact that has not yet moved the active pointer.
Artifact hash verification and capability quality gates run before approval.

**Model Candidate Approval**:
An authenticated administrator action that records review of one candidate.
The request derives the administrator identity from the bearer session and
cannot accept an approver ID supplied by the caller.

**Model Activation Approval**:
An immutable row in
`analysis_model_activation_approvals`. Production activation requires two
distinct active administrator rows, including the activating administrator;
local activation records one accountable operator. The active pointer and
append-only governance decision remain backend concerns.

**Canonical Verdict** approval is separate from model activation. A Student
preliminary result or Teacher Advisory never becomes canonical through queue
completion, model approval, or model activation; only an analyst action can
create the immutable Confirmed Decision source.

Current implementation status: the dispatch policy and persisted approval
service are implemented, with migration `a2d8e5c1b904` as the database head.
Apply that migration in each deployed database before enabling production
activation. The primary frontend remains unchanged and does not expose model
versions, checkpoints, agent graphs, queue internals, active pointers, or
rollback controls.

## MARO Teacher And Text Student Boundary (2026-08-15)

**Student Review** is the low-cost synchronous XLM-R text runtime. Its primary
supervision consists of fixed, task-specific hard labels for interpersonal harm
and claim deception. Rationale projections are auxiliary targets only; Teacher
confidence, Teacher probabilities, full Agent traces, and raw RAG documents are
audit data, not Student loss targets.

**Teacher Review** is the analyst-triggered asynchronous MARO-compatible chain:
necessary experts -> QuestionReflection -> at most two targeted responses ->
task-specific Judge. Simple cases skip QuestionReflection and targeted
responses. The chain returns an advisory report and typed sidecars; it does
not replace the Canonical Verdict.

**EvidenceRAG** retrieves traceable external evidence only for an eligible
claim. **PolicyRAG** retrieves current governance clauses only. **ReasonBank**
is an offline rationale/example lookup and is not a factual evidence source.

Claim review has three non-interchangeable states: **Claim Assessment** records
whether a structured claim is checkable; **Retrieval Status** records whether a
provider was attempted and completed; **Evidence Relation** records
support/contradiction/conflict/insufficiency only after completed, traceable
retrieval. Missing claim fields, a provider fault, and zero relevant results
must remain non-relational states, never `insufficient`.

**RationaleCapsule** is a short, source-bound rationale with input/evidence/
policy references and a quality gate. A capsule can enter auxiliary Student
supervision only after the relevant schema, provenance, citation, relation,
and policy checks pass.

**Hard-case mining** is an offline candidate-manifest generator based on
uncertainty, evidence conflict, OOD signals, and error coverage. It is not a
product defer classifier and does not call Teacher in this coding stage.

The current coding stage does not implement multimodal consistency, raw
image/video fusion, OCR/ASR/caption fusion, continuous pretraining, dataset
training, or external LLM calls. Coordination Discover, Coordination Detect,
and Propagation Analysis remain separate capabilities and are not refactored
by this Review boundary.

## Coordination Runtime Boundary (2026-08-16)

The current Coordination mainline is `cross-platform resolution -> evidence-constrained Coordination Discover -> group-level Coordination Detect`.
The resolver canonicalizes URL, domain, topic, and text-claim objects, and keeps
account identity platform-scoped unless multiple strong identity signals support
conservative cross-platform merging. Same display name alone is explicitly
insufficient.

Coordination Discover remains the system mainline based on observable evidence
objects, shared-object timing, account-object evidence, weighted coordination
network construction, dynamic windows, and community lineage. It does not use
MAGNN/GFM as the product Discovery decision path.

Coordination Detect now treats `socgfm_cross_attention` as the primary system
Detection artifact type. At runtime the active `coordination_detection` pointer
must resolve to a hash-verified SocGFM-compatible artifact or the system returns
`model_unavailable`; it does not silently fall back to a heuristic detector.
The older learned/logistic classifier remains a shadow baseline for audit and
rollback comparison, not the frontend primary result.
The current v1 deployment bridge runs the official China SocGFM
CrossAttention/SAGE checkpoints only in offline precomputation. The precompute
path loads `model0.pth` through `model4.pth`, builds platform-scoped local
account keys, requires 768-dimensional SBERT text features, constructs 128-
dimensional positional-degree structural features, executes Torch/PyG forward,
and writes `predictions.csv`, `node_mapping.csv`, `feature_audit.json`,
`checkpoint_hashes.json`, and `prediction_manifest.json` under G-drive output.
Online APIs and the frontend still do not execute neural forward; they consume
precomputed member probabilities and aggregate them to Coordination Community
proxy verdict hints.
The legacy `/api/v1/coordination/detect` route is compatibility-only and fails
closed with `model_unavailable`; it must not call the old rule/network-stat
service as a system Detection result.

The dataset registry in `coordination_model_service` remains a Coordination
Archive Replay surface for historical MAGNN/Leiden/SBERT runs. For unlabeled
uploaded datasets, rerun now uses the official China SocGFM checkpoint offline
precompute rather than the internal `china_fusion_gnn_sbert.pt` checkpoint. Any
legacy account-level archive Detection scores may be carried as
`archive_detection_*` audit fields, but they must not drive frontend primary
verdicts, key-node ranking, or risk wording.

Historical archive artifacts can contain persisted, real member-level Detection
predictions while lacking a materialized group-level `coordination_detection`
projection. The read path reconstructs only a traceable group projection from
those persisted predictions and the stored Coordination Community membership;
it never creates a verdict when predictions are absent. The latest-result cache
uses `coordination-latest-result-v3` so a prior empty projection cannot hide a
newly reconstructable historical result. A high-risk group is an analyst prompt,
not a Confirmed Decision.

`magnn_leiden_hybrid_discovery` is a research-only candidate. It uses the
existing evidence graph as the constraint, learns relation-aware account
embeddings and edge affinities, fuses them with evidence weights, and uses
Leiden only as the community partition/explanation head. It may be compared in
offline proxy and stability experiments, but it does not replace the
evidence-constrained Discovery mainline unless future evaluations beat both the
system Discovery path and the retained MAGNN legacy baseline under the same
protocol.

## HateCoT MARO Expanded Evaluation Boundary (2026-08-17)

The current research track defines a strict three-way, text-only MARO-compatible
adaptation on HateCoT. It is not the official MARO binary misinformation
reproduction and it does not claim that MARO's misinformation mechanism directly
transfers to hate labels.

Each held-out fold is isolated as:

```text
source-train -> source-dev -> held-out target-test
```

`source-train` is the only pool visible to DeepSeek rule proposal and strict
improvement retention. `source-dev` is used once, after proposal generation, to
rank the fixed candidate pool by Macro-F1. `target-test` labels are read only
after all prompts and rule selection are complete. The three target domains are
`cad`, `dynahate`, and `toraman`, with 100 cases per normalized class in each
fold. `Animosity` remains excluded as an ambiguous source label.

The primary arm is `policy_context_mode=off`. `local_advisory` is a separate
local governance-context ablation using the same split and strict source rule
pool; it is not semantic PolicyRAG domain adaptation. No Exa, external fact
retrieval, Student/LRKD, multimodal input, Countermeasure, defer, coverage, or
abstention logic is part of this experiment.

The runner records source/target manifest hashes, label-mapping version, and a
fold protocol hash. `--resume` reuses only reports and analysis caches whose
hashes match the current protocol; a stale fold fails closed. A Judge format or
provider failure after retries fails the run rather than removing a target row
from the metric denominator.
