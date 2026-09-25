# Finite shoulder movement matrix

Status: offline proposal; not installed or authorized by this file.

## Purpose

Gather varied command/response evidence before fitting compensation. Distinguish
target register changes, sampled physical response, final endpoint error and
target history. A small response is an experimental result, not proof of no motion.
Encoder evidence does not establish Cartesian or stylus-tip accuracy.

## First matrix

Twelve explicit legs: offsets (-4,0,-8,0,-12,0), repeated twice from the initial
paired target-register anchor. Hold speed 20 and acceleration 1 fixed. All target
pairs retain sum 4114. Record repositioning legs exactly like outbound legs.

Using the last HISTORICAL r36 capture only as an offline example:

| Step | Servo 12 target | Servo 13 target | Register change |
|---|---:|---:|---|
| 1 | 2385 | 1729 | -4 / +4 |
| 2 | 2389 | 1725 | +4 / -4 |
| 3 | 2381 | 1733 | -8 / +8 |
| 4 | 2389 | 1725 | +8 / -8 |
| 5 | 2377 | 1737 | -12 / +12 |
| 6 | 2389 | 1725 | +12 / -12 |

Repeat steps 1–6 once. Fresh measured positions and target registers must replace
historical values at admission. These are not predicted physical displacements.
Prior targets 2389/1725 and 2397/1717 are marked as visited. New outbound targets
extend beyond the earlier forward target without repeatedly walking the anchor.

## Classification versus progression

- Retain existing accurate/miss outcomes for clearly measured displacement.
- SMALL_SETTLED_RESPONSE: some sampled movement, but one or both net changes
  are below the existing two-count threshold.
- TRANSIENT_THEN_SMALL_NET_RESPONSE: sampled displacement at least two counts
  returns below that threshold on at least one selected servo.
- NO_SAMPLED_DISPLACEMENT: all acquired positions unchanged; does not exclude
  movement between samples.
- Unsafe or unverified evidence stays a stop, regardless of movement visibility.

Draft eligibility for reviewing the next planned leg: one consecutive settled
small-response observation, verified delivery/readback/export, residual <=12 counts
on both selected servos, valid timing, unchanged torque, direction checks, bounded
travel and stable neighbours. A second consecutive small response stops the matrix.
This allowance is implemented in offline source, but is NOT installed or active
on the arm. Native owner, result codec, host assessment and receipt signing now
share the restricted matrix policy described below.

Retain two-second small-response observation, global 32-count measured-anchor
envelope, 2-count neighbour envelope and per-leg bounds. Never resend a command
to force a response. Fault or uncertain receipt delivery must stop host progression;
independent read-only reconciliation must not be called proof of controller stop.

## Evidence and implementation status

Implemented offline draft/classifier in `shoulder_movement_matrix.py`, retaining
movement_authorized=false and receipt_issued=false. Existing installed/live
assessment remains unchanged. Ten tests pass, including six unsafe-evidence
scenarios and two-consecutive-small rejection.

Verified r36 historical export was reclassified as SMALL_SETTLED_RESPONSE (0/+2
net counts). Proposal/review export:
`wizard-20260920T163405566041Z-f7e7d068901f4de1a4b552dfa2e6895e`.
No hardware accessed for this work.

## Next implementation and experiments

1. DONE offline: exact native matrix preparation and typed small-response result.
2. DONE offline: matching host/native checks and consecutive-small accounting;
   incompatible legacy outcomes are rejected rather than promoted silently.
3. Native/socket simulations: small then clear, two small results, target revisit,
   transient return, asymmetric response, corrupt feedback and lost receipt ACK.
4. Stage/build/review candidate and seek approval before installation/live run.
5. Analyze residual and peak/net response grouped by target, direction and magnitude.
   Do not pool revisits and new endpoints or equate completion with accuracy.
6. Only after magnitude tests are interpretable, propose a second speed comparison;
   change one variable at a time. Fit compensation only with held-out validation.

## Offline controller/host integration — 2026-09-20

The authenticated complete twelve-target manifest selects the matrix policy only
when it exactly matches `(-4,0,-8,0,-12,0)*2` relative to its second target.
The first baseline's target registers must match that anchor. No new network
target-setting route or generic relaxation was introduced. Existing legacy,
matched and smoke sequences retain their original small-response stop behavior.

Result framing `RCCRESULT01` adds outcome byte 4, `SETTLED_SMALL_RESPONSE`.
It never means accurate arrival or independently measured physical displacement.
Old hosts reject this unknown outcome; new hosts reject it for non-matrix
manifests or when independent assessment disagrees. Upgrade host and controller
together before a matrix deployment. The deployed board still selects Matched;
no matrix live CLI, firmware staging, installation or hardware access occurred.

For the matrix, both native and host require at least two seconds from the first
post-write sample's start to the final sample's finish before accepting a small
result. This conservative shared timestamp is necessary because the current
result record does not contain send time. Existing patterns retain their r36
send-relative window. Small counters advance only with accepted native export
receipts / issued host receipts; clear measured responses reset the counter.
Uncertain receipt delivery is not retried.

Production native controller plus authenticated loopback HTTP and real disk
exports now exercise:

- Constant residual: all 12 legs complete with 12 exported/acknowledged results.
- Frozen reverse response: six results retained, including three small results
  separated by clear responses; seventh write stops on opposite-direction motion.
- Fully frozen response: one small result retained; second consecutive small
  result stops, with its full failure evidence exported and no third write.
- Independent host rejection of a forged eligible second-small outcome, and
  rejection of small outcomes attached to a legacy manifest.

These are simulated bus responses, not new measurements from the arm. The
follow-up work below completes the listed variant coverage and offline build
review; physical campaign execution remains separate.

### Follow-up coverage and candidate preparation

The next offline pass added matrix-specific cases:

- Delayed reverse response: all 12 results retained.
- Transient reverse response: sampled peak 4/4 counts and final net 0/-2 are
  preserved as a small result; later wrong-direction travel stops at write 7.
- Direction-dependent residuals: seven results retained; write 8 stops on the
  second consecutive small response. This is an expected experimental outcome,
  not a reason to remove the stop or claim accurate arrival.
- Lost receipt acknowledgment: no retry or resume; read-only reconciliation
  reports that the accepted receipt may already have enabled the next leg.
- Export failure: no receipt and no second write.

The expanded seven-file regression command below passed 67 tests. Candidate r37
was staged from pinned r36 with exactly five changed headers (matrix preparation,
controller selector, policy outcome, owner progression, and board selection).
Stage export: `wizard-20260920T165015675676Z-ab463a965fe342bab6e0282dba88bc75`.
No settings, credentials, startup code or installed firmware were changed.

### r37 compiled candidate review

- Compile export: `wizard-20260920T165204433480Z-9ee192ff5bd24979a284023834ad2400`.
- Review export: `wizard-20260920T165240191510Z-7d095e8e200841ae9fd0036ac411a21a`.
- App SHA-256: `24a3f58df32b5c3db77a6952ed22bf1eddc79c535760afc90abcc67d8e8806ee`.
- App bytes: 1,156,080; available app-slot headroom: 154,640 bytes.
- Bootloader and partition hashes match the reviewed r36 profile.
- Original paired backups and retained recovery app passed integrity checks.
- Largest reviewed individual compiled frame: 1,072 bytes. This is not proof
  of total stack usage; runtime resources remain unverified for r37.
- 67 regression tests plus 12 staged-source/native tests passed in this turn.

The offline reviewer reports `deployable=false`: no current device bytes or
runtime state were verified, and no hardware was accessed. Installation and
startup authorization are not inferred from these artifacts. Installed r36 and
its consumed campaign remain untouched.

Next: connect the pinned r37 artifact and `MatrixRunner` to the existing one-use
deployment/startup/launch checks, test those checks offline, then obtain the
bounded installation/startup and matrix-run authorization. After installation,
use fresh measurements rather than historical pose values; retain each result
before allowing the next leg. Do not add another firmware change merely to
force all simulated fault cases to complete.

### r37 deployment and launch integration — completed offline

The installer now recognizes only the pinned r37 app (1,156,080 bytes, hash
above), with r36 as its required predecessor and a separate one-use r37 journal.
The installation-evidence reader and read-only startup observer recognize r37.
`scripts/run_r37_matrix.py` selects `MatrixRunner`, requires an r37 startup export,
and atomically reserves `r37-capture-<boot>.json` before creating the transport.
Failure does not delete the reservation, restart the controller, or retry motion.

Validation: 200 tests passed across CLI reservation, deployment preflight,
installation evidence, startup binding, matrix socket campaigns and staged-source
integrity. The actual local r37 deployment preflight also passed, with
`hardware_access=false`, `journal_reserved=false`, and
`deployment_authorized=false`. Neither firmware nor startup code changed in this
integration step. No r37 installation or hardware startup has occurred.

#### Runbook (from `software`; live steps require authorization)

1. Repeat local installer preflight:
   `..\.venv\Scripts\python.exe scripts/deploy_reviewed_diagnostic_app.py --revision 37 --preflight-only`
2. After explicit approval for one app-only installation and one startup:
   `..\.venv\Scripts\python.exe scripts/deploy_reviewed_diagnostic_app.py --revision 37 --authorized-app-only-and-startup`
   Preserve settings and credentials. Stop on any error; do not rerun automatically.
3. Read-only startup observation, which does not itself reset the controller:
   `..\.venv\Scripts\python.exe scripts/observe_r10_startup.py --revision 37`
   Retain the resulting startup export ID. Stop if the startup is not verified.
4. Use that exact new export ID for local launch preflight:
   `..\.venv\Scripts\python.exe scripts/run_r37_matrix.py --startup-export <r37-startup-export-id> --preflight-only`
5. After bounded movement authorization and clear workspace confirmation:
   `..\.venv\Scripts\python.exe scripts/run_r37_matrix.py --startup-export <r37-startup-export-id> --authorized-twelve-leg-campaign-clearance-confirmed`
   Native preparation acquires fresh positions and targets before admission.
   Maximum 12 legs, fixed speed 20/acceleration 1, 4/8/12-count target changes,
   existing excursion limits, per-leg exports, no automatic retry or extra return.
6. Review exports under `runs/wizard-exports`. Report retained results, actual
   sampled displacement, residuals and any stop cause separately; completion
   does not prove stylus-tip accuracy or authorize another campaign.

Next action is the authorized installation/startup and bounded matrix run, not
another firmware revision. Camera, physical contact and stylus accuracy remain
out of scope.

### Approved r37 hardware run — 2026-09-20

Installed r37 once, app-only; full readback matched the pinned app SHA-256 and
protected regions were unchanged. One startup was sent. Read-only startup checks
passed with boot `3edba6a2a8169615fcf01dabda2fe997`, stable IDLE state and no storage
fault. Installation export: `wizard-20260920T170024896884Z-2cd0489e86e543d2bca53760c8a49ce3`.
Startup export: `wizard-20260920T170025311857Z-b5e382c1584844baad06de06c90e69a5`.

The authorized matrix acquired fresh target anchor 2389/1725 and measured anchor
2398/1718 for servos 12/13. Eight target writes occurred; seven result receipts
were accepted, followed by terminal NO_CLEAR_RESPONSE at leg 7 (zero-based).
The final failed leg was exported without a receipt. No retry, extra return,
reset, torque command or follow-on movement was sent.

| Leg (1-based) | Target 12/13 | Measured endpoint 12/13 | Net change 12/13 | Result |
|---|---|---|---|---|
| 1 | 2385/1729 | 2395/1722 | -3/+4 | Settled miss |
| 2 | 2389/1725 | 2395/1722 | 0/0 | Small: no sampled displacement |
| 3 | 2381/1733 | 2391/1726 | -4/+4 | Settled miss |
| 4 | 2389/1725 | 2391/1724 | 0/-2 | Small: one-sided response |
| 5 | 2377/1737 | 2386/1730 | -5/+6 | Settled miss |
| 6 | 2389/1725 | 2391/1724 | +5/-6 | Within two-count endpoint tolerance |
| 7 | 2385/1729 | 2391/1724 | 0/0 | Small: no sampled displacement |
| 8 | 2389/1725 | 2391/1724 | 0/0 | Stop: second consecutive small result |

Small-result windows contained 19 samples over approximately 2.06 seconds.
These observations do not exclude movement between acquisitions. Positions are
servo-reported counts, not independent Cartesian/stylus measurements. The final
recorded pose is historical, not a continuously tracked current pose.

Run export: `wizard-20260920T170057808629Z-794d9f59a6c14dad9b37178148c2b70d`.
Fault export: `wizard-20260920T170057579733Z-c2a0a1d155cb4fc5aa37ac5b26e11e68`.
Final-leg export: `wizard-20260920T170057744815Z-7c48419ee435484b97211c2fe9315cb2`.
All ten run/result/fault bundles passed integrity verification using absolute
paths. (An initial relative-path verification call was rejected; no artifact
was changed to resolve that caller-path issue.)

Interpretation: communication and fresh encoder response are working, including
bidirectional measured displacement at the 12-count target step. Smaller reversals
often produce little/no net response, and the same return target settles at
different positions depending on history. Forward residuals were +9 to +10 / -7
counts; return residuals ranged from +6/-3 to +2/-1. This supports investigating
direction/history-dependent deadband or hysteresis, but does not isolate a
mechanical cause or justify a universal fixed compensation.

Next: analyze this retained dataset against the existing constant/directional
simulations before choosing another campaign. Do not reinstall firmware merely
because the matrix stopped. The r37 campaign and approval are consumed; any new
startup or movement campaign needs its own bounded scope. No compensation was
applied in this run, and legs 9–12 were not attempted.

### Offline model comparison after the physical run

Reproducible analyzer: `scripts/review_r37_matrix_models.py`, with pure model
logic in `matrix_model_review.py`; six unit tests passed (including no refitting
from held-out data). Verified analysis export:
`wizard-20260920T170440265418Z-23aea01dab354f209f8c8ca5b3369e06`.
No network, hardware, firmware, settings or compensation changes were made.

Fits use legs 1–6 only. Legs 7–8 are chronological held-out checks. Models predict
one endpoint at a time from the measured starting position; they are not an
open-loop trajectory simulation. Absolute prediction errors below pool both
selected servos, in encoder counts:

| Model | Held-out mean absolute error | Held-out maximum error |
|---|---:|---:|
| One constant residual | 2.25 | 4.50 |
| Separate forward/reverse residuals | 1.92 | 3.67 |
| Stateful position band | 0.00 | 0.00 |

The third hypothesis predicts no displacement when the current measured position
is already within a target-relative band; otherwise it predicts the nearest band
edge. Edges fitted only from clearly moving training legs were +2 to +9.67 counts
for servo 12, and -7 to -1 for servo 13. It accounts for why repeating a target
change does not guarantee repeating a physical displacement.

IMPORTANT: both held-out legs had zero sampled net movement. Model selection
itself was informed by this same run. Zero error on those two endpoints is not
general accuracy validation, causal diagnosis, or permission to deploy a
compensator. In particular, target registers remain coupled while these fitted
encoder bands are separate observations, not independently assignable commands.

#### Best next bounded experiment (proposal, not authorized motion)

1. Freeze these model parameters before collecting more evidence. Compare all
   three models on new clearly moving outbound AND return legs.
2. Prefer repeating the already tested 12-count target separation at the same
   speed/acceleration before adding speed variation or larger excursions. The
   first 12-count pair produced -5/+6 then +5/-6 measured changes. Test repeatability
   rather than assuming that one pair establishes it.
3. Use fresh poses and target registers, validate the full proposed path against
   existing per-leg/campaign bounds, and keep the current no-retry and export
   gates. The earlier endpoints 2377/1737 and 2389/1725 are historical references,
   not automatically reusable live targets. Plan at most three outbound/return
   pairs and retain actual starting position for every prediction.
4. Do not replay the current r37 matrix: it begins with the smaller steps that
   produced the two-small stop. The installed selector does not admit an arbitrary
   alternate sequence. Prepare the narrower repeatability experiment offline
   through the existing authenticated manifest contract; any necessary controller
   selection change and startup must be reviewed and explicitly approved.
5. After new data, compare per-direction mean/max prediction errors and same-target
   endpoint spread, including misses and partial outcomes. Do not fit on that
   validation set and then report it as held out. Only then propose compensation.

No firmware revision is being made merely to remove the observed stop, and no
claim about keyboard hit rate or Cartesian millimetre accuracy follows yet.

### Six-leg repeatability preparation — completed offline

`shoulder_repeatability_plan.py` freezes the three fitted parameter sets with
SHA-256 and validates an exact six-leg proposal through the existing manifest
validator. `scripts/prepare_repeatability_plan.py` reads verified r37 model and
final-pose exports, without hardware access, and retains provenance and predictions.

- Proposal export: `wizard-20260920T170731881182Z-5aa06999afa04b93a1c450b826e54391`.
- Frozen model hash: `963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5`.
- Historical start: target 2389/1725, measured 2391/1724.
- Historical example targets: 2377/1737 then 2389/1725, repeated three times.
- Stateful simulated endpoints: about 2386.67/1730 outbound and 2391/1724 return.
  Predicted changes: approximately -4.33/+6 then +4.33/-6 counts.
- Commands remain uncompensated; fitted numbers only predict outcomes.
- This rollout propagates predicted states for illustration. Actual scoring must
  use each newly measured starting pose and must not refit the frozen parameters.

