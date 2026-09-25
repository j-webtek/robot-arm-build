# Reference-frame rehearsal integration

Implementation checkpoint: 2026-09-07/08. Stage 13 is implemented and its full
public workflow has passed explicit browser review, verified export and a fresh
completed-store reopen with device/evaluator/fit/FK replay forbidden. Consult
[implementation progress](WIZARD_IMPLEMENTATION_PROGRESS.md) for the exact
test/source and original-store restart checkpoint. This document describes a numerical
rehearsal, **not physical calibration or permission to move the arm**.

## Purpose and boundaries

Canonical stage: `reference_frame_calibration`. It uses the existing explicit
collect → assess → distinct-reviewer workflow in the original M1 rehearsal
session. It adds no browser-supplied transform, port, power switch, home/probe
command, or physical bootstrap acquisition.

The selected static-overhead camera architecture is preserved. Historical
eye-on-arm AX=XB calibration is not repurposed as arm-to-board calibration.
Source-derived nominal geometry and the pinned URDF remain assumptions until
separately characterized on the actual build. Controller feedback values do not
become calibrated joint angles; model world, controller coordinates, startup
middle pose and safe park are not interchangeable reference frames.

The numerical component fits a proper rigid transform from explicit 3-D point
correspondences. Only training points enter the fit. Held-out points independently
measure residuals. It does not fit scale, shear or a reflected coordinate system.
It does not infer TCP, controller zeros/signs, physical stationarity, measurement
uncertainty or real observation provenance. Its result is a candidate even when
its numerical checks pass. See [the fitter contract](RIGID_CORRESPONDENCE_FITTER.md).

## Code ownership and data flow

| Component | Responsibility |
| --- | --- |
| `calibration/rigid_correspondence.py` | Immutable bounded frame-labelled input, lazy NumPy training-only fit, residuals, observability and pure retained-result verification |
| `application/rehearsal_reference_binding.py` | Exact reviewed dependencies and immutable canonical nominal-source snapshot; no device selectors or authority |
| `application/rehearsal_reference_stage.py` | Actual source-derived graph/FK/fit rehearsal, complete evidence and independent retained-evidence checks |
| `application/commissioning_rehearsal_service.py` | Due-stage leases, collection, cancellation boundaries, full receipt retention, assessment, review and cached summary |
| `application/commissioning_rehearsal_reopen.py` | Original-store schema/lifecycle association, audited predecessor binding and pure verification; never replay a fit or device operation |
| `application/arrival_wizard_service.py` | Human-readable action preview, original source-bound execution and diagnostic export |
| `ui/static/app.js`, `ui/terminal.py` | Compact diagnostic presentation and explicit physical-pending labels, no numerical or device authority |

### Exact prerequisites

Under the original session's verified storage transaction, collection derives:

1. Workspace source, catalog, cell, session and current operator identity.
2. Full canonical receipt/assessment/review hashes from reviewed stages 7, 8 and
   12, together with each complete evaluated-report hash. Embedded assessment
   self-hashes are not substituted for full assessment-payload hashes.
3. The exact stage-6 camera receipt and independently checked retained binary
   dataset. Stages 6–8 are dependencies, **not numerical correspondence inputs**.
4. Stage 12's actual retained campaign result, consumed reservation/permit and
   complete private evidence record. All three must match the original audit.
5. Distinct feedback hashes: reviewed-input binding, campaign-context binding,
   full campaign bytes, inner feedback evidence, fixed request and controller.
6. The independently modeled post-campaign final-power observation. Closing the
   serial transport does not establish de-energization. No physical power was
   observed in this workflow.
7. A freshly read, source-pinned static-graph context and nominal geometry snapshot.
   The snapshot is immutable bytes with a detached decoded view and a 16 KiB cap.

No hashes are accepted from the browser as substitutes for these checks. Source
drift requires a fresh run; an old store is not rebased or converted.

## What collection actually exercises

- The existing static Phase-1 rehearsal builds fifteen `NOMINAL_ONLY` artifacts
  and checks all 27 parent and 41 context dependency edges. Its physical registry
  read is not installation, promotion or complete physical graph closure.
