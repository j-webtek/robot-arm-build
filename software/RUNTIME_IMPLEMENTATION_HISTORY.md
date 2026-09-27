# Tactevra Runtime implementation history

- **Document status:** Historical evidence index
- **Audience:** Contributors and reviewers tracing earlier implementation work
- **Authority:** Historical context only; it does not authorize hardware operation
- **Separated from:** `software/README.md` on 2026-09-27

This page preserves dated implementation checkpoints that previously appeared
before the current runtime installation and command reference. Statements such
as “current,” “next,” and “not released” apply to the checkpoint in which they
were written. For supported setup, current capabilities, and present ownership,
use the [software reference](README.md), [project status](../PROJECT_STATUS.md),
and [shared AI/arm workplan](ai/docs/SHARED_AI_ARM_WORKPLAN.md).

Historical outcomes are retained rather than rewritten to match newer
architecture or branding. Compatibility identifiers such as `rocell` remain
intentional where they name commands, packages, schemas, or historical records.

## Dated checkpoints

Working arm integration checklist: [Arm wizard implementation plan](docs/ARM_WIZARD_IMPLEMENTATION_PLAN.md).

New rehearsal feature: [Passive USB connection rehearsal](docs/ARM_PASSIVE_WIZARD_CHECKPOINT.md)
is available on the Arm page in rehearsal mode, with retained process diagnostics
and verified log export. It does not open the received arm.

Received-arm update (2026-09-12): [USB onboarding progress](docs/ARM_USB_RECEIVED_UNIT_PROGRESS.md)
records the CP210x native metadata fix, actual COM6 correlation, diagnostic
exports, and remaining serial release work. Detection is tested; physical arm
feedback and motion are not released.

RoCell is the simulation-first Python runtime for the RC03 RoArm-M3-Pro
keyboard and phone placemat. It reads the controlled hardware package, compiles
text into semantic actions, checks a frozen nominal workcell, and produces
deterministic simulation reports. It cannot command live motion or contact.

Freeze-011 state is intentionally restrictive:

- manifest `ROCELL-PHASE0-RC03-INT-R1-FREEZE-011`;
- active build `2026-09-01_CELL-A`;
- keyboard and phone routes selected;
- measurement-gate status `15 PASS / 63 NOT_TESTED / 4 NA / 2 FAIL`;
- physical release `UNRELEASED`;
- `safe_to_power_robot: false`; and
- `contact_enabled: false`.

A simulation pass never changes those values.

