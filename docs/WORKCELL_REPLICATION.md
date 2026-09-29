# Tactevra workcell replication guide

**Document status:** Maintained procurement and replication index  
**Audience:** Prospective builders, reviewers, and contributors  
**Authority:** Informational; controlled BOMs and readiness records remain authoritative

This guide collects the parts, materials, tools, and source records currently
needed to reproduce the Tactevra research workcell. It is deliberately not a
one-click shopping list. Some items are fully specified, while others must be
selected from physical measurements or remain candidates pending qualification.

Use this page to understand the scope and prepare a purchasing worksheet. Before
buying, printing, drilling, or assembling anything, check the linked controlled
records for the exact revision and current gate status.

## Procurement status vocabulary

| Status | Meaning |
| --- | --- |
| **Specified** | The repository records an exact product or engineering specification. Physical acceptance may still be required. |
| **Candidate** | A proposed product, size, or material is recorded but has not completed every qualification gate. |
| **Measure to select** | The final size or variant depends on the builder's received hardware and must not be guessed. |
| **Optional or fallback** | Needed only for a selected route or released fallback configuration. |
| **Existing equipment** | A tool or device expected to be available rather than consumed in the build. |

These labels describe procurement maturity, not permission to operate the robot.

## System-level shopping overview

| Area | Item | Quantity | Current status | Notes |
| --- | --- | ---: | --- | --- |
| Robot | Waveshare RoArm-M3 Pro | 1 | Specified | Primary arm used by the current workcell. |
| Work surface | Birch plywood structural board | 1 | Specified | `610 × 457 × 18 mm` preferred; finish and flatness must pass the build checks. |
| Keyboard | Perixx PERIBOARD-409 | 1 | Specified | Nominal `315 × 147 × 21 mm`; measure the received unit. |
| Phone | Samsung Galaxy A16 5G | 1 | Specified for the phone route | Nominal bare body `164.4 × 77.9 × 7.9 mm`; case and cable change fit. |
| Vision | USB camera | 1 | Candidate / measure to select | Exact model, optical mode, case, cable, and mounting interface must be recorded. |
| Safety | Latching power cutoff or E-stop | 1 | Specified by function | Must be rated for the arm power supply. |
| Fabrication | QIDI X-Plus 4 with 0.4 mm nozzle | 1 | Existing equipment | The controlled RC03 print profiles target this printer configuration. |
| Rigid prints | QIDI ABS Rapido | 1 controlled lot | Specified | Primary rigid material for the current package. |
| Flexible prints | TPU 95A | 1 qualified spool | Candidate lot | Used for contact and compression parts; record the exact product and calibrated preset. |
| Ductile adapters | PETG | 1 qualified spool | Optional / candidate lot | Used only by selected split-adapter routes. |
| Fallback prints | ASA | 1 qualified spool | Optional fallback | Do not purchase for the primary route solely because it appears in the BOM. |

The controlled RC03 BOM contains the full set of board interfaces, station
hardware, tools, cable-management parts, consumables, and service spares:
[`active-project/RoCell_v0_3/BOM.csv`](../active-project/RoCell_v0_3/BOM.csv).

## RC03 workcell hardware categories

The following checklist makes the controlled BOM easier to scope without
replacing it.

### Board and station interfaces

- Six `6 × 20 mm` precision dowel pins: four installed and two spares.
- Twelve M4 board threaded interfaces: nine installed and three spares.
- Candidate M4 station-retention screws in `20 mm` and `25 mm` lengths.
- M4 flat washers, keyboard clamp hardware, and compliant face pads.
- A measured, precut underside reinforcement plate for the factory arm clamp.
- Six board feet and a low-gloss neutral board finish.
- Slow-cure structural epoxy compatible with steel and sealed plywood.

The final insert, screw, washer, and reinforcement selections remain subject to
the package's coupon and received-hardware checks.

### Phone, tool, and cable hardware

- M4 captured nuts and two M4 × 25 mm hand-adjustable phone-clamp screws.
- M3 heat-set inserts and M3 × 10 mm button-head screws for the TCP receiver and
  compliant tool.
- One light compression spring with `OD ≤ 13.5 mm`, `ID ≥ 10.5 mm`, and
  `18–22 mm` free length.
- One `6 mm` smooth rod, `90–110 mm` long, for the keyboard tool route.
- One passive capacitive stylus with an approximately `8.5–9.5 mm` barrel for
  the optional phone route.
- Nylon cable ties, compatible low-profile cable-tie anchors, and removable
  retaining compound.

### Fiducials and cleaning supplies

- Two sheets of matte white letter or A4 paper/card.
- Twelve full-surface matte AprilTag tiles: IDs `0–5` plus one spare set.
- Lint-free wipes and a finish-compatible cleaner.

## Printed static camera portal

The printed portal is maintained as its own revisioned hardware package. Its
authoritative BOM contains every printed part and each fastener quantity:
[`hardware/static_overhead_camera/BOM_PRINTABLE_FRAME.csv`](../hardware/static_overhead_camera/BOM_PRINTABLE_FRAME.csv).

At the current revision, its non-printed procurement groups are:

