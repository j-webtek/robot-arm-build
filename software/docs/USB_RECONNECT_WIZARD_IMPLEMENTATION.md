# Explicit USB reconnect trial and physical-node observation

Status: fresh-BASELINE and five-step RECONNECT_ABSENCE public hardware-free
acceptance verified; AFTER_RECONNECT and AFTER_REBOOT remain unfinished,
2026-09-09. The first absence test failed collection and remains preserved.
After timing/readback fixes, fresh run 02 passes one test in 700.42s, including
the baseline, all absence actions, complete export/restore and fresh reopen/no
replay. Storage is genuine; hardware/process observations are modeled. See the
[absence work order](USB_ABSENCE_PHASE_IMPLEMENTATION.md) for exact evidence,
timing boundaries, scoped regressions and the remaining work.
No received-hardware USB, camera, actual CIM or arm query ran in these tests.
This work continues the
[verified baseline integration](USB_IDENTITY_WIZARD_DISPATCH_WORKORDER.md) toward
the full [camera/arm developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md).
It does not release camera capture, robot power, serial access or motion.

The next implementation slice is now detailed in
[AFTER_RECONNECT implementation](USB_AFTER_RECONNECT_IMPLEMENTATION.md): an
inert typed physical-absence successor and fresh preparation, followed by the
original v12/service/UI/export integration. Component availability is not public
reconnect acceptance; the completed public boundary remains ABSENCE.

## What changes for the operator

The wizard offers an explicit **Declare USB qualification trial** action
after the exact received-camera identity workflow, or after a clean completed
baseline diagnostic. It records cable/port labels and a new original trial plan
before any trial measurement. It is a file-only action. The old standalone USB
baseline is retained as a diagnostic predecessor, not relabeled as trial data.
The new Camera panel distinguishes a declared plan from collected evidence.

The intended measurement sequence remains BASELINE, RECONNECT_ABSENCE,
AFTER_RECONNECT and AFTER_REBOOT. Every phase needs its own contemporaneous boot
observation and exact original inputs. A new application launch is not a reboot.
Unknown effects, quarantined originals and partial writes cannot become an
automatic retry. Later phase-collection controls must be implemented through the
same service/coordinator/original-store boundary before being exposed as usable.

## Why an explicit new trial is necessary

The existing standalone baseline did not declare a qualification plan or collect
a boot report alongside its USB query. The existing series codec requires both
observations inside the phase interval, after plan creation. We cannot backdate
a plan or attach a later boot report to that old query. A new, explicitly named
qualification trial is a distinct workflow, never replay of the earlier permit.

The native camera endpoint inventory also cannot establish physical USB-node
absence. A disabled or missing camera endpoint is not evidence of an unplugged
physical device. The new producer must inspect the physical instance originally
observed in the baseline, and retain fresh request-bound acquisition evidence.

## Implementation ownership and contracts

1. Original-store agent: additive v9 trial declaration/readback using the
   existing `UsbQualificationPlan` codec. Retain role
   `camera-usb-qualification-plan-v1:usbtrial-<32 hex>`, at most 16 KiB.
   REQUESTED moves the exact eligible stage-4 predecessor to WAITING_OPERATOR;
   DECLARED retains the plan reference and moves to REVIEW_PENDING. Retain
   incomplete writes explicitly; do not auto-finish them on restart. Existing
   v7/v8 readers and historical baseline effects preserve their original meaning.
2. UI agent: one service-backed file-only declaration action, server-derived
   original/source/trial identifiers, explicit operator confirmation, and a
   separate closed `usb_qualification` cached view. Existing baseline display
   becomes historical when the successor plan owns the current stage. The view
   must not manufacture phase observations, comparisons or a qualification PASS.
3. Root: complete additive diagnostic export v2, preserving v1 exports unchanged
   when no trial exists. Include the full trial original, request/declaration
   evidence and partial state; keep existing attachment and privacy limits.
4. Windows agent: independently audit the host-boot process owner, use a fixed
   detached-pipe owner where warranted, retain strict Job process/cleanup
   accounting, and preserve historical v1 receipt compatibility. Test only the
   incapable boot fixture; actual CIM execution remains NOT_RUN.
5. Root: implement a separate bounded physical-USB-node presence producer and
   strict request/result codec. Do not edit or repin the already reviewed USB
   descriptor-query executable. Keep real Windows API code separate from the
   incapable test adapter so hardware-free tests cannot enumerate devices.

## Physical-node producer design

### Active owned-acquisition integration

The next implementation connects the producer to original admission; it does
not substitute a runtime flag or the old USB descriptor-query permit. A new
closed `PHYSICAL_DIAGNOSTIC_USB_PRESENCE` domain will admit only
`physical-native-usb-presence` at CAMERA_IDENTITY, with CELL/SESSION/CAMERA
leases, four bounded list calls and no device handles, writes, frames or energy
envelope. The original 30-second permit lifetime is not renewed; dispatch must
retain at least 15 seconds within it, including cleanup.

The selected identity will be the immutable phase-binding subject reconstructed
from the declared original plan, exact declaration event and complete new-trial
BASELINE phase/sources. Its target is derived from that baseline's physical USB
instance, never a UI text field. A separately pinned runtime binds the exact
presence helper, shared parser inputs, build record and incapable alternative.
Neither file agreement nor pure binding validation authenticates original M1
references, approves a runtime, collects a phase or issues a permit.

Runtime approval has its own required `runtime_review_sha256` in the new
admission snapshot; it is not hidden inside the phase identity or hazard report.
The pure review binds the exact presence policy, runtime/helper, source/original
context, physical target and pre-review operation. The dependency order is
operation, then review, then admission, then permit, then native request. There
is no circular review/permit hash in the operation and no caller-controlled
expected review hash standing in for original authentication.

The presence M1 facts retain the full review, its original evidence reference
and committed event. Admission reads the actual review bytes under leases and
requires stage-4 REVIEW_PENDING to BLOCKED with
`CAMERA_USB_PRESENCE_RUNTIME_REVIEWED_<TRIAL_SUFFIX>`, followed by an adjacent
explicit BLOCKED to WAITING_OPERATOR event
`CAMERA_USB_PRESENCE_QUERY_REQUESTED_<TRIAL_SUFFIX>`. Both cite the same review
reference. No existing stage transition changes. Before any durable reservation,
the intended helper and operation must match that original review; readback and
consumed-scope revalidation repeat the joins. A review records exact diagnostic
acknowledgment, not canonical PASS or authenticated independent people.

