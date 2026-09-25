# First-power-on onboarding and rehearsal

This guide defines the ordered path from the current hardware-independent
software state to the first controlled connection of the RoCell workcell. The
same order is exercised now by `rehearse-first-power-on` using deterministic
fake camera and arm observations. This command constructs its built-in fake
provider internally; callers cannot swap in a live provider. A separate
`physical-onboard` subsystem now preserves the gate order in a source-bound,
persistent diagnostic journal. It can retain physical evidence and explicitly
requested device metadata, but it does not change this rehearsal's provider and
does not yet expose a reviewed physical-stage PASS assessor or any release
command.

The command is a **zero-hardware rehearsal**. It does not enumerate or open a
camera, open a serial port, power the RoArm, request live feedback, generate a
motion command, initialize the controller, validate an E-stop, calibrate a
physical transform, or release contact. A nominal result means the onboarding
logic reached its expected terminal state; it does not mean the cell is
commissioned.

For the actual arrival-session commands and their strict stop line, use
[Physical onboarding automation](PHYSICAL_ONBOARDING_AUTOMATION.md). The safe
Windows entry point from the workspace root is
`.\start-rocell-onboarding.ps1 -CellId CELL-A`; it
prepares the controlled environment, runs only hardware-free checks, and creates
a diagnostic session with the first two zero-I/O stages prepared. Those checks
include a fresh incapable-provider B0477/RoArm connection rehearsal immediately
before the session is bound.

## Current architecture and controlled-state boundary

Phase 1 uses the purchased Arducam B0477 / Sony IMX283 camera with the included
nominal 16 mm manual C-mount lens as a **static overhead** camera. The host
computer connects to that camera over its own USB 3 data path. The camera is not
mounted on the RoArm and does not connect through the RoArm ESP32.

The source-locked B0477 profile, support design, fake UVC inventory, synthetic
intrinsics contract, and static JPEG-to-tag-to-pose rehearsal are additive
preparation for that Phase-1 architecture. Freeze 009 remains immutable and
contains historical eye-on-arm declarations. Onboarding must expose that
controlled migration as an outstanding physical handoff condition. It must not
silently rewrite Freeze 009 or interpret the additive B0477 selection as a
physical release. A later reviewed, superseding freeze must synchronize the
controlled build before physical commissioning can complete.

The current hard conditions remain:

- `safe_to_power_robot: false`;
- `contact_enabled: false`;
- physical calibration registry empty/blocked;
- physical release unreleased; and
- no live-motion command exposed by this workflow.

## Quick rehearsal

Run from the workspace root after installing the package, or use
`python -m rocell` with `software/src` on `PYTHONPATH`:

```powershell
rocell --workspace . rehearse-first-power-on `
  --scenario nominal `
  --require-expected `
  --json
```

Exercise only the prefix through camera setup:

```powershell
rocell --workspace . rehearse-first-power-on `
  --scenario nominal `
  --stop-after optics_intrinsics `
  --require-expected `
  --json
```

The shorter connection-lifecycle rehearsal is also part of host preparation:

```powershell
rocell --workspace . rehearse-physical-connections `
  --require-expected `
  --json
```

It uses only constructor-fixed incapable providers and exercises host dependency
evidence, persistent B0477 discovery/open/configure/flush/fresh-frame/
close-reopen-close, unpowered RoArm identity, and one synthetic T=105/T=1051
exchange. Named faults cover wrong identity/mode, stale frames, identity drift,
close failure, dirty serial input, malformed feedback, and retry prohibition.
It performs no OS inventory or physical device I/O.

Create an explicit checkpoint, then verify and resume it:

```powershell
rocell --workspace . rehearse-first-power-on `
  --scenario nominal `
  --stop-after camera_frame_freshness `
  --checkpoint software/runs/first-power-on-rehearsal.json `
  --require-expected `
  --json

rocell --workspace . rehearse-first-power-on `
  --scenario nominal `
  --resume software/runs/first-power-on-rehearsal.json `
  --require-expected `
  --json
```

Use the exact checkpoint path emitted by the command if the implementation
selects a content-addressed filename. `--resume` means “strictly verify prior
rehearsal state and continue the simulation.” It never means reconnect,
re-energize, reinitialize, retry motion, or resume a physical operation.

`--require-expected` returns nonzero if a scenario behaves differently from its
declared expectation. A deliberate fault scenario is successful only when its
exact signature matches: blocking stage, detail code, failed-check IDs, and
bounded synthetic frame/feedback counts. Downstream stages must not run and the
report must retain zero authority. Stopping a fault scenario before its injected
gate is a checkpoint, not a successful fault result.
For serial faults, the detail code is derived from the behavior observed at the
fake wire boundary—not selected from the requested scenario name—so swapping a
timeout for a disconnect or malformed reply is detected as a mismatch.

## Physical-shaped provider contract

The original 15-stage command remains the broad, source-bound onboarding
rehearsal. A second API now exercises the exact *provider shape* expected for a
future hardware-acquisition workflow without sharing a live/physical switch:

