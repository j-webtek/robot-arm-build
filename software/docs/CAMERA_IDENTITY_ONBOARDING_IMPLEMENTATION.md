# Camera identity integration work order

2026-09-08. The preceding received-camera increment is verified progress,
source `616b690f10aab2eb85ac7dec1917b8d34ec5c584ec9c6eab01abae6725e114c6`.
This work continues the full camera/arm connection playbook; it does not
redefine its completion as metadata review or a passing simulated receipt.

## Intended end state and current evidence

The wizard must identify one received B0477, retain its actual OS/native
identity and driver/USB observations, correlate the received label, qualify
reconnect/reboot behavior, then admit only a separately reviewed bounded camera
campaign. Calibration and the independently gated RoArm startup/feedback path
remain part of the full objective. Physical typing/contact is later authority.

Current code already has generic Windows metadata discovery/review, a reviewed
fixed native helper, exact native endpoint inventory/identity/review, an ASCII
`PhysicalCameraSelection` bridge, and original receipt stage 3. Those metadata
tools are launch-local; their full packets are not yet original stage-4 records.
Native identity currently reports endpoint/devnode/container/location/parents.
The original v6 reader permits stage 4 WAIT with no identity evidence only.

Implement the original evidence/service/UI join and exact-devnode driver
observation next. These are prerequisites for complete identity qualification,
not substitutes for its missing unit-serial, USB and stability evidence. A
metadata-only assessment must expose those gaps and cannot authorize stage 5.
No existing effect taxonomy, physical release, source freeze or activation
manifest is silently changed by this work.

## Implemented operator interface (2026-09-08 local)

The original metadata-only increment is now implemented. The verification
ledger below distinguishes executed checks from the still-unfinished full
connection objective.

After steps 1–6 below, the Camera page offers **Submit identity metadata**.
Its form retains the exact server-owned reviewed helper and native enrollment,
plus INT-018 as an explicit observation or UNKNOWN with a reason and method.
It does not accept a raw endpoint, executable path or custom hardware command.
**Review identity metadata** is a separate action with a distinct procedural
reviewer label; those labels are not authenticated accounts. Both acknowledgement
and rejection leave this metadata-only stage BLOCKED. A subsequent collection
requires another explicit submission; four collections are supported.

**Export identity metadata** saves a complete dedicated bundle beneath the
confirmed `software/runs/wizard-exports` parent. The ordinary Export logs bundle
contains a compact coverage pointer, not a duplicate full identity history.
Exports retain original subject hashes, explicit redaction/reconstruction status,
and partial/unlogged attempts. Exporting cannot qualify a camera or restore a
live selection. Reopen/refresh verifies originals without enumerating devices.

If an operation stops or its outcome is uncertain, do not repeat Submit. Export
the retained diagnostics, then explicitly refresh/reopen the original record.
A complete unlogged commit can be discovered by readback; a partial collection
stays held. No automatic journal repair or replacement is performed.

The Windows driver v2 helper is a separately built **unqualified development
artifact**, documented in [the driver API guide](CAMERA_IDENTITY_DRIVER_METADATA_API.md).
It is not silently installed into the wizard's historical fixed helper catalog.
The existing registered v1 helper remains supported; its absent driver fields
are shown as NOT_RETAINED. A v2 receipt can retain four independently available
driver properties, but neither receipt version proves USB serial provenance,
operating speed, reconnect stability or actual hardware qualification.

### Developer ownership map

| Component | Responsibility |
| --- | --- |
| `physical_camera_identity_submission.py` | Pure bounded subjects, full producer verification, INT-018 and deterministic missing requirements |
| `physical_camera_identity_service.py` | Server-owned metadata collection, original-store writes, separate review and publication handoff |
| `physical_camera_setup_service.py::identity_transaction` | Source/Stop/original-context checks, original lease and exact post-write readback |
| `physical_camera_identity_readback.py` | Closed v7 append-only history; no device calls, fabricated prefix or stage-5 advance |
| `physical_camera_identity_export.py` | Complete readable metadata bundles, verified coverage and redaction-aware reconstruction |
| `arrival_wizard_service.py`, `wizard_actions.py` | Explicit previews/tickets, staged owners, completion log, recovery export and invalidation |
| `ui/static/app.js`, `ui/terminal.py` | Cached Camera guidance and projections; rendering never dispatches an action |

The five role bounds are metadata 896 KiB, helper 240 KiB, receipt 32 KiB,
assessment 16 KiB and review 16 KiB per collection. Original v7 adds at most
20 stage-owned references. Older original grammars, generic export limits and
native IPC limits are unchanged. Only v7's private aggregate cache allows
262,144 JSON nodes; older versions remain at 65,536 and depth stays 16.

### Executed development evidence so far

- Native/Python driver lane: 250 tests and four CTests passed, including 31
  cross-language modeled receipts. No actual OS inventory or device activation.
