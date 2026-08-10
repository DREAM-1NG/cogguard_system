# Case Workbench Implementation Comparison

## Reading This Comparison

This is a design comparison, not a procurement recommendation and not an empirical evaluation. The five vendor URLs below are unverified comparison hypotheses: no vendor capability statement was captured or retained, and none supplies design evidence. Technical references identify ideas and boundaries, but they do not prove implementation quality, Chinese-domain performance, legal fitness, or operational suitability. The conclusion is a minimum auditable scope for CogGuard, not a claim of feature parity.

## Comparison Boundary Map

| Reference | Comparison status | CogGuard use | Evidence limitation |
| --- | --- | --- | --- |
| Brandwatch Consumer Research | Unverified comparison hypothesis; no capability statement was captured or retained. | None; not used as design evidence. | Configured reader attempt was blocked by anonymous-query authentication. |
| Talkwalker Consumer Intelligence | Unverified comparison hypothesis; no capability statement was captured or retained. | None; not used as design evidence. | URL was indexed but not retrieved; no source text is available in this pack. |
| Pulsar TRAC | Unverified comparison hypothesis; no capability statement was captured or retained. | None; not used as design evidence. | Configured reader attempt was blocked by anonymous-query authentication. |
| NewsWhip Spike | Unverified comparison hypothesis; no capability statement was captured or retained. | None; not used as design evidence. | URL was indexed but not retrieved; no source text is available in this pack. |
| Blackbird.AI | Unverified comparison hypothesis; no capability statement was captured or retained. | None; not used as design evidence. | URL was indexed but not retrieved; no source text is available in this pack. |
| CooRTweet | Detects coordinated behavior from coordinated actions and exports a related network; its public README mentions potential cross-platform analysis. | CogGuard should keep Coordination as evidence-graph analysis, retain type/time/object provenance, and not turn a community into a verdict. | Repository has `NOASSERTION` license metadata; source content was inspected but not retained. |
| Hoaxy | Visualizes the spread of claims and related fact checking; backend README states it is archived. | Propagation/claim linkage is useful, but an archived reference cannot be treated as an active dependency. | Historical/archived technical reference only. |
| BERTopic | Embedding-driven clustering with c-TF-IDF topic representations. | Use a scoped, candidate-only topic artifact with model/scope hashes; keep topic clusters separate from risk. | MIT upstream documentation describes its approach, not Chinese-domain quality. |
| KeyBERT | Embedding similarity keyword/keyphrase extraction and a documented MMR option. | Use shared embeddings and deterministic MMR parameters with a captured scope/input hash. | MIT upstream documentation, not a validation study for this corpus. |
| DISARM | A framework vocabulary for describing disinformation incidents/techniques. | Keep structured evidence, actions, and audit records; do not map a case to a framework taxonomy without source-level support. | Public foundation material is conceptual; no retained source because license/retention was not clear in the bounded capture. |

## What The Workbench Adopts

| Concern | Chosen minimum | Why |
| --- | --- | --- |
| Product boundary | One `CaseRecord` per `event_id`, with immutable snapshots and append-only audit. | Makes collection/review/closure inspectable as one historical aggregate. |
| Evidence | AuthoritySource organizational tier plus independent review status, exact quotes, spans, content hashes, independent claim role, and a selected primary claim. | Prevents narrative summaries from becoming untraceable facts while keeping source classification separate from claim role. |
| Coordination and propagation | Link existing specialist outputs to the Case Workbench. | Reuse current product capabilities rather than duplicate analytical surfaces. |
| Semantics | Scoped, auxiliary, candidate/unvalidated artifacts. | Allows useful investigation without contaminating established risk results. |
| Review/actions | Immutable CaseVerdictVersions, a pointer-only canonical projection, and append-only operations and feedback. | Keeps human authority and operational accountability explicit without mutating verdict history or dual-writing legacy review data. |
| Reporting | Versioned web/print/PDF payloads with source/model/run hashes. | Supports post-hoc inspection and reproducibility rather than mutable exports. |

## What The Workbench Explicitly Does Not Copy

- It does not claim to reproduce a vendor platform, its data access, audience graph, or proprietary scoring.
- It does not treat a Coordination community, topic, sentiment, named entity, or stance prediction as proof of coordination, harm, or intent.
- It does not ingest vendor APIs, scrape vendor pages, or add their dependencies.
- It does not make a broad DISARM taxonomy label mandatory for an evidence record.
- It does not adopt Hoaxy or CooRTweet as a runtime root. Existing repository boundaries remain unchanged.

## Technical Reference Consequences

### CooRTweet

The useful transferable idea is an evidence relationship with source object, actor, and time. CogGuard already has Coordination Discover as a formal capability; the Case Workbench only links its outputs and must preserve provenance. The case service cannot invent a campaign label from an edge/network alone.

### Hoaxy

The useful transferable idea is linking claims to visible propagation/fact-check context. CogGuard retains its own Propagation Analysis boundary. The Case Workbench graph tab must therefore reference immutable evidence and output IDs, not reimplement a second propagation engine.

### BERTopic and KeyBERT

The planned semantic stage uses a shared embedding cache to avoid separate uncontrolled representations. BERTopic-style clusters/c-TF-IDF and KeyBERT-style MMR are candidate descriptive outputs. Every result carries scope, input, model revision, and payload hashes. The original model prediction remains visible after any analyst correction.

### DISARM

The workbench borrows the discipline of structured incident description, not a mandatory classification ontology. A claim/action/audit record must stand on its own evidence. Any later DISARM mapping is a separately versioned annotation with source references and validation rules.

## Research Gaps Before Strong Claims

1. No local Chinese-domain evaluation exists for the four pinned semantic candidates.
2. No same-event Douyin data has been asserted for the seed case; collection is explicitly partial.
3. No selected authoritative CCTV/Xinhua source pages have been captured for the supplied claim seeds.
4. Brandwatch and Pulsar reader attempts were blocked by anonymous-query authentication; Talkwalker, NewsWhip, and Blackbird were indexed but not retrieved. All five remain unverified comparison hypotheses and are not design evidence.
5. No end-to-end latency, memory, calibration, false-positive, or human-agreement measurement is recorded for the proposed Case Workbench.

The implementation plan therefore treats every semantic capability as a candidate artifact and requires local evaluation before any promotion beyond `candidate_unvalidated`.