```python
from rocell.application import (
    build_physical_shaped_fake_providers,
    default_physical_shaped_onboarding_request,
    run_physical_shaped_fake_onboarding,
)

request = default_physical_shaped_onboarding_request()
providers, audit_provider = build_physical_shaped_fake_providers(request)
result = run_physical_shaped_fake_onboarding(request, providers)

assert result.zero_physical_authority
assert result.accounting.synthetic_feedback_requests == 1
assert result.accounting.synthetic_t104_motion_requests == 0
```

Its ten ordered stages are camera receipt, persistent OS inventory/selection,
exact native mode and manual-control readback, buffer flush/fresh captures,
close/reopen identity verification, retained-install calibration acquisition
receipts with a precommitted 24-training/8-held-out split bound to mount,
lighting, manual-focus lock, aperture lock, and fixed cable-route witnesses,
arm identity while power is reported off, procedure-shaped safety
evidence, a zero-command power-event observation, and exactly one
identity-bound synthetic `T=105`/`T=1051` exchange. Cleanup is attempted in a
`finally` path at every one of the 17 provider-call boundaries.

The accepted provider descriptor is constructor-fixed to `EXPLICIT_FAKE`.
The protocols expose no motion, contact, raw-write, serial-open, or generic
command method, and the result types permanently report no physical receipt,
calibration, safety, power, release, motion, or contact authority. A future
live adapter must live in a separate physical-evidence package and map observed
OS/UVC/serial data into separately reviewed schemas; it cannot be enabled by
changing a flag or substituting a provider in this runner.

## Persistent physical-arrival controller

The distinct `physical-onboard` controller is implemented for evidence-bearing
arrival work. It binds the active build, exact stage plan, policy, launcher and
setup scripts, controlled configuration/design/runbook sources, and the RoCell
Python source tree. Its journal and high-water record are append-only; evidence
is copied into bounded content-addressed packages, and every mutation requires a
fresh challenge bound to the current source/session/journal/evidence state.

Automation is deliberately narrow:

- `new --prepare-safe` may automatically pass only `workspace_sources` and
  `static_camera_contract`, both without device enumeration or I/O;
- `next --execute` can only put a later stage into `WAITING_OPERATOR`;
- `intake` validates the controlled 55-row received-hardware questionnaire;
- `inventory`, when explicitly invoked after its session/host preflight, reads
  camera and serial identity metadata but never opens or selects a device; and
- `verify` rechecks the complete source/header/journal/high-water/evidence
  closure.

Four canonical typed receipt schemas are implemented for the three most
judgment-sensitive manual boundaries and their review:

- `CameraReceiptInspection` for the exact delivered B0477/lens/article evidence;
- `PowerSafetyReview` for a de-energized E-stop, supply, mounting, cable, and
  keepout review;
- `FirstPowerObservation` for exactly one externally controlled possible-motion
  event, including effect certainty, startup-motion classification, attempt and
  automatic-retry counts, and bound media; and
- `ControlledOperatorDecision`, exactly bound to one subject receipt and its
  assessment.

Those schemas reject extra, ambiguous, or noncanonical data and bind the
source, session header, cell, stage plan, stage, and content-addressed evidence.
Their assessors can produce only `DIAGNOSTIC_READY`, `HOLD`, or
`SIDE_EFFECT_UNCERTAIN`. There is no generic PASS receipt; an acknowledgement
cannot upgrade a hold or uncertainty, and none of these types can mutate the
session or confer power, motion, contact, release, or build-promotion authority.
They remain a Python/tested foundation until a separately reviewed CLI assessor
is implemented.

## Power domains and connection order

Treat these as three independent systems:

1. **Host computer** — loads and verifies configuration and records evidence.
2. **Static B0477 camera** — may be connected to a qualified host USB 3 port
   while the RoArm remains de-energized.
3. **RoArm-M3 Pro** — receives 12 V actuator/controller power separately and
   is not powered merely because the camera is connected.

This separation lets camera identity, modes, controls, focus, intrinsics, and
installed visibility be qualified before robot power is considered. It also
prevents camera success from being treated as an arm-power permit.

## Ordered onboarding state machine

Every stage consumes only evidence produced by its declared prerequisites. A
blocked stage stops the forward path; later evidence cannot fill an earlier
gap. The rehearsal uses synthetic inputs and marks each success as
rehearsal-only. The persistent arrival workflow must supply separately typed,
observed evidence and currently stops before any human-reviewed stage can pass.

