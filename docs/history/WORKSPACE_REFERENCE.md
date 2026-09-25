# Historical workspace reference

Preserved from the root README on 2026-09-25. This document collects earlier
software, simulation, camera, and hardware-package checkpoints. Statements such
as "current," "next," and "not released" below describe those checkpoints;
they are not the latest project status or instructions to run a live test.

Start with [project status](../../PROJECT_STATUS.md) for the latest summary or
use the [documentation guide](../README.md) to find a specific topic.
Commands below assume the repository root as the working directory. Paths in
the RC03 package map are relative to `active-project/RoCell_v0_3/`.

---

# Robot Arm Build Workspace

## Start here: shared development baseline

See [PROJECT_STATUS.md](../../PROJECT_STATUS.md) for the current hardware/software
checkpoint and [CONTRIBUTING.md](../../CONTRIBUTING.md) for cloning, binary files, progress
tracking, and sharing diagnostic evidence. The sections below include historical
pre-hardware instructions; they are not the current live-test authorization.

This private repository tracks source, plans, tests, and hardware designs.
Credentials, raw device backups, local firmware toolchains, and raw run exports
remain outside Git. It is not a complete backup of the laboratory workstation.

This workspace is organized around one active release and one frozen baseline:

- `active-project/RoCell_v0_3/` — active printer-only integrated package for the QIDI Plus4 (`RC03-INT-R1`).
- `active-project/RoCell_v0_2/` — frozen prior release retained for comparison and recovery; do not mix its parts with RC03.
- `archives/` — untouched source archives and legacy material.

## Robot typing software roadmap

The [six-step pre-arm-calibration execution plan](../../software/docs/PRE_ARM_CALIBRATION_EXECUTION_PLAN.md)
is the current near-term software preparation checklist. It pairs the agreed
priorities with implementation tickets, tests, dependencies and separate
physical-calibration readiness gates; the governing roadmap below is unchanged.

### Local wizard workbench

Run `.\start-rocell-wizard.ps1` for the new local rehearsal/diagnostic UI, or
add `-Ui terminal` for the same actions without a browser. It joins baseline
tests, camera/arm rehearsals, nominal task planning and verified exports under
`software/runs/wizard-exports/`. Launching opens no hardware. Physical camera
capture, arm connection, power, motion and contact remain held pending the
remaining reviewed integration and received-hardware qualification. See the
[workbench guide](../../software/docs/WIZARD_WORKBENCH.md) for exact scope and usage.

Use [`ROBOT_TYPING_SYSTEM_MASTER_PLAN.md`](../../ROBOT_TYPING_SYSTEM_MASTER_PLAN.md) as the governing roadmap and [`BUILD_ALIGNMENT_FREEZE.md`](../../BUILD_ALIGNMENT_FREEZE.md) as the RC03 crosswalk. The machine-readable freeze is [`software/config/system_manifest.json`](../../software/config/system_manifest.json), and the pinned arm/model contract is [`software/models/roarm_m3/README.md`](../../software/models/roarm_m3/README.md); verify alignment with `python software/tools/validate_build_alignment.py`. These files live outside the checksum-controlled RC03 hardware package and consume its geometry/evidence read-only.

For the current software data flow, restart rules, zero-authority boundaries,
test commands, and the exact sequence for replacing synthetic providers after
delivery, use the [pre-hardware runtime foundations guide](../../software/docs/PREHARDWARE_RUNTIME_FOUNDATIONS.md).

