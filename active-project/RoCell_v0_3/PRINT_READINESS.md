# Print readiness - QIDI Plus4

**Design revision: RC03-INT-R1**

**5 ready / 15 waiting / 4 not selected / 24 total jobs**

This report is generated from config/measurement_record.json. READY means every release prerequisite is PASS with complete evidence; post-print, kitting, and assembly progression is tracked separately.

| Job | Status | Stage | Material/profile | Layer | Plate | Purpose |
|---|---|---|---|---:|---|---|
| 00A | **READY** | diagnostic | QIDI ABS Rapido / abs_rapido_tray_structural_0p4 | 0.20 mm | 00A_ABS_keyboard_station_fit_tests.3mf | ABS keyboard datum, board/seam locator, clearance, and washer qualification using the exact station profile |
| 00B | **READY** | diagnostic | QIDI ABS Rapido / abs_rapido_cradle_0p4 | 0.20 mm | 00B_ABS_phone_station_fit_tests.3mf | ABS phone width, station locator, profile-specific M3 insert, and washer qualification; retained nut and cable-saddle objects document superseded screening geometry |
| 00C | **READY** | diagnostic | QIDI ABS Rapido / abs_rapido_precision_0p4 | 0.16 mm | 00C_ABS_tool_profile_fit_tests.3mf | ABS RoArm grip, stepped spring seat, profile-specific M3 insert, and M3 head tests using the exact tool profile |
| 00D | **WAITING** | diagnostic | PETG / petg_adapter_0p4 | 0.12 mm | 00D_PETG_adapter_profile_fit_tests.3mf | Phone-stylus-route sliding-fit qualification using the exact adapter profile |
|  | Missing |  |  |  |  | petg_adapter_profile_calibrated |
| 00E | **READY** | diagnostic | QIDI ABS Rapido / abs_rapido_general_0p4 | 0.20 mm | 00E_ABS_general_setup_tests.3mf | ABS general clearance, screw-head, washer, camera-hex, and TPU-retention setup tests |
| 00F | **READY** | diagnostic | QIDI ABS Rapido / abs_rapido_calibration_0p4 | 0.16 mm | 00F_ABS_calibration_profile_clearance_test.3mf | ABS M3 clearance and M3 button-head recess verification using the exact fine-layer calibration-puck profile |
| 01 | **WAITING** | first_article | QIDI ABS Rapido / abs_rapido_tray_structural_0p4 | 0.20 mm | 01_ABS_keyboard_station_left.3mf | ABS left master keyboard station with integrated datums, locator sockets, clamp track, and seam posts |
|  | Missing |  |  |  |  | keyboard_dimensions_measured, qidi_studio_roundtrip_confirmed |
| 02 | **WAITING** | production | QIDI ABS Rapido / abs_rapido_tray_structural_0p4 | 0.20 mm | 02_ABS_keyboard_station_right.3mf | ABS right slave keyboard station located from the accepted left-station seam |
|  | Missing |  |  |  |  | keyboard_dimensions_measured, keyboard_seam_coupon_pass, keyboard_left_first_article_pass, qidi_studio_roundtrip_confirmed |
| 03A | **WAITING** | first_article | QIDI ABS Rapido / abs_rapido_cradle_0p4 | 0.20 mm | 03A_ABS_phone_TCP_station.3mf | Integrated ABS phone and TCP service station with fixed datums, keyed receiver, and replaceable-rail interface |
|  | Missing |  |  |  |  | phone_dimensions_measured, phone_side_features_measured, phone_cable_measured, phone_m4_captive_nut_coupon_pass, phone_station_m3_insert_coupon_pass, cable_tie_saddle_coupon_pass, qidi_studio_roundtrip_confirmed |
| 03B | **WAITING** | production | QIDI ABS Rapido / abs_rapido_general_0p4 | 0.20 mm | 03B_ABS_keyboard_clamps.3mf | Two replaceable ABS guided keyboard rear clamp sliders |
|  | Missing |  |  |  |  | keyboard_dimensions_measured, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, qidi_studio_roundtrip_confirmed |
| 03C1 | **WAITING** | first_article | QIDI ABS Rapido / abs_rapido_cradle_0p4 | 0.20 mm | 03C1_ABS_phone_clamp_rail.3mf | Production-equivalent ABS phone keeper and clamp-tower rail that qualifies the revised captive-nut seats and adopted wide-tie saddle before Job 03A |
|  | Missing |  |  |  |  | qidi_studio_roundtrip_confirmed |
| 03C2 | **WAITING** | production | QIDI ABS Rapido / abs_rapido_general_0p4 | 0.20 mm | 03C2_ABS_board_setup_tools.3mf | Reusable ABS 55 mm direct-tag application frame and board setup tooling |
|  | Missing |  |  |  |  | tag_stock_measured, tag_artwork_scale_pass, board_setup_template_scale_pass, qidi_studio_roundtrip_confirmed |
| 03C3 | **NOT_SELECTED** | production | PETG / petg_general_0p4 | 0.20 mm | 03C3_PETG_camera_plate.3mf | Fixed-mast fallback camera plate; not an arm-camera adapter and not released while the camera architecture hold is open |
|  | Missing |  |  |  |  | fixed_camera_fallback_architecture_released, petg_general_profile_calibrated, camera_mount_interface_measured, general_clearance_holes_coupon_pass, setup_hardware_coupon_pass, qidi_studio_roundtrip_confirmed |
| 03D | **WAITING** | first_article | QIDI ABS Rapido / abs_rapido_calibration_0p4 | 0.16 mm | 03D_ABS_TCP_datum_cartridges.3mf | Two keyed ABS TCP datum cartridges: one selected INSTALL datum and one qualified recalibration-required SPARE |
|  | Missing |  |  |  |  | calibration_clearance_holes_coupon_pass, qidi_studio_roundtrip_confirmed |
| 04A | **WAITING** | route | QIDI ABS Rapido / abs_rapido_precision_0p4 | 0.16 mm | 04A_ABS_shared_compliant_tool.3mf | Shared ABS compliant tool body with keyed cap and one spare cap |
|  | Missing |  |  |  |  | compliant_tool_m3_insert_coupon_pass, gripper_interface_measured, gripper_coupon_pass, spring_dimensions_measured, spring_fit_coupon_pass, precision_m3_head_coupon_pass, qidi_studio_roundtrip_confirmed |
| 04B | **WAITING** | route | PETG / petg_adapter_0p4 | 0.12 mm | 04B_PETG_phone_stylus_adapters.3mf | Two phone-route stylus collars for thin-wall retention qualification and one spare |
|  | Missing |  |  |  |  | petg_adapter_profile_calibrated, stylus_diameter_measured, stylus_gauge_coupon_pass, adapter_retention_method_selected, qidi_studio_roundtrip_confirmed |
| 04C | **WAITING** | route | PETG / petg_adapter_0p4 | 0.12 mm | 04C_PETG_keyboard_rod_adapters.3mf | Two keyboard-route rod bushings for retention qualification and one spare |
|  | Missing |  |  |  |  | petg_adapter_profile_calibrated, keyboard_rod_measured, adapter_retention_method_selected, qidi_studio_roundtrip_confirmed |
| 05A | **WAITING** | first_article | TPU 95A / tpu95a_0p4 | 0.16 mm | 05A_TPU_phone_tip_first_article.3mf | One phone TPU tip for dimensional and pull-off acceptance |
|  | Missing |  |  |  |  | tpu_profile_calibrated, qidi_studio_roundtrip_confirmed |
| 05B | **WAITING** | production | TPU 95A / tpu95a_0p4 | 0.16 mm | 05B_TPU_phone_tips_and_spares.3mf | Three additional phone TPU tips, yielding two installed and two total spares |
|  | Missing |  |  |  |  | tpu_profile_calibrated, phone_tpu_retention_coupon_pass, qidi_studio_roundtrip_confirmed |
| 05C | **WAITING** | first_article | TPU 95A / tpu95a_0p4 | 0.16 mm | 05C_TPU_keyboard_tip_first_article.3mf | One keyboard TPU tip for dimensional and pull-off acceptance |
|  | Missing |  |  |  |  | tpu_profile_calibrated, keyboard_rod_measured, qidi_studio_roundtrip_confirmed |
| 05D | **WAITING** | production | TPU 95A / tpu95a_0p4 | 0.16 mm | 05D_TPU_keyboard_tips_and_spares.3mf | Three additional keyboard TPU tips, yielding two installed and two total spares |
|  | Missing |  |  |  |  | tpu_profile_calibrated, keyboard_rod_measured, keyboard_tpu_retention_coupon_pass, qidi_studio_roundtrip_confirmed |
| 06 | **NOT_SELECTED** | diagnostic | ASA / asa_structural_0p4 | 0.24 mm | 06_ASA_mast_fit_tests.3mf | Fixed-mast fallback 2020 socket and production-axis M5 nut/clearance/washer tests; blocked until the fallback architecture is explicitly released |
|  | Missing |  |  |  |  | fixed_camera_fallback_architecture_released, asa_profile_calibrated |
| 07A | **NOT_SELECTED** | first_article | ASA / asa_structural_0p4 | 0.24 mm | 07A_ASA_mast_foot_first_article.3mf | First fixed-mast fallback foot with rear-lug clamp bolts; not part of the intended arm-mounted camera architecture |
|  | Missing |  |  |  |  | fixed_camera_fallback_architecture_released, asa_profile_calibrated, asa_mast_socket_coupon_pass, asa_m5_nut_coupon_pass, asa_m5_clearance_coupon_pass, qidi_studio_roundtrip_confirmed |
| 07B | **NOT_SELECTED** | optional | ASA / asa_structural_0p4 | 0.24 mm | 07B_ASA_mast_foot_second.3mf | Second fixed-mast fallback foot after first-article acceptance; not part of the intended arm-mounted camera architecture |
|  | Missing |  |  |  |  | fixed_camera_fallback_architecture_released, asa_profile_calibrated, asa_mast_socket_coupon_pass, asa_m5_nut_coupon_pass, asa_m5_clearance_coupon_pass, mast_foot_first_article_pass, qidi_studio_roundtrip_confirmed |

