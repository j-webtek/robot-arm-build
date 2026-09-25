# RoCell RC02-PRO-R1 print enhancement and release plan

## Purpose and scope

This is the manufacturing-control plan for the current QIDI Plus4 release. It
covers all 37 distinct printable STL files and 52 total plate objects across the
24 jobs named by `config/print_jobs.json`, including the six individually marked tag frames, and maps each model to its
print process, dimensional interfaces, release gate, inspection, assembly aid,
and deliberately deferred work.

The plan separates three different ideas that must not be conflated:

- **Integrated** means the aid is already present in the current parametric CAD.
- **Release control** means the geometry is credible but must pass the named
  physical measurement, coupon, or first-article gate before production.
- **Deferred** means changing the CAD now would guess a real hardware or device
  dimension. Record the measurement first, update the parameter, regenerate all
  dependent outputs, and repeat the relevant coupon.

Passing mesh validation or fitting the 295 x 295 x 280 mm conservative Plus4
envelope does not release a part for use. `PRINT_READINESS.md` and the recorded
gates in `config/measurement_record.json` remain the release authority.

## Common professional-print standard

Apply these controls to every job unless its sidecar is stricter:

1. Use the exact named profile, exact material spool/lot, 0.4 mm nozzle, and
   orientation below. A nozzle, material, flow, XY compensation, or meaningful
   slicer change invalidates that profile's dimensional coupons.
2. Confirm the imported 3MF remains inside the 295 x 295 mm safe XY envelope and
   that no object was auto-scaled. Complete one QIDI Studio save/reopen round
   trip before releasing production jobs.
3. Keep seams off fit surfaces, male keys, pocket mouths, washer tracks,
   gripper flats, sliding bores, tag artwork pockets, and TPU contact surfaces.
4. Inspect the first layer for closed bores, filled graduations, and elephant
   foot. Remove flash by hand; ream only with the coupon-selected hand tool.
5. Let PETG/ASA parts cool to room temperature before measuring. Record actual
   values, spool lot, profile revision, QIDI Studio version, operator, and date.
6. Fasteners must enter by hand for at least two turns. Use the specified washer
   seats, tighten in alternating steps, and stop at whitening, cracking,
   dishing, or surface creep.
7. Photograph every diagnostic result and first article beside calipers or the
   actual mating hardware. Retain failed coupons with the settings that made
   them; they are useful process evidence.
8. Mark accepted fasteners with a removable paint witness and recheck PETG and
   ASA joints after 24 hours.

### Current process profiles

| Profile | Process | Intended use |
|---|---|---|
| `petg_tray_structural_0p4` | PETG, 0.20 mm, 5 walls, 6 top/bottom, 35% gyroid, no support; 6 mm brim on tray halves | Keyboard trays and exact-profile tray coupons |
| `petg_cradle_0p4` | PETG, 0.20 mm, 5 walls, 5 top/bottom, 30% gyroid; build-plate support only under horizontal bores if required; 5 mm brim on cradle | Phone cradle and exact-profile cradle coupons |
| `petg_precision_0p4` | PETG, 0.16 mm, 5 walls, 6 top/bottom, 40% gyroid, no support; 5 mm body brim | Compliant tool and exact-profile tool coupons |
| `petg_adapter_0p4` | PETG, 0.12 mm, 4 walls, 5 top/bottom, 100% rectilinear, no support; 8 mm bushing brim | Stylus/rod adapters and their fit coupons |
| `petg_general_0p4` | PETG, 0.20 mm, 4 walls, 5 top/bottom, 25% gyroid; support off unless overridden | Clamps, frames, camera plate, and general setup coupons |
| `petg_calibration_0p4` | PETG, 0.16 mm, 4 walls, 6 top/bottom, 40% gyroid, no ironing | TCP calibration puck |
| `tpu95a_0p4` | Dry TPU 95A, 0.16 mm, 3 walls, 5 top/bottom, 100% rectilinear, no support | Phone and keyboard contact tips |
| `asa_structural_0p4` | ASA, 0.24 mm, 6 walls, 6 top/bottom, 45% gyroid, enclosed; 10 mm brim | Optional mast coupons and feet |

## Phased execution and release sequence

### Phase 0 — freeze measurements and process identity

1. Confirm the installed 0.4 mm nozzle and create one revision-controlled
   profile for each material/process actually used.
2. Measure the keyboard, phone/case, phone side-feature keepouts, USB cable and
   tie, gripper jaws, spring, stylus, 6 mm rod, tag stock, camera interface,
   inserts, screw heads, washers, nuts, and 2020 extrusion.
3. Put only measured overrides in `config/user_overrides.json`; regenerate CAD,
   board layout, plates, validation reports, manual, and checksums as one set.
4. Perform the QIDI Studio import/save/reopen check without scaling.

### Phase 1 — print all six required diagnostic jobs

1. Print `00A` with the tray profile and record the keyboard corner, seam,
   tray-profile clearance, and tray-profile M4 washer results.
2. Print `00B` with the cradle profile and record phone width, horizontal M4
   insert, cable-saddle, and cradle-profile M4 washer selections.
3. Print `00C` with the precision profile and record gripper, spring, and M3
   insert and M3 screw-head results.
4. Print `00D` with the adapter profile and record stylus sliding clearance and
   the selected horizontal M2/M3 thread pilot.
5. Print `00E` with the general profile and record general clearances, head/
   washer/hex selections, and preliminary TPU retention.
6. Print `00F` with the calibration profile and record the M4 clearance and
   washer recess selected specifically for the fine-layer calibration-puck
   process.

Do not average selections from different profiles. The same nominal hole,
washer seat, or head recess may print differently under the tray, cradle,
precision, general, calibration, and ASA profiles.

### Phase 2 — required PETG first articles and production

1. Release `01` only after all keyboard measurements and `00A` gates pass.
2. Inspect the left tray as the first article; release `02` only after
   `keyboard_left_first_article_pass` is recorded.
3. Release `03A`, `03B`, `03C1`, `03C3`, and `03D` only through their own gates.
4. Validate tag ID0 with real artwork first. Release IDs 1–5 only after scale,
   pocket depth, washer isolation, and camera readability pass.

### Phase 3 — tool route and TPU first articles

1. Select at least one tool route. Print shared tool job `04A` after the gripper,
   spring, precision-profile M3 insert, and precision-profile M3 head selections
   pass.