For the current application status, use the
[completion matrix](docs/ONBOARDING_APPLICATION_COMPLETION_MATRIX.md).
The [six-step pre-arm-calibration execution plan](docs/PRE_ARM_CALIBRATION_EXECUTION_PLAN.md)
is the current near-term implementation checklist: camera startup, static task
simulation, reach/collision diagnosis, arm onboarding, received-camera
qualification and calibration-day UI. It separates software acceptance from
physical prerequisites and does not authorize device operations by itself.
The [received-camera bench report](docs/CAMERA_BENCH_2026-09-11.md) records the
first actual B0477 capture tests, the observed 8 fps full-resolution limit, and
remaining hardware checks. Those local bench observations do not qualify or
advance the production wizard.
The [pre-build operability playbook](docs/PREBUILD_OPERABILITY_PLAYBOOK.md)
provides the current camera-first workflow and the wizard's grouped no-device
vision/fault checks. Final optics are deferred until the build is ready.
The [metadata-runtime successor checkpoint](docs/CAMERA_METADATA_SUCCESSOR_WORKORDER.md)
records the repaired wizard registration and actual B0477 endpoint/USB-instance
matching. Persistent-unit binding remains held on missing serial evidence;
no video activation, calibration or robot permission was granted by that check.
The [startup-failure diagnostics update](docs/CAMERA_ATTEMPT_FAILURE_DIAGNOSTICS_WORKORDER.md)
now exposes retained admission errors in the wizard and exported reports;
simulated deadline failures remain quarantined and cannot be replayed.
The [P1 camera timing update](docs/CAMERA_COHERENT_OBSERVATION_WORKORDER.md)
removes a redundant fresh session read and passes 417 targeted regressions.
Full-history run 04 still fails the unchanged startup deadline; the plan records
the next measured optimization. No received hardware was accessed in that run.
Its [bounded-read buffer successor](docs/CAMERA_BOUNDED_READ_BUFFER_WORKORDER.md)
reduces allocation/copying while keeping every fresh read and validation boundary.
681 selected checks pass, including expanded history profiling; fresh full-history run 05 still fails the
complete startup deadline. The remaining record/ledger costs need further work.
This does not enable physical connections or change the hardware build.
The next [existing-root optimization](docs/STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md)
passed 796 distinct selected checks, including growing and mixed history profiles.
Full-history run 06 passed probe/capture release but failed post-capture ingestion
at a missing test-source alias. After the fixture-only correction, run 07's
complete test passes, including capture/export/final readback. Its final source
comparison fails because concurrent arm/UI edits changed the shared checkout;
fixed-source acceptance remains open. A later 144-case restart/export/UI
selection passes, but is not combined with earlier-source results as one release.
No hardware qualification is claimed; coordinate or isolate source before rerunning.
The component history below includes earlier checkpoints, not a claim that
every camera/arm milestone is integrated. The latest
[task-feedback checkpoint](docs/TASK_FEEDBACK_AND_FULLSIZE_CHECKPOINT.md)
separates worker completion from sampled reachability and discloses the task
simulator's remaining legacy-camera graph. The original camera path still has
an open full-history admission-timing check; arm startup/feedback, physical
calibration and live typing remain unfinished integration/qualification work.

The local browser/terminal [wizard workbench](docs/WIZARD_WORKBENCH.md) now
provides explicit software baselines, camera/arm rehearsals, semantic task
planning and verified diagnostic exports. Run `.\start-rocell-wizard.ps1`
from the workspace root. This does not activate physical connections or
replace the remaining reviewed commissioning milestones.

The [settings-capture developer handoff](docs/CAMERA_CONFIGURATION_WIZARD_HANDOFF.md)
describes the integrated, original-bound one-frame camera settings test and its
per-attempt diagnostic export. It remains separate from physical calibration,
arm startup and typing/contact authority; missing prerequisites keep it held.

The [camera and arm connection integration plan](docs/CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md)
details the next implementation work: a service-backed onboarding interface,
native Windows camera preview/controls, identity-bound serial diagnostics,
supervised startup, calibration acquisition, and arrival acceptance tests.
The full live-connection plan is not yet implemented; the existing diagnostic
wizard is not a physical release.
Use its paired [developer playbook](docs/CAMERA_ARM_DEVELOPER_PLAYBOOK.md) for
setup commands, code ownership, dependency-ordered tickets, acceptance tests,
and developer handoffs.

The [camera identity workflow](docs/CAMERA_IDENTITY_ONBOARDING_IMPLEMENTATION.md)
adds original metadata submission, distinct BLOCKED review, restart and a
dedicated full diagnostic export. It does not release physical USB identity,
camera activation or robot startup. Its driver v2 binary is a separate
unqualified development artifact, not an automatic runtime upgrade.

The [USB identity/host-boot work order](docs/CAMERA_USB_IDENTITY_IMPLEMENTATION.md)
tracks descriptor-backed USB observations, strict native/Python conformance,
and bounded provider-reported reboot checks. The
[controlled USB integration work order](docs/USB_IDENTITY_WIZARD_DISPATCH_WORKORDER.md)
now joins exact policy-bound M1 dispatch, an owned Windows helper and original
stage records to four explicit wizard actions: inspect files, review the exact
target, collect one controlled USB baseline, and export its complete evidence.
Full-history integration verification is recorded in that work order. One
baseline is not reconnect/reboot qualification, camera capture or arm access.
Exports default to `software/runs/wizard-exports`, as confirmed by the operator;
`-ExportDirectory` can explicitly assign a different parent at launch.

