# Read-only diagnostic transport candidate

Latest entry-path revision: `--diagnostic-boot` generates
`diagnostic-boot-candidate`, preserving the earlier candidates. It replaces
reference setup/loop and registers diagnostic routes only, with no startup servo
transactions or legacy command ingress. See `SERVO_DIAGNOSTIC_DEPLOYMENT_REVIEW.md`
for exact behavior changes and remaining deployment requirements. The warnings
below about inherited startup behavior apply to the earlier transport/baseline
candidates, not the new diagnostic-only entry path. No candidate is installed or
approved for deployment, and no diagnostic start route is exposed yet.

This is source under review, not an installed interface or approved image.
Generate with `software/scripts/prepare_owner_firmware_candidate.py --transport`;
compile with `software/scripts/compile_diagnostic_reference.py transport-v2-candidate`.
The source-verified baseline and owner candidate remain unchanged.
The earlier `transport-candidate` directory is preserved as the v1 build baseline.

The newer internal-session integration is generated with `--received` and compiled
as `baseline-candidate` (the earlier `received-candidate` is preserved). It uses
the real converter, fresh-baseline gate and timed session and blocks
ordinary command/background interference while owned. Its internal start API is
not registered as a network or serial command. It remains nondeployable pending
admission, compatibility and startup-behavior review; see the main plan for build evidence.

## Endpoints in the candidate

- `GET /rocell/diagnostics/status`: session state, first fault reason, retained
  record count, storage-fault flag. `start_supported` and
  `durable_export_verified` are explicitly false.
- `GET /rocell/diagnostics/record?index=0`: repeatable indexed retrieval of a
  retained record with kind and record body. No consumption/acknowledgment occurs.
  Invalid indexes return 400; absent records return 404. Responses use no-store.

Both handlers run through the existing synchronous server owner. They never
dispatch, sample the bus, reset a session or delete evidence. The static store
contains 16 records of up to 2047 JSON bytes each, outside the task stack.
The v2 successful responses include the same 128-bit hexadecimal instance ID,
generated once at route registration after Wi-Fi initialization. It distinguishes
controller boot instances but is neither a secret nor authenticated provenance.
The host checks it on every record and the final status, including when a reboot
would leave the same record count. Legacy v1 collection remains available with
`instance_identity_bound=false`, never movement authority.
Session reservation permits at most 12 pairs with the four current boundary
records; future receipt/status records must reduce or explicitly revise this
budget. The baseline candidate reserves six boundary records and therefore allows
at most ten pairs. It retains the baseline read pair and selected delta/tracking/
age/span limits under record kind `baseline`, between receipt and conversion.
RAM retention is lost on reset and is not a durable host export.

## Scope and gaps

### Host read-only adapter

`rocell.application.servo_diagnostic_http.DiagnosticHTTPReader(address, port=80)`
implements the collector's `get_bytes` interface. Construction performs no I/O.
Use an explicitly selected numeric private-LAN IPv4 address (loopback is available
for tests), only after checking installed diagnostic capability. It has no DNS,
environment-proxy, redirect, retry, command, reset, or fallback behavior. Each GET
uses a new connection and a total deadline of at most three seconds across connect,
send, headers, and body. Headers are limited to 8192 bytes; bodies to 512 bytes for
status and 2304 for records. Only fixed-length uncompressed JSON responses with
HTTP 200 are accepted. I/O or protocol failure latches that reader against reuse.

Pass the reader to `collect_planned_run` with the independently prepared command,
policy, original payload bytes, sampling schedule, and baseline policy. That path
persists and verifies the frozen plan before the first GET. A successful HTTP
response does not establish device identity, firmware compatibility, successful
motion, or physical accuracy. Contract validation and export verification remain
separate requirements. Do not construct an automatic retry with a new reader.

The adapter is not automatically wired to startup or the wizard: no installed
endpoint support has been established, and no hardware traffic was used to test
it. Loopback tests cover real socket collection/export/replay, malformed framing,
redirect rejection, truncation, oversized headers/bodies, compressed/chunked
responses, slow-trickle total deadlines, proxy bypass, and command-route rejection.

No start endpoint is exposed yet. Ordinary reference command routes remain
unchanged, and do not produce these diagnostic records. The installed arm does
not gain this capability by compiling the candidate. Native receipt binding,
cross-ingress admission, sample timing, command-session identity on transport,
host verification/export, and authenticated deployment review remain unfinished.

The server retains the reference's unauthenticated LAN access model. Do not
expose it to the internet or interpret a returned JSON record as authenticated
device provenance. Review authentication and permitted clients before enabling
a diagnostic command ingress.

The candidate still contains reference startup movement and servo-configuration
writes. Deployment requires explicit approval plus compatibility, backup/recovery
and startup-behavior review. No firmware upload or live movement is authorized by
these read-only handler tests.
