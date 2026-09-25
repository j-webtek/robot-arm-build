# Practical path to reliable typing and phone tapping

Date: 2026-09-17  
Status: operator-confirmed movement, scoped local wrist-cycle evidence and one successful held-out local increasing-elbow correction trial. Qualify reverse elbow behavior and repeatability next; coordinated control remains unqualified and native T104 held. Camera deferred.  
Purpose: turn the working movement foundation into a usable application without
making perfect joint positioning a prerequisite for progress.

## Start here — practical execution order

### Current checkpoint and next actions

Updated priority: implement
[command-to-servo diagnostics](COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md) before further
reverse-motion trials. Verify supported readback/fresh acquisition, build the
contract and simulated cases, and integrate wizard reporting/exports. Video is
optional, not a blocker for this software work. Firmware deployment is a separate
reviewed decision. This priority supersedes the historical checkpoints below.

21:31 UTC update: the separately screened uncorrected elbow return produced no
reported movement (29 trial samples plus 113 read-only follow-up samples over
35 seconds). Failure and observation exports are retained in the current goal
document. Reverse behavior needs diagnosis and a separately reviewed identification
range before repeatability tests; no automatic larger command or historical
reverse offset is authorized by the forward success. This supersedes the next
action in the 21:27 checkpoint below.

21:27 UTC update: 52 focused tests passed; one frozen increasing-elbow candidate
trial passed reported endpoint/settling checks and export verification, with
0.451096 mm modeled desired-tip error. No retry or return was sent. Next qualify
reverse behavior independently and establish finite repeatability. This supersedes
the pending candidate-integration/trial wording below; see the current goal's
timestamped checkpoint for the exact live export. No measured physical accuracy
claim follows from this model-based result.

This checkpoint supersedes historical "next" instructions later in this document.
The current execution order is maintained in
[CURRENT_TYPING_AND_TAPPING_GOAL.md](CURRENT_TYPING_AND_TAPPING_GOAL.md).
The operator has now confirmed visible movement in the latest demonstration.
Endpoint accuracy remains a separate test; link that observation to a trial only
if command/export records establish the association. Diagnostic packaging repair,
the elbow evidence bundle and local wrist-cycle tests are already completed.
Do not repeat those merely because older checkpoints describe them as pending.

Next finish and test the frozen local increasing-elbow correction's runner
integration, including exact start/payload binding and separate desired/wire
endpoint scoring. Then attempt one prospective trial from a fresh matching start,
export its result, and independently qualify return behavior before finite paired
cycles. Earlier T102 attempts do not qualify coordinated control. Keep native T104
held and do not deploy the prospectively failed affine model. Qualify remaining
press-relevant joint demands before coordinated noncontact approach/press/retract,
one ghost key and a short adjacent-key sequence. The refreshed execution order,
six working phases and completion gates are in the
current goal document linked above. Each leg requires its own endpoint check and
reproducible export before progression. Preserve earlier failures; do not reopen
blind speed/amplitude escalation or transfer posture-specific corrections outside
their validated range. Set practical task tolerances before testing, rather than
seeking perfect residuals or changing criteria after failure.
Camera, physical contact and measured tip accuracy remain deferred. Transport
agreement alone is not encoder-freshness evidence.

#### Historical checkpoints

USB restored (18:52 UTC): expected CP210x unit is back on COM7 and public wizard
native metadata correlation passed. Export
`wizard-20260917T185219832056Z-db55d7a8f18947f9903adf317ad0c36a` verified.
No port opened yet. Next use the existing bounded zero-write powered telemetry
capture and compare with HTTP feedback. Missing-USB notes below are historical.

Latest interface inspection (18:45 UTC): the served page explicitly expects HTTP
T105 telemetry, so our transport matches its UI. No version obtained; getDevInfo
returns 404. Only Bluetooth serial ports are enumerated, no arm USB serial port.
Next obtain a USB data connection for independent feedback comparison, reviewing
reset behavior before opening serial. No motion or configuration change made.

Current read-only finding (18:43 UTC): all 31 last-trial packets were identical;
torque-state/voltage are missing. The observed HTTP telemetry interface differs
from the pinned source's HTTP-ok/WebSocket-telemetry implementation. Next identify
installed interface/version clues without motion or configuration writes.
Detailed evidence is in TIP_REVERSE_FIRMWARE_DIAGNOSIS.md.

Latest result (18:41 UTC): the separate T101 elbow-only comparison also failed
arrival, with no reported joint movement across 31 observations and no runner
error. Explicit 20/1 settings did not resolve the discrepancy. No retry/return.
Next inspect retained servo fields and available read-only diagnostics; do not
increase commands to force movement or resume a ghost sequence.

Source review is now recorded in [TIP_REVERSE_FIRMWARE_DIAGNOSIS.md](TIP_REVERSE_FIRMWARE_DIAGNOSIS.md).
No reference elbow sign reversal was found. T104 uses history-dependent shared
servo settings; T101 uses explicit speed/acceleration. Installed behavior remains
unknown. Next prepare one separate elbow-only T101 diagnostic at the current
posture, with path screening and no reuse of earlier posture-specific offsets.
No firmware/register changes or movement were made during the source review.

Read-only update (18:36 UTC): command reservation/payload hash and reference IK
agree. Elbow remains 10 predicted counts from target; wrist count matches.
Fresh feedback matches the prior final pose. No movement. Next review firmware
paths and isolated elbow evidence; host audit does not prove actual bus targets
or physical cause. See current goal for verified audit/read-only exports.

Latest live checkpoint (18:34 UTC): upward diagnostic failed at 5.069348 mm and
reported an opposite-sign elbow response (requested -.721856 degrees, reported
+.175781). Thirty samples, no runner error. Further motion stopped; next is
read-only diagnosis, not another offset or automatic return. Live evidence:
`wizard-20260917T183418258680Z-39080a782e1d4bfdb5273d6b85bd4d9d`.

Current next action (18:32 UTC): separately qualify a bounded upward diagnostic.
Two-tip-trial comparison shows changing elbow/wrist offsets; repeatability is
not established. The new 2 mm-up controller reference passes offline, with no
descending compensation applied. No hardware movement occurred in this step.
Freeze/screen a single upward command before live testing, then use the evidence
to design fixed-endpoint paired trials. Details and exports are in the current
goal document.

Latest live result (18:30 UTC): the frozen tip correction was tested once on its
held-out goal. Desired residual 1.060005 mm, outside .5 mm; 30 samples and no
runner error. No return or replay. Export
`wizard-20260917T183047269334Z-94f355c5112a48cfae9ac624121a1637`.
Next compare the two tip trials and choose a bounded identification strategy,
including reverse-direction qualification, rather than repeatedly descending
and fitting a new offset to each changed pose. Physical typing remains pending.

Current next action (18:28 UTC): validate the exported local tip correction on
its new held-out target, using fresh matching feedback and separate desired/wire
verdicts. The offline corrected path passed; maximum hypothetical wire-tip sweep
2.865 mm and maximum joint excursion 1.479 degrees. Thirty-one focused tests pass.
This is not yet a live success. See CURRENT_TYPING_AND_TAPPING_GOAL.md for the
candidate hash, export and source plateau evidence.

Latest live result (18:26 UTC): the first direct local 2 mm hypothetical press
was sent and recorded, but failed endpoint verification (3.590 mm controller
residual; 30 feedback samples; no runner error). Elbow overshoot and wrist
undershoot remain significant in coordinated motion. No return/retry followed.
Next analyze and validate a bounded coordinated correction; the ideal simulation
is not evidence that this physical command reached its desired endpoint.
Evidence: `wizard-20260917T182619277841Z-90592a21fcd14c78be0a319d0bdc6038`.

The active six-step execution plan and rewritten goal are in
[CURRENT_TYPING_AND_TAPPING_GOAL.md](CURRENT_TYPING_AND_TAPPING_GOAL.md).
The latest operator confirmation establishes visible motion, not measured tip
accuracy. Next finish testing/exporting the offline coordinated 2 mm tip-cycle
preview, qualify individual live legs, combine a finite local cycle, and only
then connect the separately screened approach to the saved ghost keyboard.
Local preview now passed offline (18 focused tests): 2 mm depth, less than .001 mm
numerical lateral drift, maximum .784 degree joint excursion. Verified export:
`wizard-20260917T182200103616Z-12d8c587c8af479c900409f0481f81f0`.
This is a linear-joint model reference, not firmware-path or physical accuracy
validation. The subsequent eight-leg T104 reference screen also passed; export
`wizard-20260917T182339455535Z-be6764567ff04c50a55c22152b11366a`.
Next integrate one named bounded leg with fresh-pose admission and native endpoint
verification; the whole reference route is not authorized for dispatch.
Do not repeat larger
demonstration moves merely to reconfirm movement. This documentation update sends
no hardware commands. The older checkpoints below are historical evidence, not
an executable queue.

Hypothetical stylus review: wrist cycle gives 2.27 mm vertical / 1.68 mm lateral
travel, not a straight press. The saved route begins at PARK, not the first key
hover; current modeled distances are 167.44 mm to PARK and 248.12 mm to A HOVER.
Next screen coordinated tip-space motion and approach separately. No camera,
board registration or physical contact was introduced by this review.

The automatic two-leg wrist cycle now passed and reproduced the manually reviewed
pair. Verified per-leg exports, exact candidate/command checks, fresh continuity
and fault/cancellation stops are in place. Next review the modeled stylus arc
against ghost-key geometry; this is not yet task-space approach or physical typing.

The first local shared-endpoint wrist out-and-back passed both legs: down .351116
modeled mm error, up exact reported high angle. No runner errors or other-joint
changes. Next compose and repeat the finite pair with verified per-leg exports;
the full ghost keyboard approach and task-space press/retract remain incomplete.

Ascending correction passed at .489892 modeled mm and a later read-only check
confirmed the same endpoint. Together with descending successes, this supports
testing a finite shared-endpoint pair next—not claiming that cycle already works.
Keep the narrow ascending margin visible; do not relax the .5 mm threshold.

Ascending wrist response is now measured separately: +1.5 degrees requested,
+1.230469 reported, .810134 modeled mm miss. Next validate a separate ascending
correction, not the descending offset. Both directions must be qualified before
automatic paired progression; the diagnostic's failed endpoint remains failed.

The fixed-posture descending wrist correction passed two new endpoints using the
unchanged residual: both desired errors .108677 modeled mm, four observations,
no runner errors, other joints unchanged. Next characterize the reverse direction
separately, then a finite noncontact paired cycle. This local T101 result does not
qualify T104 compensation, full keyboard approach or physical tip accuracy.

The post-coordinated T101 wrist-only test also undershot (-1.5 degrees requested,
-.527344 reported), with unchanged other joints and no feedback failures. Pinned
source inspection confirms a terminal T104 write and feedback-updated last pose.
Next qualify a small local wrist-only correction at this fixed shoulder/elbow
posture; do not attribute the problem solely to T104 or resume the rejected hybrid.

The proposed hybrid is NOT admitted: 2,010 sampled local approach targets yielded
no command pair inside both fitted training ranges. Better single-joint prediction
does not ensure a usable combined inverse. Next isolate wrist response and review
T104 interpolation versus single-joint commands before selecting another model.
Do not keep walking the approach simply to collect more drifting-posture fits.

Offline holdout comparison now favors an affine movement model for elbow and a
proportional movement model for wrist over the averaged-offset alternative.
Next screen a separate hybrid candidate and validate it on new evidence; three
changed-posture trials do not qualify a general model. See the current goal
document's 17:50 checkpoint and the linked experiment history for numeric results.

Coordinated v2 achieved a 0.881280 modeled mm desired residual on its held-out
target, still outside the unchanged .5 mm band. Elbow desired error .064338 degrees,
wrist .201745 degrees. Native deadline admission worked without a transport error.
Next focus on wrist residual/delta dependence rather than indiscriminately adding
the same correction to both joints. No ghost route progression is yet qualified.

