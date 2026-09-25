# Finite elbow local-correction experiment

2026-09-17. Experimental; not a global calibration or physical accuracy claim.

## Purpose and evidence

Two lifting trials show approximately 3 degrees of reported shortfall. One
opposite-direction trial overshoots its target by 0.515625 degrees (six predicted
encoder counts). The offset is only a candidate for that local direction/range
at speed 20 and acceleration 1. It needs an independent validation trial.

Training export:
`wizard-20260917T162113108962Z-9d5d681c4a304b0195449e2e0ab3f489`.
Desired validation endpoint: the same 1.5633309535598299 rad controller elbow
angle. Candidate command: desired angle minus the retained positive residual
0.008999354440170082 rad, namely 1.5543315991196598 rad. This is a continuous-angle
candidate; the exact quantized command and predicted count must be checked before
execution. Do not substitute a universal three-degree correction.

## Separate preparation from validation

1. One existing -5-degree elbow-only lift from fresh current baseline, speed 20,
   acceleration 1. Its preflight displacement is approximately 27.57 mm and the
   goal remains within previously commanded elbow angles. This is an explicit
   conditioning trial, not a resend of the previous absolute target.
2. Stop after that trial regardless of outcome. Preserve the existing strict
   endpoint verdict. If it misses its requested endpoint, do NOT mark it passed,
   automatically chain another command, or merely widen arrival tolerance.
3. Review the actual retained pose and trajectory separately. If the conditioning
   endpoint verifies, prepare validation normally. If it does not, decide whether
   an independently reviewed subsequent experiment can use a fresh reported
   baseline; record that decision and its limits explicitly rather than claiming
   a successfully completed conditioning campaign. Unstable, nonresponsive or
   unexpected motion prevents progression.
4. Validation must approach the candidate command from below, keep the same
   speed/acceleration, preserve other joints, and screen its full sampled path.
   No native correction is enabled merely by writing this document.
5. Compare final reported angle against BOTH the corrected wire target and desired
   validation endpoint. A command-level miss cannot be hidden by a desired-target
   success. Report both verdicts, final-window variation and source/config hashes.
6. Keep the candidate frozen while collecting held-out evidence. A single improved
   trial is preliminary, not acceptance of a full-range model. Require repeatable
   improvement before adding it to task execution or extending to other joints.

No camera, tool contact, torque/PID/midpoint change, firmware write, or automatic
return is included. Actual keyboard/screen input validation remains later work.

## Conditioning result

Preflight: `wizard-20260917T162520540119Z-55fead6cb406401f9ac3eae672086c5a`.
Executed once: `wizard-20260917T162626894495Z-1bb6844ca4154b559587100b16183196`.
Start 1.572330308 rad, command 1.4850638454002836 rad, final report 1.535514769 rad.
Reported change -2.1094 degrees for -5 requested; shortfall 2.8906 degrees.
Other joint reports unchanged. Endpoint verification failed; no further command
was sent in this run. The final pose is below the proposed validation command,
but is not a passed conditioning endpoint. A subsequent independent experiment
requires fresh baseline, reviewed stability/response and separately screened path.

## First held-out candidate result — 2026-09-17 16:33 UTC

38 focused tests passed before execution. Fresh identity-matched preflight:
`wizard-20260917T163304753280Z-673ef995de014fd7abb5ae3dc5930b8d`.
The independent experiment began from the unchanged reported conditioning pose;
the earlier conditioning failure was not relabeled or automatically chained.

One native command, with no return/retry:
`wizard-20260917T163336056001Z-71f29a765c9e44d2a3d6d1edb0d1bf61`.
Frozen candidate SHA256:
`94285286e6a0d95735bf75ced9a8ab1337129ed6a54b35495ad58f6dc3d7df3f`.

| Quantity | Result |
| --- | --- |
| Starting reported elbow | 1.535514769 rad |
| Desired elbow | 1.5633309535598299 rad |
| Transmitted elbow target | 1.5543315991196598 rad |
| Final reported elbow | 1.563126423 rad |
| Desired endpoint angular residual | -0.01171874 degrees |
| Desired endpoint model-derived position error | 0.06463335 mm |
| Wire-target angular residual | +0.50390629 degrees |
| Wire-target model-derived position error | 2.77922174 mm |
| Desired reported endpoint verdict | DESIRED_REPORTED_ENDPOINT_VERIFIED |
| Strict wire-target verdict | COMPLETION_DEADLINE_EXCEEDED |

