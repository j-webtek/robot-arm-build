# Fixed wrist-roll long-window repetition plan

## Why

Relative one-degree probes change their absolute target when the reported start
changes. We now have two long-window measured endpoints; freeze the actual raw
commands and measured starts so repeats compare the same experiment. Do not
transfer base/pitch coefficients or introduce compensation in this screen.

## Enumerated profile to implement before movement

Preserve v17's old fixed-target contract and v19's relative contract. Introduce
a separately versioned long-window fixed-target profile with these exact values:

| Direction | Required measured start r (rad) | Raw target r (rad) | Expected next measured anchor r (rad) |
| --- | ---: | ---: | ---: |
| Decreasing | 0.021475731 | -0.0005795035199432953 | 0.004601942 |
| Increasing | 0.004601942 | 0.022055234519943297 | 0.021475731 |

The decreasing raw target was previously sent from a different start. Its new
start-to-command travel is approximately 1.263672 degrees, within the existing
1.5-degree delta envelope. Its expected reported endpoint is an anchor hypothesis,
not a guarantee. The increasing pair has already been observed once.

Other five axes remain fixed to the current bench pose. Keep speed 20,
acceleration 1, one-use admission, fresh six-joint matching within 0.01 degree,
35-second observation, existing persistence/arrival/drift criteria, byte/read
budgets and cleanup reserves. No arbitrary targets, offset fitting or guard
relaxation belong in this profile. Simulation must cover substituted targets,
wrong starts/axes/speed, delayed change, misses, cancellation and reconstruction.

## Finite live scope after validation

At most four separately admitted commands: decreasing, increasing, decreasing,
increasing. Begin from the current measured high anchor. Independently verify
each original export and full-window persistence before considering the next
command. A fresh baseline must match the next anchor. Stop on a mismatch even
if the prior endpoint passed its broad arrival band. No corrective positioning,
automatic retry, or return command is included.

Compare the two new decreasing trials with each other and the two new increasing
trials with each other, matching complete six-joint starts, command, speed,
acceleration, payload, workcell and protocol/source context. The prior decreasing
trial is context only because its start differed. Preserve misses and incomplete
runs; do not select only favorable trials or call partial execution complete.

## Completion and later modeling

Export per-horizon error, after-five-second changes, matched-pair spread and
write/cleanup accounting from pinned originals. Two repeats per direction remain
a local screen. Only then consider additional independent points and candidate
local offset/linear models, with separate held-out corrected/control trials.
Joint feedback is not proof of Cartesian tool-tip accuracy.

Status: v20 implemented and validated (86 focused tests plus three supervisor
cases). One of four live commands was sent. Its raw capture was retained, but
verification held on a split JSON boundary; later complete rows also changed
roll position and did not match the next anchor. The remaining three commands
were not sent. No replay or corrective positioning. See
[first-run evidence and next work](WRIST_ROLL_LONG_FIXED_FIRST_HOLD_20260915.md).
