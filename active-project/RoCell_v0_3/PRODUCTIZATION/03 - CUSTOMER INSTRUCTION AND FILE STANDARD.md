# Customer instruction and file standard

This standard applies to every file a customer sees. The existing engineering records may remain more detailed.

## 1. Proposed customer-package structure

```text
RoCell_RC03_Customer_Release/
  00 - START HERE.pdf
  01 - CONFIRM PRODUCT AND INVENTORY/
  02 - VERIFY THE PRINTER/
  03 - PRINT INSPECT AND SORT/
    PRINT 01 - KEYBOARD MASTER/
    PRINT 02 - KEYBOARD SLAVE/
    PRINT 03 - PHONE TCP STATION/
    PRINT 04 - SERVICE PARTS/
    PRINT 05 - CAMERA AND TAG TOOLS/
    PRINT 06 - CONTACT TOOL/
    PRINT 07 - SOFT PARTS AND SPARES/
  04 - PREPARE BOARD AND ARM/
  05 - ASSEMBLE KEYBOARD/
  06 - ASSEMBLE PHONE AND TCP/
  07 - INSTALL TAGS/
  08 - INSTALL AND CALIBRATE CAMERA/
  09 - ASSEMBLE CONTACT TOOL/
  10 - COMMISSION AND USE/
  90 - TROUBLESHOOTING AND SUPPORT/
  91 - MAINTENANCE AND SPARES/
```

The stage number must match the manual chapter, setup-assistant state, Build Passport page, bag/action reference, and support code. The exact number of print packs must be established by the released QIDI projects.

Keep the engineering/manufacturing archive as a separately controlled package. The normal customer download must not expose alternate routes, unreleased models, or source values that compete with the released workflow.

Each applicable customer stage may retain its relevant STL copies to support the prior per-step model-file requirement. Generate those copies from one canonical source, exclude inactive/unreleased models, and mark them `STL SOURCE - USE ONLY THROUGH THE NAMED PRINT PACK`. Native QIDI/3MF projects remain the primary print method.

## 2. One action ID everywhere

Assign one stable ID to each customer action and use it in the manual, illustration, bag label, setup assistant, Build Passport, troubleshooting guide, and support report.

Example: `KB-05.03 — Seat the master station`.

The ID remains stable through wording or artwork changes unless the physical action changes.

## 3. Required action-card format

Every customer action uses this pattern:

### `ACTION-ID — Plain action name`

- **Result:** What will be true when this action is complete.
- **Get:** Exact printed part, hardware bag, consumable, quantity, and tool.
- **Orient:** Named face, molded arrow, FRONT, +X, +Y, or contact direction.
- **Do:** One physical operation in one or two short sentences.
- **Set:** Torque, depth, count, time, temperature, force, or software setting.
- **Check:** One immediately observable or measurable result.
- **STOP if:** Specific symptoms that prohibit continuation.
- **Fix:** One allowed recovery or the exact troubleshooting entry.
- **Record:** Only the simple customer-visible field/photo required.
- **Next:** The next action ID.

An action card may contain only one irreversible operation. Split drilling, bonding, powered motion, firmware change, and destructive testing into separate actions.

## 4. Language rules

Use:

- one verb-led action per numbered item;
- short sentences and plain physical nouns;
- exact part IDs alongside friendly names;
- numeric or tactile checks immediately after the action;
- direct warnings at the point of risk;
- the same term for the same component everywhere.

Do not use these words in a customer action unless they are immediately defined:

- `gently`;
- `just touches`;
- `as specified`;
- `approved`;
- `measured set`;
- `responsible engineering`;
- `find the interference`;
- `tighten evenly`;
- `lightly disturb`;
- `materially disagree`.

Replace them with a spacer, witness mark, torque, force, travel, count, datum, or explicit troubleshooting decision.

## 5. Visual standard

### Required for every stage

- one clean overview showing the finished stage;
- constant board orientation with FRONT and +Y visible;
- all parts labeled with their physical part IDs;
- starting and completed states;
- a picture of the relevant hardware bag.

### Required for every critical action

