# Contained camera-process rehearsal presentation

The Guided rehearsal page and headless terminal display the optional cached
`commissioning_rehearsal.camera_process` projection. The source is the closed
`rocell.rehearsal_owned_camera_summary.v1` evidence view, not the private complete
evidence, native output, or a live provider. An absent value adds no status claim.
Malformed, oversized, unknown-field, or internally inconsistent values display
`CAMERA_PROCESS_NOT_VERIFIED` without expanding the supplied record.

## What the operator can distinguish

- **Actual child process:** retained creation/resume/tree-exit observations,
  outcome, Windows return code, bounded output-byte counts, request hash, primary
  error, and retained/omitted cleanup-error counts.
- **Synthetic native contract:** receipt validity, synthetic native status,
  cleanup result, six bounded API counters, and frame count. An `OK` fixture
  receipt never overrides a failed, cancelled, or timed-out child.
- **Retained frame metadata:** capture-binding status, frame/logical-byte counts,
  manifest, plan, envelope, and source-contract hashes. Matching metadata is not
  file-content verification; the backend separately verifies content on reopening.
- **Dependencies:** exact evidence, source, attempt, session, permit, operation,
  selected-identity, and settings-epoch references remain inspectable.

All pixels are source-derived incapable fixtures, not received camera frames.
Both complete and incomplete rehearsal displays retain `NOT_CONNECTED` /
`NOT_QUALIFIED`, `device_cleanup_proven=false`, and `physical_authority=false`.
Process cleanup proves neither physical device cleanup nor driver, USB3-link,
received-unit, or capture-backend qualification. A zero-frame retained metadata
summary is permitted only as incomplete evidence, never a complete capture.

## Explicit workflow, unchanged authority

The registered `rehearsal_owned_camera_campaign` action uses the existing generic
preview and exact-ticket confirmation workflow. Its closed inputs are a frame
count of 1–4 and a named fixture fault (`none`, `identity-mismatch`,
`cleanup-uncertain`, `child-timeout`, or `malformed-result`). Eligibility and stage
gates remain backend-owned. This presentation introduces no action controls,
arbitrary command, provider import, path input, or physical-mode activation.

Reading or refreshing the display does not launch/resume/retry a child, read
artifacts, discover devices, acquire images, or dispatch another action. The card
does not load a preview. The existing Camera image API and its separate current
image-provenance caption remain authoritative for any explicitly published
synthetic preview. A held or uncertain result must be inspected, not replayed
because a status card refreshed.

## Developer checks

`test_wizard_owned_camera_process_ui.py` exercises the browser DOM and terminal
with bounded cached projections, including incomplete process/native/capture
combinations, safe counter limits, omitted errors, unknown fields, escaped text,
no-dispatch rendering, and separate prepare/execute confirmation. These fixtures
are presentation tests, not evidence of process containment or dataset commits.
The evidence producer and public service have separate integration tests.

## Reproducible public-API smoke

With the development environment installed, Windows storage available, source
frozen, and other expensive commissioning tests stopped, run from the repository
root:

```powershell
.venv\Scripts\python.exe software\scripts\wizard_owned_camera_smoke.py --frame-count 1 --fault none --assess-and-review
```

The script creates a **new** separate rehearsal, collects/assesses/reviews the
first four canonical stages, opens stage five, records synthetic settings, and
executes only `rehearsal_owned_camera_campaign`. The optional
`--assess-and-review` assesses and freshly reviews a nominal complete stage-five
result, stopping before any stage-six campaign. Operator/reviewer labels are
distinct fixture labels, not authenticated proof of two people.

For a held result, select one closed fault instead; do not add the review option:

```powershell
.venv\Scripts\python.exe software\scripts\wizard_owned_camera_smoke.py --frame-count 1 --fault cleanup-uncertain
```

Frame count is limited to 1–4. Other faults are `identity-mismatch`,
`child-timeout`, and `malformed-result`. There is no physical-mode switch, host
device inventory, old binary-campaign fallback, arbitrary command, session
reopen, or automatic retry. Optionally pin the expected frozen source with
`--expected-source-sha256 <64-lowercase-hex-digits>`. Each action also uses the
service's source-bound ticket checks.

The normal path uses at most 19 explicit actions including export, below the
32-operation launch budget. The script prints actual session/operation/source
identities, the public campaign result, the safe process projection, and the
assigned export path with independent `verify_export` results. Export is
attempted for both nominal and held outcomes. A local operation-wait timeout
requests the registered diagnostic Stop once and drains for a bounded interval;
an unresolved operation/export is reported without replay or a robot E-stop
claim. The service is always shut down in `finally`.

This script uses real Arrival/M1/owned-child integration, not test doubles. Its
presence, formatting and compilation are not a successful execution record.
Reserve about 85 MB per frame plus storage margin; running it creates durable
rehearsal, artifact and diagnostic records. All generated pixels remain
incapable fixtures, and every physical stage remains pending.