Parallel ownership: Windows agent implements runtime inspection; original-store
agent implements pure phase binding; UI agent implements the closed coordinator
domain and in-process tests; root implements fixed stage policy and additive M1
admission/storage integration. The application service must still supply fresh
original facts and runtime review before exposing any collection action. Existing
domain permissions, old records and physical release gates remain unchanged.

Acceptance requires independent negative binding/domain tests, original-storage
round-trip and cross-domain audit, followed by actual incapable owned-run tests
and service/UI phase collection. No development check in this increment may
execute production presence, USB, CIM, camera or arm operations.

### Application path after owned presence admission

#### Active fresh-BASELINE implementation

The current work adds the first collected trial phase through the application,
not a replacement success criterion for the four-phase workflow. Ownership is:
the Windows agent adds the phase-bound descriptor operation; the original-store
agent adds v10 phase roles/readback and setup serialization; the UI agent joins
service actions, trusted acquisition timing and both renderers; root joins the
separately bounded boot observer, diagnostic export and integrated verification.

Begin BASELINE must establish its original interval before new native metadata
acquisition. Existing metadata packets alone have no UTC acquisition bracket;
changing their hash or reviewing them later cannot prove freshness. The service
must retain its own acquisition provenance and reject pre-phase cached reports.
The exact pre-review descriptor operation is v2, with the original plan,
header/trial/ordinal, `usbphase-<32 hex>` operation identifier and predecessor.
Legacy v1 remains the standalone diagnostic subject.

The immutable stage transition table still applies: REVIEW_PENDING cannot go
directly to WAITING_OPERATOR. Explicit baseline entry first records BLOCKED,
then the requested action enters WAITING_OPERATOR. Boot observation requires a
separate durable request and bounded admission, never reuse of the USB permit.
After crash or uncertain completion, that request remains incomplete and cannot
be silently replayed. A complete retained phase must join the exact original
plan, acquisition records, reviewed operation, boot observation and USB campaign.
Partial state and unknown effect evidence must survive export and same-store
reopen. Tests use incapable providers or clearly MODELED earlier hardware facts;
actual camera, USB, CIM and arm operations remain NOT_RUN in development.

The next application-facing acceptance is a genuinely new trial BASELINE, not
another standalone descriptor diagnostic. One service owner must implement its
prepare/review/collect-next actions together with an additive original reader,
cached browser/terminal projection, full export and same-store reopen. Server
code derives the next phase, target and original prefix; UI input is limited to
operator labels, manual-event acknowledgments and explicit action consent.

The existing `UsbIdentityOperation` v1 has no phase context and its hash cannot
be reused for the three observed phases. A separately versioned phase-bound
operation is required before preparing each descriptor campaign. Keep old
operation bytes and v7/v8/v9 reader meanings unchanged. The baseline also needs
its own current reviewed metadata and independently owned host-boot report.
Host-boot and descriptor observations need separate bounded admissions within
one original phase interval: a 12-second boot lifecycle and a 20-second USB
minimum cannot fit in a single 30-second permit. No TTL renewal may hide this.

The original four-phase reader/assessment must use a versioned physical-node
absence join. The existing v1 endpoint-only absence intentionally cannot pass;
do not change it into physical removal evidence. Reconnect requires fresh
identity metadata and review. AFTER_REBOOT requires actual same-host boot-epoch
change, explicit original-store reopening and new observations, not a new app
launch. Final review must show bounded actual serial/driver/topology/boot values
alongside the hashes; a generic `VALUE_IN_ORIGINAL` message alone is insufficient
for reviewing an exact subject. Stage-5 entry, runtime/capture release and arm
commissioning remain later explicit decisions.

Use only the local Configuration Manager present-device-ID list, filtered to
the exact USB enumerator/device-ID portion of the previously observed physical
instance. Microsoft documents `CM_GETIDLIST_FILTER_PRESENT` as excluding
nonpresent devices, and permits combining it with an enumerator/device-ID
filter. See [CM_Get_Device_ID_ListW](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_id_listw).

The size and list reads use identical fixed filters. Size is an allocation
bound, not the returned string length; parse the terminating MULTI_SZ correctly.
See [CM_Get_Device_ID_List_SizeW](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_id_list_sizew).
Bound the buffer, number of IDs, API calls, output and acquisition duration.
Retain two complete observations with explicit timing and request identity.
An API error, truncated list, malformed ID, timeout, cancellation or inconsistent
samples yields HELD, never absence. Do not use a failed locate call as absence.

The producer reports whether this exact physical device node was listed at its
two observation instants. It cannot prove the mechanical cause of removal,
continuous absence between samples, power isolation or authenticated identity.
The operator unplug step and original baseline/boot/phase joins remain separate.
No hub/device handles, descriptor IOCTLs, camera frames, settings writes, device
disable/remove requests, remote calls or reboot command belong in this producer.

## Verification and completion requirements

- Pure native/codec tests: present/absent/change, wrong target/filter, same-model
  second unit, mixed-case IDs, invalid MULTI_SZ, API failures, buffer growth,
  bounds, late/cancelled work and exact request/result correspondence.
- Incapable process tests: explicit request/READY/RELEASE, one-process ownership,
  bounded pipes, original deadline, cancellation and complete cleanup. A missing
  receipt must retain unknown observations, not zero API calls.
- Original-store tests: actual isolated durable plan declaration/reopen,
  old baseline preservation, no replay, partial writes, source/epoch substitution
  and refusal of uncertain/quarantined predecessors.
- Public integration: actual Arrival tickets, consent, queued execution,
  completion publication, browser/terminal rendering, full plan export/restore,
  chosen workspace export folder and inert startup in both modes.
- Preserve prior USB baseline tests. Record commands and exact scope here;
  component tests are not proof of the full four-phase workflow or received unit.

The remaining full-goal work includes original phase acquisition/series review,
finite camera probe/settings/capture, installed optical/board calibration,
identity-bound feedback-only arm commissioning and supervised noncontact
acceptance. This work order does not narrow that goal to plan declaration.

## Verified trial-declaration checkpoint

Implemented APIs and modules:

- `physical_camera_usb_trial_readback.py`: actual original v9 declaration,
  exact existing plan reconstruction, private prefix verification, partial
  state retention and original predecessor checks. Setup now owns a dedicated
  `usb_qualification_transaction`; it does not call a device producer.