Native source now supports a trusted `Repeatability` selector, producing exactly
six legs with offsets `(-12,0)*3`. `RepeatabilityRunner` independently checks that
same sequence against the fresh reference and retains existing export and total
excursion checks. This is offline source only: no board wiring, live launcher,
staging, compilation, installation, restart or movement occurred in this step.

Unlike the exploratory twelve-leg matrix, this six-leg experiment requires clear
response on every leg. Its manifest does not activate the matrix-only small-result
allowance. A small response retains its failure data and stops; there is no retry
or additional return. Existing limits, speed 20 and acceleration 1 are unchanged.

Validation: 30 model/planner/native-socket/matrix/matched tests passed, plus eight
staged-integrity/composition tests. Native/socket simulations complete all six
legs for constant and direction-dependent residual fixtures. Frozen reverse
stops at the second write, exports its record, sends no second receipt and never
issues a third write. Installed r37 and its frozen artifact remain unchanged.

Next implementation: stage a minimal candidate from frozen r37 changing only
preparation/selector support and board selection; compile/review it. Add a
revision-bound six-leg launcher that binds the frozen model export and preserves
predictions alongside per-leg evidence. Only after those offline checks and
explicit installation/startup/campaign approval should this run on hardware.

### r38 repeatability candidate and launcher — ready for approval

Completed offline on 2026-09-20:

- Staged from frozen r37 with exactly three changed headers:
  `characterization_prepare.h`, `characterization_controller.h`, and
  `characterization_smoke_board.h`. Owner, outcome policy, startup, settings and
  credentials were not changed. No hardware access or installation occurred.
- Stage export: `wizard-20260920T171651296628Z-de279c39668f4b9fa807aa26ddc9db7b`.
- Compile export: `wizard-20260920T171839175122Z-d0ed0e8ab5634672a1f7913cba0137f4`.
- Review export: `wizard-20260920T171917875430Z-2a0ed0cb7d7e4204946ca57e81dbc160`.
- App SHA-256: `eee1b0f9b8b835573e0237f830108e2f4ead3f88efc3a11651401c7130f0d92e`.
- App size 1,156,048 bytes; slot headroom 154,672 bytes. Bootloader/partition
  profile and recovery artifacts verified. Largest reviewed individual frame
  1,072 bytes, not a total-stack guarantee. Offline review remains
  `deployable=false` until the authorized device/runtime checks are performed.
- Actual local deployment preflight passed with r37 predecessor, preserved
  filesystem hash, no journal reservation and no hardware access.
- 221 tests passed across launcher, frozen-model binding, installation/startup
  evidence, deployment preflight, native/socket runner and candidate review.

`run_r38_repeatability.py` binds the exact pinned model proposal and SHA-256,
requires an r38 startup receipt and reserves a boot once before opening transport.
`RepeatabilityRunner` exports frozen parameters and hypothetical rollouts before
sending start. After each retained result, it scores all three fixed models using
that leg's recorded measured starting pose, exports the score and verifies its
bundle before transmitting a continuation receipt. Prediction-export failure
prevents start; score-export failure prevents continuation. No model refitting or
compensation is performed. Failed terminal legs remain in the usual failure
exports and must also be included in subsequent offline analysis.

#### Approved-operation commands (not run yet)

From `software`, after explicit approval for one app-only installation/startup
and one six-leg campaign with the area clear:

```powershell
..\.venv\Scripts\python.exe scripts/deploy_reviewed_diagnostic_app.py --revision 38 --preflight-only
..\.venv\Scripts\python.exe scripts/deploy_reviewed_diagnostic_app.py --revision 38 --authorized-app-only-and-startup
..\.venv\Scripts\python.exe scripts/observe_r10_startup.py --revision 38
```

Only if installation and read-only startup checks pass, substitute the newly
created startup export ID below (never reuse an r37 record):

```powershell
..\.venv\Scripts\python.exe scripts/run_r38_repeatability.py --startup-export <new-r38-startup-export-id> --preflight-only
..\.venv\Scripts\python.exe scripts/run_r38_repeatability.py --startup-export <new-r38-startup-export-id> --authorized-six-leg-campaign-clearance-confirmed
```

Native preparation reacquires fresh positions and target registers before any
target write. Maximum six legs: three -12/+12 target pairs at speed 20 and
acceleration 1, within the unchanged excursion limits. Stop on failed checks,
small/invalid response, uncertain delivery or export failure. No automatic retry,
extra return, new campaign, torque-off or settings changes. Preserve the one-use
journals even if an attempt fails. No additional firmware development is needed
before this bounded test unless a preflight reveals a concrete defect.

### r38 physical repeatability run — COMPLETE, 2026-09-20

User approved proceeding with the scoped installation/startup and six-leg test.
One r38 app-only installation completed with exact full readback and unchanged
protected regions. One startup passed read-only checks, boot
`72faa01b36fb5a5408dc36db44f232a2`, stable IDLE, no storage fault.

- Installation export: `wizard-20260920T172507905546Z-7ff55eac6ff04df3a7baf57d0f8fed24`.
- Startup export: `wizard-20260920T172508311851Z-123ad93940d043efb899f3ebff4ca325`.
- Pre-start frozen-prediction export: `wizard-20260920T172522264374Z-e7e69c60f15342db88ae5b816d73361a`.
- Completed run: `wizard-20260920T172529936570Z-29afb96eae204b2483923ed76723933b`.

Fresh starting positions were 2391/1724 on servos 12/13. All six commands completed
with fresh target readback, clear measured response, independently checked results,
per-leg score exports and acknowledged continuation receipts. No retry, additional
return, follow-on motion or compensation was used. All 14 run/prediction/result/
score bundles passed integrity verification. The separate installation/startup
exports also passed their own creation-time verification.

| Leg | Target 12/13 | Measured endpoint 12/13 | Measured change | Classification |
|---|---|---|---|---|
| 1 | 2377/1737 | 2385/1731 | -6/+7 | Settled miss |
| 2 | 2389/1725 | 2391/1724 | +6/-7 | Within two-count tolerance |
| 3 | 2377/1737 | 2386/1730 | -5/+6 | Settled miss |
| 4 | 2389/1725 | 2391/1724 | +5/-6 | Within two-count tolerance |
| 5 | 2377/1737 | 2386/1730 | -5/+6 | Settled miss |
| 6 | 2389/1725 | 2391/1724 | +5/-6 | Within two-count tolerance |

Same-target encoder endpoint range was one count on each selected servo for the
three outbound legs, and zero counts for the three returns. This demonstrates
local repeatability at this pose, speed and target pair, not global accuracy.
Outbound residuals remained +8/-6 or +9/-7; return residuals were +2/-1. Therefore
protocol completion does not mean every requested register endpoint was attained.

Frozen r37 models were scored on this new campaign without refitting. Pooled
absolute endpoint prediction errors over both servos and all six legs:

| Model | Mean absolute error (counts) | Maximum absolute error (counts) |
|---|---:|---:|
| Constant residual | 3.083 | 4.500 |
| Direction-dependent residual | 0.833 | 1.667 |
| Stateful position band | 0.333 | 1.667 |

This is new moving-endpoint validation, unlike r37's two zero-motion holdout legs.
The stateful model has the lowest average error here; its maximum error equals
the directional model. Six observations at one target pair cannot establish a
universal model or mechanical root cause. No stylus or independent Cartesian
measurement was used, and these results do not demonstrate millimetre accuracy.

Next: keep the installed r38 unchanged and analyze an offline compensation
proposal that respects coupled targets and direction/history. Before applying
compensation, choose a separate nearby target pair for held-out validation and
compare predictions without fitting to its outcomes. Preserve this successful
uncompensated run as a baseline. The current campaign and one-use authorization
are consumed; do not reset or launch another campaign automatically.

### Offline stateful compensation proposal — 2026-09-20

Implemented `stateful_pair_compensation.py` and reproducible exporter
`scripts/review_stateful_compensation.py`. The solver enumerates bounded coupled
target pairs instead of independently offsetting the two servos. It minimizes
worst predicted endpoint error, then squared error, then register travel. It
rejects inconsistent starting states, unsupported endpoint changes, changes
outside the observed primary target range 2377–2389, invalid coupling, joint-bound
violations and campaign excursions. It requires clear predicted motion and no
more than two predicted counts of error per servo. None of these model checks
prove physical clearance or replace fresh native feedback checks.

23 model/planner/compensation tests passed. Frozen model parameters were not
changed or refitted. No firmware, settings or installed behavior changed and no
hardware commands were sent. Installed r38 does not accept this alternate target
sequence; the proposal is not an executable live admission.

Current proposal export:
`wizard-20260920T180630996955Z-ee8cf46f611b41488c4ff50d9a3619bb`.

| Quantity | Servo 12 | Servo 13 |
|---|---:|---:|
| Historical measured start | 2391 | 1724 |
| Historical current target register | 2389 | 1725 |
| Desired measured endpoint (experiment choice) | 2388 | 1729 |
| Proposed compensated target registers | 2378 | 1736 |
| Stateful predicted endpoint | 2387.667 | 1729 |
| Predicted signed error | -0.333 | 0 |
| Uncorrected coupled comparison registers | 2387 | 1727 |
| Uncorrected model-predicted signed error | +3 | -5 |

The desired measured pair need not sum to 4114, but command registers must.
Therefore the uncorrected comparator is the closest legal coupled target pair,
not an invalid direct write of the desired measured values. Both alternatives
are scored from the SAME measured starting pose. Model predictions alone cannot
establish that either outcome will occur.

Target 2378/1736 lies inside the observed command interval but was not present in
the retained r37/r38 datasets: it is unvalidated interpolation. The exporter now
derives that novelty flag from verified prior records rather than assuming it.
An earlier offline draft (`wizard-20260920T180602033409Z-14c6d496bde5447c96a248d40aa43d92`)
selected the already-tested 2377/1737 target and incorrectly labelled it unseen;
it is SUPERSEDED, retained unchanged for audit, and must not be used for novel-target
validation. No command from either draft has been sent.

#### Next validation design

Freeze this proposal before a new physical test. Reacquire starting target and
position; reject or re-plan offline if the starting state differs materially.
Test the unseen command while keeping speed/acceleration and bounds unchanged.
Evaluate measured endpoint error against the desired pair (not just the written
registers), and compare it with the predeclared uncorrected prediction. A genuine
physical A/B improvement claim additionally requires an uncompensated observation
from a comparable starting pose and direction/history, not merely the model's
prediction. Do not send A then B and treat them as matched-start trials.

Include small/no-motion and failed outcomes in the analysis; do not discard them
or refit before scoring. Repetition and a reverse-direction validation remain
necessary before enabling general compensation. Retain the successful r38
uncompensated repeatability baseline. No new installation or campaign is
authorized by this offline proposal.

### Matched-start A/B pilot — prepared offline

`compensation_ab_plan.py` and `scripts/prepare_compensation_ab.py` now generate
two separately admitted three-leg campaigns with identical conditioning history.
Verified plan export:
`wizard-20260920T180844757144Z-064f2b53fe9848bf97f08e077e984202`.
15 A/B and compensation unit tests passed. No firmware changes, startup, hardware
queries or movements occurred in this preparation step.

| Campaign | Conditioning outbound | Conditioning return | Terminal trial target |
|---|---|---|---|
| Uncorrected control | 2377/1737 | 2389/1725 | 2387/1727 |
| Compensated candidate | 2377/1737 | 2389/1725 | 2378/1736 |

Desired measured trial endpoint is 2388/1729 for both. These are historically
anchored proposals, not live targets admitted from current readings. Maximum six
target writes across the two campaigns; no extra recovery or return is included.
Speed 20, acceleration 1 and previous excursion limits remain unchanged.

Required execution/review rules:

1. Each campaign independently reacquires fresh baseline and must pass existing
   feedback, target-readback, direction, bounds and export checks. Native initial
   target registers must agree with the reviewed anchor; never silently translate
   this experiment to a changed pose.
2. Both conditioning legs require clearly measured settled responses. The return
   endpoint must be within one count per servo of reference 2391/1724 before
   permitting the terminal trial. Also inspect each recorded trial baseline.
3. Compare actual trial starting positions directly: at most one count difference
   per servo, same target registers, conditioning targets, speed and acceleration.
   If these fail, report unmatched starts, not a compensation improvement.
4. The control is predicted to have little/no displacement. Its terminal
   NO_CLEAR_RESPONSE is retained as an experimental observation only if fresh,
   settled, correct-target feedback and export validity are established. Do not
   relax the controller stop or send an automatic return to force completion.
5. Score both endpoints against the SAME desired measured pair. Include stopped
   trials and all raw evidence. The new endpoint scoring helper is descriptive
   only: it does not certify raw telemetry validity, causality or calibration.
6. This is a one-pair pilot, not a statistically strong A/B validation. If useful,
   repeat with order reversed and separately validate reverse-direction motion
   before generalizing. Do not refit the frozen model before scoring this pilot.

Interface assessment: installed r38 supports only its fixed six-leg repetition
and cannot execute these alternate three-leg manifests. Do not bypass its trusted
selector or use an unrelated low-level command route. Next implementation is
bounded control/candidate selectors plus a host runner that verifies conditioning
before authorizing trial progression, binds the frozen proposal, and exports the
terminal result even when the controller stops. The initial pilot needs no new
servo settings or feedback-policy relaxation. Any resulting firmware installation,
startup and separate campaigns must receive scoped approval before execution.

### A/B execution source implemented — offline validation complete

The native `ABControl` and `ABCandidate` selectors now produce only the fixed
three-leg manifests above. `characterization_ab_runner.py` binds the frozen model,
exports predictions before starting, verifies conditioning, and exports a terminal
endpoint audit even when the control stops for NO_CLEAR_RESPONSE. A retained
measurement does not authorize continuation or certify compensation.

Initial preparation accepts paired target registers 2389/1725 or 2387/1727,
with measured positions within one count of 2391/1724. This accommodates the
control's terminal register state without an extra reset movement. It does not
translate the experiment: both trials must still follow the same conditioning
targets, with terminal-trial target readback 2389/1725 and measured start within
one count of 2391/1724. Both host and native owner independently enforce the
conditioning-position gate before the terminal write.

Validation: **50 tests passed** across A/B, repeatability, matrix and matched
runners, comparison planning and native owner. Simulated evidence:

- Control: three writes, no clear terminal movement, endpoint retained for review;
  campaign remains INCONCLUSIVE, without a return or retry.
- Candidate: three writes and successful simulated completion.
- Wrong conditioning endpoint: host withholds progression after two writes.
- Host gate deliberately omitted in a test fixture: native BASELINE_ADMISSION
  independently stops before the third write.

These are fake-servo simulations through authenticated host/native test interfaces,
not physical accuracy evidence. Installed r38 is unchanged. No installation,
startup, hardware query, settings change or physical movement occurred in this step.

Remaining release work is tracked below. Do not run these manifests through
installed r38 or broaden an unrelated command route.

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/test_characterization_ab_runner.py tests/unit/test_compensation_ab_plan.py tests/unit/test_characterization_repeatability_runner.py tests/unit/test_characterization_matrix_runner.py tests/unit/test_characterization_matched_runner.py tests/unit/test_shoulder_characterization_owner.py -q
```

Validation: 62 tests passed across matrix and matched runners, host signing,
offline classification, authenticated socket campaigns, native owner and result
codec. Command from `software`:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/test_characterization_matrix_runner.py tests/unit/test_characterization_matched_runner.py tests/unit/test_characterization_host_session.py tests/unit/test_shoulder_movement_matrix.py tests/unit/test_characterization_socket_campaign.py tests/unit/test_shoulder_characterization_owner.py tests/unit/test_characterization_result_codec.py -q
```

### Candidate staging and installation-gated launcher

Implemented `scripts/stage_ab_pilot.py` and `scripts/run_ab_pilot.py`.
The stage script verifies every frozen r38 source file against its retained
compile export, changes only three reviewed diagnostic headers and the fixed
board selector, verifies write readback, and exports the complete change hashes.
It refuses overwrite and checks export availability before creating a candidate.

Variant mapping is fixed: r39/control and r40/compensated. These are separate
compile-time candidates, not a new runtime command-selection API. Only the r39
control source has been staged so far:
`wizard-20260920T182450232728Z-34c7a059eb0a4ba09d4d980dbe908178`.

r39 compiled successfully with `default-4mb-no-psram`; verified compile export:
`wizard-20260920T182703864132Z-27fca418a8904c028739ffdf88e744ec`.
App SHA-256:
`590a2f942214e9830fdfda9ad9610cf4c71c9fec818aa3dacabc02a6291f1156`.
Compilation is not the independent release review and does not establish
hardware behavior or authorize installation. Installed r38 remains unchanged.

The launcher connects the existing authenticated transport, ABRunner, recovery
reader and verified exports. Its local preflight binds the selected revision's
installation/startup and frozen model. Before any live connection it durably
reserves the boot; a failure never removes that reservation or triggers a retry.
Terminal audit paths appear in the CLI output even for an inconclusive trial.

At initial launcher completion the installation registry rejected r39/r40.
r39 review and binding have now been completed as recorded below; r40 remains
unreviewed. No fallback to r38 is allowed. Tests mock installation evidence to
exercise the live branch without connecting to hardware.

Validation: 59 launcher/runner/planning/native regression tests plus 2 staging
tests passed (61 total). Covered model tampering, boot reuse, preflight with no
key/network access, claim-before-connection, fixed variant selection, preserved
files, changed predecessor rejection and overwrite rejection.

Next: complete exact-binary review, then add its pinned installation/startup
profile and installer support. Seek the scoped installation/startup and pilot
authorization only after that evidence is ready. No settings changes are needed.

