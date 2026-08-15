# Claim Response Landscape Design

## Goal

Add one evidence-first `主张回应图谱` tab to Propagation Analysis. It lets an
analyst inspect a bound authority claim, the official accounts that published
it, the high-propagation accounts that responded to it, and the observed paths
that carry those responses.

## Boundary

- It is an observed-evidence projection, not a fact checker, credibility
  classifier, or risk-score input.
- An account appears as an official source only when an allowlisted
  `AuthoritySource` has an exact `(platform, author_id)` binding.
- Platform verification is stored as a verification snapshot. It can support a
  review decision but never creates an official-source classification itself.
- An influential account is ranked only within its event and platform using
  observed downstream reach and path contribution. Followers and engagement
  are contextual attributes, not authority signals.
- Stance remains relative to a bound primary claim. Sentiment is not a proxy
  for stance. Missing semantic evidence is reported as unavailable.

## Domain Model

`AuthoritySourceAccount` is an administrator-maintained, reviewed binding from
an allowlisted authority source to one platform account. It records the
platform account id, a display-name snapshot, and optional platform
verification evidence.

`Claim Response Landscape` is a read-only event projection keyed by a primary
claim. It contains a claim anchor, official publications, influential account
responses, and path-backed propagation metrics. Each visible response retains
a post reference and any exact evidence-path references used to compute it.

## Projection Contract

The read endpoint returns one of `ready`, `not_found`, or `blocked` and, when
ready, contains:

- `claim_anchor`: exact quote, source, tier, timestamp, and source URL;
- `official_publications`: exact account-bound posts with optional semantic
  fields;
- `influential_responses`: per-platform ranked accounts with downstream reach,
  path count, entry time, and platform-local engagement percentile;
- `timeline`: official and response events keyed by evidence references;
- `coverage`: explicit availability of author verification, followers,
  engagement, semantic evidence, and propagation paths.

## Product Presentation

The propagation page adds one tab called `主张回应图谱`:

1. A fixed claim anchor shows the exact authority quote and source provenance.
2. A two-lane timeline aligns official publications above influential account
   responses. Node size represents observed downstream reach, and response
   color represents stance only when a semantic artifact is ready.
3. Selecting a timeline node opens the existing evidence and path drill-down;
   the detail panel shows the original text, account context, semantic labels,
   and propagation contribution.
4. A compact platform-local influence list filters the response lane. It is not
   a separate global leaderboard.

The view shows explicit empty or blocked states. It never creates a synthetic
official source, a synthetic stance, or an unlinked propagation path.

## Verification

- Exact source account binding is required; same-name and verification-only
  accounts are excluded from official publications.
- Ranking is platform scoped and uses only path-backed downstream reach and
  path contribution as primary order keys.
- Every displayed official publication and response can resolve to a post and,
  where claimed, to exact path evidence.
- Missing artifacts and fields render unavailability rather than inferred
  values.
