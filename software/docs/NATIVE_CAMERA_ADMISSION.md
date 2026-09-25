# Guarded native camera probe: development boundary

This increment adds real request translation and a guarded entry to the Windows
camera helper. It does **not** enable physical dispatch, register a trusted build,
qualify a driver, or establish an actual camera connection. The runtime candidate
stays `DORMANT_REVIEW_REQUIRED`; its owned-process composition remains
`PHYSICAL_UNQUALIFIED`. No device-capable executable was run to verify this change.

## Inert preparation API

`providers/windows/native_camera_registration.py` exposes:

```python
runtime = create_native_camera_runtime_registration(
    workspace,
    source_sha256=reviewed_workspace_source_hash,
    catalog_sha256=reviewed_runtime_catalog_hash,
    helper_sha256=reviewed_new_helper_hash,
    build_record_sha256=reviewed_new_build_record_hash,
)
prepared = prepare_owned_native_probe(
    runtime, logical_camera_plan,
    session_id=session_id,
    operation_sha256=operation_hash,
    permit_sha256=already_consumed_permit_hash,
    working_directory=server_owned_working_directory,
)
```

These calls and their returned properties perform no filesystem reads, directory
creation, process calls, inventory, camera access or permission redemption. The
fixed helper path is `software/native/windows_camera/build-owned/Release/rocell_windows_camera.exe`;
the fixed build record is `software/native/windows_camera/owned_build_manifest.json`.
Pins must come from a separate reviewed build record, never auto-updated from a
file found on disk. The previous metadata-only registration is not substitutable.

`PreparedOwnedNativeProbe` owns canonical bytes and exposes `runtime`,
`registration`, `admission_request`, `camera_plan`, `preparation_sha256`,
`required_lifetime_ns`, and copy-isolated `to_dict()`. The logical plan is an exact
unchanged `WindowsCameraWorkerClient.prepare_probe` result. Capture plans, mutated
nested inputs, mismatched source/helper pins, mode/control/output requests and
extra fields are denied. Native probe duration is 5,000 ms; the otherwise unused
probe frame budget is 1 / 39,923,712 bytes and never permits frame acquisition.

The fixed process budget is 10 seconds execution plus 2 seconds cleanup, with
32 KiB stdout, 8 KiB stderr and at least 17 KiB stdin. Parent admission must check
at least `required_lifetime_ns` remains and recheck current deadline/cancellation.
Preparation does not close filesystem TOCTOU or qualify owned-process cleanup.

## Versioned request / READY / RELEASE / result

`native_camera_protocol.py` provides bounded immutable request and READY values,
`parse_native_camera_ready`, `native_camera_release`, and
`parse_owned_native_camera_result`. Canonical flat ASCII JSON uses sorted compact
keys, with Unicode endpoint characters escaped and hashed as decoded UTF-8.
Request/handshake limits include the single required line-ending LF.

| Message | Schema | Required binding |
| --- | --- | --- |
| REQUEST | `rocell.native_camera_admission_request.v1` | attempt/session, workspace source, operation, selected identity, exact endpoint/hash, helper/runtime registration, logical camera request, consumed permit; fixed durations |
| READY | `rocell.native_camera_admission_ready.v1` | canonical request SHA-256, actual child PID, 32-byte random challenge encoded as 64 lowercase hex characters |
| RELEASE | `rocell.native_camera_admission_release.v1` | same request/PID/permit and SHA-256 of the ASCII challenge |
| Result | `rocell.owned_native_camera_result.v1` | same request/PID/challenge digest/permit plus full unchanged `rocell.windows_camera.v1` native probe receipt |

The parent starts the pinned owned process with only
`--owned-probe --request-sha256 <canonical-request-hash>`, sends REQUEST + LF, and
keeps stdin open. The child requires pipe handles, validates the bounded request,
generates a challenge using system CNG, and writes READY + LF. The parent must
validate READY against its actual owned PID and revalidate the current consumed
permit before sending RELEASE + LF and closing stdin. The child permits exactly
one release attempt, requires EOF and refuses extra input. Total child admission
time is 2 seconds. COM/MF initialization and exact-endpoint probe follow only
after this sequence completes.

This handshake is not an authenticated M1 database reader inside the child. A
trusted owned parent establishes current authority. Hash matching or successfully
encoding RELEASE is not permission. Another process capable of launching this
binary and constructing both pipe messages is not prevented by a separate OS
authentication boundary. Physical composition therefore remains closed until
the complete coordinator/owned-process runtime is separately reviewed.

The child uses bounded small synchronous pipe calls; its admission deadline and
the parent supervisor detect lateness, but this is not proof that every OS call
can be hard-interrupted on every received driver/host. A missing or late result
does not prove that a camera source shut down. The existing inner receipt's real
activation/shutdown counters are retained without replacing them with fixture
zeros or claiming physical qualification.

## Source behavior change and build separation

The **new** helper source rejects direct `probe` / `capture` and unknown CLI entry
points with `OWNED_ADMISSION_REQUIRED` before COM/MF. Inventory and identity
metadata retain their separate explicit entry points. The old logical Python
client probe arguments must be translated through this guarded preparation;
they are not directly executable against this new helper. Guarded capture is not
implemented. No old binary, historical manifest or metadata catalog pin was
overwritten. The old metadata catalog's source comparison will correctly report
drift after these native source changes; it must not silently approve this build.

Build without running the device-capable helper:

```powershell
cmake -S software/native/windows_camera -B software/native/windows_camera/build-owned -G "Visual Studio 17 2022" -A x64
cmake --build software/native/windows_camera/build-owned --config Release --target rocell_windows_camera rocell_camera_admission_tests rocell_camera_admission_entry_tests
ctest --test-dir software/native/windows_camera/build-owned -C Release -R '^camera_admission_parser_incapable$' --output-on-failure
```

Do not substitute an unfiltered CTest invocation here: older registered tests
include the device-capable helper's self-test entry. The selected parser target
links only protocol/CNG code. The separate `rocell_camera_admission_entry_tests`
target links the real pipe entry/protocol but no COM/MF/camera implementation. Its
explicit `rocell.native_camera_admission_only_test.v1` completion contains
`admitted`, `request_sha256`, `child_pid`, `challenge_sha256` and `device_effects=0`;
it is intentionally rejected as a production camera result.

## Verification and remaining hold

This build used existing MSVC 19.42.34435, Windows SDK 10.0.22621.0 and CMake 3.31.3
with warnings-as-errors. The helper and both incapable targets compiled. The
selected incapable parser CTest passed. Fifty-eight pure Python contract tests
passed; both new Python modules passed mypy. Parent integration separately ran
five real owned-process tests using **only the incapable pipe-entry target**:
nominal cross-language binding/EOF, wrong PID, cancellation, changed permit and
trailing input. There was no camera, OS inventory or native helper execution.

The source uses system CNG challenge generation and preserves SHA object storage
until hash destruction, including exceptional paths, as required by Microsoft's
[BCryptCreateHash contract](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptcreatehash).
Inherited pipe classification follows
[GetFileType](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfiletype);
bounded reads inspect available pipe bytes through
[PeekNamedPipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe).

Still held: reviewed physical runtime registration/admission, received-unit
identity and driver qualification, actual metadata/probe behavior, firmware and
power observations, camera capture, and any arm movement. None is inferred from
this compiled protocol or its incapable test results.
