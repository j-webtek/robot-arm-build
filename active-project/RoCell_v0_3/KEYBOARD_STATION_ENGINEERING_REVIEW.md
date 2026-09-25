# Keyboard station engineering review

**Revision:** `RC03-INT-R1`

## Decision

Use two open-datum printed stations because the full keyboard fixture cannot fit the QIDI Plus4 protected plate in one piece. The left station is the board-registered master; the right station is a seam-located slave.

Do not independently pin both halves while also retaining a keyed seam. That combination closes an overconstrained tolerance loop and can bind after normal ABS process variation or hand-drilled board variation.

## Load and datum logic

- The finished board supports the stations.
- The continuous printed base seats directly on the finished board; three broad-triangle retention zones control lift without separate shims.
- The left round locator fixes X/Y; its radial slot fixes yaw while relieving pin-spacing error.
- Three left screws provide hold-down only.
- The seam transfers the keyboard datum from left to right.
- Three relieved right screws provide hold-down without imposing a competing pin baseline.
- Front/side device walls locate the keyboard; rear guided sliders remove play without bowing the shell.

## Printability

Each station is one object, printed flat, one per plate, in `abs_rapido_tray_structural_0p4` with `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle`:

- 0.4 mm nozzle;
- 0.20 mm layers;
- five walls;
- six top and bottom layers;
- 35% gyroid;
- supports off;
- 8 mm outer brim with 0.05 mm object gap.

The confirmed filament preset uses 250 °C on the first layer, 260 °C thereafter, a 90 °C textured bed, a sealed 55 °C chamber, 0.95 flow ratio, 0.03 pressure advance, and 24.5 mm³/s maximum volumetric speed. Use the same locked tray process for job 00A and both stations. Never globally scale either STL for ABS shrink; select measured fits through the coupon-controlled parameters instead.

The slicer seam must stay away from locator sockets, seam datums, hold-down holes, clamp guides, base-contact regions, and keyboard contact faces.

## Physical gates

- Use the actual keyboard and job 00A corner/seam/locator/clearance/washer coupons.
- Master free-state corner lift <= 0.75 mm.
- Combined support-plane flatness <= 0.40 mm.
- Seam gap <= 0.40 mm.
- Seam flush mismatch <= 0.25 mm.
- No rocking with the keyboard loaded.
- Keyboard pose range <= 0.50 mm over ten load/unload cycles.
- Station reinstall X/Y range <= 0.25 mm, yaw <= 0.20 degrees, and Z <= 0.20 mm over ten cycles.
- No whitening, stress cracks, or layer separation after locator and fastener cycling.

## Service and usability

- `RC03-L MASTER`, `RC03-R SLAVE`, and the rear-clamp `KB R3` identities are readable from above; the illustrated guide supplies board-axis and fastener callouts that are not molded into the stations.
- Rear sliders use replaceable face pads and low-profile hand screws. Each hand screw passes through its slider and station into the board anchor, serving as that station's third retainer.
- The keyboard's existing feet rest directly on the finished board; current CAD uses no added support pads or station seating shims.
- Both clamp scales are matched; clamp force is fingertip-only.
- A failed slider can be replaced without disturbing station registration.
- A failed right station can be replaced and registered from the accepted master; it does not require two new board pin holes.

## Release conclusion

The architecture is mechanically coherent and fits the printer, but it is not physically validated until the actual keyboard, printed coupons, cooled first articles, board interface, seam, support plane, device cycling, and station repeatability all pass their numeric gates.
