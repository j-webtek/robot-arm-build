# Arducam B0477 static-overhead integration

This is the software handoff for the purchased Arducam USB 3.0 20 MP camera
package with the included nominal 16 mm manual C-mount lens and metal case. The
catalog configuration is treated as Arducam `B0477`, Sony `IMX283`.

The camera is the Phase-1 **static overhead** source. It is not carried by the
RoArm and it does not connect to the RoArm ESP32. The host computer connects to
the camera over a dedicated USB 3 data path; the arm remains a separate,
independently gated control connection.

Purchase confirmation selects the catalog profile. It does not prove which
unit was received, its serial number, its delivered lens/mount, one-metre
focus, USB modes, calibration, installation, or suitability. Every physical
field therefore remains open and robot power, motion, descent, and contact
remain blocked.

## Controlled design point

- Board frame `B`: origin at the front-left of the placemat top surface, `+X`
  right, `+Y` rear/toward the arm, and `+Z` up.
- Camera entrance-pupil screening point: `B=(305, 228.5, 1000) mm`.
- Camera optical axis: nominally perpendicular to the board along board `-Z`.
- Sensor long axis: parallel to board `+X`.
- Qualification height range: `950..1050 mm` after the received hardware is
  measured.
- Provisional lowest overhead-hardware plane inside the robot work area:
  `Z=920 mm`; this is a screening value, not collision clearance approval.
- Required screened view: `670 x 517 mm`, providing a nominal 30 mm margin
  around the `610 x 457 mm` board.

The support is a bench-anchored, rear-open metal portal sharing a repeatable
datum with the placemat. It must not rely on printed feet on the plywood. Use a
positive-retention, antirotation camera cage and a safety tether; derive its
final dimensions from the received enclosure and official STEP model.

## Camera modes used by the software

Two intentionally different modes are represented:

| Use | Mode | Meaning |
|---|---|---|
| Intended physical precision capture | `5472 x 3648`, YUY2, up to 9 fps, USB 3 | Manufacturer-published target; must be observed and repeated on the received unit |
| Bounded synthetic raster | `2736 x 1824` | Exact half-scale/aspect proxy in `C_overhead_optical`; it preserves the published 49-degree H / 38-degree V values as provenance but uses a square-pixel, aspect-consistent 49-degree H / 33.799-degree V rectilinear model |

The advertised 120 fps mode is `1280 x 720`; it is not the planned precision
mode. The published 49-degree horizontal and 38-degree vertical values cannot
both describe a centered, square-pixel rectilinear projection at 3:2 aspect
ratio. The synthetic contract therefore records both catalog values, derives
the effective vertical angle from the horizontal angle and image aspect, and
uses equal `fx`/`fy`. It also applies a modest nonzero Brown-Conrady stress warp
to capture pixels and analytically maps detected corners into the named
`UNDISTORTED_PINHOLE_PIXELS` estimator space. Those coefficients and that map
are deterministic test fixtures, not measurements of the delivered lens.

## Current software boundaries

`software/config/camera_profiles/arducam_b0477_imx283_16mm.json`

: Exact purchase-time catalog profile, published modes, synthetic projection,
  provenance, null received/USB/calibration observations, and zero authority.

`rocell.vision.camera_profile`

: Strict bounded parser with duplicate/unknown-field rejection, semantic and
  source-byte hashes, typed published modes, and derived nominal proxy
  intrinsics.

`rocell.vision.camera_commissioning`

: Zero-hardware rehearsal of the future identity/mode/control/reopen gates. Its
  accepted device identity must use the `synthetic://` namespace and its result
  is permanently `commissioned=false`.

`rocell.vision.uvc_inventory`

: Provider-neutral contract for bounded UVC enumeration, persistent selection,
  exact mode/bus negotiation, manual-control readback, and reopen stability. A
  deterministic fake provider exercises the boundary before delivery without
  importing an OS backend, enumerating a USB device, or treating a numeric
  camera index as identity.

`rocell.calibration.static_camera_intrinsics`

: Sealed synthetic ChArUco intrinsics-artifact contract. The committed fixture
  binds the purchase profile, exact native capture mode, synthetic persistent
  UVC identity and settings hashes, focus/aperture/control evidence placeholders,
  target definition, print-scale evidence, every input-image hash, a
  precommitted 24-training/8-held-out split, solution/crop/residuals, and the
  undistortion-map hash. It cannot produce a valid physical calibration.

`rocell.application.b0477_optical_contract`

