# USB identity wire v1

All objects are closed: no extra fields. JSON is ASCII escaped from valid
Unicode code points, not UTF-8 bytes treated as Latin-1. Native receipt key order
is immaterial; the Python verifier canonicalizes the exact values. Admission
messages are canonical ASCII sorted compact JSON followed by one newline.
Hashes are lowercase SHA-256; identifiers are bounded ASCII identifiers.

## Admission and result

Request schema: `rocell.native_usb_identity_admission_request.v1`.
Its exact fields are:

```text
schema, attempt_id, session_id, source_sha256, operation_sha256,
selected_identity_sha256, native_identity_sha256, endpoint, endpoint_sha256,
expected_device_instance_id, expected_device_instance_id_sha256,
helper_sha256, runtime_registration_sha256, permit_sha256,
native_duration_ms, admission_timeout_ms
```

IDs are at most 96 characters. Endpoint/expected instance are nonempty strings
of at most 4096 UTF-8 bytes; each digest hashes the actual UTF-8 string. Request
including newline is at most 16 KiB. The only durations are 10000 / 5000 ms.

READY schema `rocell.native_usb_identity_admission_ready.v1` has exact fields
`challenge, child_pid, request_sha256, schema`. The challenge is 32 random bytes
represented as 64 lowercase hex characters. RELEASE schema
`rocell.native_usb_identity_admission_release.v1` has exact fields
`challenge_sha256, child_pid, permit_sha256, request_sha256, schema`. The
challenge digest hashes the ASCII challenge, not its decoded random bytes.
Each handshake line is at most 1024 bytes including newline.

Owned result schema `rocell.owned_usb_identity_result.v1` has exact fields
`schema, request_sha256, child_pid, challenge_sha256, permit_sha256,
native_receipt`. Native receipt is the full object below, not a hash substitute.
Exit codes: 0 OBSERVED, 1 HELD with receipt, 2 admission refusal, 3 failure to
produce/write a result after admission. No result after release is uncertain,
regardless of process cleanup.

## Receipt and subjects

Receipt schema `rocell.windows_usb_identity.v1` has exactly:

```text
schema, request_sha256, requested_endpoint, expected_device_instance_id,
outcome, pre_mapping, post_mapping, device_descriptor, languages,
serial_descriptors, link, accounting, calls, error, elapsed_ms
```

`outcome` is OBSERVED or HELD. Complete OBSERVED requires elapsed strictly below
10000 ms, identical complete mappings, a valid matching device descriptor, a
nonempty consistent serial in every advertised language, clean handles and no
root error. It does not require USB3 or available EX_V2, and is not qualification.

Mappings are null or objects with six keys:

```text
returned_endpoint: string|null
endpoint_instance_id: string|null
physical_usb_instance_id: string|null
physical_driver_key: string|null
host_controller_instance_id: string|null
hops: [{hub_instance_id, hub_interface_path, connection_index,
        downstream_driver_key}]
```

Each hop has three actual nonempty strings and a port 1..255. At most eight
hops, ordered from the selected physical USB unit outward to the host. Prefixes
and missing scalars remain partial; no ordinal or first-match selection.

Device subject is null or `{raw_hex, vid, pid, bcd_usb, i_serial_number}`.
Valid device bytes have length 18, descriptor type 1 and declared length 18.
VID/PID are four lowercase hex characters; bcd_usb is u16; serial index is u8.
All four decoded fields are null for malformed bytes; original raw remains.

Languages are null or `{raw_hex, language_ids}`. A valid string descriptor has
length 4..10, type 3, exact/even declared length and at most four distinct
nonzero u16 IDs. Malformed languages retain raw and an empty ID list. Serial
subjects are `{language_id, raw_hex, value}` in advertised language order. Valid
strings have exact/even declared length 4..255 and strict UTF-16 without NUL,
control characters or unpaired surrogates. Invalid `value` is null. Zero serial
index is SERIAL_NOT_PRESENT, never a generated or instance-derived serial.

Link is null or exactly:

```text
connection_status, ex_speed, ex_v2_available, supported_usb_protocols,
operating_superspeed_or_higher, capable_superspeed_or_higher,
operating_superspeed_plus_or_higher, capable_superspeed_plus_or_higher,
ex_raw_hex, ex_v2_raw_hex
```