The [reconnect trial increment](docs/USB_RECONNECT_WIZARD_IMPLEMENTATION.md)
adds an explicit file-only original trial declaration and complete v2 export,
with historical baseline preservation and partial-save diagnostics. It also
implements a separately tested physical-node presence helper and strengthens
the boot-report process owner. Neither is automatically run from the UI;
ordered trial acquisition and physical camera/arm qualification remain open.

The additive presence-admission path now binds the exact new-trial baseline,
fixed runtime, original runtime/policy review and one-use M1 permit. Its separate
record domain shares the complete camera-family attempt audit without changing
old camera or descriptor-query permissions. Runtime file checks and pure review
objects do not authorize execution. The owned presence runner and original
five-step absence service/UI now have a joined implementation; complete
four-phase acceptance, camera capture and arm access remain separate.

The active successor adds a **fresh trial BASELINE**: explicit Begin,
server-recorded new metadata acquisitions, file preparation, exact review,
separately requested host-boot observation and a separately admitted USB query.
Its new original-storage format and complete v3 exports preserve partial and
held records. The [baseline operator guide](docs/USB_BASELINE_OPERATOR_GUIDE.md)
describes the sequence and restart limitations. Public Begin/Prepare/Review/
Collect/export/reopen now passes actual local-storage acceptance with modeled
hardware facts and an injected BOOT_HELD result: no process or USB query runs.
The nominal boot-to-USB public software path also passes with explicitly modeled
boot/USB/process observations: real M1 admission, all nine original roles, full
export/restore, fresh reopening and no replay (two tests, 397.09s). Neither test
queries received hardware or grants a stage PASS. A real-browser diagnostic-
note/export check also passed in the confirmed workspace folder. The separately
owned presence runner, campaign and retained absence codec are implemented, but
the first public unplug-test run failed collection and remains preserved. After
failure-readback/timing fixes, fresh actual-NTFS run 02 passes the complete
five-step flow, full v4 export/restore and original reopening/no replay (700.42s).
Its hardware/process observations are modeled; this does not enable live typing.
The passing bundle is in `runs/wizard-exports/hardware-free-usb-absence-20260909-verified`.
See the reconnect work
order and [absence integration contract](docs/USB_ABSENCE_PHASE_IMPLEMENTATION.md)
for verified scope and remaining work.

The next [AFTER_RECONNECT work order](docs/USB_AFTER_RECONNECT_IMPLEMENTATION.md)
adds a typed physical-absence successor and checks newly logged metadata in
reconnect preparation. These are inert components; the new original reader,
boot/service/UI actions and full successor export are not yet joined. This
increment does not enable live camera capture or robot typing.

The [received-camera onboarding work order](docs/RECEIVED_CAMERA_ONBOARDING_IMPLEMENTATION.md)
describes the implemented file-only wizard path: original observations and
attachments, distinct exact-subject review, restart and separate complete
metadata exports. These records do not open a camera or release robot motion.

## Camera architecture migration — 2026-09-05

Phase 1 now selects a rigid, static overhead (eye-to-hand) camera as its primary
vision architecture. The additive hardware package selects an Arducam B0477
with included 16 mm lens, a nominal `B=(305,228.5,1000) mm` entrance-pupil
pose, and a compact bench-anchored front portal for detailed screening. The
strict `load_static_camera_support_design` boundary source-locks that candidate,
computes conservative 3:2 coverage, and rejects authority, geometry, optical,
base-rail, or source drift. Received geometry and every physical qualification
remain open. This selection has zero physical authority and does not change any
release, power, motion, or contact gate.

Active Freeze 011 deliberately retains the legacy arm-camera fields in the
canonical manifest and simulation hardware profile under
`CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`. The additive B0477 services and V2
mission are the selected Phase-1 simulation path; they do not silently promote
those legacy fields or create physical camera authority.

