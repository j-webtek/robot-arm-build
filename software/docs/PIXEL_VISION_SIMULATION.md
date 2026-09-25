# Pixel vision simulation

> **Active Freeze 011 camera architecture:** Phase 1 uses the purchased
> Arducam B0477/IMX283 USB 3.0 camera and delivered nominal 16 mm C-mount lens
> as a rigid static overhead eye-to-hand source. The fixed-overview path here
> is its software topology, but all present images, intrinsics, and poses are
> synthetic. Received identity, final support/height, mode/settings, and
> calibration remain open. An arm camera is optional Phase 2 only, never an
> automatic fallback, and this work has zero physical authority.

## Scope and authority

RoCell now has an executable pixel-to-board-pose path for the fixed RC03
overview fixture:

```text
RC03 scene + fixed overview camera + released tag artwork
                            |
                            v
             deterministic grayscale raster renderer
                            |
                            v
             FramePacket containing real JPEG bytes
                            |
                            v
       independent bounded tag36h11 pixel detector
                            |
                            v
        immutable AprilTagDetectionBatch + hashes
                            |
                            v
     normalized planar homography + pinhole decomposition
                            |
                            v
        immutable AprilTagPoseObservation + covariance
                            |
                            v
              camera_overview_optical_T_board
```

This is a hardware-free perception test. It does not open a camera, read robot
feedback, command the RoArm, change a calibration registry, release a physical
gate, or authorize contact. The fixed overview output is not an eye-on-arm
transform and is not converted into a robot-frame correction.

`simulate-session` now runs this chain at every physical action's hover
endpoint. Pixel processing receives only a capture sequence and capture mode;
the returned result is associated with the action/target/waypoint afterward.
A contact cannot proceed unless the normal result passes the fixed-overview
quality policy. Session report schema v3 summarizes the sealed vision ledger,
and manifest schema v2 stores the complete redacted ledger in `vision.json` for
strict verification and deterministic replay.

## Component boundaries

| Stage | Inputs | Output | Independence rule |
| --- | --- | --- | --- |
| Raster renderer | Frozen nominal scene, explicit fixed camera model and transform, released tag artwork, immutable render configuration | `SyntheticRenderedFrame` containing a `FramePacket` | Render output contains no embedded tag IDs, expected corners, or detections |
| JPEG frame | Exact encoded bytes, dimensions, source/host timing, settings hash, freshness fields | Immutable `FramePacket` | Downstream code receives encoded pixels, not renderer geometry |
| Pixel detector | `FramePacket`, immutable detector policy, explicit released tag36h11 codebook | `AprilTagDetectionBatch` | Receives no scene, tag map, planned pose, renderer wrapper, or expected corner input |
| Planar estimator | `AprilTagDetectionBatch`, `PinholeIntrinsics`, immutable `PlanarBoardTagMap`, bounded estimator policy | `AprilTagPoseObservation` | Receives no simulator camera transform, rendered corners, robot state, or planned board pose |

The primary implementations are:

- [`simulation/synthetic_raster.py`](../src/rocell/simulation/synthetic_raster.py);
- [`vision/apriltag_codebook.py`](../src/rocell/vision/apriltag_codebook.py);
- [`vision/pixel_detector.py`](../src/rocell/vision/pixel_detector.py);
- [`vision/detections.py`](../src/rocell/vision/detections.py);
- [`vision/planar_pose_estimator.py`](../src/rocell/vision/planar_pose_estimator.py); and
- [`vision/pose_estimation_records.py`](../src/rocell/vision/pose_estimation_records.py).

Pillow is loaded lazily to render/decode JPEG pixels. Importing RoCell does not
load Pillow, OpenCV, or a camera backend. The detector implements its bounded
candidate extraction, projective sampling, rotation decoding, Hamming policy,
and decision-margin policy without OpenCV. The homography/pose estimator is
standard-library-only.

## Corner convention

Corner identity is semantic and must never be reconstructed by sorting pixel
coordinates.

The released codebook defines the physically marked upright-tag corners as:

| Canonical index | Marked corner |
| ---: | --- |
| 0 | top-left (`TL`) |
| 1 | top-right (`TR`) |
| 2 | bottom-right (`BR`) |
| 3 | bottom-left (`BL`) |

`AprilTagDetection.corners_px` uses
`apriltag_canonical_0_1_2_3`. After decoding tag rotation, the detector returns
the marked `TL, TR, BR, BL` sequence, even when the marked top-left is not the
geometric top-left of the image quadrilateral. Pixel coordinates use `u` right
and `v` down.

