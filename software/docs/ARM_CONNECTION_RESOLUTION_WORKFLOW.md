# Arm connection rehearsal: fresh controller identity at both boundaries

Date: 2026-09-08. Implementation checkpoint for the
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md).

This implements an end-to-end **hardware-incapable connection rehearsal**. It
does not release physical serial access, energize or initialize the RoArm, move
the arm, calibrate the installed board, or type/tap on received hardware.
The purchased static Arducam camera architecture and active hardware freeze are
unchanged. The broader application goal remains in progress.

## What changed and why

The contained arm child previously returned the expected controller identity
from a fixed callback. That tested serial lifecycle behavior but skipped the
production Windows metadata acquisition and matching path. The new child uses:

```text
Reviewed synthetic stage-9/10/11 predecessors
  -> explicit modeled native transport binding (original generic review retained)
  -> original scoped permit + pinned incapable child + READY/RELEASE/EOF
  -> sealed CM ABI/inventory source
  -> actual WindowsControllerMetadataAcquirer
  -> actual ExplicitArmControllerResolver: PRE_OPEN
  -> actual ArmFeedbackWorker + NonPurgingArmFeedbackBackend: modeled open/quiet check
  -> a second fresh acquisition and resolution: PRE_WRITE
  -> one fixed T105 request, bounded response, serial cleanup
  -> retained trace + feedback + native lifecycle + actual process outcome
  -> M1 retention/assessment, logged wizard projection and assigned-folder export
```

Only the metadata source and serial API are incapable fixtures. CM property
decoding, inventory consistency checks, controller matching, worker behavior,
result validation, process ownership and the wizard integration use application
code. No DLL or host inventory fallback exists in the sealed producer.