- `PhysicalUsbIdentityService`: `physical_usb_qualification_declare` through
  the existing action-ticket/consent/queue/publication owner, separate cached
  `usb_qualification` view, and preserved historical baseline display.
- `physical_usb_identity_export.py`: exact additive diagnostics/export v2;
  no trial still emits the original v1. All partial states are reconstructible.
  Schema relabeling, source mismatch and altered subject hashes are rejected.
- `host_boot_observation.py`: v2 adds exact detached one-process Job ownership
  and resource/cleanup accounting. V1 readback is unchanged, not upgraded.
- `native/windows_usb_presence/` and `usb_presence_protocol.py`: separate real
  CM producer, incapable core/entry binaries, strict Python request/receipt
  codecs and bounded READY/RELEASE handshake. It is built but not yet connected
  to a qualified application process owner, original admission or UI collection.

Executed checks below are scoped and overlap; do not sum them as a full suite:

- Root combined export/presence/host/UI/legacy action selection: **351 passed
  in 16.90 seconds**. It covers the new native fixture/entry codecs, v1/v2
  exports, host observations, declaration card and existing baseline actions.
- Existing qualification-series pure selection: **30 passed, 5 deselected in
  104.17 seconds**. This preserves the existing v1 comparison semantics; it does
  not supply the still-missing new original physical-absence series join.
- Host lane: **101 tests in 1.74 seconds**, plus **103 process/USB regressions
  in 8.12 seconds**. Actual incapable children demonstrate detached suspended
  creation, exact Job membership/limit one, bounded streams and complete cleanup.
  Real CIM, camera and serial entrypoints were not invoked.
- Presence native lane: three CTest groups passed in **6.53 seconds**. The
  production executable was built, never executed. Its source/artifact hashes
  match the separate development build record; old descriptor-query pins remain
  unchanged. Review-driven late-result tests preserve returned native codes
  after timeout/Stop, and an unreturned call keeps its code null.
- Original trial lane: 24 new pure cases passed across overlapping selections;
  one actual isolated NTFS retention/reopen test passed in **118.13 seconds**,
  and five old-workflow compatibility cases passed in **24.48 seconds**. That
  storage test explicitly completed its own partial test transaction; public
  service acceptance is a separate check, not inferred from it.
- UI lane: eight new composed cases passed across 112.07-second and 52.79-second
  selections, plus 133 focused UI/catalog/Arrival tests in 6.74 seconds and a
  clean-v8 successor case in 26.65 seconds. Earlier received/source/host facts
  are modeled. Node renders cached fake DOM only, not a live browser/device.

A separate actual-NTFS public Arrival acceptance test now passes: **1 passed
in 178.82 seconds**. The public declaration took **32.313 seconds**, within its
unchanged 120-second budget. It exercised preview, confirmation, queued action,
durable completion publication, dedicated full-plan export, general log export,
fresh original v9/raw-plan readback, explicit refresh and new-service adoption.
Duplicate execution did not replay the declaration, and later stages remained
PENDING. Real local storage was used; all earlier hardware facts were explicitly
MODELED and device/process/phase-collection entrypoints were forbidden.

