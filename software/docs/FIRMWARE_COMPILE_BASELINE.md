# Firmware compile baseline — no deployment

Completed 2026-09-18 UTC. This establishes a working local ESP32 toolchain and
reference source build, not installed firmware identity or hardware qualification.

## Results

| Target | Result | Verified export |
| --- | --- | --- |
| January reference plus candidate SCS response-ID/length check | Compiled; 1,205,725 program bytes, 48,208 static RAM bytes | `wizard-20260918T012035460657Z-2209cf8da8074ae882ca2aecb5dbec77` |
| Inert diagnostic template/atomic/serialization probe | ESP32 compile/link succeeded | `wizard-20260918T012100178445Z-2147d638cf4c4266a56d8206865e6061` |

The reference binary SHA256 is
`1635c79c24f7b25cd22c172d3d84f752410934a203065f5dd3cd2680f3894f25`.
The reference still has its original boot motion and configuration behavior and
does NOT contain the integrated diagnostic workflow. Do not upload it.
The inert probe retains a link reference to diagnostic code but does not invoke
it from setup/loop; no serial or servo startup is present.

## Toolchain and resolved dependency issue

Versions are recorded in `software/firmware/toolchain.lock.json`. Arduino CLI
1.5.1 was downloaded from the official release and verified against its published
SHA256. All toolchain/libraries/staging/build outputs live under workspace-local
`software/.firmware-tools`; no global Arduino installation was changed.

ESP32 core 3.0.7 and Huge APP/PSRAM-enabled compilation settings follow the
[Waveshare development guide](https://docs.waveshare.net/RoArm-M3/Secondary-Development/).
These compilation settings do not independently verify this board's hardware.

The first reference build failed because INA219_WE 1.4 renamed constants used in
the sketch. Selecting 1.3.8 fixed that build without editing the reference's power
monitor code. Other resolved versions: ArduinoJson 7.3.1, SSD1306 2.5.17, GFX 1.12.6,
BusIO 1.17.4, plus the hash-pinned guarded SCServo source.

The first probe command accidentally replaced ESP32's default `-MMD -c` flags;
restoring them alongside the diagnostic include path fixed its compile step.
The reproducible script preserves those flags explicitly.

## Repeat the work

Use workspace Python to run `software/scripts/prepare_reference_firmware_build.py`.
It stages only approved source files, never vendor binaries, and refuses to
overwrite differing files. Its generated input manifest records source hashes.
The Arduino YAML has this workstation's absolute workspace paths; other developers
must configure equivalent isolated paths before using it.

Then run:

```powershell
.\.venv\Scripts\python.exe software/scripts/compile_diagnostic_reference.py probe
.\.venv\Scripts\python.exe software/scripts/compile_diagnostic_reference.py reference
```

These scripts compile named targets and export build logs, compiler/library
inventory and artifact hashes. Neither accepts an upload action or serial port.
Generated binaries are review artifacts, not approved deployment packages.

## Next

Separate owner-handoff candidate now builds successfully. Its source generator is
`software/scripts/prepare_owner_firmware_candidate.py`; compile with
`software/scripts/compile_diagnostic_reference.py owner-candidate`.
The baseline is preserved. Candidate results and limitations are in
[SERVO_BUS_OWNERSHIP_REVIEW.md](SERVO_BUS_OWNERSHIP_REVIEW.md).
No command-correlated diagnostic endpoints have been integrated yet.

Integrate command receipt/conversion/write hooks, callback handoff and diagnostic
sampling in a separate candidate; preserve this baseline for comparison. Test the
full exported evidence path and failure handling, then review exact image identity,
boot behavior, backup/recovery and deployment authorization. No installed arm
accuracy, reverse-motion diagnosis, runtime stack margin or on-device concurrency
claim follows from these compile results.
