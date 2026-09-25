# Approved entry policy: first USB-only passive connection

Proposal ID: `ROCELL-ARM-USB-PASSIVE-ENTRY-002`
Date: 2026-09-12
Status: **USER APPROVED; IMPLEMENTATION IN PROGRESS; NO PHYSICAL RELEASE**
Parent: [arm integration plan](ARM_WIZARD_IMPLEMENTATION_PLAN.md), A2-A4.

## Why this decision is needed

The current plan requires an electrical-isolation review before a physical port
opening. It does not yet define whether a vendor-design review plus current
operator reports is sufficient, or whether independent received-unit electrical
confirmation is mandatory. Implementing a native caller without resolving that
policy would silently select the evidence standard.

The controller metadata is already correlated. The operator has confirmed the
expected RoArm-M3 Pro, secured installation, clear movement radius and, most
recently, external adapter disconnected with USB connected. These statements are
accepted as operator reports; repeating model identification is not the next step.

The [electrical design review](ARM_USB_ELECTRICAL_DESIGN_REVIEW.md) identifies
separate nominal supply paths and a reset/boot circuit. It is not a measurement
of the attached board, proof against backfeed or a no-reset guarantee.

## Proposed evidence basis

For this single engineering-test purpose only, accept the retained vendor-design
review and a fresh explicit operator USB-only setup confirmation as the basis
for attempting passive serial qualification. Record all of the following:

- `power_basis`: operator-reported external adapter disconnected;
- `electrical_basis`: vendor-design review, not measured received-unit isolation;
- `measured_isolation`: not established;
- `installed_firmware`: unknown unless separately evidenced;
- `reset_on_open`: possible; not disproved by requested DTR/RTS settings;
- `canonical_commissioning_pass`: false;
- `motion_or_contact_authority`: false.

This changes the pre-build engineering entry policy, not the canonical stage
catalog. It must be approved explicitly before implementation can treat that
evidence combination as sufficient. Approval is a risk/entry-policy decision,
not a claim that an electrical observation occurred.

## Exact proposed test

1. Use the existing wizard queue and current source binding. Freshly resolve only
   the reviewed USB identity; ambiguity, changed identity or conflicting ownership
   blocks. No first-COM selection or transport fallback.
2. Reconfirm external adapter disconnected and a secured/clear physical setup.
   Do not reconnect external power as part of this test.
3. Retain original entry evidence and exact intent before dispatch. An explicitly
   prepared and confirmed Start consumes one attempt; no unattended retry.
4. A narrowly registered supervised child opens the selected endpoint exclusively,
   requests the existing 115200/8N1, disabled RTS/DTR/flow-control settings, and
   verifies readback. Opening/configuration may affect control lines before
   readback; this remains a declared limitation.
5. Retain passive startup bytes within the existing time/byte limits. Send **zero
   outbound bytes**. No firmware/SDK initialization, query, reset toggle, purge,
   home, torque, power switching, movement or contact command.
6. Close under the existing finite supervision/cleanup rules. Retain failed and
   uncertain outcomes and original raw output. Process exit is not power-off or
   device-cleanup proof. Unexpected behavior prevents progression.
7. Export and review the result. A successful passive attempt does not unlock
   powered feedback, calibration, motion, keyboard typing or phone tapping.

## Software work still required after approval

Approval alone must not remove `WindowsNativeSerialApi`'s current hold or make a
rehearsal provider physical. Complete a separate capable registration, exact
entry verification, physical original intent/outcome storage, one-use dispatch,
native ABI/lifecycle qualification checks and public wizard acceptance first.
Keep existing historical and memory-only runtime semantics unchanged.

If this proposal is not approved, retain the existing physical hold and obtain
the independent electrical evidence required by the stricter interpretation.
Do not manufacture that evidence or substitute another serial tool.

## Decision record

- Approval: **2026-09-12**, user replied **“Yes proceed”** to the supervised,
  zero-write USB-only entry-policy proposal. This approves the vendor-design
  review plus operator-report basis, not measured electrical isolation.
- The latest operator report is USB connected with the external adapter
  disconnected. Retain that report as a report, not an independent measurement.
- Approval does not expire merely because implementation continues, but the
  physical setup, source, identity and one-use Start must be checked for the
  actual attempt. Historical approval is not a reusable dispatch token.
- No permission, registration, stage state or hardware setting changed by this
  document. No physical serial/camera access occurred during this decision audit.
