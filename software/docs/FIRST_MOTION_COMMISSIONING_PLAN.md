# First-motion commissioning implementation plan

## Current requirements update — 2026-09-13

Use [Observational bench testing](OBSERVATIONAL_BENCH_TESTING.md) for the revised
basic functional-test requirements. Operator observations and available telemetry
replace mandatory precision measurements in the planned observational workflow.
The measured v1 executor described below has not yet been migrated; its numeric
fields must not be filled with invented measurements to bypass that distinction.

Decision: Jack's “do whats best” selects development of a separate, supervised
commissioning procedure. This does not certify the present physical setup or
approve an unreviewed numeric movement. The existing endpoint guard stays intact.

## Latest checkpoint: ticketed wizard attachment action

`attach_retained_first_motion` now exposes the retained-record bridge through the
normal wizard preview/execute flow. Select a successful generated draft and one
explicit APPROVED operation for each of the five engineering checks. Choices
come from this session's successful receipts; their labels include selection
digests. Mixed-selection or stale reviews are not approved by their presence in
the dropdown: attachment revalidates the actual originals and exact draft.

The existing retained-draft preview also appears for attachment. Empty required
choices, an existing attachment/endpoint binding or a prior commissioning attempt
block the action. Attachment reads the existing private review key but never
provisions it, opens hardware, signs a final operator confirmation or creates a
motion attempt. The separate run action still requires its current conditions and
final-click checks.

Public host attachment/selection methods remain idle-only. Private shared helpers
accept only the current operation context from the attachment runner; callbacks
check cancellation, deadline, closed/log-failed state and exact operation ownership
before and during validation and immediately before installing the attachment.
The implementation never temporarily clears the running operation to bypass the
idle guards. A log failure or interrupted pre-install validation does not install
the candidate; retained diagnostic records are not themselves motion authority.

Validation: `software/runs/first-motion-attachment-action-20260913-01.xml` records
130 passing tests in 15.28 seconds. The actual ticketed attachment path is tested
with synthetic evidence and key, actual original/measurement/review loaders and
an incapable draft assembler. Coverage includes altered references/measurements,
invalid review selection, missing key, repeat attachment, public idle-only guards,
zero hardware counters and absence of a motion attempt. Existing run workflow,
service, catalog and modeled preview tests also pass. Real key/deadline latency,
full browser interaction and physical movement are not qualified by this run.

Next: verify the complete browser selection/review/attachment flow and resolve the
actual supporting evidence, independent geometry/clearance and private key setup.
After an approved live trial, retain independent physical observation alongside
telemetry before progressing into the original finite pose/speed campaign and
evidence-backed settings report. The full objective remains open.

## Previous checkpoint: retained-record attachment bridge

The trusted host can now call `configure_first_motion_from_retained` with only a
successful generated draft operation ID and five explicit review operation IDs.
The bridge reads the canonical generated draft original and checks its successful
receipt hash. It derives support and measurement IDs from that receipt, resolves
the same-session supporting-record association, re-reads each original and checks
its retained hash. No caller-supplied measurement ID, original bytes, paths or
expected hashes enter this attachment path.

It delegates to the existing attachment checks: exact reference hashes, actual
measurement receipt/age/uncertainty, five distinct current approved review
originals, current source, existing private review key and unbound/one-use state.
It neither provisions a key nor opens a device, signs final operator reviews or
creates a launch permit. Attachment remains separate from final confirmation and
the safeguarded executor. The method is a trusted-host API; its browser ticketed
attachment action remains to be wired.

Validation: 66 tests passed in 7.62 seconds, recorded in
`software/runs/first-motion-retained-attachment-regression-20260913-01.xml`.
The new path is exercised alongside the original host attachment path, including
changed supporting/measurement originals, duplicate reviews, missing key and
repeat-attachment rejection. Synthetic evidence/key material and an incapable
draft assembler are used; actual original loaders and attachment checks run.
Existing run/coordinator and review tests also pass. No hardware commands or real
physical approvals were produced.

Next: expose this bridge through a non-actuating wizard action with exact selected
record IDs and operation ownership checks, then verify the entire browser flow.
Do not weaken idle-only host APIs or final-click checks to make that integration
work. Actual geometry/clearance/key setup and live qualification still precede
the original pose/speed characterization campaign and evidence-backed settings
report. The full goal remains unfinished.

## Previous checkpoint: retained-draft engineering review and preview

The normal wizard path now offers `review_retained_first_motion_draft`. Select
one successful same-session generated draft, inspect its cached selection preview,
then explicitly supply reviewer identity, engineering check, decision and rationale.
The default decision remains UNKNOWN. The old JSON-based review action is labeled
advanced; it is not required by this retained-draft workflow.

Draft generation now exclusively saves canonical bytes to an operation-relative
`-first-motion-generated-draft.json` original and includes its SHA-256 in the
successful result. Retained review re-reads that fixed original, compares its hash
with the service-owned successful receipt, validates the canonical draft, then
uses the existing review recorder. It does not copy browser JSON or refresh any
measurement. The resulting five distinct APPROVED engineering records can be
selected by the existing authenticated-review pipeline. UNKNOWN/DENIED records
remain non-authorizing, and every review remains self-reported rather than proof
of physical truth.

The renderer shows the chosen selection digest, unit identity, geometry, command,
references and limits using text content. It warns that cached display is not
current physical verification and that execution rechecks the original. Selection
alone makes no request and does not change the decision. No device was accessed.

Validation: `software/runs/first-motion-retained-review-ui-20260913-01.xml` records
150 passing tests in 14.09 seconds. Coverage includes same-session retained review,
altered-file and cross-session rejection, selection of all five resulting review
originals, existing review/attachment/service tests, and the shipped JavaScript
renderer in a modeled DOM. Draft generation in the service lifecycle test uses an
incapable assembler double; this is not physical qualification or live-browser QA.

Next: connect selected draft/support/measurement/review records to the existing
host attachment path, without accepting arbitrary originals from the browser.
Actual supporting evidence, private review key setup, independent geometry and
clearance, supervised live qualification, and the original finite pose/speed
campaign/settings report remain required. No campaign completion is claimed.

## Previous checkpoint: wizard draft-generation action

`create_first_motion_draft` is now a physical-mode, non-actuating wizard action.
Its two select fields are populated from this session's successful measurement
operations and completely retained supporting-record receipts. Both choices are
required; an empty prerequisite list blocks the action. The normal ticket flow
validates the same choices, and execution re-reads the originals and their hashes.
There is no browser-supplied original JSON, filesystem path, hash, command or time.

The action returns the untimed canonical draft and preview in its retained result.
It does not attach a run, sign reviews, provision a key or access a device. The
private assembler path allows only the currently owning draft operation; public
host helpers continue to require an idle wizard. Cancellation/source checks and
the action deadline still apply. A draft retained before a later cancellation is
not approval and is not automatically promoted to an attachment.

Validation: `software/runs/first-motion-draft-action-20260913-01.xml` records
201 passing tests in 19.27 seconds: service, action catalog, diagnostic runtime,
draft generation/assembly, attachment and run workflow. New service tests exercise
the preview/execute action with an incapable assembler double and verify that
changed supporting bytes fail before assembly. Existing separate tests exercise
the actual assembler. No live browser interaction or hardware qualification is
claimed by these results.

Next: select a retained successful draft directly in the engineering-review form
(that form still asks for draft JSON), provide a readable evidence/preview display,
then attach the exact reviewed selection via the host integration. Supporting
original ingestion remains trusted-host-only; there are no real supporting
records or measurements fabricated by this implementation. Actual physical
qualification and the original pose/speed campaign remain pending.

## Previous checkpoint: retained supporting-original selection

The trusted-host wizard service now provides `retain_first_motion_support` and
`create_first_motion_draft_from_retained`. The first validates and exclusively
saves all seven supporting originals unchanged, logs a receipt, and returns a
wizard-generated record ID. The second resolves that same-session receipt and
re-reads/hash-checks the originals before using the existing measurement-receipt
draft assembler. No caller file paths, expected hashes, posture replacements,
latest-file search or restart recovery are accepted by this selection path.

These methods are host integration APIs, NOT completed browser actions. Retention
means byte integrity, not verified physical truth or engineering approval. They
do not create a key, approve a review, attach a run or access the arm/camera.
Only completely saved and successfully logged sets are selectable. Partial files
remain for diagnosis and are not automatically adopted. Returned receipts are
copies; editing one cannot alter the service's retained association.

Validation: 79 tests passed in 13.87 seconds, including draft assembly, new
retention/selection tests, attachment, run workflow and the arrival wizard service.
Report: `software/runs/first-motion-support-regression-20260913-01.xml`.
The initial focused run exposed a missing first-use log directory; retention now
records intent through the log owner before writing originals. The corrected
focused run passed 22 tests. Synthetic records and incapable hardware doubles
were used; no real measurements, reviews, device commands or live qualification
were produced.

### Host integration sequence and remaining browser work

1. Obtain the seven actual supporting originals from explicit reviewed sources.
   Do not manufacture compatibility, clearance, observation or controller records
   just to satisfy the nonempty JSON check. Their original formats/content remain
   unchanged; later review must assess their meaning and the actual device.
2. Call `retain_first_motion_support(supporting_originals=originals)` and retain
   the returned `record_id` in the host workflow. A failure does not yield a usable
   record ID; preserve its partial files for diagnostics.
3. Record an actual independent measurement through the existing wizard action.
   Retain its successful operation ID; existing measurement age and uncertainty
   checks are not reset by storing or selecting supporting originals.
4. Call `create_first_motion_draft_from_retained` with that measurement operation
   ID and the support record ID. Inspect the returned untimed draft, then obtain
   explicit engineering decisions against its exact selection digest.
