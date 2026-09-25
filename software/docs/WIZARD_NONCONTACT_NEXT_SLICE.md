# Stage 14: hardware-free noncontact diagnostic integration plan

Status: **AUDITED PLAN — NOT IMPLEMENTED BY THIS DOCUMENT**. NC-01 now has a
separate [implementation record](WIZARD_NONCONTACT_IMPLEMENTATION.md); NC-02/03
and physical acceptance remain open. This plan describes the next
bounded slice after the retained stage-13 reference-frame rehearsal. It does
not change the stage catalog, the wizard, source configuration, a physical
permit, or any power/motion/contact hold.

This audit read the existing implementation, tests and recorded study notes.
It did **not** rerun IK, virtual missions, sensitivity campaigns or hardware
tests. Numerical results quoted below are identified as previously recorded
results, not fresh results of this audit. New integration must produce and
retain its own source-bound evidence before showing a current result.

## 1. Decision and authority boundary

Build a **noncontact preparation diagnostic**, not a move-the-arm button. Its
first purpose is to show, independently, what is covered, what failed, what
was not evaluated and what still needs physical evidence. Successful execution
of a diagnostic is not successful acceptance of the workcell.

The canonical stage is `PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE`
(`noncontact_acceptance`). The
[stage catalog](../config/physical_onboarding_stage_catalog.json) assigns it:

- effects `MANUAL_ENERGY_CHANGE` and `NONCONTACT_ARM_MOTION_EXTERNAL`;
- power requirement `EXTERNAL_NONCONTACT_PERMIT_END_DISCONNECTED`;
- intake `INT-054`;
- owned artifacts `collision_configuration`, `arm_induced_visibility_atlas`
  and `noncontact_acceptance_report`;
- eventual bundle components `noncontact_qualification_phase_receipt`,
  `untouched_final_acceptance_phase_receipt`, `noncontact_acceptance_report`,
  `arm_induced_visibility_atlas`, `collision_configuration` and
  `accuracy_budget_assessment`.

None of those physical qualifications is supplied by the proposed rehearsal.
Its composition remains `HARDWARE_INCAPABLE_REHEARSAL`, with zero actual
device opens, camera frames, serial writes, robot motions and contacts.
Virtual contacts must have separate counters and must not be renamed
noncontact motion. The independent post-stage-12 power observation is
synthetic dependency evidence, not present physical power knowledge.

This follows DEV-010/DEV-011 in the
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md): exact geometry and
calibration dependencies, separate reference/noncontact release, an untouched
final partition, no fallback to nominal calibration, and no rehearsal PASS or
export granting typing/tapping authority. The stage-14 inventory in
[remaining stage integration](WIZARD_REMAINING_STAGE_INTEGRATION.md) remains
the larger implementation roadmap.

## 2. Do not collapse these different claims

| Evidence | What is actually checked | What it does not establish |
| --- | --- | --- |
| Current stage 13 | Nominal frame graph; six source-defined FK poses; four training and two held-out rigid-fit pairs; coordinate roundtrips for keyboard `A` and phone `key_q` | Neither target was solved as an IK goal by that roundtrip. No all-75 coverage, route, collision, calibrated controller joints or physical reference |
| Independent target sweep | A chosen target/tool/phase matrix of independently solved poses, plus independently solved parks | Sequential routes, previous-joint continuity, collision or arbitrary text |
| Trajectory simulation | Ordered, densified Cartesian waypoints, sequential seeded IK and sampled joint checks | Continuous clearance, physical singularity/force/dynamics or actual controller execution |
| All-target mission coverage | Each of 46 keyboard and 29 phone targets on its own park-to-target-to-park route | Inter-target joint-state equality, arbitrary multi-target sequences or complete collision |
| Placement sensitivity | Perturbed nominal geometry versus an unchanged nominal command point | Measured error bounds, motion repeatability, actual press/tap depth or camera calibration |
| Collision diagnostics | Explicit supplied geometry at explicit sampled poses, with an explicit clearance policy | Missing geometry, cable motion between samples, continuous swept clearance or installed qualification |
| Virtual keyboard/Android missions | In-memory trajectories, contact outcomes, observations, park and cleanup | Physical noncontact acceptance, actual key/phone actuation or a fresh B0477 image per action |

