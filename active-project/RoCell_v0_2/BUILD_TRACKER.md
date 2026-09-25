# RoCell build tracker

**Design revision: RC02-PRO-R1**

**16 selected / 24 total jobs**

Lifecycle: UNRELEASED -> READY_TO_SLICE -> SLICE_REVIEWED -> PRINTED -> POSTPRINT_PASS -> KITTED -> ASSEMBLY_PASS -> IN_SERVICE

READY_TO_SLICE is derived from route selection and prerequisite gates. Every later state requires sequential signed evidence in config/job_build_record.json.

| Job | Effective state | Recorded state | Stage | Kit | Plate | Blocking prerequisites |
|---|---|---|---|---|---|---|
| 00A | **UNRELEASED** | UNRELEASED | diagnostic | KIT-CAL | 00A_PETG_keyboard_profile_fit_tests.3mf | nozzle_0p4_confirmed, petg_tray_profile_calibrated |
| 00B | **UNRELEASED** | UNRELEASED | diagnostic | KIT-CAL | 00B_PETG_phone_profile_fit_tests.3mf | nozzle_0p4_confirmed, petg_cradle_profile_calibrated |
| 00C | **UNRELEASED** | UNRELEASED | diagnostic | KIT-CAL | 00C_PETG_tool_profile_fit_tests.3mf | nozzle_0p4_confirmed, petg_precision_profile_calibrated |
| 00D | **UNRELEASED** | UNRELEASED | diagnostic | KIT-CAL | 00D_PETG_adapter_profile_fit_tests.3mf | nozzle_0p4_confirmed, petg_adapter_profile_calibrated |
| 00E | **UNRELEASED** | UNRELEASED | diagnostic | KIT-CAL | 00E_PETG_general_setup_tests.3mf | nozzle_0p4_confirmed, petg_general_profile_calibrated |
| 00F | **UNRELEASED** | UNRELEASED | diagnostic | KIT-CAL | 00F_PETG_calibration_profile_clearance_test.3mf | nozzle_0p4_confirmed, petg_calibration_profile_calibrated |
| 01 | **UNRELEASED** | UNRELEASED | first_article | KIT-KB | 01_PETG_keyboard_left.3mf | nozzle_0p4_confirmed, petg_tray_profile_calibrated, keyboard_dimensions_measured, keyboard_corner_coupon_pass, keyboard_seam_coupon_pass, tray_clearance_holes_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 02 | **UNRELEASED** | UNRELEASED | production | KIT-KB | 02_PETG_keyboard_right.3mf | nozzle_0p4_confirmed, petg_tray_profile_calibrated, keyboard_dimensions_measured, keyboard_corner_coupon_pass, keyboard_seam_coupon_pass, tray_clearance_holes_coupon_pass, geometry_matches_measurements, keyboard_left_first_article_pass, qidi_studio_roundtrip_confirmed |
| 03A | **UNRELEASED** | UNRELEASED | production | KIT-PHONE | 03A_PETG_phone_cradle.3mf | nozzle_0p4_confirmed, petg_cradle_profile_calibrated, phone_dimensions_measured, phone_side_features_measured, phone_cable_measured, phone_width_coupon_pass, m4_horizontal_insert_coupon_pass, cable_tie_saddle_coupon_pass, cradle_m4_washer_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 03B | **UNRELEASED** | UNRELEASED | production | KIT-KB | 03B_PETG_keyboard_clamps.3mf | nozzle_0p4_confirmed, petg_general_profile_calibrated, keyboard_dimensions_measured, keyboard_corner_coupon_pass, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 03C1 | **UNRELEASED** | UNRELEASED | first_article | KIT-VISION-TAG | 03C1_PETG_tag_frame_first_article.3mf | nozzle_0p4_confirmed, petg_general_profile_calibrated, tag_stock_measured, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 03C2 | **UNRELEASED** | UNRELEASED | production | KIT-VISION-TAG | 03C2_PETG_tag_frames_remaining.3mf | nozzle_0p4_confirmed, petg_general_profile_calibrated, tag_stock_measured, tag_artwork_scale_pass, tag_frame_first_article_pass, qidi_studio_roundtrip_confirmed |
| 03C3 | **UNRELEASED** | UNRELEASED | production | KIT-VISION-CAM | 03C3_PETG_camera_plate.3mf | nozzle_0p4_confirmed, petg_general_profile_calibrated, camera_mount_interface_measured, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 03D | **UNRELEASED** | UNRELEASED | production | KIT-PUCK | 03D_PETG_calibration_puck.3mf | nozzle_0p4_confirmed, petg_calibration_profile_calibrated, calibration_clearance_holes_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 04A | **NOT_SELECTED** | UNRELEASED | route | KIT-TOOL-COMMON | 04A_PETG_shared_compliant_tool.3mf | nozzle_0p4_confirmed, petg_precision_profile_calibrated, m3_insert_coupon_pass, gripper_interface_measured, gripper_coupon_pass, spring_dimensions_measured, spring_fit_coupon_pass, precision_m3_head_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 04B | **NOT_SELECTED** | UNRELEASED | route | KIT-TOOL-PHONE | 04B_PETG_phone_stylus_adapters.3mf | nozzle_0p4_confirmed, petg_adapter_profile_calibrated, stylus_diameter_measured, stylus_gauge_coupon_pass, adapter_retention_method_selected, qidi_studio_roundtrip_confirmed |
| 04C | **NOT_SELECTED** | UNRELEASED | route | KIT-TOOL-KB | 04C_PETG_keyboard_rod_adapters.3mf | nozzle_0p4_confirmed, petg_adapter_profile_calibrated, keyboard_rod_measured, adapter_retention_method_selected, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 05A | **UNRELEASED** | UNRELEASED | first_article | KIT-PHONE | 05A_TPU_phone_tip_first_article.3mf | nozzle_0p4_confirmed, tpu_profile_calibrated, qidi_studio_roundtrip_confirmed |
| 05B | **UNRELEASED** | UNRELEASED | production | KIT-PHONE | 05B_TPU_phone_tips_and_spares.3mf | nozzle_0p4_confirmed, tpu_profile_calibrated, phone_tpu_retention_coupon_pass, qidi_studio_roundtrip_confirmed |
| 05C | **NOT_SELECTED** | UNRELEASED | first_article | KIT-TOOL-KB | 05C_TPU_keyboard_tip_first_article.3mf | nozzle_0p4_confirmed, tpu_profile_calibrated, keyboard_rod_measured, qidi_studio_roundtrip_confirmed |
| 05D | **NOT_SELECTED** | UNRELEASED | production | KIT-TOOL-KB | 05D_TPU_keyboard_tips_and_spares.3mf | nozzle_0p4_confirmed, tpu_profile_calibrated, keyboard_rod_measured, keyboard_tpu_retention_coupon_pass, qidi_studio_roundtrip_confirmed |
| 06 | **NOT_SELECTED** | UNRELEASED | diagnostic | KIT-MAST | 06_ASA_mast_fit_tests.3mf | nozzle_0p4_confirmed, asa_profile_calibrated |
| 07A | **NOT_SELECTED** | UNRELEASED | first_article | KIT-MAST | 07A_ASA_mast_foot_first_article.3mf | nozzle_0p4_confirmed, asa_profile_calibrated, asa_mast_socket_coupon_pass, asa_m5_nut_coupon_pass, asa_m5_clearance_coupon_pass, geometry_matches_measurements, qidi_studio_roundtrip_confirmed |
| 07B | **NOT_SELECTED** | UNRELEASED | optional | KIT-MAST | 07B_ASA_mast_foot_second.3mf | nozzle_0p4_confirmed, asa_profile_calibrated, asa_mast_socket_coupon_pass, asa_m5_nut_coupon_pass, asa_m5_clearance_coupon_pass, geometry_matches_measurements, mast_foot_first_article_pass, qidi_studio_roundtrip_confirmed |

## State definitions

- UNRELEASED: one or more selected-job prerequisites are unresolved.
- READY_TO_SLICE: selected and every print prerequisite is PASS.
- SLICE_REVIEWED: object count, orientation, supports, seams, brim, and critical layers were reviewed.
- PRINTED: the complete cooled job was recovered and identified.
- POSTPRINT_PASS: every mapped inspection/first-article gate is PASS.
- KITTED: accepted parts, spares, hardware, and labels are together under the listed kit ID.
- ASSEMBLY_PASS: every mapped module assembly gate is PASS.
- IN_SERVICE: the accepted assembly was released for controlled operation.