5. Still to implement: browser list/selection of successfully retained records,
   draft creation/display without pasted JSON, and host attachment using the same
   selected originals and engineering receipts. Do not expose the raw-byte host
   helper as an unaudited browser approval endpoint.
6. Still required before a live experiment: actual independent geometry and
   clearance evidence, compatible installed-unit/controller review, private review
   key setup, current operator checks, and a qualified connection. Afterward,
   correlate independent physical observation with retained command/telemetry.

The original movement-characterization campaign is still open. No pose/speed
sweep, continuous movement qualification or optimized settings report is complete.

## Previous checkpoint: wizard-owned measurement selection for draft assembly

The trusted `create_first_motion_draft` service method now accepts one successful
same-session measurement operation ID and seven supporting original records.
It reads the fixed measurement filename from its own session root, verifies its
hash against the successful operation receipt, and supplies those exact bytes to
the draft assembler. Caller-supplied posture bytes, paths or expected measurement
hashes are not accepted. The generated preview/digest association is logged; it
does not attach a run, create reviews, provision a key or enable movement.

9 service-selection/assembly tests passed:
`software/runs/first-motion-draft-service-20260913-01.xml`.
Service tests use an incapable assembler double to verify original receipt
selection and reject cross-session operations, altered files and posture override;
separate assembly tests exercise the actual source/build/measurement derivation.
No hardware was accessed or actual physical evidence manufactured.

Next: trusted selection/loading of the other seven evidence originals and browser
draft-generation wiring. Their semantic reviews must remain explicit, especially
installed command compatibility, clearance and observation method. Missing real
geometry/key setup and independent physical qualification still block live testing.

## Previous checkpoint: derive untimed draft from retained originals

`first_motion_draft.draft_from_originals` now assembles a review selection from
eight explicit host-selected original byte records. It derives all original
hashes, reads current source/build hashes, takes unit identity and complete
uncertainty-expanded geometry from the measurement original, then revalidates the
entire measurement's original bytes/session/operation/source/age and derivations.
No manually retyped geometry, zero uncertainty or replacement timestamps are used.

A validation-only request envelope is discarded when returning the untimed draft;
no launch reservation, review key, approval or device access occurs. Source/build
are checked again before return. Caller must still resolve successful same-session
wizard receipts before attaching the draft; structured references do not prove
their semantic compatibility or clearance. This is a trusted host helper, not yet
a browser assembly action.

15 assembly/draft tests passed:
`software/runs/first-motion-assembly-20260913-01.xml`. Synthetic tests reproduce the
exact expected selection digest and reject altered derived geometry, cross-session
measurement, missing originals and expired measurement records. No actual physical
measurement or review was created.

Next: resolve the measurement receipt and original files from the service's
successful operations, expose draft generation without caller-supplied hashes,
then perform explicit key setup/physical measurement and live qualification when
the required operator evidence is available. Original campaign goal remains open.

## Previous checkpoint: visible unconfigured-run prerequisites

The unconfigured commissioning run form now shows a concise prerequisite sequence:
check/explicitly provision the private review key, record actual independent
measurements with uncertainty, retain five engineering decisions, attach exact
same-session evidence through trusted host integration, then inspect the displayed
move and confirm current physical conditions. It distinguishes missing key storage
from a USB/arm fault and explicitly says a photo cannot manufacture measurements.

This guidance does not pretend that host attachment is already a browser workflow:
automatic draft/original assembly remains a developer integration responsibility.
The blocked form makes that dependency visible instead of showing only an empty
selection-hash input. It does not preselect approvals or issue any action.

9 renderer/run-lifecycle tests passed:
`software/runs/first-motion-guidance-20260913-01.xml`. The shipped renderer's
unconfigured state includes the prerequisite sequence, lacks a claimed selection
and performs GET-only modeled requests. No real key setup or hardware activity
occurred. Physical qualification and the original characterization goal remain
incomplete.

## Previous checkpoint: actual host key prerequisite missing; early diagnostic added

A read-only call to the actual host first-motion authority loader found that the
private bench review key is not configured. No protected key was created,
replaced, printed or exported; no device was accessed. Consequently actual DPAPI
load latency and authenticated native startup cannot yet be qualified on this host.
The earlier timing runs deliberately used synthetic test keys.

`configure_first_motion` now performs a read-only protected-key readiness check
before accepting its attachment. Missing, corrupt or unavailable key storage
produces `FIRST_MOTION_REVIEW_KEY_REQUIRED` and directs the operator to the existing
Set up private bench review key action (CHECK or explicit PROVISION). It does not
silently provision storage or wait until a final click consumes the attempted run.
The authority object is not retained on the service; execution still reloads it.

12 attachment/run-lifecycle tests passed:
`software/runs/first-motion-key-preflight-20260913-01.xml`.
Attachment tests now explicitly supply a synthetic authority and cover missing-key
refusal without installing an attachment or consuming a motion attempt. No actual
key provisioning or hardware operation occurred during these tests.

Required before live qualification: explicit private-key setup, current independent
wrist interval/distal-radius measurements and reviewed clearance/observation evidence.
Browser interaction QA and actual native startup timing also remain pending. The
original approved pose/speed campaign and evidence-backed settings report are not
complete; missing local key setup must not be mistaken for an arm/USB fault.

## Previous checkpoint: actual browser startup inspection (partial QA)

Started a fresh unbound physical-mode wizard through the real CLI with cell label
`UI-QA-NO-HARDWARE`, default workspace export folder and a free loopback port.
Opened its local authenticated launch URL in the in-app browser; no launch
credentials are recorded here. Browser accessibility state confirmed:

- Local service connected and the expected cell/session identity.
- Camera and arm both NOT CONNECTED; received-unit verification not claimed.
- Physical activation independently gated and all physical stages pending.
- Explicit preview-before-execution guidance and diagnostic-only authority state.

No action was previewed or executed, no approval checkbox was selected, and no
hardware access was requested. The QA server was stopped using its owned process
session after inspection (terminal completion observed). The browser tab may now
show that disconnected QA session; it is not a live arm-control connection.

This is only real-browser startup/accessibility evidence, NOT complete screenshot
or form-interaction QA. Browser control initialization returned page state but no
documented click/screenshot API; interaction was not attempted through guessed
methods. Automated shipped-renderer coverage remains the evidence for the full
selected-command form. Complete browser interaction and native startup/physical
qualification remain outstanding, as does the original pose/speed campaign.

## Previous checkpoint: mutation coverage and broad commissioning regression

Prelaunch tests now inject changed source references, signed-review bytes,
launch bytes and backwards time immediately AFTER the actual measurement loader
returns. Final reconstruction/record verification rejects each mutation before
any worker claim. These tests use synthetic source observations and real local
measurement/review/launch files, not physical observations.

The initial four added cases patched the helper's defining module instead of
prelaunch's imported reference, so the mutation never occurred. The corrected
hook explicitly checks that mutation happened. All 11 prelaunch cases then passed
in `software/runs/first-motion-drift-20260913-02.xml`.

Broad regression rerun: **441 passed in 70.87 seconds**,
`software/runs/first-motion-full-20260913-03.xml`. This covers all first-motion unit
modules except the separately run variable-load timing benchmark, plus coordinator
and diagnostic-runtime tests. The earlier 437-pass/four-test-hook-failure run is
retained in `first-motion-full-20260913-02.xml`. No production checks were weakened
to resolve those test-hook failures and no hardware was accessed.

Remaining qualification is unchanged: browser visual/interaction QA, real
protected-key/process startup verification, independently measured geometry and
observed slow live response, then the original approved pose/speed campaign and
evidence-backed settings report. A green software suite is not physical readiness.

## Previous checkpoint: real parent prelaunch exercised with incapable backend

The advancing-clock real-file benchmark now optionally uses the real owned
supervisor, registration validation and both authenticated prelaunch checks, but
substitutes an incapable backend whose start method validates its callback and
then stops without process creation. Original reviews/measurements and keys are
explicitly synthetic; native binding and port APIs cannot be reached.

The first broader run exposed `LIFETIME_BUDGET_DOES_NOT_FIT`. Parent prelaunch was
reconstructing all references inside each measurement-loader context callback,
in addition to reconstruction before and after that bounded read. Those inner
callbacks now enforce the request deadline; full source/build/original validation
still brackets the entire measurement/key-read operation and precedes authority
verification. Launch and signed-review files are still reread and compared.

10 prelaunch/timing tests passed (3 constructor-only variants deselected):
`software/runs/first-motion-prelaunch-timing-20260913-04.xml`.
The broader samples took 3048.5735, 3474.6407 and 3563.4809 ms including the
intentional backend failure and result retention. All reached the backend's
post-prelaunch stop with no process created/resumed and no worker claim. These
totals include the second prelaunch inside the run window, not just the initial
three-second preparation allowance. They are not native hardware latency.

Earlier test attempts also exposed a test-only clock-origin mismatch in cleanup;
the advancing synthetic clock now covers both injected and module cleanup clocks,
without clearing or bypassing the actual cleanup hold. Previous reports retain
those failures. No physical commands or actual operator confirmations occurred.

Next: current-source mutation coverage around the optimized prelaunch read,
browser visual QA, and real protected-key/native startup latency verification
before independent slow-move qualification and the original pose/speed campaign.

## Previous checkpoint: separate repeated ownership checks from source scans

The run-operation callback previously called `_recheck_source` at every receipt,
measurement and context checkpoint. Twenty actual read-only `_recheck_source`
calls against this workspace took 4.596 seconds, already exceeding the three-
second preparation allowance before other work. This was redundant with the
separate source reconstruction performed by staging/snapshot/native admission.

The wizard now performs a full source recheck at commissioning operation entry
and uses in-memory ownership, source-invalidated, closed/log, attachment,
confirmation and powered-context checks for the repeatedly invoked callback.
Full current source/build/original validation remains at staging before/after
publication, snapshot construction and native prelaunch. No fingerprint is cached
as an admission substitute. A source change during review work is still rejected
by later actual file reconstruction before hardware dispatch.

