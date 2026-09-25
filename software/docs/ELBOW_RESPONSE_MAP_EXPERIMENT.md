# Fixed-start elbow response mapping

2026-09-17. Noncontact controller-state experiment; no camera or tool calibration.

## Evidence and reason for changing approach

Offline map export:
`wizard-20260917T165013115060Z-256abd3929c44379b233c60a73e90486`.
The four verified trial archives produce six pairs but only two comparable pairs.
Two preparations repeat the same command and endpoint from 1.563126423 rad.
Two descending validations start at 1.552388557 rad and use different commands
(1.4826170384002835 and 1.4813936349002836 rad), yet both end at 1.532446807 rad.
The four cross-start comparisons are excluded. Pooling those starting poses into
a constant offset is not justified. The midpoint candidate failed held-out testing.

The new offline reviewer verifies archive hashes, retains source/command/desired/
reported values and verdicts, and compares matching six-joint baselines, direction,
speed and acceleration. It distinguishes repeated commands, reported plateaus,
monotonic and nonmonotonic pairs. It never creates an inverse model or live authority.
Host-observed plateaus may include cached samples; physical settling remains unknown.

## Next finite experiment

1. Reacquire the current pose. Prepare the previously tested ascending v3 endpoint
   only if its baseline and sampled path pass; review desired-endpoint outcome.
2. Use the observed starting elbow 1.552388557 rad for comparisons, keeping all
   other reported joints, speed 20 and acceleration 1 unchanged. If preparation
   differs, record another group rather than treating it as the same start.
3. Predeclare one additional descending command: 1.4758599604002836 rad, with
   desired observation reference 1.530 rad. This wire angle has been used before,
   but not from this matched baseline. It is about 4.385 degrees below that start,
   within the previous 5-degree lift envelope. Screen the full new path before
   execution; retain the 28 mm displacement cap and existing excursion/feedback
   guards. This is an identification sample, not a promise of endpoint arrival.
4. Send once, retain both error measures and time series, and stop for review.
   Compare with the two same-start commands. Do not automatically return, repeat,
   increase torque, or widen accuracy tolerance.
5. If this yields a different monotonic endpoint, use the resulting bracket to
   propose a local inverse lookup for a subsequent held-out trial. If it remains
   flat or becomes inconsistent, do not keep adjusting an offset; review reported
   resolution, command conversion and approach-dependent behavior first.

Do not run multiple mapping points automatically. Preserve old failures and the
original candidates. A fitted point is training, not validation. Qualify a useful
bidirectional pair on new trials before integrating noncontact ghost press/retract.

## Offline reproduction

Run `software/scripts/review_elbow_response_map.py` with 2–12 native elbow trial
export IDs. It writes a verified `elbow-response-map.json` attachment in the workspace
export folder without opening any device. Eleven focused map/trace tests passed
when this report was introduced. The live mapping sample above is not yet executed.

## First mapping sample completed — 16:53 UTC

54 focused tests passed. Explicit CLI mode:
`--elbow-only --elbow-local-validation --mapping-sample` (read-only unless executed).
The mode rejects starts outside 1.552388557 +/- 1e-8 rad, preserves the existing
28 mm sampled path cap, and sends once. It is marked identification, not a fitted
correction. All six reported joints were checked against the earlier baseline.

Preparation preflight: `wizard-20260917T165216311989Z-4a23258f4649452182dfe61f55397a56`.
Preparation live: `wizard-20260917T165233201557Z-8e61d053d46f4edea4faf0db9d7a82b5`.
Ascending desired endpoint verified again at 0.29780439 modeled mm residual.
Mapping preflight: `wizard-20260917T165257877102Z-2ab7f86ff90943d68580ab55fb65cb49`.
Mapping live: `wizard-20260917T165325102147Z-5e47538b48ae41288ac4e22ea0337b74`.

Start 1.552388557 rad; command 1.4758599604002836 rad; final report 1.529378846 rad.
Against desired 1.530 rad: -0.03558950 degrees / 0.19628956 model-derived mm,
DESIRED_REPORTED_ENDPOINT_VERIFIED. Wire-target error 16.91035394 modeled mm,
COMPLETION_DEADLINE_EXCEEDED, separately retained. Other joints unchanged.
No automatic return, retry or tolerance change.