2. Print `04B` for the phone-stylus route or `04C` for the keyboard-rod route
   only after choosing a positive retention method.
3. Print one TPU first article (`05A` and, when selected, `05C`). Perform the
   actual-hardware pull-off test before printing the three-piece production/
   spare jobs `05B` and `05D`.

### Phase 4 — optional camera mast

1. Print ASA job `06` from the same conditioned spool and profile intended for
   the feet.
2. Release `07A` only after socket, horizontal nut trap, horizontal M5 clearance,
   and same-profile M5 washer selections pass.
3. Fully assemble the first foot, measure base flatness, and inspect immediately
   and after 24 hours. Release `07B` only after that first article passes.

### Phase 5 — controlled powered commissioning

Dry-assemble, hand-cycle, and inspect every mechanism before installing it on
the robot. Begin powered testing at minimum practical speed and force with a
reachable latching cutoff. Record initial settings, paint-witness positions,
and the 24-hour reinspection.

## Per-print enhancement and inspection plan

### Job 00A — keyboard-profile diagnostics

#### `keyboard_corner_fit_test.stl`

- **Integrated enhancement:** 58 x 58 x 11 mm production corner section with a
  4 mm base, 4 mm walls, 7 mm upper lip, open skeleton region, and `FRONT-L`
  orientation mark.
- **Print:** `petg_tray_structural_0p4`; flat exactly as exported; no support.
- **Critical interface:** nominal 315 x 147 x 21 mm keyboard with 1.0 mm CAD
  clearance per side. Test the exact keyboard and any intended anti-slip pad.
- **Pre-release gate:** produces `keyboard_corner_coupon_pass`; actual keyboard
  dimensions and `geometry_matches_measurements` must precede tray release.
- **Post-print inspection:** confirm the keyboard seats against both datums by
  gravity, does not rock, and leaves no polished/white interference line.
- **UX benefit / deferred work:** makes fit failure cheap and obvious. A pad
  pocket should be added to this coupon only after pad material/thickness is
  selected so the coupon and production support plane remain identical.

#### `keyboard_seam_fit_male.stl`

- **Integrated enhancement:** production male key section, 22 mm nominal key
  length, 30 mm depth, 3.5 mm corner radius, 4 mm thickness, `M`, and `C0.28`.
- **Print:** `petg_tray_structural_0p4`; flat as exported; no support; keep seam
  off the key perimeter.
- **Critical interface:** must be tested only against the female coupon from the
  same plate/profile.
- **Pre-release gate:** paired result contributes to
  `keyboard_seam_coupon_pass`.
- **Post-print inspection:** full hand insertion, flush top/bottom faces, no
  visible yaw, no layer peeling at the root, and no tool-assisted assembly.
- **UX benefit / deferred work:** marked gender and clearance prevent mixing or
  guessing. Do not alter the key clearance until the cooled pair is measured.

#### `keyboard_seam_fit_female.stl`

- **Integrated enhancement:** production open-mouth pocket with 0.28 mm nominal
  clearance, cusp-removing straight entry, `F`, and `C0.28` marks.
- **Print:** `petg_tray_structural_0p4`; flat as exported; no support; keep the
  seam and first-layer compensation away from the pocket mouth.
- **Critical interface:** male coupon above; pocket depth and mouth must remain
  identical to the production right tray.
- **Pre-release gate:** paired result contributes to
  `keyboard_seam_coupon_pass`.
- **Post-print inspection:** verify full insertion and removal by hand, no loose
  vertical step, no rocking, and no retained brim inside the mouth.
- **UX benefit / deferred work:** prevents wasting two large tray prints on an
  unverified joint. Change both coupon and tray together if tuning is required.

#### `hardware_fit_gauge.stl` — tray-profile instance

- **Integrated enhancement:** current code defines a 160 x 30 x 6 mm clearance
  ladder with M3 holes 3.2/3.4/3.6 mm, M4 holes 4.4/4.6/4.8 mm, and M5 holes
  5.3/5.5/5.7 mm, each engraved with its modeled diameter.
- **Print:** `petg_tray_structural_0p4`; flat as exported; no support.
- **Critical interface:** actual tray screws, not drill shanks alone. The tray
  uses nominal 4.6 mm M4 passages with 9.2 mm washer tracks.
- **Pre-release gate:** record the tray-profile selection as
  `tray_clearance_holes_coupon_pass`; do not substitute the general-profile copy.
- **Post-print inspection:** after cooling, identify the smallest hole that
  passes the actual fastener freely without thread cutting or side load.
- **UX benefit / deferred work:** profile-specific selection prevents hidden
  fit drift. Add paint-marker selection pads only in a later revision if the
  current engraved labels prove difficult to record.

#### `m4_washer_fit_gauge.stl` — tray-profile instance

- **Integrated enhancement:** compact 78 x 30 x 6 mm ladder with 4.6 mm M4
  passages and 8.8/9.2/9.6 mm-diameter washer recesses, each effectively 0.6 mm
  deep and engraved `W8.8`, `W9.2`, or `W9.6`.
- **Print:** job `00A`, `petg_tray_structural_0p4`; flat as exported with labels
  upward; no support.
- **Critical interface:** the exact M4/#8 board fastener and M4 washer intended
  for the tray's slotted 0.6 mm-deep washer tracks.
- **Pre-release gate:** this physical instance combines with the `00A`
  `hardware_fit_gauge.stl` result to release
  `tray_clearance_holes_coupon_pass`; record board-screw diameter, smallest free
  hole, accepted M4 washer OD, and washer-fit result.
- **Post-print inspection:** select the smallest recess in which the actual
  washer seats flat by hand, does not dish or rock, and remains below the
  surrounding edge without force.
- **UX benefit / deferred work:** keeps the washer visibly located while
  preserving slot travel. Never substitute the cradle, calibration, or general
  profile result for this tray-profile selection.

### Job 00B — phone-profile diagnostics

#### `phone_width_fit_test.stl`

- **Integrated enhancement:** 86.3 x 36 x 9 mm default U-channel, 79.9 mm
  default internal width, 3.2 mm walls, 3 mm base, 6 mm default rail height,
  and generated `FIT79.9` marking.
- **Print:** `petg_cradle_0p4`; flat as exported; no support.
- **Critical interface:** phone measured in the exact case state; default CAD is
  77.9 mm phone width plus 1.0 mm clearance on each side.
- **Pre-release gate:** `phone_dimensions_measured` and
  `phone_width_coupon_pass`.
