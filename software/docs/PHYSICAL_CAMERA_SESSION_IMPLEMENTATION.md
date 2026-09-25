# Physical camera session and prerequisite workflow

Date: 2026-09-08. Status: this file-only session/checklist slice implemented and
public-service tested; the overall physical connection playbook is incomplete.
This follows the tested
[camera planning/native join](PHYSICAL_CAMERA_APPLICATION_IMPLEMENTATION.md)
and preserves the complete camera/arm developer playbook objective.

Follow-up: the [restart-continuity implementation](PHYSICAL_CAMERA_RESTART_IMPLEMENTATION.md)
now adds explicit discovery/opening across app launches. This document preserves
the preceding slice's scope and source-bound test evidence.

## Implementation plan before service changes

At the start of this slice, the wizard could prepare a physical-camera intent
but did not own an actual camera-domain setup session. The following plan was
written before service changes and is now implemented:

1. Add a session-lifecycle component using the existing qualified Windows/NTFS
   M1 runtime and camera-only persistence. Its server-assigned launch directory
   and camera cell/session/source bindings must match the existing intent.
   Construction and status remain inert. Explicit initialization creates a
   fresh all-PENDING session once, never a set of fixture predecessor passes.
2. Add explicit verification/reopening of that same original store, with
   actual camera-record auditing under the existing stage leases. Reopening
   does not initialize a replacement, rerun a worker, clear quarantine or
   silently approve changed state. Preserve partial stores and historical
   verification after failure; scope each operation to its original deadline.
3. Generate a bounded prerequisite document from the actual fixed stage
   catalog, hazard register, epoch policy and immutable hardware-intake
   question set. Derive canonical stage 1–4 ownership from those contracts.
   Record the eight physical epochs as UNMEASURED; retain required observation
   labels, units, methods and evidence requirements. Do not demand every one
   of the 55 intake rows at the camera-receipt stage.
4. Join the current exact camera selection and optional original typed
   source-preflight report to that document. Keep the source preflight's
   separate domain, hash and original source-only limitations. Metadata review
   remains metadata, not received-unit, link-speed or driver qualification.
5. Wire explicit initialize, verify and prerequisite-collection actions through
   Arrival's existing preview/ticket/execute/result/export paths. Collection
   retains the full prerequisite bytes in the actual camera M1 store and reads
   them back. It may put the due source stage into WAITING_OPERATOR, but cannot
   mark source, receipt, identity, installation or hardware qualification PASS.
6. Present storage/session provenance and the generated prerequisite checklist
   in the existing Camera browser/terminal interface. Publish current summaries
   only after retention, source/context checks and diagnostic completion logs.
   Failed/redacted publication keeps historical results and withdraws current
   readiness. No new renderer-side permission or generic raw command interface.
7. Verify real public service → qualified session → retained/read-back
   prerequisite document → refresh → chosen-folder export. Exercise Stop,
   stale context, corrupt records, existing paths, source drift and log failures.
   Preserve old stores, native builds/catalogs and controlled hardware configs.

## Ownership

- Root: application orchestration, Arrival/actions, ticket/publication binding,
  end-to-end tests, this document and final integration.
- Windows camera agent: new `physical_camera_session.py`, lifecycle/storage
  tests and component documentation. No edits to the existing M1/core domain.
- Diagnostics agent: new `physical_camera_prerequisites.py`, actual-source
  collector, pure artifact verification/tests and contract documentation.
- UI agent: existing browser/terminal presentation and producer-contract tests.

## Existing contracts and genuine qualification requirements

Stages 1–3 are NO_DEVICE_IO; stage 4 is READ_ONLY_OS_INVENTORY. All require
actuator power disconnected, which software-file checks do not observe.

- Stage 1 needs original actual source evidence plus independently reviewed
  actuator-isolation/HZ-012 evidence. A coherent preflight is not stage PASS.
- Stage 2 uses the actual static profile/architecture/support checks, not a
  claim that the camera is installed, focused or collision-free.
- Stage 3 owns INT-001–009, INT-017 and INT-019–024. Reuse delivered-camera
  receipt validation and add measured passive-workcell evidence. INT-005 must
  be measured here, but its accuracy-related acceptance is deferred to stage 14;
  no flatness tolerance may be invented or prematurely marked PASS.
- Stage 4 owns INT-018. Current generic/native metadata selection must be joined
  to received-label correlation, stable unit/host-port/driver identity and
  reconnect/reboot evidence before it can qualify a real camera connection.

