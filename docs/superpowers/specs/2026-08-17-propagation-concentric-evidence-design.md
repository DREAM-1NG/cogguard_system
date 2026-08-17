# Propagation Concentric Evidence Design

## Goal

Refine the Propagation Monitoring page into an evidence-led reading surface for
an analyst. The page must make four questions easy to answer without changing
Coordination, Propagation, Review, or risk scores:

1. How does the observed diffusion relate to the current primary source?
2. How many observed nodes occur at each evidence-path depth?
3. Which shared objects have the widest observable participation?
4. Which accounts originate, bridge, or amplify observed paths, and why?

## Boundary

- The graph remains a projection of observed reply, repost, or shared-object
  time-order evidence. Proximity in the drawing never proves a causal link.
- One deterministic primary source sits at the centre. Other unconnected source
  branches are labelled as independent observations, rather than fabricated as
  descendants of that source.
- Role labels are evidence-derived, not a popularity, credibility, or authority
  classification. Followers and engagement remain contextual information.
- This change does not add a new analytical model, alter existing risk scores,
  or invent missing object timestamps, evidence references, or downstream reach.

## Reference Pattern

The design transfers the separate reading modes documented by Zhiwei:
propagation path, hierarchy, and key users are distinct analytical views rather
than one overloaded graph. The migration is deliberately narrower:

- a concentric map provides the source-and-depth overview;
- the hierarchy panel provides count-backed depth proportions;
- object and role views provide compact, drillable evidence rankings.

Sources: Zhiwei's [propagation-analysis description](https://weiboreach.com/explain.html),
[individual propagation graph](https://research.zhiweidata.com/2021/01/11/1adfe8712e/),
and [event propagation graph](https://research.zhiweidata.com/2021/01/14/f0ab9c7545/).

## Data Contract

The propagation result gains only evidence-backed fields where current data can
support them:

- `primary_root_id`: the stable primary source selected from observed roots by
  downstream reach, then earliest observed evidence, then account id.
- `layer_distribution`: count and ratio for every depth relative to the primary
  source. Independent observations have an explicit status and are not counted
  as descendants.
- `shared_objects`: object type, display label, occurrence count, distinct
  account count, first observed timestamp when available, and exact path or
  evidence references when available.
- `role_contributions`: originator, bridge, and amplifier entries with account
  identity, depth, direct downstream count, unique observable downstream reach,
  evidence-path references, and any unavailable-data reason.

No absolute file path, synthetic edge, inferred timestamp, or generic semantic
overlay is accepted into this projection.

## Computation

### Primary source and layers

Choose the primary root from observed zero-in-degree nodes. Sort candidates by
unique reachable descendants descending, earliest evidence ascending, then
stable account id. Compute directed shortest-path depth from that root only.
Nodes with no directed path from it are independent observations. Ratios use
the count of connected, displayed nodes as the denominator and display two
decimal places; raw counts remain visible beside every ratio.

### Role contributions

`Originator` is the primary source and, separately labelled, any independent
source with observed downstream evidence. `Bridge` has both an observed upstream
and downstream edge and a non-zero path-bridging contribution; it must show the
paths that establish that position. `Amplifier` is a non-originator ranked by
unique observable directed descendants, then direct downstream count. A high
in-degree alone can never create an amplifier label.

If the underlying graph cannot establish a contribution, the corresponding
metric is shown as unavailable and does not become zero or a role assignment.

### Concentric evidence layout

The browser owns this visual-only layout so service responses continue to carry
facts rather than pixels. The primary source is at `(0, 0)`. Connected nodes
are placed in rings by directed depth. Within each ring, a stable order groups
nodes by their evidence-backed predecessor before assigning a deterministic
id-seeded angle and bounded radial jitter. Ring spacing increases with depth;
minimum angular separation avoids visual overlap. Independent observations use
a labelled outer dashed band. The layout must be stable for the same result and
must not use a random runtime source.

## Product Presentation

The page header becomes a three-part tool area: `事件范围`, `显示密度`, and
`操作`. It replaces the repeated "传播路径" card title with one concise caption
that states the primary-source boundary.

1. **传播路径** contains the concentric evidence map and a compact layer panel.
   Layer bars show `count` and `xx.xx%`, and tooltips retain the same precision.
2. **传播对象** is an object-type selector plus a dense evidence ranking. A row
   exposes occurrence count, participating accounts, first observation where
   available, and a path-evidence entry. It replaces the keyword-pill wall.
3. **角色与贡献** replaces the ignition star. Three contribution-ranked groups
   state the role reason, direct contribution, downstream reach, depth, and a
   `查看证据` action that opens the existing node or path drill-down.

The graph is the sole intentionally dark canvas; controls and evidence lists
remain compact, light, and keyboard accessible. All tooltips, buttons, and
status wording use business language, not storage ids or internal scores.

## Failure Handling

- No connected primary-source path: show the graph empty state and preserve
  independent observations as an explicit unavailable result, not a radial
  approximation.
- Missing object timestamp or path reference: show `未提供` and omit the
  unavailable action.
- Missing role contribution evidence: omit the role item rather than relabeling
  a centrality score as a role.
- Event or platform changes reset the displayed projection and all focused-node
  state before new data is rendered.

## Verification

- Backend tests cover deterministic primary-root selection, connected versus
  independent layers, two-decimal count-backed ratios, and all three role
  definitions with explicit path evidence.
- Frontend tests cover stable concentric positions, no use of server pixel
  coordinates, forward evidence edges only, ratio precision, grouped toolbars,
  object ranking, role evidence actions, and reset behaviour.
- Browser checks cover desktop and mobile graph readability, visible keyboard
  focus, no horizontal page overflow, and node-to-evidence drill-down.
