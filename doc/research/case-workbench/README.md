# Case Workbench Research Pack

This directory is the Task 01 research and provenance foundation for the proposed Case Workbench. It is intentionally narrow: it records design-relevant comparisons, model-governance constraints, seed-data facts, and a small reproducible source set. It is not evidence that any vendor, model, or research implementation has been deployed or evaluated in CogGuard.

## Contents

| File | Purpose |
| --- | --- |
| [implementation-comparison.md](implementation-comparison.md) | Product/technical capability comparison and constrained adoption decisions. |
| [model-selection-governance.md](model-selection-governance.md) | Pinned candidate models, semantic isolation rules, and required local evaluation. |
| [twitter-benchmark-manifest.json](twitter-benchmark-manifest.json) | Verified metadata/statistics/hash only for the separate Twitter benchmark. |
| [source-metadata.json](source-metadata.json) | URLs, retrieval status, license/retention decisions, and source limitations. |
| [sources/originals](sources/originals) | Small MIT-licensed authoritative technical-source HTML originals. |
| [sources/conversions](sources/conversions) | Microsoft MarkItDown conversions plus provenance metadata. |

## Evidence Scope

- `trump_visit_2026_05_21` is the Case Workbench seed event, not a completed cross-platform dataset. Current known coverage is Weibo only: 74 unique main posts from 57 authors and 5,048 unique comments from 4,492 comment users. The core window is 2026-05-14..17 Beijing time and the context window is 2026-05-08..20. A same-event Douyin collection is planned and coverage remains `partial_collection` until it is captured.
- The supplied CCTV and Xinhua quotes are claim seeds, not independently retrieved source pages. Both are expected to be `central_mainstream_media` after administrator allowlisting, while their independent ClaimRoles are `primary` and `supporting`. Before article capture/review, an AuthoritySource has `authority_tier = null` and `review_status = pending_review`; implementation must add exact URLs, accounts, publication times, captured content hashes, and Unicode spans before a CaseClaim can be saved.
- The Twitter benchmark manifest is deliberately separate from case evidence. The repository contains neither the CSV nor a full CSV-to-Markdown conversion.
- Vendor URLs are unverified discovery references. No capability statement was captured, retained, or used as a design input.
- Model cards/readmes establish identifiers and upstream behavior, not Chinese-domain performance, calibration, safety, or suitability for CogGuard. All semantic outputs remain `candidate_unvalidated` pending local evaluation.

## MarkItDown Record

The retained source documents were converted with the prescribed wrapper:

```powershell
python C:\Users\p\.codex\skills\markitdown\scripts\convert_literature.py \
  "doc\research\case-workbench\sources\originals" \
  --recursive \
  --out-dir "doc\research\case-workbench\sources\conversions" \
  --overwrite
```

Successful retained conversions:

- [BERTopic README conversion](sources/conversions/bertopic-readme-ce5816b8.md), paired with [metadata](sources/conversions/bertopic-readme-ce5816b8.meta.json).
- [KeyBERT README conversion](sources/conversions/keybert-readme-e8d74b8d.md), paired with [metadata](sources/conversions/keybert-readme-e8d74b8d.meta.json).

Both sources are MIT-licensed repository documentation. CooRTweet, Hoaxy, DISARM, and the BERTopic arXiv paper were inspected for bounded source comparison but not retained in this repository when the license/retention decision was not equally clear or the source was outside the minimal retained set; their URLs, hashes where observed, and explicit exclusion reasons remain in `source-metadata.json`.

## Review Boundary

The resulting design is in [the approved Case Workbench spec](../../../docs/superpowers/specs/2026-08-10-case-workbench-design.md), with executable tasks in [the implementation plan](../../../docs/superpowers/plans/2026-08-10-case-workbench.md). Any implementation that changes a listed decision must update the spec and the appropriate source/validation record rather than silently treating this pack as current runtime evidence.
