# Stage 13: reference-frame next-slice audit

Status: recommendation only, 2026-09-07. No stage-13 implementation, calibration
promotion, hardware access or motion was performed during this audit. The
canonical boundary is [WIZARD_REMAINING_STAGE_INTEGRATION.md](WIZARD_REMAINING_STAGE_INTEGRATION.md#stage-13--reference_frame_calibration).

Implementation follow-up: the bounded numerical/reference rehearsal recommended
below now has [integration code and documentation](WIZARD_REFERENCE_INTEGRATION.md)
and a [rigid correspondence fitter](RIGID_CORRESPONDENCE_FITTER.md). This audit is
retained as rationale, not rewritten as physical qualification. See the
[implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md) for executed tests.

## Recommended bounded implementation

Build an **incapable, noncontact reference-chain rehearsal**, not a receipt that
claims installed calibration. Reuse the real graph/registry and rigid-transform
math; retain actual calculated results and negative checks. Leave the eight
canonical physical components visibly pending: bootstrap phase receipt,
reference-characterization phase receipt, arm-to-board transform, controller
correlation, free-state tool TCP, keyboard map, phone map and observer candidates.

A rehearsal PASS may mean that the source-bound graph, geometry and refusal
rules worked. It must not mean those physical components are complete. Do not
add a wizard move, home, probe, power or contact command to satisfy this stage.

## What exists, and what it actually calculates

| Existing code | Real behavior | Limitation for stage 13 |
| --- | --- | --- |
| `application/static_phase1_calibration.py`: `static_phase1_context_hashes`, `build_static_phase1_synthetic_closure`, `run_static_phase1_calibration_rehearsal` | Builds 15 immutable `NOMINAL_ONLY` artifacts, resolves both 12-entry device closures, reads the physical registry without installing anything, and independently rotates all 27 parent plus 41 context edges. | Artifact payloads contain graph/provenance markers, not fitted arm-board or TCP transforms. A coherent graph is not a calibration solve. |
| `calibration/registry.py`: `CalibrationRegistry.assess/resolve`; `calibration/artifacts.py`: `CalibrationArtifact` | Checks publication integrity, exact current parent hashes, context, manifest/build, missing states and recursive validity of artifacts claiming `VALID`. | Generic artifact assessment is not a per-component numeric acceptance verifier. New code must not mint `VALID` fixtures. |
| `application/b0477_static_vision.py`: `run_b0477_static_vision_capture_rehearsal`; `vision/planar_pose_estimator.py`: `PlanarBoardPoseEstimator.estimate` | Renders synthetic pixels, detects AprilTags, estimates `camera_T_board` from T0–T3, and scores withheld K0/P0 reprojection. Stage 8 already uses this path. | Nominal optical geometry and synthetic distortion; neither an installed extrinsic nor an arm-base transform. Reuse the exact reviewed stage-8 evidence instead of calling a fresh default image the session's registration. |
| `geometry/transforms.py`: `RigidTransform.compose/inverse/transform_point`, `Rotation3`; `geometry/urdf.py`: `UrdfModel.forward_kinematics`, `JointPosition` | Computes full rigid transforms/FK with frame checks, millimetres, typed radians and right-handed rotation validation. | The input board-to-URDF-world transform, joint reference and tool offset remain supplied assumptions. These operations do not identify them from measurements. |
| `application/target_sweep.py`: `run_target_sweep`; `kinematics/ik.py`: `RoArmM3NumericalIk.solve` | Loads the hash-pinned URDF, solves individual board-frame tool-tip targets and park, and records residuals/joint-limit intersection results. | Independent point screening only: not reference fitting, controller correlation, branch-continuous routing, collision qualification or measured park. Use only explicit `HOVER`/`TRANSIT` phases in a noncontact stage-13 rehearsal. |
| `application/placemat_uncertainty.py`: `run_placemat_uncertainty_simulation` | Recomputes target-frame errors/margins for 46 keyboard plus 29 phone targets; default 59 signed/corner cases perturb board/device pose, local maps and TCP. | Bounds are assumed sensitivities, not measured tolerances/covariance or physical acceptance limits. Default tests expose phone-target gaps; do not suppress them to get an all-green page. |
| `application/virtual_calibrations.py`: `resolve_virtual_calibrations` | Explicitly labels URDF joint truth, unmeasured arm-board overlay, controller bypass, virtual tool length and nominal target maps. | Dependency/orchestration surrogates only; historical eye-on-arm requirement IDs must not be reinterpreted as static-overhead physical artifacts. |

`calibration/static_camera_intrinsics.py` is a strict synthetic result parser and
assessor; it does not itself fit intrinsics from images. The numerical
`calibration/eye_on_arm_solver.py: solve_eye_on_arm` really solves an AX=XB-style
problem, but it is for the historical **moving camera** model. Do not reuse its
name or equations as if it implemented the selected static-camera arm-board
calibration.

## Exact admission and retained-evidence binding

Derive all dependencies server-side under the original M1 audit/lease, following
`commissioning_rehearsal_reopen.py: _feedback_binding/_verify_feedback_receipt`.
The browser supplies no transforms, source hashes, controller choice or phase
status that can act as trusted evidence.

Required binding inputs for the new evaluator/report:

- Current workspace source and evaluator-source hashes, catalog hash, cell,
  session, operator, exact stage ID and static Phase-1 graph hash.
- Full canonical stage-12 receipt, assessment and review payload hashes. The
  review must approve that exact assessment; require its actual evaluation PASS.
- Exact stage-12 `CAMPAIGN_RESULT`, consumed reservation/permit and
  `CAMPAIGN_EVIDENCE` relationship: one retained exchange, known sealed attempt,
  no unresolved attempt/quarantine, matching worker/operation/source/controller,
  and byte-for-byte verification through
  `verify_retained_arm_feedback_campaign`.
- Separately identified stage binding hash, campaign-context binding hash,
  retained full campaign hash, inner feedback evidence hash and request hash.
  These have different meanings and must not be compared interchangeably.
- Exact reviewed controller/identity evidence plus the independently retained
  **synthetic** final-power observation hash. Preserve the serial worker's
  `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION` statement. A valid packet, close, or
  synthetic observer does not prove physical power, firmware, reference or pose.
- Current reviewed stage-7/8 optical reports, stage-6 camera dataset and exact
  source/settings/identity/manifest bindings. Reverify their existing full
  chain. Label whether retained camera evidence is an actual math input or only
  a dependency; the session capture is not automatically the optics fixture.
- Revalidated `SimulationContext` source set, pinned URDF hash, board/layout/tag
  map, target catalog, semantic profiles, support design and B0477 profile.
  Preserve the historical freeze and additive static-camera hashes separately.

Do not feed stage-12 T105 fields straight into FK as a calibrated joint state.
That exchange establishes a bounded transport fixture; controller sign/zero/
units/model mapping requires its own explicit candidate and verification.

## Substantive first slice

1. Verify the predecessor chain above, then call
   `load_simulation_context/revalidate_simulation_context` and the existing
   static Phase-1 graph rehearsal. Retain its complete baseline and exact
   per-edge results, not only counts or a hash of an unretained report.
2. Add a compact, explicitly nominal frame-chain exercise using the public
   `RigidTransform` and `UrdfModel.forward_kinematics` APIs. Retain exact inputs,
   frame names, units, tool case, composed matrices, target points and inverse
   round-trip residuals. The modeled chain is
   `board_T_URDFworld × URDFworld_T_hand(q) × hand_T_tip`; the camera-to-board
   chain is separate. Never alias `R_ctrl`, URDF world, startup middle or park.
3. Optionally run a predeclared bounded `run_target_sweep` noncontact subset with
   complete result rows and explicit coverage. A subset is not all-target
   acceptance. Keep feasibility gaps as nominal outcomes, not expected-fault
   successes. A later all-75-target campaign can broaden coverage explicitly.
4. Keep the default sensitivity campaign as a distinct diagnostic, not a
   requirement that assumed phone margins be positive. If integrated, retain
   the actual 75-target/59-case results with a reviewed evidence quota.
5. Use the existing compact UI check contract (`NOMINAL`, `EXPECTED_FAULT`,
   `INVARIANT`) with separately derived nominal/fault outcomes. Show independent
   keyboard/phone coverage, remaining physical components and no-authority
   provenance. Expected rejection must not override a failed nominal chain.
6. Add a bounded, versioned immutable evidence contract and pure reopen verifier.
   Verification checks full retained inputs/results, exact hashes and semantic
   consistency; it does not rerun the evaluator, solver, inventory or worker.

Measure complete report sizes before selecting the artifact budget. The current
stage evidence envelope is bounded; full uncertainty/sweep matrices may not fit
its 128-KiB limit. Use an explicitly reviewed retained-artifact extension or a
smaller predeclared campaign, never silent truncation or a summary-only digest.

## Missing work that must stay explicit

No standalone static arm-to-board correspondence fitter, controller reference/
correlation fitter, free-state TCP pivot/offset fitter, or strict assigned-source
bootstrap/reference-phase receipt importer was found in the inspected code.
The legacy `_probe_reference_frame_calibration` invokes the real graph but also
contains literal-true procedural checks; those checks are not evidence that a
phase ran or that frames were measured.

The eventual fitting work needs versioned correspondence datasets, explicit
frame/unit conventions, rank/excitation checks, independent heldouts, residual
and uncertainty reporting, tool/base/install identities and source/epoch ties.
Develop and test these offline with truth-known fixtures before allowing any
physical import. Bootstrap must precede reference characterization; neither is
an in-wizard motion operation. Physical work remains a separately released,
observed noncontact procedure ending independently disconnected.

The broader 15-entry graph includes contact TCP/activation/outcome qualification.
Keep these graph nodes visible as future requirements, but do not demand their
physical closure for a stage-13 noncontact rehearsal. Free-state TCP and observer
candidates are not contact calibration or qualified outcome observers.

## Acceptance and regression anchors

Existing anchors read during this audit:

- `tests/unit/test_static_phase1_calibration.py`: 15-node graph, two 12-entry
  closures, 68 exact staleness probes, deterministic reports, no physical
  registry mutation or synthetic promotion.
- `tests/unit/test_geometry_transforms.py` and `test_geometry_urdf.py`: transform
  direction/inversion, wrong frames, invalid/reflected rotations, finite values
  and typed joint units.
- `tests/unit/test_application_simulation.py`: actual target IK, model hash,
  unknown targets, explicit subset coverage and immutable reports.
- `tests/unit/test_placemat_uncertainty.py`: all 75 nominal targets, signed-error
  oracle, yaw pivots, default phone gaps, altered source/context refusal.
- `tests/unit/test_first_power_on_onboarding.py`: historical graph-probe behavior;
  use as regression context, not as proof of a physical phase receipt.
- Current stage-12 campaign/evidence/stage tests: failed cleanup/retention,
  uncertain attempts and absent final observations must prevent admission.

Add stage-13-specific faults for mixed session/source/catalog, changed controller,
stale support/settings/TCP/target map, missing or reordered phase predecessor,
reflected/reversed frames, wrong-unit inputs, numeric tampering with recomputed
inner hashes, missing/duplicate/degenerate correspondences, heldout leakage,
synthetic-as-measured claims and contact-dependent nodes falsely made mandatory.
Only exercise correspondence/fit acceptance once that actual solver exists.

No tests were executed for this audit; the statements above distinguish inspected
implementation/test assertions from a new execution result. Production source
was not changed, and the ongoing stage-12 source-frozen validation is unaffected.
