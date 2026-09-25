# Reference-frame rehearsal presentation

This is the browser/terminal presentation contract for canonical stage 13,
`reference_frame_calibration`. The original rehearsal journal, exact retained
evidence and separate assessment/review still determine progress. A displayed
diagnostic success does not install a calibration or release physical effects.

## What the operator sees

The **Retained synthetic reference-frame checks** card separates:

- Nominal check results, deliberately injected failure handling, and invariants.
  Expected-fault success cannot replace a failed nominal result.
- The nominal 15-artifact dependency graph and its 27 parent plus 41 context
  edges. Detected stale edges describe injected dependency faults, not physical
  calibration accuracy or physical closure of the whole graph.
- A synthetic point-fit report: four training points, two independent held-out
  points, training/held-out RMS in millimetres, and maximum coordinate-roundtrip
  error. An unavailable residual is `NOT_AVAILABLE`, never an invented zero.
- Explicit target coverage: the selected keyboard target and phone target,
  alongside their 46-target and 29-target catalogs. Two coordinate roundtrips
  are not all-75-target acceptance, IK reachability, continuous routing,
  collision qualification, or physical typing/tapping accuracy.

All eight physical components remain `PENDING`, including when the software
rehearsal checks pass:

1. Bootstrap phase receipt.
2. Reference-characterization phase receipt.
3. Arm-to-board transform.
4. Controller-model correlation.
5. Free-state tool TCP.
6. Keyboard target map.
7. Phone target map.
8. Outcome-observer candidates.

Those holds are not inferred from caller-supplied status strings. A malformed
summary cannot turn a component green. Contact-dependent graph nodes remain
future requirements; the broader dependency graph is not a claim that contact
calibration belongs in this noncontact rehearsal.

## Input provenance and next action

Stages 6, 7 and 8 are `DEPENDENCY_ONLY_NOT_NUMERIC_INPUT` for this reference
exercise. They bind the retained camera chain, but their capture/optics data are
not silently substituted for measured point correspondences. Stage-12 controller
feedback is `TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT`; a T105 packet does not
establish calibrated joint units, signs, zeros, pose, stationarity or reference.

Use the existing explicit collect, assess, and exact review actions for the due
stage. There is no new physical bootstrap importer, transform editor, controller
endpoint input, power button, move/home/probe action, or contact command. Viewing
the report runs none of these actions and does not rerun an evaluator.

The next canonical stage is stage 14, `noncontact_acceptance`, which remains
pending after this slice. A successful stage-13 rehearsal is neither physical
readiness nor completion of all fifteen commissioning stages.

## Cached projection boundary

The service supplies `commissioning_rehearsal.reference_evaluation`, nullable
until retained results exist. Its common fields match the earlier retained-check
cards: `stage`, `outcome`, `evaluation_sha256`, `selected_inputs_sha256`,
`checks`, `provenance`, `physical_authority: false`, and `meaning`.

The summary is an explicit, closed `reference_summary` object with schema
`rocell.rehearsal_reference_summary.v1`:

- `graph`: nominal artifact, parent-edge, context-edge and detected-edge counts.
- `numeric`: training/held-out counts and finite nonnegative or null residuals.
- `target_coverage`: separate bounded keyboard/phone selections and totals.
- `claim`: `TWO_TARGET_COORDINATE_ROUNDTRIPS_NOT_REACHABILITY_OR_COMPLETE_COVERAGE`.
- `physical_components_pending`: the eight exact canonical component IDs.
- `camera_role` and `controller_feedback_role`: the provenance statements above.

Neither frontend expands `technical_reports` or other incidental full-report
fields through generic commissioning facts. Complete technical evidence is a
separate backend retention concern. The card shows a visible `NOT_VERIFIED`
message for missing/inconsistent summary data, unknown fields, wrong types,
changed coverage declarations, or exceeded display bounds. No evidence
verification, storage qualification or physical authority is supplied by the
renderer itself.

## Focused checks

`test_arrival_wizard_reference_ui.py` uses a JavaScript DOM harness and the actual
terminal frontend with a read-only fake service. It covers nominal success,
regressed nominal checks beside passing negative checks, nullable residuals,
malformed counts/coverage/provenance/component lists, missing projections and
suppressed full technical data. It verifies that rendering sends only a view
request and adds no action controls. These presentation tests do not replace
the evaluator, original-store reopen or physical acceptance tests.
