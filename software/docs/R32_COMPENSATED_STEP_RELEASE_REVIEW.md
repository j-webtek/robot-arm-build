# r32 compensated shoulder step — offline release review

## Status

**Deployment paused by the updated user-selected strategy.** Follow
[bounded characterization](BOUNDED_MOTION_CHARACTERIZATION_PLAN.md) instead of
installing r32 for another single compensated trial. Preserve this candidate as
offline evidence and reusable components; it is not the active next release.

Source frozen, ESP32 default 4 MB/no-PSRAM compilation successful, offline artifact
review passed. **Not installed.** r31 remains the installed image. No hardware
connection, restart, settings write or movement occurred in this checkpoint.

This candidate implements the [compensated contract](COMPENSATED_SHOULDER_CONTRACT.md).
Desired measured endpoints and compensated goal-register targets remain distinct.

## Board composition

Build selection: `ROCELL_COMPENSATED_SHOULDER_STEP`. Selecting both this and the
older local-step macro is a compile-time error.

- `POST /rocell/compensated-step/prepare`: exclusive reservation, existing key
  loading and owner allocation. No servo operations in the handler. Subsequent
  same-task polling begins the three-record read-only capture.
- `GET /rocell/compensated-step/status` and `/record`: retained state/evidence.
- `POST /rocell/compensated-step/authorize` and `/receipt`: exact signed plan
  admission and durable-export progression.
- `/rocell/shoulder-settling/*`: read-only collection attached to a faulted parent.

The selected binary excludes `/rocell/local-step/prepare` and
`/rocell/shoulder-session/start`. The existing diagnostic startup path remains;
no stock startup homing path or new torque operation is added.

Preparation rejects a conflicting owner, missing key, unhealthy/busy state,
insufficient free heap or insufficient contiguous allocation space. Both large
owners are heap allocated. Free memory must cover owner sizes plus 32,768 bytes,
with a postallocation reserve check. This policy is not measured live sufficiency.

Board and existing-configuration regression: **101 passed in 20.09 seconds**.
The 13 compensated cases exercise board ingress with a stub bus and zero writes;
full valid signed-command progression is covered by the prior native session and
runner tests, not by claiming these board-ingress cases performed motion.

## Frozen artifacts

Under `software/runs/wizard-exports/`:

- Stage: `wizard-20260920T003946420647Z-b724a96736f34514b2b303f2c97df547`.
- Compile: `wizard-20260920T004148743875Z-a1aeb0c7fdd9484188bc457606fd0dde`.
- Review: `wizard-20260920T004158925113Z-f006401dd80243a08dd7f1cd737fa587`.

App SHA-256: `98e33a9f7ba0e5f5036a0098ef342cadbbfba786496653f2f5b728b9347dca14`.
App size: 1,152,256 bytes; slot: `0x140000`; offset: `0x10000`;
remaining slot space: 158,464 bytes.

Bootloader and partition hashes match the existing reviewed profile. Original
backup/recovery evidence, frozen source hashes, artifact identity and diagnostic
entrypoint were checked. Review inspected 238 relevant static frames; largest
individual frame was 960 bytes. This is not a total call-stack bound or live
runtime resource measurement. Offline review deliberately reports deployable=false.

Source: `.firmware-tools/configured-diagnostic-candidate-r32/RoArm-M3_example`.
Build: `.firmware-tools/build-configured-diagnostic-candidate-r32--default-4mb-no-psram`.
Neither the frozen r31 artifact nor the saved settings image was changed.

## Remaining release sequence

1. Pin this exact r32 app and review in installer/evidence/startup bindings;
   predecessor is the installed r31 image. Preserve the existing filesystem and
   credentials; use a new exclusive deployment journal.
2. Enable only the compensated transport namespace in its explicit-capability
   adapter. Bind the host runner to r32 evidence and a fresh same-boot idle read;
   r31 authority must not authorize this candidate.
3. Review the nominal local trajectory and candidate-specific integration tests.
4. Perform one approved app-only installation and diagnostic startup, then export
   and review its startup evidence before preparing a local trial.
5. Acquire fresh state. Reject changed/out-of-envelope pose rather than replaying
   historical targets. If admitted, one bounded prospective compensation trial,
   then export desired error, goal residual and any fault-settling observations.

No global compensation, physical clearance or stylus accuracy is established by
these offline results. The first physical compensation trial remains outstanding.
