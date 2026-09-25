# Full-body collision foundation

> **Camera architecture notice — 2026-09-05:** Phase 1 uses a rigid static
> overhead Arducam B0477 with its included 16 mm lens. Its support, camera
> body, lighting, and routed cable must be modeled as static workcell collision
> geometry. The source-locked support candidate supplies a nominal screening
> envelope, but received and installed geometry remains unqualified. Existing
> moving-camera bodies are retained only for optional Phase 2 work and are not
> an automatic fallback. All collision results remain zero-authority.

## Purpose and authority

This foundation provides a typed, bounded, deterministic collision-model
contract for the RoArm-M3-Pro RC03 workcell. It is the software boundary for
representing robot links, the factory base/clamp, camera assembly, moving
camera cable, contact tool, and static placemat objects before pose and sweep
diagnostics are attempted.

It does not authorize the robot. Every contract, audit, pose report, and sweep
report is simulation-only, generates zero hardware commands, cannot release a
physical gate, and leaves contact disabled. A report that is clear at a pose or
at discrete sweep samples is diagnostic evidence only. It is never a motion
permit or a continuous-collision proof.

The implementation is split between:

- `rocell/simulation/collision.py`: pure typed geometry, audit, pose-query, and
  discrete-sweep kernels that can be exercised with synthetic fixtures; and
- `rocell/application/collision_readiness.py`: current-artifact audit that
  revalidates the complete `SimulationContext`, inspects the exact hash-pinned
  URDF bytes, projects the RC03 scene, and reports every unresolved body.

This is separate from the existing geometric route simulator's coarse
tool-tip-versus-AABB checks. The collision foundation is not yet wired into a
typing or phone-tapping route executor.

## Versioned data model

The current schemas are:

| Artifact | Schema |
| --- | --- |
| Geometry contract | `rocell.collision_geometry_contract.v1` |
| Geometry audit | `rocell.collision_geometry_audit.v1` |
| Pose report | `rocell.collision_pose_report.v1` |
| Sweep report | `rocell.collision_sweep_report.v1` |
| Current-artifact readiness | `rocell.current_collision_readiness.v1` |

A `CollisionGeometryContract` has one root frame, required body declarations,
body bindings, and typed pair exclusions. A requirement and its body binding
must agree on body ID, parent frame, role, and binding mode. A `STATIC_ROOT`
body must be parented directly to the contract root; a different parent fails
closed at construction or audit rather than producing a misleading ready
status.

Binding modes are:

| Binding mode | Meaning |
| --- | --- |
| `RIGID_FRAME` | Local primitives move with one named rigid parent frame. |
| `STATIC_ROOT` | Primitives are fixed in the contract root frame. |
| `CONFIGURATION_SAMPLED` | Geometry is supplied for each evaluated configuration, for example the moving camera cable. |

Body geometry evidence is explicit:

| Evidence state | Diagnostic use | Physical completeness |
| --- | --- | --- |
| `ACCEPTED_MEASURED` | Yes | Yes, subject to the separate physical acceptance process |
| `PINNED_DIGITAL` | Yes | No; diagnostic-only digital geometry |
| `SYNTHETIC_TEST_ONLY` | Yes | No; tests only |
| `UNKNOWN` | No | No |
| `MISSING` | No | No |

`PINNED_DIGITAL` therefore cannot satisfy physical acceptance. Every required
body must have a compatible binding and diagnostic-usable geometry before the
audit can set `diagnostic_ready: true`. A non-sampled body with a usable state
and an empty primitive list is blocked. A configuration-sampled body must
supply non-empty, evidence-bearing geometry at each pose and is never declared
physically complete merely because its contract-level primitive list is empty.

## Geometry and query pipeline

The reduced-envelope primitives are millimetre-valued spheres, capsules, and
oriented boxes. They are deliberately simple enough to audit and test; no
unavailable physical dimensions are inferred from a product name or nominal
rendering.

A pose query performs these steps:

1. Audit all required bodies and bindings.
2. Require a transform for every rigid parent and per-pose sampled geometry
   for every configuration-sampled body.
3. Require an explicit clearance and uncertainty policy.
4. Transform and conservatively inflate each primitive.
5. Use world-axis-aligned bounds as the broad phase.
6. Run narrow-phase intersection tests for sphere/sphere, sphere/capsule,
   capsule/capsule, sphere/box, capsule/box, and box/box candidates.
7. Serialize tested counts, primitive indices, blockers, bound inputs, and zero
   authority.

