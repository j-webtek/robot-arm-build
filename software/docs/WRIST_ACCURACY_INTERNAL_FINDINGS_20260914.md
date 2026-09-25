# Internal wrist accuracy findings

## Correction: reference midpoint asymmetry (2026-09-14)

Re-fetched the official `RoArm-M3_example_20260701.zip` and verified SHA-256
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
The earlier 2048 command-midpoint model and table below are superseded:
config line 94 sets the command midpoint to **2047**; module lines 364-370
add rounded radian counts to it; feedback lines 54-55 subtract pi (2048 counts).
The older directional-trace document correctly identified this asymmetry.

Correct reference predictions: 0 degrees -> register 2047 -> reported -0.087890625
degrees; +4 degrees -> 2093 -> +3.955078125 degrees; -4 degrees -> 2001 ->
-4.130859375 degrees. A measured +0.966796894-degree endpoint at commanded zero
is approximately **12 counts** above the reference prediction, not 11.
This still cannot be explained by rounding alone.

`wrist_accuracy_analysis.v2` corrects this offline model and separates rounding
error from total reference-feedback error. No motion commands, tolerances,
servo settings or retained original exports changed. Installed firmware remains
unverified; reference source is not evidence of the unit's actual deadband.
Regression: `software/runs/wrist-reference-midpoint-20260914.xml` (55 passed).

## Directional error versus software dispatch delay — 2026-09-14

Keep two distinct findings separate. Saved physical zero-from-above endpoints
repeat at +0.966796894 degrees, whereas the saved opposite approach ended at
-0.439453128 degrees. This supports a local approach-dependent discrepancy, not
a proven backlash/friction/deadband diagnosis. No new physical experiment has
validated the proposed -0.966796875-degree motor target for nominal zero.

The final-readback path is now integrated through runner, parent reconstruction,
native archive and v2 exports. All 409 selected correction tests passed in
93.76 seconds (fake device only). The instrumented real-clock rehearsal sent
zero fake commands: final evidence was 47 ms old at initial validation and aged
beyond the 100 ms gate during subsequent durable review/consumption. This is an
identified software timing cause for a withheld command, not the cause of the
previous physical directional miss. Next optimize redundant verification work,
then qualify timing before the one-command physical comparison. See the latest
implementation-plan section and `software/runs/wrist-correction-final-integration-regression-20260914.xml`.

## Wizard correction/controller matching — 2026-09-14

The wizard now matches a retained eligible correction assessment to a reviewed
controller, reloading all selected originals and checking unit identity. Changed
evidence, ineligible assessments and controller mismatch are refused. Current
connection and pose remain unverified; no motion authority is issued. 21 tests
passed (`software/runs/wrist-correction-controller-binding-20260914.xml`) using
synthetic evidence. No physical correction or accuracy measurements occurred.

## Wizard assessment of saved directional trials — 2026-09-14

Added a read-only wizard action to select saved absolute trials by operation ID,
reconstruct their original evidence and retain a correction hypothesis. It
neither accepts arbitrary offsets nor authorizes movement. Service execution
and log export were verified with synthetic files: 20 tests passed in 3.68
seconds (`software/runs/wrist-correction-saved-ui-20260914.xml`). No new physical
measurements were collected. Current-setup/final-review UI binding remains.

## Correction host coordinator and exports — 2026-09-14

Added reviewed host orchestration through preparation, one supervision call and
closed-roster exports. Original acceptance cannot be renewed after delay; changed
host state refuses preparation, and post-run cancellation does not erase logs.
Exports preserve byte/hash-addressed originals and explicitly list missing data.
20 tests passed (`software/runs/wrist-correction-coordinator-20260914.xml`) using
synthetic/fake execution. No physical correction was run. Browser integration
and attended UI validation remain pending.

## Correction runtime preparation — 2026-09-14

Added immutable runtime staging and signed-plan worker preparation. Prepared
fixture requests pass prelaunch and actual invocation checks; repeated attempts,
changed sources/runtime/plans and invalid timing are refused. 28 tests passed
in 8.11 seconds (`software/runs/wrist-correction-preparation-20260914.xml`).
No correction worker or arm movement was launched. Coordinator/wizard review
and export integration are still pending before physical bias experiments.

## Process-owner dispatch integration — 2026-09-14

Correction execution is connected to the shared contained owner with runtime,
prelaunch, external authorization and one-use checks. Parent retention/review
runs after cleanup; failed finalization cannot produce success. Fake-backend
tests covered child failure, refused authorization, retention failure and replay.
The combined correction/shared-owner regression passed 83 tests in 16.21 seconds
(`software/runs/wrist-correction-process-owner-20260914.xml`). No actual correction
child or device was launched. Physical wizard preparation remains incomplete.

## Parent retention/review ordering — 2026-09-14

