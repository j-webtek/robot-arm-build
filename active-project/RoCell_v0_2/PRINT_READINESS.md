# Print readiness - QIDI Plus4

**Design revision: RC02-PRO-R1**

**0 ready / 16 waiting / 8 not selected / 24 total jobs**

This report is generated from config/measurement_record.json. READY means every release prerequisite is PASS with complete evidence; post-print, kitting, and assembly progression is tracked separately.

| Job | Status | Stage | Material/profile | Layer | Plate | Purpose |
|---|---|---|---|---:|---|---|
| 00A | **WAITING** | diagnostic | PETG / petg_tray_structural_0p4 | 0.20 mm | 00A_PETG_keyboard_profile_fit_tests.3mf | Keyboard corner, seam, clearance, and M4 washer tests using the exact tray profile |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_tray_profile_calibrated |
| 00B | **WAITING** | diagnostic | PETG / petg_cradle_0p4 | 0.20 mm | 00B_PETG_phone_profile_fit_tests.3mf | Phone width, horizontal M4 insert, cable-saddle, and washer tests using the exact cradle profile |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_cradle_profile_calibrated |
| 00C | **WAITING** | diagnostic | PETG / petg_precision_0p4 | 0.16 mm | 00C_PETG_tool_profile_fit_tests.3mf | RoArm grip, stepped spring seat, M3 insert, and M3 head tests using the exact tool profile |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_precision_profile_calibrated |
| 00D | **WAITING** | diagnostic | PETG / petg_adapter_0p4 | 0.12 mm | 00D_PETG_adapter_profile_fit_tests.3mf | Stylus sliding-fit and horizontal thread-pilot tests using the exact adapter profile |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_adapter_profile_calibrated |
| 00E | **WAITING** | diagnostic | PETG / petg_general_0p4 | 0.20 mm | 00E_PETG_general_setup_tests.3mf | General clearance, screw-head, washer, camera-hex, and TPU-retention setup tests |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_general_profile_calibrated |
| 00F | **WAITING** | diagnostic | PETG / petg_calibration_0p4 | 0.16 mm | 00F_PETG_calibration_profile_clearance_test.3mf | M4 clearance and washer verification using the exact fine-layer calibration-puck profile |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_calibration_profile_calibrated |
| 01 | **WAITING** | first_article | PETG / petg_tray_structural_0p4 | 0.20 mm | 01_PETG_keyboard_left.3mf | Left keyboard tray first article |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_tray_profile_calibrated, keyboard_dimensions_measured, keyboard_corner_coupon_pass, keyboard_seam_coupon_pass, tray_clearance_holes_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 02 | **WAITING** | production | PETG / petg_tray_structural_0p4 | 0.20 mm | 02_PETG_keyboard_right.3mf | Right keyboard tray after left first-article acceptance |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_tray_profile_calibrated, keyboard_dimensions_measured, keyboard_corner_coupon_pass, keyboard_seam_coupon_pass, tray_clearance_holes_coupon_pass, geometry_matches_measurements, keyboard_left_first_article_pass, qidi_studio_roundtrip_confirmed |
| 03A | **WAITING** | production | PETG / petg_cradle_0p4 | 0.20 mm | 03A_PETG_phone_cradle.3mf | Phone cradle with closed mounting ears and raised cable saddle |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_cradle_profile_calibrated, phone_dimensions_measured, phone_side_features_measured, phone_cable_measured, phone_width_coupon_pass, m4_horizontal_insert_coupon_pass, cable_tie_saddle_coupon_pass, cradle_m4_washer_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 03B | **WAITING** | production | PETG / petg_general_0p4 | 0.20 mm | 03B_PETG_keyboard_clamps.3mf | Two scaled, gusseted keyboard rear clamps |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_general_profile_calibrated, keyboard_dimensions_measured, keyboard_corner_coupon_pass, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 03C1 | **WAITING** | first_article | PETG / petg_general_0p4 | 0.20 mm | 03C1_PETG_tag_frame_first_article.3mf | ID0 tag frame first article with isolated artwork and washer zones |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_general_profile_calibrated, tag_stock_measured, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 03C2 | **WAITING** | production | PETG / petg_general_0p4 | 0.20 mm | 03C2_PETG_tag_frames_remaining.3mf | Remaining ID1-ID5 tag frames after first-article acceptance |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_general_profile_calibrated, tag_stock_measured, tag_artwork_scale_pass, tag_frame_first_article_pass, qidi_studio_roundtrip_confirmed |
| 03C3 | **WAITING** | production | PETG / petg_general_0p4 | 0.20 mm | 03C3_PETG_camera_plate.3mf | Universal camera plate isolated for measured camera hardware |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_general_profile_calibrated, camera_mount_interface_measured, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 03D | **WAITING** | production | PETG / petg_calibration_0p4 | 0.16 mm | 03D_PETG_calibration_puck.3mf | TCP calibration puck isolated at its fine process |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_calibration_profile_calibrated, calibration_clearance_holes_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 04A | **NOT_SELECTED** | route | PETG / petg_precision_0p4 | 0.16 mm | 04A_PETG_shared_compliant_tool.3mf | Shared compliant tool body with keyed cap and one spare cap |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_precision_profile_calibrated, m3_insert_coupon_pass, gripper_interface_measured, gripper_coupon_pass, spring_dimensions_measured, spring_fit_coupon_pass, precision_m3_head_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 04B | **NOT_SELECTED** | route | PETG / petg_adapter_0p4 | 0.12 mm | 04B_PETG_phone_stylus_adapters.3mf | Two phone-route stylus collars for thin-wall retention qualification and one spare |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_adapter_profile_calibrated, stylus_diameter_measured, stylus_gauge_coupon_pass, adapter_retention_method_selected, qidi_studio_roundtrip_confirmed |
| 04C | **NOT_SELECTED** | route | PETG / petg_adapter_0p4 | 0.12 mm | 04C_PETG_keyboard_rod_adapters.3mf | Two keyboard-route rod bushings for retention qualification and one spare |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, petg_adapter_profile_calibrated, keyboard_rod_measured, adapter_retention_method_selected, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 05A | **WAITING** | first_article | TPU 95A / tpu95a_0p4 | 0.16 mm | 05A_TPU_phone_tip_first_article.3mf | One phone TPU tip for dimensional and pull-off acceptance |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, tpu_profile_calibrated, qidi_studio_roundtrip_confirmed |
| 05B | **WAITING** | production | TPU 95A / tpu95a_0p4 | 0.16 mm | 05B_TPU_phone_tips_and_spares.3mf | Three additional phone TPU tips, yielding two installed and two total spares |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, tpu_profile_calibrated, phone_tpu_retention_coupon_pass, qidi_studio_roundtrip_confirmed |
| 05C | **NOT_SELECTED** | first_article | TPU 95A / tpu95a_0p4 | 0.16 mm | 05C_TPU_keyboard_tip_first_article.3mf | One keyboard TPU tip for dimensional and pull-off acceptance |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, tpu_profile_calibrated, keyboard_rod_measured, qidi_studio_roundtrip_confirmed |
| 05D | **NOT_SELECTED** | production | TPU 95A / tpu95a_0p4 | 0.16 mm | 05D_TPU_keyboard_tips_and_spares.3mf | Three additional keyboard TPU tips, yielding two installed and two total spares |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, tpu_profile_calibrated, keyboard_rod_measured, keyboard_tpu_retention_coupon_pass, qidi_studio_roundtrip_confirmed |
| 06 | **NOT_SELECTED** | diagnostic | ASA / asa_structural_0p4 | 0.24 mm | 06_ASA_mast_fit_tests.3mf | Same-profile 2020 socket and production-axis M5 nut/clearance/washer tests |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, asa_profile_calibrated |
| 07A | **NOT_SELECTED** | first_article | ASA / asa_structural_0p4 | 0.24 mm | 07A_ASA_mast_foot_first_article.3mf | First corrected mast foot with rear-lug clamp bolts |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, asa_profile_calibrated, asa_mast_socket_coupon_pass, asa_m5_nut_coupon_pass, asa_m5_clearance_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 07B | **NOT_SELECTED** | optional | ASA / asa_structural_0p4 | 0.24 mm | 07B_ASA_mast_foot_second.3mf | Second camera mast foot after first-article acceptance |
|  | Missing |  |  |  |  | nozzle_0p4_confirmed, asa_profile_calibrated, asa_mast_socket_coupon_pass, asa_m5_nut_coupon_pass, asa_m5_clearance_coupon_pass, geometry_matches_measurements, mast_foot_first_article_pass, qidi_studio_roundtrip_confirmed |

