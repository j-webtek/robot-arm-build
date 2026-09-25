# Hold-only r7: installation review, not deployment authorization

## Execution result — 2026-09-18

**Completed within approved scope.** User confirmed supported links, external
power disconnected and USB connected. Fresh local preflight and COM7 USB identity
matched; installer verified MAC, flash, r6 predecessor, partitions and provisioned
filesystem before its single app write. Full readback matched the reviewed r7
image, protected-region digests were unchanged, and exactly one application
startup reset was sent. Installer exited successfully.

A single status-only HTTP GET returned `rocell.hold_transport.v1`, state `IDLE`,
reason `NOT_CONFIGURED`, zero records, no storage fault, boot
`cb73246b081511962f682ed39f359919`. No challenge was requested. No provisioning,
torque engagement or movement command was performed. This confirms the status
route responds, not complete application/heap health or servo readiness.

Journal: `software/private-backups/controller-20260918-session1/app-r7-deployment-events.jsonl`
(consumed; no reuse). Verified public evidence export:
`wizard-20260918T191322958288Z-a8f1786858e441619438af6e01245a46`.
Earlier pending/approval text below is historical and superseded by this result.

## Current authorization update

The user has now explicitly approved this reviewed **r7 app-only installation and
one startup, without provisioning or movement**. The installation procedure below
remains unchanged. The pending prerequisite is confirmation of mechanically
supported links and USB-only power. No r7 deployment journal exists at this check;
no deployment or reset has been performed. The prior approval request language
below describes the review history, not a request for repeated authorization.

## What this changes

Installed r6 stopped before dispatch because its startup policy expected enabled
torque, while valid control-register reads reported torque disabled. Reconnecting
power does not resolve that recorded mismatch. r7 adds an elbow-only, fresh-position
hold path. It does not add forward/reverse movement or ghost typing yet.

The first hold write can engage torque and cause movement, even if its target
equals the fresh measured position. Treat installation, provisioning and a live
hold attempt as separate reviewed actions; none has occurred for r7.

## Exact candidate

- Source: `software/.firmware-tools/configured-diagnostic-candidate-r7/RoArm-M3_example`.
- Build profile: `default-4mb-no-psram` (ESP32, default 4 MB partitions).
- Application: `RoArm-M3_example.ino.bin`, 1,070,912 bytes.
- SHA-256: `380d7a69e0b456b25b4ae50e34f8d947724ca5c22db42d75958df509e2618c33`.
- App-only target: offset `0x10000`, slot size `0x140000`.
- Compile export: `wizard-20260918T174440380311Z-592ae9d2f2484a13b103cc8e8b954407`.
- Do not flash the merged image, bootloader or partition binary.

The candidate hash was rechecked locally on 2026-09-18. Startup establishes
stored STA networking and servo UART transport without servo initialization,
homing, torque writes, mission playback or legacy command ingress. Without
separate `/rocell-hold.json` and `/rocell-hold.key` provisioning, no hold listener
can be prepared. Existing startup files are not fallback configuration.

## Recovery evidence rechecked locally

Private directory: `software/private-backups/controller-20260918-session1`.
Do not copy these files into public diagnostic exports.

- Both original full-flash copies:
  `d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9`.
- Original app0 slot:
  `50dbba429355156d0bbd77e603a777ed2d2a289a21a00f6df042ae6fc5bfbf6b`.

These hashes confirm saved recovery bytes, not the current installed state.
Installation must freshly verify controller MAC, flash identity, predecessor
application and protected regions. No automatic rollback or reset retry.

## Deployment-tool issue found before use

**Resolved locally (2026-09-18):** the installer now has an explicit r6-to-r7
edge and a separate one-use r7 journal. For r7 only, it verifies the retained
provisioning-result export and decrypts the saved DPAPI filesystem image in
memory, verifies its SHA-256/size, and derives the prewrite digest. No filesystem
mount, key extraction or plaintext file is involved. Earlier upgrade edges keep
their original filesystem expectation. All installed app/partition/filesystem
checks and protected-region checks remain mandatory.

Eleven installer tests passed (0.65 s), including wrong retained evidence/image,
each prewrite mismatch, one-use journals and local-only preflight. Actual local
`--revision 7 --preflight-only` returned LOCAL_PREFLIGHT_VERIFIED with candidate
hash above, r6 predecessor `71447b72...691526` and filesystem
`567d3cc0f20b2a5843bf27c7aac069f0df18782234f8579fae48a73604e569c6`.
No hardware was opened and no deployment journal was reserved. Fresh installed
state verification is still required inside an explicitly approved deployment.

Historical issue and resolution rationale:

`deploy_reviewed_diagnostic_app.py` currently allows revisions 2, 3 and 6 only.
It also compares the filesystem with the original full-flash backup. The later
approved r6 provisioning changed that filesystem, so simply adding revision 7
would leave an incorrect prewrite expectation. Do not bypass that check.

The required implementation step was: resolve the exact successful provisioning receipt and
its retained filesystem image; bind the r6-to-r7 upgrade to that reviewed state,
test rejection of wrong predecessor/filesystem, and retain unchanged protected
region checks. Local preflight must remain free of serial access and journal
reservation. This is now implemented; explicit installation approval is next.

## Memory evidence and limits

Full link: 57,232 bytes static RAM; 1,064,341 bytes program usage. The linker
remainder is not measured free heap. Native tests independently fail the network
graph allocation, runtime/evidence allocation and listener startup: each remains
faulted with zero servo reads/writes, no accepted request, and no automatic rearm
when memory or listener availability returns. Four focused tests passed in
7.69 seconds. JSON/Wi-Fi allocation pressure and task stack headroom still need
runtime observation after an approved installation, before servo engagement.

## Physical sequence when installation is approved

1. Mechanically support the articulated links before removing external power.
   The arm previously dropped when motor power was removed; do not repeat that.
2. Confirm supported USB-only state for flashing. Opening serial/resetting the
   existing application can run its startup, so keep the area clear.
3. Perform one reviewed app-only write, exact readback and protected-region checks.
   Stop on any uncertainty; do not retry or restore automatically.
4. Perform only the reviewed startup reset and non-motion health inspection.
5. Separately review provisioning bytes/policy, hardware-origin collection and
   first hold authorization. Historical joint windows are not fresh clearance
   evidence. No keyboard/screen contact or physical accuracy claim.

Success of this phase means the correct hold-only application is installed and
healthy, not that holding, reverse movement or endpoint accuracy is proven.
