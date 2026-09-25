# Original-bound camera settings capture: developer handoff

This is an implementation handoff, not a hardware acceptance record. It pairs
with `CAMERA_SETTINGS_READBACK_WORKORDER.md` and the existing wizard integration
playbook. The purchased camera remains a static overhead camera. This change
does not alter the placemat layout, arm mounting or optics specification.

Confirmed diagnostic destination:

    C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports

## What this slice implements

An internal service operation can use the same original Session and camera
enrollment that produced a successful capability probe, authenticate their
retained evidence, validate explicit camera settings, and request one separate
bounded settings-readback capture. Its result remains staged until publication
is separately validated. This is not a continuous video connection, calibration,
stage PASS, arm startup or permission to touch a keyboard/phone.

The browser action for this new profile is **not yet connected**. Do not enable
the old stage-6 capture button or call the internal service from an unguarded
HTTP route. The public completion-log and export integration below is required.

## Ownership and data flow

| Component in `software/src/rocell/application` | Responsibility |
| --- | --- |
| `physical_camera_acquisition_service.py` | Serializes explicit operations; requires the same live Session/enrollment owners and published settings; holds failures and prevents replay of an attempted request key. |
| `camera_probe_original_scope.py` | Authenticates setup originals before the short permit; later checks actual locked inventory, shared-family records, source, cancellation and deadline. |
| `camera_configuration_original_scope.py` | Re-reads the original probe permit/result/paired evidence/facts; independently reconstructs capabilities, settings and the exact new capture plan. |
| `camera_configuration_admission.py` | Binds those original dependencies, current operator-reported arm-power isolation, explicit consent and current output capacity into immutable admission facts. |
| `camera_configuration_capacity.py` | Counts raw frame, ingested copy, preview, metadata, private output and remaining shared-family record allowance. Measures the assigned local volume without creating output. |
| Existing coordinator, M1 persistence and native supervisor | Own the new one-use permit, ordered leases, bounded process lifetime, device observation, cleanup and original evidence retention. |
| Existing dispatcher and capture workflow | Read originals back after retention, verify mode/control observations, ingest frame bytes and stage the result. The later publisher controls visibility. |

The internal entry point is
`PhysicalCameraAcquisitionService.run_original_configuration_capture(...)`.
It requires exact original header/preparation/review/plan hashes, the same Session
and enrollment objects, an explicit request key, typed finite capture budget,
operator identity and consent, the original cancellation/deadline, progress
reporting and a current-context validator. Hashes are comparisons, not evidence.
The caller must authenticate current logged UI publication; a callback returning
`True` cannot grant permission. Valid validators return `None` or raise.

The new plan is the closed
`rocell.physical_native_camera_configuration_campaign.v1` profile, with action
`physical-native-camera-configuration-capture-v1` at `camera_mode_controls`.
Its native capture budget is fixed at 5,000 ms and one frame, with equal per-frame
and total byte limits. The actual maximum bytes must come from the verified mode
and server policy; do not copy the 16-byte synthetic test budget into production.

The older v2 freshness capture remains a separate stage-6 operation. Probe
capability reports do not contain a requested/observed image mode and cannot
substitute for the settings readback. A new explicit capture may be requested
for a subsequent reopen check; it gets a new permit and does not itself pass
the reopen assessment. Failed/unknown attempts never auto-retry.

## Timing and capacity rules

- A settings capture has at most 25 seconds and cannot outlive its original
  30-second maximum permit. The coordinator uses the remaining original time,
  never renews it, and requires the fixed 17-second process/cleanup lifetime.
  Native preparation repeats full-lifetime checks before start and release.
- Revalidation does one fresh full record audit per boundary. Probe-reference
  comparison and headroom arithmetic share those same read bytes only within
  that synchronous call. There is no cross-operation audit cache. Final source,
  identity, Session snapshot, lease and Stop checks bracket the disk observation.
- Camera and earlier USB records share aggregate storage quotas. Both probe and
  settings-capture headroom include the complete audited family, not merely the
  current camera directory. Existing byte/record limits are not increased.
- Free space is an observation, not a reservation. The full output allowance is
  conservatively required again at later boundaries. Partially written output
  earns no credit. Low space after effects can cause a hold; nothing is deleted
  to manufacture headroom. Dataset publication checks its own capacity again.

## Diagnostic continuity

The service pins probe diagnostics independently from its most recent dispatcher.
`retained_probe_diagnostics()` returns the original probe admission/dispatch;
`retained_configuration_diagnostics()` returns the latest settings attempt.
Changing dispatchers must not cause the dedicated probe export to contain a
later capture. These are detached diagnostic data, never restorable live owners.

