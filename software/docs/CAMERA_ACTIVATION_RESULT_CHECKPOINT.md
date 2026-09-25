# Camera connection: installed v2 wire validation

Follow-up: [v2 preparation and owned-process parent integration](CAMERA_ACTIVATION_PARENT_CHECKPOINT.md)
is now installed/tested. The source and counts below describe this earlier wire
codec checkpoint; the sealed export remains unchanged.

Date: 2026-09-10. This increment installs **pure Python request/result codecs**,
not physical camera dispatch. The native camera worker integration remains a
compiled draft. Camera/arm startup, device access and motion remain disabled.

## Outcome and source boundary

The parent now validates a full v2 probe or capture result against its exact
request, READY challenge, expected child PID and permit digest. It also validates
the unchanged acquisition/cleanup body and independently compares fresh reported
unit/driver metadata to the expected identity. It never accepts a child's MATCH
flag alone. A valid result is wire consistency, not proof that the process owner
consumed authority, finished cleanup, or authenticated original setup records.

Application source before installation:
`6eda11d89c0bc817b46c18c2e2f6fd3b154594594b5cdd82a7137cc5f5e11453`.
Application source after installation:
`809c8510f383f748905f7117e5e86e19adfd02efd1679f856b24e5237c6ae262`.

The full public NTFS entry run passed on the **earlier** source. Its accepted
originals, full source snapshot and seven verified exports remain unchanged in
[the accepted checkpoint](../runs/wizard-exports/hardware-free-camera-entry-accepted-20260910-01/README.md).
That run was not repeated after adding these codecs. Do not present the old
37-minute acceptance as a full acceptance of the new source or relabel its
history. The new code does not alter original-store readers or dispatch paths.

Installed `software/native/windows_camera/camera_worker.cpp` remains SHA-256
`0bc84f21e99d1d72eb7bc4a4969945016c7593247e67bf586f14101f59e298be`.
No runtime manifest, trust pin or physical hold was changed.

## How the parts connect

| Installed component | Responsibility | Not its responsibility |
| --- | --- | --- |
| `application/camera_activation_expectation.py` | Read the existing reviewed enrollment/metadata join, preserve the exact original metadata digest and unit/driver traits | Authenticate a detached snapshot as original storage, replace a fresh query, or relabel a historical launch |
| `providers/windows/native_camera_activation_expectation.py` | Closed bounded expectation data; exact UTF-16 traits and ordered location paths | Device discovery or selection |
| `providers/windows/native_camera_activation_observation.py` | Validate observed timing, nullable progress, counts and metadata; recompute the identity comparison | Infer zero activity from missing observations |
| `providers/windows/native_camera_activation_protocol.py` | Separate v2 requests, bound RELEASE encoding, and complete owned-result wire validation | Spawn a worker, consume a permit, operate hardware, read a pixel file, or mark a stage passed |

These modules are available to the next dispatch integration but are not yet
called by a physical wizard action. Draft compatibility modules import these
installed implementations, so native interop tests exercise the installed code.
The enrollment factory stays in the application layer; provider codecs do not
import the application or enrollment models.

Both probe and capture reuse the existing **metadata-only** acquisition parser.
Capture preserves exact requested mode rationals/stride, control requests and
readback, bounded frame names/counts/bytes and cleanup accounting. It does not
claim that reported frames exist or contain verified pixels. Those checks belong
to the existing image-ingestion owner after actual dispatch.

Old v1 request/result codecs remain unchanged and reject v2 inputs. Native request
size remains 16 KiB, native results 256 KiB, and the existing bounded JSON decoder
rejects duplicate/nonfinite fields, extra data and excessive depth/node counts.
One original five-second native deadline is preserved; process-level deadlines
and Stop remain the parent's responsibility.

## Executed verification

