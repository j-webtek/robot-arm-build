# Micro commissioning readiness — 2026-09-17

## Completed without movement

- Launched an isolated physical-mode wizard; inspected the Arm page in the browser.
- Confirmed the live micro card states at most two commands, no repositioning,
  retry or return, two passive holds and automatic exports.
- Left the exclusive-controller declaration unchecked. Clicking Preview action
  produced the required-checkbox validation message, not an execution ticket.
  Accepted-preview rendering and live execution remain untested in the browser.
- Closed the temporary tab and stopped its server after inspection.
- Queried the actual arm over Wi-Fi; no serial port was opened or motion sent.

## Network observation and recovery

The initial diagnostic stopped at IDENTITY_BEFORE / IDENTITY_NOT_MATCHED with
zero HTTP connections and zero request attempts. Windows had no matching neighbor
entry. A single ICMP ping to 192.168.0.225 succeeded (39 ms), after which Windows
reported FC-E8-C0-F8-D5-38 as reachable. A separate read-only diagnostic succeeded
with the pinned MAC matched before and after the HTTP response (173.264 ms).

This is consistent with an empty neighbor cache, not evidence of firmware failure.
No identity guard was bypassed. Do not automatically retry movement on this error.
For future onboarding, distinguish missing neighbor evidence from an actual MAC
mismatch; resolve/recheck identity before attempting any arm command.

## Stationary feedback test

The existing bounded observation completed for 35.001932 seconds:

- 116 successful original responses; response span 34.837580 seconds.
- Maximum response gap 478.163 ms, within the provisional 1,000 ms allowance.
- All six reported joint values identical throughout the observation.
- Wrist roll 0.021475731 radians, approximately 1.230468748 degrees.
- Zero motion commands; no calibration or compensation settings changed.
- Export manifest and retained attachment hashes verified successfully.

These are controller reports and stationary transport results, not independent
physical-tip accuracy or proof of successful movement.

## Retained workspace exports

Under `software/runs/wizard-exports/`:

1. Initial identity refusal: `wizard-20260917T113730987468Z-11a95b2fd8c344f2bd0dbc18da9230f8`.
2. Successful single query: `wizard-20260917T113746941096Z-b225e182ea2a47dc817a2d040f75c5e7`.
3. Verified bounded observation: `wizard-20260917T113833135942Z-517ebd42bb1f42ccbe5a138d1c707e66`.

## Next physical sequence

1. Obtain fresh feedback and use the existing separate bounded positioning action
   to command roll 2.5 degrees only if its current admission checks pass. From
   the observed 1.23047 degrees this is about 1.26953 degrees, inside the existing
   >0.5 and <=1.5-degree single-step envelope. This is a planned move, not sent.
2. Verify endpoint and passive hold, exporting the original evidence. Do not
   proceed after a failed move/hold or use today's observation as fresh admission.
3. Inspect the accepted micro-action preview under an actual exclusive-controller
   declaration, then execute the descending 0.95-degree predecessor if admissible.
4. If it already reports within 1.25 +/-0.05 degrees, accept NO_CORRECTION_NEEDED.
   Only the defined 1.35–1.45-degree result permits the optional 0.90-degree command.
5. Review final classification and exported originals; no repeated attempts merely
   to manufacture an out-of-band result, and no global compensation promotion.
