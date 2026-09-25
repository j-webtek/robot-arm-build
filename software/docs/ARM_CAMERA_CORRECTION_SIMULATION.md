# Arm-camera correction simulation

> **Camera architecture notice — 2026-09-05:** This moving-camera simulation
> now represents historical coverage and optional Phase 2 refinement, not the
> Phase 1 runtime. Phase 1 selects the purchased Arducam B0477 with its included
> 16 mm lens on the source-locked nominal static support; receipt inspection,
> installed geometry, calibration, and qualification remain open. No arm-camera
> fallback is automatic, and these results retain zero physical authority.

## Purpose and current result

This is a retained hardware-free integration path for the optional Phase-2
architecture: the RoArm-M3-Pro carries a simulated camera on its bundled
upper-arm holder, observes the placemat tags from achieved joint state,
corrects the board registration when needed, replaces every not-yet-executed
joint command, and then simulates pressing a keyboard key or tapping an Android
target. The device contact is adjudicated from fresh achieved forward
kinematics against a private virtual board truth. The selected Phase-1 B0477
path is separate and static.

The path is implemented for keyboard and phone sessions. In the locked
simulation profile:

- an injected 12 mm board translation is recovered from rendered JPEG pixels,
  produces one `APPLY`, installs a fully re-solved suffix, then produces
  `NO_CHANGE` at the corrected hover;
- the old nominal keyboard contact misses, while the corrected achieved
  contact resolves to `keyboard:A`;
- an injected 8 mm translation similarly resolves `phone:key_a`, followed by
  a separate Android UI-state verification; and
- zero injected offset keeps revision zero and executes no replacement.

These are deterministic software regression results. The camera mount,
intrinsics, timing, controller correlation, contact mechanics, and collision
geometry are synthetic or incomplete. This path has exactly zero hardware
authority and cannot release any physical gate.

## Hardware/build alignment

The software runs within the active Freeze-011 RC03 context without modifying
it. This optional path deliberately consumes the legacy arm-camera fields that
Freeze 011 retains under `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`; it does not
reinterpret them as the selected static architecture. Its placemat geometry
and rank-1 unmeasured sensitivity profile remain unchanged
Freeze-005-derived inputs rather than newly generated Freeze-009 or Freeze-011
evidence. For this historical/optional fixture only:

- Waveshare RoArm-M3-Pro, not M3-S;
- the holder bundled with the standalone arm, mounted on the moving upper-arm
  structure;
- the Waveshare IMX335 5MP USB Camera (B), SKU 26719, is the historical
  Freeze-009 arm-camera geometric candidate, not the current Phase-1 camera;
- USB/UVC through the `usb_opencv` adapter when a received camera is eventually
  qualified; and
- the six existing RC03 tag36h11 markers as the board observations.

The arm controller's ESP32 is not a camera. An ESP HTTP/MJPEG source exists as
a separate adapter for a separately purchased ESP camera, but neither that
source nor the IMX335 route is selected for Phase 1. The selected Phase-1
camera is the static USB/UVC B0477.

The present synthetic camera uses a deliberately explicit, unmeasured fixture:

```text
link2_T_E.translation       = (200, 0, 0) mm
E_T_C_arm.translation       = (10, 0, 15) mm
combined link2-to-camera    = (210, 0, 15) mm before rotation effects
image                       = 1920 x 1080
fx, fy                      = 300, 300 px
cx, cy                      = 960, 540 px
```

Its optical rotation was screened to keep the RC03 tags visible across the
locked test route. None of those numbers is a fabrication instruction,
received-part measurement, physical intrinsic calibration, or permissible
mount tolerance.

## End-to-end architecture

```text
requested text
    |
    v
semantic keyboard/phone compiler
    |
    v
locked RC03 target map + nominal Cartesian intent
    |
    v
bounded nominal IK trajectory (registration revision 0)
    |
    v
zero-authority VirtualArmPlant executes to physical-action HOVER
    |
    +--> achieved sample before exposure
    |        + exposure timestamp
    +--> achieved sample after exposure
             |
             v
      achieved FK -> moving C_arm pose
             |
             v
 private board truth -> raster -> real JPEG bytes
             |
             v
 independent tag36h11 decoder -> planar C_arm_T_board estimate
             |
             v
 Wv_T_C_arm * C_arm_T_board -> candidate Wv_T_board
             |
             v
        REJECT / NO_CHANGE / APPLY
                         |
                         v
  reconstruct current tip from achieved joints in candidate board frame
                         |
                         v
 check correction legs -> re-solve every remaining Cartesian waypoint
                         |
                         v
 build complete accepted queue -> one atomic queue replacement
                         |
                         v
 execute corrected HOVER -> observe again -> require convergence
                         |
                         v
 execute CONTACT -> fresh achieved FK -> private truth board coordinates
                         |
                         v
 geometry-only keyboard/Android hit test -> ContactResult-only observer
                         |
                         v
 final PARK -> output hash/length check -> close virtual plant
```