| Lane/report under `.codex-preserved` | Result | Scope |
| --- | --- | --- |
| `activation-result-tests-20260910-01.xml` | 95 passed, 3.19 s | Initial draft result codec plus 12 real incapable-child pipe/result exchanges |
| `activation-installed-tests-20260910-01.xml` | 119 failed / 7 passed, 4.15 s | Installation defect: missing `SCHEMA` import in the moved application factory; preserved, corrected without weakening validation |
| `activation-installed-tests-20260910-02.xml` | 126 passed, 3.37 s | Three new installed pure test modules |
| `activation-installed-regression-20260910-01.xml` | 380 passed, 5.61 s | Those 126 plus selected existing v1 protocols, acquisition, metadata and selection tests |
| `activation-installed-native-20260910-01.xml` | 168 passed, 23.42 s | Installed implementations through draft compatibility imports; old parser/pipe tests plus new result interop |
| `activation-installed-tool-checks-20260910-01.json` | Passed | Both launch modes, four-module targeted mypy, seven-file Black, and incapable helper import inspection |

These lanes overlap; their counts are not distinct tests to sum. The initial
missing-import failures are not received-camera or native-driver failures.
Targeted mypy is not a repository-wide clean type-check claim.

The new MSVC 19.42 / SDK 10.0.22621.0 `/W4 /WX` result-test target compiled on the
first attempt. Its fixed tested binary SHA-256 is
`577b57491a6d7e3c7a3b9081bda05be849db3725dce881b913d46e7c41312889`.
It links the real v2 owned pipe entry and result formatter plus an exact extracted
copy of the installed identity serializer. A test compares the extracted source
regions byte-for-byte after newline normalization. No metadata resolver, Windows
device adapter, COM/MF or capture implementation is linked. Import inspection
found no checked device or dynamic-loader imports. This is an incapable test
artifact, never a physical runtime registration.

The 12 native result exchanges cover probe/capture success, changed driver,
query exception, late metadata return, failure before the gate, and failed
cleanup. Process/pipe behavior and serialized bytes are real. Device metadata,
post-start timing, acquisition/cleanup counts and frame metadata are explicitly
**MODELED**. No camera worker was executed; no camera, arm, frame file or capture
directory was accessed/created by these tests.

Both wizard launcher checks returned the new source, zero operations,
`NOT_CONNECTED` for both devices, physical authority false and the confirmed
workspace export folder. They do not connect or initialize hardware.

## Reproduce the fast installed checks

From the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_native_camera_activation_expectation.py software/tests/unit/test_native_camera_activation_observation.py software/tests/unit/test_native_camera_activation_protocol.py -q --tb=short
.\start-rocell-wizard.ps1 -Check
.\start-rocell-wizard.ps1 -Mode physical -Check
```

These installed tests require no draft executable. Native interop is a separate
developer lane under `.codex-preserved/camera-activation-identity-draft-20260910-01`.
Its fixed test-child hashes/paths are evidence for this build, not operator
configuration options. Do not learn a trusted runtime hash from arbitrary files.

## Next implementation boundary

The [verified developer archive](../runs/wizard-exports/developer-checkpoint-camera-v2-codecs-20260910-01/README.md)
is in the confirmed export folder: 885 copies / 19,615,648 bytes, independently
verified with zero mismatches. Its 370-input application snapshot reproduces the
new source fingerprint. Older accepted/failed originals and sealed checkpoints
were not overwritten. The archive is evidence, not a deployment or runtime grant.

1. Prepare/register v2 requests in the existing owned process runner. Bind full
   original-derived camera facts, current selection/continuity, controller
   isolation, active lease, consumed permit and the exact reviewed runtime.
2. Add the closed original stage-5 acquisition successor before retaining probe
   receipts. The v15 entry reader intentionally accepts only the entry suffix;
   arbitrary later evidence must not be made acceptable by trimming history.
3. Join explicit finite probe, returned mode/control selection, and one bounded
   still capture to the existing service, Stop, ingestion, UI and export owners.
   No refresh-triggered capture, blind retry or automatic physical initialization.
4. Continue arm identity/supervised startup/feedback and installed calibration
   separately. A camera picture does not authorize robot contact.

See the [work order](CAMERA_IDENTITY_TO_ACQUISITION_WORKORDER.md) and
[completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md). The application
goal remains open; remaining software work is not merely waiting for hardware.