- **Post-print inspection:** phone must enter without spreading the walls, seat
  flat, withdraw without scratching, and have only slight lateral motion.
- **UX benefit / deferred work:** exposes case/clearance errors before the large
  cradle. Add or alter inner lead-in chamfers only if insertion—not width—is the
  demonstrated failure mode.

#### `m4_horizontal_insert_fit_gauge.stl`

- **Integrated enhancement:** 26 x 80 x 16 mm production-axis ladder with 4.6
  mm passages; 5.9/6.2/6.5 mm pockets, each 6.2 mm deep; 0.7 mm tapered entries;
  `H` labels and `OUTER` orientation mark.
- **Print:** `petg_cradle_0p4`; flat base as exported so the bores remain
  horizontal; use only local build-plate support if the slicer preview proves
  the roof cannot bridge cleanly.
- **Critical interface:** actual M4 heat-set insert, 5–6 mm long, and actual M4
  screw. Installation axis must match the phone towers.
- **Pre-release gate:** `m4_horizontal_insert_coupon_pass`.
- **Post-print inspection:** ream the passage by hand if selected, heat the
  insert squarely, then reject splitting, spinning, axial pullout, or roof sag
  that prevents a screw from traversing the pocket.
- **UX benefit / deferred work:** directly represents the difficult printed
  orientation. Do not use the vertical M3 ladder to infer this result.

#### `cable_tie_saddle_fit_gauge.stl`

- **Integrated enhancement:** 84 x 30 x 7 mm ladder with three 14 x 10 x 3 mm
  raised saddles, 1.8 mm-high tunnels, and 2.6/3.2/4.0 mm labeled tie widths.
- **Print:** `petg_cradle_0p4`; flat as exported; no internal support in the
  tunnels.
- **Critical interface:** exact cable tie and cable; production cradle defaults
  to a 3.2 mm-wide, 1.8 mm-high tunnel.
- **Pre-release gate:** `phone_cable_measured` and
  `cable_tie_saddle_coupon_pass`.
- **Post-print inspection:** tie passes by hand without shaving, tunnel roof is
  intact, cable can be restrained without flattening, and tie head remains
  above—not under—the board plane.
- **UX benefit / deferred work:** gives strain relief without trapping a tie
  head beneath the cradle. Final saddle position remains dependent on the
  measured USB-port/cable path and bend radius.

#### `m4_washer_fit_gauge.stl` — cradle-profile instance

- **Integrated enhancement:** the same compact 78 x 30 x 6 mm gauge with 4.6
  mm passages and `W8.8`/`W9.2`/`W9.6` recesses, 0.6 mm deep.
- **Print:** job `00B`, `petg_cradle_0p4`; flat as exported with labels upward;
  no support.
- **Critical interface:** the actual washer used in the phone cradle's four M4
  mounting-ear tracks; do not infer fit from the general setup plate.
- **Pre-release gate:** releases `cradle_m4_washer_coupon_pass`; record actual
  washer OD, selected modeled recess, and flat-seating result. The horizontal
  M4 insert/passage remains controlled separately by
  `m4_horizontal_insert_coupon_pass`.
- **Post-print inspection:** washer drops into the smallest accepted recess by
  hand, lies flat without rocking or edge climb, and can be removed without
  prying or damaging the coupon.
- **UX benefit / deferred work:** qualifies the exact cradle process so mounting
  washers remain captured and visually centered during adjustment.

### Job 00C — precision-tool diagnostics

#### `compliant_tool_grip_fit_test.stl`

- **Integrated enhancement:** corrected 28 x 24 x 34 mm coupon reproducing the
  full 18 mm-wide x 1.2 mm-deep x 28 mm-high production gripping recesses with
  3 mm end margins and `G` marking.
- **Print:** `petg_precision_0p4`; upright as exported; 5 mm brim if needed;
  seam must not touch the two gripper faces.
- **Critical interface:** measured RoArm jaw opening, pad width, pad height, and
  usable stroke.
- **Pre-release gate:** `gripper_interface_measured` and
  `gripper_coupon_pass`.
- **Post-print inspection:** jaws do not bottom out, contact both flats evenly,
  hold against manual axial/torsional load, and leave no crushing or white stress
  marks at the minimum useful force.
- **UX benefit / deferred work:** establishes repeatable gripper force before a
  tall precision print. A positive seating shoulder is deferred until the jaw
  geometry and collision envelope are measured.

#### `spring_fit_gauge.stl`

- **Integrated enhancement:** 30 x 30 x 14 mm stepped cup reproducing the 15.2
  mm chamber, 14.2 mm cap seat, and 10.0 mm center post.
- **Print:** `petg_precision_0p4`; flat as exported; no support; clear all pocket
  strings without enlarging the steps.
- **Critical interface:** spring OD no more than 13.5 mm, ID at least 10.5 mm,
  free length 18–22 mm, and a measured light rate appropriate to 3–6 mm travel.
- **Pre-release gate:** `spring_dimensions_measured` and
  `spring_fit_coupon_pass`.
- **Post-print inspection:** spring passes over the 10.0 mm post, enters both
  stepped seats without scraping, stands square, and returns freely after hand
  compression.
- **UX benefit / deferred work:** checks both body and cap interfaces cheaply.
  Hard stops or travel-window geometry remain deferred until spring rate, coil
  bind, and required robot contact travel are physically proven.

#### `m3_insert_fit_gauge.stl`

- **Integrated enhancement:** 78 x 30 x 8 mm vertical full-depth ladder with
  4.3/4.6/4.9 mm pockets, 6.2 mm depth, and 0.7 mm tapered entries.
- **Print:** `petg_precision_0p4`; flat as exported; no support.
- **Critical interface:** actual M3 heat-set inserts, nominal 4.5–4.7 mm OD and
  5–6 mm length, plus the actual installation tip.
- **Pre-release gate:** `m3_insert_coupon_pass`.
- **Post-print inspection:** insert seats square and flush, does not split the
  coupon or spin under screw installation, and accepts the M3 screw by hand.
- **UX benefit / deferred work:** isolates insert selection from the tool body.
  Production pocket diameter must be updated to the selected result before
  regenerating if 4.6 mm does not win.

#### `m3_head_fit_gauge.stl`

- **Integrated enhancement:** compact 78 x 30 x 6 mm ladder with 3.4 mm M3
  passages and 5.8/6.2/6.6 mm-diameter head recesses, each effectively 2.0 mm
  deep and engraved `H5.8`, `H6.2`, or `H6.6`.