A blocked input produces a typed blocked status rather than a clear result.
Complete queries can report `COLLISION_DETECTED` or
`CLEAR_AT_SAMPLED_POSE`. A collision-free diagnostic additionally requires a
complete diagnostic geometry audit and no reported collision pair.

### Positive clearance and uncertainty inflation

Intersection of nominal, uninflated shapes is insufficient for this workcell.
Every pose or sweep query therefore requires a `CollisionClearancePolicy`; the
default evaluation policy has no clearance policy and fails closed with
`BLOCKED_CLEARANCE_POLICY`.

For each body, the engine expands its primitive by:

```text
minimum_separation_mm / 2
+ geometry_uncertainty_mm_per_body
+ pose_uncertainty_mm_per_body
```

The pair receives twice that amount. The all-zero case is rejected. The policy
also carries an evidence state and source reference, and its exact content and
hash are bound into the query report. Box half-extents are expanded along the
box's local axes, which is conservative for the represented envelope.

Before physical use, engineering acceptance must choose a positive required
separation and evidence-backed geometry and pose uncertainties. The engine's
ability to run with any positive total inflation does not itself establish
that those values are adequate for the installed arm, flex, backlash,
calibration error, payload, or contact process.

## Typed pair exclusions

Pair exclusions are not raw body-ID tuples. Each `CollisionPairExclusion`
contains the normalized body pair, scope, evidence state, rationale, and source
reference. The allowed scope/evidence combinations are:

| Scope | Required evidence | Acceptance meaning |
| --- | --- | --- |
| `ENGINEERING_GLOBAL` | `ACCEPTED_ENGINEERING` | Reviewed global exclusion |
| `URDF_ADJACENT_DIAGNOSTIC` | `PINNED_KINEMATIC_DIAGNOSTIC` | Diagnostic only |
| `SYNTHETIC_TEST_ONLY` | `SYNTHETIC_TEST_ONLY` | Test fixture only |

The current adjacent-link exclusions are derived from the exact pinned URDF
topology. They are diagnostic and not physically accepted because adjacency
alone does not prove that installed body envelopes may always overlap safely.

Keyboard-key and phone-screen contact are phase-specific allowances. They must
be modeled by a future phase-local contact query and must never be converted
into global collision exclusions. No exclusion can authorize contact.

## Configuration-sampled cable geometry

The moving camera cable uses `CONFIGURATION_SAMPLED`. Each `CollisionPose` must
bind that body ID to a `SampledCollisionGeometry` containing:

- at least one primitive, normally a reviewed capsule chain or another
  conservative reduced envelope;
- an evidence state for that exact sample; and
- a source reference identifying how that configuration-specific geometry was
  obtained.

Contract-level evidence is not silently reused as per-pose cable evidence. A
rigid endpoint interpolation also cannot infer how a cable deforms between
poses. The current two-endpoint sweep API has no intermediate deformable-body
input boundary, so it always returns `BLOCKED_DEFORMABLE_SWEEP` when a
configuration-sampled body is present. Endpoint cable samples are not enough;
an explicit bounded waypoint-sequence or validated deformation-sampler
boundary is still required.

## Determinism, provenance, and bounds

Pose reports embed the complete deterministic contract, pose, and policy
content and the SHA-256 of each. Sweep reports do the same for the contract,
start pose, end pose, and policy. The current readiness report additionally
binds the revalidated manifest, build snapshot, simulation bundle, alignment
report, scene hashes, and exact URDF byte inventory.

Input iterables and mappings are bounded while they are materialized; a custom
container cannot bypass a cap by lying in `__len__`. The implementation hard
caps are:

| Resource | Hard maximum |
| --- | ---: |
| Requirements | 128 |
| Bodies | 128 |
| Primitives per body or sampled body | 64 |
| Pair exclusions | 4,096 |
| Pose transforms | 256 |
| Body pairs per pose | 8,192 |
| Primitive-pair narrow tests per pose | 65,536 |
| Sweep samples | 512 |
| Sweep body-pair evaluations | 262,144 |
| Sweep primitive-pair evaluations | 1,048,576 |

The lower default evaluation-policy limits are 64 bodies, 2,048 body pairs per
pose, 32,768 primitive-pair tests per pose, 128 sweep samples, 65,536 sweep
body-pair evaluations, and 262,144 sweep primitive-pair evaluations. Default
sampling limits are 5 mm of surface travel and 5 degrees of rotation per step.
Requests over either the selected limit or an implementation hard cap fail
closed.

