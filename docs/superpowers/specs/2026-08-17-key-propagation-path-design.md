# Key Propagation Path Design

## Decision

The propagation path view opens with a **Key Propagation Path**, not a
truncated full graph.  It shows the current primary source, up to 24
evidence-backed bridge or amplifier accounts, and the real observed ancestor
chains that connect those accounts.  Ordinary accounts are absent until an
analyst deliberately expands a visible account.

## Evidence Boundary

An edge in either the initial key path or an expanded branch must be an
observed directed edge from the propagation graph.  The view may select and
omit evidence, but must never synthesize a causal edge, infer a display parent
from radial position, or select an account solely from popularity or in-degree.

Independent observation roots form separate outside islands.  Their internal
observed edges remain visible; no edge connects an island to the current
primary source.

## Interaction

Selecting a key account toggles its full observable descendant branch.  The
branch projection is returned by the backend for the same event/platform scope
and contains only the selected account, its directed descendants, and observed
edges inside that set.  Scope changes clear all branch expansions.

Radius encodes observed hop distance only.  The client provides deterministic
angular layout and does not use server layout coordinates as causal evidence.
