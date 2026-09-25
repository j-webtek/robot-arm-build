# Local command-spacing experiment

## Question

Do nearby descending commands produce distinguishable reported endpoints, or is
the between-trial variation comparable to the effect of changing the command?
The completed controlled blocks reproduced two different endpoints for command
0.95 despite consistent scheduling. Do not refit an offset before measuring the
local response. This experiment measures controller joint feedback, not physical
tip accuracy, and cannot by itself establish deadband, encoder resolution or a
mechanical cause.

## Prefer small command spacing over in-place micro-movement

Use a separately verified high position before every probe. Proposed commands:
**0.85, 0.95, 1.05, 1.05, 0.95, 0.85 degrees**. Each command appears twice in a
forward/reverse order. All probes have desired verification reference 1.25,
speed 20 and acceleration 1. This is characterization, not candidate validation
or automatic error correction. Keep both frozen lookup candidates unchanged.

At the historical high baseline 2.285156222 degrees, these correspond to physical
command deltas approximately -1.435156, -1.335156 and -1.235156 degrees. All fit
the existing >0.5 and <=1.5 degree transaction step window, absolute target bounds,
desired-to-command bound and same-side rule. **No minimum-step relaxation is
needed for this design.** Small spacing between successive experimental commands
does not imply small travel from each independently prepared starting position.

This compatibility is conditional on the actual fresh baseline. It is not
admission for the historical pose. The new 0.85 and 1.05 commands are not currently
exposed by native wizard actions; an explicit enumerated sweep action is still
required. Do not send arbitrary JSON or modify a frozen candidate to route around
the native allowlist.

## Finite procedure

At most six probes and six positioning moves, one independently admitted move at
a time. Before each probe:

1. Read a fresh six-joint baseline. Preflight the positioning command 2.5 using
   existing limits. If the present pose cannot reach it within the existing
   envelope, stop and replan; no automatic bridge/return or guard changes.
2. Execute the high positioning action, verify endpoint and full unchanged hold,
   export and independently reconstruct the evidence.
3. Use the existing measured scheduling procedure, then obtain a fresh baseline
   and preflight the selected probe again. Reject an incompatible baseline.
4. Persist the exact command and predecessor link; send the selected probe once.
   Collect independent endpoint responses, full hold and export. Stop the session
   on connection, endpoint, other-joint, hold, integrity or scheduling failure.
5. Only after review, prepare the next leg. Never interpret the command receipt
   as endpoint evidence and never retry an uncertain command.

The full hold is the existing approximately 35-second capture. The proposed
18–22 second inter-leg dispatch window controls experiment scheduling only, not
ordinary motion authority. Report measured coverage rather than assuming a
nominal 35-second capture proves 35 seconds of observations.

## Analysis and decision

Record each command, predecessor hash, fresh pose, direction, dispatch/response
timing, initial endpoint, hold-final endpoint and full hold range. Group two
independent trials per command; report individual outcomes, ranges and overlap
between neighboring groups. Keep failed and incomplete records visible. Two
trials per command are exploratory, not confidence intervals or qualification.

If within-command spread overlaps the neighboring command responses, do not
pretend a single deterministic inverse mapping is established. If neighboring
groups separate, that suggests another bounded validation experiment, not an
automatic calibration promotion. Do not estimate fine resolution from rounded
telemetry alone. No runtime compensation model is fitted by this experiment.

## Implemented and verified offline

`src/rocell/arm/local_command_sweep.py` provides pure preflight and descriptive
response summaries. `scripts/preflight_local_command_sweep.py` evaluates the
historical example without hardware access. All six example probes passed the
unchanged transaction constructor. Twelve tests passed across this module and
the existing transaction tests, including incompatible starting positions,
duplicate/reordered evidence, invalid readings, incomplete trials and failures.

No native code, wizard action, movement policy or candidate was changed. No
physical movement occurred. Next implement the enumerated probe action and
finite six-probe session adapter, test them in simulation, then launch explicitly.

## Wizard and finite-session integration completed

The implementation stage described above is now complete. Three fixed native
actions are registered and shown in the wizard:

- `run_wifi_roll_sweep_low_trial`: command 0.85 degrees.
- `run_wifi_roll_sweep_center_trial`: command 0.95 degrees.
- `run_wifi_roll_sweep_high_trial`: command 1.05 degrees.

All use desired 1.25, speed 20 / acceleration 1, the unchanged bounded transaction,
fresh baseline, MAC checks, transport lock, native one-use reservation and existing
endpoint verification. Their metadata is `LOCAL_COMMAND_SPACING_V1`, with
`held_out: false` and `model_updated: false`. The central 0.95 probe is explicitly
characterization, not an additional frozen-candidate validation sample.

`CommandSpacingSession` reuses the tested finite scheduler, durable session journal,
wizard adapter and original-export reviewer. Its immutable default sequence has
twelve legs: high before each of the six probes in the order above. It validates
characterization metadata as well as command, desired endpoint, candidate absence,
hold, predecessor and scheduling checks. No resumable queue, corrective move or
retry was added. Prior comparison sessions retain their original eight-leg plan.

Explicit live launch, when ready for up to twelve bounded roll movements:

```powershell
.\.venv\Scripts\python.exe software/scripts/run_controlled_roll_comparison.py --live-six-probes
```

This flag is mutually exclusive with `--live-two-blocks`; the default shows help
without constructing a physical service. Default help was checked. The physical
sweep has **not** been run during this implementation turn.

167 focused tests passed across native actions, session scheduling, wizard adapter,
local sweep and wizard service. Coverage includes allowed and rejected baselines,
fixed command values, metadata, twelve-leg simulated completion, wrong evidence
classification and inert previews. JavaScript syntax validation passed.
No transaction bounds, candidate contents or compensation coefficients changed.

Next execute the explicitly launched sweep, review all six characterization
outcomes including failures, and summarize within-command ranges. Do not add
these probes to the historical held-out lookup validation counts.

## First physical run

The first twelve-leg run stopped on a read-only timeout during the final probe's
hold, after eleven fully verified legs. See `LOCAL_COMMAND_SWEEP_LIVE_RESULTS.md`
and `LOCAL_COMMAND_SWEEP_EVIDENCE.json`. All twelve initial movements reached
verified reported endpoints, but only five probes have complete verified holds.
The failed hold remains excluded from complete-hold comparisons; no retry was sent.
