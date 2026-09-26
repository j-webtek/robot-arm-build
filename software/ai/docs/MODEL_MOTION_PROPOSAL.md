# Model coordinate proposal integration

`rocell.model_motion_proposal.v1` is the supported handoff from a
coordinate-producing model to RoCell's deterministic motion stack.

The proposal is a real planning input, not prose and not a hidden prompt. It is
also not a serial command. RoCell owns frame conversion, target-map comparison,
calibration, inverse kinematics, trajectory smoothness, collision screening,
execution admission, protocol encoding, and transport writes.

## Contract

```json
{
  "schema": "rocell.model_motion_proposal.v1",
  "proposal_id": "keyboard-h-001",
  "device": "keyboard",
  "target_id": "H",
  "coordinate_frame": "keyboard_local",
  "target_mm": {"x": 131.55, "y": 69.0, "z": 0.0},
  "interaction": "HOVER",
  "approach_clearance_mm": 25.0,
  "speed_class": "SLOW",
  "confidence": 0.98,
  "source": {
    "model_id": "candidate-model-v1",
    "frame_id": "frame-001",
    "image_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
}
```

Allowed coordinate frames are:

- `keyboard_local`: X from keyboard left, Y from keyboard front, Z upward from
  the key surface;
- `phone_screen_local`: X from phone left, Y from the USB/device front, Z normal
  to the screen;
- `board`: the RC03 board frame in millimetres.

Version 1 requires a named target as well as coordinates. This gives the
deterministic boundary two independent facts to compare: what the model believes
the target is and where it believes that target lies. A coordinate outside the
named target's safe rectangle fails closed.

`target_mm.z` identifies the device surface, not the hover height. The requested
clearance is carried separately so a planner can generate approach, hover/contact,
and retract waypoints without confusing surface geometry with motion policy.

The complete JSON Schema is
[`model_motion_proposal_v1.schema.json`](../schemas/model_motion_proposal_v1.schema.json).

## Offline bridge

Run the zero-write bridge from the `software` directory:

```powershell
$env:PYTHONPATH = "src"
python -m rocell.application.model_motion_bridge `
  --workspace .. `
  --proposal ai/examples/model_motion_proposal_keyboard_h.json
```

The output binds the proposal and nominal target-map hashes, converts an approved
device-local coordinate into the nominal board frame, checks confidence and the
named target safe region, and emits board-frame planning waypoints.

Current output deliberately contains:

```json
{
  "controller_commands": [],
  "hardware_commands_generated": 0,
  "physical_authority": false
}
```

That is the next integration seam, not a dead end. Once measured device placement,
board-to-controller correlation, and tool geometry are commissioned, the accepted
board-frame candidate can enter deterministic IK, smooth trajectory generation,
full-route screening, exact Waveshare command encoding, and the single-writer
executor.

Generate the machine-checkable translation trace from the repository root:

```powershell
python software/ai/run_offline.py assure-motion-proposal `
  --proposal software/ai/examples/model_motion_proposal_keyboard_h.json `
  --output motion-assurance.json
```

The trace binds the proposal, target catalog, converted candidate, source frame,
and image identity. The current implementation passes proposal validation,
named-target resolution, and coordinate conversion, then blocks at missing
commissioned physical calibration. IK, route screening, admission, encoding,
and verification remain `not_run`, with zero permits, commands, writes, and
retries.

## Training use

The current nominal profiles provide 46 keyboard and 29 phone targets. They are
appropriate seed labels for model training and offline integration tests. They are
marked `SIMULATION_ONLY_NOMINAL_UNMEASURED` and must not be represented as observed
physical truth.

Recommended model supervision preserves:

- device and named target;
- device-local surface coordinate;
- source image/frame identity;
- coordinate uncertainty or confidence;
- interaction mode and requested clearance;
- exact configuration/profile version used to create the label.

A later sequence contract should contain an ordered array of these target proposals
plus transition intent. It should not be implemented by concatenating raw controller
JSON emitted by a model.

## Ordered AI-to-RoCell handoff

