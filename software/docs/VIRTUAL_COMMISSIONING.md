# Virtual commissioning without physical hardware

> **Active Freeze 011 camera architecture:** Phase 1 uses the purchased
> Arducam B0477/IMX283 USB 3.0 camera with its delivered nominal 16 mm C-mount
> lens as a rigid static overhead eye-to-hand source. The received identity,
> final support, working height, capture mode/settings, and calibration remain
> unqualified. References to the Waveshare IMX335 on the upper-arm holder are
> historical Freeze-009 provenance or optional Phase 2 research only, never an
> automatic fallback. Every result in this document remains zero-authority.

This is the executable pre-hardware workflow for the RoCell keyboard and
Android missions. It initializes the complete locked software workcell,
compiles text into semantic actions, plans a multi-contact trajectory, executes
the accepted joint states against deterministic virtual components, resolves
the achieved contact geometry against a separate virtual device model, observes
only that contact result, and can record and recompute the run.

The workflow is intentionally useful before the arm, camera, keyboard, or phone
is connected. It is not a physical robot authority. A successful run proves
that the implemented software components agree for the selected idealized
inputs; it does not prove that the received mechanism can occupy or safely
follow the route.

## Current hardware and model contract

The controlled robot identity is the Waveshare RoArm-M3 Pro, 5 + 1 DOF. The
standalone product includes the default upper-arm camera holder but does not
include camera electronics. The onboard ESP32-WROOM-32 is the arm controller,
not the camera.

The selected Phase-1 purchase is the Arducam B0477, supplier-described Sony
IMX283 20 MP USB 3.0 UVC camera in a metal case with a nominal 16 mm manual
focus/aperture C-mount lens. The published native `5472 x 3648 @ 9 fps YUY2`
full-frame mode is a receipt-qualification target, not a commissioned mode.
The camera remains unqualified until the received USB identity, sensor/lens/
case configuration, focus at the final working distance, persistent mode and
controls, usable field of view, distortion, fixed support, cable, lighting,
and calibration pass physical acceptance. This workflow opens no camera or
USB backend.

The default Waveshare upper-arm holder remains package inventory. The legacy
Waveshare IMX335-B binding is retained under the camera-architecture hold only
for historical provenance and a separately controlled optional Phase-2
eye-on-arm experiment.

The virtual route uses the locked pre-hardware rank-1 sensitivity overlay:

| Input | Locked virtual value |
| --- | ---: |
| Study input | `reach-944d7463f4c67905` |
| Rear clamp/base X | 385 mm |
| Rear edge to base-axis Y | 75 mm |
| Base yaw | -105 degrees |
| Base-link Z | 70.1 mm |
| Keyboard virtual tool | 120 mm |
| Phone virtual tool | 100 mm |
| Park probe in board frame | `(290, 10, 70)` mm |

These values are stored in
[`virtual_commissioning_profile.json`](../config/virtual_commissioning_profile.json)
and locked by the six-artifact simulation bundle. They are classified
`UNMEASURED_SENSITIVITY_OVERLAY`. They are not instructions for clamp placement,
tool fabrication, drilling, camera placement, or physical motion.

## Executed software chain

```text
strict runtime policy + active Freeze-011 manifest + six-artifact bundle
                              |
                              v
               fail-closed virtual-workcell bootstrap
                              |
          +-------------------+--------------------+
          |                                        |
          v                                        v
 semantic keyboard/phone plan          declared virtual calibration closure
          |                                        |
          +-------------------+--------------------+
                              v
       park -> transit -> hover -> observe -> approach -> contact -> retract
                              |
              fresh JPEG -> decoded tags -> board pose quality
                              |
                              v
             bounded sequential IK and waypoint correlation
                              |
                              v
       achieved tip XYZ + achieved normal + declared virtual dwell
                              |
                              v
       coordinate/depth/normal/dwell device contact truth -> ContactResult
                              |
                              v
       ContactResult-only output observer -> hash/length outcome check
                              |
                              v
                    return to park -> close -> evidence
```

