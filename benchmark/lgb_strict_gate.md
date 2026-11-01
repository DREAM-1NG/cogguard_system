# LGB Strict Reproduction Gate

- Paper: `LGB: Language Model and Graph Neural Network-Driven Social Bot Detection`
- Task: `bot_detection`
- Status: `incomplete`
- Strict reproduction complete: `False`
- Artifacts root: `G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict`

## Dataset Checks

### TwiBot-22

- Directory: `G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict\TwiBot-22`
- Status: `missing`

| Check | Status |
|---|---|

### TwiBot-20

- Directory: `G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict\TwiBot-20`
- Status: `missing`

| Check | Status |
|---|---|

## Open Items

- TwiBot-22: missing artifact directory G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict\TwiBot-22
- TwiBot-20: missing artifact directory G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict\TwiBot-20

## Completion Rule

Each dataset must provide conversion_summary.json, strict RoBERTa/T5 lm_sft_report.json, 5-seed lgb_multiseed_summary.json with Accuracy/F1/ROC-AUC mean/std, and complete Table III ablation suite.
