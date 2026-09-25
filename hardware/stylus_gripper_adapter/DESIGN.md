# RoArm-M3 stylus adapter

Design proposal, 2026-09-25. Dimensions and physical fit are not yet verified.
This is a mechanical design task; no additional gripper or arm command is
part of it. The last loading result is one verified close step, with stylus
retention still unconfirmed by the operator.

## Selected direction

Develop a compact holder with two independent interfaces:

1. A keyed saddle mechanically captured on one verified fixed gripper/hand
   plate. Locate against plate edges or a confirmed mounting pattern so that
   twisting and axial pull are resisted by geometry. Use a removable keeper
   and screws; do not rely solely on servo squeeze. Existing holes may be used
   only after confirming their dimensions and that they are available mounting
   holes. Do not remove pivot, bearing, or servo fasteners to attach the holder.
2. A two-piece barrel clamp with two spaced support regions and distributed
   contact around the stylus. Tighten the clamp with screws and captive nuts,
   with provision for a replaceable thin liner if needed. Select screw size and
   wall thickness after measuring the available envelope. A removable split
   depth collar seats against the holder to repeat the insertion depth. If the
   stylus has a suitable physical shoulder, investigate capturing it instead.

Keep the stylus near the hand axis and its exposed length short enough to
reduce bending, while preserving jaw, disc, cable and keyboard clearance.
The clamp must engage the straight barrel rather than its cap, clip, disc or
articulating stem. Provide access for changing the stylus without moving the
entire holder. Inspect whether the selected stylus needs electrical contact
through its barrel before covering that surface for later touchscreen use.

The saddle must not rigidly bridge two independently moving jaws. Its actual
attachment surface remains a CAD/measurement decision: if no suitable fixed
plate exists, revise the mount explicitly rather than assuming a hole pattern.
Check the full gripper travel against the adapter, screws and stylus even if
normal operation leaves the gripper stationary. Mechanical retention of the
stylus does not support the arm if joint power is lost.

## Existing parts to reuse selectively

The existing `active-project/RoCell_v0_3/scripts/generate_cad.py` includes:

- `compliant_tool_body`: 28 x 24 x 65 mm nominal body with gripper recesses,
  sliding guide, spring chamber and screwed cap.
- `stylus_collar`: a split collar for a nominal 9 mm barrel, relying on fitted
  retention rather than a bolted barrel clamp.
- `stylus_diameter_gauge` and `compliant_tool_grip_fit_test`: useful starting
  points for fitting coupons.

These files establish useful cartridge ideas but do not establish fit to the
actual gripper or stylus. The configured 9 mm barrel is nominal, not measured.
Keep the existing released parts unchanged while developing this adapter in
its own directory. Defer the spring/plunger mechanism until rigid mounting and
tip geometry are established; any later compliance needs measured travel and
force before contact work.

## Selected stylus

The operator identified [Amazon ASIN B08Q7L85X2](https://www.amazon.com/dp/B08Q7L85X2)
as the exact stylus on 2026-09-25. The listing identifies OASO model 1010B,
an aluminum-bodied, battery-free capacitive disc stylus with a magnetic cap.
Mount on the barrel with the cap removed and leave the disc/stem clear.

The listing gives overall item dimensions of 6.3 x 3.54 x 0.39 inches, but does
not identify a barrel diameter. These dimensions are not a mechanical drawing:
do not substitute 0.39 inches (9.906 mm) for the clamp bore, or treat the listed
length as the uncapped mounted length. The older CAD's nominal 9 mm barrel
remains unverified. Set the final bore from the actual barrel or a fitting
coupon; keep bore and liner thickness independently adjustable.

Battery-free operation does not establish whether this stylus will register
when held only by a printed mount. Verify hands-free touchscreen response
separately before treating it as a robot-operated touchscreen tool.

## Measurements needed for the first fitting coupon

All dimensions are millimeters. Record the measurement method and uncertainty.

| Dimension | Purpose | Current evidence |
| --- | --- | --- |
| Barrel diameter at two intended support locations | Clamp bore and taper check | Unknown; 9 mm is an old nominal value |
| Straight barrel length, clip and shoulder locations | Choose grip zone and depth stop | Unknown |
| Fixed attachment plate width, thickness and usable length | Saddle and keeper fit | Photos only; not dimensioned |
| Hole diameters and center spacing, if used | Mounting fasteners | Unverified |
| Plate-edge distance to screw/servo/jaw travel and cable route | Mount clearance | Unverified |
| Mounted jaw-reference-to-tip distance and lateral offset | Tool transform and collision model | Must be measured after assembly |

Calipers are preferred for bore/plate fit. A photo estimate can seed a coupon,
but its dimensions must remain labeled as estimates and cannot establish final
fit. If the stylus diameter cannot be measured directly, adapt the existing
diameter gauge to bracket it before making the clamp bore.

## CAD and fitting sequence

1. Obtain the official model or direct plate measurements and identify the
   exact installed gripper variant. Review the chosen attachment surface.
2. Make an adjustable CAD model for the saddle, keeper, barrel clamp and depth
   collar. Expose interface dimensions and print-fit offsets as parameters;
   avoid embedding an assumed mounting-hole pattern.
3. Export a small saddle coupon and barrel-fit coupon first. Confirm fit by
   hand without forcing either onto the mechanism or stylus.
4. Apply the measured coupon corrections, then export STEP, STL and an assembly
   drawing with fasteners and print orientation. Mark provisional outputs
   clearly until the fit is confirmed.
5. With the assembled holder stationary, check retention, twist, axial slip,
   cracks and disc freedom. Record the assembled mass and tip geometry.
6. Update the mounted-tool profile and screen the complete holder/stylus
   envelope along noncontact paths before resuming ghost typing. Secure mounting
   alone does not establish positioning accuracy or suitable contact force.

## Sources and limits

- [Waveshare RoArm-M3 hardware resources](https://docs.waveshare.net/RoArm-M3/Resources-And-Documents/)
  lists the official 3D model and 2D drawings. Checked 2026-09-25. The linked
  downloads were not retrieved successfully in this review; no interface
  dimensions have been extracted from them.
- Local source: `active-project/RoCell_v0_3/scripts/generate_cad.py`, functions
  listed above, and `active-project/RoCell_v0_3/config/parameters.json`.
- Loading evidence: `software/docs/STYLUS_LOADING_PROCEDURE.md` and its referenced
  opening/first-close captures. Servo counts are not jaw-gap or grip-force
  measurements.