The generic stage-nine fixture is not a native Windows observation. Its
`usb-unit:` identifier cannot be used as a `\\?\` native interface path.
`owned_metadata_feedback_binding` creates an explicitly modeled transport and
retains the full `generic_reviewed_controller` separately in binding.v2. This
happens before admission. Memory-only feedback and historical generic bindings
remain unchanged; physical bindings cannot use this adapter.

## Developer ownership and contracts

| Component | Responsibility |
| --- | --- |
| `rehearsal_feedback_binding.py` | Pure reviewed-predecessor lineage and explicit owned native fixture adaptation. |
| `incapable_controller_metadata.py` | Sealed five-function CM ABI facade and two bounded inventory acquisitions; no device API. |
| `controller_metadata.py` | Existing real Windows metadata decoder, before/after inventory/interface checks and original deadline. |
| `arm_controller_resolution.py` | Shared strict snapshot decoder, exact comparisons, two-attempt trace, pure trace verification and compact summary. |
| `_owned_arm_feedback_child.py` | Closed isolated runtime bootstrap, release gate, production resolver/worker/backend composition. |
| `arm_owned_protocol.py` | Exact versioned request/result schemas and trace/feedback/native evidence joins. |
| `owned_arm_feedback_package.py`, `owned_arm_feedback_runner.py` | Pinned closed package, bounded actual child lifecycle, current execution versus historical reconstruction. |
| `owned_arm_feedback_rehearsal_campaign.py` | Original permit/operation/deadline binding, full evidence retention and independent assessment predicates. |
| `commissioning_rehearsal_service.py`, `commissioning_rehearsal_reopen.py` | Due-stage workflow, separate generic/native binding lineage, original-store verification, cached diagnostics. |
| `arrival_wizard_service.py` | Logged publication, explicit actions, Stop/source holds and assigned-folder export. |
| `ui/static/app.js`, `ui/terminal.py` | Existing arm card with PRE_OPEN/PRE_WRITE details; no new hardware authority. |

The UI consumes verified compact summaries, not browser-supplied identity,
snapshot, COM path, command, backend or deadline values. Merely viewing a panel
does not acquire metadata or rerun the feedback transaction.

### Trace integrity and ordering

`ExplicitArmControllerResolver.retained_trace()` returns a bounded immutable
`ControllerResolutionTrace`. Each attempted boundary retains the complete
snapshot and comparison when available, their hashes, phase, timestamps and
fixed refusal code. A snapshot returned too late is retained but cannot supply a
usable identity. An acquisition that raises before returning has no invented
snapshot. Missing data and a failed comparison are distinct.

`verify_controller_resolution_trace` takes the exact reviewed binding, original
deadline, independently expected trace hash and optionally the actual feedback
result. It re-runs only pure comparisons. It checks identity-check counters,
successful PRE_OPEN before open, successful PRE_WRITE before a write, timing
against worker events, and held phase/error consistency. Hash equality alone
does not establish a successful connection. No verifier enumerates or opens a
device.

The trace limit is 16 KiB; nested result remains 48 KiB and owned aggregate
128 KiB. The observed nominal fixture trace was 8,140 bytes, nested result
20,691 bytes and owned evidence 54,146 bytes in focused testing. Sizes vary with
bounded identifiers and timing values. Oversize retention holds rather than
truncating evidence into a success-shaped result.

Ordinary worker-result cards contain only the compact trace status/hash with
`FULL_TRACE_IN_DEDICATED_EXPORT`. The full trace uses its reserved attachment,
avoiding extra `steps/report` nesting. A failed outer action cannot publish a
current arm card even when inner M1 retention succeeded. See the
[preserved initial publication failure and repair](ARM_RESOLUTION_PUBLICATION_INCIDENT.md).

### Version and timing policy

Current execution requires request.v3, result.v2, runtime.v2 and preparation.v2.
The runtime includes the four explicitly listed metadata/resolution modules,
not a recursive application import tree. Historical runtime.v1 has its original
closed roster. Request.v1/v2 and result.v1 remain historical read formats, never
an execution fallback. Legacy summaries remain their original schema and gain
only a presentation caption: **NOT_RETAINED**, not a newly passed identity check.

READY and RELEASE remain v1. Request.v1's historical admission wait is 2 seconds;
v2/v3 use 5 seconds. The current change does not renew or extend the original
permit, 30-second synthetic envelope, 20-second owned campaign, 5-second inner
feedback budget or 2-second cleanup bound. The one-use scope is rechecked before
release. Process exit, serial close and independently modeled final power remain
different observations. Stop is not an E-stop or proof of de-energization.

## Use the wizard

From the workspace root, launch the local browser interface:

```powershell
.\start-rocell-wizard.ps1
```

Rehearsal is the default. To inspect startup configuration without starting a
server or opening a browser, use `-Check`; `-Ui terminal` selects the terminal
interface. The launcher's `-ExportDirectory` override remains available, but
omit it here to use the user-confirmed workspace export folder. Switching to
`-Mode physical` does not grant device access or bypass the pending stages.

Follow [the workbench walkthrough](WIZARD_WORKBENCH.md) in rehearsal mode. Review
the existing camera/optics and arm identity/power prerequisites, then open the
due **Feedback-only connection** stage. Choose **Run contained incapable
arm-feedback rehearsal**, inspect its exact preview and confirm once.

The nominal outcome should show both PRE_OPEN and PRE_WRITE metadata matches,
one bounded feedback exchange, separate serial/process cleanup, and separate
synthetic final-power evidence. Assess the retained evidence and review the exact
assessment as a distinct rehearsal reviewer. These are rehearsal stages only.

Closed fault choices include `identity-change-preopen`, `identity-change`
(pre-write), and `malformed-metadata`, alongside existing startup bytes, short
write, response timeout/malformed/extra data, cleanup failure, child timeout and
malformed-result scenarios. Each fault attempt is one-shot. Inspect/export an
uncertain result; do not retry it, clear quarantine or replace its original
records to obtain a passing result.

The nominal developer walkthrough is:

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_arm_setup_rehearsal_smoke.py --owned-feedback --expected-source-sha256 <verified-current-source>
```

For this dated checkpoint, `<verified-current-source>` is the complete
`64c699d7...` fingerprint in the verification record below. Compare it with the
startup check before running; the placeholder must be replaced, not entered
literally in PowerShell.

