# Complete camera-identity review: implementation work order

Status: pure components, the original v14 Session reader, file-only Setup/USB
assessment and review actions, both UI projections/controls, and complete v7
diagnostic export/restore are installed. Composed service/UI validation and the
full fresh public v14 acceptance pass. Separate stage-5 entry is now implemented
through Setup/UI/export and passes modeled composition; its fresh public NTFS
entry/reopen acceptance remains unfinished.
This is identity review, not camera capture or an operational robot release.
Read the [application completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md)
and [AFTER_REBOOT work order](USB_AFTER_REBOOT_IMPLEMENTATION.md).

Successor status: the [entry/cleanup checkpoint](CAMERA_ENTRY_CLEANUP_CHECKPOINT.md)
preserves the first fresh NTFS entry failure (operator-label mismatch), its fix
and passing modeled public test. Full NTFS run 02 then failed at camera entry's
pending-stage storage boundary. The [entry storage fix](CAMERA_ENTRY_STORAGE_CHECKPOINT.md)
and focused real-storage tests do not change or replay the accepted v14
original documented below.

## Current checkpoint — 2026-09-09

### Full fresh public acceptance passed

`complete-public-ntfs-20260909-01`: **1 passed in 2,090.53 s**. This constructs
the complete original four-phase chain, then exercises public ASSESS/REVIEW,
wrong-reviewer rejection before consumption, exact ticket effects, withheld
pending results, original readback, v7 export/restore and a genuinely fresh
application's public discovery/reopen. Consumed actions cannot be replayed.
The original stage-4 decision is PASS; all later stages and device permissions
remain unchanged. Hardware/process observations are modeled; storage, leases,
clocks, action routing and completion logs are real.

Acceptance held application source
`32ca99bce1754fdf3af48e4131ae677717aee423bea3eec3511665a516d8a422`
fixed. Final assessment/review took 133.375/138.735 s. The reboot query's
post-pin margin is only 0.922 s above its unchanged 20-second reserve.

The [accepted checkpoint](../runs/wizard-exports/hardware-free-usb-complete-accepted-20260909-01/README.md)
retains the 599-file original copy, JUnit result, selected test source and a
fingerprint-matched snapshot of all 361 application source inputs. The ordinary
v7 bundle in the confirmed folder independently reconstructs all 54 subjects
with unchanged original-diagnostics digest. No accepted or failed original was
rebound or replayed. This finishes the public identity-review increment, **not**
the camera/arm application goal.

### Service, UI and export increment

The existing physical USB owner now exposes two explicit actions:

1. **Assess all four original USB phases** (`physical_usb_complete_assess`).
   Reopen the exact current original under its stage lease, reconstruct the
   baseline/absence/reconnect/reboot chain, and retain series plus assessment.
   Their producer shares one reconstruction; required original rereads remain
   separate. No metadata, boot, USB or camera query runs.
2. **Review final camera-identity assessment** (`physical_usb_complete_review`).
   Confirm the displayed assessment hash and supply a procedural reviewer label
   distinct from the plan author and all four phase operators. Decision defaults
   to `REJECT`; required checkboxes start unchecked. The codec repeats the
   original-byte comparison before retaining the review and stage event.

The public action catalog routes both through the existing service, context-
bound ticket, confirmation, cancellation and completion-log path. The Setup
scope and action use the existing 180-second extended budget; no device permit,
admission deadline or cleanup reserve is enlarged. A failed/partial attempt
stays available for inspection/export and is not automatically retried.

The additive `rocell.wizard_usb_qualification.v6` projection carries compact
assessment/review summaries and three exact subject hashes. Browser and terminal
checks agree with the four historical phase records and current stage state.
Pending publication withholds **all** phase and final-review details. A retained
review file without its committed original event remains `INCOMPLETE`, never
PASS. Accepted identity leaves every subsequent stage pending and every capture,
arm, power, movement and contact permission unchanged.

Ordinary USB diagnostics/export advance to v7 only when complete-review records
or attempts exist. All three original subjects, events and partial attempts
remain reconstructible through the existing verified export system; earlier
schema rosters/caps stay closed. The confirmed parent remains
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

New implementation owners: `physical_usb_complete_service.py` (operations),
`physical_usb_complete_projection.py` (pure display checks), existing Setup/USB
and Arrival services (ownership/publication), and existing terminal/browser
renderers (inert presentation). No second device manager or logger was added.

