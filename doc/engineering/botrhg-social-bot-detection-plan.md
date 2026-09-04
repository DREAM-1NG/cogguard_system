# BotRHG Social Bot Detection Integration Plan

## Goal

Integrate an account-level social bot detection surface into the current CogGuard system code root (`system/`) using the NLPCC 2026 BotRHG method direction: feature encoding, KNN hyperedge construction, reliability-guided routing, and selective residual correction.

## Design

- Add a backend-only service under the account-monitoring boundary. The service consumes already collected `raw_posts` and returns account-level bot probabilities, base predictions, local reliability, routed hyperedge evidence, and final selective predictions.
- Keep the implementation deterministic and lightweight for system integration. It mirrors the BotRHG inference contract and explainability fields without importing the full LLMbot training CLI into CogGuard.
- Reuse existing Mongo event/platform filtering and account-profile features. Text/profile/activity signals form the feature encoder proxy; nearest account features form support hyperedges; low-reliability accounts receive residual correction from local support evidence.
- Expose the feature through `POST /api/v1/accounts/bot-detection`, leaving the existing Coordination Discover coordination dataset/model routes untouched.

## Implementation Tasks

1. Write failing tests for the BotRHG account detector core and API pass-through.
2. Implement the deterministic BotRHG-style detector core in `system/backend/app/core/bot_detection.py`.
3. Add service orchestration in `system/backend/app/services/bot_detection_service.py`.
4. Register the account API route in `system/backend/app/api/v1/accounts.py`.
5. Update README and engineering roadmap/log entries to reflect that `system/` is the active code root for this feature.
6. Run focused tests for bot detection, account/event scoping, and route import health.

## Research Boundary

The production integration is an inference-compatible BotRHG system adapter, not a claim that CogGuard embeds the full trained NLPCC experiment pipeline. The full research implementation remains in `G:/Research/BotDetection/LLMbot`, where the method maps to RoBERTa/property encoding, HyperScan-style KNN hypergraph construction, conformal KNN residual-risk routing, and residual second-view correction.