### r39 control release preparation — reviewed, not installed

Offline candidate review export:
`wizard-20260920T182910494497Z-76154dbb00e04330b2b6eed869f6fb7f`.
The review checked the pinned app/compile inputs, exact four-file change set,
fixed control selector, preparation and matched-start guards, compiled diagnostic
routes, retained recovery backups and unchanged partition/bootloader identities.
App size is 1,156,384 bytes, leaving 154,336 bytes in its slot. Largest inspected
individual stack frame is 1,072 bytes; this is NOT a total-stack or runtime proof.

r39 is now pinned in the installer, installation-evidence registry, startup
observer and startup binding. Required predecessor is exactly r38. Existing
settings/credentials and protected flash checks remain unchanged. Local-only
installer preflight passed with no journal reservation, device access or reset.
The launcher still requires the actual completed r39 installation journal and
matching idle startup export: source readiness cannot substitute for those.

214 offline tests passed across A/B launcher/runner, startup binding (including
changed boot/hash/path/status/installation), installation journals, deployment
preflight and candidate-review tests. A test initially expected the wrong
exception class for a missing installation journal; it was corrected to assert
the specific durability exception. Runtime rejection behavior was unchanged.

Next hardware scope to authorize: one r39 app-only installation and one startup,
preserving settings/credentials; read-only idle checks; then one three-leg control
campaign only if fresh pose, direction, limits and exports pass. Stop on any failed
gate; no retry, extra return, torque/configuration changes or subsequent campaign.
The planned control may finish NO_CLEAR_RESPONSE; retain and score its endpoint,
do not classify that as success or force an additional movement. r40 preparation
and the compensated campaign remain separate future work.

No hardware operations occurred during this release-preparation step. r38 remains
the last verified installed image; the current physical pose was not remeasured.

### Approved r39 installation and physical control pilot — executed

Following explicit approval, r39 was installed once app-only and started once.
Full application readback matched the pinned SHA; protected regions were unchanged.
No provisioning or settings changes occurred. Read-only startup checks observed
stable IDLE with no storage fault. Boot: `a58819873f57bb18eec41273582649d0`.

- Installation: `wizard-20260920T183744176126Z-92f43eb6d6114d868c6d3e524c55c837`.
- Startup: `wizard-20260920T183745080547Z-c5c4c2b457114eccb68d4ade33c30d75`.
- Frozen predictions: `wizard-20260920T183755483403Z-63bde00a4f764df4ae49b4e59da052cc`.
- Run: `wizard-20260920T183801292549Z-c5e35a17c9194061a5e6ae75d383915c`.
- Terminal audit: `wizard-20260920T183801352365Z-150c883b704449b581992fc4a59618c2`.

Fresh initial measured shoulder pair was 2391/1724, targets 2389/1725.
All values below are servo encoder counts, not independently measured Cartesian
positions or stylus accuracy.

| Leg | Written targets | Measured endpoint | Net change | Outcome |
|---|---|---|---|---|
| Conditioning outbound | 2377/1737 | 2385/1730 | -6/+6 | SETTLED_MISS |
| Conditioning return | 2389/1725 | 2391/1724 | +6/-6 | SETTLED_ACCURATE |
| Uncorrected control | 2387/1727 | 2391/1724 | 0/0 | NO_CLEAR_RESPONSE / STOP |

Both conditioning gates passed. Terminal evidence contains 18 fresh samples over
1,939,525 microseconds from first sample start to last completion, with correct
target readback. The terminal audit retained this measurement as usable; desired
endpoint 2388/1729 was missed by +3/-5 counts. The frozen stateful-band prediction
was exactly 2391/1724 for this control. This supports its no-displacement prediction
for this one case; it does not prove compensation or identify the physical cause.

Controller status reported FAULT, two completed legs, three writes attempted.
The host preserved INCONCLUSIVE and issued no third result receipt, retry, return
or subsequent movement. `controller_stop_confirmed` remains false in the generic
run report; the retained FAULT response is evidence of campaign termination, not
an independent mechanical-stop certification. All 10 installation/startup/run/
prediction/reference/result/fault/audit bundles passed export integrity checks.

Last recorded full positions: 2047,2391,1724,2904,1591,2041,2047. Last targets:
2047,2387,1727,2907,1589,2040,2047. These are historical observations, not perpetual
live-state guarantees. The r39 boot claim and deployment journal are consumed.

Next: prepare/review r40 compensated candidate offline, then obtain scoped
installation/startup and three-leg candidate authorization. Use identical
conditioning, verify matched trial starts, and compare actual errors to this
control without refitting. No further physical operation is authorized by this
completed one-campaign approval.

### r40 compensated pilot — offline preparation complete

r40 is staged, compiled, reviewed and integrated with the existing installation/
startup binding. It is NOT installed. Its staged source differs from frozen r39
only in `characterization_smoke_board.h`: ABControl becomes ABCandidate. No model
refit, feedback-policy change, servo setting or runtime selector route was added.

- Stage: `wizard-20260920T185155494852Z-1e1237d73e1d48bc9e6592af0b7cddc1`.
- Compile: `wizard-20260920T185347392266Z-f3e2a8433061406d8f5eda3789aa139d`.
- Review: `wizard-20260920T185410694745Z-9399b344b6434d32ba81c5718d567618`.
- App SHA-256: `0bdfad949388b758fff3b8b177a24c9da87e7089ed6a952c6a03b6daf9833213`.
- App bytes: 1,156,384; slot headroom: 154,336 bytes.
- Required installed predecessor: pinned r39; separate one-use r40 journal.

Local installer preflight passed without hardware access or journal reservation.
238 tests passed covering comparison-source validation, staging, launcher,
startup/installation binding, deployment preflight and native simulated campaigns.
No hardware operations occurred during this preparation.

`scripts/compare_ab_pilot.py` now verifies exported audit/source bundles, fixed
manifests, conditioning results, actual terminal-source linkage, raw endpoint
agreement and frozen-prediction provenance before descriptive comparison. The
reader successfully checked the real r39 control audit. It requires both audit
IDs; no candidate result or comparison has been fabricated. It does not grant
movement authority or certify Cartesian accuracy/general compensation validity.

Physical scope ready for approval: one r40 app-only installation and one startup,
preserving settings and credentials; read-only idle checks; then one three-leg
compensated campaign if fresh checks pass. Conditioning targets remain
2377/1737 then 2389/1725; terminal target is 2378/1736. Desired measured endpoint
remains 2388/1729. Frozen predicted endpoint is approximately 2387.667/1729,
an unproven prediction rather than an acceptance guarantee. No retry, extra
return, settings/torque changes or follow-on campaign.

After execution, export and compare against control audit
`wizard-20260920T183801352365Z-150c883b704449b581992fc4a59618c2`.
Require trial-start agreement within one count per servo and identical conditioning.
Keep stopped outcomes; do not refit before scoring. Even an improved single pair
remains a pilot, requiring repetitions and reverse-direction evidence before
generalization.

### Approved r40 installation and compensated pilot — executed

Following explicit approval, r40 was installed once app-only and started once.
Full application readback matched the pinned SHA and protected regions were
unchanged. No provisioning or settings changes occurred. Read-only startup checks
observed stable IDLE with no storage fault. Boot:
`c6a1d50dfbd89f1ceb9ae37d0732c1e6`.

- Installation: `wizard-20260920T185915842279Z-3e32abdfa701476ca49f1b5db3dde21a`.
- Startup: `wizard-20260920T185916537342Z-7f8b1d4e98ce4e97aced0489d9faa622`.
- Frozen predictions: `wizard-20260920T185923845306Z-ed0e228d49e44fd2a1420233ffc27aec`.
- Run: `wizard-20260920T185927984423Z-385785fe321a4de39e56dd37098b404a`.
- Terminal audit: `wizard-20260920T185928036920Z-212a0ec7b32949d5ac9117297277feb2`.
- A/B comparison: `wizard-20260920T185935526806Z-7535d6838baf4f22b93ebce0204dbb0c`.

The compensated campaign completed all three writes with no retry or extra return.
All values below are local servo encoder counts, not Cartesian measurements.

| Leg | Written targets | Measured endpoint | Net change | Outcome |
|---|---|---|---|---|
| Conditioning outbound | 2377/1737 | 2385/1731 | -6/+7 | SETTLED_MISS |
| Conditioning return | 2389/1725 | 2391/1724 | +6/-7 | SETTLED_ACCURATE |
| Compensated trial | 2378/1736 | 2387/1730 | -4/+6 | SETTLED_MISS vs written goal |

The terminal trial started at exactly 2391/1724, identical to the retained control
trial. Both campaigns used the same conditioning targets and returned to the same
measured terminal start. The compensated endpoint was 2387/1730 versus desired
2388/1729: signed error -1/+1 counts. The control was 2391/1724: signed error
+3/-5. Maximum absolute error therefore improved from 5 to 1 count in this single
matched-pair pilot. The frozen stateful prediction for the candidate was about
2387.667/1729; the actual endpoint differed by about -0.667/+1 count.

The compensated written target itself retained a +9/-6 count residual, so the
result is evidence that the predeclared target offset improved this desired
endpoint—not evidence that raw target tracking became exact. The comparison
export deliberately retains `compensation_validated: false`: one successful pair
does not establish general compensation, Cartesian accuracy, contact accuracy or
causality across the workspace. Repeat trials and reverse-direction/out-of-sample
tests remain necessary before enabling this broadly.

All 10 installation/startup/prediction/reference/result/run/audit/comparison
bundles passed integrity checks. r40 and its boot claim are consumed. No further
movement was issued after the compensated terminal endpoint.

### Next validation stage — frozen offline plan

Verified plan export:
`wizard-20260920T190401776719Z-da3be81ec93e4e6299dad3dadcfe7c2c`.
`next_compensation_validation.py` derives this plan from the verified r39/r40
terminal audits and unchanged frozen model. Seventeen focused planning/comparison
tests passed. No hardware access, startup, installation or movement occurred.

The next stage deliberately separates three campaigns:

1. **Forward repeat (4 writes):** normalize to 2389/1725, condition to
   2377/1737, return to 2389/1725, then repeat candidate 2378/1736.
2. **Reverse candidate (3 writes):** condition 2389/1725 then 2377/1737,
   followed by candidate 2385/1729.
3. **Reverse control (3 writes):** identical conditioning followed by control
   2386/1728. Candidate-before-control reverses the earlier forward A/B order.

Maximum is ten writes across separately admitted campaigns; there is no automatic
retry or return. The retained r40 endpoint 2387/1730 with targets 2378/1736 is the
required initial state for the forward repeat, within one count per joint. Reverse
trials require matched lower-side starts near 2385/1731 after their identical
conditioning. Every campaign must reacquire fresh feedback and stop independently.

For desired reverse endpoint 2388/1729, the unchanged model proposes candidate
2385/1729 with predicted endpoint 2387/1728, versus control 2386/1728 with
predicted endpoint 2388/1727. These are hypotheses, not accuracy promises. The
reverse trials are particularly valuable because they test whether the learned
offset behavior transfers across direction rather than merely repeating the
successful forward case.

This is a plan only. Installed r40 remains unchanged and its prior boot/campaign
claims remain consumed. Next implementation must add fixed compile-time selectors,
native matched-start gates, host export/scoring, simulation, candidate review and
fresh startup binding before any physical execution is proposed.

### Forward-repeat implementation — reviewed, not installed

Fixed native selectors now exist for ForwardRepeat, ReverseCandidate and
ReverseControl. Each produces only its reviewed absolute manifest. Native trial
gates independently require the upper matched start for the forward repeat and
the lower matched start for reverse trials. Host runner checks the same conditions,
binds frozen predictions before movement and exports terminal measurements.
Simulation covers all three successful campaigns plus a deliberately wrong lower
conditioning endpoint; the latter stops with BASELINE_ADMISSION before its trial
even when the host result gate is deliberately omitted.

The first implementation candidate is r41/ForwardRepeat:

- Stage: `wizard-20260920T190913144896Z-a34166e1e88340f0865c10e8e9f05c56`.
- Compile: `wizard-20260920T191113385227Z-ead78ebe2fbc4f3185d9b0ab9df8033e`.
- Review: `wizard-20260920T191205226246Z-ee1d09ac979f445582bcdd3bd9a37416`.
- App SHA-256: `caa26535377b8f35e3bfdc8d0546c779db052a520a355eaab455dcf64defc5cf`.
- App bytes: 1,156,992; required predecessor: installed r40.

r41 is pinned into the installer/startup evidence path and passed local-only
installer preflight. `run_next_validation.py` binds the verified plan, exact
variant/revision, frozen model, installation/startup evidence and one-use boot
claim before opening a connection. It cannot silently select r40 or arbitrary
targets. 235 release/binding/regression tests passed after the focused native/host
simulation suite; no hardware access occurred.

Physical scope ready for explicit approval: one r41 app-only installation and one
startup, preserving settings/credentials; read-only idle checks; then one fixed
four-leg ForwardRepeat campaign if fresh r40 terminal-state and all other gates
pass. No retry, extra return, settings/torque changes or reverse campaign. Export
the repeated terminal endpoint and compare it to the first r40 compensated trial.
Reverse r42/r43 staging remains later and depends on this fresh result.

### Approved r41 forward-repeat campaign — executed

Following explicit approval, r41 was installed once app-only and started once.
Full application write/readback matched the pinned SHA-256 and protected flash
regions were unchanged. No provisioning, settings or credential changes occurred.
Read-only startup checks observed IDLE and the expected held-pair protocol on boot
`fb74b1650ea694dd19b41ab15e9129b1` before any movement.

- Installation: `wizard-20260920T192413552052Z-aad06054f5214e02a4afbac94ed12aa8`.
- Startup: `wizard-20260920T192413911578Z-495fd12996df4e839894eb35662955dd`.
- Frozen predictions: `wizard-20260920T192422067292Z-9643f2fdd6d6479a9dcf23dd98bf23bb`.
- Initial reference: `wizard-20260920T192422130575Z-08834a4bf44e41689d06721f1b2988c1`.
- Run: `wizard-20260920T192427124401Z-7444c16b7bf743638d9efae7eb8ea28f`.
- Terminal audit: `wizard-20260920T192427176078Z-ee1c1fb42de14a4698cfc1f3c1c8ee7c`.

The initial fresh measured pair was 2386/1730 with retained goals 2378/1736,
inside the reviewed one-count admission window. The fixed campaign completed all
four writes without a retry or extra movement. Values remain local servo encoder
counts, not Cartesian or stylus measurements.

| Leg | Written targets | Measured endpoint | Net change | Outcome |
|---|---|---|---|---|
| Normalize upper | 2389/1725 | 2391/1724 | +5/-6 | SETTLED_ACCURATE |
| Condition lower | 2377/1737 | 2386/1730 | -5/+6 | SETTLED_MISS |
| Condition return | 2389/1725 | 2391/1724 | +5/-6 | SETTLED_ACCURATE |
| Repeat compensated forward | 2378/1736 | 2387/1730 | -4/+6 | SETTLED_MISS vs written goal |

The repeated trial began at 2391/1724, exactly matching the first r40 candidate's
trial start, and finished at 2387/1730, exactly matching its endpoint. Against the
predeclared desired endpoint 2388/1729, both trials therefore have signed error
-1/+1 counts and maximum absolute error one count. The r41 terminal endpoint also
matches the frozen directional/stateful prediction to within about -0.667/+1
count. This is useful repeatability evidence for this one conditioned forward
transition. It does not validate a workspace-wide compensation model, Cartesian
accuracy, contact accuracy or reverse-direction behavior.

The lower conditioning endpoint varied by one count per joint from the first r40
campaign (2386/1730 here versus 2385/1731), but the following upper return and
compensated terminal endpoints reproduced exactly. All ten installation, startup,
prediction, reference, per-leg, run and audit exports passed integrity checks.
No movement was issued after the terminal endpoint.

Next: prepare and review r42 ReverseCandidate offline using the already frozen
plan and model. Its separate physical campaign must freshly reacquire state and
prove the required lower-side matched start before the reverse trial. Keep r43
ReverseControl separate and do not fit or change the model between the two.

### r42 reverse-candidate implementation — reviewed and ready

The reverse candidate is now frozen as a separate r42 application. The staged
source is derived from the pinned r40 compile inputs and changes only the three
reviewed diagnostic control headers plus the compile-time board selector. Its
manifest is fixed at 2389/1725, 2377/1737, then 2385/1729; no request can supply
alternate targets. The frozen compensation model and desired endpoint 2388/1729
remain unchanged from the predeclared validation plan.

- Stage: `wizard-20260920T192830130674Z-5156e0d64647449e970025c154ae9349`.
- Compile: `wizard-20260920T193043779230Z-a73a2d24d52242128cd5ee2c9a3b090c`.
- Review: `wizard-20260920T193204775927Z-5a61acd29ce945859a551e99b93121f1`.
- App SHA-256: `6d3405b3b42db9347ec02445b0937886ca0fba82bf38d905e3989ad48c8f71ea`.
- App bytes: 1,156,992; slot headroom: 153,728 bytes.
- Required installed predecessor: exact r41 application.

Installer, installation-evidence and startup-binding profiles now recognize only
this pinned r42 identity and upgrade edge. The native trial gate requires the
second conditioning leg to retain goals 2377/1737 and measured position within
one count of 2385/1731 before the third write. The host independently checks the
same lower-side start. Failure at either layer stops without a candidate write,
retry or automatic return.

