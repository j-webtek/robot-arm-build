# Scoped physical native-camera campaign join

This module connects the camera-only commissioning coordinator to the actual
`OwnedNativeCameraRunner`. It does **not** enable that runner: its independent
physical qualification hold remains before owner construction, file pinning,
process launch, Media Foundation, device enumeration or camera activation.

## Inert preparation

`PhysicalNativeCameraCampaign(workspace, assigned_parent, *, source_sha256,
cell_id, session_id, selection, runtime, mode=None, controls=(), budget=None)`
accepts only the exact `PhysicalCameraSelection` and purpose-specific native
runtime-candidate types. The runtime determines probe versus capture. There is
no supplied executable, runner, authorizer Boolean or physical-enable option.

- `plan()` returns a detached bounded document. It retains the full selection,
  runtime pins, source/workspace, exact camera-only M1 namespace, settings and
  output policy. SHA-256 of its canonical bytes is the operation binding.
- `registration()` returns the camera-only scoped action registration. Probe
  uses stage `camera_mode_controls`; capture uses `camera_frame_freshness`.
  Parent budgets are 20 and 25 seconds respectively; the original permit is
  not renewed. Evidence has a 128 KiB ceiling, separate from native frame bytes.
- `preparation_for_permit(permit)` reconstructs the existing logical camera
  plan and guarded native preparation using the actual attempt/session/permit.
  It is pure and is not an executable authorization interface.
- `from_plan(document)` reconstructs and compares the complete canonical plan;
  it performs no file checks, enumeration, directory creation or execution.

Probe uses the existing exact 5-second native budget and no requested mode or
controls. Capture requires explicit typed mode and budget, canonical sorted
control IDs, and the existing guarded capture contract. Existing validators
reject unsupported format, dimensions, padding/stride and budget combinations.
Controls are intent, not proof that the received camera supports those values;
the separate capability/settings layer and service own that review.

The metadata launch session remains recorded inside the selection. It is not
silently equated with the separate camera-domain M1 session. Selected identity
is SHA-256 of the complete ASCII selection document, not an endpoint hash or
the original UTF-8 metadata-review hash.

## Explicit scoped execution

The coordinator invokes `run_scoped_campaign(permit, *, deadline_ns,
cancellation, authorization)` with the exact `ConsumedCommissioningScope`.
The worker checks the entire registration, camera stage/resource/domain,
cell/session, source-domain binding, selected identity, and absent arm energy
envelope before acknowledging the already-consumed attempt once.

It reads the current source fingerprint and revalidates the original scope.
The callback supplied to the native runner additionally binds the entire
prepared request, process registration, assigned working directory, settings,
budgets and original permit. After-pin and READY/release checks can revalidate
that same consumed scope; they cannot consume again or extend its deadline.
The current physical hold occurs before those native callbacks, so this join
also performs one explicit live revalidation before calling the held runner.

The original native evidence bytes are retained as one `CampaignEvidence`.
`evidence` returns an owned typed copy for private diagnostic retention. The
current result is uncertain and unqualified, not a canonical stage PASS. The
coordinator retains the full held evidence and quarantines the attempt. A
second execute returns its prior result; neither worker nor runner retries.

Zero device counters are projected only when retained evidence proves that no
owner/process/release was attempted. If a future activated process returns no
native counters, this version refuses to invent zero observations. When a
typed native receipt exists its separate counters are preserved. Process and
native cleanup remain separate; absence of a source/process does not become a
fabricated successful native shutdown. Final power state remains unknown.

## Pure retained verification

`verify_physical_native_camera_campaign_evidence(evidence, *, campaign,
expected_permit, expected_evidence_sha256)` reconstructs the complete original
preparation, checks independent trusted M1 references, refuses an incapable
fixture/native-domain substitution, and checks the retained deadline against
the original permit. It does not replay a worker, load files, or grant renewed
authority. The caller must obtain the plan, permit and evidence hash from
audited M1 records; matching self-authored objects are not origin authentication.

## Deliberately unfinished physical requirements

The assigned parent is a server-owned canonical local absolute Windows path,
not a browser-supplied path. Planned directories are
`<parent>/native-camera-<attempt_id>` and, for capture, its
`capture-<attempt_id>` child. No directory is created by a held run. Future
dispatch needs reviewed directory/file ownership, pinning and no-overwrite
publication before this policy can change. A source fingerprint or candidate
binary hash does not close filesystem TOCTOU or qualify a runtime/driver.

Captured metadata does not verify sample files or pixels. A future released
capture join still needs bounded regular-file validation, actual byte hashes,
immutable `PHYSICAL_UNVERIFIED` ingestion and derived-preview provenance.
This module cannot infer camera position, calibration, arm/TCP coordinates,
received-unit identity, firmware behavior, energization or physical readiness.

## Verification scope

`test_physical_native_camera_campaign.py` uses modeled physical-shaped
selection/runtime records through the actual pure codecs. Its core transaction
double is incapable; the actual unchanged native runner is called and must hold
before any owner exists. Process, DLL and device calls are prohibited in that
lane. The separate `slow` test uses actual qualified NTFS publication and OS
leases with clearly labeled incapable predecessor storage fixtures, then calls
the same held runner and verifies retained evidence after original-store reopen.
It permits Windows filesystem APIs, not camera or native-helper execution.

Run the fast lane with `pytest software/tests/unit/test_physical_native_camera_campaign.py -m "not slow"`.
Run the actual storage join explicitly by selecting
`test_actual_m1_scope_retains_real_native_runner_pre_owner_hold` in that file.
Neither lane is received-hardware or physical stage qualification.