- close-up from the customer’s actual working view;
- insertion, drilling, tightening, cable, or motion arrow;
- fastener size and bag ID beside the hole;
- tool position and access direction;
- hidden-interface cross-section where seating or engagement cannot be seen;
- correct/incorrect comparison for plausible errors;
- result callout showing the actual inspection point.

Critical means irreversible, hidden, orientation-sensitive, alignment-sensitive, safety-related, measurement-dependent, or likely to cause rework.

Do not rely on color alone. Pair color with text, shape, pattern, or symbol. Images must remain legible on a Letter-size print.

### Minimum additions by current step

| Current step | Required new visuals |
|---|---|
| 00 | QIDI import, profile, critical layer, support, first-layer, coupon, and accept/reject examples. |
| 01 | Tile map, overlap, symbol legend, board workholding, depth-stop cross-section, center audit, anchor installation, and breakout examples. |
| 02 | Released plate drawing, clamp stack, exact placement, E-stop wiring/function, anti-shift, and clearance view. |
| 03-08 | One exploded stack per fastener type; round/radial, seam, rail-key, and cartridge close-ups. |
| 09-10 | Actual phone/case no-go overlay, clamp spacer/indicator, bend radius, tie setting, and correct cable path. |
| 11-12 | Working-page map, six-ID map, +Y alignment, adhesive handling, burnishing, lift/yaw, and accept/reject tags. |
| 13 | Exact support, cable strain relief, expected live view, accepted/rejected captures, named poses, and final PASS screen. |
| 14 | Route-specific exploded view, spring cross-section, travel/force/retention fixture, and TCP procedure. |
| 15 | Exclusion zone, E-stop/observer locations, proof-load directions, empty-motion envelope, and first-contact sequence. |

## 6. Printed-part and hardware naming

### Printed parts

Use a friendly name plus stable ID, for example:

- `Keyboard Master — P-KB-MASTER`;
- `Keyboard Slave — P-KB-SLAVE`;
- `Keyboard Slider — P-KB-SLIDER`;
- `Phone + TCP Base — P-PT-BASE`;
- `Phone Rail — P-PT-RAIL`;
- `TCP Cartridge — P-TCP-CART`.

Mold or emboss, where safe and legible:

- part ID;
- release revision;
- LEFT/RIGHT or MASTER/SLAVE;
- FRONT/+Y or TOP/contact face;
- INSTALL/SPARE where applicable.

### Hardware IDs

Use descriptive stable IDs, for example:

- `H-M4-BH-20` — M4 x 20 button-head screw;
- `H-M4-LP-25` — M4 x 25 low-profile hand screw;
- `L-PIN-6X20` — 6 x 20 mm locator pin.

Never show only `M4 retainer` or an internal feature ID. Show both:

`Front master-station screw — KBL-HOLD-F — H-M4-BH-20`.

## 7. Hardware-bag system

Recommended stage bags:

| Bag | Purpose |
|---|---|
| `B01-BOARD` | Board anchors, locator pins, guide consumables, feet. |
| `B02-ARM-SAFE` | Reinforcement, clamp accessories, anti-shift, E-stop hardware. |
| `B03-KB-MASTER` | Master station hardware. |
| `B04-KB-SLAVE` | Slave station hardware. |
| `B05-KB-DEVICE` | Sliders, pads, and device-contact hardware. |
| `B06-PT-BASE` | Phone/TCP base hardware. |
| `B07-PT-RAIL-TCP` | Rail, cartridge, clamps, cable tie, and tips. |
| `B08-TAGS` | Tags, adhesive, application consumables, and tag spares. |
| `B09-CAMERA` | Camera support, retention, strain relief, and cable hardware. |
| `B10-TOOL` | One released contact-tool route. |
| `B11-SPARES` | Labeled service spares only. |

Every bag label shows:

- plain name and bag ID;
- applicable action range;
- quantity installed and quantity spare;
- part dimensions and head style;
- actual-size silhouette where practical;
- revision/lot;
- `INSTALL`, `SPARE`, `TEST ONLY`, or `DO NOT INSTALL`;
- QR code and an offline printed action reference.