Run from `software/`, with a new unused isolated `--basetemp` each time:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/test_arrival_usb_trial_actual.py -q -s --basetemp=C:\Users\Jack\AppData\Local\Temp\rocell-usb-trial-public-20260909-03
```

That successful run's directory is preserved. Do not reuse the command's
existing `--basetemp`, because pytest may clear it. Runs 01 and 02 are also
preserved: they exposed test-only assertion/refresh-sequencing mistakes, not a
production failure; the final run corrected those tests without relaxing gates.

Both successful diagnostic bundles were copied unchanged into
`software/runs/wizard-exports/hardware-free-usb-trial-20260909-verified/`.
Both copied bundles pass `verify_export` using their absolute paths. The
collection README records the raw manifest hashes, modeled scope and originals.
These exports are review material, never received-hardware qualification.

Final source fingerprint:
`19323cc4eeafd6184213bea7e9787ab1a138cb118fc1d0a7b7634bccd3a10000`.
Both `start-rocell-wizard.ps1 -Mode rehearsal -Check` and
`start-rocell-wizard.ps1 -Mode physical -Check` passed at this source with
READY_FOR_DIAGNOSTICS, zero operations, no physical authority, NOT_DECLARED trial
status and the confirmed workspace export folder. A real local browser visual
check of the fresh rehearsal Camera panel confirmed the declaration/status
layout and disabled unavailable actions. No form or hardware action was run;
the temporary tab and listener were closed afterwards.

The offline wheel under
`software/runs/usb-reconnect-wheel-09e03b11e33649c699e341bbe3345566/`
matches all **301 Python/UI entries** and **305 RECORD digests**, with no missing,
extra, duplicate or mismatched entries. Its SHA-256 is
`0ffc609eca3a776c580d5c10d0efc33d6b8024dec719aefa15f6c62f4234f0fc`.
The adjacent `verification.json` and build log record exact checks. No network,
installation or native rebuild occurred in that package check. It is not a
clean-host installation test or a physical-runtime release.

No physical hardware was operated during this increment. Full-goal acceptance
remains open: qualified owned presence dispatch, original four-phase acquisition
and review, camera controls/capture, calibration and arm commissioning are still
required before live keyboard or phone interaction can be claimed.

## Original-bound presence-admission checkpoint

The additive source now includes:

- `usb_presence_stage_policy.py`: fixed four-list-call, camera-lease-only policy;
  no writes, device handles, frames, retries or energy envelope.
- `physical_usb_presence_binding.py`: reconstructs an intended physical-node
  target from a predeclared new-trial BASELINE and its full original USB,
  metadata and current owned host-boot sources. It does not collect absence.
- `usb_presence_registration.py`: separate fixed production/incapable runtime
  candidates and file inspection, with exact build/source/artifact pins and
  source checks before/after inspection. Process budget is 13 seconds plus
  2 seconds cleanup, matching the unchanged 15-second minimum remaining window.
- `usb_presence_review.py`: exact pure review of policy, runtime/helper,
  phase/target, original context and pre-review operation. A review constructor
  neither authenticates originals nor grants authority.
- `UsbPresenceAdmissionSnapshot` / `PhysicalUsbPresenceCoordinator`: the new
  phase and review hashes participate in exact admission freshness, while old
  snapshot schemas remain unchanged. Original 30-second permits are never renewed.
- `commissioning_usb_presence_persistence.py` and the separate M1 record domain:
  frozen full facts, actual original-review bytes/event/request authentication,
  reviewed operation/helper comparison before reservation, consumed-scope checks,
  full sibling-ledger audit and explicit known/unknown terminal readback.

Review found and corrected the admission path's use of a stage-only reader
while holding CAMERA. It now uses the existing camera-scoped original reader.
A shared pre-reservation validation hook avoids an extra complete admission
read while still checking fresh review subjects before any durable write.
No historical permissions or native build pins were changed.

Settled scoped checks (selections overlap; these are not a repository-wide sum):

- Root policy/coordinator/runtime/wire/permit selection: **242 passed in 2.23s**.
- Review/coordinator/shared in-memory regressions: **412 passed, 2 actual-M1
  cases deselected in 10.82s**. This includes 142 review and 90 coordinator cases.
- Pure full-baseline binding matrix: **9 passed in 35.08s**, using complete
  explicitly MODELED physical-shaped observations and original references.
- Legacy USB actual-NTFS integration: **2 passed, 25 deselected in 72.55s**;
  preserved under `C:\Users\Jack\AppData\Local\Temp\rocell-presence-legacy-m1-20260909-01`.
  These use real storage with incapable in-process workers, not device queries.
- Existing Arrival/USB/declaration UI/action/export selection: **182 passed
  in 9.73s**. No UI collection control was added by this increment.
- Four root policy/M1 source files pass mypy and Black. The independently owned
  runtime, binding and review/coordinator lanes also pass their scoped checks.

Both inert startup checks passed at
`3f709a2c7e7352d7f4a0d390e22d97ef1879bc9bb10eff6e560e516451aa3664`:
READY_FOR_DIAGNOSTICS, zero operations, no physical authority, NOT_DECLARED,
and the confirmed `software/runs/wizard-exports` parent.

The offline wheel under
`software/runs/usb-presence-wheel-f6a672de06884db9a331087cc0e3fe0a/`
matches **306 package entries** and **310 RECORD digests**, including unchanged
source fingerprint before/after, ZIP CRC and README metadata. Wheel SHA-256:
`671c5ad3b16f7b3b164737ac2afaed5b31a220ff357f2d88f47a2fcb7e13dcb3`.
The adjacent verification report records scope. This is package-content proof,
not a clean-host installation, native runtime release or hardware qualification.

The new presence-persistence suite has settled results across two invocations:

- Full run 02: **12 passed, 1 test-only assertion-text mismatch in 170.37s**.
  Ten pure cases and two actual-NTFS cases passed. Clean completion verified
  original review authentication, complete facts/permit readback, sibling-ledger
  audit and reopen without replay. Unknown completion retained quarantine with
  exactly three request/evidence/result records and no fabricated receipt.
- Targeted run 03: the corrected final actual-NTFS case **passed, with 12
  deselected, in 40.74s**. Changed inputs are rejected at the fresh challenge,
  before intent or worker execution; reopen cannot replay the prepared request.
  Only the expected error text and formatting changed after run 02, not
  production behavior or the refusal assertions.

This is coverage of all 13 cases across those invocations, not a claim that one
all-green 13-case command ran. The earlier run 01 unknown-result smoke exposed a
test-only expected-record-count mistake, corrected without inventing receipts.
All original trees are preserved under
`C:\Users\Jack\AppData\Local\Temp\rocell-usb-presence-m1-20260909-01`,
`C:\Users\Jack\AppData\Local\Temp\rocell-usb-presence-m1-20260909-02` and
`C:\Users\Jack\AppData\Local\Temp\rocell-usb-presence-m1-20260909-03`.
Do not reuse these existing pytest `--basetemp` paths. The run 02
`test_actual_ntfs_review_permit0/isolated-camera-contract` store intentionally
ends with rehashed sibling-record corruption to prove audit refusal; it is
negative-test evidence, not an intact successful session head. These tests used
real local NTFS stores with explicitly MODELED hardware facts and incapable
in-process workers. No native helper, device, CIM query or wizard export ran.

The next required application step remains the new-trial BASELINE and subsequent
original four-phase collector/reviewer described above. Runtime preparation,
owned presence dispatch/evidence, the phase-bound descriptor operation, original
phase readback and service/UI collection/export are not yet complete. Full
camera controls/calibration and arm commissioning remain part of the active goal.

## Fresh-BASELINE integration: verified held-path checkpoint

The public begin/prepare/review/collect actions now join a new original v10
baseline and fresh server-recorded acquisition timing. The actual local-storage
acceptance below verifies the complete **BOOT_HELD** path, including export and
reopen. It does not verify a nominal physical boot-to-USB collection or finish
the four-phase qualification workflow.

Settled component checks during this work:

- Earlier source/session and USB v8/v9 reader regressions: **163 passed in
  662.81s** (`test_physical_camera_session_readback.py`,
  `test_physical_source_qualification_readback.py`,
  `test_physical_camera_usb_readback.py` and
  `test_physical_camera_usb_trial_readback.py`). The new additive extension
  preserves the tested earlier original formats; this is not full application
  or received-hardware acceptance.
- New v10 preparation/original-prefix tests: **11 passed in 149.35s**. Separate
  modeled boot/USB-result cases: **6 passed in 84.04s**, including full nine-role
  known-HELD retention, incomplete original campaigns and stale/rehashed input
  rejection. These use modeled storage/observations with real codecs.
  A further **5 cases passed, 11 deselected, in 67.16s**: partial runtime review
  must match the preparation's launch, v9 cannot accept v10 evidence, and unknown
  roles/events/citations or a substituted PASS are rejected. Results are from
  separate scoped invocations, not one combined all-green run.
- A separate actual-NTFS v10 test **passed in 177.63s**: six original baseline
  roles and four committed events survive lease exit and fresh-owner reopening
  byte-for-byte, while stages 5 onward stay PENDING. The physical/OS facts are
  explicitly modeled and process/device entry points are forbidden. This is
  actual storage/readback coverage, not public metadata acquisition or a
  successful physical USB campaign.
- Phase-bound descriptor operation plus legacy campaign tests: **67 passed in
  93.85s** (40 new, 27 legacy). Six additional deadline cases passed in 1.10s;
  one actual-child test was excluded. No native process or device operation ran.
- Additive full-baseline diagnostic export v3 plus existing v1/v2 exports:
  **87 passed in 3.77s** in the final scoped run. These verify every closed partial/terminal phase shape,
  full role and in-progress attempt preservation, actual assigned-directory
  export/manifest reconstruction, version substitution refusal and credential
  redaction. Export fixtures are explicitly MODELED cache data, not original
  received-unit proof or integrated wizard acceptance.
- The root boot collector and exporter pass scoped mypy. Independent boot
  review identified missing cleanup-counter checks in terminal classification;
  the implementation now requires zero retained handles/pins, no pending stdin
  and timely cleanup, not merely an empty error list. The pure observation join
  now reparses the actual supplied event fields/hash instead of trusting an
  unchecked dataclass instance. Boot coverage passes **31 cases in 72.34s** plus
  **11 additional cases in 26.04s** across two invocations, not one 42-case run.
  These use actual codecs with modeled transaction/executor seams, not NTFS
  ownership or actual process/device observations. The separate public test
  below covers actual original-store ownership with the injected boot observer.
- Final browser/terminal/action and legacy USB UI selection: **166 passed in
  31.57s** across eight test files. The real typed boot report is accepted by
  both renderers with its exact six fractional UTC digits, and original
  BOOT_HELD remains distinct from the report's intrinsic observed status.
- Fresh metadata callback and composed baseline service cases: **10 passed in
  251.40s** (`test_arrival_usb_phase_composed.py`). Separate legacy qualification
  and Arrival service tests: **54 passed in 211.43s**. These verify service
  acquisition/publication joins using modeled observations; they are not
  physical device acquisition tests. Black and scoped mypy pass for the owned
  UI/service files. Counts in this section are separate scoped selections,
  not a full-repository aggregate.

The boot intent records fixed local-CIM scope and a separate 30-second total
admission window. Within that window the existing owned process keeps its
10-second run plus 2-second cleanup budget. The window is created once after
durable original admission; it does not expire while waiting for manual review,
and it does not renew or share the USB permit. The collector itself commits the
request before dispatch. Reopening a pending request is held/export-only.
Post-PREPARED phases from another application launch are also held/export-only:
the current phase codec cannot silently rebind old enrollment to a new boot
request. A pre-PREPARED phase must reacquire all metadata in the current launch.

Required remaining acceptance is the nominal clean boot-to-USB public path,
including its full nine-role original, export and reopen. Original readback,
the public held path, both renderers and the scoped old-flow regressions are
verified as stated here. The later three qualification phases, camera/arm
commissioning and physical tests remain separate unfinished work.

An interim real-browser smoke also opened a fresh local rehearsal launch and
inspected Overview, Camera and Diagnostics & exports without previewing or
executing an action. It displayed the purchased static-camera/RoArm profiles,
no retained image, no connected device, the four disabled physical baseline
forms and the confirmed workspace export directory. Diagnostic events stayed
at zero. The temporary tab and its own listener were closed afterward. This
is startup/navigation coverage, not populated-baseline renderer acceptance or
physical operation. The check identified a rehearsal next-step navigation
improvement; final-source verification still follows integration.

Actual public baseline acceptance exposed a cross-layer display defect after
Begin, Prepare, Review and held Collect all completed with original retention
and completion logs: the boot producer emits six fractional UTC digits, while
the new display fixtures/validators had assumed seven. Run 02 therefore stopped
before export/reopen at the strict terminal projection check (**1 failed in
256.87s**). Its actual BOOT_HELD state, zero USB queries and originals remain
preserved under
`C:\Users\Jack\AppData\Local\Temp\rocell-usb-phase-public-20260909-02`.
The display contract was corrected to the producer's exact six-digit format;
no observation was coerced or relabeled and the original run was not replayed.
A fresh run 03 then passed the full held-path acceptance:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arrival_usb_phase_ntfs_acceptance.py -q -s -x --tb=short --basetemp=C:/Users/Jack/AppData/Local/Temp/rocell-usb-phase-public-20260909-03
```

