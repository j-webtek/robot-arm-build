# M1 qualified zero-hardware onboarding runtime

**Implementation status:** application runtime and CLI implemented; zero
physical authority; effect-capable coordinator and physical providers not
implemented

**2026-09-07 rehearsal extension:** a narrow lease-owning transaction boundary
and immutable `REHEARSAL` header mode now support the isolated, incapable
guided workflow. Physical-header defaults/hashes remain unchanged; physical
dispatch is still unavailable. See the [rehearsal developer handoff](M1_REHEARSAL_TRANSACTIONS.md)
for its public API, durable reservation/result records and remaining gates.

This document explains the first executable part of the reviewed physical
onboarding v2 roadmap. M1 gives the eventual arrival wizard a qualified,
crash-aware place to store cell-global safety state and v2 diagnostic sessions.
It is deliberately not a camera or robot runtime.

The public M1 facade can initialize storage, create a blank v2 session, verify
existing state, and perform conservative evidence-only startup recovery. It
does not expose a method to enumerate or open a camera, open a serial port,
apply robot power, send feedback or motion commands, descend, press a key, or
tap a phone. Every report keeps `runtime_activation: false` and every physical
authority false.

## What is implemented

The M1 application layer now joins these independently verified components:

- a Windows/NTFS publication adapter with bounded regular-file reads,
  same-volume write-through publication, flushed file contents, atomic head
  replacement, and strict path/link checks;
- a fresh on-volume startup self-test plus an immutable qualification anchor;
- ordered OS leases in the required
  `CELL -> SESSION -> CAMERA -> ARM_CONTROLLER` order, with owner metadata,
  challenge rechecks, and explicit stale-owner reconciliation records;
- a cell-global append-only attempt/effect ledger;
- a separate cell-global append-only quarantine ledger;
- source-, cell-, stage-plan-, and durability-bound v2 session headers;
- event-first/head-second append semantics, content-addressed evidence, bounded
  enumeration, and conservative detection of uncommitted suffixes; and
- one M1 facade that owns the leases around its mutations and returns a single
  cross-store verification challenge.

The M1 facade currently exposes only storage-safe operations. The lower-level
attempt and quarantine structures are foundations for M2; they are not an
operator API and must not be called directly to manufacture an effect record.

## Safe command workflow

Run from the workspace root in Windows PowerShell. First establish the checked-in
environment and run the zero-I/O gates:

```powershell
Set-Location C:\Users\Jack\Desktop\robot-arm-build
.\setup-rocell.ps1 -Profile hardware
.\rocell.ps1 host-doctor --profile hardware --require-pass --json
.\rocell.ps1 physical-onboard verify-foundation --json
.\rocell.ps1 rehearse-physical-connections --require-expected --json
```

The M1 CLI surface is:

```powershell
# Explicit one-time creation, or exact verification of an existing cell store.
.\rocell.ps1 physical-onboard init-v2-storage --cell-id CELL-A --json

# Read-only cross-store verification after each process or machine restart.
.\rocell.ps1 physical-onboard verify-v2-runtime --cell-id CELL-A --json

# Create one new, blank, source-bound v2 diagnostic session.
$SessionId = 'arrival-20260907-cell-a-001'
.\rocell.ps1 physical-onboard new-v2 `
  --cell-id CELL-A `
  --session-id $SessionId `
  --json

# Verify that exact session and both cell-global ledgers together.
.\rocell.ps1 physical-onboard verify-v2-runtime `
  --cell-id CELL-A `
  --session-id $SessionId `
  --json
```

These commands are the supported M1 surface. Do not substitute the legacy
`new`/`next` path or a direct Python call for M1 initialization. The legacy
workflow remains independently supported and does not gain M1 durability merely
because the M1 runtime exists.

Initialization is explicit. `new-v2` must not silently create or repair the
cell store. The deployment root must remain on an approved local fixed Windows
NTFS volume; mapped/UNC, removable, RAM-disk, and other volume types are
rejected. Copying only part of the tree, switching source bindings, moving to
another volume, or changing qualification identity causes startup to fail
closed.