The current fixed-overview JPEG -> tag36h11 -> planar-pose pipeline is the
software migration target because its stationary-camera geometry matches the
selected Phase-1 architecture. Its camera model, intrinsics, images, results,
and acceptance bounds remain synthetic and do not qualify a physical camera or
support. Eye-on-arm work remains available only as disabled, opt-in Phase-2
research. It is not a runtime fallback, must never activate automatically, and
requires its own later qualification and controlled release.

The B0477 preparation stack now also has a provider-neutral UVC inventory
contract with a deterministic fake provider, a sealed 32-view synthetic
ChArUco intrinsics contract (24 training / 8 held out), and an application-level
coherence assessor. The intrinsics fixture binds the same synthetic persistent
camera identity and reopen settings hashes as the UVC fixture; the stack
assessor prevents independently valid artifacts for different identities,
modes, settings, or support assumptions from being combined. The recommended
full rehearsal runs both normal and tag-loss pixel cases. Its current result is
`SYNTHETIC_B0477_STACK_COHERENT` with 10/10 checks, while hardware presence,
live capture, physical calibration/extrinsic, robot motion, and contact
authority all remain false.

The separate `stress-placemat-geometry` service source-binds the active
Freeze-011 RC03 layout and nominal 46-keyboard/29-phone target catalog to the
repaired static-support design and purchased B0477 profile. Its default 59-case
matrix currently finds no sampled gap for the 46 keyboard targets and a sampled
gap for 27 of 29 phone targets; the zero-bound control keeps all 75 target
centres inside their nominal safe regions. These are unmeasured sensitivity
inputs and zero-authority software results, not hardware tolerances.

`rehearse-first-power-on` now sequences the selected static-camera preparation,
received-unit boundary, RoArm identity, pre-power safety, the required record
schema for observing possible automatic middle-position startup motion,
feedback-only protocol, calibration
dependency, and noncontact handoff as 15 deterministic stages. The receipt
stage parses and hashes the observed synthetic article before comparison, so a
wrong model cannot share nominal evidence. Frame freshness
requires both advancing synthetic sequence and distinct raw-JPEG identity, with a
separate `camera-frame-rewrapped` fault. Feedback rejects any complete reply
already buffered before a request because T=1051 has no echoed transaction ID.
The selected static-overhead calibration graph now contains 15 artifacts, two
12-artifact device closures, and 68 individually exercised staleness edges.
Checkpoint resume source-binds the implementation, runtime codec identity, and
transitive controlled inputs and reruns the exact stored prefix. The nominal
noncontact stage hash-binds every representative action observation to one
shared Stage-8 B0477 registration context and records exactly 109 executed virtual waypoints, nine virtual
contacts, and nine observations; the injected first-waypoint stall proves no
later waypoint/contact/observation and unchanged output. These are distinct
from the zero hardware motion/contact counters; the historical virtual plant
still supplies per-action pixels, so this does not claim a fresh B0477 frame at
each contact. Its nominal terminal status is
`SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED`; every real
hardware operation and physical authority remains zero.

The repository now also contains a separate persistent arrival workflow. The
root `start-rocell-onboarding.ps1` entry point prepares the controlled hardware
environment, runs the side-effect-free host gate and incapable-provider
connection rehearsal, and creates a source-bound 15-stage diagnostic session.
Only `workspace_sources` and `static_camera_contract` can pass automatically;
later stages stop in `WAITING_OPERATOR`. The underlying `physical-onboard`
commands can retain immutable evidence, validate the 55-row hardware intake,
explicitly inventory camera/serial metadata without opening either device, and
verify the append-only journal. No public CLI assessor can pass a reviewed
physical stage.

The reviewed v2 onboarding foundation remains additive and runtime-inactive.
Its strict aggregate validator source-binds six specialized contracts for
closed effect classes, canonical-stage annotations and progressive intake
ownership, configuration epochs, HZ-001..016, the workcell ICD, and
conservative keyboard/phone accuracy accounting. Stage 1 validates this graph
using bounded local file reads before recording its zero-I/O workspace
evidence.