Other joint reports were unchanged. Compared with the training trial's desired
endpoint error of 2.843854 mm, this new trial is substantially closer; the starting
pose and travel amplitude differ, so this is preliminary local evidence rather
than a controlled repeatability estimate or full-range qualification.

Trace analysis export:
`wizard-20260917T163348740272Z-66cc00a3bdab4b1bac0d17b80f7eabc6`.
Last reported change was 1.322 seconds after dispatch, followed by 8.585 seconds
of unchanged readings. Seven final-two-second observations had zero reported span.
Servo acquisition freshness and physical tip accuracy are not established.

Next: freeze this candidate unchanged. Separately prepare a new below-target
baseline within its admitted range, review that preparation's result, then perform
another ascending validation. Do not resend from the present above-command pose:
that would change approach direction. Require repeat evidence before task use;
retain both verdicts and all failed trials. No global compensation is enabled.

## Repeat preparation — 2026-09-17 16:35 UTC

Fresh preflight `wizard-20260917T163438509865Z-b0f5ef33b0f74a7fb32ca7b9ef97e62d`
confirmed the prior endpoint unchanged. One independent preparation lift was sent:
`wizard-20260917T163506671259Z-de320d9a030045a3a03e24bfa4bff6a7`.
Start 1.563126423 rad, wire target 1.4758599604002836 rad, final reported elbow
1.523242922 rad. Reported travel -2.28515628 degrees; remaining shortfall
2.71484372 degrees. Other joints remained unchanged; strict endpoint failed.

Analysis `wizard-20260917T163520728183Z-8b86917311a34ab8a9dc927ed73bd9f7`
found the last reported change at 4.180 seconds and an unchanged 5.529-second tail.
Seven final-two-second readings had zero span. This does not prove sensor freshness.

Independent read-only candidate preflight:
`wizard-20260917T163521310400Z-0b126856b41b438aabe99022f042c06a`.
Result: CANDIDATE_START_OUTSIDE_LOCAL_RANGE. The observed start is approximately
0.1007 degrees below the fixed 1.525 rad lower limit. No validation command was
sent, and no automatic return or repeated positioning command followed.

### Next experiment design, not live authority

Evaluate a separately versioned start-range extension to 1.520 rad, retaining the
same desired target, command offset, direction, speed, acceleration, 12 mm sampled
displacement cap and endpoint tolerances. This changes the experiment's admitted
starting range, not its accuracy acceptance. Preserve the original candidate and
hash; do not silently edit it or call the new range previously validated.

Before execution, test boundary rejection and path screening over the proposed
range, verify current feedback, and retain the extended experiment identity in
exports. One successful extension trial would support the unchanged offset over
a somewhat longer approach, but would still not establish full-range compensation.
Prefer this explicit, reviewed experiment to repeated failed repositioning in an
attempt to force an exact preparation pose. No extension is enabled by this note.

## Start-range extension implemented and tested — 16:37 UTC

The separate v2 candidate retains the v1 parent hash, fixed wire/desired targets,
speed, acceleration and accuracy tolerances. Only its minimum start changes to
1.520 rad. CLI selection is explicit:
`--elbow-only --elbow-local-validation --extended-candidate-start`.
Without `--execute` it remains read-only. Original v1 remains unchanged.
41 focused tests passed, including identity preservation, both boundary rejections,
41-point path screening at seven representative starts/boundaries, one-send behavior
and separate desired/wire verdicts.

Fresh preflight: `wizard-20260917T163719286164Z-fbc810271b154988a33a386e6bfbdc0c`.
Single live trial: `wizard-20260917T163737713843Z-3c0902dc1b764c719db050fa8ae20f84`.
Candidate SHA256: `93fae9c481489956101ce4f63b42e16a55edab4cf10423d74742cd4ba829b103`.
Start 1.523242922 rad; unchanged wire target 1.5543315991196598 rad;
final report 1.563126423 rad, exactly the first validation's reported final angle.
Desired residual -0.01171874 degrees / 0.06463335 model-derived mm; desired reported
endpoint verified. Wire-target residual +0.50390629 degrees / 2.77922174 modeled mm;
strict wire endpoint still COMPLETION_DEADLINE_EXCEEDED. Other joints unchanged.
No return or retry followed.

Trace export `wizard-20260917T163748762380Z-58e22741fb9b44fe8c45a208db337105`:
last reported change 1.316 seconds, unchanged tail 8.592 seconds, final seven
observations zero span. Two held-out ascending trials now reach the same reported
endpoint from different starting poses using the frozen correction. This supports
local usefulness, not independent physical accuracy or arbitrary-target performance.

