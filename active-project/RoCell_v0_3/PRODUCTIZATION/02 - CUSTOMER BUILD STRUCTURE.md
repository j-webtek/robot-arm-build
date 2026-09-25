# Customer build structure

The customer should see ten stages, not the internal qualification system. Each stage ends with a visible result and only three outcomes:

- **PASS — continue.**
- **FIX — return to the named action.**
- **STOP — do not continue or operate; use the named troubleshooting entry.**

The internal Steps 00-15 remain authoritative for engineering traceability.

## Stage 1 — Confirm this product fits the customer

**Maps to:** Product definition and current Step 00 prerequisites.

### Customer receives

- Start Here card.
- Compatibility table.
- Illustrated BOM and tool list.
- Workspace and safety requirements.
- Download/package revision.
- Offline `START ROCELL SETUP` installer/launcher and local-data notice.

### Customer actions

1. Match the exact QIDI Plus4, nozzle, computer, RoArm, keyboard, phone/case, cable, camera, and tool configuration to the supported table.
2. Confirm the required work surface, board space, ventilation, electrical supply, and robot exclusion area.
3. Inventory every purchased item, consumable, and tool before printing.
4. Install or open `START ROCELL SETUP` and run its clean-machine compatibility check.
5. Create one local Build Passport ID through the setup assistant.

### PASS

- Every supported component and tool is present and matches the listed revision or SKU.
- The setup assistant passes its computer/file check and creates the local Build Passport.

### FIX

- Use the Stage 1 compatibility, inventory, or installer recovery entry; replace an unsupported/missing item before continuing.

### STOP

- A device, route, material, printer, or software version is not supported.
- A required safety component or measurement tool is missing.

### Customer output

- Completed compatibility and inventory page in the Build Passport.

---

## Stage 2 — Verify the printer

**Maps to:** Customer subset of current Step 00.

### Customer receives

- One `PRINT FIRST` QIDI project.
- Exact material preparation card.
- Import/profile screenshots.
- Printed go/no-go card with acceptable and rejected examples.

### Customer actions

1. Verify the 0.4 mm nozzle and released build surface.
2. Prepare the exact released material using the stated drying method.
3. Open the tested QIDI project in the supported QIDI Studio version.
4. Confirm object count, orientation, scale, profile, supports/brim, and bed position without changing them.
5. Print the verification plate.
6. Cool it fully, inspect it, and perform each labeled go/no-go check.

### PASS

- All verification features pass the released simple checks.

### FIX

- Follow the named printer/material troubleshooting entry and reprint the verification plate.

### STOP

- Do not print production parts after a failed verification plate.

### Customer output

- Printer Verification page marked PASS.

---

## Stage 3 — Print, inspect, and sort the product

**Maps to:** Current Step 00 production, first-article, inspection, and kitting work.

### Customer receives

- Approximately seven to nine ordered QIDI projects for the fixed V1 route.
- One preview and print card per project.
- Illustrated part catalog.
- Milestone bag or tray labels.

### Customer actions

1. Print projects in the supplied order; keep each large station on its own plate.
2. Do not scale, auto-orient, move, or combine objects.
3. Let each plate cool before removal.
4. Remove only the supports and cleanup identified on that print card.
5. Match every part to its catalog image, part ID, revision, and quantity.
6. Perform the listed flatness, passage, insert, seam, and service-fit checks.
7. Put accepted parts in the named customer-stage bag or tray.
8. Put failed or uncertain parts in `HOLD`; never mix them with accepted parts.

### PASS

- All required printed parts and spares are accepted, identified, and sorted.

### FIX

- Reprint only through the named print-recovery entry.

### STOP

- Mixed revisions, unreadable IDs, datum sanding, unexplained warp, cracks, whitening, delamination, or an unlisted slicer change.

### Customer output

- Printed Parts page marked PASS with every part checked off.

---

## Stage 4 — Prepare the board and install the arm safety system

**Maps to:** Current Steps 01-02.

### Customer receives

- Released board specification.
- Letter tile guide and 24 x 36 alternative.
- One page explaining exactly which guide to use.
- Tile map and board-center audit.
- Exact anchor, fastener, drill, depth-stop, reinforcement, clamp, feet, anti-shift, and E-stop diagrams.

### Customer actions

1. Inspect the cut board against released size, thickness, flatness, bow, and damage limits.
2. Seal and cure the board using the released product and schedule, unless a prepared board is used.
3. Print one drill-guide format at Actual Size / 100 percent.
4. Verify every physical X/Y scale control before registration.
5. For Letter printing, use pages 4-12 only as the nine working tiles, overlap by the printed 12 mm, and match every registration ID.
6. Register the guide to FRONT, +Y, and all four board edges.
7. Transfer and independently audit exactly thirteen named centers.
8. Practice the released locator and anchor operations on a matching offcut.
9. Clamp and support the board; set the released positive depth stops.
10. Drill the four locator and nine anchor interfaces in the released sequence.
11. Inspect blind floors, the underside, and every center before installing hardware.
12. Install the released anchors and dry-fit all stations before bonding locator pins.
13. Install and cure locator pins at the released projection.
14. Install feet, reinforcement plate, factory clamp, anti-shift system, and E-stop/power cutoff.
15. Recheck board flatness, clearances, and E-stop behavior.

