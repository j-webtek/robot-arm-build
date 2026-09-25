# Job 00B - Phone width, horizontal M4 insert, cable-saddle, and washer tests using the exact cradle profile

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00B_PETG_phone_profile_fit_tests.3mf` |
| Plate SHA-256 | `8df377ad10c14faa25363c9b48b95b021ef0474aad656b0ea7001c201fa382f9` |
| Profile | `petg_cradle_0p4` / `874f2e964792b58d533f2fd659f5ad595af5759c7acba9d2244d5fc5b20e841c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 216.0 x 80.0 x 16.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_width_fit_test.stl` | 1 | Flat as exported | `96aaf6fe04d5be4ab6eb9c01f810583198dcc250f86f5d316134f385ce633c77` |
| `m4_horizontal_insert_fit_gauge.stl` | 1 | Flat as exported; production-axis bores horizontal | `47b228a28e1847036e8ebbac43e3d926d815aed85bf14d3a0d1fb07050a3d414` |
| `cable_tie_saddle_fit_gauge.stl` | 1 | Flat as exported; saddles upward | `c00cd708d208909996e38fab9653f2b991335407dbd38fbb7d7089fc98232158` |
| `m4_washer_fit_gauge.stl` | 1 | Flat as exported; W8.8/W9.2/W9.6 labels upward | `8594207f90b7b1e08a7e91e665fcc29d9a92100835ad2fed3fa172585cb4d08f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_cradle_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual phone/case, M4 inserts/washers, USB cable and selected ties.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: build-plate only under horizontal clamp bores if needed. Bed adhesion: 5 mm brim recommended around the asymmetric cradle and clamp towers.
- Dimensional controls: Use the horizontal M4 insert coupon; ream the 4.6 mm passages by hand after printing.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Record phone hand-fit, selected horizontal insert pocket, insert squareness/spin resistance, selected saddle, cable bend clearance, and the smallest flat-seating M4 washer recess.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_width_coupon_pass`, `m4_horizontal_insert_coupon_pass`, `cable_tie_saddle_coupon_pass`, `cradle_m4_washer_coupon_pass`.

## Signoff

| Record | Entry |
|---|---|
| Spool brand / lot / dry record | ______________________________ |
| QIDI Studio project / version | ______________________________ |
| Printed date / operator | ______________________________ |
| Measured values / tool ID | ______________________________ |
| Evidence folder / photo IDs | ______________________________ |
| Result | [ ] PASS  [ ] REWORK  [ ] QUARANTINE |
| Inspector / date | ______________________________ |
