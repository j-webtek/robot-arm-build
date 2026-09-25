# Model-to-arm translation assurance

**Status:** governing AI integration process, 2026-09-25
**Applies to:** every worker changing intent models, vision models, target
resolution, trajectory planning, safety admission, controller encoding, or
outcome verification

## Decision

The model emits a semantic task proposal and scene classifications. It does
not emit executable arm commands. Deterministic, versioned RoCell components
translate an accepted semantic task into named targets, calibrated board-frame
coordinates, collision-screened joint trajectories, and finally controller
protocol messages.

This separation is the project definition of correct model-to-arm translation:

```text
user request
  -> grounded model/intent result
  -> RoCell semantic ActionPlan
  -> named device targets
  -> same-frame visual target observations
  -> calibrated board/tool coordinates
  -> inverse kinematics and full-route screening
  -> safety admission bound to exact hashes and epochs
  -> controller command encoding
  -> transmitted-command receipt and fresh feedback
  -> independent keyboard/phone outcome observation
```

A stage may accept, reject, or return uncertainty. Missing evidence always
stops progression. No later stage may reconstruct or assume a value rejected
or omitted by an earlier stage.

## Ownership by stage

| Stage | Accepted input | Output owner | Required result |
| --- | --- | --- | --- |
| Intent grounding | User text and fresh observation reference | AI adapter plus grounding policy | Operation, one device, exact literal payload, or explicit clarification/rejection |
| Semantic compilation | Grounded proposal | RoCell keyboard/phone compiler | `rocell.action_plan.v1` with named actions and a plan hash |
| Scene assessment | Exact image bytes | Local multimodal observer plus deterministic quality checks | Device/layout/state/visibility classifications bound to frame and image hashes |
| Target localization | Same image and active target catalog | Precision perception and deterministic target resolver | Named targets in board millimetres with source, confidence, and error evidence |
| Calibration | Immutable configuration epoch | Calibration registry | Camera, board, base, device, and tool transforms with validation evidence |
| Planning | Named calibrated targets and fresh telemetry | Deterministic IK/trajectory planner | Ordered hover, approach, contact, retract, and clearance samples |
| Admission | Exact observation, calibration, plan, trajectory, and policy hashes | Safety supervisor | Rejection or a short-lived, single-use permit |
| Encoding and write | Unexpired permit and exact admitted trajectory | One verified execution adapter | Exact controller bytes/JSON and a correlated receipt |
| Verification | Fresh controller feedback and post-action image/device state | Independent outcome verifier | Observed success, observed failure, or uncertainty |

## Model output boundary

Permitted learned outputs:

- `type_text`, `clarify`, or `unsupported` intent decisions;
- keyboard or phone identity and visible state;
- image quality, obstruction, and target visibility classifications;
- a named target plus bounded device-local or board-coordinate hypothesis under
  `rocell.model_motion_proposal.v1`;
- other bounded perception hypotheses that deterministic geometry validates.

Coordinate hypotheses never become arm coordinates by themselves. The motion
bridge must verify the named target, frame, surface plane, safe region,
confidence, image provenance, and catalog identity before calibrated planning.

Forbidden learned outputs:

- servo counts, joint angles, PWM values, speed or dwell parameters;
- controller JSON, serial bytes, network commands, or transport selection;
- execution permits, collision-clear claims, calibration identities, or
  success claims;
- automatic retries or corrections after failure or uncertainty.

If a model response contains a forbidden field, unknown field, invalid enum,
nonfinite number, changed text payload, or unbound coordinate, validation must
reject the complete response.

## Functional translation invariants

Every implementation and test must preserve these invariants:

1. **Literal intent:** the compiled text exactly matches the user-grounded
   payload. Its hash and action sequence are reproducible.
2. **Named-target continuity:** each semantic action resolves to the intended
   key or phone region. The model cannot replace a requested target.
3. **Frame continuity:** scene classification and target coordinates bind to
   the same frame ID and exact image SHA-256.
4. **Coordinate continuity:** pixels, board millimetres, arm-base coordinates,
   tool-tip coordinates, joint space, and controller units remain distinct and
   are connected only by active calibrated transforms.
5. **Configuration continuity:** camera, board, base, device, tool, arm,
   controller, software, and power epochs cannot change during an attempt.
6. **Trajectory continuity:** admission covers the complete ordered route,
   including hover, approach, contact, retract, transitions, and cable/body
   clearance. Endpoint reachability alone is insufficient.
