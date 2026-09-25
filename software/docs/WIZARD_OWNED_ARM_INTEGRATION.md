# Owned arm-feedback integration checkpoint

Date: 2026-09-08. This increment joins the existing onboarding application to
an actual isolated arm-feedback process using an **incapable serial backend**.
It is working software-path preparation, not received-hardware qualification
or permission to start the RoArm. The selected diagnostic export folder is
`software/runs/wizard-exports`; every export gets a new directory.

This follows [actual-source preflight](PHYSICAL_PREFLIGHT_INTEGRATION.md) and
implements another part of the [connection plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md)
and [developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md). Freeze 011, controlled
placemat geometry and the physical camera/arm activation gates are unchanged.

## Use the application

```powershell
.\start-rocell-wizard.ps1
```

In **Guided rehearsal**, complete and review stages 1–11, then collect the
feedback-only stage. Choose **Run contained incapable arm-feedback rehearsal**,
select `nominal`, preview and explicitly confirm. This is a separate action
from the original memory-only feedback campaign; the original remains available.

The operator cannot supply an executable, port, raw command, path, deadline or
arbitrary scenario. The selected controller and prerequisite evidence come from
the reviewed server-owned session. The only feedback request is the existing
fixed T105 request; no motion or contact command is introduced.

Read the process, serial/native, feedback and synthetic-power results separately.
Only a complete known campaign can enter assessment and explicit review. A
rehearsal PASS is not a physical PASS. On a fault, preserve the original store
and use **Diagnostics & exports**; do not clear uncertainty or replay the attempt.
The software Stop button is diagnostic cancellation, not an emergency stop.

Detailed screen and reopening rules: [operator/UI guide](WIZARD_OWNED_ARM_FEEDBACK.md).

## How the pieces fit

| Piece | Role and boundary |
| --- | --- |
| Action registry and Arrival service | Closed scenario, preview/execute, cached raw-free cards, completion-log publication, assigned-folder exports |
| Rehearsal service | Verify reviewed stage dependencies; explicitly build a development runtime; create fresh synthetic envelope after slow admission preparation; owned-only one-lease prepare/execute window with fresh reads retained |
| `owned_arm_feedback_rehearsal_campaign.py` | Bind full plan/runtime/directory/scenario to registration; acknowledge one consumed permit; recheck original scope; retain full result before known sealing |
| Runtime package | Deterministic closed ZIP of actual worker/backend/dependency source, fixed inert namespace initializers, source and executable pins; development-only, not a signed release |
| Owned Windows runner | Actual owned process/Job, bounded pipes and timeouts, actual-PID challenge, one RELEASE plus EOF, independent cleanup, shared unresolved-process hold |
| Incapable child | Actual feedback worker and non-purging owner against a fixed in-memory Win32 API; physical native DLL activation remains blocked |
| Evidence and assessment | Independently verify exact request, raw retained records and process/native lifecycles; derive separate predicates; never infer final power from cleanup |
| Original-store reopening | Verify original permit, full evidence, assigned directory, scenario, assessment and review; no package rebuild, device access or worker replay |

Read [IPC/evidence](ARM_OWNED_IPC_EVIDENCE.md) and
[runtime/runner](OWNED_ARM_FEEDBACK_RUNNER.md) before extending the lower layers.
The [single-lease dispatch contract](SCOPED_REHEARSAL_DISPATCH.md) explains
phase restrictions, fresh checks and final lease-cleanup handling.
Constructors, status and historical reconstruction are inert. Package preparation
is an explicit local write and cannot substitute for authorization to execute.

## Important evidence distinctions

- A retained READY/RELEASE record alone does not prove the final write occurred.
  Check independently verified process status, byte accounting and the returned
  child result. A denied final authorization cannot pass.
- A complete record can describe a failed serial operation. `COMPLETE_INCAPABLE_EVIDENCE`
  is not a success label for the feedback transaction.
- Final power remains unknown to both the process owner and serial worker. The
  separate post-campaign fixture is explicitly synthetic, references both the
  actual inner feedback hash (nullable when absent) and owned-process evidence
  hash, and never claims a human/sensor measured physical de-energization.
