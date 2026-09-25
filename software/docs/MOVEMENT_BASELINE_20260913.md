# Live zero-command baseline — 2026-09-13

The operator freshly confirmed clear, secured and correctly powered setup and
requested continuation. Public physical wizard actions performed inventory,
exact controller selection, native metadata correlation, setup recording and
one zero-command powered telemetry capture. No motion command was sent.

- Controller: CP210x 10c4:ea60, serial 52E4E1E8337FEF119E92181CEDD322A4, COM7.
- Session: wizard-a73d7abcbf5e4d67bd09882be21471cf.
- Capture operation: operation-54741561a39948669aa45caa7affbe9d.
- Capture time: approximately 13:25:30–13:25:37 UTC.
- Result: UNSOLICITED_TELEMETRY_CAPTURED; observation window complete; no errors.
- Confirmed command bytes: **0**. Serial cleanup and process-tree exit confirmed.
- Export: `software/runs/wizard-exports/wizard-20260913T132537905277Z-ccb8276b0ac14eb5ba17ea6368339788`.
- Verified manifest SHA-256: `1070df9a4d15788f505684725a78d712b82479df59f67a7c1c9515a2de6658f1`.
- Raw capture SHA-256: `42c2110bcb4cf5288c8596703d735f9a0e6fdeb1e720d08228f20821b3acb346`.

## Full-window reanalysis

Retained 56,000 bytes; 55,933 bytes accounted for as complete lines. There were
270 complete pose records, one rejected line at the possible partial prefix
(bytes 0–43), and a 67-byte unterminated suffix (bytes 55,933–56,000).
The compact original UI count of 255 was not used as the full analysis count.

All 270 reported poses had identical XYZ, pitch, roll and gripper fields:

| Field | Reported value |
| --- | ---: |
| x (mm) | 345.3513288 |
| y (mm) | -3.178663578 |
| z (mm) | 210.1326353 |
| pitch (rad) | 0.03834952 |
| roll (rad) | -0.003067962 |
| gripper (rad) | 3.149262558 |

This demonstrates stable *reported* values during acquisition, not calibrated
physical accuracy, independent sample freshness or response to a command.
Voltage and torque-switch fields were absent; their states remain unknown.

## Next integration issue

The live stream began and ended mid-frame. The current endpoint admission
correctly refuses invalid baseline records and an unframed suffix. Do not pass
this raw capture to it as a clean baseline, drop bytes silently, claim the
partial fragments are complete frames, or weaken its checks just to move.
Frame-aware bounded capture preparation needs to retain boundary fragments
explicitly while establishing a separately identified complete-frame interval.
Actual motion also still requires the real request-bound engineering reviews.
No small move or continuous-motion campaign is qualified by this capture.

## Frame-boundary fix and second live validation

The boundary issue above is now addressed in software. A bounded complete-frame
interval is derived without modifying the retained raw capture. Recognized
leading/trailing fragments are separately identified as unobserved; interior
malformed records, arbitrary garbage and timing violations still fail checks.
Read timestamps are preserved. Endpoint admission, offline endpoint analysis
and native-result verification use the same derivation. Continuous-motion
analysis retains its stricter existing coverage requirements.

A second public-wizard zero-command capture ran approximately 13:31:58–13:32:05
UTC. It completed with confirmed serial cleanup/process exit and no reported
errors. **Confirmed command bytes: 0.**

- Capture operation: `operation-03911a4f8c7544258b1c8fd9fb2073fd`.
- Export: `software/runs/wizard-exports/wizard-20260913T133206239050Z-278298bed3e041de8f0cb930e0c15efd`.
- Manifest SHA-256: `feb3179afadd9c2772f38c6c8e764df9475bc64f10fd577bee011a90cb7f71bc`.
- Original capture: 55,936 bytes; SHA-256 `97132111bfceb59fa65b144f8d654c0bd920803ee64b7899eabedd2444f5827a`.
- Complete-frame interval: `[85, 55768)`; SHA-256 `8d598f7c7bbd6705d80fd5a4fab3d286bf6fdb9a107a921cb58f4e3b670741f7`.
- Unobserved boundary ranges: `[0, 85)` and `[55768, 55936)`.
- Reanalysis with the updated code: **269 complete pose records, zero rejected
  lines within the selected interval**. All original bytes remain retained.

The new capture exposed a numeric-token leading fragment, which was added to
the narrowly bounded recognition logic and tested against the saved original
bytes without another serial open. Boundary fragments are not certified valid
telemetry, and this does not establish independent sample freshness.

Verified regression checkpoints: 280 combined endpoint/campaign tests passed
before the numeric-token refinement; 34 targeted tests passed afterward.
The final combined run was launched, but its terminal result was not retained
in the available tool session, so no final combined pass count is claimed here.

### Next physical-stage work

The framing issue is resolved, but no software-commanded movement occurred in
these captures. Finish the real host evidence binding and request-bound reviews
for one small, slow, noncontact endpoint trial. Then acquire the trial through
the supervised one-shot executor, retain command/telemetry/cleanup evidence,
and evaluate it before separately testing a return, repetitions or higher
speeds. Do not substitute synthetic test evidence for these live records.
