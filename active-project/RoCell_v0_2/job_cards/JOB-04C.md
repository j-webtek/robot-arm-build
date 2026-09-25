# Job 04C - Two keyboard-route rod bushings for retention qualification and one spare

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `keyboard_rod_route` / `route` |
| Kit | `KIT-TOOL-KB` |
| Plate | `04C_PETG_keyboard_rod_adapters.3mf` |
| Plate SHA-256 | `feb287014ddd1de53dcbd904953614f507ad0ab353590c75d0d2f0098160230f` |
| Profile | `petg_adapter_0p4` / `5addad813637abbe2dbc969afe8fde8637973498ff1f2439e590e070d62a2308` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.12 mm |
| Plate envelope | 38.5 x 13.5 x 38.8 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `rod_bushing_6_to_9mm.stl` | 2 | Upright on flange with 8 mm brim | `c30bee2a303f025e94b21e1cf2c5639babbf5d75d3bb008711ea86b5e8160d63` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `keyboard_rod_measured` | **NOT_TESTED** | `{"diameter_mm": null, "length_mm": null, "material": null, "measurement_locations": null}` |
| `adapter_retention_method_selected` | **NOT_TESTED** | `{"hardware_or_adhesive_spec": null, "retention_method": null, "route": null, "thread_pilot_selection": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Deburred 6 mm rod, selected retaining method, pull gauge.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_adapter_0p4`: 4 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Use an 8 mm brim for the upright rod bushing; skirt is sufficient for the short collar.
- Dimensional controls: Calibrate elephant-foot compensation so split bores remain open at the first layer.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Check bore and split, press fit without cracks, set 30-40 mm projection, then quantify pull retention and 24-hour creep. No radial M3 screw is permitted in the thin flange.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `rod_bushing_retention_pass`.

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