Feedback scheduling now avoids starting a native read without its normal I/O
budget remaining; endpoint deadline failures stay failures and real transport
faults remain visible. Cross-trial review shows elbow/wrist wire bias both changed
by about +0.195 degrees across different operating points. Next screen a separately
versioned correction using the latest local bias, with held-out validation; do not
claim a global fit or same-start repeatability from these two traces.

The frozen coordinated offset candidate has now been tested on a new 5 mm desired
segment: 1.725 modeled mm desired miss, approximately +0.195 degrees each at elbow
and wrist. It did not pass and a late feedback request timed out. No next motion
followed. Next review cross-trial residuals and transport deadline handling before
selecting a revised bounded correction; do not promote the additive model globally.

The post-wrist 5 mm coordinated diagnostic now has complete telemetry (32 samples,
no feedback failures) but failed endpoint verification at 3.695 modeled mm.
Elbow overshoot and wrist undershoot dominate; reports plateaued by 0.467 seconds.
Next use this new-posture evidence to design a bounded direction-specific
correction/validation experiment, not longer timeouts or continued route dispatch.

Clean wrist desired-endpoint termination is now implemented and physically tested:
the new v2 trial finished COMPENSATED_REPORTED_ENDPOINT_VERIFIED, five samples,
no runner error, 0.401277 modeled mm desired residual. Wire-target verification
remains false. Next qualify a bounded coordinated segment from fresh current
posture; no whole-route dispatch or transfer of old elbow scope is authorized.

The active execution sequence and rewritten goal are now in
[CURRENT_TYPING_AND_TAPPING_GOAL.md](CURRENT_TYPING_AND_TAPPING_GOAL.md).
The user's visual confirmation establishes observed motion, not measured tip
accuracy or a pass for every historical trial. Do not send larger demonstration
moves merely to reconfirm that movement is possible. Older checkpoints below are
an experiment history, not a queue of commands to execute.

The extended-start wrist trial reproduced the same desired endpoint (0.401 modeled
mm error) from a second start. Its later diagnostic transport error still prohibits
automatic progression. Next add clean desired-arrival termination for the qualified
wrist candidate, preserving fault stops, before testing coupled corrections.

Wrist preparation reported 0.01994175 rad rather than 0.026077673 and remains a
failed endpoint. No correction was chained. Next evaluate an explicit start-range
extension for the unchanged descending wrist candidate, preserving v1 and all
accuracy tolerances; avoid repeated positioning attempts to force the old start.

The first local wrist correction passed its held-out desired endpoint at 0.401
modeled mm error, with no runner error and other joints unchanged. Preserve the
separate wire timeout verdict. Next qualify a separately screened preparation and
repeat the frozen wrist correction before combining it with elbow compensation.

Isolated wrist test reproduced a -1.5 degree request as -0.703 degree reported
movement with other joints unchanged and no feedback failures. Next freeze and
validate a local wrist correction at this posture; preserve the failed endpoint
verdict and do not replay the old probe from its now-out-of-scope starting angle.

Coordinated-trace analysis shows the modeled 6.11 mm miss was mostly vertical and
reported joints had already plateaued for 5.85 seconds before the feedback timeout.
Both elbow and wrist residuals contribute. Next isolate wrist pitch at the current
posture rather than extending timeout or applying the old elbow-only correction.

The first coordinated 5 mm ghost-approach trial was sent once and did not verify:
retained error 6.11 modeled mm, then a feedback-request timeout. Read-only recovery
succeeded at the same reported final pose; no retry/return occurred. Follow
[FIRST_COORDINATED_GHOST_STEP.md](FIRST_COORDINATED_GHOST_STEP.md) to analyze
multi-joint response and transport timing before another bounded diagnostic.

Approach review now includes provisional joint limits and hypothetical 100 mm tool
sweep. Full descent remains offline: it changes shoulder/wrist substantially and
ends near an unregistered model base plane. Next qualify only the first approximately
5 mm coordinated segment from fresh pose; retain all other route legs as simulation.

Two native local cycles now passed with identical reported final endpoints. An
offline approach from fresh saved pose to the full-size ghost route passed 39/39
reference legs (192.84 mm total), with no live approach sent. Next inspect joint/tool
sweep and qualify the first bounded coordinated leg; do not extrapolate the local
elbow correction or dispatch the whole route from this model-only pass.

The first native automatic two-leg local cycle passed with clean feedback and
verified per-leg exports: desired modeled errors 0.298 / 0.288 mm, about 2.1 seconds
per leg. Next assess bounded repeats, then bridge to a separately screened coordinated
ghost approach/press/retract route. This is not yet keyboard-coordinate typing.

The one-use two-leg coordinator is implemented with export-before-progression and
fault-stop tests. Native transport ownership, fresh-pose continuity admission and
the verified-export adapter remain next; no physical cycle has run yet. Preserve
the tested non-elbow posture when binding the native adapter.

Clean compensated completion is implemented and tested for the two local modes.
It stops at verified desired arrival and preserves the separate wire result;
historical timeout/transport-error outcomes cannot advance a cycle. Next implement
the finite coordinator and export-before-next-leg fault tests, then validate native
cycling. No physical movement occurred during this software checkpoint.

The descending lookup passed its unchanged held-out repeat, reaching exactly the
same reported endpoint (0.196 modeled mm error). Ascending preparation also passed
again (0.298 modeled mm). Next implement and fault-test explicitly bound desired-
endpoint progression for a finite two-leg local cycle; preserve strict wire verdicts
and do not treat arbitrary timeouts as success. Then validate that cycle physically.

The fixed-start mapping sample passed the intended reported endpoint at 0.196
model-derived mm error. The map shows a plateau followed by a monotonic response.
Next repeat this useful lookup point unchanged on new evidence, then qualify the
local bidirectional pair and desired-target progression before ghost task routes.
Do not keep optimizing away an already acceptable local residual.

Offline response-map review now separates unlike starting poses: only the two
same-start descending validations establish the observed plateau. Follow
[ELBOW_RESPONSE_MAP_EXPERIMENT.md](ELBOW_RESPONSE_MAP_EXPERIMENT.md) for the next
single fixed-start mapping sample; do not pool different starts into an offset fit.

Descending v2 did not improve v1: a different command from the same baseline
reached the same reported endpoint, still 0.773 modeled mm from desired. Next
characterize a small command-to-endpoint response map rather than repeatedly
retuning an additive offset. Both failed verdicts remain intact; ascending results
remain useful. See the experiment log's 16:47 checkpoint for evidence and scope.

First descending correction trial finished with 0.773 model-derived mm desired
error, outside the unchanged 0.5 mm acceptance band. No retry followed. Next assess
a separately versioned descending estimate from the retained operating points and
validate it on new trials. Ascending results remain intact; bidirectional task
execution is not yet qualified. Detailed evidence is in the finite experiment log.

Nearby-target validation is now complete: the unchanged ascending offset passed
at a second desired endpoint (0.298 model-derived mm residual). Three held-out
ascending trials cover two targets. Next qualify a separate descending correction
from the retained lifting evidence, then evaluate bidirectional noncontact cycles.
Do not extend these results to physical tip accuracy or arbitrary joint poses.

The separately versioned extension has now completed: two held-out ascending
correction trials from different starts reached the same reported final angle,
with desired residual -0.01172 degrees / 0.06463 model-derived mm. No physical tip
accuracy claim follows. Next qualify a nearby different desired endpoint and then
the descending direction before coordinated press/retract; see the experiment log.
The earlier out-of-range rejection below is retained as history, not a current block.

Repeat preparation landed at 1.523242922 rad, just outside the frozen candidate's
starting range. The subsequent read-only preflight rejected validation; no second
candidate command was sent. Next evaluate a separately versioned, narrowly extended
start-range experiment with the offset and accuracy tolerances unchanged, as
specified in the finite experiment log. Do not silently widen the original candidate.

The first frozen local correction has now completed one held-out live trial:
desired reported endpoint verified, angular residual -0.01172 degrees and
model-derived position residual 0.06463 mm. The strict transmitted-target verdict
remains failed and is separately retained. This is preliminary local improvement,
not physical tip accuracy or repeatability qualification. Next collect independent
repeat evidence with the candidate unchanged; details and exports are in
[the finite experiment](ELBOW_LOCAL_VALIDATION_EXPERIMENT.md).

The user has confirmed seeing the elbow move. Do not repeat visibility tests merely
to establish that motion is possible. Endpoint accuracy remains a separate,
incomplete qualification: the three -5-degree trials reported approximately
-1.93, -2.02 and -2.11 degrees; the +3-degree trial reported +3.52 degrees.
These are controller-reported angles, not independently measured tip positions.

1. Completed: 38 focused regression tests, fresh preflight and one held-out local
   validation trial. Preserve these as the baseline for repeat validation.
2. Follow [the finite local experiment](ELBOW_LOCAL_VALIDATION_EXPERIMENT.md):
   acquire a fresh baseline, screen the path, and test one frozen, direction- and
   range-specific candidate. Record desired target, actual transmitted target,
   reported trajectory, final residual, settling evidence and configuration identity.
   Preserve separate wire-target and desired-target verdicts. No global offset.
3. Review each result before another movement. Use held-out repeat trials to assess
   repeatability and improvement over the uncorrected baseline. Expand direction,
   range or joint coverage one factor at a time only when the local evidence supports
   it. Do not optimize indefinitely for zero residual or silently widen tolerances.
4. Once the tested corridor supports the next task, screen the approach from the
   current pose to one ghost key. Execute noncontact approach, virtual press and
   retract, then a short A–S–D sequence with per-leg verification and exports.
   Keep the full-size keyboard model and hypothetical 100 mm tool offset explicit.
5. Defer camera registration and physical contact until the supports/tool are built.
   Then measure the mounted tip transform and validate actual key/tap events.

Progress criteria: reproducible evidence, a bounded tested operating range and
successful noncontact task progression—not a claim of millimetre physical accuracy
from encoder feedback alone. Stop on missing/inconsistent feedback or unexpected
motion; do not automatically replay failed moves. An independently reviewed trial
may begin from a fresh stable reported pose without relabeling the prior failure.

### Active goal and autonomy (updated 2026-09-17)

Implement this practical path through reliable physical keyboard typing and
Android tapping. Preserve the completed full-size A–S–D interpolation screening,
automated endpoint rehearsal, fault-stop tests and reproducible exports as the
regression baseline. Physical elbow movement is now visually confirmed on the
side-view test, consistent with reported movement. The immediate priority is to
characterize and reduce the remaining undershoot: two -5-degree requests produced
about -1.93 and -2.02 degrees of reported movement, not verified arrival. Analyze
saved time-series evidence first to distinguish ongoing travel, settling and
stable shortfall. Use bounded experiments to select and validate a practical
timing, command or compensation adjustment; do not assume a fixed 3-degree offset
or extrapolate from two trials. After repeatable endpoint performance is adequate
for the next noncontact task, validate an approach from the current live pose,
then progress to physical noncontact press cycles and short ghost sequences.
Use the selected OASO stylus as the build reference; retain the 100 mm offset as
hypothetical until the mounted tool transform is measured. Defer camera work until
its support is ready. Later qualify real keyboard and phone input events.

Treat the user's confirmation of connected power/systems and a secured, clear
setup as the standing operating assumption unless contradicted by new evidence.
Work autonomously on software, simulation, analysis and incremental qualified
tests without routine permission prompts. Check connectivity and current pose
programmatically before live trials; a standing assumption is not live telemetry.
Stop progression on missing, inconsistent or out-of-bounds feedback, unexpected
motion, or a task-specific unresolved physical discrepancy. Do not automatically
retry uncertain motion, increase torque, or bypass existing execution guards.
Ask only for a material missing observation, physical adjustment or decision that
cannot be obtained internally. Continue useful offline work when live work waits.

Success is reproducible command-to-endpoint verification and ultimately confirmed
key/tap events, not perfect model residuals. Keep synthetic results, controller-
derived tip estimates and independently observed physical results distinct.

