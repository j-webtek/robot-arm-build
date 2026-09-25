# Guided arm setup: stages 9–11

Implementation date: 2026-09-07. This document describes the shared service
integration; exact executed checks are recorded in
[the implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md). It extends the
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md), not the physical release
policy. The received RoArm-M3 Pro and overhead camera remain unqualified.

## What actually runs

| Due stage | Explicit collection | Retained result | Not established |
| --- | --- | --- | --- |
| `arm_identity` | Load the configured arm profile; invoke existing inventory normalization/composition with ten closed injected metadata fixtures | Profile, raw/normalized/composed reports, selection mismatch reasons and 12 checks | No host enumeration, COM open, received Pro/firmware/driver identification or reset-behavior measurement |
| `power_safety` | Run the existing typed power-safety assessor on synthetic review inputs | Complete typed inputs and actual assessor reports, 11 checks | No supply, restraint, E-stop or installation inspection; no power action |
| `power_on_observation` | Run the first-power assessor on synthetic procedure observations | Complete typed inputs and actual assessor reports, 15 checks | No energization, startup trajectory prediction, motion observation or final power-state evidence |

Check counts describe the present closed evaluator versions, not a user-editable
scenario list. A nominal check failing yields a blocked assessment even when
all expected-fault checks pass. Expected uncertainty/hold handling is a successful
test of that procedure, not nominal acceptance or a claim the arm is powered off.

The power evaluator's internal typed receipts are domain-separated synthetic
assessment fixtures. They are not physical M1 receipts, permits or energy events.
None of these three no-device evaluations creates a coordinator device attempt;
the prior two synthetic camera campaigns retain their own audited attempts.

## Data and control connections

The browser and terminal submit the existing closed actions through
`ArrivalWizardService`: preview → confirm → collect → assess → review.
`CommissioningRehearsalService` owns the due stage, operator binding, M1 leases,
retained evidence, assessment and distinct-reviewer commit. The UI does not
supply evidence hashes, raw ports, protocol bytes, arbitrary paths or power flags.

| Evaluation | Immediate predecessor whose full receipt/assessment/review payloads are hashed | Additional exact dependency |
| --- | --- | --- |
| Stage 9 | Reviewed stage 8 (`static_registration`) | Inner stage-8 evaluator digest |
| Stage 10 | Reviewed stage 9 (`arm_identity`) | Inner stage-9 evaluator digest |
| Stage 11 | Reviewed stage 10 (`power_safety`) | Inner stage-9 evaluator digest |

Each binding also carries the workspace source, catalog, cell, session, operator
and stage. `predecessor_assessment_sha256` hashes the **entire canonical M1
assessment payload**, including its embedded self-hash; it is not just the
embedded `assessment_sha256` value. The reviewed predecessor is selected from
one exact committed PASS trio, never from a browser's proposed hash.

The stage-8 chain is reverified through the strict optics verifier, reviewed
camera selection/settings and retained stage-six binary dataset. The latter is
an integrity dependency, not the pixels used by the nominal registration probe,
not an arm identity observation, and not power-on evidence.

## Publication and verification

1. An explicit collection opens the due stage under the original M1 transaction,
   then retains a stage-opening/operator document.
2. Dependency verification runs before the evaluator. Cancellation is checked
   before evaluation and again before result publication.
3. The complete evaluator result and its digest are retained in the stage-specific
   outer receipt. Each evaluator is bounded to 96 KiB; outer M1 receipts remain
   bounded to 128 KiB, with a 1 MiB aggregate reconstruction budget.
4. Assessment calls the pure retained verifier, supplying the exact expected
   binding, trusted retained digest and current evaluator-source digest. No
   fixture provider, device enumerator or power assessor reruns during this step.
5. The immutable assessment names each failed check. A distinct reviewer accepts
   that exact assessment: accepting BLOCKED commits BLOCKED, never PASS.
6. Review rechecks the retained bytes/dependencies before publishing and committing.
   Stop during verification prevents the later publication/commit boundary.

Outer schemas:

- `rocell.rehearsal_arm_identity_stage_open.v1`
- `rocell.rehearsal_arm_identity_receipt.v1`
- `rocell.rehearsal_power_stage_open.v1`
- `rocell.rehearsal_power_receipt.v1`

Power receipts share a schema but their stage and prerequisite bindings must
match exactly; stage 10 cannot replace stage 11. Generic source-prerequisite
receipts remain restricted to the first four stages.

The complete reports are also returned as a bounded operation-result attachment
for diagnostic export. The UI receives compact `arm_identity_evaluation` and
`power_evaluation` projections. The latter shows the latest retained power stage,
not two interchangeable power approvals. Renderer rules are in
[the presentation contract](WIZARD_RETAINED_ARM_POWER_CHECKS.md).

## Restart, Stop and logs

Explicit discovery/open selects the **original** store, requalifies its storage,
and verifies retained evidence. WAITING with a complete report can proceed to
assessment. REVIEW_PENDING restores the exact assessment for a fresh explicit
review. Missing/canceled evaluation, ambiguous evidence, source drift or corrupt
dependencies holds; opening never regenerates a report or silently repairs data.

There are at most 32 primary operations per application launch. The full guided
sequence therefore uses checkpoints: after stage 8, export, close the application,
launch again, discover and reopen the same session, then continue stages 9–11.
Do not initialize a new cell as a substitute for reopening existing progress.
Each launch has its own diagnostic log. Export before closing if full reports
from that launch are needed; later logs are not copies of historical operations.

The user-selected export root is `software/runs/wizard-exports`. Every export
uses a fresh directory and manifest verification; previous reports are preserved.
Keep the original M1 store too. Diagnostic exports are not complete raw-camera
archives, qualified commissioning bundles, physical release or recovery authority.

After eleven reviewed rehearsal stages, `feedback_only_connection` is the next
pending integration boundary. Installed calibration and handoff also remain
pending. All fifteen physical stages remain `PHYSICAL_PENDING` in the app.

## Developer verification

Run the focused no-device adapter and evaluator tests:

```powershell
.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_arm_setup_bindings.py software/tests/unit/test_rehearsal_arm_identity_stage.py software/tests/unit/test_rehearsal_power_stages.py -q
```

The explicit multi-minute Windows/NTFS integration test traverses the original
store, actual binary synthetic captures, optics, arm identity and power checks:

```powershell
.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_rehearsal_optics.py -k real_eleven -q
```

This test disables evaluator replay during reopen and checks unchanged device
attempt counts, WAIT/REVIEW restoration, Stop before review publication, distinct
review and later-stage holds. It does not test a physical arm or camera.
