# Bounded park-pose optimization

`optimize-park` searches for a simulation-only park overlay for the documented
Freeze-005-derived reach-study placement, revalidated through the active
Freeze-011 context. It addresses the nominal park failure without changing the
RC03 placemat, base placement, route tools, manifest, or any physical gate.

## Contract

The optimizer derives XY candidates from the revalidated 610 x 457 mm board,
the modeled device/station keepouts, and the physical AprilTag tile footprints.
It uses the one derived transit-plane height, 70 mm in the current nominal
scene, and screens each eligible point independently through the canonical
numerical IK solver for both selected 100 mm route tools.

The bounded coarse/fine search has serialized candidate and IK-solve ceilings.
Ranking prefers, in order, acceptance for both route tools, accepted-route
count, worst accepted arm-joint margin, planar point clearance, IK residual,
distance from the frozen nominal park, and stable coordinates/identity. The
original nominal park is retained as an auditable baseline candidate.

The service captures the pinned URDF through the shared bounded exact-byte
loader, verifies the digest before parsing those same bytes, and retains the
loaded digest and byte count in report provenance.

Run it from the workspace root:

```powershell
rocell optimize-park --json
rocell optimize-park --require-both-routes --json
```

`--require-both-routes` changes only the exit status. It does not grant motion
or contact authority.

## Freeze-005-derived result retained through active Freeze 011

Freeze 009 first carried this historical input forward. Active Freeze 011
continues to source-bind it without relabeling the result or hashes as a new
Freeze-011 execution.

The best candidate is board-frame point `B = (290, 10, 70) mm`. Both selected
100 mm tools pass the independent pointwise IK screen. Its worst accepted
normalized arm-joint margin is `0.2704734350`, and its minimum modeled planar
point clearance is 10 mm. The final source-bound park report hash is
`1a61bea96ba19c802ec5e28f1e465c582b3de6964fc3bcdfc2bc9955393c1ef6`.

This result is deliberately narrow. The 10 mm value is clearance for the
tool-tip point projection against nominal planar proxies; it is not link,
holder, camera, tool-body, cable, fixture, self-collision, or swept-volume
clearance. The IK results are independent poses, not a path from the installed
arm's measured state. The placement, tool lengths, scene, and transforms remain
nominal and unmeasured.

The candidate may be applied to the trajectory simulator without altering the
canonical context:

```powershell
rocell simulate-trajectory --device keyboard --text "a" --use-optimized-park --json
rocell simulate-trajectory --device phone --text "a" --use-optimized-park --json
```

The overlay is accepted only when it is bound to the same documented
reach-study input as the trajectory. Manual `--park-x-mm`/`--park-y-mm`
coordinates and `--use-optimized-park` are mutually exclusive.

## What the result revealed

With the optimized park, the current keyboard `"a"` route accepts all 24 of 24
densified waypoints and reports
`DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS`.
The phone `"a"` route still fails closed at `APPROACH`: its normalized
arm-joint margin is `0.000657824`, below the `0.01` gate. Independently, both
fully screened reach-study finalists reject the phone `key_a` contact pose.

Therefore the optimizer removed the first park-only software blocker but did
not produce a complete typing-and-phone result for the frozen baseline. A
separate broader study now has sensitivity-only layout/tool overlays that pass
all 75 independent target-route diagnostics, but those unmeasured overlays do
not revise this park result, the canonical RC03 geometry, or any physical gate.
They remain inputs to measured mechanical validation and collision analysis.

## Authority and unsupported checks

Every report remains `simulation_only: true`, generates zero hardware commands,
does not modify canonical geometry, and has no physical-release effect. It does
not evaluate route continuity, the full six-dimensional physical Jacobian,
physical manipulability, dynamics, payload, force, controller correlation,
commissioned Phase-1 static vision, optional Phase-2 arm-mounted vision, device
outcomes, or any full-body collision volume.
