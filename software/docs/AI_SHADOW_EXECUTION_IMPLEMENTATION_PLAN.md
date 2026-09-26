# AI-guided motion: shadow execution implementation plan

Status: governing implementation plan, 2026-09-25.

This document supersedes the forward-looking execution sequence in
[CONTROL_TO_TYPING_IMPLEMENTATION_PLAN.md](CONTROL_TO_TYPING_IMPLEMENTATION_PLAN.md).
That document and the diagnostic exports remain evidence; they are not deleted or
reinterpreted.

The AI-specific baseline, multimodal observer strategy, and model evidence remain
owned by
[AI_SYSTEM_BASELINE_AND_IMPLEMENTATION_PLAN.md](../ai/docs/AI_SYSTEM_BASELINE_AND_IMPLEMENTATION_PLAN.md).
That plan describes the perception branches; this document governs their end-to-end
composition with observations, calibration, planning, admission, execution, and
outcome verification.

## 1. Decision and objective

Stop expanding one-off ghost-typing firmware routines. Preserve the verified r96
landmark as the end of that diagnostic lineage and move target selection, planning,
safety admission, execution, and verification into a host-side system with explicit
contracts.

The objective is one reproducible pipeline that can accept a user request and a
fresh observation, determine symbolic targets, create a safe candidate trajectory,
and explain what it would do **without moving the arm**. Only after the shadow
pipeline passes its evidence gates may the same candidate format be admitted to a
bounded physical executor.

The first milestone is therefore not autonomous typing. It is trustworthy shadow
execution:

```text
user request + fresh image + fresh telemetry + active calibration
    -> grounded intent
    -> symbolic targets
    -> board-frame targets
    -> candidate trajectory
    -> safety/admission report
    -> expected observations
    -> immutable shadow record
```

This plan authorizes no hardware movement, torque change, firmware installation, or
settings change by itself.

## 2. Why the project is pivoting now

The diagnostic campaign proved useful lower-level facts:

- commands can be issued and correlated with joint readback;
- bounded moves can be screened, observed, and exported;
- multi-leg non-contact motion is possible in the present workspace;
- command acceptance, measured arrival, and visual success are different facts;
- small residuals and configuration-specific behavior must not be promoted into
  universal corrections.

The latest preserved physical landmark is r96:

- app SHA-256: `e3ccc4cbd5693bab8116ba65b63be88c186c19e6b44f9a59a7a9e9e07ea9d033`;
- boot id: `4390cfab5cd74a16fd5048406c1b5adf`;
- measured positions: `[2100, 2081, 2033, 2609, 2233, 2041, 1900]`;
- goals: `[2107, 2075, 2039, 2600, 2233, 2040, 1897]`;
- export: `wizard-20260925T192321044325Z-585d3a0f6d1c4669ade120dae20dfd47`;
- outcome: clear, no contact, and the r96 motion reservation is exhausted.

At adoption, the repository also contains a fail-closed multimodal preview, a
versioned `scene_observation_v0` contract, deterministic fixtures, fusion checks,
and local Ollama/llama.cpp-compatible observation adapters. They are inputs to WP1
and WP4, not evidence that live camera calibration or motion admission is complete.

Those results do not yet prove that an arbitrary image-space or key-space request
can be transformed into a safe, precise physical action. Continuing to encode each
pose in firmware would produce more isolated demonstrations without closing that
gap. The next value comes from the system that connects observations to decisions.

## 3. Non-negotiable design rules

1. **AI proposes meaning and bounded coordinates, not transport writes.** The AI
   layer may emit a grounded operation, device, text, named target, clarification,
   or coordinate proposal in an approved device-local or board frame. It may not
   emit joint values, PWM values, controller JSON, an execution permit, or write to
   the transport. Deterministic code validates and transforms every coordinate
   before trajectory generation. This preserves the boundary in
   [the AI contract](../ai/docs/CONTRACT.md).
2. **Deterministic code owns geometry and safety.** Target resolution, transforms,
   inverse kinematics, limits, collision checks, route generation, admission, and
   command encoding remain inspectable deterministic components.
3. **One physical writer.** Only the verified execution adapter may write to the
   arm. Perception, AI, planners, dashboards, and tests are read-only clients.
4. **Freshness is data, not an assumption.** Every artifact carries timestamps,
   configuration epochs, hashes, and its parent artifact ids.
5. **Uncertainty stops progression.** `UNCERTAIN` is a terminal outcome for the
   current attempt. It never produces an automatic retry or correction move.
