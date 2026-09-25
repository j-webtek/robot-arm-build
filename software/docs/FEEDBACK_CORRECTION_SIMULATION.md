# Offline bounded feedback-correction experiment

Implemented in `software/src/rocell/arm/feedback_correction_simulation.py`.
Run without hardware:

```powershell
.\.venv\Scripts\python.exe software/scripts/simulate_feedback_correction.py
```

No network/serial sender, wizard live action, durable admission or physical command
is created. No existing live policy, candidate or calibration is changed.

## Evidence consolidation

`ROLL_150_MAPPING_EVIDENCE.json` separates initial arrival from final hold error
for the two held-out 1.50-degree lookup trials. Both exports were re-reviewed from
original responses. Initial values ranged from 1.406250023 to 1.494140602 degrees;
both holds ended at 1.406250023 degrees. These observed ranges are not confidence
intervals or guaranteed physical bounds. One trial had a late change; the other
was unchanged throughout its hold. Training probes are not counted as validation.

## Simulation policy

- Full 35-second modeled observation windows, feedback intervals no greater than
  one second; malformed, missing, stale or transport-fault evidence stops.
- Compare the entire hold against an explicitly supplied illustrative error band;
  a final in-band sample cannot erase earlier out-of-band readings.
- At most three hypothetical corrections, each followed by a new full hold.
- Propose `previous_command + clipped(desired - final_reported)` with adjustment
  magnitude capped at 0.10 degrees and absolute command within 3 degrees.
- Stop on no improvement, command limits, incomplete holds or correction budget.
- By default, consult the actual pure `DiscreteTransaction` constructor and reject
  proposals incompatible with existing live rules. This check is not admission.
- A separate `enforce_current_policy=False` branch is explicitly hypothetical and
  only feeds scripted observations; it has no path to a hardware sender.

The 0.05- and 0.10-degree bands are sensitivity examples, not approved requirements
and not changes to the existing 0.5-degree operational arrival tolerance. Band
compliance is different from an exactly unchanged hold. Neither proves Cartesian
accuracy. A finite observation cannot guarantee indefinite stability afterward.

## Results

28 focused tests passed across the new simulation, evidence reviewer and discrete
transaction. All nine scenario expectations passed:

| Scenario | Outcome |
| --- | --- |
| Current policy, stable residual | Correction rejected, zero simulated corrections |
| Current policy, late change | Correction rejected, zero simulated corrections |
| Hypothetical ideal unit response | 0.05-degree sustained band met after one correction |
| Hypothetical deadband | Stops after one correction with no improvement |
| Hypothetical worsening response | Stops after one correction with no improvement |
| Hypothetical feedback loss | Stops with transport fault |
| Illustrative 0.10-degree band | Observed alternatives fit without correction |
| Short hold | Rejected as incomplete |
| Out-of-band then returns | Requires more hold evidence; no premature success |

The ideal, deadband and worsening plant responses are scripted hypotheses, NOT
mechanical models learned from validation data. The measured endpoint alternatives
seed the scenarios; a uniform half-second sample cadence is synthetic, not a replay
of real timestamps. The script makes no claim that native correction will converge.

At reported 1.406250023 degrees, desired 1.50 degrees and previous command 1.25
degrees, the residual rule proposes approximately 1.343749977 degrees. This is
only about 0.062500045 degrees from the reported position, below the current
greater-than-0.5-degree minimum step. It also lies below the reported position
while the desired endpoint lies above it, conflicting with the current desired-
and-command same-side rule. Those rules remain intact; simply shrinking the
minimum-step limit would not resolve all policy and response-model questions.

## Next work

Update: actual-timestamp replay is now implemented; see
`SUSTAINED_BAND_REPLAY.md` for the two real held-out results, coverage semantics
and tests. The following paragraph records the rationale for that extension.

Use these tests to evaluate candidate control strategies offline, not to turn on
automatic correction. Next add a replay-based evaluator for user/task-selected
sustained error bands over actual timestamps, keeping band compliance distinct
from unchanged-hold and external accuracy. Report both 0.05 and 0.10-degree
sensitivity examples without selecting one as a task requirement. This provides
an evidence-based decision about whether corrections are needed before designing
a separately bounded small-step hardware protocol.

No physical movement occurred in this work. Last hardware report remains in the
previous live trial; future commands require a new baseline.
