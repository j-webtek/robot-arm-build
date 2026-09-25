# Hardware arrival and qualification plan

This plan converts named candidates into measured engineering evidence. It does not authorize bulk purchasing or customer release.

## 1. Purchase and quarantine

1. Buy one or two reference units/lots only, under an approved engineering purchase record.
2. On receipt, keep each item quarantined and assign a traceable receipt ID. Photograph packaging, label, model/part number, revision/lot code, quantity, and visible condition.
3. Record the measuring tools and calibration status. Do not substitute a visually similar SKU or regional variant.
4. Compare the received identity with `config/v1_prehardware_configuration.json`. A mismatch is a stop condition and issue-register update.
5. Store raw measurements and photos under the active build ID. Enter accepted evidence only through the canonical recording workflow.

The phone-stylus route is selected for V1 evaluation but its exact stylus remains open. Select and record one exact passive stylus before purchasing a reference unit or printing route-dependent job 00D/04B parts; no stylus item or print is qualified yet.

## 2. Qualification order

Use this dependency order so late discoveries do not invalidate downstream work:

1. **Reference QIDI Plus4:** identify serial/nozzle/build surface; measure X/Y/Z exclusions; prove the provisional 295 x 295 x 275 mm protected envelope.
2. **Board blanks:** identify material/lot; measure length, width, thickness, flatness, and squareness; condition and finish representative samples before anchor tests.
3. **Exact hardware system:** qualify pins, inserts, nuts, screws, washers, anchors, reinforcement plate, feet, anti-shift components, and the enclosed power-cutoff assembly on matching scrap and a representative board.
4. **Keyboard and phone:** identify exact variants; measure full envelopes and every no-go/retention/cable feature; compare the evidence with controlled CAD parameters before production geometry.
5. **Cable:** measure connector bodies, exit direction, OD, projection, and relaxed routing; prove host/power function, service loop, strain relief, repeated docking, and no lateral phone-port load.
6. **Arm-mounted camera architecture:** do not buy, print, or install an adapter from the current RC03 geometry. First identify the exact camera, carrying arm link/frame, mounting interface, mass/center of mass, connector and cable exit. Then control the arm mount, moving-cable strain relief and service loop, eye-in-hand calibration chain, required tag visibility at every task pose, image timing, payload/reach/collision effects, and E-stop consequences. The paired 2020 mast remains a selected but unqualified fixed-camera fallback only; qualify it as a separate eye-to-hand route if it is retained.
7. **Spring and contact tools:** measure spring/rod/tip/stylus/printed interfaces; prove force and travel, no bind/rub, return, retention, pull-off, creep, keyboard actuation and phone touch reliability, cycle durability, and route-specific TCP repeatability.
8. **Materials and print projects:** qualify exact PETG/TPU/ASA lots and QIDI profiles; run selected diagnostics including 00D, first articles, complete plates, reopen/reslice checks, and retained-part inspection.
9. **Integrated system:** complete drill/assembly proof, empty-cell safety run, six-tag vision acceptance, both selected contact routes, final task, duty-cycle/reliability test, maintenance validation, and recovery drills.

## 3. Item-specific minimum evidence

| Candidate | Arrival checks | Qualification decision evidence |
|---|---|---|
| PERIBOARD-409 U | Label, language/layout, USB-A cable, body/feet/key field dimensions | Fixture insertion/removal cycles, retention, datum repeatability, all required key actuations, cable clearance |
| Galaxy A16 5G SM-A166B candidate | Model label, bare body, buttons, glass edge, camera bump, USB-C port | Fixture cycles, clamp proof, no-go clearance, cable route, device function and damage inspection |
| StarTech R2CCR-1M | Exact part number, connector orientation, length, OD, bodies | Host/power operation, bend/service loop, docking cycles, strain relief, no port side-load |
| Logitech C920e 960-001401 | Part number, envelope, mass, cable, tripod thread and usable depth | Safe retention, focus/exposure persistence, calibrated coverage, all six tags in all required poses |
| Intended arm-camera system | Exact camera identity; carrying link/frame; mount interface; fasteners; mass/center of mass; connector and moving cable | Mount fit, full-joint cable sweep and flex life, payload/reach/collision proof, visibility at all task poses, eye-in-hand calibration, focus/exposure/blur/timing, gravity-drop and E-stop behavior |
| Paired 2020 mast fallback | Extrusion dimensions/straightness and all exact M5 hardware | Only if the fixed-camera fallback is intentionally qualified: foot fit, clamp engagement/torque, crossbar level, eye-to-hand calibration, static/dynamic rigidity and 24-hour drift |
| Lee LP022J01S316 | Stock code, OD, ID/work-over-rod, wire, free/solid length | Force curve through 1–6 mm, preload, coil-bind margin, rub, return, creep and contact-force compliance |
| 6 mm rod + TPU tip | Rod diameter/straightness, bushing fit, TPU lot/profile | Retention/pull-off, creep, cycle wear, keyboard function, spring travel and TCP repeatability |
| Exact passive stylus — `OPEN` | Select and record manufacturer/model, diameter profile, tip construction, length, mass, and finish | Job 00D gauge, job 04B collar, retention/pull/cycle/removal/creep, safe contact force, touch reliability and TCP repeatability |

## 4. Decision and failure handling

- A vendor datasheet or nominal match leaves the item `PHYSICAL_QUALIFICATION_REQUIRED`.
- If a candidate fails, quarantine it, add/update the issue register, record the failure evidence, and return to the owning configuration decision. Do not edit measurements to fit CAD.
- If a dimension changes geometry, update controlled parameters, regenerate all dependent artifacts, and rerun affected digital and physical checks before resuming.
- Only the canonical measurement, lifecycle, first-customer, beta, and release workflows can authorize downstream use. This provisional configuration always remains a planning/procurement record.
