# Mixed shoulder target experiment: path to verified destinations

## Implemented offline

### Authenticated resumable integration completed in source

The native session now has a distinct `MixedTarget` scope, signed as
`MIXED_TARGET`, with command identity `mixed-shoulder-target-v1`. The existing
board adapter opts in only when built with `ROCELL_MIXED_TARGET_EXPERIMENT`;
default builds retain the old pair-hold scope. Prepare/start perform no servo
I/O. The shared bus reservation and control-task dispatch rules still apply.

The mixed state machine exports BASELINE, PRELOAD_INTENT, PRELOAD_RESULT and
three PRELOAD_VERIFIED records. Each requires a boot/command/sequence/digest-bound
authenticated receipt after durable host export. It reacquires before the one
write, preserves neighbors, never sends an explicit torque command, and enforces
a two-second post-write observation/receipt deadline. Both expected torque
outcomes finish without further action. Fault scans are retained when available.

`mixed_shoulder_session_review.py` independently validates ordered identities,
raw position/speed/moving evidence, target/speed, action timing, target readback,
neighbors and stable selected torque before the runner signs receipts.
`run_shoulder_session(..., experiment='MIXED_TARGET')` uses this reviewer and the
existing export workflow. A simulated native-process bridge exercises the actual
host runner with real signing, native authentication and filesystem exports.

Validation: 64 integration/model tests passed, including both target outcomes,
wrong-scope/tampered-start rejection, bad receipt, export abort and late final
receipt. The board ingress suite runs for both build selections. No target
write occurs before exported intent; no simulated torque-enable broadcast occurs.

**Not deployed:** the live runner intentionally rejects MIXED_TARGET on current
r23/r24 installation bindings before any network access. Hardware execution
requires a separately staged, compiled and reviewed mixed-enabled image, an exact
installation/startup binding, and explicit deployment/test approval. There is no
force flag to treat the installed passive-only image as mixed-capable.

### Native single-write candidate added

`firmware/diagnostics/mixed_shoulder_candidate.h` now implements the experiment
against the shared bounded seven-joint sampler. It exports initial state and
intent, reacquires immediately before sending, writes only the passive shoulder
once, and records three post-write scans. The selected position must still equal
the exported target immediately before sending; otherwise it stops rather than
silently altering the intent. It issues no explicit torque commands and has no
retry, reset, return or second target write.

Native tests cover passive/enabled outcomes, wrong target readback, neighbor
drift, uncertain delivery, prewrite drift, export failure and delayed post-write
observation. For both success outcomes the native JSON records are replayed
through the Python mixed-state model and checked independently of the write ACK.

The original synchronous candidate remains an offline reference. Its logic is
now adapted into the resumable session described above; it is not directly called
from a web handler. No firmware image was installed or started; r24 is unchanged.

`mixed_shoulder_trial.py` models one target write to the passive member of a
mixed shoulder pair. It preserves the already-enabled shoulder and neighboring
joints. There is no transport, torque command, restart or automatic follow-on.
`replay_mixed_shoulder_trial.py` replays validated raw pose exports and emits
separately labeled synthetic outcome cases, never live arrival evidence.

The actual three-snapshot capture selects servo13, with hypothetical target1659
from its last measured position. This number is historical; it must be replaced
by a fresh measured position immediately before a future authorized write.
Servo12's target2455 and enabled state remain unchanged in the model.

Replay export: `wizard-20260919T192458347005Z-eb5af439dfae4ae8a66b43c302b4ebab`.
Forty targeted regression tests passed, including thirteen new model cases.
Simulations cover unchanged torque and activation after a target write, stale
state, changed goals/torque, drift, moving feedback, neighbor changes, old scans,
oscillating torque and uncertain delivery. No hardware command was sent.

## Why this experiment first

An acknowledgment does not establish target readback or actual arrival. The
earlier target2455 is now stored on shoulder12, which is enabled, but we lack
the intermediate scan explaining when torque changed. Do not infer exact cause.
A same-pose command on the passive shoulder can investigate target/torque
behavior without intentionally requesting travel. It may still actuate and
requires a reviewed native implementation and separate bounded authorization.
Same-pose success would not prove commanded movement or spatial accuracy.

## Remaining work before physical execution

1. Implement a native one-write owner using the tested mixed-state contract.
   Preserve signed command identity, exclusive ownership and export-before-write.
   Do not relax or reuse the existing passive-only session implicitly.
2. Acquire and publish the initial full state regardless of admission outcome.
   Reacquire immediately before the write and compare positions, goals and torque.
   Keep current boot identity and controller-clock timestamps bound throughout.
3. Write only the passive shoulder's measured target once. Treat this as possibly
   actuating. No shoulder12 write and no explicit torque enable/disable.
4. Capture and export command bytes, delivery result and post-write state even
   on rejection or uncertainty. Do not retry an uncertain transmission.
5. Verify three post-command scans: exact selected target readback, bounded
   position change, unchanged neighbors and stable torque classification.
   Stop after reporting either passive or enabled outcome; no automatic enable.
6. Integrate host review/runner and test native-to-host simulated execution for
   both outcomes and all failure cases before reviewing a firmware candidate.
7. Request the exact necessary installation/startup/test scope only after that
   implementation is ready. Current r24 hardware has not been changed by this work.

## Following experiment: actual destination change

After both shoulders have an understood, verified operational state, select one
small target change with a validated direction that increases board clearance.
Record baseline, requested destination, transmitted target, target readback,
fresh position series, signed endpoint error and settling time. Verify outbound
arrival before considering a separately scoped return. Compare both directions
over repeated trials before adding compensation. Do not equate encoder accuracy
with tip accuracy or use the disabled joints' zero goals as home coordinates.

The implementation covers same-pose target establishment only. Native/host
integration is tested in simulation; reviewed firmware release, wizard-specific
controls, moving-endpoint validation and physical accuracy remain open.
