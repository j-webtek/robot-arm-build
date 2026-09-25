# r30 fault-settling integration candidate

## Decision

Frozen, compiled and reviewed offline. **Not installed and not motion-released.**
Installed hardware remains r29. No controller connection, startup, target write,
torque command or settings change was performed for this candidate review.

r30 integrates the bounded settling collector with the board owner, candidate
HTTP routes and signed host export workflow. It preserves the original fault and
permits no additional actuator writes through settling capture.

## Reproducible evidence

All export IDs refer to `software/runs/wizard-exports/`.

- Source stage: `wizard-20260919T221100042416Z-1e047753eab94b5e891b6c84a0546da0`
- Compile: `wizard-20260919T221302697829Z-343bb03334ac4b208bac6495cef8dc99`
- Offline review: `wizard-20260919T221317679072Z-8a44ccc7848b4a108e6017b7888b909b`
- Frozen source: `.firmware-tools/configured-diagnostic-candidate-r30/RoArm-M3_example`
- Build: `.firmware-tools/build-configured-diagnostic-candidate-r30--default-4mb-no-psram`
- App SHA-256: `e325a0a3062127417bfd23351cf981f7486d79d24e4e9dc53e43ef64732b566c`
- App size: 1,151,872 bytes; offset `0x10000`; slot size `0x140000`.
- Remaining app space: 158,848 bytes (155.125 KiB).
- Bootloader SHA-256: `b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7`
- Partitions SHA-256: `148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1`

The reviewer checked artifact/source hashes, the unchanged diagnostic-only entry
point, retained backup/recovery artifacts, compiled settling route strings, fault
digest linkage, and 242 relevant static stack frames. The largest individual
frame is 528 bytes. This is NOT a bound on total stack use or heap availability.
Runtime resources and current device bytes have not been verified by this review.

## Why this is not a movement release

The motion owner retains r29's exact starting-window checks and targets. Historical
settled shoulders were 2429/1688, with goals 2419/1695; that pose does not satisfy
the old starting contract. Installing this image would not make the old step
appropriate. No thresholds were silently widened and no compensation was inferred.

The host live runner therefore still rejects fault-settling execution: there is
no new motion/revision binding. Candidate transport capability is not authorization.

## Next implementation

Started: [fresh-pose local-step contract](LOCAL_SHOULDER_STEP_CONTRACT.md) implements
host proposal/signing, native target/prewrite checks and native authenticated
three-record digest/plan verification, with parity and real-crypto tests. The
controller-owned capture/export stage and one-shot dispatch integration remain
before this can become a motion release.

1. Define a bounded next-step contract from a fresh seven-joint capture, separating
   measured starting positions from the previously active goals. Retain verified
   upward direction, limits and one-use ownership; do not blindly home or return.
2. Prefer a reviewed parameterized local-step contract over another hardcoded
   waypoint per firmware image. Bind parameters, reference-pose digest, boot and
   command to the start authorization; check them again immediately before write.
3. Cover that contract and fault-settling together in the native/host bridge,
   including partial arrival and transient neighbor response.
4. Freeze/review the resulting release, then add its exact app/startup/host bindings.
   Deploy through the existing app-only workflow, preserving settings/credentials.
5. Run one bounded movement from fresh evidence, export arrival or fault and
   settling, and assess the residual before any subsequent move.

The intermittent diagnostic-export failure documented in the integration plan
remains a release-review caveat: later tests passed, but its cause is not proven.
