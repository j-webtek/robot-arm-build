# Job 00B Print and Fit Review

Build ID: `2026-09-01_CELL-A`  
Printer: QIDI Plus4, 0.4 mm nozzle  
Material/process: QIDI ABS Rapido / `abs_rapido_cradle_0p4`  
Review date: 2026-09-06

## Recorded print result

- The photographed coupons completed without obvious gross warp, cracking, layer separation, or missing bodies.
- The raised labels remain difficult to read in black-on-black photographs; candidate numbers must not be inferred from relief text alone.
- Ten original photographs are retained in `../photos/` and indexed in `../photos/README.md`.

## Phone width and rail-height coupon — physical fit observed, gate pending

The actual phone seats between both rails of the `PHONE / FIT 79.9` coupon. The rail tops appear below the screen face. The operator reports approximately `1–2 mm` of total side-to-side motion and describes the phone as able to slip out easily.

That easy longitudinal removal is expected from this particular coupon: it is a short, open-ended, 36 mm-deep cross-section intended to test width and rail height only. It has no front/rear keepers and no clamp screws. The full station adds fixed front/left datum faces, keeper geometry, and two M4 clamp screws with TPU tips that push the phone against the fixed datum. Therefore these photographs alone do not justify narrowing the production cradle.

Disposition: retain the current production width provisionally; do not claim final retention. Keep `phone_width_coupon_pass` pending until the operator confirms the phone was in its intended final case state, the rails clear the screen/buttons/ports, and the width-only purpose is accepted. Final retention remains a first-article clamp test.

Evidence: `../photos/00B-07_phone_width_coupon_fit_view1.jpg`, `../photos/00B-08_phone_width_coupon_fit_view2.jpg`.

## Cable-tie saddle — non-pass with the selected physical tie

The selected ribbed cable tie does not feed through the tested end saddle from either mouth. No obvious saddle crack is visible. The photographs do not show a USB cable, so cable bend/connector clearance was not tested.

The controlled BOM specifies a nylon tie `2.5–3.2 mm` wide and no more than `1.2 mm` thick. The photographed tie visibly appears wider than that class and is consistent with a common approximately 4.8 mm tie, although no numeric size is claimed from the photograph. The current coupon candidates are `T2.6`, `T3.2`, and `T4.0`, all with a 1.8 mm-high closed tunnel.

Disposition: `cable_tie_saddle_coupon_pass` is not satisfied. Do not force the tie. Either use the specified narrow tie and retest the widest saddle, or explicitly adopt the present wider tie and issue a saddle-only rework coupon before changing production CAD.

Evidence: `../photos/00B-01_cable_tie_saddle_edge_view1.jpg` through `../photos/00B-05_cable_tie_saddle_failed_feed_view2.jpg`.

## M4 washer recess — provisional fit only

One actual washer appears flat in one end recess, and the operator reports that it fits. The coupon orientation and label are not reliable enough to prove whether the photographed end is `OD8.8` or `OD9.6`, nor does one photograph establish the smallest flat-seating candidate.

Disposition: keep `cradle_m4_washer_coupon_pass` pending. Repeat the washer in the visibly smallest, middle, and largest recesses and report the smallest recess in which it drops fully flat by finger pressure and lifts out without prying.

Evidence: `../photos/00B-06_m4_washer_left_candidate_provisional.jpg`.

## M4 captive-nut gauge — printed geometry only

The three towers and horizontal bores appear open and intact. No M4 hex nut is visibly installed and no screw is visibly threaded through a nut in the horizontal axis. The operator's statement that M4 appears to fit supports screw passage only; it does not establish captive-nut installation or retention.

Disposition: keep `phone_m4_captive_nut_coupon_pass` pending. The selected tower still requires finger-only nut installation, horizontal screw alignment, and a 20-cycle no-spin/no-crack test.

Evidence: `../photos/00B-09_m4_nut_gauge_top_side_view.jpg`, `../photos/00B-10_m4_nut_gauge_bottom_side_view.jpg`.

## Unshown tests

No retained Job 00B photograph shows either of the following:

- the actual 6 mm locator pin tested in the phone-profile round socket and radial slot;
- a production M3 heat-set insert installed in the phone-profile insert coupon.

Accordingly, `phone_station_registration_coupon_pass` and `phone_station_m3_insert_coupon_pass` remain pending.

## Current Job 00B disposition

- Print completion and gross coupon condition: **accepted**.
- Phone width/rail-height observation: **physically seats; purpose clarification and final clamp verification pending**.
- Selected physical cable tie: **non-pass in the tested saddle**.
- Washer: **functional fit reported; exact selected candidate pending**.
- M4 captive nut, locator, and M3 insert: **not yet demonstrated**.
- Production Jobs `03A` and `03C1`: **remain on hold**.
- No controlled production geometry or compatibility gate has been changed from this preliminary review.