Even a 75/75 sampled-route result must retain its exact placement, tool and
park hypothesis. It cannot inherit the identity of the stage-13 nominal
transform merely because both use the same board and URDF.

## 3. Source and geometry provenance

Use `load_simulation_context(workspace, manifest_path)` and
`revalidate_simulation_context(context)` from
[application/context.py](../src/rocell/application/context.py). They reconstruct
the source-linked build snapshot, frozen bundle, hardware profile, scenario,
scene, target catalog and alignment. The revalidator compares actual loaded
values, not just digest strings supplied by a caller.

The nominal geometry documented by
[placemat sensitivity](PLACEMAT_GEOMETRY_SENSITIVITY.md) is:

| Item | Digital input, not a hardware measurement |
| --- | --- |
| Board | 610 × 457 × 18 mm |
| Keyboard | Board origin (85, 85) mm; envelope 315 × 147 × 21 mm; 46 synthetic ANSI targets at nominal Z=21 mm |
| Phone | Board origin (499.2, 84.2) mm; envelope 77.9 × 164.4 × 7.9 mm; 29 synthetic Gboard targets at nominal screen Z=11.9 mm |
| Static camera | Purchased B0477/IMX283 source profile; nominal optical centre above (305, 228.5) mm and nominal entrance-pupil Z=1000 mm |

Read these from verified sources at execution, not copied constants in a new
evaluator. Retain units and frame names explicitly. Device planes and safe
regions remain nominal. The camera's architecture/profile/support hashes are
a dependency binding unless the calculation actually consumes the exact
retained camera evidence; they are not themselves image measurements.

There are at least two deliberately different geometry domains:

1. Stage 13 uses the nominal source-defined frame chain and nominal 100 mm
   tool offset. Its two-target roundtrips are an internal mathematical check.
2. `run_default_virtual_session` loads the explicit
   [rank-1 virtual profile](../config/virtual_commissioning_profile.json),
   `ROCELL-VIRTUAL-COMMISSIONING-RANK1-001`. It is labelled
   `UNMEASURED_SENSITIVITY_OVERLAY`: base-axis/clamp hypothesis X=385 mm,
   rear-edge offset Y=75 mm, base-link Z=70.1 mm, yaw −105 degrees,
   keyboard tool 120 mm, phone tool 100 mm, and park (290, 10, 70) mm.
   `B_T_Ru` and derived `B_T_Wv` are different transforms and must retain
   their exact source representation.

The second is not an authorized correction to the first and not a fabrication
instruction. New integration must show this difference. Do not silently
substitute the passing virtual profile into a nominal stage-13 check.

## 4. Existing numerical and lifecycle entry points

### Independent pose coverage

`run_target_sweep(context, *, devices, tool_case_ids, phases, target_ids=None)`
in [target_sweep.py](../src/rocell/application/target_sweep.py) uses the pinned
URDF, nominal board transform, selected tool offset, fixed gripper and bounded
`RoArmM3NumericalIk`. It retains per-row convergence, position and alignment
residuals, attempt counts, selected joints and controller-intersection margin.
Targets are independently solved; park is independently screened per tool.

`CONTACT` subtracts nominal contact overtravel from the target Z; `APPROACH`
and `HOVER` add the respective source-defined heights; `TRANSIT` uses the
highest scene obstacle plus source-defined clearance. For the first strictly
noncontact *pose* diagnostic, an explicit HOVER/TRANSIT subset is suitable;
it is not a route. Report all selected IDs, phases and tool cases, including
every rejected row. With all 75 targets and one tool case this is 150 pose
rows plus that tool's park result, not all four phases.

`complete_matrix` has an existing precise meaning: both devices, every
configured tool case, all four phases and the entire catalog. It must remain
false for a HOVER/TRANSIT-only request even when all 75 targets are present.
Use a separate `selected_catalog_complete` count rather than relabelling it.
Existing statuses distinguish `FEASIBILITY_GAPS_REPORTED`,
`PASS_SELECTED_MATRIX` and `PASS_COMPLETE_MATRIX`.

### Ordered sampled routes

