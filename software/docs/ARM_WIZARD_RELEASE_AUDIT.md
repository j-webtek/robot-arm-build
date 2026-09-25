# Arm wizard release audit and next engineering boundary

Date: 2026-09-12. Parent plan: [ROCELL-ARM-WIZARD-001](ARM_WIZARD_IMPLEMENTATION_PLAN.md).
This is a source audit, not hardware qualification or authorization to open COM6.

## Holds and their owners

| Boundary | Current behavior | Evidence/work required before a reviewed replacement |
| --- | --- | --- |
| `arm_connection.json` | Port/unit/firmware unresolved; no auto-connect/initialize; build and capability checks required | Received-unit identity and applicable power/firmware review; never fill from nominal defaults |
| `WindowsNativeSerialApi._kernel` | `_native_release_hold()` raises before DLL loading | Reviewed ABI/lifecycle, independent driver qualification and narrowly registered physical purpose |
| `NonPurgingArmFeedbackBackend` | Native adapter remains held; incapable adapter available | Actual supervised lifecycle and original admission; metadata alone cannot construct stronger reviewed identity |
| `ArmFeedbackWorker` | Physical composition separately held; pyserial purge incompatibility separately identified | Exact identity/model/firmware/boot references, non-purging backend, finite owner/cleanup qualification |
| `owned_arm_feedback_runner` | Requires incapable composition before process dispatch | Versioned physical registration, request/result purpose, original one-use scope and verified containment |
| `SerialTransport.send_motion` | Always raises for live motion | Bounded goal/path executor, calibration, limits and separate motion authority |
| Original stages | Catalog runtime migration pending; original arm identity work order is proposed | Genuine predecessor producers and stage 9–12 service/storage/assessment/review integration |

Removing one hold would not complete the other layers. A raw pyserial script,
unreviewed SDK construction or Wi-Fi fallback would bypass rather than satisfy
these requirements and is not the implementation path.

## Dependency findings

The [vendor electrical design review](ARM_USB_ELECTRICAL_DESIGN_REVIEW.md) now
documents the linked controller schematic, separate nominal supply nets and
RTS/DTR reset circuit. It narrows A2's design questions without asserting measured
isolation or removing native release holds. Expected-model confirmation is
accepted from the operator; the remaining gap is not adapter identification.

1. Original stage 9 requires genuine stage-8 static registration. Bench metadata
   diagnostics are not that predecessor and must remain separately labeled.
2. `commissioning_rehearsal_service.py`, `rehearsal_arm_identity_stage.py`,
   `rehearsal_power_stages.py` and rehearsal feedback producers exercise modeled
   evidence. They are not proof of physical original stage implementation.
3. Stage 10 owns power safety, stage 11 manual startup observation, stage 12
   feedback-only serial opening/writing. Their physical transitions and required
   end-disconnected policy remain distinct.
4. Installed-firmware and boot-policy evidence required by the feedback binding
   cannot be manufactured from the fixed T=105 packet or the network display.
5. A first passive engineering serial observation needs its own reviewed entry
   contract if it is to happen before canonical commissioning. It must not require
   its own successful feedback output as a prerequisite, nor grant feedback after
   a passive open succeeds.

## Next bounded contract to implement (A2)

Proposed purpose: `USB_PASSIVE_OPEN_OBSERVE_CLOSE`. This name is design-only;
there is currently no registered physical action for it.

- Input references: exact source/runtime/profile identity; current generic/native
  USB review; received-unit association; independent isolation review; fresh
  operator attestation; unique attempt and owning launch; absolute deadline.
- Admitted effects: one exclusive open, reviewed configuration/readback, bounded
  passive observation and cleanup. No outbound JSON, purge, reset toggle, torque,
  firmware operation, power switching or movement command.
- Native configuration/control-line changes still have possible startup effects;
  do not call this physically inert simply because outbound JSON is forbidden.
- Runtime: reuse the existing owned process boundary. Specify a separate closed
  protocol version/purpose and exact package roster; do not alter historical
  request semantics or let a public flag activate the old held branch.
