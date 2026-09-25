# Adaptive prehardware stress and coverage

> **Camera architecture notice — 2026-09-05:** Phase 1 vision is now a rigid
> static overhead camera, and the fixed-overview pipeline is the runtime
> migration target. Moving-camera stress results below are retained as prior or
> optional Phase 2 research; they are not an automatic fallback. The selected
> Phase-1 hardware path is the purchased B0477/16 mm configuration and
> source-locked nominal static support; receipt, installed geometry,
> calibration, and qualification remain open. Every diagnostic remains
> zero-authority.

## Purpose

These diagnostics push the hardware-free RoCell stack beyond one-key smoke
tests while keeping every physical gate closed. They are designed to expose
software defects in camera freshness, correction/replanning, achieved-state
contact, semantic action correlation, transport framing, cleanup, and evidence
integrity before the RoArm-M3-Pro, camera, keyboard, or phone is connected.

They do not validate the actual Waveshare arm, the purchased-pending-receipt
B0477, its installed static support/cable/optics, or the historical optional
IMX335 arm-camera and bundled-holder installation. They also do not validate
controller frames, collision clearance, force, or device activation.

## Evidence tiers

| Diagnostic | What it executes | What a pass means |
|---|---|---|
| `screen-mission-routes` | 75 independent trajectory/IK routes | Every locked target has one accepted synthetic park-to-target-to-park trajectory on the selected overlay. |
| `screen-adaptive-mission-routes` | 75 independent optional Phase-2 moving-camera/contact/outcome sessions | Every target also crosses achieved-joint camera FK, JPEG/tag pose, registration, achieved-FK contact, independent outcome, close, and park. |
| `stress-adaptive-session` | Optional Phase-2 fixed signed/boundary and seeded combined perturbations | In-band offsets converge and over-limit offsets reject before contact exactly as declared. |
| `qualify-prehardware` | Locked integration and fault catalog | The selected quick/standard regression contract passes coherently and retains zero authority. |

None of the four reports sets `physical_ready` or releases a capability.

## Verified software checkpoint — 2026-09-04

The pixel boundary now identifies the planar estimator as
`rocell.planar_apriltag_homography` version `1.1.0` (v1.1). Its consensus
refinement is monotonic: after the unique maximum-support inlier mask is
selected, refits may remove newly exposed outliers but never re-admit a tag
excluded by an earlier mask. This keeps threshold-crossing integer-pixel cases
deterministic and bounded rather than allowing mask oscillation.

The two milestone campaigns intentionally bind different synthetic policies:

- full-catalog adaptive coverage uses a 2.5 mm translation deadband, 0.5 degree
  yaw/tilt deadband, 5 px maximum inlier reprojection RMSE, and at most 128
  executed virtual waypoints in each single-target route; and
- the perturbation campaign uses the stricter 1.5 mm translation, 0.25 degree
  yaw/tilt, and 3 px policy, with the same 128-execution route ceiling.

With estimator v1.1 and the full-catalog policy, the 2026-09-04 adaptive screen
accepted 75/75 target sessions. Its deterministic report SHA-256 is
`232dcdd5c7bb6cb7afb6e4dcac6001797991faa54587dd7e0979e67880d8d4e2`.
The 2026-09-04 estimator-v1.1 perturbation rerun passed all 20/20 declared
outcomes, including four expected safe rejections. Its report SHA-256 is
`9dda1bc28015ee6943d0e5017e16756dd30c6d0530d950a818161c28aa15dd20`.
These thresholds and results characterize a quantized synthetic renderer, not
installed-camera accuracy, physical calibration tolerances, collision
clearance, or permission to move the arm.

## Full 75-target adaptive coverage

`screen-adaptive-mission-routes` obtains the canonical one-to-one semantic
binding for all 46 keyboard and 29 Android targets. For each target it creates
a fresh one-character action plan and a fresh nominal hidden board truth, then
runs a complete independent adaptive session:

```text
park -> transit -> hover -> achieved-joint camera observation
     -> NO_CHANGE -> approach -> achieved-FK contact
     -> independent device outcome -> retract -> transit -> park -> close
```

An early route failure is retained but cannot hide later targets. Reports are
chunked only to bound orchestration/evidence size; chunks are never joined into
one trajectory. The report enforces exact 46/29/75 catalog identity, contiguous
ordinals, unique targets, at most 128 executed virtual waypoints per
single-target child, bounded captures/contacts, final source revalidation,
child-report hashes, and recursive zero authority. Plaintext characters are
replaced by SHA-256 plus codepoint length.

Run it from the workspace root:

```powershell
python -m rocell screen-adaptive-mission-routes --require-all --json
```

This is intentionally multi-minute. Keep the quick qualification profile as
the normal edit loop and use full adaptive coverage at milestone boundaries.

## Deterministic perturbation campaign

`stress-adaptive-session` always includes twelve fixed cases:

- nominal keyboard and phone;
- positive and negative in-band X/Y translations;
- positive and negative in-band yaw;
- positive and negative over-limit translations; and
- positive and negative over-limit yaw.