It creates a new isolated rehearsal, exercises real local storage and the
public service API, reopens the original records, rotates ordinary result cards,
and checks the reserved resolution export. It never opens an actual device.
Keep production source fixed for the entire run; never migrate an older store
to a new source fingerprint. The script's review actions are test labels, not
claims of a physical safety review.

## Diagnostics and restart behavior

The user-selected export root is:

`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`

Each explicit export writes a new uniquely named folder, readable report and
verified manifest. `attachment-owned-arm-connection.json` reserves a slot before
ordinary result rotation. During the original launch it includes the complete
bounded controller-resolution trace when the child returned one. The export
compares sanitized versus original data and marks redaction explicitly; redacted
data is not the original evidence named by its hashes. Budget overflow is an
export failure, not a truncated successful export.

After a verified original-store reopen, this diagnostic attachment restores the
verified compact trace summary and hash. It explicitly says
`FULL_TRACE_NOT_RESTORED_USE_ORIGINAL_M1`; it does not claim that the complete
trace is included. Full trace, serial exchange and child streams remain in the
original immutable M1 campaign record. Export before closing when the full
metadata attachment is needed. Neither export nor status reads copy operational
ledgers, raw serial streams or camera pixels.

## Verification record

Verified public-workflow source after the publication/history repairs:
`64c699d73d432bb34e79a96defb7765d816652180efc7cc4e1db86608122145b`.

Focused checks have passed: 184 resolver/metadata tests; 139 protocol/evidence/
runner tests; 72 browser/terminal presentation tests; 79 root binding/campaign/
public-action/export tests. These selections overlap and must not be added into
a purported unique total. The real contained child uses only incapable metadata
and serial sources. Presentation tests use both production renderers with a
modeled browser DOM, not a newly observed live browser session.

The first public run on `3e993f36…` failed at outer result publication, despite
successful inner synthetic evidence retention. Its verified failure export and
original attempt remain preserved without replay. The compact-result and
historical operation-v1 repairs are implemented; eleven dedicated historical
tests and the real-trace compact-result/export regression pass.

The fresh full public walkthrough completed with exit 0 on this fixed source:
all twelve rehearsal stages reviewed, original-store reopening and assessment
verified, and completed-stage replay forbidden. Reference-frame calibration,
noncontact acceptance and handoff were not run by this twelve-stage selection;
all fifteen physical stages remain pending. The original store is
`software/runs/wizard-rehearsal/wizard-5c51398b4f9141848b789f64e3259e95`,
session `rehearsal-6adda885280442a5aa1767bbd0f7e094`.

Retained connection evidence:

- Successful owned action: `operation-1349a81494ff4e8980c7e4ef55b80502`.
- Owned evidence SHA-256: `4ae66e3bc4bccaa7b6a2e8699704dec814bef773abab7364683e27d2fa443cbb`.
- Resolution trace SHA-256: `43e184bfffd8c8653cfce307e57b53070da758c24641961425b2e208fa7e31dd`.

These exports live under the assigned `software/runs/wizard-exports` root;
each complete manifest and every listed payload were verified:

| Check | Export folder | Manifest SHA-256 |
| --- | --- | --- |
| Complete trace after nine notes rotated ordinary result history | `wizard-20260908T183522244189Z-370e989f0e0f4025824a0b71588783d6` | `ae657a8ab2abb7363dcc79eed468ab921507ff5d2247f22fb5555917e2660f6e` |
| Reopened receipt and assessment; explicit compact-only trace | `wizard-20260908T183620714544Z-2b0d45ca92f84b32bb6475e76059eefe` | `f47974137f87ebead2cce228c168ce2197a3f1b1dff90cd5d4480e9e1588bc74` |
| Twelve reviewed stages after another original-store reopen | `wizard-20260908T183720962588Z-5381bfa52490482eb05cd8c2aced791d` | `658ed2a552ae7a6f9dce8d32a7dd4028f5da42b33f8da3990d284e5f08cfaee3` |
| Final completed original-store verification with replay forbidden | `wizard-20260908T183757901494Z-fb80657864614d1294aa38f979c928cb` | `1a9edae250bd4cbcc588acd395aa4ed15bb43e6b6524c9316dee36a89445182b` |