That ordered boundary is now `rocell.model_motion_batch.v1`. The AI side should
emit one `ModelMotionProposal` for every movement-producing semantic action, in
the exact action-plan order, then construct `ModelMotionBatch` from the core
`rocell.models` package. It must not hand-calculate servo targets or concatenate
Waveshare JSON.

The batch binds:

- the exact semantic `ActionPlan.plan_hash`;
- scene-observation, precision-observation, and fusion-decision hashes;
- one model, frame ID, and image hash shared by every proposal;
- the ordered proposal records and a canonical batch hash.

`rocell.application.model_motion_ingress.ingest_model_motion_batch` revalidates
the active repository context, verifies the batch against the supplied semantic
plan, requires independently validated scene/precision/fusion hashes, enforces
exact target order and `CONTACT` interaction for typing/tapping, and runs every
coordinate through deterministic named-target admission. Its accepted output is
still offline and contains no controller command or physical authority.

This is the coordination contract for the AI worker:

```text
grounded request -> ActionPlan
scene + precision observations -> accepted fusion decision
ActionPlan + accepted coordinates -> ModelMotionBatch
ModelMotionBatch + same ActionPlan -> model_motion_ingress
ordered admitted candidates -> one fresh-state calibrated planner gate at a time
```

Phone verification actions do not receive coordinate proposals. After any phone
tap that changes state, orchestration must stop and obtain the required new
observation before a later tap can be planned. Likewise, a multi-key batch does
not permit all controller commands to be prepared against one initial arm state:
each physical action will require fresh achieved-state evidence before its
planner gate and successor action.

Machine-readable schemas are
[`model_motion_batch_v1.schema.json`](../schemas/model_motion_batch_v1.schema.json)
and
[`model_motion_ingress_v1.schema.json`](../schemas/model_motion_ingress_v1.schema.json).

The current `rocell.ai_visual_targets.v1` KeyboardPoseNet output cannot yet be
promoted into this handoff for physical use. It is explicitly synthetic, reports
no calibrated per-target confidence or uncertainty, and has no final-camera
measurement qualification. Research fixtures may exercise batch ingestion, but
the production emitter must abstain until the precision contract carries
validated uncertainty/confidence and the fused sources come from one fresh,
qualified capture.

## Planner-admission gate

The next deterministic boundary is implemented by
`rocell.application.model_motion_planner_gate`. It binds the accepted coordinate
candidate to the frozen build snapshot, simulation bundle, target catalog,
kinematic model, arm-frame contract, configuration-epoch policy, and complete
device calibration graph. Its output is
`rocell.model_motion_planner_gate.v1`.

The current repository correctly reports
`BLOCKED_CALIBRATION_MISSING_OR_STALE`: the physical calibration registry is
empty. A strict decoder now accepts only hash-matched `VALID` artifacts with
exact payload schemas for robot reference, `B_T_Wv`, separate `R_ctrl`
correlation, measured device pose, and `G_T_T`. A valid snapshot now reprojects
the model's device-local target through measured placement, then constructs a
bounded measured-route screening request. IK is intentionally withheld until a
fresh observed starting joint state is supplied. Full-body/tool/cable collision
geometry is still incomplete, so no screened result can authorize execution.
The gate performs no controller encoding or hardware write.

The observed-state boundary is now implemented by
`rocell.application.observed_planner_start_state`. It consumes the exact
single-query T=105 request/receipt pair, rejects buffered/retried/motion-bearing
or stale evidence through the typed receipt contract, requires all six `b/s/e/t/r/g`
feedback fields, and verifies the observed arm identity against the measured
robot reference. It then applies the calibrated projection
`q_model = sign*q_feedback + offset` and supplies the five URDF arm joints to
trajectory screening only until the monotonic freshness deadline. A plain joint
dictionary is no longer accepted as an observed start state. The adapter and
screen remain command-free and carry no physical authority.

Run the zero-write gate from the repository root:

```powershell
$env:PYTHONPATH = "software/src"
python -m rocell.application.model_motion_planner_gate `
  --workspace . `
  --proposal software/ai/examples/model_motion_proposal_keyboard_h.json
```

