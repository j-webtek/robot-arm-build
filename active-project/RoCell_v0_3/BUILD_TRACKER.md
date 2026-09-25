# RoCell build tracker

**Design revision: RC03-INT-R1**

**20 selected / 24 total jobs**

Lifecycle: UNRELEASED -> READY_TO_SLICE -> SLICE_REVIEWED -> PRINTED -> POSTPRINT_PASS -> KITTED -> ASSEMBLY_PASS -> IN_SERVICE

READY_TO_SLICE is derived from route selection and prerequisite gates. Machine jobs require native QIDI Studio evidence for that exact job. Every later state requires sequential signed evidence in config/job_build_record.json.

| Job | Effective state | Recorded state | Native QIDI | Stage | Kit | Plate | Blocking prerequisites |
|---|---|---|---|---|---|---|---|
| 00A | **POSTPRINT_PASS** | POSTPRINT_PASS | NOT_REQUIRED | diagnostic | KIT-CAL | 00A_ABS_keyboard_station_fit_tests.3mf | - |
| 00B | **PRINTED** | PRINTED | NOT_REQUIRED | diagnostic | KIT-CAL | 00B_ABS_phone_station_fit_tests.3mf | - |
| 00C | **READY_TO_SLICE** | UNRELEASED | NOT_REQUIRED | diagnostic | KIT-CAL | 00C_ABS_tool_profile_fit_tests.3mf | - |
| 00D | **UNRELEASED** | UNRELEASED | NOT_REQUIRED | diagnostic | KIT-CAL | 00D_PETG_adapter_profile_fit_tests.3mf | petg_adapter_profile_calibrated |
| 00E | **READY_TO_SLICE** | UNRELEASED | NOT_REQUIRED | diagnostic | KIT-CAL | 00E_ABS_general_setup_tests.3mf | - |
| 00F | **READY_TO_SLICE** | UNRELEASED | NOT_REQUIRED | diagnostic | KIT-CAL | 00F_ABS_calibration_profile_clearance_test.3mf | - |
| 01 | **UNRELEASED** | UNRELEASED | MISSING | first_article | KIT-KB | 01_ABS_keyboard_station_left.3mf | keyboard_dimensions_measured, qidi_studio_roundtrip_confirmed |
| 02 | **UNRELEASED** | UNRELEASED | MISSING | production | KIT-KB | 02_ABS_keyboard_station_right.3mf | keyboard_dimensions_measured, keyboard_seam_coupon_pass, keyboard_left_first_article_pass, qidi_studio_roundtrip_confirmed |
| 03A | **UNRELEASED** | UNRELEASED | MISSING | first_article | KIT-PHONE | 03A_ABS_phone_TCP_station.3mf | phone_dimensions_measured, phone_side_features_measured, phone_cable_measured, phone_m4_captive_nut_coupon_pass, phone_station_m3_insert_coupon_pass, cable_tie_saddle_coupon_pass, qidi_studio_roundtrip_confirmed |
| 03B | **UNRELEASED** | UNRELEASED | MISSING | production | KIT-KB | 03B_ABS_keyboard_clamps.3mf | keyboard_dimensions_measured, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, qidi_studio_roundtrip_confirmed |
| 03C1 | **UNRELEASED** | UNRELEASED | MISSING | first_article | KIT-PHONE | 03C1_ABS_phone_clamp_rail.3mf | qidi_studio_roundtrip_confirmed |
| 03C2 | **UNRELEASED** | UNRELEASED | MISSING | production | KIT-BOARD-SETUP | 03C2_ABS_board_setup_tools.3mf | tag_stock_measured, tag_artwork_scale_pass, board_setup_template_scale_pass, qidi_studio_roundtrip_confirmed |
| 03C3 | **NOT_SELECTED** | UNRELEASED | MISSING | production | KIT-VISION-CAM | 03C3_PETG_camera_plate.3mf | fixed_camera_fallback_architecture_released, petg_general_profile_calibrated, camera_mount_interface_measured, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, qidi_studio_roundtrip_confirmed |
| 03D | **UNRELEASED** | UNRELEASED | MISSING | first_article | KIT-PUCK | 03D_ABS_TCP_datum_cartridges.3mf | calibration_clearance_holes_coupon_pass, qidi_studio_roundtrip_confirmed |
| 04A | **UNRELEASED** | UNRELEASED | MISSING | route | KIT-TOOL-COMMON | 04A_ABS_shared_compliant_tool.3mf | compliant_tool_m3_insert_coupon_pass, gripper_interface_measured, gripper_coupon_pass, spring_dimensions_measured, spring_fit_coupon_pass, precision_m3_head_coupon_pass, qidi_studio_roundtrip_confirmed |
| 04B | **UNRELEASED** | UNRELEASED | MISSING | route | KIT-TOOL-PHONE | 04B_PETG_phone_stylus_adapters.3mf | petg_adapter_profile_calibrated, stylus_diameter_measured, stylus_gauge_coupon_pass, adapter_retention_method_selected, qidi_studio_roundtrip_confirmed |
| 04C | **UNRELEASED** | UNRELEASED | MISSING | route | KIT-TOOL-KB | 04C_PETG_keyboard_rod_adapters.3mf | petg_adapter_profile_calibrated, keyboard_rod_measured, adapter_retention_method_selected, qidi_studio_roundtrip_confirmed |
| 05A | **UNRELEASED** | UNRELEASED | MISSING | first_article | KIT-PHONE | 05A_TPU_phone_tip_first_article.3mf | tpu_profile_calibrated, qidi_studio_roundtrip_confirmed |
| 05B | **UNRELEASED** | UNRELEASED | MISSING | production | KIT-PHONE | 05B_TPU_phone_tips_and_spares.3mf | tpu_profile_calibrated, phone_tpu_retention_coupon_pass, qidi_studio_roundtrip_confirmed |
| 05C | **UNRELEASED** | UNRELEASED | MISSING | first_article | KIT-TOOL-KB | 05C_TPU_keyboard_tip_first_article.3mf | tpu_profile_calibrated, keyboard_rod_measured, qidi_studio_roundtrip_confirmed |
| 05D | **UNRELEASED** | UNRELEASED | MISSING | production | KIT-TOOL-KB | 05D_TPU_keyboard_tips_and_spares.3mf | tpu_profile_calibrated, keyboard_rod_measured, keyboard_tpu_retention_coupon_pass, qidi_studio_roundtrip_confirmed |
| 06 | **NOT_SELECTED** | UNRELEASED | NOT_REQUIRED | diagnostic | KIT-MAST | 06_ASA_mast_fit_tests.3mf | fixed_camera_fallback_architecture_released, asa_profile_calibrated |
| 07A | **NOT_SELECTED** | UNRELEASED | MISSING | first_article | KIT-MAST | 07A_ASA_mast_foot_first_article.3mf | fixed_camera_fallback_architecture_released, asa_profile_calibrated, asa_mast_socket_coupon_pass, asa_m5_nut_coupon_pass, asa_m5_clearance_coupon_pass, qidi_studio_roundtrip_confirmed |
| 07B | **NOT_SELECTED** | UNRELEASED | MISSING | optional | KIT-MAST | 07B_ASA_mast_foot_second.3mf | fixed_camera_fallback_architecture_released, asa_profile_calibrated, asa_mast_socket_coupon_pass, asa_m5_nut_coupon_pass, asa_m5_clearance_coupon_pass, mast_foot_first_article_pass, qidi_studio_roundtrip_confirmed |

## State definitions

- UNRELEASED: one or more selected-job prerequisites are unresolved.
- READY_TO_SLICE: selected and every print prerequisite is PASS.
- SLICE_REVIEWED: object count, orientation, supports, seams, brim, and critical layers were reviewed.
- PRINTED: the complete cooled job was recovered and identified.
- POSTPRINT_PASS: every mapped inspection/first-article gate is PASS.
- KITTED: accepted parts, spares, hardware, and labels are together under the listed kit ID.
- ASSEMBLY_PASS: every mapped module assembly gate is PASS.
- IN_SERVICE: the accepted assembly was released for controlled operation.
