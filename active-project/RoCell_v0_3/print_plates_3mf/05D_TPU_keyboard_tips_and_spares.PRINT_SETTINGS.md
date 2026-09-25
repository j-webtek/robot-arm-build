# Job 05D — exact print settings

**STOP — exact process settings are supplied, but the physical spool's filament/thermal preset is unresolved. Do not print until the required spool inputs and calibrations are recorded and its material gate is PASS.**

## Job identity

- Plate: `05D_TPU_keyboard_tips_and_spares.3mf`
- Purpose: Three additional keyboard TPU tips, yielding two installed and two total spares
- Stage / selection: `production` / `keyboard_rod_route`
- Material class: **TPU 95A**
- Components: `keyboard_tip_TPU_6mm.stl` × 3
- Required gates: `plus4_machine_confirmed`, `plus4_protected_envelope_verified`, `nozzle_0p4_confirmed`, `tpu_profile_calibrated`, `keyboard_rod_measured`, `keyboard_tpu_retention_coupon_pass`, `qidi_studio_roundtrip_confirmed`

## Select these presets in QIDI Studio

- Verified QIDI Studio configuration: `2.7.2.60`
- Printer: `X-Plus 4 0.4 nozzle`
- Build surface: `Textured PEI Plate`
- Filament preset ID: `exact_tpu95a_spool_xplus4_0p4`
- Filament preset in QIDI Studio: `Generic TPU 95A @Qidi X-Plus 4 0.4 nozzle`
- Process profile ID: `tpu95a_0p4`
- Imported process name: `RC03 TPU 95A Contact Tips 0.16`
- Import process file: `../slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json`
- Base process preset: `0.16mm High Quality @XPlus4`

## Filament settings

- Resolution status: `EXACT_SPOOL_PRESET_REQUIRED`
- Required operator inputs: `manufacturer`, `product name`, `Shore hardness`, `spool lot`, `vendor preset name and revision`, `drying record`, `flow calibration`, `pressure advance calibration`
- Unresolved fields: `nozzle temperature`, `bed temperature`, `flow ratio`, `pressure advance`, `maximum volumetric speed`, `cooling`

## Quality

| QIDI Studio key | Exact value |
|---|---|
| `layer_height` | `0.16` |
| `initial_layer_print_height` | `0.2` |
| `xy_hole_compensation` | `0` |
| `xy_contour_compensation` | `0` |
| `elefant_foot_compensation` | `0.1` |
| `seam_position` | `aligned` |
| `enable_arc_fitting` | `1` |
| `resolution` | `0.012` |

## Strength

| QIDI Studio key | Exact value |
|---|---|
| `wall_loops` | `3` |
| `top_shell_layers` | `5` |
| `bottom_shell_layers` | `5` |
| `sparse_infill_density` | `100%` |
| `sparse_infill_pattern` | `rectilinear` |

## Speed

| QIDI Studio key | Exact value |
|---|---|
| `outer_wall_speed` | `30` |
| `inner_wall_speed` | `45` |
| `sparse_infill_speed` | `45` |
| `internal_solid_infill_speed` | `40` |
| `top_surface_speed` | `30` |
| `bridge_speed` | `20` |
| `gap_infill_speed` | `30` |
| `initial_layer_speed` | `20` |
| `initial_layer_infill_speed` | `25` |
| `travel_speed` | `250` |
| `default_acceleration` | `2000` |
| `travel_acceleration` | `3500` |
| `initial_layer_travel_acceleration` | `1500` |
| `initial_layer_acceleration` | `300` |
| `outer_wall_acceleration` | `800` |
| `inner_wall_acceleration` | `1200` |
| `top_surface_acceleration` | `800` |

## Support

| QIDI Studio key | Exact value |
|---|---|
| `enable_support` | `0` |

## Others

| QIDI Studio key | Exact value |
|---|---|
| `ironing_type` | `no ironing` |
| `brim_type` | `outer_only` |
| `brim_width` | `3` |
| `brim_object_gap` | `0.1` |
| `skirt_loops` | `0` |
| `enable_prime_tower` | `0` |
| `print_sequence` | `by layer` |
| `fuzzy_skin` | `none` |

## Orientation, slicing, and preview checks

1. Import the plate at **100% scale**. Do not auto-orient, globally XY-scale, merge objects, or rearrange the centered group.
2. Preserve the locked exported Z=0 orientation. Keep raised or recessed labels and intended upward faces visible as modeled.
3. Supports: **off**
4. Bed adhesion: **3 mm outer brim with 0.10 mm object gap after the exact dry TPU spool is qualified**
5. Dimensional controls: **Keep first-layer flow calibrated so flared bore entries remain open; do not force a failed tip onto hardware**
6. Confirm object count, first-layer contact, open holes/slots, pocket roofs, thin walls, seams, and brim clearance in layer preview.
7. Save a native QIDI Studio project and record its version/path in the build evidence before printing.

## Controlled hashes

- Plate SHA-256: `63efc560b375ce5a6abbd5092f51632a51de8771b90aca70794ec6b7e999e843`
- Process profile SHA-256: `4d655c7387b95cece3d27151ae8a7283688bbf87db088790376aa3156d5afd4b`
- Filament preset SHA-256: `945d923a44ad2a09516d5ae3dceffc8bcd567a4e4c25b408ff4879c2435bb9cf`
- Resolved preset SHA-256: `f64a085bf3b87253b51e2b5c837bea6bec0ce13dc98bd1e4f779c41acf3624a4`
- QIDI process file SHA-256: `547c6502ce8d5f4b04a5d247b50fcafb884dbe587b1df9c43935dfa6d297e6ba`

The 3MF contains geometry and placement only. This sheet and its paired `.print.json` define setup; `PRINT_READINESS.md` grants or withholds authority to print.