: One canonical synthetic projection shared by the B0477 renderer, detector
  boundary, pose estimator, and virtual-acceptance preflight. It pins
  `C_overhead_optical`, the capture and estimator pixel-space names, equal
  focal lengths, published/effective FOV values, nonzero stress-distortion
  coefficients, inverse-map algorithm, iteration/tolerance settings, and the
  content hashes of the optical contract and analytic undistortion map. Any
  frame, focal, FOV, distortion, map, or support-source drift fails closed.

`rocell.vision.usb_opencv`

: Explicit USB/OpenCV capture adapter. It now requests a configured FOURCC and
  reads back width, height, frame rate, and FOURCC before accepting the source.
  Linux `YUYV` is normalized only as the defined equivalent of vendor `YUY2`.
  A production instance must require a separately observed persistent identity;
  a numeric camera index is never sufficient identity evidence.

`rocell.workcell.static_camera_support`

: Strict support/coverage validator. It pins the architecture plan, B0477
  purchase profile, board layout, and robot screening inputs by exact SHA-256.
  It cannot release cut lengths, fabrication, installation, or robot use.

`rocell.application.b0477_static_vision`

: Production-shaped, hardware-free static-view rehearsal. It reloads and
  cross-checks the profile/support source hashes, renders the six-tag placemat
  through the canonical distorted capture model at the nominal one-metre
  geometry, passes only JPEG bytes to the pixel detector, rectifies the
  detected corners, and then performs planar pose estimation. Its normal and
  tag-loss modes test success and natural fail-closed behavior without OpenCV
  or a device.

`rocell.application.b0477_sensor_session`

: Zero-authority bridge from the B0477 pixel rehearsal to the immutable raw
  sensor-session v2 package. It exposes a backward-compatible companion capture
  containing the exact detector-input JPEG, raw and rectified detection
  batches, optical contract, and pose record. The bridge constructs an exact
  `2736 x 1824` packed YUY2 buffer (`9,980,928` bytes), RGB8 decoded and
  rectified buffers (`14,971,392` bytes each), bounded base64 chunks for the
  original JPEG, explicit pixel layouts/strides, and hash-bound rectifier,
  detector, pose, calibration, timing, and source provenance. The pixel-layout
  contract also fixes YUY2 color primaries, transfer function, matrix,
  quantization range, 4:2:2 chroma siting, and top-left row origin, plus the
  corresponding full-range sRGB interpretation of derived RGB8 buffers. Both
  normal and tag-loss results can be recorded, verified, and replayed. Its
  B0477-specific replay wrapper exact-compares every stored/applied contract,
  identity, mode, control, timing, calibration, JSON record, blob, and manifest
  field against the source session; a generic self-consistent package cannot be
  substituted and called a source-bound B0477 replay. Its only protocol
  fixture is one **unsent** T=105 line paired with a synthetic T=1051 line; it
  has no T=104 or physical adapter.

`rocell.evidence.sensor_session`

: Generic manifest-last v2 evidence store. It rejects wrong file sets,
  noncanonical JSON, symlinks, byte/hash drift, wrong YUY2/RGB8 dimensions or
  strides, stale capture-to-perception timing, excessive stage/session duration,
  feedback-buffer/latency faults, and a replay policy weaker than the recorded
  contract. Replay receipts disclose and hash both stored and applied policies,
  and verified/replayed result types can be constructed only by their strict
  factories. This generic layer proves package integrity and declared bindings,
  not independent perception truth. It does not yet independently rerun the
  decoder, undistorter, tag detector, pose estimator, or calibration solver.

`rocell.application.b0477_stack_coherence`

: Application-level cross-check across the profile, support, commissioning,
  UVC inventory, and intrinsics contracts. It rejects profile/source/mode,
  synthetic persistent-identity, capture-settings, geometry, or authority
  disagreement. The CLI includes the normal and tag-loss pixel reports by
  default so a single report proves that the independent rehearsal artifacts
  still describe one internally coherent synthetic stack.

The checked-in Freeze 009 camera manifest and simulation hardware profile still
record the older historical eye-on-arm choice. They are not silently rewritten.
The additive B0477 contracts and tests are the input to a later reviewed,
superseding freeze.

## Commands available before delivery

From `software/`:

```powershell
$env:PYTHONPATH = (Resolve-Path src)

# Validate and display the exact purchase-time profile; no camera is opened.
python -m rocell --workspace .. camera-profile --json

# Exercise synthetic persistent identity, native mode, manual controls, and
# two identical close/reopen observations; no camera is enumerated or opened.
python -m rocell --workspace .. rehearse-camera-commissioning --json

# Exercise the provider-neutral UVC inventory seam with the deterministic fake
# provider. Require every identity/mode/bus/control/reopen gate to pass.
python -m rocell --workspace .. rehearse-b0477-uvc-inventory --require-pass --json

# Validate the sealed 32-view synthetic ChArUco contract (24 training and 8
# held out), including its UVC identity/settings and content-hash bindings.
python -m rocell --workspace .. rehearse-b0477-intrinsics --json

# Render the B0477-specific 2736x1824 proxy, decode all six tags from JPEG
# pixels, and estimate nominal static board pose.
python -m rocell --workspace .. simulate-b0477-vision --mode normal --require-expected --json

# Prove that loss of four registration tags naturally blocks pose estimation.
python -m rocell --workspace .. simulate-b0477-vision --mode tag-loss --require-expected --json

# Validate the source-locked static support and optical screen.
python tools\validate_static_camera_support.py --json

# Recommended complete B0477 gate. This also runs the normal and tag-loss JPEG
# pixel pair and requires all cross-artifact coherence checks to pass.
python -m rocell --workspace .. rehearse-b0477-stack --require-pass --json

# Faster development check: validate the five core artifacts without rendering
# the optional pixel pair. This does not replace the complete milestone gate.
python -m rocell --workspace .. rehearse-b0477-stack --skip-pixel-vision --require-pass --json

# Rehearse the complete 15-stage camera-first connection, calibration, RoArm
# power-on-observation, feedback-only, and noncontact handoff sequence.
python -m rocell --workspace .. rehearse-first-power-on --scenario nominal --require-expected --json
```

The raw B0477 evidence bridge is currently a library API so it cannot be
mistaken for a live acquisition command:

```python
from pathlib import Path
from rocell.application import record_and_replay_b0477_synthetic_sensor_session

evidence_root = Path("runs/b0477-sensor-fixtures")
evidence_root.mkdir(parents=True, exist_ok=True)
result = record_and_replay_b0477_synthetic_sensor_session(
    Path(".."), evidence_root, sequence=1
)
assert result.replay.status == "REPLAY_VERIFIED_SIMULATION_ONLY"
```

Use a new empty evidence root or a new sequence for each record. The recorder
does not overwrite an existing content-addressed package.

An accepted rehearsal means the software gate behaves correctly on controlled
fake input. It does not mean the delivered camera passed the gate.

The latest checked-in default full-stack rehearsal reports
`SYNTHETIC_B0477_STACK_COHERENT`: 10/10 coherence checks pass, the normal image
accepts all six tags, and the deliberately occluded image naturally rejects
with only tags 4 and 5 detected. Its report simultaneously records zero camera
frames requested, zero arm-motion commands, zero contact commands, and false
hardware-presence, live-capture, physical-calibration, physical-extrinsic,
motion, and contact authority. This is regression status, not workcell status.

## Synthetic gates versus physical acceptance

Keep these two evidence classes separate:

| Evidence | What it can establish now | What must replace it after delivery |
|---|---|---|
| Fake UVC inventory and commissioning fixtures | Parser, provider, selection, exact-tuple, control, reopen, and fail-closed logic | Observed VID/PID/serial/persistent path, enumerated modes, negotiated USB bus, actual readbacks, reconnect/reboot stability, and fresh-frame behavior |
| 32-view synthetic ChArUco fixture | Hash sealing, 24/8 split enforcement, coverage/resource checks, solution/crop/map schema, and held-out gate logic | Images from the received unit at its final locked lens, mode, controls, support pose, lighting, and temperature; measured target scale; a separately reviewed physical threshold policy |
| Nominal B0477 pixel pair | JPEG decode, nonzero synthetic capture distortion, hash-bound corner rectification, six-tag planar-pose success, and natural tag-loss rejection under simulated geometry | Recorded installed-camera campaigns covering measured distortion, glare, occlusion, blur, exposure, timing/freshness, support disturbance, and route-specific visibility |
| Stack coherence report | All synthetic artifacts bind the same profile, mode, identity/settings hashes, and support assumptions | Receipt inspection, physical calibration/extrinsic, collision and structural qualification, staged commissioning, and a superseding controlled freeze |

The rehearsal thresholds—including the ChArUco corner/coverage requirements and
pixel residual limits—are deliberately labeled synthetic. They are useful for
testing code behavior but are **not** provisional physical pass criteria. The
physical criteria must be approved before the real dataset is collected; do not
copy the fixture's values or numeric camera solution into a physical artifact.

