# Job 03C2 - Reusable ABS 55 mm direct-tag application frame and board setup tooling

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-BOARD-SETUP` |
| Plate | `03C2_ABS_board_setup_tools.3mf` |
| Plate SHA-256 | `6f84a4addac525d32ebe0685c5f11764a15270caf11d29bd6bda20338e1e3b6b` |
| Profile | `abs_rapido_general_0p4` / `4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede` |
| Exact settings sheet | `print_plates_3mf/03C2_ABS_board_setup_tools.PRINT_SETTINGS.md` / `fad0b88672c052346ceff5fd3fcc86caac6565b081497eeb372ffd4bf6b64416` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json` / `756895e547ed186ab4b0d532d6d66fc3e2ad31376bc342a0150cbd4667a5d239` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 75.0 x 75.0 x 2.4 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `tag_application_frame_55mm.stl` | 1 | Flat as exported; 55 mm DIRECT and +Y/REAR marks plus center notches upward | `492f7e3c567a7aa3a4bc255d59425f73dc0c64ab240df8af8f9adf861d53a10f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_general_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_general_0p4 SHA256 4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `tag_stock_measured` | **NOT_TESTED** | `{"adhesive_type": null, "compressed_adhesive_thickness_mm": null, "curl_result": null, "detection_edge_mm": null, "full_surface_adhesive": null, "matte_finish_result": null, "measured_optical_plane_z_mm": null, "stock_thickness_mm": null, "stock_type": null, "tile_height_mm": null, "tile_width_mm": null}` |
| `tag_artwork_scale_pass` | **NOT_TESTED** | `{"detection_edge_mm": null, "orientation_marked": null, "print_scale_percent": null, "tag_id": null, "tile_size_mm": null}` |
| `board_setup_template_scale_pass` | **NOT_TESTED** | `{"all_sheet_registration_marks_result": null, "page_scaling_setting": null, "selected_guide_path": null, "selected_guide_sha256": null, "source_layout_sha256": null, "template_revision": null, "x_scale_bar_mm": null, "y_scale_bar_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: 1:1 board setup template, six direct adhesive tags, steel rule and calipers.
- Open `print_plates_3mf/03C2_ABS_board_setup_tools.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Zero XY contour and hole compensation until the matching ABS coupon provides measured evidence; elephant-foot compensation 0.15 mm.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Verify the 55 mm application opening, center and +Y witness marks, flatness, and finger access. Prove the 100 mm template scale before installing any direct tag.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `tag_application_tool_postprint_pass`.

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