Three-point fixed-start response-map export:
`wizard-20260917T165340211288Z-57d5945e9e1d468c987f570723e254aa`.
All three pairs are comparable. Two close commands share one endpoint; the wider
command step moves the reported endpoint in the expected direction. The measured
pairwise gains are approximately 0.45/0.55 rather than an assumed unit gain. This
supports local lookup/reachable-point selection, not a universal additive offset.

## Next: freeze and validate the useful lookup point

Do not fit a new interpolated target solely to reduce 0.196 mm residual. Preserve
this command/desired pair unchanged and run a new held-out repeat after separately
reviewed ascending preparation. The identification sample is training evidence;
it cannot also prove the lookup's repeatability. Preserve both endpoint verdicts.
If that repeat passes, the ascending v3 point and this descending point provide a
candidate local bidirectional pair. Before autonomous cycling, bind the desired
endpoint separately from the compensated wire target in progression logic, test
fault stops, and validate the bounded path in both directions. This is an elbow-only
noncontact cycle, not yet keyboard-coordinate ghost typing or physical tip accuracy.

## Held-out repeat completed — 16:55 UTC

Ascending preparation preflight:
`wizard-20260917T165427272382Z-2df5c34612034011a4083ab0198c3f2b`.
Live preparation `wizard-20260917T165444481148Z-8052bae4d7e74550b842ceb506217f37`
again reached 1.552388557 rad and passed desired-state verification at 0.29780439
modeled mm error. Fresh mapping preflight:
`wizard-20260917T165458316294Z-4c28bee3c21346aaa17e9822c9c7def0`.
Held-out descending repeat:
`wizard-20260917T165516631340Z-b869774fbbed441d99ff90279ecdefd8`.
Unchanged command 1.4758599604002836 rad again reached 1.529378846 rad. Desired
1.530 rad error was -0.03558950 degrees / 0.19628956 modeled mm, verified with
unchanged dwell/tolerances. Strict wire-target timeout remains separately recorded.
Other reported joints unchanged; no automatic return or retry.

Verified repeat comparison:
`wizard-20260917T165530684761Z-0433d51869a6446b9ff779d61200c7d9`.
Same six-joint baseline, speed, direction and command; zero difference in final
reported endpoint. This is held-out repeat evidence for the selected lookup point,
not independent physical measurement or general-range qualification.

## Next implementation: finite compensated cycle

The tested pair is ascending v3 (desired 1.5533309535598299, command
1.5443315991196598) and descending lookup (desired 1.530, command
1.4758599604002836). Freeze these identities and source evidence before integration.
Keep the diagnostic transaction's strict wire verdict unchanged. Add a separate
compensated-task outcome that verifies its bound desired endpoint using the same
0.5 mm/.02 rad/three-sample/500 ms criteria. It must not treat arbitrary timeout as
success: feedback gaps, invalid/model-inconsistent data, unexpected joint movement,
cancellation, uncertain sends or cleanup failure always prevent progression.

Implement and test the decision on retained exports and synthetic faults before
allowing a finite two-leg cycle. Validate fresh start and screened path separately
for each leg; no queued moves, automatic retry or recovery return. Bound execution
to the tested pair and preserve per-leg request, wire goal, desired goal, observations,
both verdicts, model/config hashes and export identities. This local elbow cycle
is a precursor to—not a substitute for—the coordinated ghost-key route.

## Clean compensated completion implemented (software only)

Inspection found historical diagnostic runs can retain
`TRANSACTION_INTERRUPTED_OR_UNCERTAIN` when a final feedback request meets the
strict wire-target deadline. Their earlier desired-endpoint observations remain
useful experimental evidence, but those terminal reports MUST NOT authorize an
automatic next leg. Do not whitelist a timeout because a desired endpoint appeared
earlier in its trace.

