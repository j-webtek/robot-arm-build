# AFTER_REBOOT — bounded successor design notes

Status: design summary, 2026-09-09. Fresh public
[AFTER_RECONNECT run 06 passed](USB_AFTER_RECONNECT_IMPLEMENTATION.md).
The reboot reader, collector, Setup/service actions, UI and v6 exporter are now
installed with scoped hardware-free tests. Full public v13 NTFS acceptance,
final series assessment and physical camera/arm activation remain pending.
The purchased static overhead camera, RoArm-M3 Pro and placemat build remain
unchanged. Exports retain the operator-confirmed workspace destination.

This document is the design summary. The
[detailed work order](USB_AFTER_REBOOT_IMPLEMENTATION.md) specifies
the codec and original/service/UI/export contracts and records current tests.
Neither document grants execution authority or substitutes for received-unit
verification.

## Intended operator experience

1. Complete and export the original reconnect observation. Close the wizard
   normally. The app does not restart Windows or manipulate devices for the
   operator.
2. After a manual host restart, launch the wizard and explicitly discover,
   open and verify the original store. Its completed reconnect phase is history,
   not resumable work. An interrupted reconnect phase is not an eligible input.
3. Begin a **new** AFTER_REBOOT phase referencing that completed original.
   Generate new phase and operation identities in the current launch. Never
   reuse a prior live request, admission, preparation or permit.
4. Collect/review fresh generic and native camera metadata, explicitly refresh
   the same original, then prepare and separately review the exact new scope.
5. Separately collect the owned host-boot observation. Verify its relationship
   to the completed reconnect phase before admitting any descriptor query.
6. Explicitly collect the new USB descriptor result, inspect it and export.
   Locally retained evidence is not final trial acceptance or camera release.

Do not offer an automatic reboot. Closing the application, a new process ID,
an operator checkbox or a new launch ID cannot establish a host restart.

## Existing code to reuse without changing historical contracts

- `physical_usb_identity_campaign.usb_identity_phase_operation` already accepts
  AFTER_REBOOT at ordinal 3 and binds the exact predecessor hash. Its verifier
  reconstructs the full operation against independently supplied context.
- `host_boot_observation.compare_boot_observations` recognizes
  `SAME_HOST_DIFFERENT_BOOT`. The owned producer supplies bounded process and
  cleanup evidence. Reported SMBIOS UUID and OS LastBootUpTime are observations,
  not cryptographic attestation or proof of mechanical cause.
- `physical_camera_usb_qualification._observed_usb_fields` reconstructs exact
  native/descriptor observations without imposing a predecessor schema.
- Current acquisition routing, completion-log publication, independent boot
  intent, single-use campaigns, strict original readback and complete exports
  provide implementation patterns. Reuse them with explicit phase ownership;
  do not fall back to an older phase when a new publication is missing.

## New boundaries that are actually required

The existing reconnect transaction deliberately requires the same application
launch as its operator report. Keep that rule unchanged. Add a separate
AFTER_REBOOT Setup purpose accepting an authenticated, clean completed v12
predecessor from the historical launch, while binding every new action and
metadata acquisition to the current launch.

Add separate typed reboot report/preparation/boot-intent/phase subjects and an
additive original suffix/reader. The installed v13 successor follows the
eleven-role/seven-event reconnect pattern, with exact grammar and limits in
the governing work order. Preserve old v1–v12 meanings, role
hashes, reference IDs and sibling-campaign audits. Only the successor may admit
the fourth descriptor campaign; partition it by its exact operation. The
physical-node presence family remains separately accounted for.

Do not force these phases into the old `UsbQualificationSeries` v1: it accepts
only the old homogeneous `UsbQualificationPhase` type. Its assessment
intentionally remains BLOCKED for missing physical-node absence. The completed
heterogeneous baseline/physical-absence/reconnect/reboot chain needs a new
versioned series, reconstruction, assessment and separate review contract.
Do not reinterpret historical JSON or remove the old unconditional hold.

## Conservative decisions carried into the work order

- Prefer **post-reboot Begin**, as above. A pre-reboot declaration would require
  an additional cross-launch handover contract and is outside this minimal
  successor. Restarting within an unfinished new phase must remain held.
- Require the reported new boot epoch to occur **after reconnect completion**
  and **before the new phase's acquisitions**. Existing comparison only checks
  it against the previous boot observation, which can precede reconnect's USB
  query. Add the stronger phase chronology check; do not weaken the old parser.
- Require the same reported host and exact camera/serial/topology/driver
  continuity. Missing or changed observations hold the result. Driver updates
  or source changes need separately supported requalification, not an exception
  hidden inside this trial. Clock inconsistencies also remain explicit holds.
- Keep process, native, READY, permit, cleanup and export budgets unchanged.
  Compute any new original snapshot allowance from the actual retained role
  caps; do not enlarge unrelated historical limits.
- Keep final stage-4 acceptance separate from local phase retention. Camera
  capture/settings, optical calibration, arm commissioning and motion/contact
  require their own remaining gates; four retained phases do not release them.

## Minimum acceptance checklist

1. Same boot despite application restart, preserved boot epoch, changed host,
   reused report and unowned/injected boot data all hold.
2. A boot before reconnect completion, post-boot stale metadata, wrong launch,
   missing durable publication and reused phase/operation/attempt/permit IDs
   cannot produce an eligible new observation.
3. Exact original received-camera, plan, baseline, physical-node absence and
   reconnect evidence are independently reconstructed. Changed references or
   extra sibling campaigns are rejected, not ignored.
4. Boot collection and descriptor collection remain distinct actions; nothing
   runs on page load, Refresh, review, export or reopening.
5. Partial writes, consumed requests, Stop, source drift and unknown cleanup
   remain exportable and non-replayable. Missing native counts remain unknown.
6. Hardware-free tests execute the production service/runner timing contracts
   over explicitly modeled peers; fresh actual-storage acceptance verifies
   public actions, logs, complete export/restore and original reopen.
7. Later stage states and physical authority remain unchanged. A separate
   received-unit test is still needed after the software acceptance passes.

These notes came from a read-only code assessment. No hardware, host-boot
producer, USB query, original store or new phase was operated during that review.