### Immediate milestones — authoritative next-work order

Milestones 1–2 below are completed for the selected route, not outstanding work.
The active task is milestone 3, detailed in the characterization sequence immediately
below. The later physical and contact milestones remain incomplete.

1. **Interpolation screening:** check all 55 projected A–S–D legs using the pinned
   controller reference, not endpoints alone. Export failures and assumptions;
   passing the reference model does not establish installed firmware equivalence.
2. **Endpoint rehearsal:** run the screened route through the existing non-hardware
   endpoint runner using bounded per-leg subplans. Test normal completion and
   representative feedback faults; verify stop-before-next-leg behavior. Preserve
   route identity, per-key phase mapping and existing export size limits.
3. **Live endpoint characterization:** physical movement is confirmed. Analyze
   the repeatable undershoot, test a justified adjustment, and verify held-out
   endpoints before expanding routes. Arrival remains unverified.
4. **Physical ghost typing:** validate the current-pose approach separately, then
   one virtual press/retract, repeats, and a short sequence with per-leg feedback.
   No camera, physical keyboard or mounted stylus is required for this stage.
5. **Actual contact later:** calibrate the installed stylus transform, confirm
   robot-held capacitive operation, and validate real input events before expanding
   tasks. Add camera registration once its hardware is ready.

Completion of milestones 1–2 means simulation is evaluable, not that physical
accuracy or actual key actuation has been established. The checkpoints below are
historical evidence; this ordered list supersedes their older next-step wording.

### Elbow endpoint characterization — active priority

Finite local-validation experiment now documented in
[ELBOW_LOCAL_VALIDATION_EXPERIMENT.md](ELBOW_LOCAL_VALIDATION_EXPERIMENT.md).
One conditioning lift reported -2.1094 degrees for -5 requested, consistent with
earlier lifting shortfall, and failed strict endpoint verification. No command
was chained afterward. Next review its trace and a fresh baseline before admitting
any independent local-correction validation; preserve both wire-target and desired-
endpoint error. The candidate is not enabled globally or validated yet.

Matched-target design correction: simply resending the last reverse target from
its overshot final pose is not an independent opposite-side trial. A read-only
preflight was retained, but no command was sent and that temporary native mode
was removed. Next design explicit conditioning and measurement legs with adequate
approach distance, separate roles and separately screened paths. Do not chain into
measurement automatically after an unverified conditioning result or interpret a same-goal retry
as directional evidence. See the elbow review's 16:23 checkpoint.

Opposite-direction comparison completed: +3 degrees requested at unchanged
speed/acceleration yielded +3.5156 degrees reported (0.5156-degree overshoot),
versus the lifting trials' approximately 3-degree shortfall. Endpoint residual
2.8439 mm still fails existing arrival criteria. No tolerance was widened.
Next use a matched-target comparison within the existing corridor to separate
approach effects before fitting a local correction. Details and exports are in
the elbow review; no universal model or physical tip accuracy is established.

Completed trace analysis: last reported changes occurred at 0.906/0.609 seconds
after dispatch, followed by 8.918/9.099 seconds of unchanged elbow readings.
Shortfalls were 3.0664/2.9785 degrees. Thus a longer timeout is not presently the
evidence-backed primary remedy. Next construct/screen one opposite-direction
comparison at unchanged speed within the recent tested joint interval, preserving
one-send verification; do not fit or apply a universal offset yet. Detailed
analysis and export are in the elbow review. No hardware moved during analysis.

Latest evidence: side-view trial
`wizard-20260917T161418612421Z-8ee31488c2074a1aa540575121c14c54`.
The user explicitly confirmed seeing the movement. Requested -5 degrees; reported
-2.0215 degrees. The preceding trial reported -1.9336 degrees for -5 requested.
Both timed out outside their endpoint acceptance bands. Physical response is
established, not precise tip position, full requested travel, or a universal model.

1. Analyze the two retained traces: command/receipt times, distinct feedback values,
   joint change over time, last-change time, final-window drift and residual.
   Separate host observation timing from unknown underlying servo acquisition
   timing. Do not infer settling solely from repeated identical cached payloads.
2. Select the smallest useful discriminating test. If the trace is still changing
   near timeout, consider a bounded observation-only extension before another
   command. If it plateaus, compare bounded approach direction/start pose or one
   justified speed setting. Do not repeatedly resend the same failed leg.
3. Preserve exact commands, baselines, configuration and observations. Evaluate
   one factor at a time; distinguish additive shortfall, direction-dependent
   hysteresis, proportional response and timing effects. These are hypotheses,
   not diagnoses from the two existing points.
4. If compensation is supported, keep it local to the tested joint, direction,
   speed and range. Compare unadjusted and adjusted results on held-out trials;
   reject corrections that worsen error, exceed path bounds or hide stale data.
   Do not blindly change torque, PID, midpoint, firmware or global calibration.
5. Define task-relevant endpoint acceptance from key spacing and the assumed tool
   geometry before qualifying a ghost route. Keep controller-derived tip residuals
   separate from unmeasured physical accuracy; do not simply widen tolerances to
   turn the current roughly 16 mm controller endpoint miss into success.
6. Once repeated endpoints meet those criteria, screen the current-pose approach,
   execute one noncontact press/retract, then repeat and expand to short sequences.
   Keep per-leg verification and reproducible exports; no contact qualification
   until the mounted tool and actual input events are checked.

The earlier nonresponse investigation below is retained as history and fallback
if response is lost or contradictory evidence appears. Power-off inspection and
manufacturer escalation are not current prerequisites merely because the initial
2-degree trial showed no reported change. Do not repeat the visual-confirmation
request as a routine gate; the latest trial's observation has been received.

### Earlier elbow nonresponse investigation — historical, superseded priority

Evidence: [watched elbow review](CARTESIAN_ELBOW_RESPONSE_REVIEW_20260917.md),
trial `wizard-20260917T155919439246Z-4bd875f42550457a956eab38b96b4a25`.
One T101 joint-3 command requested -2 degrees; the operator saw no movement,
reported change was zero, and completion timed out. HTTP 200 was not an execution
acknowledgement. This does not prove a failed servo or identify the root cause.

1. Audit the exact retained command, receipt and endpoint samples against the
   applicable official command semantics and installed interface evidence. The
   joint index and radian units have been checked; do not repeat that check or
   poll identical state as a substitute for a new discriminating test.
2. Identify remaining hypotheses and select checks that separate them: installed
   command-handler behavior, actuator communication/configuration, supply under
   load or mechanical obstruction. Prefer supported read-only diagnostics. Do
   not label missing torque or voltage fields OFF/zero. Do not assume the pinned
   source archive is the installed binary.
3. If software cannot expose the needed evidence, request one specific physical
   inspection or manufacturer diagnostic. Physical connector/mechanism inspection
   must be power-isolated; never ask the operator to force a powered joint. Do
   not indiscriminately disable holding torque on a gravity-loaded arm.
4. Apply only a remedy supported by the findings. No blind torque/PID/midpoint
   changes, firmware flashing, resets or larger movements to force a response.
   Explain consequential configuration changes and obtain any necessary authority
   beyond the current bounded testing scope before making them.
5. After a remedy or genuinely new evidence, run one bounded, logged elbow test
   with fresh baseline and endpoint comparison. Stop on nonresponse, unexpected
   motion or uncertain feedback; no automatic retry or return. Correlate an
   operator observation when software cannot establish actual response.
6. Confirm repeatable command-to-reported-position behavior before coordinated
   ghost typing. Validate approach from the actual current pose separately; do
   not jump to the virtual keyboard's first sample. Preserve failed runs and the
   before/after configuration alongside successful results.

Recovery acceptance: an explained/intervened-on failure mode, observed elbow
response consistent with the command, bounded repeatable endpoint results, and
reproducible exports. This still does not establish physical stylus-tip accuracy.
Coordinate compensation resumes only on responsive, usable measurements.

### Goal text for the app

The Active goal and autonomy section above is the revised working objective.
The goal-management tools available in this session cannot replace the text of
an unfinished app goal; updating this document does not claim to update that UI
field. Use the replacement goal supplied in the conversation for the app field.

### Completed ghost-keyboard work and historical checkpoints (2026-09-17)

Product-size endpoint milestone complete: normal and delayed-arrival simulations
each verified 55/55 route legs; seven injected fault cases stopped at leg 2 and
skipped the remaining 53. Individual leg archives, case manifests and a verified
suite index are recorded in the product-size plan. The CLI now provides an
evaluable full-size keyboard rehearsal; the wizard now offers a read-only saved
product-case review with per-leg archive verification. Running new product cases
remains CLI-only. No hardware moved. Next address live elbow response and the
current-pose approach, without treating synthetic endpoints as physical evidence.

Latest completed increment: all 55 projected A–S–D legs pass sampled firmware-
reference interpolation checks (12,877 samples, SPD coefficient 0.05). The verified
export and retained initial budget-limited run are recorded in the product-size
plan. This is offline mathematical evidence only; next implement per-leg endpoint
rehearsal for this route. No live commands or camera access occurred.

The user selected the OASO disc-tip stylus (ASIN B08Q7L85X2). See
[selected stylus reference](SELECTED_STYLUS_REFERENCE.md). Keep the existing
100 mm ghost offset hypothetical until the mounted reference-to-tip transform
is measured; verify robot-held touchscreen response separately from hand-held
response. Camera work remains deferred. No runtime geometry changed for this
product-reference update.

Product route bridge checkpoint: the selected full-size A–S–D simulation now has
an offline 56-sample/55-leg firmware-reference projection via solved joints, with
virtual tip coordinates retained separately. Thirteen bridge/overlay tests pass.
The projection assumes same joint signs/zeros; it neither validates installed
correlation nor includes a route from the current live pose. Next screen reference
interpolation and exercise the projected legs through endpoint rehearsal. Details
and caveats are in the companion product-size plan. No hardware was accessed.

Product-size placement milestone: a bounded translation overlay now moves the
keyboard envelope and all nominal keys together without changing frozen files,
scale or pitch. Four offsets were tested with fixed 100 mm tool length. The [0,-20]
mm board-frame shift passes A–S–D at all 56 sampled waypoints; [+20,0], [-20,0]
and [0,+20] fail joint-margin checks. See the companion product-size plan for exact
commands and all exports. No live movement, camera access, fixture redesign or
physical clearance approval resulted. Next connect this candidate's tool-aware
trajectory to controller-frame endpoint rehearsal; do not send board coordinates
directly as firmware coordinates.

**Latest refinement:** use the user's real Perixx PERIBOARD-409U dimensions and
existing nominal key layout, not just the artificial three-key row. The detailed
execution plan is [Product-size physical ghost typing](PERIBOARD_PHYSICAL_GHOST_TYPING_PLAN.md).
Manufacturer envelope: 315 × 147 × 21 mm. Initial assumed tool offset: 100 mm in
the modeled hand-TCP frame. Key centers and placement remain explicitly nominal.
Initial unshifted simulations: `a` passed 38/38 sampled waypoints; `asd` stopped at
S's approach on joint-margin rejection. The subsequently implemented [0,-20] mm
overlay passes A–S–D at 56/56 waypoints. Next screen its controller interpolation
and connect it to endpoint rehearsal before bounded real noncontact trials.
Preserve the earlier three-key suite as regression coverage.
Camera work remains deferred; modeled tip coordinates are not independent physical
measurements. See the companion plan for sources, exports and completion criteria.

G3 current-state check: a new read-only Wi-Fi T105 request succeeded with identity
matched before/after and 233.887 ms HTTP latency. Reported pose remains
[344.4737558,-0.528416538,205.72691] mm; elbow 1.596874 rad and raw load 97,
unchanged from the failed elbow trial. Torque-switch fields and supply voltage
remain absent. Export:
`software/runs/wizard-exports/wizard-20260917T150321359347Z-2d5da37fefbf4e8889202a54aefd5afe`.
This proves current Wi-Fi request/response access, not fresh underlying servo
acquisition or restored elbow movement. Metadata-only serial enumeration found
COM3/4/9/10, all Bluetooth; no USB serial arm endpoint was available for a second
transport comparison. No ports were opened and no movement was commanded.