For arrival-day setup and connection evidence, use the controlled
[physical onboarding automation runbook](../../software/docs/PHYSICAL_ONBOARDING_AUTOMATION.md).
The detailed build sequence for the guided terminal/browser commissioning
experience is the
[physical onboarding wizard implementation plan](../../software/docs/PHYSICAL_ONBOARDING_WIZARD_IMPLEMENTATION_PLAN.md).
For the concrete camera preview/control, USB serial connection, supervised
startup, and early interface delivery sequence, use the
[camera and arm connection integration plan](../../software/docs/CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md).
Developers implementing that plan should start with the paired
[developer playbook](../../software/docs/CAMERA_ARM_DEVELOPER_PLAYBOOK.md), which maps
existing code to implementation tickets, test lanes, and handoff criteria.
This researched implementation proposal adds no hardware authority and keeps
the existing stage, source-alignment, and qualification gates intact.
The wizard's reviewed v2 Phase-0 foundation is implemented as a strict, source-bound,
zero-authority contract set covering stage/effect ownership, progressive
intake, configuration epochs, hazards, workcell interfaces, and target
accuracy. The M1 application slice now adds qualified Windows/NTFS
publication, ordered leases, cell-global attempt/quarantine ledgers, blank v2
session creation, and evidence-only no-replay recovery behind a facade with no
hardware-effect method. The effect-capable coordinator, bounded workers and
permits, energization envelopes, physical providers, calibration campaigns,
reviewed wizard flow, and independent rollback anchor remain blocked
milestones. See the
[M1 qualified zero-hardware runtime guide](../../software/docs/M1_ZERO_HARDWARE_RUNTIME.md).
The roadmap preserves the current zero-authority controller and separates
camera diagnostics, one-shot arm feedback, noncontact motion qualification,
and later keyboard/phone contact releases.
The supported Windows entry point is:

```powershell
.\start-rocell-onboarding.ps1 -CellId CELL-A
```

It creates or verifies the workspace `.venv`, validates the runtime-inactive
onboarding foundation, runs hardware-free host and synthetic connection checks,
and creates a source-bound diagnostic session with only the first two zero-I/O
stages prepared. It does not inventory or open a camera or serial port, apply
robot power, initialize or move the arm, or grant calibration/contact authority.
The lower-level `setup-rocell.ps1`,
`host-doctor`, `rehearse-physical-connections`, and `physical-onboard` commands
are documented in that runbook for controlled troubleshooting and staged use.

The separate M1 v2 storage sequence is explicit and remains zero-hardware:

```powershell
.\rocell.ps1 physical-onboard init-v2-storage --cell-id CELL-A --json
.\rocell.ps1 physical-onboard verify-v2-runtime --cell-id CELL-A --json
.\rocell.ps1 physical-onboard new-v2 --cell-id CELL-A --session-id arrival-v2-local-001 --json
.\rocell.ps1 physical-onboard verify-v2-runtime --cell-id CELL-A --session-id arrival-v2-local-001 --json
```

These are the supported M1 commands. Never substitute direct module calls or
edit storage to bypass a hold.

Active Freeze 011 is aligned to build `2026-09-01_CELL-A`; Freeze 009 remains immutable archived provenance. On 2026-09-05 the builder selected a **rigid static overhead eye-to-hand camera as the Phase 1 primary** and subsequently confirmed purchasing the Arducam USB 3.0 20 MP package sold with a 60-degree diagonal, nominal 16 mm C-mount lens and metal case. The design maps that purchase to the Arducam B0477/IMX283 catalog configuration with state `PURCHASED_PENDING_RECEIPT_INSPECTION`; see the [strict purchased-camera profile](../../software/config/camera_profiles/arducam_b0477_imx283_16mm.json), [static overhead architecture plan](../../STATIC_OVERHEAD_CAMERA_ARCHITECTURE_PLAN.md), its [machine-readable change plan](../../software/config/camera_architecture_plan.json), and the [dimensioned static-camera hardware addendum](../../hardware/static_overhead_camera/README.md). The additive hardware baseline uses a bench-anchored front portal, a nominal 1000 mm entrance-pupil height, and a provisional 920 mm overhead-hardware floor. Its strict source-locked contract records the intended catalog configuration and supports simulation, but does not verify the received unit or grant cut, fabrication, installation, motion, or contact authority. Freeze 011 deliberately retains the legacy arm-camera fields under `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`; the additive B0477 path is the selected Phase 1 simulation direction, not a silently promoted physical configuration. The earlier upper-arm IMX335-B candidate and moving-camera path are demoted to optional Phase 2 research, and the old 700 mm mast is not suitable for the static primary. Camera-guided motion, robot power, and contact remain blocked until a superseding freeze and physical qualification.

The additive B0477 software stack now rehearses the provider-neutral UVC
inventory boundary with a deterministic fake provider, validates a sealed
32-view synthetic ChArUco intrinsics artifact (24 training / 8 held out), and
cross-checks profile, support, commissioning, UVC identity/settings hashes,
intrinsics, and the normal/tag-loss pixel pair as one application-level
contract. The recommended `rehearse-b0477-stack --require-pass` check currently
reports `SYNTHETIC_B0477_STACK_COHERENT` with 10/10 gates. It requests no camera
frames, emits no arm or contact commands, and grants no hardware-presence,
live-capture, calibration, extrinsic, motion, or contact authority. Its fixtures,
thresholds, and numeric solution are synthetic test data—not future physical
acceptance criteria.

