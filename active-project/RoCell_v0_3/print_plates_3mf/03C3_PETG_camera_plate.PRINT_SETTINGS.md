# Job 03C3 — exact print settings

**STOP — exact process settings are supplied, but the physical spool's filament/thermal preset is unresolved. Do not print until the required spool inputs and calibrations are recorded and its material gate is PASS.**

## Job identity

- Plate: `03C3_PETG_camera_plate.3mf`
- Purpose: Fixed-mast fallback camera plate; not an arm-camera adapter and not released while the camera architecture hold is open
- Stage / selection: `production` / `camera_mast_optional`
- Material class: **PETG**
- Components: `camera_plate_universal.stl` × 1
- Required gates: `fixed_camera_fallback_architecture_released`, `plus4_machine_confirmed`, `plus4_protected_envelope_verified`, `nozzle_0p4_confirmed`, `petg_general_profile_calibrated`, `camera_mount_interface_measured`, `general_clearance_holes_coupon_pass`, `setup_hardware_coupon_pass`, `geometry_matches_measurements`, `qidi_studio_roundtrip_confirmed`

## Select these presets in QIDI Studio

- Verified QIDI Studio configuration: `2.7.2.60`
- Printer: `X-Plus 4 0.4 nozzle`
- Build surface: `Textured PEI Plate`
- Filament preset ID: `exact_petg_spool_xplus4_0p4`
- Filament preset in QIDI Studio: `Generic PETG @Qidi X-Plus 4 0.4 nozzle`
- Process profile ID: `petg_general_0p4`
- Imported process name: `RC03 PETG General 0.20`
- Import process file: `../slicer_profiles/QIDI_PLUS4/petg_general_0p4.process.json`
- Base process preset: `0.20mm Standard @XPlus4`

## Filament settings

- Resolution status: `EXACT_SPOOL_PRESET_REQUIRED`
- Required operator inputs: `manufacturer`, `product name`, `spool lot`, `vendor preset name and revision`, `drying record`, `flow calibration`, `pressure advance calibration`
- Unresolved fields: `nozzle temperature`, `bed temperature`, `chamber temperature`, `flow ratio`, `pressure advance`, `maximum volumetric speed`, `cooling`

## Quality

| QIDI Studio key | Exact value |
|---|---|
| `layer_height` | `0.2` |
| `initial_layer_print_height` | `0.2` |
| `xy_hole_compensation` | `0` |
| `xy_contour_compensation` | `0` |
| `elefant_foot_compensation` | `0.15` |

## Strength

| QIDI Studio key | Exact value |
|---|---|
| `wall_loops` | `4` |
| `top_shell_layers` | `5` |
| `bottom_shell_layers` | `5` |
| `sparse_infill_density` | `25%` |
| `sparse_infill_pattern` | `gyroid` |

## Speed

| QIDI Studio key | Exact value |
|---|---|
| `outer_wall_speed` | `60` |
| `inner_wall_speed` | `120` |
| `sparse_infill_speed` | `130` |
| `internal_solid_infill_speed` | `100` |
| `top_surface_speed` | `50` |
| `bridge_speed` | `30` |
| `gap_infill_speed` | `70` |
| `initial_layer_speed` | `25` |
| `initial_layer_infill_speed` | `40` |
| `default_acceleration` | `4000` |
| `travel_acceleration` | `7000` |
| `outer_wall_acceleration` | `1600` |
| `inner_wall_acceleration` | `2600` |
| `top_surface_acceleration` | `1100` |

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
| `brim_object_gap` | `0.1` |
| `enable_prime_tower` | `0` |
| `print_sequence` | `by layer` |
| `fuzzy_skin` | `none` |

## Orientation, slicing, and preview checks

1. Import the plate at **100% scale**. Do not auto-orient, globally XY-scale, merge objects, or rearrange the centered group.
2. Preserve the locked exported Z=0 orientation. Keep raised or recessed labels and intended upward faces visible as modeled.
3. Supports: **off**
4. Bed adhesion: **5 mm outer brim after the exact PETG spool is qualified**
5. Dimensional controls: **Use only with same-spool coupons**
6. Confirm object count, first-layer contact, open holes/slots, pocket roofs, thin walls, seams, and brim clearance in layer preview.
7. Save a native QIDI Studio project and record its version/path in the build evidence before printing.

## Controlled hashes

- Plate SHA-256: `b659444974c21f27d0832b97b0511edd4a879c2049d81ae010cb28d61c8eae42`
- Process profile SHA-256: `00f5efa4c8c65c9857564a255fdec4d4eaa571962c83d77095a470a20942edc6`
- Filament preset SHA-256: `e4af446b19a2425a1f87b49feb022fb06e525dc92f670689940c8dade2908fc4`
- Resolved preset SHA-256: `160b234cf8bc1509030601f0ecfaf61b123c7bf746a8921b5e7bb7e9b38beb04`
- QIDI process file SHA-256: `4e3fcda86460e9823234db1eff750e880a8b43bcb916dc2b584038b97376b605`

The 3MF contains geometry and placement only. This sheet and its paired `.print.json` define setup; `PRINT_READINESS.md` grants or withholds authority to print.