- **Print:** job `00C`, `petg_precision_0p4`; flat as exported with labels
  upward; no support.
- **Critical interface:** the actual M3 x 10 mm button-head screw used by the
  compliant-tool cap. Test the purchased head, not only a nominal standard.
- **Pre-release gate:** releases `precision_m3_head_coupon_pass`; record actual
  screw-head diameter, the smallest accepted modeled recess, and below-face fit
  result.
- **Post-print inspection:** screw shank passes freely, head seats square and
  fully below the surrounding face without forcing, and sufficient annular wall
  remains around the recess.
- **UX benefit / deferred work:** gives the precision-profile cap its own head
  fit instead of borrowing a coarser general-profile result. A standard M3
  washer is still not authorized unless separately measured and designed.

### Job 00D — adapter-profile diagnostics

#### `stylus_diameter_gauge.stl`

- **Integrated enhancement:** 92 x 28 x 4 mm ladder labeled 8.0–10.0 mm in 0.5
  mm steps; each modeled hole is label +0.2 mm and the plate states
  `SLIDE +0.2`.
- **Print:** `petg_adapter_0p4`; flat as exported; no support.
- **Critical interface:** the exact stylus barrel at several points, excluding
  clips, tapers, seams, and soft grip material.
- **Pre-release gate:** `stylus_diameter_measured` and
  `stylus_gauge_coupon_pass`.
- **Post-print inspection:** select the smallest cooled hole that permits smooth
  axial sliding without rocking; record both the label and measured printed ID.
- **UX benefit / deferred work:** prevents confusing a sliding clearance with
  literal stylus diameter. Collar bore remains measurement-driven.

#### `thread_pilot_fit_gauge.stl`

- **Integrated enhancement:** 26 x 106 x 18 mm horizontal blind-pilot ladder,
  7 mm deep, with M2 pilots 1.5/1.6/1.7 mm and M3 pilots 2.4/2.5/2.6 mm.
- **Print:** `petg_adapter_0p4`; flat as exported so pilots print horizontally;
  no support inside pilots.
- **Critical interface:** exact flat- or nylon-tip grub screw selected for the
  stylus collar or any future adapter retention feature.
- **Pre-release gate:** use this evidence to set
  `adapter_retention_method_selected`; record screw standard, pilot, insertion
  depth, and repeat-cycle result.
- **Post-print inspection:** screw starts square, develops useful holding torque
  without splitting, remains flush, and survives at least five install/remove
  cycles in the selected pilot.
- **UX benefit / deferred work:** turns thread selection into a controlled test.
  Do not add an M3 pilot to the thin rod-bushing flange; current wall depth is
  insufficient for a reliable printed M3 thread.

### Job 00E — general setup diagnostics

#### `hardware_fit_gauge.stl` — general-profile instance

- **Integrated enhancement:** same 3.2–5.7 mm labeled clearance ladder described
  under job `00A`, deliberately reprinted with the general profile.
- **Print:** `petg_general_0p4`; flat as exported; no support.
- **Critical interface:** actual #8/M4/M5 hardware used in general fixtures.
- **Pre-release gate:** `general_clearance_holes_coupon_pass`; it is not
  interchangeable with the tray-profile result.
- **Post-print inspection:** select the smallest freely passing hole for each
  actual fastener after cooling and record any reamer used.
- **UX benefit / deferred work:** preserves measured compatibility across profile
  changes rather than assuming identical shrink.

#### `setup_hardware_fit_gauge.stl`

- **Integrated enhancement:** 160 x 84 x 8 mm four-row ladder: M3 head seats
  5.8/6.2/6.6 mm x 2.0 mm deep; M4 washer seats 8.8/9.2/9.6 mm x 0.6 mm; M5
  washer seats 10/11/12 mm x 0.8 mm; and camera hex pockets
  12.6/13.2/13.8 mm x 3.2 mm.
- **Print:** `petg_general_0p4`; flat as exported; no support.
- **Critical interface:** actual M3 button head, M4/M5 washers, and selected
  1/4-20 nut or captured-head geometry.
- **Pre-release gate:** releases only the general-profile
  `setup_hardware_coupon_pass`; `camera_mount_interface_measured` remains a
  separate prerequisite for the camera plate.
- **Post-print inspection:** hardware seats fully without force, does not rock or
  rotate when intended captive, and leaves adequate surrounding wall.
- **UX benefit / deferred work:** makes head and washer fit visible before the
  part is printed. The camera pocket cannot be finalized until it is known
  whether the plate captures a nut or a bolt head. This general-profile gauge
  must not release tray, cradle, precision-tool, calibration, or ASA interfaces.

#### `tpu_tip_retention_gauge.stl`

- **Integrated enhancement:** 38 x 22 x 14 mm rigid gauge with 4.0 mm x 8 mm M4
  proxy peg, 6.0 mm x 11 mm rod proxy peg, labels, and seating bands at 5.5 and
  8.5 mm.
- **Print:** `petg_general_0p4`; flat base as exported; no support.
- **Critical interface:** matching TPU first articles. The smooth printed M4 peg
  is only a preliminary proxy for a threaded screw.
- **Pre-release gate:** contributes to `phone_tpu_retention_coupon_pass` and
  `keyboard_tpu_retention_coupon_pass`, followed by testing on the actual M4
  screw and actual 6 mm rod.
- **Post-print inspection:** tips reach the witness band by firm hand pressure,
  resist direct pull-off and twisting, and show no bore split after removal.
- **UX benefit / deferred work:** standardizes seating depth. Final release must
  never rely solely on the smoother printed proxy pegs.

### Job 00F — calibration-profile clearance diagnostic

#### `hardware_fit_gauge.stl` — calibration-profile instance

- **Integrated enhancement:** same current-code 160 x 30 x 6 mm clearance
  ladder used in jobs `00A` and `00E`, with M3 holes 3.2/3.4/3.6 mm, M4 holes
  4.4/4.6/4.8 mm, and M5 holes 5.3/5.5/5.7 mm. Printing the same geometry a
  third time deliberately isolates profile-dependent dimensional change.
- **Print:** `petg_calibration_0p4`; flat as exported, 0.16 mm layers, 4 walls,
  6 top/bottom layers, 40% gyroid, no support, and no ironing.