## Nominal coordinate rehearsal

`simulate-motion-proposal` accepts one keyboard `CONTACT` proposal and runs its
converted board coordinate through the existing static geometry, sampled IK,
and dense route screen. The report binds proposal, candidate, assurance bundle,
static context, target overlay, and geometry hashes. Static source artifacts are
revalidated after the run. No local model or network service is needed to replay
a saved proposal.

This first version evaluates the proposed contact location using the static
scenario route policy. It does not evaluate model-requested clearance, speed,
cadence, phone interactions, or an ordered multi-action sequence. The example
is synthetic and hand-authored; this run measures no model accuracy.

The saved H example passes geometry but fails sampled IK. Dense screening stops
at waypoint 0 (`PARK`) with `IK_NO_CONVERGED_SOLUTION`, before reaching H. This
is a limitation of the nominal start/setup assumptions, not evidence that H is
physically unreachable. The simulation result does not advance the physical
assurance trace past its missing-calibration blocker. Commands, hardware writes,
and observed physical input events remain zero.

Next priority is a bounded study of the nominal park pose, base placement, and
tool offset using existing layout simulation overlays, with every assumption
recorded. After a route passes, expand to proposal clearance/cadence and
multiple targets, then combine camera-condition stress cases. Simulation labels
must retain their synthetic provenance until measured setup data exists.

## Park and layout study result

The four-case H-contact study is saved in
`eval/model_motion_keyboard_h_layout_study_v0.json`. Nominal setup fails at PARK.
Changing park XY to (290, 10) mm reaches HOVER before IK fails (14 waypoints
evaluated). Applying only the existing rank-1 layout also fails at PARK. Combining
that layout and park passes all 32 sampled route waypoints. The layout changes
both base pose and tool length (120 mm); this study does not isolate their
individual effects. Its profile hash and unmeasured transform are recorded in
each applicable report. The original nominal report remains unchanged.

This is an exploratory result for one hand-authored H coordinate. It provides
a candidate setup for the next simulation: broader key coverage and approach
clearance, followed by camera-condition stress. It does not validate installed
geometry, full-arm collisions, physical typing, or language-model accuracy.

## Keyboard coverage result

The fixed candidate layout and park pass sampled geometry, IK, and dense route
screening for all 46 nominal keyboard centers in
`eval/keyboard_route_coverage_v0.json`. Every case records its generated proposal
and source-bound simulation report. The source image hash is a synthetic
placeholder, and confidence 1.0 denotes generator input; neither is vision
evidence. These are independent park-to-key-to-park routes under the same
unmeasured base/tool assumptions. No hardware command or input event occurred.

Next evaluate ordered multi-key transitions and proposal approach clearance,
then perturb visual localization and camera conditions. Passing individual
center routes does not establish direct inter-key motion, cadence, edge contact
accuracy, model interpretation accuracy, or physical typing success.

## Ordered sequence and clearance study

`run_sequence_clearance_study.py` evaluates H-I, H-H, A-Z, and 1-Space-Enter at
12, 25, and 40 mm common hover clearance. All 12 cases pass sampled route
screening under the same candidate layout. Repeated keys remain separate
actions, and movements between keys ascend to the static transit plane.

The sequence simulator accepts one to eight keyboard CONTACT/SLOW proposals.
Each proposal passes the existing coordinate bridge. A repeated key must retain
the same coordinate; mixed clearances and unsupported speed classes are rejected.
The common requested clearance sets hover and retract height. The static policy
still sets the near-surface approach and nominal contact overtravel.

Cadence is an arithmetic hypothesis: 10 mm/s Cartesian travel, 0.1 s contact
dwell, and 0.2 s per vision-correction or verification placeholder. Acceleration,
servo response, keyboard debounce, and observed inputs are not modeled. Planned
contact timestamps do not establish that a blocked route reaches any contact.
No installed controller speed mapping is implied by this SLOW-only study.

