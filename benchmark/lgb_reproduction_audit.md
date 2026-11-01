# LGB Reproduction Audit

- Task: `bot_detection`
- KT2 position: `auxiliary_participant_risk_module`
- Strict reproduction ready: `False`
- Official data ready: `False`
- Local adapter ready: `True`
- Official converter ready: `True`
- LM SFT feature exporter ready: `True`
- External LM feature input ready: `True`
- Table III ablation scheduler ready: `True`
- Strict artifact gate ready: `True`
- Strict pipeline ready: `True`
- Data request package ready: `True`
- TwiBot-22 path: `None`
- TwiBot-20 path: `None`
- Data request package command: `python -m benchmark.adapters.lgb_bot_detection --write_data_request --dataset_root G:\CISCN\dataset --out_dir G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark`
- Strict pipeline command: `python -m benchmark.adapters.lgb_bot_detection --strict_pipeline --dataset_root G:\CISCN\dataset --artifacts_root G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\lgb_strict --device cuda --encoder_backend transformers_roberta_sft`

## Blockers
- Missing official dataset(s): TwiBot-22, TwiBot-20
- Current local adapter uses HashingVectorizer; strict LGB requires supervised RoBERTa/T5 SFT features.
- No verified five-seed TwiBot-22/TwiBot-20 mean +/- std result table is recorded locally.
- No verified Table III ablation suite is recorded locally.

## Required Full Reproduction

| Item | Requirement |
|---|---|
| datasets | ['TwiBot-22', 'TwiBot-20'] |
| text_encoder | supervised fine-tuned RoBERTa or T5 |
| graph_stage | edge-dropout GCL with InfoNCE, tau=0.4 |
| fusion | Concat(LM representation, GNN representation) + MLP |
| runs | 5 random initializations, mean +/- std |
| metrics | ['Accuracy', 'F1-Score', 'ROC-AUC'] |
| ablations | ['w/o LM SFT', 'w/o GNN fine-tuning', 'w/o GNN pretraining', 'w/o concat', 'average fusion', 'max fusion', 'SFT LM only'] |