Settings status progresses through authentication, original verification,
admission derivation and `RESULT_STAGED_NOT_PUBLISHED`. Failure records
`FAILED_HELD` and its prior phase while preserving available original attempt
diagnostics. Missing native accounting remains unknown; do not invent a
zero-I/O receipt. Original M1 quarantine and no-replay rules remain authoritative.

## Next public-wizard implementation, in order

1. Add a distinct settings-capture action with a closed request schema, not a
   generic JSON-command textbox. The browser supplies operator/consent choices,
   never a device path, worker, output path, permit, budget or stage override.
2. Pin the successful settings-publication receipt independently of the rotating
   operation history. Join it to the current logged probe completion, metadata
   enrollment, settings epoch, original Session, source and exact plan.
3. Queue an explicit operation once. Derive its key, capture budget and finite
   deadline on the server. Call the internal service with the original Stop event
   and a validator that checks these exact current dependencies.
4. Return the distinct stage-5 action ID through the closed service/HTTP/browser
   result validators. Today the private dispatcher still stages the generic
   `physical_camera_capture` result; do not mislabel it as stage-6 acceptance.
5. Validate retained observation, persist completion successfully, and only then
   publish the image. Stop, source/identity/settings drift, missing logs or failed
   lease exit must withhold it. A preview is retained evidence, not a live stream.
6. Add a dedicated settings-attempt export using the existing bounded readable
   native-wire/redaction codec. Include intent, original references, settings,
   observed readback, attempt/accounting, cleanup, completion and failure phase.
   Keep the original probe export independent. Do not place oversized raw native
   buffers in general logs or silently raise their limits.
7. Exercise the complete original onboarding history with the actual local store,
   then maximum admitted history/record sizes and timing. The current incapable
   service tests model the setup-authentication seam; they do not close this gate.
8. Add policy-derived stage-5 mode/control/USB transport/reopen assessment and its
   separate review. Stage 6 needs its own original freshness evidence. Continue
   to measured overhead calibration and RoArm identity/startup/feedback only
   through their independent commissioning gates.

## Test boundaries and how to extend them

The configuration capacity/originals/service/deadline tests use incapable native
owners, synthetic YUY2 pixels and explicitly modeled setup authentication. The
actual M1/NTFS publishers, leases, probe-result verification, settings derivation,
configuration admission, evidence readback and pixel ingestion run normally.
Injected sibling records test quota routing/arithmetic only; they are not a
fabricated valid USB history. Clock-injection tests establish deadline routing,
not real scheduling guarantees. No camera/serial hardware is opened.

Keep using fresh `--basetemp` and JUnit destinations. Preserve failed drafts and
their explanations; never count them as clean reports. Run the existing probe
scope, export, wizard publication, old capture and coordinator regressions when
changing these joins. Check both actual launchers with `-Check`; startup should
have zero operations, no connected camera/arm and no physical authority.

The verification appendix in `CAMERA_SETTINGS_READBACK_WORKORDER.md` identifies
the checkpoint and exact reports. This document is deliberately not a shortcut
for importing reports as physical evidence or bypassing the wizard's gates.

## Local developer commands

Run these from the workspace root. The launcher checks do not start a server or
connect devices:

```powershell
.\start-rocell-wizard.ps1 -Mode rehearsal -Check
.\start-rocell-wizard.ps1 -Mode physical -Check
```

Run the four new incapable test modules with fresh, explicitly checked report
destinations. Keep the resulting reports, including failures:

```powershell
$configurationRunId = [Guid]::NewGuid().ToString('N')
$configurationBase = "software/runs/pytest-settings-$configurationRunId"
$configurationReport = ".codex-preserved/settings-$configurationRunId.xml"
if ((Test-Path -LiteralPath $configurationBase) -or
    (Test-Path -LiteralPath $configurationReport)) { throw 'Fresh paths required' }
$configurationTests = @(
    'software/tests/unit/test_camera_configuration_deadline.py'
    'software/tests/unit/test_camera_original_configuration_service.py'
    'software/tests/unit/test_camera_configuration_capacity.py'
    'software/tests/unit/test_camera_configuration_originals.py'
)
.\.venv\Scripts\python.exe -m pytest @configurationTests `
    "--basetemp=$configurationBase" "--junitxml=$configurationReport" -q
```

Do not run installed camera-capable workers as a substitute for these tests.
The full original-history and received-hardware acceptance lanes require their
own documented operator conditions and commissioning workflow.

## Public wizard follow-through

The public settings-capture operation, exact logged-settings reference, dedicated
per-attempt export and browser guidance are now implemented in the subsequent
`CAMERA_CONFIGURATION_WIZARD_HANDOFF.md` slice. Use that handoff and its final
verification appendix for current integration status. The checkpoint above
remains an immutable record of the earlier internal-only state. Full-history,
maximum-history and received-hardware qualification gates remain separate.
