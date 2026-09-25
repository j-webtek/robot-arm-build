# Offline eye-on-arm calibration foundation

> **Camera architecture notice — 2026-09-05:** This document is no longer the
> Phase 1 calibration route. Phase 1 uses a rigid static overhead camera and the
> selected hardware path is the Arducam B0477 with its included 16 mm lens on
> the source-locked nominal static support. Receipt, installed geometry,
> calibration, and qualification remain open. The eye-on-arm method below is
> preserved for optional Phase 2 research only, never automatic fallback, and
> this foundation has zero authority.

This foundation records and checks offline calibration evidence for the
historical Freeze-009 Waveshare IMX335 5MP USB Camera (B), SKU 26719, on the
bundled moving upper-arm holder. Active Freeze 011 retains that legacy
arm-camera profile under `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`; it is not the
selected Phase-1 B0477 route and is not reinterpreted as static-camera
evidence. This foundation does not access the camera, arm, serial transport,
or motion supervisor.

## Frame equation

Every capture obeys one explicit direction convention:

```text
Wv_T_B = Wv_T_E(q_i) * E_T_C_arm * C_arm_T_B(i)
```

- `Wv` is the vendor URDF world/root frame.
- `E` is the installation-specific carrier frame rigidly attached to `link2`.
- `C_arm` is the installed camera optical frame.
- `B` is the RC03 board frame or the board frame recovered from a registered
  static calibration target.

`E` is deliberately not aliased to `link2`. A real dataset must identify a
measured carrier-registration artifact such as `link2_T_E` (including the
locked rail, holder, fasteners, camera seating, and cable state). A source hash
named `carrier_registration` is mandatory even though the loader cannot decide
whether that external artifact passed commissioning.

## Dataset contract

`rocell.eye_on_arm_dataset.v1` is a strict, content-addressed JSON schema. Each
sample atomically binds:

1. one image sequence, timestamp, dimensions, clock, and image SHA-256;
2. one synchronized six-joint state in the pinned RoArm-M3-Pro joint order;
3. the corresponding `Wv_T_E` carrier pose and referenced joint sequence; and
4. the corresponding `C_arm_T_B` target pose and referenced image sequence.

The loader rejects duplicate or unknown JSON fields, nonfinite numbers,
incorrect transform directions, reordered/missing joints, reused image hashes,
non-monotonic sequences or timestamps, insufficient target observations,
unsettled captures, and frame/joint timing beyond the declared bound. Dataset
objects, nested samples, joint maps, and source hashes are immutable.

Required source hashes bind the frame contract, camera manifest, camera
intrinsics, carrier registration, carrier kinematic model, measured tag map,
and robot reference. Loading can additionally require the exact dataset-file
hash and exact source-hash map.

Only settled stop-and-look capture is currently supported. Evidence kind is
not a descriptive label that callers may self-assert:

- `SYNTHETIC` requires `synthetic_exact` timing plus `synthetic_truth` carrier
  and target records.
- `OFFLINE_CAPTURE` requires `device_exposure` timing, `offline_fk` carrier
  poses, and `apriltag_bundle` direct-board detections. Synthetic records and
  host-receipt-only timing are rejected.

The report's `exposure_synchronized` boolean means only that this internal
kind/source/timestamp contract was coherent. It does not independently verify
the camera clock, exposure metadata, raw feedback bracket, or synchronization
qualification evidence and cannot pass physical acceptance.

The v1 pose is directly `C_arm_T_B`. `charuco` is therefore forbidden here:
ChArUco observes a separate fixture frame and first needs a typed, measured,
hashed `B_T_F` registration contract. Synthetic exact timestamps exercise
software only and do not qualify physical calibration.

The held-out IDs are precommitted inside `validation_split`. The split is part
of the dataset content hash, so a caller cannot repeatedly choose a favorable
validation split after seeing results.

## Numerical solver

Install the isolated dependency with `pip install -e .[calibration]`. NumPy is
loaded lazily only when `solve_eye_on_arm` runs; OpenCV is not imported by this
solver.

```python
from rocell.calibration import load_eye_on_arm_dataset, solve_eye_on_arm

dataset = load_eye_on_arm_dataset(
    "capture.json",
    expected_file_sha256="...64 lowercase hex characters...",
)
result = solve_eye_on_arm(
    dataset,
)
```

The solver reduces pose pairs to `A X = X B`, solves rotation by a Kronecker
null-space system, solves translation by least squares, and estimates the
constant `Wv_T_B` from training poses. At least five training poses and one
explicit held-out pose are required as an algorithmic floor only. Future
physical qualification policy requires at least 15 training and 6 held-out
poses, in addition to observability and quality gates; count alone never passes
qualification.

The safe CLI reads one dataset and writes a deterministic report to stdout. It
does not create or install a calibration artifact:

