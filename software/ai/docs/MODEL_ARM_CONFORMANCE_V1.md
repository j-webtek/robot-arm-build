# Model-to-arm conformance baseline v1

This baseline compares GitHub `main` at ARM-070 with the AI research branch at
commit `caf1962389971de949a5aee40b3244bf48fcb607`. It is a zero-hardware review:
no camera, serial endpoint, controller, torque, or movement is accessed.

## Result

The software boundary is structurally aligned. The actual AI v2 assembler emits
canonical `rocell.model_motion_batch.v2` bytes that the arm decoder, trusted
registry ingress, and freshness gate accept. Repeated targets retain their exact
order (`H`, `H`, `I`). Model output contains no controller command or authority.

Operational readiness remains blocked. The latest AI study,
`inflated_risk_gate_v1`, did not pass its preregistered selection gate and did
not install a localization qualification. Its predicted scale is research
evidence, not the qualified planar error bound required by the arm. The camera,
placement, target-region, and calibration evidence needed by the trusted registry
also remains absent.

## Exact division of responsibility

| AI/model supplies | Arm runtime owns |
|---|---|
| Ordered semantic targets and board-frame XYZ candidates | Resolving the trusted capability and evidence registry |
| Capture, image, model, observation, fusion, lease, placement, and catalog identities | Freshness, revocation, safe-region checks, and error composition |
| Qualified localization error bound and its coverage/domain identity | Observed start state, IK, collision screening, and dynamics |
| Observation confidence from a declared precision method | Speed, clearance, contact, settling, permits, encoding, transport, and verification |

The AI must never emit joint angles, servo IDs, PWM, speed, acceleration,
clearance, controller JSON, execution permits, or hardware authority.

## Executable matrix

The canonical profile is
[`software/config/model_arm_conformance_profile_v1.json`](../../config/model_arm_conformance_profile_v1.json).
The integration suite proves:

1. Actual producer bytes preserve `H`, `H`, `I` and reach the arm pre-planner.
2. Missing qualified uncertainty causes producer abstention.
3. Phone plans remain unsupported by the initial keyboard-only profile.
4. Low confidence is rejected by the arm-owned registry threshold.
5. A composed uncertainty disk crossing a key's measured safe region is rejected.
6. Model-injected motion policy, controller commands, or authority is rejected.

All accepted simulation paths remain zero-authority. The measured planner is
expected to stop at `BLOCKED_CALIBRATION_MISSING_OR_STALE`; replacing that blocker
with synthetic readiness would be a regression.

## Next compatible handoff

The AI workstream can integrate only after it produces a separately confirmed,
physically applicable uncertainty qualification and a precision adapter that
populates every v2 evidence identity without invention. The arm workstream must
populate the trusted registry from commissioned camera, placement, target-map,
surface, calibration, and capability records. The first integrated physical case
should remain a single keyboard target with fresh observation and independent
outcome verification.

For the camera/support portion, the ARM-073 retained-original adapter now turns
the four exact, hash-reviewed evidence files into the typed ARM-070 bindings
without manual field transcription. It is intentionally downstream of physical
collection and owner-AI review: it authenticates and binds those inputs but does
not create them, judge model accuracy, or grant execution authority.

The current cross-lane state is materialized by
[`arm072_model_arm_operational_readiness.json`](../eval/arm072_model_arm_operational_readiness.json).
That content-bound report prevents the passing wire-contract simulation from
being mistaken for operational readiness and gives both workers one ordered
blocker map. It also recognizes the owner's ARM-067 governance decision, so the
superseded external-review dependency is not carried forward.
