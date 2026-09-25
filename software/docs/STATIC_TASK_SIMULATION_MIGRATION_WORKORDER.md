# Static-camera task simulation: integration work order

Date: 2026-09-10; updated 2026-09-13. Status: **increment 1 implemented;
increment 2 semantic edge added; static context/task-route migration and IK
diagnostic implementation remain open**. Increment-1 verification is in
`TASK_FEEDBACK_AND_FULLSIZE_CHECKPOINT.md`.
Companion to `CAMERA_ARM_DEVELOPER_PLAYBOOK.md` and
`ONBOARDING_APPLICATION_COMPLETION_MATRIX.md`. No hardware/build change, live
motion, contact, calibration acceptance or controlled-freeze promotion occurs
by writing this document.

Read-only follow-up on 2026-09-12 is recorded at the end of this document. It
reproduces the legacy IK gaps and inventories remaining integration boundaries;
it does not migrate the task simulator or change the controlled geometry.

## Evidence and the actual mismatch

The real wizard browser walkthrough is retained in
`CAMERA_WIZARD_USABILITY_HANDOFF.md`, including the exact verified export and
source fingerprint. Its two `simulate_task` reports use nominal board/device
geometry, contain physical holds, and identify provisional IK gaps. A worker
returning `SUCCEEDED` currently means its CLI exited successfully, not that
all sampled points converged or that a physical path is executable.

The source chain explains why the selected camera is not yet represented
throughout task simulation:

| Layer | Current implementation | Consequence |
| --- | --- | --- |
| Selected design | `config/camera_architecture_plan.json` selects static overhead primary; secondary is unselected | Correct design intent, no received-unit qualification |
| Original onboarding | Static contract collection/review checks the architecture, camera and support inputs | Accepting that contract does not change another locked simulator |
| Semantic task | `typing/development_profiles.py` builds default `KeyboardProfile`/`PhoneProfile` | Both inherit `eye_on_arm_extrinsic` |
| Dependency closure | `calibration/requirements.py` defines legacy camera intrinsics and makes `arm_board` depend on eye-on-arm | Replacing only a displayed name would leave the wrong graph |
| Alignment | `workcell/alignment.py` explicitly expects those legacy dependency sets | A partial edit must be rejected, not silently repinned |
| Source lock | `config/simulation_bundle_lock.json` binds Freeze 011, target profile, camera manifest, geometry and URDF | Existing task reports remain legacy-model evidence even though newer design planning exists |
| Report/UI | `application/simulate.py` distinguishes required checks and optional sampled IK; operation summaries already expose `steps[].report_status` | Show those limits visibly; do not translate process completion into feasibility |

The current target catalog uses synthetic key centers within nominal device
dimensions. It is not a surveyed keyboard drawing or measured screen map. Its
semantic-content hash includes calibration dependencies as well as key mapping.
Keep that binding meaningful during migration.

## Increment 1: accurate task-result presentation

Use existing service-owned operation summaries; do not introduce a second
simulation, automatic result fetch, automatic retry or stage mutation.

- Label task simulation operation status as worker/process status.
- Interpret only the exact `simulate_task` step for the exact action; ambiguous,
  malformed, missing, incomplete or inconsistent summaries get an unavailable
  interpretation, never an optimistic fallback.
- Show required-check failure, provisional IK gaps, and all-sampled-converged
  as distinct diagnostic outcomes. Even the last is sampled nominal evidence,
  not continuous-path, collision, calibration or execution qualification.
- Keep full retained results and export unchanged and accessible.
- On the Tasks page, disclose that the current locked task simulator still
  uses the legacy camera calibration graph. The new overhead commissioning
  workflow is not proof of task-model migration.
- Verify the actual renderer with gap/pass/fail/missing/duplicate/mismatched
  reports, navigation and zero preview/execute/device effects; inspect in a
  real browser after implementation.

Prepared tests: `tests/unit/test_wizard_task_simulation_feedback_ui.py`.
On the unchanged application fingerprint `70f10a3e...bde902`, the initial red
run returned **33 expected failures and three passes**, 3.42 s, JUnit
`.codex-preserved/task-feedback-red-20260910-01.xml`. It detects the absent
visible interpretations and legacy-model notice. The short finite-DOM run
overlapped full-history run 02; no production source, storage reader, clock or
admission input changed. This is test-development evidence, not acceptance.