- Original reader: 59 new cases covered across separate runs, including actual
  isolated NTFS original readback/restart. A 321-case legacy run passed before
  final narrow edits; targeted checks cover those edits. This is not yet a
  same-source whole-regression claim.
- A genuine maximum-inventory original history (32 source, 3 static, 80 receipt,
  20 identity references; 128 generic candidates and 64 native endpoints per
  metadata snapshot) measured 2,070,751 bytes, depth 13 and 76,854 nodes.
- Four exact-role-byte-cap collections plus a distinct full failed attempt fit
  seven unchanged-limit export attachments: 6,073,795 bytes total, maximum 985
  nodes/depth 6 per part. This capacity-shaped case is not physical evidence.
  A separate actual-codec maximum-inventory case reconstructs every original
  subject byte-for-byte from a 499,386-byte attachment.
- Arrival/service composed tests cover submission, separate BLOCKED review,
  export, stale ticket/metadata, Stop, source drift, completion-log failure and
  result-retention failure. Final same-source verification remains to be added.

All positive device-shaped values in these tests are explicitly modeled. The
NTFS tests establish storage behavior, not receipt or installed acceptance.

## Official software decisions

Use four fixed, read-only Configuration Manager device-instance properties on
the exact mapped camera devnode: driver provider, service, version and INF.
Microsoft documents these properties and `CM_Get_DevNode_Property` retrieval:
[provider](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-driverprovider),
[service](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-service),
[version](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-driverversion),
[INF](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-driverinfpath).
The installed 10.0.19041.0 and 10.0.22621.0 SDK `devpkey.h` definitions agree.
These are reported installed-driver metadata, not signature/firmware approval.

Do not infer serial from an instance-ID suffix: Microsoft documents that an
[instance ID may contain serial or location information](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/instance-ids).
The current generic `DEVPKEY_Device_SerialNumber` query has no verified official
definition in the inspected SDKs; do not treat an optional value as established
USB descriptor provenance. Preserve historical bytes rather than rewriting them.

Negotiated USB behavior needs a separately designed hub-query capability.
[Operating and capable speed flags are distinct](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ns-usbioctl-_usb_node_connection_information_ex_v2_flags).
Hub handles/IOCTLs exceed the current `READ_ONLY_OS_INVENTORY` contract, whose
`device_open_allowed` is false. Neither a product label nor a SuperSpeed-capable
flag supplies actual operating speed. Define/review that capability and its
cleanup/accounting before integration; do not hide it in this metadata action.

## Operator path to connect the existing pieces

1. Complete original receipt review and explicitly request identity stage.
2. Navigate to the existing `inventory_devices` form (currently on Arm),
   acknowledge the required power-disconnected condition, and run discovery.
3. Review the exact generic camera candidate. No first-device selection.
4. Inspect/review the fixed native helper with distinct procedural labels.
5. Run native inventory, select the exact opaque endpoint, resolve identity,
   and review the exact mapping. This is not stream activation.
6. Explicitly refresh the already-owned original camera store **after** the
   final metadata review. Metadata changes withdraw Setup CURRENT; intermediate
   refreshes are unnecessary. A new launch instead discovers/reopens originals.
7. Submit the server-owned helper/enrollment/selection evidence to original
   stage 4, with the original INT-018 question and explicit observations or
   unknowns. The UI accepts no raw endpoint, packet, path or digest input.
8. Inspect deterministic checks/missing evidence and perform separate
   exact-subject review. Retain partial writes and historical subjects; never
   replay an uncertain submission or automatically enter another stage.

The Camera next-step guidance must navigate to these existing forms, including
the bounded cross-page discovery link. Navigation, rendering and polling never
prepare/execute actions, read the filesystem or query a device.

## Native compatibility and testing

Add a separate native identity receipt v2 with four independently observed or
unavailable driver strings belonging to the exact endpoint devnode. Parent
properties must never substitute for missing device properties. Preserve the
v1 decoder and original bytes; v1 has no retained driver observation. Do not
alter capture receipt v1 or increase generic IPC limits to accept the extension.

Reuse the native fake `IdentityMetadataApi` for disappearance, wrong type,
malformed UTF-16, missing/oversized property, budget, cancellation and cleanup
tests. Build a fresh diagnostic artifact without replacing historical helpers
or registrations. Only self-tests and incapable fake API tests may execute in
this development run; received-device verification remains NOT_RUN.

## Original stage owner and evidence contracts

Bind every identity collection to the original source/cell/session/header,
current collection launch/operator, reviewed received-camera trio and exact
identity-entry event. Keep the full helper registration/inspection, enrollment
snapshot and immutable selection evidence; summaries are not their replacement.
Reuse strict existing parsers/hash domains, including UTF-8 metadata hashes
versus the ASCII selection bridge. INT-018 belongs to stage 4, not the sixteen
stage-3 notebook questions. Nominal values must not fill its observations.

