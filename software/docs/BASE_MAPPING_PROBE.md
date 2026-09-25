# Base-joint mapping: bounded first native probe

## Purpose

Extend the empirical endpoint map beyond wrist pitch. The first experiment is
one uncorrected logical base command (T101, joint 1), not a wrist-derived offset.
Servo-reported joint position is the measurement; Cartesian tool-tip accuracy
and encoder sample freshness are not independently established by this test.

## Versioned path

The trusted host stages `stage_base_mapping_probe` through
`ArrivalWizardService.configure_base_mapping_probe`. The wizard uses its existing
review/start slot, native worker, original retention, and portable export verifier.
Intent v6 explicitly selects `b`; v1–v5 retain their wrist semantics.

### Opt-in synchronized baseline (v7)

The trusted-host `synchronize=True` option (bench flag
`--synchronized-baseline`, base probes only) selects v7. Movement bounds,
single-write admission and endpoint tolerances are unchanged. V6 and all older
exports keep their original interpretation.

V7 captures 1.25 seconds before dispatch. It assigns exactly the first line,
valid or invalid, to startup synchronization. The first newline must arrive
within 250 ms and 4096 bytes. Every startup byte remains in the original capture.
There must then be at least one second of clean pose observations; no second
malformed line or further partial prefix may be skipped. A missing/late delimiter,
short clean interval, unstable pose, gap, invalid interior line or mismatch holds
without writing. This does not assert that discarded-from-analysis startup bytes
are valid or that device samples are fresh.

`arm/campaign_stream_sync.py` implements the deterministic partition shared by
child admission, parent reconstruction and the exported diagnostic table.
The exported `baseline_synchronization` records original/startup hashes, byte
ranges and delimiter read-time bounds. The raw capture is never overwritten.
Post-command analysis is unchanged. No flushing, reconnection loop, extra serial
command, automatic retry, or added movement command is introduced.

- Exactly one nominal +1 or -1 degree increment from the retained planning pose.
- Fresh owned six-joint baseline must match before the one-use command is admitted.
- Base start and target stay within +/-5 degrees; actual fresh-start delta is
  greater than 0.5 and at most 1.5 degrees, with no direction reversal.
- Fixed speed 20, acceleration 1; five-second observation; no correction applied.
- Arrival tolerance 0.5 degree, settling span 0.1 degree, dwell 200 ms.
- All five nonselected joints retain their drift checks.
- Failed endpoint, uncertain write, cancellation, or timeout ends the attempt.
  No retry, automatic return, or second leg is authorized.
- Opening USB can reset the controller. The full arm sweep must be clear and the
  secured, powered bench setup remains user-reported, not geometrically certified.
  Software cancellation cannot guarantee stopping an already accepted goal.

## Reproducible procedure

1. Run focused incapable-kernel tests including both directions, wrong axis,
   changed bounds, misses, five nonselected axes, worker dispatch, wizard review,
   and independent portable reconstruction. These tests do not open hardware.
2. Acquire a fresh baseline through `bench_baseline_session.py`; inspect identity,
   finite/stable six-joint feedback and clean serial closure.
3. Use `bench_attended_campaign.py --base-probe plus-one` with the retained
   baseline, reviewed controller directory, and current operator confirmation.
   `minus-one` is a separate new experiment, not an automatic return.
4. Verify the exported parent report from `software/runs/wizard-exports`.
   Record requested and transmitted angles, actual start/final base feedback,
   signed error, direction, sample coverage, stability, other-joint changes,
   write accounting and cleanup. Keep the immutable originals and report hash.
5. Review before selecting the next probe. One success is not a fitted model:
   collect repeat observations and reverse-direction samples in matching contexts
   before any held-out evaluation or base compensation proposal.

## Interpretation

Do not copy wrist bias to base. The static reference map predicts command/register
conventions but is not empirical accuracy evidence. Joint coupling, load, speed,
tool configuration and approach direction may change error; preserve those contexts.
No general multi-joint native motion or automatic compensation is released here.
