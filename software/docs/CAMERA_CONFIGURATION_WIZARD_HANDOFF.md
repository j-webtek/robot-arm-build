# Camera settings capture: wizard integration handoff

This implements the public-operation portion of
`CAMERA_CONFIGURATION_WIZARD_WORKORDER.md` and continues the original-admission
work described in `CAMERA_CONFIGURATION_ADMISSION_HANDOFF.md`.

The selected camera remains the static overhead purchased Arducam profile;
this change does not alter the placemat, mount, camera purchase assumptions or
RoArm hardware build. Received model, usable focus distance, modes, USB transport
and measured geometry still require their separate checks. A manufacturer
profile is not a measured unit. No hardware was accessed during implementation.

## What an operator can do in this increment

After the original camera prerequisites, current metadata review and successful
logged original probe are available in the same live wizard:

1. Open **Stage reported native camera settings**. Select a mode actually reported
   by that probe and any supported electronic-control intent. This action only
   stages settings and saves its completion; it does not open the camera or
   physically adjust the manual lens.
2. Open **Verify settings with one camera frame**. Its preview binds the exact
   logged settings, original setup, enrollment and server-owned capture plan.
   Supply the current operator label and explicitly check both current actuator
   supply isolation and camera settings/capture consent. Both default off.
3. Confirm only after reviewing the effect statement. When every original
   admission condition passes, the existing native owner may open the selected
   camera, apply the selected electronic settings, read them back and save one
   bounded frame. This is not a continuous stream or arm startup.
4. Inspect the returned settings/readback, verified still image and operation
   result. Image publication follows successful completion logging, original
   cleanup and final source/identity/Stop checks. The still image is not a live
   connection, calibrated geometry, physical-stage PASS or permission to move.
5. Use **Export camera settings-capture attempt**, selecting the exact operation,
   when investigating success or failure. The assigned parent is:

       C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports

The camera next-step panel links to existing eligible forms only. Navigation,
polling and report inspection do not preview, execute, reconnect or retry.
Missing original prerequisites keep the action disabled. Rehearsal uses its
existing incapable workflows; switching UI mode does not qualify hardware.

## Component responsibilities

| Component | Owns | Does not own |
| --- | --- | --- |
| `wizard_actions.py` | Closed names, semantic input, default-off consent, operation timeout | Device paths, browser-supplied budgets or permits |
| `camera_configuration_wizard_contract.py` | Stable names and typed one-frame sizing policy | Native observations, admission or qualification |
| `CameraConfigurationWizard` | Exact logged settings reference, live owner comparisons, one-use queues, eight retained attempts | Original-store authentication or native execution |
| `ArrivalWizardService` | Tickets, source checks, operation logs, cancellation, publication and exports | Browser-granted hardware authority |
| `PhysicalCameraAcquisitionService` | Immutable capabilities/settings, stable intent, original service handoff and staged frame data | Calibration or stage PASS |
| Original configuration reader/admission | Actual probe permit/evidence, current scoped facts, shared capacity and plan binding | Trust in imported wizard reports |
| Existing M1/core/native dispatcher | Original short-lived permit, leases, bounded process, cleanup and original readback | Automatic retries or replacement stores |
| Existing capture workflow/ingester | Mode/control comparison, frame-byte validation and still-preview derivation | Continuous streaming or arm movement |
| Dedicated configuration export codec | Bounded readable diagnostics and credential redaction | Raw image copies, restored connections or replay |
| `app.js` | Strict cached status, navigation and registered action forms | Provider calls from polling or display |

The public action `physical_camera_configuration_capture` is distinct from
`physical_camera_capture`, the still-held stage-6 freshness action. Its internal
native action is `physical-native-camera-configuration-capture-v1`. The native
runtime remains the existing capture runtime; no executable or runtime pin was
changed. Result validation rejects relabeling one capture profile as the other.

## Why settings publication is a separate reference

Native protocol digests use compact canonical JSON. Arrival result/log digests
use the existing pretty ASCII JSON serializer. The settings reference checks the
actual Arrival serialization rather than substituting a different byte format.

The reference can be created only after the exact settings result is validated,
successfully completion-logged and published. It binds the live Session and
enrollment objects as well as their content. It also binds the pinned successful
original probe completion and currently logged metadata provenance. No report
import recreates these process-local owners.

Successful capture changes last-frame/publication state but not the operator's
settings intent. The active guard therefore compares stable intent separately
from the idle check for a pending publication. New settings intent withdraws the
old reference before its intent log, including when that log fails.