Added a finalizer which retains process output before trying semantic review,
then retains a held or reconstructed verdict. Timeout, incomplete stdin and
uncertain cleanup cannot inherit successful stdout. 23 tests passed in 11.43
seconds (`software/runs/wrist-correction-finalization-20260914.xml`) using fake
arm execution and synthetic process receipts. No physical accuracy evidence
was collected; live process-owner integration remains pending.

## Parent failure evidence retention — 2026-09-14

Added bounded parent diagnostic originals for timeout/cleanup failures and
partial stdout/stderr, independent of a valid child outcome. Missing/unreadable
child files and explicit output truncation remain visible; no replay or endpoint
authority is produced. 25 tests passed in 14.82 seconds, recorded in
`software/runs/wrist-correction-parent-retention-20260914.xml`. This is synthetic
failure-retention testing, not a real worker timeout or arm test. Integration
into process-owner dispatch remains pending.

## Actual correction invocation checks — 2026-09-14

The isolated entry now has guarded execute-one handling, checking actual
process invocation and retained file bytes before signed prelaunch and admission.
Real isolated tests rejected empty/unpinned requests; no valid physical request
was executed. The process-owner dispatch route remains held. 36 tests passed
(`software/runs/wrist-correction-invocation-20260914.xml`). This is entry validation,
not a physical movement or directional-error correction result.

## Correction child orchestration — 2026-09-14

The fixed child now composes original/source checks, controller reconstruction,
one-use process claim, current USB metadata, correction admission and the claimed
trial runner. Tests reached an incapable execution stub and rejected replay or
changed originals before native access. Eight required metadata acquisitions are
supported without changing cumulative call/byte/deadline budgets.
78 tests passed (`software/runs/wrist-correction-child-composition-20260914.xml`).
No physical correction was sent. CLI execution and process-owner dispatch remain
disabled pending their guarded integration.

## Current source and reserved-entry checks — 2026-09-14

Added correction reference reconstruction and repeated prelaunch checks of
source/runtime, retained signed evidence, timing and existing claims. Existing
protected-key loading never provisions a replacement. 37 tests passed in
10.97 seconds (`software/runs/wrist-correction-prelaunch-20260914.xml`). Synthetic
test originals were labeled in the physical evidence domain solely to exercise
these checks; no physical provenance or new accuracy evidence is claimed.
Native correction execution remains unreleased.

## Correction runtime pin validation — 2026-09-14

Correction registration now checks exact executable/package/argument and
controller/protocol original pins plus full operation association. Tests reject
changed pins, budgets and domains. Format support remains separate from launch:
the process owner still rejects correction dispatch before backend creation.
34 tests passed (`software/runs/wrist-correction-registration-20260914.xml`).
No actual arm movement or new directional-accuracy evidence was collected.

## Isolated correction import verification — 2026-09-14

Correction runtime dependencies now form an explicit deterministic archive.
Actual isolated Python processes imported the runner and parent review with
native loader/network/subprocess access disabled during the audit. Altered
packages and incorrect flags were rejected; execution mode remains unavailable.
22 package/wizard tests passed, recorded in
`software/runs/wrist-correction-isolated-imports-20260914.xml`. This verifies
packaging, not live containment, arm operation or physical accuracy.

## Independent parent endpoint reconstruction — 2026-09-14

The parent review now reconstructs nominal-endpoint verification using original
captures and signed command evidence, and checks publication, lifecycle counters,
reservation PID and process timing. Both simulated settled and missed results
were rebuilt without additional writes. Rehashed child status/counter/capture
tampering was rejected. 34 tests passed in 20.10 seconds, recorded in
`software/runs/wrist-correction-parent-review-20260914.xml`.
No physical correction was sent; this establishes software reconstruction, not
independent tool-position accuracy or completed native launch integration.

## Bounded worker result reference — 2026-09-14

The correction worker can now encode a small hash-bound reference to its
retained outcome. Parent loading checks process records and exact original
bytes rather than accepting a child status label. Endpoint/containment remain
explicitly unverified at this stage. 44 tests passed, including a complete
fake-kernel trial roundtrip and changed-outcome rejection:
`software/runs/wrist-correction-result-reference-20260914.xml`.
No physical motion or new directional-error measurements occurred.

## Parent worker receipt verification — 2026-09-14

Correction process receipts now have an independent record verifier using the
parent-observed PID and start/finish interval. Child assertions alone are not
accepted. Missing consumption, changed operation/signature, impossible timing
and authority flags are rejected; late finish remains separately visible.
41 tests passed (`software/runs/wrist-correction-worker-receipt-20260914.xml`).
No physical correction was attempted. Record consistency is not evidence of
physical accuracy, process containment or successful cleanup.

## Claimed correction trial integration — 2026-09-14

Connected the process claim to the admitted serial facade and retained trial
runner. Integration exposed an object-identity mismatch from reconstructing the
request; composition now validates decoded content while preserving the original
admitted object. This was a software integration issue, not the physical arm's
directional error. Fake-kernel success and nominal-miss cases each write once,
capture telemetry, publish the nominal endpoint result and reject replay.

