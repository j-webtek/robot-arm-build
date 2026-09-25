# Final cage/keeper plate with 1.0 and 1.1 mm shim options

Open `08D-C1_ABS_camera_cage_keeper_SHIMS_1p0_1p1_v1.3mf`.
This replaces the original 08D-C1 for this build, not the already printed 00G-C1.

- Six objects: unchanged camera cage and keeper, two 1.0 mm shims, two 1.1 mm shims.
- Use the camera precision process and ABS Rapido; retain scale and placement.
- Label tabs are detachable. Only the flat 38 x 7 mm strip goes in the side gap.
- These are alternative sizes, not a requirement to install all four.
- No extra coupon print. Final fit is selected during bench assembly.
- Nominal thicknesses are subject to layer-height quantization. Check that
  slicing preserves distinct shim thicknesses; do not infer exact printed
  thickness from the labels alone.
- Mesh and placement checks passed. Native QIDI preview and final camera
  retention remain unverified. This is not overhead load approval.

The original plate remains intact. The adjacent sidecar and validation report
describe this six-object revision; the old master manifest does not.

Regenerate using `cad/build_final_camera_shims.py` from the camera project.
