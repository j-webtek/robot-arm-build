# Physical camera runtime inspection and review

Date: 2026-09-08. Status: implementation plan, before production edits.
Starting source: `d2acf8276a66f48590b2a1d62b3cfd79795b22f2579e353fe40b0d121edc866d`.

## 1. Goal and current evidence

Advance DEV-006/008 of the camera/arm developer playbook toward a usable physical
connection workflow. This is a real installed-file prerequisite, not another
simulated camera or permission to connect. The preceding turn completed the
feedback repair and NC-01 software lifecycle; the complete onboarding goal remains
active. No current original store, export or physical qualification is replaced.

The public Camera page currently has only dormant purpose-specific runtime
candidates and a planning action. Candidate constructors perform no file reads.
Their four fixed helper/build-record hashes alone do not establish the installed
files, current source relationship or any operator review. The actual native
campaign/coordinator/owned-runner chain exists, but the native runner and physical
probe/configure/capture actions remain independently held.

Read-only audit found both fixed executable/manifest pairs match the candidate
pins. Current camera_worker.cpp matches the capture development manifest but not
the historical probe manifest. Preserve that result as a source-closure gap;
matching the executable bytes is a different claim. No historical manifest,
candidate pin, source freeze or binary will be edited to manufacture agreement.

## 2. Deliverable and non-goals

Add two explicit physical-mode Camera actions to the existing service:

1. Inspect the fixed probe/capture runtime pair. Read bounded local files only,
   verify purpose, pins, manifest structure and fixed native-source/artifact
   membership, then retain a complete immutable diagnostic report.
2. Review that exact retained report with a distinct reviewer label and explicit
   file-review acknowledgement. Review records what was seen; it cannot change a
   mismatch into a match or grant runtime registration/driver/device authority.

Show per-purpose executable/build-record/source results and actionable fixed
reasons. The current capture match and historical probe source mismatch must be
distinguishable. Preserve complete inspected evidence and the review for export.
No constructor, view, preview, review, export or restart may re-inspect files.
An explicit new inspection, if offered, must retire the previous review first;
no automatic retry, pin learning, rebuild or refresh is part of this increment.

This does not enable physical probe/capture, add a webcam fallback, load native
DLLs, enumerate devices, install/build software, open serial or energize the arm.
It does not replace source preflight, original-camera prerequisite acceptance,
received-unit evidence, native ownership qualification or motion/contact release.
The current source preflight remains a broader separate report; this new report
binds its own actual file observations directly to the two runtime candidates.

## 3. Inspection contract

Use exact NativeCameraRuntimeRegistration and
NativeCameraCaptureRuntimeRegistration values owned by the acquisition service.
The browser cannot supply candidates, paths, expected hashes, manifests, authority
flags or executable arguments. Candidate source/workspace/catalog/purpose and
registration digests must be internally coherent before any file access.

The inspector and its pure retained verifier share one strict bounded report
schema. The report includes original source and launch, both candidate records,
inspecting operator/time, exact observed file rows, per-purpose comparisons,
fixed gap codes, coverage/limitations, and zero device/process-effect counters.
Canonical immutable bytes and an independently held digest prevent mutation of
an already reviewed snapshot. A hash checks content, not authorship or provenance.

For each purpose, inspect the exact fixed executable and build record, and the
closed source/artifact inventory declared by the known manifest format. Resolve
paths from code-owned allowlists, never arbitrary manifest text. Validate manifest
membership before using its expected hashes. Distinguish missing/unreadable file,
size limit, unsafe path/reparse, pin mismatch, manifest mismatch and source drift.
Retain observed hashes/lengths without copying binaries into the report. Keep
missing observations null/NOT_OBSERVED rather than zero/success. Any uninspected
artifact must be explicitly identified; no claim of full-build coverage is allowed
unless the full declared closed inventory was inspected.

Bounds: at most 40 distinct fixed paths, 8 MiB per executable, 128 KiB per build
record, 1 MiB per native source, 32 MiB aggregate native-file reads, 128 KiB canonical
report, and a 30-second explicit inspection deadline. The separate existing
workspace fingerprint has its own 128 MiB / 4,096-file bound and is checked once
at inspector entry and once at final validation, not per file chunk. Record these
source checks separately. Check Stop/deadline around bounded native reads and
publication. Reuse existing regular-path/reparse and
bounded-read primitives; recheck file stability. Synchronous filesystem calls
cannot be forcibly interrupted, and this must not be called a qualified pinned
execution window. The eventual process owner must independently pin/revalidate
its own files before any launch. No record from this inspector is a permit.

