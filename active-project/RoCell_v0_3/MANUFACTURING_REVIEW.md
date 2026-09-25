# RoCell RC03 manufacturing review

**Revision:** `RC03-INT-R1`

## Outcome

The printer-only integrated architecture fits digitally inside the QIDI Plus4 provisional 295 x 295 x 275 mm envelope. The actual printer must pass the protected-envelope gate before production printing. The 610 x 457 x 18 mm structural board remains a purchased/hand-drilled component; no router or CNC is required.

The design reduces the board-aligned assembly to three stations, four locator pins, and nine M4 retention screws. Six tag frames and their twelve board screws are eliminated. The right keyboard station is seam-located from the left master, preventing an overconstrained pin/seam loop.

Digital CAD/package PASS is necessary but not a physical release. Device fits, hardware choices, print shrink, board flatness, station repeatability, direct-tag metrology, and robot safety remain objective build gates.

## Controlled material architecture

QIDI ABS Rapido is the primary rigid material for the 13 active jobs: 00A, 00B, 00C, 00E, 00F, 01, 02, 03A, 03B, 03C1, 03C2, 03D, and 04A. These jobs use one confirmed X-Plus 4 filament preset and five function-specific processes; a successful tray coupon does not qualify the cradle, precision, general, or calibration process.

PETG is deliberately retained for the thin split adapters in 00D, 04B, and 04C because their small ligaments benefit from ductility. TPU 95A remains the required contact material for 05A-05D. PETG job 03C3 and ASA jobs 06/07 remain inactive fixed-camera fallback assets. Exact PETG, TPU, and ASA thermal values are not released until the physical spool and calibrated vendor preset are recorded.

The QIDI ABS Rapido filament contract is 250 °C on the first layer, 260 °C thereafter, 90 °C textured bed, 55 °C chamber, 0.95 flow ratio, 0.03 pressure advance, and 24.5 mm³/s maximum volumetric speed. The enclosure stays sealed. Every job still uses its own exact process file, adhesion controls, coupons, and layer-preview acceptance; never compensate for ABS shrink by globally scaling an STL.

## Incorporated improvements

- Open-datum keyboard stations integrate device datums, clamp guides, direct-board base contact, and board registration; each rear-clamp screw is also the third station retainer.
- The phone/TCP station integrates the fixed phone nest, keyed TCP receiver, direct-board base contact, and board registration; the replaceable rail carries the cable-tie saddle.
- The phone keeper/tower rail remains replaceable because its insert bores and clamp towers are service-risk features.
- The TCP datum is a keyed replaceable cartridge; two are printed so one accepted spare can be measured and labeled.
- Profile-specific round/slot locator coupons prevent transferring fit assumptions between large-station profiles.
- The two keyboard rear-clamp screws pass through their sliders and stations into qualified board anchors, so the sliders remain serviceable without captive nuts or heat-set inserts in thin keyboard platforms. The phone rail's redesigned 7.2 mm lower-half hex seats and 5.6 x 2.2 mm tie saddle are qualified on the production-equivalent Job 03C1 rail; the failed Job 00B features remain historical screening evidence.
- Direct full-surface matte adhesive tags share the finished board plane and eliminate frame tolerance, fastener occlusion, and frame yaw/translation.
- Named board features generate coordinates, drawings, maps, manual blocks, and validation checks.
- Per-job QIDI Studio evidence is required; a global PASS cannot release an unvalidated plate.
- Factory arm hardware remains the load-bearing interface, with a measured metal underside reinforcement plate.

## Module review

### Keyboard station pair

The left/master station uses one round locator, one radial slot, and three hold-downs. The right/slave station is located by the master seam and uses three relieved hold-downs. This is mechanically determinate and allows normal print/board tolerance without binding.

Principal risk: ABS warp over the large footprints. Controls are symmetric/open geometry, one part per plate, the exact 8 mm outer brim and 0.05 mm gap, sealed 55 °C chamber, full cooling before inspection, continuous-base contact checks at the three retention zones, first-article sequencing, and numeric plane/rocking gates.

### Phone/TCP service station

The combined station preserves a single board registration for phone and TCP calibration while keeping the highest-risk rail and datum cartridge replaceable.

Principal risks: unmeasured case/button/camera geometry, ABS warp or stress cracking around captive-nut and insert features, cable bend interference, and receiver-seat distortion. Controls are actual-device checks, the retained Job 00B phone/locator/M3/washer results, Job 03C1 production-equivalent nut/tie qualification, explicit keepouts, continuous-base contact, and ten-cycle device/cartridge tests.

### Direct AprilTags

T0-T3 remain the primary world tags. K0/P0 are residual checks. All six centers are preserved, but their Z becomes the measured compressed adhesive-plus-stock thickness above the finished sealed board.

Principal risks: paper curl, bubbles, gloss, placement error, and coordinate-map drift. Controls are full-surface matte adhesive stock, reusable application frame, 1:1 scale-verified template, installed XY/yaw/Z metrology, 20/20 detection testing, and a layout revision/hash in derived artifacts.

### Board and arm

The board can be purchased cut to size, equally sealed, templated, and hand drilled. Locator bores are blind; threaded interfaces are selected on a scrap-board stack. The factory arm clamp remains primary and loads are spread with metal underneath.

Principal risks: board bow/moisture, uncontrolled drilling depth, tee-nut variation, screw bottoming, and clamp crushing. Controls are local/overall flatness limits, scale bars, brad-point bit/depth stop, dry fit before epoxy, measured thread engagement, proof loading, low torque, and post-humidity checks.

## Required physical acceptance

| Characteristic | Limit |
|---|---:|
| Board local flatness | <= 0.50 mm over any 300 mm station region |
| Overall board bow | <= 1.5 mm |
| Station free-state corner lift | <= 0.75 mm |
| Keyboard support-plane flatness | <= 0.40 mm |
| Phone support-plane flatness | <= 0.30 mm |
| TCP receiver-seat flatness | <= 0.15 mm |
| Keyboard seam gap / flush mismatch | <= 0.40 / 0.25 mm |
| Station reinstall X/Y / yaw / Z range | <= 0.25 mm / 0.20 deg / 0.20 mm over 10 cycles |
| Keyboard device pose range | <= 0.50 mm over 10 cycles |
| Phone device pose range | <= 0.35 mm over 10 cycles |
| TCP cartridge play / height range | <= 0.15 / 0.10 mm over 10 cycles |
| Tag tile / detection edge | 55.0 +/- 0.2 / 40.0 +/- 0.2 mm |
| Tag center / yaw / edge lift | <= 0.50 mm / 0.30 deg / 0.20 mm |
| Vision | 20/20 detections each; <= 1.0 px reprojection error |
| Structural proof | 20 N lateral station and 10 N functional load; <= 0.10 mm permanent shift |

## Release status

The RC03 package can be released for **controlled QIDI ABS Rapido coupon printing and digital review** after automated validation passes. Full station printing remains blocked until the matching ABS diagnostic and first-article gates pass. Retained PETG and TPU jobs additionally require their exact spool presets; inactive fallback PETG/ASA jobs remain blocked by the camera-architecture release. Robot operation remains blocked until station, device, tag, camera, tool, and empty-cell safety acceptance is complete.