| Order | Stage | What the rehearsal proves | Physical evidence that must replace it | Required physical power state |
| ---: | --- | --- | --- | --- |
| 1 | `workspace_sources` | Runtime policy, active manifest, source hashes, simulation bundle, build identity, and zero-authority rules load coherently | Exact received/build identity and a reviewed controlled source set | Arm and camera need not be connected |
| 2 | `static_camera_contract` | The B0477 profile, static support screen, commissioning/UVC/intrinsics fixtures, and normal/tag-loss pixel reports are consumed as one coherent synthetic stack | Received camera/lens/support identities and a superseding static-camera freeze | RoArm off |
| 3 | `camera_receipt` | A strict, typed zero-hardware receipt is parsed before comparison; the adapter requires the comparator's exact ten-check contract, and a modeled wrong article has its own different content hash and fails the exact B0477/IMX283/16 mm identity check | Photographs of labels, camera, lens, cable, connectors, enclosure, and kit; exact model/serial and delivered lens; measured enclosure, mass, projection, mount/thread, connector, and usable fastener depth. Measure and retain `INT-005` board-flatness evidence here, but do not accept that limit here. | RoArm off; camera need not be connected; `INT-005` acceptance remains deferred to Stage 14 after the target-accuracy budget closes |
| 4 | `camera_identity` | Unique persistent-camera selection and wrong/ambiguous-device rejection work with the fake UVC provider | VID, PID, serial descriptor, persistent OS path, driver, negotiated bus, and stability after reopen/reconnect/reboot | RoArm off; camera connected to known USB 3 host port |
| 5 | `camera_mode_controls` | Exact-mode, USB-bus, FOURCC, manual exposure/gain/white-balance, and close/reopen gates behave correctly; the software does not read the manual lens rings | Before the first possible capture, clear private screens, documents, people, and identifiers from view; then read back `5472 x 3648 @ 9 fps YUY2`, negotiated USB 3 topology/speed, exposure, white balance, and gain; physically set, lock, witness, photograph, and later verify focus/aperture; prove reconnect and host-reboot stability | RoArm off; camera on; missing privacy clearance blocks capture |
| 6 | `camera_frame_freshness` | The nominal synthetic pair passes only when its capture sequence advances and its raw JPEG digest changes; `camera-frame-stale` and `camera-frame-rewrapped` prove that unchanged sequence or unchanged raw bytes block even if wrapper metadata changes | Bounded buffer flushing, device/host timing brackets, latency, dropped-frame behavior, and multi-frame stability from the received camera; distinct synthetic JPEG bytes are not a substitute for physical timing evidence | RoArm off; camera on |
| 7 | `optics_intrinsics` | Preliminary one-metre focus/FOV/throughput qualification is kept separate from the sealed 24-training/8-held-out synthetic ChArUco contract; temporary-fixture results cannot become final intrinsics | Delivered-lens focus/FOV/throughput feasibility at `950..1050 mm` and a reviewed final-install capture protocol; no final calibration is accepted here | RoArm off; camera on |
| 8 | `static_registration` | Synthetic six-tag visibility, planar-pose acceptance, and tag-loss rejection work at the nominal static support geometry | Retained camera/light/cable installation followed by warm-up, exact mode/control readback, locked focus/aperture, physical ChArUco intrinsics, measured tag corners/plane, static eye-to-hand transform, held-out K0/P0 checks, disturbance/reseat/drift results, and route visibility atlas | Actuator 12 V physically disconnected; no arm motion |
| 9 | `arm_identity` | The expected Pro model, serial protocol, 115200-baud profile, explicit ownership, disabled auto-connect/auto-initialize rules, expected firmware package, and approved read-only firmware-query plan are represented | Exact RoArm-M3 Pro serial number, controller USB identity, stable port identity, power supply, connection ownership, expected firmware package, and an approved non-motion readback method; this stage produces only an inventory candidate and never a qualified controller identity | RoArm off; do not open the port |
| 10 | `power_safety` | Missing checklist evidence blocks the modeled power boundary; no geometry, clearance, E-stop, gravity, or power-loss behavior is simulated | Installed and tested physical power-cut E-stop, gravity-safe containment, board anti-shift, complete startup swept-volume clearance, approved power procedure, observer, and empty cell | RoArm off |
| 11 | `power_on_observation` | The workflow treats application of robot power as a possible motion event and exercises only the required observation-record schema without issuing host motion or predicting a trajectory | A unique, reviewed Stage-11 energization envelope; video/observer record of whether and how the arm moves, actual swept clearance, abnormal behavior, E-stop access, contained power-loss behavior, and independently observed final de-energization | First supervised RoArm power only after Stage 10 physically passes; Stage 11 must end with actuator power off and creates no standing authority |
| 12 | `feedback_only_connection` | Exact T=105 request/T=1051 response framing, typed endpoint/joint/load/torque/voltage parsing, timeout/reset/disconnect/malformed failures, and pre-request receive-buffer freshness are rehearsed with a hardware-incapable emulator; nominal simulation uses two scripted open/query/close cycles and cannot mint a live feedback permit | After Stage 11 ends de-energized, create a new Stage-12 energization envelope; with devices/tools removed, manually energize, consume a one-use permit before opening the explicitly selected identity-bound port, keep RTS/DTR disabled, require a quiescent receive buffer, issue one bounded T=105 feedback request, retain raw bytes and decoded fields, close without retry, manually de-energize, and prove final power off. Promote the Stage-9 inventory candidate to `qualified_controller_identity` only after the controlled exchange and an approved installed-firmware observation; otherwise Stage 12 remains blocked. | Fresh Stage-12 envelope and observer/E-stop controls; serial open is a possible reset/motion effect even though T=105 is not a motion command; final actuator power off is mandatory |
| 13 | `reference_frame_calibration` | The complete selected static-overhead Phase-1 graph rehearses 15 versioned artifacts, both 12-artifact device closures, and all 68 parent/context staleness edges; its namespaced calibration-dependency set therefore has 39 entries (15+12+12), independently of the different 39-component top-level bundle contract; settings and intrinsics bind the retained stack while the empty physical registry remains blocked | First, a separately permitted and sealed empty-cell precalibration bootstrap based only on external geometry and conservative containment; then an independently reviewed reference-characterization campaign with repeated achieved feedback, joint signs/zeros/ranges, `R_ctrl` correlation, installed B0477/board/robot/TCP/device-map/outcome-observer artifacts, and held-out residuals | Each external campaign has its own envelope and permit, must prove final actuator disconnection, and seals uncertain/quarantines if final power is unknown; the wizard imports reports and does not initialize or move the arm |
| 14 | `noncontact_acceptance` | Keyboard and phone virtual reports reuse the newest accepted Stage-8 sequence-101 B0477 normal/tag-loss pair and expose exactly 109 virtual waypoints, nine virtual contact attempts/acceptances, and nine observations; they verify output, park/close, and a first-waypoint stall with no later contact/observation while the incomplete physical collision model stays blocked | Complete physical link/tool/cable/gantry collision geometry, approved limits/program hashes, reduced-speed empty-cell motion, E-stop tests, safe park, above-surface route checks, and one-device-at-a-time noncontact hover validation | Only after separately released empty-cell-motion gates; every campaign must end with independently proven actuator disconnection, and unknown final power seals uncertain and quarantines |
| 15 | `physical_handoff` | Rehearses the different 39-component top-level `CommissioningBundle` contract directly from the controlled stage catalog and verifies that every component has one producer; it explicitly satisfies zero physical components and does not construct the real bundle | A verified physical `CommissioningBundle`, every applicable blocker retained, and independent review; any promotion, motion, descent, keyboard contact, or phone contact remains a later, separate release | This rehearsal performs no hardware I/O or power action, leaves `commissioning_bundle_complete: false`, does not claim `COMPLETE_DIAGNOSTIC`, and retains `physical_release_effect: NONE` |

