# Observational bench testing — revised acceptance policy

Date: 2026-09-13. User decision: use observations, photos and available internal
metrics for basic movement testing; defer precision measurements to calibration.

## What changes

### Capture-boundary implementation checkpoint

The real-clock, hardware-incapable rehearsal now exercises host preparation,
child admission, a one-second synthetic baseline, exactly one synthetic command,
and a five-second synthetic post window. It uses synthetic metadata and review
authority, and never opens a native serial handle. This is software evidence,
not a physical movement qualification or a complete browser-to-hardware test.

The observational collector no longer starts a read in the final 50 ms of its
window. Earlier reads reserve 25 ms before the window deadline; the collector
waits through the remaining tail with cancellation checks. Original deadlines,
timestamps and coverage are retained. Late completions still fail and retain
their bytes; telemetry-age checks, one-command limits and no-retry behavior
remain unchanged. The separate measured profile retains its previous behavior.
An overloaded host may still hold a trial; these tests do not guarantee timing.

Verification: 259 regression tests passed in
`../runs/observational-capture-boundary-20260913-02.xml`; 12 focused tests passed
in `../runs/observational-tail-regression-20260913-01.xml`, including cancellation
in the tail, late-byte retention, unchanged window deadlines and real-clock
synthetic execution. No physical command was sent for this checkpoint.

For supervised, non-contact functional tests, do not require the operator to
measure wrist angles, distal radius, millimetre displacement, uncertainty or
timing. Do not require a calibrated photograph. A plain-language observation is
valid evidence of visible movement; photos or video are optional supporting
evidence, not an additional mandatory gate. A still image alone cannot establish
the path, speed or absence of a transient collision.

Keep observations labelled operator-reported. Keep controller positions labelled
controller-reported. Neither needs to pretend to be independent metrology for us
to accept a basic functional response. Unknown accuracy is not a failed response.

## Operator workflow

1. Confirm once per supervised session that the arm is secured, supplied power is
   on, the movement area and cables are clear, and power shutdown is reachable.
   Reconfirm after a setup change, interruption or unexpected event—not each move.
2. Software identifies the connected unit and captures a baseline. It displays
   the selected joint, expected direction and bounded target before dispatch.
3. Start with one slow, small, single-joint, free-space movement. No contact,
   homing, automatic return, speed sweep or continuous sequence at this stage.
4. Operator reports: moved as expected, did not move, moved unexpectedly, or
   unsure. Add noise, vibration, cable or other concerns when present. No ruler
   or stopwatch is required.
5. Software pairs that observation with the command and available telemetry.
   Matching expected movement and a clean capture support a functional pass for
   that trial. Conflicts or missing evidence remain visible and stop progression.
6. Progress one variable at a time: repeatability, modest displacement changes,
   then speed changes, then a short finite multi-pose sequence. Each next command
   still needs current baseline and bounded-path checks. No unrestricted loop.

## Metrics software should collect automatically

- Device identity, command, host timestamps and transport/cleanup errors.
- Reported joint positions before, during and after the command, when available.
- Reported target error, sample gaps and apparent settling duration, with units
  and coverage. Host receipt time is not a device timestamp or exact motion time.
- Available load/error fields, retaining their native meaning; do not label an
  uncalibrated load field as measured contact force.
- Operator outcome and optional image/video association, paired to the trial ID.
- One export bundle in the workspace wizard export folder, including raw records,
  summary and any disagreements. Missing metrics are marked unavailable.

A functional pass does not certify millimetre accuracy, device-sample freshness,
physical emergency stopping, every other pose, or readiness to touch a device.

## Measurements reserved for later

Before keyboard or phone contact: board and camera registration, tool-tip offset,
surface heights, key/target locations, safe approach/retract geometry and bounded
contact travel. Use known build dimensions and software-derived estimates where
appropriate; request physical measurements only where the task actually needs them.

## Implementation status and next work