The exact binary review found the expected routes, selector, preparation guards,
matched-start gate, retained recovery artifacts and unchanged bootloader/partition
identities. A focused release suite of 245 tests passed. Local-only deployment
preflight verified the r42 image, installed-r41 predecessor identity, preserved
filesystem expectation and unused one-use journal without device access.

Execution scope: one r42 app-only installation and one startup, preserving existing
settings and credentials; read-only idle checks; then one fixed three-leg
ReverseCandidate campaign if the fresh r41 terminal pose and every subsequent
gate pass. No retry, extra return, refit, settings/torque change or r43 control
campaign is included. Retain the terminal endpoint even if it is a miss, and use
it only as the candidate half of the still-incomplete reverse comparison.

### r42 installation recovery and reverse candidate — executed

The first r42 installation attempt stopped before any flash write. The loader
detected download mode but received no synchronization reply from the serial TX
path. The original one-use journal was retained with exactly RESERVED and STOPPED
records; r41 remained installed. A new one-use recovery helper accepted only that
exact journal, issued one hard reset without flashing or servo commands, and r41
was subsequently observed stable and IDLE on a fresh boot.

- Failed prewrite journal SHA-256:
  `30abc7feff8027500a38c712b3e239be59cb81ae438ca6139495737dd3bde8ea`.
- r41 recovery startup:
  `wizard-20260920T193603078018Z-f8da68cf462b432daba97f39da803971`.
- Recovered r41 observation:
  `wizard-20260920T193627118049Z-5e63b63aa617467da55d5e658481b23e`.

A separate second-attempt path preserves the failed journal and requires both its
exact hash and the recovery export. It passed 231 focused tests and a local-only
preflight. The second attempt installed and read back r42 successfully, preserving
all protected regions, then performed one startup.

- Installation: `wizard-20260920T194115434962Z-f6e06fb5afa04c2c8e2018f431b45b84`.
- Startup: `wizard-20260920T194115884306Z-b690de8ab03a4ed8856741b447502cd4`.
- Boot: `2776dea80fb131c8d32b106d75500b6b`.
- Frozen predictions: `wizard-20260920T194124308486Z-4ac04967cdfa4e1d90c60dc6fa2af569`.
- Initial reference: `wizard-20260920T194124371344Z-d5329664ec14460d8c50622824736d93`.
- Run: `wizard-20260920T194129721686Z-96efa9800d0f485fa91b08c9d53f8b79`.
- Terminal audit: `wizard-20260920T194129776533Z-1ccfcdad8018415ca0080be94a67ff85`.

The fixed campaign performed all three writes. Its first two conditioning legs
were exported normally. The terminal reverse-candidate write produced a small,
stable displacement, so the unchanged policy retained it as `NO_CLEAR_RESPONSE`
and fault-stopped the campaign instead of treating it as an accurate arrival.

| Leg | Written targets | Measured endpoint | Net change | Outcome |
|---|---|---|---|---|
| Condition upper | 2389/1725 | 2391/1724 | +4/-6 | SETTLED_ACCURATE |
| Condition lower | 2377/1737 | 2386/1730 | -5/+6 | SETTLED_MISS |
| Reverse candidate | 2385/1729 | 2387/1728 | +1/-2 | NO_CLEAR_RESPONSE / STOP |

The third leg began at 2386/1730 and finished at 2387/1728. That endpoint exactly
matches the frozen stateful-band prediction and is -1/-1 counts from the desired
2388/1729 endpoint. It is therefore useful candidate evidence, but the campaign
remains INCONCLUSIVE because the terminal movement did not meet the unchanged
clear-response classifier. It must not be rewritten as a pass.

All ten installation, startup, prediction, reference, result, fault, run and audit
exports passed integrity verification. No retry, return or r43 control movement
was issued after the fault. The retained terminal goals are 2385/1729 and measured
position is 2387/1728; these are historical observations pending fresh reacquisition.

Next: prepare and review r43 ReverseControl offline without changing the model.
Its separate physical campaign should use the retained reverse-candidate terminal
as its admitted initial state, repeat identical upper/lower conditioning, then
write the predeclared control target 2386/1728. Compare the candidate and control
only after both raw terminal audits verify. Preserve `NO_CLEAR_RESPONSE` as a
measured outcome rather than forcing additional movement.

### r43 reverse-control implementation — reviewed and ready

r43 is now staged and compiled from the same pinned r40 source basis with the same
three reviewed diagnostic headers. Its only variant-specific change relative to
that basis is the compile-time `ReverseControl` selector. The model was not refit
after seeing r42. The fixed manifest is 2389/1725, 2377/1737, then the previously
declared control target 2386/1728.

- Stage: `wizard-20260920T194307726100Z-c1b6444fb03448969cfd8d19655de8a6`.
- Compile: `wizard-20260920T194503301024Z-de44baaa4ad540b3b20a812c290df83a`.
- Review: `wizard-20260920T194546707012Z-b8c32ef012224eb193a00565332fca2e`.
- App SHA-256: `459e1f31ac103c634b2205654501693d9116bded2bcd9ac1bf8de5284a20fb1b`.
- App bytes: 1,156,992; slot headroom: 153,728 bytes.
- Required predecessor: exact installed r42 application.

Installer, installation-evidence and startup profiles now bind the exact r43
binary and r42 predecessor. The native and host gates require the retained r42
terminal goals 2385/1729 and measured pair near 2387/1728 at preparation, then a
fresh lower-side trial start near 2385/1731 after identical conditioning. The
release suite passed 257 tests, and local deployment preflight verified the exact
binary, predecessor, filesystem expectation and unused one-use journal without
hardware access.

Execution scope: one r43 app-only installation and startup, read-only checks, then
one fixed three-leg ReverseControl campaign if all fresh gates pass. No retry,
automatic return, model change or additional movement. Afterward compare the raw
r42 candidate and r43 control terminal audits; neither small-response result may
be promoted to a successful arrival merely because its endpoint is informative.

### r43 reverse control and frozen comparison — executed

r43 was installed once app-only from the exact r42 predecessor. Full application
readback matched the reviewed hash and protected regions were unchanged. Startup
checks observed the expected protocol stable and IDLE on boot
`311d4947ef8c41fd179740c54e92f93c` before movement.

- Installation: `wizard-20260920T195039641648Z-a643493710bd46e88d2d486bf850abc3`.
- Startup: `wizard-20260920T195039980259Z-0f831f521f0f419197adc7c512bba876`.
- Frozen predictions: `wizard-20260920T195047385838Z-e67788c48a8d43c6a665ff4930ebf67c`.
- Initial reference: `wizard-20260920T195047426915Z-23f09fa2c451419ea99ea0d0efa057d2`.
- Run: `wizard-20260920T195051454497Z-5fba0678626b450bb19056d05d12ae59`.
- Terminal audit: `wizard-20260920T195051508882Z-3e1076f2aa1146449ad46398fd8b2c0c`.
- Reverse comparison: `wizard-20260920T195237993804Z-4556252271304711963b722a2bcd1a9a`.

The fixed control campaign completed all three writes without retry or additional
movement:

| Leg | Written targets | Measured endpoint | Net change | Outcome |
|---|---|---|---|---|
| Condition upper | 2389/1725 | 2391/1724 | +4/-4 | SETTLED_ACCURATE |
| Condition lower | 2377/1737 | 2385/1731 | -6/+7 | SETTLED_MISS |
| Reverse control | 2386/1728 | 2388/1727 | +3/-4 | SETTLED_ACCURATE |

The reverse candidate and control used the same frozen model and manifests declared
before either result. Their trial starts were 2386/1730 and 2385/1731 respectively,
matching within one count per joint as required. Against desired endpoint 2388/1729:

| Variant | Measured endpoint | Signed error | Max absolute error | L1 error | Squared error |
|---|---|---|---:|---:|---:|
| Reverse candidate | 2387/1728 | -1/-1 | 1 | 2 | 2 |
| Reverse control | 2388/1727 | 0/-2 | 2 | 2 | 4 |

The reverse candidate improves maximum absolute and squared encoder error, while
L1 error ties. Both endpoints exactly match their frozen stateful-band predictions.
However, the candidate was retained as `NO_CLEAR_RESPONSE` because its physical
delta was small, whereas the control met `SETTLED_ACCURATE` relative to its written
target. The comparison is eligible and useful, but it deliberately retains
`general_compensation_validated: false`: this is one local reverse pair, not a
workspace-wide, Cartesian or contact-accuracy validation.

All ten r43 installation/startup/prediction/reference/result/run/audit/comparison
bundles passed integrity verification. The comparison reader also validates both
raw terminal records, conditioning exports, fixed manifests, matched starts and
frozen-model provenance. No movement was sent after the control endpoint.

Next: consolidate the two forward trials and reverse candidate/control pair into
a small local bidirectional evidence record. Keep the current model frozen. The
next useful physical expansion is a new nearby pose or a second reverse repetition,
not another immediate refit. Only after multiple pose/direction groups should a
replacement compensation map be trained and evaluated on held-out campaigns.

### Consolidated bidirectional record and nearby held-out plan — complete offline

The five terminal trials and both predeclared comparisons are now consolidated in
one hash-verified diagnostic record:

- Bidirectional evidence: `wizard-20260920T195904937964Z-0a6902dbff5340e887db1d93b27259f6`.
- Superseded three-leg held-out draft:
  `wizard-20260920T200021168296Z-a6963a3bfbb94173ac43d23edda3c861`.
- Current two-leg held-out plan:
  `wizard-20260920T200421886717Z-b78da5a8c1c64ca0a661883a2cb52828`.
- Frozen model SHA-256 remains
  `963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5`.

The consolidator independently reopens the raw r39/r40/r41/r42/r43 campaign
records, each conditioning result, fixed manifest, frozen prediction and terminal
audit. It then verifies that the forward and reverse comparison files bind the
exact audit hashes. The retained local count-space findings are:

| Direction/trial | Measured endpoint | Signed error | Max absolute error |
|---|---:|---:|---:|
| Forward control | 2391/1724 | +3/-5 | 5 |
| Forward candidate | 2387/1730 | -1/+1 | 1 |
| Forward candidate repeat | 2387/1730 | -1/+1 | 1 |
| Reverse candidate | 2387/1728 | -1/-1 | 1 |
| Reverse control | 2388/1727 | 0/-2 | 2 |

This establishes exact forward repeatability at the tested endpoint and lower
maximum count error for the candidate in both tested directions. It does not
establish general compensation, Cartesian accuracy, keyboard accuracy or camera
registration.

The next experiment is deliberately a held-out interpolation rather than another
fit. Both variants use the same lower conditioning target, then target a new
desired encoder endpoint 2390/1725 from a lower-side start expected near
2385/1731:

| Variant | Terminal command | Frozen predicted endpoint |
|---|---:|---:|
| Candidate | 2388/1726 | 2390/1725 |
| Control | 2389/1725 | 2391/1724 |

Native simulation rejected the original three-leg ordering before hardware: the
control predecessor is already within one count of the proposed initial upper
target, so that redundant command correctly produced `NO_CLEAR_RESPONSE`. The
current plan removes that leg. Each variant is now exactly two writes—lower
conditioning, then its terminal target—which preserves the matched terminal
history and avoids manufacturing motion merely to satisfy the classifier.

The command pair remains inside the observed 2377–2389 primary-register interval,
but interpolation is still not validation. Candidate and control require separate
campaign admissions and matched starts within one count per selected joint. There
is no retry or automatic return. Before physical execution, reacquire the current
pose and reconfirm that the fixed three-target sequence is compatible with the
actual arm state and clearance; historical r43 positions are not treated as live.

Implementation now includes `consolidate_bidirectional_pair_evidence.py`, the
pure `heldout_pair_validation` designer, `plan_heldout_pair_validation.py`, and
tamper/fixed-plan tests. Native held-out candidate/control selectors, preparation
guards, matched-start gates and host runner configurations are implemented. The
candidate and control both complete in native HTTP-relay simulation with exact
frozen endpoints; 15 focused native/runner/plan tests passed after the sequencing
correction. Next: stage and review the exact r44/r45 candidates around the current
two-leg export. Do not change its
targets after results are observed, and do not refit until the held-out comparison
is complete.

### r44/r45 held-out implementation — compiled and reviewed offline

The corrected two-leg plan now has distinct immutable candidate builds:

| Revision | Variant | Stage export | Compile export | Review export | App SHA-256 |
|---|---|---|---|---|---|
| r44 | held-out candidate | `wizard-20260920T200444850264Z-de8ff4369a1b4954998eefeb9e9ca2d8` | `wizard-20260920T200650505840Z-9d0d5414fe8e47e4a314383fa8c78600` | `wizard-20260920T201138154080Z-45b1e4acd6c1447eb5e11b7db94862db` | `f1910697b4653c941974e9dc9939357ccfe7a7016c526285465decdea2614d7d` |
| r45 | held-out control | `wizard-20260920T200445717730Z-b0271580c4c44b25a378fe72aacbea0b` | `wizard-20260920T201042691995Z-036c2707f7d545d88005052251cb7ceb` | `wizard-20260920T201139668664Z-ef44c6bcac254e6bb907258b3b923cf2` | `3b9e5930b9818ee4c4425541f6100d8dc22320eadd883f9d4391ff8499487af6` |

Each application is 1,157,616 bytes with 153,104 bytes of slot headroom. Static
review found only the three reviewed diagnostic headers plus the compile-time
selector changed from the pinned r40 source basis. The binaries retain the fixed
campaign excursion and baseline-admission guards, authenticated evidence routes,
and no generic target surface.

Installer, installation-evidence, startup-observation and retained-startup review
profiles now support the exact r43→r44→r45 predecessor chain. A local r44 deployment
preflight verified the exact application, current r43 predecessor, preserved
filesystem hash and unused one-use journal without opening hardware. The expanded
focused suite passed 268 installer/evidence/startup/runner tests. No firmware was
installed and no movement was sent in this phase.

Next live boundary: one explicitly authorized r44 app-only installation and one
startup, then read-only current-state reacquisition. Only if the installed r43
predecessor and fresh pose match should the fixed two-write candidate campaign be
considered. r45 remains offline until the r44 terminal export is complete and
verified; do not batch both installations or campaigns.

### r44 installation and fresh-state reacquisition — complete, no movement

r44 was installed once, app-only, from the exact r43 predecessor. Full application
readback matched the reviewed r44 SHA-256 and the protected regions were unchanged.
The one approved startup produced boot `478613f9f0684dad68e20b58489d3995`;
read-only startup checks observed the expected `hold-first-pair-v1` protocol in
`IDLE / NOT_CONFIGURED` with no storage fault.

- Installation evidence:
  `wizard-20260920T202201905008Z-44ac2b441f1f4a2b97113ae4a8cf1f71`.
- Startup observation:
  `wizard-20260920T202202353163Z-3449c8f86f1b456590461868cce28e41`.
- Pose assessment:
  `wizard-20260920T202252633670Z-ae1f2692abcc4b8caebb09670efaefae`.
- Final pose-capture receipt:
  `wizard-20260920T202252687106Z-082bd389afd74a6582773e7891eb9e44`.

The one-use read-only pose acquisition completed three snapshots and recorded zero
actions. All seven servo positions had zero span, torque state was unchanged, and
the current shoulder pair matches the immutable r44 admission reference:

| Servo | Goal | Sampled position | Required r44 reference | Result |
|---|---:|---:|---:|---|
| 12 | 2386 | 2388 | goal 2386, position 2388 +/- 1 | PASS |
| 13 | 1728 | 1727 | goal 1728, position 1727 +/- 1 | PASS |

The neighboring joints were also stationary across all three samples. The capture
therefore establishes a stable, device-read initial encoder state and satisfies the
fixed candidate campaign's current-state gate. It does not establish Cartesian or
stylus-tip accuracy. All installation, startup, transport, intermediate capture,
assessment and final capture bundles passed independent manifest verification.
The focused evidence/held-out/pose suite passed 11 tests after adding r44 pose
observation support.

No movement, hold, torque change, settings change, provisioning, retry or automatic
return was sent during this phase. The next live boundary is one separately
authorized fixed r44 candidate campaign with exactly two writes: lower conditioning
`2377/1737`, then terminal candidate `2388/1726`. Each leg must export and verify
before continuation; there is no retry or automatic return. r45 remains offline
until the complete r44 terminal evidence is retained and reviewed.

### First r44 campaign attempt — safely rejected before movement

The first authorized r44 campaign attempt produced the verified inconclusive export
`wizard-20260920T203125078225Z-513900ef40104d7ab2e06fde21d52965`.
The authenticated initial status was `NEW` with `writes_attempted: 0`; preparation
then returned an authenticated rejection. The host recorded
`start_attempted: false`, did not retry, and did not send either fixed target.

Investigation identified a deterministic lifecycle conflict: the preceding explicit
pose observation sets `rocellPoseReserved` and `rocellDiagnosticOwned`, both of which
are intentionally retained for the entire boot. Characterization preparation must
reject that boot because it cannot acquire exclusive bus ownership. This is not an
arm, endpoint, authentication or compensation failure, and it yielded no physical
movement.

The live preflight now detects a same-boot pose-observation claim and rejects it
locally before connecting. A regression test covers the conflict. The corrected
workflow is: separately authorize one startup of the already-installed r44 image,
perform ordinary read-only startup health checks that do not reserve the pose owner,
then run the fixed campaign. Characterization preparation itself acquires three
fresh stationary snapshots and the host verifies their exact goals, positions,
neighbor stability and immutable manifest before it signs start authorization.
Therefore, no separate pose-observation capture should precede a characterization
campaign on the same boot.

