# Printable camera-frame QIDI Studio profiles

These process files are additive **prototype** profiles for the QIDI
X-Plus 4 with the confirmed `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle`
filament preset. They do not replace the existing RC03 profiles or transfer
qualification from the inactive PETG/ASA mast jobs.

| Process file | Use | Critical settings |
| --- | --- | --- |
| `abs_rapido_camera_frame_structural_0p4.process.json` | `00G-S1`, every `08A`/`08B` plate, and every `08C` plate: coupons, external splice collars, saddles/caps, upright/crossbar/boom members, corner/root nodes, and direct carriage | 0.20 mm; 6 walls; 7 top/bottom layers; 40% gyroid; outer-only 10 mm brim with 0.05 mm gap; supports off; 45 mm/s outer wall; 3000 mm/s^2 normal acceleration |
| `abs_rapido_camera_holder_precision_0p4.process.json` | `00G-C1` camera gauge/shim ladder and `08D-C1` cage/keeper | 0.16 mm; 5 walls; 7 top/bottom layers; 45% gyroid; outer-only 6 mm brim with 0.05 mm gap; supports off; 35 mm/s outer wall; 2500 mm/s^2 normal acceleration |
| `tpu95a_camera_clamp_pad_0p4.process.json` | `00G-P1`: four mechanically captured board-protection pads plus one mechanically trapped camera top-compression pad | 0.16 mm; 3 walls; 100% rectilinear; outer-only 3 mm brim with 0.1 mm gap; supports off; 30 mm/s outer wall; 2000 mm/s^2 normal acceleration |

## Import

1. In QIDI Studio select `X-Plus 4 0.4 nozzle` and `Textured PEI Plate`.
2. Select the exact QIDI ABS Rapido filament preset already recorded by RC03,
   except for `board_pressure_pad` and `camera_top_compression_pad`, which use
   the installed TPU 95A filament preset and the TPU process above.
3. Import the appropriate `.process.json` file.
4. Confirm the imported process name exactly matches the `name` field.
5. Open the validated numbered geometry-only 3MF named in
   [`../../print_jobs/printable_camera_frame_jobs.json`](../../print_jobs/printable_camera_frame_jobs.json),
   verify it against its same-base `.print.json` sidecar, keep model scale at
   `100.00%`, inspect every layer, and use the sidecar's separate native
   save-as name. Never overwrite the generated geometry 3MF.

[`../../cad/output/PLATE_VALIDATION.json`](../../cad/output/PLATE_VALIDATION.json)
supplies the validated stored plate layout and object count. Keep those object
transforms, with raised IDs upward. Do not auto-arrange, rotate a part out of
the XY plane, globally scale a fit failure, enable fuzzy skin, or substitute
the printer's maximum-speed defaults.

These settings make a strong first article; they do not establish long-term
camera stability. The assembled frame still requires joint, board-clamp, sag,
cable-tug, disturbance, thermal and 24-hour drift tests.

Do not substitute the existing PETG process for the towers, crossbar, booms,
splices, saddles, or camera cage. PETG remains available elsewhere in RC03 for
its assigned adapter parts, but this overhead prototype is dimensioned and
qualified as an ABS Rapido structure; a PETG build would require its own creep,
joint, and stability qualification.
