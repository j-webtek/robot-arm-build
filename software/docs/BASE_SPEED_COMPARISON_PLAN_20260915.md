# Controlled base speed-parameter comparison

## Purpose

The fixed speed-20/acceleration-1 route now has two complete single-connection
hardware runs with matching reported endpoints and verified exports. Next vary
one motion parameter while preserving endpoint accountability, rather than add
more identical endpoint repetitions. Camera work remains deferred.

## Before selecting the new value

1. Verify the exact received firmware's T101 speed and acceleration semantics
   against the retained protocol/firmware evidence and official implementation.
   Do not assume command values are degrees/second or that a smaller integer
   always means a slower physical motion. Avoid special zero/unlimited values.
2. Select one conservative comparison value and record its meaning and provenance
   before any live command. Keep acceleration at 1 and all other settings fixed.
3. Preserve v10–v14 speed-20 semantics. Use a separately versioned experimental
   profile with an enumerated parameter value, not a free-form speed/angle API.

## Experimental design

- Reuse the same small two-endpoint base route and actual six-joint pose context.
- Freeze the transmitted angles during comparison to isolate the effect of the
  speed parameter. At the new speed, the old inverse is only a candidate—not a
  validated speed-specific compensation model.
- Keep five-second post observations and existing recency, excursion, nonselected
  joint, handoff, one-use submission and cleanup checks. Do not simultaneously
  shorten dwell/capture or change connection strategy.
- Start with one increasing leg at the candidate value. Independently review its
  endpoint and telemetry before a separately admitted decreasing leg. Do not send
  a reversal from an ineligible endpoint or add a recovery move automatically.
- Once both directions qualify, predeclare a finite paired comparison against
  speed 20 with matched starting pose and clearly separated positioning moves.
  Counterbalance order if repeating. Do not stop collecting only when favorable.

## Software/export work

Add a speed experiment descriptor binding firmware/protocol, candidate parameter,
route, payload/context and model provenance. Explicitly mark validation at the
new parameter as pending. Preserve raw command bytes and independently measured
reported endpoints separately from desired endpoints and model predictions.

Extend comparison outputs with parameter value, signed/absolute endpoint error,
reported transition sequence, first changed report, final constant-run entry,
settling span, maximum reported excursion, other-joint drift, write accounting,
selected-sample age and cleanup. Separate host processing/USB timing from physical
speed claims. Reject mixed firmware/pose contexts and duplicate trials.

## Simulation and release checks

Test both directions, each allowed parameter, rejected unsupported/zero values,
endpoint miss, opposite response, excursion, other-joint movement, malformed or
late feedback, uncertain write, cancellation, no retry/fifth write and portable
reconstruction. Include modeled endpoint bias that changes with speed: it must
not be hidden by the existing speed-20 inverse or training aggregation.

Only then predeclare the exact finite live scope. A clean endpoint miss remains
an observation and ends progression. If timing changes without meaningful error
improvement, retain that result rather than claiming an optimization. Physical
tip accuracy and continuous overlapping trajectories remain outside this test.

## Progress: protocol review and offline comparison layer

Candidate selected: **spd=10, acc=1**, against the existing spd=20, acc=1.
The official [T101 documentation](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control)
describes speed in servo steps/second (4096 steps/revolution), with larger
nonzero values faster, and acceleration in 100 steps/second squared. The
[official M3 SDK documentation](https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/doc/roarm_m3_zh.md)
also identifies these units and nonzero integer ranges. Zero remains excluded.
This selects a lower documented setting, not a verified physical speed or a
promise that the motion will take exactly twice as long.

Important qualification: retained protocol.original.json explicitly says
installed_binary_verified=false. We have corroborated vendor semantics, **not
verified the exact installed binary**. Item 1's exact-firmware wording is not
fully satisfied; do not claim otherwise or silently mark it complete. Before
native release, resolve that item against the recorded unchanged-delivery and
vendor-protocol evidence policy; no flashing or firmware mutation is requested.

Implemented `application/base_speed_experiment.py`:

- Fixed offline specifications for both directions and only speed 10/20;
  acceleration and transmitted targets remain unchanged.
- Actual reported endpoint error, maximum base displacement, per-joint drift,
  and existing bounded host-acquisition timing summary.
- Explicit non-authoritative output: not export verification, settling proof,
  model validation, or permission to move.
- Simulation checks deliberately give speed 10 a larger endpoint bias and
  demonstrate that the summary retains the miss instead of using the inverse
  model's expected result. Both directions are tested.

Validation: 23 focused tests passed (speed specification/summary and existing
reported-timing tests). This is not the full native release matrix above.