`PlanarBoardTag.corners_board_mm` must contain the corresponding physical tag
corners in exactly the same indices and in one explicit board frame. The
estimator pairs index 0 with index 0 through index 3 with index 3. It does not
sort by image `x/y`, polygon winding, tag centre, or board coordinates. Both
pixel and board records reject duplicate, crossed, or degenerate corner lists.

This convention is tested for all four 90-degree decoded rotations and for a
perspective quadrilateral.

## Board plane and transform direction

The estimator preserves the exact optical frame declared by
`PinholeIntrinsics.camera_frame`. For the current fixture the output is:

```text
camera_overview_optical_T_board
```

The transform maps board-frame coordinates into the fixed overview camera's
optical frame. A future arm-mounted input may use another explicit optical
frame, but the estimator neither aliases nor normalizes that name.

RC03 tag faces lie on one explicit plane slightly above the board origin. The
immutable map therefore contains `tag_plane_z_board_mm`; every mapped corner is
frame-checked and required to have that same Z within a strict coplanarity
tolerance. Homography decomposition initially obtains translation to the tag
plane. The estimator converts that to the board origin using the recovered
board normal `r3`:

```text
t_board = t_plane - r3 * tag_plane_z_board_mm
```

For the current 0.3 mm test plane and fixed overview orientation, omitting this
step would report approximately 499.7 mm rather than the fixture's 500 mm board
origin depth.

The output does **not** establish physical `B_T_Wv`, `board_T_base_link`,
`Wv_T_C_overhead_optical`, controller `R_ctrl`, or any robot/camera
correlation. It also says nothing about an optional Phase-2
`holder_T_C_arm`/`E_T_Carm` chain.

## Homography, consensus, and pose result

Accepted, mapped detector corners supply board-XY/pixel correspondences. The
current estimator is `rocell.planar_apriltag_homography` version `1.1.0`
(v1.1). It normalizes both domains, forms a bounded eight-unknown homography
system, and solves its normal equations with deterministic partial pivoting.
It rejects insufficient spread, rank loss, a singular scale, and a relatively
degenerate homography.

The board-to-pixel homography is decomposed with the exact pinhole matrix.
Decomposition checks:

- basis scale agreement;
- basis orthogonality;
- a right-handed orthonormal rotation;
- minimum non-grazing board-normal component;
- positive minimum camera depth for every evaluated map point; and
- bounded translation magnitude.

Outlier handling is deterministic and bounded. Each tag supplies one minimal
hypothesis; all-tag and leave-one-tag-out hypotheses are also evaluated within
the fixed resource ceiling. Candidate poses are scored by tag-level
reprojection RMSE. Equal-support candidates with different inlier masks are
rejected as ambiguous rather than selected arbitrarily. The chosen mask is
refit until it converges or reaches the configured round bound. Refinement is
monotonic: each refit intersects with the current mask, so it may remove a
newly exposed outlier but never re-admits a previously excluded tag. This
conservative rule prevents integer-pixel threshold crossings from oscillating
between masks.

`AprilTagPoseObservation` covers every detector record exactly once. A tag may
be:

- an inlier with a finite reprojection residual;
- a pose outlier with its residual and rejection reason;
- detector-rejected; or
- absent from the board map.

The observation also carries a deterministic diagonal 6x6 diagnostic
covariance in `(tx_mm, ty_mm, tz_mm, rx_rad, ry_rad, rz_rad)` order. It is a
first-order software diagnostic bound to the estimator configuration, not a
measured physical covariance model.

## Content and provenance hashes

The chain binds the following independently:

- render configuration, source bundle, controlled artwork, renderer
  implementation, and complete renderer definition;
- exact JPEG bytes, frame settings, resolution, freshness, source timing, and
  host timing;
- detector configuration, released codebook, detector implementation, and
  canonical detection-batch content;
- intrinsic source artifact and normalized pinhole values;
- tag-map source artifact, board frame, tag-plane Z, and every canonical board
  corner;
- estimator policy and exact implementation bytes; and
- the complete pose observation, diagnostics, covariance, and source hashes.

Renderer provenance deliberately redacts selected occlusion IDs from its
serialized output, and carries no detection truth. The detector and estimator
recompute their results from their declared inputs. Every typed detection and
pose record declares exactly zero physical authority:

```text
physical_authority: NONE
physical_commands_generated: 0
can_authorize_motion: false
can_release_physical_gates: false
```

Changing a hash or producing a low residual cannot promote a calibration or
authorize motion.

## Fixed-overview checkpoint

The current simulation fixture is intentionally easy to inspect:

- six released RC03 tag36h11 IDs: 0 through 5;
- nominal RC03 scene and controlled tag artwork;
- a fixed `camera_overview_optical` pinhole view;
- fixture rotation `diag(1, -1, -1)`; and
- board-origin translation `(-305, 228.5, 500) mm`.

