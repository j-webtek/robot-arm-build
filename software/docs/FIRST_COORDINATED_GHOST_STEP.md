# First coordinated ghost-approach commissioning step

2026-09-17. One noncontact 5 mm controller-frame step; not keyboard contact.

Latest checkpoint: hypothetical stylus review at 18:14 UTC quantifies wrist arc
and remaining approach, distinguishing PARK from key HOVER. No new movement.
Descending correction passed two targets at .108677 modeled mm. Historical
"next" instructions are superseded by CURRENT_TYPING_AND_TAPPING_GOAL.md.

## Implementation

`ghost_first_step.preview_first_step` derives a 5 mm segment toward the reviewed
first ghost hover from fresh feedback. It admits only the tested starting posture,
preserves reported roll/gripper, screens the T104 reference trace and caps each
arm-joint change at 3 degrees within provisional limits. No local elbow correction
is extrapolated. The existing durable one-use reservation, receipt checks, feedback
validation and endpoint tolerances are reused. Explicit CLI:
`bench_cartesian_vertical.py --ghost-first-step` (add `--execute` for one move).
Elbow/compensation/alternate step modes cannot be combined with this selection.
50 focused tests passed before execution.

## Live evidence

Preflight: `wizard-20260917T171122877218Z-2d216b9c814f46e4b6891d03a5ac3acf`.
Live trial: `wizard-20260917T171146908344Z-931dcb7b7843476c96b97cb17494d31b`.
Outcome COMMAND_OUTCOME_UNCERTAIN. A later feedback request failed with TIMEOUT
in REQUEST_SEND; cleanup was confirmed. Earlier retained samples were available,
but no completed endpoint was verified. No retry, return or next segment followed.

| Joint | Requested change (deg) | Reported change (deg) |
| --- | --- | --- |
| Base | -0.0672 | 0 |
| Shoulder | +0.4331 | +0.4395 |
| Elbow | +1.3218 | +1.9336 |
| Wrist pitch | -1.7732 | -0.8789 |

Roll/gripper reports remained unchanged. Last retained endpoint error was
6.112501 mm in controller-model space; pitch error 0.026396 rad. Shoulder error
was small, while elbow and wrist errors compounded. Do not treat receipt, observed
motion or individual joint progress as successful Cartesian arrival.

Read-only recovery export:
`wizard-20260917T171159057564Z-947c740e7e6246bca78d6f063e6d88eb`.
Feedback SUCCEEDED and matched the final retained joint values:
b=.001533981, s=.007669904, e=1.563126423, t=.03834952,
r=.01994175, g=3.138524692 rad. The preview rejected this new posture as outside
the original first-step starting scope; no further movement was attempted.
This restores communication evidence, not a retrospective successful trial.

## Next actions

1. Analyze the retained multi-joint trajectory and feedback timing. Separate the
   transport failure from the persistent geometric residual; do not fix one by
   hiding the other or widening endpoint tolerances.
2. Plan a new bounded diagnostic from the actual current pose, not an automatic
   return to old elbow-only scope. Qualify wrist-pitch response and elbow response
   in this coordinated posture before selecting a correction or approach strategy.
3. Preserve the full keyboard route and 100 mm hypothetical tool model offline.
   The first step itself is not yet qualified; do not advance along the 39-leg path.
   No camera, stylus attachment, real board registration or physical tip accuracy
   was established by this experiment.

## Saved-trace review — 17:14 UTC

Added `coordinated_trace_review` and an offline verified-export CLI. The review
checks timestamp order, complete finite joint data and FK consistency; it retains
per-joint residuals, last reported changes, transport failure metadata and source
hashes. Counterfactual FK substitutions are explicitly model-only, not independent
measurements or fitted compensation. Two focused tests passed.

Analysis export: `wizard-20260917T171410784637Z-23925e97d36d4524abd2e9dc8fe437e7`.
XYZ residual is approximately [-0.441, +0.407, -6.083] mm. Shoulder, elbow and
wrist pitch last changed at 0.504 seconds after dispatch; each remained unchanged
for the following 5.849 seconds of retained observations. The failed request later
timed out during REQUEST_SEND after 814.676 ms with an 0.8-second I/O budget and
confirmed cleanup. It does not explain the preceding geometric error. Acquisition
timestamps are still absent, so identical host samples do not prove physical settling.

Model-only substitutions quantify priorities: setting only elbow to its intended
angle leaves 2.754 mm error; setting only wrist pitch ideal leaves 3.439 mm; correcting
only shoulder leaves 6.076 mm. These effects are coupled, not additive error shares.
Observed elbow residual +0.612 degrees and wrist-pitch residual +0.894 degrees
must both be addressed for a reliable coordinated endpoint. No compensation was
fitted or hardware moved during this analysis.

Next define a single wrist-pitch identification command from the newly observed
posture, with the other joints left uncommanded, fresh admission and full trace
export. Keep command direction/magnitude predeclared; preserve any miss and do not
automatically retry. Use its evidence to distinguish wrist response from Cartesian
coordination effects, then validate a local correction on a new movement before
another coordinated step. Transport timeout recovery stays a separate concern:
missing/uncertain feedback must continue stopping progression.

## Isolated wrist-pitch trial — 17:17 UTC