## Increment 2: architecture-bound calibration and semantic contracts

Do not edit historical evidence or blanket-replace `eye_on_arm_extrinsic`.
Keep the legacy graph/profile as a named historical option. Introduce a
versioned static-primary simulation contract with explicit architecture and
source hashes. It must be impossible to mix a static profile with a legacy
camera manifest/graph through a default parameter.

The static graph must express these distinct prerequisites:

1. Exact camera/lens/focus/aperture/mode/crop identity and intrinsics.
2. Measured six-tag corner and optical-plane map in board frame `B`.
3. Robot reference (installed signs/zeros/ranges), separately qualified.
4. Fixed `Wv_T_C_overhead_optical` extrinsic: independently surveyed robot/board
   registration plus a simultaneous observation, or a separately observable
   calibration dataset. Tags alone are not robot-frame evidence.
5. Runtime `Wv_T_B = Wv_T_C_overhead_optical * C_overhead_optical_T_B` with
   measured validity/uncertainty, static support witness and freshness.
6. Independent controller-frame correlation; no assumption that `R_ctrl`,
   `Wv`, board or camera frames are equivalent.
7. Per-device geometry, route TCP/compliance/travel, and independent keyboard
   or Android outcome observation.

Separate calibration seeding from runtime registration to avoid a circular
dependency (`arm_board` cannot both establish and depend on its own extrinsic).
Preserve explicit transform direction, units and frame names. Reuse existing
intrinsics/settings-epoch contracts where applicable, but a synthetic rehearsal
assessment cannot become installed calibration evidence.

Preserve the commissioning-stage distinction already present in
`config/physical_onboarding_stage_catalog.json`: stage 8 owns passive
**camera-to-board** registration with actuator power disconnected. It does not
establish the robot-world camera extrinsic. Arm identity, power/startup and
feedback are stages 9–12; robot/board and controller-model correlation belong
to stage 13. Do not introduce an energized robot-reference prerequisite into
stage 8 or claim that its board pose establishes `Wv_T_C_overhead_optical`.
The task dependency graph must require the later robot-frame evidence without
creating a commissioning cycle.

Tests: deterministic prerequisite closure; unknown/cyclic/mixed-architecture
rejection; stable content hashes; legacy replay remains legacy; calibrated and
unmeasured origins remain distinct; an unselected secondary cannot satisfy the
primary; any relevant settings/support/layout change invalidates downstream
bindings. Add fixtures before migrating the wizard's default task route.

## Increment 3: coherent static simulation bundle and observations

Create a separately versioned bundle, then atomically bind its semantic IDs and
hashes, camera contract, scene, target catalog, calibration graph and report
schema. Follow existing source-lock validation, preserving the old bundle and
reports. Geometry must still match the actual build source; do not manufacture
new board measurements. Do not promote a physical freeze as a side effect.

Simulate the overhead camera fixed relative to the workcell, with the arm
moving independently. Cover all-six-tag clear observation poses, T0–T3 solve
and independent K0/P0 checks, tool/arm occlusion, stale/duplicate frames,
settings drift, support/board/device displacement and re-observation after
retraction. Do not reuse moving-camera extrinsics or synchronized joint pose
as if they were static-camera truth. No automatic secondary-camera fallback.

The wizard must state which bundle/architecture was simulated and retain exact
source identities in reports and exports. Existing original onboarding stages
remain authoritative for physical commissioning; simulation cannot skip them.

## Increment 4: investigate, do not hide, the IK gaps

The retained `hi` examples converge at 2/8 sampled keyboard points and 7/8 phone
points. Both fail the same nominal park point; the keyboard also has failures
near the key plane. These observations do not distinguish numerical solver
limitations from incorrect nominal transforms/TCP or true configuration limits.

- Reproduce a bounded deterministic point set from the retained report using
  its pinned URDF, frame transform, tool case, limits and solver options.
- Separate position error, tool-normal error and controller/URDF intersection
  failures; retain every seed/attempt and compare forward-kinematic residuals.
- Check axis signs, transform direction, TCP extension and fixture coordinates
  against the source contract before proposing solver changes.