The integrated [first-power-on onboarding guide](FIRST_POWER_ON_ONBOARDING.md)
places received-camera inspection before USB identity and keeps the RoArm off
through camera qualification. Its nominal status,
`SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED`, confirms only
that all 15 synthetic stages ran in order. Stage 2 consumes the normal/tag-loss
pixel pair as part of the coherent B0477 stack. The freshness stage requires an
advancing synthetic capture sequence and a distinct raw-JPEG digest, while the
`camera-frame-rewrapped` case proves that new wrapper metadata cannot hide
repeated raw bytes. That synthetic oracle does not qualify physical buffering,
exposure timing, or freshness. Checkpoint resume binds the implementation and
transitive controlled inputs and reruns the exact stored prefix. The workflow
leaves Freeze 009 unchanged and does not authorize camera access, robot power,
motion, calibration promotion, or contact.

## Physical commissioning sequence once the camera arrives

Do these stages in order. A later stage may not fill in missing evidence from
an earlier one.

1. Receipt and mechanical identity

   - Photograph the unopened package, labels, camera, lens markings, cable,
     connectors, enclosure faces, and all included hardware.
   - Record manufacturer/model/serial labels and order evidence separately.
   - Measure case width/height/depth, mass, lens projection, entrance-pupil
     offset, mounting-hole/thread details, and usable fastener depth.
   - Resolve the catalog C-mount/CS-mount wording against the delivered unit.
   - Keep the carriage drawing unreleased until fasteners cannot bottom or load
     the focus/iris rings.

2. Host USB identity and mode inventory

   - Use a known USB 3 host port and a short qualified data cable first.
   - Record VID, PID, serial descriptor, persistent OS device path, driver, and
     negotiated bus speed. Do not accept camera index `0` as identity.
   - Enumerate all modes and controls without the arm powered.
   - Request `5472 x 3648 @ 9 fps YUY2`; read every value back.
   - Close/reopen twice, reconnect the cable, and reboot the host. Persistent
     identity, mode, and locked settings must remain stable.

3. Optical bench qualification

   - On an adjustable test fixture at the planned `950..1050 mm` distance,
     without arm power, prove the included 16 mm lens can reach board-wide
     focus and the selected height can provide the required FOV, orientation,
     throughput, and control range.
   - Treat this as feasibility only. Do not mechanically witness final focus or
     accept intrinsics from the temporary mounting, lighting, or cable stack.

4. Static installation and camera-to-board registration

   - Install the positively retained camera, tether, diffuse lighting, and
     strain-relieved USB cable on the common metal frame.
   - Warm the installed camera to its defined condition. Read back the final
     mode and controls; set, lock, and witness focus/aperture with the retained
     camera, light, and cable load in place.
   - Measure usable FOV, crop/orientation, distortion, vignetting/corner
     illumination, glare, blur, buffering, latency, and thermal drift. Capture
     the controlled ChArUco training/held-out set now, and solve installed
     intrinsics with source-image hashes, regional coverage, and held-out
     residuals. Never promote the nominal synthetic matrix.
   - Import/model the official RoArm, clamp, tools, camera, portal, lights,
     fasteners, and cable. Complete the software collision screen now, but do
     not call the physical geometry or startup sweep qualified yet.
   - Survey the six tag corners/planes and frame/robot-base witness fiducials.
   - Solve and independently validate only the installed static-camera/tag-map
     registration at this stage: fit T0-T3 and keep K0/P0 held out.
   - Validate camera removal/reseat, cable pull, bump, warm-up, settling, and
     24-hour drift behavior with held-out observations. Any changed mount,
     focus, lighting, cable load, mode, or controls invalidates intrinsics and
     registration. Controller correlation, TCP, and device maps occur only
     after the controlled arm connection.

5. RoArm identity while actuator power remains off

   - Record the exact RoArm-M3 Pro and controller labels, serial numbers,
     VID/PID/location/driver, persistent port identity, supply, and cable.
   - Verify that host configuration cannot auto-connect, auto-initialize,
     silently select another port, or blind-retry.
   - Bind the expected firmware package and approve a non-motion firmware
     readback method. Do not claim the installed revision or open the serial
     port at this stage.

6. Pre-power safety release

   - Remove the keyboard, phone, contact tool, and loose parts; keep the cell
     empty for the first power event.
   - Install the independent power-cut E-stop, passive gravity-safe
     containment, board/frame anti-shift controls, and exclusive command
     ownership. First verify the power-cut circuit with an electrically
     representative inert test load while the RoArm is disconnected; that
     electrical check does not prove mechanical stopping or gravity safety.
   - Clear the complete possible startup swept volume, including arm, gripper,
     attachments, camera portal, lights, fasteners, and cables. Position an
     observer at the E-stop. Missing or stale evidence stops the sequence here.

