# RoCell manufacturing review

## Outcome

The active package is organized as 24 measured print jobs containing 37
validated printable part types. The geometry is suitable for staged fabrication
on a QIDI Plus4, provided the diagnostic jobs and physical gates are completed.
Digital validation cannot establish actual filament strength, printer shrink,
hardware tolerances, device case geometry, or RoArm gripping force.

## Improvements incorporated in this review

| Module | Improvement | Manufacturing reason |
|---|---|---|
| Keyboard clamps | Added three triangular root gussets | Transfers clamp force into the base and reduces layer-line peel |
| Profile-specific testing | Split diagnostics into jobs 00A-00F | Every dimensional coupon now uses the exact process class it releases |
| Profile-specific washer fit | Added a compact M4 washer ladder to tray, cradle, and calibration jobs | Prevents a recess proven under one PETG profile from releasing a different profile |
| Profile-specific screw-head fit | Added a compact M3 head ladder to precision-tool job 00C | Proves below-flush cap-screw seating with the actual tool profile |
| Insert testing | Separated the M3 precision insert ladder from the horizontal production-axis M4 ladder | Prevents an unrelated print direction/profile from releasing an insert interface |
| Phone clamp | Added `H5.9`, `H6.2`, and `H6.5` horizontal M4 insert pockets | Reproduces the phone tower's printed bore direction, sag, and layer orientation |
| Phone compatibility | Added a measured side-feature keepout gate | Prevents clamp screws from landing on buttons, ports, or case features |
| TPU tips | Added flared bore entrances | Reduces first-layer elephant-foot blockage and eases assembly |
| Rod adapter | Replaced the unsupported flange underside with a tapered transition | Removes the adapter's largest unsupported horizontal surface |
| Tool cap | Changed the broad underside pocket to an annular spring groove | Reduces the unsupported bridge span while retaining spring location |
| RoArm/tool interface | Added a short engraved gripper coupon | Tests jaw geometry and grip before the 65 mm tool body is printed |
| Spring interface | Added an OD/ID seating gauge and measurement gates | Prevents spring binding and incorrect plunger geometry |
| ASA mast feet | Split the pair into first-article and second-foot jobs | Avoids losing two long ASA prints to the same unverified fit or stress crack |
| Slicer guidance | Added bed-adhesion and dimensional-control notes to every active profile | Makes brim, seam, hole, and first-layer requirements explicit |
| Board fasteners | Added shallow washer tracks to every M4 slotted board mount | Keeps washers located, preserves adjustment travel, and makes the correct hardware visually obvious |
| Mast/camera fasteners | Added M5 washer seats around base holes and camera slots | Spreads clamp load and reduces local crushing around printed holes |
| Insert installation | Added tapered entries to production M3/M4 pockets and matching coupons | Helps inserts start square without changing the tested retention diameter |
| Assembly marking | Added `KB`, `USB`, `TOP`, `HAND`, `CAM`, `MAST`, `UP`, and `SPR` markings where space permits | Reduces reversed parts and over-tightening mistakes |
| Keyboard mounting | Moved all slots and anti-slip pockets onto intact front/rear rails | Removes cuts that previously occupied unsupported window space |
| Phone mounting/cable | Closed all four mounting slots and added a raised, coupon-sized cable saddle | Preserves edge ligaments and gives the USB lead measured strain relief |
| Tag system | Enlarged and uniquely labeled six 78 mm frames; isolated artwork from washer tracks | Prevents ID swaps, paper damage, and fastener/marker interference |
| Mast foot | Moved transverse clamp bolts behind the 2020 socket and matched horizontal ASA gauges | Prevents bolt/extrusion collision and validates the printed load path |
| Tool cap | Added an asymmetric locator and spare cap | Makes cap orientation self-evident and serviceable |

## Module review

### Diagnostic parts

- Jobs 00A-00F become the first releasable jobs only after the nozzle and their exact spool/profile qualifications pass; a fresh record correctly shows zero READY jobs.
- Engraved labels identify every selectable dimensional cavity.
- The M3 precision pockets accept the full intended insert depth.
- The separate horizontal M4 ladder must be used for the phone tower because a
  vertical round hole does not predict horizontal-hole roof sag.