The [first-power-on onboarding guide](../../software/docs/FIRST_POWER_ON_ONBOARDING.md)
joins those camera gates to arm identity, pre-power safety, the required record
schema for observing possible automatic middle-position startup motion,
feedback-only connection,
calibration dependencies, and noncontact handoff in one 15-stage zero-hardware
rehearsal. It source-binds implementation and transitive controlled inputs,
replays checkpoint prefixes exactly, rejects stale or rewrapped synthetic camera
frames using sequence plus raw-JPEG identity, and runs bounded keyboard/phone
virtual trajectory, pixel, outcome, park, and stall-cleanup paths while preserving
the incomplete physical-collision hold. A nominal run ends at
`SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED`; it does not
change active Freeze 011 or confer robot-power, motion, calibration, or contact authority.

That complete fake workflow is complemented by a persistent, physical-arrival
controller under `physical-onboard`. Its append-only, source-bound journal can
prepare the two zero-I/O contract stages, place later stages into
`WAITING_OPERATOR`, retain content-addressed evidence, validate the controlled
55-row intake, perform explicitly requested metadata-only camera/serial
inventory, and verify session integrity. Strict typed receipt foundations exist
for B0477 receipt inspection, power-off safety review, one externally controlled
first-power observation, and a bound operator decision. They can derive only
`DIAGNOSTIC_READY`, `HOLD`, or `SIDE_EFFECT_UNCERTAIN`; they are not yet public
CLI stage assessors and can never grant power, motion, contact, build-promotion,
or session-mutation authority.

Additional pre-hardware foundations now rehearse the future provider sequence
and failure boundaries without creating a live path. A separate ten-stage,
17-boundary
`EXPLICIT_FAKE` onboarding API covers camera receipt, persistent selection,
exact B0477 mode/manual-control readback, frame flush/freshness, reconnect,
retained-install 24/8 calibration split plus mount/lighting/focus/aperture/cable
witnesses, arm identity
while off, and a hash-linked safety → power-event → synthetic controller
session → empty-input-buffer → exact T=105/T=1051 chain with unconditional
cleanup; it exposes no T=104 or generic write method. Its logical time/nonces
are deliberately untrusted and have no physical evidentiary value.
The B0477 raster can also be converted into exact YUY2/RGB8 sensor buffers and
stored in a strict manifest-last v2 package with perception-time freshness and
replay-policy checks. The pixel schema fixes colorimetry, range, chroma siting,
and row origin, while the B0477 wrapper requires an exact source-bound replay.
A hash-chained, sync-attempted per-action journal latches the first
possible-contact boundary so lost/truncated suffixes fail closed and cannot
authorize a duplicate keypress or tap. An ordered authorization-v2 cursor binds
the exact controller/session, build, registry-resolved 12-artifact device
closure, trajectory/collision report, device state, current interlock samples,
operator nonce, plan, action occurrences, and command sequence. The multi-action
kernel consumes a sealed receipt before each virtual hover, approach, contact,
retract, and final park, and restart requires authorization for only the exact
safe remaining suffix. All of these outputs remain simulation-only and
zero-authority; same-process Python seals, unkeyed local hashes, caller-time
inputs, and the current unqualified Windows directory-flush path are not
physical security or power-loss-durability boundaries.

The separate `rehearse-physical-connections --require-expected` command now
exercises the exact ten-step host/B0477/RoArm connection lifecycle with
constructor-fixed incapable providers: dependency receipt, persistent B0477
discovery, open, exact native-mode/manual exposure-gain-white-balance setup,
flush, one fresh retained frame, close/reopen verification, final close,
unpowered arm identity, and exactly one synthetic T=105/T=1051 exchange. Its
named fault cases prove fail-stop and no-retry behavior. It never enumerates or
opens physical hardware and exposes no T=104, torque, motion, or contact path.