EX raw is the full returned 35..4096 bytes. Packed offsets: port u32 at 0,
device descriptor 18 bytes at 4, speed u8 at 23, hub boolean u8 at 24, pipe
count u32 at 27, connection status u32 at 31. Status 0..10, speed 0..3,
hub boolean 0..1. At least `35 + 11*pipe_count` bytes must actually be retained.

V2 is independently available. Its raw is null if unavailable, otherwise the
returned bytes. Valid V2 is exactly 16 bytes: same port u32 at 0, length 16 u32
at 4, supported protocols bitmask 0..7 at 8 and flags bitmask 0..15 at 12.
Flag bits 1/2/4/8 map to the four booleans in the order above; operating-plus
requires operating-super. Malformed EX or V2 retains its raw and corresponding
decoded fields are null. Capability never becomes operation or an exact Mbps.

## Call trace and accounting

Each call has exactly sixteen fields:

```text
sequence, phase, operation, handle_id, target_id, connection_index,
requested_bytes, returned_bytes, returned_raw_hex, descriptor_index,
language_id, status, error_domain, error_code, observed_text, observed_number
```

Sequence starts at one. Phase is PRE, OBSERVE, POST or CLEANUP. Handle IDs are
local nonzero u32 tokens, not native HANDLE values; null when inapplicable.
Target is the actual DEVINST input token or null; port is 1..255 or null.
Requested/returned counts are integers 0..4096, with returned <= requested.
Status is OK or ERROR; domain is NONE, WIN32, CM or CONTRACT; error code is u32.
Observed text is actual metadata text or null, not the request text substituted
afterward. Successful MAP_ENDPOINT/PARENT/HUB_INFORMATION retain their actual
u32 result as observed_number; all other calls retain null.

Operations are closed:

```text
MAP_ENDPOINT, DEVICE_ID, PARENT, DRIVER_KEY_PROPERTY, HUB_INTERFACE,
HOST_CONTROLLER_PROPERTY, OPEN_HUB, HUB_INFORMATION, CONNECTION_DRIVER_KEY,
CONNECTION_EX, CONNECTION_EX_V2, DEVICE_DESCRIPTOR, LANGUAGE_DESCRIPTOR,
SERIAL_DESCRIPTOR, CLOSE_HUB
```

Successful EX/EX_V2/device/language/serial calls retain returned_raw_hex,
including empty/truncated bytes; other calls and failed IOCTLs retain null.
Descriptor raw excludes its 12-byte request header; call lengths include it.
Descriptor index/language are 0/0 for device/language queries, actual index and
language for serial queries, and null/null for every other operation. Selected
subject raw must exactly equal the original corresponding OBSERVE call raw.

Accounting has eleven fields, independently derived from the complete calls:

```text
api_calls, hub_open_attempts, hub_open_successes, ioctl_attempts,
ioctl_successes, descriptor_requests, close_attempts, close_successes,
peak_open_handles, remaining_open_handles, returned_bytes
```

These count closed semantic seams, not every internal OS call. Failed opens
have an assigned token but never enter the live set; failed closes remain live
and are never retried. A compound metadata read can retain bytes/text on ERROR
if its later information-set cleanup failed. This does not establish a mapping.

Root error is null or `{code, domain, native_code}`. Closed reason codes are
NOT_REQUESTED, REQUEST_INVALID, ENDPOINT_MISMATCH, DEVICE_CHANGED,
USB_ANCESTOR_MISSING, ANCESTRY_AMBIGUOUS, HUB_MAPPING_MISSING,
HUB_MAPPING_AMBIGUOUS, PORT_MISMATCH, NOT_CONNECTED, SERIAL_NOT_PRESENT,
SERIAL_AMBIGUOUS, DESCRIPTOR_MALFORMED, UTF16_INVALID, PROPERTY_TYPE, BYTE_LIMIT,
CALL_LIMIT, HOP_LIMIT, TIMEOUT, CANCELLED, API_FAILED, CLOSE_FAILED and
POST_MAPPING_FAILED. Late cleanup failure can supersede another reason without
removing its already retained raw evidence.
