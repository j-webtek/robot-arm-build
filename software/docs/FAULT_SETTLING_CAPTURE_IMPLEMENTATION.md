# Fault settling capture: implementation checkpoint

Latest: [r30 frozen build and offline release review](R30_FAULT_SETTLING_RELEASE_REVIEW.md).
The image compiled and passed offline artifact review. It is not installed or
released for movement from the latest known pose; live execution remains disabled.

## Purpose

Keep the motion command faulted, but record where its already-active target
eventually leaves the arm. A fault stops command progression, not necessarily
physical motion. Never treat a stationary residual as successful target arrival.

The r29 trial moved the shoulders by -19/+21 counts, leaving residuals +10/-7.
Its transient wrist excursion triggered the fault before settling. The subsequent
settled capture required a diagnostic restart. These are historical observations;
they are not permission to reuse the old starting window or assume current pose.

## Implemented offline

`firmware/diagnostics/shoulder_fault_settling_capture.h` provides a separate,
one-use read-only collector. It does not alter the installed controller or the
existing motion state machine.

- Begin only with a latched parent fault and exported original failure evidence.
- Acquire the existing validated seven-servo scan (mode, torque state, goal and
  raw feedback), on the controller task with exclusive bus ownership.
- At most 12 scans within eight seconds, with at least 500 ms between scans.
- Retain each scan until its identity-bound durable export is verified; no reads
  while waiting. Late, wrong-sequence or failed export terminates collection.
- Require three stationary scans within one count of a fixed stability anchor,
  and at least two seconds elapsed, before reporting `STABLE_SAMPLED_POSE`.
  Slow cumulative drift cannot satisfy this by shifting the anchor every scan.
- Preserve valid surprising target/torque-change scans for failure reporting.
- Stop collection on invalid feedback, lost admission, changed target/torque,
  clock reversal, deadline or export failure. Never retry or issue a target,
  torque command, return, reset or settings change.
- Keep residual errors in the observations. Stability does not imply arrival,
  physical clearance, calibrated tip accuracy or permission for another move.

Native tests use a bus with no write methods, providing a compile-time check
against accidental actuator writes. Tests cover stable residuals, continuing
motion, accumulating drift, changed goals/torque, time reversal/deadline, invalid
exports, lost admission and failure at each of the 28 register reads.

Validation: 150 tests passed in 82.45 seconds across the new collector, existing
preload/hold candidate, session bridge and board session suites. This is a focused
offline regression result, not a full-suite or physical hardware validation.

## Remaining integration before hardware use

### Authenticated candidate integration (not deployed)

Implemented `shoulder_fault_settling_session.h`, a separate fault-linked session:
the original fault's exact bytes must receive a valid parent-command export
receipt before any reads. Subsequent observations use a separate `settle-` command
namespace and include the original fault SHA-256. Sequence, boot, command and
record digest are bound by the existing HMAC receipt verifier. Parent fault and
original evidence are neither consumed nor cleared.

Candidate `shoulder_fault_settling_routes.h` provides status/record GETs and
start/receipt POSTs. No handler has access to a servo bus. Registration is explicit
and is NOT added to installed r29. The board must provide only the authorized,
faulted owner's collector and advance it on the reserved control task.

Host `shoulder_fault_settling_export.py` independently validates the linked record,
timing, seven joint rows, raw position bytes and unchanged goals/torque before
durably exporting and signing. A failed review latches further signing off.

The native/host process bridge passed real Windows SHA/HMAC verification using
synthetic test keys and a read-only fake bus. Tests include forged original and
sample receipts, cross-command receipt replay, malformed evidence, route input
validation and preservation of the parent's original fault bytes. No credentials
or live hardware are used in these tests.

Integration regression result: 163 tests passed in 80.60 seconds across the
collector, authenticated bridge, routes, existing session bridge and board session.
After tightening host JSON shape validation, the 13-test authenticated bridge/
review suite was rerun and passed. These counts overlap; they are not hardware
validation or a full repository test result.

### Board-owner and full runner composition

`ShoulderSessionOwner` can now explicitly own a separate settling session. The
board opts in only with `ROCELL_FAULT_SETTLING_CAPTURE`; without that define the
old route set remains unchanged. Allocation failure prevents session admission.
The collector is accessible only after its active parent faults, keeps the same
sticky bus reservation, and advances only on the existing control task. Entering
a fault does not automatically start acquisition; an authenticated original-fault
export receipt remains necessary.

`run_shoulder_session(..., fault_settling=True)` now exercises the full candidate
workflow in simulation. It delegates to `shoulder_fault_settling_runner.py`, saves
raw observations before independent review, signs accepted records, and keeps the
parent run `STOPPED` even if settling succeeds. The host independently checks the
stationary sample sequence rather than trusting a controller `SETTLED` string.
The restricted HTTP adapter has an explicit settling capability and separate
one-use request identities for parent and settling commands.

Live use of the new runner option remains rejected before any transport call:
there is no reviewed live revision binding yet. Existing r29 routes and firmware
have not changed. Next are a frozen firmware build/resource review, exact release
bindings, installation and a bounded physical trial from fresh pose evidence.
Do not use a simulation adapter to bypass the live release checks.

Composition validation: 77 board-ingress tests passed, including the opt-in
settling build, and the 108-test host/native/routes/HTTP suite passed on its final
run. An earlier run of that 108-test suite had 107 passes and one pre-existing
recovery-path `WizardDiagnosticExportError`; it stopped without a further receipt.
That case passed alone and the full suite subsequently passed. The sporadic export
failure's underlying cause is not established; retain this caveat for release
review rather than claiming it was fixed. A new fake-HTTP test initially omitted
the required JSON content type; the fixture was corrected, not the transport check.

1. Attach the collector to a new reviewed session revision, not the installed r29
   contract. Retain the parent `FAULT`, reason and original failure record.
2. Bind authorization and every export receipt to boot ID, command ID, original
   fault digest, capture sequence and retained record digest. The boolean core
   export hook is not authentication and must never be exposed directly as HTTP.
3. Serve retained observations via authenticated handlers; schedule fresh bus
   reads only on the owning controller task. Preserve sticky bus ownership.
4. Extend the host runner to export the original fault first, then collect the
   bounded settling records. Report failed motion and settling result separately.
5. Test integrated fault/export/replay cases, build and review the frozen image,
   and deploy through the existing app-only preservation workflow.
6. Obtain a fresh starting capture and review one bounded upward step from that
   state. The previous r29 starting window does not fit the last settled pose.
   Do not fit compensation from this single trial or blindly replay its target.

No firmware installation, controller restart or physical movement was performed
for this implementation checkpoint.
