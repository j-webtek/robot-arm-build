# Physical camera metadata selection identity

`application/physical_camera_selection.py` is a pure bridge between existing
native endpoint metadata review and M1 admission facts. It does not discover,
connect, qualify or activate a camera. Physical provenance is retained as such;
rehearsal enrollment is refused, not relabeled.

```python
selection = selection_from_enrollment(
    enrollment,
    source_sha256=current_workspace_source,
    launch_session_id=current_wizard_session,
)
camera_binding = selection.binding
identity_facts = selection.identity_document
```

Conversion requires the exact `WizardNativeCameraEnrollment` class and takes a
coherent detached staged snapshot. It checks physical mode, source/launch,
reviewed state, original artifact hash, generic/native packet hashes, endpoint
occurrence, instance/container joins and `binding()`. It reuses existing pure
metadata validators; no files, native calls, new original review or provider
lookups occur. The original enrollment is unchanged.

## Hash domains and immutable API

- `PhysicalCameraSelection(payload: bytes)` validates a closed document with
  schema `rocell.physical_camera_selection.v1` and a **64 KiB** maximum. Excess
  bytes are rejected; nothing is truncated.
- `.payload` is canonical JSON: sorted keys, compact separators,
  `ensure_ascii=True`, ASCII bytes and **no trailing newline**. This matches
  M1's fact-document encoding, not its newline-terminated ledger-file encoding.
- `.sha256` hashes those exact bytes; `.identity_document` returns a detached
  dictionary for M1. `.binding` uses the original opaque endpoint/hash but this
  new selection hash as `CameraEndpointBinding.binding_sha256`.
- The original metadata-review payload remains embedded as `metadata_review`.
  `metadata_review_binding_sha256` still hashes its original canonical
  **UTF-8**, `ensure_ascii=False`, no-newline encoding. Unicode is not normalized,
  discarded or silently rehashed into the original review identity.
- Source, launch, endpoint, generic candidate/report/review and native
  inventory/identity packet hashes are cross-bound in the new identity document.
  `native_identity_sha256` is the retained native packet hash, not the new M1
  selection hash. All connected/qualified/persistent-binding/authority flags
  remain false; baseline USB3, received-unit and physical-stage holds remain.

`.safe_summary()` returns exactly four hashes, with no endpoint text:

```text
endpoint_sha256
identity_sha256                    # new selection/M1 identity hash
metadata_review_binding_sha256     # unchanged original UTF-8 review hash
generic_candidate_sha256
```

Invalid input raises `PhysicalCameraSelectionError` with a bounded fixed message
and a fixed code; underlying endpoint/provider exception text is not exposed.

## Caller obligations

This snapshot is a point-in-time metadata identity, not authenticated origin,
received-unit acceptance, runtime qualification or an effect permit. Directly
restoring a valid payload does not establish that it is the current selection.
The server must retain/trust the relevant original review and independently
revalidate current source/enrollment at planning and consumed-admission
boundaries. A later invalidation does not mutate historical selection bytes
or permit them to bypass current holds. No browser-provided identity document
or original-review hash is an authoritative substitute.

Tests exercise actual pure enrollment/parsers using explicitly injected
physical-shaped metadata fixtures. They do not query OS devices or claim
received-hardware observations. Unicode endpoint/reviewer cases demonstrate
both hash domains and equality to the actual M1 fact encoder. Other tests cover
source/session/domain refusal, held/missing review, mutated hash/endpoint joins,
false authority, defensive copies, byte/canonical limits and forbidden
file/process/device operations.

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit/test_physical_camera_selection.py -q
```