```powershell
rocell solve-eye-on-arm-offline `
  --dataset .\capture.json `
  --expected-sha256 <exact-file-sha256> `
  --require-diagnostic-pass `
  --json
```

The report includes a canonical semantic `report_hash`, explicit zero hardware
access/command counts, and `artifact_created: false` / `artifact_installed:
false`.

## Raw feedback and pinned FK verification

The byte-preserving pre/exposure/post companion format and its zero-authority
offline verifier are documented separately in
[`EYE_ON_ARM_CAPTURE_BUNDLE.md`](EYE_ON_ARM_CAPTURE_BUNDLE.md).

`rocell.eye_on_arm_capture_evidence.v1` is a separate immutable evidence
package bound to the exact dataset hash, manifest/build IDs, camera USB
identity, camera settings, timing qualification, robot reference, carrier
registration, and kinematic-model hashes. For every sample it preserves the
complete decoded T=1051 field object, its canonical content hash, joint
sequence, timestamp, and clock.

The installed reference is explicit per joint:

```text
q_model_rad = sign * q_feedback_rad + offset_rad
```

`verify_eye_on_arm_fk()` reads the pinned URDF through a bounded byte buffer,
checks its SHA-256 before parsing those same bytes, and additionally requires
the reviewed repository model digest
`a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`.
Dataset/evidence agreement on some other model digest is rejected, so callers
cannot circularly bless a changed joint origin, axis, or limit. The verifier
projects all six raw feedback joints through the installed-reference rules and
recomputes:

```text
Wv_T_E(q_i) = Wv_T_link2(q_i) * link2_T_E
```

It compares both the projected joint vector and recomputed carrier transform
with the dataset record. Missing raw samples, sequence/clock/timestamp drift,
model/source-hash drift, wrong joint mappings, joint-limit violations, and
carrier translation/rotation mismatches fail the hashed FK-verification
report. Report construction independently derives each sample's required
failure reasons from the serialized FK policy, so a caller cannot mark a
threshold-violating metric as passed. Capture evidence and FK indexing are
both capped at 128 raw feedback records. This proves internal reproduction
from the supplied evidence; it does not itself prove that the robot-reference
or `link2_T_E` artifacts were measured correctly.

The offline CLI requires SHA-256 pins for the exact bytes of both inputs,
reloads the canonical verified workspace context, requires the evidence
manifest/build/model identities to match it, and uses that bundle's reviewed
URDF at `software/models/roarm_m3/`:

```powershell
rocell verify-eye-on-arm-fk-offline `
  --dataset .\capture.json `
  --dataset-sha256 <exact-dataset-file-sha256> `
  --evidence .\raw-feedback.json `
  --evidence-sha256 <exact-evidence-file-sha256> `
  --require-pass `
  --json
```

The command emits the verified context identities in its hashed wrapper, zero
hardware access/command counts, creates and installs no artifact, and does not
run the commissioning assessment. A `PASS` proves only that the supplied raw
fields reproduce the supplied dataset under the pinned software model and
policy. It does not turn the registry's unresolved physical prerequisites into
accepted evidence.

The stricter three-file companion verifier additionally binds the exact raw
T=1051 wire lines, JPEG bytes and metadata, normalized detections, and each
pre/exposure/post bracket to that dataset/evidence pair:

```powershell
rocell verify-eye-on-arm-capture-bundle-offline `
  --dataset .\capture.json `
  --dataset-sha256 <exact-dataset-file-sha256> `
  --evidence .\raw-feedback.json `
  --evidence-sha256 <exact-evidence-file-sha256> `
  --bundle .\capture-bundle.json `
  --bundle-sha256 <exact-bundle-file-sha256> `
  --require-pass `
  --json
```

Its pass is structural only. T=1051 has no device measurement timestamp; the
clock-correlation payload is hash-bound but not content-qualified; camera and
artifact identities are not registry-resolved; and the normalized detection is
not the original tag-corner/inlier/covariance output. It cannot commission or
promote a calibration artifact. See
[`EYE_ON_ARM_CAPTURE_BUNDLE.md`](EYE_ON_ARM_CAPTURE_BUNDLE.md) for the byte and
resource contract.

`--require-diagnostic-pass` returns a nonzero configuration status when the
hashed diagnostic policy fails, but still emits the full report. Without that
flag, a diagnostic-fail candidate can still be inspected with process status
zero; it never gains physical authority either way.

Pose count is not treated as observability. The solver reports and gates on:

- carrier rotation-axis rank, maximum relative rotation, and independent
  second-axis RMS excitation;
- rotation null-space separation and fit ratio;
- translation rank and condition number;
- `A X = X B` pair residuals; and
- per-pose training and held-out translation/rotation residuals.

