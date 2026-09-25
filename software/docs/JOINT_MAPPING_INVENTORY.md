# Joint mapping inventory

## Implemented map

| Logical joint | T101 joint ID | T1051 feedback | Servo bus IDs | Register direction for positive command |
| --- | ---: | --- | --- | --- |
| Base | 1 | b | 11 | Decreasing |
| Shoulder | 2 | s | 12, 13 | Driving increases; driven decreases |
| Elbow | 3 | e | 14 | Increasing |
| Wrist pitch | 4 | t | 15 | Increasing |
| Wrist roll | 5 | r | 16 | Decreasing |
| Gripper | 6 | g | 17 | Increasing |

Command angles and these feedback fields use radians. Servo register direction
is not a claim about clockwise/counterclockwise in board or camera coordinates.
Shoulder feedback is the driving-servo angle, not independent confirmation of
both physical servos.

Sources: [Waveshare joint-control documentation](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control)
and the [pinned reference firmware archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip).
Archive SHA-256: `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
Implementation references: `RoArm-M3_config.h` lines 61–67 and 86–96;
`RoArm-M3_module.h` lines 36–62, 306–403, 635–661 and 770–797.
The reference archive is verified; the installed firmware binary is not attested.
Some old source comments mention M2/EOAT conventions, so executable definitions
and dispatch functions were checked instead of relying on comments alone.

## Code and artifacts

- `arm/joint_mapping.py`: immutable logical/feedback/servo map; reference
  register conversion and predicted feedback; one-command local probe previews.
- `runs/JOINT_MAPPING_INVENTORY_20260915.json`: serialized map and reverified
  evidence references for the currently populated empirical wrist cell.
- `arm/joint_endpoint_verification.py`: selected-joint nominal endpoint checking.
- `application/joint_bias_experiments.py`: separate local joint/direction fitting
  and held-out prediction checks, currently synthetic input only.

The reference conversion preserves opposite base/roll signs, mirrored shoulder
commands, elbow's 1024-step offset, gripper's absolute register coordinate,
reference clamping and C++ half-away-from-zero rounding. It also exposes the
2047 command / 2048 feedback midpoint difference where applicable. These are
reference predictions, NOT learned correction values and NOT executable permits.
Reference register limits must not be mistaken for safe physical sweep limits.

## Empirical coverage

Wrist pitch has one populated cell: decreasing approach from reported ~3.7793
degrees toward intended +2 degrees, spd 20 / acc 1, unchanged tool/pose context.
Three corrected live trials reported ~2.0215 degrees using a ~1.0332-degree
command. Exact original-export hashes are in the inventory. Matched controls
remain documented in `MATCHED_CORRECTION_REPETITIONS_20260915.md`.

The original base characterization set has eleven uncorrected observations: four one-degree probes (two in each
direction), four fixed-target two-degree-profile probes (two per direction),
and three unseen-target tests (one positive interior point and two directional
midpoints). See `BASE_LOCAL_MODEL_AND_HOLDOUT_20260915.md` and `BASE_MIDPOINT_COMPARISON_20260915.md`.
See `BASE_FIXED_TARGET_REPETITIONS_20260915.md`, `BASE_TWO_DEGREE_DIRECTIONS_20260915.md`,
`BASE_REPEATABILITY_20260915.md` and
`BASE_STREAM_SYNCHRONIZATION_20260915.md`; no target was reached. One intermediate
repeat attempt held before writing and is excluded from measured trials. This is not
a generally validated base correction cell. The first matched live correction
pair has since passed its local screen; details below. Shoulder, elbow, roll and gripper remain
unmeasured at that stage; the first roll probe is now recorded below. No wrist coefficients have been transferred.
Only the explicit frozen local base inverse experiment is available; generalized
compensation and coordinated corrected motion are not enabled. This inventory
is joint-space mapping, not board/camera registration.

## Next data collection

The v6 base-only native path is implemented and tested: selected joint and
logical ID are bound in parent and child, all five other axes are monitored,
and intended/transmitted targets are exported. Older wrist intent semantics
remain unchanged. See `BASE_MAPPING_PROBE.md` for the finite procedure.

The first live base probe requested +1 degree and reported only +0.08789 degree
change; its export reconstructed cleanly and the attempt held without retry.
This moves the full arm, so the physical sweep matters even though the angle is
small. Both approaches and held-out measurements were collected before the first
base correction; repeated matched correction/control validation is now next.
Shoulder/elbow require their own pose/load context; roll and gripper likewise
need distinct experiments. Forty-four base commands have now been sent: eleven
original characterization commands, three positioning commands, four corrected
trials and four matched controls, plus four separate-session alternating corrected
legs, two completed legs of the first single-connection campaign, and four legs
of the successful optimized single-connection retest, and four in its successful
repeat, plus one increasing and one decreasing speed-10 trial, and two matched
speed-20 references, plus four reversed-order speed-comparison commands. The increasing speed-10 trial reported
the same 1.054687474-degree endpoint, with no observed other-joint drift. A prior
isolated packaging failure sent no command. See
[speed-10 native result](BASE_SPEED_FIRST_NATIVE_TRIAL_20260915.md).
The decreasing speed-10 trial reported 0.439453128 degrees for desired 0.4,
also with no other-joint drift and fully verified exports/cleanup. See
[decreasing result](BASE_SPEED_DECREASING_NATIVE_TRIAL_20260915.md).
The matched speed-20 references reproduced both speed-10 endpoints exactly;
neither speed has demonstrated an endpoint advantage in these pairs. See
[matched results](BASE_SPEED_MATCHED_REFERENCE_PLAN_20260915.md).
The reversed-order repeat reproduced both directional endpoints again, with
eight distinct comparison trials total and no consistent speed advantage. See
[completed speed comparison](BASE_SPEED_REVERSED_REPEAT_20260915.md).
The two complete single-connection runs matched all reported endpoints;
dispatch sample ages remained at or below 172 ms. See
[repeat results and speed-comparison preparation](BASE_SINGLE_CONNECTION_REPEAT_20260915.md).
General base compensation is not enabled. The four-leg sequence completed with
three exact reported six-joint handoffs; see
[alternating movement results](BASE_ALTERNATING_MOVEMENT_20260915.md).
The first single-connection run held before its third write; the two completed
endpoints passed. Original diagnostic integrity is verified, but full campaign
reconstruction is incomplete. A redundant intent-decoding optimization passed
simulation and then completed the four-leg live retest with full reconstruction.
Selected-sample age at writes stayed between 140 and 172 ms. See
[completed retest](BASE_SINGLE_CONNECTION_RETEST_20260915.md) and
[single-connection status](BASE_SINGLE_CONNECTION_SEQUENCE_20260915.md).

The first base inverse proposal is now implemented and evidence-checked:
desired reported endpoint +1 degree, candidate transmitted target +2.335749466
degrees, increasing approach only. See
[the correction experiment plan](BASE_CORRECTION_EXPERIMENT_PLAN_20260915.md).
Native v10/v11 corrected/control integration passed simulation and its first live
pair: corrected endpoint 1.054687474 degrees versus control 0.439453128 degrees
for desired 1 degree, from identical six-joint starts. Reported absolute error
was 90.24% lower in this pair. See
[the retained first-pair results](BASE_FIRST_COMPENSATION_PAIR_20260915.md).
The reversed-order repeat reproduced both endpoints exactly: two corrected trials
passed, and both controls missed. See [the reversed-pair results](BASE_REVERSED_PAIR_20260915.md).
Settling timing differed despite identical reported endpoints. Further timing and
repeat evaluation is next; this does not establish Cartesian or all-joint accuracy.

The retained timing analysis is now complete, and a decreasing-direction offline
proposal targets +0.4 degree using a -0.684826381-degree command from the separate
decreasing model. Native v12/v13 profiles are now implemented and their first
matched live pair completed: corrected 0.439453128 degrees versus unchanged
control 1.054687474 degrees for desired 0.4 degree, from identical starts.
Reported absolute error was 93.97% lower. One increasing corrected positioning
command restored the paired start and is excluded from the comparison/training.
See [first decreasing native pair](DECREASING_BASE_NATIVE_TRIAL_20260915.md).
The reversed-order decreasing repeat reproduced both endpoints exactly; both
decreasing pairs support the local candidate. See
[reversed decreasing results and next measurement work](DECREASING_BASE_REVERSED_PAIR_20260915.md).
Other poses/speeds/joints and physical Cartesian accuracy remain unverified.
Earlier offline work remains in
[timing analysis and decreasing proposal](BASE_TIMING_AND_DECREASING_PROPOSAL_20260915.md).

## Wrist-roll coverage

v16 now exposes one uncorrected +/-1-degree roll probe (T101 joint 5 / feedback r)
through the wizard, with all five other axes monitored and independent exports.
The first increasing command requested +1 degree and reported +0.791015620 degree,
undershooting the absolute target by 0.208984380 degree. It passed the existing
0.5-degree endpoint band; this is a discrepancy to characterize, not proof of
accurate compensation. Other joints were unchanged; raw reconstruction, write
accounting and cleanup passed. Exactly one roll command has been sent, with no
return, model fitting, or transferred coefficients. See
[roll profile and first result](WRIST_ROLL_FIRST_PROBE_20260915.md).

The second roll command (decreasing by a requested 1 degree) reported
-0.615234345 degree travel and +0.384765655 degree endpoint error. It passed the
existing band with all other axes unchanged and verified export/cleanup. Roll
command count is now two; no compensation has been fitted. These observations
use different starts/absolute targets, so they are not yet a repeatability or
direction-only model. See [fixed-target repetition plan](WRIST_ROLL_FIXED_TARGET_REPEAT_PLAN_20260915.md).

The v17 fixed-target repeat screen is now complete: four additional roll commands,
two matched repeats in each direction, with zero reported within-pair endpoint
spread. Increasing error was -0.208984380 degree and decreasing error was
+0.384765655 degree in both repeats. All other joints reported unchanged.
Roll command count is now six; base count remains 44. No roll compensation is
fitted or enabled. Final reported roll is +0.001533981 rad. See
[repeat evidence and next steps](WRIST_ROLL_FIXED_REPEAT_20260915.md).

Second-point discovery added one v16 increasing command (roll total seven;
base still 44). Command +1.087890637 degrees reported +0.878906257 at the end of
the five-second capture. Two later zero-command captures instead reported
+0.966796894 degrees, a +0.087890637-degree change. Other axes remained unchanged.
The planned decreasing command was withheld; no roll model was fitted. Current
reported roll is 0.016873789 rad, so the old fixed-repeat starting anchor is no
longer current. See [delayed endpoint evidence](WRIST_ROLL_SECOND_POINT_20260915.md).

The 35-second same-connection observation path is implemented. Its first v18
launch failed before request delivery (zero motion commands), with diagnostics
retained. A separately versioned v19 profile adds preparation time only and passed
38 focused tests. Physical long-window validation remains pending; command counts
remain unchanged. See [persistence integration and launch correction](WRIST_ROLL_PERSISTENCE_IMPLEMENTATION_20260915.md).

The first v19 live persistence trial is now complete. One decreasing command
reported +0.263671854 degrees at all four horizons (5/10/20/35 seconds), with
zero after-five-second change or other-axis drift. A separate reconnect baseline
matched. Final command error was +0.296874960 degree; no correction was applied.
Roll count is now eight, base still 44; current r=0.004601942 rad. See
[first completed persistence trial](WRIST_ROLL_PERSISTENCE_LIVE_20260915.md).

The increasing v19 persistence run also completed: +1.263671854-degree command,
+1.230468748-degree reported endpoint, -0.033203106-degree error, no changes after
five seconds, no other-axis drift, and matching reconnect feedback. Roll count
is nine; base remains 44. Current r=0.021475731 rad. No compensation was applied.
See [increasing persistence results](WRIST_ROLL_PERSISTENCE_INCREASING_20260915.md)
and [the next fixed long-window repeat plan](WRIST_ROLL_LONG_FIXED_REPEAT_PLAN_20260915.md).

v20 fixed long-window repeat implementation passed 89 focused/supervisor tests.
Its first decreasing command was sent, then held at verification on a split
baseline/post JSON frame. Complete retained records separately show a roll
change at ~18.3 s from 0.004601942 to 0.003067962 rad. No further repeat commands
were sent. Roll count is ten, base 44; last reported r=0.003067962 rad. Historical
hold is preserved; compensation remains unfitted. See
[boundary and late-change findings](WRIST_ROLL_LONG_FIXED_FIRST_HOLD_20260915.md).

Offline cross-window framing replay now separates the valid split frame from
the genuine reported late change: 1,948 complete poses, no remaining decoded
capture issues, and REPORTED_ENDPOINT_CHANGED. Native integration is not yet
enabled; original hold and command counts are unchanged. See
[reproducible framing replay](WRIST_ROLL_CROSS_WINDOW_REPLAY_20260915.md).

Opt-in v21 framing is now integrated across native admission, reconstruction,
portable exports, wizard staging and supervisor packaging/budgets. Consolidated
regression: 352 passed; an additional named-error export test also passed. No
new hardware run, command count change or compensation fit. See
[native framing integration](WRIST_ROLL_FRAMED_NATIVE_INTEGRATION_20260915.md).

Fresh baseline matched the prior held endpoint. One existing v19 increasing
one-degree discovery probe then completed: target 0.020521254519943296 rad,
reported endpoint 0.016873789 rad, error -0.208984 deg, stable at 5/10/20/35 s,
zero other-axis drift. Original export reconstruction passes. No compensation;
roll count eleven, base 44. This was not v21 live qualification. See
[fresh-start live result](WRIST_ROLL_FRESH_START_PROBE_20260915.md).

One decreasing v19 probe completed from fresh matching feedback: reported
travel -0.791016 deg for a -1-degree command; final r=0.003067962 rad, stable
through 35 seconds, no other-axis drift. The latest increasing/decreasing pair
returns to identical reported six-joint endpoints, but the older same-geometry
decreasing trial differs by 0.087891 deg and has different source/runtime hashes.
No compensation fitted. Roll count twelve, base 44. See
[return-pair comparison](WRIST_ROLL_RETURN_PAIR_20260915.md).

Two further v19 increasing/decreasing probes completed with 35-second stable
endpoints and zero other-axis drift. The recent two-per-direction screen has
zero increasing endpoint spread but 0.087891-degree decreasing spread despite
matching source/start/command context. Last reported r=0.004601942 rad; roll
count fourteen, base 44. No compensation applied. Next candidate is the v21
fixed increasing probe if a fresh baseline matches. See
[recent repeat screen](WRIST_ROLL_RECENT_REPEATS_20260915.md).

First v21 live fixed increasing probe completed with an actual validated split
frame (11 baseline + 194 post bytes), excluded from post-motion evidence. Final
r=0.021475731 rad, error -0.033203 deg, persistent 35 seconds; other-axis drift
zero. Export reconstructs, matching the older same-geometry endpoint without
claiming identical source/schema context. Roll count fifteen, base 44. See
[framing-enabled live result](WRIST_ROLL_FRAMED_LIVE_20260915.md).

First v21 decreasing fixed trial also completed, including real split-frame
handling (4 baseline + 199 post bytes). Final r=0.004601942 rad, error +0.296875
deg, stable at every 5/10/20/35-second horizon with no other-axis drift. The
historical same-geometry late change did not recur in this run; its held verdict
remains unchanged. Roll count sixteen, base 44. See
[framed decreasing result](WRIST_ROLL_FRAMED_DECREASING_20260915.md).

Second v21 pair completed. Increasing endpoint repeated exactly; decreasing
ended at r=0.007669904 rad versus prior 0.004601942, a 0.175781-degree spread
with matching source/start/command context. Latest error +0.472656 deg passes
the broad arrival band but fails the next fixed anchor. Sequence stopped; no
compensation or corrective move. Roll count eighteen, base 44. Next priority is
offline history/model assessment, not further identical repetitions. See
[v21 repeat comparison](WRIST_ROLL_FRAMED_REPEATS_20260915.md).

Offline history assessment now pins all 19 retained roll campaign exports:
18 retained submission attempts, 10 clean long-window samples, seven short
observations, one held late-change trial and one campaign without a retained
trial. Four chronological error predictions give 0.065918-degree MAE versus
0.252930 for zero error, but only one training sample per prediction and a
0.175781-degree worst residual. This is not corrected-command validation.
41 focused tests pass; no new hardware access or compensation. See
[history assessment and next work](WRIST_ROLL_HISTORY_ASSESSMENT_20260915.md).

2026-09-16: added a read-only endpoint quality projection and wizard display
separating arrival, persistence, diagnostic precision and next-start agreement.
The proposed 0.1-degree screen does not change admission thresholds. Four pinned
v21 originals reconstruct unchanged: both increasing errors are 0.033203 degrees;
decreasing errors are 0.296875 and 0.472656 degrees. Only the latest return misses
the opposite fixed profile's anchor. Derived evidence is in
`software/runs/WRIST_ROLL_QUALITY_REVIEW_20260916.json`.
Validation: 190 passed, 156 deliberately inapplicable profile combinations skipped;
an earlier focused run passed 30 tests, and JavaScript syntax validation passed.
No hardware access, new movements, compensation or physical accuracy claims.
Continue from the [target-variation implementation plan](WRIST_ROLL_TARGET_VARIATION_PLAN.md).

The next offline step now implements six enumerated outward/return cases and
60 synthetic response/fault combinations using the production persistence and
quality evaluators. Full-pose anchor mismatches prevent simulated writes; cases
never queue returns. 71 focused and 43 native-package/framing/export regression
tests passed. No new hardware access; native case selection and wizard integration
remain next. Results: `software/runs/WRIST_ROLL_TARGET_VARIATION_SIMULATION_20260916.json`.

v22 native integration now implements the six named variation cases through
admission, framing, native budgets, reconstruction, export and host-staged wizard
preview/run. 125 integration/regression tests passed; four prior pinned exports
remain unchanged. First physical v22 test is pending: discovery at 13:15 UTC
on 2026-09-16 found no expected arm USB controller and stopped before any port
open. Diagnostic export: `wizard-20260916T131504706336Z-eb18d0e90c624300927e697911c4c0ec`.
Roll/base counts remain 18/44. Restore USB, capture fresh feedback, then evaluate
the nominal-case starting pose. See the updated target-variation plan.