Added exclusive `--wrist-probe` mode: T101 joint 4 (the existing audited wrist-pitch
mapping), -1.5 degrees relative to fresh feedback, speed 20 and acceleration 1.
It admits only the observed post-approach posture, samples 41 points with a 6 mm
modeled sweep cap, and leaves other joints uncommanded. One-use reservations and
unchanged endpoint tolerances apply. Corrected per-joint reporting so this T101
probe labels wrist, not elbow, as commanded. 45 focused tests passed.

Preflight: `wizard-20260917T171644626710Z-a8278b668a554237861d6cc87fec8e9d`.
Live: `wizard-20260917T171702860871Z-6310136178104360ac605fb7c4263618`.
Start wrist 0.03834952 rad; requested 0.012169581220085053 rad; final report
0.026077673 rad. Requested -1.500 degrees, reported -0.703125 degrees;
shortfall 0.796875 degrees / 2.395163 model-derived mm. All other joints unchanged.
COMPLETION_DEADLINE_EXCEEDED; no arrival claim, retry or return.

Analysis: `wizard-20260917T171729397977Z-4bd0d4acf3ab45dba5961dd84c94675f`.
Last wrist report change at 0.281754 seconds; unchanged tail 9.630586 seconds.
No feedback failures in this trial. Thus wrist shortfall occurs independently of
the earlier coordinated trial's request timeout; acquisition freshness/physical
accuracy remain unmeasured. The current wrist report is 0.026077673 rad, outside
the original probe's starting interval—do not rerun that probe blindly.

Next predeclare a direction-specific local wrist candidate from this evidence,
keeping its training status explicit. Validate on a new desired endpoint from a
fresh, separately screened pose, with separate desired/wire errors. Do not infer
global wrist calibration from one isolated trial or import older corrections from
other postures without checking their scope. Coordinate with elbow correction only
after the wrist candidate has held-out support.

## Predeclared wrist candidate v1

Training residual: 0.026077673 - 0.012169581220085053 = 0.013908091779914946 rad.
New desired endpoint: 0.010 rad; command: -0.003908091779914946 rad. Decreasing
approach, start interval [0.025,0.027] rad, all other joints fixed at the observed
post-approach configuration. Same speed 20, acceleration 1 and 6 mm sampled sweep
cap. The one-point correction is a hypothesis, not validated calibration. Freeze
its hashed identity before the new trial. Keep strict wire verification and desired
wrist verification separate; desired scoring must not accidentally adjust elbow.
CLI selection: `--wrist-probe --wrist-candidate`, read-only unless `--execute`.

## Wrist candidate first held-out result — 17:20 UTC

59 focused tests passed, including explicit wrist-index desired scoring and
unchanged elbow/cycle behavior. Fresh preflight:
`wizard-20260917T172008000898Z-45c8181b5b534cb19e0ac037e475ff3f`.
Live validation: `wizard-20260917T172027466486Z-dbe12cb642b34778992d3ed6407c1d6d`.
Candidate SHA256: `24b4bb51d8e27ff3bd36e1d960134f879264e9aba1801d1967ba7f14f10e0583`.

Start wrist 0.026077673 rad; wire -0.003908091779914944 rad; desired 0.010 rad;
final reported wrist 0.007669904 rad. Desired error -0.13350467 degrees /
0.40127747 modeled mm: DESIRED_REPORTED_ENDPOINT_VERIFIED under unchanged bands.
Strict wire error 1.99389328 modeled mm: COMPLETION_DEADLINE_EXCEEDED, separately
preserved. Runner error was null. All other reported joints remained unchanged.
No automatic return or retry followed; no physical tip accuracy claim.

This is the first held-out pass for this direction/posture, not a full wrist model.
Keep the correction unchanged for repeat validation rather than optimizing its
already in-band residual. The current wrist report 0.007669904 rad is outside the
candidate starting interval. A new, separately screened preparation must establish
a usable above-target pose; do not simply replay the candidate or auto-return.
Then repeat on new evidence before combining wrist and elbow correction in a
coordinated target. If preparation lands elsewhere, retain and review that outcome
rather than silently widening the candidate's admitted range.

## Separate wrist preparation — 17:23 UTC

Added explicit `--wrist-probe --wrist-prepare`: fixed 0.026077673 rad target from
starting wrist interval [0.005,0.012] rad, other reported joints fixed, speed 20,
acceleration 1, 6 mm sampled sweep cap. No compensation or automatic follow-up.
29 focused tests passed. The preview now preserves the exact frozen command at
its final sample rather than accumulating a floating-point interpolation difference.

Preflight: `wizard-20260917T172228713077Z-5c744694b9b5450aac4acc9ef57d3b61`.
Live preparation: `wizard-20260917T172303913398Z-13a00fd9693b413b9b965314393e4228`.
Start 0.007669904 rad, requested 0.026077673 rad, reported 0.01994175 rad.
Requested +1.054687 degrees, reported +0.703125 degrees; endpoint miss 1.056696
modeled mm. Other joint reports unchanged. Strict endpoint failed, no retry/return
or correction validation followed. This is new opposite-direction evidence, not
a passed preparation endpoint. The result is below the original candidate's narrow
[0.025,0.027] starting interval, so that candidate must not be replayed as-is.

