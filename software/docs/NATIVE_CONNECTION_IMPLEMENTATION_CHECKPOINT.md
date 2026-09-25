# Native connection-path implementation checkpoint

Date: 2026-09-08. Status: **connection prerequisites implemented and tested;
physical integration and activation remain held**.
This records the connection-path increment after the contained-camera
probe/configuration work. It is not a physical onboarding release, hardware
acceptance report, replacement stage catalog or permission to energize the arm.

The parent [connection plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md) defines
the intended operator outcome. The [developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md)
and [implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md) distinguish
previously verified increments from the work tracked here. Do not carry an old
workspace fingerprint or old test result forward as verification of new source.

## Scope and implemented prerequisites

| Boundary | Already implemented before this increment | What that evidence does not establish |
| --- | --- | --- |
| Local application | One Arrival service, explicit preview/execute tickets, browser/terminal, bounded diagnostics and assigned-folder exports | Hardware connection, power control or motion authority |
| Generic identity | Explicit metadata inventory, opaque candidate choices and metadata acknowledgement | Persistent unit identity, installed firmware or a currently connected capture/serial handle |
| Camera metadata | Fixed helper-file inspection/review, metadata-only registration, native endpoint inventory/identity and prospective reviewed endpoint artifact | Runtime activation registration, native mode qualification, negotiated USB3 speed or received-camera acceptance |
| Camera request/evidence | Inert native request preparation; typed modes/controls; incapable owned-process probe/capture; streamed native-format fixture datasets; settings/readback and review/reopen verification | Physical camera pixels, genuine driver controls, installed optics or qualified physical device cleanup |
| Arm feedback | Exact one-request worker, shared wire validation, consumed rehearsal authorization, retained memory-only feedback and separate synthetic final-power observation | Received controller/arm correlation, actual firmware/boot policy, native serial connection or de-energization |
| Native serial precursor | Single-owner non-purging Win32-shaped lifecycle, bounded completion/cleanup accounting and an unconditional physical hold | Worker-registry integration, executed ctypes/kernel behavior, no reset pulse or atomic COM-to-opened-unit identity |
| Durable storage | Source/session/cell-bound M1 records, one-use attempts, uncertainty holds and original-store read-only/review semantics | Authority to invoke a camera, open serial, energize, move or contact a target |

These are different kinds of evidence. A file hash is not a trusted release;
metadata acknowledgement is not unit qualification; a child-process exit is
not device cleanup; a parsed feedback response is not firmware identity; a
storage qualification is not physical authority.

## This increment: implementation seams

The items below are implemented prerequisites, not completed acceptance of the
full connection plan. The source and verification scope appear below.

| Owner/seam | Intended change | Required invariant | Current verification |
| --- | --- | --- | --- |
| Camera runtime preparation | Separate native runtime-registration record and inert probe preparation; never reuse metadata-only helper registration as activation authority | Exact source/helper/endpoint/request linkage; preparation performs no device or process I/O; physical registration gate stays closed | 58 pure protocol/preparation tests |
| Parent-owned process transport | Bounded two-message stdin transport and exact parent handshake | READY precedes one current-permit check and release; cancellation, original deadline, cumulative byte bound and no retry | 70 transport/existing-owner tests; 33 parent-handshake tests |
| Native camera child | Guarded pre-device probe entry; direct probe/capture refused | No COM/MF before admission; actual child PID/challenge and EOF required; capture has no guarded entry yet | Compiled helper only; incapable parser CTest; 5 actual Python/Win32/C++ pipe interoperability tests |
| Arm adapter | `arm_nonpurging_adapter` joins the non-purging owner to the closed feedback worker | Exact reviewed identity, origin, total budget, quiet input, no purge, one write, shared parser and native cleanup companion; native activation stays held | 359 related adapter/worker/owner/evidence/rehearsal tests |
| Independent review | Read-only inspection of joined source and tests | Report ordering, binding, replay and cleanup defects without hardware execution | Three findings corrected and re-reviewed; see review log |

The two-phase handshake is a transport/admission mechanism, not a new public
command console. No HTTP field may supply an executable, endpoint, COM path,
stdin payload or blanket hardware flag. A standalone registration/preparation
API does not imply the application has a released physical action. Rehearsal
continues to label modeled native observations separately from actual owned
process observations.