At the reusable connection-contract layer, `B0477NativeMode.host_bus` is the
family label `USB_3_X`. The selected camera profile, inventory/topology receipt,
and physical onboarding policy remain stricter: they require the observed link
to satisfy `USB_3_2_GEN_1`. A generic USB-3-family mode receipt alone is not the
topology/speed evidence required for the physical stage.

The exact nominal rehearsal terminal status is
`SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED`. It distinguishes
a complete software exercise from a commissioned cell.

The nominal report now separates simulated activity from hardware-protocol
activity. It records 15 emulated image observations in the full workflow, two
hardware-incapable feedback requests, 109 executed virtual waypoints, nine
virtual contact attempts, nine accepted virtual contacts, and nine virtual
outcome observations. Hardware arm motion commands and physical contact
commands remain exactly zero. The per-action mission imagery still comes from
the mature fixed-overview virtual plant and is post-associated with the newest
validated, content-addressed Stage-8 B0477 mission context; the report explicitly says
that a new B0477 pixel frame was **not** rendered for every action. That is a
known simulation boundary, not physical camera evidence.

The report, checkpoint, and CLI envelopes are version 2. Version 2 adds exact
virtual waypoint/contact/observation counters and is intentionally not parsed
as the earlier strict version-1 checkpoint shape.

The nominal frame-freshness check is intentionally a synthetic two-part oracle:
both sequence and raw-JPEG digest must advance. The rewrapped-frame scenario
advances wrapper/sequence metadata while repeating the observed raw digest and
must block. Identical image bytes alone are not a valid physical stale-frame
decision for a static scene; the received camera still requires qualified
device/host timing, buffer flushing, latency, and dropped-frame evidence.

Likewise, the hardware-incapable feedback emulator uses two scripted
open/query/close cycles to exercise exact framing and bounded exchange
accounting across a reconnect. T=1051 has no echoed host transaction ID, so the
software cannot infer on-wire request/reply identity from a label. Instead it
requires the receive buffer to be empty before open acceptance and again before
every request. The `arm-stale-feedback` scenario places a complete valid T=1051
line in that buffer before the second open; the session closes and emits no
second T=105 request. It issues no `FeedbackPermit`, and its session type cannot
be passed to the live transport. The first physical read-only session remains
exactly one bounded, properly authorized T=105 transaction. Qualified physical
timing and buffering evidence remains open.

