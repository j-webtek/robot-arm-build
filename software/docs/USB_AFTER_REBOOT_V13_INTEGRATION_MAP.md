# AFTER_REBOOT v13 integration map

Status: **application/storage/UI extension installed with scoped tests**,
2026-09-09. Full public NTFS v13 acceptance and final series assessment remain
pending. This map preserves the audited integration contracts; use the governing
work order's current checkpoint for executed tests and exact limitations.
Documentation does not authorize a device operation or qualify hardware.

The governing contract is [the reboot work order](USB_AFTER_REBOOT_IMPLEMENTATION.md).
The preparation/data adapter, original boot collector, full readback, Setup/owner
joins, five registered actions and both cached interfaces are installed. Do not
duplicate their codecs in the service. Earlier AFTER_RECONNECT public acceptance
does not substitute for the still-pending public AFTER_REBOOT acceptance.

## Operator path and closed action contract

1. Finish and explicitly export a clean original AFTER_RECONNECT. Close the
   wizard, manually restart Windows, then explicitly reopen and verify the same
   original under the **same source fingerprint** in a new application launch.
2. Begin a new AFTER_REBOOT interval. An operator report is not reboot evidence.
3. Use the existing generic inventory/review, helper inspection/review if needed,
   and native inventory/identity/review forms. All three acquisitions must have
   new IDs and genuine completion-log publications after Begin and the report.
4. Explicitly Refresh the same original, preserving that new phase/ledger, then
   Prepare and independently Review its exact target, policy, runtime and boot
   intent. Refresh does not rebind or renew an attempted interval.
5. Collect host boot once. Only a clean physical-owned same-host/different-boot
   result satisfying `reconnect finish < new boot epoch <= Begin` enables the
   separate USB query. Boot collection never runs USB automatically.
6. Collect USB once; retain all original results/partial writes, inspect and
   export. Local `REBOOT_OBSERVATIONS_RETAINED` is not final trial acceptance.

Installed closed IDs and forms:

| Action | Closed fields | Outer timeout |
| --- | --- | ---: |
| `physical_usb_reboot_begin` | `operator_id`, `file_only`, `confirm_host_restarted` | 120 s |
| `physical_usb_reboot_prepare` | `operator_id`, `file_only` | 180 s |
| `physical_usb_reboot_review` | `reviewer_id`, `confirm_policy_review`, `confirm_runtime_review`, `confirm_exact_target`, `confirm_boot_metadata` | 120 s |
| `physical_usb_reboot_boot_collect` | `confirm_host_boot`, `confirm_no_capture_or_arm` | 180 s |
| `physical_usb_reboot_collect` | `confirm_usb_query`, `confirm_no_capture_or_arm` | 180 s |

Use existing actor limits and false checkbox defaults. No caller target, argv,
host, operation ID, original reference or permit fields. Keep the existing USB
worker and all inner native/READY/permit/cleanup bounds. Stop remains software
cancellation, not a robot E-stop. No automatic reboot or acquisition on GET.

## 1. Original storage and campaign family

All source paths below are under `software/src/rocell/application/` unless stated.

