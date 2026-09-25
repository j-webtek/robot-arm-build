# Job 05D - Three additional keyboard TPU tips, yielding two installed and two total spares

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `keyboard_rod_route` / `production` |
| Kit | `KIT-TOOL-KB` |
| Plate | `05D_TPU_keyboard_tips_and_spares.3mf` |
| Plate SHA-256 | `63efc560b375ce5a6abbd5092f51632a51de8771b90aca70794ec6b7e999e843` |
| Profile | `tpu95a_0p4` / `4d655c7387b95cece3d27151ae8a7283688bbf87db088790376aa3156d5afd4b` |
| Exact settings sheet | `print_plates_3mf/05D_TPU_keyboard_tips_and_spares.PRINT_SETTINGS.md` / `c2f91ab16e4faeea96945bdef95eba4cfb142430f44302565ebee51ca891ce9f` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` / `547c6502ce8d5f4b04a5d247b50fcafb884dbe587b1df9c43935dfa6d297e6ba` |
| Filament preset | `exact_tpu95a_spool_xplus4_0p4` / `945d923a44ad2a09516d5ae3dceffc8bcd567a4e4c25b408ff4879c2435bb9cf` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | TPU 95A / 0.4 mm / 0.16 mm |
| Plate envelope | 52.0 x 12.0 x 14.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_tip_TPU_6mm.stl` | 3 | Upright, flared bore entry on bed | `22ba42201e769ff4ed146b125d69d585b7188b7f274a1b3430b741ad62931d37` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `keyboard_rod_measured` | **NOT_TESTED** | `{"diameter_mm": null, "length_mm": null, "material": null, "measurement_locations": null}` |
| `keyboard_tpu_retention_coupon_pass` | **NOT_TESTED** | `{"approved_limits_id": null, "axial_pull_test_method": null, "contact_face_result": null, "first_article_job": null, "installation_result": null, "measured_pull_force_n": null, "minimum_pull_force_n": null, "proof_duration_s": null, "pull_off_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted first article and actual 6 mm rod.
- Open `print_plates_3mf/05D_TPU_keyboard_tips_and_spares.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` and select `Generic TPU 95A @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: 3 mm outer brim with 0.10 mm object gap after the exact dry TPU spool is qualified.
- Dimensional controls: Keep first-layer flow calibrated so flared bore entries remain open; do not force a failed tip onto hardware.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Compare all three with the accepted article; reject blocked bores or face defects. Label installed parts and spares.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_tpu_batch_postprint_pass`.

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