Do not repeatedly query unchanged state to claim progress on G3. The next live
diagnostic needs independent operator observation of elbow response or a supported
read-only actuator diagnostic path. A mounted camera is not required. A full ghost
sequence remains premature until this specific discrepancy is resolved; its
simulation suite remains available without hardware. USB reconnection is optional,
not a new mandatory transport requirement, and must not trigger automatic motion.

Reproducible ghost regression baseline: run
`.\.venv\Scripts\python.exe software/scripts/rehearse_ghost_suite.py` from the workspace.
The finite nine-case A–B–A suite checks normal/delayed completion plus seven fault
cases, progression, skipped trials and write counts. It exports each case separately
through the existing bounded diagnostic exporter, then a readable Markdown summary
and JSON index referencing those sibling exports. All exports are verified before
success is returned; diagnostic limits were not increased. Keep the index and its
nine referenced folders together when sharing evidence. Seventeen suite/sequence
tests passed, including detecting an injected duplicate write in retained results.

The actual offline run returned SIMULATION_SUITE_PASS (9 cases), export verified:
`software/runs/wizard-exports/wizard-20260917T150248432030Z-4ddaea35e21744dc8408728c27af9099`.
Open `attachment-ghost-summary.md` there for the case table and evidence index.
These are software regression results, not measured movement or task qualification.

G2 fault coverage update: the shared owned-endpoint rehearsal now supports
DELAYED_ARRIVAL (350 ms of starting-pose reports before target reports),
MISSING_FEEDBACK (no post-write bytes) and POSITION_BIAS (Z offset twice the
declared positional tolerance). They are selectable in the wizard's single-leg
and ghost-sequence tests. On A–B–A with injection at trial 2, delayed arrival
completes all 11 trials with one write per trial. Missing feedback and a 0.2 mm
Z bias each stop after trial 2 as INSUFFICIENT_ENDPOINT_EVIDENCE and skip nine
trials. Neither case retries. Eighty-three targeted tests passed. Fault parameters
are retained in each result/export; they are synthetic, not measured arm behavior.

This does not establish servo acquisition freshness: a cached at-target payload
cannot be distinguished from fresh stationary feedback without additional evidence.
The report explicitly retains that limitation. Synthetic delay is not a physical
speed model. No camera or arm connection was made for these tests.

Endpoint integration checkpoint: wizard Tasks now includes **Test ghost sequence
endpoints (simulation only)**. It converts the retained ghost legs into a finite
campaign and invokes the existing owned endpoint runner for one leg at a time.
The existing runner's small-plan limits are preserved. The full campaign and
per-leg mapping are retained alongside each synthetic request/result. Zero-distance
travel legs are explicitly listed but never dispatched, including repeated keys.
A–B–A completes 11 nonzero-motion trials; a short write at trial 2 stops there and
skips nine remaining trials, without a retry or return. Baseline mismatch, unchanged
feedback, cancellation after write and cleanup uncertainty likewise stop progression.
One hundred two targeted tests passed, including wizard presentation and export.

This advances G2's endpoint/transport orchestration, not native dispatch or measured
accuracy. Synthetic feedback jumps to the expected target; it is not a servo dynamics
model and does not establish live timing. Each leg uses its own synthetic baseline
and owned session, not a persistent live controller connection. Remaining G2 work
includes delayed/missing/stale feedback and systematic error cases. G3 remains open
before coordinated live ghost tests; camera work remains deferred.

Implementation checkpoint: G1's first fixed three-key nominal layout is saved in
`software/config/ghost_keyboard_v1.json`. The wizard Tasks action **Preview ghost
keyboard (camera-free, no movement)** reuses `KeyboardCompiler` and the pinned
firmware FK/IK reference. It accepts 1–8 lowercase a/b/c characters, preserves
repetition/order, and samples travel, hover, virtual downstroke and retract legs
at no more than 2 mm Cartesian spacing. A–B–A produces 12 legs; A, ABC, CBA and
eight repeated A strokes also pass the sampled reference checks. The transform
places ghost X along nominal controller Y, with origin [340,0,220] mm and virtual
travel/hover/surface offsets 10/4/0 mm. These are simulation coordinates only.

Eighty-two targeted tests passed, including rejection of unsupported inputs/layout
edits, early IK failure, same-height lateral travel, deterministic hashes, wizard
display and full result export in both modes without device opens. Full-arm
clearance, installed limits/tool geometry, timing, simulated endpoint feedback and
native dispatch are NOT verified by this preview. G2 remains partial: next add
finite endpoint/transport simulation to these retained legs using the existing
move-verification path; do not use geometric pass alone to admit live ghost motion.

The user confirms the camera is not currently connected for use and its supports
are still being built. Treat camera availability, mounting, focus and calibration
as **DEFERRED**, not a blocker for software simulation or camera-free arm testing.
Do not repeat camera captures or request lens/lighting adjustments until the user
resumes camera commissioning. Earlier camera captures below are historical device
observations, not evidence of the current installation or a camera fault.

The immediate objective is a **ghost keyboard in free space**: named virtual keys
and simulated press cycles, using the existing motion planning, feedback and export
pipeline. No real keyboard, phone, stylus or camera is required for this stage.
The final objective remains real keyboard typing and phone tapping after tool and
board calibration; ghost testing does not complete those physical milestones.

#### G1. Define a reproducible virtual layout

- Reuse the existing keyboard layout/sequence compiler rather than create a second
  typing engine. Store key IDs, centers, usable rectangles and nominal key pitch
  in a versioned ghost-layout configuration with explicit millimeter units.
- Start with three adjacent keys and a short sequence such as A–B–A. Expand to a
  row, then multiple rows after the smaller routes work. Labels need not imply
  the physical keyboard has those keys in those positions.
- Keep the keyboard-local frame separate from the controller frame. In simulation,
  use an explicit nominal transform. For live trials, use a reviewed free-space
  anchor relative to fresh controller feedback, never guessed board registration.
- Start with the controller's existing end-effector reference. Any future stylus
  offset is a separate simulated configuration, not an installed-tool calibration.
- Define hover height, virtual downstroke depth, orientation, travel limits and
  speed policy explicitly. The lowest point remains in free space. Do not derive
  actual bench/link clearance from a virtual plane or unverified dimensions.

**Deliverable:** saved layout, transform and preview of named-key trajectories,
all clearly labeled SIMULATED/NOMINAL where applicable.

#### G2. Exercise the complete task path without hardware

For each key, generate approach at travel height → hover → bounded virtual
downstroke → retract → next key. Lateral travel occurs only after retraction.
Use the same target resolution, kinematics and result contract intended for live
execution. Validate intermediate samples, not only endpoints; include configured
obstacles and all modeled links, and label absent physical geometry as unknown.

Test reachable and unreachable keys, invalid frames/units, direction reversal,
settling delay, quantization, systematic offsets, missing/stale feedback, timeout
after dispatch, cancellation and export failure. Stop the remaining sequence on
an uncertain leg; never replay a virtual press automatically after a lost response.
Simulation may synthesize a virtual key hit, but must not report a real key event.

**Deliverable:** one end-to-end sequence and finite failure cases through the
wizard, with deterministic seed/configuration and reproducible exports.

#### G3. Restore the movement prerequisite independently of camera work

The saved elbow trials showed no reported response. Deferring the camera does
not clear that separate discrepancy, but a mounted camera is not the only way
to investigate it. Review command/feedback evidence and use operator-observed
bounded joint tests or supported diagnostics as appropriate. Record observation
separately from controller feedback. Do not assume mechanical failure, demand
precise external measurements for a gross response check, or increase displacement
and torque blindly to overcome apparent nonresponse.

**Deliverable:** sufficient evidence of commanded-joint response to admit the
selected coordinated route. Simulation and UI work proceed while this is open.

#### G4. Run finite camera-free ghost sequences on the arm

- Preview and review the actual free-space route from a fresh starting pose.
  Maintain existing motion limits and workspace clearance checks; no contact.
- Begin with one approach/downstroke/retract cycle. If all legs verify, run three
  cycles, then A–B–A and a short row sequence. No endless unattended campaign.
- Read endpoints after every leg. Preserve desired position, transmitted command,
  reported joints/XYZ, residual, settling time and sequence outcome. Clearly flag
  controller-derived XYZ and any unverified servo-read freshness.
- Start with one conservative supported speed; compare two additional bounded
  profiles only after the baseline route succeeds. Compare missed endpoints and
  cycle time before attempting continuous or blended movement.
- Stop sequence progression after a failed or uncertain leg. Do not automatically
  return home, retry the stroke or change compensation after a failure.

**Deliverable:** usable named-key command execution with per-leg results and logs,
qualified only for the demonstrated free-space route and controller-report policy.

#### G5. Learn useful patterns without claiming physical accuracy

Summarize errors by virtual key, approach direction, speed and repetition. Keep
raw commands and observations beside the summary. Compare any bounded compensation
candidate against an unchanged baseline on held-out routes/repeats; promote only
when it improves the declared endpoint metric without new failures. First correct
frame, unit, command or feedback defects; do not fit compensation to nonresponse.

Ghost tests can improve sequencing, communication, reported endpoint agreement,
repeatability and throughput. They cannot independently establish millimeter tip
accuracy, pressure, real key actuation or capacitive touchscreen response. An
operator's visual confirmation establishes observed motion, not calibrated XYZ.

#### G6. Rejoin the physical build when ready

Continue holder, fixture and camera-support construction in parallel. Later,
replace the nominal transform with measured board/tool calibration, verify camera
coverage and independent tip positions, then reuse the tested sequence engine for
one real key and one benign phone target. Use the existing input observers to
confirm actual events. Preserve the ghost suite as a regression test.

**Next implementation slice:** G1–G2, using the existing static task rehearsal and
movement interfaces; G3 diagnosis in parallel. G4 follows successful response and
route checks. Camera commissioning is not in this immediate queue.

### Historical checkpoints (not the current work order)

Camera revalidation: a fresh samples-only run (`camera-arm-view-check-20260917-02`)
again produced NEAR_BLACK frames. Added a bounded optional 0–5-second nominal
frame warm-up to the existing bench utility; 25 bench tests pass. A subsequent
live run with five-second warm-up (`camera-arm-view-check-20260917-03`) still
returned NEAR_BLACK at both 1080p and 20MP, with over 99.99% of pixels at levels
0–8. Both runs completed and closed their capture processes. The longer warm-up
did not restore visibility; it does not establish a lens-cap or sensor diagnosis.
No exposure/gain writes or arm motion occurred. Further identical captures are
not useful until the lens/iris/lighting/view is checked or another specific cause
is identified. Physical camera validation and elbow observation remain open.

Phone observer checkpoint: a self-contained benign target page is available at
`software/tools/phone-tap-test.html`, with the wizard Tasks action **Review phone
tap-test capture (no movement)**. It checks a supplied down/up/click transcript
against the captured target interior and expected count, then retains the result
in normal diagnostic exports. The page has no network or robot access. See
`software/docs/PHONE_TAP_OBSERVER_GUIDE.md` for manual acceptance and transfer.
Eighty-five targeted observer/action/rendering tests passed; actual Android page
operation, command association and robot tapping remain unverified. This closes
the initial offline phone-observation implementation gap, not Phase F acceptance.

Camera bench follow-up: `camera_bench_check.py` now records whole-frame grayscale
statistics and a gross exposure screen in future bench reports. At least 99% of
pixels at levels 0–8 yields NEAR_BLACK; at least 99% at 247–255 yields NEAR_WHITE.
Otherwise the outcome remains SCENE_REVIEW_REQUIRED, never automatic calibration
or arm visibility approval. The existing saved 1080p and 20MP samples both evaluate
NEAR_BLACK (over 99.99% dark pixels). The original exports were not altered.
Twenty-three offline bench tests passed, including threshold boundaries, a hot
pixel in a black frame and invalid image rejection. No new physical capture or
camera-setting change was needed for this follow-up. The lens/lighting/view check
below remains necessary before independent camera observation can proceed.

