# Job 06 — exact print settings

**STOP — exact process settings are supplied, but the physical spool's filament/thermal preset is unresolved. Do not print until the required spool inputs and calibrations are recorded and its material gate is PASS.**

## Job identity

- Plate: `06_ASA_mast_fit_tests.3mf`
- Purpose: Fixed-mast fallback 2020 socket and production-axis M5 nut/clearance/washer tests; blocked until the fallback architecture is explicitly released
- Stage / selection: `diagnostic` / `camera_mast_optional`
- Material class: **ASA**
- Components: `mast_socket_fit_test.stl` × 1, `m5_nut_trap_fit_gauge.stl` × 1
- Required gates: `fixed_camera_fallback_architecture_released`, `plus4_machine_confirmed`, `plus4_protected_envelope_verified`, `nozzle_0p4_confirmed`, `asa_profile_calibrated`

## Select these presets in QIDI Studio

- Verified QIDI Studio configuration: `2.7.2.60`
- Printer: `X-Plus 4 0.4 nozzle`
- Build surface: `Textured PEI Plate`
- Filament preset ID: `exact_asa_spool_xplus4_0p4`
- Filament preset in QIDI Studio: `QIDI ASA @Qidi X-Plus 4 0.4 nozzle`
- Process profile ID: `asa_structural_0p4`
- Imported process name: `RC03 ASA Mast Structural 0.24`
- Import process file: `../slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json`
- Base process preset: `0.24mm Draft @XPlus4`

## Filament settings

- Resolution status: `EXACT_SPOOL_PRESET_REQUIRED`
- Required operator inputs: `manufacturer`, `product name`, `spool lot`, `vendor preset name and revision`, `drying record`, `flow calibration`, `pressure advance calibration`
- Unresolved fields: `nozzle temperature`, `bed temperature`, `chamber temperature`, `flow ratio`, `pressure advance`, `maximum volumetric speed`, `cooling`

## Quality

| QIDI Studio key | Exact value |
|---|---|
| `layer_height` | `0.24` |
| `initial_layer_print_height` | `0.24` |
| `xy_hole_compensation` | `0` |
| `xy_contour_compensation` | `0` |
| `elefant_foot_compensation` | `0.15` |
| `seam_position` | `aligned` |
| `enable_arc_fitting` | `1` |
| `resolution` | `0.012` |

## Strength

| QIDI Studio key | Exact value |
|---|---|
| `wall_loops` | `6` |
| `top_shell_layers` | `6` |
| `bottom_shell_layers` | `6` |
| `sparse_infill_density` | `45%` |
| `sparse_infill_pattern` | `gyroid` |

## Speed

| QIDI Studio key | Exact value |
|---|---|
| `outer_wall_speed` | `50` |
| `inner_wall_speed` | `110` |
| `sparse_infill_speed` | `110` |
| `internal_solid_infill_speed` | `100` |
| `top_surface_speed` | `50` |
| `bridge_speed` | `30` |
| `gap_infill_speed` | `60` |
| `initial_layer_speed` | `25` |
| `initial_layer_infill_speed` | `40` |
| `travel_speed` | `400` |
| `default_acceleration` | `4000` |
| `travel_acceleration` | `6500` |
| `initial_layer_travel_acceleration` | `2500` |
| `initial_layer_acceleration` | `400` |
| `outer_wall_acceleration` | `1600` |
| `inner_wall_acceleration` | `2600` |
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
| `brim_width` | `10` |
| `brim_object_gap` | `0.05` |
| `skirt_loops` | `0` |
| `enable_prime_tower` | `0` |
| `print_sequence` | `by layer` |
| `fuzzy_skin` | `none` |

## Orientation, slicing, and preview checks

1. Import the plate at **100% scale**. Do not auto-orient, globally XY-scale, merge objects, or rearrange the centered group.
2. Preserve the locked exported Z=0 orientation. Keep raised or recessed labels and intended upward faces visible as modeled.
3. Supports: **off unless a released fallback revision approves build-plate-only support**
4. Bed adhesion: **10 mm outer brim, enclosed printer, stable chamber, and no drafts**
5. Dimensional controls: **Use same-spool ASA socket and nut coupons before a full mast foot**
6. Confirm object count, first-layer contact, open holes/slots, pocket roofs, thin walls, seams, and brim clearance in layer preview.
7. Save a native QIDI Studio project and record its version/path in the build evidence before printing.

## Controlled hashes

- Plate SHA-256: `02525021bb7f82f1d5c04946222ef5d898551181deb6bedda3b60a54cede6daa`
- Process profile SHA-256: `f1e5cb6562054f5363ffbb34572181e1e52fad37aea3595c4a7c5a9cfa8ec7c9`
- Filament preset SHA-256: `568d1ecd4a7a2acf80e0789ea89a8513e51af7d415c8d0e24041669682cb5953`
- Resolved preset SHA-256: `0709fd6261009b4b349152683fcbabd20c1c27739deda3aa24f5afd303f2ee81`
- QIDI process file SHA-256: `a6116150e09eb3212b6d4d76b7def11495593f564f497d2e8e5799ec6e69f7de`

The 3MF contains geometry and placement only. This sheet and its paired `.print.json` define setup; `PRINT_READINESS.md` grants or withholds authority to print.