In the combined renderer-to-estimator development check, the detector recovered
all six IDs from the JPEG and the estimator produced approximately:

- 0.7063 px inlier reprojection RMSE; and
- 0.268 mm translation error relative to the fixed fixture.

Separate exact-corner tests recover the fixture transform to numerical
precision, explicitly verify the 0.3 mm tag-plane correction, and reject a
65 px tag outlier while retaining the consistent tags.

These numbers characterize one deterministic synthetic fixture. They are not
accuracy specifications for the purchased B0477, its delivered 16 mm lens, a
physical static support, printed tags, the placemat installation, or robot
operation.

## Quality and fault cases

The current test surfaces cover the following cases:

| Boundary | Passing/diagnostic cases | Fail-closed or rejection cases |
| --- | --- | --- |
| Renderer | Deterministic JPEG bytes, all six encoded patterns, marked orientation, hashed sequence/provenance | Missing optional Pillow backend, frame-direction mismatch, unknown occlusion ID, JPEG/resource overflow, source/artwork mismatch |
| Pixel change | Pixel-level tag occlusion changes JPEG and configuration hashes | Occluded tag is absent from independent detector output; no truth ID is passed to the detector |
| Decoder | Valid grayscale JPEG with exact metadata dimensions | Structurally JPEG-like but undecodable bytes, metadata/decoded-size mismatch, byte/pixel limits |
| Candidate detector | All released tags, four rotations, perspective warp, bounded Hamming acceptance | Blank image, excessive dark-pixel fraction, component/run/hull/candidate resource limits |
| Decode policy | Hamming-0, configured Hamming-1, decision margin evidence | Hamming-policy and low-margin candidates carry explicit rejection reasons |
| Map/input | Exact frames, resolution, canonical corners, coplanar tag plane, immutable source hashes | Resolution mismatch, unknown tags, detector rejection, duplicate IDs/corners, crossed quad, wrong frame, off-plane corner |
| Homography/pose | Multi-tag consensus, deterministic refit, per-tag residuals, explicit optical frame | Insufficient tags, rank/scale/determinant degeneracy, basis mismatch, grazing plane, non-positive depth, unbounded translation |
| Robustness | One large tag outlier rejected while a larger consistent set survives | Equal-support incompatible tag sets rejected as ambiguous, hypothesis/refit budget exhaustion |

The session's `CAMERA_UNAVAILABLE` profile stops before a frame exists.
`CAMERA_TAG_LOSS` renders pixels with world tags 0-3 occluded, independently
decodes held-out tags 4-5, then fails naturally because the minimum four-tag
pose gate cannot be met. Normal sessions require world IDs 0-3 and held-out
IDs 4-5 as pose inliers, at most 1.0 px RMSE, at most 1.0 mm fixture-translation
error, and at most 0.1 degree fixture-rotation error. These are synthetic
regression bounds, not physical acceptance limits.

Both paths are available from the normal session entry point as
`--fault-profile camera-unavailable` and `--fault-profile camera-tag-loss`.

## Synthetic fixed overview versus the selected static camera

The fixed fixture is not mounted on the robot, so its topology matches the
selected Phase-1 eye-to-hand architecture. Its pose is constant and does not
depend on joints, but its idealized 500 mm transform, pinhole intrinsics,
pixels, lighting, and timing are synthetic and are not the physical B0477
installation. It exists to force real bytes through independent perception
boundaries while hardware is unavailable.

A separate adaptive simulator reuses this JPEG/detector/planar-estimator
boundary with a view derived from achieved six-joint FK and an explicitly
unmeasured moving-camera fixture. That work is retained as optional Phase-2
research. It does not replace, fall back from, or qualify the Phase-1 static
path. See [arm-camera correction simulation](ARM_CAMERA_CORRECTION_SIMULATION.md).

The selected Phase-1 purchase is the Arducam B0477, supplier-described Sony
IMX283 20 MP USB 3.0 UVC camera in a metal case with a nominal 16 mm manual
focus/aperture C-mount lens. The published `5472 x 3648 @ 9 fps YUY2` native
full-frame mode is only the initial receipt-qualification target. No received
USB identity, delivered lens/case configuration, stable mode/settings,
intrinsics, distortion, usable field of view, support transform, fixed cable/
lighting behavior, timestamp quality, or static eye-to-hand accuracy is
claimed by this simulation. The Waveshare IMX335/bundled-holder route remains
historical Freeze-009 provenance or separately controlled optional Phase 2.

