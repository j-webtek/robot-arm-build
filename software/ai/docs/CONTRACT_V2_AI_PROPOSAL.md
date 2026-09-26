# S1 AI contract-v2 semantic proposal

Status: PROPOSED; arm-lane agreement pending. No published schema, decoder,
emitter migration, installed qualification, or integration completion is implied.
The shared stage board remains authoritative. This is a bounded AI design increment.

## Boundary and migration

Retain `ModelMotionBatch` as the only motion proposal boundary. Version the wire
schema explicitly as v2 after agreement; preserve immutable v1 fixtures for offline
compatibility tests. Do not auto-upgrade v1 or invent absent v2 evidence. A v2-only
consumer must reject v1 for that route. Existing v1 research behavior is unchanged.
Unknown fields, duplicate keys, nonfinite numbers, booleans used as numbers, mixed
versions and altered canonical hashes must reject the entire batch.
No joint, PWM, controller JSON, serial, permit, transport, or execution-authority fields.

## Proposed semantic groups (field spellings await shared schema review)

| Group | Required meaning |
|---|---|
| Identity | Batch/request IDs, exact compiler plan hash, device, capability-profile content hash |
| Capture | Capture ID, frame ID, exact image hash, camera identity, capture time and clock-domain identity |
| Evidence | Scene, precision, fusion and model artifact hashes; evaluation time |
| Lease | Expiry and externally issued scene-lease reference, bound to device placement and target map |
| Geometry | Producer coordinate profile, units, independently sourced placement record hash and target-map hash |
| Uncertainty | Bound type, positive finite bound in mm, coverage, qualification hash, domain ID and covered target set |
| Actions | Unique proposal ID, zero-based semantic action index, exact target ID, coordinate, contact intent, observation confidence |

One proposal per movement action, in exact compiler order; repeats remain repeats.
Batch size remains 1–64 pending consumer agreement. Evidence common to all actions
belongs at batch level; conflicting per-action overrides are forbidden.

## Freshness proposal

Use integer UTC epoch milliseconds with a declared capture clock domain. The
trusted capture service establishes clock mapping; model text cannot establish it.
Require capture <= evaluation <= consumer now < expiry, with expiry capped by the
consumer's registered maximum age and lease deadline. Equality at expiry rejects.
Absent trusted clock mapping or future capture/evaluation rejects; do not add an
implicit skew allowance. Any later bounded skew rule needs an explicit profile.
Use monotonic local elapsed-time checks after admission; wall-clock rollback must
invalidate rather than extend validity. Recheck immediately before each action.

The producer references an externally established lease; it cannot create validity
by choosing a long expiry. Device movement, camera/placement/map changes, lost
visibility, or revoked fixed-device evidence invalidate reuse. Every state-changing
phone action requires new capture, scene, precision and fusion evidence before the
next action; phone remains unsupported in the initial keyboard-only profile.

## Uncertainty proposal

Initial bound type: `planar_l2_disk`, expressed in mm in the declared target plane.
Coverage describes the qualified calibration procedure and declared sampling unit;
it is not per-image correctness probability or batch success probability.
Observation confidence remains separate, finite in [0,1], with a declared source
and meaning in the precision profile. Never copy qualification coverage into it.
If that confidence source is unavailable, abstain rather than fabricate a value.

The consumer resolves qualification by hash in its own registry and verifies
model, domain, target set, bound type, map and evidence method. A producer's
accepted fusion decision is evidence to recheck, never admission authority.
No trusted qualification currently exists. The 6.037862 mm synthetic radius is
research evidence only and must not be installed through this proposal.

Planar uncertainty does not validate contact height. Surface-plane identity and
normal-direction tolerances need independent measured evidence. The consumer must
also account for placement/calibration uncertainty. Proposed conservative rule:
combine compatible bounded errors by addition after transforming to the same plane;
never silently discard transform error or assume independence. The arm lane must
approve the actual composition and coverage semantics before implementation.

## Placement, orientation and target-map proposal

Initial producer profile: `board_mm_xy_plane_v2`, retaining current board-frame
predictions. Axis convention, board origin, handedness and surface-plane reference
must resolve to a versioned frame definition. Do not infer these from an image.

For this profile, image-derived points must bind the camera/projection record and
precision method that produced them. Current synthetic projection is not a measured
camera calibration. Keyboard-local output is deferred to a separately specified
profile; no silent fallback between frames.

The placement record must be supplied by an independent commissioned geometry
source and bind its method, source evidence, capture applicability, validity,
translation, orientation, frame identities and uncertainty. Its source cannot be
the KeyboardPoseNet prediction being tested. A different file/hash of the same
prediction is not independence. A trusted geometry registry enforces provenance;
self-declared independence is insufficient. Rendered truth is evaluation-only.

Target-map content binds device/layout/version, named local key centers, oriented
safe regions and plane references. Transform those regions with the independent
placement, not with the model's estimated placement. Check the entire uncertainty
disk against the oriented region (inverse-transform to key-local axes for a rigid
planar rotation). Axis-aligned board bounding boxes are not an adequate substitute
for rotated safe rectangles. Reject missing placement, wrong orientation/frame,
map mismatch or any bound crossing. The latest nominal mismatch is a blocker,
not permission to center the safe region on the predicted target.

## Capability and motion-hint proposal

Consumer-owned capability profile specifies supported device, semantic compiler
profile, actions, coordinate profiles, target map, uncertainty methods and evidence
requirements. The AI references its content hash and cannot expand it. Tool/TCP
compatibility stays consumer-owned through this profile and commissioning records;
no model-selected tool or controller session. Unknown/revoked profiles reject.

Remove speed and clearance hints from v2. Retain only interaction intent and the
named target. Arm policy derives clearance, timing, contact, dynamics and settling.
This avoids carrying ambiguous v1 hints into a new contract. No learned dwell or
motion-policy override is proposed.

## Proposed acceptance matrix and next dependency

Before implementation, arm lane must accept or revise: UTC/clock policy and lease
issuer; independent placement record/provenance; oriented target representation;
uncertainty composition and coverage unit; confidence semantics; capability registry;
removal of motion hints; exact canonical JSON schema and migration policy.

Then publish a joint compatibility matrix and freeze actual emitter fixtures.
Test repeated H,H,I ordering and independent one-field mutations for plan, image,
time, lease, model, map, placement, orientation, qualification, domain, capability,
confidence and uncertainty. Include exact expiry, future capture, edge equality,
edge crossing, wrong plane, moved keyboard, missing independent placement and
phone reuse. Assert specific rejection and zero writes/movements. A handcrafted
fixture cannot close the actual-producer integration gate.

| Producer | Consumer | Current expectation |
|---|---|---|
| Existing v1 | Existing v1 | Existing offline regression behavior |
| Existing v1 | Future v2-only | Explicit rejection; no synthesized evidence |
| Future v2 | Existing v1 | Unknown version rejection |
| Future v2 | Future v2 | Pending joint schema, implementation and gate evidence |

No lane or gate is declared complete by this proposal.
