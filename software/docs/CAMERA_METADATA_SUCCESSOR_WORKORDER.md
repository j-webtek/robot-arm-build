# Metadata-only camera runtime successor

## Scope and completion criteria

Repair the wizard's native metadata path without accepting drift in the old
catalog. Preserve old executables, build records, exports and registration
semantics. No camera capture, electronic control change or arm access is in
scope. The operator authorized continuing software work and metadata checks
without repeated proceed prompts; physical actions remain separate.

1. Build a separate metadata-only executable from current reviewed sources in
   a new directory. A compile-time entry guard must reject all non-metadata
   commands before admission handling or COM/camera startup. Reuse existing
   inventory and identity wire protocols rather than creating another parser.
2. Run the inert self-test, fake identity API/wire tests and forbidden-command
   tests. Record exact build inputs, artifact hashes, toolchain and test scope
   in a new build record. Never overwrite an earlier build directory or record.
3. Add a closed successor catalog alongside the retained v1 catalog. Retained
   reports resolve only a known catalog ID; arbitrary paths/hashes are not
   accepted. Bind the new binary, build record, all native build inputs and
   current metadata client. No runtime hash learning or fallback to v1.
4. Use the successor for new wizard helper inspections. Keep explicit review,
   current-source/file revalidation on each lookup, no automatic selection,
   strict receipts, unchanged physical gates and export retention. Test old
   and new catalogs, malformed/mixed reports, drift, provider scope, UI/service
   composition and export.
5. Start a fresh physical diagnostic session, inspect/review the successor,
   acquire/review only the expected B0477 generic camera, enumerate native
   endpoints, explicitly match the exact endpoint and acquire/review identity.
   Preserve missing values or mismatches. Export and shut down. Do not proceed
   into capture or settings to obtain a favorable outcome.

Diagnostic inspector/reviewer IDs used by Codex describe separate software
steps, not independent authenticated people or hardware qualification.

## Existing evidence

Generic camera lookup succeeds after the Windows PowerShell array correction.
The expected camera-function instance and USB parent share their container and
report PnP status OK. Before this work, native metadata registration was held on
seven drifted source/client pins in the retained v1 catalog. Details and original exports are in
[the pre-build operability playbook](PREBUILD_OPERABILITY_PLAYBOOK.md).

## Completed checkpoint — 2026-09-12 UTC

All five steps above were completed for the metadata-only scope. The new wizard
default uses the closed `windows-camera-metadata-only-development-v2` catalog
(17 fixed files) and the separately built `rocell_windows_camera_metadata.exe`.
The historical catalog and executables remain unchanged; the old catalog still
reports its source drift. The entry guard rejects active commands before
admission or camera startup; the shared translation unit still contains legacy
capture code, so this is not a claim that all capture code was removed.

- Build and immutable input/artifact hashes:
  [metadata-only build record](../native/windows_camera/metadata_only_build_record_20260912.json).
- Native verification: **4/4 test groups passed**, including 31 fake identity
  wire receipts and nine rejected active/malformed commands. JUnit:
  `../../.codex-preserved/metadata-successor-native-20260912-01.xml`.
- Selected Python regression: **615 passed in 35.48 seconds**. JUnit:
  `../../.codex-preserved/metadata-successor-python-20260912-03.xml`, SHA-256
  `609929a64a7706936c0978efa88701dc1a339b335046f6076e1041dcd4d06397`.
  Earlier failed/stale-expectation runs remain retained. This is not the full
  repository or full-history commissioning acceptance suite.
- Targeted mypy checks passed for the inspection and successor-catalog modules;
  Black checks passed for those modules and the two new Python test files.
- Actual physical-mode wizard service: helper inspection/review, generic camera
  inventory/review, native endpoint inventory, exact identity lookup/review and
  assigned-folder diagnostic export all completed. These were real backend
  actions, not browser-click verification or injected device fixtures.

The Media Foundation endpoint maps to the expected B0477 camera-function
instance and container. Its interface GUID differs from the earlier DirectShow
endpoint; identity was checked rather than equating those opaque strings.
Driver and parent-chain metadata were retained. All source activation, sample,
frame and control-write counts were zero; the service shut down after export.

The final review remains **REVIEW_HELD** because the generic camera-function
record does not supply a unit serial or persistent-unit selector. The USB parent
identifier was observed but was not substituted for a separately qualified unit
serial. No persistent binding or physical-stage pass was granted.

Verified completed metadata export:
`../runs/wizard-exports/wizard-20260912T011802570264Z-f97251374e6648128bd0ae956595830e`.
The earlier partial endpoint-discovery run is preserved separately:
`../runs/wizard-exports/wizard-20260912T011648755304Z-2aa086769eec4658a8a4cd487a38544e`.
The [operability playbook](PREBUILD_OPERABILITY_PLAYBOOK.md) records exact
received-device observations and the remaining integration dependencies.

## Limits

Matching metadata is not a persistent-unit qualification, negotiated USB-speed
measurement, driver approval, live stream, calibration or robot permission.
The legacy catalog remains inspectable with its original hashes and honest
drift report. A new source binding does not resume old sessions or replay old
operations. Real capture/full-history commissioning remains separate work.