23 lifecycle/staging/prelaunch tests passed:
`software/runs/first-motion-context-20260913-01.xml`. The new lifecycle test invokes
the actual captured callback twenty times, confirms it does not rescan source,
then marks the source invalid and confirms rejection. Other tests retain current
source-drift and authenticated prelaunch coverage. These are synthetic/inert tests;
no hardware was accessed. Complete live dispatch timing remains unqualified.

Next: measure full real-file parent prelaunch with incapable native backend,
complete browser QA, then collect physical measurements/reviews for the slow
qualification move. The original pose/speed characterization goal is incomplete.

## Previous checkpoint: staging boundary ordering reduces redundant scans

Staging now performs in-memory input checks and current-context checks first,
then a fresh source/build scan immediately before publication. After publication
it checks external context BEFORE reconstructing all current source/build/original
references, followed by the deadline check. This removes redundant scans during
the no-write validation phase and immediately after a complete reconstruction.
No source digest is cached and worker preparation/admission checks are unchanged.

10 staging/pipeline timing tests passed in
`software/runs/staging-timing-20260913-01.xml`; the three real-file pre-dispatch
samples took 2110.6815, 2132.5167 and 2071.7727 ms. As before, dispatch is replaced
by an incapable supervisor and keys/evidence are synthetic. These measurements
do not include actual wizard callbacks, protected-key load or native prelaunch.

16 staging/reference-reader regression tests passed in
`software/runs/staging-drift-20260913-01.xml`. New tests inject changed source at
the pre-publication and post-publication context boundaries: both fail; the early
failure writes nothing and the late failure retains the consumed attempt/files.
No hardware commands were sent. Full live timing and physical qualification remain
incomplete; next measure actual wizard callback costs and complete prelaunch.

## Previous checkpoint: fresh source metadata read optimization

Source path validation now returns the leaf metadata obtained during its existing
fresh lstat/ancestor walk. Fingerprinting reuses that metadata within the same call
instead of issuing additional following stat/is-file/is-directory calls. There is
no cross-call metadata or content cache: every ancestor is still checked for
links/reparse points and every source file is reread and hashed. Digest ordering
and read-length/growth budgets remain unchanged.

65 metadata, diagnostic-runtime and pipeline timing tests passed:
`software/runs/source-timing-20260913-04.xml`. The three blocked-dispatch timing
samples were 2844.5485, 2823.6272 and 2753.2197 ms. All reached the intentionally
incapable supervisor boundary within the three-second allowance, but headroom is
small and these timings still exclude actual protected-key loading, wizard source
callbacks and native prelaunch. Full live timing is NOT qualified.

Tests check unchanged digest ordering, detection of same-length edits without
cached content, regular-file/directory checks, concurrent growth and existing
diagnostic runtime behavior. The growth test's metadata double was updated to
retain Windows attributes while overriding size; the initial test-only failures
are retained in earlier reports. No physical commands were sent.

Next: remove redundant work across adjacent preparation stages through reviewed
preparation ordering, preserving independently fresh checks at real admission.
Measure the complete wizard/prelaunch path before live qualification; do not
interpret this narrow performance improvement as readiness for a movement sweep.

## Previous checkpoint: real-file timing exposes preparation overrun

Added `test_first_motion_pipeline_timing.py`: real review recording/selection,
final confirmation, measurement loading, staging, snapshot/archive and registration
preparation, using synthetic evidence/test keys and a real elapsed clock. The
supervisor constructor is replaced by an incapable stop, so no native worker,
controller claim or serial activity can occur. A fixed synthetic clock origin is
used only to align the synthetic records; elapsed time advances normally.

The three samples in `software/runs/first-motion-timing-20260913-01.xml` took
2380.6831, 2991.3252 and 3015.5798 ms. Two reached the deliberately blocked
dispatch boundary; the third correctly failed preparation after exhausting its
three-second allowance. **This timing qualification is failing, not complete.**
Do not infer readiness from earlier constant-clock tests or extend review/request
lifetimes to make it pass. This benchmark also excludes real key loading, wizard
current-context callbacks and native supervisor prelaunch, so passing it alone
would still not qualify total live latency.

Profile retained at `software/runs/first-motion-timing-profile-20260913.prof`.
Under profiling the preparation overran again (~3134.6 ms). Seven source fingerprint
calls (including fixture setup) accumulated 2.440 s; staging accumulated 1.569 s,
snapshot preparation 0.953 s and two archive reconstructions 0.469 s. These timings
are diagnostic and profiler-affected, not hardware performance settings.

Next: optimize redundant filesystem traversal/reconstruction while preserving
fresh source/content checks and final pinned-byte validation, or move immutable
preparation before final click with a fresh validation at dispatch. Keep stale
evidence, changed source, cancellation and one-use failures closed. Re-run timing
with real wizard callbacks and complete prelaunch after optimization, before any
live qualification. No hardware commands were sent in these tests.

## Previous checkpoint: failure recovery in general wizard exports

General wizard export now reserves `first-motion-native-logs.json` before ordinary
result rotation whenever the service retains an owned commissioning process
outcome. This closes a gap where failed native result publication left original
streams only in memory. The attachment includes bounded base64 stdout/stderr
chunks and parent process metadata/hashes, excludes parsed child claims, preserves
the failure stage, and explicitly denies physical qualification and replay.

9 export/lifecycle tests passed:
`software/runs/first-motion-export-20260913-01.xml`.
Export recovery tests use synthetic owned results with publication failure and
zero, 1,000 and maximum 262,144 stdout bytes, plus binary stderr. They verify the
produced export manifest and decode exported chunks to exact original bytes and
hashes. No motion rerun is needed; the in-memory result remains unchanged. No
hardware was accessed. General export remains bounded and may explicitly fail if
combined dedicated attachments exceed its existing budgets; it must not truncate
these original streams and claim complete recovery.

Next: browser visual/interaction QA and complete real-file pre-run timing, then
physical measurement/review and actual slow-move qualification. The full original
pose/speed characterization goal remains incomplete.

## Previous checkpoint: visible commissioning selection and stale-ticket checks

The shipped renderer now displays `commissioning_preview` on the run form.
Previously the service supplied this data but the form rendered only the endpoint
draft special case. The commissioning form now shows the selected command,
identity, reference hashes, geometry interval/radius and limits as text, plus
plain-language absolute-versus-increment semantics, speed/acceleration settings,
startup movement risk and cancellation limitations. Original data is not HTML.

51 lifecycle/form-draft tests passed in
`software/runs/first-motion-preview-20260913-01.xml`. New service cases reject
powered-setup, selected-draft and state-epoch changes after preview before an
attempt is accepted or dispatched. One additional shipped-renderer modeled-DOM
test passed in `software/runs/first-motion-render-20260913-01.xml`, checking visible
command semantics, digest, measurement fields and GET-only behavior.

These are automated renderer/lifecycle checks, not browser screenshot QA or real
hardware tests. Browser interaction/visual QA, diagnostic export failure handling,
full pre-run timing and independent live qualification still remain. No operator
confirmation or hardware command was submitted during this work.

## Previous checkpoint: ticketed commissioning run action

The physical wizard now registers `run_first_motion`. It requires the attached
selection digest, operator identity and seven explicit checks, and exposes the
attached preview in its action data. No attachment or an already-attempted
attachment blocks it. Preview and execution bind the existing powered-setup
context and normal source/state-epoch ticket checks remain in place.

Acceptance reserves the in-memory attachment and logs the host final-click time
before queueing. The coordinator carries that accepted time into request creation;
queue delay cannot renew the 30-second request window. Invalid, future or excessively
old accepted times fail. The run operation delegates to the distinct commissioning
coordinator, checks current ownership/context, and retains the service-owned
outcome including original owned-process data when publication fails. A retained
IPC result is not claimed as independent physical response qualification.

87 run-lifecycle/confirmation/coordinator/action tests passed:
`software/runs/first-motion-run-20260913-01.xml`.
26 additional accepted-time and endpoint-intake regression tests passed:
`software/runs/first-motion-run-regression-20260913-01.xml`.
Run-lifecycle tests substitute an incapable coordinator and attach synthetic host
state. They prove dispatch association, blocked unattached/repeated attempts and
retained failure outcomes, not real native admission or device motion. No hardware
was accessed and no actual operator confirmation was submitted.

Next: browser rendering/interaction QA (including visibility of full selected
command), stale-ticket/cancellation/export failure integration and full real-file
pre-run timing. Resolve any timing gaps without extending old approvals. Physical
measurements, independent observation, slow live qualification and the original
finite approved pose/speed characterization are still outstanding.

## Previous checkpoint: trusted wizard commissioning attachment

`ArrivalWizardService.configure_first_motion` now attaches an exact draft, copies
all eight original byte values, resolves the successful same-session measurement
and five engineering-review receipts, and retains the configuration event before
installing it. Hash/structure mismatch, missing measurement and invalid review
selection fail without attachment. An existing commissioning or endpoint binding
cannot be replaced or installed alongside a conflicting configuration.

Measurement validation uses a temporary request envelope only to reuse strict
original/session/geometry validation; this envelope is never sealed or dispatched.
Final execution must still issue its own request and revalidate every original,
source/build, current controller association and review lifetime. Attachment is
not command compatibility proof, clearance approval or native admission.

15 attachment/endpoint-selection tests passed:
`software/runs/first-motion-attachment-20260913-01.xml`.
The tests create synthetic measurement/review operations, verify exact association,
copy isolation, failed attachment and replacement refusal with zero runner calls.
No hardware was accessed. The public run action and browser visual QA are still
pending; attachment alone does not enable motion.

Next: use this immutable selected material in the wizard's ticketed final-click
and operation lifecycle, invalidate stale tickets, retain outcomes/exports and
verify the complete pre-run timing before any actual slow-move qualification.