The additive static-B0477 route-collision foundation inventories 26 required
robot, tool, device, board, portal, camera, lighting, fixed-USB, and arm-harness
bodies against nine design-source hashes. It evaluates every one of the 75
nominal targets at park, transit, hover, approach, contact, retract, and final
park, plus a required midpoint sample on each adjacent transition. The arm
harness is supplied for every pose, global collision exclusions are forbidden,
and only the exact tool-tip/designated-target overlap is tolerated during that
target's CONTACT phase. This is conservative synthetic screening only: it is
now bound into the additive mission V2 path, but only through a deliberately
isolated software-fixture geometry. The fixture explicitly reports
`physical_clearance_established: false`; it cannot qualify measured geometry or
release physical motion/contact.

The additive integrated V2 rehearsal closes the former zero-hardware assembly
gap without changing the legacy session or V1 runtime-port contracts. It keeps
semantic, physical-contact, route-waypoint, and authorization-command ordinals
separate; revalidates the accepted trajectory from current source bytes and
stored joint solutions; maps every waypoint after the known initial park to a
strict non-wire controller-emulator target; and independently reconstructs the
dense command/contact schedule and endpoint/exact-joint-midpoint collision
bindings. A single-use stateful B0477 replay port yields only the exact next
synthetic observation after the matching final HOVER reports its bound settled
pose. Phone-state observations are chronological prerequisites: later motion,
camera, contact, mission-tail, and fault-frontier evidence is rejected if a
required earlier state check is missing or an intervening contact is unfinished.
The runner then executes authorization-v2, crash-conservative per-contact
journals, geometry-resolved virtual contact, independent virtual outcome
observation, retraction, and final park as one flow. Full authorization and T104
trace receipts, camera/contact receipts, and journal events are serialized and
deterministically replay-checked. Controller faults bind their exact failed T104
trace. A camera-fault schedule is sealed into the assembly and acts as a global
execution boundary. Capture-area failures use one honest settled-HOVER
observation-boundary cause; a typed B0477 failure receipt is retained only as
explicitly unauthenticated diagnostic detail. Free-form fault text is diagnostic
only. The keyboard
`test` acceptance route is 48 waypoints, 47 commands, and four simulated
contacts. Android `test.` is 61 waypoints, 60 commands, and five simulated
contacts; its state check creates no contact, route command, authorization entry,
or journal. V2 is deliberately bounded to at most eight physical targets per
mission. Nothing in V2 can encode or transmit T=104, and its calibration,
camera, collision, controller-frame, and interlock evidence remains synthetic
and zero-authority.

Active Freeze 011 is the latest in the append-only evidence chain.
Freeze 005 remains the explicitly historical 14-source hardware-alignment and
park/reach/simulation provenance baseline; the later evidence freezes do not
rewrite or relabel those study results. Freeze 005 → 006 was the seven-source
Job 00A lifecycle transition that recorded `PRINTED` and accepted the
keyboard-corner coupon at 0.0 mm compensation. Freeze 006 → 007 was a
five-source traceability synchronization for the actual M4 screw/washer
observations; it left the tray gate `NOT_TESTED` and the counts at 9/71/4.
Freeze 007 → 008 is the seven-source operator-waived prototype functional-fit
transition. It accepts only `tray_clearance_holes_coupon_pass`: the M4 screw's
4.0 mm major diameter is a nominal designation assumption rather than caliper
metrology, the actual screw passed at 4.4 mm with no smaller candidate passing,
and the actual washer fit all candidates with the photographed/current 9.2 mm
recess retained for assembly margin. `python software/tools/validate_build_alignment.py`
reports `ALIGNED_CAMERA_HOLD_CONTACT_BLOCKED`; the waiver does not release any
robot power, motion, or contact. Freeze 008 → 009 is the seven-source transition
that accepts the keyboard-station registration coupon at the operator-confirmed
6.2 mm round/slot selection and advances Job 00A to `POSTPRINT_PASS`; it does
not release downstream printing or the robot. Freeze 009 → 010 is the
14-source reconciliation that records the static-camera alignment hold,
preserves the accepted Job 00A/00B fits, records two Job 00B failures, and
regenerates the Job 03C1 production-equivalent rail. Freeze 010 → 011 is a
four-source workflow correction that removes Job 03C2's self-dependency without
changing geometry, gate counts, or physical authority. Future transitions
use the reviewed-plan workflow in [`BUILD_ALIGNMENT_FREEZE.md`](../../BUILD_ALIGNMENT_FREEZE.md)
and retain prior aliases plus an append-only record under
[`software/freezes/`](../../software/freezes/README.md).