Repeated poses, downstream-only joint changes that leave the `link2` carrier
stationary, exact/near-duplicate carrier poses, train/held-out pose leakage,
single-axis or weak-second-axis carrier motion, deficient translation rank,
badly conditioned solves, excessive sample counts, and excessive pair counts
are rejected before an unbounded solve. File loading is independently capped
at 4 MiB and uses a bounded read, so sample/pair gates are not preceded by an
unbounded JSON allocation.

Every numerical/resource/observability/diagnostic threshold is held in a
frozen `EyeOnArmSolverPolicy` and serialized into the report hash. The default
policy also classifies training, held-out, relative-motion, and rotation-fit
limits. Inconsistent data produces a
`DIAGNOSTIC_FAIL_CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY` result rather
than a passing candidate.

## Authority and remaining work

Every result is either a diagnostic-pass or diagnostic-fail
`CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY` and has
`physical_release_effect: NONE`. `to_nominal_artifact()` can store the report as
an immutable `NOMINAL_ONLY` calibration artifact. It cannot produce `VALID`,
install itself, enable motion, or satisfy contact preflight.

`assess_eye_on_arm_commissioning()` is currently a fail-closed readiness
boundary, not a promotion gate. It checks an `OFFLINE_CAPTURE`, the 15/6
precommitted split, the reviewed model pin, exact FK sample coverage, exact
solver source/split/count bindings, deterministic solver-report reproduction,
stricter residual limits, and exact prerequisite assessment hashes for the
camera, target, robot reference, carrier, model, settings, and timing claims.
It rejects a generic caller-created `VALID` `CalibrationArtifact` as proof of
independent validation.

Every current assessment returns `EVIDENCE_GATE_BLOCKED`. This is deliberate:
the repository does not yet have content-verifying registry adapters for all
typed physical artifacts, a verified active-context provider, a qualified
clock-correlation source, raw AprilTag corner/inlier evidence, integration of
the structural capture bundle into a physical boundary, or a typed independent
physical-validation report. Mutually consistent caller-authored hashes
therefore cannot become a commissioning pass. The assessment creates and
installs nothing and cannot authorize power, motion, or contact.

Before a physical extrinsic can be accepted, a separate typed commissioning
boundary still needs:

- received camera USB identity and locked capture mode/settings;
- measured camera intrinsics and distortion at that exact mode;
- measured `link2_T_E`/holder/camera installation registration;
- a measured target registered to `B` and an independently checked tag map;
- validated joint signs, zeros, FK, and exposure-time joint synchronization;
- diverse physical poses with independent held-out trials;
- controlled outlier handling, covariance/uncertainty, and released numerical
  acceptance thresholds; and
- post-solve validation after reseating, cable changes, impacts, or fastener
  changes.

Several physical-acceptance blockers remain outside this foundation and are
also emitted as executable failed checks by the readiness assessment:

- the supplied joint signs/offsets and `link2_T_E` still require controlled
  physical measurement and independent acceptance;
- the companion capture bundle now retains exact T=1051 lines, JPEGs, and a
  structural pre/exposure/post bracket, but T=1051 carries no device timestamp
  and the recorder-projected clock correlation is not yet content-qualified;
- normalized target-pose bytes are retained, but raw AprilTag IDs, corners,
  inliers, covariance, and detector logs are not yet modeled;
- a separate calibration fixture still requires explicit measured
  `B_T_F`/`F_T_B` rather than relabeling its observation as `C_arm_T_B`;
- the physical holder/bracket/rail, fastener witness, camera seating, and cable
  route still need controlled qualification; and
- the pinned M3 kinematic projection is not by itself a received-unit Pro
  metrology model or a validated `R_ctrl` controller correlation.

Source hashes, successful FK reproduction, and diagnostic consistency do not
substitute for those controls.

The deterministic unit fixtures cover exact recovery, held-out translation
error reporting, duplicate/source-hash integrity, timing failure, target
occlusion, missing carrier registration, repeated/downstream-only motion, and
optional-dependency failure. Adversarial fixtures also cover evidence-kind
relabeling, split/policy hash changes, pair/sample exhaustion, cross-split
duplicates, weak second-axis motion, and diagnostic-fail CLI behavior. They are
synthetic algorithm tests, not evidence about the actual arm or camera.

The pinned-FK fixture additionally uses the repository's exact reviewed RoArm
URDF,
21 base/shoulder-diverse poses, a nonidentity `link2_T_E`, complete raw T=1051
joint fields, and a 15/6 split. Tests recover the known transform, detect raw
joint/carrier/model drift (including a colluding changed-model hash), validate
evidence/report serialization, detect omitted samples and forged solver source
maps, and prove that generic self-asserted `VALID` artifacts cannot unblock
commissioning.