### Implemented callable seams

- `providers/windows/_owned_worker_win32.py` adds
  `WindowsOwnedProcess.start(..., keep_stdin_open=True)` and one
  `send_final_input(wire, check=...)`. Existing one-write callers retain their
  EOF behavior. This is bounded transport, not a physical dispatcher.
- `providers/windows/native_camera_protocol.py` defines
  `NativeCameraAdmissionRequest`, `parse_native_camera_ready`,
  `native_camera_release` and `parse_owned_native_camera_result`. Canonical
  request bytes bind source, operation, selected identity, endpoint/helper,
  runtime registration, native request and permit hashes. READY binds the
  request to an expected owned child PID and challenge; release/result retain
  those bindings. The pure release encoder does not consume authorization.
- `providers/windows/arm_nonpurging_adapter.py` adds
  `NonPurgingArmFeedbackBackend`, `ArmNativeLifecycleEvidence` and
  `verify_arm_native_lifecycle_evidence`. The feedback worker's exact backend
  registry now recognizes that adapter. It captures bounded native ownership
  and late-read evidence after the worker's cleanup path, alongside—not instead
  of—the full feedback receipt. The native facade remains unconditionally held.
- `providers/windows/native_camera_registration.py` adds the distinct dormant
  `NativeCameraRuntimeRegistration` and `PreparedOwnedNativeProbe`. Preparation
  reconstructs the existing logical probe request and binds new-build helper
  and build-record pins; the returned process registration remains
  `PHYSICAL_UNQUALIFIED`. The whole preparation, including process budget and
  assigned working directory, must be covered by parent admission—not only the
  child request hash. It does not reapprove the historical metadata binary.
- `providers/windows/native_camera_parent_admission.py` adds
  `NativeCameraParentHandshake`: inert construction/view, explicit `begin`,
  start-boundary checks, one `accept_ready`, one `check_release` and a separate
  result parser. It snapshots the whole preparation and rechecks the existing
  consumed permit before request transport and immediately before release.
  The future caller must use the same pinned process registration, original
  permit-derived deadline, actual owned PID and final-write callback.
- `native/windows_camera/admission_protocol.{h,cpp}` supplies a bounded flat
  request/release parser and single-use `AdmissionState`.
  `admission_entry.{h,cpp}` uses inherited pipe handles, a bounded request and
  release, a fresh child challenge and final EOF before returning admission.
  The child validates protocol linkage; the trusted parent—not possession of
  a correctly formatted release message—must establish current durable
  authority. The new `camera_worker.cpp` main branch refuses legacy direct
  probe/capture arguments before COM/Media Foundation startup. Its
  `--owned-probe` branch requires completed admission before reconstructing the
  logical probe. Metadata inventory/identity remain separate. This changes
  new-build activation arguments; it does not reapprove historical helper pins.

Detailed contracts: [camera admission and build](NATIVE_CAMERA_ADMISSION.md) and
[non-purging arm adapter](ARM_NONPURGING_ADAPTER.md).

### Changed files and compatibility

Python production changes are limited to six files beneath
`software/src/rocell/providers/windows`: new `arm_nonpurging_adapter.py`,
`native_camera_protocol.py`, `native_camera_registration.py`,
`native_camera_parent_admission.py`; updated `arm_feedback_worker.py` and
`_owned_worker_win32.py`. Normal one-write incapable process/camera callers keep
their original behavior. No Arrival service, browser action, coordinator,
physical gate, hardware profile or frozen board geometry was changed.

The native source adds `admission_protocol.{h,cpp}` and
`admission_entry.{h,cpp}`, separate incapable parser/entry test targets, and
changes `camera_worker.cpp`/`CMakeLists.txt`. The new helper is compiled under
`build-owned/Release`, with a separate
[development build record](../native/windows_camera/owned_build_manifest.json).
It was **not run**. Only the separately linked incapable test executables ran.

**Visible consequence in physical metadata mode:** current native source no
longer matches the historical metadata catalog. Inspection reports `HASH_DRIFT`
for `camera_worker.cpp` and `CMakeLists.txt`; the historical binary and manifest
still match their old pins. Review stays held and no provider is registered.
There is no automatic hash refresh or substitution of the new helper. A future
reviewed metadata/runtime release must address this explicitly. Rehearsal
metadata and camera controls remain available.

