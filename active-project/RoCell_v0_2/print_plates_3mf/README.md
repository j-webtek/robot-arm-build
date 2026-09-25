# QIDI Plus4 measured print jobs

Start with `../PRINT_READINESS.md`. Print only a selected job marked READY.

Every `.3mf` has a same-name `.print.json` sidecar. The sidecar is the authoritative source for material, nozzle, layer height, walls, top/bottom layers, infill, support guidance, contents, and prerequisite gate IDs.

The 3MF files intentionally contain geometry and placement only. Use a calibrated QIDI Studio filament preset for the exact spool; do not infer temperatures from the filename.

| Job | Stage | Selection | Plate | Material | Layer | Purpose |
|---|---|---|---|---|---:|---|
| 00A | diagnostic | required | `00A_PETG_keyboard_profile_fit_tests.3mf` | PETG | 0.20 mm | Keyboard corner, seam, clearance, and M4 washer tests using the exact tray profile |
| 00B | diagnostic | required | `00B_PETG_phone_profile_fit_tests.3mf` | PETG | 0.20 mm | Phone width, horizontal M4 insert, cable-saddle, and washer tests using the exact cradle profile |
| 00C | diagnostic | required | `00C_PETG_tool_profile_fit_tests.3mf` | PETG | 0.16 mm | RoArm grip, stepped spring seat, M3 insert, and M3 head tests using the exact tool profile |
| 00D | diagnostic | required | `00D_PETG_adapter_profile_fit_tests.3mf` | PETG | 0.12 mm | Stylus sliding-fit and horizontal thread-pilot tests using the exact adapter profile |
| 00E | diagnostic | required | `00E_PETG_general_setup_tests.3mf` | PETG | 0.20 mm | General clearance, screw-head, washer, camera-hex, and TPU-retention setup tests |
| 00F | diagnostic | required | `00F_PETG_calibration_profile_clearance_test.3mf` | PETG | 0.16 mm | M4 clearance and washer verification using the exact fine-layer calibration-puck profile |
| 01 | first_article | required | `01_PETG_keyboard_left.3mf` | PETG | 0.20 mm | Left keyboard tray first article |
| 02 | production | required | `02_PETG_keyboard_right.3mf` | PETG | 0.20 mm | Right keyboard tray after left first-article acceptance |
| 03A | production | required | `03A_PETG_phone_cradle.3mf` | PETG | 0.20 mm | Phone cradle with closed mounting ears and raised cable saddle |
| 03B | production | required | `03B_PETG_keyboard_clamps.3mf` | PETG | 0.20 mm | Two scaled, gusseted keyboard rear clamps |
| 03C1 | first_article | required | `03C1_PETG_tag_frame_first_article.3mf` | PETG | 0.20 mm | ID0 tag frame first article with isolated artwork and washer zones |
| 03C2 | production | required | `03C2_PETG_tag_frames_remaining.3mf` | PETG | 0.20 mm | Remaining ID1-ID5 tag frames after first-article acceptance |
| 03C3 | production | required | `03C3_PETG_camera_plate.3mf` | PETG | 0.20 mm | Universal camera plate isolated for measured camera hardware |
| 03D | production | required | `03D_PETG_calibration_puck.3mf` | PETG | 0.16 mm | TCP calibration puck isolated at its fine process |
| 04A | route | any_tool_route | `04A_PETG_shared_compliant_tool.3mf` | PETG | 0.16 mm | Shared compliant tool body with keyed cap and one spare cap |
| 04B | route | phone_stylus_route | `04B_PETG_phone_stylus_adapters.3mf` | PETG | 0.12 mm | Two phone-route stylus collars for thin-wall retention qualification and one spare |
| 04C | route | keyboard_rod_route | `04C_PETG_keyboard_rod_adapters.3mf` | PETG | 0.12 mm | Two keyboard-route rod bushings for retention qualification and one spare |
| 05A | first_article | required | `05A_TPU_phone_tip_first_article.3mf` | TPU 95A | 0.16 mm | One phone TPU tip for dimensional and pull-off acceptance |
| 05B | production | required | `05B_TPU_phone_tips_and_spares.3mf` | TPU 95A | 0.16 mm | Three additional phone TPU tips, yielding two installed and two total spares |
| 05C | first_article | keyboard_rod_route | `05C_TPU_keyboard_tip_first_article.3mf` | TPU 95A | 0.16 mm | One keyboard TPU tip for dimensional and pull-off acceptance |
| 05D | production | keyboard_rod_route | `05D_TPU_keyboard_tips_and_spares.3mf` | TPU 95A | 0.16 mm | Three additional keyboard TPU tips, yielding two installed and two total spares |
| 06 | diagnostic | camera_mast_optional | `06_ASA_mast_fit_tests.3mf` | ASA | 0.24 mm | Same-profile 2020 socket and production-axis M5 nut/clearance/washer tests |
| 07A | first_article | camera_mast_optional | `07A_ASA_mast_foot_first_article.3mf` | ASA | 0.24 mm | First corrected mast foot with rear-lug clamp bolts |
| 07B | optional | camera_mast_optional | `07B_ASA_mast_foot_second.3mf` | ASA | 0.24 mm | Second camera mast foot after first-article acceptance |
