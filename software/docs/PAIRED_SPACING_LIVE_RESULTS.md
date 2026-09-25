# Paired wrist-roll spacing: completed live run

Session: `f779bddc786f4828945dee5aa264609b` (export timestamps 20260917 UTC).

## Implementation and checks

Added `PairedSpacingSession` and the explicit CLI option
`--live-paired-spacing` to `software/scripts/run_controlled_roll_comparison.py`.
Default CLI behavior remains inert. The fixed sequence is high/0.95,
high/1.05, high/1.05, high/0.95 degrees. Existing native one-use admissions,
fresh baseline checks, endpoint verification, passive holds, journal publication,
timing limits and fault-stop rules are unchanged. No automatic retry or return.
34 focused session, adapter and raw-load tests passed before live execution.

## Verified result

All eight single-command legs completed endpoint verification and unchanged
six-joint passive holds. Four positioning commands of 2.5 degrees each reached
2.285156222 degrees. All probe desired endpoints were 1.25 degrees; speed 20,
acceleration 1. These are controller-reported joint angles, not independent
physical-space measurements.

| Probe order | Command degrees | Reported endpoint degrees | Desired error degrees | Successful hold reads | Constant raw tR |
| --- | --- | --- | --- | --- | --- |
| A1 | 0.95 | 1.230468748 | -0.019531252 | 120 | -20 |
| B1 | 1.05 | 1.406250023 | +0.156250023 | 120 | -24 |
| B2 | 1.05 | 1.406250023 | +0.156250023 | 116 | -24 |
| A2 | 0.95 | 1.230468748 | -0.019531252 | 121 | -20 |

There were no failed hold requests. Maximum hold response gap across all legs:
427.149 ms (below the current provisional 1-second limit; 250 ms is not a gate).
Measured predecessor-hold-end to next dispatch intervals: 20.881946–20.920781 s.
The 34 journal records were replayed in sequence with their hash links checked.
Final event: COMPLETED, eight reviewed legs. Final journal-file SHA256:
`cbc546bddfb717798a955033d5b86aa950ff5920e14c2627e25b8cf1a1030b56`.

## Interpretation and next work

The ABBA repeats agreed within this run. However, earlier 1.05 commands reached
1.230468748 with tR=0, versus 1.406250023 with tR=-24 now. Earlier 0.95 trials
also occasionally reached 1.406250023. Neither fixed command has demonstrated
universal repeatability. The current evidence favors 0.95 for this session's
1.25 target, but does not justify replacing or globally enabling compensation.

Raw tR units and installed-firmware computation remain unverified. Settled tR
is post-command information, not a proven pre-dispatch predictor. Do not fit a
causal load correction from this small selected dataset.

Next: consolidate cross-session command, baseline and approach history into a
single offline comparison, including failed trials. Assess bounded endpoint
verification/correction strategies in simulation before admitting any corrective
micro-move: existing moves must exceed 0.5 degrees, so simply issuing the tiny
remaining error would violate current admission. Do not weaken that guard or
automatically retry to make results pass. No new motion or model is authorized
by this report.

## Reproducible exports

All directories below are in `software/runs/wizard-exports`; each contains its
manifest and original response evidence. The session's `comparison-<session>-*`
files bind their manifest hashes and ordering.

1. `wizard-20260917T033713806210Z-a72784c94dc948048c89b2a0bdd2eb04`
2. `wizard-20260917T033811685835Z-21629c46a2b84a3c954bfca5b190063a`
3. `wizard-20260917T033909537737Z-74b3a4d1e71540999f267e55ca7e5d75`
4. `wizard-20260917T034007489896Z-5ec4b8626aba4e4aa244bc003322f9d9`
5. `wizard-20260917T034105282836Z-1c549f7e0dd74aecb8d1e4778d3f2412`
6. `wizard-20260917T034203247660Z-0ef9416404e349aca64867b0fed885f0`
7. `wizard-20260917T034301109017Z-632bf18953f5420c8fc55684b79e997a`
8. `wizard-20260917T034358977385Z-f3689f51e42f4bec9cada371e0b6b6b3`

Offline review (no movement): run `software/scripts/review_roll_load.py` with
one or more exact export paths using `.venv\Scripts\python.exe`.

Last recorded pose: b=-0.001533981, s=0, e=1.593806039, t=0.007669904,
r=0.021475731, g=3.149262558 radians. This is historical evidence, not a fresh
baseline for a later move. The process exited successfully; no further move
was sent after the final hold.