`PinholeIntrinsics` requires corners in an already-undistorted pinhole pixel
space. The current detector does not itself undistort a B0477 frame. A physical
adapter must bind the calibrated image mode and perform or prove the required
pixel transformation before using this estimator.

## Session integration boundary

The current fixed-overview integration now:

- renders a fresh sequence-bound JPEG at every physical action's hover;
- executes the independent detector and planar estimator in `_SessionExecutor`;
- applies the locked synthetic pose-quality policy before approach/contact;
- stores redacted frame provenance, typed detections, typed pose, quality, and
  post-processing action association in a bounded immutable ledger;
- writes that ledger as a separately hashed evidence artifact;
- strictly reconstructs every nested record and redundant hash during package
  verification; and
- recomputes and byte-compares the pixel artifact during session replay.

It deliberately does **not** calculate a correction, change a waypoint, replan
the route, consume a measured static extrinsic, or infer robot pose. The
production-aligned path must use a commissioned
`Wv_T_C_overhead_optical * C_overhead_optical_T_B` registration and separately
qualified `R_ctrl` correlation. No lateral correction should be applied below
the clearance plane, and uncertain contact must never be retried automatically.

## Physical commissioning gaps

Before physical vision can influence an arm route, the project still needs:

1. Record the exact received B0477 serial and persistent USB descriptors,
   delivered IMX283/lens/case configuration, driver, image orientation, and
   stable device ownership. Prove one locked resolution/pixel-format/crop and
   controls after close/reopen and reboot; treat the published native
   `5472 x 3648 @ 9 fps YUY2` mode as an unverified starting target.
2. Positively retain the camera on the final rigid support and qualify its
   height/aim, fasteners, fixed USB cable/strain relief, controlled lighting,
   stiffness, settling, thermal behavior, bump/remove-reinstall repeatability,
   and reference-witness drift. Add all of those bodies to the collision and
   swept-volume model.
3. Measure intrinsics and distortion for the exact lens, focus, aperture,
   mode, crop, orientation, and settings, with varied ChArUco training views,
   held-out residuals, and a defined undistorted pixel output.
4. Measure a content-addressed installed board tag map, then solve and
   independently validate the constant `Wv_T_C_overhead_optical`. A fresh
   `C_overhead_optical_T_B` must be captured for each startup and action
   observation; T0–T3 fit pose and K0/P0 remain held out.
5. Qualify physical detection and pose estimation across scale, angle, blur,
   rolling shutter, exposure, latency, freshness, lighting, glare, occlusion,
   UVC behavior, false-positive inputs, partial tag loss, and held-out
   residual/covariance limits. The bounded local detector is not claimed
   equivalent to the upstream AprilTag implementation.
6. Verify expected device presence, seating, orientation, pose, and the active
   keyboard or phone target map from accepted images. Missing, moved,
   ambiguous, or inconsistent device evidence must block descent.
7. Establish the robot reference and correlate `R_ctrl` independently to `Wv`
   across the usable range. A camera-board pose cannot prove controller signs,
   zeros, limits, or the controller/model bridge.
8. Calibrate both route TCPs/compliance and validate TCP, approach axis, Z, and
   travel with the keyed puck across keyboard and phone regions.
9. Migrate the fixed-view behavior behind the shared observation runtime port;
   accept support-witness, stale-buffer, settings-drift, camera-loss, and
   board/device-movement fault tests plus held-out end-to-end keyboard and phone
   route trials.
10. Accept complete arm/tool/static-support/camera/cable/lighting/device/clamp/
    fixture collision coverage, E-stop, containment, motion/contact permits,
    and operator recovery procedures. Vision quality alone grants none of them.

An optional Phase-2 arm camera would additionally require its own received
identity, carrier/extrinsic, exposure-to-joint synchronization, payload,
moving-cable, collision, and route-visibility qualification. None of those
records can replace a Phase-1 static-camera acceptance item.

## Focused verification

From the workspace root, the component tests are:

```powershell
python -m pytest software/tests/unit/test_synthetic_raster.py
python -m pytest software/tests/unit/test_apriltag_pixel_detector.py
python -m pytest software/tests/unit/test_planar_pose_estimator.py
python -m pytest software/tests/unit/test_vision_records.py
python -m pytest software/tests/unit/test_virtual_pixel_vision.py
python -m pytest software/tests/unit/test_virtual_pixel_vision_deserialization.py
python -m pytest software/tests/unit/test_virtual_session_evidence.py
```

`rocell simulate-session ... --require-pass` now requires this synthetic pixel
chain as part of a complete session. Its PASS remains zero-authority model
evidence and says nothing about the uncommissioned B0477 installation or
physical release gates.