Completed checks for this increment:

| Run | Result | Scope |
| --- | --- | --- |
| `complete-export-regression-20260909-01` | 104 passed, 3.45 s | V7 partial/full export, restore and earlier reboot/reconnect export contracts |
| `complete-service-cold-20260909-01` | 31 passed, 1 deselected, 7.92 s | File-action boundaries, partial writes, cancellation and closed inputs |
| `complete-service-composed-20260909-01` | 1 passed, 195.61 s | Actual Setup/USB operations and original codecs over modeled storage; assess/review and complete v7 restore |
| `complete-projection-cold-20260909-02` | 67 passed, 0.84 s | Both display validators and file-operation bounds |
| `complete-public-contracts-20260909-02` | 164 passed, 10.93 s | Public catalog/Arrival regressions, display parity and v7 exports |
| `complete-projection-cold-20260909-04` | 77 passed, 0.86 s | Label preflight, pending-result publication order, actual legacy baseline display shape and Python/JS parity |
| `complete-public-contracts-20260909-03` | 286 passed, 14.51 s | Expanded catalog/Arrival, new and previous export, projection and file-operation regressions |
| `complete-ui-composed-20260909-05` | 1 passed, 206.40 s | Actual Setup/USB assess → review → full restore over modeled storage, both renderers, altered-summary rejection and navigation with only GET requests |
| `complete-public-contracts-20260909-04` | 286 passed, 14.10 s | Expanded regression selection rerun after the baseline-display correction |

Current application fingerprint for the final two runs:
`32ca99bce1754fdf3af48e4131ae677717aee423bea3eec3511665a516d8a422`.
Mypy passes for eight integrated service/export/UI modules; JavaScript syntax
checks pass. The composed action test forbids all subprocess creation during
file operations; Node is used separately for the finite UI harness. UI action
availability is modeled in that test, so it does not replace the complete fresh
public ticket/storage/reopen acceptance below.

These are hardware-free checks. Modeled storage/monotonic time in the composed
test is not NTFS timing acceptance. Browser checks use the finite Node fake-DOM
harness, not a live-browser visual inspection. Initial UI attempts caught a
non-UI launch label in a newly generated fixture and a fixture-wide process ban
that also blocked Node; no received hardware was queried. An older action-list
test also omitted the already-installed reconnect/reboot actions. Failed JUnit
reports remain preserved; no original store was relabeled or reused.

Composed tests subsequently caught two integration defects: the action report
could inherit a historical execution summary and build its projection before
marking publication pending; and the new final display expected a status field
not present in the legacy baseline projection. The file-only result now clears
old query summaries and sets PENDING before projection. Both renderers derive
baseline status from its already-validated checks, preserving the old schema.
Focused tests cover both corrections; no acquisition guard was relaxed.

### Earlier original-reader checkpoint (historical source)

The prerequisite full public v13 acceptance passed in fresh run 07. Its actual
NTFS storage and explicitly modeled hardware/process boundaries remain as
recorded; that accepted store was not relabeled or replayed.

Installed components under `software/src/rocell/application`:

- `physical_usb_complete_series.py`: bounded immutable series, assessment and
  procedural review. Actual heterogeneous phase codecs reconstruct the four
  observations; the bulk retained-subject verifier reconstructs once per call,
  with no cross-call result cache.
- `physical_camera_usb_complete_constants.py`: three roles (56 KiB total),
  three events and an additive v14 view. No additional query campaign.
- `physical_camera_usb_complete_layout.py`: full-snapshot suffix membership,
  ordered partial publication, predecessor references, cross-hashes and exact
  event citations/times/states. Layout alone does not authenticate originals.
- `physical_camera_usb_complete_inputs.py`: independent role bytes/references
  and original permits from the completed v13 reader, not a saved status flag.
- `physical_camera_usb_complete_readback.py`: verifies layout, then the full
  unchanged v13 predecessor/campaign chain on the **same real snapshot**, then
  independently derives the retained series/assessment/review meaning.

The Session owner now reads the exact three labels under its existing lease,
verifies the role bytes, audits the unchanged campaign family and selects the
v14 reader. Private earlier-prefix relays account for only three later events
and exact later IDs. Public v1–v13 interfaces/caps are unchanged. Historical
query inventories exclude only these later file-only roles. Four descriptor
campaigns and one presence campaign remain the ceiling.

