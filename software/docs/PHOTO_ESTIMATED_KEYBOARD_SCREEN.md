# Photo-estimated keyboard placement: offline checkpoint

Date: 2026-09-25. Status: simulation only; no new arm command was sent.

The operator's ruler and overview photos show the physical Perixx keyboard on
the printed board layout, with the arm above it. They are useful for selecting
placement *hypotheses* and identifying nearby loose printed parts. Perspective,
occlusion and the moving ruler do not provide a measured six-degree-of-freedom
keyboard registration, tool transform, or clearance certificate. The key
legends appear approximately half-turned relative to the printed front-row
text, so both zero and 180-degree orientations must remain explicit candidates.

The frozen nominal profile places the 315 x 147 mm keyboard at board XY
`[85,85]` mm. A prior translation-only study also used `[85,65]` mm. Neither
is established as the installed physical footprint. The 100 mm stylus offset
used below remains hypothetical until the selected stylus is loaded and
measured using [the loading procedure](STYLUS_LOADING_PROCEDURE.md).

## Screens already run

- Independent nominal 100 mm-tool **hover** targets: 11/46 accepted (`A`,
  `B`, `C`, `D`, `Q`, `S`, `SPACE`, `TAB`, `V`, `X`, `Z`). Hover here means only
  about 12 mm above the synthetic key plane, not clearance for the bare jaw.
- Independent nominal 100 mm-tool **transit** targets: 37/46 accepted. The
  nine missing targets were `0`, `6`, `7`, `8`, `9`, `O`, `P`, `MINUS`, and
  `EQUAL`. This is independent-point IK, not a continuous route or physical
  collision check.
- The no-extension `hand_tcp_only` nominal hover case accepted 0/46. This
  does not prove the real gripper cannot traverse the keyboard; it shows that
  the existing tip-target geometry is not a usable jaw-clearance model.
- At translated origin `[85,65]` mm with nominal 100 mm tool and zero yaw,
  dense routes for `1230`, `qwerty`, and `.,/;'-=` stopped at the approach to
  `1`, `W`, and `PERIOD`, respectively, on the normalized arm-joint-margin
  check. Exports:
  `wizard-20260925T142737624145Z-4d2e2ee692654c87be6d74e61c84bee5`,
  `wizard-20260925T142746043863Z-1333864a0aa64402a34b1a8d77397f6e`,
  `wizard-20260925T142754864048Z-9245196be0ef4d7c9ddca040070c7d06`.
- An explicit simulation-only half-turn overlay was added without changing
  the keyboard footprint or source files. At `[85,65]` mm and 180-degree
  rotation, one-key dense `1` passed; `a` and `.` failed. Exports:
  `wizard-20260925T143307346299Z-4de1c40fcc3a42d0a49f3747fa2e5072`,
  `wizard-20260925T143304121331Z-816f2218e6b5455dbe3d0235c6e1a905`,
  `wizard-20260925T143311890569Z-81753713b70245b8ba13be2fc4f38927`.
The pass is numerical only, and these dense task routes include lower
  approach phases; they are not the proposed high noncontact travel route.

## Reconstructed from the existing ruler and board photographs

The board-frame placement is now an explicit, reproducible **offline photo
estimate**, not merely a guessed translation. The annotated source is the
operator's overhead `10-Photo-10.jpg` (SHA-256
`f78bd8078e8dedb93de8a3ed4705a07f9254401b2c5ceb35372b15d3345c0884`).
Eight printed marks spanning the A1/A2/A3 sheets tie image pixels to known
RC03 board coordinates. A planar homography maps pixels to the board plane;
its maximum fiducial residual is 1.337 mm. Four visible housing corners are
then fitted to the known 315 x 147 mm keyboard footprint. The maximum
corner-fit residual is 6.996 mm, mainly reflecting manual corner selection
and housing height/parallax. Neither residual is a physical accuracy bound.

The fitted *housing footprint* front-left is `[78.70, 77.92]` mm in board XY,
with yaw `+0.302°`. The keyboard's own front-left is at approximately
`[392.92, 226.58]` mm and its local yaw is `180.302°`: the key legends face
the opposite way from board +X/+Y. The previous `[85,85]` nominal origin was
close, but it had the wrong local orientation. Applying this rigid transform
to the 46 nominal local key centers yields hypotheses including `1` at
`[371.50,115.47]`, `A` at `[356.98,157.39]`, `B` at `[271.17,177.94]`,
`PERIOD` at `[194.97,177.54]`, and `SPACE` at `[254.06,198.85]` mm.

The [input annotations](../config/photo_keyboard_registration_20260925.json)
and [estimator](../src/rocell/application/photo_keyboard_registration.py) keep
the calculation repeatable. Run
`python software/scripts/estimate_photo_keyboard_registration.py` from the
repository root for the versioned annotation, optionally passing `--photo`
with the original attachment to verify its bytes. The
`--photo-estimated-keyboard` option in
[the static rehearsal](../scripts/rehearse_static_task.py) feeds these centers
into the existing offline geometry/IK path and inflates the keyboard obstacle
by a **15 mm study margin**. That margin is a conservative scenario choice,
not a statistically calibrated uncertainty interval. The overlay records
`motion_authorized=false`, `keyboard_registered=false`, and
`arm_board_transform_verified=false`.

An offline `b` rehearsal with this placement passed its coarse geometry
checks but reported `SAMPLED_IK_GAPS` (0/5 sampled poses converged) under the
existing *nominal 100 mm tool* and *nominal board-to-arm* assumptions. This
is **not** a conclusion that the physical arm cannot reach `B`: neither the
actual gripper/tool tip nor the installed board-to-controller transform is
known, and the screen is not a whole-arm collision certificate. No motion or
controller command was generated. The photo determines a useful keyboard-to-
board map; it does not close the board-to-arm/TCP mapping needed for precise
typing.

## Next study after tool loading

Replace the 100 mm assumption with the measured tip transform and validate
the now photo-estimated keyboard footprint/yaw against physical measurements.
Establish the installed board-to-arm frame correlation. Build a **travel-only**
route from freshly observed arm state across representative keys in each row,
keeping the loaded stylus and every arm link clear of the keys, board, paper,
cables, ruler, and printed parts. Screen each segment, not just endpoints, and
export failures. The current r91 app only admits its completed fixed A cycle;
no arbitrary photo-derived route can be sent through it.