## Previous checkpoint: final-click to supervised coordinator composition

`wizard_first_motion_coordinator.run_confirmed_first_motion` now composes trusted
receipt selection, existing protected-key loading, final-click request/sealing,
original measurement loading, exact evidence staging and the existing supervised
run/publication coordinator. It checks cancellation/current context between stages
and validates assigned roots before consuming a click. It does not provision a
key, renew an original, widen a command or retry an attempt. The returned execution
outcome is preserved unchanged, including owned result bytes on retention failure.

36 coordinator/confirmation/staging/preparation tests passed:
`software/runs/first-motion-pipeline-20260913-01.xml`.
New orchestration cases use incapable doubles to prove ordering and short-circuit
behavior at review, confirmation, measurement, staging and cancellation failures.
Existing component tests cover real local publication and package preparation.
This is not yet a full admitted live integration test or proof the full preparation
fits the three-second pre-run allowance on this host. No hardware was accessed.

Next: the wizard service must own the configured draft, receipt/hash selections,
reference originals and final-click operation identity; expose run only through
that guarded lifecycle, then verify UI/export behavior and end-to-end timing.
Independent physical measurements and actual slow-move qualification still precede
the original finite pose/speed campaign. The overall goal remains incomplete.

## Previous checkpoint: selection-bound final-click construction

`first_motion_confirmation.confirm_draft` now maps explicit operator checks for
the displayed immutable selection to one new host-timed request. Browser values
cannot supply command fields, timestamps or a replacement request hash. Every
material selection field remains identical; only the host attempt identity and
30-second envelope are new. A retained final-click original binds the submitted
selection/checks and generated request before authenticated review publication.

The final-click filename is exclusive. If sealing fails, its retained record
prevents automatic retry with the same attempt. Neither original measurements
nor engineering-review times are renewed. The helper does not open hardware or
dispatch a worker, and does not independently verify an operator's declarations.

22 final-click/confirmation/draft tests passed:
`software/runs/first-motion-click-20260913-01.xml`.
Synthetic tests cover material preservation, host-generated timing, changed
selection, non-boolean acknowledgment, injected timestamp, failed sealing with
retained click and duplicate publication refusal. No physical action occurred.

Next: wire the trusted draft/evidence/receipt attachment and final click into the
wizard run operation, retaining cancellation and failed-supervisor results. The
helper is not yet a public launch action. Browser visual QA and actual independent
physical qualification remain required before the finite pose/speed campaign.

## Previous checkpoint: exact-request operator confirmation and sealing

`application/first_motion_confirmation.py` creates the seven operator original
records only from explicit true checks, a bounded operator identity and the exact
request digest. Host-owned time is recorded within the request window. It combines
these with the five unchanged engineering originals, authenticates the complete
bundle using the existing protected-authority type and exclusively publishes the
fixed attempt-specific review filename consumed by worker preparation.

The helper rejects changed context, backwards time and less than 27 seconds of
remaining worker/preparation budget; it never extends the request. A late failure
after publication retains the bundle and prevents overwriting/replaying that
publication. Authentication establishes record integrity, not physical truth or
a native motion permit. No authority keys are provisioned by this helper.

34 confirmation/authentication/draft tests passed:
`software/runs/first-motion-confirmation-20260913-01.xml`.
Tests use a synthetic key and synthetic reviews, cover exact original preservation,
unchecked operator input, wrong request digest, malformed engineering evidence,
insufficient time, context failure and retained publication after late failure.
No hardware, actual operator attestation or physical qualification was performed.

Next: connect draft-bound final click to trusted request construction and these
operator originals inside the wizard operation lifecycle. Do not make the user
manually review a newly generated hash within the short execution window: the
host must map the confirmed immutable selection to that exact timed request.
Then stage/seal/prepare once and retain the supervised outcome through UI exports.
Physical qualification and the original finite pose/speed campaign remain pending.

## Previous checkpoint: exact same-session engineering review selection

The trusted wizard method `select_first_motion_reviews` resolves five distinct
successful commissioning review operations from its own session. It obtains
expected hashes from retained results rather than accepting caller-provided
approval digests. `first_motion_review_intake.load_selected_reviews` rereads the
original draft and decision files, reconstructs the exact review using its OLD
timestamp, requires all five different approved checks, and checks current source,
context and expiry. It returns unchanged original bytes, not a signed bundle or
motion permit. No automatic latest-file selection or evidence renewal occurs.

32 intake/selection/authentication tests passed:
`software/runs/first-motion-selection-20260913-01.xml`.
Coverage includes successful same-session resolution and rejection of cross-session
operations, repeated operation IDs, duplicate checks, denied/expired decisions,
changed hashes and changed context. All reviews are synthetic; no hardware access
or physical qualification occurred.

Next: final confirmation must combine these originals with newly recorded exact-
request operator attestations, authenticate the bundle, then use the existing
bounded supervisor and export coordinator. Selection alone cannot enable motion.
Browser visual QA, independent geometry measurements and the actual approved
slow-move/pose-speed characterization remain outstanding.

## Previous checkpoint: wizard engineering-decision intake

The physical wizard now exposes `record_first_motion_engineering_review` as a
parent-only, non-hardware action. It accepts an exact commissioning draft, one of
the five engineering checks, self-reported reviewer identity, explicit decision
and rationale. UNKNOWN is the default; UNKNOWN and DENIED remain retained rather
than becoming approvals. The operation publishes the original draft and review
under exclusive operation-specific filenames and records their selection/digest
association. Source mismatch and malformed inputs fail before publication.

`application/first_motion_review_intake.py` emits the existing first-motion review
schema with the original host recording time and a bounded five-minute lifetime.
Recording is not review authentication, proof of reviewer identity or motion
permission. Selecting successful records, authenticating the complete bundle,
operator final-confirmation and native dispatch are still separate pending wiring.

Verification: 25 intake/authentication tests passed in
`software/runs/first-motion-intake-20260913-01.xml`; 78 commissioning intake,
endpoint intake and action-registry regression tests passed in
`software/runs/first-motion-intake-regression-20260913-02.xml`.
The first registry run correctly flagged the new action missing from its explicit
expected set; the set was updated and the tests rerun. Service tests retained all
three decisions with zero device opens and zero motion commands. Browser visual
QA remains outstanding; no real physical review was recorded or hardware accessed.

Next: resolve five successful same-session engineering receipts by original hash,
reject missing/duplicate/expired/denied selections, and bind them to final click.
The original full movement-characterization goal remains incomplete.

## Previous checkpoint: untimed review selection and final-request binding

`application/first_motion_draft.py` adds an immutable, untimed commissioning
selection. It shares the strict first-motion request validation and the exact
selection digest already used by engineering review authentication. Only attempt
identity and execution times are excluded; command, identity, reference hashes,
geometry, limits and unknown-freshness status remain bound. Finalization checks
the reviewed selection digest before constructing the timed request.

This avoids spending the short execution window while a human reads the proposed
test. It does not renew original measurements or approvals, reserve an attempt,
open a port, or issue a motion permit. The trusted host must still supply actual
final-click times and retain new exact-request operator attestations. Existing
durable launch claims remain responsible for preventing physical replay.

45 draft/authentication/measurement-binding tests passed:
`software/runs/first-motion-draft-20260913-01.xml`.
Tests prove material-field preservation, mutation rejection, changed-selection
digest rejection, and refusal to seal a new timed request with old operator
attestations. Synthetic new operator records can be combined with unchanged,
still-valid engineering originals. No actual reviews or hardware operations were
performed. The draft is not yet connected to a public wizard action.

Next: trusted intake of the wizard's successful engineering review operations,
then final-confirmation/operator-original creation and coordinator UI wiring.
Independent geometry and physical qualification remain outstanding; the full
movement-characterization objective is unchanged and incomplete.

## Previous checkpoint: immutable evidence staging and regression verification

`application/first_motion_staging.py` now reserves the exact commissioning
request and retains all eight original reference documents without replacing
the selected measurement, its uncertainty bounds or its timestamp. It checks
source/build identity, original hashes and current host context before publication
and again afterward. A partial write or late context failure leaves the attempt
reserved and its artifacts intact; it cannot be retried under the same identity.

The wizard service's trusted `stage_first_motion_evidence` method selects only
this session's successful measurement receipt and records the staging outcome.
Logging failure is surfaced rather than reported as successful staging. This is
internal host wiring, not a browser route, authenticated review, or motion permit.

Verification completed without arm/camera access:

- 311 commissioning regression tests passed in 67.06 seconds:
  `software/runs/first-motion-regression-20260913-01.xml`.
- After adding two service integration cases, 25 measurement/staging tests passed:
  `software/runs/first-motion-service-staging-20260913-01.xml`.
  These service cases exercise actual retained receipt selection with an incapable
  staging double; the staging tests separately exercise real file publication.
- Publication interruption and late context changes preserve originals and refuse
  replay. No test constitutes physical movement or independent pose verification.

Remaining implementation order:

1. Connect successful wizard review operations to authenticated engineering and
   operator review originals; never infer approvals from staging or telemetry.
2. Build the reviewed selection/final-click binding, issuing the short-lived exact
   request only at final confirmation without renewing old measurements.
3. Attach the supervised coordinator to the wizard's bounded operation lifecycle,
   cancellation, retained failure results and assigned-folder export status.
4. Test the browser workflow and independent physical observation intake before
   qualifying one slow live move; then return to the approved pose/speed campaign.

Actual independent wrist-angle/radius measurements and physical review remain
outstanding. The full movement-characterization goal is not complete.

## Previous checkpoint: trusted wizard-parent run coordinator

`application/wizard_first_motion_coordinator.py` now composes exact reviewed
request preparation, supervisor dispatch and diagnostic publication. It binds the
measurement operation, verifies parent dispatch inputs/current-session checks,
never renews the final request and never retries. Cancellation after dispatch
does not skip retention. On publication failure, the outcome retains the owned
process result so logs can be recovered without rerunning physical motion.

