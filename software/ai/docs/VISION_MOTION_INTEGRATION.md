# Intent, vision, and arm motion integration

Implementation and review must follow the
[model-to-arm translation assurance process](MODEL_TO_ARM_TRANSLATION_ASSURANCE.md).
That process is the authoritative checklist for proving that semantic model
outputs remain correctly bound through target resolution, planning, encoding,
feedback, and outcome observation.

## Desired runtime path

1. Capture a timestamped overhead image and controller state.
2. Detect the board reference, keyboard/phone placement, visible key or screen
   targets, and phone UI state. Bind every detection to the exact image bytes,
   camera calibration, and frame ID. Report uncertainty and missing targets.
3. Interpret the user's text as an operation, target device, and literal text.
4. Compile characters to named semantic targets, then match those names against
   the same fresh visual observation. A missing or ambiguous target blocks.
5. Resolve board-frame target positions through measured frame and tool-tip
   calibrations. Plan hover, approach, contact, retract, and verification using
   inverse kinematics, collision checks, and the runtime's motion policy.
6. Send only approved controller commands, collect controller feedback, and
   independently observe whether the key or screen action occurred. Reobserve
   after every state-changing phone action.

The model's useful outputs are intent and visual detections. It does not need
to memorize servo coordinates. Positions change with the camera, arm, device,
and tool installation; the motion planner computes joint targets from fresh
observations and measured calibration. A future learned policy may propose
waypoints, but the runtime must independently validate them before execution.

## Implemented offline slice

`simulate-vision` creates a hash-bound, displaced target observation from the
nominal catalog. `coordinate-preview` combines it with a grounded text request,
the RoCell semantic compiler, and the nominal target map. This tests target
identity, frame matching, coordinate propagation, and rejection of tampering,
missing targets, stale observations, and mismatched devices. These observations
are **not** image-derived. Their confidence is a simulator value, not measured
detector accuracy. The coordinates are simulation data and cannot be sent to
the arm.

## Vision model scope and data

RoCell already has an AprilTag pixel detector and board-pose estimator for
bounded synthetic JPEG tests. They can anchor the board frame once physically
qualified. A separate target detector/recognizer is needed if keyboard or
phone placement and visible UI targets cannot be determined from measured
device registration and the phone-state observer. Before training that model,
collect overhead images from the actual camera across device placements,
lighting, occlusion by the arm, phone screens, and key layouts. Label board
tags, device outlines, target centers/regions, UI state, frame identity, and
actual coordinate measurements. Split evaluation by capture session and device
placement so near-identical frames cannot leak between training and test.

The first ten [real setup photos](REAL_PHOTO_SEED_ASSESSMENT.md) are now
inventoried as one development-only capture group. They establish appearance
and scene context but lack target-coordinate and camera-calibration labels.
The [synthetic keyboard vision pilot](SYNTHETIC_VISION_TRAINING.md) uses one
photo crop as appearance texture and trains a pose CNN on simulated images.
Its pixel-derived coordinate preview is a research path with no physical
authority; a harsher synthetic challenge exposes a large error tail.

Train and score intent and vision components separately, then score their
combined target selection and coordinate error. Report detection recall,
wrong-target rate, mm position error, calibration uncertainty, and full-task
outcome. Synthetic rendering can exercise the interface but cannot qualify a
vision model on the physical workcell.

## Remaining integration gates

- Image-derived visual-target records with frame byte hash and capture time.
- Measured board, device, camera, robot, and tool-tip calibration.
- Collision-checked, executable arm trajectory and controller-command adapter.
- Runtime authorization and independent keyboard/phone effect observation.
- Physical evaluations with held-out scenes before any automatic typing.