7. Observed physical power-on behavior

   - With no serial client connected and no host command issued, apply actuator
     power under direct observation and containment.
   - Record whether and how the arm moves, including any movement toward the
     factory middle state, swept path, settling, final pose, abnormal behavior,
     and controlled power-loss consequence.
   - If behavior is unknown, outside the cleared envelope, or unexpected, cut
     power and return to the safety/collision gate. Do not send a park command
     to compensate.

8. Controlled feedback-only connection and firmware readback

   - Only after the observed power-on behavior passes, explicitly open the one
     commissioned serial port at 115200 with RTS, DTR, and flow control inactive.
   - In the first physical session, issue exactly one bounded T=105 request with
     a fresh one-use permit only after proving the receive buffer is empty.
     Preserve raw T=105/T=1051 bytes and typed endpoint,
     six-joint, load, torque-switch, and voltage fields, then close without
     retry.
   - Use only the separately approved non-motion method to read and bind the
     installed firmware identity. Any reset banner, disconnect, timeout,
     malformed/incomplete reply, or unexpected movement ends the session.
   - The zero-hardware simulator deliberately uses two scripted
     open/query/close cycles in a hardware-incapable session to test framing,
     bounded exchange accounting, and receive-buffer freshness. T=1051 does
     not echo a host transaction ID. A fault case places a complete valid old
     reply in the input buffer and proves it is rejected before a second T=105
     write. The emulator mints no live feedback permit. This does not change
     the one-query limit for the first physical session, and it does not close
     the still-open physical buffering/timing qualification.

9. Reference, controller-frame, arm/board, TCP, and device calibration

   - Use separately reviewed, bounded empty-cell characterization sessions;
     never label the automatic power-on middle position as calibrated home.
   - Establish commissioned reference and safe-park procedures, joint
     order/sign/zero/range, controller-to-URDF correlation, installed
     arm-base/board transform, and route-specific TCP/compliance artifacts.
   - Build the keyboard target map and Android screen/UI map as separate
     dependency-bound artifacts, with independent held-out validation and
     explicit invalidation on any changed parent.
   - Rehearse the selected static-overhead graph as 15 distinct artifacts. The
     current software verifies both 12-artifact device closures and all 68
     parent/context staleness edges while leaving every artifact
     `NOMINAL_ONLY` and the physical registry blocked.
   - The settings and intrinsics artifacts directly bind the retained camera,
     support, lighting, cable/strain-relief, and witness stack. Any change to
     that installed optical stack requires new physical evidence.

10. Physical noncontact acceptance

   - Complete and approve the full arm/link/clamp/tool/cable/gantry collision
     geometry before treating any virtual route result as physical evidence.
   - Run released reduced-speed empty-cell programs first. Verify stop, power
     loss, safe park, tracking/settling, localization, and above-surface routes
     with devices removed.
   - Add one device at a time and validate noncontact hover/visibility only.
     No descent or contact is included in this gate.

11. Controlled physical handoff

   - Assemble the immutable evidence set and generate a reviewed superseding
     freeze without changing historical Freeze 009.
   - Release only the specifically reviewed capability. Motion review and
     contact review remain separate; onboarding completion never arms either.

12. Later, separate keyboard and phone contact releases

   - Qualify keyboard contact and Android contact independently, beginning with
     non-destructive dummy contacts and large targets.
   - For each released action use `observe while retracted -> localize/quality
     gate -> approach -> contact -> retract -> independently verify outcome`.
   - Require a fresh board/device observation before every autonomous descent.
     Treat tool occlusion as expected and never infer success from a commanded
     pose.
   - Advance from large targets to keyboard keys and a purpose-built large phone
     UI. Stock Android QWERTY remains conditional on the measured total error
     fitting within every target's safe region.

## Physical facts software cannot decide in advance

The repository deliberately cannot fill in the received serial number,
persistent USB path, actual controls/modes, one-metre focus, case fasteners,
intrinsics/distortion, installed extrinsics, glare/lighting behavior, collision
clearance, route visibility, TCP/contact behavior, or keyboard/Android outcome
accuracy. Those values require the delivered camera and completed workcell.

Until those artifacts exist and a superseding controlled freeze is reviewed:

- camera receipt is unverified;
- physical calibration is invalid;
- the arm must remain unpowered by this workflow;
- live motion and descent are unauthorized; and
- keyboard/phone contact is disabled.
