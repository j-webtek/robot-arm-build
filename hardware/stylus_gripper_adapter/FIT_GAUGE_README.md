# Stylus barrel fitting gauges

These two parts help size the pen clamp for the operator's OASO 1010B,
ASIN B08Q7L85X2. They are measuring coupons, not load-bearing holder parts.
They do not establish the Waveshare mounting dimensions.

## Print

- Print `fit_gauges/barrel_gap_gauge_A.stl` and
  `fit_gauges/barrel_gap_gauge_B.stl` flat, engraved labels facing upward.
- Scale: 100%, millimeters. Keep the orientation supplied in the files.
- Suggested starting settings: 0.4 mm nozzle, 0.2 mm layers, four walls and
  solid infill. No supports are required. Use the material and calibrated
  dimensional compensation intended for the final clamp.
- Gauge A is 111 x 36 x 4 mm, with 8.00–10.00 mm gaps. Gauge B is
  116 x 36 x 4 mm, with 10.25–12.00 mm gaps. The range is exploratory; the
  stylus diameter has not been assumed to lie within it.
- Check the preview and overall dimensions in the slicer. Remove brim or
  strings without sanding or enlarging the measuring walls. A distorted print
  or first-layer flare can bias the result; record any fit near the bottom face.

## Use

1. Choose two accessible straight barrel locations where the final clamp could
   grip, away from the cap, tapered nose, disc and stem. Keep the stylus
   stationary; this gauge does not require any arm/gripper movement. If the
   required region is inaccessible, defer that measurement until unloading.
2. Start with a generous slot and move the gauge sideways onto the barrel,
   keeping the pen axis perpendicular to the gauge face. The open mouth avoids
   threading the disc through a hole. Do not use the gauge to lever the pen.
3. Work down to the smallest slot that accepts the barrel with light contact
   and no force. The straight walls near the mouth define the labeled gap;
   there is no need to push against the rounded end.
4. Repeat at the second location and after rotating the gauge 90 degrees
   around the barrel. Record the smallest accepting slot and the next smaller
   rejecting slot. If every slot fits or none fits, report that result so the
   range can be extended.
5. Report those four results, the material, and whether the pen has a clip or
   taper in the grip region. A photo showing the chosen grip region helps
   locate the clamp along the barrel.

Labels are nominal CAD gaps with zero added clearance. They are not certified
diameters; printer error and surface finish affect fit. Use the results to size
a short split-clamp coupon before printing the complete adapter. Do not assume
an open-slot fit guarantees the fit of a circular bore printed in a different
orientation.

## Pen retention in the final holder

The holder will have a removable clamp half secured by screws into captive
metal nuts, with contact distributed over two separated barrel regions.
Screw heads will bear on clamp flanges, not directly on the pen. A small split
depth collar will seat against the holder as a repeatable axial reference and
additional restraint. A verified barrel shoulder can provide a more positive
axial stop if the physical stylus has one in a useful location.

The clamp gap must remain available for tightening before the two halves
bottom out. Bore, liner thickness, clamp gap, wall thickness and fastener
locations will be set after coupon fitting. A round smooth barrel still relies
on clamp friction against rotation; test for twist and axial slip after
assembly. A collar gripping the same smooth barrel also needs a slip check.
No tightening torque or grip-force capability is claimed from this gauge.

The gripper attachment is a separate keyed saddle/keeper design described in
`DESIGN.md`. Secure retention requires both interfaces to pass fitting.

## Regenerate and verify

Run `python hardware/stylus_gripper_adapter/generate_fit_gauges.py` from the
repository root with CadQuery, trimesh, NumPy and matplotlib installed. The
generator exports editable STEP, STL, a mesh-derived top preview and
`fit_gauges/verification.json`. It checks solid validity, nominal throat
clearance, intact slot walls, mesh closure/scale, and STEP reimport. Physical
fit remains to be checked after printing.

Generation note (2026-09-25): the local CadQuery 2.5.2 process completed both
exports and the validation report, then returned exit code 1 without a
traceback. A separate process without CadQuery reloaded both STLs, confirmed
closed single-solid meshes and expected extents, and checked all four STEP/STL
hashes against the report; that check returned exit code 0. The final preview
was visually inspected. The CAD process exit behavior remains unresolved and
must not be reported as a clean generator exit.
