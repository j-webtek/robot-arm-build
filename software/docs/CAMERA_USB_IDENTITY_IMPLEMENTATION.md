# Camera USB identity and onboarding implementation work order

Status: USB/host-boot acquisition components implemented and component-tested.
The successor [controlled dispatch work order](USB_IDENTITY_WIZARD_DISPATCH_WORKORDER.md)
now implements the owned helper, policy-bound original M1/application dispatch
and pure comparison codecs. Original-stage service and visible wizard actions
remain pending; internal dispatch is not a public connect feature.
Hardware execution NOT_RUN. This extends,
and does not replace, `CAMERA_ARM_DEVELOPER_PLAYBOOK.md` and
`CAMERA_IDENTITY_ONBOARDING_IMPLEMENTATION.md`. The destination remains the
usable camera/arm onboarding wizard, with later capture, calibration, startup,
noncontact tests and task execution. Completing this slice is not completing
that larger destination.

## Outcome and operator flow

The wizard must verify the selected overhead camera's actual USB identity and
operating connection, then compare separately retained baseline, disconnect /
reconnect and host-restart observations. It must show the compared values,
not just hashes. The purchased camera remains the nominal Arducam B0477 / IMX283
20 MP USB 3.0 model with the supplied nominal 16 mm lens; nominal product
information never fills received-unit observations.

1. Complete the existing original source, placemat/static-camera and received
   camera stages. Keep the original metadata-only identity assessment honest:
   it remains BLOCKED and is not retrospectively promoted.
2. Collect and review the generic camera, helper and native endpoint metadata.
   Refresh the original store explicitly after this metadata chain.
3. Inspect and review the separate USB-query helper and the exact selected
   endpoint, observed device instance and operation. A metadata-helper review
   is not permission to open a USB hub.
4. Explicitly collect a baseline USB observation and local host-boot record.
   Retain device/language/string descriptors, exact mapping, operating-speed
   categories, driver context, errors and resource cleanup outcomes.
5. Save the baseline, manually disconnect the camera, and collect a complete
   inventory proving the selected unit is absent. An inventory error, timeout
   or truncated enumeration does not establish absence. Reconnect manually;
   acquire a fresh selection and observation on the declared cable/port.
6. Persist the series and close all workers. Manually choose Windows Restart.
   Discover/select/reopen the original session explicitly after the restart;
   no permit, worker or live endpoint cache survives it. Collect fresh metadata,
   USB identity and host-boot evidence. A new app launch is not a reboot.
7. Present baseline/reconnect/reboot values and differences for separate review.
   Only complete consistent observations may make identity qualification
   eligible. USB2 operation, changed unit/host, absent serial, incomplete mapping,
   uncertain cleanup or missing boot evidence remain specific blockers.
