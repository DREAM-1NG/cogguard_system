# NLPCC TwiBot-20 Research Runtime

## Scope

CogGuard contains a hash-verified bundle for the NLPCC account-detection
checkpoint trained on TwiBot-20. It is a **fixed-graph, transductive research
runtime**: it queries only the 11,826 labeled TwiBot-20 nodes already present
in its graph. It cannot score an arbitrary new account and is not a Chinese
online detector.

The runtime is separate from the governed Chinese account model family
`cogguard.botrhg.account.v3`. It cannot be registered as an online Active
Pointer or appear as a Chinese account-profile prediction source.

## Selection Evidence

The source experiment completed five seeds and selected checkpoints by
validation accuracy. Seed 3 was selected (`0.908828` validation accuracy,
`0.904926` validation macro-F1, validation count `5,188`). The five-seed test
comparison against low-only has mean macro-F1 improvement `0.002158` with
two-sided `p=0.6428`; this is artifact evidence, not a statistically
significant superiority claim.

## Bundle And CLI

The generated local bundle is:

`system/artifacts/social_bot_detection/nlpcc_twibot20_seed3/`

Its manifest records the checkpoint, compact node predictions, node mapping,
source manifest, selection metrics, file sizes, and SHA-256 hashes. The
deployment scope is `twibot20_transductive_research`, and
`online_account_activation_allowed` is permanently `false`.

Run from `system/`:

```powershell
python -m research.social_bot_detection.twibot20_cli info `
  --bundle artifacts/social_bot_detection/nlpcc_twibot20_seed3

python -m research.social_bot_detection.twibot20_cli predict `
  --bundle artifacts/social_bot_detection/nlpcc_twibot20_seed3 `
  --node-id u17461978
```

The checkpoint is read from the external evidence directory only during
bundle construction. The runtime imports no code from that directory.

## Deployment Boundary

Use this runtime for benchmark reproduction, fixed-node inspection, and model
card evidence. Use the Chinese `account.v3` pipeline for account profiles:
approved Chinese labels, Chinese encoder binding, leakage-safe evaluation,
calibration, shadow execution, approval, and the database Active Pointer.
Do not infer cross-dataset or cross-language transfer from the TwiBot-20
bundle. Its metrics are tied to the supplied graph, features, node order, and
split provenance.
