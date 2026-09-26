# AI system baseline and implementation plan

**Baseline date:** 2026-09-25  
**Scope:** English intent, image understanding, calibrated target coordinates,
and their handoff to the existing RoCell planner  
**Authority:** offline research only; this document does not authorize camera,
robot, or contact effects

## System goal

The system must turn a user's English request into a verified sequence of
keyboard or phone interactions. It must use a fresh camera observation to
locate the device and assess whether the requested targets are visible, then
pass calibrated target coordinates to RoCell's deterministic inverse
kinematics, collision, authorization, controller, and outcome-verification
layers.

The learned models do not own servo commands. Device geometry, calibration,
motion limits, collision checks, and execution authority remain explicit
runtime contracts.

Models may propose named target coordinates through the strict
[`model_motion_proposal_v1`](../schemas/model_motion_proposal_v1.schema.json)
contract. Those coordinates remain candidates until deterministic map checks,
measured transforms, IK, full-route screening, and execution admission succeed.

## What exists today

### Intent path

- The grounded intent parser extracts a device and literal text, then asks the
  existing RoCell compiler whether the request is supported.
- It scored 30/30 on the small, agent-authored v9 set, accepting all 12
  supported requests with no wrong accepted plan.
- The evaluated Llama 3.2 1B Instruct and response-SFT candidates are text-only
  experiments. They remain blocked because their held-out results include
  false execution proposals or inadequate supported-request coverage.
- The grounded parser is therefore the current reference path. Its limited
  benchmark is not evidence of general language understanding or permission
  to execute hardware motion.

### Precision vision path

- `KeyboardPoseNet` is a small PyTorch convolutional model. It consumes a
  128 x 96 RGB image and estimates keyboard centre X/Y and yaw.
- A deterministic transform applies that pose to the nominal keyboard target
  map, producing board-frame key-coordinate candidates.
- The current checkpoint was trained with 3,600 procedurally rendered frames.
  One real setup-photo crop supplies appearance texture; it supplies no
  measured coordinate truth.
- The standard synthetic validation selected-key error has a 2.592 mm
  95th percentile. The appearance-shift validation 95th percentile is
  2.433 mm.
- A harder 300-image synthetic challenge has a 24.832 mm selected-key-error
  95th percentile. This tail is well outside the required contact accuracy.
- There is no real-camera evaluation, calibrated physical target truth,
  uncertainty head, or qualified abstention threshold.
- The model is invoked by offline scripts. It is not a resident service and is
  not connected to a live camera.

### Joint offline path

The implemented research path is:

```text
English request -> grounded intent -> named keys
synthetic image -> KeyboardPoseNet -> keyboard pose -> candidate coordinates
named keys + coordinates -> RoCell route screening
```

The most recent synthetic keyboard campaign completed 6/6 requests, 14 key
contacts, and 381/381 sampled route waypoints using an unmeasured promoted
layout hypothesis. It emitted zero hardware commands and observed zero
physical input events.

### Multimodal vision status

The P0 and P1 offline integration now exists. A strict scene-observation
contract binds every result to the exact image bytes, an Ollama adapter and a
llama.cpp-compatible adapter implement the same interface, and a fail-closed
fusion gate combines scene classification with precision coordinates.

`gemma3:4b` is the provisional local observer. The installed Q4_K_M artifact
is 3.3 GB, used about 3.0 GB of GPU memory with an 8,192-token context, and
works offline after installation. On the ten user-supplied setup photos it
matched the agent-authored keyboard-presence label 10/10 times, with 1.692 s
median and 1.993 s maximum latency. These correlated handheld photos contain
no negative device cases, phone states, measured coordinates, or deployment
camera captures.

The smaller `qwen3-vl:2b` artifact was evaluated and rejected for this runtime:
with Ollama 0.34.0 it placed repeated structured output in the thinking field
until truncation rather than returning the required JSON record. That is a
measured adapter/runtime failure, not a general judgment of the model family.

A six-case deterministic stress run accepted the unchanged control and
rejected severe darkness, blur, glare, central obstruction, and a uniform
absent-device image. The multimodal model itself still reported a keyboard
with high confidence on several adverse edits. The combined result therefore
depends on the deterministic pixel-quality gate. The development thresholds
are not calibrated physical thresholds.

The offline `shadow-preview` command now composes a request and saved
observations into one canonical zero-write record. When precision coordinates
are unavailable it records `precision_observation_missing` and exposes no
targets. The first real-photo replay demonstrates that blocked path on Photo 2.

## Target architecture