41 integration/claim/runner/wizard tests passed in 20.93 seconds; report:
`software/runs/wrist-correction-claimed-trial-20260914.xml`. No physical correction
was sent, and the measured physical bias remains unchanged/unresolved.

## Correction worker one-use association — 2026-09-14

Launch, process claim and consumption records now bind the entire correction
selection and revalidate its signed original evidence. Changed PID, operation,
source/runtime, stored evidence or expiry prevents consumption; a failed attempt
cannot be retried through the same claim. Competing claims yield one winner.
47 tests passed (`software/runs/wrist-correction-worker-claim-20260914.xml`).
This is software-only process-association progress, not physical motion or
accuracy evidence. Actual process containment and native correction release
remain unverified.

## Correction original-store integration — 2026-09-14

Added bounded staging/loading of the exact original trials and signed plan for
the correction worker. Generated filenames avoid caller-selected paths; the
assigned root must match the handoff. Hash verification and signature verification
remain distinct, and partial writes are not automatically repaired or replayed.
44 tests passed, including missing/corrupt/oversized originals, wrong keys and
partial staging. Evidence: `software/runs/wrist-correction-evidence-store-20260914.xml`.
This was disk/synthetic testing only, with no new physical accuracy evidence.

## Evidence-bound correction IPC — 2026-09-14

The new internal worker protocol binds the exact signed-plan bytes and ordered
original request/trial hashes into its operation identity, together with the
context and runtime registration. This closes a context-only association gap
before building the child launcher. Tests reject altered plans, reordered or
changed original bytes, command overrides and cross-worker requests. These are
integrity checks, not proof of physical origin or motor authorization.

39 protocol/owned-runner/wizard tests passed; see
`software/runs/wrist-correction-protocol-20260914.xml`. No actual arm access or
new physical accuracy measurement. Child containment and physical admission
remain incomplete.

## Correction outcome retention — 2026-09-14

Incomplete and interrupted internal correction trials now retain a canonical
original outcome with partial telemetry and cleanup/write-uncertainty evidence.
The receipt records bytes and SHA-256; failed retention explicitly changes the
top-level status to `OUTCOME_RETENTION_FAILED`. A catchable interruption is
re-raised after retaining evidence, never used as a reason to resend a command.
Hard-kill retention remains work for the containing worker/supervisor.

29 runner/publication/wizard tests passed, zero failures/errors, recorded in
`software/runs/wrist-correction-outcome-retention-20260914.xml`. No actual device
IO occurred. The directional-bias hypothesis and proposed compensation remain
unproven physically; the native correction runner is still internal, not a
released physical wizard action.

## Internal correction single-trial runner — 2026-09-14

Added `_run_wrist_correction_trial`: exact owned connection/permit checks,
baseline capture and signed binding, one write through the real permit/facade,
post-command capture, unconditional revoke/close, lifecycle/envelope retention
and nominal-endpoint publication when originals are complete. Incomplete/error
paths remain held with partial evidence; no automatic resend or return motion.

31 tests passed (`software/runs/wrist-correction-owned-trial-20260914.xml`): full
fake-kernel settled trial, nominal miss, cancellation before open, setup failure,
short write despite settled telemetry, uncertain write exception, publication
and facade regressions. No real device access. The runner is internal and not
registered with a physical worker or wizard route. Process ownership evidence
remains explicitly false pending source/runtime-contained worker integration.

Reconciliation timing correction: the owned write-call interval begins before
the facade's durable consumption. A valid claim can therefore occur inside that
interval, not necessarily before its start. Publication now requires baseline
end <= claim <= write-call end; actual consumption-before-WriteFile is enforced
by the native facade, not inferred from file timestamps. Claims after write end
still fail. This does not promote record consistency to native provenance.

## Correction connection/collector integration points — 2026-09-14

Added `wrist_correction_serial_connection.py`, reusing bounded owned handle
setup, read/write limits, cancellation completion and reverse-order cleanup.
The correction context exposes the fixed runtime budgets and start-time check.
Added `wrist_correction_capture.py`, a typed adapter to the production collector
and validator: 1-second baseline, 5-second post window, bounded read rate/size,
and no projection of cancelled/incomplete envelopes into a complete raw result.
Full collector envelopes must remain retained alongside projected raw evidence.

27 tests passed (`software/runs/wrist-correction-owner-capture-20260914.xml`):
fake open/read/exact write/post/cleanup, setup failures, late cancellation bytes,
no-baseline refusal, finite captures, cancelled/hash-mismatched capture rejection,
facade and wizard registration regressions. No actual DLL/device access.
The single-trial worker still needs to compose these adapters and retain every
failure path under source/runtime-bound process ownership before live release.

## Correction native boundary, fake kernel validated — 2026-09-14

Added `safety/wrist_correction_admission.py` and
`providers/windows/wrist_correction_serial_api.py`. Only exact correction request/
permit types can compose the facade. It reuses the existing owned-handle/event
and IO-token boundary, validates selected bytes, burns dispatch before WriteFile,
and permits at most one open/write attempt. Command binding now supplies exact
token-construction bytes separately from consumption and compares the consumed
command to that selection. The old facade cannot accept correction permits.