The bounded ordinary result history may rotate old results. Settings and attempt
references are pinned separately, but required current metadata ownership is
still enforced. If history rotation retires that ownership, a new capture fails
with retained diagnostics; it does not silently recreate the missing review.
This is not a solution to full-workflow restart/resumption, which remains a gate.

## Limits and failure semantics

- Capture policy: 5,000 ms native capture duration, one frame, equal frame/total
  byte allowance. For a reported YUY2 stride, account for complete padded rows.
  Unknown stride remains unknown and uses the existing finite 64 MiB allowance;
  it is not recorded as a guessed driver observation. Unsupported sizing fails.
- Existing native process/cleanup limits, 30-second maximum permit lifetime,
  remaining-permit rules and 17-second native-window floor remain unchanged.
  The outer wizard action is bounded to 300 seconds and cannot renew a permit.
- Queue a server operation ID once before intent logging; retire the old image.
  Re-executing its ticket returns its receipt, not another camera action.
  A later explicit request has a different key and must requalify current state.
- Preserve at most eight configuration attempts in this wizard launch. There is
  no attempt eviction, reset button or silent retry to bypass the limit.
  Existing ordinary operation/result/storage quotas are not raised.
- Source/identity/settings/owner changes, Stop, failed intent/completion logs,
  redaction, failed cleanup or publication failure withhold the image. Native
  work may already have occurred; a failed UI result must not imply zero effects.
- Export remains available for retained attempts under source/log/ordinary
  operation-budget holds. A changed selected-report ticket must be previewed
  again. Closing the application is not an importable connection checkpoint.

The diagnostic packet keeps the queue's logged settings/operator reference,
later original admission, actual dispatch/readback and completion. Missing
counts stay missing/unknown. The separate original probe packet remains pinned
and unchanged across subsequent settings captures.

Configuration diagnostic, export and part schemas use the distinct
`rocell.camera_configuration_attempt_*` family and
`camera-configuration-attempt-part-*` attachment names. Probe schemas and old
entry points retain their original names. Both use the same closed, bounded
readable native-buffer, redaction and reconstruction implementation. Generic
logs carry a small settings-attempt pointer, not full native buffers or pixels.

## Development verification and boundaries

Use fresh test directories and reports. Run from the workspace root:

```powershell
$configurationRunId = [Guid]::NewGuid().ToString('N')
$configurationTests = @(
  'software/tests/unit/test_camera_configuration_wizard_arrival.py'
  'software/tests/unit/test_camera_configuration_wizard_retention.py'
  'software/tests/unit/test_camera_configuration_wizard_contract.py'
  'software/tests/unit/test_camera_configuration_attempt_ui.py'
  'software/tests/unit/test_camera_configuration_attempt_export.py'
)
.\.venv\Scripts\python.exe -m pytest @configurationTests -q `
  "--basetemp=software/runs/pytest-settings-ui-$configurationRunId" `
  "--junitxml=.codex-preserved/settings-ui-$configurationRunId.xml"
```

The public Arrival lane uses actual logs, M1/NTFS storage, OS leases, configuration
original reading/admission, native evidence validation and image ingestion.
Its metadata provenance and predecessor setup semantic-authentication seams
remain explicitly modeled; native owners are incapable and pixels are tiny
synthetic YUY2 frames. This is not a complete original-history or physical-camera
acceptance test. The retention lane models its context comparator deliberately;
it cannot prove admission. JavaScript tests execute the actual renderer and full
navigation code in a finite DOM model, not a physical-camera browser session.

Run the existing probe, configuration, publication, catalog, export, coordinator
and UI regressions alongside this lane. Do not count intermediate runs twice or
use failed drafts as clean verification. The final checkpoint appendix records
the selected reports, source fingerprint and remaining gaps.

These actual startup checks do not start a server or access devices:

```powershell
.\start-rocell-wizard.ps1 -Mode rehearsal -Check
.\start-rocell-wizard.ps1 -Mode physical -Check
```

For an interactive hardware-free walkthrough, launch rehearsal without `-Check`
and open its printed local URL. Rehearsal success does not clear physical holds.
Do not execute a camera-capable helper directly as a substitute for admission.

## Required next work, not completed by this increment

1. Complete original-history composition without modeled predecessor semantics,
   including actual current metadata/logs, same-store restarts and operation
   history limits. Demonstrate a genuinely reachable end-to-end onboarding path.
2. Exercise maximum original record/family sizes and timing within unchanged
   permit and cleanup limits. Small fixtures are not maximum-history evidence.
3. Implement policy-derived mode/control/USB/reopen assessment and its separate
   review; retain stage-6 freshness as an independent qualification workflow.
4. Measure optics/intrinsics, overhead mount pose, placemat registration and
   target-location accuracy. Board dimensions alone do not calibrate pixels.
