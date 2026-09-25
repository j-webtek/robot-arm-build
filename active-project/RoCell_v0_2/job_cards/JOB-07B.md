# Job 07B - Second camera mast foot after first-article acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `optional` |
| Kit | `KIT-MAST` |
| Plate | `07B_ASA_mast_foot_second.3mf` |
| Plate SHA-256 | `63c6e356e24b395b53d4780ba27e248d6b6a836d0920af1070d2719b9b7f8bc3` |
| Profile | `asa_structural_0p4` / `7f5a63b82b79566c55df616753ef9acc31e6a172a2689b726498aa2cb82c7a22` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | ASA / 0.4 mm / 0.24 mm |
| Plate envelope | 92.0 x 92.0 x 74.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `mast_foot_2020.stl` | 1 | Flat 92 x 92 mm base on bed; socket vertical | `2b6384b63a5b191ef88ae5590b50ffb5cd0c64d2102b3145b8336b2fb901faa5` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `asa_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "chamber_condition": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `asa_mast_socket_coupon_pass` | **NOT_TESTED** | `{"extrusion_x_mm": null, "extrusion_y_mm": null, "fit_result": null, "selected_socket_mm": null}` |
| `asa_m5_nut_coupon_pass` | **NOT_TESTED** | `{"nut_across_flats_mm": null, "nut_thickness_mm": null, "retention_result": null, "selected_hex_mm": null}` |
| `asa_m5_clearance_coupon_pass` | **NOT_TESTED** | `{"bolt_major_diameter_mm": null, "m5_washer_fit_result": null, "m5_washer_od_mm": null, "selected_base_hole_mm": null, "selected_horizontal_hole_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `mast_foot_first_article_pass` | **NOT_TESTED** | `{"base_flatness_mm": null, "bolt_clamp_result": null, "crack_result_after_24h": null, "initial_crack_result": null, "job_id": null, "nut_fit_result": null, "socket_fit_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted first foot, second extrusion/foot hardware and crossbar.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `asa_structural_0p4`: 6 walls, 6 top / 6 bottom layers, 45% gyroid infill.
- Supports: build-plate only under transverse bores if needed. Bed adhesion: 10 mm brim, enclosed printer, stable chamber, and no drafts.
- Dimensional controls: Use the ASA socket and nut coupons from the same spool before the first full foot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Repeat 07A checks, label feet A/B, assemble the pair, then verify matched seating, crossbar level, plumb witness lines and stand stability.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `mast_second_foot_postprint_pass`, `mast_pair_installation_pass`.

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
