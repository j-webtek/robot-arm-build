# Pre-hardware layout sensitivity and mission-route coverage

> **Active Freeze 011 camera architecture:** Phase 1 registration uses the
> purchased Arducam B0477/IMX283 USB 3.0 camera with its delivered nominal
> 16 mm C-mount lens on a rigid static overhead eye-to-hand support. This route
> study remains camera-hardware-independent and zero-authority; received
> identity, support/height, mode/settings, and calibration remain open.
> Moving-camera work is optional Phase 2 only, never an automatic fallback.

This stage asks two simulation-only questions before the received arm, clamp,
tools, camera installation, and placemat can be measured:

1. Which source-traceable base/yaw/tool hypotheses are worth carrying into a
   complete route study?
2. For one selected hypothesis, which of the locked 46 keyboard and 29 phone
   targets pass a complete sampled park-to-target-to-park route?

It does not choose fabrication dimensions, modify the canonical workcell, move
the RoArm, or authorize contact. Every searched dimension remains an
unmeasured sensitivity value until replaced by controlled physical evidence.

## Relationship to the earlier studies

The original [reach-layout diagnostic](REACH_LAYOUT_STUDY.md) screened an
18-member near-nominal grid and found no complete contact-and-park finalist.
The [park optimizer](PARK_OPTIMIZATION.md) then found the board-frame probe
`B = (290, 10, 70) mm`, which removed the original park-only blocker but left
the phone `key_a` approach below the arm-joint margin gate.

The broader layout service expands only the already recorded sensitivity
envelope. It reuses that one optimized coordinate as a fixed park probe and
re-screens the probe for both tool hypotheses at every layout. It does not
optimize a new park for each hypothesis. Candidates that survive the staged
pose screens may then enter the independent full-catalog route service built on
the [trajectory simulator](TRAJECTORY_SIMULATION.md).

```text
verified active Freeze-011 context
  -> bounded, field-evidenced layout hypotheses
  -> fixed park + phone key_a + spatial-sentinel regression screens
  -> top-eight full 46-key + 29-phone contact shortlist
  -> explicit promotion gate
  -> 75 independent park-to-target-to-park trajectory diagnostics
```

## Broader layout contract

The default coarse grid has five three-value axes, producing exactly 243
hypotheses:

| Field | Search values | Evidence meaning |
| --- | --- | --- |
| Rear clamp contact X | 225, 305, 385 mm | Endpoints and midpoint of the locked RC03 clamp zone; layout-derived, not a received-part measurement |
| Rear edge to base-axis Y | 0, 50, 100 mm | Recorded reach sensitivity bounds and their midpoint; not a mechanical allowance |
| Base yaw in board | -105, -90, -75 degrees | Locked nominal -90 degrees and its +/-15-degree sensitivity bounds; not an allowed installation range |
| Keyboard TCP length | 80, 100, 120 mm | Locked virtual tool cases; not a measured keyboard TCP |
| Phone TCP length | 80, 100, 120 mm | Locked virtual tool cases; not a measured stylus TCP |

Clamp-to-base-axis X stays at an unmeasured 0 mm hypothesis. Roll and pitch
stay at zero, and base-link Z stays at the pinned 70.1 mm profile projection.
Every candidate serializes field-level source ID, derivation, and evidence
classification. Every search-value evidence record explicitly sets
`physical_measurement: false` and `mechanically_allowed: false`.

The search is staged:

1. Revalidate the complete simulation context and exact pinned URDF bytes, then
   reproduce the retained, bounded Freeze-005-derived park source.
2. Screen each coarse hypothesis at the fixed park with both route tools, at
   phone `key_a` contact and approach, and at three deterministic spatial
   sentinels per device. The implementation tests the park and `key_a`
   regressions first and skips later sentinels after a primary failure.
3. Refine at most six ranked coarse anchors using one-axis-at-a-time midpoints
   of actual adjacent coarse intervals.
4. Rank every regression pass deterministically, but run the canonical
   75-contact screen for only the top eight.