11 coordinator/preparation tests passed:
`software/runs/first-motion-coordinator-20260913-01.xml`.
Coordinator tests use incapable doubles to verify ordering, authorization failure,
single-run behavior, post-dispatch cancellation and retained data after export
failure. No real hardware was accessed. The coordinator is a trusted internal
function, not yet attached to the public wizard service or a browser action.

Next: actual wizard service staging/selection and authenticated review/final-click
integration, UI launch/export status and independent observation review, followed
by the required physical qualification and approved pose/speed campaign.

## Previous checkpoint: coordinator worker preparation

`application/first_motion_worker_preparation.py` validates the existing signed
review bundle and exact selected measurement, restores the reviewed controller,
builds the immutable evidence snapshot/archive, pins interpreter/entry/archive/
evidence, constructs fixed registration and reserves the launch. Preparation
requires 27 seconds remaining and never extends the request deadline. It does
not create approvals, provision keys, claim a worker, open hardware or launch.
Supporting originals and signed reviews must already have been staged by the
trusted coordinator; staging and sealing are not silently performed here.

8 commissioning and endpoint worker-preparation tests passed:
`software/runs/first-motion-preparation-20260913-02.xml`.
Tests exercise actual package/snapshot/launch publication with synthetic original
measurements and reviews. An integration case traverses real parent prelaunch
authentication using a test key and current workspace reconstruction, reaching
only an incapable fake backend. Its deliberate child failure is retained with
confirmed fake cleanup. No actual native process or hardware was accessed.

Next: wizard coordinator staging/selection and review integration, final request
confirmation and launch/export wiring, independent observation intake/review,
then the actual slow live qualification and approved pose/speed campaign.

## Previous checkpoint: supervised handoff tests and explicit child entry

Supervisor orchestration now has tests through an incapable fake process backend:
both prelaunch checkpoints run, a second-check failure prevents resume, successful
IPC is associated with an actual synthetic durable claim, a mismatched owned PID
is rejected, cleanup runs and the worker cannot rerun. Prelaunch authentication
is separately tested; these orchestration tests stub that check. The successful
IPC case reports cancellation before device open, not successful movement.

The isolated child now accepts exactly `check-imports` and `execute-one`. The
latter decodes a bounded request and invokes the existing reviewed/reserved child
composition, encoding a bounded result or a non-authorizing error. Empty input
is tested in a real isolated subprocess and fails before claiming or opening.
Import checks still prohibit native/device/network/process access. Unknown modes
remain rejected; there is no unrestricted command mode.

14 child-entry/composition/parent-orchestration tests passed:
`software/runs/first-motion-entry-20260913-01.xml`.
Earlier orchestration tests passed 4 cases in
`software/runs/first-motion-parent-20260913-01.xml`.
No actual arm or camera access occurred. Real admitted hardware execution has
not been qualified, and the wizard still lacks the complete preparation/launch
and independent-observation workflow.

Next: wizard worker preparation/staging and registration construction, review
and final-confirmation integration, durable exports and independent observation
review, then the required slow live qualification and approved campaign.

## Previous checkpoint: commissioning supervisor branch

`OwnedWindowsWorker` now has a commissioning branch that validates fixed
registration, enforces the exact deadline, verifies reserved-entry evidence
before dispatch and again at the execution boundary, and verifies returned
result/claim association against the parent's actual process ID. Existing
authorizer, pinning, cancellation, finite process budgets and cleanup remain
in the shared supervisor path.

28 registration/package/endpoint-registration tests passed in
`software/runs/first-motion-supervisor-20260913-01.xml`; a further 10 targeted
commissioning-registration and endpoint-parent-activation tests passed in
`software/runs/first-motion-supervisor-20260913-02.xml`.
The targeted test proves prelaunch refusal occurs before authorizer/backend
creation. This is denial-path evidence, not proof of successful admitted physical
worker execution. No hardware was accessed.

The isolated commissioning child CLI remains check-only, so this branch is not
yet an operational live path. Next verify a fully admitted synthetic supervisor
handoff, finish deliberate child activation, and integrate wizard preparation,
review and independent observation before physical qualification.

## Previous checkpoint: parent result/claim association and publication

`providers/windows/first_motion_result_publication.py` retains immutable raw
request/stdout/stderr streams before interpretation, validates the result codec,
and checks the durable child claim against the parent's owned process ID, original
launch/runtime and completion time. The report separates `claim_receipt_verified`
from process completion and leaves physical qualification/campaign advancement
false. A PID mismatch or malformed output is retained but rejected; nonzero exit
or unconfirmed process completion cannot yield `RESULT_RETAINED`.

18 commissioning and endpoint publication tests passed:
`software/runs/first-motion-publication-20260913-01.xml`.
Tests cover the publication/claim-association layer with synthetic child data,
actual synthetic launch/claim files, wrong PID, exit/completion failure, malformed
bytes and overwrite refusal. Synthetic review bytes here test receipt integrity,
not review authentication, which is a separate prelaunch/admission requirement.

A typed supervisor-result adapter is implemented but not yet exercised through a
real admitted commissioning worker. Parent launch integration and wizard review/
observation remain unfinished. No physical worker or hardware was accessed.

## Previous checkpoint: child result IPC coding and consistency checks

`providers/windows/first_motion_native_result.py` provides bounded result encoding/
decoding with exact outer request/attempt/schema association, separate child claim
identity, execution/lifecycle request association and read/write/handle budgets.
Completed forms must have closed resources and a full trial review recomputed from
original captures. Lifecycle read/write counts must agree with the trial records.
Failed forms remain `FAILURE_DIAGNOSTIC_ONLY`, not validated completed trials.

No codec result verifies parent process ownership or physical movement. The claim
digest still requires verification against the actual parent's owned process and
durable launch/claim originals. Diagnostic retention remains separate so malformed
output is not lost when decoding fails. The codec is in the isolated bundle.

29 codec/package/completed-review tests passed:
`software/runs/first-motion-result-codec-20260913-01.xml`.
Synthetic runner bytes were explicitly production-labelled within protocol tests
only to exercise that branch; they are not retained physical evidence. No hardware
was accessed and no physical worker was launched.

Next: parent-owned receipt association and publication, supervised launch wiring,
then wizard integration/independent observation and physical qualification.

## Previous checkpoint: parent reserved-entry verification

`providers/windows/first_motion_prelaunch.py` reconstructs current references,
verifies the one-use launch/runtime/review association, reloads the exact selected
measurement original, obtains the existing host review authority and re-verifies
signed originals without renewing their timestamps. It rechecks references,
launch/review bytes and remaining request budget after the intermediate work.
This function is parent-only and must follow fixed registration validation.

32 prelaunch/claim/measurement-binding tests passed:
`software/runs/first-motion-prelaunch-20260913-02.xml`.
Tests use actual synthetic signed bundles, measurement and launch files with
synthetic reference/key providers. Changed evidence, wrong key/runtime/selection
and expiry are refused; no claim or device reservation is issued. The initial run
exposed a callback-contract mismatch (the measurement checker requires a void
success return), corrected with an explicit reference-comparison callback.

This is not yet connected to physical process creation. Child IPC result coding,
parent-owned receipt association and supervised wizard launch integration remain
required, followed by independent physical observation and qualification.
No hardware was accessed by this checkpoint.

## Previous checkpoint: production child composition function

`providers/windows/first_motion_child_execution.py` composes handoff decoding,
current reference reconstruction, registered frozen snapshot verification,
controller-original reconstruction, host review authority, one-use process claim,
current metadata/context, selected measurement and authenticated review checking,
then commissioning admission and native execution. An admitted permit is revoked
in `finally`, including executor failure. No synthetic fallback is implemented.

The function is included in the isolated bundle, but the CLI remains check-only
and the parent worker still has no physical commissioning launch branch.
Production wiring is implemented at the child-function level, not yet end-to-end
through a supervised, admitted wizard launch.

10 child-composition and isolated-package tests passed:
`software/runs/first-motion-child-20260913-01.xml`.
Tests verify early cancellation, actual source mismatch refusal before key/claim/
metadata access, mocked dependency ordering and permit revocation on failure.
Ordering tests do not prove live metadata, key loading or physical operation.
No hardware was accessed.

Next: parent prelaunch authenticated review/reservation verification, child IPC
result encoding and parent-owned receipt association, then deliberate supervised
launch integration and wizard observation/review. Physical qualification and the
pose/speed campaign remain incomplete.

## Previous checkpoint: fixed commissioning registration validation

`providers/windows/first_motion_native_registration.py` validates the exact
interpreter digest, child/archive/evidence pins, isolated arguments, assigned
attempt directory, fixed process budget, request identity/deadline and retained
registration document. Evidence bytes are decoded against the exact request.
Changed arguments, budgets, directories, missing pins and modified evidence fail.

The generic `OwnedWorkerRequest` now recognizes the separate commissioning
handoff data format. This is not a physical execution registration: no commissioning
launch branch has been added. A test submits valid registration data to the actual
worker API and verifies it refuses before authorizer/backend/process creation.
The child itself also remains check-only.

28 commissioning registration/package and endpoint-registration tests passed:
`software/runs/first-motion-registration-20260913-02.xml`.
The first run found the missing generic request-data branch; adding only strict
payload parsing resolved it without enabling launch. No hardware was accessed.

Next: production child evidence composition, parent prelaunch review/reservation
verification, owned-process result association and wizard integration. Live
qualification and the complete approved pose/speed campaign remain outstanding.

## Previous checkpoint: frozen commissioning evidence snapshot

