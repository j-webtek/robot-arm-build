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

The fourth [SFT result](sft_v3_result.json) uses balanced request pairs and
phrase-family-held-out validation. A one-epoch checkpoint was selected before
v7 because it had lower held-out validation loss and higher exact accuracy
on consumed v6 than a two-epoch checkpoint. On frozen v7, the selected model
is 15/30 exact, makes four wrong compiler-accepted plans, and has six correct
gate-admitted plans. SFT v1, run as a reference on v7, is 17/30 exact with
eight correct gate-admitted plans. SFT v3 remains **blocked**. The low
validation loss did not translate into a better v7 result.

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

The fourth pilot uses `build_sft_v3_data.py` and `fit_sft.py --data-version v3
--epochs 1` with fresh ignored directories. `sft_v3_result.json` records both
the selected one-epoch run and the two-epoch development comparison.

Use a new `--output` and `--staging-dir` for each run. The importer stages the
adapter in an ignored folder with the filenames required by this Ollama
installation. Model weights, adapter weights, and raw run files are not
committed. This SFT pilot teaches the output contract from compiler-checked
labels; it is not teacher-logit distillation or evidence of robot typing.

The [synthetic keyboard vision pilot](../docs/SYNTHETIC_VISION_TRAINING.md)
trains a separate small CNN for keyboard center/yaw from rendered pixels.
[`synthetic_pose_photo_v0_result.json`](synthetic_pose_photo_v0_result.json)
records the first photo-texture run; v1 adds mixed appearance augmentation
and has its own [result](synthetic_pose_photo_v1_result.json). The selected
checkpoint is kept in ignored `runs/` and bound by SHA-256. It was not
trained on measured key coordinates or real overhead-camera frames.

The first local multimodal comparison is recorded separately from the text
SFT experiments. [`gemma3_4b_vision_candidate.json`](gemma3_4b_vision_candidate.json)
pins the provisional 4B Q4 scene observer. The smaller
[`qwen3_vl_2b_rejected_candidate.json`](qwen3_vl_2b_rejected_candidate.json)
records its structured-output failure with the current Ollama adapter. Model
weights remain local and are not committed. Neither candidate produces servo
commands or has physical authorization.

## Challenge-robust pose candidate v0

A new KeyboardPoseNet candidate was fine-tuned from the prior checkpoint using
3,600 procedural images in 1,200 new seed groups, including the harder
challenge transformations. Development selection used 300 images in 100
separate groups; epoch 12 had the lowest development MSE. Training and
calibration/evaluation ranges were committed before training. The selected
checkpoint was pinned before scoring and remains local in
`software/ai/results/robust_pose_v0/pose_model.pt` (SHA-256
`a9590dce78cb801b9c37eab3522ce9785404ba2776152eefdde04a08983e8b60`).

On the same fresh 100 calibration and 100 evaluation groups:

| Metric | Prior checkpoint | Robust candidate |
| --- | ---: | ---: |
| Empirical calibration radius | 28.788 mm | 3.306 mm |
| Held-out radius coverage | 89/100 | 89/100 |
| Held-out group-max error, nearest-rank p95 | 36.250 mm | 4.005 mm |
| Worst held-out group error | 60.258 mm | 7.572 mm |
| Nominal center rectangles fitting radius | 0/46 | 46/46 |

The group maximum includes every key under all three paired conditions.
The coordinate accuracy improved substantially, but coverage still misses the
95% target. No qualification is installed, no default checkpoint is replaced,
and the current producer continues to abstain. The center-fit result is
optimistic geometry, not physical hit accuracy. No Gemma inference or hardware
operation ran in this training experiment. The scorecard's no-retraining note
refers to the evaluation stage; the training stage is recorded separately.

These evaluation groups are consumed. Next investigate uncertainty/rejection
on new development data and calibrate with larger fresh splits and a
predeclared conservative coverage rule. Do not increase this bound using the
observed evaluation errors or count this split as fresh evidence afterward.