At each physical action's hover endpoint, `observe` now renders a fresh fixed-
overview JPEG, independently detects tag36h11 pixels, emits a typed detection
batch, estimates the synthetic fixture transform
`camera_overview_optical_T_board`, and applies the synthetic pose-quality
policy before approach/contact. The processor sees no action or target;
association occurs only after processing. This fixed-view topology is aligned
with the selected static architecture, but its synthetic frame and calibration
are not the commissioned `C_overhead_optical`, and it is not converted into a
robot-frame correction. See [pixel vision simulation](PIXEL_VISION_SIMULATION.md).

The contact and output paths are more strongly split:
the session builds a `ContactEvent` from the accepted IK result's achieved
board-frame tool-tip position and hand-TCP axis, plus a fixed virtual dwell and
fault-controlled activation count. The virtual device receives no planned
target identifier or expected character. It independently resolves polygon
membership, contact depth, normal angle, dwell, focus, and Android UI state to
a `ContactResult`. A separate observer receives only those immutable results,
consumes each once, and accumulates the in-memory output whose hash and length
are compared with the request.

The implementation is split deliberately:

| Concern | Source |
| --- | --- |
| Strict startup and source revalidation | [`application/bootstrap.py`](../src/rocell/application/bootstrap.py) |
| Locked sensitivity profile decoder | [`simulation/virtual_profile.py`](../src/rocell/simulation/virtual_profile.py) |
| Semantic keyboard/phone compilers | [`typing/`](../src/rocell/typing/) |
| Action-indexed Cartesian/joint trajectory | [`application/trajectory_simulation.py`](../src/rocell/application/trajectory_simulation.py) |
| Explicit virtual calibration substitutes | [`application/virtual_calibrations.py`](../src/rocell/application/virtual_calibrations.py) |
| Hardware-neutral runtime contracts for clock, arm, observation, contact, outcome, cancellation, and evidence | [`application/runtime_ports.py`](../src/rocell/application/runtime_ports.py) |
| Virtual clock, faults, arm, geometry-driven contact truth, devices, and event ledger | [`simulation/virtual_workcell.py`](../src/rocell/simulation/virtual_workcell.py) |
| Independent, `ContactResult`-only virtual output observation | [`simulation/virtual_outcome.py`](../src/rocell/simulation/virtual_outcome.py) |
| Deterministic fixed-overview JPEG renderer | [`simulation/synthetic_raster.py`](../src/rocell/simulation/synthetic_raster.py) |
| Released tag36h11 codebook and independent bounded pixel detector | [`vision/apriltag_codebook.py`](../src/rocell/vision/apriltag_codebook.py), [`vision/pixel_detector.py`](../src/rocell/vision/pixel_detector.py) |
| Planar homography/pose estimator | [`vision/planar_pose_estimator.py`](../src/rocell/vision/planar_pose_estimator.py) |
| Immutable frame/detector/tag/pose/covariance boundary | [`vision/detections.py`](../src/rocell/vision/detections.py), [`vision/pose_estimation_records.py`](../src/rocell/vision/pose_estimation_records.py) |
| Plan-blind pixel processing, quality gate, and post-process attempt ledger | [`application/virtual_pixel_vision.py`](../src/rocell/application/virtual_pixel_vision.py) |
| End-to-end lifecycle and outcome verification | [`application/virtual_session.py`](../src/rocell/application/virtual_session.py) |
| Atomic records and full recomputation | [`evidence/virtual_session.py`](../src/rocell/evidence/virtual_session.py) |

No virtual component is accepted by the physical permit boundary. The virtual
arm consumes five-joint states already accepted by the trajectory diagnostic;
it never derives or serializes a T=104 request. This is important because the
physical relationship between the vendor URDF and firmware `R_ctrl` frame is
not commissioned.

`runtime_ports.py` is a structural application boundary, not the current
session implementation. It defines immutable request/result envelopes,
structural protocols, deadlines/cancellation, authority declarations, and a
fail-closed complete-bundle validator. The current virtual session has not yet
been refactored to execute through a `MissionRuntimePorts` bundle, and no live
or replay adapter is certified by that contract.