`application/first_motion_evidence_snapshot.py` verifies current source/build and
the eight retained originals, publishes an immutable request-bound snapshot, and
provides `FrozenFirstMotionReferences` for exact pinned execution bytes. It checks
each original's digest and bounds and rechecks current references during assembly.
The snapshot is added to the deterministic child bundle's import roster.

This supplies the third pin required by the existing registration design:
interpreter/entry/archive validation alone is insufficient without the exact
reviewed evidence snapshot. Frozen references are not a current-workspace or
physical-state assertion. Parent pinning and fresh USB metadata, measurement
association and review-expiry checks must remain separate launch/dispatch checks.

20 snapshot, isolated-package and endpoint-snapshot tests passed:
`software/runs/first-motion-snapshot-20260913-01.xml`.
Tests reconstructed the actual workspace build/source with explicitly synthetic
supporting originals, rejected changed snapshots and verified no overwrite.
No hardware was accessed and no physical evidence was approved.

Fixed parent registration is still next; it must pin this snapshot in addition
to the child and archive. Production child composition, receipt association,
wizard integration and actual physical qualification remain incomplete.

## Previous checkpoint: separate parent/child IPC contract

`providers/windows/first_motion_native_protocol.py` defines the commissioning
handoff and request envelope, separate worker/schema/authority identifiers,
selected measurement operation/session, exact request and registration hashes,
USB identity hash and matching request/parent deadlines. Inputs are bounded to
64 KiB, with a 32 KiB registration ceiling and no extra fields. The fixed process
budget is 25 seconds plus 2 seconds cleanup; requests must reserve at least
27 seconds. Parsing does not authenticate registration or grant launch authority.

The module is included in the explicit deterministic bundle and imported by the
isolated check-only child. 33 protocol/package and existing endpoint-wire tests
passed: `software/runs/first-motion-protocol-20260913-02.xml`.
Rehashing an envelope cannot excuse changed request/identity/deadline associations;
malformed handoffs and endpoint/commissioning domain substitution are refused.
No physical worker was launched and no hardware was accessed.

Still required: actual fixed parent registration validation, production evidence
staging/child composition, authenticated owned-process result association and
wizard launch/observation integration. The child remains check-only until those
are implemented and verified; physical qualification is not complete.

## Previous checkpoint: deterministic isolated commissioning bundle

`providers/windows/first_motion_native_package.py` builds a deterministic archive
from the existing closed endpoint dependency roster plus explicit commissioning
modules. No recursive source-tree glob or wizard server is included. The separate
`_first_motion_native_child.py` entry validates isolated/no-site execution and the
archive digest before importing commissioning components.

Its sole current mode is `check-imports`, which prohibits native DLL loading,
subprocess creation, sockets and `os.open` during imports. Construction of the
inert native facade reports no loaded native API. Live and unknown entry modes,
including `execute-one`, are explicitly rejected pending production registration
and child evidence composition. This is not yet a runnable physical worker.

14 commissioning and endpoint packaging tests passed, including real isolated
Python subprocess import checks:
`software/runs/first-motion-package-20260913-01.xml`.
No arm or camera was accessed. The import-check child processes are test processes,
not admitted physical trial workers.

Next: fixed parent registration and IPC schema, staged evidence/child composition,
owned-process result association and wizard integration. Physical qualification
and the full approved pose/speed campaign remain required for goal completion.

## Previous checkpoint: completed trial data review

`application/first_motion_result_review.py` validates bounded completed-trial JSON,
checks exact request/basis association, full write byte count and timing, validates
both original captures and recomputes the entire telemetry analysis. Child-supplied
analysis and status must match the recomputation. Cleanup now retains start/finish
timestamps; the reviewer checks handle/pending-I/O fields, order and time budget.

This is a consistency review, not process authentication or physical qualification.
Even unchanged feedback can be consistently reported as insufficient telemetry.
Failed/uncertain trial forms cannot enter completed-trial review; their raw bytes
remain retainable through the separate diagnostic retention path. Parent IPC
envelope/owned-process receipt validation is still required before trusting the
provenance of any reviewed result.

30 result-review, runner and owned-connection tests passed:
`software/runs/first-motion-result-review-20260913-01.xml`.
Tests cover real synthetic runner outputs, changed summaries, claimed physical
success, wrong byte counts, altered cleanup timing, and failed trial rejection.
No hardware was opened or commanded.

Remaining: source-pinned supervised child packaging and registration, production
child evidence composition, parent receipt integration, wizard launch and
independent observation review, then physical qualification and the full campaign.

## Previous checkpoint: clean capture validation before analysis

`application/first_motion_capture_validation.py` validates the separate capture
schema, request/phase association, original-byte hashes and canonical chunking,
phase byte/read budgets, host timing/deadlines and byte accounting. It recomputes
coverage and optional baseline framing from raw bytes rather than trusting child
summaries. Changed physical-success/freshness flags are rejected. Failed captures
remain retainable but cannot enter this clean-capture analysis path.

The owned commissioning runner now uses this validator before baseline checks
and before final raw telemetry analysis. Bounded IPC decoding and owned-process
receipt verification remain separate requirements for external child results.
A structurally valid capture may still contain invalid pose lines; the full-window
motion analyzer, not this integrity check, determines telemetry sufficiency.

39 validation/runner/connection/native-wrapper tests passed after integration:
`software/runs/first-motion-capture-validation-20260913-02.xml`.
The earlier standalone validation/capture/runner set passed 40 tests in
`software/runs/first-motion-capture-validation-20260913-01.xml`.
Tests used synthetic capture data and fake kernels only; no hardware access.

Supervised child packaging, whole-result validation and wizard integration still
remain. Neither clean capture integrity nor telemetry agreement qualifies the
physical wrist experiment or subsequent pose/speed campaign.

## Previous checkpoint: immutable diagnostic stream retention

`application/first_motion_result_retention.py` retains exact request, stdout and
stderr originals with byte counts, raw/stored SHA-256 digests and readback checks.
It accepts malformed or empty child output without interpreting child claims,
so failure evidence is not discarded. Limits are 256 KiB stdout and 8 KiB stderr;
invalid/oversized inputs are refused before publication. Immutable attempt names
prevent overwriting earlier evidence after interrupted or repeated publication.

The report is explicitly `ORIGINALS_RETAINED_NOT_VALIDATED`. It does not verify
a supervisor receipt, trust child-reported success, qualify physical movement
or allow campaign advancement. It intentionally remains callable after request
expiry so late failure evidence can be saved. The parent still needs to compose
this with IPC/result validation and actual owned-process receipt verification.

21 commissioning retention and endpoint-publication tests passed:
`software/runs/first-motion-retention-20260913-02.xml`.
The initial test run encountered generated test-ID/fixture setup errors from
large byte parameters; bounded explicit IDs corrected the harness. No retention
limits were relaxed, and no hardware was accessed.

Child packaging/registration, result validation, production child composition
and wizard integration remain incomplete. No physical qualification is claimed.

## Previous checkpoint: one-use worker claim and native execution wrapper

`application/first_motion_worker_claim.py` adds commissioning-specific launch
reservations, process-bound one-use claims and post-exit receipt verification.
It has separate schemas, filenames and exact request types from endpoint claims.
It retains the runtime registration bytes and binds request/source/runtime and
review-bundle hashes. Interrupted claim publication prevents reclaiming the same
attempt. These records bind integrity and ownership, not runtime approval.

`providers/windows/first_motion_trial_execution.py` consumes that claim before
opening the admitted connection and composes the existing commissioning runner.
Cancellation before open leaves the device unopened. Setup errors retain a
lifecycle snapshot and close acquired handles without retries. The wrapper has
no CLI or wizard activation and does not itself supervise a process.

Verification (synthetic runtime/reviews and fake kernel only):

- 15 commissioning/existing endpoint claim tests passed:
  `software/runs/first-motion-worker-claim-20260913-01.xml`.
- 18 execution/claim/connection and endpoint-execution regression tests passed:
  `software/runs/first-motion-execution-20260913-01.xml`.

No process was launched or hardware opened by this work. Still required are
source-pinned child packaging, fixed parent registration, production evidence
staging/child composition, durable result publication and wizard integration.
Actual physical reviews and qualification remain unmet; the pose/speed campaign
and evidence-backed settings report are not complete.

## Previous checkpoint: current commissioning reference reconstruction

`application/first_motion_reference_reader.py` reconstructs current source/build
hashes and all eight other commissioning reference hashes from fixed
attempt-relative original files. It reuses bounded regular-file validation and
does not accept arbitrary browser paths or digest callbacks. The endpoint reader
still rejects commissioning requests. Changed, missing or oversized originals
are refused; exact original bytes, not a dictionary of claimed hashes, are used.

41 reference/context/admission and existing endpoint-reference tests passed:
`software/runs/first-motion-references-20260913-02.xml`.
One test reconstructed the real workspace source/build hashes against synthetic
supporting originals. It does not validate physical evidence. The initial run
needed test exception expectations corrected for the durability layer's explicit
missing/oversized-file refusal; those refusal behaviors were not relaxed.

Before production use, the exact original measurement selected by the wizard
must also be staged byte-for-byte as its posture reference, and all other
supporting originals must actually exist and undergo semantic review. Worker
launch reservation, supervised packaging, child composition and wizard launch
remain incomplete. No hardware access was performed by this checkpoint.

## Previous checkpoint: commissioning current-context reader

`providers/windows/first_motion_current_context.py` reuses the established
persistent-controller metadata resolution and reference-reconstruction checks,
but accepts only `FirstMotionRequest` and returns `FirstMotionCurrentContext`.
The connection identity must equal the exact commissioning attempt ID. Missing,
duplicate, changed-port, stale or reference-mismatched observations are refused.
Source/build reconstruction remains before the fresh metadata snapshot so its
work does not silently renew the 100 ms metadata-acquisition window.