| Extension site | Required bounded change |
| --- | --- |
| New `physical_camera_usb_reboot_constants.py` | Closed v13 schema, eleven ordered roles/1,224 KiB, seven events and the corresponding eleven states. Labels/events follow the work order. Reuse neither reconnect labels nor a generic unknown-role allowance. |
| New `physical_camera_usb_reboot_readback.py` | Verify the real full snapshot and exact new packages; reconstruct the complete v12 prefix and new phase. Retain request-only, each partial role prefix, boot held/uncertain, original-campaign-only and final states without replay. |
| `physical_camera_usb_reconnect_readback.py:59`, `verify_usb_reconnect_workflow` | Currently consumes every event from reconnect start to the end and closes inventory over old+reconnect IDs. Keep that public v12 behavior. Add a private bounded v12-prefix route for the v13 owner with separately authenticated reboot IDs and an exact event boundary. |
| `physical_camera_usb_absence_readback.py:60`, `read_original_usb_absence_campaigns` | Current private reconnect option permits at most three identity campaigns and one presence campaign. Add an explicit v13-only option for at most four identity campaigns; preserve the complete global/sibling ledger audit, selected-session filtering, final attempt-head/lease checks and one presence campaign. |
| New v13 campaign partition | Decode every original permit. Partition at most one new campaign by the exact separately retained reboot operation SHA; send all remaining identity campaigns to the v12 verifier (at most three). Never discard an unmatched or second same-operation attempt. Four is the maximum including an optional old v8 campaign, not a requirement to create four. |
| `physical_camera_session.py`, `PhysicalCameraOnboardingSession._read_original`, `_verify_original_source_roles` | Recognize the new event/label namespace; inspect exact role caps, media, source/launch and content-bound refs; choose v13 before v12; pass all family originals. Add the new schema to the strict private cached-copy path, not worker JSON decoding. |

The private-prefix propagation is a real integration dependency, not merely one
new reader import. Today `_verify_usb_absence_prefix` accepts only eleven
reconnect exclusions and seven later events. The phase, trial, legacy USB,
identity, received, static and source-qualification prefix helpers also have
explicit reconnect flags, exclusion sets and tail ceilings. Their files are:

- `physical_camera_usb_absence_readback.py`
- `physical_camera_usb_phase_readback.py`
- `physical_camera_usb_trial_readback.py`
- `physical_camera_usb_readback.py`
- `physical_camera_identity_readback.py`
- `physical_received_camera_readback.py`
- `physical_static_contract_readback.py`
- `physical_source_qualification_readback.py`

Carry a separately closed reboot extension through these private paths, adding
only its exact eleven IDs and seven events, with disjointness and union-equals-
actual-inventory checks. Do not disguise reboot IDs as reconnect IDs, slice an
invented earlier snapshot, rewrite a committed head or loosen public v1-v12
defaults. Historical permit-inventory reconstruction must exclude both exact
later-suffix IDs and the historical attempt's own transferred result roles.

The new reader must compare the reboot phase's two `predecessor_records` to the
actual existing absence/reconnect phase references, and its five `records` to
the separate new operation/report/enrollment/execution/boot records. The
independently retained reconnect permit and new permit are mandatory inputs;
their hashes inside worker evidence are not substitutes for either original.

## 2. Epochs, source and new-launch eligibility

`physical_configuration_epochs.py:1024` currently exposes the private v12
verifier. Add a private v13 counterpart, preserving the original epoch payload
and all public defaults. The actual cap arithmetic is:

- total original references: 171 + 11 = **182**;
- stage-4 references: 56 + 11 = **67**;
- stage-4 payload allowance: existing 7,740 KiB + 1,224 KiB = **8,964 KiB**.

These are private full-audit restoration ceilings, not a new epoch-creation
allowance. `physical_camera_session.py:1524` needs the matching event-gated
readback limit. Its new byte-cache ceiling should follow the existing role-plus-
bounded-campaign accounting (`MAX_USB_RECONNECT_WORKFLOW_BYTES:167`), without
raising depth 16, 262,144 private history nodes or unrelated worker limits by
default. Exercise realistic and maximal supported shapes before any further
capacity decision.

`wizard_diagnostic_coordinator.source_fingerprint:247` already includes every
new `.py`/UI/config file. No source roster exemption or migration is appropriate.
Build the entire acceptance prefix under the final reboot-enabled source, then
model the next launch/boot. A preserved current v12 store from an older build
cannot be turned current by rewriting its binding. Documentation itself is not
part of that fingerprint.

Add `PhysicalCameraSetupService.usb_reboot_transaction`, beside the existing
`usb_reconnect_transaction:711`. The old scope deliberately denies final or
earlier-launch reconnect work (`:1001`); keep it unchanged. The new scope needs:

