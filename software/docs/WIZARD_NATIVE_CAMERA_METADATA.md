# Native camera metadata bridge

This is the explicit metadata connection between the existing Windows client
and wizard enrollment. It does not probe modes, open a source, capture pixels,
change controls, issue authority or qualify the received camera. No helper is
discovered automatically; the application must independently review any runtime
client registration before composing a native provider. The workbench now
provides a [fixed-file inspection and metadata-only registration workflow](WIZARD_CAMERA_HELPER_REGISTRATION_API.md)
around this adapter; it does not grant camera activation or release approval.

## Public contract

`NativeCameraMetadataProvider(client)` exposes inert `descriptor()`, explicit
`inventory()`, and `identity(candidate: CameraCandidate)`. Its cached immutable
descriptor contains exactly `provenance` and `helper_sha256`. The native adapter
uses `WINDOWS_NATIVE_METADATA`; this declaration alone is not origin or hardware
qualification evidence. Construction and descriptor access perform no I/O.

Inventory calls only `client.enumerate_metadata(duration_ms=5000)`; identity
calls only `client.resolve_identity_metadata(candidate, duration_ms=5000,
max_parent_nodes=8)`. The private wire sink is supplied to those calls. Helper
path, declared digest and runner identity cannot silently change after adapter
construction. The existing client checks helper bytes during each explicit
action. Filesystem TOCTOU and qualified owned-process integration remain separate
work; this adapter does not release physical admission or auto-reconnect.

Each action returns a plain packet with exactly these fields:

```text
schema: "rocell.wizard_native_camera_packet.v1"
kind: "inventory" | "identity"
provenance: "INCAPABLE_FIXTURE" | "WINDOWS_NATIVE_METADATA"
helper_sha256: lowercase SHA-256
receipt: full original decoded native wire receipt
```

`validate_native_packet(packet, *, kind, provenance, helper_sha256,
expected_endpoint=None)` returns `(canonical_owned_packet, typed_receipt)`.
Supply independently trusted descriptor values, and an exact server-owned
endpoint for identity. Inventory must not select an endpoint. Validation is
pure: no files, processes, native APIs, workers or replay. Bounds are 256 KiB
canonical JSON, depth 16, 4096 nodes, 128 entries per container and 16 KiB per
string, with only plain JSON types and signed-64-bit integers. Typed receipt
counts/limits do not alias the returned mutable packet.

Inventory uses the public pure `parse_camera_inventory_receipt` and the same
strict native-v1 parser as the client. Effects, modes, control observations and
sample artifacts are forbidden. Identity uses the existing separately versioned
strict parser. Observed/unavailable values, native error codes, parent limits and
zero activation/authority remain explicit. A complete metadata receipt may
describe failed cleanup or unavailable mapping; its existence is not acceptance.

## Lossless retention seam

The client metadata methods accept optional `wire_receipt_sink(bytes)` after
strict parsing and process-exit consistency. It receives bounded immutable
canonical JSON preserving all decoded wire fields, including raw cleanup
HRESULTs and COM flags which the typed inventory summary otherwise loses.
Whitespace/key order are canonicalized; observations are never reconstructed.
Sink failure fails the call and does not retry. Capture/probe signatures and
receipt schemas are unchanged. The bridge uses one local sink per call, not a
shared last-receipt cache, and reparses the retained wire to check agreement.

## Incapable fixtures and tests

`RehearsalNativeCameraMetadataProvider(scenario="nominal")` supports exactly
`nominal`, `missing-mapping`, `wrong-device` and `duplicate-name`. All scenarios
have the same inert fixture descriptor/hash and always return
`INCAPABLE_FIXTURE`. Its inner Windows wire vocabulary exercises parsers and is
not a claim that Windows was queried.

Nominal mapping retains instance `USB\VID_FFFE&PID_0001\SYNTHETIC-CAMERA-A` and
container `11111111-2222-3333-4444-555555555555`. Missing mapping has unavailable
observations; wrong-device changes instance/container; duplicate-name exposes
two exact endpoints sharing a label. No serial, USB speed, firmware or received
Pro identity is inferred from these fields. Fixture identity rejects candidates
outside its closed scenario; wizard enrollment must enforce its own current
candidate/revision binding too.

`test_wizard_native_camera_metadata.py` covers real parser validation, bounds,
copy isolation, metadata-only effects, all scenarios, registration drift, exact
cleanup retention and sink failures. Native-adapter tests inject an incapable
runner reading/writing only private fixture files; they never run a helper,
enumerate host devices or open hardware.