The standalone fixed-overview chain now produces the typed vision boundary from
real JPEG bytes. Records bind a `FramePacket` identity, JPEG/settings hashes,
source and host timing, detector/estimator identities and configurations,
marked-tag canonical `TL, TR, BR, BL` corners, inlier masks/residuals, an
explicit-frame pose, a finite symmetric 6x6 diagnostic covariance, and
intrinsics/tag-map/implementation hashes. The estimator accounts for the
explicit tag-plane height when reporting the board origin. These records have
zero physical authority. The virtual session now consumes them through a
fixed-overview gate, stores a sealed redacted attempt ledger, and recomputes it
during replay; it never treats them as eye-on-arm or physical evidence.

## Startup behavior

Run the full bootstrap before debugging a mission:

```powershell
$env:PYTHONPATH = (Resolve-Path software/src)
python -m rocell bootstrap-sim --json
python -m rocell doctor --mode sim --json
```

Startup performs the following read-only checks:

1. Loads the exact simulation-only runtime policy and rejects unknown fields,
   duplicate JSON keys, nonfinite values, path escape, hardware enablement, or
   weakened retry/fallback rules.
2. Imports the complete RC03 snapshot and six-artifact bundle, then verifies
   every bound file hash.
3. Recomputes placemat alignment and confirms scene source bytes match the
   snapshot pins.
4. Confirms the stored capability projection exactly matches capabilities
   derived from the build state.
5. Verifies the calibration manifest and content-addressed registry inventory.
   Missing physical calibration families are declared gaps, not silently
   converted to PASS.
6. Parses the RoArm-M3 Pro connection profile without importing or opening a
   serial backend.
7. Checks the fixed synthetic overview fixture can project all six locked tags.
   Bootstrap still uses the cheap analytic projection check. The mission later
   requires the JPEG detector/pose gate at every action hover. Neither path
   opens the purchased B0477 or proves its installed static extrinsic.
8. Audits the 19-body collision contract and reports the currently missing or
   unknown geometry.

The expected status is `READY_SIMULATION_ONLY_WITH_DECLARED_GAPS`. The gaps are
essential: physical calibration, full collision geometry, and physical release
remain incomplete.

## Run a virtual typing or tapping mission

The CLI accepts text and a device only. It intentionally exposes no placement,
joint, Cartesian, tool-length, speed, or contact-force controls.

```powershell
python -m rocell simulate-session --device keyboard --text "test" --require-pass --json
python -m rocell simulate-session --device phone --text "test." --require-pass --json
```

The current golden runs demonstrate:

| Mission | Result |
| --- | --- |
| Keyboard `test` | 48 accepted virtual joint waypoints, four fresh six-tag pixel/pose passes, four geometry-resolved virtual contacts, `ContactResult`-observed output hash/length match, final park confirmed, plant closed |
| Android `test.` | 61 accepted virtual joint waypoints, initial `KEYBOARD_LOWER` state verified, five fresh six-tag pixel/pose passes, five geometry-resolved virtual taps, `ContactResult`-observed output hash/length match, final park confirmed, plant closed |

Repeated targets retain their original action index through geometric steps,
densified Cartesian waypoints, joint results, and contact events. A route for
`aa`, for example, records two distinct action occurrences even though both use
the target `keyboard:A`.

The virtual keyboard and Android plants retain their produced text internally
only while the run is active. Contact resolution is driven by the achieved IK
pose, not by an expected-character argument. The independent observer likewise
retains only the output emitted by `ContactResult` records. Reports serialize
the expected/observed SHA-256, Unicode-code-point length, focus/UI state,
contact/result counts, and model-definition hashes; there is no raw output
field. Semantic target names remain visible in the action/trajectory evidence
so a failing action can be diagnosed, but they are not supplied to the virtual
device's hit test.

## Fault injection

Declarative fault profiles exercise fail-stop behavior without monkey-patching
the planner or using a hardware adapter:

```powershell
python -m rocell simulate-session --device keyboard --text "a" `
  --fault-profile contact-missed --json
python -m rocell simulate-session --device phone --text "a" `
  --fault-profile phone-wrong-ui --json
```

The declarative fault scripts cover arm connection/reference/stall, camera
unavailable, pixel-level tag loss, missed contact, keyboard double contact,
Android UI drift, and device focus loss; the CLI exposes the bounded public
subset listed by `--help`. Camera unavailable produces no frame. Tag loss occludes
world IDs 0-3 in the rendered image; the detector still finds held-out IDs 4-5,
then the pose stage fails its four-tag minimum. Component tests additionally
cover malformed/blank images, Hamming and margin rejection, resource ceilings,
pose degeneracy/outliers, and ambiguous consensus. A trigger is immutable,
selector-bound, consumed at most once, and recorded in the event ledger.
Session v1 permits one injected fault because it has no retry/recovery path.