Result: **1 passed in 280.27s**. One real NTFS original passed public Begin,
Prepare (31.312s), Review (37.188s), Collect (63.610s), full diagnostic export
with manifest verification/restore, and fresh-owner original reopening.
Completed action/result logs and duplicate-ticket no-replay behavior were
checked. The real original boot collector retained `INJECTED_CIM_EXECUTOR`
evidence as **BOOT_HELD**; zero processes, CIM executions and USB queries ran.
Prior hardware/source/metadata facts and their acquisition lineage were
explicitly modeled. Stages 5 onward stayed PENDING. The held result contains
seven roles, not a fabricated execution or complete nine-role baseline.

The preserved `acceptance.json` is under
`C:\Users\Jack\AppData\Local\Temp\rocell-usb-phase-public-20260909-03\test_actual_public_baseline_be0`.
It records original paths, full public operation IDs and these identities:

- Export manifest identity:
  `facc1a58972386956e8244d41425f185a68afd26f4bbe765d0186109db52ee2f`.
- Original host-boot evidence:
  `0cdb652148a8b48b6874dd3cba0a7723abea73410024fc5639b506d603e55477`.

This test begins from the declared-trial fixture. Root separately reran
`test_arrival_usb_trial_actual.py` on a fresh actual NTFS original after the UI
freeze: **1 passed in 173.93s**, using
`C:\Users\Jack\AppData\Local\Temp\rocell-usb-declaration-public-20260909-final`.
That test exercises public declaration, export and fresh reopening and confirms
the updated DECLARE-to-BEGIN handoff, with device/process entry points forbidden.
No passing held-path or declaration test is evidence of physical USB
qualification.

### Final-source startup and real-browser export

Both `./start-rocell-wizard.ps1 -Mode rehearsal -Check` and
`-Mode physical -Check` passed on source
`8c8db83b0855fab025e471428be25f1866ed024c1d912acbb0acb88eb92dadf1`:
READY_FOR_DIAGNOSTICS, zero operations, no physical authority, trial NOT_DECLARED
and all four baseline actions registered but disabled pending prerequisites.
Both reported the operator-confirmed workspace export parent.

A real local browser launch on that same source verified the improved Camera
next-step navigation, then previewed/executed only a hardware-free diagnostic
note and general export. The UI reported both actions SUCCEEDED and the bundle
was independently reverified from disk. Export snapshot/logs include the note,
source identity and zero physical authority. The four exported events stop at
the export's start; its own completion is a fifth event in the live append-only
log, not a falsely claimed self-contained completion record in that snapshot.
No camera, arm, USB or CIM query ran. The temporary tab and its own local
listener were closed after the check.

