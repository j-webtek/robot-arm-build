# Job 00A — exact print settings

**EXACT_REPRODUCIBLE — the machine, process, and QIDI ABS Rapido filament preset are all identified. Print authority still comes only from `PRINT_READINESS.md`.**

## Job identity

- Plate: `00A_ABS_keyboard_station_fit_tests.3mf`
- Purpose: ABS keyboard datum, board/seam locator, clearance, and washer qualification using the exact station profile
- Stage / selection: `diagnostic` / `required`
- Material class: **QIDI ABS Rapido**
- Components: `keyboard_corner_fit_test.stl` × 1, `station_locator_fit_gauge.stl` × 1, `hardware_fit_gauge.stl` × 1, `m4_washer_fit_gauge.stl` × 1
- Required gates: `plus4_machine_confirmed`, `plus4_protected_envelope_verified`, `nozzle_0p4_confirmed`, `abs_rapido_tray_profile_calibrated`

## Select these presets in QIDI Studio

- Verified QIDI Studio configuration: `2.7.2.60`
- Printer: `X-Plus 4 0.4 nozzle`
- Build surface: `Textured PEI Plate`
- Filament preset ID: `qidi_abs_rapido_xplus4_0p4`
- Filament preset in QIDI Studio: `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle`
- Process profile ID: `abs_rapido_tray_structural_0p4`
- Imported process name: `RC03 ABS Rapido Tray Structural 0.20`
- Import process file: `../slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json`
- Base process preset: `0.20mm Standard @XPlus4`

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
| `layer_height` | `0.2` |
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
| `sparse_infill_density` | `35%` |
| `sparse_infill_pattern` | `gyroid` |
| `internal_solid_infill_pattern` | `zig-zag` |

## Speed

| QIDI Studio key | Exact value |
|---|---|
| `initial_layer_speed` | `30` |
| `initial_layer_infill_speed` | `50` |
| `outer_wall_speed` | `60` |
| `inner_wall_speed` | `140` |
| `sparse_infill_speed` | `150` |
| `internal_solid_infill_speed` | `120` |
| `top_surface_speed` | `60` |
| `bridge_speed` | `40` |
| `gap_infill_speed` | `80` |
| `travel_speed` | `500` |
| `default_acceleration` | `5000` |
| `travel_acceleration` | `8000` |
| `initial_layer_travel_acceleration` | `3000` |
| `initial_layer_acceleration` | `500` |
| `outer_wall_acceleration` | `2000` |
| `inner_wall_acceleration` | `3000` |
| `top_surface_acceleration` | `1500` |

## Support

| QIDI Studio key | Exact value |
|---|---|
| `enable_support` | `0` |

## Others

| QIDI Studio key | Exact value |
|---|---|
| `ironing_type` | `no ironing` |
| `brim_type` | `outer_only` |
| `brim_width` | `8` |
| `brim_object_gap` | `0.05` |
| `skirt_loops` | `0` |
| `enable_prime_tower` | `0` |
| `print_sequence` | `by layer` |
| `fuzzy_skin` | `none` |

## Orientation, slicing, and preview checks

1. Import the plate at **100% scale**. Do not auto-orient, globally XY-scale, merge objects, or rearrange the centered group.
2. Preserve the locked exported Z=0 orientation. Keep raised or recessed labels and intended upward faces visible as modeled.
3. Supports: **off**
4. Bed adhesion: **8 mm outer brim with 0.05 mm object gap; clean textured PEI; one production station per plate**
5. Dimensional controls: **Keep the slicer seam away from locator sockets, relieved hold-down holes, seam datums, clamp guides, and keyboard contact datums; zero XY compensation pending Job 00A**
6. Confirm object count, first-layer contact, open holes/slots, pocket roofs, thin walls, seams, and brim clearance in layer preview.
7. Save a native QIDI Studio project and record its version/path in the build evidence before printing.

## Controlled hashes

- Plate SHA-256: `cdedea55ccdf765a78d35b976cbd18ea153dc8caf6fb91ce08e507c9be837237`
- Process profile SHA-256: `4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f`
- Filament preset SHA-256: `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4`
- Resolved preset SHA-256: `ba7c7bb09cea3d44840bb5ddda5815d01765de8391e5daab1791b41f428975f6`
- QIDI process file SHA-256: `c89e92d6af33cb676d7200e34937ec05c7cec9b55f2d0700b07b89a57cbd81c6`

The 3MF contains geometry and placement only. This sheet and its paired `.print.json` define setup; `PRINT_READINESS.md` grants or withholds authority to print.