## Future onboarding sequence and release gates

This is the intended sequence **after the missing integrations and independent
physical releases are completed**. It is not an arrival-day instruction to use
currently held actions or to bypass a blocked wizard step.

1. Launch the application inertly. Check source/build identity and assigned
   evidence/export locations. Select the intended cell/session; never resume a
   prior effect merely because a retained receipt can be reopened.
2. Review the installed hardware and canonical board layout. The planned camera
   is static overhead and connected to the host, not the arm controller. Nominal
   geometry and fixture images remain distinct from received installation
   measurements. Do not copy nominal camera calibration into physical evidence.
3. Explicitly collect metadata and select/review the received camera/controller
   candidates. Resolve missing, duplicate or ambiguous identity. Friendly name,
   camera index and COM spelling are not sufficient persistent identity.
4. Inspect/review the fixed camera helper for its allowed scope. Metadata-only
   registration permits only its reviewed metadata operations; runtime admission
   requires a distinct registration and independent qualification. Helper/source
   drift invalidates current claims rather than silently refreshing a hash.
5. For a later released camera campaign, prepare the exact reviewed endpoint,
   native operation, budgets and evidence destination. Under the coordinator's
   locks and original authorization window, recheck identity and admit the
   bounded owned child before its first possible device effect. Metadata,
   process startup and device activation must remain separately visible.
6. Retain native reported modes/controls, stage explicit immutable intent, and
   perform a separately authorized finite capture. Compare requested and actual
   readback, verify complete frame/provenance retention, then publish diagnostic
   preview/status only after completion logging. Focus/aperture and mount
   placement remain physical adjustments requiring fresh measurements.
7. Complete arm identity with actuator power disconnected under the canonical
   stage procedure. Bind USB controller identity to the received Pro arm/model
   separately. Installed firmware, startup mission/boot policy, driver behavior
   and competing-controller observations cannot be inferred from USB metadata.
8. Review the independent power cut, gravity/startup containment and safe
   observation arrangement. Record one supervised **manual** startup event in
   its own armed attempt with zero host commands and an independent final-power
   observation. A successful storage operation cannot authorize this event.
9. A later feedback-only connection gets a new reviewed power envelope and exact
   one-use admission. Opening serial can itself cause a reset/effect; requested
   RTS/DTR-disabled settings do not prove absence of a bridge pulse. Revalidate
   identity before the one open and preserve every unexpected startup byte.
10. After the bounded quiet-input requirement passes, permit only the existing
    one-shot feedback request. No purge, buffer reset, retry, remainder write,
    reconnect, baud probing, torque toggle or vendor demo is a recovery path.
    Retain exact private bytes, independently assess the typed response, and
    close using conservative native/process cleanup accounting.
11. Record a separate post-campaign power observation. Serial close, process
    exit, cancellation and a UI Stop button cannot prove de-energization or act
    as a certified robot emergency stop. Missing/unknown observations hold the
    original attempt; do not repair or replay it automatically.
12. Installed calibration, controller/model/TCP correlation, whole-board
    noncontact acceptance, handoff and a separately released motion/contact
    executor still precede actual individual keyboard presses or Android taps.
    A diagnostic connection is not authorization to type.

Use the original plan's received-hardware procedures for physical events. No
new power switch, motion endpoint, arbitrary command input, firmware update,
boot-mission edit, servo-zero rewrite or automatic parking is introduced here.

## Acceptance record

Frozen workspace source fingerprint:
`05a804d04d6096486d5fc3006d59eff27b06027b041efab69272e875d269d3e8`.
This existing fingerprint covers Python/UI/configuration sources, not the native
C++ tree. Native sources/artifacts have separate exact hashes in the build record;
its SHA256 is `705228b1595e1efeb2b8ceef171e3f6fdffad505b6e680b847cec352d712d7b6`.
Docs, tests and run artifacts do not change the workspace source fingerprint.