## RoArm automatic power-on motion

Waveshare documents that the arm can move its joints toward a middle position
when powered on. Therefore **“the host sent no motion command” does not mean
“the arm cannot move.”** Applying 12 V power is itself treated as a motion
event and requires a cleared, controlled startup envelope.

Before the first physical power application:

- remove the keyboard, phone, contact tools, loose parts, and unnecessary
  cables from the swept area;
- install and function-test the independent power-cut E-stop;
- establish passive gravity-safe containment so an E-stop or power loss cannot
  let the arm fall into a person, board, support, or device;
- model and clear the complete possible startup sweep, including gripper,
  attachments, camera portal, lights, fasteners, and cables;
- place an observer at the E-stop and keep every person outside the sweep;
- do not connect a serial client that may assert RTS/DTR or initialize the arm;
  and
- record the actual power-on behavior before defining any reference or park
  procedure.

`power_on_observation` simulates this decision point only. It does not turn on
an outlet, controller, or supply, and it cannot verify the real startup path.
If physical power-on behavior is unknown, differs from the approved envelope,
or produces unexpected motion, cut power using the independent control and
return to the safety/collision stage. Do not compensate by immediately sending
a park command.

## Exact physical order when hardware arrives

The eventual operator sequence is intentionally more conservative than
“connect everything and run calibration”:

1. With all workcell power off, inspect and record the exact board, support,
   camera, lens, cable, arm variant, controller, supply, clamp, and fasteners.
2. Keep the RoArm de-energized. Connect only the B0477 to a known USB 3 host
   port with a short qualified cable. Record persistent identity and all modes.
3. Request and read back the exact native YUY2 mode and manual controls. Repeat
   close/open, cable reconnect, and host reboot checks without fallback to a
   numeric camera index.
4. On an adjustable optical test fixture at `950..1050 mm`, prove feasibility:
   the delivered lens can reach board-wide focus and the camera can provide the
   required field of view, orientation, throughput, and control range. Treat
   these as preliminary measurements only; do not accept final intrinsics from
   the temporary mounting stack.
5. With actuator 12 V physically disconnected, install the camera, tether,
   final diffuse lighting, and strain-relieved cable on the common static
   frame. Warm it to its defined operating condition, then
   read back the final mode/controls; set, lock, and witness focus/aperture in
   the retained installation. Capture the physical ChArUco training/held-out
   sets only now. Solve installed intrinsics, measure the support and tag map,
   and independently validate static registration. Repeat bump, tug, reseat,
   warm-up, cycle, settle, and drift checks; any changed mount, focus, lighting,
   cable load, mode, or controls invalidates the optical artifacts.
6. Still with the RoArm off, bind its exact identity and verify that the host
   profile has no automatic connect, initialize, fallback, or retry behavior.
7. Install the E-stop, gravity containment, anti-shift controls, and complete
   startup collision envelope. First verify the power-cut circuit against an
   electrically representative inert test load with the RoArm disconnected;
   record voltage removal and reset behavior. This electrical check does not
   prove mechanical stopping or gravity safety. Obtain the remaining reviewed
   safety and limit evidence. If any field is missing or stale, stop here.
8. Create and arm one unique Stage-11 energization envelope, clear the cell,
   and apply arm power under direct observation. Issue no host motion. Record
   whether and how the arm moves, the complete startup behavior, and the
   contained power-cut consequence. Manually de-energize, independently observe
   actuator power off, and seal the envelope; it creates no standing authority.
9. Create a distinct Stage-12 envelope and repeat its current safety, observer,
   E-stop, identity, and empty-cell checks. Manually energize, then consume the
   one-use feedback permit **before** opening the selected commissioned serial
   port with reset lines inactive. Treat port open as a possible reset or motion
   effect even though T=105 is not a motion command. Perform one bounded T=105
   transaction, record raw and decoded evidence, use only the separately
   approved read-only method to identify installed firmware, and close it. Do
   not blind-retry. Manually de-energize and independently prove final actuator
   power off.
10. In a separately permitted, externally measured and contained empty-cell
    session, run and seal the conservative precalibration bootstrap. Only then
    independently review and permit the reference-characterization campaign;
    characterize reference behavior and controller/model correlation, then
    solve installed arm/board and TCP calibrations with held-out validation.
11. Add only released reduced-speed empty-cell programs. Test stop, power loss,
    safe park, and above-surface routes with devices removed, then one device at
    a time without contact.
12. Treat keyboard contact and Android contact as later independent releases.
    Neither feedback success nor calibration success authorizes descent.

## Checkpoints and resume semantics

A checkpoint is evidence of a rehearsal prefix, not a mutable permit. It binds
the workflow definition and scenario, the implementation source tree, all
enumerated transitive controlled inputs used by the rehearsal, ordered stage
results chained by `previous_record_sha256`, its own canonical hash, and its
zero-authority declaration. It is not a signed physical evidence package or a
motion permit.