5. Finish original-bound RoArm identity, manual power/startup observations and
   feedback-only connection UI. Serial opening/reset may move the controller;
   this camera work grants no arm startup or power permission.
6. Continue reference-frame/noncontact acceptance and only then separately
   authorized keyboard keystrokes and Android taps. Received hardware remains
   necessary for all physical claims.

The overall usable camera/arm onboarding application goal remains active and
incomplete. This document is a developer guide to one integrated slice, not a
claim that the assembled cell can yet be powered and used for typing.

### Concrete starting point for full-history verification

The next bridge is between two existing, complementary test lanes:

- `test_camera_probe_original_scope_readback.py` runs the complete semantic
  original-reader/facts composition but explicitly models storage, leases and
  clock. Its `prepare_reviewed` fixture comes from
  `test_camera_probe_preparation_readback.py`.
- `test_camera_original_probe_service.py` and the new public settings-capture
  lane run actual M1/NTFS/OS ownership but model predecessor semantics.

Neither lane alone is the missing combined proof. Build a fresh, isolated actual
store using production writers and the complete typed predecessor chain; bind
every dependent subject to its real header, events, evidence and launch IDs.
Keep only hardware observations/native owners incapable. Do not replace the
original reader, facts derivation, capacity, leases, clock or result validation
in the combined lane. Never transplant a modeled manifest as if it were a
verified operational store or reconstruct live owners from exported reports.

Drive the actual Arrival metadata/probe/settings/capture/log/export operations
where the APIs exist. Record which earlier stages still need fixture-only
construction, and treat those as explicit integration gaps. Include at least one
same-store application restart at the intended workflow boundary and prove which
references must be collected again. Test the ordinary 32-operation/history
budget, current-metadata retention, eight-capture limit and original-record
quotas as constraints, not numbers to increase until a test passes.

Only after that nominal composition is demonstrated should the same fixture be
expanded toward maximum valid history and timed with actual monotonic clocks.
If it cannot fit unchanged permit/cleanup bounds, retain the measured failure
and investigate redundant work; do not renew permits, skip fresh original checks
or claim a smaller modeled fixture covers the maximum case.

## Verified checkpoint — 2026-09-10

Application source fingerprint:

    440d3f7a3adae328493e1cf48b8f3cca5e2415639f04ae083031730cc13f364e

Final selected reports, with **679 distinct passing test IDs**, no duplicate IDs
and zero failures, errors or skips:

| JUnit report in `.codex-preserved` | Passed | Seconds |
| --- | ---: | ---: |
| `configuration-wizard-complete-20260910-01.xml` | 28 | 707.145 |
| `configuration-wizard-regression-20260910-01.xml` | 485 | 239.843 |
| `configuration-wizard-publication-20260910-01.xml` | 166 | 28.975 |

This is a selected suite, not the entire repository. The 28-case complete lane
means this increment's new public/retention and internal service tests, **not**
the still-missing complete original-history lane. Native owners and received
observations remain incapable/modeled as described above. Some runs overlapped
in separate disposable stores; timings are not hardware performance claims.

Black checked all 18 changed Python files; Mypy checked the nine changed Python
production modules. Node checked JavaScript syntax and executed the actual
status renderer/navigation tests. Both actual launchers passed `-Check` on the
fingerprint above: READY_FOR_DIAGNOSTICS, zero operations, camera/arm
NOT_CONNECTED, no settings reference or attempt, configuration/freshness capture
and arm connection disabled, and no physical authority. Both use the selected
workspace export folder.

All 46 indexed workspace native files still match the earlier v2-runtime
checkpoint; none was rebuilt, repinned or executed as a camera-capable process.
All 24 copies in the prior original-admission checkpoint remain unchanged.
Hardware-build files were not edited, and no physical camera/serial was opened.

Copy-only developer delta:

    software/runs/wizard-exports/developer-checkpoint-configuration-wizard-20260910-01

Its copy index and verification summary record the source/test/document hashes,
report hashes and boundaries. It is a developer delta, not a standalone install
or an operational-store backup that can restore live connections or permits.

Eight failed draft reports are preserved with the checkpoint. They exposed a
missing closed export-part profile, oversized generated Windows pytest parameter
IDs, an overly broad test fixture forbidding legitimate NTFS calls, an invalid
modeled staging label (two diagnostic runs), a re-entered late-Stop test hook,
an outdated closed action/timeout roster, and a sizing test that reached the
native decoder's earlier range error. These were corrected without loosening
device gates, quotas, deadlines or cleanup requirements. Intermediate clean
reports remain on disk but are not counted again in the 679 final IDs.
