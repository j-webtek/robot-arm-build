# RoCell AI work area

This folder is the small, reviewable AI addition to the
[`robot-arm-build`](https://github.com/j-webtek/robot-arm-build) repository. It
will translate English requests into RoCell's existing semantic typing plans.
RoCell remains the owner of target geometry, motion, calibration, physical
authorization, controller feedback, and independent input verification.

## Current scope

- **First milestone:** offline intent-to-plan for supported keyboard and phone
  text. Return clarification or `unsupported_by_profile` for requests the
  current semantic profiles cannot compile.
- **Current intent reference:** deterministic grounded parsing backed by the
  existing RoCell compiler. The response-SFT checkpoints remain research
  comparisons because they have produced wrong executable proposals.
- **Current vision reference:** the offline `gemma3:4b` Ollama artifact is a
  provisional scene observer. It describes device presence and image quality;
  the separate `KeyboardPoseNet` branch proposes target coordinates.
- **Next:** collect static-camera keyboard and phone captures with measured
  board coordinates, then calibrate abstention and coordinate-error thresholds.

The current system baseline and the prioritized multimodal implementation are
tracked in the [AI system baseline and implementation plan](docs/AI_SYSTEM_BASELINE_AND_IMPLEMENTATION_PLAN.md).

No file here authorizes arm motion. The current RoCell development runtime has
live hardware and contact disabled. See [project status](../../PROJECT_STATUS.md)
before treating any simulated or controller-feedback result as a physical
typing result.

## Run the offline baseline

From the repository root with Python 3.10 or newer:

```powershell
python software/ai/run_offline.py propose --request 'Type "test" on the keyboard'
python software/ai/run_offline.py inspect --request 'Type "test" on the keyboard'
python software/ai/run_offline.py evaluate
python software/ai/run_offline.py review
python software/ai/run_offline.py evaluate-model --model llama-3.1-8b-instruct-q4_k_m:latest
python software/ai/run_offline.py evaluate-model --model llama32-1b-meta-92131767:latest
python software/ai/run_offline.py ground --request 'Type "test" on the keyboard'
python software/ai/run_offline.py coordinate-preview --request 'Type "test" on the keyboard'
python software/ai/run_offline.py simulate-vision --device keyboard --frame-id manual-offline --offset-x-mm 2 --output visual.json
python software/ai/run_offline.py coordinate-preview --request 'Type "test" on the keyboard' --visual-observation visual.json
python software/ai/run_offline.py observe-image --image frame.jpg --frame-id frame-001 --runtime ollama --endpoint http://127.0.0.1:11434 --model YOUR_VISION_MODEL --model-identity YOUR_PINNED_MODEL_ID --output scene.json
python software/ai/run_offline.py evaluate-scene-observer --runtime ollama --endpoint http://127.0.0.1:11434 --model gemma3:4b --model-identity ollama:YOUR_PINNED_DIGEST --output software/ai/eval/local_scene_report.json
python software/ai/vision/evaluate_scene_stress.py --source software/ai/data/raw/real_photo_seed_v0/photo_02.jpg --model gemma3:4b --model-identity ollama:YOUR_PINNED_DIGEST --output software/ai/eval/local_scene_stress.json
python -m unittest discover -s software/ai/tests
```

`observe-image` reads one existing image and calls the selected local vision
runtime. It never opens a camera or arm. Replace the model placeholders with a
multimodal model installed on the deployment host and a pinned identity from
that installation. A transport or validation failure produces an explicit,
image-bound abstention record.

The current small offline vision candidate is pinned in
[`train/gemma3_4b_vision_candidate.json`](train/gemma3_4b_vision_candidate.json).
On the ten supplied setup photos it detected the visible keyboard in 10/10
agent-labeled cases at 1.692 seconds median latency. This set has no absent
device examples, phone examples, static-camera captures, or coordinate truth.
In the six-case severe synthetic stress run, the fused scene gate rejected all
five adverse cases. The vision model itself still described a keyboard in
several corrupted or device-absent edits, so the deterministic pixel gate is
essential and this candidate is not authorized for physical control.

The `propose` command uses caller-supplied fixture state only. Its phone state
defaults to `UNKNOWN`; pass `--phone-state KEYBOARD_LOWER` only for an offline
case where that state is part of the fixture. These commands do not open an arm
or camera and do not authorize typing. The committed
[baseline scorecard](eval/baseline_v0_scorecard.json) records the first 28-case
sanity benchmark. The [simulated review](eval/simulated_review_v1.json) and
[v1 scorecard](eval/baseline_v1_scorecard.json) cover the frozen 31-case
paraphrase set. No person reviewed the v1 labels; the baseline has one false
execution proposal, so it is not ready for arm control.

The local Llama 3.1 8B Q4 candidate is evaluated with `evaluate-model` using
an explicit task prompt and a pinned Ollama model digest. Its
[v1 scorecard](eval/llama31_8b_q4_v1_scorecard.json) is offline evidence only.
The installed artifact's weight origin and license are unverified; this run
does not authorize hardware execution or model redistribution.

The official Meta Llama 3.2 1B Instruct source revision and imported local
digest are recorded in the [candidate manifest](train/llama32_1b_candidate.json).
Its [offline v1 scorecard](eval/llama32_1b_official_v1_scorecard.json) shows
that the current strict proposal prompt fails on all 31 cases. A separate
[v2 challenge set](eval/benchmark_v2.manifest.json) was frozen before the
first training experiment.

The [first SFT result](train/sft_v0_result.json) scores 14/31 on v1 and 10/24
on v2. It still makes false execution proposals, so it is blocked from arm
control. The [request-grounding gate](rocell_ai/admission.py) now checks an
explicit device, one exact quoted payload, a typing request, fresh state, and
RoCell compiler support before accepting a model proposal. On the v3 challenge
set, SFT v0 scores 11/30 raw with four wrong compiler-accepted plans. The gate
accepts seven correct plans, blocks all four wrong plans, and blocks five
supported requests. This is an offline coverage and safety observation, not
permission for arm control. A gate rule was adjusted after inspecting a v3
request, so that admission result is exploratory.

The [v4 challenge](eval/benchmark_v4.manifest.json) was committed before
scoring against the unchanged admission policy. Its manifest's policy hash had
a transcription error that was corrected after scoring; the policy file and
cases were unchanged. On its 30 agent-authored cases, SFT v0
scores 10 exact with six wrong compiler-accepted plans. The unchanged gate
admits six correct plans, blocks all six wrong plans, and blocks six of 12
supported requests. This clean offline check measures a narrow request set;
it does not establish general safety or physical typing success.

The [second SFT pilot](train/sft_v1_result.json) uses broader synthetic
phrasing. It improves raw accuracy on the consumed v4 set, but on the frozen
v5 challenge it still produces four wrong compiler-accepted plans out of 30
cases. The fixed gate blocks those four and accepts six correct plans, while
rejecting six supported requests. Both model candidates remain barred from
arm control; a new benchmark is required before further tuning.

The [contrast-pair pilot](train/sft_v2_result.json) reduced raw wrong-plan
proposals on the frozen v6 challenge but also reduced correct admitted plans
from six to two compared with SFT v1. It remains blocked. This result shows
why raw exact accuracy, wrong-plan rate, and supported-request coverage are
reported separately.

The [balanced-data pilot](train/sft_v3_result.json) used validation phrases
held out by template family. On frozen v7, it still trails SFT v1: six
correct gate-admitted plans versus eight, with four wrong raw plans the
compiler would accept. SFT v1 remains the strongest measured offline
reference, and every model remains blocked from arm control.

The [grounded intent path](rocell_ai/grounded.py) is a new offline alternative:
it extracts one target and exact payload from the request, then asks RoCell's
compiler whether the text is supported. It does not use model-generated text
or device slots. On the frozen 30-case v9 set it accepts all 12 supported
requests with no wrong accepted plans, compared with eight correct and one
wrong admitted plan for SFT v1 plus the older gate. These cases are
agent-authored and small; the grounded path is still blocked from arm control.

The [coordinate preview](rocell_ai/coordinate_preview.py) resolves a grounded
request's named keys or phone targets to board-frame millimetre coordinates.
It can consume a [simulated visual-target observation](rocell_ai/visual_observation.py)
that shifts those coordinates with a mock device placement. The observation is
generated from nominal target data, **not** recovered from image pixels or a
trained vision model. Output includes the source hash, frame ID, semantic plan,
and explicit execution blockers. It contains no controller commands. This is
the first integration seam for a future image detector, calibrated motion
planner, and result observer; see [vision/motion integration](docs/VISION_MOTION_INTEGRATION.md).

A [synthetic keyboard vision pilot](docs/SYNTHETIC_VISION_TRAINING.md) now
trains a small image-to-keyboard-pose CNN using procedural scenes mixed with
a crop from the user-provided Photo 5. A joined offline command runs text
intent through image-predicted keyboard pose to candidate key coordinates.
The separate synthetic challenge has a 24.83 mm 95th-percentile key-position
error; no real-camera accuracy is known and no arm commands are emitted.

## Folder map

| Path | Purpose |
| --- | --- |
| [`docs/`](docs/README.md) | AI contract, source boundary, and implementation plan |
| [`schemas/`](schemas/README.md) | Versioned English-to-task proposal and result formats |
| [`eval/`](eval/README.md) | Frozen offline cases, scoring, and baseline comparisons |
| [`data/`](data/README.md) | Dataset manifests and provenance-marked examples only |
| [`train/`](train/README.md) | Pinned model and training manifests after baseline evidence |

The existing `software/src/rocell/models/actions.py` and
`software/src/rocell/typing/` are the integration boundary. Do not copy the
older ADB-agent source tree or model artifacts into this folder.