Next prioritize a nearby *different desired endpoint* to test local generalization
before coordinated movement. Keep ascending direction and speed fixed; define the
target and model identity before testing, screen preparation and validation paths,
and report both errors. Do not extrapolate this ascending offset to descending
elbow motion, whose much larger shortfall remains unresolved. A bounded descending
model/approach strategy is needed before a reliable press/retract cycle can use both
directions. Keep contact and camera work deferred.

## Predeclared nearby-target experiment (v3)

Test desired elbow 1.5533309535598299 rad, wire command 1.5443315991196598 rad:
both are 0.01 rad below the original pair, preserving the trained offset exactly.
Use ascending approach from [1.520, 1.540] rad, speed 20, acceleration 1,
the unchanged 12 mm sampled path cap and existing endpoint tolerances. v3 has a
separate hash and v2 parent; scoring is bound to its own desired target.
Select explicitly with `--elbow-only --elbow-local-validation --nearby-candidate-target`.
Fresh screened preparation and review remain separate from validation. One held-out
trial is intended; no automatic retry or return. This tests a new endpoint rather
than fitting to it. Retain any failure and do not retune from the result in place.

## Nearby-target result — 16:41 UTC

42 focused tests passed. Added explicit verification that v3 results are scored
against v3's desired endpoint, not the original target. Original identities remain
unchanged. Preparation export:
`wizard-20260917T164028812312Z-ede1be83a00144d48545ebaea698d838`.
It again reported 1.523242922 rad from 1.563126423 rad, with strict wire failure
retained. Analysis `wizard-20260917T164039651856Z-e217f6cca16d48fa8bdf12c76f70b72b`
reported an unchanged 8.600-second tail. No automatic chaining occurred.

Fresh v3 preflight: `wizard-20260917T164040307638Z-b3012b6d07614d09b2f85a3a82199e6c`.
Live validation: `wizard-20260917T164057496395Z-d3deef3ce63e41c08c436f4ed79a81b7`.
Candidate SHA256: `dd28cc0fa2eab07d49c38e7be027323a6c390275e6b7bf3c2995fa58e156c200`.
Final reported elbow 1.552388557 rad. Desired residual -0.05399535 degrees,
model-derived position error 0.29780439 mm: DESIRED_REPORTED_ENDPOINT_VERIFIED.
Wire residual +0.46162968 degrees / 2.54605276 model-derived mm:
COMPLETION_DEADLINE_EXCEEDED. Other joint reports unchanged; no retry/return.

Analysis `wizard-20260917T164109606577Z-40035d1cc5c3494191411878b6c25498`:
last reported change 3.892 seconds; unchanged tail 5.821 seconds; final seven
observations zero span. This new target passes the existing desired-state band
without retuning the offset. Three held-out ascending trials now cover two desired
targets, with 0.065–0.298 mm model-derived residuals. This is local reported-state
evidence only, not physical tip measurement or continuous-route qualification.

Next: derive a separate descending candidate from retained preparation traces and
define its local validation before execution. Do not reuse the ascending correction
for lifting. The current reported elbow is 1.552388557 rad; reacquire it before
planning the next leg. Preserve existing successful ascending evidence unchanged.

## Predeclared descending experiment

Use the residual repeated in preparation exports at 16:35 and 16:40:
1.523242922 - 1.4758599604002836 = 0.047382961599716555 rad.
Freeze desired 1.530 rad, command 1.4826170384002835 rad, decreasing approach,
start interval [1.550, 1.565], speed 20, acceleration 1. This target is distinct
from the training outcome and tests the constant-residual hypothesis locally.
It is not a fit to the upcoming validation result. Starting at the last report,
the wire request is about -4 degrees, inside the previously reviewed 5-degree
lift envelope. Screen all 41 samples with a 28 mm displacement cap. Retain the
existing 6-degree lift excursion stop and unchanged endpoint acceptance/dwell.
No torque, firmware, PID, or tolerance adjustment is involved.

Select `--elbow-only --elbow-local-validation --descending-candidate` explicitly;
default is read-only. Perform one screened trial and review both target errors,
not an automatic return or correction loop. A miss must remain a miss; do not
infer a valid descending model from ascending results.

## Descending v1 held-out result — 16:44 UTC