6. **No success by implication.** A sent command, an acknowledgement, a matching
   goal register, a measured joint arrival, and a visually correct outcome are
   recorded separately.
7. **No firmware-per-target workflow.** Firmware remains for device support,
   recovery, and bounded diagnostics. Ordinary targets are host-side data.
8. **Configuration is immutable during an attempt.** Camera, board, base, tool,
   controller, software, and power epochs are bound before planning and checked
   again before execution.
9. **Residual learning is bounded.** Learned residuals may refine an already-safe
   deterministic target within a frozen correction envelope. They may not bypass
   kinematic, collision, workspace, freshness, or confidence gates.

## 4. System ownership and trust boundaries

| Component | Owns | Must not own |
|---|---|---|
| Intent adapter | English-to-structured task proposal and clarification | Joints, protocol commands, permits |
| Observation service | Synchronized camera frame, joint snapshot, health, epochs | Target choice or motion |
| Perception/model service | Device pose, named targets, bounded coordinate proposals, confidence | Joints, permits, physical execution |
| Target resolver | Named key/region to board-frame point and hover/contact semantics | Arm commands |
| Calibration registry | Versioned transforms and held-out validation evidence | Silent online mutation |
| Trajectory planner | IK candidates, full route, timing, modeled clearances | Permission to execute |
| Safety supervisor | Admission or rejection with reason codes | Target invention or retries |
| Execution adapter | Official serial/JSON write and readback correlation | Replanning, AI decisions |
| Outcome verifier | Post-action telemetry/vision comparison and evidence | Inferring success from send/ack |
| Evidence store | Append-only lineage, exports, summaries | Editing historical observations |

The intended composition is:

```text
AI intent proposal
      |
      v
grounding gate -----> clarification/rejection
      |
      v
observation + perception + calibration
      |
      v
deterministic target resolver -> planner -> safety supervisor
                                          |
                                  shadow report only
                                          |
                              [later promotion gate]
                                          |
                            single verified executor
                                          |
                           telemetry + visual verifier
```

## 5. Canonical artifact contracts

All artifacts use canonical JSON serialization, a schema id, an artifact id, UTC
capture/creation times, SHA-256 content hashes, parent artifact ids, and the complete
configuration epoch vector. Schemas reject unknown fields until an explicit schema
revision adds them.

### 5.1 `rocell.observation_bundle.v1`

One synchronized, read-only view of the world:

- camera frame id, image hash, capture time, camera epoch, exposure metadata;
- controller snapshot id, receive time, positions, goals, health/status fields;
- base, board, keyboard, tool, power, arm, controller, and software epochs;
- maximum camera/telemetry skew and measured skew;
- source adapter versions and transport identity;
- freshness result and explicit missing-field list.

The bundle is invalid if its component timestamps, hashes, or epochs cannot be
verified. A photo supplied by a user can enter the offline pipeline, but it is
labelled `USER_SUPPLIED_UNSYNCHRONIZED` and can never receive a live permit.

### 5.2 `rocell.task_intent.v1`

The accepted output of the existing AI proposal and grounding gate:

- operation and device;
- literal text or ordered symbolic targets;
- requested mode such as `HOVER`, `CONTACT`, or `OBSERVE_ONLY`;
- ambiguity/clarification result;
- proposal model/version and grounding evidence;
- explicit prohibition on joints, PWM, protocol commands, and permits. Coordinate
  output uses the separate model-motion proposal contract below.

Reuse the current AI proposal/result contracts where they already meet these
requirements; add an adapter rather than a competing intent language.

### 5.2a `rocell.model_motion_proposal.v1`

The strict internal handoff from the user's coordinate-producing model:

- named keyboard or phone target;
- coordinate in `keyboard_local`, `phone_screen_local`, or `board`;
- hover/contact intent, approach clearance, speed class, and confidence;
- exact model, frame, and image hash provenance;
- no joint values, protocol fields, permit, or transport authority.

The deterministic bridge compares the proposal with the named target's safe region
and converts device-local coordinates into a board-frame planning request. Nominal
maps can support offline training and screening; measured transforms remain required
before physical compilation.

### 5.3 `rocell.scene_targets.v1`

The perception and target-resolution result:

- detected device class and pose hypothesis;
- named landmarks and named targets;
- target centers in the board frame, never controller space;
- confidence, covariance or bounded error estimate, visibility, and source;
- image, observation, layout, and calibration hashes;
- separate fields for measured, model-predicted, and assumed values.

