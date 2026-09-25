# Camera setup entry and cleanup checkpoint — 2026-09-10

This is an implementation checkpoint, not a camera/arm release. The governing
[completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md) and
[camera acquisition work order](CAMERA_IDENTITY_TO_ACQUISITION_WORKORDER.md)
remain open. Exports use the operator-confirmed workspace folder:
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

Follow-up: [camera-entry storage integration](CAMERA_ENTRY_STORAGE_CHECKPOINT.md)
addresses run 02's terminal pending-stage failure without changing ordinary
evidence admission or relabeling this checkpoint's source fingerprint.

## What changed

**Camera-entry operator labels now agree across the interface and service.**
The entry document already supported labels such as `Camera setup operator`;
the shared Setup service incorrectly applied its other actions' portable-ID
restriction. One pure validator now serves the entry codec, action validation
and Setup entry path. It requires a trimmed, nonempty label of at most 64 UTF-8
bytes, without control characters. Internal spaces and Unicode are permitted.
Other Setup actions keep their existing portable-ID rules. Invalid entry labels
are rejected before the public action queues an intent. Labels remain procedural
annotations, not authenticated identities, filenames or permission grants.

**Camera permits receive their first timestamp after preparation completes.**
The camera coordinator now shares the existing USB diagnostic behavior: finish
read-only preparation and successful lease cleanup before first issuance. The
30-second lifetime, execute-time fresh checks, worker budgets and cleanup limits
are unchanged. Repeated prepare does not refresh a cached or expired permit.
Failed preparation/cleanup cannot issue one; a changed snapshot still invalidates
it. No arm, controller-energy or generic commissioning domain was changed.

**Native camera cleanup is explicitly testable without a camera.**
`camera_cleanup.h` contains only once-only cleanup ordering and observations.
The existing worker supplies the COM/Media Foundation adapter. Tests supply a
recorder with no device implementation. A failed shutdown HRESULT still permits
reference release; an interrupted call does not fabricate completed cleanup.
The receipt still counts explicit activation-shutdown attempts, not every
possible driver/internal Source Reader shutdown. No receipt schema or physical
runtime registration changed.

The new capture build compiles both capture-enabled and probe-only workers in
a fresh preserved directory. Its cleanup test target is registered only in
the capture CMake entry point. The historical probe CMake file, runtime manifests
and old binaries remain byte-identical: they are not repinned to new sources.
The file-only runtime inspector correctly reports the new worker and capture
CMake differences as additional historical source gaps, not a qualified build.

## Verification and honest limits

Application fingerprint, excluding native build inputs as defined by the existing
application fingerprint function:
`bc2bf67a26c125efe515ed02eeb68af17d7834a0526b80a78c94743553284b68`.
The checkpoint copy index records the changed native inputs separately.

| Check | Result | What it proves |
| --- | --- | --- |
| Entry contract, queue, projection and action tests | 268 passed, 2.13 s | Shared label rules and existing entry guards |
| Camera/USB issuance and coordinator regressions | 126 passed, 2.04 s | First issuance, expiration, fresh checks and failed cleanup behavior |
| Entry/history/export/native-runner regressions | 191 passed, 14.51 s | Selected integration and preserved historical runtime comparisons |
| Full modeled public entry/UI/export | 1 passed, 167.75 s | Actual public service and export path with modeled storage/device facts; labels with spaces work |
| New native cleanup and capture-parser CTests | 2 passed, 0.08 s | 148 cleanup and 84 parser assertions; no camera implementation executed |
| New-build incapable capture pipe cases | 8 passed | Exact incapable child's success, delayed/invalid release, EOF and timeout behavior |
| MSVC build | Passed, both worker variants | Compilation only; actual camera helpers were not executed |
| Black / targeted mypy | 10 files unchanged / 4 production files clean | Selected checks, not a repository-wide clean result |
| Rehearsal and physical launcher `-Check` | Both passed | Disconnected, zero operations, no physical authority, confirmed export folder |

Earlier expanded mypy still has 35 findings in existing terminal/USB identity
sections, recorded in the preceding service checkpoint. This increment does not
claim to fix them or run the complete repository test suite.

### Preserved failures and the fresh acceptance run

`camera-mode-public-ntfs-20260910-01` failed after 2,019.87 seconds on the previous
application fingerprint `0ffacaccc5fb74e833e3aa408f9bd1614262d6550dca9129556f19a9dfac4d5b`.
The complete identity sequence, final review, dedicated export and fresh reopen
passed before camera entry rejected the spaced operator label. No camera-entry
write or device access occurred. The consumed attempt and its original store
remain unchanged; this is not a passed stage-5 acceptance.

The first selected regression run also retained two failures: the intentionally
changed native source no longer matched a test's old current-source expectation,
and adding a test to the historically pinned probe CMake entry point invalidated
the old incapable child package. The fix records the new expected source gaps
and restores that CMake file exactly. The second run passes all 191 tests. Old
binary/manifest pins were not updated to make a test pass.

A **new** full public NTFS run, `camera-mode-public-ntfs-20260910-02`, failed
after 2,104.65 seconds under the fingerprint above. Its complete identity
sequence, final review, dedicated export and fresh reopen passed. Camera entry
then failed because ordinary V2 evidence storage rejects a still-PENDING stage.
The entry's intended one-record/one-event protocol had not been exercised by
the modeled store's permissive write callback. The entry package was not
published; no device was opened. The original and consumed attempt remain
unchanged. This is not a passed stage-5 acceptance.

The next increment adds a narrow file-only entry retention operation and real
storage contract regressions. It must preserve the ordinary evidence guard,
original readback layout and separate hardware holds. A new full acceptance
run is required; neither failed original may be repaired or reused as a pass.

## Next implementation boundary

1. Fix the pending-entry storage contract, test against real storage, preserve
   run 02 without replay, and execute a fresh public acceptance run.
2. Join current, original-derived camera setup/runtime facts to the existing
   acquisition coordinator. Historical entry alone must not impersonate current
   camera selection or an independent power/isolation observation.
3. Complete and separately register a current physical native runtime, including
   selected unit/driver identity checking immediately before activation. An
   echoed request identity hash is not such a measurement.
4. Wire finite capability probe, advertised mode/control selection and readback,
   then a bounded fresh image into the existing service, UI, Stop and export paths.
   Keep manual focus and observed image/coverage quality explicit.
5. Continue the separate arm identity, supervised startup and feedback workflow,
   then optical/board/reference calibration and noncontact acceptance. Physical
   keypresses and phone taps remain later motion/contact work.

No hardware hold was removed by these fixes. The wizard is still a usable
hardware-free diagnostic/rehearsal workbench, not yet the completed physical
camera/arm application requested by the project.

## Native cleanup references

The adapter preserves explicit activation shutdown and reference cleanup as
documented by Microsoft. Source Reader release may itself shut down its media
source by default; the test counter deliberately does not claim otherwise.
See [IMFActivate::ShutdownObject](https://learn.microsoft.com/en-us/windows/win32/api/mfobjects/nf-mfobjects-imfactivate-shutdownobject),
[MFCreateSourceReaderFromMediaSource](https://learn.microsoft.com/en-us/windows/win32/api/mfreadwrite/nf-mfreadwrite-mfcreatesourcereaderfrommediasource)
and [Media Foundation capture lifecycle](https://learn.microsoft.com/en-us/windows/win32/medfound/audio-video-capture-in-media-foundation).