The plan-blind vision processor receives a capture bracket and fault mode only.
It receives no action index, target name, expected tag corners, planner board
pose, or private truth transform. Semantic association happens after pixel
processing. The device model receives only achieved position, achieved normal,
dwell, and action occurrence; it does not receive the expected key or output.

## Frame and calibration contract

The arm-camera pose uses the reviewed six-joint achieved model vector and the
pinned RoArm URDF:

```text
Wv_T_C_arm(q) = Wv_T_link2(q) * link2_T_E * E_T_C_arm
```

- `Wv` is the vendor URDF root used by the virtual kinematic plant.
- `link2` is the moving URDF link to which the carrier is registered.
- `E` is the installation-specific carrier frame; it is not silently aliased
  to `link2`.
- `C_arm` is the camera optical frame.
- `board` is the RC03 placemat frame: front-left board-top origin, +X right,
  +Y rear/toward the arm, +Z up.

The pixel estimator reports `C_arm_T_board`. Composition yields a candidate:

```text
Wv_T_board(candidate) = Wv_T_C_arm(achieved) * C_arm_T_board(pixel estimate)
```

The correction decision compares this candidate with the active registration.
It checks timestamp quality, freshness, pose age, feedback bracketing, carrier
motion, inlier count, reprojection residual, translation, yaw, and tilt. It is
a pure decision: it cannot install a calibration or execute motion.

The IK solver historically names its root `world`. Correction code performs an
explicit frame-token relabel between `Wv` and that pinned URDF root; it never
equates `Wv` with controller frame `R_ctrl`. Controller-to-model correlation
remains a physical commissioning requirement.

## Capture and achieved-state boundary

Each observation requires two distinct achieved samples around exposure:

```text
settled_since <= before < exposure < after
```

Both samples must:

- use the arm-camera clock and one qualified tick period;
- be non-stale and from `VIRTUAL_PLANT` in this simulator;
- reference the same executed command sequence;
- contain the exact five arm joints plus the explicit gripper joint;
- lie inside the scenario's controller/URDF intersection; and
- remain within configured joint, camera-translation, camera-rotation,
  settling-time, and bracket-width limits.

The correction replanner accepts the complete typed achieved feedback sample,
not a bare joint mapping. It binds the sample ID, clock, timestamp, command
sequence, stale flag, source kind, complete joint vector, and source-state hash.
The achieved state may differ slightly from the requested hover, but its maximum
tracking error must remain within the source trajectory's adjacent-joint-step
policy. Current-tip FK and every new IK seed use those achieved values.

## Pixel boundary and private truth

The renderer uses the achieved moving camera pose and one
`HiddenVirtualBoardTruth`. That object exposes only:

- a content hash;
- a narrowly framed camera observation operation; and
- a narrowly framed achieved-contact projection operation.

It does not expose or serialize its transform. The same object is injected into
the raster camera and the independent contact projector, so both simulated
sensors see exactly the same plant. The correction planner never receives it.

Rendering produces actual JPEG bytes. Downstream detection receives the
`FramePacket`, not renderer geometry. The released tag36h11 decoder recovers
pixel corners, and planar estimator `rocell.planar_apriltag_homography` version
`1.1.0` (v1.1) consumes only those detections, synthetic intrinsics, and the
mapped board-tag geometry. After choosing a unique maximum-support consensus
mask, its bounded refit is monotonic: it can remove a newly exposed outlier but
cannot re-admit an excluded tag. Evidence cross-binds:

- before/after samples and synchronization policy;
- achieved camera FK;
- JPEG bytes, timing, settings, and freshness identity;
- detector result and frame identity;
- pose result and detection batch;
- quality metrics and the exact quality policy; and
- camera and contact views to the same private-truth hash.

Rejected pose candidates remain diagnostic records but cannot be obtained from
the pass-only `observed_Wv_T_board` accessor.

## Corrected suffix and atomic replacement

An `APPLY` decision invalidates every unexecuted joint solution made under the
old registration. The replanner therefore retains only Cartesian intent. It:

1. verifies the revision-zero nominal lineage and executed hover boundary;
2. validates the achieved virtual-plant sample and reconstructs the current
   tool tip with the pinned URDF and selected tool length;
3. requires that tip to remain safely above the semantic target and clear of
   unrelated obstacles;
4. checks an ascent to the correction plane, lateral move, and descent to the
   corrected hover;
5. densifies at the finest resolution allowed by the source trajectory policy;
6. re-solves the correction maneuver and every remaining approach/contact/
   retract/transit/park waypoint through the shared canonical IK gates; and
