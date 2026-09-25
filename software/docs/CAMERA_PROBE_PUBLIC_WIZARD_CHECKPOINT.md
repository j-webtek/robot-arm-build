# Original-bound camera probe: public wizard integration

10 September 2026. Successor to the
[camera-scope original handoff](CAMERA_PROBE_ORIGINAL_SCOPE_CHECKPOINT.md), within
the [developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md).

The wizard now has an implemented, gated **Probe physical camera capabilities**
action and a separate **Export camera probe attempt** action. This is a bounded
capability probe, not a persistent connection, image stream, capture release,
physical commissioning completion, or permission to access/move the RoArm.

No physical camera/arm or camera-capable native worker was exercised during this
implementation. Tests use explicitly incapable producers and modeled hardware
facts. The complete camera/arm application goal remains unfinished.

## Operator procedure

1. Start the existing local wizard from the workspace:
   `./start-rocell-wizard.ps1 -Mode physical`. Startup itself is device-inert.
   Use `-Mode rehearsal` for the existing hardware-free workflows; it cannot run
   the physical probe. `-Check` validates startup without starting a web server or
   dispatching any operation.
2. Complete the existing original-store prerequisites and their explicit
   reviews. The first four original stages must be PASS; stage 5 must be
   WAITING_OPERATOR after the distinct probe preparation/review suffix. The
   later stages must remain PENDING. No checkbox creates these predecessors.
3. Collect and review current camera metadata through the wizard. Its generic
   inventory, native inventory, identity and review operations must have
   successful persisted completion logs. A saved enrollment is not a live owner.
4. Run **Prepare bounded camera probe**, then **Review prepared camera probe**.
   These remain file-only operations. Review makes further admission checks
   eligible; it does not open a camera or bypass installed runtime requirements.
5. Open **Probe physical camera capabilities**. Enter a current operator label
   and explicitly confirm both the disconnected arm actuator supply and this
   single bounded probe. These confirmations default off. A supply-disconnection
   checkbox is an operator report, not electrical measurement or proof of power.
6. Review the preview's exact plan hash, scope and export folder, then execute
   once. The server authenticates the full original setup before issuing any
   short-lived permit. Fresh runtime/endpoint/driver checks and output/storage
   headroom remain mandatory. Missing evidence or changed context holds execution.
7. Inspect the capability result and the separate attempt-status card. Successful
   result retention and completion logging precede publication of reported modes
   and controls. Nothing selects or applies settings automatically. No images
   are captured by this operation, and camera/arm connected flags remain false.
8. Before restart or developer investigation, use **Export camera probe attempt**
   in Diagnostics. Also export the separate preparation bundle when setup needs
   investigation. General logs contain only a pointer to the complete native
   attempt bundle. Do not interpret an uncertain failure as permission to replay.

The confirmed default export destination is:

    C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports

Each export creates a new verified bundle. `-ExportDirectory` remains the existing
explicit launch override. No export is imported as a current enrollment or permit.

## How the components connect

| Component | Responsibility and boundary |
| --- | --- |
| `wizard_actions.py` / `ui/static/app.js` | Closed semantic form fields; explicit preview/execute; inert status and export navigation. No raw device path, executable, command or approval-object input. |
| `ArrivalWizardService` | Current logged metadata owner, original context ticket, one-use queue before intent logging, original operation deadline, Stop/source checks and exact completion publication. |
| `PhysicalCameraSetupService.original_probe_context` | Small cached setup/identity binding for the ticket. It is not substantive admission or original-store authentication. |
| `PhysicalCameraAcquisitionService.run_original_probe` | One existing nonreentrant acquisition lock; bind the actual verified Session; authenticate originals; derive facts; use the existing v2 dispatcher. Never create a replacement store automatically. |
| `camera_probe_original_scope.py` | Complete v16 predecessor authentication under exact CELL/SESSION/CAMERA ownership; later actual inventory/snapshot/source/context checks. Reuse must keep the same original directory, not a cloned store with identical IDs. |
| `camera_probe_admission.py` | Current operator report, accepted-unit continuity, original stage policy/review references, all eight configuration dependencies and current capacity; immutable substantive documents for the existing core. |
| `camera_probe_capacity.py` | Read-only assigned-volume and campaign-record headroom. Accounts for already-owned records without charging the same reservation twice; checks again before subsequent admission. Observation is not reserved disk space. |
| `commissioning_camera_persistence.py` / shared M1 audit | Scoped facts callback receives the actual active transaction. New requests retain full bounded admission documents; readback matches their hashes to the original permit. Legacy records remain readable but cannot invent missing original facts. |
| Existing v2 dispatch/native supervisor | Fresh selected endpoint/driver and installed-runtime checks, bounded one-use native execution, paired run/supervision retention, actual accounting and cleanup. No new camera controller or fallback was added. |
| Arrival completion publisher | Accept exact pending data only after full-result retention and successful completion logging. Late Stop/source/log/identity failure withholds current publication. |

The shared Session still uses its default-denying facts provider. Only the
original-bound probe route supplies the scoped substantive provider. Capture,
serial access, motor startup, power, motion and contact are not admitted by it.

## Diagnostic retention and privacy

The dedicated attempt export includes the cached queue, admission phase and full
facts, available original run/supervision readback, and the pinned completion
outcome. Completion survives ordinary result rotation. Partial admission may
have no permit, native receipt or counters: missing observations remain unknown.

