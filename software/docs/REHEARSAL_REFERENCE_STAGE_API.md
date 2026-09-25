# Stage-13 nominal reference evidence API

This is a hardware-incapable rehearsal implementation, not installed calibration
or permission to move the arm. It implements the bounded slice in
[the reference-frame audit](WIZARD_REFERENCE_FRAME_NEXT_SLICE.md) and is joined to
the wizard by [the integration contract](WIZARD_REFERENCE_INTEGRATION.md).

## Public interface

Module: `rocell.application.rehearsal_reference_stage`.

```python
source_context = read_reference_source_context(workspace)

# The integration layer creates this immutable typed binding from audited M1
# predecessors and canonical source_context bytes, never browser-supplied hashes.
evidence = evaluate_rehearsal_reference_stage(workspace, binding)

verified = verify_rehearsal_reference_evidence(
    evidence.canonical_bytes(),
    expected_binding=binding,
    expected_evidence_sha256=trusted_retained_evidence_sha256,
    expected_evaluator_source_sha256=trusted_reference_module_sha256,
)
```

`binding` must be the exact `RehearsalReferenceBinding` type. The binding module
owns the reviewed stage-7, stage-8 and stage-12 predecessor trios, camera receipt,
distinct serial/campaign/controller hashes, independent synthetic final-power
observation hash, and immutable source snapshot. These values are dependencies,
not calibrated joints or newly measured correspondences. The integration layer
must audit the original records and review relationships before invoking this
module; a hash supplied by an untrusted caller is not authentication.

`RehearsalReferenceEvidence` stores canonical immutable bytes and exposes
`canonical_bytes()`, `to_dict()`, `evidence_sha256`, `evaluation_sha256`, `checks`
and `outcome`. Dictionaries returned by `to_dict()` are detached. Its constructor
checks bounded canonical encoding, but is not a substitute for the complete
required-hash verifier. Neither API publishes a calibration artifact, M1 receipt,
permit or stage PASS. The wizard separately retains, assesses and reviews it.

The evaluator hash identifies this module alone. The report additionally records
source hashes for the graph, registry, artifact, URDF, transform and fitter
modules. Those dependency hashes remain inside the externally trusted full
workspace/evidence binding; pure verification does not open their files.

## Calculations actually performed

The source reader loads and revalidates `SimulationContext`, verifies the pinned
URDF, and preserves the exact 2,849-byte XML snapshot. It captures the nominal
board/world overlay, virtual tool offset, typed ready-joint vector, declared
fixture offsets, board dimensions and the two source-selected targets. The
historical frozen context and additive static-camera source hashes remain
distinct. Evaluation refuses a source snapshot that differs from a fresh read.

The closed evaluator then performs:

1. The actual static Phase-1 registry rehearsal: 15 `NOMINAL_ONLY` artifacts,
   both complete 12-entry device closures, and 27 parent plus 41 context-edge
   invalidations. The complete original report is retained verbatim, including
   actual physical-registry assessments. It never installs an artifact.
2. Actual URDF forward kinematics for six explicit nominal joint states. Four
   poses are training inputs and two are held out. Millimetres and typed radians
   are explicit; the gripper joint is supplied and validated too. The chain is
   `board_T_world × world_T_hand_tcp(q) × hand_tcp_T_nominal_tip`.
3. Actual rigid-correspondence fitting from world-tip to board-tip coordinates.
   The target points are generated using the assumed board/world transform, so
   agreement checks implementation mathematics, not physical accuracy. Complete
   training/held-out inputs, spectral certificates, candidate transform,
   observability, policy, residual vectors and summaries are retained.
4. A second actual fit with the same training data and a 10-mm offset applied
   only to one held-out target. It must report the two held-out residual failures
   without changing the fitted training transform. Expected-fault checks cannot
   compensate for a failed nominal fit.
5. Actual geometry refusals for a reflected rotation, disconnected frame chain
   and millimetres supplied to a revolute joint. Complete closed inputs and the
   observed error type/message are retained. An unexpectedly accepted input can
   be retained coherently as `BLOCKED`, never relabeled a successful refusal.
6. Coordinate inverse/forward round trips for keyboard `A` and phone `key_q`.
   These cover one of 46 keyboard targets and one of 29 phone targets. They are
   not an IK solve, reachable-pose proof, route, collision screen, all-75-target
   campaign or sensitivity qualification.