The private epoch extension adds exactly three references (185 total, 70 in
stage 4) and 56 KiB. The cached-view cap adds those documents plus a tested
16 KiB wrapper/event allowance, not another 1,280 KiB campaign. Existing JSON
depth/node bounds remain unchanged. This is readback support, not an action
that creates a stage review or opens hardware.

### Recorded validation

Every run below has a JUnit file under workspace `.codex-preserved`, named
`<run>-results.xml`. All physical/device facts are explicitly modeled.

| Run | Result | What it establishes |
| --- | --- | --- |
| `complete-series-semantic-draft-20260909-02` | 35 passed, 548.93 s | Heterogeneous codec semantics, bulk verifier and full input-adapter join |
| `complete-components-installed-20260909-01` | 84 passed, 9.059 s | Installed constants/layout and cold role/input rejection |
| `complete-prefix-v13-regression-20260909-01` | 1 passed, 74.54 s | Earlier full original v13 workflow and cache still verify |
| `complete-original-join-20260909-01` | 2 passed, 99.80 s | Original v14 Session join, unchanged predecessor records, full cache, later stages pending and public v13 refusal |
| `complete-prefix-cold-bounds-20260909-01` | 42 passed, 0.85 s | Bad types/counts/aliases/extensions rejected before predecessor calls; old public interfaces unchanged |
| `complete-epoch-budget-regression-20260909-01` | 107 passed, 1.79 s | Exact new quota geometry, old quota regressions, complete snapshot checks and envelope budget |
| `complete-original-boundaries-20260909-01` | 2 passed, 292.39 s | Every publication boundary, explicit review rejection and foreign predecessor role/event/campaign regressions |
| `complete-source-session-regression-20260909-01` | 76 passed, 22.56 s | Source workflow and initial-epoch Session regressions, including original-store reopen cases |

Black and mypy pass for the 13 edited original-reader/epoch/Session modules.
Historical application source fingerprint for this reader checkpoint:
`cc764f8e5c97f40e81705d6c2cd7636c45976a44636652a56677b2ee816ca44e`.
All selections above have completed. Both launcher `-Check` modes return
`READY_FOR_DIAGNOSTICS`, camera/arm `NOT_CONNECTED`, physical capture/connection
unavailable, and the confirmed workspace export directory. No hardware was
queried or moved. These checks do not establish browser rendering or a public
v14 action/export workflow. The later increments above install those joins and
record their separate full public acceptance.
The preserved draft and its earlier historical results remain under
`.codex-preserved/usb-complete-series-draft-20260909-01`; use installed modules
for further work.

### Next implementation boundary

1. Continue from the accepted original stage-5 owner/UI entry described in the
   [camera acquisition work order](CAMERA_IDENTITY_TO_ACQUISITION_WORKORDER.md).
   Its additive v15 reader is installed after the accepted run and passes
   modeled full-history tests. Setup mutation, public/UI action and full entry
   export pass the modeled public composition. Fresh public NTFS entry, both
   exports and fresh-app reopen now also pass in run 03 (2,230.09 s).
   General diagnostics include the full
   new entry but only compact USB history pointers; the existing separate USB
   export continues to own its complete original records.
   Camera capture, arm startup, movement and contact still require their own
   unfinished software joins. Never reuse the accepted original as a new-build
   qualification fixture or replay its consumed operations.

## Outcome

After the four observation phases have completed, show one understandable
camera-identity assessment: what matched, what changed, what is unknown and
which original evidence supports each result. A separate exact-subject review
may accept only the camera-identity stage. Entering camera mode/control setup
is a further explicit action; it does not open a camera or release the arm.

This fills a real software gap. The existing v1 series accepts only historical
homogeneous phase records and intentionally blocks physical USB absence. It
cannot consume the currently implemented physical-node absence, reconnect and
reboot records. Preserve its format and meaning for historical readback.

## Integration contract

1. Add an additive, strictly versioned pure series/assessment/review codec.
   Reconstruct the four original phase types with their existing verifiers.
   Use the original received submission, assessment and review, plan, independent
   role bytes/references, original permits and complete execution evidence.
   A saved phase summary or a content-shaped reference is not storage authority.
