# Job 04C — exact print settings

**STOP — exact process settings are supplied, but the physical spool's filament/thermal preset is unresolved. Do not print until the required spool inputs and calibrations are recorded and its material gate is PASS.**

## Job identity

- Plate: `04C_PETG_keyboard_rod_adapters.3mf`
- Purpose: Two keyboard-route rod bushings for retention qualification and one spare
- Stage / selection: `route` / `keyboard_rod_route`
- Material class: **PETG**
- Components: `rod_bushing_6_to_9mm.stl` × 2
- Required gates: `plus4_machine_confirmed`, `plus4_protected_envelope_verified`, `nozzle_0p4_confirmed`, `petg_adapter_profile_calibrated`, `keyboard_rod_measured`, `adapter_retention_method_selected`, `geometry_matches_measurements`, `qidi_studio_roundtrip_confirmed`

## Select these presets in QIDI Studio

- Verified QIDI Studio configuration: `2.7.2.60`
- Printer: `X-Plus 4 0.4 nozzle`
- Build surface: `Textured PEI Plate`
- Filament preset ID: `exact_petg_spool_xplus4_0p4`
- Filament preset in QIDI Studio: `Generic PETG @Qidi X-Plus 4 0.4 nozzle`
- Process profile ID: `petg_adapter_0p4`
- Imported process name: `RC03 PETG Split Adapter 0.12`
- Import process file: `../slicer_profiles/QIDI_PLUS4/petg_adapter_0p4.process.json`
- Base process preset: `0.12mm High Quality @XPlus4`

## Filament settings

- Resolution status: `EXACT_SPOOL_PRESET_REQUIRED`
- Required operator inputs: `manufacturer`, `product name`, `spool lot`, `vendor preset name and revision`, `drying record`, `flow calibration`, `pressure advance calibration`
- Unresolved fields: `nozzle temperature`, `bed temperature`, `chamber temperature`, `flow ratio`, `pressure advance`, `maximum volumetric speed`, `cooling`

## Quality

| QIDI Studio key | Exact value |
|---|---|
| `layer_height` | `0.12` |
| `initial_layer_print_height` | `0.2` |
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
| `sparse_infill_density` | `100%` |
| `sparse_infill_pattern` | `rectilinear` |

## Speed

| QIDI Studio key | Exact value |
|---|---|
| `outer_wall_speed` | `45` |
| `inner_wall_speed` | `90` |
| `sparse_infill_speed` | `90` |
| `internal_solid_infill_speed` | `80` |
| `top_surface_speed` | `45` |
| `bridge_speed` | `25` |
| `gap_infill_speed` | `60` |
| `initial_layer_speed` | `25` |
| `initial_layer_infill_speed` | `40` |
| `travel_speed` | `350` |
| `default_acceleration` | `3500` |
| `travel_acceleration` | `6000` |
| `initial_layer_travel_acceleration` | `2000` |
| `initial_layer_acceleration` | `400` |
| `outer_wall_acceleration` | `1500` |
| `inner_wall_acceleration` | `2200` |
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
| `brim_width` | `8` |
| `brim_object_gap` | `0.1` |
| `skirt_loops` | `0` |
| `enable_prime_tower` | `0` |
| `print_sequence` | `by layer` |
| `fuzzy_skin` | `none` |

## Orientation, slicing, and preview checks

1. Import the plate at **100% scale**. Do not auto-orient, globally XY-scale, merge objects, or rearrange the centered group.
2. Preserve the locked exported Z=0 orientation. Keep raised or recessed labels and intended upward faces visible as modeled.
3. Supports: **off**
4. Bed adhesion: **8 mm outer brim with 0.10 mm object gap after the exact PETG spool is qualified**
5. Dimensional controls: **Calibrate elephant-foot compensation so split bores remain open; never globally scale**
6. Confirm object count, first-layer contact, open holes/slots, pocket roofs, thin walls, seams, and brim clearance in layer preview.
7. Save a native QIDI Studio project and record its version/path in the build evidence before printing.

## Controlled hashes

- Plate SHA-256: `39b706d658b093fe29c7cd845412ba2082dacdb6cf321b97d9cb6209a5e81427`
- Process profile SHA-256: `ce4f08af3ad5623c70bc5bb65dc086ae69cb51b98410dd26e85dbd0c1f693747`
- Filament preset SHA-256: `e4af446b19a2425a1f87b49feb022fb06e525dc92f670689940c8dade2908fc4`
- Resolved preset SHA-256: `13f92ee97bdb5a9d652e943c052bacd7be2ecb3321ceef6c7a19d7e465249e0a`
- QIDI process file SHA-256: `0eac339f7768fb799fa420cd300710e080134d0c0737652fd9afd51d9bc4fa91`

The 3MF contains geometry and placement only. This sheet and its paired `.print.json` define setup; `PRINT_READINESS.md` grants or withholds authority to print.