After each restart, run `verify-v2-runtime` before creating or resuming a v2
session. A healthy empty store reports
`M1_STORAGE_READY_ZERO_HARDWARE_AUTHORITY`, zero unresolved/uncertain attempts,
no quarantine latch, `effect_methods_exposed: false`, and zero device/robot
operation counters. `effects_allowed_by_m1_storage: true` means only that the
storage admission state is clear; it is not an effect permit and does not
activate a hardware path.

## Files that form one deployment

The locked policy places the deployment under
`software/runs/physical-onboarding/`. Its durable structure is conceptually:

```text
physical-onboarding/
  durability-anchor.json
  lease-*.lock
  lease-*.owner.json
  lease-*.reconciliation-*.receipt.json
  cells/
    cell-<sha256-of-cell-id>/
      cell.json
      attempts/
        header.json
        head.json
        events/event-00000000.json ...
      quarantine/
        header.json
        head.json
        events/event-00000000.json ...
  onboarding-<session-id>/
    header.json
    journal/
    evidence/
```

Treat this as one evidence set. Do not rename entries, edit JSON, delete a
suffix, clear owner metadata, copy one session without its cell ledgers, or
replace a head by hand. Back up or archive the whole deployment only while no
writer owns a lease, and verify it again before relying on the copy.

## Restart and recovery rules

M1 is intentionally conservative:

- A write that did not advance its committed head is not silently adopted.
- A committed intent that stopped before `EFFECT_ARMED` may be sealed only by
  the controlled evidence-only recovery path as `ABORTED_PRE_EFFECT`.
- Once an attempt reached `EFFECT_ARMED`, missing completion evidence becomes
  `SEALED_UNCERTAIN` and latches the cell-global quarantine.
- Neither case replays the original operation.
- A new session ID cannot bypass an unresolved attempt or a quarantine latch.
- An OS lock becoming free after a process exits does not prove that the prior
  operation was safe or complete.
- Stale `ACTIVE` owner metadata requires an exact, reviewed reconciliation
  record. Process identity alone is not permission to clear it.

The current CLI does not expose automatic recovery, stale-owner clearing, or
quarantine clearing. If verification reports
`M1_INTEGRITY_VALID_RECONCILIATION_REQUIRED` or
`M1_INTEGRITY_VALID_CELL_QUARANTINED`, stop. Keep the arm de-energized, retain
the entire deployment directory, and review the evidence. Do not retry the
operation, create another session, or delete the file that caused the hold.

## Guarantees and limits

M1 is designed to fail closed for ordinary local-process crashes, concurrent
writers, stale challenges, malformed or noncanonical JSON, unexpected links or
paths, and ambiguous attempt state on its qualified deployment volume. Its
hash chains and immutable records make inconsistency detectable under the
project's declared local-software threat model.

M1 does not yet provide:

- the M2 effect-capable coordinator, bounded worker executables, one-use
  permits, or energization envelopes;
- a reviewed stage assessor or terminal/browser wizard;
- a physical B0477 identity/open/capture provider;
- a physical RoArm identity/serial/T=105 provider;
- calibration, noncontact motion, keyboard-contact, or phone-contact release;
- automatic repair, automatic retry, or quarantine clearing;
- protection against a trusted local administrator deliberately replacing the
  program and rolling back every local copy together; or
- an independently anchored, signed commissioning bundle.

The final two protections require later independent review and an off-machine
anchor. A successful M1 self-test is evidence that the current Windows/NTFS
deployment supports the implementation's required primitives; it is not a
claim that the camera, arm, power system, E-stop, placemat, or calibration has
been physically qualified.

## Arrival-day role

M1 should be run before either device is opened. It gives arrival onboarding a
stable cell identity, a fresh storage qualification result, global safety
ledgers that survive session changes, and an empty v2 session to which later
reviewed evidence can eventually be attached. The arrival sequence remains:

1. verify the checkout and host without device access;
2. initialize or verify M1 storage on its final NTFS volume;
3. create and verify a unique v2 diagnostic session;
4. keep camera and arm effect paths disabled until their later milestone
   providers, permits, receipts, and review services exist;
5. inspect and mount the camera/arm using the physical runbooks; and
6. advance only through separately implemented and reviewed onboarding stages.

Today, step 3 is the M1 stopping point. It is useful pre-hardware infrastructure,
but it does not make the system ready to connect, energize, calibrate, move, or
type.