Every inspection/review and view retains false for dispatch_enabled,
driver_qualified, hardware_qualified, connected and physical_authority. File
agreement and reviewed acknowledgement have separate status fields. An incomplete
or drifted inspection may be reviewed as a held diagnostic, never accepted as a
qualified native runtime.

## 4. Service, UI and export join

The acquisition service owns the candidate pair and staged runtime inspection /
review state; do not add a second connection manager. The Arrival service owns
preview tickets, source/revision binding, execution, cancellation, validated
result retention and successful-log publication. Inspection retires old review at
admission. Staged copies publish only after the normal log/result checks succeed;
late failure keeps historical evidence for diagnosis but exposes no current review.

Keep runtime inspection independent of endpoint enrollment and camera-store
creation, so installed software can be checked before the hardware arrives.
Changing source/candidate/context or Stop/log failure withdraws current status.
Fresh endpoint metadata does not make an old file report current executable
authority. Existing native candidates remain immutable and dormant.

The Camera page and terminal use the same compact cached projection, with
status, report digest, operator/reviewer labels, per-purpose match/gap counts,
specific missing/source-drift rows and remaining qualification holds. Raw complete
evidence stays behind explicit details/export, not a giant generic fact table.
Physical mode is required; rehearsal must not fabricate installed-file evidence.
No file check runs when visiting or refreshing a page.

Export the complete last retained inspection and any review in a dedicated
diagnostic attachment before generic result rotation. Reuse the existing eight
attachment slots and 6 MiB aggregate limit; do not enlarge them. Clearly label
CURRENT versus HISTORICAL_HELD, preserve original bytes/hash semantics, and list
omissions if a budget is exceeded. Exports are not runtime registration or proof
that files are still unchanged at execution time. Restart restoration of this
inspection/review is not implicit; a later import/reopen path requires its own
strict original-record verification.

## 5. Ownership and implementation sequence

- Native-camera developer: pure inspector, immutable report/verifier and focused
  file/manifest/purpose/deadline/cancellation tests; publish exact report/projection
  contract before other code depends on it.
- Integration owner: acquisition-service staged state, explicit Arrival actions,
  publication/invalidation, bounded dedicated export, and service integration tests.
- Interface developer: strict compact Camera/terminal rendering, acknowledgement
  labels and no-implicit-action tests against the agreed projection.
- Independent reviewer: audit the actual inspector/service path and add adversarial
  retention/export tests plus a bounded public no-device smoke runner after the
  action contract is frozen. Do not run that smoke against changing production.

Preserve all existing records and unrelated edits. No native rebuild, dependency
install, actual hardware/native metadata/process test, or physical hold change is
included. Use isolated file fixtures for faults and a separately recorded current
source public inspection for the real installed-file baseline.

## 6. Verification and completion for this increment

Test exact candidate types/purposes, wrong source/catalog, missing and extra
manifest membership, swapped helper, mismatched length/hash, unreadable/reparse
files, source changes during reads, Stop/deadline, numeric/Boolean coercion,
unknown fields and report tampering. The pure verifier must reconstruct derived
counts/status from retained observations rather than trust a supplied true flag.

Test service preview/execute once, stale ticket, distinct reviewer, stale report,
result/log/redaction failure, safe historical export, result eviction, no native
client invocation and inert construction/view/review/export. Both rendering
adapters must preserve a held probe beside a matching capture without suggesting
that either is a connected or qualified camera. Keep existing launcher/native
runner physical holds covered by regression.

After freezing source, run a real public physical-mode inspect -> review ->
export walkthrough using the workspace export folder. Expected current baseline:
binary/manifest pins match; historical probe source closure reports a gap;
capture closure is reported according to actual bytes, not hardcoded PASS.
Independently verify export and exact report restoration/presentation. Exercise
UI preview/execute/export in the local browser if available, without devices.
Record exact source, actions, hashes, bounds, test selections and limitations below.

## 7. Larger connection work remains

The parallel audits also found missing physical prerequisite stage-one/two
assessment/review before stage-three received-camera evidence can be accepted.
Existing M1 evidence storage must be reused; a stage-three submission must not
be hidden under stage one. Original prerequisite restoration must eventually
recognize a bounded exact inventory of legitimate evidence roles.

The arm still lacks native metadata enrollment, a physical stages9–12 coordinator
domain, actual manual power-evidence intake, and a physical owned child. The
current coordinator's camera/source final-power rule cannot simply be reused
for an energized arm; its domain-specific final observation needs explicit design.
ReviewedControllerBinding requires real model/firmware/boot/profile evidence,
not just a generic SERIAL metadata checkbox. These are subsequent joins, not
capabilities granted by camera-runtime inspection.

## 8. Implementation and verification record