Latest physical camera check (2026-09-17): the exact Arducam B0477 DirectShow
endpoint was present before and after a bounded samples-only bench run. Both
1920x1080 and 5472x3648 captures completed and were encoded offline. However,
the images are effectively black: mean 8-bit grayscale levels approximately
0.000041 and 0.000751 respectively. Camera transport works for these samples;
usable scene visibility, arm observation and calibration are NOT established.
Evidence: `software/runs/wizard-exports/camera-arm-view-check-20260917-01`
(raw samples, PNGs, control readbacks, logs and file hashes). No arm commands or
electronic camera control writes were performed. Next physical action: check
that the lens is uncovered, iris admits light and camera points at the lit arm
and board; then repeat a bounded capture. Do not treat a successful frame read
as usable vision or use these black frames to infer that the arm is stationary.

Latest software checkpoint (2026-09-17): keyboard test-pad submission now latches
before dispatch, preventing another save attempt for that capture after success
or a lost response. Late focus/stop events cannot re-enable submission. Targeted
observer, action and wizard UI tests: 147 passed. This is automated handler/service
evidence, not real-browser input or physical robot-press validation. Next input
milestone remains a real-keyboard capture reviewed and exported through the wizard,
followed by association with a qualified robot command. Live elbow response remains
a separate unresolved movement prerequisite; no motion was issued for this update.

This is the working plan, not a requirement to finish every diagnostic before
building the stylus holder. Detailed phases follow; implementation checkpoints
record narrower achievements and must not be read as completion of whole phases.

### Delivery priorities and stop-investigating rules

Work toward the following demonstrations in order. Software and mechanical work
may proceed in parallel; a blocked live test does not block building the holder,
fixtures, result viewer or input observer.

| Delivery | Concrete output | Evidence needed to move forward |
| --- | --- | --- |
| 1. Trust one movement | One bounded route through command, feedback, verdict and export | A successful outward/return pair, followed by three successful pairs; retain failures too |
| 2. Install the tool | Adjustable stylus holder, stable fixtures and overhead camera | Recorded tool geometry, coverage and a manually confirmed screen-compatible tip |
| 3. Aim at one target | Board/tool mapping and one large target on each device | Independent noncontact checks fit within the usable target interior |
| 4. Perform one action | Approach, one press/tap, retract and event confirmation | Intended input occurs with no wrong or extra input; distinguish observation from robot attribution |
| 5. Repeat usefully | Ten trials per selected target, then a short sequence | Report success count, misses, duplicate inputs and recovery behavior; expand only the demonstrated scope |
| 6. Improve throughput | Shorter settling and limited compensation where useful | Held-out trials improve task outcomes without more misses or ambiguous execution |

The ten-trial batch is a practical commissioning screen, not a reliability
certification. Record its actual result rather than turning a small sample into
a claim of universal accuracy. A failed trial calls for a focused correction and
another finite batch, not an open-ended campaign.

**Immediate decision:** review the latest implementation checkpoints before live
execution. A joint that does not respond as expected is different from a small
residual positioning error: resolve that response issue before expanding motion.
Do not compensate for apparent nonresponse by increasing commands blindly.

For each development increment:

1. Select one demonstrable outcome from the table and reuse the existing path.
2. Implement only the missing pieces and run targeted simulation/fault tests.
3. Run a finite hardware trial only when its relevant prerequisites are met.
4. Export requested target, transmitted command, baseline, endpoint, timing,
   configuration, verdict and any independently observed input or tip result.
5. Update this file with the evidence and one next action. Defer unrelated tuning.

Do not require global compensation, every key, every phone application, maximum
speed, a finished enclosure or an exhaustive root-cause explanation before the
first useful demonstration. Do require an explainable command outcome and enough
target margin to avoid unintended contact. Controller telemetry alone does not
prove the physical stylus reached the intended point.

### Supporting delivery: one useful noncontact whole-arm route

1. **Select the existing execution path.** Trace wizard action → validated request
   → transport → feedback → result → export. The existing Wi-Fi wrist action is
   not automatically a Cartesian movement API. Reuse the existing endpoint runner
   where supported; document any missing adapter before implementing it.
2. **Connect preview to execution without changing its meaning.** The saved
   controller-space +2 mm/return preview is a geometric starting point only.
   Obtain fresh feedback before forming the actual trial; preserve orientation
   and unchanged joints, and check the small route against the installed setup.
   Do not copy an old absolute position into a live command blindly.
3. **Test the integrated path without hardware first.** Cover success, target
   rejection, timeout after transmission, missing feedback and export failure.
   No case may send the following leg after an uncertain preceding leg. A timeout
   must not cause a duplicate command or automatic contact retry.
4. **Execute one bounded outward/return pair when admitted.** Record the starting
   pose, desired pose, transmitted command, endpoint samples and verdict for each
   leg. Use supported conservative speed settings; record their units. If firmware
   blocks feedback during motion, report endpoint-only verification honestly.
5. **Review, then repeat a small finite batch.** Start with three pairs after the
   first pair passes. Agree the tolerance before running and preserve failures.
   This is a commissioning screen, not proof of workspace-wide accuracy.
6. **Close the delivery.** Show the route and per-leg outcomes in the wizard;
   export a readable summary plus raw evidence to `software/runs/wizard-exports`.
   Document the qualified route, configuration and remaining limits. Move on
   when this route is useful; do not require every possible pose to pass.

### Parallel delivery: build the physical tool

- Proceed with a lightweight, adjustable, repeatably mounted stylus holder now.
  Existing controller feedback alone does not establish physical tip accuracy,
  but complete global error compensation is not a prerequisite for construction.
- Record the installed tip length, orientation and payload; provide appropriate
  compliance and a bounded contact travel rather than relying on servo position
  alone to limit contact force.
- Finish the keyboard/phone fixtures and static camera mount. Preserve adjustment
  until actual coverage and focus are checked at the final board distance.
- Feed measured geometry back into the software. Nominal simulation dimensions
  remain explicitly nominal until checked against the build.

### First useful demonstration, then expansion

1. Calibrate the installed tool and board; validate a few independent points.
2. Qualify hovering over one large key and one large benign phone target.
3. Demonstrate one press and one tap with safe withdrawal and independent event
   confirmation. Follow with the finite screening batches in Phases E and F.
4. Demonstrate a short word and a fixed phone-button sequence through the wizard.
5. Expand target coverage, then shorten settling time and improve throughput.
   Add compensation only where held-out trials show it improves actual results.

### What counts as good enough

- **Communications:** each request has a traceable outcome; uncertainty is visible,
  not silently treated as success or replayed.
- **Reported motion:** the chosen route meets its declared endpoint policy.
  This is distinct from independently measured tip position.
- **Physical targeting:** tip footprint plus observed error and a reserve margin
  fits within the selected target's usable interior. Choose tolerances from the
  real target, not an arbitrary universal millimeter requirement.
- **Task operation:** the intended key/touch event occurs without wrong or extra
  events. A controller endpoint pass cannot substitute for this observation.
- **Progress:** if one small target fails, work with a larger qualified target;
  if a noncritical discrepancy does not change the next decision, record it and
  defer it. Never turn an unmeasured quantity into a passing result.

After each delivery, update this document with what changed, test/export paths,
what is actually qualified, and the single next implementation step. No new
diagnostic framework is warranted unless it closes a concrete gap in that step.

## 1. Destination and operating principle

The finished system lets an operator connect the RoArm-M3 Pro and static overhead
camera, configure the board and tool, select a keyboard key or Android screen
target, preview the action, and execute a controlled approach, press/tap and
withdrawal. It records what was requested, commanded, reported and independently
observed, so failures can be diagnosed from exported evidence.

**Success means reliably hitting the intended target without unintended contact,
not eliminating every fractional-degree discrepancy.**

Build on existing software. Prefer one usable end-to-end vertical slice over more
isolated diagnostic frameworks. Investigation must answer a question needed by
the next milestone; an unexplained discrepancy alone is not a reason to stop all
mechanical or software development.

This plan sets priorities. It does not authorize arbitrary motion, relax existing
admission limits, or convert historical results into current motion permission.

## 2. Baseline: what is established and what is not

### Established in the recent work

- Wi-Fi command/feedback access to the arm, with identity checks and bounded I/O.
- Existing one-use movement actions, endpoint checks, passive holds and exports.
- A completed eight-leg balanced wrist comparison with 946 hold readings. All
  four comparison probes reported 1.230468748 degrees against desired 1.25.
- Forty selected exports reviewed across sessions; both unfavorable results and
  failed/incomplete observations retained.
- An experimental descending wrist command of 0.95 degrees often improves the
  reported endpoint relative to desired 1.25, but is not universally repeatable.
- Wizard results distinguish command angle, desired angle and reported angle.

### Not established by those results

- Accurate Cartesian tool-tip positioning across the board or other joints.
- Final stylus geometry, payload effects, board registration or contact depths.
- A globally valid compensation model, or independent millimeter accuracy.
- Hardware performance of the optional 0.90-degree micro-correction branch.
- Reliable keyboard presses, touchscreen activation or sequence execution.

The camera selected by the user is an Arducam USB 3.0 20MP camera with a 16 mm
C-mount lens, intended for a static overhead mount. Confirm the exact installed
device, supported capture modes and working coverage from actual hardware; do not
infer final image quality, mount height or full-resolution frame rate from the
product title. The earlier approximately 10-inch focus experiment is not the
final mounting distance or calibration.

## 3. Rules that keep the project moving

1. Separate **transport reliability**, **reported positioning**, **physical tip
   accuracy**, and **task success**. Passing one does not imply the others.
2. Reuse the current wizard, native adapters, reviewer and export format. Audit
   existing implementations before adding a new abstraction or parallel runner.
3. Keep successful configuration snapshots and experimental candidates separate.
   Make rollback explicit; do not silently change global compensation.
4. Time-box a noncritical investigation to one planned experiment plus review.
   If it does not change the next engineering decision, record it and move on.
5. No more wrist-only zero-variability campaigns by default. Reopen that work only
   if it blocks a selected trajectory, makes verification unreliable, or causes
   an observed task miss. Its root cause is not a holder-build prerequisite.
6. A 35-second hold remains part of existing characterization actions. Do not
   insert it after every future keystroke. Develop and validate a shorter task
   settling policy separately; do not silently shorten existing diagnostic gates.
7. No automatic replay after a timeout or uncertain command. Obtain new state and
   report the uncertainty. A failed contact action must not trigger another press.
8. Halt progression on identity mismatch, stale/unusable feedback, unexpected
   joint motion, clearance uncertainty, export failure or uncertain execution.
   A software Stop is not a physical emergency stop. Use the existing bench
   precautions; commissioning a new emergency-stop subsystem is not a prerequisite
   for software work or holder construction under this plan.
9. Keep calibration changes explicit. Tool, camera, board or fixture movement
   invalidates the affected calibration; transport reconnection must not erase
   that fact or silently re-enable contact.

## 4. Implementation sequence and completion criteria

### Phase A — Freeze the baseline and consolidate the move interface

**Do now; no stylus required.**

- Inventory current wizard actions and implementations. Identify the production
  route for each step instead of assuming every historical plan was completed.
- Record configuration, source version/hash, firmware identity when available,
  selected transport/device identity, limits and reference exports. Do not copy
  credentials into diagnostics.
- Define one public move request/result contract used by UI and tests. Include
  request ID, coordinate frame, target, units, speed policy and configuration ID.
- Keep desired endpoint and actual transmitted command separate, including any
  compensation candidate ID and the scope under which it is applicable.
- Route requests through connection/identity checks, fresh baseline, validation,
  bounded dispatch, endpoint verification and result retention.
- Expose clear outcomes: NOT_SENT, ARRIVED_REPORTED, OUTSIDE_TOLERANCE,
  EXECUTION_UNCERTAIN and CANCELLED/STOPPED. Keep raw native states in diagnostics;
  do not relabel uncertain movement as a clean cancellation.
