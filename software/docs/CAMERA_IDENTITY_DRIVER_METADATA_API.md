# Exact-endpoint driver metadata v2

This extension observes installed-driver metadata, not driver approval, firmware,
unit serial identity, USB operating speed, camera activation or physical release.
No existing helper registration or historical build artifact is replaced.

## Wire and Python API

Current native identity output uses `rocell.windows_camera_identity.v2`. Its
only additional root field is `driver`, either null or this closed object:

```text
driver = {devnode, provider, service, version, inf_path}
```

Each of the four strings has the existing exact observation fields
`{availability, value, error}`. `error` retains `{reason, domain, native_code}`.
Absent native properties stay UNAVAILABLE; strings are not manufactured from a
friendly name, an instance-ID suffix, a parent or a presumed Microsoft driver.

`NativeWindowsDriverMetadata` is frozen and exposes the five fields above.
`NativeCameraIdentityReceipt.driver` is that type or None;
`.protocol_schema` retains the exact decoded version. The existing
`parse_camera_identity_receipt(value, *, expected_endpoint, duration_ms,
max_parent_nodes)` accepts strict v1 and v2 shapes. A v1 root rejects `driver`
and returns None, meaning **NOT_RETAINED**, not an unavailable OS observation.
The v2 root requires `driver`; it is null exactly when no device metadata was
retained. An existing device requires a driver object bound to its exact mapped
devnode, even if all fields remain NOT_REQUESTED after interruption.

The parser does not rewrite its input. Existing packet retention and enrollment
hash the complete original versioned packet. `rocell.windows_camera.v1` capture
and inventory schemas are unchanged.

## Native behavior and limits

After exact SetupDi endpoint mapping and completed device metadata, the resolver
reads, in order, `DEVPKEY_Device_DriverProvider`, `DEVPKEY_Device_Service`,
`DEVPKEY_Device_DriverVersion`, and `DEVPKEY_Device_DriverInfPath` through
`CM_Get_DevNode_PropertyW`. A nonmatching returned endpoint or failed mapping
cleanup prevents all four queries. Only the endpoint devnode is queried;
ancestor properties never substitute for an unavailable device field.

All queries share the original limits: default duration 5,000 ms, at most 128
API-seam invocations, 16 KiB per raw property, 128 KiB total accepted raw
property bytes, and 1,024 UTF-16 code units per decoded string. The four driver
fields consume that same budget; no new deadline or authority is issued.
`api_calls` counts seam invocations, not individual lower-level CM calls.
Stop/deadline before a later field preserves completed prior driver observations
and leaves unattempted suffix fields NOT_REQUESTED. Malformed/wrong-type fields
retain unavailable errors and do not suppress independent later observations.

The existing child wall timeout remains necessary for a synchronous Windows
call that does not return. The new code adds no CreateFile, hub IOCTL, COM/MF
activation, control, power, serial-port or installation operation.

## Verification and development artifact

`build-identity-driver` is a fresh, unqualified development build using the
existing MSVC 19.42.34435.0 toolchain and Windows SDK 10.0.22621.0. The separate
`identity_driver_build_record.json` records exact sources, binaries, commands
and executed results; it is not a runtime-release manifest.

Native tests use the incapable `FakeApi`, including exact property ordering,
unavailable fields, present-parent/no-fallback, disappearance, wrong type,
malformed UTF-16, property/total bounds, deadline, cancellation and cleanup.
Cross-language testing feeds actual fake-native serialization into the strict
Python parser. Python tests also retain v1 compatibility and exercise actual
enrollment/selection with clearly modeled v2 packets; successful endpoint
review still does not claim complete identity qualification.

Microsoft sources: [provider](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-driverprovider),
[service](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-service),
[version](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-driverversion),
[INF](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-driverinfpath).
These describe reported installed-device properties, not trusted package or
hardware acceptance. USB descriptor/operating-link queries remain a separately
designed capability, outside the no-device-open metadata taxonomy.
