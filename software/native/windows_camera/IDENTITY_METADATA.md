# Identity metadata provider — explicit native/client integration

This separate DEV-006 follow-up resolves a previously observed Media Foundation
symbolic endpoint into typed Windows metadata. It is **compiled, linked into the
native helper, integrated with a strict typed Python client, and pure-tested**.
It is not yet wired into a qualified physical wizard coordinator and is not
qualified on received hardware. No Windows metadata query or device enumeration
was performed while developing/testing it.

Files: [identity_metadata.h](identity_metadata.h),
[identity_metadata.cpp](identity_metadata.cpp),
[identity_metadata_tests.cpp](identity_metadata_tests.cpp).

## Native/client receipt contract

The helper's explicitly invoked `identity` action accepts only `--endpoint`,
`--max-ms`, and `--max-parents`. It routes before COM/Media Foundation startup.
There is no index, friendly-name selection, generic command, implicit discovery,
camera activation, file output or fallback to another unit. Production UI code
must select a server-stored inventory candidate; never accept a browser-provided
device path or pass through raw arguments.

The Python entry point is:

```python
# Called inside an explicit operator metadata action, not a view/constructor.
# candidate is a server-resolved CameraCandidate from explicit MF inventory.
metadata = client.resolve_identity_metadata(
    candidate, duration_ms=5000, max_parent_nodes=8
)
```

Construction is inert. The method verifies the configured helper SHA-256 before
dispatch and uses a bounded shell-free subprocess. It returns
`NativeCameraIdentityReceipt`, parsed from **`rocell.windows_camera_identity.v1`**.
This is a separate versioned protocol, not a loosening of the strict existing
`rocell.windows_camera.v1` inventory/probe/capture receipt.

| Field | Meaning |
| --- | --- |
| `requested_endpoint`, `endpoint_sha256` | Exact supplied opaque endpoint; SHA-256 is computed by the Python client over its UTF-8 bytes. |
| `devnode`, `interface_path` | Independently observed SetupAPI mapping; actual interface path is not normalized to match the request. |
| `device`, `parents`, `observed_root` | Selected node, immediate-parent-first bounded chain, independently observed root. |
| Node `instance_id`, `container_id`, `location_paths` | Typed observed/unavailable values, with registered reason/domain/native error code. |
| `cleanup_errors`, `chain_end`, `chain_error` | Retained metadata-handle cleanup and incomplete traversal outcomes. |
| `api_calls`, `observed_property_bytes`, `limits` | Bounded API-seam/raw-property accounting and exact requested budgets. |
| `physical_authority` | Always false; native `camera_activation_count` must be exactly integer zero. |

The wire receipt also requires exact status `METADATA_ONLY` and provenance
`WINDOWS_SETUPAPI_CONFIGURATION_MANAGER_METADATA`. Unknown keys, inferred
serial/speed fields, duplicate JSON keys, malformed observations, budget changes,
wrong endpoint, impossible chain/accounting, nonfinite numbers and inconsistent
exit status are rejected. No retry occurs. Transport timeouts/errors are metadata
failures, not claims of camera shutdown. A receipt claiming camera activation or
physical authority is explicitly flagged as an unexpected-effect uncertainty.

`exact_endpoint_observed` is true only when both mapping fields were observed,
the actual path equals the requested endpoint as an exact string, and mapping
cleanup has no reported errors. This is **not** a stable unit-identity guarantee.
`DEVINST` values are ephemeral host device-tree handles; do not persist or compare
them as a camera serial. No identity receipt grants activation; the existing
required `authorize(CameraActivationRequest)` gate on probe/capture is unchanged.

## Explicit flow and ownership

The caller supplies an `IdentityMetadataApi`, an exact opaque endpoint, limits,
and an injected monotonic clock/cancellation hook. No constructor initializes
COM, Media Foundation, SetupAPI, a camera source or any device handle. There is
no global metadata discovery, hidden first-camera selection or reconnect.

`WindowsIdentityMetadataApi` implements this explicit metadata-only sequence:

1. Create a local SetupAPI information set. Map the unchanged endpoint using
   `SetupDiOpenDeviceInterfaceW`; obtain its `SP_DEVINFO_DATA.DevInst` using a
   bounded two-call `SetupDiGetDeviceInterfaceDetailW` query. Retain the actual
   interface path independently from the supplied endpoint.
2. Delete the temporary interface entry and destroy the information set,
   retaining cleanup failures rather than claiming a clean result. These
   objects are metadata information handles, not camera capture handles.
3. Query `CM_Get_Device_ID_Size` and `CM_Get_Device_IDW` for whole device-instance
   identifiers. Do not split their suffixes into an invented camera serial.
4. Read `DEVPKEY_Device_ContainerId` and `DEVPKEY_Device_LocationPaths` through
   bounded `CM_Get_DevNode_PropertyW` queries. Preserve unavailable native error
   codes and their Win32/Configuration Manager domain.
5. Explicitly observe the device-tree root with
   `CM_Locate_DevNodeW(NULL, CM_LOCATE_DEVNODE_NORMAL)` and follow `CM_Get_Parent`
   through a bounded parent chain. A missing node/parent is **not** treated as
   successful arrival at the root. No phantom or cancel-removal flags are used.

`IdentityMetadata` reports the selected node, immediate-parent-first chain,
individually observed/unavailable instance IDs, container GUIDs, location paths,
mapping cleanup errors, termination reason and bounded accounting. Missing
fields remain unavailable; an observed empty list or zero GUID is retained as
observed data, not upgraded to unique identity. No serial, VID/PID, negotiated
USB speed, driver version, manufacturer or model is inferred from other fields.

## Bounds, typing and failure behavior