- Provide a compact export index so a developer can follow request → command →
  feedback → verdict → original evidence without reading a huge JSON dump.

**Tests:** simulated success, wrong identity, stale feedback, timeout before/after
dispatch, out-of-band endpoint, repeated request, cancellation and export failure.

**Done when:** one existing bounded movement is callable through the consolidated
interface, its UI and export agree, and tests prove at most one dispatch for an
uncertain request. Do not require support for every command family first.

### Phase B — Small whole-arm, noncontact movement workflow

**Start in simulation, then use bounded live trials.**

- Audit available forward/inverse kinematics and firmware command support before
  selecting the Cartesian or joint-space implementation. Verify units, reference
  frames, joint ordering, limits and orientation conventions.
- Define a small local set of two or three reachable poses with a clear route,
  above the board. Do not invent millimeter coordinates from photographs or use
  unverified board dimensions. Until mapping is verified, use explicitly reviewed
  controller-frame poses rather than claiming board-frame accuracy.
- Check the path, not just endpoints: other arm links, base, board, camera mount,
  cables and future tool all matter. Do not equate tip clearance with full-arm
  clearance. Keep speed conservative within the existing supported limits.
- Start with sequential bounded moves and verified stops at waypoints. Only add
  blended/continuous movement after this route is reliable; do not gain smoothness
  by queuing commands faster than their outcomes can be tracked.
- Predeclare a finite trial list, initially one outward/return pair, then a small
  repeat batch if it passes. Retain the actual start pose and every failed leg.

**Tests:** unreachable target, invalid frame/unit, path exclusion, unexpected
other-joint motion, feedback loss, mid-sequence stop and no subsequent dispatch.

**Done when:** the selected local route completes repeatedly with coherent
feedback, bounded behavior and reproducible exports. This qualifies only that
route and reported motion—not physical typing accuracy or the entire workspace.

### Phase C — Stylus holder and fixtures in parallel

**Mechanical construction need not wait for Phase B to be perfect.**

- Make the holder rigid, lightweight, adjustable and repeatably attachable. Keep
  a stable tool reference and record protrusion, orientation and payload.
- Consider a controlled compliant tip or travel limit for contact; account for
  deflection during later calibration rather than assuming a perfectly rigid tip.
- Use a capacitive-screen-compatible tip for phone tapping; verify it works on
  the actual phone before attributing failed taps to arm positioning.
- Secure keyboard and phone in repeatable fixtures. Record board dimensions,
  fixture locations and surface heights from the build, not guessed defaults.
- Provide camera mounting adjustment and cable strain relief. Select final
  camera height by actual field of view, focus and target resolution.

**Done when:** holder, fixtures and camera can remain stable during repeated moves,
and their geometry is measurable. Cosmetic finish and perfect calibration are
not prerequisites for this mechanical milestone.

### Phase D — Tool, camera and board calibration

- Keep transforms explicit: controller/base, board, camera, tool and target frames.
  Store units, calibration ID, measured geometry and validation observations.
- Determine the actual tip offset relative to the controlled end effector. A
  wrist-angle correction is not a substitute for this tool calibration.
- Calibrate camera intrinsics at the selected mode and lens setting; register
  board coordinates using known markers/control points. Lock or record settings
  whose changes affect calibration.
- Account for keyboard and phone surface heights. A single board-plane image
  mapping is not automatically accurate for raised keys or an elevated screen.
- Check mapping against points not used to fit it, including different board
  areas. Mark unreachable or poorly observed areas unavailable.
- Define target polygons and conservative interior aim areas. Reserve margins
  for tip footprint, calibration error, observed repeatability and contact drift.

**Done when:** independent checks support a useful interior aim area for at least
one keyboard key and one large phone target. No universal submillimeter claim is
required; uncertainty must fit inside the selected target with margin.

### Phase E — Actual tip repeatability, initially without contact

- Use the selected few targets, initially hovering at a measured safe height.
  Observe the actual tip with a calibrated camera or suitable independent method.
  A 2D image alone does not verify tip height or all three spatial coordinates.
- Predeclare five approaches per initial target/direction as an engineering
  screening batch, not a statistical reliability certification.
- Compare requested target, controller-reported pose and independent tip evidence.
  Separate repeatable bias from spread and registration/fixture errors.
- If the spread fits comfortably inside the target, proceed. If it does not,
  correct the demonstrated cause: mounting/calibration first, then only scoped
  compensation supported by the evidence. Validate on separate points/trials.

**Done when:** all approaches in the initial batch fit the chosen interior target
area with margin and no unsafe approach. If a small target fails, begin contact
testing on a larger qualified target while investigating the smaller one.

### Phase F — One press and one tap

- Implement approach → hover → bounded contact descent → dwell → withdrawal.
  Prevent lateral travel while in contact. Use separately configured keyboard
  and screen surface/depth behavior; do not assume shared pressing parameters.
- Use low-energy contact, conservative depth limits and appropriate compliance.
  Do not rely on undocumented raw servo fields as a force sensor.
- Start with one isolated key in a disposable local text field, and one large
  button in a benign phone test screen. Avoid credentials, purchases, messages
  and other consequential app actions during testing.
- Confirm the resulting key/touch event independently where possible. Distinguish
  a successful robot endpoint from a successful input event. Detect missing,
  duplicate and wrong inputs; do not retry them automatically.

**Done when:** an initial batch of ten isolated presses/taps per selected target
has the intended event, no extra event and safe withdrawal. This is a first-use
milestone, not a guarantee of long-run reliability. Preserve all attempts.

### Phase G — Short useful sequences through the wizard

- Represent keyboard work as discrete keys, not an assumed one-character/one-key
  mapping. Handle layout, Shift/modifiers, dwell and release explicitly.
- Represent phone work as targets in a known screen state. Start with fixed large
  controls; defer arbitrary UI recognition, scrolling and changing layouts.
- Preview the finite sequence, targets and expected input results. Execute one
  bounded step at a time with progress, pause/stop and a clear fault summary.
- After a failure, retain the actual state. Resuming requires a new reviewed
  remainder; never replay an uncertain completed press.
- Demonstrate a short word and a short benign phone-button sequence, then repeat
  a predetermined batch before expanding layouts or improving speed.

**Done when:** the user can connect, load valid setup, preview, execute, observe
results and export diagnostics through the application without developer commands.

## 5. Evidence and interface essentials

Every trial should identify the run/request, target/frame, configuration and
calibration, starting state, command bytes, receipt, timestamped feedback, endpoint
decision, contact/event outcome when applicable, and fault/stop reason. Retain
original evidence and make the short human-readable result the default UI view.

Reported joint error, reported Cartesian error, independently observed tip error
and input-event success must have separate fields. Unmeasured values remain
unknown—not zero or success. Exports go to `software/runs/wizard-exports` unless
the operator explicitly selects another folder.

Connection onboarding should guide device selection and recoverable checks,
including an empty network-neighbor cache versus a true identity mismatch.
Reconnection is not motion replay, fresh calibration or proof of actuator power.

## 6. Immediate work queue

- [ ] Define the versioned ghost keyboard and explicit nominal/controller transform (G1).
- [ ] Reuse the task compiler for virtual approach/downstroke/retract sequences (G2).
- [ ] Exercise complete ghost sequences and fault cases through the wizard/export path (G2).
- [ ] Resolve reported elbow nonresponse using camera-independent evidence (G3).
- [ ] Execute one finite free-space cycle, then three cycles and A–B–A (G4).
- [ ] Compare bounded speed/direction profiles and retain baseline/held-out results (G5).
- [ ] Resume camera commissioning only when supports are ready and the user requests it (G6).

The following original phase checklist remains the full-project destination;
it is not a requirement to finish camera installation before the ghost workflow:

- [ ] Audit/reuse existing move interfaces and document the selected end-to-end route.
- [ ] Freeze a reproducible reference configuration and known evidence links.
- [ ] Consolidate move request/result statuses and export indexing (Phase A).
- [ ] Test the complete interface in simulation, including uncertain dispatch.
- [ ] Define and simulate a small clear local route (Phase B).
- [ ] Review route geometry and perform a finite noncontact hardware trial.
- [ ] Continue holder/fixture/camera construction in parallel (Phase C).
- [ ] Calibrate the installed tool and actual build (Phase D).
- [ ] Validate independent tip placement on selected targets (Phase E).
- [ ] Demonstrate isolated press/tap, then short sequences (Phases F–G).

The next implementation slice is G1–G2 above, building on Phases A–B. Do not begin a new
wrist-only research loop in place of these deliverables. Update this checklist
with actual outcomes and evidence, never mark live milestones from simulation.

## 7. Deferred work and scope boundaries

### Implementation checkpoint — 2026-09-17

Phase A is in progress, not complete. The existing bounded native Wi-Fi roll
wizard route now retains a `rocell.move_result.v1` projection alongside its full
native evidence. The wizard displays the same retained object that is included
in diagnostic exports: operation/request ID, command, desired angle, last
reported angle, error and endpoint-verification outcome. The evidence pointer
`/steps/0/report` locates the original report within that operation result.

Cancellation or timeout after attempted dispatch remains EXECUTION_UNCERTAIN;
it does not claim a stopped robot. NOT_SENT requires evidence that dispatch did
not start. Arrival requires the native verifier's success, not merely an HTTP
receipt. No motion admission, retry policy, compensation or limits changed.

Targeted validation covers the real transaction simulation, injected transport,
duplicate requests, UI rendering, native wizard integration and exported result
equality. This checkpoint does not establish live accuracy or complete Phase A's
request/configuration contract and standalone export index.

The Phase B audit found existing `trajectory_simulation.py` and numerical IK.
They already solve sampled keyboard/phone routes using the pinned model, but
explicitly do not establish full-arm/cable/holder clearance or issue physical
commands. Reuse this simulation; do not treat sampled tip clearance as whole-arm
hardware qualification. No live movements were made for this checkpoint.

### Request and export integration checkpoint — 2026-09-17

The existing durable Wi-Fi reservation now stores a `rocell.move_request.v1`
before dispatch. It records the native attempt ID, explicit controller-joint
radian target, transmitted command, desired endpoint, baseline and a hashed
configuration snapshot. The snapshot includes expected device identity,
transport, native speed/acceleration settings, completion budget and endpoint
policy. Firmware version and calibration remain explicitly unknown; this hash
is not a source-code hash, physical calibration or certification.

The runner returns the same request on success and failure. The wizard summary
links its operation ID to the native request ID and configuration ID. General
diagnostic `report.json` now contains `snapshot.movement_export_index`, pointing
only to included result attachments. Original report and command evidence remain
in those attachments; existing omission reporting and manifest verification are
unchanged. A repeated request is not a new success or a resumable command.

Validation: 163 targeted tests passed across move results, injected/native adapter
contracts, one-use dispatch and the wizard service. An end-to-end simulated
transaction passed through the physical wizard branch with injected transport,
then exported its request and result unchanged. No hardware was contacted.

Next: finish reference/source identity recording and audit the existing nominal
trajectory inputs and controller-frame conversion. Do not add another motion
sender merely to produce a route demo. Phase A remains partial until its full
test matrix and baseline snapshot are covered; Phase B remains unqualified live.

### Static task-route checkpoint — 2026-09-17

The documented legacy `simulate-trajectory --use-optimized-park` invocation was
tested against the current freeze and returned `PLACEMENT_SELECTION_REQUIRED`:
it has no documented default placement for Freeze 011. It also uses the legacy
camera context. Do not silently reuse a historical placement as installed truth.

An explicit static route now joins the already-existing static bundle/context,
static semantic compiler and target catalog to the existing geometric engine
and shared numerical IK sampler. No legacy manifest or source lock was changed.
Run from the workspace root:

```powershell
.\.venv\Scripts\python.exe software/scripts/rehearse_static_task.py --device keyboard --text a
.\.venv\Scripts\python.exe software/scripts/rehearse_static_task.py --device phone --text a
```