- Bundle:
  `software/runs/wizard-exports/wizard-20260909T095301955700Z-c2b5ef470ea54b899ba9a267821279b6`.
- Verified manifest identity:
  `8ddc62b617a5a536637bd4d17e6de6a81c7aa1cddef70dc9c1f0ea815be38f0c`.
- Literal `manifest.json` file SHA-256 (distinct from its embedded identity):
  `e12ffeab69e305687840da29a16af4e33ecd3b530dcbc1a1ea826b00fc910ec5`.
- Five files, 127,308 total bytes; no raw camera media or operational-ledger
  copies. This is general diagnostic-export UI coverage, not a browser-run
  physical baseline. No new wheel or native build was made in this increment.

The existing source-bound virtual workcell also remains healthy:
`./rocell.ps1 doctor --mode sim --json` returns PASS_WITH_HARDWARE_HOLDS,
`simulation_ready: true`, zero generated hardware commands and no hardware
access. Snapshot `a1e5d4ed21a48890bb0a70aea31c96e8afee175ad8679fe95013ba593d18604e`
still has twelve missing calibration requirements; those are not supplied by
USB metadata or software tests.

## Owned physical-node presence execution component

### Active successor: nominal baseline and retained physical absence

The exact service/journal/codec contract is recorded in
[Physical USB absence: application integration](USB_ABSENCE_PHASE_IMPLEMENTATION.md).
It now records the five implemented public actions, additive original
boot/readback/export work and their scoped tests. The first full actual-NTFS
absence acceptance failed and its original is preserved. The documented
timing/readback corrections subsequently passed fresh public run 02; this
software result does not qualify received hardware.

The preceding goal turn made progress: the public held-path acceptance,
declaration regression, real-browser export and scoped regressions completed.
The next increment keeps the original full application goal and advances three
independent seams:

1. Original-store agent: a new actual-NTFS public nominal baseline test, with
   explicitly constructed physical-shaped observations but actual service,
   original persistence and consumed-permit boundaries. All real device/process
   calls remain forbidden. Retain/export/reopen all nine roles; do not relabel
   this hardware-free test as a received-device measurement.
2. Windows agent: a new original-bound presence campaign. A server-generated
   absence phase ID, launch ID and nonce precede review; operation retains the
   complete baseline binding and fixed runtime. One existing M1 consumed permit
   reaches the existing owned runner exactly once. Actual counters and unknown
   effects are preserved; no shared policy/budget/native pin changes are planned.
3. Root: a separate pure retained physical-presence phase record, reconstructed
   from the independent baseline originals, exact operation, operator unplug
   report, fresh host-boot report and full owned presence evidence. The old v1
   endpoint-only absence/series semantics remain unchanged. The record keeps
   provenance, interval, target and cleanup failures explicit and grants no
   canonical stage pass, capture, motion or contact authority.
4. UI agent: audit the exact next service/original-journal lifecycle and define
   action/readback ownership before editing shared owners. Existing presence
   admission requires RUNTIME_REVIEWED immediately before QUERY_REQUESTED.
   Therefore collect/retain independently reviewed boot evidence before that
   final presence review/query pair. Do not relax adjacency or relabel the
   baseline-only boot intent as an absence request.

An operator report establishes only what was reported, not mechanical unplug
truth. Two absent physical-node samples establish only absence at those two
instants, not continuous absence. A pure record or campaign component is not a
completed public phase. Actual original-store admission-to-incapable-runner,
phase journal/readback/export integration, later reconnect/reboot collection
and final four-phase assessment remain required before this successor is done.

#### Successor verification and preserved nominal failures

The new presence campaign passes **177 selected tests, 1 deselected, in 28.63s**:
39 new campaign cases plus coordinator and owned-runner regressions. The actual
incapable-process case was explicitly excluded from that command. Operation,
launch, nonce, full review/permit joins, known versus unknown counters, cleanup,
source drift, cancellation and no-replay behavior are covered. The full
physical-shaped native outcomes are explicitly MODELED; this selection runs no
process/device/CIM. Black and scoped mypy pass.

Root's new absence phase plus binding and older qualification selection passes
**82 tests in 189.43s**. It covers all three native outcomes, independent original
reconstruction, exact current phase/launch/operator/nonce, wrong references,
boot/host changes, acquisition order, late cleanup, missing receipts, authority
flag refusal and rejection by the old endpoint-only phase parser. This broader
legacy selection also runs **four fixed incapable USB identity children** across
two existing tests; their native APIs, admission/metadata facts and boot reports
are modeled. No production helper, USB device, camera, actual CIM or arm ran.
The pure new-code tests themselves forbid process/device entry points. Root's
two new files are Black-clean; the production codec passes scoped mypy. A
separate read-only review found no concrete evidence-join defect.

A subsequent narrow verifier hardening explicitly requires a canonical
64-character lowercase expected SHA string. Its **7 added cases passed, 38
deselected, in 13.20s**; the prior 82-case selection predates that small change.
Black/scoped mypy remain clean. These results are separate scoped invocations,
not one combined 89-test run.

The final focused run of `test_physical_usb_presence_phase.py` passes **all 45
cases in 44.26s** on the final codec, including that verifier hardening. This
selection executes no child, hardware or actual CIM; its original acquisition
and physical-shaped observations are explicitly modeled. It supersedes the
earlier partial invocations for that new test file, not the legacy selections.

