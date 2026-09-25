# Native camera capabilities, staged settings and readback

`application/physical_camera_configuration.py` is a pure application join. It
does not enumerate, open, configure or start a camera, execute a helper, read
pixels, change a registry or issue authority. The current native physical runner
remains held. Its three schemas are distinct from `camera_configuration.py`'s
incapable rehearsal schemas:

| Artifact | Meaning | Display status |
|---|---|---|
| `rocell.physical_camera_capabilities.v1` | Exact metadata reported by a retained successful native probe | `OBSERVED_NATIVE_UNQUALIFIED` |
| `rocell.physical_camera_configuration.v1` | Operator's selected electronic-settings request, not applied state | `STAGED_NOT_APPLIED_NATIVE` |
| `rocell.physical_camera_readback.v1` | Exact requested settings compared with retained native capture metadata | `REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED` or `READBACK_MISMATCH_UNQUALIFIED` |

All retain `provenance=PHYSICAL_UNQUALIFIED`, `physical_authority=false` and
`hardware_qualified=false`. A successful comparison is not device qualification,
pixel validation, calibration, final power observation or permission to move.

## Trusted admission chain

1. `derive_physical_camera_capabilities(evidence, *, expected_preparation,
   expected_evidence_sha256, expected_source_sha256)` accepts only an exact
   `PreparedOwnedNativeProbe` and the complete retained
   `OwnedNativeCameraRunEvidence`. It independently verifies the evidence hash,
   original preparation and source. Admission-only, held, failed, incomplete or
   unclean campaigns cannot produce selectable capabilities. Both native cleanup
   and owned-process cleanup must be confirmed in the retained records.
2. Modes (up to 128) and controls (up to six) are copied exactly. Mode choice IDs
   bind the full capability artifact and original row; duplicate reported rows
   remain distinguishable. Unsupported formats/widths/strides/byte sizes remain
   visible but unselectable. Missing controls are explicitly unavailable; there
   is no guessed camera model or default selected mode.
3. `stage_physical_camera_configuration(capabilities, mode_choice_id, controls,
   *, expected_capabilities_sha256, expected_source_sha256, expected_session_id,
   expected_selected_identity_sha256)` produces
   `StagedPhysicalCameraConfiguration`. It validates exact typed controls against
   observed support flags, ranges and steps, then sorts their IDs before any
   logical capture plan is prepared. `.mode` and `.controls` feed that plan.
   `.settings_epoch` hashes the immutable request artifact; `applied` stays false.
4. `compare_physical_camera_readback(configuration, capture_evidence, *,
   expected_preparation, expected_capture_evidence_sha256,
   expected_settings_epoch)` requires the exact `PreparedOwnedNativeCapture`.
   Source, session, reviewed selected identity and opaque endpoint hash must
   match the probe/configuration. The capture's complete mode/control request
   must match the staged intent. Probe and capture intentionally use separate
   purpose-specific helper binaries: their hashes are retained independently,
   not required to equal. The service must separately review the permitted
   runtime pair and current M1 authority.

The caller must obtain all `expected_*` values from trusted retained M1/server
state, never a browser payload or the same untrusted artifact being checked.
Dataclass construction alone performs structural validation, not authentication.

## Readback behavior

Requested-mode echo is exact; negotiated rates may use an equivalent rational.
An explicitly requested stride must match negotiated and sample metadata. Manual
values and flags must match; auto requires the observed auto flag, not a promise
of a fixed later value. Requested control ranges, steps, defaults, support flags
and units are compared with the probe so capability drift cannot look successful.

Known failed captures produce an immutable mismatch report. A held/raw-only
capture supplies no invented mode or control observations. Unknown or mismatched
trusted hashes, preparation, source/identity or settings raise an error rather
than admitting another campaign's observations. Process cleanup and native
cleanup are separate Booleans, `frame_content_verified` remains false, and final
power remains `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`. No image is published here.

## Retained verification and UI

`verify_physical_camera_capabilities`, `verify_physical_camera_configuration`
and `verify_physical_camera_readback` require their independent trusted artifact
hashes and exact dependencies. They rederive only the pure data joins, never
replay a worker, resolve a path or repair evidence. Each artifact is canonical,
bytes-backed and capped at 96 KiB; `to_dict()`/`view()` return detached objects.

`.view()` separates reported capabilities, staged intent and readback. It omits
raw endpoint paths, process streams and camera bytes. Mode/control data are the
reported scalar metadata, not a list invented for a known product. The service
owns selection/review freshness, durable publication, cancellation, last-frame
labeling and qualification gates.

## Hardware-free tests

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit/test_physical_camera_configuration.py -q
```

Fixtures construct explicitly modeled physical-shaped native wire/process
records and send them through the actual strict evidence codecs. They are not
claims that a received camera ran. Filesystem, process and device calls are
forbidden in the pure tests. `physical_configuration_fixture(tmp_path)` provides
real producer objects for UI projection tests; it does not create any files.