- **Begin:** authenticated complete v12, original `RETAINED_BLOCKED`, locally
  complete `RECONNECT_OBSERVATIONS_RETAINED`, clean `SEALED_KNOWN`, no quarantine,
  exact transferred execution and independently decoded original permit;
- **Later actions:** authentic v13 at only the relevant unused boundary,
  operator-report launch equal to this owner, no prior original campaign/event;
- current source/header/head/full inventory and original epoch authentication;
  unchanged 180-second maximum original outer deadline, no renewal;
- original readback before pending publication, durable outer completion before
  CURRENT; partial/error paths retain known committed events and bytes.

**Adapter trap:** `original_usb_reconnect_predecessor_v12` in
`physical_camera_usb_reconnect.py:106` returns the absence predecessor. It is
not a verifier of complete reconnect. A new reboot predecessor adapter must
assemble the received trio, baseline, absence, reconnect sources/references and
reconnect permit from the already authenticated full workflow, then call the
installed `verify_usb_reboot_predecessor`.

## 3. Existing owner and Arrival

Add one private `physical_usb_reboot_service.py` composition helper inside
`PhysicalUsbIdentityService`; do not add an independent wizard or dispatcher.

- Owner construction/adopt/observe/invalidate, `context_sha256`, `fields`,
  `blocked_reason`, `perform`, `_result`, publication and diagnostics must all
  include the new helper. Route reboot actions before the current blanket
  reconnect-successor hold (`physical_usb_identity_service.py:675`). Once a
  reboot phase or attempt exists, all prior phase mutations remain denied.
- `acquisition_started:291` / `acquisition_published:303` currently choose only
  reconnect or baseline. Prioritize the explicit active reboot interval, seal
  its generation/phase/source/launch, and never fall back to an older helper for
  missing, malformed or stale reboot tokens. Arrival's durable-completion
  publication callback remains the only ledger-row publication path.
- Reuse the reconnect retain/commit/refresh/dispatch sequence, including immediate
  caching of successful commit return values. Boot gets its separate original
  collector and admission. Only an authenticated clean boot terminal allows a
  fresh QUERY_REQUESTED and separately consumed descriptor permit.
- Extend `_facts_provider:846` explicitly for the new preparation/refs/policy.
  Require exact leased snapshot head **and full inventory** and v13 epochs.
  Before constructing a new dispatcher, require fresh QUERY_REQUESTED with no
  pre-existing original campaign/event; use the deterministic phase request key
  for durable under-lease deduplication. Do not mistake the current operation's
  own subsequently reserved attempt for a replay at consumed-scope checks.
  Inventory SHA must use
  `physical_onboarding_durability.canonical_sha256` including LF (`:977`), not
  the nearby USB wire canonical serializer. Preserve every fresh read boundary.
- Register the five real forms in `wizard_actions.py`; keep them absent until
  the service and original path agree. Arrival reviewer validation (`:1698`),
  effect previews (`:1975`), running/cancel copy (`:2680`) and strict result
  validation (`:4134`) need exact reboot cases. No broader legacy child validator.
- Reuse descriptor action result semantics: file/boot actions have no USB query,
  file actions no execution; boot has the exact original-state summary; USB
  Collect has query-attempted and literal retained descriptor counts. Missing
  native accounting stays null/NOT_REPORTED. A missing execution is not zero.

## 4. Cached UI, history and assigned-folder export

Installed cached qualification **v5** adds only `reboot` to v4;
diagnostics/export **v6** adds `qualification_reboot` and
`qualification_reboot_attempt` to v5. The service and both renderers use these
closed fields. Preserve exact old
versions when no new phase/attempt exists.

The current reconnect projection (`physical_usb_reconnect_service.py:645`)
marks the entire outer publication historical after launch change. Reboot must
derive its own current-entry eligibility from freshly verified Setup while
presenting reconnect as history. Do not just wrap this result and inherit its
historical top-level gate; do not make reconnect current again. Cached v5
validation must permit a historical predecessor alongside a current new phase.

