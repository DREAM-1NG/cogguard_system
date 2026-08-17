# HateCoT XLM-R Transfer Protocol

This document records the runnable XLM-R encoder experiment aligned to the
public [HateCoT paper](https://arxiv.org/abs/2403.11456) and its
[data/model repository](https://github.com/hnghiem-nlp/hatecot).

## Boundary

HateCoT's reported zero-shot result is a prompt-based LLM procedure: models
fine-tuned on HateCoT receive target-dataset definitions and generate target
labels, optionally with explanations. The public repository provides the data
and LLaMA PEFT models, not an encoder training implementation.

The local runnable is an XLM-R encoder experiment with two distinct results:

- `source_3way_transfer`: HateCoT-only supervised encoder transfer. This is
  not called the paper's prompt zero-shot result.
- `kshot_{32,64,128,256}`: target-domain adaptation starting from the
  HateCoT-trained source checkpoint, compared with `kshot_{K}_base` trained
  from the original XLM-R initialization.
- `full_data`: original XLM-R trained on all allowed target rows, without
  HateCoT explanations or source weights. It is an in-domain no-explanation
  reference, not a continuation of the source model.

The production taxonomy heads remain unchanged. Protocol heads are experiment
only: `hatecheck_binary`, `hatexplain_3way`, `latent_hate_3way`, and
`hatecot_universal_3way`.

## Labels And Splits

HateCoT source labels with stable semantics map to `Normal / Offensive / Hate`.
`Animosity`, `Threatening`, and `Support` are excluded from this three-way
source supervision and reported as skipped rather than silently reassigned.

For the encoder-only Latent_Hate transfer baseline, the source universal head
is remapped as `Normal -> Not Hate`, `Hate -> Explicit Hate`, and
`Offensive -> Implicit Hate`. The middle mapping is an explicit ontology proxy,
not evidence that source offensive annotations supervise implicit hate. The
result is labelled `ontology_proxy` in the report and cannot be interpreted as
the paper's definition-conditioned LLM zero-shot result.

HateCheck evaluates `Non-hateful / Hateful`; HateXplain evaluates
`Normal / Offensive / Hate`; Latent_Hate evaluates `Not Hate / Explicit Hate /
Implicit Hate`. HateXplain uses its published train/validation/test division.
HateCheck and the locally available Latent_Hate snapshot have no equivalent
target train split in this workspace, so their results are marked as local
snapshot protocol reproductions.

The paper's Table 1 development sample counts are retained in the manifest:
HateCheck `300/class`, HateXplain and Latent_Hate `200/class`. Section 4.2
instead forms a `256/class` K-shot pool from non-test target training rows and
draws `K={32,64,128,256}` from that pool. The runner implements this latter
rule for K-shot training and never uses any official HateXplain test row for
adaptation.

## Run

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system
$env:USE_TF = '0'
$env:TRANSFORMERS_NO_TF = '1'
python system\backend\scripts\run_hatecot_official_transfer_student.py `
  --checkpoint G:\CISCN\.tmp\hatecot_lrkd_full_xlmr_transfer_checkpoint_v3_20260813\checkpoint.pt `
  --experiment all `
  --datasets HateCheck HateXplain Latent_Hate `
  --epochs 3 --batch-size 8 --max-length 128 `
  --source-lr 2e-5 --target-lr 1e-4 --amp --device cuda `
  --output-dir G:\CISCN\.tmp\hatecot_official_transfer_xlmr_20260814
```

Each output directory includes `report.json`, `label_mapping.json`, a
dataset-specific `split_manifest.json`, predictions, confusion matrices, and
reloadable checkpoints. The report records file/snapshot hashes, label mapping
versions, class supports, and comparability notes. Only protocol-matched
three-class metrics may be compared with the HateCoT paper; binary legacy
transfer results are separate.

The source and target optimizers are intentionally separate: `2e-5` for the
HateCoT source adaptation and `1e-4` for target K-shot/full-data adaptation,
matching the paper's target-domain tuning setting. Each `dataset x K` pair
uses a stable seed and reinitializes the target protocol head identically for
the HateCoT-initialized and base-XLM-R arms. CUDA AMP is on by default for the
formal run; use `--no-amp` only for a numerical-debug run.

## Current Evidence

The implementation smoke at
`G:\CISCN\.tmp\hatecot_official_transfer_smoke_20260814b` verified the
HateCheck `300/class` development and `500/class` test manifests, source
checkpoint reload, prediction output, and confusion matrix. It used only 12
HateCoT source cases and disabled LRKD, so it is a plumbing check and is not a
performance result.

The first formal target result is at
`G:\CISCN\.tmp\hatecot_official_transfer_metric_20260814\HateCheck_b4_final\report.json`.
It reuses a separately completed full HateCoT source checkpoint (50,811
unambiguous source rows, three epochs, LRKD weight 0.2) and evaluates 1,000
disjoint HateCheck test cases. The local GPU required batch size 4 and target
checkpoint writes were disabled after Windows page-file and large-checkpoint
serialization failures; split manifests, per-case predictions, and confusion
matrices are retained. This is a partial result, not a completed three-dataset
comparison: K=32 and K=64 source-initialized adaptation beat their base-XLM-R
controls, but K=128/K=256 and the full-data control collapsed to one class.
The result therefore establishes neither a monotonic K-shot gain nor a general
transfer claim. HateXplain and Latent_Hate remain unrun because Windows virtual
memory could not map another XLM-R weight set while local services were active.