7. **Command continuity:** encoded commands are derived from the exact admitted
   trajectory. The receipt records requested, encoded, transmitted,
   acknowledged, and measured values separately.
8. **Outcome independence:** command acceptance and servo arrival do not prove
   a key press or screen action. A fresh independent observation determines the
   outcome.
9. **Fail-closed uncertainty:** stale data, missing coordinates, weak
   confidence, obstruction, calibration gaps, collisions, transport faults,
   or ambiguous outcomes create no write and no retry.
10. **One writer:** AI, perception, dashboards, evaluators, and shadow tools
    cannot instantiate a writable arm transport.

## Required worker verification

Before merging a change that affects translation, the worker must provide a
trace covering every affected boundary:

1. user request and expected literal payload;
2. grounded proposal and rejection behavior for ambiguous variants;
3. compiler-produced semantic actions and plan hash;
4. frame, image, scene-observation, target-catalog, and precision-observation
   hashes;
5. calibration snapshot and complete configuration epoch vector;
6. named target through every coordinate frame with units;
7. route samples, selected IK branch, limits, continuity, and collision report;
8. safety decision and reason codes;
9. exact encoded command compared with the admitted trajectory;
10. receipt fields for sent data, acknowledgement, goal/readback, and outcome;
11. explicit counts for hardware writes, permits, retries, and commands.

Shadow and simulation work must report all four counts as zero. A physical
test must bind each nonzero count to an approved permit and reviewed receipt.

The current machine-checkable implementation is
[`translation_assurance.py`](../rocell_ai/translation_assurance.py), with its
versioned [JSON schema](../schemas/translation_assurance_v0.schema.json). Run
`python software/ai/run_offline.py assure-shadow --shadow shadow.json` to
validate stage ordering and produce a hash-bound assurance record. In v0,
exactly one stage blocks progression and all later stages must be `not_run`.

## Minimum test matrix

Each supported keyboard or phone capability needs tests for:

- one successful semantic mapping per supported character or target class;
- repeated characters and order-sensitive strings;
- unsupported characters, unknown device state, ambiguous text, and extra
  requested operations;
- stale image/telemetry, altered hashes, mismatched frames, and changed epochs;
- absent device, wrong layout, darkness, blur, glare, and arm/tool/cable
  obstruction;
- missing target, wrong-target substitution, low confidence, and coordinates
  outside the calibrated envelope;
- unreachable IK, joint-limit margin, discontinuity, collision, and incomplete
  route geometry;
- expired/reused permit, altered trajectory, encoding mismatch, partial write,
  disconnect, and controller restart;
- sent command with no observed effect, wrong observed effect, and ambiguous
  post-action state.

Tests must assert the specific rejection reason and confirm zero writes for
every rejected case. Held-out physical evaluation remains separate from
synthetic and agent-authored evaluation.

## Current implementation status

The repository currently implements grounded intent, semantic compilation,
hash-bound scene observations, a synthetic precision-coordinate contract,
fail-closed vision fusion, replayable zero-write shadow previews, and a strict
`rocell.model_motion_proposal.v1` bridge for bounded coordinate hypotheses.
That bridge checks the named target, coordinate frame, target envelope, plane,
confidence, and provenance; transforms approved device-local coordinates into
the board frame; and deliberately emits no controller command or physical
authority. The
provisional offline Gemma 3 4B observer supplies scene classifications. The
real-photo shadow example stops at `precision_observation_missing` because no
calibrated real-image coordinate observation exists.

The following are still required before functional arm-command qualification:

- fixed-camera real-image target labels and held-out evaluation;
- commissioned camera/board/base/device/tool calibration;
- precision confidence and error thresholds derived from physical data;
- complete full-body, tool, cable, and environment route screening;
- an execution adapter that consumes only a valid single-use permit;
- independent observation of the resulting key or phone action.

## Worker workflow

1. Read this document, the [AI contract](CONTRACT.md), and the
   [shadow execution plan](../../docs/AI_SHADOW_EXECUTION_IMPLEMENTATION_PLAN.md).
2. Identify the stage owned by the change and list its input/output contracts.
3. Implement the smallest change without crossing ownership boundaries.
4. Add positive, rejection, tamper, stale-data, and zero-write tests.
5. Run the AI suite and the relevant RoCell unit/integration suites.
6. Save a hash-bound shadow record and document remaining assumptions.
7. Update the status documentation without describing simulated evidence as
   physical evidence.

No worker may promote a learned output directly into controller space. New
capabilities extend semantic profiles, target catalogs, calibration evidence,
planning, admission, encoding, and verification in that order.
