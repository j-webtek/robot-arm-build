# Diagnostic application deployment result — 2026-09-18

## Outcome

The explicitly approved app-only installation and one USB-only startup completed.
The diagnostic HTTP service is reachable at `192.168.0.225`. No movement command,
challenge/start request, policy/key provisioning or servo-configuration change
was performed in this deployment stage. Reverse-motion diagnosis remains open.

## Installation evidence

- Controller MAC verified before writing: `fc:e8:c0:f8:d5:38`.
- App0 offset `0x10000`; image length 1,072,832 bytes.
- Installed SHA-256: `5d1e081a1b33ddf9eb85a248112c6d18484e04417a1b87042f805875414ba481`.
- Vendor write verification and independent full-image readback passed; readback
  matched the approved bytes and SHA-256 exactly.
- Pre/post-write hashes of all flash outside app0 matched before startup.
  This does not assert that ordinary Wi-Fi startup cannot subsequently update NVS.
- One deliberate startup reset was sent after verification. No automatic retry,
  reflashing or rollback occurred. Recovery backup remains available but restore
  has not been exercised.

## Read-only startup evidence

Bounded status collection returned identical before/after status:

- Schema: `rocell.diagnostic_transport.v3`.
- Boot instance: `b2a0cd929529da98a3b1db45024ec4a7`.
- State `IDLE`; reason `NOT_CONFIGURED`; records `0`; storage fault `false`.
- `start_supported=true` advertises protocol capability, not motion readiness.
- `durable_export_verified=false` is the controller field; the separate host
  export below passed its integrity verification.
- Windows neighbor entry for the IP matched the verified controller MAC.

HTTP status is not authenticated hardware attestation, a heap/stack endurance
test, servo feedback, or a physical-position measurement. No-record status and
the reviewed no-motion startup path do not constitute measured motion evidence.

## Reproducible export

`software/runs/wizard-exports/wizard-20260918T125536277135Z-264cb87f58d149c6991b792e1c98506a`

Contains deployment events, startup snapshot and both raw status responses.
`verify_export` returned `VERIFIED_DIAGNOSTIC_EXPORT`, valid true, no reasons.
Private flash backups and Wi-Fi credentials were not included.

## Next boundary

1. Prepare and review the exact bounded diagnostic policy and secret-key
   provisioning method, preserving existing filesystem content.
2. Obtain separate authorization for those persistent changes; this installation
   approval did not include provisioning or movement.
3. After provisioning and motor-power setup, collect a bounded command-correlated
   test: requested target, converted/transmitted target, write result, supported
   target readback and freshly acquired servo position.
4. Assess forward/reverse evidence before progressing to cycles and ghost keys.
   Stop on uncertain delivery, invalid feedback or export failure.

Keep external motor power disconnected during the current configuration stage,
with moving links mechanically supported. The user subsequently reported a drop
when unplugging motor power, with no damage reported. See
`POWER_LOSS_AND_PROVISIONING_CHECKPOINT.md`; prior pose assumptions are stale.