### PASS

- The board, thirteen interfaces, reinforcement, clamp, feet, anti-shift, and E-stop pass the Board Acceptance Card.

### FIX

- Use the explicit board repair matrix; repeat every affected measurement.

### STOP

- Scale/registration disagreement, wrong center, insufficient blind floor, breakout, spinning anchor, board bow, clamp movement, obstruction, or failed E-stop behavior.

### Customer output

- Board and Arm page marked PASS with required photos.

---

## Stage 5 — Assemble the keyboard station

**Maps to:** Current Steps 03-05.

### Customer receives

- `KEYBOARD` printed-parts tray.
- Exact hardware bags for master, slave, and device retainers.
- Exploded diagrams for all six board-retention positions.
- Master/slave seam and pad-contact close-ups.

### Customer actions

1. Identify `MASTER`, `SLAVE`, FRONT, and both padded sliders.
2. Place the left slider and park it fully rearward before installing its shared screw.
3. Seat the master on the round/radial locator pair by hand.
4. Install the three labeled hardware stacks in the released start/tighten order.
5. Confirm seating, board contact, engagement, no bottoming, and torque.
6. Place the right slider.
7. Confirm that the slave has no independent board locator pins; never drill or add them.
8. Seat the slave into the master seam by hand; do not pull the seam together with screws.
9. Install and tighten the three slave stacks in the released order.
10. Check seam gap, flushness, combined support plane, torque, and rocking.
11. Place the supported keyboard on its own feet.
12. Route the cable along the released path.
13. Set both sliders to the released contact indicator; do not use them to bow or locate the keyboard.
14. Complete the customer repeatability check using fixed visible datums.

### PASS

- Stations are seated and torqued; the seam is in limit; the keyboard does not rock, bow, lift a foot, or pinch its cable.

### FIX

- Use the named locator, seam, fastener, slider, pad, cable, or repeatability recovery entry and repeat the affected checks.

### STOP

- Forced locator, screw-closed seam, bottomed stack, stripped anchor, lifted base, slider bind, case distortion, or failed repeatability.

### Customer output

- Keyboard page marked PASS.

---

## Stage 6 — Assemble the phone and TCP station

**Maps to:** Current Steps 06-10.

### Customer receives

- `PHONE + TCP` printed-parts tray.
- Separate labeled bags for base, rail, TCP cartridge, phone clamps, cable tie, and soft tips.
- Exact supported-phone no-go overlay.
- Cable and clamp setting diagram.

### Customer actions

1. Seat the phone/TCP station on its round/radial locator pair.
2. Install only the TCP-side station retainer.
3. Seat the rail on both keys by hand.
4. Seat the `INSTALL` TCP cartridge in its only valid orientation.
5. Start and tighten the shared rail/station and cartridge screws in the released order.
6. Install the exact clamp screws, nuts, and accepted soft tips.
7. Verify rail flushness, cartridge play/height, engagement, torque, and nut retention.
8. Connect the exact USB cable to the supported phone in its released case state.
9. Seat the phone against its fixed datums.
10. Route the cable with the released bend radius, service loop, saddle, and tie setting.
11. Advance clamp tips to the released indicator or spacer; do not use subjective force.
12. Verify positive glass, button, camera, connector, and cable margins using the supplied overlay/checks.
13. Complete the phone repeatability and cable-disturbance checks.

### PASS

- Rail and cartridge remain seated, phone pose repeats, connector is unloaded, and every no-go margin is positive.

### FIX

- Use the named base, rail, cartridge, clamp, cable, or device-fit recovery entry; replace an incompatible printed or purchased part rather than forcing it.

### STOP

- Lifted rail, spinning nut, cartridge shift, cracked tower, glass/button/camera contact, strained connector, tight cable bend, or phone movement caused by clamping.

### Customer output

- Phone + TCP page marked PASS.

---

## Stage 7 — Install the reference tags

**Maps to:** Current Steps 11-12.

### Customer receives

- Exact tag stock and spare set.
- ID/location map for T0, T1, T2, T3, K0, and P0.
- Verified transfer guide instructions.
- Tag application tool and plain-language measurement worksheet.

### Customer actions

1. Remove the keyboard and phone; protect installed fixtures and cables from paper, pencil debris, and cleaner.
2. Reverify the physical transfer guide scale and registration.
3. Transfer only six tag centers and +Y orientation witnesses.
4. Remove all paper before adhesive work.
5. Verify tag ID, size, print scale, finish, and orientation before removing backing.
6. Clean the board using the released method and observe the stated drying time.
7. Apply one tag at a time with the registered application tool.
8. Burnish, remove the tool vertically, and inspect for lift, bubbles, damage, and yaw.
9. Measure each installed tag using the supplied method or fixture.
10. Remove and store the application tool after the sixth accepted tag; it does not remain installed.
11. Run the guided tag-map generation module in the already-installed setup assistant.

