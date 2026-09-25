# System print pack v1 — start with the left saddle

Prepared 2026-09-16. This is a prototype print queue, not certification for
overhead use, unattended operation, or robot motion. All original files remain
unchanged. The revised USB camera cover is separate and is provisionally
accepted by the user; its physical check remains open.

## Next print

**Saddle correction:** use GROUNDED_v2 for both S1 saddles. The old WELDED_v1
saddles had unsupported diagonal brace starts and intrusion into the upright
pocket. They are superseded, not approved support-free prints. See the
[correction report](SADDLE_REVISION_NOTES/PRINT_THIS_REVISION.md).

Open [left bench saddle](PRINT_ABS_frame/08A-S1_ABS_left_bench_saddle_GROUNDED_v2.3mf).
Expected: **one object**, at 100% scale, in the stored orientation. These 3MFs
contain geometry, not embedded printer/filament/process presets or G-code.
Import the process JSON through the slicer's preset/config import, not as a
model; alternatively enter the settings manually.

ABS process: `RoCell ABS Rapido Camera Frame Structural 0.20 Print Pack v1`.

- Printer: QIDI Plus 4 / X-Plus 4 with 0.4 mm nozzle.
- Filament: previously used QIDI ABS Rapido preset; retain its temperatures/cooling.
- Layer height: 0.20 mm; first layer: 0.20 mm.
- Walls: 6. Top layers: 7. Bottom layers: 7.
- Infill: 40% gyroid. Internal solid infill: rectilinear.
- Wall order: inner wall / outer wall / infill. Wall generator: Classic.
- Supports: off. Fuzzy skin: off. Ironing: off. Print sequence: by layer.
- Brim: outer only, 10 mm; brim gap: 0.05 mm. Skirt loops: 0.
- Speeds, mm/s: first layer 25; first-layer infill 40; outer wall 45;
  inner wall 90; sparse infill 95; internal solid 80; top 40; bridge 25;
  gap infill 55; travel 400.
- XY contour/hole compensation: 0; elephant-foot compensation: 0.15 mm.

The complete process files are in `profiles/`. The pack copies normalize the
obsolete wall-sequence key and the internal-solid infill enum; original
profiles and any installed user settings have NOT been overwritten.

Before each print, slice and inspect QIDI's preview: correct object count,
first-layer contact, open bolt passages, bridge paths, no floating islands or
out-of-bed brims. Native QIDI slicing has not been verified by this preparation.
Do not print through a mesh/geometry warning or change global scale to fix fit.

## Queue

Print each plate once. T1 and T2 intentionally contain identical upright
modules: both are needed, for four modules per side. Alphabetical file order
is not the assembly order.

1. **08A-S1** — left saddle (1 object).
2. **08A-S2** — left cap, two splice collars, two M6 retainers (5 objects).
3. **00G-P1 board pads ONLY** — four TPU board pads; separate material/profile.
4. Bench-fit the complete left clamp to the board before duplicating it. Finish
   M6 nut seating, retainer and full nylon-engagement checks with the existing
   coupon/first clamp. Partial bolt insertion alone was not a complete check.
5. **08A-T1, 08A-T2** — two uprights each; **08A-J1** — two left corner plates.
6. **08B-S1, 08B-S2**, then **08B-T1, 08B-T2, 08B-J1** — right support.
7. **08C-X1, 08C-X2** — crossbar; **08C-J1** — collars;
   **08C-B1, 08C-B2** — boom modules; **08C-J2** — root straps.

The earlier successful production splice from 00G supplies the remaining
left-upright collar. The extra 00G fit coupons and sacrificial nut retainer
are not production hardware. Use fresh final retainers and locking nuts.

**HOLD:** `08C-C1` camera carriage is repaired but isolated in its HOLD folder.
Do not print it until back-exiting USB plug/cable clearance is revised. The old
camera compression pad is deliberately omitted from the TPU plate and fallback
STLs. Reuse the camera spacers the user reports working; do not assume they
qualify the changed keeper or complete overhead assembly.

## Existing socket-head M5 bolts

There is no demonstrated need to replace all the M5 bolts just for head style.
The checked alternative is **M5-0.8 socket-cap bolt + one flat METAL washer
under the head**, retaining the specified flanged locking nut. Do not treat a
bare small socket head pressing on ABS as equivalent to the original flange.

- Washer: M5, approximately 5.3 mm ID, 10 mm OD, nominal 1 mm thick;
  the geometry/length check allows up to 1.2 mm thickness.
- 48 washers for all final M5 heads: 44 on the frame, 4 at the held carriage.
- Standard M5 DIN 912 / ISO 4762 head checked: 8.5 mm diameter, 5 mm high,
  driven with a 4 mm hex key. Use a suitable driver on the flanged nuts.
- Keep the original length allocation: 32 x 75 mm, 4 x 80 mm, 4 x 85 mm,
  8 x 90 mm. A different head does not authorize arbitrary length swaps.
- Nominal stack checks assume flanged nut total height no more than 6 mm.
  Confirm each actual bolt passes fully through the nylon and leaves at least
  two full threads visible. The tightest nominal projection is 1.8 mm at the
  portal corners, so actual nut/washer thickness matters there.
- If your nuts are ordinary non-flanged nuts, this option is NOT yet checked:
  another washer changes the stack. Do not silently omit load-spreading hardware.
- Hand-tighten only, stop if ABS dishes or cracks; no torque/strength rating is
  established. Received bolt grades, actual dimensions and proof/creep behavior
  are not qualified by this CAD check.

The report `M5_SOCKET_HEAD_CHECK.json` includes 32 local bearing-seat/head/tool
checks plus six nominal stack calculations. All passed the stated geometric
conditions. It does not claim equivalence in clamp pressure to a 12 mm flange,
nor a structural capacity rating.

Dimension references: [Bossard M5 socket-cap catalog](https://bossard-embedded.partcommunity.com/3d-cad-models/bn-612-hex-socket-head-cap-screws-fully-threaded-din-912-iso-4762-stainless-steel-a4-bossard-catalog?info=bossard%2F01%2F01_100%2F01_100_100%2F01_100_100_10%2Fbn_610_612_31101%2Fbn_612.prj),
[Accu M5 flat-washer dimensions](https://www.accu.co.uk/metric-flat-washers/404043-HPW-M5-V1-A4-BL).
Process enum reference: [QIDI PrintConfig source](https://github.com/QIDITECH/QIDIStudio/blob/main/src/libslic3r/PrintConfig.cpp).

## What was actually verified

17 prepared plates: 16 ABS frame plates and one four-pad TPU plate. One more
carriage plate is repaired but held. Both S1 saddles now use GROUNDED_v2 geometry,
with added brace feet and a cleared upright pocket, and have additional layer
start checks. Other plates received exact-coordinate topology repair only;
their geometry has not changed. Files were reopened and checked for closed manifold meshes,
positive volume, expected object counts, unprefixed 3MF geometry tags and
295 x 295 x 275 mm protected build bounds. Each file has a hash and report.

Mesh checks do not replace native toolpath inspection, print adhesion/bridge
checks, physical assembly checks, load/creep testing, a suitable independent
metal tether, or robot collision checks. Starting prototype printing is distinct
from approval to suspend the camera or operate the robot.