This is the measured-scene successor to
[`visual_targets_v1.schema.json`](../ai/schemas/visual_targets_v1.schema.json), whose
current source is intentionally synthetic-only.

### 5.4 `rocell.calibration_snapshot.v1`

A closed transform chain for one immutable epoch vector:

- camera-to-board transform and calibration residuals;
- board-to-arm-base transform;
- readback-to-controller correlation and sign/unit conventions;
- gripper-to-tool-tip transform, or explicit bare-gripper geometry;
- keyboard layout dimensions and keyboard-to-board transform;
- training/calibration samples separated from held-out validation samples;
- validity envelope and revocation/supersession state.

The snapshot must preserve the frame separation in
[`arm_frame_contract.json`](../config/arm_frame_contract.json). `Wv`, `R_u`,
`R_ctrl`, `G`, `T`, and `B` may not be aliased merely because values look similar.

### 5.5 `rocell.trajectory_candidate.v1`

A planner product, not an authorization:

- starting observation and calibration ids;
- ordered waypoints in named frames;
- selected IK branch and full joint-space samples;
- speed/acceleration envelope;
- modeled arm, tool, cable, board, keyboard, and environment clearances;
- joint-limit, singularity, reachability, and discontinuity margins;
- expected endpoint observations and planner version;
- disposition: `SCREENED`, `REJECTED`, or `INCOMPLETE`.

### 5.6 `rocell.execution_permit.v1`

A short-lived, single-use capability created only by the safety supervisor:

- exact candidate, observation, calibration, executor, and epoch hashes;
- allowed waypoint range and command count;
- absolute expiry and maximum observation age;
- permitted physical mode (`NON_CONTACT` before `CONTACT`);
- no-retry flag and exhausted/revoked state;
- required human/environment confirmations when applicable.

Shadow mode never creates this artifact.

### 5.7 `rocell.execution_receipt.v1`

What the transport actually did:

- permit id and one-writer session id;
- exact transmitted bytes/JSON and timestamps;
- acknowledgements and raw responses;
- pre-, during-, and post-command telemetry snapshots;
- per-waypoint arrival classification;
- transport errors, timeouts, and whether any write was attempted;
- permit exhaustion recorded atomically.

### 5.8 `rocell.outcome_observation.v1`

Independent post-action assessment:

- fresh image and telemetry ids;
- observed target/pose and error bounds;
- contact/non-contact evidence;
- unexpected scene change or obstruction evidence;
- outcome: `OBSERVED_SUCCESS`, `OBSERVED_FAILURE`, or `UNCERTAIN`;
- difference between intended, planned, transmitted, measured, and visually observed
  states.

## 6. State machine

```text
CAPTURED
  -> INTENT_GROUNDED
  -> TARGETS_RESOLVED
  -> PLAN_SCREENED
  -> SHADOW_ACCEPTED | REJECTED | UNCERTAIN

SHADOW_ACCEPTED -- later release gate --> PERMITTED
  -> EXECUTING
  -> OBSERVED_SUCCESS | OBSERVED_FAILURE | UNCERTAIN
```

Every transition is an append-only event. `REJECTED`, `UNCERTAIN`, expired,
revoked, epoch mismatch, stale observation, and exhausted permit have no automatic
outgoing motion transition.

## 7. Work packages and implementation order

### WP0 — Freeze and index the diagnostic lineage

- Mark r96 as the final ghost-routine physical landmark.
- Keep prior firmware sources, binaries, hashes, exports, and analyses immutable.
- Add no r97 merely to encode another keyboard pose.
- Classify firmware paths as `RECOVERY`, `DIAGNOSTIC`, or `LEGACY_EVIDENCE`.
- Make the host pipeline consume historical exports only through read-only adapters.

Exit gate: the project can identify the last installed/observed state without
mistaking it for a fresh runtime observation.

### WP1 — Contracts and a zero-write shadow orchestrator

- Add JSON schemas for the eight artifacts in Section 5.
- Build typed loaders, canonical hashing, validation, and lineage checks.
- Implement one `shadow_execution` application service that joins the existing
  grounded intent adapter, observation input, visual targets, calibration snapshot,
  target resolver, and static trajectory rehearsal.
- Add a hard zero-write invariant: shadow mode cannot import or instantiate a
  writable transport.
- Emit machine-readable JSON plus a concise Markdown report.

Exit gate: a real stored photo, stored telemetry, and text request produce one
replayable shadow record with zero hardware writes.

