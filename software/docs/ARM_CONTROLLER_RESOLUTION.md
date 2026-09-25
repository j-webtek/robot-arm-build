# Exact pre-open controller metadata resolution

This increment implements the missing metadata resolver used by
`ArmFeedbackWorker.identity_resolver`. It does **not** enable the physical worker,
open a serial port, qualify the received arm/firmware, or establish an atomic
mapping between a COM name and an opened handle. No actual device enumeration or
native DLL execution was used for verification.

## Existing gap and implemented join

The worker already invokes its resolver before creating/opening a serial object
and again after the quiet interval, immediately before its single feedback write.
Previously its concrete callers supplied rehearsal resolvers only. The generic
inventory alone is insufficient: its `os_instance_id` is pySerial HWID text and
its `driver_service` retains the interface description. Neither field is silently
promoted to a native PnP instance or driver service by this implementation.

New files:

- `src/rocell/application/arm_controller_resolution.py`: strict immutable
  observations/snapshot, pure comparison, small hash-bound diagnostic result and
  the directly usable callback.
- `src/rocell/providers/windows/controller_metadata.py`: explicit, lazy,
  metadata-only Windows Configuration Manager acquisition.

```python
# Construction is inert. Only an eventual explicit worker execution invokes
# the metadata callback; the existing native availability gate still refuses
# execution before authorization or metadata acquisition in this revision.
acquire = WindowsControllerMetadataAcquirer(
    deadline_ns=exact_request.expires_monotonic_ns,
    cancellation=cancel,
)
resolve = ExplicitArmControllerResolver(
    exact_request.controller,
    acquire,
    deadline_ns=exact_request.expires_monotonic_ns,
    cancellation=cancel,
)
worker = ArmFeedbackWorker(
    authorizer=existing_exact_authorizer,
    identity_resolver=resolve,
    backend=existing_nonpurging_backend,
)
```

This snippet is a software join, not a release procedure. Neither module is
wired into the public wizard or the physical worker's availability gate. An
external caller still owns the reviewed binding, exact source/stage/power
authorization, deadline and separately qualified process supervision. Callback
providers are trusted internal code, never browser-selected callables or paths.

## Exact comparison and unavailable values

`ControllerNativeMetadata` retains the observed interface symbolic path, its
associated device-instance ID, COM property, typed VID/PID properties, and the
driver provider/service/version/INF fields. Unknown optional properties remain
`None`; review values never fill them. Instance/path equality selects the native
row. COM, USB identity and driver fields are subsequent exact comparisons, not
fallback selectors. Duplicate instance/path, COM or generic USB-unit observations,
incomplete collections, missing properties and changed values produce `HELD`.

Unit serial remains explicitly sourced from the existing generic serial
inventory. It is not obtained by parsing the native interface path or copying
the reviewed identity, and is **not verification of a USB string descriptor**.
Generic manufacturer/product values are retained as observed, including `None`.
The existing `RoArmUsbSerialIdentity` type has nominal arm/model/controller
constants; returning that type does not turn those constants into observations.
Installed model, firmware, boot behavior, physical power, duplicated manufacturer
serials, and COM-to-open-handle identity need separate received-hardware work.

`resolve_controller_metadata(reviewed, snapshot)` is pure and returns a
`ControllerResolution` with immutable `payload`, `sha256`, detached `to_dict()`,
`safe_summary()`, and `identity` only when the comparison matches. A successful
status is `MATCHED_METADATA_ONLY`, never a canonical stage PASS or qualification.
The safe summary omits raw endpoints, COM names, driver paths and generic text.
The full diagnostic retains actual compared metadata and its source hashes; it
is not an M1 identity receipt or a replacement for the original reviewed binding.

`ExplicitArmControllerResolver` matches the existing callback protocol exactly:
`resolver(expected_identity) -> RoArmUsbSerialIdentity`, or it raises a fixed-code
`ControllerResolutionError` recognized by the worker. It accepts at most two
attempts, obtains a fresh bracketed snapshot for each, checks cancellation and
the unchanged absolute deadline, and never retries or reuses a previous snapshot.
Construction/status perform no acquisition, file read, clock read or DLL load.

