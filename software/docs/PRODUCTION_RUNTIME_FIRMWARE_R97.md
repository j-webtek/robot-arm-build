# Production runtime firmware candidate r97

r97 is the first controller-side implementation of the production runtime
contract. It is an **offline compiled candidate**, not an installed or qualified
controller application.

## Narrow runtime surface

The sketch starts the host serial port and servo-bus serial port, emits a
read-only runtime attestation, and then waits. Startup performs no servo write,
feedback read, torque change, filesystem access, settings change, Wi-Fi setup,
mission playback, retry, or movement.

Only two canonical input lines are accepted:

- exact compact ordered `T=102` all-joint commands;
- exact `{"T":105}` feedback requests.

A valid `T=102` produces exactly one seven-servo group-write call and a canonical
`T=1021,status=ACCEPTED_ONCE,ordinal=N` response. The host must consume the exact
pending ordinal before sending another command or requesting feedback; this
receipt is not proof of physical arrival. A `T=105` reads every servo once and returns a bounded
`T=1051` line containing `b,s,e,t,r,g`. Any malformed, overlong, noncanonical,
unsupported, or failed-feedback input enters terminal lock. There is no retry,
replay, alternate dispatcher, HTTP path, or single-servo command path in the
sketch.

## Identity and bindings

The startup attestation computes the running application digest using the ESP
partition API. It also reports the source hashes of the host T=102 encoder and
joint-mapping module used when r97 was staged.

The configuration epoch is deliberately reported as `null`. r97 must not be
installed or used physically until an independently reviewed installed session
binds its measured calibration/configuration epoch. This is an explicit blocker,
not a default calibration.

## Reproducible offline result

- App SHA-256: `7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d`
- App size: 314,640 bytes (partition limit 1,310,720 bytes)
- Compile profile: `default-4mb-no-psram`
- Compile export: `wizard-20260926T173219601251Z-d485be98eea84923b79039bc01b7dbe4`
- Source review status: first-party checks passed; independent review pending
- Installation/startup/movement: none

Stage and review with:

```powershell
$env:PYTHONPATH='software/src;software/scripts'
python software/scripts/stage_r97_production_runtime.py
python software/scripts/compile_diagnostic_reference.py configured-diagnostic-candidate-r97 --profile default-4mb-no-psram
python software/scripts/review_r97_production_runtime.py
```

Compilation is offline only. None of these commands uploads firmware or opens a
controller port.
