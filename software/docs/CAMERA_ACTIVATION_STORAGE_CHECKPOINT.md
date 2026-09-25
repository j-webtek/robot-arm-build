# Camera v2: coordinator and original diagnostic storage

Date: 2026-09-10. Component checkpoint for the
[full onboarding application](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md).

The camera-v2 supervisor can now return evidence through the commissioning core
into the existing original M1 record store. The new path preserves unavailable
native counts, bounded private diagnostics and interrupted publication. It does
not enable a physical Connect button, install a camera runtime, grant arm power
or motion permission, or complete the public acquisition/export workflow.

## Implemented connections

| Component | Responsibility |
| --- | --- |
| `camera_activation_campaign_evidence.py` | Closed pair: exact v2 run record and matching supervision detail. Shared observations, preparation and executed registration must agree. |
| `camera_activation_campaign_contract.py` | Fixed probe/capture action profiles; original permit, identity, source, operation and deadline binding; native receipt accounting or explicit absence. |
| `camera_activation_evidence_parts.py` | Pure ordered part/index codec. Each raw part is at most 64 KiB; hashes, lengths, roles, names and complete reassembly are checked. |
| `cell_commissioning_coordinator.py` | Accepts the new result only in its camera domain. Retains returned evidence before handling a failed final scope check or unavailable native accounting. |
| `commissioning_m1_persistence.py` | Immutable part publication, final index last, complete-family audit, private original readback and native-accounting validation for known and uncertain outcomes. |

The existing `CampaignEvidence` type, 128 KiB aggregate limit, USB-only uncertain
execution type, historical v1 bytes and record filename grammar are unchanged.
The new camera pair permits at most 512 KiB run data plus 1 MiB supervision data.
There are at most eight run parts, sixteen supervision parts and one final index.
The enclosing records remain within the existing 1 MiB per-record ceiling.

New publication checks the entire camera family's existing 2,048-file / 32 MiB
budget, including sibling domains. It also reserves three record slots and
three times the existing per-record byte maximum for the two lifecycle receipts
and terminal result. This is deliberately conservative. The future admitted
campaign must check capacity before device effects as well; the retention check
is a final protection, not a pre-dispatch capacity guarantee.

No supplied filename or destination is trusted. Parts use derived
`receipt-attempt-…-camera_activation_<role>_<letter>.json` names inside the original
camera record directory. The index uses the existing per-attempt evidence name.
Private native buffers may contain device paths; they are not ordinary UI logs.

## Failure and reopening behavior

- Missing final index means incomplete evidence, even if every part is present.
- A failed write/sync never retries, overwrites or deletes an original.
- Partial parts remain subject to the original request, domain, armed predecessor,
  envelope/hash and aggregate audit. They cannot produce a known successful seal.
- A publication error after the final index still yields an uncertain attempt
  with quarantine. Complete evidence does not reverse that outcome on reopening.
- When the native receipt is unavailable, the result retains `receipt=None`;
  there are no invented zero counters. Available counters cannot be discarded or
  altered merely because the overall result is uncertain.
- Reopening audits the same complete cell-global ledger and camera-family records.
  Reading a saved permit does not make it executable in a fresh coordinator.

## Verification boundary

The new protocol tests use a modeled owner and clocks, with real native-owner
construction forbidden. The new storage tests use actual local NTFS publication,
Windows leases, ledgers, original readback and fresh runtime reopening, but
explicitly modeled camera/process/admission facts and monotonic time. Predecessor
PASS entries are labeled incapable storage fixtures, not received-unit evidence.
No camera, arm, metadata query, physical helper or pixel acquisition is invoked.
These tests do not establish real campaign timing margin or full public UI
acceptance.

Final verification on source `457e9586…`:

| Lane | Result | Report |
| --- | --- | --- |
| New camera contracts/supervisor/evidence and selected legacy core/camera/USB regressions | 687 passed, 166.23 s | [selected final report](../../.codex-preserved/activation-storage-final-selected-20260910-01.xml) |
| Actual local M1 publication, leases and reopening: 17 new camera cases plus 21 existing M1/camera cases | 38 passed, 274.29 s | [original-storage final report](../../.codex-preserved/activation-storage-final-m1-20260910-01.xml) |
| Targeted mypy | Six production modules clean | `--follow-imports=silent --check-untyped-defs` |
| Black | Ten changed production/test files clean | `black --check` |

That is 725 passing checks across the two final pytest runs, not a full-suite or
hardware acceptance claim. Both launcher modes were rechecked on this source:
camera/arm `NOT_CONNECTED`, zero operations, physical authority false, and the
confirmed export directory. The archive repeats those inert checks and verifies
the copied source inventory independently.

Reproduce the new focused lanes from the workspace, using fresh report/temp
paths when preserving a run:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_camera_activation_campaign_contract.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_camera_activation_original_storage.py -q
```

The second command requires Windows/NTFS and still forbids physical device access.

Initial verification, retained without replacing earlier reports:

- Paired artifact tests: 38 passed.
- Part/index tests: 32 passed after correcting an oversized Windows test name.
  The first run retained 31 passing cases and two harness errors; its oversized
  parameter was not executed in that run. Only the test ID was corrected.
- New core/profile/receipt tests: 24 passed.
- Initial actual-store cases: 13 passed in 149.84 s; independent changed-counter
  original audit: 1 passed in 12.83 s.
- Selected pre-final regressions: 494 passed; legacy M1/camera storage: 21 passed;
  USB regression lane: 206 passed. These overlap with later final runs.

## Source boundary

Starting application source:
`f2cc4429a7ec69123fe3c20b17d76fbf705c143a9a939e4ff72b6a1e71043b7d`.
Initial storage join:
`15a9b827d903093f2e16880fa20e1e041048892bbc10e087276387a248eef681`.
Final addition of uncertain-result accounting validation:
`457e9586ecc197d244efe3eebe9f786dd3e2df154eff1bd05290335ce3f25cad`.
Native worker source/runtime pins are unchanged. Earlier full public NTFS v15
acceptance belongs to its historical source; it was not rerun for this increment.

## Next developer work

1. Implement the scoped camera-v2 campaign that constructs the exact preparation
   from original accepted identity, reviewed runtime, current stage and bounded
   acquisition intent. Use the active consumed M1 scope for both supervisor
   revalidations. No reconstructed/exported permit or permissive placeholder.
2. Review/install the purpose-specific v2 native runtime. Keep the legacy runner
   hold intact; a test registration or candidate runtime is not physical approval.
3. Add an original stage-5 acquisition successor to the accepted v15 entry reader.
   Preserve original history and distinguish retained, assessed and reviewed
   acquisition. Own capture output, verify image bytes and freshness separately.
4. Join those actions to the existing wizard, Stop, summaries and explicit private
   export/reopen path. Do not create a second logging or connection system.
5. Continue installed-camera optics/placemat calibration and separate original
   arm identity, supervised startup and bounded feedback services. Live keyboard
   and Android contact execution remains later, separately qualified work.

The operator-confirmed export parent remains
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
See [the storage work order](CAMERA_ACTIVATION_STORAGE_WORKORDER.md) for acceptance
criteria and [the developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md) for the
whole application, not just this component.

The [verified developer snapshot](../runs/wizard-exports/developer-checkpoint-camera-v2-storage-20260910-01/README.md)
retains 1,656 copies / 21,631,054 bytes with zero independent hash mismatches.
Its 377 application inputs reproduce the final source; 779 copied original-store
test files retain the new actual-storage cases, including intentional faults.
It is a development checkpoint, not an importable wizard export or physical
qualification. The archived checkpoint omits only this post-seal navigation note.
