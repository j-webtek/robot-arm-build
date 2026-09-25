# Micro-correction commissioning plan and offline simulator

Status: offline policy implemented and tested; NOT connected to hardware.
The live >0.5-degree minimum step remains unchanged. No live command was sent.

## Purpose

Determine whether a bounded feedback correction can improve wrist-roll endpoint
repeatability without repeated blind commands. Existing 0.95/1.05-degree trials
showed multiple settled endpoints despite matching reported starting poses.
Do not assume the desired endpoint equals the correct actuator command.

## Built now

- `software/src/rocell/arm/micro_correction_simulator.py`: pure synthetic policy.
- `software/scripts/simulate_micro_correction.py`: inert-to-hardware scenario CLI.
- `software/tests/unit/test_micro_correction_simulator.py`: stop/limit tests.
- `software/runs/wizard-exports/micro-correction-synthetic-v1.json`: synthetic
  results, explicitly not mixed with successful hardware-trial evidence.
- 20 focused tests passed including previous correction-decision tests.

## Proposed simulation limits

| Parameter | Offline value | Meaning |
| --- | --- | --- |
| Joint | wrist roll only | Other five joints remain at initial values within tolerance |
| Absolute roll | +/-3 degrees | Initial, proposed and reported roll envelope |
| Analysis acceptance band | +/-0.05 degrees | Illustrative, not a live tolerance change |
| Maximum idealized target increment | 0.10 degrees | Relative to last settled reported angle |
| Attempt limit | 3 | Each attempt consumed before feedback inspection |
| Cumulative target increments | 0.30 degrees | Not a measurement of actual swept travel |
| Maximum observed excursion per episode | 0.25 degrees | Relative to episode starting roll |
| Other-joint drift | 0.10 degrees | Relative to original six-joint pose |
| Feedback gap / episode budget | 1 / 10 seconds | Synthetic post-dispatch clock |
| Settling | Last 3 samples span >=0.20 s and <=0.01 degrees | Synthetic only; not a replacement for live passive holds |

No automatic direction reversal after an out-of-band overshoot. No next attempt
after a failed request, uncertain outcome, invalid/nonmonotonic/late feedback,
excursion, other-joint drift, unsettled endpoint or insufficient improvement.
Late failures in the supplied trace override an earlier apparent arrival.
Continuous trajectory clearance and inter-sample excursions are not proven.

## Scenario results

| Synthetic scenario | Result |
| --- | --- |
| Ideal progress | In band in two attempts |
| Quantized progress | In band in two attempts |
| Unchanged reading | Stop: no useful progress |
| Overshoot outside band | Stop: no reversal |
| Feedback delayed beyond 1 second | Stop: deadline |
| Missing/uncertain response | Stop: feedback unavailable |
| Other-joint drift | Stop: drift |
| Slow improvement | Stop after three attempts |
| Arrival followed by failed feedback | Stop: failure, not successful arrival |

The provided traces are hypotheses, not an identified plant model. Successful
synthetic cases say nothing about probability of hardware success. Timestamps
are relative to hypothetical dispatch; the simulator does not prove real
transport deadlines, sensor freshness, force limits or physical accuracy.

## Next implementation stages

### 1. Resolve command-space semantics offline

Completed initial comparison and single-step specification:
[command strategy results](COMMAND_STRATEGY_COMPARISON.md). Incremental adjustment
is a commissioning hypothesis only, not a calibrated or enabled controller.

Compare two explicitly different hypotheses: target desired physical angle versus
adjust the previous actuator setpoint by measured endpoint error. Use retained
command/endpoint pairs and direction history. Do not treat either hypothesis as
calibrated. Test quantization, deadband and variable offset, including cases where
a changed command produces no changed report. Score signed error, convergence,
attempts and failures; never select only successful runs.

### 2. Specify a separate single-micro-command experiment

Keep the current native admission unchanged. Before adding any alternate live
path, define exact allowed command-space increments (candidate: 0.05 and 0.10
degrees), starting-pose envelope, speed/acceleration, one-use dispatch, maximum
observed excursion, fresh baseline and endpoint/hold evidence. Initially permit
one command per experiment, not the simulated three-attempt loop. Preserve
original request/response bytes, prior actuator setpoint, reported baseline,
direction, raw tR, timing, endpoint and hold outcome in each export. Raw tR units
remain unverified; do not use it to set a control gain.

### 3. Validate implementation before dispatch

Tests must cover serialization units, distinct admission identity, wrong pose,
stale baseline, failed send, no response, overshoot, no progress, other-joint
movement, cancellation, duplicate execution and export failure. No retries or
automatic returns. Proposed command is not proof of motion; endpoint feedback
is not independent end-effector metrology.

### 4. Single-step commissioning, then reassess

Only after that separate path is reviewed should a bounded live micro-command
be tried through the wizard. Reconstruct the endpoint from original feedback
and collect the existing full passive hold before judging it. Stop on failure;
do not loosen tolerance to declare improvement. A new command must have a fresh
baseline and its own admission. Enable a finite correction sequence only after
single-step response is understood sufficiently and independent held-out tests
support the strategy. Do not automatically enable other joints or board contact.

## Reproduce offline

```powershell
.venv\Scripts\python.exe software/scripts/simulate_micro_correction.py
.venv\Scripts\python.exe -m pytest software/tests/unit/test_micro_correction_simulator.py software/tests/unit/test_endpoint_correction_simulation.py -q
```

`--output <new-path>` saves a new synthetic JSON report and refuses overwrite.
Neither simulator imports a hardware sender or consumes a live admission.