## Required next evidence

- petg_adapter_profile_calibrated (NOT_TESTED; petg_adapter_0p4; rev RC03-INT-R1): Identify and calibrate the exact dry PETG spool with petg_adapter_0p4 before printing the retained thin-wall adapter jobs.
- keyboard_dimensions_measured (NOT_TESTED; geometry_input; rev RC03-INT-R1): Measure the keyboard at its widest and tallest points, including its cable keepout.
- qidi_studio_roundtrip_confirmed (NOT_TESTED; all_active_profiles; rev RC03-INT-R1): For each production job: import, slice, save, reopen, and inspect without auto-scaling or losing objects/settings; record the job-specific native-project hash and preview evidence.
- keyboard_seam_coupon_pass (NOT_TESTED; abs_rapido_tray_structural_0p4; rev RC03-INT-R1): After accepting job 01, use its measured 8 mm master posts with job 00A's seam round/radial ladder. Independently select the smallest 8.2/8.3/8.4 mm round-socket diameter and radial-slot width that seat by hand without perceptible rocking/yaw and release without tools. Record both values separately. Station-pair gap and flush are measured after job 02, not on this coupon.
- keyboard_left_first_article_pass (NOT_TESTED; abs_rapido_tray_structural_0p4; rev RC03-INT-R1): Inspect cooled job 01 as the pinned master station before releasing the matching slave station.
- phone_dimensions_measured (NOT_TESTED; geometry_input; rev RC03-INT-R1): Measure the phone in the exact case state, including the camera-bump envelope.
- phone_side_features_measured (NOT_TESTED; geometry_input; rev RC03-INT-R1): Use the PASS engineering release in phone_no_go_clearance_limit_approved. Record every right-side keepout as a named start/end interval, both clamp centers, the minimum measured margin, and measurement uncertainty. The conservative margin after uncertainty must meet the approved minimum.
- phone_cable_measured (NOT_TESTED; geometry_input; rev RC03-INT-R1): Measure the installed USB-C connector, bend envelope, and selected strain-relief tie.
- phone_m4_captive_nut_coupon_pass (FAIL; abs_rapido_cradle_0p4; rev RC03-INT-R1): The as-built Job 00B N7.4 screening channel failed because the nut dropped in loosely and the M4 screw would not engage reliably. Qualify the redesigned 7.2 mm lower-half hex seat only on the production-equivalent Job 03C1 rail: each actual nut must top-load by hand, each screw must engage at least three full turns, and neither nut may spin during 20 advance/back-out cycles.
- phone_station_m3_insert_coupon_pass (NOT_TESTED; abs_rapido_cradle_0p4; rev RC03-INT-R1): Use the PHONE-labeled gauge whose 6.2 mm-deep pockets reproduce the station receiver's 0.3 mm floor. Install the production M3 insert vertically in the same service-station profile and record squareness, depth, floor condition, and resistance to rotation; repeat the insert check on the first station article before release.
- cable_tie_saddle_coupon_pass (FAIL; abs_rapido_cradle_0p4; rev RC03-INT-R1): No separate replacement coupon is required. On the production-equivalent Job 03C1 rail, feed the selected nominal 4.8 mm wide by no more than 1.5 mm thick tie through the controlled 5.6 x 2.2 mm saddle around the actual USB cable; confirm free feeding, useful cinching range, cable clearance, and no saddle cracking.
- general_clearance_holes_coupon_pass (NOT_TESTED; abs_rapido_general_0p4; rev RC03-INT-R1): Record the smallest freely passing general-profile QIDI ABS Rapido hole for each fastener family.
- setup_hardware_coupon_pass (NOT_TESTED; abs_rapido_general_0p4; rev RC03-INT-R1): Verify the production recess, washer, and camera-hex selections against the setup gauge.
- tag_stock_measured (NOT_TESTED; geometry_input; rev RC03-INT-R1): Measure the direct-adhesive tag stock and compressed adhesive, confirm a 55.0 mm tile with 40.0 mm detection edge, matte finish, full-area adhesion, and no curl; optical Z is adhesive plus stock above the finished sealed board.
- tag_artwork_scale_pass (NOT_TESTED; artwork_100_percent; rev RC03-INT-R1): Verify the tag detection edge, tile size, 100% scale, and +Y orientation mark.
- board_setup_template_scale_pass (NOT_TESTED; board_setup_template_actual_size; rev RC03-INT-R1): Select either the released Letter tiled guide or the released 24 x 36 full-size guide, record that PDF path and SHA-256 plus the source workcell-layout SHA-256, and print at Actual Size. Require both independent 100 mm scale bars to measure 100.0 +/- 0.2 mm. For the tiled guide, verify every matching registration mark and the prescribed 12 mm overlaps; for the full-size guide, verify the board-edge, orientation, and scale controls. Do not use an overview, schedule, or assembly-map page as a drilling template.
- calibration_clearance_holes_coupon_pass (NOT_TESTED; abs_rapido_calibration_0p4; rev RC03-INT-R1): Using the exact calibration-puck profile and an actual M3 x 10 mm button-head screw from the intended hardware lot, record the screw major diameter and head diameter, the smallest freely passing 3.2/3.4/3.6 mm M3 hole, and the smallest H5.8/H6.2/H6.6 recess that seats the head below the surrounding face without forcing.
- compliant_tool_m3_insert_coupon_pass (NOT_TESTED; abs_rapido_precision_0p4; rev RC03-INT-R1): Use the TOOL-labeled gauge whose pockets reproduce the compliant tool body's 5 mm edge ligaments. Record the precision-profile M3 pocket that installs square without splitting, edge breakout, or spinning; repeat the insert check on the first article before releasing the tool body.
- gripper_interface_measured (NOT_TESTED; abs_rapido_precision_0p4; rev RC03-INT-R1): Measure the RoArm gripper and record the intended low-force gripping setting.
- gripper_coupon_pass (NOT_TESTED; abs_rapido_precision_0p4; rev RC03-INT-R1): Grip the production-face coupon without bottoming, rocking, slipping, or crushing.
- spring_dimensions_measured (NOT_TESTED; abs_rapido_precision_0p4; rev RC03-INT-R1): Measure spring OD, ID, free length, approximate rate, and coil-bind length.
- spring_fit_coupon_pass (NOT_TESTED; abs_rapido_precision_0p4; rev RC03-INT-R1): Record the stepped spring seat and verify the spring fits without binding.
- precision_m3_head_coupon_pass (NOT_TESTED; abs_rapido_precision_0p4; rev RC03-INT-R1): Using the exact precision-tool profile, record the actual M3 screw-head diameter and the smallest recess that seats it below the surrounding face.
- stylus_diameter_measured (NOT_TESTED; petg_adapter_0p4; rev RC03-INT-R1): Measure the capacitive stylus barrel at several locations.
- stylus_gauge_coupon_pass (NOT_TESTED; petg_adapter_0p4; rev RC03-INT-R1): Record the smallest adapter-profile stylus hole that slides freely without excessive play.
- adapter_retention_method_selected (NOT_TESTED; petg_adapter_0p4; rev RC03-INT-R1): Select and document measured dry-fit retention or the minimal plastics-compatible removable compound. A thin-wall radial screw is not part of RC03.
- keyboard_rod_measured (NOT_TESTED; petg_adapter_0p4; rev RC03-INT-R1): Measure the rod diameter at several points and record its finished length.
- tpu_profile_calibrated (NOT_TESTED; tpu95a_0p4; rev RC03-INT-R1): Calibrate the exact dry TPU spool with tpu95a_0p4.
- phone_tpu_retention_coupon_pass (NOT_TESTED; tpu95a_0p4; rev RC03-INT-R1): Use the PASS engineering release in phone_tpu_retention_limits_approved. Test the Job 05A first article on the M4 peg with a calibrated force gauge and record the approval ID, approved minimum force, achieved duration, method, measured force, and pull-off result.
- keyboard_tpu_retention_coupon_pass (NOT_TESTED; tpu95a_0p4; rev RC03-INT-R1): Use the keyboard-rod route values in the PASS tool_force_tcp_limits_approved record. Test the Job 05C first article on the 6 mm peg with a calibrated force gauge and record the approval ID, force, duration, method, and pull-off result.

## Safe workflow

1. Complete operator, date, printer, measurement-tool, evidence-directory, and QIDI Studio test context.
2. Confirm the 0.4 mm nozzle and calibrate every exact filament/profile combination.
3. Print required diagnostic jobs 00A, 00B, 00C, 00E, and 00F with their matching profiles; print 00D only when `phone_stylus_route` is selected.
4. Measure devices and hardware; record each coupon selection and its process/profile/revision scope.
5. Apply accepted selections to config/parameters.json, regenerate affected geometry, and pass the objective geometry check.
6. Re-run python scripts/validate_print_readiness.py and print only jobs marked READY.
7. Use python scripts/generate_build_tracker.py for slice review, print inspection, kitting, assembly, and service release.
