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
[v2 proposal](model_motion_proposal_v2.schema.json) and
[v2 batch](model_motion_batch_v2.schema.json) add a bounded scene lease,
independent placement and board-frame evidence, camera/clock/lease identity,
integer epoch-millisecond freshness, capability identity, ordered semantic action
indexes, qualified planar uncertainty, and per-observation confidence. V2
deliberately removes model-owned speed and clearance choices and initially accepts
only `board_mm_xy_plane_v2`. The arm consumer composes producer localization error
with independent placement error, while surface-normal evidence is checked
separately. It remains zero-authority and is additive beside the frozen v1
compatibility contract. The
[model-motion ingress report](model_motion_ingress_v1.schema.json) records
RoCell's deterministic admission of that batch while retaining zero hardware
authority.
The [model-motion sequence snapshot](model_motion_sequence_snapshot_v1.schema.json)
tracks that admitted batch one action at a time. It requires a new observed arm
state for every proposal, forbids lookahead and automatic retry, and advances
only after exact, independently verified completion evidence.
The [durable sequence-journal snapshot](model_motion_sequence_journal_snapshot_v1.schema.json)
records the append-only, hash-chained lifecycle and its conservative restart
disposition. A committed dispatch boundary with no verified result explicitly
forbids replay and requires outcome reconciliation.
The [trajectory execution envelope](trajectory_execution_envelope_v1.schema.json)
is the sealed, controller-independent input to the future sole writer. It binds
the current model action and planner/collision evidence to timed five-joint
waypoints, measured position/velocity/acceleration/jerk limits, settling policy,
deadline, controller session, build, calibration, and configuration epochs. It
contains no wire command or execution authority.
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

The S4 zero-write controller boundary publishes five strict, closed schemas:
the [T=102 encoding profile](zero_write_waveshare_t102_profile_v1.schema.json),
[single-use preview permit](zero_write_waveshare_preview_permit_v1.schema.json),
[wire preview receipt](zero_write_waveshare_preview_receipt_v1.schema.json),
[sole-writer journal](zero_write_sole_writer_journal_v1.schema.json), and
[sole-writer rehearsal report](zero_write_sole_writer_report_v1.schema.json).
They make the model-to-arm handoff reviewable without granting transport or
physical authority. The profile's joint mapping remains a content-addressed
claim only; these schemas and their synthetic golden bytes do not qualify the
mapping against installed firmware or hardware.
The [installed-controller evidence schema](installed_controller_qualification_evidence_v1.schema.json)
and [assessment schema](installed_controller_qualification_report_v1.schema.json)
close that gap at the software boundary: a profile becomes eligible only for
zero-write profile binding when independently reviewed, current physical
evidence matches its controller session, configuration epoch, mapping hash,
protocol-source hash, T=102 fields, T=1051 fields, planner order, and fixed
gripper field. Even a passing assessment grants no transport or execution
authority; evidence collection and physical qualification remain separate.
The [installed-controller surface evidence schema](installed_controller_surface_evidence_v1.schema.json)
and [surface compatibility report](installed_controller_surface_compatibility_report_v1.schema.json)
add a prior fail-closed check that the exact installed app actually exposes the
generic `T=102` command and `T=105`/`T=1051` feedback paths. The check prevents a
finite diagnostic image such as r96 from being mistaken for a production
runtime. A compatible result still grants no transport, execution, or physical
authority.

[Precision observation v2](precision_observation_v2.schema.json) carries explicit
localization abstention or a reference to externally qualified uncertainty.
[Localization qualification v0](localization_qualification_v0.schema.json)
binds an offline synthetic error bound to a checkpoint, domain, target set,
and distinct calibration/evaluation datasets. No qualification is installed.
The producer constructs the existing shared ModelMotionBatch only after
precision and scene checks; scene confidence cannot fill a localization gap.