8. Export the complete series and failures to the confirmed parent:
   `C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
   Retain readable values, provenance, hashes and coverage/redaction notices.
   Qualification does not release camera capture or arm power/motion/contact.

## Policy decision and historical compatibility

Use a new exact USB-query operation under the existing conservative
`BOUNDED_CAMERA_CAMPAIGN` effect and CELL -> SESSION -> CAMERA ownership.
Do not alter the seven-class authority policy or pretend this is
`READ_ONLY_OS_INVENTORY`: descriptor reads require a hub handle and USB control
requests. Introduce explicit versioned stage-4 admission/persistence and stage
catalog successors, rather than widening every physical-camera allowlist.

The new operation accepts only the currently reviewed camera target. It cannot
reset/cycle a port, change configuration, send vendor commands, activate Media
Foundation, acquire frames, set camera controls or access serial ports.
Record a durable attempt, consume one permit, verify the current source and
selection immediately before release, and retain the terminal evidence after
lease exit. Automatic retries are forbidden. Camera leases are cell-scoped;
they do not exclude other host applications or users of a shared USB hub.

Historical native binaries, registration manifests, fixed pins, policy-v1
records and camera metadata-v1/v2 readers remain unchanged. New native code
lives in `software/native/windows_usb_identity`. Old stage-5/6 permits cannot
become USB-query permits. V7 metadata-only identity records retain their exact
meaning; a closed additive successor must retain the new observation series.

Original session headers bind the source hash permanently. Initially use a
fresh original session under the new source/policy. Old source-bound stores
remain available for historical review/export, not silently rebound to this
build. Cross-build continuation requires its own audited lineage migration;
no implementation may substitute a current hash into an old header.

## Native request and producer contract

Implement a separate Windows adapter behind an injectable bounded C++ API.
Construction is inert. Real API construction/device access follows a parent-
owned READY/RELEASE exchange and EOF, never arbitrary command-line endpoints.
The only production entry is an owned request with its exact SHA-256; pure
resolver/admission tests are separate executables.

The canonical ASCII request is at most 16 KiB. Its exact fields are schema,
attempt_id, session_id, source_sha256, operation_sha256,
selected_identity_sha256, native_identity_sha256, endpoint, endpoint_sha256,
expected_device_instance_id, expected_device_instance_id_sha256, helper_sha256,
runtime_registration_sha256, permit_sha256, native_duration_ms and
admission_timeout_ms. READY/RELEASE bind request, child PID, random challenge
and original permit. Fixed gate/native limits are 5 s / 10 s; a parent deadline
and cleanup bound must also contain a stuck Windows call without claiming
that process termination proves USB cleanup.

Receipt schema `rocell.windows_usb_identity.v1`, maximum 64 KiB, exact fields:
schema, request_sha256, requested_endpoint, expected_device_instance_id,
outcome, pre_mapping, post_mapping, device_descriptor, languages,
serial_descriptors, link, accounting, calls, error and elapsed_ms.
`OBSERVED` means a complete stable identity observation, not qualification or
USB3 operation; `HELD` retains incomplete/error evidence. No PASS field.

- Mapping retains the returned endpoint, endpoint instance, physical USB
  instance, physical driver key, host controller and at most eight ordered
  hub/port hops. Authenticate each port using the downstream device driver
  key. Partial fields/prefixes remain nullable; ambiguity must not select the
  first match. Recheck mapping after observation and retain both results.
- Device descriptor retains raw hex, VID/PID, bcdUSB and iSerialNumber.
  Language descriptor retains raw bytes and at most four language IDs.
  Serial descriptors retain language, raw bytes and strict UTF-16 value.
  Zero serial index is unavailable, never an inferred instance-ID suffix.
  Conflicting language strings stay held.
- Link observation retains connection status, EX speed and raw EX bytes;
  independent EX_V2 availability, protocol and operating/capable flags plus
  raw EX_V2 bytes. Retain the complete EX header plus any reported pipe list
  (35..4096 bytes); V2 is 16 bytes. Malformed returned descriptors/link bytes
  remain in HELD evidence with null decoded fields, never silently dropped.
  Missing V2 fields are null. Do not derive an exact Mbps
  value from an "or higher" category or confuse capability with operation.
- Retain at most 128 call rows, each with sequence, phase, operation, handle
  token, target, port, requested/returned bytes, status, error domain/code and
  observed metadata text. Retain `observed_number` for successful endpoint
  mapping, parent lookup and hub-port count, and null otherwise. Retain exact
  `descriptor_index` / `language_id` for descriptor queries (zero/zero for
  device and language-list requests), and null otherwise. These are checked
  against the serial index and supported languages, not inferred afterwards.
  Enumerate only the fixed allowed operations.
  `returned_raw_hex` retains every successful EX/V2/descriptor payload,
  including malformed scans before or after the selected observation; other
  calls/failed IOCTLs carry null. The decoder checks each scanned port's status
  and complete driver-key coverage against these bytes, and binds selected
  raw subjects to their actual call rows. A failed required query cannot be
  hidden by a later successful retry in an OBSERVED result.
  Account for all closed API-seam calls, opens, IOCTLs, descriptor requests, closes,
  returned bytes, peak live handles and remaining handles. No raw HANDLE.
  Cap total hub opens at 32, live handles at one, individual buffers at
  4096 bytes and USB string descriptors at 255 bytes. Reserve evidence and
  cleanup capacity before an operation; budget exhaustion retains HELD,
  never silently drops observations or leaks a handle. The API-seam count is
  not a count of the adapter's internal bounded CM/SetupAPI calls. A compound
  metadata read may retain observed bytes when its later information-set
  cleanup fails; that is still a HELD observation, not a successful mapping.
  Descriptor
  IOCTL byte counts include the 12-byte request header; raw descriptor fields
  retain only the returned payload. Thus a serial request can reserve 267
  bytes while its descriptor payload is bounded to 255 bytes.

The producer and Python decoder independently enforce field sets, sizes,
descriptor decoding, trace/accounting consistency and complete-observation
requirements. Native errors retain a closed reason, domain and numeric code.
An unconfirmed close cannot become a successful clean observation.

## Host-boot observation contract

Use a separate explicit local read of supported CIM properties:
`Win32_OperatingSystem.LastBootUpTime` and
`Win32_ComputerSystemProduct.UUID`, with OS version/build as context.
Use fixed command/class/property names, no remote host or arbitrary query.
Import and construction perform no DLL, process, filesystem or device calls.
The actual executor must impose output, process-tree and deadline bounds;
checking output length after unbounded subprocess buffering is insufficient.

Retain the exact bound request, provider response, command/script hash,
execution outcome, observation timestamps, stdout hash/length and cleanup
evidence. Separate full observation hash, stable host key and stable boot key.
The boot key contains only the verified host key and normalized observed boot
timestamp, never PID, launch ID or time-now minus uptime. Reject unavailable,
all-zero/all-one UUIDs, malformed/ambiguous dates and inconsistent chronology.
Comparisons are SAME_HOST_SAME_BOOT, SAME_HOST_DIFFERENT_BOOT or HELD.
Provider-reported boot epochs are not cryptographic host attestation; Fast
Startup can retain the kernel session and must not count as an assumed reboot.

## Independent implementation lanes

- Native agent: new native producer, adapter, admission, CMake and fake tests;
  send exact cross-language fixtures; do not edit historical camera sources.
- UI agent: new host-boot contract/provider with hard-bounded execution and
  fake tests; then real-service operator phase/comparison integration.
- Evidence agent: versioned identity qualification series and original-store
  integration after the native/boot API agreement. Preserve all old readers.
- Root: strict Python USB decoder, policy/admission and service integration,
  native/Python conformance, full workflow tests and evidence ledger.

Before production Python/config edits, reconcile the frozen f177 compatibility
run. New native sources and this document do not change that source hash.
Keep each change's current-source test results distinct from historical runs.

## Verification and definition of done

First exercise native fake API -> actual wire -> strict Python parser. Cover
composite ancestry, duplicate port matches, missing serial, malformed/truncated
descriptors, language conflicts, USB2 versus USB3 capability/operation, mapping
drift, deadline/cancellation, failed closes and exhausted evidence budgets.
Test actual producer output, not only hand-authored JSON fixtures.

Then exercise the real coordinator/original persistence -> sealed incapable
worker -> terminal readback -> identity service. Verify wrong target/source,
stale metadata, expired or reused permit, Stop and late results cannot advance
the stage. Preserve failed/partial evidence for export without replay.

Join baseline, observed absence, reconnect and host-reboot records with exact
received-label serial correlation and reviewer subjects. Test same-launch /
new-launch versus same-boot / changed-boot independently; changed unit or host
must not pass. Test actual file-store restart/export and both wizard UIs.
Positive hardware facts in all pre-arrival tests are explicitly modeled.

Only declare this slice complete when the callable wizard can perform and
retain the intended sequence through the owned implementation, display values
and blockers, export the whole series, and recover safely after restart.
Native code alone or a modeled PASS is not completion. Hardware acceptance
remains NOT_RUN until the actual received equipment is tested.

## Official references reviewed for this decision

- [Microsoft descriptor IOCTL](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ni-usbioctl-ioctl_usb_get_descriptor_from_node_connection)
  targets a USB hub and retrieves descriptors for an indicated port.
- [Microsoft EX_V2 structure](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ns-usbioctl-_usb_node_connection_information_ex_v2)
  distinguishes port protocols and device operation/capability flags.
- [Device driver key](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-driver)
  and [hub-port driver key](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ni-usbioctl-ioctl_usb_get_node_connection_driverkey_name)
  support the explicit mapping join.
- [Windows OS properties](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem)
  and [system UUID](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-computersystemproduct)
  define the boot-time and host metadata used here.

## Executed evidence

Plan committed before implementation. No USB/CIM/device operation was executed
to prepare this work order or exercise these tests.

- `usb_identity_protocol.py`: strict, inert request/READY/RELEASE codecs and
  immutable USB observation decoder. Independently validates raw descriptor
  decoding, speed flags, complete before/after CM/hub/port traces, exact serial
  query parameters, call/handle accounting and owned-result binding. Black and
  mypy pass. The expanded admission/receipt/fault suite passed 305 tests in
  1.05 s. This includes malformed raw evidence, failed-call retry rejection,
  exact selected-subject bytes and wrong connected-port claims.
- New `software/native/windows_usb_identity` project compiles with the existing
  MSVC/Windows SDK. Its real adapter is compiled, never executed. The separate
  fake producer contains no Windows USB adapter. Actual fake-produced JSON
  passed the Python decoder for all 21 final scenarios: nominal, Unicode,
  USB2, pipe lists, unavailable V2 and sixteen held/error cases. Nominal was
  24,549 bytes, 65 semantic API calls, five opens/five closes, peak one handle
  and zero remaining handles. The 33,263-byte maximum-raw case retained three
  full 4,096-byte scan payloads, stopped at BYTE_LIMIT and closed both opened
  handles. These are modeled device observations only.
  All three native CTests passed in 5.81 s: 94 native assertions, the 21
  request-bound wire cases and seven inherited-pipe admission cases. The latter
  uses the actual full Python owned-result parser. New C++ was formatted and
  rebuilt with warnings treated as errors; historical native files/pins remain
  unchanged. The compiled-only USB executable SHA-256 is
  `0f5555ac77835cee3d21d969085b355128006c18b5c4819051137fa5b18ec8c1`.
  The [component build record](../native/windows_usb_identity/BUILD_RECORD.json)
  binds 18 inputs and three artifacts; root independently checked all 21
  size/hash pairs. Record SHA-256:
  `5e570a8d583eff9b8cb663a02f37bbcc15a0e915cee747b8bbe7785e3441135a`.
  Root also independently reran all three CTests successfully in 5.80 s.
- [Host-boot implementation](HOST_BOOT_OBSERVATION.md): callable fixed local
  CIM provider, bounded owned process, immutable record and pure comparisons.
  Root independently reran 74 focused tests in 1.67 s. The agent's combined
  host-boot/existing owned-process selection passed 126 tests in 6.50 s.
  Actual CIM invocation is NOT_RUN; injected bytes and a separately sealed
  incapable child exercised parsing, output limits, timeout and cleanup.
- The historical frozen-source checks are recorded in the prior identity
  work order, including 820 original/source tests passed and two repaired
  test-only UI fixture expectations. Do not add overlapping counts or call
  those old results a full regression of this changed source.
- Final root integration selection: USB protocol + host-boot + repaired
  configuration-record service tests passed **400 tests in 4.73 s**. These
  overlap the component results above; do not sum them as unique tests.
  Three Python files pass Black and both new provider/codec modules pass mypy.
- Both supported launcher `-Check` modes passed on final source
  `d214cfea3e91419e97e9e60b20e1cf4b01b42f9a8e879cee1baebd19e0e2dc2a`:
  READY_FOR_DIAGNOSTICS, workspace export parent, identity NOT_STARTED,
  zero operations and physical authority false. No server/device was opened.

### What is not yet joined

The wizard currently exposes the earlier metadata submission/review/export,
not these new USB/boot operations. The new helper has no accepted runtime
registration or original stage-4 execution grant. Next implement the exact
USB preparation/owned parent runner, reviewed stage-policy/persistence
successor, baseline/absence/reconnect/reboot original series, separate review
and value-by-value UI/export. Then continue qualified capture/settings,
installed calibration and separately gated RoArm startup/feedback/tasks.
Neither a passing fake test nor the existence of a hardware-capable executable
means the application can yet run the full hardware onboarding sequence.