7. returns a passing suffix only if every waypoint is accepted.

The effective replacement cap is the minimum of the hard suffix cap, the
source policy's maximum waypoints per round, and its total IK-solve budget.
Building over that limit fails before solving or queue mutation.

The executor hashes the old queue and the complete accepted replacement first.
One queue assignment then discards the old suffix. No partial replacement or
old joint result can execute afterward.

Three identities remain intentionally separate:

| Identity | Meaning |
| --- | --- |
| `source_nominal_sequence` | Original Cartesian intent; refined points may share it |
| `execution_sequence` | Unique, contiguous virtual command occurrence |
| `trajectory_revision` | Board registration under which the joint solution was made |

The corrected hover is observed again. The current simulation allows at most
one installed correction revision; a second `APPLY` fails closed rather than
iterating indefinitely.

## Contact and outcome independence

At a contact endpoint, a new achieved sample is projected through the pinned
URDF and the tool transform:

```text
Wv_T_tip = Wv_T_hand_tcp(achieved q) * hand_tcp_T_tip
truth_board_T_tip = truth_Wv_T_board^-1 * Wv_T_tip
```

The projector rejects stale/non-virtual feedback, wrong joint order, and any
arm or gripper value outside the controller/URDF intersection. It has no
planner-coordinate parameter. Its board point and tool axis feed the existing
keyboard or Android region/depth/normal/dwell model. A separate observer sees
only the resulting `ContactResult` and verifies final output by hash and length.

This separation is why the 12 mm test is meaningful: the old nominal IK contact
resolves `OUTSIDE_REGION`, while the pixel-derived corrected contact resolves
`keyboard:A` against the same hidden plant.

## Primary implementation files

| Responsibility | Module |
| --- | --- |
| Achieved six-joint FK to moving camera | `application/arm_camera_pose.py` |
| Opaque shared plant registration | `application/virtual_board_truth.py` |
| Joint-dependent raster/perception service | `application/virtual_arm_camera.py` |
| Pure correction decision and gates | `application/board_pose_correction.py` |
| Re-solved bounded trajectory suffix | `application/corrected_trajectory_suffix.py` |
| Achieved FK to truth-frame contact | `application/actual_contact_geometry.py` |
| End-to-end keyboard/Android runner | `application/adaptive_virtual_session.py` |
| Full 75-target adaptive coverage | `application/adaptive_mission_coverage.py` |
| Seeded signed/boundary stress campaign | `application/adaptive_perturbation_campaign.py` |
| Generic zero-authority port rehearsal | `application/runtime_rehearsal.py` |
| JPEG renderer and perturbations | `simulation/synthetic_raster.py` |
| Tag decoder and planar estimator | `vision/pixel_detector.py`, `vision/planar_pose_estimator.py` |

The legacy report-v3 `simulate-session` path remains unchanged for replay
compatibility. The adaptive runner uses its own
`rocell.adaptive_arm_camera_session.v1` report schema.

The exhaustive services bind explicit policies around the same estimator. The
full 75-target coverage screen allows the measured synthetic quantization
envelope of 2.5 mm translation, 0.5 degree yaw/tilt, and 5 px maximum inlier
RMSE. The perturbation campaign deliberately retains the stricter 1.5 mm,
0.25 degree, and 3 px policy. Both cap each single-target adaptive route at 128
executed virtual waypoints. On 2026-09-04, estimator v1.1 accepted 75/75
full-catalog sessions with report SHA-256
`232dcdd5c7bb6cb7afb6e4dcac6001797991faa54587dd7e0979e67880d8d4e2`.
The same day's estimator-v1.1 perturbation rerun passed all 20/20 declared
outcomes, including four expected safe rejections, with report SHA-256
`9dda1bc28015ee6943d0e5017e16756dd30c6d0530d950a818161c28aa15dd20`.
These are synthetic regression settings and results, not physical tolerances
or authority.

## Running it without hardware

The CLI runs the complete locked rehearsal. Hidden-truth controls affect only
the synthetic plant and the output intentionally redacts the transform:

```powershell
rocell simulate-adaptive-session `
  --device keyboard `
  --text "a" `
  --truth-offset-x-mm 12 `
  --require-pass `
  --json

rocell stress-adaptive-session --seed 20260903 --generated-cases 8 --require-pass --json
rocell screen-adaptive-mission-routes --require-all --json

rocell simulate-adaptive-session `
  --device phone `
  --text "a" `
  --truth-offset-x-mm 8 `
  --require-pass `
  --json
```

Optional simulation-only controls are `--truth-offset-x-mm`,
`--truth-offset-y-mm`, `--truth-offset-z-mm`, and `--truth-yaw-deg`.
Non-finite values fail at argument parsing. `--require-pass` returns nonzero if
vision, correction, contact, independent output, or final park fails.

