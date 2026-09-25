# Revision 3 installation result — 2026-09-18

The user explicitly approved the app-only installation and one USB-only startup.
Deployment completed successfully; no baseline request, movement, provisioning,
servo-configuration change or motor-power restoration was performed.

## Verified execution

- COM7 CP210x identity matched the expected USB instance; controller MAC verified
  as `fc:e8:c0:f8:d5:38` before writing.
- Installed predecessor bytes matched the expected r2 application device digest.
  Partition table and filesystem matched the reviewed backup.
- Wrote 1,076,384 app bytes at `0x10000`, with no automatic write retry.
- Vendor write verification and independent full app readback passed.
- Readback SHA-256: `46e23efb7f9f18557882b1b185ecf4874ba4b2123ef64867f3a2831c56e01ee1`.
- All regions outside app0 matched their prewrite digests before startup.
  Ordinary startup may subsequently change NVS; this is not a claim of an
  entirely read-only application boot.
- One deliberate startup reset was sent after verification. Process exited 0.
- No rollback occurred; r2 binary and original private backup evidence remain.

## Passive startup and export

Status at `192.168.0.225` was identical before/after collection:

- Schema `rocell.diagnostic_transport.v3`.
- Boot ID `ed6197256410da0aefaa1a9bf3a926cd`.
- `IDLE`, `NOT_CONFIGURED`, zero records, storage fault false.
- `start_supported=true` is protocol capability, not authorization/readiness.

Verified export:
`software/runs/wizard-exports/wizard-20260918T143341527603Z-51103c5aa83a43dcacc5e47b6d19c358`.
Includes deployment events and raw status responses; no backup/credential data.
Host export integrity passed. The controller's `durable_export_verified=false`
field is separate from that host result. HTTP is not authenticated attestation.

## What remains

The baseline scan capability is installed but has not been invoked or hardware
validated. Status describes the motion runtime, not a scan result. Reverse-motion
ambiguity, live endpoint assessment and physical tip accuracy remain unresolved.

Before powered acquisition: inspect/support the arm after the reported drop and
review safe servo power-up. Do not rely on the base clamp to hold articulated
links or restore power just to lift the arm. Keep the current USB-only setup until
that physical step is agreed. A subsequent baseline-only scan requires no motion
policy/key and sends only servo read requests; it consumes the baseline session
claim. It does not authorize motion or make the earlier pose valid again.
