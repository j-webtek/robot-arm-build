# RoCell consumer productization — start here

This folder is the execution plan for turning `RC03-INT-R1` from a controlled engineering build into an easy self-print product.

## Product target

The first release target is **RoCell RC03 Self-Print Hybrid Kit for QIDI Plus4**.

The intended customer:

- owns a QIDI Plus4 with a verified 0.4 mm nozzle;
- can use QIDI Studio, a hand drill, calipers, and a torque driver;
- can print, clean, and identify ordinary FDM parts;
- does not need CAD, code, JSON, hash management, or engineering judgment;
- uses no router or CNC;
- follows one supported keyboard, phone/case/cable, camera, tool, board, and hardware configuration.

The recommended first commercial format is a **self-print hybrid kit**. The customer prints the plastic parts; the seller supplies a labeled pack containing the exact fasteners, anchors, pins, inserts, nuts, washers, tags, pads, spring, safety components, and reinforcement plate. The customer supplies the listed printer, filament, robot, devices, and board. A download-only edition may follow after the same BOM has been validated, but it will create more sourcing and support risk. A predrilled-board edition can remove the highest-risk irreversible operation later.

## Current state

The controlled package is digitally consistent but physically `UNRELEASED`.

- Print readiness: `5 READY / 15 WAITING / 4 NOT_SELECTED`; the ABS diagnostic jobs are available under their recorded prototype-waiver/profile gates, the phone-stylus and keyboard-rod routes are selected for qualification, and the fixed-mast fallback remains unselected. A `READY` print job is not a product or build release.
- All nine board-fastener selections are unresolved.
- The reinforcement plate, E-stop system, camera support, tool route, and final robot programs are not released as one customer configuration.
- The current 16 build steps are strong engineering work instructions, not yet a simple customer manual.

Do not advertise, distribute, or describe the current package as a released product.

## Two-role rule

You will work in two separate roles:

1. **Engineer:** select, measure, test, and release every product decision.
2. **First customer:** build from a clean release-candidate package without using private engineering knowledge.

If the first-customer version of you needs an unstated answer that the engineer version knows, record a documentation defect. Do not silently supply the answer.

## What “easy” means

The customer package is easy only when all of the following are true:

- one supported V1 configuration is clearly named;
- no customer-facing field says `as specified`, `measured set`, `responsible engineering approval`, or similar;
- the customer never chooses an anchor, bore, fastener length, camera mount, or safety limit;
- prepared QIDI projects can be printed without moving, scaling, or reorienting models;
- every printed part and hardware bag has a visible ID;
- every irreversible or safety-relevant action has a close-up image, exact tool, limit, and recovery instruction;
- every check ends in `PASS`, `FIX`, or `STOP`;
- camera setup and final validation run through guided launchers rather than a normal command-line workflow;
- a customer can finish without CAD edits, source-file inspection, or undocumented support.

## Follow this order

1. Read [01 - END-TO-END PRODUCTIZATION ROADMAP.md](<01 - END-TO-END PRODUCTIZATION ROADMAP.md>).
2. Freeze the product in Phase 1 before rewriting the complete customer manual.
3. Use [02 - CUSTOMER BUILD STRUCTURE.md](<02 - CUSTOMER BUILD STRUCTURE.md>) to convert the internal 16 steps into ten customer stages.
4. Apply [03 - CUSTOMER INSTRUCTION AND FILE STANDARD.md](<03 - CUSTOMER INSTRUCTION AND FILE STANDARD.md>) to every customer-facing file.
5. Run [04 - FIRST-CUSTOMER VALIDATION PLAN.md](<04 - FIRST-CUSTOMER VALIDATION PLAN.md>) from a clean release candidate.
6. Keep [05 - RELEASE SCORECARD.md](<05 - RELEASE SCORECARD.md>) current. A phase closes only when every required row is evidenced.
7. Use [06 - CURRENT STEP CONVERSION MATRIX.md](<06 - CURRENT STEP CONVERSION MATRIX.md>) to ensure none of the existing engineering requirements are lost.
8. Use [07 - PHASE 1 CONFIGURATION FREEZE DECISIONS.md](<07 - PHASE 1 CONFIGURATION FREEZE DECISIONS.md>) as the current pre-hardware decision record; retain [07 - PHASE 1 V1 PRODUCT DEFINITION WORKSHEET.md](<07 - PHASE 1 V1 PRODUCT DEFINITION WORKSHEET.md>) as the underlying worksheet/history.
9. Read [08 - V1 PREHARDWARE CONFIGURATION.md](<08 - V1 PREHARDWARE CONFIGURATION.md>), work the blockers in [09 - ISSUE REGISTER.csv](<09 - ISSUE REGISTER.csv>), record scope changes in [10 - CHANGE LOG.md](<10 - CHANGE LOG.md>), and receive/test candidates through [11 - HARDWARE ARRIVAL AND QUALIFICATION PLAN.md](<11 - HARDWARE ARRIVAL AND QUALIFICATION PLAN.md>).

## Productization flow

`Define V1 -> close engineering blockers -> qualify prints/board/safety/software -> engineer proof build -> finalize customer kit/package -> first-customer build -> external beta -> commercial release`

Any failed gate returns to the phase that owns the failed requirement. Do not repair a release problem only in customer wording.

## Start with these five actions

1. Close the `OPEN` and `PHYSICAL_QUALIFICATION_REQUIRED` rows in the configuration decision record and issue register.
2. Receive and qualify the named keyboard, bare phone, cable, camera/support, keyboard tool route, printer, board, and QIDI ABS Rapido candidates; select the still-open anchor system, E-stop, exact PETG/TPU spools, any later fallback ASA, and software platform.
3. Purchase or identify the exact physical examples that will become the reference hardware.
4. Complete the nine-row `FASTENER_MAP.csv` using scrap-board qualification.
5. Release the reinforcement-plate and power-cutoff designs before production printing.

Until those actions are complete, improve only planning, engineering controls, and known accuracy defects. Avoid polishing customer instructions for hardware that may still change.
