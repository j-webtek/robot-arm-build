# Discrete route trajectory simulation

This stage connects a typed keyboard or phone plan to an ordered, bounded
sequence of nominal Cartesian waypoints and diagnostic joint solutions. It is
the bridge between the independent contact/park reach study and future
installed-system planning. It does not move the arm or prove that a physical
route is safe.

## Pipeline contract

```text
text
  -> semantic keyboard/phone ActionPlan
  -> selected bounded reach-study placement hypothesis
  -> nominal, manual, or retained Freeze-005-derived optimized park overlay
  -> geometric park/transit/hover/approach/contact/retract endpoints
  -> bounded Cartesian densification
  -> sequential numerical IK, previous solution first
  -> joint-limit margin, solver-task numerical-rank, and sampled-joint delta checks
  -> content-addressed diagnostic report
```

The public service reloads and revalidates the canonical active Freeze-011
simulation context before using the requested placement overlay. It checks that
the placement still obeys the RC03 rear-clamp zone, the reach-study base-offset and
yaw envelope, and the pinned 70.1 mm vendor-world/base-link relationship. The
overlay never changes the frozen placemat files.

The existing geometric engine first creates an ordered route beginning and
ending at park. Non-motion `VISION_CORRECT` and `VERIFY` records remain future
observer requirements and are not converted into motion. For each physical
target, the simulator requires ordered transit, hover, approach, contact, and
retract endpoints. Each Cartesian segment is then subdivided to the policy's
maximum step.

At every waypoint, the bounded numerical IK solver receives the previously
accepted joint solution as its first seed. An accepted sample must:

- converge within the serialized attempt/iteration budget;
- stay inside the controller/URDF intersection for all five arm joints;
- retain the configured normalized arm-joint margin;
- retain numerical rank five in the solver's weighted five-constraint task
  Jacobian; and
- stay within the configured adjacent sampled-joint delta.

Failure from non-convergence or excessive adjacent delta may trigger bounded
Cartesian refinement. Other failures stop immediately. This sampled process
does not prove mathematical continuity between waypoints.

Trajectory report schema `rocell.discrete_sequential_ik_waypoint_simulation.v2`
adds a deterministic local solver-task Jacobian diagnostic at each selected IK
state. Numerical rank loss is fail-closed. The normalized minimum singular
value and condition number are serialized for diagnosis only; they have no
acceptance threshold because this is the solver's weighted residual metric,
not a calibrated physical six-dimensional Jacobian or manipulability model.

## Run it

From the workspace root after installing `software/`:

```powershell
rocell simulate-trajectory --device keyboard --text "ab" --json
rocell simulate-trajectory --device phone --text "ab" --json
rocell simulate-trajectory --device keyboard --text "a" --use-optimized-park --require-pass --json
```

The default fast path replays the retained Freeze-005-derived placement input.
Use `--refresh-placement-ranking` to rerun the full bounded reach optimizer and
select `--placement-rank 1` or `2`. Use `--study-input-id` to replay an exact
content-derived member of the locked default placement grid. A park override
requires both `--park-x-mm` and `--park-y-mm` and must remain on the board and
outside every modeled keepout and tag tile.

`--use-optimized-park` runs the retained, bounded Freeze-005-derived park
diagnostic and applies
its best both-routes candidate only when it is bound to the same reach-study
input. It cannot be combined with manual park coordinates and does not mutate
canonical geometry. See [the park-pose contract](PARK_OPTIMIZATION.md).

Policy arguments are intentionally bounded:

- `--maximum-cartesian-step-mm` controls waypoint spacing;
- `--maximum-joint-step-rad` gates adjacent accepted samples;
- `--minimum-arm-joint-margin` gates normalized limit margin;
- `--maximum-refinement-rounds` is limited to 0–3; and
- `--maximum-route-targets` is limited to 1–16.

`--require-pass` changes only the process exit status. It cannot authorize
hardware, calibration, motion, or contact.

## Freeze-005-derived result retained through active Freeze 011

Freeze 009 first carried this historical input forward. Active Freeze 011
continues to source-bind it without relabeling the result or hashes as a new
Freeze-011 execution.

