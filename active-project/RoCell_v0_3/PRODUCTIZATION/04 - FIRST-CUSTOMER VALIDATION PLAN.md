# First-customer validation plan

The engineer is the first customer, but the roles must not mix during this test.

## 1. Entry gate

Do not begin the customer test until:

- one V1 configuration and route are frozen;
- the engineer reference build has completed all applicable internal Steps 00-15;
- every customer print project was physically printed and accepted;
- all nine board fastener rows are complete;
- reinforcement, clamp, E-stop, anti-shift, camera support, tool, and robot programs are released;
- the customer files contain no known incorrect command or contradictory requirement;
- a read-only release-candidate archive has been generated;
- no open P0/P1 engineering issue remains.

Testing an unfinished configuration mostly measures the designer’s ability to improvise, not the customer experience.

## 2. Prepare a clean customer environment

Use:

- a clean bench;
- one fresh board blank and board offcut;
- fresh material or fully documented released material;
- a fresh set of released hardware/consumable bags;
- an empty Build Passport;
- a clean supported computer user profile or test computer;
- reset/default QIDI Studio state plus only the supplied import/setup method;
- the read-only customer release archive;
- camera/phone for recording the test;
- a visible timer.

Remove from reach:

- CAD source and engineering notes;
- old printed parts and mixed hardware;
- previous evidence folders;
- private command history;
- alternate devices, routes, fasteners, or materials;
- verbal reminders prepared by the engineer.

## 3. Customer-role rules

1. Follow only the customer package.
2. Use only tools and components listed before the applicable action.
3. Do not inspect source JSON, CAD, scripts, parameter files, or internal gates to discover an answer.
4. Do not silently change a slicer setting, model, dimension, fastener, or method.
5. If designer knowledge supplies a missing answer, log a P1 documentation defect before using it.
6. If two interpretations seem reasonable, log P2 and choose neither until the guide identifies a safe branch.
7. Do not edit the customer package during an active test session.
8. Stop immediately for a safety risk or irreversible action without an adequate check.

The first self-build is an **exploratory usability run** used to discover defects. Stop and correct any P0 before resuming powered or irreversible work. After all P0-P2 corrections, perform a separate **clean acceptance self-build**; the pass criteria below apply to that second run.

## 4. Record every stage

For each of the ten customer stages record:

- start and finish time;
- action IDs completed;
- first-attempt success or failure;
- wrong part, bag, tool, orientation, setting, or file selected;
- rereads and searches longer than one minute;
- backtracking and repeated actions;
- help or engineering knowledge required;
- missing tool, component, value, visual, or recovery instruction;
- reprint, repair, scrap, and material/time loss;
- unsafe act, near miss, or required intervention;
- actual acceptance values and result;
- confidence/clarity rating from 1 to 5;
- photo of the starting and accepted/failure state.

Use an issue entry containing:

`Issue ID | Date | Product revision | Stage/action | Severity | Observed behavior | Expected behavior | Evidence | Owning source | Correction | Regression result`

## 5. Run order

1. Stage 1 — Confirm compatibility and inventory.
2. Stage 2 — Verify printer.
3. Stage 3 — Print, inspect, and sort.
4. Stage 4 — Prepare board and arm safety system.
5. Stage 5 — Assemble keyboard station.
6. Stage 6 — Assemble phone/TCP station.
7. Stage 7 — Install reference tags.
8. Stage 8 — Install and calibrate camera.
9. Stage 9 — Assemble and qualify tool.
10. Stage 10 — Commission and release.

Finish or formally stop one stage before opening the next stage’s detailed instructions.

## 6. Severity rules

### P0 — Release blocked

- safety risk or unsafe instruction;
- collision, unintended motion/contact, E-stop failure, electrical risk;
- physical incompatibility;
- irreversible board/tag/device damage caused by the released workflow;
- customer is directed to pass an actually unsafe or out-of-limit state.

### P1 — Release blocked

- customer cannot continue without undocumented engineering knowledge;
- missing/wrong part, hardware, file, program, command, tool, or acceptance value;
- prepared print project or setup workflow cannot be completed;
- required result is impossible to record or verify.

### P2 — Must fix and regression-test

- two plausible interpretations;
- incorrect first attempt followed by documented recovery;
- avoidable rework, wrong orientation, wrong fastener, or repeated search;
- a measurement or visual is difficult but possible.

### P3 — Polish backlog

- spelling, visual alignment, minor navigation, or non-blocking presentation issue.

## 7. Acceptance self-build pass criteria

The clean acceptance self-build passes only when:

- zero P0 issues occur;
- zero unresolved P1 issues remain;
- no undocumented component, tool, value, or decision is used;
- no CAD, JSON, parameter, or source edit is required;
- every prepared QIDI project opens and prints successfully;
- no production geometry is scaled, moved, auto-oriented, or repaired outside the stated process;
- every accepted part is identified and bagged correctly;
- no irreversible board or tag error occurs;
- all ten stages reach PASS through their stated checks;
- every failure encountered has a documented and successful recovery;
- software installs and produces valid reports without manual command repair;
- E-stop, empty motion, first contact, and customer unit commissioning pass; engineering design and seller kit releases must already exist;
- published time/tool/material expectations can be updated from the actual record.

The exploratory run does not receive a release PASS. A release candidate requires the separate clean acceptance run after corrections.

## 8. Correction loop

For each P0-P2 issue:

1. Identify the owning layer: product decision, BOM, CAD, print project, board process, software, visual, instruction, or packaging.
2. Correct the owning source first.
3. Regenerate every dependent artifact.
4. Run automated package validation.
5. Physically regression-test the failed action and all affected downstream checks.
6. Update the issue with evidence.
7. Close it only when the original failure cannot be reproduced using the corrected customer package.

Do not fix a hardware or software defect only by warning the customer.

## 9. External beta after the self-test

The designer cannot provide a fully blind usability test. After the second clean self-build:

1. Recruit at least three unfamiliar builders for alpha/beta use; reach five before commercial release if practical.
2. Ensure they match the stated skill level.
3. Test every product route, guide format, device variant, and optional feature that will be advertised. If it is not tested, remove it from the compatibility claim.
4. Observe without coaching unless safety requires intervention.
5. Record the same action-level data.
6. Require fresh builders to regression-test corrected P0-P2 actions.

Recommended commercial usability targets:

- zero safety intervention, collision, unintended contact, or E-stop failure;
- zero undocumented seller decision;
- 100 percent of builders complete using the manual and documented recovery;
- at least 95 percent of physical actions correct on the first attempt;
- 100 percent of completed builds pass engineering acceptance limits;
- zero irreversible board-drilling or tag-placement error;
- 100 percent inventory and part-identification accuracy;
- software succeeds on the first attempt for at least 80 percent of beta builders and for 100 percent through documented recovery;
- no repeated documentation-caused error across more than one tester;
- stage clarity averages at least 4/5, with no safety-critical action below 4/5.

If the product later supports many phones, cameras, printers, or tool routes, increase the beta sample to cover each advertised configuration.

## 10. Final test report

The test report should contain:

- tested release archive name and checksum;
- hardware, device, material, printer, software, and firmware revisions;
- tester skill profile;
- time and outcome per stage;
- all P0-P3 issues;
- reprints, scrap, and recoveries;
- engineering acceptance results;
- software/calibration report;
- final Build Passport;
- separate engineering design-release, seller kit-release, and customer unit-commissioning results;
- unresolved limitations;
- signed release recommendation or rejection.
