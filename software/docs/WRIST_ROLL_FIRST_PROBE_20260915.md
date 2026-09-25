# Wrist-roll single-joint characterization

## Implemented profile

v16 is distinct from all base and wrist-pitch profiles: logical T101 joint 5,
telemetry r (index 4), one uncorrected +/-1-degree request, speed 20, acceleration
1. Maximum roll start magnitude 2 degrees, target magnitude 3 degrees, fresh
six-joint start matching within 0.01 degree. Other-joint starting pose remains
within 0.5 degree of the recorded bench context. The existing 0.5-degree endpoint
arrival/drift tolerance, 0.1-degree settling span, 200ms dwell, 250ms selected
sample age and five-second post capture are retained; no compensation is applied.

Wizard: configure_roll_mapping_probe. Bench CLI: --roll-probe increasing or
decreasing. Both share one-use reviewed execution and portable exports. UI labels
the roll axis explicitly. No arbitrary angle/joint/speed input or automatic return.

Reference mapping rechecked against the SHA256-pinned vendor archive:
https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip
SHA256 a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57.
RoArm-M3_config.h defines ROLL_JOINT=5 and ROLL_SERVO_ID=16. Module roll control
lines 376-384 writes middle-position minus rounded angle steps; feedback lines
57-59 reverses the register direction. Existing joint_mapping.py records this
mapping. Reference firmware is not installed-binary attestation or empirical
position compensation.

Validation: 206 profile/legacy/native-package/supervisor/UI regression tests
passed (runs/roll-profile-regression-20260915.xml). Earlier focused run: 45 passed,
including both-direction wizard-to-collector-to-export tests and no replay.
Coverage includes wrong axis/speed/offset/pose, miss, wrong direction, excursion,
all five other axes, malformed/late feedback, short/uncertain write, cancellation,
and isolated interpreter intent validation. Simulated perfect endpoints are not
hardware evidence.

## First live scope, predeclared

Use standing secured/clear/powered/operator-present setup confirmation; verify
the selected USB identity and a fresh baseline. Expected reported pose radians:
[0.007669904,0,1.593806039,0.047553404,-0.001533981,3.149262558].
Send at most one increasing roll request, target = staged roll start + 1 degree.
From the expected start this is approximately +0.912109 degree absolute.
No base movement, no return, no retry, no model correction. Review original
export, raw axis readings, signed endpoint error, other-axis drift and cleanup.
If the endpoint misses, retain it for characterization and end this run.

Status at declaration: software ready; no roll hardware command sent yet.

## First physical result

Fresh baseline `operation-ae2593d5bf7e4231b213b93c676dae53` matched the expected
pose and closed with zero command bytes. One v16 command was then sent:
`campaign-43a7e9a656904344bfa8e5922b4e8045`.
Report SHA256: `07575808693c889b9fb8932f8426ed1f46da5e51458d8f1cc8db46073bb0728a`.

- Start roll approximately -0.08789063 degree.
- Transmitted/desired absolute target 0.015919311519943295 rad, approximately
  +0.91210937 degree: exactly a +1-degree request from the staged start.
- Final reported roll 0.012271846 rad, approximately +0.703125 degree.
- Reported change +0.791015620 degree; signed endpoint error -0.208984380 degree.
- Endpoint passed the existing 0.5-degree arrival band and quiet-dwell checks.
  Passing is not exact positioning: preserve this undershoot for characterization.
- All five other reported joints unchanged; no excursion flagged.
- One submission, 64 confirmed bytes, no uncertainty; 280 post pose samples.
- Selected baseline age at write 141ms. Final constant-value entry acquired
  265-281ms after write; host acquisition timing is not physical servo timing.
- All handles closed, zero pending I/O, cleanup within budget.
- Original integrity, endpoint reconstruction and completion independently verified.

Full observations: `runs/WRIST_ROLL_FIRST_PROBE_20260915.json`.
Originals: `runs/wizard-exports/campaign-43a7e9a656904344bfa8e5922b4e8045/`.
Final joints [b,s,e,t,r,g] radians:
`[0.007669904,0,1.593806039,0.047553404,0.012271846,3.149262558]`.
Roll command count: one. Base command count remains 44. No settings were made
persistent, no compensation was fitted, and no return or second command was sent.

## Next finite test, not executed

After a fresh baseline verifies this actual endpoint and unchanged other joints,
stage one uncorrected decreasing roll request of -1 degree from the newly reported
start, using the same v16 profile, speed 20/acceleration 1 and five-second capture.
This is not a command to a presumed zero position or an automatic return. Retain
the actual signed error, all-axis telemetry and raw export even if it misses.
Stop after this leg; do not compensate using the first observation alone.
Then define repeated matched-start directional observations before fitting any
roll model. Base/wrist-pitch coefficients must never be reused for roll.

## Decreasing probe completed

Fresh baseline `operation-8c5bd19e34b3451f8e56b490247f8387` matched the actual
previous endpoint and closed with zero command bytes. One decreasing v16 trial:
`campaign-a03bb73fa3ac40589769699ff6ae6907`.
Report SHA256: `f656340e95049f6e9f12f6b3547bcf66fda06c492c0b7d3a90f5f4a354a050df`.

From r=0.012271846 rad, the transmitted absolute target was
-0.005181446519943296 rad (one degree lower). Final r=0.001533981 rad:
reported travel -0.615234345 degree; signed endpoint error +0.384765655 degree.
The endpoint passed the 0.5-degree band and dwell, but this is not exact placement.
All five other reported joints remained unchanged; no excursion flagged.

Exactly one submission, 65 confirmed bytes, no uncertainty; 281 post samples.
Selected sample age at write 140ms; final constant-run entry acquired 344-360ms
after write. All handles closed with zero pending I/O within budget. Original
integrity, endpoint reconstruction and completion independently verified.
No further or return command was sent and no compensation was applied.

Result: `runs/WRIST_ROLL_DECREASING_PROBE_20260915.json`.
Originals: `runs/wizard-exports/campaign-a03bb73fa3ac40589769699ff6ae6907/`.
Current [b,s,e,t,r,g] radians:
`[0.007669904,0,1.593806039,0.047553404,0.001533981,3.149262558]`.
Roll command count is now two; base remains 44. Next preparation is defined in
`WRIST_ROLL_FIXED_TARGET_REPEAT_PLAN_20260915.md`; no fixed-target repeat sent yet.
