# KT2 Full Protocol Run Status

Started: 2026-06-29 12:44 Asia/Shanghai
Workdir: G:\CISCN\CogGuard\subsystems\cogguard_dev
Data root: G:\CISCN\dataset\forest-data
Output: benchmark\kt2_sequence_vs_minds_full_protocol_5ep_streamed.json
Config: kt2-sequence-vs-minds-full-protocol-5ep-streamed

Protocol:
- datasets: douban,twitter,memetracker
- seeds: 42,43,44
- MINDS epochs: 5
- KT2SequenceJointModel epochs: 5
- cascade truncation: none (`--max_minds_cascades 0`, `--kt2_max_train_cascades 0`, `--kt2_max_test_cascades 0`)
- device: cuda

Current process at note time:
- parent: python -m benchmark.kt2_minds_comparison (PID 17768 when recorded)
- child: MINDS douban seed 42 (PID 27912 when recorded)

Important fixes applied before full run:
- benchmark/adapters/cascade_io.py now accepts float timestamps by converting to integer milliseconds.
- benchmark/adapters/minds_runner.py avoids the legacy dense previous-user mask allocation and computes top-k metrics without full NumPy argsort.
- benchmark/same_protocol_full_run_baselines.py supports streaming adapter logs.
- benchmark/kt2_minds_comparison.py writes per-MINDS-pair logs under benchmark/logs.

Verification before launch:
- `python -m pytest tests\test_smoke.py -q` => 85 passed, 6 warnings.
- `benchmark\kt2_patch_three_dataset_smoke.json` => 3 datasets, 1 seed, both MINDS and KT2SequenceJointModel status ok.

Monitor commands:
```powershell
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | Sort-Object CreationDate -Descending | Format-List
Get-Content benchmark\logs\MINDS_douban_seed42_kt2-sequence-vs-minds-full-protocol-5ep-streamed.log -Tail 80
python -c "import json; p='benchmark/kt2_sequence_vs_minds_full_protocol_5ep_streamed.json'; d=json.load(open(p,encoding='utf-8')); print(d.get('status'), d.get('full_validation_passed'), len(d.get('rows',[])), len(d.get('comparisons',[])), len(d.get('missing_pairs',[]))); print([(r.get('model'),r.get('dataset'),r.get('seed'),r.get('status'),r.get('elapsed_s')) for r in d.get('rows', [])[-6:]])"
```

Resume command if interrupted:
```powershell
python -u -m benchmark.kt2_minds_comparison `
  --datasets douban,twitter,memetracker `
  --seeds 42,43,44 `
  --forest_data_root G:\CISCN\dataset\forest-data `
  --minds_repo G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS `
  --max_minds_cascades 0 `
  --minds_epochs 5 `
  --minds_batch_size 4 `
  --minds_emb_dim 64 `
  --minds_max_seq_length 200 `
  --minds_reproduction_level frontier_reproduction_full_run `
  --kt2_epochs 5 `
  --kt2_batch_size 64 `
  --kt2_hidden_dim 64 `
  --kt2_max_train_cascades 0 `
  --kt2_max_test_cascades 0 `
  --kt2_max_sequence_len 64 `
  --kt2_obs_ratios 0.1,0.3,0.5 `
  --out benchmark\kt2_sequence_vs_minds_full_protocol_5ep_streamed.json `
  --config_id kt2-sequence-vs-minds-full-protocol-5ep-streamed `
  --device cuda `
  --timeout 14400 `
  --resume
```