Next evaluate a separately identified start-range extension for the unchanged
descending command/desired pair from the now-observed lower starting angle. Keep
the 6 mm sweep cap and existing endpoint tolerances; explicitly label the altered
starting range as new scope and preserve v1. Prefer this bounded comparison over
repeated positioning attempts to force an exact starting angle. Review fresh pose
and retained stability before execution; do not mix this ascending residual into
the descending correction fit.

## Wrist v2 start-range extension and repeat — 17:25 UTC

Explicit `--wrist-probe --wrist-candidate --wrist-extended-start` selects a distinct
v2 identity admitting [0.018,0.027] rad starts. V1 and its hash are preserved.
Command, desired endpoint, correction residual, speed, acceleration, 6 mm sweep
cap and all accuracy/dwell thresholds are unchanged. 49 focused tests passed,
including identity preservation and boundary rejection. No automatic preparation
or return is included.

Preflight: `wizard-20260917T172456968279Z-02efae8b9c9f41d29afe437390f3fb9a`.
Live repeat: `wizard-20260917T172515691586Z-221c87c120204ff0ae0d849632d1a943`.
V2 SHA256: `5842ce328bc927d9b68639c43da1cefc70a738b7473c1f5cabe151d2c9b66e46`.
Start 0.01994175 rad, wire -0.003908091779914946 rad, desired 0.010 rad,
final report 0.007669904 rad. Same endpoint as the first validation, with desired
error -0.13350467 degrees / 0.40127747 modeled mm. Desired-state dwell verified;
other joints unchanged. This is repeat reported-state evidence, not physical accuracy.

Strict wire result remains COMPLETION_DEADLINE_EXCEEDED and runner error is
TRANSACTION_INTERRUPTED_OR_UNCERTAIN from a later diagnostic request. Preserve that
error; this report is NOT clean progression authority despite its earlier desired
endpoint observations. No further movement followed.

Next reuse the clean compensated-completion mechanism for this specifically bound
wrist candidate, so a new trial terminates at verified desired arrival instead of
waiting for the deliberately offset wire target. Test fault-stop behavior and exact
desired-joint binding before native use. Then use a separately screened new-pose
experiment to assess elbow/wrist correction together; old elbow-only posture
qualification cannot simply be assumed after shoulder and wrist changes.

## Clean wrist completion — 17:33 UTC

Implemented opt-in `--wrist-clean`, requiring `--wrist-probe --wrist-candidate`.
It forwards the existing compensated-endpoint policy through native admission;
only named elbow candidates or wrist candidates may enable it. Plain wrist probes
and preparation cannot. Default diagnostic behavior is unchanged. Tests exercise
both wrist candidate versions, separate wire/desired results, one-use dispatch,
missing receipt, reset, late/incoherent/missing feedback, joint drift, unchanged
feedback, deadline and cancellation. 62 focused tests and 17 adjacent regressions
passed without hardware access.

Preparation preflight:
`wizard-20260917T173235230492Z-94cb0c80c7854f338033c8931c8a29a1`.
Preparation execution:
`wizard-20260917T173310112456Z-d3916a1228f74fd0bd83523a42bf7a45`.
The wrist again reported 0.01994175 rather than requested 0.026077673 rad;
1.056696 modeled mm miss, COMPLETION_DEADLINE_EXCEEDED, no runner error and
other joints unchanged. This remains a failed preparation; no automatic chain.

Separate fresh-pose v2 candidate preflight:
`wizard-20260917T173322618642Z-2a8fd9a83a9f4aa1a419201b8176fb12`.
Clean execution:
`wizard-20260917T173331734047Z-db11da2e2b81417dbedb5f0c4affab62`.
Outcome COMPENSATED_REPORTED_ENDPOINT_VERIFIED, acknowledgment true, error null,
five feedback observations. Desired 0.010 rad, command -0.003908091779914946 rad,
reported final 0.007669904 rad. Desired residual -0.13350467 degrees / 0.40127747
modeled mm; other joints unchanged. Separate wire endpoint remains unverified
(1.993893 modeled mm miss). Export verification passed. No return or additional
movement followed. This is local reported-state validation, not tip metrology.

Next: screen a new bounded coordinated experiment from fresh actual posture.
The fixed elbow-only qualification at shoulder zero cannot be silently reused
at this shoulder/wrist pose. Preserve full ghost approach offline until local
coordinated response supports progression.

## Post-wrist coordinated diagnostic — 17:36 UTC

Added explicit `--ghost-post-wrist` scope (not a replay or widening of the original
first-step mode). The starting wrist roll had settled one reported encoder count
below the last wrist trial. Three read-only checks agreed on r=0.018407769 rad:
`wizard-20260917T173542308362Z-a7ccd4f3bfa34930bb815aabd45d30e0`,
`wizard-20260917T173557163343Z-cd96f356694f4b689c68c223497196ba`,
`wizard-20260917T173557954380Z-e885d3dcc53b4f639cec7828079b1bf2`.
The new experiment preserves that exact settled roll instead of commanding a
roll correction. Other starting joints were b=.001533981, s=.007669904,
e=1.563126423, t=.007669904, g=3.138524692 rad. No cause of the small roll change
is established. No accuracy tolerance was relaxed.

