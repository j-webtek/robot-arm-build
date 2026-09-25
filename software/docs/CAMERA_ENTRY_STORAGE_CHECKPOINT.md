# Camera setup entry: storage integration checkpoint

Date: 2026-09-10. This increment fixes entry into camera setup; it does not
connect a camera, start the arm, or qualify received hardware. The full target
remains the [application completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md).

The operator-confirmed diagnostic export parent is:

`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`

## Failure and correction

Fresh public NTFS run `camera-mode-public-ntfs-20260910-02` failed after
2,104.65 seconds. It successfully built and reviewed the full original identity
sequence, exported it, and reopened it. Entry then called ordinary evidence
storage while stage 5 was still `PENDING`. That storage API correctly refused
the write. No entry package was published and no device was opened. The failed
store and consumed operation are preserved, not repaired or replayed.

The entry format requires a retained package before its one opening event can
reference that package. The fix adds a dedicated file-only operation rather
than weakening ordinary evidence storage or changing the original v15 layout.

| Owner | Responsibility |
| --- | --- |
| Arrival / Setup | Claim the one-use action, check source/deadline/Stop, authenticate the full original reviewed identity chain under the stage lease |
| M1 camera transaction | Accept only the closed camera-entry document; require CELL + SESSION leases, matching header/cell/session/source and final complete-review event, and valid record/capture times |
| V2 storage | Require the empty next pending stage and a legal prospective opening transition; publish one bounded immutable package, verify it, and recheck the committed head |
| Setup / original reader | Read exact retained bytes, append one `PENDING → WAITING_OPERATOR` event referencing them, then authenticate the full unchanged predecessor plus entry |
| Arrival / export | Publish success only after the existing completion checks; retain partial diagnostics and export original bytes without replay |

Ordinary `store_evidence` still rejects pending stages. The new M1 method accepts
no caller-selected stage, label, media type, device action or permission flag.
The private V2 primitive is not evidence qualification. M1's structural check
does not replace Setup's substantive original-chain verification.

## Interruption and recovery contract

- Before publication: invalid context, stale head or invalid input leaves the
  original session unchanged.
- After package publication, before the event: the entry is `INCOMPLETE`, not
  entered. A second entry cannot append another record to that pending stage.
- Failed journal-head publication: retain the package and uncommitted event;
  the existing reconciliation hold prevents further mutation.
- After commit: Stop cannot undo stored history. The existing operation owner
  preserves what happened and never manufactures successful public completion.
- Reopening reads the original; it does not rerun the action or open a device.

## Executed verification

Application source fingerprint for this increment:

`6eda11d89c0bc817b46c18c2e2f6fd3b154594594b5cdd82a7137cc5f5e11453`

The existing fingerprint includes Python/UI/configuration inputs, not native
build inputs. No native production code or runtime registration changed here.

- **39 passed, 19.55 s:** real V2 storage, a genuine NTFS M1 transaction, existing
  V2 regressions and entry-service Stop/failure boundaries. Test predecessors
  are labeled synthetic storage fixtures, not authenticated hardware evidence.
- **Targeted mypy:** all three changed production modules pass with
  `--follow-imports=silent --check-untyped-defs`.
- **355 passed, 204.77 s:** selected entry codec/layout/readback/queue/projection,
  history/export, genuine M1 camera persistence and historical runtime checks.
  This selected run overlaps some service-boundary checks above; it is not a
  full repository suite or a distinct-test total.
- **1 passed, 177.29 s:** public modeled service/UI/export flow using the corrected
  dedicated storage seam. The actual ordinary export preserves the entry bytes.
- **Black:** all six changed production/test files pass the check.
- **Fresh full public NTFS run 03 passed: 1 test, 2,230.09 s (37:10).** It
  constructs the complete original identity history, enters stage 5 through
  the public action, verifies both export types and reopens the unchanged v15
  original in a fresh application without replay. Camera entry took 118.672 s;
  dedicated USB export took 1.86 s and general export 3.062 s. All three actions
  succeeded. Application/native inputs stayed unchanged throughout the run.

Two initial focused-test reports remain preserved: 3 failures/35 passes, then
1 failure/37 passes. These were test implementation mistakes: the head filename,
attempting to mutate a frozen session handle, reading an exclusively locked
lease file, and calling a nonexistent snapshot serializer. They were fixed in
the tests; production storage guards were not relaxed to make them pass.

The public modeled fixture now provides the dedicated entry method and fails
if the service calls ordinary storage, so it cannot hide the original regression.

## Preserved workspace export

The sealed [developer checkpoint](../runs/wizard-exports/developer-checkpoint-camera-entry-storage-20260910-01/CHECKPOINT.md)
contains **1,004 verified copies / 34,224,730 bytes**. Independent re-verification
found zero hash/length mismatches, and the existing export verifier accepted all
six copied diagnostic bundles. Those integrity results do not turn the failed
run or modeled device observations into qualification.

The snapshot includes all **366 application-fingerprint inputs / 11,332,368
bytes**, selected tests/docs, and all **603 failed-run-02 original files /
20,313,865 bytes**. The old original's source fingerprint remains distinct.
Public run 03 was still running when that component checkpoint was sealed;
that historical copy remains unchanged. Its later passing result is recorded
above and preserved separately as the accepted hardware-free entry run.

The [accepted run archive](../runs/wizard-exports/hardware-free-camera-entry-accepted-20260910-01/README.md)
contains 646 verified copies / 24,167,522 bytes. Independent re-verification
found zero mismatches, all seven copied diagnostic bundles passed the export
verifier, and the referenced preserved application snapshot reproduces the
tested fingerprint. No failed original or earlier sealed copy was modified.

The [separate native draft checkpoint](../runs/wizard-exports/developer-checkpoint-native-camera-activation-20260910-02/CHECKPOINT.md)
contains 45 verified copies / 941,185 bytes, with zero independent mismatches.
It includes the compiled pre-activation identity integration and its tests,
not an installed runtime. Its first copy attempt remains visibly incomplete
after a report-path error; the complete checkpoint uses the new `-02` folder.

Both launcher `-Check` modes also pass with the corrected source fingerprint,
the confirmed workspace export folder, zero operations, disconnected camera
and arm, and no physical authority. Native production runtimes were not run.

## Reproduce

Run from the workspace root with the existing virtual environment. Choose new
`--basetemp` and report paths for every retained run; never reuse an original
test store, because pytest may delete a reused temporary directory.

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_camera_mode_entry_persistence.py `
  software/tests/unit/test_camera_mode_entry_service_bounds.py `
  software/tests/unit/test_physical_onboarding_v2.py -q
```

The separate `test_camera_mode_entry_public_composed.py` exercises the public
service, renderers and actual export files with modeled storage. The slower
`test_arrival_camera_mode_entry_ntfs.py` constructs the complete original in
fresh real storage and checks both export types plus a new application's reopen.
Neither test accesses received hardware.

The accepted result is original schema `rocell.physical_camera_source_workflow_readback.v15`
with camera entry `ENTERED`. Stage states are four `PASS`, stage 5
`WAITING_OPERATOR`, and ten later stages `PENDING`. These are file-only setup
states: the actual camera and arm remain disconnected and no physical authority
is created by this acceptance.

Next production work is still the [camera acquisition work order](CAMERA_IDENTITY_TO_ACQUISITION_WORKORDER.md):
original-derived acquisition facts, current native runtime registration,
pre-activation unit/driver comparison, finite mode/control probing and bounded
image capture through the UI. Arm connection/startup and installed calibration
remain separate unfinished software work, not merely pending hardware tests.