5. Promote a full-catalog candidate only when all of the following hold:
   both route tools accept the fixed park probe; all 46 keyboard contacts and
   all 29 phone contacts pass; and phone `key_a` contact plus approach pass the
   positive 0.01 normalized arm-joint-margin gate.

Promotion means only `eligible_for_full_route_screen`. It does not claim route
continuity, collision clearance, physical reachability, or motion authority.
The coarse regression solver is deliberately limited to two attempts and 18
iterations per attempt, so a regression rejection is not proof that no IK
solution exists.

### Layout resource ceilings

| Resource | Hard maximum |
| --- | ---: |
| Coarse hypotheses | 243 |
| Refinement anchors | 6 |
| Refinement hypotheses | 66 |
| Full-catalog candidates | 8 |
| Layout IK solves | 4,096 |
| Separate park-optimizer IK solves | 192 |
| Total service IK solves | 4,288 |
| Canonical IK effort | 8 attempts x 200 iterations |
| Coarse regression IK effort | 2 attempts x 18 iterations |
| Captured URDF bytes | 1,000,000 |

## Independent mission-route contract

The route service requires a one-to-one semantic mapping for the exact locked
46-keyboard + 29-phone catalog. It invokes the canonical trajectory boundary
once for each target. Every target independently begins at the selected park,
passes through ordered transit, hover, approach, contact, retract, return
transit, and park endpoints, and carries the previous accepted IK solution only
within that route.

One target's rejection does not hide later targets. A source, identity,
provenance, or resource-contract failure aborts the complete report instead of
returning partial evidence as success. Chunks are deterministic orchestration
groups only; they are never joined into a trajectory, and no joint state is
carried between targets or chunks.

The default route policy uses a 30 mm maximum Cartesian step, 0.35 rad maximum
adjacent sampled-joint step, 0.01 minimum normalized arm-joint margin, at most
one refinement round, 64 waypoint records per round, 128 IK solves per route,
and eight targets per orchestration chunk. Each route contains exactly one
physical target.

### Mission resource ceilings

| Resource | Hard maximum |
| --- | ---: |
| Targets per route | 1 |
| Target routes | 75 |
| Orchestration chunk size | 16 |
| Orchestration chunks | 75 |
| Refinement rounds per route | 1 |
| Waypoint records per round | 64 |
| IK solves per route | 128 |
| Mission waypoint records | 9,600 |
| Mission IK solves | 9,600 |
| Task-Jacobian FK evaluations per evaluated waypoint | 11 |
| Mission task-Jacobian FK evaluations | 105,600 |

## Evidence and provenance

The broader layout report binds the manifest and snapshot, simulation bundle
and lock, scenario and target profiles, exact captured URDF digest and byte
count, alignment report, RC03 layout/reach source hashes, park-source report,
policy and every searched value, solver identity/version/options, relevant
module hashes, implementation-bundle hash, runtime version, and complete
loaded `rocell` source-tree hash. Its report hash is over deterministic
canonical JSON with non-finite numbers rejected.

The mission service additionally verifies that every semantic plan isolates
exactly one expected physical target. It retains the semantic-character hash,
action-plan hash, trajectory report hash, endpoint/contact evidence, first
failure, waypoint and IK use, joint margins and deltas, and solver-task
Jacobian diagnostics for every route. Common source provenance must remain
identical across all 75 invocations. The CLI wrapper binds that coverage report
to either:

- the retained Freeze-005-derived reach result plus its independently bounded
  park report; or
- one exact promoted rank, broader-layout report hash, study-input ID, and
  re-screened park-probe identity.

Both report layers retain `simulation_only: true`,
`execution_authorized: false`, `contact_authorized: false`, zero hardware
commands, and `physical_release_effect: NONE`.

## Commands

Run from the workspace root after installing `software/`:

```powershell
rocell study-layout-hypotheses --json
rocell study-layout-hypotheses --require-promotable --json

rocell screen-mission-routes --json
rocell screen-mission-routes --require-all --json
rocell screen-mission-routes --from-layout-study-rank 1 --require-all --json
```

