# Schemas

Version the AI task proposal and adapter result here. A schema must distinguish
`type_text`, `clarify`, and `unsupported`, preserve exact text when supported,
and bind a source observation. The semantic task proposal contains no robot
coordinates or raw controller command. The separate model-motion proposal may
contain device-local or board coordinates but never joints, wire commands, or
transport authority. RoCell's existing `ActionPlan` remains authoritative for
semantic typing actions.

The first implementation work package is in [the roadmap](../docs/ROADMAP.md).
The initial proposal shape is [`task_proposal_v0.schema.json`](task_proposal_v0.schema.json).
The read-only compiler inspection response is
[`plan_result_v0.schema.json`](plan_result_v0.schema.json). An accepted result
contains RoCell's own semantic `ActionPlan`; it is not an execution receipt.
The [synthetic visual target schema](visual_targets_v0.schema.json) is a
separate board-coordinate observation contract. It has no motion authority.
The [synthetic image-model prediction schema](visual_targets_v1.schema.json)
binds pixel and checkpoint hashes to predicted keyboard target coordinates;
its model scores are uncalibrated and it also has no motion authority.
The [scene-observation schema](scene_observation_v0.schema.json) binds a strict
multimodal scene assessment to exact image bytes. It describes visibility and
image quality and cannot contain coordinates or controller commands.
The [shadow-preview schema](shadow_preview_v0.schema.json) binds one request,
image, scene observation, precision observation, and guarded preview into a
replayable offline record with zero hardware writes and no permit.
The [model-motion proposal schema](model_motion_proposal_v1.schema.json) lets a
model propose a named keyboard or phone coordinate in a declared frame. The
proposal still has no transport authority; deterministic code must resolve,
plan, screen, and admit it before any controller command can exist.
The [ordered model-motion batch schema](model_motion_batch_v1.schema.json) binds
one semantic plan to same-frame, same-image proposals in action order. The
[model-motion ingress report](model_motion_ingress_v1.schema.json) records
RoCell's deterministic admission of that batch while retaining zero hardware
authority.
The [translation-assurance schema](translation_assurance_v0.schema.json)
records the ordered stage disposition and proves that no downstream stage can
pass after the first blocker in the current offline path.
The [model-motion assurance bundle](model_motion_assurance_bundle_v0.schema.json)
binds a strict coordinate proposal to its deterministic nominal candidate and
forces every physical stage after missing calibration to remain `not_run`.
The [model-motion planner gate schema](model_motion_planner_gate_v1.schema.json)
binds that candidate to the frozen build, frame contract, configuration epochs,
and calibration graph. It remains zero-write and emits neither IK nor a route
while measured calibration, strict payload decoding, or target reprojection is
unavailable.
The [planner calibration snapshot schema](planner_calibration_snapshot_v1.schema.json)
records the exact hash-matched measured transforms, robot reference, controller
correlation, device placement, and tool/TCP geometry accepted by the strict
decoder. It carries no physical authority.
The [model-motion simulation report](model_motion_simulation_v0.schema.json)
binds a nominal coordinate rehearsal to its proposal and static source hashes.
The Python validator also checks hashes and zero physical authority. Even
`SAMPLES_PASS_NOT_EXECUTABLE` does not permit controller execution.
The [measured target reprojection schema](measured_target_reprojection_v1.schema.json)
validates a model point in the measured device frame, binds it to its named target,
and transforms its surface/clearance points into calibrated board frame `B`. It is
Cartesian planner input only and contains no IK result or controller command.
The [measured trajectory screening schema](measured_trajectory_screening_v1.schema.json)
binds that target to a fresh observed start state, deterministic sampled IK and
joint-continuity evidence, plus the current full-body collision-readiness audit.
Missing start telemetry or incomplete collision geometry remains an explicit blocker.
The [observed planner start-state schema](observed_planner_start_state_v1.schema.json)
binds one authenticated, fresh T=1051 receipt to the measured robot reference.
It requires all six feedback joints, applies the calibrated sign/offset projection,
and exposes a time-limited five-joint IK start state with no commands or authority.
The [installed collision-geometry profile schema](installed_collision_geometry_profile_v1.schema.json)
defines the measured, content-addressed body envelopes, source bindings,
engineering exclusions, and clearance policy required before route screening may
rely on the installed arm rather than diagnostic placeholders.

[Precision observation v2](precision_observation_v2.schema.json) carries explicit
localization abstention or a reference to externally qualified uncertainty.
[Localization qualification v0](localization_qualification_v0.schema.json)
binds an offline synthetic error bound to a checkpoint, domain, target set,
and distinct calibration/evaluation datasets. No qualification is installed.
The producer constructs the existing shared ModelMotionBatch only after
precision and scene checks; scene confidence cannot fill a localization gap.