| Evidence | Result |
| --- | --- |
| Final changed source/API inventory | Six Python files plus separately recorded native source/build changes; listed above |
| Frozen workspace fingerprint | Exact hash above, rechecked after packaging and public smoke |
| Two-write transport and existing owned-worker tests | **70 passed in 5.21 s**; includes injected write failures and an actual incapable child with owned Windows Job/pipes |
| Parent handshake | **33 passed in 0.63 s**; whole preparation, PID/hash, pre/post-callback cancellation/deadline, no renewal or retry, native-result separation |
| Camera runtime/child pre-device admission tests | Agent: **58 pure tests**, **1 incapable parser CTest**; root: **5 actual pipe interoperability tests in 0.49 s**, no skips in this run. Nominal, wrong PID, cancelled release, wrong permit, extra input; admission-only completion cannot pass the native camera receipt parser |
| Non-purging adapter/feedback integration tests | Agent: **359 passed in 2.00 s**, actual feedback worker through sealed incapable native API plus existing evidence/rehearsal coverage |
| Independent read-only review findings and disposition | Three concrete issues corrected and inspected; no remaining finding in bounded review |
| Combined regression command/count/duration | **2,487 passed, 2,999 deselected in 133.37 s**; exact selection below, not the entire repository suite. Targeted counts above overlap and must not be summed |
| Startup/import/status no-I/O check | Launcher `-Check`: 0 operations, both devices `NOT_CONNECTED`, 15 physical stages pending, assigned workspace export directory; foundation: 6 valid zero-authority contracts, activation false |
| Formatting/type checks | Black and mypy clean for all six changed production Python files |
| Packaging/build provenance | Offline/no-dependency/no-install wheel built; six changed source entries byte-match; native helper and incapable targets compiled with `/W4 /WX`; no runtime release |
| Public wizard regression/export | 21 explicit public actions completed; modeled probe/settings/capture/assessment/review and verified assigned-folder export; details below |
| Actual hardware enumeration/activation/power/motion/contact | None performed by any agent during this increment; physical release remains held |

The first combined selection returned **2,481 passed and 5 failed**: those five
tests still expected historical native-source approval. Tests were corrected to
require the production source-drift hold. Positive registration/revalidation
coverage uses a separately identified, isolated incapable file catalog with
process creation forbidden; no production catalog was reapproved. Both affected
test files subsequently passed **59 tests in 2.55 s**. Final combined rerun passed
as recorded above; no production pin was refreshed to change the result.

Reproduce the combined hardware-free selection from the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit -q -k '(arrival_wizard or wizard_actions or wizard_worker or wizard_diagnostic or wizard_device_selection or wizard_native_camera or wizard_camera_helper or windows_camera_preparation or windows_camera_worker or windows_camera_identity or windows_camera_capture_ingest or wizard_reference_stage_integration or owned_camera or owned_worker_process or wizard_feedback_stage_integration or camera_configuration or camera_probe_evidence or arm_nonpurging or arm_feedback or nonpurging_serial or native_camera or owned_admission_transport) and not wizard_owned_camera_integration and not wizard_camera_configuration_integration' -m 'not slow' --tb=short
```

The independently compiled incapable C++ entry target must exist for its five
interoperability tests to run; absent that target, pytest reports skips rather
than evidence of interoperability. This checkpoint's run had no skips. The
separate slow all-stage/M1 integration tests were not run in this increment;
the public real-M1 camera regression below was run. No new browser visual QA
was performed because the UI assets/actions were unchanged.

### Public wizard regression and assigned-folder export

Executed on the frozen source through the normal service preview/execute flow:

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_owned_camera_smoke.py --probe-and-configure --assess-and-review --frame-count 1 --fault none --expected-source-sha256 05a804d04d6096486d5fc3006d59eff27b06027b041efab69272e875d269d3e8
```

This is the existing incapable camera workflow, not the newly held native
dispatcher. Launch `wizard-9abd855246134a96aa5977cd483996b8` created rehearsal
`rehearsal-669ce7980f604a99abf79eedf9155d8b`. It made **21 explicit actions**,
completed stage-five review, and stopped with stage six pending. No operation
was replayed; all fifteen physical stages remained pending. The full-size
synthetic capture retained **40,108,288 logical bytes** including its preview;
manual gain 32 and automatic exposure read back as modeled. Electronic controls
remain fixture observations, not received-camera specifications.