Implemented and exercised on 2026-09-08. This completes the file-inspection/review
increment, not the full physical connection goal. Production source fingerprint:
`3a77273a31934c4917fcd0a638e25d2bba03b52e0fbaad7cafcbc7500d458fce`.
The active hardware/foundation freeze was not changed.

Focused verification: 41 inspector tests (40 isolated fixtures plus one actual
installed-file test with modeled workspace source), 71 UI tests, 50 independent
Arrival/export/smoke tests, and seven additional late-publication tests. The
five touched Python source files passed mypy; JavaScript syntax and Black checks
passed. Earlier selected service/action/export and setup/enrollment regressions
passed 182 and 252 tests respectively; these selections overlap later broad runs.

The first broad selection passed 2,525 tests with three stale preflight assertions
failing and eight slow tests deselected (326.35 s). The old assertions incorrectly
expected current source to match the preserved historical probe build. A
tests-only correction requires exactly its one known camera_worker.cpp mismatch,
all other checks/comparisons passing, and preserves a separate coherent file
fixture plus real Windows writer/rename-denial coverage. All 50 source-preflight
tests then passed (37.66 s); no production or native file changed. The final broad
rerun passed **2,529 tests**, with eight slow tests deselected, in 306.88 s. It used
the same frozen production fingerprint above and the corrected source-excluded
test expectations. Selection: unit-test filenames beginning with
`test_arrival_wizard`, `test_wizard_`, `test_physical_camera_`,
`test_physical_intake`, `test_physical_source_preflight`,
`test_owned_native_camera`, `test_native_camera_registration` or
`test_native_camera_capture_registration`, with `-m "not slow"`.
This is a selected regression run, not every test in the repository or a physical
hardware qualification. Counts from the focused runs overlap this selection.

### Actual frozen-source public workflow

One public service walkthrough completed in 2.51 s: inspect, review, nine notes,
export. Launch `wizard-faebc66740474248b7db811ec2cd8792`; inspection operation
`operation-3b6503ebebd64dce916352dbe6dda0a7`; review operation
`operation-29df1c20f9384575a85b5108bad6f9bd`.

- Inspection digest: `9a519967073d091c5b028dcf3b9e22552f3fe62d5bc42828df778b8378ba4789`
  (22,552 canonical bytes).
- Export: `software/runs/wizard-exports/wizard-20260908T145318266397Z-fa19059890c14b3b9ef3313fe245e884`.
- Manifest binding: `11c3b9d4ed445f28c34f3ee343d6be57b5babf6fc6eef7a19e3b7d6f36afe0c1`.
- Dedicated attachment: 26,745 bytes;
  `7392e68b106f074f8c483cf3343fa67f5f0fee14bc1a0bff338ea953494b95d0`.

All 27 fixed paths were observed. Both executable/build-record pins match;
probe source closure is 9/10 matching with the historical camera_worker.cpp gap;
probe artifacts are 3/3 matching. Capture sources are 15/15 and artifacts 4/4
matching. Overall file result remains HELD; the distinct-label diagnostic review
is ACKNOWLEDGED_HELD_REPORT. Nine notes evicted both generic inspection/review
results, but the dedicated complete original report/review survived. Pure restore
and manifest verification passed. No physical store, metadata, native helper,
camera, serial, power or motion action was dispatched.

Independent exact-export/presentation verification passed in 1.07 s using
`software/scripts/verify_camera_runtime_export_presentation.py` (source-excluded).
It joins full report, pure codec and cached review, then renders the same snapshot
through actual app.js in a fake DOM and the terminal renderer. Only one GET/view
per renderer occurred; original export/source bytes stayed unchanged. This check
is separate from the real-browser test below.

### Real browser and packaging

A separate local browser session, `wizard-0d5dc5e85d144c119dc42ef8eb6c491d`, exercised
the actual Camera action fields, default-unchecked acknowledgements, previews,
inspection, review and export controls. The pending card withheld observations;
the completed card visibly retained HELD and ACKNOWLEDGED_HELD_REPORT beside the
separate purpose results. The initial page remained revision zero before actions.
No browser warnings/errors were reported. All physical actions stayed held.

- Browser inspection: `operation-418b1553277a4633a55d8778d9e36eef`, digest
  `de9ab2210c4abf0edc12ecff53af1bfdd0fb5cf9b127849cd03758e089f8ab63`.
- Browser review: `operation-085555eb80ab4aa4af02453e78ff6e98`.
- Browser export: `software/runs/wizard-exports/wizard-20260908T145921297351Z-aff7829f55c141c38e8703505d0d2117`.
- Manifest binding: `83bb3f72d25ccf26dd4fe13b5bf91ef1e28e75a15f1f44dbd841bf413018217a`.
- Attachment: 26,739 bytes, digest
  `6345e2ab21c37684b7f0a613aeb139a5c44450351d0969777bcdba53bacecede`.