After a fault there is no contact retry, pose retry, camera-backend fallback,
or automatic resume. The virtual arm transitions to `FAULT`, closes, and the
hash/length mismatch remains visible.

## Record and replay

Record a successful session under the runtime's `software/runs` root:

```powershell
python -m rocell simulate-session --device keyboard --text "test" `
  --record --require-pass --json
```

The immutable record directory contains:

- `action-plan.json`;
- `scenario.json`;
- `trajectory.json`;
- `events.json`;
- `vision.json`;
- `report.json`; and
- `manifest.json`, written last.

Current records use manifest schema v2 and session-report schema v3. The vision
artifact contains no JPEG bytes, but binds their hash, freshness, renderer,
detector, detections, pose, quality, and post-process action association. The
verifier strictly reconstructs every nested typed record and redundant hash.
Schema-v2 pre-pixel reports remain byte-verifiable history, while replay with
current software is expected to diverge until a new record is created.

Each artifact has a role, exact byte count, and SHA-256 in the manifest. Record
finalization uses an exclusive temporary directory followed by an atomic
rename. Existing record IDs are never overwritten. Loading rejects extra or
missing files, duplicate keys, nonfinite values, oversized artifacts, path
traversal, checksum drift, mismatched split artifacts, and incomplete
manifests.

Replay verifies the package, reconstructs and recompiles the semantic request,
reloads the current locked sources, reruns the canonical planner and virtual
executor, and compares the complete report:

```powershell
python -m rocell replay-session `
  --manifest software/runs/virtual-<report-prefix>/manifest.json `
  --require-identical --json