`run_trajectory_simulation(context, plan, study_input, policy)` in
[trajectory_simulation.py](../src/rocell/application/trajectory_simulation.py)
constructs the nominal geometric route, densifies segments, and seeds each
bounded IK solve with the preceding selected state. Selected states must
satisfy the controller/URDF intersection, normalized arm-joint margin and
maximum adjacent sampled-joint delta. A bounded weighted five-constraint
solver-task Jacobian rank diagnostic is calculated at otherwise-valid states.
Nominal AABBs screen the tool-tip centreline. Robot-link, self, gripper,
tool-volume, cable, full physical manipulability, dynamics and force remain
unsupported. No T104 bytes are generated.

`revalidate_trajectory_simulation_report(context, plan, report)` does not
rerun IK. It reloads source/model/implementation identities, reconstructs
nominal geometry and recomputes FK, task residuals, limits, joint deltas and
the Jacobian diagnostic from retained selected states. It rejects injected
test-solver reports. This is useful validation, but is **not a filesystem-free
retained verifier**: source reload and numerical recalculation are deliberate.
A future reopen path must either provide an explicit source-reading boundary
before a pure verifier or implement a retained-source attestation contract;
do not claim the current function is a pure byte decoder.

`run_mission_route_coverage(context, study_input, park_xy_board_mm, policy)` in
[mission_route_coverage.py](../src/rocell/application/mission_route_coverage.py)
materializes exactly 75 semantic routes through `mission_semantic_routes`.
Each starts from park and contains canonical TRANSIT/HOVER/APPROACH/CONTACT/
RETRACT/TRANSIT/PARK endpoints. These are **virtual contact routes**, not a
noncontact-only plan. Individual route rejections do not skip later targets;
source, contract or resource failure aborts the complete report.

Default policy uses 30 mm Cartesian steps, 0.35 rad adjacent joint steps,
0.01 normalized arm-joint margin, one refinement round, at most 64 waypoints
per round and 128 IK solves per route. Hard aggregate caps include 9,600 IK
solves and 9,600 waypoint records. Device-separated chunks of eight are
orchestration only. Every route deliberately repeats canonical source/model
validation; avoiding that cost requires a separately reviewed immutable
shared-run capture contract, not removal of checks.

Important retention gap: the mission coverage result retains compact route
metrics, first failures and trajectory report hashes, **not every complete
underlying trajectory report**. A hash is not reopen-verifiable numerical
evidence. Before wiring all-target route acceptance, retain the complete
per-route reports through a narrowly reviewed sink or a closed orchestrator
that calls the canonical trajectory boundary per target. This is new work.

`build_dense_route_schedule` in
[dense_route_schedule.py](../src/rocell/application/dense_route_schedule.py)
can join accepted route waypoints to nonwire controller targets. It explicitly
retains uncommissioned controller-frame correlation. It is not needed for the
first stage-14 screen and must not become a hidden physical command path.

### Geometry sensitivity

`run_placemat_uncertainty_simulation(context, bounds=None, *, support_path=None,
camera_profile_path=None)` in
[placemat_uncertainty.py](../src/rocell/application/placemat_uncertainty.py)
holds the commanded point at the nominal target and perturbs board
registration, device placement, local target maps and TCP. It computes local
XY error, signed safe-region margin, absolute Z separation, adjacent-target
ambiguity and device/board envelope violations. Whole-device board violations
conservatively mark all targets of that device for that case.

The defaults are explicitly unmeasured assumptions: board and device XY
±1 mm, Z ±0.5 mm, yaw ±0.2 degrees; target-map XYZ ±0.5 mm; TCP XYZ ±0.75 mm.
The deterministic generator produces 59 cases × 75 targets = 4,425
observations. `PlacematUncertaintyBounds.zero()` is a separate one-case
nominal control, not measured zero uncertainty. The implementation caps
targets at 128, cases at 96 and observations at 10,000, and revalidates sources
again after calculation. Bind exact bounds, case IDs, support and camera
profile in retained evidence.

### Virtual pipeline and existing onboarding probe

`run_default_virtual_session(workspace, device, requested_text, *, runtime_path,
fault_script)` in [virtual_session.py](../src/rocell/application/virtual_session.py)
loads the locked rank-1 profile, compiles text and exercises in-memory arm,
device, vision and outcome components. It is useful for pipeline and cleanup
tests, not proof of nominal-build feasibility.