The [diagnostic export](../runs/wizard-exports/wizard-20260908T053211735973Z-df12153e02b5470986ef34fa64a807f1/README.md)
is in the user's selected workspace export folder. Independent verification:
`VERIFIED_DIAGNOSTIC_EXPORT`, **11 payload files / 291,829 bytes**, manifest SHA256
`23b191036305579f7fd31dbe4c13966e2e3710afdbe270dedc0b20a33216b973`.
Raw frames/full private M1 records are not silently included in normal exports.
The smoke process finished successfully and shut down its local service.

The offline development [wheel](../runs/wizard-package-check-05a804d0/rocell-0.1.0-py3-none-any.whl)
is **1,629,377 bytes**, SHA256
`a3467e1705c9b770e66d97f98bc11eb9760f8a7be04995e28d3c9158c6751bda`.
This is package-content verification, not an installed application acceptance
test; the native development helper is separately distributed and still held.

### Next implementation dependency

1. Implement the distinct physical M1/lease-owning transaction and diagnostic
   coordinator composition, with independent source/release qualification.
   Do not relabel the rehearsal persistence adapter or its evidence schemas.
2. Join the exact native probe preparation/handshake/owned process to that
   coordinator, retain raw pipes plus independent native cleanup, then expose
   the narrowly released probe action. Guarded capture/control admission follows;
   the current new helper deliberately has no direct capture fallback.
3. Add contained arm IPC and trustworthy Windows controller resolution. Join
   the new adapter and complete native companion to physical retained evidence
   and separately observed manual power events. Keep default native holds until
   those dependencies and the reviewed release are satisfied.
4. Finish installed calibration, final two rehearsal stages, noncontact
   acceptance and separate execution authority before typing/tapping hardware.

### Read-only integration review log

- Parent transport draft: reviewed `WindowsOwnedProcess.start(...,
  keep_stdin_open=True)` and `send_final_input(...)`. The initial draft checked
  one scheduled write and no pending I/O before allowing the final write, but
  did not establish that the first write completed successfully. Initial
  validation/check failure or a short write could leave that final slot
  available if a caller caught the failure. **Addressed:** final input now also
  requires exactly one confirmed complete prior write; validation/check/short
  failures do not increment that count. The changed ordering and focused
  regressions were re-reviewed. Owner-reported test scope appears above; the
  higher-level parent/child protocol was subsequently reviewed too.
- Pure camera protocol draft: request/READY/release/result binding and reuse of
  the existing typed native probe parser were inspected. No concrete join
  regression found in this bounded read-only pass; no code was executed.
  Dormant runtime/request reconstruction was also inspected without execution.
  The parent must cover the complete preparation/cwd/budget in its current
  admission. This is not an approval of native activation.
- Parent handshake and guarded C++ main branch: one-use state transitions,
  whole-preparation checks, cancellation/deadline checks after callbacks,
  child/request/challenge binding, final EOF and refusal of legacy activating
  arguments were inspected. No further concrete regression found in this
  bounded read-only review. The handshake remains a primitive without an
  enabled physical dispatcher; neither review nor compilation supplies release.
- C++ admission hash cleanup draft: the caller-owned hash buffer was scoped
  inside a `try` block, allowing exception unwinding to destroy it before the
  catch destroyed its CNG hash handle. Reported to the owner; cleanup must
  preserve the buffer until hash destruction, as required by
  [Microsoft's BCryptCreateHash contract](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptcreatehash).
  **Addressed and re-reviewed:** storage now outlives the `try` block, including
  hash destruction in its exception path. No native failure injection was run
  by the independent reviewer; owner test/build results remain separate.
- Arm companion draft: requested cross-accounting between a successful worker
  outcome and native closed/readback/write/cleanup evidence; individually
  schema-valid native fields must not support a contradictory successful
  companion. **Addressed and re-reviewed:** successful companions now require
  closed/error-free/readback-verified native state, the exact fixed write and
  complete resource cleanup. Pure verification cross-checks the expected worker
  result, retained-byte aggregate, origin and cleanup. Final adapter request
  snapshot/one-use tests are included in the recorded 359-test run.

Do not replace pending entries with fixture success constants. Record whether
a test uses pure values, an injected Win32 facade, an actual incapable child,
native compilation, real local storage or received hardware. Each tests a
different boundary. The operator-facing application may expose only the scope
that its service, coordinator, storage and physical release jointly allow.