37 tests passed (`software/runs/wrist-correction-native-facade-20260914.xml`):
fake kernel exact correction once, substituted commands/no retry, repeated open,
stale/cancelled/changed context before syscall, no baseline, old-domain rejection,
unadmitted native-load refusal, binding and wizard regressions. No real device
opened or commanded. This facade is dormant and not registered for physical UI
execution. Owned connection/collector and source/runtime-bound worker lifecycle
still require integration before a live correction experiment.

## Durable correction command binding — 2026-09-14

Added a distinct open/baseline/consume state machine using the authenticated
current-context reader and original store. The opening reservation is durable
before any future native open; a crash/reconstruction cannot silently reuse it.
Selection preserves raw baseline/windows and exact bound review. Command bytes
are returned once only after durable consumption and a second current-context
check. Baseline receipt must remain within 100 ms at dispatch; no timing limit
was widened. Cancellation, process change, clock regression, changed plan/store
records and stale evidence fail closed. Native opening itself is not performed.

34 tests passed (`software/runs/wrist-correction-command-binding-20260914.xml`),
covering state order, repeat opening/dispatch, original-store restart, cancellation,
revocation, stale baseline, changed review, clock regression, competing consumers,
metadata and consumption regressions plus wizard registration. All synthetic.
Still required: disjoint native facade/permit, exact command/handle binding,
bounded worker capture/write/cleanup and physical-mode wizard composition.

## Correction Windows context adapter — 2026-09-14

`providers/windows/wrist_correction_current_context.py` adds a distinct immutable
context request and exact current-context types. Reuses existing reviewed
controller metadata resolution (no serial open), verifies source references,
unit and COM correlation, and rereads the fixed signed plan on each boundary
check. Host metadata must be current within 100 ms. This is not an atomic
association with an opened handle and does not prove physical identity/power.

34 tests passed in `software/runs/wrist-correction-current-context-20260914.xml`:
positive metadata correlation, stale/ambiguous/missing metadata, changed sources,
wrong port, altered plan and expiry, plus plan-binding/wizard regressions. All
metadata fixtures are synthetic. No device enumerated/opened by this test run.
`verify_plan` is now shared by the metadata reader and raw-baseline binding.
Owned native opening/dispatch and worker composition remain incomplete.

## Conditional plan-to-baseline binding — 2026-09-14

Added disjoint `seal_plan` and `bind_review_from_capture` stages to the correction
authority. The plan signs the fixed proposal before acquisition. Binding verifies
that original plan, operator time and context; validates every retained raw
baseline frame; recomputes the same correction at the accepted current pose;
then produces the existing exact-baseline review without extending its deadline
or refreshing operator confirmation. Plan signatures cannot be used directly as
dispatch reviews. Neither stage grants native opening/dispatch authority.

The production wizard rehearsal now exercises these stages before consumption
and retains `plan-review.json` alongside the bound review (eleven originals for
completed synthetic chains). 41 tests passed in
`software/runs/wrist-correction-plan-binding-20260914.xml`: tampered plan, stale/
corrupt/pre-review raw captures, wrong pose/basis, cross-stage rejection and full
wizard/service export compatibility. No hardware access. The separate owned
Windows context/serial adapter is still required before live correction.

## Full synthetic correction chain through wizard/export — 2026-09-14

`wrist_correction_pipeline_rehearsal.py` now connects the existing wizard action
to signed review, durable consumption, raw telemetry result review and exclusive
publication. Uses a deliberately public fixture key and synthetic clocks/USB
identity, never protected host keys. No physical open/write. Wrong approach and
stale baseline remain held before consumption. New run directories are under
`software/runs/wrist-correction-rehearsals`; originals are also embedded in the
wizard result for ordinary diagnostic export.

The initial full-chain result hit RESULT_RETENTION_LIMIT because originals were
large strings. Fixed by encoding bounded 4096-byte chunks; no retention threshold
was relaxed. 25 tests passed (`software/runs/wizard-correction-full-chain-20260914.xml`).
The public-service export test verifies every original's length/hash, reconstructs
the signed review and original-trial inputs from exported bytes alone, and
recomputes WRIST_EXCURSION against nominal zero. Failed endpoints remain failed.

This completes synthetic chaining, not native correction execution. The public
HTTP evidence from the preceding checkpoint predates this chaining change; the
new chain was tested via worker/service/export tests, not yet a new live HTTP run.
Owned native capture/dispatch and qualified live correction remain pending.

## Wizard correction rehearsal — 2026-09-14

New arm-section action: **Rehearse directional correction (no hardware)**.
`application/wrist_correction_rehearsal.py` generates two synthetic original
trials with the production bounded collector and runs the real correction
proposal/nominal-endpoint monitor. Browser inputs are a closed scenario enum;
no arbitrary command, native mode or path is accepted. The modeled bias is
0.87 degrees for testing; it is not the measured arm's calibrated offset.