The pure resolver validates GUID property type and exact 16-byte layout;
`ContainerGuid` has explicitly decoded GUID components. Location paths must be
the expected UTF-16 `MULTI_SZ` type, with valid surrogate pairs, bounded text,
the final double NULL, and no ambiguous interior empty entries. Wrong types,
odd/truncated buffers, embedded NULLs and excess counts are not normalized away.

Defaults: at most eight ancestors, 16 KiB per raw property, 128 KiB accepted raw
property data, 1,024 UTF-16 code units per ID/path, 16 paths per node, five seconds.
The public native action/client fix the property/text/path budgets at these
defaults, expose only parent-count (0–16) and duration (100–30,000 ms), and cap
combined stdout/stderr at 256 KiB. The outer process timeout is the requested
duration plus five seconds for cleanup. The pure resolver library has wider hard
ceilings: 16 ancestors, 64 KiB per property, 512 KiB accepted raw property
data, 4,096 code units per ID/path, 32 paths, 30 seconds and 128 injected API-seam
calls. `api_calls` counts seam invocations, **not individual Windows API calls**;
some methods make a bounded size/read pair. No size-change retry is performed.
Property read allowances shrink with the remaining overall byte budget.

Cancellation, time expiry, a backward clock, an ancestor cycle, missing metadata
and a depth limit produce explicit incomplete results. A Windows call blocked
inside the system cannot be interrupted by the in-process clock checks. The
client therefore retains an outer native process deadline. Wizard integration
must retain the coordinator's admission and identity rules. Complete snapshots are not atomic
across plug/unplug; recheck the reviewed identity at the permitted pre-open
boundary and retain mismatches.

## Tests and dated build record

From the repository root, run each command separately and check its exit code:

```powershell
cmake -S software/native/windows_camera -B software/native/windows_camera/build -G "Visual Studio 17 2022" -A x64 -T v143 "-DCMAKE_SYSTEM_VERSION=10.0.22621.0"
cmake --build software/native/windows_camera/build --config Release --parallel 2
ctest --test-dir software/native/windows_camera/build -C Release --output-on-failure
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_windows_camera_worker.py software/tests/unit/test_windows_camera_identity.py -q
```

Observed on 2026-09-07: MSVC 19.42.34435.0, SDK 10.0.22621.0, CMake 3.31.3,
Windows x64 Release, `/W4 /WX`. The native test passed **43 assertions** using
only the incapable `FakeApi`: exact endpoint preservation, GUID/MULTI_SZ parsing,
missing/removed observations, selected node instead of an index, parent order,
root proof, cycles, depth/byte bounds, cancellation/deadline/clock failure and
retained metadata cleanup errors. It never constructs or calls the production
Windows API wrapper, accesses an actual device tree, opens cameras or writes
files. Compiling the concrete Windows API wrapper validates declarations and
linking, not its behavior against an installed driver.

See [identity_metadata_build_record.json](identity_metadata_build_record.json)
for the **historical pre-integration** library/test hashes. The current linked
helper and all relevant source hashes are in
[integrated_build_manifest.json](integrated_build_manifest.json). These are
unqualified development records, not signed registrations or activation permits.
The current helper links the resolver; its separate identity schema does not
alter the camera v1 receipt. `build_manifest.json` also remains historical: its
old camera source/CMake/executable hashes do not represent the current build.

The third CTest runs [identity_metadata_wire_test.py](identity_metadata_wire_test.py)
using the repository's existing `.venv`. It starts only the incapable FakeApi
test executable and parses 22 actual native-serialized receipts through the
production Python parser: nominal/missing nodes, cycles, depth, unavailable root,
cleanup, empty/zero observations and cancellation at every seam boundary. It
never invokes the real helper metadata action. Python fixture tests additionally
reject malformed/forged IPC and verify helper registration and no automatic retry.
All three CTests and all 95 camera/identity Python tests passed.

## Integration work still required

- Integrate this explicit metadata provider into the wizard's source-bound
  coordinator and logs without running it from page load/status. Native/client
  support alone does not complete that application integration.
- Define binding assessment for container/topology observations without
  asserting that a port-bound device is uniquely identified or serial-equipped.
- Test the concrete SetupAPI calls with an instrumented Win32 seam, then test
  received B0477 enumeration, unplug/replug, reboot and device-removal races.
- Qualify bounds, cleanup, OS/API availability, package/source registration and
  identity revalidation in the existing process/lease/coordinator design.
- Keep physical acquisition, calibration, robot motion and contact authority
  closed until their separate release criteria are satisfied.

## Official references verified

- [MF symbolic endpoint attribute](https://learn.microsoft.com/en-us/windows/win32/medfound/mf-devsource-attribute-source-type-vidcap-symbolic-link): the opaque endpoint can be passed to `SetupDiOpenDeviceInterface`; a friendly name is a different attribute.
- [SetupDiOpenDeviceInterfaceW](https://learn.microsoft.com/en-us/windows/win32/api/setupapi/nf-setupapi-setupdiopendeviceinterfacew) and [interface detail retrieval](https://learn.microsoft.com/en-us/windows/win32/api/setupapi/nf-setupapi-setupdigetdeviceinterfacedetailw): map the interface in an information set and observe its devnode with bounded caller-owned buffers.
- [Device-instance ID size](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_id_size): the size excludes the terminating NULL; the resolver reserves it explicitly.
- [Device property retrieval](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_devnode_propertyw), [ContainerId](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-containerid) and [LocationPaths](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-locationpaths): preserve the declared GUID and string-list property types; locations represent device-tree metadata, not negotiated USB throughput.
- [Root devnode lookup](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_locate_devnodew) and [parent lookup](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_parent): root observation and parent traversal are separate, explicit operations.