### PASS

- Six correct, matte, flat tags are within the released center, yaw, lift, and optical-plane limits.

### FIX

- Use the named transfer, cleaning, adhesion, ID/orientation, or measurement recovery entry; replace one failed tag and repeat every affected measurement.

### STOP

- Wrong ID, wrong orientation, scaled/glossy/damaged tag, paper left under adhesive, edge lift, or out-of-limit placement.

### Customer output

- Installed Tag Map page marked PASS.

---

## Stage 8 — Install and calibrate the camera

**Maps to:** Current Step 13.

### Customer receives

- Exact camera/support hardware bag.
- Fixed support placement diagram.
- Camera module in the already-installed `START ROCELL SETUP` launcher.
- Named calibration and FOV pose guide.

### Customer actions

1. Install the support at the released board/workspace datums.
2. Mount the camera with the released screw/strap stack and bottoming clearance.
3. Route the USB cable with the released service loop and strain relief.
4. Verify that cable disturbance does not move the camera.
5. Open the setup launcher and choose `Camera setup`.
6. Follow live framing, focus, exposure, and ChArUco capture guidance.
7. Capture the named FOV pose set; do not substitute repeated similar views.
8. Let the launcher calibrate, detect tags, and create the report.
9. Lock the accepted camera settings and support position.

### PASS

- The human-readable report is green and contains accepted calibration, pose coverage, tag visibility, and camera identity.

### FIX

- Use the launcher's named support, cable, focus/exposure, capture, calibration, tag, or retry recovery; export the local recovery bundle if the launcher cannot continue.

### STOP

- Camera movement, screw bottoming, focus/exposure drift, missing required tags, insufficient pose coverage, or failed reprojection limit.

### Customer output

- Camera Calibration page marked PASS.

---

## Stage 9 — Assemble and qualify the contact tool

**Maps to:** Current Step 14.

### Customer receives

- One released route only.
- Exact printed parts and hardware bag.
- Route-specific exploded diagram.
- Supplied/simple travel, force, retention, and TCP fixtures or methods.

### Customer actions

1. Confirm that every part belongs to the same released route.
2. Install inserts using the released temperature, depth, and fixture.
3. Assemble the spring, moving body, caps, adapter, and contact tip in the illustrated order.
4. Tighten fasteners to released values.
5. Cycle the tool through the released count and verify smooth travel and full return.
6. Measure travel and force at the named checkpoints.
7. Run the retention and creep tests using the supplied fixture/method.
8. Install the tool in the gripper and run guided TCP calibration.

### PASS

- Travel, return, force, retention, function, and TCP repeatability are in limit.

### FIX

- Use the route-specific assembly, insert, spring, adapter, retention, force, or TCP recovery entry; replace the named part when no customer repair is permitted.

### STOP

- Binding, coil bind, cap distortion, adapter or tip slip, crack, excessive force, or unstable TCP.

### Customer output

- Contact Tool page marked PASS.

---

## Stage 10 — Commission and begin normal use

**Maps to:** Current Step 15.

### Customer receives

- Safety and commissioning guide.
- Approved robot programs.
- Safe-zone and observer diagram.
- Final Build Passport checklist.
- Normal-use and maintenance quick start.

### Customer actions

1. Verify board, clamp, anti-shift, stations, hardware, cable routes, camera, tags, tool, and workspace condition.
2. Verify controller/firmware/program revisions.
3. Test the E-stop and confirm reset cannot restart motion automatically.
4. Remove the keyboard, phone, and contact tool; confirm the illustrated empty-fixture state.
5. Run the approved no-device/no-tool empty-motion program at the released reduced settings.
6. Check every clearance and cable state.
7. Install only the contact tool and repeat the empty-space check without devices.
8. Complete the released structural and repeatability proofs with the illustrated fixtures and load directions.
9. Reinstall only the supported device required for the next controlled contact test.
10. Position the observer at the released location with immediate E-stop access.
11. Run one controlled first-contact test at a time at released speed, force, and travel; remove or replace devices only as instructed between tests.
12. Confirm keyboard, phone, TCP, camera, and tool results.
13. Save the final report and mark this assembled unit `CUSTOMER COMMISSIONING PASS`.

### PASS

- Every commissioning check is green. Engineering design release and seller kit release were already completed by their responsible signers; the customer records only this unit's commissioning result.

### FIX

- Use the named static, E-stop, program, clearance, proof, camera/tag, tool, or contact-test recovery; repeat all invalidated checks before another contact attempt.

### STOP

- Failed E-stop, unexpected restart, collision risk, cable tension, movement, crack, out-of-limit proof, camera/tag loss, or contact outside the released target.

### Customer output

- Build Passport with `CUSTOMER COMMISSIONING PASS` and normal-use eligibility for this unit; it is not a design-approval or product-safety certification by the customer.
