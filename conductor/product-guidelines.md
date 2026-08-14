# Product Guidelines

## Product-facing language

Use the canonical names in `../UBIQUITOUS_LANGUAGE.md`.

| Prefer | Avoid in product copy |
| --- | --- |
| Event Review Case | ticket, job, analysis run |
| Preliminary Finding | model score, first guess |
| Review Advisory | final verdict, automatic decision |
| Confirmed Decision | mutable decision, model approval |
| Coordination Discover | numbered technology label, classifier claim |
| Propagation Analysis | trend guess, prediction blob |
| Evidence Sufficiency | completeness score, confidence score |

## Presentation rules

- Present the evidence, its provenance, and uncertainty before a conclusion.
- Keep semantic enrichment as evidence assistance; it must not alter Coordination Discover, Propagation Analysis, or Review conclusions.
- Do not expose model version, checkpoint path, artifact hash, queue state, Active Pointer, or rollback controls in the primary product workspace.
- When an internal capability is unavailable, say what evidence is unavailable and why; do not substitute a successful-looking result.

## Copy style

- Use concise Chinese language for analyst-facing UI.
- State observable facts separately from analyst decisions.
- Do not label a Coordination Community as a campaign or botnet without external evidence or analyst confirmation.