Use explicit append-only collection, deterministic assessment and distinct
review. Metadata completeness is a reported check, not complete B0477 identity
qualification. Missing serial provenance, USB operation or stability evidence
must remain specific blockers. The eventual full qualification path must add
those real observations and a legitimate PASS/next-stage entry; no manual PASS
override or weaker metadata-only PASS may replace it.

The original reader needs an additive closed suffix after the unique identity
entry event. Verify the real complete original journal/inventory; use a private
received-prefix seam rather than fabricate an earlier head/snapshot. Preserve
v1–v6 behavior and exact original configuration provenance. Verify every role,
label, hash, stage owner and predecessor. Keep partial retention distinct from
committed review-pending/reviewed states, with no automatic repair.

Publish only after exact original readback, exact worker-result retention and
durable Arrival completion logging. Run original mutations outside the Arrival
lock under the existing source/Stop/deadline and original-store lease checks.
New metadata/context changes invalidate current identity eligibility while
retaining original history. Reopening cannot repopulate live metadata caches or
imply that a historical endpoint is currently connected.

## Bounded storage and export design

Agree and measure the concrete wire/role budgets before extending original
inventory/cache limits. Existing enrollment and helper report maxima together
already reach 1 MiB before wrapping. Keep full subjects in separate roles,
avoid duplicating full packets inside receipts, and leave source/static/received
and generic export limits unchanged. Add only explicit stage-owned bounds.

Use a dedicated complete identity metadata export with visible history coverage,
hashes, redaction notices and manifest verification. The normal export carries
a compact coverage/pointer record, not another unbounded nested copy. Fail
before original writes when the agreed representation cannot fit; never drop
an evidence role silently. Historical/source-changed/log-failed export remains
available without republishing acceptance. Default parent remains
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

## Parallel ownership and completion evidence

- Native agent: exact-devnode driver receipt, Python wire compatibility,
  native fake tests and a fresh build artifact. No OS/device enumeration.
- Original-store agent: agreed stage-4 grammar/readback and minimal prefix,
  epoch/inventory changes, real file-store restart and malformed-chain tests.
- UI agent: Arrival actions/context/publication, cross-page next-step navigation,
  browser/terminal parity and real-service composed tests.
- Root: wire agreement, pure original identity assessment/observation contracts,
  application service/export, failure integration, documentation and final
  startup/package/regression checks.

Required checks include actual existing metadata flow while Setup is held,
one refresh retaining that selection, stale-context refusal, exact-device versus
parent driver distinction, incomplete identity BLOCKED, distinct review,
partial original retention, lost completion, Stop/source drift, unchanged older
readers, complete export after rotating results, and restart without provider
calls. Use explicitly modeled hardware facts for positive software cases.
Record executed counts/artifacts only after they exist.

## Follow-on work required for the full goal

This increment does not complete camera identity qualification. Next add the
reviewed USB/serial observation capability, actual received-label correlation
and multi-observation reconnect/reboot qualification, then join original
identity to existing native runtime/acquisition admission. Continue installed
optical calibration, RoArm exact identity/startup/feedback, later noncontact
tests, task rehearsals and received-hardware acceptance from the full playbook.
Keep the overall goal active until that end state is implemented and verified.

### Next complete slice: USB observation and identity qualification

1. Define a purpose-specific bounded USB descriptor-query capability. Hub
   handles and IOCTLs do not fit the existing no-device-open metadata effect.
   Keep reset, port cycling, configuration/vendor requests, camera activation
   and serial access forbidden. Account for attempts, bytes, cancellation and
   confirmed close outcomes; uncertain cleanup prevents automatic retry.
2. Start from the exact reviewed endpoint/devnode, resolve its physical USB
   ancestor and hub port, and authenticate that join. Microsoft documents
   [the device driver key](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-driver)
   and [the corresponding hub-port query](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ni-usbioctl-ioctl_usb_get_node_connection_driverkey_name).
   Keep endpoint-driver observations distinct from ancestor topology evidence.
3. Obtain descriptor-backed serial, retaining the descriptor, `iSerialNumber`,
   supported language ID, returned string bytes and decode outcome. A zero
   index, malformed response, ambiguity or disappearance stays unavailable.
   [Descriptor requests](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ns-usbioctl-_usb_descriptor_request)
   perform a device-to-host control read; they are not registry-only inspection.
4. Version the speed contract before constructing full identity. Retain actual
   operating categories separately from capable categories. The present
   `Usb3Topology.negotiated_speed_mbps` field cannot truthfully be populated
   from an EX_V2 "or higher" flag. Do not invent an exact numerical link rate.
