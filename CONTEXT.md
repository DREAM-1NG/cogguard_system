# CogGuard System Context

This context defines shared language for the current system refactor. It separates deployed system contracts from research claims so implementation, evaluation, and documentation do not drift.

## Unified Analysis Language

**Event Snapshot**:
An immutable, content-addressed analysis input built from MongoDB `raw_posts` and `raw_comments`. It contains event ID, platforms, core/context time windows, normalized content, observed relationships, quality report, provenance, and data fingerprint.
_Avoid_: ad hoc event query, temporary dataframe, surface count

**Analysis Run**:
A MySQL-tracked execution request against one Event Snapshot. Its state is one of `queued`, `running`, `needs_evidence`, `awaiting_review`, `completed`, `failed`, or `cancelled`.
_Avoid_: background task only, dashboard request, implicit pipeline state

**Analysis Run Event**:
An append-only event stream item for one Analysis Run. The numeric event ID is the recovery cursor for REST polling and SSE `Last-Event-ID`.
_Avoid_: log line, progress string

**Review Verdict**:
A versioned review decision. `preliminary` and `teacher_advisory` are not canonical. Only an analyst-approved immutable version can become `canonical`.
_Avoid_: latest label, model output, mutable review status

**Teacher**:
The asynchronous multi-agent research review runtime. It may advise, calibrate, and produce evidence, but does not become canonical without analyst approval.
_Avoid_: rule engine, final detector

**Student**:
The synchronous deployable review runtime distilled from approved evidence and Teacher traces. It must be versioned, measured, and activated through explicit governance.
_Avoid_: heuristic shortcut, unversioned classifier

Current implementation status: Event Snapshot contracts, registry persistence, Analysis Run lifecycle, V2 REST routes, SSE recovery, and the Analysis Run executor port are implemented as the system entry layer. Coordination Discover now runs `coordination-evidence-runtime-v2` from EventSnapshot records, including multi-kind evidence edges, overlapping windows, community lineage, null-model significance, perturbation robustness, evidence coverage, and domain-shift reporting. Propagation Analysis runs through the internal `system/research/propagation_analysis` boundary, including event bundle, public fixture loader, live fallback, hindcast protocol, split-conformal intervals, next-hop ranking, platform hindcasts, and baseline registry; fitted TGN/DyGFormer/CasFlow/CasFT checkpoints still need approval before research-grade activation. Student now runs through `system/runtimes/review_student` and returns a synchronous preliminary verdict with active-learning and distillation metadata; without an approved checkpoint it explicitly marks `shadow_untrained`. Teacher now runs through `system/research/review_teacher` as an asynchronous 5+1+1 advisory DAG. Only analyst-approved immutable verdicts can become canonical.

---

# CogGuard Review Context

This context defines the shared language for Review harmfulness assessment. It keeps research, implementation, and evaluation discussions aligned around the same post-level and group-level concepts.

## Language

**Post View**:
A modality-specific interpretation of one post, currently one of Tweet View, Meme View, Image View, or Video View.
_Avoid_: raw feature, channel feature, modality flag

**View Detector**:
A detector that judges one Post View and returns a standard label, score, confidence, evidence, and abstention decision.
_Avoid_: keyword matcher, feature extractor

**View Abstention**:
A detector outcome meaning the view lacks enough decodable evidence to make a confident judgment.
_Avoid_: negative prediction, safe prediction

**Decodable Evidence**:
Content that a View Detector can actually interpret, such as text, OCR, ASR, caption, alt text, or extracted frame/context text. A media URL alone is not Decodable Evidence.
_Avoid_: media exists, URL evidence

For `meme`, `img`, and `video` views, availability means view-specific decodable media evidence exists. Reusing tweet text because a media URL is present is not a valid media-view judgment.

**Effective View**:
A Post View that is available and not abstained, therefore eligible for Majority Vote and View Fusion.
_Avoid_: present modality, raw channel

**Majority Vote**:
A post-level decision rule that counts only confident, non-abstained View Detector labels.
_Avoid_: average score, rule score

**View Fusion**:
A post-level decision rule that combines standardized View Detector outputs into one final harmfulness judgment.
_Avoid_: feature concatenation, manual scoring

**Harmfulness Judgment**:
The final Review post-level conclusion: harmful, non-harmful, or uncertain, with harm type and evidence when available.
_Avoid_: toxicity score only, content score only