- Outputs: actual settings/readback, bounded startup data and truncation counters,
  elapsed times, open/config/read/cleanup outcomes, source/runtime references and
  explicit actual versus modeled provenance. No `commissioned`, `safe_to_move`,
  `installed_firmware_verified` or equivalent inferred success flags.
- Failure: known failed attempt is exportable; unknown cleanup prevents another
  device attempt. All original attempts remain append-only. Closing a port never
  establishes the external power state.
- Review still required: verify actual USB/servo supply isolation or obtain
  competent electrical evidence. The user's prior cable-disconnected statement
  is an attestation, not that measurement. Determine acceptable startup/reset
  observation method and numerical budgets before physical release.

Contract development and incapable tests can proceed while physical evidence is
missing. Physical dispatch must remain unavailable until these entry conditions
and the new owner/retention composition are implemented and reviewed.

## Readiness implementation in this increment

`arm_wizard_readiness.py` derives a compact next-step projection from the existing
service-owned view. The browser and terminal consume it. It gives priority to a
running operation or service hold, then explicit inventory/review/native checks,
and finally export plus the truthful unreleased-backend explanation.

The recommended browser action is an existing validated action form with the
normal preview/confirmation flow. No new device actions, current-unit defaults,
physical holds, stage acceptance or native release are introduced.

## Acceptance work still open

The initial `arm_bench_qualification_contract.py` codec is now implemented and
tested. It validates immutable bounded request bytes, exact evidence-reference
roles, fixed passive purpose, one open attempt, zero outbound bytes/retries, a
5-second observation and 2-second cleanup allowance, and 64 KiB startup data.
These are proposed engineering-test budgets, not measured performance guarantees.
The parser explicitly reports `SYNTAX_VALIDATED_NOT_ADMITTED`; it authenticates
none of the referenced originals and provides no physical dispatch capability.
The result codec is now implemented in `arm_bench_qualification_result.py`.
Admission service, original retention and runtime dispatch join remain to be
implemented. A parsed `physical` mode never releases a held backend.

### Passive result checkpoint

The result is bounded to 96 KiB and binds the exact request, attempt, launch,
runtime reference and mode/provenance. It retains up to 64 KiB of startup bytes
with exact encoding/hash checks. Missing/unaccounted bytes remain explicitly
unknown rather than being assigned a zero count. Timestamps and reported
open/close state must be internally consistent.

Summary states distinguish `OBSERVED_CLOSED`, `NOT_OPENED`, `FAILED_KNOWN`,
`CLEANUP_UNCERTAIN`, `SIDE_EFFECT_UNCERTAIN` and `INCIDENT_HOLD`. Late completion,
unexpected outbound bytes, readback failure, truncated data and unknown cleanup
are representable and held; none becomes a qualified hardware result. Reported
port closure remains distinct from authenticated process/handle cleanup and final
power observation. Even a clean parsed result reports runtime authentication,
physical authority, connection and qualification as false.

Final focused regression: 169 passed in 5.32s across request/result, readiness,
existing arm-owned evidence and owned protocol tests. The final result module
also passed scoped Mypy; final test evidence is
`software/runs/pytest-arm-passive-result-20260912-03`. No physical device/process
dispatch occurred. The first run's oversized test parameter caused test setup
errors; short explicit test IDs fixed the fixture naming, not production limits.

Next: use this codec at the bounded supervised-child result boundary, authenticate
the owner/runtime separately, retain the original bytes even on parser failure,
and implement original admission/retention before enabling a physical action.

Update: [passive process integration](ARM_PASSIVE_PROCESS_CHECKPOINT.md) now joins
the codec to the existing owner with a fixed incapable child and real contained
process tests. Original evidence authentication/storage, public wizard dispatch
and the physical serial backend remain unfinished.

- Add full browser interaction coverage for guided forms, stale revisions and
  double submission (beyond existing generic action-form coverage).
- Finish the A2 closed contract and incapable lifecycle/retention tests.
- Audit exact policy/runtime registration before any new physical composition.
- Reconcile older camera run-06 status entries individually; the received-unit
  document and completion matrix already identify the terminal failure.
