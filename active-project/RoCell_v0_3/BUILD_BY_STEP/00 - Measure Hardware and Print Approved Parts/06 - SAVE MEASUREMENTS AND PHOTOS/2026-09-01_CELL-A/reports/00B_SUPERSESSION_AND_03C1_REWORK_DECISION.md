# Job 00B supersession and Job 03C1 rework decision

Date: 2026-09-06  
Operator: Jack  
Design revision: RC03-INT-R1  
Material/process: QIDI ABS Rapido / `abs_rapido_cradle_0p4`

## Preserved as-built reference

The physical Job 00B plate remains evidence for the interfaces actually printed. Its recovered geometry-only plate SHA-256 is `c40772e5c1a0536f78ea3f862d3425a727b786ae2e5d8d2199f570a780e92e51`. The original report and photographs are retained unchanged.

Accepted from that physical print under the operator's no-caliper prototype waiver:

- Bare-phone width/rail-height hand fit: `PHONE/FIT79.9`.
- Service-station locator pair: middle rows, `6.2 mm` round socket and `6.2 mm` radial slot.
- M4 washer recess: middle `OD9.2`, washer lies flat.

## Superseded interfaces

The physical `N7.4` captive-nut channel is a functional **FAIL**: the standard M4 nut drops in with excessive clearance and the screw does not engage reliably. The old rectangular loading slot cut through most of the nominal hex seat, so selecting a smaller printed label alone would not correct the seating problem.

The physical cable-saddle screening feature is a functional **FAIL** for the operator-selected wider tie: the tie does not feed through the legacy opening. The operator authorized adopting the wider tie without printing another standalone coupon.

Neither failed 00B feature may be recorded as a PASS or used to release Job 03A.

## Controlled replacement in Job 03C1

Job 03C1 is the production-equivalent first article for both corrections:

- Captive nut: `7.2 mm` lower-half hex seat, `3.35 mm` X-depth for the nominal `3.2 mm` nut, `4.0 mm` screw axis, corner-clear top chute, and a shallow loading lead-in. The lower hex half remains intact to locate the thread and resist rotation.
- Cable tie: project-standard nominal `4.8 mm` wide by no more than `1.5 mm` thick; controlled printed tunnel `5.6 mm` wide by `2.2 mm` high; saddle outer size `10 x 10 x 4 mm`; tunnel length `12 mm`; tunnel floor offset `0.8 mm`.
- Optional camera-plate strap slots also use the controlled `5.6 mm` width.

No replacement nut-only or tie-only coupon is required. The loose Job 03C1 rail must still receive the actual hardware before Job 03A is released:

1. Top-load both standard M4 nuts.
2. Confirm each actual M4 screw catches and advances at least three full turns without lifting the nut.
3. Advance/back out each screw through 20 cycles; reject any nut spin, tower crack, or blocked axis.
4. Feed the nominal 4.8 mm tie around the actual USB cable through the production saddle; confirm free feed, useful cinching range, cable clearance, and no cracking.
5. Save close photos and the Job 03C1 plate/STL SHA-256 values in this build evidence directory.

The full `phone_clamp_rail_first_article_pass` remains pending until the rail can later be seated on the printed Job 03A station and checked with the actual phone.