The Python entry point uses the locked build/profile and allows an explicitly
synthetic hidden board offset:

```python
from pathlib import Path

from rocell.application import run_default_adaptive_virtual_session
from rocell.geometry import Vec3

report = run_default_adaptive_virtual_session(
    Path(r"C:\path\to\robot-arm-build"),
    "keyboard",
    "a",
    truth_translation_Wv_mm=Vec3(12.0, 0.0, 0.0),
)

assert report.pipeline_completed
assert report.correction_installations[0].suffix.passed
assert report.contact_attempts[0].accepted
```

Focused verification from `software/`:

```powershell
python -m pytest `
  tests/unit/test_arm_camera_pose.py `
  tests/unit/test_virtual_arm_camera.py `
  tests/unit/test_board_pose_correction.py `
  tests/unit/test_corrected_trajectory_suffix.py `
  tests/unit/test_actual_contact_geometry.py `
  tests/unit/test_adaptive_virtual_session.py -q
```

## Faults and bounded behavior

The current tests cover normal, camera-unavailable, tag-loss, excess-blur,
excess-noise, unqualified-timestamp, stale-frame, source-kind, bracket-order,
duplicate bracket, out-of-controller-range, quality rejection, invalid
correction lineage, unsafe correction start, resource exhaustion,
correction-iteration limit, nominal-suffix discard, truth-derived miss/hit,
Android state, output mismatch, and final-park behavior. All six pixel/timing
faults also run through an immutable adaptive fault schedule and must be
consumed once, stop before contact, and close the plant. Multi-character
keyboard `aa`/`test` and Android `test.` tests retain occurrence identity after
one corrected suffix replaces the old queue.

The general adaptive-session hard ceilings currently include:

- a constructor-level absolute ceiling of 512 executions, while every
  full-catalog or perturbation single-target route selects the tighter
  128-execution ceiling;
- 32 arm-camera captures;
- one installed correction revision; and
- the tighter source trajectory waypoint/IK budgets for each replacement.

The synthetic renderer also bounds image size, encoded bytes, components,
candidates, blur kernel, noise, and detector/estimator work.

## What remains before physical use

No physical command path should be added around the simulator by merely
swapping an address or port. The following inputs and gates must first replace
their synthetic counterparts with measured, versioned evidence:

1. received camera identity, firmware/mode, lens, focus, exposure, resolution,
   distortion, and ChArUco intrinsics;
2. installed holder rail position, `link2_T_E`, `E_T_C_arm`, fastener witness
   marks, cable state, and repeated eye-on-arm held-out residuals;
3. qualified exposure timestamp and feedback-clock correlation;
4. measured tag corners and optical Z, station/device transforms, keyboard key
   regions, phone screen plane, UI version/state, and installed tool TCP;
5. controller `R_ctrl` to the pinned model joint/frame convention, including
   reference offsets, signs, limits, tracking error, timeouts, and firmware;
6. complete arm/base/clamp/holder/camera/connector/cable/tool collision geometry
   plus continuous swept-route checks;
7. payload, gravity, speed, acceleration, compliance travel, contact force,
   missed-contact, stuck-contact, and watchdog characterization;
8. independent E-stop/power removal and gravity-safe collapse/support tests;
9. real computer and Android outcome observers that cannot receive expected
   output as an oracle; and
10. staged no-tool, soft-target, keyboard, large-phone-target, fixed-keypad,
    and only then stock-phone-keyboard acceptance trials.

Until those close, `safe_to_power_robot` remains false, contact remains
disabled, and every adaptive report retains its physical/model hold list.

## Next software improvements while hardware is unavailable

The all-75 adaptive sweep, signed/boundary and seeded board-pose campaign,
moving-camera fault schedules, multi-action queue/revision checks, independent
FK oracle, protocol emulator, and generic mission-through-ports rehearsal are
now implemented. The remaining bounded work is:

1. persist and strictly replay adaptive *session* evidence, including exact
   JPEG sidecars, queue-installation proofs, and recomputation from locked
   inputs (aggregate qualification evidence already has its own strict schema);
2. extend seeded matrices beyond board pose to mount/intrinsic/tag placement,
   exposure-to-joint timing, tracking distributions, and visibility;
3. apply the emulator's deterministic nonzero achieved deviation to a
   geometry-aware adapter once controller/URDF units and joints can be stated
   without inventing hardware truth;
4. refactor the full adaptive geometry state machine through the validated
   `MissionRuntimePorts` seam; the current generic rehearsal proves the seam
   and cleanup contract but is not a physical adapter; and
5. implement recorded-camera and recorded-controller adapters before live
   adapters, enabling repeatable hardware-data replay with the arm unpowered.

Those improvements raise confidence in orchestration and failure handling. They
still cannot substitute for the physical measurements and safety evidence
listed above.