```text
                         +------------------------+
user request ----------> | intent interpreter     | ---- semantic actions ---+
                         +------------------------+                          |
                                                                               v
camera frame ----------> +------------------------+                    +-------------+
       |                 | precision pose model   | -- pose/targets --> | fusion gate |
       |                 +------------------------+                    +-------------+
       |                                                                      |
       +---------------> +------------------------+ -- scene quality --------+
                         | multimodal observer    |     and visibility
                         +------------------------+
                                                                               v
                       measured calibration -> target resolver -> RoCell planner
                         -> authorization -> controller -> outcome observation
```

The precision branch estimates geometry. The multimodal observer classifies
scene conditions such as device presence, layout, lighting, blur, glare,
occlusion, and visible phone state. The fusion gate requires both outputs to
refer to the exact same image bytes and rejects stale, low-confidence,
occluded, or contradictory observations.

The first multimodal observer will not supply final servo angles or bypass
RoCell. Coarse corners or pose proposals may be evaluated later, but they must
be checked against calibrated geometric observations.

## Runtime strategy

Define one internal `VisionObserver` contract and place runtime-specific code
behind adapters:

1. **Ollama adapter first.** It provides the shortest local integration path,
   accepts image input, and supports schema-constrained JSON responses.
2. **llama.cpp adapter second.** It supports deployable GGUF model and
   projector artifacts through `llama-server`, but its multimodal interface is
   still evolving. It must produce the same internal observation record.
3. **Deterministic fixture adapter.** Tests and benchmarks must run without a
   downloaded model or network service.

Every observer result must bind:

- schema version;
- frame ID and SHA-256 of the exact encoded image bytes;
- capture time when available;
- runtime, model name, and model identity supplied by configuration;
- bounded scene classifications and confidence values;
- an observation SHA-256 over the canonical record.

The runtime must reject unknown fields, invalid enum values, non-finite
numbers, a changed image hash, mismatched frame IDs, weak visibility, material
occlusion, adverse image quality, or observer/pose disagreement.

## Prioritized implementation

### P0: contracts and fail-closed fusion â€” implemented offline

1. Add versioned scene-observation and fused-decision data contracts.
2. Add canonical hashing and exact frame-byte binding.
3. Implement a deterministic observer fixture for offline testing.
4. Implement fusion rules for presence, quality, occlusion, confidence,
   freshness, and identity disagreement.
5. Prove with unit tests that malformed or conflicting records cannot reach
   coordinate preview.

### P1: local multimodal observer â€” implemented and provisionally benchmarked

1. Add an Ollama HTTP adapter with explicit endpoint, model, timeout, prompt,
   and JSON schema configuration.
2. Treat transport errors, invalid JSON, extra fields, timeouts, and model
   refusal as an abstention.
3. Add a CLI that observes one image and writes a content-bound record without
   opening a camera or commanding an arm.
4. Add a llama.cpp OpenAI-compatible adapter after the internal contract is
   stable.

Model selection is a benchmark decision. Candidate size and quantization must
fit the intended vision host's GPU memory and system RAM. A model is not
promoted based on conversational quality alone.

### P2: stress data and benchmark â€” initial seed only

Generate a frozen, provenance-marked synthetic set varying:

- exposure, contrast, white balance, shadows, and localized glare;
- motion/defocus blur, compression, and sensor noise;
- arm, tool, cable, and hand occlusion at measured severity bands;
- keyboard placement, yaw, scale, partial crop, and absent-device negatives;
- phone brightness, orientation, screens, and keyboard states.

Compare precision-only, multimodal-only, and fused results. Report pose and
selected-target millimetre error, device-presence false positives, obstruction
recall, unsafe-accept rate, abstention, latency, and memory use. Split real
data by capture session so adjacent frames cannot cross train/test boundaries.

### P3: live observation and calibration

1. Capture frames through the existing B0477 camera boundary.
2. Qualify intrinsics, board tags, static extrinsics, device registration, and
   tool-tip/contact geometry with physical measurements.
3. Feed only fused, fresh observations into a simulation-only target preview.
4. Compare predictions with independently measured board coordinates.
5. Establish thresholds on held-out physical scenes before requesting any
   motion authority.

### P4: closed-loop device tasks

1. Execute one approved contact at a time through existing RoCell gates.
2. Capture a new frame after every state-changing phone action.
3. Verify keyboard or phone effects independently of the requested command.
4. Stop, reobserve, or request clarification whenever the expected state is
   missing or ambiguous.
5. Expand from single keys to short strings, then bounded dialer workflows.

### P5: multimodal distillation

Only after measured data exists, train or distill a vision-capable student on
paired image, intent, calibration context, structured scene labels, semantic
actions, and observed outcomes. The current text-only Llama adapter cannot be
the multimodal base. Coordinate and motion validation remain deterministic
even if a later student proposes coarse geometry or waypoints.

## Completion gates

Software implementation can be completed before hardware arrival, but physical
qualification cannot be simulated into existence. The project reaches an
operational completion gate only when all of the following are demonstrated on
held-out real captures and measured geometry:

