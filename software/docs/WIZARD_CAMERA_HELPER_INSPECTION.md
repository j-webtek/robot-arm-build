# Fixed camera helper inspection and metadata-only registration

`inspect_camera_helper(workspace, *, source_sha256, mode, scenario=None)` performs
only explicit file inspection in physical mode. The server chooses the workspace;
no browser-supplied executable path, command, hash update or installer is accepted.
No helper is launched, including `--self-test`. The source hash is caller-bound
context; Arrival verifies it independently. Rehearsal is pure and supports exactly
`nominal`, `missing-helper`, and `hash-drift` without reading any files.

The retained v1 module-constant catalog pins eleven fixed files: the existing
179,200-byte native helper, historical integrated record, native/CMake/test
sources, and the current reviewed metadata client. `camera_helper_catalog()`
returns its bounded data and canonical digest. The historical record is neither
changed nor treated as runtime approval. Its old Python-client digest differs
from the current metadata client's separately reviewed compatibility pin, so
every report explicitly says `historical_full_build_match=false` and includes
`CLIENT_CHANGED_SINCE_BUILD_RECORD`.

## Closed catalog versions

New wizard sessions call `inspect_current_camera_helper(...)`, which selects
`windows-camera-metadata-only-development-v2`. Its separate module pins 17 files:
the metadata-only executable, its new build record and CMake/denial tests,
current native inputs/client, fake-test executable and historical integrated
record. The [successor work order](CAMERA_METADATA_SUCCESSOR_WORKORDER.md)
records the build and received-camera metadata verification.

The original `inspect_camera_helper(...)` and `camera_helper_catalog()` defaults
remain v1 for historical callers; an explicit known `catalog_id` can select v2.
Verification resolves only these closed IDs and requires that version's exact
complete rows and digests. Unknown IDs and mixed/rehashed catalogs are rejected.
New wizard inspection never falls back to the old executable when v2 is missing
or changed. Each metadata lookup revalidates the same catalog as its reviewed
registration, including its fixed executable path.

The v2 build rejects probe/capture/settings commands before admission or camera
startup. This does not change the permissions or entry surface of old builds.
The historical client-change warning still describes the old integrated record;
the new coherent build does not retroactively upgrade that historical record.

## Inspection and registration contract

Physical reads stream 64 KiB blocks, with 8 MiB per-file, 32 MiB aggregate,
512-read and five-second between-operation limits. Existing regular/reparse
validation plus opened/named identity, size, link-count and modification checks
reject unsafe, hard-linked, changed or over-budget files. A slow OS call cannot
be forcibly interrupted. Hash checks are not filesystem TOCTOU or owned-process
qualification, and do not lock paths through a later launch.

Reports use `rocell.wizard_camera_helper_inspection.v1`, contain complete fixed
file observations, catalog/source/helper hashes and a canonical self-hash, and
remain under 64 KiB. Status is `MATCHED_METADATA_CATALOG`, `MISSING_FILES`,
`HASH_DRIFT` or `UNSAFE_OR_UNREADABLE`. Only a match is metadata-eligible; all
activation, driver qualification, physical authority and trusted-release flags
remain false. Missing/unreadable observations have null hash/byte values.

`verify_camera_helper_inspection(report, *, expected_source_sha256,
expected_inspection_sha256, expected_provenance)` is strict and pure. Independent
expected hashes are required. Held reports are valid retained diagnostics, not
registration authority. Rehearsal rows are explicitly modeled observations and
its helper digest is the existing incapable metadata-provider digest, not a
claim that any executable was read.

The separately owned registration state retains inspection and distinct operator
labels. `create_metadata_provider(workspace, registration_artifact, *, mode,
source_sha256, scenario=None)` accepts only its immutable
`ReviewedCameraHelperRegistration`; it independently verifies all context,
inspection hashes, distinct labels/operations and inventory/identity-only scope.
Construction and `descriptor()` are inert. The factory does not authenticate
people or establish signed-release/driver qualification.

Before **each** physical `inventory()` or `identity(candidate)` call, the returned
closed adapter verifies current workspace source and rehashes the fixed catalog.
It compares the entire current inspection with the committed report; it never
updates registered hashes. Only then does it construct the fixed native client
and metadata provider. There are no probe/capture methods. Rehearsal revalidation
remains pure and its optional metadata scenario is one of `nominal`,
`missing-mapping`, `wrong-device`, or `duplicate-name`.

`CameraHelperInspectionError.code` reports invalid registration, source drift or
`HELPER_INSPECTION_CHANGED`. The last case carries a defensive
`inspection_report` for the UI to retain while invalidating registration and
native choices. No metadata lookup occurs after a failed revalidation.

Tests inspect copied fixed files, exercise missing/hash/hardlink/type faults,
verify full immutable registration context, block I/O in rehearsal, and join the
physical wrapper to an explicitly incapable injected client runner. They never
launch a helper, enumerate OS devices or open hardware.
