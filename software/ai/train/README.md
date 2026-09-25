# Training

Training begins after the offline benchmark and deterministic/unmodified-model
baselines show a measured need. Track pinned configs, model revisions, seed,
data hash, license and output-use check, tokenizer/chat template, and final
scorecard here. Keep adapters, checkpoints, exports, and run logs in ignored
locations.

The first candidate method is response SFT on verified task proposals.
Preference or logit distillation is a later experiment tied to a specific
failure pattern. Existing ADB-agent Axolotl settings are historical examples,
not defaults for RoCell.

The first provenance-pinned small checkpoint is
[`llama32_1b_candidate.json`](llama32_1b_candidate.json). Its official Meta
source revision is cached locally and imported into Ollama at F16. Its v1
strict-schema baseline failed, so the subsequent LoRA experiments have a
measured target. Frozen challenge sets remain outside training and prompt
selection.

The first response-SFT LoRA pilot is recorded in
[`sft_v0_result.json`](sft_v0_result.json). It uses 264 synthetic training
examples and 36 validation examples from [`data/`](../data/README.md). The
adapter improved strict v1 exact matches from 0/31 to 14/31 and scored 10/24
on v2. It still proposed executable plans for five wrong v1 cases and one
wrong v2 case, so its promotion status is **blocked**. v2 has been used for
this first pilot evaluation.

The second [SFT result](sft_v1_result.json) uses 605 training and 60
validation examples with more natural paraphrases and ambiguity labels. It
was trained after the v5 benchmark was committed. On consumed v4, it improves
raw exact matches from SFT v0's 10/30 to 14/30, and the unchanged gate admits
eight correct plans instead of six. On frozen v5, it scores 15/30 raw exact,
makes four wrong compiler-accepted plans, and the gate admits six correct
plans with no wrong plans. This candidate is also **blocked** from arm control.
The model and gate have not been tuned after seeing v5 results.

The third [SFT result](sft_v2_result.json) adds 250 contrast pairs to the
v1 data. On consumed v5 it makes no wrong compiler-accepted plans, but the
gate admits only three supported requests instead of six for SFT v1. On the
frozen v6 set, raw exact matches rise from 12/30 for SFT v1 to 13/30 for
SFT v2, while admitted correct plans fall from six to two. SFT v2 still makes
two wrong compiler-accepted proposals. It is **blocked** and represents a
coverage regression despite low validation loss. Neither model nor gate was
tuned after seeing v6.

Reproduce the local pilot with the pinned Meta checkpoint already cached:

```powershell
python software/ai/train/build_sft_data.py
python software/ai/train/fit_sft.py --output software/ai/train/runs/sft_v0
python software/ai/train/import_adapter.py --adapter-dir software/ai/train/runs/sft_v0 --staging-dir software/ai/artifacts/sft-v0-import --base-tag llama32-1b-meta-92131767:latest --tag llama32-1b-rocell-sft-v0:latest
python software/ai/run_offline.py evaluate-model --model llama32-1b-rocell-sft-v0:latest
```

Reproduce the second pilot with a separate ignored output directory:

```powershell
python software/ai/train/build_sft_v1_data.py
python software/ai/train/fit_sft.py --data-version v1 --output software/ai/train/runs/sft_v1
python software/ai/train/import_adapter.py --adapter-dir software/ai/train/runs/sft_v1 --staging-dir software/ai/artifacts/sft-v1-import --base-tag llama32-1b-meta-92131767:latest --tag llama32-1b-rocell-sft-v1:latest
python software/ai/run_offline.py evaluate-model --model llama32-1b-rocell-sft-v1:latest --cases software/ai/eval/benchmark_v5.jsonl --manifest software/ai/eval/benchmark_v5.manifest.json
```

The third pilot uses `build_sft_v2_data.py` and `fit_sft.py --data-version v2`
with fresh ignored run and import directories. Its exact run configuration,
adapter hash, local Ollama digest, and scorecards are in `sft_v2_result.json`.

Use a new `--output` and `--staging-dir` for each run. The importer stages the
adapter in an ignored folder with the filenames required by this Ollama
installation. Model weights, adapter weights, and raw run files are not
committed. This SFT pilot teaches the output contract from compiler-checked
labels; it is not teacher-logit distillation or evidence of robot typing.
