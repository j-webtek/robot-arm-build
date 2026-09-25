# Fastener and print user-experience guide

This guide explains the assembly aids built into each printable part. It does
not replace the dimensional gates in `PRINT_READINESS.md`.

## Shared fastener conventions

- M4 board slots use a 9.2 mm shallow washer track sized for a standard M4 flat
  washer. Keep the washer inside the recessed track and tighten only enough to
  prevent movement.
- M5 base holes and camera slots use 11.0 mm shallow washer seats.
- Heat-set insert openings have a short tapered lead-in. The taper is only an
  alignment aid; the selected straight pocket controls retention.
- Start every board fastener loosely, align the part, and tighten in alternating
  steps. Stop if a washer dishes, a slot whitens, or the printed surface creeps.
- Finish printed holes by hand with the coupon-selected drill or reamer. Do not
  use a powered drill on an assembled printed part.

## Part-by-part handling

| Part | Built-in aid | User action |
|---|---|---|
| Keyboard tray left/right | `RC02-L`/`RC02-R` marks, three seam keys, solid-rail closed slots/washer tracks, and four anti-slip pockets | Dry-fit the seam, start all eight screws, square the keyboard, then tighten and install four rail pads |
| Keyboard rear clamps | Root gussets, `KB` mark, recessed adjustment track and 2 mm scale | Add the face pad and washer; use the scale to match both clamps and apply only enough pressure to remove motion |
| Phone cradle | `USB`/`TOP` labels, four closed mounting ears, `HAND` clamp labels, insert lead-ins and raised cable saddle | Check buttons/cable first; use the job-00B tie selection and fingertip clamp force only |
| Phone TPU caps | Flared bore entry, seating witness and rounded contact face | Remove first-layer flash; seat to the witness and perform the actual-hardware pull test |
| Phone width coupon | Production width and rail-height section | Test the actual phone/case without forcing it |
| Keyboard corner coupon | Production corner walls and support plane | Confirm clearance and that the keyboard sits without rocking |
| Seam coupons | Engraved `M`/`F` identification | Mate by hand; reject binding or visible rocking |
| Hardware gauge | Labeled M3/M4/M5 clearance rows | Record the smallest free hole under the exact tray, general, or calibration profile; do not transfer results between them |
| Compact M4 washer gauge | Labeled 8.8/9.2/9.6 mm recesses | Print in jobs 00A, 00B and 00F; use each result only for its tray, cradle or calibration profile |
| Compact M3 head gauge | Labeled 5.8/6.2/6.6 mm recesses | Print in job 00C; select the smallest recess that seats the actual tool-cap screw below flush |
| M3 insert gauge | Full-depth 4.3/4.6/4.9 mm pockets in the precision-tool profile | Record insert OD/length, selected pocket, installed depth and spin resistance |
| Horizontal M4 gauge | Production-axis pockets with matching tapered entrances | Use this result for the phone towers; a vertical or clearance coupon cannot predict horizontal roof sag |
| Setup-hardware gauge | M3 head, M4/M5 washer and camera-hex ladders | Record each selected seat for general-profile parts only and feed it back to the matching CAD parameter |
| Thread-pilot gauge | Horizontal M2/M3 pilot ladders | Select a pilot only; release the final thin adapter with its own pull/cycle test |
| Cable-saddle gauge | 2.6/3.2/4.0 mm tie tunnels | Feed the actual tie and cable; reject cracking or inadequate bend clearance |
| M5 nut gauge | Production-axis nut traps, clearances and washer seats | Select the smallest non-splitting trap and freely passing bore using the final ASA lot |
| Mast socket gauge | Three labeled 2020 sockets with 20 mm engagement | Test the exact extrusion cut from the final stock |
| TPU retention gauge | Labeled M4 and 6 mm pegs | Require firm hand installation and a pull-off pass |
| Tag frames ID0-ID5 | Unique ID/+Y marks, isolated M4 washer tracks, 55.4 mm paper recess and thumbnail scoop | Match physical tag to frame ID; install at 100%; confirm orientation and unobstructed matte faces |
| Calibration puck | Recessed washer tracks and protected center divot | Tighten gradually and verify the puck remains flat |
| Camera plate | `CAM`/`MAST` labels and recessed M5 tracks | Confirm camera screw length before tightening into the camera body |
| Mast feet | Four M5 washer seats, paired clamp bolts, slit and ribs | Print one first; alternate clamp-bolt tightening and recheck after 24 hours |
| Compliant tool body | Tapered M3 insert entries and dedicated gripper flats | Install inserts squarely; keep seams and jaw contact off the flats |
| Tool top cap | `UP` mark, asymmetric locator and recessed M3 screw heads | Confirm it seats only in the keyed orientation; tighten alternately until seated and bag the spare |
| Gripper coupon | Engraved `G` and full 28 mm production gripping faces | Establish minimum non-slip gripper force before printing the full body |
| Spring gauge | `SPR` mark with both 15.2 and 14.2 mm production seats | Spring must pass over the post and inside both stepped cups without scraping |
| Stylus collar | Split ring and parameterized radial M2 pilot | Use a selected M2 screw only after thin-wall pull/cycle testing; otherwise use measured interference or minimal removable adhesive |
| Rod bushing | Tapered flange transition and split shaft | Deburr the rod; do not spread the slit with a screwdriver |
| Keyboard TPU tips | Flared bore entry, 8.5 mm seating witness and rounded contact | Seat to the witness, pull-test on the actual rod, and replace when polished, split, or loose |
| Stylus gauge | Engraved diameter ladder | Measure only after cooling and select a freely sliding hole |

## Installation sequence that minimizes rework

1. Qualify the exact spools/profiles, then print and record jobs 00A through 00F.
2. Finish holes and remove brim/first-layer flash before installing hardware.
3. Insert every fastener by hand for at least two full turns.
4. Dry-assemble without devices, springs, or robot motion.
5. Load the keyboard and phone, then tighten from the fixed datum outward.
6. Mark each inspected fastener with a removable paint pen if desired.
7. Recheck PETG fasteners after 24 hours and periodically during early use.
