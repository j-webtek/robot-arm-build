# Command-space comparison and proposed single-micro-command experiment

## Completed offline

Added `command_strategy_simulation.py`, `compare_command_strategies.py` and unit
tests. 24 focused tests passed across strategy comparison, micro-policy simulation
and existing correction decision replay. Results are saved in
`software/runs/wizard-exports/command-strategy-synthetic-v1.json`.
No hardware movement, live guard modification or compensation setting change.

## Why command space matters

Starting example: command 0.95 degrees, reported angle 1.40625 degrees, desired
angle 1.25 degrees. This resembles a saved observation, but the simulated future
response is hypothetical, not fitted hardware behavior.

- Moving the actuator setpoint toward 1.25 increases the command from 0.95.
- Adding measured error to the previous command decreases it: error is -0.15625.

Those directions are opposite. A target measured in endpoint space cannot safely
be substituted for a calibrated actuator setpoint. Both simulated strategies cap
each command change at 0.10 degrees and cumulative changes at 0.30 degrees, with
at most three attempts and stops for no useful progress, overshoot or excursion.

| Hypothetical response | Toward desired setpoint | Previous command plus measured error |
| --- | --- | --- |
| Fixed additive offset | Stops: worsening error | In band, two attempts |
| Same offset plus 360/4096-degree quantization | Stops: no useful progress | In band, two attempts |
| 0.11-degree per-command deadband | Stops: unchanged | Stops: unchanged |
| Alternating offset perturbation | Stops: excursion | Stops: excursion |

The quantization/deadband/offset values are synthetic stress assumptions, not
verified firmware properties. The deadband model specifically ignores each
increment below its threshold; other deadband models may behave differently.
Eight deterministic cases do not establish success rates or optimal controller
gains. We have evidence to choose a commissioning hypothesis, not a production
compensator. The raw load field is not used to tune these models.

## Proposed hardware experiment: one 0.05-degree command decrement

Status: specification only. NOT registered in the wizard or native sender.
The existing >0.5-degree admission remains intact. This proposal requires a
separate bounded admission and its own tests before dispatch.

### Required starting evidence

1. A new verified descending 0.95-degree trial, speed 20 and acceleration 1,
   with a completed passive hold and an immutable export identifying its exact
   command. A saved old trial is insufficient proof of the active setpoint.
2. Starting reported wrist roll in [1.35, 1.45] degrees, desired endpoint 1.25.
   If a fresh 0.95 trial instead reaches the in-band 1.23047-degree endpoint,
   do not correct it or retry until a desired starting error appears.
3. Fresh six-joint feedback agreeing with that completed predecessor within a
   separately specified baseline tolerance, and no intervening commands from
   another process, web interface or SDK. Single-sender ownership must cover the
   predecessor-to-experiment interval; an old export cannot establish this alone.
4. Existing secured, powered, clear bench commissioning conditions. Stop/fault
   handling remains available; this experiment does not qualify unattended use.

### Fixed action and expected evaluation

The only proposed actuator setpoint is 0.90 degrees, exactly 0.05 below the
verified previous 0.95-degree command. This is not a promise of a 0.05-degree
physical displacement. It remains within +/-3 degrees absolute roll. Use joint
5, speed 20, acceleration 1, with an explicit degrees-to-radians serialization
test. One-use attempt is consumed before sending. No retry, return, reversal,
second correction or automatic high-positioning action follows any result.

After the command, retain the original receipt but do not count it as arrival.
Obtain independent feedback using the current bounded transport. Stop on missing,
stale or failed feedback, roll excursion >0.25 degrees from the fresh baseline,
or other-joint deviation >0.10 degrees from the initial pose. These proposed
limits require review in the new admission; they are not changes to current code.
Preserve the current 10-second completion budget and provisional 1-second feedback
gap, followed by the existing full passive hold if settling is verified.

Evaluate signed displacement, desired error before/after, whether the reported
position changed at all, stability, unchanged other joints and all timing/failure
metrics. A stable endpoint outside the desired band is an experimental result,
not a successful accuracy claim. Preserve failures and do not enlarge tolerance
to turn them into passes. Raw tR is retained without unverified unit conversion.

### Mandatory implementation tests before enabling this path

- Wrong prior command, missing/changed predecessor export, stale baseline,
  incorrect starting range or unrelated sender ownership must reject admission.
- Target 0.90 only, correct joint/radians/speed/acceleration; reject arbitrary
  target fields and multiple commands. No modification of the existing admission.
- Consume once; reject duplicate execution, restart/resume and uncertain retries.
- Command receipt alone cannot satisfy endpoint verification.
- Test unchanged, quantized, overshooting, drifting, delayed and failed feedback.
- Failed evidence or export must prevent continuation; always retain the attempt.
- Verify reports distinguish command delta from measured motion and preserve
  original bodies, checksums, predecessor identity and target/error metrics.

## Reproduce comparison (offline)

```powershell
.venv\Scripts\python.exe software/scripts/compare_command_strategies.py
.venv\Scripts\python.exe -m pytest software/tests/unit/test_command_strategy_simulation.py software/tests/unit/test_micro_correction_simulator.py software/tests/unit/test_endpoint_correction_simulation.py -q
```

Use `--output <new-path>` for a separate synthetic report; existing files cannot
be overwritten. No live protocol payloads are emitted by this simulator.