- **Critical interface:** the exact board fastener intended for the calibration
  puck. The production puck models 4.6 mm M4 passages and 9.2 mm washer tracks,
  but its fine-layer profile must be qualified independently of the tray and
  general PETG profiles.
- **Pre-release gate:** job `00F` requires the machine/nozzle and calibrated
  `petg_calibration_0p4` profile; its recorded result produces
  `calibration_clearance_holes_coupon_pass` for job `03D`.
- **Post-print inspection:** after cooling, record the smallest M4-labeled hole
  that passes the actual fastener freely without thread cutting or side load;
  record measured printed ID, any hand reamer used, spool lot, and profile
  revision. Do not copy the `00A` or `00E` selection.
- **UX benefit / deferred work:** the puck can now be installed without guessing
  whether its finer layers changed hole fit. Alter the puck passage only if this
  exact-profile coupon demonstrates that the nominal 4.6 mm value fails.

#### `m4_washer_fit_gauge.stl` — calibration-profile instance

- **Integrated enhancement:** the same compact 78 x 30 x 6 mm M4 washer ladder
  with 4.6 mm passages and 8.8/9.2/9.6 mm x 0.6 mm recesses.
- **Print:** job `00F`, `petg_calibration_0p4`; flat as exported with labels
  upward; 0.16 mm layers, no support, and no ironing.
- **Critical interface:** the exact washer and board fastener used on the TCP
  puck's 9.2 mm nominal washer tracks.
- **Pre-release gate:** combines with the `00F` clearance ladder to release
  `calibration_clearance_holes_coupon_pass`; record board-screw diameter,
  smallest free hole, accepted M4 washer OD, and washer-fit result.
- **Post-print inspection:** actual washer seats flat and removable in the
  smallest accepted recess; reject edge climb, force fit, rocking, or a filled
  recess lip.
- **UX benefit / deferred work:** independently qualifies both clearance and
  washer seating under the puck's fine-layer process; no general-profile result
  may substitute.

### Jobs 01 and 02 — keyboard trays

#### `keyboard_tray_left.stl`

- **Integrated enhancement:** 184.5 x 157 x 11 mm first article with 4 mm base,
  reinforced skeleton and ribs, three male seam keys, four 18 x 4.6 mm slots on
  intact front/rear rails, 9.2 mm washer tracks, 2 mm graduations, two
  16 x 10 x 0.6 mm pad pockets on solid rails, and `RC02-L` marking.
- **Print:** `petg_tray_structural_0p4`; flat as exported, 6 mm brim, no support;
  seam away from keys, slots, pad pockets, and keyboard datums.
- **Critical interface:** 315 x 147 mm nominal keyboard, 1.0 mm per-side
  clearance, 4 mm walls, #8/M4 board fasteners and 9.2 mm M4 washers.
- **Pre-release gate:** every prerequisite in job `01`, especially keyboard
  measurements, corner/seam coupons, combined tray-profile clearance/washer
  gate, geometry match, and QIDI Studio round trip.
- **Post-print inspection:** flat within the accepted board tolerance; slots and
  washer tracks complete; scales readable; pad pockets supported; keys match the
  accepted coupon; keyboard rests on rails without rocking.
- **UX benefit / deferred work:** left-first sequencing prevents duplicating a
  large defect. Cable-specific clips or exits remain deferred until the actual
  keyboard cable origin and bend radius are measured.

#### `keyboard_tray_right.stl`

- **Integrated enhancement:** 162.5 x 157 x 11 mm matching half with three
  open-mouth female pockets, identical rail-mounted slots, washer tracks,
  graduations, solid pad pockets, and `RC02-R` marking.
- **Print:** `petg_tray_structural_0p4`; flat as exported, 6 mm brim, no support;
  keep seams away from all three female mouths.
- **Critical interface:** accepted left first article, male/female seam, same
  keyboard and board hardware.
- **Pre-release gate:** job `02` prerequisites plus
  `keyboard_left_first_article_pass`.
- **Post-print inspection:** mate all three keys by hand, confirm a flush support
  plane and square 325 x 157 mm assembled envelope, then verify the keyboard
  seats without forcing either half apart.
- **UX benefit / deferred work:** a staged matched pair is easier to diagnose and
  replace than an untracked one-piece print.

### Job 03A — phone cradle

#### `phone_cradle_a16.stl`

- **Integrated enhancement:** 117.3 x 172.8 x 20 mm default cradle with 4 mm
  skeleton base, 3.2 mm rails, 79.9 x 166.4 mm default fit envelope, left/top
  datums, camera relief, four closed 18 x 4.6 mm Y-oriented mounting slots and
  9.2 mm washer tracks, two horizontal clamp towers, `USB`/`TOP`/`HAND` marks,
  and a raised cable-tie saddle.
- **Print:** `petg_cradle_0p4`; flat as exported with 5 mm brim; support only the
  horizontal clamp-bore roofs if slicer preview requires it.
- **Critical interface:** measured phone/case, buttons and ports, cable/tie,
  nominal 4.6 mm M4 passages, 6.2 mm-diameter x 6.2 mm-deep insert pockets, M4 x
  25 mm hand screws, and TPU tips.
- **Pre-release gate:** all job `03A` prerequisites, including phone/case and
  side-feature measurements, cable measurement, width/horizontal-M4/saddle
  coupons, `cradle_m4_washer_coupon_pass`, geometry match, and round trip.
- **Post-print inspection:** base flat; ears closed around slots; washer tracks
  fully supported; cable saddle tunnel open; inserts square; screws traverse the
  reamed bores; clamp centers miss all keepouts; phone seats without rocking.
- **UX benefit / deferred work:** datum labels, hand-force labels, closed ears,
  and above-board strain relief make installation self-explanatory. A hard screw
  travel stop and datum liners remain deferred until screw-head, case thickness,
  compressible pad thickness, and side-feature positions are measured.

### Job 03B — keyboard rear clamps

#### `keyboard_rear_clamp.stl`

- **Integrated enhancement:** 52 x 34 x 25 mm clamp with 5 mm base, 5 mm-thick x
  20 mm-high face, three triangular gussets, 42 x 10 x 0.8 mm face-pad recess,
  20 x 4.6 mm adjustment slot, 9.2 mm washer track, 2 mm scale, and `KB` mark.
- **Print:** `petg_general_0p4`; two copies, flat base on bed with face and
  gussets upward; no support.
- **Critical interface:** keyboard rear surface, selected adhesive pad, #8/M4
  board fastener, and M4 washer.
