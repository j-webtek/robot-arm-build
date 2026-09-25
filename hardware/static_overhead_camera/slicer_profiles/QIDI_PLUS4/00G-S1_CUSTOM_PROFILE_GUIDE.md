# 00G-S1 custom process — ABS Rapido, X-Plus 4, 0.4 mm nozzle

Preset name: **RoCell 00G-S1 ABS Rapido Structural 0.20 v1**

Process file: [abs_rapido_00G_S1_structural_v1.process.json](abs_rapido_00G_S1_structural_v1.process.json)

Print plate: [00G-S1_ABS_board_splice_fit_tests.3mf](../../cad/output/plates_3mf/00G-S1_ABS_board_splice_fit_tests.3mf)

## Scope and provenance

This is a separately named copy of the existing camera-frame structural recipe, with selected inherited values explicitly pinned from the installed QIDI Studio X-Plus 4 presets on 2026-09-12. It does not overwrite the original process, generated plate, plate mapping, installed presets, or filament preset.

The original structural recipe's wall_sequence entry is represented here by QIDI Studio's native wall_infill_order field: inner wall/outer wall/infill. This matches the installed inherited default. Top shell thickness remains the parent's 1.0 mm minimum and bottom shell thickness remains 0 mm; seven layers govern both at a fixed 0.20 mm layer height. Selected inherited defaults are pinned, not newly optimized. Other options still inherit from 0.20mm Standard @XPlus4.

The goal is to test the same process intended for structural production parts, not make a special easier-fitting coupon. Keep the same dimensional settings for the later structural parts. This process is not for the precision camera cage or TPU pads.

JSON structure and source-value comparisons were checked locally. Native import, slicing, saving and reopening in QIDI Studio remain to be checked before printing. Digital consistency is not physical fit or load qualification.

## Load and save

1. Select X-Plus 4, 0.4 mm nozzle, standard-flow hardware, and the appropriate textured PEI plate.
2. Keep the existing QIDI ABS Rapido filament preset. No temperature, cooling, flow ratio, pressure advance, retraction, or maximum volumetric-flow changes are included here.
3. Import the custom process JSON through QIDI Studio's configuration import.
4. Open the geometry-only 00G-S1 3MF. If asked to use project settings, ensure the custom process remains selected afterward.
5. Confirm FOUR objects: board saddle coupon, small M6 nut retainer, splice coupon, and splice collar. Keep 100% scale and stored orientation/placement; do not auto-arrange.
6. Enable Advanced settings and compare the tabs below.
7. Slice, inspect the small retainer and all holes/channels layer by layer, then save a separate native project as 00G-S1_QIDI_native_custom_v01.3mf. Do not overwrite the supplied geometry plate.
8. Reopen that native project and verify the process, filament, four objects, scale, and preview remain intact. Read time and material estimates from this slice; no estimate has been established for this custom project yet.

## Quality

| Setting | Value |
|---|---|
| Layer height | 0.20 mm |
| Initial layer height | 0.20 mm |
| Adaptive layer height | Off |
| Default line width | 0.42 mm |
| Initial layer line width | 0.50 mm |
| Outer wall line width | 0.42 mm |
| Inner wall line width | 0.45 mm |
| Top surface line width | 0.42 mm |
| Sparse infill line width | 0.45 mm |
| Internal solid infill line width | 0.42 mm |
| Wall generator | Classic |
| Wall/infill order | Inner wall → outer wall → infill |
| Seam position | Aligned |
| XY hole compensation | 0.00 mm |
| XY contour compensation | 0.00 mm |
| Elephant-foot compensation | 0.15 mm |
| Resolution | 0.012 mm |
| Arc fitting | On |
| Ironing | Off |

Leave scarf-seam and other unlisted quality settings at their inherited values. Do not use XY compensation or model scaling to rescue a failed fit. Keep the same seam behavior for coupons and production parts.

## Strength

