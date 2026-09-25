# Job 04A — exact print settings

**EXACT_REPRODUCIBLE — the machine, process, and QIDI ABS Rapido filament preset are all identified. Print authority still comes only from `PRINT_READINESS.md`.**

## Job identity

- Plate: `04A_ABS_shared_compliant_tool.3mf`
- Purpose: Shared ABS compliant tool body with keyed cap and one spare cap
- Stage / selection: `route` / `any_tool_route`
- Material class: **QIDI ABS Rapido**
- Components: `compliant_tool_body.stl` × 1, `compliant_tool_top_cap.stl` × 2
- Required gates: `plus4_machine_confirmed`, `plus4_protected_envelope_verified`, `nozzle_0p4_confirmed`, `abs_rapido_precision_profile_calibrated`, `compliant_tool_m3_insert_coupon_pass`, `gripper_interface_measured`, `gripper_coupon_pass`, `spring_dimensions_measured`, `spring_fit_coupon_pass`, `precision_m3_head_coupon_pass`, `geometry_matches_measurements`, `qidi_studio_roundtrip_confirmed`

## Select these presets in QIDI Studio

- Verified QIDI Studio configuration: `2.7.2.60`
- Printer: `X-Plus 4 0.4 nozzle`
- Build surface: `Textured PEI Plate`
- Filament preset ID: `qidi_abs_rapido_xplus4_0p4`
- Filament preset in QIDI Studio: `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle`
- Process profile ID: `abs_rapido_precision_0p4`
- Imported process name: `RC03 ABS Rapido Precision 0.16`
- Import process file: `../slicer_profiles/QIDI_PLUS4/abs_rapido_precision_0p4.process.json`
- Base process preset: `0.16mm High Quality @XPlus4`

## Filament settings

- Resolution status: `CONFIRMED_EXACT`
- `nozzle_temperature_c`: {"allowed_range": [240, 280], "initial_layer": 250, "other_layers": 260}
- `textured_bed_temperature_c`: {"initial_layer": 90, "other_layers": 90}
- `chamber_temperature_c`: 55
- `enclosure`: sealed
- `flow_ratio`: 0.95
- `pressure_advance`: {"enabled": true, "value": 0.03}
- `max_volumetric_speed_mm3_s`: 24.5
- `cooling`: {"auxiliary_fan_percent": 0, "exhaust_after_print_percent": 0, "exhaust_during_print_percent": 0, "fan_off_first_layers": 3, "model_fan_max_percent": 80, "model_fan_min_percent": 20, "overhang_fan_percent": 80, "overhang_threshold_percent": 25}

## Quality

| QIDI Studio key | Exact value |
|---|---|
| `layer_height` | `0.16` |
| `initial_layer_print_height` | `0.2` |
| `line_width` | `0.42` |
| `initial_layer_line_width` | `0.5` |
| `outer_wall_line_width` | `0.42` |
| `inner_wall_line_width` | `0.45` |
| `top_surface_line_width` | `0.42` |
| `sparse_infill_line_width` | `0.45` |
| `internal_solid_infill_line_width` | `0.42` |
| `wall_generator` | `classic` |
| `wall_sequence` | `inner wall/outer wall` |
| `xy_hole_compensation` | `0` |
| `xy_contour_compensation` | `0` |
| `elefant_foot_compensation` | `0.15` |
| `seam_position` | `aligned` |
| `enable_arc_fitting` | `1` |
| `resolution` | `0.012` |

## Strength

| QIDI Studio key | Exact value |
|---|---|
| `wall_loops` | `5` |
| `top_shell_layers` | `6` |
| `bottom_shell_layers` | `6` |
| `sparse_infill_density` | `40%` |
| `sparse_infill_pattern` | `gyroid` |
| `internal_solid_infill_pattern` | `zig-zag` |

## Speed

| QIDI Studio key | Exact value |
|---|---|
| `initial_layer_speed` | `25` |
| `initial_layer_infill_speed` | `40` |
| `outer_wall_speed` | `45` |
| `inner_wall_speed` | `90` |
| `sparse_infill_speed` | `100` |
| `internal_solid_infill_speed` | `80` |
| `top_surface_speed` | `40` |
| `bridge_speed` | `30` |
| `gap_infill_speed` | `60` |
| `travel_speed` | `450` |
| `default_acceleration` | `4000` |
| `travel_acceleration` | `7000` |
| `initial_layer_travel_acceleration` | `2500` |
| `initial_layer_acceleration` | `400` |
| `outer_wall_acceleration` | `1500` |
| `inner_wall_acceleration` | `2500` |
| `top_surface_acceleration` | `1000` |

## Support

| QIDI Studio key | Exact value |
|---|---|
| `enable_support` | `0` |

## Others

| QIDI Studio key | Exact value |
|---|---|
| `ironing_type` | `no ironing` |
| `brim_type` | `outer_only` |
| `brim_width` | `5` |
| `brim_object_gap` | `0.05` |
| `skirt_loops` | `0` |
| `enable_prime_tower` | `0` |
| `print_sequence` | `by layer` |
| `fuzzy_skin` | `none` |

## Orientation, slicing, and preview checks

1. Import the plate at **100% scale**. Do not auto-orient, globally XY-scale, merge objects, or rearrange the centered group.
2. Preserve the locked exported Z=0 orientation. Keep raised or recessed labels and intended upward faces visible as modeled.
3. Supports: **off**
4. Bed adhesion: **5 mm outer brim with 0.05 mm object gap on clean textured PEI**
5. Dimensional controls: **Keep the seam off gripper flats, spring seats, insert pockets, and the sliding guide bore; zero XY compensation pending Job 00C**
6. Confirm object count, first-layer contact, open holes/slots, pocket roofs, thin walls, seams, and brim clearance in layer preview.
7. Save a native QIDI Studio project and record its version/path in the build evidence before printing.

## Controlled hashes

- Plate SHA-256: `91a9be9ec968c66b10543d13faae269d991b176fffd105d801a07f4a08107882`
- Process profile SHA-256: `60827c142c2f8e88c0a45ace71712cf2c94f84d66dc796880352ab32de1e7195`
- Filament preset SHA-256: `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4`
- Resolved preset SHA-256: `c50226a292699926b12c6d5e5aea7ec7bc42628a554e45a6ab950648f3125741`
- QIDI process file SHA-256: `c115ad0ca8acafa86bc303973bbbae27578fdd57db8cbf437a7c8175710ba90a`

The 3MF contains geometry and placement only. This sheet and its paired `.print.json` define setup; `PRINT_READINESS.md` grants or withholds authority to print.