### r44 held-out candidate — executed successfully

One reviewed startup of the already-installed r44 image cleared the prior pose
reservation without flashing, provisioning, changing settings or sending a servo
command. The old boot was `478613f9f0684dad68e20b58489d3995`; the new healthy
boot is `7b98be62802cf78698ca589b686e7fa7`.

- Startup-reset evidence:
  `wizard-20260920T203545798591Z-3114f0fd78d541599f38db22ff0d9288`.
- New-boot observation:
  `wizard-20260920T203608454919Z-ef031ea1f5514643ab4dcf7a0517ef4d`.
- Frozen prediction export:
  `wizard-20260920T203617851602Z-ccbd62699f2d4e3c8a4d8e485aab9d04`.
- Fresh campaign reference:
  `wizard-20260920T203617894131Z-95dd4d85bd194cc0b6c2bd791014b1a0`.
- Lower-conditioning result:
  `wizard-20260920T203620633831Z-123d4c749ad141fca9d5d4782e06a951`.
- Terminal-candidate result:
  `wizard-20260920T203621809574Z-bea4f6c3061f4129b857e85f51b206be`.
- Complete campaign:
  `wizard-20260920T203621971640Z-4202a8a53af24a118d58557b934c8000`.
- Terminal audit:
  `wizard-20260920T203622022896Z-7f7eaa45c6f649a581c0cf9f85033b3d`.

The campaign's own fresh three-snapshot capture reproduced the admitted state at
shoulder position 2388/1727 with goals 2386/1728. It then completed the immutable
two-write manifest without retry or automatic return:

| Leg | Written targets | Measured endpoint | Outcome |
|---|---:|---:|---|
| Lower conditioning | 2377/1737 | 2386/1730 | SETTLED_MISS |
| Held-out candidate | 2388/1726 | 2389/1725 | SETTLED_ACCURATE |

The terminal desired endpoint was 2390/1725, so held-out signed error was -1/0,
maximum absolute encoder error was one count, and the terminal measurement is
usable. The frozen stateful-band model predicted 2390/1725; observed residual from
that prediction was therefore -1/0. This is positive held-out evidence for the
local paired-shoulder compensation, but `general_compensation_validated` remains
false: no Cartesian, stylus-tip, keyboard or workspace-wide accuracy is claimed.

The startup, both leg results, complete run and terminal-audit bundles pass
independent integrity verification. No commands were sent after the terminal
candidate. Next: review this retained candidate result, then—under separate
authorization—install r45 from the exact r44 predecessor, start it once, and run
the predeclared held-out control campaign from this terminal state. Only the
candidate/control comparison may decide whether this interpolation improves on
the uncompensated command.

### r45 held-out control and comparison — executed successfully

r45 was installed once, app-only, from the exact r44 predecessor. Full readback
matched reviewed application SHA-256
`3b9e5930b9818ee4c4425541f6100d8dc22320eadd883f9d4391ff8499487af6`,
protected regions were unchanged, and one startup produced healthy boot
`ac14cee71eb73a7dad4a2ba4ab181fb0`.

- Installation evidence:
  `wizard-20260920T204115683207Z-2e18a9e42d004cb7a86a97777b439a41`.
- Startup observation:
  `wizard-20260920T204116045015Z-30ffacefe8d8452f96e9d6cb97e293b8`.
- Lower-conditioning result:
  `wizard-20260920T204127657383Z-a9f27fc37e8944bea19295f49968923a`.
- Terminal-control result:
  `wizard-20260920T204128844913Z-0ba337ce1b664439a23d063dc29e0c4f`.
- Complete campaign:
  `wizard-20260920T204129061313Z-d45979e9effa4276b6498ea7110848f8`.
- Terminal audit:
  `wizard-20260920T204129113355Z-11ae97a35adf44ce9f60b5b92a39069f`.
- Candidate/control comparison:
  `wizard-20260920T204230041822Z-da2831b91d6c496f8fd9f7a5b608aa58`.

The control completed its fixed two writes without retry or automatic return:

| Leg | Written targets | Measured endpoint | Outcome |
|---|---:|---:|---|
| Lower conditioning | 2377/1737 | 2385/1730 | SETTLED_MISS |
| Held-out control | 2389/1725 | 2390/1724 | SETTLED_ACCURATE |

The candidate and control terminal starts, 2386/1730 and 2385/1730, match within
one count. Against the common held-out desired endpoint 2390/1725:

| Variant | Command | Actual | Signed error | Max abs | L1 | Squared |
|---|---:|---:|---:|---:|---:|---:|
| Candidate | 2388/1726 | 2389/1725 | -1/0 | 1 | 1 | 1 |
| Control | 2389/1725 | 2390/1724 | 0/-1 | 1 | 1 | 1 |

The comparison is eligible and all primary encoder-error metrics tie. Therefore,
this held-out interpolation does not demonstrate that the candidate improves on
the uncompensated command, but it also does not show a regression: both landed
within one encoder count of the desired pair. The correct decision is to retain
the evidence, keep the model frozen, and avoid claiming a winner or refitting from
this tied pair. `general_compensation_validated` remains false.

`compare_heldout_validation.py` independently reopens both audits, raw leg records,
complete run manifests and frozen predictions before exporting the comparison.
All r45 installation/startup/leg/run/audit bundles and the comparison bundle pass
integrity verification. No commands were sent after the terminal control.

### r46/r47 second held-out comparison — frozen and reviewed offline

The first held-out pair tied at one encoder count, so it was not discriminating
enough to select compensation. The model remains unchanged. A second endpoint was
selected in the reverse direction using only the already-frozen model and retained
evidence; no r44/r45 result was used to refit parameters.

- desired measured endpoint: `2387/1729`
- r46 candidate command: `2378/1736`
- r47 direct control command: `2386/1728`
- frozen candidate prediction: `2387.667/1729` (error `+0.667/0`)
- frozen control prediction: error `+3/-5`
- common terminal approach: lower `2377/1737`, then upper `2389/1725`

The r46 manifest is lower → upper → candidate. The r47 manifest is upper → lower
→ upper → control. r47 has one extra setup write because its predecessor will be
the candidate goal `2378/1736`; beginning directly with lower `2377/1737` would be
a one-count near-zero command and would correctly fail the response policy. The
extra leg does not change the immediate lower-to-upper history before either
terminal comparison.

Offline artifacts are immutable and independently verified:

| Revision | Variant | Stage export | Compile export | Review export | App SHA-256 |
|---|---|---|---|---|---|
| r46 | second held-out candidate | `wizard-20260920T205020058080Z-2867ea2dd2454dd494122ab5458211ae` | `wizard-20260920T205253317663Z-77f70298282a44589de7c2beee464e9f` | `wizard-20260920T205529221817Z-b2496f89ae384f439878d7a7d3ee09dc` | `1b205cffb023761f228be728a8caee9de0e13b17751d4bec28b6ba5584c83d87` |
| r47 | second held-out control | `wizard-20260920T205020895579Z-b591b63515de4063a8d2c19d8d7128da` | `wizard-20260920T205446973251Z-8976b7d26d31403f9a40f3c8c5818e35` | `wizard-20260920T205530940952Z-6c8e518625804964838aea735d71e768` | `a2101ea8ec27b7f9c93063b3e5dea91546b91b2edfbca63b3cc5e71f3f7cee1e` |

The frozen plan export is
`wizard-20260920T205018907434Z-55fca8d673974a429423f6606f6be19e`.
Both applications are 1,157,936 bytes with 152,784 bytes of slot headroom. Native
HTTP-relay simulation completes both authenticated campaigns and produces terminal
errors of `0/+1` for candidate versus `+1/-2` for control. This simulation confirms
sequencing, gates, receipts and exports; it does not predict the physical result.

Host deployment profiles now bind the exact r45→r46→r47 predecessor chain and
pass local preflight without opening hardware. The focused plan, runner and
deployment suite passes 50 tests. No firmware was installed and no movement was
sent in this phase.

Next live boundary: separately authorize one r46 app-only installation and one
startup, then run only the fixed three-write r46 campaign. r47 must remain offline
until r46 completes and its terminal evidence is verified. After a separate r47
installation/startup and fixed four-write control campaign, compare the two retained
terminal endpoints without refitting the model. Stop either sequence on preparation,
matched-start, feedback, export, or endpoint-validation failure; do not retry or
automatically return.

### r46 second held-out candidate — executed successfully

r46 was installed once, app-only, from the exact r45 predecessor. Full application
readback matched SHA-256
`1b205cffb023761f228be728a8caee9de0e13b17751d4bec28b6ba5584c83d87`,
protected regions were unchanged, and the approved startup produced healthy boot
`b3bd6fa66833d62707c926bcb552fbe9`.

- Installation evidence:
  `wizard-20260920T211035108777Z-1b1d1515fdff42799488e24903f96b71`.
- Startup observation:
  `wizard-20260920T211035525714Z-e007573adb8a4b98bb90511c93584ed0`.
- Frozen prediction export:
  `wizard-20260920T211121824279Z-00af35574902484f91d5dad0c19ed039`.
- Fresh campaign reference:
  `wizard-20260920T211121864965Z-6a65b6e60815437392ad04c87509798e`.
- Lower result:
  `wizard-20260920T211123286939Z-7a88467754584098ba9d5ce83529130c`.
- Upper result:
  `wizard-20260920T211124478986Z-6dea3bf77b3742ff81ff503d9a5c5fb3`.
- Terminal candidate result:
  `wizard-20260920T211125818978Z-1331480019984904a823c89181ddd2d0`.
- Complete campaign:
  `wizard-20260920T211125944760Z-360a5c07dd164d418143b60f22c2c626`.
- Terminal audit:
  `wizard-20260920T211126005982Z-3df6c381baf34322a51b2a912a2fb02e`.

The campaign used exactly three writes with no retry or automatic return:

| Leg | Written targets | Measured endpoint | Outcome |
|---|---:|---:|---|
| Lower conditioning | 2377/1737 | 2385/1730 | SETTLED_MISS |
| Upper conditioning | 2389/1725 | 2391/1724 | SETTLED_ACCURATE |
| Second held-out candidate | 2378/1736 | 2387/1730 | SETTLED_MISS |

The terminal measurement is usable. Against desired `2387/1729`, signed error is
`0/+1`, maximum absolute error is one encoder count. This matches the offline
simulation's maximum error and is close to the frozen prediction
`2387.667/1729`; it is not yet evidence of improvement because the predeclared
r47 control remains unmeasured. All installation, startup, leg, run and audit
bundles verify. `general_compensation_validated` remains false.

One host-only omission was found before movement: the startup evidence reader's
revision allowlist ended at r45. The first campaign invocation stopped locally
before claim creation or device contact. r46/r47 were added to that exact read-only
binding, 260 related tests passed, and the unused boot then ran the authorized
campaign. This did not require another startup, movement retry, or firmware change.

Next live boundary: one separately authorized r47 app-only installation and one
startup from the exact r46 predecessor, followed by its fixed four-write control
campaign: upper setup → lower → upper → direct control `2386/1728`. There is no
retry or automatic return. Only after its terminal export verifies may the r46/r47
comparison select or reject compensation for this local reverse-direction case.

### r47 control and second held-out comparison — retained no-response evidence

r47 was installed once, app-only, from the exact r46 predecessor. Full readback
matched SHA-256
`a2101ea8ec27b7f9c93063b3e5dea91546b91b2edfbca63b3cc5e71f3f7cee1e`,
protected regions were unchanged, and startup produced healthy boot
`6d8c896ae6eb84d1ae59cd9549e03cfc`.

- Installation evidence:
  `wizard-20260920T211629295545Z-28928bff24d44624b981826a7929940a`.
- Startup observation:
  `wizard-20260920T211629572437Z-09291aa720c3439eb3d103f0a1ebce01`.
- Upper setup result:
  `wizard-20260920T211638133294Z-1d4d3e446b0a477ba588155d75983a4f`.
- Lower result:
  `wizard-20260920T211639379325Z-735656999ff74e678cc7466d483fb534`.
- Repeated upper result:
  `wizard-20260920T211640839070Z-6fcbad6d08fc4e0d86af7db2c82a4794`.
- Terminal fault:
  `wizard-20260920T211643524259Z-def6596d936e4da6a59a0814d42e000a`.
- Retained terminal control record:
  `wizard-20260920T211643798234Z-2888cd4e55f44593b37140edd924edf6`.
- Inconclusive campaign envelope:
  `wizard-20260920T211643858519Z-dbdc7b5902f642b19216186f196eece9`.
- Terminal audit:
  `wizard-20260920T211643928410Z-a9130e99a4254a56be185603c4dd6d25`.
- r46/r47 comparison:
  `wizard-20260920T211756163014Z-475119d6344843309d3d757d35f9e1da`.

The first three conditioning writes completed and the repeated upper endpoint was
exactly the required terminal start `2391/1724`. The fourth target `2386/1728` was
written once, but fresh feedback remained `2391/1724` for the complete two-second
observation window. The controller stopped with `NO_CLEAR_RESPONSE`; it did not
retry, return, or issue a fifth command. The retained terminal record is usable as
the measured outcome of the direct-control write, although the campaign envelope
is correctly `INCONCLUSIVE` rather than `COMPLETE`.

The candidate and control terminal starts are identical. Against desired
`2387/1729`:

| Variant | Command | Actual | Signed error | Max abs | L1 | Squared |
|---|---:|---:|---:|---:|---:|---:|
| r46 compensated candidate | 2378/1736 | 2387/1730 | 0/+1 | 1 | 1 | 1 |
| r47 direct control | 2386/1728 | 2391/1724 | +4/-5 | 5 | 9 | 41 |

`compare_second_heldout_validation.py` independently reopens the raw terminal
records, audits, campaign manifests and frozen predictions. The comparison is
eligible and supports the frozen compensation for this local reverse-direction
case: the candidate improves maximum absolute, L1 and squared encoder error. This
also demonstrates a practical reason for compensation—the direct command fell
inside the pair's effective deadband/hysteresis from this approach state.

This is still local encoder-space evidence. It does not establish Cartesian,
keyboard, stylus-tip, phone-screen or workspace-wide accuracy, and
`general_compensation_validated` remains false. All r47 and comparison bundles
verify successfully. No movement was sent after the retained no-response control.

### Evidence-bound local compensation policy

The successful comparison is now represented by
`local_pair_compensation_policy.py`, not by changing or refitting the frozen model.
Policy export
`wizard-20260920T212044333082Z-86fe03dcc6c04fffaba007b50569fce5`
binds the exact comparison digest, r46 manifest and frozen model identity.

The resolver applies only when all of these are true:

- current shoulder goals are exactly `2389/1725`;
- fresh shoulder positions are within one count of `2391/1724`;
- requested measured endpoint is exactly `2387/1729`;
- the retained r46/r47 comparison remains unchanged.

Only then does it resolve command `2378/1736`, with observed expected endpoint
`2387/1730`. Any other goal, stale position, nearby desired endpoint, altered
comparison, extrapolation or general-purpose request is rejected. The policy has
no transport or motion API, grants no movement authority, and retains explicit
false values for Cartesian, stylus and general compensation validation. Fifteen
focused policy, held-out-plan and native-runner tests pass. No hardware access or
movement occurred during policy promotion.
## r48 batched local-pair mapping campaign (prepared offline)

The next physical campaign is intentionally a single fixed batch rather than another
firmware-edit/test loop for every endpoint. It samples the local shoulder-pair response
over both command directions and repeats the lower and upper anchors so repeatability
and approach-history effects can be compared from one run.

The exact primary-register route is:

`2377, 2389, 2379, 2387, 2381, 2389, 2377, 2385, 2389, 2383, 2377, 2388`

The paired register is always `4114 - primary`. Consecutive primary changes are between
4 and 12 counts, and every target remains inside the previously exercised 2377–2389
range and the controller's 32-count measured-anchor envelope. The start gate requires
goals `[2386, 1728]` and fresh measured positions `[2391, 1724]` within one count.

The firmware and host both recognize this exact route. This is not an arbitrary target
surface. Each leg uses one write, three fresh baselines, bounded observations, durable
per-leg export, and an export receipt before progression. One non-consecutive settled
small response may be retained as deadband evidence; it is not labeled as accurate
arrival. Any second consecutive small response or other invalid result stops the batch.

Host output records the command, approach direction, measured start, measured endpoint,
target residual, and repeated-anchor endpoints. The consolidated result explicitly does
not fit or promote a general compensation model; model selection happens only after the
batch is complete and its evidence is reviewed.

Offline evidence:

- Frozen plan: `wizard-20260920T212829382977Z-6d68c808f1f34e80913e35317c558ae3`
- r48 staged source: `wizard-20260920T213026961987Z-975f0b4f144348cbbfddcf739226c900`
- r48 compile: `wizard-20260920T213222876827Z-02a4a76763f648af84d117d20565d499`
- r48 offline review: `wizard-20260920T213308029747Z-8b3fbead82f44e5c84eeafa41c6a1843`
- r48 app SHA-256: `e76470e40216c39dd6ebc57df3e665c50fa6436da680bbeea0b18c599deddc1b`

No r48 installation, startup, device contact, or physical movement has occurred. The
next live boundary is one separately authorized r48 app-only installation and startup,
followed by a fresh read-only gate check before the fixed batch is released.

### r48 installation and read-only gate result