44 focused tests passed before the live trial, covering separate fit identity,
direction, interval boundaries, sampled displacement and unchanged acceptance.
Preflight: `wizard-20260917T164330593149Z-23bcfd13de924af19ca470eba3f7eb4e`.
One live trial: `wizard-20260917T164349530197Z-3680dd0bc2134fbbbdc37b07ec807f84`.
Candidate SHA256: `8dcb1cb97bf2538f1c2fcfb25288eea558ed6a5ee4d01d9b775386185acf52ae`.

Start 1.552388557 rad; desired 1.530 rad; wire 1.4826170384002835 rad;
final report 1.532446807 rad. Desired error +0.14019171 degrees / 0.77320929
model-derived mm, outside the unchanged 0.5 mm band: DESIRED_ENDPOINT_NOT_VERIFIED.
Wire error +2.85503543 degrees / 15.74495452 modeled mm; strict wire outcome
COMPLETION_DEADLINE_EXCEEDED. Other reported joints unchanged. No retry/return.

Analysis: `wizard-20260917T164405098360Z-43d2350018154c969aac9e011a3e87be`.
Last reported change 0.910 seconds; unchanged tail 8.907 seconds; final seven
samples zero span. No evidence here that extending timeout would remove the miss.
No independent physical measurement was made.

This descending correction is promising but not qualified. Its observed residual
0.04982976859971644 rad differs from training's 0.047382961599716555 rad by
0.002446807 rad. Do not silently fit v1 to this validation point or relabel it.
Next evaluate a separately frozen revised estimate using both retained operating
points, explicitly treating this trial as training for that revision. Validate the
revision on new movements, preserving the prior miss as held-out failure for v1.
Ascending approach preparation may use the already tested local candidate only
after fresh baseline/path review. Do not enable bidirectional task execution yet.

## Predeclared descending v2

Use equal weight for the two distinct observed operating-point residuals:
(0.047382961599716555 + 0.04982976859971644)/2 = 0.0486063650997165 rad.
Duplicate preparation observations do not receive extra weight. Desired endpoint
remains 1.530 rad; transmitted target becomes 1.4813936349002835 rad. Preserve
v1 and its failed verdict. The former held-out v1 result is explicitly training
for v2, so it cannot validate v2. Range, speed, acceleration, path cap and all
accuracy tolerances remain unchanged. Select with the additional
`--revised-descending` flag. Use one independent new validation after reviewed
ascending preparation; no automatic chaining or return. This midpoint estimate
is a local hypothesis, not proof that residual is constant.

## Descending v2 result — 16:47 UTC

46 focused tests passed. Ascending preparation preflight:
`wizard-20260917T164649449937Z-9af1ce07c83f4d61b997460131ad7e8a`;
live preparation `wizard-20260917T164706353433Z-856f8792847b494fa047273ad9232888`
again passed the desired reported endpoint at 1.552388557 rad / 0.29780439 modeled
mm error. Its strict wire failure remains separate.

Fresh descending v2 preflight:
`wizard-20260917T164717025211Z-58282f37b8954401993be951d56c2532`.
Live trial: `wizard-20260917T164736441432Z-177f2db2f882449ba8e515aad21dd60b`.
Candidate SHA256: `15a1b355232e89620d6f0641d7001993b7ecc4b063071ea06f5683063e560d76`.
Final reported angle again 1.532446807 rad; desired residual +0.14019171 degrees /
0.77320929 modeled mm: DESIRED_ENDPOINT_NOT_VERIFIED. Strict wire failure retained.
Other joints unchanged. Analysis export:
`wizard-20260917T164754518165Z-04c737efaec548ef8dfd64a8f555d1a8`:
last change 1.212 seconds; unchanged tail 8.614 seconds; seven final samples zero span.

The same baseline produced the same reported final position for two distinct
commands: 1.4826170384002835 and 1.4813936349002836 rad (predicted goal counts
1991 and 1990 respectively, final reported reconstructed count 2023). This does
not support a locally unit-slope additive-offset model at this resolution. It is
consistent with a local plateau/deadband or quantized response, not proof of its
physical cause. No repeated command, automatic return or tolerance change followed.

Next replace incremental offset tuning with a predeclared bounded response-map
experiment: compare distinct command counts over the already reviewed corridor
from comparable starting poses, retain failed trials, and estimate monotonicity,
plateaus and useful endpoint spacing. Use that evidence to choose reachable
noncontact task waypoints or a local inverse lookup. Do not relabel the 0.773 mm
miss as a passed 0.5 mm test, and do not extrapolate encoder-derived accuracy to
the unmounted stylus. The current reported elbow is 1.532446807 rad.
