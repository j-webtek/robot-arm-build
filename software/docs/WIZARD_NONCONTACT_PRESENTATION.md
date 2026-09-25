# Noncontact readiness gap presentation

The existing browser and terminal Guided Rehearsal views render the nullable
`commissioning_rehearsal.noncontact_evaluation` projection. This is NC-01's
retained readiness **gap report**, not a physical noncontact test, move button,
keyboard/phone readiness claim, or stage-15 handoff.

Use the existing explicit collect, assess and exact-review workflow when the
backend makes stage 14 due. A successful diagnostic operation or expected-fault
check is not a successful stage assessment. Missing installed geometry and
unmeasured accuracy keep nominal readiness `BLOCKED`; reviewing those results
does not clear the gaps. Export the original retained evidence for development
review. The card adds no controls, polling action, local storage or file access.

## Independent sections

- Historical collision audit: the original 19-body **eye-on-arm** requirements,
  proxy count, actual reported URDF collision-element count, missing and unknown
  bodies. The six nominal proxies are not updated static-camera clearance.
- Static-camera requirements: the separate 26-body/nine-source inventory,
  explicitly `NOT_EVALUATED`; naming a body does not supply its installed shape.
- Real-build accuracy: ten unmeasured terms and `BLOCKED_UNBOUNDED`, with absent
  aggregate and margin shown as `NOT_AVAILABLE`, never zero. The retained
  `real_unmeasured` calculation uses a synthetic target boundary only to expose
  missing measurements, not to qualify a real key or phone target.
- Separate synthetic controls: missing/stale/domain cases, signed target-margin
  failure and a finite control. Integer micrometre values belong to those fixed
  inputs; a finite control does not bound the real build. Regressed controls can
  remain visible as blocked without changing nominal readiness.
- Actual selected nominal tool/domain: zero evaluated targets out of 46 keyboard
  and 29 phone targets. No passing `UNMEASURED_SENSITIVITY_OVERLAY` is substituted.
- Original reviewed stage-13 identities: exact reference binding/evidence and
  predecessor receipt/assessment/review hashes. Camera evidence is dependency
  only, and serial feedback is not calibrated joint input.
- Pose, route, sensitivity, visibility, dynamics and physical motion are all
  `NOT_EVALUATED`. No virtual route or plant runs in this slice. Physical opens,
  acquired frames, serial writes, motions and contacts remain zero.

The fixed warning is: **No power, movement or contact is authorized.** Physical
reference/acceptance components and NC-02/NC-03 remain separate open work.

## Projection boundary

The outer projection has exactly `stage`, `evaluation_sha256`,
`selected_inputs_sha256`, `outcome`, `checks`, `provenance`, `physical_authority`,
`meaning` and `safe_summary`. The stage is `noncontact_acceptance`, outcome is
`BLOCKED`, and authority is false. Checks remain separately classified as
`NOMINAL`, `EXPECTED_FAULT` and `INVARIANT`; at least one nominal gap must remain.

The nested schema is `rocell.rehearsal_noncontact_summary.v1`. Both renderers
validate its exact bounded fields, unique portable identifiers, ordered six
accuracy cases, strict integer counts/metrics, null unbounded values, hashes,
nominal domain, fixed not-evaluated axes and false authority. Unknown fields,
coercible strings/booleans, omitted inventories, unsafe numbers or contradictory
claims withhold the whole report as `NOT_VERIFIED`; no partial passing checks or
raw technical report are expanded. These are display checks, not a replacement
for the backend's retained-evidence and source-binding verification.

Literal tool/body IDs, dependency hashes and narrative text retain underscores
and signs. Browser output uses text nodes, never HTML interpretation. Terminal
structured output uses lossless JSON escaping, not terminal control sequences.

## Verification

`tests/unit/test_arrival_wizard_noncontact_ui.py` includes pure modeled display
fixtures for hold separation, invalid and oversized values, no implicit actions,
literal narrative/identifier preservation and regressed finite controls. It also
runs the actual source-reading collision/accuracy evaluator, passes its retained
document through the service's compact projection and both strict renderers,
then checks that full evidence bytes remain unchanged. Source/evaluator functions
are forbidden during the projection/render portion. The predecessor hashes in
this test are explicitly modeled; it is not a durable M1 or physical review proof.

The actual producer join shows eight checks (three nominal blocked, five
controls passed), 19 historical bodies/six proxies/zero URDF collision elements,
26 missing static geometry bodies and nine required source identities. Four
design hashes are retained, so only five source keys are missing; none of those
design hashes qualifies installed geometry. All ten accuracy terms are
unmeasured. The synthetic margin-failure result remains −1500 micrometres and
the finite-control margin remains 3000 micrometres, in separate control rows.

Focused verification: 59 new tests passed; 137 existing reference, arm/power and
terminal tests passed. Node syntax, Black and terminal mypy checks passed.
Source-bound public-session/export checks remain the integration owner's
separate evidence, not inferred from these display tests.

Related contracts: [implementation brief](WIZARD_NONCONTACT_IMPLEMENTATION.md),
[audited NC-01/02/03 plan](WIZARD_NONCONTACT_NEXT_SLICE.md).