Next implementation boundary: separately versioned native single-leg speed
profile, wizard staging, byte-exact portable reconstruction, and verified-export
comparison adapter that rejects mixed context and duplicate trials. The offline
summary intentionally does not accept unverified input as hardware evidence.
Then run the specified fault/simulation matrix before the first physical leg.

No speed-10 command has been sent. Existing v10-v14 speed-20 semantics and all
native admission checks are unchanged. No hardware connection was opened during
this implementation increment; historical base command count remains 36.

## Native integration increment

Implemented v15: one fixed speed-10/acceleration-1 base leg, separately named
increasing/decreasing routes. Staging rebuilds the frozen speed-20 model evidence
but labels it an unvalidated speed-10 candidate. All six fresh baseline angles
must match the staged pose within 0.01 degree, in addition to the fitted base
start-domain and nominal/transmitted travel checks. No retries or return moves.

`ArrivalWizardService.configure_base_speed_experiment` uses the existing one-use
wizard slot. Review text displays the actual speed and the model qualification.
The bench entry point exposes `--base-speed increasing` or `decreasing`; it does
not expose arbitrary speeds or angles. Portable reconstruction shares the exact
endpoint mathematics without converting the actual speed-10 command to speed 20.
`base_speed_comparison.compare_base_speeds` independently reads pinned original
exports, retains clean misses, and rejects wrong roles, hashes, context, starts,
or duplicate campaigns. Speed experiments cannot enter the training dataset.

Regression: **334 passed, 156 intentionally skipped** (inapplicable combinations
of the existing shared test matrix), 270.73 seconds. Report:
`runs/base-speed-integration-20260915.xml`. Includes native-shaped speed faults,
both directions, wizard review/execution/export/no replay, old profiles and v15
supervisor request/receipt association. No real serial device is used by tests.

Reference firmware rechecked against the pinned archive SHA256
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`:
[Waveshare archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip).
`uart_ctrl.h` lines 16-22 passes JSON speed/acceleration into T101's single-joint
function. `RoArm-M3_module.h` lines 770-774 passes them to base control; lines
306-314 passes them unchanged into `WritePosEx`. This corroborates the vendor
protocol; the installed binary remains unattested. For this bounded experiment,
use the existing unchanged-delivery + vendor-reference compatibility basis,
not a new requirement to flash or attest firmware. This explicitly resolves the
plan's overly strong exact-installed-firmware wording without claiming proof.

First live scope: see `BASE_SPEED_FIRST_NATIVE_TRIAL_20260915.md`. Only a fresh
eligible baseline permits one increasing write. Capture and review before any
separately planned decreasing trial or matched speed-20 positioning work.

Current result: the first isolated launch exposed a missing archive dependency
before serial execution. Fixed and covered by real isolated-interpreter v15
validation; 47 post-fix targeted tests passed. A separately admitted one-command
live test then completed with reported endpoint 1.054687474 degrees for desired
1 degree, error +0.054687474 degrees, zero other-joint drift and fully verified
exports/cleanup. See the first-native-trial document for both retained attempts.
Speed 10 has not yet demonstrated better accuracy or timing. Decreasing speed-10
testing and matched single-leg speed comparisons remain next; no model was
refitted and no additional or return command was sent.

Subsequent decreasing trial completed one speed-10 command: reported endpoint
0.439453128 degrees for desired 0.4 degree, signed error +0.039453128 degrees.
All other reported joints remained unchanged; portable verification and cleanup
passed. Both directions now have one passing candidate observation. See
`BASE_SPEED_DECREASING_NATIVE_TRIAL_20260915.md` and the next finite
`BASE_SPEED_MATCHED_REFERENCE_PLAN_20260915.md`. No matched speed-20 references
for this single-leg comparison have been collected yet.

Matched references subsequently completed: one increasing and one decreasing
speed-20 single-leg observation, both with identical six-joint starts and final
reported endpoints to their speed-10 counterparts. Error reduction is zero in
both pairs; host timing differences have opposite signs. No preferred speed or
new model is justified. See completed results and the unexecuted reversed-order
repeat in `BASE_SPEED_MATCHED_REFERENCE_PLAN_20260915.md`.

The reversed-order repeat has since completed and passed all four legs. Across
eight distinct matched observations, each direction's endpoint was identical at
speeds 10 and 20; timing showed no consistent advantage. Close this bounded
comparison without changing the default speed or fitting a new model. Results
and next movement-coverage work: `BASE_SPEED_REVERSED_REPEAT_20260915.md`.
