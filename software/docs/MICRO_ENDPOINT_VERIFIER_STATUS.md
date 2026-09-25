# Micro endpoint verifier: offline implementation

Implemented `arm/micro_endpoint.py` and `application/micro_endpoint_review.py`.
48 focused tests passed across the verifier, original-body replay, staged
admission and existing simulation tests. No arm movement or live-limit change.

## Decisions

The pure verifier checks every provided row for ordered host timestamps, finite
six-joint positions, maximum one-second feedback gaps (including receipt latency
and trailing silence), ten-second completion budget from dispatch, other-joint
drift <=0.10 degrees, and roll excursion <=0.25 degrees from baseline. Roll must
remain within +/-3 degrees. Baseline roll must be 1.35–1.45 degrees.

It requires at least two seconds of post-receipt feedback before declaring
reported settling, with the last three readings spanning >=200 ms and <=0.01
degrees of roll variation. Two seconds is provisional: it prevents a fast
three-packet prefix being treated as completed motion, but does not prove servo
execution or device-side freshness. The full passive hold remains required.

Settled captures are separately classified as in the illustrative +/-0.05-degree
desired band, improved but outside band, unchanged/subresolution, overshoot, or
not improved. None authorizes another command. Unchanged readings are not proof
that a physical move occurred. Physical tip accuracy remains unverified.

Late transport failure, cancellation, excursion or drift overrides apparent
settling. A receipt alone cannot establish arrival. Corrupted response originals,
length/hash mismatch or derived pose disagreement are rejected by the application
reviewer before evaluating positions. A failed request anywhere prevents arrival,
even if later successful feedback is supplied; recovery is not stitched into a pass.

## Remaining integration

These modules have no sender and do not consume live admissions. The caller must
bind baseline and dispatch/receipt timestamps to a real one-use transaction;
the verifier cannot establish those facts from caller-supplied values alone.
Next implement that transaction orchestration with injected fake transport and
durability failures, verifying exact command, send-boundary expiry, consumption,
polling deadlines, hold/export behavior and stop-without-retry. Only then compose
the reviewed native path and separate wizard action. Exclusive-controller
assumptions described in MICRO_ADMISSION_IMPLEMENTATION_STATUS.md still apply.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest software/tests/unit/test_micro_endpoint.py software/tests/unit/test_micro_endpoint_review.py software/tests/unit/test_micro_command_admission.py software/tests/unit/test_command_strategy_simulation.py software/tests/unit/test_micro_correction_simulator.py -q
```