## Required next evidence

- nozzle_0p4_confirmed (NOT_TESTED; machine_configuration; rev RC02-PRO-R1): Confirm the installed nozzle is 0.4 mm and record how it was verified.
- petg_tray_profile_calibrated (NOT_TESTED; petg_tray_structural_0p4; rev RC02-PRO-R1): Calibrate the exact PETG spool with petg_tray_structural_0p4.
- petg_cradle_profile_calibrated (NOT_TESTED; petg_cradle_0p4; rev RC02-PRO-R1): Calibrate the exact PETG spool with petg_cradle_0p4.
- petg_precision_profile_calibrated (NOT_TESTED; petg_precision_0p4; rev RC02-PRO-R1): Calibrate the exact PETG spool with petg_precision_0p4.
- petg_adapter_profile_calibrated (NOT_TESTED; petg_adapter_0p4; rev RC02-PRO-R1): Calibrate the exact PETG spool with petg_adapter_0p4.
- petg_general_profile_calibrated (NOT_TESTED; petg_general_0p4; rev RC02-PRO-R1): Calibrate the exact PETG spool with petg_general_0p4.
- petg_calibration_profile_calibrated (NOT_TESTED; petg_calibration_0p4; rev RC02-PRO-R1): Calibrate the exact PETG spool with petg_calibration_0p4.
- keyboard_dimensions_measured (NOT_TESTED; geometry_input; rev RC02-PRO-R1): Measure the keyboard at its widest and tallest points, including its cable keepout.
- keyboard_corner_coupon_pass (NOT_TESTED; petg_tray_structural_0p4; rev RC02-PRO-R1): Confirm the keyboard corner seats on both datums without force or rocking.
- keyboard_seam_coupon_pass (NOT_TESTED; petg_tray_structural_0p4; rev RC02-PRO-R1): Mate the M/F coupons by hand and record gap and flush mismatch.
- tray_clearance_holes_coupon_pass (NOT_TESTED; petg_tray_structural_0p4; rev RC02-PRO-R1): Record the smallest freely passing tray-profile hole and the accepted M4 washer recess diameter for the selected board hardware.
- geometry_matches_measurements (NOT_TESTED; generated_geometry; rev RC02-PRO-R1): Confirm all PASS measurement/coupon selections match config/parameters.json for this design revision.
- qidi_studio_roundtrip_confirmed (NOT_TESTED; all_active_profiles; rev RC02-PRO-R1): For each production job: import, slice, save, reopen, and inspect without auto-scaling or losing objects/settings; record the job-specific native-project hash and preview evidence.
- keyboard_left_first_article_pass (NOT_TESTED; petg_tray_structural_0p4; rev RC02-PRO-R1): Inspect cooled job 01 before releasing the matching right tray.
- phone_dimensions_measured (NOT_TESTED; geometry_input; rev RC02-PRO-R1): Measure the phone in the exact case state, including the camera-bump envelope.
- phone_side_features_measured (NOT_TESTED; geometry_input; rev RC02-PRO-R1): Record every right-side feature interval and prove both clamp centers clear them.
- phone_cable_measured (NOT_TESTED; geometry_input; rev RC02-PRO-R1): Measure the installed USB-C connector, bend envelope, and selected strain-relief tie.
- phone_width_coupon_pass (NOT_TESTED; petg_cradle_0p4; rev RC02-PRO-R1): Confirm the final phone/case seats by hand with measured slight lateral clearance.
- m4_horizontal_insert_coupon_pass (NOT_TESTED; petg_cradle_0p4; rev RC02-PRO-R1): Install the production M4 insert in the same-axis coupon and record size, depth, passage, and retention.
- cable_tie_saddle_coupon_pass (NOT_TESTED; petg_cradle_0p4; rev RC02-PRO-R1): Feed the selected tie through the saddle and confirm secure clearance without cracking.
- cradle_m4_washer_coupon_pass (NOT_TESTED; petg_cradle_0p4; rev RC02-PRO-R1): Using the exact cradle profile, record the actual washer OD and the smallest recess that seats it flat without forcing.
- general_clearance_holes_coupon_pass (NOT_TESTED; petg_general_0p4; rev RC02-PRO-R1): Record the smallest freely passing general-profile PETG hole for each fastener family.
- setup_hardware_coupon_pass (NOT_TESTED; petg_general_0p4; rev RC02-PRO-R1): Verify the production recess, washer, and camera-hex selections against the setup gauge.
- tag_stock_measured (NOT_TESTED; geometry_input; rev RC02-PRO-R1): Measure the cut tag stock and confirm it is flat, matte, and compatible with the recess.
- tag_artwork_scale_pass (NOT_TESTED; artwork_100_percent; rev RC02-PRO-R1): Verify the tag detection edge, tile size, 100% scale, and +Y orientation mark.
- tag_frame_first_article_pass (NOT_TESTED; petg_general_0p4; rev RC02-PRO-R1): Inspect job 03C1 for flatness, tag fit, washer zones, and ID0 legibility.
- camera_mount_interface_measured (NOT_TESTED; petg_general_0p4; rev RC02-PRO-R1): Measure the camera thread, screw engagement, crossbar fasteners, and selected strap.
- calibration_clearance_holes_coupon_pass (NOT_TESTED; petg_calibration_0p4; rev RC02-PRO-R1): Record the calibration-profile clearance and washer fit used by the TCP puck.
- tpu_profile_calibrated (NOT_TESTED; tpu95a_0p4; rev RC02-PRO-R1): Calibrate the exact dry TPU spool with tpu95a_0p4.
- phone_tpu_retention_coupon_pass (NOT_TESTED; tpu95a_0p4; rev RC02-PRO-R1): Test the job 05A first article on the M4 peg and record the pull-off result.

## Safe workflow

1. Complete operator, date, printer, measurement-tool, evidence-directory, and QIDI Studio test context.
2. Confirm the 0.4 mm nozzle and calibrate every exact filament/profile combination.
3. Print diagnostic jobs 00A, 00B, 00C, 00D, 00E, and 00F with their matching profiles.
4. Measure devices and hardware; record each coupon selection and its process/profile/revision scope.
5. Apply accepted selections to config/parameters.json, regenerate affected geometry, and pass the objective geometry check.
6. Re-run python scripts/validate_print_readiness.py and print only jobs marked READY.
7. Use python scripts/generate_build_tracker.py for slice review, print inspection, kitting, assembly, and service release.
