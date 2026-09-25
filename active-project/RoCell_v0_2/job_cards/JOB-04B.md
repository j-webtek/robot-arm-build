# Job 04B - Two phone-route stylus collars for thin-wall retention qualification and one spare

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `phone_stylus_route` / `route` |
| Kit | `KIT-TOOL-PHONE` |
| Plate | `04B_PETG_phone_stylus_adapters.3mf` |
| Plate SHA-256 | `4f23eb2f4dcdd1b74458da5b1dd4077fb4da578030158055d60e3a59f49258af` |
| Profile | `petg_adapter_0p4` / `5addad813637abbe2dbc969afe8fde8637973498ff1f2439e590e070d62a2308` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.12 mm |
| Plate envelope | 33.6 x 13.6 x 5.5 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `stylus_collar_9mm.stl` | 2 | Flat flange on bed; split and radial pilot open | `041b31a9256250365eb8995a7ce42d3cb38875f75d0cc164228d3feaf0fa4637` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `stylus_diameter_measured` | **NOT_TESTED** | `{"diameter_mm": null, "measurement_locations": null, "stylus_model": null}` |
| `stylus_gauge_coupon_pass` | **NOT_TESTED** | `{"excess_play_result": null, "selected_nominal_mm": null, "sliding_fit_result": null}` |
| `adapter_retention_method_selected` | **NOT_TESTED** | `{"hardware_or_adhesive_spec": null, "retention_method": null, "route": null, "thread_pilot_selection": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Measured stylus, selected M2 screw or removable retaining method, pull gauge.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_adapter_0p4`: 4 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Use an 8 mm brim for the upright rod bushing; skirt is sufficient for the short collar.
- Dimensional controls: Calibrate elephant-foot compensation so split bores remain open at the first layer.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Check bore, split and thin-wall pilot. Set projection, then quantify pull retention and repeat cycles; inspect after 24-hour creep and verify capacitive function.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `stylus_collar_retention_pass`, `stylus_function_pass`.

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