- Six closed, source-related nominal joint configurations feed actual typed URDF
  forward kinematics. The retained frame chains and complete pinned XML allow
  algebraic checking on reopen without repeating the FK evaluator.
- Four training and two held-out correspondences exercise the rigid fitter.
  A separate held-out-only perturbation must be detected without refitting the
  nominal training data or allowing that fault check to replace nominal success.
- Two selected target coordinate round trips cover keyboard `A` and phone
  `key_q`, drawn from their actual nominal catalogs. This is **not** all-75-target
  coverage, IK reachability, collision checking, continuous motion, typing or
  phone-tapping accuracy.

The full graph, matrices, correspondence inputs, residuals and fit certificates
are retained. The UI intentionally shows only a compact projection. Do not
replace complete numerical evidence with a digest or a green status flag.

## Retention, restart and cancellation

Collection retains a stage-opening/operator receipt before numerical work. It
verifies dependencies, checks Stop, evaluates the bounded fixture, pure-verifies
the resulting bytes, checks Stop again and publishes the complete receipt. The
in-memory receipt is normalized to the exact JSON representation being stored.

The new evaluator permits at most 112 KiB after measuring the complete report;
the existing outer M1 evidence cap remains 128 KiB. Neither physical timing nor
authority limits are changed. Public result/export serialization must also pass
the existing nesting, item, string and size checks; JSON encoding alone is not
proof that the public path can retain the report.

Assessment and review reread the exact dependencies and receipt. A distinct
reviewer accepts the current assessment; they cannot override failed predicates.
The assessment outcome is derived from retained checks, never a caller PASS flag.

On restart:

- A complete receipt before assessment restores as receipt-ready.
- A complete assessment restores as review-pending and needs fresh review.
- Reviewed stage 13 restores with stage 14 due; it does not replay prior work.
- An opening without its complete result is an inspect/export hold. It is not
  retried, repaired, advanced or replaced with a new hidden session.
- Missing workspace context, missing campaign records, changed source/data,
  inconsistent operator/evidence ordering or an ambiguous suffix prevent use.

Stop can prevent later publication but does not undo an already retained result.
No cancellation path clears evidence or creates movement authority.

## Operator and developer checks

Launch the normal workbench from the workspace root:

```powershell
.\start-rocell-wizard.ps1
```

Use Guided rehearsal and the due-stage collection/assessment/review controls.
The [presentation guide](WIZARD_REFERENCE_PRESENTATION.md) explains the counts,
residuals, fault labels and eight physical component holds.

With the existing development environment, the public smoke includes original
store restarts, full-report export and optional browser review:

```powershell
.venv\Scripts\python.exe software\scripts\wizard_arm_setup_rehearsal_smoke.py --reference --serve
```

After reviewing stage 13, independently verify that exact completed store with
camera/arm workers, fitter, reference evaluator and FK replay forbidden:

```powershell
.venv\Scripts\python.exe software\scripts\wizard_arm_setup_rehearsal_smoke.py --reference --verify-completed 'rehearsal-EXACT_SESSION_ID'
```

Run only one heavy NTFS/camera workflow at a time. Preserve failed stores and
their exports for investigation; don't relax physical timing or rewrite source
bindings to make a failed run pass. Exports remain under the assigned
`software/runs/wizard-exports` folder and grant no physical authority.

## Work still needed

The eight physical components remain pending: bootstrap receipt,
reference-characterization receipt, arm-to-board transform, controller-model
correlation, free-state TCP, keyboard map, phone map and observer candidates.
The strict physical receipt importers and measured acceptance procedures are
separate development work. Stages 14/15, native provider admission/qualification,
received hardware baselines and later bounded motion/contact execution are not
completed by this reference rehearsal.

The [next noncontact integration plan](WIZARD_NONCONTACT_NEXT_SLICE.md) maps the
existing all-target, uncertainty, static-camera collision and virtual lifecycle
calculations. It is an audited implementation plan, not completed stage 14 or
evidence that the nominal build can reach every target.
