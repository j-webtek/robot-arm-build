# Job 03C2 - Remaining ID1-ID5 tag frames after first-article acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-VISION-TAG` |
| Plate | `03C2_PETG_tag_frames_remaining.3mf` |
| Plate SHA-256 | `0ff8bff94b0a1bb09bb9f6a5bf50a8ded326c1cd9ae79e79aa3188f38fe18dcb` |
| Profile | `petg_general_0p4` / `ecd7e9e90881087b4ef04779c3717bc972489d689924d8602b5cae9d4855408c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 244.0 x 161.0 x 4.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `tag_frame_ID1_55mm.stl` | 1 | Flat as exported; ID1 and +Y readable | `e0abf77eec5661404b9776d84090b0f9d60234c0b9655d5670aab756da242742` |
| `tag_frame_ID2_55mm.stl` | 1 | Flat as exported; ID2 and +Y readable | `9aad4d845438f978a565afeb6b67f0cd8d24e9fe70a0bffdc6efb67b5d56bbf9` |
| `tag_frame_ID3_55mm.stl` | 1 | Flat as exported; ID3 and +Y readable | `e3acb03f9d9f6bd6b7ce6493551ad4fdccd78ea69c3a55c68eedc82e2bfd145d` |
| `tag_frame_ID4_55mm.stl` | 1 | Flat as exported; ID4 and +Y readable | `94aeecbe6349d9f7587772b1025e6de6f7df2033f9163f737230b0417f434a9c` |
| `tag_frame_ID5_55mm.stl` | 1 | Flat as exported; ID5 and +Y readable | `35339aecc93f8a394a555d959c66e9da67a21f1e4fe8f313759dc3798c7a1c6b` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `tag_stock_measured` | **NOT_TESTED** | `{"stock_thickness_mm": null, "stock_type": null, "tile_height_mm": null, "tile_width_mm": null}` |
| `tag_artwork_scale_pass` | **NOT_TESTED** | `{"detection_edge_mm": null, "orientation_marked": null, "print_scale_percent": null, "tag_id": null, "tile_size_mm": null}` |
| `tag_frame_first_article_pass` | **NOT_TESTED** | `{"flatness_mm": null, "id_legibility_result": null, "job_id": null, "tag_fit_result": null, "washer_zone_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: ID1-ID5 tiles, matte tape, ten screws/washers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off unless a job override says otherwise. Bed adhesion: Clean textured PEI; use a 5 mm brim only after observed corner lift.
- Dimensional controls: Use calibrated elephant-foot and XY-hole compensation from the diagnostic coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Confirm every physical ID matches its debossed frame and board map. Check all faces flat, matte, unobstructed, and oriented +Y before mounting.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `tag_frame_batch_postprint_pass`, `tag_frame_installation_pass`.

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