| Hardware | Quantity | Key requirement |
| --- | ---: | --- |
| M6 × 25 flange-head bolts | 4 | External hex; top-driven corner clamps |
| M6 DIN 985 nyloc nuts | 5 | Includes one sacrificial fit/torque test nut |
| M5 × 75 flange-head bolts | 32 | Structural splice positions |
| M5 × 80 flange-head bolts | 4 | Saddle tower receiver cross-bolts |
| M5 × 85 flange-head bolts | 4 | Carriage-to-boom end collars |
| M5 × 90 flange-head bolts | 8 | Boom-root sandwich straps |
| M5 flanged nyloc nuts | 52 | Includes sacrificial proof/creep-test nuts |
| M4 × 60 button-head bolts | 4 | Camera keeper closure |
| M4 × 70 button-head socket bolts | 3 | Camera leveling screws |
| M4 standard hex nuts | 6 | Captured and jam-nut positions |
| M4 nyloc nuts | 4 | Keeper closure |
| M4 washers | 14 | Leveling and keeper stacks |
| Cable ties, maximum 5 mm width | 6 | Cage, boom, and upright routing |
| Factory-terminated metal safety tether | 1 | Exact construction and load requirements are in the controlled BOM |

The portal also requires ABS Rapido rigid parts and five TPU 95A
contact/compression pads. Use the exact print jobs and processes referenced by
the [portal build guide](../hardware/static_overhead_camera/PRINTABLE_FRAME_BUILD_GUIDE.md),
not loose STL files or an assembly STEP.

## Fabrication and measurement equipment

Plan access to the following equipment before beginning qualification:

- digital calipers;
- an M3 heat-set-insert tip and compatible installation tool;
- hand drill, pilot bits, a `6 mm` brad-point bit, depth collars, and a drill
  square or portable guide;
- filament drying or dry storage suitable for ABS, PETG, TPU, and ASA;
- a `0–50 N` push-pull force gauge with `0.1 N` resolution, or a safe fixture
  with traceable `10 N`, `20 N`, and `50 N` weights;
- a `300 mm` precision straightedge and `0.10 mm`/`0.50 mm` feeler gauges; and
- a calibrated low-range torque driver covering `0.25–0.35 N·m` with an M4 bit.

These tools are part of the acceptance process; owning the nominal components
alone is not enough to reproduce the recorded configuration.

## Items that must not be guessed

Record these from the received hardware before final purchasing or fabrication:

- exact camera model, case dimensions, optical settings, cable, and mount;
- arm-clamp footprint and reinforcement-plate dimensions;
- board insert type and pilot/anchor drilling details after scrap testing;
- station screw lengths and washer dimensions from the actual stack;
- keyboard, phone/case, cable, pins, inserts, nuts, spring, gripper, and tool
  dimensions;
- exact PETG, TPU, or fallback ASA product lot and calibrated printer preset;
- camera screw depth or camera-cage shim selection; and
- all substitutions, which require the same fit and readiness checks as the
  recorded candidate.

## Recommended replication sequence

1. Choose the exact repository revision and record the RC03 controlled revision.
2. Review [pre-hardware readiness](../active-project/RoCell_v0_3/PREHARDWARE_READINESS.md)
   and [print readiness](../active-project/RoCell_v0_3/PRINT_READINESS.md).
3. Copy the controlled BOMs into a private purchasing worksheet without editing
   the source CSV files.
4. Mark every line as on hand, ordered, received, measured, accepted, or held.
5. Complete the received-hardware measurements and diagnostic coupons before
   committing to dependent fastener, insert, camera, or tool variants.
6. Print only jobs explicitly marked ready for the recorded machine, material,
   process, and revision.
7. Follow the [hardware build guide](HARDWARE_BUILD_GUIDE.md) and the generated
   build-by-step package for assembly and evidence capture.

## Source-of-truth map

| Question | Authoritative record |
| --- | --- |
| What must be purchased for RC03? | [RC03 BOM](../active-project/RoCell_v0_3/BOM.csv) |
| Which exact hardware candidate is being evaluated? | [Hardware candidates](../active-project/RoCell_v0_3/config/hardware_candidates.json) |
| Which print jobs are currently eligible? | [Print readiness](../active-project/RoCell_v0_3/PRINT_READINESS.md) |
| Which material and process belongs to each job? | [Print job configuration](../active-project/RoCell_v0_3/config/print_jobs.json) and [print profiles](../active-project/RoCell_v0_3/config/print_profiles.json) |
| How is each interface fastened? | [Fastener map](../active-project/RoCell_v0_3/FASTENER_MAP.csv) |
| What belongs in each assembly kit? | [Job kits](../active-project/RoCell_v0_3/JOB_KITS.csv) |
| What does the printed portal require? | [Portal BOM](../hardware/static_overhead_camera/BOM_PRINTABLE_FRAME.csv) |
| What may be built now? | [Pre-hardware readiness](../active-project/RoCell_v0_3/PREHARDWARE_READINESS.md) and [build tracker](../active-project/RoCell_v0_3/BUILD_TRACKER.md) |

## Contributing replication evidence

Contributions that improve replication are especially useful when they include
an exact part identifier, vendor-neutral specification, received dimensions,
revision, measurement method, and the gate that the evidence resolves. Follow
the [contribution guide](../CONTRIBUTING.md) and do not publish order details,
addresses, serial numbers, credentials, or unsanitized device data.
