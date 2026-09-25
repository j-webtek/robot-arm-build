# Phase 1 — configuration-freeze decisions

**Record date:** 2026-09-01  
**Engineering baseline:** `RC03-INT-R1`  
**Candidate customer revision:** `RC03-CUST-R0`  
**Machine-readable record:** `config/v1_prehardware_configuration.json`

This freezes a provisional V1 purchasing and physical-test target. It does **not** release a product, authorize production printing, or prove physical compatibility. The states used here are `CANDIDATE`, `CANDIDATE_SELECTED`, `OUT_OF_V1`, `OPEN`, and `PHYSICAL_QUALIFICATION_REQUIRED`. `CANDIDATE_SELECTED` records an intended V1 route, not a qualified one. No item is `PASS` or customer-released.

## Frozen pre-hardware boundary

| Decision | Provisional V1 value | Decision state | Evidence still required |
|---|---|---|---|
| Product | RoCell RC03 Self-Print Hybrid Kit for QIDI Plus4 | `CANDIDATE` | Complete engineering build, first-customer build, beta, and release gates. |
| Printer | QIDI Plus4; nominal 305 x 305 x 280 mm | `CANDIDATE` | Measure the reference machine and prove every released plate. |
| Protected print envelope | 295 x 295 x 275 mm | `CANDIDATE` | Prove X/Y/Z clearance to the real machine, plate, purge zone, enclosure, and carriage. |
| Primary rigid print material | QIDI ABS Rapido using the exact X-Plus 4 0.4 mm filament preset and five job-family processes | `CANDIDATE_SELECTED` | Physically qualify jobs 00A/00B/00C/00E/00F, first articles, warp/flatness, hardware fits, and the final same-lot production plates; never release from preset data alone. |
| Retained specialist materials | PETG for 00D/04B/04C split adapters; TPU 95A for 05A-05D contact tips; PETG/ASA only for the inactive fixed-camera fallback | `OPEN` | Select exact PETG and TPU products/lots and qualify their vendor presets; select ASA only after formal fallback release. |
| Board blank | 610 x 457 x 18 mm; birch plywood candidate; hand drilled | `CANDIDATE` | Freeze supplier/material range, dimensional limits, finish, anchors, fasteners, reinforcement, feet, and anti-shift system. |
| Keyboard | Perixx PERIBOARD-409; candidate variant PERIBOARD-409 U, USB-A, English US, black; nominal 315 x 147 x 21 mm | `CANDIDATE` | Buy and identify the exact unit; measure its body, feet, key field, cable exit, and connector. |
| Phone | Bare Samsung Galaxy A16 5G; candidate regional variant SM-A166B; nominal body 164.4 x 77.9 x 7.9 mm | `CANDIDATE` | Confirm regional model and measure body, buttons, camera bump, glass edge, port, and orientation. Cases are excluded. |
| Phone cable | StarTech `R2CCR-1M-USB-CABLE`, right-angle USB-C to straight USB-C, 1 m | `CANDIDATE` | Prove connector direction/projection, host and power compatibility, relaxed service loop, and zero lateral port load. No bend radius is published. |
| Primary camera architecture | Arm-mounted camera per the user's intended specification; exact specification is not present in the current RC03 package | `OPEN` | Control the exact camera/link/frame/mount, mass/COM, cable route, eye-in-hand calibration, pose-dependent FOV, timing, payload, reach, and collision evidence before geometry or instructions are released. |
| Fixed-camera fallback | Logitech C920e, US P/N `960-001401`, on two 700 mm 2020 posts plus one 650 mm crossbar | `CANDIDATE` | Retained only as the selected but unqualified fallback route; measure and qualify the camera, mast, retention, FOV, stability, and fixed eye-to-hand workflow. |
| Tool spring | Lee Spring `LP022J01S316` / `LP 022J 01 S316` | `CANDIDATE` | Measure the received lot and prove force, preload, 1–6 mm travel, return, rub, creep, and no coil bind. |
| V1 contact route | 6 mm keyboard rod + printed bushing + replaceable TPU tip in shared compliant body | `CANDIDATE` | Qualify rod, retention, TPU pull-off/creep, spring force, keyboard function, and TCP repeatability. |
| Phone stylus route | Passive capacitive stylus in a printed collar and shared compliant body | `CANDIDATE_SELECTED` | Select an exact stylus, then qualify jobs 00D/04B, retention, pull/cycle/removal/creep, contact force, touch reliability, and TCP repeatability. |

Every `CANDIDATE` or `CANDIDATE_SELECTED` route row also carries `PHYSICAL_QUALIFICATION_REQUIRED` in the machine-readable record.

## Explicitly open before release

1. Exact board stock, finish, locator pins, all nine anchor/fastener stacks, reinforcement plate, feet, and anti-shift system.
2. Exact enclosed low-voltage E-stop/power-cutoff assembly and restart behavior.
3. Physical qualification of the selected QIDI ABS Rapido lot/processes; exact PETG and TPU products/lots and presets; fallback ASA only if released; exact pads, adhesives, tags, and epoxy.
4. Supported Windows, QIDI Studio, RoArm hardware/controller/firmware, homing, empty-cell, and final-process versions.
5. Intended operations, motion/contact limits, duty cycle, service life, maintenance intervals, and unsupported uses.
6. Phone cable host/power source and final strain relief.
7. Exact passive stylus manufacturer/model for the selected phone-stylus route.
8. Exact arm-mounted camera specification and the controlled mount, payload/collision, cable, vision, and eye-in-hand calibration architecture.

## Route-control consequence

`config/measurement_record.json` keeps `phone_stylus_route` and `keyboard_rod_route` set to `true`; those booleans activate route-dependent work only and do not satisfy a measurement, lifecycle, physical-qualification, or release gate. `camera_mast_optional` remains `false`, so PETG job 03C3 and ASA jobs 06/07 stay inactive fallback assets. Print job 00D remains route-dependent on `phone_stylus_route` and is active only because that route is selected.

## Evidence basis

Local controlled inputs are `config/parameters.json`, `config/workcell_layout.json`, `config/print_jobs.json`, and `BOM.csv`. Candidate vendor evidence is recorded with exact URLs in `config/v1_prehardware_configuration.json`, including official QIDI, Perixx, Samsung, StarTech, Logitech, and Lee Spring sources. Vendor dimensions constrain purchasing; only received-part measurement and controlled physical tests can qualify the configuration.
