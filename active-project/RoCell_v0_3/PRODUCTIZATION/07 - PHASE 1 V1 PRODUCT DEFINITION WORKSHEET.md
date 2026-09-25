# Phase 1 — V1 product definition worksheet

> **Superseded as the active decision record on 2026-09-01.** Retain this worksheet as planning history and an unresolved-field checklist. Use `07 - PHASE 1 CONFIGURATION FREEZE DECISIONS.md` and `config/v1_prehardware_configuration.json` for the current provisional V1 boundary. Their candidates still require physical qualification.

This is the first execution worksheet. It is an engineering record, not a customer-facing specification yet.

Use these statuses:

- `CANDIDATE` — already represented in the current design but still needs physical confirmation;
- `CANDIDATE_SELECTED` — included in intended V1 scope and selected as a route, but still unqualified and unreleased;
- `SELECTED` — exact choice recorded and purchased/available;
- `QUALIFIED` — physical evidence meets the released test;
- `OPEN` — decision still required;
- `OUT OF V1` — intentionally excluded from the first product;
- `PLANNED` — implementation is assigned to a later roadmap phase after the configuration choice is frozen.

Do not mark an item `QUALIFIED` from a nominal dimension or a digital model alone.

## 1. Product contract

| Field | Proposed V1 value | Status | Required evidence/decision |
|---|---|---|---|
| Product name | RoCell RC03 Self-Print Hybrid Kit for QIDI Plus4 | CANDIDATE | Confirm customer-facing name. |
| Consumer revision | `RC03-CUST-R0` during development | CANDIDATE | Assign after change-control record is created. |
| Product format | Customer prints plastic parts; seller supplies labeled hardware/safety/tag/reinforcement pack | CANDIDATE | Confirm supplied/customer-owned classification for every BOM row. |
| Intended customer | QIDI Plus4 owner with ordinary maker and hand-tool experience | CANDIDATE | Confirm no advertised action requires advanced metrology or programming. |
| Board fabrication | Hand drill with released guides and depth control; no router/CNC | SELECTED | Qualify final guide/process and board tolerances. |
| Intended use | Automated interaction with the released keyboard and phone using a released RoArm program and compliant tool | OPEN | Write exact operations, duty cycle, environment, and excluded uses. |
| Intended duty/life | Not defined | OPEN | Define cycles per session/day, expected service life, maintenance interval, and reliability-test multiplier. |
| Product boundary | Fixture, printed parts, hardware/safety pack, software, and instructions; robot/printer/devices/customer board supplied separately unless reclassified | CANDIDATE | Confirm what is sold, owned, printed, and excluded. |

## 2. Core platform

| Component | Current candidate | Status | Decision required before SELECTED/QUALIFIED |
|---|---|---|---|
| Printer | QIDI Plus4 | SELECTED | Record serial for the reference unit. |
| Nozzle | Installed 0.4 mm | CANDIDATE | Physically verify and record method. |
| Candidate print envelope | 295 x 295 x 275 mm protected envelope within the nominal 305 x 305 x 280 mm volume | CANDIDATE | Physically establish X/Y/Z clearances to carriage, enclosure, purge area, and plate exclusions. |
| QIDI Studio | Exact version not frozen | OPEN | Select one supported release; validate every native project. |
| Build surface | Not frozen | OPEN | Select exact plate/surface and cleaning method. |
| Supported computer OS | Windows recommended for V1 | CANDIDATE | Select exact supported Windows version and clean-machine test. |
| Robot | Waveshare RoArm-M3 Pro | CANDIDATE | Record exact hardware/clamp revision, controller, and firmware. |
| Factory clamp | Existing rear-edge factory clamp | CANDIDATE | Measure footprint; release installation method and setting. |

## 3. Supported devices

| Component | Current candidate | Status | Decision required before SELECTED/QUALIFIED |
|---|---|---|---|
| Keyboard | Perixx PERIBOARD-409 U, USB-A, English US, black; nominal 315 x 147 x 21 mm | CANDIDATE | Confirm the received label/revision and measure the physical reference unit. |
| Phone | Bare Samsung Galaxy A16 5G, candidate SM-A166B; nominal body 164.4 x 77.9 x 7.9 mm | CANDIDATE | Confirm the exact regional model and measure all no-go features. |
| Phone case | No case in the V1 candidate | OUT OF V1 | Any later case requires a separate compatibility configuration. |
| Phone USB cable | StarTech R2CCR-1M-USB-CABLE, right-angle USB-C to straight USB-C, 1 m | CANDIDATE | Prove host/power compatibility, connector direction/projection, relaxed service loop, strain relief, and no port side-load; no bend radius is published. |
| Camera | Logitech C920e, US P/N 960-001401 | CANDIDATE | Measure the received camera and blind thread; prove retention, coverage, lighting, and focus/exposure persistence. |
| Camera support | Paired 700 mm 2020 posts with 650 mm crossbar | CANDIDATE_SELECTED | Qualify feet, M5 stacks, lens height, rigidity, disturbance recovery, and drift. |

## 4. Board and structural system