- zero unsafe accepts in the frozen adverse-scene acceptance set;
- target-coordinate accuracy within the measured safe region and contact
  budget for each supported device;
- reliable abstention under obstruction, missing device, stale frame, blur,
  glare, and observer disagreement;
- bounded end-to-end latency on the deployment host;
- collision-checked trajectories and controller feedback through RoCell;
- independent confirmation of the resulting key press or phone state;
- an explicit physical authorization review recorded by the existing safety
  system.

Until those gates pass, outputs remain offline observations, candidate
coordinates, or simulated routes.

## Arm-runtime integration track

The arm-side implementation is tracked separately in
[MODEL_COMMAND_RUNTIME_IMPLEMENTATION_PLAN.md](MODEL_COMMAND_RUNTIME_IMPLEMENTATION_PLAN.md).
Its first sequential coordinator is implemented: it consumes the admitted
ordered batch one action at a time, requires a never-reused fresh observed arm
state, blocks lookahead and automatic retries, and advances only from an exact
verified result. It remains zero-hardware while measured planning blockers are
open.

## 2026-09-26 actual-model benchmark update

A new 24-image benchmark was committed before inference, using eight unseen
seed groups (4000000-4000007) paired across standard, appearance-shift, and
challenge conditions. Source files and the selected pose checkpoint are pinned
in `eval/frozen_vision_v0.manifest.json`. Both KeyboardPoseNet and local Gemma
3 4B actually ran; this is not archived scene replay or injected coordinates.

Across all 46 key positions per image, 95th-percentile error was 2.694 mm for
standard scenes, 2.006 mm for appearance shift, and 30.830 mm for challenge
scenes. The scene/pixel quality check accepted 6/8 standard, 8/8 shifted, and
8/8 challenge scenes. Three challenge scenes were accepted despite maximum
key errors of approximately 16.79, 37.65, and 14.13 mm, exceeding the
predeclared 5 mm diagnostic budget. This is a quality-filter false acceptance
relative to synthetic coordinate truth, not a physical execution event or
a measurement of full vision-fusion admission.

The set is now consumed. Keep its seed groups out of training and use a new
held-out set for the next model or gate change. The immediate priority is
localization-specific abstention and harder development data; scene quality
alone does not bound geometric error. No model weights were changed by this
evaluation. No route or hardware command ran.

The renderer uses a fixed synthetic top-down projection, not calibrated
deployment optics. Truth is independent of model predictions but comes from
the same renderer family used in training. Eight paired groups cannot establish
real-world reliability; no absent-device or phone examples are included.

## Independent localization-radius evaluation

The frozen `localization_radius_v0` study uses 100 calibration and 100 disjoint
evaluation seed groups, each with standard, appearance-shift, and challenge
conditions: 600 images total. Its score is the worst XY error across all 46
keys and all three conditions within each group. Correlated key errors are
therefore not counted as independent calibration samples.

The unchanged checkpoint's empirical 95% nearest-rank calibration radius is
**25.409 mm**. Applied unchanged to evaluation, it covers **90/100 groups**,
below the 95% target. It fits **0/46** nominal key safe rectangles even when
centered ideally. No qualification is installed; precision v2 still abstains.

This is empirical coverage in a shared renderer family, not a statistical or
physical guarantee. The evaluation split is now consumed. Next improve
localization robustness or rejection on separate development data, then freeze
new calibration and evaluation groups. Increasing the bound cannot resolve
the already-zero target-fit coverage.

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

## Larger conservative uncertainty study

The unchanged robust candidate was evaluated on 1,000 fresh calibration seed
groups and 500 fresh evaluation groups, three image conditions per group
(4,500 images). Before inference, the study committed a 99% empirical
calibration quantile and acceptance criteria of at least 95% held-out group
coverage plus 46/46 ideal nominal center fits. The calibration quantile and
evaluation criterion are intentionally different and were not adjusted after
scoring.

The resulting radius is **6.038 mm** and covers **494/500 groups (98.8%)**.
It fits all 46 nominal rectangles at their centers. Both declared synthetic
criteria pass. This is descriptive held-out coverage, not a population
confidence bound, real-camera validation, or proof of physical contact. A
6 mm radius leaves little margin for displaced predictions, and the actual
batch producer must check each uncertainty region against its named target.

The result remains `SYNTHETIC_CRITERIA_PASS_UNQUALIFIED`: no qualification is
installed, the default model is unchanged, and no hardware commands ran.
Full image/pose evidence is reproducible via
`vision/evaluate_conservative_radius.py`; the compact committed scorecard
preserves group hashes, scores, and the full-study hash. Both splits are now
consumed. Next exercise rejection near target boundaries using this fixed
bound and actual predictions in a fresh synthetic integration study before
considering a strictly simulation-only qualification.
