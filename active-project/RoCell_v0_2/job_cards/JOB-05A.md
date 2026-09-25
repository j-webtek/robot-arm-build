# Job 05A - One phone TPU tip for dimensional and pull-off acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PHONE` |
| Plate | `05A_TPU_phone_tip_first_article.3mf` |
| Plate SHA-256 | `05d7b42e788b5c03bc60740145ed28b08074330aa980aa9795f3c0c8d8c2e23b` |
| Profile | `tpu95a_0p4` / `59b69f285f6bead89753b66a3fa1005b3db9b065b58905e3dd84fa684dfa9e49` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | TPU 95A / 0.4 mm / 0.16 mm |
| Plate envelope | 7.5 x 7.5 x 8.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_clamp_tip_TPU_M4.stl` | 1 | Upright, flared bore entry on bed | `77883a940d153460346de3ffdfcf3a281e2572ab404dd1f4dc50ec8808afef94` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual M4 screw/peg and pull gauge.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Clean PEI with no glue unless required by the exact TPU; use a 3 mm brim if a tip rocks.
- Dimensional controls: Dry filament and keep first-layer flow calibrated so the flared bore entries remain open.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect flared bore, seating witness and contact face. Fit to actual hardware, record seating depth and provisional axial pull force; retain as the first article.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_tpu_retention_coupon_pass`.

## Signoff

| Record | Entry |
|---|---|
| Spool brand / lot / dry record | ______________________________ |
| QIDI Studio project / version | ______________________________ |
| Printed date / operator | ______________________________ |
| Measured values / tool ID | ______________________________ |
| Evidence folder / photo IDs | ______________________________ |
| Result | [ ] PASS  [ ] REWORK  [ ] QUARANTINE |
| Inspector / date | ______________________________ |