- Full private serial/child bytes stay in immutable M1 campaign evidence. Browser,
  terminal and ordinary diagnostics show bounded summaries, hashes and errors.
  An ordinary export is not the original store or a commissioning authority bundle.
- Parent campaign budget is 20 seconds; inner feedback budget is 5 seconds with
  a 2048-byte line cap. Admission and independent cleanup have separate bounds.
  No renewal, automatic retry or fallback is allowed after a consumed attempt.
- Full campaign retention is capped at 128 KiB. Oversize evidence is refused,
  never truncated into a passing result. Observed pipe-prefix hashes are not
  hashes of unseen output when overflow occurs.
- Source changes invalidate current results. Keep the source fixed through a
  campaign and its restart test; do not rebase old source-bound evidence.

## Verification record

### Current versioned-handshake checkpoint

Source fingerprint, fixed throughout the current integration run:
`8ff7b119ca3b2045094dc20ec0892fa04a02de2af4014ad14e0a4dbc64668d66`.

- Broad non-slow selection: **2,173 passed, 3,734 deselected**, 226.82 seconds.
  This is a selected regression lane, not the whole repository suite.
- Included focused coverage: 75 protocol/evidence cases, 40 owned-runner cases,
  12 application bridge cases and 5 smoke/export cases. Counts overlap the broad
  selection. Real fixed-child tests accept a three-second live validation and
  refuse a 5.1-second validation before RELEASE; timeout retains request-only
  stdin, no serial/native evidence and confirmed process-tree exit.
- Historical v1 records remain structurally decodable at their original
  two-second bound. Current preparation/child refuse v1 execution, mismatched
  timing/version pairs and insufficient original lifetime.
- Mypy passed for fourteen integration modules; Black checks on those fourteen
  modules and the browser JavaScript syntax check passed.
- Physical-mode inert startup: zero operations, camera/arm `NOT_CONNECTED`,
  fifteen `PHYSICAL_PENDING` stages, contained rehearsal action disabled and
  the assigned workspace export directory retained.
- Foundation verification returned `VALID_ZERO_AUTHORITY_FOUNDATION`, six
  contracts, runtime activation false and zero device/power/command effects.
  Workcell inspection returned `PASS_NOMINAL_ALIGNMENT_WITH_PHYSICAL_HOLDS`
  for `RC03-INT-R1` and `ROCELL-SIM-BUNDLE-RC03-INT-R1-FREEZE-011-011`;
  alignment report SHA-256:
  `eb29cf656ac7fbe96ad86750faa7a2cf01de12c7b0b8c215ceb7fffebe1c7290`.
- Offline wheel assembly passed. All **237** workspace Python/HTML/CSS/JS
  package entries matched the wheel byte-for-byte. Artifact:
  `software/runs/wizard-package-check-8ff7b119/rocell-0.1.0-py3-none-any.whl`,
  1,708,465 bytes, SHA-256
  `7b76b64eae2136c3292725f1e32f913c35296099f0880f1a38d35ddf7f67c2ec`.
  This is assembly verification, not physical release qualification.
- Nine related guides: all 162 local Markdown link targets existed.
- Seventeen additional historical-inspector tests passed using full incapable
  worker evidence in labeled structural envelopes and real temporary-folder
  exports. The inspector and five smoke/export cases also passed together
  (**22 passed**, 1.48 seconds). These do not constitute a full M1 audit.
  Direct source/permit joins and ordered integer timestamps must agree with
  the exact inner request and retained process duration before export.
- The actual preserved v1 timeout record was structurally inspected under the
  new decoder without reopening or replaying its session. Its payload hash
  remained `41051b535bfc035389f3500064f53ba4364fecf33b0f1057134ecdad77902f18`;
  the new verified diagnostic export is
  `software/runs/wizard-exports/wizard-20260908T081428920951Z-548a3e1d0f904f2cab117a882188bf39`.

### Completed public-service/M1 workflow

The fresh full run **passed with exit code 0** on the same `8ff7b119…` source,
which matched again after completion. It used actual original NTFS/M1 stores,
the public service actions and the real owned incapable arm child. No physical
camera or serial endpoint was accessed. No old failed attempt was replayed.