It then adds 0-16 combined translation/yaw cases. A versioned SHA-256 mapping
derives each value from the signed 64-bit seed, so results do not depend on
Python's process-randomized hash or a platform PRNG. Fixed cases never change
with the seed. Exact transforms enter only the private virtual-truth boundary;
the public report stores their classification and input hash, not coordinates.
This campaign binds the 1.5 mm / 0.25 degree / 3 px synthetic policy and the
128-execution per-case ceiling; it does not inherit the wider full-catalog
coverage thresholds.

```powershell
python -m rocell stress-adaptive-session --seed 20260903 --generated-cases 8 --require-pass --json
```

Expected outcomes are explicit: `COMPLETE_NO_CHANGE`, `COMPLETE_CORRECTED`, or
`REJECT_BEFORE_CONTACT`. A corrected case requires exactly one atomic suffix
installation followed by re-observed `NO_CHANGE`; a rejection must have no
contact. Aggregate execution/capture caps are enforced after every child, and
the locked source set is revalidated at the end.

## Moving-camera fault and cleanup coverage

`AdaptiveCameraFaultSchedule` selects faults only by one-based capture
sequence. It cannot inspect device, target, action, or expected output. The
schedule and each fault are content-addressed and consumed exactly once.

Adaptive integration tests cover:

- camera unavailable;
- tag loss;
- excess blur;
- excess noise;
- unqualified timestamp; and
- stale frame.

Every case must stop before contact and close the arm. A second-capture fault
after a successful correction additionally proves that the atomically
installed queue cannot proceed after corrected-hover vision fails. Unexpected
exceptions at the arm, camera, detector/estimator, correction, contact, or
outcome boundary are converted to stable fail-stop evidence; untrusted
exception detail is not serialized.

Corrected multi-action tests cover repeated keyboard keys, keyboard `test`, and
Android `test.`. They assert that action index, semantic target, achieved
feedback, contact geometry, device result, and observer order remain correlated
after one old suffix is discarded.

## Independent adversarial checks

The surrounding test suite deliberately uses checks outside the production
algorithm where practical:

- an ElementTree/plain-matrix FK oracle reparses the pinned URDF and compares
  128 deterministic joint samples without calling production FK math;
- independently rendered AprilTags are rotated and projected in perspective,
  then degraded by blur, glare, low contrast, deterministic pixel noise, and
  border clipping; a degraded tag may reject but may not become a wrong
  accepted identity;
- ESP HTTP freshness checks require all established sequence/timestamp/ETag
  channels to advance coherently and reject cached, downgraded, contradictory,
  repeated, and nonadjacent replayed frames;
- optional Phase-2 eye-on-arm solve tests inject a large single training
  outlier and swap two
  otherwise valid target poses; both must remain nominal-only diagnostic
  failures; and
- collision primitive/sweep tests remain active, while the real 19-body model
  stays blocked because seven robot bodies lack geometry and six installed
  attachment bodies remain unknown.

These checks reduce shared-code false confidence. They still cannot validate
the vendor URDF against the received arm or synthetic pixels against the final
camera.

## Runtime-port and protocol rehearsal

The transport layer includes an in-memory Waveshare protocol controller for
valid, malformed, truncated, overlong, wrong-type, partial-write, timeout,
disconnect, and reset behavior. Separately, deterministic VIRTUAL and REPLAY
ports implement clock, cancellation, lifecycle, execution, feedback,
observation, opaque contact, outcome, and evidence roles under one runtime ID.

`run_zero_authority_mission_rehearsal` validates the bundle before and after a
bounded mission. It crosses every port in canonical order, validates strictly
increasing/correlated fresh achieved feedback with a nonzero synthetic tracking
deviation, and attempts stop, close, evidence append/finalize, and final
validation even after injected failure. Its report binds step results,
authority, adapter identities, achieved-state digest, and cleanup outcome.

This is the reusable adapter seam for later commissioned implementations. It is
not itself the geometry-rich adaptive typing state machine and provides no
physical adapter or motion permit.

## Automated slow tests

The real campaigns are collected but skipped in the default fast suite:

```powershell
$env:ROCELL_RUN_STANDARD_QUALIFICATION = '1'
python -m pytest tests/integration/test_cli.py -k standard_runs_real_17_case -m slow -q

$env:ROCELL_RUN_ADAPTIVE_CAMPAIGNS = '1'
python -m pytest tests/integration/test_cli.py -k "adaptive_mission_coverage_runs_real or adaptive_perturbation_campaign_runs_real" -m slow -q
```

Both subprocess paths also assert that sentinel `serial` and `cv2` modules are
not imported. Normal `pytest` still collects these tests and reports the
intentional skips.

## What remains for hardware

Before even low-energy physical motion, record and verify the exact arm,
firmware, USB/UART behavior, B0477 persistent identity/mode/settings, installed
static-support pose/extrinsic, mass/CG, cable route, controller-to-URDF
correlation, E-stop, and gravity-safe power-loss behavior. Then replace every
synthetic static-camera calibration/timing, tag-map, TCP/compliance, contact,
target-map, and outcome assumption with versioned measured evidence and
complete the full-body swept collision model. If optional Phase-2 arm vision
is later pursued, its holder transform, timing, and eye-on-arm calibration need
their own separate qualification. Device contact remains a later, separate
release.