The generated prerequisite document guides actual intake; it is not those
missing observations. Checkbox completion and readable file hashes alone do
not prove the delivered hardware or its physical power state. The current
native release gate, output ownership/byte-ingestion requirements, installed
calibration, physical arm service and later motion/contact gates remain intact.

## How to use this increment

Launch from the workspace root with `./start-rocell-wizard.ps1 -Mode physical`.
Physical mode here still means a diagnostic interface, not device activation.
In Camera, preview and explicitly confirm these separate actions:

1. **Initialize camera-only setup records** creates a uniquely assigned local
   M1 store, verifies qualified NTFS storage, and starts all fifteen stages at
   PENDING. Construction, page polling and action preview do not create it.
2. **Collect camera build prerequisites** reads exactly the catalog, hazards,
   epochs and static-camera intake-template sources. It keeps their full bytes,
   joins available original metadata/source-preflight context, starts source
   evidence collection at WAITING_OPERATOR and retains/read-verifies the full
   document. Missing measurements stay missing. This is one attempt per launch.
3. **Verify original camera setup records** audits the same store, camera
   records, stage/evidence inventory, attempts, quarantine and leases. It does
   not create missing suffixes, repair a partial store or replay any action.
   The exact checklist is redisplayed only when the original audited inventory
   and current source/metadata/preflight context still match.
4. **Export diagnostic report** creates a new verified report under the user's
   selected `software/runs/wizard-exports` folder. Preserve the manifest and the
   full-result attachments. No earlier exports are overwritten.

The browser and terminal distinguish recorded camera-store stage states from
the overall physical progress list. A CURRENT setup report means that its
storage/report publication completed, not that the camera is connected.
Storage `effects_allowed_by_m1_storage` is not hardware permission.

Operator IDs are procedural labels, not authenticated independent people.
No arm startup, power operation, native helper, camera, serial port or physical
image is accessed by any of these three new setup actions.

## Implementation map

- `physical_camera_setup_service.py`: application-owned session composition,
  exact ticket context, one-use collection, original full-byte retention,
  refresh restoration and publication/history separation.
- `physical_camera_session.py`: bounded original M1 initialization/refresh;
  its facts provider explicitly refuses camera admission. See
  [session API](PHYSICAL_CAMERA_SESSION.md).
- `commissioning_camera_persistence.py`: narrow stage-only evidence readback
  under the original CELL/SESSION leases; no arbitrary path or camera permit.
- `physical_camera_prerequisites.py`: four-source collector and pure canonical
  verifier. See [prerequisite contract](PHYSICAL_CAMERA_PREREQUISITES.md).
- `arrival_wizard_service.py` / `wizard_actions.py`: explicit preview/execute,
  Stop, stale-context checks, final logging and scoped export integration.
- Existing browser `app.js` and terminal renderer: strict cached producer
  projections; intake owners, deferred INT-005 acceptance, hazards and eight
  UNMEASURED epochs. No renderer-side admission or automatic action dispatch.
- `scripts/wizard_physical_camera_setup_smoke.py`: finite real-storage public
  integration check, with a required frozen source hash and a closed four-action
  set. It never uses injected device facts or physical predecessor passes.

## Verification record

Public integration source fingerprint:
`2dfab1fbe57900060c5547510a39c6e2e591c83664fb717deeed2c5b8e5a2d00`.

The real Arrival ticket/service → actual NTFS/M1 → original stage-evidence
readback → refresh → selected-folder export check completed all four actions
successfully. No physical device, helper, inventory or incapable process was
needed for this storage/checklist check.

- Launch: `wizard-a2fdf1e2f8ec441eb2e0068149d6b126`.
- Original cell: `wizard-physical-camera-3bdbae2831da0a71`.
- Original session: `physical-camera-30f1d92fa742285ceb3a72ef026ff8e3`.
- Requirements SHA-256:
  `8b96b0678165b5141f32c2cc38b6379166e228c945eb18a55ac744d63de0d33b`.
- Export: `software/runs/wizard-exports/wizard-20260908T110036648580Z-bff2203dbb184532a27c9d6e8dd9a005`.
- Export receipt: 7 files, 341,139 bytes; original collection attachment was
  compared byte-for-byte in JSON form. Manifest binding:
  `981e9452a9c1aa9662d2f27862d62e5affd218fd8a3316f947502e5f04a33f4a`.
- Final camera-store state: source stage WAITING_OPERATOR, fourteen PENDING;
  all fifteen overall physical progress entries remain PHYSICAL_PENDING.
- Both camera and arm remain NOT_CONNECTED; physical images are absent and
  probe/capture/arm connection/typing execution are still disabled.

