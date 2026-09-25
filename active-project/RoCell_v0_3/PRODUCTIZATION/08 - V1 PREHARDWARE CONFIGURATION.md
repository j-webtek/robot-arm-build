# V1 pre-hardware configuration

This is the short operator-facing summary of the provisional V1 target. The controlling data is `config/v1_prehardware_configuration.json`; the rationale is in `07 - PHASE 1 CONFIGURATION FREEZE DECISIONS.md`.

## What V1 is targeting

- QIDI Plus4, nominal 305 x 305 x 280 mm, with a provisional 295 x 295 x 275 mm protected envelope.
- QIDI ABS Rapido as the primary rigid material for the 13 active jobs, using the confirmed X-Plus 4 0.4 mm filament preset plus five exact job-family processes.
- PETG retained only for split-adapter jobs 00D/04B/04C and inactive fallback plate 03C3; TPU 95A retained for contact-tip jobs 05A-05D; ASA retained only for the inactive fixed-mast fallback.
- A 610 x 457 x 18 mm birch-plywood candidate board, hand drilled from a released 1:1 guide; no router or CNC.
- Perixx PERIBOARD-409 U USB-A English-US black keyboard, measured as the exact purchased unit.
- Bare Samsung Galaxy A16 5G, candidate variant SM-A166B; no case.
- StarTech `R2CCR-1M-USB-CABLE` right-angle USB-C cable.
- User-intended primary camera: arm-mounted per its intended specification. That specification is not present in the current RC03 package, so camera geometry and operation remain on engineering alignment hold.
- Retained inactive fallback camera candidate: Logitech C920e (`960-001401`) on a paired 2020 mast, still physically unqualified and not a substitute for the missing arm-camera specification.
- Shared compliant tool using Lee Spring `LP022J01S316`, a 6 mm keyboard rod, printed bushing, and replaceable TPU tip.
- A second selected V1 evaluation route using an exact-to-be-selected passive capacitive stylus, job 00D gauge, job 04B collar, and the shared compliant body.
- Customer-printed plastic plus a seller-supplied, labeled compatibility/safety/hardware pack.

## What V1 is not targeting

- Phone cases or alternate keyboard/camera/device variants.
- Router or CNC board fabrication.
- Customer selection of anchors, fastener lengths, safety wiring, camera mounts, or contact limits.

## What remains unresolved

Board stock/finish/anchors/reinforcement, exact safety assembly, exact PETG and TPU products/lots, any later fallback ASA, other consumable SKUs, all supported software/firmware versions, phone host/power source, exact passive stylus SKU, the exact arm-camera specification and mount/calibration contract, and product duty/life claims remain `OPEN`. The QIDI ABS Rapido preset data is selected, but its coupons, first articles, and production plates remain `PHYSICAL_QUALIFICATION_REQUIRED`. Every named hardware item is a `CANDIDATE`; the phone-stylus route is `CANDIDATE_SELECTED` and also requires physical qualification.

Do not use this file as purchasing approval for a production lot or as authority to print/build/sell. Purchase only the small reference quantities authorized by the qualification plan, quarantine received items, and record evidence through the canonical workflows. A selected route boolean is scope intent, not evidence.
