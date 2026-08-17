# Claim Response Semantic Readout Plan

## Goal

Complete the analyst reading loop for the existing **Claim Response Landscape**:

`primary authority post -> observed comment-thread response -> exact evidence refs -> real semantic readout`

The implementation must remain a read-only Propagation Analysis projection. It
does not change Coordination, Propagation, or Review conclusions and never
infers relationships from text similarity, account names, or graph adjacency.

## Task 1: Exact Path Semantic Readout And Reach Scope

- Add a failing backend test using a ready semantic artifact whose post and
  comments are the exact evidence references of an observed direct-comment
  path.
- The returned path reference includes a semantic overlay only when every
  exact path reference maps to a real semantic-layer record.
- Aggregate only those mapped records into sentiment, stance, keywords,
  topics, entities, platforms, time range, and the same evidence references.
- Missing semantic records leave the overlay absent rather than creating a
  partial or fabricated result.
- Extend the existing response coverage with the count of direct-comment path
  overlays returned by this projection, so an event-level ready artifact and a
  path-level unmapped result remain distinguishable.

## Task 2: Reach Scope Truthfulness

- A direct comment-thread path has no generic propagation-network downstream
  calculation in this projection. Return the network-reach field as unavailable,
  with a stable reason, rather than returning a numeric zero that suggests a
  measured absence of spread. Preserve the existing platform-local ordering using
  path contribution and engagement when reach is unavailable.

## Task 2: Propagation Page Projection

- Carry an exact path semantic overlay through the existing path drawer and
  show its source references.
- Show `评论链路径，未计算网络下游覆盖` when the projection marks reach
  unavailable; show a numeric downstream coverage only for a measured graph
  value.
- Preserve the current generic propagation-artifact overlay path for existing
  propagation paths, but do not require it to render a claim-response overlay.
- Add frontend contract coverage for both states and run TypeScript/build
  checks.

## Acceptance

- Path semantic output is derived from the same observed references displayed
  in the drawer.
- A missing semantic record or network metric is explicitly unavailable.
- No fallback, inferred edge, synthetic path identifier, or changed risk score
  is introduced.