Original rehearsal session: `rehearsal-dc27132f234d4c56abc7b618edea2573`.
Original store:
`software/runs/wizard-rehearsal/wizard-d2540f8c2b614c76970d1be88c36e5f8`.
Owned attempt: `attempt-1e986737794443a69b04a8447d2cd9cc`.
Retained owned evidence SHA-256:
`e2938eb1d901e4dd1bfbdf9061ee9ef942a1cce57fb52f49b2fec28fd24654aa`.

The complete path verified:

1. All eleven prerequisites, collection and explicit review, including original
   session reopening before the arm campaign.
2. One contained arm-feedback campaign, complete retained evidence, successful
   child exit (code 0), confirmed tree exit, valid fixed feedback response,
   independently confirmed incapable native/serial cleanup and separate
   synthetic final-power observation. No cleanup result asserts physical power.
3. Reopening the published feedback receipt before assessment, assessment,
   another restart and explicit review. No feedback transaction was repeated.
4. Nominal reference-frame fitting, retained report, restart, assessment,
   restart and explicit review: all thirteen implemented rehearsal stages PASS.
5. A final original-store reopen with camera/arm workers, package preparation,
   upstream evaluators and calibration computations patched to fail if called.
   This passed and verified a final diagnostic export. The attempt ledger
   remained at fifteen events; physical stages remained fifteen pending.

The final stage is `noncontact_acceptance`: stages 14–15 are not joined yet.
This was the complete developer smoke, not a rerun or relabeling of the earlier
failed pytest slow lane. Browser/terminal projections are covered separately by
the focused tests; this smoke drives the shared public application service.

Selected verified exports below are relative to `software/runs/wizard-exports/`.
Each restart creates a distinct diagnostic launch; the original M1 rehearsal
session above remains the same. These exports do not replace its original store.

| Checkpoint | Export directory | Verified manifest SHA-256 |
| --- | --- | --- |
| Owned feedback result | `wizard-20260908T081715173244Z-b9c1cfe49aef4acb8f2c25b36779fbb2` | `e62cc43d617f32b12c22861a2b408f303e2538e6060ffbfa027062a435ead4a3` |
| Full reference report | `wizard-20260908T081901734535Z-8a1db01467aa4854b45c0608471ef7ea` | `190ef9ebe0c95d5c398fcd968f94a58a71c1852b61f3c217c9c80c487a29f21f` |
| Completed-store replay-forbidden verification | `wizard-20260908T082102782830Z-882664cee7934cac88c031a5bd0c4f3e` | `a76d0a1213968f38e7d413bd77de64d64d25d2d6b8ce6c35428334f76f1ae597` |

### Previous checkpoint and preserved failed runs

Previous tested software checkpoint (before the versioned handshake correction):
`05db1c6720ecb75ca994a77b0616d52aa726aaf2371522ed31b44831eb3c12d8`.

- Broad non-slow selection: **2,153 passed, 3,734 deselected**, 241.58 seconds.
  This is not the entire repository suite.
- Included focused coverage: 63 protocol/evidence cases, 37 owned-runner cases,
  12 application bridge cases, 18 single-lease adapter cases (four with actual
  new NTFS/M1 stores), plus existing feedback/coordinator/UI regressions. These
  overlap the broad selection; do not add them as unique totals.
- Actual child and bridge tests include nominal feedback, serial fault paths,
  cancellation, denied admission, malformed output, missing independent power
  evidence, no replay and pure historical reconstruction. A timestamp regression
  rejects an observation preceding the retained full process duration.
- Inert physical-mode CLI startup: zero operations, camera/arm `NOT_CONNECTED`,
  fifteen `PHYSICAL_PENDING` stages, owned rehearsal action disabled, correct
  assigned `software/runs/wizard-exports` folder.
- Mypy passed for all thirteen integration modules; Black found no formatting
  changes needed in those modules; the browser JavaScript syntax check passed.
- Offline wheel built; thirteen changed source/UI entries matched the workspace
  byte-for-byte. Artifact: `software/runs/wizard-package-check-05db1c67/rocell-0.1.0-py3-none-any.whl`,
  1,707,970 bytes, SHA-256
  `02f45cf4e13a53e35a50069ebad559e433fcb0e2168df17115a8d21a2a6a65c9`.
  This verifies assembly, not a signed/independently qualified release runtime.

