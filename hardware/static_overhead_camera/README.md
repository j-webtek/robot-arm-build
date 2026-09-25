# Printed static camera portal

The current printed-arm candidate is
`ROCELL-PRINTABLE-CAMERA-PORTAL-PROTOTYPE-003`: two bench-bearing front board
anchors, two four-module uprights, a four-module crossbar, two two-module booms,
a positive-lock carriage, and a four-sided camera cage with a planar four-bolt
keeper. Rigid parts use ABS Rapido; five contact/compression pads use TPU 95A.

The board locates the portal and helps react overturning. It does **not** carry
portal dead load; both `120 x 120 mm` saddle feet bear on the same bench plane
as the board underside.

## Build from these files

- [`PRINTABLE_FRAME_BUILD_GUIDE.md`](PRINTABLE_FRAME_BUILD_GUIDE.md) — exact
  print, hardware, assembly, locking, and qualification sequence
- [`BOM_PRINTABLE_FRAME.csv`](BOM_PRINTABLE_FRAME.csv) — exact quantities
- [`print_jobs/printable_camera_frame_jobs.json`](print_jobs/printable_camera_frame_jobs.json)
  and same-base `.print.json` sidecars — exact 3MF-to-process mapping
- [`cad/output/manifest.json`](cad/output/manifest.json) — generated geometry,
  hashes, and validation reports
- [`cad/output/assembly/printable_camera_portal_printed_parts_only.step`](cad/output/assembly/printable_camera_portal_printed_parts_only.step)
  — printed-part orientation and placement reference
- [`config/printable_frame_design.json`](config/printable_frame_design.json) —
  parametric source contract

Do not slice an assembly STEP or a loose STL for production. Use the exact
numbered geometry-only 3MF in [`cad/output/plates_3mf`](cad/output/plates_3mf),
its matching sidecar, the named process, and the separately selected filament
preset. Keep stored orientation/placement, 100% scale, supports off, and fuzzy
skin off.

## Rebuild and verify

From the workspace root:

```powershell
py -3.10 hardware/static_overhead_camera/cad/generate_printable_frame.py
py -3.10 hardware/static_overhead_camera/cad/sync_operator_package.py
py -3.10 hardware/static_overhead_camera/cad/validate_printable_frame_package.py
```

The final validator independently reopens every STEP, STL, and 3MF, checks
topology and protected printer envelope, reconciles every printed quantity and
hardware count, verifies every sidecar/hash/process mapping, and requires all
generated interface reports to pass.

## Current mechanical choices

- no drilled board holes and no wood screws;
- four captured M6 clamp nuts and top-driven M6 x 25 bolts;
- full-height open-U structural modules and external bolted splice collars;
- paired portal-corner plates and top/bottom four-bolt boom-root straps;
- four positive-lock M5 carriage bolts, all in one selected Y row;
- three M4 leveling screws, all in one selected X index;
- a bench-assembled, removable camera module closed by four M4 keeper bolts;
- front-opening installed wrench access for both front leveling jam nuts;
- one independently rated, factory-terminated metal safety tether.

The package is a validated **digital prototype**, not a certified overhead load
rating. Physical coupon fit, proof load, 24-hour ABS creep, witness-mark,
camera-fit, tether, optical, and full robot collision checks remain mandatory.
Nothing here authorizes robot power or motion.

[`PRINTABLE_FRAME_INTEGRATION_MAP.md`](PRINTABLE_FRAME_INTEGRATION_MAP.md) is
superseded planning history and is not a build instruction. The older metal
support study remains reference material only.