- **Pre-release gate:** job `03B` prerequisites and accepted pad material.
- **Post-print inspection:** gusset roots continuous, face square to base, slot
  open, scale readable, pad sits slightly proud, and clamp removes keyboard
  motion without case deflection.
- **UX benefit / deferred work:** scale makes both clamps repeatable and gussets
  resist peel. A captive/replaceable printed pad is deferred until pad thickness,
  hardness, adhesive, and keyboard contact geometry are selected.

### Jobs 03C1 and 03C2 — individually identified tag frames

All six frames share this integrated geometry: 78 x 78 x 4 mm; centered
55.4 x 55.4 mm artwork pocket; default 0.4 mm pocket depth; two 14 x 4.6 mm
Y-oriented slots at x=6 and x=72; 9.2 mm washer tracks entirely outside the
artwork; a 9 mm-diameter thumbnail scoop; and an `IDn +Y` orientation mark.
Print flat with `petg_general_0p4`, no support. Use measured matte tag stock and
100% artwork scale. A clear cover, snap bezel, or changed pocket depth is
deferred until stock/laminate thickness and camera glare are tested.

#### `tag_frame_ID0_55mm.stl` — world tag T0

- **Interface and location:** AprilTag ID0 / T0; board origin (8, 1) mm and
  78 mm-frame center (47, 40) mm.
- **Pre-release gate:** job `03C1`: `tag_stock_measured`, general clearance,
  setup hardware, geometry match, and QIDI Studio round trip.
- **Post-print inspection:** first-article standard—paper sits flat and removable,
  washers never cover artwork, `+Y` matches board coordinates, printed detection
  edge measures exactly 40 mm, and camera detection is reliable without shadow.
- **UX benefit:** this single frame qualifies artwork scale and pocket usability
  before the remaining five are printed.

#### `tag_frame_ID1_55mm.stl` — world tag T1

- **Interface and location:** AprilTag ID1 / T1; board origin (401, 1) mm and
  78 mm-frame center (440, 40) mm,
  intentionally left of the phone USB/cable path.
- **Pre-release gate:** job `03C2`, including `tag_artwork_scale_pass` and
  `tag_frame_first_article_pass`.
- **Post-print inspection:** ID/engraving match, `+Y` orientation, washer-artwork
  separation, and clear cable lane.
- **UX benefit:** unique molded ID prevents swapping a world datum during setup.

#### `tag_frame_ID2_55mm.stl` — world tag T2

- **Interface and location:** AprilTag ID2 / T2; board origin (8, 371) mm and
  78 mm-frame center (47, 410) mm.
- **Pre-release gate:** job `03C2` after accepted ID0.
- **Post-print inspection:** confirm correct ID, rear-left placement, `+Y`, flat
  paper, and unobstructed camera view.
- **UX benefit:** physical identity and direction survive paper replacement.

#### `tag_frame_ID3_55mm.stl` — world tag T3

- **Interface and location:** AprilTag ID3 / T3; board origin (524, 371) mm and
  78 mm-frame center (563, 410) mm.
- **Pre-release gate:** job `03C2` after accepted ID0.
- **Post-print inspection:** confirm correct ID, rear-right placement, `+Y`, flat
  paper, and no board-edge overhang.
- **UX benefit:** removes ambiguity between symmetric rear world references.

#### `tag_frame_ID4_55mm.stl` — keyboard tag K0

- **Interface and location:** AprilTag ID4 / K0; board origin (285, 270) mm and
  78 mm-frame center (324, 309) mm.
- **Pre-release gate:** job `03C2` after accepted ID0.
- **Post-print inspection:** confirm correct device association, `+Y`, artwork
  scale, washer clearance, and no interference with keyboard service access.
- **UX benefit:** molded ID ties the tag to the keyboard coordinate workflow.

#### `tag_frame_ID5_55mm.stl` — phone tag P0

- **Interface and location:** AprilTag ID5 / P0; board origin (420, 270) mm and
  78 mm-frame center (459, 309) mm.
- **Pre-release gate:** job `03C2` after accepted ID0.
- **Post-print inspection:** confirm correct device association, `+Y`, artwork
  scale, washer clearance, and clear phone/cable service path.
- **UX benefit:** molded ID prevents using the phone datum at a world-tag station.

### Job 03C3 — camera plate

#### `camera_plate_universal.stl`

- **Integrated enhancement:** 90 x 55 x 6 mm plate with 6.8 mm central passage,
  13.2 mm-across-corners x 3.2 mm-deep generic hex pocket, two 24 x 4.8 mm
  camera/strap slots, two 15 x 5.5 mm mast slots, 11 mm washer tracks, 2 mm
  graduations, and `CAM`, `MAST`, and `1/4` marks.
- **Print:** `petg_general_0p4`; flat as exported; no support.
- **Critical interface:** actual camera base, optical axis, cable exit, selected
  1/4-20 screw/nut or head, M5 mast hardware, and straps.
- **Pre-release gate:** `camera_mount_interface_measured`, general clearance,
  setup hardware, geometry match, and round trip.
- **Post-print inspection:** selected central hardware seats as intended; screw
  cannot bottom in the camera; straps do not cover controls/vents; M5 washers
  remain in tracks through full travel; optical center is recorded.
- **UX benefit / deferred work:** labels and scales support repeatable camera
  replacement. A truly captive head recess, finger access, cable strain relief,
  and optical-center engraving remain deferred until the camera and hardware are
  physically measured.

### Job 03D — calibration puck

#### `calibration_puck.stl`

- **Integrated enhancement:** 60 x 60 x 8 mm puck with 42 mm-long x 0.8 mm-wide
  x 0.8 mm-deep crosshairs, 3 mm-deep central conical divot from 4.4 to 0.6 mm
  diameter, two 12 x 4.6 mm slots, 9.2 mm washer tracks, 2 mm graduations, and
  `TCP R2` mark.
- **Print:** `petg_calibration_0p4`; flat as exported; skirt normally sufficient;
  no support and no ironing over the datum.
- **Critical interface:** robot tool tip, board flatness, board fasteners, and
  stable low-torque mounting.
- **Pre-release gate:** job `03D` requires the exact-profile
  `calibration_clearance_holes_coupon_pass`, geometry/profile gates, and QIDI
  Studio round trip.
- **Post-print inspection:** crosshair and divot clean, base does not rock,
  washer tracks intact, and repeated manual tip placement returns to the same
  center without visible divot growth.