Commands, from the workspace:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_physical_usb_presence_campaign.py software/tests/unit/test_commissioning_usb_presence.py software/tests/unit/test_owned_usb_presence_runner.py -q -k 'not actual_incapable' --tb=short
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_physical_usb_presence_phase.py software/tests/unit/test_physical_usb_presence_binding.py software/tests/unit/test_physical_camera_usb_qualification.py -q -x --tb=short
```

The actual-NTFS nominal public test exposed two later integration seams that
the prior held-path acceptance could not exercise. Both runs are preserved;
neither original is resumed or relabeled as a current success:

| Fresh nominal run | Public outcome | Original evidence already retained |
| --- | --- | --- |
| 01: 1 failed, 1 passed in 308.55s | INTAKE_STORAGE_INTERRUPTED at 120.682s | Nine roles, final RETAINED event, OBSERVATIONS_RETAINED phase and SEALED_KNOWN attempt |
| 02: 1 failed, 1 passed in 356.29s | KeyError `port` during result projection at 165.399s | Nine roles, final RETAINED event, OBSERVATIONS_RETAINED phase and known full execution |

They live under
`C:\Users\Jack\AppData\Local\Temp\rocell-usb-phase-nominal-20260909-01`
and the corresponding `-02` directory. Both forbid actual processes and device
APIs. Full physical-shaped observations are modeled while actual original M1,
leases, campaign admission, five consumed-scope rechecks and journals are used.
Neither reached the final dedicated export/reopen assertions.

Run 01 proved an outer scope mismatch: COLLECT had 180s but its storage lifecycle
was truncated to 120s. The narrow correction passes the original action deadline
unchanged and allows at most 180s only for the explicit USB phase storage scope;
all default/legacy scopes keep 120s. **83 deadline/setup tests pass in 1.65s**,
including boundary, mixed-scope, Stop, expiration and exact action-deadline
forwarding. Inner boot/query/process/permit/cleanup bounds are unchanged. The
actual runner interval was 9.469s inside 23.672s remaining on the unchanged
bounded permit; the timeout occurred later, not inside hardware acquisition.

Run 02 reached the nominal service projection and found that actual hop records
use `connection_index`, not `port`. A further read-only strict-shape audit found
that descriptor VID/PID are four-character lowercase hex strings, whereas the
terminal renderer expected integers. These projections are now corrected without
changing the original producer bytes: `hub_port` comes from `connection_index`,
VID/PID remain canonical four-character lowercase hex strings in both interfaces,
and `bcd_usb` remains an integer. No aliases or numeric coercions were introduced.

The full strict producer-to-service-to-both-renderers regression and seven
existing UI/action modules pass **170 tests in 95.81s** (four new pure cases and
166 existing cases). The modeled strict OBSERVED reports exercise complete raw
descriptor traces and EX speed 2/3 with independent V2 SuperSpeed flags. Both
renderers reject malformed, numeric, boolean and uppercase VID/PID. Tests assert
that rendering preserves original bytes and grants no hardware authority.
The new test models final cache publication; it does not authenticate an actual
original store or replace the separate public acceptance. Black and scoped
mypy pass. Final scoped command:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_usb_observed_projection.py software/tests/unit/test_wizard_usb_phase_ui.py software/tests/unit/test_wizard_usb_identity_ui.py software/tests/unit/test_wizard_usb_qualification_ui.py software/tests/unit/test_wizard_actions.py software/tests/unit/test_wizard_camera_next_step_ui.py software/tests/unit/test_wizard_camera_identity_navigation.py software/tests/unit/test_arrival_usb_identity.py -q -x --disable-warnings --tb=short
```

Fresh nominal run 03 passes **2 tests in 397.09s** in its new isolated directory;
runs 01/02 remain untouched. It exercises actual public Begin/Prepare/Review/
Collect, durable completion logging, genuine original M1 admission with five
consumed-scope checks, all nine roles and eight phase events, SEALED_KNOWN
campaign retention, full dedicated export/restore, original reopening in a fresh
owner and refusal to replay. Later stages remain PENDING. The physical-shaped
boot, USB and process observations are explicitly modeled; actual process and
hardware-query counts are zero. Final phase is OBSERVATIONS_RETAINED, public
state is RETAINED_BLOCKED, and canonical stage PASS/physical authority stay false.

Prepare took 31.297s, review 37.500s and collect 162.172s inside its original
180s outer bound. The modeled runner took 9.312s within 23.734s left on the
unchanged permit; the five actual original-scope checks each took 1.828–1.859s.
This is software-path acceptance, not evidence of actual USB throughput or
production CIM/device latency. Exact command:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arrival_usb_phase_ntfs_nominal.py -q -s -x --tb=short --basetemp=C:/Users/Jack/AppData/Local/Temp/rocell-usb-phase-nominal-20260909-03
```

The receipt and full public checkpoint are preserved under that directory's
`test_actual_public_nominal_bas0` child as `nominal-acceptance.json` and
`nominal-public-checkpoint.json`. The original exported bundle is
`exports/wizard-20260909T105259751479Z-ff128cc192764e779e622726cba12668`.
Literal manifest-file SHA is
`b83d317a15f9f36746998b95c3ce19ec6f7314f18c85cfeca1053f9a385dc8bc`;
phase SHA is `ca78308cc5437b69d5bf5fefd8f534842f83297325ab648e1e477ea64e9fb000`.
The passing test does not replace the required original-store presence dispatch,
five public absence actions, reconnect/reboot phases or final series assessment.

An exact diagnostic copy, receipt, public checkpoint and independent verification
are now preserved in the operator-confirmed export parent:
`software/runs/wizard-exports/hardware-free-usb-phase-nominal-20260909-verified`.
Its README labels all physical-shaped observations as modeled and records the
original temporary source. Original and copy both pass manifest verification
and complete USB restoration (354,017 payload bytes); their seven copied files
and roster were independently compared. The verifier's internal manifest digest
is `404e35876674db18ad471b9984bfbce02b1ef097c968903968e63868eaf100d7`,
distinct from the literal file SHA above. This copy is not a replacement
original journal or received-hardware commissioning evidence.

#### Absence boot component and final inert startup

The additive `physical_usb_absence_boot.py` now implements exact original-bound
intent, distinct review and one-shot requested collection. Its **81 focused
tests pass in 61.55s**, with Black and scoped mypy clean. Actual codecs run
against explicitly modeled M1 transaction and boot observer effects; no actual
lease, process, CIM or device API runs. Coverage includes original omissions and
byte drift, changed/injected boot, unknown cleanup, partial retention, replay
refusal and Stop/source changes during report storage/readback. Currentness is
rechecked after full readback and cannot recover from an earlier failure in the
same action. The report bytes remain available even when progression is held.

Two initial test-only assertions were corrected before that final full pass:
one failed to mutate the false authority value; one expected a later intent
failure although the reused legacy baseline identifier correctly failed the
operation constructor first. No production gate was weakened for those tests.
Root independently reviewed the collector and the post-readback correction.
The production SHA is
`dbe195d7b9a0fd5c9a34fada1f47611b956cd3821a2c5e44bec10030430cd977`.
Its exact event/role/API contract and unfinished original-reader/public service
work are in [the absence integration document](USB_ABSENCE_PHASE_IMPLEMENTATION.md).

Both final inert launcher modes pass on source
`4fc084e290e384bad6a0dfd22fd6c52e834b824bee42a8ae6ff7d7fbecdfc65e`:
READY_FOR_DIAGNOSTICS, zero events/operations, NO_PHYSICAL_AUTHORITY, trial
NOT_DECLARED, all four registered baseline actions disabled until their original
prerequisites, and the confirmed workspace export parent. No browser/device was
opened by these checks; no wheel was rebuilt. Exact commands:

```powershell
.\start-rocell-wizard.ps1 -Check
.\start-rocell-wizard.ps1 -Mode physical -Check
```

#### Earlier measured performance follow-up

Read-only audit of successful nominal03 separates original storage from modeled
acquisition: refresh plus full readback takes 28.43s after boot, 28.56s after the
USB request and 41.51s after final retention, totaling 98.51s of 162.17s. Actual
device/CIM latency was not measured. Do not remove these freshness boundaries
or extend the inner permits to hide the storage cost.

Evaluate these bounded optimizations in order, with negative fault tests and a
new complete public acceptance after changes:

1. `_UsbTrialBaseline._commit` discards the verified snapshot returned by
   `commit_stage_state` and immediately snapshots again. Reuse that return only
   within the same existing transaction; retain precommit and exit checks.
2. Batch permit/result/facts/evidence reads in the existing descriptor dispatch
   transaction, retaining complete family, terminal, partial-state and scope
   audits. No cross-transaction cache.
3. Batch original stage-evidence reads against one transaction-local inventory.
   Currently each package read snapshots and rehashes the whole inventory,
   producing quadratic work across 33 packages. Preserve guarded per-package
   before/after checks and a fresh final head/inventory/family audit.
4. Only then consider one owner-internal refresh/readback operation at each
   unchanged boundary and local reuse of immutable parsed projection objects.

No savings are claimed yet. Never reuse authenticated facts across a mutation,
lease exit, source change, distinct action or admission boundary; preserve all
five fresh consumed-scope checks and original unknown-effect behavior.

The independent preparation/runner/evidence lane is now implemented and frozen
for this increment. It preserves the fixed native artifacts and existing
presence policy. Preparation derives the exact target/request from the full
phase binding and consumed-domain permit; caller-supplied expected hashes do
not replace those originals. The runner uses the shared one-process Windows
owner and five source/scope rechecks, with a separate fixed incapable executable
for tests. There is no generic production-enable flag or arbitrary command.

Final scoped command:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_owned_usb_presence_runner.py software/tests/unit/test_usb_presence_registration.py software/tests/unit/test_usb_presence_review.py -q -s --tb=short
```