All five scenarios ran through an actual local wizard HTTP prepare/execute
flow. CONSTANT_BIAS settled; BIAS_DISAPPEARS and OVERSHOOT retained
WRIST_EXCURSION; WRONG_APPROACH and STALE_BASELINE held before simulated motion.
The operation succeeds when its expected injected-fault outcome matches, not
because the endpoint necessarily passed. Exported reports preserve that distinction.

Verified export `wizard-20260914T102803608794Z-304acc2fd589423c963d474a6273255a`,
manifest `7d9be34aaee75c3c1f5093e66fd5e54bb673c3178747f5d59f850067001668e7`.
Nine dedicated worker/service/export tests passed; registered in the positional
suite. Rehearsal wizard closed afterward. No physical connection or command.
This action does not yet exercise the signed consumption/publication chain;
those have separate integration tests. Native owned worker and live correction
UI remain to be implemented and qualified.

## Correction durable-result publication — 2026-09-14

`application/wrist_correction_result_publication.py` now reconciles reconstructed
trial evidence with the exact attempt reservation and consumed claim from a
pinned store. It checks command/intent/bundle hashes, nominal endpoint and claim
timing; publishes raw trial bytes exclusively; rereads the records to detect
changes during publication; then publishes the derived result exclusively.
It does not authenticate a PID as a live owned worker, and explicitly leaves
physical execution and campaign advancement false.

38 tests passed (`software/runs/wrist-correction-publication-20260914.xml`):
consumption-to-publication success/miss paths, substituted claim/command/time,
missing reservation/claim, repeated publication, partial disk failure, raw
verification, consumption and wizard registration. All synthetic; no hardware
opened or commanded. A failed final publication preserves the raw trial and
requires review rather than overwriting/resuming the attempt.

## Correction raw-result review — 2026-09-14

Added `application/wrist_correction_result_review.py`. Reconstructs baseline
samples from bounded raw bytes/read windows, revalidates the signed review at
write time, matches exact transmitted command bytes, checks temporal ordering
and a complete five-second post window, then evaluates against nominal endpoint.
Post corruption/gaps and transport/cleanup failures cannot pass. Originals and
framing hashes are retained in the derived result; physical provenance, consumed
receipt and owned-process verification explicitly remain false.

71 combined correction and wizard tests passed in
`software/runs/wrist-correction-raw-review-20260914.xml`. New tests cover nominal
versus motor target, other-joint motion, short/uncertain writes, failed cleanup,
modified command/basis/duration, corrupt interior bytes and capture gaps. The
raw review suite is registered in the wizard's positional test action.
No hardware access. Remaining integration is the owned capture/command worker,
durable receipt association, result publication and correction-specific UI;
simulation evidence cannot release native motion or unattended campaigns.

## Durable correction consumption — 2026-09-14

Added `application/wrist_correction_consumption.py`, using existing exclusive
durable reservation publication. It snapshots supplied context/baseline, verifies
the signed review before reserving, checks retained record hashes and process/
clock continuity, persists a consumption claim before returning reviewed data,
then verifies again. Failure holds the object. Reconstructing the same attempt
in its original store fails rather than overwriting its reservation. A claim
written just before expiry remains consumed even though no receipt is returned.
The trusted coordinator must pin the store; moving/deleting it is not a supported
restart path. No native serial facade accepts this data receipt.

58 tests passed in `software/runs/wrist-correction-consumption-20260914.xml`,
covering correction analysis/preview/review, duplicate and interrupted attempts,
stale and regressing clocks, tampered reservation, revocation, publication failure,
post-publication expiry, concurrent consumers and wizard registration. Tests use
temporary stores and synthetic telemetry, with no hardware access.

Still needed: an owned-current-context adapter and raw baseline acquisition,
separate native permit/command admission, bounded worker lifecycle and result
reconstruction against nominal endpoint, plus correction-specific wizard controls
and exports. The review-consumption receipt is not evidence of movement or stop.

## Disjoint signed correction review — 2026-09-14

Added `safety/wrist_correction_review_authority.py` with a separate host-key
derivation domain. Sealing and verification rebuild the proposal/preview from
original trials and the exact baseline; bind nominal endpoint, motor command,
USB identity, source references, session/attempt, and operator checks; enforce
host baseline recency and the existing bounded review/start budget. No browser
key input, native adapter, runtime launch, key creation or physical command.

63 targeted tests passed (`software/runs/wrist-correction-review-20260914.xml`),
including modified target/hash rejection, changed context, stale baseline,
expired review, synthetic/physical mismatch, wrong key and cross-domain rejection
by the old absolute authority. Registered the new tests in the wizard suite.

This authenticates a coordinator's exact supplied review, NOT hardware truth.
It intentionally has no one-use consumption yet. Re-verification is read-only;
it must not be interpreted as a repeatable command permit. Native integration
must separately bind an owned fresh baseline, durable consumption, command byte
accounting, cleanup and nominal-endpoint reanalysis. No live correction occurred.

