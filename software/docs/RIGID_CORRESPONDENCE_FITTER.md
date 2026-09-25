# Offline rigid point-correspondence fitter

`rocell.calibration.rigid_correspondence` is a mathematical component for
stage-13 development, not a commissioned calibration or an arm command. It has
no file, registry, device or transport API. NumPy is optional and imported only
inside the explicit fit call; nothing is installed automatically.

## Public contract

```python
RigidPointPair(pair_id: str, source: Point3Mm, target: Point3Mm)

RigidCorrespondenceInput(
    dataset_id: str,
    source_frame: str,
    target_frame: str,
    training: tuple[RigidPointPair, ...],
    held_out: tuple[RigidPointPair, ...],
    workspace_source_sha256: str,
    binding_sha256: str,
    origin: CorrespondenceOrigin,
    units: str = "mm",
)

fit_rigid_correspondence(
    data: RigidCorrespondenceInput,
    *, policy=DEFAULT_RIGID_CORRESPONDENCE_POLICY,
) -> RigidCorrespondenceResult

verify_rigid_correspondence_result(
    payload: bytes,
    *,
    expected_input: RigidCorrespondenceInput,
    expected_policy: RigidCorrespondencePolicy,
    expected_evidence_sha256: str,
) -> RigidCorrespondenceResult
```

`CorrespondenceOrigin` admits `SYNTHETIC_REHEARSAL_ONLY` or
`UNVERIFIED_SUPPLIED_OBSERVATIONS`. Neither implies hardware qualification.
The input exposes `to_dict()` and `input_sha256`; the policy exposes `to_dict()`
and `policy_sha256`. Both are immutable exact typed contracts. The workspace and
binding hashes are caller-supplied context labels; the fitter does not read the
workspace or establish their measurement provenance.

The result exposes `candidate_transform: RigidTransform`, `diagnostic_pass`,
`diagnostic_failures`, `to_dict()`, `canonical_bytes()` and `report_sha256`.
Dictionary projections are independent copies; the retained canonical bytes are
immutable. There is no `install`, `promote`, physical permit or transport method.

## Direction, numerical method and limits

The fitted transform is **target_T_source**: target-frame coordinates equal
`R * source_coordinates + t`. All point/translation values are millimetres.
Frames must be distinct bounded identifiers and match every point exactly.
Changing the direction requires explicitly swapping both frames and pairs; no
implicit frame aliasing or unit conversion occurs.

Training pairs alone determine centroids and the cross-covariance matrix.
Kabsch/SVD yields a least-squares rotation with determinant +1 and a translation.
Scale, shear, reflection and per-point adjustments are not fitting parameters.
Held-out pairs are evaluated only after fitting; their coordinates never affect
the centroids, singular vectors or candidate transform.

Hard bounds are 128 total pairs, 1,000,000 mm absolute point coordinates and
262,144 bytes of complete canonical evidence. At least three training pairs and
one held-out pair are required. IDs cannot repeat within or across partitions;
source or target positions that repeat within the separation threshold are
rejected even with different IDs. Only explicit immutable tuples are admitted.

Default numerical policy:

- Minimum point separation: 0.000001 mm.
- Relative numerical rank threshold: 0.000000001; training source, target and
  cross-covariance must each have rank at least two.
- Minimum second-axis RMS spread: 0.1 mm; maximum in-plane condition: 10,000.
- Training RMS/maximum residual limits: 0.5 / 1.0 mm.
- Held-out RMS/maximum residual limits: 0.75 / 1.5 mm.
- Maximum training pair-distance disagreement: 1.0 mm.

These are explicit **diagnostic defaults**, not approved physical acceptance
limits. A supplied policy is fully retained and hashed; fixed work/numerical
ceilings cannot be disabled. No retry, outlier removal or automatic threshold
relaxation takes place.

