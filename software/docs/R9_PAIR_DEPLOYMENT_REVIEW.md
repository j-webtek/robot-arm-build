# R9 held-elbow pair candidate: offline review

Status: offline artifact/recovery checks passed; **not installed or authorized for deployment**.

## Verified local evidence

- Review export: `wizard-20260919T011856526245Z-9632e510ffd44a5eaee57787344f35e1`.
- Build export: `wizard-20260919T010713961695Z-58d0552f91cd48da8d66d2c3097fb042`.
- Application SHA-256: `2af941a662a36f711f9571e34c3ab48b44bb0c2247bab797381c1814e75d3da9`.
- Application size: 1,104,112 bytes; app0 offset `0x10000`, slot `0x140000`, remaining 206,608 bytes.
- Candidate sources and all recorded binary hashes still match the saved compile report.
- Partition and bootloader artifacts match the previously reviewed default-4MB profile. This does not authorize writing either artifact.
- Both original 4MB backup files remain identical with SHA-256 `d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9`.
- Original app0 recovery bytes exactly match that backup's app0 region. Retained r7 app hash is verified.
- Diagnostic startup uses `LittleFS.begin(false)` and the hold/pair owner scheduler, not legacy command initialization.

The review reads files and disassembles the local ELF only. It never opens serial/network, decrypts private filesystem images, reserves a deployment attempt, writes flash or starts the arm.

## Resource findings and limits

The disassembly review includes optimized mangled symbols and found 71 relevant frames. The largest individual frame is 3,808 bytes in the prepare path; the pair-settings parser has a 1,328-byte frame. Individual frames do **not** bound total nested stack use. A regression test now prevents the optimized-symbol omission found in the first audit.

The linker reports 68,896 bytes of globals. Runtime free heap, largest free block, complete stack high-water mark and live bus/network timing are not yet measured. The capability endpoint can report heap metrics, but does not attest a firmware hash or prove resource sufficiency. ELF-to-app linkage has not been independently reconstructed beyond the saved build evidence.

No current device flash content or current power/support state was checked in this review. Saved evidence is historical, not a live-device verification.

## Remaining steps before a deployment request

1. Review nested prepare-path stack use and reduce stack-resident scratch buffers or add appropriate measurements if needed.
2. Extend the reviewed installer for this exact r7-to-r9 app-only transition; the existing installer currently rejects revision 9. Test its offline preflight and failure paths without opening hardware.
3. Verify the latest provisioned filesystem reference and protected-region expectations through saved provisioning evidence. Do not substitute the original pre-provisioning backup as current filesystem state.
4. Finish the explicit trial admission/UI flow. Offline review is available; live pair execution is not yet exposed in the wizard.
5. Present a separate approval request for the exact application image and one diagnostic startup. A powered movement trial and pair-settings provisioning are separate scopes.

## Proposed installation scope, not an executable authorization

If separately approved: support the arm mechanically before power removal (it previously fell when torque disappeared), disconnect external servo power, retain USB, and use the reviewed one-use app-only installer. Write only the reviewed application at `0x10000`; preserve bootloader, partition table, NVS and filesystem. Readback/verification failure stops without automatic retry or recovery.

One separately approved startup should only establish diagnostic connectivity/capabilities. Do not issue hold/pair challenge or motion commands as part of startup verification. This work has not provisioned the new pair settings file; missing settings fail closed, with no fallback motion configuration.

After successful separately approved provisioning and a powered trial: create fresh same-boot hold evidence, export it, then run the bounded forward/return workflow. Old boot receipts, hold handoffs and consumed nonces are not reusable.