Update `ui/static/app.js` `usbQualificationProjection:1972`, the phase-state
render loops, and `cameraNextStep:2946`; mirror in `ui/terminal.py` qualification
validation/display. Route active reboot before reconnect/baseline, retain the
narrow same-launch unattempted Refresh hint, show all actual boot blockers,
provider-reported UTC/host relation and literal descriptor values, and make
AFTER_REBOOT display its actual state rather than NOT ACQUIRED. Never imply
that four rows equal qualification PASS or capture/settings/arm permission.

Narrow historical compatibility correction implemented: the explicit rosters
in `physical_source_qualification_service.py`,
`physical_static_camera_onboarding_service.py`,
`physical_received_camera_service.py`, and
`physical_camera_identity_service.py` now include v12 and future v13 in the
existing historical-display/identity-replay-denial handling only. This does
not implement or accept a v13 reader, alter other mutation rules, or activate
any new action. `test_usb_reboot_predecessor_history.py` passed five focused
tests (32.75 seconds): real owner/codec fixtures with explicitly modeled
audited-successor labels preserve full original/export payloads and reference
hashes, deny predecessor mutations, and leave current/unknown-version behavior
unchanged. All four source files passed scoped mypy. No hardware or production
helper was run in that earlier checkpoint. The current v13 integration tests
are listed separately in the governing work order.

Extend `physical_usb_identity_export.py` version map, `_input:149`, a new exact
reboot-record validator beside `_reconnect_input:328`, and coverage summaries.
Keep original cached roles/events/campaigns plus full partial attempts/known
commit returns. Preserve the existing general export pointer and explicit
`physical_usb_identity_export` action with the operator-confirmed export parent;
no new export screen or device operation is needed. Current input caps are
6 MiB/200,000 nodes/depth 40, separate from original-history cache caps; output
attachment/manifest caps are also independent. Test complete new diagnostics
and partial/unknown cases without truncating originals or silently raising caps.

## Minimal ownership and verification order

1. **Pure preparation/boot lanes:** freeze the new exact APIs with the installed
   phase codec. Keep metadata-log freshness and real boot admission as distinct
   proofs. No UI controls yet.
2. **Original-reader/Setup lane:** own constants, v13 reader, explicit private
   prefix propagation, epoch/cache limits and new scope/predecessor adapter.
   Test v12 historical eligibility, optional v8 + fourth campaign, fifth/extra
   campaigns, unchanged head plus extra reference, all eleven write boundaries,
   same-launch rules and fresh reopen. Keep older public reader tests.
3. **Application/UI/export lanes:** connect the five service-backed actions,
   exact publication routing/results and v5/v6 views/exports together. First run
   composed Begin/fresh publications/Refresh/Prepare/Review/Boot/Collect through
   actual codecs, including transfer/final role verification. Then use a fresh
   isolated public original-store acceptance, never replay preserved runs.

Suggested focused new tests: `test_usb_reboot_storage_scope.py`,
`test_physical_camera_usb_reboot_readback.py`,
`test_usb_reboot_family_audit_boundary.py`, `test_usb_reboot_metadata_routing.py`,
`test_usb_reboot_inventory_boundary.py`, `test_usb_reboot_service_composed.py`,
`test_arrival_usb_reboot_results.py`, `test_wizard_usb_reboot_ui.py`,
`test_usb_reboot_export.py`, then `test_arrival_usb_reboot_ntfs_acceptance.py`.
Reuse the reconnect counterparts and actual in-memory metadata owners rather
than hand-authored successful projections. Include Stop, lost completion log,
same boot/new launch, reboot during unfinished work, partial/no-native-result,
explicit Refresh, preserved original hashes, export round-trip and no fallback.

Final heterogeneous series reconstruction/assessment and independent review
remain a separate next contract. The installed v1 homogeneous series retains
its physical-absence hold. No final stage-4 PASS or stage-5/camera/arm release is
part of this v13 local phase integration.