## Official-mesh synthetic occlusion data

The fixed-overview Isaac evidence can be expanded into a target-specific
occlusion dataset without rerunning Isaac. The builder verifies the source
receipt and atlas hashes, materializes deterministic lighting variants, and
emits one label per target and image. Training uses `ready` and `hover_t` with
nominal, dim, and bright lighting. Evaluation holds out `hover_e` together
with warm, glare, and blur transformations, so both pose and lighting groups
are disjoint.

```powershell
python software/ai/train/build_official_mesh_occlusion_data.py `
  --source-manifest software/integrations/isaac_sim/evidence/fixed_overview_official_mesh_v1/manifest.json `
  --output-dir software/runs/official-mesh-occlusion-v1 `
  --baseline-output software/runs/official-mesh-occlusion-baseline-v1
```

This dataset teaches only `target_visible` versus `abstain` for synthetic robot
occlusion. Its evaluation split is a development fixture. It does not qualify
the physical camera, localization accuracy, collision clearance, or execution.
The optional baseline is a class-weighted logistic model over standardized
16-by-16 RGB target crops. Its fixed threshold, confusion matrix, Brier score,
ten-bin calibration error, and every misclassified case are retained in the
external scorecard. A good training score cannot promote it; the held-out
synthetic score and physical-data dependency govern that decision.

The v3 builder path accepts the 21-pose transit source recorded by
`E-20260930-AI-462`. All previously consumed endpoint poses and lighting
families become training input. Six outbound/return poses with desaturation,
dark gamma, and vignette form development. Six inter-key poses with low
contrast, right-side shadow, and motion blur remain reserved evaluation. The
three pose and lighting groups are pairwise disjoint. Materializing and hashing
the evaluation JSONL does not authorize reading it during candidate selection;
the selected checkpoint and decision threshold must be frozen first.

The first v3 spatial candidate is intentionally tiny: two convolution layers
(3→8→16), adaptive 4-by-4 pooling, and one linear head, totaling 1,649
parameters. It uses CPU-only deterministic training and selects its threshold
on development. Its evaluation result is evidence `E-20260930-AI-464`. The
model greatly reduces missed synthetic occlusions but rejects too many visible
targets, so it remains blocked and is not a runtime default.

The v4 specificity experiment is evidence `E-20260930-AI-465`. It moves all 21
consumed poses and lighting families into training, reserves six unused
near-park transit poses for development, and freezes six different unused poses
for one evaluation. The same tiny architecture reduces the held-out visible-
target false-abstention rate from 40.3% to 2.3%, but its missed-abstention rate
rises from 0.7% to 13.5%. This exposes a safety-versus-cadence tradeoff rather
than a promotable model. The evaluation is consumed, the candidate remains
blocked and synthetic-only, and another fresh split is required before tuning.

## Simulator progression videos

Retained official-mesh frames and a frozen spatial candidate can be exported
as deterministic H.264 review videos without rerunning Isaac or loading an
evaluation split for model selection:

```powershell
python software/ai/train/build_official_mesh_occlusion_data.py `
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v4-run1\manifest.json `
  --record-existing `
    C:\IsaacSim\artifacts\issue190\official-mesh-specificity-data-v1 `
    C:\IsaacSim\artifacts\issue190\official-mesh-specificity-candidate-v1 `
    C:\IsaacSim\artifacts\issue190\sim-progression-videos-v1
```

The pose progression video overlays ground-truth safe-region visibility on all
33 source poses. The candidate evaluation video overlays the frozen decision
for all targets in the 18 held-out pose/lighting images. The bundle manifest
binds the source receipt, dataset, checkpoint, scorecard, MP4 hashes, frame
counts, and zero authority. These videos visualize existing static synthetic
frames. They are diagnostic progression evidence, not continuous physics
captures, new training samples, physical-camera qualification, or deployment
evidence.