The camera family has a separate bounded codec; generic exporter attachment,
depth, node and total-byte limits were not increased. It preflights complete
reconstruction capacity before creating an output folder. Over-capacity export
fails explicitly instead of claiming a complete truncated report.

Native pipe observations are decoded before credential redaction. JSON fields
are inspected with their original names, and whole-text redaction precedes part
splitting. Export parts contain readable text rather than opaque base64 buffers.
Exact safe UTF-8 can be reconstructed and checked against the original hashes.
Malformed JSON, binary/control data or credentials can require transformation;
changed reports are explicitly not the original bytes. Original M1 files are
untouched. Always review remaining private content before sharing a bundle.

Reconstruction functions restore diagnostic data only, never a live owner,
authenticated Session, current camera observation, permit or retry authorization.
The new UI status card does not copy native buffers or perform source/device I/O
during polling. General-log export points to the dedicated attempt action.

## Fault handling

| Boundary | Required behavior |
| --- | --- |
| Missing original setup/current logged identity | Probe disabled; no synthetic prerequisite, automatic initialization or saved-owner restoration. |
| Changed preview context | Refuse before queuing or dispatch. |
| Intent log fails | Queue remains consumed and exportable, with `claimed=false`; no service/native dispatch. |
| Stop/source/owner/capacity/runtime check fails | Hold; retain available original diagnostics and release owned scopes. No automatic retry. |
| Malformed/incomplete native result or uncertain cleanup | Retain original run/supervision and accounting when available; do not publish capabilities from an unaccepted result. |
| Completion log fails or Stop arrives late | Keep the returned data as historical; do not publish a current observation. A completed native action cannot be undone by changing a UI flag. |

Stop is software cancellation, **not** a robot emergency stop. No supply state
or safe physical condition is inferred from process exit or handle cleanup.

## Verification record

Current source fingerprint:

    8d93cc94905cc3a4bf34ac86e4d626d509ad110e92a186265f90922a4a8842fb

Final selected reports under `.codex-preserved`:

| JUnit report | Passed | Seconds |
| --- | ---: | ---: |
| `probe-public-ui-final-20260910-01.xml` | 265 | 62.84 |
| `probe-public-core-final-20260910-01.xml` | 59 | 476.60 |
| `probe-public-full-final-20260910-01.xml` | 2 | 330.82 |
| `probe-public-retention-final-20260910-01.xml` | 4 | 10.97 |
| `probe-public-display-final-20260910-01.xml` | 5 | 1.04 |

These reports contain 335 passing executions covering 327 distinct test IDs,
with zero failures, errors or skips. The final display-only wording clarification
is covered by the display report; persistence/admission/dispatch code did not
change after its final run. Failed draft reports remain preserved. This is not
the entire repository suite or received-hardware qualification.

Mypy passed for all 13 changed production Python modules. Black checked all 23
changed Python production/test files. Browser JavaScript syntax passed. Both
launcher modes passed `-Check` on the final fingerprint: zero operations, camera
and arm NOT_CONNECTED, probe NOT_ATTEMPTED, no physical authority and the confirmed
workspace export folder. All 46 previously indexed native files matched their
hashes; no native source/binary was rebuilt, repinned or executed.

Copy-only developer delta checkpoint:
`software/runs/wizard-exports/developer-checkpoint-camera-probe-public-20260910-01`.
Its index identifies copied inputs, hashes, test reports and startup checks. It
is not a full source archive, importable commissioning session or device permit.

The test lanes deliberately separate evidence claims:

- The public wizard/service/M1/core/dispatch lane uses actual local NTFS storage,
  OS leases, intent/completion logging and export files, with an incapable native
  owner. Semantic predecessor authentication and device/admission observations
  are explicitly modeled in that lane.
- The complete original-reader/facts composition runs all real predecessor
  verifiers on the same typed v16 history. Storage, hardware observations and
  timing are modeled. It is not a maximum-size real-store performance result.
- Capacity, admission retention/tampering, one-use lifecycle, browser rendering,
  redaction/large-buffer reconstruction and unchanged legacy paths have separate
  tests. No single lane claims genuine physical camera commissioning.

## Remaining work, in order

1. Expand the full-history + real-M1 composition and measure worst-case original
   read/revalidation latency with representative maximum-sized records. The full
   read is bounded to 180 seconds inside the original 300-second operation; the
   existing permit lifetime remains 30 seconds, not a renewable UI timeout.
2. Implement original stage-5 capability assessment/review and the persistent
   stage transition. A successful capability observation currently does not pass
   stage 5. Export/reopen must preserve failed evidence without replay.
3. Join the already implemented internal settings/capture/data workflow to the
   original stage-6 admission, bounded public capture action and image/baseline
   qualification. Keep explicit mode/control selection and stale-frame handling.
4. Continue measured overhead-camera intrinsics and placemat registration,
   tip/tool/reference frames, held-out accuracy checks and noncontact baselines.
   Simulated geometry does not substitute for installation measurements.
5. Finish the RoArm identity-bound connection/startup/feedback UI and original
   safety observations. Firmware startup behavior and power conditions need
   separate verification; no keyboard or phone contact follows automatically.
6. Only after those prerequisites, separately authorize and test single keyboard
   keystrokes and Android taps against the calibrated placemat and contact limits.

This increment closes the public bounded-probe join, not the complete connection,
camera-stream, calibration or robot-control application. The overall goal stays
active. Previous delegated agents remain terminal with account usage errors;
the root agent completed this increment locally without a reset or workaround.