- **UX benefit / deferred work:** a marked, isolated precision print makes TCP
  setup repeatable. A hardened replaceable datum and explicit wear-limit ring
  are deferred until tool-tip material, contact force, and acceptable datum wear
  are measured.

### Job 04A — shared compliant tool

#### `compliant_tool_body.stl`

- **Integrated enhancement:** 28 x 24 x 65 mm body plus a 1.2 mm locating pin;
  10.0 mm lower guide to z=44; 15.2 mm spring chamber above; opposing
  18 x 1.2 x 28 mm grip recesses; two 4.6 mm x 6.2 mm M3 insert pockets with
  tapered leads; asymmetric 2.6 mm locating pin.
- **Print:** `petg_precision_0p4`; upright as exported with 5 mm brim; no support;
  seam off grip flats and sliding bore.
- **Critical interface:** accepted gripper coupon, selected spring, stylus collar
  or rod flange, selected M3 inserts, and keyed cap.
- **Pre-release gate:** all job `04A` prerequisites, especially gripper/spring
  measurement and coupons, M3 insert, and
  `precision_m3_head_coupon_pass`.
- **Post-print inspection:** body straight; bore slides the accepted adapter
  without binding; chamber clean; grip faces parallel; inserts square; locating
  pin intact; hand-compressed plunger returns through the full required travel.
- **UX benefit / deferred work:** long production grip faces and keyed cap reduce
  setup ambiguity. A side travel window, positive jaw shoulder, or force scale
  is deferred until first-article strength, jaw collisions, and spring travel
  are demonstrated.

#### `compliant_tool_top_cap.stl`

- **Integrated enhancement:** 28 x 24 x 5 mm cap; 10.6 mm guide opening;
  14.2/10.0 mm annular spring groove 1.2 mm deep; asymmetric 3.1 mm pin socket;
  two 3.4 mm screw passages and 6.2 mm x 2.0 mm head recesses; `UP` mark.
- **Print:** `petg_precision_0p4`; two copies flat as exported; remove brim
  carefully and keep the spring groove clean.
- **Critical interface:** body locating pin, M3 x 10 mm button-head screws, M3
  inserts, spring, and sliding stylus/adapter.
- **Pre-release gate:** shared job `04A` gates, including the accepted
  `precision_m3_head_coupon_pass` result from job `00C`.
- **Post-print inspection:** only the correct face/orientation seats; both screws
  enter by hand; heads fit the recesses; spring seats in the annulus; center bore
  does not rub the moving member. Retain the second accepted cap as a spare.
- **UX benefit / deferred work:** physical key plus `UP` makes reversal difficult.
  Standard M3 washers do not fit the present 6.2 mm recess; washer seats or a
  different head recess require measured hardware and a repeated setup coupon.

### Job 04B — phone stylus route

#### `stylus_collar_9mm.stl`

- **Integrated enhancement:** 13.6 mm OD x 5.5 mm split collar, default 9.25 mm
  bore, 1.2 mm relief slit, and a horizontal 1.6 mm M2 pilot intended for a
  flush flat/nylon-tip grub screw.
- **Print:** `petg_adapter_0p4`; two copies, flat ring on bed, no support; verify
  the slit and pilot remain open.
- **Critical interface:** measured stylus, 15.2 mm tool chamber, selected pilot,
  and a short flush grub screw that cannot exceed the 13.6 mm envelope.
- **Pre-release gate:** `stylus_diameter_measured`,
  `stylus_gauge_coupon_pass`, `adapter_retention_method_selected`, and round trip.
- **Post-print inspection:** one collar qualifies retention and one is spare;
  collar slides inside the chamber, grips without stylus damage, screw remains
  below OD, and five service cycles do not split or strip the pilot.
- **UX benefit / deferred work:** positive, serviceable retention replaces an
  undocumented adhesive-only fit. Final bore and pilot remain measurement-gated;
  do not enlarge the collar beyond the chamber clearance.

### Job 04C — keyboard rod route

#### `rod_bushing_6_to_9mm.stl`

- **Integrated enhancement:** 8.85 mm sliding OD, 6.25 mm bore, 33.5 mm straight
  sleeve, 2.5 mm self-supporting taper, 13.5 mm x 2.8 mm flange, 38.8 mm total
  length, and 1.2 mm relief slit.
- **Print:** `petg_adapter_0p4`; two copies upright with flange at top and 8 mm
  brim; 100% infill; no support.
- **Critical interface:** measured 6 mm rod, 10 mm body guide, 15.2 mm chamber,
  spring, and selected retention method.
- **Pre-release gate:** `keyboard_rod_measured`,
  `adapter_retention_method_selected`, geometry match, and round trip.
- **Post-print inspection:** shaft straight, guide slide smooth, bore open, flange
  fully formed, taper free of unsupported droop, rod retention survives axial
  pull/twist, and spare matches the accepted first article.
- **UX benefit / deferred work:** tapered flange prints without a broad bridge
  and split sleeve permits tuning. A radial M3 thread is intentionally deferred:
  the 2.8 mm flange is too thin. Use measured interference/removable adhesive or
  redesign around verified short hardware rather than forcing a screw feature.

### Jobs 05A and 05B — phone TPU tips

#### `phone_clamp_tip_TPU_M4.stl`

- **Integrated enhancement:** 7.5 mm OD x 8 mm high rounded contact cap, 4.1 mm
  blind bore 5.8 mm deep, 4.8-to-4.1 mm flared 0.8 mm entry, and a 0.3 mm-deep
  seating witness at z=4.5.
- **Print:** `tpu95a_0p4`; bore opening on bed; one first article in `05A`, then
  three in `05B`; use a 3 mm brim only if the tip rocks.
- **Critical interface:** actual threaded M4 thumb/nylon screw and phone/case
  contact surface.
- **Pre-release gate:** calibrated dry TPU; then
  `phone_tpu_retention_coupon_pass` before `05B`.
- **Post-print inspection:** first-layer bore open, tip reaches witness depth,
  resists pull/twist on the actual screw, contact dome has no seam ridge, and
  installed pair applies broad contact without approaching the screen edge.
- **UX benefit / deferred work:** witness gives visible seating and the first
  article prevents a four-piece batch failure. Further wear grooves or texture
  are deferred because either could mark the phone or weaken the thin TPU wall.

### Jobs 05C and 05D — keyboard TPU tips

