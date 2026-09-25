# Job 03A - Phone cradle with closed mounting ears and raised cable saddle

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-PHONE` |
| Plate | `03A_PETG_phone_cradle.3mf` |
| Plate SHA-256 | `4de7e4f3e5161e070e629d4e408fecdc307a33639ed3791bc98a0c3fb8119e5b` |
| Profile | `petg_cradle_0p4` / `874f2e964792b58d533f2fd659f5ad595af5759c7acba9d2244d5fc5b20e841c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 117.3 x 172.8 x 20.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_cradle_a16.stl` | 1 | Flat base on bed; USB mark toward plate front | `a6a9af5f1c350002bee9752ac4aa1f30642138d3e656f903ef064baefd2e9c18` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_cradle_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `phone_dimensions_measured` | **NOT_TESTED** | `{"camera_bump_envelope_mm": null, "case_installed": null, "device_model": null, "length_mm": null, "thickness_mm": null, "width_mm": null}` |
| `phone_side_features_measured` | **NOT_TESTED** | `{"minimum_keepout_margin_mm": null, "right_side_keepouts_from_bottom_mm": null, "selected_clamp_centers_from_bottom_mm": null}` |
| `phone_cable_measured` | **NOT_TESTED** | `{"connector_thickness_mm": null, "connector_width_mm": null, "minimum_bend_radius_mm": null, "selected_tie_width_mm": null, "straight_projection_mm": null}` |
| `phone_width_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "lateral_clearance_mm": null, "rail_height_result": null}` |
| `m4_horizontal_insert_coupon_pass` | **NOT_TESTED** | `{"insert_length_mm": null, "insert_od_mm": null, "installed_depth_mm": null, "reamed_passage_mm": null, "retention_result": null, "selected_pocket_mm": null}` |
| `cable_tie_saddle_coupon_pass` | **NOT_TESTED** | `{"cable_clearance_result": null, "feed_result": null, "saddle_crack_result": null, "selected_slot_width_mm": null, "selected_tie_width_mm": null}` |
| `cradle_m4_washer_coupon_pass` | **NOT_TESTED** | `{"actual_washer_od_mm": null, "fit_result": null, "m4_washer_od_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Phone/case, cable, 2 M4 inserts, 2 thumb screws, accepted TPU tips, 4 board screws/washers, ties.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: build-plate only under horizontal clamp bores if needed. Bed adhesion: 5 mm brim recommended around the asymmetric cradle and clamp towers.
- Dimensional controls: Use the horizontal M4 insert coupon; ream the 4.6 mm passages by hand after printing.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect flatness, closed mounting ears, rails, towers and raised cable saddle. Install inserts square, verify all keepouts, then complete ten phone cycles without button contact.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_cradle_postprint_pass`, `phone_fixture_assembly_pass`.

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
