# Grounded saddles v2 — replaces both original S1 saddle files

Print `08A-S1_ABS_left_bench_saddle_GROUNDED_v2.3mf` next. The matching right
replacement is `08B-S1_ABS_right_bench_saddle_GROUNDED_v2.3mf`.
Do not print the earlier WELDED_v1 saddles: topology welding did not fix their
unsupported brace starts. Original files remain available for comparison.

## Changes

- Added two permanent 10 x 30 x 16 mm brace feet, reaching the build plate and
  overlapping the existing base by 4 mm. They stay inside the original overall
  envelope and outside the board footprint. These are NOT removable supports.
- Removed brace intrusion from the upright insertion pocket above the existing
  68 mm-high support ledges. The old model intersected the nominal inserted
  upright; the revised CAD does not.
- M6 clamp channels/stops, M5 hole positions and exterior bearing seats,
  upright ledges, and overall 250 x 190 x 104 mm print dimensions are unchanged.
- The shared CAD generator now applies this correction to both handed saddles.

## Loading and settings

Remove the old saddle object from QIDI and load the new v2 3MF as geometry.
Keep your process and filament selections. Expect one object, 100% scale,
the foot flat on the bed and the receiver opening upward, as supplied.

Use the SAME structural ABS settings already entered: 0.20 mm layers,
0.20 mm first layer, 6 walls, 7 top and bottom layers, 40% gyroid,
supports OFF, 10 mm outer brim, 0.05 mm brim gap. No global scaling or
auto-orientation. Keep the existing ABS filament temperatures and cooling.

Reslice; do not reuse the previous G-code. If a floating-region warning
remains, stop and send the new preview rather than ignoring it or enabling
blanket supports. Inspect the receiver ledge bridges and nut-channel roofs.

## Checks and limits

Both CAD solids and serialized meshes passed validity, watertightness,
single-solid, bounds, and interface checks. Section checks at 0.20 mm and
0.16 mm layer heights with a 0.20 mm first layer found no new unsupported
islands greater than 0.01 mm2. These checks require actual overlap with the
preceding layer, without a support-distance buffer. Nominal upright
interference is zero within the CAD tolerance.

This is not a claim that all overhangs/bridges will print successfully, nor a
native QIDI verification or structural-load certification. Native slicing
and physical assembly/strength checks remain necessary.
