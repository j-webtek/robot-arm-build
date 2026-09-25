# System-freeze archive and transaction policy

This directory is append-only provenance for synchronized RC03/software
re-freezes. It does not authorize hardware, motion, or contact.

- `ROCELL-PHASE0-...-FREEZE-NNN/` retains the exact six active provenance
  aliases superseded by the next freeze: system manifest, camera manifest,
  simulation hardware profile, gate projection, simulation bundle lock, and
  calibration registry.
- `transactions/` records the old/new aliases, every RC03 source-hash
  transition, reason, approval reference, tool/input/output hashes, package
  preflight state, and prospective alignment result.
- Existing archive or transaction bytes must never be overwritten. A mismatch
  is a release-process error.

The Freeze-004 archive was restored after the first Freeze-005 transaction
audit because append-only archival did not yet exist when that transition was
applied. Its transaction explicitly records this reconstruction and leaves the
unknown original apply-tool hash as `null`; it does not present reconstructed
evidence as an originally captured transaction.

Use the dry-run, reviewed-plan, apply, validation, and interruption-recovery
procedure in [`BUILD_ALIGNMENT_FREEZE.md`](../../BUILD_ALIGNMENT_FREEZE.md).