The first integration attempt exposed a diagnostic nesting-limit bug after
successful original M1 retention. Its store
`wizard-0d85dd2281b4407b843e8702ba66c38c` was preserved, not repaired or replayed.
The successful check used a fresh isolated test store after the code fix.
The complete readable prerequisite document now sits at the shallower
`steps[0].report.prerequisite_document` field; its retention metadata/reference
remain at `steps[0].report.prerequisites`. Original M1 bytes are unchanged.
Shared JSON depth, string and byte bounds were not weakened. Code review also
caught and fixed wall-clock journal timestamp ordering and checklist loss on
refresh before the successful end-to-end check.

Component checks: 36 session/readback tests, 43 prerequisite tests, 32 new UI
tests, and 101 combined setup/acquisition/action tests passed in their recorded
runs. Some fast application tests explicitly model storage to exercise faults;
they are not substitutes for the separate actual-M1 public check above.
Broader selected non-slow regression: **3,140 passed, 3,355 deselected in
532.63 seconds**, one completed invocation on the frozen source above. The
selection covered Arrival/wizard, native/Windows camera, capture ingestion,
controller/arm feedback, owned processes, coordinator scopes, physical camera,
camera persistence/faults and stage-evidence readback. This is not the entire
repository suite; deselected tests are not claimed as executed.

After the final tests-only restoration/actual-export cases were added, a
separate focused setup/UI/restoration invocation passed **67 tests in 6.82
seconds**. The new tests do not alter the production source fingerprint or
qualify received hardware.

Additional frozen-source checks:

- Both strict browser and terminal renderers accept the actual exported
  111,336-byte session snapshot: REFRESHED_STORAGE_ONLY/CURRENT, first stage
  WAITING_OPERATOR, fourteen PENDING, INT-005 deferred acceptance, five hazards,
  eight unmeasured dependencies and UNKNOWN power. Pending/historical variants
  hide current checklist details and dispatch no action/result fetch. The
  expanded setup UI suite passes **36 tests**; a separate combined frontend
  regression run passes **448 tests**.
- Eighteen restoration/depth regressions cover exact audited inventory,
  changed selection/preflight, source/session/reference tampering, no replay,
  full readable normal/late-failure documents, and rejection of the previous
  excessive nesting. Together with thirteen setup publication tests:
  **31 passed in 2.68 seconds**.
- Six production modules pass mypy with `--check-untyped-defs`; eight edited
  Python files pass Black; browser JavaScript passes `node --check`.
- Physical launcher `-Check` passes with the same source fingerprint, both
  devices NOT_CONNECTED, setup NOT_INITIALIZED and all fifteen physical stages
  pending. This check does not start a server or access devices.
- Wheel: `software/runs/wizard-package-check-2dfab1fb/rocell-0.1.0-py3-none-any.whl`,
  1,800,199 bytes, SHA-256
  `99f3c17caa82fe59f1bea080113c63fe72dd134914f1c09ebe42287fee776513`.
  All 250 packaged Python/HTML/CSS/JavaScript entries match local source bytes.

## Remaining work — do not confuse this increment with live onboarding

1. Camera-specific discovery/opening after restart was completed in the
   [follow-up restart workflow](PHYSICAL_CAMERA_RESTART_IMPLEMENTATION.md),
   including explicit same-original verification after failure. Source migration
   between software versions is still not implemented; do not initialize a
   replacement or edit stored bindings to bypass a source mismatch.
2. Typed delivered-camera/passive-workcell intake and evidence review in the
   UI, including real receipt/label/optics/support dimensions and independently
   reviewed power isolation. Requirements are implemented; observations and
   physical acceptance are not fabricated from them.
3. Full static-contract evaluation, actual epoch records, and explicit review
   transitions for stages 1–4. The current collection cannot pass these stages.
4. Purpose-specific physical probe/capture runtime qualification, identity-bound
   output ownership and bounded verified pixel ingestion. Existing development
   binaries/catalogs were not rebuilt or reapproved to bypass their holds.
5. Received-camera native mode/control/focus/FOV/USB-link verification, finite
   physical frame publication and installed calibration.
6. Separate physical arm identity, supervised first-power/startup evidence and
   bounded feedback-only connection. Power-on can move/reset the arm; camera
   success cannot authorize it.
7. Measured board/device/tool registration, non-contact clearance tests and
   independently enabled single-key/phone-tap execution. Current semantic
   planning and simulation are not evidence of successful physical presses.

Continue these joins from the developer playbook; the overall goal is not
complete merely because this file-only camera slice passes.