The script accepts up to eight characters and exports via the existing diagnostic
exporter. A nonzero exit with `SAMPLED_IK_GAPS` is a retained negative result, not
a broken export. This is not yet wired into the wizard Tasks page and does not
perform camera observation, continuous route verification or physical commands.

Both actual runs passed geometric checks and converged at four of five sampled
poses. The only failed sample was nominal PARK; target transit/hover/approach/
contact samples converged. This is numerical feasibility, not measured accuracy.

- Keyboard: `software/runs/wizard-exports/wizard-20260917T130437020904Z-f92c45d5d1974061b52b29c9163cae47`
- Phone: `software/runs/wizard-exports/wizard-20260917T130446066160Z-92d5a0feabe040bcade616ac8610b441`

The static route/context test selection passed 39 tests, including the real
solver, retained park failure, report hash, architecture separation and network/
subprocess prohibition. Next: an explicit simulation-only park selection and
sampled route check, followed by wizard integration. Preserve the unsuccessful
baseline rather than loosening convergence thresholds to hide it.

### Explicit park overlay — 2026-09-17

Static rehearsal now accepts `--park-xy-mm X Y`. It validates the candidate
against the board boundary, obstacle footprints and marker tiles using the
existing trajectory park rule. The selected coordinates and overlay provenance
are included in the hashed report. No frozen file, tool geometry, convergence
tolerance or installed calibration is changed.

The finite trials produced:

- `(305, 300)` rejected: overlaps marker K0; no route evaluated.
- `(250, 300)` retained as an IK-gap result (four of five samples converged):
  `software/runs/wizard-exports/wizard-20260917T130713122638Z-2b6f6969c7944d87a27f2b64dcaee4fa`.
- `(290, 40)` accepted all five samples for keyboard `a`:
  `software/runs/wizard-exports/wizard-20260917T130720579836Z-107cd520677a49f18d0d831f722af6f3`.
- The same `(290, 40)` accepted all five samples for phone `a`:
  `software/runs/wizard-exports/wizard-20260917T130721733987Z-4e06f117720447929a6d065b94d0f250`.

Reproduce either device with the previous command plus `--park-xy-mm 290 40`.
The nominal `(305, 400)` baseline remains unchanged. Do not use the overlay as
a physical board measurement or send it directly to the robot. Passing these
five samples does not prove reachability between them, full-arm clearance or
controller-frame agreement. Next work is sequential/densified route screening
and wizard integration, not further point-only success counts.

### Dense static-route checkpoint — 2026-09-17

Add `--dense` to the static rehearsal command for a sequential route screen.
It reuses the existing trajectory densifier and joint-result evaluator with
15 mm maximum Cartesian sample spacing, 0.35 rad maximum adjacent joint change,
the existing 0.01 normalized joint margin and numerical-rank check. The previous
accepted solution seeds each next solve. One pass is capped at 256 waypoints;
the first failure stops solving and leaves the remainder explicitly unevaluated.
No automatic refinement or tolerance relaxation occurs in this mode.

With explicit park `(290, 40)` and text `a`, real numerical runs passed:

- Keyboard: 38/38 waypoints. Export:
  `software/runs/wizard-exports/wizard-20260917T130940021001Z-702bd56bc8d84c2f9b00799f7ac336f4`.
- Phone: 44/44 waypoints. Export:
  `software/runs/wizard-exports/wizard-20260917T130951897398Z-45fed150c20c4d14a0cb519c8c1af283`.

39 static-route and legacy-trajectory tests passed, including all intermediate
checks, continuation seeds, and stopping at the first failed nominal park. No
arm or camera access occurred. These routes include numerical contact phases,
but are not executable contact paths: physical tool geometry, controller-frame
correlation, installed mapping and full-arm clearance are still unqualified.
Next: wizard integration of the explicit static rehearsal and its compact result;
then derive the noncontact commissioning route from measured controller state.

### Wizard static rehearsal integration — 2026-09-17

The Tasks page now includes **Rehearse static-camera typing/tapping route**, in
both rehearsal and physical application modes. The action itself is always
simulation-only: no device providers, network, camera capture or robot command.

Workflow:

1. Select keyboard or phone and one to eight non-sensitive test characters.
2. Select `overlay_290_40` for the explicitly labeled simulation park, or
   `nominal` to reproduce the retained park failure. Neither changes the build.
3. Prepare/review and execute the action using the existing wizard controls.
4. Read route outcome, planned/evaluated waypoint counts and first failure.
   Expand **Inspect full static route evidence** for original numerical results.
5. Use **Export logs** to save the result and source hashes to the assigned
   workspace export folder. A failed route remains exportable evidence.

The parent service owns the report and rechecks source identity before and
after computation. A dense-route failure produces FAILED, not merely a
successful-worker label. Physical typing/tapping remains unavailable; this
action does not qualify installed geometry or enable the separate executor.
Historical `simulate_task` remains labeled as the legacy route.

Initial integration verification passed six tests using the real static solver
through the service in both application modes, JSON export/manifest verification,
negative input checks and actual application-JavaScript rendering of pass/fail
cards. No physical devices were opened. A live-browser usability check remains
to be performed; DOM harness tests are not a claim of that walkthrough.

### Short-sequence capacity and failure visibility — 2026-09-17

Real numerical runs exercised more than a single target, with park `(290,40)`:

- Keyboard `aaaaaaaa`: all 108 sequential samples passed and the complete
  563,635-byte attachment exported successfully:
  `software/runs/wizard-exports/wizard-20260917T131609880408Z-bb8351b54310403db9b995d599f0037e`.
- Keyboard `hello`: 13 of 83 planned samples evaluated, stopping at H's HOVER
  waypoint with `IK_NO_CONVERGED_SOLUTION`. The attempted solve's residual was
  about 0.2834 mm and 0.01347 rad. Those are numerical residuals, not measured
  physical errors. This does not establish that H is physically unreachable.
  Negative evidence exported at
  `software/runs/wizard-exports/wizard-20260917T131553112375Z-49b803a505d144f58d65ed633434e7e2`.

The report and wizard now retain/display requested target order including
repeats, target count, and the first failed target/phase. Repeated targets are
not silently collapsed into a single press by the task summary; the endpoint
sampler's deduplication remains separate from dense sequence evaluation.
Neither a numerical contact waypoint nor a simulated sequence establishes an
actual key/touch event. Those event observations remain explicitly unperformed.

### Bounded H-approach investigation — 2026-09-17

The retained failed waypoint was replayed with the same model, controller joint
bounds, previous accepted seed and target. The original 4 attempts × 45 iterations,
10 × 140 and 16 × 280 all failed the unchanged 0.20 mm / 0.003 rad solver
tolerances. Best selected residuals remained approximately 0.28–0.29 mm and
0.0134 rad. This rules out a simple insufficient-small-budget explanation for
this experiment; it does not prove physical unreachability or a unique cause.
Export: `software/runs/wizard-exports/wizard-20260917T131906403407Z-b88ec2109c434d6bbb88dca8651c7bb4`.
Replay helper: `software/scripts/diagnose_static_ik_failure.py --input <export>`;
it checks export integrity and current static-source identity and is restricted
to nominal-tool failures. No device I/O is used.

The static rehearsal also accepts an explicitly labeled `--tool-length-mm`
hypothesis (80, 100 or 120 only). These are offsets from modeled `hand_tcp`, not
stylus fabrication lengths. They do not mutate the context, source locks,
installed configuration or wizard default. The full `hello` route still failed:

- 80 mm: evaluated 11/83 samples; export
  `software/runs/wizard-exports/wizard-20260917T132057872260Z-e90aabab2cb8400a8688958891b1964e`.
- 100 mm: previously retained 13/83 baseline.
- 120 mm: evaluated 14/83 samples; export
  `software/runs/wizard-exports/wizard-20260917T132026263171Z-6d5f3ac24cea47fdae56b16e3db8e702`.

Decision: stop this bounded study. Neither more iterations nor these three tool
offsets produced a qualified word route. Retain the working isolated-target
route, continue holder/fixture and measured controller-frame preparation, and
revisit the full keyboard layout using installed geometry rather than tuning
unmeasured coordinates indefinitely. No convergence threshold was relaxed and
no physical motion occurred.

### Live controller-frame baseline — 2026-09-17

Two explicit T105 feedback-only wizard requests succeeded with expected MAC
identity before and after each request. No motion commands or serial opens.
The second HTTP exchange took 121.239 ms and reported the same response hash
and joints as the first. This is two observations, not a continuous stability
or independent sensor-freshness proof.

The installed response includes x/y/z/tit. The previous Wi-Fi report projected
only joints, so the report now retains Cartesian field coverage and values and
the wizard displays them. Missing fields are null, never fabricated zeros.
Latest controller-reported pose: x=345.6206222 mm, y=-0.53017581 mm,
z=214.5461189 mm, tit=0.030679616 rad. No board/TCP equivalence is assumed.

Export: `software/runs/wizard-exports/wizard-20260917T132259741971Z-2765554dcbd64b7abfb0e4c55886317f`.
The report is a historical baseline, not a reusable dispatch admission.
120 feedback/native transaction tests passed after the projection change.
Next: correlate controller-reported Cartesian and joint fields with the pinned
model offline; preserve frame/zero hypotheses and avoid interpreting firmware
FK output as an independent physical tip measurement.

### Controller/model frame comparison — 2026-09-17

The saved controller snapshot was compared offline to the exact pinned URDF
under the explicit, unqualified same-sign/same-zero arm-joint hypothesis.
`review_controller_model_baseline.py --input <feedback-export>` verifies the
input export and emits a separate diagnostic export. It uses only the ancestors
of `hand_tcp`; the gripper is a sibling branch and its value is not substituted
or included in that transform. No stylus offset or fitted calibration is applied.

At this one pose:

- Controller XYZ: `(345.6206222, -0.53017581, 214.5461189)` mm.
- Vendor-world `hand_tcp`: `(343.0852661, -0.5275469, 335.2215467)` mm.
- Vendor-base `hand_tcp`: `(343.0852661, -0.5275469, 265.1215467)` mm.

The naive equivalence residual is therefore approximately -2.535 mm in X and
+120.675 mm in world Z (or +50.575 mm in base Z). This rejects treating these
named frames/endpoints as interchangeable at this snapshot. It does **not**
prove arm inaccuracy, a valid constant translation, installed joint offsets,
or a unique explanation. Never feed this residual back as a correction.

Export: `software/runs/wizard-exports/wizard-20260917T132516806230Z-f39191e409df418bb350f2bef7c43e13`.
Seven offline tests passed, including equivalence of the ancestor calculation
to full-model FK, independence from the gripper branch, missing Cartesian data,
identity mismatch and invalid numbers. Next: inspect the pinned firmware's
Cartesian endpoint definition and joint conventions, then test any resulting
hypothesis across independently varied joint poses before estimating a transform.

### Firmware endpoint reconciliation — 2026-09-17

Re-downloaded the official pinned reference ZIP into memory and verified SHA-256
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
Inspected `RoArm-M3_config.h:101-177` and `RoArm-M3_module.h:595-619`.
The executable FK sums link contributions without adding l1/base height and
uses configured end-edge dimensions 171.67/13.69 mm. Roll and gripper do not
enter this XYZ calculation. URDF link origins and its `hand_tcp` are different.

The existing bench script already contained these reference equations. They
are now centralized in `kinematics/firmware_reference.py`, reused by the bench
script and controller/model comparison, with finite-input validation. This is
an offline reference model, not a newly enabled command path.

At the saved live pose, reference FK predicts
`(345.620622198, -0.530175884, 214.546118785)` mm; distance from the reported XYZ
is `1.36345e-7` mm. Predicted pitch is `0.030679616205` rad. This is agreement
between calculations to reported precision, **not** submicrometer physical
accuracy, installed binary attestation or a board/TCP calibration.