51 focused tests passed, including distinct start-scope rejection and simulated
arrival. Preflight `wizard-20260917T173624070561Z-0387ee5b0d2546d58697098f6daf3a56`
screened 93 reference samples, a 5 mm translation and less than 3 degrees per
arm joint. Roll/gripper preserved, speed coefficient .05, no compensation.
The CLI now removes a generic preview if the named preview fails, avoiding a
misleading nested pass in a rejected preflight.

Live export: `wizard-20260917T173649895803Z-4dd31f63a6874991aaec1828fb30aaf1`.
Analysis: `wizard-20260917T173709726429Z-6beaea1e9e734e62a188285d1a87a81d`.
Outcome COMPLETION_DEADLINE_EXCEEDED; error null; 32 feedback samples, no feedback
failures. Desired [349.780340, .116059, 216.976964] mm. Final modeled residual
[-.469243, +.419778, -3.640647] mm, magnitude 3.694687 mm. Pitch residual .017079 rad.

| Joint | Requested change (degrees) | Reported change (degrees) | Residual (degrees) |
| --- | ---: | ---: | ---: |
| Base | -.068880 | 0 | +.068880 |
| Shoulder | +.479226 | +.439453 | -.039773 |
| Elbow | +1.250130 | +1.582031 | +.331902 |
| Wrist pitch | -1.741096 | -1.054688 | +.686408 |

Roll/gripper unchanged during the trial. Final reports: b=.001533981,
s=.015339808, e=1.590738077, t=-.010737866, r=.018407769, g=3.138524692 rad.
Changing joints last changed at .466657 seconds; unchanged tail 9.418533 seconds.
This is not proof of independent sample acquisition, but no retained trajectory
evidence suggests that merely waiting longer would resolve the miss.

Next design a bounded correction experiment using these posture-specific
directional residuals. Freeze its desired target and wire command separately,
screen from fresh actual pose, and validate on new data. An additive residual is
only a candidate, not an established general model. Do not automatically return,
reuse the old start scope, or advance the full ghost route after this failed leg.

## Coordinated offset held-out test — 17:42 UTC

Implemented an offline candidate builder using the preceding coordinated trace.
Model: subtract the observed elbow and wrist joint residuals from the desired
joint targets; leave other desired joints unchanged. This is a local direction-
specific additive hypothesis, not regression, learned global calibration or a
physical tip model. Desired and wire poses remain separate in exports and scoring.

Candidate export `wizard-20260917T173947435134Z-3b04138c1a3d4db891f263627cfc88e2`.
Frozen identity `2745b882dd25f533a58d6739ab5580486f78d79ad834fabfec2736c6fbf1aa83`.
Training residuals: elbow .005792777472 rad, wrist .011980086251 rad.
Desired next endpoint [351.272952, .099259, 208.758051] mm; wire endpoint
[351.614368, .099356, 212.640445] mm. Desired translation 5 mm; wire reference
sweep 2.445365 mm across 48 samples, maximum joint excursion 2.463509 degrees.
The corrected command preserves observed roll/gripper and direction of travel.

Added `--coordinated-candidate` for this exact frozen held-out experiment, using
the existing one-use admission and clean desired-endpoint completion mechanism.
No dispatch-time fitting or generic artifact-to-command path. Tests distinguish
wire/desired targets and reject changed posture, invalid training evidence,
feedback gaps, incoherence and joint excursions. 84 focused tests passed.

Preflight `wizard-20260917T174154000311Z-6245ac69aff24f4f96c65c00a4d8362c`.
Live `wizard-20260917T174213158886Z-8fcb3b9899e54b4d8cf53aa200d4ac51`.
Outcome COMPLETION_DEADLINE_EXCEEDED, error TRANSACTION_INTERRUPTED_OR_UNCERTAIN,
33 retained samples. Desired result NOT VERIFIED: 1.725343 modeled mm miss.
Desired residuals in degrees: base +.071701, shoulder +.000852, elbow +.194927,
wrist +.195069. Wire error 5.583132 modeled mm; never confuse it with desired error.
This smaller desired miss than the preceding 3.694687 mm occurred at a different
target/start, so it is not a controlled improvement or a qualified correction.

Analysis `wizard-20260917T174236039249Z-7920a27b10114b68ae63019814f79e4c`:
reported joints last changed at .386324 s with 9.427367 s unchanged tail.
The late failed request was REQUEST_SEND/TIMEOUT, elapsed 46.368 ms, advertised
I/O budget .8 s, cleanup confirmed. Investigate remaining transaction budget
before interpreting this as slow network response; do not extend accuracy limits.

Read-only recovery `wizard-20260917T174236602587Z-3135adb51d924cc0ad76cee17ba47314`
succeeded. The frozen old-start preview correctly rejected the new posture.
Final reported joints: b=.001533981, s=.024543693, e=1.61528177, t=-.03834952,
r=.018407769, g=3.138524692 rad. No return, retry or next route leg followed.

Next compare joint bias across the two nearby coordinated traces, separating
posture/delta dependence from repeatability (not established at identical starts).
Preserve v1 and its failed validation; any revised candidate needs its own frozen
scope, path review and held-out evidence. Physical accuracy remains unmeasured.

## Deadline admission and residual comparison — 17:45 UTC