`CartesianTransaction` now has an opt-in `compensated_endpoint` mode restricted to
the tested ascending v3 and descending lookup modes. It stops during clean feedback
when the desired endpoint meets the existing dwell/tolerances, with a distinct
`COMPENSATED_REPORTED_ENDPOINT_VERIFIED` state. The wire result is not relabeled.
Reservations bind the candidate identity and desired goal into configuration hashing.
Default diagnostic behavior remains unchanged. Native CLI does not yet expose this
mode, and no physical cycle was sent for this checkpoint.

`compensated_elbow_progression.clean_compensated_completion` rejects timeouts,
transport errors, missing acknowledgment, cleanup failure and non-task outcomes.
It is an internal outcome rule, not authority to replay a saved archive. Tests cover
clean completion in both directions before timeout, one-use behavior, command/desired
separation, configuration binding, cancellation, missing/inconsistent feedback,
unexpected joint change and rejection of unqualified correction modes.

66 focused transaction/progression tests passed; existing ghost endpoint/export and
trace regressions also passed (25 tests). Next compose the finite two-leg coordinator
with per-leg fresh admission, verified export publication before progression, and
tests proving no second command after any failure. Then expose an explicit native
cycle mode and validate it physically; this checkpoint does not qualify that cycle.

## Finite coordinator implemented (no native execution yet)

`CompensatedElbowCycle` now owns a one-use, two-leg sequence: ascending v3 then
descending lookup. Device and export operations are injected; there is no default
sender. Each result must have the exact expected candidate/command/configuration,
clean compensated completion and confirmed receipt cleanup. Each full report must
be durably exported and verified before progression. Failure, exception, cancellation
or unverified export prevents the second leg; no replay, retry or recovery move.
The prior endpoint is passed to the next leg adapter for fresh pre-dispatch checking.

27 coordinator/progression tests passed, plus 68 local-motion and ghost/export
regressions. These use incapable simulated adapters, not live hardware. Tests prove
publication order, single-use behavior and no second command after first-leg faults.

Next implement the native adapter holding transport ownership across the whole
cycle, with fresh identity/pose acquisition and prior-endpoint continuity checks
before each reservation. Bind the tested fixed non-elbow posture as well as elbow
range; reject mismatches rather than executing from an unrelated pose. Use verified
workspace exports as the publisher and retain a final cycle index. Only after
adapter fault tests and read-only preflight should an explicit finite native run
be performed. No native cycle or physical motion occurred in this checkpoint.

## First native finite cycle verified — 17:02 UTC

Native adapter now holds the transport mutex through both legs and publications.
Each leg independently acquires identity-matched fresh feedback, checks the tested
non-elbow posture, and screens its path before creating a one-use reservation.
Second-leg baseline must match the preceding reported endpoint. No saved archive
can initiate or resume a run. CLI `software/scripts/bench_compensated_elbow_cycle.py`
defaults to read-only first-leg preflight; `--execute` explicitly runs at most two legs.

55 adapter/coordinator/progression/transport tests passed. Preflight:
`wizard-20260917T170220973253Z-6f7f0ec5ff334d8b8363fdbcb3132de6`.
Live cycle index:
`wizard-20260917T170234035577Z-4a94a1b4ec74450bac3e73c7fbaee116`.
Outcome: LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED.

| Leg | Export | Desired modeled error | Observation duration |
| --- | --- | --- | --- |
| Ascending | wizard-20260917T170231734897Z-39b8fc1c4a94432383d65c7a947566c1 | 0.29780439 mm | 2.11185 s |
| Descending | wizard-20260917T170233983744Z-2ce6109803af4a468c5f4391e4e2d535 | 0.28845993 mm | 2.03779 s |

Each sent exactly once and ended COMPENSATED_REPORTED_ENDPOINT_VERIFIED with
`error: null`; no diagnostic timeout or uncertain final request was used for
progression. First leg export was verified before second-leg admission. Wire-target
errors remain 2.54605 / 17.39492 modeled mm and are not relabeled as wire arrival.
The second final reported angle differs slightly from the earlier long-observation
trial but meets the unchanged desired-state dwell and tolerance; no zero-error claim.

