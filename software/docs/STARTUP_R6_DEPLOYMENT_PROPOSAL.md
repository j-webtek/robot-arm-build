# Startup diagnostics r6: app-only deployment proposal

Status: r6 installed and readback verified on 2026-09-18 after explicit app-only
approval and user confirmation of supported links, external power disconnected,
and USB-only power. Provisioning, servo-configuration changes and motion were
not included or performed. Keep the arm supported and USB-only for now.

## Completed deployment evidence

- Local preflight verified the exact image, retained r3 predecessor, both matching
  full backups and original recovery slot. COM7 enumerated the expected CP210x.
- Live prewrite checks matched controller MAC, security/flash identity, installed
  r3, partition table and retained filesystem snapshot.
- One app write completed. Full application readback matched r6 exactly; both
  protected flash ranges were unchanged. One startup reset was sent. No retries.
- Journal: `software/private-backups/controller-20260918-session1/app-r6-deployment-events.jsonl`.
  This consumed journal must not be overwritten or automatically resumed.
- Verified deployment export: `wizard-20260918T155337255349Z-a811a3cc7e9d486ebe811b700b839cda`.
- Two bounded read-only status GETs returned stable `IDLE / NOT_CONFIGURED`,
  zero records, no storage fault, boot instance `a92f8d4a46620f79609b26383134746e`.
- Verified/replayed status export: `wizard-20260918T155337593408Z-591d8b1edf354f3ab6ff0008cc52afd8`.

The application endpoint responds, but movement commissioning is NOT complete.
`start_supported` reports firmware capability, not an enabled/provisioned motion
path. No baseline POST, start token, policy/key write or servo command was sent.
The pending step is separately reviewed and approved startup provisioning.

## Purpose

Support the observed zero-goal/nonzero-position startup condition without treating
zero target registers as actual positions. The startup path authenticates one
bounded elbow command, obtains two stationary position scans and direct mode/
torque readback, binds a position-relative target, then captures strict post-write
target/position evidence. Normal arrival criteria are not relaxed.

## Exact proposed write

- Controller: RoArm-M3 Pro, MAC `FC:E8:C0:F8:D5:38`; verify identity/port again.
- App: `software/.firmware-tools/build-configured-diagnostic-candidate-r6--default-4mb-no-psram/RoArm-M3_example.ino.bin`.
- SHA-256: `71447b72f1488954ece0f6e9d95ca6ec3fc14b45982a10d65a96d3caa3691526`.
- Length: 1,081,872 bytes; app0 offset `0x10000`, slot size `0x140000`.
- Sector erase range: `0x10000` through `0x118fff`; exclusive end `0x119000`.
- Require installed r3 readback to match SHA-256
  `46e23efb7f9f18557882b1b185ecf4874ba4b2123ef64867f3a2831c56e01ee1`
  over its 1,076,384-byte image before overwrite. Retain r3 and original backups.
- Preserve bootloader, partition table, OTA data, app1, NVS and LittleFS during
  flashing. Verify outside-app0 preservation before application startup; ordinary
  Wi-Fi startup may subsequently update NVS internally.
- Verify full new application readback, then one deliberate USB-only startup and
  passive diagnostic status. Export results. No retries, chip erase or automatic
  recovery/reversion on an uncertain result.

The installer now has an explicit r6-to-r3 predecessor binding and a distinct
`app-r6-deployment-events.jsonl` journal. It rejects an existing journal and must
never overwrite or automatically resume one. Existing r2/r3 journals remain
untouched. It flashes the exact hash-checked bytes held in memory, not a later
reopening of the image path. This implementation is not approval to execute it.

Offline preflight (safe local reads only):

```powershell
.\.venv\Scripts\python.exe software/scripts/deploy_reviewed_diagnostic_app.py --revision 6 --preflight-only
```

Executed preflight verified r6, the retained r3 predecessor, both matching full
backup images and the original app0 recovery slot. It reserved no journal and
performed no hardware access. Five offline tests passed: exact revision/edge,
separate journal, content tampering/path replacement, incorrect length, existing
journal rejection and preflight isolation from serial/esptool imports. Hardware
prewrite identity checks still occur only in a separately approved deployment.

## Physical setup before an approved installation

Support all articulated links BEFORE removing holding/motor power. The arm
previously dropped when main power was unplugged; a base clamp alone is not link
support. Do not unplug power now merely because this document exists. After
approval and support confirmation, use USB-only controller power for flashing and
startup. Motor-power restoration and movement remain separate steps.

## Explicit exclusions

No startup policy or key is generated/provisioned by this installation. No torque,
servo mode, ID, persistent servo configuration or calibration is changed. No
baseline POST, start token or movement command is included. No camera, physical
contact or stylus-tip accuracy claims are included.

The candidate reads separate `/rocell-startup.json` and `/rocell-startup.key`
files; missing configuration fails closed. Existing normal-mode files are not
fallbacks. Baseline and motion share a one-use boot claim. App installation alone
does not make the full movement workflow operational.

## Evidence

- Compile export: `wizard-20260918T151815541742Z-e59178a1371b488fbfca4dd48490450d`.
- Offline artifact/stack review: `wizard-20260918T151839636777Z-fd23358c4a1247d88c0d2a59f64e0b60`.
- App fits the reviewed 4 MB/no-PSRAM partition profile. Partition digest:
  `148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1`.
- Compiler: 1,075,301 program bytes, 60,400 static RAM bytes. r4 failed static DRAM;
  r5 moved one bounded runtime object to fail-closed heap allocation; r6 moved a
  4 KiB parser scratch buffer off the loop stack.
- Compiled configuration-parser frame is 1,040 bytes, down from r5's 5,152.
  This is not a worst-case call-chain proof or measured live stack/heap headroom.
- Focused host regression suite: 43 passed. Real signed bytes, native parser and
  pinned conversion pass through scripted socket/runtime and simulated servo bus.
  Short acceptance, disconnect, trailing bytes and allocation failure stop without
  servo activity. Arrival/non-arrival/fault exports replay independently.

## After this installation, separately

Review exact startup provisioning schema, matching validator and filesystem paths;
obtain provisioning approval. Initial live request must use fresh positions and
bounded windows, not historical scans as current proof. Verify direct mode/torque
state without silently enabling torque. A mismatch stops before dispatch.

Complete wizard controls and retained transport-failure reporting. Validate one
bounded live command and endpoint before reverse/cycles. No routine visual proof
is required when valid software evidence suffices, but inconclusive evidence must
not be upgraded to arrival.