The default mission command uses the retained Freeze-005-derived placement and
bounded park. `--from-layout-study-rank` reruns the broad study and accepts only
a candidate actually promoted from the screened full-catalog shortlist.
Strict flags change only the process exit code after emitting evidence.

## Freeze-005-derived canonical results retained as history under Freeze 011

The hashes and counts in this section preserve their Freeze 005 report
provenance. The Freeze 006 to Freeze 007 evidence-only traceability transition,
Freeze 007 to Freeze 008 operator-waived Job 00A functional-fit transition,
Freeze 008 to Freeze 009 operator-confirmed 6.2 mm station-registration
transition, Freeze 009 to Freeze 010 camera-hold/Job 03C1 reconciliation, and
Freeze 010 to active Freeze 011 workflow correction regenerated controlled
derivatives, not these study inputs. No relabeling of the recorded reports is
claimed. The source-bound
broader study reports
`CANDIDATES_ELIGIBLE_WITHIN_SCREENED_FULL_CATALOG_SHORTLIST` with report hash
`3b65e3bca509f7c7e1583e5801e189639ab9e40cbf30827b71794752cd7259b4`.

| Stage | Current result |
| --- | --- |
| Coarse screens | 243 |
| Refinement screens | 34 |
| Regression passes | 49 |
| Full-catalog shortlist | Top 8 screened |
| Regression passes omitted from full catalog | 41 |
| Promotions | 6 |
| Layout IK use | 2,777 actual / 3,394 planned upper bound |
| Park-source IK use | 81 |

The presence of 41 omitted regression passes is important: status and
promotion conclusions apply only to the ranked top-eight full-catalog
shortlist. The study is not an exhaustive proof about every regression pass.

Promoted rank 1 is `reach-944d7463f4c67905`:

| Field | Sensitivity-only value |
| --- | ---: |
| Rear clamp contact X | 385 mm |
| Clamp-to-base-axis X | 0 mm |
| Rear-edge-to-base-axis Y | 75 mm |
| Base-link Z | 70.1 mm |
| Base yaw | -105 degrees |
| Keyboard tool length | 120 mm |
| Phone tool length | 100 mm |

These values are diagnostic hypotheses, not dimensions for drilling,
clamping, printing, tool fabrication, or camera placement.

### Baseline versus promoted route coverage

| Selection | Coverage status and accepted independent routes | Resource use | Final hashes |
| --- | --- | --- | --- |
| Documented baseline `reach-00ed8c5820df03c7`, optimized park `(290, 10, 70)` mm | `MISSION_ROUTE_COVERAGE_DIAGNOSTIC_GAPS_REPORTED`; 38/75: keyboard 20/46, phone 18/29; 37 gaps; phone `key_a` first fails at approach with margin `0.0006578241188109833 < 0.01` | 2,530 waypoint records; 1,649 IK solves; 17,501 task-Jacobian FK evaluations | coverage `1f89a2cf293a4b5d8d2a347960b7c4301ede98b4e3d35ddbcce956358d7ca718`; CLI wrapper `3c466811f49368c99ebb59f34b5bdd6d8c72727aa029bc190e7529730fc63bef` |
| Promoted rank 1 `reach-944d7463f4c67905`, same fixed park coordinate re-screened for this hypothesis | `MISSION_ROUTE_COVERAGE_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS`; 75/75 independent routes accepted | 2,424 waypoint records; 2,066 IK solves; 22,726 task-Jacobian FK evaluations | coverage `c67ac5d2cece745077ac631304b80f51a19c981edd107812ffa716673fbf2cd4`; CLI wrapper `759f7b82bc23880903222316b42115994857b8bc247e8e684aebc00e398208b8` |

The baseline selection is also bound to reach report
`335275e2a68aa2cda82163fedfe93c17daccdd65d87e07ab03359fafc738fc00`
and park report
`1a61bea96ba19c802ec5e28f1e465c582b3de6964fc3bcdfc2bc9955393c1ef6`.

