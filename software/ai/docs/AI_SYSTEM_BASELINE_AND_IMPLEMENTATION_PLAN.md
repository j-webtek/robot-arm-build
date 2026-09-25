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

No Ollama or llama.cpp vision-language model is currently running in the
pipeline. The existing Llama 3.2 1B candidate is text-only. Vision cannot be
added to that checkpoint with the existing text LoRA; a multimodal base model
and its matching projector are required.

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

### P0: contracts and fail-closed fusion

1. Add versioned scene-observation and fused-decision data contracts.
2. Add canonical hashing and exact frame-byte binding.
3. Implement a deterministic observer fixture for offline testing.
4. Implement fusion rules for presence, quality, occlusion, confidence,
   freshness, and identity disagreement.
5. Prove with unit tests that malformed or conflicting records cannot reach
   coordinate preview.

### P1: local multimodal observer

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

### P2: stress data and benchmark

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