r48 was subsequently installed app-only with full readback verification. The application
SHA-256 matched `e76470e40216c39dd6ebc57df3e665c50fa6436da680bbeea0b18c599deddc1b`,
and protected flash regions were unchanged. The single startup produced boot
`1267226364559923c0513aebe878ed04` and a stable idle diagnostic interface.

The authenticated read-only preparation captured goals `[2386, 1728]` and measured
positions `[2391, 1724]`; therefore the exact r48 starting gate passed. No target command,
receipt, torque change, or movement was sent. This preparation intentionally consumed the
boot's one-use campaign reservation. A physical mapping run requires one new separately
authorized startup before its 12 commands may be released.

- Installation evidence: `wizard-20260920T214253809908Z-d7e235838d6b4a8b9d7b152923d1d03d`
- Startup evidence: `wizard-20260920T214254144031Z-4d7e344ed1764354aa59abdf65df71e5`
- Read-only gate evidence: `wizard-20260920T214345123904Z-2b67d1ad4edb48c0a7e84b70a414f911`
- Raw reference export: `wizard-20260920T214345060925Z-bf8436a4951042809c310967157bc493`

### First r48 mapping run

A fresh idle boot passed the same starting gate, and the fixed batch began. The controller
issued five writes and then stopped without retry on two consecutive small responses.
This is useful deadband/plateau evidence rather than a transport or hardware-delivery
failure:

| Leg | Command | Measured before | Measured endpoint | Classification |
| --- | --- | --- | --- | --- |
| 0 | `[2377, 1737]` | `[2391, 1724]` | `[2385, 1731]` | settled miss |
| 1 | `[2389, 1725]` | `[2385, 1731]` | `[2391, 1724]` | settled accurate |
| 2 | `[2379, 1735]` | `[2391, 1724]` | `[2387, 1728]` | settled miss |
| 3 | `[2387, 1727]` | `[2387, 1728]` | `[2387, 1727]` | retained small response |
| 4 | `[2381, 1733]` | `[2387, 1727]` | `[2387, 1728]` | stop: no clear response |

The observed primary encoder endpoints span 2385–2391. In particular, commands 2379,
2387, and 2381 all terminate near primary position 2387 from the tested histories. This
supports a local plateau/deadband hypothesis but does not yet justify a fitted general
compensation model. No sixth command was sent.

- Fresh startup: `wizard-20260920T214557062482Z-a1a85c49a31f4f70bd1c2f66e08fafa2`
- Campaign run: `wizard-20260920T214624078252Z-4b5f726dbec1411c8658ccc52f1f0682`
- Verified partial map: `wizard-20260920T214732246917Z-16d2099d2e1747f5bc0d6082c99501bf`

Next, revise the batch ordering so informative larger transitions separate plateau probes.
That preserves the one-consecutive-small rule while allowing the remaining endpoints to
be sampled in one campaign. Do not weaken the controller stop rule based on this run.

## r49 separated-probe mapping campaign (offline-qualified)

r49 keeps the r48 stop policy unchanged and changes only the frozen route ordering. Each
uncertain plateau target is separated from the next by a larger upper/lower transition,
so the campaign does not intentionally place two likely small responses back-to-back.
It starts from the retained r48 terminal state: goals `[2381, 1733]` and measured
positions `[2387, 1728]` within one count.

The exact primary-register route is:

`2389, 2377, 2385, 2389, 2383, 2377, 2388, 2377, 2381, 2389, 2377, 2387`

The paired register remains `4114 - primary`. Every consecutive primary step is 4–12
counts; the first is +8 counts from the retained goal. The controller still permits at
most one consecutive settled-small response, performs one write per leg, requires a
durable export receipt before progression, performs no automatic retry, and stops on
the next uncertain response. Host execution accepts only this exact manifest and the
exact retained start gate.

Offline evidence:

- Frozen plan: `wizard-20260920T220134625656Z-27b9c57f0b09480fb16b21b26818ea03`
- Staged source: `wizard-20260920T220241067011Z-6142af43a408432792d1919e4828d2f0`
- Compile: `wizard-20260920T220450539161Z-281bba4e5ff94c94a14e4ebfd733d2ef`
- Offline candidate review: `wizard-20260920T220532774591Z-a2b11b514039439f88d74896432fabb9`
- App SHA-256: `e4b331623527aa94078e514f8cd37e18ac00a04bf543b9005072ff677a42c21f`
- App bytes: `1,158,528`; slot headroom: `152,192` bytes.
- Focused host/native/deployment tests: 358 passed.
- Installer preflight: locally verified against exact r48 predecessor, preserved
  filesystem image, reviewed binary, and unused r49 journal; no hardware access.

The full 12-leg path completes in native simulation, including authenticated admission,
per-leg record transfer, independent host assessment, durable exports, signed receipts,
and final completion. This proves the command/export workflow, not physical arrivals.
The next live boundary is one app-only r49 installation and one startup preserving
settings and credentials, followed first by read-only idle/start-state checks. The fixed
campaign may run only after that gate verifies; there is no retry or automatic return.

### r49 installation and read-only start gate

r49 was installed app-only from the exact r48 predecessor. Full application readback
matched `e4b331623527aa94078e514f8cd37e18ac00a04bf543b9005072ff677a42c21f`,
and both protected flash regions were unchanged. Exactly one startup reset was sent.
The resulting boot `a8bb3982465d69c1c3801f381bf8204b` was stably idle with preserved
pair capabilities and no storage fault.

Authenticated read-only preparation then captured three fresh, stable poses. All three
reported shoulder-pair goals `[2381, 1733]` and positions `[2387, 1728]`; therefore the
exact r49 start gate passed. The challenge carried the exact frozen 12-leg manifest.
No target, receipt, torque command, or movement was sent. Preparation consumed this
boot's one-use campaign reservation, so it cannot be reused for movement.

- Installation evidence: `wizard-20260920T222828831388Z-a5a9371f5fde46babebd7ae34e11d528`
- Startup evidence: `wizard-20260920T222829140320Z-643dd3ca848a44f1bcdb2976edbc3d3c`
- Read-only gate: `wizard-20260920T222917561443Z-39072f9573144939ac9add0b18a128c1`
- Raw reference: `wizard-20260920T222917513576Z-9cc4ad36bdad46019bb99569c282d6e9`

The next physical boundary is one fresh startup of the already installed r49 image,
followed by the exact fixed campaign. That startup must produce a new idle boot; the
runner must independently revalidate the same start state before signing and releasing
the first command. No automatic retry or return is allowed.

### r49 physical campaign and combined map

A fresh startup produced idle boot `37d15b06b5ae6bc6e8258f255eee423d`.
The one-use runner rebound that boot to the frozen plan, revalidated the exact start
state, and completed all 12 writes. Every leg was exported and independently assessed
before its signed receipt released the next leg. There was no fault, retry, automatic
return, or unplanned command.

- Fresh startup: `wizard-20260920T224532579954Z-6370cf3edb6b49f29387af1fb93349e5`
- Complete campaign: `wizard-20260920T224608495302Z-7205b82ca3d8417cacf97c327a0dd9fb`
- Consolidated r49 map: `wizard-20260920T224608597099Z-151dafd0c1d547a9bc323d28db5cc550`
- Combined r48/r49 analysis: `wizard-20260920T224719566536Z-5f0101935604437bb92e275c339b5664`

The combined 17-write evidence supports repeatable local hysteresis/plateaus:

- command `2389` produced primary endpoint `2391` in 4/4 samples;
- command `2377` produced primary endpoint `2385–2386` in 5/5 samples;
- decreasing approaches had primary command residuals of +6 to +9 counts, mean +8.125;
- increasing approaches had residuals of 0 to +5 counts, mean +2.0;
- multiple distinct commands terminated on the same measured plateaus at 2386, 2387,
  2389, and 2391.

This makes random delivery failure an unsupported explanation for the earlier misses.
The dominant local effect is direction/history-dependent response with a deadband-like
plateau. The analysis intentionally fits and promotes no general model. These are
encoder-space measurements only; they do not establish Cartesian or stylus-tip accuracy.
The next software step is a held-out lookup/policy proposal that uses approach direction
and measured start plateau, followed by simulation and a separately bounded physical
validation before the policy can control typing trajectories.

### Cross-session plateau policy and r50 fine-endpoint plan

The anchor-navigation policy was trained only on r49 and tested against untouched r48
anchor transitions. The r48 lower transition fell within the learned primary range and
one count outside the learned paired-register range; the upper transition matched
exactly. Maximum held-out error was one count. Policy export
`wizard-20260920T225030977676Z-49605b8c62e2470bb558a7bf8d0e5a5e` therefore validates
only two conditioning actions: upper plateau to lower via `2377/1737`, and lower plateau
to upper via `2389/1725`. Resolution requires fresh feedback inside the measured start
plateau and grants no movement authority. Fine endpoint lookup remains false.

Two r49 observations are promising but still require repetition:

- from the lower plateau, `2385/1729` reached desired `2387/1727` exactly, while the
  retained direct command reached `2389/1726`;
- from the lower plateau, `2388/1726` reached desired `2389/1725` exactly, while the
  retained direct command reached `2391/1724`.

The frozen r50 plan repeats both candidates from a validated lower conditioning plateau,
with an upper/lower transition between every sample. It contains 12 fixed writes, one
write per leg, no retry, and no automatic return. Both held-out repeats must finish
within one count and improve on their retained direct controls before a fine lookup may
be proposed. The plan is exported as
`wizard-20260920T225134995939Z-bb6fae52d11a4f168f7d09a627e31165`.

r50 is now fully qualified offline as a fixed diagnostic candidate. The implementation
binds the exact 12-leg route and retained start gate in both firmware and host code;
the native composition test completes the entire authenticated command, feedback,
assessment, durable-export, and signed-receipt sequence. Deployment metadata preserves
the reviewed filesystem/settings image and requires r49 as the exact predecessor.

- Frozen plan: `wizard-20260920T225134995939Z-bb6fae52d11a4f168f7d09a627e31165`
- Staged source: `wizard-20260921T015949337205Z-27ab9c72b76f43a499d52be980b489c3`
- Compile: `wizard-20260921T020149348463Z-cabf450e3bc44b66af61f58e5f77cb6d`
- Offline candidate review: `wizard-20260921T020230782394Z-2434980751944f1698896e49d76415a9`
- App SHA-256: `0dda0988222a1de534a5d72de1f528f6ae42fed5be0215fed8fbd75129e6121b`
- App bytes: `1,158,736`; slot headroom: `151,984` bytes.
- Focused firmware/host/deployment/observer tests: 367 passed.
- Installer preflight: locally verified against the exact r49 predecessor and preserved
  filesystem image; hardware access false and deployment authorization false.

The read-only observer now recognizes revision 50, verifies the exact frozen manifest,
exports the authenticated raw joint reference, and requires shoulder-pair goals
`[2387,1727]` with positions `[2389,1726]` within one count. It cannot send a target.

At offline qualification, no r50 installation, startup, target write, or physical
movement had occurred. The required live sequence was app-only installation, one
startup, and read-only idle/start-gate verification before any campaign. Read-only
preparation consumes its boot's one-use reservation, so movement requires a later fresh
startup. There is no automatic retry or automatic return.

### r50 installation and read-only start gate

r50 was installed app-only from the exact r49 predecessor. Full application verification
matched `0dda0988222a1de534a5d72de1f528f6ae42fed5be0215fed8fbd75129e6121b`,
and the protected filesystem/settings regions were unchanged. Exactly one startup reset
was sent. Boot `c9250ccdca21fc8b897f14aac2f4797e` was stably idle with the expected
pair protocol and no storage fault.

Authenticated read-only preparation captured three stable poses. All three reported
shoulder-pair goals `[2387,1727]` and measured positions `[2389,1726]`, so the exact r50
start gate passed. The challenge contained the frozen 12-leg manifest. No target,
receipt, torque command, or movement was sent.

- Installation evidence: `wizard-20260921T021429235273Z-de41344015914dacbc17ef6c7858fd32`
- Startup evidence: `wizard-20260921T021429477726Z-06443c0f8cd74372b3deb18639daec7e`
- Raw reference: `wizard-20260921T021437145384Z-d2ca458bd3fb45b18849dd472dff3ce0`
- Read-only gate: `wizard-20260921T021437193869Z-ee26363d1cd541f4870921630061dc62`

Preparation consumed this boot's one-use reservation. The next physical boundary is one
fresh startup of the installed r50 image followed by the exact fixed 12-leg campaign.
The runner must independently revalidate the same start pose before the first write.

### r50 physical fine-endpoint validation

A fresh startup produced idle boot `2efc984fc28c732b64e89be9fafaa026`. The first
campaign invocation stopped locally before hardware access because the reset observation
was not the full startup attachment required by the runner. A full read-only startup
observation then bound the same untouched boot; the one-use campaign claim remained
unused. The exact 12-leg campaign subsequently completed with one write per leg, durable
evidence before each receipt, no retry, and no unplanned return.

- Pre-reset observation: `wizard-20260921T021611903356Z-cf44753a93414d569fe3d2eee0de553a`
- Fresh-boot observation: `wizard-20260921T021617446731Z-43240410e5c64ff986e031555c32599b`
- Full startup binding: `wizard-20260921T021642967095Z-cc3eae8cda224c79bf7d18bc8d946117`
- Complete physical campaign: `wizard-20260921T021709821652Z-54c9bb4eb15d4250b80e496cea3182e0`
- Consolidated r50 result: `wizard-20260921T021709908019Z-13859a6cdef3442c94e7c6720ef84742`
- Bounded lookup analysis: `wizard-20260921T021831649937Z-b061470e8d864fadba3664929977b836`

All repeated endpoints were identical within each command group:

- conditioning command `2377/1737` reached `2385/1730` in 4/4 samples;
- candidate `2385/1729` reached `2387/1728` in 2/2 samples, one count from the
  desired `2387/1727` and better than the retained direct result `2389/1726`;
- candidate `2388/1726` reached desired `2389/1725` exactly in 2/2 samples;
- upper command `2389/1725` reached `2391/1724` in 4/4 samples.

The frozen release rule therefore validates two local encoder endpoint lookups only:
`2385/1729 -> 2387/1728` and `2388/1726 -> 2389/1725`, when approached from the
validated lower plateau. It does not validate a general compensation model, Cartesian
accuracy, stylus-tip accuracy, or movement authority. These two bounded lookups were
therefore added to a local policy resolver that retains the required conditioning state
and fresh-feedback gate before any coordinated ghost-key trajectory may use them.

### Operational use and finite generalization gates

The two r50 corrections are now integrated into a bounded endpoint resolver and exported
as `wizard-20260921T025358135319Z-9e37a08d875249caac4601884359f7ed`.
It resolves only the two measured desired endpoints, only after fresh feedback confirms
the validated lower conditioning plateau. Unknown endpoints and stale/wrong approach
states fail closed. This is enough to use those two endpoints as controlled building
blocks now; they are no longer classified merely as experimental observations.

"Enough to generalize" is divided into finite releases so that the qualification target
cannot move indefinitely:

1. **Discrete local lookup — achieved.** Two repeated candidates, independent retained
   direct controls, identical held-out repeats, and no result worse than one encoder
   count. Only the two explicit lookups may be used.
2. **Local interval interpolation — next finite mapping campaign.** Measure at least
   five ordered endpoints spanning the intended local shoulder-pair interval, with at
   least three conditioned samples per endpoint across at least two startups. Reserve
   at least one sample per endpoint as held-out evidence. Release interpolation when
   endpoints remain monotonic, every held-out paired-register error is at most two
   counts, the 95th-percentile error is at most two counts, and no endpoint exceeds the
   direct-command error. This releases interpolation only inside the measured interval;
   extrapolation remains forbidden.
3. **Coordinated ghost-key motion.** Exercise the actual multi-joint approach, hover,
   press and retract path at a set of representative virtual key locations. Release the
   path planner when every joint has fresh feedback, every sequence completes without
   an unexplained stop, and repeat endpoints stay inside the encoder tolerance assigned
   by the local interval model.
4. **Task-space typing accuracy.** This requires the mounted stylus and workspace
   registration (camera or measured fixture). Only this phase can translate encoder
   repeatability into millimetres and demonstrate correct key or screen selection.

Accordingly, the project does not need a full-arm universal model before advancing.
It may use the validated discrete endpoints immediately, and it may generalize across
the local shoulder interval after the finite five-endpoint campaign spanning three
fresh startups passes. Claims beyond that measured interval remain intentionally unsupported.

### r51 local-interval campaign implementation

The finite generalization gate is now implemented as one reusable 11-write manifest run
on three fresh startups. This supplies three samples per endpoint while keeping every
session inside the controller's twelve-leg capacity. The measured commands are
`2377`, `2383`, `2385`, `2388`, and `2389`; upper/lower conditioning legs separate
nearby samples so the retained one-consecutive-small-response rule is not weakened.

Commands `2377`, `2385`, and `2389` are training anchors. Commands `2383` and `2388`
are excluded from the fit and score interpolation as truly held-out interior locations.
The model releases interpolation only if the training endpoints are strictly monotonic
and both maximum and 95th-percentile paired-register held-out errors are at most two
counts. Extrapolation remains forbidden.

- Frozen superseding plan: `wizard-20260921T030720711609Z-dd03b9b60955416198ea6897c13a1216`
- Staged r51 source: `wizard-20260921T030802212946Z-edc3704c0dc344d083c8e07b3c990ee6`
- Compile: `wizard-20260921T030956990516Z-bb60378cb348435a897d1f8b08083b78`
- Offline candidate review: `wizard-20260921T031043920855Z-da5c6305db944ba1a889bf28c6816e5a`
- App SHA-256: `0a45c55ace66374038c712672bee41b507a80e64a121b0a020b4836ce2bddc9e`
- App bytes: `1,158,992`; slot headroom: `151,728` bytes.
- Focused native/host/deployment tests: 369 passed.
- Installer preflight: exact r50 predecessor and protected filesystem image verified;
  hardware access false and deployment authorization false.

