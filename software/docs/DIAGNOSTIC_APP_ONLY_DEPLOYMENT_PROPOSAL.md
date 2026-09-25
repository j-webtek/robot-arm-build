# Stage 1 proposal: diagnostic application and USB-only startup

Execution checkpoint: approved installation, independent readback verification,
one startup and read-only HTTP status collection succeeded. See
`DIAGNOSTIC_APP_DEPLOYMENT_RESULT_20260918.md` for evidence and verified export.
The proposal below preserves the approved scope; it is not an instruction to
repeat installation. Policy/key provisioning and motion remain separate stages.

Status: user explicitly approved installation of the reviewed application image.
The approved proposal includes verification and one USB-only startup. Execution
results are recorded separately; approval is not evidence that deployment succeeded.
No provisioning, servo changes or motion are authorized by this approval.

## Purpose and scope

Replace only the application to establish the diagnostic service on actual hardware.
Then perform one deliberate application boot with external motor power disconnected
and the arm supported. Validate status/discovery and export the results. This is a
stage of the full command-to-motion plan, not completion of it or proof of movement.
No policy/key provisioning, servo commands, contact tests or motion are included.

## Evidence reviewed

- Controller MAC FC:E8:C0:F8:D5:38; ESP32-D0WD-V3 revision 3.1; flash 4 MB.
- Targeted read-only getters report secure boot disabled and flash encryption
  disabled. No key material was read and no eFuses were written.
- Two uninterrupted full-flash reads match SHA-256
  `d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9`.
- Installed bootloader/app image checksums and appended hashes are valid. Saved
  OTA metadata is consistent with app0 at 0x10000 under standard IDF selection.
- Candidate partition binary exactly matches installed dual-OTA layout. Candidate
  does not depend on PSRAM. Runtime heap/stack behavior is not yet verified.
- Offline LittleFS mount succeeds; stored Wi-Fi fields are structurally usable.
  Diagnostic policy and key are absent. They must stay absent for this stage.
- Build export: `wizard-20260918T121159084880Z-c4061a611eba4557a6732828f0dbaf2e`.
  Backup export: `wizard-20260918T123027416050Z-c1136b3b46ee40d086d924ace37e6fe5`.

## Exact proposed persistent write

Only write the following application at **0x10000**:

`software/.firmware-tools/build-configured-diagnostic-candidate-r2--default-4mb-no-psram/RoArm-M3_example.ino.bin`

- Length: 1,072,832 bytes; slot size 1,310,720 bytes.
- SHA-256: `5d1e081a1b33ddf9eb85a248112c6d18484e04417a1b87042f805875414ba481`.
- Flash erase is sector-granular: affected app sectors 0x10000 through 0x115fff
  (exclusive upper bound 0x116000). Entire range is inside app0.
- Use pinned esptool 4.6, COM7 after PnP/MAC recheck, 115200 baud and bounded
  connection attempts. Preserve flash parameters; no chip erase or merged image.
- Do not write bootloader, partition table, OTA data, app1, NVS or filesystem.
  Normal application/Wi-Fi startup may update NVS internally; this is distinct
  from our flash write list and cannot be represented as a no-state-change boot.

## Verification and first startup

1. Recheck candidate/recovery hashes, private backup files and controller identity.
   Keep motor power disconnected; do not restore it during this stage.
2. Write only the approved app range, leave loader active, and verify device flash
   against the approved app image. Stop on uncertainty/error; no automatic retry.
3. Following successful verification, perform the one application restart included
   in this proposed scope. No general-purpose legacy initialization or motion route
   is present in diagnostic setup/loop. Physical startup behavior is still unproven.
4. Obtain read-only diagnostic status on the existing network. Confirm boot identity,
   bounded records and no servo dispatch. Do not mistake advertised protocol
   capability for permission/readiness to move. Do not invoke a start POST.
5. Export and replay the startup evidence. If Wi-Fi/mount/status fails, stop and
   investigate; do not format, provision, restore firmware, reset repeatedly or
   enable a fallback motion interface automatically.

## Recovery prepared, not exercised

Private original full app0 slot:
`software/private-backups/controller-20260918-session1/original-app0-slot.bin`.
Offset 0x10000; length 1,310,720 bytes; SHA-256
`50dbba429355156d0bbd77e603a777ed2d2a289a21a00f6df042ae6fc5bfbf6b`.
This artifact was derived from the matching pair, fsynced and reread byte-for-byte.
An app-only rollback would restore this slot and verify it, preserving other
partitions. Restoration is NOT tested and NOT automatically authorized: present
the failure and request rollback approval. Full backups are also retained; never
blindly restore a whole flash image or overwrite newer configuration.

## User decision requested

Authorize the exact app-only write above, verification, and one USB-only startup
with external motor power disconnected. This temporarily replaces the stock arm
application; legacy control interfaces will be unavailable. Existing filesystem
content is preserved. It does not authorize policy/key provisioning, servo settings,
motor-power restoration or movement. Those remain subsequent reviewed stages.
