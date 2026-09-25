# Keyboard tray engineering review

## Scope and conclusion

This review covers the first production pair, `keyboard_tray_left` and
`keyboard_tray_right`. The revised geometry is mechanically credible for a
compact keyboard fixture when both halves are fastened to the specified rigid
plywood board with all eight tray screws and washers. The plywood is the primary
structure; the printed seam aligns the two datum surfaces.

This is a geometry and load-path review, not a material certificate or finite
element analysis. Physical coupon, keyboard-fit, and staged robot tests remain
mandatory.

## Design inputs

| Item | Revised value |
|---|---:|
| Nominal keyboard | 315 x 147 x 21 mm |
| Keyboard pocket | 317 x 149 mm |
| Nominal clearance | 1.0 mm per side |
| Assembled tray envelope | 325 x 157 x 11 mm |
| Base/support thickness | 4.0 mm |
| Perimeter wall thickness | 4.0 mm |
| Wall height above support plane | 7.0 mm |
| Board attachment | Four slotted points per half; eight total |
| Seam | Three 22 x 30 mm rounded keys, 0.28 mm side clearance |
| Anti-slip interfaces | Four 16 x 10 x 0.6 mm pockets, all on intact front/rear rails |

## Load-path review

- Vertical robot keypress force passes through the keyboard shell into five
  support lines per half, then through four mounting regions into the plywood.
- The added 8 mm cross-rib in each original window reduces the largest clear
  front-to-rear support span from about 56.7 mm to about 22.8 mm.
- Increasing the support plane from 3.2 to 4.0 mm gives approximately 1.95 times
  the plate bending stiffness from thickness alone, because bending stiffness
  scales approximately with thickness cubed.
- The seam now has three alignment keys instead of two. Their increased length,
  depth, and thickness improve resistance to local peel and yaw, but the keys are
  deliberately not treated as the main structural connection.
- Each half remains independently fixed to the board. A loose seam therefore
  does not release the fixture if the mounting screws remain installed.
- Every mounting slot and pad pocket is fully supported by the intact perimeter
  rails; none occupies an open support window.

## Fit and interference checks

- The keyboard pocket remains 2 mm larger than the nominal keyboard in width and
  depth. The mandatory corner coupon verifies the real keyboard housing and the
  printer's dimensional offset before either large tray is released.
- The production seam and the male/female coupons use shared dimensions.
- Female pockets have straight entry mouths so the rounded male roots do not
  collide with re-entrant corner cusps.
- A CAD solid-intersection check at the assembled position reports zero overlap
  for both the production halves and the coupon pair.
- Both revised halves remain inside the QIDI Plus4 safe plate envelope.
- Engraved `RC02-L` and `RC02-R` identifiers make the controlled revision and
  hand obvious after printing.

## Printing and assembly requirements

- Use `petg_tray_structural_0p4`: 0.4 mm nozzle, 0.20 mm layers, five walls, six
  top and bottom layers, 35% gyroid, and no supports.
- Print the seam and corner coupons first using the same calibrated PETG spool,
  0.4 mm nozzle, 0.20 mm layer height, and dimensional compensation intended
  for the production trays.
- Print the left half as job 01 and accept flatness, all four closed slots,
  washer tracks, pad pockets, datums and seam keys before releasing job 02.
- Install every tray screw with a flat washer. Tighten only until seated;
  excessive torque can creep or crush PETG around a slot.
- Assemble on a flat board, fully seat all three keys, then tighten screws from
  the outer corners toward the seam while checking that both planes stay flush.
- Reject the result if the seam rocks, either half bows, the keyboard bridges
  above a support rail, or ten reinstall cycles do not return to the same datums.

## Remaining physical uncertainties

- Actual PETG strength and creep depend on filament condition and profile.
- The keyboard underside may contain feet or molded bosses not represented by
  its published bounding dimensions.
- Robot press force and lateral misalignment must be limited during commissioning.
- Printed clearance is printer-, nozzle-, and material-specific; the CAD value
  is only the starting candidate selected by the coupon.