- Compare bounded deterministic alternative seeds/algorithms diagnostically;
  preserve original tolerances and command limits. Never count a pose outside
  the controller intersection as a successful executable solution.
- Expand to every supported target and intervening path, then add continuous
  swept-volume checks. Eight sampled points are only a screen.
- A necessary build/layout/tool change requires a separately reviewed source
  revision and new simulation evidence, not silent movement of the keyboard.

## Integration and handoff

Keep production source fixed until any active source-bound acceptance run
terminates. Tests/docs may be prepared independently; do not alter its inputs,
readers, clocks, leases or evidence. After changes, run focused tests first,
source/lock consistency and selected regressions next, then real browser
rehearsal with separate keyboard/phone results and verified unique export.

Acceptance for this work order is accurate UI interpretation plus a coherent
static task simulation lane and reproducible IK diagnostics. It is not physical
camera/arm qualification. Record the remaining hardware and execution gates
explicitly in the completion matrix; never describe this software gap as only
waiting for hardware.

## Read-only P2/P3 investigation — 2026-09-12

Performed while the independent P1 full-history run 04 constructs its USB
predecessors. No production/configuration/test input of that run changed.
The ordinary CLI simulations and the bounded diagnostic solver comparisons
below generated zero hardware commands and accessed no camera or arm.

### Integration boundaries confirmed

| Existing component | Specific join required for P2 |
| --- | --- |
| `models/profiles.py` and `typing/development_profiles.py` | Keep legacy defaults historical; add explicitly architecture-bound semantic profiles. Dependencies participate in semantic hashes, so IDs/hashes must migrate together. |
| `calibration/static_phase1_requirements.py` | Reuse the existing 15-node B0477 graph, not a replacement graph. Its `phase1_static_extrinsic` currently means camera-to-board; do not relabel it as a robot-world extrinsic. |
| `application/context.py` | Load/revalidate a coherent selected simulation lane. It currently joins the legacy hardware profile, manifest, bundle, scene and targets at every service boundary. |
| `simulation/bundle.py` | Its v1 six-artifact roster and arm-frame semantic hash are exact. Use a separately versioned static bundle rather than making the historical loader accept arbitrary alternate paths. |
| `simulation/profile.py` and `workcell/alignment.py` | Current checks explicitly require eye-on-arm and the old calibration sets. Static validation needs an explicit architecture branch/contract; removing checks would hide mixed inputs. |
| `application/simulate.py` | Current fixed synthetic overview is disclosed as a test fixture, while reports still include missing eye-on-arm transforms. Static output must bind its actual selected graph/pose assumptions and retain separate IK/observer limits. |
| `simulation/static_mission_route.py` | Existing dense-route collision input checks cover endpoints and supplied joint-interpolated midpoints. Reuse them, but do not call this continuous swept-volume proof or claim that the module derives those poses from FK. |

The static graph's settings description still mentions one-metre focus evidence.
Reconcile that nominal/research wording with the user's deferred installed-height
decision when defining the versioned static contract. Neither that text nor the
approximately 10-inch bench observation is an installed calibration measurement.
This investigation did not alter a graph hash or optical requirement.

### Reproduced legacy `hi` task results

Commands: `rocell.ps1 simulate --device keyboard --text hi --json` and the same
command with `--device phone`. They use the unchanged Freeze-011 bundle, nominal
100 mm tool case and exact pinned URDF
`a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`.

- Keyboard: 2/8 sampled points converge; one additional unique point is omitted
  by the current eight-point diagnostic sampling policy. Both transit points
  converge; park and the sampled low keyboard points do not.
- Phone: 7/8 sampled points converge; the failed point is the same park.
  Report hash: `532fe41f8a01ba2f3930d6d4140a42756d222c1489243142c17504cf410f1576`.
- Common park: board `(305, 400, 70)` mm; positional residual 2.575498 mm and
  alignment residual 0.078915 rad. No solution is exposed for the failed point.
- Both CLI reports remain
  `PASS_REQUIRED_SIMULATION_CHECKS_WITH_PROVISIONAL_IK_GAPS_AND_PHYSICAL_HOLDS`.
  Process success is not complete reachability, camera migration or execution.

### Bounded numerical and tool sensitivity checks

