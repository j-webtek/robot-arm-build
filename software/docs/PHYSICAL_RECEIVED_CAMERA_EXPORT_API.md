# Received-camera metadata export

`physical_received_camera_export.export_received_camera_metadata(diagnostics,
*, export_parent, source_sha256, launch_id, cancellation, deadline_ns)` returns
the unchanged `WizardDiagnosticExporter` receipt. This is an explicit local
file export, not an M1 transaction or an approval. It reads no original store,
input inbox, media, device or native API. The caller owns current source checks
and publication of the completed receipt.

The input is the complete server-owned
`rocell.wizard_received_camera_diagnostics.v1` cache. Historical publication and
original source/session/actor bindings remain unchanged; the export's separate
source and launch identify the caller. The original reader's four cycle roles
and raw-original descriptors have closed keysets. Raw original bytes are never
accepted as JSON metadata. The helper does not replace the original typed
subject or journal verifiers.

## Complete families, existing limits

There are at most six attachments:

- `attachment-received-camera-cycle-01.json` through `-04.json`, one entire
  original cycle per file, including partial states and every role/reference;
- `attachment-received-camera-draft.json`, containing current draft, its origin,
  and any separate failed/unpublished draft and origin;
- `attachment-received-camera-attempt.json`, containing the whole last attempt,
  including descriptor-only partial original-media retention records.

Each `rocell.received_camera_metadata_family.v1` packet lifts the closed nested
`document`, `notebook`, `foundation`, `inspection` and `inspection_assessment`
objects into a content-addressed table. Exact duplicate documents are included
once within that family; no family depends on another attachment. All other
original fields remain in place. Nothing is selected, shortened or summarized
to fit. The ordinary exporter limits remain 1 MiB per attachment, 20,000 value
nodes, depth 12, eight attachments and 8 MiB total.

The private supplied-cache preflight is at most 3 MiB, 65,536 value nodes and
depth 20. A full expanded family is at most 512 KiB. These are local metadata
bounds, not changes to owned-worker IPC limits or original M1 quotas. Inputs
outside the supported bounds are refused before export directory creation.

`restore_received_camera_family(packet, *, expected_original_family_sha256=None)`
is a pure reconstruction helper. It verifies every expanded document digest,
all document references, no cycles or unused records, and the whole restored
family hash. Non-redacted role documents reconstruct to the original canonical
sorted compact ASCII JSON, without a newline. Their existing evidence hashes
can therefore be checked without trusting reserialized pretty-file hashes.

The report preserves original metadata, its pre/post-redaction hashes, the
original diagnostics hash and exact original field-name roster, plus all family
attachment names and reconstruction hashes. These hashes are not signatures.

## Redaction and late failure

Existing credential redaction runs on each flattened family. If it changes any
content, `credential_redaction_applied=true` and
`original_bytes_preserved=false`; the original and reconstructed hashes differ.
The sanitized documents are re-keyed to their own real hashes. They must not be
fed to subject verifiers as though they were the original M1 bytes. Original
context metadata has the equivalent explicit flags and hash pair. Other private
text is not guaranteed to be detected; review files before sharing.

Cancellation and the caller's original deadline (no more than 120 seconds)
are checked while preparing families and immediately before the ordinary
exporter call. The existing synchronous exporter has no mid-write cancellation
API. Once it returns a completed verified receipt, this helper returns it even
if Stop/deadline arrives late. The caller can retain that receipt historically
while withholding current publication. Partial directories are not purged and
there is no automatic retry.

Tests use actual pure submission/foundation/review codecs with explicitly
modeled observations, and the real exporter under temporary directories. Four
near-64-KiB original notebooks plus all cycle families, two drafts and the last
attempt fit without changing any global limit; no hardware qualification is
claimed by that file-only test.