The current controlled state is 20 jobs selected (5 `READY`, 15 `WAITING`) and 4 `NOT_SELECTED`, with 15 measurement gates `PASS`, 63 `NOT_TESTED`, 4 `NA`, and 2 explicit `FAIL`. Job 00A is separately tracked as `POSTPRINT_PASS`. `READY` releases only the named print jobs; physical system release remains `UNRELEASED`, `safe_to_power_robot` is `false`, and contact is disabled.

The simulation-first runtime under [`software/`](../../software/README.md) verifies the frozen build, compiles semantic keyboard/phone actions, and provides an exact-byte-bounded projection of the pinned official Waveshare kinematic model, typed transforms and FK, a separately framed firmware/controller FK and T=104 easing emulator, a nominal RC03 collision scene, a real-JPEG [synthetic fixed-overview pixel-vision and planar-pose pipeline](../../software/docs/PIXEL_VISION_SIMULATION.md), an achieved-joint-dependent [arm-mounted-camera correction simulation](../../software/docs/ARM_CAMERA_CORRECTION_SIMULATION.md), a locked aggregate [prehardware software qualification](../../software/docs/PREHARDWARE_QUALIFICATION.md), nominal keyboard/phone target maps, deterministic tool-tip paths, numerical IK, a bounded [reach-layout diagnostic](../../software/docs/REACH_LAYOUT_STUDY.md), a geometry-derived [park-pose optimizer](../../software/docs/PARK_OPTIMIZATION.md), staged broader [layout sensitivity and all-75-target mission coverage](../../software/docs/PREHARDWARE_MISSION_COVERAGE.md), a source-bound [placemat geometry sensitivity simulation](../../software/docs/PLACEMAT_GEOMETRY_SENSITIVITY.md), a fail-closed [full-body collision-geometry foundation](../../software/docs/COLLISION_FOUNDATION.md), a schema-v2 [discrete waypoint diagnostic](../../software/docs/TRAJECTORY_SIMULATION.md), and an end-to-end [virtual commissioning and replay workflow](../../software/docs/VIRTUAL_COMMISSIONING.md). The fixed-overview topology is now the migration target for the production-aligned static primary. The eye-on-arm code and calibration tools remain zero-authority optional-secondary regressions. No live-motion command is exposed and no simulation result can satisfy a physical gate.

The placemat sensitivity command consumes the current Freeze-011 RC03 layout,
all 46 keyboard and 29 phone targets, and the repaired static-support/B0477
source bindings. Its 59-case default study currently observes no sampled gap
for the keyboard targets and a sampled gap for 27 phone targets; the zero-bound
control keeps all 75 nominal centres inside their regions. Those assumed bounds
are diagnostic inputs, not measured tolerances or a physical pass/fail result.