Focused tests use actual owned child execution, the existing feedback worker
and non-purging backend, protocol faults, pure reconstruction, scoped coordinator
retention, and both renderers.
Protocol-store doubles are not durability tests; real NTFS/M1 tests are labeled
separately. No test here uses a physical camera or serial endpoint.

The first full public-service/M1 run on source
`f8f169770c7e23d3092e18de14068ca865db3b8f4fd4ce3ed36a5505e30d1f1f`
passed all eleven predecessors and reopened the waiting feedback stage, then
stopped **before any arm reservation or child dispatch**: repeated lease setup
left insufficient coverage in the original synthetic envelope for the declared
20-second campaign. The exact public failure was `energization envelope cannot
cover the bounded campaign`. That attempt was not replayed. This exposed a
software integration timing issue, not a serial/hardware result. The correction
keeps one actual qualified lease across preflight, preparation and execution,
retains every fresh admission/current-state check, and does not extend the
original envelope or worker budget. Its final verification is recorded separately.

The second full run, on `05db1c67…`, passed the original M1 admission and
launched the contained incapable child, but stopped at `ARM_RELEASE_TIMED_OUT`.
The mature session's fresh consumed-permit validation exceeded the old
two-second child RELEASE wait. The child received only the 3,328-byte REQUEST;
the parent retained 227 bytes of READY and confirmed the process tree exited.
No RELEASE or serial request was sent and no feedback/native result existed.
The retained RELEASE field records a constructed message, not a delivered one.
The original attempt was sealed uncertain and was not replayed:
`attempt-b4868915928f490a8ce70923177a5368` in session
`rehearsal-1d67c5d56bca49159b61cec6d531ca69`.

The complete failed campaign remains in its original store under
`software/runs/wizard-rehearsal/wizard-e3e47429fb8c479f87b12c34f1b0c9b7`.
A verified raw-free historical inspection export is at
`software/runs/wizard-exports/wizard-20260908T075909173375Z-bb30b840c6ab4bc2a04404815d6f8600`.
The inspector checks structural/hash joins, not the complete M1 audit or
current qualification. Retained payload SHA-256:
`41051b535bfc035389f3500064f53ba4364fecf33b0f1057134ecdad77902f18`.
Process duration was 5.437 seconds; full wrapper duration was 5.453 seconds.

The correction uses a new arm request version with a fixed five-second
admission bound, explicitly bound into the operation/permit. Pure decoding of
the old request version preserves its original two-second bound for historical
diagnostics; it cannot execute using the new runtime or borrow the new budget.
Parent campaign, original envelope, inner feedback and cleanup bounds remain
unchanged. Focused and fresh end-to-end verification of this correction is
recorded below when complete; the prior failed runs are not success evidence.
The developer smoke now attempts a diagnostic export before propagating an
owned-campaign failure, without retrying the campaign or repairing the store.

Reproduce the multi-minute public-service workflow and chosen-folder exports:

```powershell
.venv/Scripts/python.exe software/scripts/wizard_arm_setup_rehearsal_smoke.py --owned-feedback --reference
```

Omit `--reference` for the twelve-stage path. To inspect the completed original
session without replay, while the source still matches:

```powershell
.venv/Scripts/python.exe software/scripts/wizard_arm_setup_rehearsal_smoke.py --verify-completed rehearsal-dc27132f234d4c56abc7b618edea2573 --reference
```

This explicitly writes a new ordinary diagnostic log/export and reads the
original store; it does not rebuild packages, run workers or change reviews.
Do not use this command to migrate a source-mismatched session.

## Remaining plan work

This does not finish the full onboarding plan. Remaining work includes the
qualified physical camera runtime/admission and retained physical frame path;
the physical non-purging serial API and reliable received-controller resolution;
actual firmware/startup and independent power observations; physical calibration
and contact/force qualification; the final two rehearsal-stage joins; and the
separately authorized typing/tapping executor. Installed camera mode, view
coverage, placement, board geometry and accuracy still require arrival evidence.

The next physical integration should reuse these exact boundaries, not relabel
incapable evidence or add an unrestricted command box. No hardware execution is
enabled by this checkpoint.