2. Reuse `original_usb_reboot_predecessor_v13` for the unchanged predecessor
   joins and `verify_usb_reboot_qualification_phase` for the final phase.
   Keep actual original-store authentication in `physical_camera_session`,
   under the existing Setup owner and current canonical storage leases.
   Do not create a second persistence/admission owner or substitute exports.
3. Produce deterministic checks with explicit held/unknown outcomes. Include
   received serial and VID/PID agreement; physical-node absence; observed USB3
   operating semantics; identity, endpoint, topology and driver continuity;
   same-host/same-boot removal/reconnect and a later different boot for reboot;
   complete accounting and cleanup; distinct actions/attempts/permits; complete
   original role/event membership and actual fresh metadata publication joins.
4. Keep the distinction between malformed or mismatched original inputs
   (reject and retain a diagnostic) and well-formed negative observations
   (retain a blocked assessment with reasons). Missing values and missing
   counts are not successes or zero effects. Test both branches.
5. Add bounded original assessment and review records through an explicit
   successor grammar. Specify exact role names, byte caps, event transitions,
   inventory accounting and admitted states before changing readers. Earlier
   version caps/defaults remain unchanged. No further device campaign is
   admitted by this file-only suffix.
6. Review must bind the exact assessment, current source/header/head/inventory,
   and the authenticated original chain. Preserve the existing distinction
   between procedural reviewer labels and authenticated human identity.
   A review acknowledgment must not override failed criteria or uncertainty.
7. Extend the existing Arrival action catalog, owner dispatch, browser cards
   and terminal projection. Viewing a card or following a next-step link must
   not execute assessment, review or stage entry. Stale tickets, Stop, source
   changes, failed publication and reopened partial work remain held.
8. Extend the existing full diagnostics/export pipeline with the exact new
   originals and failure records. Preserve all earlier schemas and partial
   attempts. Use the operator-confirmed `software/runs/wizard-exports` parent;
   no separate logging system, private dump or silent omission.

## Stage boundary and user experience

### Exact input join for the pure component

The installed module is `physical_usb_complete_series.py`, separate from
the historical `physical_camera_usb_qualification.py` v1 family. Its pure
implementation remains file/device/process-free. It uses the distinct schema
family `rocell.usb_complete_qualification_{series,assessment,review}.v1`; do not
construct a legacy series and then change its schema string or phase fields.

| Independently supplied input | Existing reconstruction boundary |
| --- | --- |
| Plan, its reference, declaration event, baseline, baseline reference and baseline sources | The six-key `original_baseline` accepted by the reboot verifier |
| Received submission, assessment and review | The exact three-key `received` mapping; `verify_usb_qualification_plan` reconstructs its binding |
| Physical absence and its reference/sources | `UsbPresenceQualificationPhase`, not historical endpoint-only `UsbQualificationPhase` |
| Reconnect and its reference/sources/original permit | `verify_usb_reboot_predecessor`; this requires completed physical absence/reconnect |
| Reboot payload/reference, five independent source payloads and references, original permit | `verify_usb_reboot_qualification_phase`; the five roles are operation, operator event, native enrollment, owned USB run and host boot |

The returned nine-input predecessor adapter is useful, but does not verify the
final reboot or authenticate the original store. Supply that final phase and
permit separately. Reconstruct even exact-type dataclass inputs from their
payloads; a forged in-memory object's type is not verification. Compare the
independent phase reference with both the payload hash/length and its actual
original role. Distinctness checks must cover the entire chain, not just the
four summary references. Preserve codec-specific canonical JSON conventions.

An incomplete/negative predecessor cannot normally reach this suffix: the
existing reboot admission already requires a completed reconnect. Do not
invent missing phase evidence to make a four-row assessment. Such cases retain
their existing phase diagnostics. A correctly reconstructed final reboot may
contain a negative or unknown observation; the new assessment must retain that
as BLOCKED. Malformed originals or mismatched references are reconstruction
errors, not an invented well-formed negative observation.

Use a bounded four-row summary containing phase, original hash, observed
status and failed check IDs. Retain raw identities and complete source bytes
only through the existing original/export mechanisms, avoiding another copy
of every native packet in the summary. Derive final checks from reconstructed
phases; caller fields must never set a passed check or qualification verdict.

### Original suffix contract (reader and action publication installed)