The full connection attachment was 23,786 bytes; its original trace hash and
compact summary matched the current published arm card. Reopened attachments
were 9,706 bytes and explicitly excluded the full trace, preserving its hash.

Final-source bounded reruns: 184 metadata/resolution tests passed in 1.50 s;
150 protocol/evidence/runner/history tests passed in 63.26 s, including finite
contained incapable children; 105 UI/publication tests passed in 14.29 s (one
actual-child test deselected in that UI-only run); and 47 campaign/binding tests
passed in 33.01 s, including finite actual incapable children. These four
disjoint file selections total 486 passing tests. Runner and campaign selections
independently verified the same source fingerprint before and after execution.

Two overlapping broad runs were interrupted rather than left running alongside
a third. The earlier run began during production edits and printed one failure
marker; it did not produce a final failure traceback or suite result before
interruption and is not release evidence. The second printed no failures before
interruption but is not a passing result either. Both included seven genuinely
multi-minute full-NTFS workflow cases that lacked `slow` labels. Only those six
functions (seven cases) received labels; assertions and production code did not
change. The fresh fixed-source non-slow regression then completed: **1,335
passed, 34 deselected in 353.32 s**, exit 0. Its selection overlaps the 486
focused tests and is not an additional unique test count. This result is separate
from the successful full public walkthrough above. Excluding a slow test does
not count as passing it; the earlier interrupted failure remains unattributed.

Reproduce that scoped regression from the workspace root:

```powershell
$armWizardTests = rg --files software/tests/unit -g '*.py' | Where-Object {
    [IO.Path]::GetFileName($_) -match '^(test_arrival_wizard|test_wizard_.*arm|test_wizard_feedback|test_rehearsal_feedback|test_commissioning_rehearsal|test_scoped_rehearsal|test_owned_arm|test_arm_controller|test_incapable_controller|test_arm_resolution|test_rehearsal_reference)'
} | Sort-Object
.\.venv\Scripts\python.exe -m pytest @armWizardTests -q -m 'not slow' -k 'not actual_child and not actual_owned_child' --durations=10
```

Rehearsal and physical-mode `start-rocell-wizard.ps1 -Check` both exit 0. The
physical view reports the chosen export root, no connected arm, no automatic
connection or initialization, and all fifteen physical stages pending. Offline
wheel build also passed; all 259 Python/HTML/CSS/JavaScript entries match source.
Wheel SHA-256: `e6320acef475c690b0277fb4aa3acae132b6e800e84f4541269dd6b17719bc87`.
This is a package-content check, not a clean-host installation or hardware test.
Both existing native camera executables and their manifests remain unchanged.

## Remaining application work

1. Finish genuine physical prerequisite admission and original-scope dispatcher
   joins for the camera and arm; do not substitute staged notes or simulated
   facts for accepted evidence. Physical native release remains held.
2. Join authentic reviewed controller binding, received firmware/boot behavior
   and supervised power evidence to the physical feedback path. Connection must
   not automatically home, torque-enable or replay commands after restart.
3. Complete calibrated static-camera placement, actual intrinsics/distortion,
   board/reference registration, tool offset and surface/contact measurements.
4. Finish noncontact NC-02/03 and handoff acceptance, then separately authorize
   low-speed motion and contact. Physical keyboard/phone execution is not yet
   available through this workbench.
5. Add explicit export/recovery of full retained metadata after restart through
   a bounded original-store read contract, if needed; do not add implicit replay.

The [camera data workflow](PHYSICAL_CAMERA_CAPTURE_WORKFLOW.md) remains the
companion implementation for native-reported settings, validated YUY2 datasets
and logged last-frame publication. The arm slice does not bypass its missing
physical admission/dispatch joins.