On resume, the command must:

1. load bounded strict JSON and reject duplicate keys, nonfinite values,
   unexpected fields, paths outside the controlled root, and symlinks;
2. re-enumerate and hash the implementation plus transitive controlled input
   set, then require exact agreement with the recorded source bindings;
3. recompute the checkpoint and ordered record hash chain;
4. rerun every completed deterministic stage from the beginning and compare
   each reconstructed record exactly with the stored prefix;
5. reject reordered, missing, duplicated, added, altered, or replay-divergent
   stage results, naming the first replay-divergent stage when applicable;
6. repeat a previously blocked stage rather than treating it as progress; and
7. retain explicit zero hardware, motion, calibration, and release authority.

There is no automatic resume after interruption, camera loss, serial loss,
controller reset, E-stop, power loss, source drift, or calibration fault. A
physical arrival session currently stops for deliberate reconciliation; a
future reviewed recovery command must require fresh preflight evidence. A
synthetic checkpoint must never be accepted as that evidence.

## Fault scenarios to rehearse

The integrated scenario catalog is finite and visible through `--help`. The
named scenarios below are the exact end-to-end injections implemented by this
command. The broader failure-family table also records conditions that must be
covered by lower-level tests or future physical adapters; it must not be read as
a claim that every listed condition has its own integrated scenario.

The implemented values are `nominal`, `camera-receipt-mismatch`,
`camera-missing`, `camera-wrong-identity`, `camera-usb2`,
`camera-settings-drift`, `camera-frame-stale`, `camera-frame-rewrapped`,
`intrinsics-tampered`, `camera-tag-loss`, `arm-identity-mismatch`,
`startup-safety-blocked`, `startup-motion-unobserved`, `arm-timeout`,
`arm-malformed-feedback`, `arm-disconnect`, `arm-reset-banner`,
`arm-incomplete-feedback`, `arm-stale-feedback`, `calibration-stale`, and
`noncontact-path-blocked`.

| Family | Injected condition | Required behavior |
| --- | --- | --- |
| Controlled sources | Manifest, profile, support, workflow, or fixture hash mismatch | Block before optional hardware imports or provider construction |
| Camera selection | Camera absent, duplicate candidates, missing persistent identity, wrong model, or changed reconnect identity | Block `camera_identity`; never fall back to index `0` |
| USB/mode/settings | USB 2 negotiation, native mode absent, wrong size/FPS/FOURCC, automatic exposure/white balance, or reopen drift | Block `camera_mode_controls`; no alternate backend or silent mode downgrade |
| Frame integrity | Stale sequence, repeated raw JPEG hidden behind a fresh wrapper, unavailable, duplicate, wrong-resolution, oversized, or temporally invalid frame | Block `camera_frame_freshness`; do not reuse the last frame; the integrated scenarios explicitly cover stale sequence and rewrapped raw bytes, while physical buffering/timing remains open |
| Optics/calibration | Blur, glare, weak regional coverage, dataset split violation, altered image hash, identity/settings mismatch, or artifact tamper | Block `optics_intrinsics`; never promote synthetic or mismatched intrinsics |
| Static registration | Required-tag loss, excessive residual/covariance, support witness movement, board/station shift, or stale extrinsic | Block `static_registration`; no descent or nominal-pose substitution |
| Arm identity | Missing/ambiguous port, wrong controller, wrong arm variant, unapproved firmware, or reset-line policy change | Block `arm_identity`; do not open a serial port |
| Power safety | E-stop, gravity containment, anti-shift, startup sweep, observer, or approved limits absent | Block `power_safety`; no simulated success may confer power permission |
| Power-on observation record | Missing required startup-observation or containment fields | Fail `power_on_observation` and require return to the safety/collision stage; trajectory, dynamics, E-stop performance, and gravity consequences are not simulated |
| Feedback protocol | Timeout, partial write, disconnect, reset banner, malformed/overlong/truncated JSON, wrong response type, incomplete/invalid fields, unavailable buffer state, or a complete valid T=1051 line already buffered before a request | Reject before reuse, fail once, close, record raw received/scripted digests and the exact detail/check/count signature, emit no blind retry, and never treat a host label as an echoed on-wire ID |
| Calibration chain | Any of the 15 static Phase-1 identity/mode/settings/intrinsics/tag/static-extrinsic/reference/controller/arm-board/device-map/TCP/outcome-observer artifacts or any of their 68 parent/context edges is missing/stale | Block at `reference_frame_calibration` or later; keep all synthetic artifacts `NOMINAL_ONLY` and do not fill physical gaps with nominal data |
| Noncontact acceptance | Injected first-waypoint arm stall in a bounded virtual keyboard route | Stop, close the virtual arm plant, prove zero executed waypoints/contact/observation and unchanged output after the injected boundary, and block downstream stages; nominal virtual keyboard/phone sessions still cannot satisfy the incomplete physical collision model |
| Checkpoint integrity | Interrupted write, unexpected file, invalid chain, tamper, source drift, or changed scenario | Reject resume without executing the next stage |