## Target-aware occlusion candidate

The v5 experiment freezes twelve unused actual-emitter schedule poses before
rendering. Six poses and three lighting families are development-only; six
different poses and three different lighting families are loaded once for
evaluation after checkpoint and threshold freeze. All previously consumed pose
and lighting groups are training-only.

The candidate adds one catalog-derived channel to the RGB target crop: a binary
mask of the named target's known safe region. The simulator robot mask remains
label-only and is explicitly excluded from model input. This keeps the model
small at 1,721 parameters while telling it which pixels matter for the proposed
target.

```powershell
python software/ai/train/build_official_mesh_occlusion_data.py `
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v5-run1\manifest.json `
  --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-data-v1-retry1 `
  --target-aware-output C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-candidate-v1-retry1
```

On the fresh synthetic evaluation, the frozen candidate misses 5 of 165
required abstentions and falsely stops on 27 of 1,185 visible targets. This is
the first candidate in this sequence to keep both synthetic rates below 5% on
its own fresh split. It remains blocked: exact catalog alignment is assumed,
the split is now consumed, and no physical camera, installed support/tool
geometry, or deployment-calibrated localization uncertainty is represented.

The same `--record-existing` mode also accepts this four-channel checkpoint:

```powershell
python software/ai/train/build_official_mesh_occlusion_data.py `
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v5-run1\manifest.json `
  --record-existing `
    C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-data-v1-retry1 `
    C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-candidate-v1-retry1 `
    C:\IsaacSim\artifacts\issue190\target-aware-progression-videos-v1
```

Its v2 video manifest identifies the fourth channel as the known target safe
region and records that the simulator robot mask is absent from model input.
The videos replay the consumed frozen evaluation for review; they remain lossy
presentation artifacts and add no training, deployment qualification, or
physical authority.

## Target-mask localization perturbation

The v6 diagnostic campaign renders six previously unused schedule states into
a development-only corpus. Its training and evaluation splits are explicitly
empty. A frozen four-channel checkpoint can then be measured at predeclared
1, 2, 4, and 8 mm target-estimate offsets in eight directions:

```powershell
python software/ai/train/build_official_mesh_occlusion_data.py `
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-mask-perturbation-v6-run1\manifest.json `
  --perturb-existing `
    C:\IsaacSim\artifacts\issue190\mask-perturbation-development-data-v1 `
    C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-candidate-v1-retry1 `
    C:\IsaacSim\artifacts\issue190\target-mask-perturbation-study-v1
```

Each offset translates the RGB crop and known-target safe-region mask together
while retaining the ground-truth occlusion label. The nominal conversion of
2 pixels per millimetre comes from the synthetic 1,000-pixel focal length and
500 mm target depth. This study measures sensitivity under nominal simulator
geometry. It is not a camera calibration, uncertainty bound, evaluation split,
or deployment qualification.

## Localization-robust candidate

The v5 training corpus can be combined with the v6 development-only corpus to
fit a deterministic offset-augmented checkpoint and freeze an uncertainty
abstention policy without opening evaluation:

```powershell
python software/ai/train/build_official_mesh_occlusion_data.py `
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-mask-perturbation-v6-run1\manifest.json `
  --train-localization-robust `
    C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-data-v1-retry1 `
    C:\IsaacSim\artifacts\issue190\mask-perturbation-development-data-v1 `
    C:\IsaacSim\artifacts\issue190\localization-robust-candidate-v1
```

Each training row receives one hash-selected nominal, 1 mm, or 2 mm offset.
Policy selection requires every development direction inside a candidate bound
to keep both missed abstentions and visible-target false stops at or below 5%.
Evidence `E-20260930-AI-471` selected a 0 mm bound: nominal development passes,
but the worst 1 mm direction misses 6 of 108 abstentions. The checkpoint must
therefore abstain on any nonzero localization uncertainty and remains blocked
without a fresh evaluation.