```powershell
# Controlled arrival preparation. This remains zero-I/O/zero-authority.
.\setup-rocell.ps1 -Profile hardware
.\rocell.ps1 host-doctor --profile hardware --require-pass --json
.\rocell.ps1 rehearse-physical-connections --require-expected --json
# Or create a diagnostic session through the combined safe starter:
.\start-rocell-onboarding.ps1 -CellId CELL-A

$env:PYTHONPATH = (Resolve-Path software/src)
python software/tools/validate_static_camera_support.py --json
python -m rocell --workspace . rehearse-b0477-uvc-inventory --require-pass --json
python -m rocell --workspace . rehearse-b0477-intrinsics --json
# Recommended complete stack gate; includes normal and tag-loss pixel runs.
python -m rocell --workspace . rehearse-b0477-stack --require-pass --json
# Faster core-only loop; does not replace the complete milestone gate.
python -m rocell --workspace . rehearse-b0477-stack --skip-pixel-vision --require-pass --json
# Rehearse the complete camera-first, 15-stage connection/calibration sequence.
python -m rocell --workspace . rehearse-first-power-on --scenario nominal --require-expected --json
python -m rocell status --json
python -m rocell bootstrap-sim --json
python -m rocell qualify-prehardware --profile quick --require-pass --json
# Standard adds all deterministic faults and a fresh 75-route screen.
python -m rocell qualify-prehardware --profile standard --require-pass --json
python -m rocell qualify-prehardware --profile quick --record --require-pass --json
python -m rocell replay-prehardware-qualification --manifest software/runs/qualification-<report-prefix>/manifest.json --require-identical --json
python -m rocell doctor --mode sim --json
python -m rocell workcell --json
# Default assumed bounds intentionally expose phone-target sensitivity gaps.
python -m rocell stress-placemat-geometry --json
# Zero-bound control: all 75 nominal target centres must remain in-region.
python -m rocell stress-placemat-geometry --zero-bounds --require-no-gaps --json
python -m rocell plan --device keyboard --text "test" --json
python -m rocell dry-run --device phone --text "test" --json
python -m rocell simulate --device keyboard --text "test" --json
python -m rocell optimize-layout --json
python -m rocell optimize-park --json
python -m rocell study-layout-hypotheses --json
python -m rocell screen-mission-routes --json
python -m rocell screen-mission-routes --from-layout-study-rank 1 --json
python -m rocell stress-adaptive-session --seed 20260903 --generated-cases 8 --require-pass --json
python -m rocell screen-adaptive-mission-routes --require-all --json
python -m rocell collision-status --json
python -m rocell simulate-trajectory --device keyboard --text "a" --use-optimized-park --json
python -m rocell simulate-session --device keyboard --text "test" --require-pass --json
python -m rocell simulate-session --device phone --text "test." --require-pass --json
# Use a new, nonexistent journal directory for each initial V2 run.
python -m rocell --workspace . simulate-integrated-v2 --device keyboard --text "test" --journal-root software\runs\integrated-v2-keyboard-local-001 --require-pass --json
python -m rocell --workspace . simulate-integrated-v2 --device phone --text "test." --journal-root software\runs\integrated-v2-phone-local-001 --require-pass --json
# Prove a stale B0477 frame stops at the settled final hover, before approach.
python -m rocell --workspace . simulate-integrated-v2 --device keyboard --text "test" --journal-root software\runs\integrated-v2-camera-fault-local-001 --camera-fault-kind stale-frame --camera-fault-contact-ordinal 0 --require-pass --json
python -m rocell simulate-adaptive-session --device keyboard --text "a" --truth-offset-x-mm 12 --require-pass --json
python -m rocell simulate-adaptive-session --device phone --text "a" --truth-offset-x-mm 8 --require-pass --json
```

The integrated V2 command persists one crash-conservative journal per physical contact.
Do not reuse a journal root for another initial run. `--open-existing` reopens
the exact assembly-bound set, but execution refuses automatic retry after any
journal advances beyond `INTENT_COMMITTED`. These journals make the contact
boundary and outcome uncertainty durable. They do not yet persist a
mission-global dispatch high-water mark for every transit/HOVER command; an
abrupt process loss after a non-contact command is therefore an explicit
physical-adapter blocker, even though the current in-memory emulator cannot
move hardware. Two deliberately tested internal-integrity cases can terminalize
all journals and then raise without returning a structured report: failure while
wrapping a controller trace after the emulator advanced, and failure while
wrapping contact evidence after the virtual outcome was applied. Reopening is
still refused. A physical executor needs a mission-global write-ahead dispatch
ledger and lower-level partial-effect receipts before either boundary can be
connected to hardware.

`simulate` performs nominal scene/path/vision checks and reports sampled IK feasibility gaps. `optimize-park` found a board-frame overlay at `(290, 10, 70) mm`, accepted pointwise for both frozen-baseline 100 mm tools with `0.2704734350` worst normalized arm margin and 10 mm modeled planar point clearance. On that explicitly historical Freeze-005 layout, retained unchanged as simulation provenance under active Freeze 011, complete independent mission screening accepts only 38/75 routes: 20/46 keyboard and 18/29 phone. The one-character diagnostic is consistent with that rejection: keyboard `"a"` passes 24/24 discrete waypoints, while phone `"a"` fails at `APPROACH` because `0.000657824 < 0.01`.