The compact `eval/sequence_clearance_study_v0.json` includes ordered proposals,
source bindings, result hashes, contact timestamps, and route outcomes. Calling
`rocell_ai.motion_sequence_simulation.run` regenerates full geometry and dense
route detail. These cases are development probes, not a held-out model benchmark.
Next priority is perturbing target localization and adding camera-condition
rejection cases while preserving these route and sequence checks.

## Localization and archived scene stress

The 60-case development study pairs six archived scene conditions with ten
synthetic H-I probes: nominal, +/-6 mm on each axis, +/-8 mm on each axis, and
confidence 0.5. Five control-scene routes pass sampled screening (nominal and
four 6 mm offsets). Four 8 mm offsets and the low-confidence case stop at the
coordinate bridge. The five adverse archived scene conditions suppress all
50 associated route attempts.

The scene decisions come from the existing Gemma photo-stress report; its
report, observation, and pixel hashes and frame bindings are checked. These
are archived classifications applied as synthetic experimental conditions to
unrelated nominal coordinates. This is not the current-frame vision-fusion
API, fresh inference, or calibrated image grounding. A route pass at 6 mm
does not establish physical key accuracy or an acceptable deployment tolerance.

The saved result is `eval/localization_scene_stress_v0.json`. Each accepted
probe binds the resulting sequence and route hashes; rejected cases record no
route result. All outcomes retain zero hardware authority. Next priority is
a fixed-camera synthetic image evaluation with actual local-model predictions
and independent target truth, retaining freshness and frame-binding checks
when composing scene and precision observations.

## AI precision v2 and shared batch producer

`rocell_ai.precision_observation` wraps the image prediction in
`rocell.ai_precision_observation.v2`. An unqualified prediction explicitly
abstains with `localization_uncalibrated`; it cannot borrow Gemma scene
confidence. The current `run_joint_preview` returns this v2 record alongside
its legacy research preview. Legacy v1 previews and route studies remain
research artifacts and are not batch-admission evidence.

`rocell_ai.batch_emitter.emit` consumes a compiled `ActionPlan`, exact frame
bytes, scene observation, precision v2 record, and evaluation time. It reruns
the existing freshness/image-quality/scene fusion checks, then verifies the
localization qualification and error bounds before constructing RoCell's
`ModelMotionBatch`. It preserves every movement action, including repeated
keys, with unique proposal IDs, CONTACT mode, and exact plan/evidence hashes.
It invokes the shared nominal coordinate bridge before returning a batch.

Qualification records are supplied by trusted application configuration, never
by model output. A record binds checkpoint, domain, catalog, covered targets,
distinct calibration/evaluation dataset hashes, coverage probability, and a
planar error radius in mm. The application must independently select the
matching domain via `expected_domain_id`. The producer requires the whole XY
error bound to fit inside the target rectangle. Proposal confidence comes from
that localization coverage, not scene confidence. Per-target coverage is not
a joint success probability for an entire batch. Hashes protect integrity,
not scientific validity: dataset separation and statistical qualification
must be established before records enter the trusted registry.

This revision supports `SYNTHETIC_OFFLINE_ONLY` qualifications. No trusted
qualification is installed and no measured deployment qualification is claimed.
The test suite uses explicitly fabricated TEST_ONLY records to prove the
producer/decoder/ingress integration; these records are not deployed. The CLI
`run_batch_emission.py` has an empty trust registry and cannot accept a model's
self-supplied qualification. The saved
`eval/current_checkpoint_batch_abstention_v0.json` comes from actual checkpoint
and Gemma inference on development seed 1000001: it abstains despite passing
scene checks. Its capture/evaluation times are synthetic replay times.

Phone plans are rejected by this keyboard-only producer. A later phone
producer must stop at each state-changing action, obtain new image/scene/
precision/fusion evidence, and compile the next segment. It must not pre-emit
a full dialer workflow using one frame. No AI code emits servo angles,
Waveshare wire commands, execution permits, or claimed hardware effects.

RoCell's sequential orchestrator remains responsible for fresh achieved-state
feedback before each successor, calibration, trajectory screening, and later
execution admission. An offline batch is not an execution authorization.
