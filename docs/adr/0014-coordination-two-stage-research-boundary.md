# ADR 0014: Coordination Discovery And Harmful Detection Research Boundary

- Status: accepted
- Date: 2026-08-08
- Decision owners: CogGuard research and backend maintainers
- Related: ADR 0012

## Context

Coordination research previously mixed three different meanings of
"detection": finding coordinated behavior, classifying harmful intent, and
analyst/agent review. That made it possible to overstate an unsupervised
community score as a harmful-CIB conclusion, or to let external evaluation
labels influence Discovery implementation choices.

The system has a stable evidence-constrained Discovery mainline
(`coordination-evidence-runtime-v2`). New TSGS/MHCR and learned Detection code
is research-only until it passes a task-aligned, leakage-safe activation gate.
IOHunter provides useful external account labels, but its processed graphs do
not provide harmful-CIB Gold, true coordination-edge/community labels, causal
annotations, or observed timestamps.

## Decision

Adopt a one-way, two-stage research boundary.

| Stage | Allowed inputs | Forbidden inputs | Output | Activation rule |
| --- | --- | --- | --- | --- |
| Discovery | Observed account-object relations, native relations, timestamps when available, and content-derived coordination evidence | harmful-CIB, bot, faction, account-risk, evaluator, fold, and test labels | `DiscoveredClusterBatch` | Never activates production directly. |
| Detection | A serialized `DiscoveredClusterBatch`, explicit detection-only features, and labeled train/validation cases | Stage 1 fitting internals, test-fitting, and heuristic-only primary decisions | `ClusterDetectionBatch` | Requires target-task Gold, leakage-safe holdouts, calibration, selective-risk evidence, and approved activation review. |
| Product runtime | Frozen evidence-constrained Discovery output | Research candidate artifacts without gate approval | Existing product coordination result | Continues unchanged until a candidate is approved. |

`DiscoveredClusterBatch` is the only Stage 1 to Stage 2 seam. It is versioned,
checksummed through its fingerprint, and represents unsupervised candidate
clusters. Its ranking values are not harmfulness probabilities.

The `heuristic_baseline_v1` fixed Bayesian weights remain an explicit baseline.
They cannot be trained, silently selected, used as a learned detector, or used
to activate a model.

Experiment outputs, caches, temporary files, reports, and signed artifacts for
this work must use explicit G-drive locations. C-drive temporary paths are not
valid artifact roots.

## Consequences

### Positive

- Stage 1 can be audited as genuinely label-free.
- Stage 2 model coefficients, calibrators, thresholds, and OOD bounds have a
  clear train/validation provenance.
- Research proxy results cannot silently replace the product runtime.
- Artifact rows, prediction bundles, source hashes, and claim decisions give
  interrupted matrix runs a recoverable audit trail.

### Costs

- A useful Discovery case study can still be unable to support a harmful-CIB
  performance claim.
- Data adapters and experiments carry more split, fingerprint, and capability
  metadata.
- The full IOHunter proxy matrix is expensive and remains insufficient for the
  target harmful-CIB claim even when completed.

## Claim Rules

| Claim type | Current status | Required evidence before promotion |
| --- | --- | --- |
| Research pipeline and contract implementation | supported | Tests and checksummed artifacts. |
| External account-recovery proxy comparison | blocked | All 30 canonical IOHunter campaign-seed pairs and a positive paired 95% bootstrap CI lower bound. |
| True coordination recovery | blocked | External edge/community ground truth. |
| Harmful-CIB Detection | blocked | Target-task Gold labels, Stage 2 evaluation, leakage-safe campaign/platform/time holdouts, calibration and abstention results. |
| Observed-time coordination claim | blocked for IOHunter processed graphs | Dataset with recorded event timestamps. |
| Production activation | blocked | All task-aligned gates plus independent review and model governance approval. |

## Rejected Alternatives

- Treat unsupervised coordination rankings as harmful-CIB probabilities:
  rejected because they answer different tasks.
- Let IOHunter labels enter TSGS/MHCR fitting or selection: rejected because it
  leaks evaluation supervision into Discovery.
- Promote a fixed Bayesian rule as the learned detector: rejected because it
  cannot adapt coefficients, calibration, or abstention to a labeled corpus.
- Replace the production runtime on proxy improvement alone: rejected because
  IOHunter's capabilities do not cover the product claim.

## Verification

`test_coordination_stage1_contracts.py`,
`test_coordination_stage1_tsgs.py`,
`test_coordination_stage1_mhcr.py`,
`test_coordination_stage2_detection.py`, and the compact IOHunter matrix tests
enforce the contract, label ordering, split provenance, artifact checksums, and
claim gates. The current Russia artifact smoke is execution validation only;
its claim decisions remain blocked as recorded in the G-drive output root.