#### `keyboard_tip_TPU_6mm.stl`

- **Integrated enhancement:** 12 mm OD x 14 mm rounded tip, 6.25 mm blind bore
  9 mm deep, 6.9-to-6.25 mm flared 1 mm entry, and seating witness at z=8.1.
- **Print:** `tpu95a_0p4`; bore opening on bed; one route-specific first article
  in `05C`, then three in `05D`; optional 3 mm brim only if unstable.
- **Critical interface:** actual deburred 6 mm rod and keyboard key/contact load.
- **Pre-release gate:** keyboard route selected, rod measured, dry TPU profile
  calibrated, then `keyboard_tpu_retention_coupon_pass` before `05D`.
- **Post-print inspection:** bore open, full witness-depth seating, pull/twist
  resistance on actual rod, centered dome, no split after removal, and safe key
  actuation by hand before robot use.
- **UX benefit / deferred work:** staged first article and three-piece follow-up
  yield two installed tips and two total spares. A wear-limit groove remains
  deferred until real wear shows a safe location and depth.

### Job 06 — ASA mast diagnostics

#### `mast_socket_fit_test.stl`

- **Integrated enhancement:** 110 x 36 x 24 mm ladder with 20.2/20.5/20.8 mm
  square sockets, 4 mm floor, approximately 20 mm effective engagement, and
  1 mm-high entries enlarged by 2 mm at the mouth.
- **Print:** `asa_structural_0p4`; flat as exported, enclosed, 10 mm brim, same
  conditioned spool/profile as mast feet.
- **Critical interface:** actual extrusion cut from final stock, including corner
  radii, coating, burrs, and measured across-flats size.
- **Pre-release gate:** `asa_mast_socket_coupon_pass`.
- **Post-print inspection:** select the smallest socket that accepts 20 mm of
  extrusion by hand without wall spread, rocking, abrasion, or retained brim.
- **UX benefit / deferred work:** longer engagement exposes shrink/taper missed by
  a shallow ring. A one-bolt slit/clamp coupon is a future option if the first
  foot reveals clamp-compliance behavior not predicted by the rigid ladder.

#### `m5_nut_trap_fit_gauge.stl`

- **Integrated enhancement:** 26 x 90 x 30 mm production-axis gauge. Lower row:
  5.5 mm passages with 9.1/9.4/9.7 mm-across-corners hex traps, 5 mm deep, plus
  0.7 mm enlarged entries. Upper row: 5.3/5.5/5.7 mm passages with
  10/11/12 mm washer seats 0.8 mm deep.
- **Print:** `asa_structural_0p4`; flat as exported so passages and traps remain
  horizontal; use local support only if the first slicer preview requires it.
- **Critical interface:** actual M5 x 60 mm clamp bolt, nut, and washer.
- **Pre-release gate:** `asa_m5_nut_coupon_pass` and
  `asa_m5_clearance_coupon_pass`. The latter must record the selected horizontal
  M5 hole, selected base hole, `m5_washer_od_mm`, and washer-fit result from job
  `06`; the general PETG setup gauge is not valid for ASA.
- **Post-print inspection:** nut seats from the production face without splitting
  and cannot spin; bolt traverses the selected horizontal passage; washer sits
  flat without climbing the seat.
- **UX benefit / deferred work:** one coupon now represents nut, bore, washer,
  material, and print axis. Captive bolt-head recesses remain deferred until
  exact head diameter/height and tool access are measured.

### Jobs 07A and 07B — optional mast feet

#### `mast_foot_2020.stl`

- **Integrated enhancement:** 92 x 92 x 74 mm foot with 10 mm base, 48 mm tower,
  64 mm socket height, 20.5 mm square socket and 1 mm entry flare, 3 mm rear
  slit, four 16 mm tapered ribs, two rear-lug 5.5 mm clamp passages at z=34/58,
  9.4 mm hex traps 5 mm deep with 0.7 mm entries, four 5.5 mm base holes, 11 mm
  washer seats, and front-center witness.
- **Print:** `asa_structural_0p4`; flat base on bed, 10 mm brim, enclosed stable
  chamber; one first article `07A`, second only in `07B`.
- **Critical interface:** accepted 2020 extrusion, M5 x 60 clamp bolts/nuts,
  selected M5 washers, and the actual stand-base anchoring method.
- **Pre-release gate:** all job `07A` gates; then
  `mast_foot_first_article_pass` before `07B`.
- **Post-print inspection:** base flatness recorded; socket reaches full depth;
  ribs/slit/lugs have no cracks; nuts fully seat; bolts pass and clamp without
  contacting extrusion; alternate bolt tightening; inspect immediately and
  after 24 hours under preload.
- **UX benefit / deferred work:** first-article sequencing, entry relief,
  production-axis traps, paired bolts, and witness make assembly controlled.
  Captive head counterbores, bolt-order text, and a plumb scale remain deferred
  until selected heads, driver clearance, and stand alignment method are fixed.

## Change-control checklist for any further enhancement

Any geometry change after RC02-PRO-R1 must include all of the following in the
same revision:

1. Update the parameter or generator; never hand-edit an STL.
2. Regenerate STEP/STL, board model/layout, 3MF plates, sidecars, preview images,
   validation CSV, readiness report, manual, workbook, and SHA-256 manifest.
3. Confirm every configured STL exists exactly once in the release inventory and
   remove superseded names.
4. Re-run watertight/single-body/positive-volume checks and Plus4 safe-envelope
   validation.
5. Reopen every changed 3MF in QIDI Studio and inspect layer previews at all
   holes, pockets, keys, saddles, thin slits, and first-layer bores.
6. Reprint the exact-profile coupon for every changed interface. If a production
   feature changes, its coupon must change in the same commit/revision.
7. Update the revision marking and record why the previous release was rejected
   or superseded.

## Planned professional additions outside individual geometry

- Create one laminated or printable assembly card per job with plate image,
  quantity, material/profile, hardware bag, tightening order, inspection fields,
  and gate sign-off.
- Add a separate M3/M4/M5 fastener-length gauge covering the actual purchased
  screw range; do not overload structural part geometry with length rulers.
- Label hardware bags by job ID and part code. Keep accepted coupons with the
  corresponding spool/profile record.
- Maintain two service spares for wear TPU parts and one accepted spare tool cap.
- Add a maintenance log for paint-witness movement, TPU polishing/loosening,
  PETG creep, ASA cracking, tag damage, and calibration-divot wear.