### WP2 — Fresh observation service

- Add a camera adapter with frame hashes and monotonic/UTC timing.
- Add a serial read-only telemetry adapter using the official Waveshare JSON
  protocol and existing repository transport code.
- Define maximum capture skew and freshness policy in configuration.
- Detect camera movement, board movement, controller restart, transport identity
  change, and incomplete snapshots.
- Preserve user-supplied images as offline evidence without treating them as live.

Exit gate: stale, mismatched, tampered, incomplete, and cross-epoch bundles are
rejected by automated tests.

### WP3 — Calibration registry and commissioning

- Implement immutable calibration snapshots tied to
  [`configuration_epochs.json`](../config/configuration_epochs.json).
- Measure and validate the camera-to-board, board-to-base, controller-correlation,
  and tool transforms separately.
- Use fiducials or another explicit board registration method; photo estimates can
  seed hypotheses but cannot commission a transform.
- Split calibration samples from held-out validation samples before fitting.
- Publish residual distributions, validity envelopes, and revocation rules.
- Require a new epoch whenever the camera, base, board, keyboard, or tool moves.

Exit gate: the complete transform chain closes on held-out points within thresholds
frozen before evaluation, with no frame aliasing or unmeasured tool assumption.

### WP4 — Real-scene perception evaluation

- Capture a versioned real-image dataset across lighting, partial occlusion, board
  locations, keyboard locations, and camera noise.
- Label board corners, keyboard corners, named keys/regions, visibility, and scene
  validity independently of model output.
- Evaluate the existing synthetic model on the frozen real set before retraining.
- Separate detection error, target-resolution error, and calibration error.
- Calibrate confidence and reject out-of-distribution scenes.
- Train or fine-tune only after baseline failure modes are catalogued.

Exit gate: the model meets a pre-registered non-contact accuracy and wrong-target
rate on a held-out real dataset. Contact thresholds remain stricter and separate.

### WP5 — Deterministic target and trajectory layer

- Resolve symbolic keys/regions through a versioned keyboard layout model.
- Transform targets through the commissioned frame chain.
- Reuse the existing IK and dense route-screening code behind stable interfaces.
- Model the full arm, gripper/tool, keyboard, board, workspace exclusions, and
  conservative cable envelope, not only the endpoint.
- Generate lift/traverse/descend or hover routes from policy rather than recorded
  pose snippets.
- Reject discontinuous IK branches, weak margins, and unknown geometry.

Exit gate: every accepted candidate passes deterministic joint, reachability,
continuity, clearance, freshness, and epoch checks across the entire route.

### WP6 — Verified host execution adapter

- Use official Waveshare serial/JSON as the preferred bidirectional path.
- Reuse the repository serial transport and command encoder; do not invent another
  wire protocol.
- Enforce one writer, one permit, one bounded command sequence, and atomic permit
  exhaustion.
- Record requested target, encoded command, sent bytes, acknowledgement, goals, and
  measured positions separately.
- Provide no silent retry, no automatic return, and no implicit torque-off.
- Keep HTTP as an explicitly lower-trust onboarding/fallback path until equivalent
  feedback correlation is demonstrated.

Exit gate: replay and fault-injection tests prove that stale permits, duplicate
writes, disconnects, partial responses, and restarts cannot create an unrecorded or
retried movement.

### WP7 — Independent outcome verification and bounded residuals

- Capture fresh telemetry and imagery after each admitted action.
- Compare intent, target, plan, command, readback, and visual result independently.
- Store residuals with configuration and direction-of-approach context.
- Fit residual models only on commissioned, comparable data.
- Bound any correction by a small declared envelope and re-run the complete planner
  and safety supervisor after applying it.
- Never learn from ambiguous or manually disturbed trials as if they were clean.

Exit gate: the verifier distinguishes success, failure, and uncertainty without
using command acceptance as the success label.

### WP8 — Staged physical promotion

Promotion order:

1. offline replay of historical data;
2. live read-only shadow operation;
3. supervised single non-contact hover in a large-clearance region;
4. supervised multi-hover route with independent verification at each leg;
5. broader keyboard-region coverage;
6. bare-gripper near-surface trials;
7. commissioned tool and contact trials;
8. typed sequences only after contact/release evidence is reliable.

Each stage requires a written evidence review and a configuration-specific release
record. Passing one stage does not authorize a different tool, camera pose, board
pose, firmware, power condition, or environment.

## 8. Evaluation and promotion gates

