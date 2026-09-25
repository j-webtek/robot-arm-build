# Physical camera runtime file inspection API

`application/physical_camera_runtime_inspection.py` observes the fixed installed
probe/capture build files without executing an EXE, loading a native DLL,
querying devices, opening a camera/serial port or granting authority. The two
runtime candidate types remain dormant and immutable. The inspector has no
release flag, arbitrary file roster, fixture scenario or public pin-update API.

```python
report = inspect_physical_camera_runtime_pair(
    workspace,
    expected_source_sha256=original_source,
    launch_session_id=original_wizard_launch,
    operator_id="setup-operator",
    probe_candidate=service_owned_probe_candidate,
    capture_candidate=service_owned_capture_candidate,
    cancellation=original_stop_event,
    progress=optional_progress_callback,
)
```

The exact code-owned candidate pair, workspace, source, catalog and purpose are
checked before file reads. The launch is `wizard-` plus 32 lowercase hex digits;
operator labels contain 1–64 ASCII letters/digits/dot/underscore/hyphen, beginning
with a letter or digit. A progress callback receives only a fixed relative path.

The immutable `PhysicalCameraRuntimeInspection` contains canonical `.payload`,
its `.sha256`, detached `.to_dict()` and compact `.safe_summary()`. It records
observed file hashes/lengths, not binary contents. Exact raw build-record bytes
are retained as base64 only when their independent fixed pin matches; only a
strictly validated known record can supply expected source/artifact hashes.
Manifest text can never extend the fixed path inventory.

`FILES_MATCHED` means only that this finite file inspection completed with every
comparison matched. `HELD` preserves gaps. Both retain false for
`dispatch_enabled`, `driver_qualified`, `hardware_qualified`, `connected` and
`physical_authority`. Per-purpose executable pin, build-record pin, current-source
closure and artifact-closure states remain separate. Matching a historical
probe binary does not make its old source record match current source.

## Bounds, failure and lifetime

The closed inventory has 27 distinct paths: at most 40 are allowed, with 8 MiB
per artifact, 128 KiB per build record, 1 MiB per source, 32 MiB aggregate native
reads, 512 native read calls and a 128 KiB canonical report ceiling. Stop and
the 30-second deadline are checked around every bounded native read. Named and
opened file identity/length/time/link count are compared before and after reads.

Workspace `source_fingerprint` checks run only at entry and final publication,
with the existing separate 128 MiB-per-check/4096-file bound. Their count is
recorded separately; it is not included in the 27-path/32 MiB native inventory.
They share the inspection's time/Stop checks. Synchronous filesystem calls are
not forcibly interruptible. Observations do not pin files for later execution;
the future qualified process owner must independently revalidate and pin them.

Missing, unsafe, unreadable, oversized, unstable or drifted files produce held
observations. Unknown bytes/hashes remain null, never zero-byte success.
`PhysicalCameraRuntimeInspectionError` exposes `.code` and detached
`.inspection_report` for cancellation, deadline, source, read-budget or progress
failure after context validation. That bounded partial/full report is historical
evidence, not permission to publish a current reviewed state. There is no retry.

## Pure retained verification

```python
checked = verify_physical_camera_runtime_inspection(
    retained_bytes_or_dict_or_typed_report,
    expected_source_sha256=trusted_source,
    expected_launch_session_id=trusted_launch,
    expected_probe_candidate=trusted_probe_candidate,
    expected_capture_candidate=trusted_capture_candidate,
    expected_report_sha256=independently_retained_report_hash,
)
```

This API performs no filesystem/source checks or replay. It validates strict
schema/types/limits, original candidate bindings, raw manifest bytes and hashes,
file inventory, conservative read-accounting bounds and recomputed comparisons,
counts and statuses. Its expected hash must come from the original trusted
retention context, not be accepted from an arbitrary report sender. Content
hashes do not establish human authorship, release approval or current freshness.

Focused verification: `test_physical_camera_runtime_inspection.py` has 40 isolated
file/parser/lifecycle tests plus one read-only actual installed-file test using
an explicitly modeled workspace source. That file check observed matching
binary/record/artifact pins for both purposes, one historical probe source gap,
and matching current capture closure. It is not the separately required public
true-source inspect/review/export walkthrough or received-unit qualification.