A fault-scenario report identifies the expected blocking stage, observed
blocking stage, stable detail code, expected and observed failed-check IDs,
cleanup result, stages not run, exact next safe action, and whether the complete
expected signature—including bounded simulated-operation counts—matched.
Cleanup is measured at the exercised boundary: feedback faults must report
`SYNTHETIC_SERIAL_TRANSPORT_CLOSED`, and the injected route stall must report
`VIRTUAL_ARM_CLOSED_AFTER_FAIL_STOP`. A cleanup regression adds a failed check,
makes `cleanup_satisfied` false, and prevents the fault from counting as the
expected safe outcome. Failures before any simulated resource is opened report
`NOT_APPLICABLE_NO_RESOURCE_OPENED`.

## Evidence classes must remain separate

The workflow uses three non-interchangeable evidence classes:

1. **Synthetic rehearsal evidence** proves parsers, stage ordering, dependency
   handling, fault stops, checkpoint verification, and zero-authority behavior.
2. **Observed physical diagnostic evidence** records exact device identity,
   raw feedback/captures, settings, timing, measurements, tests, residuals, and
   witnesses. It may satisfy only its named diagnostic gate.
3. **Reviewed release evidence** binds approved physical artifacts into a new
   controlled build and explicitly projects a capability. It cannot be created
   by a rehearsal or by merely changing an authority boolean.

The report should always state, at minimum:

```text
simulated_operations.camera_frames: <bounded synthetic count>
simulated_operations.feedback_queries: <bounded emulated count>
simulated_operations.virtual_waypoints_executed: <bounded virtual count>
simulated_operations.virtual_contact_attempts: <bounded virtual count>
simulated_operations.virtual_contacts_accepted: <bounded virtual count>
simulated_operations.virtual_observations: <bounded virtual count>
simulated_operations.motion_commands: 0  # hardware-protocol commands
simulated_operations.contact_commands: 0 # physical contact commands
physical_state.physical_onboarding_started: false
physical_state.camera_physically_calibrated: false
physical_state.safe_to_power_robot: false
physical_state.motion_authorized: false
physical_state.contact_authorized: false
authority.simulation_only: true
authority.hardware_accessed: false
authority.camera_enumerations: 0
authority.live_camera_frames: 0
authority.arm_port_opens: 0
authority.arm_feedback_commands: 0
authority.arm_motion_commands: 0
authority.contact_commands: 0
authority.commissioned: false
authority.safe_to_power_robot_conferred: false
authority.motion_authorized: false
authority.contact_authorized: false
authority.physical_release_effect: NONE
```

Do not use one schema that can be changed from synthetic to physical by
toggling a field. Physical acquisition, calibration promotion, and release
need separate schemas and separately reviewed commands.

## Pre-hardware implementation status and backlog

The current state machine is the startup spine, not the end of useful
simulation. Work proceeds in this order while live motion remains unavailable.
Items marked **foundation implemented** have strict zero-authority APIs and
tests; they are not physical qualification:

1. **Immutable sensor-session record/replay — foundation implemented.** The v2
   package records raw UVC-shaped bytes, decoded
   distorted and undistorted images, camera identity/mode/control snapshots,
   a synthetic unsent T=105 line, a synthetic T=1051 line, and host timing
   brackets in a manifest-last,
   content-addressed archive. Missing, extra, reordered, duplicated, or changed
   files fail replay. Pixel layouts, exact strides/byte lengths, YUY2/RGB8
   colorimetry, quantization range, chroma siting, row origin, perception-time
   freshness, bounded stage/session durations, and stored-versus-applied replay
   policies are explicit. Physical acquisition and algorithmic recomputation
   from a received camera remain open.
2. **Persistent physical-arrival evidence spine — foundation implemented.** The
   controlled launcher/environment gate, combined safe starter, source-bound
   15-stage session, append-only journal/high-water record, fresh challenges,
   bounded evidence store, intake validator, and metadata-only inventory are
   implemented. Only the two zero-I/O stages can pass automatically. Strict
   camera-receipt, power-safety, first-power, and operator-decision schemas are
   tested, but their diagnostic assessments cannot mutate the session and are
   not exposed as public stage assessors. Next, design and independently review
   the stage-specific assessor/application boundary without creating a generic
   PASS or weakening the stop line.
3. **Physical-shaped acquisition adapters — first provider seam implemented.**
   The ten-stage fake-only runner exercises camera/arm/safety acquisition order,
   including retained-install receipt hashes and unconditional cleanup. The
   synthetic tail is an exact hash chain from safety evidence through the
   power-event request/observation, in-memory controller-session identity,
   explicit empty-input-buffer observation, and sole T=105/T=1051 exchange.
   Its deterministic logical times and nonces are explicitly untrusted and
   cannot stand in for a physical clock or attestation source. Next,
   drive fake ChArUco,
   surveyed-tag, static-extrinsic, robot-reference, controller-correlation,
   arm/board, TCP, and device-map providers through the same v2 evidence schemas
   that will later accept observations. Synthetic outputs remain
   `NOMINAL_ONLY`; replacing a provider must not change the graph or gate order.