Implemented first component: `motion/observational_wrist_plan.py` generates a
preview of a one-degree wrist offset converted to an absolute T101 target using
a recent stable six-joint reported baseline. It bounds capture size, age, gaps,
stability and the first-test wrist envelope. It requests no physical angle/radius
measurements and grants no execution authority. Unit and unchanged measured
contract regression tests: **48 passed** on 2026-09-13 (synthetic, no hardware).

Command reference checked against the manufacturer's
[joint-control documentation](https://www.waveshare.net/wiki/RoArm-M3-S_%E6%9C%BA%E6%A2%B0%E8%87%82%E6%8E%A7%E5%88%B6):
T101 targets an absolute joint angle in radians; joint 4 is wrist pitch; speed is
servo steps/second, with zero selecting maximum speed. This reference does not
identify or certify the firmware installed on our individual Pro unit.

Raw-capture adapter and response assessment are now implemented in
`arm/observational_wrist_analysis.py`. They consume original bytes/read windows,
retain framing hashes, examine every complete frame, preserve shared host read
timestamps, and compare the supplied dispatched command with the baseline-derived
candidate. Target response/dwell, other-joint excursions, operator outcome and
transport/cleanup status determine a basic functional pass or hold. Synthetic
passes have a separate label. Accuracy and future movement authority remain false.
The caller still must authenticate the command/transport/identity association;
passing a dictionary to this pure analyzer does not establish those facts.

Verification: **73 tests passed**, including existing measured-contract/analysis
regressions, retained-byte adaptation, shared reads, invalid frames, observation
conflicts and command mismatch. Evidence:
`software/runs/observational-wrist-analysis-20260913-01.xml`. No live device access.

Wizard publication integration: `PoweredFeedbackOutcome._telemetry_publication`
now adds `observational_wrist_preview` to a successful owned telemetry result.
`application/observational_capture_preview.py` decodes and hashes original capture
bytes, checks all complete frames, then selects the final one-second baseline.
It labels the result historical-only and does not renew capture time. A malformed
capture or unsuitable baseline produces a held diagnostic without suppressing
the primary capture result. Failed owned outcomes do not produce a preview.

Verification: **133 tests passed** (wizard service, new preview/publication tests,
observational planning/analysis, measured contract/analysis and powered no-reply
regressions). Evidence: `software/runs/observational-wizard-preview-20260913-01.xml`.
The publication integration tests use an incapable process-result double and
actual synthetic raw-frame parsing; they do not prove a live USB trial or browser
rendering. No device was opened in this change.

Command binding implementation: `application/observational_command_binding.py`
now reserves one attempt durably, derives its exact command from baseline bytes
recorded after issuance, binds the selected session/connection/USB identity, and
allows one consumption. Changed retained files, stale acquisition, context
mismatch, backwards time or a failed selection prevent reuse. The binding grants
no physical permission and is not accepted as a permit by existing native APIs.
Its identity arguments must come from authenticated native admission, not
browser input. Native admission is described below; worker wiring remains pending.

Authentication implementation: `safety/observational_review_authority.py` now
authenticates the exact bounded policy, session/attempt, USB identity, source,
runtime and protocol references plus four explicit operator confirmations. No
measured geometry fields are required. `BenchReviewAuthority` derives a separate
observational key and the Windows loader reads existing DPAPI storage without
creating or replacing it. These APIs are trusted-host internals, not browser
signing endpoints. Record authentication is not physical truth or a native permit.

Verification: **78 tests passed** for observational authority, command binding,
capture publication, planner and analysis. Evidence:
`software/runs/observational-review-authority-20260913-01.xml`. Synthetic keys only;
the real private key was not loaded or provisioned, and no hardware was accessed.

Current-context implementation: `providers/windows/observational_current_context.py`
uses the existing reviewed-controller metadata resolver, with an immutable
`ObservationalIntent` and a separate authenticated reader. It re-reads the review
bundle, reconstructs references via the host provider, checks current metadata
and the selected COM endpoint, then verifies the signed intent. The signed
references now include `native_controller_review_sha256` so the actual reviewed
binding cannot be substituted. Metadata does not prove handle association or
physical conditions, and this reader does not open a serial port.

Native admission implementation: `safety/observational_admission.py` joins the
authenticated reader with durable command binding: admitted -> open claimed ->
baseline selected -> one dispatch. Boundary checks re-read signed records and
current metadata. Changed context or failed consumption revokes the attempt;
the same attempt cannot be re-admitted after restart. The separate
`providers/windows/observational_serial_api.py` accepts only this permit and
reuses existing bounded Win32 ownership/exact-token submission. Its construction
is inert; it is not registered with the wizard or a live worker yet.

Admission tests use synthetic records/metadata and prohibit native kernel loading
in the facade-construction test. They cover duplicate open, single dispatch,
concurrent attempts, changed port/device/review, stale baseline and revocation.
They do not prove a real native WriteFile path or physical motion.

Owned-runner implementation: `application/observational_owned_trial.py` now runs
baseline -> authenticated command selection -> one submission -> bounded post
capture -> unconditional cleanup on an already-owned connection. Uncertain writes
are never retried and still receive post capture when the budget allows. An
otherwise clean result awaits the operator's observation, not physical qualification.
`observational_capture.py` reuses the existing raw collector and original-byte
validator with a distinct typed schema; `observational_serial_connection.py`
reuses bounded handle ownership/cleanup without converting the intent to a
measured request. Native-worker registration and wizard live wiring remain absent.

Synthetic runner tests exercise actual capture loops, metadata/review checks,
one-use command selection and cleanup callbacks, including cancellation, malformed
baseline, short write, write exception and cleanup failure. No real serial I/O.

Result reconstruction: `application/observational_result_review.py` verifies a
bounded completed-trial original and exact command-selection original against
the immutable intent. It reconstructs capture coverage, selected preview, write
accounting, timing and cleanup, then recomputes telemetry with operator outcome
UNKNOWN. Changed command/data/selection/cleanup claims are rejected; uncertain
submissions remain diagnostics instead of clean completed trials. This does not
authenticate a worker process or replace the separate operator observation.

Native request contract: `providers/windows/observational_native_protocol.py`
defines the distinct worker ID, fixed process budget, bounded handoff and exact
outer request association. It binds session/attempt, intent, selected USB identity,
source, runtime reference and deadlines. It carries neither caller-selected motion
commands nor measured geometry. Extra fields and rehashed context substitutions
are rejected. Parsing only establishes consistency; actual registration, package
pins, process claim, child entry point and supervised launch remain pending.

Native result envelope: `providers/windows/observational_native_result.py` binds
the returned envelope to its exact request and claim digest, checks bounded
lifecycle/capture counters, and reconstructs clean trial/selection originals.
Failures remain diagnostic-only even if their nested data looks successful.
Process receipt authentication and physical movement are explicitly unverified.
Codec tests use synthetic trial data labelled with the expected native domain
solely to exercise validation; this is not a physical test or process proof.

Worker claims/composition: `application/observational_worker_claim.py` retains a
one-use launch reservation and process-ID-bound claim, verifies original runtime
and review associations, and supports parent-owned PID receipt checking after
completion. `providers/windows/observational_trial_execution.py` consumes that
claim before constructing/opening the native connection, revokes on claim failure,
runs the owned sequence, reads the exact selection original and retains lifecycle
cleanup data. A guarded registered child entry now exists; a wizard action is
still pending.
Tests cover replay, changed process/runtime/review, cancellation before open and
rejected runtime; native kernel loading is prohibited in composition tests.

Worker package: `providers/windows/observational_native_package.py` builds a
deterministic explicit dependency archive. `_observational_native_child.py` now
supports isolated `check-imports`, verifies the archive digest, and forbids
native DLL loading, sockets and child-process creation during that check. Real
isolated subprocess tests passed; wrong hashes and malformed `execute-one`
requests are rejected. The guarded `execute-one` entry verifies the actual
invocation and pinned interpreter/entry before reconstructing a signed reserved
request. These tests do not establish hardware operability.

Registration/reference implementation: `observational_native_registration.py`
checks the fixed interpreter, child argv, archive bytes, controller/protocol pins,
resource budgets and exact outer request against the signed runtime reference.
`ObservationalReferenceReader` recomputes source and fixed-file original hashes.
The supervisor verifies registration and reserved originals before backend
creation, repeats the original/review checks before resume, and validates the
result against the owned process claim. Incapable-backend tests exercise these
boundaries without devices; accepted registration is not semantic approval of
fixture records.

Two-phase preparation: `application/observational_worker_preparation.py` stages
the deterministic archive, controller/protocol originals and registration before
the timed request. Final preparation re-reads references, reconstructs the reviewed
controller, authenticates the supplied review using the existing host key, reserves
one launch and validates the outer registration. It never launches or provisions
a key. Partial directories remain retained and cannot be silently reused.
Synthetic preparation tests cover changed originals/review, missing key, expired
budget and replay; the key loader is replaced only inside those tests.

Child reconstruction: `observational_prelaunch.py` rechecks source/originals,
reserved launch and signed review before entry. `observational_child_execution.py`
then freezes verified execution originals (not current-workspace truth), reconstructs
the controller, claims the process attempt, obtains fresh metadata and admits the
single command path. Metadata, signed-review expiry and baseline recency are not
frozen. Source scans stay outside the short baseline-to-write interval.
Synthetic composition tests reach an incapable execution boundary using actual
file/reference/authentication logic; changed originals, replay and cancellation
are rejected. The isolated child entry and supervised branch are implemented,
but no physical trial has been qualified through this path.

One initial test inadvertently reached the actual read-only host key lookup,
which reported no configured key. Nothing was provisioned or changed; fixtures
were corrected to use their synthetic key at both imported loader references.

Parent integration: `application/wizard_observational_coordinator.py` prepares
one reviewed request, checks the current host context, supervises once, and
retains the actual receipt even when cancellation follows dispatch. Export
failure returns that receipt for recovery without retrying motion.
`providers/windows/observational_result_publication.py` saves bounded original
request/stdout/stderr bytes before interpreting child output. Reports preserve
parent timing/resource/cleanup metrics, validate the owned PID claim, and never
treat a retained report as a functional pass or campaign authorization.
Synthetic tests cover malformed output, wrong request/PID, cleanup uncertainty,
cancel-before/after dispatch, changed authorization, export failure and immutable
round-trip retention. No hardware APIs are used by these coordinator fixtures.

Operator UI integration: `record_observational_movement` now selects the current
session's retained observational result, asks for an operator label, outcome and
whole-trial coverage, and accepts empty optional notes. No measurement, photo or
separate limitations narrative is required. It re-reads the exact saved result,
rejects changed/cross-session selections, and retains request/result/observation
originals. `export_logs` includes a hash-checked, bounded original-byte bundle.
This action records evidence only; expected movement does not override telemetry
conflicts or authorize another command. Public service preview/execute/export
tests use synthetic host-injected trial results, not live hardware or browser
rendering. The action remains unavailable until this session has a retained trial.

Run UI integration: `run_observational_movement` now consumes one final click,
preserves its original timestamp, signs the fixed policy with the existing host
key, and invokes the observational coordinator. The parent retains the actual
outcome for observation and raw-log export, including report-publication failure.
Source/setup changes, old confirmation, unchecked setup, missing key and consumed
attempt remain holds. No key is created implicitly. The trusted host method
`configure_observational_movement` stages typed reviewed controller and structured
protocol originals without measurements or device access. The public
`setup_observational_movement` action now selects a committed same-session
source receipt, verifies its original hashes, reconstructs the typed controller,
and stages the runtime. No manual JSON/hash entry or arbitrary COM input is
added to the form. Sources enter through the trusted host method
`retain_reviewed_observational_sources`, limited to eight records; its caller
must provide already reviewed controller/protocol originals. This is not a
browser upload and does not promote the older unreviewed support-record sets.
`use_current_arm_for_observational_test` now provides the public intake route:
it reuses the current correlated metadata and generic USB review, records an
explicit operator-reported RoArm-M3 Pro/unchanged-firmware statement, and retains
the original metadata, generic review, history, serial profile, boot policy and
fixed vendor protocol review. It populates the setup selector without user-entered
JSON, paths or hashes. USB correlation still does not identify installed firmware.

The fixed vendor review was checked on 2026-09-13 against
[Waveshare joint control](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control)
and the [RoArm-M3 overview](https://www.waveshare.com/wiki/RoArm-M3).
T101 selects one joint; joint 4 is wrist pitch and its target uses radians.
The policy selects nonzero speed/acceleration and derives the absolute target
from the owned baseline. Vendor documentation is not proof of installed code.

Functional assessment integration: recording an observation now invokes
`observational_functional_assessment.py`. It reconstructs the original request,
stdout/stderr, native trial, current host-held process receipt and retained
observation. It checks the owned PID claim and clean process completion before
recomputing the full-window response with the reported outcome and coverage.
`OBSERVED_FUNCTIONAL_PASS` means matching functional evidence only; missing or
conflicting evidence remains HELD. Accuracy, device sample freshness, physical
stopping and next-command permission remain explicitly unverified/not granted.
The immutable assessment and its hash are included in the operator export bundle.
Tests use synthetic native-domain codec captures and an incapable claim-check
substitute for the positive correlation fixture; this is not live qualification.
Real claim/PID validation remains covered separately by coordinator regressions.

Next integration: verify the complete intake/setup/run/observe UI workflow and complete
export round-trip. The owned runner already recomputes the preview within its
connection. Do not dispatch a plain preview dictionary through an unguarded
serial helper.

Regression checkpoint: 228 observational and shared owned-worker tests passed
on 2026-09-13. Report: `../runs/observational-supervised-launch-20260913-01.xml`.
This includes incapable-backend before-resume checks, not live arm movement.

Coordinator checkpoint: 250 observational, shared supervisor and existing
measured-profile coordinator regressions passed on 2026-09-13. Report:
`../runs/observational-coordinator-20260913-01.xml`. The observational setup/run
workflow and live qualification remain incomplete; the full campaign goal stays active.

Operator UI checkpoint: 303 observational, action-catalog, arrival-service and
existing measured-observation wizard tests passed on 2026-09-13. Report:
`../runs/observational-operator-wizard-20260913-01.xml`. No live movement occurred.

Run UI checkpoint: 309 observational/catalog/service/legacy-run regressions
passed (`../runs/observational-run-wizard-20260913-01.xml`), followed by 15 focused
run tests after the final cross-profile hold and raw-export recovery changes.
Tests use incapable coordinator substitutes; live operation is not qualified.

Setup selector checkpoint: 318 observational, action-catalog, service,
controller-context and legacy-run regressions passed. Report:
`../runs/observational-setup-wizard-20260913-01.xml`. The new setup tests retain
synthetic reviewed inputs and reject changed originals without device access.

Functional assessment checkpoint: 260 observational, arrival-service and legacy
observation-wizard regressions passed. Report:
`../runs/observational-functional-assessment-20260913-01.xml`. Original assessment
bytes are verified through the public service export round-trip. No live trial
or progressive pose/speed characterization has been qualified by this checkpoint.

Onboarding intake checkpoint: 319 observational, action-catalog and arrival-service
regressions passed (`../runs/observational-onboarding-intake-20260913-01.xml`).
The public intake test populates the setup selector from modeled metadata and
explicit operator reports without querying or opening hardware. End-to-end
rendered UI and live qualification remain to verify.

Source-original export integration: the retained source receipt now binds the
onboarding operation and all six supporting original hashes. `export_logs`
includes `observational-source-originals.json` with the controller/protocol pair,
native and generic metadata, received-unit report, serial profile and boot policy.
Originals are deduplicated by digest, bounded to eight source receipts/600 KiB
unique raw bytes/900 KiB encoded output, and read only from fixed contained paths.
Missing or changed files fail export rather than omit evidence. Tests verify all
exported hashes and reject corruption. A public intake/setup/run/export sequence
also verifies that the production final-click compiler rejects synthetic USB IDs
before key lookup or dispatch; this is a rejection-path test, not a successful
native motion rehearsal or hardware qualification.

Source export checkpoint: 321 observational, action-catalog and arrival-service
regressions passed. Report:
`../runs/observational-source-export-20260913-01.xml`. No hardware was opened or moved
by the new export/sequence fixtures. Successful end-to-end rehearsal, rendered UI
verification and live qualification remain incomplete.

Renderer checkpoint: the observational run card now shows the relative increment,
speed/acceleration, selected USB identity, simple setup sequence and startup/cancel
warnings. An absent or invalid staged preview disables its form even if a malformed
view labels the action enabled. The older measured-profile card is explicitly
identified as a separate advanced workflow. 51 renderer/form regressions passed.
A fresh inspection-only local server loaded the real overview in the in-app
browser with camera and arm NOT CONNECTED. No device or motion actions were
executed; the server was then stopped. The arm-page visual inspection itself is
still pending; modeled DOM tests are not presented as screenshot verification.

Real-clock/read-only checkpoint: host preparation reached the incapable backend
at 1171 ms and completed the before-resume checks at 1765 ms after acceptance
(preparation alone: 484 ms). The actual source/file checks fit the current host
budget in this sample; native process launch and serial I/O were not exercised.
A separate read-only Windows metadata acquisition took 31 ms and reported the
expected `10c4:ea60` / `52E4E1E8337FEF119E92181CEDD322A4` interface on COM7 with
no missing native properties for that interface. Four unrelated interfaces had
missing properties. No serial port was opened and no command was sent.
See `../runs/observational-host-readiness-20260913-01.json`; it is a diagnostic
summary, not a reusable identity/clearance/admission receipt. Current supplied
power, operator presence, full movement clearance and live behavior remain unverified.

This is an approved requirements change, not a claim that the existing executor
already supports it. The current first-motion v1 request still requires measured
starting-angle/radius originals and uses a fixed **absolute** +1-degree target;
that is not a +1-degree relative move. Do not substitute invented measurements,
relabel telemetry as measured geometry, or disable its admission checks.

Implement an explicit observational commissioning profile alongside the old
measured profile. It should accept session setup confirmation and operator
outcomes without numeric measurement fields. Select a conservative target from
the current reported baseline only after validating command semantics, joint
limits and a visual sanity check of the starting pose. Inconsistent or suspect
baseline data must produce a diagnostic hold, not an assumed safe target.

Reuse identity binding, single-owner serial access, bounded execution, raw-log
retention and no-retry behavior. Simplify operator-facing reviews into setup,
preview, run, observation and result. Internal bookkeeping belongs in software,
not a request for the operator to assemble hashes or repeated review forms.

Test before live use: correct bounded target selection; invalid baseline; wrong
unit; timeout; no response; unexpected joint response; expected observation with
conflicting telemetry; successful functional response with unknown precision;
and export round-trip. No passing simulation may be recorded as a physical trial.

This policy supersedes mandatory precision measurement prerequisites for the
planned basic observational workflow, not the separate requirements for contact
calibration or the currently implemented measured-profile contract.