The host includes an exact r51 per-startup runner, a three-session analyzer, and a
read-only observer for the 11-leg manifest and start pose. At offline qualification,
no r51 installation, startup, or physical movement had occurred. The required live
boundary was app-only installation and read-only start-gate verification before session
1. Sessions 2 and 3 each require a separately observed fresh startup; no session retries
automatically.

### r51 installation and read-only start gate

r51 was installed app-only from the exact r50 predecessor. Full application verification
matched `0a45c55ace66374038c712672bee41b507a80e64a121b0a020b4836ce2bddc9e`,
and protected filesystem/settings regions were unchanged. Boot
`2c5399d7eb2d1afa911ed2a28e83cfaa` was stably idle with no storage fault.

Three authenticated read-only poses consistently reported goals `[2389,1725]` and
positions `[2391,1724]`; the exact 11-leg r51 manifest and start gate passed. No target,
receipt, torque command, or movement was sent.

- Installation: `wizard-20260921T033111126483Z-15de4c864c5e4179abbeb3fca8589c52`
- Startup: `wizard-20260921T033111485938Z-66c1deae4a3742c3a3e72b2fa74fb177`
- Read-only gate: `wizard-20260921T033119583526Z-6408599fe00445e0bd615cd754f38963`

Read-only preparation consumed this boot's one-use reservation. Session 1 therefore
requires one fresh startup, full startup observation, and independent revalidation of
the same start gate before its first of eleven writes.

### r51 physical session 1

Session 1 completed on fresh boot `d3fa0439fd86f0dc4a4f2113b7019bf6` with exactly
the frozen 11-write route. There was no retry, route substitution, settings change, or
automatic follow-on campaign. All eleven leg exports, the consolidated campaign export,
and the derived five-endpoint session result were written successfully. Their final
manifests are complete and every declared file size and SHA-256 digest reverified.

- Fresh-startup status before reset:
  `wizard-20260921T033242921281Z-5ffe74fb7a2e4ac18be489e79083b995`
- Fresh-startup status after reset:
  `wizard-20260921T033248452183Z-3d89cb3d48cc418fa06653b7c65e3d1b`
- Full startup observation:
  `wizard-20260921T033255046612Z-df92334f1f7e42019499a711d0e9bddf`
- Session-start evidence:
  `wizard-20260921T033305297888Z-e7853c592aae48c6b8267c6dac51d65d`
- Consolidated 11-leg campaign:
  `wizard-20260921T033324955513Z-5674056e46ad4f96a5eeaaff45055b5d`
- Derived session result:
  `wizard-20260921T033325043203Z-4ee1dfdca95249979a5221b7613a5f7d`

The five retained endpoint samples were:

| Commanded pair | Measured pair | Residual | Classification |
| --- | --- | --- | --- |
| `[2377,1737]` | `[2385,1731]` | `[8,-6]` | settled miss |
| `[2383,1731]` | `[2385,1731]` | `[2,0]` | settled small response |
| `[2385,1729]` | `[2387,1728]` | `[2,-1]` | settled small response |
| `[2388,1726]` | `[2389,1725]` | `[1,-1]` | settled accurate |
| `[2389,1725]` | `[2391,1724]` | `[2,-1]` | settled accurate |

Session 1 is not sufficient to fit or promote a model. It does provide an important
working hypothesis for the remaining frozen repeats: the upper portion of the interval
tracks within one or two counts, while the lower command may encounter a retained
plateau/backlash region and the immediately following six-count command may not create
a newly sampled displacement. That is an observation, not yet a correction rule.
Sessions 2 and 3 must repeat the unchanged manifest on separate fresh startups. Only
the predeclared analyzer may then decide whether monotonicity and held-out error gates
pass. If the lower plateau repeats and strict monotonicity fails, the correct outcome is
to reject interpolation across the full interval and define a smaller supported interval
or a separately evidenced conditioning strategy; the data must not be forced to fit.

### r51 physical session 2

Session 2 completed on independent fresh boot `0a83c1ec11adfa0b4ef9c0330d62e88b`.
The controller was observed idle before the frozen route began, and the startup itself
sent no movement. The session then completed exactly eleven writes without retry or
substitution. Both final manifests are complete; every declared file size and SHA-256
digest reverified.

- Fresh-startup status before reset:
  `wizard-20260921T033705055696Z-36e8708f726248fcb2f9037f333c74b2`
- Fresh-startup status after reset:
  `wizard-20260921T033710613878Z-60018b7e6ea9495584baa372af33c7f8`
- Full startup observation:
  `wizard-20260921T033716482408Z-4cbdb88483514864b6ee4fef7e11642e`
- Consolidated 11-leg campaign:
  `wizard-20260921T033743384505Z-477904176f4842d8b5080b9f7aa076e3`
- Derived session result:
  `wizard-20260921T033743445603Z-e1513904ff9947998cbdd2c7e3682561`

The five retained endpoint samples were:

| Commanded pair | Measured pair | Residual | Classification |
| --- | --- | --- | --- |
| `[2377,1737]` | `[2385,1730]` | `[8,-7]` | settled miss |
| `[2383,1731]` | `[2385,1730]` | `[2,-1]` | settled small response |
| `[2385,1729]` | `[2387,1728]` | `[2,-1]` | settled accurate |
| `[2388,1726]` | `[2389,1724]` | `[1,-2]` | settled accurate |
| `[2389,1725]` | `[2391,1724]` | `[2,-1]` | settled accurate |

This independently reproduces session 1's structure: the two lowest commands share the
same measured primary-register plateau, while the three upper sampled commands remain
ordered and within two counts per register. No model is fitted or promoted yet. Session
3 remains necessary because the frozen release gate requires three independent startups;
after it completes, the analyzer must report the full-interval result and may additionally
identify a smaller supported upper interval if the full interval fails monotonicity.

### r51 physical session 3 and final interval decision

Session 3 completed on independent fresh boot `a3d1771a86d4997792ccf18454772ba6`.
As in sessions 1 and 2, startup validation sent no motion and the physical campaign
executed the exact frozen eleven-write route with no retry. Both session manifests are
complete and all declared sizes and SHA-256 digests reverified.

- Fresh-startup status before reset:
  `wizard-20260921T033920036749Z-13fa6480fbb94fdd8fc4bfd14c29527c`
- Fresh-startup status after reset:
  `wizard-20260921T033925501716Z-67d76e9f702e405a96b89d630f9b06c7`
- Full startup observation:
  `wizard-20260921T033931238892Z-9a349e895bcc4332a9bf99d349302d05`
- Consolidated 11-leg campaign:
  `wizard-20260921T033958553394Z-8ff01f839fbf460c8dd47a4ed54bb97a`
- Derived session result:
  `wizard-20260921T033958629676Z-40021e01981242cebd04637effa7fbe7`

Session 3 again measured the lower commands at `[2386,1730]` for both `2377/1737`
and `2383/1731`. The upper samples were `[2387,1728]`, `[2389,1725]`, and
`[2391,1724]` for commands `2385/1729`, `2388/1726`, and `2389/1725`.

The frozen three-session analysis first produced
`wizard-20260921T034022383194Z-93e578532d3a4f27a9ffd5765a39a57e`.
It correctly rejected interpolation across the full `2377..2389` primary-command span:
the held-out `2383` point produced maximum and p95 paired errors of 2.5 counts, above
the unchanged two-count gate. The full interval must therefore not be generalized.

The analyzer now also reports the explicitly bounded upper subinterval without altering
the failed full-span result or its tolerance. It fits only commands `2385` and `2389`,
keeps command `2388` wholly held out, and applies the same maximum and p95 two-count
release gates. Across the three independent sessions, the held-out `2388` errors were
`[1.0,1.0,1.0]` counts. Training endpoints were strictly monotonic. The upper
`2385..2389` primary-command interval is therefore validated for encoder-space linear
interpolation, with no extrapolation.

- Final full-span/subinterval analysis:
  `wizard-20260921T034147915991Z-6193f1cb9d754682b9cfd9c449e7ae11`
- Full interval `2377..2389`: **rejected**, maximum/p95 error `2.5` counts.
- Upper interval `2385..2389`: **validated**, maximum/p95 error `1.0` count.
- Focused interval-model/campaign/runner tests after adding the subinterval classifier:
  9 passed.

This release concerns only the correlated shoulder-pair encoder interval. It does not
authorize movement by itself and does not establish Cartesian, stylus-tip, keyboard-key,
or phone-screen accuracy. The next engineering step is to expose this bounded upper
interpolator through the command resolver, retain the two discrete endpoint lookups,
and use those components in a coordinated hover/press/retract ghost-key trajectory.

### Bounded command resolver and first ghost-key molecule

The validated upper interval is now integrated into a non-authorizing resolver. It
preserves the two r50 discrete lookups exactly and adds inverse mapping only for feasible
measured encoder pairs within the r51 `2385..2389` command interval. The resolver requires
fresh feedback at the validated lower conditioning plateau, rejects off-manifold desired
pairs, and forbids extrapolation, automatic retry, and automatic return.

- Command-policy export:
  `wizard-20260921T034659920859Z-ecdab535f19544a7aaa4d8671d507e50`
- Scope: `DISCRETE_ENDPOINTS_PLUS_UPPER_2385_2389_INTERPOLATION`
- Relevant resolver/model tests: 19 passed.

The first composed encoder-space molecule uses desired hover `[2388,1727]`, desired
press `[2390,1725]`, and the same hover for retract. The resolver produces command pairs
`[2386,1728] -> [2388,1726] -> [2386,1728]`, so each direct transition is two counts on
the paired registers. This is deliberately exported as a preview rather than executable
authority:

- Ghost-cycle candidate:
  `wizard-20260921T034824834028Z-fcdecda4a3d149fc894c596f6b363b21`
- Status: `PREVIEW_ONLY_DIRECT_TRANSITIONS_UNVALIDATED`
- Combined interval/resolver/cycle tests: 23 passed.

The distinction is important: r51 validated each endpoint after lower conditioning; it
did not validate direct upper-endpoint transitions. The next physical campaign should
therefore repeat the exact three-step command sequence from a freshly verified start,
capture each endpoint, and test both forward and reverse transitions across multiple
fresh startups. Passing that campaign would release this encoder-space molecule for a
ghost-key cycle. It still would not claim physical contact or task-space accuracy.

### Frozen direct-transition campaign

The next campaign is now frozen as a 12-write, three-startup experiment. Each session
contains repeated direct `2386/1728 <-> 2388/1726` transitions, lower conditioning,
and the known `2389/1725` terminal endpoint. It tests the proposed hover/press/retract
molecule rather than adding more isolated endpoint samples.

- Campaign-plan export:
  `wizard-20260921T034947657070Z-49435f72783047f9bd6aba05a46bf65c`
- Plan SHA-256: `eae09448c0542baf1ec054c2bdd9a5ce7e1752b01b7f5d0b9a49f9b0dd2229b6`
- Route length: 12 writes per startup; required startups: 3.
- Automatic retry: disabled.
- Maximum endpoint error: 2 counts; maximum repeat spread: 2 counts.
- Direct movement must be at least one primary-register count and match commanded
  direction.
- Planning/resolver/cycle tests in the final focused slice: 21 passed.

The existing global consecutive-small-response guard must not be relaxed. A future
firmware candidate may recognize only this exact manifest and continue a small direct
transition only after fresh endpoint verification passes; it must stop on wrong direction,
out-of-tolerance feedback, export failure, or any manifest difference. No firmware was
changed or installed while freezing this campaign, and the plan itself grants no movement.

### r52 offline implementation and qualification

The frozen campaign now has an exact firmware selector, native per-leg outcome policy,
matching host receipt policy, a dedicated runner, and a three-session offline analyzer.
The 12-command route is `2377, 2386, 2388, 2386, 2388, 2386, 2377, 2386, 2388, 2386,
2388, 2389` on the primary register; every secondary target is `4114 - primary`.
Preparation requires a freshly read start at goal `[2389,1725]` and measured pair
`[2391,1724]` within one count. Each completed leg is checked against its frozen
endpoint within two counts. Direct hover/press reversals must show at least one count
of primary motion in the requested direction, with no opposing secondary motion.
Only this exact manifest may retain a small-but-verified direct response after the
two-second observation window; four consecutive such direct responses stop progression.
Any failed native check or host export/assessment withholds the receipt, so the next
write is not released. The normal response policy remains unchanged for other routes.

Offline evidence (no controller connection, installation, startup, or movement):

- r52 staged from the pinned r51 source:
  `wizard-20260921T094319998322Z-f0f30f056b094e0eaddf6493cc16072b`.
- Default 4 MB/no-PSRAM profile compiled successfully:
  `wizard-20260921T094941126648Z-acc5e720a663431f8c0758f2212de354`.
- Pinned app SHA-256:
  `0389e22b97cb9e87a97dc4491746af385d3dfcf76c00daaaab434a36b088738b`.
- Offline source/binary/backup review:
  `wizard-20260921T095000154047Z-7509bcd94555463a86eae274d9e8b6f0`.
  App-slot headroom is 151,392 bytes; this is not a runtime stack or deployment proof.
- The legacy huge-app profile also compiled, but deployment review uses the default
  partition profile above. Neither build was uploaded.

The next gate is to reconcile the focused native/host regression suite, then wire the
reviewed r52 identity into the existing authenticated installation/startup workflow.
After an independently reviewed live installation, three fresh-startup sessions can
run the exact frozen route and be assessed by the offline analyzer. Until those
physical results pass, the direct ghost-key cycle remains **preview only**; there is
no released typing/contact or Cartesian accuracy claim.

### r52 installation and live-session wiring prepared

The reviewed r52 app is now bound to a single r51-to-r52 upgrade edge in the app-only
installer. The installer pins the 1,159,328-byte r52 image SHA-256 above, compares the
installed predecessor and protected regions before any write, retains the one-use
deployment journal, and preserves the filesystem. Installation evidence, read-only
startup observation, campaign preparation, and fresh-boot restart recognition now
accept only the explicit r52 revision. The session CLI independently binds the frozen
plan, one unused boot, a reviewed r52 startup export, and the exact runner; the analyzer
still requires three completed session exports.

Local installer preflight passed with `hardware_access=false`,
`deployment_authorized=false`, and no journal reservation. The focused r52
installer/CLI/runner/analyzer regression slice passed 45 tests. Neither the app-only
installation nor a controller startup or movement has been performed at this stage.
The live sequence remains: separately authorize one r52 app-only installation/startup;
verify its installation and idle read-only startup exports; confirm the fresh measured
start pose and clear fixed route; run one session without retry; examine/export results;
then use separate fresh starts for sessions two and three. A failure stops that sequence
instead of substituting a new pose or automatically trying another route.

### r52 single authorized installation and startup

The one approved app-only r51-to-r52 upgrade completed. The installer matched the
controller MAC and installed r51 predecessor before writing, verified all 1,159,328
r52 app bytes by full readback, and found the protected regions unchanged. Its one-use
journal records one startup reset and no retry or provisioning. Read-only startup
observation subsequently found one stable idle boot, no storage fault, and the expected
pair protocol. The frozen session-1 binding passed a local preflight only; **no
campaign preparation or movement command was sent**.

- App journal: `private-backups/controller-20260918-session1/app-r52-deployment-events.jsonl`.
- Installation evidence export:
  `wizard-20260921T183206556091Z-e7f5e6feee2941a08e04edb8dbb30533`.
- Idle startup export:
  `wizard-20260921T183206900052Z-81e57ace1709431a92f3e5b6f71f3e1a`.
- Current observed boot: `5995c4c8d61189911df7bd1bfab77a4f`.
- The read-only preparation path is useful for inspection, but it consumes the
  authenticated request sequence and the campaign's `NEW` state on that boot.
  A separate runner cannot begin at sequence zero on the same prepared boot.
  No ghost-key cycle or physical typing claim follows from startup.

### r52 read-only session-1 preparation

The authorized next step captured the fixed 12-leg challenge and three fresh joint
snapshots on boot `5995c4c8d61189911df7bd1bfab77a4f`. All three snapshots report
shoulder-pair goals `[2389,1725]` and measured positions `[2391,1724]`, exactly at
the frozen start gate. The report states `READ_ONLY_CAPTURE_PREPARED`, with raw joint
positions exported, start gate passed, and **zero target commands sent**. The
session-1 CLI initially passed its local one-use boot and plan preflight, but that
preflight did not account for the already prepared campaign on this same boot.
This does not establish clearance or authorize the 12-write physical campaign.

- Read-only campaign observation:
  `wizard-20260921T185721903937Z-4ddde89dc9b04598879e52d9d14c3c7e`.
- Raw and decoded joint-reference export:
  `wizard-20260921T185721852123Z-8b79bf6457a543cb85e09759f6e3a99e`.

### r52 session-1 no-write stop and handoff correction

The first approved session-1 runner attempt on this already prepared boot stopped
at its first authenticated status request with `Response sequence mismatch`.
The prior read-only capture had made six authenticated requests and changed the
campaign from `NEW` to `AWAITING_AUTHORIZATION`; the new runner correctly assumed
neither sequence continuity nor permission to resume. Its export reports no
responses, `start_attempted=false`, and no session result. The controller's separate
read-only hold status remained `IDLE` on the same boot. **No target write was
attempted; this is a host workflow error, not a measured motion failure.**