| Setting | Value |
|---|---|
| Wall loops | 6 |
| Embed wall into infill | Off |
| Detect thin wall | Off |
| Top surface pattern | Monotonic line |
| Top surface density | 100% |
| Top shell layers | 7 |
| Top shell minimum thickness | 1.0 mm; seven 0.20 mm layers give 1.4 mm on a full flat shell |
| Top paint penetration layers | 5; irrelevant for this single-color job |
| Bottom surface pattern | Monotonic |
| Bottom surface density | 100% |
| Bottom shell layers | 7 |
| Bottom shell minimum thickness | 0 mm; layer count still supplies the bottom shell |
| Bottom paint penetration layers | 3; irrelevant for this single-color job |
| Internal solid infill pattern | Rectilinear (JSON value zig-zag) |
| Sparse infill density | 40% |
| Sparse infill pattern | Gyroid |
| Fill multiline | 1 |
| Infill/wall overlap | 15% |
| Infill direction | 45° |
| Minimum sparse infill area | 15 mm² |
| Infill combination | Off |
| Detect floating vertical shells | On |
| Only one wall on top surfaces | On, retained from the existing inherited structural recipe |

Infill anchors, narrow-solid-infill detection and vertical-shell-thickness controls remain inherited. Six walls is the configured wall count; thin geometry and the inherited top-surface single-wall option can alter the number of paths in individual regions. Inspect the slice rather than assuming every section contains six complete loops.

## Speed

All speeds are requested limits; short paths, acceleration, cooling and filament volumetric-flow limits can lower achieved speed.

| Setting | Value |
|---|---|
| Initial layer | 25 mm/s |
| Initial layer infill | 40 mm/s |
| Outer wall | 45 mm/s |
| Inner wall | 90 mm/s |
| Small perimeters | 50% |
| Small-perimeter threshold | 4 mm |
| Sparse infill | 95 mm/s |
| Internal solid infill | 80 mm/s |
| Vertical shell speed | 80% |
| Top surface | 40 mm/s |
| Slow down for overhangs | On |
| Overhang speeds, 10 / 25 / 50 / 75 / 100% | 0 / 50 / 30 / 10 / 10 mm/s |
| Slow down by height | Off |
| Bridge | 25 mm/s |
| Gap infill | 55 mm/s |
| Travel | 400 mm/s |

The zero entry is the inherited special value, not a request for the printer to stop. Leave resonance avoidance and accel_to_decel behavior at their inherited printer/profile settings; this custom file does not retune motion compensation.

### Acceleration

| Setting | Value |
|---|---|
| Normal printing | 3000 mm/s² |
| Travel | 6000 mm/s² |
| Initial layer travel | 2200 mm/s² |
| Initial layer | 400 mm/s² |
| Outer wall | 1200 mm/s² |
| Inner wall | 2000 mm/s² |
| Top surface | 900 mm/s² |
| Sparse infill | 100% of normal printing |

## Support

| Setting | Value |
|---|---|
| Enable support | Off |
| Raft layers | 0 |
| Support type, interfaces, distances | Leave inherited; inactive while supports are off |

Do not fill the nut tunnel or splice interface with generated support. If the supplied orientation produces an unexpected unsupported island or failed bridge in preview, investigate that before printing rather than enabling support globally.

## Others

| Setting | Value |
|---|---|
| Skirt loops | 0 |
| Brim type | Outer only |
| Brim width | 10 mm |
| Brim-object gap | 0.05 mm |
| Prime tower | Off |
| Print sequence | By layer |
| Spiral vase | Off |
| Fuzzy skin | None |
| Reduce infill retraction | Disabled |

Leave slicing mode, timelapse, exclude-objects, purge options and other unlisted controls at inherited settings. Do not add post-processing scripts. A brim joining near neighboring parts is not a reason to auto-arrange the validated layout; check that paths remain in the usable plate area. Remove only the brim after the print has cooled.

## What not to change between this coupon and structural production

Keep layer height, line widths, wall generator/order, seam behavior, shell counts, infill, wall/bridge speeds, dimensional compensation, filament calibration and material consistent. If one changes, do not automatically transfer the coupon's fit result to the changed process. The future holder-precision and TPU-pad jobs have their own prescribed recipes.

Before starting, verify the small nut retainer is complete in layer preview, the channels are open, no support is generated, and the entire brim fits the build area. After cooling, continue with the [physical coupon checks and assembly guide](../../PRINTABLE_FRAME_BUILD_GUIDE.md).

