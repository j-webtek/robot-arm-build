# Native camera endpoint metadata enrollment

Implemented in
[`wizard_native_camera_enrollment.py`](../src/rocell/application/wizard_native_camera_enrollment.py).
This is a pure, launch-local join between an explicitly reviewed generic
CAMERA candidate and exact Windows-native endpoint metadata. No method invokes
a provider, enumerates, opens a camera, captures pixels, writes files or grants
a permit. `connected`, `qualified`, `persistent_binding` and
`physical_authority` remain exactly false, even after successful review.

## API and publication

```python
enrollment = WizardNativeCameraEnrollment(
    mode, session_id, source_sha256,
    provider_descriptor=provider.descriptor(),  # None means an explicit hold.
)
staged = enrollment.staged_copy()
report = staged.ingest_inventory(
    inventory_packet, operation_id=inventory_operation_id,
    generic_review=device_selection.reviewed_candidate("CAMERA"),
)
# Caller validates/retains/logs report, then atomically publishes staged state.
options = staged.choices()  # Never chooses an endpoint automatically.
details = staged.preview(operator_choice_id)
candidate = staged.candidate(operator_choice_id)  # Server resolver only.
# A separately admitted caller/provider action supplies the identity packet.
report = staged.retain_identity(
    operator_choice_id, identity_packet, operation_id=identity_operation_id
)
report = staged.review(operator_choice_id, reviewer_id)
prospective_binding = staged.binding()  # CameraEndpointBinding or None.
```

These are separate explicit actions, not an automatic connection sequence.
`ingest_inventory`, `retain_identity` and `review` return full plain-JSON
reports. `export_snapshot()` reads the same retained state without performing
an operation. `view()` is bounded. `staged_copy()` uses a fresh lock and shares
only immutable bytes and copied endpoint values. The caller owns admission,
cancellation, source/revision checks, retention/logging and publication.

The new generic method `WizardDeviceSelection.reviewed_candidate(class)`
returns the current exact full acknowledgement or None. It does not call
`review()`, issue choices, change reviewer, reread a provider or reconnect.
Returned values are detached.

## Exact evidence join

Provider descriptors contain exactly `provenance` and `helper_sha256`, copied
at construction. Rehearsal requires `INCAPABLE_FIXTURE`; physical mode requires
`WINDOWS_NATIVE_METADATA`. None produces `PROVIDER_UNAVAILABLE`; no historical
helper is searched for, trusted or opened implicitly.

The generic review is reconstructed against the existing public selection
preview contract and complete original inventory. It must match the expected
mode/session/source, CAMERA candidate hash, inventory hash/operation and
acknowledgement. Windows-native enrollment requires Windows generic metadata.

Native packets use schema `rocell.wizard_native_camera_packet.v1` and exact
fields `schema`, `kind`, `provenance`, `helper_sha256`, `receipt`. The shared
[`validate_native_packet`](../src/rocell/application/wizard_native_camera_metadata.py)
checks kind/provider/helper and the exact server-owned endpoint for identity.
It uses actual native receipt parsers with 5,000 ms metadata and eight-parent
bounds. Inventory requires successful completion and confirmed cleanup. Full
wire metadata, unavailable observations and cleanup errors remain retained.

A prospective artifact is produced only when:

1. The exact selected endpoint mapping is observed, including cleanup checks.
2. Its observed device-instance string exactly equals the generic candidate's
   `os_instance_id`: no friendly-name or case-normalized fallback.
3. Its observed canonical container equals the sole canonical container in
   the generic `windows-container:` persistent ID. GUID braces/case can be
   canonicalized; missing, malformed or conflicting values remain held.
4. Generic identity has no unresolved missing/duplicate/ambiguous identity
   blockers and the endpoint occurrence is unambiguous.

Equal friendly names with different endpoint hashes remain separate choices.
No serial number, negotiated speed or persistent unit identity is inferred
from an endpoint, container or parent chain. Missing/wrong mappings can be
acknowledged as held evidence, but `binding()` remains None.

The actual generic provider codes
`CAMERA_NEGOTIATED_LINK_SPEED_NOT_OBSERVED` and
`CAMERA_USB3_TOPOLOGY_NOT_OBSERVED` remain in overall holds, but do not prevent
preparing an exact **metadata-only** endpoint artifact. Other connection,
received-model, native-qualification and physical-stage holds also remain.
Possession of `CameraEndpointBinding` does not satisfy the native client's
separate authorizer or qualify activation.

