# Job 03C1 - ID0 tag frame first article with isolated artwork and washer zones

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-VISION-TAG` |
| Plate | `03C1_PETG_tag_frame_first_article.3mf` |
| Plate SHA-256 | `c49ef0465c90419dbb4e115d8493039ae78b852f48ac7eca887e21d72c0e3315` |
| Profile | `petg_general_0p4` / `ecd7e9e90881087b4ef04779c3717bc972489d689924d8602b5cae9d4855408c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 78.0 x 78.0 x 4.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `tag_frame_ID0_55mm.stl` | 1 | Flat as exported; ID0 and +Y readable | `5ef9601731298f7f674cd21ec9c0c6d3403db1f10e0e1f279bcceb9923034758` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `tag_stock_measured` | **NOT_TESTED** | `{"stock_thickness_mm": null, "stock_type": null, "tile_height_mm": null, "tile_width_mm": null}` |
| `general_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"m3_selected_mm": null, "m4_or_board_screw_selected_mm": null, "m5_selected_mm": null}` |
| `setup_hardware_coupon_pass` | **NOT_TESTED** | `{"camera_hex_ac_mm": null, "fit_result": null, "m3_head_recess_d_mm": null, "m4_washer_od_mm": null, "m5_washer_od_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: ID0 paper tile, matte tape, two screws/washers, ruler.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off unless a job override says otherwise. Bed adhesion: Clean textured PEI; use a 5 mm brim only after observed corner lift.
- Dimensional controls: Use calibrated elephant-foot and XY-hole compensation from the diagnostic coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Verify the 55.4 mm pocket, 40.0 mm detection edge, thumbnail scoop, +Y orientation, flatness, and complete washer isolation from artwork.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `tag_artwork_scale_pass`, `tag_frame_first_article_pass`.

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