## Windows acquisition and bounds

Only five fixed metadata functions are bound, through a lazily loaded
System32 `cfgmgr32.dll`:

1. Enumerate present `GUID_DEVINTERFACE_COMPORT` interfaces using the list-size
   and list functions. No device filter, arbitrary GUID, COM selector or friendly
   name is supplied.
2. Read each interface's `DEVPKEY_Device_InstanceId` and the serial PortName,
   UsbVendorId and UsbProductId properties with exact property-type validation.
3. Locate the associated configured devnode using `CM_LOCATE_DEVNODE_NORMAL`,
   then read its DriverProvider, Service, DriverVersion and DriverInfPath.
4. Re-enumerate the interface list and generic serial metadata before returning.
   Observed boundary changes remain a collection hold, not an automatic retry.

No `CreateFile`, serial object, device handle, COM line control, purge, write,
reset, driver install, registry mutation or phantom/cancel-remove operation is
implemented. A DEVINST is a metadata identifier, not an open port handle.

Bounds: 128 candidates, 128 KiB interface-list buffer, 2048 bytes per native
property, 1 MiB cumulative allocated native buffers and 4096 native calls per
acquirer instance, two explicit acquisitions, and one retry for a list-size race.
Pure snapshot encoding is capped at 2 MiB and resolution diagnostics at 32 KiB;
over-limit data is rejected, not truncated. All buffer budgets are checked before
allocation/content reads. Property growth/type changes, malformed UTF-16 and
unexpected API errors refuse the acquisition. Only an explicit missing-property
result becomes `None`.

The deadline is checked before/after native calls, but a synchronous native call
may stall past it. These checks are **not hard process containment**. Before/after
metadata observations also cannot prevent unplug/replug or COM reassignment
between a check and open/write. No atomic handle identity or fresh native
qualification is claimed. The fixed physical release hold is unchanged.

## Verified references and tests

Microsoft recommends discovering COM interfaces through
[GUID_DEVINTERFACE_COMPORT](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/guid-devinterface-comport);
legacy COM names can collide. The acquisition uses its fixed GUID and compares,
but never selects by, the reported COM property.

The present-device filter, symbolic-link result and list-size race behavior are
specified by [CM_Get_Device_Interface_ListW](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_interface_listw).
Interface metadata follows
[CM_Get_Device_Interface_PropertyW](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_interface_propertyw)
and Microsoft's [serial interface publication example](https://learn.microsoft.com/en-us/windows-hardware/drivers/serports/device-interface-publication-sercx).
Configured devnode lookup uses only the normal flag documented in
[CM_Locate_DevNodeW](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_locate_devnodew);
driver properties are obtained with
[CM_Get_DevNode_PropertyW](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_devnode_propertyw).
Property GUIDs/PIDs/types were also checked against the installed Windows SDK
10.0.22621.0 `devpkey.h` and `ntddser.h`, including the shared device/interface
instance-ID key. No guessed serial-number property or interface-path parsing is
used.

The focused suites are `test_arm_controller_resolution.py` and
`test_arm_controller_metadata_windows.py`. They exercise exact native ABI buffer
parsing through injected C functions, actual existing inventory normalization,
the actual `ArmFeedbackWorker` and sealed non-purging Win32 model, before-open and
before-write identity drift, missing/duplicate/partial metadata, cancellation,
stale snapshots, malformed property/list data and resource bounds. They prohibit
native DLL loading and host enumeration. These tests establish the software join,
not native OS execution, received-arm identity, handle binding or physical release.

Source-frozen validation: **86 new tests**, plus the existing feedback-worker
and non-purging-adapter regressions, **200 passed in 1.26 seconds**. This includes
the full injected CM reader → exact resolver callback → actual incapable
feedback-worker composition. Both new source modules pass mypy; formatting is
clean. The default Windows DLL-loader test substitutes the DLL boundary itself
and checks the fixed System32 load request without executing a native library.