```

`REPLAY_IDENTICAL` means the recomputed report matched. It is stronger than
trusting a stored PASS, but it remains software evidence only. Source changes
are expected to change implementation/source hashes and make an old run diverge
until intentionally migrated or rerun.

The record omits a direct plaintext field and the virtual device serializes
only output hash and length. It is nevertheless **redacted, not confidential**:
`action-plan.json` retains the ordered semantic key/tap targets so deterministic
replay can reconstruct the request. Protect or delete run directories according
to the sensitivity of the typed content; this format is not encryption.

## What a virtual PASS means

A completed session currently means all of the following:

- locked startup sources were coherent;
- the requested characters compiled through the frozen semantic profile;
- every required physical calibration dependency had an explicit virtual
  substitute and remained separately listed as a physical blocker;
- nominal tool-tip path checks passed;
- every densified waypoint received an accepted bounded IK result;
- action, target, phase, waypoint, and result identities stayed correlated;
- the virtual arm lifecycle and command sequence were valid;
- each physical action had a fresh independently decoded fixed-overview frame,
  all world and held-out tags required by the synthetic policy were inliers,
  and reprojection/fixture-pose residuals passed before approach;
- each contact endpoint's achieved IK tool-tip position and hand-TCP axis were
  converted into board-frame position/contact-normal data with the declared
  virtual dwell and activation count;
- the virtual device independently resolved those values against its immutable
  region, depth, normal, dwell, focus, and UI-state model;
- the session confirmed the resolved region matched the semantic action, while
  the separate observer consumed only `ContactResult` records;
- the observer-derived output hash and length matched the request;
- the route finished at the locked virtual park; and
- the arm and ledger closed with zero hardware commands.

It does not mean any of the following:

- the 385/75 mm, -105 degree placement or 120/100 mm tools are measured or
  mechanically allowed;
- the received arm's joint zeros/signs, controller firmware, or `R_ctrl` frame
  match the URDF;
- the B0477 received identity, delivered lens/case, persistent native mode,
  intrinsics, support, fixed cable/lighting, or static
  `Wv_T_C_overhead_optical` is commissioned;
- the fixed-overview fixture pose is a physical `C_overhead_optical_T_B` or
  produced a robot-frame correction (the detector and estimator did run and
  are recorded, but only as synthetic fixture evidence);
- robot links, self-collision, clamp, static support, camera, connector, cable,
  tools, devices, and fixtures have complete accepted collision geometry;
- interpolation between sampled waypoints is collision-free or dynamically
  feasible;
- physical singularity/manipulability, payload, gravity, velocity,
  acceleration, compliance, force, travel, or touchscreen/keystroke activation
  is safe;
- the achieved IK pose equals a physical feedback pose or contact measurement;
- the nominal contact polygons, surface heights, depth/normal/dwell thresholds,
  activation count, output map, focus, or Android state model are measured;
- the `ContactResult`-only virtual observer is independent of the virtual
  contact model in the physical-sensor sense, or that a keyboard/OS or
  Android/ADB observer verified an outcome;
- the structural `runtime_ports.py` contract is the active session execution
  path or has a commissioned physical adapter; or
- robot power, empty-cell motion, keyboard contact, or phone contact is
  authorized.

## Physical-hardware handoff

When parts arrive, keep this virtual pipeline and replace idealized boundaries
in controlled stages:

1. Bind the exact Pro arm, controller, firmware, USB identity, joint reference,
   and power-on behavior.
2. Bind the exact received B0477 USB identity, sensor/lens/case configuration,
   driver, full-frame mode, pixel format, crop/orientation, exposure and image
   controls. Prove the chosen mode and controls persist after close/reopen and
   reboot; the published `5472 x 3648 @ 9 fps YUY2` mode is only the initial
   qualification target.
3. Build and qualify the rigid support and camera retention together with the
   fixed cable/strain relief and controlled lighting. Measure the installed
   working height and aim, add every support/camera/cable/light body to the
   collision model, and accept load, settling, bump, thermal, remove/reinstall,
   and support-witness drift tests.
4. Adapt and qualify the existing bounded JPEG/tag36h11/planar-pose path for the
   exact received camera and mode, or replace a stage with an independently
   validated implementation while preserving the typed boundary. Exercise
   physical image campaigns and bind frame, detection, fit, covariance, and
   source-hash records into session evidence without treating synthetic tests
   or schema validation as physical pose qualification.
5. Calibrate B0477 intrinsics/distortion at the exact locked lens, focus,
   aperture, resolution, crop, orientation, and controls. Measure the installed
   board tag map and solve the constant `Wv_T_C_overhead_optical`, retaining
   varied training data and independent held-out residuals.
6. At startup and before every descent, require a uniquely fresh
   `C_overhead_optical_T_B`: T0–T3 fit the pose, K0/P0 remain held-out, and the
   expected keyboard or phone must be present, seated, oriented, and consistent
   with its target map. Verify the support witness and reject stale frames,
   settings drift, board/device movement, tag loss, or primary-camera loss.
7. Correlate `R_ctrl` independently over the usable robot range; never alias it
   to `Wv`, `base_link`, or a camera-derived board pose.
8. Measure keyboard/phone poses and target regions, route TCP/compliance, press
   or tap travel, normal/depth/dwell limits, and activation behavior. Replace
   achieved IK truth with qualified arm/contact feedback. Use the keyed puck to
   validate TCP, approach axis, Z, and travel across both device regions.
9. Implement keyboard/OS and Android/ADB outcome observers that do not consume
   virtual `ContactResult.resolved_output` as their measurement source.
10. Refactor the orchestrator to consume validated `MissionRuntimePorts` and add
   virtual/replay adapters first. Admit physical adapters only behind the
   separate capability, permit, cancellation, deadline, and evidence gates.
11. Complete full-body/static-support/camera/cable/lighting collision geometry,
   held-out keyboard and phone route acceptance, uncertainty/clearance policy,
   physical singularity/dynamics checks, E-stop, gravity-safe containment,
   anti-shift controls, and the local contact guard.
12. Introduce feedback-only hardware-in-loop tests, then separately gated
   empty-cell motion. Contact remains a later capability.

An IMX335 on the bundled arm holder may be evaluated later only through a
separate Phase-2 qualification of its carrier transform, hand-eye calibration,
exposure/joint synchronization, payload, moving cable, collision, and local
visibility. It cannot substitute automatically for a failed Phase-1 camera or
close a Phase-1 acceptance gate.

The virtual record/replay suite should remain the regression layer around every
one of those substitutions.