The separate staged sensitivity study evaluated 243 coarse and 34 refinement hypotheses, found 49 regression passes, fully screened the ranked top eight against all 46 keyboard plus 29 phone contacts, and marked six as eligible for full-route screening. Its rank-1 software overlay, `reach-944d7463f4c67905`, uses rear clamp X 385 mm, rear-edge-to-axis Y 75 mm, yaw -105 degrees, base Z 70.1 mm, zero clamp-to-axis X offset, and 120/100 mm keyboard/phone virtual tools. Reusing the `(290, 10, 70) mm` park probe, that overlay accepts 75/75 independent park-to-target-to-park route diagnostics. These are unmeasured sensitivity values—not a mechanical allowance, installed transform, fabrication change, arbitrary text-sequence proof, collision proof, or hardware authorization.

That exact overlay is now a locked, zero-authority virtual commissioning scenario. The complete keyboard `test` session accepts 48 virtual joint waypoints, requires four fresh fixed-overview JPEG/tag/pose passes, and resolves four simulated contacts from solver-achieved board-frame tip geometry; the Android `test.` session accepts 61 waypoints, verifies the initial UI state, requires five pixel/pose passes, and geometry-resolves five simulated taps. Pixel processing receives no action or target, the device models receive no per-action expected character, and a separate exact-once observer consumes only their `ContactResult` records. Schema-v3 reports and manifest-v2 packages bind a strict redacted vision ledger plus every contact-result hash before comparing output hash/length; replay recomputes every artifact. Both sessions return to park, close the virtual plant, and generate zero hardware commands. Hardware-neutral runtime-port contracts now have deterministic VIRTUAL/REPLAY implementations and a separate complete mission-through-ports rehearsal. The geometry-rich adaptive executor is not yet a commissioned physical-port implementation. Physical static-camera identity, intrinsics/distortion, `Wv_T_C_overhead_optical`, support rigidity/keepout, controller correlation, contact guarding, and real outcome observation remain blocked.

A separate adaptive-schema runner retains the former moving-camera architecture
as optional Phase 2 research without changing the replay-stable fixed-overview
path selected for Phase 1 migration. It derives
`Wv_T_C_arm` from achieved six-joint feedback, renders the partial RC03 view to
real JPEG bytes, independently recovers `C_arm_T_board`, and classifies the
registration as `REJECT`, `NO_CHANGE`, or `APPLY`. On `APPLY`, it reconstructs
the current tip from achieved feedback, checks correction legs, re-solves the
entire remaining Cartesian suffix, and atomically replaces the old queue only
after every new waypoint passes the same IK gates. Camera and achieved-contact
models share one opaque virtual board truth that the planner cannot read. The
12 mm shifted keyboard regression proves that the nominal contact misses while
the corrected contact resolves `keyboard:A`; the 8 mm shifted Android case
resolves `phone:key_a`; both converge at a re-observed hover, verify independent
output, return to park, and generate zero hardware commands. The synthetic
holder transform and wide-FOV intrinsics are unmeasured, so this is software
integration evidence—not installed-camera, calibration, collision, or contact
qualification.

The adaptive layer also has two bounded milestone campaigns. One runs all 46
keyboard and 29 phone targets as independent complete moving-camera,
achieved-contact, outcome, and park sessions. The other combines twelve fixed
nominal/signed/over-limit cases with SHA-256-seeded translation/yaw cases while
keeping exact hidden transforms out of the report. Moving-camera schedules
cover unavailable, tag-loss, blur, noise, unqualified-timestamp, and stale-frame
failures; each must close before contact. See the
[adaptive stress guide](../../software/docs/ADAPTIVE_PREHARDWARE_STRESS.md).

The 2026-09-04 full-catalog run used planar estimator v1.1's monotonic consensus
with a synthetic 2.5 mm translation, 0.5 degree yaw/tilt, and 5 px maximum
inlier-RMSE policy. It accepted 75/75 adaptive target sessions within the
128-execution ceiling for each single-target route; its deterministic report
SHA-256 is
`232dcdd5c7bb6cb7afb6e4dcac6001797991faa54587dd7e0979e67880d8d4e2`.
The perturbation campaign remains deliberately stricter at 1.5 mm,
0.25 degree, and 3 px. Its 2026-09-04 estimator-v1.1 rerun passed all 20/20
declared outcomes, including four expected safe rejections, with report SHA-256
`9dda1bc28015ee6943d0e5017e16756dd30c6d0530d950a818161c28aa15dd20`.
These policies and results remain synthetic zero-authority evidence, not
installed-camera or physical motion qualification.