Inspection identified that the runner checked only whether the deadline had
already expired, allowing a new .8 s-budget feedback request with about 46 ms
remaining. Native transports now advertise their normal feedback budget. The
runner skips starting I/O when the remaining absolute window is smaller, records
remaining/required/deadline values, honors cancellation while waiting and ticks
the unchanged deadline. A non-arrival remains COMPLETION_DEADLINE_EXCEEDED, never
a clean pass. This is prospective scheduling, not suppression of old or new I/O
failures. 58 focused runner tests passed, including real-fault retention, clean
arrival, deadline failure and cancellation during the final wait.

Added a hash-linked offline two-trace comparison, preserving source errors and
separating desired from wire residuals. 16 candidate/comparison tests passed.
Export `wizard-20260917T174530932266Z-a70210a8fc824850aadabd26f1235941` shows:

| Joint | Earlier wire bias (rad) | Held-out wire bias (rad) | Change (degrees) |
| --- | ---: | ---: | ---: |
| Elbow | .005792777472 | .009194895633 | +.194927 |
| Wrist pitch | .011980086251 | .015384684885 | +.195069 |

Starts, targets and requested deltas differ, so these two observations cannot
identify posture, command magnitude, load or timing effects independently. They
do show why the frozen first offset left residual error at the held-out point.
No global model or repeatability claim is established. No hardware motion sent.

Next screen a v2 candidate with the latest locally observed bias at a new bounded
same-direction desired target. Preserve v1 and its failed trial, keep the 3-degree
joint envelope and separate desired/wire scoring, and test on new evidence rather
than interpreting a training fit as success. Do not blindly stack offsets onto
the current position or automatically retry the previous command.

## Coordinated v2 held-out trial — 17:48 UTC

Added separately selected `--coordinated-candidate --coordinated-v2`, preserving
v1 and its identity. V2 uses the latest locally observed wire residuals from the
reviewed plateau; its provenance explicitly retains the source runner error and
successful read-only recovery. It does not reinterpret that source as a passed leg.
Frozen v2 SHA256 `ba64659960c6aec0b134d84ca7541db26849bee25458630a68e8bc16cd47e509`.
57 focused tests passed; 15 candidate tests passed again after pinning the hash.

Preflight `wizard-20260917T174730520132Z-d209a161446b40e389e02a5570eb788d` passed
52 reference samples, unchanged 3-degree joint / 10 mm sweep limits, same-direction
elbow increase/wrist decrease, exact starting pose and preserved roll/gripper.
Desired [353.100064, .085707, 202.529057] mm; wire [353.635934, .085837, 208.064609]
mm. Difference is intentional compensation, not two descriptions of one target.

Live `wizard-20260917T174810942521Z-dd64f15588074210845150057e18113c`:
COMPLETION_DEADLINE_EXCEEDED, error null, 30 feedback rows. Desired error .881280
modeled mm; wire error 6.314254 modeled mm. Desired joint residuals (degrees):
base +.073983, shoulder -.039366, elbow +.064338, wrist +.201745. Roll/gripper
unchanged. Final reported joints b=.001533981, s=.033747577, e=1.636757501,
t=-.065961174, r=.018407769, g=3.138524692 rad.

Feedback scheduling recorded INSUFFICIENT_REMAINING_FEEDBACK_BUDGET with
753948800 ns remaining versus 800000000 ns required. No truncated request was
started; the unchanged deadline ended the trial as a failed endpoint. This is
live evidence for the scheduling fix, not successful endpoint completion.

The smaller residual versus v1 is encouraging but targets/starts differ. Maintain
the failed verdict and do not claim a controlled improvement or physical accuracy.
Next compare wrist response across the nearby same-direction observations and
screen a wrist-focused refinement. Elbow no longer needs the same incremental
adjustment as wrist. No return, retry or next route leg followed this trial.

## Offline response-model comparison — 17:50 UTC

Added a chronological comparison of three simple movement-response hypotheses:
additive bias (reported delta = commanded delta + bias), proportional gain
(reported delta = gain * commanded delta), and affine delta (gain * delta + bias).
Coefficients use only the first two coordinated traces; the third is scored
without refitting. Trace order, command speed, finite FK-consistent data,
direction and reported plateau are checked. Source failures are retained.
Five model/comparison tests passed, including holdout-leakage and ordering tests.

Export `wizard-20260917T175047625832Z-94203ba8bc614fbcba48c69bf5b48551`.

| Joint | Additive holdout error (degrees) | Proportional error | Affine error |
| --- | ---: | ---: | ---: |
| Elbow | -.161802 | -.350841 | +.061922 |
| Wrist pitch | -.299280 | -.097218 | -.147269 |

Exploratory selected coefficients: elbow reported delta = .4741767332009183 *
commanded delta + .017265650405936212 rad; wrist reported delta =
.6300524197763826 * commanded delta. These describe only the sampled nonzero
movement range. In particular, the affine elbow intercept is NOT evidence that
a zero command produces motion, nor permission to extrapolate through zero.

Model selection uses the holdout, so another independent trial remains necessary.
Changed posture, load and command size are confounded; the middle trace's late
transport failure remains visible. No model is enabled for arbitrary motion.