Sweeps use bounded discrete rigid-transform interpolation with sample density
driven by translation, rotation, and body radius. Even when every evaluated
sample is clear, the only valid status is
`CLEAR_AT_DISCRETE_SWEEP_SAMPLES`; `continuous_collision_proof` is always
false. Dynamics, unmodeled deformation, payload effects, and events between
samples are not inferred.

## Freeze-005 readiness-audit provenance retained through active Freeze 011

The following is the exact Freeze-005 result recorded on 2026-09-01. Freeze 009
first retained it as historical report provenance, and active Freeze 011 still
does so; the listed manifest and report hashes are not relabeled as a
Freeze-009 or Freeze-011 execution. It is reproducible only against its
originally bound source hashes.

| Field | Current value |
| --- | --- |
| Status | `COLLISION_DIAGNOSTIC_BLOCKED_REQUIRED_GEOMETRY_INCOMPLETE` |
| Contract | `ROCELL-ROARM-M3-RC03-PREHARDWARE-COLLISION-V1` |
| Required / bound body records | 19 / 19 |
| Diagnostic ready | `false` |
| Physical geometry complete | `false` |
| Readiness report SHA-256 | `73e50b1dd84fbc8ed2f5fba6a2cfbbc16a3f4a58e3544f6fbd4a1e7f96a6ca5d` |
| Manifest SHA-256 | `18d898977a62b2222f9a953548f262dc46eebe8ff5a4c5acb47bfd6aa7cd284e` |
| Build snapshot SHA-256 | `710cd2474a70d3da0e85b9940fd9ce4e45b44fb4dbd258da00f59aa20c414de9` |
| Bundle-lock SHA-256 | `330fc09fb03927223abb32c3b55e5a22e0d2c8ddcd6e24777241c90bff0a3f5f` |
| Alignment-report SHA-256 | `74223cb6b9b7fc7ea47afd919070e3d05042bff98458f86f979d83628a41761d` |

All 19 required bodies are named below. "Bound" means a typed body record
exists; it does not mean that usable geometry exists.

| Required body | Binding | Current evidence |
| --- | --- | --- |
| `robot:base_link` | `RIGID_FRAME` to `base_link` | `MISSING` |
| `robot:link1` | `RIGID_FRAME` to `link1` | `MISSING` |
| `robot:link2` | `RIGID_FRAME` to `link2` | `MISSING` |
| `robot:link3` | `RIGID_FRAME` to `link3` | `MISSING` |
| `robot:link4` | `RIGID_FRAME` to `link4` | `MISSING` |
| `robot:link5` | `RIGID_FRAME` to `link5` | `MISSING` |
| `robot:gripper` | `RIGID_FRAME` to `gripper_link` | `MISSING` |
| `installation:base_and_factory_clamp` | `STATIC_ROOT` to `board` | `UNKNOWN` |
| `attachment:camera_holder` | `RIGID_FRAME` to `holder` | `UNKNOWN` |
| `attachment:camera_module` | `RIGID_FRAME` to `camera_module` | `UNKNOWN` |
| `attachment:camera_connector` | `RIGID_FRAME` to `camera_module` | `UNKNOWN` |
| `attachment:moving_camera_cable` | `CONFIGURATION_SAMPLED` in `board` | `UNKNOWN` |
| `attachment:contact_tool` | `RIGID_FRAME` to `hand_tcp` | `UNKNOWN` |
| `workcell:board_solid` | `STATIC_ROOT` to `board` | `PINNED_DIGITAL` |
| `workcell:keyboard` | `STATIC_ROOT` to `board` | `PINNED_DIGITAL` |
| `workcell:phone` | `STATIC_ROOT` to `board` | `PINNED_DIGITAL` |
| `workcell:station:keyboard_left` | `STATIC_ROOT` to `board` | `PINNED_DIGITAL` |
| `workcell:station:keyboard_right` | `STATIC_ROOT` to `board` | `PINNED_DIGITAL` |
| `workcell:station:phone_tcp` | `STATIC_ROOT` to `board` | `PINNED_DIGITAL` |

The exact missing-body list is:

```text
robot:base_link
robot:gripper
robot:link1
robot:link2
robot:link3
robot:link4
robot:link5
```

The exact unknown-body list is:

```text
attachment:camera_connector
attachment:camera_holder
attachment:camera_module
attachment:contact_tool
attachment:moving_camera_cable
installation:base_and_factory_clamp
```