## Correction preview and verification simulation — 2026-09-14

Implemented `application/wrist_correction_preview.py`. It recomputes the proposal
from originals, verifies current USB context, validates every baseline row for
host recency/stability, requires the repeated experiment's starting pose, checks
approach direction, and caps corrected displacement to five degrees. It binds
the proposal and baseline hashes and keeps nominal endpoint separate from motor
command. This is a preview, not a signed native admission or hardware qualification.

The fixed five-second synthetic bias simulation uses the production reported
wrist endpoint monitor against nominal zero. Tests demonstrate that the bias
hypothesis can settle at nominal zero; settling at the adjusted motor target
instead fails; and an overshoot remains a fault after the position recovers.
The nominal excursion boundary was not widened to make compensation pass.
Stale/future timestamps, changed unit/joints, wrong-side starts, excessive command
displacement, and invalid synthetic values are rejected.

55 focused tests passed (`software/runs/wrist-correction-preview-20260914.xml`).
Both correction suites are registered in the wizard's closed positional test
list; executing the actual worker action ran **230 tests successfully**, with
zero device opens, serial writes, power events or movement commands. This was
the worker action, not a new HTTP/UI launch. The simple bias model is not a
validated robot dynamics model. Signed admission, owned native execution,
correction-specific wizard controls and a live experiment remain incomplete.

## Offline correction proposal implemented — 2026-09-14

`application/wrist_correction_proposal.py` now rebuilds endpoint traces from
2–8 original request/trial pairs. It rejects duplicate attempts, mixed evidence
bases, corrupt capture originals, changed USB unit, unmatched approach/target,
start differences over 0.5 degrees, other-joint context differences, short or
invalid settled tails, bias spread above one reference step, and offsets over
1.5 degrees. It retains request/trial hashes, supplied USB/source references,
and start contexts. These bindings do not authenticate the physical device.

Replayed the two actual zero-from-above originals (operations b9fae47... and
b77390c...) through this code: OFFLINE_EXPERIMENT_CANDIDATE, nominal target 0,
experimental motor target -0.966796875 degrees, reference register 2037,
downward approach, observed bias +0.966796894 degrees, zero observed spread.
The near-zero predicted residual is only the arithmetic consequence of the
constant-bias assumption, NOT a measured improvement or accuracy claim.

62 targeted tests passed (`software/runs/wrist-correction-proposal-20260914.xml`),
including new tests for provenance corruption, duplicate evidence, direction,
nominal/motor target separation, invalid traces and synthetic/physical mismatch.
No serial connection, native policy expansion, compensation write or movement
occurred in this implementation turn.

Still required before live correction: separate admission binding nominal and
motor targets; fresh-baseline/direction and command-delta checks; endpoint
verification against nominal zero; simulator tests for overshoot, stale context
and offset limits; wizard prepare/review/execute/export integration. Existing
absolute native allowlist remains unchanged. The current reported start near
+0.9668 is NOT the matched +3.7793 experiment start; do not reuse the proposal
as permission to send its candidate from the current pose.

## Repeatability and next correction experiment — 2026-09-14 10:09 UTC

Two new one-use live commands, joint 4, spd 20 / acc 1, unchanged 0.5-degree
arrival tolerance. Fresh USB identity and zero-write baseline before each;
no automatic retries, return, PID changes or compensation applied.

| Target / approach | Earlier endpoint | New endpoint | New result |
|---|---:|---:|---|
| +4 degrees from below | 3.779296882 | 3.779296882 | REPORTED_SETTLED |
| 0 degrees from +3.779296882 | 0.966796894 | 0.966796894 | TARGET_MISSED |

The +4 repeat started at -0.439453128, unlike the earlier +1.845703 start;
the zero repeat had the same reported start as its earlier comparator.
New +4 trial: `operation-af47174177144d1b9e4541a18aa85e3b`, 281 post samples,
220 constant-final reports over a conservative 3.922 seconds, error -0.220703118
degrees. New zero trial: `operation-b77390c8f95b4aa190770b904e407941`, 282 samples,
222 constant-final reports over 3.953 seconds, error +0.966796894 degrees.
Both had clean transport, no capture issues, no other-joint change or wrist
excursion detected. Zero miss ended testing, with last reported wrist +0.966797.

Both load tails repeated their earlier ranges: +4 tT -13..-9, final -13;
zero tT 49..53, final 53. Load is not calibrated torque. Changing load weakens
the entire-stream-frozen hypothesis but does not establish per-servo freshness.

### Causal interpretation

Repeatable, direction-dependent reported settling is now supported more strongly.
Command quantization cannot explain zero's +11-step residual (zero is exactly
representable). Merely waiting longer within the five-second window did not
resolve either residual. Servo deadband/static friction/load equilibrium are
plausible leading explanations, not experimentally isolated root causes.
Motor encoder reports alone cannot distinguish tool-side backlash or flex.
Do not claim physical accuracy or firmware freshness verified.