Hashes establish internal consistency, not authentication or freshness. The
caller must bind packets to its actual source-bound provider action and
current generic review. This module cannot prove where external JSON came
from, that metadata remains current, or that a device stayed attached.

## Full report, artifact and view

Report schema is `rocell.wizard_native_camera_enrollment_report.v1`, containing
`view`, full `generic_review`, full `inventory_packet`, full `identity_packet`
and `binding_artifact`; absent evidence is None. Artifact shape is
`{payload, binding_sha256}`. Its payload status is
`REVIEWED_ENDPOINT_METADATA_ONLY` and binds:

- mode/session/source and provider/helper;
- exact generic review/candidate/report hashes and operation;
- inventory/identity packet hashes and operations;
- endpoint/choice, reviewer, matching observed instance/container and holds.

Full reports are retained alongside the artifact and hashed, not duplicated
inside it. There is no self-referential hash or invented review timestamp.
The endpoint digest binds exact symbolic-link UTF-8 bytes. Full retained
metadata contains private OS IDs and symbolic links; use the assigned
diagnostic export workflow, not browser-provided paths or commissioning intake.

View schema is `rocell.wizard_native_camera_enrollment.v1`. Fields are
provenance; inventory hash/operation; generic candidate/report/operation;
`candidates:[{choice_id,friendly_name,endpoint_sha256}]`; nullable identity
`{choice_id,endpoint_sha256,identity_sha256,operation_id,exact_endpoint_observed,
generic_device_match,container_match,blockers}`; nullable review
`{choice_id,reviewer_id,binding_sha256,status,physical_authority}`; overall
blockers; the four false flags; and nullable invalidation reason. No raw
symbolic link is in view or ordinary preview.

Statuses are `NO_INVENTORY`, `PROVIDER_UNAVAILABLE`, `INVALIDATED`,
`ENDPOINT_CHOICES_AVAILABLE`, `IDENTITY_RETAINED`, `ENDPOINT_METADATA_REVIEWED`
and `REVIEW_HELD`. Successful review status is
`REVIEWED_ENDPOINT_METADATA_ONLY`; held review is
`METADATA_ACKNOWLEDGED_BUT_HELD`, without a binding hash.

Native packets are independently capped at 256 KiB, full generic review at
256 KiB and full enrollment report at 768 KiB. There are at most 128 endpoint
choices and 32 displayed blocker codes. Friendly names have the native
1,024-byte UTF-8 cap; choice labels are explicitly shortened while full
bounded names remain retained. No existing wizard envelope limit is widened.
The actual nominal closed-producer fixture measured 12,050 canonical bytes
(15,873 pretty JSON bytes), with 12 overall holds and no physical authority.

## Invalidation and errors

`invalidate(reason)` clears native inventory, generic anchor, choices,
identity, review and artifact. Use it for generic inventory/review refresh,
native inventory refresh, source change and logging failure, even if the new
action fails/cancels. New inventory rotates opaque tokens; restart does not
restore state or activate anything.

`invalidate_identity(reason)` preserves selectable inventory/generic evidence
but clears identity/review/artifact. `invalidate_review(reason)` preserves
identity but clears review/artifact. The caller uses partial resets at explicit
dispatch before staging. Their active inventory status remains visible with
the reason. An oversize result cannot leave a successful-looking local state.

`NativeCameraEnrollmentError(ValueError)` has a fixed public `.code` and
bounded message. Shared typed/parser failures are wrapped rather than exposing
raw endpoint exceptions. Invalid identity packets are not published as valid
evidence; the caller can retain bounded failed packets separately. Errors do
not authorize automatic retry, connection or motion.

## Tests

[`test_wizard_native_camera_enrollment.py`](../tests/unit/test_wizard_native_camera_enrollment.py)
joins the actual closed generic/native fixture producers. It requires nominal
binding with speed/topology holds, rejects forged helper/source/endpoint/hash/
schema, retains missing/wrong/duplicate identity holds, distinguishes equal
names from identities, and verifies staged copies, partial resets, full-report
limits and detached outputs. Provider/filesystem calls are forbidden in inert
API tests. No OS inventory or native camera is accessed.
