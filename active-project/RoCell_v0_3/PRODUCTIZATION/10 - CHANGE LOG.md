# Productization change log

This log records product-definition changes. It does not replace the design revision, measurement, lifecycle, or release records.

## 2026-09-01 — ABS-heavy print-material plan selected

- Selected QIDI ABS Rapido and its exact X-Plus 4 0.4 mm filament preset as the primary rigid material for 13 active jobs.
- Retained PETG only for split-adapter jobs 00D, 04B, and 04C and inactive fallback plate 03C3; retained TPU 95A for contact-tip jobs 05A-05D; retained ASA only for inactive fixed-mast jobs.
- Split the ABS work across tray, cradle, precision, general, and calibration processes so coupon evidence stays matched to production geometry.
- Recorded complete ABS preset data but did not mark physical qualification complete. Exact PETG, TPU, and ASA thermal values remain open until their physical spools and calibrated vendor presets are recorded.

## 2026-09-01 — provisional V1 pre-hardware freeze

- Added `config/v1_prehardware_configuration.json` with provisional states `CANDIDATE`, `CANDIDATE_SELECTED`, `OUT_OF_V1`, `OPEN`, and `PHYSICAL_QUALIFICATION_REQUIRED`.
- Fixed the printer target at QIDI Plus4, nominal 305 x 305 x 280 mm, with a provisional protected envelope of 295 x 295 x 275 mm.
- Fixed the board candidate at 610 x 457 x 18 mm and retained hand-drill fabrication; router/CNC remains outside the product workflow.
- Named PERIBOARD-409 keyboard and bare Galaxy A16 5G phone candidates.
- Named StarTech `R2CCR-1M-USB-CABLE`, Logitech C920e `960-001401`, Lee Spring `LP022J01S316`, and paired-2020 camera mast candidates for reference purchasing and qualification.
- Chose the 6 mm rod + printed bushing + TPU keyboard route as the V1 contact-tool candidate.
- Kept the phone-stylus route in intended V1 scope as `CANDIDATE_SELECTED` / `PHYSICAL_QUALIFICATION_REQUIRED`; changed diagnostic print job 00D from required to `phone_stylus_route` controlled.
- At that provisional-freeze stage, preserved `phone_stylus_route`, `keyboard_rod_route`, and `camera_mast_optional` as `true` scope selections in `config/measurement_record.json`. Those booleans did not constitute physical qualification or release.
- Added the issue register and hardware-arrival qualification plan. No physical or commercial release state changed.

## 2026-09-01 — arm-mounted camera intent recorded

- Recorded the user's intended arm-mounted camera architecture in `config/camera_architecture_decision.json`.
- Marked camera architecture as an engineering alignment hold because the exact arm-camera specification, carrier link/frame, mount geometry, mass/COM, cable route, and eye-in-hand calibration contract are absent from the current RC03 package.
- Set `camera_mast_optional` to `false`; retained the paired-2020 mast and Logitech camera only as an unqualified inactive fallback, so PETG job 03C3 and ASA jobs 06/07 are not selected. No camera geometry or powered vision behavior was released.

## Change-control rule

Update the machine-readable configuration and this log together when a candidate, scope boundary, or open decision changes. Hardware evidence belongs in the canonical controlled workflows; do not upgrade an item here to a release state.
