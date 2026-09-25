# Retained-telemetry baseline analysis

This is offline reanalysis of an actual zero-write capture, not a new live run.
No movement was commanded. No speed setting has been optimized or selected.

## Source and coverage

- Capture operation: `operation-531fb7e94a254e3ca988eec2394af57c` on COM7.
- Export: `software/runs/wizard-exports/wizard-20260912T230532370345Z-b8bf9b50fbe14fe9b4f4390340712601`.
- Native stdout SHA was checked before extracting capture bytes; extracted byte
  count and SHA were independently checked before analysis.
- Capture: 56,320 bytes; SHA
  `3e500d6fca141fcf90d28b9862ac99de35cd7fe0ac7d98cc507d2401cf95422a`.
- 256 parsed records: one rejected leading line and 255 complete pose samples.
- Offsets 53,098–56,320 remain retained but unparsed due to the record cap.
- Original public operation remains FAILED (IPC structure limit); the later
  representation fix and offline reanalysis do not rewrite that original result.

## Observed pose variation

Every parsed complete sample has the same values in all ten core pose fields.
Peak-to-peak spread and population standard deviation are zero **in the reported
values**. Do not interpret that as zero physical error, accuracy or a permissible
motion tolerance. Steady pose, quantization and cached/buffered telemetry are not
distinguished by these records alone.

| Field | Reported value | Unit |
|---|---:|---|
| x | 345.3562001 | mm |
| y | -5.298113331 | mm |
| z | 210.3949988 | mm |
| tit | 0.036815539 | rad |
| b | -0.015339808 | rad |
| s | 0 | rad |
| e | 1.61528177 | rad |
| t | -0.007669904 | rad |
| r | -0.003067962 | rad |
| g | 3.149262558 | rad |

These are robot-reported coordinates, not independently calibrated board/tool
coordinates. Loads tB/tS/tE/tT/tR are present in every complete sample. Voltage,
gripper load and torque-switch fields are absent throughout and remain unknown.

## What this cannot measure

The capture lacks per-read/device timestamps and a commanded target. It cannot
establish true sample cadence, command latency, settling, tracking error, overshoot,
freshness or physical repeatability. In particular, dividing 255 by five seconds
would misrepresent frame cadence because parsing was capped and input may be buffered.

## Software evidence and next action

Added pure `rocell.arm.telemetry_baseline.analyze_pose_variation`, which derives
statistics from original bytes and reports rejected/incomplete/unparsed coverage,
optional-field presence and limitations. No device-opening capability.

Tests: **22 passed in 0.46 seconds**, baseline analysis and stream framing,
basetemp `pytest-pose-baseline-20260912-01`. Covers known variation, constant
readings, empty/single samples, partial input, record limits and numeric overflow.

Next: add bounded per-read host timestamps to capture and validate their relation
to frame offsets. Confirm the corrected public capture path, then qualify one
small slow move with an operator and safe swept volume. Check that pose telemetry
responds to that movement before collecting a pose/speed matrix. No automatic
motion or firmware-setting changes follow from this baseline.