The default actual fixture produced training RMS `6.55e-14 mm`, held-out RMS
`8.04e-14 mm`, and maximum frame/target round-trip error `1.42e-14 mm`. These are
floating-point residuals of truth-known nominal inputs, **not measured robot
precision or an achievable physical typing tolerance**.

## Retained verification and failure behavior

Verification performs no filesystem/device access, registry assessment, graph
rehearsal, `forward_kinematics`, correspondence fit, NumPy import or provider
dispatch. It checks exact canonical schema, source/session/predecessor binding,
expected evaluator/evidence hashes and non-authority fields. It then:

- Reconstructs nominal artifact identities and checks every retained graph edge,
  physical-assessment projection, closure hash and derived disposition.
- Parses the retained, source-pinned XML and independently composes local joint
  equations to validate the reported FK matrices and round trips. It does not
  invoke the FK evaluator entry point or consume controller feedback as joints.
- Uses the fitter's pure verifier to check its retained spectral certificates,
  least-squares solution, exact input splits and every reported residual.
- Derives the nine compact checks and summary again from that verified evidence.

Malformed or contradictory evidence raises `RehearsalReferenceError`. A coherent
failed expected-refusal or edge-detection result stays inspectable as `BLOCKED`.
Nominal graph baseline, nominal numerical acceptance and expected negatives are
classified independently. No failure causes a retry, hardware operation or
automatic calibration promotion.

## Sizes and publication

The initial complete fixture is **102,471 canonical bytes**. Its measured major
sections are the graph report 66,851 bytes; frame-chain report 6,832 bytes;
nominal fit 6,818 bytes; held-out fault fit 6,842 bytes; and refusal inputs/results
890 bytes. The canonical source snapshot is 5,893 bytes and is retained within
the full dependency binding.

The original 96-KiB design target was insufficient for this full evidence. This
new schema therefore has an explicit **112-KiB evaluator cap (114,688 bytes)**,
leaving 12,217 bytes above the measured fixture. The existing **128-KiB M1 outer
receipt limit is unchanged**: the bare fixture leaves 28,601 bytes for its outer
wrapper, and a maximum-sized allowed evaluator still leaves 16 KiB. The fixture
cardinality is fixed; these margins do not authorize more poses or reports.

No graph deduplication, compression, truncation, summary-only digest or omission
is used. The complete graph and both numerical reports remain readable JSON.
The integration layer also checks the actual outer service receipt and public
operation envelope against their unchanged limits and diagnostic sanitizer;
export verification must preserve the full report rather than silently trim it.

The compact `reference_summary` contains graph counts, finite numerical metrics,
exact per-device subset coverage, a direct `claim` field, eight physical-pending
IDs and explicit camera/controller input roles. The UI does not render the full
technical reports by default. The full evaluator hash is added by the outer
projection, avoiding a self-referential hash inside the evaluator payload.

## Physical requirements that remain pending

All eight canonical components remain pending even after rehearsal PASS:

- Bootstrap phase receipt.
- Reference-characterization phase receipt.
- Measured arm-to-board transform.
- Controller-model correlation.
- Free-state tool TCP.
- Keyboard target map.
- Phone target map.
- Outcome-observer candidates.

The broader graph includes future contact-dependent TCP and qualification nodes;
their physical closure is not demanded as a stage-13 noncontact rehearsal
predicate. Source ready pose, URDF world, controller frame, startup middle and
safe park are not interchangeable. Reviewed camera stages are dependency-only
in this numerical fixture; their capture pixels are not silently reused as the
correspondence observations. The separately verified T105 exchange remains
transport evidence, not calibrated joint truth. Synthetic final power is not a
measurement of received hardware.

## Focused verification

`tests/unit/test_rehearsal_reference_stage.py`: 68 tests passed. Combined with the
existing graph and new rigid fitter suites: 148 tests passed in 2.02 seconds.
Formatting and module type checking passed. Tests include full-report retention,
immutable/deep-detached evidence, pure verification with I/O/evaluator/FK/fit
entry points forbidden, every predecessor/hash domain, numerical tampering with
recomputed hashes, split leakage, missing/duplicate edges, incorrect units,
synthetic-as-physical claims, finite/bounded parsing, expected-fault regression
classification and explicit physical-pending coverage.

These are software/fixture results. Full public wizard progression and original
store reopening are separate integration checks recorded by the parent workflow.