5. Build and explicitly inspect/review a separate purpose-specific helper
   entry. Preserve old binaries, manifests and v1/v2 decoders; old metadata
   approval does not grant USB hub-query authority or camera capture release.
6. Add original baseline, witnessed reconnect and actual host-boot observation
   records. A new application launch is not a reboot. Join the descriptor
   serial to original receipt-label evidence, exact driver/endpoint/topology
   and operating USB3 proof. Only a complete separately reviewed series can
   become identity PASS-eligible; the current metadata-only history remains
   unchanged and cannot be manually promoted.
7. Test the actual native fake API → Python parser → service → original-store
   chain without hardware: composite devices, duplicate paths, malformed and
   missing serial, language variants, speed capability versus operation,
   before/after drift, timeout/close failure, changed-unit reconnect, actual
   boot-evidence distinction and restart without replay. Model positive facts
   explicitly, then keep received-hardware validation separately NOT_RUN.

### Frozen-source integration verification

Current source:
`f1778142255277bca4adf1eae4f3f015d1813d9ab26cc9b1f9a9c6a6c359700e`.

- Root service lane: 15 tests passed in 164.73 s.
- Final Arrival/browser/terminal composed lane: 12 tests passed in 180.69 s.
- Terminal lane: 7 identity + 13 received tests passed in 103.45 s;
  another 42 legacy terminal tests passed. Test selections may overlap.
- Actual isolated NTFS service test: 1 passed in 119.21 s. Submit took
  28.594 s, review 25.671 s and export 0.156 s, each within the existing
  120-second action limit. Real original transactions, complete export
  reconstruction and fresh-owner restart passed; physical facts, source hash
  and outer completion logging were explicitly modeled.
- Eleven joined application/UI Python files pass mypy and Black; JavaScript
  syntax check passes. Both launcher `-Check` modes report
  READY_FOR_DIAGNOSTICS, the confirmed workspace export parent, identity
  NOT_STARTED and native release false.
- The live local browser Camera page and new identity panel were visually
  inspected. State revision remained zero; no action was prepared/executed.
  The temporary browser tab and server were closed.

The offline wheel at
`software/runs/camera-identity-wheel-d28a6a5e156944a89f23c221b57af842/rocell-0.1.0-py3-none-any.whl`
contains 284 code/UI entries byte-identical to the workspace. SHA-256:
`0608b330c7bf82dfe2b4ea2d70bf84456032688583df53b2be82fe5865d5f6aa`.
No dependency downloads, runtime registration or installation was performed.

The actual file-only `wizard_workspace_sources_smoke.py` succeeded on that
source: initialize, real prerequisites/source assessment, explicit BLOCKED
review, nine-note result rotation, export, shutdown, discover/reopen and export.
Original source stayed BLOCKED and every later physical stage stayed PENDING;
no physical isolation statement or device observation was invented.

- Original launch: `wizard-9daec0a3de5548b9bb38560e5650a74b`.
- Reopened launch: `wizard-893c4bb0203c45e682a71beade7d1a6d`.
- First verified export, 373,345 bytes:
  `software/runs/wizard-exports/wizard-20260909T024440812935Z-92765bfbd5984f2192c91f3d83029fb8`.
- Reopened verified export, 478,721 bytes:
  `software/runs/wizard-exports/wizard-20260909T024450302580Z-5196aa683ed747ae95cfc9975e451fb1`.
- Preserved original configuration SHA-256:
  `958f2093391cfb3c9e84a68769904c3ce9cbf7fd54847743f90ae2b6087cd868`.
- Preserved original source review SHA-256:
  `deb298cc64648603e54b199b3945d2ed8d8158d94b5ef52764adf009ab2159aa`.

Broader same-source compatibility runs are still being reconciled. One initial
UI run passed 1,144 tests before a stale actual-file expectation failed: the
historical capture build correctly reports source gaps after the identity
metadata C++/header changes. Historical artifacts remain pinned and held; the
tests were corrected to assert the exact changed-file set, not relaxed to
accept arbitrary drift. Both runtime-inspection/UI files then passed 112 tests
in 8.85 s. They also verify all 27 historical files remain unchanged before and
after inspection. The original/source selection completed with 820 tests
passed in 1550.19 s. The separate UI continuation passed 1,020 tests before
an outdated partial cache fixture failed. That test now uses the production
verifier's full historical workflow shape; production validation is unchanged.
The affected module passed 21 tests in 2.55 s, focused reader compatibility
passed 74 tests (2 deselected) in 15.21 s, and the v7 cache-bound test passed.
These separate selections are not a whole-broader-suite PASS claim, and their
counts must not be added as unique coverage. Both original runs are terminal.

The next detailed work order is `CAMERA_USB_IDENTITY_IMPLEMENTATION.md`. It
records the bounded USB-query policy decision, native wire, host-boot evidence,
operator sequence, historical-source handling and implementation/test lanes.