The second export also passed the independent pure-codec/presentation verifier.
The temporary browser tab and owned test server were closed; its port 61865 had
no remaining listener. No unrelated user session was closed. Browser validation
used the computer-use skill's observation/action checks and background tab.

Both launcher modes passed their inert startup check. An offline, no-dependency,
no-install wheel build from explicit `./software` produced
`software/runs/wizard-package-check-3a77273a/rocell-0.1.0-py3-none-any.whl`:
1,866,934 bytes, SHA-256
`7bada3401839172e71cd308b8ac2167353503dce3f8ff21b5684ec2a03c1fe77`.
All 255 packaged source/assets matched the workspace bytes.

Packaging correction: an initial command used bare `software`, which pip resolved
as an unrelated registry package and downloaded/built without installing. Its
1,394-byte wheel was renamed with `.NOT-A-ROCELL-ARTIFACT` in that package-check
folder and is excluded from deliverables. The corrected build used `--no-index`
and the explicit local path. No package or driver was installed. No native camera
binary, manifest, fixed pin, historical session or physical qualification was
modified by either packaging check.

### Implemented workflow and developer map

The two registered Camera actions share the existing preview/execute ticket,
source binding, single-operation worker, Stop and completion-log boundaries.
`physical_camera_runtime_inspect` accepts only `operator_id` and the explicit
`file_inspection_only: true` acknowledgement. `physical_camera_runtime_review`
accepts only `reviewer_id` and `file_review_only: true`. Neither accepts a path,
camera index, command, hash override, trust flag or scenario. A reviewer label
must differ from the inspection operator ignoring capitalization; labels do not
authenticate independent people.

| Component | Responsibility |
| --- | --- |
| `application/physical_camera_runtime_inspection.py` | Closed 27-file inventory, separate purpose pins, bounded observations, immutable canonical report and pure verifier. No process/device/M1 access. |
| `application/physical_camera_acquisition_service.py` | Cached report, exact candidate/report context, staged review, current publication only after outer success, historical retention after withdrawal. |
| `application/wizard_actions.py` | Two physical-only semantic actions with no default consent. |
| `application/arrival_wizard_service.py` | Ticket binding, dispatch outside UI lock, final source/context/result join, successful logging prerequisite, reserved full-report export. |
| `ui/static/app.js`, `ui/terminal.py` | Strict compact summary rendering. Pending details withheld; original source/launch retained visibly for historical reports. No implicit reads or action dispatch. |
| `scripts/wizard_physical_camera_runtime_smoke.py` | Explicit frozen-source public inspect/review/nine-note/export walkthrough; no action replay, hardware action or source repair. |

Source paths above are relative to `software/src/rocell`, except the smoke script,
which is relative to `software`. The complete inspection attachment is named
`attachment-camera-runtime-inspection.json`. Its wrapper distinguishes a current
file report from historical evidence and states whether original bytes were
preserved. The contained canonical report digest is distinct from the pretty
attachment digest and export-manifest digest. A pending candidate review is never
exported as a successfully logged review.

### Operator use

1. Start `./start-rocell-wizard.ps1 -Mode physical` from the workspace root.
   Opening the wizard performs no native runtime inspection or device connection.
2. In Camera, choose **Inspect installed camera runtime files**, enter an operator
   label, explicitly acknowledge file-only scope, then inspect the preview and
   confirm that single action. This does not initialize physical-camera storage.
3. Read both purposes: executable/build-record pin results are separate from
   current source closure and declared-artifact results. Preserve any HELD gaps.
   Do not rebuild, alter pins or infer connection from this report.
4. Use **Review exact camera runtime report** with the reviewer's distinct label
   and explicit file-review acknowledgement. Review records the original result;
   it cannot upgrade HELD to FILES_MATCHED or unlock acquisition.
5. Record investigation notes if needed, then choose **Export diagnostic report**.
   The assigned root is `C:/Users/Jack/Desktop/robot-arm-build/software/runs/wizard-exports`;
   each export is a new child directory with a verified manifest. The complete
   last retained inspection survives generic result rotation.
6. Export before closing. A new app launch does not silently restore a runtime
   review, reconnect hardware, reapply settings or retry a failed action.

If source, result retention, logging or Stop interrupts the workflow, investigate
the original retained historical report and export available diagnostics. A
verified export is not proof of current file ownership, trusted release, camera
identity, physical calibration or permission to move.
