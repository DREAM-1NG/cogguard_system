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

Current implementation status: the case service, snapshot revisions, evidence annotations, decision drafts, confirmed decisions, and activity stream are implemented in the current branch. Automatic routing after successful collection creates or revises a case and can request an internal review advisory when evidence sufficiency or urgency warrants it. This workspace is prototype code in the branch; it is not a claim of production rollout.

---

## Internal Diagnostics

**Event Snapshot**:
An immutable content-addressed analysis input built from MongoDB `raw_posts` and `raw_comments`. It contains event identity, platforms, core/context windows, normalized content, observed relationships, quality report, provenance, and data fingerprint.
_Avoid_: ad hoc event query, temporary dataframe, surface count

**Coordination Discover**:
The unsupervised coordination pipeline that learns temporal coordination structure from an evidence graph.
_Avoid_: numbered stage label, classifier shortcut

**Coordination Detect**:
The validation layer that tests whether Coordination Discover representations improve detection on labeled data.
_Avoid_: detect shorthand, main detector, event labeler

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
`ANALYSIS_TEACHER_DISPATCH_MODE=auto` permits local inline execution only when
`BACKEND_ENV=local`. Production resolves to `queue_required`; a broker or
worker failure is persisted as a failed Teacher Advisory and is recoverable
through the Analysis Run event stream.

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