`run_b0477_bound_virtual_acceptance(workspace_root, *, keyboard_text="test",
phone_text="test.", registration_sequence=0, normal_vision_report=None,
tag_loss_vision_report=None)` in
[b0477_virtual_acceptance.py](../src/rocell/application/b0477_virtual_acceptance.py)
validates the B0477 support/optical source stack, runs those two virtual
sessions, and binds observations to **one shared B0477 preflight context**.
The original virtual session uses a historical raster internally; the wrapper
does not turn it into per-action B0477 pixels. Supplied typed normal/tag-loss
reports are an in-process optimization, not authenticated deserialization.

`DeterministicOnboardingProvider._probe_noncontact_acceptance` in
[first_power_on_onboarding.py](../src/rocell/application/first_power_on_onboarding.py)
already exercises representative nominal missions and an actual in-memory
first-waypoint `ARM_STALL`. The fault checks zero subsequent virtual
waypoints/contact/observations, unchanged output and closed plant. Nominal
code expects 109 virtual waypoints, nine virtual contacts and nine bound
observations across `test` / `test.`. It returns the explicit status
`NONCONTACT_ACCEPTANCE_REHEARSED_PHYSICAL_COLLISION_BLOCKED`.

Do not adopt that private probe as the new M1 stage receipt: its sequence-101
normal/tag-loss lookup and legacy collision audit are not automatically the
current session's reviewed stage-8 evidence. Adapt the actual retained pair
only after exact verification, or mark this diagnostic's camera context as a
separate source-bound synthetic fixture. Never rerender default evidence and
call it the session's installed registration.

## 5. Collision support and the static-camera mismatch

`assess_current_collision_readiness(context)` in
[collision_readiness.py](../src/rocell/application/collision_readiness.py)
verifies the actual pinned URDF and audits source-bound body requirements.
Existing tests assert zero URDF collision elements, missing geometry for the
base, links 1–5 and gripper, and unknown clamp/tool/camera-attachment geometry.
The current historical contract has 19 requirements and still names the
arm-mounted camera holder/module/connector/moving-camera cable. Its six
nominal workcell bodies are diagnostic AABB proxies. Preserve this report as
a **historical readiness audit**, not a complete inventory of the updated
static B0477 installation.

The updated contract exists separately in
[static_route_collision.py](../src/rocell/simulation/static_route_collision.py):
`STATIC_ROUTE_BODY_REQUIREMENTS` lists 26 bodies. These cover seven robot
bodies, contact-tool body and tip, configuration-sampled arm harness,
board/clamp/keyboard/phone, portal posts/crossbar/camera boom/two light booms,
B0477 enclosure/lens/connector, fixed USB route and two lights. Its required
source keys are `robot_model`, `workcell_layout`, `target_profile`,
`static_support_design`, `b0477_mechanical_design`, `fixed_usb_route_design`,
`lighting_design`, `arm_harness_design` and `contact_tool_design`.

No complete installed geometry is synthesized from those names. A new
source-to-static-contract builder is an integration prerequisite. Missing
required bodies remain missing; guessed boxes must not be labelled measured.
Synthetic complete contracts may exercise the evaluator separately as
fixtures, with unmistakable synthetic provenance.

Existing collision calculations are usable without hardware:

- `audit_collision_geometry(contract)` checks required coverage and evidence
  state. `evaluate_collision_pose(contract, pose, policy)` in
  [collision.py](../src/rocell/simulation/collision.py) requires complete
  geometry, complete poses and an explicit positive clearance/uncertainty
  policy, inflates bodies, and performs broad/narrow primitive checks.
- `evaluate_collision_sweep` is a bounded, discrete rigid-body sweep. It
  refuses to interpolate required configuration-sampled cable geometry.
- `evaluate_static_b0477_target_route(contract, route, policy)` evaluates its
  seven phases and all six supplied intermediate-sampled segments. Only the
  exact tool-tip/designated-device overlap at CONTACT receives an allowance;
  intermediate poses, APPROACH and RETRACT do not inherit it.
- `evaluate_static_b0477_mission_route(trajectory, contract, policy,
  target_bindings, endpoint_poses, incoming_midpoint_poses)` in
  [static_mission_route.py](../src/rocell/simulation/static_mission_route.py)
  binds every accepted dense endpoint and explicitly supplied joint midpoint
  to exact trajectory and command ordinals. The caller supplies complete
  transforms and freshly sampled harness envelopes. This function does not
  generate body poses from FK or prove clearance between samples.

