# QIDI Plus4 measured print jobs

Start with `../PRINT_READINESS.md`. Print only a selected job marked READY.

Every `.3mf` has a same-name `.print.json` machine-readable sidecar and `.PRINT_SETTINGS.md` operator sheet. Together they are the authoritative source for the exact machine, filament and process presets, material, nozzle, layer height, walls, shells, infill, speeds, acceleration, support, adhesion, contents, hashes, and prerequisite gate IDs.

Import the matching process preset from `../slicer_profiles/QIDI_PLUS4/`. The 3MF files intentionally contain geometry and placement only. QIDI ABS Rapido uses the exact confirmed system filament preset; PETG, TPU, and ASA jobs remain blocked until the exact physical spool preset is recorded.

| Job | Stage | Selection | Plate | Material | Layer | Purpose |
|---|---|---|---|---|---:|---|
| 00A | diagnostic | required | `00A_ABS_keyboard_station_fit_tests.3mf` | QIDI ABS Rapido | 0.20 mm | ABS keyboard datum, board/seam locator, clearance, and washer qualification using the exact station profile |
| 00B | diagnostic | required | `00B_ABS_phone_station_fit_tests.3mf` | QIDI ABS Rapido | 0.20 mm | ABS phone width, station locator, profile-specific M3 insert, and washer qualification; retained nut and cable-saddle objects document superseded screening geometry |
| 00C | diagnostic | required | `00C_ABS_tool_profile_fit_tests.3mf` | QIDI ABS Rapido | 0.16 mm | ABS RoArm grip, stepped spring seat, profile-specific M3 insert, and M3 head tests using the exact tool profile |
| 00D | diagnostic | phone_stylus_route | `00D_PETG_adapter_profile_fit_tests.3mf` | PETG | 0.12 mm | Phone-stylus-route sliding-fit qualification using the exact adapter profile |
| 00E | diagnostic | required | `00E_ABS_general_setup_tests.3mf` | QIDI ABS Rapido | 0.20 mm | ABS general clearance, screw-head, washer, camera-hex, and TPU-retention setup tests |
| 00F | diagnostic | required | `00F_ABS_calibration_profile_clearance_test.3mf` | QIDI ABS Rapido | 0.16 mm | ABS M3 clearance and M3 button-head recess verification using the exact fine-layer calibration-puck profile |
| 01 | first_article | required | `01_ABS_keyboard_station_left.3mf` | QIDI ABS Rapido | 0.20 mm | ABS left master keyboard station with integrated datums, locator sockets, clamp track, and seam posts |
| 02 | production | required | `02_ABS_keyboard_station_right.3mf` | QIDI ABS Rapido | 0.20 mm | ABS right slave keyboard station located from the accepted left-station seam |
| 03A | first_article | required | `03A_ABS_phone_TCP_station.3mf` | QIDI ABS Rapido | 0.20 mm | Integrated ABS phone and TCP service station with fixed datums, keyed receiver, and replaceable-rail interface |
| 03B | production | required | `03B_ABS_keyboard_clamps.3mf` | QIDI ABS Rapido | 0.20 mm | Two replaceable ABS guided keyboard rear clamp sliders |
| 03C1 | first_article | required | `03C1_ABS_phone_clamp_rail.3mf` | QIDI ABS Rapido | 0.20 mm | Production-equivalent ABS phone keeper and clamp-tower rail that qualifies the revised captive-nut seats and adopted wide-tie saddle before Job 03A |
| 03C2 | production | required | `03C2_ABS_board_setup_tools.3mf` | QIDI ABS Rapido | 0.20 mm | Reusable ABS 55 mm direct-tag application frame and board setup tooling |
| 03C3 | production | camera_mast_optional | `03C3_PETG_camera_plate.3mf` | PETG | 0.20 mm | Fixed-mast fallback camera plate; not an arm-camera adapter and not released while the camera architecture hold is open |
| 03D | first_article | required | `03D_ABS_TCP_datum_cartridges.3mf` | QIDI ABS Rapido | 0.16 mm | Two keyed ABS TCP datum cartridges: one selected INSTALL datum and one qualified recalibration-required SPARE |
| 04A | route | any_tool_route | `04A_ABS_shared_compliant_tool.3mf` | QIDI ABS Rapido | 0.16 mm | Shared ABS compliant tool body with keyed cap and one spare cap |
| 04B | route | phone_stylus_route | `04B_PETG_phone_stylus_adapters.3mf` | PETG | 0.12 mm | Two phone-route stylus collars for thin-wall retention qualification and one spare |
| 04C | route | keyboard_rod_route | `04C_PETG_keyboard_rod_adapters.3mf` | PETG | 0.12 mm | Two keyboard-route rod bushings for retention qualification and one spare |
| 05A | first_article | required | `05A_TPU_phone_tip_first_article.3mf` | TPU 95A | 0.16 mm | One phone TPU tip for dimensional and pull-off acceptance |
| 05B | production | required | `05B_TPU_phone_tips_and_spares.3mf` | TPU 95A | 0.16 mm | Three additional phone TPU tips, yielding two installed and two total spares |
| 05C | first_article | keyboard_rod_route | `05C_TPU_keyboard_tip_first_article.3mf` | TPU 95A | 0.16 mm | One keyboard TPU tip for dimensional and pull-off acceptance |
| 05D | production | keyboard_rod_route | `05D_TPU_keyboard_tips_and_spares.3mf` | TPU 95A | 0.16 mm | Three additional keyboard TPU tips, yielding two installed and two total spares |
| 06 | diagnostic | camera_mast_optional | `06_ASA_mast_fit_tests.3mf` | ASA | 0.24 mm | Fixed-mast fallback 2020 socket and production-axis M5 nut/clearance/washer tests; blocked until the fallback architecture is explicitly released |
| 07A | first_article | camera_mast_optional | `07A_ASA_mast_foot_first_article.3mf` | ASA | 0.24 mm | First fixed-mast fallback foot with rear-lug clamp bolts; not part of the intended arm-mounted camera architecture |
| 07B | optional | camera_mast_optional | `07B_ASA_mast_foot_second.3mf` | ASA | 0.24 mm | Second fixed-mast fallback foot after first-article acceptance; not part of the intended arm-mounted camera architecture |