- Stopped runner export:
  `wizard-20260921T191640343948Z-64cbf187875e412e945a152c0decefcd`.
- The r52 session preflight now rejects any boot with a prior r52 read-only campaign
  capture. It also rejects any boot claimed by a different session index.
- For the next authorized session attempt, use a fresh startup and pass that new
  startup export directly to the runner. The runner's own single authenticated
  session reads and verifies the start pose and frozen reference before its first
  target write. Do not retry or resume the prepared `5995c4c8...` boot.

### Fresh-start r52 session 1: first reverse-transition stop

A separately approved fresh startup produced idle boot
`8e687b95f5511a095951225d1075ed89` and the session runner used one
authenticated sequence from `NEW` through reference review. It attempted four
target writes. Legs 0–2 were exported and accepted at measured endpoints
`[2385,1730]`, `[2387,1727]`, and `[2389,1725]`; their observation windows were
approximately 0.586, 0.468, and 0.354 seconds. Leg 3 commanded the first direct
reverse step to `[2386,1728]`. Its fault snapshot still measured `[2389,1725]`
and reported `GHOST_ENDPOINT_OR_DIRECTION`; no result or receipt was exported for
leg 3 and no later leg was attempted. Authenticated read-only recovery confirmed
`completed=3`, `phase=FAULT`, and no retained pending result. The fault is valid
evidence that direction was not yet proven, **not** evidence that the reverse
servo can never respond or that the physical arm reached the planned endpoint.

- Fresh-start idle startup export:
  `wizard-20260921T191935188583Z-28fd18e96af24a7a886183a5f70573dd`.
- Stopped session export:
  `wizard-20260921T191954678998Z-8a7f05501aeb4217a7a7cd162702b51b`.
- Fault export:
  `wizard-20260921T191954624346Z-1ec4d90b0223466d87352f26289f8e2c`.
- Read-only recovery export:
  `wizard-20260921T192038020348Z-ae3c79273e3f443fb95a1e113c2eab7e`.

Offline inspection identified an early-classification seam: the controller checked
the frozen direct endpoint/direction as soon as the normal assessor classified
three samples, even when fewer than two seconds had been observed. A revised
candidate will retain the same final endpoint/direction limits but require the
full two-second direct-transition window before promoting or faulting a settled
assessment. The host receipt assessor mirrors that minimum window. A simulated
delayed-reverse fixture now proves that the intended direction can appear after
the initial three scans; it does not establish that this physical arm will do so.
No further commands or restart are authorized on this faulted boot.

### r53 direct-window candidate and installation

The timed observation correction is staged as r53 from the reviewed r52 source.
Only `shoulder_characterization_owner.h` changes in the application image. The
same 12 target pairs, start gate, endpoint tolerance, direction requirement,
no-retry behavior, and export-before-next-leg rule remain. Direct legs that
already look settled must continue observation until at least two seconds have
elapsed from the first post-write sample. A truly stationary or wrong-direction
leg still faults after that window; this is not a compensation or tolerance
increase. The host receipt policy independently rejects direct-leg exports
shorter than the same window.

- Source staging:
  `wizard-20260921T192353008071Z-1b9f01d5ac994488a15d76852be9a349`.
- Default-profile offline compile:
  `wizard-20260921T192555773211Z-73d0f9f74c9c4b5d8cb022e9370880d0`.
- Pinned r53 app SHA-256:
  `8d5ed3f0feb491e2294bb6f56bf27f82c53f616d257c61f493df58d94f050de5`.
- Offline source/binary/backup review:
  `wizard-20260921T192611219874Z-692de670df434dc5a509ea921aa22b0a`.
- Local app-only installer preflight passed for the exact r52-to-r53 edge, with
  no hardware access, journal reservation, installation, startup, or movement.

One approved r52-to-r53 app-only installation completed. The installer verified
the predecessor, board identity, full r53 app readback, and unchanged protected
regions. It then performed its single startup. A separate read-only observation
found `IDLE` on boot `0e20871fbfad674d3ce715b8b39066da`, with the held-pair
capability endpoint responding. No servo command, movement test, provisioning,
or settings change was performed.

- App journal:
  `private-backups/controller-20260918-session1/app-r53-deployment-events.jsonl`.
- Installation export:
  `wizard-20260921T201020457398Z-3866fb2c590e461480be5623c1c2c03a`.
- Idle startup observation export:
  `wizard-20260921T201020861811Z-0cf96b6a2ed547f3ba9542be8e74ceff`.

The next physical session remains unrun and requires its own scoped movement
authorization. It should record whether the first direct reverse leg gains a
count within the full two-second window; the simulated pass and idle startup
do not establish a physical reverse-motion result.

### r53 session 1: pre-motion capture stop

The authorized fixed session was attempted once on idle boot
`0e20871fbfad674d3ce715b8b39066da`. Offline binding passed. Its authenticated
controller sequence returned `NEW`, accepted `prepare` as a read-only capture,
then advanced through `CAPTURING` to `FAULT`. The runner stopped
`INCONCLUSIVE` with `start_attempted=false` and `retry_allowed=false`; the last
status reported `writes_attempted=0`. **No target write or movement command was
sent.** The response does not include the internal capture/preparation fault
reason. The last r52 fault snapshot had goal pair `[2386,1728]` and position
pair `[2389,1725]`, whereas this frozen session requires goals `[2389,1725]`
and positions `[2391,1724]` within one count. If those earlier values persisted,
the preparation gate would fail. The r53 export does not itself measure the
current pair or distinguish that cause from a capture fault.

- Stopped session export:
  `wizard-20260921T201358771991Z-3092230e2928453390ece79367fb00a8`.
- Do not retry or use this boot for movement. First identify the capture failure
  from existing read-only evidence or improve non-motion fault observability
  offline. A subsequent attempt would need a fresh reviewed startup and its own
  movement scope; do not assume that the frozen start gate is satisfied.

### r53 fresh read-only pose after the capture stop

The existing pose-observation CLI was extended to bind r53 installation/startup
evidence and to reject a boot already claimed by an r53 campaign. Its focused
unit suite passed (15 tests). After one verified USB restart, the new idle boot
`fda9e5ae20739dfb4177d579f5607b95` produced a separate three-snapshot
device capture, categorized `STABLE_SAMPLED_POSE`. All seven control pairs were
unchanged across the capture. The relevant measured state was:

| Servo | Goal register | Position register | Three-snapshot span |
| --- | ---: | ---: | ---: |
| 12 | 2386 | 2390 | 0 |
| 13 | 1728 | 1725 | 0 |

The r53 ghost campaign requires starting goals `[2389,1725]` and positions
`[2391,1724]` within one count. The positions are within its tolerance, but
the **goal registers are not**. This confirms a concrete gate mismatch after
the r52 reverse-leg fault and explains why another unchanged campaign start
would be unproductive. It does not prove the precise internal reason emitted
by the previous `FAULT`, because that reason was not exposed in its response.

- Verified restart after observation failure:
  `wizard-20260921T201742709910Z-33d1ade9e34a48978258adf27a71d4a9`.
- Read-only startup export:
  `wizard-20260921T201748978614Z-72d57c07dbb04a45839ccbcc1b44b834`.
- Device pose capture export:
  `wizard-20260921T201803404732Z-c829773c1f064d6bb93f6e0daad1a64c`.
- Decoded pose assessment:
  `wizard-20260921T201803348737Z-4e6cf56e1de64e379e6cd752eb1dc661`.

This pose-observation boot is now reserved and cannot run the movement campaign.
Next, review a single bounded shoulder-pair positioning command from the
measured state to the frozen start goal, with independent feedback and export.
Do not silently weaken the campaign start gate or relabel goal values as
measured positions. Only after that positioning leg is verified should a new
startup be considered for the r53 transition session.

### Offline fixed-pair re-anchor contract

`src/rocell/application/fixed_pair_reanchor.py` now replays and verifies the
device-capture export, admits only the measured source goals `[2386,1728]`
with positions within one count of `[2390,1725]`, and freezes one paired
target `[2389,1725]`. Its endpoint verifier requires target goal readback,
positions within one count of `[2391,1724]`, at most three counts of selected
position travel, no neighbor goal changes, and at most two counts of neighbor
position change. All servo controls must remain unchanged, torque-on, and
within one count of sample spread across each three-snapshot capture. It
deliberately does not treat goal readback as
proof of physical motion; a zero-position-delta correction can satisfy the
start gate while remaining unproven as a motion test. The contract carries no
movement authority or transport. The real saved capture replayed successfully
through this policy, and the focused pose/re-anchor suite passed 23 tests.

The installed r53 diagnostic app does **not** expose this one-shot command.
The offline proposal is reproducibly exported at
`wizard-20260921T203220667017Z-c072e1a10c7641eb9f9c3ac962d8ac21`;
the export explicitly grants no hardware or movement authority.
An r54 candidate must implement it as a separate fixed, authenticated,
one-use native operation, never an arbitrary pair-target API. Required native
sequence: fresh three-snapshot start read on a new boot; exact source-goal and
position gate; bounded paired sync write once with fixed speed/acceleration;
fresh bounded post-write observation; stop on invalid/stale feedback or
unexpected neighbor travel; retained raw target and position evidence; durable
host export before declaring the re-anchor usable. A native fault must expose
its reason in read-only status to avoid repeating the opaque r53 preparation
fault. No automatic retry, return, torque change, or ghost sequence. Stage,
compile, simulate faults, and review the candidate before considering any
installation or physical write.

The first native policy component is now in
`firmware/diagnostics/fixed_pair_reanchor_policy.h`. It independently checks
three fresh read-only prewrite scans and three postwrite scans against the
fixed pair, full seven-servo torque/goal/position evidence, timing, readback,
selected travel, and neighbor envelope. It contains **no bus write or route**.
Its native fixture covers a successful pair plus stale start, wrong starting
goal/position, moving flag, wrong target readback, excessive endpoint travel,
neighbor change (including transient excursions), postwrite timing error, and
inconsistent raw feedback. The combined focused host/native suite passed 35
tests. This is a policy component,
not an r54 app image or permission to move; authenticated one-use command
composition, raw-result export, startup binding, and full candidate review
remain to be implemented.

`firmware/diagnostics/fixed_pair_reanchor_owner.h` now adds the isolated
one-use native state machine: sticky reservation, three start samples, fixed
intent, separate fresh prewrite sample, at most one fixed 12/13 paired write
at speed 20 and acceleration 1, three postwrite samples, and an await-export
state. Faults do not retry, return, or automatically mark completion. It
retains start/prewrite/end samples and attempted-write timing for a future
authenticated export adapter. Native fake-bus tests cover success, changed
start/prewrite, uncertain delivery, bad endpoint, evidence failure, and
single-use behavior. This owner is **not** registered on the current board:
its write callback and export-confirmation seam must remain inaccessible until
an authenticated route and exact retained-byte export verification exist.
The combined focused read-only pose, host re-anchor, native policy, and native
owner suite passed 41 tests after this addition.

The isolated owner now serializes its retained start/prewrite/endpoint scans,
attempted-write timestamp, count, and boot binding into a fixed 1,127-byte
big-endian record only while awaiting export. The host decoder independently
rechecks the fixed goal/position gates, scan timing, seven-servo raw feedback,
and neighbor envelope. A native-generated fixture is exported as canonical
hex plus assessment in a diagnostic-only folder and replayed byte-for-byte;
framing, boot, write-count, and starting-goal corruption are rejected. The
combined focused suite now passes 47 tests. This cross-language evidence
contract still does not authenticate a live source; the board route and
authenticated, one-use receipt/export binding are the next implementation
boundary. No r54 image has been staged or installed.

### r54 offline authenticated re-anchor candidate

The candidate now attaches the fixed-pair owner to the existing signed
characterization HTTP gate, explicitly enabled only for r54. The route exposes
start, status, retained record, and digest receipt; start accepts no caller
targets. The board adapter reuses the seven-servo raw-feedback reader and
exclusive ownership gate. Its only possible write is IDs 12/13 to goals
`[2389,1725]` at speed 20/acceleration 1. The owner counts a transmission
attempt even when delivery is uncertain and cannot retry or return. A native
fixture verifies inert registration, rejection of caller targets, exactly one
write, retained record, digest mismatch rejection, completion, and refusal to
start a second run. Existing characterization routes remain unchanged unless
r54 explicitly enables this addition.

The host's `FixedPairReanchorHost` uses the signed no-retry HTTP transport,
checks the exact 1,127-byte record and boot, independently reassesses every
scan, writes it to the workspace diagnostic export folder, replays the saved
bytes, and only then sends the retained-record SHA-256 digest as its receipt.
An HTTP timeout or invalid result stops the run; it is never interpreted as
permission to issue another movement. A digest receipt proves the authenticated
host acknowledged the exact record, not physical stylus-tip accuracy or any
general movement model. The host coordinator is a library seam, not a live
CLI or an invitation to start the arm without installation review.

The r54 staging script pinned and verified the reviewed r53 source, then
overlaid the fixed owner, policy, route, shared board reader, and explicit
composition flag. Its offline stage export is
`wizard-20260921T212212710482Z-d53d0e9a1dd44cc3b8f5adf0ef55ade3`.
The application-only `default-4mb-no-psram` compile passed; compile evidence
is `wizard-20260921T212407586789Z-77c03cf66296433dad23aba1c4e72ff3`.
The compiled app SHA-256 is
`c418af3062200c91e6cdf4c5540a7e251f09cdc36fccb9659a9b9a6181f818fe`.
The route, host, signed-transport, prior-composition, and pose-observation
focused regression set passed 83 tests. These are offline
tests, not a live endpoint test. **r54 has not been installed, started, or used
to send a movement command.** The installed board remains r53. Before any
physical trial, review memory/headroom and source hashes, verify a fresh boot
and exact current start pose, and use the normal app-only deployment and
read-only startup checks. Only one bounded re-anchor is contemplated; no
automatic ghost-key campaign follows it.

### r54 installed and read-only verified

The exact r53-to-r54 source and artifact review is exported at
`wizard-20260921T221053269829Z-74b79cc238f64a85ab3e8cc953be7c72`.
The app fits the 0x140000-byte slot (1,167,056-byte app, 143,664 bytes of
slot headroom). The pinned installer passed local preflight with predecessor
SHA-256 `8d5ed3f0…050de5` and unchanged-settings expectation. Before
installation, r53's read-only capabilities reported 151,300 bytes free
internal heap and a 90,100-byte largest block; those are observed runtime
numbers, not a complete stack or collision proof.

One app-only r54 installation and one startup completed. The installer
verified controller MAC `fc:e8:c0:f8:d5:38`, installed r53 predecessor bytes,
the partition table and filesystem, then independently read back the full
r54 app and confirmed SHA-256 `c418af30…1f818fe`. Protected regions were
unchanged. The one-use deployment journal is
`private-backups/controller-20260918-session1/app-r54-deployment-events.jsonl`.
No filesystem, credentials, torque setting, or servo target was changed by
this deployment.

The r54 startup observation at
`wizard-20260921T221826008253Z-840394dcac0349c09cb6a105e0670caf`
shows boot `413c3d9a5979773299ef36e411421eb4`, idle hold status, no
storage fault, and 145,372 bytes free internal heap (90,100-byte largest
block). A read-only seven-servo pose capture at
`wizard-20260921T221844006382Z-bb61853c6c1346f0ac88d7167cdab1f7`
was assessed as stable; its assessment export is
`wizard-20260921T221843949709Z-da337d96ad784d6bb734ec70b1cba03a`.
Selected servo 12 has goal/position `2386/2390`, and servo 13 has
`1728/1725`; all seven position spans were zero and all controls remained
torque-on. The fresh r54-derived offline re-anchor plan is
`wizard-20260921T221915958401Z-02c0a7ba6b3f42e980a67f89b7ff80a4`.
An authenticated, read-only request to the new r54 route returned `NEW|0`
and was exported at
`wizard-20260921T222004100232Z-97105f296a1449a58f4b570ff085caf3`.

**No r54 re-anchor target write has been sent.** The pose-observation and
authenticated status check consume this boot for trial purposes. The
`run_fixed_pair_reanchor.py` preflight correctly rejects it. A separate
startup, fresh startup receipt, and fixed-run preflight are required before
the single possible write. The gripper was previously photographed touching
the board; verify it is clear of contact before that physical trial. The
native owner will still require new three-snapshot start and postwrite
readbacks and will stop on any mismatch. Success would validate only this
small joint-goal re-anchor, not general spatial accuracy or a key press.

### r54 re-anchor result and standard-start checkpoint (2026-09-21)

The preceding paragraph records the **pretrial state**, not the current one.
After the user confirmed the gripper was clear of the board, a new r54 boot
passed startup and one-use preflight. The fixed pair command was sent once,
and its retained record was exported and receipt-bound at
`wizard-20260921T222923014318Z-d559019a180d41eaa9c43c62c39e6c48`.
Independent replay reports `GOAL_AND_ENDPOINT_VERIFIED`; the selected encoder
displacement was `[0,-1]` count. It does not establish visible rise, tip
location, or repeatable park. All seven servo goals/positions were frozen as
`REFERENCE_A` at
`wizard-20260921T223040009414Z-19964cdec96940a3a6e08e9715fd7856`.
See `STANDARD_START_AND_PARK_PROGRESSION.md` for the measured reference and
next bounded park-step plan. No additional movement on that boot is permitted.
