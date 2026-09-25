# Job 00A Print and Fit Review

Build ID: `2026-09-01_CELL-A`  
Printer: QIDI Plus4, 0.4 mm nozzle  
Material/process: QIDI ABS Rapido / `abs_rapido_tray_structural_0p4`  
Review date: 2026-09-02

## Recorded production result

- All four Job 00A coupons completed.
- Operator-reported actual consumption: **slightly over 100 g**.
- Operator-reported actual duration: **approximately 6 hours**.
- Operator physically confirmed the keyboard remained level in the corner coupon.
- No gross warp, crack, layer separation, missing section, or forced deformation is visible in the retained photographs.
- Minor top-surface/toolpath texture and localized roughness at some hole/recess rims are acceptable for continued coupon testing.

## Accepted result

### Keyboard front-left corner fit — PASS

The actual keyboard front-left corner seated within both printed datum walls without force. The operator confirmed that the keyboard remained level, with no observed binding or interference. Record the selected compensation as `0.0 mm`.

Primary evidence: `../photos/00A-05_keyboard_fit_primary.jpg`  
Supporting evidence: `../photos/00A-06_keyboard_fit_support.jpg`  
Coupon condition: `../photos/00A-04_keyboard_corner_coupon.jpg`

This establishes corner clearance only. It does not measure an exact clearance or validate the final direct-board support plane.

## Additional accepted results

### M4 washer ladder — recess selection complete

Photo `00A-07_washer_middle_recess_provisional.jpg` shows the actual M4 production washer in the middle recess, identified by controlled CAD order as `W9.2`. The operator subsequently confirmed that this same washer fits all three recesses well and explicitly waived caliper metrology for this prototype build. **`OD9.2` is retained as the final production selection** because it is the photographed candidate, matches the current controlled CAD, and provides a useful service margin for easy assembly.

### M4 clearance ladder — clearance selection complete

Photos `00A-08_clearance_4p4_actual_m4_alt_view.jpg` and `00A-09_clearance_4p4_actual_m4_pass.jpg` show the actual M4 station screw in the `4.4 mm` candidate. The operator confirmed that it passed through cleanly and that no smaller candidate passed. Therefore the selected smallest free-passing tray-profile hole is **`4.4 mm`**.

The production station holes remain at the controlled `4.6 mm` diameter. That deliberate `+0.2 mm` service margin over the verified smallest passing coupon makes hand assembly more tolerant while the dowel pair—not the retention screws—controls station position.

The operator authorized a prototype functional-fit waiver instead of caliper measurement. The recorded `4.0 mm` screw major diameter is the nominal M4 designation and is explicitly an assumption, not a measured value. The demonstrated physical passage result remains the controlling evidence.

### Station locator ladder

The actual nominal 6 mm production dowel was tested in the controlled board-locator rows. The retained photograph shows it seated in `BOARD-R 6.2`, and the operator separately confirmed that the same pin fits `BOARD-S 6.2`. The selected production pair is therefore **6.2 mm round socket + 6.2 mm radial-slot width**, with the controlled **10.0 mm slot length**.

Primary round-socket evidence: `../photos/00A-10_locator_board_round_6p2_pass.jpg`  
Radial-slot evidence: operator confirmation in the active Codex build task.

The operator authorized the same prototype functional-fit waiver used for the M4 hardware checks. Pin caliper measurements, numerical lateral-play measurement, 20 repeated cycles, and inversion-retention testing were not performed and are not represented as measured results. The actual pin inserted by hand in both selected features; no cracking or whitening is visible in the retained photograph or was reported for the slot. `keyboard_station_registration_coupon_pass` is accepted as **PASS under this explicit prototype waiver**.

The seam `SR/SW` section is retained for later testing with the actual printed master posts after Job 01; it is not selected with the 6 mm pins.

## Label nonconformance — redesign required

The small, shallow black-on-black engravings are not reliably readable on the physical coupons. This is a real model/user-interface defect rather than only a photography issue. The fit geometry printed successfully, so the current physical coupons remain usable by controlled position order; they do not need to be reprinted solely to finish the present tests.

Next CAD revision requirements:

- Raised identification, approximately `0.6 mm` high (three 0.20 mm layers).
- Larger characters with printer-safe stroke widths.
- Labels kept clear of holes, recesses, slots, and all keyboard datum/contact surfaces.
- Explicit part/row identity and unambiguous candidate values.
- Visual verification in the sliced preview before any revised diagnostic plate is released.

## Photo disposition

Photo 3 is retained as washer-recess detail only; it is not required as a separate level/flatness photograph. Operator physical observation is the source for the level statement.

## Current Job 00A disposition

- Print completion: **accepted**.
- Keyboard corner gate: **PASS**.
- Tray M4 clearance/washer gate: **PASS under operator-authorized prototype functional-fit waiver**; nominal M4 diameter `4.0 mm` assumed, tested smallest free hole `4.4 mm`, and selected washer recess `OD9.2`.
- Keyboard station locator gate: **PASS under operator-authorized prototype functional-fit waiver**; selected `BOARD-R 6.2` and `BOARD-S 6.2` with the controlled `10.0 mm` slot length.
- All three mapped Job 00A post-print gates are now PASS. The controlled lifecycle record has advanced from `PRINTED` to **`POSTPRINT_PASS`**.

## As-built traceability and label-only deviation

The physical coupons in this evidence set were printed from the pre-correction label geometry. Their released-at-print hashes were:

| Artifact | As-built SHA-256 |
|---|---|
| `00A_ABS_keyboard_station_fit_tests.3mf` | `343e02f1aa6105032652c054c4662aea2f26f1d62f1e986f5f48246baff449de` |
| `keyboard_corner_fit_test.stl` | `782ce3b7a62afd0bf21bcb1f524788aa0eeabb07a27ee6998a2cde75308b2423` |
| `station_locator_fit_gauge.stl` | `64d25cf2763b72506eb03b2ceb80e463b843abfd9200d03a3e5a701267eb2868` |
| `hardware_fit_gauge.stl` | `beb9ecb2cd3b6020c998dc74d284e7639af7ac7b5040f7ab857d9c3fc3212c26` |
| `m4_washer_fit_gauge.stl` | `8594207f90b7b1e08a7e91e665fcc29d9a92100835ad2fed3fa172585cb4d08f` |

After this review, the source was revised to replace unreadable shallow engravings with larger raised labels. No tested hole, recess, slot, pocket, candidate value, or feature center was changed. The keyboard identifier was moved to a new external tab that does not touch either keyboard datum or the keyboard footprint.

Engineering disposition: **accepted label-only deviation**. The current physical coupons remain valid for the fit tests documented here. Any future Job 00A reprint must use the current regenerated plate and current hashes in `job_cards/JOB-00A.md`.
