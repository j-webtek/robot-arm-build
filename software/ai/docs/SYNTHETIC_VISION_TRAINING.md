# Synthetic keyboard vision pilot

## Why this experiment exists

The intended fixed overhead camera is not mounted or calibrated yet. The
repository contains nominal keyboard geometry and a separate photo-based
placement study. Ten new user-supplied setup photos show the actual keyboard
appearance but do not provide measured key coordinates. This pilot trains a
small CNN to estimate keyboard center and yaw from simulated pixels, then
maps named RoCell keys through that estimated pose. It is an integration and
simulation experiment, not physical calibration or a robot command source.

The prior [photo study](../../docs/PHOTO_ESTIMATED_KEYBOARD_SCREEN.md) suggests
the keyboard key layout is approximately 180 degrees from the nominal board
axes. Its annotated Photo 10 SHA-256 differs from the newly supplied Photo 10
SHA-256. We use the half-turn and approximate keyboard center as broad render
priors, never as labels for the new capture set.

## Data and model

[`synthetic_keyboard.py`](../vision/synthetic_keyboard.py) renders 256×192 RGB
board images with keyboard translations up to 30 mm horizontally and 24 mm
vertically, yaw within 11 degrees of a half-turn, printed marks, seams,
ruler-like clutter, lighting variation, blur and arm-like occlusion. It mixes
procedural keys with one agent-rectified crop of the user's Photo 5. That crop
is appearance only: its source quadrilateral is approximate and is not a
key-center annotation. The JPEG and crop remain in ignored local data.

[`KeyboardPoseNet`](../vision/pose_model.py) receives downsampled 128×96
pixels and predicts center XY and yaw. It does not read key legends or phone
UI. Named key positions come from RoCell's nominal keyboard map and are
rigidly transformed by the predicted pose. The image-to-millimetre conversion
is known to the simulator; no real camera extrinsic is inferred.

The selected v1 run used 3,600 generated training frames, 300 standard-style
validation frames, and 300 altered-style validation frames. Training mixed
standard and altered styles. All validation seeds are disjoint from training,
but all images share this one renderer and the same Photo 5 crop. The local
checkpoint is ignored by Git; [the result](../train/synthetic_pose_photo_v1_result.json)
pins its SHA-256, source hashes, seed, and metrics.

| Evaluation | Mean selected-key XY error | 95th percentile |
| --- | ---: | ---: |
| v0, standard synthetic validation | 1.83 mm | 3.51 mm |
| v0, altered appearance | 5.69 mm | 12.94 mm |
| v1, standard synthetic validation | 1.21 mm | 2.59 mm |
| v1, altered appearance | 1.19 mm | 2.43 mm |
| v1, separate challenge after selection | 5.10 mm | 24.83 mm |

The [separate challenge](../eval/synthetic_pose_v1_challenge.json) adds stronger
illumination, contrast, blur, glare and arm-like occlusion to 300 new seeds.
It was evaluated once after v1 selection; we have not tuned v1 against it.
Its long error tail shows that same-renderer accuracy is not enough for
coordinate release. There is **no measured real-photo or real-camera accuracy**.

## Joined offline path

[`run_joint_preview.py`](../vision/run_joint_preview.py) renders a new synthetic
image, hashes its pixels, infers keyboard pose from the trained checkpoint,
transforms RoCell target names to candidate board coordinates, and combines
them with a grounded English typing request. The resulting
[`visual_targets_v1`](../schemas/visual_targets_v1.schema.json) record binds
image, model, frame and target-catalog hashes. `coordinate-preview` returns
candidate coordinates and no controller commands. Unsupported requests remain
blocked. This is a joined inference demonstration, not a trained multimodal
Llama or a live arm adapter.

Run locally from the repository root after the ten photos have been ingested:

```powershell
python software/ai/vision/train_pose.py --output software/ai/train/runs/a-new-run --train-count 3600 --validation-count 300 --epochs 20 --train-domain mixed --photo-path software/ai/data/raw/real_photo_seed_v0/photo_05.jpg
python software/ai/vision/run_joint_preview.py --request 'Type "hi" on the keyboard' --checkpoint software/ai/train/runs/synthetic_pose_photo_v1/pose_model.pt --photo-path software/ai/data/raw/real_photo_seed_v0/photo_05.jpg --seed 1000001
```

Use a new output directory for retraining because runs are immutable. The
model checkpoint, rendered images, and original photos are not on GitHub.

## Next image evidence

Acquire fixed-camera frames with intrinsics, capture identity, measured
board-to-camera registration, keyboard placement, and target annotations.
Evaluate the current checkpoint without fitting to that session; expect a
large domain gap. Collect distinct placements and sessions before tuning.
Phone screen-state and target localization need a separate image dataset;
the current model is keyboard-only.

## Offline keyboard route and outcome rehearsal

[`run_keyboard_rehearsal.py`](../vision/run_keyboard_rehearsal.py) extends the
joined preview through RoCell's static-overhead geometric dry run, sampled IK,
and dense sequential waypoint screen. A bounded simulation-only overlay places
RoCell's keyboard envelope and named targets at the image model's predicted
center and yaw. The script verifies that the AI and static catalogs have the
same key geometry and that the semantic key sequences agree.

A separate virtual keyboard resolves each predicted contact point against the
**hidden synthetic true** key rectangles. It reports the key that would be hit
if every contact were reached. The route result controls whether the report
may show a simulated completed string. A virtual hit alone is not a press, and
the route screen does not prove a continuous collision-free physical motion.

Run from the repository root with the local checkpoint:

```powershell
python software/ai/vision/run_keyboard_rehearsal.py --request 'Type "hi" on the keyboard' --checkpoint software/ai/train/runs/synthetic_pose_photo_v1/pose_model.pt --seed 1000001
```

The [seed-1000001 result](../eval/keyboard_rehearsal_seed_1000001.json)
estimated the keyboard center within 1.22 mm and yaw
within 0.10 degrees of the simulator truth. Both virtual points hit `H` and
`I`. The nominal dense route failed at PARK (waypoint 0,
`IK_NO_CONVERGED_SOLUTION`), so `virtual_text_after_screened_route` is null and zero
physical input events are claimed. An explicit park study at (290, 10) mm
([saved result](../eval/keyboard_rehearsal_seed_1000001_park_study.json))
progressed to the `H` HOVER waypoint but also failed IK. For `"a"` with the
same park study, the first failure was at the `A` TRANSIT waypoint due to the
minimum modeled arm-joint margin. These are route diagnostics, not evidence
that a keyboard was typed on.

The report separates intent, image pose error, virtual key hit, geometry, IK,
and dense route failure. The next physical-data milestone remains fixed-camera
calibration and measured key labels; the training set and key-hit simulator do
not substitute for either.