4. **Optical contract unified; broader sensitivity campaigns open.** The
   B0477 renderer and estimator now share one frame, aspect-consistent focal
   model, nonzero stress distortion, and hash-bound rectifier. Continue by
   perturbing focal length, principal point,
   distortion model, mount translation/rotation, individual tag placement and
   lift, blur, glare, exposure, partial occlusion, cable load, warm-up, and
   support drift. Report detection/reprojection/targeting sensitivity without
   converting unmeasured priors into physical tolerances.
5. **Execution-shaped RoArm emulator — partial foundation implemented.** The
   deterministic runtime ports already exercise lifecycle, feedback, faults,
   deadlines, cancellation, observation, virtual contact, outcome, and
   evidence. Add bounded protocol-shaped T=104 trajectory replay,
   achieved T=1051 feedback, settling, overshoot, timeout, reset, disconnect,
   drift, and watchdog faults. It must remain a distinct emulator type that
   cannot receive a live permit or open a serial port.
6. **Crash-safe authorized multi-action kernel — foundation implemented.** Each
   planned key/tap has a stable occurrence ID; intent and the possible-contact
   boundary are written before virtual contact. A directory-synced high-water
   record latches the first contact boundary and exact tail, so suffix loss,
   truncation, partial publication, or rollback fails closed. After a possibly
   completed contact, recovery enters `OUTCOME_UNCERTAIN` and may
   observe/retract but never blindly repeat. The shared zero-authority runtime
   now combines those journals with exact controller/build/device/calibration/
   collision/interlock/operator/plan bindings and an ordered authorization-v2
   cursor. A sealed receipt is consumed before each simulated hover, approach,
   contact, retract, and final park, and a restart requires a newly issued
   cursor for the exact safe remaining suffix. Semantic device outcome records,
   report construction, final journal verification, and cleanup-failure
   aggregation are independently checked. Coordinated malicious
   rollback of both the journal and high-water record will require an external
   append-only or WORM trust anchor in the physical design.
7. **Route-coupled collision and cable simulation.** Evaluate every
   park/transit/hover/approach/contact/retract waypoint against a complete
   synthetic 19-body model, phase-local contact allowances, uncertainty
   inflation, and sampled cable geometry. The incomplete physical geometry must
   continue to block release.
8. **Contact-guard and UI-state faults.** Simulate stale/missing load samples,
   overload, overtravel, derivative spikes, stuck contact, sensor disagreement,
   Android rotation/dialog/lock/Gboard changes, keyboard layout changes, and
   per-action outcome mismatch. Every unsafe case must latch before another
   descent.
9. **Soak, fuzz, and deterministic recovery campaigns.** Run long repeated-key
   and phone-text missions, random-but-seeded camera/controller faults,
   checkpoint corruption, cancellation, deadlines, and cleanup failures. Every
   run must retain bounded memory/files, exact operation accounting, final
   park/close when possible, and zero hardware authority.

These items improve the handoff seam and expose design errors before delivery.
They still cannot determine the real arm's startup path, installed camera
intrinsics, collision clearance, compliance, force limits, or touch/keypress
success; those remain observed physical gates below.

## What remains physical

Even a complete nominal rehearsal cannot determine or prove:

- the received B0477 serial/persistent path, exact delivered lens, enclosure,
  mass, connector, cable, mounting threads, or usable fastener depth;
- actual USB modes/controls, native throughput, frame freshness, latency,
  dropped frames, exposure behavior, focus, depth of field, glare, corner
  illumination, distortion, or thermal drift;
- final support stiffness, positive retention, cable strain, collision
  clearance, swept-volume visibility, witness stability, or reseat accuracy;
- measured tag geometry, physical intrinsics, static camera extrinsic,
  controller/model correlation, installed arm/board transform, TCP, compliance,
  force/travel behavior, or device target maps;
- the RoArm's actual power-on trajectory, reference behavior, repeatability,
  settling, feedback rate/schema, command completion semantics, or safe park;
- E-stop effectiveness, gravity-safe consequences, anti-shift performance,
  local contact guard behavior, or approved speed/acceleration/force limits;
- keyboard/OS or Android outcome observation and end-to-end typing/tapping
  accuracy; or
- physical power, empty-cell motion, descent, keyboard contact, phone contact,
  or final workcell release.

The immediate physical handoff begins with received-unit inspection and
camera-only USB qualification while the RoArm remains off. Robot power comes
later, only after the independent safety, gravity, anti-shift, startup-sweep,
and controlled-build gates are physically complete. Execute and record that
sequence only through the controlled
[physical onboarding automation runbook](PHYSICAL_ONBOARDING_AUTOMATION.md).