Numeric thresholds must be frozen in the relevant test protocol before a held-out
set is evaluated. Do not tune a threshold after seeing the result. At minimum:

| Gate | Required evidence |
|---|---|
| Intent | Zero false executable proposals on frozen safety challenges; exact symbolic-target accounting; independently reviewed labels |
| Observation | Hash/epoch/time integrity; declared skew and freshness limits; stale and tampered rejection tests |
| Perception | Frozen real-image holdout; position/yaw error distribution; wrong-target rate; confidence calibration; invalid-scene rejection |
| Calibration | Held-out transform closure; repeatability after recapture; independent frame evidence; explicit tool uncertainty |
| Planning | Full-route joint/IK/clearance checks; collision fixtures; branch-continuity tests; deterministic replay |
| Admission | Exact artifact binding; short expiry; single use; restart and epoch invalidation; no permit in shadow mode |
| Execution | One writer; exact TX/RX evidence; no silent retry; fault injection; permit exhaustion |
| Outcome | Independent post-observation; success/failure/uncertain separation; contact evidence when contact is claimed |

For non-contact keyboard hover, the final geometric acceptance bound must be derived
from measured key spacing, bare-gripper/tool footprint, perception error,
calibration error, kinematic residual, and required clearance. For contact, the
budget must additionally include key-cap boundary, approach angle, compliance,
press depth/force proxy, release, and adjacent-key avoidance. A single average error
is insufficient; tail error and wrong-target events govern promotion.

## 9. Test pyramid

1. **Schema tests:** valid fixtures, missing fields, unknown fields, hash tampering,
   lineage mismatch, epoch mismatch, and time-boundary cases.
2. **Unit/property tests:** transforms, units, sign conventions, interpolation,
   keyboard target resolution, permit consumption, and no-retry invariants.
3. **Replay tests:** historical diagnostic exports produce deterministic analyses
   and never open a writable transport.
4. **Synthetic tests:** broad geometry and perception variation for coverage, never
   used alone to claim real-world readiness.
5. **Real offline tests:** frozen labelled photographs and captured telemetry with
   no device connection.
6. **Live shadow tests:** fresh camera and telemetry, full planning, zero writes.
7. **Supervised physical tests:** one promoted permit at a time, independent outcome
   capture, and explicit stop between stages.

CI must run levels 1–5 without hardware. Hardware tests remain opt-in, identify the
connected device, and refuse to run from a generic test command.

## 10. Repository structure and reuse

Prefer adapting existing modules to creating parallel stacks. The intended shape is:

```text
software/
  ai/
    schemas/                     # intent and scene/perception contracts
    docs/                        # AI and vision evaluation evidence
  schemas/                       # cross-system observation/plan/permit/receipt contracts
  config/                        # epoch manifests and policy, not mutable calibration blobs
  src/rocell/
    application/
      observation_bundle.py
      shadow_execution.py
      target_resolution.py
      execution_admission.py
      static_task_rehearsal.py   # existing planner/rehearsal seam
    calibration/
      registry.py
      transforms.py
    perception/
      keyboard_pose.py
    planning/
      trajectory_candidate.py
    arm/
      serial_transport.py        # existing official-protocol path
      verified_executor.py
    verification/
      outcome_observation.py
  tests/
    fixtures/shadow/
```

Exact filenames may change after the source audit, but responsibilities and artifact
contracts must not collapse together. In particular, do not place an execution
write inside an AI, perception, or calibration module.

Reuse targets already present in the repository include:

- the grounded intent proposal/result adapters and safety challenge sets;
- `scene_observation_v0`, multimodal preview/fusion, local vision adapters, the
  visual target schema, and the synthetic vision campaign as starting points;
- `static_task_rehearsal.py`, keyboard layouts, IK, and dense route screening;
- serial transport and official JSON command encoding;
- configuration epochs and the arm frame contract;
- diagnostic export, hashing, and review patterns.

## 11. Evidence storage and experiment discipline

Every run receives a unique id and append-only directory containing:

- request and grounded intent;
- raw observation manifest and immutable media hashes;
- perception output and model identity;
- calibration snapshot identity;
- target-resolution and trajectory artifacts;
- safety report and, in shadow mode, proof that no executor was loaded;
- execution permit/receipt when physical execution is eventually enabled;
- post-action observations and final classification;
- human annotations stored separately from sensor facts.

Requested, predicted, planned, transmitted, measured, and visually observed values
must remain separate columns/objects. Reports may join them for readability but may
not overwrite the source records.