Next screen a frozen hybrid candidate with these coefficients, exact current
start and same motion directions, preserving desired/wire endpoints and envelope
checks. Reject inverse solutions outside the observed command range rather than
extrapolating the affine intercept. New live data must establish whether the
hybrid improves desired arrival. No hardware command was sent in this checkpoint.

## Hybrid range screen — 17:53 UTC

Implemented a finite offline search using the existing coefficients without
refitting or extending their training ranges. Search: translations 1 through
10 mm toward the ghost anchor and 201 pitch offsets from -.020 to +.020 rad,
2,010 combinations total. Inverse elbow/wrist commands must remain within the
first two traces' training command ranges and the 3-degree joint-change envelope.
Any accepted point would still require full path screening; the grid itself
grants no motion authority. Four response-model tests passed.

Export `wizard-20260917T175346648813Z-8f5fe928fafa4f39b9e7a73bedf10c07`:
NO_IN_RANGE_GRID_POINT, zero feasible candidates. Overlapping rejection counts:
1,879 elbow-range failures, 1,829 wrist-range failures, 1,099 joint-envelope failures.
No IK failures. This is not proof that all possible paths are infeasible; it means
the proposed combination is unsupported for this sampled local approach family.

Do not promote independently lowest-error models into a combined controller
without checking their inverse domains. In particular, elbow's positive affine
intercept consumes much of the desired small movement and leaves an inverse
command outside the fitted range when wrist remains within its own range.

Next stop the sequence of changed-posture coordinated fitting trials. Review the
pinned T104 interpolation/final-target semantics and plan a bounded wrist-only
response diagnostic from fresh pose. Any comparison between T101 and T104 must
label changed starts as confounded; a controlled comparison needs independently
verified matching starts, not an automatic return after failure. Use this evidence
to decide whether a joint-space endpoint command or a better-supported local
response model is the next practical route toward ghost press/retract.

## Reference-source review and isolated wrist — 17:56 UTC

Re-fetched the official reference archive in memory and verified SHA256
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
No source was executed, flashed or installed. Source:
https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip
In RoArm-M3_module.h, lines 934-936 explicitly issue the final T104 goal; lines
625-642 refresh feedback and call computePosbyJointRad, which updates lastX/Y/Z/T
at lines 614-619. Thus a missing terminal write or an always-stale stored start
is not established by this reference. Installed binary equivalence remains unknown.
T104 uses synchronous servo writes with speed/acceleration zero through goalPosMove;
T101 passes explicit speed/acceleration, so their profiles are not interchangeable.

Added `--wrist-post-coordinated`, exclusive and bound to the exact observed pose
b=.001533981, s=.033747577, e=1.636757501, t=-.065961174, r=.018407769,
g=3.138524692 rad. Fixed -1.5-degree T101 joint4, speed20/acc1, 41-sample FK sweep
under 6 mm, no compensation/return/retry. 59 focused tests passed.

Preflight `wizard-20260917T175619995728Z-c48c5dfed21844a19416b7d420093d78`.
Trial `wizard-20260917T175637612429Z-34ef0ef0e9484ef7810967bb31445882`.
Analysis `wizard-20260917T175652712583Z-e5590d679f6748d79e2fa1344f7de4cc`.
Target wrist -.09214111277991494 rad, reported final -.075165059 rad.
Requested -1.5 degrees, reported -.527343766 degrees; residual +.972656234 degrees
(.01697605377991493 rad), modeled endpoint miss 2.923496 mm. Other joints unchanged.
COMPLETION_DEADLINE_EXCEEDED; no feedback failures. Last reported wrist change
.296999 s, unchanged tail 8.908819 s. No subsequent motion.

The isolated result establishes that coordinated interpolation is not necessary
for the observed undershoot. It is not a controlled proof of relative T101/T104
performance: starting posture, target and command profile differ. Next freeze a
small descending wrist correction at this fixed shoulder/elbow posture and test
on a new endpoint with separately screened desired and wire sweeps. Avoid another
combined model fit until the isolated response supports it. Physical accuracy
and the cause of persistent servo-level residual remain unmeasured.

## Fixed-posture descending wrist validation — 17:58 to 18:00 UTC

Frozen isolated residual .01697605377991493 rad from the previous wrist-only
trial. First desired -.085 rad, command -.10197605377991494 rad, exact start
-.075165059 rad. Fixed other joints b=.001533981, s=.033747577, e=1.636757501,
r=.018407769, g=3.138524692 rad. Candidate SHA256
`80157408a3b326bfca196a98e45f1f4eae2038c299bb4a663313b40fcb4695e7`.
49 focused tests passed; separate fresh preflight passed. Command remains T101
joint4, speed20/acc1, with a 41-sample modeled sweep below 6 mm.

Preflight `wizard-20260917T175839156393Z-9978a7500aa64f1ab5ce9262cd67e673`.
Live `wizard-20260917T175849192557Z-aafcb367e76d4062bf1c41f052b114eb`.
COMPENSATED_REPORTED_ENDPOINT_VERIFIED, error null, four feedback samples.
Final -.084368943 rad; desired residual +.036156903 degrees / .108677399 modeled
mm. Wire endpoint remains unverified, 3.032169 modeled mm miss. Other joints unchanged.

