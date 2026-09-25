# Bounded physical USB-node presence helper

Development implementation only. The production executable builds, but it has
**not been run against hardware or qualified for wizard dispatch**. This helper
does not modify the historical `windows_usb_identity` executable or build pins.

The local Windows adapter performs at most four Configuration Manager API calls:
size/list twice, using the same fixed PRESENT + ENUMERATOR filter each time.
The filter is the USB device-ID portion of a previously observed exact physical
instance. Composite `&MI_` interfaces, camera endpoints, root IDs and guessed
indexes are rejected. At most 8,192 UTF-16 characters and 64 IDs per sample are
accepted. The native acquisition ceiling is two seconds; a future qualified
parent must independently enforce its original process/cleanup deadline because
a blocked OS call cannot be interrupted by a clock check inside this process.

Successful results mean that the exact physical device node was PRESENT or
ABSENT at two complete observation instants. They do not prove continuous
absence, mechanical cable removal, power isolation or authenticated identity.
The other same-model device does not count as the selected target. List errors,
growth races, malformed termination, duplicates, mismatched filters, deadline,
clock regression and Stop produce HELD. Returned error codes survive late
checks; a call that throws without returning has `native_code: null`.
Unexpected exception text is not copied into diagnostics.

The adapter opens no hub/device handle, sends no descriptor IOCTL, captures no
frame and makes no configuration or power change. It does not disable/remove a
device. The selected node must come from authenticated original baseline
evidence in the later application join, not a string typed into the browser.

## Wire and integration

`providers/windows/usb_presence_protocol.py` is the strict pure Python codec.
The native child accepts only the purpose-specific owned argument shape and
canonical request through inherited pipes. It emits READY with a random
challenge and its PID, requires matching RELEASE plus EOF within the unchanged
five-second admission window, and only then constructs the API adapter.

The sixteen-field request binds source/session/attempt, selected identity,
operation, phase binding, target/hash, helper/runtime, permit and request nonce.
`phase_binding_sha256` must be derived by the future original-series owner from
the plan, trial/phase/launch and exact baseline/boot references. This codec does
not issue a permit or authenticate those originals. The resulting wrapper binds
request, PID, challenge and permit. The Python decoder independently checks the
exact request and expected real-versus-incapable provider origin.

Remaining before use: original-store phase binding and admission, reviewed
runtime registration, actual one-process Job/pipe owner with independent cleanup
accounting, retained original run evidence, a versioned qualification-series
join and explicit service-backed UI collection. Do not invoke this executable
manually as a substitute for that integration.

## Build and hardware-free verification

From the repository workspace root, with the already installed MSVC/SDK/CMake:

```powershell
cmake -S software/native/windows_usb_presence -B software/native/windows_usb_presence/build -G "Visual Studio 17 2022" -A x64
cmake --build software/native/windows_usb_presence/build --config Release
ctest --test-dir software/native/windows_usb_presence/build -C Release --output-on-failure
```

The production target alone links `windows_api.cpp` and `cfgmgr32`. The two
separately linked test binaries contain only the incapable adapter. The test
group covers the native core, cross-language observation decoding and actual
READY/RELEASE/EOF/error/deadline entry behavior. Direct child wire tests do not
qualify an M1 transaction or Job owner. No production executable is selected by
these tests. The strict flat JSON parser and SHA implementation are reused from
the prior module without changing its source.

Verified development build: MSVC 19.42.34435.0, Windows SDK 10.0.22621.0, x64
Release. Three CTest groups passed in 6.53 seconds. Compilation initially found
Windows SDK header ordering after formatting; the local format configuration
now preserves required include order. See [BUILD_RECORD.json](BUILD_RECORD.json)
for the final source/artifact hashes, not an installation approval.

Official API semantics:
[present device-ID lists](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_id_listw)
and [allocation size versus actual list length](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_id_list_sizew).