The M1 application runtime now implements a separate qualified Windows/NTFS
publication path, ordered leases, cell-global attempt and quarantine ledgers,
source-bound v2 session creation, and cross-store verification. Its public
facade has no effect method, reports `runtime_activation: false`, and performs
zero camera, serial, power, motion, or contact operations. This is storage and
recovery infrastructure, not a physical runtime: effect coordination, workers,
permits, energization control, reviewed stage progression, physical providers,
calibration, motion, and contact remain unavailable. The controlled foundation
still reports its explicit open implementation gates until independent
milestone acceptance. See
[M1 qualified zero-hardware onboarding runtime](docs/M1_ZERO_HARDWARE_RUNTIME.md).
Validate the foundation with
`python tools/validate_physical_onboarding_foundation.py` from `software/` or
`python software/tools/validate_physical_onboarding_foundation.py` from the
workspace root.

Strict receipt schemas also exist for `CameraReceiptInspection`,
`PowerSafetyReview`, `FirstPowerObservation`, and
`ControlledOperatorDecision`. Every receipt binds the exact source/session/
stage plan and content-addressed evidence. Their assessors can return only
`DIAGNOSTIC_READY`, `HOLD`, or `SIDE_EFFECT_UNCERTAIN`; even diagnostic
readiness has permanently zero power, motion, contact, release, build-promotion,
and session-mutation authority. These schemas are a tested foundation and are
not yet wired to a public stage-advance command.

The pre-hardware boundary also includes three lower-level foundations intended
to survive the transition from fake providers to recorded hardware data:

- a separate, ten-stage physical-shaped fake-provider workflow that rehearses
  persistent camera selection, exact configuration/readback, flush/freshness,
  reopen, retained-install acquisition with a fixed 24/8 training/held-out
  split, arm-off identity, safety/power-event
  records, one identity-bound `T=105`, and unconditional cleanup without
  exposing `T=104`, raw writes, motion, or contact;
- a manifest-last raw sensor-session package for bounded transport bytes,
  raw/decoded/undistorted frame data, exact camera identity/mode/controls,
  timing, calibration/source bindings, detections, pose, and deterministic
  replay; and
- an append-only per-action mission journal with stable occurrence IDs and a
  hash-chained, sync-attempted high-water anchor plus conservative `OUTCOME_UNCERTAIN`
  recovery state. Suffix loss or truncation fails closed; once contact may have
  occurred, automatic retry is forbidden.

The current Windows directory-sync compatibility path is not evidence of
power-loss durability; the v2 roadmap requires a qualified Win32 adapter before
effects. These APIs improve startup, recording, and restart behavior in simulation.
They are not connected to live camera or serial adapters and cannot change a
physical release gate.

The B0477 bridge exercises the record path with exact `2736 x 1824` buffers:
packed YUY2 raw bytes plus RGB8 decoded and rectified bytes, with exact color
matrix/range/chroma-siting/row-origin metadata, the original
detector-input JPEG, raw/rectified tag batches, optical-map and pose bindings,
and both accepted and tag-loss cases. Its source-bound wrapper exact-compares
the complete verified/replayed package to the originating B0477 session rather
than accepting any independently self-consistent generic package. Sensor-session
v2 rejects wrong layout,
stride, byte length, capture-to-perception age, stage/session duration, file
set, canonical encoding, hash, or weaker replay policy. It still does not
independently recompute decoding, undistortion, detection, pose, or calibration;
that deterministic physical-data verifier remains a pre-hardware backlog item.

Only later passages that explicitly identify themselves as Freeze-009,
IMX335, eye-on-arm, or moving-arm-camera material are retained as historical or
optional Phase-2 provenance. That label does not apply to the current
Freeze-011/B0477/static-support sections and commands below. Historical camera
material is not a current hardware instruction, and it may not be relabeled as
B0477 evidence; replacing the retained canonical legacy fields still requires
a synchronized controlled freeze.