Second candidate translates the desired target by the previous reported step
without refitting residual: desired -.094203884 rad, wire -.11117993777991493 rad,
exact start -.084368943 rad. Separate v2 identity
`ce0a3a4902fe01fd61b9d523c5ee19431f80ea0dc41de4575fdfad50882f6347`, parent v1 above.
Explicit `--wrist-post-coordinated --wrist-candidate --wrist-clean --wrist-nearby-target`.
46 focused tests passed; old experiment scopes remain separate.

Preflight `wizard-20260917T175952988341Z-c46d7ab11b054ccca5c343069c50aa23`.
Live `wizard-20260917T180002142128Z-741792e95c244d34b015e0533a4252bb`.
COMPENSATED_REPORTED_ENDPOINT_VERIFIED, error null, four feedback samples.
Final -.093572828 rad; desired residual +.036156845 degrees / .108677353 modeled
mm. Other joints unchanged. Same requested step -1.536157 degrees and reported
step -.527344 degrees as the first candidate, with unchanged fitted bias.

This is local same-direction transfer across nearby endpoints, not a return-cycle
repeatability result or physical tip measurement. No further move was sent.
Next admit a separate bounded ascending diagnostic from fresh current pose;
preserve descending coefficients and do not assume reverse symmetry. Once both
directions have clean desired-endpoint evidence, compose a finite noncontact pair
with export-before-progression, then evaluate how it maps to ghost press/retract.

## Ascending wrist diagnostic — 18:02 UTC

Added exclusive `--wrist-post-coordinated --wrist-ascending`, not mixed with
descending candidates. Exact starting wrist -.093572828 rad; unchanged fixed
shoulder/elbow/other joints. T101 joint4, +1.5 degrees, speed20/acc1, no correction.
41 modeled samples below 6 mm sweep; 47 focused tests passed.

Preflight `wizard-20260917T180201432106Z-1b284d4bf0bc4474a5687bb5dca8750b`.
Trial `wizard-20260917T180217981403Z-efa28b4ae1f64b19b7a1382dbcc48c75`.
Command -.06739288922008504 rad; final reported -.072097097 rad.
Requested +1.5 degrees, reported +1.230468748 degrees; residual -.269531252
degrees (-.004704207779914954 rad). Modeled endpoint error .810134 mm,
COMPLETION_DEADLINE_EXCEEDED. Other joints unchanged. No return/retry followed.

This new positive-direction residual differs in sign and magnitude from the
descending correction. Next freeze it as an ascending candidate, screen a new
small target and validate held-out arrival without changing tolerance. Do not
use descending compensation in reverse. A finite paired cycle remains pending
until both directions have clean new desired-endpoint evidence.

## Ascending correction validation — 18:04 UTC

New ascending-only candidate uses residual -.004704207779914954 rad from the
isolated ascending diagnostic, not the descending correction. Exact start
-.072097097 rad, desired -.055 rad, wire -.05029579222008505 rad. Other joints
remain fixed. T101 joint4, speed20/acc1, modeled sweep below 6 mm.
48 focused tests passed. Direction and candidate identities remain separate.

Preflight `wizard-20260917T180355918816Z-a428a4b92b2145afb3f71e0d33634c33`.
Trial `wizard-20260917T180403867312Z-7320da0a89d14d3aadaf652c0926bd11`.
COMPENSATED_REPORTED_ENDPOINT_VERIFIED, error null, four feedback samples.
Wrist reports progressed -.055223308, -.053689328, -.052155347, -.052155347 rad.
Final desired error +.162986611 degrees / .489891732 modeled mm, narrowly within
the existing .5 mm band. Wire result remains unverified (insufficient wire dwell),
even though its final error was .320243 modeled mm. No other joint changed.

Read-only follow-up `wizard-20260917T180414205384Z-bd71a0cb4ee846f680c3a0a9055e1661`
returned the same complete joint pose; the old-start preview correctly rejected
it. No further command was sent. This supports reported persistence after arrival,
not independently measured physical stability or an assertion of large margin.

Next select shared low/high endpoints within the local modeled sweep and test a
finite bidirectional pair. Each direction must retain its own candidate and fresh
start admission. Publish each result before progression, stop on a failed leg,
and do not automatically return after failure. Existing one-way successes are
not a substitute for validating the pair, nor for the later coordinated ghost
keyboard approach and press/retract sequence.

## Shared-endpoint wrist pair — 18:07 UTC

Added `wrist_shared_pair.py` with fixed desired LOW=-.068 and HIGH=-.052155347
rad. Directional biases remain unchanged: down +.01697605377991493 rad,
up -.004704207779914954 rad. Start admission uses the opposite endpoint center
within .0028 rad, with exact other-joint posture. Both desired and transmitted
sweeps are screened (82 samples total), <=6 mm and <=3 degrees. This start range
does not alter the .5 mm desired-arrival requirement. No generic target input.
Explicit `--wrist-pair-leg down|up` sends at most one separately admitted leg.
52 focused tests passed, including direction-specific arrival and wrong-start
rejection. No automatic pair sender exists at this checkpoint.

Down preflight `wizard-20260917T180639924599Z-1c94d7ea5f3f46d996411688551317e1`.
Down trial `wizard-20260917T180652223876Z-b2c307f1e4e146eeb8a647861824ddae`:
COMPENSATED_REPORTED_ENDPOINT_VERIFIED, error null. Reported -.065961174 rad,
desired -.068 rad, .351116389 modeled mm error. Other joints unchanged. Result
export reviewed before selecting the next leg.