The CONTACT-aware contracts are reusable simulation diagnostics, not a
ready-made noncontact-only plan type. A future physical noncontact route must
be an explicit separately released above-surface plan with no contact
exclusion. It must not be implemented by quietly relabelling these routes.
An arm-induced tag/device visibility atlas is still a separate missing
artifact; geometric clearance does not establish camera visibility.

## 6. Accuracy-budget calculation and missing evidence

`assess_target_accuracy_budget(policy, observations, *, term_bindings,
assessment_context, target_geometry)` in
[accuracy_budget.py](../src/rocell/calibration/accuracy_budget.py) uses strict
typed evidence with frame, operating domain, sample basis, bound method,
coverage, dependency hashes, observation time, expiry and configuration epoch.
Digest consistency alone does not establish trust.

The ten noncontact terms are board pose, intrinsics/distortion, camera-board
registration, static-support drift, arm-board transform, controller
correlation, free TCP, device pose, motion repeatability, and timing/settling.
The last two belong to stage 14; earlier terms are not made measured by the
stage-13 nominal fit. The separate contact addendum remains out of scope.

For fully admissible terms, the implemented conservative calculation is:

`error = SUM(term bounds)`

`eroded radius = target safe radius − tool-tip radius − guard`

`remaining margin = eroded radius − error`

Units are integer micrometres. Strictly positive eroded radius and nonnegative
remaining margin are required for `DIAGNOSTIC_FITS_ZERO_AUTHORITY`. Missing,
stale, future, out-of-domain or mismatched terms produce
`BLOCKED_UNBOUNDED`, with no finite aggregate or remaining margin. Negative
geometric clearance is retained, not clamped to zero.

A useful first wrapper runs actual typed missing/stale/domain/target-margin
fixtures, including a separately labelled synthetic finite-sum control.
The real-build readiness projection must remain UNBOUNDED while term
measurements are absent. Do not feed illustrative sensitivity bounds into
`MEASURED_IN_DOMAIN`, or use rectangle half-width as a measured safe radius
without explicit source-bound target-geometry evidence.

## 7. Known gaps and previously recorded results

These are regression targets and warnings, not current session observations:

| Recorded source | Result and implication |
| --- | --- |
| [Placemat sensitivity](PLACEMAT_GEOMETRY_SENSITIVITY.md) | Default assumed bounds previously produced gaps on 27/29 phone targets, 0/46 keyboard targets; worst margins −0.7560 mm and +2.7525 mm respectively. Current unit assertions require at least 26 phone gaps, negative phone margin and no keyboard XY gaps. The zero-error control is a different experiment. |
| [Mission coverage](PREHARDWARE_MISSION_COVERAGE.md) | Baseline `reach-00ed8c5820df03c7` at the optimized park previously accepted 38/75 independent routes: 20/46 keyboard and 18/29 phone. Phone `key_a` first failed at APPROACH, margin 0.0006578241188109833 below 0.01. |
| Same mission study, different hypothesis | Rank-1 `reach-944d7463f4c67905` previously accepted 75/75 sampled routes, but with changed base placement/yaw and a 120 mm keyboard tool. Status explicitly includes `WITH_UNSUPPORTED_CHECKS`; it is not nominal geometry or installed clearance. |
| [Collision foundation tests](../tests/unit/test_collision_foundation.py) | The pinned URDF has zero collision elements and the actual current audit is `COLLISION_DIAGNOSTIC_BLOCKED_REQUIRED_GEOMETRY_INCOMPLETE`. |
| Stage 13 | Eight physical reference components are still PENDING: bootstrap receipt, reference-characterization receipt, arm-to-board transform, controller correlation, free-state TCP, keyboard map, phone map and observer candidates. |

Do not suppress rejected phone targets, choose a new passing overlay after
seeing the results, loosen joint/clearance policy automatically, or present
an expected-gap regression check as nominal feasibility success. Any new
overlay must be a distinct, operator-reviewed hypothetical input, never an
update to the frozen build or accepted calibration.

## 8. Recommended implementation order

### NC-01 — exact binding and a small retained readiness evaluator

