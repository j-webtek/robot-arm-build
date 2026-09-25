# Offline eye-on-arm capture bundle

> **Camera architecture notice — 2026-09-05:** This bundle now supports only
> historical validation and optional Phase 2 eye-on-arm research. Phase 1 uses
> a rigid static overhead camera, with the fixed-overview stack as its migration
> target; an arm camera is not an automatic fallback. Exact static hardware
> remains open and this bundle continues to grant zero physical authority.

`rocell.eye_on_arm_capture_bundle.v1` is a byte-preserving, offline-only
companion to the eye-on-arm dataset and FK evidence package. It does not open a
camera, arm connection, or serial port; issue a command; create a calibration
artifact; or grant commissioning, motion, or contact authority.

## What the bundle proves

For every dataset sample, the bundle retains and verifies:

- the exact newline-terminated pre- and post-capture T=1051 response bytes,
  their SHA-256 digests, and the pinned parser identity;
- the canonical decoded-field digest obtained by parsing those exact bytes,
  including all unknown firmware fields and a complete `b/s/e/t/r/g` vector;
- request, first-byte, and completion timestamps plus strict request sequence
  ordering;
- the exact JPEG bytes, structural JPEG dimensions, settings hash, freshness
  token, source sequence, and source exposure timestamp;
- a recorder-declared pre/exposure/post interval and clock-correlation digest;
- normalized bytes for the existing `TargetPoseRecord`, tied to the exact
  image, camera-intrinsics hash, tag-map hash, and detector version; and
- exact dataset/evidence IDs, hashes, sample coverage, and sample order.

The verifier projects both feedback joint vectors through the evidence
package's installed joint-reference rules. It reports pre/post joint drift,
the largest error against the dataset joint record, bracket duration, and
exposure duration under a frozen serialized policy.

Every sample's clock-correlation digest must equal the evidence package's
single `timing_qualification_sha256` binding. This prevents correlation
versions from drifting silently within one bundle, but does not resolve or
validate that external artifact's payload.

`STRUCTURAL_PASS_NO_PHYSICAL_AUTHORITY` means only that these byte and
relationship checks passed. The report always sets
`eligible_for_commissioning`, `artifact_created`, `artifact_installed`,
`motion_authorized`, and `contact_authorized` to `false`.

## Honest timing boundary

RoArm T=1051 does not contain a device measurement timestamp. Consequently,
`correlated_capture_timestamp_ns` is explicitly a recorder claim bound to a
`clock_correlation_sha256`; it is not treated as verified clock evidence. The
bundle checks that:

```text
pre projected time <= exposure start <= camera source time
                   <= exposure end <= post projected time
```

It separately checks that the complete host camera transaction is between the
pre response completion and post request. These checks detect reversed,
stale, duplicated, or excessively wide brackets, but cannot prove the clock
projection itself. The report therefore always retains the blockers
`CLOCK_CORRELATION_ARTIFACT_NOT_CONTENT_VERIFIED` and
`T1051_DEVICE_MEASUREMENT_TIMESTAMP_NOT_ON_WIRE`.
Camera and calibration identities are likewise still caller-bound hashes, so
`CAMERA_AND_ARTIFACT_IDENTITIES_NOT_REGISTRY_RESOLVED` remains present.

## Detection boundary

The current detection bytes are the strict normalized serialization of the
existing direct-board `TargetPoseRecord`. They are not raw AprilTag detector
evidence. Tag IDs, pixel corners, inlier masks, covariance, detector logs, and
the original detector output still require a future typed schema. The report
retains `RAW_APRILTAG_CORNERS_INLIERS_AND_COVARIANCE_NOT_RETAINED` even when
the normalized record matches.

## Resource limits

- bundle file: 96 MiB, read through a `MAX + 1` bounded read;
- aggregate decoded blobs: 64 MiB;
- JPEG: 8 MiB per sample;
- T=1051 line: 64 KiB per observation;
- normalized detection: 128 KiB per sample;
- samples: 128; and
- JSON nesting: 32 levels after bounded parsing.

Base64 lengths are checked before decoding. Duplicate JSON keys, nonfinite
numbers, invalid UTF-8, parser drift, duplicate record IDs or request
sequences, extra/missing samples, and hash mismatches are rejected.

## Public offline API

The CLI reloads the verified active manifest/build/model context and requires
SHA-256 pins for the exact bytes of all three inputs:

```powershell
rocell verify-eye-on-arm-capture-bundle-offline `
  --dataset .\capture.json `
  --dataset-sha256 <exact-dataset-file-sha256> `
  --evidence .\raw-feedback.json `
  --evidence-sha256 <exact-evidence-file-sha256> `
  --bundle .\capture-bundle.json `
  --bundle-sha256 <exact-bundle-file-sha256> `
  --require-pass `
  --json
```

`--require-pass` makes a structural failure return nonzero after the report is
emitted. A zero exit still means only that the supplied bytes and declared
relationships passed the structural policy. The command requests zero camera
frames, generates zero arm commands, creates/installs no artifact, does not run
commissioning assessment, and always leaves physical timing unqualified.
The wrapper serializes the three verified external file SHA-256 pins alongside
the semantic dataset, evidence, and bundle hashes, so it records exactly which
input files were checked.

The same boundary is available through the offline API:

```python
from rocell.calibration import (
    load_eye_on_arm_capture_bundle,
    load_eye_on_arm_capture_evidence,
    load_eye_on_arm_dataset,
    verify_eye_on_arm_capture_bundle,
)

dataset = load_eye_on_arm_dataset(
    "capture.json", expected_file_sha256="<dataset-file-sha256>"
)
evidence = load_eye_on_arm_capture_evidence(
    "feedback-evidence.json", expected_file_sha256="<evidence-file-sha256>"
)
bundle = load_eye_on_arm_capture_bundle(
    "capture-bundle.json", expected_file_sha256="<bundle-file-sha256>"
)
report = verify_eye_on_arm_capture_bundle(dataset, evidence, bundle)

print(report.to_dict())
print(report.report_hash)
assert report.structural_passed  # structural only; never commissioning authority
```

`assemble_eye_on_arm_capture_bundle()` builds the immutable aggregate from
already-recorded `CaptureBundleSample` values. It performs no capture and no
filesystem writes.

## Remaining physical blockers

Before this bundle can contribute to physical commissioning, the system still
needs:

- a registry-resolved, content-verified clock-correlation artifact and a
  capture implementation that records its source measurements;
- a controller-provided or independently established joint measurement time,
  because T=1051 itself has none;
- independently verified camera identity, settings, intrinsics, tag map,
  carrier registration, and robot-reference payloads rather than matching
  caller-authored digest strings;
- raw AprilTag IDs/corners/inliers/covariance and detector input/output logs;
- independent dwell/settling evidence and repeatability trials; and
- a separate typed independent-validation and promotion boundary.

The capture bundle intentionally does not weaken any existing commissioning
blocker while those inputs are absent.
