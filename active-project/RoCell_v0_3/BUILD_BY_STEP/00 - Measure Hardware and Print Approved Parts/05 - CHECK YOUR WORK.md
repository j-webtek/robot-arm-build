# Step 00 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 00 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 00 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `00-A` | Every selected job is READY before print | Run validate_print_readiness.py and retain PRINT_READINESS.json | No selected job may be WAITING | `qidi_studio_roundtrip_confirmed` | Readiness report plus native QIDI project records | `scripts/record_step_result.py` |
| `00-B` | All required fits use the matching production profile or production-equivalent first article | Check the actual hardware in its controlled diagnostic or Job 03C1 production interface | Every required coupon gate is PASS and every selected value is regenerated into CAD | `geometry_matches_measurements` | Raw observations, photos, selected values, and first-article identity | `scripts/record_step_result.py` |
| `00-C` | Printed parts are accepted and kitted | Count, inspect, label, and reconcile against JOB_KITS.csv | No missing required part, spare, or traceability record | `keyboard_station_pair_postprint_pass` | Signed job cards and kit photos | `scripts/record_step_result.py` |
| `00-D` | One named board drill guide is printed at verified 1:1 scale and remains traceable | Print either the nine Letter drilling tiles or the single 24 x 36 inch guide at Actual Size / 100 percent; measure the independent X and Y 100 mm controls on every physical drilling sheet; verify every matching tiled registration mark or the full-size board-edge/orientation controls; record the selected path plus guide and source-layout SHA-256 values | Every X and Y control is 100.0 +/- 0.2 mm, all applicable registration/edge controls agree, and the recorded path and hashes match the exact files used; this scale check alone does not release hole positions | `board_setup_template_scale_pass` | Ruler photos for every drilling sheet, registration/edge photos, selected guide path, print settings, revision, guide SHA-256, and source-layout SHA-256 | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| `nozzle_0p4_confirmed` | **PASS** |
| `abs_rapido_general_profile_calibrated` | **PASS** |
| `abs_rapido_tray_profile_calibrated` | **PASS** |
| `abs_rapido_cradle_profile_calibrated` | **PASS** |
| `abs_rapido_precision_profile_calibrated` | **PASS** |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** |
| `abs_rapido_calibration_profile_calibrated` | **PASS** |
| `tpu_profile_calibrated` | **NOT_TESTED** |
| `keyboard_dimensions_measured` | **NOT_TESTED** |
| `phone_dimensions_measured` | **NOT_TESTED** |
| `phone_side_features_measured` | **NOT_TESTED** |
| `phone_cable_measured` | **NOT_TESTED** |
| `phone_no_go_clearance_limit_approved` | **NOT_TESTED** |
| `phone_tpu_retention_limits_approved` | **NOT_TESTED** |
| `tag_stock_measured` | **NOT_TESTED** |
| `camera_mount_interface_measured` | **NOT_TESTED** |
| `keyboard_corner_coupon_pass` | **PASS** |
| `keyboard_station_registration_coupon_pass` | **PASS** |
| `tray_clearance_holes_coupon_pass` | **PASS** |
| `phone_width_coupon_pass` | **PASS** |
| `phone_station_registration_coupon_pass` | **PASS** |
| `phone_m4_captive_nut_coupon_pass` | **FAIL** |
| `phone_station_m3_insert_coupon_pass` | **NOT_TESTED** |
| `cable_tie_saddle_coupon_pass` | **FAIL** |
| `cradle_m4_washer_coupon_pass` | **PASS** |
| `general_clearance_holes_coupon_pass` | **NOT_TESTED** |
| `setup_hardware_coupon_pass` | **NOT_TESTED** |
| `calibration_clearance_holes_coupon_pass` | **NOT_TESTED** |
| `tag_artwork_scale_pass` | **NOT_TESTED** |
| `board_setup_template_scale_pass` | **NOT_TESTED** |
| `geometry_matches_measurements` | **PASS** |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** |
| `keyboard_station_pair_postprint_pass` | **NOT_TESTED** |
| `keyboard_clamps_postprint_pass` | **NOT_TESTED** |
| `phone_tcp_station_postprint_pass` | **NOT_TESTED** |
| `phone_clamp_rail_first_article_pass` | **NOT_TESTED** |
| `phone_tpu_batch_postprint_pass` | **NOT_TESTED** |
| `tag_application_tool_postprint_pass` | **NOT_TESTED** |
| `calibration_puck_datum_pass` | **NOT_TESTED** |
| `tool_force_tcp_limits_approved` | **NOT_TESTED** |
| `gripper_interface_measured` | **NOT_TESTED** |
| `spring_dimensions_measured` | **NOT_TESTED** |
| `gripper_coupon_pass` | **NOT_TESTED** |
| `spring_fit_coupon_pass` | **NOT_TESTED** |
| `compliant_tool_m3_insert_coupon_pass` | **NOT_TESTED** |
| `precision_m3_head_coupon_pass` | **NOT_TESTED** |
| `tool_body_postprint_pass` | **NOT_TESTED** |
| `stylus_diameter_measured` | **NOT_TESTED** |
| `stylus_gauge_coupon_pass` | **NOT_TESTED** |
| `adapter_retention_method_selected` | **NOT_TESTED** |
| `stylus_collar_retention_pass` | **NOT_TESTED** |
| `keyboard_rod_measured` | **NOT_TESTED** |
| `rod_bushing_retention_pass` | **NOT_TESTED** |
| `keyboard_tpu_retention_coupon_pass` | **NOT_TESTED** |
| `keyboard_tpu_batch_postprint_pass` | **NOT_TESTED** |
| active-build step signoff | **INVALID — HOLD** |
| select at least one of `phone_stylus_route, keyboard_rod_route` | **PASS: phone_stylus_route, keyboard_rod_route** |

## If a check fails

Set Step 00 to `HOLD`; correct the measurement, profile, CAD parameter, slice, or print, then repeat every affected diagnostic and downstream release check.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.
