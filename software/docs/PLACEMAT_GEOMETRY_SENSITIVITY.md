# Placemat geometry sensitivity simulation

## Purpose

This diagnostic answers two different questions without confusing them:

1. Does the software use the current RC03 board, keyboard, phone, and target
   geometry consistently?
2. If the real build differs from those nominal values by an assumed amount,
   could a command aimed at a nominal target centre leave that target's safe
   region?

The first question has a one-case nominal control. The second uses a bounded,
deterministic sensitivity matrix. Neither result is physical calibration,
manufacturing tolerance, safety approval, or permission to power or move the
arm.

## Geometry actually used

The runtime imports and hash-checks the active Freeze-011 manifest, the current
RC03 layout, the nominal target catalog, and the selected static-camera design
sources. The main dimensions are:

| Item | Nominal simulation value | Evidence state |
| --- | --- | --- |
| Board | 610 x 457 x 18 mm | Frozen digital design geometry; physical measurement open |
| Keyboard | origin B=(85, 85) mm; 315 x 147 x 21 mm | Nominal envelope; physical identity, dimensions, placement, and key heights open |
| Phone | origin B=(499.2, 84.2) mm; 77.9 x 164.4 x 7.9 mm | Nominal envelope; physical identity, placement, screen, and UI geometry open |
| Keyboard targets | 46 targets at nominal Z=21 mm | Synthetic ANSI seed, not a measured key map |
| Phone targets | 29 targets at nominal screen Z=11.9 mm | Synthetic Gboard seed, not a screenshot or measured homography |
| Static camera | Arducam B0477/IMX283, centred at B=(305, 228.5), nominal entrance-pupil Z=1000 mm | Purchased catalog configuration and support-screening input; receipt, installation, optics, and calibration open |

The exact source bytes are included in each report through hashes for the
system manifest, simulation bundle, hardware profile, target catalog, alignment
report, scene inputs, static support, and purchased B0477 profile. A stale or
mismatched source fails before analysis.

The B0477 binding proves that this diagnostic belongs to the selected static
overhead architecture. It does not mean the sensitivity calculation uses an
image to measure the devices. Pixel-level B0477 rendering, tag detection, and
planar pose recovery are exercised separately by `rehearse-b0477-stack` and the
integrated V2 mission.

## Error model

For each case, the software keeps the command at the nominal target centre and
perturbs the assumed physical geometry around it. It models:

- board-registration X, Y, Z, and yaw error;
- keyboard and phone placement X, Y, Z, and yaw error independently;
- keyboard and phone local target-map X, Y, and Z error independently; and
- tool-centre-point X, Y, and Z error.

The default illustrative bounds are:

| Assumed source | X | Y | Z | Yaw |
| --- | ---: | ---: | ---: | ---: |
| Board registration | +/-1.0 mm | +/-1.0 mm | +/-0.5 mm | +/-0.2 deg |
| Keyboard placement | +/-1.0 mm | +/-1.0 mm | +/-0.5 mm | +/-0.2 deg |
| Phone placement | +/-1.0 mm | +/-1.0 mm | +/-0.5 mm | +/-0.2 deg |
| Keyboard target map | +/-0.5 mm | +/-0.5 mm | +/-0.5 mm | n/a |
| Phone target map | +/-0.5 mm | +/-0.5 mm | +/-0.5 mm | n/a |
| TCP | +/-0.75 mm | +/-0.75 mm | +/-0.75 mm | n/a |

These numbers are deliberately labelled `ASSUMED_UNMEASURED_SENSITIVITY_BOUNDS`.
They are not predictions of the hardware and must not be copied into physical
acceptance criteria.

The default generator creates 59 unique cases: nominal, signed one-at-a-time
axis cases, and eight combined signed corners for each device. All 75 targets
are evaluated in every case, for 4,425 target/case observations. Each target
records:

- error in the perturbed target's local XY frame;
- remaining or exceeded nominal safe-region margin;
- absolute target-plane/TCP Z separation, without treating it as an accepted
  press depth;
- overlap with another target on the same device;
- target/device-envelope violation; and
- target or displaced whole-device/board-envelope violation. The board-boundary
  class is deliberately conservative: if a sampled placement moves any part of
  the device envelope off the board, every target for that device is marked
  board-boundary-exceeded for that case.

## Commands

Run the default assumed-error study:

```powershell
.\rocell.ps1 stress-placemat-geometry --json
```

Save the complete hash-sealed matrix as JSON:

```powershell
.\rocell.ps1 stress-placemat-geometry --json > placemat-sensitivity.json
```

Run the zero-error control and require every nominal centre to remain inside
its own region:

```powershell
.\rocell.ps1 stress-placemat-geometry --zero-bounds --require-no-gaps --json
```

`--require-no-gaps` intentionally returns nonzero for any sampled result whose
classification is not solely inside its intended region. That includes
safe-region misses, same-device adjacent-target ambiguity, and device/board
boundary findings. Do not use it as a physical release gate. The default
assumed matrix is expected to expose phone-key sensitivity.

## Current deterministic result

With the current source tree and default illustrative bounds:

- 75 targets x 59 cases = 4,425 observations;
- keyboard targets with an observed XY gap: 0 of 46;
- phone targets with an observed XY gap: 27 of 29;
- worst sampled keyboard safe-region margin: +2.7525 mm;
- worst sampled phone safe-region margin: -0.7560 mm; and
- report SHA-256:
  `0ca40102d6bfb8efb53447ba9782fba75a7cf81659ad6bfd0e91ecc7914b1186`.

The zero-error control evaluates 75 observations with no gap and report
SHA-256
`16b55c2c71d771f6f10a1a7bc5603dd1d4782ed00577fbb9dd137f5efa1674a9`.

The conclusion is narrow: the digital target pipeline is internally aligned,
while small phone targets are much more sensitive to plausible combined
geometric error than the keyboard targets. The result does not establish that
the real keyboard will pass or that the real phone will fail, because the
bounds and targets are not measurements.

## What still needs hardware

After the parts arrive, replace assumptions with versioned evidence rather
than editing nominal constants in place:

1. Measure the finished board and installed device locator geometry.
2. Record exact keyboard and phone identity, dimensions, orientation, and
   repeatable placement.
3. Calibrate the B0477 persistent identity, native mode/settings, intrinsics,
   distortion, and retained static camera-to-board transform.
4. Survey the installed AprilTag map and held-out station tags.
5. Calibrate board-to-arm/controller registration and each installed TCP.
6. Measure keyboard key centres/heights and phone screen/UI target polygons.
7. Derive an uncertainty budget from repeated held-out observations and tool
   contacts.
8. Re-run this style of target-region analysis against measured artifacts,
   then qualify collision, compliance, force/travel, outcome observation, and
   supervised physical contact through their separate gates.

Until those steps pass, this command always reports zero camera frames, zero
arm commands, zero contact commands, and no physical release effect.
