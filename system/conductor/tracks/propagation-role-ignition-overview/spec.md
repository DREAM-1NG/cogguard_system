# Specification

## Goal

Add a compact ignition overview to the propagation role-analysis tab.

## Acceptance Criteria

- The center is the selected evidence-chain originator.
- Outer nodes are only direct, evidence-backed outgoing neighbors from that originator.
- Outer nodes render account names only; details remain in the existing node drawer.
- Solid lines represent explicit edges and dashed lines represent inferred edges.
- No propagation role algorithm, API, or dependency changes are introduced.