### Next implementation, before another corrective live test

1. Add an offline, provenance-bound correction proposal: original target,
   direction, repeated trial hashes, observed residual and quantized candidate.
   Keep nominal task target distinct from transmitted motor target.
2. For zero approached downward only, -11 reference steps (-0.966796875 degrees)
   is a candidate experiment under a constant-bias hypothesis, NOT an established
   calibration. Check exact quantization and model assumption explicitly.
3. Extend the separate bounded diagnostic policy and signed command admission
   deliberately; do not pass a new target through the existing {-4,0,+4} allowlist
   or loosen endpoint tolerance. Require a fresh baseline, same approach,
   reviewed start and existing movement bounds. No automatic correction loop.
4. Test proposal provenance, target/command separation, stale baseline rejection,
   direction mismatch, excessive offsets, quantization and overshoot fault stops
   in simulation before admitting one correction command.
5. Evaluate the resulting endpoint against NOMINAL ZERO, not the offset command.
   Retain misses unchanged. Compare against both repeated uncorrected trials.
6. Replicate any improvement before enabling direction-specific compensation;
   validate at other targets/load conditions separately. Do not generalize one
   wrist result to other joints or keyboard/phone tool positioning.

### Software fault fixed and evidence

Initial zero-write capture `operation-f79d79bc3ab24a1994934b97b512a8e0`
began mid-report at `:1.593806039,...`; only its first 106 bytes were a fragment.
The parser did not recognize attachment at a field colon. Added strictly bounded
first-line colon-tail recognition; retained original hashes/ranges, rejected
unknown/nonfinite/duplicate fields, and never filtered interior corruption.
The original held operation is unchanged; subsequent tests used fresh captures.
70 targeted tests passed: `software/runs/colon-boundary-accuracy-20260914.xml`.

Verified export receipts:
- +4: `wizard-20260914T100726730897Z-0c7e1ff6daf9446fadab2a7b6de6d4e8`,
  manifest `78a85bee0f32c22cbf4c9c6a9409225caf2cdd95bf64ce3f00e899e0b79a3cc2`.
- zero: `wizard-20260914T100901889908Z-5e87bcd655274776b6741c2be11110f6`,
  manifest `0e5a78cb06e50cae1f8c0e7bd54f941d325f82f55700ecb77c1185fd8ffaa311`.

Wizard processes closed after exports. No correction command has been sent.

## Matched zero-degree target — 2026-09-14 09:56 UTC

User-approved independent test from below completed as
`operation-e906bfd4c2434e8eb7dd06bb611662d4`. Fresh zero-write capture and native
identity correlation preceded a new exact admission; the earlier failed -4
positioning leg was not reclassified or resumed. One T101 joint-4 command to
0 rad, spd 20, acc 1; no return, retry or tuning change.

| Approach to 0 deg | Reported start | Reported final/error | Result |
|---|---:|---:|---|
| From above, earlier trial | +3.779297 deg | +0.966797 deg | TARGET_MISSED |
| From below, new trial | -3.251953 deg | -0.439453 deg | REPORTED_SETTLED |

Separation: approximately **1.406250 degrees / 16 reference servo steps**.
The zero-degree target has no reference quantization error in either case.
This supports approach-dependent behavior over a fixed target/rounding offset.
It is not an isolated causal experiment: start magnitudes, elapsed time and
unmeasured thermal/load conditions differ, and there is only one sample per side.

New trial: 280 complete post frames, no capture issues, no other-joint change,
clean serial/process shutdown and verified parent claim. Final value repeated
for 222 frames spanning a conservative 3.954 seconds; first-final read occurred
0.922–0.953 seconds after command completion. Load tT varied from -21 to -17
while position was constant. Error is about -5 reference steps.

The pass margin is only **0.060547 degrees** against the unchanged 0.5-degree
tolerance, less than one reference servo step. Do not call this robust accuracy
or release a preferred-direction policy after a single near-boundary pass.

Next experiment should measure repeatability of this same target/direction,
with separately reviewed bounded positioning moves and explicit failure holds.
Only then compare approach strategies or supported control tuning. Universal
offset compensation remains unsuitable because error changes sign by approach.
No new motion is authorized by this report.

## What the retained evidence establishes

Revalidated the three absolute trials against their original requests, capture
hashes, command bytes and acquisition envelopes. Compared them with the pinned
reference firmware conversion: 4096 steps/revolution, wrist midpoint 2048,
C++ round-to-nearest with ties away from zero. No device was opened or tuned.
Installed firmware equivalence is still unverified.

| Requested target | Reference goal register | Representable target | Reported final | Residual to representable target | Final-position tT range |
|---:|---:|---:|---:|---:|---:|
| +4 deg | 2094 | +4.042969 deg | +3.779297 deg | -3 steps / -0.263672 deg | -13 to -9 |
| 0 deg | 2048 | 0 deg | +0.966797 deg | +11 steps / +0.966797 deg | 49 to 53 |
| -4 deg | 2002 | -4.042969 deg | -3.251953 deg | +9 steps / +0.791016 deg | 41 to 45 |

