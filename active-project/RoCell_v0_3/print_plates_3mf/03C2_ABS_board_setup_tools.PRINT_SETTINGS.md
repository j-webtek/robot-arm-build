# Job 03C2 — exact print settings

**EXACT_REPRODUCIBLE — the machine, process, and QIDI ABS Rapido filament preset are all identified. Print authority still comes only from `PRINT_READINESS.md`.**

## Job identity

- Plate: `03C2_ABS_board_setup_tools.3mf`
- Purpose: Reusable ABS 55 mm direct-tag application frame and board setup tooling
- Stage / selection: `production` / `required`
- Material class: **QIDI ABS Rapido**
- Components: `tag_application_frame_55mm.stl` × 1
- Required gates: `plus4_machine_confirmed`, `plus4_protected_envelope_verified`, `nozzle_0p4_confirmed`, `abs_rapido_general_profile_calibrated`, `tag_stock_measured`, `tag_artwork_scale_pass`, `board_setup_template_scale_pass`, `geometry_matches_measurements`, `qidi_studio_roundtrip_confirmed`

## Select these presets in QIDI Studio

- Verified QIDI Studio configuration: `2.7.2.60`
- Printer: `X-Plus 4 0.4 nozzle`
- Build surface: `Textured PEI Plate`
- Filament preset ID: `qidi_abs_rapido_xplus4_0p4`
- Filament preset in QIDI Studio: `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle`
- Process profile ID: `abs_rapido_general_0p4`
- Imported process name: `RC03 ABS Rapido General 0.20`
- Import process file: `../slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json`
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
| `wall_loops` | `4` |
| `top_shell_layers` | `5` |
| `bottom_shell_layers` | `5` |
| `sparse_infill_density` | `25%` |
| `sparse_infill_pattern` | `gyroid` |
| `internal_solid_infill_pattern` | `zig-zag` |

## Speed

| QIDI Studio key | Exact value |
|---|---|
| `initial_layer_speed` | `30` |
| `initial_layer_infill_speed` | `50` |
| `outer_wall_speed` | `60` |
| `inner_wall_speed` | `130` |
| `sparse_infill_speed` | `140` |
| `internal_solid_infill_speed` | `110` |
| `top_surface_speed` | `50` |
| `bridge_speed` | `35` |
| `gap_infill_speed` | `70` |
| `travel_speed` | `500` |
| `default_acceleration` | `4500` |
| `travel_acceleration` | `7500` |
| `initial_layer_travel_acceleration` | `2800` |
| `initial_layer_acceleration` | `500` |
| `outer_wall_acceleration` | `1800` |
| `inner_wall_acceleration` | `2800` |
| `top_surface_acceleration` | `1200` |

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
5. Dimensional controls: **Zero XY contour and hole compensation until the matching ABS coupon provides measured evidence; elephant-foot compensation 0.15 mm**
6. Confirm object count, first-layer contact, open holes/slots, pocket roofs, thin walls, seams, and brim clearance in layer preview.
7. Save a native QIDI Studio project and record its version/path in the build evidence before printing.

## Controlled hashes

- Plate SHA-256: `6f84a4addac525d32ebe0685c5f11764a15270caf11d29bd6bda20338e1e3b6b`
- Process profile SHA-256: `4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede`
- Filament preset SHA-256: `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4`
- Resolved preset SHA-256: `40860f3c2b9992ca64e8b43746f6a8746a91724e78f6339e16cda41b943971d8`
- QIDI process file SHA-256: `756895e547ed186ab4b0d532d6d66fc3e2ad31376bc342a0150cbd4667a5d239`

The 3MF contains geometry and placement only. This sheet and its paired `.print.json` define setup; `PRINT_READINESS.md` grants or withholds authority to print.