| Component | Current candidate | Status | Decision required before SELECTED/QUALIFIED |
|---|---|---|---|
| Board | 610 x 457 x 18 mm birch plywood preferred | CANDIDATE | Select exact material/supplier range, tolerances, conditioning, and finish. |
| Board finish | Matte finish, both faces equally | OPEN | Select exact product, preparation, coat schedule, cure, cleaner, and compatibility. |
| Locator pins | 6 x 20 mm, four installed plus two spares | CANDIDATE | Select exact SKU/material/tolerance and qualify in matching bores. |
| Board anchors | M4 tee nut or threaded insert candidates | OPEN | Select one exact SKU and qualify all nine locations in 18 mm board. |
| Station screws | M4 x 20 or M4 x 25 candidates | OPEN | Select exact length/head/washer for each of nine rows. |
| Reinforcement plate | Minimum 3 mm aluminum or 2 mm steel concept | OPEN | Release exact material, dimensions, finish, edge treatment, and board location. |
| Feet | Six generic rubber feet | OPEN | Select exact SKU, placement, and attachment. |
| Anti-shift | Not released | OPEN | Select method and proof. |
| E-stop/power cutoff | Generic latching cutoff rated for arm supply | OPEN | Prefer a seller-supplied enclosed/prewired/plug-compatible assembly; select exact voltage domain, connectors/polarity, model, rating, placement, reset, and restart behavior. Customer mains work is outside V1. |

## 5. Print materials and process

| Component/profile | Current state | Status | Decision required before SELECTED/QUALIFIED |
|---|---|---|---|
| PETG | Type only; brand/SKU/color not fixed | OPEN | Select primary material, drying, profile, and supported substitute policy. |
| TPU | Type only; brand/SKU/color/hardness not fixed | OPEN | Select exact hardness/SKU, drying, profile, and tip acceptance. |
| ASA | Selected mast route only; exact SKU/profile remains open | OPEN | Select and qualify the exact ASA lot and mast profile. |
| Build plate profiles | Multiple internal profiles | OPEN | Qualify internally and reduce customer profiles where evidence permits. |
| Customer verification plate | Not created | PLANNED | Design in Phase 3 after released profile/interface decisions. |
| Customer native QIDI projects | Engineering sidecars/3MFs exist; customer release not qualified | PLANNED | Create, reopen, reslice, physically print, and accept every pack in Phase 3. |

## 6. Phone/TCP and contact hardware

| Component | Current candidate | Status | Decision required before SELECTED/QUALIFIED |
|---|---|---|---|
| Keyboard pads | EVA or TPU, 42 x 10 x 0.8-1.0 mm | OPEN | Select exact material/SKU/adhesive/compression/replacement limit. |
| Phone clamp nuts | Standard M4 measured nuts | OPEN | Select exact SKU and accepted printed channel. |
| Phone clamp screws | M4 x 25 thumb or nylon screws | OPEN | Select exact SKU and accepted soft-tip interface. |
| TCP inserts | M3 heat-set, nominal 4.5-4.7 OD x 5-6 mm | OPEN | Select exact insert SKU and install method. |
| TCP screws | M3 x 10 button head | CANDIDATE | Select exact SKU and torque/engagement. |
| Tool spring | Lee Spring LP022J01S316 / LP 022J 01 S316 | CANDIDATE | Measure the received lot and qualify preload, rate, travel, force, rub, return, creep, and coil-bind margin. |
| V1 tool routes | 6 mm keyboard rod + TPU tip and passive phone stylus + printed collar | CANDIDATE_SELECTED | Both routes are in intended scope; select the exact passive stylus and physically qualify both routes independently. |
| Tool retention | Dry fit or qualified removable compound | OPEN | Select exact released method and creep/pull limits. |

## 7. Vision and software

| Component | Current candidate | Status | Decision required before SELECTED/QUALIFIED |
|---|---|---|---|
| AprilTags | Six IDs 0-5 plus spare set; 55 mm tile/40 mm detection edge | CANDIDATE | Select exact stock, printer/source, matte adhesive, thickness, cleaner, and dwell. |
| ChArUco target | Current controlled target | CANDIDATE | Validate physical scale and customer print method. |
| Vision dependencies | `numpy>=2.0`, `opencv-contrib-python>=4.10` | OPEN | Pin exact supported versions and produce one installer. |
| Setup flow | Manual Python/CLI workflow | PLANNED | Replace normal customer flow with one launcher/assistant in Phase 5. |
| Detector command | Known incorrect example in detailed manual | PLANNED | Correct and regression-test every documented invocation in Phase 5. |
| Robot programs | Required but not supplied as released customer files | PLANNED | Release homing/reference, empty-cell, and final-process programs in Phase 5. |
| Motion/contact limits | Approval record absent | PLANNED | Release speed, acceleration, clearance, force, travel, and proof durations in Phases 2/5. |

## 8. Commercial-pack classification

Create one row for every BOM item using this format:

| Item ID | Friendly name | Classification | Exact SKU/file | Qty installed | Qty spare | Bag/print pack | Status |
|---|---|---|---|---:|---:|---|---|
| Example | Reinforcement plate | SELLER SUPPLIES | OPEN | 1 | 0 | B02-ARM-SAFE | OPEN |

Allowed classifications:

- `SELLER SUPPLIES`;
- `CUSTOMER PRINTS`;
- `CUSTOMER OWNS`;
- `CUSTOMER BUYS EXACT SKU` only when shipping it is impractical;
- `NOT IN V1`.

Prefer `SELLER SUPPLIES` for small compatibility- or safety-critical hardware. Avoid asking the customer to source visually similar fasteners or anchors.

## 9. Phase 1 completion check

- [ ] Exact intended use and excluded uses written.
- [ ] Product format and product boundary confirmed.
- [ ] Every Phase 1 configuration decision is `SELECTED` or intentionally `OUT OF V1`; no required choice remains `OPEN`.
- [ ] Later implementation work is marked `PLANNED` with its owning roadmap phase rather than mistaken for a completed selection.
- [ ] Every selected physical component is available for measurement/testing.
- [ ] Every BOM item has a stable ID and classification.
- [ ] One tool route selected.
- [ ] One camera/support route selected.
- [ ] One phone/case/cable state selected.
- [ ] Supported software/firmware versions selected.
- [ ] Unsupported variants removed from customer claims.

When this checklist is complete, proceed to Roadmap Phase 2 and physically qualify the structural and safety decisions.