The canonical placement remains documented reach input
`reach-00ed8c5820df03c7`. The separate bounded park optimizer selected
`B = (290, 10, 70) mm`; both 100 mm route tools pass its independent pointwise
IK screen with a worst normalized arm-joint margin of `0.2704734350` and 10 mm
minimum modeled planar point clearance.

Using that simulation-only overlay produces different one-character outcomes:

| Route | Current result | Final source-bound hashes |
| --- | --- | --- |
| Keyboard `"a"` | Strict exit 0; 24/24 densified waypoints accepted; `DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS` | trajectory `828101968a0ba10d10c818b9d883dba77a486817f380ee007cd220e7213f97e0`; wrapper `53ed18aa0c496bcec6d4bdb5eaf0566a69149fe233ad5a6ef2849d3cd25695c0` |
| Phone `"a"` | Strict exit 3; fails closed at `APPROACH`; normalized arm-joint margin `0.000657824` is below the `0.01` gate | trajectory `f66a992a1be13fa1cb1a6b14ef74e2261a3a1982d1b5af2ee4d81a21934317b4`; wrapper `c9710d991cd80c1b4a93a98ddd8ba9db30efdd0084853820a8fe74267266b7dd` |

Both fully screened reach-study finalists also reject the phone `key_a` contact
pose. The optimized park therefore removes the old first-waypoint blocker and
allows the keyboard `"a"` diagnostic to exercise the entire nominal route, but
it does not make the combined keyboard-and-phone mission feasible. The current
base/tool/layout hypothesis still requires measured inputs and redesign. These
results reject nominal hypotheses, not the received physical RoArm-M3-Pro.

The full-catalog follow-on is described in
[pre-hardware mission coverage](PREHARDWARE_MISSION_COVERAGE.md). With the same
independent-route policy, the documented baseline accepts 38/75 targets
(`1f89a2cf293a4b5d8d2a347960b7c4301ede98b4e3d35ddbcce956358d7ca718`),
while sensitivity-only promoted rank 1 accepts 75/75
(`c67ac5d2cece745077ac631304b80f51a19c981edd107812ffa716673fbf2cd4`).
Each target still starts and ends at park independently; this is not an
arbitrary typing-sequence, collision, or physical-installation proof.

## Provenance and interpretation

The report binds the manifest snapshot, simulation bundle, hardware/target
profiles, pinned URDF, alignment report, semantic plan, reach-study input,
solver options, joint bounds, active solver/geometry implementation identities,
individual module hashes, and the complete loaded `rocell` Python source-tree
hash. Unit-test solver doubles are explicitly labeled and cannot be reported as
the canonical implementation.

The URDF is read once through a bounded exact-byte loader. Its digest is checked
before those same captured bytes are parsed, and the loaded digest and byte
count are retained in provenance. The simulation, target sweep, reach, park,
and trajectory services share this boundary so a changed file cannot be hashed
and then reparsed from different bytes.

The two public result classes are:

- `DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS`;
- `DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_GAPS_REPORTED`.

Even the first status means only that every sampled waypoint passed the
implemented diagnostics. Both retain `simulation_only: true`,
`execution_authorized: false`, `hardware_accessed: false`, zero generated
hardware commands, and `physical_release_effect: NONE`.

## Explicitly unsupported physical proofs

The report emits these as blocking, unevaluated diagnostics:

- full robot-link and self collision;
- holder, camera, tool-volume, fixture, and moving-cable collision;
- full six-dimensional physical Jacobian singularity/manipulability and force
  capability; the implemented five-constraint solver-task conditioning is not
  a substitute;
- time parameterization, velocity, acceleration, dynamics, payload, and force;
- installed controller/URDF correlation and T=104 execution;
- commissioned static-overhead vision correction and keyboard/Android outcome
  observers (optional arm-mounted Phase-2 vision is separate); and
- measured transforms, uncertainty, repeatability, and contact qualification.

The current nominal AABB checks follow the tool-tip centreline only. They are
useful for finding software/placement failures before hardware arrives, but
they are not a swept-volume or physical safety certificate.