The six `PINNED_DIGITAL` RC03 scene proxies are diagnostic-only. They are the
board, keyboard, phone, two keyboard station proxies, and the phone/TCP station
proxy listed in the table. They do not make the installed workcell physically
complete.

The exact URDF file is
`software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf`: 2,849 bytes with
SHA-256
`a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`.
The readiness audit reads and hashes one bounded byte snapshot, parses those
same bytes, and finds zero `<collision>` elements. The seven robot-link shapes
therefore remain missing; the software does not substitute nominal sizes.

The six current diagnostic-only exclusion pairs are:

```text
robot:base_link <-> robot:link1
robot:gripper   <-> robot:link5
robot:link1     <-> robot:link2
robot:link2     <-> robot:link3
robot:link3     <-> robot:link4
robot:link4     <-> robot:link5
```

Each is scoped `URDF_ADJACENT_DIAGNOSTIC` with evidence
`PINNED_KINEMATIC_DIAGNOSTIC`; none is an accepted engineering exclusion.

The report also preserves the snapshot values
`safe_to_power_robot: false` and `contact_enabled: false`. Separately, the
report itself always confers neither permission, even if a future source
snapshot changes.

## Command and strict exit

Run from the workspace root after installing the package from `software/`:

```powershell
rocell collision-status --json
```

This command revalidates the current context, emits the full audit, and returns
exit code 0 when the audit itself ran successfully. Exit code 0 does not mean
the geometry is ready; read `status` and `geometry_audit.diagnostic_ready`.

For automation, require complete diagnostic geometry explicitly:

```powershell
rocell collision-status --require-diagnostic-ready --json
```

The strict form emits the same report and returns configuration-error exit code
3 while `diagnostic_ready` is false. A context, source, URDF, or contract audit
failure also fails as a configuration error and emits
`COLLISION_READINESS_AUDIT_FAILED`. Neither command performs hardware I/O or a
pose/sweep collision query.

## Concrete path to unblock collision diagnostics

No dimension should be inserted merely to turn the current status green. The
next work is:

1. Define a reviewed, versioned, content-addressed collision-geometry artifact
   and loader. Bind it through the simulation bundle/context so accepted body
   shapes and transforms cannot be substituted in memory or changed without a
   hash change.
2. Derive conservative reduced primitives for all seven robot bodies from the
   exact received Pro arm and authoritative CAD or measured geometry. Record
   the reduction method, source bytes, link-frame convention, uncertainty, and
   engineering acceptance.
3. Measure the installed factory base/clamp envelope and its board-frame pose.
   Include fasteners or protrusions that can enter the swept workspace.
4. Identify the exact received holder, camera module, connector/plug, strain
   relief, and locked mounting configuration. Measure complete envelopes and
   accepted transforms for `holder` and `camera_module`; do not infer them from
   the camera's mounting-hole pitch alone.
5. Define the keyboard and phone contact tools separately, including their
   rigid `hand_tcp` transforms, full envelopes, compliance/flex uncertainty,
   and route-specific installation identity.
6. Capture the moving cable's conservative configuration-dependent envelope.
   Add a bounded explicit waypoint-sequence/deformable-sampler query boundary,
   then bind evidence-bearing cable geometry at every evaluated sample; the
   current two-endpoint sweep cannot accept those intermediate samples.
7. Replace the six nominal RC03 proxies with measured installed board, device,
   station, and nearby-fixture geometry where those bodies are required for
   physical reasoning.
8. Approve an evidence-backed clearance policy with positive minimum
   separation and explicit per-body geometry and pose uncertainties. Validate
   it against metrology, calibration residuals, repeatability, backlash, flex,
   payload, and the intended operating speed.
9. Review each global exclusion against the accepted envelopes. Promote only
   genuinely invariant pairs to `ENGINEERING_GLOBAL`; keep typing/tapping
   contact allowances phase-local.
10. Project route joint states and accepted frame transforms into
    `CollisionPose` values and call the pose/sweep engine for park, transit,
    hover, approach, contact, and retract. Preserve the report hashes alongside
    the route evidence.
11. Add a validated continuous or conservatively swept-volume collision method
    if hardware release requires collision freedom between samples. The
    existing discrete sweep cannot make that claim.
12. Re-run the strict readiness command, then the route-level diagnostics. Keep
    motion/contact authority in the independent safety and commissioning gates;
    collision readiness alone must never release them.