`qualify-prehardware` now composes those paths into one hash-bound regression
campaign. The five-case quick profile checks coherent startup, corrected
keyboard and phone contact, legacy pixel tag-loss fail-stop, and a complete
document determinism repeat. The standard profile adds nominal adaptive cases,
excessive-offset rejection, all nine legacy fault families, and a fresh
required 75/75 route screen on the promoted unmeasured overlay. Its report
keeps `campaign_passed`, route coverage, and `physical_ready: false` separate;
even a complete pass generates zero hardware commands and cannot release a
physical gate. A dedicated six-artifact, manifest-last evidence schema can now
record the compact report; replay rejects byte/schema/hash/authority drift and
reruns the complete public campaign rather than trusting stored PASS data.

`collision-status` currently reports `COLLISION_DIAGNOSTIC_BLOCKED_REQUIRED_GEOMETRY_INCOMPLETE`: all 19 required bodies are named and bound, but seven robot bodies lack geometry and six installed base/clamp/holder/camera/connector/cable/tool bodies remain unknown. `simulate-trajectory` and mission coverage check sequential IK, margin/delta gates, and numerical rank of the solver's weighted task; normalized conditioning is report-only, and full physical singularity, payload, calibration, collision, device-outcome, and commissioning evidence remain blockers. Every result generates zero hardware commands and leaves the canonical geometry and physical release unchanged.

## Start here

1. Open `active-project/RoCell_v0_3/BUILD_BY_STEP/README.md` and proceed through Step 00, then assembly Steps 01-15.
2. Review `active-project/RoCell_v0_3/PRINT_READINESS.md`; only jobs marked **READY** are released to print.
3. Use one unique build ID in every step's `06_EVIDENCE/` folder; never overwrite evidence from an earlier build.
4. Use `active-project/RoCell_v0_3/RC03_INTEGRATED_BUILD_PLAN.md` for the engineering rationale and `ASSEMBLY_MANUAL.pdf` for subsystem detail.
5. Preserve completed Job `00A` evidence, then print diagnostic jobs `00B` through `00F` before production parts and record the measured selections.
6. Use `BOM.csv` for purchasing, `JOB_KITS.csv` for staging, and `BUILD_TRACKER.md` for lifecycle status.

## RC03 package map

| Location | Purpose |
| --- | --- |
| `cad/step/` | Neutral STEP models, structural-board reference, and full assembly |
| `stl/` | Individual RC03 printable parts; the named board reference is explicitly non-printable |
| `print_plates_3mf/` | Twenty-four modular QIDI Plus4 print jobs and controlled setting sidecars |
| `config/` | Dimensions, print jobs/profiles, measurements, and generated layout source |
| `drawings/` | Named board features and 1:1 hand-drill/direct-tag setup template |
| `fiducials/` | Exact-size AprilTags, ChArUco assets, and runtime coordinate map |
| `job_cards/` | Per-job controlled travelers |
| `scripts/` | CAD, drawing, plate, readiness, preview, documentation, and release generators |
| `software_helpers/` | Camera calibration and AprilTag detection utilities |
| `images/` | Generated assembly, exploded, and part-reference previews |
| `BUILD_BY_STEP/` | Generated operator sequence with one complete work package per step; canonical files are linked and hash-checked rather than duplicated |

## Operating rules

- RC03 is designed around the QIDI Plus4 nominal 305 x 305 x 280 mm volume and a provisional protected 295 x 295 x 275 mm envelope; the actual-machine envelope gate must still pass.
- The 610 x 457 x 18 mm board is purchased cut to rectangle or hand cut, sealed on both faces, and hand drilled with the generated 1:1 template and depth stops. No router or CNC is required.
- Do not combine RC02 fixtures, coordinates, tag frames, plates, or instructions with RC03.
- Do not scale production geometry to force a fit. Qualify the actual material/hardware with the matching diagnostic job, record the result, regenerate, and revalidate.
- The package can be digitally consistent while remaining physically **UNRELEASED**. Device measurements, coupons, first articles, direct-tag metrology, repeatability, QIDI Studio round trips, and safety gates still require real evidence.
- Use `SHA256SUMS.txt` to verify the supplied package after the final generation pass.