Proposed new modules: `application/rehearsal_noncontact_binding.py` and
`application/rehearsal_noncontact_stage.py`, with dedicated pure tests. These
names/APIs are proposals, not present implementation.

Create a frozen binding from the verified original M1 store under existing
CELL/SESSION leases, never browser-authored hashes. Retain:

- workspace, evaluator/dependency source and catalog hashes; cell/session/
  operator identity; exact stage ID and rehearsal composition;
- the reviewed stage-13 receipt/assessment/review payload hashes and complete
  evaluation hash, with full predecessor verification;
- exact reviewed camera capture, stage-7 optics and stage-8 registration
  dependencies, selected camera/settings/dataset identity and support source;
- reviewed controller identity, the full audited stage-12 campaign/request/
  evidence binding and independent final synthetic-power observation;
- verified build snapshot, bundle, URDF, target catalog, alignment, geometry
  source documents, selected tool/placement/park domain and all policies;
- exact finite case IDs and input hashes, with training/characterization and
  untouched final-acceptance partitions kept separate.

First collect the actual collision-readiness report, static-architecture
inventory gaps and typed accuracy-budget cases. Optionally add the bounded
all-75 HOVER/TRANSIT pose screen only after result retention and runtime size
are measured. Show nominal feasibility BLOCKED when required geometry,
accuracy or selected pose results fail. An expected missing-term test can
pass as a software regression while that nominal readiness remains BLOCKED.

### NC-02 — actual uncertainty and coverage evidence

Add the unchanged nominal control and default uncertainty campaign, retaining
all bounds/cases/outcomes. Then integrate independent target sweep and route
coverage as separately selectable, fixed source-bound diagnostics. Keep
nominal and rank-1 hypothesis results side by side, not combined. Rejected
target IDs, first failed phase, residuals, joint margins and evaluated versus
not-reached counts are required output.

Do not put a 75-route solver campaign in `view()`, prepare, assessment, review,
reopen or export. Run it once behind an explicit one-use action in a bounded
hardware-incapable worker. Pin source/input identities before work and recheck
before publication. Determine budgets from measured fixture runs; existing
global caps are not a promise of interactive latency. Stop requests cancel
diagnostics, not the robot. Incomplete/cancelled/source-drifted runs may retain
diagnostic partials with counts, but never a complete accepted campaign.

### NC-03 — static collision and virtual lifecycle joins

Build the reviewed static-source/26-body contract boundary without inventing
missing dimensions. Exercise complete synthetic positive geometry and exact
faults separately: missing body, missing clearance, wrong target hash,
wrong frame, omitted midpoint, sampled cable omission, collision and
contact-exclusion misuse. Join complete trajectory reports to complete
endpoint/harness inputs before calling the dense collision evaluator.

Adapt the representative virtual acceptance and stall case only after the
camera context and geometry-domain differences are explicit. The UI should
say “virtual contact/outcome lifecycle” for these checks, not “physical
noncontact test.” Actual installed collision, visibility, timing/repeatability
and untouched final-partition intake remain a later, separately released
physical commissioning task.

## 9. Evidence retention and no-replay requirements

Proposed API shape:

```python
evaluate_rehearsal_noncontact_stage(workspace, binding, fixed_selection)
    -> RehearsalNoncontactEvidence

verify_rehearsal_noncontact_evidence(
    payload,
    *,
    expected_binding,
    expected_evidence_sha256,
    expected_evaluator_source_sha256,
    retained_artifacts,
) -> RehearsalNoncontactEvidence
```

The verifier must exact-check schemas, bounds, immutable artifact membership,
source/session/settings/predecessor joins and derived predicates. It must not
rerun an IK search, virtual plant, renderer, camera/provider or acceptance
campaign. Complete source-bound numerical evidence is required to recheck
claimed route acceptance. Existing compact route hashes alone do not supply
that evidence.

Keep the existing 128 KiB M1 outer-JSON limit and ordinary operation/export
sanitizer limits unchanged. Stage 13 already needed roughly 102 KiB for its
complete report; 4,425 sensitivity observations and 75 complete trajectories
must not be assumed to fit the same envelope. Before UI integration, measure
actual compact/pretty bytes, nesting, strings, counts and worst-case failures.

