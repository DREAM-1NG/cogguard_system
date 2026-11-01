---
status: accepted
date: 2026-07-21
---

# Review PropagationTreeAgent Evidence Boundary

## Context

`PropagationTreeAgent` existed as a MARO-style expert role, but offline dataset experiments passed only a single selected post, an empty `selected_tree_ids` list, and a one-node graph summary. That made the role capable of producing a natural-language report, but not capable of evidence-bound propagation analysis.

Prior graph-learning literature is useful for future model training, but it does not directly define how an LLM expert should read a social media thread. The transferable evidence comes from LLM rumor detection, stance explanation, conversation threading, and human-facing social context review.

## Decision

Risk Review now distinguishes:

- `Thread Context`: the normalized node-edge source-post/reaction tree.
- `Propagation Context`: the compact `review-propagation-context-v1` bundle read by `PropagationTreeAgent`.

`PropagationTreeAgent` may be recommended only when explicit propagation context or graph edges exist. A claim list, reaction count, or empty graph summary is not enough.

The first implementation target is PHEME because the local dataset contains source tweets and reactions. Other datasets must not fabricate thread structure.

## Consequences

- PHEME conversion now preserves `thread_context`.
- Offline Agent experiments pass `selected_tree_ids` when a case has a tree.
- `run_review_agent_dataset_experiment.py` builds a compact propagation bundle from the case.
- `agent_review.py` reads `review-propagation-context-v1` before falling back to legacy graph summaries.
- Claim-only samples no longer trigger `PropagationTreeAgent`.

## Rejected

- Treating propagation-tree work as a graph-model training task in this round: rejected because the immediate bug is missing Agent evidence input, not missing graph neural network capacity.
- Passing the full raw thread directly to the LLM: rejected because long conversation trees need branch selection and evidence compaction before review.
- Triggering `PropagationTreeAgent` whenever claims are available: rejected because claim evidence and propagation evidence are different domains.