The promoted result is valuable software evidence: it demonstrates that the
complete locked target catalog can traverse the implemented sampled route
checks somewhere inside the declared sensitivity envelope. It does not prove
that the received arm can be installed at that pose, that either tool has the
assumed TCP, or that arbitrary text can be typed continuously.

## Deliberately unsupported claims

- arbitrary multi-key or cross-device sequence feasibility;
- mathematical continuity between sampled IK waypoints or time-parameterized
  velocity, acceleration, and jerk feasibility;
- robot-link, self, gripper, tool-volume, camera, holder, connector, moving
  cable, base/clamp, fixture, or swept-volume collision clearance;
- calibrated physical six-dimensional Jacobian, manipulability, force, payload,
  dynamics, compliance, or contact behavior;
- controller-to-URDF correlation, homing behavior, or measured starting-state
  motion to park;
- received B0477 identity/mode/lens, fixed-support/cable/lighting acceptance,
  intrinsics, static `Wv_T_C_overhead_optical`, fresh
  `C_overhead_optical_T_B`, device-presence verification, or vision correction;
  optional Phase-2 arm-camera qualification is also outside this study; and
- observed keyboard actuation, Android UI state, tap success, or text outcome.

The implemented five-constraint solver-task Jacobian rank check remains a
numerical diagnostic, not a physical six-dimensional singularity certificate.

## Next physical steps

1. Record delivered identities before use: RoArm-M3-Pro serial/controller and
   firmware, power supply, base/clamp parts, tools, the exact received Arducam
   B0477/IMX283 USB identity, delivered 16 mm lens/case configuration, driver,
   connector, cable, and static-support parts. Keep the arm's ESP32 controller
   identity separate from the USB camera identity; record the bundled holder
   only as inventory unless an optional Phase-2 experiment is opened.
2. Measure the installed board-to-base transform, clamp contact and base-axis
   offsets, Z/roll/pitch/yaw, keyboard and phone poses, and both route TCPs with
   uncertainties. Compare the measurements with the sensitivity report; never
   force the build to match rank 1 merely because its simulation passed.
3. Positively retain the B0477 on the final fixed support; qualify support
   fasteners, height/aim, fixed cable and strain relief, controlled lighting,
   stiffness/settling, bump/remove-reinstall/thermal drift, and a support
   reference witness. Capture complete collision geometry and frame bindings
   for every robot link, gripper, tool, base/clamp, keyboard, phone, static
   support, camera, connector, cable, and light. Keep motion blocked until the
   collision readiness audit can run a complete diagnostic.
4. Correlate encoder signs, zero offsets, limits, ready/park states, and the
   ESP32 controller frame with the pinned URDF using power-limited,
   non-contact procedures and a verified stop path.
5. Prove the exact B0477 resolution, pixel format, crop/orientation, and locked
   controls persist after close/reopen and reboot; treat published
   `5472 x 3648 @ 9 fps YUY2` as an unverified receipt-test target. Calibrate
   intrinsics/distortion at the final lens/focus/aperture/settings, measure the
   installed tag map, and solve/hold out the static
   `Wv_T_C_overhead_optical`.
6. At startup and before descent, require a fresh
   `C_overhead_optical_T_B` with T0–T3 used for pose and K0/P0 held out. Verify
   camera settings/freshness, support witness, expected device presence,
   seating/orientation, and target-map residuals. Independently qualify
   `R_ctrl`, then validate both route TCPs, approach axis, Z, and travel with
   the keyed puck across the keyboard and phone regions.
7. Rerun the broad and 75-route diagnostics with measured overlays and complete
   collision acceptance. Then
   progress through empty-cell, above-surface, low-force keyboard, and Android
   outcome tests under explicit commissioning gates. No simulated PASS should
   bypass those stages.

The historical Waveshare IMX335/bundled-holder route may be evaluated only as
a separate optional Phase-2 project with its own carrier transform, hand-eye
calibration, exposure/joint synchronization, payload, moving-cable, collision,
and route-visibility evidence. It cannot satisfy a Phase-1 gate or act as an
automatic fallback.