## 8. Print-pack standard

Every customer print pack contains:

1. tested native QIDI/3MF project;
2. bed-layout PNG;
3. finished-part catalog image;
4. exact object count and part IDs;
5. supported material/profile and QIDI Studio version;
6. final sliced time and mass estimate;
7. support/brim/cooldown/removal steps;
8. critical-layer screenshots;
9. inspection and reject card;
10. destination bag/tray label;
11. relevant customer-printable STL source copies in that print pack, generated from the canonical models and clearly secondary to the native project.

Primary file-name pattern:

`PRINT 03 - PHONE TCP STATION [JOB-03A] - {CONSUMER_REV}.3mf`

The filename tells the customer the order and purpose while preserving the internal job ID and revision.

## 9. Measurement standard

### Customer measurement card

Every customer measurement instruction must state:

- datum and exact measurement points;
- axis/direction;
- supplied/released tool or go/no-go fixture;
- force or preload when relevant;
- cycle count and when readings are taken;
- simple pass range or go/no-go result;
- how many values the customer records;
- what to do when one value fails.

Prefer supplied go/no-go gauges, spacers, witnesses, or fixtures over requiring the customer to reproduce engineering metrology.

### Engineering measurement definition

The separate engineering record must additionally define tool resolution/accuracy, fixture qualification, formula, uncertainty budget, worked example, sampling rationale, and derivation of the released customer limit. Do not expose this derivation as a required customer calculation.

## 10. Troubleshooting standard

Each action includes a short recovery box. A master guide uses this structure:

| Symptom | Likely cause | Safe check | Allowed fix | Replace/scrap rule | Return action | Support code |
|---|---|---|---|---|---|---|

Required symptom groups:

- print adhesion, warp, blocked holes, dimensional failure, wrong profile;
- template scale/registration, wrong punch, breakout, anchor spin;
- tight/loose locator, base lift, seam gap, fastener bottoming;
- slider bind, keyboard rock, pad wear;
- rail/key/cartridge seating and height;
- phone clamp, cable strain, button/camera/glass interference;
- tag scale, ID, yaw, lift, and adhesion;
- camera installation, missing tags, calibration rejection;
- spring bind, adapter slip, force/TCP failure;
- E-stop, anti-shift, clearance, collision, and first-contact abort.

Every irreversible failure receives a definite `repair`, `replace`, or `scrap` decision.

## 11. Setup assistant and Build Passport

The customer should not run the current manual Python, JSON, hash, and regeneration workflow.

The setup assistant should:

1. create the Build Passport ID;
2. confirm supported configuration and inventory;
3. show only the next eligible print/stage;
4. accept simple measurements with range validation;
5. capture photos under automatic names;
6. guide camera setup and calibration;
7. run tag and final tests;
8. preserve the internal gate/evidence structure behind the interface;
9. export a plain-language Build Passport and support bundle;
10. resume safely after interruption;
11. operate offline by default and store photos, camera captures, measurements, and reports locally;
12. explain the local storage path, retention, manual export, deletion, and any optional support upload before collecting data;
13. provide a safe local export/recovery path when the assistant cannot continue, without making the engineering CLI the normal fallback.

The customer Build Passport contains:

- product and configuration revision;
- printed-part revisions;
- printer verification;
- board/arm acceptance;
- keyboard acceptance;
- phone/TCP acceptance;
- installed tag map;
- camera calibration;
- contact-tool qualification;
- E-stop and commissioning result;
- customer unit commissioning state, kept distinct from engineering design release and seller kit release;
- maintenance/service entries.

## 12. Customer-package definition of done

A customer-facing stage is complete only when:

- all referenced parts and files exist and open;
- all quantities, IDs, fasteners, tools, settings, and limits are exact;
- each action passes the action-card standard;
- required close-ups and correct/incorrect images exist;
- every STOP has a troubleshooting destination;
- every measurement method is reproducible;
- a reviewer can trace the customer check to its internal engineering gate;
- the action has been physically performed from the customer package;
- no undocumented verbal explanation was required.