Export: `software/runs/wizard-exports/wizard-20260917T132808054434Z-f0ccdebae3314be5ac3b3c0c1a469849`.
Do not use the prior world/base residual as a constant compensation translation.
Next: use the firmware endpoint model for controller-space noncontact previews,
and keep URDF whole-arm geometry and installed stylus registration as distinct
contracts. Verify across varied saved/live joint poses before asserting general
agreement with the installed controller.

### Small controller-space route preview — 2026-09-17

Added `application/controller_route_preview.py`, reusing the centralized firmware
reference equations. The saved identity-matched Cartesian/joint snapshot now
supports a finite +2 mm R_ctrl Z leg and a return leg, 41 geometric samples each.
Reported pitch is preserved; roll/gripper are retained unchanged and no command
bytes, speed policy, live admission or dispatch are generated.

Checks include complete finite feedback, FK agreement with the saved baseline,
regular-branch IK, modeled arm bounds, a 3-degree baseline excursion limit,
1-degree adjacent-sample limit, and XYZ/pitch roundtrip agreement. These numerical
checks do not establish installed clearance, timing, payload behavior or board
registration. The initial preview passed all 82 samples. Maximum changes from
baseline were approximately base 0, shoulder 0.00778, elbow 0.78380 and wrist
pitch 0.79157 degrees.

Export: `software/runs/wizard-exports/wizard-20260917T133002625624Z-4e584ed9022f4b42b2be80c61c4e1325`.
Reproduce using `review_controller_model_baseline.py --input <feedback-export>`;
its report includes `noncontact_route_preview`. 51 preview/reference tests passed.
No physical movement occurred. Next: reuse the existing live campaign and
admission path for an explicitly bounded controller-space trial, rather than
creating a direct-send shortcut or treating this saved preview as a permit.

Defer a global learned compensation model, exhaustive joint/speed sweeps, perfect
zero repeatability, root-cause proof of every discrepancy, arbitrary Android app
navigation and maximum typing speed until a basic end-to-end task works.

Retain the existing optional micro-correction experiment, but hardware validation
of that branch is not a prerequisite for the holder or noncontact workflow. Do
not force an unfavorable endpoint merely to exercise it.

This roadmap supersedes further wrist-only investigation as the default project
priority. It does not supersede current native safety checks or verified evidence.
When a milestone is blocked, identify the smallest missing measurement or software
capability and continue independent mechanical/simulation work where possible.

## 8. Reference evidence

### Independent keyboard input capture — 2026-09-17

With movement paused for elbow diagnosis, implemented the independent keyboard
test pad and `review_input_capture` wizard action. It records only an explicitly
started, focused local field, checks individual key-down/text/release events,
and stores the review through existing wizard tickets and diagnostic exports.
The Tasks page links to it. No global input hook or robot command is involved.

See [Keyboard input observer guide](KEYBOARD_INPUT_OBSERVER_GUIDE.md). A passing
transcript establishes matching browser input, NOT robot attribution or contact
readiness. Real-browser manual validation, command/capture association and Android
pairing remain incomplete. This advances Phase F's outcome-observer software
without claiming that physical pressing or the elbow fault is resolved.

### Wizard fault-review integration — 2026-09-17

Added the read-only `review_cartesian_export` Arm action. It verifies a workspace
trial export and shows per-joint expected/reported response, uncommanded drift,
endpoint error, original outcome and source hashes. The usual wizard export
retains this review; it does not create movement authority or replay the source.

The existing Wi-Fi feedback card now exposes optional torque-switch, raw load
and voltage coverage. A new read-only observation still omitted all torque
states and voltage, so actuator condition remains unknown. Further movement is
still paused; this integration makes the failure usable in the application
while independent software and mechanical work can continue.

### Direct elbow diagnostic outcome — 2026-09-17

The fixed -2-degree elbow-only T101 diagnostic was tested in simulation and then
sent once using fresh baseline, the existing exact-send latches and endpoint
observation. Elbow feedback remained unchanged at count 2065 rather than the
predicted 2042. The other joints remained unchanged; no return/retry was sent.
This means the observed failure is not confined to the Cartesian path.

Further motion testing is paused pending elbow control/actuator-state diagnosis;
no torque, PID, calibration or firmware settings were changed. See the updated
[elbow response review](CARTESIAN_ELBOW_RESPONSE_REVIEW_20260917.md) for exports,
read-only status limitations and the next diagnostic decision. The main project
goal remains incomplete; software/fixture work can continue independently.

### Elbow isolation checkpoint — 2026-09-17

See [Cartesian elbow response review](CARTESIAN_ELBOW_RESPONSE_REVIEW_20260917.md).
Pinned firmware inspection identified a one-count command/feedback midpoint
asymmetry; new endpoint reports show both ideal joint errors and predicted bus
count errors. This is diagnostic modeling, not captured servo-bus telemetry.

A distinct +5 mm Z trial was added within the existing modeled joint limits and
performed once after fresh preflight. Wrist pitch followed its predicted count
target, but elbow feedback changed +2 counts rather than -22. The reported XYZ
miss was 11.755 mm. The trial failed; no return or retry was sent. Larger
Cartesian steps and global compensation are paused pending elbow isolation.
143 tests passed before this live diagnostic. The detailed review records source
lines, exports, limitations and the next bounded test decision.

### First live Wi-Fi Cartesian leg — 2026-09-17

Implemented a separate bounded Cartesian transaction/reservation and native
adapter, reusing the existing durable send-once latches, HTTP receipt handling,
transport mutex and observation runner. Scope is exactly one +2 mm controller-Z
leg with unchanged pitch/roll/gripper, no automatic return or retry. It is not a
general task/contact API and is not yet exposed as a live wizard action.

`scripts/bench_cartesian_vertical.py` performs a read-only fresh-feedback preview
by default. **`--execute` physically sends one leg** after fresh feedback and
the reference screen; it must not be used as an automatic retry of this failed
endpoint test. Both modes export and verify diagnostics. The live caller must
still establish actual route clearance; the reference calculation does not.

Evidence from the single live trial:

- Read-only preflight passed from the reported starting pose, export
  `wizard-20260917T134716735033Z-2138acff4fd9494c9e7ff967f7476655`.
- One T104 request was sent: start Z 214.5461189 mm, target Z 216.5461189 mm,
  X/Y/pitch and roll/gripper preserved, firmware coefficient 0.05.
- HTTP 200 returned old pose data; that receipt was correctly NOT used as an
  endpoint acknowledgment. Independent subsequent feedback was collected.
- 32 accepted observations reported Z 212.4470354 mm; the endpoint did NOT pass.
  Last XYZ error was 4.1064243 mm and pitch error 0.012271846 rad.
- Expected elbow was 1.580126232 rad versus initial 1.593806039 rad, but feedback
  continued to report the initial elbow value. Wrist pitch changed from
  0.007669904 to 0.019941750 rad (reference target 0.021485430 rad).
- This is reported controller-state behavior, not an independently measured
  physical tip error. Deadband, load, mechanics or firmware behavior are possible
  explanations, not established causes. No compensation was inferred/applied.
- Live export: `wizard-20260917T134750110509Z-43eed641415c4961b4fe26655bd3b341`.
  It retains `COMMAND_OUTCOME_UNCERTAIN` because the final read timed out near
  the absolute completion deadline. Earlier endpoint samples already showed
  a persistent miss. The original report remains unchanged.
- A subsequent read-only check reported the same pose, export
  `wizard-20260917T134816124791Z-055c8c5199e64259bf143565a1b0fbb2`.
  There was no automatic return, second movement or retry.

After reviewing the live export, the Cartesian runner was corrected to report
expiration of an active observation/completion deadline accurately when a read
raises at that deadline. This does not promote a missed endpoint to success.
129 tests pass covering Cartesian transactions/native byte dispatch, failure
behavior, reference preview and existing wrist regressions.

Next: expose the per-joint expected-versus-reported differences in the endpoint
review, then select a finite diagnostic that distinguishes insufficient small
elbow response from a command/frame problem. Do not repeat the same relative
move blindly, accumulate offsets, or apply a global coordinate correction from
this one pose. The route is NOT qualified; holder/fixture work remains parallel.

### Owned endpoint workflow rehearsal — 2026-09-17

`application/controller_endpoint_rehearsal.py` now translates the screened
controller-space +2 mm/return route into the existing frozen campaign contract
and exercises `run_owned_endpoint_trial` through the existing incapable wizard
rehearsal. It does not implement another command sender. Both legs preserve the
recorded pitch, roll and gripper values; only a clean first endpoint permits the
simulated return. Source feedback is historical; reviews, elapsed time and
post-command observations are explicitly synthetic.

Run from the workspace with:

```powershell
.\.venv\Scripts\python.exe software/scripts/rehearse_controller_endpoints.py --input software/runs/wizard-exports/wizard-20260917T132259741971Z-2765554dcbd64b7abfb0e4c55886317f
```

Add `--fault SHORT_WRITE` to exercise uncertain dispatch. Other supported faults
are baseline mismatch, unchanged endpoint, cancellation after write and pending
cleanup (see CLI help for exact names). These are simulated faults only.

The export contains the complete results and a `campaign-plan.json` attachment
compatible with the existing wizard campaign/endpoint rehearsal inputs. It is
not an approved live request and carries synthetic evidence labels.

Evidence:

- Successful simulated pair, both `OBSERVED_ENDPOINT_DWELL`:
  `software/runs/wizard-exports/wizard-20260917T134042847721Z-06c492bff9024f158c1648ef6c400b41`.
- Incomplete simulated write, `WRITE_UNCERTAIN_NO_RETRY`, return skipped:
  `software/runs/wizard-exports/wizard-20260917T134043541308Z-49c87242b8a64b88acd695168b17dcf2`.
- 35 tests passed across the new bridge, existing wizard endpoint integration,
  request contract and controller preview. No physical command was sent.

The native endpoint composition inspected here is USB-specific; the current
Wi-Fi discrete sender is wrist-specific. Live Wi-Fi Cartesian execution remains
an implementation gap, not a feature established by these rehearsals. Next work
must adapt the transport with explicit at-most-once dispatch, fresh starting
state and Cartesian endpoint observation rather than route arbitrary commands
through the wrist reservation. Existing USB admission must not be bypassed as
an alternative shortcut.

### Integrated campaign reference-IK checkpoint — 2026-09-17

The existing wizard movement campaign preview now checks every bounded T104
interpolation sample against the centralized pinned firmware inverse/forward
equations. It retains sample counts, joint landmarks, numerical roundtrip error,
maximum adjacent joint change and the first unresolved sample. The wizard displays
the reference-IK outcome separately from successful interpolation generation.

The implementation reuses `motion/characterization_controller.py`; it adds no
sender, alternate command path or live authority. Only the regular four-joint
reference branch is covered. Installed limits, roll/gripper, collisions, actual
motion timing and physical tool-tip accuracy remain unqualified. Synthetic
campaign completion remains an analysis-workflow test, not hardware readiness.

Validation: 41 focused tests passed across controller preview, campaign planning,
wizard campaign integration and the actual JavaScript summary renderer. Coverage
includes a modeled +2 mm/return pair, unsupported reference geometry, failure at
an intermediate sample, trace-budget exhaustion and visible failure reporting.
No physical movement was performed for this checkpoint.

Next: wire a bounded Cartesian trial through the existing admitted endpoint
execution workflow. The current Wi-Fi wrist-specific runner is not a Cartesian
sender; do not treat this numerical preview or old feedback as live permission.

- [Balanced live comparison](BALANCED_DIRECTION_RUN_20260917.md)
- [Cross-session comparison and limitations](ROLL_COMPENSATION_GENERALIZATION_20260917.md)
- [Zero-position variability review](ZERO_POSITION_VARIABILITY_REVIEW_20260917.md)
- [Current micro commissioning wizard](MICRO_COMMISSIONING_WIZARD_GUIDE.md)
- [First native micro-workflow result](MICRO_COMMISSIONING_FIRST_LIVE_RESULT_20260917.md)

These documents support the baseline, not proof that later phases are finished.