- Hardware clearance ladders are repeated under tray, general, and calibration profiles rather than treated as globally interchangeable.
- M4 washer recesses are independently qualified under tray, cradle, and calibration profiles; the broad setup gauge releases only general-profile parts.
- The M3 head recess used by the compliant tool is independently qualified under the precision-tool profile.

### Keyboard fixture

- The plywood board carries the primary load through eight tray fasteners.
- Reinforced tray support rails and the three-key seam control the keyboard datum.
- Rear clamps now have root gussets and must be installed with washers.
- All eight tray slots and four anti-slip pockets are located in solid rails, not the open support windows.
- The seam, corner, and actual keyboard measurement gates remain mandatory.

### Phone fixture

- The base, towers, rails, and four mounting ears form one connected body.
- The phone width coupon does not establish button or port clearance; those
  locations must be measured separately before job 03A is released.
- Horizontal M4 passages may receive local build-plate support and must be chased
  by hand after printing. Never force an insert into an undersized tower.
- The four board slots are closed-ended, and the raised cable saddle must be selected with the actual tie/cable coupon.
- The cradle's M4 washer track is released only by the washer ladder printed in job 00B with the exact cradle profile.
- TPU tips use a flared entry but still require a pull-off test on the M4 peg.

### Vision and calibration parts

- Six unique tag frames, the camera plate, and calibration puck print flat with large bed contact.
- Tag washer zones do not enter the 55.4 mm paper pockets; every frame carries its physical ID and +Y mark.
- The puck uses a separate 0.16 mm job so its divot and crosshair are not degraded
  by the general 0.20 mm plate.
- The puck's M4 washer recess is qualified by job 00F rather than borrowed from a tray or general-profile coupon.
- Paper tags and ChArUco sheets must be printed at 100% and physically measured.

### Compliant tool and adapters

- The full tool remains gated by RoArm jaw measurements, the gripper coupon,
  spring measurements, the spring gauge, M3 inserts, and the precision-profile M3 head ladder.
- The upright body uses a brim; slicer seams must stay off gripping and sliding
  surfaces.
- The rod adapter now has a self-supporting tapered flange and requires an 8 mm
  brim because its bed contact is small relative to its height.
- Spring travel and return must be proven by hand before robot installation.
- The cap is mechanically keyed, and both adapter routes use a spare plus a measured pull/cycle and 24-hour creep gate.

### Optional camera stand

- ASA socket and nut coupons must come from the same spool/profile as the feet.
- The socket coupon now reproduces 20 mm engagement, and the nut/clearance coupon prints on the same horizontal axes as the foot.
- Both mast clamp bolts pass through rear lugs behind the extrusion socket; they no longer cross the installed 2020 member.
- Print only job 07A initially. Assemble and inspect it immediately and after 24
  hours before recording first-article PASS and releasing 07B.
- Use a 10 mm brim, stable enclosure/chamber, and local support only where the
  transverse bores require it.

## Remaining build controls

1. Dry and calibrate each exact filament spool; do not copy temperatures from a
   different brand or material.
2. Verify installed nozzle diameter and repeat coupons after changing nozzle,
   material, compensation, or meaningful flow settings.
3. Import the 3MF, then apply every field in its same-name `.print.json` sidecar.
4. Inspect the slicer preview layer by layer around horizontal holes, pocket roofs,
   thin split collars, seam keys, and the first layer of TPU bores.
5. Measure completed parts only after they cool to room temperature.
6. Use washers and low installation torque on printed slots; PETG can creep under
   sustained clamp load.
7. Keep each washer centered in its shallow recessed track. If the washer climbs
   onto the surrounding surface, loosen the screw and realign the part.
8. Perform staged hand tests before powered robot contact, then start at low speed
   and low force with a reachable latching power cutoff.

## Release status

An STL or STEP passing digital validation means its geometry is coherent and
printable within the machine envelope. It does not mean the physical interface
has passed. `PRINT_READINESS.md` is the operational release authority.