Noncollinear planar board points are supported. Full-rank reflected
correspondences always fail diagnostic acceptance, even with loose residual
thresholds. A planar set cannot independently distinguish an ambient-space
reflection from an equivalent proper rotation on its plane; the report explicitly
sets `planar_handedness_not_independently_observable`. Additional observations
are needed to establish physical handedness; the fitter cannot manufacture them.

## Results and refusal semantics

The versioned result schema is `rocell.rigid_correspondence_result.v1`. It retains
the complete input and policy, their hashes, candidate transform, numerical
rank/conditioning, spectral certificate, every predicted point and signed
target-frame residual, separate training/held-out summaries, maximum pair-distance
error, diagnostic outcome/reasons and no-authority provenance.

Observable datasets with poor fit or held-out residuals return a complete result
with `DIAGNOSTIC_FAIL_CANDIDATE_ONLY`. In particular, a held-out-only fault must
leave the candidate and training certificate unchanged. Full-rank reflections,
nonrigid pair distances and residual thresholds have distinct reason codes.

Malformed, duplicate, insufficient or degenerate datasets raise
`RigidCorrespondenceError` with a bounded `code`, rather than returning a made-up
transform. Examples include `FRAME_OR_UNIT_MISMATCH`,
`DUPLICATE_ID_OR_SPLIT_LEAKAGE`, `DUPLICATE_GEOMETRY_OR_SPLIT_LEAKAGE` and
`DEGENERATE_TRAINING`. Missing/broken NumPy raises
`RigidCorrespondenceUnavailable`; no alternative fitter is attempted.

Declared units and coordinate bounds cannot establish that measurements were
actually acquired in those units. Similarly, disjoint IDs and geometry cannot
prove untouched acquisition history. External evidence admission must verify
source provenance and precommitted partition membership independently.

## Pure retained verification

The caller must independently supply the expected complete input, policy and
trusted outer evidence hash. A digest taken from the same untrusted payload is
not independent admission evidence.

Verification rejects oversized/noncanonical JSON, duplicate or unknown fields,
nonfinite numbers, type substitutions, altered input/policy and changed result
semantics. It does not import NumPy, read a file or call the fitter.

The retained small singular-vector/value certificate is checked algebraically
against the actual training Gram and cross-covariance matrices, using a fixed
numerical tolerance. Orthonormality, ordered singular values and decomposition
are checked before reconstructing the determinant-corrected proper-rotation
optimum and centroid translation. All predicted coordinates, residuals,
conditioning, thresholds and outcome predicates are independently recalculated
with bounded scalar arithmetic and compared to the complete canonical report.
This verifies numerical consistency within the fixed floating-point tolerance;
it is not a new least-squares solve or a physical measurement certification.

## Stage-13 integration boundary

The service must bind these inputs/results to its audited stage-12 known attempt,
complete retained exchange, approved predecessor receipt/assessment/review,
separate final-power observation and exact stage-7/8 optical dependencies. The
fitter's `binding_sha256` must identify that reviewed context, not a browser value.

This fitter does not prove a received Pro model, firmware, reference procedure,
controller-to-URDF correlation, TCP, power state, static-camera calibration or
safe motion. T105 feedback must not be relabeled as those measurements. Any
numerical PASS remains a candidate-only diagnostic; all physical-authority,
calibration-qualified, hardware-access and registry-write fields stay false.

The analytic six-training/two-held-out test fixture produces a 7,196-byte complete
report in the installed environment. Reports for other datasets vary; callers
must preflight actual retained-byte quotas, never truncate substantive results.

Tests: `software/tests/unit/test_rigid_correspondence.py` covers analytic truth,
planar/minimal excitation, deterministic noise, untouched held-out failure,
scale/shear/reflection, duplicates/degeneracy, frame/unit reversal, policy bounds,
full 128-point budget, immutability, rehashed numerical tampering and verification
with NumPy/fit calls explicitly disabled. All fixtures are offline and incapable
of device access.
