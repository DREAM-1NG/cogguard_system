# Propagation Fair Comparison

## Scope

This benchmark only reports methods that can be evaluated under the same
propagation protocol.

| Table | Included methods | Excluded from this table |
| --- | --- | --- |
| Macro size / trend | Ours, MINDS, CasFT | FOREST, TGN, DyGFormer |
| Micro next-hop | Ours, MINDS, FOREST | CasFT, TGN, DyGFormer |

TGN and DyGFormer are not included in the formal Macro/Micro tables in this
round because their native task is temporal link prediction. They require a
separate temporal-link table or a new cascade-prefix user-ranking adapter.

## Fair Protocol

All formal rows must satisfy:

- Use native FOREST split files: `cascade.txt`, `cascadevalid.txt`, `cascadetest.txt`.
- Build `user_id -> vocab_id` from `cascade.txt` only.
- Reserve `PAD=0`, `EOS=1`, `UNK=2`.
- Map validation/test unseen users to `UNK`.
- Build observation windows from `obs_ratio = 0.1, 0.3, 0.5`.
- Generate candidate users from the training vocabulary, not from the future tail.
- Report OOV and candidate coverage.
- Use learned logits/scores, not transition/popularity proxy ordering.
- Set `fair_protocol_passed=true` before a row may enter a formal summary.

## Files

- `benchmark/adapters/fair_protocol.py`: split loader, vocabulary, prefix windows, metrics, and audit gate.
- `benchmark/adapters/fair_learned_adapters.py`: same-protocol learned adapters for Ours, MINDS, FOREST, and CasFT.
- `benchmark/propagation_fair_full_matrix.py`: formal matrix orchestrator and report generator.
- `benchmark/run_propagation_fair_full_matrix_20260812.ps1`: long-running full-source launch script.
- `tests/test_fair_propagation_protocol.py`: protocol and adapter smoke tests.

## Smoke Run

Use this before any long run:

```powershell
python -m pytest tests/test_fair_propagation_protocol.py -q
python -m benchmark.propagation_fair_full_matrix `
  --datasets douban `
  --seeds 42 `
  --models Ours,MINDS,FOREST,CasFT `
  --epochs 1 `
  --train_limit 20 `
  --eval_limit 8 `
  --batch_size 4 `
  --hidden_dim 16 `
  --max_sequence_len 32 `
  --max_train_users 256 `
  --device cpu `
  --output benchmark\propagation_fair_smoke.json `
  --report benchmark\propagation_fair_smoke.md
```

Smoke outputs are engineering checks only. Do not cite them as performance
evidence.

## Full-Source Run

```powershell
.\benchmark\run_propagation_fair_full_matrix_20260812.ps1 `
  -Device cuda `
  -Epochs 200 `
  -TrainLimit 0 `
  -EvalLimit 0 `
  -MaxTrainUsers 0
```

Outputs:

- `benchmark/propagation_fair_full_matrix_20260812.json`
- `benchmark/propagation_fair_full_matrix_20260812.md`
- `benchmark/propagation_fair_full_matrix_20260812_logs/fair_full_matrix.status.json`
- `benchmark/propagation_fair_full_matrix_20260812_logs/fair_full_matrix.stdout.log`
- `benchmark/propagation_fair_full_matrix_20260812_logs/fair_full_matrix.stderr.log`

## Claim Boundary

The same-protocol adapters make the rows comparable by task and metric. They are
not a claim that every original GitHub repository has been reproduced unchanged.
Original public runners that re-split data, build graphs from all cascades, use
hash buckets, or output proxy rankings remain reproduction evidence only until
they are adapted to the shared protocol.