An in-memory diagnostic used the same source-loaded board transform, exact URDF,
controller/URDF intersection, gripper state and ready seed. It evaluated park and
the nominal H/I contact points directly, without the task run's continuation
seeds. Therefore its contact residuals are not asserted identical to that run.
No profile or solver default was edited.

| Point | 4 attempts × 45 iterations | 10 attempts × 140 iterations |
| --- | --- | --- |
| Park `(305,400,70)` | Not converged: 2.575498 mm / 0.078915 rad | Not converged: 2.981031 mm / 0.076584 rad |
| H contact `(216.55,154,20)` | Not converged: 1.512747 mm / 0.073376 rad | Not converged: 1.553454 mm / 0.073231 rad |
| I contact `(249.85,175,20)` | Not converged: 2.936796 mm / 0.134493 rad | Not converged: 2.996993 mm / 0.134267 rad |

Both branches retained 0.20 mm position and 0.003 rad alignment tolerances. The
comparison shows this bounded increase in numerical effort did not resolve the
points; it does **not** prove global infeasibility. Selection minimizes the
weighted combined residual, so the position component alone need not improve.

The same three points were also checked at the profile's existing 0, 80 and
120 mm virtual tool offsets using the original 4×45 numerical budget. The
hand-TCP-only park converged, but its keyboard contacts did not. Neither 80 mm
nor 120 mm converged at all three points. At 120 mm, H contact improved to
0.512005 mm / 0.025581 rad but still failed both unchanged tolerances.

Next diagnosis must retain attempt/seed/termination details and inspect the
constraint-active joints, transform/TCP convention and alternative bounded
solvers. Do not increase live joint limits, pick another tool, move a fixture or
hide the park failure based on these observations. No changed build is approved.

### P2 first implementation ticket: close the context/semantic join

Additional read-only review during P1 run 05 (2026-09-12) confirms that the
existing static graph rehearsal is not yet an independent static task context.
`static_phase1_context_hashes()` deliberately revalidates the historical
`SimulationContext`, then adds the three static source files. It still derives
keyboard/phone semantic hashes from the historical development-profile factories.
Do not promote that rehearsal to a migrated task route merely by changing its
display label or using its `NOMINAL_ONLY` artifacts as installed calibration.

The smallest coherent P2 implementation should proceed in this order after
source-bound P1 verification terminates:

1. Add explicitly named static semantic-profile factories with versioned IDs
   and static requirement closures. Reuse `KeyboardCompiler`/`PhoneCompiler`
   and their existing supported characters/state transitions. Their outputs
   are named semantic actions, not robot commands; no compiler rewrite or
   expansion to uppercase/modifier chords is necessary for camera migration.
2. Add a closed static bundle/context loader, or an equally explicit tagged
   version branch, which binds robot/build geometry, target catalog, semantic
   profiles, graph ID/hash, camera architecture, B0477 profile and support design.
   Preserve the old v1 loader and six-artifact roster. Never accept arbitrary
   paths or reinterpret an old manifest as an approved static-camera freeze.
3. Reuse source-loaded scene geometry and numerical types where their meanings
   match. `SimulationScenario` already separates numerical inputs from hardware
   identity. Do not carry over `load_simulation_hardware_profile()`'s IMX335-B
   module/holder/carrier assertions into the B0477 path, or delete those checks
   from the historical loader. Test exact equality of unchanged board/device/
   tag coordinates and URDF bytes across the two modeled routes.
4. Make static context revalidation reconstruct that same explicitly selected
   route. It must not call today's default legacy loader and then patch fields
   in memory. Reject a modified dataclass, stale source, mixed graph, mismatched
   semantic hash or legacy target catalog claiming a static profile ID.
5. Make the static graph rehearsal consume the selected static context hashes.
   Retain its original historical-context entry point for historical tests and
   reports; do not install its in-memory synthetic artifacts in the physical
   registry. Keep the exact context-dependency key set and per-edge invalidation.
6. Join application reports and CLI/wizard selection only after those contracts
   pass. Reuse existing registered task actions, operation logs and exports;
   disclose architecture/graph/profile versions and nominal geometry in every
   resulting report. Legacy selection must remain visibly legacy.

