# Three-trial command and timing review

Offline only. No commands, compensation changes or live-policy changes occurred.
`scripts/review_wifi_roll_export.py` now includes a reusable `trial_timeline`
for successful trials with retained command receipts. It checks the recorded
payload SHA-256 against the same canonical serialization used by dispatch,
checks original response bytes against their digest, and reports host timestamps
for independent endpoint reads. Receipts remain excluded from endpoint evidence.

## What matched

All three held-out descending trials used:

- Frozen candidate `822965da1d902c86993a50c8647b06e672e37323b56a211a42a1c4bc6e48a910`.
- Wire command: T=101, joint=5, rad=0.01658062789394613 (0.95 degrees), spd=20, acc=1.
- Canonical payload SHA-256 `b663d23d5912de791b2deccbcd6515581b89e130603c9663fe2cfff0fce1fbde`.
- Desired host verification endpoint 1.25 degrees and the same six-joint baseline
  `[-0.001533981, 0, 1.593806039, 0.007669904, 0.0398835, 3.149262558]`.
- Numeric HTTP receipt with response SHA-256
  `3e41ff9bf8e24ae967d452ea275a526c281b35ff2d9fa6bd4a37505e54a70c03`.
  Its roll value matches the pre-move baseline, not the final endpoint.
- Four independent post-command observations followed by unchanged full holds.

These checks establish agreement among retained software records, not a packet
capture, proof of device sample freshness or independent physical accuracy.

## What differed

Trials A/B/C correspond to the three ordered entries in
`ROLL_LOCAL_MAPPING_EVIDENCE.json`.

| Measurement | A | B | C (latest) |
| --- | ---: | ---: | ---: |
| Baseline age at dispatch (ms) | 8.9225 | 8.8295 | 10.9287 |
| Dispatch to HTTP receipt (ms) | 52.7869 | 34.5154 | 47.5136 |
| First response after dispatch (s) | 0.270765 | 0.289868 | 0.306203 |
| First reported roll (deg) | 2.109375005 | 1.845703151 | 1.933593731 |
| Second response after dispatch (s) | 0.580905 | 0.718800 | 0.614253 |
| Second and subsequent reported roll (deg) | 1.230468748 | 1.230468748 | 1.406250023 |
| Dispatch to verified endpoint (s) | 1.183723 | 1.222639 | 1.233339 |
| Verification to first hold request (s) | 0.750346 | 0.718441 | 0.748374 |
| Hold response span (s) | 34.855355 | 34.930239 | 34.903407 |
| Hold responses | 121 | 119 | 115 |
| Previous observation end to dispatch (s) | 20.060760 | 76.618328 | 22.117787 |

There are only four endpoint samples per trial; these do not reconstruct the
continuous movement, exact physical settling time or any unobserved overshoot.
Each trial's last three endpoint samples match its entire subsequent hold.

## Positioning history

A and C both followed a verified command to 2.5 degrees, from a reported
1.494140602-degree starting roll, followed by a full unchanged hold. Their final
positioning readings matched the lookup's fresh baseline. Earlier mechanical
history and total elapsed dwell were not controlled identically.

B followed a separate recovery observation after an uncertain high-positioning
attempt. That recovery also matched the lookup baseline but cannot convert the
preceding uncertain command into a verified positioning trial.

Previous observation exports:

- A: `wizard-20260917T013121624155Z-395773d64dc241c2b95506075c010ed0`
  manifest `b92034fd65b256778a415194f20c91ba54f3e92c5f620a857725995199b931c2`.
- B: `wizard-20260917T013556012810Z-61e8a82bb35a498e819320c3931ba5e8`
  manifest `46465a48ec677f46b3cefeb0ff27871eddf925191989804bf44c0eb60b3efb2d`.
- C: `wizard-20260917T023739179740Z-cb144bbb5c0549519688d24e7b673522`
  manifest `a3ff99c95d11791b9a756f049da4bf258b7c29f6fd35dedda81d1828b4aa018c`.

All lookup and predecessor export integrity checks passed, and predecessor
observation bodies reconstructed their stored summaries. Cross-export intervals
use host monotonic timestamps assuming the same clock epoch; the records do not
independently attest a shared boot identity. They are not controller dwell timers.

## Conclusion

No mismatched command payload, changed reported baseline, command receipt error,
or late hold change explains C in these records. Receipt and verification timing
are broadly similar, not a demonstrated cause. A different sampling instant
could explain different early readings but not, by itself, the persistently
different later reported endpoint. Mechanical state and firmware/servo behavior
remain possible explanations, not established diagnoses. Do not infer a required
new offset or a successful root-cause fix.

## Next bounded repetition protocol (not executed here)

Implement an explicit, finite two-block experiment with frozen commands and
complete evidence. Each block uses the same positioning action history:

1. Fresh baseline; position high and verify endpoint plus full hold.
2. Uncorrected descending 1.25 command; verify endpoint plus full hold.
3. Position high again; verify endpoint plus full hold.
4. Frozen descending lookup 0.95 for desired 1.25; verify endpoint plus full hold.

Do not pre-queue commands: authorize each through existing single-use admissions
only after the preceding evidence review succeeds. Stop the block on transport,
endpoint or unchanged-hold failure; no retries or automatic return. Starting
envelope failures require replanning, not guard bypasses.

The runner should record predecessor export hashes and a shared host clock/boot
identifier. Use a fixed observation procedure and a measured post-hold scheduling
window (proposed 20 +/- 2 seconds), with a fresh baseline immediately before the
next dispatch. This is an experimental control, not an accuracy requirement or
safety relaxation. Missing the window invalidates comparability; do not rush or
skip integrity review to meet it. No wait/sequence runner was enabled here.

Assess within-command endpoint ranges and paired uncorrected-versus-compensated
errors, retaining all failures. Two blocks are exploratory, not qualification.
Do not refit while gathering them. If variation persists, the next investment
should be a bounded small-step response experiment or independent measurement,
not unbounded repetition of the same offset.

## Verification

41 focused tests passed (reviewer, timestamp bands and transaction runner),
including payload/response tampering and invalid timing bounds. The three real
lookup exports separately passed endpoint/hold replay with the new timeline.
This work has no hardware effects; latest physical state remains historical.

Block-level evidence checking is now implemented in
`review_roll_comparison_block.py`; see `ROLL_COMPARISON_BLOCK_AUDIT.md` for the
historical replay. The finite session scheduler remains to be implemented and
tested; block auditing alone does not enable or qualify live execution.
