# RC03 reach-layout diagnostic

This study answers a narrow pre-hardware question: which bounded arm-clamp and
route-tool hypotheses deserve later full path, collision, and physical tests?
It does not move the RoArm, alter the frozen placemat scenario, or prove that a
typing route is executable.

## Frame and placement contract

The physical input is the arm base-link pose, not the vendor URDF world pose:

```text
B_T_Wv = B_T_Ru * inverse(Wv_T_Ru)
```

- `B` is the RC03 placemat board frame.
- `Ru` is URDF `base_link`.
- `Wv` is the vendor URDF root `world`.
- Pinned `Wv_T_Ru` is a fixed +70.1 mm Z translation.

Each candidate identifies a rear-edge clamp contact X inside the recorded
225–385 mm zone and a separate, explicitly unmeasured clamp-to-base-axis X/Y
offset. The bounded default currently assumes both offsets are zero, base-link
Z is the canonical 70.1 mm, and base roll/pitch are zero. Yaw and route tool
lengths remain hypotheses. These are study assumptions, not fabrication or
installation dimensions.

## Default bounded policy

The default grid contains 18 coarse inputs:

- clamp contact X: 225, 305, and 385 mm;
- clamp-to-axis X offset: 0 mm;
- rear-edge-to-axis Y offset: 0 mm;
- yaw: nominal -90 degrees and ±8 degrees;
- keyboard tool length: 80 and 100 mm;
- phone tool length: 100 mm; and
- park: the canonical board park point at the required obstacle-clearance Z.

Coarse screening uses three spatially spread targets per device and every
declared park. It keeps two finalists, then runs the full 46-key plus 29-phone
contact catalog and both route tools at each park with the canonical diagnostic
IK effort. A pose must retain at least 1% normalized margin across the five IK
arm joints. The gripper is fixed at its provisional lower bound and is reported
separately; it is not silently counted as having positive margin.

Hard resource ceilings limit study inputs, finalists, target count, parks, IK
attempts/iterations, park height, and the planned IK solve count. All coarse
evidence is retained in the report so finalist selection is auditable.

Ranking is deterministic and lexicographic:

1. all contacts plus both route parks;
2. accepted route parks;
3. minimum keyboard/phone completion fraction;
4. total accepted contacts;
5. worst accepted-pose arm-joint margin;
6. minimum deviation from nominal assumptions; and
7. stable candidate and park IDs.

This prevents the smaller phone catalog from masking poor keyboard coverage.

## Run it

```powershell
rocell optimize-layout --json
rocell optimize-layout --require-complete --json
```

`--require-complete` returns nonzero unless one fully evaluated finalist passes
all 75 contact poses and both route parks. Passing would still mean only
`INDEPENDENT_CONTACT_AND_PARK_IK_DIAGNOSTIC_ONLY`; it would not authorize
hardware.

## Freeze-005-derived corrected simulation result

The default study was rerun read-only against its historical Freeze-005 context.
Freeze 009 retains this report as historical simulation provenance because the
reach inputs did not change; it is not relabeled as a Freeze 009 result. The
result is not a feasible typing layout:

| Field | Best diagnostic finalist |
| --- | --- |
| Status | `CONTACT_AND_PARK_DIAGNOSTIC_NO_COMPLETE_FINALIST` |
| Report hash | Omitted until the final source-hardening verification rerun |
| Study effort | 18 coarse inputs / 135 IK solves; 2 full finalists / 152 IK solves |
| Clamp/base hypothesis | clamp contact X 385 mm; unmeasured X/Y axis offsets 0 mm; base-link Z 70.1 mm; yaw -82 degrees |
| Route tools | keyboard 100 mm; phone 100 mm |
| Keyboard contacts | 20/46 |
| Phone contacts | 18/29 |
| Required route parks | 0/2; both `NO_CONVERGED_SOLUTION` |
| Worst accepted-pose arm margin | 0.0100156 normalized, barely above the 0.01 gate |
| Fixed gripper margin | 0.0 normalized; reported separately and not qualified |

Accepted keyboard targets are `1`, `2`, `3`, `A`, `B`, `C`, `D`, `E`, `F`,
`G`, `M`, `N`, `Q`, `S`, `SPACE`, `TAB`, `V`, `W`, `X`, and `Z`. Accepted
phone targets are `key_b`, `key_c`, `key_enter`, `key_f`, `key_g`, `key_h`,
`key_j`, `key_k`, `key_l`, `key_m`, `key_n`, `key_o`, `key_p`, `key_period`,
`key_space`, `key_v`, `key_x`, and `key_z`.

This evidence says the current planar base/tool/park assumptions need redesign
or a wider mechanically justified study; it does not say the physical arm is
incapable. A follow-on bounded park search has now replaced the first failing
park overlay for simulation, but a 1.00156% worst accepted reach-finalist arm
margin is not robust to installation error and the contact catalog remains
incomplete.

## Deliberately missing from this study

- approach, hover, retract, and transit sequencing;
- IK continuity between sampled waypoints and time-parameterized interpolation;
- full six-dimensional physical task-Jacobian/singularity,
  manipulability/force, and dynamic/load analysis;
- full robot-link, self, holder, camera, cable, fixture, and tool collision;
- measured base, clamp-axis, device, and route TCP transforms;
- controller Cartesian-frame correlation; and
- force/contact and keyboard/Android outcome verification.

The first follow-on numerical stage is now implemented by
[`simulate-trajectory`](TRAJECTORY_SIMULATION.md): it verifies every nominal
motion phase for one retained placement, densifies Cartesian segments, feeds
the previous solution into the next IK solve, and gates adjacent sampled-joint
deltas. Its schema-v2 solver-task diagnostic also rejects numerical rank loss
in the weighted five-constraint IK residual while treating normalized
conditioning as report-only. It still does not prove continuity between
samples, swept collision, or physical six-dimensional singularity margins.

[`optimize-park`](PARK_OPTIMIZATION.md) separately found the nominal
board-frame overlay `(290, 10, 70) mm`, accepted pointwise by both 100 mm tools
with `0.2704734350` worst normalized arm margin and 10 mm modeled planar point
clearance. With that overlay, keyboard `"a"` accepts 24/24 trajectory
waypoints, but phone `"a"` fails at `APPROACH` on a `0.000657824 < 0.01` arm
margin; both reach finalists also reject the phone `key_a` contact. The next
physical stage must measure the received clamp/base/tool geometry rather than
turning either optimized hypothesis into a nominal fact, and the software
study must broaden or redesign the current base/tool/layout before claiming
full-mission feasibility.

That broader staged study is now documented in
[pre-hardware mission coverage](PREHARDWARE_MISSION_COVERAGE.md). Its
source-bound report `3b65e3bca509f7c7e1583e5801e189639ab9e40cbf30827b71794752cd7259b4`
promotes six candidates within the screened top-eight shortlist. Sensitivity-only
rank 1, `reach-944d7463f4c67905`, accepts 75/75 independent target routes; the
documented baseline accepts 38/75. This is a design lead, not a measured or
mechanically authorized installation.