Three new stage-4 roles are sufficient for this file-only review. Installed
payload caps are series 16 KiB, assessment 32 KiB and review 8 KiB: **56 KiB and
three references** in total. Codec and original-epoch limits have passing
boundary tests, as recorded above. The cached workflow, export and epoch limits
must be derived separately from their actual serialized structures; do not add
an unexplained allowance or change public v1-v13 limits.

Installed labels follow
`camera-usb-complete-{series|assessment|review}-v1:usbseries-<32 lowercase hex>`.
The file-only suffix admits no fifth descriptor campaign and no additional
presence campaign. Its authenticated predecessor is the complete v13 audit,
including all sibling/global attempt records and quarantine state.

| Explicit boundary | Stage-4 state | Original references |
| --- | --- | --- |
| Assessment requested | `WAITING_OPERATOR` from the completed phase's `BLOCKED` | Exact final reboot phase |
| Series and assessment retained | `REVIEW_PENDING` | Exact new series and assessment |
| Exact review retained | `PASS` only for independently eligible and accepted originals; otherwise `BLOCKED` | Exact new series, assessment and review |

These use existing V2 transitions; there must be no same-state event. A
file-only request is still consumed: a stopped or partly retained request is
not silently resumed. Preserve request-only and each partial role prefix,
including an original write that succeeded before completion publication
failed. Reopen displays those records without reenacting the request.

The separate review obtains current source/header/head/inventory under the
existing Setup scope and re-reads all exact subjects. It cannot convert
unknown or failed observations to eligibility. Reviewer-label distinction is
procedural, not authenticated proof that two people participated. Stage-4 PASS
must mean only the reviewed camera-identity checks have been accepted; it must
not assert measured image accuracy, camera runtime release, arm connection or
physical safety. Add the exact stage-5 entry contract in a separate increment.

The existing USB owner, Setup original transaction and Arrival action catalog
remain the owners. Proposed public actions are one explicit assess command and
one exact-subject review command, with operator/reviewer labels and existing
closed confirmations only. No public form accepts a filesystem path, arbitrary
original, permit, target or success flag. Ordinary export remains available
for failed or incomplete results in the confirmed workspace folder.

Show a compact phase table and a prioritized reason list, with original hashes
available in diagnostic detail. Successful evidence retention is not a green
hardware-ready indication. The phase result `RETAINED_BLOCKED` can mean the
observation completed but final stage review remains outstanding; show both
facts instead of presenting the raw enum alone.

An eligible assessment, its independent review, and the camera-identity stage
transition must be separate facts. All diagnostic/capture/arm authority flags
remain at their existing ceilings. Stage-5 entry requires a separately reviewed
contract joining the accepted identity to current launch/device metadata and
the original configuration record. It must not install a runtime, open a device,
write controls or acquire a frame as a side effect.

Camera connection work then remains: qualify the actual native runtime,
implement physical owned dispatch, expose supported modes and control readback,
bounded preview/capture, cancellation and cleanup, image-health checks and
calibration acquisition. Arm connection/startup is a separate set of original
stages and a qualified serial/feedback composition. Neither is completed by
the camera identity review.

## Acceptance sequence

- First, pure original-codec tests with device/process access forbidden:
  complete modeled chain; each missing/changed observation; wrong predecessor;
  aliased roles; incomplete cleanup; reused request identities; forged success;
  endpoint-only absence; clock/host/boot mismatch; historical v1 compatibility.
- Then fresh real-storage tests for exact inventory/event membership, every
  partial write, failed publication, quarantine, source changes, Stop and
  original reopen without replay. Do not use old acceptance stores as fixtures.
- Verify both actual renderers and closed action forms, including stale tickets
  and inert navigation. A DOM/renderer test is not live-browser verification.
- Verify complete ordinary exports by reconstruction and byte/hash checks,
  including held and partially retained outcomes, in an explicitly assigned
  test directory.
- Finally run a complete new-launch public flow in a new preserved NTFS store,
  under frozen source. Keep current 30-second permits and lifecycle reserves.
  Record observed timing margin as well as pass/fail; do not retry until green.
  Hardware/process observations must remain explicitly modeled until actual
  received-hardware testing is separately performed.

The work order is complete only after installed code, joined public acceptance
and operator/developer documentation agree. Component tests or a visible button
alone do not satisfy this slice, and this slice does not finish the application.