Next run a small finite repeat assessment of this same pair, retaining per-cycle
results and endpoint variation, before extending its scope. Then bridge the local
motion evidence into a separately screened coordinated approach/press/retract route.
This successful elbow cycle does not establish board registration, constant-tip
orientation, hypothetical 100 mm stylus clearance, or real keyboard/phone input.

## Automatic repeat and ghost approach bridge — 17:05 UTC

Second native cycle passed:
`wizard-20260917T170351466492Z-9972240094a04943b6f344ec2feccb73`.
Leg exports: `wizard-20260917T170349357399Z-dee14c2f0c8d4d679a677ccb3226c781`
and `wizard-20260917T170351412805Z-47e263f00dd1450292a2ec9dc85c9958`.
Both clean, same final reported angles as the first automatic cycle: 1.552388557
and 1.530912826 rad. Desired modeled errors remain 0.29780439 / 0.28845993 mm.
This establishes two finite successful automatic cycles, not arbitrary repetition
or physical tip accuracy. Stop repeating merely to optimize these residuals.

New offline `product_ghost_approach` projects a saved current pose to the first
full-size keyboard ghost waypoint, preserving actual reported gripper rather than
using the route's old placeholder. It divides the approach into <=5 mm translation
and <=0.025 rad pitch/roll increments, <=64 legs, and screens controller-reference
interpolation with <=1024 samples per leg. No compensation is extrapolated or native
request generated; hypothetical 100 mm tool and frame limitations remain explicit.

Fresh saved pose: `wizard-20260917T170532158579Z-3070ee04d7c44af89f865a0d3408b203`.
Product source: `wizard-20260917T152617941503Z-4ec783651cc64029a66e4a7305b07139`.
Approach export: `wizard-20260917T170544349443Z-90eb3bdcf1d44a24b10be3b306ae525e`.
APPROACH_REFERENCE_PASS_NOT_EXECUTABLE: 192.8404 mm, 39/39 reference legs passed.
Two focused tests cover no-authority/tool/gripper preservation and stop on reference
failure. This is sampled four-joint reference feasibility, not collision clearance,
installed frame correlation, continuous timing or qualification of other joints.

Next review the approach's joint excursion and hypothetical tool sweep, select the
first small coordinated commissioning leg, and validate that separately. Do not
dispatch the 193 mm route or apply the elbow-only lookup outside its tested posture.

## Approach joint and hypothetical tool review — 17:08 UTC

Enhanced offline screening now records all-sample joint extrema/excursions, rejects
provisional joint-limit violations and reports the hypothetical -100 mm hand-TCP
tool-tip sweep using the verified static bundle's URDF. This is vendor-base model
space, not the installed board frame. No tool mounting or collision clearance is
inferred. Twelve approach/interpolation tests passed, including rejection and sweep
labeling checks.

Export: `wizard-20260917T170817165722Z-9dd8fd21d5d54d038c97d6ec01d64042`.
The full 39-leg approach stays within provisional limits but requires maximum
excursions of approximately base 2.15, shoulder 34.77, elbow 20.97, wrist pitch
55.34 and wrist roll 1.14 degrees. Maximum adjacent model-sample joint change
is 0.0303 degrees. This is smooth numerical interpolation, not verified real motion.

Hypothetical tip starts at [342.116, 2.518, 177.568] mm and ends at
[416.996, -15.000, -0.098] mm in VENDOR_BASE_UNREGISTERED. Near-zero modeled
tip height reinforces why this full route is not live-admissible without frame/tool
and clearance qualification. Do not interpret that value as real board penetration
or as a calibrated board contact.

The first segment changes the modeled joints by [-0.0665, +0.4281, +1.3075,
-1.7536, -0.0293] degrees and ends at controller pose
[347.74377, 0.13003, 222.45509, 0.0119573] (XYZ mm, pitch rad).
Next derive that small coordinated trial from a fresh pose, preserve measured
gripper, bind its exact goal/path to one-use admission, and verify all affected joint
responses. Do not extrapolate elbow-only compensation. The remaining approach
and hypothetical contact stay offline. No physical movement occurred in this review.
