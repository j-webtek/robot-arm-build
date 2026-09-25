# Third frozen-lookup attempt: transport interruption

## Execution

Two explicit single-command wizard actions were attempted. Candidate, speed,
acceleration, limits and deadlines were unchanged. No automatic retry, return,
compensation or direction comparison followed the interruption.

1. High positioning: fresh reported roll 1.406250023 degrees, command 2.5,
   verified reported endpoint 2.285156222. All six joints unchanged during
   114 hold responses spanning 34.8748075 seconds. Maximum gap 616.5188 ms,
   below the existing one-second gap policy. Export integrity, original endpoint
   replay and exact hold verification passed.
2. Frozen descending lookup: fresh reported roll 2.285156222, command 1.25,
   desired 1.50 degrees. One send attempt; connection reset, no HTTP receipt,
   no endpoint feedback rows. Outcome remains `COMMAND_OUTCOME_UNCERTAIN`.
3. Separate read-only recovery query succeeded at 02:25:30 UTC September 17,
   reporting roll 2.285156222 and unchanged other joints. This does not prove
   that the command was never received or reconstruct its movement history.

## Evidence

All directories are beneath `software/runs/wizard-exports/`:

- Position: `wizard-20260917T022452303397Z-fe00a18cda364df6a7437cfeeed6583d`
  manifest SHA-256 `09516ce986124bc9e3a1b12c0c85f0806051d2a6eae880c61e531d13c20078c7`.
- Interrupted lookup: `wizard-20260917T022509854289Z-ea327d82629b40588413bd7e51ab68ce`
  manifest SHA-256 `780b9aac467b3c09d2e6d7b0a96cdff9f570fdee9357a185c9db06a5d4285e29`.
- Read-only recovery: `wizard-20260917T022530680580Z-cf8598560208418c9aaa6ab67d65d060`.

The offline reviewer now exposes whitelisted command-receipt failure metadata;
previously its compact output showed only the generic transaction failure and
an empty feedback-failure list. Original exports already retained the reset
category. Unknown/free-text failure strings are not copied into this summary.

## Conclusions and next step

There are still only two completed held-out endpoint observations, plus this
incomplete third attempt. The interruption is recorded separately in
`ROLL_150_MAPPING_EVIDENCE.json`, excluded from numeric endpoint ranges but not
hidden from reliability assessment. Neither compensation accuracy nor direction
dependence can be inferred from this attempt. Candidate remains disabled.

The observed failure is command-exchange connection reset, not demonstrated
arrival-tolerance failure or an 800 ms timeout. Its underlying network/controller
cause is unknown. Do not adjust compensation or deadlines to hide it.

Next perform a bounded read-only connection-stability observation. If clean,
plan a distinct fresh-baseline single-command trial from the actual current
pose, without replaying the consumed reservation. Keep direction comparison
pending until valid endpoint and hold evidence can be collected. No arm transport
or live control-policy code was changed in this turn.

## Read-only stability follow-up completed

Export `wizard-20260917T022718899209Z-30acbe1080bc4d138fbf33a5ec986342`
passed integrity verification using its resolved absolute path and original-body
observation reconstruction. There were 116 successful responses over 34.925426
seconds, maximum response gap 363.409 ms, with all six reported joints unchanged.
Roll remained 2.285156222 degrees. No further movement was sent. This clean
read-only interval does not resolve the preceding command's uncertain outcome
or prove that future command exchanges will be reliable.

34 focused tests passed for the reviewer, timestamp-band evaluator and transaction
runner. The next movement test remains a distinct fresh-baseline trial; approach-
direction comparison has not been performed in this turn.