If full technical evidence exceeds the envelope, implement a separately
reviewed bounded immutable artifact store/reader: exact assigned root,
source-bound manifest, fixed artifact IDs, per-file and aggregate byte/count
caps, no overwrite, invalidity marker until complete publication, hashes and
strict inventory. Retain complete technical bytes there and reference them
from the small M1 receipt. Verify content on review/reopen, not just existence
or manifest hashes. Export must explicitly include those retained bytes or
state that they were omitted; an ordinary lightweight log export is not a
complete numerical-evidence bundle. No silent truncation, hash-only proof,
archive expansion or arbitrary browser paths.

Reuse existing exact admission/revision/source checks, durable evidence before
reviewed commit, one-use request deduplication and cancellation boundaries.
An interrupted result is not resumed or recomputed by reopen. If evidence was
written but not linked/reviewed, retain a held orphan/pending state rather than
replaying approval. Notes cannot clear a numerical gap or physical hold.

## 10. UI and test acceptance checklist

The card should present independent sections, with raw evidence available only
through bounded retained details/export:

- source domain: NOMINAL versus UNMEASURED_SENSITIVITY_OVERLAY;
- coverage: selected/total targets, per-device successes/gaps/not-evaluated,
  phases, tool cases and independent-route versus sequence scope;
- nominal readiness and separate expected-fault/invariant checks;
- signed phone/keyboard margins and first failed route phases; unavailable
  values shown as NOT_AVAILABLE, not zero;
- collision inventory complete/missing/unknown, discrete sampling coverage,
  and static-camera architecture provenance;
- bounded versus UNBOUNDED accuracy terms and missing physical components;
- explicit virtual counters, zero actual hardware counters, and the warning
  “No power, movement or contact is authorized.”

Before enabling the new rehearsal action:

1. Verify constructor/view/prepare/reopen/export are inert with the actual
   solver, renderer, virtual session and every device/native provider forbidden.
2. Reject altered source, session, stage-13 review, camera settings/dataset,
   controller, final observer, overlay, policy, target IDs or incomplete
   artifact membership. No unknown fields or booleans masquerading as counts.
3. Test actual canonical pose/route math on bounded fixtures; test catalog
   completeness/duplicate detection independently. Never use fixture-created
   literal true fields as evidence of a real numerical pass.
4. Preserve known phone failures and independent nominal controls. An expected
   fault check must not mint nominal acceptance or hide a separate failed case.
5. Test collision/accuracy refusal paths described above; missing terms stay
   UNBOUNDED and missing body/midpoint/cable coverage stays BLOCKED.
6. Test cancel/deadline/source drift before, during and after result retention;
   duplicate execution does not redispatch and review/reopen never solve again.
7. Measure full successful and failed reports through the real service,
   Arrival validation, UI projection, export and original-store reopen. Prove
   no evidence is discarded and no aggregate budget is bypassed.
8. Run the all-75 heavy lane only after bounded contracts pass; retain complete
   results for the exact selection. Do not run concurrent heavy campaigns
   against a time-sensitive commissioning workflow.

Existing regression anchors to reuse, not results claimed by this audit:
`test_trajectory_simulation.py`, `test_mission_route_coverage.py`,
`test_reach_optimizer.py`, `test_placemat_uncertainty.py`,
`test_collision_foundation.py`, `test_static_mission_route.py`,
`test_b0477_virtual_acceptance.py`, plus the actual accuracy-budget and
first-power onboarding suites. Add new binding/evidence/service/reopen/UI
tests without rewriting the historical golden baseline.

## 11. Completion definition for this next slice

The first deliverable is a usable, retained **gap report** tied to the exact
reviewed stage-13 session. It can accurately explain why an assumed board/
tool/target/route is or is not supported by the available model. It can show
that software rejection, cancellation, retention and review behave correctly.
It must not promise that the incoming arm is reachable, clear, calibrated or
safe because a related synthetic mission passed.

Actual stage-14 qualification remains pending until separately authorized
physical evidence supplies installed geometry/visibility, calibrated reference
and controller/TCP maps, measured accuracy terms, bounded noncontact motion
and stop behavior, final independent disconnection observation and untouched
acceptance-partition results. Stage 15 cannot convert this rehearsal into a
physical handoff or a keyboard/phone execution permit.