Up preflight `wizard-20260917T180700855856Z-376858cb9df64024b5dabc1bc2d6a874`.
Up trial `wizard-20260917T180712827870Z-818412cf1700488aa18336a3edfe5aac`:
COMPENSATED_REPORTED_ENDPOINT_VERIFIED, error null. Reported -.052155347 rad,
equal to desired high and original reported starting angle; modeled positional
error ~1.2e-7 mm is numerical rounding, NOT physical accuracy. Other joints unchanged.
Wire-target outcomes remain separately unverified as expected for the offsets.

Read-only follow-up `wizard-20260917T180722867420Z-002b0980218d43fa86f8802fa3bac0f3`
admits the high endpoint for a possible future down leg. No further movement sent.

Next implement a finite two-leg coordinator using exact candidate/command binding,
fresh pose continuity, transport ownership and export-before-next-leg. Test
failure/cancellation/export-error stops without hardware, then run a paired repeat.
Do not equate this wrist arc with the task-space ghost keyboard press/retract:
the subsequent approach, stylus transform and task sequence still need integration.

## Automatic finite wrist cycle — 18:10 UTC

Implemented CompensatedWristCycle using the existing finite elbow coordinator's
publish-before-progression loop, with distinct wrist modes, joint and schema.
The elbow behavior remains covered by regression tests. A dedicated native wrist
adapter owns the transport lock across both fresh admissions and exports, checks
exact six-joint continuity between legs and uses one-use reservations. The CLI
`bench_compensated_wrist_cycle.py` is read-only unless `--execute` is supplied;
execution sends at most one down and one up command, with no retries or recovery
returns. Candidate, command, receipt cleanup and bound request configuration must
match before a verified publication can permit progression.

50 focused tests passed: both cycles, wrong commands/candidates, failed feedback,
failed publication, cancellation, changed pose and native held-before-send cases.
Preflight `wizard-20260917T181031044557Z-accc882b9e4b43d2a006d3975073d3e0` passed.

Cycle `wizard-20260917T181042068964Z-89bbdac5740d43f681aec56bc04041d5`:
LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED.
- Down `wizard-20260917T181040373709Z-46b9f03dae7b4a3fa7ff5c2c1af95043`:
  clean desired arrival, .351116389 modeled mm error, reported wrist -.065961174.
- Up `wizard-20260917T181042013640Z-9ff055514b46412787c9505c5358bdbd`:
  clean desired arrival, reported wrist -.052155347 exactly equal to desired high.
  Numerical Cartesian residual ~1.2e-7 mm is rounding, not measured tip accuracy.

Both runner errors null; other joints unchanged. The endpoints match the earlier
separately admitted pair. Down was durably exported and verified before fresh up
admission; final cycle index also verified. No subsequent motion was sent.

Next inspect the local arc in the hypothetical 100 mm stylus model, its orientation
change and relationship to a ghost key plane. Joint-angle down/up labels are not
physical press/retract labels (the controller Z response is reversed here). Keep
the existing full-size keyboard geometry and full task objective; do not call
this local repeat a completed keyboard approach or typed sequence.

## Hypothetical stylus arc and route separation — 18:14 UTC

Implemented an offline model review consuming the verified wrist cycle, its two
leg exports, the saved full-size ghost-key route and pinned URDF bundle. The
same-sign/same-zero joint correspondence remains a hypothesis, and the tool is
still -100 mm along hand-TCP Z. Forty-one samples per leg interpolate the joint
arc geometrically; they are not observed in-motion measurements. Seven focused
geometry/approach tests passed, including failure rejection and PARK/HOVER naming.

Corrected review export:
`wizard-20260917T181402014692Z-6bffea7204b44ec6b4285dc45986fc1b` (schema v2).
Initial review `wizard-20260917T181319649586Z-ad05707ad58e457f80d71cec1b0ff396`
mislabeled the first PARK waypoint as a ghost hover; retain as superseded evidence.
No coordinate or route point changed, only selection/labeling of the actual HOVER.

In VENDOR_BASE_UNREGISTERED coordinates:
- High wrist endpoint tip [345.256602, 2.369024, 150.197531] mm.
- Low wrist endpoint tip [346.939598, 2.371600, 152.465298] mm.
- Each leg: vertical magnitude 2.267767 mm, lateral magnitude 1.682998 mm,
  wrist orientation change .791016 degrees. Modeled closed-cycle displacement zero.
- Route PARK entry [416.995602, -14.999842, -.098435] mm, 167.442644 mm away.
- First keyboard:A HOVER [322.999857, -183.699919, -12.433432] mm,
  248.124655 mm from the cycle endpoint.

Neither the negative vendor-frame Z coordinates nor the distances establish
physical board clearance: there is no registered board transform. No keyboard
placement was shifted to make the local wrist test appear to reach a key.

Next use coordinated joint planning for a predominantly vertical tip-space
press/retract and evaluate the saved approach separately. The demonstrated wrist
arc can be a control primitive but has substantial lateral drift. Preserve all
prior endpoint evidence without claiming a straight press, key contact, or the
full ghost route. No live motion occurred during this geometry checkpoint.
