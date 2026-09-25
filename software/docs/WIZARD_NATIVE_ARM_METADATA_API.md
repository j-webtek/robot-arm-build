# Native arm metadata packet and correlation API

This slice connects the existing Windows CM metadata collector to the closed
wizard diagnostic subprocess. It does not connect to a serial port, establish
received RoArm model/firmware/boot evidence, construct `ReviewedControllerBinding`,
or release the physical backend. Status `METADATA_CORRELATED` means only that
the retained generic USB-unit/COM observation and a unique native USB-pair/COM
mapping agree. Native persistent interface/instance and driver fields are
observations, not authority for a later open.

## Pure APIs

Module: `rocell.application.wizard_native_arm_metadata`.

```python
decode_controller_snapshot(value, mode) -> ControllerMetadataSnapshot
correlate_native_arm_metadata(
    snapshot, generic_review, *, mode, session_id, source_sha256, operation_id
) -> dict
summarize_native_arm_metadata(report) -> dict
rehearse_native_arm_metadata_snapshot(scenario="nominal") -> dict
```

Decode accepts canonical-owned plain JSON/bytes or the exact typed snapshot,
reconstructs every original candidate/native field and rejects normalization
drift, unknown fields, duplicate JSON keys, origin substitution, malformed
timing and nonzero authority/effects. Incomplete collections remain evidence.
This new diagnostic uses a strict 10-second collector duration, 128 rows per
source, existing 2 MiB snapshot maximum, bounded strings/nodes/depth, and a
separate 768 KiB full correlation retention maximum. An overbudget report is
refused; no rows or bytes are silently truncated.

Correlation requires the actual current `WizardDeviceSelection.reviewed_candidate`
SERIAL document. It verifies the full original generic report and acknowledgment,
then retains the exact candidate/acknowledgment and original full-review/report
hashes without duplicating the old inventory. It retains the entire new snapshot
once. The caller owns source/launch/action freshness, independent original hashes,
Stop, logging/publication and dedicated full export retention.

The full report schema is `rocell.wizard_native_arm_metadata.v1`. Its self-hash
is SHA-256 over sorted compact ASCII JSON excluding `report_sha256`. The nested
snapshot hash uses the original snapshot's canonical bytes. Full reports include
the source/launch/operation/review binding, provenance, counts, fixed blockers,
limitations and zero-effect fields. `summarize_native_arm_metadata` recomputes
the comparison from retained inputs, including the full snapshot. Its structural
checks are not authentication of externally supplied original-review hashes;
the parent must independently bind those before presenting a current result.

The compact schema `rocell.wizard_native_arm_metadata_summary.v1` retains the
binding, report/snapshot digests, provenance, four counts, nine native-field
availability statuses, fixed blockers and four false authority flags. It never
contains native paths, COM locators or driver strings. Availability is
`OBSERVED`, `MISSING` or `NOT_VERIFIED`. `HELD` means at least one fixed blocker;
`METADATA_CORRELATED` requires exactly one generic/native match and all nine
native fields observed. Both statuses leave model, firmware, power and driver
qualification pending.

## Explicit child boundary

`inspect_native_arm_metadata` uses worker `native_arm_metadata`, requires
explicit metadata-only/power-disconnected acknowledgments, and constructs the
real `WindowsControllerMetadataAcquirer` only inside that child branch on
Windows. The 20-second parent diagnostic timeout/Stop/pipe cleanup encloses its
10-second native-call deadline. The checkbox is an operator assertion, not a
measured power observation. The existing diagnostic supervisor is not relabeled
as qualified physical Job containment or power safety.

`rehearse_native_arm_metadata` uses worker `native_arm_metadata_fixture` with
the closed scenarios `nominal`, `missing-fields`, `duplicate-mapping`,
`changed-device`, and `incomplete`. These fixtures use the real existing generic
inventory parsers but never import/call a live collector. The original fixture
times, COM91, serial and driver labels are intentionally synthetic. Parent result
steps use `native_arm_metadata_snapshot`. Physical metadata collection reports
`metadata_inventory_performed=true`; incapable rehearsal reports false. All
serial-open/write/power/motion/contact counters remain zero.

## Tests and remaining limits

`test_wizard_native_arm_metadata.py` uses only typed fixtures and an explicitly
incapable injected collector. It forbids native DLL loads, host serial inventory
and subprocess creation. Existing controller metadata/resolution tests exercise
the separate injected CM ABI. Public subprocess tests must select the incapable
action only; no received-unit validation is performed by these checks.

Generic HWID remains distinct from the native PnP instance, generic interface
description from native driver service, and generic unit serial from a verified
USB descriptor. The initial correlation uses no friendly-name/index fallback
and is not atomic COM-to-open-handle identity binding. Later port opening still
requires separately reviewed model/firmware/boot/profile/identity evidence and
fresh pre-open/pre-write checks through the independently held physical path.