Result: **239 passed in 26.95s** (49 new preparation/runner/evidence cases,
48 runtime cases and 142 review cases). Black passes five owned files; mypy
passes three source files. This single final run supersedes earlier overlapping
selections. One case executes the fixed incapable child in a real Windows Job:
ABSENT with four explicitly modeled list calls, zero device handles/writes/
frames, one observed process, five scope checks and measured clean cleanup.
Its source/admission facts are modeled; it is not genuine M1 admission or a
physical presence observation. No production helper or received device ran.

Failure retention preserves the accepted READY bytes independently from later
stdout. Changed or overflowing output keeps its actual bounded prefix, with
unknown tail length/hash and unknown unreported native counts. Actual run and
cleanup cutoffs and measured cleanup intervals are retained. The unchanged
128-KiB evidence limit has a conservative closed-schema envelope of **130,646
bytes**, including the 24-KiB preparation cap and all bounded failure records;
the measured full-cap test is 120,218 bytes. No subject is silently clipped.

At that component checkpoint, original absence intent/review/boot, campaign
admission, phase readback, public collection and full export were still missing.
The current [absence integration record](USB_ABSENCE_PHASE_IMPLEMENTATION.md)
tracks their implementation and actual-storage acceptance separately. Neither
checkpoint finishes the four-phase USB trial or releases camera capture, arm
power, motion or contact.

## Next bounded successor: AFTER_RECONNECT

Absence acceptance is complete. This checklist is expanded by the
[typed successor work order](USB_AFTER_RECONNECT_IMPLEMENTATION.md). The first
typed/preparation components do not yet constitute a wired original successor.
Retain the same hardware, policy limits and original no-replay constraints.

1. Reuse `usb_identity_phase_operation(phase="AFTER_RECONNECT", ...)`, its
   context verifier, `PhysicalUsbIdentityDispatchOwner`, M1 and the owned
   descriptor runner. Give the new phase an exact genuine absence predecessor,
   fresh selection/review and deterministic new request key. Do not change the
   effect policy to make a fixture pass.
2. Add a versioned typed predecessor/series join. The old
   `UsbQualificationPhase` predecessor is not the genuine
   `UsbPresenceQualificationPhase`; historical v1 series semantics must stay
   unchanged. Reconstruct the complete physical absence and its independent
   sources rather than manufacturing an endpoint-only predecessor.
3. Define an additive original suffix over authenticated v11. Reuse the nine
   baseline role categories and add an explicit operator reconnect report.
   Propose the exact legal transitions and role caps before implementation.
   Start from the absence BLOCKED state; preserve partial, held and uncertain
   records. Extend the descriptor-attempt reader by exactly one joined successor,
   retaining the entire sibling-domain ledger audit.
4. Reuse the acquisition-ledger and Begin/Prepare/Review/Collect pattern, not
   BASELINE-only preparation/boot schemas. Begin must precede all three fresh,
   successfully logged metadata acquisitions. Require a fresh owned
   SAME_HOST_SAME_BOOT result before the descriptor query. Add the Setup scope,
   existing-owner routing and strict compact UI projection; keep older subjects
   historical.
5. Add explicit successor diagnostics/export versions for all roles, original
   events, campaign results and partial attempts. Measure maximum complete
   histories against existing limits before considering any limit change.

Acceptance must refuse endpoint-only/PRESENT/HELD or wrong-unit predecessors,
changed originals, old-launch or pre-Begin metadata, missing completion logs and
reused tickets. Test partial writes, Stop, restart, lost publication and unknown
counts without replay. Exercise the real descriptor runner's original lifetime,
five-second admission and cleanup cutoffs using truthful modeled timing. Verify
the full public action/log/export/restore/fresh-reopen path with stage 5 onward
still PENDING. AFTER_REBOOT and independent final review remain required; a new
application launch is not a host reboot.