Rounding alone cannot explain these errors under the reference model. Even a
perfect representable endpoint differs from the +/-4-degree request by only
0.042969 degrees. The firmware clamps none of these targets. The sign and units
of the observed movements are consistent with the requested radian commands.

Load changes while each final position repeats. In the reference getFeedback
routine both position and load are updated after successful feedback reads.
This weakens an explanation based on one completely frozen position/load cache.
It is not proof of sample freshness or installed-firmware behavior; buffering,
intermittent failures and other implementations remain possible. tT is not
calibrated torque and its sign alone does not establish gravity/friction.

## Ranked working hypotheses, not a root-cause claim

1. Servo control/deadband and load-dependent steady-state error, or mechanical
   hysteresis/friction. Fits stable residuals and direction-correlated load.
2. Installed-firmware behavior or intermittent stale feedback. Not excluded;
   per-servo acquisition success/age remains missing.
3. Simple conversion rounding, insufficient observation duration, or failed
   host transmission: poor explanations for the retained complete trials.

Targets and approach directions are confounded in the present small dataset.
No repeatability statistics or direction-only correction can be inferred.

## Accuracy improvement sequence

1. **Matched target before tuning.** Review a new standalone 0-degree test
   from below after a fresh all-joint baseline. The earlier -4 positioning
   attempt remains failed; do not resume its sequence or mark it accepted.
   If separately admitted, a positive approach to the same 0-degree target
   can discriminate direction/approach effects from fixed target error.
   Preserve one write, existing speed, tolerance and no automatic return/retry.
2. **Repeatability before offsets.** If the response is safe and consistent,
   plan separately admitted repetitions at the same target from both sides.
   Separate reported accuracy, spread and failure count. No universal offset
   from these three results; such an offset may worsen the opposite approach.
3. **Physical corroboration.** Use a fixed visual reference or calibrated vision
   to distinguish true tip position from servo encoder/firmware reports. Inspect
   linkage play/cable drag only with an appropriate supported/powered-down
   procedure; do not manually force a powered joint or release torque blindly.
4. **One parameter at a time.** Only after a reviewed supported control path,
   compare finite speed/acceleration cells and any applicable tuning. Preserve
   original settings and evaluate endpoints, not just visible movement. Do not
   alter PID, torque limits or EEPROM during ordinary movement tests.
5. **Task-level accuracy.** Once repeatable positioning is demonstrated, calibrate
   tip/tool offset, board frame and approach height. Keyboard/phone contact
   precision is not established by joint-angle endpoint tests alone.

No tolerance widening, corrective overshoot, repeated convergence commands,
PID update or native campaign release is implemented by this analysis.

## Software

`application/wrist_accuracy_analysis.py` validates original trials and computes
reference goal quantization, residual steps and load variation during the final
constant-position tail. New absolute-wrist reports include `accuracy_diagnostic`.
Unknown load remains null; corrupt or uncertain evidence cannot produce a
reference accuracy comparison. The reference source hash is included, and
installed-firmware/compensation claims stay false.

Reference source:
[Waveshare example archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip),
SHA-256 `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`;
`RoArm-M3_module.h` lines 35–38, 54–55, 364–372.
# Correction runtime wizard setup — 2026-09-14

Composed endpoint update: HTTP tests now traverse real child admission/capture
and parent reconstruction with a fake kernel and virtual clock. The synthetic
nominal endpoint passes; an incorrect endpoint is held as `WRIST_EXCURSION`.
One fake write per attempt and complete byte-verified exports are asserted.
26 tests passed in 37.97 seconds (`wrist-correction-http-endpoints-20260914.xml`).
No physical improvement or native process/timing qualification is established.

HTTP integration update: real signing/preparation exposed a tuple/list boundary
bug in the wizard's retained-originals handoff. Fixed with a local list copy,
preserving the immutable retained binding and exact evidence. Actual loopback
HTTP timeout/cancellation tests now reach an incapable owner and retain/verifiably
export failure originals. 31 regression tests passed in 45.48 seconds; report
`wrist-correction-http-integration-20260914.xml`. No hardware IO or physical
accuracy claim. Successful synthetic-child integration remains next.

Subsequent update: final-review and one-use run wiring now exists, including
separate setup/execution IDs and explicit nominal versus experimental target
display. 46 tests passed (`wrist-correction-wizard-run-20260914.xml`); service
dispatch used a fake coordinator and UI checks used a pure-DOM harness. No
physical correction was sent. Full nonhardware integration rehearsal is next.

The wizard can now stage a pinned correction runtime from a revalidated matched
assessment. It rechecks originals before and after staging, clears old setup on
failed replacement, and exports the setup receipt through standard logs.
29 targeted tests passed (`wrist-correction-wizard-runtime-20260914.xml`), using
synthetic evidence and no hardware. Final-review/run-action binding remains;
no correction command was sent and no physical accuracy improvement is claimed.