35 commissioning-context/admission and existing endpoint-context tests passed:
`software/runs/first-motion-context-20260913-01.xml`.
Fixtures contain explicitly synthetic metadata; no enumeration or device open
occurred. A matching USB metadata snapshot is not proof of firmware, arm model,
geometry, clearance or an atomic binding to a subsequently opened handle.

Production still must provide supervised metadata acquisition and actual
reference reconstruction to this reader, compose it into authenticated admission,
and package/launch the owned worker through the wizard. Merely constructing a
context object or passing synthetic tests does not satisfy those live steps.

## Previous checkpoint: commissioning owned-connection composition

`providers/windows/first_motion_serial_connection.py` now binds the exact
commissioning request and admitted native facade to the shared exclusive handle
lifecycle. Its fixed payload is T101 from the immutable commissioning request;
the original endpoint owner still rejects these types. Cleanup returns the
commissioning-specific result and snapshots use a distinct lifecycle schema.

An integrated synthetic test traverses authenticated admission, native facade,
owned connection, commissioning runner, collector and raw analysis down to a fake
Windows kernel: 20 baseline reads, one exact wrist write, 100 post reads, then
reverse-order closure of the two events and port. Additional tests reject wrong
payloads and endpoint substitution and ensure setup failures close handles
without a write or reopen. This test does not load a real DLL or access hardware.

23 connection/runner and existing endpoint-owner tests passed:
`software/runs/first-motion-connection-20260913-01.xml`.

Remaining: production current-context/review construction, supervised worker
packaging/launch and wizard integration, independent physical observation intake,
then actual approved qualification and pose/speed characterization. The connection
class alone is not authorization to open the attached arm; opening can cause
controller reset/startup movement. No physical trial was performed here.

## Previous checkpoint: owned commissioning sequence

`application/first_motion_owned_trial.py` composes baseline capture and reported
baseline validation, authenticated one-use consumption, one exact wrist write,
post capture, raw telemetry analysis and unconditional cleanup. It does not open
a connection and is not a wizard live launcher. Trusted worker composition must
bind its writer to the matching native facade and enforce native timeouts plus
parent-process supervision; arbitrary Python callbacks cannot provide that.

The baseline must have clean full-window records, sufficient host time span,
stable reported joints and wrist reports consistent with the independently
declared starting interval. This comparison is not independent measurement or
device freshness qualification. The existing authenticated measurement/review
reader remains required at permit consumption and native dispatch.

Short writes and submission exceptions are never retried; post data is retained
when possible because an uncertain submission may still have moved the arm.
Cancellation or capture failure cannot yield a successful response status.
Cleanup is attempted even after diagnostic clock failure, and uncertain cleanup
overrides telemetry agreement. No result authorizes campaign advancement or
claims physical movement or stopping.

196 commissioning and existing endpoint capture/runner/serial tests passed:
`software/runs/first-motion-owned-regression-20260913-01.xml`.
All commissioning runner tests used synthetic readers/writers, not hardware.

Next: production owned-connection/context and supervised-worker composition,
wizard review/launch integration, independent observation intake and actual
physical qualification. The original pose/speed campaign goal is still pending;
this first wrist experiment is a prerequisite, not a replacement deliverable.

## Previous checkpoint: bounded commissioning capture

`application/first_motion_capture.py` now provides a separate typed collector
for the fixed 1-second baseline and 5-second post-write windows. The actual read
loop is shared privately with the existing endpoint collector; each public
wrapper still rejects the other request type and produces a distinct schema.
Commissioning does not acquire a fabricated Cartesian campaign or endpoint permit.

Limits remain 32 KiB/256 reads before writing and 64 KiB/512 reads afterward,
with at most 256 bytes per read. Cancellation, late completions and partial bytes
are retained. A delayed post-capture start cannot extend the deadline measured
from write completion. Cleanup time remains reserved. The collector itself has
no open, write, purge or close operation and cannot preempt a blocking callback;
the supervised native worker must supply bounded reads and own cleanup.

36 commissioning-capture and existing endpoint-capture/trial tests passed:
`software/runs/first-motion-capture-20260913-01.xml`.
Tests used synthetic readers only. No hardware was opened or commanded.

Next integration remains the owned commissioning runner that composes baseline
validation, one-use dispatch, post capture and unconditional cleanup, followed
by production wiring and wizard observation intake. The live path is not ready.

## Previous checkpoint: raw wrist-response diagnostics

`arm/first_motion_analysis.py` processes retained baseline and post-command
bytes using the full-window telemetry parser (64 KiB / 512 read-window bounds).
It retains original-byte digests and explicitly identified boundary fragments,
checks every interior frame, and compares all six reported joints. It rejects
invalid records, coverage gaps, unstable baselines, reported wrist excursions,
changes in other reported joints, missing change and missing final target dwell.

The diagnostic thresholds are provisional: 0.5 degree comparison tolerance,
100 ms maximum host-read gap, 100 ms baseline span and 200 ms final target dwell.
These are neither measured mechanical accuracy nor protective safety limits.
Buffered samples with no elapsed host span cannot manufacture dwell. Reported
agreement can still be a cached-command artifact; the result never qualifies
device freshness, physical movement, endpoint baseline or campaign advancement.
Write completion, cleanup and independent physical observation must be composed
separately by the commissioning worker/coordinator.

23 focused and existing endpoint-analysis/framing tests passed:
`software/runs/first-motion-analysis-20260913-02.xml`.
The first run exposed an invalid overlapping-timestamp synthetic fixture; the
fixture was corrected to use equal zero-duration timestamps, and the intended
no-elapsed-dwell rejection now passes. No hardware was accessed.

Remaining integration is unchanged: bounded owned worker, production context
and review wiring, wizard launch/observation intake, then actual qualification.

## Previous checkpoint: separate native commissioning facade

`providers/windows/first_motion_serial_api.py` now binds only an exact
`FirstMotionRequest` and admitted `FirstMotionPermit`. It reuses the endpoint
facade's owned-handle, overlapped-I/O, pinned-buffer and cleanup implementation
through a fixed payload hook; the original endpoint factory still rejects
commissioning types. The commissioning factory cannot accept arbitrary permits.

The adapter submits only the immutable request's fixed wrist command, at most
once. Changed payloads, missing consumption or changed COM context refuse the
write. Pending/uncertain writes retain buffers and prevent cleanup from freeing
resources prematurely. A short write retains its actual byte count and is never
retried; the future worker must classify it as inconclusive. Handle closure or
software timeout is not a physical stop.

69 tests passed with a fake kernel, covering the new facade, commissioning
admission and existing endpoint serial/connection/trial regressions. Receipt:
`software/runs/first-motion-native-20260913-02.xml`.
No Windows DLL or physical device was accessed by these tests.

Still required: supervised current-context production wiring, a bounded owned
commissioning worker, raw before/after observation analysis and wizard launch
integration. This adapter is not registered for live wizard execution. Actual
geometry measurements and physical/compatibility reviews remain prerequisites.

## Previous checkpoint: one-use commissioning admission

Implemented in `safety/first_motion_admission.py` with an authenticated reader
in `safety/first_motion_review_authority.py`. This is software admission only;
it performs no device I/O and is not yet connected to a native motion executor.

- Rechecks the exact request, original measurement, signed review originals,
  USB identity, current references, deadlines and owned COM endpoint.
- Exclusively reserves the attempt on disk before issuing a permit. Interrupted
  admission cannot reuse that reservation; the production root must be stable
  across restarts and must not be selectable by browser input.
- Allows one open claim, one permission consumption and one dispatch claim.
  Failed validation revokes permission; this does not physically stop an arm.
- Pins the COM endpoint through consumption and dispatch. Identity equality
  alone cannot silently admit a port change after opening.
- Rejects modified reservations/reviews, backwards clocks, expired acquisition
  windows, omitted/replaced dispatch ports and duplicate consumption/dispatch.
  Recent host acquisition still does not prove fresh device measurements.
- Remains separate from the normal Cartesian endpoint permit and native API.

Verification used synthetic files/context and no native transport:

- 57 commissioning admission/authentication/measurement-binding tests passed:
  `software/runs/first-motion-admission-20260913-02.xml`.
- 63 existing endpoint admission/serial/reservation/key/review regression tests
  passed: `software/runs/first-motion-admission-regression-20260913-01.xml`.

Next: implement the supervised native context provider and separate bounded
single-joint transport/worker, then test fault handling and raw observation
analysis through the wizard. Actual independent geometry measurements,
installed-unit compatibility and physical reviews are still required before
live execution. No live movement or hardware qualification is claimed here.
Earlier checkpoints below describe their state at the time of completion.

## Proposed experiment and rationale

Investigate a single **wrist-pitch joint** command (T101, joint 4), rather than
using unqualified Cartesian feedback to reposition several joints through IK.
The candidate is an absolute +1 degree wrist position, 20 servo steps/second,
acceleration parameter 1. These are proposed commissioning settings, not measured
physical limits. In particular, this is not a relative +1 degree command.

An independently established initial wrist interval of [-5,+5] degrees would
bound the requested angular travel to at most 6 degrees. This interval is a
prerequisite to measure/review, not something established by the current photo.
With an independently checked distal assembly radius no greater than 200 mm,
the ideal rigid-point path length would be at most 20.944 mm. Cable slack,
deflection, servo overshoot, wrong configuration and startup motion are outside
that ideal bound and require their own reviewed clearance margins. Do not use
this calculation as a protective safety limit or a full-arm collision check.

No other joint is requested to move. No gripper actuation, home, automatic
return, repeated movement, torque release or configuration change is included.

## Official source review

Reference archive:
https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip

SHA-256: `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
Downloaded into memory and hash-checked for this review; not installed or run.

- `uart_ctrl.h:16-22` passes joint/rad/spd/acc to single-joint absolute control.
- `RoArm-M3_module.h:770-797` selects wrist control for joint 4. That branch
  updates cached joint values and computed coordinates; a commanded/cached
  value must not count as observed physical motion.
- `RoArm-M3_module.h:364-372` clamps wrist radian input to +/-pi/2 and writes
  the wrist servo only, passing the requested speed and acceleration.
- `RoArm-M3_example.ino:202-215` subsequently refreshes servo feedback and
  optionally emits telemetry. This is not a verified installed-firmware schedule.
- Crucially, `RoArm-M3_module.h:72-100` retains the previous position on failed
  servo feedback; `625-642` does not check those return values before computing
  coordinates. Repeated, plausible telemetry alone cannot certify fresh feedback.

[Official command documentation](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control)
identifies joint 4 as wrist pitch, angles in radians, servo speed in steps/s
(4096 steps/revolution), and acceleration in units of 100 steps/s². Avoid zero
speed/acceleration sentinel behavior. Documentation/reference compatibility
does not identify the received binary; retain that uncertainty explicitly.

## Implementation sequence and acceptance

1. Implement a pure, fixed proposal and deterministic observation-assessment
   rehearsal. No native imports, live permits, connection or write callbacks.
2. Add a wizard rehearsal action and verified diagnostic export. Cover nominal,
   unchanged, telemetry-only, physical-only, wrong-direction, short-write and
   cleanup-uncertain outcomes. Even agreement requires engineering review.
3. Define the separate original-bound live commissioning contract: exact unit,
   measured starting-angle interval, distal radius, full clearance/drop review,
   supplied power, current operator, one immutable command, explicit speed and
   acceleration, installed-unit compatibility review and observation method.
   Telemetry freshness must be UNKNOWN at entry, not falsely marked verified.
4. Independently review and implement a separate native one-command adapter;
   preserve ownership, deadlines, source/identity binding, no retry and cleanup
   diagnostics. Existing T104 permits must reject this command family. Do not
   widen the generic transport or change its physical holds.
5. Integrate actual observation capture: before/after frames with original host
   times, independent physical observation, and all write/cleanup results.
   Reject disagreement, malformed/stale evidence, unexpected other-joint motion,
   cancellation or uncertain cleanup. A firmware echo is not servo movement.
6. Run one supervised physical trial only after steps 3-5 pass and physical
   prerequisites are freshly confirmed. Export all outcomes; no automatic return.
7. Use agreement only as evidence for the tested joint/event. It does not qualify
   all joints, permanent freshness, continuous tracking or absolute calibration.
   Review what additional evidence the original Cartesian trial needs; then
   resume the original pose/speed characterization plan without redefining it.

## Current completion

### Commissioning review-authentication checkpoint

`safety/first_motion_review_authority.py` now requires twelve explicit original
reviews under a distinct wrist-experiment schema: seven operator attestations
and five engineering reviews. Missing, denied, unknown, altered, expired or
wrong-scope reviews cannot be sealed into an acceptable bundle.

Engineering originals bind `FirstMotionRequest.selection_sha256`, which excludes
only the attempt ID and request timestamps. All identity, command, source,
reference, measurement and limit fields remain bound. Engineering reviews may
predate the final request for at most their five-minute lifetime. Operator
originals must bind the full exact request and fall inside its actual time
window. Sealing preserves original bytes and times; effective expiry is bounded
by every review and the request deadline.

The protected host bench key derives a separate commissioning key/domain through
`BenchReviewAuthority.for_first_motion()`. The host loader uses the existing
DPAPI store without exporting a key, provisioning a replacement or adding a
browser signing endpoint. Existing Cartesian review/request types reject these
commissioning types. DPAPI still does not isolate software running as the same
Windows user, and authentication does not prove the truth of physical reviews.

61 initial focused tests passed; after the final cache/loader test changes,
63 combined authority, protected-key, existing endpoint issuance, native package
and worker-preparation tests passed. JUnit:
`software/runs/first-motion-authority-20260913-01.xml` and
`software/runs/first-motion-authority-regression-20260913-01.xml`.

This implements review authentication, **not a native motion permit**. Actual
current original acquisition, owned-context validation, durable one-use admission,
native commissioning execution and physical observation qualification remain
outstanding. No actual-unit approval bundle was fabricated or signed, and no
device was opened during these tests.

### Exact retained-measurement selection checkpoint

The measurement loader now reads only a fixed operation-derived original from
the host's assigned root, checks its exact request-bound SHA-256, reconstructs
all declared fields and uncertainty calculations, and verifies source/session/
operation/unit association. Request angle interval and radius must exactly match
the complete recorded uncertainty bounds. It rejects stale/future recording
times, changed context, edited claims and geometry substitutions. The five-minute
record-age check is not a claim of physical measurement freshness.

Trusted host method `ArrivalWizardService.select_first_motion_measurement`
resolves the digest from a successful measurement operation in this same session;
it does not accept another session's receipt or a caller-selected file. Selection
is logged and does not create any endpoint binding, permit or native connection.
The record's original timestamp is preserved, and a short-lived request remains
subject to its original execution/cleanup budget after selection logging.

162 combined measurement, request, rehearsal, catalog and existing endpoint
intake/live-action tests passed in 3.75 seconds before the additional final
post-log time recheck. Evidence: `software/runs/first-motion-selection-20260913-01.xml`.
Synthetic test originals are not actual-unit physical evidence. Actual measured
originals and commissioning-specific authenticated admission/native execution
remain outstanding.

### Independent measurement intake checkpoint

Wizard action `record_first_motion_measurements` now records operator-reported
noncontact measurements through a parent-only path. The actual source/session/
operation and recording timestamp bind the immutable original. The result carries
the complete original for the existing diagnostic export path; no device is opened.

The observer must report the unit serial, method, wrist angle **relative to the
forearm**, angle uncertainty, radius from wrist axis to the furthest distal rigid
part, radius uncertainty and explanatory notes. An explicit acknowledgment is
required that these are actual independent measurements, not telemetry, a
simulation or assumed form defaults. The present photograph has not been converted
into invented numeric measurements.

The derived interval expands by +/- angle uncertainty; the radius upper bound
adds radius uncertainty. Observations outside the proposal are still retained
and marked outside its numeric bounds. Nothing is clamped into eligibility.
In-range numbers do not authenticate physical measurement, observer identity,
unit association, clearance or motion approval. Recording time is explicitly
distinct from independently verified measurement time.

119 focused tests passed, including the public wizard record/export workflow,
out-of-proposal retention, malformed input refusal and immutable publication.
Another 69 existing service/engineering-intake/endpoint tests passed.
JUnit evidence:
`software/runs/first-motion-measurements-20260913-01.xml` and
`software/runs/first-motion-measurements-regression-20260913-01.xml`.

Next implementation work is selecting and validating exact retained measurement
originals against the commissioning request, followed by distinct authenticated
admission/native ownership and raw-observation analysis. Numeric checks alone
must not serve as the admission decision. No live commissioning executor or
actual-unit measurement approval exists at this checkpoint.

### Separate request/review contract checkpoint

`application/first_motion_contract.py` defines canonical immutable
`FirstMotionRequest` data for exactly T101/joint 4/absolute +1 degree/speed 20/
acceleration 1. It cannot be parsed as an `EndpointTrialRequest`. Ten distinct
supporting-reference digests are required, including independent posture,
swept-clearance, observation-method and installed-unit compatibility reviews.
Digest validity does not authenticate any of those physical assertions.

The declared starting interval must stay within [-5,+5] degrees, and declared
distal radius within (0,200] mm. These declarations still need independent
measurement/review before admission. Feedback freshness at entry is explicitly
UNKNOWN. The fixed no-retry, one-write resource budgets and bounded request
lifetime cannot be changed. The normal endpoint guard is unchanged.

New wizard action `first_motion_review` validates and displays retained request
JSON without accepting execution flags or supplying device access. Preview
states that measurement authentication, physical clearance and live execution
are not established. The rehearsal shares the fixed command definition so its
proposed speed/acceleration/target cannot drift from this contract.

104 focused contract/rehearsal/catalog tests passed. JUnit:
`software/runs/first-motion-contract-20260913-01.xml`.
Tests include target/joint/speed changes, zero-speed sentinels, Boolean inputs,
bad intervals, oversized radius, forged freshness, expired requests, identity
changes, duplicate JSON fields and normal-endpoint format rejection.

This is step 3's data/review portion only. Actual measured originals,
authenticated commissioning admission, one-use native execution, observation
analysis and physical qualification remain incomplete. No request has been
constructed from fabricated measurements for the actual attached arm.

Steps 1-2 now have a fixed proposal and observation-logic rehearsal implemented
in `application/first_motion_rehearsal.py`, exposed through wizard action
`first_motion_rehearse`. This simulates evidence categories, not servo dynamics
or measured motion. All nine scenarios completed through the public service.

Verification: 77 focused/catalog tests and 88 existing endpoint/service regression
tests passed. JUnit receipts: `software/runs/first-motion-rehearsal-20260913-01.xml`
and `software/runs/first-motion-endpoint-regression-20260913-01.xml`.

Results are retained across two verified exports under `software/runs/wizard-exports`:

- `wizard-20260913T152834046761Z-8214707722c749aaac1059b2fdc29815` (eight fault scenarios).
- `wizard-20260913T152926743812Z-2443105c52d24abab0a7865be037eff3` (nominal scenario).

The diagnostic export retains a bounded recent-result attachment set; the nominal
case was exported separately so all nine full results remain available. An initial
verification looked for full result text in the compact report snapshot; the
actual full results reside in `attachment-result-*.json`. Verify those attachments,
not text presence in the snapshot. No hardware was accessed by these rehearsals.

Browser visual QA and steps 3-7 are not complete. No first-motion native command
path has been added; the normal endpoint admission policy is unchanged.

This plan is the governing design for the new procedure. Steps 3-7 remain live
integration/qualification work, not a license to bypass them. A simulation PASS
or an operator's permission alone cannot satisfy the physical prerequisites.