## 12. First implementation slice

Implement the following before any additional general-purpose arm movement:

- [ ] Add the cross-system schemas and representative valid/invalid fixtures.
- [ ] Add canonical JSON hashing and parent-lineage validation.
- [ ] Implement `observation_bundle` for stored image + stored telemetry inputs.
- [ ] Adapt the current grounded-intent result into `task_intent`.
- [x] Add the strict model coordinate proposal and nominal-map bridge. The bridge
      emits board-frame planning candidates only and produces zero controller writes.
- [x] Bind model-coordinate candidates to the frozen build, frame contract,
      configuration-epoch policy, and complete calibration graph through a
      zero-write planner-admission gate. The empty physical registry fails closed
      before IK or route screening.
- [x] Add the strict measured calibration snapshot decoder for robot reference,
      `B_T_Wv`, separate `R_ctrl` correlation, device placement, and `G_T_T`.
      Nominal/non-valid artifacts, hash mismatches, wrong transform directions,
      unknown fields, and invalid limits fail closed.
- [x] Reproject validated model targets through measured `B_T_keyboard` or
      `B_T_phone_screen`. Named-target containment is checked in device coordinates,
      clearance follows measured device-local +Z, and the hash-bound output advances
      only to deterministic IK and full-route screening with zero hardware writes.
- [ ] Adapt current visual targets and keyboard layout into `scene_targets`.
- [ ] Wrap `static_task_rehearsal` as a `trajectory_candidate` producer.
- [ ] Implement the safety report with explicit reject reason codes.
- [ ] Implement `shadow_execution` with a structural zero-write guarantee.
- [ ] Generate one replayable report using a real user-supplied keyboard photo and
      stored controller data, clearly labelled unsynchronized/offline.
- [ ] Add tests for stale data, wrong epochs, altered hashes, missing calibration,
      ambiguous intent, low visual confidence, unreachable targets, and collision.
- [ ] Publish the first shadow milestone review before starting live camera work.

The first slice is complete only when one command can reproduce the shadow report
from immutable inputs, CI proves no writable transport is reachable, and every
accept/reject decision links to its source artifacts.

## 13. Suggested implementation increments

Keep commits narrow and reviewable:

1. schemas, fixtures, and validators;
2. observation and artifact-lineage services;
3. intent and scene-target adapters;
4. planner adapter and safety reason codes;
5. shadow runner and Markdown/JSON reporting;
6. offline real-photo replay and milestone report;
7. live read-only observation service;
8. calibration registry and commissioning tools;
9. real-scene evaluation harness;
10. executor only after shadow/calibration/perception gates pass.

Each increment updates this plan's checklist or links its evidence. A failed result
is retained and analysed; it is not erased by the next build.

## 14. Definition of done

### Shadow milestone

- A user request, real image, stored/read-only telemetry, and explicit calibration
  hypothesis produce deterministic symbolic targets and a screened route.
- The report exposes all assumptions, uncertainties, margins, hashes, and epochs.
- Re-running identical inputs produces identical semantic artifacts.
- Invalid or stale inputs fail closed with machine-readable reasons.
- The process cannot write to the arm by construction.

### First physical non-contact milestone

- A commissioned camera/board/base transform and bare-gripper geometry are active.
- Real held-out perception and calibration gates pass.
- A fresh live shadow result is promoted to one short-lived single-use permit.
- The official serial/JSON adapter records exact command and readback evidence.
- Independent telemetry and vision classify the outcome.
- No retry or follow-on movement occurs from failure or uncertainty.

### Typing-readiness milestone

- Multiple keyboard regions and approach directions pass held-out non-contact tests.
- Contact geometry and tool transform are commissioned separately.
- Press and release are independently observable and adjacent-key avoidance is
  demonstrated.
- Sequence planning maintains safety and accuracy across transitions, not just
  isolated keys.
- The AI remains outside the motor-command and permit trust boundary.

## 15. Open decisions to resolve with evidence

- fixed fiducial design and placement for board registration;
- camera mounting and recapture policy;
- bare-gripper versus stylus/tool geometry for the first contact campaign;
- numeric freshness, skew, calibration, perception, and clearance thresholds;
- collision representation for cables and nearby movable objects;
- whether residual correction is necessary after deterministic calibration;
- the minimum real-image dataset size needed to bound tail risk credibly.

These decisions are not reasons to delay WP1. The shadow contracts must represent an
unknown or uncommissioned value explicitly so later measurements can replace
hypotheses without changing the architecture.