Required new contract cases: both devices; deterministic profile/graph hashes;
all supported semantic targets; unchanged key/tap behavior; unknown/mixed IDs;
wrong model/manifest/target hash; replacement context fields; support/settings
drift; all-six-tag versus missing-tag observations; and zero physical effects.
Neither a static graph pass nor a task process exit resolves the retained IK
gaps or proves whole-path collision clearance.

Keep observed facts separate from existing candidate data. The support design
currently records nominal 1,000 mm entrance-pupil height, a 950–1,050 mm adjustment
range and nominal full-resolution 9 fps as **screening inputs**. The camera bench
observed approximately 10-inch focus and 8 fps; it did not establish installed
height, full-board coverage or an accepted mode policy. The architecture plan's
installed height, commissioned mode and persistent identity remain null. P2 may
use labeled synthetic camera parameters, but must not silently resolve these
P5/P6 hardware decisions or change source locks to make the values agree.

This entry adds implementation guidance only. No static profile, graph, source
lock, support dimension or task default was changed while run 05 was active.

## S1 semantic implementation — 2026-09-13

The additive `typing/static_development_profiles.py` now supplies:

- `static_development_keyboard_profile()` and `static_development_phone_profile()`:
  explicitly versioned static-primary IDs and the existing graph's complete,
  prerequisite-first per-device calibration closure.
- `compile_static_development_text(device, text)`: the existing compiler behavior
  with those profiles; no coordinates, controller values or hardware dispatch.
- `static_semantic_profile_binding(profile)`: exact-profile validation and a
  detached binding of profile content, graph ID/hash and B0477/static architecture.
  Geometry/installed-calibration binding and physical authority remain false.

The mapping, supported characters, phone state checks and normalized text hashes
remain identical to their legacy counterparts. Both historical profile hashes
remain the pinned values. Changed profile IDs, mixed legacy dependencies, changed
key mappings/state and caller JSON are rejected. Graph-purpose changes invalidate
the graph/binding hash even when artifact IDs remain unchanged.

The final focused development selection passed 30 tests in 0.31 s, including a
no-file/process/network-IO guard, both devices, all supported characters, repeats,
empty input and CRLF, unsupported characters, prerequisite order and graph drift.
Focused mypy passed the one production module. Earlier failed and passing checks
are preserved under checkpoint 09; this live-tree slice is not in that checkpoint's
earlier frozen camera/storage input and is not a fixed static-bundle acceptance.
The subsequent existing-model/typing and static-calibration compatibility
selection passed 55 tests in 1.09 s, including those same 30 cases.

Next: implement the separately versioned static bundle/context and explicit target
catalog joins before selecting this route in CLI/UI. Do not pass these new IDs to
the old catalog, change historical defaults, relabel a legacy context or promote
nominal calibration artifacts. Geometry, support height, optics, source locks and
all retained IK gaps are unchanged. S1 remains open.

## S1 target-catalog join — 2026-09-13

`config/static_nominal_target_profiles.json` is a separate catalog with explicit
static semantic IDs/hashes and the full graph/profile binding. The existing
nominal catalog is unchanged. `targets/static_nominal.py` checks its fixed
geometry seed hash, exact document/semantic/graph contract, bounded JSON and
unchanged reads before returning the existing numerical catalog type.

The loader reads the new catalog through the existing target/workcell parser;
it does not load and relabel a legacy simulation context. All 46 keyboard and
29 phone targets have exactly equal geometry to the historical nominal seed,
including device origins and target regions. Every supported new static
semantic action resolves to the same named region. The inherited geometry is
still synthetic/unmeasured; its source reference is not an installed survey.

Development verification: 20 new cases plus the prior semantic/model/calibration
selection passed **75 tests in 1.67 s**. Tests cover mixed IDs/hashes, moved
targets/device origins, graph/source changes, authority and Boolean substitutions,
extra/missing fields, duplicate/nonfinite/oversized JSON and mid-read replacement.
The first development run retained one test-fixture error using the wrong layout
field name; after changing the fault injection to the real `nominal_origin_xy`
field, the intended numerical-origin rejection passed. Focused mypy passed the
new target loader. Details are in checkpoint 09's development evidence.

The target slice is outside the frozen camera acceptance input. Static context,
scenario/source bundle, graph rehearsal integration, CLI/UI route and expanded
IK diagnostics remain open. No geometric simulation is claimed to use this
catalog until that route is implemented and revalidated as a whole.
