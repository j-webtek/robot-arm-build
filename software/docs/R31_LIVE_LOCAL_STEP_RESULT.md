# r31 live local shoulder step — result and next decision

## Outcome

r31 was installed app-only, with a full matching application readback and
unchanged protected flash regions. One startup was sent. Read-only startup
observations showed the same idle boot before and after capability collection.

One bounded shoulder-pair target packet was sent. Fresh position feedback confirms
motion in both intended directions. The requested endpoints were not reached
within the two-count criterion: the parent ended STOPPED / ARRIVAL_DEADLINE.
Read-only fault settling then completed on the same boot, without a restart,
retry, return, torque command or further target packet.

These are encoder/goal-register observations, not measured Cartesian accuracy.

## Command and measured response (servo counts)

| Value | Shoulder 12 | Shoulder 13 |
| --- | ---: | ---: |
| Three identical fresh starting positions | 2429 | 1688 |
| Prior goal registers | 2419 | 1695 |
| New requested and read-back goals | 2405 | 1709 |
| Goal-register change | -14 | +14 |
| Positions during the arrival timeout | 2415 | 1702 |
| Last settling positions | 2414 | 1702 |
| Actual start-to-settled change | -15 | +14 |
| Final actual minus goal | +9 | -7 |

The three baseline scans passed. Authorization and prewrite checks passed.
Speed was 20 and acceleration 1. The first postwrite sample showed 2416/1700;
the second showed 2415/1702. It remained there through the five-second arrival
window, followed by a one-count change during settling. All five nonselected
joints retained their starting positions in the exported observations.

Final observed positions, IDs 11 through 17:
`[2047,2414,1702,2904,1591,2041,2047]`.
Final observed goals: `[2047,2405,1709,2907,1589,2040,2047]`.
These are historical observations, not authority to move from stale state.

## What this establishes

- The command reached the goal registers, and both measured positions changed.
  This trial is not evidence of a lost command or a reverse-direction failure.
- Actual incremental travel closely followed the change in the previous goals
  (-15/+14 versus -14/+14), rather than reaching the new absolute goals.
- The preexisting +10/-7 position-minus-goal residual became +9/-7. This supports
  investigating a locally persistent loaded-position offset. It does not prove
  its mechanical cause or a general compensation model.
- Increasing the timeout alone is not supported as a complete fix: observations
  remained short throughout arrival and subsequent settling.
- End-to-end command correlation, target readback, position review, fault
  retention and postfault exports now have real-device evidence.

## Next work

1. Compare this response with retained r29 data using actual deltas, prior goals,
   new goals and final residuals. Separate displacement prediction from absolute
   endpoint success so a useful motion trial is not confused with a passed target.
2. Build an offline local offset proposal and replay test. Preserve the coupled
   goal sum (4114); do not independently cancel each servo residual and force the
   coupled pair against itself. Check the achievable endpoint and tolerance for
   both joints before proposing a compensation command.
3. Test the candidate prediction on held-out data and failures before expanding
   the starting envelope. Do not loosen limits solely to relabel this run a pass.
4. For the next live trial, reacquire current pose and review a new bounded
   target. This boot/command is consumed; do not replay prepare or authorize.
   Do not automatically restart or return after this result.

Camera integration, contact tests, stylus accuracy and board registration remain
deferred. No higher-amplitude motion is justified merely by this small-step result.

## Evidence

Under `software/runs/wizard-exports/`:

- Installation review: `wizard-20260919T233940352510Z-6c5ee31b93114d1cafa7d75ca292f983`.
- Startup: `wizard-20260919T233940752174Z-c602d6610e0d4d5b9b9671f11744cec7`.
- Run: `wizard-20260919T234006065057Z-53ea59edfe2d4b20bfc7d3eaae25253e`.
- Original fault: `wizard-20260919T234003307893Z-6b4a93b6bedd482ebaf7041daedba0f4`.

Boot: `9a9130455e7486743fd7949fd7be31c2`; command: `local-step-1`.
Run plus referenced raw/signed movement and settling exports: 53 verification
checks, all valid. The run retains 20 accepted movement records plus original
fault evidence and five settling observations. Controller status reports one
target packet. The deployment journal has one write and one startup attempt.

Installed app SHA-256:
`e8400d1c302a70bed3283c4102fa6b202785c1ea35826de2e98754a09b80fae3`.
Entry point: `software/scripts/run_r31_local_step.py`; it uses the existing
protected key source and the r31-bound runner, with no plaintext key export.
